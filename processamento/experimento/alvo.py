"""Alvo do experimento: o único campo que olha t+1 (seção 7.3 da especificação).

Para cada pregão t e ticker, o alvo compara o retorno da ação de t para t+1 com o do IBOV no
mesmo intervalo. t+1 é a linha seguinte da grade de `cal` (o próximo pregão estrito do
calendário). Funções puras: nada de banco ou rede. Ausência é NaN, nunca 0.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.fatos.precos import grade_de_precos

IBOV = "IBOV"


def _abertura_ajustada(abertura, aj, fech):
    """Abertura ajustada = abertura · aj / fech (NaN onde o fechamento não é positivo)."""
    return abertura * aj / fech.where(fech > 0)


def _retorno(futuro, base):
    """futuro(t+1) / base(t) − 1, com t+1 = linha seguinte da grade (NaN se base não é positiva)."""
    return futuro.shift(-1) / base.where(base > 0) - 1


def _repetir_ibov(serie: pd.Series, modelo: pd.DataFrame) -> pd.DataFrame:
    """Repete a série do IBOV em todas as colunas de `modelo` (mesmo índice de pregões)."""
    return pd.DataFrame(
        np.tile(serie.to_numpy()[:, None], (1, modelo.shape[1])),
        index=modelo.index,
        columns=modelo.columns,
    )


def _comparar(ret: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """1.0 se ret > ref, senão 0.0 (empate = 0); NaN se faltar qualquer lado."""
    return (ret > ref).astype(float).where(ret.notna() & ref.notna())


def alvos(precos: pd.DataFrame, cal: list, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Alvo, alvo_abertura, ret_t1 e ret_ibov_t1 (pregão × ticker).

    `alvo` compara o fechamento ajustado; `alvo_abertura`, a abertura ajustada (abertura · aj /
    fech, também para o IBOV) com a base do fechamento ajustado de t. No último pregão de `cal`,
    t+1 não existe e o alvo é NaN.
    """
    tickers = list(tickers)
    aj = grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    ab = grade_de_precos(precos, cal, "abertura", tickers)
    fech = grade_de_precos(precos, cal, "fechamento", tickers)
    ibov_aj = grade_de_precos(precos, cal, "fechamento_ajustado", [IBOV])[IBOV]
    ibov_ab = grade_de_precos(precos, cal, "abertura", [IBOV])[IBOV]
    ibov_fech = grade_de_precos(precos, cal, "fechamento", [IBOV])[IBOV]

    ret_t1 = _retorno(aj, aj)
    ret_ibov_t1 = _repetir_ibov(_retorno(ibov_aj, ibov_aj), aj)
    ab_aj = _abertura_ajustada(ab, aj, fech)
    ibov_ab_aj = _abertura_ajustada(ibov_ab, ibov_aj, ibov_fech)
    ret_ab_t1 = _retorno(ab_aj, aj)
    ret_ibov_ab_t1 = _repetir_ibov(_retorno(ibov_ab_aj, ibov_aj), aj)

    return {
        "alvo": _comparar(ret_t1, ret_ibov_t1),
        "alvo_abertura": _comparar(ret_ab_t1, ret_ibov_ab_t1),
        "ret_t1": ret_t1,
        "ret_ibov_t1": ret_ibov_t1,
    }
