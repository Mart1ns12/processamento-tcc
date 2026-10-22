"""Testes de processamento/fatos/precos.py: grade e variação as-of (caso a da etapa 3).

Séries montadas com tests/fabrica_precos.py; janelas do bloco fase1 real.
Nenhum teste usa banco ou rede.
"""

import pytest

from fabrica_precos import pregoes_uteis, precos_de
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    carregar_parametros_precos,
    grade_de_precos,
    variacao,
)

CAL3 = pregoes_uteis(3)
CAL4 = pregoes_uteis(4)


def _v(grade, ticker, i):
    return grade.valor[ticker].iloc[i]


def _s(grade, ticker, i):
    return grade.status[ticker].iloc[i]


def _divd3():
    return precos_de("DIVD3", CAL3, fech=[9.00, 10.00, 9.60], aj=[8.55, 9.50, 9.60])


def test_variacao_de_um_dia_no_fechamento_e_no_ajustado():
    precos = _divd3()
    fech = variacao(grade_de_precos(precos, CAL3, "fechamento", ["DIVD3"]), 1)
    aj = variacao(grade_de_precos(precos, CAL3, "fechamento_ajustado", ["DIVD3"]), 1)

    assert _v(fech, "DIVD3", 2) == pytest.approx(-0.04, abs=1e-12)
    assert _v(aj, "DIVD3", 2) == pytest.approx(0.010526315789473717, abs=1e-12)
    assert _s(fech, "DIVD3", 2) == OK


def test_variacao_de_dois_dias():
    precos = _divd3()
    fech = variacao(grade_de_precos(precos, CAL3, "fechamento", ["DIVD3"]), 2)
    aj = variacao(grade_de_precos(precos, CAL3, "fechamento_ajustado", ["DIVD3"]), 2)

    assert _v(fech, "DIVD3", 2) == pytest.approx(0.06666666666666665, abs=1e-12)
    assert _v(aj, "DIVD3", 2) == pytest.approx(0.12280701754385959, abs=1e-12)


def test_variacao_sem_base_e_historico_insuficiente():
    precos = _divd3()
    g = grade_de_precos(precos, CAL3, "fechamento", ["DIVD3"])

    n3 = variacao(g, 3)
    assert n3.status["DIVD3"].iloc[2] == HIST
    assert n3.valor["DIVD3"].isna().iloc[2]

    n1 = variacao(g, 1)
    assert n1.status["DIVD3"].iloc[0] == HIST
    assert n1.valor["DIVD3"].isna().iloc[0]


def test_ticker_sem_linhas_fica_indisponivel_em_tudo():
    precos = _divd3()
    for coluna in ("fechamento", "fechamento_ajustado"):
        g = grade_de_precos(precos, CAL3, coluna, ["DIVD3", "SEMP3"])
        for n in (1, 2):
            grade = variacao(g, n)
            assert all(grade.status["SEMP3"] == INDISPONIVEL)
            assert grade.valor["SEMP3"].isna().all()


def test_base_as_of_usa_o_ultimo_preco_ate_t_menos_n():
    # XPTO3 sem linha em p1: a base de p2 e p3 para n=1 é o último preço conhecido (p0 e p2).
    precos = precos_de("XPTO3", [CAL4[0], CAL4[2], CAL4[3]], fech=[10.0, 11.0, 12.0])
    g = grade_de_precos(precos, CAL4, "fechamento_ajustado", ["XPTO3"])

    n1 = variacao(g, 1)
    assert n1.status["XPTO3"].iloc[1] == INDISPONIVEL
    assert _v(n1, "XPTO3", 2) == pytest.approx(0.10000000000000009, abs=1e-12)
    assert _v(n1, "XPTO3", 3) == pytest.approx(0.09090909090909083, abs=1e-12)

    n2 = variacao(g, 2)
    assert _v(n2, "XPTO3", 3) == pytest.approx(0.19999999999999996, abs=1e-12)


def test_janelas_reais_do_bloco_fase1():
    cal = pregoes_uteis(253)
    precos = precos_de("PETR4", cal, fech=[100.0 + i for i in range(253)])
    g = grade_de_precos(precos, cal, "fechamento_ajustado", ["PETR4"])
    janelas = carregar_parametros_precos().janelas

    esperado = {
        "d1": 0.002849002849002913,
        "m1": 0.06344410876132933,
        "m6": 0.5575221238938053,
        "a1": 2.52,
    }
    for nome, n in janelas.items():
        grade = variacao(g, n)
        assert grade.status["PETR4"].iloc[-1] == OK
        assert _v(grade, "PETR4", -1) == pytest.approx(esperado[nome], abs=1e-12)


def test_a1_com_252_pregoes_e_historico_insuficiente():
    cal = pregoes_uteis(252)
    precos = precos_de("PETR4", cal, fech=[100.0 + i for i in range(252)])
    g = grade_de_precos(precos, cal, "fechamento_ajustado", ["PETR4"])

    a1 = variacao(g, carregar_parametros_precos().janelas["a1"])
    assert a1.status["PETR4"].iloc[-1] == HIST
