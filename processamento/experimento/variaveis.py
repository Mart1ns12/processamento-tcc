"""Variáveis de preço do dataset do experimento (seção 7.3 da especificação; plano da etapa 5, fase 5).

Reusa as contas de processamento/fatos/precos.py (variação, volatilidade, volume, beta e média do
setor). Funções puras: DataFrames entram, DataFrames saem. Ausência é NaN, nunca 0. Cada grade é
pregão × ticker, só com o valor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.experimento.parametros import ParametrosExperimento
from processamento.fatos import precos as fatos_precos
from processamento.fatos.indices import grade_de_indices
from processamento.fatos.precos import ParametrosPrecos
from processamento.fatos.proventos import ligar_proventos, somas_na_janela


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


def exposicao_de_retorno(g_aj: pd.DataFrame, ret_fator: pd.Series, janela: int, minimo: int,
                         excluir: pd.DataFrame | None = None) -> pd.DataFrame:
    """Beta da ação sobre o retorno diário do fator, vezes esse retorno no dia."""
    b = fatos_precos.beta_sobre_retornos(g_aj, ret_fator, janela, minimo, excluir=excluir).valor
    return b.mul(ret_fator, axis=0)


def exposicao(g_aj: pd.DataFrame, fator: pd.Series, janela: int, minimo: int,
              excluir: pd.DataFrame | None = None) -> pd.DataFrame:
    """Beta da ação sobre o fator (ex.: dólar) vezes o retorno do fator no dia.

    `excluir` (seção 6, "Retorno diário suspeito"): retornos suspeitos da ação, que saem do beta.
    """
    return exposicao_de_retorno(g_aj, fator / fator.shift(1) - 1, janela, minimo, excluir)


def _media_do_setor(r: pd.DataFrame, setor_de: dict, cnpj_de: dict, modo: str) -> pd.DataFrame:
    status = pd.DataFrame(fatos_precos.OK, index=r.index, columns=r.columns)
    return fatos_precos.media_setor(
        fatos_precos.montar_grade(r, status), list(r.columns), setor_de, cnpj_de, modo, agregacao="media"
    ).valor  # o modelo continua com a média (seção 7.3); o painel usa a mediana


def ret_vs_setor(ret: pd.DataFrame, mascara: pd.DataFrame, setor_de: dict, cnpj_de: dict,
                 modo: str) -> pd.DataFrame:
    """Retorno da ação menos a média do setor, só entre as ações da máscara.

    No modo "empresa", o CNPJ inteiro sai da média (ver `fatos.precos.media_setor`).
    """
    r = ret.where(mascara)
    return r - _media_do_setor(r, setor_de, cnpj_de, modo)


MOM_PERTO, MOM_LONGE, LIQUIDEZ_SESSOES, RET_IDIO_PREGOES = 21, 252, 20, 5


def posicao_fechamento(g_fech, g_max, g_min):
    """(fech − mín) ÷ (máx − mín) do dia; NaN com máx ≤ mín ou insumo vazio. Sem máscara de suspeito; não corta em [0, 1]."""
    return ((g_fech - g_min) / (g_max - g_min)).where(g_fech.notna() & (g_max > g_min))


def _base_asof(g, n, defasagem_max):
    return g.ffill().shift(n).where(fatos_precos.defasagem_pregoes(g).shift(n) <= defasagem_max)


def mom_12_1(g_aj, suspeitos, defasagem_max, perto=MOM_PERTO, longe=MOM_LONGE):
    atravessa = fatos_precos.suspeita_na_janela(suspeitos, longe - perto).shift(perto, fill_value=False)
    return _distancia(_base_asof(g_aj, perto, defasagem_max), _base_asof(g_aj, longe, defasagem_max)).mask(atravessa)


def liquidez_20d(g_fech, gv, suspeitos, sessoes=LIQUIDEZ_SESSOES):
    return (g_fech * gv).rolling(sessoes, min_periods=sessoes).median().mask(
        fatos_precos.suspeita_na_janela(suspeitos, sessoes))


def ret_idio(ret_5d, beta_acao, ret_ibov_5d: pd.Series):
    return ret_5d - beta_acao.mul(ret_ibov_5d, axis=0)


def momento_setor(ret, mascara, setor_de, cnpj_de):
    return _media_do_setor(ret.where(mascara), setor_de, cnpj_de, "empresa")


def serie_smll(indices, cal) -> pd.Series:
    """Fechamento do SMLL na grade; NaN onde faltar (tabela ausente ou vazia = tudo NaN). Fora de `cal` não entra."""
    if indices is None or indices.empty:
        return pd.Series(np.nan, index=fatos_precos.indice_pregoes(cal), dtype=float, name="SMLL")
    return grade_de_indices(indices, cal, ("SMLL",))["SMLL"]


DY_SESSOES_SUSPEITA = 20


def dy_12m(ligados, g_fech, suspeitos, meses, sessoes=DY_SESSOES_SUSPEITA):
    """Proventos com data_com em (t − meses, t] ÷ fechamento(t). Sem provento = 0,0 com preço válido (D8).

    NaN sem preço (ou ≤ 0) e com retorno suspeito nas `sessoes` até t: o `fechamento` pode estar errado.
    """
    somas = pd.DataFrame({t: somas_na_janela(ligados, t, g_fech.index, meses) for t in g_fech.columns},
                         index=g_fech.index, columns=g_fech.columns, dtype=float)
    return (somas / g_fech).where(g_fech > 0).mask(fatos_precos.suspeita_na_janela(suspeitos, sessoes))


def dy_12m_de_proventos(proventos, cadastro, mudancas, precos, cal, tickers, meses, params_precos: ParametrosPrecos):
    """Grade de `dy_12m` a partir das tabelas. `proventos` com tickers ORIGINAIS (`unir_mudancas=False`); None = tudo NaN."""
    g_fech = fatos_precos.grade_de_precos(precos, cal, "fechamento", tickers)
    if proventos is None:
        return g_fech * np.nan
    g_aj = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    suspeitos = fatos_precos.retornos_suspeitos(
        g_aj, params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max,
        params_precos.base_defasagem_max_pregoes, params_precos.eventos_retorno_suspeito,
    )
    return dy_12m(ligar_proventos(proventos, cadastro, mudancas), g_fech, suspeitos, meses)


def controle_sorteado(modelo: pd.DataFrame, semente: int) -> pd.Series:
    """Uniforme em [0, 1) por pregão, sobre os tickers do dia em ordem alfabética. Só depende de (semente, data, tickers do dia)."""
    saida = pd.Series(np.nan, index=modelo.index, dtype=float)
    for data, grupo in modelo.groupby("data", sort=False):
        ordem = grupo.sort_values("ticker")
        rng = np.random.default_rng([semente, pd.Timestamp(data).toordinal()])
        saida.loc[ordem.index] = rng.random(len(ordem))
    return saida


def variaveis_de_preco(
    precos: pd.DataFrame,
    cal: list,
    tickers: list[str],
    mascara: pd.DataFrame,
    setor_de: dict,
    cnpj_de: dict,
    params: ParametrosExperimento,
    params_precos: ParametrosPrecos,
    smll: pd.Series | None = None,
) -> dict[str, pd.DataFrame]:
    """As 19 grades de preço e volume do dataset (pregão × ticker, só o valor); seção 7.3.

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
    # retornos suspeitos da ação saem de todas as contas de preço do modelo (seção 6, "Retorno diário suspeito");
    # a janela com o salto fica vazia e o preço não é corrigido
    suspeitos = fatos_precos.retornos_suspeitos(
        g_aj, params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max,
        params_precos.base_defasagem_max_pregoes, params_precos.eventos_retorno_suspeito,
    )

    res: dict[str, pd.DataFrame] = {}
    for nome, n in params.retornos.items():
        res[nome] = fatos_precos.variacao(g_aj, n, params_precos.base_defasagem_max_pregoes).valor.mask(
            fatos_precos.suspeita_na_janela(suspeitos, n)
        )

    ret_dia = fatos_precos.variacao(g_aj, 1, params_precos.base_defasagem_max_pregoes).valor.mask(suspeitos)
    res["volatilidade_20d"] = fatos_precos.volatilidade(
        g_aj, params_precos.volatilidade_retornos, excluir=suspeitos
    ).valor
    res["beta"] = fatos_precos.beta(
        g_aj, ibov, params_precos.beta_pregoes, params_precos.beta_minimo, excluir=suspeitos
    ).valor
    res["volume_relativo"] = fatos_precos.volume_relativo(gv, params_precos.volume_pregoes)[1].valor
    res["salto_abertura"] = salto_abertura(g_ab, g_aj, g_fech).mask(suspeitos)
    # a janela de n preços contém o salto (s−1 e s) de s até s+n−2, ou seja, em n−1 pregões
    no_extremo = fatos_precos.suspeita_na_janela(suspeitos, params.extremos_pregoes - 1)
    dist_max, dist_min = extremos(g_aj, params.extremos_pregoes, params.extremos_minimo)
    res["dist_max_52s"], res["dist_min_52s"] = dist_max.mask(no_extremo), dist_min.mask(no_extremo)
    res["amplitude"] = amplitude(g_max, g_min, g_fech)
    res["ret_vs_setor"] = ret_vs_setor(ret_dia, mascara, setor_de, cnpj_de, "empresa")
    res["exposicao_dolar"] = exposicao(g_aj, usd, params.exposicao_pregoes, params.exposicao_minimo,
                                       excluir=suspeitos)
    res["exposicao_petroleo"] = exposicao(g_aj, brent, params.exposicao_pregoes, params.exposicao_minimo,
                                          excluir=suspeitos)
    N = params_precos.base_defasagem_max_pregoes
    res["posicao_fechamento"] = posicao_fechamento(g_fech, g_max, g_min)
    res["mom_12_1"] = mom_12_1(g_aj, suspeitos, N)
    res["liquidez_20d"] = liquidez_20d(g_fech, gv, suspeitos)
    res["ret_idio_5d"] = ret_idio(res["ret_5d"], res["beta"],
                                  fatos_precos.variacao(ibov.to_frame("IBOV"), RET_IDIO_PREGOES, N).valor["IBOV"])
    res["momento_setor_5d"] = momento_setor(res["ret_5d"], mascara, setor_de, cnpj_de)
    serie = pd.Series(np.nan, index=ibov.index, dtype=float) if smll is None else smll.reindex(ibov.index)
    fator_small = (serie / serie.shift(1) - 1) - (ibov / ibov.shift(1) - 1)
    res["exposicao_small"] = exposicao_de_retorno(g_aj, fator_small, params.exposicao_pregoes,
                                                  params.exposicao_minimo, excluir=suspeitos)
    return res
