"""Testes da seção "Histórico novo" do diagnóstico (historico.py), sem banco: `ler` falso ou sem `ler`."""

from datetime import date

import pandas as pd
import pytest

from processamento import fontes
from processamento.diagnostico.historico import (
    cobertura_por_ano,
    composicao_sem_preco,
    nota_cobertura,
    nota_composicao_sem_preco,
    nota_corrigir_horas,
    secao_historico,
)
from processamento.exclusoes import Exclusoes
from processamento.universo import montar_universo


@pytest.fixture(scope="module")
def mapa():
    """Mapa real do fontes.yaml (só leitura do arquivo, sem banco)."""
    return fontes.carregar_mapa()


def _ler_sem_banco(sql, params=None):
    """Falha se a seção consultar quando nenhuma tabela existe."""
    raise AssertionError(f"não devia consultar: {sql}")


def _ts(s):
    return pd.Timestamp(s) if s is not None else pd.NaT


# ---------------------------------------------------------------------------
# 5A composição sem preço
# ---------------------------------------------------------------------------

def _comp_5a():
    pares = [
        ("PETR4", "2021-01-01", None),
        ("NTCO3", "2021-01-01", "2025-06-30"),
        ("ALPA4", "2021-01-01", "2023-04-30"),
        ("ALPA4", "2023-09-01", "2024-04-30"),
        ("BRML3", "2021-01-01", "2022-11-30"),
        ("CPLE5", "2021-01-01", "2021-12-31"),
        ("AXIA6", "2024-01-01", None),
        ("ELET6", "2021-01-01", "2023-12-31"),
        ("GOLL4", "2021-01-01", "2024-01-02"),
        ("BRDT3", "2021-01-01", "2021-08-31"),
    ]
    return pd.DataFrame({
        "ticker": [p[0] for p in pares],
        "data_inicio": [_ts(p[1]) for p in pares],
        "data_fim": [_ts(p[2]) for p in pares],
    })


def test_composicao_sem_preco_caso_5a():
    linhas = composicao_sem_preco(
        _comp_5a(),
        {"IBOV", "PETR4", "NATU3", "AXIA3"},
        {"NTCO3": "NATU3", "ELET6": "AXIA3", "BRDT3": "VBBR3"},
        {"NTCO3", "ELET6", "BRDT3"},
        {"PETR4", "NATU3", "CPLE3", "AXIA3"},
    )
    assert linhas == [
        ["AXIA6", "empresa_do_cadastro", "2024-01-01", "vigente", "sim"],
        ["BRDT3", "empresa_do_cadastro", "2021-01-01", "2021-08-31", "não"],
        ["CPLE5", "empresa_do_cadastro", "2021-01-01", "2021-12-31", "não"],
        ["ALPA4", "fora_do_cadastro", "2021-01-01", "2024-04-30", "sim"],
        ["BRML3", "fora_do_cadastro", "2021-01-01", "2022-11-30", "não"],
        ["GOLL4", "fora_do_cadastro", "2021-01-01", "2024-01-02", "sim"],
    ]


# ---------------------------------------------------------------------------
# 5B nota da composição sem preço
# ---------------------------------------------------------------------------

def test_nota_composicao_sem_preco_caso_5b():
    linhas = [
        ["AXIA6", "empresa_do_cadastro", "2024-01-01", "vigente", "sim"],
        ["BRDT3", "empresa_do_cadastro", "2021-01-01", "2021-08-31", "não"],
        ["CPLE5", "empresa_do_cadastro", "2021-01-01", "2021-12-31", "não"],
        ["ALPA4", "fora_do_cadastro", "2021-01-01", "2024-04-30", "sim"],
        ["BRML3", "fora_do_cadastro", "2021-01-01", "2022-11-30", "não"],
        ["GOLL4", "fora_do_cadastro", "2021-01-01", "2024-01-02", "sim"],
    ]
    assert nota_composicao_sem_preco(linhas, 10) == (
        "Composição do Ibovespa: 6 de 10 tickers sem nenhum preço em v1-precos (3 código antigo de empresa "
        "do cadastro, 3 fora do cadastro); 3 estiveram no índice em 2024 ou depois. O preço é procurado com a "
        "união das mudanças de ticker (o código antigo vale pelo atual)."
    )


def test_nota_composicao_sem_preco_lista_vazia():
    assert nota_composicao_sem_preco([], 10) == (
        "Composição do Ibovespa: todos os 10 tickers têm preço em v1-precos (com a união das mudanças de ticker)."
    )


# ---------------------------------------------------------------------------
# 5C corrigir_horas
# ---------------------------------------------------------------------------

def test_nota_corrigir_horas_caso_5c():
    df = pd.DataFrame({
        "id": ["2026-10-23-coletar-135621"],
        "status_execucao": ["agendada"],
        "status_etapa": ["pendente"],
        "iniciada_em": ["2026-10-23 16:56:21"],
        "finalizada_em": [None],
    })
    assert nota_corrigir_horas(df) == (
        "corrigir_horas: execução mais recente 2026-10-23-coletar-135621 (status agendada), etapa pendente; "
        "iniciada em 2026-10-23 13:56, finalizada em — (horário de São Paulo)"
    )


def test_nota_corrigir_horas_vazio():
    vazio = pd.DataFrame(columns=["id", "status_execucao", "status_etapa", "iniciada_em", "finalizada_em"])
    assert nota_corrigir_horas(vazio) == "corrigir_horas: nenhuma execução com essa etapa"


# ---------------------------------------------------------------------------
# 5D cobertura por ano e 5E nota
# ---------------------------------------------------------------------------

def _universo_5d():
    cal = [date(2020, 12, 29), date(2020, 12, 30), date(2021, 1, 4), date(2021, 1, 5), date(2021, 1, 6)]
    cadastro = pd.DataFrame({
        "ticker": ["AAAA3", "BBBB4", "CCCC32"],
        "tipo_acao": ["ON", "PN", "BDR"],
    })
    comp = pd.DataFrame({
        "ticker": ["AAAA3", "DDDD3"],
        "data_inicio": [pd.Timestamp("2021-01-01"), pd.Timestamp("2021-01-01")],
        "data_fim": [pd.NaT, pd.Timestamp("2021-01-05")],
    })
    linhas_preco = []
    for d in cal:
        linhas_preco.append(("IBOV", d))
        linhas_preco.append(("AAAA3", d))
        linhas_preco.append(("CCCC32", d))
    linhas_preco += [("BBBB4", d) for d in cal[:3]]
    linhas_preco += [("DDDD3", date(2021, 1, 4)), ("DDDD3", date(2021, 1, 6))]
    precos = pd.DataFrame({
        "data": [pd.Timestamp(d) for _, d in linhas_preco],
        "ticker": [t for t, _ in linhas_preco],
        "fechamento": 10.0,
        "fechamento_ajustado": 10.0,
    })
    return montar_universo(cal, cadastro, precos, Exclusoes(), comp), cal


def test_cobertura_por_ano_caso_5d():
    universo, cal = _universo_5d()
    assert cobertura_por_ano(universo, cal) == [
        [2020, 2, 4, 2, 2.0, 2, "composicao_atual"],
        [2021, 3, 4, 1, 1.0, 2, "composicao_historica"],
    ]


def test_nota_cobertura_caso_5e():
    cal = [date(2020, 12, 29), date(2020, 12, 30), date(2021, 1, 4), date(2021, 1, 5), date(2021, 1, 6)]
    linhas = [[2020, 2, 4, 2, 2.0, 2, "composicao_atual"], [2021, 3, 4, 1, 1.0, 2, "composicao_historica"]]
    assert nota_cobertura(linhas, cal) == (
        "Cobertura do experimento (universo com a composição, motivo ok): 8 linhas em 5 pregões, "
        "de 2020-12-29 a 2021-01-06."
    )


# ---------------------------------------------------------------------------
# 5F seção sem tabelas: 3 notas puladas, sem consulta
# ---------------------------------------------------------------------------

def test_secao_historico_sem_tabelas_caso_5f(mapa):
    secao = secao_historico(_ler_sem_banco, mapa, set(), exclusoes=Exclusoes())
    assert len(secao["notas"]) == 3
    assert all("pulada: tabela ausente" in n for n in secao["notas"])
    assert secao["tabelas"] == []
    assert secao["divergencias"] == []


# ---------------------------------------------------------------------------
# Parte (ii) isolada: só o painel existe; (i) e (iii) puladas
# ---------------------------------------------------------------------------

def test_secao_historico_parte_ii_com_ler_falso(mapa):
    existentes = {"v1-painel_etapas", "v1-painel_execucoes"}
    df_5c = pd.DataFrame({
        "id": ["2026-10-23-coletar-135621"],
        "status_execucao": ["agendada"],
        "status_etapa": ["pendente"],
        "iniciada_em": ["2026-10-23 16:56:21"],
        "finalizada_em": [None],
    })

    def ler(sql, params=None):
        if "corrigir_horas" not in sql:
            raise AssertionError(f"não devia consultar: {sql}")
        return df_5c

    secao = secao_historico(ler, mapa, existentes, exclusoes=Exclusoes())
    assert secao["tabelas"] == []
    assert secao["divergencias"] == []
    assert len(secao["notas"]) == 3
    assert secao["notas"][0].startswith("Composição sem preço: pulada: tabela ausente")
    assert secao["notas"][1] == nota_corrigir_horas(df_5c)
    assert secao["notas"][2].startswith("Cobertura do experimento: pulada: tabela ausente")
