"""Testes de processamento/fatos/fundamentos.py: parâmetros, texto e a fábrica de fundamentos.

Usa o parametros.yaml real e cópias temporárias (tmp_path) para os casos de erro.
Nenhum teste usa banco ou rede.
"""

import re
from datetime import date

import numpy as np
import pytest
import yaml

from fabrica_fundamentos import CNPJ, LINHAS_A, mundo
from processamento import calendario
from processamento.fatos.fundamentos import (
    ErroParametrosFundamentos,
    ParametrosFundamentos,
    carregar_parametros_fundamentos,
    eh_financeiro,
    normalizar_texto,
)


def _parametros_em(tmp_path, mudar) -> str:
    """Copia o parametros.yaml real, aplica `mudar(dados)` e grava em tmp_path."""
    dados = yaml.safe_load(calendario.CAMINHO_PARAMETROS.read_text(encoding="utf-8"))
    mudar(dados)
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return str(caminho)


def test_yaml_real_traz_o_bloco_fundamentos():
    params = carregar_parametros_fundamentos()
    assert params == ParametrosFundamentos(
        subsetores_financeiros=("Intermediários Financeiros", "Previdência e Seguros", "Holdings Diversificadas"),
        meses_janela=12,
        anos_payout=5,
        anos_historico_proventos=5,
        pvp_minimo_plausivel=0.05,
        balanco_idade_max_meses=15,
        pvp_maximo_plausivel_x1000=20.0,
        quantidade_suspeita_manual=(
            ("RAIZ4", date(2026, 11, 3),
             "RAIZ4 virou RAIZ55 em 03/11/2026, cotada por lote de 100 (Ofício Circular B3 022/2026-VPE); "
             "quantidade de ações não acompanha o preço até a coleta corrigir"),
        ),
    )


def test_calendario_aceita_o_bloco_fundamentos():
    dados = calendario.carregar_parametros()
    assert "fundamentos" in dados
    assert "fase1" in dados


def test_yaml_sem_bloco_fundamentos_levanta_erro(tmp_path):
    caminho = _parametros_em(tmp_path, lambda d: d.pop("fundamentos"))
    with pytest.raises(ErroParametrosFundamentos, match=re.escape("falta o bloco fundamentos")):
        carregar_parametros_fundamentos(caminho)


@pytest.mark.parametrize(
    "mudar, trecho",
    [
        (lambda d: d["fundamentos"].__setitem__("chave_nova", 1), "chave desconhecida"),
        (lambda d: d["fundamentos"].pop("anos_payout"), "faltam chaves"),
        (lambda d: d["fundamentos"].__setitem__("subsetores_financeiros", []), "fundamentos.subsetores_financeiros"),
        (lambda d: d["fundamentos"].__setitem__("subsetores_financeiros", [1]), "subsetor inválido"),
        (lambda d: d["fundamentos"].__setitem__("subsetores_financeiros", ["  "]), "subsetor inválido"),
        (lambda d: d["fundamentos"].__setitem__("meses_janela", 0), "fundamentos.meses_janela"),
        (lambda d: d["fundamentos"].__setitem__("anos_payout", True), "fundamentos.anos_payout"),
        (lambda d: d["fundamentos"].__setitem__("anos_historico_proventos", "5"),
         "fundamentos.anos_historico_proventos"),
        (lambda d: d["fundamentos"].pop("pvp_minimo_plausivel"), "faltam chaves"),
        (lambda d: d["fundamentos"].__setitem__("pvp_minimo_plausivel", 0), "fundamentos.pvp_minimo_plausivel"),
        (lambda d: d["fundamentos"].__setitem__("pvp_minimo_plausivel", 1), "fundamentos.pvp_minimo_plausivel"),
        (lambda d: d["fundamentos"].__setitem__("pvp_minimo_plausivel", -0.05), "fundamentos.pvp_minimo_plausivel"),
        (lambda d: d["fundamentos"].__setitem__("pvp_minimo_plausivel", True), "fundamentos.pvp_minimo_plausivel"),
        (lambda d: d["fundamentos"].__setitem__("pvp_minimo_plausivel", "0.05"), "fundamentos.pvp_minimo_plausivel"),
        (lambda d: d["fundamentos"].pop("pvp_maximo_plausivel_x1000"), "faltam chaves"),
        (lambda d: d["fundamentos"].__setitem__("pvp_maximo_plausivel_x1000", 0), "fundamentos.pvp_maximo_plausivel_x1000"),
        (lambda d: d["fundamentos"].__setitem__("pvp_maximo_plausivel_x1000", True), "fundamentos.pvp_maximo_plausivel_x1000"),
        (lambda d: d["fundamentos"].__setitem__("pvp_maximo_plausivel_x1000", "50"), "fundamentos.pvp_maximo_plausivel_x1000"),
        (lambda d: d["fundamentos"].pop("balanco_idade_max_meses"), "faltam chaves"),
        (lambda d: d["fundamentos"].__setitem__("balanco_idade_max_meses", 0), "fundamentos.balanco_idade_max_meses"),
        (lambda d: d["fundamentos"].__setitem__("balanco_idade_max_meses", True), "fundamentos.balanco_idade_max_meses"),
        (lambda d: d["fundamentos"].__setitem__("balanco_idade_max_meses", "15"), "fundamentos.balanco_idade_max_meses"),
    ],
)
def test_parametros_fundamentos_invalidos_levantam_erro(tmp_path, mudar, trecho):
    caminho = _parametros_em(tmp_path, mudar)
    with pytest.raises(ErroParametrosFundamentos, match=re.escape(trecho)):
        carregar_parametros_fundamentos(caminho)


@pytest.mark.parametrize(
    "subsetor",
    ["Intermediários Financeiros", " intermediarios financeiros", "Previdência e Seguros", "PREVIDENCIA E SEGUROS",
     "Holdings Diversificadas", "holdings diversificadas"],
)
def test_eh_financeiro_ignora_acento_caixa_e_espacos(subsetor):
    assert eh_financeiro(subsetor, carregar_parametros_fundamentos()) is True


@pytest.mark.parametrize("subsetor", ["Serviços Financeiros Diversos", None, np.nan, ""])
def test_eh_financeiro_recusa_fora_da_lista(subsetor):
    assert eh_financeiro(subsetor, carregar_parametros_fundamentos()) is False


@pytest.mark.parametrize("texto", [None, np.nan, "", "   "])
def test_normalizar_texto_vazio_vira_none(texto):
    assert normalizar_texto(texto) is None


def test_normalizar_texto_tira_acento_e_caixa():
    assert normalizar_texto("  Previdência   e  SEGUROS ") == "previdencia e seguros"


def test_fabrica_tem_nove_linhas_de_balanco_na_tabela_a():
    assert len(LINHAS_A) == 9


def test_mundo_devolve_doze_tickers_e_a_troca_de_ticker():
    cadastro, balancos, acoes, proventos, precos, cal, mudancas = mundo()
    assert len(cadastro) == 12
    assert set(cadastro["ticker"]) >= {"AAAA3", "KKKK3"}
    assert mudancas == {"KKKK6": "KKKK3"}
    assert set(balancos["cnpj"]) == set(CNPJ[c] for c in ("A", "U", "PREJ", "BANC", "D", "BDRX", "DUPN", "EXTI", "K"))
    assert len(cal) > 0
