"""Testes da seção de lacunas nas séries de preços e índices (diagnostico/lacunas.py).

Sem banco e sem rede: `fontes.ler_tabela` é trocado por monkeypatch. Casos L1, L2 e L3 do plano (seção 2.3).
"""

import dataclasses
from datetime import date

import pandas as pd
import pytest

from fabrica_precos import indices_de, precos_de, pregoes_uteis
from processamento import fontes
from processamento.diagnostico import lacunas
from processamento.diagnostico.lacunas import (
    COLUNAS,
    lacunas_em_meses,
    lacunas_em_pregoes,
    meses_com_poucas_noticias,
    secao_lacunas,
    secao_noticias_por_mes,
)
from processamento.experimento.parametros import carregar_parametros_experimento

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


# Notícias por mês: meses_com_poucas_noticias (função pura)

def _mensal_2024(valor=100):
    """Contagem de 2024 inteiro com `valor` artigos por mês."""
    return {f"2024-{m:02d}": valor for m in range(1, 13)}


def test_n_a_baixos_fora_de_periodo_e_mes_ausente_vale_zero():
    cont = {**_mensal_2024(), "2025-01": 10, "2025-03": 100, "2025-04": 100}
    baixos, rever = meses_com_poucas_noticias(cont, 0.25, ())
    assert baixos == [
        {"mes": "2025-01", "artigos": 10, "mediana_referencia": 100, "situacao": "rever: fora de periodos_sem_coleta"},
        {"mes": "2025-02", "artigos": 0, "mediana_referencia": 100, "situacao": "rever: fora de periodos_sem_coleta"},
    ]
    assert rever == []


def test_n_b_baixos_dentro_de_periodo_viram_cadastrado():
    cont = {**_mensal_2024(), "2025-01": 10, "2025-03": 100, "2025-04": 100}
    periodos = ((date(2025, 1, 1), date(2025, 2, 28)),)
    baixos, rever = meses_com_poucas_noticias(cont, 0.25, periodos)
    assert [(l["mes"], l["situacao"]) for l in baixos] == [("2025-01", "cadastrado"), ("2025-02", "cadastrado")]
    assert rever == []


def test_n_c_mes_do_periodo_preenchido_deve_ser_revisto():
    cont = {**_mensal_2024(), "2025-01": 100, "2025-02": 100}
    periodos = ((date(2025, 1, 1), date(2025, 1, 31)),)
    baixos, rever = meses_com_poucas_noticias(cont, 0.25, periodos)
    assert baixos == []
    assert rever == ["2025-01"]


def test_n_d_historico_curto_nao_avalia_nada():
    cont = {"2025-01": 100, "2025-02": 100, "2025-03": 100, "2025-04": 100}
    assert meses_com_poucas_noticias(cont, 0.25, ()) == ([], [])


def test_n_e_limite_estrito_25_nao_e_baixo_24_e():
    cont = {**_mensal_2024(), "2025-01": 25, "2025-02": 100}
    assert meses_com_poucas_noticias(cont, 0.25, ()) == ([], [])
    cont["2025-01"] = 24
    baixos, _ = meses_com_poucas_noticias(cont, 0.25, ())
    assert [l["mes"] for l in baixos] == ["2025-01"]


def test_n_f_mes_baixo_nao_entra_na_referencia_dos_seguintes():
    # referência de 3 meses: 2025-04 (10) e 2025-05 (20) são baixos; se 2025-04 entrasse na referência de
    # 2025-05, a mediana seria 30 e 20 não seria baixo (7,5 de corte)
    cont = {"2025-01": 100, "2025-02": 100, "2025-03": 30, "2025-04": 10, "2025-05": 20,
            "2025-06": 100, "2025-07": 100}
    baixos, rever = meses_com_poucas_noticias(cont, 0.25, (), referencia=3, minimo_referencia=3)
    assert baixos == [
        {"mes": "2025-04", "artigos": 10, "mediana_referencia": 100, "situacao": "rever: fora de periodos_sem_coleta"},
        {"mes": "2025-05", "artigos": 20, "mediana_referencia": 100, "situacao": "rever: fora de periodos_sem_coleta"},
    ]
    assert rever == []


def test_n_contagem_vazia_e_vazia():
    assert meses_com_poucas_noticias({}, 0.25, ()) == ([], [])


# Notícias por mês: secao_noticias_por_mes (com banco de teste em SQLite)

@pytest.fixture
def params_noticias(monkeypatch):
    """Sem períodos de coleta e fração 0,25, independentemente do parametros.yaml."""
    params = dataclasses.replace(carregar_parametros_experimento(), periodos_sem_coleta=(),
                                 noticias_mes_fracao_minima=0.25)
    monkeypatch.setattr(lacunas, "carregar_parametros_experimento", lambda *_a, **_k: params)
    return params


def _noticia_banco(id_, dia):
    """Linha de v1-noticias (colunas do banco de teste) publicada em `dia` (AAAA-MM-DD), origem wordpress."""
    return {
        "id": id_, "ticker": "PETR4", "data_hora_publicacao": f"{dia}T10:00:00-03:00",
        "data_hora_coleta": "2026-09-07T17:38:43-03:00", "titulo": f"Notícia {id_}", "fonte": "F",
        "link": f"https://exemplo.invalid/{id_}", "prob_positivo": "0.5", "prob_neutro": "0.3",
        "prob_negativo": "0.2", "origem": "wordpress", "papel": None, "tipo_conteudo": None, "evento": None,
        "qualidade": None, "data_publicacao": dia, "momento_pregao": "durante",
    }


def test_n_secao_noticias_com_banco_de_teste(banco_teste, mapa, params_noticias):
    # 2024: 8 por mês; 2025-01: 1 (baixo); 2025-02 ausente (0, baixo); 2025-03 e 2025-04: 8 (último, incompleto)
    cont = {**_mensal_2024(8), "2025-01": 1, "2025-03": 8, "2025-04": 8}
    linhas, k = [], 0
    for mes, n in cont.items():
        for _ in range(n):
            k += 1
            linhas.append(_noticia_banco(f"w{k:06d}", f"{mes}-15"))

    def _substituir(df):
        return pd.DataFrame(linhas, columns=df.columns)

    ler = banco_teste(alterar={"v1-noticias": _substituir})
    secao = secao_noticias_por_mes(ler, mapa, {fontes.nome_real("noticias")})

    assert secao["titulo"] == "Notícias por mês"
    assert secao["divergencias"] == []
    assert secao["tabelas"] == [{
        "subtitulo": "Meses com poucas notícias",
        "colunas": ["mes", "artigos", "mediana_referencia", "situacao"],
        "linhas": [
            ["2025-01", 1, 8, "rever: fora de periodos_sem_coleta"],
            ["2025-02", 0, 8, "rever: fora de periodos_sem_coleta"],
        ],
    }]
    assert "9 meses avaliados" in secao["notas"][0]
    assert "Atenção: 2 mês(es) com poucas notícias fora de experimento.periodos_sem_coleta: rever o parâmetro." \
        in secao["notas"]


def test_n_secao_noticias_tabela_ausente_vira_nota_pulada(mapa, params_noticias):
    secao = secao_noticias_por_mes(None, mapa, set())
    assert len(secao["notas"]) == 1
    assert secao["notas"][0].startswith("pulada: tabela ausente")
    assert secao["tabelas"] == []
