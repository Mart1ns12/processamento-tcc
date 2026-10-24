"""Testes da checagem diária (plano da etapa 8, fase 7; seção 9 do plano). Sem banco e sem rede.

Os valores esperados são os gabaritos da seção 9 do plano, feitos à mão.
"""

from datetime import date

import pandas as pd

from fabrica_precos import precos_de, pregoes_uteis
from processamento.rotina.checagem import avisos_do_dia, avisos_indicadores
from processamento.rotina.parametros import ParametrosChecagem

PARAMS = ParametrosChecagem(acoes_minimo_fracao=0.9, retorno_maximo_abs=0.30,
                            preco_parado_pregoes=5, max_tickers_por_aviso=10)
PARES = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3", "GGGG3", "HHHH3", "IIII3", "JJJJ3"]
T_MERCADO = date(2025, 10, 21)


def _cenario(n: int = 6) -> tuple[pd.DataFrame, list, object]:
    """Gabarito da seção 9 com os últimos `n` pregões (n=6 é o caso completo)."""
    cal = pregoes_uteis(6)[-n:]
    t = cal[-1]
    series = {
        "AAAA3": ([10, 10.1, 10.2, 10.3, 10, 13.5], None, None),
        "BBBB3": ([10, 10, 10.1, 10.2, 10, 6.9], None, None),
        "CCCC3": ([10, 10.1, 10.2, 10.3, 10, 12.9], None, None),
        "DDDD3": ([10, 10.1, 10.2, 10.1, 10.2, 10.3], None, [1000, 1000, 1000, 1000, 1000, 0]),
        "EEEE3": ([9, 10, 10, 10, 10, 10], None, None),
        "FFFF3": ([9, 9.5, 10, 10, 10, 10], None, None),
        "GGGG3": ([10, 10.5, 10.2, 10.4, 10.1, 10.6], None, None),
        "HHHH3": ([10, 9.8, 10.1, 9.9, 10.2, 10.0], None, None),
        "IIII3": ([10, 10.1, 10.2, 10.3, 10.1, None], None, None),
        "JJJJ3": ([10, 10.1, 10.2, 10.3, 10.1, None], None, None),
    }
    partes = []
    for ticker, (fech, aj, vol) in series.items():
        partes.append(precos_de(ticker, cal, fech[-n:], aj if aj is None else aj[-n:],
                                None if vol is None else vol[-n:]))
    partes.append(precos_de("IBOV", cal, [100, 101, 102, 101, 103, 104][-n:]))
    return pd.concat(partes, ignore_index=True), cal, t


def test_gabarito_completo_na_ordem_da_secao_9():
    precos, cal, t = _cenario(6)
    assert avisos_do_dia(precos, cal, t, PARES, PARAMS) == [
        "Checagem: só 8 de 10 ações (ON, PN e UNIT) com preço em 2025-01-09.",
        "Checagem: retorno do dia acima de 30% em módulo em 2025-01-09: AAAA3 (35,0%), BBBB3 (-31,0%).",
        "Checagem: volume zero em 2025-01-09: DDDD3.",
        "Checagem: preço parado (mesmo fechamento nos últimos 5 pregões até 2025-01-09): EEEE3.",
    ]


def test_preco_parado_nao_roda_com_quatro_pregoes():
    precos, cal, t = _cenario(4)
    avisos = avisos_do_dia(precos, cal, t, PARES, PARAMS)
    assert not any("preço parado" in a for a in avisos)
    assert "Checagem: só 8 de 10 ações (ON, PN e UNIT) com preço em 2025-01-09." in avisos
    assert "Checagem: volume zero em 2025-01-09: DDDD3." in avisos


def test_volume_zero_com_doze_tickers_corta_em_dez():
    tickers = [f"{c}{c}{c}{c}3" for c in "ABCDEFGHIJKL"]
    cal = pregoes_uteis(6)
    fech = [10, 10.1, 10.2, 10.1, 10.2, 10.3]
    precos = pd.concat([
        precos_de(tk, cal, fech, volume=[1000, 1000, 1000, 1000, 1000, 0]) for tk in tickers
    ], ignore_index=True)
    avisos = avisos_do_dia(precos, cal, cal[-1], tickers, PARAMS)
    assert avisos == [
        "Checagem: volume zero em 2025-01-09: AAAA3, BBBB3, CCCC3, DDDD3, EEEE3, FFFF3, GGGG3, HHHH3, "
        "IIII3, JJJJ3 e mais 2.",
    ]


def test_volume_vazio_nao_conta_como_volume_zero():
    cal = pregoes_uteis(6)
    precos = precos_de("AAAA3", cal, [10, 10.1, 10.2, 10.1, 10.2, 10.3], volume=[1000] * 5 + [None])
    assert avisos_do_dia(precos, cal, cal[-1], ["AAAA3"], PARAMS) == []


def test_primeiro_pregao_nao_roda_retorno_nem_parado():
    cal = pregoes_uteis(6)
    precos = pd.concat([
        precos_de("AAAA3", cal, [10, 13.5, 13.5, 13.5, 13.5, 13.5]),
        precos_de("IBOV", cal, [100, 101, 102, 101, 103, 104]),
    ], ignore_index=True)
    assert avisos_do_dia(precos, cal, cal[0], ["AAAA3"], PARAMS) == []


def test_poucas_acoes_sem_pares_nao_avisa():
    cal = pregoes_uteis(6)
    precos = precos_de("IBOV", cal, [100, 101, 102, 101, 103, 104])
    assert avisos_do_dia(precos, cal, cal[-1], [], PARAMS) == []


def _folha(valor, status):
    return {"valor": valor, "status": status}


def _mercado(usdbrl=(None, "indisponivel"), ipca=(None, "historico_insuficiente")):
    return {
        "IBOV": {"fechamento": _folha(100.0, "ok"), "variacao_dia": _folha(0.01, "ok"), "unidade": "pontos"},
        "USDBRL": {"fechamento": _folha(usdbrl[0], usdbrl[1]), "variacao_dia": _folha(None, "indisponivel"),
                   "unidade": "BRL/USD"},
        "BRENT": {"fechamento": _folha(80.0, "ok"), "variacao_dia": _folha(0.0, "ok"), "unidade": "USD/barril"},
        "cdi_dia": _folha(0.1, "ok"),
        "cdi_data": "2025-01-09",
        "ipca_12m": _folha(None, ipca[1]),
    }


def _acao(ticker, pvp=(None, "indisponivel"), d1=(0.01, "ok")):
    return {
        "ticker": ticker,
        "cotacao": {"fechamento": _folha(10.0, "ok"), "variacao_dia": _folha(0.01, "ok")},
        "rentabilidade": {"d1": _folha(d1[0], d1[1]), "m1": _folha(0.02, "ok")},
        "volume": {"total": _folha(1000.0, "ok")},
        "volatilidade_20d": _folha(0.2, "ok"),
        "beta": _folha(1.0, "ok"),
        "pvp": {"valor": pvp[0], "status": pvp[1], "setor": _folha(1.0, "ok")},
        "dividend_yield": _folha(0.05, "ok"),
    }


def test_indicador_vazio_de_mercado_ignora_historico_insuficiente():
    assert avisos_indicadores(_mercado(), None, T_MERCADO, PARAMS) == [
        "Checagem: indicador vazio em 2025-10-21: USDBRL.fechamento.",
    ]


def test_indicador_vazio_de_mercado_lista_cada_um_na_ordem():
    mercado = _mercado()
    mercado["BRENT"]["fechamento"] = _folha(None, "indisponivel")
    mercado["cdi_dia"] = _folha(None, "indisponivel")
    assert avisos_indicadores(mercado, None, T_MERCADO, PARAMS) == [
        "Checagem: indicador vazio em 2025-10-21: USDBRL.fechamento.",
        "Checagem: indicador vazio em 2025-10-21: BRENT.fechamento.",
        "Checagem: indicador vazio em 2025-10-21: cdi_dia.",
    ]


def test_indicador_vazio_em_todas_as_acoes():
    resumo = [_acao("AAAA3"), _acao("BBBB3")]
    assert avisos_indicadores(None, resumo, T_MERCADO, PARAMS) == [
        "Checagem: indicador vazio em todas as ações em 2025-10-21: pvp.",
    ]


def test_indicador_vazio_em_uma_acao_so_nao_avisa():
    resumo = [_acao("AAAA3"), _acao("BBBB3", pvp=(2.0, "ok"))]
    assert avisos_indicadores(None, resumo, T_MERCADO, PARAMS) == []


def test_historico_insuficiente_nao_conta_como_vazio():
    resumo = [_acao("AAAA3", d1=(None, "historico_insuficiente")), _acao("BBBB3", d1=(None, "historico_insuficiente"))]
    assert avisos_indicadores(None, resumo, T_MERCADO, PARAMS) == [
        "Checagem: indicador vazio em todas as ações em 2025-10-21: pvp.",
    ]


def test_sem_mercado_nem_resumo_nao_avisa():
    assert avisos_indicadores(None, None, T_MERCADO, PARAMS) == []
    assert avisos_indicadores(None, [], T_MERCADO, PARAMS) == []

