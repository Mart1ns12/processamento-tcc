"""Fábrica de dados de teste para fundamentos e proventos (tests/test_fund_*.py).

Os nomes de colunas são os de `fontes.ler_tabela` (balancos, acoes_emitidas, proventos e
cadastro). Datas saem como Timestamp normalizado; ausência numérica sai como NaN.
Nenhuma função usa banco ou rede. Os valores são os da seção F0 do plano da etapa 4 e dos
ajustes A3 e A4 (empresa K e `mudancas`).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from fabrica_precos import precos_de
from processamento.exclusoes import Exclusoes

CNPJ = {
    "A": "00000000000101",
    "U": "00000000000202",
    "PREJ": "00000000000303",
    "BANC": "00000000000404",
    "SEMB": "03847461000192",
    "NOBA": "00000000000505",
    "D": "00000000000606",
    "BDRX": "00000000000707",
    "DUPN": "00000000000808",
    "EXTI": "00000000000909",
    "B": "00000000001010",
    "C": "00000000001111",
    "F": "00000000001212",
    "K": "00000000001313",
}

_COLUNAS_NUMERICAS_BALANCO = [
    "receita_liquida", "lucro_bruto", "lucro_liquido", "patrimonio_liquido", "ebit",
    "depreciacao_amortizacao", "emprestimos_curto_prazo", "emprestimos_longo_prazo",
    "caixa", "aplicacoes_financeiras",
]


def _numero(valor) -> float:
    """Número com None virando NaN."""
    return float("nan") if valor is None else float(valor)


def _bal(tipo: str, ini: str, fim: str, entrega: str, **valores) -> dict:
    """Uma linha de balanço (dict) com os campos de período e os valores dados."""
    return {"tipo_documento": tipo, "data_inicio_periodo": ini, "data_fim_periodo": fim,
            "data_entrega": entrega, **valores}


def _a(tipo, ini, fim, entrega, receita, lucro_bruto, lucro_liquido, pl) -> dict:
    """Linha de balanço só com receita, lucro bruto, lucro líquido e PL (demais colunas NaN)."""
    return _bal(tipo, ini, fim, entrega, receita_liquida=receita, lucro_bruto=lucro_bruto,
                lucro_liquido=lucro_liquido, patrimonio_liquido=pl)


def _d(tipo, ini, fim, entrega, receita, lucro_bruto, lucro_liquido, ebit, da, pl,
       emp_cp, emp_lp, caixa, aplic) -> dict:
    """Linha de balanço com todas as colunas (None vira NaN)."""
    return _bal(tipo, ini, fim, entrega, receita_liquida=receita, lucro_bruto=lucro_bruto,
                lucro_liquido=lucro_liquido, ebit=ebit, depreciacao_amortizacao=da,
                patrimonio_liquido=pl, emprestimos_curto_prazo=emp_cp,
                emprestimos_longo_prazo=emp_lp, caixa=caixa, aplicacoes_financeiras=aplic)


def _alterar(linhas: list[dict], numeros: list[int], **campos) -> list[dict]:
    """Cópia de `linhas` com `campos` trocados nas linhas `numeros` (1 a n, como na tabela)."""
    nova = list(linhas)
    for n in numeros:
        nova[n - 1] = {**nova[n - 1], **campos}
    return nova


# Tabela A (9 linhas): ITR e DFP de 2024 e 2025, com trimestre e acumulado.
LINHAS_A = [
    _a("ITR", "2024-07-01", "2024-09-30", "2024-11-10", 300, 120, 30, 1000),
    _a("ITR", "2024-01-01", "2024-09-30", "2024-11-10", 900, 360, 90, 1000),
    _a("DFP", "2024-01-01", "2024-12-31", "2025-03-20", 1300, 500, 130, 1100),
    _a("ITR", "2025-01-01", "2025-03-31", "2025-05-10", 350, 140, 35, 1150),
    _a("ITR", "2025-04-01", "2025-06-30", "2025-08-10", 360, 150, 40, 1200),
    _a("ITR", "2025-01-01", "2025-06-30", "2025-08-10", 710, 290, 75, 1200),
    _a("ITR", "2025-07-01", "2025-09-30", "2025-11-10", 380, 160, 45, 1250),
    _a("ITR", "2025-01-01", "2025-09-30", "2025-11-10", 1090, 450, 120, 1250),
    _a("DFP", "2025-01-01", "2025-12-31", "2026-03-15", 1500, 620, 160, 1300),
]

# Tabela D (6 linhas): com EBIT, D&A e dívida. Linhas 2 e 4 sem D&A (NaN).
LINHAS_D = [
    _d("ITR", "2025-01-01", "2025-03-31", "2025-05-10", 100, 40, 10, 20, 5, 500, 50, 150, 30, 20),
    _d("ITR", "2025-04-01", "2025-06-30", "2025-08-10", 100, 40, 10, 20, None, 510, 50, 150, 30, 20),
    _d("ITR", "2025-01-01", "2025-06-30", "2025-08-10", 200, 80, 20, 40, 11, 510, 50, 150, 30, 20),
    _d("ITR", "2025-07-01", "2025-09-30", "2025-11-10", 100, 40, 10, 20, None, 520, 60, 140, 40, 10),
    _d("ITR", "2025-01-01", "2025-09-30", "2025-11-10", 300, 120, 30, 60, 18, 520, 60, 140, 40, 10),
    _d("DFP", "2025-01-01", "2025-12-31", "2026-03-15", 420, 170, 45, 85, 26, 540, 70, 130, 80, 20),
]

# D2: caixa líquido (caixa maior que a dívida de curto e longo prazo).
LINHAS_D2 = _alterar(LINHAS_D, [6], caixa=200)

# B: reapresentação. Linhas 5 e 6 entregues só em 2025-12-01.
LINHAS_B = _alterar(LINHAS_A, [5, 6], data_entrega="2025-12-01")

# C: 9 meses reentregue depois da DFP. Linhas 7 e 8 entregues em 2026-04-01.
LINHAS_C = _alterar(LINHAS_A, [7, 8], data_entrega="2026-04-01")

# PREJ: prejuízo em todas as linhas (lucro líquido da tabela trocado).
LINHAS_PREJ = [
    {**linha, "lucro_liquido": valor}
    for linha, valor in zip(LINHAS_A, [-10, -30, -50, -20, -30, -50, -10, -60, -80])
]

# BANC: sem lucro bruto (banco não o informa).
LINHAS_BANC = _alterar(LINHAS_A, list(range(1, 10)), lucro_bruto=None)

# F: exercício de abril a março (fora do ano-calendário).
LINHAS_F = [
    _bal("ITR", "2025-04-01", "2025-06-30", "2025-08-10", receita_liquida=100),
    _bal("ITR", "2025-07-01", "2025-09-30", "2025-11-10", receita_liquida=110),
    _bal("ITR", "2025-04-01", "2025-09-30", "2025-11-10", receita_liquida=210),
    _bal("ITR", "2025-10-01", "2025-12-31", "2026-02-10", receita_liquida=120),
    _bal("ITR", "2025-04-01", "2025-12-31", "2026-02-10", receita_liquida=330),
    _bal("DFP", "2025-04-01", "2026-03-31", "2026-06-20", receita_liquida=460),
]

# Data de referência da fábrica (corte da maioria dos testes).
T = date(2026, 3, 31)
CAL = [d.date() for d in pd.bdate_range("2025-01-02", "2026-04-30")]
EXCL = Exclusoes(cnpjs_sem_balanco={CNPJ["SEMB"]: "sem balanço nas fontes"})

# Cadastro do mundo: (ticker, cnpj, setor, subsetor, tipo, unit_on, unit_pn, fechamento).
_MUNDO_CADASTRO = [
    ("AAAA3", "A", "S1", "X", "ON", None, None, 10),
    ("AAAA4", "A", "S1", "X", "PN", None, None, 8),
    ("UUUU11", "U", "S1", "X", "UNIT", 1, 2, 30),
    ("PREJ3", "PREJ", "S1", "X", "ON", None, None, 4),
    ("BANC4", "BANC", "Financeiro", "Intermediários Financeiros", "PN", None, None, 20),
    ("SEMB3", "SEMB", "S3", "X", "ON", None, None, 5),
    ("NOBA3", "NOBA", "S3", "X", "ON", None, None, 7),
    ("DDDD3", "D", "S4", "X", "ON", None, None, 9),
    ("BDRX32", "BDRX", "S4", "X", "BDR", None, None, 50),
    ("DUPN5", "DUPN", "S5", "X", "PN", None, None, 6),
    ("EXTI3", "EXTI", "S5", "X", "ON", None, None, 12),
    ("KKKK3", "K", "S6", "X", "ON", None, None, 10),
]

# Ações emitidas do mundo: (empresa, data_referencia, qtd_on, qtd_pn).
_MUNDO_ACOES = [
    ("A", "2025-03-31", 50, 50), ("A", "2025-12-31", 60, 40),
    ("U", "2025-03-31", 100, 200), ("U", "2025-12-31", 100, 200),
    ("PREJ", "2025-12-31", 100, 0),
    ("BANC", "2025-12-31", 50, 50),
    ("SEMB", "2025-12-31", 100, 0),
    ("NOBA", "2025-12-31", 100, 0),
    ("D", "2025-12-31", 100, 0),
    ("BDRX", "2025-12-31", 100, 0),
    ("DUPN", "2025-03-31", 100, 300), ("DUPN", "2025-12-31", 100, 300),
    ("EXTI", "2025-03-31", 100, 50), ("EXTI", "2025-12-31", 150, 0),
    ("K", "2025-03-31", 100, 200), ("K", "2025-12-31", 300, 0),
]

# Proventos do mundo: (ticker, tipo, data_com, valor_por_acao, data_pagamento).
_MUNDO_PROVENTOS = [
    ("AAAA3", "DIVIDENDO", "2024-05-10", 0.40, None),
    ("AAAA4", "DIVIDENDO", "2024-05-10", 0.44, None),
    ("AAAA3", "DIVIDENDO", "2025-03-31", 0.99, None),
    ("AAAA3", "DIVIDENDO", "2025-04-15", 0.30, "2025-05-02"),
    ("AAAA4", "DIVIDENDO", "2025-04-15", 0.33, None),
    ("AAAA3", "JCP", "2025-10-15", 0.20, None),
    ("AAAA4", "JCP", "2025-10-15", 0.22, None),
    ("AAAA3", "DIVIDENDO", "2026-04-10", 0.50, None),
    ("UUUU11", "DIVIDENDO", "2025-03-30", 5.00, None),
    ("UUUU11", "DIVIDENDO", "2025-06-10", 1.50, None),
    ("UUUU3", "DIVIDENDO", "2025-06-10", 0.50, None),
    ("UUUU4", "DIVIDENDO", "2025-06-10", 0.50, None),
    ("UUUU11", "JCP", "2026-01-15", 0.90, None),
    ("UUUU3", "JCP", "2026-01-15", 0.30, None),
    ("UUUU4", "JCP", "2026-01-15", 0.30, None),
    ("PREJ3", "DIVIDENDO", "2025-06-01", 0.10, None),
    ("SEMB3", "DIVIDENDO", "2025-09-01", 0.25, None),
    ("DUPN3", "DIVIDENDO", "2025-08-15", 0.20, None),
    ("DUPN5", "DIVIDENDO", "2025-08-15", 0.30, None),
    ("DUPN6", "DIVIDENDO", "2025-08-15", 0.10, None),
    ("DUPN3", "JCP", "2026-02-10", 0.10, None),
    ("DUPN5", "JCP", "2026-02-10", 0.12, None),
    ("EXTI3", "DIVIDENDO", "2025-05-20", 0.40, None),
    ("EXTI6", "DIVIDENDO", "2025-05-20", 0.44, None),
    ("EXTI3", "DIVIDENDO", "2026-01-20", 0.50, None),
    ("BDRX32", "DIVIDENDO", "2025-07-01", 0.80, None),
    ("KKKK6", "JCP", "2025-04-10", 0.04, None),
    ("KKKK6", "DIVIDENDO", "2025-05-20", 0.10, None),
    ("KKKK3", "DIVIDENDO", "2025-05-20", 0.08, None),
    ("KKKK3", "JCP", "2026-01-20", 0.05, None),
]

# Balanços do mundo: (empresa, linhas). Empresa sem linha (SEMB, NOBA) não tem balanço.
_MUNDO_BALANCOS = [
    ("A", LINHAS_A),
    ("U", LINHAS_A),
    ("PREJ", LINHAS_PREJ),
    ("BANC", LINHAS_BANC),
    ("D", LINHAS_D),
    ("BDRX", LINHAS_D),
    ("DUPN", LINHAS_A),
    ("EXTI", LINHAS_A),
    ("K", LINHAS_A),
]

# Troca de ticker no mundo: KKKK6 (PN) virou KKKK3 (ON).
MUDANCAS = {"KKKK6": "KKKK3"}


def balanco_de(cnpj: str, linhas: list[dict]) -> pd.DataFrame:
    """Linhas de `v1-balancos` de uma empresa (ver `_bal`). Coluna numérica ausente vira NaN."""
    registros = []
    for linha in linhas:
        registros.append({
            "cnpj": cnpj,
            "tipo_documento": linha["tipo_documento"],
            "data_inicio_periodo": pd.Timestamp(linha["data_inicio_periodo"]),
            "data_fim_periodo": pd.Timestamp(linha["data_fim_periodo"]),
            "data_entrega": pd.Timestamp(linha["data_entrega"]),
            **{c: _numero(linha.get(c)) for c in _COLUNAS_NUMERICAS_BALANCO},
        })
    colunas = ["cnpj", "tipo_documento", "data_inicio_periodo", "data_fim_periodo", "data_entrega",
               *_COLUNAS_NUMERICAS_BALANCO]
    return pd.DataFrame(registros, columns=colunas)


def acoes_de(linhas: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    """Linhas de `v1-acoes_emitidas`: (cnpj, 'AAAA-MM-DD', qtd_on, qtd_pn)."""
    return pd.DataFrame({
        "cnpj": [cnpj for cnpj, _, _, _ in linhas],
        "data_referencia": pd.to_datetime([data for _, data, _, _ in linhas]).to_numpy(),
        "qtd_on": [_numero(on) for _, _, on, _ in linhas],
        "qtd_pn": [_numero(pn) for _, _, _, pn in linhas],
    })


def proventos_de(linhas: list[tuple[str, str, str, float, str | None]]) -> pd.DataFrame:
    """Linhas de `v1-proventos`: (ticker, tipo, 'AAAA-MM-DD' data_com, valor_por_acao, data_pagamento|None)."""
    return pd.DataFrame({
        "ticker": [ticker for ticker, *_ in linhas],
        "tipo": [tipo for _, tipo, *_ in linhas],
        "data_com": pd.to_datetime([data_com for _, _, data_com, _, _ in linhas]).to_numpy(),
        "valor_por_acao": [_numero(valor) for _, _, _, valor, _ in linhas],
        "data_pagamento": pd.to_datetime([pagamento for *_, pagamento in linhas]).to_numpy(),
    })


def cadastro_fund_de(linhas: list[tuple]) -> pd.DataFrame:
    """Linhas de `v1-cadastro` para fundamentos.

    Cada linha: (ticker, cnpj, setor, subsetor, tipo_acao, unit_qtd_on, unit_qtd_pn).
    empresa = ticker. Unit_qtd_on e unit_qtd_pn ausentes (None) viram NaN.
    """
    return pd.DataFrame({
        "ticker": [ticker for ticker, *_ in linhas],
        "cnpj": [cnpj for _, cnpj, *_ in linhas],
        "empresa": [ticker for ticker, *_ in linhas],
        "setor": [setor for _, _, setor, *_ in linhas],
        "subsetor": [subsetor for _, _, _, subsetor, *_ in linhas],
        "tipo_acao": [tipo for _, _, _, _, tipo, *_ in linhas],
        "unit_qtd_on": [_numero(on) for _, _, _, _, _, on, _ in linhas],
        "unit_qtd_pn": [_numero(pn) for _, _, _, _, _, _, pn in linhas],
    })


def mundo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                     list[date], dict[str, str]]:
    """Dados completos de 12 tickers para os testes de fundamentos e proventos.

    Devolve (cadastro, balancos, acoes, proventos, precos, cal, mudancas), nessa ordem.
    `cal` são os dias de CAL; `mudancas` é o mapa de troca de ticker (KKKK6 -> KKKK3).
    `EXCL` e `T` são constantes do módulo (não vêm na tupla).
    """
    cadastro = cadastro_fund_de([
        (ticker, CNPJ[emp], setor, subsetor, tipo, on, pn)
        for ticker, emp, setor, subsetor, tipo, on, pn, _ in _MUNDO_CADASTRO
    ])
    balancos = pd.concat(
        [balanco_de(CNPJ[emp], linhas) for emp, linhas in _MUNDO_BALANCOS], ignore_index=True
    )
    acoes = acoes_de([(CNPJ[emp], data, on, pn) for emp, data, on, pn in _MUNDO_ACOES])
    proventos = proventos_de(_MUNDO_PROVENTOS)
    precos = pd.concat(
        [precos_de(ticker, CAL, [fech] * len(CAL)) for ticker, *_, fech in _MUNDO_CADASTRO],
        ignore_index=True,
    )
    return cadastro, balancos, acoes, proventos, precos, CAL, dict(MUDANCAS)
