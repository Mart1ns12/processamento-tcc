"""Seção "Histórico novo" do diagnóstico (24/10/2026): composição sem preço, corrigir_horas e cobertura.

SQL só pelo `ler` (executado por `fontes.executar_leitura`); tabelas do contrato por `fontes.ler_tabela` e
`fontes.ler_composicao` (sempre pelo módulo `fontes`, para o monkeypatch dos testes). As funções puras
(`composicao_sem_preco`, `nota_*`, `cobertura_por_ano`) não fazem I/O.
"""

from __future__ import annotations

import pandas as pd

from processamento import calendario, fontes
from processamento.diagnostico.regras import adicionar_tabela, nova_secao, texto
from processamento.diagnostico.temas import _col, _existe, _pulada, _tab
from processamento.exclusoes import Exclusoes, carregar_exclusoes
from processamento.tickers import aplicar_mudancas, raiz
from processamento.universo import montar_universo

INICIO_2024 = pd.Timestamp("2024-01-01")
COLUNAS_COMPOSICAO = ["ticker", "grupo", "inicio", "fim", "no_indice_desde_2024"]
COLUNAS_COBERTURA = ["ano", "pregoes", "linhas_ok", "min_por_pregao", "mediana_por_pregao", "max_por_pregao", "universo"]


def composicao_sem_preco(comp: pd.DataFrame, tickers_com_preco: set, mudancas: dict, antigos: set,
                         tickers_cadastro: set) -> list[list]:
    """Tickers da composição (como vêm na tabela) sem nenhum preço, procurado com a união das mudanças."""
    raizes = {raiz(t) for t in tickers_cadastro}
    linhas = []
    for t, g in comp.groupby("ticker", sort=True):
        if aplicar_mudancas(t, mudancas) in tickers_com_preco:
            continue
        grupo = "empresa_do_cadastro" if (t in antigos or raiz(t) in raizes) else "fora_do_cadastro"
        vigente = g["data_fim"].isna().any()
        fim = "vigente" if vigente else pd.Timestamp(g["data_fim"].max()).date().isoformat()
        desde_2024 = vigente or bool((g["data_fim"] >= INICIO_2024).any())
        inicio = pd.Timestamp(g["data_inicio"].min()).date().isoformat()
        linhas.append([t, grupo, inicio, fim, "sim" if desde_2024 else "não"])
    return sorted(linhas, key=lambda l: (l[1] != "empresa_do_cadastro", l[0]))


def nota_composicao_sem_preco(linhas: list[list], m: int) -> str:
    """Resumo da composição sem preço; `m` = nº de tickers distintos da composição."""
    if not linhas:
        return f"Composição do Ibovespa: todos os {m} tickers têm preço em v1-precos (com a união das mudanças de ticker)."
    a = sum(1 for l in linhas if l[1] == "empresa_do_cadastro")
    k = sum(1 for l in linhas if l[4] == "sim")
    return (f"Composição do Ibovespa: {len(linhas)} de {m} tickers sem nenhum preço em v1-precos "
            f"({a} código antigo de empresa do cadastro, {len(linhas) - a} fora do cadastro); {k} estiveram no "
            "índice em 2024 ou depois. O preço é procurado com a união das mudanças de ticker (o código antigo "
            "vale pelo atual).")


def _hora_sp(valor) -> str:
    """Instante UTC sem fuso (painel da coleta) em São Paulo, 'AAAA-MM-DD HH:MM'; vazio = '—'."""
    if valor is None or pd.isna(valor):
        return "—"
    return fontes.para_sao_paulo_de_utc(pd.Series([valor])).iloc[0].strftime("%Y-%m-%d %H:%M")


def nota_corrigir_horas(df: pd.DataFrame) -> str:
    """Status da execução mais recente com a etapa corrigir_horas (df com 0 ou 1 linha)."""
    if df.empty:
        return "corrigir_horas: nenhuma execução com essa etapa"
    linha = df.iloc[0]
    return (f"corrigir_horas: execução mais recente {texto(linha['id'])} (status {texto(linha['status_execucao'])}), "
            f"etapa {texto(linha['status_etapa'])}; iniciada em {_hora_sp(linha['iniciada_em'])}, "
            f"finalizada em {_hora_sp(linha['finalizada_em'])} (horário de São Paulo)")


def cobertura_por_ano(universo: pd.DataFrame, cal: list) -> list[list]:
    """Por ano: pregões, linhas com motivo ok, mín/mediana/máx de ações ok por pregão e os universos do ano."""
    datas = pd.DatetimeIndex([pd.Timestamp(d) for d in cal])
    ok = universo[universo["motivo"] == "ok"]
    por_pregao = ok.groupby("data").size().reindex(datas, fill_value=0)
    linhas = []
    for ano in sorted(set(datas.year)):
        do_ano = por_pregao[por_pregao.index.year == ano]
        tipos = sorted(set(universo.loc[pd.to_datetime(universo["data"]).dt.year == ano, "universo"]))
        linhas.append([int(ano), int(len(do_ano)), int(do_ano.sum()), int(do_ano.min()), float(do_ano.median()),
                       int(do_ano.max()), "/".join(tipos)])
    return linhas


def nota_cobertura(linhas: list[list], cal: list) -> str:
    """Resumo da cobertura do experimento."""
    total = sum(l[2] for l in linhas)
    return (f"Cobertura do experimento (universo com a composição, motivo ok): {total} linhas em {len(cal)} "
            f"pregões, de {pd.Timestamp(cal[0]).date().isoformat()} a {pd.Timestamp(cal[-1]).date().isoformat()}.")


def secao_historico(ler, mapa: dict, existentes: set, exclusoes: Exclusoes | None = None) -> dict:
    """Composição sem preço, status do corrigir_horas e cobertura do experimento por ano (só notas e tabelas)."""
    secao = nova_secao("Histórico novo: composição, corrigir_horas e cobertura do experimento")
    faltam = lambda chaves: [c for c in chaves if not _existe(mapa, existentes, c)]
    precos = None

    # (i) composição sem preço
    falta = faltam(("composicao_ibov", "precos", "cadastro", "mudancas_ticker"))
    if falta:
        secao["notas"].append(f"Composição sem preço: {_pulada(mapa, falta[0])}")
    else:
        cc = lambda x: _col(mapa, "composicao_ibov", x)
        bruto = ler(f"SELECT {cc('ticker')} AS ticker, {cc('data_inicio')} AS data_inicio, "
                    f"{cc('data_fim')} AS data_fim FROM {_tab(mapa, 'composicao_ibov')}")
        comp = pd.DataFrame({
            "ticker": fontes.normalizar_ticker(bruto["ticker"].map(texto)),
            "data_inicio": pd.to_datetime(bruto["data_inicio"], errors="coerce"),
            "data_fim": pd.to_datetime(bruto["data_fim"], errors="coerce"),
        }).dropna(subset=["ticker"])
        mud = fontes.ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False)
        precos = fontes.ler_tabela("precos", ler=ler)
        cadastro = fontes.ler_tabela("cadastro", ler=ler)
        linhas = composicao_sem_preco(comp, set(precos["ticker"].dropna()), fontes.mudancas_como_dict(mud),
                                      set(mud["ticker_antigo"].dropna()), set(cadastro["ticker"].dropna()))
        if linhas:
            adicionar_tabela(secao, "Composição do Ibovespa: tickers sem nenhum preço em v1-precos",
                             COLUNAS_COMPOSICAO, linhas)
        secao["notas"].append(nota_composicao_sem_preco(linhas, comp["ticker"].nunique()))

    # (ii) corrigir_horas
    falta = faltam(("painel_etapas", "painel_execucoes"))
    if falta:
        secao["notas"].append(f"corrigir_horas: {_pulada(mapa, falta[0])}")
    else:
        g = lambda x: _col(mapa, "painel_etapas", x)
        e = lambda x: _col(mapa, "painel_execucoes", x)
        df = ler(
            f"SELECT x.{e('id')} AS id, x.{e('status')} AS status_execucao, x.{e('iniciada_em')} AS iniciada_em, "
            f"x.{e('finalizada_em')} AS finalizada_em, t.{g('status')} AS status_etapa "
            f"FROM {_tab(mapa, 'painel_etapas')} t JOIN {_tab(mapa, 'painel_execucoes')} x "
            f"ON x.{e('id')} = t.{g('execucao_id')} WHERE t.{g('etapa_id')} = 'corrigir_horas' "
            f"ORDER BY x.{e('iniciada_em')} DESC, x.{e('id')} DESC LIMIT 1"
        )
        secao["notas"].append(nota_corrigir_horas(df))

    # (iii) cobertura do experimento
    falta = faltam(("precos", "cadastro"))
    if falta:
        secao["notas"].append(f"Cobertura do experimento: {_pulada(mapa, falta[0])}")
        return secao
    precos = fontes.ler_tabela("precos", ler=ler) if precos is None else precos
    cal = calendario.pregoes(precos)
    if not cal:
        secao["notas"].append("Cobertura do experimento: sem pregão com preço do IBOV")
        return secao
    emissores = fontes.ler_emissores(ler) if _existe(mapa, existentes, "emissores_ticker") else None
    universo = montar_universo(cal, fontes.ler_tabela("cadastro", ler=ler), precos,
                               exclusoes if exclusoes is not None else carregar_exclusoes(),
                               fontes.ler_composicao(ler=ler), emissores=emissores)
    linhas = cobertura_por_ano(universo, cal)
    adicionar_tabela(secao, "Cobertura do experimento por ano (universo com a composição, motivo ok)",
                     COLUNAS_COBERTURA, linhas)
    secao["notas"].append(nota_cobertura(linhas, cal))
    return secao
