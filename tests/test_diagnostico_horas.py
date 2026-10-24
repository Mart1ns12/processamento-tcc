"""Diagnóstico da hora das notícias por ano (Fase 4): hora real, "só data" N1-A e sem hora.

Sem banco: `ler` falso roteado pelo SQL pedido. Valores esperados vêm do plano
(`docs/plano_historico_novo.md`, seção 3.3, casos 4A, 4B e 4C).
"""

import pandas as pd

from processamento import fontes
from processamento.diagnostico.regras import nova_secao
from processamento.diagnostico.temas import _horas_por_ano, meia_noite_por_ano_origem

MAPA = fontes.carregar_mapa()
EXISTENTES_COM_RAW = {"v1-noticias", "raw_articles"}
EXISTENTES_SEM_RAW = {"v1-noticias"}


def _ler_factory(com_raw: bool):
    """`ler` falso: totais, candidatos a meia-noite e (se `com_raw`) marca 'só data' do raw_articles."""
    def _ler(sql):
        if "AS sem_hora" in sql:
            return pd.DataFrame({
                "ano": [2024, 2024, 2025],
                "origem": ["cvm_ipe", "google_news", "google_news"],
                "total": [10, 100, 200],
                "sem_hora": [10, 91, 4],
            })
        if "'00:00'" in sql:
            return pd.DataFrame({
                "ano": [2025, 2025, 2025, 2025],
                "origem": ["google_news"] * 4,
                "instante": [
                    "2025-06-10T04:00:00-03:00",   # 00:00 em Los Angeles (PDT)
                    "2025-01-10T05:00:00-03:00",   # 00:00 em Los Angeles (PST)
                    "2025-01-10T04:00:00-03:00",   # 23:00 PST: hora real
                    "2025-06-10T10:00:00-03:00",   # 06:00 PDT: hora real
                ],
                "n": [150, 30, 6, 2],
            })
        if "published_precision" in sql:
            if not com_raw:
                raise AssertionError(f"não devia consultar raw_articles: {sql}")
            return pd.DataFrame({
                "ano": [2024, 2024, 2024, 2025],
                "precisao": ["date", "datetime", None, "date"],
                "n": [85, 5, 1, 4],
            })
        raise AssertionError(f"SQL inesperado: {sql}")
    return _ler


def test_horas_por_ano_4a_com_raw_articles():
    secao = nova_secao("x")
    df = _horas_por_ano(_ler_factory(True), MAPA, EXISTENTES_COM_RAW, secao)

    tabelas = {t["subtitulo"]: t for t in secao["tabelas"]}
    por_ano = tabelas["Hora da publicação, por ano (artigos distintos)"]
    assert por_ano["colunas"] == [
        "ano", "total", "hora_real", "pct_hora_real", "so_data_n1a", "pct_so_data_n1a", "sem_hora", "pct_sem_hora",
    ]
    assert por_ano["linhas"] == [[2024, 110, 9, 8.2, 0, 0.0, 101, 91.8], [2025, 200, 16, 8.0, 180, 90.0, 4, 2.0]]

    por_origem = tabelas["Hora da publicação, por ano e origem (artigos distintos)"]
    assert por_origem["colunas"] == [
        "ano", "origem", "total", "hora_real", "pct_hora_real", "so_data_n1a", "pct_so_data_n1a",
        "sem_hora", "pct_sem_hora",
    ]
    assert por_origem["linhas"] == [
        [2024, "cvm_ipe", 10, 0, 0.0, 0, 0.0, 10, 100.0],
        [2024, "google_news", 100, 9, 9.0, 0, 0.0, 91, 91.0],
        [2025, "google_news", 200, 16, 8.0, 180, 90.0, 4, 2.0],
    ]

    assert secao["notas"] == [
        "89 notícias do Google News sem hora, marcadas 'só data' pela coleta "
        "(raw_articles.published_precision = 'date'): 2024: 85, 2025: 4",
    ]
    assert secao["divergencias"] == [{
        "tema": "noticia_sem_hora",
        "tabela": "v1-noticias",
        "detalhe": "2024: 6 de 100 sem hora e sem a marca 'só data' em raw_articles",
    }]
    assert sorted(set(df["ano"])) == [2024, 2025]


def test_horas_por_ano_4b_sem_raw_articles():
    secao = nova_secao("x")
    _horas_por_ano(_ler_factory(False), MAPA, EXISTENTES_SEM_RAW, secao)

    assert secao["notas"] == ["Marca 'só data' (raw_articles): pulada: tabela ausente (`raw_articles`)"]
    assert secao["divergencias"] == [
        {"tema": "noticia_sem_hora", "tabela": "v1-noticias",
         "detalhe": "2024: 91 de 100 sem hora e sem a marca 'só data' em raw_articles"},
        {"tema": "noticia_sem_hora", "tabela": "v1-noticias",
         "detalhe": "2025: 4 de 200 sem hora e sem a marca 'só data' em raw_articles"},
    ]


def test_meia_noite_por_ano_origem_4c():
    candidatos = pd.DataFrame({
        "ano": [2025, 2025, 2025, 2025],
        "origem": ["google_news"] * 4,
        "instante": [
            "2025-06-10T04:00:00-03:00",
            "2025-01-10T05:00:00-03:00",
            "2025-01-10T04:00:00-03:00",
            "2025-06-10T10:00:00-03:00",
        ],
        "n": [150, 30, 6, 2],
    })
    assert meia_noite_por_ano_origem(candidatos) == {(2025, "google_news"): 180}
