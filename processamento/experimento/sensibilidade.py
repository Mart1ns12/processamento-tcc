"""Análises exploratórias de sensibilidade de uma rodada (padrão: 001): recorte com notícia, datasets principais e
hora_real_noite, e só notícias. Rodada 001: família logística; outras rodadas: família e hiperparâmetros da configuração
final. Mesmas dobras e semente, colunas congeladas.

Só desenvolvimento: os CSV entram por `treino.ler_desenvolvimento` (nada do banco, nada do teste final, nada de
registro do protocolo nem de modelos/). Não muda hipótese, configuração congelada nem teste final. Os IC saem sem
ajuste por múltiplas comparações. Não constitui recomendação de investimento.

Uso: python -m processamento.experimento.sensibilidade --data AAAA-MM-DD [--rodada N] [--congelado docs/protocolo_congelado_rodada_NNN.json]
     [--configuracao docs/configuracao_final_rodada_NNN.json] [--pasta-datasets saida/experimento] [--pasta-docs docs]
Exemplo: python -m processamento.experimento.sensibilidade --data 2026-11-06 --rodada 3
Saídas: docs/busca_rodada_NNN_sensibilidade.md e .json. Nunca sobrescreve: se já existirem, erro.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from processamento import fontes
from processamento.experimento import avaliacao, busca, preparacao, protocolo, treino, validacao
from processamento.experimento import busca_execucao as be
from processamento.experimento import protocolo_registro as reg
from processamento.experimento.parametros import carregar_parametros_treino

PASTA_DOCS_PADRAO = fontes.RAIZ / "docs"
CONGELADO_PADRAO = PASTA_DOCS_PADRAO / "protocolo_congelado_rodada_001.json"


def nome_saida(rodada: int) -> str:
    """Nome-base das saídas de uma rodada: `busca_rodada_NNN_sensibilidade`."""
    return f"busca_rodada_{rodada:03d}_sensibilidade"


NOME_SAIDA = nome_saida(1)
MIN_PAPEIS_DIA = 5            # regra de dia curto: no recorte, o dia entra só com ao menos isso
MODELO = "logistica"          # família padrão (rodada 001, sem configuração final)
NOMES_FAMILIA = {"logistica": "logística", "xgb": "XGBoost", "lgbm": "LightGBM"}   # aceitas na configuração final
CHAVES = ["data", "ticker"]
COLUNAS_CONFERIDAS = preparacao.COLUNAS_PRECO + preparacao.COLUNAS_ALVO


class ErroSensibilidade(Exception):
    """Dados que não batem com a análise: preço diferente entre versões, congelado de outro dataset, saída já existente."""


def recorte_com_noticia(df: pd.DataFrame) -> pd.DataFrame:
    """Linhas com `noticias_dia_qtd` BRUTO >= 1. NaN (sem coleta, jan–jul/2025) não conta como zero: sai."""
    return df.loc[df["noticias_dia_qtd"] >= 1]


def conferir_precos_iguais(base: pd.DataFrame, outra: pd.DataFrame, nome: str) -> None:
    """Preço e alvo têm de ser iguais nas mesmas chaves (data, ticker) das duas versões. Senão, ErroSensibilidade."""
    a = base[CHAVES + COLUNAS_CONFERIDAS].sort_values(CHAVES).reset_index(drop=True)
    b = outra[CHAVES + COLUNAS_CONFERIDAS].sort_values(CHAVES).reset_index(drop=True)
    if not a[CHAVES].equals(b[CHAVES]):
        raise ErroSensibilidade(f"{nome}: pregão × ticker diferente do dataset todas")
    for coluna in COLUNAS_CONFERIDAS:
        x, y = a[coluna], b[coluna]
        if not (x.eq(y) | (x.isna() & y.isna())).all():
            raise ErroSensibilidade(f"{nome}: a coluna {coluna} difere do dataset todas nas mesmas chaves")


def dias_validos(pred: pd.DataFrame, minimo: int = MIN_PAPEIS_DIA) -> tuple[list[pd.Timestamp], dict[int, int]]:
    """Dias que entram no recorte: ao menos `minimo` papéis com alvo e as duas classes de alvo.

    Devolve (dias que entram, dias perdidos por ano).
    """
    validos: list[pd.Timestamp] = []
    perdidos: dict[int, int] = {}
    for data, grupo in pred.groupby("data", sort=True):
        candidatas = grupo.loc[grupo["alvo"].notna()]
        if len(candidatas) >= minimo and candidatas["alvo"].nunique() >= 2:
            validos.append(pd.Timestamp(data))
        else:
            ano = pd.Timestamp(data).year
            perdidos[ano] = perdidos.get(ano, 0) + 1
    return validos, dict(sorted(perdidos.items()))


def _so_dias(pred: pd.DataFrame, dias: list[pd.Timestamp]) -> pd.DataFrame:
    return pred.loc[pred["data"].isin(dias)].reset_index(drop=True)


def _mascara_recorte(pred: pd.DataFrame, bruto: pd.DataFrame) -> np.ndarray:
    """Linhas da previsão cujo (data, ticker) tem `noticias_dia_qtd` bruto >= 1 em `bruto`."""
    return treino._no_recorte(pred, recorte_com_noticia(bruto))


def _alinhar(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mesma ordem nas duas previsões (`medir_comparacao` exige). Pares (data, ticker) diferentes: erro."""
    a2 = a.sort_values(CHAVES, kind="stable").reset_index(drop=True)
    b2 = b.sort_values(CHAVES, kind="stable").reset_index(drop=True)
    if not a2[CHAVES].equals(b2[CHAVES]):
        raise ErroSensibilidade("as previsões têm pregão × ticker diferentes entre as versões")
    return a2, b2


def _cobertura_por_ano(pred: pd.DataFrame) -> list[dict]:
    """Papéis (linhas) por dia em cada ano, antes da regra de dia curto."""
    ano = pd.to_datetime(pred["data"]).dt.year
    saida = []
    for valor, grupo in pred.groupby(ano, sort=True):
        por_dia = grupo.groupby("data").size()
        saida.append({"ano": int(valor), "n_dias": int(len(por_dia)), "papeis_por_dia": float(por_dia.mean())})
    return saida


def _media(valores: pd.Series) -> float | None:
    return float(valores.mean()) if len(valores) else None


def _vs_acaso(taxa: float | None, faixa: dict) -> str | None:
    if taxa is None or faixa.get("p97_5") is None:
        return None
    return avaliacao.comparar_com_acaso(taxa, faixa)


def _faixa_resumo(faixa: dict) -> dict:
    return {"media": faixa["media"], "p2_5": faixa["p2_5"], "p97_5": faixa["p97_5"], "n_dias": faixa["n_dias"]}


def _ics_auc(auc: pd.Series, params, lim) -> tuple[list, list]:
    """IC 95% e IC 99,5% (limites da busca) do AUC − 0,5 por bootstrap de blocos de pregões."""
    excesso = (auc - 0.5).to_numpy()
    ic95 = avaliacao.ic_bootstrap_blocos(excesso, params.bootstrap_bloco_pregoes, params.bootstrap_reamostragens, params.semente)
    ic995 = avaliacao.ic_bootstrap_blocos(excesso, lim.bloco_bootstrap, lim.reamostragens, params.semente,
                                          percentis=lim.percentis_ic)
    return list(ic95), list(ic995)


def _resumo_modelo(pred: pd.DataFrame, taxa: float | None, acertos: int, n_dias: int, faixa, params, lim) -> dict:
    auc = avaliacao.auc_por_pregao(pred)
    ic95, ic995 = _ics_auc(auc, params, lim)
    return {
        "auc_medio": _media(auc),
        "auc_menos_0_5_ic95": ic95,
        "auc_menos_0_5_ic995": ic995,
        "top5_taxa": taxa,
        "top5_acertos": acertos,
        "top5_n_dias": n_dias,
        "vs_acaso_top5": _vs_acaso(taxa, faixa) if faixa is not None else None,
    }


def _comparacao(base: pd.DataFrame, cand: pd.DataFrame, params, lim, com_acaso: bool) -> dict:
    """Modelo 3 (`cand`) contra modelo 1 (`base`): mesmas linhas, mesma ordem. Acaso só no recorte (`com_acaso`)."""
    k = params.topk[0]
    if k != lim.k_top:
        raise ErroSensibilidade(f"o top principal ({k}) difere do limite da busca ({lim.k_top})")
    m = protocolo.medir_comparacao(base, cand, params.semente, lim)
    dif = avaliacao.diferenca_pareada(avaliacao.auc_por_pregao(cand), avaliacao.auc_por_pregao(base))
    dif_top = avaliacao.diferenca_pareada(treino._serie(cand, "acerto_top5_dia", k), treino._serie(base, "acerto_top5_dia", k))
    faixa = treino.calcular_acaso(base, params)[str(k)] if com_acaso else None
    top = m["top"]
    ganho_ic95 = avaliacao.ic_bootstrap_blocos(dif.to_numpy(), params.bootstrap_bloco_pregoes,
                                               params.bootstrap_reamostragens, params.semente)
    top_ic95 = avaliacao.ic_bootstrap_blocos(dif_top.to_numpy(), params.bootstrap_bloco_pregoes,
                                             params.bootstrap_reamostragens, params.semente)
    return {
        "n_linhas": int(len(base)),
        "n_dias": int(base["data"].nunique()),
        "n_dias_auc": int(m["n_dias_auc"]),
        "modelos": {
            "modelo_1": _resumo_modelo(base, top["taxa_base"], top["acertos_base"], top["n_dias"], faixa, params, lim),
            "modelo_3": _resumo_modelo(cand, top["taxa_candidato"], top["acertos_candidato"], top["n_dias"], faixa, params, lim),
        },
        "ganho": m["ganho"],
        "ganho_ic95": list(ganho_ic95),
        "ganho_ic995": list(m["ic"]),
        "ganho_por_ano": m["ganho_por_ano"],
        "n_dias_por_ano": m["n_dias_por_ano"],
        "top5_diferenca": float(dif_top.mean()) if len(dif_top) else None,
        "top5_diferenca_ic95": list(top_ic95),
        "acaso_top5": _faixa_resumo(faixa) if faixa is not None else None,
    }


def _escopo_recorte(base: pd.DataFrame, cand: pd.DataFrame, mascara: np.ndarray, params, lim) -> dict:
    """Comparação só no recorte com notícia, com a regra de dia curto e o acaso recalculado no recorte."""
    base_r = base.loc[mascara].reset_index(drop=True)
    cand_r = cand.loc[mascara].reset_index(drop=True)
    dias, perdidos = dias_validos(base_r)
    res = _comparacao(_so_dias(base_r, dias), _so_dias(cand_r, dias), params, lim, com_acaso=True)
    res["cobertura_por_ano"] = _cobertura_por_ano(base_r)
    res["dias_perdidos_por_ano"] = perdidos
    return res


def _analise_dataset_extra(nome: str, csv: Path, df_t: pd.DataFrame, p1: pd.DataFrame, c3: list[str], params, lim,
                           prever, hiper, familia: str = MODELO) -> tuple[dict, dict]:
    """Análise (b) ou (c): modelo 3 treinado no dataset `nome` contra o MESMO modelo 1 de `todas`."""
    df_x, info_x = treino.ler_desenvolvimento(csv, params)
    conferir_precos_iguais(df_t, df_x, nome)
    prep_x, cal_x = treino.preparar_dev(df_x)
    dobras_x = validacao.dobras_walk_forward(cal_x, params.treino_minimo_meses, params.embargo_pregoes)
    p3_x = prever(prep_x, dobras_x, c3, familia, params, hiper)
    p1_a, p3_a = _alinhar(p1, p3_x)
    # recorte da própria versão (qtd bruta de df_x); os dois modelos são avaliados nas mesmas linhas
    mascara = _mascara_recorte(p3_a, df_x)
    analise = {
        "todas": _comparacao(p1_a, p3_a, params, lim, com_acaso=False),
        "recorte_noticia": _escopo_recorte(p1_a, p3_a, mascara, params, lim),
    }
    return analise, _versao(nome, csv, info_x, df_x, cal_x)


def _previsao_noticias(prep: pd.DataFrame, dobras, params, prever, familia: str = MODELO, hiper=None) -> pd.DataFrame:
    """Análise (d): `familia` só com as colunas de notícia (`preparacao.NOTICIAS_DIA`), na versão todas."""
    return prever(prep, dobras, preparacao.NOTICIAS_DIA, familia, params, hiper)


def _resumo_so_noticias(pred: pd.DataFrame, params, lim) -> dict:
    """AUC − 0,5 com IC contra o acaso (AUC 0,5) e o top 5 contra a faixa do acaso. Sem modelo 1."""
    k = params.topk[0]
    auc = avaliacao.auc_por_pregao(pred)
    ic95, ic995 = _ics_auc(auc, params, lim)
    diario = avaliacao.resumo_diario(pred, k, com_retorno=False)
    m = avaliacao.metricas_periodo(diario, com_retorno=False)
    faixa = treino.calcular_acaso(pred, params)[str(k)]
    auc_medio = _media(auc)
    return {
        "n_linhas": int(len(pred)),
        "n_dias": int(pred["data"].nunique()),
        "n_dias_auc": int(len(auc)),
        "auc_medio": auc_medio,
        "auc_menos_0_5": None if auc_medio is None else auc_medio - 0.5,
        "referencia_acaso_auc": 0.5,
        "auc_menos_0_5_ic95": ic95,
        "auc_menos_0_5_ic995": ic995,
        "top5_taxa": m["taxa_acerto"],
        "top5_acertos": int(diario["acertos_top"].sum()),
        "top5_n_dias": m["n_dias"],
        "vs_acaso_top5": _vs_acaso(m["taxa_acerto"], faixa),
        "acaso_top5": _faixa_resumo(faixa),
    }


def _escopo_so_noticias_recorte(pred: pd.DataFrame, mascara: np.ndarray, params, lim) -> dict:
    r = pred.loc[mascara].reset_index(drop=True)
    dias, perdidos = dias_validos(r)
    res = _resumo_so_noticias(_so_dias(r, dias), params, lim)
    res["cobertura_por_ano"] = _cobertura_por_ano(r)
    res["dias_perdidos_por_ano"] = perdidos
    return res


def _versao(nome: str, csv: Path, info: dict, df: pd.DataFrame, cal: list) -> dict:
    if info.get("versao_preparacao") != preparacao.VERSAO_PREPARACAO:
        raise ErroSensibilidade(
            f"{nome}: versao_preparacao {info.get('versao_preparacao')} difere da atual {preparacao.VERSAO_PREPARACAO}"
        )
    return {
        "arquivo": csv.name,
        "sha256": info["sha256"],
        "versao_preparacao": info["versao_preparacao"],
        "periodo_ini": cal[0].isoformat(),
        "periodo_fim": cal[-1].isoformat(),
        "n_linhas": int(len(df)),
        "n_pregoes": int(len(cal)),
    }


def ler_configuracao_final(caminho, sha256: str, congelado: dict) -> tuple[str, dict]:
    """Família e hiperparâmetros da configuração final de uma rodada (`docs/configuracao_final_rodada_NNN.json`).

    ErroSensibilidade se a configuração for de outro dataset, se as colunas não baterem com as do congelado ou se a
    família não estiver em `NOMES_FAMILIA`.
    """
    cfg = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if cfg.get("sha256_dataset") != sha256:
        raise ErroSensibilidade("a configuração final é de outro dataset (sha256 diferente)")
    for chave in ("colunas_1", "colunas_3"):
        if cfg.get(chave) != congelado.get(chave):
            raise ErroSensibilidade(f"a configuração final tem {chave} diferente do congelado (colunas)")
    familia = cfg.get("familia")
    if familia not in NOMES_FAMILIA:
        raise ErroSensibilidade(f"família {familia!r} fora de {', '.join(NOMES_FAMILIA)}")
    hiper = cfg.get("hiperparametros")
    if not isinstance(hiper, dict):
        raise ErroSensibilidade("a configuração final não traz hiperparâmetros")
    return familia, hiper


def _caminhos_saida(pasta_docs: Path, nome: str = NOME_SAIDA) -> tuple[Path, Path]:
    md = Path(pasta_docs) / f"{nome}.md"
    js = Path(pasta_docs) / f"{nome}.json"
    for caminho in (md, js):
        if caminho.exists():
            raise ErroSensibilidade(f"{caminho.name} já existe: saídas de análise nunca são sobrescritas")
    return md, js


def _gravar_novo(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "x", encoding="utf-8", newline="\n") as arq:
        arq.write(texto)


def gravar_saidas(pasta_docs, texto_md: str, resultado: dict, nome: str = NOME_SAIDA) -> tuple[Path, Path]:
    """Grava o .md e o .json, os dois novos. Se algum já existir, erro e nada é gravado."""
    caminho_md, caminho_json = _caminhos_saida(Path(pasta_docs), nome)
    _gravar_novo(caminho_md, texto_md)
    _gravar_novo(caminho_json, json.dumps(treino._para_json(resultado), ensure_ascii=False, indent=2))
    return caminho_md, caminho_json


def executar(pasta_datasets, pasta_docs, *, data, congelado: Path, configuracao: Path | None = None, rodada: int = 1,
             params=None, lim=be.LIMITES_BUSCA, prever=None) -> tuple[Path, Path]:
    """Roda as quatro análises (a, b, c, d) sobre o desenvolvimento e grava o relatório e o JSON, ambos novos.

    Sem `configuracao`: logística com o hiperparâmetro de `busca.candidatos`. Com ela: a família e os hiperparâmetros
    do arquivo, em todos os casos. Nada é gravado se uma conferência falhar.
    """
    params = carregar_parametros_treino() if params is None else params
    prever = treino.prever_walk_forward if prever is None else prever
    nome_base = nome_saida(rodada)
    _caminhos_saida(Path(pasta_docs), nome_base)   # falha cedo se a saída já existir
    csvs = treino.localizar_datasets(Path(pasta_datasets), data)
    for nome in ("principais", "hora_real_noite"):
        if csvs[nome] is None:
            raise ErroSensibilidade(f"não achei dataset-{nome}-{data:%Y-%m-%d}.csv em {pasta_datasets}")
    congelado_dados = json.loads(Path(congelado).read_text(encoding="utf-8"))

    df_t, info_t = treino.ler_desenvolvimento(csvs["todas"], params)
    if congelado_dados.get("sha256_dataset") != info_t["sha256"]:
        raise ErroSensibilidade("o congelado é de outro dataset (sha256 diferente)")
    c1, c3 = congelado_dados["colunas_1"], congelado_dados["colunas_3"]
    if configuracao is None:
        familia, hiper = MODELO, {c["nome"]: c for c in busca.candidatos(params)}[MODELO]["hiper"]
        hiper_noticias = None   # a análise d sempre rodou sem hiperparâmetro (logística padrão)
    else:
        familia, hiper = ler_configuracao_final(configuracao, info_t["sha256"], congelado_dados)
        hiper_noticias = hiper

    prep_t, cal_t = treino.preparar_dev(df_t)
    dobras_t = validacao.dobras_walk_forward(cal_t, params.treino_minimo_meses, params.embargo_pregoes)
    p1 = prever(prep_t, dobras_t, c1, familia, params, hiper)
    p3 = prever(prep_t, dobras_t, c3, familia, params, hiper)
    p_noticias = _previsao_noticias(prep_t, dobras_t, params, prever, familia, hiper_noticias)
    mascara_t = _mascara_recorte(p1, df_t)

    analises: dict[str, dict] = {"a_recorte_noticia": {"recorte_noticia": _escopo_recorte(p1, p3, mascara_t, params, lim)}}
    versoes = {"todas": _versao("todas", csvs["todas"], info_t, df_t, cal_t)}
    for chave, nome in (("b_principais", "principais"), ("c_hora_real_noite", "hora_real_noite")):
        analises[chave], versoes[nome] = _analise_dataset_extra(nome, csvs[nome], df_t, p1, c3, params, lim, prever,
                                                                hiper, familia)
    analises["d_so_noticias"] = {
        "recorte_noticia": _escopo_so_noticias_recorte(p_noticias, mascara_t, params, lim),
        "todas_linhas": _resumo_so_noticias(p_noticias, params, lim),
    }

    resultado = {
        "exploratorio": True,
        "modelo_oficial": False,
        "data": data.isoformat(),
        "identificacao": {
            "versoes": versoes,
            "semente": params.semente,
            "top_principal": params.topk[0],
            "sha_parametros": reg.sha_parametros(params),
            "versoes_bibliotecas": treino._versoes(),
            "versao_preparacao_atual": preparacao.VERSAO_PREPARACAO,
            "colunas_1": c1,
            "colunas_3": c3,
            "colunas_noticias": list(preparacao.NOTICIAS_DIA),
            "rodada_congelada": congelado_dados.get("rodada"),
            "rodada": rodada,
            "familia": familia,
            "hiperparametros": hiper,
            "configuracao": Path(configuracao).name if configuracao is not None else None,
            "dobras": len(dobras_t),
            "ic95": {"bloco_pregoes": params.bootstrap_bloco_pregoes,
                     "reamostragens": params.bootstrap_reamostragens, "percentis": [2.5, 97.5]},
            "ic995": {"bloco_pregoes": lim.bloco_bootstrap, "reamostragens": lim.reamostragens,
                      "percentis": list(lim.percentis_ic)},
        },
        "analises": analises,
    }
    resultado["contagem"] = {
        "analises": len(analises),
        "escopos": sum(len(v) for v in analises.values()),
        "fora_do_registro_do_protocolo": True,
    }
    return gravar_saidas(pasta_docs, _relatorio(resultado), resultado, nome=nome_base)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _num(valor, casas: int = 5) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "n/d"
    return f"{valor:.{casas}f}"


def _ic(par) -> str | None:
    if not par or par[0] is None or par[1] is None:
        return None
    return f"[{_num(par[0])}; {_num(par[1])}]"


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join("n/d" if c is None else str(c) for c in linha) + " |" for linha in linhas]
    return saida


def _rotulo(vs: str | None) -> str:
    return {"acima": "acima do acaso", "abaixo": "abaixo do acaso", "dentro": "dentro da faixa do acaso"}.get(vs, "n/d")


def _percentis(par) -> str:
    return " e ".join(f"{p:g}".replace(".", ",") for p in par)


def _md_identificacao(r: dict) -> list[str]:
    ident = r["identificacao"]
    linhas = ["## Identificação", ""]
    for nome, v in ident["versoes"].items():
        linhas.append(
            f"- Dataset {nome}: `{v['arquivo']}`; sha256 `{v['sha256']}`; versao_preparacao {v['versao_preparacao']}; "
            f"{v['n_linhas']} linhas; {v['n_pregoes']} pregões; {v['periodo_ini']} a {v['periodo_fim']}"
        )
    linhas += [
        f"- Data: {r['data']}; semente: {ident['semente']}; top principal: {ident['top_principal']}; "
        f"dobras walk-forward: {ident['dobras']}; rodada congelada: {ident['rodada_congelada']}",
        f"- sha_parametros: `{ident['sha_parametros']}`; versões: {ident['versoes_bibliotecas']}",
        f"- Família: {NOMES_FAMILIA[ident['familia']]}; hiperparâmetros: {ident['hiperparametros'] or 'padrão da família'}; "
        f"configuração: {ident['configuracao'] or 'nenhuma'}",
        f"- Colunas do modelo 1: {', '.join(ident['colunas_1'])}",
        f"- Colunas do modelo 3: {', '.join(ident['colunas_3'])}",
        f"- Colunas de notícia (análise d): {', '.join(ident['colunas_noticias'])}",
        f"- IC 95%: bloco de {ident['ic95']['bloco_pregoes']} pregões, {ident['ic95']['reamostragens']} reamostragens, "
        f"percentis {_percentis(ident['ic95']['percentis'])}",
        f"- IC 99,5%: bloco de {ident['ic995']['bloco_pregoes']} pregões, {ident['ic995']['reamostragens']} "
        f"reamostragens, percentis {_percentis(ident['ic995']['percentis'])}",
        "",
    ]
    return linhas


def _md_dias_perdidos(res: dict) -> list[str]:
    perdidos = res.get("dias_perdidos_por_ano", {})
    if not perdidos:
        return ["Dias perdidos pela regra de dia curto: nenhum.", ""]
    texto = "; ".join(f"{ano}: {n}" for ano, n in perdidos.items())
    return [f"Dias perdidos pela regra de dia curto (por ano): {texto}.", ""]


def _md_cobertura(res: dict) -> list[str]:
    linhas = ["Cobertura no recorte (antes da regra de dia curto):", ""]
    linhas += _tabela(
        ["Ano", "Dias no recorte", "Papéis por dia (média)", "Dias perdidos"],
        [[c["ano"], c["n_dias"], _num(c["papeis_por_dia"], 2), res["dias_perdidos_por_ano"].get(c["ano"], 0)]
         for c in res["cobertura_por_ano"]],
    )
    return linhas + [""]


def _md_comparacao(res: dict) -> list[str]:
    m1, m3 = res["modelos"]["modelo_1"], res["modelos"]["modelo_3"]
    linhas = [f"- Linhas: {res['n_linhas']}; dias: {res['n_dias']}; dias com AUC: {res['n_dias_auc']}", ""]
    tabela = [
        ["AUC médio por pregão", _num(m1["auc_medio"]), _num(m3["auc_medio"]), _num(res["ganho"])],
        ["IC 95% (AUC − 0,5 nos modelos; ganho na diferença)", _ic(m1["auc_menos_0_5_ic95"]),
         _ic(m3["auc_menos_0_5_ic95"]), _ic(res["ganho_ic95"])],
        ["IC 99,5% (idem)", _ic(m1["auc_menos_0_5_ic995"]), _ic(m3["auc_menos_0_5_ic995"]), _ic(res["ganho_ic995"])],
        ["Top 5: taxa de acerto", _num(m1["top5_taxa"]), _num(m3["top5_taxa"]), _num(res["top5_diferenca"])],
        ["Top 5: acertos / dias", f"{m1['top5_acertos']} / {m1['top5_n_dias']}",
         f"{m3['top5_acertos']} / {m3['top5_n_dias']}", "–"],
        ["IC 95% do top 5 diário (diferença)", "–", "–", _ic(res["top5_diferenca_ic95"])],
    ]
    if res["acaso_top5"] is not None:
        tabela.append(["Top 5 frente ao acaso", _rotulo(m1["vs_acaso_top5"]), _rotulo(m3["vs_acaso_top5"]), "–"])
    linhas += _tabela(["Métrica", "modelo 1", "modelo 3", "Diferença (3 − 1)"], tabela)
    linhas.append("")
    if res["acaso_top5"] is not None:
        a = res["acaso_top5"]
        linhas += [
            f"Acaso do top 5 no mesmo recorte ({a['n_dias']} dias): média {_num(a['media'])}; "
            f"faixa 2,5%–97,5%: {_ic([a['p2_5'], a['p97_5']])}.",
            "",
        ]
    linhas += ["Ganho (AUC, 3 − 1) e pregões por ano:", ""]
    linhas += _tabela(
        ["Ano", "Pregões", "Ganho"],
        [[ano, res["n_dias_por_ano"].get(ano), _num(ganho)] for ano, ganho in res["ganho_por_ano"].items()],
    )
    linhas.append("")
    return linhas


def _md_so_noticias(res: dict) -> list[str]:
    linhas = [f"- Linhas: {res['n_linhas']}; dias: {res['n_dias']}; dias com AUC: {res['n_dias_auc']}", ""]
    linhas += _tabela(
        ["Métrica", "Valor"],
        [
            ["AUC médio por pregão", _num(res["auc_medio"])],
            ["AUC − 0,5 (referência do acaso: 0,5)", _num(res["auc_menos_0_5"])],
            ["IC 95% de AUC − 0,5", _ic(res["auc_menos_0_5_ic95"])],
            ["IC 99,5% de AUC − 0,5", _ic(res["auc_menos_0_5_ic995"])],
            ["Top 5: taxa de acerto", _num(res["top5_taxa"])],
            ["Top 5: acertos / dias", f"{res['top5_acertos']} / {res['top5_n_dias']}"],
            ["Top 5 frente ao acaso", _rotulo(res["vs_acaso_top5"])],
        ],
    )
    a = res["acaso_top5"]
    linhas += ["", f"Acaso do top 5 ({a['n_dias']} dias): média {_num(a['media'])}; "
               f"faixa 2,5%–97,5%: {_ic([a['p2_5'], a['p97_5']])}.", ""]
    return linhas


def _relatorio(r: dict) -> str:
    an = r["analises"]
    c = r["contagem"]
    ident = r["identificacao"]
    linhas = [
        f"# Sensibilidade da rodada {ident['rodada']:03d}: exploratório",
        "",
        f"**Exploratório.** `modelo_oficial`: false. Não muda hipótese, configuração congelada nem teste final. "
        "Não constitui recomendação de investimento.",
        "",
        f"- Contagem declarada à parte do protocolo: {c['analises']} análises e {c['escopos']} escopos. "
        "Não entra em `docs/protocolo_tentativas.jsonl`.",
        "- IC sem ajuste por múltiplas comparações.",
        "- Só desenvolvimento (`treino.ler_desenvolvimento`): sem banco, sem teste final e sem gravar em modelos/.",
        "",
    ]
    linhas += _md_identificacao(r)

    a = an["a_recorte_noticia"]["recorte_noticia"]
    linhas += ["## (a) Recorte com ≥ 1 notícia: modelo 1 × modelo 3 (dataset todas)", "",
               "Treino em todas as linhas; avaliação só no recorte (`noticias_dia_qtd` bruto >= 1).", ""]
    linhas += _md_dias_perdidos(a) + _md_comparacao(a) + _md_cobertura(a)

    for chave, titulo, nome in (("b_principais", "(b) Dataset principais", "principais"),
                                ("c_hora_real_noite", "(c) Dataset hora_real_noite", "hora_real_noite")):
        bloco = an[chave]
        linhas += [f"## {titulo}: modelo 3 treinado no dataset {nome} × modelo 1 de todas", ""]
        if chave == "c_hora_real_noite":
            linhas += ["**Cobertura baixa**: a tabela de papéis por dia por ano no recorte mostra quantos "
                       "papéis cada dia tem; o top 5 depende de dias com ao menos 5 papéis.", ""]
        linhas += ["### Todas as linhas", ""] + _md_comparacao(bloco["todas"])
        linhas += ["### Recorte ≥ 1 notícia (qtd bruta da própria versão)", ""]
        linhas += _md_dias_perdidos(bloco["recorte_noticia"]) + _md_comparacao(bloco["recorte_noticia"])
        linhas += _md_cobertura(bloco["recorte_noticia"])

    d = an["d_so_noticias"]
    linhas += [f"## (d) Só notícias: {NOMES_FAMILIA[ident['familia']]} com `preparacao.NOTICIAS_DIA` (dataset todas)", "",
               "Sem comparação contra o modelo 1. A referência é o acaso: AUC 0,5 e a faixa do top 5.", ""]
    linhas += ["### Principal: recorte ≥ 1 notícia", ""]
    linhas += _md_dias_perdidos(d["recorte_noticia"]) + _md_so_noticias(d["recorte_noticia"])
    linhas += _md_cobertura(d["recorte_noticia"])
    linhas += ["### Secundária: todas as linhas", ""] + _md_so_noticias(d["todas_linhas"])
    linhas += ["Ressalvas da secundária:", "",
               "- Dias sem notícia dão score empatado: o top 5 desses dias sai em ordem alfabética de ticker.",
               "- No período sem coleta (NaN de `noticias_dia_qtd`, jan–jul/2025), o AUC é 0,5 exato.",
               "- Não é recorte: os números misturam dias com e sem notícia.", ""]
    return "\n".join(linhas) + "\n"


def caminhos_entrada(rodada: int, congelado: Path | None = None,
                     configuracao: Path | None = None) -> tuple[Path, Path | None]:
    """Congelado e configuração final da rodada. Sem argumento explícito, em `docs/`: rodada 001 usa o congelado e a
    logística (sem configuração); da rodada 002 em diante, `protocolo_congelado_rodada_NNN.json` e
    `configuracao_final_rodada_NNN.json`.
    """
    if congelado is None:
        congelado = PASTA_DOCS_PADRAO / f"protocolo_congelado_rodada_{rodada:03d}.json"
    if configuracao is None and rodada >= 2:
        configuracao = PASTA_DOCS_PADRAO / f"configuracao_final_rodada_{rodada:03d}.json"
    return Path(congelado), configuracao


def main(argv=None, params=None, lim=be.LIMITES_BUSCA, prever=None) -> int:
    """Ponto de entrada (`python -m processamento.experimento.sensibilidade`).

    Devolve 0 em sucesso; 2 se faltar dataset, o sha256 do congelado não bater, uma conferência falhar ou a saída já existir.
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.experimento.sensibilidade",
        description="Análises exploratórias de sensibilidade de uma rodada (padrão: 001). "
                    "Só lê os CSV do desenvolvimento (nada do banco).",
    )
    parser.add_argument("--data", type=treino._data_argumento, required=True, help="data do dataset (AAAA-MM-DD)")
    parser.add_argument("--rodada", type=int, default=1, help="número da rodada (padrão: 1)")
    parser.add_argument("--congelado", type=Path, default=None,
                        help="protocolo congelado da rodada (padrão: docs/protocolo_congelado_rodada_NNN.json)")
    parser.add_argument("--configuracao", type=Path, default=None,
                        help="configuração final da rodada (padrão: docs/configuracao_final_rodada_NNN.json, da rodada 2 em diante)")
    parser.add_argument("--pasta-datasets", type=Path, default=treino.PASTA_DATASETS_PADRAO,
                        help="pasta dos CSV (padrão: saida/experimento)")
    parser.add_argument("--pasta-docs", type=Path, default=PASTA_DOCS_PADRAO,
                        help="pasta de saída do .md e do .json (padrão: docs)")
    args = parser.parse_args(argv)
    congelado, configuracao = caminhos_entrada(args.rodada, args.congelado, args.configuracao)
    try:
        caminho_md, _ = executar(args.pasta_datasets, args.pasta_docs, data=args.data, congelado=congelado,
                                 configuracao=configuracao, rodada=args.rodada, params=params, lim=lim, prever=prever)
    except (treino.ErroDataset, ErroSensibilidade, FileExistsError) as erro:
        print(f"{erro}")
        return 2
    print(f"Relatório gravado: {caminho_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
