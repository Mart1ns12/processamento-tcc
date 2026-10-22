"""media_setor no modo "empresa": cada CNPJ conta uma vez (plano da etapa 4, ajuste A1).

Grade de 1 pregão escrita à mão. Z3 tem status não ok (ex.: lucro_negativo), então
`montar_grade` o anula e ele fica fora das médias. Nenhum teste usa banco ou rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, pregoes_uteis
from processamento.fatos.precos import HIST, OK, indice_pregoes, mapas_cadastro, media_setor, montar_grade

# (ticker, cnpj, setor, valor, status)
LINHAS = [
    ("X3", "1", "S", 10.0, OK),
    ("X4", "1", "S", 20.0, OK),
    ("Y3", "2", "S", 40.0, OK),
    ("Z3", "3", "S", -5.0, "lucro_negativo"),
    ("W3", None, "S", 30.0, OK),
    ("Q3", "4", "T", 8.0, OK),
    ("R3", "5", "T", -2.0, "lucro_negativo"),
]
TICKERS = [t for t, *_ in LINHAS]


def _media(trocar: dict | None = None):
    linhas = [(t, c, s, (trocar or {}).get(t, (v, st))) for t, c, s, v, st in LINHAS]
    idx = indice_pregoes(pregoes_uteis(1))
    valores = pd.DataFrame([[v for *_, (v, _) in linhas]], index=idx, columns=TICKERS, dtype=float)
    status = pd.DataFrame([[st for *_, (_, st) in linhas]], index=idx, columns=TICKERS, dtype=object)
    setor_de, cnpj_de = mapas_cadastro(cadastro_de([(t, c, s, "ON") for t, c, s, _ in linhas]))
    return media_setor(montar_grade(valores, status), TICKERS, setor_de, cnpj_de, "empresa")


def _confere(res, ticker, valor, status):
    assert res.status[ticker].iloc[0] == status
    if valor is None:
        assert np.isnan(res.valor[ticker].iloc[0])
    else:
        assert res.valor[ticker].iloc[0] == pytest.approx(valor, rel=1e-9)


def test_cada_empresa_conta_uma_vez():
    res = _media()
    _confere(res, "X3", 35.0, OK)  # (Y 40 + W 30) / 2
    _confere(res, "X4", 35.0, OK)
    _confere(res, "Y3", 22.5, OK)  # (X 15 + W 30) / 2; por ação daria 20
    _confere(res, "W3", 27.5, OK)  # (X 15 + Y 40) / 2
    _confere(res, "Z3", 28.333333333333332, OK)  # (15 + 40 + 30) / 3


def test_empresa_com_uma_classe_sem_valor_usa_a_outra():
    res = _media({"X4": (float("nan"), HIST)})
    _confere(res, "Y3", 20.0, OK)  # (X 10 + W 30) / 2


def test_unico_par_sem_valor_ok_fica_fora():
    res = _media()
    _confere(res, "Q3", None, HIST)  # R3 com lucro_negativo não entra
    _confere(res, "R3", 8.0, OK)
