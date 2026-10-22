"""Testes de beta (caso d da etapa 3): regressão dos retornos da ação sobre os do IBOV.

Séries montadas com tests/fabrica_precos.py. Nenhum teste usa banco ou rede.
"""

import pandas as pd
import pytest

from fabrica_precos import pregoes_uteis, precos_de, serie_por_retornos
from processamento.fatos.precos import HIST, INDISPONIVEL, OK, beta, grade_de_precos


def _r_ibov(n):
    """Retornos do IBOV: 0.01·((i mod 5) − 2) para i = 1..n−1."""
    return [0.01 * ((i % 5) - 2) for i in range(1, n)]


def _r_acao_linear(r_ibov):
    """Ação com retorno 2·r_ibov + 0.001 (beta exatamente 2)."""
    return [2 * r + 0.001 for r in r_ibov]


def _beta_da_acao(cal, r_ibov, acao_datas, acao_fech, janela=252, minimo=120):
    """Grade de beta da ACAO3 com IBOV em `cal`; a ação tem só `acao_datas`/`acao_fech`."""
    ibov = precos_de("IBOV", cal, fech=serie_por_retornos(1000, r_ibov))
    acao = precos_de("ACAO3", acao_datas, fech=acao_fech)
    g = grade_de_precos(pd.concat([ibov, acao]), cal, "fechamento_ajustado", ["ACAO3", "IBOV"])
    return beta(g[["ACAO3"]], g["IBOV"], janela, minimo)


def test_cento_e_vinte_pares_calcula_beta_dois():
    cal = pregoes_uteis(130)
    r_ibov = _r_ibov(130)
    acao = serie_por_retornos(50, _r_acao_linear(r_ibov))

    b = _beta_da_acao(cal, r_ibov, cal[9:], acao[9:])

    assert b.status["ACAO3"].iloc[-1] == OK
    assert b.valor["ACAO3"].iloc[-1] == pytest.approx(2.0, abs=1e-9)


def test_cento_e_dezenove_pares_e_historico_insuficiente():
    cal = pregoes_uteis(130)
    r_ibov = _r_ibov(130)
    acao = serie_por_retornos(50, _r_acao_linear(r_ibov))

    b = _beta_da_acao(cal, r_ibov, cal[10:], acao[10:])

    assert b.status["ACAO3"].iloc[-1] == HIST
    assert pd.isna(b.valor["ACAO3"].iloc[-1])


def test_retorno_faltando_no_meio_reduz_os_pares_para_historico():
    # Sem o preço de cal[70], saem os retornos de 70 e 71: sobram 119 pares.
    cal = pregoes_uteis(130)
    r_ibov = _r_ibov(130)
    acao = serie_por_retornos(50, _r_acao_linear(r_ibov))
    acao_com_buraco = list(acao[8:])
    acao_com_buraco[70 - 8] = None

    b = _beta_da_acao(cal, r_ibov, cal[8:], acao_com_buraco)

    assert b.status["ACAO3"].iloc[-1] == HIST
    assert pd.isna(b.valor["ACAO3"].iloc[-1])


def test_janela_de_252_esquece_o_regime_antigo():
    cal = pregoes_uteis(300)
    r_ibov = _r_ibov(300)
    # i<48: retorno da ação = 0.02 − r_ibov (outro regime); i≥48: 2·r_ibov + 0.001.
    r_acao = [
        (0.02 - r) if (i + 1) < 48 else (2 * r + 0.001)
        for i, r in enumerate(r_ibov)
    ]
    acao = serie_por_retornos(50, r_acao)

    b = _beta_da_acao(cal, r_ibov, cal, acao, janela=252, minimo=120)

    assert b.status["ACAO3"].iloc[-1] == OK
    assert b.valor["ACAO3"].iloc[-1] == pytest.approx(2.0, abs=1e-9)

    penultimo = b.valor["ACAO3"].iloc[-2]
    assert abs(penultimo - 2) > 1e-6
    assert penultimo == pytest.approx(1.9999849506142493, abs=1e-9)


def test_sem_aj_no_dia_e_indisponivel():
    cal = pregoes_uteis(130)
    r_ibov = _r_ibov(130)
    acao = serie_por_retornos(50, _r_acao_linear(r_ibov))
    acao[-1] = None

    b = _beta_da_acao(cal, r_ibov, cal, acao)

    assert b.status["ACAO3"].iloc[-1] == INDISPONIVEL
    assert pd.isna(b.valor["ACAO3"].iloc[-1])
