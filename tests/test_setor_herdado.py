"""Setor herdado pela empresa (plano Fase 6b): ticker fora do cadastro ligado a uma empresa dele.

Casos A a E do plano (valores esperados vêm do plano). Sem banco nem rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, pregoes_uteis, precos_de, serie_por_retornos
from fabrica_experimento import noticias_de
from processamento.exclusoes import Exclusoes
from processamento.experimento.dataset import DadosExperimento, montar_dataset
from processamento.experimento.variaveis import ret_vs_setor
from processamento.fatos import precos as fatos_precos
from processamento.fatos.precos import mapas_cadastro
from processamento.tickers import mapas_por_empresa
from processamento.universo import montar_universo


SETOR_DE = {"JBSS32": "Consumo não Cíclico", "PETR4": "Petróleo", "AAAA3": "S1", "AAAB3": None}
CNPJ_DE = {"JBSS32": "C1", "PETR4": "C2", "AAAA3": "C3", "AAAB3": "C9"}


# --- A: herança pelo CNPJ e pela raiz -------------------------------------------------

def test_a_ticker_fora_do_cadastro_herda_cnpj_e_setor():
    setor_de2, cnpj_de2, herdados = mapas_por_empresa(
        ["JBSS3", "PETR3", "XPTO3", "PETR4", "AAAA4"], SETOR_DE, CNPJ_DE, {}
    )
    assert herdados == {
        "JBSS3": ("C1", "Consumo não Cíclico"),
        "PETR3": ("C2", "Petróleo"),
        "AAAA4": ("C3", "S1"),
    }
    assert "XPTO3" not in setor_de2 and "XPTO3" not in cnpj_de2
    assert setor_de2["PETR4"] == "Petróleo"
    assert setor_de2["JBSS3"] == "Consumo não Cíclico"
    # entradas intactas
    assert SETOR_DE == {"JBSS32": "Consumo não Cíclico", "PETR4": "Petróleo", "AAAA3": "S1", "AAAB3": None}
    assert CNPJ_DE == {"JBSS32": "C1", "PETR4": "C2", "AAAA3": "C3", "AAAB3": "C9"}


# --- B: raiz ambígua não herda --------------------------------------------------------

def test_b_raiz_ambigua_nao_herda():
    _, _, herdados = mapas_por_empresa(
        ["AAAA4"], {"AAAA3": "S1", "AAAA11": "S2"}, {"AAAA3": "C3", "AAAA11": "C4"}, {}
    )
    assert herdados == {}


# --- C: via mudanças de ticker --------------------------------------------------------

def test_c_via_mudanca_de_ticker():
    _, _, herdados = mapas_por_empresa(
        ["CCRO3"], {"MOTV3": "Bens Industriais"}, {"MOTV3": "C5"}, {"CCRO3": "MOTV3"}
    )
    assert herdados["CCRO3"] == ("C5", "Bens Industriais")


# --- D: CNPJ com dois setores no cadastro: sem setor ----------------------------------

def test_d_cnpj_com_dois_setores_fica_sem_setor():
    setor_de2, cnpj_de2, herdados = mapas_por_empresa(
        ["X1AA5"], {"X1AA3": "S1", "X1AA4": "S2"}, {"X1AA3": "C6", "X1AA4": "C6"}, {}
    )
    assert herdados["X1AA5"] == ("C6", None)
    assert cnpj_de2["X1AA5"] == "C6"
    assert "X1AA5" not in setor_de2


# --- E: dataset com JBSS3 herdado; ret_vs_setor usa o setor herdado -------------------

CADASTRO_E = cadastro_de([
    ("JBSS32", "C1", "S", "BDR"),
    ("AAAA3", "C5", "S", "ON"),
    ("BBBB3", "C6", "S", "ON"),
])
RETORNOS_NO_DIA = {"JBSS3": 0.01, "AAAA3": 0.02, "BBBB3": 0.04}


def _mundo_e():
    cal = pregoes_uteis(25)
    k = 20  # pregão de teste: cal[20]
    precos = []
    for ticker, r in RETORNOS_NO_DIA.items():
        rets = [0.0] * (len(cal) - 1)
        rets[k - 1] = r
        serie = serie_por_retornos(100.0, rets)
        precos.append(precos_de(ticker, cal, serie))
    precos.append(precos_de("IBOV", cal, [100.0] * len(cal)))
    precos = pd.concat(precos, ignore_index=True)
    composicao = pd.DataFrame({
        "ticker": list(RETORNOS_NO_DIA),
        "data_inicio": [pd.Timestamp(cal[0])] * 3,
        "data_fim": [pd.NaT] * 3,
    })
    universo = montar_universo(cal, CADASTRO_E, precos, Exclusoes(), composicao)
    dados = DadosExperimento(
        precos=precos,
        cadastro=CADASTRO_E,
        # sem notícia: uma linha de exemplo, depois zerada (as colunas ficam)
        noticias=noticias_de([("n0", "BBBB3", None, cal[3], 0.5, 0.2, "cvm_ipe", "protagonista", "comunicado")]).iloc[0:0],
        balancos=pd.DataFrame({
            "cnpj": pd.Series([], dtype=object),
            "tipo": pd.Series([], dtype=object),
            "data_entrega": pd.Series([], dtype="datetime64[ns]"),
        }),
        universo=universo,
        mudancas={},
    )
    return cal, k, precos, dados


def test_e_ret_vs_setor_com_setor_herdado():
    cal, k, precos, _ = _mundo_e()
    setor_de, cnpj_de = mapas_cadastro(CADASTRO_E)
    setor_de, cnpj_de, _ = mapas_por_empresa(list(RETORNOS_NO_DIA), setor_de, cnpj_de, {})
    aj = precos.pivot(index="data", columns="ticker", values="fechamento_ajustado")[list(RETORNOS_NO_DIA)]
    ret = fatos_precos.retornos_diarios(aj.astype(float))
    mascara = pd.DataFrame(True, index=ret.index, columns=list(RETORNOS_NO_DIA))
    bruto = ret_vs_setor(ret, mascara, setor_de, cnpj_de, "empresa").loc[pd.Timestamp(cal[k])]
    assert bruto["JBSS3"] == pytest.approx(0.01 - np.mean([0.02, 0.04]), abs=1e-12)
    assert bruto["AAAA3"] == pytest.approx(0.02 - np.mean([0.01, 0.04]), abs=1e-12)
    assert bruto["BBBB3"] == pytest.approx(0.04 - np.mean([0.01, 0.02]), abs=1e-12)


def test_e_dataset_setor_empresa_e_info():
    cal, k, _, dados = _mundo_e()
    df, info = montar_dataset(dados, cal)
    linha = df[(df["data"] == pd.Timestamp(cal[k])) & (df["ticker"] == "JBSS3")]
    assert len(linha) == 1
    assert linha["setor"].iloc[0] == "S"
    assert linha["empresa"].iloc[0] == "C1"
    assert info["setor_herdado"] == {"JBSS3": "S"}
