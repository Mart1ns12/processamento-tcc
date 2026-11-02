"""Testes do registro de tentativas do protocolo (processamento/experimento/protocolo_registro.py).
Tudo em tmp_path: nenhum teste toca docs/ real. Gabaritos do plano da Parte C, fase 1.4."""

from dataclasses import replace

import pytest

from fabrica_treino import params_teste
from processamento.experimento import protocolo_registro as registro
from processamento.experimento.protocolo import LIMITES
from processamento.experimento.protocolo_registro import ErroRegistro


def _doc(pasta, secao3="Critério 1: ganho maior que +0,005.", secao6="Busca: texto da seção 6."):
    doc = pasta / "protocolo.md"
    texto = (
        "# Protocolo\n\n## 1. Escopo\ntexto 1\n\n## 2. Blocos\ntexto 2\n\n"
        f"## 3. Critérios\n{secao3}\n\n## 4. Ordem\ntexto 4\n\n## 5. Regras\ntexto 5\n\n## 6. Busca\n{secao6}\n"
    )
    doc.write_bytes(texto.encode("utf-8"))   # bytes: fim de linha LF fixo, independe do sistema
    return doc


def test_sem_arquivo_registro_vazio(tmp_path):
    caminho = tmp_path / "tentativas.jsonl"
    assert registro.ler(caminho) == []
    assert registro.proxima_rodada([], "protocolo") == 1


def test_dois_acrescimos_encadeados(tmp_path):
    caminho = tmp_path / "tentativas.jsonl"
    primeiro = registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "inicio", "rodada": 1})
    bytes_1 = caminho.read_bytes()
    segundo = registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "falhou", "rodada": 1})
    assert primeiro["seq"] == 1 and segundo["seq"] == 2
    assert primeiro["sha_anterior"] == ""
    linha_1 = bytes_1.decode("utf-8").rstrip("\n")
    assert segundo["sha_anterior"] == registro._sha_texto(linha_1)
    assert caminho.read_bytes().startswith(bytes_1)
    eventos = registro.ler(caminho)
    assert [e["seq"] for e in eventos] == [1, 2]


def test_editar_linha_quebra_a_cadeia(tmp_path):
    caminho = tmp_path / "tentativas.jsonl"
    registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "inicio", "rodada": 1})
    registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "falhou", "rodada": 1})
    texto = caminho.read_text(encoding="utf-8")
    caminho.write_text(texto.replace('"rodada": 1', '"rodada": 9', 1), encoding="utf-8")
    with pytest.raises(ErroRegistro):
        registro.ler(caminho)


def test_apagar_primeira_linha_quebra_a_cadeia(tmp_path):
    caminho = tmp_path / "tentativas.jsonl"
    registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "inicio", "rodada": 1})
    registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "falhou", "rodada": 1})
    segunda = caminho.read_text(encoding="utf-8").split("\n")[1]
    caminho.write_text(segunda + "\n", encoding="utf-8")
    with pytest.raises(ErroRegistro):
        registro.ler(caminho)


def test_proxima_rodada_conta_inicio_sem_fim(tmp_path):
    caminho = tmp_path / "tentativas.jsonl"
    registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "inicio", "rodada": 1})
    registro.acrescentar(caminho, {"tipo": "protocolo", "evento": "falhou", "rodada": 1})
    registro.acrescentar(caminho, {"tipo": "busca", "evento": "inicio", "rodada": 1})
    eventos = registro.ler(caminho)
    assert registro.proxima_rodada(eventos, "protocolo") == 2
    assert registro.proxima_rodada(eventos, "busca") == 2


def test_primeira_rodada_completa_e_repeticoes(tmp_path):
    assinatura = {"sha256_dataset": "abc", "semente": 1}
    eventos = [
        {"tipo": "protocolo", "evento": "inicio", "rodada": 1},
        {"tipo": "protocolo", "evento": "fim", "rodada": 1, "assinatura": assinatura},
        {"tipo": "protocolo", "evento": "inicio", "rodada": 2},
        {"tipo": "protocolo", "evento": "fim", "rodada": 2, "assinatura": assinatura},
    ]
    assert registro.primeira_rodada_completa(eventos, "protocolo")["rodada"] == 1
    assert registro.primeira_rodada_completa(eventos, "busca") is None
    assert len(registro.rodadas_iguais(eventos, "protocolo", assinatura)) == 2
    assert registro.rodadas_iguais(eventos, "protocolo", {"sha256_dataset": "x"}) == []


def test_sha_regras_ignora_fim_de_linha_e_secao_6(tmp_path):
    base = registro.sha_regras(_doc(tmp_path), LIMITES)
    pasta_crlf = tmp_path / "crlf"
    pasta_crlf.mkdir()
    doc_crlf = _doc(pasta_crlf)
    doc_crlf.write_bytes(doc_crlf.read_bytes().replace(b"\n", b"\r\n"))
    assert registro.sha_regras(doc_crlf, LIMITES) == base
    pasta_6 = tmp_path / "secao6"
    pasta_6.mkdir()
    assert registro.sha_regras(_doc(pasta_6, secao6="outro texto da seção 6"), LIMITES) == base


def test_sha_regras_muda_com_a_secao_3_e_com_os_limites(tmp_path):
    base = registro.sha_regras(_doc(tmp_path), LIMITES)
    pasta = tmp_path / "trocada"
    pasta.mkdir()
    assert registro.sha_regras(_doc(pasta, secao3="Critério 1: ganho maior que +0,006."), LIMITES) != base
    assert registro.sha_regras(_doc(tmp_path), replace(LIMITES, k_top=3)) != base


def test_sha_regras_sem_secao_3_levanta(tmp_path):
    doc = tmp_path / "sem.md"
    doc.write_text("# Protocolo\n\n## 1. Escopo\nsó isto\n", encoding="utf-8")
    with pytest.raises(ErroRegistro):
        registro.sha_regras(doc, LIMITES)


def test_sha_parametros_estavel_e_sensivel_a_semente():
    params = params_teste()
    assert registro.sha_parametros(params) == registro.sha_parametros(params_teste())
    assert registro.sha_parametros(params) != registro.sha_parametros(replace(params, semente=1))
