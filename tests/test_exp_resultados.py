"""Testes dos dias de resultado (processamento/experimento/resultados.py)."""

from datetime import date

import pandas as pd

from processamento.experimento.resultados import dias_de_resultado

CAL = [date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)]


def _balancos():
    return pd.DataFrame({
        "cnpj": ["1", "1", "2", "3", "4", "5"],
        "tipo": ["ITR", "ITR", "DFP", "ITR", "ITR", "ITR"],
        "data_entrega": pd.to_datetime(
            ["2026-06-18", "2026-06-18", "2026-06-20", "2026-06-22", None, "2026-06-17"]
        ),
    })


def _pares(df):
    return set(zip(df["data"], df["empresa"]))


def test_sem_proximo_ao_vivo_entrega_na_noite_de_t():
    resultado, contagens = dias_de_resultado(_balancos(), CAL)
    assert _pares(resultado) == {
        (pd.Timestamp("2026-06-18"), "1"),
        (pd.Timestamp("2026-06-19"), "2"),
    }
    assert len(resultado) == 2  # as duas linhas do CNPJ 1 viram uma só
    assert list(resultado.columns) == ["data", "empresa"]
    assert contagens == {"sem_data": 1, "fora": 2}


def test_com_proximo_ao_vivo_entra_a_entrega_de_22():
    resultado, contagens = dias_de_resultado(_balancos(), CAL, proximo_ao_vivo=date(2026, 6, 23))
    assert _pares(resultado) == {
        (pd.Timestamp("2026-06-18"), "1"),
        (pd.Timestamp("2026-06-19"), "2"),
        (pd.Timestamp("2026-06-22"), "3"),
    }
    assert contagens == {"sem_data": 1, "fora": 1}


def test_sem_balancos_devolve_tabela_vazia_com_colunas():
    vazio = _balancos().iloc[0:0]
    resultado, contagens = dias_de_resultado(vazio, CAL)
    assert resultado.empty
    assert list(resultado.columns) == ["data", "empresa"]
    assert contagens == {"sem_data": 0, "fora": 0}


def test_linha_de_periodo_invalido_nao_gera_dia_de_resultado():
    # ITR de 31 dias (linha lixo, seção 6) entregue na noite de 18/06: não conta; a ITR válida conta.
    balancos = pd.DataFrame({
        "cnpj": ["1", "1", "2"],
        "tipo_documento": ["ITR", "ITR", "ITR"],
        "data_inicio_periodo": pd.to_datetime(["2026-03-01", "2026-01-01", "2026-04-01"]),
        "data_fim_periodo": pd.to_datetime(["2026-03-31", "2026-03-31", "2026-06-30"]),
        "data_entrega": pd.to_datetime(["2026-06-18", "2026-06-19", "2026-06-19"]),
    })
    resultado, contagens = dias_de_resultado(balancos, CAL)
    assert _pares(resultado) == {(pd.Timestamp("2026-06-19"), "1"), (pd.Timestamp("2026-06-19"), "2")}
    assert contagens == {"sem_data": 0, "fora": 0}
