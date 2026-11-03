"""Seções de emissores e de ações emitidas do diagnóstico (03/11/2026).

"Emissores por período" lê `v1-emissores_ticker` com `fontes.ler_tabela` (sem `ler_emissores`, que levanta
erro na sobreposição: aqui a sobreposição vira divergência). "Ações emitidas: base atual e eventos" cruza
`v1-acoes_emitidas` com `v1-eventos_acoes`. As funções puras não fazem I/O; o SQL sai só pelo `ler`
(via `fontes`).

Este módulo importa os helpers de `temas.py`; por isso `temas.py` importa daqui só dentro das funções
(import local), para não criar ciclo.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date

import pandas as pd

from processamento import emissores as emissores_mod
from processamento import fontes
from processamento.diagnostico.regras import adicionar_tabela, div, nova_secao, texto
from processamento.diagnostico.temas import _existe, _nome, _pulada, _registros

COLUNAS_EMISSORES = [
    "ticker", "ordem", "ticker_negociado", "cnpj", "empresa", "vigencia_inicio", "vigencia_fim", "fator_acoes",
]
COLUNAS_COERENCIA = [
    "cnpj", "data_referencia", "data_entrega", "qtd_total", "fator_eventos", "fator_acoes", "esperado",
    "base_total", "razao",
]
TOLERANCIA_PADRAO = 0.01


# ---------------------------------------------------------------------------
# Funções puras (sem banco)
# ---------------------------------------------------------------------------

def problemas_emissores(emissores, cadastro: pd.DataFrame) -> dict:
    """Problemas da tabela de emissores em relação ao cadastro: sobreposição, lacuna e CNPJ divergente.

    Chaves: `sobrepostas`, `lacunas`, `difere_cadastro` [(ticker, cnpj_vigente_hoje, cnpj_cadastro)],
    `sem_emissor` (tickers do cadastro sem linha) e `cnpj_de_outra_empresa` [(ticker, cnpj, outro_ticker)].
    """
    indice = emissores_mod.indice(emissores)
    cnpj_cad = {texto(t): texto(c) for t, c in zip(cadastro["ticker"], cadastro["cnpj"]) if texto(t) is not None}

    # vigente hoje: a linha sem vigencia_fim de maior ordem
    vigente_hoje = {}
    for ticker, linhas in indice.items():
        abertas = [linha for linha in linhas if pd.isna(linha["vigencia_fim"])]
        if abertas:
            vigente_hoje[ticker] = max(abertas, key=lambda linha: linha["ordem"])
    difere = []
    for ticker in sorted(vigente_hoje):
        cad = cnpj_cad.get(ticker)
        vig = texto(vigente_hoje[ticker]["cnpj"])
        if cad is not None and vig is not None and vig != cad:
            difere.append((ticker, vig, cad))

    sem_emissor = sorted(t for t in cnpj_cad if t not in indice)

    dono: dict[str, list[str]] = {}
    for ticker, cnpj in cnpj_cad.items():
        if cnpj is not None:
            dono.setdefault(cnpj, []).append(ticker)
    outra = set()
    for ticker, linhas in indice.items():
        cad = cnpj_cad.get(ticker)
        if cad is None:
            continue
        for linha in linhas:
            cnpj = texto(linha["cnpj"])
            if cnpj is None or cnpj == cad:
                continue
            for outro in dono.get(cnpj, []):
                if outro != ticker:
                    outra.add((ticker, cnpj, outro))

    return {
        "sobrepostas": emissores_mod.sobreposicoes(emissores),
        "lacunas": emissores_mod.lacunas(emissores),
        "difere_cadastro": difere,
        "sem_emissor": sem_emissor,
        "cnpj_de_outra_empresa": sorted(outra),
    }


def coerencia_acoes_eventos(acoes, eventos, emissores, tolerancia: float = TOLERANCIA_PADRAO) -> pd.DataFrame:
    """Linhas de `v1-acoes_emitidas` (ok) cuja base atual não bate com quantidade × eventos × fator_acoes.

    `fator_eventos`: produto dos fatores únicos por (data_com, tipo, fator) dos eventos do mesmo CNPJ com
    data_com depois da entrega, ignorando BONIFICACAO com `isin_emitido` preenchido e diferente de `isin`.
    `fator_acoes`: o fator do emissor com esse CNPJ (sem linha: 1,0; mais de um distinto: a linha é pulada).
    Linhas sem data de entrega também são puladas (a ausência já é divergência de `acoes_sem_entrega`).
    Devolve só `|razao − 1| > tolerancia`.
    """
    fatores_emissor: dict[str, set[float]] = {}
    if emissores is not None and len(emissores):
        for cnpj, fator in zip(emissores["cnpj"], emissores["fator_acoes"]):
            if isinstance(cnpj, str) and pd.notna(fator):
                fatores_emissor.setdefault(cnpj, set()).add(float(fator))

    def fator_acoes(cnpj):
        distintos = fatores_emissor.get(cnpj)
        if not distintos:
            return 1.0
        if len(distintos) > 1:
            return None
        return next(iter(distintos))

    def fator_eventos(cnpj, entrega) -> float:
        sel = eventos[(eventos["cnpj"] == cnpj) & (eventos["data_com"] > entrega)]
        ignorar = (sel["tipo"] == "BONIFICACAO") & sel["isin_emitido"].notna() & (sel["isin_emitido"] != sel["isin"])
        sel = sel[~ignorar]
        return float(sel[["data_com", "tipo", "fator"]].drop_duplicates()["fator"].prod())

    linhas = []
    for r in acoes[acoes["situacao"] == "ok"].to_dict("records"):
        qtd = r["qtd_on"] + r["qtd_pn"]
        if not qtd > 0 or pd.isna(r["data_entrega"]):
            continue
        fa = fator_acoes(r["cnpj"])
        if fa is None:
            continue
        fe = fator_eventos(r["cnpj"], r["data_entrega"])
        esperado = qtd * fe * fa
        base = r["qtd_on_base_atual"] + r["qtd_pn_base_atual"]
        razao = base / esperado
        if abs(razao - 1) > tolerancia:
            linhas.append([r["cnpj"], r["data_referencia"], r["data_entrega"], qtd, fe, fa, esperado, base, razao])
    return pd.DataFrame(linhas, columns=COLUNAS_COERENCIA)


def _fator_txt(fator) -> str:
    """Fator sem zeros à direita e com vírgula: 0.000007 -> '0,000007', 5.0 -> '5'."""
    return format(float(fator), ".6f").rstrip("0").rstrip(".").replace(".", ",")


def eventos_por_pregao(eventos, cal) -> dict[tuple[str, date], str]:
    """Pregões marcados por evento: (ticker, data_com) se a data_com é pregão, e (ticker, primeiro pregão > data_com).

    Valor: "TIPO fator (data_com AAAA-MM-DD)". Mais de um evento no mesmo pregão: textos separados por "; ".
    """
    pregoes = sorted({pd.Timestamp(d).date() for d in cal})
    conjunto = set(pregoes)
    saida: dict[tuple[str, date], str] = {}
    for ticker, data_com, tipo, fator in zip(eventos["ticker"], eventos["data_com"], eventos["tipo"], eventos["fator"]):
        if pd.isna(data_com):
            continue
        dc = pd.Timestamp(data_com).date()
        rotulo = f"{tipo} {_fator_txt(fator)} (data_com {dc.isoformat()})"
        marcas = [dc] if dc in conjunto else []
        i = bisect_right(pregoes, dc)
        if i < len(pregoes):
            marcas.append(pregoes[i])
        for m in marcas:
            anterior = saida.get((ticker, m))
            saida[(ticker, m)] = rotulo if anterior is None else f"{anterior}; {rotulo}"
    return saida


def separar_fora_do_pregao(fora: dict, conhecidas: dict) -> tuple[dict, dict]:
    """Separa as datas fora do calendário do IBOV em (desconhecidas, conhecidas).

    `fora`: ticker -> datas encontradas no banco. `conhecidas`: ticker -> datas listadas no fontes.yaml
    (`precos.fora_do_pregao_conhecidas`, strings ou datas). Só tickers com lista não vazia entram no resultado.
    """
    de_conhecidas = {t: {pd.Timestamp(d).date() for d in (ds or [])} for t, ds in conhecidas.items()}
    desconhecidas: dict[str, list[date]] = {}
    encontradas: dict[str, list[date]] = {}
    for ticker in sorted(fora):
        datas = sorted({pd.Timestamp(d).date() for d in fora[ticker]})
        ja_conhecidas = de_conhecidas.get(ticker, set())
        novas = [d for d in datas if d not in ja_conhecidas]
        velhas = [d for d in datas if d in ja_conhecidas]
        if novas:
            desconhecidas[ticker] = novas
        if velhas:
            encontradas[ticker] = velhas
    return desconhecidas, encontradas


# ---------------------------------------------------------------------------
# Seções (leem pelo `ler` e pelo `fontes`)
# ---------------------------------------------------------------------------

def _data_txt(valor) -> str:
    return "-" if pd.isna(valor) else pd.Timestamp(valor).date().isoformat()


def secao_emissores(ler, mapa: dict, existentes: set) -> dict:
    """Emissor por período: nota de contagem, tabela dos tickers com mais de um emissor e os problemas
    de `problemas_emissores` (sobreposição e CNPJ divergente são divergências; lacunas e tickers sem emissor são notas).
    """
    secao = nova_secao("Emissores por período (v1-emissores_ticker)")
    if not _existe(mapa, existentes, "emissores_ticker"):
        secao["notas"].append(_pulada(mapa, "emissores_ticker"))
        return secao
    nome = _nome(mapa, "emissores_ticker")
    emissores = fontes.ler_tabela("emissores_ticker", ler=ler, unir_mudancas=False)

    contagem = emissores["ticker"].value_counts()
    com_varios = sorted(contagem[contagem > 1].index)
    secao["notas"].append(
        f"{len(emissores)} linhas, {emissores['ticker'].nunique()} tickers; {len(com_varios)} com mais de um emissor"
    )
    if com_varios:
        adicionar_tabela(
            secao, "Tickers com mais de um emissor", COLUNAS_EMISSORES,
            _registros(emissores[emissores["ticker"].isin(com_varios)], COLUNAS_EMISSORES),
        )

    if not _existe(mapa, existentes, "cadastro"):
        secao["notas"].append(_pulada(mapa, "cadastro"))
        return secao
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    problemas = problemas_emissores(emissores, cadastro)

    for detalhe in problemas["sobrepostas"]:
        secao["divergencias"].append(div("emissor_sobreposto", nome, detalhe))
    for detalhe in problemas["lacunas"]:
        secao["notas"].append(detalhe)
    for ticker, vig, cad in problemas["difere_cadastro"]:
        secao["divergencias"].append(div("emissor_difere_cadastro", nome, f"{ticker}: emissor {vig}, cadastro {cad}"))
    for ticker, cnpj, outro in problemas["cnpj_de_outra_empresa"]:
        secao["divergencias"].append(
            div("cnpj_de_outra_empresa", nome, f"{ticker}: cnpj {cnpj} é o do cadastro de {outro}")
        )
    if problemas["sem_emissor"]:
        secao["notas"].append(
            "Tickers do cadastro sem emissor em v1-emissores_ticker: " + ", ".join(problemas["sem_emissor"])
        )
    return secao


def secao_acoes_eventos(ler, mapa: dict, existentes: set) -> dict:
    """Ações emitidas: divergências de base atual e de entrega, e coerência da base com os eventos de ações."""
    secao = nova_secao("Ações emitidas: base atual e eventos")
    if not _existe(mapa, existentes, "acoes_emitidas"):
        secao["notas"].append(_pulada(mapa, "acoes_emitidas"))
        return secao
    nome = _nome(mapa, "acoes_emitidas")
    acoes = fontes.ler_tabela("acoes_emitidas", ler=ler)

    anulado = acoes["situacao"] == "anulado"
    base_preenchida = acoes["qtd_on_base_atual"].notna() | acoes["qtd_pn_base_atual"].notna()
    base_vazia = acoes["qtd_on_base_atual"].isna() | acoes["qtd_pn_base_atual"].isna()

    def rotulo(linha) -> str:
        return f"{linha['cnpj']} {_data_txt(linha['data_referencia'])}"

    for _, linha in acoes[anulado & base_preenchida].iterrows():
        secao["divergencias"].append(div("acoes_anulado_com_base", nome, f"{rotulo(linha)}: anulado com base preenchida"))
    for _, linha in acoes[~anulado & base_vazia].iterrows():
        secao["divergencias"].append(div("acoes_sem_base", nome, f"{rotulo(linha)}: base atual vazia"))
    for _, linha in acoes[acoes["data_entrega"].isna()].iterrows():
        secao["divergencias"].append(div("acoes_sem_entrega", nome, f"{rotulo(linha)}: sem data de entrega"))
    for _, linha in acoes[acoes["data_entrega"] < acoes["data_referencia"]].iterrows():
        secao["divergencias"].append(
            div("acoes_entrega_antes_da_referencia", nome, f"{rotulo(linha)}: entrega {_data_txt(linha['data_entrega'])}")
        )

    faltam = [c for c in ("eventos_acoes", "emissores_ticker") if not _existe(mapa, existentes, c)]
    for c in faltam:
        secao["notas"].append(_pulada(mapa, c))
    if not faltam:
        eventos = fontes.ler_eventos_acoes(ler)
        emissores = fontes.ler_tabela("emissores_ticker", ler=ler, unir_mudancas=False)
        incoerentes = coerencia_acoes_eventos(acoes, eventos, emissores)
        secao["notas"].append(
            f"{len(incoerentes)} linhas incoerentes com os eventos (base_atual ≠ quantidade × fatores posteriores "
            "à entrega × fator_acoes, tolerância 1%; fatores arredondados como 0,000007 podem aparecer)"
        )
        if len(incoerentes):
            adicionar_tabela(secao, "Linhas incoerentes com os eventos", COLUNAS_COERENCIA,
                             _registros(incoerentes, COLUNAS_COERENCIA))
    return secao
