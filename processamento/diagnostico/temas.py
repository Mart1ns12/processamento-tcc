"""Seções do diagnóstico por tema: notícias, preços, balanços, tickers e painel.

Cada função de seção recebe `ler` (função `ler(sql) -> DataFrame`), o `mapa` do
`fontes.yaml` e o conjunto `existentes` (nomes reais das tabelas que existem no banco).
Só este módulo monta o SQL dos temas, sempre com os nomes vindos do mapa, citados com
crases. Nada aqui importa o SQLAlchemy nem abre conexão: quem executa é o `ler`.
Tabela ausente gera uma nota "pulada: tabela ausente" e a seção não consulta.
"""

from __future__ import annotations

import pandas as pd

from processamento import fontes
from processamento.diagnostico.esperado import (
    AMOSTRA_FUSO_POR_ANO,
    ETAPAS_COLETA,
    HORAS_DAILY_UTC,
    IDIOMAS,
    MACROS_PRECOS,
    MODELOS_FINBERT,
    OFFSET_SP,
    SEM_CNPJ_CONHECIDOS,
    SERIES_FORA_CALENDARIO,
    STATUS_ETAPA,
    UNITS,
)
from processamento.diagnostico.regras import (
    adicionar_tabela,
    resumo_proventos_por_ticker,
    buracos_por_ticker,
    classificar_dias_periodo,
    classificar_grupo_iso,
    classificar_id_noticia,
    cnpjs_fora_do_padrao,
    comparar_colunas,
    comparar_com_referencia,
    confere_fuso,
    contar_por_ano,
    dias_uteis_sem_pregao,
    div,
    horas_fora_da_agenda,
    inteiro,
    nova_secao,
    offset_iso,
    pct_com_hora_por_ano,
    resumir_probabilidades,
    texto,
    tickers_fora_do_padrao,
    valores_fora_da_lista,
    veredito_escala,
)
from processamento.exclusoes import Exclusoes, carregar_exclusoes
from processamento.tickers import classificar_classe, codigos_por_cnpj, ligar_a_cnpj, parse_other_codes


# ---------------------------------------------------------------------------
# Construtor puro do formato ISO
# ---------------------------------------------------------------------------

def montar_sql_formato_iso(tabela: str, coluna: str) -> str:
    """SQL que agrupa os valores de uma coluna de data/hora por tamanho e últimos 6 caracteres.

    `tabela` e `coluna` são os nomes REAIS no banco (ex.: 'v1-noticias'); as crases são
    colocadas aqui via `fontes.citar`.
    """
    col = fontes.citar(coluna)
    return (
        f"SELECT CHAR_LENGTH({col}) AS tam, RIGHT({col}, 6) AS fim, COUNT(*) AS n, "
        f"MIN({col}) AS exemplo_min, MAX({col}) AS exemplo_max "
        f"FROM {fontes.citar(tabela)} WHERE {col} IS NOT NULL "
        f"GROUP BY tam, fim ORDER BY n DESC"
    )


# ---------------------------------------------------------------------------
# Auxiliares de mapa, nomes e conversões
# ---------------------------------------------------------------------------

def _entrada(mapa: dict, chave: str) -> dict:
    """Procura a tabela do contrato em `tabelas` e depois em `auxiliares`."""
    for grupo in ("tabelas", "auxiliares"):
        if chave in mapa.get(grupo, {}):
            return mapa[grupo][chave]
    raise ValueError(f"tabela do contrato desconhecida: {chave}")


def _nome(mapa: dict, chave: str) -> str:
    """Nome real da tabela no banco (sem crase)."""
    return _entrada(mapa, chave)["nome_real"]


def _tab(mapa: dict, chave: str) -> str:
    """Nome real da tabela já citado para SQL."""
    return fontes.citar(_nome(mapa, chave))


def _col_real(mapa: dict, chave: str, coluna: str) -> str:
    """Nome real da coluna no banco (sem crase)."""
    colunas = _entrada(mapa, chave).get("colunas", {})
    if coluna not in colunas:
        raise ValueError(f"tabela {chave} sem a coluna {coluna} no mapa")
    return colunas[coluna]


def _col(mapa: dict, chave: str, coluna: str) -> str:
    """Nome real da coluna já citado para SQL."""
    return fontes.citar(_col_real(mapa, chave, coluna))


def _existe(mapa: dict, existentes: set, chave: str) -> bool:
    """Diz se a tabela (contrato ou auxiliar) existe no banco."""
    return _nome(mapa, chave) in existentes


def _pulada(mapa: dict, chave: str) -> str:
    """Texto padrão da nota de seção pulada por tabela ausente."""
    return f"pulada: tabela ausente (`{_nome(mapa, chave)}`)"


def _registros(df: pd.DataFrame, colunas) -> list:
    """Linhas do DataFrame como listas, nas colunas pedidas, na ordem dada."""
    return [list(r) for r in df[list(colunas)].itertuples(index=False, name=None)]


def _valores(ler, tabela: str, coluna: str) -> set:
    """Valores distintos de uma coluna (COLLATE binário), sem None."""
    df = ler(f"SELECT DISTINCT {coluna} COLLATE utf8mb4_bin AS valor FROM {tabela}")
    return {v for v in (texto(x) for x in df["valor"]) if v is not None}


def _data(valor):
    """Converte DATE/datetime/texto do MySQL em datetime.date; None se ausente."""
    ts = pd.to_datetime(valor, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def _ano(valor):
    """Ano como int; None se ausente."""
    return None if pd.isna(valor) else int(valor)


def _lista(valores) -> str:
    """Lista separada por vírgula, ou 'nenhum' quando vazia."""
    itens = list(valores)
    return ", ".join(str(v) for v in itens) if itens else "nenhum"


def _resumo_horas(contagem: dict) -> str:
    """Texto '11h: 30, 14h: 2' a partir de {hora: n}."""
    return ", ".join(f"{h}h: {n}" for h, n in sorted(contagem.items()))


# ---------------------------------------------------------------------------
# Notícias
# ---------------------------------------------------------------------------

def secao_noticias(ler, mapa: dict, existentes: set) -> dict:
    """Seção de notícias: probabilidades, hora, formato ISO, fuso, idioma, FinBERT e id."""
    secao = nova_secao("Notícias (v1-noticias)")
    if not _existe(mapa, existentes, "noticias"):
        secao["notas"].append(_pulada(mapa, "noticias"))
        return secao
    nome = _nome(mapa, "noticias")
    T = _tab(mapa, "noticias")
    c = lambda x: _col(mapa, "noticias", x)
    pp, pn, pg = c("prob_positivo"), c("prob_neutro"), c("prob_negativo")

    # a) probabilidades do FinBERT
    df = ler(
        f"SELECT ({pp} IS NULL) + ({pn} IS NULL) + ({pg} IS NULL) AS n_nulos, "
        f"ROUND({pp} + {pn} + {pg}, 4) AS soma, "
        f"(LEAST({pp}, {pn}, {pg}) < 0 OR GREATEST({pp}, {pn}, {pg}) > 1) AS fora, "
        f"COUNT(*) AS n FROM {T} GROUP BY n_nulos, soma, fora"
    )
    contagem = resumir_probabilidades(df)
    adicionar_tabela(secao, "Probabilidades do FinBERT", ["veredito", "linhas"],
                     [[k, v] for k, v in contagem.items()])
    for veredito in ("parcial", "fora_intervalo", "soma_errada"):
        if contagem[veredito] > 0:
            secao["divergencias"].append(
                div("probabilidades", nome, f"{veredito}: {contagem[veredito]} linhas"))
    for rotulo, col in (("positivo", pp), ("neutro", pn), ("negativo", pg)):
        df_faixa = ler(f"SELECT MIN({col}) AS minimo, MAX({col}) AS maximo FROM {T}")
        adicionar_tabela(secao, f"Faixa de prob_{rotulo}", ["minimo", "maximo"],
                         _registros(df_faixa, ("minimo", "maximo")))

    # b) percentual com hora, por ano e por origem
    df_ano = ler(
        f"SELECT YEAR({c('data_publicacao')}) AS ano, {c('origem')} AS origem, "
        f"COUNT(*) AS total, SUM({c('data_hora_publicacao')} IS NOT NULL "
        f"AND {c('data_hora_publicacao')} <> '') AS com_hora "
        f"FROM {T} GROUP BY ano, origem ORDER BY ano, origem"
    )
    pct = pct_com_hora_por_ano(df_ano)
    adicionar_tabela(secao, "Percentual com hora, por ano", ["ano", "pct_com_hora"],
                     [[a, p] for a, p in pct.items()])
    linhas_ao = [
        [_ano(a), texto(o), inteiro(t), inteiro(ch)]
        for a, o, t, ch in _registros(df_ano, ("ano", "origem", "total", "com_hora"))
    ]
    adicionar_tabela(secao, "Percentual com hora, por ano e origem",
                     ["ano", "origem", "total", "com_hora"], linhas_ao)
    for ano_v, origem_v, total, com_hora in linhas_ao:
        if origem_v == "google_news" and com_hora < total:
            secao["divergencias"].append(
                div("noticia_sem_hora", nome, f"{ano_v}: {total - com_hora} de {total} sem hora"))

    # c) formatos ISO de data_hora_publicacao e data_hora_coleta
    linhas_iso = []
    for coluna in ("data_hora_publicacao", "data_hora_coleta"):
        df_iso = ler(montar_sql_formato_iso(nome, _col_real(mapa, "noticias", coluna)))
        for tam, fim, n, ex_min, ex_max in _registros(
                df_iso, ("tam", "fim", "n", "exemplo_min", "exemplo_max")):
            classe = classificar_grupo_iso(ex_min, ex_max)
            off = offset_iso(ex_max)
            linhas_iso.append([coluna, inteiro(tam), fim, inteiro(n), ex_min, ex_max, classe])
            if classe != "iso_com_fuso" or off != OFFSET_SP:
                secao["divergencias"].append(div(
                    "formato_data", nome,
                    f"{coluna}: {inteiro(n)} linhas com formato {classe} (offset {off})"))
    adicionar_tabela(secao, "Formatos de data/hora",
                     ["coluna", "tam", "fim", "n", "exemplo_min", "exemplo_max", "classe"],
                     linhas_iso)
    secao["notas"].append(
        "formato classificado por grupo (tamanho + últimos 6 caracteres) "
        "usando os exemplos mínimo e máximo")

    # d) fuso conferido com raw_articles.published_at
    anos = sorted({a for a in (_ano(x) for x in df_ano["ano"]) if a is not None})
    if _existe(mapa, existentes, "raw_articles"):
        RAW = _tab(mapa, "raw_articles")
        r = lambda x: _col(mapa, "raw_articles", x)
        linhas_fuso = []
        for ano in anos:
            df_f = ler(
                f"SELECT n.{c('data_hora_publicacao')} AS iso, r.{r('published_at')} AS utc "
                f"FROM {T} n JOIN {RAW} r ON r.{r('id')} = CAST(SUBSTRING(n.{c('id')}, 2) AS UNSIGNED) "
                f"WHERE n.{c('data_hora_publicacao')} IS NOT NULL "
                f"AND YEAR(n.{c('data_publicacao')}) = {ano} LIMIT {AMOSTRA_FUSO_POR_ANO}"
            )
            pares = _registros(df_f, ("iso", "utc"))
            batem = sum(1 for iso, utc in pares if confere_fuso(iso, utc))
            amostra = len(pares)
            nao_batem = amostra - batem
            linhas_fuso.append([ano, amostra, batem, nao_batem])
            if nao_batem > 0:
                secao["divergencias"].append(div(
                    "fuso", nome,
                    f"{ano}: {nao_batem} de {amostra} não batem com raw_articles.published_at"))
        adicionar_tabela(secao, "Fuso: data_hora_publicacao × raw_articles.published_at",
                         ["ano", "amostra", "batem", "nao_batem"], linhas_fuso)
    else:
        p = _pulada(mapa, "raw_articles")
        secao["notas"].append(f"Fuso: {p}")

    # e) idioma e modelo do FinBERT
    if _existe(mapa, existentes, "raw_articles"):
        df_idi = ler(
            f"SELECT YEAR(n.{c('data_publicacao')}) AS ano, r.{r('lang')} AS lang, "
            f"COUNT(*) AS pares, COUNT(DISTINCT n.{c('id')}) AS artigos "
            f"FROM {T} n LEFT JOIN {RAW} r ON r.{r('id')} = CAST(SUBSTRING(n.{c('id')}, 2) AS UNSIGNED) "
            f"GROUP BY ano, lang ORDER BY ano, lang"
        )
        linhas_idi = _registros(df_idi, ("ano", "lang", "pares", "artigos"))
        adicionar_tabela(secao, "Idioma (raw_articles.lang)",
                         ["ano", "lang", "pares", "artigos"], linhas_idi)
        for ano_v, lang_v, pares_v, _artigos in linhas_idi:
            if texto(lang_v) is None:
                secao["divergencias"].append(div(
                    "ligacao_raw_articles", nome,
                    f"{ano_v}: {inteiro(pares_v)} pares sem idioma em raw_articles"))
        fora_idioma = valores_fora_da_lista([linha[1] for linha in linhas_idi], IDIOMAS)
        if fora_idioma:
            secao["divergencias"].append(
                div("idioma", _nome(mapa, "raw_articles"), ", ".join(fora_idioma)))

        if _existe(mapa, existentes, "sentimento_artigos"):
            SENT = _tab(mapa, "sentimento_artigos")
            s = lambda x: _col(mapa, "sentimento_artigos", x)
            df_mod = ler(
                f"SELECT r.{r('lang')} AS lang, s.{s('model')} AS model, "
                f"s.{s('text_source')} AS text_source, COUNT(*) AS n "
                f"FROM {T} n JOIN {RAW} r ON r.{r('id')} = CAST(SUBSTRING(n.{c('id')}, 2) AS UNSIGNED) "
                f"JOIN {SENT} s ON s.{s('article_id')} = r.{r('id')} "
                f"GROUP BY lang, model, text_source"
            )
            linhas_mod = _registros(df_mod, ("lang", "model", "text_source", "n"))
            adicionar_tabela(secao, "Modelo do FinBERT por idioma",
                             ["lang", "model", "text_source", "n"], linhas_mod)
            fora_modelo = valores_fora_da_lista(
                [linha[1] for linha in linhas_mod], MODELOS_FINBERT.values())
            if fora_modelo:
                secao["divergencias"].append(div(
                    "modelo_finbert", _nome(mapa, "sentimento_artigos"), ", ".join(fora_modelo)))
        else:
            p = _pulada(mapa, "sentimento_artigos")
            secao["notas"].append(f"Modelo do FinBERT: {p}")
    else:
        p = _pulada(mapa, "raw_articles")
        secao["notas"].append(f"Idioma e modelo do FinBERT: {p}")

    # f) formato do id
    df_id = ler(
        f"SELECT LEFT({c('id')}, 1) AS ini, CHAR_LENGTH({c('id')}) AS tam, COUNT(*) AS n, "
        f"MIN({c('id')}) AS exemplo_min, MAX({c('id')}) AS exemplo_max "
        f"FROM {T} GROUP BY ini, tam"
    )
    linhas_id = _registros(df_id, ("ini", "tam", "n", "exemplo_min", "exemplo_max"))
    adicionar_tabela(secao, "Formato do id", ["ini", "tam", "n", "exemplo_min", "exemplo_max"],
                     linhas_id)
    for _ini, _tam, _n, ex_min, ex_max in linhas_id:
        for exemplo in dict.fromkeys((ex_min, ex_max)):
            if not classificar_id_noticia(exemplo):
                secao["divergencias"].append(
                    div("id_noticia", nome, f"exemplo fora do padrão n + 6 dígitos: {exemplo}"))
    return secao


# ---------------------------------------------------------------------------
# Preços
# ---------------------------------------------------------------------------

def secao_precos(ler, mapa: dict, existentes: set) -> dict:
    """Seção de preços: calendário de pregões, buracos por ticker e séries macro."""
    secao = nova_secao("Preços (v1-precos)")
    if not _existe(mapa, existentes, "precos"):
        secao["notas"].append(_pulada(mapa, "precos"))
        return secao
    nome = _nome(mapa, "precos")
    T = _tab(mapa, "precos")
    c = lambda x: _col(mapa, "precos", x)
    t, d, v = c("ticker"), c("data"), c("volume")

    # Calendário do IBOV
    df_ibov = ler(f"SELECT {d} AS data FROM {T} WHERE {t} = 'IBOV' ORDER BY data")
    datas_ibov = [x for x in (_data(valor) for valor in df_ibov["data"]) if x is not None]
    anos = contar_por_ano(datas_ibov)
    adicionar_tabela(secao, "Pregões por ano (IBOV)", ["ano", "pregoes"],
                     [[a, n] for a, n in anos.items()])
    sem_pregao = dias_uteis_sem_pregao(datas_ibov)
    adicionar_tabela(secao, "Dias úteis sem pregão (informativo, inclui feriados)",
                     ["data"], [[x] for x in sem_pregao])
    secao["notas"].append(f"{len(sem_pregao)} dias úteis sem pregão no IBOV (inclui feriados)")

    # Buracos por ticker
    df_outros = ler(
        f"SELECT {t} AS ticker, {d} AS data FROM {T} WHERE {t} NOT IN ('IBOV', 'USDBRL', 'BRENT')"
    )
    por_ticker: dict = {}
    for tk, dt in _registros(df_outros, ("ticker", "data")):
        tk_txt = texto(tk)
        dt_val = _data(dt)
        if tk_txt is None or dt_val is None:
            continue
        por_ticker.setdefault(tk_txt, []).append(dt_val)
    buracos = buracos_por_ticker(datas_ibov, por_ticker)
    linhas_buracos = []
    for tk in sorted(buracos):
        b = buracos[tk]
        if not b["faltando"] and not b["fora_do_pregao"]:
            continue
        datas = por_ticker[tk]
        linhas_buracos.append([
            tk, min(datas), max(datas), len(b["faltando"]), len(b["fora_do_pregao"]),
            b["faltando"][:5],
        ])
        if b["faltando"]:
            secao["notas"].append(
                f"{tk}: {len(b['faltando'])} pregões faltando (pode ser suspensão)")
        if b["fora_do_pregao"]:
            secao["divergencias"].append(div("preco_fora_do_pregao", nome, tk))
    adicionar_tabela(secao, "Buracos por ticker (só os com problema)",
                     ["ticker", "primeira", "ultima", "n_faltando", "n_fora_do_pregao",
                      "exemplos (5 primeiros)"], linhas_buracos)

    # Séries macro
    df_macro = ler(
        f"SELECT {t} AS ticker, COUNT(*) AS linhas, COUNT({v}) AS com_volume, "
        f"MIN({d}) AS inicio, MAX({d}) AS fim FROM {T} "
        f"WHERE {t} IN ('IBOV', 'USDBRL', 'BRENT', 'IVVB11') GROUP BY {t}"
    )
    linhas_macro = _registros(df_macro, ("ticker", "linhas", "com_volume", "inicio", "fim"))
    adicionar_tabela(secao, "Séries macro", ["ticker", "linhas", "com_volume", "inicio", "fim"],
                     [[tk, inteiro(n), inteiro(cv), ini, fim] for tk, n, cv, ini, fim in linhas_macro])
    presentes = {texto(linha[0]) for linha in linhas_macro}
    for serie in sorted(MACROS_PRECOS - presentes):
        secao["divergencias"].append(div("serie_ausente", nome, serie))
    for tk, _n, cv, _ini, _fim in linhas_macro:
        if texto(tk) in {"IBOV", "USDBRL", "BRENT"} and inteiro(cv) > 0:
            secao["divergencias"].append(div("volume_nao_acao", nome, texto(tk)))
    return secao


# ---------------------------------------------------------------------------
# Balanços
# ---------------------------------------------------------------------------

def secao_balancos(ler, mapa: dict, existentes: set) -> dict:
    """Seção de balanços: escala, maiores receitas, períodos e datas de entrega."""
    secao = nova_secao("Balanços (v1-balancos)")
    if not _existe(mapa, existentes, "balancos"):
        secao["notas"].append(_pulada(mapa, "balancos"))
        return secao
    nome = _nome(mapa, "balancos")
    T = _tab(mapa, "balancos")
    c = lambda x: _col(mapa, "balancos", x)
    cnpj, tipo, ini, fim = c("cnpj"), c("tipo_documento"), c("data_inicio_periodo"), c("data_fim_periodo")
    entrega, receita = c("data_entrega"), c("receita_liquida")

    # Escala
    linhas_escala = []
    for col in ("receita_liquida", "patrimonio_liquido"):
        cc = c(col)
        df = ler(
            f"SELECT FLOOR(LOG10(ABS({cc}))) AS ordem, COUNT(*) AS n FROM {T} "
            f"WHERE {cc} IS NOT NULL AND {cc} <> 0 GROUP BY ordem ORDER BY ordem"
        )
        ordens = {inteiro(o): inteiro(n) for o, n in _registros(df, ("ordem", "n"))}
        veredito = veredito_escala(ordens)
        linhas_escala.append([col, veredito, sum(ordens.values())])
        if col == "receita_liquida" and veredito != "reais":
            secao["divergencias"].append(div("escala", nome, f"receita_liquida: {veredito}"))
        df_mil = ler(
            f"SELECT COUNT({cc}) AS com_valor, "
            f"SUM(MOD(ROUND({cc}), 1000) = 0) AS multiplos_de_mil FROM {T}"
        )
        com_valor = inteiro(df_mil["com_valor"].iloc[0])
        multiplos = inteiro(df_mil["multiplos_de_mil"].iloc[0])
        secao["notas"].append(
            f"{col}: {multiplos} de {com_valor} valores são múltiplos de 1000 (informativo)")
    adicionar_tabela(secao, "Escala (ordem de grandeza)", ["coluna", "veredito", "valores"],
                     linhas_escala)

    # Maiores receitas DFP, com o nome da empresa
    if _existe(mapa, existentes, "cadastro"):
        CAD = _tab(mapa, "cadastro")
        k = lambda x: _col(mapa, "cadastro", x)
        df_top = ler(
            f"SELECT b.{cnpj} AS cnpj, c.empresa AS empresa, b.{fim} AS fim, b.{receita} AS receita "
            f"FROM {T} b LEFT JOIN (SELECT {k('cnpj')} AS cnpj, MIN({k('empresa')}) AS empresa "
            f"FROM {CAD} GROUP BY {k('cnpj')}) c ON c.cnpj = b.{cnpj} "
            f"WHERE b.{tipo} = 'DFP' ORDER BY b.{receita} DESC LIMIT 5"
        )
        adicionar_tabela(secao, "5 maiores receitas (DFP), com nome",
                         ["cnpj", "empresa", "fim", "receita"],
                         _registros(df_top, ("cnpj", "empresa", "fim", "receita")))
    else:
        p = _pulada(mapa, "cadastro")
        secao["notas"].append(f"Maiores receitas: {p}")

    # Períodos
    df_per = ler(
        f"SELECT {tipo} AS tipo_documento, DATEDIFF({fim}, {ini}) + 1 AS dias, COUNT(*) AS n "
        f"FROM {T} GROUP BY tipo_documento, dias ORDER BY tipo_documento, dias"
    )
    agregado: dict = {}
    for tp, dias, n in _registros(df_per, ("tipo_documento", "dias", "n")):
        rotulo_tipo = "NULL" if texto(tp) is None else texto(tp)
        classe = classificar_dias_periodo(inteiro(dias))
        agregado[(rotulo_tipo, classe)] = agregado.get((rotulo_tipo, classe), 0) + inteiro(n)
    adicionar_tabela(secao, "Períodos (tipo × classe de dias)", ["tipo_documento", "classe", "n"],
                     [[tp, cl, n] for (tp, cl), n in sorted(agregado.items())])
    for (tp, cl), n in sorted(agregado.items()):
        if tp == "DFP" and cl != "12m":
            secao["divergencias"].append(div("periodo", nome, f"DFP com período {cl}: {n} linhas"))
        if tp == "ITR" and cl not in ("3m", "6m", "9m"):
            secao["divergencias"].append(div("periodo", nome, f"ITR com período {cl}: {n} linhas"))

    # Entrega
    df_ent = ler(
        f"SELECT COUNT(*) AS total, SUM({entrega} IS NULL) AS sem_entrega, "
        f"SUM({entrega} < {fim}) AS entrega_antes_do_fim FROM {T}"
    )
    total = inteiro(df_ent["total"].iloc[0])
    sem_entrega = inteiro(df_ent["sem_entrega"].iloc[0])
    antes_fim = inteiro(df_ent["entrega_antes_do_fim"].iloc[0])
    adicionar_tabela(secao, "Datas de entrega", ["total", "sem_entrega", "entrega_antes_do_fim"],
                     [[total, sem_entrega, antes_fim]])
    if sem_entrega > 0:
        secao["divergencias"].append(
            div("data_entrega", nome, f"sem_entrega: {sem_entrega} de {total}"))
    if antes_fim > 0:
        secao["divergencias"].append(
            div("data_entrega", nome, f"entrega_antes_do_fim: {antes_fim} de {total}"))
    return secao


# ---------------------------------------------------------------------------
# Tickers e CNPJs
# ---------------------------------------------------------------------------

_PARES_TICKERS = {
    "cad_ticker": ("cadastro", "ticker"),
    "precos": ("precos", "ticker"),
    "noticias": ("noticias", "ticker"),
    "proventos": ("proventos", "ticker"),
    "mud_antigo": ("mudancas_ticker", "ticker_antigo"),
    "mud_novo": ("mudancas_ticker", "ticker_novo"),
    "cad_cnpj": ("cadastro", "cnpj"),
    "bal_cnpj": ("balancos", "cnpj"),
    "acoes_cnpj": ("acoes_emitidas", "cnpj"),
}

_COMPARACOES_TICKERS = (
    ("cadastro × precos", "cad_ticker", "precos"),
    ("cadastro × noticias", "cad_ticker", "noticias"),
    ("cadastro × proventos", "cad_ticker", "proventos"),
    ("cadastro × mudancas (ticker_novo)", "cad_ticker", "mud_novo"),
    ("cadastro × balancos (cnpj)", "cad_cnpj", "bal_cnpj"),
    ("cadastro × acoes_emitidas (cnpj)", "cad_cnpj", "acoes_cnpj"),
)


def _classificar_proventos(tickers, cadastro: dict, mudancas: dict, codigos: dict) -> dict:
    """Classifica os tickers de proventos fora do cadastro pela classe (other_codes da B3).

    Devolve `existem` (ticker -> ticker do cadastro da mesma empresa, o primeiro em ordem
    alfabética), `extintas` (lista) e `pendentes` (textos 'ticker (situação)' para divergência).
    """
    existem: dict = {}
    extintas: list = []
    pendentes: list = []
    for tk in tickers:
        info = classificar_classe(tk, cadastro, mudancas, codigos)
        situacao = info["situacao"]
        if situacao == "existe":
            irmaos = sorted(t for t, cn in cadastro.items() if cn == info["cnpj"])
            existem[tk] = irmaos[0]
        elif situacao == "extinta":
            extintas.append(tk)
        else:
            pendentes.append(f"{tk} ({situacao})")
    return {"existem": existem, "extintas": extintas, "pendentes": pendentes}


def _tabela_proventos_extintas(ler, mapa: dict, existentes: set, secao: dict, extintas) -> None:
    """Tabela com os proventos de cada classe extinta e quantos caem no período analisado.

    Período analisado = do primeiro ao último pregão do IBOV em `v1-precos` (seção 6).
    """
    inicio = fim = None
    if _existe(mapa, existentes, "precos"):
        p = lambda x: _col(mapa, "precos", x)
        df_per = ler(f"SELECT MIN({p('data')}) AS inicio, MAX({p('data')}) AS fim "
                     f"FROM {_tab(mapa, 'precos')} WHERE {p('ticker')} = 'IBOV'")
        if not df_per.empty:
            inicio, fim = _data(df_per["inicio"].iloc[0]), _data(df_per["fim"].iloc[0])
    v = lambda x: _col(mapa, "proventos", x)
    df_prov = ler(f"SELECT {v('ticker')} AS ticker, {v('data_com')} AS data_com "
                  f"FROM {_tab(mapa, 'proventos')}")
    linhas = [(texto(tk), _data(dc)) for tk, dc in _registros(df_prov, ("ticker", "data_com"))]
    secao["notas"].append(f"período analisado (pregões do IBOV): {inicio} a {fim}")
    adicionar_tabela(secao, "Classes extintas: proventos",
                     ["ticker", "proventos", "primeira_data_com", "ultima_data_com", "no_periodo"],
                     resumo_proventos_por_ticker(linhas, extintas, inicio, fim))


def secao_tickers(ler, mapa: dict, existentes: set, exclusoes: Exclusoes | None = None) -> dict:
    """Seção de tickers e CNPJs: conjuntos, comparações e padrões de identificadores.

    `exclusoes` vem de `config/exclusoes.yaml`; se não for dado, é carregado aqui.
    """
    if exclusoes is None:
        exclusoes = carregar_exclusoes()
    secao = nova_secao("Tickers e CNPJs")
    faltam = sorted({_nome(mapa, tab) for tab, _col_ in _PARES_TICKERS.values()
                     if _nome(mapa, tab) not in existentes})
    if faltam:
        secao["notas"].append("pulada: tabela ausente (" + ", ".join(f"`{x}`" for x in faltam) + ")")

    conj: dict = {}
    for chave, (tab, coluna) in _PARES_TICKERS.items():
        if _nome(mapa, tab) in existentes:
            conj[chave] = _valores(ler, _tab(mapa, tab), _col(mapa, tab, coluna))
        else:
            conj[chave] = None

    # Cadastro (ticker -> CNPJ), mudanças de ticker e other_codes por CNPJ (códigos atuais)
    cad_dict: dict = {}
    if _existe(mapa, existentes, "cadastro"):
        CAD = _tab(mapa, "cadastro")
        k = lambda x: _col(mapa, "cadastro", x)
        df_cad = ler(f"SELECT {k('ticker')} AS ticker, {k('cnpj')} AS cnpj FROM {CAD}")
        cad_dict = {texto(tk): texto(cn) for tk, cn in _registros(df_cad, ("ticker", "cnpj"))
                    if texto(tk) is not None}

    mudancas: dict = {}
    if _existe(mapa, existentes, "mudancas_ticker"):
        MUD = _tab(mapa, "mudancas_ticker")
        m = lambda x: _col(mapa, "mudancas_ticker", x)
        df_mud = ler(f"SELECT {m('ticker_antigo')} AS ticker_antigo, "
                     f"{m('ticker_novo')} AS ticker_novo FROM {MUD}")
        mudancas = {texto(a): texto(b) for a, b in _registros(df_mud, ("ticker_antigo", "ticker_novo"))
                    if texto(a) is not None and texto(b) is not None}

    codigos: dict = {}
    tem_raw = _existe(mapa, existentes, "raw_b3_cadastro")
    if tem_raw:
        RAW = _tab(mapa, "raw_b3_cadastro")
        b = lambda x: _col(mapa, "raw_b3_cadastro", x)
        df_raw = ler(f"SELECT {b('cnpj')} AS cnpj, {b('other_codes')} AS other_codes "
                     f"FROM {RAW} WHERE {b('cnpj')} IS NOT NULL")
        validos, invalidos = [], []
        for cn, oc in _registros(df_raw, ("cnpj", "other_codes")):
            try:
                parse_other_codes(oc)
                validos.append((cn, oc))
            except ValueError:
                invalidos.append(texto(cn))
        codigos = codigos_por_cnpj(validos)
        if invalidos:
            secao["divergencias"].append(div(
                "other_codes", _nome(mapa, "raw_b3_cadastro"),
                "JSON inválido em other_codes: " + ", ".join(sorted(set(invalidos)))))

    # Cobertura do other_codes: cada ticker do cadastro (com CNPJ) precisa estar na lista da empresa
    if not tem_raw:
        secao["divergencias"].append(div(
            "other_codes", _nome(mapa, "raw_b3_cadastro"),
            "tabela ausente: não dá para ligar ticker à empresa nem classificar classes"))
    elif cad_dict:
        sem_linha: dict = {}
        fora: list = []
        for tk in sorted(cad_dict):
            cn = cad_dict[tk]
            if cn is None or tk in exclusoes.tickers_excluidos:
                continue
            if cn not in codigos:
                sem_linha.setdefault(cn, []).append(tk)
            elif tk not in codigos[cn]:
                fora.append(f"{tk} ({cn})")
        partes = []
        if sem_linha:
            partes.append("cnpj sem linha em other_codes: " + ", ".join(
                f"{cn} ({', '.join(tks)})" for cn, tks in sorted(sem_linha.items())))
        if fora:
            partes.append("ticker fora do other_codes da empresa: " + ", ".join(fora))
        if partes:
            secao["divergencias"].append(div(
                "other_codes", _nome(mapa, "raw_b3_cadastro"), "; ".join(partes)))

    # Tickers excluídos por decisão (config/exclusoes.yaml) que aparecem sem ser divergência
    excluidos: set = set()

    # Formato dos tickers, na união de todas as tabelas de ticker
    uniao: set = set()
    for chave in ("cad_ticker", "precos", "noticias", "proventos", "mud_antigo", "mud_novo"):
        if conj[chave] is not None:
            uniao |= conj[chave]
    fora_padrao = tickers_fora_do_padrao(uniao - SERIES_FORA_CALENDARIO)
    if fora_padrao:
        secao["divergencias"].append(
            div("ticker_formato", "tickers (várias tabelas)", ", ".join(fora_padrao)))

    # Comparações de conjuntos
    resultados: dict = {}
    linhas_cmp = []
    for rotulo, ref, outro in _COMPARACOES_TICKERS:
        if conj[ref] is None or conj[outro] is None:
            continue
        res = comparar_com_referencia(conj[ref], conj[outro])
        resultados[(ref, outro)] = res
        linhas_cmp.append([rotulo, res["so_na_referencia"], res["so_no_outro"]])
    adicionar_tabela(secao, "Comparação de conjuntos",
                     ["comparacao", "so_na_referencia", "so_no_outro"], linhas_cmp)

    # Preços: tickers do cadastro sem preço (excluídos por decisão viram nota) e preços sem cadastro
    res_precos = resultados.get(("cad_ticker", "precos"))
    if res_precos is not None:
        sem_cadastro = [tk for tk in res_precos["so_no_outro"] if tk not in MACROS_PRECOS]
        if sem_cadastro:
            secao["divergencias"].append(
                div("ticker_sem_cadastro", _nome(mapa, "precos"), ", ".join(sem_cadastro)))
        excluidos.update(tk for tk in res_precos["so_na_referencia"]
                         if tk in exclusoes.tickers_excluidos)
        sem_preco = [tk for tk in res_precos["so_na_referencia"]
                     if tk not in exclusoes.tickers_excluidos]
        if sem_preco:
            secao["divergencias"].append(div(
                "ticker_sem_preco", _nome(mapa, "precos"), ", ".join(sem_preco)))
    if conj["precos"] is not None:
        for tk in sorted(exclusoes.tickers_excluidos):
            if tk in conj["precos"]:
                secao["notas"].append(f"exclusão a rever: {tk} tem preço")

    # Notícias e proventos: sem cadastro é divergência; sem linha é só nota.
    # Proventos: classe de empresa conhecida vira nota (existe/extinta); o resto diverge.
    for chave in ("noticias", "proventos"):
        res_ref = resultados.get(("cad_ticker", chave))
        if res_ref is None:
            continue
        pendentes = list(res_ref["so_no_outro"])
        if chave == "proventos":
            # Classe de empresa excluída (ex.: STBP4 da STBP3) segue a exclusão da empresa
            cnpjs_excluidos = {cad_dict[t] for t in exclusoes.tickers_excluidos if cad_dict.get(t)}
            da_excluida = {tk for tk in pendentes
                           if tk in exclusoes.tickers_excluidos
                           or ligar_a_cnpj(tk, cad_dict, mudancas)[0] in cnpjs_excluidos}
            excluidos.update(da_excluida)
            pendentes = [tk for tk in pendentes if tk not in da_excluida]
            cls = _classificar_proventos(pendentes, cad_dict, mudancas, codigos)
            if cls["existem"]:
                secao["notas"].append(
                    f"{len(cls['existem'])} classes ligadas à empresa pela raiz "
                    "(estão no other_codes): "
                    + ", ".join(f"{tk} → {alvo}" for tk, alvo in cls["existem"].items()))
            if cls["extintas"]:
                secao["notas"].append(
                    f"{len(cls['extintas'])} classes extintas (fora do other_codes): contam no "
                    "histórico de proventos e no payout, ligadas pela raiz; units (final 11) "
                    "ficam de fora do payout: " + ", ".join(cls["extintas"]))
                _tabela_proventos_extintas(ler, mapa, existentes, secao, cls["extintas"])
            pendentes = cls["pendentes"]
        if pendentes:
            secao["divergencias"].append(div(
                "ticker_sem_cadastro", _nome(mapa, chave), ", ".join(pendentes)))
        if res_ref["so_na_referencia"]:
            secao["notas"].append(
                f"{_nome(mapa, chave)}: {len(res_ref['so_na_referencia'])} tickers do cadastro "
                f"sem linhas (informativo)")
    if excluidos:
        secao["notas"].append(
            "excluídos por decisão (config/exclusoes.yaml): " + ", ".join(sorted(excluidos)))

    # Mudanças de ticker: o novo ticker precisa estar no cadastro
    res_mud = resultados.get(("cad_ticker", "mud_novo"))
    if res_mud is not None and res_mud["so_no_outro"]:
        secao["divergencias"].append(div(
            "mudanca_ticker", _nome(mapa, "mudancas_ticker"), ", ".join(res_mud["so_no_outro"])))

    # CNPJs: formato e ligação entre cadastro, balanços e ações emitidas
    for chave, tab in (("cad_cnpj", "cadastro"), ("bal_cnpj", "balancos"),
                       ("acoes_cnpj", "acoes_emitidas")):
        if conj[chave] is not None:
            fora_cnpj = cnpjs_fora_do_padrao(conj[chave])
            if fora_cnpj:
                secao["divergencias"].append(
                    div("cnpj_formato", _nome(mapa, tab), ", ".join(fora_cnpj)))
    res_bal = resultados.get(("cad_cnpj", "bal_cnpj"))
    if res_bal is not None:
        sem_balanco = [c for c in res_bal["so_na_referencia"] if c not in exclusoes.cnpjs_sem_balanco]
        por_decisao = [c for c in res_bal["so_na_referencia"] if c in exclusoes.cnpjs_sem_balanco]
        if por_decisao:
            secao["notas"].append(
                "sem balanço por decisão (config/exclusoes.yaml): " + ", ".join(por_decisao))
        if sem_balanco:
            secao["divergencias"].append(div(
                "cnpj_sem_balanco", _nome(mapa, "cadastro"), ", ".join(sem_balanco)))
    if conj["bal_cnpj"] is not None:
        for c in sorted(exclusoes.cnpjs_sem_balanco):
            if c in conj["bal_cnpj"]:
                secao["notas"].append(f"exclusão a rever: {c} tem balanço")
    res_acoes = resultados.get(("cad_cnpj", "acoes_cnpj"))
    if res_acoes is not None and res_acoes["so_na_referencia"]:
        secao["divergencias"].append(div(
            "cnpj_sem_acoes_emitidas", _nome(mapa, "cadastro"),
            ", ".join(res_acoes["so_na_referencia"])))

    # Cadastro: CNPJ ausente, units e ETF no cadastro
    if _existe(mapa, existentes, "cadastro"):
        CAD = _tab(mapa, "cadastro")
        k = lambda x: _col(mapa, "cadastro", x)
        df_sem = ler(f"SELECT {k('ticker')} AS ticker FROM {CAD} WHERE {k('cnpj')} IS NULL")
        sem_cnpj = sorted({texto(x) for x in df_sem["ticker"]} - {None} - SEM_CNPJ_CONHECIDOS)
        if sem_cnpj:
            secao["divergencias"].append(
                div("cnpj_ausente", _nome(mapa, "cadastro"), ", ".join(sem_cnpj)))

        df_un = ler(
            f"SELECT {k('ticker')} AS ticker, {k('unit_qtd_on')} AS unit_qtd_on, "
            f"{k('unit_qtd_pn')} AS unit_qtd_pn FROM {CAD} WHERE {k('tipo_acao')} = 'UNIT'"
        )
        unit_tickers = {texto(x) for x in df_un["ticker"]} - {None}
        comp_un = comparar_com_referencia(UNITS, unit_tickers)
        if comp_un["so_na_referencia"] or comp_un["so_no_outro"]:
            secao["divergencias"].append(div(
                "units", _nome(mapa, "cadastro"),
                f"UNIT fora de UNITS: {_lista(comp_un['so_no_outro'])}; "
                f"em UNITS sem tipo_acao UNIT: {_lista(comp_un['so_na_referencia'])}"))
        nulos_un = [str(tk) for tk, on, pn in _registros(
            df_un, ("ticker", "unit_qtd_on", "unit_qtd_pn")) if pd.isna(on) or pd.isna(pn)]
        if nulos_un:
            secao["divergencias"].append(div(
                "units", _nome(mapa, "cadastro"),
                f"unit_qtd_on/unit_qtd_pn NULL em: {', '.join(nulos_un)}"))

    if conj["cad_ticker"] is not None and "IVVB11" in conj["cad_ticker"]:
        secao["divergencias"].append(div(
            "ivvb11_no_cadastro", _nome(mapa, "cadastro"),
            "IVVB11 (ETF) está no v1-cadastro; com tipo_acao UNIT entraria no universo do "
            "modelo (seção 3.5)"))
    return secao


# ---------------------------------------------------------------------------
# Painel de execuções da coleta
# ---------------------------------------------------------------------------

def secao_painel(ler, mapa: dict, existentes: set) -> dict:
    """Seção do painel: execuções, horário do daily (UTC), etapas e composição do Ibovespa."""
    secao = nova_secao("Painel de execuções (v1-painel_execucoes e v1-painel_etapas)")
    if not _existe(mapa, existentes, "painel_execucoes"):
        secao["notas"].append(_pulada(mapa, "painel_execucoes"))
    else:
        EXE = _tab(mapa, "painel_execucoes")
        e = lambda x: _col(mapa, "painel_execucoes", x)
        tipo, status, ini, origem = e("tipo"), e("status"), e("iniciada_em"), e("origem")

        df_exec = ler(
            f"SELECT {tipo} AS tipo, {status} AS status, COUNT(*) AS n, "
            f"MIN({ini}) AS primeira, MAX({ini}) AS ultima FROM {EXE} "
            f"GROUP BY tipo, status ORDER BY tipo, status"
        )
        adicionar_tabela(secao, "Execuções por tipo e status",
                         ["tipo", "status", "n", "primeira", "ultima"],
                         _registros(df_exec, ("tipo", "status", "n", "primeira", "ultima")))
        if "daily" not in {texto(x) for x in df_exec["tipo"]}:
            secao["divergencias"].append(
                div("sem_daily", _nome(mapa, "painel_execucoes"), "nenhuma execução do tipo daily"))

        df_hora = ler(
            f"SELECT {origem} AS origem, HOUR({ini}) AS hora, COUNT(*) AS n "
            f"FROM {EXE} WHERE {tipo} = 'daily' GROUP BY origem, hora ORDER BY origem, hora"
        )
        horas = [
            ["NULL" if texto(o) is None else texto(o), inteiro(h), inteiro(n)]
            for o, h, n in _registros(df_hora, ("origem", "hora", "n"))
        ]
        adicionar_tabela(secao, "Hora de início do daily (UTC)", ["origem", "hora", "n"], horas)

        cron: dict = {}
        manual: dict = {}
        outras: dict = {}
        for o, h, n in horas:
            if o == "cron":
                cron[h] = cron.get(h, 0) + n
            elif o == "manual":
                manual[h] = manual.get(h, 0) + n
            else:
                outras[o] = outras.get(o, 0) + n

        agenda = "/".join(f"{h}h" for h in HORAS_DAILY_UTC)
        if not cron:
            secao["notas"].append("nenhum daily com origem cron")
        else:
            fora = horas_fora_da_agenda(cron)
            if fora:
                secao["notas"].append(
                    f"daily cron fora da agenda ({agenda} UTC): {_resumo_horas(fora)} execuções")
        if manual:
            total_manual = sum(manual.values())
            secao["notas"].append(
                f"daily manual: {total_manual} execuções ({_resumo_horas(manual)})")
        for o, n in sorted(outras.items()):
            secao["notas"].append(f"daily com origem fora de cron/manual: {o}: {n} execuções")

    if _existe(mapa, existentes, "painel_etapas"):
        ETA = _tab(mapa, "painel_etapas")
        g = lambda x: _col(mapa, "painel_etapas", x)
        df_eta = ler(
            f"SELECT {g('etapa_id')} AS etapa_id, MIN({g('ordem')}) AS ordem, "
            f"{g('status')} AS status, COUNT(*) AS n FROM {ETA} "
            f"GROUP BY etapa_id, status ORDER BY ordem, status"
        )
        adicionar_tabela(secao, "Etapas do painel", ["etapa_id", "ordem", "status", "n"],
                         _registros(df_eta, ("etapa_id", "ordem", "status", "n")))
        ids = {texto(x) for x in df_eta["etapa_id"]} - {None}
        desconhecidas = valores_fora_da_lista(ids, ETAPAS_COLETA)
        if desconhecidas:
            secao["divergencias"].append(
                div("etapa_desconhecida", _nome(mapa, "painel_etapas"), ", ".join(desconhecidas)))
        if "entrega" not in ids:
            secao["divergencias"].append(div(
                "etapa_entrega_ausente", _nome(mapa, "painel_etapas"),
                "a etapa 'entrega' não aparece no painel"))
        fora_status = valores_fora_da_lista(df_eta["status"], STATUS_ETAPA)
        if fora_status:
            secao["divergencias"].append(
                div("status_desconhecido", _nome(mapa, "painel_etapas"), ", ".join(fora_status)))
    else:
        secao["notas"].append(_pulada(mapa, "painel_etapas"))

    # Composição do Ibovespa (opcional): só confere as colunas se a tabela existir
    if _existe(mapa, existentes, "composicao_ibov"):
        cmp_nome = _nome(mapa, "composicao_ibov")
        df_cols = ler(
            "SELECT COLUMN_NAME AS coluna FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{cmp_nome}'"
        )
        reais = [texto(x) for x in df_cols["coluna"] if texto(x) is not None]
        cfg = _entrada(mapa, "composicao_ibov")
        comp = comparar_colunas(list(cfg["colunas"].values()), reais,
                                cfg.get("colunas_ignoradas", []))
        secao["notas"].append(
            f"{cmp_nome}: colunas faltando {_lista(comp['faltando'])}; "
            f"extras {_lista(comp['extras'])}")
        if comp["faltando"]:
            secao["divergencias"].append(
                div("coluna_faltando", cmp_nome, ", ".join(comp["faltando"])))
    return secao
