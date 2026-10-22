"""Testes de tabela_classes (processamento/tickers.py): ligação de classes pela raiz.

Os valores esperados vêm do gabarito do plano (seção 6 da especificação). Sem banco nem rede.
"""

from processamento.tickers import tabela_classes

CADASTRO = {
    "PETR3": "33000167000101",
    "PETR4": "33000167000101",
    "TAEE11": "07859971000130",
    "ITUB4": "60872504000123",
    "AXIA3": "00001180000126",
    "BPAC11": "30306294000145",
    "CRFB3": None,
}
TIPOS_CADASTRO = {
    "PETR3": "ON",
    "PETR4": "PN",
    "TAEE11": "UNIT",
    "ITUB4": "PN",
    "AXIA3": "ON",
    "BPAC11": "UNIT",
    "CRFB3": "ON",
}
MUDANCAS = {"ELET3": "AXIA3", "ELET6": "AXIA6"}
CODIGOS = {
    "33000167000101": {"PETR3", "PETR4"},
    "07859971000130": {"TAEE3", "TAEE4", "TAEE11"},
    "60872504000123": {"ITUB3", "ITUB4"},
    "00001180000126": {"AXIA3"},
    "30306294000145": {"BPAC3", "BPAC5", "BPAC11"},
}
TICKERS = [
    "AXIA6",
    "BPAC5",
    "CPLE5",
    "CRFB3",
    "ELET6",
    "ITUB3",
    "PETR3",
    "PETR4",
    "TAEE11",
    "TAEE3",
    "TAEE4",
]
COLUNAS = ["ticker", "ticker_atual", "cnpj", "tipo", "situacao", "ligacao"]
ESPERADO = [
    ("AXIA6", "AXIA6", "00001180000126", "PN", "extinta", "raiz"),
    ("BPAC5", "BPAC5", "30306294000145", "PN", "existe", "raiz"),
    ("CPLE5", "CPLE5", None, "PN", "sem_empresa", "sem_empresa"),
    ("CRFB3", "CRFB3", None, "ON", "sem_empresa", "sem_empresa"),
    ("ELET6", "AXIA6", "00001180000126", "PN", "extinta", "raiz"),
    ("ITUB3", "ITUB3", "60872504000123", "ON", "existe", "raiz"),
    ("PETR3", "PETR3", "33000167000101", "ON", "existe", "cadastro"),
    ("PETR4", "PETR4", "33000167000101", "PN", "existe", "cadastro"),
    ("TAEE11", "TAEE11", "07859971000130", "UNIT", "existe", "cadastro"),
    ("TAEE3", "TAEE3", "07859971000130", "ON", "existe", "raiz"),
    ("TAEE4", "TAEE4", "07859971000130", "PN", "existe", "raiz"),
]


def _tabela(tickers=TICKERS):
    return tabela_classes(tickers, CADASTRO, TIPOS_CADASTRO, MUDANCAS, CODIGOS)


def test_colunas_e_indice_reiniciado():
    df = _tabela()
    assert list(df.columns) == COLUNAS
    assert list(df.index) == list(range(len(TICKERS)))


def test_ordenada_por_ticker():
    assert list(_tabela()["ticker"]) == sorted(TICKERS)


def test_valores_esperados_por_codigo():
    obtido = [tuple(linha) for linha in _tabela().itertuples(index=False)]
    assert obtido == ESPERADO


def test_ausencia_e_none_nao_zero_nem_texto_vazio():
    df = _tabela()
    cple5 = df[df["ticker"] == "CPLE5"].iloc[0]
    assert cple5["cnpj"] is None
    assert cple5["ligacao"] == "sem_empresa"


def test_mesmo_cnpj_para_codigos_da_mesma_empresa():
    cnpj = _tabela().set_index("ticker")["cnpj"]
    assert cnpj["PETR3"] == cnpj["PETR4"] == "33000167000101"
    assert cnpj["TAEE3"] == cnpj["TAEE4"] == cnpj["TAEE11"] == "07859971000130"


def test_lista_vazia_devolve_tabela_vazia_com_colunas():
    df = _tabela(tickers=[])
    assert len(df) == 0
    assert list(df.columns) == COLUNAS
