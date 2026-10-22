"""Testes de media_setor, comparacao_fraca e mapas_cadastro (caso e da etapa 3).

Grade de 1 pregão escrita à mão; os dois modos ("acao" e "empresa") são testados.
Nenhum teste usa banco ou rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, pregoes_uteis
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    comparacao_fraca,
    indice_pregoes,
    mapas_cadastro,
    media_setor,
    montar_grade,
)

# (ticker, cnpj, setor, tipo_acao, valor, status) — uma linha por ticker, na ordem da tabela.
LINHAS = [
    ("A3", "1", "Energia", "ON", 0.01, OK),
    ("B3", "2", "Energia", "ON", 0.02, OK),
    ("C3", "3", "Energia", "ON", 0.06, OK),
    ("Z32", "9", "Energia", "BDR", 0.50, OK),
    ("D3", "4", "Unico", "ON", 0.05, OK),
    ("G3", "7", "Bancos", "ON", 0.10, OK),
    ("G4", "7", "Bancos", "PN", 0.12, OK),
    ("H3", "8", "Bancos", "ON", 0.03, OK),
    ("E3", "5", "Varejo", "ON", 0.02, OK),
    ("F3", "6", "Varejo", "ON", float("nan"), HIST),
    ("X3", "10", None, "ON", 0.07, OK),
]
PARES = [t for t, _, _, tipo, _, _ in LINHAS if tipo != "BDR"]
TICKERS = [t for t, *_ in LINHAS]

# Modo "acao": só a própria ação sai do setor.
ESPERADO_ACAO = {
    "A3": (0.04, OK),
    "B3": (0.035, OK),
    "C3": (0.015, OK),
    "Z32": (0.03, OK),
    "D3": (None, INDISPONIVEL),
    "G3": (0.075, OK),
    "G4": (0.065, OK),
    "H3": (0.11, OK),
    "E3": (None, HIST),
    "F3": (0.02, OK),
    "X3": (None, INDISPONIVEL),
}
# Modo "empresa" (padrão): G3 e G4 são do mesmo CNPJ, então nenhuma tira a outra do setor.
ESPERADO_EMPRESA = {**ESPERADO_ACAO, "G3": (0.03, OK), "G4": (0.03, OK)}

FRACA_ACAO = {
    "A3": False, "B3": False, "C3": False, "Z32": False,
    "G3": False, "G4": False, "H3": False,
    "E3": True, "F3": True, "D3": True, "X3": True,
}
FRACA_EMPRESA = {**FRACA_ACAO, "G3": True, "G4": True, "H3": True}


def _cadastro():
    return cadastro_de([(t, c, s, tipo) for t, c, s, tipo, _, _ in LINHAS])


def _grade():
    idx = indice_pregoes(pregoes_uteis(1))
    valores = pd.DataFrame([[v for *_, v, _ in LINHAS]], index=idx, columns=TICKERS, dtype=float)
    status = pd.DataFrame([[s for *_, s in LINHAS]], index=idx, columns=TICKERS, dtype=object)
    return montar_grade(valores, status)


def _confere(grade, ticker, valor, status):
    assert grade.status[ticker].iloc[0] == status
    if valor is None:
        assert np.isnan(grade.valor[ticker].iloc[0])
    else:
        assert grade.valor[ticker].iloc[0] == pytest.approx(valor, abs=1e-12)


def test_media_do_setor_modo_acao():
    setor_de, cnpj_de = mapas_cadastro(_cadastro())
    res = media_setor(_grade(), PARES, setor_de, cnpj_de, "acao")

    for ticker, (valor, status) in ESPERADO_ACAO.items():
        _confere(res, ticker, valor, status)


def test_media_do_setor_modo_empresa_padrao():
    setor_de, cnpj_de = mapas_cadastro(_cadastro())
    res = media_setor(_grade(), PARES, setor_de, cnpj_de, "empresa")

    for ticker, (valor, status) in ESPERADO_EMPRESA.items():
        _confere(res, ticker, valor, status)


def test_comparacao_fraca_modo_acao():
    setor_de, cnpj_de = mapas_cadastro(_cadastro())
    res = comparacao_fraca(TICKERS, PARES, setor_de, cnpj_de, "acao", 3)

    assert {t: bool(res[t]) for t in TICKERS} == FRACA_ACAO


def test_comparacao_fraca_modo_empresa():
    setor_de, cnpj_de = mapas_cadastro(_cadastro())
    res = comparacao_fraca(TICKERS, PARES, setor_de, cnpj_de, "empresa", 3)

    assert {t: bool(res[t]) for t in TICKERS} == FRACA_EMPRESA


def test_mapas_cadastro_vazio_e_nan_viram_none():
    cad = cadastro_de([("AAAA3", "", "  ", "ON"), ("BBBB3", None, "Bancos", "ON")])
    setor_de, cnpj_de = mapas_cadastro(cad)

    assert setor_de == {"AAAA3": None, "BBBB3": "Bancos"}
    assert cnpj_de == {"AAAA3": None, "BBBB3": None}


def test_modo_invalido_levanta_erro():
    setor_de, cnpj_de = mapas_cadastro(_cadastro())
    with pytest.raises(ValueError):
        media_setor(_grade(), PARES, setor_de, cnpj_de, "x")
    with pytest.raises(ValueError):
        comparacao_fraca(TICKERS, PARES, setor_de, cnpj_de, "x", 3)
