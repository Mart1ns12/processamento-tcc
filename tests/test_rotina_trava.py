"""Testes da trava da rotina (plano da etapa 8, seção 5; quatro casos). Sem banco, sem rede, sem relógio real."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from processamento import fontes
from processamento.rotina.trava import ErroTrava, trava
from processamento.saida.contrato import data_hora_txt

AGORA = datetime(2025, 10, 22, 8, 0, tzinfo=fontes.SP)
VALIDADE_HORAS = 6


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Nenhum teste da rotina abre o banco da coleta."""
    def _proibido(*args, **kwargs):
        raise AssertionError("criar_engine chamado num teste da rotina")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


def _arquivo_de_trava(caminho, criada_em: datetime, pid: int = 4242) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"pid": pid, "criada_em": data_hora_txt(criada_em)}), encoding="utf-8")


def test_caso_1_duas_travas_aninhadas_a_segunda_levanta(tmp_path):
    caminho = tmp_path / "estado" / "rotina.trava"

    with trava(caminho, AGORA, VALIDADE_HORAS):
        with pytest.raises(ErroTrava, match="outra rotina em andamento desde 2025-10-22T08:00:00-03:00"):
            with trava(caminho, AGORA, VALIDADE_HORAS):
                pass
        assert caminho.is_file()  # a trava da 1ª continua no lugar

    assert not caminho.exists()


def test_caso_2_trava_com_sete_horas_e_abandonada_e_e_adquirida(tmp_path, caplog):
    caminho = tmp_path / "rotina.trava"
    _arquivo_de_trava(caminho, AGORA - timedelta(hours=7))

    with caplog.at_level("WARNING"):
        with trava(caminho, AGORA, VALIDADE_HORAS) as adquirida:
            assert adquirida == caminho
            assert json.loads(caminho.read_text(encoding="utf-8"))["criada_em"] == data_hora_txt(AGORA)

    assert not caminho.exists()
    assert "trava abandonada" in caplog.text


def test_caso_3_trava_com_cinco_horas_levanta_e_nao_apaga(tmp_path):
    caminho = tmp_path / "rotina.trava"
    _arquivo_de_trava(caminho, AGORA - timedelta(hours=5), pid=999)

    with pytest.raises(ErroTrava, match=r"pid 999\)"):
        with trava(caminho, AGORA, VALIDADE_HORAS):
            pass
    assert caminho.is_file()  # não é nossa: quem criou continua dona


def test_caso_4_excecao_dentro_do_bloco_apaga_a_trava(tmp_path):
    caminho = tmp_path / "rotina.trava"

    with pytest.raises(RuntimeError, match="falhou no meio"):
        with trava(caminho, AGORA, VALIDADE_HORAS):
            assert caminho.is_file()
            raise RuntimeError("falhou no meio")

    assert not caminho.exists()
