"""Testes de processamento/diagnostico/consultas.py (gabarito do plano, Fase 4a).

Nenhum teste conecta ao banco nem usa rede: o `ler` é uma função falsa que devolve DataFrames.
"""

import pandas as pd

from processamento import fontes
from processamento.diagnostico import consultas as c

MAPA = fontes.carregar_mapa()

CONTRATO_AUSENTE_ESPERADO = {
    "v1-cadastro", "v1-mudancas_ticker", "v1-balancos",
    "v1-acoes_emitidas", "v1-proventos", "v1-indices",
}
AUXILIAR_AUSENTE_ESPERADO = {
    "staging_article_sentiment", "v1-painel_execucoes", "v1-painel_etapas", "v1-raw_b3_cadastro",
}


# ---------------------------------------------------------------------------
# Construtores de SQL (string exata)
# ---------------------------------------------------------------------------

def test_montar_sql_resumo_com_data():
    assert c.montar_sql_resumo("v1-precos", "data", "ticker") == (
        "SELECT COUNT(*) AS linhas, MIN(`data`) AS inicio, MAX(`data`) AS fim, "
        "COUNT(DISTINCT `ticker`) AS entidades FROM `v1-precos`"
    )


def test_montar_sql_resumo_sem_data():
    assert c.montar_sql_resumo("v1-cadastro", None, "ticker") == (
        "SELECT COUNT(*) AS linhas, NULL AS inicio, NULL AS fim, "
        "COUNT(DISTINCT `ticker`) AS entidades FROM `v1-cadastro`"
    )


def test_montar_sql_duplicatas_chave_simples():
    assert c.montar_sql_duplicatas("v1-precos", ["`data`", "`ticker`"]) == (
        "SELECT COUNT(*) AS grupos, COALESCE(SUM(n - 1), 0) AS linhas_extras "
        "FROM (SELECT COUNT(*) AS n FROM `v1-precos` GROUP BY `data`, `ticker` "
        "HAVING COUNT(*) > 1) d"
    )


def test_montar_sql_duplicatas_com_where_e_md5():
    assert c.montar_sql_duplicatas(
        "v1-noticias", ["`ticker`", "MD5(`link`)"], where="`link` IS NOT NULL"
    ) == (
        "SELECT COUNT(*) AS grupos, COALESCE(SUM(n - 1), 0) AS linhas_extras "
        "FROM (SELECT COUNT(*) AS n FROM `v1-noticias` WHERE `link` IS NOT NULL "
        "GROUP BY `ticker`, MD5(`link`) HAVING COUNT(*) > 1) d"
    )


def test_montar_sql_vazios_por_tipo():
    assert c.montar_sql_vazios(
        "v1-precos", [("data", "date"), ("ticker", "varchar"), ("volume", "bigint")]
    ) == (
        "SELECT COUNT(*) AS total, SUM(`data` IS NULL) AS `nulos__data`, "
        "SUM(`ticker` IS NULL) AS `nulos__ticker`, SUM(`ticker` = '') AS `vazios__ticker`, "
        "SUM(`volume` IS NULL) AS `nulos__volume`, SUM(`volume` = 0) AS `zeros__volume` "
        "FROM `v1-precos`"
    )


def test_montar_sql_distintos():
    assert c.montar_sql_distintos("v1-noticias", "papel") == (
        "SELECT valor, COUNT(*) AS n FROM (SELECT `papel` COLLATE utf8mb4_bin AS valor "
        "FROM `v1-noticias`) d GROUP BY valor ORDER BY n DESC"
    )


# ---------------------------------------------------------------------------
# secao_existencia
# ---------------------------------------------------------------------------

def _ler_existencia(sql):
    assert "information_schema.TABLES" in sql
    return pd.DataFrame({"tabela": ["v1-noticias", "v1-precos", "raw_articles"]})


def test_secao_existencia_conjunto_de_existentes():
    _, existentes = c.secao_existencia(_ler_existencia, MAPA)
    assert existentes == {"v1-noticias", "v1-precos", "raw_articles"}


def test_secao_existencia_conta_tabela_ausente():
    secao, _ = c.secao_existencia(_ler_existencia, MAPA)
    ausentes = [d for d in secao["divergencias"] if d["tema"] == "tabela_ausente"]
    assert len(ausentes) == 10
    contrato = {d["tabela"] for d in ausentes} & CONTRATO_AUSENTE_ESPERADO
    assert contrato == CONTRATO_AUSENTE_ESPERADO
    assert {d["tabela"] for d in ausentes} - CONTRATO_AUSENTE_ESPERADO == AUXILIAR_AUSENTE_ESPERADO


def test_secao_existencia_composicao_ibov_so_vira_nota():
    secao, _ = c.secao_existencia(_ler_existencia, MAPA)
    assert not any("v1-composicao_ibov" in str(d) for d in secao["divergencias"])
    assert any("v1-composicao_ibov" in nota for nota in secao["notas"])


# ---------------------------------------------------------------------------
# secao_colunas_chaves
# ---------------------------------------------------------------------------

COLUNAS_CADASTRO = [
    "ticker", "cnpj", "empresa", "setor", "subsetor", "tipo_acao", "unit_qtd_on", "unit_qtd_pn",
]


def _ler_cadastro(sql):
    if "KEY_COLUMN_USAGE" in sql:
        return pd.DataFrame({"tabela": ["v1-cadastro"], "coluna": ["ticker"], "pos": [1]})
    colunas = COLUNAS_CADASTRO + ["atualizado_em"]
    return pd.DataFrame({
        "tabela": ["v1-cadastro"] * len(colunas),
        "coluna": colunas,
        "tipo": ["varchar"] * 6 + ["int", "int", "datetime"],
        "nulo": ["NO"] * 8 + ["YES"],
        "pos": list(range(1, len(colunas) + 1)),
    })


def test_secao_colunas_chaves_detecta_coluna_extra():
    secao, df_colunas = c.secao_colunas_chaves(_ler_cadastro, MAPA, {"v1-cadastro"})
    assert len(secao["divergencias"]) == 1
    divergencia = secao["divergencias"][0]
    assert divergencia["tema"] == "coluna_extra"
    assert "atualizado_em" in divergencia["detalhe"]
    assert set(df_colunas["coluna"]) == set(COLUNAS_CADASTRO + ["atualizado_em"])
