"""Montagem dos fundamentos em 21/10/2025 pela camada de leitura (etapa 4, F6).

Usa a fixture `banco_teste` (SQLite em memória com tests/dados/*.csv), nunca o banco da coleta.
Proventos e mudanças de ticker são lidos com `unir_mudancas=False` (tickers ORIGINAIS, ajuste A3).
Valores esperados da seção F6 do plano da etapa 4, conferidos à mão contra os CSVs de teste.
"""

import math
from datetime import date

import pandas as pd
import pytest

from processamento import calendario, fontes
from processamento.exclusoes import carregar_exclusoes
from processamento.fatos.fundamentos import (
    DadosFundamentos,
    balanco_referencia_no_dia,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
)
from processamento.fatos.precos import INDISPONIVEL, NAO_SE_APLICA, OK, resumo_precos_no_dia
from processamento.fatos.proventos import ligar_proventos

T = date(2025, 10, 21)
MODO_SETOR = "empresa"


def _itub4_financeira(df: pd.DataFrame) -> pd.DataFrame:
    """ITUB4 no subsetor financeiro do parâmetro (D5): sem isso, a margem bruta seria calculada."""
    df = df.copy()
    df.loc[df["ticker"] == "ITUB4", "subsetor"] = "Intermediários Financeiros"
    return df


@pytest.fixture
def montagem(banco_teste):
    """Tabelas lidas pela camada de leitura, mais o calendário e as exclusões."""
    ler = banco_teste(alterar={"v1-cadastro": _itub4_financeira})
    precos = fontes.ler_tabela("precos", ler=ler)
    dados = DadosFundamentos(
        precos=precos,
        cadastro=fontes.ler_tabela("cadastro", ler=ler),
        balancos=fontes.ler_tabela("balancos", ler=ler),
        acoes_emitidas=fontes.ler_tabela("acoes_emitidas", ler=ler),
        proventos=fontes.ler_tabela("proventos", ler=ler, unir_mudancas=False),
        mudancas=fontes.mudancas_como_dict(
            fontes.ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False)
        ),
    )
    return dados, calendario.pregoes(precos), carregar_exclusoes()


@pytest.fixture
def grades(montagem):
    dados, cal, excl = montagem
    params = carregar_parametros_fundamentos()
    return calcular_fundamentos_no_dia(T, cal, dados, excl, params, MODO_SETOR)


@pytest.fixture
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


def test_petr3_e_petr4_em_21_10_2025(resumo):
    # P/L e payout: o total de ações de 2025-09-30 (999) não entra, o balanço só saiu em 2025-11-10.
    for ticker in ("PETR3", "PETR4"):
        _ok(resumo, ticker, "pl.valor", 6.896551724137931)
        _ok(resumo, ticker, "pvp.valor", 0.8333333333333334)
        _ok(resumo, ticker, "roe.valor", 0.12083333333333333)
        _ok(resumo, ticker, "margem_bruta.valor", 0.3900709219858156)
        _ok(resumo, ticker, "margem_liquida.valor", 0.10283687943262411)
        _ok(resumo, ticker, "dividend_yield.valor", 0.05)
        _ok(resumo, ticker, "payout.valor", 0.3448275862068966)
        _sem_valor(resumo, ticker, "ebitda.valor_12m", INDISPONIVEL)
        _sem_valor(resumo, ticker, "endividamento.divida_liquida", INDISPONIVEL)


def test_taee11_unit_em_21_10_2025(resumo):
    # Payout pelas classes ON e PN (TAEE3 e TAEE4), nunca pela unit (regra 5 do plano).
    _ok(resumo, "TAEE11", "pl.valor", 6.896551724137931)
    _ok(resumo, "TAEE11", "dividend_yield.valor", 0.09)
    _ok(resumo, "TAEE11", "payout.valor", 0.6206896551724138)


def test_itub4_sem_preco_e_sem_margem_bruta(resumo):
    _sem_valor(resumo, "ITUB4", "pl.valor", INDISPONIVEL)
    _sem_valor(resumo, "ITUB4", "pvp.valor", INDISPONIVEL)
    _sem_valor(resumo, "ITUB4", "dividend_yield.valor", INDISPONIVEL)
    _ok(resumo, "ITUB4", "roe.valor", 0.12083333333333333)
    _sem_valor(resumo, "ITUB4", "margem_bruta.valor", NAO_SE_APLICA)
    _ok(resumo, "ITUB4", "payout.valor", 0.0)


@pytest.mark.parametrize("ticker", ["ABEV3", "NOVA3"])
def test_sem_balanco_pl_roe_e_payout_indisponiveis(resumo, ticker):
    _sem_valor(resumo, ticker, "pl.valor", INDISPONIVEL)
    _sem_valor(resumo, ticker, "roe.valor", INDISPONIVEL)
    _sem_valor(resumo, ticker, "payout.valor", INDISPONIVEL)
    _ok(resumo, ticker, "dividend_yield.valor", 0.0)


def test_bdr_jbss32_sem_pl_nem_yield(resumo):
    _sem_valor(resumo, "JBSS32", "pl.valor", INDISPONIVEL)
    _sem_valor(resumo, "JBSS32", "dividend_yield.valor", INDISPONIVEL)


def test_balanco_de_referencia_de_petr4(montagem):
    dados, _, excl = montagem
    ref = balanco_referencia_no_dia(T, dados, excl)
    linha = ref[ref["ticker"] == "PETR4"].iloc[0]
    assert pd.Timestamp(linha["data_fim_periodo"]) == pd.Timestamp("2025-06-30")
    assert pd.Timestamp(linha["data_entrega"]) == pd.Timestamp("2025-08-10")
    assert linha["status"] == OK


def test_eletrobras_vira_axia_e_fica_sem_empresa(montagem, resumo):
    dados, _, _ = montagem
    ligados = ligar_proventos(dados.proventos, dados.cadastro, dados.mudancas)
    elet = ligados[ligados["ticker"] == "ELET6"].iloc[0]
    assert elet["ticker_atual"] == "AXIA6"
    assert elet["ligacao"] == "sem_empresa"
    assert pd.isna(elet["cnpj"])
    assert not set(resumo["ticker"]) & {"ELET6", "AXIA6"}
