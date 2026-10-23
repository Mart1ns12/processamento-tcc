"""Testes de processamento/fatos/fundamentos.py: valor de mercado e indicadores por empresa (F3a).

As fotos saem de foto_balanco sobre a fábrica em T = 2026-03-31 (tests/fabrica_fundamentos.py),
com os valores da seção F3a do plano da etapa 4. Nenhum teste usa banco ou rede.
"""

import math
from datetime import date

import pytest

from fabrica_fundamentos import (
    CNPJ,
    EXCL,
    LINHAS_A,
    LINHAS_BANC,
    LINHAS_D,
    LINHAS_D2,
    LINHAS_PREJ,
    T,
    balanco_de,
    mundo,
)
from processamento.fatos.fundamentos import LUCRO_NEGATIVO, indicadores_empresa, valor_de_mercado
from processamento.fatos.precos import HIST, INDISPONIVEL, NAO_SE_APLICA, OK
from processamento.fatos.trimestres import ESTOQUE, FLUXO, FotoBalanco, foto_balanco

NAN = math.nan
CADASTRO = mundo()[0]

A = balanco_de(CNPJ["A"], LINHAS_A)
PREJ = balanco_de(CNPJ["PREJ"], LINHAS_PREJ)
BANC = balanco_de(CNPJ["BANC"], LINHAS_BANC)
D = balanco_de(CNPJ["D"], LINHAS_D)
D2 = balanco_de(CNPJ["D"], LINHAS_D2)

CHAVES = {
    "pl.valor", "pvp.valor", "roe.valor", "payout.valor", "margem_bruta.valor",
    "margem_liquida.valor", "ebitda.valor_12m", "ebitda.margem", "endividamento.divida_liquida",
    "endividamento.dl_pl", "endividamento.dl_ebitda", "endividamento.caixa_liquido",
}


def _par(par, valor, status):
    """Confere um par (valor, status). `valor` None significa NaN esperado (status diferente de ok)."""
    v, s = par
    assert s == status
    if valor is None:
        assert math.isnan(v)
    else:
        assert v == pytest.approx(valor, rel=1e-9)


def _foto_a_mao(base=OK, fluxo=None, estoque=None) -> FotoBalanco:
    """Foto montada à mão: tudo indisponivel, exceto o que for dado em `fluxo` e `estoque`."""
    fluxo_12m = {c: (NAN, INDISPONIVEL) for c in FLUXO}
    fluxo_12m.update(fluxo or {})
    estoque_fim = {c: (NAN, INDISPONIVEL) for c in ESTOQUE}
    estoque_fim.update(estoque or {})
    return FotoBalanco(
        status_base=base,
        data_fim_periodo=None,
        data_entrega=None,
        fluxo_12m=fluxo_12m,
        fluxo_trimestre={},
        estoque=estoque_fim,
    )


def _todas_indisponiveis(resultado, status=INDISPONIVEL):
    """Todas as chaves com (NaN, status)."""
    assert set(resultado) == CHAVES
    for chave in CHAVES:
        _par(resultado[chave], None, status)


# ---------------------------------------------------------------------------
# valor_de_mercado
# ---------------------------------------------------------------------------

def test_valor_de_mercado_on_e_pn():
    fech = {"AAAA3": 10.0, "AAAA4": 8.0}
    r = valor_de_mercado(CNPJ["A"], fech, CADASTRO, ["AAAA3", "AAAA4"], (60, 40, OK))
    _par(r, 920.0, OK)


def test_valor_de_mercado_on_e_pn_sem_preco_de_uma_classe():
    fech = {"AAAA3": 10.0, "AAAA4": NAN}
    r = valor_de_mercado(CNPJ["A"], fech, CADASTRO, ["AAAA3", "AAAA4"], (60, 40, OK))
    _par(r, None, INDISPONIVEL)


def test_valor_de_mercado_unit():
    r = valor_de_mercado(CNPJ["U"], {"UUUU11": 30.0}, CADASTRO, ["UUUU11"], (100, 200, OK))
    _par(r, 3000.0, OK)


def test_valor_de_mercado_unit_sem_composicao():
    cadastro = CADASTRO.copy()
    cadastro.loc[cadastro["ticker"] == "UUUU11", "unit_qtd_on"] = NAN
    r = valor_de_mercado(CNPJ["U"], {"UUUU11": 30.0}, cadastro, ["UUUU11"], (100, 200, OK))
    _par(r, None, INDISPONIVEL)


def test_valor_de_mercado_so_pn():
    r = valor_de_mercado(CNPJ["BANC"], {"BANC4": 20.0}, CADASTRO, ["BANC4"], (50, 50, OK))
    _par(r, 2000.0, OK)


def test_valor_de_mercado_so_pn_dupn():
    r = valor_de_mercado(CNPJ["DUPN"], {"DUPN5": 6.0}, CADASTRO, ["DUPN5"], (100, 300, OK))
    _par(r, 2400.0, OK)


def test_valor_de_mercado_bdr_fica_indisponivel():
    r = valor_de_mercado(CNPJ["BDRX"], {"BDRX32": 50.0}, CADASTRO, ["BDRX32"], (100, 0, OK))
    _par(r, None, INDISPONIVEL)


def test_valor_de_mercado_quantidade_indisponivel():
    r = valor_de_mercado(CNPJ["A"], {"AAAA3": 10.0, "AAAA4": 8.0}, CADASTRO, ["AAAA3", "AAAA4"],
                         (NAN, NAN, INDISPONIVEL))
    _par(r, None, INDISPONIVEL)


def test_valor_de_mercado_quantidade_zero():
    r = valor_de_mercado(CNPJ["A"], {"AAAA3": 10.0, "AAAA4": 8.0}, CADASTRO, ["AAAA3", "AAAA4"],
                         (0, 0, OK))
    _par(r, None, INDISPONIVEL)


def test_valor_de_mercado_sem_cnpj():
    r = valor_de_mercado(None, {"AAAA3": 10.0, "AAAA4": 8.0}, CADASTRO, ["AAAA3", "AAAA4"], (60, 40, OK))
    _par(r, None, INDISPONIVEL)


# ---------------------------------------------------------------------------
# indicadores_empresa
# ---------------------------------------------------------------------------

def test_indicadores_empresa_a():
    foto = foto_balanco(A, CNPJ["A"], T, EXCL)
    r = indicadores_empresa(foto, (920.0, OK), (52.5, OK), False)
    assert set(r) == CHAVES
    _par(r["pl.valor"], 5.75, OK)
    _par(r["pvp.valor"], 0.7076923076923077, OK)
    _par(r["roe.valor"], 0.12307692307692308, OK)
    _par(r["payout.valor"], 0.328125, OK)
    _par(r["margem_bruta.valor"], 0.41333333333333333, OK)
    _par(r["margem_liquida.valor"], 0.10666666666666667, OK)
    for chave in CHAVES - {"pl.valor", "pvp.valor", "roe.valor", "payout.valor",
                           "margem_bruta.valor", "margem_liquida.valor"}:
        _par(r[chave], None, INDISPONIVEL)


def test_indicadores_prejuizo_mantem_pl_e_zera_payout():
    foto = foto_balanco(PREJ, CNPJ["PREJ"], T, EXCL)
    r = indicadores_empresa(foto, (400.0, OK), (10.0, OK), False)
    _par(r["pl.valor"], -5.0, LUCRO_NEGATIVO)
    _par(r["payout.valor"], None, LUCRO_NEGATIVO)
    _par(r["roe.valor"], -0.06153846153846154, OK)
    _par(r["margem_liquida.valor"], -0.05333333333333334, OK)


def test_indicadores_lucro_zero_pl_e_payout_sem_valor():
    foto = _foto_a_mao(
        fluxo={"lucro_liquido": (0.0, OK), "receita_liquida": (100.0, OK)},
        estoque={"patrimonio_liquido": (1000.0, OK)},
    )
    r = indicadores_empresa(foto, (500.0, OK), (10.0, OK), False)
    _par(r["pl.valor"], None, LUCRO_NEGATIVO)
    _par(r["payout.valor"], None, LUCRO_NEGATIVO)


def test_indicadores_banco_financeiro():
    foto = foto_balanco(BANC, CNPJ["BANC"], T, EXCL)
    r = indicadores_empresa(foto, (2000.0, OK), (0.0, OK), True)
    _par(r["pl.valor"], 12.5, OK)
    _par(r["pvp.valor"], 1.5384615384615385, OK)
    _par(r["roe.valor"], 0.12307692307692308, OK)
    _par(r["payout.valor"], 0.0, OK)
    for chave in ("margem_bruta.valor", "margem_liquida.valor", "ebitda.valor_12m", "ebitda.margem",
                  "endividamento.divida_liquida", "endividamento.dl_pl", "endividamento.dl_ebitda",
                  "endividamento.caixa_liquido"):
        _par(r[chave], None, NAO_SE_APLICA)


def test_indicadores_empresa_sem_balanco_cnpj_excluido():
    foto = foto_balanco(A, CNPJ["SEMB"], T, EXCL)
    r = indicadores_empresa(foto, (500.0, OK), (0.0, OK), False)
    _todas_indisponiveis(r)


def test_indicadores_empresa_sem_linhas():
    foto = foto_balanco(A, CNPJ["NOBA"], T, EXCL)
    r = indicadores_empresa(foto, (500.0, OK), (0.0, OK), False)
    _todas_indisponiveis(r)


def test_indicadores_empresa_d_com_divida():
    foto = foto_balanco(D, CNPJ["D"], T, EXCL)
    r = indicadores_empresa(foto, (900.0, OK), (0.0, OK), False)
    _par(r["pl.valor"], 20.0, OK)
    _par(r["pvp.valor"], 1.6666666666666667, OK)
    _par(r["roe.valor"], 0.08333333333333333, OK)
    _par(r["payout.valor"], 0.0, OK)
    _par(r["margem_bruta.valor"], 0.40476190476190477, OK)
    _par(r["margem_liquida.valor"], 0.10714285714285714, OK)
    _par(r["ebitda.valor_12m"], 111.0, OK)
    _par(r["ebitda.margem"], 0.2642857142857143, OK)
    _par(r["endividamento.divida_liquida"], 100.0, OK)
    _par(r["endividamento.dl_pl"], 0.18518518518518517, OK)
    _par(r["endividamento.dl_ebitda"], 0.9009009009009009, OK)
    _par(r["endividamento.caixa_liquido"], 0.0, OK)


def _foto_divida(emp_cp, emp_lp, aplic=50.0):
    """PL 1000, caixa 100, EBIT 12m 200 + D&A 50 (EBITDA 250); empréstimos e aplicações dados."""
    return _foto_a_mao(
        fluxo={"ebit": (200.0, OK), "depreciacao_amortizacao": (50.0, OK)},
        estoque={
            "patrimonio_liquido": (1000.0, OK),
            "emprestimos_curto_prazo": (emp_cp, OK),
            "emprestimos_longo_prazo": (emp_lp, OK),
            "caixa": (100.0, OK),
            "aplicacoes_financeiras": (aplic, OK),
        },
    )


def test_emprestimos_cp_e_lp_zero_juntos_viram_indisponivel():
    r = indicadores_empresa(_foto_divida(0.0, 0.0), (NAN, INDISPONIVEL), (NAN, INDISPONIVEL), False)
    for chave in ("endividamento.divida_liquida", "endividamento.dl_pl",
                  "endividamento.dl_ebitda", "endividamento.caixa_liquido"):
        _par(r[chave], None, INDISPONIVEL)
    _par(r["ebitda.valor_12m"], 250.0, OK)  # o EBITDA não depende dos empréstimos


@pytest.mark.parametrize("emp_cp, emp_lp, aplic, dl", [
    (0.0, 500.0, 50.0, 350.0),   # só o CP = 0: vale (0 + 500 − 100 − 50)
    (300.0, 0.0, 50.0, 150.0),   # só o LP = 0: vale (300 + 0 − 100 − 50)
    (300.0, 500.0, 0.0, 700.0),  # aplicações = 0: vale (300 + 500 − 100 − 0)
])
def test_um_emprestimo_zero_ou_aplicacoes_zero_continuam_valendo(emp_cp, emp_lp, aplic, dl):
    r = indicadores_empresa(_foto_divida(emp_cp, emp_lp, aplic), (NAN, INDISPONIVEL),
                            (NAN, INDISPONIVEL), False)
    _par(r["endividamento.divida_liquida"], dl, OK)
    _par(r["endividamento.dl_pl"], dl / 1000.0, OK)
    _par(r["endividamento.dl_ebitda"], dl / 250.0, OK)
    _par(r["endividamento.caixa_liquido"], 0.0, OK)


def test_indicadores_empresa_d2_caixa_liquido():
    foto = foto_balanco(D2, CNPJ["D"], T, EXCL)
    r = indicadores_empresa(foto, (900.0, OK), (0.0, OK), False)
    _par(r["endividamento.divida_liquida"], -20.0, OK)
    _par(r["endividamento.dl_pl"], -0.037037037037037035, OK)
    _par(r["endividamento.dl_ebitda"], -0.18018018018018017, OK)
    _par(r["endividamento.caixa_liquido"], 1.0, OK)


def test_indicadores_empresa_a_em_2025_08_09_historico_insuficiente():
    foto = foto_balanco(A, CNPJ["A"], date(2025, 8, 9), EXCL)
    r = indicadores_empresa(foto, (920.0, OK), (52.5, OK), False)
    _par(r["pl.valor"], None, HIST)
    _par(r["roe.valor"], None, HIST)
    _par(r["margem_bruta.valor"], None, HIST)
    _par(r["margem_liquida.valor"], None, HIST)
    _par(r["payout.valor"], None, HIST)
    _par(r["pvp.valor"], 0.8, OK)
    _par(r["ebitda.valor_12m"], None, INDISPONIVEL)


def test_indicadores_empresa_a_com_vm_indisponivel():
    foto = foto_balanco(A, CNPJ["A"], T, EXCL)
    r = indicadores_empresa(foto, (NAN, INDISPONIVEL), (52.5, OK), False)
    _par(r["pl.valor"], None, INDISPONIVEL)
    _par(r["pvp.valor"], None, INDISPONIVEL)
    _par(r["roe.valor"], 0.12307692307692308, OK)


def test_indicadores_patrimonio_negativo_nao_se_aplica():
    foto = _foto_a_mao(
        fluxo={"lucro_liquido": (50.0, OK), "receita_liquida": (1000.0, OK)},
        estoque={"patrimonio_liquido": (-100.0, OK)},
    )
    r = indicadores_empresa(foto, (1000.0, OK), (0.0, OK), False)
    _par(r["pl.valor"], 20.0, OK)
    _par(r["pvp.valor"], None, NAO_SE_APLICA)
    _par(r["roe.valor"], None, NAO_SE_APLICA)


def test_indicadores_receita_zero_margens_indisponiveis():
    foto = _foto_a_mao(
        fluxo={"receita_liquida": (0.0, OK), "lucro_bruto": (50.0, OK), "lucro_liquido": (10.0, OK)},
        estoque={"patrimonio_liquido": (1000.0, OK)},
    )
    r = indicadores_empresa(foto, (1000.0, OK), (0.0, OK), False)
    _par(r["margem_bruta.valor"], None, INDISPONIVEL)
    _par(r["margem_liquida.valor"], None, INDISPONIVEL)


def test_indicadores_ebitda_negativo_dl_ebitda_nao_se_aplica():
    foto = _foto_a_mao(
        fluxo={
            "receita_liquida": (500.0, OK),
            "lucro_liquido": (50.0, OK),
            "ebit": (-30.0, OK),
            "depreciacao_amortizacao": (10.0, OK),
        },
        estoque={
            "patrimonio_liquido": (1000.0, OK),
            "emprestimos_curto_prazo": (50.0, OK),
            "emprestimos_longo_prazo": (100.0, OK),
            "caixa": (10.0, OK),
            "aplicacoes_financeiras": (5.0, OK),
        },
    )
    r = indicadores_empresa(foto, (1000.0, OK), (0.0, OK), False)
    _par(r["ebitda.valor_12m"], -20.0, OK)
    _par(r["endividamento.dl_ebitda"], None, NAO_SE_APLICA)
