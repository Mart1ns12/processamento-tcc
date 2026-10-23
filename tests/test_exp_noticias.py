"""Testes de experimento/noticias.py (etapa 5, fase 3): filtro de versão, empresa, duplicadas e janela.

Tabelas montadas à mão, tickers fictícios. Nenhum teste usa banco ou rede.
"""

import dataclasses
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from processamento.experimento.noticias import (
    COLUNAS_PREPARADAS,
    classificar_para_modelo,
    deduplicar,
    filtrar_versao,
    ligar_empresa,
    preparar_noticias,
)
from processamento.experimento.parametros import carregar_parametros_experimento

SP = ZoneInfo("America/Sao_Paulo")
PARAMS = carregar_parametros_experimento()
CAL = [date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)]
CNPJ_DE = {
    "XXXX3": "11111111000111",
    "XXXX4": "11111111000111",
    "YYYY3": "22222222000122",
    "SEMC3": None,
}


def sp(texto: str) -> pd.Timestamp:
    """Instante de São Paulo a partir de 'AAAA-MM-DD HH:MM[:SS]'."""
    return pd.Timestamp(texto).tz_localize(SP)


def nota(
    id_: int,
    ticker: str,
    *,
    hora: str | None = None,
    data: str = "2026-06-18",
    momento: str | None = None,
    titulo: str | None = "Titulo",
    pp: float | None = 0.5,
    pn: float | None = 0.2,
    origem: str | None = "google_news",
    papel: str | None = None,
    tipo: str | None = None,
) -> dict:
    """Uma linha no formato de `fontes.ler_noticias`. Sem `hora`, o momento vira 23:59:59 do dia."""
    if momento is None:
        momento = hora if hora is not None else f"{data} 23:59:59"
    return {
        "id": id_,
        "ticker": ticker,
        "data_hora_publicacao": sp(hora) if hora is not None else None,
        "data_publicacao": pd.Timestamp(data),
        "momento_ref": sp(momento),
        "titulo": titulo,
        "prob_positivo": pp,
        "prob_negativo": pn,
        "origem": origem,
        "papel": papel,
        "tipo_conteudo": tipo,
    }


def fazer(linhas: list[dict]) -> pd.DataFrame:
    """DataFrame com os tipos de `fontes.ler_noticias` (instantes tz-aware de São Paulo)."""
    df = pd.DataFrame(linhas)
    for coluna in ["data_hora_publicacao", "momento_ref"]:
        df[coluna] = pd.to_datetime(df[coluna], utc=True).dt.tz_convert(SP)
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"])
    return df


def com_empresa(linhas: list[dict]) -> pd.DataFrame:
    """Notícias já com a coluna `empresa` (sem mudanças de ticker)."""
    return ligar_empresa(fazer(linhas), CNPJ_DE, {})


def classificar(linhas: list[dict], params=PARAMS, proximo=None):
    """Classifica as linhas já com a coluna `empresa`, como o pipeline faz."""
    return classificar_para_modelo(com_empresa(linhas), CAL, proximo, params)


# ---------------------------------------------------------------- filtro de versão


def _sete_linhas() -> pd.DataFrame:
    return fazer(
        [
            nota(1, "AAAA3", origem="cvm_ipe"),
            nota(2, "AAAA3", tipo="reportagem", papel="protagonista"),
            nota(3, "AAAA3", tipo="reportagem", papel="citada_com_fato"),
            nota(4, "AAAA3", tipo="reportagem", papel="mencao"),
            nota(5, "AAAA3", tipo="opiniao", papel="protagonista"),
            nota(6, "AAAA3"),
            nota(7, "AAAA3", tipo="reportagem"),
        ]
    )


def test_filtro_principais_mantem_so_as_do_criterio():
    filtradas, info = filtrar_versao(_sete_linhas(), "principais", PARAMS)
    assert set(filtradas["id"]) == {1, 2, 3}
    assert info == {"lidas": 7, "fora_versao": 4, "papel_vazio_fora": 2}


def test_filtro_todas_mantem_tudo():
    filtradas, info = filtrar_versao(_sete_linhas(), "todas", PARAMS)
    assert len(filtradas) == 7
    assert info == {"lidas": 7, "fora_versao": 0, "papel_vazio_fora": 0}


def test_versao_invalida_levanta_erro():
    with pytest.raises(ValueError):
        filtrar_versao(_sete_linhas(), "xyz", PARAMS)


# ---------------------------------------------------------------- empresa


def test_empresa_pelo_cnpj_mudanca_e_raiz():
    df = fazer(
        [
            nota(1, "XXXX4"),
            nota(2, "OLDX3"),
            nota(3, "XXXX5"),
            nota(4, "ZZZZ3"),
            nota(5, "SEMC3"),
        ]
    )
    saida = ligar_empresa(df, CNPJ_DE, {"OLDX3": "XXXX3"})
    empresas = dict(zip(saida["ticker"], saida["empresa"]))
    assert empresas == {
        "XXXX4": "11111111000111",
        "OLDX3": "11111111000111",
        "XXXX5": "11111111000111",
        "ZZZZ3": "ZZZZ3",
        "SEMC3": "SEMC3",
    }


# ---------------------------------------------------------------- duplicadas


def test_mesma_noticia_em_dois_codigos_da_mesma_empresa_fica_uma_vez():
    linhas = [
        nota(1, "XXXX3", hora="2026-06-18 10:00:00", titulo="Teste A"),
        nota(1, "XXXX4", hora="2026-06-18 10:00:00", titulo="Teste A"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert len(saida) == 1
    assert info == {"duplicadas_id": 1, "duplicadas_titulo": 0}


def test_mesma_noticia_em_empresas_diferentes_fica_duas_vezes():
    linhas = [
        nota(2, "XXXX3", hora="2026-06-18 10:00:00", titulo="Teste B"),
        nota(2, "YYYY3", hora="2026-06-18 10:00:00", titulo="Teste B"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert len(saida) == 2
    assert info["duplicadas_id"] == 0


def test_titulo_repetido_no_dia_fica_a_de_menor_momento():
    linhas = [
        nota(3, "XXXX3", hora="2026-06-18 19:00:00", titulo="Petrobras sobe 2%"),
        nota(4, "XXXX4", hora="2026-06-18 18:00:00", titulo="petrobras  sobe 2%"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [4]
    assert info == {"duplicadas_id": 0, "duplicadas_titulo": 1}


def test_titulo_repetido_sem_deduplicar_titulo_fica_tudo():
    linhas = [
        nota(3, "XXXX3", hora="2026-06-18 19:00:00", titulo="Petrobras sobe 2%"),
        nota(4, "XXXX4", hora="2026-06-18 18:00:00", titulo="petrobras  sobe 2%"),
    ]
    params = dataclasses.replace(PARAMS, deduplicar_titulo=False)
    saida, info = deduplicar(com_empresa(linhas), params)
    assert sorted(saida["id"]) == [3, 4]
    assert info["duplicadas_titulo"] == 0


def test_cvm_ipe_com_mesmo_titulo_no_dia_nao_deduplica():
    linhas = [
        nota(5, "XXXX3", hora="2026-06-18 10:00:00", titulo="Fato Relevante", origem="cvm_ipe"),
        nota(6, "XXXX3", hora="2026-06-18 11:00:00", titulo="Fato Relevante", origem="cvm_ipe"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [5, 6]
    assert info["duplicadas_titulo"] == 0


# ---------------------------------------------------------------- janela e score


def test_classificacao_das_janelas_e_do_score():
    linhas = [
        nota(1, "XXXX3", hora="2026-06-18 17:00:00"),
        nota(2, "XXXX3", hora="2026-06-18 19:42:00", pp=0.7, pn=0.1),
        nota(3, "XXXX3", hora="2026-06-19 08:00:01"),
        nota(4, "XXXX3", data="2026-06-20"),
        nota(5, "XXXX3", hora="2026-06-17 20:00:00"),
        nota(6, "XXXX3", hora="2026-06-22 19:00:00"),
    ]
    saida, info = classificar(linhas)
    assert list(saida.columns) == COLUNAS_PREPARADAS
    assert set(saida["id"]) == {1, 2, 3, 4}
    por_id = saida.set_index("id")
    assert (por_id["janela"] == "dia").all()
    assert por_id.loc[1, "pregao_ref"] == pd.Timestamp("2026-06-18")
    assert por_id.loc[2, "pregao_ref"] == pd.Timestamp("2026-06-18")
    assert por_id.loc[2, "score"] == pytest.approx(0.6, abs=1e-12)
    assert por_id.loc[3, "pregao_ref"] == pd.Timestamp("2026-06-19")
    assert por_id.loc[4, "pregao_ref"] == pd.Timestamp("2026-06-19")
    assert por_id.loc[4, "sem_horario"]
    assert por_id.loc[4, "momento"] == sp("2026-06-20 23:59:59")
    assert not por_id.loc[1, "sem_horario"]
    assert info == {
        "sem_horario": 1,
        "descartadas_sem_horario": 0,
        "meia_noite_pacifico": 0,
        "pre_abertura": 1,
        "fora_do_calendario": 2,
        "descartadas_fora_da_janela": 0,
    }


def test_inicio_fechamento_so_mantem_a_noite():
    linhas = [
        nota(1, "XXXX3", hora="2026-06-18 17:00:00"),
        nota(2, "XXXX3", hora="2026-06-18 19:42:00", pp=0.7, pn=0.1),
        nota(3, "XXXX3", hora="2026-06-19 08:00:01"),
        nota(4, "XXXX3", data="2026-06-20"),
    ]
    params = dataclasses.replace(PARAMS, inicio_janela="fechamento")
    saida, info = classificar(linhas, params=params)
    por_id = saida.set_index("id")
    assert set(saida["id"]) == {2, 4}
    assert (saida["janela"] == "dia").all()
    assert por_id.loc[2, "pregao_ref"] == pd.Timestamp("2026-06-18")
    assert por_id.loc[4, "pregao_ref"] == pd.Timestamp("2026-06-19")
    assert info["descartadas_fora_da_janela"] == 2
    assert info["pre_abertura"] == 1


def test_fora_do_calendario_vira_noite_com_proximo_ao_vivo():
    linhas = [nota(6, "XXXX3", hora="2026-06-22 19:00:00")]
    saida, info = classificar(linhas, proximo=date(2026, 6, 23))
    assert list(saida["id"]) == [6]
    assert saida.iloc[0]["janela"] == "dia"
    assert saida.iloc[0]["pregao_ref"] == pd.Timestamp("2026-06-22")
    assert info["fora_do_calendario"] == 0


def test_fora_do_calendario_sai_sem_proximo_ao_vivo():
    linhas = [nota(6, "XXXX3", hora="2026-06-22 19:00:00")]
    saida, info = classificar(linhas)
    assert saida.empty
    assert info["fora_do_calendario"] == 1


def test_sem_horario_sai_quando_flag_desligada():
    linhas = [nota(4, "XXXX3", data="2026-06-20")]
    params = dataclasses.replace(PARAMS, sem_horario_na_noite=False)
    saida, info = classificar(linhas, params=params)
    assert saida.empty
    assert info["sem_horario"] == 1
    assert info["descartadas_sem_horario"] == 1


def test_score_sem_probabilidade_fica_nan():
    linhas = [nota(7, "XXXX3", hora="2026-06-18 19:00:00", pp=None, pn=0.2)]
    saida, _ = classificar(linhas)
    assert pd.isna(saida.iloc[0]["score"])


def test_preparar_noticias_encadeia_as_etapas():
    linhas = [
        nota(1, "XXXX3", hora="2026-06-18 19:42:00", origem="cvm_ipe"),
        nota(1, "XXXX4", hora="2026-06-18 19:42:00", origem="cvm_ipe"),
        nota(2, "YYYY3", hora="2026-06-18 17:00:00", tipo="reportagem", papel="mencao"),
    ]
    saida, info = preparar_noticias(fazer(linhas), CAL, CNPJ_DE, {}, "principais", PARAMS)
    assert list(saida["id"]) == [1]
    assert list(saida.columns) == COLUNAS_PREPARADAS
    assert saida.iloc[0]["janela"] == "dia"
    assert info["lidas"] == 3
    assert info["fora_versao"] == 1
    assert info["duplicadas_id"] == 1
    assert info["preparadas"] == 1
