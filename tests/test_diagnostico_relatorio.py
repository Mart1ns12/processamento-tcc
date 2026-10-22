"""Testes do relatório markdown do diagnóstico (gabarito da Fase 3 do plano)."""

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from processamento.diagnostico.relatorio import formatar_valor, gerar_markdown, tabela_md


# ---------- formatar_valor ----------

@pytest.mark.parametrize(
    "entrada, esperado",
    [
        (None, "NULL"),
        (float("nan"), "NULL"),
        (np.nan, "NULL"),
        (pd.NA, "NULL"),
        (True, "sim"),
        (False, "não"),
        (np.bool_(True), "sim"),
        (3, "3"),
        (np.int64(7), "7"),
        (75.0, "75"),
        (0.5, "0.5"),
        (2.25, "2.25"),
        (Decimal("2.50"), "2.5"),
        (1234567.0, "1.235e+06"),
        (date(2026, 1, 5), "2026-01-05"),
        (datetime(2026, 1, 5, 11, 0), "2026-01-05 11:00:00"),
        (pd.Timestamp("2026-01-05"), "2026-01-05"),
        ("a|b", "a\\|b"),
        ("linha1\nlinha2", "linha1 linha2"),
        (["a", "b"], "a, b"),
        ([], "—"),
        ((), "—"),
        (set(), "—"),
    ],
)
def test_formatar_valor(entrada, esperado):
    assert formatar_valor(entrada) == esperado


def test_formatar_valor_set_ordenado():
    assert formatar_valor({"b", "a", "c"}) == "a, b, c"


# ---------- tabela_md ----------

def test_tabela_md_com_nulo():
    esperado = "| ano | pct |\n|---|---|\n| 2025 | 75 |\n| 2026 | NULL |"
    assert tabela_md(["ano", "pct"], [[2025, 75.0], [2026, None]]) == esperado


def test_tabela_md_sem_linhas():
    assert tabela_md(["ano", "pct"], []) == "_(sem linhas)_"


# ---------- gerar_markdown ----------

CAB = {"gerado_em": "2026-10-22 09:00 (America/Sao_Paulo)", "banco": "tcc_scraper", "versao_mysql": "8.0.36"}


def _secoes_com_divergencia():
    return [
        {
            "titulo": "Tabelas",
            "notas": ["8 de 8 tabelas do contrato existem."],
            "tabelas": [
                {
                    "subtitulo": "Existência",
                    "colunas": ["tabela", "existe"],
                    "linhas": [["v1-noticias", True]],
                }
            ],
            "divergencias": [],
        },
        {
            "titulo": "Balanços",
            "notas": [],
            "tabelas": [],
            "divergencias": [
                {"tema": "escala", "tabela": "v1-balancos", "detalhe": "mediana da ordem de grandeza = 6"}
            ],
        },
    ]


def test_gerar_markdown_cabecalho_e_fim():
    texto = gerar_markdown(CAB, _secoes_com_divergencia())
    assert texto.startswith("# Diagnóstico do banco da coleta (só leitura)\n")
    assert texto.endswith("\n")
    assert not texto.endswith("\n\n")


def test_gerar_markdown_conteudo_esperado():
    texto = gerar_markdown(CAB, _secoes_com_divergencia())
    assert "- Banco: tcc_scraper" in texto
    assert "| 1 | escala | v1-balancos | mediana da ordem de grandeza = 6 |" in texto
    assert "## 1. Tabelas" in texto
    assert "- 8 de 8 tabelas do contrato existem." in texto
    assert "### Existência" in texto
    assert "| v1-noticias | sim |" in texto
    assert "## 2. Balanços\n\n_(sem dados)_" in texto


def test_gerar_markdown_ordem_das_secoes():
    texto = gerar_markdown(CAB, _secoes_com_divergencia())
    i_div = texto.index("## Divergências × especificação")
    i_1 = texto.index("## 1. Tabelas")
    i_2 = texto.index("## 2. Balanços")
    assert i_div < i_1 < i_2


def test_gerar_markdown_sem_divergencias():
    secoes = _secoes_com_divergencia()
    secoes[1]["divergencias"] = []
    texto = gerar_markdown(CAB, secoes)
    assert "Nenhuma divergência encontrada." in texto
    assert "| # | Tema | Tabela | Detalhe |" not in texto
