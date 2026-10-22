"""Caso (g) da etapa 3: nada depois de t pode mudar o que é calculado em t.

Dois cenários: "cortado" (só dados até t, calendário até t) e "cheio e alterado" (todos os dados,
com preços, volumes, CDI e IPCA posteriores a t multiplicados por valores diferentes). Os resumos
em t têm de ser idênticos. Nenhum teste usa banco ou rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, indices_de, pregoes_uteis, precos_de, serie_por_retornos
from processamento.exclusoes import Exclusoes
from processamento.fatos.indices import calcular_indices, cdi_dia, indices_no_dia, ipca_12m, ipca_ate
from processamento.fatos.precos import (
    HIST,
    OK,
    calcular_precos,
    carregar_parametros_precos,
    resumo_precos_no_dia,
)

N = 300
CADASTRO = cadastro_de([
    ("A3", "1", "S1", "ON"),
    ("B3", "2", "S1", "ON"),
    ("C3", "3", "S1", "ON"),
    ("D3", "4", "S2", "ON"),
])


def _mundo():
    """Calendário de N pregões e as séries de IBOV, A3, B3, C3 e D3 (D3 só a partir de cal[100])."""
    rng = np.random.default_rng(7)
    cal = pregoes_uteis(N)
    partes = []
    for ticker, inicio in (("IBOV", 0), ("A3", 0), ("B3", 0), ("C3", 0), ("D3", 100)):
        datas = cal[inicio:]
        n = len(datas)
        aj = serie_por_retornos(100.0, rng.normal(0, 0.02, n - 1).tolist())
        fech = [x * 1.05 for x in aj]
        volume = rng.integers(1000, 5000, size=n).tolist()
        partes.append(precos_de(ticker, datas, fech, aj, volume))
    precos = pd.concat(partes, ignore_index=True)

    cdi = [(d.isoformat(), "CDI", 0.05) for d in cal]
    meses = pd.period_range("2024-12", pd.Timestamp(cal[-1]), freq="M")
    ipca = [(f"{m.start_time:%Y-%m-%d}", "IPCA", 0.4) for m in meses]
    indices = indices_de(cdi + ipca)
    return cal, precos, indices


def _cortado(cal, precos, indices, t):
    """Só dados até t (inclusive) e calendário até t."""
    corte = pd.Timestamp(t)
    cal_c = [d for d in cal if d <= t]
    return cal_c, precos[precos["data"] <= corte], indices[indices["data"] <= corte]


def _alterado_depois_de(precos, indices, t):
    """Cópias com os dados posteriores a t multiplicados: preços x3, volume x10, CDI x5, IPCA x5."""
    corte = pd.Timestamp(t)
    p = precos.copy()
    depois = p["data"] > corte
    p.loc[depois, ["fechamento", "fechamento_ajustado"]] = p.loc[depois, ["fechamento", "fechamento_ajustado"]] * 3
    p.loc[depois, "volume"] = p.loc[depois, "volume"] * 10

    i = indices.copy()
    cdi_depois = (i["indice"] == "CDI") & (i["data"] > corte)
    i.loc[cdi_depois, "valor"] = i.loc[cdi_depois, "valor"] * 5
    ipca_depois = (i["indice"] == "IPCA") & (i["data"] >= corte.replace(day=1))
    i.loc[ipca_depois, "valor"] = i.loc[ipca_depois, "valor"] * 5
    return p, i


def _resumo(cal, precos, indices, t):
    params = carregar_parametros_precos()
    res_p = calcular_precos(precos, CADASTRO, cal, Exclusoes(), params)
    res_i = calcular_indices(precos, indices, cal, params)
    return resumo_precos_no_dia(res_p, t), indices_no_dia(res_i, t)


def _valor(df, chave, indicador):
    linha = df[(df["ticker"] == chave) & (df["indicador"] == indicador)]
    assert len(linha) == 1
    return linha["valor"].iloc[0], linha["status"].iloc[0]


@pytest.fixture(scope="module")
def cenario():
    cal, precos, indices = _mundo()
    t = cal[260]
    return cal, precos, indices, t


def test_cortado_e_cheio_alterado_dao_o_mesmo_resumo(cenario):
    cal, precos, indices, t = cenario
    cal_c, p_c, i_c = _cortado(cal, precos, indices, t)
    p_a, i_a = _alterado_depois_de(precos, indices, t)

    resumo_c, ind_c = _resumo(cal_c, p_c, i_c, t)
    resumo_a, ind_a = _resumo(cal, p_a, i_a, t)
    pd.testing.assert_frame_equal(resumo_c, resumo_a)
    pd.testing.assert_frame_equal(ind_c, ind_a)

    assert cdi_dia(i_c, t) == cdi_dia(i_a, t)
    assert ipca_12m(i_c, t) == ipca_12m(i_a, t)
    assert ipca_ate(i_c, t) == ipca_ate(i_a, t)


def test_comparacao_tem_valores_nao_vazios_em_t(cenario):
    cal, precos, indices, t = cenario
    resumo, ind = _resumo(cal, precos, indices, t)
    beta_a3, st_a3 = _valor(resumo, "A3", "beta.valor")
    beta_d3, st_d3 = _valor(resumo, "D3", "beta.valor")
    assert st_a3 == OK and np.isfinite(beta_a3)
    assert st_d3 == OK and np.isfinite(beta_d3)
    assert _valor(resumo, "A3", "rentabilidade.a1")[1] == OK
    # D3 começa em cal[100]: a base do a1 (cal[8]) não existe
    assert _valor(resumo, "D3", "rentabilidade.a1")[1] == HIST
    assert _valor(resumo, "A3", "cotacao.fechamento")[1] == OK
    assert cdi_dia(indices, t)[1] == OK
    assert ipca_12m(indices, t)[1] == OK
    assert ipca_ate(indices, t) is not None


def test_alteracao_depois_de_t_muda_o_resumo_depois_de_t(cenario):
    # prova de que a alteração "cheio e alterado" de fato mexeu nos dados posteriores a t
    cal, precos, indices, t = cenario
    depois = cal[280]
    p_a, i_a = _alterado_depois_de(precos, indices, t)
    resumo, _ = _resumo(cal, precos, indices, depois)
    resumo_a, _ = _resumo(cal, p_a, i_a, depois)
    v, _ = _valor(resumo, "A3", "cotacao.fechamento")
    va, _ = _valor(resumo_a, "A3", "cotacao.fechamento")
    assert va == pytest.approx(3 * v, abs=1e-9)


def test_mudar_aj_em_t_muda_rentabilidade_d1_em_t(cenario):
    cal, precos, indices, t = cenario
    resumo, _ = _resumo(cal, precos, indices, t)
    p_s = precos.copy()
    em_t = (p_s["ticker"] == "A3") & (p_s["data"] == pd.Timestamp(t))
    p_s.loc[em_t, "fechamento_ajustado"] = p_s.loc[em_t, "fechamento_ajustado"] * 1.01
    resumo_s, _ = _resumo(cal, p_s, indices, t)
    antes, st_antes = _valor(resumo, "A3", "rentabilidade.d1")
    depois, st_depois = _valor(resumo_s, "A3", "rentabilidade.d1")
    assert st_antes == OK and st_depois == OK
    assert depois != pytest.approx(antes, abs=1e-9)
