"""Checagem diária da seção 6 (plano da etapa 8, fase 7; seção 9 do plano): avisos no `execucao`.

Avisos só informam, nunca bloqueiam nada. Funções puras: DataFrames e dicionários entram, lista de
textos sai. Nenhuma acessa banco ou rede. Ausência é NaN ou status `indisponivel`; volume vazio
não é volume zero.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from processamento.experimento.relatorio import pct
from processamento.fatos.precos import grade_de_precos, retornos_diarios
from processamento.rotina.parametros import ParametrosChecagem

INDISPONIVEL = "indisponivel"

# (caminho no registro, nome no aviso); a ordem é a dos avisos.
_MERCADO_CHECADO = (
    (("IBOV", "fechamento"), "IBOV.fechamento"),
    (("USDBRL", "fechamento"), "USDBRL.fechamento"),
    (("BRENT", "fechamento"), "BRENT.fechamento"),
    (("cdi_dia",), "cdi_dia"),
    (("ipca_12m",), "ipca_12m"),
)
_ACOES_CHECADO = (
    (("cotacao", "fechamento"), "cotacao.fechamento"),
    (("rentabilidade", "d1"), "rentabilidade.d1"),
    (("volume", "total"), "volume.total"),
    (("volatilidade_20d",), "volatilidade_20d"),
    (("beta",), "beta"),
    (("pvp",), "pvp"),
    (("dividend_yield",), "dividend_yield"),
)


def _posicao(cal: list, t: date) -> int:
    """Posição de t no calendário (levanta ValueError se t não for pregão do calendário)."""
    dias = [pd.Timestamp(d).normalize() for d in cal]
    return dias.index(pd.Timestamp(t).normalize())


def _data(t: date) -> str:
    """Data no formato AAAA-MM-DD, como nos textos da seção 9."""
    return pd.Timestamp(t).strftime("%Y-%m-%d")


def _lista(itens: list[str], params: ParametrosChecagem) -> str:
    """Itens separados por vírgula; acima de `max_tickers_por_aviso`, corta e diz quantos faltam."""
    maximo = params.max_tickers_por_aviso
    if len(itens) <= maximo:
        return ", ".join(itens)
    return ", ".join(itens[:maximo]) + f" e mais {len(itens) - maximo}"


def _status(registro: dict, caminho: tuple[str, ...]) -> str | None:
    """Status da folha em `caminho` do registro; None se a folha não existir."""
    atual: object = registro
    for chave in caminho:
        if not isinstance(atual, dict) or chave not in atual:
            return None
        atual = atual[chave]
    return atual.get("status") if isinstance(atual, dict) else None


def avisos_do_dia(precos: pd.DataFrame, cal: list[date], t: date, pares: list[str],
                  params: ParametrosChecagem) -> list[str]:
    """Avisos dos preços em t, nesta ordem: poucas ações, retorno, volume zero, preço parado.

    `precos`: colunas data, ticker, fechamento, fechamento_ajustado, volume (IBOV incluído, para o
    preço parado). `pares`: ações do painel (ON, PN, UNIT, sem excluídos). Regras que precisam de
    um pregão anterior ou de N pregões não rodam se eles faltarem no calendário.
    """
    dias = list(cal)
    i = _posicao(dias, t)
    ts = pd.Timestamp(t).normalize()
    txt_t = _data(t)
    pares = list(dict.fromkeys(pares))
    avisos: list[str] = []

    g_aj = grade_de_precos(precos, dias, "fechamento_ajustado", pares)
    g_vol = grade_de_precos(precos, dias, "volume", pares)
    g_fech = grade_de_precos(precos, dias, "fechamento", list(dict.fromkeys([*pares, "IBOV"])))

    com_preco = int(g_aj.loc[ts].notna().sum())
    total = len(pares)
    if com_preco < params.acoes_minimo_fracao * total:
        avisos.append(f"Checagem: só {com_preco} de {total} ações (ON, PN e UNIT) com preço em {txt_t}.")

    retorno_t = retornos_diarios(g_aj).loc[ts]
    grandes = [
        f"{tk} ({pct(v)})"
        for tk, v in retorno_t.sort_index().items()
        if np.isfinite(v) and abs(v) > params.retorno_maximo_abs
    ]
    if grandes:
        limite = pct(params.retorno_maximo_abs, 0)
        avisos.append(f"Checagem: retorno do dia acima de {limite} em módulo em {txt_t}: "
                      f"{_lista(grandes, params)}.")

    volume_t = g_vol.loc[ts]
    zerados = [tk for tk, v in volume_t.sort_index().items() if v == 0]
    if zerados:
        avisos.append(f"Checagem: volume zero em {txt_t}: {_lista(zerados, params)}.")

    n = params.preco_parado_pregoes
    if i - n + 1 >= 0:
        janela = g_fech.iloc[i - n + 1:i + 1]
        parados = [
            tk for tk in sorted(g_fech.columns)
            if janela[tk].notna().all() and janela[tk].nunique() == 1
        ]
        if parados:
            avisos.append(f"Checagem: preço parado (mesmo fechamento nos últimos {n} pregões até {txt_t}): "
                          f"{_lista(parados, params)}.")
    return avisos


def avisos_indicadores(mercado: dict | None, resumo: list[dict] | None, t: date,
                       params: ParametrosChecagem) -> list[str]:
    """Avisos de indicadores vazios: um por indicador, primeiro o mercado e depois as ações.

    `mercado`: registro de `mercado_dia` (ou None). `resumo`: lista de `resumo_acao` (ou None).
    Só `indisponivel` conta; `historico_insuficiente` não é vazio. `params` fica na assinatura da
    fase 7; estes avisos não listam tickers, então não usa o limite.
    """
    txt_t = _data(t)
    avisos: list[str] = []
    if mercado is not None:
        for caminho, nome in _MERCADO_CHECADO:
            if _status(mercado, caminho) == INDISPONIVEL:
                avisos.append(f"Checagem: indicador vazio em {txt_t}: {nome}.")
    if resumo:
        for caminho, nome in _ACOES_CHECADO:
            if all(_status(acao, caminho) == INDISPONIVEL for acao in resumo):
                avisos.append(f"Checagem: indicador vazio em todas as ações em {txt_t}: {nome}.")
    return avisos
