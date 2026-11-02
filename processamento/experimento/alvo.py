"""Alvo do experimento: o único campo que olha t+1 (seção 7.3 da especificação).

Para cada pregão t e ticker, o alvo compara o retorno da ação de t para t+1 com o do IBOV no
mesmo intervalo. t+1 é a linha seguinte da grade de `cal` (o próximo pregão estrito do
calendário). Funções puras: nada de banco ou rede. Ausência é NaN, nunca 0.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.fatos.precos import ParametrosPrecos, carregar_parametros_precos, grade_de_precos, retornos_suspeitos

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


def alvos(
    precos: pd.DataFrame, cal: list, tickers: list[str], params_precos: ParametrosPrecos | None = None
) -> dict[str, pd.DataFrame]:
    """Alvo, alvo_abertura, ret_t1 e ret_ibov_t1 (pregão × ticker).

    Retorno diário suspeito em t+1 (seção 6) deixa `ret_t1`, `alvo` e `alvo_abertura` de t em NaN.
    `params_precos` None lê o bloco fase1.

    `alvo` compara o fechamento ajustado; `alvo_abertura`, a abertura ajustada (abertura · aj /
    fech, também para o IBOV) com a base do fechamento ajustado de t. No último pregão de `cal`,
    t+1 não existe e o alvo é NaN.

    `alvo_abertura_valido`: 1.0 se a abertura do IBOV em t+1 ≠ o fechamento do IBOV em t (abertura
    informada); 0.0 se igual (defeito do Yahoo); NaN se faltar algum lado ou no último pregão.
    """
    tickers = list(tickers)
    aj = grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    ab = grade_de_precos(precos, cal, "abertura", tickers)
    fech = grade_de_precos(precos, cal, "fechamento", tickers)
    ibov_aj = grade_de_precos(precos, cal, "fechamento_ajustado", [IBOV])[IBOV]
    ibov_ab = grade_de_precos(precos, cal, "abertura", [IBOV])[IBOV]
    ibov_fech = grade_de_precos(precos, cal, "fechamento", [IBOV])[IBOV]

    pp = carregar_parametros_precos() if params_precos is None else params_precos
    suspeito_t1 = retornos_suspeitos(
        aj, pp.retorno_suspeito_min, pp.retorno_suspeito_max, pp.base_defasagem_max_pregoes
    ).shift(-1, fill_value=False).astype(bool)

    ret_t1 = _retorno(aj, aj).mask(suspeito_t1)
    ret_ibov_t1 = _repetir_ibov(_retorno(ibov_aj, ibov_aj), aj)
    ab_aj = _abertura_ajustada(ab, aj, fech)
    ibov_ab_aj = _abertura_ajustada(ibov_ab, ibov_aj, ibov_fech)
    ret_ab_t1 = _retorno(ab_aj, aj).mask(suspeito_t1)
    ret_ibov_ab_t1 = _repetir_ibov(_retorno(ibov_ab_aj, ibov_aj), aj)
    ibov_ab_t1 = ibov_ab.shift(-1)
    igual = pd.Series(np.isclose(ibov_ab_t1, ibov_fech, rtol=0.0, atol=1e-9), index=ibov_fech.index)
    valido = (~igual).astype(float).where(ibov_ab_t1.notna() & ibov_fech.notna())

    return {
        "alvo": _comparar(ret_t1, ret_ibov_t1),
        "alvo_abertura": _comparar(ret_ab_t1, ret_ibov_ab_t1),
        "alvo_abertura_valido": _repetir_ibov(valido, aj),
        "ret_t1": ret_t1,
        "ret_ibov_t1": ret_ibov_t1,
    }
