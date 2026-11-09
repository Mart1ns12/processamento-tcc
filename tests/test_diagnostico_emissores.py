"""Testes do diagnóstico de emissores e de ações emitidas (diagnostico/emissores.py), sem banco nem rede.

Gabaritos da tarefa T7 (03/11/2026). As seções recebem `ler` falso e `fontes.ler_tabela` substituído.
"""

from datetime import date

import pandas as pd
import pytest
from fabrica_emissores import (
    ACOES_HAPV3_LINHAS,
    ACOES_MGLU3_LINHAS,
    CNPJ_HAPV3,
    CNPJ_JBS_NV,
    CNPJ_JBS_SA,
    CNPJ_MGLU3,
    EMISSORES_REAIS,
    acoes_base_de,
    emissores_de,
)
from fabrica_precos import precos_de, pregoes_uteis

from processamento import fontes
from processamento.diagnostico.emissores import (
    coerencia_acoes_eventos,
    eventos_por_pregao,
    problemas_emissores,
    secao_acoes_eventos,
    secao_emissores,
    separar_fora_do_pregao,
)
from processamento.diagnostico.temas import secao_precos, secao_retornos_suspeitos


@pytest.fixture(scope="module")
def mapa():
    """Mapa real do fontes.yaml (só leitura do arquivo, sem banco)."""
    return fontes.carregar_mapa()


def _ler_sem_banco(sql, params=None):
    raise AssertionError(f"não devia consultar: {sql}")


CADASTRO = pd.DataFrame({
    "ticker": ["HAPV3", "MGLU3", "JBSS32", "NATU3", "PETR4", "XXXX3"],
    "cnpj": [CNPJ_HAPV3, "47960950000122", CNPJ_JBS_NV, "71673990000177", "33000167000101", "32785497000197"],
})


# ---------------------------------------------------------------------------
# problemas_emissores
# ---------------------------------------------------------------------------

def test_problemas_emissores_gabarito():
    problemas = problemas_emissores(EMISSORES_REAIS, CADASTRO)
    assert problemas["sobrepostas"] == []
    assert problemas["lacunas"] == []
    assert problemas["difere_cadastro"] == [("MGLU3", "47960950000121", "47960950000122")]
    assert problemas["sem_emissor"] == ["PETR4", "XXXX3"]
    assert problemas["cnpj_de_outra_empresa"] == [("NATU3", "32785497000197", "XXXX3")]


def test_sobreposicao_e_lacuna_entre_vigencias_consecutivas():
    emissores = emissores_de([
        ("X3", 1, "X3", "11111111000111", "A", None, "2020-01-10", 1.0),
        ("X3", 2, "X3", "11111111000111", "A", "2020-01-12", "2021-01-01", 1.0),
        ("Y3", 1, "Y3", "22222222000122", "B", None, "2021-06-30", 1.0),
        ("Y3", 2, "Y3", "22222222000122", "B", "2021-06-30", None, 1.0),
    ])
    problemas = problemas_emissores(emissores, CADASTRO)
    assert problemas["sobrepostas"] == ["Y3: ordem 1 e ordem 2"]
    assert problemas["lacunas"] == ["X3: sem emissor de 2020-01-11 a 2020-01-11"]


# ---------------------------------------------------------------------------
# coerencia_acoes_eventos
# ---------------------------------------------------------------------------

MGLU3_AJUSTADA = [
    (c, dr, de, qon, qpn, 6823873190 if dr == "2021-06-30" else bon, bpn, sit)
    for (c, dr, de, qon, qpn, bon, bpn, sit) in ACOES_MGLU3_LINHAS
]
ACOES_GABARITO = acoes_base_de(
    ACOES_HAPV3_LINHAS
    + MGLU3_AJUSTADA
    + [
        ("99999999000199", "2025-09-30", "2025-11-10", 1000, 0, 1000, 0, "ok"),
        (CNPJ_JBS_SA, "2024-12-31", "2025-03-26", 2218116370, 0, 1109058185, 0, "ok"),
        (CNPJ_HAPV3, "2024-03-31", "2024-05-15", 7539463263, 0, None, None, "anulado"),
    ]
)

EVENTOS_GABARITO = pd.DataFrame({
    "ticker": ["HAPV3", "HAPV3", "MGLU3", "MGLU3", "MGLU3", "ZZZZ3"],
    "data_com": pd.to_datetime(["2020-11-24", "2025-06-05", "2020-10-13", "2024-05-24", "2025-12-29", "2025-12-19"]),
    "tipo": ["DESDOBRAMENTO", "GRUPAMENTO", "DESDOBRAMENTO", "GRUPAMENTO", "BONIFICACAO", "BONIFICACAO"],
    "fator": [5.0, 0.066667, 4.0, 0.1, 1.05, 1.262838],
    "isin": ["BRHAPVACNOR4", "BRHAPVACNOR4", "BRMGLUACNOR2", "BRMGLUACNOR2", "BRMGLUACNOR2", "BRZZZZACNOR0"],
    "isin_emitido": ["BRHAPVACNOR4", "BRHAPVACNOR4", "BRMGLUACNOR2", "BRMGLUACNOR2", "BRMGLUACNOR2", "BRZZZZACNPB0"],
    "cnpj": [CNPJ_HAPV3, CNPJ_HAPV3, CNPJ_MGLU3, CNPJ_MGLU3, CNPJ_MGLU3, "99999999000199"],
})


def test_coerencia_acoes_eventos_gabarito():
    df = coerencia_acoes_eventos(ACOES_GABARITO, EVENTOS_GABARITO, EMISSORES_REAIS)
    assert len(df) == 2
    # 09/11/2026 (eventos depois da data_referencia): a MGLU3 ref. 30/09/2020, entregue em 09/11/2020, já vem
    # com a quantidade depois do desdobramento 4 de 13/10/2020, então a razão é 0,25 (pela entrega batia).
    antes = df.iloc[0]
    assert antes["data_referencia"] == pd.Timestamp("2020-09-30")
    assert antes["fator_eventos"] == pytest.approx(0.42, rel=1e-9)
    assert antes["razao"] == pytest.approx(0.25, rel=1e-6)
    linha = df.iloc[1]
    assert linha["cnpj"] == CNPJ_MGLU3
    assert linha["data_referencia"] == pd.Timestamp("2021-06-30")
    assert linha["qtd_total"] == pytest.approx(6498926848, rel=1e-12)
    assert linha["fator_eventos"] == pytest.approx(0.105, rel=1e-9)
    assert linha["fator_acoes"] == pytest.approx(1.0, rel=1e-12)
    assert linha["esperado"] == pytest.approx(682387319.04, rel=1e-6)
    assert linha["base_total"] == pytest.approx(6823873190, rel=1e-12)
    assert linha["razao"] == pytest.approx(10.0, rel=1e-6)


def test_coerencia_sem_linhas_devolve_tabela_vazia_com_colunas():
    df = coerencia_acoes_eventos(ACOES_GABARITO.iloc[0:0], EVENTOS_GABARITO, EMISSORES_REAIS)
    assert df.empty
    assert list(df.columns) == [
        "cnpj", "data_referencia", "data_entrega", "qtd_total", "fator_eventos", "fator_acoes", "esperado",
        "base_total", "razao",
    ]


# ---------------------------------------------------------------------------
# eventos_por_pregao
# ---------------------------------------------------------------------------

CAL_EVENTOS = [date(2026, 4, 16), date(2026, 4, 17), date(2026, 4, 20)]


def _evento_azul(data_com: str) -> pd.DataFrame:
    return pd.DataFrame({
        "ticker": ["AZUL3"],
        "data_com": pd.to_datetime([data_com]),
        "tipo": ["GRUPAMENTO"],
        "fator": [0.000007],
    })


def test_eventos_por_pregao_marca_data_com_e_proximo_pregao():
    marcas = eventos_por_pregao(_evento_azul("2026-04-17"), CAL_EVENTOS)
    texto = "GRUPAMENTO 0,000007 (data_com 2026-04-17)"
    assert marcas == {("AZUL3", date(2026, 4, 17)): texto, ("AZUL3", date(2026, 4, 20)): texto}


def test_eventos_por_pregao_data_com_fim_de_semana_marca_so_o_proximo_pregao():
    marcas = eventos_por_pregao(_evento_azul("2026-04-18"), CAL_EVENTOS)
    assert list(marcas) == [("AZUL3", date(2026, 4, 20))]
    assert marcas[("AZUL3", date(2026, 4, 20))] == "GRUPAMENTO 0,000007 (data_com 2026-04-18)"


# ---------------------------------------------------------------------------
# separar_fora_do_pregao
# ---------------------------------------------------------------------------

def test_separar_fora_do_pregao_gabarito():
    fora = {"JBSS32": [date(2020, 11, 20)], "NATU3": [date(2020, 11, 20), date(2021, 1, 2)], "PETR4": [date(2022, 3, 5)]}
    conhecidas = {"JBSS32": ["2020-11-20"], "NATU3": ["2020-11-20"]}
    desconhecidas, encontradas = separar_fora_do_pregao(fora, conhecidas)
    assert desconhecidas == {"NATU3": [date(2021, 1, 2)], "PETR4": [date(2022, 3, 5)]}
    assert encontradas == {"JBSS32": [date(2020, 11, 20)], "NATU3": [date(2020, 11, 20)]}


# ---------------------------------------------------------------------------
# Seções (com ler falso e tabelas servidas por monkeypatch)
# ---------------------------------------------------------------------------

def test_secao_emissores_pulada_sem_tabela(mapa):
    secao = secao_emissores(_ler_sem_banco, mapa, set())
    assert secao["notas"] == ["pulada: tabela ausente (`v1-emissores_ticker`)"]
    assert secao["divergencias"] == []


def test_secao_emissores_mostra_problemas_do_cadastro(mapa, monkeypatch):
    tabelas = {"emissores_ticker": EMISSORES_REAIS, "cadastro": CADASTRO}
    monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: tabelas[tabela].copy())
    secao = secao_emissores(_ler_sem_banco, mapa, {"v1-emissores_ticker", "v1-cadastro"})

    assert secao["notas"][0] == "7 linhas, 4 tickers; 2 com mais de um emissor"
    assert len(secao["tabelas"]) == 1 and len(secao["tabelas"][0]["linhas"]) == 5
    temas = sorted((d["tema"], d["detalhe"]) for d in secao["divergencias"])
    assert temas == [
        ("cnpj_de_outra_empresa", "NATU3: cnpj 32785497000197 é o do cadastro de XXXX3"),
        ("emissor_difere_cadastro", "MGLU3: emissor 47960950000121, cadastro 47960950000122"),
    ]
    assert "Tickers do cadastro sem emissor em v1-emissores_ticker: PETR4, XXXX3" in secao["notas"]


def test_secao_acoes_eventos_pulada_sem_tabela(mapa):
    secao = secao_acoes_eventos(_ler_sem_banco, mapa, set())
    assert secao["notas"] == ["pulada: tabela ausente (`v1-acoes_emitidas`)"]
    assert secao["divergencias"] == []


def test_secao_acoes_eventos_coerencia_com_eventos(mapa, monkeypatch):
    tabelas = {"acoes_emitidas": ACOES_GABARITO, "emissores_ticker": EMISSORES_REAIS}
    monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: tabelas[tabela].copy())
    monkeypatch.setattr(fontes, "ler_eventos_acoes", lambda ler=None: EVENTOS_GABARITO.copy())
    existentes = {"v1-acoes_emitidas", "v1-eventos_acoes", "v1-emissores_ticker"}

    secao = secao_acoes_eventos(_ler_sem_banco, mapa, existentes)

    assert secao["divergencias"] == []  # o anulado sem base e a linha ok com base vazia não existem aqui
    assert secao["notas"] == [
        "2 linhas incoerentes com os eventos (base_atual ≠ quantidade × fatores posteriores à data de referência × "
        "fator_acoes, tolerância 1%; fatores arredondados como 0,000007 podem aparecer)"
    ]
    assert len(secao["tabelas"]) == 1
    assert len(secao["tabelas"][0]["linhas"]) == 2


def test_secao_acoes_eventos_divergencias_de_base_e_entrega(mapa, monkeypatch):
    acoes = acoes_base_de([
        (CNPJ_HAPV3, "2024-03-31", "2024-05-15", 100, 0, None, None, "anulado"),   # anulado sem base: ok
        (CNPJ_HAPV3, "2024-06-30", "2024-05-15", 100, 0, 100, 0, "ok"),          # entrega antes da referência
        (CNPJ_MGLU3, "2024-09-30", None, 100, 0, None, 0, "ok"),                 # sem entrega e base vazia
        (CNPJ_MGLU3, "2024-12-31", "2025-03-26", 100, 0, 100, 0, "anulado"),     # anulado com base
        (CNPJ_MGLU3, "2025-03-31", "2025-05-10", 100, 40, 140, None, "ok"),       # só PN vazia: nota, não divergência
        (CNPJ_MGLU3, "2025-06-30", "2025-08-10", 100, 40, 140, None, "corrigido_escala"),
    ])
    tabelas = {"acoes_emitidas": acoes, "emissores_ticker": EMISSORES_REAIS}
    monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: tabelas[tabela].copy())
    monkeypatch.setattr(fontes, "ler_eventos_acoes", lambda ler=None: EVENTOS_GABARITO.copy())
    existentes = {"v1-acoes_emitidas", "v1-eventos_acoes", "v1-emissores_ticker"}

    secao = secao_acoes_eventos(_ler_sem_banco, mapa, existentes)

    temas = sorted(d["tema"] for d in secao["divergencias"])
    assert temas == [
        "acoes_anulado_com_base",
        "acoes_entrega_antes_da_referencia",
        "acoes_sem_base",
        "acoes_sem_entrega",
    ]
    assert [d["detalhe"] for d in secao["divergencias"] if d["tema"] == "acoes_sem_base"] == [
        f"{CNPJ_MGLU3} 2024-09-30: base atual vazia"
    ]
    assert (f"2 linhas com qtd_pn_base_atual vazia e qtd_on_base_atual preenchida (PN extinta na troca por ON; "
            f"nas contas a PN vale zero): {CNPJ_MGLU3} (2)") in secao["notas"]


def test_coerencia_usa_eventos_posteriores_a_data_de_referencia():
    # 09/11/2026: a quantidade é a da data de referência. Desdobramento 2 entre a referência (31/03) e a
    # entrega (15/05): a base atual 200 bate com 100 × 2 e não é incoerente (pela entrega, daria razão 2).
    acoes = acoes_base_de([("99999999000199", "2025-03-31", "2025-05-15", 100, 0, 200, 0, "ok")])
    eventos = pd.DataFrame({
        "ticker": ["ZZZZ3"], "data_com": pd.to_datetime(["2025-04-10"]), "tipo": ["DESDOBRAMENTO"],
        "fator": [2.0], "isin": ["BRZZZZACNOR0"], "isin_emitido": ["BRZZZZACNOR0"], "cnpj": ["99999999000199"],
    })
    assert coerencia_acoes_eventos(acoes, eventos, EMISSORES_REAIS).empty
    # Evento no próprio dia da referência não entra (a quantidade já é a do fim do dia).
    eventos_no_dia = eventos.assign(data_com=pd.to_datetime(["2025-03-31"]))
    df = coerencia_acoes_eventos(acoes, eventos_no_dia, EMISSORES_REAIS)
    assert len(df) == 1 and df.iloc[0]["razao"] == pytest.approx(2.0, rel=1e-12)


CAL_R = pregoes_uteis(6, "2026-04-06")
PRECOS_R = pd.concat([
    precos_de("IBOV", CAL_R, [10.0] * 6),
    precos_de("AZUL3", CAL_R, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0]),
    precos_de("GAPX3", CAL_R, [10.0, None, 25.0, 25.0, 25.0, 25.0]),
], ignore_index=True)


def test_retornos_suspeitos_na_data_de_evento_vira_nota_e_tabela_separada(mapa, monkeypatch):
    monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: PRECOS_R.copy())
    evento = pd.DataFrame({
        "ticker": ["AZUL3"], "data_com": pd.to_datetime(["2026-04-08"]),
        "tipo": ["GRUPAMENTO"], "fator": [0.1],
    })
    monkeypatch.setattr(fontes, "ler_eventos_acoes", lambda ler=None: evento)
    existentes = {fontes.nome_real("precos"), fontes.nome_real("eventos_acoes")}

    secao = secao_retornos_suspeitos(_ler_sem_banco, mapa, existentes)

    assert secao["notas"][0].startswith("3 retornos diários suspeitos em 2 tickers")
    assert secao["notas"][1] == (
        "1 retornos suspeitos na data de um evento de ações: evento não ajustado no preço (pedido à coleta)"
    )
    assert [t["subtitulo"] for t in secao["tabelas"]] == [
        "Retornos diários suspeitos", "Retornos suspeitos na data de um evento",
    ]
    assert secao["tabelas"][1]["linhas"] == [["AZUL3", date(2026, 4, 8), "GRUPAMENTO 0,1 (data_com 2026-04-08)"]]


def test_secao_precos_fora_do_pregao_conhecido_so_anota(mapa):
    """JBSS32 2020-11-20 é conhecida (fontes.yaml) e só vira nota; NATU3 tem uma desconhecida (2021-01-02)."""
    def ler(sql):
        if "NOT IN" in sql:
            return pd.DataFrame({
                "ticker": ["JBSS32", "JBSS32", "JBSS32", "NATU3", "NATU3", "NATU3", "NATU3"],
                "data": [date(2020, 11, 18), date(2020, 11, 20), date(2020, 11, 23),
                         date(2020, 11, 18), date(2020, 11, 20), date(2020, 11, 23), date(2021, 1, 2)],
            })
        if "= 'IBOV'" in sql:
            return pd.DataFrame({"data": [date(2020, 11, 18), date(2020, 11, 19), date(2020, 11, 23)]})
        if "IN ('IBOV'" in sql:
            return pd.DataFrame({"ticker": [], "linhas": [], "com_volume": [], "inicio": [], "fim": []})
        raise AssertionError(f"SQL inesperado: {sql}")

    secao = secao_precos(ler, mapa, {"v1-precos"})

    fora = [d["detalhe"] for d in secao["divergencias"] if d["tema"] == "preco_fora_do_pregao"]
    assert fora == ["NATU3"]
    assert "linha fora do calendário (conhecida, pedida à coleta): JBSS32 2020-11-20, NATU3 2020-11-20" in secao["notas"]
