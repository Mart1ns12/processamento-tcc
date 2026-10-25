"""Retornos diários suspeitos fora da volatilidade e do beta (seção 6, "Retorno diário suspeito").

Casos V1 a V5 do plano de 24/10/2026. Dados escritos à mão com a fábrica `fabrica_precos`.
Nenhum teste usa banco ou rede.
"""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, precos_de, pregoes_uteis, serie_por_retornos
from processamento.exclusoes import Exclusoes
from processamento.experimento.parametros import ParametrosExperimento
from processamento.experimento.variaveis import variaveis_de_preco
from processamento.fatos import precos as fatos_precos
from processamento.fatos.precos import (
    HIST,
    OK,
    ParametrosPrecos,
    beta,
    calcular_precos,
    carregar_parametros_precos,
    retornos_suspeitos,
    volatilidade,
)


def _mascara(index: pd.Index, ticker: str, posicoes: list[int]) -> pd.DataFrame:
    """Máscara bool de uma ação: True nas posições (índice do pregão) dadas; o resto False."""
    return pd.DataFrame({ticker: [i in posicoes for i in range(len(index))]}, index=index)


# ---------------------------------------------------------------- V1: volatilidade, n = 3

CAL9 = pregoes_uteis(9, "2026-04-06")
AJ_V1 = [100.0, 101.0, 99.0, 300.0, 303.0, 300.0, 303.0, 306.0, 309.0]   # p3 = salto (retorno 300/99 − 1)


def _g_v1() -> pd.DataFrame:
    return fatos_precos.grade_de_precos(precos_de("XXXX3", CAL9, AJ_V1), CAL9, "fechamento_ajustado", ["XXXX3"])


def test_v1_volatilidade_sem_excluir_inclui_o_salto():
    g = _g_v1()
    res = volatilidade(g, 3)
    r = [300 / 99 - 1, 303 / 300 - 1, 300 / 303 - 1]   # p3, p4, p5
    assert res.valor["XXXX3"].iloc[5] == pytest.approx(np.std(r, ddof=1), rel=1e-12)
    assert res.status["XXXX3"].iloc[5] == OK


def test_v1_volatilidade_com_excluir_p3_tira_p3_p4_p5_e_volta_em_p6():
    g = _g_v1()
    ex = _mascara(g.index, "XXXX3", [3])
    res = volatilidade(g, 3, excluir=ex)
    assert res.status["XXXX3"].iloc[3:6].tolist() == [HIST, HIST, HIST]
    assert res.valor["XXXX3"].iloc[3:6].isna().all()
    r = [303 / 300 - 1, 300 / 303 - 1, 303 / 300 - 1]   # p4, p5, p6 (p6 já não contém p3)
    assert res.valor["XXXX3"].iloc[6] == pytest.approx(np.std(r, ddof=1), rel=1e-12)
    assert res.status["XXXX3"].iloc[6] == OK


def test_v1_volatilidade_em_p8_igual_com_e_sem_excluir():
    g = _g_v1()
    ex = _mascara(g.index, "XXXX3", [3])
    com = volatilidade(g, 3, excluir=ex)
    sem = volatilidade(g, 3)
    assert com.valor["XXXX3"].iloc[8] == pytest.approx(sem.valor["XXXX3"].iloc[8], rel=1e-12)
    assert com.status["XXXX3"].iloc[8] == sem.status["XXXX3"].iloc[8] == OK


# ---------------------------------------------------------------- V2: beta, janela = 6, mínimo = 4

IBOV_V2 = serie_por_retornos(1000.0, [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.01])
# ação = 2·r do IBOV em todo dia, exceto p4 (retorno +3,0: erro da coleta)
ACAO_V2 = serie_por_retornos(100.0, [0.02, -0.04, 0.03, 3.0, -0.02, 0.04, -0.01, 0.02])


def _g_v2():
    precos = pd.concat([precos_de("XXXX3", CAL9, ACAO_V2), precos_de("IBOV", CAL9, IBOV_V2)])
    g = fatos_precos.grade_de_precos(precos, CAL9, "fechamento_ajustado", ["XXXX3"])
    ibov = fatos_precos.grade_de_precos(precos, CAL9, "fechamento_ajustado", ["IBOV"])["IBOV"]
    return g, ibov


def test_v2_beta_com_excluir_p4_da_2():
    g, ibov = _g_v2()
    ex = _mascara(g.index, "XXXX3", [4])
    res = beta(g, ibov, 6, 4, excluir=ex)
    assert res.valor["XXXX3"].iloc[8] == pytest.approx(2.0, abs=1e-12)
    assert res.status["XXXX3"].iloc[8] == OK


def test_v2_beta_sem_excluir_nao_da_2():
    g, ibov = _g_v2()
    res = beta(g, ibov, 6, 4)
    assert abs(res.valor["XXXX3"].iloc[8] - 2) > 0.1


def test_v2_beta_com_excluir_e_minimo_6_vira_historico_insuficiente():
    g, ibov = _g_v2()
    ex = _mascara(g.index, "XXXX3", [4])
    res = beta(g, ibov, 6, 6, excluir=ex)   # sobram 5 pares em p8 (p3, p5, p6, p7, p8)
    assert res.status["XXXX3"].iloc[8] == HIST
    assert np.isnan(res.valor["XXXX3"].iloc[8])


# ---------------------------------------------------------------- V3: excluir todo False = sem excluir

CAL8 = pregoes_uteis(8, "2026-04-06")


def _g_v3():
    precos = pd.concat([
        precos_de("XXXX3", CAL8, [100.0, 101.0, 99.0, None, 103.0, 104.0, 102.0, 105.0]),   # NaN no meio
        precos_de("YYYY3", CAL8, [50.0, 51.0, 49.5, 50.5, 52.0, 51.0, 53.0, 52.5]),
        precos_de("IBOV", CAL8, [1000.0, 1010.0, 1005.0, 1020.0, 1015.0, 1030.0, 1025.0, 1040.0]),
    ])
    g = fatos_precos.grade_de_precos(precos, CAL8, "fechamento_ajustado", ["XXXX3", "YYYY3"])
    ibov = fatos_precos.grade_de_precos(precos, CAL8, "fechamento_ajustado", ["IBOV"])["IBOV"]
    return g, ibov


@pytest.mark.parametrize("ex_fn", [
    lambda g: pd.DataFrame(False, index=g.index, columns=g.columns),
    lambda g: pd.DataFrame(dtype=bool),   # células ausentes = False
])
def test_v3_excluir_todo_falso_e_igual_a_sem_excluir(ex_fn):
    g, ibov = _g_v3()
    ex = ex_fn(g)
    vol_a, vol_b = volatilidade(g, 3), volatilidade(g, 3, excluir=ex)
    pd.testing.assert_frame_equal(vol_a.valor, vol_b.valor)
    pd.testing.assert_frame_equal(vol_a.status, vol_b.status)
    beta_a, beta_b = beta(g, ibov, 5, 3), beta(g, ibov, 5, 3, excluir=ex)
    pd.testing.assert_frame_equal(beta_a.valor, beta_b.valor)
    pd.testing.assert_frame_equal(beta_a.status, beta_b.status)


# ---------------------------------------------------------------- V4: painel (calcular_precos)

CAL12 = pregoes_uteis(12, "2026-04-06")
R_IBOV = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.01, 0.003, -0.004, 0.012]
R_AAAA = [0.02, -0.04, 0.03, 0.01, -0.02, 3.0, 0.0, 0.02, -0.01, 0.024, 0.024]   # p6 = +3,0 (suspeito)
R_BBBB = [0.005, 0.01, -0.01, 0.02, 0.0, -0.005, 0.01, 0.015, -0.02, 0.005, 0.01]
R_CCCC = [-0.01, 0.02, 0.01, -0.005, 0.015, 0.0, 0.02, -0.01, 0.005, 0.01, -0.02]


def _mundo_v4():
    precos = pd.concat([
        precos_de("IBOV", CAL12, serie_por_retornos(1000.0, R_IBOV)),
        precos_de("AAAA3", CAL12, serie_por_retornos(100.0, R_AAAA)),
        precos_de("BBBB3", CAL12, serie_por_retornos(50.0, R_BBBB)),
        precos_de("CCCC3", CAL12, serie_por_retornos(70.0, R_CCCC)),
    ])
    cadastro = cadastro_de([("AAAA3", "1", "S1", "ON"), ("BBBB3", "2", "S1", "ON"), ("CCCC3", "3", "S2", "ON")])
    params = replace(carregar_parametros_precos(), janelas={"d1": 1}, volatilidade_retornos=3,
                     beta_pregoes=5, beta_minimo=3)
    return precos, cadastro, params


def test_v4_painel_so_muda_o_ticker_com_retorno_suspeito():
    precos, cadastro, params = _mundo_v4()
    res = calcular_precos(precos, cadastro, CAL12, Exclusoes(), params)
    tickers = ["AAAA3", "BBBB3", "CCCC3"]
    g = fatos_precos.grade_de_precos(precos, CAL12, "fechamento_ajustado", tickers)
    ibov = fatos_precos.grade_de_precos(precos, CAL12, "fechamento_ajustado", ["IBOV"])["IBOV"]
    susp = retornos_suspeitos(g, params.retorno_suspeito_min, params.retorno_suspeito_max,
                              params.base_defasagem_max_pregoes)
    assert susp["AAAA3"].tolist() == [False] * 6 + [True] + [False] * 5
    assert not susp["BBBB3"].any() and not susp["CCCC3"].any()

    vol_sem = volatilidade(g, 3).valor
    beta_sem = beta(g, ibov, 5, 3).valor
    vol_painel = res["volatilidade_3d.valor"].valor
    beta_painel = res["beta.valor"].valor

    # painel = funções com a máscara de suspeitos
    pd.testing.assert_frame_equal(vol_painel, volatilidade(g, 3, excluir=susp).valor)
    pd.testing.assert_frame_equal(beta_painel, beta(g, ibov, 5, 3, excluir=susp).valor)

    # AAAA3 muda: em p8 a janela de 3 (p6..p8) tem o suspeito
    assert np.isnan(vol_painel["AAAA3"].iloc[8]) and np.isfinite(vol_sem["AAAA3"].iloc[8])
    assert np.isfinite(beta_painel["AAAA3"].iloc[8]) and np.isfinite(beta_sem["AAAA3"].iloc[8])
    assert abs(beta_painel["AAAA3"].iloc[8] - beta_sem["AAAA3"].iloc[8]) > 1e-6

    # BBBB3 e CCCC3 não mudam
    pd.testing.assert_frame_equal(vol_painel[["BBBB3", "CCCC3"]], vol_sem[["BBBB3", "CCCC3"]])
    pd.testing.assert_frame_equal(beta_painel[["BBBB3", "CCCC3"]], beta_sem[["BBBB3", "CCCC3"]])


# ---------------------------------------------------------------- V5: variaveis_de_preco (experimento)

CAL50 = pregoes_uteis(50, "2025-01-02")
TICKERS_V5 = ["AAAA3", "BBBB3"]


def _params_exp() -> ParametrosExperimento:
    return ParametrosExperimento(
        retornos={"ret_1d": 1, "ret_5d": 5, "ret_20d": 20},
        exposicao_pregoes=120,
        exposicao_minimo=60,
        extremos_pregoes=252,
        extremos_minimo=120,
        mudanca_tom_pregoes=30,
        mudanca_tom_minimo=5,
        sem_horario_na_noite=True,
        inicio_janela="manha",
        deduplicar_titulo=True,
        origens_principais=("cvm_ipe",),
        tipos_principais=("reportagem",),
        papeis_principais=("protagonista", "citada_com_fato"),
    )


def _mundo_v5():
    rng = np.random.default_rng(5)
    rets_aaaa = rng.normal(0, 0.01, 49).tolist()
    rets_aaaa[24] = 2.5   # pregão 25 (índice 25 do calendário): retorno suspeito de +250%
    rets_bbbb = rng.normal(0, 0.01, 49).tolist()
    precos = pd.concat([
        precos_de("AAAA3", CAL50, serie_por_retornos(100.0, rets_aaaa)),
        precos_de("BBBB3", CAL50, serie_por_retornos(50.0, rets_bbbb)),
        precos_de("IBOV", CAL50, serie_por_retornos(1000.0, rng.normal(0, 0.01, 49).tolist())),
        precos_de("USDBRL", CAL50, serie_por_retornos(5.0, rng.normal(0, 0.005, 49).tolist())),
        precos_de("BRENT", CAL50, serie_por_retornos(70.0, rng.normal(0, 0.01, 49).tolist())),
    ])
    return precos


def test_v5_volatilidade_20d_do_experimento_some_so_nas_janelas_com_o_suspeito():
    precos = _mundo_v5()
    idx = fatos_precos.indice_pregoes(CAL50)
    mascara = pd.DataFrame(True, index=idx, columns=TICKERS_V5)
    setor_de = {"AAAA3": "S1", "BBBB3": "S1"}
    cnpj_de = {"AAAA3": "1", "BBBB3": "2"}
    params_precos = ParametrosPrecos(
        janelas={"d1": 1}, volume_pregoes=20, volatilidade_retornos=20, beta_pregoes=252,
        beta_minimo=120, setor_minimo=3, setor_excluir="empresa",
    )
    res = variaveis_de_preco(precos, CAL50, TICKERS_V5, mascara, setor_de, cnpj_de, _params_exp(), params_precos)
    vol = res["volatilidade_20d"]

    # suspeito em t = 25 (índice 25): a janela de 20 sessões contém o suspeito em t = 25 até 44
    assert vol["AAAA3"].iloc[25:45].isna().all()
    assert np.isfinite(vol["AAAA3"].iloc[24])
    assert np.isfinite(vol["AAAA3"].iloc[45])

    g_aj = fatos_precos.grade_de_precos(precos, CAL50, "fechamento_ajustado", TICKERS_V5)
    sem = fatos_precos.volatilidade(g_aj, 20).valor
    assert np.isfinite(sem["AAAA3"].iloc[30])   # sem a máscara, a mesma janela tem valor

    # BBBB3 não muda: igual à volatilidade sem máscara
    pd.testing.assert_series_equal(vol["BBBB3"], sem["BBBB3"])
