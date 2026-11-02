"""Vazamento temporal do dataset do experimento (plano da etapa 5, fase 8).

Nada depois de t pode mudar as linhas de t, exceto o alvo (que olha t+1). Cenários: "cortado"
(só o que se saberia no fim de t) e "cheio e alterado" (futuro de t mudado: preços ×3, volumes
×10, SMLL ×3, notícias após 08:00 de t1 com pp e pn trocados, notícias novas, cvm_ipe, balanço, proventos e
documentos da CVM em t1 ou depois).
Os blocos A e B do protocolo (inclusive exposicao_small, que lê o SMLL e o IBOV) também não podem
olhar o futuro. Nenhum teste usa banco ou rede.
"""

import dataclasses
import functools
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from fabrica_experimento import (
    AP,
    CADASTRO_MUNDO,
    FATO,
    SP,
    alterado,
    cortado,
    dados_do_mundo,
    depois_de_t1_alterado,
    em_t,
    linha_entregue_em,
    mexer_no_futuro,
    mundo,
    noticias_de,
    sem_pregao,
    so_t1_alterado,
)
from fabrica_fundamentos import _a, balanco_de, documentos_de, proventos_de
from fabrica_precos import cadastro_de, precos_de, serie_por_retornos
from processamento import calendario, fontes
from processamento.exclusoes import Exclusoes
from processamento.experimento.dataset import executar, montar_dataset
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.experimento.preparacao import (
    COLUNAS_ALVO,
    COLUNAS_PROTOCOLO,
    COMPLEMENTARES_PRECO,
    ESSENCIAIS_PRECO,
    preparar,
    rank_no_pregao,
)
from processamento.universo import montar_universo

PRECO = ESSENCIAIS_PRECO + COMPLEMENTARES_PRECO  # as 13 colunas de preço e volume (sem os blocos A e B)


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
        dados_do_mundo(c),
        c["cal"],
        proximo_ao_vivo=t1,
    )
    df_cheio, _ = montar_dataset(
        dados_do_mundo(m), m["cal"]
    )
    df_alterado, _ = montar_dataset(
        dados_do_mundo(a), a["cal"]
    )
    sem_f4 = m["noticias"][m["noticias"]["id"] != "f4"]
    df_sem_f4, _ = montar_dataset(
        dados_do_mundo({**m, "noticias": sem_f4}), m["cal"]
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
    return montar_dataset(dados_do_mundo(m), m["cal"])


def _dataset(m):
    return _montar(m)[0]


@functools.lru_cache(maxsize=None)
def _pares_do_caso(caso):
    """Dataset cru de cortado(m) e de alterado(m) no caso: o mesmo desenho do cenário, em outro t."""
    m = _mundo_do_caso(caso)
    c = cortado(m)
    a = alterado(m)
    df_cortado, _ = montar_dataset(
        dados_do_mundo(c),
        c["cal"],
        proximo_ao_vivo=m["t1"],
    )
    df_alterado, _ = montar_dataset(
        dados_do_mundo(a), a["cal"]
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
        dados_do_mundo(m), m["cal"]
    )
    df_regravado, _ = montar_dataset(
        dados_do_mundo({**m, "precos": precos}), m["cal"]
    )
    pd.testing.assert_frame_equal(
        _linhas(df_original, t)[["data", "ticker", *PRECO, *COLUNAS_PROTOCOLO]],
        _linhas(df_regravado, t)[["data", "ticker", *PRECO, *COLUNAS_PROTOCOLO]],
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


def _espiar(ler_banco):
    consultas = []

    def espiao(sql, params=None):
        consultas.append((sql, params))
        return ler_banco(sql, params)

    return espiao, consultas


def test_dataset_le_proventos_documentos_e_indices_com_corte_e_nao_le_acoes(banco_teste, tmp_path):
    ler_banco = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler_banco))
    espiao, consultas = _espiar(ler_banco)
    csv = executar("todas", cal[1], None, tmp_path, ler=espiao, existe_composicao=False)
    assert csv.exists()
    assert any("v1-precos" in sql for sql, _ in consultas)
    for tabela in ("v1-balancos", "v1-indices", "v1-proventos", "v1-raw_ipe_docs"):
        assert any(tabela in sql and params and params.get("ate") == cal[1].isoformat() for sql, params in consultas), tabela
    assert not any("v1-acoes_emitidas" in sql for sql, _ in consultas)


def test_com_proximo_balancos_e_documentos_vao_ate_a_vespera_e_proventos_ate_t(banco_teste, tmp_path):
    ler_banco = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler_banco))
    espiao, consultas = _espiar(ler_banco)
    executar("todas", cal[2], cal[3], tmp_path, ler=espiao, existe_composicao=False)
    vespera = (cal[3] - timedelta(days=1)).isoformat()
    for tabela, corte in (("v1-balancos", vespera), ("v1-raw_ipe_docs", vespera), ("v1-proventos", cal[2].isoformat())):
        assert any(tabela in sql and params and params.get("ate") == corte for sql, params in consultas), tabela
    assert not any("v1-acoes_emitidas" in sql for sql, _ in consultas)


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


# ---------------------------------------------------------------- cópia posterior ao corte não muda o pregão de t


def _copias_em_torno_do_corte(t1, origem_cedo, origem_tarde):
    """Cópia às 07:00 de t+1 (ainda na janela de t), sem probabilidade, e cópia às 10:00 de t+1 (já na de t+1), com."""
    cedo = noticias_de(
        [("c-cedo", "AAAA3", _instante_sp(t1, "07:00:00"), t1, np.nan, np.nan, origem_cedo, "protagonista", "reportagem")],
        campos={"c-cedo": {"titulo": TITULO_COPIA}},
    )
    tarde = noticias_de(
        [("c-tarde", "AAAA3", _instante_sp(t1, "10:00:00"), t1, 0.9, 0.05, origem_tarde, "protagonista", "reportagem")],
        campos={"c-tarde": {"titulo": TITULO_COPIA}},
    )
    return cedo, tarde


@pytest.mark.parametrize(
    "origem_cedo, origem_tarde",
    [("wordpress", "google_news"), ("google_news", "google_news")],
    ids=["entre_origens", "mesma_origem"],
)
def test_copia_depois_do_corte_com_probabilidade_nao_tira_a_de_antes_do_corte(origem_cedo, origem_tarde):
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    cedo, tarde = _copias_em_torno_do_corte(t1, origem_cedo, origem_tarde)
    so_cedo = _com_noticias(m, cedo)
    com_tarde = _com_noticias(so_cedo, tarde)
    df_cedo, _ = _montar(so_cedo)
    df_tarde, _ = _montar(com_tarde)
    df_sem, _ = _montar(m)
    pd.testing.assert_frame_equal(_linhas(df_cedo, t), _linhas(df_tarde, t), rtol=1e-12, atol=1e-12)
    # a cópia de 07:00 conta em t, e a posterior não muda isso
    assert _valor(df_tarde, t, "AAAA3", "noticias_dia_qtd") == _valor(df_sem, t, "AAAA3", "noticias_dia_qtd") + 1
    # e a de 10:00, mais tarde, sai: t+1 fica igual a sem ela
    assert _valor(df_tarde, t1, "AAAA3", "noticias_dia_qtd") == _valor(df_cedo, t1, "AAAA3", "noticias_dia_qtd")


# ---------------------------------------------------------------- blocos A e B do protocolo não olham o futuro


def test_colunas_novas_tem_valor_em_t():
    m = _mundo_do_caso("T_INDICE")
    t = m["t"]
    df = _df_cheio("T_INDICE")
    linhas = _linhas(df, t)
    for coluna in COLUNAS_PROTOCOLO:
        assert linhas[coluna].notna().any(), coluna
    # DDDD3 é o único do setor S2: a média do setor não tem outro para comparar
    assert pd.isna(_valor(df, t, "DDDD3", "momento_setor_5d"))


_TROCAS_FUTURO = [
    pytest.param({"so_t1": True, "acoes_preco": 1.05}, id="precos_so_t1"),
    pytest.param({"acoes_preco": 3.0}, id="precos_depois"),
    pytest.param({"so_t1": True, "acoes_volume": 10.0}, id="volumes_so_t1"),
    pytest.param({"acoes_volume": 10.0}, id="volumes_depois"),
    pytest.param({"so_t1": True, "smll": 1.05}, id="smll_so_t1"),
    pytest.param({"smll": 3.0}, id="smll_depois"),
    pytest.param({"so_t1": True, "ibov": 1.05}, id="ibov_so_t1"),
    pytest.param({"ibov": 3.0}, id="ibov_depois"),
]


@pytest.mark.parametrize("trocas", _TROCAS_FUTURO)
def test_futuro_nao_muda_colunas_novas_em_t(trocas):
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    antes = _df_cheio("T_INDICE")
    depois = _dataset(mexer_no_futuro(m, **trocas))
    pd.testing.assert_frame_equal(_linhas(antes, t), _linhas(depois, t), rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(
        _linhas(preparar(antes.copy()), t), _linhas(preparar(depois.copy()), t), rtol=1e-12, atol=1e-12
    )
    # prova de efeito: o futuro mudou as colunas novas de t+1
    assert _difere(_linhas(antes, t1)[COLUNAS_PROTOCOLO], _linhas(depois, t1)[COLUNAS_PROTOCOLO])


def test_empresa_nova_depois_de_t_nao_muda_t():
    m = _mundo_do_caso("T_INDICE")
    cal = m["cal"]
    t = m["t"]
    i = cal.index(t)
    rng = np.random.default_rng(9)
    depois = cal[i + 1:]
    extra = precos_de("EEEE3", depois, serie_por_retornos(60.0, rng.normal(0, 0.01, len(depois) - 1).tolist()))
    precos = pd.concat([m["precos"], extra], ignore_index=True)
    cadastro = pd.concat([CADASTRO_MUNDO, cadastro_de([("EEEE3", "9", "S1", "ON")])], ignore_index=True)
    nova, _ = montar_dataset(dados_do_mundo({**m, "precos": precos}, cadastro), cal)
    antes = _df_cheio("T_INDICE")
    pd.testing.assert_frame_equal(_linhas(antes, t), _linhas(nova, t), rtol=1e-12, atol=1e-12)
    assert "EEEE3" not in set(_linhas(nova, t)["ticker"])
    # prova de efeito: a empresa nova entra na média do setor de AAAA3 depois de t
    dia = cal[i + 6]
    assert not np.isclose(
        _valor(antes, dia, "AAAA3", "momento_setor_5d"), _valor(nova, dia, "AAAA3", "momento_setor_5d")
    )


def test_entrada_na_composicao_depois_de_t_nao_muda_t():
    m = _mundo_do_caso("T_INDICE")
    t, t1, cal = m["t"], m["t1"], m["cal"]
    i = cal.index(t)

    def com_composicao(inicio_ccc):
        composicao = pd.DataFrame({
            "ticker": ["AAAA3", "AAAA4", "BBBB3", "DDDD3", "CCCC3"],
            "data_inicio": [pd.Timestamp(cal[0])] * 4 + [pd.Timestamp(inicio_ccc)],
            "data_fim": [pd.NaT] * 5,
        })
        dados = dados_do_mundo(m)
        universo = montar_universo(cal, CADASTRO_MUNDO, m["precos"], Exclusoes(), composicao)
        return montar_dataset(dataclasses.replace(dados, universo=universo), cal)[0]

    entra_em_t1 = com_composicao(t1)
    entra_depois = com_composicao(cal[i + 5])
    pd.testing.assert_frame_equal(_linhas(entra_em_t1, t), _linhas(entra_depois, t), rtol=1e-12, atol=1e-12)
    # prova de efeito: CCCC3 pesa na média do setor de AAAA3 em t+1
    assert not np.isclose(
        _valor(entra_em_t1, t1, "AAAA3", "momento_setor_5d"), _valor(entra_depois, t1, "AAAA3", "momento_setor_5d")
    )


def test_balanco_so_muda_as_colunas_de_balanco():
    m = _mundo_do_caso("T_INDICE")
    cal = m["cal"]
    balancos = m["balancos"].copy()
    balancos.loc[balancos["cnpj"] == "1", "data_entrega"] = pd.Timestamp(cal[6])
    antes = _df_cheio("T_INDICE")
    depois = _dataset({**m, "balancos": balancos})
    de_balanco = ["dia_resultado", "dias_desde_resultado", "var_lucro_aa"]
    assert not antes["dia_resultado"].equals(depois["dia_resultado"])
    pd.testing.assert_frame_equal(
        antes.drop(columns=de_balanco), depois.drop(columns=de_balanco), rtol=1e-12, atol=1e-12
    )


# ---------------------------------------------------------------- blocos C, D, E e controle não olham o futuro


def _com_linhas(m, chave, extra):
    return {**m, chave: pd.concat([m[chave], extra], ignore_index=True)}


def _igual_em_t(antes, depois, t):
    """Linhas de t iguais antes e depois dos ranks."""
    pd.testing.assert_frame_equal(_linhas(antes, t), _linhas(depois, t), rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(
        _linhas(preparar(antes.copy()), t), _linhas(preparar(depois.copy()), t), rtol=1e-12, atol=1e-12
    )


def test_gabarito_das_colunas_novas_em_t():
    m = _mundo_do_caso("T_INDICE")
    t = m["t"]
    assert t == date(2026, 6, 1)
    df = _df_cheio("T_INDICE")
    # entrega em 10/05/2026 (domingo) -> pregão 08/05; até 01/06 são 16 pregões
    for ticker in ("AAAA3", "AAAA4", "BBBB3", "CCCC3"):
        assert _valor(df, t, ticker, "dias_desde_resultado") == 16
    assert pd.isna(_valor(df, t, "DDDD3", "dias_desde_resultado"))
    # 1º tri de 2026 − 1º tri de 2025, sobre PL 1000; mesmo valor nas duas classes
    assert _valor(df, t, "AAAA3", "var_lucro_aa") == pytest.approx(0.01, abs=1e-12)
    assert _valor(df, t, "AAAA4", "var_lucro_aa") == pytest.approx(0.01, abs=1e-12)
    assert _valor(df, t, "CCCC3", "var_lucro_aa") == pytest.approx(0.03, abs=1e-12)
    assert pd.isna(_valor(df, t, "BBBB3", "var_lucro_aa"))   # sem o ano anterior
    assert _valor(df, t, "DDDD3", "dy_12m") == 0.0           # nunca pagou, com preço
    assert _valor(df, t, "AAAA3", "dy_12m") != _valor(df, t, "AAAA4", "dy_12m")   # por classe
    assert _valor(df, t, "AAAA3", "fato_relevante_cvm") == 0
    assert _valor(df, m["cal"][262], "AAAA3", "fato_relevante_cvm") == 1          # índice 3 + 7 × 37


def test_balanco_entregue_em_t1_nao_muda_t():
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    antes, depois = _df_cheio("T_INDICE"), _dataset(_com_linhas(m, "balancos", linha_entregue_em("1", t1, 999.0)))
    _igual_em_t(antes, depois, t)
    # prova de efeito: 2º tri de 2026 (999) − 2º tri de 2025 (21), sobre PL 500
    assert _valor(depois, t1, "AAAA3", "var_lucro_aa") == pytest.approx(1.956, abs=1e-12)
    assert _valor(depois, t1, "AAAA3", "dias_desde_resultado") == 0
    assert _valor(antes, t1, "AAAA3", "dias_desde_resultado") == 17


def _antigo(dia, lucro):
    """1º tri de 2025 do CNPJ 2, que falta no mundo: é o ano anterior do trimestre de referência em t."""
    return balanco_de("2", [_a("ITR", "2025-01-01", "2025-03-31", dia.isoformat(), 1, 1, lucro, 1000.0)])


def test_trimestre_antigo_entregue_depois_de_t_nao_muda_t():
    m = _mundo_do_caso("T_INDICE")
    t, cal = m["t"], m["cal"]
    dia = cal[cal.index(t) + 5]
    antes, depois = _df_cheio("T_INDICE"), _dataset(_com_linhas(m, "balancos", _antigo(dia, 40.0)))
    _igual_em_t(antes, depois, t)
    assert pd.isna(_valor(depois, t, "BBBB3", "var_lucro_aa"))
    # prova de efeito: (60 − 40) ÷ 1000 a partir da entrega; atraso acima de 180 dias não zera a contagem
    assert _valor(depois, dia, "BBBB3", "var_lucro_aa") == pytest.approx(0.02, abs=1e-12)
    assert pd.isna(_valor(antes, dia, "BBBB3", "var_lucro_aa"))
    assert _valor(depois, dia, "BBBB3", "dias_desde_resultado") == 21
    assert _valor(antes, dia, "BBBB3", "dias_desde_resultado") == 21
    assert bool(_valor(depois, dia, "BBBB3", "dia_resultado"))


def test_reapresentacao_futura_troca_valor_e_data_sem_mudar_t():
    # A coleta guarda só a última versão: a reapresentação muda valor e data da mesma linha. Antes das duas datas, nada muda.
    m = _mundo_do_caso("T_INDICE")
    t, cal = m["t"], m["cal"]
    i = cal.index(t)
    versao_1 = _dataset(_com_linhas(m, "balancos", _antigo(cal[i + 5], 40.0)))
    versao_2 = _dataset(_com_linhas(m, "balancos", _antigo(cal[i + 10], 400.0)))
    _igual_em_t(versao_1, versao_2, t)
    # prova de efeito, depois de t
    assert _valor(versao_1, cal[i + 5], "BBBB3", "var_lucro_aa") == pytest.approx(0.02, abs=1e-12)
    assert pd.isna(_valor(versao_2, cal[i + 5], "BBBB3", "var_lucro_aa"))
    assert _valor(versao_2, cal[i + 10], "BBBB3", "var_lucro_aa") == pytest.approx(-0.34, abs=1e-12)
    assert _valor(versao_2, cal[i + 10], "BBBB3", "dias_desde_resultado") == 26


def _proventos_futuros(m):
    cal, t1 = m["cal"], m["t1"]
    return proventos_de([
        ("AAAA3", "DIVIDENDO", t1.isoformat(), 50.0, None),
        ("BBBB3", "DIVIDENDO", cal[cal.index(t1) + 20].isoformat(), 50.0, None),
    ])


def test_provento_futuro_nao_muda_t():
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    antes, depois = _df_cheio("T_INDICE"), _dataset(_com_linhas(m, "proventos", _proventos_futuros(m)))
    _igual_em_t(antes, depois, t)
    assert _valor(depois, t1, "AAAA3", "dy_12m") > _valor(antes, t1, "AAAA3", "dy_12m")   # prova de efeito


def test_provento_futuro_entregue_a_conta_no_ultimo_pregao_nao_entra():
    # sem corte na leitura (dataset sem --ate): a data_com futura chega à conta e tem de sair lá dentro
    m = _mundo_do_caso("T_INDICE")
    t, t1 = m["t"], m["t1"]
    c = cortado(m)
    com_futuro = {**c, "proventos": pd.concat([m["proventos"], _proventos_futuros(m)], ignore_index=True)}
    assert (com_futuro["proventos"]["data_com"] > pd.Timestamp(t)).any()
    limpo = montar_dataset(dados_do_mundo(c), c["cal"], proximo_ao_vivo=t1)[0]
    sujo = montar_dataset(dados_do_mundo(com_futuro), c["cal"], proximo_ao_vivo=t1)[0]
    _igual_em_t(limpo, sujo, t)


def _documento(cnpj, dia):
    return documentos_de([(f"novo-{dia}", cnpj, FATO, dia, AP, 1)])


def test_documento_do_proximo_pregao_nao_muda_a_sexta():
    m = _mundo_do_caso("sexta")
    t, t1 = m["t"], m["t1"]
    antes, depois = _dataset(m), _dataset(_com_linhas(m, "documentos", _documento("3", t1)))
    _igual_em_t(antes, depois, t)
    assert _valor(depois, t, "CCCC3", "fato_relevante_cvm") == 0
    assert _valor(depois, t1, "CCCC3", "fato_relevante_cvm") == 1   # prova de efeito


@pytest.mark.parametrize("dias", [1, 2], ids=["sabado", "domingo"])
def test_documento_do_fim_de_semana_marca_a_sexta_e_nao_a_segunda(dias):
    m = _mundo_do_caso("sexta")
    t, t1 = m["t"], m["t1"]
    dia = t + timedelta(days=dias)
    antes, depois = _dataset(m), _dataset(_com_linhas(m, "documentos", _documento("3", dia)))
    assert _valor(depois, t, "CCCC3", "fato_relevante_cvm") == 1
    assert _valor(depois, t1, "CCCC3", "fato_relevante_cvm") == 0
    # o resto de t não muda: é a marca correta, não vazamento
    pd.testing.assert_frame_equal(
        _linhas(antes, t).drop(columns="fato_relevante_cvm"), _linhas(depois, t).drop(columns="fato_relevante_cvm"),
        rtol=1e-12, atol=1e-12,
    )


def test_documento_de_d_presente_nos_dados_nao_entra_na_noite_de_t():
    m = _mundo_do_caso("sexta")
    t, t1 = m["t"], m["t1"]
    c = cortado(m)
    com_d = _com_linhas(c, "documentos", _documento("3", t1))
    limpo = montar_dataset(dados_do_mundo(c), c["cal"], proximo_ao_vivo=t1)[0]
    sujo = montar_dataset(dados_do_mundo(com_d), c["cal"], proximo_ao_vivo=t1)[0]
    _igual_em_t(limpo, sujo, t)


def _so_controle(df, d):
    return _linhas(df, d)[["ticker", "controle_sorteado"]]


def test_controle_nao_muda_ao_mexer_em_pregoes_futuros_ou_tickers_de_outros_dias():
    m = _mundo_do_caso("T_INDICE")
    t, t1, cal = m["t"], m["t1"], m["cal"]
    anterior = pd.Timestamp(cal[cal.index(t) - 1])
    antes = _df_cheio("T_INDICE")

    # tira os pregões depois de t + 1
    curto = pd.Timestamp(t1)
    m_curto = {**m, "cal": [d for d in cal if d <= t1], "precos": m["precos"][m["precos"]["data"] <= curto].reset_index(drop=True)}
    pd.testing.assert_frame_equal(_so_controle(antes, t), _so_controle(_dataset(m_curto), t))

    # tira BBBB3 em t − 1 e em t + 1
    fora = (m["precos"]["ticker"] == "BBBB3") & m["precos"]["data"].isin([anterior, pd.Timestamp(t1)])
    depois = _dataset({**m, "precos": m["precos"][~fora].reset_index(drop=True)})
    pd.testing.assert_frame_equal(_so_controle(antes, t), _so_controle(depois, t))
    # ranks do controle em t também iguais
    pd.testing.assert_frame_equal(
        _so_controle(rank_no_pregao(antes, ["controle_sorteado"]), t),
        _so_controle(rank_no_pregao(depois, ["controle_sorteado"]), t),
    )
    # prova de efeito: nos dias mexidos, CCCC3 passa a receber outro sorteio
    assert _valor(depois, t1, "CCCC3", "controle_sorteado") != _valor(antes, t1, "CCCC3", "controle_sorteado")
    assert _valor(depois, anterior, "CCCC3", "controle_sorteado") != _valor(antes, anterior, "CCCC3", "controle_sorteado")
