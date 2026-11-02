"""Testes das regras puras do protocolo (processamento/experimento/protocolo.py): limites, critérios 1 a 5,
medição pareada, conjunto e decisão da rodada. Gabaritos do plano da Parte C, fase 1.3. Sem banco, sem treino."""

from dataclasses import replace
from fractions import Fraction

import pandas as pd
import pytest

from processamento.experimento.protocolo import (
    ANOS_PROTOCOLO,
    BLOCOS_ADOTAVEIS,
    LIMITES,
    ORDEM_TESTES,
    avaliar_criterios,
    criterio_1,
    criterio_2,
    criterio_3,
    criterio_4,
    criterio_5,
    decidir_conjunto,
    decidir_rodada,
    medir_comparacao,
)


def _anos(valores):
    return dict(zip(ANOS_PROTOCOLO, valores))


def _medidas(ganho=0.01, ic=(0.001, 0.02), ganho_ano=0.01, regime=0.01):
    return {
        "ganho": ganho,
        "ic": ic,
        "ganho_por_ano": {a: ganho_ano for a in ANOS_PROTOCOLO},
        "top": {"k": 5, "n_dias": 1000, "acertos_base": 2650, "acertos_candidato": 2650},
        "regime": {"ganho": regime},
    }


def _avaliacoes(aprovados):
    return {nome: {"aprovado": nome in aprovados} for nome in ORDEM_TESTES}


def _dia(data, scores, alvo=(1, 1, 0, 0)):
    return pd.DataFrame({
        "data": pd.to_datetime([data] * 4),
        "ticker": ["A", "B", "C", "D"],
        "score": list(scores),
        "alvo": list(alvo),
        "ret_t1": 0.0,
        "ret_ibov_t1": 0.0,
    })


# ---------- Limites ----------

def test_limites_fixos():
    assert LIMITES.ganho_minimo == 0.005
    assert LIMITES.percentis_ic == (0.5, 99.5)
    assert LIMITES.bloco_bootstrap == 5
    assert LIMITES.reamostragens == 2000
    assert LIMITES.anos == (2021, 2022, 2023, 2024, 2025, 2026)
    assert LIMITES.anos_positivos_minimos == 4
    assert LIMITES.piso_ano == -0.005
    assert LIMITES.k_top == 5
    assert LIMITES.queda_top_maxima == Fraction(1, 200)
    assert LIMITES.anos_regime == (2024,)
    assert LIMITES.anos_regime_relato == (2023, 2024)


# ---------- Critério 1: ganho ----------

def test_c1_borda_reprova():
    assert criterio_1(0.005) is False


def test_c1_valores():
    assert criterio_1(0.0050001) is True
    assert criterio_1(0.0049) is False
    assert criterio_1(None) is False


# ---------- Critério 2: IC ----------

def test_c2_tocando_zero_reprova():
    assert criterio_2((0.0, 0.01)) is False


def test_c2_valores():
    assert criterio_2((1e-9, 0.01)) is True
    assert criterio_2((-0.001, 0.01)) is False
    assert criterio_2((None, None)) is False


# ---------- Critério 3: anos ----------

def test_c3_quatro_de_seis_passa_com_zeros():
    assert criterio_3(_anos([0.01] * 4 + [0.0, 0.0])) is True


def test_c3_tres_de_seis_reprova():
    assert criterio_3(_anos([0.01] * 3 + [0.0] * 3)) is False


def test_c3_ano_abaixo_do_piso_reprova():
    assert criterio_3(_anos([0.01] * 5 + [-0.0051])) is False


def test_c3_ano_exatamente_no_piso_passa():
    assert criterio_3(_anos([0.01] * 5 + [-0.005])) is True


def test_c3_ano_ausente_nao_conta():
    assert criterio_3({a: 0.01 for a in ANOS_PROTOCOLO[1:]}) is True
    assert criterio_3({2025: 0.01, 2026: 0.01}) is False


# ---------- Critério 4: top 5 ----------

def test_c4_queda_de_meio_ponto_passa_sem_erro_de_ponto_flutuante():
    assert criterio_4(2650, 2625, 5, 1000, LIMITES) is True


def test_c4_acima_de_meio_ponto_reprova():
    assert criterio_4(2650, 2624, 5, 1000, LIMITES) is False


def test_c4_borda_com_n_real():
    assert criterio_4(3000, 2967, 5, 1320, LIMITES) is True
    assert criterio_4(3000, 2966, 5, 1320, LIMITES) is False


def test_c4_subiu_passa():
    assert criterio_4(2650, 2700, 5, 1000, LIMITES) is True


def test_c4_sem_dias_reprova():
    assert criterio_4(0, 0, 5, 0, LIMITES) is False


# ---------- Critério 5: regime ----------

def test_c5_valores():
    assert criterio_5(1e-9) is True
    assert criterio_5(0.0) is False
    assert criterio_5(-0.001) is False
    assert criterio_5(None) is False


# ---------- Avaliação completa ----------

def test_avaliar_sem_criterio_5_nao_se_aplica():
    aval = avaliar_criterios(_medidas(regime=-0.01), aplica_5=False)
    assert aval["c5"] is None
    assert aval["aprovado"] is True


def test_avaliar_com_criterio_5_reprova_regime_negativo():
    aval = avaliar_criterios(_medidas(ganho=0.006, ic=(0.001, 0.01), regime=-0.0001), aplica_5=True)
    assert aval["c5"] is False
    assert aval["aprovado"] is False


# ---------- Medição pareada ----------

def _previsoes():
    base = pd.concat([
        _dia("2023-01-02", [.9, .1, .8, .2]),
        _dia("2024-01-02", [.9, .7, .8, .2]),
        _dia("2024-01-03", [.9, .1, .8, .2]),
        _dia("2026-01-05", [.9, .1, .8, .2], alvo=(1, 1, 1, 1)),
    ], ignore_index=True)
    cand = pd.concat([
        _dia("2023-01-02", [.9, .7, .8, .2]),
        _dia("2024-01-02", [.9, .1, .8, .2]),
        _dia("2024-01-03", [.9, .8, .7, .2]),
        _dia("2026-01-05", [.1, .2, .3, .4], alvo=(1, 1, 1, 1)),
    ], ignore_index=True)
    return base, cand


def test_medir_comparacao_gabarito():
    base, cand = _previsoes()
    lim = replace(LIMITES, k_top=2, reamostragens=50)
    m = medir_comparacao(base, cand, 1, lim)
    assert m["ganho"] == pytest.approx(1 / 6)
    assert m["n_dias_auc"] == 3
    assert m["ganho_por_ano"] == pytest.approx({2023: 0.25, 2024: 0.125})
    assert m["n_dias_por_ano"] == {2023: 1, 2024: 2}
    assert m["regime"]["ganho"] == pytest.approx(0.125)
    assert m["regime"]["por_ano"] == pytest.approx({2023: 0.25, 2024: 0.125})
    assert m["top"]["acertos_base"] == 5
    assert m["top"]["acertos_candidato"] == 6
    assert m["top"]["n_dias"] == 4
    assert m["top"]["k"] == 2


def test_medir_comparacao_recusa_tickers_trocados():
    base, cand = _previsoes()
    cand_trocado = cand.assign(ticker=cand["ticker"].replace({"A": "B", "B": "A"}))
    with pytest.raises(ValueError):
        medir_comparacao(base, cand_trocado, 1, replace(LIMITES, k_top=2, reamostragens=50))


# ---------- Conjunto e decisão ----------

@pytest.mark.parametrize("aprovados, conjunto, esperado", [
    ([], None, []),
    (["bloco_b"], None, ["bloco_b"]),
])
def test_conjunto_com_zero_ou_um_aprovado(aprovados, conjunto, esperado):
    assert decidir_conjunto(aprovados, {}, conjunto) == esperado


def test_conjunto_passa():
    assert decidir_conjunto(["bloco_a", "bloco_c"], {"bloco_a": 0.007, "bloco_c": 0.009}, True) == ["bloco_a", "bloco_c"]


def test_conjunto_falha_fica_o_de_maior_ganho():
    assert decidir_conjunto(["bloco_a", "bloco_c"], {"bloco_a": 0.007, "bloco_c": 0.009}, False) == ["bloco_c"]


def test_conjunto_falha_empate_fica_o_primeiro():
    assert decidir_conjunto(["bloco_a", "bloco_c"], {"bloco_a": 0.009, "bloco_c": 0.009}, False) == ["bloco_a"]


def test_decidir_rodada_controle_aprovado_invalida():
    dec = decidir_rodada(_avaliacoes({"controle", "bloco_a"}), ["bloco_a"], regras_mudaram=False)
    assert dec["status"] == "invalida"
    assert dec["adotados"] == []
    assert dec["bloco_e_aprovado"] is False


def test_decidir_rodada_regras_alteradas_invalida():
    dec = decidir_rodada(_avaliacoes(set()), [], regras_mudaram=True)
    assert dec["status"] == "invalida"


def test_decidir_rodada_controle_reprovado_valida():
    dec = decidir_rodada(_avaliacoes({"bloco_a"}), ["bloco_a"], regras_mudaram=False)
    assert dec["status"] == "valida"
    assert dec["adotados"] == ["bloco_a"]


def test_blocos_adotaveis_nao_incluem_controle_nem_e():
    assert BLOCOS_ADOTAVEIS == ("bloco_a", "bloco_b", "bloco_c", "bloco_d")
