"""Notícias "só data" (meia-noite do Pacífico): função pura, regra, janela e leitura de raw_articles.

Os valores esperados são montados à mão (calendário explícito). Nenhum teste usa banco ou rede:
`ler_raw_articles` roda sobre SQLite em memória.
"""

from datetime import date

import pandas as pd
import pytest
import sqlalchemy

from processamento import calendario, fontes
from processamento.fontes import SP, ErroLeitura

CAL = [
    date(2026, 1, 13), date(2026, 1, 14), date(2026, 1, 15),
    date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22),
    date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16),
]


def _sp(textos) -> pd.Series:
    """Série de instantes de São Paulo a partir de textos ("AAAA-MM-DD HH:MM:SS"); None vira NaT."""
    return pd.to_datetime(pd.Series(textos, dtype=object)).dt.tz_localize(SP)


def _sp1(texto: str) -> pd.Timestamp:
    return pd.Timestamp(texto, tz=SP)


def _noticias(linhas) -> pd.DataFrame:
    """Formato de `_tratar` (sem `momento_ref`): (id, origem, instante SP ou None, data de publicação)."""
    return pd.DataFrame(
        {
            "id": [l[0] for l in linhas],
            "ticker": ["AAAA3"] * len(linhas),
            "origem": [l[1] for l in linhas],
            "data_hora_publicacao": _sp([l[2] for l in linhas]),
            "data_publicacao": pd.to_datetime([l[3] for l in linhas]),
            "prob_positivo": [0.6] * len(linhas),
            "prob_negativo": [0.2] * len(linhas),
        }
    )


CASOS_SO_DATA = [
    (1, "google_news", "2026-07-15 04:00:00", "2026-07-15"),  # PDT: 00:00 em Los Angeles
    (2, "google_news", "2026-01-14 05:00:00", "2026-01-14"),  # PST: 00:00 em Los Angeles
    (3, "google_news", "2026-01-14 04:00:00", "2026-01-14"),  # 23:00 em LA: hora real
    (4, "google_news", "2026-07-15 04:00:01", "2026-07-15"),  # hora real
    (5, "google_news", "2026-07-15 10:30:00", "2026-07-15"),  # hora real
    (6, "google_news", "2026-06-19 04:00:00", "2026-06-19"),  # sexta, só data
    (7, "google_news", "2026-06-20 04:00:00", "2026-06-20"),  # sábado, só data
    (8, "cvm_ipe", None, "2026-07-15"),  # nunca teve horário
]


# --- meia_noite_pacifico ------------------------------------------------------------

def test_meia_noite_pacifico_casos_de_borda():
    instantes = _sp([
        "2026-07-15 04:00:00",  # PDT
        "2026-01-14 05:00:00",  # PST
        "2026-01-14 04:00:00",  # 23:00 LA
        "2026-07-15 04:00:01",
        "2026-07-15 10:30:00",
        "2026-07-15 05:00:00",  # 01:00 LA em PDT
        None,
    ])
    out = fontes.meia_noite_pacifico(instantes)
    assert list(out) == [True, True, False, False, False, False, False]
    assert out.dtype == bool


# --- aplicar_regra_so_data ----------------------------------------------------------

def test_regra_marca_precisao_e_ajusta_so_as_so_data():
    out = fontes.aplicar_regra_so_data(_noticias(CASOS_SO_DATA)).set_index("id")
    assert list(out["precisao_hora"]) == [
        "meia_noite_pacifico", "meia_noite_pacifico", "hora", "hora", "hora",
        "meia_noite_pacifico", "meia_noite_pacifico", "sem_hora",
    ]
    assert out.loc[1, "data_publicacao"] == pd.Timestamp("2026-07-15")
    assert pd.isna(out.loc[1, "data_hora_publicacao"])
    assert out.loc[1, "momento_ref"] == _sp1("2026-07-15 23:59:59")
    assert out.loc[7, "data_publicacao"] == pd.Timestamp("2026-06-20")
    assert out.loc[7, "momento_ref"] == _sp1("2026-06-20 23:59:59")
    assert out.loc[8, "momento_ref"] == _sp1("2026-07-15 23:59:59")
    # linhas "hora" ficam intactas
    assert out.loc[3, "data_hora_publicacao"] == _sp1("2026-01-14 04:00:00")
    assert out.loc[3, "momento_ref"] == _sp1("2026-01-14 04:00:00")
    assert out.loc[3, "data_publicacao"] == pd.Timestamp("2026-01-14")


def test_regra_e_idempotente():
    uma = fontes.aplicar_regra_so_data(_noticias(CASOS_SO_DATA))
    duas = fontes.aplicar_regra_so_data(uma)
    pd.testing.assert_frame_equal(uma, duas)


# --- janela com o calendário --------------------------------------------------------

def test_janela_so_data_segue_regra_das_sem_horario():
    out = fontes.aplicar_regra_so_data(_noticias([
        (1, "google_news", "2026-07-15 04:00:00", "2026-07-15"),
        (2, "google_news", "2026-01-14 05:00:00", "2026-01-14"),
        (3, "google_news", "2026-01-14 04:00:00", "2026-01-14"),
        (4, "google_news", "2026-07-15 04:00:01", "2026-07-15"),
        (5, "google_news", "2026-07-15 10:30:00", "2026-07-15"),
        (6, "google_news", "2026-06-19 04:00:00", "2026-06-19"),
        (7, "google_news", "2026-06-20 04:00:00", "2026-06-20"),
        (8, "cvm_ipe", None, "2026-07-15"),
    ]))
    # mesma montagem de preparar/classificar_para_modelo: sem horário usa momento_ref
    com_momento = out.assign(data_hora_publicacao=out["data_hora_publicacao"].fillna(out["momento_ref"]))
    classificado = calendario.classificar_noticias(com_momento, CAL).set_index("id")
    esperado = {
        1: ("noite", pd.Timestamp("2026-07-15")),
        2: ("noite", pd.Timestamp("2026-01-14")),
        3: ("noite", pd.Timestamp("2026-01-13")),
        4: ("noite", pd.Timestamp("2026-07-14")),
        5: ("pregao", pd.Timestamp("2026-07-15")),
        6: ("noite", pd.Timestamp("2026-06-19")),
        7: ("noite", pd.Timestamp("2026-06-19")),
        8: ("noite", pd.Timestamp("2026-07-15")),
    }
    for id_, (janela, ref) in esperado.items():
        assert classificado.loc[id_, "janela"] == janela, id_
        assert classificado.loc[id_, "pregao_ref"] == ref, id_
    assert classificado.loc[1, "data_hora_publicacao"] == _sp1("2026-07-15 23:59:59")


# --- ler_raw_articles ---------------------------------------------------------------

def _ler_com_raw_articles(linhas: pd.DataFrame):
    eng = sqlalchemy.create_engine("sqlite://")
    linhas.to_sql("raw_articles", eng, index=False)
    return lambda sql, params=None: fontes.executar_leitura(sql, params, engine=eng)


def test_ler_raw_articles_meia_noite_e_id_noticia():
    raw = pd.DataFrame({
        "id": [123, 124, 125],
        "lang": ["en", "pt", "pt"],
        "published_at": ["2026-07-15 07:00:00", "2026-01-14 08:00:00", "2026-01-14 07:00:00"],
        "published_precision": ["day", "day", "minute"],
        "origem": ["google_news", "google_news", "google_news"],
    })
    df = fontes.ler_raw_articles(ler=_ler_com_raw_articles(raw)).set_index("id")
    assert df.loc[123, "meia_noite_pacifico"] and df.loc[124, "meia_noite_pacifico"]
    assert not df.loc[125, "meia_noite_pacifico"]
    assert df.loc[123, "id_noticia"] == "n000123"
    assert df.loc[123, "publicado_em_sp"] == _sp1("2026-07-15 04:00:00")
    assert df.loc[123, "published_precision"] == "day"
    assert df.loc[125, "origem"] == "google_news"


def test_ler_raw_articles_erro_sem_tabela():
    eng = sqlalchemy.create_engine("sqlite://")
    ler = lambda sql, params=None: fontes.executar_leitura(sql, params, engine=eng)
    with pytest.raises(ErroLeitura, match="raw_articles"):
        fontes.ler_raw_articles(ler=ler)
