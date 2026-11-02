"""Previsão do dia: top 5 do modelo 3, motivos (contribuições do XGBoost), chance e sombras (plano da etapa 6, fase 5).

Funções puras sobre DataFrames e arrays. Nada de banco, rede ou arquivo. A chance só sai com a
probabilidade quando há calibração aprovada E `liberar_chance: true` (F16); senão a probabilidade não é exportada.
Os textos dos motivos ("Notícias ... (3 notícias)") ficam para a etapa 7: aqui sai só fator, contribuição,
valor bruto e efeito. Linguagem: "estimativa", "experimento", "maior chance segundo o modelo".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.experimento import avaliacao, modelos, preparacao
from processamento.experimento.parametros import ParametrosTreino

MEDIA_DE_REFERENCIA = 0.5


def efeito(contrib: float, limiar: float) -> str:
    """"ajudou" se a contribuição passa do limiar para cima; "atrapalhou" se fica abaixo de −limiar; senão "neutro"."""
    if contrib > limiar:
        return "ajudou"
    if contrib < -limiar:
        return "atrapalhou"
    return "neutro"


def motivos(contrib: pd.Series, valores: pd.Series, qtd: int, limiar: float) -> list[dict]:
    """Os `qtd` fatores de maior |contribuição| (ignora "vies"; empate pelo nome do fator, asc).

    `valores` é o dataset BRUTO da linha (antes do rank); ausência vira None.
    """
    fatores = [f for f in contrib.index if f != "vies"]
    ordem = sorted(fatores, key=lambda f: (-abs(float(contrib[f])), f))[:qtd]
    saida = []
    for fator in ordem:
        c = float(contrib[fator])
        bruto = valores[fator]
        saida.append(
            {
                "fator": fator,
                "contribuicao": c,
                "valor": None if pd.isna(bruto) else float(bruto),
                "efeito": efeito(c, limiar),
            }
        )
    return saida


def chance(prob: float, liberar_chance: bool, calibracao_aprovada: bool) -> dict:
    """Chance do top: a probabilidade só aparece com calibração aprovada e `liberar_chance` ligado (F16)."""
    if liberar_chance and calibracao_aprovada:
        return {"valor": float(prob), "media": MEDIA_DE_REFERENCIA, "exibir": True, "status": "ok"}
    return {
        "valor": None,
        "media": MEDIA_DE_REFERENCIA,
        "exibir": False,
        "status": "calibracao_nao_conferida",
    }


def _ranking(df_dia: pd.DataFrame, scores: np.ndarray, k: int) -> pd.DataFrame:
    """Top k do pregão pela ordem de `avaliacao.ordenar_no_dia` (score desc, ticker asc).

    `pos` guarda a posição da linha em `df_dia`, para achar prob, contribuições e valores brutos.
    """
    base = pd.DataFrame(
        {
            "data": 0,
            "ticker": df_dia["ticker"].to_numpy(),
            "score": np.asarray(scores, dtype=float),
            "pos": np.arange(len(df_dia)),
        }
    )
    return avaliacao.ordenar_no_dia(base).head(k)


def ordenar_top(df_dia: pd.DataFrame, scores: np.ndarray, k: int) -> list[str]:
    """Os `k` primeiros tickers do dia pelo score (maior primeiro; empate por ticker asc)."""
    return _ranking(df_dia, scores, k)["ticker"].tolist()


def top_do_dia(
    preparado_dia: pd.DataFrame,
    bruto_dia: pd.DataFrame,
    modelo,
    metadados: dict,
    params: ParametrosTreino,
) -> list[dict]:
    """Top k (k = `params.topk[0]`) do modelo 3 no dia, com chance e motivos.

    `preparado_dia` e `bruto_dia` precisam ter o mesmo índice e a mesma ordem de linhas
    (`preparacao.rank_no_pregao` preserva o índice).
    """
    if not preparado_dia.index.equals(bruto_dia.index):
        raise ValueError("preparado_dia e bruto_dia precisam ter o mesmo índice e a mesma ordem de linhas")
    colunas = metadados["colunas"]
    X = preparado_dia[colunas]
    prob = modelos.prob_xgb(modelo, X)
    # os motivos falam das colunas do dataset, mesmo se o modelo usa uma variante preparada
    contrib = modelos.contribuicoes(modelo, X).rename(columns=preparacao.COLUNA_BRUTA)
    aprovada = metadados["calibracao"]["aprovada"]
    brutos = bruto_dia[[preparacao.COLUNA_BRUTA.get(c, c) for c in colunas]]

    ranking = _ranking(preparado_dia, prob, params.topk[0])
    itens = []
    for posicao, pos, ticker in zip(ranking["posicao"].tolist(), ranking["pos"].tolist(), ranking["ticker"].tolist()):
        itens.append(
            {
                "posicao": int(posicao),
                "ticker": ticker,
                "chance": chance(prob[pos], params.liberar_chance, aprovada),
                "motivos": motivos(contrib.iloc[pos], brutos.iloc[pos], params.motivos_qtd, params.motivos_limiar),
            }
        )
    return itens


def top_sombra_volatilidade(preparado_dia: pd.DataFrame, k: int) -> list[str]:
    """Sombra da regra da volatilidade: menor `volatilidade_20d` do pregão primeiro (score de `modelos`)."""
    return ordenar_top(preparado_dia, modelos.score_volatilidade(preparado_dia), k)


def top_sombra_modelo(preparado_dia: pd.DataFrame, modelo, colunas: list[str], k: int) -> list[str]:
    """Sombra do modelo 1: os k maiores `prob_xgb` do pregão, com as colunas do modelo 1."""
    return ordenar_top(preparado_dia, modelos.prob_xgb(modelo, preparado_dia[colunas]), k)
