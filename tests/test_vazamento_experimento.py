"""Vazamento temporal do dataset do experimento (plano da etapa 5, fase 8).

Nada depois de t pode mudar as linhas de t, exceto o alvo (que olha t+1). Cenários: "cortado"
(só o que se saberia no fim de t) e "cheio e alterado" (futuro de t mudado: preços ×3, volumes
×10, notícias após 08:00 de t1 com pp e pn trocados, notícias novas, cvm_ipe e balanço em t1).
Nenhum teste usa banco ou rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_experimento import CADASTRO_MUNDO, alterado, cortado, dados_de, mundo
from processamento.experimento.dataset import montar_dataset
from processamento.experimento.preparacao import (
    COLUNAS_ALVO,
    COMPLEMENTARES_PRECO,
    ESSENCIAIS_PRECO,
    preparar,
)

PRECO = ESSENCIAIS_PRECO + COMPLEMENTARES_PRECO  # as 13 colunas de preço e volume


def _linhas(df, d):
    """Linhas do pregão d, sem as colunas de alvo, com índice reiniciado."""
    return df[df["data"] == pd.Timestamp(d)].drop(columns=COLUNAS_ALVO).reset_index(drop=True)


def _valor(df, d, ticker, coluna):
    linha = df[(df["data"] == pd.Timestamp(d)) & (df["ticker"] == ticker)]
    assert len(linha) == 1
    return linha[coluna].iloc[0]


@pytest.fixture(scope="module")
def cenario():
    m = mundo()
    t, t1 = m["t"], m["t1"]
    c = cortado(m)
    a = alterado(m)
    df_cortado, _ = montar_dataset(
        dados_de(c["cal"], c["precos"], CADASTRO_MUNDO, c["noticias"], c["balancos"]),
        c["cal"],
        proximo_ao_vivo=t1,
    )
    df_cheio, _ = montar_dataset(
        dados_de(m["cal"], m["precos"], CADASTRO_MUNDO, m["noticias"], m["balancos"]), m["cal"]
    )
    df_alterado, _ = montar_dataset(
        dados_de(a["cal"], a["precos"], CADASTRO_MUNDO, a["noticias"], a["balancos"]), a["cal"]
    )
    sem_f4 = m["noticias"][m["noticias"]["id"] != "f4"]
    df_sem_f4, _ = montar_dataset(
        dados_de(m["cal"], m["precos"], CADASTRO_MUNDO, sem_f4, m["balancos"]), m["cal"]
    )
    return {
        "t": t,
        "t1": t1,
        "df_cortado": df_cortado,
        "df_cheio": df_cheio,
        "df_alterado": df_alterado,
        "df_sem_f4": df_sem_f4,
    }


def test_linhas_de_t_iguais_sem_alvo(cenario):
    t = cenario["t"]
    pd.testing.assert_frame_equal(
        _linhas(cenario["df_cortado"], t),
        _linhas(cenario["df_alterado"], t),
        rtol=1e-12,
        atol=1e-12,
    )


def test_so_data_de_t1_nao_entra_em_t(cenario):
    # f4 é "só data" de t1 (04:00 SP): vai para o dia de t1, nunca para o de t
    t = cenario["t"]
    pd.testing.assert_frame_equal(
        _linhas(cenario["df_sem_f4"], t),
        _linhas(cenario["df_cheio"], t),
        rtol=1e-12,
        atol=1e-12,
    )


def test_so_data_de_t1_entra_no_dia_de_t1(cenario):
    t1 = cenario["t1"]
    com_f4 = _valor(cenario["df_cheio"], t1, "AAAA3", "noticias_dia_qtd")
    sem_f4 = _valor(cenario["df_sem_f4"], t1, "AAAA3", "noticias_dia_qtd")
    assert com_f4 == sem_f4 + 1


def test_linhas_de_t_iguais_depois_de_preparar(cenario):
    t = cenario["t"]
    prep_cortado = preparar(cenario["df_cortado"])
    prep_alterado = preparar(cenario["df_alterado"])
    pd.testing.assert_frame_equal(
        _linhas(prep_cortado, t),
        _linhas(prep_alterado, t),
        rtol=1e-12,
        atol=1e-12,
    )


def test_noticias_de_t_existem_e_alvo_olha_o_futuro(cenario):
    t = cenario["t"]
    assert _valor(cenario["df_cortado"], t, "AAAA3", "noticias_dia_qtd") > 0
    assert _valor(cenario["df_alterado"], t, "AAAA3", "noticias_dia_qtd") > 0
    assert pd.isna(_valor(cenario["df_cortado"], t, "AAAA3", "alvo"))
    assert _valor(cenario["df_cheio"], t, "AAAA3", "alvo") in (0.0, 1.0)
    assert _valor(cenario["df_alterado"], t, "AAAA3", "alvo") in (0.0, 1.0)


def test_alteracao_mexeu_no_dia_seguinte(cenario):
    # prova de que a alteração realmente mudou o futuro: o tom do dia de t1 muda e t1 ganha balanço
    t1 = cenario["t1"]
    antes = _valor(cenario["df_cheio"], t1, "AAAA3", "noticias_dia_tom")
    depois = _valor(cenario["df_alterado"], t1, "AAAA3", "noticias_dia_tom")
    assert not np.isclose(antes, depois, rtol=1e-9, atol=1e-12)
    assert bool(_valor(cenario["df_alterado"], t1, "AAAA3", "dia_resultado"))
    assert not bool(_valor(cenario["df_cheio"], t1, "AAAA3", "dia_resultado"))


def test_regravacao_do_ajustado_nao_muda_precos_de_t():
    m = mundo()
    t = m["t"]
    precos = m["precos"].copy()
    antes = precos["data"] <= pd.Timestamp(t)
    mascara = antes & (precos["ticker"] == "AAAA3")
    precos.loc[mascara, "fechamento_ajustado"] = precos.loc[mascara, "fechamento_ajustado"] * 0.97
    df_original, _ = montar_dataset(
        dados_de(m["cal"], m["precos"], CADASTRO_MUNDO, m["noticias"], m["balancos"]), m["cal"]
    )
    df_regravado, _ = montar_dataset(
        dados_de(m["cal"], precos, CADASTRO_MUNDO, m["noticias"], m["balancos"]), m["cal"]
    )
    pd.testing.assert_frame_equal(
        _linhas(df_original, t)[["data", "ticker", *PRECO]],
        _linhas(df_regravado, t)[["data", "ticker", *PRECO]],
        rtol=1e-9,
        atol=1e-12,
    )
