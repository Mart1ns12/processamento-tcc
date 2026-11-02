"""Testes de preparacao.py (etapa 5, fase 7): ranks por pregão, colunas do modelo e filtros.

Tabelas montadas à mão, tickers fictícios. Nenhum teste usa banco ou rede.
"""

import itertools

import numpy as np
import pandas as pd
import pytest

from processamento.experimento.preparacao import (
    BLOCOS_COMPLEMENTARES,
    BLOCOS_PROTOCOLO,
    COLUNAS_ALVO,
    COLUNAS_BRUTAS,
    COLUNAS_PROTOCOLO,
    COMPLEMENTARES_PRECO,
    EXTREMO_RANK,
    COLUNAS_RANK,
    COMPLEMENTARES_NOTICIAS,
    ESSENCIAIS_PRECO,
    IDENTIFICACAO,
    NOTICIAS_DIA,
    VERSAO_PREPARACAO,
    colunas_do_modelo,
    linhas_de_treino,
    linhas_modelo_3b,
    preparar,
    rank_no_pregao,
)

NAN = np.nan


def _longo(dias):
    """Formato longo (data, ticker, x) a partir de {data: {ticker: valor}}."""
    return pd.DataFrame(
        [{"data": pd.Timestamp(d), "ticker": t, "x": v} for d, por_ticker in dias.items() for t, v in por_ticker.items()]
    )


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


def _confere(obtido: pd.Series, esperado: dict) -> None:
    """Confere valores por chave: None = NaN; demais com tolerância 1e-12."""
    for chave, valor in esperado.items():
        if valor is None:
            assert pd.isna(obtido[chave]), chave
        else:
            assert obtido[chave] == pytest.approx(valor, abs=1e-12), chave


def test_rank_gabarito_por_dia():
    dias = {
        "2026-06-18": {"AAAA3": 0.03, "BBBB3": 0.01, "CCCC3": NAN, "DDDD3": 0.01, "EEEE3": 0.05},
        "2026-06-19": {"AAAA3": -0.02, "BBBB3": 0.04, "CCCC3": 0.0, "DDDD3": NAN, "EEEE3": NAN},
        "2026-06-22": {"AAAA3": 0.07, "BBBB3": NAN, "CCCC3": NAN, "DDDD3": NAN, "EEEE3": NAN},
        "2026-06-23": {"AAAA3": 0.02, "BBBB3": 0.02, "CCCC3": 0.02, "DDDD3": NAN, "EEEE3": NAN},
    }
    df = _longo(dias)
    res = rank_no_pregao(df, ["x"]).set_index(["data", "ticker"])["x"]
    d1, d2, d3, d4 = (pd.Timestamp(d) for d in dias)
    _confere(res, {
        (d1, "AAAA3"): 2 / 3, (d1, "BBBB3"): 1 / 6, (d1, "CCCC3"): None,
        (d1, "DDDD3"): 1 / 6, (d1, "EEEE3"): 1.0,
        (d2, "AAAA3"): 0.0, (d2, "BBBB3"): 1.0, (d2, "CCCC3"): 0.5,
        (d2, "DDDD3"): None, (d2, "EEEE3"): None,
        (d3, "AAAA3"): 0.5,
        (d4, "AAAA3"): 0.5, (d4, "BBBB3"): 0.5, (d4, "CCCC3"): 0.5,
    })


def test_rank_nao_e_o_pct_do_pandas():
    """Com n = 4 e empate no menor valor, o rank médio dá 1/6 (pandas pct=True daria outro valor)."""
    df = _longo({"2026-06-18": {"A": 0.01, "B": 0.01, "C": 0.02, "D": 0.03}})
    res = rank_no_pregao(df, ["x"])["x"]
    assert res.tolist() == pytest.approx([1 / 6, 1 / 6, 2 / 3, 1.0], abs=1e-12)


def test_preparar_faz_rank_antes_de_descartar_sem_alvo():
    df = _dataset([
        {"data": "2026-06-18", "ticker": "AAAA3", "alvo": 1.0, "ret_1d": 0.01},
        {"data": "2026-06-18", "ticker": "BBBB3", "alvo": NAN, "ret_1d": 0.03},
        {"data": "2026-06-18", "ticker": "CCCC3", "alvo": 0.0, "ret_1d": 0.02},
    ])
    prep = preparar(df)
    assert prep["ret_1d"].tolist() == pytest.approx([0.0, 1.0, 0.5], abs=1e-12)

    treino = linhas_de_treino(prep)
    assert treino["ticker"].tolist() == ["AAAA3", "CCCC3"]
    assert treino["ret_1d"].tolist() == pytest.approx([0.0, 0.5], abs=1e-12)
    assert treino["alvo"].tolist() == [1.0, 0.0]


def test_preparar_mantem_colunas_de_noticia_e_alvo():
    df = _dataset([
        {"data": "2026-06-18", "ticker": "AAAA3", "alvo": 1.0, "alvo_abertura": 0.0, "ret_t1": 0.125,
         "ret_ibov_t1": 0.0625, "noticias_dia_qtd": 2.0, "noticias_dia_tom": 0.3, "tom_mercado": 0.16,
         "ret_1d": 0.01},
        {"data": "2026-06-18", "ticker": "BBBB3", "alvo": NAN, "alvo_abertura": NAN, "ret_t1": NAN,
         "ret_ibov_t1": NAN, "noticias_dia_qtd": 0.0, "noticias_dia_tom": NAN, "tom_mercado": 0.16,
         "ret_1d": 0.03},
    ])
    prep = preparar(df)
    colunas = COLUNAS_BRUTAS + COLUNAS_ALVO + IDENTIFICACAO
    pd.testing.assert_frame_equal(prep[colunas], df[colunas])
    assert list(prep.columns) == [*df.columns, EXTREMO_RANK]


def test_preparar_falta_coluna_levanta_erro():
    df = _dataset([{"data": "2026-06-18", "ticker": "AAAA3", "ret_1d": 0.01}]).drop(columns=["alvo"])
    with pytest.raises(ValueError, match="alvo"):
        preparar(df)


def test_colunas_do_modelo_por_modelo():
    assert colunas_do_modelo("1") == ESSENCIAIS_PRECO
    assert colunas_do_modelo("3") == ESSENCIAIS_PRECO + NOTICIAS_DIA
    with pytest.raises(ValueError, match="modelo desconhecido"):
        colunas_do_modelo("3b")   # "3b" é só uma avaliação das previsões do modelo 3 (F12)


def test_colunas_do_modelo_blocos_na_ordem_dada():
    cols = colunas_do_modelo("3", ("macro", "preco_contexto"))
    esperado = (
        ESSENCIAIS_PRECO + NOTICIAS_DIA
        + BLOCOS_COMPLEMENTARES["macro"] + BLOCOS_COMPLEMENTARES["preco_contexto"]
    )
    assert cols == esperado
    assert colunas_do_modelo("3", ("noticias_contexto",))[-2:] == COMPLEMENTARES_NOTICIAS


def test_colunas_do_modelo_erros():
    with pytest.raises(ValueError):
        colunas_do_modelo("1", ("noticias_contexto",))
    with pytest.raises(ValueError, match="modelo 2 removido"):
        colunas_do_modelo("2")
    with pytest.raises(ValueError, match="modelo 2 removido"):
        colunas_do_modelo("2", ("noticias_contexto",))
    with pytest.raises(ValueError):
        colunas_do_modelo("9")
    with pytest.raises(ValueError):
        colunas_do_modelo("3", ("bloco_inexistente",))
    with pytest.raises(ValueError):
        colunas_do_modelo("3", ("macro", "macro"))


def test_linhas_modelo_3b_so_dias_de_resultado():
    df = _dataset([
        {"data": "2026-06-18", "ticker": "AAAA3", "alvo": 1.0, "dia_resultado": True},
        {"data": "2026-06-18", "ticker": "BBBB3", "alvo": 0.0, "dia_resultado": False},
        {"data": "2026-06-19", "ticker": "AAAA3", "alvo": 0.0, "dia_resultado": False},
    ])
    res = linhas_modelo_3b(preparar(df))
    assert res["ticker"].tolist() == ["AAAA3"]
    assert res["data"].tolist() == [pd.Timestamp("2026-06-18")]


def test_noticias_dia_qtd_entra_em_rank_no_pregao_e_as_outras_de_noticia_ficam_brutas():
    df = _dataset([
        {"data": "2026-06-18", "ticker": "AAAA3", "noticias_dia_qtd": 2.0, "noticias_dia_tom": 0.3, "noticias_dia_extremo": 0.9},
        {"data": "2026-06-18", "ticker": "BBBB3", "noticias_dia_qtd": 0.0, "noticias_dia_tom": NAN},
        {"data": "2026-06-18", "ticker": "CCCC3", "noticias_dia_qtd": 0.0, "noticias_dia_tom": NAN},
        {"data": "2026-06-18", "ticker": "DDDD3", "noticias_dia_qtd": NAN, "noticias_dia_tom": NAN},
        {"data": "2026-06-19", "ticker": "AAAA3", "noticias_dia_qtd": 0.0},
        {"data": "2026-06-19", "ticker": "BBBB3", "noticias_dia_qtd": 0.0},
    ])
    prep = preparar(df)
    # 18/06: válidos 2, 0, 0 -> posições médias 3; 1,5; 1,5 -> 1; 0,25; 0,25. Vazio continua vazio (período sem coleta).
    assert prep["noticias_dia_qtd"].iloc[:3].tolist() == [1.0, 0.25, 0.25]
    assert pd.isna(prep["noticias_dia_qtd"].iloc[3])
    # 19/06: todas zeradas -> empate no meio
    assert prep["noticias_dia_qtd"].iloc[4:].tolist() == [0.5, 0.5]
    assert prep["noticias_dia_tom"].iloc[0] == 0.3
    assert prep["noticias_dia_extremo"].iloc[0] == 0.9   # a variante em rank fica em outra coluna


def test_extremo_rank_e_uma_coluna_a_parte():
    df = _dataset([
        {"data": "2026-06-18", "ticker": "AAAA3", "noticias_dia_extremo": -0.9},
        {"data": "2026-06-18", "ticker": "BBBB3", "noticias_dia_extremo": 0.1},
        {"data": "2026-06-18", "ticker": "CCCC3", "noticias_dia_extremo": NAN},
    ])
    prep = preparar(df)
    assert prep[EXTREMO_RANK].iloc[:2].tolist() == [0.0, 1.0]
    assert pd.isna(prep[EXTREMO_RANK].iloc[2])


# ---------------------------------------------------------------- blocos A e B do protocolo (fora por padrão)


def test_blocos_do_protocolo():
    assert BLOCOS_PROTOCOLO == {
        "bloco_a": ["posicao_fechamento", "mom_12_1", "liquidez_20d", "ret_idio_5d"],
        "bloco_b": ["momento_setor_5d", "exposicao_small"],
        "bloco_c": ["dias_desde_resultado", "var_lucro_aa"],
        "bloco_d": ["dy_12m"],
        "bloco_e": ["fato_relevante_cvm"],
        "controle": ["controle_sorteado"],
    }


def _combinacoes_validas(modelo):
    blocos = list(BLOCOS_COMPLEMENTARES)
    for k in range(len(blocos) + 1):
        for comb in itertools.combinations(blocos, k):
            if modelo == "1" and "noticias_contexto" in comb:
                continue
            yield comb


@pytest.mark.parametrize("modelo", ["1", "3"])
def test_protocolo_nao_entra_em_nenhuma_combinacao_de_blocos(modelo):
    for comb in _combinacoes_validas(modelo):
        cols = colunas_do_modelo(modelo, comb)
        assert not set(cols) & set(COLUNAS_PROTOCOLO), (modelo, comb)


@pytest.mark.parametrize("bloco", list(BLOCOS_PROTOCOLO))
def test_blocos_do_protocolo_nao_sao_blocos_do_modelo(bloco):
    with pytest.raises(ValueError, match="bloco desconhecido"):
        colunas_do_modelo("3", (bloco,))


def test_protocolo_fora_dos_grupos_so_no_rank():
    assert not set(COLUNAS_PROTOCOLO) & set(ESSENCIAIS_PRECO + COMPLEMENTARES_PRECO + NOTICIAS_DIA)
    assert set(COLUNAS_PROTOCOLO) <= set(COLUNAS_RANK)
    assert not set(COLUNAS_PROTOCOLO) & set(COLUNAS_BRUTAS)
    assert VERSAO_PREPARACAO == 4


_BASE_PROTOCOLO = [("AAAA3", 0.10, 1.0), ("BBBB3", 0.10, NAN), ("CCCC3", NAN, 0.0),
                   ("DDDD3", 0.30, 0.0), ("EEEE3", 0.50, 0.0)]


@pytest.mark.parametrize("coluna", COLUNAS_PROTOCOLO)
def test_protocolo_rank_no_pregao_antes_de_tirar_sem_alvo(coluna):
    linhas = [{"data": "2026-06-18", "ticker": t, coluna: v, "alvo": a} for t, v, a in _BASE_PROTOCOLO]
    linhas.append({"data": "2026-06-19", "ticker": "AAAA3", coluna: 999.0, "alvo": 1.0})
    df = _dataset(linhas)
    entrada = df[coluna].copy()

    prep = preparar(df)
    d18 = prep[prep["data"] == pd.Timestamp("2026-06-18")].set_index("ticker")[coluna]
    _confere(d18, {"AAAA3": 1 / 6, "BBBB3": 1 / 6, "CCCC3": None, "DDDD3": 2 / 3, "EEEE3": 1.0})
    d19 = prep[prep["data"] == pd.Timestamp("2026-06-19")][coluna]
    assert d19.tolist() == pytest.approx([0.5], abs=1e-12)

    # 999 vira −999 e a ordem dos outros não muda: o pregão de 18/06 fica igual
    df_neg = df.copy()
    df_neg.loc[df_neg["data"] == pd.Timestamp("2026-06-19"), coluna] = -999.0
    d18_neg = preparar(df_neg)
    d18_neg = d18_neg[d18_neg["data"] == pd.Timestamp("2026-06-18")].set_index("ticker")[coluna]
    _confere(d18_neg, {"AAAA3": 1 / 6, "BBBB3": 1 / 6, "CCCC3": None, "DDDD3": 2 / 3, "EEEE3": 1.0})

    # linhas_de_treino tira a sem alvo depois do rank: AAAA3 mantém 1/6
    treino = linhas_de_treino(prep)
    assert "BBBB3" not in treino[treino["data"] == pd.Timestamp("2026-06-18")]["ticker"].tolist()
    aaaa3 = treino[(treino["data"] == pd.Timestamp("2026-06-18")) & (treino["ticker"] == "AAAA3")][coluna]
    assert aaaa3.tolist() == pytest.approx([1 / 6], abs=1e-12)

    # a entrada de preparar continua bruta
    pd.testing.assert_series_equal(df[coluna], entrada)


def test_colunas_cde_e_controle_fora_dos_modelos_e_no_rank():
    novas = ["dias_desde_resultado", "var_lucro_aa", "dy_12m", "fato_relevante_cvm", "controle_sorteado"]
    assert set(novas) <= set(COLUNAS_PROTOCOLO) and set(novas) <= set(COLUNAS_RANK)
    assert not set(novas) & set(COLUNAS_BRUTAS)
    for modelo in ("1", "3"):
        for comb in _combinacoes_validas(modelo):
            assert not set(colunas_do_modelo(modelo, comb)) & set(novas), (modelo, comb)


def test_fato_relevante_binario_vira_rank_com_empate_e_vazio():
    df = _dataset([
        {"data": "2026-06-18", "ticker": "AAAA3", "fato_relevante_cvm": 1.0},
        {"data": "2026-06-18", "ticker": "BBBB3", "fato_relevante_cvm": 0.0},
        {"data": "2026-06-18", "ticker": "CCCC3", "fato_relevante_cvm": 0.0},
        {"data": "2026-06-18", "ticker": "DDDD3", "fato_relevante_cvm": NAN},
        {"data": "2026-06-19", "ticker": "AAAA3", "fato_relevante_cvm": 0.0},
        {"data": "2026-06-19", "ticker": "BBBB3", "fato_relevante_cvm": 0.0},
    ])
    prep = preparar(df)["fato_relevante_cvm"].tolist()
    assert prep[:3] == [1.0, 0.25, 0.25] and pd.isna(prep[3])
    assert prep[4:] == [0.5, 0.5]
