"""Testes da orquestração do diagnóstico (`__main__.py`), sem banco real: `ler` falso e monkeypatch."""

import pandas as pd
import pytest

from processamento import fontes
from processamento.diagnostico.__main__ import coletar, main


def _ler_sem_banco(sql, params=None):
    """Simula um banco inacessível: toda consulta falha."""
    raise RuntimeError("sem banco")


@pytest.fixture(scope="module")
def mapa():
    """Mapa real do fontes.yaml (só leitura do arquivo, sem banco)."""
    return fontes.carregar_mapa()


def test_coletar_com_banco_falho_devolve_uma_secao_de_falha(mapa):
    secoes = coletar(_ler_sem_banco, mapa)

    assert len(secoes) == 1
    assert secoes[0]["divergencias"][0]["tema"] == "falha_consulta"


def test_main_com_ler_falso_grava_relatorio_com_falha(tmp_path):
    saida = tmp_path / "d.md"

    assert main(["--saida", str(saida)], ler=_ler_sem_banco) == 0

    texto = saida.read_text(encoding="utf-8")
    assert texto.startswith("# Diagnóstico do banco da coleta (só leitura)")
    assert "falha_consulta" in texto
    assert "MySQL: desconhecida" in texto


def test_main_recusa_sessao_que_nao_e_somente_leitura(tmp_path, monkeypatch):
    saida = tmp_path / "d.md"
    monkeypatch.setattr(fontes, "criar_engine", lambda: object())
    monkeypatch.setattr(
        fontes, "executar_leitura", lambda sql, params=None, engine=None: pd.DataFrame({"ro": [0]})
    )

    assert main(["--saida", str(saida)]) == 3
    assert not saida.exists()


def test_main_com_configuracao_incompleta_devolve_2(tmp_path, monkeypatch):
    saida = tmp_path / "d.md"

    def criar_engine_sem_config():
        raise fontes.ErroConfiguracao("faltam no .env: SENHA_BANCO")

    monkeypatch.setattr(fontes, "criar_engine", criar_engine_sem_config)

    assert main(["--saida", str(saida)]) == 2
    assert not saida.exists()
