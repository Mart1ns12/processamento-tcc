"""Integração da fase 1 (etapa 3, passo P8): montagem dos indicadores em 21/10/2025.

Usa a fixture `banco_teste` (SQLite em memória com tests/dados/*.csv), nunca o banco da coleta.
Valores esperados conferidos à mão contra os CSVs de teste.
"""

import math
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from processamento import calendario, fontes
from processamento.exclusoes import carregar_exclusoes
from processamento.fatos.indices import calcular_indices, indices_no_dia, ipca_ate
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    NAO_SE_APLICA,
    OK,
    calcular_precos,
    carregar_parametros_precos,
    pares_do_painel,
    resumo_precos_no_dia,
    tickers_do_painel,
)

T = date(2025, 10, 21)
PAINEL = ["ABEV3", "ITUB4", "JBSS32", "NOVA3", "PETR3", "PETR4", "TAEE11"]


@pytest.fixture
def dados(banco_teste):
    ler = banco_teste()
    precos = fontes.ler_tabela("precos", ler=ler)
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    indices = fontes.ler_tabela("indices", ler=ler)
    cal = calendario.pregoes(precos)
    return precos, cadastro, indices, cal


def _resumos(dados, params=None, t=T):
    precos, cadastro, indices, cal = dados
    params = params or carregar_parametros_precos()
    excl = carregar_exclusoes()
    res = calcular_precos(precos, cadastro, cal, excl, params)
    resumo = resumo_precos_no_dia(res, t)
    ri = indices_no_dia(calcular_indices(precos, indices, cal, params), t)
    return resumo, ri


def _linha(df, chave, nome, valor_col, dim):
    linha = df[(df[dim] == chave) & (df[nome[0]] == nome[1])]
    assert len(linha) == 1, (chave, nome)
    return linha[valor_col].iloc[0], linha["status"].iloc[0]


def _checa(r, ticker, indicador, status, valor=None):
    """Confere o status; se ok, o valor (aproximado); se não ok, o valor tem de ser NaN."""
    v, s = _linha(r, ticker, ("indicador", indicador), "valor", "ticker")
    assert s == status, (ticker, indicador, s)
    if status == OK:
        assert v == pytest.approx(valor, abs=1e-12), (ticker, indicador)
    else:
        assert math.isnan(v), (ticker, indicador, v)


def _checa_indice(ri, indice, janela, status, valor=None):
    v, s = _linha(ri, indice, ("janela", janela), "valor", "indice")
    assert s == status, (indice, janela, s)
    if status == OK:
        assert v == pytest.approx(valor, abs=1e-12), (indice, janela)
    else:
        assert math.isnan(v), (indice, janela, v)


def test_tickers_do_painel_e_pares_vem_do_cadastro(dados):
    _, cadastro, _, _ = dados
    excl = carregar_exclusoes()
    assert tickers_do_painel(cadastro, excl) == PAINEL
    assert pares_do_painel(cadastro, excl) == ["ABEV3", "ITUB4", "NOVA3", "PETR3", "PETR4", "TAEE11"]


def test_colunas_da_saida_vem_do_cadastro(dados):
    r, _ = _resumos(dados)
    tickers = set(r["ticker"])
    assert tickers == set(PAINEL)  # CRFB3 excluída; ITUB4 entra mesmo sem preço
    assert "IBOV" not in tickers and "BRENT" not in tickers


def test_petr4_em_21_10_modo_empresa(dados):
    r, _ = _resumos(dados)
    _checa(r, "PETR4", "cotacao.fechamento", OK, 10.0)
    _checa(r, "PETR4", "cotacao.variacao_dia", OK, 0.0)
    _checa(r, "PETR4", "rentabilidade.d1", OK, 0.0)
    _checa(r, "PETR4", "rentabilidade.m1", HIST)
    _checa(r, "PETR4", "rentabilidade.ibov.d1", OK, 0.0)
    _checa(r, "PETR4", "volume.total", OK, 1000.0)
    _checa(r, "PETR4", "volume.relativo", HIST)
    _checa(r, "PETR4", "beta.valor", HIST)
    # PETR3 tem o mesmo CNPJ: no modo "empresa" não entra no setor da PETR4
    _checa(r, "PETR4", "rentabilidade.setor.d1", INDISPONIVEL)
    # setor com só 1 empresa (CNPJs distintos) -> comparação fraca
    _checa(r, "PETR4", "setor_comparacao_fraca", OK, 1.0)


def test_petr4_setor_modo_acao_com_parametro_alterado(dados):
    params = replace(carregar_parametros_precos(), setor_excluir="acao")
    r, _ = _resumos(dados, params=params)
    # no modo "acao", PETR3 (outra ação da mesma empresa) entra: rentabilidade d1 0.0
    _checa(r, "PETR4", "rentabilidade.setor.d1", OK, 0.0)


def test_abev3_e_nova3(dados):
    r, _ = _resumos(dados)
    _checa(r, "ABEV3", "cotacao.fechamento", OK, 10.0)
    _checa(r, "ABEV3", "rentabilidade.d1", INDISPONIVEL)  # aj vazio em 21/10
    _checa(r, "ABEV3", "rentabilidade.setor.d1", INDISPONIVEL)  # Bebidas sem outra empresa
    _checa(r, "TAEE11", "rentabilidade.d1", OK, 0.0)
    _checa(r, "JBSS32", "volume.posicao_pct", NAO_SE_APLICA)  # BDR fica fora dos pares
    _checa(r, "ITUB4", "cotacao.fechamento", INDISPONIVEL)  # sem linhas em v1-precos


def test_nova3_d1_ok_em_21_e_historico_em_20(dados):
    r, _ = _resumos(dados)
    _checa(r, "NOVA3", "rentabilidade.d1", OK, 0.0)
    r20, _ = _resumos(dados, t=date(2025, 10, 20))
    _checa(r20, "NOVA3", "rentabilidade.d1", HIST)


def test_indices_em_21_10(dados):
    _, ri = _resumos(dados)
    _checa_indice(ri, "CDI", "d1", OK, 0.0005)
    _checa_indice(ri, "IDIV", "d1", OK, 0.010000000000000009)
    _checa_indice(ri, "IPCA", "d1", OK, 0.0)
    _checa_indice(ri, "IPCA", "m1", HIST)
    _checa_indice(ri, "SMLL", "d1", INDISPONIVEL)
    _checa_indice(ri, "IVVB11", "d1", INDISPONIVEL)


def test_idiv_d1_em_20_10_historico(dados):
    _, ri = _resumos(dados, t=date(2025, 10, 20))
    _checa_indice(ri, "IDIV", "d1", HIST)


def test_ipca_ate_em_21_10(dados):
    _, _, indices, _ = dados
    assert ipca_ate(indices, T) == "2025-09"


def test_t_que_nao_e_pregao_levanta_erro(dados):
    precos, cadastro, indices, cal = dados
    excl = carregar_exclusoes()
    params = carregar_parametros_precos()
    res = calcular_precos(precos, cadastro, cal, excl, params)
    ri = calcular_indices(precos, indices, cal, params)
    sabado = date(2025, 10, 18)
    with pytest.raises(ValueError):
        resumo_precos_no_dia(res, sabado)
    with pytest.raises(ValueError):
        indices_no_dia(ri, sabado)


def test_resumo_tem_formato_longo(dados):
    r, ri = _resumos(dados)
    assert list(r.columns) == ["ticker", "indicador", "valor", "status"]
    assert list(ri.columns) == ["indice", "janela", "valor", "status"]
    assert not r.duplicated(["ticker", "indicador"]).any()
    assert set(r["status"]) <= {OK, INDISPONIVEL, HIST, NAO_SE_APLICA}
