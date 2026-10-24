"""Testes dos retornos diários suspeitos (processamento/fatos/precos.py; plano suspeitos_setor, Fase 1).

Casos 1a a 1k do plano. Dados escritos à mão com a fábrica `fabrica_precos`.
Nenhum teste usa banco ou rede.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import precos_de, pregoes_uteis
from processamento.fatos.precos import (
    grade_de_precos,
    retornos_asof,
    retornos_diarios,
    retornos_suspeitos,
    suspeita_na_janela,
    tickers_com_suspeita,
)

CAL = pregoes_uteis(6, "2026-04-06")   # 06, 07, 08, 09, 10 e 13/04/2026
AZUL = [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0]   # bug x20000 em 08 e 09/04
GAPX = [10.0, None, 25.0, 25.0, 25.0, 25.0]                  # salto escondido atrás de um dia sem preço
LIMI = [100.0, 25.0, 50.0, 100.0, 24.99, 50.0]               # limites exatos
TICKERS = ["AZUL3", "GAPX3", "LIMI3"]
PRECOS = pd.concat([precos_de("AZUL3", CAL, AZUL), precos_de("GAPX3", CAL, GAPX), precos_de("LIMI3", CAL, LIMI)])
G = grade_de_precos(PRECOS, CAL, "fechamento_ajustado", TICKERS)
S = retornos_suspeitos(G, -0.75, 1.0)


def _lista(serie) -> list:
    """Valores de uma coluna como lista (NaN fica NaN)."""
    return serie.tolist()


def _assert_booleanos(serie, esperado: list[bool]) -> None:
    assert _lista(serie) == esperado


def test_1a_retorno_asof_azul3():
    r = _lista(retornos_asof(G)["AZUL3"])
    esperado = [np.nan, 0.020000000000000018, 19999.0, 0.050000000000000044, -0.9999509803921569, 0.0]
    assert pd.isna(r[0])
    assert r[1:] == pytest.approx(esperado[1:], rel=1e-12)


def test_1b_retorno_asof_pula_dia_sem_preco_e_diario_nao():
    r = _lista(retornos_asof(G)["GAPX3"])
    assert pd.isna(r[0]) and pd.isna(r[1])
    assert r[2:] == pytest.approx([1.5, 0.0, 0.0, 0.0], rel=1e-12)
    assert pd.isna(retornos_diarios(G)["GAPX3"].iloc[2])


def test_1c_retorno_asof_limites_exatos():
    r = _lista(retornos_asof(G)["LIMI3"])
    assert pd.isna(r[0])
    assert r[1:] == pytest.approx([-0.75, 1.0, 1.0, -0.7501, 1.0008003201280515], rel=1e-12)


def test_1d_suspeitos_por_coluna_limites_estritos():
    _assert_booleanos(S["AZUL3"], [False, False, True, False, True, False])
    _assert_booleanos(S["GAPX3"], [False, False, True, False, False, False])
    _assert_booleanos(S["LIMI3"], [False, False, False, False, True, True])


def test_1e_janela_1_igual_aos_suspeitos_do_dia():
    janela = suspeita_na_janela(S, 1)
    for tk in TICKERS:
        _assert_booleanos(janela[tk], _lista(S[tk]))


def test_1f_janela_2():
    janela = suspeita_na_janela(S, 2)
    _assert_booleanos(janela["AZUL3"], [False, False, True, True, True, True])
    _assert_booleanos(janela["GAPX3"], [False, False, True, True, False, False])
    _assert_booleanos(janela["LIMI3"], [False, False, False, False, True, True])


def test_1g_janela_3():
    janela = suspeita_na_janela(S, 3)
    _assert_booleanos(janela["AZUL3"], [False, False, True, True, True, True])
    _assert_booleanos(janela["GAPX3"], [False, False, True, True, True, False])
    _assert_booleanos(janela["LIMI3"], [False, False, False, False, True, True])


def test_1h_tickers_com_suspeita_ate_13_abril():
    t = date(2026, 4, 13)
    assert tickers_com_suspeita(PRECOS, CAL, t, TICKERS, -0.75, 1.0, 1) == {"LIMI3"}
    assert tickers_com_suspeita(PRECOS, CAL, t, TICKERS, -0.75, 1.0, 2) == {"AZUL3", "LIMI3"}
    assert tickers_com_suspeita(PRECOS, CAL, t, TICKERS, -0.75, 1.0, 4) == {"AZUL3", "GAPX3", "LIMI3"}


def test_1i_sem_suspeita_antes_do_primeiro_salto():
    assert tickers_com_suspeita(PRECOS, CAL, date(2026, 4, 7), TICKERS, -0.75, 1.0, 21) == set()


def test_1j_fim_de_semana_nao_e_pregao():
    with pytest.raises(ValueError):
        tickers_com_suspeita(PRECOS, CAL, date(2026, 4, 4), TICKERS, -0.75, 1.0, 21)


def test_1k_sem_vazamento_de_futuro():
    corte = PRECOS[PRECOS["data"] <= pd.Timestamp("2026-04-09")]
    assert tickers_com_suspeita(corte, CAL[:4], date(2026, 4, 9), TICKERS, -0.75, 1.0, 1) == set()
    assert tickers_com_suspeita(PRECOS, CAL, date(2026, 4, 9), TICKERS, -0.75, 1.0, 1) == set()
