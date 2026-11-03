"""Fábrica de dados de teste para o emissor por período (tests/test_emissores.py e testes de fundamentos).

Os nomes de colunas são os de `fontes.ler_emissores` (v1-emissores_ticker) e de
`fontes.ler_tabela("acoes_emitidas")` com a base atual. Datas saem como datetime64 (vazio = NaT) e
números como float (ausência = NaN). `cadastro_fund_de` vem de `fabrica_fundamentos`.
Nenhuma função usa banco ou rede. Valores da tabela da seção 6 do plano (T1, 03/11/2026).
"""

from __future__ import annotations

import pandas as pd

CNPJ_HAPV3 = "05197443000138"
CNPJ_MGLU3 = "47960950000121"
CNPJ_JBS_SA = "02916265000160"
CNPJ_JBS_NV = "49115815000105"


def _numero(valor) -> float:
    """Número com None virando NaN."""
    return float("nan") if valor is None else float(valor)


def emissores_de(linhas: list[tuple]) -> pd.DataFrame:
    """Linhas de `v1-emissores_ticker`: (ticker, ordem, ticker_negociado, cnpj, empresa, ini|None, fim|None, fator).

    `cd_cvm` fica None. `ini`/`fim` None viram NaT (sem limite).
    """
    return pd.DataFrame({
        "ticker": [ticker for ticker, *_ in linhas],
        "ordem": [int(ordem) for _, ordem, *_ in linhas],
        "ticker_negociado": [negociado for _, _, negociado, *_ in linhas],
        "cd_cvm": [None for _ in linhas],
        "cnpj": [cnpj for _, _, _, cnpj, *_ in linhas],
        "empresa": [empresa for _, _, _, _, empresa, *_ in linhas],
        "vigencia_inicio": pd.to_datetime([ini for _, _, _, _, _, ini, *_ in linhas]).to_numpy(),
        "vigencia_fim": pd.to_datetime([fim for _, _, _, _, _, _, fim, _ in linhas]).to_numpy(),
        "fator_acoes": [_numero(fator) for *_, fator in linhas],
    })


def acoes_base_de(linhas: list[tuple]) -> pd.DataFrame:
    """Linhas de `v1-acoes_emitidas` com a base atual.

    Cada linha: (cnpj, data_referencia, data_entrega, qtd_on, qtd_pn, qtd_on_base_atual,
    qtd_pn_base_atual, situacao). Datas viram datetime64; números, float (None vira NaN).
    """
    return pd.DataFrame({
        "cnpj": [linha[0] for linha in linhas],
        "data_referencia": pd.to_datetime([linha[1] for linha in linhas]).to_numpy(),
        "data_entrega": pd.to_datetime([linha[2] for linha in linhas]).to_numpy(),
        "qtd_on": [_numero(linha[3]) for linha in linhas],
        "qtd_pn": [_numero(linha[4]) for linha in linhas],
        "qtd_on_base_atual": [_numero(linha[5]) for linha in linhas],
        "qtd_pn_base_atual": [_numero(linha[6]) for linha in linhas],
        "situacao": [linha[7] for linha in linhas],
    })


# Linhas de v1-emissores_ticker da tabela da seção 6 (ordem, código negociado, CNPJ, empresa, vigência, fator).
LINHAS_EMISSORES_REAIS = [
    ("JBSS32", 1, "JBSS3", CNPJ_JBS_SA, "JBS SA", None, "2025-06-08", 0.5),
    ("JBSS32", 2, "JBSS32", CNPJ_JBS_NV, "JBS N.V.", "2025-06-09", None, 1.0),
    ("NATU3", 1, "NATU3", "71673990000177", "Natura Cosmeticos", None, "2019-12-17", 1.0),
    ("NATU3", 2, "NTCO3", "32785497000197", "Natura &Co Holding", "2019-12-18", "2025-07-01", 1.0),
    ("NATU3", 3, "NATU3", "71673990000177", "Natura Cosmeticos", "2025-07-02", None, 1.0),
    ("HAPV3", 1, "HAPV3", CNPJ_HAPV3, "Hapvida", None, None, 1.0),
    ("MGLU3", 1, "MGLU3", CNPJ_MGLU3, "Magazine Luiza", None, None, 1.0),
]

EMISSORES_REAIS = emissores_de(LINHAS_EMISSORES_REAIS)

# Ações da HAPV3 (base atual): (cnpj, data_ref, data_entrega, qtd_on, qtd_pn, base_on, base_pn, situacao).
# Linhas expostas para quem precisa acrescentar uma linha (ex.: anulado) antes de montar o DataFrame.
ACOES_HAPV3_LINHAS = [
    (CNPJ_HAPV3, "2020-03-31", "2020-05-20", 742985906, 0, 247661969, 0, "ok"),
    (CNPJ_HAPV3, "2020-12-31", "2021-03-23", 3714929530, 0, 247661969, 0, "ok"),
    (CNPJ_HAPV3, "2021-03-31", "2021-05-12", 3714929530, 0, 247661969, 0, "ok"),
    (CNPJ_HAPV3, "2021-06-30", "2021-08-11", 3891569750, 0, 259437983, 0, "ok"),
    (CNPJ_HAPV3, "2022-03-31", "2022-05-16", 7142378316, 0, 476158554, 0, "ok"),
    (CNPJ_HAPV3, "2023-03-31", "2024-11-29", 7144255843, 0, 476283723, 0, "ok"),
    (CNPJ_HAPV3, "2023-12-31", "2024-05-13", 7539463263, 0, 502630884, 0, "ok"),
    (CNPJ_HAPV3, "2025-06-30", "2025-08-13", 502630884, 0, 502630884, 0, "ok"),
]
ACOES_HAPV3 = acoes_base_de(ACOES_HAPV3_LINHAS)

# Ações da MGLU3 (mesmo formato da HAPV3).
ACOES_MGLU3_LINHAS = [
    (CNPJ_MGLU3, "2020-09-30", "2020-11-09", 6498926848, 0, 682387319, 0, "ok"),
    (CNPJ_MGLU3, "2021-03-31", "2021-05-13", 6498926848, 0, 682387319, 0, "ok"),
    (CNPJ_MGLU3, "2021-06-30", "2021-08-16", 6498926848, 0, 682387319, 0, "ok"),
    (CNPJ_MGLU3, "2024-03-31", "2024-05-09", 7389952489, 0, 775945011, 0, "ok"),
    (CNPJ_MGLU3, "2024-06-30", "2024-08-09", 738995248, 0, 775945010, 0, "ok"),
    (CNPJ_MGLU3, "2025-12-31", "2026-03-12", 775945010, 0, 775945010, 0, "ok"),
]
ACOES_MGLU3 = acoes_base_de(ACOES_MGLU3_LINHAS)
