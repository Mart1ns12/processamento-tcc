"""Proventos por ação e ações emitidas por data (seções 5 e 6 da especificação).

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Ausência é NaN + `status` (nunca 0), salvo o 0.0 "ok" de quem não teve provento na janela
(decisão D8) e o total pago sem eventos. `ticker` é o código original do provento;
`ticker_atual` é o código após as mudanças de ticker (`tickers.aplicar_mudancas`).
Proventos de BDR não são coletados: o yield e a soma de BDR saem indisponíveis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.fatos.precos import INDISPONIVEL, OK
from processamento.tickers import aplicar_mudancas, classe, ligar_a_cnpj, tipo_por_classe

_TIPOS_CLASSE_PAGA = ("ON", "PN")  # payout: a unit fica de fora (já é a soma de ON e PN)


def inicio_janela(t, meses: int) -> pd.Timestamp:
    """Início da janela de `meses` que termina em `t`. A janela é (inicio, t]."""
    return pd.Timestamp(t) - pd.DateOffset(months=meses)


def ligar_proventos(proventos: pd.DataFrame, cadastro: pd.DataFrame, mudancas: dict[str, str]) -> pd.DataFrame:
    """Liga cada provento à empresa e marca se ele conta para o ticker atual.

    Colunas extras:
    - `ticker_atual`: código após as mudanças de ticker;
    - `cnpj` e `ligacao`: empresa do código atual (`tickers.ligar_a_cnpj`);
    - `tipo_classe`: ON, PN, UNIT ou BDR pela classe do ticker ORIGINAL;
    - `mesma_classe`: a classe do ticker original é a do ticker atual (ex.: KKKK6 -> KKKK3 não é);
    - `duplicada`: linha trocada, da mesma classe, que colide com provento já lançado no ticker
      atual (mesmo tipo e data_com); mesma regra de `fontes.unir_historicos`;
    - `conta_no_ticker`: `mesma_classe` e não `duplicada`.
    """
    por_ticker = {t: (None if pd.isna(c) else c) for t, c in zip(cadastro["ticker"], cadastro["cnpj"])}
    df = proventos.copy()
    atuais = [aplicar_mudancas(t, mudancas) for t in df["ticker"]]
    ligados = [ligar_a_cnpj(a, por_ticker, {}) for a in atuais]
    mesma = [classe(t) == classe(a) for t, a in zip(df["ticker"], atuais)]
    trocada = [t != a for t, a in zip(df["ticker"], atuais)]
    lancados = set(zip(df["ticker"], df["tipo"], df["data_com"]))
    duplicada = [
        bool(tr and mc and ((a, tipo, data) in lancados))
        for tr, mc, a, tipo, data in zip(trocada, mesma, atuais, df["tipo"], df["data_com"])
    ]
    df["ticker_atual"] = atuais
    df["cnpj"] = [c for c, _ in ligados]
    df["ligacao"] = [motivo for _, motivo in ligados]
    df["tipo_classe"] = [tipo_por_classe(classe(t)) for t in df["ticker"]]
    df["mesma_classe"] = pd.Series(mesma, index=df.index, dtype=bool)
    df["duplicada"] = pd.Series(duplicada, index=df.index, dtype=bool)
    df["conta_no_ticker"] = df["mesma_classe"] & ~df["duplicada"]
    return df


def _do_ticker(ligados: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Linhas que contam para o ticker atual (`ticker_atual` igual e `conta_no_ticker`)."""
    return ligados[(ligados["ticker_atual"] == ticker) & ligados["conta_no_ticker"]]


def _soma_na_janela(ligados: pd.DataFrame, ticker: str, inicio, fim) -> float:
    """Soma de `valor_por_acao` do ticker com data_com em (inicio, fim]."""
    linhas = _do_ticker(ligados, ticker)
    na_janela = linhas[(linhas["data_com"] > inicio) & (linhas["data_com"] <= pd.Timestamp(fim))]
    return float(na_janela["valor_por_acao"].sum())


def somas_na_janela(ligados: pd.DataFrame, ticker: str, datas: pd.DatetimeIndex, meses: int) -> np.ndarray:
    """Soma de `valor_por_acao` do ticker com data_com em (d − meses, d], para cada d de `datas`.

    Mesma conta de `_soma_na_janela` + `inicio_janela`, sem repetir o filtro por pregão. data_com depois de d nunca entra.
    """
    linhas = _do_ticker(ligados, ticker)
    linhas = linhas[linhas["data_com"].notna()].sort_values("data_com")
    com = pd.DatetimeIndex(linhas["data_com"])
    valores = linhas["valor_por_acao"].to_numpy(dtype=float)
    fim = com.searchsorted(datas, side="right")
    inicio = com.searchsorted(datas - pd.DateOffset(months=meses), side="right")
    return np.array([np.nansum(valores[i:j]) for i, j in zip(inicio, fim)], dtype=float)


def dividend_yield(ligados: pd.DataFrame, ticker: str, tipo_acao: str | None, fech, t, meses: int) -> tuple[float, str]:
    """Yield do ticker: proventos com data_com em (t - meses, t] divididos pelo `fechamento` (seção 5).

    BDR: indisponível. Cotação NaN ou ≤ 0: indisponível. Sem provento na janela: 0.0 com status ok (D8).
    """
    if tipo_acao == "BDR":
        return float("nan"), INDISPONIVEL
    if pd.isna(fech) or fech <= 0:
        return float("nan"), INDISPONIVEL
    total = _soma_na_janela(ligados, ticker, inicio_janela(t, meses), t)
    return total / fech, OK


def acoes_disponiveis(acoes_emitidas: pd.DataFrame, balancos: pd.DataFrame, t) -> pd.DataFrame:
    """Linhas de ações emitidas já conhecidas em `t` (D4).

    Ações não têm data de entrega: a linha vale em `t` se existir balanço do mesmo CNPJ com
    data_fim_periodo igual a data_referencia e data_entrega ≤ t.
    """
    t_ts = pd.Timestamp(t)
    entregues = balancos[balancos["data_entrega"] <= t_ts]
    chaves = set(zip(entregues["cnpj"], entregues["data_fim_periodo"]))
    mascara = pd.Series(
        [(c, d) in chaves for c, d in zip(acoes_emitidas["cnpj"], acoes_emitidas["data_referencia"])],
        index=acoes_emitidas.index, dtype=bool,
    )
    return acoes_emitidas[mascara].sort_values(["cnpj", "data_referencia"]).reset_index(drop=True)


def acoes_na_data(disponiveis: pd.DataFrame, cnpj: str, data) -> tuple[float, float, str]:
    """Quantidades (ON, PN) da empresa na data: a mais recente ≤ data.

    Sem linha anterior à data, usa a de menor data_referencia (fallback, D3). Sem linha da empresa,
    ou com quantidade NaN, sai indisponível. `qtd_pn` igual a zero é válido.
    """
    linhas = disponiveis[disponiveis["cnpj"] == cnpj]
    if linhas.empty:
        return float("nan"), float("nan"), INDISPONIVEL
    d = pd.Timestamp(data)
    anteriores = linhas[linhas["data_referencia"] <= d]
    if anteriores.empty:
        escolhida = linhas.sort_values("data_referencia").iloc[0]
    else:
        escolhida = anteriores.sort_values("data_referencia").iloc[-1]
    qtd_on, qtd_pn = escolhida["qtd_on"], escolhida["qtd_pn"]
    if pd.isna(qtd_on) or pd.isna(qtd_pn):
        return float("nan"), float("nan"), INDISPONIVEL
    return float(qtd_on), float(qtd_pn), OK


def total_pago(ligados: pd.DataFrame, disponiveis: pd.DataFrame, cnpj: str | None,
               inicio_exclusivo, fim_inclusivo) -> tuple[float, str]:
    """Total pago à empresa com data_com em (inicio, fim]: base do payout (seção 6).

    Entram só as linhas sem `duplicada` de classe ON ou PN (a unit fica de fora). Por evento
    (tipo, data_com): soma dos ON vezes as ações ON, mais a média dos PN que têm linha no evento
    vezes as ações PN (D2). Sem eventos: 0.0 com status ok. Sem ações disponíveis em algum evento:
    indisponível. Sem CNPJ: indisponível.
    """
    if cnpj is None or pd.isna(cnpj):
        return float("nan"), INDISPONIVEL
    inicio, fim = pd.Timestamp(inicio_exclusivo), pd.Timestamp(fim_inclusivo)
    linhas = ligados[
        (ligados["cnpj"] == cnpj)
        & ~ligados["duplicada"]
        & ligados["tipo_classe"].isin(_TIPOS_CLASSE_PAGA)
        & (ligados["data_com"] > inicio)
        & (ligados["data_com"] <= fim)
    ]
    if linhas.empty:
        return 0.0, OK
    total = 0.0
    for (_, data_com), evento in linhas.groupby(["tipo", "data_com"]):
        on = evento.loc[evento["tipo_classe"] == "ON", "valor_por_acao"]
        pn = evento.loc[evento["tipo_classe"] == "PN", "valor_por_acao"]
        qtd_on, qtd_pn, status = acoes_na_data(disponiveis, cnpj, data_com)
        if status != OK:
            return float("nan"), INDISPONIVEL
        total += float(on.sum()) * qtd_on
        if len(pn):
            total += float(pn.mean()) * qtd_pn
    return total, OK


def soma_por_ano(ligados: pd.DataFrame, ticker: str, tipo_acao: str | None, t, anos: int) -> pd.DataFrame:
    """Soma de proventos por ano-calendário: do ano de `t` e dos `anos` - 1 anteriores.

    Colunas: ticker, ano, valor, status. Ano sem provento vale 0.0 com status ok.
    BDR: todas as linhas saem indisponíveis.
    """
    t_ts = pd.Timestamp(t)
    linhas = _do_ticker(ligados, ticker)
    datas = pd.to_datetime(linhas["data_com"])
    registros = []
    for ano in range(t_ts.year - anos + 1, t_ts.year + 1):
        if tipo_acao == "BDR":
            valor, status = float("nan"), INDISPONIVEL
        else:
            mascara = (datas.dt.year == ano) & (datas <= t_ts)
            valor, status = float(linhas.loc[mascara, "valor_por_acao"].sum()), OK
        registros.append({"ticker": ticker, "ano": ano, "valor": valor, "status": status})
    return pd.DataFrame(registros, columns=["ticker", "ano", "valor", "status"])


def lista_proventos(ligados: pd.DataFrame, tickers: list[str], t) -> pd.DataFrame:
    """Proventos dos tickers atuais com data_com ≤ t, sem duplicadas.

    Colunas: ticker (o atual), tipo, data_com, data_pagamento, valor_por_acao. Ordenado por
    ticker, data_com e tipo.
    """
    fim = pd.Timestamp(t)
    linhas = ligados[
        ligados["ticker_atual"].isin(tickers) & ligados["conta_no_ticker"] & (ligados["data_com"] <= fim)
    ]
    saida = linhas[["ticker_atual", "tipo", "data_com", "data_pagamento", "valor_por_acao"]]
    saida = saida.rename(columns={"ticker_atual": "ticker"})
    return saida.sort_values(["ticker", "data_com", "tipo"]).reset_index(drop=True)
