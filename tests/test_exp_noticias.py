"""Testes de experimento/noticias.py (etapa 5, fase 3): filtro de versão, empresa, duplicadas e janela.

Tabelas montadas à mão, tickers fictícios. Nenhum teste usa banco ou rede.
"""

import dataclasses
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from processamento import fontes
from processamento.experimento.noticias import (
    COLUNAS_PREPARADAS,
    classificar_para_modelo,
    deduplicar,
    deduplicar_com_pares,
    filtrar_versao,
    ligar_empresa,
    preparar_noticias,
    remover_entre_origens,
)
from processamento.experimento.parametros import carregar_parametros_experimento

SP = ZoneInfo("America/Sao_Paulo")
PARAMS = carregar_parametros_experimento()
# contagens da deduplicação entre origens (0 quando as cópias são da mesma origem)
_ZERO_ENTRE = {"duplicadas_titulo_mesmo_dia": 0, "duplicadas_titulo_janela": 0, "duplicadas_url": 0}
CAL =[date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)]
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
    precisao: str | None = None,
    link: str | None = None,
    resolved: str | None = None,
) -> dict:
    """Uma linha no formato de `fontes.ler_noticias`. Sem `hora`, o momento vira 23:59:59 do dia.

    `precisao`, `link` e `resolved` (resolved_url) só entram na linha quando são dados.
    """
    if momento is None:
        momento = hora if hora is not None else f"{data} 23:59:59"
    linha = {
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
    if precisao is not None:
        linha["precisao_hora"] = precisao
    if link is not None:
        linha["link"] = link
    if resolved is not None:
        linha["resolved_url"] = resolved
    return linha


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
    assert info == {**_ZERO_ENTRE, "duplicadas_id": 1, "duplicadas_titulo": 0}


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
    assert info == {**_ZERO_ENTRE, "duplicadas_id": 0, "duplicadas_titulo": 1}


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


def test_copia_mais_cedo_vence_mesmo_sem_probabilidade():
    linhas = [
        nota(8, "XXXX3", hora="2026-06-18 09:00:00", titulo="Teste F", pp=None, pn=None),
        nota(9, "XXXX3", hora="2026-06-18 10:00:00", titulo="Teste F", pp=0.5, pn=0.2),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [8]
    assert info == {**_ZERO_ENTRE, "duplicadas_id": 0, "duplicadas_titulo": 1}
    assert "_sem_prob" not in saida.columns


def test_mesmo_momento_a_copia_com_probabilidade_desempata():
    linhas = [
        nota(7, "XXXX3", hora="2026-06-18 09:00:00", titulo="Teste H", pp=None, pn=None),
        nota(8, "XXXX3", hora="2026-06-18 09:00:00", titulo="Teste H", pp=0.5, pn=0.2),
    ]
    saida, _ = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [8]


def test_mesmo_id_em_duas_classes_fica_a_mais_cedo():
    linhas = [
        nota(10, "XXXX3", hora="2026-06-18 09:00:00", pp=0.5, pn=None),
        nota(10, "XXXX4", hora="2026-06-18 10:00:00", pp=0.4, pn=0.1),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [10]
    assert saida.iloc[0]["ticker"] == "XXXX3"
    assert info == {**_ZERO_ENTRE, "duplicadas_id": 1, "duplicadas_titulo": 0}


def test_duas_copias_sem_probabilidade_fica_a_mais_cedo():
    linhas = [
        nota(11, "XXXX3", hora="2026-06-18 11:00:00", titulo="Teste G", pp=None, pn=None),
        nota(12, "XXXX3", hora="2026-06-18 09:00:00", titulo="Teste G", pp=None, pn=None),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [12]
    assert info == {**_ZERO_ENTRE, "duplicadas_id": 0, "duplicadas_titulo": 1}


def test_cvm_ipe_nao_deduplica_por_titulo_mesmo_com_copia_com_probabilidade():
    linhas = [
        nota(13, "XXXX3", hora="2026-06-18 09:00:00", titulo="Fato X", origem="cvm_ipe", pp=None, pn=None),
        nota(14, "XXXX3", hora="2026-06-18 10:00:00", titulo="Fato X", origem="cvm_ipe", pp=0.5, pn=0.2),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [13, 14]
    assert info["duplicadas_titulo"] == 0


def test_deduplicar_sem_colunas_de_probabilidade_fica_a_mais_cedo():
    linhas = [
        nota(15, "XXXX3", hora="2026-06-18 11:00:00", titulo="Teste H"),
        nota(16, "XXXX3", hora="2026-06-18 09:00:00", titulo="Teste H"),
    ]
    df = com_empresa(linhas).drop(columns=["prob_positivo", "prob_negativo"])
    saida, info = deduplicar(df, PARAMS)
    assert list(saida["id"]) == [16]
    assert info == {**_ZERO_ENTRE, "duplicadas_id": 0, "duplicadas_titulo": 1}


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


# ---------------------------------------------------------------- versão hora_real_noite


def _quatro():
    return fontes.aplicar_regra_so_data(fazer([
        nota(1, "AAAA3", hora="2026-06-18 19:00", titulo="A"),   # hora real, noite de 18/06
        nota(2, "AAAA3", hora="2026-06-18 11:00", titulo="B"),   # hora real, pregão
        nota(3, "AAAA3", origem="cvm_ipe", titulo="C"),          # sem hora
        nota(4, "AAAA3", hora="2026-06-18 04:00", titulo="D"),   # 00:00 em LA = só data
    ]))


def test_filtro_hora_real_noite_mantem_so_hora_real():
    filtradas, info = filtrar_versao(_quatro(), "hora_real_noite", PARAMS)
    assert set(filtradas["id"]) == {1, 2}
    assert info == {"lidas": 4, "fora_versao": 2, "papel_vazio_fora": 0}


def test_hora_real_noite_so_fica_a_noite():
    saida, info = preparar_noticias(_quatro(), CAL, CNPJ_DE, {}, "hora_real_noite", PARAMS)
    assert saida["id"].tolist() == [1]
    assert saida["pregao_ref"].iloc[0] == pd.Timestamp("2026-06-18")
    assert info["fora_versao"] == 2 and info["descartadas_fora_da_janela"] == 1 and info["preparadas"] == 1


def test_hora_real_noite_sem_precisao_hora_levanta():
    with pytest.raises(ValueError, match="precisao_hora"):
        filtrar_versao(fazer([nota(1, "AAAA3", hora="2026-06-18 19:00")]), "hora_real_noite", PARAMS)


# ---------------------------------------------------------------- deduplicação entre origens

T = "Petrobras anuncia novo plano de investimentos"
SO_DATA = "meia_noite_pacifico"
HORA = "hora"


def so_data_gn(id_, dia, titulo=T, ticker="XXXX3", **kw):
    """google_news só com a data: 23:59:59 do dia, precisão meia_noite_pacifico."""
    return nota(id_, ticker, data=dia, momento=f"{dia} 23:59:59", titulo=titulo, origem="google_news",
                precisao=SO_DATA, **kw)


def hora_wp(id_, dia, hora, titulo=T, ticker="XXXX3", **kw):
    """wordpress com horário real."""
    return nota(id_, ticker, data=dia, hora=f"{dia} {hora}", titulo=titulo, origem="wordpress",
                precisao=HORA, **kw)


def test_entre_origens_gn_so_data_com_sufixo_cai_quando_wp_tem_hora_no_dia():
    linhas = [
        so_data_gn(21, "2026-10-27", titulo=f"{T} - InfoMoney"),
        hora_wp(22, "2026-10-27", "10:00:00"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [22]
    assert info == {"duplicadas_id": 0, "duplicadas_titulo": 0, "duplicadas_titulo_mesmo_dia": 1,
                    "duplicadas_titulo_janela": 0, "duplicadas_url": 0}


def test_entre_origens_pares_descrevem_a_remocao():
    linhas = [
        so_data_gn(21, "2026-10-27", titulo=f"{T} - InfoMoney"),
        hora_wp(22, "2026-10-27", "10:00:00"),
    ]
    _, _, pares = deduplicar_com_pares(com_empresa(linhas), PARAMS)
    assert len(pares) == 1
    par = pares.iloc[0]
    assert (par["regra"], par["id_removido"], par["origem_removido"], par["id_mantido"], par["origem_mantido"]) == (
        "titulo_mesmo_dia", 21, "google_news", 22, "wordpress")
    assert par["dias"] == 0 and bool(par["tambem_url"]) is False
    assert par["empresa"] == CNPJ_DE["XXXX3"]


def test_entre_origens_titulo_com_um_dia_de_diferenca_fica_a_mais_antiga():
    # GN de 26/10 só-data; WP de 27/10 às 07:00: a data mais antiga vence; hora real só desempata na mesma data
    linhas = [
        so_data_gn(21, "2026-10-26"),
        hora_wp(22, "2026-10-27", "07:00:00"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [21]
    assert info["duplicadas_titulo_janela"] == 1 and info["duplicadas_titulo_mesmo_dia"] == 0


def test_entre_origens_copia_posterior_com_probabilidade_nao_tira_a_antiga_sem():
    linhas = [
        so_data_gn(21, "2026-10-26", pp=None, pn=None),
        hora_wp(22, "2026-10-27", "07:00:00"),
    ]
    saida, _ = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [21]


def test_entre_origens_titulo_a_dois_dias_fica_tudo():
    linhas = [
        so_data_gn(21, "2026-10-25"),
        hora_wp(22, "2026-10-27", "07:00:00"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [21, 22]
    assert info["duplicadas_titulo_janela"] == 0 and info["duplicadas_titulo_mesmo_dia"] == 0


def test_entre_origens_minimo_de_palavras_segura_titulo_curto():
    curto = "Petrobras sobe forte hoje"  # 4 palavras
    linhas = [so_data_gn(21, "2026-10-27", titulo=curto), hora_wp(22, "2026-10-27", "10:00:00", titulo=curto)]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [21, 22]
    assert info["duplicadas_titulo"] == 0 and info["duplicadas_titulo_mesmo_dia"] == 0


def test_entre_origens_minimo_de_palavras_deixa_titulo_de_cinco():
    cinco = "Petrobras sobe forte hoje cedo"  # 5 palavras
    linhas = [so_data_gn(21, "2026-10-27", titulo=cinco), hora_wp(22, "2026-10-27", "10:00:00", titulo=cinco)]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [22]
    assert info["duplicadas_titulo_mesmo_dia"] == 1


def test_entre_origens_url_resolvida_remove_sem_janela_de_data():
    linhas = [
        so_data_gn(21, "2026-10-17", titulo="Acoes sobem na bolsa hoje", resolved="http://infomoney.com.br/x"),
        hora_wp(22, "2026-10-27", "10:00:00", titulo="Petrobras anuncia dividendo bilionario",
                link="https://infomoney.com.br/x/?utm=1"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [21]  # a data mais antiga vence: a cópia de 27/10 não muda o dia 17/10
    assert info["duplicadas_url"] == 1 and info["duplicadas_titulo_janela"] == 0


def test_entre_origens_url_vale_com_titulo_de_duas_palavras():
    # o mínimo de palavras não vale para URL
    linhas = [
        so_data_gn(21, "2026-10-17", titulo="Petro alta", resolved="http://infomoney.com.br/x"),
        hora_wp(22, "2026-10-27", "10:00:00", titulo="Petro cai", link="https://infomoney.com.br/x/?utm=1"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [21]
    assert info["duplicadas_url"] == 1


def test_entre_origens_mesma_origem_dias_seguidos_fica_tudo():
    linhas = [so_data_gn(21, "2026-10-27"), so_data_gn(22, "2026-10-28")]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [21, 22]
    assert info["duplicadas_titulo"] == 0


def test_entre_origens_mesma_origem_mesmo_dia_fica_uma():
    linhas = [so_data_gn(21, "2026-10-27"), so_data_gn(22, "2026-10-27")]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [21]
    assert info["duplicadas_titulo"] == 1 and info["duplicadas_titulo_mesmo_dia"] == 0


def test_entre_origens_wp_mais_cedo_vence_mesmo_sem_probabilidade():
    # WP às 10:00 contra GN só-data (23:59:59): o momento mais cedo vence
    linhas = [
        hora_wp(22, "2026-10-27", "10:00:00", pp=None, pn=None),
        so_data_gn(21, "2026-10-27"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [22]
    assert info["duplicadas_titulo_mesmo_dia"] == 1


def test_entre_origens_mesmo_momento_probabilidade_e_hora_real_desempatam():
    # WP às 23:59:59 (hora real) e GN só-data (23:59:59): mesmo momento
    com_prob = [hora_wp(22, "2026-10-27", "23:59:59", pp=None, pn=None), so_data_gn(21, "2026-10-27")]
    assert list(deduplicar(com_empresa(com_prob), PARAMS)[0]["id"]) == [21]  # probabilidade primeiro
    com_hora = [hora_wp(22, "2026-10-27", "23:59:59"), so_data_gn(21, "2026-10-27")]
    assert list(deduplicar(com_empresa(com_hora), PARAMS)[0]["id"]) == [22]  # depois a hora real


def test_entre_origens_copia_de_07h_da_data_seguinte_nao_vence_a_de_mesma_data_mais_cedo():
    # WP 07:00 de 27/10 é anterior à GN só-data de 27/10 (23:59:59): fica a WP, publicada antes
    linhas = [so_data_gn(21, "2026-10-27"), hora_wp(22, "2026-10-27", "07:00:00")]
    assert list(deduplicar(com_empresa(linhas), PARAMS)[0]["id"]) == [22]


def test_entre_origens_empresa_pelo_cnpj_une_codigos_diferentes():
    linhas = [so_data_gn(21, "2026-10-27", ticker="XXXX3"), hora_wp(22, "2026-10-27", "10:00:00", ticker="XXXX4")]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert list(saida["id"]) == [22]
    assert info["duplicadas_titulo_mesmo_dia"] == 1


def test_entre_origens_empresas_diferentes_ficam_as_duas():
    linhas = [so_data_gn(21, "2026-10-27", ticker="XXXX3"), hora_wp(22, "2026-10-27", "10:00:00", ticker="YYYY3")]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [21, 22]
    assert info["duplicadas_titulo_mesmo_dia"] == 0


def test_entre_origens_cvm_ipe_nao_entra():
    linhas = [
        nota(31, "XXXX3", data="2026-10-27", momento="2026-10-27 23:59:59", titulo=T, origem="cvm_ipe",
             precisao="sem_hora"),
        so_data_gn(21, "2026-10-27"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [21, 31]
    assert info["duplicadas_titulo_mesmo_dia"] == 0 and info["duplicadas_titulo_janela"] == 0


def test_entre_origens_cadeia_nao_e_transitiva_e_gn_cai():
    # WP D, GN D+1, WP D+2: a GN cai pela WP de D; a WP de D+2 só compara com as mantidas (WP D, mesma origem)
    linhas = [
        hora_wp(41, "2026-10-27", "10:00:00"),
        so_data_gn(42, "2026-10-28"),
        hora_wp(43, "2026-10-29", "10:00:00"),
    ]
    saida, info = deduplicar(com_empresa(linhas), PARAMS)
    assert sorted(saida["id"]) == [41, 43]
    assert info["duplicadas_titulo_janela"] == 1


def test_entre_origens_desligada_mantem_so_a_chave_antiga():
    params = dataclasses.replace(PARAMS, deduplicar_entre_origens=False)
    mesmo_dia = [so_data_gn(21, "2026-10-27"), hora_wp(22, "2026-10-27", "10:00:00")]
    saida, info = deduplicar(com_empresa(mesmo_dia), params)
    assert list(saida["id"]) == [22]  # E10 antiga: a de menor momento (a WP, 10:00)
    assert info == {"duplicadas_id": 0, "duplicadas_titulo": 1, "duplicadas_titulo_mesmo_dia": 0,
                    "duplicadas_titulo_janela": 0, "duplicadas_url": 0}

    dia_seguinte = [so_data_gn(21, "2026-10-26"), hora_wp(22, "2026-10-27", "10:00:00")]
    saida, info = deduplicar(com_empresa(dia_seguinte), params)
    assert sorted(saida["id"]) == [21, 22] and info["duplicadas_titulo"] == 0

    por_url = [
        so_data_gn(21, "2026-10-17", titulo="Acoes sobem na bolsa hoje", resolved="http://infomoney.com.br/x"),
        hora_wp(22, "2026-10-27", "10:00:00", titulo="Petrobras anuncia dividendo bilionario",
                link="https://infomoney.com.br/x/?utm=1"),
    ]
    saida, info = deduplicar(com_empresa(por_url), params)
    assert sorted(saida["id"]) == [21, 22] and info["duplicadas_url"] == 0


def test_entre_origens_sem_colunas_opcionais_nao_quebra():
    # sem link, resolved_url, precisao_hora e probabilidades
    df = com_empresa([
        so_data_gn(21, "2026-10-27"),
        hora_wp(22, "2026-10-27", "10:00:00"),
    ]).drop(columns=["prob_positivo", "prob_negativo", "precisao_hora"])
    saida, info = deduplicar(df, PARAMS)
    # sem precisão nem probabilidade, vale o momento_ref: a WP (10:00) vem antes da GN (23:59:59)
    assert list(saida["id"]) == [22]
    assert info["duplicadas_titulo_mesmo_dia"] == 1


def test_remover_entre_origens_devolve_restante_e_pares_sem_colunas_auxiliares():
    df = com_empresa([so_data_gn(21, "2026-10-27"), hora_wp(22, "2026-10-27", "10:00:00")])
    colunas = list(df.columns)
    restante, pares = remover_entre_origens(df, PARAMS)
    assert list(restante["id"]) == [22]
    assert list(restante.columns) == colunas  # a saída mantém as colunas da entrada
    assert list(pares.columns) == [
        "empresa", "regra", "tambem_url", "id_removido", "origem_removido", "titulo_removido", "data_removido",
        "ticker_removido", "id_mantido", "origem_mantido", "titulo_mantido", "data_mantido", "ticker_mantido", "dias",
    ]
    assert len(pares) == 1


def test_remover_entre_origens_exige_origem():
    with pytest.raises(ValueError, match="origem"):
        remover_entre_origens(com_empresa([hora_wp(22, "2026-10-27", "10:00:00")]).drop(columns="origem"), PARAMS)

