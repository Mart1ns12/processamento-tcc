"""Testes de experimento/dataset.py (etapa 5, fase 8): montagem do dataset em um mundo pequeno.

Tickers fictícios e casos exatos (tests/fabrica_experimento.py). Nenhum teste usa banco ou rede.
"""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from fabrica_experimento import (
    CADASTRO_INTEGRACAO,
    CADASTRO_MUNDO,
    EXCLUSOES_INTEGRACAO,
    dados_de,
    integracao,
    mundo,
)
from fabrica_precos import indices_de, pregoes_uteis
from processamento.exclusoes import Exclusoes
from processamento.experimento.dataset import COLUNAS_DATASET, DadosExperimento, montar_dataset
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.experimento.preparacao import COLUNAS_ALVO, COLUNAS_BRUTAS, VERSAO_PREPARACAO, preparar
from processamento.experimento.tom import COLUNAS_NOTICIAS
from processamento.universo import montar_universo


@pytest.fixture(scope="module")
def caso():
    i = integracao()
    dados = dados_de(
        i["cal"], i["precos"], CADASTRO_INTEGRACAO, i["noticias"], i["balancos"], EXCLUSOES_INTEGRACAO
    )
    df, info = montar_dataset(dados, i["cal"])
    return {"cal": i["cal"], "dados": dados, "df": df, "info": info}


def _dia(df, d, ticker=None):
    """Linhas do pregão d (ou só a de `ticker`)."""
    m = df["data"] == pd.Timestamp(d)
    if ticker is not None:
        m &= df["ticker"] == ticker
    return df[m]


def test_linhas_so_do_universo_do_modelo(caso):
    df = caso["df"]
    assert len(df) == 89  # AAAA3 e AAAA4 (30 cada) + BBBB3 (29: sem preço em cal[10])
    assert set(df["ticker"]) == {"AAAA3", "AAAA4", "BBBB3"}
    assert not df["ticker"].isin(["BDRX34", "CRFB3"]).any()
    assert _dia(df, caso["cal"][10], "BBBB3").empty
    assert not df.duplicated(["data", "ticker"]).any()


def test_colunas_e_mapeamento_de_notícias(caso):
    df = caso["df"]
    assert list(df.columns) == COLUNAS_DATASET
    assert set(COLUNAS_NOTICIAS) == set(COLUNAS_BRUTAS) | {"noticias_dia_qtd"}
    assert set(df["universo"]) == {"composicao_atual"}
    assert df["dia_resultado"].dtype == bool


def test_empresa_e_setor(caso):
    df, c = caso["df"], caso["cal"]
    assert _dia(df, c[5], "AAAA4")["empresa"].iloc[0] == "1"
    assert _dia(df, c[5], "BBBB3")["empresa"].iloc[0] == "2"
    assert _dia(df, c[5], "BBBB3")["setor"].iloc[0] == "S1"


def test_info_das_fases_3_e_6(caso):
    info = caso["info"]
    assert info["linhas"] == 89
    assert info["pregoes"] == 30
    assert info["versao_noticias"] == "todas"
    assert info["cobertura_inicio"] == caso["cal"][3].isoformat()
    assert info["sem_horario"] == 1
    assert info["preparadas"] == 2
    assert info["sem_probabilidade"] == 0
    assert info["sem_data"] == 0
    assert info["fora"] == 0


def test_noticias_de_cal_0_a_2_sao_nan(caso):
    df, c = caso["df"], caso["cal"]
    antes = df[df["data"].isin([pd.Timestamp(c[k]) for k in range(3)])]
    assert antes["noticias_dia_qtd"].isna().all()


def test_noticias_dia_de_cal_20(caso):
    df, c = caso["df"], caso["cal"]
    for t in ["AAAA3", "AAAA4"]:
        linha = _dia(df, c[20], t).iloc[0]
        assert linha["noticias_dia_qtd"] == 1
        assert linha["noticias_dia_tom"] == pytest.approx(0.6, abs=1e-9)
    bbbb = _dia(df, c[20], "BBBB3").iloc[0]
    assert bbbb["noticias_dia_qtd"] == 0
    assert pd.isna(bbbb["noticias_dia_tom"])
    assert bbbb["tom_setor"] == pytest.approx(0.6, abs=1e-9)
    for t in ["AAAA3", "AAAA4", "BBBB3"]:
        assert _dia(df, c[20], t).iloc[0]["tom_mercado"] == pytest.approx(0.6, abs=1e-9)


def test_versao_principais_so_muda_colunas_de_noticia(caso):
    principais, info = montar_dataset(caso["dados"], caso["cal"], versao_noticias="principais")
    assert info["versao_noticias"] == "principais"
    c = caso["cal"]
    # a notícia de AAAA4 (sem papel) sai da versão principal; a noite de cal[20] fica sem notícia
    assert _dia(principais, c[20], "AAAA3").iloc[0]["noticias_dia_qtd"] == 0
    fora_das_noticias = [col for col in COLUNAS_DATASET if col not in COLUNAS_NOTICIAS]
    pd.testing.assert_frame_equal(caso["df"][fora_das_noticias], principais[fora_das_noticias])


def test_versao_hora_real_noite(caso):
    df, info = montar_dataset(caso["dados"], caso["cal"], versao_noticias="hora_real_noite")
    c = caso["cal"]
    assert info["inicio_janela_efetivo"] == "fechamento" and info["preparadas"] == 1 and info["fora_versao"] == 1
    assert _dia(df, c[3], "BBBB3").iloc[0]["noticias_dia_qtd"] == 0      # em "todas" é 1
    for t in ["AAAA3", "AAAA4"]:
        assert _dia(df, c[20], t).iloc[0]["noticias_dia_qtd"] == 1
        assert _dia(df, c[20], t).iloc[0]["noticias_dia_tom"] == pytest.approx(0.6, abs=1e-9)
    fora = [col for col in COLUNAS_DATASET if col not in COLUNAS_NOTICIAS]
    pd.testing.assert_frame_equal(caso["df"][fora], df[fora])


def test_versao_invalida_levanta(caso):
    with pytest.raises(ValueError):
        montar_dataset(caso["dados"], caso["cal"], versao_noticias="xyz")


def test_dia_resultado(caso):
    df, c = caso["df"], caso["cal"]
    assert bool(_dia(df, c[5], "AAAA3").iloc[0]["dia_resultado"])
    assert bool(_dia(df, c[5], "AAAA4").iloc[0]["dia_resultado"])
    assert not bool(_dia(df, c[5], "BBBB3").iloc[0]["dia_resultado"])
    assert not bool(_dia(df, c[6], "AAAA3").iloc[0]["dia_resultado"])


def test_rank_so_no_universo_do_modelo(caso):
    # BDRX34 e CRFB3 subiram 50% em cal[15]. Se entrassem no rank, AAAA3/AAAA4/BBBB3 não
    # ocupariam 0, 0,5 e 1 (o maior seria 1/3 ou menos).
    c = caso["cal"]
    p = preparar(caso["df"])
    no_dia = p[p["data"] == pd.Timestamp(c[15])]
    assert sorted(no_dia["ret_1d"]) == pytest.approx([0.0, 0.5, 1.0], abs=1e-12)
    assert _dia(p, c[15], "BBBB3")["ret_1d"].iloc[0] == pytest.approx(1.0, abs=1e-12)

    sem_bbbb = p[p["data"] == pd.Timestamp(c[10])]
    assert sorted(sem_bbbb["ret_1d"]) == pytest.approx([0.0, 1.0], abs=1e-12)


def test_ultima_data_sem_alvo_com_ret_1d(caso):
    df, c = caso["df"], caso["cal"]
    ultimo = _dia(df, c[-1])
    assert ultimo["alvo"].isna().all()
    assert ultimo["ret_1d"].notna().all()


def test_alvo_em_zero_um_ou_nan(caso):
    alvo = caso["df"]["alvo"].dropna()
    assert set(alvo.unique()) <= {0.0, 1.0}


def test_colunas_de_alvo_presentes(caso):
    assert set(COLUNAS_ALVO) <= set(caso["df"].columns)


def test_noite_do_ultimo_pregao_aberta_sem_proximo_ao_vivo(caso):
    # Sem proximo_ao_vivo, a noite do último pregão está aberta: as colunas da noite ficam NaN.
    df, c = caso["df"], caso["cal"]
    assert _dia(df, c[-1])["noticias_dia_qtd"].isna().all()


def test_noite_do_ultimo_pregao_fechada_com_proximo_ao_vivo(caso):
    # Com proximo_ao_vivo, a noite está fechada: sem notícia, qtd = 0 (não NaN) em cobertura.
    c = caso["cal"]
    proximo = pregoes_uteis(31, "2026-05-04")[30]
    fechado, _ = montar_dataset(caso["dados"], c, proximo_ao_vivo=proximo)
    bbbb = _dia(fechado, c[-1], "BBBB3").iloc[0]
    assert bbbb["noticias_dia_qtd"] == 0


def test_universo_historico_gera_o_rotulo_da_composicao():
    i = integracao()
    cal = i["cal"]
    composicao = pd.DataFrame({
        "ticker": ["AAAA3", "AAAA4", "BBBB3"],
        "data_inicio": [pd.Timestamp(cal[0]), pd.Timestamp(cal[0]), pd.Timestamp(cal[12])],
        "data_fim": [pd.NaT, pd.NaT, pd.NaT],
    })
    universo = montar_universo(cal, CADASTRO_INTEGRACAO, i["precos"], EXCLUSOES_INTEGRACAO, composicao)
    dados = DadosExperimento(
        precos=i["precos"],
        cadastro=CADASTRO_INTEGRACAO,
        noticias=i["noticias"],
        balancos=i["balancos"],
        universo=universo,
        mudancas={},
    )
    df, _ = montar_dataset(dados, cal)
    assert set(df["universo"]) == {"composicao_historica"}
    assert len(df) == 30 + 30 + 18  # BBBB3 só a partir de cal[12] (e com preço)
    assert _dia(df, cal[11], "BBBB3").empty
    assert _dia(df, cal[12], "BBBB3").shape[0] == 1


def test_sem_bdr_e_exclusao_saem_do_universo_do_modelo():
    i = integracao()
    universo = montar_universo(i["cal"], CADASTRO_INTEGRACAO, i["precos"], Exclusoes(tickers_excluidos={"CRFB3": "x"}))
    motivos = universo.groupby("ticker")["motivo"].unique()
    assert set(motivos["BDRX34"]) == {"tipo_nao_aceito"}
    assert set(motivos["CRFB3"]) == {"excluido_por_decisao"}


def test_sem_probabilidade_conta_as_preparadas_com_score_vazio(caso):
    # Sem probabilidade do FinBERT, as duas notícias preparadas ficam com score NaN (tratadas como ausentes).
    noticias = caso["dados"].noticias.assign(prob_positivo=np.nan)
    dados = dataclasses.replace(caso["dados"], noticias=noticias)
    _, info = montar_dataset(dados, caso["cal"])
    assert info["preparadas"] == 2
    assert info["sem_probabilidade"] == 2


def test_periodo_sem_coleta_deixa_noticias_vazias_e_conta_no_info(caso):
    cal = caso["cal"]
    params = dataclasses.replace(
        carregar_parametros_experimento(), periodos_sem_coleta=((cal[20], cal[21]),)
    )
    df, info = montar_dataset(caso["dados"], cal, params=params)
    assert info["pregoes_sem_coleta"] == 2
    dentro = df[df["data"].isin([pd.Timestamp(cal[20]), pd.Timestamp(cal[21])])]
    assert len(dentro) > 0 and dentro[COLUNAS_NOTICIAS].isna().all(axis=None)
    assert df.loc[df["data"] == pd.Timestamp(cal[19]), "noticias_dia_qtd"].notna().all()
    # preço e alvo não mudam
    assert dentro["ret_1d"].notna().any()


def test_info_traz_a_versao_de_preparacao_e_o_csv_guarda_a_qtd_bruta(caso):
    assert caso["info"]["versao_preparacao"] == VERSAO_PREPARACAO
    assert len(COLUNAS_DATASET) == len(set(COLUNAS_DATASET)) == 41
    qtd = caso["df"]["noticias_dia_qtd"].dropna()
    assert (qtd == qtd.round()).all() and qtd.max() >= 1   # contagem bruta: o rank só vem em `preparar`


# ---------------------------------------------------------------- SMLL ausente (exposicao_small)


def _montar_mundo(m, indices):
    return montar_dataset(
        dados_de(m["cal"], m["precos"], CADASTRO_MUNDO, m["noticias"], m["balancos"], indices=indices), m["cal"]
    )


def test_smll_ausente_no_dataset_inteiro_so_zera_exposicao_small():
    m = mundo()
    cal = m["cal"]
    cdi = indices_de([(d.isoformat(), "CDI", 10.0) for d in cal])   # tabela sem SMLL
    com, info_com = _montar_mundo(m, m["indices"])
    assert com["exposicao_small"].notna().any()
    assert info_com["smll_pregoes"] == 300 and info_com["smll_ate"] == cal[-1].isoformat()
    for indices in (None, cdi):
        sem, info_sem = _montar_mundo(m, indices)
        assert sem["exposicao_small"].isna().all()
        assert info_sem["smll_pregoes"] == 0 and info_sem["smll_ate"] is None
        pd.testing.assert_frame_equal(
            sem.drop(columns="exposicao_small"), com.drop(columns="exposicao_small"), rtol=1e-12, atol=1e-12
        )
