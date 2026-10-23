"""Testes de tom.py (etapa 5, fase 4): variáveis de notícias por empresa, setor e mercado.

Tabelas montadas à mão, tickers fictícios. Nenhum teste usa banco ou rede.
Todas as notícias têm janela "dia" (a única que sai de `classificar_para_modelo`).
"""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.experimento.tom import COLUNAS_NOTICIAS, extremo, variaveis_de_noticias

NAN = np.nan
PARAMS = carregar_parametros_experimento()
CAL3 = ["2026-06-17", "2026-06-18", "2026-06-19"]


def _nots(*itens):
    """Notícias preparadas: (id, empresa, janela, pregao_ref, score)."""
    return pd.DataFrame(
        [
            {
                "id": i,
                "ticker": "AAAA3",
                "empresa": e,
                "origem": "google_news",
                "momento": pd.NaT,
                "sem_horario": False,
                "janela": j,
                "pregao_ref": pd.Timestamp(d),
                "score": s,
            }
            for i, e, j, d, s in itens
        ],
        columns=["id", "ticker", "empresa", "origem", "momento", "sem_horario", "janela", "pregao_ref", "score"],
    )


def _linhas(*itens):
    """Linhas do dataset: (data, ticker, empresa, setor)."""
    return pd.DataFrame(
        [{"data": pd.Timestamp(d), "ticker": t, "empresa": e, "setor": s} for d, t, e, s in itens]
    )


def _tabela_a():
    """Notícias do teste A (pregões 06-18 e 06-19) e linhas de 06-18 (a empresa "6" não tem notícia)."""
    nots = _nots(
        ("n1", "1", "dia", "2026-06-18", 0.6),
        ("n2", "1", "dia", "2026-06-18", -0.4),
        ("n3", "1", "dia", "2026-06-18", 0.0),
        ("n13", "1", "dia", "2026-06-18", NAN),
        ("n4", "2", "dia", "2026-06-18", 0.7),
        ("n5", "2", "dia", "2026-06-19", 0.9),
        ("n6", "3", "dia", "2026-06-18", -0.4),
        ("n7", "4", "dia", "2026-06-18", -0.1),
        ("n8", "1", "dia", "2026-06-18", 0.3),
        ("n9", "1", "dia", "2026-06-18", -0.2),
        ("n12", "5", "dia", "2026-06-18", -0.9),
    )
    linhas = _linhas(
        ("2026-06-18", "XXXX3", "1", "S1"),
        ("2026-06-18", "XXXX4", "1", "S1"),
        ("2026-06-18", "YYYY3", "2", "S1"),
        ("2026-06-18", "ZZZZ3", "3", "S1"),
        ("2026-06-18", "WWWW3", "4", "S2"),
        ("2026-06-18", "KKKK3", "6", "S1"),
    )
    return nots, linhas


def _iguais(real, esperado):
    """Compara valor a valor: NaN esperado exige NaN; número esperado usa aproximação de 1e-12."""
    if np.isnan(esperado):
        return np.isnan(real)
    return real == pytest.approx(esperado, abs=1e-12)


def test_teste_a_valores_do_dia_com_setor_e_mercado():
    nots, linhas = _tabela_a()
    out = variaveis_de_noticias(
        nots, linhas, CAL3, PARAMS, noite_aberta=None, cobertura_inicio=pd.Timestamp("2026-06-17")
    ).set_index("ticker")
    # Empresa "1": 6 notícias (0,6; -0,4; 0,0; NaN; 0,3; -0,2) -> tom 0,3/5 = 0,06.
    # tom_setor: média de (0,7; -0,4) das outras da S1. tom_mercado: 8 scores de 06-18 (n13 sem score; n12 fora).
    esperado = {
        "XXXX3": dict(qtd=6, tom=0.06, ext=0.6, setor=0.15, mercado=0.5 / 8),
        "XXXX4": dict(qtd=6, tom=0.06, ext=0.6, setor=0.15, mercado=0.5 / 8),
        "YYYY3": dict(qtd=1, tom=0.7, ext=0.7, setor=-0.17, mercado=0.5 / 8),
        "ZZZZ3": dict(qtd=1, tom=-0.4, ext=-0.4, setor=0.38, mercado=0.5 / 8),
        "WWWW3": dict(qtd=1, tom=-0.1, ext=-0.1, setor=NAN, mercado=0.5 / 8),
        # Empresa "6": sem notícia -> qtd 0; tom_setor = média das outras da S1 (0,06; 0,7; -0,4).
        "KKKK3": dict(qtd=0, tom=NAN, ext=NAN, setor=0.12, mercado=0.5 / 8),
    }
    for ticker, e in esperado.items():
        r = out.loc[ticker]
        assert r["noticias_dia_qtd"] == e["qtd"], ticker
        assert _iguais(r["noticias_dia_tom"], e["tom"]), ticker
        assert _iguais(r["noticias_dia_extremo"], e["ext"]), ticker
        assert _iguais(r["tom_setor"], e["setor"]), ticker
        assert _iguais(r["tom_mercado"], e["mercado"]), ticker
        assert np.isnan(r["mudanca_tom"]), ticker


def test_saida_mesma_ordem_e_colunas():
    nots, linhas = _tabela_a()
    out = variaveis_de_noticias(
        nots, linhas, CAL3, PARAMS, noite_aberta=None, cobertura_inicio=pd.Timestamp("2026-06-17")
    )
    assert list(out.columns) == list(linhas.columns) + COLUNAS_NOTICIAS
    assert list(out["ticker"]) == list(linhas["ticker"])


def test_teste_b_antes_da_cobertura_e_noite_aberta():
    nots, linhas = _tabela_a()
    linhas = pd.concat(
        [
            _linhas(("2026-06-17", "XXXX3", "1", "S1")),
            linhas,
            _linhas(("2026-06-19", "YYYY3", "2", "S1")),
        ],
        ignore_index=True,
    )
    out = variaveis_de_noticias(
        nots, linhas, CAL3, PARAMS, noite_aberta=pd.Timestamp("2026-06-19").date(),
        cobertura_inicio=pd.Timestamp("2026-06-18"),
    )
    antes = out[out["data"] == pd.Timestamp("2026-06-17")]
    assert antes[COLUNAS_NOTICIAS].isna().all(axis=None)
    # YYYY3 em 06-19 tem a notícia n5 (0,9), mas a janela do dia ainda não fechou: tudo vazio.
    aberta = out[out["data"] == pd.Timestamp("2026-06-19")].iloc[0]
    assert aberta[COLUNAS_NOTICIAS].isna().all()


def test_teste_b_antes_da_cobertura_zera_qtd_tambem():
    nots, linhas = _tabela_a()
    linhas = pd.concat([_linhas(("2026-06-17", "XXXX3", "1", "S1")), linhas], ignore_index=True)
    out = variaveis_de_noticias(
        nots, linhas, CAL3, PARAMS, noite_aberta=None, cobertura_inicio=pd.Timestamp("2026-06-18")
    )
    assert np.isnan(out.iloc[0]["noticias_dia_qtd"])
    assert out.iloc[1]["noticias_dia_qtd"] == 6


def test_teste_c_extremo():
    assert extremo(pd.Series([0.5, -0.5, 0.25])) == 0.0
    assert extremo(pd.Series([0.2, -0.6, 0.6])) == 0.0
    assert extremo(pd.Series([0.1, -0.7, 0.3])) == -0.7
    assert np.isnan(extremo(pd.Series([NAN, NAN])))
    assert np.isnan(extremo(pd.Series([], dtype=float)))


def test_teste_d_tom_mercado_conta_id_uma_vez():
    nots = _nots(
        ("n20", "1", "dia", "2026-06-18", 0.5),
        ("n20", "2", "dia", "2026-06-18", 0.5),
        ("n21", "1", "dia", "2026-06-18", -0.3),
    )
    linhas = _linhas(("2026-06-18", "XXXX3", "1", "S1"), ("2026-06-18", "YYYY3", "2", "S1"))
    out = variaveis_de_noticias(nots, linhas, CAL3, PARAMS, noite_aberta=None, cobertura_inicio=None)
    assert out["tom_mercado"].tolist() == pytest.approx([0.1, 0.1], abs=1e-12)


CAL_E = ["2026-06-12", "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"]


def _notas_e():
    """Notícias da empresa "1" do teste E (base de 06-18 = pregões 06-15, 06-16, 06-17)."""
    return _nots(
        ("a", "1", "dia", "2026-06-15", 0.2),
        ("b", "1", "dia", "2026-06-16", 0.4),
        ("c", "1", "dia", "2026-06-17", -0.3),
        ("d", "1", "dia", "2026-06-12", 0.9),
        ("e", "1", "dia", "2026-06-18", -0.8),
        ("f", "1", "dia", "2026-06-18", 0.5),
    )


def _linhas_e():
    return _linhas(
        ("2026-06-16", "XXXX3", "1", "S1"),
        ("2026-06-17", "XXXX3", "1", "S1"),
        ("2026-06-18", "XXXX3", "1", "S1"),
    )


def _mudanca(nots, params, cobertura=None):
    """Série data -> mudanca_tom das linhas do teste E."""
    out = variaveis_de_noticias(nots, _linhas_e(), CAL_E, params, noite_aberta=None, cobertura_inicio=cobertura)
    return out.set_index("data")["mudanca_tom"]


def test_teste_e_mudanca_tom_base_e_minimo():
    # base de 06-18: (0,2 + 0,4 - 0,3) / 3 = 0,1; tom de 06-18: (-0,8 + 0,5) / 2 = -0,15; mudança = -0,25.
    params = dataclasses.replace(PARAMS, mudanca_tom_pregoes=3, mudanca_tom_minimo=2)
    m = _mudanca(_notas_e(), params)
    assert m[pd.Timestamp("2026-06-18")] == pytest.approx(-0.25, abs=1e-12)
    assert np.isnan(m[pd.Timestamp("2026-06-16")])
    assert np.isnan(_mudanca(_notas_e(), dataclasses.replace(params, mudanca_tom_minimo=4))[pd.Timestamp("2026-06-18")])
    assert np.isnan(_mudanca(_notas_e(), params, pd.Timestamp("2026-06-13"))[pd.Timestamp("2026-06-17")])
    assert _mudanca(_notas_e(), params, pd.Timestamp("2026-06-13"))[pd.Timestamp("2026-06-18")] == pytest.approx(
        -0.25, abs=1e-12
    )


def test_mudanca_tom_nao_olha_pregao_depois_de_t():
    # Notícias do pregão t entram no tom de t (e não na base), por isso o teste usa só t+1.
    params = dataclasses.replace(PARAMS, mudanca_tom_pregoes=3, mudanca_tom_minimo=2)
    sem_futuro = _notas_e()
    futuro = _nots(
        ("g", "1", "dia", "2026-06-19", 0.99),
        ("h", "1", "dia", "2026-06-19", -0.99),
    )
    com_futuro = pd.concat([sem_futuro, futuro], ignore_index=True)
    antes = _mudanca(sem_futuro, params)[pd.Timestamp("2026-06-18")]
    depois = _mudanca(com_futuro, params)[pd.Timestamp("2026-06-18")]
    assert depois == pytest.approx(antes, abs=1e-12)
    assert depois == pytest.approx(-0.25, abs=1e-12)
