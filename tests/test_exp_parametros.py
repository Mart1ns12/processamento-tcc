"""Testes do bloco `experimento` de config/parametros.yaml (plano da etapa 5, fase 1)."""

from datetime import date

import pytest

from processamento import calendario
from processamento.experimento.parametros import (
    ErroParametrosExperimento,
    carregar_parametros_experimento,
    mascara_sem_coleta,
)

_CABECALHO_YAML = """fuso: "America/Sao_Paulo"
corte_noite: "08:00"
horarios_b3_valido_ate: "2027-03-12"
horarios_b3:
  - {a_partir_de: "2026-03-09", abertura: "10:00", fechamento: "17:00"}
"""

_BLOCO_VALIDO = """experimento:
  retornos: {ret_1d: 1, ret_5d: 5, ret_20d: 20}
  exposicao_pregoes: 120
  exposicao_minimo: 60
  extremos_pregoes: 252
  extremos_minimo: 120
  mudanca_tom_pregoes: 30
  mudanca_tom_minimo: 5
  sem_horario_na_noite: true
  inicio_janela: "manha"
  deduplicar_titulo: true
  deduplicar_entre_origens: true
  janela_dias_entre_origens: 1
  titulo_palavras_min_entre_origens: 5
  periodos_sem_coleta: []
  noticias_mes_fracao_minima: 0.25
  principais:
    origens: ["cvm_ipe"]
    tipos_conteudo: ["reportagem"]
    papeis: ["protagonista", "citada_com_fato"]
"""


def _escrever(tmp_path, bloco: str) -> str:
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(_CABECALHO_YAML + bloco, encoding="utf-8")
    return str(caminho)


# --- arquivo real ----------------------------------------------------------------------------


def test_arquivo_real_carrega_os_valores_do_plano():
    params = carregar_parametros_experimento()
    assert params.retornos == {"ret_1d": 1, "ret_5d": 5, "ret_20d": 20}
    assert (params.exposicao_pregoes, params.exposicao_minimo) == (120, 60)
    assert (params.extremos_pregoes, params.extremos_minimo) == (252, 120)
    assert (params.mudanca_tom_pregoes, params.mudanca_tom_minimo) == (30, 5)
    assert params.sem_horario_na_noite is True
    assert params.inicio_janela == "manha"
    assert params.deduplicar_titulo is True
    assert params.deduplicar_entre_origens is True
    assert (params.janela_dias_entre_origens, params.titulo_palavras_min_entre_origens) == (1, 5)
    assert params.origens_principais == ("cvm_ipe",)
    assert params.tipos_principais == ("reportagem",)
    assert params.papeis_principais == ("protagonista", "citada_com_fato")
    assert params.periodos_sem_coleta == ((date(2025, 1, 1), date(2025, 7, 31)),)


def test_calendario_continua_carregando_com_o_bloco_experimento():
    dados = calendario.carregar_parametros()
    assert "experimento" in dados
    assert "fase1" in dados


# --- erros -----------------------------------------------------------------------------------


def test_sem_o_bloco_experimento_da_erro(tmp_path):
    caminho = _escrever(tmp_path, "")
    with pytest.raises(ErroParametrosExperimento, match="falta o bloco experimento"):
        carregar_parametros_experimento(caminho)


def test_chave_desconhecida_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("  deduplicar_titulo: true\n", "  deduplicar_titulo: true\n  extra: 1\n"))
    with pytest.raises(ErroParametrosExperimento, match="chave desconhecida"):
        carregar_parametros_experimento(caminho)


def test_deduplicar_entre_origens_precisa_ser_booleano(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("deduplicar_entre_origens: true", "deduplicar_entre_origens: 1"))
    with pytest.raises(ErroParametrosExperimento, match="deduplicar_entre_origens"):
        carregar_parametros_experimento(caminho)


def test_janela_entre_origens_nao_pode_ser_negativa(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("janela_dias_entre_origens: 1", "janela_dias_entre_origens: -1"))
    with pytest.raises(ErroParametrosExperimento, match="janela_dias_entre_origens"):
        carregar_parametros_experimento(caminho)


def test_exposicao_minimo_maior_que_a_janela_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("exposicao_minimo: 60", "exposicao_minimo: 130"))
    with pytest.raises(ErroParametrosExperimento, match="exposicao_minimo"):
        carregar_parametros_experimento(caminho)


def test_mudanca_tom_minimo_booleano_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("mudanca_tom_minimo: 5", "mudanca_tom_minimo: true"))
    with pytest.raises(ErroParametrosExperimento, match="mudanca_tom_minimo"):
        carregar_parametros_experimento(caminho)


def test_inicio_janela_invalido_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace('inicio_janela: "manha"', 'inicio_janela: "tarde"'))
    with pytest.raises(ErroParametrosExperimento, match="inicio_janela"):
        carregar_parametros_experimento(caminho)


def test_inicio_janela_fechamento_carrega(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace('inicio_janela: "manha"', 'inicio_janela: "fechamento"'))
    assert carregar_parametros_experimento(caminho).inicio_janela == "fechamento"


def test_booleano_com_texto_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("sem_horario_na_noite: true", 'sem_horario_na_noite: "sim"'))
    with pytest.raises(ErroParametrosExperimento, match="sem_horario_na_noite"):
        carregar_parametros_experimento(caminho)


def test_papeis_vazio_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace('papeis: ["protagonista", "citada_com_fato"]', "papeis: []"))
    with pytest.raises(ErroParametrosExperimento, match="papeis"):
        carregar_parametros_experimento(caminho)


# --- períodos sem coleta ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor, trecho",
    [
        ('{inicio: "2025-01-01"}', "periodos_sem_coleta"),
        ('[{inicio: 2025-01-01, fim: "2025-07-31"}]', "entre aspas"),
        ('[{inicio: "2025-08-01", fim: "2025-07-31"}]', "depois do fim"),
        ('[{inicio: "2025-01-01"}]', "faltam chaves"),
    ],
)
def test_periodos_sem_coleta_invalidos(tmp_path, valor, trecho):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("periodos_sem_coleta: []", f"periodos_sem_coleta: {valor}"))
    with pytest.raises(ErroParametrosExperimento, match=trecho):
        carregar_parametros_experimento(caminho)


def test_periodos_sem_coleta_sem_a_chave_da_erro(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO.replace("  periodos_sem_coleta: []\n", ""))
    with pytest.raises(ErroParametrosExperimento, match="faltam chaves"):
        carregar_parametros_experimento(caminho)


def test_mascara_sem_coleta_limites_inclusivos():
    periodos = ((date(2025, 1, 1), date(2025, 7, 31)),)
    datas = ["2024-12-30", "2025-01-02", "2025-07-31", "2025-08-01"]
    assert mascara_sem_coleta(datas, periodos).tolist() == [False, True, True, False]
    assert mascara_sem_coleta(datas, ()).tolist() == [False] * 4
