"""Testes de previsao.py (etapa 6, fase 5): efeito, motivos, chance, top do dia e sombras.

Gabaritos do plano (docs/plano_etapa6.md, fase 5): casos 3, 6, 8 (parte 2) e 9, além do desempate e das sombras.
Dados sintéticos pequenos; nenhum teste usa banco ou rede.
"""

import json

import numpy as np
import pandas as pd
import pytest

from processamento.experimento import modelos, previsao
from processamento.experimento.parametros import carregar_parametros_treino
from processamento.experimento.preparacao import (
    COLUNAS_ALVO,
    COLUNAS_BRUTAS,
    COLUNAS_RANK,
    IDENTIFICACAO,
    preparar,
)

NAN = np.nan
HIPER = {"n_estimators": 50}

# Caso 3: dia 1 (ticker, score, alvo, ret_t1), com empate de score em 0,50 (EEEE3 e FFFF3).
DIA_1 = [
    ("AAAA3", 0.70, 1, 0.020),
    ("BBBB3", 0.60, 0, -0.010),
    ("CCCC3", 0.60, 1, 0.015),
    ("DDDD3", 0.55, 1, 0.008),
    ("EEEE3", 0.50, 0, -0.004),
    ("FFFF3", 0.50, 1, 0.012),
    ("GGGG3", 0.40, 0, -0.020),
]


def _dados_sinteticos():
    """X 2000×4 (beta todo NaN, tom NaN a cada 7 linhas) e y binário ligado a ret_1d (como em test_treino_modelos)."""
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


def _dia_sintetico(n=30):
    """Um pregão com `n` tickers, tirados dos dados sintéticos (X já é o preparado: ranks não importam aqui)."""
    X, _ = _dados_sinteticos()
    dia = X.head(n).reset_index(drop=True).copy()
    dia.insert(0, "ticker", [f"T{i:02d}" for i in range(n)])
    return dia


def _treino_sintetico(colunas):
    X, y = _dados_sinteticos()
    return modelos.treinar_xgb(X[colunas], y, HIPER, semente=7)


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
    """Caso 6 do plano: seis ações num único pregão, com volatilidade_20d e alvo conhecidos (já preparado)."""
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


# ---------- efeito ----------


def test_efeito_borda_e_sinais():
    assert previsao.efeito(0.01, 0.01) == "neutro"
    assert previsao.efeito(-0.0100001, 0.01) == "atrapalhou"
    assert previsao.efeito(0.0100001, 0.01) == "ajudou"
    assert previsao.efeito(-0.01, 0.01) == "neutro"


# ---------- Caso 8, parte 2: motivos ----------


def _contrib_caso_8():
    return pd.Series(
        {
            "ret_1d": 0.30,
            "ret_5d": -0.45,
            "volatilidade_20d": 0.005,
            "noticias_dia_tom": 0.30,
            "beta": -0.02,
            "vies": -0.1,
        }
    )


def _valores_caso_8():
    return pd.Series(
        {
            "ret_5d": -0.031,
            "noticias_dia_tom": 0.42,
            "ret_1d": 0.012,
            "beta": NAN,
            "volatilidade_20d": 0.018,
        }
    )


def test_caso8_motivos_qtd_3():
    itens = previsao.motivos(_contrib_caso_8(), _valores_caso_8(), 3, 0.01)
    assert [m["fator"] for m in itens] == ["ret_5d", "noticias_dia_tom", "ret_1d"]
    assert [m["efeito"] for m in itens] == ["atrapalhou", "ajudou", "ajudou"]
    assert itens[0]["contribuicao"] == pytest.approx(-0.45)
    assert itens[0]["valor"] == pytest.approx(-0.031)
    assert itens[1]["valor"] == pytest.approx(0.42)
    assert itens[2]["valor"] == pytest.approx(0.012)


def test_caso8_motivos_qtd_5_ausencia_vira_none_e_sem_vies():
    itens = previsao.motivos(_contrib_caso_8(), _valores_caso_8(), 5, 0.01)
    assert [m["fator"] for m in itens] == [
        "ret_5d",
        "noticias_dia_tom",
        "ret_1d",
        "beta",
        "volatilidade_20d",
    ]
    beta, vol = itens[3], itens[4]
    assert beta["valor"] is None
    assert beta["efeito"] == "atrapalhou"
    assert vol["valor"] == pytest.approx(0.018)
    assert vol["efeito"] == "neutro"
    assert all(m["fator"] != "vies" for m in itens)


def test_motivos_chaves_do_item():
    item = previsao.motivos(_contrib_caso_8(), _valores_caso_8(), 1, 0.01)[0]
    assert set(item) == {"fator", "contribuicao", "valor", "efeito"}


# ---------- Caso 9: a chance fica escondida ----------


def test_caso9_chance_escondida_sem_uma_das_condicoes():
    for liberar, aprovada in [(False, True), (True, False)]:
        ch = previsao.chance(0.61, liberar, aprovada)
        assert ch == {"valor": None, "media": 0.5, "exibir": False, "status": "calibracao_nao_conferida"}


def test_caso9_chance_exibida_com_as_duas_condicoes():
    ch = previsao.chance(0.61, True, True)
    assert ch == {"valor": 0.61, "media": 0.5, "exibir": True, "status": "ok"}


def test_caso9_top_do_dia_com_parametros_reais_nao_exporta_prob():
    params = carregar_parametros_treino()
    assert params.liberar_chance is False
    dia = _dia_sintetico()
    colunas = ["ret_1d", "ret_5d", "noticias_dia_tom", "beta"]
    modelo = _treino_sintetico(colunas)
    metadados = {"colunas": colunas, "calibracao": {"aprovada": True}}
    itens = previsao.top_do_dia(dia, dia.copy(), modelo, metadados, params)
    assert len(itens) == params.topk[0]
    assert all(item["chance"]["valor"] is None for item in itens)
    assert all(item["chance"]["exibir"] is False for item in itens)
    assert "prob" not in json.dumps(itens)


# ---------- top do dia: formato, ordem e valores brutos ----------


def test_top_do_dia_formato_ordem_e_valor_bruto():
    params = carregar_parametros_treino()
    dia = _dia_sintetico()
    colunas = ["ret_1d", "ret_5d", "noticias_dia_tom", "beta"]
    modelo = _treino_sintetico(colunas)
    metadados = {"colunas": colunas, "calibracao": {"aprovada": False}}
    bruto = dia.copy()
    bruto["ret_1d"] = bruto["ret_1d"] + 100.0  # o valor bruto precisa vir do bruto, não do preparado

    itens = previsao.top_do_dia(dia, bruto, modelo, metadados, params)

    assert [i["posicao"] for i in itens] == list(range(1, params.topk[0] + 1))
    assert all(set(i) == {"posicao", "ticker", "chance", "motivos"} for i in itens)
    assert len({i["ticker"] for i in itens}) == params.topk[0]
    prob = modelos.prob_xgb(modelo, dia[colunas])
    tickers_ordenados = list(dia["ticker"].iloc[np.argsort(-prob, kind="stable")])
    assert [i["ticker"] for i in itens] == tickers_ordenados[: params.topk[0]]
    for item in itens:
        assert len(item["motivos"]) == params.motivos_qtd
        linha = dia.loc[dia["ticker"] == item["ticker"]].iloc[0]
        for m in item["motivos"]:
            if m["fator"] == "ret_1d":
                assert m["valor"] == pytest.approx(linha["ret_1d"] + 100.0)


def test_top_do_dia_exige_mesmo_indice():
    params = carregar_parametros_treino()
    dia = _dia_sintetico()
    colunas = ["ret_1d", "ret_5d", "noticias_dia_tom", "beta"]
    modelo = _treino_sintetico(colunas)
    metadados = {"colunas": colunas, "calibracao": {"aprovada": False}}
    bruto = dia.copy()
    bruto.index = bruto.index + 1  # mesmas linhas, índice deslocado: tem de falhar
    with pytest.raises(ValueError):
        previsao.top_do_dia(dia, bruto, modelo, metadados, params)


# ---------- desempate e sombras ----------


def test_ordenar_top_caso3_dia1_com_desempate_por_ticker():
    dia = pd.DataFrame({"ticker": [t[0] for t in DIA_1]})
    scores = np.array([t[1] for t in DIA_1])
    assert previsao.ordenar_top(dia, scores, 5) == ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3"]


def test_ordenar_top_nao_depende_da_ordem_das_linhas():
    dia = pd.DataFrame({"ticker": [t[0] for t in DIA_1]})
    scores = np.array([t[1] for t in DIA_1])
    perm = np.random.default_rng(3).permutation(len(DIA_1))
    dia_emb = dia.iloc[perm].reset_index(drop=True)
    assert previsao.ordenar_top(dia_emb, scores[perm], 5) == ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3"]


def test_ordenar_top_score_ausente_levanta_erro():
    dia = pd.DataFrame({"ticker": ["AAAA3", "BBBB3"]})
    with pytest.raises(ValueError):
        previsao.ordenar_top(dia, np.array([0.5, np.nan]), 1)


def test_top_sombra_volatilidade_caso6():
    preparado = _caso_volatilidade()
    assert previsao.top_sombra_volatilidade(preparado, 5) == ["AAAA3", "CCCC3", "EEEE3", "DDDD3", "BBBB3"]


def test_top_sombra_modelo_k_distintos_na_ordem_da_prob():
    dia = _dia_sintetico()
    colunas = ["ret_1d", "ret_5d", "noticias_dia_tom"]
    modelo = _treino_sintetico(colunas)
    k = 5
    tickers = previsao.top_sombra_modelo(dia, modelo, colunas, k)
    assert len(tickers) == k
    assert len(set(tickers)) == k
    prob = modelos.prob_xgb(modelo, dia[colunas])
    esperado = [t for _, t in sorted(zip(-prob, dia["ticker"]))][:k]
    assert tickers == esperado


def test_motivos_com_extremo_em_rank_falam_da_coluna_do_dataset():
    import dataclasses

    from fabrica_treino import dataset_sintetico, params_teste
    from processamento.experimento import modelos, preparacao, previsao

    bruto = dataset_sintetico(n_pregoes=130, n_tickers=12)
    prep = preparacao.preparar(bruto)
    treino = preparacao.linhas_de_treino(prep)
    colunas = [
        preparacao.EXTREMO_RANK if c == "noticias_dia_extremo" else c for c in preparacao.colunas_do_modelo("3")
    ]
    params = dataclasses.replace(params_teste(), motivos_qtd=len(colunas))
    modelo = modelos.treinar_xgb(treino[colunas], treino["alvo"], params.xgboost, params.semente)
    dia = prep["data"].max()
    mascara = prep["data"] == dia
    itens = previsao.top_do_dia(prep[mascara], bruto[mascara], modelo, {"colunas": colunas, "calibracao": {"aprovada": False}}, params)
    fatores = {m["fator"] for m in itens[0]["motivos"]}
    assert "noticias_dia_extremo" in fatores and preparacao.EXTREMO_RANK not in fatores
