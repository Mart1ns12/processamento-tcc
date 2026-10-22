"""Camada de leitura (fontes.py): contrato, fusos, mudanças de ticker e intervalos.

Todos os testes usam SQLite em memória (fixture `banco_teste`), nunca o banco da coleta.
"""

from datetime import date

import pandas as pd
import pytest

from processamento import fontes
from processamento.fontes import SP, ErroLeitura

D1, D2, D3, D4 = date(2025, 10, 16), date(2025, 10, 17), date(2025, 10, 20), date(2025, 10, 21)
COLUNAS_PRECOS = {
    "data", "ticker", "abertura", "maxima", "minima",
    "fechamento", "fechamento_ajustado", "volume",
}


def _ts(texto: str) -> pd.Timestamp:
    return pd.Timestamp(texto)


def _afirmar_erro(chamada, *trechos):
    with pytest.raises(ErroLeitura) as info:
        chamada()
    for trecho in trechos:
        assert trecho in str(info.value)


def _sem_fechamento_ajustado(df):
    return df.drop(columns=["fechamento_ajustado"])


def _duplica_petr4_d1(df):
    linha = df[(df["data"] == "2025-10-16") & (df["ticker"] == "PETR4")]
    return pd.concat([df, linha], ignore_index=True)


def _fechamento_texto(df):
    df.loc[(df["data"] == "2025-10-16") & (df["ticker"] == "PETR4"), "fechamento"] = "abc"
    return df


def _data_no_formato_errado(df):
    df.loc[(df["data"] == "2025-10-16") & (df["ticker"] == "PETR4"), "data"] = "16/10/2025"
    return df


def _tipo_acao_invalido(df):
    df.loc[df["ticker"] == "PETR3", "tipo_acao"] = "XX"
    return df


def _data_hora_sem_fuso(df):
    df.loc[df["id"] == "n000001", "data_hora_publicacao"] = "2025-10-17T17:00:00"
    return df


def _fotos(carteiras: dict) -> pd.DataFrame:
    linhas = [(_ts(d), t) for d, tickers in carteiras.items() for t in tickers]
    return pd.DataFrame(linhas, columns=["data_carteira", "ticker"])


def _intervalos(df: pd.DataFrame) -> list:
    return [(t, i, None if pd.isna(f) else f) for t, i, f in df.itertuples(index=False, name=None)]


# --- tabelas e contrato -------------------------------------------------------------

def test_precos_colunas_e_datas(banco_teste):
    df = fontes.ler_tabela("precos", ler=banco_teste())
    # IBOV 4 + BRENT 5 + PETR3 4 + PETR4 4 + TAEE11 3 + ABEV3 4 + NOVA3 2 + JBSS32 4
    assert len(df) == 30
    assert set(df.columns) == COLUNAS_PRECOS
    assert pd.api.types.is_datetime64_any_dtype(df["data"])


def test_precos_filtro_por_periodo(banco_teste):
    df = fontes.ler_tabela("precos", desde=D2, ate=D3, ler=banco_teste())
    # o sábado 18/10 entra: o BRENT tem linha nele e o filtro é inclusivo de D2 a D3
    assert set(df["data"].dt.date) == {D2, date(2025, 10, 18), D3}


def test_cadastro_mantem_zero_a_esquerda_e_nulo(banco_teste):
    df = fontes.ler_tabela("cadastro", ler=banco_teste())
    assert df.loc[df["ticker"] == "TAEE11", "cnpj"].iloc[0] == "07859971000130"
    assert pd.isna(df.loc[df["ticker"] == "CRFB3", "cnpj"].iloc[0])


def test_erro_tabela_ausente(banco_teste):
    ler = banco_teste(omitir=frozenset({"v1-precos"}))
    _afirmar_erro(lambda: fontes.ler_tabela("precos", ler=ler), "v1-precos")


def test_erro_coluna_ausente(banco_teste):
    ler = banco_teste(alterar={"v1-precos": _sem_fechamento_ajustado})
    _afirmar_erro(
        lambda: fontes.ler_tabela("precos", ler=ler), "v1-precos", "fechamento_ajustado"
    )


def test_erro_chave_repetida(banco_teste):
    ler = banco_teste(alterar={"v1-precos": _duplica_petr4_d1})
    _afirmar_erro(lambda: fontes.ler_tabela("precos", ler=ler), "chave repetida", "data, ticker")


def test_erro_numero_invalido(banco_teste):
    ler = banco_teste(alterar={"v1-precos": _fechamento_texto})
    _afirmar_erro(lambda: fontes.ler_tabela("precos", ler=ler), "fechamento")


def test_erro_data_invalida(banco_teste):
    ler = banco_teste(alterar={"v1-precos": _data_no_formato_errado})
    _afirmar_erro(lambda: fontes.ler_tabela("precos", ler=ler), "data")


def test_erro_valor_fora_do_contrato(banco_teste):
    ler = banco_teste(alterar={"v1-cadastro": _tipo_acao_invalido})
    _afirmar_erro(lambda: fontes.ler_tabela("cadastro", ler=ler), "tipo_acao")


def test_erro_data_hora_sem_fuso(banco_teste):
    ler = banco_teste(alterar={"v1-noticias": _data_hora_sem_fuso})
    _afirmar_erro(lambda: fontes.ler_noticias(ler=ler), "data_hora_publicacao", "fuso")


# --- fusos e normalização -----------------------------------------------------------

def test_para_sao_paulo_iso_offset_e_utc_e_nulo():
    serie = pd.Series(["2025-10-17T17:00:00-03:00", "2025-10-17T20:00:00Z", None])
    out = fontes.para_sao_paulo_iso(serie, "teste")
    assert out.iloc[0] == pd.Timestamp("2025-10-17 17:00", tz=SP)
    assert out.iloc[1] == pd.Timestamp("2025-10-17 17:00", tz=SP)
    assert pd.isna(out.iloc[2])


def test_para_sao_paulo_de_utc():
    out = fontes.para_sao_paulo_de_utc(
        pd.Series(["2026-10-22 11:00:03.476873", "2026-10-21 00:46:43"])
    )
    assert out.iloc[0] == pd.Timestamp("2026-10-22 08:00:03.476873", tz=SP)
    assert out.iloc[1] == pd.Timestamp("2026-10-20 21:46:43", tz=SP)


def test_normalizar_ticker():
    out = fontes.normalizar_ticker(pd.Series([" petr4.sa ", "IBOV"]))
    assert list(out) == ["PETR4", "IBOV"]


def test_normalizar_cnpj():
    assert fontes.normalizar_cnpj(pd.Series(["33.000.167/0001-01"]), "x").iloc[0] == "33000167000101"
    with pytest.raises(ErroLeitura):
        fontes.normalizar_cnpj(pd.Series(["7859971000130"]), "x")


# --- mudanças de ticker -------------------------------------------------------------

def test_unir_historicos_fica_linha_com_ticker_novo():
    df = pd.DataFrame(
        {
            "data": [_ts("2025-10-16"), _ts("2025-10-17"), _ts("2025-10-17"), _ts("2025-10-20")],
            "ticker": ["ELET3", "ELET3", "AXIA3", "AXIA3"],
            "fechamento": [40.0, 41.0, 41.5, 42.0],
        }
    )
    out = fontes.unir_historicos(df, {"ELET3": "AXIA3"}, ["data", "ticker"])
    assert list(out.itertuples(index=False, name=None)) == [
        (_ts("2025-10-16"), "AXIA3", 40.0),
        (_ts("2025-10-17"), "AXIA3", 41.5),
        (_ts("2025-10-20"), "AXIA3", 42.0),
    ]


def test_ler_noticias_sem_momento_pregao_e_com_momento_ref(banco_teste):
    df = fontes.ler_noticias(ler=banco_teste())
    assert "momento_pregao" not in df.columns
    assert list(df.loc[df["id"] == "n000009", "ticker"]) == ["AXIA3"]
    momento = df.loc[df["id"] == "n000006", "momento_ref"].iloc[0]
    assert momento == pd.Timestamp("2025-10-17 23:59:59", tz=SP)


# --- intervalos ---------------------------------------------------------------------

def test_intervalos_de_fotos_caso_1():
    fotos = _fotos(
        {
            "2025-10-16": ["PETR3", "PETR4", "ABEV3"],
            "2025-10-20": ["PETR3", "TAEE11"],
            "2025-10-21": ["PETR3", "TAEE11", "NOVA3"],
        }
    )
    assert _intervalos(fontes.intervalos_de_fotos(fotos)) == [
        ("ABEV3", _ts("2025-10-16"), _ts("2025-10-19")),
        ("NOVA3", _ts("2025-10-21"), None),
        ("PETR3", _ts("2025-10-16"), None),
        ("PETR4", _ts("2025-10-16"), _ts("2025-10-19")),
        ("TAEE11", _ts("2025-10-20"), None),
    ]


def test_intervalos_de_fotos_caso_2_reentrada_abre_novo_intervalo():
    fotos = _fotos(
        {
            "2025-01-02": ["AAAA3", "BBBB3"],
            "2025-05-05": ["BBBB3"],
            "2025-09-01": ["AAAA3", "BBBB3"],
        }
    )
    assert _intervalos(fontes.intervalos_de_fotos(fotos)) == [
        ("AAAA3", _ts("2025-01-02"), _ts("2025-05-04")),
        ("AAAA3", _ts("2025-09-01"), None),
        ("BBBB3", _ts("2025-01-02"), None),
    ]


def test_intervalos_de_cadastro_nat_sem_limite():
    cadastro = pd.DataFrame(
        {
            "ticker": ["PETR4", "VALE3"],
            "entrada": ["2020-01-02", None],
            "saida": [None, "2024-06-30"],
        }
    )
    out = fontes.intervalos_de_cadastro(cadastro, "entrada", "saida")
    assert out["data_inicio"].iloc[0] == _ts("2020-01-02")
    assert pd.isna(out["data_fim"].iloc[0])
    assert pd.isna(out["data_inicio"].iloc[1])
    assert out["data_fim"].iloc[1] == _ts("2024-06-30")


def test_ler_composicao_sem_tabela_devolve_none(banco_teste):
    assert fontes.ler_composicao(ler=banco_teste(), existe=False) is None
