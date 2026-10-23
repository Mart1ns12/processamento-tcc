"""Testes das janelas de notícias e do fuso horário do experimento (etapa 5, Fase 2).

Só testam `processamento/calendario.py` e `processamento/fontes.py` como estão, com o
`parametros.yaml` real. Nenhum teste usa banco ou rede.
"""

from datetime import date

import pandas as pd
import pytest

from processamento.calendario import SP, classificar_noticias, janela_noite, janela_pregao
from processamento.fontes import para_sao_paulo_de_utc, para_sao_paulo_iso

CAL = [
    date(2026, 2, 13),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 3, 6),
    date(2026, 3, 9),
    date(2026, 3, 10),
    date(2026, 4, 2),
    date(2026, 4, 6),
    date(2026, 4, 20),
    date(2026, 4, 22),
    date(2026, 6, 3),
    date(2026, 6, 5),
    date(2026, 6, 18),
    date(2026, 6, 19),
    date(2026, 6, 22),
    date(2026, 6, 23),
    date(2026, 10, 30),
    date(2026, 11, 3),
    date(2026, 11, 4),
]


def _sp(texto: str) -> pd.Timestamp:
    """Instante de São Paulo a partir de 'AAAA-MM-DD HH:MM[:SS]'."""
    return pd.Timestamp(texto).tz_localize(SP)


def _classificar(instantes: list[pd.Timestamp], proximo: date | None = None) -> pd.DataFrame:
    """Classifica os instantes (tz de São Paulo) com o CAL do teste."""
    df = pd.DataFrame({"data_hora_publicacao": instantes})
    return classificar_noticias(df, CAL, proximo_ao_vivo=proximo)


# --- classificar_noticias: janela e pregão de referência -----------------------------------

# (instante em SP, janela esperada, pregão de referência esperado ou None, proximo_ao_vivo)
CASOS_CLASSIFICACAO = [
    ("2026-06-18 16:59:59", "pregao", "2026-06-18", None),
    ("2026-06-18 17:00:00", "pregao", "2026-06-18", None),
    ("2026-06-18 17:00:01", "noite", "2026-06-18", None),
    ("2026-06-18 19:42:00", "noite", "2026-06-18", None),
    ("2026-06-19 08:00:00", "noite", "2026-06-18", None),
    ("2026-06-19 08:00:01", "pre_abertura", "2026-06-19", None),
    ("2026-06-19 09:59:59", "pre_abertura", "2026-06-19", None),
    ("2026-06-19 10:00:00", "pregao", "2026-06-19", None),
    ("2026-06-19 17:30:00", "noite", "2026-06-19", None),
    ("2026-06-20 12:00:00", "noite", "2026-06-19", None),
    ("2026-06-22 07:59:59", "noite", "2026-06-19", None),
    ("2026-06-22 08:00:00", "noite", "2026-06-19", None),
    ("2026-06-22 08:00:01", "pre_abertura", "2026-06-22", None),
    ("2026-03-06 17:30:00", "pregao", "2026-03-06", None),
    ("2026-03-06 18:00:01", "noite", "2026-03-06", None),
    ("2026-03-09 17:30:00", "noite", "2026-03-09", None),
    ("2026-10-30 17:30:00", "noite", "2026-10-30", None),
    ("2026-11-02 12:00:00", "noite", "2026-10-30", None),
    ("2026-11-03 08:00:00", "noite", "2026-10-30", None),
    ("2026-11-03 17:30:00", "pregao", "2026-11-03", None),
    ("2026-11-03 18:00:01", "noite", "2026-11-03", None),
    ("2026-02-16 15:00:00", "noite", "2026-02-13", None),
    ("2026-02-18 08:00:00", "noite", "2026-02-13", None),
    ("2026-02-18 10:30:00", "pre_abertura", "2026-02-18", None),
    ("2026-02-18 13:00:00", "pregao", "2026-02-18", None),
    ("2026-02-18 17:30:00", "pregao", "2026-02-18", None),
    ("2026-02-18 18:00:01", "noite", "2026-02-18", None),
    ("2026-04-03 10:00:00", "noite", "2026-04-02", None),
    ("2026-04-06 08:00:00", "noite", "2026-04-02", None),
    ("2026-04-21 20:00:00", "noite", "2026-04-20", None),
    ("2026-06-04 09:00:00", "noite", "2026-06-03", None),
    ("2026-06-05 08:00:01", "pre_abertura", "2026-06-05", None),
    ("2026-06-19 23:59:59", "noite", "2026-06-19", None),
    ("2026-06-20 23:59:59", "noite", "2026-06-19", None),
    ("2026-06-22 23:59:59", "noite", "2026-06-22", None),
    ("2026-11-04 19:00:00", "fora_do_calendario", None, None),
    ("2026-11-04 19:00:00", "noite", "2026-11-04", date(2026, 11, 5)),
    ("2026-11-05 08:00:01", "fora_do_calendario", None, None),
    ("2026-11-05 08:00:01", "fora_do_calendario", None, date(2026, 11, 5)),
]


@pytest.mark.parametrize(
    "instante, janela, pregao, proximo",
    CASOS_CLASSIFICACAO,
    ids=[f"{c[0]}|{c[1]}|proximo={c[3]}" for c in CASOS_CLASSIFICACAO],
)
def test_classificar_noticias_casos_da_tabela(instante, janela, pregao, proximo):
    saida = _classificar([_sp(instante)], proximo)
    assert saida["janela"].iloc[0] == janela
    ref = saida["pregao_ref"].iloc[0]
    if pregao is None:
        assert pd.isna(ref)
    else:
        assert ref == pd.Timestamp(pregao)


# --- janela_noite e janela_pregao ----------------------------------------------------------

CASOS_JANELA_NOITE = [
    (date(2026, 6, 19), "2026-06-19 17:00", "2026-06-22 08:00"),
    (date(2026, 4, 2), "2026-04-02 17:00", "2026-04-06 08:00"),
    (date(2026, 6, 3), "2026-06-03 17:00", "2026-06-05 08:00"),
    (date(2026, 4, 20), "2026-04-20 17:00", "2026-04-22 08:00"),
    (date(2026, 2, 13), "2026-02-13 18:00", "2026-02-18 08:00"),
    (date(2026, 10, 30), "2026-10-30 17:00", "2026-11-03 08:00"),
    (date(2026, 3, 6), "2026-03-06 18:00", "2026-03-09 08:00"),
    (date(2026, 3, 9), "2026-03-09 17:00", "2026-03-10 08:00"),
    (date(2026, 11, 3), "2026-11-03 18:00", "2026-11-04 08:00"),
]


@pytest.mark.parametrize("t, inicio, fim", CASOS_JANELA_NOITE, ids=[str(c[0]) for c in CASOS_JANELA_NOITE])
def test_janela_noite(t, inicio, fim):
    assert janela_noite(t, CAL) == (_sp(inicio), _sp(fim))


def test_janela_pregao_dia_especial_de_cinzas():
    assert janela_pregao(date(2026, 2, 18), CAL) == (_sp("2026-02-18 13:00"), _sp("2026-02-18 18:00"))


# --- fuso horário -------------------------------------------------------------------------


def test_para_sao_paulo_iso_converte_os_tres_formatos_para_o_mesmo_instante():
    serie = pd.Series(["2026-06-18T19:42:00-03:00", "2026-06-18T22:42:00Z", "2026-06-18T22:42:00+00:00"])
    saida = para_sao_paulo_iso(serie, "teste")
    esperado = _sp("2026-06-18 19:42")
    assert str(saida.dt.tz) == "America/Sao_Paulo"
    for valor in saida:
        assert valor == esperado


@pytest.mark.parametrize(
    "utc, sp, janela, pregao",
    [
        ("2026-06-18 22:42:00", "2026-06-18 19:42:00", "noite", "2026-06-18"),
        ("2026-06-19 02:30:00", "2026-06-18 23:30:00", "noite", "2026-06-18"),
        ("2026-06-19 10:59:59", "2026-06-19 07:59:59", "noite", "2026-06-18"),
        ("2026-06-19 11:00:01", "2026-06-19 08:00:01", "pre_abertura", "2026-06-19"),
    ],
)
def test_para_sao_paulo_de_utc_e_classificacao(utc, sp, janela, pregao):
    serie = para_sao_paulo_de_utc(pd.Series([utc]))
    assert serie.iloc[0] == _sp(sp)
    saida = classificar_noticias(pd.DataFrame({"data_hora_publicacao": serie}), CAL)
    assert saida["janela"].iloc[0] == janela
    assert saida["pregao_ref"].iloc[0] == pd.Timestamp(pregao)
