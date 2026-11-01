"""Funções puras da validação da fonte `wordpress` (v1-noticias).

Nada aqui faz SQL, lê arquivo de banco ou acessa a rede: DataFrames entram, valores saem.
Ausência é None/NaN, nunca 0. Horários de `data_hora_publicacao` chegam já em São Paulo
(`fontes.para_sao_paulo_iso`). A regra "só data" (N1-A) é a de `fontes.aplicar_regra_so_data`,
reaproveitada e não reimplementada.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from processamento import fontes
from processamento.texto_noticias import _nulo, chave_url, dominio, normalizar_titulo

ORIGEM_WORDPRESS = "wordpress"
ORIGEM_GOOGLE = "google_news"
HORAS_SUSPEITAS = ("00:00", "03:00", "04:00", "05:00")
AMOSTRA_TAMANHO = 30
AMOSTRA_MINIMO_S = 27
LIMITE_COBERTURA_FINBERT = 0.99
MARGEM_ERRADA_PP = 0.05
SEM_PAPEL = "(vazio)"


def duplicatas_google(wp: pd.DataFrame, gn: pd.DataFrame, janela_dias: int = 1) -> pd.DataFrame:
    """Pares wordpress × google_news que são a mesma notícia.

    Título: mesmo ticker e mesmo `normalizar_titulo`, com |data_publicacao| até `janela_dias`.
    URL: `link` do wordpress igual a `resolved_url` do google_news (`chave_url`); sem janela de data.
    `wp` precisa de id, ticker, titulo, link, data_publicacao; `gn`, do mesmo mais resolved_url
    (ausente ou vazio = sem URL). Um par por (id_wp, id_gn), com `por_titulo` e `por_url`.
    """
    colunas = ["id_wp", "id_gn", "ticker", "data_wp", "data_gn", "por_titulo", "por_url"]
    if wp.empty or gn.empty:
        return pd.DataFrame(columns=colunas)

    w = pd.DataFrame(
        {
            "id_wp": wp["id"].to_numpy(),
            "ticker": wp["ticker"].to_numpy(),
            "titulo_n": wp["titulo"].map(normalizar_titulo).to_numpy(),
            "url_n": wp["link"].map(chave_url).to_numpy(),
            "data_wp": pd.to_datetime(wp["data_publicacao"]).to_numpy(),
        }
    )
    url_gn = gn["resolved_url"] if "resolved_url" in gn.columns else pd.Series(None, index=gn.index)
    g = pd.DataFrame(
        {
            "id_gn": gn["id"].to_numpy(),
            "ticker": gn["ticker"].to_numpy(),
            "titulo_n": gn["titulo"].map(normalizar_titulo).to_numpy(),
            "url_n": url_gn.map(chave_url).to_numpy(),
            "data_gn": pd.to_datetime(gn["data_publicacao"]).to_numpy(),
        }
    )

    # Título: mesmo ticker, título normalizado igual e datas a até `janela_dias` de distância
    tw = w.dropna(subset=["titulo_n"])
    tg = g.dropna(subset=["titulo_n"])
    por_titulo = tw.merge(tg, on=["ticker", "titulo_n"], suffixes=("_wp", "_gn"))
    dias = (pd.to_datetime(por_titulo["data_wp"]) - pd.to_datetime(por_titulo["data_gn"])).abs()
    por_titulo = por_titulo[dias <= pd.Timedelta(days=janela_dias)]
    por_titulo = por_titulo.assign(por_titulo=True, por_url=False)[
        ["id_wp", "id_gn", "ticker", "data_wp", "data_gn", "por_titulo", "por_url"]
    ]

    # URL: mesmo link normalizado, sem janela de data
    uw = w.dropna(subset=["url_n"])
    ug = g.dropna(subset=["url_n"])
    por_url = uw.merge(ug, on="url_n", suffixes=("_wp", "_gn"))
    por_url = por_url.assign(ticker=por_url["ticker_wp"], por_titulo=False, por_url=True)[
        ["id_wp", "id_gn", "ticker", "data_wp", "data_gn", "por_titulo", "por_url"]
    ]

    juntos = pd.concat([por_titulo, por_url], ignore_index=True)
    if juntos.empty:
        return pd.DataFrame(columns=colunas)
    juntos = juntos.assign(
        por_titulo=juntos["por_titulo"].astype(bool), por_url=juntos["por_url"].astype(bool)
    )
    agregado = juntos.groupby(["id_wp", "id_gn"], sort=True).agg(
        ticker=("ticker", "first"),
        data_wp=("data_wp", "first"),
        data_gn=("data_gn", "first"),
        por_titulo=("por_titulo", "any"),
        por_url=("por_url", "any"),
    )
    return agregado.reset_index()[colunas]


def horas_suspeitas(df: pd.DataFrame) -> dict:
    """Contagens de horário de `df["data_hora_publicacao"]` (tz-aware, São Paulo; NaT fica de fora).

    Devolve `por_hora` (hora 0..23 -> n), `por_minuto` (HH:MM -> n, do mais frequente) e `em_ponto`
    (HH:00 -> n, só para os de minuto zero) e `suspeitas` (as de HORAS_SUSPEITAS -> n em ponto).
    """
    instantes = pd.to_datetime(df["data_hora_publicacao"]).dropna()
    por_hora = instantes.dt.hour.value_counts().sort_index()
    minuto = instantes.dt.strftime("%H:%M")
    por_minuto = minuto.value_counts()
    em_ponto_mask = (instantes.dt.minute == 0) & (instantes.dt.second == 0)
    em_ponto = instantes[em_ponto_mask].dt.strftime("%H:00").value_counts().sort_index()
    suspeitas = {hh: int(em_ponto.get(hh, 0)) for hh in HORAS_SUSPEITAS}
    return {
        "total": int(len(instantes)),
        "por_hora": por_hora.astype(int),
        "por_minuto": por_minuto.astype(int),
        "em_ponto": em_ponto.astype(int),
        "suspeitas": suspeitas,
    }


def afetados_n1a(df: pd.DataFrame) -> int:
    """Quantas linhas a regra N1-A (`fontes.aplicar_regra_so_data`) marcaria como "só data".

    Usa `data_hora_publicacao` (tz-aware, São Paulo) e `data_publicacao`. Não grava nada.
    """
    base = df.drop(columns=["precisao_hora", "momento_ref"], errors="ignore")
    base = base.assign(data_publicacao=pd.to_datetime(base["data_publicacao"]))
    marcado = fontes.aplicar_regra_so_data(base)
    return int((marcado["precisao_hora"] == "meia_noite_pacifico").sum())


def sortear_amostra(
    wp: pd.DataFrame,
    n: int = AMOSTRA_TAMANHO,
    semente: int = 42,
    max_por_ticker: int = 3,
) -> pd.DataFrame:
    """Amostra estratificada por (ano, papel) para revisão manual; reprodutível com a mesma semente.

    Cada estrato (ano de `data_publicacao` × papel; papel vazio vira "(vazio)") é embaralhado com
    a semente e os estratos são percorridos em rodízio, um item por vez, para que os papéis raros
    ('errada', 'mencao') entrem. Um ticker aparece no máximo `max_por_ticker` vezes.
    Colunas: id, ticker, data_hora_publicacao, titulo, fonte, link, papel, evento, ticker_correto (vazia).
    """
    colunas = ["id", "ticker", "data_hora_publicacao", "titulo", "fonte", "link", "papel", "evento", "ticker_correto"]
    if wp.empty:
        return pd.DataFrame(columns=colunas)
    base = wp.reset_index(drop=True)
    ano = pd.to_datetime(base["data_publicacao"]).dt.year.astype("Int64").astype(str)
    papel = base["papel"].map(lambda v: SEM_PAPEL if _nulo(v) or not str(v).strip() else str(v))
    estrato = pd.DataFrame({"ano": ano, "papel": papel})

    rng = np.random.default_rng(semente)
    filas: dict[tuple, list[int]] = {}
    for chave, grupo in estrato.groupby(["ano", "papel"], sort=True):
        filas[chave] = [int(i) for i in rng.permutation(grupo.index.to_numpy())]

    escolhidos: list[int] = []
    por_ticker: Counter = Counter()
    while len(escolhidos) < n and any(filas.values()):
        for chave in sorted(filas):
            if len(escolhidos) >= n:
                break
            fila = filas[chave]
            while fila:
                idx = fila.pop(0)
                ticker = base.at[idx, "ticker"]
                if por_ticker[ticker] < max_por_ticker:
                    escolhidos.append(idx)
                    por_ticker[ticker] += 1
                    break

    escolhidas = base.loc[escolhidos].copy()
    escolhidas["_ordem"] = pd.to_datetime(escolhidas["data_publicacao"])
    escolhidas = escolhidas.sort_values(["_ordem", "id"]).reset_index(drop=True)
    saida = pd.DataFrame(
        {
            "id": escolhidas["id"],
            "ticker": escolhidas["ticker"],
            "data_hora_publicacao": escolhidas["data_hora_publicacao"].map(_texto_instante),
            "titulo": escolhidas["titulo"],
            "fonte": escolhidas["fonte"],
            "link": escolhidas["link"],
            "papel": escolhidas["papel"].map(lambda v: "" if _nulo(v) else str(v)),
            "evento": escolhidas["evento"].map(lambda v: "" if _nulo(v) else str(v)),
            "ticker_correto": "",
        }
    )
    return saida[colunas]


def _texto_instante(v) -> str:
    """Horário como texto ISO com fuso; ausência vira texto vazio."""
    if _nulo(v):
        return ""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def ler_amostra_preenchida(caminho) -> tuple[int, int, int, int]:
    """Conta os veredictos do CSV da amostra na coluna `ticker_correto`.

    Devolve (n_s, n_n, n_interrog, n_vazio): 'S' = ticker correto, 'N' = errado, '?' = dúvida,
    vazio = ainda não revisado. Levanta FileNotFoundError se o arquivo não existir.
    """
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8")
    veredito = df["ticker_correto"].str.strip().str.upper()
    n_s = int((veredito == "S").sum())
    n_n = int((veredito == "N").sum())
    n_i = int((veredito == "?").sum())
    n_v = int((veredito == "").sum())
    return n_s, n_n, n_i, n_v


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def avaliar_criterios(metricas: dict) -> list[dict]:
    """Critérios de liberação, com status OK, FALHA ou PENDENTE.

    Chaves de `metricas` (ausente ou None = PENDENTE):
      fuso_pct (fração 0..1 das linhas com horário que batem com published_at),
      finbert_cobertura (fração 0..1 do wordpress com probabilidades),
      errada_wp / errada_gn (fração de 'errada' entre as julgadas),
      anos_faltando (lista de anos >= ano_min com wordpress em raw_articles e sem wordpress na v1),
      n1a_wp (nº de linhas wordpress com horário que a N1-A trataria como só data),
      amostra_s / amostra_vazias / amostra_total (vereditos 'S' e linhas ainda não revisadas do CSV).
    Cada item: criterio, valor, limite, status, chave (usada por `recomendar`).
    """
    criterios: list[dict] = []

    def add(chave: str, criterio: str, valor_txt: str, limite: str, status: str) -> None:
        criterios.append({"chave": chave, "criterio": criterio, "valor": valor_txt, "limite": limite, "status": status})

    fuso = metricas.get("fuso_pct")
    if fuso is None:
        add("fuso", "Fuso: 100% das linhas batem com published_at (UTC→SP)", "—", "100%", "PENDENTE")
    else:
        add("fuso", "Fuso: 100% das linhas batem com published_at (UTC→SP)", _fmt_pct(fuso), "100%",
            "OK" if fuso >= 1.0 else "FALHA")

    cobertura = metricas.get("finbert_cobertura")
    if cobertura is None:
        add("finbert", "Cobertura FinBERT (wordpress) ≥ 99%", "—", "≥ 99%", "PENDENTE")
    else:
        add("finbert", "Cobertura FinBERT (wordpress) ≥ 99%", _fmt_pct(cobertura), "≥ 99%",
            "OK" if cobertura >= LIMITE_COBERTURA_FINBERT else "FALHA")

    errada_wp = metricas.get("errada_wp")
    errada_gn = metricas.get("errada_gn")
    limite_errada = f"≤ google_news + {MARGEM_ERRADA_PP * 100:.0f} p.p."
    if errada_wp is None or errada_gn is None:
        add("errada", "Taxa de papel='errada' (wordpress) ≤ google_news + 5 p.p.", "—", limite_errada, "PENDENTE")
    else:
        valor = f"wordpress {_fmt_pct(errada_wp)} × google_news {_fmt_pct(errada_gn)}"
        add("errada", "Taxa de papel='errada' (wordpress) ≤ google_news + 5 p.p.", valor, limite_errada,
            "OK" if errada_wp <= errada_gn + MARGEM_ERRADA_PP else "FALHA")

    anos = metricas.get("anos_faltando")
    if anos is None:
        add("anos", "Anos com wordpress em raw_articles presentes na v1-noticias (≥ ano_min)", "—", "nenhum faltando",
            "PENDENTE")
    else:
        valor = "nenhum" if not anos else ", ".join(str(a) for a in sorted(anos))
        add("anos", "Anos com wordpress em raw_articles presentes na v1-noticias (≥ ano_min)", valor,
            "nenhum faltando", "OK" if not anos else "FALHA")

    n1a = metricas.get("n1a_wp")
    if n1a is None:
        add("n1a", "N1-A não trata fonte com hora real (wordpress) como só data", "—", "0 linhas", "PENDENTE")
    else:
        add("n1a", "N1-A não trata fonte com hora real (wordpress) como só data", str(int(n1a)), "0 linhas",
            "OK" if n1a == 0 else "FALHA")

    s = metricas.get("amostra_s")
    vazias = metricas.get("amostra_vazias")
    total = metricas.get("amostra_total")
    limite_amostra = f"≥ {AMOSTRA_MINIMO_S}/{AMOSTRA_TAMANHO} 'S'"
    if s is None or vazias is None or total is None or total == 0:
        add("amostra", "Amostra manual ≥ 27/30 'S'", "não preenchida", limite_amostra, "PENDENTE")
    elif vazias > 0:
        add("amostra", "Amostra manual ≥ 27/30 'S'", f"{s}/{total} 'S', {vazias} sem revisão", limite_amostra,
            "PENDENTE")
    else:
        add("amostra", "Amostra manual ≥ 27/30 'S'", f"{s}/{total} 'S'", limite_amostra,
            "OK" if s >= AMOSTRA_MINIMO_S else "FALHA")
    return criterios


def recomendar(criterios: list[dict]) -> str:
    """Recomendação a partir de `avaliar_criterios`.

    Tudo OK (sem falha nem pendente) → "liberar". Só falha de 'errada' ou 'n1a' (com pendentes
    eventuais) → "liberar só depois de resolver os pendentes". Qualquer outra falha → "não liberar".
    """
    falhas = [c for c in criterios if c["status"] == "FALHA"]
    pendentes = [c for c in criterios if c["status"] == "PENDENTE"]
    if not falhas and not pendentes:
        return "liberar"
    if all(c["chave"] in ("errada", "n1a") for c in falhas):
        return "liberar só depois de resolver os pendentes"
    return "não liberar"
