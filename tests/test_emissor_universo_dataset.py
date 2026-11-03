"""Emissor por período no universo, no dataset e nos insumos (plano T6, 03/11/2026).

JBSS32 é ação ON da JBS S.A. até 08/06/2025 e BDR da JBS N.V. depois. Com o emissor, o universo
dá o tipo do período, e o dataset liga balanços e CVM pelo `cnpj_emissor` (interno, fora do CSV).
Sem emissores, vale o cadastro. Banco de teste em SQLite; sem rede, sem banco real.
"""

import dataclasses
from datetime import date

import pandas as pd

from fabrica_emissores import CNPJ_JBS_NV, CNPJ_JBS_SA, EMISSORES_REAIS
from fabrica_experimento import noticias_de
from fabrica_fundamentos import cadastro_fund_de, documentos_de
from fabrica_precos import precos_de
from processamento.exclusoes import Exclusoes
from processamento.experimento.dataset import COLUNAS_DATASET, DadosExperimento, montar_dataset
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.saida.insumos import ler_insumos
from processamento.universo import montar_universo

CAL = [date(2025, 6, 5), date(2025, 6, 6), date(2025, 6, 9)]


def _cadastro():
    return cadastro_fund_de([("JBSS32", CNPJ_JBS_NV, "Alimentos", "Carnes", "BDR", None, None)])


def _precos():
    return pd.concat(
        [
            precos_de("JBSS32", CAL, [78.00, 78.06, 78.20]),
            precos_de("IBOV", CAL, [100.0] * 3, volume=[None] * 3),
        ],
        ignore_index=True,
    )


def _composicao():
    return pd.DataFrame({
        "ticker": ["JBSS32"],
        "data_inicio": pd.to_datetime(["2021-01-01"]),
        "data_fim": pd.to_datetime(["2025-06-08"]),
    })


def _universo(emissores):
    return montar_universo(CAL, _cadastro(), _precos(), Exclusoes(), _composicao(), emissores=emissores)


def _tipo_motivo(uni, dia):
    linha = uni.loc[(uni["ticker"] == "JBSS32") & (uni["data"] == pd.Timestamp(dia))].iloc[0]
    return linha["tipo_acao"], linha["motivo"]


# --- Universo ------------------------------------------------------------------------------

def test_universo_com_emissor_da_tipo_do_periodo():
    uni = _universo(EMISSORES_REAIS)
    assert _tipo_motivo(uni, "2025-06-05") == ("ON", "ok")
    assert _tipo_motivo(uni, "2025-06-06") == ("ON", "ok")
    assert _tipo_motivo(uni, "2025-06-09") == ("BDR", "tipo_nao_aceito")


def test_universo_sem_emissores_usa_o_tipo_do_cadastro():
    uni = _universo(None)
    for dia in ["2025-06-05", "2025-06-06", "2025-06-09"]:
        assert _tipo_motivo(uni, dia) == ("BDR", "tipo_nao_aceito")


# --- Dataset -------------------------------------------------------------------------------

def _dados(emissores):
    """Universo com o emissor (o tipo do período já está nele); `emissores` vai só ao dataset."""
    uni = _universo(EMISSORES_REAIS)
    return DadosExperimento(
        precos=_precos(),
        cadastro=_cadastro(),
        noticias=noticias_de([("n0", "JBSS32", None, CAL[0], 0.5, 0.2, "cvm_ipe", "protagonista", "comunicado")]).iloc[0:0],
        balancos=pd.DataFrame({
            "cnpj": [CNPJ_JBS_SA],
            "tipo": ["ITR"],
            "data_entrega": pd.to_datetime(["2025-06-05"]),
        }),
        universo=uni,
        mudancas={},
        documentos_cvm=documentos_de([
            ("IPE9001", CNPJ_JBS_SA, "Fato Relevante", "2025-06-05", "AP - Apresentação", 1, "2025-06-05"),
        ]),
        emissores=emissores,
    )


def _params_sem_cvm_vazia():
    return dataclasses.replace(carregar_parametros_experimento(), periodos_sem_coleta_cvm=())


def test_dataset_liga_balanco_e_cvm_pelo_emissor_do_dia():
    df, _ = montar_dataset(_dados(EMISSORES_REAIS), CAL, params=_params_sem_cvm_vazia())
    assert len(df) == 2
    assert list(df["data"].dt.date) == [CAL[0], CAL[1]]
    assert (df["empresa"] == CNPJ_JBS_NV).all()
    assert list(df["dia_resultado"]) == [True, False]
    assert list(df["fato_relevante_cvm"]) == [1.0, 0.0]
    assert "cnpj_emissor" not in df.columns
    assert list(df.columns) == COLUNAS_DATASET


def test_dataset_sem_emissores_nao_liga_balanco_nem_cvm_da_jbs_sa():
    df, _ = montar_dataset(_dados(None), CAL, params=_params_sem_cvm_vazia())
    assert (df["empresa"] == CNPJ_JBS_NV).all()
    assert list(df["dia_resultado"]) == [False, False]
    assert list(df["fato_relevante_cvm"]) == [0.0, 0.0]
    assert "cnpj_emissor" not in df.columns


# --- Insumos -------------------------------------------------------------------------------

def test_insumos_leem_os_emissores_do_banco_de_teste(banco_teste):
    ins = ler_insumos(date(2025, 10, 22), banco_teste(), existe_composicao=False)  # banco_teste() = leitor
    assert ins.emissores is not None
    assert len(ins.emissores) == 7
