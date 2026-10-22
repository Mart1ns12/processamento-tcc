"""Testes de tabela_trimestral (F4, pacote 5 da seção 8.3).

Mundo de tests/fabrica_fundamentos.py em T = 2026-03-31. Valores da seção F4 do plano da etapa 4
e do caso da empresa K (troca de ticker KKKK6 -> KKKK3, payout 0.225 em 2025-12-31). Sem banco e sem rede.
"""

from datetime import date

import pandas as pd
import pytest

from fabrica_fundamentos import CNPJ, EXCL, T, mundo
from processamento.fatos.fundamentos import (
    CAMPOS_TRIMESTRAIS,
    LUCRO_NEGATIVO,
    DadosFundamentos,
    carregar_parametros_fundamentos,
    tabela_trimestral,
)
from processamento.fatos.precos import HIST, INDISPONIVEL, NAO_SE_APLICA, OK

STATUS_VALIDOS = {OK, NAO_SE_APLICA, INDISPONIVEL, HIST, LUCRO_NEGATIVO}

CADASTRO, BALANCOS, ACOES, PROVENTOS, PRECOS, CAL, MUDANCAS = mundo()
DADOS = DadosFundamentos(
    precos=PRECOS,
    cadastro=CADASTRO,
    balancos=BALANCOS,
    acoes_emitidas=ACOES,
    proventos=PROVENTOS,
    mudancas=MUDANCAS,
)
PARAMS = carregar_parametros_fundamentos()

FINS_A = ["2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]


@pytest.fixture(scope="module")
def tabela():
    return tabela_trimestral(T, DADOS, EXCL, PARAMS)


def _linha(tabela, ticker, fim):
    """Linha do ticker no trimestre que termina em `fim` (exatamente uma)."""
    sel = tabela[(tabela["ticker"] == ticker) & (tabela["data_fim_periodo"] == pd.Timestamp(fim))]
    assert len(sel) == 1, (ticker, fim)
    return sel.iloc[0]


def _confere(linha, campo, status, esperado=None):
    """Status do campo; com status ok, valor aproximado. Com status diferente de ok, valor NaN."""
    valor, st = linha[campo], linha[f"{campo}_status"]
    assert st == status, (campo, st)
    if status == OK:
        assert valor == pytest.approx(esperado, rel=1e-9), campo
    else:
        assert pd.isna(valor), campo


def test_colunas_da_tabela(tabela):
    esperado = ["ticker", "cnpj", "data_fim_periodo", "data_entrega"]
    for campo in CAMPOS_TRIMESTRAIS:
        esperado += [campo, f"{campo}_status"]
    assert list(tabela.columns) == esperado
    assert CAMPOS_TRIMESTRAIS == (
        "receita_trimestre", "receita_12m", "lucro_liquido_trimestre", "lucro_liquido_12m",
        "margem_bruta", "margem_liquida", "roe", "ebitda_trimestre", "ebitda_12m",
        "margem_ebitda", "divida_liquida", "dl_pl", "dl_ebitda", "payout_12m",
    )


def test_aaaa3_e_aaaa4_tem_seis_trimestres(tabela):
    fins = [pd.Timestamp(f) for f in FINS_A]
    for ticker in ["AAAA3", "AAAA4"]:
        do = tabela[tabela["ticker"] == ticker]
        assert list(do["data_fim_periodo"]) == fins, ticker
        assert (do["cnpj"] == CNPJ["A"]).all(), ticker


def test_aaaa3_2025_12_31(tabela):
    linha = _linha(tabela, "AAAA3", "2025-12-31")
    assert linha["data_entrega"] == pd.Timestamp("2026-03-15")
    _confere(linha, "receita_trimestre", OK, 410)
    _confere(linha, "lucro_liquido_trimestre", OK, 40)
    _confere(linha, "receita_12m", OK, 1500)
    _confere(linha, "lucro_liquido_12m", OK, 160)
    _confere(linha, "margem_bruta", OK, 0.41333333333333333)
    _confere(linha, "margem_liquida", OK, 0.10666666666666667)
    _confere(linha, "roe", OK, 0.12307692307692308)
    _confere(linha, "payout_12m", OK, 0.6375)


def test_aaaa3_2025_09_30(tabela):
    linha = _linha(tabela, "AAAA3", "2025-09-30")
    _confere(linha, "receita_trimestre", OK, 380)
    _confere(linha, "receita_12m", OK, 1490)
    _confere(linha, "lucro_liquido_12m", OK, 160)
    _confere(linha, "margem_bruta", OK, 0.3959731543624161)
    _confere(linha, "margem_liquida", OK, 0.10738255033557047)
    _confere(linha, "roe", OK, 0.128)
    _confere(linha, "payout_12m", OK, 0.50625)


def test_aaaa3_2025_06_30(tabela):
    linha = _linha(tabela, "AAAA3", "2025-06-30")
    _confere(linha, "receita_trimestre", OK, 360)
    _confere(linha, "receita_12m", OK, 1410)
    _confere(linha, "lucro_liquido_12m", OK, 145)
    _confere(linha, "margem_bruta", OK, 0.3900709219858156)
    _confere(linha, "margem_liquida", OK, 0.10283687943262411)
    _confere(linha, "roe", OK, 0.12083333333333333)
    _confere(linha, "payout_12m", OK, 0.5586206896551724)


def test_aaaa3_2025_03_31_sem_quatro_trimestres(tabela):
    linha = _linha(tabela, "AAAA3", "2025-03-31")
    _confere(linha, "receita_trimestre", OK, 350)
    _confere(linha, "lucro_liquido_trimestre", OK, 35)
    for campo in ["receita_12m", "lucro_liquido_12m", "margem_bruta", "margem_liquida", "roe", "payout_12m"]:
        _confere(linha, campo, HIST)


def test_aaaa3_2024_trimestres_e_historico_insuficiente(tabela):
    for fim, receita, lucro in [("2024-09-30", 300, 30), ("2024-12-31", 400, 40)]:
        linha = _linha(tabela, "AAAA3", fim)
        _confere(linha, "receita_trimestre", OK, receita)
        _confere(linha, "lucro_liquido_trimestre", OK, lucro)
        for campo in ["receita_12m", "lucro_liquido_12m", "margem_bruta", "margem_liquida", "roe", "payout_12m"]:
            _confere(linha, campo, HIST)
    # Data de entrega do trimestre de 2024-12-31: a DFP de 2024, entregue em 2025-03-20.
    assert _linha(tabela, "AAAA3", "2024-12-31")["data_entrega"] == pd.Timestamp("2025-03-20")


def test_aaaa3_ebitda_e_divida_indisponiveis(tabela):
    for fim in FINS_A:
        linha = _linha(tabela, "AAAA3", fim)
        for campo in ["ebitda_trimestre", "ebitda_12m", "margem_ebitda",
                      "divida_liquida", "dl_pl", "dl_ebitda"]:
            _confere(linha, campo, INDISPONIVEL)


def test_dddd3_2025_12_31(tabela):
    linha = _linha(tabela, "DDDD3", "2025-12-31")
    _confere(linha, "receita_trimestre", OK, 120)
    _confere(linha, "ebitda_trimestre", OK, 33)
    _confere(linha, "ebitda_12m", OK, 111)
    _confere(linha, "margem_ebitda", OK, 111 / 420)
    _confere(linha, "divida_liquida", OK, 100)
    _confere(linha, "dl_pl", OK, 100 / 540)
    _confere(linha, "dl_ebitda", OK, 100 / 111)
    _confere(linha, "payout_12m", OK, 0.0)


def test_dddd3_trimestres_anteriores(tabela):
    linha = _linha(tabela, "DDDD3", "2025-09-30")
    _confere(linha, "ebitda_trimestre", OK, 27)
    _confere(linha, "ebitda_12m", HIST)
    _confere(linha, "margem_ebitda", HIST)
    _confere(linha, "divida_liquida", OK, 150)
    _confere(linha, "dl_pl", OK, 150 / 520)
    _confere(linha, "dl_ebitda", HIST)
    _confere(linha, "payout_12m", HIST)

    linha = _linha(tabela, "DDDD3", "2025-06-30")
    _confere(linha, "ebitda_trimestre", OK, 26)
    _confere(linha, "divida_liquida", OK, 150)
    _confere(linha, "dl_pl", OK, 150 / 510)

    linha = _linha(tabela, "DDDD3", "2025-03-31")
    _confere(linha, "ebitda_trimestre", OK, 25)
    _confere(linha, "dl_pl", OK, 0.3)
    _confere(linha, "ebitda_12m", HIST)


def test_banc4_financeira(tabela):
    linha = _linha(tabela, "BANC4", "2025-12-31")
    for campo in ["ebitda_trimestre", "ebitda_12m", "margem_bruta", "margem_liquida",
                  "margem_ebitda", "divida_liquida", "dl_pl", "dl_ebitda"]:
        _confere(linha, campo, NAO_SE_APLICA)
    _confere(linha, "roe", OK, 160 / 1300)


def test_bdrx32_payout_indisponivel_e_margens_ok(tabela):
    do = tabela[tabela["ticker"] == "BDRX32"]
    assert len(do) == 4
    linha = _linha(tabela, "BDRX32", "2025-12-31")
    _confere(linha, "payout_12m", INDISPONIVEL)
    _confere(linha, "margem_bruta", OK, 170 / 420)
    _confere(linha, "margem_liquida", OK, 45 / 420)
    assert (do["payout_12m_status"] != OK).all()


def test_semb3_e_noba3_sem_linhas(tabela):
    assert not tabela["ticker"].isin(["SEMB3", "NOBA3"]).any()


def test_kkkk3_payout_com_troca_de_ticker(tabela):
    # Janela (2024-12-31, 2025-12-31]: 0.04*200 + 0.08*100 + 0.10*200 = 36; 36 / 160.
    # A JCP de 2026-01-20 fica fora. KKKK6 (PN) entra pela troca de ticker, não vira linha própria.
    linha = _linha(tabela, "KKKK3", "2025-12-31")
    _confere(linha, "lucro_liquido_12m", OK, 160)
    _confere(linha, "payout_12m", OK, 0.225)
    linha = _linha(tabela, "KKKK3", "2025-06-30")
    _confere(linha, "payout_12m", OK, 36 / 145)
    assert "KKKK6" not in set(tabela["ticker"])


def test_status_e_valor_coerentes(tabela):
    for campo in CAMPOS_TRIMESTRAIS:
        status = tabela[f"{campo}_status"]
        assert set(status) <= STATUS_VALIDOS, campo
        assert ((status == OK) == tabela[campo].notna()).all(), campo


def test_nada_depois_de_t(tabela):
    assert (tabela["data_entrega"] <= pd.Timestamp(T)).all()
    assert (tabela["data_fim_periodo"] <= pd.Timestamp(T)).all()


def test_t_antes_da_dfp_nao_mostra_o_quarto_trimestre():
    tab = tabela_trimestral(date(2025, 12, 15), DADOS, EXCL, PARAMS)
    do = tab[tab["ticker"] == "AAAA3"]
    assert do["data_fim_periodo"].max() == pd.Timestamp("2025-09-30")
    assert (do["data_entrega"] <= pd.Timestamp("2025-12-15")).all()
    _confere(_linha(tab, "AAAA3", "2025-09-30"), "payout_12m", OK, 0.50625)
    _confere(_linha(tab, "KKKK3", "2025-09-30"), "payout_12m", OK, 0.225)


def test_cnpj_nan_nao_gera_linha():
    cadastro = CADASTRO.copy()
    cadastro.loc[cadastro["ticker"] == "AAAA4", "cnpj"] = float("nan")
    dados = DadosFundamentos(
        precos=PRECOS, cadastro=cadastro, balancos=BALANCOS, acoes_emitidas=ACOES,
        proventos=PROVENTOS, mudancas=MUDANCAS,
    )
    tab = tabela_trimestral(T, dados, EXCL, PARAMS)
    assert "AAAA4" not in set(tab["ticker"])
    assert len(tab[tab["ticker"] == "AAAA3"]) == 6
    assert not any(pd.isna(c) for c in tab["cnpj"])
