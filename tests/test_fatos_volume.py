"""Testes de volume_relativo (caso b da etapa 3): total, relativo e mediana de 20 pregões.

Séries montadas com tests/fabrica_precos.py. Nenhum teste usa banco ou rede.
"""

import numpy as np
import pytest

from fabrica_precos import pregoes_uteis, precos_de
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    grade_de_precos,
    volume_relativo,
)

CAL22 = pregoes_uteis(22)


def _volumes(alterados=None):
    """Volume p0=1_000_000 e p_k=100·k (k=1..21); `alterados` troca posições (None = nulo)."""
    vol = [1_000_000.0] + [100.0 * k for k in range(1, 22)]
    for pos, valor in (alterados or {}).items():
        vol[pos] = valor
    return vol


def _tres_grades(volumes):
    precos = precos_de("VOLU3", CAL22, fech=[10.0] * 22, volume=volumes)
    gv = grade_de_precos(precos, CAL22, "volume", ["VOLU3"])
    return volume_relativo(gv, 20)


def test_mediana_relativo_e_total_no_ultimo_pregao():
    total, rel, med = _tres_grades(_volumes())

    assert med.valor["VOLU3"].iloc[21] == pytest.approx(1050.0, abs=1e-12)
    assert rel.valor["VOLU3"].iloc[21] == pytest.approx(2.0, abs=1e-12)
    assert total.valor["VOLU3"].iloc[21] == pytest.approx(2100.0, abs=1e-12)
    for grade in (total, rel, med):
        assert grade.status["VOLU3"].iloc[21] == OK


def test_relativo_com_vinte_pregoes_anteriores_inclui_o_primeiro_grande():
    _, rel, _ = _tres_grades(_volumes())

    assert rel.valor["VOLU3"].iloc[20] == pytest.approx(1.9047619047619047, abs=1e-12)
    assert rel.status["VOLU3"].iloc[20] == OK


def test_com_menos_de_vinte_anteriores_e_historico_insuficiente():
    total, rel, med = _tres_grades(_volumes())

    assert rel.status["VOLU3"].iloc[19] == HIST
    assert med.status["VOLU3"].iloc[19] == HIST
    assert np.isnan(rel.valor["VOLU3"].iloc[19])
    assert total.valor["VOLU3"].iloc[19] == pytest.approx(1900.0, abs=1e-12)
    assert total.status["VOLU3"].iloc[19] == OK


def test_volume_nulo_em_uma_das_vinte_anteriores_deixa_relativo_historico():
    # p5 nulo entra na janela de p21 (p1..p20), então a mediana não fecha.
    _, rel, _ = _tres_grades(_volumes({5: None}))

    assert rel.status["VOLU3"].iloc[21] == HIST
    assert np.isnan(rel.valor["VOLU3"].iloc[21])


def test_volume_nulo_no_dia_torna_total_e_relativo_indisponiveis_mas_nao_a_mediana():
    total, rel, med = _tres_grades(_volumes({21: None}))

    assert total.status["VOLU3"].iloc[21] == INDISPONIVEL
    assert rel.status["VOLU3"].iloc[21] == INDISPONIVEL
    assert med.status["VOLU3"].iloc[21] == OK
    assert med.valor["VOLU3"].iloc[21] == pytest.approx(1050.0, abs=1e-12)


def test_mediana_zero_deixa_relativo_indisponivel():
    # p1..p20 zerados: a mediana de p21 é 0 (ok), mas o relativo não existe (divisão por zero).
    volumes = _volumes({k: 0.0 for k in range(1, 21)})
    volumes[21] = 100.0
    total, rel, med = _tres_grades(volumes)

    assert med.status["VOLU3"].iloc[21] == OK
    assert med.valor["VOLU3"].iloc[21] == pytest.approx(0.0, abs=1e-12)
    assert rel.status["VOLU3"].iloc[21] == INDISPONIVEL
    assert np.isnan(rel.valor["VOLU3"].iloc[21])
    assert total.status["VOLU3"].iloc[21] == OK
