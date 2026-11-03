"""Modelos do experimento: XGBoost (ajuste, previsão, contribuições), logística, regra da volatilidade
e gravação/leitura do modelo com o seu `.meta.json` (plano da etapa 6, fase 4).

Funções puras sobre DataFrames e arrays, exceto `salvar_modelo`, `carregar_modelo` e `sha256_arquivo`,
que leem ou gravam arquivos na pasta dada. Ausência continua NaN: o XGBoost trata NaN sozinho e a
logística imputa só dentro do próprio Pipeline. Nada de banco ou rede.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.special import expit
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from processamento.experimento import dataset, preparacao

TAMANHO_BLOCO = 1024 * 1024
CHAVES_METADADOS = (
    "modelo",
    "versao_preparacao",
    "versao_noticias",
    "colunas",
    "blocos",
    "hiperparametros",
    "semente",
    "periodo_treino",
    "n_linhas_treino",
    "dataset",
    "universo",
    "metricas_validacao",
    "calibracao",
    "provisorio",
    "aviso",
    "versoes",
    "gerado_em",
    "teste_final",
)


def treinar_xgb(X: pd.DataFrame, y: pd.Series, hiper: dict, semente: int) -> xgb.XGBClassifier:
    """Ajusta um XGBClassifier com semente fixa, 1 thread e histograma (reprodutível)."""
    modelo = xgb.XGBClassifier(
        **hiper,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=semente,
        n_jobs=1,
        missing=np.nan,
    )
    return modelo.fit(X.astype(float), y.astype(int))


def prob_xgb(modelo: xgb.XGBClassifier, X: pd.DataFrame) -> np.ndarray:
    """Probabilidade da classe 1."""
    return modelo.predict_proba(X.astype(float))[:, 1]


def margem_xgb(modelo: xgb.XGBClassifier, X: pd.DataFrame) -> np.ndarray:
    """Margem bruta (logit) antes da sigmoide."""
    return modelo.get_booster().predict(xgb.DMatrix(X, missing=np.nan), output_margin=True)


def contribuicoes(modelo, X: pd.DataFrame) -> pd.DataFrame:
    """Contribuição de cada variável à margem (SHAP do XGBoost, ou a conta da logística); a última coluna é o viés."""
    if isinstance(modelo, ModeloLogistico):
        return modelo.contribuicoes(X)
    valores = modelo.get_booster().predict(xgb.DMatrix(X, missing=np.nan), pred_contribs=True)
    return pd.DataFrame(valores, columns=[*X.columns, "vies"], index=X.index)


def treinar_logistica(X: pd.DataFrame, y: pd.Series, c: float, semente: int) -> Pipeline:
    """Regressão logística: imputa a mediana (com indicador), padroniza e ajusta.

    `keep_empty_features=True` é obrigatório: sem ele, uma coluna toda vazia na dobra gera aviso.
    """
    pipe = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(C=c, max_iter=1000, random_state=semente),
    )
    return pipe.fit(X.astype(float), y.astype(int))


def prob_logistica(pipe: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """Probabilidade da classe 1 da logística."""
    return pipe.predict_proba(X.astype(float))[:, 1]


class ModeloLogistico:
    """Logística gravada em JSON (sem pickle), com a mesma conta do Pipeline de `treinar_logistica`.

    Guarda o que o Pipeline aprendeu: a mediana de cada coluna, as colunas com indicador de ausência, a média e a
    escala da padronização e os coeficientes. Prever e explicar (contribuição de cada coluna em log-odds) não
    precisa de sklearn. A entrada continua com NaN: a mediana só entra aqui, como no Pipeline.
    """

    def __init__(self, colunas, medianas, indicadoras, media, escala, coef, intercepto: float):
        self.colunas = [str(c) for c in colunas]
        self.medianas = np.asarray(medianas, dtype=float)
        self.indicadoras = np.asarray(indicadoras, dtype=int)
        self.media = np.asarray(media, dtype=float)
        self.escala = np.asarray(escala, dtype=float)
        self.coef = np.asarray(coef, dtype=float)
        self.intercepto = float(intercepto)

    @classmethod
    def de_pipeline(cls, pipe: Pipeline) -> ModeloLogistico:
        """Copia os parâmetros de um Pipeline ajustado por `treinar_logistica` (com DataFrame, para ter os nomes)."""
        imputador, padronizador, logistica = [passo for _, passo in pipe.steps]
        if not hasattr(imputador, "feature_names_in_"):
            raise ValueError("o Pipeline precisa ter sido ajustado com DataFrame (colunas com nome)")
        indicador = imputador.indicator_
        return cls(
            colunas=imputador.feature_names_in_,
            medianas=imputador.statistics_,
            indicadoras=[] if indicador is None else indicador.features_,
            media=padronizador.mean_,
            escala=padronizador.scale_,
            coef=logistica.coef_[0],
            intercepto=logistica.intercept_[0],
        )

    def _contribuicao(self, X: pd.DataFrame) -> np.ndarray:
        """Termo de cada coluna em log-odds (n × colunas), com o termo do indicador de ausência somado na sua coluna."""
        x = X[self.colunas].to_numpy(dtype=float)
        p = x.shape[1]
        nan = np.isnan(x)
        imp = np.where(nan, self.medianas, x)
        cheio = np.hstack([imp, nan[:, self.indicadoras].astype(float)])
        termo = self.coef * (cheio - self.media) / self.escala
        contrib = termo[:, :p].copy()
        contrib[:, self.indicadoras] += termo[:, p:]
        return contrib

    def margem(self, X: pd.DataFrame) -> np.ndarray:
        """Margem (logit) de cada linha, antes da sigmoide."""
        return self._contribuicao(X).sum(axis=1) + self.intercepto

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Duas colunas como no sklearn: [P(classe 0), P(classe 1)]."""
        p1 = expit(self.margem(X))
        return np.column_stack([1.0 - p1, p1])

    def contribuicoes(self, X: pd.DataFrame) -> pd.DataFrame:
        """Contribuição de cada coluna à margem; a última coluna é o viés (intercepto). Soma = logit."""
        vies = np.full(len(X), self.intercepto)
        return pd.DataFrame(
            np.column_stack([self._contribuicao(X), vies]), columns=[*self.colunas, "vies"], index=X.index
        )

    def save_model(self, caminho: Path | str) -> None:
        """Grava o modelo em JSON explícito (sem pickle). Os números voltam exatamente iguais ao serem lidos."""
        dados = {
            "familia": "logistica",
            "colunas": self.colunas,
            "medianas": self.medianas.tolist(),
            "indicadoras": self.indicadoras.tolist(),
            "media": self.media.tolist(),
            "escala": self.escala.tolist(),
            "coef": self.coef.tolist(),
            "intercepto": self.intercepto,
        }
        Path(caminho).write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def carregar(cls, caminho: Path | str) -> ModeloLogistico:
        """Relê o JSON gravado por `save_model`."""
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        if dados.get("familia") != "logistica":
            raise ValueError(f"{caminho} não é um modelo logístico (familia={dados.get('familia')!r})")
        return cls(
            colunas=dados["colunas"],
            medianas=dados["medianas"],
            indicadoras=dados["indicadoras"],
            media=dados["media"],
            escala=dados["escala"],
            coef=dados["coef"],
            intercepto=dados["intercepto"],
        )


def prob(modelo, X: pd.DataFrame) -> np.ndarray:
    """Probabilidade da classe 1 de qualquer família (XGBoost ou logística)."""
    if isinstance(modelo, ModeloLogistico):
        return modelo.predict_proba(X)[:, 1]
    return prob_xgb(modelo, X)


def treinar_lgbm(X: pd.DataFrame, y: pd.Series, hiper: dict, semente: int):
    """LightGBM com os mesmos hiperparâmetros do XGBoost, 1 thread e determinístico. NaN é tratado sozinho."""
    import lightgbm as lgb   # só a busca precisa: a rotina diária não depende disso
    modelo = lgb.LGBMClassifier(
        n_estimators=hiper["n_estimators"], max_depth=hiper["max_depth"], num_leaves=2 ** hiper["max_depth"],
        learning_rate=hiper["learning_rate"], subsample=hiper["subsample"], subsample_freq=1,
        colsample_bytree=hiper["colsample_bytree"], min_sum_hessian_in_leaf=hiper["min_child_weight"],
        min_child_samples=1, reg_lambda=hiper["reg_lambda"], random_state=semente, n_jobs=1,
        deterministic=True, force_row_wise=True, verbosity=-1,
    )
    return modelo.fit(X.astype(float), y.astype(int))


def prob_lgbm(modelo, X: pd.DataFrame) -> np.ndarray:
    """Probabilidade da classe 1 do LightGBM."""
    return modelo.predict_proba(X.astype(float))[:, 1]


def score_volatilidade(preparado: pd.DataFrame) -> np.ndarray:
    """Regra da volatilidade: 1 − rank de `volatilidade_20d` no pregão (mais calma = maior score).

    `preparado` já passou por `preparacao.preparar`. Ausência (NaN) vira 0,5, no meio da escala.
    """
    score = 1.0 - preparado["volatilidade_20d"].to_numpy(dtype=float)
    return np.where(np.isnan(score), 0.5, score)


def preparacao_compativel(meta: dict | None) -> bool:
    """O modelo foi treinado com a preparação atual? Sem a chave nos metadados (modelo antigo), não."""
    return meta is not None and meta.get("versao_preparacao") == preparacao.VERSAO_PREPARACAO


def sha256_arquivo(caminho: Path) -> str:
    """SHA-256 do arquivo, lido em blocos de 1 MiB."""
    h = hashlib.sha256()
    with open(caminho, "rb") as arq:
        for bloco in iter(lambda: arq.read(TAMANHO_BLOCO), b""):
            h.update(bloco)
    return h.hexdigest()


_PREFIXOS_MODELO = {
    "xgb": {"1": "xgb-m1-", "3": "xgb-"},
    "logistica": {"1": "logistica-m1-", "3": "logistica-"},
}
FAMILIA_PADRAO = "xgb"


def nome_modelo(mes: str, modelo: str = "3", familia: str = FAMILIA_PADRAO) -> str:
    """Nome-base do arquivo do modelo: "3" -> "xgb-AAAA-MM"; "1" -> "xgb-m1-AAAA-MM" (logística: "logistica-...")."""
    if familia not in _PREFIXOS_MODELO:
        raise ValueError(f"família desconhecida: {familia!r} (use {', '.join(_PREFIXOS_MODELO)})")
    prefixos = _PREFIXOS_MODELO[familia]
    if modelo not in prefixos:
        raise ValueError(f"modelo desconhecido: {modelo!r} (use {', '.join(prefixos)})")
    return f"{prefixos[modelo]}{mes}"


def salvar_modelo(modelo, metadados: dict, pasta: Path, nome: str) -> tuple[Path, Path]:
    """Grava `<nome>.json` (modelo) e `<nome>.meta.json` (metadados). Falta chave obrigatória -> ValueError."""
    faltando = [chave for chave in CHAVES_METADADOS if chave not in metadados]
    if faltando:
        raise ValueError(f"faltam chaves nos metadados: {faltando}")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{nome}.json"
    caminho_meta = pasta / f"{nome}.meta.json"
    modelo.save_model(caminho)
    texto = json.dumps(metadados, indent=2, ensure_ascii=False, default=dataset._json_padrao)
    caminho_meta.write_text(texto, encoding="utf-8")
    return caminho, caminho_meta


def carregar_modelo(caminho_json: Path) -> tuple[xgb.XGBClassifier | ModeloLogistico, dict]:
    """Relê o modelo e o `.meta.json` ao lado (mesmo nome, sufixo `.meta.json`).

    A meta é lida antes: `familia` ausente = xgb (modelos antigos). Logística vira `ModeloLogistico`.
    """
    caminho_json = Path(caminho_json)
    caminho_meta = caminho_json.with_name(f"{caminho_json.stem}.meta.json")
    metadados = json.loads(caminho_meta.read_text(encoding="utf-8"))
    if metadados.get("familia", FAMILIA_PADRAO) == "logistica":
        return ModeloLogistico.carregar(caminho_json), metadados
    modelo = xgb.XGBClassifier()
    modelo.load_model(caminho_json)
    return modelo, metadados
