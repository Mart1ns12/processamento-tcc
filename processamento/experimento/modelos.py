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


def contribuicoes(modelo: xgb.XGBClassifier, X: pd.DataFrame) -> pd.DataFrame:
    """Contribuição de cada variável à margem (SHAP do XGBoost); a última coluna é o viés."""
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


_PREFIXOS_MODELO = {"1": "xgb-m1-", "3": "xgb-"}


def nome_modelo(mes: str, modelo: str = "3") -> str:
    """Nome-base do arquivo do modelo: "3" -> "xgb-AAAA-MM"; "1" -> "xgb-m1-AAAA-MM"."""
    if modelo not in _PREFIXOS_MODELO:
        raise ValueError(f"modelo desconhecido: {modelo!r} (use {', '.join(_PREFIXOS_MODELO)})")
    return f"{_PREFIXOS_MODELO[modelo]}{mes}"


def salvar_modelo(modelo: xgb.XGBClassifier, metadados: dict, pasta: Path, nome: str) -> tuple[Path, Path]:
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


def carregar_modelo(caminho_json: Path) -> tuple[xgb.XGBClassifier, dict]:
    """Relê o modelo e o `.meta.json` ao lado (mesmo nome, sufixo `.meta.json`)."""
    caminho_json = Path(caminho_json)
    modelo = xgb.XGBClassifier()
    modelo.load_model(caminho_json)
    caminho_meta = caminho_json.with_name(f"{caminho_json.stem}.meta.json")
    metadados = json.loads(caminho_meta.read_text(encoding="utf-8"))
    return modelo, metadados
