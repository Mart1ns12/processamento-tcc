"""Testes do bloco `saida` de config/parametros.yaml (plano da etapa 7, fase 0).

Usa o `parametros.yaml` real e cópias temporárias (base real + bloco `saida` de cada caso).
Nenhum teste usa banco ou rede.
"""

from datetime import time

import pytest

from processamento import calendario, fontes
from processamento.calendario import CAMINHO_PARAMETROS
from processamento.saida.parametros import ErroParametrosSaida, carregar_parametros_saida

_BLOCO_VALIDO = """saida:
  limite_valido_historico: "10:00"
  pasta: "saida"
  pasta_estado: "saida/estado"
  pasta_registros: "registros/experimento"
  tom_neutro: 0.05
"""


def _base_real() -> str:
    """Texto do yaml real sem o bloco `saida` (que é trocado em cada caso)."""
    texto = CAMINHO_PARAMETROS.read_text(encoding="utf-8")
    return texto[: texto.index("\nsaida:\n") + 1]


def _escrever(tmp_path, bloco: str) -> str:
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(_base_real() + bloco, encoding="utf-8")
    return str(caminho)


def test_yaml_real_carrega():
    parametros = carregar_parametros_saida()
    assert parametros.limite_valido_historico == time(10, 0)
    assert parametros.pasta == fontes.RAIZ / "saida"
    assert parametros.pasta_registros == fontes.RAIZ / "registros" / "experimento"
    assert parametros.tom_neutro == 0.05


def test_horario_sem_aspas_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace('limite_valido_historico: "10:00"', "limite_valido_historico: 10:00")
    with pytest.raises(ErroParametrosSaida, match="aspas"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_horario_invalido_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace('"10:00"', '"25:00"')
    with pytest.raises(ErroParametrosSaida, match="horário inválido"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_chave_a_mais_erra(tmp_path):
    bloco = _BLOCO_VALIDO + "  extra: 1\n"
    with pytest.raises(ErroParametrosSaida, match="saida.extra"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_chave_faltando_erra(tmp_path):
    bloco = "\n".join(linha for linha in _BLOCO_VALIDO.splitlines() if "tom_neutro" not in linha) + "\n"
    with pytest.raises(ErroParametrosSaida, match="saida.tom_neutro"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_tom_neutro_booleano_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace("tom_neutro: 0.05", "tom_neutro: true")
    with pytest.raises(ErroParametrosSaida, match="tom_neutro"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_tom_neutro_negativo_erra(tmp_path):
    bloco = _BLOCO_VALIDO.replace("tom_neutro: 0.05", "tom_neutro: -0.1")
    with pytest.raises(ErroParametrosSaida, match="tom_neutro"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_calendario_aceita_bloco_saida(tmp_path):
    caminho = _escrever(tmp_path, _BLOCO_VALIDO)
    dados = calendario.carregar_parametros(caminho)
    assert "saida" in dados
    assert dados["saida"]["tom_neutro"] == 0.05


def test_yaml_real_nao_publica_o_top_provisorio():
    assert carregar_parametros_saida().publicar_top_provisorio is False


def test_publicar_top_ausente_e_false(tmp_path):
    assert carregar_parametros_saida(_escrever(tmp_path, _BLOCO_VALIDO)).publicar_top_provisorio is False


def test_publicar_top_true_e_lido(tmp_path):
    bloco = _BLOCO_VALIDO + "  publicar_top_provisorio: true\n"
    assert carregar_parametros_saida(_escrever(tmp_path, bloco)).publicar_top_provisorio is True


def test_publicar_top_texto_erra(tmp_path):
    bloco = _BLOCO_VALIDO + '  publicar_top_provisorio: "sim"\n'
    with pytest.raises(ErroParametrosSaida, match="saida.publicar_top_provisorio"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))


def test_chave_a_mais_continua_erro_com_publicar_presente(tmp_path):
    bloco = _BLOCO_VALIDO + "  publicar_top_provisorio: true\n  extra: 1\n"
    with pytest.raises(ErroParametrosSaida, match="chave desconhecida"):
        carregar_parametros_saida(_escrever(tmp_path, bloco))
