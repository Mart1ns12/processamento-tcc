"""Testes de fatos/noticias.py (etapa 7, fase 3): notícias da janela do painel, rótulo, destaque e resumo.

Gabarito do plano (docs/plano_etapa7.md, Fase 3), com a fábrica de notícias do experimento.
Nenhum teste usa banco ou rede.
"""

from datetime import date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from fabrica_experimento import noticias_de

from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.fatos.noticias import (
    COLUNAS_JANELA,
    destaque,
    ids_da_empresa,
    noticias_da_janela,
    resumo_noticias,
    rotulo,
)

SP = ZoneInfo("America/Sao_Paulo")
PARAMS = carregar_parametros_experimento()
CAL = [date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]
T = date(2026, 10, 22)
D = date(2026, 10, 23)
CNPJ_DE = {"AAAA3": "1", "AAAA4": "1", "BBBB3": "2", "CCCC3": "3"}
NAN = float("nan")


def sp(texto: str) -> pd.Timestamp:
    """Instante de São Paulo a partir de 'AAAA-MM-DD HH:MM[:SS]'."""
    return pd.Timestamp(texto).tz_localize(SP)


# (id, ticker, publicação (SP), dia, pp, pn, origem, papel, tipo), como o plano (Fase 3)
LINHAS_DO_PLANO = [
    ("n01", "AAAA4", sp("2026-10-22 08:00:00"), "2026-10-22", 0.5, 0.1, "google_news", None, None),
    ("n02", "AAAA4", sp("2026-10-22 08:00:01"), "2026-10-22", 0.70, 0.10, "google_news", None, None),
    ("n02", "AAAA3", sp("2026-10-22 08:00:01"), "2026-10-22", 0.70, 0.10, "google_news", None, None),
    ("n03", "AAAA3", sp("2026-10-22 14:30:00"), "2026-10-22", 0.05, 0.85, "google_news", "protagonista", None),
    ("n04", "AAAA4", sp("2026-10-22 17:00:00"), "2026-10-22", 0.30, 0.30, "google_news", None, None),
    ("n05", "AAAA3", sp("2026-10-22 19:42:00"), "2026-10-22", 0.60, 0.20, "google_news", None, None),
    ("n06", "AAAA3", sp("2026-10-22 04:00:00"), "2026-10-22", 0.10, 0.10, "google_news", None, None),
    ("n07", "AAAA3", None, "2026-10-22", 0.20, 0.30, "cvm_ipe", None, None),
    ("n08", "AAAA4", sp("2026-10-23 07:59:59"), "2026-10-23", 0.15, 0.70, "google_news", None, None),
    ("n09", "AAAA4", sp("2026-10-23 08:00:01"), "2026-10-23", 0.5, 0.1, "google_news", None, None),
    ("n10", "AAAA4", sp("2026-10-22 19:50:00"), "2026-10-22", 0.60, 0.20, "google_news", None, None),
    ("n11", "BBBB3", sp("2026-10-22 11:00:00"), "2026-10-22", 0.50, 0.10, "google_news", None, None),
]


def _com_colunas_de_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta fonte e link (como `fontes.ler_noticias`) e troca o título de n10 pelo de n05 (E10)."""
    df = df.assign(fonte="Fonte X", link=[f"https://exemplo.invalid/{i}" for i in df["id"]])
    return df.assign(titulo=df["titulo"].where(df["id"] != "n10", "titulo n05"))


def _noticias_do_plano() -> pd.DataFrame:
    return _com_colunas_de_texto(noticias_de(LINHAS_DO_PLANO))


def _janela(noticias=None, t=T, proximo=D) -> pd.DataFrame:
    base = _noticias_do_plano() if noticias is None else noticias
    return noticias_da_janela(base, CAL, t, proximo, CNPJ_DE, {}, PARAMS)


def _da_empresa(janela: pd.DataFrame, empresa: str) -> pd.DataFrame:
    return janela[janela["empresa"] == empresa]


# ---------------------------------------------------------------- rótulo


@pytest.mark.parametrize(
    "pp, pneu, pneg, esperado",
    [
        (0.5, 0.3, 0.2, "positivo"),
        (0.2, 0.3, 0.5, "negativo"),
        (0.4, 0.2, 0.4, "neutro"),
        (0.4, 0.4, 0.2, "neutro"),
        (0.3, 0.4, 0.3, "neutro"),
    ],
)
def test_rotulo_maior_probabilidade_e_empates_viram_neutro(pp, pneu, pneg, esperado):
    assert rotulo(pp, pneu, pneg) == esperado


def test_rotulo_com_probabilidade_ausente_fica_none():
    assert rotulo(float("nan"), 0.5, 0.5) is None
    assert rotulo(0.5, None, 0.2) is None


# ---------------------------------------------------------------- gabarito unitário (7 notícias da empresa 1)


def test_empresa_1_ids_na_ordem_do_destaque():
    janela = _janela()
    assert ids_da_empresa(janela, "1") == ["n03", "n02", "n08", "n05", "n07", "n06", "n04"]


def test_empresa_1_fora_da_janela_e_repetidas_nao_entram():
    ids = ids_da_empresa(_janela(), "1")
    for fora in ("n01", "n09", "n10"):
        assert fora not in ids


def test_empresa_1_resumo():
    janela = _janela()
    resumo = resumo_noticias(_da_empresa(janela, "1"), True)
    assert resumo["quantidade"] == (7.0, "ok")
    assert resumo["positivas"] == (2.0, "ok")
    assert resumo["neutras"] == (3.0, "ok")
    assert resumo["negativas"] == (2.0, "ok")
    valor, status = resumo["tom_medio"]
    assert status == "ok"
    assert valor == pytest.approx(-0.45 / 7, abs=1e-12)


def test_mesmo_id_em_dois_codigos_da_empresa_conta_uma_vez():
    janela = _janela()
    assert len(_da_empresa(janela, "1").query("id == 'n02'")) == 1


def test_empresa_2_so_n11_positivo():
    janela = _janela()
    assert ids_da_empresa(janela, "2") == ["n11"]
    assert _da_empresa(janela, "2")["rotulo"].tolist() == ["positivo"]


def test_empresa_sem_noticia_tem_contagens_zero_e_tom_nao_se_aplica():
    janela = _janela()
    assert ids_da_empresa(janela, "3") == []
    resumo = resumo_noticias(_da_empresa(janela, "3"), True)
    assert resumo["quantidade"] == (0.0, "ok")
    assert resumo["positivas"] == (0.0, "ok")
    assert resumo["neutras"] == (0.0, "ok")
    assert resumo["negativas"] == (0.0, "ok")
    valor, status = resumo["tom_medio"]
    assert np.isnan(valor)
    assert status == "nao_se_aplica"


def test_sem_cobertura_tudo_indisponivel():
    resumo = resumo_noticias(_da_empresa(_janela(), "1"), False)
    assert set(resumo) == {"quantidade", "positivas", "neutras", "negativas", "tom_medio"}
    for valor, status in resumo.values():
        assert np.isnan(valor)
        assert status == "indisponivel"


# ---------------------------------------------------------------- janela, janela do painel e bordas


def test_janela_do_painel_por_precisao_de_hora():
    janela = _janela().set_index("id")
    assert janela.loc["n06", "janela"] == "sem_horario"
    assert janela.loc["n07", "janela"] == "sem_horario"
    assert janela.loc["n02", "janela"] == "pregao"
    assert janela.loc["n05", "janela"] == "noite"
    assert janela.loc["n08", "janela"] == "noite"
    assert janela.loc["n06", "precisao_hora"] == "meia_noite_pacifico"
    assert janela.loc["n07", "precisao_hora"] == "sem_hora"
    assert pd.isna(janela.loc["n06", "publicado_em"])
    assert pd.isna(janela.loc["n07", "publicado_em"])
    assert janela.loc["n02", "publicado_em"] == sp("2026-10-22 08:00:01")


def test_colunas_da_janela():
    assert list(_janela().columns) == COLUNAS_JANELA


def test_rotulo_e_score_das_notas():
    janela = _janela().set_index("id")
    assert janela.loc["n03", "rotulo"] == "negativo"
    assert janela.loc["n03", "score"] == pytest.approx(-0.8)
    assert janela.loc["n02", "rotulo"] == "positivo"
    assert janela.loc["n04", "rotulo"] == "neutro"
    assert janela.loc["n07", "rotulo"] == "neutro"
    assert janela.loc["n07", "score"] == pytest.approx(-0.1)
    assert janela.loc["n02", "status"] == "ok"


def test_08_do_dia_d_entra_e_08_e_1_nao_entra():
    extra = ("n12", "AAAA4", sp("2026-10-23 08:00:00"), "2026-10-23", 0.3, 0.3, "google_news", None, None)
    noticias = _com_colunas_de_texto(noticias_de(LINHAS_DO_PLANO + [extra]))
    ids = ids_da_empresa(_janela(noticias), "1")
    assert "n12" in ids
    assert "n09" not in ids


def test_point_in_time_t_anterior_so_a_noite_de_t():
    janela = _janela(t=date(2026, 10, 21), proximo=date(2026, 10, 22))
    assert ids_da_empresa(janela, "1") == ["n01"]


# ---------------------------------------------------------------- probabilidade ausente e vazio


def test_probabilidade_ausente_gera_status_indisponivel():
    noticias = _noticias_do_plano()
    noticias = noticias.assign(prob_positivo=noticias["prob_positivo"].where(noticias["id"] != "n05", np.nan))
    janela = _janela(noticias)
    linha = janela.set_index("id").loc["n05"]
    assert linha["status"] == "indisponivel"
    assert linha["rotulo"] is None
    resumo = resumo_noticias(_da_empresa(janela, "1"), True)
    assert resumo["quantidade"] == (7.0, "ok")
    assert np.isnan(resumo["positivas"][0])
    assert resumo["positivas"][1] == "indisponivel"
    assert resumo["tom_medio"][1] == "indisponivel"


def test_sem_noticias_devolve_janela_vazia():
    vazias = _noticias_do_plano().iloc[0:0]
    janela = _janela(vazias)
    assert janela.empty
    assert ids_da_empresa(janela, "1") == []


# ---------------------------------------------------------------- destaque (critérios, sem pipeline)


def test_destaque_protagonista_depois_score_depois_momento_depois_id():
    df = pd.DataFrame({
        "id": ["b", "a", "c", "d", "e"],
        "protagonista": [False, False, False, True, False],
        "score": [0.2, -0.5, 0.5, 0.0, 0.5],
        "momento": pd.to_datetime([
            "2026-10-22 09:00", "2026-10-22 10:00", "2026-10-22 11:00",
            "2026-10-22 08:00", "2026-10-22 11:00",
        ]),
    })
    ordenado = destaque(df)
    assert ordenado["id"].tolist() == ["d", "c", "e", "a", "b"]
    assert ordenado["destaque"].tolist() == [1, 2, 3, 4, 5]


def test_destaque_de_empresa_vazia():
    assert destaque(_janela().iloc[0:0]).empty


def test_resumo_de_empresa_vazia_com_cobertura():
    resumo = resumo_noticias(_janela().iloc[0:0], True)
    assert resumo["quantidade"] == (0.0, "ok")
    assert resumo["tom_medio"][1] == "nao_se_aplica"
