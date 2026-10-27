"""Consulta ao /v1/saude da API publicada e registro dos tempos de resposta, para o painel de operação.

Quem consulta é o servidor do painel, nunca o navegador. A consulta é um GET público, sem chave. Só grava o
log `api_tempos.log` (uma linha JSON por medição); não acessa banco e não lê nada fora da pasta do painel.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ARQUIVO_TEMPOS = "api_tempos.log"
LIMITE_CORPO = 65536
CABECALHOS = {"Accept": "application/json", "User-Agent": "painel-processamento-tcc"}

RE_HTTPS = re.compile(r"https://[A-Za-z0-9.-]+(:\d{1,5})?/?")
RE_LOCAL = re.compile(r"http://(127\.0\.0\.1|localhost)(:\d{1,5})?/?")
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
MSG_SEM_URL = "Sem painel.api_url no parametros.yaml."
MSG_URL_INVALIDA = "painel.api_url inválida: use https://domínio, sem usuário, senha, caminho ou consulta."
MSG_PARAMS = "Parâmetros painel.api_* incompletos no parametros.yaml."


def validar_url(texto: object) -> tuple[str | None, str | None]:
    """(base sem barra final, None) ou (None, motivo). Aceita só https://host[:porta] ou http://127.0.0.1|localhost[:porta]."""
    if texto is None or (isinstance(texto, str) and not texto.strip()):
        return None, MSG_SEM_URL
    if not isinstance(texto, str):
        return None, MSG_URL_INVALIDA
    s = texto.strip()
    if not (RE_HTTPS.fullmatch(s) or RE_LOCAL.fullmatch(s)):
        return None, MSG_URL_INVALIDA
    return s.rstrip("/"), None


def _campo_texto(dados: dict, chave: str) -> str | None:
    valor = dados.get(chave)
    return valor if isinstance(valor, str) else None


def consultar_saude(url_base: str, timeout_s: float, *, abrir=None, cronometro=time.perf_counter) -> dict:
    """GET <base>/v1/saude sem chave. {"respondeu","http","ms","status","banco","ultima_publicacao","erro"}."""
    abrir = abrir or urllib.request.urlopen
    req = urllib.request.Request(url_base + "/v1/saude", method="GET", headers=dict(CABECALHOS))
    t0 = cronometro()
    try:
        try:
            with abrir(req, timeout=timeout_s) as resposta:
                http_codigo, corpo = resposta.status, resposta.read(LIMITE_CORPO)
        except urllib.error.HTTPError as e:
            http_codigo, corpo = e.code, e.read(LIMITE_CORPO)
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError) as e:
        return {"respondeu": False, "http": None, "ms": None, "status": None, "banco": None,
                "ultima_publicacao": None, "erro": type(e).__name__}
    ms = int(round((cronometro() - t0) * 1000))
    try:
        dados = json.loads(corpo.decode("utf-8"))
    except (AttributeError, ValueError):
        dados = None
    if not isinstance(dados, dict):
        dados = {}
    ultima = _campo_texto(dados, "ultima_publicacao")
    if ultima is not None and not RE_DATA.fullmatch(ultima):
        ultima = None
    return {"respondeu": True, "http": http_codigo, "ms": ms, "status": _campo_texto(dados, "status"),
            "banco": _campo_texto(dados, "banco"), "ultima_publicacao": ultima, "erro": None}


def ler_medicoes(arquivo: Path) -> list[dict]:
    """Medições do log, na ordem gravada. Arquivo ausente, ilegível ou linha quebrada não levanta exceção."""
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    medicoes = []
    for linha in texto.splitlines():
        try:
            item = json.loads(linha)
        except ValueError:
            continue
        if isinstance(item, dict):
            medicoes.append(item)
    return medicoes


def gravar_medicao(arquivo: Path, medicao: dict, manter: int) -> None:
    """Acrescenta a medição e guarda só as `manter` últimas linhas. OSError é engolido."""
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        linhas = []
    except (OSError, ValueError):
        return
    linhas.append(json.dumps(medicao, ensure_ascii=False))
    linhas = linhas[-manter:] if manter > 0 else []
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except OSError:
        return


def _ms_valido(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _segundos(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + " s"


def resumo_tempos(medicoes: list[dict], limite_s: float | None) -> dict:
    """Média e última resposta em segundos; `acima_limite` diz se a média passou do limite."""
    n = len(medicoes)
    com = [m["ms"] for m in medicoes if _ms_valido(m.get("ms"))]
    media_s = sum(com) / len(com) / 1000 if com else None
    ultimo = medicoes[-1].get("ms") if medicoes else None
    ultima_s = ultimo / 1000 if _ms_valido(ultimo) else None
    acima = media_s is not None and limite_s is not None and media_s > limite_s
    ult = _segundos(ultima_s) if ultima_s is not None else "sem resposta"
    med = _segundos(media_s) if media_s is not None else "sem medição"
    return {"n": n, "n_com_resposta": len(com), "media_s": media_s, "ultima_s": ultima_s,
            "limite_s": limite_s, "acima_limite": acima,
            "texto": f"Última: {ult} · média {med} ({len(com)} de {n} com resposta)"}


class MonitorApi:
    """Consulta a API no máximo a cada api_intervalo_s; nos outros pedidos devolve a última consulta."""

    def __init__(self, pasta_painel: Path, *, consultar=consultar_saude, monotonic=time.monotonic):
        self._pasta = pasta_painel
        self._consultar = consultar
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._ultima_t: float | None = None
        self._consulta: dict | None = None
        self._consultado_em: str | None = None

    def situacao(self, params_painel: dict, agora: datetime) -> dict:
        """{"configurada","erro_config","timeout_s","consulta","consultado_em","medicoes"}; usa cache por api_intervalo_s (threading.Lock)."""
        base, erro = validar_url(params_painel.get("api_url"))
        timeout_s = params_painel.get("api_timeout_s")
        intervalo_s = params_painel.get("api_intervalo_s")
        medicoes_max = params_painel.get("api_medicoes")
        if erro is None and any(v is None for v in (timeout_s, intervalo_s, medicoes_max)):
            erro = MSG_PARAMS
        if erro is not None:
            return {"configurada": False, "erro_config": erro, "timeout_s": timeout_s,
                    "consulta": None, "consultado_em": None, "medicoes": []}
        arquivo = self._pasta / ARQUIVO_TEMPOS
        with self._lock:
            agora_mono = self._monotonic()
            if self._ultima_t is None or agora_mono - self._ultima_t >= intervalo_s:
                consulta = self._consultar(base, timeout_s)
                self._ultima_t = agora_mono
                self._consulta = consulta
                self._consultado_em = agora.isoformat(timespec="seconds")
                gravar_medicao(arquivo, {"em": self._consultado_em, "ms": consulta.get("ms"),
                                         "http": consulta.get("http"), "ok": consulta.get("respondeu")},
                               medicoes_max)
            medicoes = ler_medicoes(arquivo)
            consulta, consultado_em = self._consulta, self._consultado_em
        return {"configurada": True, "erro_config": None, "timeout_s": timeout_s,
                "consulta": consulta, "consultado_em": consultado_em, "medicoes": medicoes}
