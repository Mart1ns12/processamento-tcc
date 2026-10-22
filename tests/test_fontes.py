"""Testes de processamento/fontes.py: mapa de nomes, configuração, trava de SQL.

Nenhum teste conecta ao MySQL nem usa rede. Onde é preciso um engine, usa-se sqlite em memória.
"""

import pandas as pd
import pytest
import sqlalchemy
from sqlalchemy.engine import URL, Engine

from processamento import fontes
from processamento.fontes import (
    ErroConfiguracao,
    ErroSomenteLeitura,
    carregar_mapa,
    citar,
    coluna_sql,
    criar_engine,
    executar_leitura,
    ler_config_banco,
    montar_url,
    nome_real,
    tabela_sql,
    validar_sql_leitura,
    verificar_sessao_somente_leitura,
)

ACEITA = [
    "SELECT 1",
    "  select * from `v1-precos`",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "SHOW TABLES",
    "-- comentario\nSELECT 1",
    "/* c */ SELECT 1",
    "SELECT 1;",
    "SELECT 1; ",
    "SELECT COUNT(*) AS n FROM `v1-painel_execucoes` WHERE status = 'concluida'",
    "SELECT atualizada_em FROM `v1-painel_etapas`",
    "SELECT `data_hora_coleta` FROM `v1-noticias`",
    "SELECT @@SESSION.transaction_read_only AS ro",
]

RECUSA = [
    "INSERT INTO `v1-precos` VALUES (1)",
    "update `v1-precos` set volume = 0",
    "DELETE FROM x",
    "DROP TABLE x",
    "CREATE TABLE x (a int)",
    "TRUNCATE x",
    "ALTER TABLE x ADD c int",
    "SELECT 1; DELETE FROM x",
    "WITH x AS (SELECT 1) DELETE FROM y",
    "SELECT * FROM x INTO OUTFILE '/tmp/a'",
    "SELECT * FROM x FOR UPDATE",
    "REPLACE INTO x VALUES (1)",
    "SET GLOBAL read_only = 0",
    "CALL proc()",
    "LOAD DATA INFILE 'a' INTO TABLE x",
    "",
    "   ",
    "GRANT ALL ON *.* TO u",
    "LOCK TABLES x WRITE",
    "/* x */ DELETE FROM y",
    "-- SELECT\nDELETE FROM y",
    "SELECT 1 FROM x WHERE a = 'drop'",
]

CONFIG_BANCO_OK = {
    "IP_BANCO": "h",
    "PORTA_BANCO": "3306",
    "NOME_BANCO": "db",
    "USER_BANCO": "u",
    "SENHA_BANCO": "segredo",
}


@pytest.mark.parametrize("sql", ACEITA)
def test_trava_aceita_leituras(sql):
    assert validar_sql_leitura(sql)


@pytest.mark.parametrize("sql", RECUSA)
def test_trava_recusa_escritas(sql):
    with pytest.raises(ErroSomenteLeitura):
        validar_sql_leitura(sql)


def test_validar_devolve_sql_limpo():
    assert validar_sql_leitura("SELECT 1;  ") == "SELECT 1"


def test_executar_leitura_recusa_antes_de_tocar_engine():
    with pytest.raises(ErroSomenteLeitura):
        executar_leitura("DELETE FROM x", engine=None)


def test_executar_leitura_sqlite_em_memoria():
    eng = sqlalchemy.create_engine("sqlite://")
    df = executar_leitura("SELECT 1 AS a", engine=eng)
    assert list(df.columns) == ["a"]
    assert df["a"].tolist() == [1]


def test_verificar_sessao_somente_leitura_aceita_ro_1():
    verificar_sessao_somente_leitura(lambda sql: pd.DataFrame({"ro": [1]}))


def test_verificar_sessao_somente_leitura_recusa_ro_0():
    with pytest.raises(ErroSomenteLeitura):
        verificar_sessao_somente_leitura(lambda sql: pd.DataFrame({"ro": [0]}))


def test_verificar_sessao_somente_leitura_recusa_resultado_vazio():
    with pytest.raises(ErroSomenteLeitura):
        verificar_sessao_somente_leitura(lambda sql: pd.DataFrame({"ro": []}))


def test_verificar_sessao_usa_select_aceito_pela_trava():
    consultas = []

    def ler(sql):
        consultas.append(sql)
        return pd.DataFrame({"ro": [1]})

    verificar_sessao_somente_leitura(ler)
    assert validar_sql_leitura(consultas[0]) == consultas[0]


def test_citar():
    assert citar("v1-precos") == "`v1-precos`"
    with pytest.raises(ValueError):
        citar("a`b")
    with pytest.raises(ValueError):
        citar("")


def test_ler_config_banco_ok():
    assert ler_config_banco(CONFIG_BANCO_OK) == {
        "host": "h",
        "porta": 3306,
        "banco": "db",
        "usuario": "u",
        "senha": "segredo",
    }


def test_ler_config_banco_sem_senha():
    env = {k: v for k, v in CONFIG_BANCO_OK.items() if k != "SENHA_BANCO"}
    with pytest.raises(ErroConfiguracao) as info:
        ler_config_banco(env)
    assert "SENHA_BANCO" in str(info.value)


def test_ler_config_banco_porta_invalida():
    env = dict(CONFIG_BANCO_OK, PORTA_BANCO="abc")
    with pytest.raises(ErroConfiguracao) as info:
        ler_config_banco(env)
    assert "PORTA_BANCO" in str(info.value)


def test_montar_url_sem_expor_senha():
    cfg = ler_config_banco(CONFIG_BANCO_OK)
    url = montar_url(cfg)
    assert isinstance(url, URL)
    assert url.drivername == "mysql+pymysql"
    assert url.host == "h"
    assert url.port == 3306
    assert url.database == "db"
    assert url.query["charset"] == "utf8mb4"
    assert "segredo" not in str(url)


def test_criar_engine_nao_conecta_e_nao_expoe_senha(monkeypatch):
    # Não lê o .env real: o load_dotenv é trocado por no-op e as variáveis vêm do teste.
    monkeypatch.setattr(fontes, "load_dotenv", lambda *a, **k: None)
    for var, valor in CONFIG_BANCO_OK.items():
        monkeypatch.setenv(var, valor)
    eng = criar_engine()
    assert isinstance(eng, Engine)
    assert eng.url.drivername == "mysql+pymysql"
    assert "segredo" not in str(eng.url)
    eng.dispose()


def test_carregar_mapa_tabelas():
    assert set(carregar_mapa()["tabelas"]) == {
        "noticias",
        "precos",
        "cadastro",
        "mudancas_ticker",
        "balancos",
        "acoes_emitidas",
        "proventos",
        "indices",
    }


GABARITO_CHAVES = {
    "noticias": ["id", "ticker"],
    "precos": ["data", "ticker"],
    "cadastro": ["ticker"],
    "mudancas_ticker": ["ticker_antigo"],
    "balancos": ["cnpj", "tipo_documento", "data_inicio_periodo", "data_fim_periodo"],
    "acoes_emitidas": ["cnpj", "data_referencia"],
    "proventos": ["ticker", "tipo", "data_com"],
    "indices": ["data", "indice"],
}


@pytest.mark.parametrize("tabela", sorted(GABARITO_CHAVES))
def test_chaves_do_contrato(tabela):
    entrada = carregar_mapa()["tabelas"][tabela]
    assert entrada["chave"] == GABARITO_CHAVES[tabela]
    for coluna in entrada["chave"]:
        assert coluna in entrada["colunas"]


@pytest.mark.parametrize("tabela", sorted(GABARITO_CHAVES))
def test_nome_real_com_prefixo_v1(tabela):
    assert nome_real(tabela) == "v1-" + tabela


def test_tabela_e_coluna_sql():
    assert tabela_sql("raw_articles") == "`raw_articles`"
    assert coluna_sql("noticias", "data_hora_publicacao") == "`data_hora_publicacao`"


def test_nome_real_desconhecido():
    with pytest.raises(ValueError):
        nome_real("inexistente")


def test_valores_permitidos_do_mapa_sao_texto():
    # YAML lê ON/OFF/YES/NO sem aspas como booleano: todo valor permitido precisa ser str
    from processamento.fontes import carregar_mapa

    for cfg in carregar_mapa()["tabelas"].values():
        for coluna, valores in (cfg.get("valores_permitidos") or {}).items():
            assert all(isinstance(v, str) for v in valores), coluna
