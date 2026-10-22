"""Testes de processamento/tickers.py: raiz, classe, tipo, mudanças, other_codes e ligação.

Os valores esperados vêm do gabarito do plano (seção 6 da especificação). Sem banco nem rede.
"""

import pytest

from processamento.tickers import (
    aplicar_mudancas,
    classe,
    classificar_classe,
    codigos_por_cnpj,
    ligar_a_cnpj,
    parse_other_codes,
    raiz,
    tipo_por_classe,
)

CADASTRO = {
    "PETR4": "33000167000101",
    "PETR3": "33000167000101",
    "ITUB4": "60872504000123",
    "AXIA3": "00001180000126",
    "USIM5": "60894730000105",
    "VALE3": "33592510000154",
    "CRFB3": None,
}
MUDANCAS = {"ELET3": "AXIA3", "ELET6": "AXIA6"}
CODIGOS = {
    "33000167000101": {"PETR3", "PETR4"},
    "60872504000123": {"ITUB3", "ITUB4"},
    "00001180000126": {"AXIA3", "AXIA5", "AXIA6"},
    "60894730000105": {"USIM3", "USIM5", "USIM6"},
    "33592510000154": {"VALE3"},
}


def test_raiz_pega_quatro_primeiras_letras():
    assert raiz("ITUB3") == "ITUB"
    assert raiz("B3SA3") == "B3SA"


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [("ITUB3", 3), ("KLBN11", 11), ("B3SA3", 3), ("IBOV", None), ("PETR4", 4)],
)
def test_classe(codigo, esperado):
    assert classe(codigo) == esperado


@pytest.mark.parametrize(
    ("c", "esperado"),
    [(3, "ON"), (4, "PN"), (5, "PN"), (6, "PN"), (11, "UNIT"), (32, "BDR"), (35, "BDR"), (7, None), (None, None)],
)
def test_tipo_por_classe(c, esperado):
    assert tipo_por_classe(c) == esperado


def test_aplicar_mudancas_segue_cadeia():
    assert aplicar_mudancas("A1", {"A1": "B1", "B1": "C1"}) == "C1"


def test_aplicar_mudancas_para_no_ciclo():
    assert aplicar_mudancas("A1", {"A1": "B1", "B1": "A1"}) == "B1"


def test_aplicar_mudancas_sem_entrada_devolve_o_proprio():
    assert aplicar_mudancas("X3", {}) == "X3"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ('["PETR4", "PETR3"]', ["PETR4", "PETR3"]),
        (None, []),
        ("[]", []),
        (["X3"], ["X3"]),
        (b'["A3"]', ["A3"]),
        ('["A3", null, ""]', ["A3"]),
        (' [" B3 ", 5] ', ["B3"]),
    ],
)
def test_parse_other_codes(valor, esperado):
    assert parse_other_codes(valor) == esperado


@pytest.mark.parametrize("valor", ['{"a": 1}', "xx"])
def test_parse_other_codes_recusa_formato_invalido(valor):
    with pytest.raises(ValueError, match="other_codes inválido"):
        parse_other_codes(valor)


def test_codigos_por_cnpj_une_e_ignora_sem_cnpj():
    linhas = [
        ("11111111000111", '["A3"]'),
        ("11111111000111", '["A4"]'),
        (None, '["B3"]'),
        ("22222222000122", None),
    ]
    assert codigos_por_cnpj(linhas) == {
        "11111111000111": {"A3", "A4"},
        "22222222000122": set(),
    }


def test_ligar_a_cnpj_pelo_cadastro():
    assert ligar_a_cnpj("PETR4", CADASTRO, MUDANCAS) == ("33000167000101", "cadastro")


def test_ligar_a_cnpj_pela_raiz():
    assert ligar_a_cnpj("ITUB3", CADASTRO, MUDANCAS) == ("60872504000123", "raiz")


def test_ligar_a_cnpj_aplica_mudanca_antes_da_raiz():
    assert ligar_a_cnpj("ELET6", CADASTRO, MUDANCAS) == ("00001180000126", "raiz")


def test_ligar_a_cnpj_sem_empresa():
    assert ligar_a_cnpj("ZZZZ3", CADASTRO, MUDANCAS) == (None, "sem_empresa")


def test_ligar_a_cnpj_no_cadastro_sem_cnpj_e_sem_irma_com_cnpj():
    assert ligar_a_cnpj("CRFB3", CADASTRO, MUDANCAS) == (None, "sem_empresa")


def test_ligar_a_cnpj_ambiguo_quando_raiz_tem_duas_empresas():
    cadastro = {"ABCD3": "11111111000111", "ABCD4": "22222222000122"}
    assert ligar_a_cnpj("ABCD11", cadastro, {}) == (None, "ambiguo")


def test_ligar_a_cnpj_raiz_com_mesma_empresa_nao_e_ambiguo():
    # PETR3 e PETR4 são da mesma empresa: a raiz PETR tem um único CNPJ.
    assert ligar_a_cnpj("PETR5", CADASTRO, MUDANCAS) == ("33000167000101", "raiz")


@pytest.mark.parametrize(
    ("ticker", "situacao", "ticker_atual"),
    [
        ("ITUB3", "existe", "ITUB3"),
        ("USIM6", "existe", "USIM6"),
        ("VALE5", "extinta", "VALE5"),
        ("ELET6", "existe", "AXIA6"),
        ("ZZZZ3", "sem_empresa", "ZZZZ3"),
    ],
)
def test_classificar_classe(ticker, situacao, ticker_atual):
    resultado = classificar_classe(ticker, CADASTRO, MUDANCAS, CODIGOS)
    assert resultado["situacao"] == situacao
    assert resultado["ticker_atual"] == ticker_atual


def test_classificar_classe_sem_other_codes_da_empresa():
    codigos_sem_itub = {k: v for k, v in CODIGOS.items() if k != "60872504000123"}
    resultado = classificar_classe("ITUB3", CADASTRO, MUDANCAS, codigos_sem_itub)
    assert resultado["situacao"] == "sem_other_codes"
    assert resultado["cnpj"] == "60872504000123"
