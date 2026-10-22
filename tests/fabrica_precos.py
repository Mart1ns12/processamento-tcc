"""Fábrica de dados de teste para os fatos de preço e índices (tests/test_fatos_*.py).

Séries curtas são escritas à mão nos testes; as longas saem daqui. Os nomes de colunas são os
de `fontes.ler_tabela` (precos, cadastro, indices). Nenhuma função usa banco ou rede.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def pregoes_uteis(n: int, inicio: str = "2025-01-02") -> list[date]:
    """n dias úteis (seg-sex) a partir de `inicio`."""
    return [ts.date() for ts in pd.bdate_range(inicio, periods=n)]


def serie_por_retornos(p0: float, retornos: list[float]) -> list[float]:
    """Preços [p0, p0(1+r1), p0(1+r1)(1+r2), ...]."""
    precos = [float(p0)]
    for r in retornos:
        precos.append(precos[-1] * (1 + r))
    return precos


def _colunar(valores: list) -> list[float]:
    """Lista de números com None virando NaN."""
    return [float("nan") if v is None else float(v) for v in valores]


def precos_de(ticker: str, datas: list[date], fech: list, aj: list | None = None,
              volume: list | None = None) -> pd.DataFrame:
    """Linhas de `v1-precos` para um ticker.

    `aj=None` vale igual a `fech`; `volume=None` vale 1000 em todas as datas. None dentro de
    uma lista vira NaN. Abertura, máxima e mínima valem `fech`.
    """
    fech_c = _colunar(fech)
    aj_c = fech_c if aj is None else _colunar(aj)
    vol_c = [1000.0] * len(datas) if volume is None else _colunar(volume)
    return pd.DataFrame({
        "data": pd.to_datetime(list(datas)).to_numpy(),
        "ticker": ticker,
        "abertura": fech_c,
        "maxima": fech_c,
        "minima": fech_c,
        "fechamento": fech_c,
        "fechamento_ajustado": aj_c,
        "volume": vol_c,
    })


def indices_de(linhas: list[tuple[str, str, float]]) -> pd.DataFrame:
    """Linhas de `v1-indices`: (data 'AAAA-MM-DD', indice, valor)."""
    return pd.DataFrame({
        "data": pd.to_datetime([d for d, _, _ in linhas]).to_numpy(),
        "indice": [i for _, i, _ in linhas],
        "valor": [float(v) for _, _, v in linhas],
    })


def cadastro_de(linhas: list[tuple[str, str | None, str | None, str]]) -> pd.DataFrame:
    """Linhas de `v1-cadastro`: (ticker, cnpj, setor, tipo_acao). empresa = ticker."""
    n = len(linhas)
    return pd.DataFrame({
        "ticker": [t for t, _, _, _ in linhas],
        "cnpj": [c for _, c, _, _ in linhas],
        "empresa": [t for t, _, _, _ in linhas],
        "setor": [s for _, _, s, _ in linhas],
        "subsetor": [None] * n,
        "tipo_acao": [k for _, _, _, k in linhas],
        "unit_qtd_on": [None] * n,
        "unit_qtd_pn": [None] * n,
    })
