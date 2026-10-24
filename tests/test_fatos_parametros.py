"""Testes de processamento/fatos/precos.py: parâmetros da fase 1 e grade com status.

Usa o parametros.yaml real e cópias temporárias (tmp_path) para os casos de erro.
Nenhum teste usa banco ou rede.
"""

import re

import numpy as np
import pandas as pd
import pytest
import yaml

from processamento import calendario
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    ErroParametrosPrecos,
    carregar_parametros_precos,
    montar_grade,
)


def _parametros_em(tmp_path, mudar) -> str:
    """Copia o parametros.yaml real, aplica `mudar(dados)` e grava em tmp_path."""
    dados = yaml.safe_load(calendario.CAMINHO_PARAMETROS.read_text(encoding="utf-8"))
    mudar(dados)
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return str(caminho)


def test_yaml_real_traz_o_bloco_fase1():
    params = carregar_parametros_precos()
    assert params.janelas == {"d1": 1, "m1": 21, "m6": 126, "a1": 252}
    assert params.volume_pregoes == 20
    assert params.volatilidade_retornos == 20
    assert params.beta_pregoes == 252
    assert params.beta_minimo == 120
    assert params.setor_minimo == 3
    assert params.setor_excluir == "empresa"
    assert params.retorno_suspeito_min == -0.75
    assert params.retorno_suspeito_max == 1.0
    assert params.retorno_suspeito_pregoes_nivel == 21


def test_calendario_continua_carregando_o_yaml_real():
    dados = calendario.carregar_parametros()
    assert "fase1" in dados
    assert dados["fuso"] == "America/Sao_Paulo"


def test_yaml_sem_bloco_fase1_levanta_erro(tmp_path):
    caminho = _parametros_em(tmp_path, lambda d: d.pop("fase1"))
    with pytest.raises(ErroParametrosPrecos, match=re.escape("falta o bloco fase1")):
        carregar_parametros_precos(caminho)


@pytest.mark.parametrize(
    "mudar, trecho",
    [
        (lambda d: d["fase1"].__setitem__("setor_excluir", "x"), "fase1.setor_excluir"),
        (lambda d: d["fase1"]["janelas"].__setitem__("d1", 0), "fase1.janelas.d1"),
        (lambda d: d["fase1"].__setitem__("beta_minimo", 300), "fase1.beta_minimo"),
        (lambda d: d["fase1"].__setitem__("volume_pregoes", True), "fase1.volume_pregoes"),
        (lambda d: d["fase1"].__setitem__("chave_nova", 1), "chave desconhecida"),
        (lambda d: d["fase1"].__setitem__("retorno_suspeito_min", 0.1), "fase1.retorno_suspeito_min"),
        (lambda d: d["fase1"].__setitem__("retorno_suspeito_min", True), "fase1.retorno_suspeito_min"),
        (lambda d: d["fase1"].__setitem__("retorno_suspeito_max", -1.0), "fase1.retorno_suspeito_max"),
        (lambda d: d["fase1"].__setitem__("retorno_suspeito_pregoes_nivel", 0), "fase1.retorno_suspeito_pregoes_nivel"),
        (lambda d: d["fase1"].pop("retorno_suspeito_max"), "faltam chaves"),
    ],
)
def test_parametros_invalidos_levantam_erro(tmp_path, mudar, trecho):
    caminho = _parametros_em(tmp_path, mudar)
    with pytest.raises(ErroParametrosPrecos, match=re.escape(trecho)):
        carregar_parametros_precos(caminho)


def test_montar_grade_anula_onde_status_nao_ok():
    idx = pd.DatetimeIndex(["2025-01-02", "2025-01-03"], name="data")
    valor = pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, 4.0]}, index=idx)
    status = pd.DataFrame({"A": [OK, HIST], "B": [INDISPONIVEL, OK]}, index=idx)

    grade = montar_grade(valor, status)

    assert grade.valor.loc[idx[0], "A"] == 1.0
    assert grade.valor.loc[idx[1], "B"] == 4.0
    assert np.isnan(grade.valor.loc[idx[1], "A"])
    assert np.isnan(grade.valor.loc[idx[0], "B"])
    pd.testing.assert_frame_equal(grade.status, status)
