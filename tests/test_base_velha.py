"""Testes da regra da base velha (seção 6 da especificação, "Base velha"; plano docs/plano_base_velha.md, seção 1).

Casos A a F (defasagem, variação com borda, calcular_precos, setor, sem lacunas, sem vazamento) e 1G (retorno
suspeito através de lacuna). Valores esperados vêm do plano (conferidos num protótipo); não mudar o gabarito.
Séries montadas com tests/fabrica_precos.py. Nenhum teste usa banco ou rede.
"""

import dataclasses
import math

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, pregoes_uteis, precos_de
from processamento.exclusoes import Exclusoes
from processamento.fatos.precos import (
    HIST,
    OK,
    ParametrosPrecos,
    calcular_precos,
    defasagem_pregoes,
    grade_de_precos,
    indice_pregoes,
    retornos_asof,
    retornos_suspeitos,
    variacao,
)
from processamento.fatos.series import rentabilidade_setor_sem_empresa


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _mesmo(a, b) -> bool:
    if pd.isna(a) or pd.isna(b):
        return bool(pd.isna(a) and pd.isna(b))
    return a == pytest.approx(b, abs=1e-12)


# ---------------------------------------------------------------- A. defasagem_pregoes

def test_a_defasagem_pregoes_conta_desde_o_ultimo_valor():
    cal = pregoes_uteis(6)
    g = pd.DataFrame({"X": [np.nan, 1.0, np.nan, np.nan, 4.0, np.nan]}, index=pd.DatetimeIndex(pd.to_datetime(cal)))
    d = defasagem_pregoes(g)["X"]
    assert pd.isna(d.iloc[0])              # NaN antes do 1º valor
    assert list(d.iloc[1:]) == [0.0, 1.0, 2.0, 0.0, 1.0]


# ---------------------------------------------------------------- B. variacao com borda

CAL = pregoes_uteis(12)
PRECOS_B = pd.concat([
    precos_de("AAAA3", CAL, [100] + [None] * 5 + [106, 107, 108, 109, 110, 111]),
    precos_de("BBBB3", CAL, [100] + [None] * 6 + [107, 108, 109, 110, 111]),
    precos_de("CCCC3", CAL, [100, 101, None, 103, 104, 105, 106, 107, 108, 109, 110, 111]),
])
TICKERS_B = ["AAAA3", "BBBB3", "CCCC3"]

CASOS_B = [
    # (n, defasagem_max, ticker, linha, valor esperado (None = NaN), status)
    (1, 5, "AAAA3", 6, 0.06000000000000005, OK),
    (1, 5, "BBBB3", 7, None, HIST),
    (1, None, "BBBB3", 7, 0.07000000000000006, OK),
    (1, 5, "BBBB3", 8, 0.009345794392523255, OK),
    (1, 5, "CCCC3", 3, 0.01980198019801982, OK),
    (1, 0, "CCCC3", 3, None, HIST),
    (1, 0, "AAAA3", 7, 0.009433962264151052, OK),
    (2, 5, "AAAA3", 7, 0.07000000000000006, OK),
    (2, 5, "BBBB3", 8, None, HIST),
    (2, None, "BBBB3", 8, 0.08000000000000007, OK),
    (2, 0, "CCCC3", 3, 0.01980198019801982, OK),
]


@pytest.mark.parametrize("n, defasagem, ticker, linha, esperado, status", CASOS_B)
def test_b_variacao_com_base_velha(n, defasagem, ticker, linha, esperado, status):
    g = grade_de_precos(PRECOS_B, CAL, "fechamento", TICKERS_B)
    r = variacao(g, n, defasagem)
    assert r.status[ticker].iloc[linha] == status
    if _nan(esperado):
        assert pd.isna(r.valor[ticker].iloc[linha])
    else:
        assert r.valor[ticker].iloc[linha] == pytest.approx(esperado, abs=1e-12)


# ---------------------------------------------------------------- C. calcular_precos

PRECOS_C = pd.concat([PRECOS_B, precos_de("IBOV", CAL, [1000 + i for i in range(12)])])
CADASTRO_C = cadastro_de([("AAAA3", "1", "S", "ON"), ("BBBB3", "2", "S", "ON"), ("CCCC3", "3", "S", "ON")])
PARAMS_C = ParametrosPrecos(
    janelas={"d1": 1, "n2": 2}, volume_pregoes=20, volatilidade_retornos=20, beta_pregoes=252,
    beta_minimo=120, setor_minimo=3, setor_excluir="empresa",
)
T_C = pd.Timestamp(CAL[7])

CASOS_C = [
    # (indicador, ticker, valor esperado (None = NaN), status), com N = 5 (padrão)
    ("cotacao.variacao_dia", "AAAA3", 0.009433962264151052, OK),
    ("cotacao.variacao_dia", "BBBB3", None, HIST),
    ("variacao_preco.d1", "AAAA3", 0.009433962264151052, OK),
    ("variacao_preco.d1", "BBBB3", None, HIST),
    ("rentabilidade.d1", "AAAA3", 0.009433962264151052, OK),
    ("rentabilidade.d1", "BBBB3", None, HIST),
    ("rentabilidade.n2", "AAAA3", 0.07000000000000006, OK),
    ("rentabilidade.n2", "BBBB3", 0.07000000000000006, OK),
    ("rentabilidade.ibov.d1", "AAAA3", 0.0009940357852882276, OK),
    ("rentabilidade.ibov.d1", "BBBB3", 0.0009940357852882276, OK),
    ("rentabilidade.setor.d1", "AAAA3", 0.009433962264151052, OK),
    ("rentabilidade.setor.d1", "BBBB3", 0.009433962264151052, OK),
    ("rentabilidade.setor.n2", "AAAA3", 0.01904761904761898, OK),
    ("rentabilidade.setor.n2", "BBBB3", 0.01904761904761898, OK),
]


def _calcular_c(params):
    return calcular_precos(PRECOS_C, CADASTRO_C, CAL, Exclusoes(), params)


@pytest.mark.parametrize("indicador, ticker, esperado, status", CASOS_C)
def test_c_calcular_precos_com_a_regra(indicador, ticker, esperado, status):
    res = _calcular_c(PARAMS_C)
    g = res[indicador]
    assert g.status[ticker].loc[T_C] == status
    if _nan(esperado):
        assert pd.isna(g.valor[ticker].loc[T_C])
    else:
        assert g.valor[ticker].loc[T_C] == pytest.approx(esperado, abs=1e-12)


def test_c_sem_limite_bbbb3_volta_ao_valor_antigo():
    params = dataclasses.replace(PARAMS_C, base_defasagem_max_pregoes=10**9)
    res = _calcular_c(params)
    for indicador in ("cotacao.variacao_dia", "variacao_preco.d1", "rentabilidade.d1"):
        g = res[indicador]
        assert g.status["BBBB3"].loc[T_C] == OK
        assert g.valor["BBBB3"].loc[T_C] == pytest.approx(0.07000000000000006, abs=1e-12)


# ---------------------------------------------------------------- D. rentabilidade.setor (razão da SETOR_SEM)

CALS = pregoes_uteis(16)
PRECOS_D = pd.concat([
    precos_de("AAAA3", CALS, [10 + i for i in range(16)]),
    precos_de("BBBB3", CALS, [20, 21, 22] + [None] * 10 + [25, 26, 27.3]),
])
CAD_D = cadastro_de([("AAAA3", "1", "S", "ON"), ("BBBB3", "2", "S", "ON")])
JANELAS_D = {"d1": 1, "n2": 2, "n3": 3}


def _setor_d(defasagem_max):
    gaj = grade_de_precos(PRECOS_D, CALS, "fechamento_ajustado", ["AAAA3", "BBBB3"])
    return rentabilidade_setor_sem_empresa(gaj, CAD_D, ["AAAA3", "BBBB3"], ["AAAA3", "BBBB3"], JANELAS_D,
                                           "empresa", defasagem_max=defasagem_max)


def test_d_setor_com_base_velha_vira_historico_insuficiente():
    r = _setor_d(5)
    assert r["d1"].valor["AAAA3"].iloc[15] == pytest.approx(0.050000000000000044, abs=1e-12)
    assert r["d1"].status["AAAA3"].iloc[15] == OK
    assert pd.isna(r["n2"].valor["AAAA3"].iloc[15])
    assert r["n2"].status["AAAA3"].iloc[15] == HIST
    assert pd.isna(r["n3"].valor["AAAA3"].iloc[15])
    assert r["n3"].status["AAAA3"].iloc[15] == HIST


def test_d_setor_sem_limite_mostra_o_valor_antigo():
    r = _setor_d(None)
    assert r["d1"].valor["AAAA3"].iloc[15] == pytest.approx(0.050000000000000044, abs=1e-12)
    assert r["n2"].valor["AAAA3"].iloc[15] == pytest.approx(0.09200000000000008, abs=1e-12)
    assert r["n3"].valor["AAAA3"].iloc[15] == pytest.approx(0.09200000000000008, abs=1e-12)
    assert r["n2"].status["AAAA3"].iloc[15] == OK


# ---------------------------------------------------------------- E. sem lacunas longas, nada muda

def _grade_sintetica() -> pd.DataFrame:
    """400 pregões, 3 tickers; lacunas de 5 (A), 3 (B) e 1 (C) pregões."""
    rng = np.random.default_rng(20261024)
    idx = indice_pregoes([d.date() for d in pd.bdate_range("2024-01-02", periods=400)])
    g = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (400, 3)), axis=0), index=idx, columns=["A", "B", "C"])
    g.iloc[50:55, 0] = np.nan
    g.iloc[100:103, 1] = np.nan
    g.iloc[300, 2] = np.nan
    return g


def test_e_sem_lacuna_de_mais_de_5_nada_muda():
    g = _grade_sintetica()
    for n in (1, 21, 126, 252):
        com, sem = variacao(g, n, 5), variacao(g, n)
        assert com.valor.equals(sem.valor)
        assert com.status.equals(sem.status)


@pytest.mark.parametrize("n, data_esperada", [
    (1, "2024-03-20"), (21, "2024-04-17"), (126, "2024-09-11"), (252, "2025-03-06"),
])
def test_e_lacuna_de_6_muda_so_uma_celula(n, data_esperada):
    g = _grade_sintetica()
    g.iloc[50:56, 0] = np.nan              # lacuna de 6 pregões em A
    com, sem = variacao(g, n, 5), variacao(g, n)
    diferentes = com.status != sem.status
    assert int(diferentes.to_numpy().sum()) == 1
    data = pd.Timestamp(data_esperada)
    assert bool(diferentes.loc[data, "A"])
    assert com.status.loc[data, "A"] == HIST


# ---------------------------------------------------------------- F. sem vazamento temporal

def test_f_resultado_em_t_nao_depende_do_futuro():
    g = _grade_sintetica()
    g.iloc[50:56, 0] = np.nan              # mesma grade de E com lacuna de 6
    for n in (1, 21):
        completo = variacao(g, n, 5)
        for t in g.index[[60, 76, 120, 399]]:
            parcial = variacao(g.loc[:t], n, 5)
            for c in g.columns:
                assert _mesmo(parcial.valor.loc[t, c], completo.valor.loc[t, c])
                assert parcial.status.loc[t, c] == completo.status.loc[t, c]


# ---------------------------------------------------------------- 1G. retorno suspeito através de lacuna

CAL9 = pregoes_uteis(9)


def _retornos_x(valores):
    g = grade_de_precos(precos_de("X", CAL9, valores), CAL9, "fechamento_ajustado", ["X"])
    return g


def test_1g_a_retorno_atravessando_lacuna_longa_nao_e_suspeito():
    g = _retornos_x([10.0] + [None] * 6 + [30.0, 30.0])
    p7, p8 = pd.Timestamp(CAL9[7]), pd.Timestamp(CAL9[8])
    com = retornos_suspeitos(g, -0.75, 1.0, 5)
    sem = retornos_suspeitos(g, -0.75, 1.0)
    assert not com.loc[p7, "X"]            # defasagem 6: retorno ausente, nunca suspeito
    assert not com.loc[p8, "X"]            # retorno 0.0
    assert sem.loc[p7, "X"]                # comportamento antigo: +200% suspeito
    assert not sem.loc[p8, "X"]
    assert retornos_asof(g).loc[p8, "X"] == pytest.approx(0.0, abs=1e-12)


def test_1g_b_lacuna_de_5_ainda_marca_suspeito():
    g = _retornos_x([10.0] + [None] * 5 + [30.0, 30.0, 30.0])
    p6 = pd.Timestamp(CAL9[6])
    com = retornos_suspeitos(g, -0.75, 1.0, 5)
    assert com.loc[p6, "X"]                # defasagem 5 = N: vale (retorno 2.0)
    assert retornos_suspeitos(g, -0.75, 1.0).loc[p6, "X"]


def test_1g_c_salto_sem_lacuna_continua_suspeito():
    g = _retornos_x([10.0, 10.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0])
    p2 = pd.Timestamp(CAL9[2])
    com = retornos_suspeitos(g, -0.75, 1.0, 5)
    sem = retornos_suspeitos(g, -0.75, 1.0)
    assert com.loc[p2, "X"]
    assert sem.loc[p2, "X"]
    assert int(com.to_numpy().sum()) == 1
    assert int(sem.to_numpy().sum()) == 1
