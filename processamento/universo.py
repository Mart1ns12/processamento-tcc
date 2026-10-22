"""Universo de ações por data (seção 3.5 da especificação).

Funções puras: recebem DataFrames e devolvem o universo, sem banco e sem rede.
O universo tem uma linha por pregão × ação candidata. `motivo` diz por que a ação entrou
(`ok`) ou ficou de fora: vale o primeiro critério que se aplicar.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd

from processamento.exclusoes import Exclusoes
from processamento.tickers import classe, tipo_por_classe

TIPOS_ACEITOS = {"ON", "PN", "UNIT"}
COLUNAS = ["data", "ticker", "tipo_acao", "no_universo", "motivo", "universo"]


def _data_ou_none(valor: object) -> date | None:
    """Data (datetime ou texto) como `date`; vazio (None, NaT ou NaN) vira None."""
    if valor is None or pd.isna(valor):
        return None
    return pd.Timestamp(valor).date()


def _tipo_ou_none(valor: object) -> str | None:
    """Tipo de ação do cadastro; vazio (None, NaN ou texto em branco) vira None."""
    if isinstance(valor, str) and valor.strip():
        return valor
    return None


def _na_composicao(dia: date, intervalos: list[tuple[date | None, date | None]]) -> bool:
    """Diz se o dia cai em algum intervalo da composição (None = sem limite)."""
    return any(
        (ini is None or ini <= dia) and (fim is None or fim >= dia) for ini, fim in intervalos
    )


def montar_universo(
    pregoes: list[date],
    cadastro: pd.DataFrame,
    precos: pd.DataFrame,
    exclusoes: Exclusoes,
    composicao: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Monta o universo de cada pregão para as ações candidatas.

    `cadastro`: colunas ticker e tipo_acao. `precos`: colunas data, ticker e fechamento_ajustado
    (data como datetime ou texto; preço nulo conta como sem preço). `composicao`: colunas
    ticker, data_inicio e data_fim (NaT = sem limite). Sem composição, o universo é
    `composicao_atual`; com ela, `composicao_historica`.
    """
    tipos_cadastro = {
        t: _tipo_ou_none(tipo) for t, tipo in zip(cadastro["ticker"], cadastro["tipo_acao"])
    }

    com_preco = set()
    for data, t, fechamento in zip(precos["data"], precos["ticker"], precos["fechamento_ajustado"]):
        dia = _data_ou_none(data)
        if dia is not None and pd.notna(fechamento):
            com_preco.add((dia, t))

    intervalos: dict[str, list[tuple[date | None, date | None]]] = defaultdict(list)
    candidatos = set(cadastro["ticker"].dropna())
    if composicao is not None:
        candidatos |= set(composicao["ticker"].dropna())
        for t, ini, fim in zip(composicao["ticker"], composicao["data_inicio"], composicao["data_fim"]):
            intervalos[t].append((_data_ou_none(ini), _data_ou_none(fim)))
    universo = "composicao_atual" if composicao is None else "composicao_historica"

    tipo_de = {t: tipos_cadastro.get(t) or tipo_por_classe(classe(t)) for t in candidatos}

    linhas = []
    for pregao in pregoes:
        dia = _data_ou_none(pregao)
        for t in sorted(candidatos):
            tipo = tipo_de[t]
            if t in exclusoes.tickers_excluidos:
                motivo = "excluido_por_decisao"
            elif tipo not in TIPOS_ACEITOS:
                motivo = "tipo_nao_aceito"
            elif composicao is not None and not _na_composicao(dia, intervalos.get(t, [])):
                motivo = "fora_da_composicao"
            elif (dia, t) not in com_preco:
                motivo = "sem_preco"
            else:
                motivo = "ok"
            linhas.append(
                {
                    "data": pd.Timestamp(dia),
                    "ticker": t,
                    "tipo_acao": tipo,
                    "no_universo": motivo == "ok",
                    "motivo": motivo,
                    "universo": universo,
                }
            )

    df = pd.DataFrame(linhas, columns=COLUNAS)
    df["data"] = pd.to_datetime(df["data"])
    df["no_universo"] = df["no_universo"].astype(bool)
    return df.sort_values(["data", "ticker"]).reset_index(drop=True)


def tickers_do_dia(universo: pd.DataFrame, d: date) -> list[str]:
    """Tickers que estão no universo no pregão `d`, em ordem alfabética."""
    linhas = universo.loc[(universo["data"] == pd.Timestamp(d)) & universo["no_universo"]]
    return sorted(linhas["ticker"].tolist())
