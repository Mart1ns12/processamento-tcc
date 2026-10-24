"""Balanço velho (seção 6, "Balanço velho"; plano item 2, Fase 2).

Borda: velho ⇔ fim do mês de (data_fim_periodo + N meses) < t. O painel do dia e os múltiplos
diários usam `foto_dentro_do_prazo`; payout por ano, tabela trimestral e balanço de referência
continuam com a foto original. Mundo de tests/fabrica_fundamentos.py com duas linhas novas
(U e PREJ entregues em 2026-03-31). Sem banco e sem rede.
"""

import dataclasses
import math
from datetime import date

import pandas as pd
import pytest

from fabrica_fundamentos import CNPJ, EXCL, _a, balanco_de, mundo
from processamento.fatos.fundamentos import (
    LUCRO_NEGATIVO,
    DadosFundamentos,
    balanco_referencia_no_dia,
    balanco_velho,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
    payout_por_ano,
    tabela_trimestral,
)
from processamento.fatos.multiplos import multiplos_diarios
from processamento.fatos.precos import INDISPONIVEL, NAO_SE_APLICA, OK

IND = INDISPONIVEL
NAO = NAO_SE_APLICA
LN = LUCRO_NEGATIVO

CADASTRO, BALANCOS, ACOES, PROVENTOS, PRECOS, CAL, MUDANCAS = mundo()
EXTRA = pd.concat([
    balanco_de(CNPJ["U"], [_a("ITR", "2026-01-01", "2026-03-31", "2026-03-31", 400, 160, 50, 1350)]),
    balanco_de(CNPJ["PREJ"], [_a("ITR", "2026-01-01", "2026-03-31", "2026-03-31", 400, 160, -40, 1250)]),
])
BAL2 = pd.concat([BALANCOS, EXTRA], ignore_index=True)
DADOS2 = DadosFundamentos(PRECOS, CADASTRO, BAL2, ACOES, PROVENTOS, MUDANCAS)
P15 = carregar_parametros_fundamentos()
P3 = dataclasses.replace(P15, balanco_idade_max_meses=3)
ABRIL = date(2026, 4, 1)
G15 = calcular_fundamentos_no_dia(ABRIL, CAL, DADOS2, EXCL, P15, "empresa")
G3 = calcular_fundamentos_no_dia(ABRIL, CAL, DADOS2, EXCL, P3, "empresa")


def _celula(grades, ticker, campo):
    """(valor, status) de um indicador de um ticker na linha do dia da grade."""
    grade = grades[campo]
    return grade.valor.iloc[0][ticker], grade.status.iloc[0][ticker]


def _dia(grade, dia, ticker):
    """(valor, status) de um ticker num dia da grade diária."""
    ts = pd.Timestamp(dia)
    return grade.valor.loc[ts, ticker], grade.status.loc[ts, ticker]


# 2A: borda (fim do mês de data_fim + meses; velho se o limite é antes de t).
@pytest.mark.parametrize(
    "data_fim, t, meses, esperado",
    [
        (pd.Timestamp("2023-12-31"), pd.Timestamp("2025-03-31"), 15, False),
        (pd.Timestamp("2023-12-31"), pd.Timestamp("2025-04-01"), 15, True),
        (pd.Timestamp("2024-02-29"), pd.Timestamp("2025-05-31"), 15, False),
        (pd.Timestamp("2024-02-29"), pd.Timestamp("2025-06-01"), 15, True),
        (pd.Timestamp("2024-09-30"), pd.Timestamp("2025-12-31"), 15, False),
        (pd.Timestamp("2024-09-30"), pd.Timestamp("2026-01-01"), 15, True),
        (pd.Timestamp("2024-11-30"), pd.Timestamp("2026-02-28"), 15, False),
        (pd.Timestamp("2024-11-30"), pd.Timestamp("2026-03-02"), 15, True),
        (pd.Timestamp("2025-12-31"), pd.Timestamp("2026-03-31"), 3, False),
        (pd.Timestamp("2025-12-31"), pd.Timestamp("2026-04-01"), 3, True),
        (None, pd.Timestamp("2026-04-01"), 3, False),
        (pd.NaT, pd.Timestamp("2026-04-01"), 3, False),
    ],
)
def test_balanco_velho_usa_o_fim_do_mes(data_fim, t, meses, esperado):
    assert balanco_velho(data_fim, t, meses) is esperado


# 2B: integração na fábrica. Em 01/04/2026 com 3 meses, as empresas velhas (A, BANC, D, BDRX, DUPN,
# EXTI, K) saem; com 15 meses, nada muda em relação ao comportamento anterior.
# (ticker, campo, valor com 15 meses, status com 15 meses, valor com 3 meses, status com 3 meses).
# Valor None = NaN.
CASOS_2B = [
    ("AAAA3", "pl.valor", 5.75, OK, None, IND),
    ("AAAA3", "pvp.valor", 0.7076923076923077, OK, None, IND),
    ("AAAA3", "roe.valor", 0.12307692307692308, OK, None, IND),
    ("AAAA3", "payout.valor", 0.328125, OK, None, IND),
    ("AAAA3", "margem_bruta.valor", 0.41333333333333333, OK, None, IND),
    ("AAAA3", "margem_liquida.valor", 0.10666666666666667, OK, None, IND),
    ("AAAA3", "dividend_yield.valor", 0.05, OK, 0.05, OK),
    ("AAAA3", "pl.setor", 17.142857142857142, OK, 17.142857142857142, OK),
    ("AAAA3", "pvp.setor", 1.271111111111111, OK, 1.271111111111111, OK),
    ("UUUU11", "pl.valor", 17.142857142857142, OK, 17.142857142857142, OK),
    ("UUUU11", "pl.setor", 5.75, OK, None, IND),
    ("UUUU11", "pvp.setor", 0.5138461538461538, OK, 0.32, OK),
    ("UUUU11", "roe.setor", 0.02153846153846154, OK, -0.08, OK),
    ("UUUU11", "payout.setor", 0.328125, OK, None, IND),
    ("UUUU11", "margem_bruta.setor", 0.41311827956989244, OK, 0.4129032258064516, OK),
    ("PREJ3", "pl.valor", -4.0, LN, -4.0, LN),
    ("PREJ3", "pl.setor", 11.446428571428571, OK, 17.142857142857142, OK),
    ("PREJ3", "pvp.setor", 1.464957264957265, OK, 2.2222222222222223, OK),
    ("PREJ3", "roe.setor", 0.12635327635327637, OK, 0.12962962962962962, OK),
    ("PREJ3", "payout.setor", 0.8497767857142857, OK, 1.3714285714285714, OK),
    ("DDDD3", "ebitda.valor_12m", 111.0, OK, None, IND),
    ("DDDD3", "ebitda.margem", 0.2642857142857143, OK, None, IND),
    ("DDDD3", "endividamento.divida_liquida", 100.0, OK, None, IND),
    ("DDDD3", "endividamento.dl_pl", 0.18518518518518517, OK, None, IND),
    ("DDDD3", "endividamento.caixa_liquido", 0.0, OK, None, IND),
    ("BANC4", "pl.valor", 12.5, OK, None, IND),
    ("BANC4", "pvp.valor", 1.5384615384615385, OK, None, IND),
    ("BANC4", "margem_bruta.valor", None, NAO, None, NAO),
    ("BANC4", "ebitda.valor_12m", None, NAO, None, NAO),
    ("BANC4", "endividamento.dl_pl", None, NAO, None, NAO),
    ("BANC4", "dividend_yield.valor", 0.0, OK, 0.0, OK),
    ("KKKK3", "pl.valor", 18.75, OK, None, IND),
    ("KKKK3", "dividend_yield.valor", 0.013000000000000001, OK, 0.013000000000000001, OK),
]


def _confere(valor_obtido, status_obtido, valor_esperado, status_esperado):
    assert status_obtido == status_esperado
    if valor_esperado is None:
        assert math.isnan(valor_obtido)
    else:
        assert valor_obtido == pytest.approx(valor_esperado, rel=1e-12)


@pytest.mark.parametrize("ticker, campo, v15, s15, v3, s3", CASOS_2B)
def test_fabrica_com_15_e_com_3_meses(ticker, campo, v15, s15, v3, s3):
    _confere(*_celula(G15, ticker, campo), v15, s15)
    _confere(*_celula(G3, ticker, campo), v3, s3)


def test_com_3_meses_no_dia_da_borda_2026_03_31_pl_ainda_vale():
    g = calcular_fundamentos_no_dia(date(2026, 3, 31), CAL, DADOS2, EXCL, P3, "empresa")
    _confere(*_celula(g, "AAAA3", "pl.valor"), 5.75, OK)


# 2C: não mudam (payout, tabela trimestral e balanço de referência usam a foto original).
def test_payout_tabela_e_balanco_de_referencia_nao_mudam():
    pd.testing.assert_frame_equal(
        payout_por_ano(ABRIL, DADOS2, EXCL, P3), payout_por_ano(ABRIL, DADOS2, EXCL, P15)
    )
    pd.testing.assert_frame_equal(
        tabela_trimestral(ABRIL, DADOS2, EXCL, P3), tabela_trimestral(ABRIL, DADOS2, EXCL, P15)
    )
    ref = balanco_referencia_no_dia(ABRIL, DADOS2, EXCL).set_index("ticker")
    assert ref.loc["AAAA3", "data_fim_periodo"] == pd.Timestamp("2025-12-31")
    assert ref.loc["AAAA3", "data_entrega"] == pd.Timestamp("2026-03-15")
    assert ref.loc["AAAA3", "status"] == OK


# 2D: múltiplos diários (a idade é checada dia a dia, dentro do trecho entre entregas).
def test_multiplos_diarios_pl_e_pvp_saem_no_dia_certo():
    m = multiplos_diarios(DADOS2, CAL, EXCL, P3, desde=date(2026, 3, 31))
    _confere(*_dia(m["pl"], "2026-03-31", "AAAA3"), 5.75, OK)
    _confere(*_dia(m["pl"], "2026-04-01", "AAAA3"), None, IND)
    _confere(*_dia(m["pl"], "2026-04-01", "UUUU11"), 17.142857142857142, OK)
    _confere(*_dia(m["pl"], "2026-04-01", "PREJ3"), -4.0, LN)
    _confere(*_dia(m["pl"], "2026-04-01", "DDDD3"), None, IND)
    _confere(*_dia(m["pvp"], "2026-04-01", "AAAA3"), None, IND)
    _confere(*_dia(m["pvp"], "2026-04-01", "UUUU11"), 2.2222222222222223, OK)
    _confere(*_dia(m["pvp"], "2026-04-01", "PREJ3"), 0.32, OK)


def test_multiplos_diarios_dividend_yield_igual_ao_de_15_meses():
    m3 = multiplos_diarios(DADOS2, CAL, EXCL, P3, desde=date(2026, 3, 31))
    m15 = multiplos_diarios(DADOS2, CAL, EXCL, P15, desde=date(2026, 3, 31))
    pd.testing.assert_frame_equal(m3["dividend_yield"].valor, m15["dividend_yield"].valor)
    pd.testing.assert_frame_equal(m3["dividend_yield"].status, m15["dividend_yield"].status)


def test_multiplos_diarios_com_15_meses_pl_do_abril_segue_ok():
    m15 = multiplos_diarios(DADOS2, CAL, EXCL, P15, desde=date(2026, 3, 31))
    _confere(*_dia(m15["pl"], "2026-04-01", "AAAA3"), 5.75, OK)
