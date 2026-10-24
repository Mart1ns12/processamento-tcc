"""P/L, P/VP e dividend yield diários (seções 5 e 6 da especificação; etapa 7, fase 2).

Função pura: DataFrames entram, grades saem. Mesmas regras e status de
`fundamentos.calcular_fundamentos_no_dia`, mas calculados por trechos entre entregas de balanço:
entre duas entregas do CNPJ, a foto do balanço e as ações emitidas não mudam, então são calculadas
uma vez por trecho. Ausência é NaN + `status` (nunca 0).
"""

from __future__ import annotations

import bisect
import math

import numpy as np
import pandas as pd

from processamento.exclusoes import Exclusoes
from processamento.fatos.fundamentos import (
    LUCRO_NEGATIVO,
    DadosFundamentos,
    ParametrosFundamentos,
    foto_dentro_do_prazo,
    indicadores_empresa,
    valor_de_mercado,
)
from processamento.fatos.precos import (
    INDISPONIVEL,
    OK,
    Grade,
    grade_de_precos,
    indice_pregoes,
    mapas_cadastro,
    tickers_do_painel,
)
from processamento.fatos.proventos import _do_ticker, acoes_disponiveis, acoes_na_data, inicio_janela, ligar_proventos
from processamento.fatos.trimestres import foto_balanco

_MANTEM_VALOR = (OK, LUCRO_NEGATIVO)  # mesma regra de `fundamentos._grade_do_dia`


def _grade(valor: np.ndarray, status: np.ndarray, idx: pd.DatetimeIndex, tickers: list[str]) -> Grade:
    """Grade com o valor mantido só onde o status é ok ou lucro_negativo (NaN no resto)."""
    mantem = np.isin(status, _MANTEM_VALOR)
    return Grade(
        pd.DataFrame(np.where(mantem, valor, np.nan), index=idx, columns=tickers, dtype=float),
        pd.DataFrame(status, index=idx, columns=tickers, dtype=object),
    )


def _yield_diario(ligados: pd.DataFrame, tickers: list[str], tipo_de: dict, fech: np.ndarray,
                  idx: pd.DatetimeIndex, params: ParametrosFundamentos) -> tuple[np.ndarray, np.ndarray]:
    """(valor, status) do yield de cada ticker em cada pregão; a janela é (t - meses, t]."""
    valor = np.full(fech.shape, np.nan)
    status = np.full(fech.shape, INDISPONIVEL, dtype=object)
    datas_ns = idx.to_numpy(dtype="datetime64[ns]")
    ini_ns = np.array([inicio_janela(t, params.meses_janela) for t in idx], dtype="datetime64[ns]")
    for j, ticker in enumerate(tickers):
        if tipo_de.get(ticker) == "BDR":
            continue
        linhas = _do_ticker(ligados, ticker).sort_values("data_com")
        datas_com = pd.to_datetime(linhas["data_com"]).to_numpy(dtype="datetime64[ns]")
        por_acao = linhas["valor_por_acao"].fillna(0.0).to_numpy(dtype=float)  # soma ignora vazio, como `.sum()`
        acumulado = np.concatenate([[0.0], np.cumsum(por_acao)])
        soma = (acumulado[np.searchsorted(datas_com, datas_ns, side="right")]
                - acumulado[np.searchsorted(datas_com, ini_ns, side="right")])
        cotacao = fech[:, j]
        com_preco = ~np.isnan(cotacao) & (cotacao > 0)
        divisor = np.where(com_preco, cotacao, 1.0)
        valor[:, j] = np.where(com_preco, soma / divisor, np.nan)
        status[:, j] = np.where(com_preco, OK, INDISPONIVEL)
    return valor, status


def multiplos_diarios(dados: DadosFundamentos, cal: list, exclusoes: Exclusoes,
                      params: ParametrosFundamentos, desde=None) -> dict[str, Grade]:
    """P/L, P/VP e yield de todos os tickers do painel em cada pregão de `cal`.

    Chaves "pl", "pvp" e "dividend_yield"; cada uma é uma `Grade` pregão × ticker (ordem de
    `tickers_do_painel`). `desde` (S19): só os pregões com data >= desde; as tabelas continuam
    inteiras (foto do balanço e janela de 12 meses usam o histórico todo). BDR: P/L, P/VP e yield
    sempre indisponíveis (D9). Sem CNPJ: P/L e P/VP indisponíveis.
    """
    tickers = tickers_do_painel(dados.cadastro, exclusoes)
    idx = indice_pregoes(cal)
    if desde is not None:
        idx = idx[idx >= pd.Timestamp(desde)]
    if len(idx) == 0:
        vazio = pd.DataFrame(index=idx, columns=tickers, dtype=float)
        return {k: Grade(vazio.copy(), vazio.copy().astype(object)) for k in ("pl", "pvp", "dividend_yield")}

    _, cnpj_de = mapas_cadastro(dados.cadastro)
    tipo_de = dict(zip(dados.cadastro["ticker"], dados.cadastro["tipo_acao"]))
    gf = grade_de_precos(dados.precos, list(idx), "fechamento", tickers)
    fech = gf.to_numpy(dtype=float)
    fechs = gf.to_dict("records")  # um dict por pregão: ticker -> fechamento
    lig = ligar_proventos(dados.proventos, dados.cadastro, dados.mudancas)

    dy_valor, dy_status = _yield_diario(lig, tickers, tipo_de, fech, idx, params)

    shape = fech.shape
    pl_valor, pl_status = np.full(shape, np.nan), np.full(shape, INDISPONIVEL, dtype=object)
    pvp_valor, pvp_status = np.full(shape, np.nan), np.full(shape, INDISPONIVEL, dtype=object)

    colunas_de_cnpj: dict[str, list[int]] = {}
    for j, ticker in enumerate(tickers):
        cnpj = cnpj_de.get(ticker)
        if cnpj and tipo_de.get(ticker) != "BDR":  # D9: BDR fica indisponível
            colunas_de_cnpj.setdefault(cnpj, []).append(j)

    for cnpj, colunas in sorted(colunas_de_cnpj.items()):
        cad_c = dados.cadastro[dados.cadastro["cnpj"] == cnpj]
        entregas = sorted({
            pd.Timestamp(d) for d in dados.balancos.loc[dados.balancos["cnpj"] == cnpj, "data_entrega"].dropna()
        })
        cache: dict[int, tuple] = {}
        for i, ts in enumerate(idx):
            trecho = bisect.bisect_right(entregas, ts) - 1
            if trecho not in cache:  # o 1º pregão do trecho calcula; o resto do trecho reusa
                cache[trecho] = (
                    foto_balanco(dados.balancos, cnpj, ts, exclusoes),
                    acoes_na_data(acoes_disponiveis(dados.acoes_emitidas, dados.balancos, ts), cnpj, ts),
                )
            foto, qtd = cache[trecho]
            foto = foto_dentro_do_prazo(foto, ts, params.balanco_idade_max_meses)  # por dia: a idade cruza o limite dentro do trecho
            vm = valor_de_mercado(cnpj, fechs[i], cad_c, tickers, qtd)
            ind = indicadores_empresa(foto, vm, (math.nan, INDISPONIVEL), False,
                                      pvp_minimo=params.pvp_minimo_plausivel)
            pl_valor[i, colunas], pl_status[i, colunas] = ind["pl.valor"]
            pvp_valor[i, colunas], pvp_status[i, colunas] = ind["pvp.valor"]

    return {
        "pl": _grade(pl_valor, pl_status, idx, tickers),
        "pvp": _grade(pvp_valor, pvp_status, idx, tickers),
        "dividend_yield": _grade(dy_valor, dy_status, idx, tickers),
    }
