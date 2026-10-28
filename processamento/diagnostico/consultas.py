"""Seções gerais do diagnóstico do banco da coleta: existência, colunas, resumo, duplicatas,
valores distintos e vazios.

Cada seção recebe `ler(sql) -> DataFrame` e o mapa de `config/fontes.yaml`. Este módulo não
importa SQLAlchemy: monta o SQL com `fontes.citar` (nomes de tabela e coluna já vêm do mapa)
e executa só pela função `ler` recebida. Só SELECT/SHOW/WITH, sem LIKE e sem `%`.
Ausência é NULL, nunca 0.
"""

from __future__ import annotations

from processamento import fontes
from processamento.diagnostico import regras as r
from processamento.diagnostico.esperado import INDICES

TIPOS_NUMERICOS = {"tinyint", "smallint", "mediumint", "int", "bigint", "double", "float", "decimal"}
TIPOS_TEXTO = {"char", "varchar", "text", "mediumtext", "longtext"}

SQL_TABELAS = (
    "SELECT TABLE_NAME AS tabela FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA = DATABASE()"
)
SQL_COLUNAS = (
    "SELECT TABLE_NAME AS tabela, COLUMN_NAME AS coluna, DATA_TYPE AS tipo, "
    "IS_NULLABLE AS nulo, ORDINAL_POSITION AS pos FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION"
)
SQL_CHAVES = (
    "SELECT TABLE_NAME AS tabela, COLUMN_NAME AS coluna, ORDINAL_POSITION AS pos "
    "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() "
    "AND CONSTRAINT_NAME = 'PRIMARY' ORDER BY TABLE_NAME, ORDINAL_POSITION"
)


# ---------------------------------------------------------------------------
# Construtores de SQL (puros: só montam a string)
# ---------------------------------------------------------------------------

def montar_sql_resumo(tabela: str, coluna_data, coluna_entidade: str) -> str:
    """Linhas, período (MIN/MAX da coluna de data) e entidades distintas de uma tabela.

    Sem coluna de data (`coluna_data` None), o período vira NULL.
    """
    entidade = fontes.citar(coluna_entidade)
    if coluna_data is None:
        periodo = "NULL AS inicio, NULL AS fim"
    else:
        data = fontes.citar(coluna_data)
        periodo = f"MIN({data}) AS inicio, MAX({data}) AS fim"
    return (
        f"SELECT COUNT(*) AS linhas, {periodo}, "
        f"COUNT(DISTINCT {entidade}) AS entidades FROM {fontes.citar(tabela)}"
    )


def montar_sql_duplicatas(tabela: str, expressoes: list[str], where: str | None = None) -> str:
    """Grupos repetidos e linhas extras para as expressões de chave (já em SQL).

    `where`, se dado, é um predicado SQL já pronto, inserido antes do GROUP BY.
    """
    filtro = f" WHERE {where}" if where else ""
    return (
        "SELECT COUNT(*) AS grupos, COALESCE(SUM(n - 1), 0) AS linhas_extras "
        f"FROM (SELECT COUNT(*) AS n FROM {fontes.citar(tabela)}{filtro} "
        f"GROUP BY {', '.join(expressoes)} HAVING COUNT(*) > 1) d"
    )


def montar_sql_vazios(tabela: str, colunas: list[tuple[str, str]]) -> str:
    """Contagem de nulos, textos vazios e zeros por coluna, conforme o tipo (nomes reais).

    Tipos numéricos ganham `zeros__`, tipos texto ganham `vazios__`, os demais só `nulos__`.
    """
    partes = ["COUNT(*) AS total"]
    for nome, tipo in colunas:
        col = fontes.citar(nome)
        tipo_min = (tipo or "").lower()
        partes.append(f"SUM({col} IS NULL) AS {fontes.citar('nulos__' + nome)}")
        if tipo_min in TIPOS_TEXTO:
            partes.append(f"SUM({col} = '') AS {fontes.citar('vazios__' + nome)}")
        elif tipo_min in TIPOS_NUMERICOS:
            partes.append(f"SUM({col} = 0) AS {fontes.citar('zeros__' + nome)}")
    return f"SELECT {', '.join(partes)} FROM {fontes.citar(tabela)}"


def montar_sql_ids_texto_vazio(tabela: str, coluna_id: str, coluna: str) -> str:
    """Até 10 ids (distintos, em ordem) das linhas com texto vazio na coluna (nomes reais)."""
    return (f"SELECT DISTINCT {fontes.citar(coluna_id)} AS id FROM {fontes.citar(tabela)} "
            f"WHERE {fontes.citar(coluna)} = '' ORDER BY id LIMIT 10")


def montar_sql_distintos(tabela: str, coluna: str) -> str:
    """Valores distintos de uma coluna, com contagem, comparados em binário (case e acento)."""
    col = fontes.citar(coluna)
    return (
        f"SELECT valor, COUNT(*) AS n FROM (SELECT {col} COLLATE utf8mb4_bin AS valor "
        f"FROM {fontes.citar(tabela)}) d GROUP BY valor ORDER BY n DESC"
    )


# ---------------------------------------------------------------------------
# Auxiliares internos
# ---------------------------------------------------------------------------

def _lista(itens) -> str:
    """Itens separados por vírgula, ou um travessão quando a lista está vazia."""
    return ", ".join(itens) if itens else "—"


def _colunas_da_tabela(df_colunas, nome: str) -> list[tuple[str, str, str]]:
    """Colunas reais de uma tabela, na ordem de posição, como (coluna, tipo, nulo)."""
    sub = df_colunas[df_colunas["tabela"].map(r.texto) == nome].sort_values("pos")
    return [
        (r.texto(c), r.texto(t), r.texto(n))
        for c, t, n in zip(sub["coluna"], sub["tipo"], sub["nulo"])
    ]


def _chave_da_tabela(df_chaves, nome: str) -> list[str]:
    """Colunas da PRIMARY KEY real de uma tabela, na ordem da chave."""
    sub = df_chaves[df_chaves["tabela"].map(r.texto) == nome].sort_values("pos")
    return [r.texto(c) for c in sub["coluna"]]


# ---------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------

def secao_existencia(ler, mapa) -> tuple[dict, set[str]]:
    """Diz quais tabelas do contrato e auxiliares existem no banco.

    Devolve a seção e o conjunto de nomes reais existentes, usado pelas outras seções.
    """
    secao = r.nova_secao("Existência das tabelas")
    existentes = {r.texto(t) for t in ler(SQL_TABELAS)["tabela"]}
    linhas = []
    notas_opcionais = []
    contrato_total = 0
    contrato_existentes = 0

    for _contrato, cfg in mapa["tabelas"].items():
        nome = cfg["nome_real"]
        existe = nome in existentes
        contrato_total += 1
        contrato_existentes += int(existe)
        linhas.append([nome, "contrato", existe])
        if not existe:
            secao["divergencias"].append(r.div("tabela_ausente", nome, "não existe no banco"))

    for _aux, cfg in mapa.get("auxiliares", {}).items():
        nome = cfg["nome_real"]
        existe = nome in existentes
        linhas.append([nome, "auxiliar", existe])
        if existe:
            continue
        if cfg.get("opcional"):
            notas_opcionais.append(
                f"`{nome}` ausente (pendência da coleta, seção 10): "
                "universo = composicao_atual (seção 3.5)"
            )
        else:
            secao["divergencias"].append(r.div("tabela_ausente", nome, "não existe no banco"))

    secao["notas"].append(f"{contrato_existentes} de {contrato_total} tabelas do contrato existem.")
    secao["notas"].extend(notas_opcionais)
    r.adicionar_tabela(secao, "Existência", ["tabela", "grupo", "existe"], linhas)
    return secao, existentes


def secao_colunas_chaves(ler, mapa, existentes):
    """Compara colunas e chave primária de cada tabela existente com o contrato.

    Devolve a seção e o DataFrame de colunas reais (reaproveitado por `secao_vazios`).
    """
    secao = r.nova_secao("Colunas e chaves")
    df_colunas = ler(SQL_COLUNAS)
    df_chaves = ler(SQL_CHAVES)
    resumo = []

    for _contrato, cfg in mapa["tabelas"].items():
        nome = cfg["nome_real"]
        if nome not in existentes:
            continue
        reais = _colunas_da_tabela(df_colunas, nome)
        nomes_reais = [c for c, _, _ in reais]
        chave_real = _chave_da_tabela(df_chaves, nome)
        chave_esperada = [cfg["colunas"][c] for c in cfg["chave"]]
        comp = r.comparar_colunas(
            list(cfg["colunas"].values()), nomes_reais, cfg.get("colunas_ignoradas", [])
        )
        veredito = r.comparar_chave(chave_esperada, chave_real)

        resumo.append([
            nome, len(nomes_reais), _lista(comp["faltando"]), _lista(comp["extras"]),
            _lista(chave_esperada), _lista(chave_real), veredito,
        ])
        r.adicionar_tabela(secao, nome, ["coluna", "tipo", "nulo"], [[c, t, n] for c, t, n in reais])

        for coluna in comp["faltando"]:
            secao["divergencias"].append(
                r.div("coluna_faltando", nome, f"coluna {coluna} do contrato não existe no banco")
            )
        for coluna in comp["extras"]:
            secao["divergencias"].append(
                r.div("coluna_extra", nome, f"coluna {coluna} existe no banco e não está no contrato")
            )
        if veredito != "igual":
            secao["divergencias"].append(
                r.div("chave", nome, f"esperada ({_lista(chave_esperada)}), "
                                     f"real ({_lista(chave_real)}): {veredito}")
            )

    for _aux, cfg in mapa.get("auxiliares", {}).items():
        nome = cfg["nome_real"]
        if nome not in existentes:
            continue
        nomes_reais = [c for c, _, _ in _colunas_da_tabela(df_colunas, nome)]
        comp = r.comparar_colunas(list(cfg["colunas"].values()), nomes_reais)
        for coluna in comp["faltando"]:
            secao["divergencias"].append(
                r.div("coluna_faltando", nome, f"coluna {coluna} do contrato não existe no banco")
            )

    r.adicionar_tabela(
        secao, "Resumo por tabela",
        ["tabela", "n_colunas", "faltando", "extras", "chave_esperada", "chave_real", "veredito_chave"],
        resumo,
    )
    return secao, df_colunas


def secao_resumo(ler, mapa, existentes):
    """Linhas, período e entidades de cada tabela do contrato, mais contagem de índices."""
    secao = r.nova_secao("Resumo das tabelas")
    linhas = []

    for contrato, cfg in mapa["tabelas"].items():
        nome = cfg["nome_real"]
        if nome not in existentes:
            continue
        coluna_data = cfg["colunas"][cfg["coluna_data"]] if cfg.get("coluna_data") else None
        coluna_entidade = cfg["colunas"][cfg["coluna_entidade"]]
        row = ler(montar_sql_resumo(nome, coluna_data, coluna_entidade)).iloc[0]
        linhas.append([
            nome, r.inteiro(row["linhas"]), row["inicio"], row["fim"],
            r.inteiro(row["entidades"]), coluna_entidade,
        ])
        if contrato == "noticias":
            sql_artigos = (
                f"SELECT COUNT(DISTINCT {fontes.citar(cfg['colunas']['id'])}) AS artigos "
                f"FROM {fontes.citar(nome)}"
            )
            artigos = r.inteiro(ler(sql_artigos).iloc[0]["artigos"])
            secao["notas"].append(
                f"{r.inteiro(row['linhas'])} linhas = {artigos} artigos; "
                "uma linha por par artigo×ticker"
            )

    r.adicionar_tabela(
        secao, "Período e entidades",
        ["tabela", "linhas", "inicio", "fim", "entidades", "coluna_entidade"],
        linhas,
    )

    cfg_indices = mapa["tabelas"].get("indices")
    if cfg_indices and cfg_indices["nome_real"] in existentes:
        nome = cfg_indices["nome_real"]
        col_indice = fontes.citar(cfg_indices["colunas"]["indice"])
        col_data = fontes.citar(cfg_indices["colunas"]["data"])
        sql = (
            f"SELECT {col_indice} AS indice, COUNT(*) AS n, MIN({col_data}) AS inicio, "
            f"MAX({col_data}) AS fim FROM {fontes.citar(nome)} GROUP BY {col_indice}"
        )
        df_indices = ler(sql)
        presentes = {r.texto(i) for i in df_indices["indice"]}
        r.adicionar_tabela(
            secao, "Índices",
            ["indice", "n", "inicio", "fim"],
            [
                [r.texto(row["indice"]), r.inteiro(row["n"]), row["inicio"], row["fim"]]
                for _, row in df_indices.iterrows()
            ],
        )
        for indice in sorted(INDICES - presentes):
            secao["divergencias"].append(r.div("indice_ausente", "v1-indices", indice))

    return secao


def secao_duplicatas(ler, mapa, existentes):
    """Grupos e linhas extras repetidas pela chave de cada tabela, mais repetições de notícias."""
    secao = r.nova_secao("Duplicatas")
    linhas_chave = []

    for _contrato, cfg in mapa["tabelas"].items():
        nome = cfg["nome_real"]
        if nome not in existentes:
            continue
        expressoes = [fontes.citar(cfg["colunas"][c]) for c in cfg["chave"]]
        row = ler(montar_sql_duplicatas(nome, expressoes)).iloc[0]
        grupos = r.inteiro(row["grupos"])
        extras = r.inteiro(row["linhas_extras"])
        linhas_chave.append([nome, _lista([cfg["colunas"][c] for c in cfg["chave"]]), grupos, extras])
        if grupos > 0:
            secao["divergencias"].append(
                r.div("duplicata_chave", nome, f"{grupos} grupos, {extras} linhas extras")
            )

    r.adicionar_tabela(
        secao, "Chave primária", ["tabela", "chave", "grupos", "linhas_extras"], linhas_chave
    )

    cfg_noticias = mapa["tabelas"].get("noticias")
    if cfg_noticias and cfg_noticias["nome_real"] in existentes:
        nome = cfg_noticias["nome_real"]
        col = {c: fontes.citar(cfg_noticias["colunas"][c]) for c in ("ticker", "data_publicacao", "titulo", "link")}
        verificacoes = [
            (
                "mesma matéria (ticker, data, título)",
                montar_sql_duplicatas(nome, [col["ticker"], col["data_publicacao"], f"MD5({col['titulo']})"]),
            ),
            (
                "mesmo link (ticker, link)",
                montar_sql_duplicatas(
                    nome, [col["ticker"], f"MD5({col['link']})"],
                    where=f"{col['link']} IS NOT NULL",
                ),
            ),
        ]
        linhas_info = []
        for descricao, sql in verificacoes:
            row = ler(sql).iloc[0]
            linhas_info.append([descricao, r.inteiro(row["grupos"]), r.inteiro(row["linhas_extras"])])
        r.adicionar_tabela(
            secao, "Repetições de notícias (informativo)",
            ["verificação", "grupos", "linhas_extras"], linhas_info,
        )

    return secao


def secao_distintos(ler, mapa, existentes):
    """Valores distintos das colunas com lista permitida; valor fora da lista vira divergência.

    Origem em `origens_ignoradas` (aceita, mas descartada pela leitura) vira nota com a contagem.
    """
    secao = r.nova_secao("Valores distintos")
    linhas = []

    for _contrato, cfg in mapa["tabelas"].items():
        nome = cfg["nome_real"]
        if nome not in existentes:
            continue
        for coluna, permitidos in cfg.get("valores_permitidos", {}).items():
            real = cfg["colunas"][coluna]
            valores = []
            for _, row in ler(montar_sql_distintos(nome, real)).iterrows():
                valor = r.texto(row["valor"])
                n = r.inteiro(row["n"])
                if valor is None:
                    rotulo, permitido = "NULL", "—"
                else:
                    rotulo, permitido = valor, ("sim" if valor in permitidos else "não")
                linhas.append([nome, real, rotulo, n, permitido])
                valores.append(valor)
                if coluna == "origem" and valor in (cfg.get("origens_ignoradas") or []):
                    secao["notas"].append(
                        f"{nome}.{real} = {valor}: {n} linhas ignoradas pela leitura "
                        "(origens_ignoradas; fonte nova, aguardando definição)"
                    )
            fora = r.valores_fora_da_lista(valores, permitidos)
            if fora:
                secao["divergencias"].append(
                    r.div("valor_desconhecido", nome, f"{real}: {', '.join(fora)}")
                )

    r.adicionar_tabela(secao, "Valores por coluna", ["tabela", "coluna", "valor", "n", "permitido"], linhas)
    return secao


def secao_vazios(ler, mapa, existentes, df_colunas):
    """Nulos, textos vazios e zeros por coluna, com as divergências da especificação."""
    secao = r.nova_secao("Vazios e zeros")
    linhas = []

    for _contrato, cfg in mapa["tabelas"].items():
        nome = cfg["nome_real"]
        if nome not in existentes:
            continue
        reais = _colunas_da_tabela(df_colunas, nome)
        row = ler(montar_sql_vazios(nome, [(c, t) for c, t, _ in reais])).iloc[0]
        total = r.inteiro(row["total"])
        nome_contrato_de = {real: contrato_col for contrato_col, real in cfg["colunas"].items()}
        conhecidas = set(cfg.get("colunas_vazias_conhecidas", []))
        so_nota_preench = set(cfg.get("colunas_nota_preenchimento", []))
        so_nota_texto = set(cfg.get("textos_vazios_nota", []))
        proibidas_zero = set(cfg.get("zero_proibido", []))

        for coluna, _tipo, _nulo in reais:
            nulos = r.inteiro(row.get(f"nulos__{coluna}"))
            textos_vazios = r.inteiro(row.get(f"vazios__{coluna}"))
            zeros = r.inteiro(row.get(f"zeros__{coluna}"))
            resumo = r.resumo_vazios(total, nulos)
            contrato_col = nome_contrato_de.get(coluna)

            for detalhe in r.divergencias_coluna(
                nome, coluna, resumo["situacao"], textos_vazios, zeros,
                contrato_col in conhecidas, contrato_col in proibidas_zero,
                so_nota_preenchimento=contrato_col in so_nota_preench,
                so_nota_texto_vazio=contrato_col in so_nota_texto,
            ):
                secao["divergencias"].append(r.div("coluna_vazia", nome, detalhe))

            if contrato_col in so_nota_preench and resumo["situacao"] != "tabela_vazia":
                secao["notas"].append(r.nota_preenchimento(nome, coluna, total, nulos))
            if contrato_col in so_nota_texto and textos_vazios > 0:
                coluna_id = cfg["colunas"][cfg["chave"][0]]
                df_ids = ler(montar_sql_ids_texto_vazio(nome, coluna_id, coluna))
                ids = [r.texto(v) for v in df_ids["id"]]
                secao["notas"].append(r.nota_texto_vazio(nome, coluna, textos_vazios, ids))

            if nulos or textos_vazios or zeros or contrato_col in conhecidas or contrato_col in so_nota_preench:
                linhas.append([
                    nome, coluna, total, nulos, resumo["pct_nulo"], resumo["situacao"],
                    textos_vazios, zeros,
                ])

    r.adicionar_tabela(
        secao, "Colunas com nulos, textos vazios ou zeros",
        ["tabela", "coluna", "total", "nulos", "pct_nulo", "situacao", "textos_vazios", "zeros"],
        linhas,
    )
    secao["notas"].append("demais colunas 100% preenchidas")
    return secao
