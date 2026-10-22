"""Testes de processamento/fatos/proventos.py: ligação de proventos, yield, ações e payout.

Usa a fábrica de tests/fabrica_fundamentos.py (empresas A, U, PREJ, BANC, SEMB, NOBA, D, BDRX,
DUPN, EXTI e K; KKKK6 virou KKKK3, com `mudancas`). Nenhum teste usa banco ou rede.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from fabrica_fundamentos import CNPJ, T, acoes_de, mundo, proventos_de
from processamento.fatos.precos import INDISPONIVEL, OK
from processamento.fatos.proventos import (
    acoes_disponiveis,
    acoes_na_data,
    dividend_yield,
    inicio_janela,
    lista_proventos,
    ligar_proventos,
    soma_por_ano,
    total_pago,
)


def _cenario(extra_mudancas=None, extra_proventos=None, t=T):
    """Mundo da fábrica com `mudancas` (e linhas extras opcionais) ligado e com ações disponíveis em t.

    Devolve (cadastro, precos, ligados, disponiveis).
    """
    cadastro, balancos, acoes, proventos, precos, _, mudancas = mundo()
    if extra_proventos is not None:
        proventos = pd.concat([proventos, extra_proventos], ignore_index=True)
    mudancas = {**mudancas, **(extra_mudancas or {})}
    ligados = ligar_proventos(proventos, cadastro, mudancas)
    disponiveis = acoes_disponiveis(acoes, balancos, t)
    return cadastro, precos, ligados, disponiveis


def _linhas(ligados: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Linhas de proventos do código original `ticker`."""
    return ligados[ligados["ticker"] == ticker]


def _tipo(cadastro: pd.DataFrame, ticker: str) -> str:
    """Tipo de ação do ticker no cadastro da fábrica."""
    return cadastro.loc[cadastro["ticker"] == ticker, "tipo_acao"].iloc[0]


def _fech(precos: pd.DataFrame, ticker: str) -> float:
    """Cotação (fechamento) constante do ticker no mundo da fábrica."""
    return precos.loc[precos["ticker"] == ticker, "fechamento"].iloc[0]


def test_inicio_janela_recua_doze_meses():
    assert inicio_janela(T, 12) == pd.Timestamp("2025-03-31")
    assert inicio_janela(date(2026, 3, 10), 12) == pd.Timestamp("2025-03-10")


# ligar_proventos

@pytest.mark.parametrize(
    "ticker, emp, ligacao, tipo_classe",
    [
        ("AAAA3", "A", "cadastro", "ON"),
        ("UUUU3", "U", "raiz", "ON"),
        ("UUUU11", "U", "cadastro", "UNIT"),
        ("DUPN6", "DUPN", "raiz", "PN"),
        ("EXTI6", "EXTI", "raiz", "PN"),
        ("BDRX32", "BDRX", "cadastro", "BDR"),
    ],
)
def test_ligar_proventos_tabela(ticker, emp, ligacao, tipo_classe):
    _, _, ligados, _ = _cenario()
    linhas = _linhas(ligados, ticker)
    assert len(linhas) >= 1
    assert (linhas["cnpj"] == CNPJ[emp]).all()
    assert (linhas["ligacao"] == ligacao).all()
    assert (linhas["tipo_classe"] == tipo_classe).all()


def test_ligar_kkkk6_vira_kkkk3_mas_nao_conta_na_classe():
    _, _, ligados, _ = _cenario()
    linhas = _linhas(ligados, "KKKK6")
    assert len(linhas) == 2
    assert (linhas["ticker_atual"] == "KKKK3").all()
    assert (linhas["cnpj"] == CNPJ["K"]).all()
    assert (linhas["tipo_classe"] == "PN").all()
    assert not linhas["mesma_classe"].any()
    assert not linhas["duplicada"].any()
    assert not linhas["conta_no_ticker"].any()


def test_ligar_proventos_troca_para_outra_empresa_e_sem_empresa():
    cadastro, _, _, _ = _cenario()
    proventos = proventos_de([
        ("VELH3", "DIVIDENDO", "2025-09-10", 0.30, None),
        ("ZZZZ3", "DIVIDENDO", "2025-06-01", 0.10, None),
    ])
    ligados = ligar_proventos(proventos, cadastro, {"VELH3": "EXTI3"})
    velh = ligados.loc[ligados["ticker"] == "VELH3"].iloc[0]
    assert velh["ticker_atual"] == "EXTI3"
    assert velh["cnpj"] == CNPJ["EXTI"]
    assert velh["tipo_classe"] == "ON"
    zzzz = ligados.loc[ligados["ticker"] == "ZZZZ3"].iloc[0]
    assert pd.isna(zzzz["cnpj"])  # ausência: None ou NaN (o pandas guarda como NaN)
    assert zzzz["ligacao"] == "sem_empresa"


def test_mesma_classe_velh3_para_exti3_conta_e_colide():
    extra = proventos_de([
        ("VELH3", "DIVIDENDO", "2025-09-10", 0.30, None),
        ("VELH3", "DIVIDENDO", "2025-05-20", 0.99, None),
    ])
    _, precos, ligados, disponiveis = _cenario({"VELH3": "EXTI3"}, extra)
    setembro = ligados.loc[(ligados["ticker"] == "VELH3") & (ligados["data_com"] == "2025-09-10")].iloc[0]
    maio = ligados.loc[(ligados["ticker"] == "VELH3") & (ligados["data_com"] == "2025-05-20")].iloc[0]
    assert setembro["mesma_classe"] and setembro["conta_no_ticker"]
    assert not setembro["duplicada"]
    assert maio["mesma_classe"] and maio["duplicada"]
    assert not maio["conta_no_ticker"]
    # yield de EXTI3: 0.40 + 0.30 (VELH3, set) + 0.50 sobre a cotação 12 em 12 meses
    valor, status = dividend_yield(ligados, "EXTI3", "ON", _fech(precos, "EXTI3"), T, 12)
    assert status == OK
    assert valor == pytest.approx(0.1, rel=1e-9)
    # total pago: 137 + 0.30 * 100 (o 0.99 de maio é duplicado e não entra)
    total, status = total_pago(ligados, disponiveis, CNPJ["EXTI"], inicio_janela(T, 12), T)
    assert status == OK
    assert total == pytest.approx(167.0, rel=1e-9)


# yield (k)

@pytest.mark.parametrize(
    "ticker, esperado",
    [
        ("AAAA3", 0.05),
        ("AAAA4", 0.06875),
        ("UUUU11", 0.08),
        ("DUPN5", 0.07),
        ("EXTI3", 0.075),
        ("PREJ3", 0.025),
        ("SEMB3", 0.05),
        ("DDDD3", 0.0),
    ],
)
def test_dividend_yield_com_janela_de_doze_meses(ticker, esperado):
    cadastro, precos, ligados, _ = _cenario()
    valor, status = dividend_yield(ligados, ticker, _tipo(cadastro, ticker), _fech(precos, ticker), T, 12)
    assert status == OK
    assert valor == pytest.approx(esperado, rel=1e-9)


def test_dividend_yield_kkkk3_ignora_kkkk6():
    cadastro, precos, ligados, _ = _cenario()
    valor, status = dividend_yield(ligados, "KKKK3", "ON", _fech(precos, "KKKK3"), T, 12)
    assert status == OK
    assert valor == pytest.approx(0.013, rel=1e-9)


def test_dividend_yield_indisponivel_para_bdr_e_cotacao_invalida():
    _, precos, ligados, _ = _cenario()
    valor, status = dividend_yield(ligados, "BDRX32", "BDR", 50, T, 12)
    assert math.isnan(valor) and status == INDISPONIVEL
    for fech in (float("nan"), 0.0, -1.0):
        valor, status = dividend_yield(ligados, "AAAA3", "ON", fech, T, 12)
        assert math.isnan(valor) and status == INDISPONIVEL


# acoes_disponiveis e acoes_na_data

def test_acoes_disponiveis_respeita_data_de_entrega():
    cadastro, balancos, acoes, _, _, _, _ = mundo()
    em_t = acoes_disponiveis(acoes, balancos, T)
    exti_t = em_t[em_t["cnpj"] == CNPJ["EXTI"]]
    assert len(exti_t) == 2
    antes = acoes_disponiveis(acoes, balancos, date(2026, 3, 10))
    exti_antes = antes[antes["cnpj"] == CNPJ["EXTI"]]
    assert list(exti_antes["data_referencia"]) == [pd.Timestamp("2025-03-31")]
    assert CNPJ["SEMB"] not in set(em_t["cnpj"])


def test_acoes_na_data_exti_em_t():
    _, _, _, disponiveis = _cenario()
    cnpj = CNPJ["EXTI"]
    assert acoes_na_data(disponiveis, cnpj, "2025-02-10") == (100.0, 50.0, OK)  # fallback (D3)
    assert acoes_na_data(disponiveis, cnpj, "2025-05-20") == (100.0, 50.0, OK)
    assert acoes_na_data(disponiveis, cnpj, "2025-12-31") == (150.0, 0.0, OK)
    assert acoes_na_data(disponiveis, cnpj, "2026-01-20") == (150.0, 0.0, OK)


def test_acoes_na_data_sem_linhas_ou_com_quantidade_ausente():
    disponiveis = acoes_de([(CNPJ["EXTI"], "2025-03-31", None, 50)])
    on, pn, status = acoes_na_data(disponiveis, CNPJ["EXTI"], "2025-05-20")
    assert math.isnan(on) and math.isnan(pn) and status == INDISPONIVEL
    _, _, _, disp = _cenario()
    on, pn, status = acoes_na_data(disp, CNPJ["SEMB"], "2025-05-20")
    assert math.isnan(on) and math.isnan(pn) and status == INDISPONIVEL


# total_pago (f)

@pytest.mark.parametrize(
    "emp, esperado",
    [("A", 52.5), ("U", 240.0), ("DUPN", 126.0), ("EXTI", 137.0), ("D", 0.0), ("NOBA", 0.0)],
)
def test_total_pago_janela_de_doze_meses_em_t(emp, esperado):
    _, _, ligados, disponiveis = _cenario()
    total, status = total_pago(ligados, disponiveis, CNPJ[emp], date(2025, 3, 31), T)
    assert status == OK
    assert total == pytest.approx(esperado, rel=1e-9)


def test_total_pago_sem_ações_disponiveis_e_indisponivel():
    _, _, ligados, disponiveis = _cenario()
    total, status = total_pago(ligados, disponiveis, CNPJ["SEMB"], date(2025, 3, 31), T)
    assert math.isnan(total) and status == INDISPONIVEL


def test_total_pago_exti_com_t_antes_da_dfp():
    t = date(2026, 3, 10)
    _, _, ligados, disponiveis = _cenario(t=t)
    total, status = total_pago(ligados, disponiveis, CNPJ["EXTI"], inicio_janela(t, 12), t)
    assert status == OK
    assert total == pytest.approx(112.0, rel=1e-9)


def test_total_pago_exercicios_de_a():
    _, _, ligados, disponiveis = _cenario()
    total, status = total_pago(ligados, disponiveis, CNPJ["A"], date(2023, 12, 31), date(2024, 12, 31))
    assert status == OK
    assert total == pytest.approx(42.0, rel=1e-9)
    total, status = total_pago(ligados, disponiveis, CNPJ["A"], date(2024, 12, 31), date(2025, 12, 31))
    assert status == OK
    assert total == pytest.approx(102.0, rel=1e-9)


def test_total_pago_kkkk_conta_kkkk6_como_pn():
    _, _, ligados, disponiveis = _cenario()
    total, status = total_pago(ligados, disponiveis, CNPJ["K"], date(2025, 3, 31), T)
    assert status == OK
    assert total == pytest.approx(51.0, rel=1e-9)
    t = date(2026, 3, 10)
    _, _, ligados, disponiveis = _cenario(t=t)
    total, status = total_pago(ligados, disponiveis, CNPJ["K"], inicio_janela(t, 12), t)
    assert status == OK
    assert total == pytest.approx(41.0, rel=1e-9)


# soma_por_ano e lista_proventos

def test_soma_por_ano_aaaa3_cinco_anos():
    _, _, ligados, _ = _cenario()
    df = soma_por_ano(ligados, "AAAA3", "ON", T, 5)
    assert list(df["ano"]) == [2022, 2023, 2024, 2025, 2026]
    assert list(df["valor"]) == pytest.approx([0.0, 0.0, 0.40, 1.49, 0.0], rel=1e-9)
    assert set(df["status"]) == {OK}


def test_soma_por_ano_kkkk3_sem_kkkk6():
    _, _, ligados, _ = _cenario()
    df = soma_por_ano(ligados, "KKKK3", "ON", T, 5)
    assert list(df["valor"]) == pytest.approx([0.0, 0.0, 0.0, 0.08, 0.05], rel=1e-9)


def test_soma_por_ano_bdr_indisponivel():
    _, _, ligados, _ = _cenario()
    df = soma_por_ano(ligados, "BDRX32", "BDR", T, 5)
    assert len(df) == 5
    assert df["valor"].isna().all()
    assert set(df["status"]) == {INDISPONIVEL}


def test_lista_proventos_aaaa3_ate_t():
    _, _, ligados, _ = _cenario()
    df = lista_proventos(ligados, ["AAAA3"], T)
    assert len(df) == 4
    assert list(df["data_com"]) == [
        pd.Timestamp("2024-05-10"),
        pd.Timestamp("2025-03-31"),
        pd.Timestamp("2025-04-15"),
        pd.Timestamp("2025-10-15"),
    ]


def test_lista_proventos_kkkk3_sem_kkkk6():
    _, _, ligados, _ = _cenario()
    df = lista_proventos(ligados, ["KKKK3"], T)
    assert len(df) == 2
    assert list(df["valor_por_acao"]) == pytest.approx([0.08, 0.05], rel=1e-9)
    assert set(df["ticker"]) == {"KKKK3"}


def test_acoes_disponiveis_com_tabela_vazia():
    from fabrica_fundamentos import acoes_de, balanco_de, LINHAS_A, CNPJ
    from processamento.fatos.proventos import acoes_disponiveis, acoes_na_data

    disp = acoes_disponiveis(acoes_de([]), balanco_de(CNPJ["A"], LINHAS_A), "2026-03-31")
    assert disp.empty and "cnpj" in disp.columns
    _, _, status = acoes_na_data(disp, CNPJ["A"], "2026-03-31")
    assert status == "indisponivel"
