"""Troca de ação por BDR não une os históricos (seção 6 da especificação; plano Fase 6).

Valores esperados vêm do plano (casos 6A a 6C). Banco de teste em SQLite (fixture `banco_teste`).
"""

import pandas as pd
import pytest

from processamento import calendario, fontes, tickers
from processamento.exclusoes import Exclusoes
from processamento.experimento.noticias import ligar_empresa
from processamento.fatos.precos import grade_de_precos, mapas_cadastro, retornos_suspeitos
from processamento.fatos.proventos import _do_ticker, ligar_proventos
from processamento.universo import montar_universo
from fabrica_fundamentos import proventos_de


# --- 6A: regra pura -------------------------------------------------------------

@pytest.mark.parametrize(
    "antigo, novo, tipo_de, esperado",
    [
        ("JBSS3", "JBSS32", {"JBSS32": "BDR"}, True),
        ("JBSS3", "JBSS32", {}, True),
        ("CCRO3", "MOTV3", {"MOTV3": "ON"}, False),
        ("ELET6", "AXIA3", {}, False),
        ("XPTO3", "XPTO34", {}, True),
        ("XPTO3", "XPTO34", {"XPTO34": "ON"}, False),
        ("AAAA11", "AAAA34", {}, True),
        ("XPTO32", "XPTO3", {}, False),
        ("XPTO3", "XPTO3F", {}, False),
    ],
)
def test_troca_acao_para_bdr(antigo, novo, tipo_de, esperado):
    assert tickers.troca_acao_para_bdr(antigo, novo, tipo_de) is esperado


# --- 6B: mudancas_como_dict ------------------------------------------------------

def test_mudancas_como_dict_tira_troca_para_bdr():
    df = pd.DataFrame(
        {
            "ticker_antigo": ["JBSS3", "CCRO3", "ELET3"],
            "ticker_novo": ["JBSS32", "MOTV3", "AXIA3"],
            "data_mudanca": ["2025-06-09", "2025-05-02", "2025-11-10"],
        }
    )
    tipo_de = {"JBSS32": "BDR", "MOTV3": "ON", "AXIA3": "ON"}
    assert fontes.mudancas_como_dict(df, tipo_de) == {"CCRO3": "MOTV3", "ELET3": "AXIA3"}
    assert fontes.mudancas_como_dict(df, None) == {"CCRO3": "MOTV3", "ELET3": "AXIA3"}


# --- 6C: banco de teste com JBSS3 -> JBSS32 em 2025-10-20 ------------------------

def _precos_jbs(df):
    df = df.copy()
    antigo = (df["ticker"] == "JBSS32") & df["data"].isin(["2025-10-16", "2025-10-17"])
    df.loc[antigo, "ticker"] = "JBSS3"
    for c in ("abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"):
        df.loc[antigo, c] = "50.00"
    return df


def _mudancas_jbs(df):
    extra = pd.DataFrame({"ticker_antigo": ["JBSS3"], "ticker_novo": ["JBSS32"], "data_mudanca": ["2025-10-20"]})
    return pd.concat([df, extra], ignore_index=True)


@pytest.fixture
def ler_jbs(banco_teste):
    return banco_teste(alterar={"v1-precos": _precos_jbs, "v1-mudancas_ticker": _mudancas_jbs})


def test_ler_mudancas_sem_a_troca_para_bdr(ler_jbs):
    assert fontes.ler_mudancas(ler_jbs) == {"ELET3": "AXIA3", "ELET6": "AXIA6"}


def test_precos_jbs3_e_jbss32_nao_se_unem(ler_jbs):
    p = fontes.ler_tabela("precos", ler=ler_jbs)
    assert len(p) == 30
    datas = pd.to_datetime(p["data"])
    jbs3 = p[p["ticker"] == "JBSS3"].assign(d=datas).sort_values("d")
    assert jbs3["d"].dt.strftime("%Y-%m-%d").tolist() == ["2025-10-16", "2025-10-17"]
    assert jbs3["fechamento"].astype(float).tolist() == [50.0, 50.0]
    jbss32 = p[p["ticker"] == "JBSS32"].assign(d=datas).sort_values("d")
    assert jbss32["d"].dt.strftime("%Y-%m-%d").tolist() == ["2025-10-20", "2025-10-21"]
    assert jbss32["fechamento"].astype(float).tolist() == [10.0, 10.0]


def test_retorno_suspeito_de_jbss32_some_com_a_regra(ler_jbs):
    p = fontes.ler_tabela("precos", ler=ler_jbs)
    g = grade_de_precos(p, calendario.pregoes(p), "fechamento_ajustado", ["JBSS3", "JBSS32"])
    assert not retornos_suspeitos(g, -0.75, 1.0).to_numpy().any()


def test_universo_jbs3_depois_do_corte_fora_da_composicao(ler_jbs):
    p = fontes.ler_tabela("precos", ler=ler_jbs)
    comp = pd.DataFrame(
        {
            "ticker": ["JBSS3", "JBSS32", "PETR4"],
            "data_inicio": pd.to_datetime(["2025-10-16", "2025-10-20", "2025-10-16"]),
            "data_fim": pd.to_datetime(["2025-10-17", None, None]),
        }
    )
    uni = montar_universo(
        calendario.pregoes(p), fontes.ler_tabela("cadastro", ler=ler_jbs), p, Exclusoes(), comp
    )
    jbs3 = uni[uni["ticker"] == "JBSS3"].assign(dia=uni["data"].dt.strftime("%Y-%m-%d")).set_index("dia")
    assert jbs3.loc["2025-10-16", "tipo_acao"] == "ON"
    assert jbs3.loc["2025-10-16", "motivo"] == "ok"
    assert jbs3.loc["2025-10-17", "motivo"] == "ok"
    assert jbs3.loc["2025-10-20", "motivo"] == "fora_da_composicao"
    assert jbs3.loc["2025-10-21", "motivo"] == "fora_da_composicao"
    jbss32 = uni[uni["ticker"] == "JBSS32"]
    assert set(jbss32["motivo"]) == {"tipo_nao_aceito"}


def test_jbs3_liga_a_empresa_jbs_pela_raiz(ler_jbs):
    cadastro = fontes.ler_tabela("cadastro", ler=ler_jbs)
    cnpj_de = mapas_cadastro(cadastro)[1]
    mudancas = fontes.ler_mudancas(ler_jbs)
    assert tickers.ligar_a_cnpj("JBSS3", cnpj_de, mudancas) == ("22222222000122", "raiz")


def test_provento_jbs3_fica_com_jbs3_e_nao_vai_para_jbss32(ler_jbs):
    cadastro = fontes.ler_tabela("cadastro", ler=ler_jbs)
    mudancas = fontes.ler_mudancas(ler_jbs)
    prov = proventos_de([("JBSS3", "DIVIDENDO", "2025-10-10", 0.5, None)])
    ligados = ligar_proventos(prov, cadastro, mudancas)
    linha = ligados.iloc[0]
    assert linha["ticker_atual"] == "JBSS3"
    assert linha["cnpj"] == "22222222000122"
    assert linha["ligacao"] == "raiz"
    assert linha["tipo_classe"] == "ON"
    assert _do_ticker(ligados, "JBSS32").empty


def test_noticia_jbs3_vale_para_a_empresa_jbs(ler_jbs):
    cadastro = fontes.ler_tabela("cadastro", ler=ler_jbs)
    cnpj_de = mapas_cadastro(cadastro)[1]
    mudancas = fontes.ler_mudancas(ler_jbs)
    out = ligar_empresa(pd.DataFrame({"ticker": ["JBSS3"]}), cnpj_de, mudancas)
    assert out["empresa"].tolist() == ["22222222000122"]
