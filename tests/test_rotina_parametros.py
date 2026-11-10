"""Testes do bloco `rotina` e do `treino.modelo_oficial` de config/parametros.yaml (plano da etapa 8, fase 0).

Usa o `parametros.yaml` real e cópias temporárias (base real + bloco trocado em cada caso).
Nenhum teste usa banco ou rede.
"""

from datetime import time

import pytest

from fabrica_treino import params_teste
from processamento import calendario, fontes
from processamento.calendario import CAMINHO_PARAMETROS
from processamento.experimento.parametros import (
    ErroParametrosExperimento,
    carregar_parametros_treino,
)
from processamento.rotina.parametros import ErroParametrosRotina, carregar_parametros_rotina

_BLOCO_VALIDO = """rotina:
  inicio_consulta: "08:00"
  intervalo_minutos: 5
  prazo: "09:45"
  prazo_tardio: "12:00"
  etapas_conferidas: ["precos", "noticias", "enriquecimento"]
  pasta_logs: "logs"
  trava: "saida/estado/rotina.trava"
  trava_validade_horas: 6
  aviso_calendario_dias: 30
  checagem:
    acoes_minimo_fracao: 0.9
    retorno_maximo_abs: 0.30
    preco_parado_pregoes: 5
    max_tickers_por_aviso: 10
"""


def _texto_real() -> str:
    return CAMINHO_PARAMETROS.read_text(encoding="utf-8")


def _escrever_rotina(tmp_path, bloco: str) -> str:
    """Yaml temporário: o real até o bloco `rotina` (exclusive) + o bloco dado."""
    texto = _texto_real()
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(texto[: texto.index("\nrotina:\n") + 1] + bloco, encoding="utf-8")
    return str(caminho)


def _escrever_trocado(tmp_path, antigo: str, novo: str) -> str:
    """Yaml temporário: o real com um trecho trocado (o trecho precisa existir exatamente uma vez)."""
    texto = _texto_real()
    assert texto.count(antigo) == 1, f"trecho não encontrado uma vez no yaml real: {antigo!r}"
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(texto.replace(antigo, novo), encoding="utf-8")
    return str(caminho)


# --- bloco rotina ----------------------------------------------------------------------------


def test_rotina_real_carrega_os_valores_do_plano():
    params = carregar_parametros_rotina()
    assert params.inicio_consulta == time(8, 0)
    assert params.prazo == time(9, 45)
    assert params.prazo_tardio == time(12, 0)
    assert params.intervalo_minutos == 5
    assert params.etapas_conferidas == ("precos", "noticias", "enriquecimento", "juiza")
    assert params.trava == fontes.RAIZ / "saida/estado/rotina.trava"
    assert params.checagem.retorno_maximo_abs == 0.30


def test_calendario_aceita_o_bloco_rotina_e_os_feriados():
    dados = calendario.carregar_parametros()
    assert "rotina" in dados
    assert "feriados_b3" in dados
    assert dados["feriados_b3_valido_ate"] == "2027-12-31"
    assert dados["feriados_b3"]["2026-11-02"].startswith("Finados")


def test_horario_sem_aspas_erra(tmp_path):
    # O PyYAML lê 09:45 sem aspas como texto; 10:30 sem aspas vira o número 630 e precisa dar erro.
    bloco = _BLOCO_VALIDO.replace('prazo: "09:45"', "prazo: 10:30")
    with pytest.raises(ErroParametrosRotina, match="entre aspas"):
        carregar_parametros_rotina(_escrever_rotina(tmp_path, bloco))


def test_prazo_antes_do_inicio_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace('prazo: "09:45"', 'prazo: "07:00"')
    with pytest.raises(ErroParametrosRotina, match="antes de rotina.prazo"):
        carregar_parametros_rotina(_escrever_rotina(tmp_path, bloco))


def test_prazo_tardio_nulo_vira_none(tmp_path):
    bloco = _BLOCO_VALIDO.replace('prazo_tardio: "12:00"', "prazo_tardio: null")
    assert carregar_parametros_rotina(_escrever_rotina(tmp_path, bloco)).prazo_tardio is None


def test_prazo_tardio_antes_do_prazo_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace('prazo_tardio: "12:00"', 'prazo_tardio: "09:00"')
    with pytest.raises(ErroParametrosRotina, match="rotina.prazo_tardio"):
        carregar_parametros_rotina(_escrever_rotina(tmp_path, bloco))


def test_etapa_de_fim_do_dia_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace('["precos", "noticias", "enriquecimento"]', '["entrega"]')
    with pytest.raises(ErroParametrosRotina, match="etapas_conferidas"):
        carregar_parametros_rotina(_escrever_rotina(tmp_path, bloco))


def test_chave_a_mais_erra(tmp_path):
    bloco = _BLOCO_VALIDO + "  xyz: 1\n"
    with pytest.raises(ErroParametrosRotina, match="rotina.xyz"):
        carregar_parametros_rotina(_escrever_rotina(tmp_path, bloco))


def test_bloco_rotina_ausente_erra(tmp_path):
    texto = _texto_real()
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(texto[: texto.index("\nrotina:\n") + 1], encoding="utf-8")
    with pytest.raises(ErroParametrosRotina, match="falta o bloco rotina"):
        carregar_parametros_rotina(str(caminho))


# --- treino.modelo_oficial -------------------------------------------------------------------


def test_modelo_oficial_real_e_verdadeiro():
    assert carregar_parametros_treino().modelo_oficial is True   # ligado em 10/11/2026


def test_modelo_oficial_ausente_vira_falso(tmp_path):
    caminho = _escrever_trocado(tmp_path, "  modelo_oficial: true", "")
    assert carregar_parametros_treino(caminho).modelo_oficial is False


def test_modelo_oficial_texto_da_erro(tmp_path):
    caminho = _escrever_trocado(tmp_path, "  modelo_oficial: true", '  modelo_oficial: "sim"')
    with pytest.raises(ErroParametrosExperimento, match="treino.modelo_oficial"):
        carregar_parametros_treino(caminho)


def test_params_teste_continua_funcionando():
    params = params_teste()
    assert params.modelo_oficial is False
    assert params.teste_final_fim is None
