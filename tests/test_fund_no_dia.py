"""Testes de calcular_fundamentos_no_dia, payout_por_ano e balanco_referencia_no_dia (F3b).

Mundo de tests/fabrica_fundamentos.py em T = 2026-03-31, modo de setor "empresa". Valores da
seção F3b do plano da etapa 4, com os ajustes A1 a A3 (média do setor por empresa, P/L do setor
sem lucro negativo e classe do provento pelo ticker original) e a empresa K. Sem banco e sem rede.
"""

import math
from datetime import date

import pandas as pd
import pytest

from fabrica_fundamentos import EXCL, T, mundo
from processamento.fatos.fundamentos import (
    INDICADORES,
    LUCRO_NEGATIVO,
    DadosFundamentos,
    balanco_referencia_no_dia,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
    payout_por_ano,
)
from processamento.fatos.precos import HIST, INDISPONIVEL, NAO_SE_APLICA, OK, resumo_precos_no_dia

STATUS_VALIDOS = {OK, NAO_SE_APLICA, INDISPONIVEL, HIST, LUCRO_NEGATIVO}

CADASTRO, BALANCOS, ACOES, PROVENTOS, PRECOS, CAL, MUDANCAS = mundo()
DADOS = DadosFundamentos(
    precos=PRECOS,
    cadastro=CADASTRO,
    balancos=BALANCOS,
    acoes_emitidas=ACOES,
    proventos=PROVENTOS,
    mudancas=MUDANCAS,
)
PARAMS = carregar_parametros_fundamentos()


@pytest.fixture(scope="module")
def grades():
    return calcular_fundamentos_no_dia(T, CAL, DADOS, EXCL, PARAMS, "empresa")


@pytest.fixture(scope="module")
def resumo(grades):
    return resumo_precos_no_dia(grades, T)


def _celula(resumo, ticker, indicador):
    """(valor, status) de um ticker e indicador no formato longo."""
    linha = resumo[(resumo["ticker"] == ticker) & (resumo["indicador"] == indicador)]
    assert len(linha) == 1
    return float(linha["valor"].iloc[0]), linha["status"].iloc[0]


def _ok(resumo, ticker, indicador, esperado):
    valor, status = _celula(resumo, ticker, indicador)
    assert status == OK
    assert valor == pytest.approx(esperado, rel=1e-9)


def _sem_valor(resumo, ticker, indicador, status):
    valor, st = _celula(resumo, ticker, indicador)
    assert st == status
    assert math.isnan(valor)


def test_chaves_sao_os_indicadores_e_cada_grade_tem_uma_linha(grades):
    assert list(grades) == list(INDICADORES)
    for grade in grades.values():
        assert list(grade.valor.index) == [pd.Timestamp(T)]
        assert set(grade.status.iloc[0]) <= STATUS_VALIDOS


def test_dia_que_nao_e_pregao_levanta_erro():
    with pytest.raises(ValueError):
        calcular_fundamentos_no_dia(date(2026, 3, 28), CAL, DADOS, EXCL, PARAMS, "empresa")


def test_units_e_valor_de_mercado_sao_da_empresa(resumo):
    _ok(resumo, "AAAA3", "pl.valor", 5.75)
    _ok(resumo, "AAAA4", "pl.valor", 5.75)
    _ok(resumo, "AAAA3", "pvp.valor", 920 / 1300)
    _ok(resumo, "AAAA4", "pvp.valor", 920 / 1300)
    _ok(resumo, "UUUU11", "pl.valor", 18.75)
    _ok(resumo, "UUUU11", "pvp.valor", 2.3076923076923075)
    _ok(resumo, "UUUU11", "dividend_yield.valor", 0.08)
    _ok(resumo, "UUUU11", "payout.valor", 1.5)


def test_dupn5_e_exti3(resumo):
    _ok(resumo, "DUPN5", "pl.valor", 15.0)
    _ok(resumo, "DUPN5", "payout.valor", 0.7875)
    _ok(resumo, "EXTI3", "pl.valor", 11.25)
    _ok(resumo, "EXTI3", "payout.valor", 0.85625)


def test_prejuizo_mostra_pl_com_status_lucro_negativo(resumo):
    valor, status = _celula(resumo, "PREJ3", "pl.valor")
    assert status == LUCRO_NEGATIVO
    assert valor == pytest.approx(-5.0, rel=1e-9)
    _sem_valor(resumo, "PREJ3", "payout.valor", LUCRO_NEGATIVO)


def test_banco_sem_margem_e_sozinho_no_setor(resumo):
    _ok(resumo, "BANC4", "pl.valor", 12.5)
    _sem_valor(resumo, "BANC4", "margem_bruta.valor", NAO_SE_APLICA)
    _sem_valor(resumo, "BANC4", "margem_bruta.setor", NAO_SE_APLICA)
    _sem_valor(resumo, "BANC4", "pl.setor", INDISPONIVEL)


def test_sem_balanco_indicadores_indisponiveis_mas_yield_ok(resumo):
    for ticker in ("SEMB3", "NOBA3"):
        for indicador in ("pl.valor", "pvp.valor", "roe.valor", "payout.valor", "margem_bruta.valor",
                          "margem_liquida.valor", "ebitda.valor_12m", "ebitda.margem",
                          "endividamento.divida_liquida"):
            _sem_valor(resumo, ticker, indicador, INDISPONIVEL)
    _ok(resumo, "SEMB3", "dividend_yield.valor", 0.05)
    _ok(resumo, "NOBA3", "dividend_yield.valor", 0.0)


def test_ebitda_e_divida_so_quando_ha_dados(resumo):
    _ok(resumo, "DDDD3", "ebitda.valor_12m", 111.0)
    _sem_valor(resumo, "AAAA3", "ebitda.valor_12m", INDISPONIVEL)
    _sem_valor(resumo, "AAAA3", "endividamento.divida_liquida", INDISPONIVEL)


def test_bdr_fica_sem_pl_pvp_yield_e_payout(resumo):
    _sem_valor(resumo, "BDRX32", "pl.valor", INDISPONIVEL)
    _sem_valor(resumo, "BDRX32", "pvp.valor", INDISPONIVEL)
    _sem_valor(resumo, "BDRX32", "dividend_yield.valor", INDISPONIVEL)
    _sem_valor(resumo, "BDRX32", "payout.valor", INDISPONIVEL)
    _ok(resumo, "BDRX32", "roe.valor", 0.08333333333333333)
    _ok(resumo, "BDRX32", "margem_bruta.valor", 0.40476190476190477)


def test_setor_pl_media_por_empresa(resumo):
    _ok(resumo, "AAAA3", "pl.setor", 18.75)
    _ok(resumo, "AAAA4", "pl.setor", 18.75)
    _ok(resumo, "UUUU11", "pl.setor", 5.75)
    _ok(resumo, "PREJ3", "pl.setor", 12.25)


def test_setor_pvp_yield_e_payout(resumo):
    _ok(resumo, "AAAA3", "pvp.setor", 1.3076923076923075)
    _ok(resumo, "PREJ3", "pvp.setor", 1.5076923076923077)
    _ok(resumo, "AAAA3", "dividend_yield.setor", 0.0525)
    _ok(resumo, "UUUU11", "dividend_yield.setor", 0.0421875)
    _ok(resumo, "AAAA3", "payout.setor", 1.5)


def test_setor_s5_s3_s4(resumo):
    _ok(resumo, "DUPN5", "pl.setor", 11.25)
    _ok(resumo, "EXTI3", "pl.setor", 15.0)
    _sem_valor(resumo, "SEMB3", "pl.setor", INDISPONIVEL)
    _sem_valor(resumo, "DDDD3", "margem_bruta.setor", INDISPONIVEL)


def test_empresa_k_com_troca_de_ticker(resumo):
    _ok(resumo, "KKKK3", "dividend_yield.valor", 0.013)
    _ok(resumo, "KKKK3", "payout.valor", 0.31875)
    _ok(resumo, "KKKK3", "pl.valor", 18.75)
    _sem_valor(resumo, "KKKK3", "pl.setor", INDISPONIVEL)


def test_payout_por_ano_em_t():
    linhas = payout_por_ano(T, DADOS, EXCL, PARAMS)
    aaaa3 = linhas[linhas["ticker"] == "AAAA3"]
    assert len(aaaa3) == 2
    por_ano = {r.ano: (r.valor, r.status) for r in aaaa3.itertuples()}
    assert por_ano[2024][0] == pytest.approx(0.3230769230769231, rel=1e-9)
    assert por_ano[2024][1] == OK
    assert por_ano[2025][0] == pytest.approx(0.6375, rel=1e-9)
    assert por_ano[2025][1] == OK


def test_payout_por_ano_so_dfp_entregue_ate_t():
    linhas = payout_por_ano(date(2026, 3, 10), DADOS, EXCL, PARAMS)
    aaaa3 = linhas[linhas["ticker"] == "AAAA3"]
    assert list(aaaa3["ano"]) == [2024]


def test_payout_por_ano_prejuizo_e_sem_linhas_sem_empresa_ou_so_bdr():
    linhas = payout_por_ano(T, DADOS, EXCL, PARAMS)
    prej = linhas[linhas["ticker"] == "PREJ3"].set_index("ano")
    assert list(prej.index) == [2024, 2025]
    for ano in (2024, 2025):
        assert math.isnan(prej.loc[ano, "valor"])
        assert prej.loc[ano, "status"] == LUCRO_NEGATIVO
    assert "SEMB3" not in set(linhas["ticker"])
    assert "BDRX32" not in set(linhas["ticker"])


def test_balanco_referencia_no_dia():
    ref = balanco_referencia_no_dia(T, DADOS, EXCL).set_index("ticker")
    assert ref.loc["AAAA3", "data_fim_periodo"] == pd.Timestamp("2025-12-31")
    assert ref.loc["AAAA3", "data_entrega"] == pd.Timestamp("2026-03-15")
    assert ref.loc["AAAA3", "status"] == OK
    assert pd.isna(ref.loc["SEMB3", "data_fim_periodo"])
    assert pd.isna(ref.loc["SEMB3", "data_entrega"])
    assert ref.loc["SEMB3", "status"] == INDISPONIVEL


def test_balanco_referencia_nao_usa_dado_entregue_depois_de_t():
    """Em 2026-03-10 a DFP 2025 (entregue em 2026-03-15) ainda não existe: vale o ITR de 9 meses."""
    ref = balanco_referencia_no_dia(date(2026, 3, 10), DADOS, EXCL).set_index("ticker")
    assert ref.loc["AAAA3", "data_fim_periodo"] == pd.Timestamp("2025-09-30")
    assert ref.loc["AAAA3", "data_entrega"] == pd.Timestamp("2025-11-10")
