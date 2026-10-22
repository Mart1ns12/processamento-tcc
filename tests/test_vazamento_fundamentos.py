"""Caso (j) da etapa 4: nada depois de t pode mudar o que os fundamentos calculam em t.

Dois cenários (como em tests/test_vazamento_fatos.py): "cortado" (só dados até t e calendário até t)
e "cheio e alterado" (todos os dados, com o que é posterior a t multiplicado e um provento novo
depois de t). Os resultados em t têm de ser idênticos: indicadores no dia, payout por ano, balanço
de referência e tabela trimestral. Nenhum teste usa banco ou rede.
"""

import math
from datetime import date

import pandas as pd
import pytest

from fabrica_fundamentos import EXCL, mundo
from processamento.fatos.fundamentos import (
    DadosFundamentos,
    balanco_referencia_no_dia,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
    payout_por_ano,
    tabela_trimestral,
)
from processamento.fatos.precos import OK, resumo_precos_no_dia

CADASTRO, BALANCOS, ACOES, PROVENTOS, PRECOS, CAL_MUNDO, MUDANCAS = mundo()
PARAMS = carregar_parametros_fundamentos()

T = date(2025, 12, 15)
T2 = date(2026, 3, 31)
MULT = 3

NUMERICAS_BALANCO = [
    "receita_liquida", "lucro_bruto", "lucro_liquido", "patrimonio_liquido", "ebit",
    "depreciacao_amortizacao", "emprestimos_curto_prazo", "emprestimos_longo_prazo",
    "caixa", "aplicacoes_financeiras",
]

DADOS_ORIGINAL = DadosFundamentos(
    precos=PRECOS,
    cadastro=CADASTRO,
    balancos=BALANCOS,
    acoes_emitidas=ACOES,
    proventos=PROVENTOS,
    mudancas=MUDANCAS,
)


def _cortado(t):
    """Só dados até t (inclusive) e calendário até t. Ações ficam inteiras: a função filtra."""
    corte = pd.Timestamp(t)
    cal_c = [d for d in CAL_MUNDO if d <= t]
    dados = DadosFundamentos(
        precos=PRECOS[PRECOS["data"] <= corte],
        cadastro=CADASTRO,
        balancos=BALANCOS[BALANCOS["data_entrega"] <= corte],
        acoes_emitidas=ACOES,
        proventos=PROVENTOS[PROVENTOS["data_com"] <= corte],
        mudancas=MUDANCAS,
    )
    return cal_c, dados


def _alterado(t):
    """Todos os dados, com o posterior a t alterado.

    - balanços entregues depois de t: colunas numéricas x3;
    - ações cujo data_referencia não tem balanço entregue até t: qtd x3 (o 2025-03-31 fica);
    - proventos com data_com depois de t: valor x3 (inclui KKKK3 de 2026-01-20), mais uma linha
      nova AAAA3 JCP 2026-01-05 9.9;
    - preços com data depois de t: fechamento x3.
    """
    corte = pd.Timestamp(t)

    balancos = BALANCOS.copy()
    depois_entrega = balancos["data_entrega"] > corte
    balancos.loc[depois_entrega, NUMERICAS_BALANCO] = (
        balancos.loc[depois_entrega, NUMERICAS_BALANCO] * MULT
    )

    acoes = ACOES.copy()
    entregues = BALANCOS.loc[BALANCOS["data_entrega"] <= corte, ["cnpj", "data_fim_periodo"]]
    com_balanco_ate_t = set(zip(entregues["cnpj"], entregues["data_fim_periodo"]))
    sem_balanco_ate_t = pd.Series(
        [(c, d) not in com_balanco_ate_t for c, d in zip(acoes["cnpj"], acoes["data_referencia"])],
        index=acoes.index,
    )
    acoes.loc[sem_balanco_ate_t, ["qtd_on", "qtd_pn"]] = (
        acoes.loc[sem_balanco_ate_t, ["qtd_on", "qtd_pn"]] * MULT
    )

    proventos = PROVENTOS.copy()
    depois_com = proventos["data_com"] > corte
    proventos.loc[depois_com, "valor_por_acao"] = proventos.loc[depois_com, "valor_por_acao"] * MULT
    novo = pd.DataFrame({
        "ticker": ["AAAA3"],
        "tipo": ["JCP"],
        "data_com": [pd.Timestamp("2026-01-05")],
        "valor_por_acao": [9.9],
        "data_pagamento": [pd.NaT],
    })
    proventos = pd.concat([proventos, novo], ignore_index=True)

    precos = PRECOS.copy()
    depois_preco = precos["data"] > corte
    precos.loc[depois_preco, "fechamento"] = precos.loc[depois_preco, "fechamento"] * MULT

    dados = DadosFundamentos(
        precos=precos,
        cadastro=CADASTRO,
        balancos=balancos,
        acoes_emitidas=acoes,
        proventos=proventos,
        mudancas=MUDANCAS,
    )
    return CAL_MUNDO, dados


def _quatro_saidas(cal, dados, t):
    """Resultados em t das quatro funções que a etapa 4 expõe ao painel."""
    grades = calcular_fundamentos_no_dia(t, cal, dados, EXCL, PARAMS, "empresa")
    return {
        "resumo": resumo_precos_no_dia(grades, t),
        "payout": payout_por_ano(t, dados, EXCL, PARAMS),
        "referencia": balanco_referencia_no_dia(t, dados, EXCL),
        "tabela": tabela_trimestral(t, dados, EXCL, PARAMS),
    }


def _celula(resumo, ticker, indicador):
    """(valor, status) de um ticker e indicador no formato longo."""
    linha = resumo[(resumo["ticker"] == ticker) & (resumo["indicador"] == indicador)]
    assert len(linha) == 1
    return float(linha["valor"].iloc[0]), linha["status"].iloc[0]


def test_cortado_e_cheio_alterado_dao_o_mesmo_resultado_em_t():
    cal_c, dados_c = _cortado(T)
    cal_a, dados_a = _alterado(T)

    saidas_c = _quatro_saidas(cal_c, dados_c, T)
    saidas_a = _quatro_saidas(cal_a, dados_a, T)

    pd.testing.assert_frame_equal(saidas_c["resumo"], saidas_a["resumo"])
    pd.testing.assert_frame_equal(saidas_c["payout"], saidas_a["payout"])
    pd.testing.assert_frame_equal(saidas_c["referencia"], saidas_a["referencia"])
    pd.testing.assert_frame_equal(saidas_c["tabela"], saidas_a["tabela"])


def test_alteracao_muda_o_pl_de_aaaa3_em_t2():
    """Prova de que a alteração mexeu: em t2 o P/L de AAAA3 difere entre original e alterado."""
    _, dados_a = _alterado(T)

    grades_orig = calcular_fundamentos_no_dia(T2, CAL_MUNDO, DADOS_ORIGINAL, EXCL, PARAMS, "empresa")
    grades_alt = calcular_fundamentos_no_dia(T2, CAL_MUNDO, dados_a, EXCL, PARAMS, "empresa")

    valor_orig, status_orig = _celula(resumo_precos_no_dia(grades_orig, T2), "AAAA3", "pl.valor")
    valor_alt, status_alt = _celula(resumo_precos_no_dia(grades_alt, T2), "AAAA3", "pl.valor")

    assert status_orig == OK
    assert status_alt == OK
    assert valor_orig == pytest.approx(5.75, rel=1e-9)
    assert valor_alt != pytest.approx(valor_orig, rel=1e-9)


def test_pl_de_aaaa3_em_t_bate_o_gabarito():
    """Em t: valor de mercado 10*50 + 8*50 = 900 (ações de 2025-03-31), lucro 12m 160: P/L 5.625."""
    cal_c, dados_c = _cortado(T)
    grades = calcular_fundamentos_no_dia(T, cal_c, dados_c, EXCL, PARAMS, "empresa")
    valor, status = _celula(resumo_precos_no_dia(grades, T), "AAAA3", "pl.valor")

    assert status == OK
    assert math.isfinite(valor)
    assert valor == pytest.approx(5.625, rel=1e-9)
