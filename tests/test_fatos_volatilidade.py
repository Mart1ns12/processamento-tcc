"""Testes de volatilidade e posicao_pct (caso c da etapa 3).

Séries montadas com tests/fabrica_precos.py; a grade de posicao_pct é escrita à mão.
Nenhum teste usa banco ou rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import pregoes_uteis, precos_de, serie_por_retornos
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    NAO_SE_APLICA,
    OK,
    grade_de_precos,
    indice_pregoes,
    montar_grade,
    posicao_pct,
    volatilidade,
)

CAL22 = pregoes_uteis(22)
COLUNAS = ["P1", "P2", "P3", "P4", "P5", "Z32"]
PARES = ["P1", "P2", "P3", "P4", "P5"]


def _aj_vola3(aj_com_nulo=None):
    """aj de VOLA3: retorno 0.5 em p1 e ±0.01 alternado de p2 a p21 (par = +, ímpar = −)."""
    retornos = [0.5] + [0.01 if k % 2 == 0 else -0.01 for k in range(2, 22)]
    aj = serie_por_retornos(100, retornos)
    for pos in aj_com_nulo or ():
        aj[pos] = None
    return aj


def _grade_aj(aj):
    precos = precos_de("VOLA3", CAL22, fech=aj, aj=aj)
    return grade_de_precos(precos, CAL22, "fechamento_ajustado", ["VOLA3"])


def test_desvio_amostral_dos_vinte_ultimos_retornos():
    vol = volatilidade(_grade_aj(_aj_vola3()), 20)

    assert vol.valor["VOLA3"].iloc[21] == pytest.approx(0.01025978352085154, abs=1e-12)
    assert vol.status["VOLA3"].iloc[21] == OK
    assert vol.valor["VOLA3"].iloc[20] == pytest.approx(0.11213126706067124, abs=1e-12)
    assert vol.status["VOLA3"].iloc[20] == OK


def test_com_menos_de_vinte_retornos_e_historico_insuficiente():
    vol = volatilidade(_grade_aj(_aj_vola3()), 20)

    assert vol.status["VOLA3"].iloc[19] == HIST
    assert np.isnan(vol.valor["VOLA3"].iloc[19])


def test_preco_faltando_dentro_da_janela_deixa_historico_insuficiente():
    # Sem o preço de p10, os retornos de p10 e p11 somem: a janela de p21 (p2..p21) fica incompleta.
    vol = volatilidade(_grade_aj(_aj_vola3(aj_com_nulo=[10])), 20)

    assert vol.status["VOLA3"].iloc[21] == HIST
    assert np.isnan(vol.valor["VOLA3"].iloc[21])


def test_aj_faltando_no_dia_e_indisponivel():
    vol = volatilidade(_grade_aj(_aj_vola3(aj_com_nulo=[21])), 20)

    assert vol.status["VOLA3"].iloc[21] == INDISPONIVEL
    assert np.isnan(vol.valor["VOLA3"].iloc[21])


def _grade_a_mao(valores, status):
    """Grade de `len(valores)` pregões e as colunas P1..P5, Z32 (None = NaN)."""
    idx = indice_pregoes(pregoes_uteis(len(valores)))
    v = pd.DataFrame(valores, index=idx, columns=COLUNAS, dtype=float)
    s = pd.DataFrame(status, index=idx, columns=COLUNAS, dtype=object)
    return montar_grade(v, s)


def test_posicao_pct_com_todos_os_pares_validos_menos_um():
    gr = _grade_a_mao(
        valores=[[0.01, 0.02, 0.02, 0.04, None, 0.03]],
        status=[[OK, OK, OK, OK, HIST, OK]],
    )
    pos = posicao_pct(gr, PARES)

    assert pos.valor["P1"].iloc[0] == pytest.approx(0.0, abs=1e-12)
    assert pos.valor["P2"].iloc[0] == pytest.approx(1 / 3, abs=1e-12)
    assert pos.valor["P3"].iloc[0] == pytest.approx(1 / 3, abs=1e-12)
    assert pos.valor["P4"].iloc[0] == pytest.approx(1.0, abs=1e-12)

    assert pos.status["P1"].iloc[0] == OK
    assert pos.status["P4"].iloc[0] == OK
    assert np.isnan(pos.valor["P5"].iloc[0])
    assert pos.status["P5"].iloc[0] == HIST  # herdado do status da própria grade

    assert np.isnan(pos.valor["Z32"].iloc[0])
    assert pos.status["Z32"].iloc[0] == NAO_SE_APLICA


def test_posicao_pct_com_so_um_par_valido_e_indisponivel():
    gr = _grade_a_mao(
        valores=[[0.01, None, None, None, None, 0.5]],
        status=[[OK, HIST, HIST, HIST, HIST, OK]],
    )
    pos = posicao_pct(gr, PARES)

    assert pos.status["P1"].iloc[0] == INDISPONIVEL
    assert np.isnan(pos.valor["P1"].iloc[0])
    for par in ("P2", "P3", "P4", "P5"):
        assert pos.status[par].iloc[0] == HIST
        assert np.isnan(pos.valor[par].iloc[0])
    assert pos.status["Z32"].iloc[0] == NAO_SE_APLICA
