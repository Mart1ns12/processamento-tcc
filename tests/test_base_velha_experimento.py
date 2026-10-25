"""Base velha no experimento (docs/plano_base_velha.md, seção 1.4, caso K; fase 3).

Retornos ret_1d/5d/20d e o retorno do dia da ret_vs_setor usam a regra as-of com
`fase1.base_defasagem_max_pregoes` (padrão 5). Valores esperados vêm do plano.
"""

from __future__ import annotations

import dataclasses
import math

import pandas as pd
import pytest

from fabrica_precos import pregoes_uteis, precos_de
from processamento.experimento.variaveis import variaveis_de_preco
from processamento.fatos import precos as fatos_precos
from test_exp_variaveis import _params, _params_precos


def _mundo_k():
    """Caso K: AAAA3 e BBBB3 com 6 e 5 pregões sem preço antes de 2025-02-07 (linha 26)."""
    cal = pregoes_uteis(30)
    aaaa3 = [10 + 0.1 * i for i in range(20)] + [None] * 6 + [13.0, 13.1, 13.2, 13.3]
    bbbb3 = [20 + 0.1 * i for i in range(21)] + [None] * 5 + [25.0, 25.1, 25.2, 25.3]
    precos = pd.concat([
        precos_de("AAAA3", cal, aaaa3),
        precos_de("BBBB3", cal, bbbb3),
        precos_de("IBOV", cal, [100 + i for i in range(30)]),
        precos_de("USDBRL", cal, [5.0] * 30),
        precos_de("BRENT", cal, [80.0] * 30),
    ], ignore_index=True)
    return precos, cal


def _rodar(base_defasagem_max_pregoes: int | None = 5):
    precos, cal = _mundo_k()
    tickers = ["AAAA3", "BBBB3"]
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(cal), columns=tickers)
    setor_de = {"AAAA3": "S", "BBBB3": "S"}
    cnpj_de = {"AAAA3": "1", "BBBB3": "2"}
    params_precos = _params_precos()
    if base_defasagem_max_pregoes is not None:
        params_precos = dataclasses.replace(params_precos, base_defasagem_max_pregoes=base_defasagem_max_pregoes)
    return variaveis_de_preco(precos, cal, tickers, mascara, setor_de, cnpj_de, _params(), params_precos)


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def test_caso_k_retornos_com_base_velha_dentro_e_fora_da_regra():
    res = _rodar()

    # ret_1d, linha 26: AAAA3 tem base em 2025-02-06 (sem preço); efetiva 2025-01-29, defasagem 6 > N → NaN.
    assert _vazio(res["ret_1d"].iloc[26]["AAAA3"])
    # BBBB3: base em 2025-02-06 (sem preço); efetiva 2025-01-30, defasagem 5 = N → vale.
    assert res["ret_1d"].iloc[26]["BBBB3"] == pytest.approx(0.13636363636363646, abs=1e-12)
    assert res["ret_1d"].iloc[27]["AAAA3"] == pytest.approx(0.007692307692307665, abs=1e-12)
    assert res["ret_1d"].iloc[27]["BBBB3"] == pytest.approx(0.0040000000000000036, abs=1e-12)

    # ret_5d: linha 26 (defasagem 5 na base) e linha 29.
    assert res["ret_5d"].iloc[26]["AAAA3"] == pytest.approx(0.09243697478991586, abs=1e-12)
    assert res["ret_5d"].iloc[26]["BBBB3"] == pytest.approx(0.13636363636363646, abs=1e-12)
    assert res["ret_5d"].iloc[29]["AAAA3"] == pytest.approx(0.11764705882352944, abs=1e-12)
    assert res["ret_5d"].iloc[29]["BBBB3"] == pytest.approx(0.15000000000000013, abs=1e-12)

    # ret_20d, linha 29.
    assert res["ret_20d"].iloc[29]["AAAA3"] == pytest.approx(0.22018348623853212, abs=1e-12)
    assert res["ret_20d"].iloc[29]["BBBB3"] == pytest.approx(0.2105263157894739, abs=1e-12)


def test_caso_k_ret_vs_setor_com_base_velha():
    res = _rodar()

    # Linha 26: o retorno do dia de AAAA3 é NaN (base velha), então a ação some da média do setor.
    assert _vazio(res["ret_vs_setor"].iloc[26]["AAAA3"])
    assert _vazio(res["ret_vs_setor"].iloc[26]["BBBB3"])
    assert res["ret_vs_setor"].iloc[27]["AAAA3"] == pytest.approx(0.0036923076923076614, abs=1e-12)
    assert res["ret_vs_setor"].iloc[27]["BBBB3"] == pytest.approx(-0.0036923076923076614, abs=1e-12)


def test_caso_k_sem_limite_reproduz_o_bug_da_base_velha():
    res = _rodar(base_defasagem_max_pregoes=10**9)

    assert res["ret_1d"].iloc[26]["AAAA3"] == pytest.approx(0.09243697478991586, abs=1e-12)
    assert res["ret_vs_setor"].iloc[26]["AAAA3"] == pytest.approx(-0.043926661573720605, abs=1e-12)
    assert res["ret_vs_setor"].iloc[26]["BBBB3"] == pytest.approx(0.043926661573720605, abs=1e-12)
    # O resto da linha 27 não muda.
    assert res["ret_1d"].iloc[27]["AAAA3"] == pytest.approx(0.007692307692307665, abs=1e-12)
    assert res["ret_vs_setor"].iloc[27]["AAAA3"] == pytest.approx(0.0036923076923076614, abs=1e-12)
