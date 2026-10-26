"""Testes de processamento/fatos/trimestres.py: trimestre isolado, 12 meses e point-in-time.

Usa a fábrica de tests/fabrica_fundamentos.py (valores da seção F1 do plano da etapa 4).
Nenhum teste usa banco ou rede.
"""

import math

import pandas as pd
import pytest

from fabrica_fundamentos import (
    CNPJ, EXCL, LINHAS_A, LINHAS_AZZAS, LINHAS_B, LINHAS_C, LINHAS_D, LINHAS_F, LINHAS_LIXO, T, balanco_de,
)
from processamento.exclusoes import Exclusoes
from processamento.fatos.precos import HIST, INDISPONIVEL, OK
from processamento.fatos.trimestres import (
    FLUXO,
    entregues_ate,
    estoques_no_fim,
    foto_balanco,
    meses_do_periodo,
    periodo_valido,
    referencia,
    so_periodos_validos,
    trimestres_isolados,
)

A = balanco_de(CNPJ["A"], LINHAS_A)
B = balanco_de(CNPJ["B"], LINHAS_B)
C = balanco_de(CNPJ["C"], LINHAS_C)
D = balanco_de(CNPJ["D"], LINHAS_D)
F = balanco_de(CNPJ["F"], LINHAS_F)
LIXO = balanco_de(CNPJ["A"], LINHAS_LIXO)
AZZAS = balanco_de(CNPJ["A"], LINHAS_AZZAS)


def _ts(texto: str) -> pd.Timestamp:
    """Data AAAA-MM-DD como Timestamp."""
    return pd.Timestamp(texto)


def _par(par, valor, status):
    """Confere um par (valor, status). `valor` None significa NaN esperado (status diferente de ok)."""
    v, s = par
    assert s == status
    if valor is None:
        assert math.isnan(v)
    else:
        assert v == pytest.approx(valor, rel=1e-9)


# ---------------------------------------------------------------------------
# Período em meses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ini,fim,esperado", [
    ("2025-01-01", "2025-03-31", 3),
    ("2024-07-01", "2024-09-30", 3),
    ("2025-01-01", "2025-06-30", 6),
    ("2024-01-01", "2024-09-30", 9),
    ("2024-01-01", "2024-12-31", 12),
    ("2025-04-01", "2026-03-31", 12),
    ("2025-01-01", "2025-02-28", None),
])
def test_meses_do_periodo(ini, fim, esperado):
    assert meses_do_periodo(_ts(ini), _ts(fim)) == esperado


# ---------------------------------------------------------------------------
# (a) Trimestre isolado
# ---------------------------------------------------------------------------

# (fim, receita, lucro bruto, lucro líquido, entrega, origem) dos 6 trimestres de A em t = 2026-03-31.
TRIMESTRES_A = [
    ("2024-09-30", 300, 120, 30, "2024-11-10", "itr_3m"),
    ("2024-12-31", 400, 140, 40, "2025-03-20", "diferenca"),
    ("2025-03-31", 350, 140, 35, "2025-05-10", "itr_3m"),
    ("2025-06-30", 360, 150, 40, "2025-08-10", "itr_3m"),
    ("2025-09-30", 380, 160, 45, "2025-11-10", "itr_3m"),
    ("2025-12-31", 410, 170, 40, "2026-03-15", "diferenca"),
]


def test_trimestres_isolados_de_a():
    tri = trimestres_isolados(A, T)
    assert len(tri) == 6
    assert list(tri.columns) == ["cnpj", "data_fim_periodo", "data_entrega", "origem", *FLUXO]
    for i, (fim, receita, lucro_bruto, lucro_liquido, entrega, origem) in enumerate(TRIMESTRES_A):
        linha = tri.iloc[i]
        assert linha["cnpj"] == CNPJ["A"]
        assert linha["data_fim_periodo"] == _ts(fim)
        assert linha["receita_liquida"] == pytest.approx(receita, rel=1e-9)
        assert linha["lucro_bruto"] == pytest.approx(lucro_bruto, rel=1e-9)
        assert linha["lucro_liquido"] == pytest.approx(lucro_liquido, rel=1e-9)
        assert linha["data_entrega"] == _ts(entrega)
        assert linha["origem"] == origem
        assert math.isnan(linha["ebit"])


def test_trimestres_isolados_d_da_pela_diferenca():
    tri = trimestres_isolados(D, T)
    assert len(tri) == 4
    assert tri["depreciacao_amortizacao"].tolist() == pytest.approx([5, 6, 7, 8], rel=1e-9)
    assert tri["ebit"].tolist() == pytest.approx([20, 20, 20, 25], rel=1e-9)
    quarto = tri.iloc[3]
    assert quarto["origem"] == "diferenca"
    assert quarto["receita_liquida"] == pytest.approx(120, rel=1e-9)
    assert quarto["lucro_bruto"] == pytest.approx(50, rel=1e-9)
    assert quarto["lucro_liquido"] == pytest.approx(15, rel=1e-9)


def test_trimestres_isolados_so_ate_t():
    # Em 2025-08-09 ainda não entregues o ITR do 2º trimestre de 2025 e o H1 (entregues em 2025-08-10).
    tri = trimestres_isolados(A, _ts("2025-08-09"))
    assert list(tri["data_fim_periodo"]) == [_ts("2024-09-30"), _ts("2024-12-31"), _ts("2025-03-31")]


def test_exercicio_de_abril_a_marco():
    foto = foto_balanco(F, CNPJ["F"], _ts("2026-06-30"), Exclusoes())
    assert foto.status_base == OK
    assert foto.data_fim_periodo == _ts("2026-03-31")
    assert foto.data_entrega == _ts("2026-06-20")
    _par(foto.fluxo_12m["receita_liquida"], 460, OK)


# ---------------------------------------------------------------------------
# Referência e saldos de balanço
# ---------------------------------------------------------------------------

def test_referencia_da_maior_data_fim_entregue():
    assert referencia(A, CNPJ["A"], T) == (_ts("2025-12-31"), _ts("2026-03-15"))


def test_referencia_sem_entrega_ate_t():
    assert referencia(A, CNPJ["A"], _ts("2024-11-09")) == (None, None)


def test_estoque_nao_vaza_antes_da_entrega():
    # DFP de 2025 entregue em 2026-03-15: em 2026-03-14 o saldo de 2025-12-31 ainda não existe.
    estoque = estoques_no_fim(A, CNPJ["A"], _ts("2025-12-31"), _ts("2026-03-14"))
    _par(estoque["patrimonio_liquido"], None, INDISPONIVEL)


# ---------------------------------------------------------------------------
# (b) 12 meses e point-in-time
# ---------------------------------------------------------------------------

def test_doze_meses_em_2026_03_31():
    foto = foto_balanco(A, CNPJ["A"], T, Exclusoes())
    assert foto.status_base == OK
    assert foto.data_fim_periodo == _ts("2025-12-31")
    assert foto.data_entrega == _ts("2026-03-15")
    _par(foto.fluxo_12m["receita_liquida"], 1500, OK)
    _par(foto.fluxo_12m["lucro_bruto"], 620, OK)
    _par(foto.fluxo_12m["lucro_liquido"], 160, OK)
    _par(foto.fluxo_12m["ebit"], None, INDISPONIVEL)
    _par(foto.estoque["patrimonio_liquido"], 1300, OK)
    _par(foto.fluxo_trimestre["receita_liquida"], 410, OK)


@pytest.mark.parametrize("t", ["2025-10-21", "2025-08-10"])
def test_doze_meses_com_referencia_em_2025_06_30(t):
    # A entrega de 2025-08-10 entra no próprio dia.
    foto = foto_balanco(A, CNPJ["A"], _ts(t), Exclusoes())
    assert foto.data_fim_periodo == _ts("2025-06-30")
    assert foto.data_entrega == _ts("2025-08-10")
    _par(foto.fluxo_12m["receita_liquida"], 1410, OK)
    _par(foto.fluxo_12m["lucro_bruto"], 550, OK)
    _par(foto.fluxo_12m["lucro_liquido"], 145, OK)
    _par(foto.estoque["patrimonio_liquido"], 1200, OK)


def test_doze_meses_com_tres_trimestres_e_historico_insuficiente():
    foto = foto_balanco(A, CNPJ["A"], _ts("2025-08-09"), Exclusoes())
    assert foto.data_fim_periodo == _ts("2025-03-31")
    assert foto.data_entrega == _ts("2025-05-10")
    _par(foto.fluxo_12m["receita_liquida"], None, HIST)
    _par(foto.fluxo_12m["lucro_liquido"], None, HIST)
    # Há trimestre presente com ebit NaN: a checagem de indisponivel vem antes.
    _par(foto.fluxo_12m["ebit"], None, INDISPONIVEL)
    _par(foto.estoque["patrimonio_liquido"], 1150, OK)


def test_nada_entregue_ate_t_vira_historico_insuficiente():
    foto = foto_balanco(A, CNPJ["A"], _ts("2024-11-09"), Exclusoes())
    assert foto.status_base == HIST
    assert foto.data_fim_periodo is None
    assert foto.data_entrega is None
    for par in foto.fluxo_12m.values():
        _par(par, None, HIST)
    for par in foto.fluxo_trimestre.values():
        _par(par, None, HIST)
    for par in foto.estoque.values():
        _par(par, None, HIST)


def test_d_completo_em_2026_03_31():
    foto = foto_balanco(D, CNPJ["D"], T, Exclusoes())
    assert foto.status_base == OK
    _par(foto.fluxo_12m["receita_liquida"], 420, OK)
    _par(foto.fluxo_12m["lucro_bruto"], 170, OK)
    _par(foto.fluxo_12m["lucro_liquido"], 45, OK)
    _par(foto.fluxo_12m["ebit"], 85, OK)
    _par(foto.fluxo_12m["depreciacao_amortizacao"], 26, OK)
    _par(foto.estoque["patrimonio_liquido"], 540, OK)
    _par(foto.estoque["emprestimos_curto_prazo"], 70, OK)
    _par(foto.estoque["emprestimos_longo_prazo"], 130, OK)
    _par(foto.estoque["caixa"], 80, OK)
    _par(foto.estoque["aplicacoes_financeiras"], 20, OK)


def test_fim_informado_usa_o_trimestre_pedido():
    foto = foto_balanco(A, CNPJ["A"], T, Exclusoes(), fim="2025-06-30")
    assert foto.data_fim_periodo == _ts("2025-06-30")
    assert foto.data_entrega == _ts("2025-08-10")
    _par(foto.fluxo_12m["lucro_liquido"], 145, OK)
    _par(foto.estoque["patrimonio_liquido"], 1200, OK)


def test_fim_sem_linha_entregue_levanta_erro():
    with pytest.raises(ValueError):
        foto_balanco(A, CNPJ["A"], T, Exclusoes(), fim="2025-02-28")
    # 2025-06-30 só é entregue em 2025-08-10: em 2025-08-09 ainda não existe.
    with pytest.raises(ValueError):
        foto_balanco(A, CNPJ["A"], _ts("2025-08-09"), Exclusoes(), fim="2025-06-30")


# ---------------------------------------------------------------------------
# (c) Reapresentação e 9 meses reentregue
# ---------------------------------------------------------------------------

def test_reapresentacao_nao_vaza_antes_da_entrega():
    foto = foto_balanco(B, CNPJ["B"], _ts("2025-11-20"), Exclusoes())
    assert foto.data_fim_periodo == _ts("2025-09-30")
    _par(foto.fluxo_12m["lucro_liquido"], None, HIST)
    _par(foto.estoque["patrimonio_liquido"], 1250, OK)


def test_reapresentacao_entregue_em_2025_12_01():
    foto = foto_balanco(B, CNPJ["B"], _ts("2025-12-01"), Exclusoes())
    assert foto.data_fim_periodo == _ts("2025-09-30")
    _par(foto.fluxo_12m["lucro_liquido"], 160, OK)
    _par(foto.fluxo_12m["receita_liquida"], 1490, OK)
    _par(foto.fluxo_12m["lucro_bruto"], 590, OK)


def test_reapresentacao_antes_da_primeira_entrega():
    foto = foto_balanco(B, CNPJ["B"], _ts("2025-10-21"), Exclusoes())
    assert foto.data_fim_periodo == _ts("2025-03-31")
    _par(foto.fluxo_12m["lucro_liquido"], None, HIST)


def test_nove_meses_reentregue_depois_da_dfp():
    foto = foto_balanco(C, CNPJ["C"], _ts("2026-03-20"), Exclusoes())
    assert foto.data_fim_periodo == _ts("2025-12-31")
    assert foto.data_entrega == _ts("2026-03-15")
    _par(foto.fluxo_12m["lucro_liquido"], None, HIST)
    _par(foto.estoque["patrimonio_liquido"], 1300, OK)


def test_nove_meses_reentregue_em_2026_04_01():
    foto = foto_balanco(C, CNPJ["C"], _ts("2026-04-01"), Exclusoes())
    _par(foto.fluxo_12m["lucro_liquido"], 160, OK)


# ---------------------------------------------------------------------------
# (g) Sem balanço
# ---------------------------------------------------------------------------

def test_cnpj_em_cnpjs_sem_balanco_e_indisponivel():
    vazio = balanco_de(CNPJ["SEMB"], [])
    foto = foto_balanco(vazio, CNPJ["SEMB"], T, EXCL)
    assert foto.status_base == INDISPONIVEL
    assert foto.data_fim_periodo is None
    assert foto.data_entrega is None
    for par in foto.fluxo_12m.values():
        _par(par, None, INDISPONIVEL)
    for par in foto.estoque.values():
        _par(par, None, INDISPONIVEL)


def test_cnpj_sem_linhas_e_fora_da_lista_e_indisponivel():
    foto = foto_balanco(A, "00000000009999", T, Exclusoes())
    assert foto.status_base == INDISPONIVEL
    _par(foto.fluxo_12m["receita_liquida"], None, INDISPONIVEL)
    _par(foto.estoque["patrimonio_liquido"], None, INDISPONIVEL)


# ---------------------------------------------------------------------------
# (h) Período inválido descartado antes de qualquer conta (seção 6, item 1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tipo,ini,fim,esperado", [
    ("ITR", "2021-01-01", "2021-03-31", True),
    ("ITR", "2021-01-01", "2021-06-30", True),
    ("ITR", "2021-01-01", "2021-09-30", True),
    ("ITR", "2021-01-01", "2021-12-31", False),
    ("ITR", "2021-03-01", "2021-03-31", False),
    ("DFP", "2021-01-01", "2021-12-31", True),
    ("DFP", "2021-01-01", "2021-03-31", False),
    ("XYZ", "2021-01-01", "2021-12-31", True),
    ("XYZ", "2021-03-01", "2021-03-31", False),
    ("ITR", None, "2021-03-31", False),
])
def test_periodo_valido(tipo, ini, fim, esperado):
    assert periodo_valido(tipo, _ts(ini) if ini else None, _ts(fim)) is esperado


def test_so_periodos_validos_sem_linhas_mantem_colunas():
    vazio = LIXO.iloc[0:0]
    filtrado = so_periodos_validos(vazio)
    assert filtrado.empty
    assert list(filtrado.columns) == list(LIXO.columns)


def test_linha_de_31_dias_nao_entra_e_caixa_fica_indisponivel():
    # Em 2021-06-01 só o ITR de 1º trimestre (100 de receita) é válido; o de 31 dias sai antes das contas.
    t = _ts("2021-06-01")
    assert len(entregues_ate(LIXO, t)) == 1
    tri = trimestres_isolados(LIXO, t)
    assert len(tri) == 1
    assert tri.iloc[0]["data_fim_periodo"] == _ts("2021-03-31")
    assert tri.iloc[0]["receita_liquida"] == pytest.approx(100, rel=1e-9)
    # O caixa da linha de 31 dias era 0 (viraria (0.0, ok)); agora é só o caixa vazio da linha válida.
    estoque = estoques_no_fim(LIXO, CNPJ["A"], _ts("2021-03-31"), t)
    _par(estoque["caixa"], None, INDISPONIVEL)


def test_itr_de_12_meses_nao_entra_antes_da_dfp():
    # Em 2022-03-10 a ITR de 12 meses (entregue no mesmo dia) não entra; a DFP ainda não.
    t = _ts("2022-03-10")
    entregues = entregues_ate(AZZAS, t)
    assert len(entregues) == 4
    assert all(meses_do_periodo(i, f) in (3, 6, 9) for i, f in
               zip(entregues["data_inicio_periodo"], entregues["data_fim_periodo"]))
    tri = trimestres_isolados(AZZAS, t)
    quarto = tri[tri["data_fim_periodo"] == _ts("2021-12-31")].iloc[0]
    assert quarto["receita_liquida"] == pytest.approx(100, rel=1e-9)
    assert quarto["origem"] == "itr_3m"


def test_dfp_aparece_no_dia_seguinte_a_itr_de_12_meses():
    entregues = entregues_ate(AZZAS, _ts("2022-03-11"))
    assert list(entregues["tipo_documento"]).count("DFP") == 1
    assert len(entregues) == 5
