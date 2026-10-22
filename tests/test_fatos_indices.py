"""Testes de processamento/fatos/indices.py: CDI, IPCA e índices de referência (caso f da etapa 3).

Séries montadas com tests/fabrica_precos.py; janelas por número de pregões do calendário.
Nenhum teste usa banco ou rede.
"""

from datetime import date

import pandas as pd
import pytest

from fabrica_precos import indices_de, pregoes_uteis, precos_de
from processamento.fatos.indices import (
    INDICES,
    calcular_indices,
    cdi_dia,
    grade_de_indices,
    indices_no_dia,
    ipca_ate,
    ipca_12m,
    rentabilidade_cdi,
    rentabilidade_ipca,
)
from processamento.fatos.precos import HIST, INDISPONIVEL, OK, ParametrosPrecos, indice_pregoes

CAL3 = pregoes_uteis(3)  # 02/01, 03/01, 06/01
CAL4 = pregoes_uteis(4)  # 02/01, 03/01, 06/01, 07/01
CAL_IPCA = pregoes_uteis(120, inicio="2025-01-01")

CDI4 = [
    ("2025-01-02", "CDI", 0.05),
    ("2025-01-03", "CDI", 0.04),
    ("2025-01-06", "CDI", 0.05),
    ("2025-01-07", "CDI", 0.06),
]
CDI3 = CDI4[:3]
PONTOS = [
    ("2025-01-02", "IDIV", 1000.0),
    ("2025-01-03", "IDIV", 1010.0),
    ("2025-01-06", "IDIV", 1030.2),
]
IPCA_TAB = [
    ("2025-01-01", "IPCA", 0.50),
    ("2025-02-01", "IPCA", 1.00),
    ("2025-03-01", "IPCA", 0.20),
]
IPCA_12 = [("2025-01-01", "IPCA", 1.00)] + [
    (f"{ts:%Y-%m-%d}", "IPCA", 0.50) for ts in pd.date_range("2025-02-01", "2026-01-01", freq="MS")
]


def _vl(grade, data, coluna):
    return grade.valor.loc[pd.Timestamp(data), coluna]


def _st(grade, data, coluna):
    return grade.status.loc[pd.Timestamp(data), coluna]


def _n(cal, base, t):
    """Número de pregões de `base` até `t` (sem contar t)."""
    return cal.index(date.fromisoformat(t)) - cal.index(date.fromisoformat(base))


def _params(janelas):
    return ParametrosPrecos(
        janelas=janelas,
        volume_pregoes=20,
        volatilidade_retornos=20,
        beta_pregoes=252,
        beta_minimo=120,
        setor_minimo=3,
        setor_excluir="empresa",
    )


# --- CDI -------------------------------------------------------------------

def test_cdi_produto_das_taxas_com_data_em_base_ate_t_excluido():
    g = rentabilidade_cdi(indices_de(CDI4), CAL4, 3)
    assert _vl(g, "2025-01-07", "CDI") == pytest.approx(0.0014006500999996785, abs=1e-12)
    assert _st(g, "2025-01-07", "CDI") == OK


def test_taxa_de_t_nao_entra_no_resultado():
    ind = indices_de(CDI3 + [("2025-01-07", "CDI", 9.99)])
    g = rentabilidade_cdi(ind, CAL4, 3)
    assert _vl(g, "2025-01-07", "CDI") == pytest.approx(0.0014006500999996785, abs=1e-12)


def test_cdi_janela_de_um_pregao():
    g = rentabilidade_cdi(indices_de(CDI4), CAL4, 1)
    assert _vl(g, "2025-01-07", "CDI") == pytest.approx(0.0005, abs=1e-12)
    assert _vl(g, "2025-01-03", "CDI") == pytest.approx(0.0005, abs=1e-12)


def test_cdi_com_pregao_faltando_no_calendario_usa_as_datas_do_cdi():
    # sem 06/01 no calendário: a janela de 07/01 com n=2 ainda inclui a taxa de 06/01
    cal = [CAL4[0], CAL4[1], CAL4[3]]
    g = rentabilidade_cdi(indices_de(CDI4), cal, 2)
    assert _vl(g, "2025-01-07", "CDI") == pytest.approx(0.0014006500999996785, abs=1e-12)

    g1 = rentabilidade_cdi(indices_de(CDI4), cal, 1)
    assert _vl(g1, "2025-01-07", "CDI") == pytest.approx(0.0009001999999997956, abs=1e-12)


def test_cdi_sem_a_linha_de_um_pregao_da_janela_fica_indisponivel():
    ind = indices_de([CDI4[0], CDI4[2], CDI4[3]])  # sem 03/01
    g = rentabilidade_cdi(ind, CAL4, 3)
    assert _st(g, "2025-01-07", "CDI") == INDISPONIVEL
    assert pd.isna(_vl(g, "2025-01-07", "CDI"))

    g1 = rentabilidade_cdi(ind, CAL4, 1)
    assert _vl(g1, "2025-01-07", "CDI") == pytest.approx(0.0005, abs=1e-12)
    assert _st(g1, "2025-01-07", "CDI") == OK


def test_cdi_com_base_antes_do_primeiro_cdi_e_historico_insuficiente():
    cal = [date(2024, 12, 30), date(2024, 12, 31)] + CAL4  # 30/12, 31/12, 02/01, 03/01, 06/01, 07/01
    g = rentabilidade_cdi(indices_de(CDI4), cal, 4)
    assert _st(g, "2025-01-07", "CDI") == HIST
    assert pd.isna(_vl(g, "2025-01-07", "CDI"))


def test_cdi_dia_e_a_ultima_taxa_ate_t():
    ind = indices_de(CDI4[:2])  # só 02/01 e 03/01
    valor, status, data = cdi_dia(ind, date(2025, 1, 6))
    assert valor == pytest.approx(0.0004, abs=1e-12)
    assert status == OK
    assert data == pd.Timestamp("2025-01-03")


def test_cdi_dia_sem_linhas_fica_indisponivel():
    valor, status, data = cdi_dia(indices_de([]), date(2025, 1, 6))
    assert pd.isna(valor)
    assert status == INDISPONIVEL
    assert data is None


# --- IPCA ------------------------------------------------------------------

def test_ipca_meses_fechados_de_k_base_ate_k_t():
    # K(14/02)=jan; K(14/04)=mar; intervalo (jan, mar] = fev e mar
    g = rentabilidade_ipca(indices_de(IPCA_TAB), CAL_IPCA, _n(CAL_IPCA, "2025-02-14", "2025-04-14"))
    assert _vl(g, "2025-04-14", "IPCA") == pytest.approx(0.01202, abs=1e-12)
    assert _st(g, "2025-04-14", "IPCA") == OK


def test_ipca_intervalo_vazio_vale_zero():
    g = rentabilidade_ipca(indices_de(IPCA_TAB), CAL_IPCA, _n(CAL_IPCA, "2025-03-03", "2025-03-31"))
    assert _vl(g, "2025-03-31", "IPCA") == 0.0
    assert _st(g, "2025-03-31", "IPCA") == OK


def test_ipca_sem_mes_anterior_a_base_e_historico_insuficiente():
    g = rentabilidade_ipca(indices_de(IPCA_TAB), CAL_IPCA, _n(CAL_IPCA, "2025-01-15", "2025-04-14"))
    assert _st(g, "2025-04-14", "IPCA") == HIST
    assert pd.isna(_vl(g, "2025-04-14", "IPCA"))


def test_ipca_mes_faltando_no_meio_fica_indisponivel():
    ind = indices_de([IPCA_TAB[0], IPCA_TAB[2]])  # sem fevereiro
    g = rentabilidade_ipca(ind, CAL_IPCA, _n(CAL_IPCA, "2025-02-14", "2025-04-14"))
    assert _st(g, "2025-04-14", "IPCA") == INDISPONIVEL
    assert pd.isna(_vl(g, "2025-04-14", "IPCA"))


def test_ipca_com_mes_de_t_faltando_usa_o_ultimo_mes_conhecido():
    # sem abril: K(14/05) = mês de março, então o resultado é o mesmo de 14/04
    g = rentabilidade_ipca(indices_de(IPCA_TAB), CAL_IPCA, _n(CAL_IPCA, "2025-02-14", "2025-05-14"))
    assert _vl(g, "2025-05-14", "IPCA") == pytest.approx(0.01202, abs=1e-12)
    assert _st(g, "2025-05-14", "IPCA") == OK


def test_ipca_ate_e_o_ultimo_mes_fechado():
    ind = indices_de(IPCA_TAB)
    assert ipca_ate(ind, date(2025, 4, 14)) == "2025-03"
    assert ipca_ate(ind, date(2025, 5, 14)) == "2025-03"
    assert ipca_ate(ind, date(2025, 2, 14)) == "2025-01"
    assert ipca_ate(ind, date(2025, 1, 15)) is None


def test_ipca_ate_sem_linhas_e_none():
    assert ipca_ate(indices_de([]), date(2025, 4, 14)) is None


def test_ipca_12m_soma_os_12_meses_ate_k_t():
    ind = indices_de(IPCA_12)
    valor, status = ipca_12m(ind, date(2026, 1, 10))
    assert valor == pytest.approx(0.06695979102800331, abs=1e-12)
    assert status == OK

    valor, status = ipca_12m(ind, date(2026, 2, 10))
    assert valor == pytest.approx(0.06167781186449828, abs=1e-12)
    assert status == OK


def test_ipca_12m_com_inicio_antes_do_primeiro_mes_e_historico_insuficiente():
    valor, status = ipca_12m(indices_de(IPCA_12), date(2025, 12, 10))
    assert pd.isna(valor)
    assert status == HIST


def test_ipca_12m_com_mes_faltando_na_janela_fica_indisponivel():
    sem_jun = [linha for linha in IPCA_12 if linha[0] != "2025-06-01"]
    valor, status = ipca_12m(indices_de(sem_jun), date(2026, 1, 10))
    assert pd.isna(valor)
    assert status == INDISPONIVEL


# --- grade de pontos e índices de referência -------------------------------

def test_grade_de_indices_so_tem_pontos_com_linha():
    g = grade_de_indices(indices_de(PONTOS), CAL3, ("IDIV", "SMLL"))
    assert list(g.columns) == ["IDIV", "SMLL"]
    assert g["IDIV"].tolist() == [1000.0, 1010.0, 1030.2]
    assert g["SMLL"].isna().all()


def test_calcular_indices_cdi_ipca_pontos_e_ivvb11():
    ind = indices_de(CDI3 + PONTOS)
    precos = precos_de("PETR4", CAL3, fech=[1.0, 1.0, 1.0])  # sem IVVB11
    res = calcular_indices(precos, ind, CAL3, _params({"d1": 1, "n2": 2}))

    assert list(res) == ["d1", "n2"]
    assert list(res["d1"].valor.columns) == list(INDICES)
    assert list(res["n2"].valor.columns) == list(INDICES)
    assert res["d1"].valor.index.equals(indice_pregoes(CAL3))

    assert _vl(res["d1"], "2025-01-06", "CDI") == pytest.approx(0.0004, abs=1e-12)
    assert _vl(res["d1"], "2025-01-06", "IDIV") == pytest.approx(0.020000000000000018, abs=1e-12)
    assert _vl(res["n2"], "2025-01-06", "IDIV") == pytest.approx(0.030200000000000005, abs=1e-12)
    assert _st(res["d1"], "2025-01-06", "IPCA") == HIST
    assert _st(res["d1"], "2025-01-06", "SMLL") == INDISPONIVEL
    assert _st(res["d1"], "2025-01-06", "IVVB11") == INDISPONIVEL


def test_ivvb11_usa_o_fechamento_ajustado_de_v1_precos():
    precos = precos_de("IVVB11", CAL3, fech=[100.0, 101.0, 102.0])
    res = calcular_indices(precos, indices_de(CDI3), CAL3, _params({"d1": 1}))
    assert _vl(res["d1"], "2025-01-06", "IVVB11") == pytest.approx(102.0 / 101.0 - 1, abs=1e-12)
    assert _st(res["d1"], "2025-01-06", "IVVB11") == OK


def test_indices_no_dia_formato_longo_e_ordenado():
    ind = indices_de(CDI3 + PONTOS)
    precos = precos_de("PETR4", CAL3, fech=[1.0, 1.0, 1.0])
    res = calcular_indices(precos, ind, CAL3, _params({"d1": 1, "n2": 2}))

    df = indices_no_dia(res, date(2025, 1, 6))
    assert list(df.columns) == ["indice", "janela", "valor", "status"]
    assert len(df) == len(INDICES) * 2
    assert df.index.equals(pd.RangeIndex(len(df)))
    pares = list(zip(df["indice"], df["janela"]))
    assert pares == sorted(pares)

    linha = df[(df["indice"] == "IDIV") & (df["janela"] == "d1")].iloc[0]
    assert linha["valor"] == pytest.approx(0.020000000000000018, abs=1e-12)
    assert linha["status"] == OK


def test_indices_no_dia_recusa_dia_que_nao_e_pregao():
    precos = precos_de("PETR4", CAL3, fech=[1.0, 1.0, 1.0])
    res = calcular_indices(precos, indices_de(CDI3 + PONTOS), CAL3, _params({"d1": 1}))
    with pytest.raises(ValueError, match="não é pregão"):
        indices_no_dia(res, date(2025, 1, 4))  # sábado
