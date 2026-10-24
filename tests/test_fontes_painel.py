"""Testes da leitura do painel da rotina (etapa 8, fase 2): `fontes.ler_painel_*` e `ultimo_pregao_ibov`.

SQLite em memória criado no próprio teste (ou a fábrica `banco_teste`). Nenhum teste toca o banco da coleta.
"""

from datetime import date, datetime

import pandas as pd
import pytest
import sqlalchemy

from processamento import fontes
from processamento.fontes import ErroLeitura, ler_painel_etapas, ler_painel_execucoes, ultimo_pregao_ibov

SP = fontes.SP

COLUNAS_EXECUCOES = ["id", "tipo", "origem", "status", "aguardando", "iniciada_em", "finalizada_em"]
COLUNAS_ETAPAS = ["execucao_id", "etapa_id", "ordem", "status", "iniciada_em", "finalizada_em"]

LINHAS_EXECUCOES = [
    ("2026-10-25-daily-213000", "daily", "cron", "concluida", None, "2026-10-26 00:30:00", "2026-10-26 01:10:00"),
    ("2026-10-26-daily-080001", "daily", "cron", "em_andamento", None, "2026-10-26 11:00:01.489947", None),
]

# Inseridas fora de ordem de `ordem` de propósito (a leitura tem de ordenar).
LINHAS_ETAPAS = [
    ("2026-10-26-daily-080001", "enriquecimento", "3", "em_andamento", "2026-10-26 11:20:01", None),
    ("2026-10-26-daily-080001", "precos", "1", "concluida", "2026-10-26 11:00:02", "2026-10-26 11:05:00"),
    ("2026-10-25-daily-213000", "precos", "1", "concluida", "2026-10-26 00:30:00", "2026-10-26 00:35:00"),
    ("2026-10-26-daily-080001", "noticias", "2", "concluida", "2026-10-26 11:05:01", "2026-10-26 11:20:00"),
]


def _banco_painel():
    """SQLite em memória com as duas tabelas do painel; tudo em texto, como na fábrica do conftest."""
    eng = sqlalchemy.create_engine("sqlite://")
    pd.DataFrame(LINHAS_EXECUCOES, columns=COLUNAS_EXECUCOES).to_sql("v1-painel_execucoes", eng, index=False)
    pd.DataFrame(LINHAS_ETAPAS, columns=COLUNAS_ETAPAS).to_sql("v1-painel_etapas", eng, index=False)
    return lambda sql, params=None: fontes.executar_leitura(sql, params, engine=eng)


def test_execucoes_desde_utc_sem_fuso_e_datas_em_sao_paulo():
    ler = _banco_painel()
    df = ler_painel_execucoes(datetime(2026, 10, 26, 3, 0), ler)
    assert len(df) == 1
    linha = df.iloc[0]
    assert linha["id"] == "2026-10-26-daily-080001"
    assert linha["iniciada_em"] == pd.Timestamp("2026-10-26 08:00:01.489947", tz="America/Sao_Paulo")
    assert pd.isna(linha["finalizada_em"])
    assert linha["aguardando"] is None


def test_execucoes_desde_com_fuso_de_sao_paulo_vira_utc():
    ler = _banco_painel()
    df = ler_painel_execucoes(datetime(2026, 10, 26, 0, 0, tzinfo=SP), ler)  # = 03:00 UTC
    assert list(df["id"]) == ["2026-10-26-daily-080001"]


def test_pegadinha_do_fuso_00_30_utc_e_25_10_as_21_30_sp():
    ler = _banco_painel()
    # 25/10 21:00 SP = 00:00 UTC de 26/10: a execução das 00:30 UTC entra
    ambas = ler_painel_execucoes(datetime(2026, 10, 25, 21, 0, tzinfo=SP), ler)
    assert list(ambas["id"]) == ["2026-10-25-daily-213000", "2026-10-26-daily-080001"]
    assert ambas.iloc[0]["iniciada_em"] == pd.Timestamp("2026-10-25 21:30:00", tz="America/Sao_Paulo")
    # 25/10 21:31 SP = 00:31 UTC de 26/10: a das 00:30 UTC fica de fora
    so_uma = ler_painel_execucoes(datetime(2026, 10, 25, 21, 31, tzinfo=SP), ler)
    assert list(so_uma["id"]) == ["2026-10-26-daily-080001"]


def test_etapas_da_execucao_na_ordem_com_datas_em_sao_paulo():
    ler = _banco_painel()
    df = ler_painel_etapas("2026-10-26-daily-080001", ler)
    assert list(df["etapa_id"]) == ["precos", "noticias", "enriquecimento"]
    assert list(df["ordem"]) == [1, 2, 3]
    assert df.iloc[0]["finalizada_em"] == pd.Timestamp("2026-10-26 08:05:00", tz="America/Sao_Paulo")
    assert pd.isna(df.iloc[2]["finalizada_em"])


def test_ultimo_pregao_ibov_pula_fim_de_semana_e_devolve_none_sem_dados(banco_teste):
    ler = banco_teste()
    assert ultimo_pregao_ibov(date(2025, 10, 21), ler) == date(2025, 10, 21)
    assert ultimo_pregao_ibov(date(2025, 10, 19), ler) == date(2025, 10, 17)
    assert ultimo_pregao_ibov(date(2025, 10, 15), ler) is None


def test_tabela_sem_coluna_aguardando_vira_erro_legivel():
    eng = sqlalchemy.create_engine("sqlite://")
    sem_aguardando = [c for c in COLUNAS_EXECUCOES if c != "aguardando"]
    pd.DataFrame([], columns=sem_aguardando).to_sql("v1-painel_execucoes", eng, index=False)
    ler = lambda sql, params=None: fontes.executar_leitura(sql, params, engine=eng)
    with pytest.raises(ErroLeitura, match="sem a coluna aguardando"):
        ler_painel_execucoes(datetime(2026, 10, 26, 0, 0), ler)


def _gravando(ler, sqls):
    """Envolve `ler` e guarda cada SQL que passa por ele."""
    def gravador(sql, params=None):
        sqls.append(sql)
        return ler(sql, params)
    return gravador


def test_sql_gerado_passa_pela_trava_e_usa_crases(banco_teste):
    sqls = []
    ler_painel = _gravando(_banco_painel(), sqls)
    ler_precos = _gravando(banco_teste(), sqls)
    ler_painel_execucoes(datetime(2026, 10, 26, 3, 0), ler_painel)
    ler_painel_etapas("2026-10-26-daily-080001", ler_painel)
    ultimo_pregao_ibov(date(2025, 10, 21), ler_precos)
    assert sqls, "nenhuma consulta foi feita"
    for sql in sqls:
        fontes.validar_sql_leitura(sql)  # levanta ErroSomenteLeitura se não passar
    assert any("`v1-painel_execucoes`" in s and "`iniciada_em` >= :desde" in s for s in sqls)
    assert any("`v1-painel_etapas`" in s and "`execucao_id` = :id" in s for s in sqls)
    assert any("`v1-precos`" in s and "MAX(`data`)" in s for s in sqls)
