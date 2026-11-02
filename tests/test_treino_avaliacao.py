"""Testes das métricas do experimento (processamento/experimento/avaliacao.py). Gabaritos do plano da etapa 6, fase 3."""

import numpy as np
import pandas as pd
import pytest

from processamento.experimento.avaliacao import (
    auc_geral,
    auc_por_pregao,
    calibracao,
    comparar_com_acaso,
    diferenca_pareada,
    faixa_do_acaso,
    ic_bootstrap_blocos,
    linhas_abertura_valida,
    metricas_periodo,
    ordenar_no_dia,
    por_ano,
    resumo_diario,
    sensibilidade_ultimo_ano,
)

D1 = pd.Timestamp("2026-03-02")
D2 = pd.Timestamp("2026-03-03")

# (ticker, score, alvo, ret_t1) por dia; ret_ibov_t1 vem do dia.
DIA_1 = [
    ("AAAA3", 0.70, 1, 0.020),
    ("BBBB3", 0.60, 0, -0.010),
    ("CCCC3", 0.60, 1, 0.015),
    ("DDDD3", 0.55, 1, 0.008),
    ("EEEE3", 0.50, 0, -0.004),
    ("FFFF3", 0.50, 1, 0.012),
    ("GGGG3", 0.40, 0, -0.020),
]
DIA_2 = [
    ("AAAA3", 0.30, 1, 0.010),
    ("BBBB3", 0.90, 0, -0.005),
    ("CCCC3", 0.80, 1, 0.001),
    ("DDDD3", 0.20, 0, -0.010),
    ("EEEE3", 0.85, np.nan, np.nan),
    ("FFFF3", 0.10, 1, 0.004),
    ("GGGG3", 0.50, 0, -0.003),
]


def _linhas(data, dia, ibov):
    return pd.DataFrame(
        {
            "data": data,
            "ticker": [t[0] for t in dia],
            "score": [t[1] for t in dia],
            "alvo": [t[2] for t in dia],
            "ret_t1": [t[3] for t in dia],
            "ret_ibov_t1": ibov,
        }
    )


def _df_caso_3_e_4():
    """Dois dias, linhas embaralhadas (a ordem da entrada não pode mudar o resultado)."""
    df = pd.concat([_linhas(D1, DIA_1, 0.005), _linhas(D2, DIA_2, -0.002)], ignore_index=True)
    ordem = [9, 0, 12, 3, 7, 13, 1, 10, 5, 2, 11, 4, 8, 6]
    return df.iloc[ordem].reset_index(drop=True)


def _ticks(ordenado):
    return list(ordenado["ticker"])


# ---------- Caso 3: ranking, desempate e linhas sem alvo ----------

def test_caso3_ordem_do_dia_1_com_desempate_por_ticker():
    df = _df_caso_3_e_4()
    dia1 = df.loc[df["data"] == D1]
    ordenado = ordenar_no_dia(dia1)
    assert _ticks(ordenado) == ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3", "GGGG3"]
    assert list(ordenado["posicao"]) == [1, 2, 3, 4, 5, 6, 7]


def test_caso3_top5_top3_e_ultimos_do_dia_1():
    df = _df_caso_3_e_4()
    ordenado = ordenar_no_dia(df.loc[df["data"] == D1])
    assert _ticks(ordenado[ordenado["posicao"] <= 5]) == ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3"]
    assert _ticks(ordenado[ordenado["posicao"] <= 3]) == ["AAAA3", "BBBB3", "CCCC3"]
    assert _ticks(ordenado[ordenado["posicao"] > 2]) == ["CCCC3", "DDDD3", "EEEE3", "FFFF3", "GGGG3"]
    assert _ticks(ordenado[ordenado["posicao"] > 4]) == ["EEEE3", "FFFF3", "GGGG3"]


def test_caso3_dia_2_sem_linha_de_alvo_nan():
    df = _df_caso_3_e_4()
    candidatos = df.loc[(df["data"] == D2) & df["alvo"].notna()]
    ordenado = ordenar_no_dia(candidatos)
    assert len(ordenado) == 6
    assert _ticks(ordenado[ordenado["posicao"] <= 5]) == ["BBBB3", "CCCC3", "GGGG3", "AAAA3", "DDDD3"]
    assert _ticks(ordenado[ordenado["posicao"] <= 3]) == ["BBBB3", "CCCC3", "GGGG3"]
    assert _ticks(ordenado[ordenado["posicao"] > 3]) == ["AAAA3", "DDDD3", "FFFF3"]
    assert _ticks(ordenado[ordenado["posicao"] > 1]) == ["CCCC3", "GGGG3", "AAAA3", "DDDD3", "FFFF3"]


def test_caso3_n_candidatos_por_dia():
    df = _df_caso_3_e_4()
    diario = resumo_diario(df, 3).set_index("data")
    assert diario.loc[D1, "n_candidatos"] == 7
    assert diario.loc[D2, "n_candidatos"] == 6


def test_score_ausente_levanta_erro():
    df = _linhas(D1, DIA_1, 0.005)
    df.loc[0, "score"] = np.nan
    with pytest.raises(ValueError):
        ordenar_no_dia(df)


def test_dia_com_menos_de_k_candidatas_fica_fora():
    df = _df_caso_3_e_4()
    diario = resumo_diario(df, 7)  # D2 tem 6 candidatas
    assert list(diario["data"]) == [D1]


# ---------- Caso 4: números exatos ----------

def _diario_caso_4(k):
    return resumo_diario(_df_caso_3_e_4(), k).set_index("data")


def test_caso4_top5():
    d = _diario_caso_4(5)
    assert d.loc[D1, "acertos_top"] == 3
    assert d.loc[D1, "acerto_top"] == pytest.approx(0.6, abs=1e-12)
    assert d.loc[D1, "excesso_top"] == pytest.approx(0.0008, abs=1e-12)
    assert d.loc[D2, "acertos_top"] == 2
    assert d.loc[D2, "acerto_top"] == pytest.approx(0.4, abs=1e-12)
    assert d.loc[D2, "excesso_top"] == pytest.approx(0.0006, abs=1e-12)
    m = metricas_periodo(d.reset_index())
    assert m["taxa_acerto"] == pytest.approx(0.5, abs=1e-12)
    assert m["excesso_medio"] == pytest.approx(0.0007, abs=1e-12)


def test_caso4_top3():
    d = _diario_caso_4(3)
    assert d.loc[D1, "acertos_top"] == 2
    assert d.loc[D1, "acerto_top"] == pytest.approx(2 / 3, abs=1e-12)
    assert d.loc[D1, "excesso_top"] == pytest.approx(0.01 / 3, abs=1e-12)
    assert d.loc[D2, "acertos_top"] == 1
    assert d.loc[D2, "acerto_top"] == pytest.approx(1 / 3, abs=1e-12)
    assert d.loc[D2, "excesso_top"] == pytest.approx(-0.001 / 3, abs=1e-12)
    m = metricas_periodo(d.reset_index())
    assert m["taxa_acerto"] == pytest.approx(0.5, abs=1e-12)
    assert m["excesso_medio"] == pytest.approx(0.0015, abs=1e-12)


def test_caso4_ultimos_5():
    d = _diario_caso_4(5)
    assert d.loc[D1, "acerto_ultimos"] == pytest.approx(0.6, abs=1e-12)
    assert d.loc[D1, "excesso_ultimos"] == pytest.approx(-0.0028, abs=1e-12)
    assert d.loc[D2, "acerto_ultimos"] == pytest.approx(0.6, abs=1e-12)
    assert d.loc[D2, "excesso_ultimos"] == pytest.approx(0.0024, abs=1e-12)
    m = metricas_periodo(d.reset_index())
    assert m["taxa_ultimos"] == pytest.approx(0.6, abs=1e-12)
    assert m["excesso_ultimos"] == pytest.approx(-0.0002, abs=1e-12)


def test_caso4_ultimos_3():
    d = _diario_caso_4(3)
    assert d.loc[D1, "acerto_ultimos"] == pytest.approx(1 / 3, abs=1e-12)
    assert d.loc[D1, "excesso_ultimos"] == pytest.approx(-0.009, abs=1e-12)
    assert d.loc[D2, "acerto_ultimos"] == pytest.approx(2 / 3, abs=1e-12)
    assert d.loc[D2, "excesso_ultimos"] == pytest.approx(0.01 / 3, abs=1e-12)
    m = metricas_periodo(d.reset_index())
    assert m["taxa_ultimos"] == pytest.approx(0.5, abs=1e-12)
    assert m["excesso_ultimos"] == pytest.approx(-0.017 / 6, abs=1e-12)
    assert m["dif_top_ultimos"] == pytest.approx(0.0, abs=1e-12)


def test_metricas_periodo_sem_retorno_nao_traz_excesso():
    d = resumo_diario(_df_caso_3_e_4(), 3, com_retorno=False)
    m = metricas_periodo(d, com_retorno=False)
    assert "excesso_medio" not in m
    assert m["n_dias"] == 2


def test_auc_geral_das_13_candidatas():
    df = _df_caso_3_e_4()
    assert auc_geral(df) == pytest.approx(15 / 28, abs=1e-12)


def test_auc_por_dia_e_media():
    df = _df_caso_3_e_4()
    por_dia = auc_por_pregao(df)
    assert por_dia.loc[D1] == pytest.approx(0.75, abs=1e-12)
    assert por_dia.loc[D2] == pytest.approx(1 / 3, abs=1e-12)
    assert por_dia.mean() == pytest.approx(13 / 24, abs=1e-12)


def test_auc_com_uma_classe_so_devolve_none():
    df = _linhas(D1, DIA_1, 0.005)
    df["alvo"] = 1.0
    assert auc_geral(df) is None
    assert len(auc_por_pregao(df)) == 0


def test_diferenca_pareada_junta_so_datas_comuns():
    a = pd.Series([0.5, 0.6, 0.7], index=pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]))
    b = pd.Series([0.1, 0.2], index=pd.to_datetime(["2026-01-05", "2026-01-06"]))
    dif = diferenca_pareada(a, b)
    assert list(dif.index) == list(pd.to_datetime(["2026-01-05", "2026-01-06"]))
    assert dif.iloc[0] == pytest.approx(0.5, abs=1e-12)  # 0.6 - 0.1
    assert dif.iloc[1] == pytest.approx(0.5, abs=1e-12)


# ---------- Caso 5: faixa do acaso ----------

def _df_acaso(dias, com_retorno=False, ret=0.0, ibov=0.0):
    """dias = lista de (data, [(ticker, alvo), ...]). Score fica zerado (o acaso não o usa)."""
    linhas = []
    for data, itens in dias:
        for ticker, alvo in itens:
            linhas.append(
                {"data": pd.Timestamp(data), "ticker": ticker, "score": 0.0, "alvo": float(alvo),
                 "ret_t1": ret, "ret_ibov_t1": ibov}
            )
    return pd.DataFrame(linhas)


def test_caso5a_universo_igual_a_k_sem_aleatoriedade():
    df = _df_acaso([
        ("2026-03-02", [("AAAA3", 1), ("BBBB3", 0), ("CCCC3", 1)]),
        ("2026-03-03", [("AAAA3", 0), ("BBBB3", 0), ("CCCC3", 1)]),
    ])
    for semente in (1, 42):
        f = faixa_do_acaso(df, 3, 10000, semente, com_retorno=False)
        assert f["media"] == pytest.approx(0.5, abs=1e-12)
        assert f["p2_5"] == pytest.approx(0.5, abs=1e-12)
        assert f["p97_5"] == pytest.approx(0.5, abs=1e-12)
        assert f["n_sorteios"] == 10000
        assert f["n_dias"] == 2


def test_caso5b_todos_acertam():
    tickers = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3"]
    df = _df_acaso([(d, [(t, 1) for t in tickers]) for d in ("2026-03-02", "2026-03-03", "2026-03-04")])
    f = faixa_do_acaso(df, 5, 10000, 7, com_retorno=False)
    assert f["p2_5"] == pytest.approx(1.0, abs=1e-12)
    assert f["p97_5"] == pytest.approx(1.0, abs=1e-12)
    assert f["media"] == pytest.approx(1.0, abs=1e-12)


def _df_caso_5c():
    tickers = [f"{letra}{letra}{letra}{letra}3" for letra in "ABCDEFGHIJ"]
    alvos = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    item = list(zip(tickers, alvos))
    return _df_acaso([(d, item) for d in ("2026-03-02", "2026-03-03", "2026-03-04")], com_retorno=True,
                     ret=0.01, ibov=0.0)


def test_caso5c_gabarito_com_semente():
    df = _df_caso_5c()
    f = faixa_do_acaso(df, 5, 10000, 123)
    assert f["media"] == pytest.approx(0.39912, abs=1e-12)
    assert f["p2_5"] == pytest.approx(0.2, abs=1e-12)
    assert f["p97_5"] == pytest.approx(0.6, abs=1e-12)
    assert f["excesso_media"] == pytest.approx(0.01, abs=1e-12)
    assert f["excesso_p2_5"] == pytest.approx(0.01, abs=1e-12)
    assert f["excesso_p97_5"] == pytest.approx(0.01, abs=1e-12)


def test_caso5c_mesma_semente_mesma_distribuicao():
    df = _df_caso_5c()
    a = faixa_do_acaso(df, 5, 10000, 123)
    b = faixa_do_acaso(df, 5, 10000, 123)
    assert np.array_equal(a["distribuicao_acerto"], b["distribuicao_acerto"])


def test_caso5d_excesso_degenerado():
    df = _df_acaso([
        ("2026-03-02", [("AAAA3", 1), ("BBBB3", 0), ("CCCC3", 1)]),
        ("2026-03-03", [("AAAA3", 0), ("BBBB3", 0), ("CCCC3", 1)]),
    ], com_retorno=True, ret=0.02, ibov=0.005)
    f = faixa_do_acaso(df, 3, 10000, 1)
    assert f["excesso_p2_5"] == pytest.approx(0.015, abs=1e-12)
    assert f["excesso_p97_5"] == pytest.approx(0.015, abs=1e-12)


def test_comparar_com_acaso():
    faixa = {"p2_5": 0.2, "p97_5": 0.6}
    assert comparar_com_acaso(0.7, faixa) == "acima"
    assert comparar_com_acaso(0.1, faixa) == "abaixo"
    assert comparar_com_acaso(0.4, faixa) == "dentro"


# ---------- Caso 7: alvo_abertura só nos dias válidos ----------

def _df_caso_7():
    linhas = []
    dados = [
        (D1, 1, [0.9, 0.8, 0.1, 0.2], [1, 0, 1, 0]),
        (D2, 0, [0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]),
        (D1 + pd.Timedelta(days=2), 1, [0.1, 0.2, 0.9, 0.8], [0, np.nan, 1, 1]),
    ]
    for data, valido, scores, aberturas in dados:
        for ticker, score, ab in zip("ABCD", scores, aberturas):
            linhas.append({"data": data, "ticker": ticker, "score": score,
                           "alvo_abertura": ab, "alvo_abertura_valido": float(valido)})
    return pd.DataFrame(linhas)


def test_caso7_so_dias_validos_e_sem_nan():
    lin = linhas_abertura_valida(_df_caso_7())
    assert set(lin["data"]) == {D1, D1 + pd.Timedelta(days=2)}
    assert lin["alvo_abertura"].notna().all()
    diario = resumo_diario(lin, 2, coluna_alvo="alvo_abertura", com_retorno=False)
    assert len(diario) == 2
    d = diario.set_index("data")
    assert d.loc[D1, "acerto_top"] == pytest.approx(0.5, abs=1e-12)
    assert d.loc[D1 + pd.Timedelta(days=2), "acerto_top"] == pytest.approx(1.0, abs=1e-12)
    m = metricas_periodo(diario, com_retorno=False)
    assert m["taxa_acerto"] == pytest.approx(0.75, abs=1e-12)
    assert m["n_dias"] == 2


def test_caso7_auc_so_nos_dias_validos():
    lin = linhas_abertura_valida(_df_caso_7())
    assert auc_geral(lin, coluna_alvo="alvo_abertura") == pytest.approx(0.75, abs=1e-12)
    por_dia = auc_por_pregao(lin, coluna_alvo="alvo_abertura")
    assert por_dia.loc[D1] == pytest.approx(0.5, abs=1e-12)
    assert por_dia.loc[D1 + pd.Timedelta(days=2)] == pytest.approx(1.0, abs=1e-12)


# ---------- Bootstrap circular ----------

def test_bootstrap_serie_constante():
    lo, hi = ic_bootstrap_blocos([0.4] * 10, 5, 200, 1)
    assert lo == pytest.approx(0.4, abs=1e-12)
    assert hi == pytest.approx(0.4, abs=1e-12)


def test_bootstrap_rotacao_inteira():
    lo, hi = ic_bootstrap_blocos([0.2, 0.4, 0.6, 0.8], 4, 200, 1)
    assert lo == pytest.approx(0.5, abs=1e-12)
    assert hi == pytest.approx(0.5, abs=1e-12)


def test_bootstrap_mesma_semente_mesmo_ic():
    valores = [0.1, 0.5, 0.3, 0.9, 0.7, 0.2, 0.6, 0.4]
    assert ic_bootstrap_blocos(valores, 3, 500, 9) == ic_bootstrap_blocos(valores, 3, 500, 9)


def test_bootstrap_serie_vazia():
    assert ic_bootstrap_blocos([], 5, 200, 1) == (None, None)


def test_bootstrap_percentis_99_com_valor_constante():
    lo, hi = ic_bootstrap_blocos([0.4] * 10, 5, 200, 1, percentis=(0.5, 99.5))
    assert (lo, hi) == pytest.approx((0.4, 0.4), abs=1e-12)


def test_bootstrap_padrao_continua_95():
    v = np.random.default_rng(0).normal(0, 1, 50)
    padrao = ic_bootstrap_blocos(v, 5, 200, 1)
    assert padrao[0] == pytest.approx(-0.22262255984169776, abs=1e-12)
    assert padrao[1] == pytest.approx(0.4797838262846961, abs=1e-12)
    assert padrao == ic_bootstrap_blocos(v, 5, 200, 1, percentis=(2.5, 97.5))


def test_bootstrap_99_e_mais_largo_que_95():
    v = np.random.default_rng(0).normal(0, 1, 50)
    lo95, hi95 = ic_bootstrap_blocos(v, 5, 2000, 1)
    lo99, hi99 = ic_bootstrap_blocos(v, 5, 2000, 1, percentis=(0.5, 99.5))
    assert lo99 <= lo95
    assert hi99 >= hi95


# ---------- Robustez por ano e sensibilidade ----------

def _diario_simples(datas, acertos_top, com_excesso=False):
    df = pd.DataFrame({
        "data": pd.to_datetime(datas),
        "acerto_top": acertos_top,
        "acerto_ultimos": [0.5] * len(datas),
    })
    if com_excesso:
        df["excesso_top"] = 0.001
        df["excesso_ultimos"] = -0.001
    return df


def test_por_ano_taxa_por_ano_do_calendario():
    diario = _diario_simples(
        ["2025-12-29", "2025-12-30", "2026-01-02", "2026-01-05"], [0.6, 0.4, 0.8, 0.4]
    )
    anos = por_ano(diario, com_retorno=False)
    assert list(anos.columns) == ["ano", "n_dias", "taxa_acerto"]
    assert list(anos["ano"]) == [2025, 2026]
    assert anos.loc[0, "taxa_acerto"] == pytest.approx(0.5, abs=1e-12)
    assert anos.loc[0, "n_dias"] == 2
    assert anos.loc[1, "taxa_acerto"] == pytest.approx(0.6, abs=1e-12)
    assert anos.loc[1, "n_dias"] == 2


def test_por_ano_com_excesso():
    diario = _diario_simples(["2025-12-29", "2026-01-02"], [0.6, 0.4], com_excesso=True)
    anos = por_ano(diario, com_retorno=True)
    assert "excesso_medio" in anos.columns
    assert anos.loc[0, "excesso_medio"] == pytest.approx(0.001, abs=1e-12)


def test_sensibilidade_ultimo_ano_e_anteriores():
    diario = _diario_simples(["2025-06-30", "2025-07-01", "2026-06-30"], [0.2, 0.4, 0.6])
    s = sensibilidade_ultimo_ano(diario)
    assert s["corte"] == "2025-06-30"
    assert s["ultimo_ano"]["n_dias"] == 2
    assert s["ultimo_ano"]["taxa_acerto"] == pytest.approx(0.5, abs=1e-12)
    assert s["anteriores"]["n_dias"] == 1
    assert s["anteriores"]["taxa_acerto"] == pytest.approx(0.2, abs=1e-12)


def test_sensibilidade_sem_anteriores_devolve_none():
    diario = _diario_simples(["2026-03-02", "2026-03-03"], [0.4, 0.6])
    s = sensibilidade_ultimo_ano(diario)
    assert s["anteriores"] is None
    assert s["ultimo_ano"]["n_dias"] == 2


# ---------- Calibração ----------

def test_calibracao_ece_e_brier_nao_aprovada():
    prob = [0.05, 0.12, 0.18, 0.52, 0.54, 0.56, 0.58, 0.95]
    alvo = [0, 0, 1, 1, 0, 1, 1, 1]
    c = calibracao(prob, alvo, bins=10, ece_maximo=0.02, linhas_minimas=5)
    assert c["ece"] == pytest.approx(0.2, abs=1e-12)
    assert c["brier"] == pytest.approx(0.197975, abs=1e-6)
    assert c["n"] == 8
    assert c["aprovada"] is False
    assert [linha["bin"] for linha in c["tabela"]] == [0, 1, 5, 9]
    assert [linha["n"] for linha in c["tabela"]] == [1, 2, 4, 1]


def test_calibracao_bem_calibrada():
    prob = [0.25] * 4 + [0.75] * 4
    alvo = [1, 0, 0, 0, 1, 1, 1, 0]
    c5 = calibracao(prob, alvo, bins=10, ece_maximo=0.02, linhas_minimas=5)
    assert c5["ece"] == pytest.approx(0.0, abs=1e-12)
    assert c5["brier"] == pytest.approx(0.1875, abs=1e-12)
    assert c5["aprovada"] is True
    c10 = calibracao(prob, alvo, bins=10, ece_maximo=0.02, linhas_minimas=10)
    assert c10["aprovada"] is False
