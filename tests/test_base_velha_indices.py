"""Testes da regra da base velha nos índices (seção 6 da especificação, "Base velha"; plano
docs/plano_base_velha.md, seções 1.1 e 1.4, casos G a J; Fase 2).

Cobre IDIV (janelas), CDI (`cdi_dia` com atraso), IPCA (janelas, `ipca_12m`, pontos do `series_diarias`) e a
variação do dia do `mercado_dia` (IBOV, USDBRL, BRENT). Valores esperados vêm do plano (conferidos num
protótipo); não mudar o gabarito. Séries montadas com tests/fabrica_precos.py. Nenhum teste usa banco ou rede.
"""

import dataclasses
import math
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from fabrica_precos import indices_de, pregoes_uteis, precos_de
from processamento.fatos.indices import calcular_indices, cdi_dia, ipca_12m, rentabilidade_ipca
from processamento.fatos.precos import HIST, INDISPONIVEL, OK, ParametrosPrecos
from processamento.fatos.series import indice_ipca
from processamento.saida.pacotes_fatos import _cotacao_de_indice


def _params(janelas):
    return ParametrosPrecos(
        janelas=janelas,
        volume_pregoes=20,
        volatilidade_retornos=20,
        beta_pregoes=252,
        beta_minimo=120,
        setor_minimo=3,
        setor_excluir="empresa",
    )


def _n(cal, base, t):
    """Número de pregões de `base` até `t` (sem contar t)."""
    return cal.index(date.fromisoformat(t)) - cal.index(date.fromisoformat(base))


# --- G. IDIV real reduzido (janelas com base velha) ----------------------------------------------

def _cenario_idiv():
    cal = [d.date() for d in pd.bdate_range("2024-12-30", "2026-10-22")]
    ind = indices_de([("2024-12-30", "IDIV", 1000), ("2026-10-20", "IDIV", 1600),
                      ("2026-10-21", "IDIV", 1605), ("2026-10-22", "IDIV", 1607)])
    precos = precos_de("PETR4", cal, [1.0] * len(cal))
    return cal, ind, precos


def test_idiv_d1_ok_e_m1_m6_a1_historico_insuficiente_em_22_10_2026():
    cal, ind, precos = _cenario_idiv()
    params = _params({"d1": 1, "m1": 21, "m6": 126, "a1": 252})
    res = calcular_indices(precos, ind, cal, params)
    t = pd.Timestamp("2026-10-22")

    assert res["d1"].valor.at[t, "IDIV"] == pytest.approx(0.0012461059190032042, abs=1e-12)
    assert res["d1"].status.at[t, "IDIV"] == OK
    for janela in ("m1", "m6", "a1"):
        assert math.isnan(res[janela].valor.at[t, "IDIV"])
        assert res[janela].status.at[t, "IDIV"] == HIST


def test_idiv_em_21_10_2026_d1_ok_com_base_de_20_10():
    cal, ind, precos = _cenario_idiv()
    res = calcular_indices(precos, ind, cal, _params({"d1": 1, "m1": 21, "m6": 126, "a1": 252}))
    t = pd.Timestamp("2026-10-21")

    assert res["d1"].valor.at[t, "IDIV"] == pytest.approx(0.0031250000000000444, abs=1e-12)
    assert res["d1"].status.at[t, "IDIV"] == OK
    for janela in ("m1", "m6", "a1"):
        assert res[janela].status.at[t, "IDIV"] == HIST


def test_idiv_em_20_10_2026_sem_base_valida():
    cal, ind, precos = _cenario_idiv()
    res = calcular_indices(precos, ind, cal, _params({"d1": 1, "m1": 21, "m6": 126, "a1": 252}))
    t = pd.Timestamp("2026-10-20")

    for janela in ("d1", "m1", "m6", "a1"):
        assert math.isnan(res[janela].valor.at[t, "IDIV"])
        assert res[janela].status.at[t, "IDIV"] == HIST


def test_idiv_sem_limite_da_base_mostra_o_bug_m1_m6_a1_ok():
    cal, ind, precos = _cenario_idiv()
    params = dataclasses.replace(_params({"d1": 1, "m1": 21, "m6": 126, "a1": 252}),
                                 base_defasagem_max_pregoes=10**9)
    res = calcular_indices(precos, ind, cal, params)
    t = pd.Timestamp("2026-10-22")

    for janela in ("m1", "m6", "a1"):
        assert res[janela].valor.at[t, "IDIV"] == pytest.approx(0.607, abs=1e-12)
        assert res[janela].status.at[t, "IDIV"] == OK


# --- H. cdi_dia com atraso de pregões -----------------------------------------------------------

CALC = pregoes_uteis(10)  # 02/01 a 15/01/2025 (sem feriados)
CDI_LINHAS = [(d.isoformat(), "CDI", 0.05) for d in CALC[:4]]  # taxa até 07/01/2025


def test_cdi_dia_com_5_pregoes_de_atraso_e_ok():
    ind = indices_de(CDI_LINHAS)
    valor, status, data = cdi_dia(ind, CALC[8], CALC, 5)  # 14/01/2025

    assert valor == pytest.approx(0.0005, abs=1e-12)
    assert status == OK
    assert data == pd.Timestamp("2025-01-07")


def test_cdi_dia_com_6_pregoes_de_atraso_e_indisponivel():
    ind = indices_de(CDI_LINHAS)
    valor, status, data = cdi_dia(ind, CALC[9], CALC, 5)  # 15/01/2025

    assert math.isnan(valor)
    assert status == INDISPONIVEL
    assert data is None


def test_cdi_dia_sem_calendario_mantem_o_comportamento_antigo():
    ind = indices_de(CDI_LINHAS)
    valor, status, data = cdi_dia(ind, CALC[9])

    assert valor == pytest.approx(0.0005, abs=1e-12)
    assert status == OK
    assert data == pd.Timestamp("2025-01-07")


# --- I. IPCA: atraso em meses -------------------------------------------------------------------

IPCA_TAB = [
    ("2025-01-01", "IPCA", 0.50),
    ("2025-02-01", "IPCA", 1.00),
    ("2025-03-01", "IPCA", 0.20),
]
IPCA_12 = [("2025-01-01", "IPCA", 1.00)] + [
    (f"{ts:%Y-%m-%d}", "IPCA", 0.50) for ts in pd.date_range("2025-02-01", "2026-01-01", freq="MS")
]
CAL_IPCA = pregoes_uteis(120, inicio="2025-01-01")


def test_ipca_12m_atraso_2_ok_e_atraso_3_indisponivel():
    valor, status = ipca_12m(indices_de(IPCA_12), date(2026, 3, 10), 2)
    assert valor == pytest.approx(0.061677811864498056, abs=1e-12)
    assert status == OK

    valor, status = ipca_12m(indices_de(IPCA_12), date(2026, 4, 10), 2)
    assert math.isnan(valor)
    assert status == INDISPONIVEL


def test_ipca_12m_sem_parametro_mantem_o_comportamento_antigo():
    valor, status = ipca_12m(indices_de(IPCA_12), date(2026, 4, 10))
    assert valor == pytest.approx(0.061677811864498056, abs=1e-12)
    assert status == OK


def test_rentabilidade_ipca_atraso_2_ok_e_atraso_3_indisponivel():
    ind = indices_de(IPCA_TAB)
    n = _n(CAL_IPCA, "2025-02-14", "2025-05-14")
    g = rentabilidade_ipca(ind, CAL_IPCA, n, 2)
    assert g.valor.at[pd.Timestamp("2025-05-14"), "IPCA"] == pytest.approx(0.01201999999999992, abs=1e-12)
    assert g.status.at[pd.Timestamp("2025-05-14"), "IPCA"] == OK

    n = _n(CAL_IPCA, "2025-02-14", "2025-06-16")
    g = rentabilidade_ipca(ind, CAL_IPCA, n, 2)
    assert math.isnan(g.valor.at[pd.Timestamp("2025-06-16"), "IPCA"])
    assert g.status.at[pd.Timestamp("2025-06-16"), "IPCA"] == INDISPONIVEL


def test_rentabilidade_ipca_sem_parametro_mantem_o_comportamento_antigo():
    n = _n(CAL_IPCA, "2025-02-14", "2025-06-16")
    g = rentabilidade_ipca(indices_de(IPCA_TAB), CAL_IPCA, n)
    assert g.valor.at[pd.Timestamp("2025-06-16"), "IPCA"] == pytest.approx(0.01201999999999992, abs=1e-12)
    assert g.status.at[pd.Timestamp("2025-06-16"), "IPCA"] == OK


def test_indice_ipca_base_100_com_atraso_maximo_2_meses():
    ind = indices_de([("2025-07-01", "IPCA", 0.26), ("2025-08-01", "IPCA", 0.50)])
    cal = [date(2025, 8, 15), date(2025, 9, 15), date(2025, 10, 15), date(2025, 11, 14), date(2025, 12, 15)]
    g = indice_ipca(ind, cal, 2)

    valores = g.valor["IPCA"].tolist()
    assert valores[0] == pytest.approx(100.0, abs=1e-9)
    assert valores[1] == pytest.approx(100.5, abs=1e-9)
    assert valores[2] == pytest.approx(100.5, abs=1e-9)
    assert math.isnan(valores[3]) and math.isnan(valores[4])
    assert g.status["IPCA"].tolist() == [OK, OK, OK, INDISPONIVEL, INDISPONIVEL]


def test_indice_ipca_sem_parametro_mantem_o_comportamento_antigo():
    ind = indices_de([("2025-07-01", "IPCA", 0.26), ("2025-08-01", "IPCA", 0.50)])
    cal = [date(2025, 8, 15), date(2025, 9, 15), date(2025, 10, 15), date(2025, 11, 14), date(2025, 12, 15)]
    g = indice_ipca(ind, cal)

    assert g.valor["IPCA"].tolist() == pytest.approx([100.0, 100.5, 100.5, 100.5, 100.5], abs=1e-9)
    assert g.status["IPCA"].tolist() == [OK] * 5


# --- J. variação do dia do mercado_dia (IBOV, USDBRL, BRENT) ------------------------------------

def test_cotacao_de_indice_brent_com_base_velha_e_usdbrl_com_defasagem_5():
    calm = pregoes_uteis(10)
    brent = precos_de("BRENT", calm, [80, None, None, None, None, None, None, 84, 85, 86])
    usdbrl = precos_de("USDBRL", calm, [5.0, None, None, None, None, None, 5.3, 5.4, 5.5, 5.6])
    precos = pd.concat([brent, usdbrl], ignore_index=True)

    ins = SimpleNamespace(precos=precos, cal=calm, t=calm[7])
    brent_dia = _cotacao_de_indice(ins, "BRENT", "USD/barril", 5)
    assert brent_dia["variacao_dia"] == {"valor": None, "status": HIST}
    assert brent_dia["fechamento"] == {"valor": 84.0, "status": OK}

    usd_dia = _cotacao_de_indice(ins, "USDBRL", "BRL/USD", 5)
    assert usd_dia["variacao_dia"]["valor"] == pytest.approx(0.018867924528301883, abs=1e-12)
    assert usd_dia["variacao_dia"]["status"] == OK

    ins_antes = SimpleNamespace(precos=precos, cal=calm, t=calm[6])
    usd_antes = _cotacao_de_indice(ins_antes, "USDBRL", "BRL/USD", 5)
    assert usd_antes["variacao_dia"]["valor"] == pytest.approx(0.06000000000000005, abs=1e-12)
    assert usd_antes["variacao_dia"]["status"] == OK
