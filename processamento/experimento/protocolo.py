"""Regras do protocolo de teste de variáveis novas (docs/protocolo_variaveis.md, seções 2 a 5).

Funções puras: não leem arquivo, não acessam banco e não treinam. Os limites são constantes
congeladas. Mudar um valor depois da primeira rodada completa invalida as rodadas (seção 5).
Comparações com limite são feitas sem arredondar; a queda do top 5 usa `Fraction` para não errar na borda.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction

import pandas as pd

from processamento.experimento import avaliacao

ANOS_PROTOCOLO = (2021, 2022, 2023, 2024, 2025, 2026)
ORDEM_TESTES = ("controle", "bloco_a", "bloco_b", "bloco_c", "bloco_d", "bloco_e")
BLOCOS_ADOTAVEIS = ("bloco_a", "bloco_b", "bloco_c", "bloco_d")   # só estes entram no conjunto
DATA_LIMITE = date(2026, 6, 23)


@dataclass(frozen=True)
class LimitesProtocolo:
    ganho_minimo: float = 0.005
    percentis_ic: tuple[float, float] = (0.5, 99.5)
    bloco_bootstrap: int = 5
    reamostragens: int = 2000
    anos: tuple[int, ...] = ANOS_PROTOCOLO
    anos_positivos_minimos: int = 4
    piso_ano: float = -0.005
    k_top: int = 5
    queda_top_maxima: Fraction = Fraction(1, 200)   # 0,5 ponto percentual
    anos_regime: tuple[int, ...] = (2024,)          # critério 5 mede só 2024 (fato_relevante_cvm vazio em 2023)
    anos_regime_relato: tuple[int, ...] = (2023, 2024)   # só para constar no relatório; não decide


LIMITES = LimitesProtocolo()


def criterio_1(ganho: float | None, lim: LimitesProtocolo = LIMITES) -> bool:
    """Ganho médio de AUC por pregão maior que o mínimo (sem arredondar)."""
    return ganho is not None and ganho > lim.ganho_minimo


def criterio_2(ic: tuple[float | None, float | None], lim: LimitesProtocolo = LIMITES) -> bool:
    """Limite inferior do IC acima de zero. IC tocando zero reprova."""
    return ic[0] is not None and ic[0] > 0


def criterio_3(ganhos_ano: dict[int, float | None], lim: LimitesProtocolo = LIMITES) -> bool:
    """Ganho positivo em pelo menos `anos_positivos_minimos` anos e nenhum ano abaixo de `piso_ano`.
    Ano ausente não entra na contagem nem no piso. Zero não é positivo, mas não fica abaixo do piso."""
    valores = [ganhos_ano.get(a) for a in lim.anos]
    positivos = sum(v is not None and v > 0 for v in valores)
    return positivos >= lim.anos_positivos_minimos and all(v is None or v >= lim.piso_ano for v in valores)


def criterio_4(acertos_base: int, acertos_cand: int, k: int, n_dias: int, lim: LimitesProtocolo = LIMITES) -> bool:
    """Queda da taxa de acerto do top k no período, em fração exata, não maior que o limite."""
    return n_dias > 0 and Fraction(acertos_base - acertos_cand, k * n_dias) <= lim.queda_top_maxima


def criterio_5(ganho_regime: float | None) -> bool:
    """Ganho positivo no período de regime (só 2024)."""
    return ganho_regime is not None and ganho_regime > 0


def _anos_do_pregao(dif: pd.Series) -> pd.Index:
    return pd.to_datetime(dif.index).year


def _media(valores: pd.Series) -> float | None:
    return float(valores.mean()) if len(valores) else None


def medir_comparacao(pred_base: pd.DataFrame, pred_cand: pd.DataFrame, semente: int, lim: LimitesProtocolo = LIMITES) -> dict:
    """Mede o candidato contra a base. Exige as mesmas linhas, na mesma ordem (senão ValueError)."""
    chaves = ["data", "ticker"]
    if not pred_base[chaves].reset_index(drop=True).equals(pred_cand[chaves].reset_index(drop=True)):
        raise ValueError("as previsões devem ter as mesmas linhas (data e ticker, na mesma ordem)")

    aucs_base = avaliacao.auc_por_pregao(pred_base)
    aucs_cand = avaliacao.auc_por_pregao(pred_cand)
    dif = avaliacao.diferenca_pareada(aucs_cand, aucs_base)
    ic = avaliacao.ic_bootstrap_blocos(
        dif.to_numpy(), lim.bloco_bootstrap, lim.reamostragens, semente, percentis=lim.percentis_ic
    )

    por_pregao = pd.Series(dif.to_numpy(dtype=float), index=_anos_do_pregao(dif))
    ganho_por_ano = {int(a): float(v) for a, v in por_pregao.groupby(level=0).mean().items()}
    n_dias_por_ano = {int(a): int(n) for a, n in por_pregao.groupby(level=0).size().items()}
    no_regime = por_pregao[por_pregao.index.isin(lim.anos_regime)]
    regime = {
        "ganho": _media(no_regime),
        "por_ano": {a: ganho_por_ano[a] for a in lim.anos_regime_relato if a in ganho_por_ano},
    }

    d_base = avaliacao.resumo_diario(pred_base, lim.k_top)
    d_cand = avaliacao.resumo_diario(pred_cand, lim.k_top)
    if len(d_base) != len(d_cand):
        raise ValueError("o top k deve ter o mesmo número de pregões nas duas previsões")
    n_dias = len(d_base)
    acertos_base = int(d_base["acertos_top"].sum())
    acertos_cand = int(d_cand["acertos_top"].sum())
    taxa_base = acertos_base / (lim.k_top * n_dias) if n_dias else None
    taxa_cand = acertos_cand / (lim.k_top * n_dias) if n_dias else None

    return {
        "n_dias_auc": int(len(dif)),
        "auc_base": _media(aucs_base),
        "auc_candidato": _media(aucs_cand),
        "ganho": _media(dif),
        "ic": ic,
        "ganho_por_ano": ganho_por_ano,
        "n_dias_por_ano": n_dias_por_ano,
        "top": {
            "k": lim.k_top,
            "n_dias": n_dias,
            "acertos_base": acertos_base,
            "acertos_candidato": acertos_cand,
            "taxa_base": taxa_base,
            "taxa_candidato": taxa_cand,
            "queda_pontos": None if taxa_base is None else (taxa_base - taxa_cand) * 100,
        },
        "regime": regime,
    }


def avaliar_criterios(medidas: dict, aplica_5: bool, lim: LimitesProtocolo = LIMITES) -> dict:
    """Aplica os critérios 1 a 5 às medidas. `c5` é None quando o critério não se aplica ao teste."""
    top = medidas["top"]
    c1 = criterio_1(medidas["ganho"], lim)
    c2 = criterio_2(medidas["ic"], lim)
    c3 = criterio_3(medidas["ganho_por_ano"], lim)
    c4 = criterio_4(top["acertos_base"], top["acertos_candidato"], top["k"], top["n_dias"], lim)
    c5 = criterio_5(medidas["regime"]["ganho"]) if aplica_5 else None
    aprovado = c1 and c2 and c3 and c4 and (c5 is None or c5)
    return {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "aprovado": bool(aprovado)}


def decidir_conjunto(aprovados: list[str], ganhos: dict[str, float], conjunto_aprovado: bool | None) -> list[str]:
    """Blocos adotados de A a D. Até um aprovado: os próprios. Dois ou mais: todos se o conjunto passou;
    senão só o de maior ganho (empate: o primeiro na ordem de BLOCOS_ADOTAVEIS)."""
    ordenados = [b for b in BLOCOS_ADOTAVEIS if b in aprovados]
    if len(ordenados) <= 1 or conjunto_aprovado:
        return ordenados
    melhor = max(ordenados, key=lambda b: (ganhos[b], -BLOCOS_ADOTAVEIS.index(b)))
    return [melhor]


def decidir_rodada(avaliacoes: dict[str, dict], adotados: list[str], regras_mudaram: bool) -> dict:
    """Status da rodada. Controle aprovado ou regras alteradas: inválida, sem bloco adotado."""
    motivos: list[str] = []
    if avaliacoes["controle"]["aprovado"]:
        motivos.append("controle aprovado: possível vazamento ou defeito; investigar antes de adotar qualquer bloco")
    if regras_mudaram:
        motivos.append("regras do protocolo (seções 3 a 5) ou limites diferentes da 1ª rodada completa")
    if motivos:
        return {"status": "invalida", "motivos": motivos, "adotados": [], "bloco_e_aprovado": False}
    return {
        "status": "valida",
        "motivos": [],
        "adotados": list(adotados),
        "bloco_e_aprovado": bool(avaliacoes["bloco_e"]["aprovado"]),
    }
