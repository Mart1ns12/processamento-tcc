"""Regra da busca pelo melhor modelo (docs/protocolo_variaveis.md, seção 6). Funções puras: sem arquivo,
banco, rede ou treino.

Candidatos em ordem de simplicidade (logística, XGBoost, LightGBM). A referência (XGBoost do ponto de
partida) fica se ninguém passar. A combinação por rank é só relatada: não pode vencer.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from processamento.experimento import preparacao, protocolo

REFERENCIA = "referencia"
COMBINACAO = "combinacao"
LIMITES_BUSCA = replace(protocolo.LIMITES, percentis_ic=(0.25, 99.75), reamostragens=10_000)
_CHAVES = ["data", "ticker"]


def _combinacoes(params) -> list[tuple[int, int]]:
    """(max_depth, min_child_weight) da grade, na ordem de simplicidade: menor profundidade, depois maior mcw.

    Como no treino, hiperparâmetro fora da grade fica no valor de `params.xgboost`.
    """
    md = params.grade.get("max_depth", (params.xgboost["max_depth"],))
    mcw = params.grade.get("min_child_weight", (params.xgboost["min_child_weight"],))
    pares = [(a, b) for a in md for b in mcw]
    return sorted(pares, key=lambda par: (par[0], -par[1]))


def candidatos(params) -> list[dict]:
    """Candidatos {nome, familia, hiper} na ordem da tabela da seção 6, sem a referência nem a combinação.

    Logística (sem hiperparâmetros da grade), XGBoost (sem a combinação do ponto de partida, que é a
    referência) e LightGBM (todas as combinações da grade).
    """
    referencia = (params.xgboost["max_depth"], params.xgboost["min_child_weight"])
    combos = _combinacoes(params)
    saida = [{"nome": "logistica", "familia": "logistica", "hiper": None}]
    for md, mcw in combos:
        if (md, mcw) != referencia:
            saida.append({"nome": f"xgb_{md}_{mcw}", "familia": "xgb",
                          "hiper": {**params.xgboost, "max_depth": md, "min_child_weight": mcw}})
    for md, mcw in combos:
        saida.append({"nome": f"lgbm_{md}_{mcw}", "familia": "lgbm",
                      "hiper": {**params.xgboost, "max_depth": md, "min_child_weight": mcw}})
    return saida


def combinar_por_rank(preds: list[pd.DataFrame]) -> pd.DataFrame:
    """Média dos ranks por pregão das previsões (`score`). As linhas têm de ser as mesmas em todas (senão ValueError)."""
    base = preds[0].reset_index(drop=True)
    ranks = []
    for pred in preds:
        pred = pred.reset_index(drop=True)
        if not pred[_CHAVES].equals(base[_CHAVES]):
            raise ValueError("as previsões devem ter as mesmas linhas (data e ticker, na mesma ordem)")
        ranks.append(preparacao.rank_no_pregao(pred, ["score"])["score"].to_numpy(dtype=float))
    saida = base.copy()
    saida["score"] = np.mean(ranks, axis=0)
    return saida


def escolher(avaliacoes: dict[str, dict], medidas: dict[str, dict], dif_para_melhor) -> dict:
    """Vencedor pela seção 6. `avaliacoes` e `medidas` têm uma entrada por candidato (ordem de simplicidade),
    mais, opcionalmente, `COMBINACAO`, que só é relatada. `dif_para_melhor(nome_melhor, nome)` devolve o IC
    99,5% de `melhor − nome`.

    Nenhum aprovado: fica a referência. Com aprovados, "melhor" é o de maior ganho (empate: o primeiro) e
    vence o primeiro, na ordem de simplicidade, cuja diferença para ele não é clara (limite inferior ≤ 0).
    Sem IC, a diferença também não é clara (fica o mais simples).
    """
    aprovados = [n for n, av in avaliacoes.items() if n != COMBINACAO and av["aprovado"]]
    combinacao_aprovada = bool(avaliacoes.get(COMBINACAO, {}).get("aprovado", False))
    if not aprovados:
        return {"vencedor": REFERENCIA, "melhor": None, "aprovados": [],
                "combinacao_aprovada": combinacao_aprovada,
                "motivo": "nenhum candidato aprovado: fica a referência"}

    melhor = max(aprovados, key=lambda n: medidas[n]["ganho"])
    vencedor = melhor
    for nome in aprovados:
        if nome == melhor:
            vencedor = nome
            break
        lo, _ = dif_para_melhor(melhor, nome)
        if lo is None or lo <= 0:
            vencedor = nome
            break

    if vencedor == melhor:
        motivo = f"{melhor} tem o maior ganho e nenhum mais simples fica sem diferença clara"
    else:
        motivo = f"{vencedor} é o mais simples entre os aprovados sem diferença clara para {melhor}"
    return {"vencedor": vencedor, "melhor": melhor, "aprovados": aprovados,
            "combinacao_aprovada": combinacao_aprovada, "motivo": motivo}
