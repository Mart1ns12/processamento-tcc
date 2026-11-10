"""Testes do bloco `treino` de config/parametros.yaml (plano da etapa 6, fase 1)."""

from datetime import date

import pytest

from processamento import calendario
from processamento.experimento.parametros import (
    ErroParametrosExperimento,
    carregar_parametros_treino,
)

_CABECALHO_YAML = """fuso: "America/Sao_Paulo"
corte_noite: "08:00"
horarios_b3_valido_ate: "2027-03-12"
horarios_b3:
  - {a_partir_de: "2026-03-09", abertura: "10:00", fechamento: "17:00"}
"""

_BLOCO_VALIDO = """treino:
  semente: 20261023
  inicio_experimento: "cobertura"
  treino_minimo_meses: 3
  embargo_pregoes: 1
  teste_final:
    inicio: "2026-06-23"
    fim: null
    liberado: false
  topk: [5, 3]
  xgboost: {n_estimators: 300, max_depth: 3, learning_rate: 0.03, subsample: 0.8, colsample_bytree: 0.8, min_child_weight: 50, reg_lambda: 5}
  grade: {max_depth: [2, 3], min_child_weight: [50, 200]}
  ganho_minimo_bloco: 0.005
  logistica_c: 1.0
  acaso_sorteios: 10000
  bootstrap_reamostragens: 2000
  bootstrap_bloco_pregoes: 5
  motivos_qtd: 3
  motivos_limiar: 0.01
  calibracao: {bins: 10, ece_maximo: 0.02, linhas_minimas: 5000, liberar_chance: false}
"""


def _escrever(tmp_path, bloco: str) -> str:
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(_CABECALHO_YAML + bloco, encoding="utf-8")
    return str(caminho)


# --- arquivo real ----------------------------------------------------------------------------


def test_arquivo_real_carrega_os_valores_do_plano():
    params = carregar_parametros_treino()
    assert params.inicio_experimento == "2021-01-01"
    assert params.teste_final_inicio == date(2026, 6, 23)
    assert params.teste_final_fim == date(2026, 11, 10)   # D2, entrada em produção em 11/11/2026
    assert params.teste_final_liberado is True
    assert params.topk == (5, 3)
    assert params.xgboost["min_child_weight"] == 50
    assert params.liberar_chance is False


def test_calendario_aceita_o_bloco_treino(tmp_path):
    dados = calendario.carregar_parametros(_escrever(tmp_path, _BLOCO_VALIDO))
    assert "treino" in dados


# --- teste final -----------------------------------------------------------------------------


def test_liberado_texto_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("liberado: false", 'liberado: "false"'))
    with pytest.raises(ErroParametrosExperimento, match="teste_final.liberado"):
        carregar_parametros_treino(caminho)


def test_inicio_sem_aspas_da_erro_com_aspas(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace('inicio: "2026-06-23"', "inicio: 2026-06-23"))
    with pytest.raises(ErroParametrosExperimento, match="aspas"):
        carregar_parametros_treino(caminho)


def test_fim_com_aspas_carrega_como_data(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("fim: null", 'fim: "2026-11-30"'))
    assert carregar_parametros_treino(caminho).teste_final_fim == date(2026, 11, 30)


def test_fim_antes_do_inicio_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("fim: null", 'fim: "2026-06-22"'))
    with pytest.raises(ErroParametrosExperimento, match="teste_final.fim"):
        carregar_parametros_treino(caminho)


def test_fim_sem_aspas_da_erro_com_aspas(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("fim: null", "fim: 2026-11-30"))
    with pytest.raises(ErroParametrosExperimento, match="aspas"):
        carregar_parametros_treino(caminho)


# --- grade, topk, embargo e chaves -----------------------------------------------------------


def test_grade_com_hiperparametro_inexistente_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("grade: {max_depth: [2, 3], min_child_weight: [50, 200]}", "grade: {gamma: [1]}"))
    with pytest.raises(ErroParametrosExperimento, match="gamma"):
        carregar_parametros_treino(caminho)


def test_topk_vazio_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("topk: [5, 3]", "topk: []"))
    with pytest.raises(ErroParametrosExperimento, match="topk"):
        carregar_parametros_treino(caminho)


def test_embargo_zero_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("embargo_pregoes: 1", "embargo_pregoes: 0"))
    with pytest.raises(ErroParametrosExperimento, match="embargo_pregoes"):
        carregar_parametros_treino(caminho)


def test_chave_a_mais_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("  motivos_qtd: 3\n", "  motivos_qtd: 3\n  extra: 1\n"))
    with pytest.raises(ErroParametrosExperimento, match="chave desconhecida"):
        carregar_parametros_treino(caminho)


# --- família em produção (treino.familia_producao) ------------------------------------------

def test_arquivo_real_produz_o_xgb():
    assert carregar_parametros_treino().familia_producao == "xgb"


def test_familia_producao_ausente_e_xgb(tmp_path):
    assert carregar_parametros_treino(_escrever(tmp_path, _BLOCO_VALIDO)).familia_producao == "xgb"


def test_familia_producao_logistica_entre_aspas(tmp_path):
    bloco = _BLOCO_VALIDO + '  familia_producao: "logistica"\n'
    assert carregar_parametros_treino(_escrever(tmp_path, bloco)).familia_producao == "logistica"


def test_familia_producao_desconhecida_da_erro(tmp_path):
    bloco = _BLOCO_VALIDO + '  familia_producao: "lgbm"\n'
    with pytest.raises(ErroParametrosExperimento, match="familia_producao"):
        carregar_parametros_treino(_escrever(tmp_path, bloco))
