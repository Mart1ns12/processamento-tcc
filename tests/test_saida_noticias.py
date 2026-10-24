"""Testes do pacote `noticias_dia` (plano da etapa 7, Fase 6c; casos 1 a 4 da Fase 6c e gabarito da 4.7).

Sem rede e sem banco: `banco_teste` é o SQLite de tests/dados (conftest). Nunca `fontes.criar_engine`.
"""

from __future__ import annotations

import json
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fabrica_experimento import noticias_de
from fabrica_saida import DADOS_ATE, GERADO, insumos_de_teste

from processamento.exclusoes import Exclusoes
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.saida import contrato
from processamento.saida.insumos import Insumos
from processamento.saida.pacote_noticias import janela_do_dia, montar_noticias_dia

SP = ZoneInfo("America/Sao_Paulo")
PARAMS = carregar_parametros_experimento()
CAL = [date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]
T = date(2026, 10, 22)
D = date(2026, 10, 23)
CNPJ_DE = {"AAAA3": "1", "AAAA4": "1", "BBBB3": "2", "CCCC3": "3"}
ZERO = {"valor": 0, "status": "ok"}
SEM_DADO = {"valor": None, "status": "indisponivel"}


def sp(texto: str) -> pd.Timestamp:
    """Instante de São Paulo a partir de 'AAAA-MM-DD HH:MM[:SS]'."""
    return pd.Timestamp(texto).tz_localize(SP)


# (id, ticker, publicação (SP), dia, pp, pn, origem, papel, tipo), como a tabela da Fase 3 (plano)
LINHAS_DO_PLANO = [
    ("n01", "AAAA4", sp("2026-10-22 08:00:00"), "2026-10-22", 0.5, 0.1, "google_news", None, None),
    ("n02", "AAAA4", sp("2026-10-22 08:00:01"), "2026-10-22", 0.70, 0.10, "google_news", None, None),
    ("n02", "AAAA3", sp("2026-10-22 08:00:01"), "2026-10-22", 0.70, 0.10, "google_news", None, None),
    ("n03", "AAAA3", sp("2026-10-22 14:30:00"), "2026-10-22", 0.05, 0.85, "google_news", "protagonista", None),
    ("n04", "AAAA4", sp("2026-10-22 17:00:00"), "2026-10-22", 0.30, 0.30, "google_news", None, None),
    ("n05", "AAAA3", sp("2026-10-22 19:42:00"), "2026-10-22", 0.60, 0.20, "google_news", None, None),
    ("n06", "AAAA3", sp("2026-10-22 04:00:00"), "2026-10-22", 0.10, 0.10, "google_news", None, None),
    ("n07", "AAAA3", None, "2026-10-22", 0.20, 0.30, "cvm_ipe", None, None),
    ("n08", "AAAA4", sp("2026-10-23 07:59:59"), "2026-10-23", 0.15, 0.70, "google_news", None, None),
    ("n09", "AAAA4", sp("2026-10-23 08:00:01"), "2026-10-23", 0.5, 0.1, "google_news", None, None),
    ("n10", "AAAA4", sp("2026-10-22 19:50:00"), "2026-10-22", 0.60, 0.20, "google_news", None, None),
    ("n11", "BBBB3", sp("2026-10-22 11:00:00"), "2026-10-22", 0.50, 0.10, "google_news", None, None),
]


def _noticias_do_plano() -> pd.DataFrame:
    """Notícias da tabela da Fase 3, com fonte, link e o título de n10 trocado pelo de n05 (E10)."""
    df = noticias_de(LINHAS_DO_PLANO)
    df = df.assign(fonte="Fonte X", link=[f"https://exemplo.invalid/{i}" for i in df["id"]])
    return df.assign(titulo=df["titulo"].where(df["id"] != "n10", "titulo n05"))


def _insumos_do_plano(t: date = T) -> Insumos:
    """Insumos montados à mão: só cal, cadastro, notícias e D/t; o resto vazio (não é usado aqui)."""
    cadastro = pd.DataFrame({
        "ticker": ["AAAA3", "AAAA4", "BBBB3", "CCCC3"],
        "cnpj": [CNPJ_DE[k] for k in ("AAAA3", "AAAA4", "BBBB3", "CCCC3")],
        "setor": ["Setor X"] * 4,
    })
    return Insumos(
        d=D, t=t, cal=CAL, precos=pd.DataFrame(), cadastro=cadastro, mudancas={},
        balancos=pd.DataFrame(), acoes_emitidas=pd.DataFrame(), proventos=pd.DataFrame(),
        indices=pd.DataFrame(), noticias=_noticias_do_plano(), composicao=None, exclusoes=Exclusoes(),
    )


def _registros(ins: Insumos) -> dict[str, dict]:
    """Registros do `noticias_dia` indexados por ticker."""
    janela = janela_do_dia(ins, PARAMS)
    return {r["ticker"]: r for r in montar_noticias_dia(ins, janela, GERADO, DADOS_ATE)}


def _ids(registro: dict) -> list[str]:
    return [item["id"] for item in registro["itens"]]


# ---------------------------------------------------------------- 1. gabarito E2E (banco de teste)

def test_gabarito_e2e_banco_de_teste(banco_teste):
    """PETR4/PETR3 com n000008 (pré-abertura de t); TAEE11 sem itens (notícias de t-1 e CVM fora da janela)."""
    ins = insumos_de_teste(banco_teste())
    assert (ins.t, ins.d) == (date(2025, 10, 21), date(2025, 10, 22))
    regs = _registros(ins)

    for ticker in ("PETR4", "PETR3"):
        r = regs[ticker]
        assert _ids(r) == ["n000008"]
        item = r["itens"][0]
        assert item["janela"] == "pregao"
        assert item["rotulo"] == "neutro"
        assert item["destaque"] == 1
        assert item["publicado_em"] == "2025-10-21T09:00:00-03:00"
        assert r["resumo"]["quantidade"] == {"valor": 1, "status": "ok"}
        assert r["resumo"]["neutras"] == {"valor": 1, "status": "ok"}
        assert r["resumo"]["positivas"] == {"valor": 0, "status": "ok"}
        assert r["resumo"]["negativas"] == {"valor": 0, "status": "ok"}
        assert r["resumo"]["tom_medio"]["status"] == "ok"
        assert r["resumo"]["tom_medio"]["valor"] == pytest.approx(-0.1, abs=1e-12)

    taee = regs["TAEE11"]
    assert taee["itens"] == []
    assert taee["resumo"]["quantidade"] == ZERO
    assert taee["resumo"]["tom_medio"] == {"valor": None, "status": "nao_se_aplica"}
    assert taee["data_referencia"] == "2025-10-21"
    assert taee["janela_inicio"] == "2025-10-21T08:00:01-03:00"
    assert taee["janela_fim"] == "2025-10-22T08:00:00-03:00"


# ---------------------------------------------------------------- 2. gabarito da Fase 3 embalado

def test_gabarito_fase3_embalado():
    """AAAA3 e AAAA4 (mesma empresa) com os 7 itens da Fase 3; CCCC3 sem notícia."""
    regs = _registros(_insumos_do_plano())
    esperado = ["n03", "n02", "n08", "n05", "n07", "n06", "n04"]

    for ticker in ("AAAA3", "AAAA4"):
        r = regs[ticker]
        assert _ids(r) == esperado
        assert [item["destaque"] for item in r["itens"]] == list(range(1, 8))
        assert r["data_referencia"] == "2026-10-22"
        assert r["janela_inicio"] == "2026-10-22T08:00:01-03:00"
        assert r["janela_fim"] == "2026-10-23T08:00:00-03:00"
        assert r["resumo"]["quantidade"] == {"valor": 7, "status": "ok"}
        assert r["resumo"]["tom_medio"]["valor"] == pytest.approx(-0.45 / 7, abs=1e-12)

        sem_hora = next(i for i in r["itens"] if i["id"] == "n06")
        assert sem_hora["publicado_em"] is None
        assert sem_hora["precisao_hora"] == "meia_noite_pacifico"
        assert sem_hora["janela"] == "sem_horario"

        n02 = next(i for i in r["itens"] if i["id"] == "n02")
        assert n02["publicado_em"] == "2026-10-22T08:00:01-03:00"
        assert n02["janela"] == "pregao"

    assert _registros(_insumos_do_plano())["BBBB3"]["itens"][0]["id"] == "n11"

    cccc = regs["CCCC3"]
    assert cccc["itens"] == []
    assert cccc["resumo"]["quantidade"] == ZERO
    assert cccc["resumo"]["tom_medio"] == {"valor": None, "status": "nao_se_aplica"}


# ---------------------------------------------------------------- 3. antes da cobertura

def test_antes_da_cobertura_todas_as_folhas_indisponiveis():
    """t = 2026-10-21 é anterior à menor data_publicacao lida (2026-10-22): resumo indisponível, itens []."""
    regs = _registros(_insumos_do_plano(t=date(2026, 10, 21)))
    for ticker in ("AAAA3", "AAAA4", "BBBB3", "CCCC3"):
        r = regs[ticker]
        assert r["itens"] == []
        for chave in ("quantidade", "positivas", "neutras", "negativas", "tom_medio"):
            assert r["resumo"][chave] == SEM_DADO


# ---------------------------------------------------------------- 4. validação do contrato

def test_todos_os_registros_passam_no_contrato(banco_teste):
    """Os registros dos cenários 1 a 3 passam em `contrato.validar` e serializam sem NaN."""
    cenarios = [
        _registros(insumos_de_teste(banco_teste())),
        _registros(_insumos_do_plano()),
        _registros(_insumos_do_plano(t=date(2026, 10, 21))),
    ]
    for regs in cenarios:
        for registro in regs.values():
            contrato.validar("noticias_dia", registro)
            json.dumps(registro, ensure_ascii=False, allow_nan=False)
