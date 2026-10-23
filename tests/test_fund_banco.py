"""Fundamentos sobre o banco real da coleta (teste de fumaça, etapa 4, F6).

Opcional: só roda com `PROC_TESTES_COM_BANCO=1 pytest -q -m banco tests/test_fund_banco.py`.
Só lê, via `fontes.ler_tabela` e a conexão somente leitura de `fontes.criar_engine()`.
Sem a variável, os testes são pulados. Escrito na etapa 4 e NÃO rodado na implementação: quem
roda é a sessão principal, quando o banco estiver disponível.
"""

from datetime import date

import pytest

from processamento import calendario, fontes
from processamento.exclusoes import carregar_exclusoes
from processamento.fatos.fundamentos import (
    LUCRO_NEGATIVO,
    DadosFundamentos,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
)
from processamento.fatos.precos import INDISPONIVEL, NAO_SE_APLICA, OK, resumo_precos_no_dia

pytestmark = pytest.mark.banco

T = date(2026, 10, 21)
MODO_SETOR = "empresa"


@pytest.fixture(scope="module")
def ler():
    """Só cria a conexão quando um teste banco roda (testes pulados não chegam aqui)."""
    engine = fontes.criar_engine()
    fontes.verificar_sessao_somente_leitura(lambda s: fontes.executar_leitura(s, engine=engine))
    return lambda s, p=None: fontes.executar_leitura(s, p, engine=engine)


@pytest.fixture(scope="module")
def resumo(ler):
    """(resumo longo de T, cadastro, exclusões) com os fundamentos calculados do banco real."""
    precos = fontes.ler_tabela("precos", ler=ler)
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    dados = DadosFundamentos(
        precos=precos,
        cadastro=cadastro,
        balancos=fontes.ler_tabela("balancos", ler=ler),
        acoes_emitidas=fontes.ler_tabela("acoes_emitidas", ler=ler),
        proventos=fontes.ler_tabela("proventos", ler=ler, unir_mudancas=False),
        mudancas=fontes.mudancas_como_dict(
            fontes.ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False)
        ),
    )
    cal = calendario.pregoes(precos)
    excl = carregar_exclusoes()
    params = carregar_parametros_fundamentos()
    grades = calcular_fundamentos_no_dia(T, cal, dados, excl, params, MODO_SETOR)
    return resumo_precos_no_dia(grades, T), cadastro, excl


def _status(resumo, ticker, indicador):
    linha = resumo[(resumo["ticker"] == ticker) & (resumo["indicador"] == indicador)]
    assert len(linha) == 1
    return linha["status"].iloc[0]


def test_ticker_sem_balanco_tem_pl_indisponivel(resumo):
    r, cadastro, excl = resumo
    cnpjs = set(excl.cnpjs_sem_balanco)
    tickers = cadastro.loc[cadastro["cnpj"].isin(cnpjs), "ticker"]
    for ticker in tickers:
        if ticker in excl.tickers_excluidos:
            continue
        assert _status(r, ticker, "pl.valor") == INDISPONIVEL


def test_petr4_com_ebitda_e_divida_liquida_e_pl_ok_ou_prejuizo(resumo):
    # Desde 22/10/2026 a coleta preenche ebit, D&A, empréstimos, caixa e aplicações
    r, _, _ = resumo
    assert _status(r, "PETR4", "ebitda.valor_12m") == OK
    assert _status(r, "PETR4", "endividamento.divida_liquida") == OK
    assert _status(r, "PETR4", "pl.valor") in (OK, LUCRO_NEGATIVO)


@pytest.mark.parametrize("ticker", ["ITUB4", "BBDC4", "BBAS3"])
def test_bancos_sem_margem_bruta(resumo, ticker):
    r, _, _ = resumo
    assert _status(r, ticker, "margem_bruta.valor") == NAO_SE_APLICA


def test_b3sa3_tem_margem_bruta_aplicavel(resumo):
    r, _, _ = resumo
    assert _status(r, "B3SA3", "margem_bruta.valor") != NAO_SE_APLICA
