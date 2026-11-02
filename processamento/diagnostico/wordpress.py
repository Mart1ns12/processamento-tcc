"""Validação da fonte `wordpress` em `v1-noticias`: `python -m processamento.diagnostico.wordpress`.

Só lê o banco (SELECT, conexão READ ONLY) e gera o relatório em Markdown (padrão:
`docs/validacao_wordpress.md`). A amostra manual vai para `docs/validacao_wordpress_amostra.csv`;
se esse CSV já existe, nunca é sobrescrito (é ele que o revisor preenche: coluna `ticker_correto`
com S, N ou ?). Nada é gravado no banco. A conta e as regras puras ficam em
`wordpress_analise.py`; aqui fica a leitura, as seções e a CLI.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from processamento import calendario, fontes
from processamento.diagnostico import wordpress_analise as an
from processamento.diagnostico.relatorio import tabela_md
from processamento.exclusoes import carregar_exclusoes
from processamento.experimento.noticias import preparar_noticias
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.experimento.tom import variaveis_de_noticias
from processamento.fatos.precos import mapas_cadastro
from processamento.tickers import ligar_a_cnpj, mapas_por_empresa
from processamento.universo import montar_universo

CAMINHO_SAIDA = fontes.RAIZ / "docs" / "validacao_wordpress.md"
CAMINHO_AMOSTRA = fontes.RAIZ / "docs" / "validacao_wordpress_amostra.csv"
ANO_MIN_PADRAO = 2022
SEMENTE_PADRAO = 42
ANO_EM_PROCESSAMENTO = 2021
FUSO = "America/Sao_Paulo"
WP = an.ORIGEM_WORDPRESS
GN = an.ORIGEM_GOOGLE

# Colunas de raw_articles que o fontes.yaml não lista (ver docs/ddl_banco_coleta.sql, tabela raw_articles)
RAW_EXTRAS = ("url", "resolved_url", "title", "source_name", "source_domain")
# Colunas de v1-noticias usadas aqui; as que o mapa lista saem por fontes.coluna_real
COLUNAS_V1 = [
    "id", "ticker", "data_hora_publicacao", "data_hora_coleta", "titulo", "fonte", "link",
    "prob_positivo", "prob_neutro", "prob_negativo", "origem", "papel", "tipo_conteudo", "evento",
    "qualidade", "data_publicacao",
]
# momento_pregao existe no banco e está em `colunas_ignoradas` do mapa: só para o informativo da seção 4
COLUNA_MOMENTO = "momento_pregao"

PERGUNTAS_COLETA = [
    "Quais sites entram na fonte wordpress, e com que critério?",
    "Como o ticker é atribuído a cada artigo (busca no título, no corpo, ou outra regra)?",
    "A coleta usa `date` ou `date_gmt`? Isso muda o fuso e a hora usados aqui.",
    "Os artigos têm corpo (body)? Hoje a análise só vê título e link.",
    "Por que 2023, 2024 e 2025 não aparecem na entrega (ver seção 0)?",
    "Qual é o status de 2021 (em processamento, descartado ou fora do escopo)?",
]
PENDENCIA_ERRADA = (
    "Papel 'errada': desde 01/11/2026 `fontes.ler_noticias` descarta papel='errada' em todas as versões "
    "(`papeis_ignorados` no fontes.yaml; papel vazio fica). Esta medição lê com o filtro desligado "
    "para mostrar o papel de cada origem."
)


def _nulo(v) -> bool:
    """True para None, NaN e NaT."""
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _txt(v) -> str | None:
    """Texto sem espaços das pontas; vazio ou nulo vira None."""
    if _nulo(v):
        return None
    s = str(v).strip()
    return s or None


def _pct(parte: int, total: int) -> str:
    """Percentual com uma casa; total zero vira traço."""
    if not total:
        return "—"
    return f"{100 * parte / total:.1f}%"


def _tabela(colunas: list[str], linhas) -> str:
    """Tabela markdown (ou aviso de tabela vazia)."""
    return tabela_md(colunas, [list(linha) for linha in linhas])


# ---------------------------------------------------------------------------
# Leitura (SQL simples, compatível com MySQL e SQLite; a junção é feita em pandas)
# ---------------------------------------------------------------------------

@dataclass
class Dados:
    """Tabelas lidas: `v1` (todas as linhas de v1-noticias já ligadas à raw), `raw` e `stg`."""

    v1: pd.DataFrame
    raw: pd.DataFrame
    stg: pd.DataFrame
    # v1-noticias como veio do banco (colunas lógicas), para a seção 8 não ler de novo
    v1_bruta: pd.DataFrame | None = None


def _ler_v1(ler) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A ÚNICA leitura de v1-noticias: (tratada para as seções, cópia bruta para `tratar_noticias_lidas`)."""
    lista = [f"{fontes.coluna_sql('noticias', c)} AS {c}" for c in COLUNAS_V1]
    lista.append(f"{fontes.citar(COLUNA_MOMENTO)} AS {COLUNA_MOMENTO}")
    df = ler(f"SELECT {', '.join(lista)} FROM {fontes.tabela_sql('noticias')}")
    bruta = df[COLUNAS_V1].copy()
    for c in df.columns:
        df[c] = df[c].map(lambda v: None if isinstance(v, str) and not v.strip() else v)
    df["dhp_txt"] = df["data_hora_publicacao"]
    df["data_hora_publicacao"] = fontes.para_sao_paulo_iso(df["data_hora_publicacao"], "v1-noticias.data_hora_publicacao")
    df["data_hora_coleta"] = fontes.para_sao_paulo_iso(df["data_hora_coleta"], "v1-noticias.data_hora_coleta")
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"], errors="coerce", format="ISO8601")
    for c in ("prob_positivo", "prob_neutro", "prob_negativo"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["id_raw"] = pd.to_numeric(df["id"].astype(str).str[1:], errors="coerce")
    return df, bruta


def _ler_raw(ler) -> pd.DataFrame:
    """raw_articles: id, horário de publicação em São Paulo (vem do UTC) e as colunas de fonte."""
    real = {c: fontes.coluna_real("raw_articles", c) for c in ("id", "lang", "published_at", "published_precision", "origem")}
    pares = [(c, real[c]) for c in real] + [(c, c) for c in RAW_EXTRAS]
    lista = ", ".join(f"{fontes.citar(col)} AS {alias}" for alias, col in pares)
    df = ler(f"SELECT {lista} FROM {fontes.tabela_sql('raw_articles')}")
    df["id_raw"] = pd.to_numeric(df["id"], errors="coerce")
    df["publicado_em_sp"] = fontes.para_sao_paulo_de_utc(df["published_at"])
    df["origem_raw"] = df["origem"]
    return df.drop(columns=["id", "published_at", "origem"]).drop_duplicates("id_raw")


def _ler_staging(ler) -> pd.DataFrame:
    """Probabilidades FinBERT por artigo: article_id (= raw_articles.id), model, text_source."""
    tabela = fontes.nome_real("sentimento_artigos")
    real = {c: fontes.coluna_real("sentimento_artigos", c) for c in ("article_id", "model", "text_source")}
    lista = ", ".join(f"{fontes.citar(real[c])} AS {c}" for c in real)
    df = ler(f"SELECT {lista} FROM {fontes.citar(tabela)}")
    df["id_raw"] = pd.to_numeric(df["article_id"], errors="coerce")
    return df


def carregar(ler) -> Dados:
    """Lê as três tabelas e liga v1-noticias à raw_articles pelo número do id ("n" + id)."""
    v1, bruta = _ler_v1(ler)
    raw = _ler_raw(ler)
    stg = _ler_staging(ler)
    raw_j = raw[["id_raw", "publicado_em_sp", "published_precision", "lang", "origem_raw",
                 "url", "resolved_url", "source_name", "source_domain"]].rename(columns={"url": "url_raw"})
    v1 = v1.merge(raw_j, on="id_raw", how="left")
    v1["score"] = v1["prob_positivo"] - v1["prob_negativo"]
    # "só data" só nas origens de fontes.origens_so_data() (mesma regra de fontes.aplicar_regra_so_data)
    v1["so_data"] = fontes.meia_noite_pacifico(v1["data_hora_publicacao"]) & v1["origem"].isin(fontes.origens_so_data())
    v1["hora_real"] = v1["data_hora_publicacao"].notna() & ~v1["so_data"]
    v1["julgado"] = v1["papel"].notna()
    v1["ano"] = v1["data_publicacao"].dt.year
    # A cópia bruta (para tratar_noticias_lidas, como em ler_noticias) recebe resolved_url do merge com raw,
    # só nas origens de origens_so_data() (origem de raw_articles): é o que ler_urls_resolvidas faz
    url_resolvida = v1["resolved_url"].where(v1["origem_raw"].isin(fontes.origens_so_data()))
    bruta = bruta.assign(resolved_url=url_resolvida.to_numpy())
    return Dados(v1=v1, raw=raw, stg=stg, v1_bruta=bruta)


# ---------------------------------------------------------------------------
# Seções (cada uma devolve o corpo markdown; `_seguro` põe o título e trata a falha)
# ---------------------------------------------------------------------------

def _seguro(numero: int, titulo: str, func, *args) -> str:
    """Seção numerada; se o cálculo falhar, escreve a falha no lugar e as demais continuam."""
    try:
        corpo = func(*args)
    except Exception as erro:
        corpo = (f"_Esta seção não pôde ser concluída: {type(erro).__name__}: {erro}. "
                 "As demais continuaram._")
    return f"## {numero}. {titulo}\n\n{corpo}"


def secao_0(ctx: dict) -> str:
    """Prontidão: artigos wordpress por ano na raw_articles × na v1-noticias."""
    dados, ano_min = ctx["dados"], ctx["ano_min"]
    raw_wp = dados.raw[dados.raw["origem_raw"] == WP]
    anos_raw = raw_wp["publicado_em_sp"].dt.year.dropna().astype(int).value_counts()
    v1_wp = ctx["wp"].drop_duplicates("id")
    anos_v1 = v1_wp["ano"].dropna().astype(int).value_counts()
    anos = sorted(set(anos_raw.index) | set(anos_v1.index))
    linhas, faltando = [], []
    for ano in anos:
        n_raw = int(anos_raw.get(ano, 0))
        n_v1 = int(anos_v1.get(ano, 0))
        if ano < ano_min:
            situacao = ("em processamento (fora do veredito)" if ano == ANO_EM_PROCESSAMENTO
                        else "anterior ao ano mínimo (fora do veredito)")
        elif n_raw > 0 and n_v1 == 0:
            situacao = "FALTANDO na v1-noticias"
            faltando.append(ano)
        elif n_raw == 0 and n_v1 > 0:
            situacao = "só na v1-noticias (sem raw_articles)"
        else:
            situacao = "ok"
        linhas.append([ano, n_raw, n_v1, situacao])
    ctx["metricas"]["anos_faltando"] = faltando
    partes = [
        f"Ano mínimo do veredito: {ano_min}. Anos anteriores ficam fora do veredito.",
        _tabela(["ano", "artigos wordpress em raw_articles", "artigos wordpress distintos na v1-noticias", "situação"],
                linhas),
    ]
    return "\n\n".join(partes)


def _pivot_origens(df: pd.DataFrame, chave: str, rotulo: str) -> tuple[list[str], list[list]]:
    """Artigos distintos e pares por `chave` × origem, em uma linha por chave (`rotulo` no cabeçalho)."""
    g = df.groupby([chave, "origem"]).agg(artigos=("id", "nunique"), pares=("id", "size"))
    p = g.unstack("origem").fillna(0).astype(int)
    p.columns = [f"{medida} {origem}" for medida, origem in p.columns]
    colunas = [rotulo, *p.columns]
    linhas = [[idx, *valores] for idx, valores in zip(p.index, p.to_numpy().tolist())]
    return colunas, linhas


def secao_1(ctx: dict) -> str:
    """Volume por ano, ano-mês, origem e ticker; distribuição de tickers por artigo wordpress."""
    v1 = ctx["v1"].copy()
    v1["ano_txt"] = v1["ano"].map(lambda a: "sem data" if _nulo(a) else str(int(a)))
    v1["mes"] = v1["data_publicacao"].map(lambda d: "sem data" if _nulo(d) else d.strftime("%Y-%m"))
    partes = []
    colunas, linhas = _pivot_origens(v1, "ano_txt", "ano")
    partes.append("### Por ano (artigos distintos e pares)\n\n" + _tabela(colunas, linhas))
    colunas, linhas = _pivot_origens(v1, "mes", "mês")
    partes.append("### Por ano-mês (artigos distintos e pares)\n\n" + _tabela(colunas, linhas))
    por_origem = v1.groupby("origem").agg(artigos=("id", "nunique"), pares=("id", "size")).reset_index()
    partes.append("### Por origem\n\n" + _tabela(["origem", "artigos", "pares"], por_origem.values.tolist()))

    cruzado = pd.crosstab(v1["ticker"], v1["origem"])
    wp_por_ticker = cruzado.get(WP, pd.Series(0, index=cruzado.index))
    total = cruzado.sum(axis=1)
    participacao = (wp_por_ticker / total).fillna(0)
    tabela_tk = pd.DataFrame({"pares": total, "pares wordpress": wp_por_ticker, "participação wordpress": participacao})
    tabela_tk = tabela_tk.sort_values(["participação wordpress", "pares"], ascending=False).head(40)
    linhas_tk = [[t, int(r["pares"]), int(r["pares wordpress"]), _pct(int(r["pares wordpress"]), int(r["pares"]))]
                 for t, r in tabela_tk.iterrows()]
    sem_wp = sorted(cruzado.index[wp_por_ticker == 0])
    partes.append("### Por ticker (40 com maior participação wordpress)\n\n" + _tabela(
        ["ticker", "pares", "pares wordpress", "participação wordpress"], linhas_tk))
    trecho = ", ".join(sem_wp[:80]) + (" …" if len(sem_wp) > 80 else "")
    partes.append(f"Tickers sem nenhum artigo wordpress: {len(sem_wp)} de {len(cruzado)}."
                  + (f" Primeiros: {trecho}." if sem_wp else ""))

    wp = ctx["wp"]
    por_artigo = wp.groupby("id")["ticker"].nunique().value_counts().sort_index()
    partes.append("### Nº de tickers por artigo wordpress\n\n" + _tabela(
        ["nº de tickers", "artigos"], [[int(k), int(v)] for k, v in por_artigo.items()]))
    return "\n\n".join(partes)


def secao_2(ctx: dict) -> str:
    """Fontes e domínios do wordpress; comparação com source_domain e source_name; links vazios e repetidos."""
    wp = ctx["wp"]
    wp_u = wp.drop_duplicates("id")
    fontes_top = wp_u["fonte"].map(lambda v: _txt(v) or "(vazio)").value_counts().head(30)
    dominios = wp_u["link"].map(lambda v: an.dominio(v) or "(sem domínio)").value_counts().head(30)
    d_link = wp_u["link"].map(an.dominio)
    d_src = wp_u["source_domain"].map(an.dominio)
    comparavel_dom = d_link.notna() & d_src.notna()
    iguais_dom = int((comparavel_dom & (d_link == d_src)).sum())
    f_v1 = wp_u["fonte"].map(lambda v: (_txt(v) or "").casefold())
    f_raw = wp_u["source_name"].map(lambda v: (_txt(v) or "").casefold())
    comparavel_nome = f_v1.ne("") & f_raw.ne("")
    iguais_nome = int((comparavel_nome & (f_v1 == f_raw)).sum())
    n = len(wp_u)
    comparacao = [
        ["domínio do link × source_domain (raw)", int(comparavel_dom.sum()), iguais_dom,
         int(comparavel_dom.sum()) - iguais_dom, n - int(comparavel_dom.sum())],
        ["fonte × source_name (raw)", int(comparavel_nome.sum()), iguais_nome,
         int(comparavel_nome.sum()) - iguais_nome, n - int(comparavel_nome.sum())],
    ]
    links_vazios_linhas = int(wp["link"].map(_txt).isna().sum())
    links_vazios_artigos = int(wp_u["link"].map(_txt).isna().sum())
    links = wp_u["link"].map(_txt).dropna()
    repetidos = links.value_counts()
    repetidos = repetidos[repetidos > 1]
    partes = [
        "### Top 30 `fonte`\n\n" + _tabela(["fonte", "artigos"], [[k, int(v)] for k, v in fontes_top.items()]),
        "### Top 30 domínio do link\n\n" + _tabela(["domínio", "artigos"], [[k, int(v)] for k, v in dominios.items()]),
        "### Comparação com a raw_articles\n\n" + _tabela(
            ["comparação", "comparáveis", "iguais", "diferentes", "sem valor (nos dois lados)"], comparacao),
        (f"Links vazios: {links_vazios_linhas} linhas de wordpress e {links_vazios_artigos} artigos distintos.\n"
         f"Links repetidos: {len(repetidos)} links aparecem em mais de um artigo "
         f"({int(repetidos.sum())} artigos ao todo)."),
    ]
    return "\n\n".join(partes)


def secao_3(ctx: dict) -> str:
    """Duplicatas com google_news: por ano, por título e por URL; hora real que o gn não tem."""
    wp, gn, pares = ctx["wp"], ctx["gn"], ctx["pares"]
    wp_u = wp.drop_duplicates("id")
    com_titulo = set(pares.loc[pares["por_titulo"], "id_wp"])
    com_url = set(pares.loc[pares["por_url"], "id_wp"])
    qualquer = com_titulo | com_url
    linhas = []
    for ano, grupo in wp_u.groupby(wp_u["ano"].map(lambda a: "sem data" if _nulo(a) else str(int(a)))):
        ids = set(grupo["id"])
        linhas.append([ano, len(ids), _pct(len(ids & com_titulo), len(ids)),
                       _pct(len(ids & com_url), len(ids)), _pct(len(ids & qualquer), len(ids))])
    total = len(wp_u)
    linhas.append(["total", total, _pct(len(com_titulo), total), _pct(len(com_url), total), _pct(len(qualquer), total)])

    hora_wp = wp_u.set_index("id")["hora_real"]
    hora_gn = gn.drop_duplicates("id").set_index("id")["hora_real"]
    p_hora_wp = pares["id_wp"].map(hora_wp).astype("boolean").fillna(False).astype(bool)
    p_hora_gn = pares["id_gn"].map(hora_gn).astype("boolean").fillna(False).astype(bool)
    so_wp_hora = pares[p_hora_wp & ~p_hora_gn]
    ids_so_wp = so_wp_hora["id_wp"].nunique()
    partes = [
        f"Artigos wordpress com par no google_news: {len(qualquer)} de {total} "
        f"({_pct(len(qualquer), total)}). Por título (mesmo ticker, ±1 dia): {len(com_titulo)}; "
        f"por URL (link × resolved_url): {len(com_url)}.",
        "### Por ano\n\n" + _tabela(["ano", "artigos wordpress", "% com título", "% com URL", "% com algum"], linhas),
        (f"Duplicatas em que o wordpress tem hora real e o google_news não tem: {ids_so_wp} artigos "
         f"({len(so_wp_hora)} pares)."),
    ]
    return "\n\n".join(partes)


def secao_4(ctx: dict) -> str:
    """Hora, fuso, data e momento_pregao; comparação com published_at; N1-A."""
    v1, wp, gn = ctx["v1"], ctx["wp"], ctx["gn"]
    partes = []

    # Fuso: texto termina em -03:00 (horário de São Paulo, sem horário de verão em 2026)
    linhas_fuso = []
    for nome, df in (("wordpress", wp), ("google_news", gn)):
        txt = df["dhp_txt"].dropna().map(str)
        linhas_fuso.append([nome, len(txt), _pct(int(txt.str.endswith("-03:00").sum()), len(txt))])
    partes.append("### Fuso do texto de data_hora_publicacao\n\n" + _tabela(
        ["origem", "linhas com horário", "terminam em -03:00"], linhas_fuso))

    # Comparação com published_at (UTC → SP) em todas as linhas, por origem
    dhp, pub = v1["data_hora_publicacao"], v1["publicado_em_sp"]
    status = np.select(
        [dhp.isna(), pub.isna(), dhp == pub],
        ["sem horário", "sem raw_articles", "igual"],
        default="diferente",
    )
    v1_st = v1.assign(status=status)
    linhas_pub = []
    for origem, grupo in v1_st.groupby("origem"):
        cont = grupo["status"].value_counts()
        linhas_pub.append([origem, len(grupo), int(cont.get("igual", 0)), int(cont.get("diferente", 0)),
                           int(cont.get("sem horário", 0)), int(cont.get("sem raw_articles", 0))])
    partes.append("### Comparação com published_at (UTC → São Paulo), todas as linhas\n\n" + _tabela(
        ["origem", "linhas", "iguais", "diferentes", "sem horário", "sem raw_articles"], linhas_pub))

    # Fuso do wordpress (critério): só linhas com horário e com raw
    wp_cmp = wp[wp["data_hora_publicacao"].notna() & wp["publicado_em_sp"].notna()]
    iguais_wp = int((wp_cmp["data_hora_publicacao"] == wp_cmp["publicado_em_sp"]).sum())
    fuso_pct = iguais_wp / len(wp_cmp) if len(wp_cmp) else None
    ctx["metricas"]["fuso_pct"] = fuso_pct
    partes.append(f"Fuso do wordpress (critério): {iguais_wp} de {len(wp_cmp)} linhas com horário batem com published_at.")

    # Histograma de hora (São Paulo)
    horas_wp = an.horas_suspeitas(wp)
    horas_gn = an.horas_suspeitas(gn)
    hist = pd.DataFrame({
        "wordpress": horas_wp["por_hora"].reindex(range(24), fill_value=0),
        "google_news": horas_gn["por_hora"].reindex(range(24), fill_value=0),
    })
    partes.append("### Histograma da hora (São Paulo)\n\n" + _tabela(
        ["hora", "wordpress", "google_news"], [[f"{h:02d}h", int(r["wordpress"]), int(r["google_news"])]
                                               for h, r in hist.iterrows()]))

    # Horas em ponto suspeitas (wordpress)
    total_wp = horas_wp["total"]
    em_ponto_total = int(horas_wp["em_ponto"].sum())
    linhas_susp = [[hh, n, _pct(n, total_wp)] for hh, n in horas_wp["suspeitas"].items()]
    partes.append(
        f"Wordpress: {em_ponto_total} de {total_wp} horários são em ponto (minuto e segundo zero). "
        "Horas em ponto suspeitas (00:00, 03:00, 04:00, 05:00):\n\n"
        + _tabela(["hora em ponto", "linhas", "% dos horários wordpress"], linhas_susp))

    # Fim de semana, publicação após a coleta, datas futuras, data_publicacao × data SP
    def _pares_base(df):
        ok = df["data_hora_publicacao"].notna()
        return df[ok]

    linhas_fds, linhas_outras = [], []
    for nome, df in (("wordpress", wp), ("google_news", gn)):
        base = _pares_base(df)
        fds = int((base["data_hora_publicacao"].dt.day_of_week >= 5).sum())
        linhas_fds.append([nome, len(base), fds, _pct(fds, len(base))])
        depois = int((base["data_hora_publicacao"] > base["data_hora_coleta"]).sum())
        dia_coleta = base["data_hora_coleta"].dt.tz_localize(None).dt.normalize()
        futuras = int((base["data_publicacao"] > dia_coleta).sum())
        dia_pub = base["data_hora_publicacao"].dt.tz_localize(None).dt.normalize()
        com_data = base["data_publicacao"].notna()
        igual = int(((dia_pub == base["data_publicacao"]) & com_data).sum())
        linhas_outras.append([nome, len(base), depois, futuras, _pct(igual, int(com_data.sum()))])
    partes.append("### Fim de semana\n\n" + _tabela(["origem", "linhas com horário", "sábado ou domingo", "%"], linhas_fds))
    partes.append("### Publicação após a coleta, datas futuras e data_publicacao × data de São Paulo\n\n" + _tabela(
        ["origem", "linhas com horário", "publicação > coleta", "data_publicacao no futuro (> dia da coleta)",
         "data_publicacao = data SP de data_hora_publicacao"], linhas_outras))

    # momento_pregao × horário (informativo)
    com_hora = wp[wp["data_hora_publicacao"].notna()].copy()
    faixa = np.where(com_hora["data_hora_publicacao"].dt.hour < 18, "antes de 18h", "18h ou depois")
    momento = com_hora[COLUNA_MOMENTO].map(lambda v: _txt(v) or "(vazio)")
    cruz = pd.crosstab(momento, faixa)
    partes.append("### momento_pregao × horário (informativo, wordpress; regra das 18h não especificada)\n\n"
                  + _tabela(["momento_pregao", *cruz.columns], [[idx, *map(int, row)] for idx, row
                                                                in zip(cruz.index, cruz.to_numpy())]))

    # N1-A: quantas linhas wordpress com hora real a regra trataria como só data
    precisao = np.select(
        [wp["data_hora_publicacao"].isna(), wp["so_data"]],
        ["sem horário", "meia-noite do Pacífico (só data pela N1-A)"],
        default="hora real",
    )
    partes.append("### Precisão do horário (wordpress)\n\n" + _tabela(
        ["precisão", "linhas", "%"],
        [[k, int(v), _pct(int(v), len(wp))] for k, v in pd.Series(precisao).value_counts().items()]))
    n1a = an.afetados_n1a(wp.drop(columns=["so_data", "hora_real", "julgado", "ano"], errors="ignore"))
    ctx["metricas"]["n1a_wp"] = n1a
    por_ano_n1a = wp.assign(meia=wp["so_data"]).groupby(wp["ano"].map(lambda a: "sem data" if _nulo(a) else str(int(a))))["meia"].sum()
    partes.append(
        f"N1-A (`fontes.aplicar_regra_so_data`) trataria {n1a} linhas wordpress com horário como só data "
        "(meia-noite do Pacífico). Por ano: "
        + ", ".join(f"{a}: {int(n)}" for a, n in por_ano_n1a.items()) + ". Só reportado; a regra não foi alterada.")
    if n1a > 0:
        ctx["pendencias"].append(
            f"N1-A em fonte com hora real: {n1a} linhas wordpress com horário seriam tratadas como só data "
            "(meia-noite do Pacífico) pela `fontes.aplicar_regra_so_data`. Só reportado; a regra não foi alterada.")
    return "\n\n".join(partes)


def secao_5(ctx: dict) -> str:
    """FinBERT: cobertura das probabilidades, model × lang × text_source, score e concordância nas duplicatas."""
    v1, wp, gn, stg, pares = ctx["v1"], ctx["wp"], ctx["gn"], ctx["dados"].stg, ctx["pares"]
    partes = []
    linhas_vazias = []
    for origem, grupo in v1.groupby("origem"):
        vazias = int(grupo["prob_positivo"].isna().sum())
        linhas_vazias.append([origem, len(grupo), vazias, _pct(vazias, len(grupo))])
    partes.append("### Probabilidades vazias (prob_positivo)\n\n" + _tabela(
        ["origem", "linhas", "vazias", "%"], linhas_vazias))
    ctx["metricas"]["finbert_cobertura"] = (
        float(wp["prob_positivo"].notna().mean()) if len(wp) else None
    )

    wp_u = wp.drop_duplicates("id")
    base = wp_u[["id_raw", "lang"]].dropna(subset=["id_raw"]).drop_duplicates("id_raw")
    stg_wp = stg.dropna(subset=["id_raw"]).merge(base, on="id_raw", how="inner")
    cont = (stg_wp.groupby(["model", "lang", "text_source"], dropna=False)["id_raw"]
            .nunique().reset_index(name="artigos").sort_values("artigos", ascending=False))
    linhas_mlt = [[_txt(r["model"]) or "(vazio)", _txt(r["lang"]) or "(vazio)", _txt(r["text_source"]) or "(vazio)",
                   int(r["artigos"])] for _, r in cont.iterrows()]
    sem_stg = int((~base["id_raw"].isin(set(stg["id_raw"].dropna()))).sum())
    partes.append("### model × lang × text_source (artigos wordpress com FinBERT)\n\n" + _tabela(
        ["model", "lang", "text_source", "artigos"], linhas_mlt))
    partes.append(f"Artigos wordpress distintos sem linha em staging_article_sentiment: {sem_stg} de {len(base)}.")

    def _resumo(s: pd.Series) -> list:
        s = s.dropna()
        if s.empty:
            return [0, "—", "—", "—", "—"]
        return [len(s), f"{s.mean():.3f}", f"{s.quantile(0.1):.3f}", f"{s.quantile(0.5):.3f}", f"{s.quantile(0.9):.3f}"]

    partes.append("### Distribuição do score (prob_positivo − prob_negativo)\n\n" + _tabela(
        ["origem", "n", "média", "p10", "p50", "p90"],
        [["wordpress", *_resumo(wp["score"])], ["google_news", *_resumo(gn["score"])]]))

    sc_wp = pares["id_wp"].map(wp.drop_duplicates("id").set_index("id")["score"])
    sc_gn = pares["id_gn"].map(gn.drop_duplicates("id").set_index("id")["score"])
    ok = sc_wp.notna() & sc_gn.notna()
    if ok.sum() >= 2:
        corr = float(np.corrcoef(sc_wp[ok], sc_gn[ok])[0, 1]) if sc_wp[ok].std() > 0 and sc_gn[ok].std() > 0 else None
        mesmo_sinal = float((np.sign(sc_wp[ok]) == np.sign(sc_gn[ok])).mean())
        concord = (f"correlação {corr:.3f}" if corr is not None else "correlação indefinida (sem variação)") \
            + f"; mesmo sinal em {mesmo_sinal * 100:.1f}% dos pares"
    else:
        concord = "menos de 2 pares com score nos dois lados, então não há o que comparar"
    partes.append(f"Concordância do score nas duplicatas ({int(ok.sum())} pares com score nos dois lados): {concord}.")
    return "\n\n".join(partes)


def secao_6(ctx: dict) -> str:
    """Juíza: % julgado; distribuições wp × gn; taxa de 'errada' por ticker."""
    v1, wp, gn = ctx["v1"], ctx["wp"], ctx["gn"]
    partes = []
    linhas_j = []
    for origem, grupo in v1.groupby("origem"):
        julgado = int(grupo["julgado"].sum())
        linhas_j.append([origem, len(grupo), julgado, _pct(julgado, len(grupo))])
    partes.append("### % julgado (papel preenchido)\n\n" + _tabela(["origem", "linhas", "julgadas", "%"], linhas_j))

    for coluna in ("papel", "tipo_conteudo", "evento", "qualidade"):
        def _cont(df):
            return df[coluna].map(lambda v: _txt(v) or "(vazio)").value_counts()
        cw, cg = _cont(wp), _cont(gn)
        todos = sorted(set(cw.index) | set(cg.index), key=lambda k: (-int(cw.get(k, 0)), str(k)))[:25]
        linhas = [[k, int(cw.get(k, 0)), _pct(int(cw.get(k, 0)), len(wp)), int(cg.get(k, 0)),
                   _pct(int(cg.get(k, 0)), len(gn))] for k in todos]
        partes.append(f"### Distribuição de {coluna} (wordpress × google_news; top 25)\n\n" + _tabela(
            [coluna, "wordpress", "% wp", "google_news", "% gn"], linhas))

    def _taxa(df):
        j = df[df["julgado"]]
        return j.groupby("ticker").agg(n=("papel", "size"),
                                       errada=("papel", lambda s: int((s == "errada").sum())))
    tw, tg = _taxa(wp), _taxa(gn)
    ctx["metricas"]["errada_wp"] = (float((wp["papel"] == "errada").sum() / wp["julgado"].sum())
                                    if wp["julgado"].sum() else None)
    ctx["metricas"]["errada_gn"] = (float((gn["papel"] == "errada").sum() / gn["julgado"].sum())
                                    if gn["julgado"].sum() else None)
    juntos = tw.merge(tg, left_index=True, right_index=True, how="outer", suffixes=("_wp", "_gn")).fillna(0)
    juntos["taxa_wp"] = juntos["errada_wp"] / juntos["n_wp"].where(juntos["n_wp"] > 0)
    juntos["taxa_gn"] = juntos["errada_gn"] / juntos["n_gn"].where(juntos["n_gn"] > 0)
    juntos["dif"] = juntos["taxa_wp"] - juntos["taxa_gn"]
    top = juntos[(juntos["n_wp"] > 0) & juntos["dif"].notna()].sort_values("dif", ascending=False).head(15)
    linhas = [[t, int(r["n_wp"]), int(r["errada_wp"]), _pct(int(r["errada_wp"]), int(r["n_wp"])),
               int(r["n_gn"]), int(r["errada_gn"]), _pct(int(r["errada_gn"]), int(r["n_gn"])),
               f"{r['dif'] * 100:+.1f} p.p."] for t, r in top.iterrows()]
    partes.append("### Taxa de 'errada' por ticker (top 15 com maior diferença wordpress − google_news; só julgadas)\n\n"
                  + _tabela(["ticker", "wp julgadas", "wp errada", "taxa wp", "gn julgadas", "gn errada",
                             "taxa gn", "diferença"], linhas))
    ctx["pendencias"].append(PENDENCIA_ERRADA)
    return "\n\n".join(partes)


def secao_7(ctx: dict) -> str:
    """Amostra manual: as linhas do CSV e como preencher."""
    amostra = ctx["amostra"]
    colunas = ["id", "ticker", "data_hora_publicacao", "titulo", "fonte", "papel", "evento", "ticker_correto"]
    presentes = [c for c in colunas if c in amostra.columns]
    linhas = amostra[presentes].values.tolist()
    fonte_txt = ("gerada agora (o CSV foi criado)" if ctx["amostra_nova"]
                 else "lida do CSV já existente (não sobrescrito)")
    return "\n\n".join([
        f"Arquivo: `{ctx['caminho_amostra']}` ({fonte_txt}).",
        "Preencher `ticker_correto` com S (ticker certo), N (ticker errado) ou ? (dúvida). "
        "Vazio = ainda não revisado. O critério exige 27 de 30 com S.",
        _tabela(presentes, linhas),
    ])


def secao_8(ctx: dict, ler) -> str:
    """Impacto com × sem wordpress (em memória, nada gravado): pares com notícia, qtd e tom, e 5 últimos pregões."""
    partes = []
    precos = fontes.ler_tabela("precos", ler=ler)
    cal = calendario.pregoes(precos)
    if not cal:
        raise ValueError("sem pregões na tabela de preços")
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    mudancas = fontes.ler_mudancas(ler)
    composicao = fontes.ler_composicao(ler=ler)
    universo = montar_universo(cal, cadastro, precos, carregar_exclusoes(), composicao)
    setor_de, cnpj_de = mapas_cadastro(cadastro)
    modelo = universo.loc[universo["no_universo"], ["data", "ticker", "universo"]].reset_index(drop=True)
    tickers = sorted(modelo["ticker"].unique())
    setor_de, cnpj_de, _ = mapas_por_empresa(tickers, setor_de, cnpj_de, mudancas)
    empresa_de = {t: ligar_a_cnpj(t, cnpj_de, mudancas)[0] or t for t in tickers}
    linhas = modelo.assign(empresa=modelo["ticker"].map(empresa_de), setor=modelo["ticker"].map(setor_de))
    params = carregar_parametros_experimento()
    partes.append(
        "v1-noticias lida uma vez só (na carga, com wordpress); os dois cenários saem em memória pelo "
        "mesmo tratamento do `ler_noticias` (`tratar_noticias_lidas`). Com = nenhuma origem ignorada. "
        "Sem = tira a origem wordpress (lista explícita, não `origens_ignoradas` do mapa, que pode estar vazia). "
        "Versão de notícias 'todas', "
        f"como no dataset; {len(linhas)} pares pregão × ação do universo; {len(cal)} pregões.")

    bruta = ctx["dados"].v1_bruta
    nots_com = fontes.tratar_noticias_lidas(bruta, ler=ler, origens_ignoradas=[], papeis_ignorados=[])
    nots_sem = _sem_ignoradas(nots_com)

    def _preparar(nots):
        cobertura = (pd.to_datetime(nots["data_publicacao"]).min().normalize()
                     if nots["data_publicacao"].notna().any() else None)
        prep, info = preparar_noticias(nots, cal, cnpj_de, mudancas, "todas", params, None)
        return prep, info, cobertura

    prep_com, info_com, cob_com = _preparar(nots_com)
    prep_sem, info_sem, cob_sem = _preparar(nots_sem)
    partes.append("### Deduplicação e preparo\n\n" + _tabela(
        ["leitura", "lidas", "duplicadas por id", "duplicadas por título", "preparadas", "sem probabilidade"],
        [["com wordpress", info_com["lidas"], info_com["duplicadas_id"], info_com["duplicadas_titulo"],
          info_com["preparadas"], info_com["sem_probabilidade"]],
         ["sem wordpress", info_sem["lidas"], info_sem["duplicadas_id"], info_sem["duplicadas_titulo"],
          info_sem["preparadas"], info_sem["sem_probabilidade"]]]))

    var_com = variaveis_de_noticias(prep_com, linhas, cal, params, noite_aberta=cal[-1], cobertura_inicio=cob_com)
    var_sem = variaveis_de_noticias(prep_sem, linhas, cal, params, noite_aberta=cal[-1], cobertura_inicio=cob_sem)
    ctx["impacto"] = {"com": var_com, "sem": var_sem}
    try:
        partes.append(_impacto_variaveis(linhas, var_com, var_sem))
    except Exception as erro:
        partes.append(f"_Comparação das variáveis não concluída: {type(erro).__name__}: {erro}._")
    try:
        partes.append(_impacto_ultimos_pregoes(bruta, nots_com, cal))
    except Exception as erro:
        partes.append(f"_Leitura dos últimos pregões não concluída: {type(erro).__name__}: {erro}._")
    return "\n\n".join(partes)


def _num(v: float) -> str:
    """Número com três casas; NaN (correlação sem dados ou sem variação) vira 'indefinida'."""
    return "indefinida" if _nulo(v) else f"{v:.3f}"


def _impacto_variaveis(linhas: pd.DataFrame, var_com: pd.DataFrame, var_sem: pd.DataFrame) -> str:
    """Pares com notícia por ano, correlação de qtd e tom, e as 10 maiores diferenças de tom."""
    base = pd.DataFrame({
        "data": pd.to_datetime(linhas["data"]).reset_index(drop=True),
        "ticker": linhas["ticker"].reset_index(drop=True),
        "qtd_com": var_com["noticias_dia_qtd"].to_numpy(),
        "qtd_sem": var_sem["noticias_dia_qtd"].to_numpy(),
        "tom_com": var_com["noticias_dia_tom"].to_numpy(),
        "tom_sem": var_sem["noticias_dia_tom"].to_numpy(),
    })
    base["ano"] = base["data"].dt.year.astype(str)
    por_ano = []
    for ano, g in base.groupby("ano"):
        com = int((g["qtd_com"] > 0).sum())
        sem = int((g["qtd_sem"] > 0).sum())
        por_ano.append([ano, len(g), com, sem, com - sem])
    total_com = int((base["qtd_com"] > 0).sum())
    total_sem = int((base["qtd_sem"] > 0).sum())
    por_ano.append(["total", len(base), total_com, total_sem, total_com - total_sem])
    corr_qtd = base["qtd_com"].corr(base["qtd_sem"])
    corr_tom = base["tom_com"].corr(base["tom_sem"])
    mudou_qtd = int(((base["qtd_com"] != base["qtd_sem"]) & base["qtd_com"].notna() & base["qtd_sem"].notna()).sum())
    par = base.dropna(subset=["tom_com", "tom_sem"]).copy()
    par["diferenca"] = (par["tom_com"] - par["tom_sem"]).abs()
    top = par.sort_values("diferenca", ascending=False).head(10)
    tabela_top = [[r["data"].date().isoformat(), r["ticker"], f"{r['tom_com']:.3f}", f"{r['tom_sem']:.3f}",
                   f"{r['diferenca']:.3f}"] for _, r in top.iterrows()]
    return "\n\n".join([
        "### Pares pregão × ação com ≥1 notícia na janela do dia (noticias_dia_qtd > 0)\n\n" + _tabela(
            ["ano", "pares", "com wordpress", "sem wordpress", "diferença"], por_ano),
        (f"Correlação de noticias_dia_qtd (com × sem): {_num(corr_qtd)}. Linhas com quantidade diferente: {mudou_qtd}.\n"
         f"Correlação de noticias_dia_tom (com × sem): {_num(corr_tom)}."),
        "### 10 maiores diferenças de noticias_dia_tom\n\n" + _tabela(
            ["data", "ticker", "tom com", "tom sem", "diferença absoluta"], tabela_top),
    ])


def _sem_ignoradas(nots: pd.DataFrame) -> pd.DataFrame:
    """Cenário 'sem': tira a origem wordpress (lista explícita; `origens_ignoradas` do mapa pode estar vazia)."""
    return nots[~nots["origem"].isin([WP])].reset_index(drop=True)


def _ate_corte(bruta: pd.DataFrame, nots: pd.DataFrame, ate: pd.Timestamp) -> pd.DataFrame:
    """Recorte em memória igual a `ler_noticias(ate=ate)`: o filtro grosso do SQL
    (`data_publicacao` original ≤ data do corte, por artigo) e o fino em `momento_ref`."""
    ate_sp = pd.Timestamp(ate).tz_convert(fontes.SP)
    data_original = pd.to_datetime(bruta["data_publicacao"], errors="coerce", format="ISO8601")
    ids_ok = set(bruta.loc[data_original.dt.strftime("%Y-%m-%d") <= ate_sp.strftime("%Y-%m-%d"), "id"])
    return nots[nots["id"].isin(ids_ok) & (nots["momento_ref"] <= ate_sp)].reset_index(drop=True)


def _impacto_ultimos_pregoes(bruta: pd.DataFrame, nots_com: pd.DataFrame, cal: list) -> str:
    """Fase 1: nº de notícias por ação nos 5 últimos pregões, com × sem (até o corte da manhã), sem reler o banco."""
    linhas_saida = []
    for d in cal[-5:]:
        com = _ate_corte(bruta, nots_com, calendario.corte_manha(d))
        sem = _sem_ignoradas(com)
        cont_com = com["ticker"].value_counts()
        cont_sem = sem["ticker"].value_counts()
        juntos = pd.concat([cont_com.rename("com"), cont_sem.rename("sem")], axis=1).fillna(0).astype(int)
        juntos["dif"] = juntos["com"] - juntos["sem"]
        maiores = juntos[juntos["dif"] != 0].sort_values("dif", ascending=False).head(3)
        txt = ", ".join(f"{t} (+{int(r['dif'])})" for t, r in maiores.iterrows()) or "nenhuma"
        linhas_saida.append([d.isoformat(), len(com), len(sem), len(com) - len(sem),
                             int((juntos["com"] > 0).sum()), int((juntos["sem"] > 0).sum()), txt])
    return "### Últimos 5 pregões: notícias por ação (leitura até o corte da manhã)\n\n" + _tabela(
        ["pregão", "notícias com", "notícias sem", "diferença", "ações com notícia (com)",
         "ações com notícia (sem)", "maiores diferenças por ação"], linhas_saida)


def secao_9(ctx: dict) -> str:
    """Veredito: critérios, recomendação, pendências e perguntas para a coleta."""
    criterios = an.avaliar_criterios(ctx["metricas"])
    recomendacao = an.recomendar(criterios)
    partes = [
        _tabela(["critério", "valor", "limite", "status"],
                [[c["criterio"], c["valor"], c["limite"], c["status"]] for c in criterios]),
        f"**Recomendação: {recomendacao}.**",
        "### Precisa resolver antes de liberar",
        ("\n".join(f"- {p}" for p in ctx["pendencias"]) if ctx["pendencias"] else "Nenhuma pendência registrada."),
        "### Perguntas para a coleta",
        "\n".join(f"- {p}" for p in PERGUNTAS_COLETA),
    ]
    ctx["recomendacao"] = recomendacao
    return "\n\n".join(partes)


def montar_relatorio(ctx: dict, ler, gerado_em: str) -> str:
    """Cabeçalho e as seções 0 a 9, cada uma tratada por `_seguro`."""
    cabecalho = "\n".join([
        "# Validação da fonte wordpress em v1-noticias (só leitura)",
        f"- Gerado em: {gerado_em}",
        "- Comando: `python -m processamento.diagnostico.wordpress`",
        "> Este relatório só leu o banco (SELECT). Nada foi gravado no banco; a amostra manual é o único arquivo "
        "escrito, e só se ainda não existir.",
    ])
    secoes = [
        _seguro(0, "Prontidão", secao_0, ctx),
        _seguro(1, "Volume por ano, ano-mês, origem e ticker", secao_1, ctx),
        _seguro(2, "Fontes e domínios", secao_2, ctx),
        _seguro(3, "Duplicatas com google_news", secao_3, ctx),
        _seguro(4, "Hora, fuso, data e momento_pregao", secao_4, ctx),
        _seguro(5, "FinBERT", secao_5, ctx),
        _seguro(6, "Juíza (papel, tipo, evento, qualidade)", secao_6, ctx),
        _seguro(7, "Amostra manual", secao_7, ctx),
        _seguro(8, "Impacto com × sem wordpress", secao_8, ctx, ler),
        _seguro(9, "Veredito", secao_9, ctx),
    ]
    return "\n\n".join([cabecalho, *secoes]) + "\n"


def _amostra(wp: pd.DataFrame, caminho: Path, semente: int) -> tuple[pd.DataFrame, bool]:
    """Lê a amostra existente (nunca sobrescreve) ou sorteia e grava uma nova. Devolve (df, criada_agora)."""
    if caminho.exists():
        return pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8"), False
    df = an.sortear_amostra(wp, n=an.AMOSTRA_TAMANHO, semente=semente, max_por_ticker=3)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False, encoding="utf-8", lineterminator="\n")
    return df, True


def _preparar_contexto(dados: Dados, ano_min: int, semente: int, caminho_amostra: Path) -> dict:
    """Recortes que as seções usam: wordpress, google_news, pares de duplicata e a amostra."""
    v1 = dados.v1
    wp = v1[v1["origem"] == WP].copy()
    gn = v1[v1["origem"] == GN].copy()
    ctx = {
        "dados": dados, "v1": v1, "wp": wp, "gn": gn, "ano_min": ano_min,
        "pendencias": [], "metricas": {}, "caminho_amostra": caminho_amostra,
    }
    ctx["pares"] = an.duplicatas_google(
        wp[["id", "ticker", "titulo", "link", "data_publicacao"]],
        gn[["id", "ticker", "titulo", "resolved_url", "data_publicacao"]],
    )
    amostra, nova = _amostra(wp, caminho_amostra, semente)
    ctx["amostra"], ctx["amostra_nova"] = amostra, nova
    s, _, _, n_vazio = an.ler_amostra_preenchida(caminho_amostra)
    ctx["metricas"].update({
        "amostra_s": s,
        "amostra_vazias": n_vazio,
        "amostra_total": len(amostra),
    })
    return ctx


def main(argv=None, ler=None) -> int:
    """Ponto de entrada (`python -m processamento.diagnostico.wordpress`). Devolve 0 em sucesso,
    2 se a configuração do banco estiver incompleta, 3 se a sessão não estiver em somente leitura
    ou a conexão falhar (nada é gravado nesses casos) e 1 se a leitura das tabelas falhar.
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.diagnostico.wordpress",
        description="Validação da fonte wordpress em v1-noticias, só leitura. Gera um relatório em Markdown.",
    )
    parser.add_argument("--saida", type=Path, default=CAMINHO_SAIDA,
                        help="arquivo .md de saída (padrão: docs/validacao_wordpress.md)")
    parser.add_argument("--amostra", type=Path, default=CAMINHO_AMOSTRA,
                        help="CSV da amostra manual (padrão: docs/validacao_wordpress_amostra.csv); "
                             "se existir, não é sobrescrito")
    parser.add_argument("--ano-min", type=int, default=ANO_MIN_PADRAO,
                        help="primeiro ano do veredito (padrão: 2022)")
    parser.add_argument("--semente", type=int, default=SEMENTE_PADRAO,
                        help="semente da amostra (padrão: 42)")
    args = parser.parse_args(argv)

    if ler is None:
        try:
            engine = fontes.criar_engine()
        except fontes.ErroConfiguracao as e:
            print(f"Configuração do banco incompleta: {e}")
            return 2

        def ler(sql, params=None):
            return fontes.executar_leitura(sql, params, engine=engine)

        try:
            fontes.verificar_sessao_somente_leitura(ler)
        except fontes.ErroSomenteLeitura as e:
            print(f"{e}. Nada foi gravado.")
            return 3
        except Exception as e:
            # Não mostra a mensagem original: ela pode conter host ou usuário.
            print(f"Falha ao conectar ao banco ({type(e).__name__}). Nada foi gravado.")
            return 3

    try:
        dados = carregar(ler)
    except Exception as e:
        print(f"Falha ao ler as tabelas ({type(e).__name__}). Nenhum relatório foi gravado.")
        return 1

    ctx = _preparar_contexto(dados, args.ano_min, args.semente, args.amostra)
    gerado_em = datetime.now(ZoneInfo(FUSO)).strftime("%Y-%m-%d %H:%M") + " (America/Sao_Paulo)"
    markdown = montar_relatorio(ctx, ler, gerado_em)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(markdown, encoding="utf-8")
    print(f"Relatório: {args.saida} | amostra: {args.amostra} | recomendação: {ctx.get('recomendacao', '?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
