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
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from processamento.tickers import aplicar_mudancas, parse_other_codes

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


# ---------------------------------------------------------------------------
# Camada de leitura (Etapa 2, fase 2): lê as tabelas da coleta, confere o contrato
# (`CONTRATO` + `valores_permitidos` do mapa) e devolve DataFrames prontos.
# Só lê: nada aqui grava no banco. Todo `ler` injetado é `ler(sql, params=None)`.
# ---------------------------------------------------------------------------

SP = ZoneInfo("America/Sao_Paulo")
PACIFICO = ZoneInfo("America/Los_Angeles")


class ErroLeitura(Exception):
    """Dado do banco fora do contrato; mensagem legível."""


CONTRATO = {
    "precos": {
        "datas": ["data"],
        "numeros": ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado", "volume"],
        "corte": "data",
    },
    "cadastro": {"datas": [], "numeros": ["unit_qtd_on", "unit_qtd_pn"], "corte": None},
    "mudancas_ticker": {"datas": ["data_mudanca"], "numeros": [], "corte": None},
    "balancos": {
        "datas": ["data_inicio_periodo", "data_fim_periodo", "data_entrega"],
        "numeros": [
            "receita_liquida",
            "lucro_bruto",
            "lucro_liquido",
            "patrimonio_liquido",
            "ebit",
            "depreciacao_amortizacao",
            "emprestimos_curto_prazo",
            "emprestimos_longo_prazo",
            "caixa",
            "aplicacoes_financeiras",
        ],
        "corte": "data_entrega",
    },
    "acoes_emitidas": {"datas": ["data_referencia"], "numeros": ["qtd_on", "qtd_pn"], "corte": None},
    "proventos": {
        "datas": ["data_com", "data_pagamento"],
        "numeros": ["valor_por_acao"],
        "corte": "data_com",
    },
    "indices": {"datas": ["data"], "numeros": ["valor"], "corte": "data"},
    "noticias": {
        "datas": ["data_publicacao"],
        "numeros": ["prob_positivo", "prob_neutro", "prob_negativo", "qualidade"],
        "iso_fuso": ["data_hora_publicacao", "data_hora_coleta"],
        "corte": None,
    },
}
TABELAS_COM_TICKER = {"precos", "proventos", "noticias"}
_RE_ISO_FUSO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")
_COLUNAS_TICKER = ("ticker", "ticker_antigo", "ticker_novo")


def _ler_padrao(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Leitura padrão, pela conexão somente leitura da coleta (só sem `ler` injetado)."""
    return executar_leitura(sql, params)


def _data_texto(d) -> str:
    """Data como texto 'AAAA-MM-DD', para usar como parâmetro de consulta."""
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def _vazio_como_nulo(serie: pd.Series) -> pd.Series:
    """Texto só com espaços vira nulo: ausência é NaN, nunca texto vazio."""
    return serie.map(lambda v: None if isinstance(v, str) and not v.strip() else v)


def tabela_existe(nome_real: str, ler: Callable[..., pd.DataFrame] | None = None) -> bool:
    """Diz se a tabela existe no schema atual do banco."""
    if ler is None:
        ler = _ler_padrao
    df = ler(
        "SELECT COUNT(*) AS n FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :nome",
        {"nome": nome_real},
    )
    return int(df["n"].iloc[0]) > 0


def _conferir_tabela(tabela: str, ler: Callable[..., pd.DataFrame]) -> list[str]:
    """Passo 2: confere se a tabela existe e tem as colunas do mapa. Devolve as colunas lógicas."""
    ent = _entrada(tabela)
    nome = ent["nome_real"]
    ignoradas = set(ent.get("colunas_ignoradas", []))
    colunas = [c for c in ent["colunas"] if c not in ignoradas]
    try:
        vazia = ler(f"SELECT * FROM {tabela_sql(tabela)} LIMIT 0")
    except (SQLAlchemyError, pd.errors.DatabaseError) as erro:
        # pandas embrulha o erro do SQLAlchemy em pandas.errors.DatabaseError
        raise ErroLeitura(f"falha ao ler a tabela {nome} (não existe ou sem acesso)") from erro
    presentes = set(vazia.columns)
    for c in colunas:
        if ent["colunas"][c] not in presentes:
            raise ErroLeitura(f"tabela {nome} sem a coluna {ent['colunas'][c]}")
    return colunas


def _selecionar(
    tabela: str,
    colunas: list[str],
    condicoes: list[str],
    params: dict | None,
    ler: Callable[..., pd.DataFrame],
) -> pd.DataFrame:
    """Passo 3: SELECT só das colunas pedidas, com alias lógico e filtros já montados."""
    lista = ", ".join(f"{coluna_sql(tabela, c)} AS {citar(c)}" for c in colunas)
    sql = f"SELECT {lista} FROM {tabela_sql(tabela)}"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    return ler(sql, params)


def _tratar(
    tabela: str, df: pd.DataFrame, ler: Callable[..., pd.DataFrame], unir_mudancas: bool
) -> pd.DataFrame:
    """Passos 4 a 9: tipos, normalização, valores permitidos, mudanças de ticker, chave e ordem."""
    ent = _entrada(tabela)
    nome = ent["nome_real"]
    ct = CONTRATO[tabela]
    for c in list(df.columns):
        df[c] = _vazio_como_nulo(df[c])
    for c in ct.get("iso_fuso", []):
        df[c] = para_sao_paulo_iso(df[c], f"{nome}.{c}")
    for c in ct["datas"]:
        original = df[c]
        datas = pd.to_datetime(original, errors="coerce", format="ISO8601").dt.normalize()
        invalido = original.notna() & datas.isna()
        if invalido.any():
            ex = original[invalido].iloc[0]
            raise ErroLeitura(f"{nome}.{c}: {int(invalido.sum())} datas inválidas, ex.: {ex!r}")
        df[c] = datas
    for c in ct["numeros"]:
        original = df[c]
        numeros = pd.to_numeric(original, errors="coerce")
        invalido = original.notna() & numeros.isna()
        if invalido.any():
            ex = original[invalido].iloc[0]
            raise ErroLeitura(f"{nome}.{c}: {int(invalido.sum())} valores não numéricos, ex.: {ex!r}")
        df[c] = numeros
    for c in _COLUNAS_TICKER:
        if c in df.columns:
            df[c] = normalizar_ticker(df[c])
    if "cnpj" in df.columns:
        df["cnpj"] = normalizar_cnpj(df["cnpj"], f"{nome}.cnpj")
    for c, permitidos in ent.get("valores_permitidos", {}).items():
        fora = [v for v in df[c] if pd.notna(v) and v not in permitidos]
        if fora:
            raise ErroLeitura(f"{nome}.{c}: valor fora do contrato: {fora[0]!r}")
    if unir_mudancas and tabela in TABELAS_COM_TICKER:
        mudancas = mudancas_como_dict(ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False))
        df = unir_historicos(df, mudancas, ent["chave"])
    chave = ent["chave"]
    repetida = df.duplicated(subset=chave, keep=False)
    if repetida.any():
        ex = df.loc[repetida, chave].iloc[0]
        raise ErroLeitura(
            f"{nome}: {int(repetida.sum())} linhas com chave repetida "
            f"({', '.join(chave)}), ex.: {' / '.join(str(v) for v in ex)}"
        )
    return df.sort_values(chave).reset_index(drop=True)


def ler_tabela(
    tabela: str,
    *,
    desde: date | None = None,
    ate: date | None = None,
    ler: Callable[..., pd.DataFrame] | None = None,
    unir_mudancas: bool = True,
) -> pd.DataFrame:
    """Lê uma tabela do contrato, confere o formato e devolve o DataFrame tratado.

    `desde` e `ate` filtram pela coluna de corte do contrato (inclusivos). Com
    `unir_mudancas`, os tickers antigos viram o código atual (só tabelas com ticker).
    """
    if tabela == "noticias":
        raise ValueError("use ler_noticias")
    if tabela not in CONTRATO:
        raise ValueError(f"tabela {tabela} não tem contrato de leitura")
    if ler is None:
        ler = _ler_padrao
    colunas = _conferir_tabela(tabela, ler)
    condicoes: list[str] = []
    params: dict[str, str] = {}
    if desde is not None or ate is not None:
        corte = CONTRATO[tabela]["corte"]
        if corte is None:
            raise ValueError(f"tabela {tabela} não tem coluna de corte para filtrar por período")
        if desde is not None:
            condicoes.append(f"{coluna_sql(tabela, corte)} >= :desde")
            params["desde"] = _data_texto(desde)
        if ate is not None:
            condicoes.append(f"{coluna_sql(tabela, corte)} <= :ate")
            params["ate"] = _data_texto(ate)
    df = _selecionar(tabela, colunas, condicoes, params or None, ler)
    return _tratar(tabela, df, ler, unir_mudancas)


def ler_noticias(
    *,
    desde: date | None = None,
    ate: pd.Timestamp | None = None,
    ler: Callable[..., pd.DataFrame] | None = None,
    unir_mudancas: bool = True,
) -> pd.DataFrame:
    """Lê `v1-noticias` na janela (seção 7.2) e devolve também `momento_ref` (horário de São Paulo).

    `momento_ref` é `data_hora_publicacao`; sem ela, 23:59:59 do dia de `data_publicacao`.
    Notícias "só data" (meia-noite do Pacífico) passam por `aplicar_regra_so_data` antes de
    qualquer filtro; `precisao_hora` diz de onde veio cada horário.
    O filtro grosso vai ao SQL pela data; o filtro fino é feito em `momento_ref`.
    `ate` precisa ter fuso horário.
    """
    tabela = "noticias"
    if ate is not None and pd.Timestamp(ate).tzinfo is None:
        raise ValueError("ate precisa ter fuso horário")
    if ler is None:
        ler = _ler_padrao
    ate_sp = pd.Timestamp(ate).tz_convert(SP) if ate is not None else None
    colunas = _conferir_tabela(tabela, ler)
    coluna_data = coluna_sql(tabela, "data_publicacao")
    condicoes: list[str] = []
    params: dict[str, str] = {}
    if ate_sp is not None:
        condicoes.append(f"{coluna_data} <= :ate_data")
        params["ate_data"] = ate_sp.strftime("%Y-%m-%d")
    if desde is not None:
        condicoes.append(f"{coluna_data} >= :desde_menos_1")
        params["desde_menos_1"] = _data_texto(pd.Timestamp(desde) - pd.Timedelta(days=1))
    df = _selecionar(tabela, colunas, condicoes, params or None, ler)
    df = _tratar(tabela, df, ler, unir_mudancas)
    df = aplicar_regra_so_data(df)
    if ate_sp is not None:
        df = df[df["momento_ref"] <= ate_sp]
    if desde is not None:
        df = df[df["momento_ref"] >= pd.Timestamp(desde).tz_localize(SP)]
    return df.sort_values(["momento_ref", "id", "ticker"]).reset_index(drop=True)


def meia_noite_pacifico(instantes: pd.Series) -> pd.Series:
    """True onde o instante, em Los Angeles, é exatamente 00:00:00.

    O Google News chega como 04:00 (PDT) ou 05:00 (PST) de São Paulo quando a fonte deu só a
    data: isso é meia-noite do Pacífico. A hora não é real. NaT vira False.
    """
    la = instantes.dt.tz_convert(PACIFICO)
    zerado = (la.dt.hour == 0) & (la.dt.minute == 0) & (la.dt.second == 0) & (la.dt.microsecond == 0)
    return zerado.fillna(False).astype(bool)


def _fim_do_dia(datas: pd.Series) -> pd.Series:
    """23:59:59 de cada data (horário de São Paulo)."""
    return datas.dt.tz_localize(SP) + pd.Timedelta(hours=23, minutes=59, seconds=59)


def aplicar_regra_so_data(noticias: pd.DataFrame) -> pd.DataFrame:
    """Marca `precisao_hora` e trata as notícias "só data" (ver `meia_noite_pacifico`).

    "hora": tem `data_hora_publicacao` real. "sem_hora": nunca teve (ex.: cvm_ipe).
    "meia_noite_pacifico": vira só data. `data_publicacao` passa a ser a data em Los Angeles,
    `data_hora_publicacao` fica nula e `momento_ref` é 23:59:59 dessa data (a mesma regra das
    sem horário). Idempotente; as linhas "hora" ficam intactas.
    """
    df = noticias.copy()
    tem_hora = df["data_hora_publicacao"].notna()
    meia = meia_noite_pacifico(df["data_hora_publicacao"])
    if "precisao_hora" in df.columns:
        meia = meia | df["precisao_hora"].eq("meia_noite_pacifico")
    datas_la = df["data_hora_publicacao"].dt.tz_convert(PACIFICO).dt.tz_localize(None).dt.normalize()
    data_pub = df["data_publicacao"].where(~(meia & tem_hora), datas_la)
    fim = _fim_do_dia(data_pub)
    if "momento_ref" in df.columns:
        momento = df["momento_ref"].where(~meia, fim)
    else:
        momento = df["data_hora_publicacao"].where(~meia, fim).fillna(fim)
    precisao = pd.Series("sem_hora", index=df.index).where(~tem_hora, "hora").where(~meia, "meia_noite_pacifico")
    return df.assign(
        data_publicacao=data_pub,
        data_hora_publicacao=df["data_hora_publicacao"].where(~meia),
        momento_ref=momento,
        precisao_hora=precisao,
    )


def ler_raw_b3_cadastro(ler: Callable[..., pd.DataFrame] | None = None) -> pd.DataFrame:
    """Lê `v1-raw_b3_cadastro`: CNPJ normalizado e `other_codes` como lista de tickers."""
    if ler is None:
        ler = _ler_padrao
    _conferir_tabela("raw_b3_cadastro", ler)
    df = _selecionar("raw_b3_cadastro", ["cnpj", "issuing_company", "other_codes"], [], None, ler)
    df["cnpj"] = normalizar_cnpj(_vazio_como_nulo(df["cnpj"]), "v1-raw_b3_cadastro.cnpj")
    try:
        df["other_codes"] = df["other_codes"].map(parse_other_codes)
    except ValueError as erro:
        raise ErroLeitura(f"v1-raw_b3_cadastro.other_codes: {erro}") from erro
    return df


def ler_raw_articles(ler: Callable[..., pd.DataFrame] | None = None) -> pd.DataFrame:
    """Lê `raw_articles` só para conferir os horários (E1): só leitura, nunca grava.

    `id_noticia` é a ligação com `v1-noticias.id` ("n" + id com zeros à esquerda, 6 dígitos ou
    mais). `publicado_em_sp` vem do UTC; `meia_noite_pacifico` diz se é a hora da fonte "só data".
    """
    if ler is None:
        ler = _ler_padrao
    colunas = _conferir_tabela("raw_articles", ler)
    df = _selecionar("raw_articles", colunas, [], None, ler)
    for c in ("lang", "published_precision", "origem"):
        df[c] = _vazio_como_nulo(df[c])
    ids = pd.to_numeric(df["id"], errors="coerce")
    if ids.isna().any():
        raise ErroLeitura(f"raw_articles.id: {int(ids.isna().sum())} valores nulos ou não numéricos")
    try:
        publicado = para_sao_paulo_de_utc(df["published_at"])
    except (ValueError, TypeError) as erro:
        raise ErroLeitura(f"raw_articles.published_at: {erro}") from erro
    return pd.DataFrame(
        {
            "id": ids.astype("int64"),
            "id_noticia": ids.astype("int64").map(lambda v: f"n{v:06d}"),
            "lang": df["lang"],
            "published_precision": df["published_precision"],
            "origem": df["origem"],
            "publicado_em_sp": publicado,
            "meia_noite_pacifico": meia_noite_pacifico(publicado),
        }
    )


def para_sao_paulo_iso(serie: pd.Series, rotulo: str) -> pd.Series:
    """Converte texto ISO com fuso (ex.: '2025-10-17T17:00:00-03:00') para horário de São Paulo.

    Texto sem fuso ou fora do formato levanta ErroLeitura. Nulo continua nulo (NaT).
    """
    fora = [v for v in serie if pd.notna(v) and not (isinstance(v, str) and _RE_ISO_FUSO.fullmatch(v))]
    if fora:
        raise ErroLeitura(f"{rotulo}: {len(fora)} valores fora do ISO com fuso, ex.: {fora[0]!r}")
    return pd.to_datetime(serie, format="ISO8601", utc=True).dt.tz_convert(SP)


def para_sao_paulo_de_utc(serie: pd.Series) -> pd.Series:
    """Converte horário UTC sem fuso (ex.: `raw_articles.published_at`) para São Paulo."""
    return pd.to_datetime(serie, format="ISO8601").dt.tz_localize("UTC").dt.tz_convert(SP)


def normalizar_ticker(serie: pd.Series) -> pd.Series:
    """Tira espaços, põe em maiúsculas e tira o sufixo '.SA' (ex.: ' petr4.sa ' -> 'PETR4')."""

    def _um(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        t = str(v).strip().upper()
        if t.endswith(".SA"):
            t = t[:-3]
        return t or None

    return serie.map(_um)


def normalizar_cnpj(serie: pd.Series, rotulo: str) -> pd.Series:
    """Deixa só os dígitos do CNPJ; comprimento diferente de 14 levanta ErroLeitura. Nulo segue nulo."""

    def _um(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        if isinstance(v, str) and not v.strip():
            return None
        digitos = re.sub(r"\D", "", str(v))
        if len(digitos) != 14:
            raise ErroLeitura(f"{rotulo}: CNPJ com {len(digitos)} dígitos (esperado 14): {v!r}")
        return digitos

    return serie.map(_um)


def mudancas_como_dict(mudancas: pd.DataFrame) -> dict[str, str]:
    """Monta {ticker antigo: ticker novo} a partir de `v1-mudancas_ticker`, ignorando linhas sem destino."""
    antigos = normalizar_ticker(mudancas["ticker_antigo"])
    novos = normalizar_ticker(mudancas["ticker_novo"])
    return {
        a: n
        for a, n in zip(antigos, novos, strict=True)
        if isinstance(a, str) and isinstance(n, str) and a != n
    }


def unir_historicos(df: pd.DataFrame, mudancas: dict[str, str], chave: list[str]) -> pd.DataFrame:
    """Troca o ticker antigo pelo novo (`tickers.aplicar_mudancas`) e junta o histórico.

    Se a linha trocada colidir com uma linha que já tinha o ticker novo na mesma chave,
    fica a que já tinha o ticker novo. Repetições que não vêm de troca continuam no
    DataFrame, para `ler_tabela` acusar a chave repetida.
    """
    original = df["ticker"]
    novos = [aplicar_mudancas(t, mudancas) if isinstance(t, str) else t for t in original]
    trocada = [isinstance(t, str) and n != t for t, n in zip(original, novos, strict=True)]
    resultado = df.copy()
    resultado["ticker"] = novos
    chaves = [tuple(linha) for linha in resultado[chave].itertuples(index=False, name=None)]
    fixas = {k for k, t in zip(chaves, trocada, strict=True) if not t}
    manter = [not (t and k in fixas) for k, t in zip(chaves, trocada, strict=True)]
    # .loc: com df vazio, resultado[[]] seleciona colunas (nenhuma) e perde a chave.
    return resultado.loc[manter].sort_values(chave).reset_index(drop=True)


def intervalos_de_fotos(fotos: pd.DataFrame) -> pd.DataFrame:
    """Transforma fotos de carteira (uma linha por carteira e ticker) em intervalos de permanência.

    Entra na primeira carteira em que o ticker aparece. Sai na primeira em que some, com
    data_fim = dia anterior a essa carteira. Se ainda está na última carteira, data_fim é
    NaT (sem limite). Reentrada abre um novo intervalo.
    """
    presentes: dict[pd.Timestamp, set[str]] = {}
    for d, t in zip(pd.to_datetime(fotos["data_carteira"]).dt.normalize(), fotos["ticker"], strict=True):
        if isinstance(t, str):
            presentes.setdefault(d, set()).add(t)
    carteiras = sorted(presentes)
    tickers = sorted({t for s in presentes.values() for t in s})
    intervalos = []
    for ticker in tickers:
        inicio = None
        for d in carteiras:
            if ticker in presentes[d]:
                if inicio is None:
                    inicio = d
            elif inicio is not None:
                intervalos.append((ticker, inicio, d - pd.Timedelta(days=1)))
                inicio = None
        if inicio is not None:
            intervalos.append((ticker, inicio, pd.NaT))
    resultado = pd.DataFrame(intervalos, columns=["ticker", "data_inicio", "data_fim"])
    return resultado.sort_values(["ticker", "data_inicio"]).reset_index(drop=True)


def intervalos_de_cadastro(cadastro: pd.DataFrame, col_entrada: str, col_saida: str) -> pd.DataFrame:
    """Um intervalo por linha: data_inicio = entrada, data_fim = saída (ambas inclusivas).

    NaT em entrada ou saída quer dizer sem limite. Colunas ausentes levantam ErroLeitura.
    """
    faltando = [c for c in (col_entrada, col_saida) if c not in cadastro.columns]
    if faltando:
        raise ErroLeitura("cadastro sem as colunas de período: " + ", ".join(faltando))
    inicio = pd.to_datetime(cadastro[col_entrada]).dt.normalize()
    fim = pd.to_datetime(cadastro[col_saida]).dt.normalize()
    resultado = pd.DataFrame(
        {
            "ticker": cadastro["ticker"].to_numpy(),
            "data_inicio": inicio.to_numpy(),
            "data_fim": fim.to_numpy(),
        }
    )
    return resultado.sort_values(["ticker", "data_inicio"]).reset_index(drop=True)


def _mudar_ticker(t, mudancas: dict[str, str]) -> str | None:
    """Código atual de um ticker (ou None, se não há ticker)."""
    return aplicar_mudancas(t, mudancas) if isinstance(t, str) else None


def ler_composicao(
    ler: Callable[..., pd.DataFrame] | None = None, existe: bool | None = None
) -> pd.DataFrame | None:
    """Intervalos de permanência no IBOV de `v1-composicao_ibov`.

    Colunas: ticker, data_inicio, data_fim (NaT = ainda vigente), participacao (float) e fonte.
    Devolve None só se a tabela não existe na coleta; tabela existente e vazia devolve um
    DataFrame vazio com essas mesmas colunas. O formato (`intervalos`, `fotos` ou `cadastro`)
    vem do `fontes.yaml`. Os tickers passam pelas mudanças de código.
    """
    if ler is None:
        ler = _ler_padrao
    ent = _entrada("composicao_ibov")
    formato = ent.get("formato")
    if formato not in ("intervalos", "fotos", "cadastro"):
        raise ValueError(f"formato de composicao_ibov desconhecido: {formato!r}")
    if formato != "cadastro":
        if existe is None:
            existe = tabela_existe(ent["nome_real"], ler)
        if not existe:
            return None
    mudancas = mudancas_como_dict(ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False))
    if formato == "cadastro":
        cadastro = ler_tabela("cadastro", ler=ler)
        intervalos = intervalos_de_cadastro(cadastro, "data_inicio", "data_fim")
        intervalos["ticker"] = intervalos["ticker"].map(lambda t: _mudar_ticker(t, mudancas))
    elif formato == "fotos":
        bruto = _selecionar("composicao_ibov", ["data_carteira", "ticker"], [], None, ler)
        bruto["ticker"] = normalizar_ticker(bruto["ticker"]).map(lambda t: _mudar_ticker(t, mudancas))
        intervalos = intervalos_de_fotos(bruto)
    else:
        _conferir_tabela("composicao_ibov", ler)  # coluna faltando vira ErroLeitura legível
        colunas = ["ticker", "data_inicio", "data_fim", "participacao", "fonte"]
        intervalos = _selecionar("composicao_ibov", colunas, [], None, ler)
        intervalos["ticker"] = normalizar_ticker(intervalos["ticker"]).map(
            lambda t: _mudar_ticker(t, mudancas)
        )
        for c in ("data_inicio", "data_fim"):
            intervalos[c] = pd.to_datetime(intervalos[c]).dt.normalize()
        intervalos["participacao"] = pd.to_numeric(intervalos["participacao"]).astype(float)
    return intervalos.sort_values(["ticker", "data_inicio"]).reset_index(drop=True)
