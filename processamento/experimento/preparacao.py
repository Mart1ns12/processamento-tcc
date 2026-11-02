"""Preparação do dataset do experimento: ranks por pregão e colunas de cada modelo (seção 7.3).

Funções puras: DataFrames entram, DataFrames saem. A mesma função serve ao treino e à previsão.
Ausência continua NaN; o rank só olha os valores válidos do mesmo pregão.
"""

from __future__ import annotations

import pandas as pd

IDENTIFICACAO = ["data", "ticker", "empresa", "setor", "universo", "dia_resultado"]
ESSENCIAIS_PRECO = ["ret_1d", "ret_5d", "ret_20d", "volatilidade_20d", "beta", "volume_relativo", "salto_abertura"]
COMPLEMENTARES_PRECO = ["dist_max_52s", "dist_min_52s", "amplitude", "ret_vs_setor", "exposicao_dolar", "exposicao_petroleo"]
COLUNAS_PRECO = ESSENCIAIS_PRECO + COMPLEMENTARES_PRECO
BLOCO_A = ["posicao_fechamento", "mom_12_1", "liquidez_20d", "ret_idio_5d"]
BLOCO_B = ["momento_setor_5d", "exposicao_small"]
BLOCO_C = ["dias_desde_resultado", "var_lucro_aa"]
BLOCO_D = ["dy_12m"]
BLOCO_E = ["fato_relevante_cvm"]
CONTROLE = ["controle_sorteado"]
BLOCOS_PROTOCOLO = {   # protocolo_variaveis.md; fora de BLOCOS_COMPLEMENTARES de propósito
    "bloco_a": BLOCO_A, "bloco_b": BLOCO_B, "bloco_c": BLOCO_C, "bloco_d": BLOCO_D, "bloco_e": BLOCO_E,
    "controle": CONTROLE,
}
COLUNAS_PROTOCOLO = BLOCO_A + BLOCO_B + BLOCO_C + BLOCO_D + BLOCO_E + CONTROLE
NOTICIAS_DIA = ["noticias_dia_qtd", "noticias_dia_tom", "noticias_dia_extremo", "mudanca_tom"]
COMPLEMENTARES_NOTICIAS = ["tom_setor", "tom_mercado"]
# A quantidade de notícias muda de regime entre os anos: entra como rank do pregão, como as de preço (o CSV guarda o bruto).
COLUNAS_RANK = COLUNAS_PRECO + ["noticias_dia_qtd"] + COLUNAS_PROTOCOLO
COLUNAS_BRUTAS = [c for c in NOTICIAS_DIA + COMPLEMENTARES_NOTICIAS if c not in COLUNAS_RANK]
# Variante testada só no desenvolvimento: `selecionar_configuracao` a troca pela bruta se o AUC subir o suficiente.
EXTREMO_RANK = "noticias_dia_extremo_rank"
COLUNA_BRUTA = {EXTREMO_RANK: "noticias_dia_extremo"}   # coluna preparada -> coluna do dataset (motivos do top)
# Sobe quando mudam os ranks, as colunas ou as regras que afetam os valores do dataset: dataset e modelo de outra
# versão não valem. 2 = regras de 01/11/2026 (cobertura, cópias pelo momento, noticias_dia_qtd em rank).
VERSAO_PREPARACAO = 5   # 3 = blocos A e B; 4 = blocos C, D, E e controle, em 02/11/2026; 5 = reapresentação sem original conta em fato_relevante_cvm, em 02/11/2026
COLUNAS_ALVO = ["alvo", "alvo_abertura", "alvo_abertura_valido", "ret_t1", "ret_ibov_t1"]
BLOCOS_COMPLEMENTARES = {
    "preco_contexto": ["dist_max_52s", "dist_min_52s", "amplitude", "ret_vs_setor"],
    "macro": ["exposicao_dolar", "exposicao_petroleo"],
    "noticias_contexto": COMPLEMENTARES_NOTICIAS,
}
MODELOS = ("1", "3")
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
    """Ranks das variáveis de preço, volume e mercado, das colunas do protocolo e de `noticias_dia_qtd`; acrescenta `EXTREMO_RANK`.

    Identificação, as outras colunas de notícias e o alvo não mudam.
    """
    faltando = [c for c in _COLUNAS_ENTRADA if c not in dataset.columns]
    if faltando:
        raise ValueError(f"faltam colunas no dataset: {faltando}")
    extremo = rank_no_pregao(dataset, ["noticias_dia_extremo"])["noticias_dia_extremo"]
    return rank_no_pregao(dataset, COLUNAS_RANK).assign(**{EXTREMO_RANK: extremo})


def linhas_de_treino(preparado: pd.DataFrame) -> pd.DataFrame:
    """Linhas com alvo. O rank já foi feito antes do filtro, então não é recalculado aqui."""
    return preparado[preparado["alvo"].notna()].reset_index(drop=True)


def colunas_do_modelo(modelo: str, blocos: tuple[str, ...] = ()) -> list[str]:
    """Colunas de entrada do modelo "1" ou "3", seguidas dos blocos complementares na ordem dada."""
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
            raise ValueError(f"o bloco noticias_contexto só vale no modelo 3 (modelo {modelo!r})")
        usados.add(bloco)
        colunas += BLOCOS_COMPLEMENTARES[bloco]
    return colunas


def linhas_modelo_3b(preparado: pd.DataFrame) -> pd.DataFrame:
    """Só os dias de resultado (dia_resultado == True), recorte da avaliação "3b" (não há modelo próprio, F12)."""
    return preparado[preparado["dia_resultado"].eq(True)].reset_index(drop=True)
