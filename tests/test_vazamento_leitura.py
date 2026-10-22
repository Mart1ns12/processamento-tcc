"""Vazamento temporal na camada de leitura (seções 6 e 7 da especificação).

Confere que, cortando o banco em uma data, nada posterior entra: preços, notícias,
classificação das janelas e universo. Usa só SQLite em memória (fixture `banco_teste`),
nunca o banco da coleta.
"""

from datetime import date

import pandas as pd
from pandas.testing import assert_frame_equal

from processamento import calendario, fontes, universo
from processamento.exclusoes import carregar_exclusoes
from processamento.fontes import SP

D1, D2, D3, D4 = date(2025, 10, 16), date(2025, 10, 17), date(2025, 10, 20), date(2025, 10, 21)


def _ate_sem_dia_seguinte(df):
    return df[df["data"] <= "2025-10-17"]


def _resumo_noticias(df: pd.DataFrame) -> dict:
    """id -> (janela, pregao_ref como date ou None), uma entrada por id."""
    saida = {}
    for linha in df.itertuples(index=False):
        ref = None if pd.isna(linha.pregao_ref) else pd.Timestamp(linha.pregao_ref).date()
        saida.setdefault(linha.id, set()).add((linha.janela, ref))
    return saida


# --- preços ----------------------------------------------------------------------------

def test_precos_ate_nao_traz_data_posterior(banco_teste):
    df = fontes.ler_tabela("precos", ate=D2, ler=banco_teste())
    assert df["data"].max() == pd.Timestamp(D2)


def test_precos_ate_igual_a_cortar_antes_da_leitura(banco_teste):
    com_corte = fontes.ler_tabela("precos", ate=D2, ler=banco_teste())
    cortado_antes = fontes.ler_tabela(
        "precos", ler=banco_teste(alterar={"v1-precos": _ate_sem_dia_seguinte})
    )
    assert_frame_equal(com_corte, cortado_antes)


# --- notícias --------------------------------------------------------------------------

def test_noticias_ate_08h_deixa_de_fora_o_que_e_posterior(banco_teste):
    df = fontes.ler_noticias(ate=pd.Timestamp("2025-10-20 08:00", tz=SP), ler=banco_teste())
    pares = set(zip(df["id"], df["ticker"]))
    assert pares == {
        ("n000001", "PETR4"),
        ("n000002", "PETR3"),
        ("n000002", "PETR4"),
        ("n000003", "PETR3"),
        ("n000004", "PETR4"),
        ("n000006", "TAEE11"),
        ("n000009", "AXIA3"),
    }


# --- classificação integrada (calendário + notícias) -----------------------------------

def test_calendario_so_com_pregoes_reais_do_ibov(banco_teste):
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=banco_teste()))
    # o sábado 18/10 tem BRENT, mas não IBOV: não é pregão
    assert cal == [D1, D2, D3, D4]


def test_classificacao_das_noticias_no_calendario_integrado(banco_teste):
    ler = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler))
    noticias = fontes.ler_noticias(ler=ler)
    classificadas = calendario.classificar_noticias(noticias, cal)
    resumo = _resumo_noticias(classificadas)
    assert resumo == {
        "n000001": {("pregao", D2)},
        "n000002": {("noite", D2)},
        "n000003": {("noite", D2)},
        "n000004": {("noite", D2)},
        "n000005": {("pre_abertura", D3)},
        "n000006": {("sem_horario", None)},
        "n000007": {("sem_horario", None)},
        "n000008": {("pre_abertura", D4)},
        "n000009": {("pregao", D1)},
    }


# --- universo --------------------------------------------------------------------------

def test_universo_ate_d2_coincide_com_o_universo_completo_ate_d2(banco_teste):
    ler_completo = banco_teste()
    ler_cortado = banco_teste()
    precos_completos = fontes.ler_tabela("precos", ler=ler_completo)
    precos_cortados = fontes.ler_tabela("precos", ate=D2, ler=ler_cortado)
    cadastro = fontes.ler_tabela("cadastro", ler=ler_completo)
    exclusoes = carregar_exclusoes()

    cal_cortado = calendario.pregoes(precos_cortados)
    cal_completo = calendario.pregoes(precos_completos)
    uni_cortado = universo.montar_universo(cal_cortado, cadastro, precos_cortados, exclusoes)
    uni_completo = universo.montar_universo(cal_completo, cadastro, precos_completos, exclusoes)

    ate_d2 = pd.Timestamp(D2)
    a = uni_cortado.loc[uni_cortado["data"] <= ate_d2].reset_index(drop=True)
    b = uni_completo.loc[uni_completo["data"] <= ate_d2].reset_index(drop=True)
    assert_frame_equal(a, b)


# --- janelas da noite ------------------------------------------------------------------

def test_janela_noite_termina_no_corte_da_manha_seguinte(banco_teste):
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=banco_teste()))
    testados = 0
    for t in cal:
        proximo = calendario.proximo_pregao(t, cal)
        if proximo is None:
            continue
        testados += 1
        inicio, fim = calendario.janela_noite(t, cal)
        assert inicio == calendario.fechamento(t)
        assert fim == calendario.corte_manha(proximo)
        assert fim <= pd.Timestamp(f"{proximo.isoformat()} 08:00", tz=SP)
    assert testados == len(cal) - 1
