"""Métricas do experimento: top k por pregão, AUC, faixa do acaso, bootstrap e calibração (plano da etapa 6, fase 3).

Cada pregão t tem as candidatas (linhas com o alvo preenchido). O score ordena o dia (maior primeiro,
desempate por ticker). Funções puras: nada de banco, rede ou arquivo. Ausência é NaN/None, nunca 0.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

RET_T1 = "ret_t1"
RET_IBOV_T1 = "ret_ibov_t1"


def _candidatos(df: pd.DataFrame, coluna_alvo: str) -> pd.DataFrame:
    """Linhas com o alvo preenchido (as que entram no ranking)."""
    return df.loc[df[coluna_alvo].notna()]


def _media(valores: pd.Series) -> float | None:
    return float(valores.mean()) if len(valores) else None


def _diferenca(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def ordenar_no_dia(df: pd.DataFrame, coluna_score: str = "score") -> pd.DataFrame:
    """Ordena por data (asc), score (desc) e ticker (asc); acrescenta `posicao` 1..n dentro de cada data."""
    if df[coluna_score].isna().any():
        raise ValueError(f"score ausente em {coluna_score}: ausência não entra no ranking")
    ordenado = df.sort_values(
        ["data", coluna_score, "ticker"], ascending=[True, False, True]
    ).reset_index(drop=True)
    ordenado["posicao"] = ordenado.groupby("data").cumcount() + 1
    return ordenado


def resumo_diario(
    df: pd.DataFrame,
    k: int,
    *,
    coluna_alvo: str = "alvo",
    coluna_score: str = "score",
    com_retorno: bool = True,
) -> pd.DataFrame:
    """Acertos do top k e dos k últimos de cada pregão (só dias com pelo menos k candidatas)."""
    ordenado = ordenar_no_dia(_candidatos(df, coluna_alvo), coluna_score)
    linhas = []
    for data, grupo in ordenado.groupby("data", sort=True):
        n = len(grupo)
        if n < k:
            continue
        top = grupo.iloc[:k]
        ultimos = grupo.iloc[n - k:]
        linha = {
            "data": data,
            "n_candidatos": n,
            "acertos_top": int(top[coluna_alvo].sum()),
            "acerto_top": top[coluna_alvo].sum() / k,
            "acertos_ultimos": int(ultimos[coluna_alvo].sum()),
            "acerto_ultimos": ultimos[coluna_alvo].sum() / k,
        }
        if com_retorno:
            ret_ibov = float(grupo[RET_IBOV_T1].iloc[0])
            ret_top = float(top[RET_T1].mean())
            ret_ultimos = float(ultimos[RET_T1].mean())
            linha.update(
                ret_top=ret_top,
                ret_ultimos=ret_ultimos,
                ret_ibov=ret_ibov,
                excesso_top=ret_top - ret_ibov,
                excesso_ultimos=ret_ultimos - ret_ibov,
            )
        linhas.append(linha)

    colunas = ["data", "n_candidatos", "acertos_top", "acerto_top", "acertos_ultimos", "acerto_ultimos"]
    if com_retorno:
        colunas += ["ret_top", "ret_ultimos", "ret_ibov", "excesso_top", "excesso_ultimos"]
    return pd.DataFrame(linhas, columns=colunas)


def metricas_periodo(diario: pd.DataFrame, com_retorno: bool = True) -> dict:
    """Médias do período a partir do resumo diário (taxa do top k, dos últimos e a diferença)."""
    taxa = _media(diario["acerto_top"])
    ultimos = _media(diario["acerto_ultimos"])
    saida = {
        "n_dias": int(len(diario)),
        "taxa_acerto": taxa,
        "taxa_ultimos": ultimos,
        "dif_top_ultimos": _diferenca(taxa, ultimos),
    }
    if com_retorno:
        excesso = _media(diario["excesso_top"])
        excesso_ultimos = _media(diario["excesso_ultimos"])
        saida.update(
            excesso_medio=excesso,
            excesso_ultimos=excesso_ultimos,
            dif_excesso=_diferenca(excesso, excesso_ultimos),
        )
    return saida


def auc_geral(df: pd.DataFrame, coluna_alvo: str = "alvo", coluna_score: str = "score") -> float | None:
    """AUC sobre todas as candidatas. Uma classe só (ou nenhuma candidata) devolve None."""
    cand = _candidatos(df, coluna_alvo)
    y = cand[coluna_alvo].to_numpy().astype(int)
    if y.size == 0 or np.unique(y).size < 2:
        return None
    return float(roc_auc_score(y, cand[coluna_score].to_numpy(float)))


def auc_por_pregao(df: pd.DataFrame, coluna_alvo: str = "alvo", coluna_score: str = "score") -> pd.Series:
    """AUC de cada pregão (índice data). Pregão com uma classe só fica fora."""
    cand = _candidatos(df, coluna_alvo)
    valores = {}
    for data, grupo in cand.groupby("data", sort=True):
        auc = auc_geral(grupo, coluna_alvo, coluna_score)
        if auc is not None:
            valores[data] = auc
    return pd.Series(valores, dtype=float, name="auc").rename_axis("data")


def faixa_do_acaso(
    df: pd.DataFrame,
    k: int,
    n_sorteios: int,
    semente: int,
    *,
    coluna_alvo: str = "alvo",
    com_retorno: bool = True,
) -> dict:
    """Distribuição do top k escolhido ao acaso (S sorteios por pregão, mesmas candidatas do ranking)."""
    rng = np.random.default_rng(semente)
    cand = _candidatos(df, coluna_alvo)
    acerto = np.zeros(n_sorteios)
    excesso = np.zeros(n_sorteios)
    n_dias = 0
    for _, grupo in cand.groupby("data", sort=True):
        if len(grupo) < k:
            continue
        grupo = grupo.sort_values("ticker", kind="stable")
        alvo = grupo[coluna_alvo].to_numpy(float)
        u = rng.random((n_sorteios, len(alvo)))
        esc = np.argsort(u, axis=1, kind="stable")[:, :k]
        acerto += alvo[esc].sum(axis=1) / k
        if com_retorno:
            ret = grupo[RET_T1].to_numpy(float)
            ret_ibov = float(grupo[RET_IBOV_T1].iloc[0])
            excesso += ret[esc].mean(axis=1) - ret_ibov
        n_dias += 1

    if n_dias == 0:
        return {
            "media": None, "p2_5": None, "p97_5": None,
            "n_sorteios": n_sorteios, "n_dias": 0,
            "excesso_media": None, "excesso_p2_5": None, "excesso_p97_5": None,
            "distribuicao_acerto": np.array([]), "distribuicao_excesso": None,
        }

    dist_acerto = acerto / n_dias
    p_acerto = np.percentile(dist_acerto, [2.5, 97.5])
    saida = {
        "media": float(dist_acerto.mean()),
        "p2_5": float(p_acerto[0]),
        "p97_5": float(p_acerto[1]),
        "n_sorteios": n_sorteios,
        "n_dias": n_dias,
        "excesso_media": None,
        "excesso_p2_5": None,
        "excesso_p97_5": None,
        "distribuicao_acerto": dist_acerto,
        "distribuicao_excesso": None,
    }
    if com_retorno:
        dist_excesso = excesso / n_dias
        p_excesso = np.percentile(dist_excesso, [2.5, 97.5])
        saida.update(
            excesso_media=float(dist_excesso.mean()),
            excesso_p2_5=float(p_excesso[0]),
            excesso_p97_5=float(p_excesso[1]),
            distribuicao_excesso=dist_excesso,
        )
    return saida


def ic_bootstrap_blocos(
    valores, tamanho_bloco: int, n_reamostragens: int, semente: int
) -> tuple[float | None, float | None]:
    """IC 95% da média por bootstrap circular de blocos (blocos de pregões consecutivos)."""
    v = np.asarray(valores, dtype=float)
    n = v.size
    if n == 0:
        return (None, None)
    rng = np.random.default_rng(semente)
    L = min(tamanho_bloco, n)
    m = math.ceil(n / L)
    estatisticas = np.empty(n_reamostragens)
    for b in range(n_reamostragens):
        ini = rng.integers(0, n, size=m)
        idx = ((ini[:, None] + np.arange(L)) % n).ravel()[:n]
        estatisticas[b] = v[idx].mean()
    lo, hi = np.percentile(estatisticas, [2.5, 97.5])
    return (float(lo), float(hi))


def diferenca_pareada(a: pd.Series, b: pd.Series) -> pd.Series:
    """a − b sobre as datas em comum (junção interna)."""
    a_alinhado, b_alinhado = a.align(b, join="inner")
    return a_alinhado - b_alinhado


def por_ano(diario: pd.DataFrame, com_retorno: bool = True) -> pd.DataFrame:
    """Taxa de acerto do top k (e excesso médio) por ano do calendário."""
    colunas = ["ano", "n_dias", "taxa_acerto"] + (["excesso_medio"] if com_retorno else [])
    ano = pd.to_datetime(diario["data"]).dt.year.rename("ano")
    linhas = []
    for valor, grupo in diario.groupby(ano, sort=True):
        linha = {
            "ano": int(valor),
            "n_dias": int(len(grupo)),
            "taxa_acerto": _media(grupo["acerto_top"]),
        }
        if com_retorno:
            linha["excesso_medio"] = _media(grupo["excesso_top"])
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=colunas)


def sensibilidade_ultimo_ano(diario: pd.DataFrame) -> dict:
    """Último ano (datas após a última menos 1 ano) contra os anteriores."""
    if diario.empty:
        return {"corte": None, "ultimo_ano": None, "anteriores": None}
    datas = pd.to_datetime(diario["data"])
    corte = datas.max() - pd.DateOffset(years=1)
    com_retorno = "excesso_top" in diario.columns
    recente = (datas > corte).to_numpy()
    ultimo = diario.loc[recente]
    anteriores = diario.loc[~recente]
    return {
        "corte": corte.strftime("%Y-%m-%d"),
        "ultimo_ano": metricas_periodo(ultimo, com_retorno) if len(ultimo) else None,
        "anteriores": metricas_periodo(anteriores, com_retorno) if len(anteriores) else None,
    }


def linhas_abertura_valida(df: pd.DataFrame) -> pd.DataFrame:
    """Só os pregões em que a abertura do IBOV é válida (alvo_abertura_valido == 1) e o alvo existe."""
    mascara = ((df["alvo_abertura_valido"] == 1) & df["alvo_abertura"].notna()).to_numpy()
    return df.loc[mascara]


def calibracao(prob, alvo, bins: int, ece_maximo: float, linhas_minimas: int) -> dict:
    """ECE e Brier de probabilidades em `bins` faixas iguais; aprovada se linhas e ECE passarem."""
    p = np.asarray(prob, dtype=float)
    y = np.asarray(alvo, dtype=float)
    n = p.size
    faixa = np.minimum(np.floor(p * bins).astype(int), bins - 1)
    ece = 0.0
    tabela = []
    for b in range(bins):
        mascara = faixa == b
        nb = int(mascara.sum())
        if nb == 0:
            continue
        media_prevista = float(p[mascara].mean())
        media_real = float(y[mascara].mean())
        ece += nb / n * abs(media_prevista - media_real)
        tabela.append({"bin": b, "n": nb, "media_prevista": media_prevista, "media_real": media_real})
    brier = float(((p - y) ** 2).mean()) if n else None
    return {
        "ece": ece if n else None,
        "brier": brier,
        "n": int(n),
        "aprovada": bool(n >= linhas_minimas and n > 0 and ece <= ece_maximo),
        "tabela": tabela,
    }


def comparar_com_acaso(taxa: float, faixa: dict) -> str:
    """'acima' se a taxa passa do percentil 97,5 do acaso, 'abaixo' se fica sob o 2,5, senão 'dentro'."""
    if taxa > faixa["p97_5"]:
        return "acima"
    if taxa < faixa["p2_5"]:
        return "abaixo"
    return "dentro"
