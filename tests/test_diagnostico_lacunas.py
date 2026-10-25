"""Testes da seção de lacunas nas séries de preços e índices (diagnostico/lacunas.py).

Sem banco e sem rede: `fontes.ler_tabela` é trocado por monkeypatch. Casos L1, L2 e L3 do plano (seção 2.3).
"""

from datetime import date

import pandas as pd
import pytest

from fabrica_precos import indices_de, precos_de, pregoes_uteis
from processamento import fontes
from processamento.diagnostico.lacunas import COLUNAS, lacunas_em_meses, lacunas_em_pregoes, secao_lacunas

CAL = pregoes_uteis(20)   # 0 = 2025-01-02 ... 19 = 2025-01-29
V = [CAL[i] for i in (0, 1, 8, 9, 10, 11, 12, 14, 15)]
M = ["2024-11", "2024-12", "2025-03", "2025-04"]

EXISTENTES = {fontes.nome_real("precos"), fontes.nome_real("indices")}

NOTA_PRECOS = (
    "1 lacunas de mais de 5 pregões em 1 tickers de v1-precos (fechamento_ajustado, só dentro do período com preço "
    "de cada ticker): as janelas com base dentro delas saem historico_insuficiente "
    "(fase1.base_defasagem_max_pregoes = 5)"
)
NOTA_INDICES = (
    "4 lacunas em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão sem taxa "
    "no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)"
)


def _serie(ticker, idx):
    """Linhas de v1-precos de `ticker` nos pregões `idx` (de CAL), com preço 10.0."""
    datas = [CAL[i] for i in idx]
    return precos_de(ticker, datas, [10.0] * len(datas))


def _indice(nome, idx):
    """Linhas de v1-indices de `nome` nos pregões `idx` (de CAL), com valor 1.0."""
    return [(CAL[i].isoformat(), nome, 1.0) for i in idx]


PRECOS = pd.concat([
    _serie("IBOV", range(20)),
    _serie("AAAA3", [0, 1] + list(range(8, 20))),
    _serie("BBBB3", range(10, 20)),
    _serie("CCCC3", range(13)),
    _serie("DDDD3", list(range(5)) + list(range(10, 20))),
], ignore_index=True)

INDICES = indices_de(
    _indice("IDIV", list(range(4)) + list(range(10, 14)))
    + _indice("SMLL", [i for i in range(20) if i not in range(7, 12)])
    + _indice("CDI", [i for i in range(20) if i != 15])
    + [("2024-08-01", "IPCA", 1.0), ("2024-10-01", "IPCA", 1.0), ("2024-11-01", "IPCA", 1.0)]
)


@pytest.fixture(scope="module")
def mapa():
    """Mapa real do fontes.yaml (só leitura do arquivo, sem banco)."""
    return fontes.carregar_mapa()


@pytest.fixture
def tabelas(monkeypatch):
    """Tabelas servidas por `fontes.ler_tabela`; o teste pode trocar o conteúdo do dicionário."""
    dados = {"precos": PRECOS.copy(), "indices": INDICES.copy()}
    monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: dados[tabela].copy())
    return dados


# L1: lacunas_em_pregoes

def test_l1_lacuna_no_meio_com_minimo_5():
    assert lacunas_em_pregoes(V, CAL, 5) == [(date(2025, 1, 6), date(2025, 1, 13), 6)]


def test_l1_minimo_0_pega_lacuna_de_1():
    assert lacunas_em_pregoes(V, CAL, 0) == [
        (date(2025, 1, 6), date(2025, 1, 13), 6),
        (date(2025, 1, 21), date(2025, 1, 21), 1),
    ]


def test_l1_trecho_final_com_minimo_fim_3():
    assert lacunas_em_pregoes(V, CAL, 5, minimo_fim=3) == [
        (date(2025, 1, 6), date(2025, 1, 13), 6),
        (date(2025, 1, 24), date(2025, 1, 29), 4),
    ]


def test_l1_trecho_final_com_minimo_fim_5_nao_entra():
    assert lacunas_em_pregoes(V, CAL, 5, minimo_fim=5) == [(date(2025, 1, 6), date(2025, 1, 13), 6)]


def test_l1_lacuna_de_exatamente_5_nao_entra():
    assert lacunas_em_pregoes([CAL[i] for i in (0, 6, 7)], CAL, 5) == []


def test_l1_sem_valor_e_comeco_tardio():
    assert lacunas_em_pregoes([], CAL, 5) == []
    assert lacunas_em_pregoes([CAL[i] for i in range(10, 20)], CAL, 5) == []


def test_l1_data_fora_do_calendario_e_ignorada():
    assert lacunas_em_pregoes([date(2025, 1, 4)], CAL, 5) == []


# L2: lacunas_em_meses

def test_l2_meses_faltando_entre_o_primeiro_e_o_ultimo():
    assert lacunas_em_meses(M) == [("2025-01", "2025-02", 2)]


def test_l2_atraso_no_fim_ate_agosto():
    assert lacunas_em_meses(M, pd.Period("2025-08", "M")) == [
        ("2025-01", "2025-02", 2),
        ("2025-05", "2025-08", 4),
    ]


def test_l2_ate_igual_ao_ultimo_nao_adiciona_nada():
    assert lacunas_em_meses(M, pd.Period("2025-04", "M")) == [("2025-01", "2025-02", 2)]


def test_l2_sem_meses_e_vazio():
    assert lacunas_em_meses([], pd.Period("2025-04", "M")) == []


# L3: secao_lacunas

def test_l3_secao_com_lacunas_de_precos_e_indices(mapa, tabelas):
    secao = secao_lacunas(None, mapa, EXISTENTES)
    assert secao["titulo"] == "Lacunas nas séries de preços e índices"
    assert secao["notas"] == [NOTA_PRECOS, NOTA_INDICES]
    assert secao["divergencias"] == []
    assert secao["tabelas"] == [
        {
            "subtitulo": "Lacunas em v1-precos (mais de 5 pregões)",
            "colunas": COLUNAS,
            "linhas": [["AAAA3", "2025-01-06", "2025-01-13", 6, "pregões"]],
        },
        {
            "subtitulo": "Lacunas em v1-indices",
            "colunas": COLUNAS,
            "linhas": [
                ["CDI", "2025-01-23", "2025-01-23", 1, "pregões"],
                ["IDIV", "2025-01-08", "2025-01-15", 6, "pregões"],
                ["IDIV", "2025-01-22", "2025-01-29", 6, "pregões"],
                ["IPCA", "2024-09", "2024-09", 1, "meses"],
            ],
        },
    ]


def test_l3_sem_lacunas_so_notas_de_nenhuma(mapa, tabelas):
    tabelas["precos"] = _serie("IBOV", range(20))
    tabelas["indices"] = indices_de([])
    secao = secao_lacunas(None, mapa, EXISTENTES)
    assert secao["notas"] == [
        "nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço "
        "de cada ticker)",
        "nenhuma lacuna em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão "
        "sem taxa no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)",
    ]
    assert secao["tabelas"] == []


def test_l3_precos_sem_ibov_nao_faz_a_checagem(mapa, tabelas):
    tabelas["precos"] = _serie("AAAA3", range(20))
    secao = secao_lacunas(None, mapa, EXISTENTES)
    assert secao["notas"] == ["sem pregão com preço do IBOV: checagem não feita"]
    assert secao["tabelas"] == []


def test_l3_tabela_ausente_vira_nota_pulada(mapa, tabelas):
    secao = secao_lacunas(None, mapa, set())
    assert len(secao["notas"]) == 1
    assert secao["notas"][0].startswith("pulada: tabela ausente")
    assert secao["tabelas"] == []


def test_l3_so_precos_existe_indices_pulada(mapa, tabelas):
    secao = secao_lacunas(None, mapa, {fontes.nome_real("precos")})
    assert len(secao["notas"]) == 2
    assert secao["notas"][0] == NOTA_PRECOS
    assert secao["notas"][1].startswith("pulada: tabela ausente")
