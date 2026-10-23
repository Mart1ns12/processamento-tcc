"""Testes das variáveis de preço do experimento (plano da etapa 5, fase 5).

Séries curtas são escritas à mão; o mundo da consistência sai de tests/fabrica_precos.py.
Nenhum teste usa banco ou rede. Valores do gabarito do plano; onde o plano dá decimal
arredondado, o teste usa a fração exata (mesmo número, sem o arredondamento).
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import pregoes_uteis, precos_de, serie_por_retornos
from processamento.experimento.parametros import ParametrosExperimento
from processamento.experimento.variaveis import (
    amplitude,
    exposicao,
    extremos,
    ret_vs_setor,
    salto_abertura,
    variaveis_de_preco,
)
from processamento.fatos import precos as fatos_precos
from processamento.fatos.precos import ParametrosPrecos

_NOMES = {
    "ret_1d", "ret_5d", "ret_20d", "volatilidade_20d", "beta", "volume_relativo", "salto_abertura",
    "dist_max_52s", "dist_min_52s", "amplitude", "ret_vs_setor", "exposicao_dolar", "exposicao_petroleo",
}


def _grade(valores: list, datas: list, ticker: str = "HHHH3") -> pd.DataFrame:
    """Grade pregão × ticker de uma coluna só (NaN onde a lista tem None)."""
    idx = pd.DatetimeIndex(pd.to_datetime(datas), name="data")
    dados = [np.nan if v is None else float(v) for v in valores]
    return pd.DataFrame({ticker: dados}, index=idx)


def _params() -> ParametrosExperimento:
    return ParametrosExperimento(
        retornos={"ret_1d": 1, "ret_5d": 5, "ret_20d": 20},
        exposicao_pregoes=120,
        exposicao_minimo=60,
        extremos_pregoes=252,
        extremos_minimo=120,
        mudanca_tom_pregoes=30,
        mudanca_tom_minimo=5,
        sem_horario_na_noite=True,
        inicio_janela="manha",
        deduplicar_titulo=True,
        origens_principais=("cvm_ipe",),
        tipos_principais=("reportagem",),
        papeis_principais=("protagonista", "citada_com_fato"),
    )


def _params_precos() -> ParametrosPrecos:
    return ParametrosPrecos(
        janelas={"d1": 1},
        volume_pregoes=20,
        volatilidade_retornos=20,
        beta_pregoes=252,
        beta_minimo=120,
        setor_minimo=3,
        setor_excluir="empresa",
    )


# --- 1. salto de abertura -------------------------------------------------------------------


_DATAS2 = ["2026-06-18", "2026-06-19"]


def test_salto_usa_abertura_ajustada_contra_o_anterior_ajustado():
    # abertura·aj/fech = 19,1·19,2/19,2 = 19,1; contra aj do pregão anterior (19) → +0,0052631...
    g_ab = _grade([20, 19.1], _DATAS2)
    g_fech = _grade([20, 19.2], _DATAS2)
    g_aj = _grade([19, 19.2], _DATAS2)
    salto = salto_abertura(g_ab, g_aj, g_fech)
    assert salto.loc["2026-06-19", "HHHH3"] == pytest.approx(0.0052631578947368585, abs=1e-12)
    assert np.isnan(salto.loc["2026-06-18", "HHHH3"])


def test_salto_sem_aj_no_pregao_anterior_e_nan():
    g_ab = _grade([20, 19.1], _DATAS2)
    g_fech = _grade([20, 19.2], _DATAS2)
    g_aj = _grade([None, 19.2], _DATAS2)
    assert np.isnan(salto_abertura(g_ab, g_aj, g_fech).loc["2026-06-19", "HHHH3"])


def test_salto_fechamento_zero_e_nan():
    g_ab = _grade([20, 19.1], _DATAS2)
    g_fech = _grade([20, 0], _DATAS2)
    g_aj = _grade([19, 19.2], _DATAS2)
    assert np.isnan(salto_abertura(g_ab, g_aj, g_fech).loc["2026-06-19", "HHHH3"])


def test_salto_pregao_anterior_e_estrito_sem_preencher():
    # Pregão do meio sem aj: o terceiro compara com o do meio (vazio) → NaN, não com o primeiro.
    datas = ["2026-06-18", "2026-06-19", "2026-06-22"]
    g_ab = _grade([20, 19.1, 19.1], datas)
    g_fech = _grade([20, 19.2, 19.2], datas)
    g_aj = _grade([19, None, 19.2], datas)
    assert np.isnan(salto_abertura(g_ab, g_aj, g_fech).loc["2026-06-22", "HHHH3"])


# --- 2. extremos ----------------------------------------------------------------------------


def test_extremos_janela_5_minimo_3():
    datas = pregoes_uteis(7, "2026-06-15")
    g = _grade([100, 120, 90, 110, 100, 105, 95], datas)
    dist_max, dist_min = extremos(g, 5, 3)
    # Frações exatas do gabarito (ex.: 110/120 − 1 = −1/12 = −0,0833333...).
    esperado_max = [np.nan, np.nan, 90 / 120 - 1, 110 / 120 - 1, 100 / 120 - 1, 105 / 120 - 1, 95 / 110 - 1]
    esperado_min = [np.nan, np.nan, 0.0, 110 / 90 - 1, 100 / 90 - 1, 105 / 90 - 1, 95 / 90 - 1]
    np.testing.assert_allclose(dist_max["HHHH3"], esperado_max, rtol=0, atol=1e-12)
    np.testing.assert_allclose(dist_min["HHHH3"], esperado_min, rtol=0, atol=1e-12)


def test_extremos_nao_cabe_na_janela_e_nan():
    # Com 2 valores e mínimo 3 nada sai; a janela inclui o próprio t.
    g = _grade([100, 120], ["2026-06-18", "2026-06-19"])
    dist_max, dist_min = extremos(g, 5, 3)
    assert dist_max["HHHH3"].isna().all() and dist_min["HHHH3"].isna().all()


# --- 3. amplitude ---------------------------------------------------------------------------


def test_amplitude_casos_do_gabarito():
    datas = pregoes_uteis(4, "2026-06-15")
    g_max = _grade([21, None, 19, 21], datas)
    g_min = _grade([19, 19, 20, 19], datas)
    g_fech = _grade([20, 20, 20, 0], datas)
    obtido = amplitude(g_max, g_min, g_fech)["HHHH3"]
    np.testing.assert_allclose(obtido, [0.1, np.nan, np.nan, np.nan], rtol=0, atol=1e-12)


# --- 4. exposição ---------------------------------------------------------------------------


def test_exposicao_beta_2_sobre_o_dolar():
    datas = pregoes_uteis(6, "2026-06-15")
    usd = [5.0, 5.1, 5.0, 5.2, 5.1, 5.3]
    r_usd = [usd[i] / usd[i - 1] - 1 for i in range(1, 6)]
    acao = serie_por_retornos(100, [2 * r for r in r_usd])
    idx = pd.DatetimeIndex(pd.to_datetime(datas), name="data")
    g_aj = pd.DataFrame({"AAAA3": acao}, index=idx)
    fator = pd.Series(usd, index=idx)
    obtido = exposicao(g_aj, fator, 5, 4)["AAAA3"]
    esperado = [np.nan, np.nan, np.nan, np.nan, -0.038461538461538436, 0.0784313725490198]
    np.testing.assert_allclose(obtido, esperado, rtol=0, atol=1e-12)


def test_exposicao_fator_vazio_na_ultima_data_e_nan_so_nela():
    datas = pregoes_uteis(6, "2026-06-15")
    usd = [5.0, 5.1, 5.0, 5.2, 5.1, None]
    r_usd = [5.1 / 5.0 - 1, 5.0 / 5.1 - 1, 5.2 / 5.0 - 1, 5.1 / 5.2 - 1]
    acao = serie_por_retornos(100, [2 * r for r in r_usd] + [0.01])
    idx = pd.DatetimeIndex(pd.to_datetime(datas), name="data")
    g_aj = pd.DataFrame({"AAAA3": acao}, index=idx)
    fator = pd.Series(usd, index=idx, dtype=float)
    obtido = exposicao(g_aj, fator, 5, 4)["AAAA3"]
    assert np.isnan(obtido.iloc[-1])
    assert obtido.iloc[-2] == pytest.approx(-0.038461538461538436, abs=1e-12)


# --- 5. ret_vs_setor (modo empresa, só com a máscara) ---------------------------------------


def test_ret_vs_setor_modo_empresa_com_mascara():
    datas = ["2026-06-18", "2026-06-19"]
    tickers = ["XXXX3", "XXXX4", "YYYY3", "ZZZZ3", "VVVV3"]
    aj = pd.DataFrame(
        {
            "XXXX3": [100.0, 102.0],
            "XXXX4": [100.0, 104.0],
            "YYYY3": [100.0, 101.0],
            "ZZZZ3": [100.0, 99.0],
            "VVVV3": [100.0, 150.0],
        },
        index=pd.DatetimeIndex(pd.to_datetime(datas), name="data"),
    )
    ret = fatos_precos.retornos_diarios(aj)
    mascara = pd.DataFrame(True, index=aj.index, columns=tickers)
    mascara.loc["2026-06-19", "VVVV3"] = False
    setor_de = {t: "S1" for t in tickers}
    cnpj_de = {"XXXX3": "1", "XXXX4": "1", "YYYY3": "2", "ZZZZ3": "3", "VVVV3": "5"}

    res = ret_vs_setor(ret, mascara, setor_de, cnpj_de, "empresa").loc["2026-06-19"]
    assert res["XXXX3"] == pytest.approx(0.02, abs=1e-12)
    assert res["XXXX4"] == pytest.approx(0.04, abs=1e-12)
    assert res["YYYY3"] == pytest.approx(0.0, abs=1e-12)
    assert res["ZZZZ3"] == pytest.approx(-0.03, abs=1e-12)
    assert np.isnan(res["VVVV3"])


# --- 6. consistência com fatos/precos.py e grade completa -----------------------------------


def _mundo(n: int = 300):
    """Preços aleatórios com semente fixa: ações, IBOV, dólar e petróleo, com uma lacuna em BBBB3."""
    cal = pregoes_uteis(n, "2025-01-02")
    rng = np.random.default_rng(11)
    linhas = []
    for ticker, base in [("IBOV", 100000.0), ("USDBRL", 5.0), ("BRENT", 70.0),
                         ("AAAA3", 20.0), ("AAAA4", 30.0), ("BBBB3", 10.0)]:
        fech = base * np.cumprod(1 + rng.normal(0, 0.015, n))
        fator = 1.0 if ticker in ("IBOV", "USDBRL", "BRENT") else 0.95
        aj = fech * np.where(np.arange(n) < n // 2, fator, 1.0)
        volume = rng.integers(1000, 100000, n).astype(float)
        linhas.append(precos_de(ticker, cal, fech.tolist(), aj.tolist(), volume.tolist()))
    precos = pd.concat(linhas, ignore_index=True)
    precos = precos[~((precos["ticker"] == "BBBB3") & (precos["data"] == pd.Timestamp(cal[150])))]
    return precos, cal


def test_variaveis_de_preco_tem_as_13_grades_no_formato_do_calendario():
    precos, cal = _mundo()
    tickers = ["AAAA3", "AAAA4", "BBBB3"]
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(cal), columns=tickers)
    setor_de = {"AAAA3": "S1", "AAAA4": "S1", "BBBB3": "S1"}
    cnpj_de = {"AAAA3": "1", "AAAA4": "1", "BBBB3": "2"}
    res = variaveis_de_preco(precos, cal, tickers, mascara, setor_de, cnpj_de, _params(), _params_precos())
    assert set(res) == _NOMES
    for nome, grade in res.items():
        assert grade.shape == (len(cal), len(tickers)), nome
        assert list(grade.columns) == tickers, nome


def test_variaveis_de_preco_reusa_as_contas_do_fatos():
    precos, cal = _mundo()
    tickers = ["AAAA3", "AAAA4", "BBBB3"]
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(cal), columns=tickers)
    setor_de = {"AAAA3": "S1", "AAAA4": "S1", "BBBB3": "S1"}
    cnpj_de = {"AAAA3": "1", "AAAA4": "1", "BBBB3": "2"}
    res = variaveis_de_preco(precos, cal, tickers, mascara, setor_de, cnpj_de, _params(), _params_precos())

    g_aj = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    gv = fatos_precos.grade_de_precos(precos, cal, "volume", tickers)
    ibov = fatos_precos.grade_de_precos(precos, cal, "fechamento_ajustado", ["IBOV"])["IBOV"]

    pd.testing.assert_frame_equal(res["ret_1d"], fatos_precos.variacao(g_aj, 1).valor, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(
        res["volatilidade_20d"], fatos_precos.volatilidade(g_aj, 20).valor, rtol=1e-12, atol=1e-12
    )
    pd.testing.assert_frame_equal(
        res["volume_relativo"], fatos_precos.volume_relativo(gv, 20)[1].valor, rtol=1e-12, atol=1e-12
    )
    pd.testing.assert_frame_equal(
        res["beta"], fatos_precos.beta(g_aj, ibov, 252, 120).valor, rtol=1e-12, atol=1e-12
    )
