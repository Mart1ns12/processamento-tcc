"""Testes do alvo (processamento/experimento/alvo.py): t+1 é o próximo pregão de cal."""

from datetime import date

import pandas as pd
import pytest

from fabrica_precos import precos_de
from processamento.experimento.alvo import alvos

NAN = float("nan")
CAL = [date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)]
D0, D1, D2 = (pd.Timestamp(d) for d in CAL)
TICKERS = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3"]


def _linhas(ticker, datas, ab, fech, aj):
    """Linhas de `v1-precos` com abertura, fechamento e fechamento ajustado escritos à mão."""
    df = precos_de(ticker, datas, fech, aj)
    df["abertura"] = [float(x) for x in ab]
    return df


def _precos():
    return pd.concat([
        _linhas("IBOV", CAL, [64000, 64320, 68000], [64000, 68000, 68000], [64000, 68000, 68000]),
        _linhas("AAAA3", CAL, [8, 9, 9], [8, 9, 9], [8, 9, 9]),
        _linhas("BBBB3", CAL, [8, 8.25, 8.5], [8, 8.25, 8.5], [8, 8.25, 8.5]),
        _linhas("CCCC3", CAL, [8, 8.5, 8], [8, 8.5, 8], [8, 8.5, 8]),
        _linhas("DDDD3", CAL, [8, NAN, 8], [8, NAN, 8], [8, NAN, 8]),
        _linhas("EEEE3", CAL, [20, 20.2, 20.2], [20, 20.4, 20.4], [19, 19.38, 19.38]),
        _linhas("FFFF3", CAL, [10, 10.04, 10.04], [10, 10.5, 10.5], [10, 10.5, 10.5]),
    ], ignore_index=True)


def test_alvo_empate_e_nan_no_ultimo_pregao():
    r = alvos(_precos(), CAL, TICKERS)
    alvo = r["alvo"]
    assert alvo.loc[D0, "AAAA3"] == 1.0
    assert alvo.loc[D1, "AAAA3"] == 0.0  # empate exato (0 = 0): vale 0
    assert pd.isna(alvo.loc[D2, "AAAA3"])
    assert alvo.loc[D0, "BBBB3"] == 0.0
    assert alvo.loc[D1, "BBBB3"] == 1.0
    assert pd.isna(alvo.loc[D2, "BBBB3"])
    assert alvo.loc[D0, "CCCC3"] == 0.0  # empate exato 0,0625 = 0,0625: vale 0
    assert alvo.loc[D1, "CCCC3"] == 0.0


def test_alvo_com_lado_faltando_e_NaN():
    alvo = alvos(_precos(), CAL, TICKERS)["alvo"]
    assert pd.isna(alvo.loc[D0, "DDDD3"])
    assert pd.isna(alvo.loc[D1, "DDDD3"])
    assert pd.isna(alvo.loc[D2, "DDDD3"])


def test_alvo_de_abertura_usa_abertura_ajustada():
    r = alvos(_precos(), CAL, TICKERS)
    ab = r["alvo_abertura"]
    assert ab.loc[D0, "AAAA3"] == 1.0
    assert ab.loc[D0, "BBBB3"] == 1.0
    assert ab.loc[D0, "CCCC3"] == 1.0
    assert ab.loc[D0, "EEEE3"] == 1.0  # 0,01 > 0,005
    assert ab.loc[D0, "FFFF3"] == 0.0  # 0,004 < 0,005
    assert pd.isna(ab.loc[D0, "DDDD3"])


def test_alvo_ret_t1_e_ibov_exatos():
    r = alvos(_precos(), CAL, TICKERS)
    assert r["ret_t1"].loc[D0, "AAAA3"] == 0.125
    assert r["ret_ibov_t1"].loc[D0, "AAAA3"] == 0.0625
    assert r["ret_ibov_t1"].loc[D0, "DDDD3"] == 0.0625


def test_t1_e_o_proximo_pregao_de_cal_nao_o_dia_seguinte():
    # 19/06 existe nos preços mas não está em cal: t+1 de 18/06 é 22/06.
    cal = [date(2026, 6, 18), date(2026, 6, 22)]
    precos = _precos()
    precos.loc[precos["data"] == pd.Timestamp("2026-06-19"), "fechamento_ajustado"] = 100.0
    r = alvos(precos, cal, ["AAAA3"])
    assert list(r["ret_t1"].index) == [pd.Timestamp("2026-06-18"), pd.Timestamp("2026-06-22")]
    assert r["ret_t1"].loc[pd.Timestamp("2026-06-18"), "AAAA3"] == 0.125


def test_abertura_do_ibov_valida_so_quando_difere_do_fechamento_anterior():
    v = alvos(_precos(), CAL, TICKERS)["alvo_abertura_valido"]
    for t in TICKERS:                  # vale igual para todas as ações, inclusive DDDD3 (com NaN)
        assert v.loc[D0, t] == 1.0     # abertura(D1)=64320 ≠ fechamento(D0)=64000
        assert v.loc[D1, t] == 0.0     # abertura(D2)=68000 = fechamento(D1)=68000
        assert pd.isna(v.loc[D2, t])   # último pregão: sem t+1
