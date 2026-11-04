"""Testes de processamento/painel/api.py: consulta ao /v1/saude e tempos. Sem rede (HTTP injetado) e sem banco."""

from __future__ import annotations

import io
import socket
import urllib.error
from datetime import datetime
from pathlib import Path

import pytest

from fabrica_painel import montar_raiz
from processamento.painel import api
from processamento.painel.api import (
    MonitorApi,
    consultar_saude,
    gravar_medicao,
    ler_medicoes,
    resumo_tempos,
    validar_url,
)

CORPO_OK = b'{"status":"ok","banco":"ok","ultima_publicacao":"2026-10-27"}'
AGORA = datetime(2026, 10, 27, 10, 0, 0)


@pytest.fixture(autouse=True)
def rede_bloqueada(monkeypatch):
    def sem_rede(*args, **kwargs):
        raise OSError("rede bloqueada no teste")

    monkeypatch.setattr(socket.socket, "connect", sem_rede)


class Resposta:
    """Imita o objeto de contexto devolvido pelo urlopen."""

    def __init__(self, status: int, corpo: bytes):
        self.status = status
        self._corpo = corpo

    def read(self, n: int = -1) -> bytes:
        return self._corpo[:n] if n >= 0 else self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def test_consulta_ok_monta_request_e_mede_tempo():
    enviados = []

    def falso(req, timeout=None):
        enviados.append((req, timeout))
        return Resposta(200, CORPO_OK)

    resultado = consultar_saude("https://api.exemplo.invalid", 5, abrir=falso,
                                cronometro=iter([10.0, 10.84]).__next__)
    assert resultado == {"respondeu": True, "http": 200, "ms": 840, "status": "ok", "banco": "ok",
                         "ultima_publicacao": "2026-10-27", "erro": None}
    req, timeout = enviados[0]
    assert req.get_method() == "GET"
    assert req.full_url == "https://api.exemplo.invalid/v1/saude"
    assert req.data is None
    assert timeout == 5
    assert {k.lower() for k, _ in req.header_items()} == {"accept", "user-agent"}


def test_http_de_erro_ainda_conta_como_resposta():
    def falso(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, "x", {},
                                     io.BytesIO(b'{"status":"erro","banco":"fora"}'))

    resultado = consultar_saude("https://api.exemplo.invalid", 5, abrir=falso,
                                cronometro=iter([1.0, 1.5]).__next__)
    assert resultado["respondeu"] is True
    assert resultado["http"] == 503
    assert resultado["status"] == "erro"
    assert resultado["banco"] == "fora"
    assert resultado["erro"] is None


def test_json_invalido_zera_campos_mas_mantem_http():
    def falso(req, timeout=None):
        return Resposta(200, b"isto nao e json")

    resultado = consultar_saude("https://api.exemplo.invalid", 5, abrir=falso,
                                cronometro=iter([0.0, 0.2]).__next__)
    assert resultado["respondeu"] is True
    assert resultado["http"] == 200
    assert resultado["status"] is None
    assert resultado["banco"] is None
    assert resultado["ultima_publicacao"] is None


def test_falha_de_rede_devolve_nome_do_erro():
    def falso(req, timeout=None):
        raise urllib.error.URLError("x")

    resultado = consultar_saude("https://api.exemplo.invalid", 5, abrir=falso)
    assert resultado == {"respondeu": False, "http": None, "ms": None, "status": None, "banco": None,
                         "ultima_publicacao": None, "erro": "URLError"}


def test_validar_url():
    assert validar_url("https://api-processamento-tcc-production.up.railway.app/") == (
        "https://api-processamento-tcc-production.up.railway.app", None)
    assert validar_url("http://127.0.0.1:8000") == ("http://127.0.0.1:8000", None)
    for ruim in ["http://exemplo.com", "https://u:s@x.com", "https://x.com/v1", "https://x.com?a=1"]:
        base, motivo = validar_url(ruim)
        assert base is None
        assert motivo == api.MSG_URL_INVALIDA
    assert validar_url(None) == (None, "Sem painel.api_url no parametros.yaml.")
    assert validar_url("https://u:s@x.com")[1] == (
        "painel.api_url inválida: use https://domínio, sem usuário, senha, caminho ou consulta.")


def test_monitor_consulta_no_intervalo_e_grava_log_limitado(tmp_path):
    raiz = montar_raiz(tmp_path)
    pasta = raiz / "logs" / "painel"
    tempo = [0.0]
    chamadas = []

    def falso_contador(base, timeout):
        chamadas.append(base)
        return {"respondeu": True, "http": 200, "ms": 500, "status": "ok", "banco": "ok",
                "ultima_publicacao": None, "erro": None}

    monitor = MonitorApi(pasta, consultar=falso_contador, monotonic=lambda: tempo[0])
    params = {"api_url": "https://api.exemplo.invalid", "api_timeout_s": 5,
              "api_intervalo_s": 60, "api_medicoes": 3}

    tempo[0] = 0.0
    monitor.situacao(params, AGORA)
    tempo[0] = 30.0
    monitor.situacao(params, AGORA)
    assert len(chamadas) == 1

    tempo[0] = 61.0
    monitor.situacao(params, AGORA)
    assert len(chamadas) == 2

    for _ in range(3):
        tempo[0] += 61.0
        situacao = monitor.situacao(params, AGORA)
    assert len(chamadas) == 5
    assert situacao["configurada"] is True
    assert situacao["consultado_em"] == "2026-10-27T10:00:00"
    assert len(situacao["medicoes"]) == 3
    assert len((pasta / "api_tempos.log").read_text(encoding="utf-8").splitlines()) == 3


def test_monitor_forcar_consulta_mesmo_dentro_do_intervalo(tmp_path):
    chamadas = []

    def falso(base, timeout):
        chamadas.append(base)
        return {"respondeu": True, "http": 200, "ms": 500, "status": "ok", "banco": "ok",
                "ultima_publicacao": None, "erro": None}

    monitor = MonitorApi(tmp_path, consultar=falso, monotonic=lambda: 0.0)
    params = {"api_url": "https://api.exemplo.invalid", "api_timeout_s": 5,
              "api_intervalo_s": 60, "api_medicoes": 10}
    monitor.situacao(params, AGORA)
    monitor.situacao(params, AGORA)
    assert len(chamadas) == 1

    situacao = monitor.situacao(params, AGORA, forcar=True)
    assert len(chamadas) == 2
    assert len(situacao["medicoes"]) == 2


def test_monitor_sem_url_ou_parametro_nao_consulta(tmp_path):
    chamadas = []
    monitor = MonitorApi(tmp_path, consultar=lambda b, t: chamadas.append(b), monotonic=lambda: 0.0)

    sem_url = monitor.situacao({"api_timeout_s": 5, "api_intervalo_s": 60, "api_medicoes": 3}, AGORA)
    assert sem_url["configurada"] is False
    assert sem_url["erro_config"] == "Sem painel.api_url no parametros.yaml."
    assert sem_url["consulta"] is None

    incompleto = monitor.situacao({"api_url": "https://api.exemplo.invalid", "api_timeout_s": None,
                                   "api_intervalo_s": 60, "api_medicoes": 3}, AGORA)
    assert incompleto["configurada"] is False
    assert incompleto["erro_config"] == "Parâmetros painel.api_* incompletos no parametros.yaml."
    assert chamadas == []


def test_gravar_medicao_engole_oserror(tmp_path):
    bloqueio = tmp_path / "arquivo_comum"
    bloqueio.write_text("x", encoding="utf-8")
    gravar_medicao(bloqueio / "api_tempos.log", {"ms": 1}, 3)


def test_ler_medicoes_ignora_ausente_e_linha_quebrada(tmp_path):
    assert ler_medicoes(tmp_path / "nao_existe.log") == []
    arquivo = tmp_path / "api_tempos.log"
    arquivo.write_text('{"ms": 800}\nquebrada{\n\n{"ms": null}\n', encoding="utf-8")
    assert ler_medicoes(arquivo) == [{"ms": 800}, {"ms": None}]


def test_resumo_tempos():
    medicoes = [{"ms": 800}, {"ms": 1000}, {"ms": None}, {"ms": 900}]
    resumo = resumo_tempos(medicoes, 2.0)
    assert resumo["media_s"] == 0.9
    assert resumo["ultima_s"] == 0.9
    assert resumo["n"] == 4
    assert resumo["n_com_resposta"] == 3
    assert resumo["acima_limite"] is False
    assert resumo["texto"] == "Última: 0,90 s · média 0,90 s (3 de 4 com resposta)"
    assert resumo_tempos(medicoes, 0.5)["acima_limite"] is True


def test_resumo_tempos_vazio():
    resumo = resumo_tempos([], None)
    assert resumo["media_s"] is None
    assert resumo["ultima_s"] is None
    assert resumo["acima_limite"] is False
    assert resumo["texto"] == "Última: sem resposta · média sem medição (0 de 0 com resposta)"


def test_fonte_do_api_sem_termos_proibidos():
    texto = Path(api.__file__).read_text(encoding="utf-8")
    proibidos = ["X-" + "API-Key", "Autho" + "rization", "." + "env", "load_" + "dotenv",
                 "envi" + "ron", "shell" + "=True"]
    for termo in proibidos:
        assert termo not in texto
