"""Testes das séries base 100 (processamento/fatos/series.py; plano da etapa 7, Fase 1).

Casos da seção 12 (Fase 1) e gabarito da seção 7 do plano. Dados escritos à mão ou pelas fábricas.
Nenhum teste usa banco ou rede.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, indices_de, precos_de, pregoes_uteis, serie_por_retornos
from processamento.fatos.indices import rentabilidade_cdi, rentabilidade_ipca
from processamento.fatos.precos import HIST, INDISPONIVEL, OK, grade_de_precos, retornos_suspeitos
from processamento.fatos.series import (
    ANTES_DO_INICIO,
    indice_base_100,
    indice_cdi,
    indice_ipca,
    indice_pontos,
    indice_setor,
    indice_setor_sem_empresa,
    rentabilidade_setor_sem_empresa,
    serie_selic_meta,
)

CAL4 =[date(2025, 10, 16), date(2025, 10, 17), date(2025, 10, 20), date(2025, 10, 21)]
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


def test_setor_sem_empresa_exemplo_caso_2a_membros_bdr_e_ticker_sem_setor():
    precos = pd.concat([
        _precos_setor_s(),
        precos_de("BDRX34", PREFIXO, [1.0, 100.0, 1.0, 100.0, 1.0]),
        precos_de("XXXX3", PREFIXO, [5.0, 6.0, 7.0, 8.0, 9.0]),
        precos_de("ZZZZ3", PREFIXO, [10.0, 11.0, None, 12.1, 12.1]),
    ])
    cadastro = _cadastro_setor_s(extra=[("BDRX34", "5", "S", "BDR"), ("XXXX3", "7", None, "ON"), ("ZZZZ3", "9", "Z", "ON")])
    tickers = ["AAAA3", "BBBB3", "BDRX34", "CCCC3", "CCCC4", "XXXX3", "ZZZZ3"]
    pares = ["AAAA3", "BBBB3", "CCCC3", "CCCC4", "XXXX3", "ZZZZ3"]
    g_aj = _g_aj(precos, PREFIXO, tickers)
    g, n = indice_setor_sem_empresa(g_aj, cadastro, pares, tickers, "empresa")
    assert list(g.valor.columns) == ["SETOR_SEM:AAAA3", "SETOR_SEM:BBBB3", "SETOR_SEM:BDRX34",
                                     "SETOR_SEM:CCCC3", "SETOR_SEM:CCCC4"]
    esperado = {
        "SETOR_SEM:AAAA3": ([100.0, 98.5, 99.485, 98.49015000000001, 100.95240375], [0, 2, 1, 1, 2]),
        "SETOR_SEM:BBBB3": ([100.0, 103.50000000000001, 102.9825, 103.49741250000001, 105.56736075], [0, 2, 2, 2, 2]),
        "SETOR_SEM:BDRX34": ([100.0, 100.66666666666666, 100.16333333333331, 100.66414999999999, 102.677433],
                             [0, 3, 2, 2, 3]),
        "SETOR_SEM:CCCC3": ([100.0, 100.0, 97.99999999999999, 99.96, 101.4594], [0, 2, 1, 1, 2]),
        "SETOR_SEM:CCCC4": ([100.0, 100.0, 97.99999999999999, 99.96, 101.4594], [0, 2, 1, 1, 2]),
    }
    for col, (valores, contagem) in esperado.items():
        assert g.valor[col].tolist() == pytest.approx(valores, abs=1e-9), col
        assert list(g.status[col]) == [OK] * 5, col
        assert n[col].tolist() == contagem, col
    # modo "acao": a CCCC3 entra no setor da CCCC4
    g_acao, n_acao = indice_setor_sem_empresa(g_aj, cadastro, pares, tickers, "acao")
    assert g_acao.valor["SETOR_SEM:CCCC4"].tolist() == pytest.approx(
        [100.0, 100.66666666666666, 100.16333333333331, 100.66414999999999, 102.677433], abs=1e-9)
    assert n_acao["SETOR_SEM:CCCC4"].tolist() == [0, 3, 2, 2, 3]


def test_setor_sem_empresa_dia_sem_outra_empresa_caso_2b():
    precos = pd.concat([precos_de("YYYY3", PREFIXO, [10.0, 11.0, None, 12.1, 12.1]),
                        precos_de("ZZZZ3", PREFIXO, [5.0] * 5)])
    cadastro = cadastro_de([("YYYY3", "8", "Z", "ON"), ("ZZZZ3", "9", "Z", "ON")])
    tickers = ["YYYY3", "ZZZZ3"]
    g_aj = _g_aj(precos, PREFIXO, tickers)
    g, n = indice_setor_sem_empresa(g_aj, cadastro, tickers, tickers, "empresa")
    zz = g.valor["SETOR_SEM:ZZZZ3"]
    assert zz.iloc[0] == pytest.approx(100.0, abs=1e-9)
    assert zz.iloc[1] == pytest.approx(110.0, abs=1e-9)
    assert pd.isna(zz.iloc[2]) and pd.isna(zz.iloc[3])
    assert zz.iloc[4] == pytest.approx(110.0, abs=1e-9)
    assert list(g.status["SETOR_SEM:ZZZZ3"]) == [OK, OK, INDISPONIVEL, INDISPONIVEL, OK]
    assert n["SETOR_SEM:ZZZZ3"].tolist() == [0, 1, 0, 0, 1]
    assert g.valor["SETOR_SEM:YYYY3"].tolist() == pytest.approx([100.0] * 5, abs=1e-9)
    assert list(g.status["SETOR_SEM:YYYY3"]) == [OK] * 5
    assert n["SETOR_SEM:YYYY3"].tolist() == [0, 1, 1, 1, 1]
    r = rentabilidade_setor_sem_empresa(g_aj, cadastro, tickers, tickers, {"d1": 1}, "empresa")["d1"]
    assert pd.isna(r.valor["ZZZZ3"].iloc[0])
    assert r.valor["ZZZZ3"].iloc[1] == pytest.approx(0.10000000000000009, abs=1e-9)
    assert pd.isna(r.valor["ZZZZ3"].iloc[2]) and pd.isna(r.valor["ZZZZ3"].iloc[3])
    assert r.valor["ZZZZ3"].iloc[4] == pytest.approx(0.0, abs=1e-9)
    assert list(r.status["ZZZZ3"]) == [HIST, OK, INDISPONIVEL, INDISPONIVEL, OK]


def _cenario_suspeitos_2c():
    cal = pregoes_uteis(8, "2026-04-06")   # 06, 07, 08, 09, 10, 13, 14 e 15/04/2026
    precos = pd.concat([
        precos_de("AZUL3", cal, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105]),
        precos_de("EMBR3", cal, serie_por_retornos(50.0, [0.02, -0.01, 0.02, -0.01, 0.01, 0.0, 0.01])),
        precos_de("WEGE3", cal, serie_por_retornos(40.0, [0.0, 0.01, -0.02, 0.03, 0.0, 0.01, -0.01])),
        precos_de("RAIL3", cal, serie_por_retornos(20.0, [0.03, 0.0, -0.01, 0.02, 0.01, -0.02, 0.0])),
        precos_de("SOLO3", cal, [10.0] * 8),
    ])
    cadastro = cadastro_de([("AZUL3", "1", "BI", "ON"), ("EMBR3", "2", "BI", "ON"), ("WEGE3", "3", "BI", "ON"),
                            ("RAIL3", "4", "BI", "ON"), ("SOLO3", "5", "Y", "ON"), ("NOPX3", "6", "Y", "ON")])
    tickers = ["AZUL3", "EMBR3", "NOPX3", "RAIL3", "SOLO3", "WEGE3"]
    g_aj = _g_aj(precos, cal, tickers)
    return g_aj, cadastro, tickers


def test_setor_sem_empresa_retornos_suspeitos_caso_2c():
    g_aj, cadastro, tickers = _cenario_suspeitos_2c()
    susp = retornos_suspeitos(g_aj, -0.75, 1.0)
    g, n = indice_setor_sem_empresa(g_aj, cadastro, tickers, tickers, "empresa", suspeitos=susp)
    assert list(g.valor.columns) == ["SETOR_SEM:AZUL3", "SETOR_SEM:EMBR3", "SETOR_SEM:NOPX3",
                                     "SETOR_SEM:RAIL3", "SETOR_SEM:WEGE3"]
    assert g.valor["SETOR_SEM:EMBR3"].tolist() == pytest.approx(
        [100.0, 101.66666666666666, 102.17499999999998, 102.85616666666664, 105.42757083333329,
         105.77899606944442, 105.77899606944442, 105.77899606944442], abs=1e-9)
    assert n["SETOR_SEM:EMBR3"].tolist() == [0, 3, 2, 3, 2, 3, 3, 3]
    assert g.valor["SETOR_SEM:AZUL3"].tolist() == pytest.approx(
        [100.0, 101.66666666666666, 101.66666666666666, 101.32777777777777, 102.67881481481481,
         103.36334024691357, 103.01879577942385, 103.01879577942385], abs=1e-9)
    assert n["SETOR_SEM:AZUL3"].tolist() == [0, 3, 3, 3, 3, 3, 3, 3]
    # sem os suspeitos, a série da EMBR3 explode (a AZUL3 entra com o preço errado)
    sem, _ = indice_setor_sem_empresa(g_aj, cadastro, tickers, tickers, "empresa")
    assert sem.valor["SETOR_SEM:EMBR3"].iloc[2] > 600000
    r = rentabilidade_setor_sem_empresa(g_aj, cadastro, tickers, tickers, {"d1": 1, "m1": 3, "m6": 5},
                                        "empresa", suspeitos=susp)
    assert pd.isna(r["d1"].valor["EMBR3"].iloc[0])
    assert r["d1"].valor["EMBR3"].tolist()[1:] == pytest.approx(
        [0.016666666666666607, 0.004999999999999893, 0.006666666666666599, 0.02499999999999991,
         0.0033333333333334103, 0.0, 0.0], abs=1e-9)
    assert list(r["d1"].status["EMBR3"]) == [HIST] + [OK] * 7
    assert pd.isna(r["m1"].valor["EMBR3"].iloc[:3]).all()
    assert r["m1"].valor["EMBR3"].iloc[3:].tolist() == pytest.approx(
        [0.028561666666666374, 0.03699249999999976, 0.03527277777777771, 0.028416666666666757,
         0.0033333333333334103], abs=1e-9)
    assert list(r["m1"].status["EMBR3"]) == [HIST] * 3 + [OK] * 5
    assert pd.isna(r["m6"].valor["EMBR3"].iloc[:5]).all()
    assert r["m6"].valor["EMBR3"].iloc[5:].tolist() == pytest.approx(
        [0.05778996069444409, 0.04044914166666658, 0.03527277777777771], abs=1e-9)
    assert list(r["m6"].status["EMBR3"]) == [HIST] * 5 + [OK] * 3
    assert list(r["d1"].status["SOLO3"])[-1] == HIST
    assert list(r["d1"].status["NOPX3"])[-1] == OK


def test_rentabilidade_setor_sem_empresa_e_razao_da_serie_caso_2d():
    g_aj, cadastro, tickers = _cenario_suspeitos_2c()
    susp = retornos_suspeitos(g_aj, -0.75, 1.0)
    g, _ = indice_setor_sem_empresa(g_aj, cadastro, tickers, tickers, "empresa", suspeitos=susp)
    r = rentabilidade_setor_sem_empresa(g_aj, cadastro, tickers, tickers, {"m1": 3, "m6": 5}, "empresa",
                                        suspeitos=susp)
    for tk in ["AZUL3", "EMBR3", "RAIL3", "WEGE3"]:
        col = f"SETOR_SEM:{tk}"
        assert r["m1"].valor[tk].iloc[-1] == pytest.approx(g.valor[col].iloc[-1] / g.valor[col].iloc[-4] - 1)
        assert r["m6"].valor[tk].iloc[-1] == pytest.approx(g.valor[col].iloc[-1] / g.valor[col].iloc[-6] - 1)


def test_setor_sem_empresa_no_dia_nao_depende_dos_dias_seguintes_caso_2e():
    precos = pd.concat([_precos_setor_s(), precos_de("XXXX3", PREFIXO, [5.0, 6.0, 7.0, 8.0, 9.0])])
    cadastro = _cadastro_setor_s(extra=[("XXXX3", "7", None, "ON")])
    tickers = ["AAAA3", "BBBB3", "CCCC3", "CCCC4", "XXXX3"]
    g_aj = _g_aj(precos, PREFIXO, tickers)
    completo, n_completo = indice_setor_sem_empresa(g_aj, cadastro, tickers, tickers, "empresa")
    corte, n_corte = indice_setor_sem_empresa(g_aj.iloc[:3], cadastro, tickers, tickers, "empresa")
    col = "SETOR_SEM:AAAA3"
    assert corte.valor[col].tolist()[:3] == pytest.approx(completo.valor[col].tolist()[:3], abs=1e-12)
    assert n_corte[col].tolist() == n_completo[col].tolist()[:3]


# --- serie_selic_meta (série SELIC da saída: taxa-meta anual em fração, nunca acumulada) -----

CAL_SELIC = [date(2025, 10, 20), date(2025, 10, 21), date(2025, 10, 22), date(2025, 10, 23), date(2025, 10, 24)]


def test_serie_selic_meta_ultimo_valor_ate_o_pregao_e_antes_do_primeiro_e_antes_do_inicio():
    ind = indices_de([("2025-10-21", "SELIC", 15.0), ("2025-10-23", "SELIC", 14.75)])
    g = serie_selic_meta(ind, CAL_SELIC, 5)
    assert g.status["SELIC"].tolist() == [ANTES_DO_INICIO, OK, OK, OK, OK]
    assert g.valor["SELIC"].iloc[1:].tolist() == pytest.approx([0.15, 0.15, 0.1475, 0.1475])
    assert g.valor["SELIC"].iloc[0] != g.valor["SELIC"].iloc[0]   # NaN antes do 1º valor


def test_serie_selic_meta_velha_demais_pela_defasagem_fica_indisponivel():
    ind = indices_de([("2025-10-20", "SELIC", 15.0)])
    g = serie_selic_meta(ind, CAL_SELIC, 2)
    assert g.status["SELIC"].tolist() == [OK, OK, OK, INDISPONIVEL, INDISPONIVEL]
    assert g.valor["SELIC"].iloc[:3].tolist() == pytest.approx([0.15, 0.15, 0.15])
    assert g.valor["SELIC"].iloc[3:].isna().all()
