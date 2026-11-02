"""Variáveis de notícias do dataset do experimento (seção 7.3; etapa 5, fase 4).

Funções puras: DataFrames entram, DataFrame sai. Nenhuma acessa banco ou rede.
Entrada: notícias preparadas (COLUNAS_PREPARADAS da fase 3), todas com janela "dia". Ausência = NaN;
a única exceção é `noticias_dia_qtd = 0` em data coberta sem notícia no dia (E4). Nunca usa pregão de t+1.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from processamento.experimento.parametros import ParametrosExperimento, mascara_sem_coleta

COLUNAS_NOTICIAS = [
    "noticias_dia_qtd",
    "noticias_dia_tom",
    "noticias_dia_extremo",
    "mudanca_tom",
    "tom_setor",
    "tom_mercado",
]


def extremo(scores: pd.Series) -> float:
    """Score de maior módulo, com sinal; empate de módulo = média dos empatados; sem valor = NaN."""
    valores = pd.to_numeric(scores, errors="coerce").dropna()
    if valores.empty:
        return float("nan")
    modulo = valores.abs()
    return float(valores[modulo == modulo.max()].mean())


def _grade(serie: pd.Series, cal_ts: pd.DatetimeIndex) -> pd.DataFrame:
    """Série indexada por (pregão, empresa) vira grade pregão × empresa alinhada ao calendário."""
    return serie.unstack("empresa").reindex(cal_ts)


def _consultar(grade: pd.DataFrame, datas: pd.DatetimeIndex, empresas: pd.Series) -> np.ndarray:
    """Valor da grade para cada linha; NaN se a data ou a empresa não estiver na grade."""
    i = grade.index.get_indexer(datas)
    j = grade.columns.get_indexer(pd.Index(empresas))
    valores = grade.to_numpy(dtype=float)
    saida = np.full(len(datas), np.nan)
    ok = (i >= 0) & (j >= 0)
    saida[ok] = valores[i[ok], j[ok]]
    return saida


def _media_base(
    nots: pd.DataFrame,
    cal_ts: pd.DatetimeIndex,
    pregoes: int,
    minimo: int,
    cobertura: pd.Timestamp | None,
    periodos_sem_coleta: tuple = (),
) -> pd.DataFrame:
    """Média dos scores da empresa nos `pregoes` pregões ANTERIORES a cada data (sem t); NaN fora das regras.

    Como no início da cobertura, a base exige a janela inteira coberta: se tocar um período sem coleta, fica NaN.
    """
    por = nots.groupby(["pregao_ref", "empresa"])["score"].agg(soma="sum", n="count")
    soma = por["soma"].unstack("empresa").reindex(cal_ts).fillna(0.0)
    contagem = por["n"].unstack("empresa").reindex(cal_ts).fillna(0.0)
    soma_janela = soma.rolling(pregoes, min_periods=pregoes).sum().shift(1)
    n_janela = contagem.rolling(pregoes, min_periods=pregoes).sum().shift(1)
    media = soma_janela / n_janela.where(n_janela >= minimo)
    if cobertura is not None:
        inicio_janela = pd.Series(cal_ts.to_numpy(), index=cal_ts).shift(pregoes)
        media = media.where(inicio_janela >= cobertura, axis=0)
    sem_coleta = pd.Series(mascara_sem_coleta(cal_ts, periodos_sem_coleta).astype(float), index=cal_ts)
    toca_periodo = sem_coleta.rolling(pregoes, min_periods=1).max().shift(1) > 0
    return media.where(~toca_periodo, axis=0)


def _tom_setor(datas: pd.DatetimeIndex, empresas: pd.Series, setores: pd.Series, tom: np.ndarray) -> np.ndarray:
    """Média do tom do dia das OUTRAS empresas do setor presentes na data (cada empresa vale 1 voto)."""
    base = pd.DataFrame(
        {"data": datas, "empresa": empresas.to_numpy(), "setor": setores.to_numpy(), "tom": tom}
    )
    unicas = base.drop_duplicates(["data", "empresa"])
    com_tom = unicas[unicas["tom"].notna() & unicas["setor"].notna()]
    grupo = com_tom.groupby(["data", "setor"])["tom"].agg(soma="sum", n="count").reset_index()
    juntas = base.merge(grupo, on=["data", "setor"], how="left")
    propria = juntas["tom"].notna().astype(float)
    n_outras = juntas["n"] - propria
    soma_outras = juntas["soma"] - juntas["tom"].fillna(0.0)
    return (soma_outras / n_outras).where(n_outras > 0).to_numpy(dtype=float)


def _tom_mercado(dia: pd.DataFrame, datas: pd.DatetimeIndex, empresas: pd.Series) -> np.ndarray:
    """Média dos scores do dia de cada data, só das empresas presentes naquela data; cada id conta uma vez."""
    presentes = pd.DataFrame({"data": datas, "empresa": empresas.to_numpy()}).drop_duplicates()
    juntas = dia.rename(columns={"pregao_ref": "data"}).merge(presentes, on=["data", "empresa"])
    unicas = juntas.drop_duplicates(["data", "id"])
    medias = unicas.groupby("data")["score"].mean()
    return medias.reindex(datas).to_numpy(dtype=float)


def variaveis_de_noticias(
    nots: pd.DataFrame,
    linhas: pd.DataFrame,
    cal: list[date],
    params: ParametrosExperimento,
    *,
    noite_aberta: date | None,
    cobertura_inicio: pd.Timestamp | None,
) -> pd.DataFrame:
    """Acrescenta as 6 colunas de notícias às `linhas` (data, ticker, empresa, setor), na mesma ordem.

    `noite_aberta`: a janela do dia dessa data ainda não fechou; as 6 colunas ficam vazias.
    `cobertura_inicio`: antes dela não há notícias no banco; todas as colunas ficam vazias.
    `params.periodos_sem_coleta`: pregões sem coleta também ficam vazios (ausência, nunca `qtd = 0`).
    """
    cal_ts = pd.DatetimeIndex(pd.to_datetime(list(cal))).sort_values()
    nots = nots.assign(
        pregao_ref=pd.to_datetime(nots["pregao_ref"]).dt.normalize(),
        score=pd.to_numeric(nots["score"]),
    )
    linhas = linhas.reset_index(drop=True)
    n = len(linhas)
    datas = pd.DatetimeIndex(pd.to_datetime(linhas["data"]))
    empresas = linhas["empresa"]

    dia_df = nots[nots["janela"] == "dia"]
    grupos_dia = dia_df.groupby(["pregao_ref", "empresa"])["score"]
    qtd_g = _grade(grupos_dia.size(), cal_ts)
    tom_g = _grade(grupos_dia.mean(), cal_ts)
    ext_g = _grade(grupos_dia.apply(extremo), cal_ts)

    tom = _consultar(tom_g, datas, empresas)
    qtd = _consultar(qtd_g, datas, empresas)
    dentro_do_calendario = cal_ts.get_indexer(datas) >= 0
    qtd = np.where(dentro_do_calendario & np.isnan(qtd), 0.0, qtd)
    extremo_dia = _consultar(ext_g, datas, empresas)

    base = _media_base(
        nots, cal_ts, params.mudanca_tom_pregoes, params.mudanca_tom_minimo, cobertura_inicio,
        params.periodos_sem_coleta,
    )
    mudanca = tom - _consultar(base, datas, empresas)

    tom_setor = _tom_setor(datas, empresas, linhas["setor"], tom)
    tom_mercado = _tom_mercado(dia_df[["pregao_ref", "empresa", "id", "score"]], datas, empresas)

    coberta = np.ones(n, dtype=bool) if cobertura_inicio is None else np.asarray(datas >= cobertura_inicio)
    coberta = coberta & ~mascara_sem_coleta(datas, params.periodos_sem_coleta)
    noite_fechada = (
        np.zeros(n, dtype=bool) if noite_aberta is None else np.asarray(datas == pd.Timestamp(noite_aberta))
    )

    resultado = linhas.copy()
    valores = {
        "noticias_dia_qtd": qtd,
        "noticias_dia_tom": tom,
        "noticias_dia_extremo": extremo_dia,
        "mudanca_tom": mudanca,
        "tom_setor": tom_setor,
        "tom_mercado": tom_mercado,
    }
    for coluna, valor in valores.items():
        valor = np.asarray(valor, dtype=float).copy()
        valor[~coberta] = np.nan
        valor[noite_fechada] = np.nan
        resultado[coluna] = valor
    return resultado
