"""Medição da deduplicação entre origens (processamento/diagnostico/dedup_origens.py): contas das seções 1 e 2.

Leitor falso (`banco_teste`, SQLite de tests/dados com as tabelas do cenário): nenhum teste abre o banco real.
Cenário (PETR4, LA = meia-noite de PDT em 2025-10-07 e 2025-10-17, por isso só data):
- par 1: GN "...investimentos - InfoMoney" 17/10 (só data) × WP "...investimentos" 17/10 10:00, mesma URL
  (infomoney.com.br/x): cópia de título com Δ=0 que também casa por URL;
- par 2: GN 07/10 (só data) × WP 17/10 12:00, títulos diferentes, mesma URL (infomoney.com.br/y): só URL, 10 dias.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from processamento import fontes
from processamento.diagnostico import dedup_origens as d
from processamento.experimento import noticias as expn
from processamento.experimento.parametros import carregar_parametros_experimento

PARAMS = carregar_parametros_experimento()
COLUNAS_V1 = [
    "id", "ticker", "data_hora_publicacao", "data_hora_coleta", "titulo", "fonte", "link",
    "prob_positivo", "prob_neutro", "prob_negativo", "origem", "papel", "tipo_conteudo", "evento",
    "qualidade", "data_publicacao", "momento_pregao",
]
T = "Petrobras anuncia novo plano de investimentos"


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Nenhum teste deste arquivo abre o banco da coleta."""
    def _proibido(*args, **kwargs):
        raise AssertionError("criar_engine chamado num teste: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


def _v1(id_, origem, dia, hora, titulo, link):
    return {
        "id": id_, "ticker": "PETR4", "data_hora_publicacao": f"{dia}T{hora}-03:00",
        "data_hora_coleta": "2026-09-07T17:38:43-03:00", "titulo": titulo, "fonte": "F", "link": link,
        "prob_positivo": "0.5", "prob_neutro": "0.3", "prob_negativo": "0.2", "origem": origem, "papel": None,
        "tipo_conteudo": None, "evento": None, "qualidade": None, "data_publicacao": dia,
        "momento_pregao": "durante",
    }


V1 = [
    _v1("n000001", "google_news", "2025-10-17", "04:00:00", f"{T} - InfoMoney", "https://exemplo.invalid/n1"),
    _v1("w000001", "wordpress", "2025-10-17", "10:00:00", T, "https://infomoney.com.br/x/?utm=1"),
    _v1("n000002", "google_news", "2025-10-07", "04:00:00", "Vale sobe muito hoje", "https://exemplo.invalid/n2"),
    _v1("w000002", "wordpress", "2025-10-17", "12:00:00", "Assunto totalmente diferente aqui",
        "https://infomoney.com.br/y/"),
]
RAW = [
    (1, "pt", "2025-10-17 07:00:00", "minute", "google_news", "https://infomoney.com.br/x"),
    (2, "pt", "2025-10-07 07:00:00", "minute", "google_news", "https://infomoney.com.br/y"),
]
COLUNAS_RAW = ["id", "lang", "published_at", "published_precision", "origem", "resolved_url"]


@pytest.fixture
def cenario(banco_teste):
    def _substituir(df):
        return pd.DataFrame(V1, columns=df.columns)

    def _raw(df):
        return pd.DataFrame(RAW, columns=COLUNAS_RAW)

    return banco_teste(alterar={"v1-noticias": _substituir, "raw_articles": _raw})


def _entradas(ler):
    return d.carregar_entradas(ler=ler)


def _com(entradas):
    return expn.ligar_empresa(
        expn.filtrar_versao(entradas["novo"], "todas", PARAMS)[0], entradas["cnpj_de"], entradas["mudancas"]
    )


def test_secao_1_conta_regras_e_titulo_com_url(cenario):
    entradas = _entradas(cenario)
    com = _com(entradas)
    _, _, pares = expn.deduplicar_com_pares(com, PARAMS)
    _, _, pares0 = expn.deduplicar_com_pares(com, dataclasses.replace(PARAMS, titulo_palavras_min_entre_origens=0))
    sec = d.secao_remocoes(pares, pares0, pares)

    assert sec["total"] == {"titulo_mesmo_dia": 1, "titulo_janela": 0, "url": 1}
    assert sec["titulo_com_url"] == 1  # o par de título também casa por URL
    assert sec["url_fora_de_um_dia"] == 1  # a remoção por URL tem 10 dias
    assert sec["segurados"] == 0  # os títulos têm 6 palavras: o mínimo não segura nada aqui
    assert list(sec["por_origem"]["pares"]) == [2]  # google_news removida, wordpress mantida, nos dois pares


def test_secao_2_pares_por_url_entre_origens(cenario):
    com = _com(_entradas(cenario))
    pares_url = d.pares_por_url(com)
    sec = d.secao_url(pares_url)

    assert sec["total"] == 2
    assert sec["dentro"] == 1  # o par de 17/10 (Δ=0)
    assert sec["fora"] == 1
    assert sec["faixas"] == {"2 a 7 dias": 0, "8 a 30 dias": 1, "mais de 30 dias": 0}


def test_amostra_tem_as_colunas_e_os_pares_removidos(cenario):
    com = _com(_entradas(cenario))
    _, _, pares = expn.deduplicar_com_pares(com, PARAMS)
    amostra = d.amostra(pares)

    assert list(amostra.columns) == d.COLUNAS_AMOSTRA
    assert len(amostra) == len(pares) == 2
    assert set(amostra["regra"]) == {"titulo_mesmo_dia", "url"}


def test_invariancia_de_entrada_igual_nao_tem_diferenca(cenario):
    entradas = _entradas(cenario)
    inv = d.comparar_invariancia(
        entradas["novo"], entradas["novo"], entradas["cal"], entradas["cnpj_de"], entradas["mudancas"],
        PARAMS, PARAMS,
    )
    assert inv["diferencas"] == 0


def test_calcular_e_relatorio_com_as_cinco_secoes(cenario):
    entradas = _entradas(cenario)
    resultado = d.calcular(entradas, PARAMS, ler=cenario)
    texto = d.relatorio(resultado)

    for titulo in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5."):
        assert titulo in texto
    assert resultado["tempos"]["linhas_urls"] == 2
