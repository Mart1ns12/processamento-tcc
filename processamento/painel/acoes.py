"""Ações do painel: lista fixa, comandos do projeto, ambiente do filho e execução (uma por vez).

Não lê o banco nem o `.env`: só monta os comandos já existentes e roda cada um em subprocesso,
gravando a saída num log que a tela pode acompanhar.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from processamento.calendario import SP


@dataclass(frozen=True)
class Acao:
    id: str
    titulo: str
    usa_banco: bool
    pode_parar: bool


ACOES: dict[str, Acao] = {
    "dia": Acao("dia", "Rodar o dia completo", True, False),
    "rotina": Acao("rotina", "Rodar a rotina do dia", True, False),
    "carga": Acao("carga", "Gerar a carga completa", True, False),
    "diagnostico": Acao("diagnostico", "Rodar o diagnóstico do banco", True, False),
    "wordpress": Acao("wordpress", "Validar a wordpress", True, False),
    "testes": Acao("testes", "Rodar os testes (pytest)", False, True),
}

SIGNIFICADOS: dict[str, dict[int, str]] = {
    "dia": {
        0: "publicado: completo, ou só a execução quando a rotina falhou (veja o log)",
        1: "publicador recusou a publicação (motivo no log)",
        2: "configuração do painel: pasta ou Python do projeto da API não encontrados",
        3: "a rotina não gerou saída nova (sem pregão, configuração, banco ou trava): nada publicado",
        4: "carga completa falhou: nada publicado",
        5: "publicador: configuração ou banco da API",
        6: "rotina falhou, mas há uma carga completa antiga deste dia: publicador não rodado",
    },
    "rotina": {
        0: "ok, parcial ou dia sem pregão (veja o log)",
        2: "configuração (banco, parâmetros ou calendário)",
        3: "conexão com o banco ou sessão que não é só leitura",
        4: "falhou: coleta não ficou pronta ou nenhum pacote gerado",
        5: "outra rotina em andamento (trava)",
    },
    "carga": {
        0: "ok ou parcial",
        2: "configuração ou pasta recusada",
        3: "conexão com o banco",
        4: "falhou",
    },
    "diagnostico": {
        0: "relatório gerado",
        2: "configuração do banco incompleta",
        3: "sessão não é só leitura ou falha de conexão",
    },
    "wordpress": {
        0: "relatório gerado",
        1: "falha ao ler as tabelas",
        2: "configuração do banco incompleta",
        3: "sessão não é só leitura ou falha de conexão",
    },
    "testes": {
        0: "todos os testes passaram",
        1: "há testes falhando",
        2: "interrompido",
        3: "erro interno do pytest",
        4: "uso incorreto do pytest",
        5: "nenhum teste encontrado",
    },
}


def significado(acao_id: str, codigo: int | None, parado: bool) -> str | None:
    """Explica o código de saída de uma ação (ou diz que foi parada pelo painel)."""
    if parado:
        return "parado pelo painel"
    if codigo is None:
        return None
    return SIGNIFICADOS[acao_id].get(codigo, f"código {codigo}")


def montar_comando(acao_id: str, *, d_rotina: date | None, d_carga: date | None) -> list[str] | None:
    """Monta o argv da ação (None quando falta a data). Levanta KeyError para id desconhecido."""
    if acao_id not in ACOES:
        raise KeyError(acao_id)
    if acao_id == "dia":
        return None if d_rotina is None else [sys.executable, "-m", "processamento.painel.dia", "--data", d_rotina.isoformat()]
    if acao_id == "rotina":
        if d_rotina is None:
            return None
        return [sys.executable, "-m", "processamento.rotina", "--data", d_rotina.isoformat(), "--sem-esperar"]
    if acao_id == "carga":
        if d_carga is None:
            return None
        return [sys.executable, "-m", "processamento.saida", "--data", d_carga.isoformat(), "--completo"]
    if acao_id == "diagnostico":
        return [sys.executable, "-m", "processamento.diagnostico"]
    if acao_id == "wordpress":
        return [sys.executable, "-m", "processamento.diagnostico.wordpress"]
    return [sys.executable, "-m", "pytest", "-q"]


def comando_texto(argv: list[str]) -> str:
    """Texto curto do comando para o log e a tela (sem o caminho do Python)."""
    return " ".join(["python", *argv[1:]])


def ambiente_filho(acao_id: str, base: Mapping[str, str]) -> dict[str, str]:
    """Ambiente do subprocesso: saída em utf-8 e sem buffer; os testes não herdam a permissão de banco."""
    env = dict(base)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    if acao_id == "testes":
        env.pop("PROC_TESTES_COM_BANCO", None)
    return env


def _argv_valido(argv: object) -> bool:
    return (
        isinstance(argv, list)
        and len(argv) > 0
        and all(isinstance(a, str) for a in argv)
        and argv[0] == sys.executable
    )


class Executor:
    """Roda uma ação por vez em subprocesso, guarda as últimas linhas e grava o log em disco."""

    def __init__(
        self,
        raiz: Path,
        pasta_logs_painel: Path,
        *,
        relogio: Callable[[], datetime] | None = None,
        ambiente_base: Mapping[str, str] | None = None,
        max_linhas: int = 5000,
        manter_logs: int = 20,
    ) -> None:
        self._raiz = raiz
        self._pasta = pasta_logs_painel
        self._relogio = relogio or (lambda: datetime.now(SP))
        self._ambiente_base = ambiente_base
        self._manter_logs = manter_logs
        self._lock = threading.Lock()
        self._fim_evento = threading.Event()
        self._linhas: deque[str] = deque(maxlen=max_linhas)
        self._total = 0
        self._acao: Acao | None = None
        self._proc: subprocess.Popen | None = None
        self._rodando = False
        self._parado = False
        self._inicio: datetime | None = None
        self._fim: datetime | None = None
        self._codigo: int | None = None
        self._significado: str | None = None
        self._arquivo: Path | None = None

    def iniciar(self, acao_id: str, argv: list[str]) -> tuple[bool, str]:
        """Inicia a ação em subprocesso. Devolve (ok, mensagem)."""
        if acao_id not in ACOES:
            return False, "ação desconhecida"
        if not _argv_valido(argv):
            return False, "comando inválido"
        acao = ACOES[acao_id]
        with self._lock:
            if self._rodando and self._acao is not None:
                return False, f"outra ação em andamento: {self._acao.titulo}"
            inicio = self._relogio()
            ambiente = self._ambiente_base if self._ambiente_base is not None else os.environ
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=str(self._raiz),
                    env=ambiente_filho(acao_id, ambiente),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except OSError as e:
                return False, f"não foi possível iniciar ({type(e).__name__})"
            arquivo = self._novo_arquivo_log(acao_id, inicio)
            cabecalho = (
                f"# painel: acao={acao_id} inicio={inicio.isoformat(timespec='seconds')} "
                f"comando={comando_texto(argv)}"
            )
            arquivo.write_text(cabecalho + "\n", encoding="utf-8")
            self._acao = acao
            self._inicio = inicio
            self._fim = None
            self._codigo = None
            self._significado = None
            self._parado = False
            self._arquivo = arquivo
            self._linhas.clear()
            self._total = 0
            self._proc = proc
            self._rodando = True
            self._fim_evento.clear()
        threading.Thread(target=self._ler, args=(acao_id, proc, arquivo), daemon=True).start()
        return True, f"iniciado: {acao.titulo}"

    def parar(self) -> tuple[bool, str]:
        """Encerra a ação em andamento, se ela puder ser parada."""
        with self._lock:
            if not self._rodando or self._acao is None or self._proc is None:
                return False, "nada rodando"
            if not self._acao.pode_parar:
                return False, "esta ação não pode ser parada"
            self._parado = True
            try:
                self._proc.terminate()
            except OSError:
                pass
            return True, "parando"

    def rodando(self) -> bool:
        with self._lock:
            return self._rodando

    def estado(self, desde: int | None = None) -> dict[str, object]:
        """Situação atual. Com `desde`, devolve só as linhas de índice >= desde que ainda estão no buffer."""
        with self._lock:
            if self._acao is None:
                return {
                    "id": None,
                    "titulo": None,
                    "rodando": False,
                    "inicio": None,
                    "fim": None,
                    "codigo": None,
                    "significado": None,
                    "pode_parar": False,
                    "arquivo_log": None,
                    "linhas": [],
                    "proximo": 0,
                    "total_linhas": 0,
                }
            primeiro = self._total - len(self._linhas)
            if desde is None:
                linhas: list[str] = []
            else:
                indice = max(desde, primeiro) - primeiro
                linhas = list(self._linhas)[indice:]
            return {
                "id": self._acao.id,
                "titulo": self._acao.titulo,
                "rodando": self._rodando,
                "inicio": self._inicio.isoformat(timespec="seconds") if self._inicio else None,
                "fim": self._fim.isoformat(timespec="seconds") if self._fim else None,
                "codigo": self._codigo,
                "significado": self._significado,
                "pode_parar": self._acao.pode_parar,
                "arquivo_log": self._relativo(self._arquivo) if self._arquivo else None,
                "linhas": linhas,
                "proximo": self._total,
                "total_linhas": self._total,
            }

    def esperar(self, timeout: float) -> bool:
        """Espera a ação atual terminar (para testes). True se terminou dentro do prazo."""
        return self._fim_evento.wait(timeout)

    def _relativo(self, arquivo: Path) -> str:
        try:
            return arquivo.relative_to(self._raiz).as_posix()
        except ValueError:
            return arquivo.name

    def _novo_arquivo_log(self, acao_id: str, inicio: datetime) -> Path:
        self._pasta.mkdir(parents=True, exist_ok=True)
        base = f"{acao_id}-{inicio:%Y-%m-%d_%H%M%S}"
        arquivo = self._pasta / f"{base}.log"
        n = 2
        while arquivo.exists():
            arquivo = self._pasta / f"{base}_{n}.log"
            n += 1
        return arquivo

    def _ler(self, acao_id: str, proc: subprocess.Popen, arquivo: Path) -> None:
        """Thread de leitura: copia a saída para o buffer e o log; no fim, registra o resultado."""
        try:
            with arquivo.open("a", encoding="utf-8") as log:
                for linha in proc.stdout:
                    linha = linha.rstrip("\r\n")
                    with self._lock:
                        self._linhas.append(linha)
                        self._total += 1
                    log.write(linha + "\n")
                    log.flush()
                codigo = proc.wait()
                fim = self._relogio()
                with self._lock:
                    parado = self._parado
                    self._codigo = codigo
                    self._fim = fim
                    self._significado = significado(acao_id, codigo, parado)
                rodape = f"# painel: fim={fim.isoformat(timespec='seconds')} codigo={codigo}"
                if parado:
                    rodape += " parado=sim"
                log.write(rodape + "\n")
            self._apagar_antigos(acao_id)
        finally:
            with self._lock:
                self._rodando = False
                self._proc = None
            self._fim_evento.set()

    def _apagar_antigos(self, acao_id: str) -> None:
        arquivos = sorted(self._pasta.glob(f"{acao_id}-*.log"))
        for antigo in arquivos[: max(0, len(arquivos) - self._manter_logs)]:
            try:
                antigo.unlink()
            except OSError:
                pass
