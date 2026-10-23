"""Preparação do dataset do experimento: ranks por pregão e colunas de cada modelo (seção 7.3).

Funções puras: DataFrames entram, DataFrames saem. A mesma função serve ao treino e à previsão.
Ausência continua NaN; o rank só olha os valores válidos do mesmo pregão.
"""

from __future__ import annotations

import pandas as pd

IDENTIFICACAO = ["data", "ticker", "empresa", "setor", "universo", "dia_resultado"]
ESSENCIAIS_PRECO = ["ret_1d", "ret_5d", "ret_20d", "volatilidade_20d", "beta", "volume_relativo", "salto_abertura"]
COMPLEMENTARES_PRECO = ["dist_max_52s", "dist_min_52s", "amplitude", "ret_vs_setor", "exposicao_dolar", "exposicao_petroleo"]
COLUNAS_RANK = ESSENCIAIS_PRECO + COMPLEMENTARES_PRECO
NOTICIAS_DIA = ["noticias_dia_qtd", "noticias_dia_tom", "noticias_dia_extremo", "mudanca_tom"]
COMPLEMENTARES_NOTICIAS = ["tom_setor", "tom_mercado"]
COLUNAS_BRUTAS = NOTICIAS_DIA + COMPLEMENTARES_NOTICIAS
COLUNAS_ALVO = ["alvo", "alvo_abertura", "alvo_abertura_valido", "ret_t1", "ret_ibov_t1"]
BLOCOS_COMPLEMENTARES = {
    "preco_contexto": ["dist_max_52s", "dist_min_52s", "amplitude", "ret_vs_setor"],
    "macro": ["exposicao_dolar", "exposicao_petroleo"],
    "noticias_contexto": COMPLEMENTARES_NOTICIAS,
}
MODELOS = ("1", "3", "3b")
_COLUNAS_ENTRADA = IDENTIFICACAO + COLUNAS_RANK + COLUNAS_BRUTAS + COLUNAS_ALVO


def _rank_coluna(valores: pd.Series, pregoes: pd.Series) -> pd.Series:
    """Rank (média − 1)/(n − 1) dentro de cada pregão; n = válidos no dia; n = 1 vira 0,5."""
    rank = valores.groupby(pregoes).rank(method="average")
    n = valores.groupby(pregoes).transform("count")
    pos = (rank - 1) / (n - 1)
    pos = pos.where(n != 1, 0.5)
    return pos.where(valores.notna())


def rank_no_pregao(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Troca cada coluna de `colunas` pelo seu rank entre as linhas do mesmo `data`; NaN fica NaN."""
    pregoes = pd.Series(df["data"].to_numpy())
    out = df.copy()
    for c in colunas:
        valores = pd.Series(df[c].to_numpy(dtype=float))
        out[c] = _rank_coluna(valores, pregoes).to_numpy()
    return out


def preparar(dataset: pd.DataFrame) -> pd.DataFrame:
    """Ranks das 13 variáveis de preço, volume e mercado; identificação, notícias e alvo não mudam."""
    faltando = [c for c in _COLUNAS_ENTRADA if c not in dataset.columns]
    if faltando:
        raise ValueError(f"faltam colunas no dataset: {faltando}")
    return rank_no_pregao(dataset, COLUNAS_RANK)


def linhas_de_treino(preparado: pd.DataFrame) -> pd.DataFrame:
    """Linhas com alvo. O rank já foi feito antes do filtro, então não é recalculado aqui."""
    return preparado[preparado["alvo"].notna()].reset_index(drop=True)


def colunas_do_modelo(modelo: str, blocos: tuple[str, ...] = ()) -> list[str]:
    """Colunas de entrada do modelo "1", "3" ou "3b", seguidas dos blocos complementares na ordem dada."""
    if modelo == "2":
        raise ValueError("modelo 2 removido: ver ESPECIFICACAO 7.4")
    if modelo not in MODELOS:
        raise ValueError(f"modelo desconhecido: {modelo!r} (use {', '.join(MODELOS)})")
    colunas = list(ESSENCIAIS_PRECO)
    if modelo != "1":
        colunas += NOTICIAS_DIA
    usados: set[str] = set()
    for bloco in blocos:
        if bloco not in BLOCOS_COMPLEMENTARES:
            raise ValueError(f"bloco desconhecido: {bloco!r}")
        if bloco in usados:
            raise ValueError(f"bloco repetido: {bloco!r}")
        if bloco == "noticias_contexto" and modelo == "1":
            raise ValueError(f"o bloco noticias_contexto só vale nos modelos 3 e 3b (modelo {modelo!r})")
        usados.add(bloco)
        colunas += BLOCOS_COMPLEMENTARES[bloco]
    return colunas


def linhas_modelo_3b(preparado: pd.DataFrame) -> pd.DataFrame:
    """Só os dias de resultado (dia_resultado == True), usados no modelo 3b."""
    return preparado[preparado["dia_resultado"].eq(True)].reset_index(drop=True)
