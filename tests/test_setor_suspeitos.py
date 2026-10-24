"""Rentabilidade do setor (DS11), medianas de nível sem a empresa suspeita (DS5) e ligação no pacote (Fase 4).

Casos 4a a 4d do plano docs/plano_suspeitos_setor.md. Sem banco real e sem rede (banco_teste do conftest).
"""

import math
from dataclasses import replace

import pandas as pd
import pytest

from fabrica_fundamentos import EXCL, T, mundo
from fabrica_precos import cadastro_de, precos_de, pregoes_uteis, serie_por_retornos
from fabrica_saida import insumos_de_teste
from processamento.exclusoes import Exclusoes
from processamento.fatos.fundamentos import (
    DadosFundamentos,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
)
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    calcular_precos,
    carregar_parametros_precos,
    grade_de_precos,
    pares_do_painel,
    resumo_precos_no_dia,
    retornos_suspeitos,
    tickers_do_painel,
)
from processamento.fatos.series import rentabilidade_setor_sem_empresa
from processamento.saida import pacotes_fatos


def _perto(obtido, esperado):
    """Compara uma série de valores: None/NaN esperado vira NaN obtido."""
    assert len(obtido) == len(esperado)
    for o, e in zip(obtido, esperado):
        if e is None or (isinstance(e, float) and math.isnan(e)):
            assert math.isnan(o)
        else:
            assert o == pytest.approx(e)


# ---------------------------------------------------------------- 4a e 4b: rentabilidade do setor

CAL = pregoes_uteis(8, "2026-04-06")   # 06, 07, 08, 09, 10, 13, 14 e 15/04/2026
PRECOS = pd.concat([
    precos_de("IBOV", CAL, [10.0] * 8),
    precos_de("AZUL3", CAL, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105]),
    precos_de("EMBR3", CAL, serie_por_retornos(50.0, [0.02, -0.01, 0.02, -0.01, 0.01, 0.0, 0.01])),
    precos_de("WEGE3", CAL, serie_por_retornos(40.0, [0.0, 0.01, -0.02, 0.03, 0.0, 0.01, -0.01])),
    precos_de("RAIL3", CAL, serie_por_retornos(20.0, [0.03, 0.0, -0.01, 0.02, 0.01, -0.02, 0.0])),
    precos_de("SOLO3", CAL, [10.0] * 8),
])
CADASTRO = cadastro_de([("AZUL3", "1", "BI", "ON"), ("EMBR3", "2", "BI", "ON"), ("WEGE3", "3", "BI", "ON"),
                        ("RAIL3", "4", "BI", "ON"), ("SOLO3", "5", "Y", "ON"), ("NOPX3", "6", "Y", "ON")])
PARAMS = replace(carregar_parametros_precos(), janelas={"d1": 1, "m1": 3, "m6": 5})
TICKERS = tickers_do_painel(CADASTRO, Exclusoes())
PARES = pares_do_painel(CADASTRO, Exclusoes())
G_AJ = grade_de_precos(PRECOS, CAL, "fechamento_ajustado", TICKERS)
SUSPEITOS = retornos_suspeitos(G_AJ, -0.75, 1.0)
RES = calcular_precos(PRECOS, CADASTRO, CAL, Exclusoes(), PARAMS)


def test_4a_rentabilidade_setor_da_embr3_vem_da_serie_sem_a_propria():
    # Valores do caso 2c da Fase 2 (mesmo cenário, mesmas janelas).
    d1 = RES["rentabilidade.setor.d1"]
    m1 = RES["rentabilidade.setor.m1"]
    m6 = RES["rentabilidade.setor.m6"]
    _perto(d1.valor["EMBR3"].tolist(), [math.nan, 0.016666666666666607, 0.004999999999999893,
                                        0.006666666666666599, 0.02499999999999991, 0.0033333333333334103,
                                        0.0, 0.0])
    assert d1.status["EMBR3"].tolist() == [HIST] + [OK] * 7
    _perto(m1.valor["EMBR3"].tolist(), [math.nan, math.nan, math.nan, 0.028561666666666374,
                                        0.03699249999999976, 0.03527277777777771, 0.028416666666666757,
                                        0.0033333333333334103])
    assert m1.status["EMBR3"].tolist() == [HIST] * 3 + [OK] * 5
    _perto(m6.valor["EMBR3"].tolist(), [math.nan] * 5 + [0.05778996069444409, 0.04044914166666658,
                                                         0.03527277777777771])
    assert m6.status["EMBR3"].tolist() == [HIST] * 5 + [OK] * 3
    # SOLO3 não tem outra empresa com preço (NOPX3 nunca tem): histórico insuficiente no último dia.
    assert RES["rentabilidade.setor.d1"].status["SOLO3"].iloc[-1] == HIST
    # NOPX3 segue a série da SOLO3 (único outro do setor Y): ok no último dia.
    assert RES["rentabilidade.setor.d1"].status["NOPX3"].iloc[-1] == OK


def test_4a_rentabilidade_da_propria_acao_nao_muda():
    # DS6: o valor da própria ação segue com o preço como veio.
    assert RES["rentabilidade.d1"].valor["AZUL3"].loc["2026-04-08"] == pytest.approx(19999.0)
    assert RES["rentabilidade.d1"].status["AZUL3"].loc["2026-04-08"] == OK
    assert RES["rentabilidade.m1"].valor["AZUL3"].loc["2026-04-09"] == pytest.approx(21419.0)
    assert RES["rentabilidade.m1"].status["AZUL3"].loc["2026-04-09"] == OK


def test_4b_rentabilidade_setor_bate_com_o_nucleo_da_serie():
    esperado = rentabilidade_setor_sem_empresa(G_AJ, CADASTRO, PARES, TICKERS, PARAMS.janelas, "empresa",
                                               suspeitos=SUSPEITOS)
    for janela in PARAMS.janelas:
        obtido = RES[f"rentabilidade.setor.{janela}"]
        pd.testing.assert_frame_equal(obtido.valor, esperado[janela].valor, check_names=False)
        pd.testing.assert_frame_equal(obtido.status, esperado[janela].status, check_names=False)


# ---------------------------------------------------------------- 4c: medianas de nível (DS5)

CAD_F, BAL_F, ACOES_F, PROV_F, PRECOS_F, CAL_F, MUDANCAS_F = mundo()
DADOS = DadosFundamentos(
    precos=PRECOS_F,
    cadastro=CAD_F,
    balancos=BAL_F,
    acoes_emitidas=ACOES_F,
    proventos=PROV_F,
    mudancas=MUDANCAS_F,
)
PARAMS_FUND = carregar_parametros_fundamentos()


def _celula(resumo, ticker, indicador):
    """(valor, status) de um ticker e indicador no formato longo."""
    linha = resumo[(resumo["ticker"] == ticker) & (resumo["indicador"] == indicador)]
    assert len(linha) == 1
    return float(linha["valor"].iloc[0]), linha["status"].iloc[0]


@pytest.fixture(scope="module")
def resumo_com_saida():
    grades = calcular_fundamentos_no_dia(T, CAL_F, DADOS, EXCL, PARAMS_FUND, "empresa",
                                         fora_do_setor_preco=frozenset({"AAAA4"}))
    return resumo_precos_no_dia(grades, T)


@pytest.mark.parametrize("ticker, indicador, valor_esperado, status_esperado", [
    ("UUUU11", "pl.setor", math.nan, INDISPONIVEL),
    ("PREJ3", "pl.setor", 18.75, OK),
    ("UUUU11", "pvp.setor", 0.3076923076923077, OK),
    ("PREJ3", "pvp.setor", 2.3076923076923075, OK),
    ("UUUU11", "dividend_yield.setor", 0.025, OK),
    ("PREJ3", "dividend_yield.setor", 0.08, OK),
    ("UUUU11", "roe.setor", 0.03076923076923077, OK),
    ("PREJ3", "roe.setor", 0.12307692307692308, OK),
    ("UUUU11", "payout.setor", 0.328125, OK),
    ("PREJ3", "payout.setor", 0.9140625, OK),
    ("AAAA3", "pl.valor", 5.75, OK),
    ("AAAA4", "pvp.valor", 0.7076923076923077, OK),
    ("AAAA4", "dividend_yield.valor", 0.06875, OK),
    ("AAAA3", "pl.setor", 18.75, OK),
    ("AAAA3", "pvp.setor", 1.3076923076923075, OK),
])
def test_4c_medianas_de_nivel_sem_a_empresa_suspeita(resumo_com_saida, ticker, indicador, valor_esperado,
                                                     status_esperado):
    valor, status = _celula(resumo_com_saida, ticker, indicador)
    assert status == status_esperado
    if math.isnan(valor_esperado):
        assert math.isnan(valor)
    else:
        assert valor == pytest.approx(valor_esperado)


# ---------------------------------------------------------------- 4d: ligação no calcular_grades

def _salto_petr4(df: pd.DataFrame) -> pd.DataFrame:
    """PETR4 com fechamento_ajustado 1.000.000 em 2025-10-20 (leitor de texto do banco_teste)."""
    df = df.copy()
    m = (df["ticker"] == "PETR4") & (df["data"] == "2025-10-20")
    df.loc[m, "fechamento_ajustado"] = "1000000.0"
    return df


def test_4d_calcular_grades_passa_a_empresa_suspeita_ao_fundamentos(banco_teste, monkeypatch):
    capturados = {}
    original = pacotes_fatos.calcular_fundamentos_no_dia

    def espiao(*args, **kwargs):
        capturados.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(pacotes_fatos, "calcular_fundamentos_no_dia", espiao)
    params_p = carregar_parametros_precos()
    params_f = carregar_parametros_fundamentos()

    ins = insumos_de_teste(banco_teste({"v1-precos": _salto_petr4}))
    pacotes_fatos.calcular_grades(ins, params_p, params_f)
    assert capturados["fora_do_setor_preco"] == frozenset({"PETR4"})

    ins_sem = insumos_de_teste(banco_teste())
    pacotes_fatos.calcular_grades(ins_sem, params_p, params_f)
    assert capturados["fora_do_setor_preco"] == frozenset()
