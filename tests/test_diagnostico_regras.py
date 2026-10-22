"""Testes das regras puras do diagnóstico (gabarito do plano, Fase 2)."""

from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from processamento.diagnostico import regras as r
from processamento.diagnostico.esperado import HORAS_DAILY_UTC, TOLERANCIA_PROB


# ---------------------------------------------------------------------------
# Constantes do esperado.py
# ---------------------------------------------------------------------------

def test_horas_daily_utc_tem_as_duas_agendas():
    assert HORAS_DAILY_UTC == (11, 21)


def test_tolerancia_prob_padrao():
    assert TOLERANCIA_PROB == 1e-3


# ---------------------------------------------------------------------------
# Helpers de estrutura
# ---------------------------------------------------------------------------

def test_nova_secao_e_adicionar_tabela_e_div():
    secao = r.nova_secao("Precos")
    assert secao == {"titulo": "Precos", "notas": [], "tabelas": [], "divergencias": []}
    r.adicionar_tabela(secao, "sub", ["a", "b"], [(1, 2)])
    assert secao["tabelas"] == [{"subtitulo": "sub", "colunas": ["a", "b"], "linhas": [(1, 2)]}]
    assert r.div("t", "tab", "det") == {"tema": "t", "tabela": "tab", "detalhe": "det"}


def test_inteiro():
    assert r.inteiro(None) == 0
    assert r.inteiro(float("nan")) == 0
    assert r.inteiro(Decimal("7")) == 7
    assert r.inteiro(3.0) == 3


def test_texto():
    assert r.texto(b"abc") == "abc"
    assert r.texto(None) is None
    assert r.texto("x") == "x"


# ---------------------------------------------------------------------------
# 1. classificar_formato_iso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    ("2026-06-18T19:42:00-03:00", "iso_com_fuso"),
    ("2026-06-18T19:42:00.123456-03:00", "iso_com_fuso"),
    ("2026-06-18T19:42-03:00", "iso_com_fuso"),
    ("2026-06-18T22:42:00Z", "iso_utc_z"),
    ("2026-06-18T19:42:00", "iso_sem_fuso"),
    ("2026-06-18 19:42:00", "iso_sem_fuso"),
    ("2026-06-18", "so_data"),
    ("18/06/2026 19:42", "invalido"),
    ("2026-13-18T19:42:00-03:00", "invalido"),
    (None, "nulo"),
    ("", "texto_vazio"),
])
def test_classificar_formato_iso(entrada, esperado):
    assert r.classificar_formato_iso(entrada) == esperado


def test_classificar_formato_iso_nan_e_nulo():
    assert r.classificar_formato_iso(float("nan")) == "nulo"


# ---------------------------------------------------------------------------
# 2. offset_iso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    ("2026-06-18T19:42:00-03:00", "-03:00"),
    ("2026-01-10T10:00:00-02:00", "-02:00"),
    ("2026-06-18T19:42:00", None),
    ("2026-06-18T22:42:00Z", None),
])
def test_offset_iso(entrada, esperado):
    assert r.offset_iso(entrada) == esperado


# ---------------------------------------------------------------------------
# 3. classificar_grupo_iso
# ---------------------------------------------------------------------------

def test_classificar_grupo_iso_iguais():
    assert r.classificar_grupo_iso("2025-01-02T10:00:00-03:00", "2026-10-21T23:59:59-03:00") == "iso_com_fuso"


def test_classificar_grupo_iso_misto():
    assert r.classificar_grupo_iso("2025-01-02T10:00:00-03:00", "2025-01-02 10:00:00X") == "misto"


# ---------------------------------------------------------------------------
# 4. confere_fuso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("iso, utc, esperado", [
    ("2026-06-18T19:42:00-03:00", datetime(2026, 6, 18, 22, 42, 0), True),
    ("2026-06-18T19:42:00-03:00", datetime(2026, 6, 18, 19, 42, 0), False),
    ("2026-06-18T19:42:00-03:00", datetime(2026, 6, 18, 22, 42, 0, 400000), True),
    ("2026-01-01T00:30:00-03:00", datetime(2026, 1, 1, 3, 30), True),
    (None, datetime(2026, 1, 1), False),
])
def test_confere_fuso(iso, utc, esperado):
    assert r.confere_fuso(iso, utc) is esperado


def test_confere_fuso_aceita_pd_timestamp():
    assert r.confere_fuso("2026-06-18T19:42:00-03:00", pd.Timestamp("2026-06-18 22:42:00")) is True


# ---------------------------------------------------------------------------
# 5. veredito_probabilidades e resumo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_nulos, soma, fora, esperado", [
    (0, 1.0, 0, "ok"),
    (0, 1.0005, 0, "ok"),
    (0, 0.9999, 0, "ok"),
    (0, 1.1, 0, "soma_errada"),
    (0, 0.998, 0, "soma_errada"),
    (3, None, None, "sem_prob"),
    (3, float("nan"), float("nan"), "sem_prob"),
    (1, None, None, "parcial"),
    (0, 1.0, 1, "fora_intervalo"),
])
def test_veredito_probabilidades(n_nulos, soma, fora, esperado):
    assert r.veredito_probabilidades(n_nulos, soma, fora, tol=TOLERANCIA_PROB) == esperado


def test_resumir_probabilidades_com_tuplas():
    linhas = [(0, 1.0, 0, 10), (3, None, None, 3), (0, 1.1, 0, 1), (0, 1.0, 1, 2)]
    assert r.resumir_probabilidades(linhas) == {
        "ok": 10, "sem_prob": 3, "parcial": 0, "fora_intervalo": 2, "soma_errada": 1,
    }


def test_resumir_probabilidades_com_dataframe():
    df = pd.DataFrame(
        [(0, 1.0, 0, 10), (3, None, None, 3), (0, 1.1, 0, 1), (0, 1.0, 1, 2)],
        columns=["n_nulos", "soma", "fora", "n"],
    )
    assert r.resumir_probabilidades(df) == {
        "ok": 10, "sem_prob": 3, "parcial": 0, "fora_intervalo": 2, "soma_errada": 1,
    }


# ---------------------------------------------------------------------------
# 6. pct_com_hora_por_ano
# ---------------------------------------------------------------------------

def test_pct_com_hora_por_ano():
    assert r.pct_com_hora_por_ano([(2025, 4, 3), (2026, 3, 1)]) == {2025: 75.0, 2026: 33.3}


def test_pct_com_hora_por_ano_soma_duas_origens():
    assert r.pct_com_hora_por_ano([(2025, 2, 1), (2025, 2, 2)]) == {2025: 75.0}


# ---------------------------------------------------------------------------
# 7. comparar_colunas
# ---------------------------------------------------------------------------

def test_comparar_colunas():
    assert r.comparar_colunas(
        ["id", "ticker", "titulo"],
        ["id", "titulo", "momento_pregao", "atualizado_em"],
        ignoradas=["momento_pregao"],
    ) == {"faltando": ["ticker"], "extras": ["atualizado_em"]}


# ---------------------------------------------------------------------------
# 8. comparar_chave
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("esperada, real, resultado", [
    (["a", "b"], ["a", "b"], "igual"),
    (["a", "b"], ["b", "a"], "ordem_diferente"),
    (["a", "b"], ["a"], "diferente"),
    (["a"], [], "sem_chave"),
])
def test_comparar_chave(esperada, real, resultado):
    assert r.comparar_chave(esperada, real) == resultado


# ---------------------------------------------------------------------------
# 9. classificar_dias_periodo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dias, esperado", [
    (88, "3m"), (93, "3m"), (90, "3m"), (92, "3m"),
    (180, "6m"), (184, "6m"), (181, "6m"),
    (271, "9m"), (276, "9m"), (273, "9m"),
    (364, "12m"), (367, "12m"), (365, "12m"), (366, "12m"),
    (46, "outro"), (120, "outro"),
])
def test_classificar_dias_periodo(dias, esperado):
    assert r.classificar_dias_periodo(dias) == esperado


# ---------------------------------------------------------------------------
# 10. veredito_escala
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ordens, esperado", [
    ({9: 50, 10: 30, 8: 20}, "reais"),
    ({5: 40, 6: 50, 7: 10}, "provavel_milhares"),
    ({7: 10}, "inconclusivo"),
    ({}, "sem_dados"),
])
def test_veredito_escala(ordens, esperado):
    assert r.veredito_escala(ordens) == esperado


# ---------------------------------------------------------------------------
# 11. dias_uteis_sem_pregao
# ---------------------------------------------------------------------------

def test_dias_uteis_sem_pregao():
    datas = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 12)]
    assert r.dias_uteis_sem_pregao(datas) == [date(2026, 1, 7)]


# ---------------------------------------------------------------------------
# 12. buracos_por_ticker
# ---------------------------------------------------------------------------

def test_buracos_por_ticker():
    calendario = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 12)]
    por_ticker = {
        "AAAA3": [date(2026, 1, 5), date(2026, 1, 8), date(2026, 1, 12)],
        "BBBB4": [date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)],
    }
    assert r.buracos_por_ticker(calendario, por_ticker) == {
        "AAAA3": {"faltando": [date(2026, 1, 6), date(2026, 1, 9)], "fora_do_pregao": []},
        "BBBB4": {"faltando": [], "fora_do_pregao": [date(2026, 1, 7)]},
    }


# ---------------------------------------------------------------------------
# 13. contar_por_ano
# ---------------------------------------------------------------------------

def test_contar_por_ano():
    datas = [date(2025, 12, 30), date(2026, 1, 2), date(2026, 1, 5)]
    assert r.contar_por_ano(datas) == {2025: 1, 2026: 2}


# ---------------------------------------------------------------------------
# 14 e 15. padrões de ticker e CNPJ
# ---------------------------------------------------------------------------

def test_tickers_fora_do_padrao():
    tickers = ["PETR4", "KLBN11", "JBSS32", "petr4", "PETR4.SA", "IBOV", "VALE3", "B3SA3", None]
    assert r.tickers_fora_do_padrao(tickers) == ["IBOV", "PETR4.SA", "petr4"]


def test_cnpjs_fora_do_padrao():
    cnpjs = ["33000167000101", "33.000.167/0001-01", "3300016700010", None]
    assert r.cnpjs_fora_do_padrao(cnpjs) == ["33.000.167/0001-01", "3300016700010"]


# ---------------------------------------------------------------------------
# 16. comparar_com_referencia
# ---------------------------------------------------------------------------

def test_comparar_com_referencia():
    assert r.comparar_com_referencia(
        {"PETR4", "VALE3", "KLBN11"},
        {"PETR4", "VALE3", "IBOV", "XXXX3"},
        ignorar={"IBOV"},
    ) == {"so_na_referencia": ["KLBN11"], "so_no_outro": ["XXXX3"]}


# ---------------------------------------------------------------------------
# 17. valores_fora_da_lista
# ---------------------------------------------------------------------------

def test_valores_fora_da_lista():
    valores = ["google_news", "cvm_ipe", None, "rss_nativo"]
    assert r.valores_fora_da_lista(valores, ["google_news", "cvm_ipe"]) == ["rss_nativo"]


# ---------------------------------------------------------------------------
# 18. resumo_vazios
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("total, nulos, esperado", [
    (10, 10, {"pct_nulo": 100.0, "situacao": "vazia"}),
    (10, 0, {"pct_nulo": 0.0, "situacao": "cheia"}),
    (8, 2, {"pct_nulo": 25.0, "situacao": "parcial"}),
    (0, 0, {"pct_nulo": None, "situacao": "tabela_vazia"}),
])
def test_resumo_vazios(total, nulos, esperado):
    assert r.resumo_vazios(total, nulos) == esperado


# ---------------------------------------------------------------------------
# 19. divergencias_coluna
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("args, esperado", [
    (("v1-balancos", "ebit", "vazia", 0, 0, True, False), []),
    (("v1-balancos", "ebit", "parcial", 0, 0, True, False),
     ["`v1-balancos.ebit`: esperada vazia (seção 3.1), mas tem dados (parcial)"]),
    (("v1-balancos", "receita_liquida", "vazia", 0, 0, False, False),
     ["`v1-balancos.receita_liquida`: 100% vazia"]),
    (("v1-noticias", "fonte", "parcial", 5, 0, False, False),
     ["`v1-noticias.fonte`: 5 textos vazios ('') em vez de NULL"]),
    (("v1-precos", "volume", "parcial", 0, 3, False, True),
     ["`v1-precos.volume`: 3 zeros (ausência deve ser NULL)"]),
])
def test_divergencias_coluna(args, esperado):
    assert r.divergencias_coluna(*args) == esperado


# ---------------------------------------------------------------------------
# 20. classificar_id_noticia
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("v, esperado", [
    ("n000123", True),
    ("n1234567", True),
    ("n12345", False),
    ("x000123", False),
    ("N000123", False),
])
def test_classificar_id_noticia(v, esperado):
    assert r.classificar_id_noticia(v) is esperado


# ---------------------------------------------------------------------------
# 21. horas_fora_da_agenda
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("contagem, esperado", [
    ({11: 30, 21: 5}, {}),
    ({11: 30}, {}),
    ({21: 12}, {}),
    ({11: 30, 14: 2}, {14: 2}),
    ({8: 30, 18: 4}, {8: 30, 18: 4}),
    ({}, {}),
])
def test_horas_fora_da_agenda(contagem, esperado):
    assert r.horas_fora_da_agenda(contagem) == esperado


# ---------------------------------------------------------------------------
# Pureza: regras.py não tem SQL nem acesso ao banco
# ---------------------------------------------------------------------------

def test_regras_nao_importam_banco():
    import processamento.diagnostico.regras as modulo
    with open(modulo.__file__, encoding="utf-8") as arquivo:
        fonte = arquivo.read()
    assert "sqlalchemy" not in fonte.lower()
    assert "pymysql" not in fonte.lower()


def test_divergencias_coluna_tabela_vazia_nao_gera_divergencia():
    from processamento.diagnostico.regras import divergencias_coluna

    assert divergencias_coluna("v1-balancos", "ebit", "tabela_vazia", 0, 0, True, False) == []


def test_resumo_proventos_por_ticker():
    from datetime import date

    from processamento.diagnostico.regras import resumo_proventos_por_ticker

    linhas = [("AXIA6", date(2025, 4, 30)), ("AXIA6", date(2025, 12, 19)), ("AXIA6", date(2024, 4, 30)),
              ("VALE5", date(2016, 3, 1)), ("PETR4", date(2025, 5, 2)), ("AXIA6", None)]
    assert resumo_proventos_por_ticker(linhas, ["VALE5", "AXIA6", "BBAS4"],
                                       date(2025, 1, 2), date(2026, 10, 21)) == [
        ["AXIA6", 3, date(2024, 4, 30), date(2025, 12, 19), 2],
        ["BBAS4", 0, None, None, 0],
        ["VALE5", 1, date(2016, 3, 1), date(2016, 3, 1), 0],
    ]
    assert resumo_proventos_por_ticker(linhas, ["VALE5"], None, None) == [
        ["VALE5", 1, date(2016, 3, 1), date(2016, 3, 1), None]]
