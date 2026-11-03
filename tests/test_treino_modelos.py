"""Testes de modelos.py (etapa 6, fase 4): XGBoost, contribuições, logística, regra da volatilidade
e gravação/leitura do modelo. Dados sintéticos pequenos; nenhum teste usa banco ou rede.
"""

import hashlib
import json
import warnings

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento.experimento import dataset, modelos, treino, validacao
from processamento.experimento.preparacao import (
    VERSAO_PREPARACAO,
    colunas_do_modelo,
    COLUNAS_ALVO,
    COLUNAS_BRUTAS,
    COLUNAS_RANK,
    IDENTIFICACAO,
    preparar,
)

NAN = np.nan
HIPER = {"n_estimators": 50}


def _dados_sinteticos():
    """X 2000×4 (beta todo NaN, tom NaN a cada 7 linhas) e y binário ligado a ret_1d."""
    rng = np.random.default_rng(0)
    n = 2000
    ret_1d = rng.normal(0, 1, n)
    ret_5d = rng.normal(0, 2, n)
    tom = rng.uniform(-1, 1, n)
    tom[::7] = NAN
    ruido = rng.normal(0, 0.3, n)
    X = pd.DataFrame({"ret_1d": ret_1d, "ret_5d": ret_5d, "noticias_dia_tom": tom, "beta": np.full(n, NAN)})
    y = pd.Series(((ret_1d + ruido) > 0.5).astype(int))
    return X, y


def _dataset(linhas):
    """DataFrame com todas as colunas do dataset; cada dict de `linhas` sobrescreve os padrões (NaN)."""
    colunas = IDENTIFICACAO + COLUNAS_RANK + COLUNAS_BRUTAS + COLUNAS_ALVO
    registros = []
    for lin in linhas:
        reg = {c: NAN for c in colunas}
        reg.update({"empresa": lin["ticker"], "setor": "S1", "universo": True, "dia_resultado": False})
        reg.update(lin)
        registros.append(reg)
    df = pd.DataFrame(registros, columns=colunas)
    df["data"] = pd.to_datetime(df["data"])
    return df


def _caso_volatilidade():
    """Caso 6 do plano: seis ações num único pregão, com volatilidade_20d e alvo conhecidos."""
    base = {"data": "2026-06-18", "ret_ibov_t1": 0.0}
    linhas = [
        {**base, "ticker": "AAAA3", "volatilidade_20d": 0.010, "alvo": 1, "ret_t1": 0.01},
        {**base, "ticker": "BBBB3", "volatilidade_20d": 0.030, "alvo": 0, "ret_t1": -0.02},
        {**base, "ticker": "CCCC3", "volatilidade_20d": 0.020, "alvo": 0, "ret_t1": -0.01},
        {**base, "ticker": "DDDD3", "volatilidade_20d": NAN, "alvo": 1, "ret_t1": 0.03},
        {**base, "ticker": "EEEE3", "volatilidade_20d": 0.020, "alvo": 1, "ret_t1": 0.02},
        {**base, "ticker": "FFFF3", "volatilidade_20d": 0.050, "alvo": 0, "ret_t1": -0.03},
    ]
    return preparar(_dataset(linhas))


# --- Caso 8, parte 1: contribuições (pred_contribs) ---------------------------------------------


def test_contribuicoes_somam_a_margem():
    X, y = _dados_sinteticos()
    modelo = modelos.treinar_xgb(X, y, HIPER, semente=0)
    contrib = modelos.contribuicoes(modelo, X)
    assert contrib.shape == (2000, 5)
    assert contrib.columns[-1] == "vies"
    assert list(contrib.columns[:-1]) == list(X.columns)
    assert contrib.index.equals(X.index)
    margem = modelos.margem_xgb(modelo, X)
    assert np.allclose(contrib.sum(axis=1).to_numpy(), margem, atol=1e-4)
    assert np.allclose(1 / (1 + np.exp(-margem)), modelos.prob_xgb(modelo, X), atol=1e-6)


# --- Caso 10: semente, arquivo do modelo, sha256, nomes ------------------------------------------


def test_mesma_semente_mesma_previsao():
    X, y = _dados_sinteticos()
    m1 = modelos.treinar_xgb(X, y, HIPER, semente=0)
    m2 = modelos.treinar_xgb(X, y, HIPER, semente=0)
    assert np.array_equal(modelos.prob_xgb(m1, X), modelos.prob_xgb(m2, X))


def _metadados(X):
    return {
        "modelo": "3",
        "versao_noticias": "v-teste",
        "versao_preparacao": VERSAO_PREPARACAO,
        "colunas": list(X.columns),
        "blocos": ("preco_contexto",),
        "hiperparametros": HIPER,
        "semente": 0,
        "periodo_treino": ("2026-01-01", "2026-05-31"),
        "n_linhas_treino": 2000,
        "dataset": "dataset-todas-2026-10-21.csv",
        "universo": "todas",
        "metricas_validacao": {"auc": 0.5},
        "calibracao": {"ece": 0.1, "brier": 0.25},
        "provisorio": True,
        "aviso": "TESTE DE FUNCIONAMENTO",
        "versoes": {"xgboost": "3.4.1"},
        "gerado_em": "2026-10-23T12:00:00",
        "teste_final": None,
    }


def test_salvar_e_carregar_modelo(tmp_path):
    X, y = _dados_sinteticos()
    modelo = modelos.treinar_xgb(X, y, HIPER, semente=0)
    meta = _metadados(X)
    caminho, caminho_meta = modelos.salvar_modelo(modelo, meta, tmp_path, "xgb-2026-06")
    assert caminho.name == "xgb-2026-06.json" and caminho.exists()
    assert caminho_meta.name == "xgb-2026-06.meta.json" and caminho_meta.exists()

    carregado, meta_lido = modelos.carregar_modelo(caminho)
    assert np.array_equal(modelos.prob_xgb(carregado, X), modelos.prob_xgb(modelo, X))
    # tuplas viram listas depois do vaivém em JSON
    esperado = json.loads(json.dumps(meta, indent=2, ensure_ascii=False, default=dataset._json_padrao))
    assert meta_lido == esperado
    assert meta_lido["colunas"] == list(X.columns)


def test_salvar_sem_chave_obrigatoria_da_erro(tmp_path):
    X, y = _dados_sinteticos()
    modelo = modelos.treinar_xgb(X, y, HIPER, semente=0)
    meta = _metadados(X)
    del meta["semente"]
    with pytest.raises(ValueError):
        modelos.salvar_modelo(modelo, meta, tmp_path, "xgb-2026-06")


def test_sha256_gabaritos(tmp_path):
    arq_abc = tmp_path / "abc.bin"
    arq_abc.write_bytes(b"abc")
    assert modelos.sha256_arquivo(arq_abc) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    arq_csv = tmp_path / "amostra.csv"
    arq_csv.write_bytes(b"data,ticker,alvo\n2026-06-18,AAAA3,1\n")
    assert modelos.sha256_arquivo(arq_csv) == "3299a78cbf26ca7db4d569949fb37a48c530bda9e115520700648ecbbdb23220"


def test_sha256_em_blocos_bate_com_hashlib(tmp_path):
    conteudo = bytes(range(256)) * (10 * 1024 + 3)  # mais de 2 blocos de 1 MiB
    arq = tmp_path / "grande.bin"
    arq.write_bytes(conteudo)
    assert modelos.sha256_arquivo(arq) == hashlib.sha256(conteudo).hexdigest()


def test_nome_modelo():
    assert modelos.nome_modelo("2026-06") == "xgb-2026-06"
    assert modelos.nome_modelo("2026-06", "1") == "xgb-m1-2026-06"


def test_nome_modelo_logistica_e_familia_invalida():
    assert modelos.nome_modelo("2026-06", familia="logistica") == "logistica-2026-06"
    assert modelos.nome_modelo("2026-06", "1", "logistica") == "logistica-m1-2026-06"
    assert modelos.nome_modelo("2026-06", "3", "xgb") == "xgb-2026-06"
    with pytest.raises(ValueError):
        modelos.nome_modelo("2026-06", familia="lgbm")


# --- Logística em JSON (ModeloLogistico) ----------------------------------------------------------

LINHAS_CASO_LOGISTICO = pd.DataFrame({"a": [0.75, 0.25, NAN], "b": [0.4, NAN, 0.2]})


def _logistica_fixture():
    """Parâmetros fixos do plano (fase 2): a tem mediana 0,5; b tem mediana 0,2 e indicador de ausência."""
    return modelos.ModeloLogistico(
        colunas=["a", "b"], medianas=[0.5, 0.2], indicadoras=[1], media=[0.5, 0.2, 0.25],
        escala=[0.25, 0.1, 0.5], coef=[0.4, -0.2, 0.6], intercepto=-0.1,
    )


def test_logistica_caso_do_plano_contribuicoes_e_prob():
    modelo = _logistica_fixture()
    contrib = modelo.contribuicoes(LINHAS_CASO_LOGISTICO)
    assert list(contrib.columns) == ["a", "b", "vies"]
    np.testing.assert_allclose(contrib["a"], [0.4, -0.4, 0.0], atol=1e-9)
    np.testing.assert_allclose(contrib["b"], [-0.7, 0.9, -0.3], atol=1e-9)
    np.testing.assert_allclose(contrib["vies"], [-0.1, -0.1, -0.1], atol=1e-12)
    np.testing.assert_allclose(modelos.prob(modelo, LINHAS_CASO_LOGISTICO), [0.40131234, 0.59868766, 0.40131234], atol=1e-8)


def test_logistica_pipeline_real_bate_com_a_conta_propria():
    X, y = _dados_sinteticos()  # beta todo NaN (coluna vazia no ajuste) e tom NaN a cada 7 linhas
    pipe = modelos.treinar_logistica(X, y, c=1.0, semente=0)
    modelo = modelos.ModeloLogistico.de_pipeline(pipe)
    assert modelo.colunas == list(X.columns)
    p_pipe = pipe.predict_proba(X.astype(float))[:, 1]
    assert np.max(np.abs(modelos.prob(modelo, X) - p_pipe)) <= 1e-12
    contrib = modelo.contribuicoes(X)
    assert np.allclose(contrib.sum(axis=1), pipe.decision_function(X.astype(float)), atol=1e-9)


def test_logistica_json_ida_e_volta_identica(tmp_path):
    X, y = _dados_sinteticos()
    modelo = modelos.ModeloLogistico.de_pipeline(modelos.treinar_logistica(X, y, c=1.0, semente=0))
    caminho = tmp_path / "logistica-2026-06.json"
    modelo.save_model(caminho)
    assert json.loads(caminho.read_text(encoding="utf-8"))["familia"] == "logistica"  # JSON explícito, sem pickle
    lido = modelos.ModeloLogistico.carregar(caminho)
    assert lido.colunas == modelo.colunas and lido.intercepto == modelo.intercepto
    for atributo in ("medianas", "indicadoras", "media", "escala", "coef"):
        assert np.array_equal(getattr(lido, atributo), getattr(modelo, atributo)), atributo
    assert np.array_equal(modelos.prob(lido, X), modelos.prob(modelo, X))
    regravado = tmp_path / "copia.json"
    lido.save_model(regravado)
    assert regravado.read_text(encoding="utf-8") == caminho.read_text(encoding="utf-8")


def test_logistica_dois_ajustes_iguais():
    X, y = _dados_sinteticos()
    m1 = modelos.ModeloLogistico.de_pipeline(modelos.treinar_logistica(X, y, c=1.0, semente=0))
    m2 = modelos.ModeloLogistico.de_pipeline(modelos.treinar_logistica(X, y, c=1.0, semente=0))
    for atributo in ("medianas", "indicadoras", "media", "escala", "coef"):
        assert np.array_equal(getattr(m1, atributo), getattr(m2, atributo)), atributo
    assert m1.intercepto == m2.intercepto


def test_salvar_e_carregar_logistica_pelo_nome_da_familia(tmp_path):
    X, y = _dados_sinteticos()
    modelo = modelos.ModeloLogistico.de_pipeline(modelos.treinar_logistica(X, y, c=1.0, semente=0))
    meta = _metadados(X)
    meta["familia"] = "logistica"
    meta["hiperparametros"] = {"C": 1.0}
    caminho, _ = modelos.salvar_modelo(modelo, meta, tmp_path, modelos.nome_modelo("2026-06", familia="logistica"))
    assert caminho.name == "logistica-2026-06.json"
    carregado, meta_lido = modelos.carregar_modelo(caminho)
    assert isinstance(carregado, modelos.ModeloLogistico)
    assert meta_lido["familia"] == "logistica" and meta_lido["hiperparametros"] == {"C": 1.0}
    assert np.array_equal(modelos.prob(carregado, X), modelos.prob(modelo, X))


def test_carregar_modelo_sem_familia_e_xgb(tmp_path):
    X, y = _dados_sinteticos()
    modelo = modelos.treinar_xgb(X, y, HIPER, semente=0)
    caminho, _ = modelos.salvar_modelo(modelo, _metadados(X), tmp_path, "xgb-2026-06")
    carregado, _ = modelos.carregar_modelo(caminho)
    assert isinstance(carregado, xgb.XGBClassifier)


# --- Logística ------------------------------------------------------------------------------------


def test_logistica_sem_aviso_com_coluna_toda_nan():
    X, y = _dados_sinteticos()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pipe = modelos.treinar_logistica(X, y, c=1.0, semente=0)
        p = modelos.prob_logistica(pipe, X)
    assert p.shape == (2000,)
    assert ((p > 0) & (p < 1)).all()


# --- Caso 6: regra da volatilidade (score) --------------------------------------------------------


def test_score_volatilidade_gabarito():
    preparado = _caso_volatilidade()
    score = modelos.score_volatilidade(preparado)
    esperado = {"AAAA3": 1.0, "BBBB3": 0.25, "CCCC3": 0.625, "DDDD3": 0.5, "EEEE3": 0.625, "FFFF3": 0.0}
    obtido = dict(zip(preparado["ticker"], score))
    assert set(obtido) == set(esperado)
    for ticker, valor in esperado.items():
        assert obtido[ticker] == pytest.approx(valor, abs=1e-12), ticker


def test_score_volatilidade_top_via_avaliacao():
    avaliacao = pytest.importorskip("processamento.experimento.avaliacao")
    preparado = _caso_volatilidade()
    df = preparado.assign(score=modelos.score_volatilidade(preparado))

    ordenado = avaliacao.ordenar_no_dia(df, "score")
    assert list(ordenado["ticker"]) == ["AAAA3", "CCCC3", "EEEE3", "DDDD3", "BBBB3", "FFFF3"]

    top3 = avaliacao.resumo_diario(df, 3)
    assert top3["acerto_top"].iloc[0] == pytest.approx(2 / 3, abs=1e-12)
    assert top3["excesso_top"].iloc[0] == pytest.approx(0.02 / 3, abs=1e-12)

    top5 = avaliacao.resumo_diario(df, 5)
    assert top5["acerto_top"].iloc[0] == pytest.approx(0.6, abs=1e-12)
    assert top5["excesso_top"].iloc[0] == pytest.approx(0.006, abs=1e-12)


# --- Fase 2.1: LightGBM (só a busca usa; a rotina diária não depende dele) -----------------------

HIPER_LGBM = {
    "n_estimators": 50, "max_depth": 3, "learning_rate": 0.03, "subsample": 0.8,
    "colsample_bytree": 0.8, "min_child_weight": 50, "reg_lambda": 5,
}


def test_prob_lgbm_entre_0_e_1_com_nan():
    X, y = _dados_sinteticos()
    modelo = modelos.treinar_lgbm(X, y, HIPER_LGBM, semente=0)
    p = modelos.prob_lgbm(modelo, X)
    assert p.shape == (2000,)
    assert np.isfinite(p).all()
    assert ((p >= 0) & (p <= 1)).all()


def test_lgbm_duas_execucoes_dao_o_mesmo_array():
    X, y = _dados_sinteticos()
    primeira = modelos.prob_lgbm(modelos.treinar_lgbm(X, y, HIPER_LGBM, semente=0), X)
    segunda = modelos.prob_lgbm(modelos.treinar_lgbm(X, y, HIPER_LGBM, semente=0), X)
    assert np.array_equal(primeira, segunda)


def test_modelos_nao_importa_lightgbm_no_topo():
    """A rotina diária importa `modelos`: o import de lightgbm tem de ficar dentro de `treinar_lgbm`."""
    import ast
    from pathlib import Path

    arvore = ast.parse(Path(modelos.__file__).read_text(encoding="utf-8"))
    topo = [n for n in arvore.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    nomes = {a.name.split(".")[0] for n in topo for a in n.names}
    nomes |= {(n.module or "").split(".")[0] for n in topo if isinstance(n, ast.ImportFrom)}
    assert "lightgbm" not in nomes


@pytest.fixture(scope="module")
def dev_lgbm(tmp_path_factory):
    """Dataset sintético de desenvolvimento, preparado com as dobras (uma vez por módulo)."""
    pasta = tmp_path_factory.mktemp("lgbm")
    gravados = gravar_versoes(pasta, dataset_sintetico(), versoes=("todas",))
    params = params_teste()
    df_dev, _ = treino.ler_desenvolvimento(gravados["todas"], params)
    prep, cal = treino.preparar_dev(df_dev)
    dobras = validacao.dobras_walk_forward(cal, params.treino_minimo_meses, params.embargo_pregoes)
    return prep, dobras, params


def test_prever_lgbm_tem_as_mesmas_linhas_que_xgb(dev_lgbm):
    prep, dobras, params = dev_lgbm
    colunas = colunas_do_modelo("3", ("preco_contexto", "macro", "noticias_contexto"))
    xgb = treino.prever_walk_forward(prep, dobras, colunas, "xgb", params)
    lgbm = treino.prever_walk_forward(prep, dobras, colunas, "lgbm", params)
    assert len(lgbm) == len(xgb) > 0
    assert lgbm[["data", "ticker", "dobra"]].reset_index(drop=True).equals(
        xgb[["data", "ticker", "dobra"]].reset_index(drop=True))
    assert lgbm["score"].between(0, 1).all()


def test_requirements_fixa_lightgbm():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    linhas = (raiz / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "lightgbm==4.7.0" in linhas
