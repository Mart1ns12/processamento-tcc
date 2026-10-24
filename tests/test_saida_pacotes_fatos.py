"""Testes dos pacotes da saída vindos dos fatos (plano da etapa 7, fase 6a; casos 1 a 8 da Fase 6a).

Sem rede e sem banco real: `banco_teste` (SQLite de tests/dados) e as fábricas. Nunca `fontes.criar_engine`.
Os gabaritos são os valores conferidos da seção 4 do plano (cenário D = 2025-10-22, t = 2025-10-21).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta

import pandas as pd
import pytest

from fabrica_fundamentos import EXCL, _a, acoes_de, balanco_de, cadastro_fund_de, mundo
from fabrica_saida import DADOS_ATE, GERADO, insumos_de_teste
from processamento.fatos.fundamentos import carregar_parametros_fundamentos
from processamento.fatos.precos import carregar_parametros_precos
from processamento.saida import contrato
from processamento.saida.insumos import Insumos
from processamento.saida.pacotes_fatos import (
    calcular_grades,
    montar_acoes,
    montar_fundamentos_trimestrais,
    montar_mercado_dia,
    montar_proventos,
    montar_resumo_acao,
)
from processamento.universo import montar_universo

PARAMS_PRECOS = carregar_parametros_precos()
PARAMS_FUND = carregar_parametros_fundamentos()
JANELAS = ("d1", "m1", "m6", "a1")
STATUS_HIST = "historico_insuficiente"


# ---------------------------------------------------------------- auxiliares

def _universo_de_t(ins: Insumos) -> pd.DataFrame:
    """Linhas de t de `montar_universo` (o que a rodada passa a `montar_acoes`)."""
    u = montar_universo(ins.cal, ins.cadastro, ins.precos, ins.exclusoes, ins.composicao)
    return u[pd.to_datetime(u["data"]).dt.date == ins.t]


def _cinco_pacotes(ins: Insumos) -> dict[str, list[dict]]:
    """Os cinco pacotes deste módulo na rodada de `ins` (gerado/dados_ate fixos)."""
    grades = calcular_grades(ins, PARAMS_PRECOS, PARAMS_FUND)
    return {
        "acoes": montar_acoes(ins, _universo_de_t(ins), GERADO, DADOS_ATE),
        "mercado_dia": montar_mercado_dia(ins, grades, GERADO, DADOS_ATE),
        "resumo_acao": montar_resumo_acao(ins, grades, PARAMS_FUND, GERADO, DADOS_ATE),
        "fundamentos_trimestrais": montar_fundamentos_trimestrais(ins, PARAMS_FUND, GERADO, DADOS_ATE),
        "proventos": montar_proventos(ins, PARAMS_FUND, GERADO, DADOS_ATE),
    }


def _por(registros: list[dict], campo: str, valor: str) -> dict:
    achados = [r for r in registros if r[campo] == valor]
    assert len(achados) == 1, f"esperava 1 registro com {campo}={valor!r}, achei {len(achados)}"
    return achados[0]


def _confere(folha: dict, valor, status: str) -> None:
    """Folha igual ao gabarito: valor com tolerância 1e-12 (ou null) e status exato."""
    assert folha["status"] == status, folha
    if valor is None:
        assert folha["valor"] is None, folha
    else:
        assert folha["valor"] == pytest.approx(valor, rel=1e-12, abs=1e-12), folha


def _folhas(obj):
    """Todas as folhas `{valor, status}` de um registro, em qualquer profundidade."""
    if isinstance(obj, dict):
        if "valor" in obj and "status" in obj:
            yield obj
        for v in obj.values():
            yield from _folhas(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _folhas(v)


def _como_coluna(df: pd.DataFrame, coluna: str, valor):
    """Valor no mesmo tipo da coluna (data como Timestamp quando a coluna é datetime)."""
    return pd.Timestamp(valor) if pd.api.types.is_datetime64_any_dtype(df[coluna]) else valor


def _copia_linha(df: pd.DataFrame, mascara: pd.Series, **alterar) -> pd.DataFrame:
    """Uma linha copiada de `df` com campos trocados (para simular dados futuros ao corte)."""
    linha = df[mascara].iloc[[-1]].copy()
    return linha.assign(**{c: [_como_coluna(df, c, v)] for c, v in alterar.items()})


@pytest.fixture
def ins(banco_teste):
    return insumos_de_teste(banco_teste())


@pytest.fixture
def pacotes(ins):
    return _cinco_pacotes(ins)


# ---------------------------------------------------------------- caso 1: gabaritos E2E (seções 4.1, 4.2, 4.3, 4.5, 4.6)

def test_acoes_gabarito(pacotes):
    regs = pacotes["acoes"]
    assert [r["ticker"] for r in regs] == ["ABEV3", "ITUB4", "JBSS32", "NOVA3", "PETR3", "PETR4", "TAEE11"]
    assert [r["ticker"] for r in regs if not r["ativo_no_universo"]] == ["JBSS32"]
    assert _por(regs, "ticker", "ABEV3")["ativo_no_universo"] is True
    assert _por(regs, "ticker", "ITUB4")["ativo_no_universo"] is True
    petr4 = _por(regs, "ticker", "PETR4")
    assert (petr4["empresa"], petr4["setor"], petr4["subsetor"], petr4["tipo_acao"]) == (
        "PETROBRAS", "Petroleo", "Petroleo e gas", "PN")


def test_mercado_dia_gabarito(pacotes):
    m = pacotes["mercado_dia"]
    assert len(m) == 1
    m = m[0]
    assert m["data_referencia"] == "2025-10-21"
    _confere(m["IBOV"]["fechamento"], 10.0, "ok")
    _confere(m["IBOV"]["variacao_dia"], 0.0, "ok")
    assert m["IBOV"]["unidade"] == "pontos"
    _confere(m["BRENT"]["fechamento"], 10.0, "ok")
    _confere(m["BRENT"]["variacao_dia"], 0.0, "ok")
    assert m["BRENT"]["unidade"] == "USD/barril"
    _confere(m["USDBRL"]["fechamento"], None, "indisponivel")
    _confere(m["USDBRL"]["variacao_dia"], None, "indisponivel")
    assert m["USDBRL"]["unidade"] == "BRL/USD"
    _confere(m["cdi_dia"], 0.0006, "ok")
    assert m["cdi_data"] == "2025-10-21"
    _confere(m["ipca_12m"], None, STATUS_HIST)
    assert m["ipca_ate"] == {"valor": "2025-09", "status": "ok"}
    _confere(m["indices"]["CDI"]["d1"], 0.0005, "ok")
    for j in ("m1", "m6", "a1"):
        _confere(m["indices"]["CDI"][j], None, STATUS_HIST)
    _confere(m["indices"]["IDIV"]["d1"], 0.01, "ok")
    _confere(m["indices"]["IPCA"]["d1"], 0.0, "ok")
    for indice in ("SMLL", "IFIX", "IVVB11"):
        for j in JANELAS:
            _confere(m["indices"][indice][j], None, "indisponivel")


def test_resumo_acao_petr4_gabarito(pacotes):
    r = _por(pacotes["resumo_acao"], "ticker", "PETR4")
    assert r["data_referencia"] == "2025-10-21"
    _confere(r["cotacao"]["fechamento"], 10.0, "ok")
    _confere(r["cotacao"]["variacao_dia"], 0.0, "ok")
    _confere(r["variacao_preco"]["d1"], 0.0, "ok")
    for j in ("m1", "m6", "a1"):
        _confere(r["variacao_preco"][j], None, STATUS_HIST)
    _confere(r["rentabilidade"]["d1"], 0.0, "ok")
    for j in ("m1", "m6", "a1"):
        _confere(r["rentabilidade"][j], None, STATUS_HIST)
    _confere(r["rentabilidade"]["ibov"]["d1"], 0.0, "ok")
    for j in ("m1", "m6", "a1"):
        _confere(r["rentabilidade"]["ibov"][j], None, STATUS_HIST)
    for j in JANELAS:
        _confere(r["rentabilidade"]["setor"][j], None, "indisponivel")
    _confere(r["volume"]["total"], 1000.0, "ok")
    assert r["volume"]["relativo"] == {"valor": None, "status": STATUS_HIST, "texto": None}
    _confere(r["volume"]["mediana_20"], None, STATUS_HIST)
    _confere(r["volume"]["posicao_pct"], None, STATUS_HIST)
    assert r["volatilidade_20d"] == {"valor": None, "status": STATUS_HIST, "texto": None,
                                     "posicao_pct": {"valor": None, "status": STATUS_HIST}}
    assert r["beta"] == {"valor": None, "status": STATUS_HIST, "texto": None}
    assert r["pl"]["valor"] == pytest.approx(6.896551724137931, rel=1e-12)
    assert (r["pl"]["status"], r["pl"]["texto"]) == ("ok", None)
    _confere(r["pl"]["setor"], None, "indisponivel")
    _confere(r["pvp"], 0.8333333333333334, "ok")
    _confere(r["roe"], 0.12083333333333333, "ok")
    _confere(r["dividend_yield"], 0.05, "ok")
    _confere(r["payout"], 0.3448275862068966, "ok")
    _confere(r["margem_bruta"], 0.3900709219858156, "ok")
    _confere(r["margem_liquida"], 0.10283687943262411, "ok")
    _confere(r["pvp"]["setor"], None, "indisponivel")
    assert r["payout_por_ano"] == [{"ano": 2024, "valor": pytest.approx(0.2153846153846154, rel=1e-12),
                                    "status": "ok"}]
    anos = [(p["ano"], p["valor"], p["status"]) for p in r["proventos_por_ano"]]
    assert [a[0] for a in anos] == [2021, 2022, 2023, 2024, 2025]
    assert [a[1] for a in anos] == [0.0, 0.0, 0.0, 0.7, 0.5]
    assert all(a[2] == "ok" for a in anos)
    for campo in ("valor_12m", "margem", "setor_margem"):
        _confere(r["ebitda"][campo], None, "indisponivel")
    assert r["ebitda"]["rotulo"] == "EBITDA (cálculo padrão CVM)"
    e = r["endividamento"]
    for campo in ("divida_liquida", "dl_pl", "dl_ebitda", "setor_dl_pl", "setor_dl_ebitda"):
        _confere(e[campo], None, "indisponivel")
    assert e["caixa_liquido"] == {"valor": None, "status": "indisponivel"}
    assert e["aviso"] == "Dívida líquida sem arrendamentos."
    assert r["setor_comparacao_fraca"] is True
    assert r["balanco_referencia"] == {"data_fim_periodo": "2025-06-30", "data_entrega": "2025-08-10",
                                       "status": "ok"}


def test_resumo_acao_outros_tickers_gabarito(pacotes):
    regs = pacotes["resumo_acao"]
    abev = _por(regs, "ticker", "ABEV3")
    _confere(abev["rentabilidade"]["d1"], None, "indisponivel")
    _confere(abev["cotacao"]["fechamento"], 10.0, "ok")
    jbss = _por(regs, "ticker", "JBSS32")
    _confere(jbss["volatilidade_20d"]["posicao_pct"], None, "nao_se_aplica")
    _confere(jbss["pl"], None, "indisponivel")
    _confere(jbss["dividend_yield"], None, "indisponivel")


def test_fundamentos_trimestrais_gabarito(pacotes):
    regs = pacotes["fundamentos_trimestrais"]
    assert len(regs) == 16
    assert sorted({r["ticker"] for r in regs}) == ["ITUB4", "PETR3", "PETR4", "TAEE11"]
    for ticker in ("ITUB4", "PETR3", "PETR4", "TAEE11"):
        fins = [r["data_fim_periodo"] for r in regs if r["ticker"] == ticker]
        assert fins == ["2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30"]
    assert max(r["data_entrega"] for r in regs) <= "2025-10-21"
    assert not any(r["data_fim_periodo"] == "2025-09-30" for r in regs)
    p = [r for r in regs if r["ticker"] == "PETR4" and r["data_fim_periodo"] == "2025-06-30"][0]
    assert p["data_entrega"] == "2025-08-10"
    _confere(p["receita_trimestre"], 360.0, "ok")
    _confere(p["receita_12m"], 1410.0, "ok")
    _confere(p["lucro_liquido_trimestre"], 40.0, "ok")
    _confere(p["lucro_liquido_12m"], 145.0, "ok")
    _confere(p["margem_bruta"], 0.3900709219858156, "ok")
    _confere(p["margem_liquida"], 0.10283687943262411, "ok")
    _confere(p["roe"], 0.12083333333333333, "ok")
    _confere(p["payout_12m"], 0.19310344827586207, "ok")
    for campo in ("ebitda_trimestre", "ebitda_12m", "margem_ebitda", "divida_liquida", "dl_pl", "dl_ebitda"):
        _confere(p[campo], None, "indisponivel")
    antigo = [r for r in regs if r["ticker"] == "PETR4" and r["data_fim_periodo"] == "2024-09-30"][0]
    _confere(antigo["receita_trimestre"], 300.0, "ok")
    _confere(antigo["lucro_liquido_12m"], None, STATUS_HIST)


def test_proventos_gabarito(pacotes):
    regs = pacotes["proventos"]
    chaves = [(r["ticker"], r["tipo"], r["data_com"], r["valor_por_acao"]["valor"]) for r in regs]
    assert chaves == [
        ("PETR3", "DIVIDENDO", "2025-08-20", 0.5),
        ("PETR4", "JCP", "2024-10-21", 0.7),
        ("PETR4", "DIVIDENDO", "2025-08-20", 0.5),
        ("TAEE11", "DIVIDENDO", "2025-05-15", 0.9),
    ]
    petr3, jcp, petr4_div = regs[0], regs[1], regs[2]
    assert petr3["data_pagamento"] == {"valor": None, "status": "indisponivel"}
    assert jcp["data_pagamento"] == {"valor": None, "status": "indisponivel"}
    assert petr4_div["data_pagamento"] == {"valor": "2025-09-10", "status": "ok"}
    _confere(petr4_div["valor_por_acao"], 0.5, "ok")


# ---------------------------------------------------------------- caso 2: contrato e metadados

def test_todo_registro_passa_no_contrato_e_tem_metadados(pacotes):
    for pacote, regs in pacotes.items():
        assert regs, pacote
        for reg in regs:
            contrato.validar(pacote, reg)
            assert reg["versao_contrato"] == "1.0"
            assert reg["gerado_em"] == GERADO
            assert reg["dados_ate"] == DADOS_ATE
    json.dumps(pacotes, ensure_ascii=False, allow_nan=False)  # sem NaN nem Infinity


# ---------------------------------------------------------------- caso 3: ausência nunca é zero

def test_ausencia_nunca_e_zero(pacotes):
    for pacote, regs in pacotes.items():
        for reg in regs:
            for folha in _folhas(reg):
                if folha["status"] != "ok":
                    assert folha["valor"] is None or folha["status"] == "lucro_negativo", (pacote, folha)


def test_ebitda_ausente_do_petr4_e_null(pacotes):
    r = _por(pacotes["resumo_acao"], "ticker", "PETR4")
    assert r["ebitda"]["valor_12m"] == {"valor": None, "status": "indisponivel"}


# ---------------------------------------------------------------- caso 4: frações

def test_percentuais_em_fracao(pacotes):
    r = _por(pacotes["resumo_acao"], "ticker", "PETR4")
    assert r["dividend_yield"]["valor"] == pytest.approx(0.05, rel=1e-12)
    assert pacotes["mercado_dia"][0]["cdi_dia"]["valor"] == pytest.approx(0.0006, rel=1e-12)


# ---------------------------------------------------------------- caso 5: point-in-time

def test_nao_usa_dados_depois_de_t(ins, pacotes):
    """Tabelas com linhas de 2025-10-22 (depois de t) não mudam nenhum dos cinco pacotes."""
    precos = pd.concat([ins.precos, _copia_linha(
        ins.precos, ins.precos["ticker"] == "PETR4", data="2025-10-22", fechamento=99.0,
        fechamento_ajustado=99.0)], ignore_index=True)
    balancos = pd.concat([ins.balancos, _copia_linha(
        ins.balancos, ins.balancos["cnpj"] == "33000167000101", data_entrega="2025-10-22")], ignore_index=True)
    proventos = pd.concat([ins.proventos, _copia_linha(
        ins.proventos, ins.proventos["ticker"] == "PETR4", data_com="2025-10-22",
        valor_por_acao=9.9)], ignore_index=True)
    futuro = dataclasses.replace(ins, precos=precos, balancos=balancos, proventos=proventos)
    assert _cinco_pacotes(futuro) == pacotes


# ---------------------------------------------------------------- caso 6: P/L com prejuízo

def test_pl_com_prejuizo_gabarito_unitario():
    cadastro, balancos, acoes, proventos, precos, cal, mudancas = mundo()
    t = date(2026, 3, 16)
    ins = Insumos(
        d=t + timedelta(days=1), t=t, cal=[d for d in cal if d <= t], precos=precos, cadastro=cadastro,
        mudancas=mudancas, balancos=balancos, acoes_emitidas=acoes, proventos=proventos,
        indices=pd.DataFrame(columns=["data", "indice", "valor"]), noticias=pd.DataFrame(),
        composicao=None, exclusoes=EXCL,
    )
    grades = calcular_grades(ins, PARAMS_PRECOS, PARAMS_FUND)
    regs = montar_resumo_acao(ins, grades, PARAMS_FUND, GERADO, DADOS_ATE)
    prej = _por(regs, "ticker", "PREJ3")
    assert prej["pl"]["valor"] == -5.0
    assert prej["pl"]["status"] == "lucro_negativo"
    assert prej["pl"]["texto"] == "P/L −5,0 · Empresa com prejuízo nos últimos 12 meses"
    aaaa = _por(regs, "ticker", "AAAA3")
    _confere(aaaa["pl"], 5.75, "ok")
    _confere(aaaa["pvp"], 0.7076923076923077, "ok")


# ---------------------------------------------------------------- caso 7: corte de 8 trimestres

ZCNPJ = "00000000001616"


def _insumos_zzzz3(t: date) -> Insumos:
    """Empresa nova ZZZZ3 com 10 ITRs de 3 meses (1º trimestre de 2024 ao 2º de 2026)."""
    trimestres = pd.period_range("2024Q1", "2026Q2", freq="Q")
    linhas = []
    for p in trimestres:
        fim = p.end_time.normalize().date()
        ini = p.start_time.date()
        linhas.append(_a("ITR", ini.isoformat(), fim.isoformat(), (fim + timedelta(days=40)).isoformat(),
                         100, 40, 10, 1000))
    cal = [d.date() for d in pd.bdate_range("2024-01-02", "2026-12-31")]
    return Insumos(
        d=t + timedelta(days=1), t=t, cal=[d for d in cal if d <= t],
        precos=pd.DataFrame(columns=["data", "ticker", "fechamento", "fechamento_ajustado", "volume"]),
        cadastro=cadastro_fund_de([("ZZZZ3", ZCNPJ, "Teste", "Teste subsetor", "ON", None, None)]),
        mudancas={}, balancos=balanco_de(ZCNPJ, linhas),
        acoes_emitidas=acoes_de([(ZCNPJ, "2024-01-01", 1000.0, 0.0)]),
        proventos=pd.DataFrame(columns=["ticker", "tipo", "data_com", "valor_por_acao", "data_pagamento"]),
        indices=pd.DataFrame(columns=["data", "indice", "valor"]), noticias=pd.DataFrame(),
        composicao=None, exclusoes=EXCL,
    )


def test_corte_de_oito_trimestres_e_removidos():
    chave = contrato.CHAVES["fundamentos_trimestrais"]
    atual = montar_fundamentos_trimestrais(_insumos_zzzz3(date(2026, 9, 30)), PARAMS_FUND, GERADO, DADOS_ATE)
    assert len(atual) == 8
    assert [r["data_fim_periodo"] for r in atual] == [
        "2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30",
        "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30",
    ]
    estado = montar_fundamentos_trimestrais(_insumos_zzzz3(date(2026, 7, 31)), PARAMS_FUND, GERADO, DADOS_ATE)
    assert [r["data_fim_periodo"] for r in estado][0] == "2024-06-30"
    assert [r["data_fim_periodo"] for r in estado][-1] == "2026-03-31"
    a_enviar, removidos = contrato.comparar_registros(atual, estado, chave)
    assert removidos == [{"ticker": "ZZZZ3", "data_fim_periodo": "2024-06-30"}]
    assert any(r["data_fim_periodo"] == "2026-06-30" for r in a_enviar)


# ---------------------------------------------------------------- caso 8: corte de 5 anos dos proventos

def test_corte_de_cinco_anos_dos_proventos(ins):
    extra = pd.concat([
        _copia_linha(ins.proventos, ins.proventos["ticker"] == "PETR4", data_com="2020-12-30",
                     valor_por_acao=0.1),
        _copia_linha(ins.proventos, ins.proventos["ticker"] == "PETR4", data_com="2021-01-04",
                     valor_por_acao=0.2),
    ], ignore_index=True)
    com_antigos = dataclasses.replace(ins, proventos=pd.concat([ins.proventos, extra], ignore_index=True))
    datas = [r["data_com"] for r in montar_proventos(com_antigos, PARAMS_FUND, GERADO, DADOS_ATE)
             if r["ticker"] == "PETR4"]
    assert "2020-12-30" not in datas
    assert "2021-01-04" in datas
