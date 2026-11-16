"""Testes do emissor por período e da quantidade na base atual nas contas (T5, 03/11/2026).

Cobre `acoes_disponiveis` (D4 pela `data_entrega`), `acoes_na_data` (`qtd_*_base_atual`, `anulado`),
`ligar_proventos` com `emissores`, `total_pago`, `calcular_fundamentos_no_dia` e `multiplos_diarios`
com a JBS (JBSS32) e a HAPV3. Gabaritos do plano (seção T5). Sem banco e sem rede.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from fabrica_emissores import (
    ACOES_HAPV3,
    ACOES_HAPV3_LINHAS,
    ACOES_MGLU3,
    CNPJ_HAPV3,
    CNPJ_JBS_NV,
    CNPJ_JBS_SA,
    CNPJ_MGLU3,
    EMISSORES_REAIS,
    acoes_base_de,
)
from fabrica_fundamentos import _a, acoes_de, balanco_de, cadastro_fund_de, proventos_de
from fabrica_precos import precos_de
from processamento.exclusoes import Exclusoes
from processamento.fatos.fundamentos import (
    DadosFundamentos,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
    valor_de_mercado,
)
from processamento.fatos.multiplos import multiplos_diarios
from processamento.fatos.precos import INDISPONIVEL, OK
from processamento.fatos.proventos import acoes_disponiveis, acoes_na_data, ligar_proventos, total_pago

PARAMS = carregar_parametros_fundamentos()
SEM_BALANCOS = pd.DataFrame()


def _disp(acoes: pd.DataFrame, t: str) -> pd.DataFrame:
    return acoes_disponiveis(acoes, SEM_BALANCOS, t)


def _cal(inicio: str, fim: str) -> list:
    return [d.date() for d in pd.bdate_range(inicio, fim)]


# ---------------------------------------------------------------------------
# 1. D4 pela data_entrega da própria linha (HAPV3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t, data, qtd_on", [
    ("2024-05-10", "2024-05-10", 476158554.0),
    ("2024-05-13", "2024-05-13", 502630884.0),
    ("2024-06-28", "2023-06-30", 476158554.0),
    ("2024-11-28", "2023-06-30", 476158554.0),
    ("2024-11-29", "2023-06-30", 476283723.0),
])
def test_d4_pela_entrega_da_propria_linha(t, data, qtd_on):
    assert acoes_na_data(_disp(ACOES_HAPV3, t), CNPJ_HAPV3, data) == (qtd_on, 0.0, OK)


# ---------------------------------------------------------------------------
# 2. Valor de mercado com a quantidade na base atual
# ---------------------------------------------------------------------------

def _vm(cnpj: str, ticker: str, preco: float, t: str, acoes: pd.DataFrame, data: str | None = None):
    cadastro = cadastro_fund_de([(ticker, cnpj, "S", "X", "ON", None, None)])
    qtd = acoes_na_data(_disp(acoes, t), cnpj, data or t)
    return valor_de_mercado(cnpj, {ticker: preco}, cadastro, [ticker], qtd)


@pytest.mark.parametrize("t, preco, esperado", [
    ("2021-07-16", 230.399994, 57061316171.62818),
    ("2021-12-30", 155.699997, 40394493174.78605),
    ("2026-10-30", 4.20, 2111049712.8000002),
])
def test_valor_de_mercado_hapv3(t, preco, esperado):
    valor, status = _vm(CNPJ_HAPV3, "HAPV3", preco, t, ACOES_HAPV3)
    assert status == OK
    assert valor == pytest.approx(esperado, rel=1e-12)


@pytest.mark.parametrize("t, preco, esperado", [
    ("2021-07-16", 212.8974, 145278486008.07062),
    ("2024-06-28", 11.476190, 8904892375.78809),
])
def test_valor_de_mercado_mglu3(t, preco, esperado):
    valor, status = _vm(CNPJ_MGLU3, "MGLU3", preco, t, ACOES_MGLU3)
    assert status == OK
    assert valor == pytest.approx(esperado, rel=1e-12)


def test_mglu3_em_2024_08_09_usa_a_base_atual():
    assert acoes_na_data(_disp(ACOES_MGLU3, "2024-08-09"), CNPJ_MGLU3, "2024-08-09")[0] == 775945010.0


# ---------------------------------------------------------------------------
# 3. anulado: a linha escolhida sem base atual dá indisponível (não volta para a anterior)
# ---------------------------------------------------------------------------

def test_anulado_dá_quantidade_indisponivel():
    linhas = ACOES_HAPV3_LINHAS + [(CNPJ_HAPV3, "2021-09-30", "2021-11-10", 3891569750, 0, None, None, "anulado")]
    acoes = acoes_base_de(linhas)
    qtd_on, qtd_pn, status = acoes_na_data(_disp(acoes, "2021-12-30"), CNPJ_HAPV3, "2021-12-30")
    assert status == INDISPONIVEL
    assert math.isnan(qtd_on) and math.isnan(qtd_pn)


# suspeito (16/11/2026): base preenchida, mas indisponível só no período dele, como o anulado
_LINHAS_SUSPEITO = ACOES_HAPV3_LINHAS + [
    (CNPJ_HAPV3, "2021-09-30", "2021-11-10", 3891569750, 0, 259437983, 0, "suspeito"),
]


def test_suspeito_dá_quantidade_indisponivel_mesmo_com_base_preenchida():
    acoes = acoes_base_de(_LINHAS_SUSPEITO)
    qtd_on, qtd_pn, status = acoes_na_data(_disp(acoes, "2021-12-30"), CNPJ_HAPV3, "2021-12-30")
    assert status == INDISPONIVEL   # não volta para a linha ok de 2021-06-30
    assert math.isnan(qtd_on) and math.isnan(qtd_pn)


@pytest.mark.parametrize("t, data, esperado", [
    ("2021-11-09", "2021-11-09", (259437983.0, 0.0, OK)),   # antes da entrega do suspeito: vale a anterior
    ("2022-06-30", "2022-06-30", (476158554.0, 0.0, OK)),   # linha seguinte entregue: volta a valer
])
def test_suspeito_vale_so_no_proprio_periodo(t, data, esperado):
    assert acoes_na_data(_disp(acoes_base_de(_LINHAS_SUSPEITO), t), CNPJ_HAPV3, data) == esperado


def test_suspeito_no_valor_de_mercado_fica_indisponivel():
    valor, status = _vm(CNPJ_HAPV3, "HAPV3", 155.699997, "2021-12-30", acoes_base_de(_LINHAS_SUSPEITO))
    assert status == INDISPONIVEL and math.isnan(valor)


# ---------------------------------------------------------------------------
# 4. Payout sintético HAPV3 com a quantidade na base atual
# ---------------------------------------------------------------------------

def test_payout_sintetico_hapv3_usa_base_atual():
    prov = proventos_de([
        ("HAPV3", "DIVIDENDO", "2021-06-15", 0.15, None),
        ("HAPV3", "JCP", "2021-09-15", 0.20, None),
    ])
    cad = cadastro_fund_de([("HAPV3", CNPJ_HAPV3, "Saude", "Hospitais", "ON", None, None)])
    ligados = ligar_proventos(prov, cad, {})
    assert total_pago(ligados, _disp(ACOES_HAPV3, "2021-12-30"), CNPJ_HAPV3,
                      "2020-12-30", "2021-12-30") == pytest.approx((89036891.95, OK), rel=1e-12)
    assert total_pago(ligados, _disp(ACOES_HAPV3, "2021-08-10"), CNPJ_HAPV3,
                      "2020-08-10", "2021-08-10") == pytest.approx((37149295.35, OK), rel=1e-12)


# ---------------------------------------------------------------------------
# 5. JBS: ligação de proventos por data e payout com o CNPJ da JBS S.A.
# ---------------------------------------------------------------------------

def _prov_jbs(com_2026: bool = True) -> pd.DataFrame:
    linhas = [
        ("JBSS32", "DIVIDENDO", "2024-08-19", 4.0, None),
        ("JBSS32", "DIVIDENDO", "2024-11-22", 2.0, None),
        ("JBSS32", "DIVIDENDO", "2025-04-29", 4.0, None),
        ("JBSS32", "DIVIDENDO", "2025-05-23", 2.0, None),
    ]
    if com_2026:
        linhas.append(("JBSS32", "DIVIDENDO", "2026-05-18", 4.276358, None))
    return proventos_de(linhas)


def _cad_jbs() -> pd.DataFrame:
    return cadastro_fund_de([("JBSS32", CNPJ_JBS_NV, "Alimentos", "Carnes", "BDR", None, None)])


def _acoes_jbs() -> pd.DataFrame:
    return acoes_base_de([(CNPJ_JBS_SA, "2024-12-31", "2025-03-26", 2218116370, 0, 1109058185, 0, "ok")])


def test_ligacao_jbs_por_data_do_provento():
    lig = ligar_proventos(_prov_jbs(), _cad_jbs(), {}, EMISSORES_REAIS)
    antes = lig[lig["data_com"] == pd.Timestamp("2025-05-23")].iloc[0]
    assert antes["cnpj"] == CNPJ_JBS_SA
    assert antes["tipo_classe"] == "ON"
    assert antes["ligacao"] == "emissor"
    depois = lig[lig["data_com"] == pd.Timestamp("2026-05-18")].iloc[0]
    assert depois["cnpj"] == CNPJ_JBS_NV
    assert depois["tipo_classe"] == "BDR"
    assert depois["ligacao"] == "emissor"


def test_total_pago_jbs_com_emissor():
    lig = ligar_proventos(_prov_jbs(), _cad_jbs(), {}, EMISSORES_REAIS)
    disp = acoes_disponiveis(_acoes_jbs(), SEM_BALANCOS, "2025-06-06")
    assert total_pago(lig, disp, CNPJ_JBS_SA, "2024-06-08", "2025-06-08") == pytest.approx(
        (13308698220.0, OK), rel=1e-12)


def test_total_pago_jbs_sem_emissores_nao_acha_proventos():
    lig = ligar_proventos(_prov_jbs(), _cad_jbs(), {})
    disp = acoes_disponiveis(_acoes_jbs(), SEM_BALANCOS, "2025-06-06")
    assert total_pago(lig, disp, CNPJ_JBS_SA, "2024-06-08", "2025-06-08") == (0.0, OK)


# ---------------------------------------------------------------------------
# 6. calcular_fundamentos_no_dia com a JBS: ON até 08/06/2025, BDR depois
# ---------------------------------------------------------------------------

CAL_JBS = _cal("2025-06-02", "2025-06-13")


def _dados_jbs(emissores) -> DadosFundamentos:
    return DadosFundamentos(
        precos=precos_de("JBSS32", CAL_JBS, [78.06] * len(CAL_JBS)),
        cadastro=_cad_jbs(),
        balancos=balanco_de(CNPJ_JBS_SA, [_a("ITR", "2025-01-01", "2025-03-31", "2025-05-14",
                                             1000, 300, 100, 1e10)]),
        acoes_emitidas=_acoes_jbs(),
        proventos=_prov_jbs(com_2026=False),
        mudancas={},
        emissores=emissores,
    )


def _no_dia(dados: DadosFundamentos, dia: str) -> dict:
    return calcular_fundamentos_no_dia(pd.Timestamp(dia).date(), CAL_JBS, dados, Exclusoes(), PARAMS, "empresa")


def _celula(grades: dict, indicador: str, dia: str, ticker: str = "JBSS32") -> tuple:
    g = grades[indicador]
    return g.valor.loc[pd.Timestamp(dia), ticker], g.status.loc[pd.Timestamp(dia), ticker]


def test_fundamentos_jbs_on_ate_08_06_e_bdr_depois():
    dados = _dados_jbs(EMISSORES_REAIS)
    g = _no_dia(dados, "2025-06-06")
    valor, status = _celula(g, "pvp.valor", "2025-06-06")
    assert status == OK and valor == pytest.approx(8.657308192110001, rel=1e-12)
    valor, status = _celula(g, "dividend_yield.valor", "2025-06-06")
    assert status == OK and valor == pytest.approx(0.15372790161414296, rel=1e-12)
    assert _celula(g, "pl.valor", "2025-06-06")[1] == "historico_insuficiente"

    g = _no_dia(dados, "2025-06-09")
    assert _celula(g, "pvp.valor", "2025-06-09")[1] == INDISPONIVEL
    assert _celula(g, "dividend_yield.valor", "2025-06-09")[1] == INDISPONIVEL


def test_fundamentos_jbs_sem_emissores_pvp_indisponivel():
    g = _no_dia(_dados_jbs(None), "2025-06-06")
    assert _celula(g, "pvp.valor", "2025-06-06")[1] == INDISPONIVEL


# ---------------------------------------------------------------------------
# 7. multiplos_diarios: JBS (trechos pelo emissor) e HAPV3 (trechos pelas entregas de ações)
# ---------------------------------------------------------------------------

def test_multiplos_diarios_jbs_troca_de_emissor():
    grades = multiplos_diarios(_dados_jbs(EMISSORES_REAIS), CAL_JBS, Exclusoes(), PARAMS)
    assert _celula(grades, "pvp", "2025-06-06")[1] == OK
    assert _celula(grades, "pvp", "2025-06-06")[0] == pytest.approx(8.657308192110001, rel=1e-12)
    assert _celula(grades, "pvp", "2025-06-09")[1] == INDISPONIVEL
    valor, status = _celula(grades, "dividend_yield", "2025-06-06")
    assert status == OK and valor == pytest.approx(0.15372790161414296, rel=1e-12)
    assert _celula(grades, "dividend_yield", "2025-06-09")[1] == INDISPONIVEL


def _dados_hapv3() -> DadosFundamentos:
    cad = cadastro_fund_de([("HAPV3", CNPJ_HAPV3, "Saude", "Hospitais", "ON", None, None)])
    cal = _cal("2021-05-03", "2021-08-31")
    return DadosFundamentos(
        precos=precos_de("HAPV3", cal, [230.399994] * len(cal)),
        cadastro=cad,
        balancos=balanco_de(CNPJ_HAPV3, [_a("ITR", "2021-01-01", "2021-03-31", "2021-05-12",
                                             1000, 300, 100, 1e10)]),
        acoes_emitidas=ACOES_HAPV3,
        proventos=proventos_de([]),
        mudancas={},
    )


def test_multiplos_diarios_hapv3_recalcula_na_entrega_de_acoes():
    grades = multiplos_diarios(_dados_hapv3(), _cal("2021-05-03", "2021-08-31"), Exclusoes(), PARAMS)
    for dia in ("2021-05-12", "2021-07-16", "2021-08-10"):
        valor, status = _celula(grades, "pvp", dia, "HAPV3")
        assert status == OK and valor == pytest.approx(5.706131617162818, rel=1e-12), dia
    for dia in ("2021-08-11", "2021-08-31"):
        valor, status = _celula(grades, "pvp", dia, "HAPV3")
        assert status == OK and valor == pytest.approx(5.97745097265721, rel=1e-12), dia
    assert _celula(grades, "pl", "2021-07-16", "HAPV3")[1] == "historico_insuficiente"
    valor, status = _celula(grades, "dividend_yield", "2021-07-16", "HAPV3")
    assert status == OK and valor == 0.0
