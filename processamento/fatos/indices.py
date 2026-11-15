"""Rentabilidade de CDI, IPCA e índices de referência nas janelas da fase 1 (seção 5 da especificação).

CDI é taxa diária: a rentabilidade da janela é o produto das taxas com data em [base, t).
IPCA é mensal e fechado: só entram os meses conhecidos (sem rateio por dia). Funções puras.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    Grade,
    grade_de_precos,
    indice_pregoes,
    montar_grade,
    variacao,
)

INDICES = ("CDI", "IPCA", "IDIV", "SMLL", "IFIX", "IVVB11")
_PONTOS = ("IDIV", "SMLL", "IFIX")


def grade_de_indices(indices: pd.DataFrame, cal: list, nomes: tuple[str, ...]) -> pd.DataFrame:
    """Matriz pregão × índice com o `valor` de cada índice; pregão sem linha vira NaN."""
    idx = indice_pregoes(cal)
    df = indices.loc[indices["indice"].isin(nomes), ["data", "indice", "valor"]].copy()
    df["data"] = pd.to_datetime(df["data"]).dt.normalize()
    df = df[df["data"].isin(idx)]
    g = df.pivot(index="data", columns="indice", values="valor")
    g = g.reindex(index=idx, columns=list(nomes)).astype(float)
    g.columns.name = "indice"
    return g


def _serie_cdi(indices: pd.DataFrame) -> pd.Series:
    """Taxa diária do CDI (decimal) indexada pela data, em ordem de data."""
    s = indices.loc[indices["indice"] == "CDI", ["data", "valor"]]
    datas = pd.DatetimeIndex(pd.to_datetime(s["data"].to_numpy())).normalize()
    return pd.Series(s["valor"].to_numpy(float) / 100, index=datas).sort_index()


def _meses_ipca(indices: pd.DataFrame) -> dict[pd.Period, float]:
    """Variação mensal do IPCA (decimal) por mês conhecido."""
    s = indices.loc[indices["indice"] == "IPCA", ["data", "valor"]]
    datas = pd.DatetimeIndex(pd.to_datetime(s["data"].to_numpy()))
    return {d.to_period("M"): float(v) / 100 for d, v in zip(datas, s["valor"].to_numpy(float))}


def _k(meses: dict[pd.Period, float], d) -> pd.Period | None:
    """K(d): maior mês conhecido estritamente anterior ao mês de d; None se não houver."""
    mes = pd.Timestamp(d).to_period("M")
    anteriores = [m for m in meses if m < mes]
    return max(anteriores) if anteriores else None


def _atraso_meses(d, k: pd.Period) -> int:
    """Meses entre o mês de d e K(d) (1 = mês anterior já conhecido, o normal)."""
    return (pd.Timestamp(d).to_period("M") - k).n


def rentabilidade_cdi(indices: pd.DataFrame, cal: list, n: int) -> Grade:
    """CDI acumulado nos n pregões anteriores a t: taxas com data em [base, t)."""
    idx = indice_pregoes(cal)
    taxa = _serie_cdi(indices)
    datas = set(taxa.index)
    fator = (1 + taxa).cumprod()

    def C(x) -> float:
        # produto das taxas com data < x
        pos = fator.index.searchsorted(x, side="left")
        return 1.0 if pos == 0 else float(fator.iloc[pos - 1])

    valores, status = [], []
    for i, t in enumerate(idx):
        if i - n < 0 or taxa.empty or idx[i - n] < taxa.index[0]:
            valores.append(np.nan)
            status.append(HIST)
        elif any(p not in datas for p in idx[i - n:i]):
            valores.append(np.nan)
            status.append(INDISPONIVEL)
        else:
            valores.append(C(t) / C(idx[i - n]) - 1)
            status.append(OK)
    return montar_grade(pd.DataFrame({"CDI": valores}, index=idx),
                        pd.DataFrame({"CDI": status}, index=idx))


def rentabilidade_ipca(indices: pd.DataFrame, cal: list, n: int, defasagem_max_meses: int | None = None) -> Grade:
    """IPCA acumulado entre K(base) e K(t): meses fechados, sem rateio por dia.

    `defasagem_max_meses` (seção 6, "Base velha"): K(t) mais de N meses antes do mês de t → indisponivel.
    None = sem limite (testes antigos; a produção passa `fase1.ipca_defasagem_max_meses`).
    """
    idx = indice_pregoes(cal)
    meses = _meses_ipca(indices)
    valores, status = [], []
    for i, t in enumerate(idx):
        if i - n < 0:
            valores.append(np.nan)
            status.append(HIST)
            continue
        kb = _k(meses, idx[i - n])
        kt = _k(meses, t)
        if kb is None or kt is None:
            valores.append(np.nan)
            status.append(HIST)
            continue
        if defasagem_max_meses is not None and _atraso_meses(t, kt) > defasagem_max_meses:
            valores.append(np.nan)
            status.append(INDISPONIVEL)
            continue
        fator = 1.0
        m = kb + 1
        while m <= kt:
            if m not in meses:
                break
            fator *= 1 + meses[m]
            m += 1
        if m <= kt:
            valores.append(np.nan)
            status.append(INDISPONIVEL)
        else:
            valores.append(fator - 1)
            status.append(OK)
    return montar_grade(pd.DataFrame({"IPCA": valores}, index=idx),
                        pd.DataFrame({"IPCA": status}, index=idx))


def cdi_dia(indices: pd.DataFrame, t, cal: list | None = None,
            defasagem_max: int | None = None) -> tuple[float, str, pd.Timestamp | None]:
    """Taxa do CDI da última data ≤ t (decimal), com status e a data usada.

    Com `cal` e `defasagem_max`: mais de `defasagem_max` pregões entre a última taxa e t → indisponivel.
    """
    taxa = _serie_cdi(indices)
    ate = taxa[taxa.index <= pd.Timestamp(t).normalize()]
    if ate.empty:
        return (np.nan, INDISPONIVEL, None)
    if cal is not None and defasagem_max is not None:
        idx = indice_pregoes(cal)
        atraso = int(((idx > ate.index[-1]) & (idx <= pd.Timestamp(t).normalize())).sum())
        if atraso > defasagem_max:   # última taxa velha demais (seção 6, "Base velha")
            return (np.nan, INDISPONIVEL, None)
    return (float(ate.iloc[-1]), OK, ate.index[-1])


def selic_meta(indices: pd.DataFrame, t, cal: list | None = None,
               defasagem_max: int | None = None) -> tuple[float, str, pd.Timestamp | None]:
    """Meta da SELIC da última data ≤ t, como fração ao ano (13,75 % a.a. -> 0.1375), com status e a data usada.

    Taxa-meta: só o último valor, nunca acumulada. Com `cal` e `defasagem_max`: mais de `defasagem_max`
    pregões entre o último valor e t → indisponivel (mesma regra do `cdi_dia`).
    """
    s = indices[indices["indice"] == "SELIC"].dropna(subset=["valor"])
    s = s.assign(data=pd.to_datetime(s["data"]).dt.normalize()).sort_values("data")
    ate = s[s["data"] <= pd.Timestamp(t).normalize()]
    if ate.empty:
        return (np.nan, INDISPONIVEL, None)
    ultima = ate["data"].iloc[-1]
    if cal is not None and defasagem_max is not None:
        idx = indice_pregoes(cal)
        atraso = int(((idx > ultima) & (idx <= pd.Timestamp(t).normalize())).sum())
        if atraso > defasagem_max:
            return (np.nan, INDISPONIVEL, None)
    return (float(ate["valor"].iloc[-1]) / 100, OK, ultima)


def ipca_12m(indices: pd.DataFrame, t, defasagem_max_meses: int | None = None) -> tuple[float, str]:
    """IPCA acumulado nos 12 meses até K(t), inclusive (decimal).

    Com `defasagem_max_meses`: K(t) mais de N meses antes do mês de t → indisponivel.
    """
    meses = _meses_ipca(indices)
    kt = _k(meses, t)
    if kt is None or not meses:
        return (np.nan, HIST)
    if defasagem_max_meses is not None and _atraso_meses(t, kt) > defasagem_max_meses:
        return (np.nan, INDISPONIVEL)
    inicio = kt - 11
    if inicio < min(meses):
        return (np.nan, HIST)
    fator = 1.0
    m = inicio
    while m <= kt:
        if m not in meses:
            return (np.nan, INDISPONIVEL)
        fator *= 1 + meses[m]
        m += 1
    return (fator - 1, OK)


def ipca_ate(indices: pd.DataFrame, t) -> str | None:
    """Último mês de IPCA conhecido na data t ("AAAA-MM"); None se não houver."""
    kt = _k(_meses_ipca(indices), t)
    return None if kt is None else str(kt)


def calcular_indices(precos: pd.DataFrame, indices: pd.DataFrame, cal: list, params) -> dict[str, Grade]:
    """Rentabilidade de cada índice em cada janela de `params.janelas` (colunas na ordem INDICES)."""
    grade_pontos = grade_de_indices(indices, cal, _PONTOS)
    grade_ivvb = grade_de_precos(precos, cal, "fechamento_ajustado", ["IVVB11"])
    resultado = {}
    for nome, n in params.janelas.items():
        partes = [
            rentabilidade_cdi(indices, cal, n),
            rentabilidade_ipca(indices, cal, n, params.ipca_defasagem_max_meses),
            variacao(grade_pontos, n, params.base_defasagem_max_pregoes),
            variacao(grade_ivvb, n, params.base_defasagem_max_pregoes),
        ]
        valor = pd.concat([p.valor for p in partes], axis=1)
        status = pd.concat([p.status for p in partes], axis=1)
        resultado[nome] = montar_grade(valor, status)
    return resultado


def indices_no_dia(res: dict[str, Grade], t) -> pd.DataFrame:
    """Formato longo [indice, janela, valor, status] de t; ValueError se t não for pregão."""
    ts = pd.Timestamp(t).normalize()
    linhas = []
    for janela, grade in res.items():
        if ts not in grade.valor.index:
            raise ValueError(f"{t} não é pregão")
        for indice in grade.valor.columns:
            linhas.append({
                "indice": indice,
                "janela": janela,
                "valor": float(grade.valor.at[ts, indice]),
                "status": grade.status.at[ts, indice],
            })
    df = pd.DataFrame(linhas, columns=["indice", "janela", "valor", "status"])
    return df.sort_values(["indice", "janela"]).reset_index(drop=True)


def ipca_mensal(indices: pd.DataFrame, t, n: int = 12) -> list[tuple[str, float, str]]:
    """IPCA de cada um dos `n` meses de referência até K(t), inclusive, do mais antigo ao mais recente.

    Mês de referência (não a data de divulgação), com o mesmo K(t) de `ipca_12m`/`ipca_ate`: só meses
    anteriores ao mês de t. (mes_ref "AAAA-MM", valor decimal, status): mês antes do 1º mês conhecido →
    historico_insuficiente; mês sem valor depois disso → indisponivel. Sem K(t): lista vazia.
    """
    meses = _meses_ipca(indices)
    kt = _k(meses, t)
    if kt is None:
        return []
    primeiro = min(meses)
    linhas = []
    for m in pd.period_range(kt - (n - 1), kt, freq="M"):
        v = meses.get(m)
        if v is not None and not np.isnan(v):
            linhas.append((str(m), v, OK))
        elif m < primeiro:
            linhas.append((str(m), np.nan, HIST))
        else:
            linhas.append((str(m), np.nan, INDISPONIVEL))
    return linhas


def cdi_mensal(indices: pd.DataFrame, t, cal: list, n: int = 12) -> list[tuple[str, float, str]]:
    """CDI composto de cada um dos `n` meses completos antes do mês de t: produto de (1 + taxa) − 1.

    O mês de t (incompleto) fica de fora. Entram as taxas com data no mês (e ≤ t). Mês sem pregão no `cal`
    ou com pregão anterior à 1ª taxa → historico_insuficiente; pregão do mês sem taxa → indisponivel
    (mesma exigência de `rentabilidade_cdi`). Do mais antigo ao mais recente.
    """
    ts = pd.Timestamp(t).normalize()
    taxa = _serie_cdi(indices)
    taxa = taxa[taxa.index <= ts]
    idx = indice_pregoes(cal)
    idx = idx[idx <= ts]
    meses_idx = idx.to_period("M")
    meses_taxa = taxa.index.to_period("M")
    datas = set(taxa.index)
    mes_t = ts.to_period("M")
    linhas = []
    for m in pd.period_range(mes_t - n, mes_t - 1, freq="M"):
        pregoes = idx[meses_idx == m]
        if len(pregoes) == 0 or taxa.empty or pregoes[0] < taxa.index[0]:
            linhas.append((str(m), np.nan, HIST))
        elif any(p not in datas for p in pregoes):
            linhas.append((str(m), np.nan, INDISPONIVEL))
        else:
            linhas.append((str(m), float(np.prod(1 + taxa[meses_taxa == m].to_numpy())) - 1, OK))
    return linhas
