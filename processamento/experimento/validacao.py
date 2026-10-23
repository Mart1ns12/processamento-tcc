"""Períodos e dobras do treino: desenvolvimento, teste final e walk-forward (seções 7.4 e 7.5).

Funções puras: DataFrames e listas de datas entram, saem DataFrames e dobras. Nada de banco ou rede.
O alvo de t olha t+1: o pregão imediatamente anterior ao 1º dia de teste sai do treino (embargo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Dobra:
    """Uma dobra: mês de teste ("AAAA-MM") e as datas de treino e de teste."""

    numero: int
    mes_teste: str
    datas_treino: tuple[date, ...]
    datas_teste: tuple[date, ...]


def _datas(df: pd.DataFrame) -> list[date]:
    """Coluna `data` como lista de `date` (aceita date ou Timestamp)."""
    return [pd.Timestamp(d).date() for d in df["data"]]


def _ordenadas(cal: list) -> list[date]:
    """Datas únicas do calendário, em ordem."""
    return sorted({pd.Timestamp(d).date() for d in cal})


def _meses(datas: list[date]) -> list[tuple[int, int]]:
    """Pares (ano, mês) distintos, na ordem em que aparecem."""
    meses: list[tuple[int, int]] = []
    for d in datas:
        if (d.year, d.month) not in meses:
            meses.append((d.year, d.month))
    return meses


def _filtrar(df: pd.DataFrame, mantem: list[bool]) -> pd.DataFrame:
    """Linhas de `df` marcadas em `mantem` (funciona também com df vazio)."""
    return df.loc[np.array(mantem, dtype=bool)].copy()


def aplicar_inicio(df: pd.DataFrame, inicio: date | None) -> pd.DataFrame:
    """Linhas com data >= `inicio`; `None` mantém todas."""
    if inicio is None:
        return df.copy()
    return _filtrar(df, [d >= inicio for d in _datas(df)])


def periodo_desenvolvimento(df: pd.DataFrame, inicio_teste_final: date, embargo: int = 1) -> pd.DataFrame:
    """Datas antes do teste final, menos as `embargo` últimas datas que sobraram."""
    datas = _datas(df)
    antes = sorted({d for d in datas if d < inicio_teste_final})
    fora = set(antes[max(len(antes) - embargo, 0):])
    return _filtrar(df, [d < inicio_teste_final and d not in fora for d in datas])


def linhas_com_alvo_ate(df: pd.DataFrame, fim: date) -> pd.DataFrame:
    """Linhas cujo dia do alvo (o próximo pregão de `df`) é <= `fim`.

    A linha do próprio `fim` (alvo depois dele) já é do teste ao vivo: é a primeira previsão ao vivo.
    A última data de `df`, sem próximo pregão conhecido, também sai.
    """
    datas = _datas(df)
    ordem = sorted(set(datas))
    proximo = dict(zip(ordem, ordem[1:]))
    return _filtrar(df, [d in proximo and proximo[d] <= fim for d in datas])


def periodo_teste_final(df: pd.DataFrame, inicio_teste_final: date, fim_teste_final: date) -> pd.DataFrame:
    """Linhas com `data >= inicio` e dia do alvo (t+1) <= `fim`. O resto depois é teste ao vivo."""
    no_alvo = linhas_com_alvo_ate(df, fim_teste_final)
    return _filtrar(no_alvo, [d >= inicio_teste_final for d in _datas(no_alvo)])


def dobras_walk_forward(cal: list[date], treino_minimo_meses: int, embargo: int = 1) -> list[Dobra]:
    """Uma dobra por mês de teste, a partir do mês de índice `treino_minimo_meses`.

    O treino são as datas anteriores ao mês de teste, menos as `embargo` últimas. Dobra sem treino é pulada.
    """
    datas = _ordenadas(cal)
    dobras: list[Dobra] = []
    for ano, mes in _meses(datas)[treino_minimo_meses:]:
        teste = tuple(d for d in datas if (d.year, d.month) == (ano, mes))
        anteriores = [d for d in datas if d < teste[0]]
        treino = tuple(anteriores[: max(len(anteriores) - embargo, 0)])
        if not treino:
            continue
        dobras.append(Dobra(len(dobras) + 1, f"{ano:04d}-{mes:02d}", treino, teste))
    return dobras


def dobras_teste_final(cal: list[date], inicio: date, fim: date, embargo: int = 1) -> list[Dobra]:
    """Uma dobra por mês com datas em [inicio, fim]. Nenhuma data depois de `fim` entra em treino ou teste."""
    datas = _ordenadas(cal)
    no_periodo = [d for d in datas if inicio <= d <= fim]
    dobras: list[Dobra] = []
    for ano, mes in _meses(no_periodo):
        teste = tuple(d for d in no_periodo if (d.year, d.month) == (ano, mes))
        anteriores = [d for d in datas if d < teste[0]]
        treino = tuple(anteriores[: max(len(anteriores) - embargo, 0)])
        if not treino:  # uso único: nunca pular mês do teste final em silêncio
            raise ValueError(f"teste final: o mês {ano:04d}-{mes:02d} não tem pregões de treino antes dele")
        dobras.append(Dobra(len(dobras) + 1, f"{ano:04d}-{mes:02d}", treino, teste))
    return dobras


def linhas_da_dobra(prep: pd.DataFrame, dobra: Dobra) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(treino, teste): linhas cujas datas estão na dobra e com `alvo` não nulo."""
    datas = _datas(prep)
    com_alvo = prep["alvo"].notna().to_numpy()
    no_treino = set(dobra.datas_treino)
    no_teste = set(dobra.datas_teste)
    mascara_treino = np.array([d in no_treino for d in datas], dtype=bool) & com_alvo
    mascara_teste = np.array([d in no_teste for d in datas], dtype=bool) & com_alvo
    treino = prep.loc[mascara_treino].reset_index(drop=True)
    teste = prep.loc[mascara_teste].reset_index(drop=True)
    return treino, teste
