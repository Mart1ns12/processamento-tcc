"""Testes da regra da busca (processamento/experimento/busca.py, seção 6 do protocolo): candidatos, limites,
escolha do vencedor e combinação por rank. Funções puras; dados pequenos em memória; nada de banco ou rede.
"""

from dataclasses import asdict

import pandas as pd
import pytest

from fabrica_treino import params_teste
from processamento.experimento import busca, protocolo
from processamento.experimento.parametros import carregar_parametros_treino

NOMES_YAML = [
    "logistica", "xgb_2_200", "xgb_2_50", "xgb_3_200",
    "lgbm_2_200", "lgbm_2_50", "lgbm_3_200", "lgbm_3_50",
]


def _av(*aprovados):
    """Avaliações: aprovado só para os nomes dados, na ordem de simplicidade da lista."""
    return {nome: {"aprovado": nome in aprovados} for nome in NOMES_YAML}


def _medidas(**ganhos):
    return {nome: {"ganho": ganho} for nome, ganho in ganhos.items()}


def _ic(valores):
    """`dif_para_melhor` fixo: devolve o IC de cada candidato (a chave é o nome do candidato)."""
    return lambda melhor, nome: valores[nome]


# --- candidatos e limites -------------------------------------------------------------------------


def test_candidatos_com_a_grade_do_yaml():
    nomes = [c["nome"] for c in busca.candidatos(carregar_parametros_treino())]
    assert nomes == NOMES_YAML


def test_candidatos_familia_e_hiperparametros():
    por_nome = {c["nome"]: c for c in busca.candidatos(carregar_parametros_treino())}
    assert por_nome["logistica"]["familia"] == "logistica"
    assert por_nome["xgb_2_200"]["familia"] == "xgb"
    assert por_nome["lgbm_3_50"]["familia"] == "lgbm"
    assert por_nome["lgbm_3_50"]["hiper"]["max_depth"] == 3
    assert por_nome["lgbm_3_50"]["hiper"]["min_child_weight"] == 50
    assert por_nome["xgb_2_200"]["hiper"]["learning_rate"] == carregar_parametros_treino().xgboost["learning_rate"]


def test_candidatos_sem_a_referencia_xgb_3_50():
    params = params_teste(grade={"max_depth": (2, 3), "min_child_weight": (50, 200)})
    nomes = [c["nome"] for c in busca.candidatos(params)]
    assert nomes == NOMES_YAML
    assert "xgb_3_50" not in nomes
    assert "lgbm_3_50" in nomes


def test_candidatos_grade_sem_mcw_usa_o_valor_do_xgboost():
    nomes = [c["nome"] for c in busca.candidatos(params_teste(grade={"max_depth": (2, 3)}))]
    assert nomes == ["logistica", "xgb_2_50", "lgbm_2_50", "lgbm_3_50"]


def test_limites_da_busca():
    limites = busca.LIMITES_BUSCA
    assert limites.percentis_ic == (0.25, 99.75)
    assert limites.reamostragens == 10_000
    base = asdict(protocolo.LIMITES)
    mudados = {"percentis_ic", "reamostragens"}
    assert {k: v for k, v in asdict(limites).items() if k not in mudados} == \
        {k: v for k, v in base.items() if k not in mudados}


# --- escolha do vencedor --------------------------------------------------------------------------


def test_ninguem_aprovado_fica_a_referencia():
    resultado = busca.escolher(_av(), _medidas(), _ic({}))
    assert resultado["vencedor"] == "referencia"
    assert resultado["melhor"] is None
    assert resultado["aprovados"] == []
    assert resultado["combinacao_aprovada"] is False


def test_so_lgbm_2_50_aprovado_vence():
    resultado = busca.escolher(_av("lgbm_2_50"), _medidas(lgbm_2_50=0.01), _ic({}))
    assert resultado["vencedor"] == "lgbm_2_50"
    assert resultado["aprovados"] == ["lgbm_2_50"]


def test_logistica_fica_quando_a_diferenca_nao_e_clara():
    medidas = _medidas(logistica=0.007, lgbm_3_50=0.009)
    ic = {"logistica": (-0.001, 0.004)}
    resultado = busca.escolher(_av("logistica", "lgbm_3_50"), medidas, _ic(ic))
    assert resultado["vencedor"] == "logistica"
    assert resultado["melhor"] == "lgbm_3_50"


def test_melhor_vence_quando_a_diferenca_e_clara():
    medidas = _medidas(logistica=0.007, lgbm_3_50=0.009)
    ic = {"logistica": (0.0001, 0.004)}
    resultado = busca.escolher(_av("logistica", "lgbm_3_50"), medidas, _ic(ic))
    assert resultado["vencedor"] == "lgbm_3_50"


def test_limite_inferior_zero_e_diferenca_nao_clara():
    medidas = _medidas(logistica=0.007, lgbm_3_50=0.009)
    ic = {"logistica": (0.0, 0.004)}
    resultado = busca.escolher(_av("logistica", "lgbm_3_50"), medidas, _ic(ic))
    assert resultado["vencedor"] == "logistica"


def test_empate_exato_vai_para_o_mais_simples():
    medidas = _medidas(xgb_2_200=0.012, lgbm_2_200=0.012)
    resultado = busca.escolher(_av("xgb_2_200", "lgbm_2_200"), medidas, _ic({"lgbm_2_200": (-0.001, 0.001)}))
    assert resultado["vencedor"] == "xgb_2_200"
    assert resultado["melhor"] == "xgb_2_200"


def test_so_a_combinacao_aprovada_nao_vence():
    avaliacoes = {**_av(), "combinacao": {"aprovado": True}}
    medidas = _medidas(combinacao=0.05)
    resultado = busca.escolher(avaliacoes, medidas, _ic({}))
    assert resultado["vencedor"] == "referencia"
    assert resultado["combinacao_aprovada"] is True
    assert resultado["aprovados"] == []


# --- combinação por rank --------------------------------------------------------------------------


def _previsoes(scores_por_modelo):
    """Um DataFrame por modelo: 3 ações num único pregão, mesmas linhas, scores dados."""
    linhas = ["AAAA3", "BBBB3", "CCCC3"]
    dados = []
    for scores in scores_por_modelo:
        dados.append(pd.DataFrame({
            "data": pd.Timestamp("2025-03-03"), "ticker": linhas, "score": scores,
        }))
    return dados


def test_combinar_por_rank_media_dos_ranks():
    preds = _previsoes([[0.9, 0.5, 0.1], [0.1, 0.5, 0.9], [0.9, 0.2, 0.3]])
    combinada = busca.combinar_por_rank(preds)
    assert list(combinada["ticker"]) == ["AAAA3", "BBBB3", "CCCC3"]
    assert combinada["score"].tolist() == pytest.approx([2 / 3, 1 / 3, 1 / 2], abs=1e-12)


def test_combinar_por_rank_recusa_linhas_diferentes():
    preds = _previsoes([[0.9, 0.5, 0.1], [0.1, 0.5, 0.9]])
    preds[1] = preds[1].assign(ticker=["AAAA3", "BBBB3", "ZZZZ3"])
    with pytest.raises(ValueError):
        busca.combinar_por_rank(preds)
