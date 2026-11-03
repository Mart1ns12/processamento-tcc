"""Emissor de cada ticker por período (03/11/2026): CNPJ, empresa e tipo na data.

Funções puras, sem banco nem rede. Só importa pandas e `processamento.tickers`; a tabela
`v1-emissores_ticker` é lida por `fontes.ler_emissores`, que não é importado aqui.

Cada linha do emissor tem `ticker`, `ordem`, `ticker_negociado`, `cnpj`, `empresa` e a vigência
`vigencia_inicio`/`vigencia_fim` (inclusiva nas duas pontas; NaT = sem limite). Sem emissores
(None ou vazio), tudo cai no cadastro. Seção 6 da especificação ("Ação → empresa").
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from processamento.tickers import classe, tipo_por_classe

_DIA = pd.Timedelta(days=1)


def _vazio(emissores) -> bool:
    return emissores is None or len(emissores) == 0


def _texto(valor) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _dia(valor) -> pd.Timestamp:
    """Data normalizada (meia-noite); None, NaN e NaT viram NaT."""
    if valor is None or pd.isna(valor):
        return pd.NaT
    return pd.Timestamp(valor).normalize()


def _data_ou_none(valor) -> date | None:
    d = _dia(valor)
    return None if pd.isna(d) else d.date()


def indice(emissores) -> dict[str, list[dict]]:
    """Linhas do emissor por ticker, ordenadas por `ordem` (para não refiltrar o DataFrame)."""
    if _vazio(emissores):
        return {}
    ind: dict[str, list[dict]] = {}
    for linha in emissores.sort_values("ordem", kind="stable").to_dict("records"):
        ind.setdefault(linha["ticker"], []).append(linha)
    return ind


def vigente_em(ind: dict[str, list[dict]], ticker: str, data) -> dict | None:
    """Primeira linha (por ordem) do ticker vigente na data. Data NaT/vazia dá None."""
    d = _dia(data)
    if pd.isna(d):
        return None
    for linha in ind.get(ticker, []):
        ini = _dia(linha["vigencia_inicio"])
        fim = _dia(linha["vigencia_fim"])
        if (pd.isna(ini) or ini <= d) and (pd.isna(fim) or fim >= d):
            return linha
    return None


def vigente(emissores, ticker: str, data) -> dict | None:
    """Linha do emissor vigente do ticker na data (ver `vigente_em`)."""
    return vigente_em(indice(emissores), ticker, data)


def cnpj_na_data(emissores, ticker: str, data, cnpj_cadastro: str | None) -> str | None:
    """CNPJ do emissor vigente, se for texto; senão o do cadastro."""
    linha = vigente(emissores, ticker, data)
    if linha is not None and _texto(linha.get("cnpj")):
        return linha["cnpj"]
    return cnpj_cadastro


def _tipo_da_linha(linha: dict, ticker: str, tipo_cadastro: str | None) -> str | None:
    """Tipo do período: pelo código negociado da linha, se for outro; senão o do cadastro."""
    negociado = linha.get("ticker_negociado")
    if _texto(negociado) and negociado != ticker:
        tipo = tipo_por_classe(classe(negociado))
        if tipo is not None:
            return tipo
    return tipo_cadastro


def tipo_na_data(emissores, ticker: str, data, tipo_cadastro: str | None) -> str | None:
    """Tipo de ação na data (JBSS3 -> ON até 08/06/2025); fora de vigência, o do cadastro."""
    linha = vigente(emissores, ticker, data)
    if linha is None:
        return tipo_cadastro
    return _tipo_da_linha(linha, ticker, tipo_cadastro)


def cadastro_na_data(cadastro: pd.DataFrame, emissores, data) -> pd.DataFrame:
    """Cópia do cadastro com `cnpj`, `empresa` e `tipo_acao` do emissor vigente na data.

    Só as linhas com emissor vigente mudam. A entrada não é alterada.
    """
    saida = cadastro.copy()
    if _vazio(emissores):
        return saida
    ind = indice(emissores)
    colunas = [c for c in ("cnpj", "empresa", "tipo_acao") if c in saida.columns]
    valores = {c: saida[c].astype(object).tolist() for c in colunas}
    mudou: set[str] = set()
    for i, ticker in enumerate(saida["ticker"]):
        linha = vigente_em(ind, ticker, data)
        if linha is None:
            continue
        if "cnpj" in valores and _texto(linha.get("cnpj")):
            valores["cnpj"][i] = linha["cnpj"]
            mudou.add("cnpj")
        if "empresa" in valores and _texto(linha.get("empresa")):
            valores["empresa"][i] = linha["empresa"]
            mudou.add("empresa")
        if "tipo_acao" in valores:
            valores["tipo_acao"][i] = _tipo_da_linha(linha, ticker, valores["tipo_acao"][i])
            mudou.add("tipo_acao")
    for c in mudou:
        saida[c] = valores[c]
    return saida


def fronteiras(emissores) -> list[pd.Timestamp]:
    """Datas em que algum emissor começa ou deixa de valer: cada `vigencia_inicio` e cada `vigencia_fim` + 1 dia."""
    if _vazio(emissores):
        return []
    marcos: set[pd.Timestamp] = set()
    for ini, fim in zip(emissores["vigencia_inicio"], emissores["vigencia_fim"]):
        ini = _dia(ini)
        fim = _dia(fim)
        if not pd.isna(ini):
            marcos.add(ini)
        if not pd.isna(fim):
            marcos.add(fim + _DIA)
    return sorted(marcos)


def trechos(idx: pd.DatetimeIndex, emissores) -> list[pd.DatetimeIndex]:
    """Divide `idx` nas fronteiras do emissor: cada trecho tem o mesmo emissor em todas as datas."""
    if _vazio(emissores):
        return [idx]
    pos = sorted(set(idx.searchsorted(pd.DatetimeIndex(fronteiras(emissores)), side="left")))
    return [idx[a:b] for a, b in zip([0, *pos], [*pos, len(idx)]) if b > a]


def _pares_negociado(emissores) -> list[tuple[str, str]]:
    """(ticker_negociado, ticker) de cada linha em que o código negociado é outro."""
    if _vazio(emissores):
        return []
    pares = []
    for ticker, negociado in zip(emissores["ticker"], emissores["ticker_negociado"]):
        if _texto(negociado) and negociado != ticker:
            pares.append((negociado, ticker))
    return pares


def trocas_cobertas(emissores) -> frozenset[tuple[str, str]]:
    """(antigo, novo) das trocas de código que o emissor descreve (JBSS3 -> JBSS32, NTCO3 -> NATU3)."""
    return frozenset(_pares_negociado(emissores))


def ticker_de_negociado(emissores) -> dict[str, str]:
    """Código negociado -> ticker atual. Um código negociado que leva a mais de um ticker fica de fora."""
    de: dict[str, set[str]] = {}
    for negociado, ticker in _pares_negociado(emissores):
        de.setdefault(negociado, set()).add(ticker)
    return {negociado: next(iter(tickers)) for negociado, tickers in de.items() if len(tickers) == 1}


def tipos_por_periodo(emissores) -> dict[str, list[tuple[date | None, date | None, str]]]:
    """Tipo por período das linhas com código negociado diferente e classe de tipo conhecida."""
    saida: dict[str, list[tuple[date | None, date | None, str]]] = {}
    for ticker, linhas in indice(emissores).items():
        for linha in linhas:
            negociado = linha.get("ticker_negociado")
            if not _texto(negociado) or negociado == ticker:
                continue
            tipo = tipo_por_classe(classe(negociado))
            if tipo is None:
                continue
            saida.setdefault(ticker, []).append(
                (_data_ou_none(linha["vigencia_inicio"]), _data_ou_none(linha["vigencia_fim"]), tipo)
            )
    return saida


def _chave_inicio(linha: dict) -> tuple[int, pd.Timestamp]:
    """Ordena por vigência de início, com NaT primeiro."""
    ini = _dia(linha["vigencia_inicio"])
    return (0, pd.Timestamp(0)) if pd.isna(ini) else (1, ini)


def _consecutivas(emissores):
    """Para cada ticker, pares (ticker, anterior, seguinte) de linhas ordenadas por início (NaT primeiro)."""
    for ticker, linhas in sorted(indice(emissores).items(), key=lambda par: par[0]):
        ordenadas = sorted(linhas, key=_chave_inicio)
        for anterior, seguinte in zip(ordenadas, ordenadas[1:]):
            yield ticker, anterior, seguinte


def sobreposicoes(emissores) -> list[str]:
    """Vigências consecutivas do mesmo ticker que se sobrepõem (fim anterior NaT, início seguinte NaT ou início ≤ fim)."""
    saida = []
    for ticker, anterior, seguinte in _consecutivas(emissores):
        fim = _dia(anterior["vigencia_fim"])
        ini = _dia(seguinte["vigencia_inicio"])
        if pd.isna(fim) or pd.isna(ini) or ini <= fim:
            saida.append(f"{ticker}: ordem {int(anterior['ordem'])} e ordem {int(seguinte['ordem'])}")
    return saida


def lacunas(emissores) -> list[str]:
    """Dias sem emissor entre duas vigências consecutivas do mesmo ticker."""
    saida = []
    for ticker, anterior, seguinte in _consecutivas(emissores):
        fim = _dia(anterior["vigencia_fim"])
        ini = _dia(seguinte["vigencia_inicio"])
        if pd.isna(fim) or pd.isna(ini):
            continue
        if fim + _DIA < ini:
            saida.append(
                f"{ticker}: sem emissor de {(fim + _DIA):%Y-%m-%d} a {(ini - _DIA):%Y-%m-%d}"
            )
    return saida


def cnpj_por_linha(emissores, tickers: pd.Series, datas: pd.Series, padrao: pd.Series) -> pd.Series:
    """CNPJ de cada linha (ticker e data posicionais): o do emissor vigente, senão `padrao`."""
    resultado = padrao.astype(object).to_numpy(copy=True)
    if _vazio(emissores):
        return pd.Series(resultado, index=padrao.index, dtype=object)
    tk = pd.Series(list(tickers), dtype=object).to_numpy()
    dt = pd.DatetimeIndex(pd.to_datetime(list(datas))).normalize()
    for _, linha in emissores.iterrows():
        cnpj = linha["cnpj"]
        if not _texto(cnpj):
            continue
        mascara = tk == linha["ticker"]
        ini = _dia(linha["vigencia_inicio"])
        fim = _dia(linha["vigencia_fim"])
        if not pd.isna(ini):
            mascara &= dt >= ini
        if not pd.isna(fim):
            mascara &= dt <= fim
        resultado[mascara] = cnpj
    return pd.Series(resultado, index=padrao.index, dtype=object)
