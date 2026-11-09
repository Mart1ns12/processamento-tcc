"""Testes das seções por tema do diagnóstico (temas.py), com `ler` falso (sem banco)."""

import copy
import dataclasses
import re
from datetime import date, datetime

import pandas as pd
import pytest

from fabrica_fundamentos import CNPJ, mundo
from fabrica_precos import precos_de, pregoes_uteis
from processamento import fontes
from processamento.diagnostico import temas
from processamento.diagnostico.esperado import ETAPAS_COLETA, ETAPAS_EXECUCAO_MANUAL
from processamento.diagnostico.temas import (
    _data_referencia_usada,
    montar_sql_formato_iso,
    secao_balancos,
    secao_noticias,
    secao_painel,
    secao_precos,
    secao_quantidade_acoes,
    secao_retornos_suspeitos,
    secao_tickers,
)
from processamento.exclusoes import Exclusoes
from processamento.fatos.fundamentos import carregar_parametros_fundamentos


@pytest.fixture(scope="module")
def mapa():
    """Mapa real do fontes.yaml (só leitura do arquivo, sem banco)."""
    return fontes.carregar_mapa()


def _ler_sem_banco(sql):
    """Falha se alguma seção tentar consultar quando a tabela está ausente."""
    raise AssertionError(f"não devia consultar: {sql}")


def test_montar_sql_formato_iso_exato():
    esperado = (
        "SELECT CHAR_LENGTH(`data_hora_coleta`) AS tam, RIGHT(`data_hora_coleta`, 6) AS fim, "
        "COUNT(*) AS n, MIN(`data_hora_coleta`) AS exemplo_min, "
        "MAX(`data_hora_coleta`) AS exemplo_max FROM `v1-noticias` "
        "WHERE `data_hora_coleta` IS NOT NULL GROUP BY tam, fim ORDER BY n DESC"
    )
    assert montar_sql_formato_iso("v1-noticias", "data_hora_coleta") == esperado


def test_secao_noticias_pulada_sem_tabela(mapa):
    secao = secao_noticias(_ler_sem_banco, mapa, set())
    assert any("pulada: tabela ausente" in n for n in secao["notas"])
    assert secao["divergencias"] == []


def _ler_precos(sql):
    """Dublê de `ler` para a seção de preços, conforme o SQL pedido."""
    if "NOT IN" in sql:
        return pd.DataFrame({
            "ticker": ["AAAA3", "AAAA3", "AAAA3", "BBBB4", "BBBB4", "BBBB4"],
            "data": [date(2026, 1, 5), date(2026, 1, 8), date(2026, 1, 12),
                     date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)],
        })
    if "= 'IBOV'" in sql:
        return pd.DataFrame({"data": [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 8),
                                      date(2026, 1, 9), date(2026, 1, 12)]})
    if "IN ('IBOV'" in sql:
        return pd.DataFrame({
            "ticker": ["IBOV", "USDBRL", "BRENT"],
            "linhas": [5, 5, 5],
            "com_volume": [0, 0, 0],
            "inicio": [date(2026, 1, 5)] * 3,
            "fim": [date(2026, 1, 12)] * 3,
        })
    raise AssertionError(f"SQL inesperado: {sql}")


def test_secao_precos_gabarito(mapa):
    secao = secao_precos(_ler_precos, mapa, {"v1-precos"})
    divs = secao["divergencias"]
    assert len(divs) == 2
    fora = [d for d in divs if d["tema"] == "preco_fora_do_pregao"]
    serie = [d for d in divs if d["tema"] == "serie_ausente"]
    assert len(fora) == 1 and "BBBB4" in fora[0]["detalhe"]
    assert len(serie) == 1 and "IVVB11" in serie[0]["detalhe"]
    tabela_uteis = [t for t in secao["tabelas"] if "úteis" in t["subtitulo"]]
    assert len(tabela_uteis) == 1
    assert any(date(2026, 1, 7) in linha for linha in tabela_uteis[0]["linhas"])


def _ler_painel_factory(horas_df):
    """Dublê de `ler` para o painel; `horas_df` é a resposta da consulta de hora do daily."""
    def _ler(sql):
        if "HOUR(" in sql:
            return horas_df
        if "etapa_id" in sql:
            return pd.DataFrame({
                "etapa_id": ETAPAS_COLETA,
                "ordem": list(range(1, len(ETAPAS_COLETA) + 1)),
                "status": ["concluida"] * len(ETAPAS_COLETA),
                "n": [1] * len(ETAPAS_COLETA),
            })
        return pd.DataFrame({
            "tipo": ["daily"],
            "status": ["concluida"],
            "n": [35],
            "primeira": [datetime(2026, 1, 5, 11, 0)],
            "ultima": [datetime(2026, 10, 21, 11, 0)],
        })
    return _ler


def test_secao_painel_cron_e_manual_viram_notas(mapa):
    horas = pd.DataFrame({
        "origem": ["cron", "cron", "manual"],
        "hora": [11, 14, 17],
        "n": [30, 2, 3],
    })
    secao = secao_painel(_ler_painel_factory(horas), mapa,
                         {"v1-painel_execucoes", "v1-painel_etapas"})
    assert secao["divergencias"] == []
    assert any("14h: 2" in n for n in secao["notas"])
    assert any("manual" in n for n in secao["notas"])


def _ler_painel_com_manuais(etapas_no_daily):
    """Dublê com as etapas da coleta + cvm_itr_dfp/build_entrega (execução manual)."""
    base = _ler_painel_factory(pd.DataFrame({"origem": ["cron"], "hora": [11], "n": [30]}))
    etapas = ETAPAS_COLETA + ETAPAS_EXECUCAO_MANUAL

    def _ler(sql):
        if " JOIN " in sql:
            assert "'daily'" in sql
            return pd.DataFrame({"etapa_id": etapas_no_daily, "n": [1] * len(etapas_no_daily)})
        if "etapa_id" in sql:
            return pd.DataFrame({
                "etapa_id": etapas,
                "ordem": list(range(1, len(etapas) + 1)),
                "status": ["concluida"] * len(etapas),
                "n": [1] * len(etapas),
            })
        return base(sql)
    return _ler


def test_secao_painel_etapas_manuais_fora_do_daily_viram_nota(mapa):
    secao = secao_painel(_ler_painel_com_manuais([]), mapa,
                         {"v1-painel_execucoes", "v1-painel_etapas"})
    assert secao["divergencias"] == []
    assert any("b3_indices, build_entrega, corrigir_horas, cvm_itr_dfp" in n for n in secao["notas"])


def test_secao_painel_etapa_manual_dentro_do_daily_e_divergencia(mapa):
    secao = secao_painel(_ler_painel_com_manuais(["cvm_itr_dfp"]), mapa,
                         {"v1-painel_execucoes", "v1-painel_etapas"})
    temas = [d["tema"] for d in secao["divergencias"]]
    assert temas == ["etapa_manual_no_daily"]
    assert "cvm_itr_dfp" in secao["divergencias"][0]["detalhe"]


def test_secao_painel_corrigir_horas_pendente_em_coletar_vira_nota(mapa):
    # execução manual tipo 'coletar' (não é daily): só nota, sem etapa_desconhecida
    base = _ler_painel_factory(pd.DataFrame({"origem": ["cron"], "hora": [11], "n": [30]}))
    etapas = ETAPAS_COLETA + ETAPAS_EXECUCAO_MANUAL
    status = ["pendente" if e == "corrigir_horas" else "concluida" for e in etapas]

    def _ler(sql):
        if " JOIN " in sql:
            assert "'daily'" in sql
            return pd.DataFrame({"etapa_id": [], "n": []})
        if "etapa_id" in sql:
            return pd.DataFrame({
                "etapa_id": etapas,
                "ordem": list(range(1, len(etapas) + 1)),
                "status": status,
                "n": [1] * len(etapas),
            })
        return base(sql)

    secao = secao_painel(_ler, mapa, {"v1-painel_execucoes", "v1-painel_etapas"})
    assert secao["divergencias"] == []
    assert any("corrigir_horas" in n and "fora do daily" in n for n in secao["notas"])


def test_secao_painel_corrigir_horas_dentro_do_daily_e_divergencia(mapa):
    secao = secao_painel(_ler_painel_com_manuais(["corrigir_horas"]), mapa,
                         {"v1-painel_execucoes", "v1-painel_etapas"})
    temas = [d["tema"] for d in secao["divergencias"]]
    assert temas == ["etapa_manual_no_daily"]
    assert "corrigir_horas" in secao["divergencias"][0]["detalhe"]


def test_secao_painel_cron_so_na_agenda_nao_gera_nota_fora_da_agenda(mapa):
    horas = pd.DataFrame({"origem": ["cron"], "hora": [11], "n": [30]})
    secao = secao_painel(_ler_painel_factory(horas), mapa,
                         {"v1-painel_execucoes", "v1-painel_etapas"})
    assert not any("fora da agenda" in n for n in secao["notas"])


# ---------------------------------------------------------------------------
# secao_tickers: cobertura do other_codes, exclusões e classes de proventos
# ---------------------------------------------------------------------------

CADASTRO_FAKE = {
    "PETR4": "33000167000101",
    "ITUB4": "60872504000123",
    "VALE3": "33592510000154",
    "ABCD3": "06057223000171",
    "CRFB3": None,
}
RAW_COMPLETO = [
    ("33000167000101", '["PETR4","PETR3"]'),
    ("60872504000123", '["ITUB3","ITUB4"]'),
    ("33592510000154", '["VALE3"]'),
    ("06057223000171", '["ABCD3"]'),
]
# Os 6 UNITS do esperado.py: sem eles a seção acusaria "units" (UNITS fora da consulta),
# o que não é o cenário testado aqui.
UNITS_FAKE = ["BPAC11", "ENGI11", "IGTI11", "KLBN11", "SANB11", "TAEE11"]
EXISTENTES_TICKERS = {
    "v1-noticias", "v1-precos", "v1-cadastro", "v1-mudancas_ticker", "v1-balancos",
    "v1-acoes_emitidas", "v1-proventos", "v1-indices", "v1-raw_b3_cadastro",
}
EXCLUSOES_FAKE = Exclusoes(
    tickers_excluidos={"CRFB3": "x"},
    cnpjs_sem_balanco={"06057223000171": "x"},
)


def _ler_tickers(raw_linhas):
    """Dublê de `ler` para secao_tickers: despacha pelo texto do SQL, sem banco."""
    tabelas = {
        "v1-cadastro": {"ticker": list(CADASTRO_FAKE), "cnpj": list(CADASTRO_FAKE.values())},
        "v1-precos": {"ticker": ["PETR4", "ITUB4", "VALE3", "ABCD3", "IBOV"]},
        "v1-noticias": {"ticker": ["PETR4"]},
        "v1-proventos": {"ticker": ["PETR4", "ITUB3", "VALE5", "ZZZZ3"]},
        "v1-mudancas_ticker": {"ticker_antigo": [], "ticker_novo": []},
        "v1-balancos": {"cnpj": ["33000167000101", "60872504000123", "33592510000154"]},
        "v1-acoes_emitidas": {"cnpj": ["33000167000101", "60872504000123",
                                       "33592510000154", "06057223000171"]},
    }

    def _ler(sql):
        tab = re.search(r"FROM `([^`]+)`", sql).group(1)
        if "DISTINCT" in sql:
            col = re.search(r"DISTINCT `([^`]+)`", sql).group(1)
            valores = pd.Series(tabelas[tab][col]).dropna().unique()
            return pd.DataFrame({"valor": list(valores)})
        if tab == "v1-precos" and "MIN(" in sql:
            return pd.DataFrame({"inicio": [date(2025, 1, 2)], "fim": [date(2026, 10, 21)]})
        if tab == "v1-proventos" and "data_com" in sql:
            return pd.DataFrame({"ticker": ["PETR4", "VALE5", "VALE5"],
                                 "data_com": [date(2025, 5, 2), date(2016, 3, 1), date(2025, 6, 2)]})
        if tab == "v1-cadastro" and "IS NULL" in sql:
            return pd.DataFrame({"ticker": ["CRFB3"]})
        if "tipo_acao" in sql:
            return pd.DataFrame({"ticker": UNITS_FAKE,
                                 "unit_qtd_on": [1] * len(UNITS_FAKE),
                                 "unit_qtd_pn": [1] * len(UNITS_FAKE)})
        if tab == "v1-raw_b3_cadastro":
            return pd.DataFrame({"cnpj": [c for c, _ in raw_linhas],
                                 "other_codes": [oc for _, oc in raw_linhas]})
        if tab == "v1-mudancas_ticker":
            return pd.DataFrame({"ticker_antigo": [], "ticker_novo": []})
        if tab == "v1-cadastro" and "AS cnpj" in sql:
            return pd.DataFrame({"ticker": list(CADASTRO_FAKE),
                                 "cnpj": list(CADASTRO_FAKE.values())})
        raise AssertionError(f"SQL inesperado: {sql}")
    return _ler


def test_secao_tickers_excluidos_e_classes_de_proventos_viram_nota(mapa):
    secao = secao_tickers(_ler_tickers(RAW_COMPLETO), mapa, EXISTENTES_TICKERS, EXCLUSOES_FAKE)
    divs = secao["divergencias"]
    assert len(divs) == 1
    assert divs[0]["tema"] == "ticker_sem_cadastro"
    assert "ZZZZ3 (sem_empresa)" in divs[0]["detalhe"]
    notas = secao["notas"]
    assert any("CRFB3" in n and "excluídos por decisão" in n for n in notas)
    assert any("ITUB3" in n for n in notas)
    assert any("VALE5" in n and "extintas" in n for n in notas)
    assert any("06057223000171" in n for n in notas)


def test_secao_tickers_cnpj_sem_linha_no_other_codes_diverge(mapa):
    raw = [linha for linha in RAW_COMPLETO if linha[0] != "60872504000123"]
    secao = secao_tickers(_ler_tickers(raw), mapa, EXISTENTES_TICKERS, EXCLUSOES_FAKE)
    divs = secao["divergencias"]
    oc = [d for d in divs if d["tema"] == "other_codes"]
    assert len(oc) == 1 and "60872504000123" in oc[0]["detalhe"]
    sem_cad = [d for d in divs if d["tema"] == "ticker_sem_cadastro"]
    assert any("ITUB3 (sem_other_codes)" in d["detalhe"] for d in sem_cad)
    assert any("ZZZZ3" in d["detalhe"] for d in sem_cad)


def test_secao_tickers_sem_tabela_raw_gera_divergencia_other_codes(mapa):
    existentes = EXISTENTES_TICKERS - {"v1-raw_b3_cadastro"}
    secao = secao_tickers(_ler_tickers([]), mapa, existentes, EXCLUSOES_FAKE)
    assert any(d["tema"] == "other_codes" for d in secao["divergencias"])


def test_secao_tickers_other_codes_json_invalido_diverge_sem_derrubar_secao(mapa):
    raw = [linha if linha[0] != "33592510000154" else ("33592510000154", "xx") for linha in RAW_COMPLETO]
    secao = secao_tickers(_ler_tickers(raw), mapa, EXISTENTES_TICKERS, EXCLUSOES_FAKE)
    detalhes = [d["detalhe"] for d in secao["divergencias"] if d["tema"] == "other_codes"]
    assert any("JSON inválido" in d and "33592510000154" in d for d in detalhes)


def test_secao_tickers_classe_de_empresa_excluida_vira_nota_de_excluidos(mapa):
    # ITUB4 excluída: ITUB3 (mesma empresa) vai para a nota de excluídos, não para "ligadas"
    exclusoes = Exclusoes(tickers_excluidos={"CRFB3": "x", "ITUB4": "x"},
                          cnpjs_sem_balanco={"06057223000171": "x"})
    secao = secao_tickers(_ler_tickers(RAW_COMPLETO), mapa, EXISTENTES_TICKERS, exclusoes)
    assert not any("ITUB3" in d["detalhe"] for d in secao["divergencias"])
    assert any("excluídos por decisão" in n and "ITUB3" in n for n in secao["notas"])
    assert not any("ligadas" in n and "ITUB3" in n for n in secao["notas"])


def test_secao_tickers_tabela_de_proventos_das_classes_extintas(mapa):
    secao = secao_tickers(_ler_tickers(RAW_COMPLETO), mapa, EXISTENTES_TICKERS, EXCLUSOES_FAKE)
    tabela = next(t for t in secao["tabelas"] if t["subtitulo"] == "Classes extintas: proventos")
    assert tabela["linhas"] == [["VALE5", 2, date(2016, 3, 1), date(2025, 6, 2), 1]]
    assert any("período analisado (pregões do IBOV): 2025-01-02 a 2026-10-21" in n for n in secao["notas"])


def _ler_tickers_com_mudancas(pares):
    """Como _ler_tickers, mas v1-mudancas_ticker devolve as linhas (antigo, novo) dadas."""
    base = _ler_tickers(RAW_COMPLETO)

    def _ler(sql):
        if "AS ticker_antigo" in sql:
            return pd.DataFrame({"ticker_antigo": [a for a, _ in pares], "ticker_novo": [b for _, b in pares]})
        return base(sql)
    return _ler


def test_secao_tickers_nota_de_mudancas_registradas_em_ordem(mapa):
    ler = _ler_tickers_com_mudancas([("RAIZ4", "RAIZ55"), ("ELET3", "AXIA3")])
    secao = secao_tickers(ler, mapa, EXISTENTES_TICKERS, EXCLUSOES_FAKE)
    assert "mudanças registradas em v1-mudancas_ticker: ELET3 → AXIA3, RAIZ4 → RAIZ55" in secao["notas"]


def test_secao_tickers_tabela_de_mudancas_vazia_diz_nenhuma(mapa):
    secao = secao_tickers(_ler_tickers(RAW_COMPLETO), mapa, EXISTENTES_TICKERS, EXCLUSOES_FAKE)
    assert "mudanças registradas em v1-mudancas_ticker: nenhuma" in secao["notas"]


def test_secao_tickers_sem_tabela_de_mudancas_nao_tem_nota(mapa):
    existentes = EXISTENTES_TICKERS - {"v1-mudancas_ticker"}
    secao = secao_tickers(_ler_tickers(RAW_COMPLETO), mapa, existentes, EXCLUSOES_FAKE)
    assert not any("mudanças registradas" in n for n in secao["notas"])


# ---------------------------------------------------------------------------
# composicao_ibov (dentro de secao_painel): colunas, contagem e período
# ---------------------------------------------------------------------------

COLUNAS_COMPOSICAO = ["ticker", "vigencia_inicio", "vigencia_fim", "participacao", "fonte"]


def _mapa_composicao(mapa):
    """Cópia do mapa com o contrato novo de composicao_ibov (nomes reais vigencia_*).

    Não depende do fontes.yaml: o yaml real está sendo editado em paralelo.
    """
    m = copy.deepcopy(mapa)
    m["auxiliares"]["composicao_ibov"]["colunas"] = {
        "ticker": "ticker", "data_inicio": "vigencia_inicio", "data_fim": "vigencia_fim",
        "participacao": "participacao", "fonte": "fonte",
    }
    return m


def _ler_composicao(colunas_reais, contagem=None):
    """Dublê de `ler` só para composicao_ibov; `contagem` é a resposta do SELECT de contagem.

    `contagem=None` faz a consulta de contagem falhar (ela não pode rodar sem as colunas de data).
    """
    def _ler(sql):
        if "information_schema.COLUMNS" in sql:
            return pd.DataFrame({"coluna": colunas_reais})
        if "COUNT(*) AS n" in sql:
            if contagem is None:
                raise AssertionError(f"não devia contar: {sql}")
            assert "`v1-composicao_ibov`" in sql
            return contagem
        raise AssertionError(f"SQL inesperado: {sql}")
    return _ler


def _secao_composicao(ler, mapa):
    """secao_painel só com composicao_ibov (painel_* ausentes: viram notas puladas)."""
    return secao_painel(ler, mapa, {"v1-composicao_ibov"})


def test_composicao_ibov_vazia_vira_nota_sem_divergencia(mapa):
    m = _mapa_composicao(mapa)
    contagem = pd.DataFrame({"n": [0], "ini": [None], "ini_max": [None], "vigentes": [None]})
    secao = _secao_composicao(_ler_composicao(COLUNAS_COMPOSICAO, contagem), m)
    assert secao["divergencias"] == []
    assert "v1-composicao_ibov existe mas está vazia: universo = composicao_atual em todas as datas (seção 3.5)" in secao["notas"]


def test_composicao_ibov_com_linhas_vira_nota_com_contagem_e_vigentes(mapa):
    m = _mapa_composicao(mapa)
    contagem = pd.DataFrame({
        "n": [3], "ini": [date(2025, 1, 2)], "ini_max": [date(2026, 9, 1)], "vigentes": [2],
    })
    secao = _secao_composicao(_ler_composicao(COLUNAS_COMPOSICAO, contagem), m)
    assert secao["divergencias"] == []
    nota = next(n for n in secao["notas"] if n.startswith("v1-composicao_ibov: 3 linhas"))
    assert "data_inicio de 2025-01-02 a 2026-09-01" in nota
    assert "2 vigentes (data_fim vazia)" in nota
    assert "datas sem vigência usam composicao_atual (seção 3.5)" in nota


def test_composicao_ibov_sem_coluna_data_fim_diverge_e_nao_conta(mapa):
    m = _mapa_composicao(mapa)
    colunas = [c for c in COLUNAS_COMPOSICAO if c != "vigencia_fim"]
    secao = _secao_composicao(_ler_composicao(colunas, contagem=None), m)
    divs = [d for d in secao["divergencias"] if d["tema"] == "coluna_faltando"]
    assert len(divs) == 1
    assert divs[0]["tabela"] == "v1-composicao_ibov"
    assert "vigencia_fim" in divs[0]["detalhe"]
    assert len(secao["divergencias"]) == 1
    assert any("contagem e período pulados" in n for n in secao["notas"])


# ---------------------------------------------------------------------------
# Quantidade de ações suspeita (mundo de fundamentos, sem banco)
# ---------------------------------------------------------------------------

T_QUANTIDADE = date(2026, 3, 16)


@pytest.fixture
def tabelas_quantidade(monkeypatch):
    """Tabelas do mundo de fundamentos servidas por `fontes.ler_tabela` (sem banco)."""
    cadastro, balancos, acoes, _, precos, _, _ = mundo()
    dados = {"precos": precos, "cadastro": cadastro, "balancos": balancos, "acoes_emitidas": acoes}

    def ler_tabela(tabela, **_kwargs):
        return dados[tabela].copy()

    monkeypatch.setattr(fontes, "ler_tabela", ler_tabela)
    return dados


def _existentes_quantidade():
    return {fontes.nome_real(c) for c in ("precos", "mudancas_ticker", "cadastro", "balancos", "acoes_emitidas")}


def _params_com_manuais(monkeypatch, lista):
    """`carregar_parametros_fundamentos` de temas devolve os parâmetros reais com a lista manual dada."""
    real = carregar_parametros_fundamentos()
    monkeypatch.setattr(temas, "carregar_parametros_fundamentos",
                        lambda *_a, **_k: dataclasses.replace(real, quantidade_suspeita_manual=lista))


@pytest.fixture
def sem_manuais(monkeypatch):
    """Parâmetros reais sem entradas manuais (para os testes da checagem automática)."""
    _params_com_manuais(monkeypatch, ())


SUBTITULO_MANUAIS = "Entradas manuais (fundamentos.quantidade_suspeita_manual)"


def test_quantidade_suspeita_sem_mudanca_nao_lista_empresas(mapa, tabelas_quantidade, sem_manuais):
    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, _existentes_quantidade(), Exclusoes(), t=T_QUANTIDADE)
    assert secao["notas"] == ["nenhuma empresa com quantidade de ações suspeita em 2026-03-16", "nenhuma entrada manual"]
    assert secao["tabelas"] == []
    assert secao["divergencias"] == []


def test_quantidade_suspeita_com_quantidade_em_milhares_lista_a_empresa(mapa, tabelas_quantidade, sem_manuais):
    acoes = tabelas_quantidade["acoes_emitidas"]
    mascara = acoes["cnpj"] == CNPJ["A"]
    acoes.loc[mascara, ["qtd_on", "qtd_pn"]] = acoes.loc[mascara, ["qtd_on", "qtd_pn"]] / 1000

    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, _existentes_quantidade(), Exclusoes(), t=T_QUANTIDADE)

    assert secao["notas"] == [
        "quantidade de ações suspeita (P/VP < 0,05 e P/VP × 1000 <= 20; v1-acoes_emitidas provavelmente em milhares) "
        "em 1 empresas em 2026-03-16: valor de mercado, P/L, P/VP e payout = indisponivel (seção 6)",
        "nenhuma entrada manual",
    ]
    assert secao["divergencias"] == []
    assert len(secao["tabelas"]) == 1
    tabela = secao["tabelas"][0]
    assert tabela["colunas"] == ["tickers", "cnpj", "data_referencia", "acoes", "pvp"]
    assert len(tabela["linhas"]) == 1
    tickers, cnpj, data_ref, acoes_emitidas, pvp = tabela["linhas"][0]
    assert tickers == "AAAA3, AAAA4"
    assert cnpj == CNPJ["A"]
    assert data_ref == date(2025, 12, 31)
    assert acoes_emitidas == pytest.approx(0.1, rel=1e-9)
    assert pvp == pytest.approx(0.0007076923076923077, rel=1e-9)


def test_quantidade_suspeita_sem_pregao_do_ibov_nao_faz_a_checagem(mapa, tabelas_quantidade, sem_manuais):
    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, _existentes_quantidade(), Exclusoes())
    assert secao["notas"] == ["sem pregão com preço do IBOV: checagem não feita", "nenhuma entrada manual"]
    assert secao["divergencias"] == []


def test_quantidade_suspeita_com_tabela_ausente_pula_a_checagem(mapa, sem_manuais):
    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, set(), Exclusoes(), t=T_QUANTIDADE)
    assert len(secao["notas"]) == 6
    assert all(n.startswith("pulada: tabela ausente") for n in secao["notas"][:5])
    assert secao["notas"][5] == "nenhuma entrada manual"


def test_quantidade_suspeita_entrada_manual_aparece_na_tabela(mapa, tabelas_quantidade, monkeypatch):
    _params_com_manuais(monkeypatch, (("AAAA3", date(2026, 11, 3), "teste"),))
    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, _existentes_quantidade(), Exclusoes(), t=T_QUANTIDADE)
    assert "entradas manuais em fundamentos.quantidade_suspeita_manual: 1; " in secao["notas"][-1]
    assert secao["tabelas"] == [{
        "subtitulo": SUBTITULO_MANUAIS,
        "colunas": ["ticker", "desde", "motivo"],
        "linhas": [["AAAA3", "2026-11-03", "teste"]],
    }]


def test_quantidade_suspeita_sem_entradas_manuais_nao_tem_tabela(mapa, tabelas_quantidade, sem_manuais):
    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, _existentes_quantidade(), Exclusoes(), t=T_QUANTIDADE)
    assert secao["notas"][-1] == "nenhuma entrada manual"
    assert secao["tabelas"] == []


def test_quantidade_suspeita_entrada_manual_aparece_com_checagem_pulada(mapa, monkeypatch):
    _params_com_manuais(monkeypatch, (("AAAA3", date(2026, 11, 3), "teste"),))
    secao = secao_quantidade_acoes(_ler_sem_banco, mapa, set(), Exclusoes(), t=T_QUANTIDADE)
    assert all(n.startswith("pulada: tabela ausente") for n in secao["notas"][:5])
    assert secao["tabelas"] == [{
        "subtitulo": SUBTITULO_MANUAIS,
        "colunas": ["ticker", "desde", "motivo"],
        "linhas": [["AAAA3", "2026-11-03", "teste"]],
    }]


def test_data_referencia_usada_segue_a_regra_de_acoes_na_data():
    disponiveis = pd.DataFrame({
        "cnpj": ["X", "X"],
        "data_referencia": pd.to_datetime(["2025-03-31", "2025-12-31"]),
        "qtd_on": [1.0, 2.0],
        "qtd_pn": [1.0, 2.0],
    })
    assert _data_referencia_usada(disponiveis, "X", pd.Timestamp("2025-06-30")) == date(2025, 3, 31)
    assert _data_referencia_usada(disponiveis, "X", pd.Timestamp("2026-03-16")) == date(2025, 12, 31)
    # Sem linha anterior à data, vale a de menor data_referencia (fallback de acoes_na_data)
    assert _data_referencia_usada(disponiveis, "X", pd.Timestamp("2025-01-01")) == date(2025, 3, 31)


# ---------------------------------------------------------------------------
# Retornos diários suspeitos (Fase 5; gabarito conferido sobre a fábrica)
# ---------------------------------------------------------------------------

CAL_R = pregoes_uteis(6, "2026-04-06")
PRECOS_R = pd.concat([
    precos_de("IBOV", CAL_R, [10.0] * 6),
    precos_de("AZUL3", CAL_R, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0]),
    precos_de("GAPX3", CAL_R, [10.0, None, 25.0, 25.0, 25.0, 25.0]),
    precos_de("SPLT3", CAL_R, [40.0, 40.0, 10.0, 10.0, 10.0, 10.0], aj=[10.0] * 6),  # desdobramento real: fora
], ignore_index=True)
EXISTENTES_RETORNOS = {fontes.nome_real("precos")}


def _servir_precos(monkeypatch, precos):
    """`fontes.ler_tabela` devolve `precos` (sem banco)."""
    monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: precos.copy())


def test_retornos_suspeitos_5a_nota_conta_saltos_e_tickers(mapa, monkeypatch):
    _servir_precos(monkeypatch, PRECOS_R)
    secao = secao_retornos_suspeitos(_ler_sem_banco, mapa, EXISTENTES_RETORNOS)
    assert secao["notas"] == [
        "3 retornos diários suspeitos em 2 tickers (fechamento_ajustado contra o último pregão com preço, "
        "abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)"
    ]
    assert secao["divergencias"] == []


def test_retornos_suspeitos_5b_tabela_com_aj_fechamento_e_retornos(mapa, monkeypatch):
    _servir_precos(monkeypatch, PRECOS_R)
    secao = secao_retornos_suspeitos(_ler_sem_banco, mapa, EXISTENTES_RETORNOS)
    assert len(secao["tabelas"]) == 1
    tabela = secao["tabelas"][0]
    assert tabela["colunas"] == ["ticker", "data", "aj_anterior", "aj", "retorno_aj", "retorno_fech"]
    linhas = tabela["linhas"]
    assert len(linhas) == 3
    assert linhas[0][:4] == ["AZUL3", date(2026, 4, 8), 102.0, 2040000.0]
    assert linhas[0][4:] == pytest.approx([19999.0, 19999.0])
    assert linhas[1][:4] == ["AZUL3", date(2026, 4, 10), 2142000.0, 105.0]
    assert linhas[1][4:] == pytest.approx([-0.9999509803921569, -0.9999509803921569])
    assert linhas[2][:4] == ["GAPX3", date(2026, 4, 8), 10.0, 25.0]
    assert linhas[2][4:] == pytest.approx([1.5, 1.5])


def test_retornos_suspeitos_5c_sem_saltos_vira_nota_sem_tabela(mapa, monkeypatch):
    _servir_precos(monkeypatch, PRECOS_R[PRECOS_R["ticker"].isin(["IBOV", "SPLT3"])])
    secao = secao_retornos_suspeitos(_ler_sem_banco, mapa, EXISTENTES_RETORNOS)
    assert secao["notas"] == [
        "nenhum retorno diário suspeito (fechamento_ajustado abaixo de -75% ou acima de 100%)"
    ]
    assert secao["tabelas"] == []
    assert secao["divergencias"] == []


def test_retornos_suspeitos_5d_sem_pregao_do_ibov_nao_faz_a_checagem(mapa, monkeypatch):
    _servir_precos(monkeypatch, PRECOS_R[PRECOS_R["ticker"] != "IBOV"])
    secao = secao_retornos_suspeitos(_ler_sem_banco, mapa, EXISTENTES_RETORNOS)
    assert secao["notas"] == ["sem pregão com preço do IBOV: checagem não feita"]
    assert secao["tabelas"] == []


def test_retornos_suspeitos_5e_tabela_ausente_pula_sem_consultar(mapa):
    secao = secao_retornos_suspeitos(_ler_sem_banco, mapa, set())
    assert len(secao["notas"]) == 1
    assert secao["notas"][0].startswith("pulada: tabela ausente")
    assert secao["tabelas"] == []


# ---------------------------------------------------------------------------
# Balanços: período inválido vira nota (descartado pelo processamento), não divergência
# ---------------------------------------------------------------------------

def _ler_balancos(periodos, linhas_invalidas=None):
    """Dublê de `ler` para secao_balancos: escala, múltiplos de mil, períodos, linhas inválidas e entrega."""
    def _ler(sql):
        if "LOG10" in sql:
            return pd.DataFrame({"ordem": [8], "n": [10]})
        if "MOD(ROUND" in sql:
            return pd.DataFrame({"com_valor": [10], "multiplos_de_mil": [0]})
        if "GROUP BY tipo_documento, dias" in sql:
            return periodos
        if "LIMIT 10" in sql:
            if linhas_invalidas is None:
                raise AssertionError(f"não devia listar linhas inválidas: {sql}")
            return linhas_invalidas
        if "sem_entrega" in sql:
            return pd.DataFrame({"total": [10], "sem_entrega": [0], "entrega_antes_do_fim": [0]})
        raise AssertionError(f"SQL inesperado: {sql}")
    return _ler


_PERIODOS_MISTOS = pd.DataFrame({
    "tipo_documento": ["DFP", "DFP", "ITR", "ITR", "ITR", "ITR"],
    "dias": [90, 365, 31, 90, 181, 365],
    "n": [1, 5, 2, 7, 4, 3],
})
_INVALIDAS_3 = pd.DataFrame({
    "cnpj": ["00000000000101", "00000000000202", "00000000000303"],
    "tipo": ["ITR", "ITR", "DFP"],
    "ini": [date(2021, 1, 1), date(2021, 3, 1), date(2021, 1, 1)],
    "fim": [date(2021, 12, 31), date(2021, 3, 31), date(2021, 3, 31)],
    "dias": [365, 31, 90],
})


def test_periodo_invalido_vira_nota_com_lista_nao_divergencia(mapa):
    secao = secao_balancos(_ler_balancos(_PERIODOS_MISTOS, _INVALIDAS_3), mapa, {"v1-balancos"})
    assert [d for d in secao["divergencias"] if d["tema"] == "periodo"] == []
    assert ("6 linhas de balanço com período inválido, descartadas pelo processamento (seção 6): "
            "00000000000101 ITR 2021-01-01→2021-12-31 (365 dias); "
            "00000000000202 ITR 2021-03-01→2021-03-31 (31 dias); "
            "00000000000303 DFP 2021-01-01→2021-03-31 (90 dias); e mais 3") in secao["notas"]


def test_periodo_so_valido_nao_gera_nota_nem_consulta_lista(mapa):
    validos = _PERIODOS_MISTOS[_PERIODOS_MISTOS["tipo_documento"] == "ITR"].iloc[[1]]
    validos = pd.concat([validos, pd.DataFrame({"tipo_documento": ["DFP"], "dias": [366], "n": [2]})])
    secao = secao_balancos(_ler_balancos(validos), mapa, {"v1-balancos"})
    assert secao["divergencias"] == []
    assert not any("período inválido" in nota for nota in secao["notas"])


def test_lista_de_periodo_invalido_limitada_a_10_com_e_mais(mapa):
    linhas = pd.DataFrame({
        "cnpj": [f"0000000000{i:04d}" for i in range(10)],
        "tipo": ["ITR"] * 10,
        "ini": [date(2021, 1, 1)] * 10,
        "fim": [date(2021, 12, 31)] * 10,
        "dias": [365] * 10,
    })
    periodos = pd.DataFrame({"tipo_documento": ["ITR"], "dias": [365], "n": [12]})
    secao = secao_balancos(_ler_balancos(periodos, linhas), mapa, {"v1-balancos"})
    nota = next(n for n in secao["notas"] if "período inválido" in n)
    assert nota.startswith("12 linhas de balanço com período inválido")
    assert nota.count("(365 dias)") == 10
    assert nota.endswith("; e mais 2")


# ---------------------------------------------------------------------------
# Balanços: D&A vazia nas não financeiras (último bloco de secao_balancos)
# ---------------------------------------------------------------------------

_PERIODOS_VAZIOS = pd.DataFrame({"tipo_documento": [], "dias": [], "n": []})
EXISTENTES_DA = {"v1-balancos", "v1-cadastro"}
CAD_COLUNAS_DA = ["ticker", "cnpj", "empresa", "setor", "subsetor", "tipo_acao", "unit_qtd_on", "unit_qtd_pn"]
EMI_COLUNAS_DA = ["ticker", "ordem", "ticker_negociado", "cd_cvm", "cnpj", "empresa",
                  "vigencia_inicio", "vigencia_fim", "fator_acoes"]
CNPJ_ABCD = "11111111000111"
CNPJ_BBBB = "22222222000122"
CNPJ_FINA = "33333333000133"
CNPJ_NATU_HOLDING = "32785497000197"
CNPJ_NATU = "61082533000124"


def _df_da(linhas, colunas):
    """DataFrame com as colunas pedidas; campo ausente vira nulo."""
    return pd.DataFrame([{c: linha.get(c) for c in colunas} for linha in linhas], columns=colunas)


def _ler_da(da_linhas, cadastro=(), emissores=()):
    """Dublê de `ler` para a D&A: consultas de cadastro, emissor e D&A; o resto vem de `_ler_balancos`."""
    base = _ler_balancos(_PERIODOS_VAZIOS)
    cad = _df_da(cadastro, CAD_COLUNAS_DA)
    emi = _df_da(emissores, EMI_COLUNAS_DA)
    da = pd.DataFrame(da_linhas, columns=["cnpj", "tipo_documento", "fim", "situacao"])

    def _ler(sql, params=None):
        if "LEFT JOIN" in sql:
            return pd.DataFrame({"cnpj": [], "empresa": [], "fim": [], "receita": []})
        if "`depreciacao_amortizacao` IS NULL" in sql:
            return da.copy()
        if "`v1-cadastro`" in sql:
            return cad.copy()
        if "`v1-emissores_ticker`" in sql:
            return emi.copy()
        return base(sql)
    return _ler


def _tabela_da(secao):
    return next((t for t in secao["tabelas"] if t["subtitulo"] == "D&A vazia nas não financeiras"), None)


def _cad(ticker, cnpj, subsetor):
    return {"ticker": ticker, "cnpj": cnpj, "subsetor": subsetor, "tipo_acao": "ON"}


_CAD_ABCD = _cad("ABCD3", CNPJ_ABCD, "Energia Elétrica")


def test_da_vazia_itr_do_trimestre_e_acumulado_viram_uma_linha(mapa):
    da = [(CNPJ_ABCD, "ITR", date(2021, 6, 30), "ok"),
          (CNPJ_ABCD, "ITR", date(2021, 6, 30), "reapresentado")]
    secao = secao_balancos(_ler_da(da, cadastro=[_CAD_ABCD]), mapa, EXISTENTES_DA)
    assert _tabela_da(secao)["colunas"] == ["ticker", "cnpj", "trimestre", "linhas", "situacao"]
    assert _tabela_da(secao)["linhas"] == [["ABCD3", CNPJ_ABCD, "2T21", 2, "ok,reapresentado"]]
    assert ("D&A vazia nas não financeiras: 1 trimestres de 1 empresas "
            "(bancos, seguradoras e holdings fora: fundamentos.subsetores_financeiros; tickers_excluidos fora)"
            ) in secao["notas"]
    assert secao["divergencias"] == []


def test_da_vazia_dfp_vira_quarto_trimestre(mapa):
    da = [(CNPJ_BBBB, "DFP", date(2020, 12, 31), "ok")]
    cadastro = [_cad("BBBB4", CNPJ_BBBB, "Comércio")]
    secao = secao_balancos(_ler_da(da, cadastro=cadastro), mapa, EXISTENTES_DA)
    assert _tabela_da(secao)["linhas"] == [["BBBB4", CNPJ_BBBB, "4T20", 1, "ok"]]


def test_da_vazia_de_financeira_sai_da_lista(mapa):
    da = [(CNPJ_FINA, "ITR", date(2021, 3, 31), "ok"), (CNPJ_ABCD, "ITR", date(2021, 3, 31), "ok")]
    cadastro = [_cad("FINA3", CNPJ_FINA, "Intermediários Financeiros"), _CAD_ABCD]
    secao = secao_balancos(_ler_da(da, cadastro=cadastro), mapa, EXISTENTES_DA)
    assert _tabela_da(secao)["linhas"] == [["ABCD3", CNPJ_ABCD, "1T21", 1, "ok"]]
    assert ("D&A vazia nas não financeiras: 1 trimestres de 1 empresas (bancos, seguradoras e holdings fora: "
            "fundamentos.subsetores_financeiros; tickers_excluidos fora)") in secao["notas"]


def test_da_vazia_de_empresa_com_ticker_excluido_sai_da_lista(mapa):
    # 09/11/2026: SRNA3 está em tickers_excluidos (exclusoes.yaml real): fora da checagem de D&A.
    cnpj_srna = "42500384000151"
    da = [(cnpj_srna, "ITR", date(2021, 6, 30), "individual"), (CNPJ_ABCD, "ITR", date(2021, 3, 31), "ok")]
    cadastro = [_cad("SRNA3", cnpj_srna, "Energia Elétrica"), _CAD_ABCD]
    secao = secao_balancos(_ler_da(da, cadastro=cadastro), mapa, EXISTENTES_DA)
    assert _tabela_da(secao)["linhas"] == [["ABCD3", CNPJ_ABCD, "1T21", 1, "ok"]]


def test_da_vazia_cnpj_so_no_emissor_usa_o_ticker_do_emissor(mapa):
    da = [(CNPJ_NATU_HOLDING, "ITR", date(2022, 9, 30), "ok")]
    cadastro = [_cad("NATU3", CNPJ_NATU, "Produtos de Uso Pessoal e de Limpeza")]
    emissores = [{"ticker": "NATU3", "ordem": 1, "cnpj": CNPJ_NATU_HOLDING,
                  "empresa": "Natura Holding", "vigencia_inicio": "2000-01-01"}]
    secao = secao_balancos(_ler_da(da, cadastro=cadastro, emissores=emissores),
                           mapa, EXISTENTES_DA | {"v1-emissores_ticker"})
    assert _tabela_da(secao)["linhas"] == [["NATU3", CNPJ_NATU_HOLDING, "3T22", 1, "ok"]]


def test_da_vazia_sem_linhas_diz_nenhuma_e_nao_tem_tabela(mapa):
    secao = secao_balancos(_ler_da([], cadastro=[_CAD_ABCD]), mapa, EXISTENTES_DA)
    assert "D&A vazia nas não financeiras: nenhuma" in secao["notas"]
    assert _tabela_da(secao) is None


def test_da_vazia_sem_cadastro_vira_nota_de_pulada(mapa):
    secao = secao_balancos(_ler_da([]), mapa, {"v1-balancos"})
    assert "D&A vazia nas não financeiras: pulada: tabela ausente (`v1-cadastro`)" in secao["notas"]
    assert _tabela_da(secao) is None
