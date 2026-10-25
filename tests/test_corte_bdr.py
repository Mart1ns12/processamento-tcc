"""Corte da série na troca de ação por BDR (plano Fase 9): antes da data da mudança, o ticker novo
(BDR) vale como o antigo (ação). Casos 9A a 9G do plano; valores esperados vêm do plano.

Banco de teste em SQLite (fixture `banco_teste`). Sem rede, sem banco real.
"""

from datetime import date

import pandas as pd
import pytest

from fabrica_experimento import noticias_de
from processamento import calendario, fontes, tickers
from processamento.exclusoes import Exclusoes
from processamento.experimento.dataset import DadosExperimento, montar_dataset
from processamento.fatos.precos import grade_de_precos, retornos_diarios, retornos_suspeitos
from processamento.universo import montar_universo


# --- 9A: aplicar_cortes (pura) ----------------------------------------------------------

def _precos_jbss32_df():
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2025-06-05", "2025-06-06", "2025-06-09"]),
            "ticker": ["JBSS32", "JBSS32", "JBSS32"],
            "fechamento": [38.290001, 39.029999, 78.199997],
            "fechamento_ajustado": [35.880646, 36.574078, 73.279350],
        }
    )


def test_9a_aplicar_cortes_troca_so_as_linhas_anteriores_a_data():
    df = _precos_jbss32_df()
    out = tickers.aplicar_cortes(df, [("JBSS3", "JBSS32", date(2025, 6, 9))], "data")
    assert out["ticker"].tolist() == ["JBSS3", "JBSS3", "JBSS32"]
    assert out["fechamento"].tolist() == [38.290001, 39.029999, 78.199997]
    assert out["fechamento_ajustado"].tolist() == [35.880646, 36.574078, 73.279350]


def test_9a_aplicar_cortes_nao_altera_a_entrada():
    df = _precos_jbss32_df()
    tickers.aplicar_cortes(df, [("JBSS3", "JBSS32", date(2025, 6, 9))], "data")
    assert df["ticker"].tolist() == ["JBSS32", "JBSS32", "JBSS32"]


# --- 9F: sem data, ou troca ação -> ação, não gera corte -------------------------------

def test_9f_troca_sem_data_nao_gera_corte():
    mudancas = pd.DataFrame(
        {
            "ticker_antigo": ["JBSS3"],
            "ticker_novo": ["JBSS32"],
            "data_mudanca": pd.to_datetime([None]),
        }
    )
    assert tickers.cortes_acao_para_bdr(mudancas, {"JBSS32": "BDR"}) == []


def test_9f_troca_acao_para_acao_nao_gera_corte():
    mudancas = pd.DataFrame(
        {
            "ticker_antigo": ["CCRO3", "JBSS3"],
            "ticker_novo": ["MOTV3", "JBSS32"],
            "data_mudanca": pd.to_datetime(["2025-05-02", "2025-06-09"]),
        }
    )
    cortes = tickers.cortes_acao_para_bdr(mudancas, {"MOTV3": "ON", "JBSS32": "BDR"})
    assert cortes == [("JBSS3", "JBSS32", date(2025, 6, 9))]


# --- Banco de teste: JBSS32 com o histórico inteiro, como a coleta grava ----------------

PRECOS_JBSS32 = {
    "2025-06-05": ("38.290001", "35.880646"),
    "2025-06-06": ("39.029999", "36.574078"),
    "2025-06-09": ("78.199997", "73.279350"),
}


def _precos_jbss32(df):
    linhas = []
    for data, (fech, aj) in PRECOS_JBSS32.items():
        linhas.append({"data": data, "ticker": "JBSS32", "abertura": fech, "maxima": fech,
                       "minima": fech, "fechamento": fech, "fechamento_ajustado": aj, "volume": "1000"})
        linhas.append({"data": data, "ticker": "IBOV", "abertura": "100.00", "maxima": "100.00",
                       "minima": "100.00", "fechamento": "100.00", "fechamento_ajustado": "100.00",
                       "volume": None})
    return pd.concat([df, pd.DataFrame(linhas)], ignore_index=True)


def _mudancas_jbs_com_data(df):
    extra = pd.DataFrame({"ticker_antigo": ["JBSS3"], "ticker_novo": ["JBSS32"], "data_mudanca": ["2025-06-09"]})
    return pd.concat([df, extra], ignore_index=True)


def _mudancas_jbs_sem_data(df):
    extra = pd.DataFrame({"ticker_antigo": ["JBSS3"], "ticker_novo": ["JBSS32"], "data_mudanca": [None]})
    return pd.concat([df, extra], ignore_index=True)


def _noticias_jbs32(df):
    base = df.iloc[[0]]
    extras = []
    for id_, data, hora in [
        ("nj1", "2025-06-01", "2025-06-01T12:00:00-03:00"),
        ("nj2", "2025-06-10", "2025-06-10T12:00:00-03:00"),
    ]:
        linha = base.copy()
        linha["id"] = id_
        linha["ticker"] = "JBSS32"
        linha["data_publicacao"] = data
        linha["data_hora_publicacao"] = hora
        extras.append(linha)
    return pd.concat([df, *extras], ignore_index=True)


@pytest.fixture
def ler_corte(banco_teste):
    return banco_teste(alterar={
        "v1-precos": _precos_jbss32,
        "v1-mudancas_ticker": _mudancas_jbs_com_data,
        "v1-noticias": _noticias_jbs32,
    })


# --- 9B: retorno suspeito antes e depois do corte ---------------------------------------

def test_9b_antes_do_corte_jbss32_tem_retorno_suspeito(ler_corte):
    bruto = fontes.ler_tabela("precos", ler=ler_corte, unir_mudancas=False)
    g = grade_de_precos(bruto, calendario.pregoes(bruto), "fechamento_ajustado", ["JBSS32"])
    assert bool(retornos_suspeitos(g, -0.75, 1.0).loc[pd.Timestamp("2025-06-09"), "JBSS32"])


def test_9b_depois_do_corte_nao_ha_retorno_suspeito(ler_corte):
    p = fontes.ler_tabela("precos", ler=ler_corte)
    g = grade_de_precos(p, calendario.pregoes(p), "fechamento_ajustado", ["JBSS3", "JBSS32"])
    # Só até a troca: o precos.csv das fixtures tem um JBSS32 de out/2025 (10,00) que não é deste caso.
    assert not retornos_suspeitos(g, -0.75, 1.0).loc[:pd.Timestamp("2025-06-09")].to_numpy().any()
    ret = retornos_diarios(g)
    assert ret.loc[pd.Timestamp("2025-06-06"), "JBSS3"] == pytest.approx(
        36.574078 / 35.880646 - 1, abs=1e-6
    )
    assert pd.isna(ret.loc[pd.Timestamp("2025-06-09"), "JBSS32"])


# --- 9C: universo histórico ---------------------------------------------------------------

def test_9c_universo_jbs3_ate_a_data_da_mudanca(ler_corte):
    p = fontes.ler_tabela("precos", ler=ler_corte)
    comp = pd.DataFrame(
        {
            "ticker": ["JBSS3"],
            "data_inicio": pd.to_datetime(["2021-01-01"]),
            "data_fim": pd.to_datetime(["2025-06-08"]),
        }
    )
    uni = montar_universo(
        calendario.pregoes(p), fontes.ler_tabela("cadastro", ler=ler_corte), p, Exclusoes(), comp
    )
    dia = uni.assign(dia=uni["data"].dt.strftime("%Y-%m-%d"))
    jbs3 = dia[dia["ticker"] == "JBSS3"].set_index("dia")
    assert jbs3.loc["2025-06-06", "tipo_acao"] == "ON"
    assert jbs3.loc["2025-06-06", "motivo"] == "ok"
    assert jbs3.loc["2025-06-09", "motivo"] == "fora_da_composicao"
    jbss32 = dia[(dia["ticker"] == "JBSS32") & dia["dia"].isin(["2025-06-05", "2025-06-06", "2025-06-09"])]
    assert set(jbss32["motivo"]) == {"tipo_nao_aceito"}


# --- 9D: setor herdado e CNPJ no dataset -------------------------------------------------

def test_9d_dataset_jbss3_herda_setor_e_cnpj_do_jbss32(ler_corte):
    cal = [date(2025, 6, 5), date(2025, 6, 6), date(2025, 6, 9)]
    p = fontes.ler_tabela("precos", ler=ler_corte)
    cadastro = fontes.ler_tabela("cadastro", ler=ler_corte)
    mudancas = fontes.ler_mudancas(ler_corte)
    comp = pd.DataFrame(
        {
            "ticker": ["JBSS3"],
            "data_inicio": pd.to_datetime(["2021-01-01"]),
            "data_fim": pd.to_datetime(["2025-06-08"]),
        }
    )
    universo = montar_universo(cal, cadastro, p, Exclusoes(), comp)
    dados = DadosExperimento(
        precos=p,
        cadastro=cadastro,
        noticias=noticias_de([("n0", "JBSS3", None, cal[0], 0.5, 0.2, "cvm_ipe", "protagonista", "comunicado")]).iloc[0:0],
        balancos=pd.DataFrame({
            "cnpj": pd.Series([], dtype=object),
            "tipo": pd.Series([], dtype=object),
            "data_entrega": pd.Series([], dtype="datetime64[ns]"),
        }),
        universo=universo,
        mudancas=mudancas,
    )
    df, info = montar_dataset(dados, cal)
    assert info["setor_herdado"] == {"JBSS3": "Alimentos"}
    linha = df[(df["data"] == pd.Timestamp("2025-06-06")) & (df["ticker"] == "JBSS3")]
    assert len(linha) == 1
    assert linha["empresa"].iloc[0] == "22222222000122"


# --- 9E: notícias ------------------------------------------------------------------------

def test_9e_noticia_jbss32_antes_do_corte_vira_jbss3(ler_corte):
    n = fontes.ler_noticias(ler=ler_corte)
    ids = n.set_index("id")["ticker"]
    assert ids["nj1"] == "JBSS3"
    assert ids["nj2"] == "JBSS32"


# --- 9F (banco): mudança sem data não corta a série --------------------------------------

def test_9f_banco_sem_data_nao_corta(banco_teste):
    ler = banco_teste(alterar={"v1-mudancas_ticker": _mudancas_jbs_sem_data})
    assert fontes.ler_cortes_bdr(ler) == []
    p = fontes.ler_tabela("precos", ler=ler)
    pd.testing.assert_frame_equal(p, fontes.ler_tabela("precos", ler=ler, unir_mudancas=False))


# --- 9G: leitura da tabela com o corte aplicado -----------------------------------------

def test_9g_ler_precos_aplica_o_corte(ler_corte):
    p = fontes.ler_tabela("precos", ler=ler_corte)
    jbs3 = p[p["ticker"] == "JBSS3"]
    assert jbs3["data"].dt.strftime("%Y-%m-%d").tolist() == ["2025-06-05", "2025-06-06"]
    assert jbs3["fechamento"].tolist() == pytest.approx([38.290001, 39.029999])
    jbss32 = p[(p["ticker"] == "JBSS32") & (p["data"] <= pd.Timestamp("2025-06-09"))]
    assert jbss32["data"].dt.strftime("%Y-%m-%d").tolist() == ["2025-06-09"]
    assert jbss32["fechamento"].tolist() == pytest.approx([78.199997])
