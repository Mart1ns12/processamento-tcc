"""Acesso ao banco da coleta: mapa de nomes, conexão somente leitura e trava de SQL.

Só este módulo monta SQL sobre as tabelas da coleta. Os nomes reais de tabelas e
colunas ficam em `config/fontes.yaml`. A conexão é sempre `READ ONLY` e cada consulta
passa pela trava `validar_sql_leitura` antes de tocar no banco.
"""

from __future__ import annotations

import functools
import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, event, text

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_MAPA = Path(__file__).resolve().parent / "config" / "fontes.yaml"
VARIAVEIS_BANCO = ("IP_BANCO", "PORTA_BANCO", "NOME_BANCO", "USER_BANCO", "SENHA_BANCO")


class ErroConfiguracao(Exception):
    """Configuração do banco ausente ou inválida (nunca mostra valores secretos)."""


class ErroSomenteLeitura(Exception):
    """Consulta recusada pela trava de somente leitura."""


@functools.lru_cache
def carregar_mapa(caminho: str | None = None) -> dict:
    """Lê o `fontes.yaml` (ou o caminho dado) e devolve o dicionário do mapa."""
    arquivo = Path(caminho) if caminho else CAMINHO_MAPA
    with arquivo.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _entrada(tabela: str) -> dict:
    """Procura a tabela do contrato em `tabelas` e depois em `auxiliares`."""
    mapa = carregar_mapa()
    for grupo in ("tabelas", "auxiliares"):
        if tabela in mapa.get(grupo, {}):
            return mapa[grupo][tabela]
    raise ValueError(f"tabela do contrato desconhecida: {tabela}")


def nome_real(tabela: str) -> str:
    """Nome da tabela no banco da coleta (ex.: 'noticias' -> 'v1-noticias')."""
    return _entrada(tabela)["nome_real"]


def coluna_real(tabela: str, coluna: str) -> str:
    """Nome da coluna no banco da coleta, a partir do nome do contrato."""
    colunas = _entrada(tabela).get("colunas", {})
    if coluna not in colunas:
        raise ValueError(f"tabela {tabela} sem a coluna {coluna} no mapa")
    return colunas[coluna]


def citar(nome: str) -> str:
    """Envolve um identificador em crases para o MySQL (aceita hífen)."""
    if not nome or "`" in nome:
        raise ValueError(f"identificador SQL inválido: {nome!r}")
    return "`" + nome + "`"


def tabela_sql(tabela: str) -> str:
    """Nome real da tabela já citado para SQL."""
    return citar(nome_real(tabela))


def coluna_sql(tabela: str, coluna: str) -> str:
    """Nome real da coluna já citado para SQL."""
    return citar(coluna_real(tabela, coluna))


def ler_config_banco(env: Mapping[str, str]) -> dict:
    """Lê as variáveis do banco de `env` e devolve host, porta, banco, usuário e senha.

    Não imprime nem inclui valores nas mensagens de erro, só os nomes das variáveis.
    """
    faltando = [v for v in VARIAVEIS_BANCO if not (env.get(v) or "").strip()]
    if faltando:
        raise ErroConfiguracao("faltam no .env: " + ", ".join(faltando))
    try:
        porta = int(env["PORTA_BANCO"])
    except ValueError:
        raise ErroConfiguracao("PORTA_BANCO deve ser um número inteiro") from None
    return {
        "host": env["IP_BANCO"],
        "porta": porta,
        "banco": env["NOME_BANCO"],
        "usuario": env["USER_BANCO"],
        "senha": env["SENHA_BANCO"],
    }


def montar_url(config: dict) -> URL:
    """Monta a URL do SQLAlchemy (mysql+pymysql, charset utf8mb4) a partir de `ler_config_banco`."""
    return URL.create(
        "mysql+pymysql",
        username=config["usuario"],
        password=config["senha"],
        host=config["host"],
        port=config["porta"],
        database=config["banco"],
        query={"charset": "utf8mb4"},
    )


def criar_engine() -> Engine:
    """Cria o engine do MySQL em modo somente leitura.

    Cada conexão nova executa `SET SESSION TRANSACTION READ ONLY`. Se esse comando
    falhar, a conexão falha: não há tratamento que engula o erro.
    """
    load_dotenv(RAIZ / ".env", override=False)
    cfg = ler_config_banco(os.environ)
    engine = create_engine(
        montar_url(cfg),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10, "read_timeout": 600},
    )

    @event.listens_for(engine, "connect")
    def _sessao_somente_leitura(dbapi_conexao, _registro):
        cursor = dbapi_conexao.cursor()
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.close()

    return engine


_RE_BLOCO = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_COMENTARIO_DUPLO = re.compile(r"--[^\n]*")
_RE_COMENTARIO_HASH = re.compile(r"#[^\n]*")
_RE_PRIMEIRA_PALAVRA = re.compile(r"^([A-Za-z]+)")
_PRIMEIRAS_PERMITIDAS = {"SELECT", "SHOW", "WITH"}
_RE_PROIBIDAS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|RENAME|GRANT|REVOKE|CALL|"
    r"LOAD|HANDLER|LOCK|UNLOCK|OUTFILE|DUMPFILE)\b",
    re.IGNORECASE,
)


def validar_sql_leitura(sql: str) -> str:
    """Confere que `sql` é uma consulta de leitura e devolve o SQL limpo.

    Recusa com `ErroSomenteLeitura` qualquer texto que não seja uma única consulta
    SELECT/SHOW/WITH sem palavras de escrita. A trava é conservadora de propósito.
    """
    limpo = _RE_BLOCO.sub(" ", sql)
    limpo = _RE_COMENTARIO_DUPLO.sub(" ", limpo)
    limpo = _RE_COMENTARIO_HASH.sub(" ", limpo)
    limpo = limpo.strip()
    if not limpo:
        raise ErroSomenteLeitura("consulta vazia")
    if limpo.endswith(";"):
        limpo = limpo[:-1].strip()
    if ";" in limpo:
        raise ErroSomenteLeitura("mais de um comando na consulta")
    casamento = _RE_PRIMEIRA_PALAVRA.match(limpo)
    primeira = casamento.group(1).upper() if casamento else ""
    if primeira not in _PRIMEIRAS_PERMITIDAS:
        raise ErroSomenteLeitura(f"comando não permitido: {primeira or '(desconhecido)'}")
    proibida = _RE_PROIBIDAS.search(limpo)
    if proibida:
        raise ErroSomenteLeitura(f"palavra de escrita proibida: {proibida.group(1).upper()}")
    return limpo


def verificar_sessao_somente_leitura(ler: Callable[[str], pd.DataFrame]) -> None:
    """Confirma que a sessão do MySQL está em READ ONLY; senão levanta `ErroSomenteLeitura`.

    `ler` é uma função que executa uma consulta e devolve um DataFrame (ex.: `executar_leitura`).
    """
    df = ler("SELECT @@SESSION.transaction_read_only AS ro")
    if df.empty or "ro" not in df.columns or pd.isna(df["ro"].iloc[0]) or int(df["ro"].iloc[0]) != 1:
        raise ErroSomenteLeitura("sessão do MySQL não está em READ ONLY; abortando")


_engine_padrao: Engine | None = None


def _obter_engine_padrao() -> Engine:
    """Cria o engine padrão na primeira necessidade e reutiliza depois."""
    global _engine_padrao
    if _engine_padrao is None:
        _engine_padrao = criar_engine()
    return _engine_padrao


def executar_leitura(
    sql: str, params: dict | None = None, engine: Engine | None = None
) -> pd.DataFrame:
    """Executa uma consulta de leitura validada e devolve um DataFrame.

    A trava `validar_sql_leitura` roda antes de qualquer acesso ao engine.
    """
    limpo = validar_sql_leitura(sql)
    if engine is None:
        engine = _obter_engine_padrao()
    with engine.connect() as con:
        return pd.read_sql_query(text(limpo), con, params=params)
