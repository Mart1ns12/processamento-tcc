"""Variáveis de preço do dataset do experimento (seção 7.3 da especificação; plano da etapa 5, fase 5).

Reusa as contas de processamento/fatos/precos.py (variação, volatilidade, volume, beta e média do
setor). Funções puras: DataFrames entram, DataFrames saem. Ausência é NaN, nunca 0. Cada grade é
pregão × ticker, só com o valor.
"""

from __future__ import annotations

import pandas as pd

from processamento.experimento.parametros import ParametrosExperimento
from processamento.fatos import precos as fatos_precos
from processamento.fatos.precos import ParametrosPrecos


def _distancia(g: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """g ÷ ref − 1, NaN onde a referência não é positiva."""
    return (g / ref - 1).where(ref > 0)


def salto_abertura(g_ab: pd.DataFrame, g_aj: pd.DataFrame, g_fech: pd.DataFrame) -> pd.DataFrame:
    """Abertura ajustada de t (abertura·aj/fech do mesmo dia) contra o fechamento ajustado do pregão anterior.

    O anterior é estrito (`shift(1)` na grade, sem preencher lacunas). Fechamento ≤ 0 vira NaN.
    """
    ab_aj = (g_ab * g_aj / g_fech).where(g_fech > 0)
    return _distancia(ab_aj, g_aj.shift(1))


def extremos(g_aj: pd.DataFrame, janela: int, minimo: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Distância do fechamento ajustado ao maior e ao menor da janela de `janela` pregões (inclui t).

    Devolve (dist_max, dist_min). Com menos de `minimo` valores na janela, NaN.
    """
    jan = g_aj.rolling(janela, min_periods=minimo)
    return _distancia(g_aj, jan.max()), _distancia(g_aj, jan.min())


def amplitude(g_max: pd.DataFrame, g_min: pd.DataFrame, g_fech: pd.DataFrame) -> pd.DataFrame:
    """(máxima − mínima) ÷ fechamento do próprio dia (mesma escala, sem ajuste).

    NaN sem insumo, com fechamento ≤ 0 ou com máxima menor que a mínima.
    """
    valido = g_max.notna() & g_min.notna() & (g_fech > 0) & (g_max >= g_min)
    return ((g_max - g_min) / g_fech).where(valido)


def exposicao(g_aj: pd.DataFrame, fator: pd.Series, janela: int, minimo: int) -> pd.DataFrame:
    """Beta da ação sobre o fator (ex.: dólar) vezes o retorno do fator no dia."""
    b = fatos_precos.beta(g_aj, fator, janela, minimo).valor
    return b.mul(fator / fator.shift(1) - 1, axis=0)


def ret_vs_setor(ret: pd.DataFrame, mascara: pd.DataFrame, setor_de: dict, cnpj_de: dict,
                 modo: str) -> pd.DataFrame:
    """Retorno da ação menos a média do setor, só entre as ações da máscara.

    No modo "empresa", o CNPJ inteiro sai da média (ver `fatos.precos.media_setor`).
    """
    r = ret.where(mascara)
    status = pd.DataFrame(fatos_precos.OK, index=r.index, columns=r.columns)
    media = fatos_precos.media_setor(
        fatos_precos.montar_grade(r, status), list(r.columns), setor_de, cnpj_de, modo, agregacao="media"
    )  # o modelo continua com a média (seção 7.3); o painel usa a mediana
    return r - media.valor


def variaveis_de_preco(
    precos: pd.DataFrame,
    cal: list,
    tickers: list[str],
    mascara: pd.DataFrame,
    setor_de: dict,
    cnpj_de: dict,
    params: ParametrosExperimento,
    params_precos: ParametrosPrecos,
) -> dict[str, pd.DataFrame]:
    """As 13 grades de preço e volume do dataset (pregão × ticker, só o valor); seção 7.3.

    Janelas de retorno, extremos, exposição e tom vêm de `params`; volatilidade, volume e beta
    vêm do bloco fase1 (`params_precos`), como no painel. Fator de câmbio e petróleo: fechamento
    ajustado. ret_vs_setor usa o retorno de 1 pregão e o modo "empresa", só com ações da máscara.
    Retornos com base as-of até `fase1.base_defasagem_max_pregoes` pregões antes da data-alvo
    (seção 6, Base velha).
    """
    g_fech = fatos_precos.grade_de_precos(precos, cal, "fechamento", tickers)
    g_ab = fatos_precos.grade_de_precos(precos, cal, "abertura", tickers)
    g_max = fatos_precos.grade_de_precos(precos, cal, "maxima", tickers)
    g_min = fatos_precos.grade_de_precos(precos, cal, "minima", tickers)
    g_aj = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    gv = fatos_precos.grade_de_precos(precos, cal, "volume", tickers)
    ibov = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", ["IBOV"])["IBOV"]
    usd = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", ["USDBRL"])["USDBRL"]
    brent = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", ["BRENT"])["BRENT"]

    res: dict[str, pd.DataFrame] = {}
    for nome, n in params.retornos.items():
        res[nome] = fatos_precos.variacao(g_aj, n, params_precos.base_defasagem_max_pregoes).valor

    ret_dia = fatos_precos.variacao(g_aj, 1, params_precos.base_defasagem_max_pregoes).valor
    res["volatilidade_20d"] = fatos_precos.volatilidade(g_aj, params_precos.volatilidade_retornos).valor
    res["beta"] = fatos_precos.beta(
        g_aj, ibov, params_precos.beta_pregoes, params_precos.beta_minimo
    ).valor
    res["volume_relativo"] = fatos_precos.volume_relativo(gv, params_precos.volume_pregoes)[1].valor
    res["salto_abertura"] = salto_abertura(g_ab, g_aj, g_fech)
    res["dist_max_52s"], res["dist_min_52s"] = extremos(g_aj, params.extremos_pregoes, params.extremos_minimo)
    res["amplitude"] = amplitude(g_max, g_min, g_fech)
    res["ret_vs_setor"] = ret_vs_setor(ret_dia, mascara, setor_de, cnpj_de, "empresa")
    res["exposicao_dolar"] = exposicao(g_aj, usd, params.exposicao_pregoes, params.exposicao_minimo)
    res["exposicao_petroleo"] = exposicao(g_aj, brent, params.exposicao_pregoes, params.exposicao_minimo)
    return res
