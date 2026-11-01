"""Testes de multiplos_diarios (P/L, P/VP e yield diários; etapa 7, fase 2).

Mundo de tests/fabrica_fundamentos.py (CAL = dias úteis de 2025-01-02 a 2026-04-30) e parâmetros
do parametros.yaml. O oráculo é calcular_fundamentos_no_dia (modo "empresa"), função da etapa 4.
Sem banco e sem rede.
"""

import dataclasses
from datetime import date

import pandas as pd
import pytest

from fabrica_fundamentos import CAL, CNPJ, EXCL, _a, balanco_de, mundo
from processamento.fatos.fundamentos import (
    LUCRO_NEGATIVO,
    DadosFundamentos,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
)
from processamento.fatos.multiplos import multiplos_diarios
from processamento.fatos.precos import HIST, INDISPONIVEL, NAO_SE_APLICA, OK, tickers_do_painel

STATUS_VALIDOS = {OK, NAO_SE_APLICA, INDISPONIVEL, HIST, LUCRO_NEGATIVO}

CADASTRO, BALANCOS, ACOES, PROVENTOS, PRECOS, _CAL, MUDANCAS = mundo()
DADOS = DadosFundamentos(
    precos=PRECOS,
    cadastro=CADASTRO,
    balancos=BALANCOS,
    acoes_emitidas=ACOES,
    proventos=PROVENTOS,
    mudancas=MUDANCAS,
)
PARAMS = carregar_parametros_fundamentos()
TICKERS = tickers_do_painel(CADASTRO, EXCL)

# Datas do oráculo: cortes de entrega de balanço e de janela de 12 meses (ver o plano, 4.4 e 10).
ORACULO_DATAS = [
    "2025-01-02", "2025-03-19", "2025-03-20", "2025-03-31", "2025-04-15", "2025-05-09",
    "2025-05-12", "2025-08-08", "2025-08-11", "2025-11-07", "2025-11-10",
    "2026-03-13", "2026-03-16", "2026-04-10", "2026-04-15", "2026-04-30",
]

# (t, ticker, indicador, valor esperado ou None (NaN), status esperado). Conferido na conta do plano.
VALORES_CONFERIDOS = [
    ("2025-03-31", "AAAA3", "pl", None, HIST),
    ("2025-03-31", "AAAA3", "pvp", None, INDISPONIVEL),
    ("2025-03-31", "AAAA3", "dividend_yield", 0.139, OK),
    ("2025-05-12", "AAAA3", "pl", None, HIST),
    ("2025-05-12", "AAAA3", "pvp", 0.782608695652174, OK),
    ("2025-05-12", "AAAA3", "dividend_yield", 0.129, OK),
    ("2025-08-11", "AAAA3", "pl", 6.206896551724138, OK),
    ("2025-08-11", "AAAA3", "pvp", 0.75, OK),
    ("2025-08-11", "AAAA3", "dividend_yield", 0.129, OK),
    ("2025-08-11", "PREJ3", "pl", None, INDISPONIVEL),
    ("2025-08-11", "UUUU11", "pl", 20.689655172413794, OK),
    ("2025-08-11", "DDDD3", "pl", None, HIST),
    ("2025-11-10", "AAAA3", "pl", 5.625, OK),
    ("2025-11-10", "AAAA3", "pvp", 0.72, OK),
    ("2025-11-10", "AAAA3", "dividend_yield", 0.149, OK),
    ("2025-11-10", "PREJ3", "pl", None, INDISPONIVEL),
    ("2025-11-10", "UUUU11", "pl", 18.75, OK),
    ("2025-11-10", "DDDD3", "pl", None, HIST),
    ("2026-03-16", "AAAA3", "pl", 5.75, OK),
    ("2026-03-16", "AAAA3", "pvp", 0.7076923076923077, OK),
    ("2026-03-16", "AAAA3", "dividend_yield", 0.149, OK),
    ("2026-03-16", "PREJ3", "pl", -5.0, LUCRO_NEGATIVO),
    ("2026-03-16", "UUUU11", "pl", 18.75, OK),
    ("2026-03-16", "DDDD3", "pl", 20.0, OK),
    ("2026-04-15", "AAAA3", "pl", 5.75, OK),
    ("2026-04-15", "AAAA3", "pvp", 0.7076923076923077, OK),
    ("2026-04-15", "AAAA3", "dividend_yield", 0.07, OK),
    ("2026-04-15", "PREJ3", "pl", -5.0, LUCRO_NEGATIVO),
    ("2026-04-15", "UUUU11", "pl", 18.75, OK),
    ("2026-04-15", "DDDD3", "pl", 20.0, OK),
    # Janela de 12 meses (exclusiva no início): o provento de 2025-04-15 sai em 2026-04-15.
    ("2025-04-15", "AAAA3", "dividend_yield", 0.169, OK),
    ("2026-04-10", "AAAA3", "dividend_yield", 0.1, OK),
    # BDR e empresa sem balanço: indisponível.
    ("2025-08-11", "BDRX32", "dividend_yield", None, INDISPONIVEL),
    ("2026-04-15", "BDRX32", "dividend_yield", None, INDISPONIVEL),
    ("2026-04-15", "BDRX32", "pl", None, INDISPONIVEL),
    ("2026-04-15", "BDRX32", "pvp", None, INDISPONIVEL),
    # D9: antes do 1º balanço do BDR também indisponível (antes saía historico_insuficiente).
    ("2025-03-31", "BDRX32", "pl", None, INDISPONIVEL),
    ("2025-03-31", "BDRX32", "pvp", None, INDISPONIVEL),
    ("2025-08-11", "BDRX32", "pl", None, INDISPONIVEL),
    ("2026-04-15", "SEMB3", "pl", None, INDISPONIVEL),
    ("2026-04-15", "NOBA3", "pl", None, INDISPONIVEL),
]


@pytest.fixture(scope="module")
def grades():
    return multiplos_diarios(DADOS, CAL, EXCL, PARAMS)


def _confere(obtido, esperado, onde):
    valor, status = obtido
    valor_esp, status_esp = esperado
    assert status == status_esp, onde
    if valor_esp is None or pd.isna(valor_esp):
        assert pd.isna(valor), onde
    else:
        assert valor == pytest.approx(valor_esp, rel=1e-9), onde


@pytest.mark.parametrize("t", ORACULO_DATAS)
def test_oraculo_igual_a_calcular_fundamentos_no_dia(grades, t):
    ref = calcular_fundamentos_no_dia(t, CAL, DADOS, EXCL, PARAMS, "empresa")
    ts = pd.Timestamp(t)
    mapa = {"pl": "pl.valor", "pvp": "pvp.valor", "dividend_yield": "dividend_yield.valor"}
    for chave, indicador in mapa.items():
        for ticker in TICKERS:
            mio = (grades[chave].valor.loc[ts, ticker], grades[chave].status.loc[ts, ticker])
            ref_valor = (ref[indicador].valor.loc[ts, ticker], ref[indicador].status.loc[ts, ticker])
            _confere(mio, ref_valor, f"{t} {ticker} {chave}")


@pytest.mark.parametrize("t, ticker, indicador, valor, status", VALORES_CONFERIDOS)
def test_valores_conferidos(grades, t, ticker, indicador, valor, status):
    obtido = (grades[indicador].valor.loc[pd.Timestamp(t), ticker],
              grades[indicador].status.loc[pd.Timestamp(t), ticker])
    _confere(obtido, (valor, status), f"{t} {ticker} {indicador}")


def test_point_in_time_nova_entrega_so_muda_depois_dela():
    # ITR entregue em 2026-04-20: não existe em 2026-04-17 e entra a partir de 2026-04-20.
    extra = balanco_de(CNPJ["A"], [_a("ITR", "2026-01-01", "2026-03-31", "2026-04-20", 400, 160, 1000, 9999)])
    dados = dataclasses.replace(DADOS, balancos=pd.concat([BALANCOS, extra], ignore_index=True))
    g = multiplos_diarios(dados, CAL, EXCL, PARAMS)
    antes, depois = pd.Timestamp("2026-04-17"), pd.Timestamp("2026-04-20")

    assert g["pl"].valor.loc[antes, "AAAA3"] == pytest.approx(5.75, rel=1e-9)
    assert g["pvp"].valor.loc[antes, "AAAA3"] == pytest.approx(0.7076923076923077, rel=1e-9)
    assert g["pl"].valor.loc[depois, "AAAA3"] == pytest.approx(920 / 1125, rel=1e-9)
    assert g["pvp"].valor.loc[depois, "AAAA3"] == pytest.approx(920 / 9999, rel=1e-9)


def test_formato_das_grades(grades):
    indice = pd.DatetimeIndex(pd.to_datetime(CAL))
    for chave, g in grades.items():
        assert g.valor.index.equals(indice), chave
        assert list(g.valor.columns) == TICKERS, chave
        assert list(g.status.columns) == TICKERS, chave
        assert set(g.status.stack().unique()) <= STATUS_VALIDOS, chave
        # valor é NaN exatamente onde o status não é ok nem lucro_negativo
        vazio = ~g.status.isin([OK, LUCRO_NEGATIVO])
        assert (g.valor.isna() == vazio).all().all(), chave


def test_desde_so_calcula_os_pregoes_da_janela(grades):
    desde = date(2026, 3, 13)
    g = multiplos_diarios(DADOS, CAL, EXCL, PARAMS, desde=desde)
    indice_esperado = grades["pl"].valor.index[grades["pl"].valor.index >= pd.Timestamp(desde)]

    assert g["pl"].valor.index[0] == pd.Timestamp("2026-03-13")
    for chave in ("pl", "pvp", "dividend_yield"):
        assert g[chave].valor.index.equals(indice_esperado), chave
        pd.testing.assert_frame_equal(g[chave].valor, grades[chave].valor.loc[indice_esperado])
        pd.testing.assert_frame_equal(g[chave].status, grades[chave].status.loc[indice_esperado])

    assert g["pl"].valor.loc[pd.Timestamp("2026-03-13"), "AAAA3"] == pytest.approx(5.625, rel=1e-9)
    assert g["pl"].valor.loc[pd.Timestamp("2026-03-16"), "AAAA3"] == pytest.approx(5.75, rel=1e-9)
    # yield de 2026-03-13 depende de proventos anteriores ao `desde`: a janela usa o histórico todo
    assert g["dividend_yield"].valor.loc[pd.Timestamp("2026-03-13"), "AAAA3"] == pytest.approx(0.149, rel=1e-9)


# Quantidade de ações da AAAA em milhares (seção 10): P/L e P/VP saem indisponíveis pela regra do
# pvp_minimo_plausivel, e o oráculo continua igual ao cálculo do dia.
_ACOES_MIL = ACOES.copy()
_mascara_a = _ACOES_MIL["cnpj"] == CNPJ["A"]
_ACOES_MIL.loc[_mascara_a, ["qtd_on", "qtd_pn"]] = _ACOES_MIL.loc[_mascara_a, ["qtd_on", "qtd_pn"]] / 1000
DADOS_MIL = dataclasses.replace(DADOS, acoes_emitidas=_ACOES_MIL)


@pytest.fixture(scope="module")
def grades_mil():
    return multiplos_diarios(DADOS_MIL, CAL, EXCL, PARAMS)


def test_quantidade_em_milhares_tira_pl_e_pvp_da_empresa(grades_mil):
    t = pd.Timestamp("2026-03-16")
    for ticker in ("AAAA3", "AAAA4"):
        for chave in ("pl", "pvp"):
            assert grades_mil[chave].status.loc[t, ticker] == INDISPONIVEL, (chave, ticker)
            assert pd.isna(grades_mil[chave].valor.loc[t, ticker]), (chave, ticker)


def test_teto_vem_dos_parametros_em_multiplos_diarios():
    # Com teto 0,5 o P/VP × 1000 da AAAA (0,71) passa do teto: não é suspeita, e o P/VP sai ok
    params = dataclasses.replace(PARAMS, pvp_maximo_plausivel_x1000=0.5)
    g = multiplos_diarios(DADOS_MIL, CAL, EXCL, params)
    t = pd.Timestamp("2026-03-16")
    assert g["pvp"].status.loc[t, "AAAA3"] == OK
    assert g["pvp"].valor.loc[t, "AAAA3"] == pytest.approx(0.7076923076923077 / 1000, rel=1e-9)


@pytest.mark.parametrize("t", ORACULO_DATAS)
def test_oraculo_igual_com_quantidade_em_milhares(grades_mil, t):
    ref = calcular_fundamentos_no_dia(t, CAL, DADOS_MIL, EXCL, PARAMS, "empresa")
    ts = pd.Timestamp(t)
    mapa = {"pl": "pl.valor", "pvp": "pvp.valor", "dividend_yield": "dividend_yield.valor"}
    for chave, indicador in mapa.items():
        for ticker in TICKERS:
            mio = (grades_mil[chave].valor.loc[ts, ticker], grades_mil[chave].status.loc[ts, ticker])
            ref_valor = (ref[indicador].valor.loc[ts, ticker], ref[indicador].status.loc[ts, ticker])
            _confere(mio, ref_valor, f"{t} {ticker} {chave}")
