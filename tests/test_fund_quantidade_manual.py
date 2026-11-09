"""Testes da lista manual `fundamentos.quantidade_suspeita_manual` (força a quantidade de ações suspeita).

Parser do yaml, indicadores por empresa, painel do dia, múltiplos diários, payout por ano e o aviso do execucao.
Mundo de tests/fabrica_fundamentos.py em T = 2026-03-31 (AAAA3 e AAAA4 são da empresa A; UUUU11 é da U).
Usa o parametros.yaml real e cópias temporárias (tmp_path) para os casos de erro. Sem banco e sem rede.
"""

import dataclasses
import math
import re
from datetime import date

import pandas as pd
import pytest
import yaml

from fabrica_fundamentos import CAL, EXCL, T, mundo
from processamento import calendario
from processamento.fatos.fundamentos import (
    DadosFundamentos,
    ErroParametrosFundamentos,
    avisos_quantidade_suspeita_manual,
    calcular_fundamentos_no_dia,
    carregar_parametros_fundamentos,
    cnpjs_suspeita_manual,
    indicadores_empresa,
    payout_por_ano,
)
from processamento.fatos.multiplos import multiplos_diarios
from processamento.fatos.precos import INDISPONIVEL, OK, resumo_precos_no_dia
from processamento.fatos.trimestres import ESTOQUE, FLUXO, FotoBalanco

NAN = math.nan
CNPJ_TESTE = "11.111.111/0001-11"
TEXTO_AVISO = ("Quantidade de ações tratada como suspeita por decisão manual (fundamentos.quantidade_suspeita_manual): "
               "RAIZ4 desde 2026-11-03 (motivo X). Valor de mercado, P/L, P/VP e payout saem indisponíveis.")


# ---------------------------------------------------------------------------
# Parser (yaml)
# ---------------------------------------------------------------------------

def _parametros_em(tmp_path, mudar) -> str:
    """Copia o parametros.yaml real, aplica `mudar(dados)` e grava em tmp_path."""
    dados = yaml.safe_load(calendario.CAMINHO_PARAMETROS.read_text(encoding="utf-8"))
    mudar(dados)
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return str(caminho)


def _com_lista(valor):
    return lambda d: d["fundamentos"].__setitem__("quantidade_suspeita_manual", valor)


def test_yaml_real_sem_entrada_ativa():
    # 09/11/2026: a RAIZ4 saiu da lista (a coleta corrigiu o preço da RAIZ55).
    params = carregar_parametros_fundamentos()
    assert params.quantidade_suspeita_manual == ()


def test_chave_ausente_vira_lista_vazia(tmp_path):
    caminho = _parametros_em(tmp_path, lambda d: d["fundamentos"].pop("quantidade_suspeita_manual"))
    assert carregar_parametros_fundamentos(caminho).quantidade_suspeita_manual == ()


def test_lista_vazia_vira_lista_vazia(tmp_path):
    caminho = _parametros_em(tmp_path, _com_lista([]))
    assert carregar_parametros_fundamentos(caminho).quantidade_suspeita_manual == ()


def test_data_como_objeto_date_tambem_e_aceita(tmp_path):
    entrada = {"ticker": "RAIZ4", "desde": date(2026, 11, 3), "motivo": "motivo X"}
    caminho = _parametros_em(tmp_path, _com_lista([entrada]))
    assert carregar_parametros_fundamentos(caminho).quantidade_suspeita_manual == (
        ("RAIZ4", date(2026, 11, 3), "motivo X"),
    )


@pytest.mark.parametrize(
    "valor, trecho",
    [
        ("RAIZ4", "deve ser uma lista"),
        ([{"ticker": "RAIZ4", "motivo": "x"}], "faltam chaves"),
        ([{"ticker": "RAIZ4", "desde": "2026-11-03"}], "faltam chaves"),
        ([{"ticker": "RAIZ4", "desde": "2026-13-01", "motivo": "x"}], "desde deve ser uma data"),
        ([{"ticker": "RAIZ4", "desde": "03/11/2026", "motivo": "x"}], "desde deve ser uma data"),
        ([{"ticker": "RAIZ4", "desde": "2026-11-03", "motivo": "x", "extra": 1}], "chave desconhecida"),
        ([{"ticker": "RAIZ4", "desde": "2026-11-03", "motivo": "x"},
          {"ticker": "RAIZ4", "desde": "2026-12-01", "motivo": "y"}], "ticker repetido"),
        ([{"ticker": " ", "desde": "2026-11-03", "motivo": "x"}], "ticker deve ser um texto não vazio"),
        ([{"ticker": "RAIZ4", "desde": "2026-11-03", "motivo": ""}], "motivo deve ser um texto não vazio"),
        (["RAIZ4"], "deve ser um mapeamento"),
    ],
)
def test_quantidade_manual_invalida_levanta_erro(tmp_path, valor, trecho):
    caminho = _parametros_em(tmp_path, _com_lista(valor))
    with pytest.raises(ErroParametrosFundamentos, match=re.escape(trecho)):
        carregar_parametros_fundamentos(caminho)


# ---------------------------------------------------------------------------
# Helpers de CNPJ e de aviso
# ---------------------------------------------------------------------------

def test_cnpjs_suspeita_manual_so_com_desde_ate_a_data():
    lista = (("RAIZ4", date(2026, 11, 3), "m"),)
    cnpj_de = {"RAIZ4": CNPJ_TESTE}
    assert cnpjs_suspeita_manual(lista, cnpj_de, date(2026, 11, 2)) == set()
    assert cnpjs_suspeita_manual(lista, cnpj_de, date(2026, 11, 3)) == {CNPJ_TESTE}
    assert cnpjs_suspeita_manual(lista, cnpj_de, pd.Timestamp("2026-11-04")) == {CNPJ_TESTE}


def test_cnpjs_suspeita_manual_ignora_ticker_sem_cnpj():
    assert cnpjs_suspeita_manual((("ZZZZ3", date(2026, 1, 1), "m"),), {}, date(2026, 6, 1)) == set()


def test_aviso_com_entrada_ativa_no_dia_tem_o_texto_exato():
    lista = (("RAIZ4", date(2026, 11, 3), "motivo X"),)
    assert avisos_quantidade_suspeita_manual(lista, date(2026, 11, 3)) == [TEXTO_AVISO]


def test_aviso_com_entrada_ainda_nao_ativa_e_vazio():
    lista = (("RAIZ4", date(2026, 11, 3), "motivo X"),)
    assert avisos_quantidade_suspeita_manual(lista, date(2026, 11, 2)) == []


def test_aviso_sem_lista_e_vazio():
    assert avisos_quantidade_suspeita_manual((), date(2026, 11, 8)) == []


def test_aviso_do_yaml_real_sem_entrada_ativa():
    # 09/11/2026: lista real vazia (RAIZ4 saiu): nenhum aviso.
    lista = carregar_parametros_fundamentos().quantidade_suspeita_manual
    assert avisos_quantidade_suspeita_manual(lista, date(2026, 11, 9)) == []


# ---------------------------------------------------------------------------
# Indicadores por empresa (indicadores_empresa com suspeita_forcada)
# ---------------------------------------------------------------------------

def _foto_a_mao(fluxo=None, estoque=None) -> FotoBalanco:
    """Foto montada à mão: indisponivel, exceto o que for dado em `fluxo` e `estoque`."""
    fluxo_12m = {c: (NAN, INDISPONIVEL) for c in FLUXO}
    fluxo_12m.update(fluxo or {})
    estoque_fim = {c: (NAN, INDISPONIVEL) for c in ESTOQUE}
    estoque_fim.update(estoque or {})
    return FotoBalanco(status_base=OK, data_fim_periodo=None, data_entrega=None,
                       fluxo_12m=fluxo_12m, fluxo_trimestre={}, estoque=estoque_fim)


def _mesmo_par(a, b):
    """Mesmo (valor, status); NaN é igual a NaN."""
    return a[1] == b[1] and (a[0] == b[0] or (math.isnan(a[0]) and math.isnan(b[0])))


def test_suspeita_forcada_tira_pl_pvp_e_payout_sem_regra_automatica():
    foto = _foto_a_mao(
        fluxo={"lucro_liquido": (160.0, OK), "receita_liquida": (1000.0, OK), "lucro_bruto": (400.0, OK)},
        estoque={"patrimonio_liquido": (1300.0, OK)},
    )
    args = (foto, (920.0, OK), (50.0, OK), False)
    sem = indicadores_empresa(*args, pvp_minimo=0.05, pvp_maximo_x1000=20.0)
    com = indicadores_empresa(*args, pvp_minimo=0.05, pvp_maximo_x1000=20.0, suspeita_forcada=True)
    # sem a lista a empresa não é suspeita (P/VP = 920 ÷ 1300 = 0,71)
    assert sem["pvp.valor"][1] == OK
    for chave in ("pl.valor", "pvp.valor", "payout.valor"):
        assert math.isnan(com[chave][0]) and com[chave][1] == INDISPONIVEL, chave
    for chave in com:
        if chave not in ("pl.valor", "pvp.valor", "payout.valor"):
            assert _mesmo_par(com[chave], sem[chave]), chave


def test_suspeita_forcada_sem_pvp_minimo_tambem_vale():
    foto = _foto_a_mao(fluxo={"lucro_liquido": (160.0, OK)}, estoque={"patrimonio_liquido": (1300.0, OK)})
    com = indicadores_empresa(foto, (920.0, OK), (50.0, OK), False, suspeita_forcada=True)
    assert com["pl.valor"][1] == INDISPONIVEL
    assert com["pvp.valor"][1] == INDISPONIVEL
    assert com["payout.valor"][1] == INDISPONIVEL


# ---------------------------------------------------------------------------
# Painel do dia (calcular_fundamentos_no_dia) e payout por ano
# ---------------------------------------------------------------------------

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


def _params_com(ticker, desde):
    return dataclasses.replace(PARAMS, quantidade_suspeita_manual=((ticker, desde, "teste"),))


def _celula(resumo, ticker, indicador):
    linha = resumo[(resumo["ticker"] == ticker) & (resumo["indicador"] == indicador)]
    assert len(linha) == 1
    return float(linha["valor"].iloc[0]), linha["status"].iloc[0]


@pytest.fixture(scope="module")
def resumo_base():
    return resumo_precos_no_dia(calcular_fundamentos_no_dia(T, CAL, DADOS, EXCL, PARAMS, "empresa"), T)


@pytest.fixture(scope="module")
def resumo_forcado(resumo_base):
    grades = calcular_fundamentos_no_dia(T, CAL, DADOS, EXCL, _params_com("AAAA3", T), "empresa")
    return resumo_precos_no_dia(grades, T)


@pytest.mark.parametrize("ticker", ["AAAA3", "AAAA4"])
def test_painel_com_desde_no_dia_tira_pl_pvp_payout_da_empresa(resumo_forcado, ticker):
    for indicador in ("pl.valor", "pvp.valor", "payout.valor"):
        _, status = _celula(resumo_forcado, ticker, indicador)
        assert status == INDISPONIVEL, (ticker, indicador)


@pytest.mark.parametrize("ticker", ["AAAA3", "AAAA4"])
def test_painel_com_desde_no_dia_nao_muda_roe_margem_e_yield(resumo_base, resumo_forcado, ticker):
    for indicador in ("roe.valor", "margem_bruta.valor", "margem_liquida.valor", "dividend_yield.valor"):
        assert _mesmo_par(_celula(resumo_forcado, ticker, indicador), _celula(resumo_base, ticker, indicador)), indicador


def test_painel_com_desde_no_dia_nao_muda_os_valores_de_outra_empresa(resumo_base, resumo_forcado):
    # UUUU11 é da empresa U: os próprios indicadores não mudam (as medianas do setor podem mudar)
    for indicador in ("pl.valor", "pvp.valor", "payout.valor", "roe.valor", "dividend_yield.valor"):
        assert _mesmo_par(_celula(resumo_forcado, "UUUU11", indicador), _celula(resumo_base, "UUUU11", indicador)), indicador


def test_painel_com_desde_depois_de_t_e_igual_ao_sem_lista():
    desde = date(2026, 4, 1)  # um dia depois de T
    base = calcular_fundamentos_no_dia(T, CAL, DADOS, EXCL, PARAMS, "empresa")
    com = calcular_fundamentos_no_dia(T, CAL, DADOS, EXCL, _params_com("AAAA3", desde), "empresa")
    assert base.keys() == com.keys()
    for campo in base:
        pd.testing.assert_frame_equal(com[campo].valor, base[campo].valor)
        pd.testing.assert_frame_equal(com[campo].status, base[campo].status)


def test_payout_por_ano_com_entrada_ativa_fica_indisponivel():
    normal = payout_por_ano(T, DADOS, EXCL, PARAMS)
    assert (normal[normal["ticker"] == "AAAA3"]["status"] == OK).any()
    linhas = payout_por_ano(T, DADOS, EXCL, _params_com("AAAA3", T))
    aaaa3 = linhas[linhas["ticker"] == "AAAA3"]
    assert len(aaaa3) > 0
    assert set(aaaa3["status"]) == {INDISPONIVEL}
    assert aaaa3["valor"].isna().all()
    uuuu_normal = normal[normal["ticker"] == "UUUU11"].reset_index(drop=True)
    uuuu_forcado = linhas[linhas["ticker"] == "UUUU11"].reset_index(drop=True)
    pd.testing.assert_frame_equal(uuuu_forcado, uuuu_normal)


# ---------------------------------------------------------------------------
# Múltiplos diários (P/L, P/VP e yield por pregão)
# ---------------------------------------------------------------------------

def test_multiplos_antes_de_desde_iguais_e_depois_pl_pvp_indisponiveis():
    desde = date(2026, 3, 16)
    base = multiplos_diarios(DADOS, CAL, EXCL, PARAMS)
    com = multiplos_diarios(DADOS, CAL, EXCL, _params_com("AAAA3", desde))
    antes = base["pl"].valor.index < pd.Timestamp(desde)
    depois = ~antes
    assert antes.any() and depois.any()
    for chave in ("pl", "pvp", "dividend_yield"):
        pd.testing.assert_frame_equal(com[chave].valor.loc[antes], base[chave].valor.loc[antes])
        pd.testing.assert_frame_equal(com[chave].status.loc[antes], base[chave].status.loc[antes])
    for ticker in ("AAAA3", "AAAA4"):
        for chave in ("pl", "pvp"):
            assert (com[chave].status.loc[depois, ticker] == INDISPONIVEL).all(), (chave, ticker)
            assert com[chave].valor.loc[depois, ticker].isna().all(), (chave, ticker)
    # o yield não depende da quantidade de ações
    pd.testing.assert_frame_equal(com["dividend_yield"].valor, base["dividend_yield"].valor)
