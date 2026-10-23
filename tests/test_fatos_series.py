"""Testes das séries base 100 (processamento/fatos/series.py; plano da etapa 7, Fase 1).

Casos da seção 12 (Fase 1) e gabarito da seção 7 do plano. Dados escritos à mão ou pelas fábricas.
Nenhum teste usa banco ou rede.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, indices_de, precos_de, pregoes_uteis
from processamento.fatos.indices import rentabilidade_cdi, rentabilidade_ipca
from processamento.fatos.precos import INDISPONIVEL, OK, grade_de_precos
from processamento.fatos.series import (
    ANTES_DO_INICIO,
    indice_base_100,
    indice_cdi,
    indice_ipca,
    indice_pontos,
    indice_setor,
)

CAL4 = [date(2025, 10, 16), date(2025, 10, 17), date(2025, 10, 20), date(2025, 10, 21)]
CAL5 = [date(2025, 8, 29), date(2025, 9, 1), date(2025, 9, 30), date(2025, 10, 1), date(2025, 11, 3)]
NAN = float("nan")

# Gabarito do setor (plano, seção 7, exemplo com 3 empresas).
SETOR_S = [100.0, 100.66666666666666, 100.16333333333331, 100.66414999999996, 102.67743299999997]
PREFIXO = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)]


def _g_aj(precos: pd.DataFrame, cal: list, tickers: list[str]) -> pd.DataFrame:
    return grade_de_precos(precos, cal, "fechamento_ajustado", tickers)


def _precos_setor_s() -> pd.DataFrame:
    """AAAA3, BBBB3, CCCC3 (empresa 3) e CCCC4 (mesma empresa, começa no dia 3); buracos da seção 7."""
    return pd.concat([
        precos_de("AAAA3", PREFIXO, [10.0, 10.5, 10.29, 10.4958, 10.600758]),
        precos_de("BBBB3", PREFIXO, [20.0, 19.0, None, 19.0, 19.38]),
        precos_de("CCCC3", PREFIXO, [50.0, 51.0, 51.51, 50.9949, 52.524747]),
        precos_de("CCCC4", PREFIXO, [None, None, None, 30.0, 30.9]),
    ])


def _cadastro_setor_s(extra: list | None = None) -> pd.DataFrame:
    linhas = [
        ("AAAA3", "1", "S", "ON"),
        ("BBBB3", "2", "S", "ON"),
        ("CCCC3", "3", "S", "ON"),
        ("CCCC4", "3", "S", "PN"),
    ]
    return cadastro_de(linhas + (extra or []))


def test_base_100_usa_o_primeiro_valor_e_marca_antes_e_indisponivel():
    idx = pd.DatetimeIndex(pd.to_datetime(PREFIXO))
    g = pd.DataFrame({"X": [NAN, 10.0, 11.0, NAN, 12.1], "Y": [NAN] * 5}, index=idx)
    res = indice_base_100(g)
    assert list(res.status["X"]) == [ANTES_DO_INICIO, OK, OK, INDISPONIVEL, OK]
    assert res.valor["X"].iloc[1] == pytest.approx(100.0, abs=1e-9)
    assert res.valor["X"].iloc[2] == pytest.approx(110.0, abs=1e-9)
    assert res.valor["X"].iloc[4] == pytest.approx(121.0, abs=1e-9)
    assert pd.isna(res.valor["X"].iloc[0]) and pd.isna(res.valor["X"].iloc[3])
    assert list(res.status["Y"]) == [ANTES_DO_INICIO] * 5
    assert res.valor["Y"].isna().all()


def test_pontos_idiv_em_base_100_e_pontos_com_nan_antes():
    indices = indices_de([("2025-10-20", "IDIV", 1000.0), ("2025-10-21", "IDIV", 1010.0)])
    base, pontos = indice_pontos(indices, CAL4)
    assert list(base.status["IDIV"]) == [ANTES_DO_INICIO, ANTES_DO_INICIO, OK, OK]
    assert base.valor["IDIV"].iloc[2] == pytest.approx(100.0, abs=1e-9)
    assert base.valor["IDIV"].iloc[3] == pytest.approx(101.0, abs=1e-9)
    assert pontos["IDIV"].iloc[2] == pytest.approx(1000.0, abs=1e-9)
    assert pontos["IDIV"].iloc[3] == pytest.approx(1010.0, abs=1e-9)
    assert pd.isna(pontos["IDIV"].iloc[0]) and pd.isna(pontos["IDIV"].iloc[1])
    assert set(base.status["SMLL"]) == {ANTES_DO_INICIO}
    assert set(base.status["IFIX"]) == {ANTES_DO_INICIO}


def test_cdi_em_base_100_e_consistente_com_a_rentabilidade_do_resumo():
    indices = indices_de([
        ("2025-10-16", "CDI", 0.05), ("2025-10-17", "CDI", 0.04),
        ("2025-10-20", "CDI", 0.05), ("2025-10-21", "CDI", 0.06),
    ])
    g = indice_cdi(indices, CAL4)
    esperado = [100.0, 100.05, 100.09002, 100.14006501]
    assert list(g.status["CDI"]) == [OK] * 4
    assert g.valor["CDI"].tolist() == pytest.approx(esperado, abs=1e-9)
    # nível(d)/nível(d-1) − 1 em 10-21 = rentabilidade de 1 pregão do resumo (taxa de 10-20)
    r = rentabilidade_cdi(indices, CAL4, 1).valor["CDI"].iloc[3]
    assert r == pytest.approx(0.0005, abs=1e-12)
    assert g.valor["CDI"].iloc[3] / g.valor["CDI"].iloc[2] - 1 == pytest.approx(r, abs=1e-12)


def test_cdi_sem_a_taxa_de_1017_fica_indisponivel_depois_dela():
    indices = indices_de([
        ("2025-10-16", "CDI", 0.05), ("2025-10-20", "CDI", 0.05), ("2025-10-21", "CDI", 0.06),
    ])
    g = indice_cdi(indices, CAL4)
    assert list(g.status["CDI"]) == [OK, OK, INDISPONIVEL, INDISPONIVEL]
    assert g.valor["CDI"].iloc[0] == pytest.approx(100.0, abs=1e-9)
    assert g.valor["CDI"].iloc[1] == pytest.approx(100.05, abs=1e-9)
    assert g.valor["CDI"].iloc[2:].isna().all()


def test_cdi_que_comeca_depois_do_cal_fica_antes_do_inicio():
    indices = indices_de([("2025-10-17", "CDI", 0.04), ("2025-10-20", "CDI", 0.05)])
    g = indice_cdi(indices, CAL4)
    assert list(g.status["CDI"]) == [ANTES_DO_INICIO, OK, OK, OK]
    assert g.valor["CDI"].iloc[1] == pytest.approx(100.0, abs=1e-9)
    assert g.valor["CDI"].iloc[2] == pytest.approx(100.04, abs=1e-9)


def test_ipca_em_base_100_e_consistente_com_a_rentabilidade_do_resumo():
    indices = indices_de([
        ("2025-07-01", "IPCA", 0.26), ("2025-08-01", "IPCA", 0.50), ("2025-09-01", "IPCA", 1.00),
    ])
    g = indice_ipca(indices, CAL5)
    assert list(g.status["IPCA"]) == [OK] * 5
    assert g.valor["IPCA"].tolist() == pytest.approx([100.0, 100.5, 100.5, 101.505, 101.505], abs=1e-9)
    r = rentabilidade_ipca(indices, CAL5, 4).valor["IPCA"].iloc[4]
    assert r == pytest.approx(0.01505, abs=1e-12)
    assert g.valor["IPCA"].iloc[4] / g.valor["IPCA"].iloc[0] - 1 == pytest.approx(r, abs=1e-12)


def test_ipca_sem_o_mes_de_agosto_fica_indisponivel_a_partir_de_outubro():
    indices = indices_de([("2025-07-01", "IPCA", 0.26), ("2025-09-01", "IPCA", 1.00)])
    g = indice_ipca(indices, CAL5)
    assert list(g.status["IPCA"]) == [OK, OK, OK, INDISPONIVEL, INDISPONIVEL]
    assert g.valor["IPCA"].iloc[:3].tolist() == pytest.approx([100.0, 100.0, 100.0], abs=1e-9)
    assert g.valor["IPCA"].iloc[3:].isna().all()


def test_ipca_so_com_agosto_comeca_em_setembro():
    indices = indices_de([("2025-08-01", "IPCA", 0.50)])
    g = indice_ipca(indices, CAL5)
    assert list(g.status["IPCA"]) == [ANTES_DO_INICIO, OK, OK, OK, OK]
    assert g.valor["IPCA"].iloc[1] == pytest.approx(100.0, abs=1e-9)


def test_setor_exemplo_da_secao_7_com_media_por_empresa():
    precos = _precos_setor_s()
    cadastro = _cadastro_setor_s()
    g_aj = _g_aj(precos, PREFIXO,["AAAA3", "BBBB3", "CCCC3", "CCCC4"])
    g, n = indice_setor(g_aj, cadastro, ["AAAA3", "BBBB3", "CCCC3", "CCCC4"])
    assert list(g.valor.columns) == ["SETOR:S"]
    assert g.valor["SETOR:S"].tolist() == pytest.approx(SETOR_S, abs=1e-9)
    assert list(g.status["SETOR:S"]) == [OK] * 5
    assert n["SETOR:S"].tolist() == [0, 3, 2, 2, 3]
    # média por ação (alternativa rejeitada) daria 102.929093375 no último dia
    assert abs(g.valor["SETOR:S"].iloc[4] - 102.929093375) > 1e-3


def test_setor_com_uma_acao_e_buraco_de_preco():
    precos = precos_de("ZZZZ3", PREFIXO, [10.0, 11.0, None, 12.1, 12.1])
    cadastro = cadastro_de([("ZZZZ3", "9", "Z", "ON")])
    g_aj = _g_aj(precos, PREFIXO,["ZZZZ3"])
    g, n = indice_setor(g_aj, cadastro, ["ZZZZ3"])
    valores = g.valor["SETOR:Z"].tolist()
    assert valores[0] == pytest.approx(100.0, abs=1e-9)
    assert valores[1] == pytest.approx(110.0, abs=1e-9)
    assert pd.isna(valores[2]) and pd.isna(valores[3])
    assert valores[4] == pytest.approx(110.0, abs=1e-9)
    assert list(g.status["SETOR:Z"]) == [OK, OK, INDISPONIVEL, INDISPONIVEL, OK]
    assert n["SETOR:Z"].tolist() == [0, 1, 0, 0, 1]


def test_bdr_fica_fora_do_setor_e_bdr_sozinho_nao_gera_coluna():
    precos = pd.concat([
        _precos_setor_s(),
        precos_de("BDRX34", PREFIXO, [1.0, 100.0, 1.0, 100.0, 1.0]),
        precos_de("BDRY34", PREFIXO, [1.0, 100.0, 1.0, 100.0, 1.0]),
    ])
    cadastro = _cadastro_setor_s(extra=[
        ("BDRX34", "5", "S", "BDR"),
        ("BDRY34", "6", "Q", "BDR"),
    ])
    tickers = ["AAAA3", "BBBB3", "CCCC3", "CCCC4", "BDRX34", "BDRY34"]
    g_aj = _g_aj(precos, PREFIXO,tickers)
    pares = ["AAAA3", "BBBB3", "CCCC3", "CCCC4"]  # como pares_do_painel: sem BDR
    g, n = indice_setor(g_aj, cadastro, pares)
    assert list(g.valor.columns) == ["SETOR:S"]
    assert g.valor["SETOR:S"].tolist() == pytest.approx(SETOR_S, abs=1e-9)
    assert n["SETOR:S"].tolist() == [0, 3, 2, 2, 3]


def test_ticker_sem_setor_nao_gera_coluna_nem_entra_em_setor():
    precos = pd.concat([_precos_setor_s(), precos_de("XXXX3", PREFIXO, [5.0, 6.0, 7.0, 8.0, 9.0])])
    cadastro = _cadastro_setor_s(extra=[("XXXX3", "7", None, "ON")])
    tickers = ["AAAA3", "BBBB3", "CCCC3", "CCCC4", "XXXX3"]
    g_aj = _g_aj(precos, PREFIXO,tickers)
    pares = tickers
    g, n = indice_setor(g_aj, cadastro, pares)
    assert list(g.valor.columns) == ["SETOR:S"]
    assert g.valor["SETOR:S"].tolist() == pytest.approx(SETOR_S, abs=1e-9)
    assert n["SETOR:S"].tolist() == [0, 3, 2, 2, 3]


def test_setor_sem_nenhum_preco_nao_e_emitido():
    precos = _precos_setor_s()
    cadastro = _cadastro_setor_s(extra=[("ITUB4", "8", "Financeiro", "ON")])
    tickers = ["AAAA3", "BBBB3", "CCCC3", "CCCC4", "ITUB4"]
    g_aj = _g_aj(precos, PREFIXO,tickers)
    g, _ = indice_setor(g_aj, cadastro, tickers)
    assert list(g.valor.columns) == ["SETOR:S"]


def test_setor_no_dia_nao_depende_dos_dias_seguintes():
    precos = _precos_setor_s()
    cadastro = _cadastro_setor_s()
    tickers = ["AAAA3", "BBBB3", "CCCC3", "CCCC4"]
    g_aj = _g_aj(precos, PREFIXO,tickers)
    completo, n_completo = indice_setor(g_aj, cadastro, tickers)
    corte, n_corte = indice_setor(g_aj.iloc[:3], cadastro, tickers)
    assert corte.valor["SETOR:S"].tolist()[:3] == pytest.approx(completo.valor["SETOR:S"].tolist()[:3], abs=1e-12)
    assert n_corte["SETOR:S"].tolist() == n_completo["SETOR:S"].tolist()[:3]
