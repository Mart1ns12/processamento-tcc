"""Variáveis do protocolo (blocos A e B) do experimento: uma coluna por bloco de casos.

Valores do gabarito do plano (parte A, seção 2). Tolerância abs 1e-12. Nenhum teste usa banco ou rede.
Séries e grades são escritas à mão ou saem de tests/fabrica_precos.py e de test_exp_suspeitos.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

import test_exp_suspeitos as sus
import test_exp_variaveis as var
from fabrica_precos import indices_de, precos_de, pregoes_uteis, serie_por_retornos
from processamento.experimento.variaveis import (
    liquidez_20d,
    mom_12_1,
    momento_setor,
    posicao_fechamento,
    ret_idio,
    serie_smll,
    variaveis_de_preco,
)
from processamento.fatos import precos as fatos_precos

NAN = float("nan")


def _grade(valores: list, datas: list, ticker: str = "HHHH3") -> pd.DataFrame:
    return var._grade(valores, datas, ticker)


def _checa(obtido, esperado):
    if esperado is None or (isinstance(esperado, float) and np.isnan(esperado)):
        assert np.isnan(obtido)
    else:
        assert obtido == pytest.approx(esperado, abs=1e-12)


# --- posicao_fechamento ---------------------------------------------------------------------

@pytest.mark.parametrize("fech, maxima, minima, esperado", [
    (20, 21, 19, 0.5),
    (21, 21, 19, 1.0),
    (19, 21, 19, 0.0),
    (20, 20, 20, NAN),
    (20, None, 19, NAN),
    (20, 21, None, NAN),
    (19.5, 21, 19, 0.25),
    (None, 21, 19, NAN),
    (20, 19, 20, NAN),
    (20, 21, 20.5, -1.0),
])
def test_posicao_fechamento_tabela(fech, maxima, minima, esperado):
    cal = pregoes_uteis(1, "2025-01-02")
    obtido = posicao_fechamento(
        _grade([fech], cal, "AAAA3"), _grade([maxima], cal, "AAAA3"), _grade([minima], cal, "AAAA3")
    )["AAAA3"].iloc[0]
    _checa(obtido, esperado)


def test_posicao_fechamento_no_suspeito_segue_0_5():
    # precos_de põe máxima = mínima = fechamento; ×1,01 e ×0,99 no pregão S dão (F − 0,99F) ÷ (1,01F − 0,99F) = 0,5.
    precos, _ = sus._mundo()
    dia = pd.Timestamp(sus.CAL50[sus.S])
    marca = (precos["ticker"] == "AAAA3") & (precos["data"] == dia)
    precos.loc[marca, "maxima"] = precos.loc[marca, "maxima"] * 1.01
    precos.loc[marca, "minima"] = precos.loc[marca, "minima"] * 0.99
    g = {c: fatos_precos.grade_de_precos(precos, sus.CAL50, c, ["AAAA3"]) for c in ("fechamento", "maxima", "minima")}
    obtido = posicao_fechamento(g["fechamento"], g["maxima"], g["minima"])["AAAA3"].iloc[sus.S]
    assert obtido == pytest.approx(0.5, abs=1e-12)


# --- mom_12_1 -------------------------------------------------------------------------------

def _mom_k(aj: list, k: int, cal_n: int | None = None) -> float:
    cal = pregoes_uteis(len(aj) if cal_n is None else cal_n)
    g = _grade(aj, cal, "AAAA3")
    suspeitos = fatos_precos.retornos_suspeitos(g, -0.75, 1.0, 5)
    return mom_12_1(g, suspeitos, 5)["AAAA3"].iloc[k]


def _linear(n: int = 300) -> list:
    return [100.0 + i for i in range(n)]


def test_mom_12_1_serie_inteira():
    assert _mom_k(_linear(), 260) == pytest.approx(339 / 108 - 1, abs=1e-12)


def test_mom_12_1_k_251_sem_base_longa_e_nan():
    assert np.isnan(_mom_k(_linear(), 251))


def test_mom_12_1_k_252_base_longa_no_inicio():
    assert _mom_k(_linear(), 252) == pytest.approx(331 / 100 - 1, abs=1e-12)


def test_mom_12_1_vazio_so_no_indice_8_usa_o_9_nao():
    aj = _linear()
    aj[8] = None
    assert _mom_k(aj, 260) == pytest.approx(339 / 107 - 1, abs=1e-12)


def test_mom_12_1_vazios_4_a_8_base_a_5_pregoes():
    aj = _linear()
    for i in range(4, 9):
        aj[i] = None
    assert _mom_k(aj, 260) == pytest.approx(339 / 103 - 1, abs=1e-12)


def test_mom_12_1_vazios_3_a_8_base_a_6_pregoes_e_nan():
    aj = _linear()
    for i in range(3, 9):
        aj[i] = None
    assert np.isnan(_mom_k(aj, 260))


def test_mom_12_1_vazios_235_a_239_ponta_t_menos_21_a_5_pregoes():
    aj = _linear()
    for i in range(235, 240):
        aj[i] = None
    assert _mom_k(aj, 260) == pytest.approx(334 / 108 - 1, abs=1e-12)


def test_mom_12_1_vazios_234_a_239_ponta_a_6_pregoes_e_nan():
    aj = _linear()
    for i in range(234, 240):
        aj[i] = None
    assert np.isnan(_mom_k(aj, 260))


def test_mom_12_1_vazios_0_a_8_sem_base_ate_a_data_alvo_mesmo_com_valor_no_9():
    aj = _linear()
    for i in range(0, 9):
        aj[i] = None
    assert np.isnan(_mom_k(aj, 260))


def _salto(s: int, n: int = 400) -> list:
    """aj = 100 + i antes de s; a partir de s, (100 + i) × 3 (salto de +200% no pregão s)."""
    return [(100.0 + i) * 3 if i >= s else 100.0 + i for i in range(n)]


@pytest.mark.parametrize("s, k, esperado", [
    (100, 351, NAN),                      # k = s + 251: a janela (k−252, k−21] ainda contém s
    (100, 352, 431 / 200 - 1),            # k = s + 252: o salto sai da janela
    (270, 269, 1.9743589743589745),       # salto ainda no futuro
    (270, 270, 1.957627118644068),        # salto no próprio t: fica fora da janela (k−21 < s), não entra na conta
    (270, 290, 369 / 138 - 1),            # k = s + 20: ainda fora da janela de NaN
    (270, 291, NAN),                      # k = s + 21: NaN começa
    (270, 300, NAN),
])
def test_mom_12_1_salto_dentro_da_janela_vira_nan(s, k, esperado):
    obtido = _mom_k(_salto(s), k)
    _checa(obtido, esperado)


# --- liquidez_20d ---------------------------------------------------------------------------

def test_liquidez_20d_mediana_de_20_sessoes():
    cal = pregoes_uteis(21)
    g_fech = _grade([10.0] * 21, cal, "AAAA3")
    gv = _grade([100.0 * (i + 1) for i in range(21)], cal, "AAAA3")
    sus_ = fatos_precos.retornos_suspeitos(g_fech, -0.75, 1.0, 5)
    r = liquidez_20d(g_fech, gv, sus_)["AAAA3"]
    assert np.isnan(r.iloc[18])
    assert r.iloc[19] == pytest.approx(10500.0, abs=1e-9)
    assert r.iloc[20] == pytest.approx(11500.0, abs=1e-9)


def test_liquidez_20d_volume_vazio_na_posicao_5_anula_19_e_20():
    cal = pregoes_uteis(21)
    g_fech = _grade([10.0] * 21, cal, "AAAA3")
    gv = _grade([None if i == 5 else 100.0 * (i + 1) for i in range(21)], cal, "AAAA3")
    sus_ = fatos_precos.retornos_suspeitos(g_fech, -0.75, 1.0, 5)
    r = liquidez_20d(g_fech, gv, sus_)["AAAA3"]
    assert np.isnan(r.iloc[19]) and np.isnan(r.iloc[20])


def test_liquidez_20d_salto_anula_20_sessoes_depois():
    cal = pregoes_uteis(55)
    aj = [100.0] * 25 + [300.0] * 30
    g_aj = _grade(aj, cal, "AAAA3")
    gv = _grade([1000.0] * 55, cal, "AAAA3")
    sus_ = fatos_precos.retornos_suspeitos(g_aj, -0.75, 1.0, 5)
    r = liquidez_20d(g_aj, gv, sus_)["AAAA3"]
    assert r.iloc[24] == pytest.approx(100000.0, abs=1e-9)
    assert r.iloc[25:45].isna().all()
    assert r.iloc[45] == pytest.approx(300000.0, abs=1e-9)


# --- ret_idio_5d ----------------------------------------------------------------------------

def _um(v) -> pd.Series:
    return pd.Series([NAN if v is None else v], index=["AAAA3"], dtype=float)


@pytest.mark.parametrize("ret_5d, beta, ibov_5d, esperado", [
    (0.03, 1.5, 0.02, 0.0),
    (0.03, -0.5, 0.02, 0.04),
    (None, 1, 0.02, NAN),
    (0.03, None, 0.02, NAN),
    (0.03, 1, None, NAN),
])
def test_ret_idio_funcao_pura(ret_5d, beta, ibov_5d, esperado):
    _checa(ret_idio(_um(ret_5d), _um(beta), _um(ibov_5d))["AAAA3"], esperado)


def test_ret_idio_integracao_com_variaveis_de_preco():
    cal = pregoes_uteis(12, "2025-01-02")
    ibov = [100.0, 101.0, 100.0, 102.0, 103.0, 102.0, 104.0, 105.0, 104.0, 106.0, 107.0, 106.0]
    r_ibov = [ibov[i] / ibov[i - 1] - 1 for i in range(1, 12)]
    acao = serie_por_retornos(50.0, [2 * r for r in r_ibov])
    precos = pd.concat([
        precos_de("AAAA3", cal, acao),
        precos_de("IBOV", cal, ibov),
        precos_de("USDBRL", cal, [5.0] * 12),
        precos_de("BRENT", cal, [70.0] * 12),
    ], ignore_index=True)
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(cal), columns=["AAAA3"])
    params = replace(var._params_precos(), beta_pregoes=10, beta_minimo=5)
    res = variaveis_de_preco(precos, cal, ["AAAA3"], mascara, {"AAAA3": "S1"}, {"AAAA3": "1"},
                             var._params(), params)
    assert res["ret_idio_5d"]["AAAA3"].iloc[11] == pytest.approx(-0.0003732787701153928, abs=1e-12)


def test_base_asof_do_ibov_com_vazios_3_a_7():
    cal = pregoes_uteis(14)
    ibov = [None if 3 <= i <= 7 else 1000.0 + 10 * i for i in range(14)]
    g = _grade(ibov, cal, "IBOV")
    obtido = fatos_precos.variacao(g, 5, 5).valor["IBOV"].iloc[12]
    assert obtido == pytest.approx(0.0980392156862746, abs=1e-12)


def test_base_asof_do_ibov_com_vazios_2_a_7_e_nan():
    cal = pregoes_uteis(14)
    ibov = [None if 2 <= i <= 7 else 1000.0 + 10 * i for i in range(14)]
    g = _grade(ibov, cal, "IBOV")
    assert np.isnan(fatos_precos.variacao(g, 5, 5).valor["IBOV"].iloc[12])


def test_ret_idio_salto_anula_ret5_pregoes_25_a_29():
    precos, _ = sus._mundo()
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(sus.CAL50), columns=sus.TICKERS)
    params = replace(var._params_precos(), beta_pregoes=20, beta_minimo=10)
    res = variaveis_de_preco(precos, sus.CAL50, sus.TICKERS, mascara, sus.SETOR_DE, sus.CNPJ_DE,
                             sus._params_exp(), params)
    r = res["ret_idio_5d"]["AAAA3"]
    assert np.isfinite(r.iloc[24])
    assert r.iloc[25:30].isna().all()
    assert np.isfinite(r.iloc[30])


# --- momento_setor_5d -----------------------------------------------------------------------

def _dia(valores: dict) -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]), name="data")
    return pd.DataFrame({t: [NAN if v is None else v] for t, v in valores.items()}, index=idx, dtype=float)


SETOR_MOM = {"XXXX3": "S1", "XXXX4": "S1", "YYYY3": "S1", "ZZZZ3": "S1", "VVVV3": "S1",
             "QQQQ3": "S2", "RRRR3": None, "SSSS3": "S1"}
CNPJ_MOM = {"XXXX3": "1", "XXXX4": "1", "YYYY3": "2", "ZZZZ3": "3", "VVVV3": "5",
            "QQQQ3": "6", "RRRR3": "7", "SSSS3": None}


def _mom_setor(ret_dict: dict, mascara_fora=("VVVV3",)) -> pd.DataFrame:
    ret = _dia(ret_dict)
    mascara = pd.DataFrame(True, index=ret.index, columns=ret.columns)
    for t in mascara_fora:
        if t in mascara.columns:
            mascara[t] = False
    return momento_setor(ret, mascara, SETOR_MOM, CNPJ_MOM).iloc[0]


BASE_MOM = {"XXXX3": 0.02, "XXXX4": 0.04, "YYYY3": 0.01, "ZZZZ3": -0.01, "VVVV3": 0.5,
            "QQQQ3": 0.03, "RRRR3": 0.07}


@pytest.mark.parametrize("caso, ret, esperado", [
    ("base", dict(BASE_MOM), {"XXXX3": 0.0, "XXXX4": 0.0, "YYYY3": 0.01, "ZZZZ3": 0.02, "QQQQ3": NAN, "RRRR3": NAN}),
    ("XXXX4 NaN", {**BASE_MOM, "XXXX4": None},
     {"XXXX3": 0.0, "XXXX4": 0.0, "YYYY3": 0.005, "ZZZZ3": 0.015, "QQQQ3": NAN, "RRRR3": NAN}),
    ("ZZZZ3 NaN", {**BASE_MOM, "ZZZZ3": None},
     {"XXXX3": 0.01, "XXXX4": 0.01, "YYYY3": 0.03, "ZZZZ3": 0.02, "QQQQ3": NAN, "RRRR3": NAN}),
    ("YYYY3 e ZZZZ3 NaN", {**BASE_MOM, "YYYY3": None, "ZZZZ3": None},
     {"XXXX3": NAN, "XXXX4": NAN, "YYYY3": 0.03, "ZZZZ3": 0.03, "QQQQ3": NAN, "RRRR3": NAN}),
])
def test_momento_setor_casos(caso, ret, esperado):
    obtido = _mom_setor(ret)
    for t, v in esperado.items():
        _checa(obtido[t], v)


def test_momento_setor_so_xxxx_e_qqqq_rrrr_no_setor():
    ret = _dia({"XXXX3": 0.02, "XXXX4": 0.04, "QQQQ3": 0.03, "RRRR3": 0.07})
    mascara = pd.DataFrame(True, index=ret.index, columns=ret.columns)
    obtido = momento_setor(ret, mascara, SETOR_MOM, CNPJ_MOM).iloc[0]
    for t in ("XXXX3", "QQQQ3", "RRRR3"):
        assert np.isnan(obtido[t]), t


def test_momento_setor_com_sem_cnpj_empresa_a_parte():
    ret = {**BASE_MOM, "SSSS3": 0.09}
    obtido = _mom_setor(ret)
    _checa(obtido["XXXX3"], 0.03)
    _checa(obtido["YYYY3"], 0.03666666666666666)
    _checa(obtido["ZZZZ3"], 0.043333333333333335)
    _checa(obtido["SSSS3"], 0.01)
    assert np.isnan(obtido["QQQQ3"]) and np.isnan(obtido["RRRR3"])


def test_momento_setor_salto_bbbb3_igual_ret5_de_cccc3_e_aaaa3_a_media():
    precos, _ = sus._mundo()
    res = sus._variaveis(precos)
    ret5, mom = res["ret_5d"], res["momento_setor_5d"]
    assert mom["BBBB3"].iloc[sus.S] == pytest.approx(ret5["CCCC3"].iloc[sus.S], abs=1e-12)
    assert np.isfinite(mom["AAAA3"].iloc[sus.S])
    assert mom["AAAA3"].iloc[sus.S] == pytest.approx(
        (ret5["BBBB3"].iloc[sus.S] + ret5["CCCC3"].iloc[sus.S]) / 2, abs=1e-12
    )


# --- exposicao_small ------------------------------------------------------------------------

CAL7 = pregoes_uteis(7, "2025-01-02")
IBOV7 = [1000.0, 1010.0, 1000.0, 1020.0, 1030.0, 1040.0, 1035.0]
SMLL7 = [500.0, 510.0, 495.0, 520.0, 525.0, 535.0, 540.0]
FATOR7 = [NAN, 0.010000000000000009, -0.01951077460687245, 0.03050505050505059,
          -0.00018853695324283493, 0.009338881183541314, 0.014153486700215545]


def _small(rets_acao=None, smll=SMLL7, exp_pregoes=5, exp_min=4) -> np.ndarray:
    """exposicao_small por posição (7 pregões). `rets_acao` padrão = 2 × fator a partir da posição 1."""
    rets = [2 * f for f in FATOR7[1:]] if rets_acao is None else rets_acao
    precos = pd.concat([
        precos_de("AAAA3", CAL7, serie_por_retornos(100.0, rets)),
        precos_de("IBOV", CAL7, IBOV7),
        precos_de("USDBRL", CAL7, [5.0] * 7),
        precos_de("BRENT", CAL7, [70.0] * 7),
    ], ignore_index=True)
    serie = None if smll is None else pd.Series(smll, index=fatos_precos.indice_pregoes(CAL7), dtype=float)
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(CAL7), columns=["AAAA3"])
    params = replace(var._params(), exposicao_pregoes=exp_pregoes, exposicao_minimo=exp_min)
    res = variaveis_de_preco(precos, CAL7, ["AAAA3"], mascara, {"AAAA3": "S1"}, {"AAAA3": "1"},
                             params, var._params_precos(), smll=serie)
    return res["exposicao_small"]["AAAA3"].to_numpy()


def test_exposicao_small_base():
    obtido = _small()
    assert np.isnan(obtido[0:4]).all()
    assert obtido[4] == pytest.approx(-0.00037707390648566996, abs=1e-12)
    assert obtido[5] == pytest.approx(0.018677762367082632, abs=1e-12)
    assert obtido[6] == pytest.approx(0.028306973400431097, abs=1e-12)


def test_exposicao_small_smll_vazio_na_6_so_nela():
    base = _small()
    smll = list(SMLL7)
    smll[6] = None
    obtido = _small(smll=smll)
    assert obtido[4] == pytest.approx(base[4], abs=1e-12)
    assert obtido[5] == pytest.approx(base[5], abs=1e-12)
    assert np.isnan(obtido[6])


def test_exposicao_small_smll_vazio_na_3_com_minimo_3_sem_preencher():
    smll = list(SMLL7)
    smll[3] = None
    obtido = _small(smll=smll, exp_min=3)
    assert np.isnan(obtido[0:5]).all()
    assert obtido[5] == pytest.approx(0.01867776236708263, abs=1e-12)
    assert obtido[6] == pytest.approx(0.02830697340043109, abs=1e-12)


def test_exposicao_small_retorno_de_200_por_cento_na_3_e_suspeito_so_nela():
    rets = [2 * f for f in FATOR7[1:]]
    rets[2] = 2.0  # retorno que entra na posição 3
    obtido = _small(rets_acao=rets, exp_pregoes=6, exp_min=4)
    assert np.isnan(obtido[0:5]).all()
    assert obtido[5] == pytest.approx(0.018677762367082625, abs=1e-12)
    assert obtido[6] == pytest.approx(0.028306973400431087, abs=1e-12)


def test_exposicao_small_sem_smll_e_tudo_nan():
    assert np.isnan(_small(smll=None)).all()


def test_serie_smll_sem_smll_e_tudo_nan():
    vazio = serie_smll(indices_de([]), CAL7)
    so_cdi = serie_smll(indices_de([("2025-01-02", "CDI", 10.0)]), CAL7)
    assert vazio.isna().all() and len(vazio) == len(CAL7)
    assert so_cdi.isna().all() and len(so_cdi) == len(CAL7)
