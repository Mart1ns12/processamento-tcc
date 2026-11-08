"""Fábrica para o núcleo do treino (tests/test_treino_nucleo.py): dataset sintético e parâmetros de teste.

Tickers fictícios (AAAA3, BBBB3, ...), variáveis N(0, 1) geradas com numpy e pregões de `fabrica_precos`.
Os nomes de colunas são os de `dataset.COLUNAS_DATASET`. Nenhuma função usa banco ou rede.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from fabrica_precos import pregoes_uteis
from processamento.experimento import dataset
from processamento.experimento.parametros import carregar_parametros_treino
from processamento.experimento.preparacao import COLUNAS_PROTOCOLO, COLUNAS_RANK, VERSAO_PREPARACAO
from processamento.experimento.tom import COLUNAS_NOTICIAS

TICKERS = [f"{letra * 4}3" for letra in "ABCDEFGHIJKL"]
VERSOES_PADRAO = ("todas", "principais", "hora_real_noite")


def dataset_sintetico(inicio: str = "2025-08-01", n_pregoes: int = 130, n_tickers: int = 12, semente: int = 0) -> pd.DataFrame:
    """Uma linha por pregão × ticker, com as colunas de `dataset.COLUNAS_DATASET`.

    Notícias: `noticias_dia_qtd` ~ Poisson(1); tom e extremo são NaN quando a quantidade é 0.
    Alvo: `ret_t1 = ibov + 0.004·ret_1d + N(0, 0.01)` e `alvo = (ret_t1 > ret_ibov_t1)`. No último
    pregão, as colunas de alvo ficam NaN.
    """
    rng = np.random.default_rng(semente)
    cal = pregoes_uteis(n_pregoes, inicio)
    tickers = np.array(TICKERS[:n_tickers])
    forma = (n_pregoes, n_tickers)

    v = {c: rng.normal(0, 1, forma) for c in COLUNAS_RANK if c not in COLUNAS_PROTOCOLO}
    # rng próprio: as colunas do protocolo não mudam o sorteio das outras (os valores antigos ficam iguais)
    rng_protocolo = np.random.default_rng(semente + 10_000)
    v.update({c: rng_protocolo.normal(0, 1, forma) for c in COLUNAS_PROTOCOLO})
    qtd = rng.poisson(1.0, forma).astype(float)
    vazio = qtd == 0
    v["noticias_dia_qtd"] = qtd
    v["noticias_dia_tom"] = np.where(vazio, np.nan, rng.normal(0, 1, forma))
    v["noticias_dia_extremo"] = np.where(vazio, np.nan, rng.normal(0, 1, forma))
    for c in ("mudanca_tom", "tom_setor", "tom_mercado"):
        v[c] = rng.normal(0, 1, forma)

    ibov = rng.normal(0, 0.01, n_pregoes)
    ret_ibov = np.broadcast_to(ibov[:, None], forma).copy()
    ret_t1 = ret_ibov + 0.004 * v["ret_1d"] + rng.normal(0, 0.01, forma)
    alvo = (ret_t1 > ret_ibov).astype(float)
    alvo_abertura = (rng.random(forma) < 0.5).astype(float)
    indice_dia = np.arange(n_pregoes)[:, None]
    valido = np.broadcast_to(np.where(indice_dia % 3 == 2, 0.0, 1.0), forma).copy()
    dia_resultado = rng.random(forma) < 0.05

    for arranjo in (alvo, alvo_abertura, valido, ret_t1, ret_ibov):
        arranjo[-1, :] = np.nan

    setores = np.array(["S1" if j % 2 == 0 else "S2" for j in range(n_tickers)])
    campos = {
        "data": np.repeat(pd.DatetimeIndex(cal).to_numpy(), n_tickers),
        "ticker": np.tile(tickers, n_pregoes),
        "empresa": np.tile(np.array([f"Empresa {t}" for t in tickers]), n_pregoes),
        "setor": np.tile(setores, n_pregoes),
        "universo": np.full(n_pregoes * n_tickers, "composicao_atual"),
        "dia_resultado": dia_resultado.ravel(),
        "alvo": alvo.ravel(),
        "alvo_abertura": alvo_abertura.ravel(),
        "alvo_abertura_valido": valido.ravel(),
        "ret_t1": ret_t1.ravel(),
        "ret_ibov_t1": ret_ibov.ravel(),
    }
    campos.update({c: arranjo.ravel() for c, arranjo in v.items()})
    return pd.DataFrame({c: campos[c] for c in dataset.COLUNAS_DATASET})


def _perturbar_noticias(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Cópia com ruído só nas colunas de notícias (NaN continua NaN)."""
    saida = df.copy()
    for c in COLUNAS_NOTICIAS:
        saida[c] = saida[c] + rng.normal(0, 0.1, len(saida))
    return saida


def gravar_versoes(pasta: Path, df: pd.DataFrame, versoes: tuple[str, ...] = VERSOES_PADRAO) -> dict[str, Path]:
    """Grava uma versão por nome com `dataset.salvar_dataset` (CSV e JSON com sha256).

    "todas" é o próprio `df`. As outras são o mesmo `df` com as notícias perturbadas. Devolve {versão: CSV}.
    """
    saida: dict[str, Path] = {}
    inicio = pd.Timestamp(df["data"].min()).strftime("%Y-%m-%d")
    for i, versao in enumerate(versoes):
        atual = df.copy() if versao == "todas" else _perturbar_noticias(df, np.random.default_rng(1000 + i))
        info = {
            "versao_noticias": versao,
            "versao_preparacao": VERSAO_PREPARACAO,
            "linhas": len(atual),
            "pregoes": int(atual["data"].nunique()),
            "cobertura_inicio": inicio,
            "lidas": len(atual),
            "fora_versao": 0,
            "papel_vazio_fora": 0,
            "preparadas": len(atual),
            "descartadas_fora_da_janela": 0,
        }
        saida[versao] = dataset.salvar_dataset(atual, info, pasta)
    return saida


def params_teste(**trocas):
    """Parâmetros do treino pequenos para teste: teste final de 2026-01-02, 20 árvores, sorteios reduzidos.

    `teste_final_fim` fica None (trava ativa). Qualquer campo pode ser trocado por `**trocas`.
    """
    base = carregar_parametros_treino()
    ajustes = dict(
        treino_minimo_meses=2,
        teste_final_inicio=date(2026, 1, 2),
        teste_final_fim=None,
        xgboost={**base.xgboost, "n_estimators": 20},
        grade={"max_depth": (2,)},
        acaso_sorteios=200,
        bootstrap_reamostragens=50,
        calibracao_linhas_minimas=100,
        familia_producao="xgb",  # os fixtures ajustam XGBoost; o YAML de produção também é o XGBoost desde a rodada 3 (testes da logística pedem)
    )
    ajustes.update(trocas)
    return dataclasses.replace(base, **ajustes)
