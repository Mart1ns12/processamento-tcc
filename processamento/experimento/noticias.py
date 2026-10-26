"""Preparo das notícias do experimento: versão, empresa, duplicadas e janela (seção 7.2 e 7.3).

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Entrada: DataFrame de `fontes.ler_noticias`. Saída: `COLUNAS_PREPARADAS`, com janela "dia".
"""

from __future__ import annotations

import dataclasses

import pandas as pd

from processamento import calendario, tickers
from processamento.experimento.parametros import ParametrosExperimento
from processamento.fatos.fundamentos import normalizar_texto

COLUNAS_PREPARADAS = ["id", "ticker", "empresa", "origem", "momento", "sem_horario", "janela", "pregao_ref", "score"]
VERSOES = ("todas", "principais", "hora_real_noite")


def _na_versao_principal(noticias: pd.DataFrame, params: ParametrosExperimento) -> pd.Series:
    """True para origem nas origens principais ou, sem ser essa origem, tipo e papel principais."""
    por_origem = noticias["origem"].isin(params.origens_principais)
    por_tipo_e_papel = noticias["tipo_conteudo"].isin(params.tipos_principais) & noticias["papel"].isin(
        params.papeis_principais
    )
    return por_origem | por_tipo_e_papel


def filtrar_versao(
    noticias: pd.DataFrame, versao: str, params: ParametrosExperimento
) -> tuple[pd.DataFrame, dict]:
    """Mantém as notícias da versão ("todas", "principais" ou "hora_real_noite"); conta o que ficou de fora."""
    if versao not in VERSOES:
        raise ValueError(f"versão de notícias inválida: {versao!r} (use 'todas', 'principais' ou 'hora_real_noite')")
    contagens = {"lidas": len(noticias), "fora_versao": 0, "papel_vazio_fora": 0}
    if versao == "todas":
        dentro = pd.Series(True, index=noticias.index)
    elif versao == "principais":
        dentro = _na_versao_principal(noticias, params)
    else:  # hora_real_noite: só horário real (nem "só data", nem sem hora)
        if "precisao_hora" not in noticias.columns:
            raise ValueError("versão hora_real_noite exige a coluna precisao_hora (fontes.aplicar_regra_so_data)")
        dentro = noticias["precisao_hora"].eq("hora")
    fora = noticias[~dentro]
    contagens["fora_versao"] = len(fora)
    if versao == "principais":
        contagens["papel_vazio_fora"] = int(
            (fora["papel"].isna() & ~fora["origem"].isin(params.origens_principais)).sum()
        )
    return noticias[dentro].copy(), contagens


def ligar_empresa(noticias: pd.DataFrame, cnpj_de: dict, mudancas: dict) -> pd.DataFrame:
    """Coluna `empresa`: o CNPJ do código (`tickers.ligar_a_cnpj`); sem CNPJ, o próprio código."""

    def _empresa(t: str) -> str:
        cnpj, _ = tickers.ligar_a_cnpj(t, cnpj_de, mudancas)
        return cnpj or t

    mapa = {t: _empresa(t) for t in noticias["ticker"].unique()}
    return noticias.assign(empresa=noticias["ticker"].map(mapa))


def deduplicar(noticias: pd.DataFrame, params: ParametrosExperimento) -> tuple[pd.DataFrame, dict]:
    """Uma linha por (empresa, id). Com `deduplicar_titulo`, também uma por (empresa, dia, título)
    entre as notícias que não são de cvm_ipe. Entre as cópias, fica a que tem probabilidade (prob_positivo e
    prob_negativo não nulos), se houver; depois a de menor momento_ref (empate: menor id). Sem as colunas de
    probabilidade, só vale o momento_ref."""
    ordem = ["momento_ref", "id"]
    if {"prob_positivo", "prob_negativo"} <= set(noticias.columns):
        sem_prob = noticias["prob_positivo"].isna() | noticias["prob_negativo"].isna()
        noticias = noticias.assign(_sem_prob=sem_prob.astype(int))
        ordem = ["_sem_prob", *ordem]
    ordenadas = noticias.sort_values(ordem).reset_index(drop=True)
    df = ordenadas.drop_duplicates(["empresa", "id"], keep="first")
    duplicadas_id = len(ordenadas) - len(df)
    duplicadas_titulo = 0
    if params.deduplicar_titulo:
        titulo = df["titulo"].map(normalizar_texto)
        candidata = (df["origem"] != "cvm_ipe") & titulo.notna()
        chave = pd.DataFrame({"empresa": df["empresa"], "data": df["data_publicacao"], "titulo": titulo})
        idx_candidatas = df.index[candidata]
        repetida = chave.loc[idx_candidatas].duplicated(keep="first").to_numpy()
        descartar = idx_candidatas[repetida]
        duplicadas_titulo = len(descartar)
        df = df.drop(index=descartar)
    if "_sem_prob" in df.columns:
        df = df.drop(columns="_sem_prob")
    contagens = {"duplicadas_id": duplicadas_id, "duplicadas_titulo": duplicadas_titulo}
    return df.reset_index(drop=True), contagens


def classificar_para_modelo(
    noticias: pd.DataFrame, cal: list, proximo_ao_vivo, params: ParametrosExperimento
) -> tuple[pd.DataFrame, dict]:
    """Janela de cada notícia (`calendario.classificar_noticias`) e score = prob_positivo − prob_negativo.

    Sem horário: entra com 23:59:59 do dia (`momento_ref`) se `sem_horario_na_noite`; senão sai.
    Saída: janela única "dia", com `pregao_ref` = t. `inicio_janela` "manha" mantém noite(t), pregão(t)
    e pré-abertura(t); "fechamento" mantém só a noite(t) e conta o resto em `descartadas_fora_da_janela`.
    Fora do calendário sai.
    """
    sem_hora = noticias["data_hora_publicacao"].isna()
    contagens = {
        "sem_horario": int(sem_hora.sum()),
        "descartadas_sem_horario": 0,
        "meia_noite_pacifico": int((noticias["precisao_hora"] == "meia_noite_pacifico").sum())
        if "precisao_hora" in noticias.columns
        else 0,
    }
    momento = noticias["data_hora_publicacao"].fillna(noticias["momento_ref"])
    df = noticias.assign(momento=momento, sem_horario=sem_hora)
    if not params.sem_horario_na_noite:
        contagens["descartadas_sem_horario"] = int(df["sem_horario"].sum())
        df = df[~df["sem_horario"]]
    classificado = calendario.classificar_noticias(
        df.assign(data_hora_publicacao=df["momento"]), cal, proximo_ao_vivo
    )
    janela = classificado["janela"]
    contagens["pre_abertura"] = int((janela == "pre_abertura").sum())
    contagens["fora_do_calendario"] = int((janela == "fora_do_calendario").sum())
    no_calendario = janela.isin(["noite", "pregao", "pre_abertura"])
    ficam = no_calendario if params.inicio_janela == "manha" else janela == "noite"
    contagens["descartadas_fora_da_janela"] = int((no_calendario & ~ficam).sum())
    saida = classificado[ficam]
    saida = saida.assign(
        janela="dia",
        score=saida["prob_positivo"] - saida["prob_negativo"],
    )
    return saida[COLUNAS_PREPARADAS].reset_index(drop=True), contagens


def preparar_noticias(
    noticias: pd.DataFrame,
    cal: list,
    cnpj_de: dict,
    mudancas: dict,
    versao: str,
    params: ParametrosExperimento,
    proximo_ao_vivo=None,
) -> tuple[pd.DataFrame, dict]:
    """Encadeia versão, empresa, duplicadas e janela. Devolve `COLUNAS_PREPARADAS` e as contagens."""
    if versao == "hora_real_noite":
        params = dataclasses.replace(params, inicio_janela="fechamento")
    filtradas, info = filtrar_versao(noticias, versao, params)
    com_empresa = ligar_empresa(filtradas, cnpj_de, mudancas)
    unicas, info_dedup = deduplicar(com_empresa, params)
    preparadas, info_classe = classificar_para_modelo(unicas, cal, proximo_ao_vivo, params)
    info.update(info_dedup)
    info.update(info_classe)
    info["preparadas"] = len(preparadas)
    info["sem_probabilidade"] = int(preparadas["score"].isna().sum())
    return preparadas, info
