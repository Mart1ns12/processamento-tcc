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
from processamento.texto_noticias import chave_url, normalizar_titulo

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


ORIGEM_CVM = "cvm_ipe"
COLUNAS_PARES = [
    "empresa", "regra", "tambem_url", "id_removido", "origem_removido", "titulo_removido", "data_removido",
    "ticker_removido", "id_mantido", "origem_mantido", "titulo_mantido", "data_mantido", "ticker_mantido", "dias",
]


def _serie(df: pd.DataFrame, nome: str) -> pd.Series:
    """Coluna `nome` de df; se não existir, uma coluna de nulos (ausência)."""
    if nome in df.columns:
        return df[nome]
    return pd.Series(None, index=df.index, dtype=object)


def _url_util(*valores) -> str | None:
    """Primeiro valor que é texto não vazio; None se nenhum for."""
    for valor in valores:
        if isinstance(valor, str) and valor.strip():
            return valor
    return None


def remover_entre_origens(df: pd.DataFrame, params: ParametrosExperimento) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tira as cópias da mesma notícia entre origens diferentes. Devolve (df sem as removidas, pares).

    Candidatas: origem diferente de cvm_ipe. Quem fica, na ordem de prioridade: o menor `momento_ref` (a hora real,
    ou 23:59:59 da data sem hora: uma cópia posterior nunca muda o passado); no mesmo momento, com probabilidade
    antes de sem; `precisao_hora == "hora"` antes (sem a coluna, não conta); menor `id`.
    Percorre as candidatas nessa ordem e cai a linha que casa com uma linha JÁ MANTIDA de OUTRA origem:
    - título (só com `deduplicar_titulo`): mesma empresa, mesmo `normalizar_titulo`, com pelo menos
      `titulo_palavras_min_entre_origens` palavras (no título normalizado) e |data_publicacao| até
      `janela_dias_entre_origens`;
    - URL: mesma empresa e mesma `chave_url`, sem janela de data. A URL da linha é `resolved_url` se houver,
      senão `link`; o mínimo de palavras não vale para URL.
    Não há fechamento transitivo: compara só com as mantidas. Atribuição: título com Δ=0 é `titulo_mesmo_dia`;
    título com Δ≠0 é `titulo_janela`; só URL é `url`. `tambem_url` diz se o par também casa por URL.
    Colunas ausentes valem como nulas (sem título, sem URL, sem precisão, sem probabilidade).
    `pares` tem uma linha por removida, com as colunas de `COLUNAS_PARES`.
    """
    df = df.reset_index(drop=True)
    if "origem" not in df.columns:
        raise ValueError("deduplicação entre origens exige a coluna origem")
    cand = df[df["origem"] != ORIGEM_CVM]
    if cand.empty:
        return df, pd.DataFrame(columns=COLUNAS_PARES)
    usa_titulo = params.deduplicar_titulo
    janela = params.janela_dias_entre_origens
    minimo = params.titulo_palavras_min_entre_origens

    if {"prob_positivo", "prob_negativo"} <= set(df.columns):
        sem_prob = (df["prob_positivo"].isna() | df["prob_negativo"].isna()).astype(int)
    else:
        sem_prob = pd.Series(0, index=df.index)
    if "precisao_hora" in df.columns:
        nao_hora = df["precisao_hora"].ne("hora").astype(int)
    else:
        nao_hora = pd.Series(0, index=df.index)

    tn = _serie(cand, "titulo").map(normalizar_titulo)
    urls = [_url_util(r, l) for r, l in zip(_serie(cand, "resolved_url"), _serie(cand, "link"))]
    w = pd.DataFrame(
        {
            "pos": cand.index,
            "empresa": cand["empresa"].to_numpy(),
            "origem": cand["origem"].to_numpy(),
            "id": cand["id"].to_numpy(),
            "ticker": _serie(cand, "ticker").to_numpy(),
            "titulo": _serie(cand, "titulo").to_numpy(),
            "data": pd.to_datetime(_serie(cand, "data_publicacao")).to_numpy(),
            "momento": cand["momento_ref"].to_numpy(),
            "tn": tn.to_numpy(),
            "uk": [chave_url(u) if u else None for u in urls],
            "sem_prob": sem_prob.loc[cand.index].to_numpy(),
            "nao_hora": nao_hora.loc[cand.index].to_numpy(),
        }
    )
    w["tn_ok"] = w["tn"].map(lambda t: isinstance(t, str) and len(t.split()) >= minimo).astype(bool)
    # ordinal do dia (int) ou None: object, para o None não virar NaN
    w["dia"] = pd.Series([d.toordinal() if pd.notna(d) else None for d in w["data"]], index=w.index, dtype=object)
    # só entram no laço as linhas de grupos com mais de uma origem (título ou URL); as outras ficam
    grupo = pd.Series(False, index=w.index)
    if usa_titulo:
        com_titulo = w[w["tn_ok"]]
        grupo |= com_titulo.groupby(["empresa", "tn"])["origem"].transform("nunique").reindex(w.index) > 1
    com_url = w[w["uk"].notna()]
    grupo |= com_url.groupby(["empresa", "uk"])["origem"].transform("nunique").reindex(w.index) > 1
    g = w[grupo].sort_values(["momento", "sem_prob", "nao_hora", "id"], kind="mergesort")

    mantidas_t: dict = {}
    mantidas_u: dict = {}
    removidas: list = []
    pares: list[dict] = []
    for lin in g.to_dict("records"):
        achado, regra = None, None
        if usa_titulo and lin["tn_ok"]:
            for k in mantidas_t.get((lin["empresa"], lin["tn"]), []):
                if k["origem"] == lin["origem"] or lin["dia"] is None or k["dia"] is None:
                    continue
                if abs(lin["dia"] - k["dia"]) <= janela:
                    achado = k
                    regra = "titulo_mesmo_dia" if lin["dia"] == k["dia"] else "titulo_janela"
                    break
        if achado is None and lin["uk"] is not None:
            for k in mantidas_u.get((lin["empresa"], lin["uk"]), []):
                if k["origem"] != lin["origem"]:
                    achado, regra = k, "url"
                    break
        if achado is None:
            if usa_titulo and lin["tn_ok"]:
                mantidas_t.setdefault((lin["empresa"], lin["tn"]), []).append(lin)
            if lin["uk"] is not None:
                mantidas_u.setdefault((lin["empresa"], lin["uk"]), []).append(lin)
            continue
        removidas.append(lin["pos"])
        tambem_url = lin["uk"] is not None and any(
            k["origem"] != lin["origem"] for k in mantidas_u.get((lin["empresa"], lin["uk"]), [])
        )
        dias = abs(lin["dia"] - achado["dia"]) if lin["dia"] is not None and achado["dia"] is not None else None
        pares.append({
            "empresa": lin["empresa"], "regra": regra, "tambem_url": bool(tambem_url),
            "id_removido": lin["id"], "origem_removido": lin["origem"], "titulo_removido": lin["titulo"],
            "data_removido": lin["data"], "ticker_removido": lin["ticker"],
            "id_mantido": achado["id"], "origem_mantido": achado["origem"], "titulo_mantido": achado["titulo"],
            "data_mantido": achado["data"], "ticker_mantido": achado["ticker"], "dias": dias,
        })
    restante = df.drop(index=removidas).reset_index(drop=True)
    return restante, pd.DataFrame(pares, columns=COLUNAS_PARES)


def deduplicar(noticias: pd.DataFrame, params: ParametrosExperimento) -> tuple[pd.DataFrame, dict]:
    """Uma linha por (empresa, id). Com `deduplicar_titulo`, também uma por (empresa, dia, título)
    entre as notícias que não são de cvm_ipe (com `deduplicar_entre_origens`, a chave tem a origem: só
    cópias de uma mesma origem). Entre as cópias, fica a de menor momento_ref; no mesmo momento, a que tem
    probabilidade (prob_positivo e prob_negativo não nulos), depois o menor id. Sem as colunas de
    probabilidade, só vale o momento_ref. Com `deduplicar_entre_origens`, depois tira as cópias entre origens
    diferentes (`remover_entre_origens`). Contagens: duplicadas_id, duplicadas_titulo, duplicadas_titulo_mesmo_dia,
    duplicadas_titulo_janela e duplicadas_url (as três últimas são 0 com a regra desligada)."""
    df, contagens, _ = deduplicar_com_pares(noticias, params)
    return df, contagens


def deduplicar_com_pares(noticias: pd.DataFrame, params: ParametrosExperimento) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Igual a `deduplicar`, e também devolve os pares removidos entre origens (`remover_entre_origens`)."""
    ordem = ["momento_ref", "id"]
    if {"prob_positivo", "prob_negativo"} <= set(noticias.columns):
        sem_prob = noticias["prob_positivo"].isna() | noticias["prob_negativo"].isna()
        noticias = noticias.assign(_sem_prob=sem_prob.astype(int))
        ordem = ["momento_ref", "_sem_prob", "id"]
    ordenadas = noticias.sort_values(ordem).reset_index(drop=True)
    df = ordenadas.drop_duplicates(["empresa", "id"], keep="first")
    duplicadas_id = len(ordenadas) - len(df)
    duplicadas_titulo = 0
    if params.deduplicar_titulo:
        titulo = df["titulo"].map(normalizar_texto)
        candidata = (df["origem"] != ORIGEM_CVM) & titulo.notna()
        chave = pd.DataFrame({"empresa": df["empresa"], "data": df["data_publicacao"], "titulo": titulo})
        if params.deduplicar_entre_origens:
            chave["origem"] = df["origem"]
        idx_candidatas = df.index[candidata]
        repetida = chave.loc[idx_candidatas].duplicated(keep="first").to_numpy()
        descartar = idx_candidatas[repetida]
        duplicadas_titulo = len(descartar)
        df = df.drop(index=descartar)
    if "_sem_prob" in df.columns:
        df = df.drop(columns="_sem_prob")
    pares = pd.DataFrame(columns=COLUNAS_PARES)
    if params.deduplicar_entre_origens:
        df, pares = remover_entre_origens(df, params)
    regras = pares["regra"] if not pares.empty else pd.Series([], dtype=object)
    contagens = {
        "duplicadas_id": duplicadas_id,
        "duplicadas_titulo": duplicadas_titulo,
        "duplicadas_titulo_mesmo_dia": int((regras == "titulo_mesmo_dia").sum()),
        "duplicadas_titulo_janela": int((regras == "titulo_janela").sum()),
        "duplicadas_url": int((regras == "url").sum()),
    }
    return df.reset_index(drop=True), contagens, pares


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
