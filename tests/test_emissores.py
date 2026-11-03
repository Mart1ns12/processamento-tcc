"""Testes de processamento/emissores.py (T1): funções puras sobre o emissor por período.

Gabarito da tabela real (EMISSORES_REAIS de tests/fabrica_emissores.py): JBS (JBSS3/JBSS32),
Natura (NATU3 e holding NTCO3) e identidades (HAPV3, MGLU3). Sem banco e sem rede.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from fabrica_emissores import (
    CNPJ_JBS_NV,
    CNPJ_JBS_SA,
    EMISSORES_REAIS,
    LINHAS_EMISSORES_REAIS,
    emissores_de,
)
from fabrica_fundamentos import cadastro_fund_de
from processamento import emissores as em

E = EMISSORES_REAIS
CNPJ_NATURA = "71673990000177"
CNPJ_HOLDING = "32785497000197"


# indice e vigência

def test_indice_agrupa_por_ticker_na_ordem():
    ind = em.indice(E)
    assert set(ind) == {"JBSS32", "NATU3", "HAPV3", "MGLU3"}
    assert [linha["ordem"] for linha in ind["NATU3"]] == [1, 2, 3]


def test_indice_sem_emissores_e_vazio():
    assert em.indice(None) == {}
    assert em.indice(emissores_de([])) == {}


def test_vigente_por_ticker_e_data():
    assert em.vigente(E, "JBSS32", "2025-06-08")["ordem"] == 1
    assert em.vigente(E, "JBSS32", "2025-06-09")["ordem"] == 2
    assert em.vigente(E, "NATU3", "2019-12-17")["ordem"] == 1
    assert em.vigente(E, "NATU3", "2019-12-18")["ordem"] == 2
    assert em.vigente(E, "NATU3", "2025-07-01")["ordem"] == 2
    assert em.vigente(E, "NATU3", "2025-07-02")["ordem"] == 3


def test_vigente_sem_linha_ou_data_nat_da_none():
    assert em.vigente(E, "PETR4", "2025-06-06") is None
    assert em.vigente(E, "JBSS32", None) is None
    assert em.vigente(E, "JBSS32", pd.NaT) is None
    assert em.vigente(None, "JBSS32", "2025-06-06") is None


def test_vigente_ignora_horario_da_data():
    # Vigência é por dia: 08/06/2025 às 15h ainda é o dia 08/06 (ordem 1).
    assert em.vigente(E, "JBSS32", pd.Timestamp("2025-06-08 15:00"))["ordem"] == 1


# cnpj e tipo na data

@pytest.mark.parametrize("ticker, data, esperado", [
    ("JBSS32", "2025-06-08", CNPJ_JBS_SA),
    ("JBSS32", "2025-06-09", CNPJ_JBS_NV),
    ("NATU3", "2019-12-17", CNPJ_NATURA),
    ("NATU3", "2019-12-18", CNPJ_HOLDING),
    ("NATU3", "2025-07-01", CNPJ_HOLDING),
    ("NATU3", "2025-07-02", CNPJ_NATURA),
    ("HAPV3", "2021-07-16", "05197443000138"),
])
def test_cnpj_na_data_segue_o_emissor_vigente(ticker, data, esperado):
    assert em.cnpj_na_data(E, ticker, data, "99999999999999") == esperado


def test_cnpj_na_data_sem_vigente_usa_o_do_cadastro():
    assert em.cnpj_na_data(E, "PETR4", "2025-06-06", "33000167000101") == "33000167000101"
    assert em.cnpj_na_data(None, "JBSS32", "2025-06-08", CNPJ_JBS_NV) == CNPJ_JBS_NV


def test_cnpj_na_data_cnpj_vazio_no_emissor_usa_o_do_cadastro():
    linhas = [("PETR4", 1, "PETR4", None, "Petrobras", None, None, 1.0)]
    assert em.cnpj_na_data(emissores_de(linhas), "PETR4", "2025-06-06", "33000167000101") == "33000167000101"


def test_tipo_na_data_jbs_e_on_ate_08_06_e_bdr_depois():
    assert em.tipo_na_data(E, "JBSS32", "2025-06-08", "BDR") == "ON"
    assert em.tipo_na_data(E, "JBSS32", "2025-06-09", "BDR") == "BDR"


def test_tipo_na_data_pela_classe_do_codigo_negociado():
    # NATU3 de 18/12/2019 a 01/07/2025 negocia como NTCO3 (classe 3, ON), mesmo com cadastro PN.
    assert em.tipo_na_data(E, "NATU3", "2020-01-02", "ON") == "ON"
    assert em.tipo_na_data(E, "NATU3", "2020-01-02", "PN") == "ON"


def test_tipo_na_data_classe_sem_tipo_usa_o_do_cadastro():
    linhas = [("XXXX3", 1, "YYYY9", "11111111000111", "Empresa X", None, None, 1.0)]
    assert em.tipo_na_data(emissores_de(linhas), "XXXX3", "2025-06-06", "ON") == "ON"


# cadastro na data

CAD = cadastro_fund_de([
    ("JBSS32", CNPJ_JBS_NV, "Alimentos", "Carnes", "BDR", None, None),
    ("PETR4", "33000167000101", "Petroleo", "Petroleo", "PN", None, None),
])


def test_cadastro_na_data_antes_da_troca_muda_so_a_jbs():
    copia = CAD.copy()
    novo = em.cadastro_na_data(CAD, E, "2025-06-06").set_index("ticker")
    jbs = novo.loc["JBSS32"]
    assert jbs["cnpj"] == CNPJ_JBS_SA
    assert jbs["tipo_acao"] == "ON"
    assert jbs["empresa"] == "JBS SA"
    assert jbs["setor"] == "Alimentos"
    petr = novo.loc["PETR4"]
    assert petr["cnpj"] == "33000167000101"
    assert petr["tipo_acao"] == "PN"
    assert petr["empresa"] == "PETR4"
    pd.testing.assert_frame_equal(CAD, copia)


def test_cadastro_na_data_depois_da_troca_usa_a_jbs_nv():
    novo = em.cadastro_na_data(CAD, E, "2025-06-09").set_index("ticker")
    jbs = novo.loc["JBSS32"]
    assert jbs["cnpj"] == CNPJ_JBS_NV
    assert jbs["tipo_acao"] == "BDR"
    assert jbs["empresa"] == "JBS N.V."


def test_cadastro_na_data_sem_emissores_devolve_copia_igual():
    pd.testing.assert_frame_equal(em.cadastro_na_data(CAD, None, "2025-06-06"), CAD)
    pd.testing.assert_frame_equal(em.cadastro_na_data(CAD, emissores_de([]), "2025-06-06"), CAD)


# fronteiras e trechos

def test_fronteiras_datas_de_inicio_e_fim_mais_um_dia():
    assert em.fronteiras(E) == [
        pd.Timestamp("2019-12-18"),
        pd.Timestamp("2025-06-09"),
        pd.Timestamp("2025-07-02"),
    ]


def test_trechos_partem_nas_fronteiras():
    idx = pd.bdate_range("2025-06-02", "2025-07-04")
    partes = em.trechos(idx, E)
    assert [len(p) for p in partes] == [5, 17, 3]
    assert [p[0] for p in partes] == [
        pd.Timestamp("2025-06-02"),
        pd.Timestamp("2025-06-09"),
        pd.Timestamp("2025-07-02"),
    ]


def test_trechos_sem_emissores_devolve_o_indice_inteiro():
    idx = pd.bdate_range("2025-06-02", "2025-07-04")
    for emissores in (None, emissores_de([])):
        partes = em.trechos(idx, emissores)
        assert len(partes) == 1
        assert partes[0].equals(idx)


# trocas, códigos negociados e tipos por período

def test_trocas_cobertas():
    assert em.trocas_cobertas(E) == frozenset({("JBSS3", "JBSS32"), ("NTCO3", "NATU3")})


def test_ticker_de_negociado():
    assert em.ticker_de_negociado(E) == {"JBSS3": "JBSS32", "NTCO3": "NATU3"}


def test_negociado_com_dois_tickers_fica_de_fora():
    linhas = [
        ("AAAA3", 1, "ZZZZ3", "11111111000111", "A", None, "2024-12-31", 1.0),
        ("BBBB3", 1, "ZZZZ3", "22222222000122", "B", "2025-01-01", None, 1.0),
    ]
    emissores = emissores_de(linhas)
    assert em.ticker_de_negociado(emissores) == {}
    assert em.trocas_cobertas(emissores) == frozenset({("ZZZZ3", "AAAA3"), ("ZZZZ3", "BBBB3")})


def test_tipos_por_periodo():
    assert em.tipos_por_periodo(E) == {
        "JBSS32": [(None, date(2025, 6, 8), "ON")],
        "NATU3": [(date(2019, 12, 18), date(2025, 7, 1), "ON")],
    }


# sobreposições e lacunas

def test_sem_sobreposicao_nem_lacuna_na_tabela_real():
    assert em.sobreposicoes(E) == []
    assert em.lacunas(E) == []


def test_sobreposicao_detectada():
    linhas = list(LINHAS_EMISSORES_REAIS)
    linhas[1] = ("JBSS32", 2, "JBSS32", CNPJ_JBS_NV, "JBS N.V.", "2025-06-08", None, 1.0)
    assert em.sobreposicoes(emissores_de(linhas)) == ["JBSS32: ordem 1 e ordem 2"]


def test_lacuna_detectada():
    linhas = list(LINHAS_EMISSORES_REAIS)
    linhas[4] = ("NATU3", 3, "NATU3", CNPJ_NATURA, "Natura Cosmeticos", "2025-07-05", None, 1.0)
    assert em.lacunas(emissores_de(linhas)) == ["NATU3: sem emissor de 2025-07-02 a 2025-07-04"]


# cnpj por linha

def test_cnpj_por_linha_usa_o_emissor_vigente_na_data_de_cada_linha():
    tickers = pd.Series(["JBSS32", "JBSS32", "NATU3", "NATU3", "PETR4"])
    datas = pd.Series(["2025-06-06", "2025-06-09", "2025-07-01", "2025-07-02", "2025-06-06"])
    padrao = pd.Series([CNPJ_JBS_NV, CNPJ_JBS_NV, CNPJ_NATURA, CNPJ_NATURA, "33000167000101"])
    resultado = em.cnpj_por_linha(E, tickers, datas, padrao)
    assert resultado.tolist() == [
        CNPJ_JBS_SA,
        CNPJ_JBS_NV,
        CNPJ_HOLDING,
        CNPJ_NATURA,
        "33000167000101",
    ]


def test_cnpj_por_linha_sem_emissores_devolve_o_padrao():
    padrao = pd.Series(["11111111000111", "22222222000122"], index=[5, 9])
    resultado = em.cnpj_por_linha(None, pd.Series(["JBSS32", "NATU3"]),
                                  pd.Series(["2025-06-06", "2025-06-06"]), padrao)
    assert resultado.tolist() == ["11111111000111", "22222222000122"]
    assert list(resultado.index) == [5, 9]
