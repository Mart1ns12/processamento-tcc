"""Geração do relatório markdown do diagnóstico.

Módulo puro: recebe as seções já calculadas (dicts com titulo, notas, tabelas
e divergencias) e devolve texto markdown. Não acessa banco nem arquivos.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd


def _e_nulo(v) -> bool:
    """Diz se o valor representa ausência (None, NaN, NaT ou pd.NA)."""
    if v is None or v is pd.NA or v is pd.NaT:
        return True
    if isinstance(v, (float, np.floating)):
        return math.isnan(float(v))
    if isinstance(v, Decimal):
        return v.is_nan()
    return False


def formatar_valor(v) -> str:
    """Converte um valor de célula em texto para a tabela markdown.

    Ordem dos testes: NULL, bool, coleção, inteiro, decimal, data/hora, data, texto.
    """
    if _e_nulo(v):
        return "NULL"
    if isinstance(v, (bool, np.bool_)):
        return "sim" if v else "não"
    if isinstance(v, (list, tuple, set)):
        if not v:
            return "—"
        itens = v
        if isinstance(v, set):
            try:
                itens = sorted(v)
            except TypeError:
                itens = sorted(v, key=str)
        return ", ".join(formatar_valor(x) for x in itens)
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (Decimal, float, np.floating)):
        x = float(v)
        if abs(x) >= 1e6:
            return f"{x:.3e}"
        return f"{x:.4f}".rstrip("0").rstrip(".")
    if isinstance(v, datetime):
        if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
            return v.date().isoformat()
        return v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        return v.replace("|", "\\|").replace("\n", " ")
    return str(v)


def tabela_md(colunas, linhas) -> str:
    """Monta uma tabela markdown; sem linhas devolve um aviso em itálico."""
    if not linhas:
        return "_(sem linhas)_"
    cabecalho = "| " + " | ".join(formatar_valor(c) for c in colunas) + " |"
    separador = "|" + "|".join(["---"] * len(colunas)) + "|"
    corpo = ["| " + " | ".join(formatar_valor(c) for c in linha) + " |" for linha in linhas]
    return "\n".join([cabecalho, separador, *corpo])


def gerar_markdown(cabecalho: dict, secoes: list[dict]) -> str:
    """Gera o documento completo: cabeçalho, divergências e uma seção por item."""
    blocos = [
        "# Diagnóstico do banco da coleta (só leitura)",
        "\n".join([
            f"- Gerado em: {cabecalho['gerado_em']}",
            f"- Banco: {cabecalho['banco']}",
            f"- MySQL: {cabecalho['versao_mysql']}",
            "- Comando: `python -m processamento.diagnostico`",
        ]),
        "> Este relatório só leu o banco (SELECT/SHOW). Nada foi gravado.",
        "## Divergências × especificação",
    ]

    divergencias = [
        (secao["titulo"], d) for secao in secoes for d in secao.get("divergencias", [])
    ]
    if not divergencias:
        blocos.append("Nenhuma divergência encontrada.")
    else:
        linhas = [
            [i, d["tema"], d["tabela"], d["detalhe"]]
            for i, (_, d) in enumerate(divergencias, start=1)
        ]
        blocos.append(tabela_md(["#", "Tema", "Tabela", "Detalhe"], linhas))

    for i, secao in enumerate(secoes, start=1):
        blocos.append(f"## {i}. {secao['titulo']}")
        notas = secao.get("notas", [])
        tabelas = secao.get("tabelas", [])
        if notas:
            blocos.append("\n".join(f"- {nota}" for nota in notas))
        for tabela in tabelas:
            blocos.append(f"### {tabela['subtitulo']}")
            blocos.append(tabela_md(tabela["colunas"], tabela["linhas"]))
        if not notas and not tabelas:
            blocos.append("_(sem dados)_")

    return "\n\n".join(blocos) + "\n"
