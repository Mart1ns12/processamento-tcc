"""Vazamento temporal do dataset do experimento (plano da etapa 5, fase 8).

Nada depois de t pode mudar as linhas de t, exceto o alvo (que olha t+1). Cenários: "cortado"
(só o que se saberia no fim de t) e "cheio e alterado" (futuro de t mudado: preços ×3, volumes
×10, notícias após 08:00 de t1 com pp e pn trocados, notícias novas, cvm_ipe e balanço em t1).
Nenhum teste usa banco ou rede.
"""

import functools
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from fabrica_experimento import (
    CADASTRO_MUNDO,
    SP,
    alterado,
    cortado,
    dados_de,
    depois_de_t1_alterado,
    em_t,
    mundo,
    noticias_de,
    sem_pregao,
    so_t1_alterado,
)
from processamento.experimento.dataset import executar, montar_dataset
from processamento.experimento.parametros import carregar_parametros_experimento
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


# Dias de corte testados: o da suíte original (T_INDICE), uma sexta (t+1 na segunda), o primeiro
# pregão depois do período sem coleta (params) e uma quinta cuja sexta seguinte virou feriado.
CASOS_T = ["T_INDICE", "sexta", "logo_depois_sem_coleta", "vespera_de_feriado"]
FIM_SEM_COLETA = max(fim for _, fim in carregar_parametros_experimento().periodos_sem_coleta)


def _primeiro_indice(cal, condicao, minimo=100):
    """Primeiro índice ≥ `minimo` de `cal` (com dois pregões depois) cuja data cumpre `condicao`."""
    return next(i for i in range(minimo, len(cal) - 2) if condicao(cal[i]))


@functools.lru_cache(maxsize=None)
def _mundo_do_caso(caso):
    base = mundo()
    cal = base["cal"]
    if caso == "T_INDICE":
        return base
    if caso == "sexta":
        return em_t(base, _primeiro_indice(cal, lambda d: d.weekday() == 4))
    if caso == "logo_depois_sem_coleta":
        return em_t(base, _primeiro_indice(cal, lambda d: d > FIM_SEM_COLETA, minimo=0))
    if caso == "vespera_de_feriado":
        i = _primeiro_indice(cal, lambda d: d.weekday() == 3)
        m = sem_pregao(base, cal[i + 1])  # a sexta seguinte sai do mundo: t+1 passa a ser a segunda
        return em_t(m, m["cal"].index(cal[i]))
    raise ValueError(caso)


def _montar(m):
    """(dataset, info) de `m` com o mesmo desenho do cenário cheio."""
    return montar_dataset(dados_de(m["cal"], m["precos"], CADASTRO_MUNDO, m["noticias"], m["balancos"]), m["cal"])


def _dataset(m):
    return _montar(m)[0]


@functools.lru_cache(maxsize=None)
def _pares_do_caso(caso):
    """Dataset cru de cortado(m) e de alterado(m) no caso: o mesmo desenho do cenário, em outro t."""
    m = _mundo_do_caso(caso)
    c = cortado(m)
    a = alterado(m)
    df_cortado, _ = montar_dataset(
        dados_de(c["cal"], c["precos"], CADASTRO_MUNDO, c["noticias"], c["balancos"]),
        c["cal"],
        proximo_ao_vivo=m["t1"],
    )
    df_alterado, _ = montar_dataset(
        dados_de(a["cal"], a["precos"], CADASTRO_MUNDO, a["noticias"], a["balancos"]), a["cal"]
    )
    return df_cortado, df_alterado


def _alvo_do_dia(df, d):
    return df[df["data"] == pd.Timestamp(d)][COLUNAS_ALVO].reset_index(drop=True)


def _difere(a, b):
    """True se algum valor muda; NaN contra número conta como mudança."""
    x, y = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
    return bool(
        (np.isnan(x) != np.isnan(y)).any()
        or not np.allclose(np.nan_to_num(x), np.nan_to_num(y), rtol=1e-12, atol=1e-12)
    )


def test_casos_de_t_cobrem_o_que_dizem():
    m = _mundo_do_caso("sexta")
    assert m["t"].weekday() == 4 and m["t1"].weekday() == 0  # sexta; t+1 na segunda
    m = _mundo_do_caso("logo_depois_sem_coleta")
    anterior = m["cal"][m["cal"].index(m["t"]) - 1]
    assert m["t"] > FIM_SEM_COLETA >= anterior  # t é o primeiro pregão depois do período sem coleta
    m = _mundo_do_caso("vespera_de_feriado")
    assert m["t"].weekday() == 3
    assert m["t"] + timedelta(days=1) not in m["cal"]  # a sexta saiu do calendário
    assert (m["t1"] - m["t"]).days == 4  # t+1 é a segunda: dois dias úteis adiante


@pytest.mark.parametrize("caso", CASOS_T)
def test_linhas_de_t_iguais_sem_alvo_em_varios_t(caso):
    t = _mundo_do_caso(caso)["t"]
    df_cortado, df_alterado = _pares_do_caso(caso)
    linhas = _linhas(df_cortado, t)
    assert not linhas.empty
    pd.testing.assert_frame_equal(linhas, _linhas(df_alterado, t), rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("caso", CASOS_T)
def test_linhas_de_t_iguais_depois_de_preparar_em_varios_t(caso):
    t = _mundo_do_caso(caso)["t"]
    df_cortado, df_alterado = _pares_do_caso(caso)
    prep_cortado = preparar(df_cortado.copy())
    prep_alterado = preparar(df_alterado.copy())
    linhas = _linhas(prep_cortado, t)
    assert not linhas.empty
    pd.testing.assert_frame_equal(linhas, _linhas(prep_alterado, t), rtol=1e-12, atol=1e-12)


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


def test_noticias_de_t_existem_e_alvo_olha_o_futuro(cenario):
    t = cenario["t"]
    assert _valor(cenario["df_cortado"], t, "AAAA3", "noticias_dia_qtd") > 0
    assert _valor(cenario["df_alterado"], t, "AAAA3", "noticias_dia_qtd") > 0
    assert pd.isna(_valor(cenario["df_cortado"], t, "AAAA3", "alvo"))
    assert _valor(cenario["df_cheio"], t, "AAAA3", "alvo") in (0.0, 1.0)
    # o futuro alterado (preço ×3 em t1) é retorno suspeito: o alvo olha t+1 e fica vazio (seção 6)
    assert pd.isna(_valor(cenario["df_alterado"], t, "AAAA3", "alvo"))


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


@functools.lru_cache(maxsize=None)
def _df_cheio(caso):
    return _dataset(_mundo_do_caso(caso))


def test_so_t1_alterado_mexe_so_nas_colunas_de_alvo_de_t():
    m = _mundo_do_caso("T_INDICE")
    t = m["t"]
    antes = _df_cheio("T_INDICE")
    depois = _dataset(so_t1_alterado(m))
    pd.testing.assert_frame_equal(_linhas(antes, t), _linhas(depois, t), rtol=1e-12, atol=1e-12)
    # o alvo de t olha t+1: ao menos uma coluna de alvo muda de fato
    assert _difere(_alvo_do_dia(antes, t), _alvo_do_dia(depois, t))


def test_depois_de_t1_alterado_nao_muda_nenhuma_linha_de_t():
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    antes = _df_cheio("T_INDICE")
    depois = _dataset(depois_de_t1_alterado(m))
    pd.testing.assert_frame_equal(_linhas(antes, t), _linhas(depois, t), rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(_alvo_do_dia(antes, t), _alvo_do_dia(depois, t), rtol=1e-12, atol=1e-12)
    # prova de que o futuro mudou: o alvo de t+1 (que olha t+2) muda
    assert _difere(_alvo_do_dia(antes, t1), _alvo_do_dia(depois, t1))


def test_dataset_nao_le_proventos_acoes_emitidas_nem_indices(banco_teste, tmp_path):
    # O dataset não lê v1-proventos, v1-acoes_emitidas nem v1-indices. Por isso, alterar essas
    # tabelas não muda nada. O espião confere que nenhuma consulta as cita, e que a leitura de
    # v1-precos passa por ele (senão o teste seria vazio).
    ler_banco = banco_teste()
    consultas = []

    def espiao(sql, *args, **kwargs):
        consultas.append(sql)
        return ler_banco(sql, *args, **kwargs)

    csv = executar("todas", None, None, tmp_path, ler=espiao, existe_composicao=False)
    assert csv.exists()
    assert any("v1-precos" in sql for sql in consultas)
    for tabela in ("v1-proventos", "v1-acoes_emitidas", "v1-indices"):
        assert not any(tabela in sql for sql in consultas), tabela


TITULO_COPIA = "Empresa AAAA3 anuncia novo plano de investimento"  # 7 palavras (mínimo: 5)
URL_COPIA = "https://exemplo.com/noticias/aaaa3-plano"


def _instante_sp(dia, hora):
    return pd.Timestamp(f"{dia} {hora}").tz_localize(SP)


def _com_noticias(m, extra):
    return {**m, "noticias": pd.concat([m["noticias"], extra], ignore_index=True)}


def _google_so_data(t, url=None):
    """Google News "só data" de t: 04:00 SP é meia-noite do Pacífico (regra N1-A), sem hora real."""
    return noticias_de(
        [("g-copia", "AAAA3", _instante_sp(t, "04:00:00"), t, 0.8, 0.1, "google_news", "protagonista", "reportagem")],
        campos={"g-copia": {"titulo": TITULO_COPIA, "resolved_url": url}},
    )


def _wordpress_no_dia_seguinte(t1):
    """Cópia wordpress do mesmo título, com hora real, no dia seguinte a t."""
    return noticias_de(
        [("w-copia", "AAAA3", _instante_sp(t1, "10:00:00"), t1, 0.3, 0.3, "wordpress", "protagonista", "reportagem")],
        campos={"w-copia": {"titulo": TITULO_COPIA}},
    )


def _wordpress_com_mesma_url(dia):
    """Cópia wordpress de outro título, três dias depois de t, só com `link` igual à URL da google."""
    return noticias_de(
        [("w-url", "AAAA3", _instante_sp(dia, "12:00:00"), dia, 0.3, 0.3, "wordpress", "protagonista", "reportagem")],
        campos={"w-url": {"titulo": "Manchete diferente sobre outro assunto da empresa", "link": URL_COPIA}},
    )


def test_copia_futura_com_mesmo_titulo_nao_muda_linhas_de_t():
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    base = _com_noticias(m, _google_so_data(t))
    g = base["noticias"][base["noticias"]["id"] == "g-copia"].iloc[0]
    assert g["precisao_hora"] == "meia_noite_pacifico" and pd.isna(g["data_hora_publicacao"])
    assert g["momento_ref"] == _instante_sp(t, "23:59:59")
    futuro = _com_noticias(base, _wordpress_no_dia_seguinte(t1))
    df_base, info_base = _montar(base)
    df_futuro, info_futuro = _montar(futuro)
    assert not _linhas(df_base, t).empty
    pd.testing.assert_frame_equal(_linhas(df_base, t), _linhas(df_futuro, t), rtol=1e-12, atol=1e-12)
    # a cópia de t+1 sai pela regra de título (Δ = 1 dia); a de t fica
    assert info_base["duplicadas_titulo_janela"] == 0
    assert info_futuro["duplicadas_titulo_janela"] == 1


def test_copia_futura_com_mesma_url_nao_muda_linhas_de_t():
    m = _mundo_do_caso("T_INDICE")
    t = m["t"]
    dia = m["cal"][m["cal"].index(t) + 3]
    base = _com_noticias(m, _google_so_data(t, url=URL_COPIA))
    futuro = _com_noticias(base, _wordpress_com_mesma_url(dia))
    df_base, info_base = _montar(base)
    df_futuro, info_futuro = _montar(futuro)
    assert not _linhas(df_base, t).empty
    pd.testing.assert_frame_equal(_linhas(df_base, t), _linhas(df_futuro, t), rtol=1e-12, atol=1e-12)
    # a cópia de t+3 sai pela URL (resolved_url da google, link da wordpress), sem janela de data
    assert info_base["duplicadas_url"] == 0
    assert info_futuro["duplicadas_url"] == 1
