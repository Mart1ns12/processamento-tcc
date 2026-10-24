"""Trava da rotina diária (plano da etapa 8, seção 5; decisão R14).

Um arquivo (`saida/estado/rotina.trava`) criado com `O_CREAT | O_EXCL`, atômico no Windows e no Linux.
Com menos de `validade_horas` de idade, outra rotina está rodando e a trava levanta `ErroTrava`. Mais
velha que isso é tida como abandonada (o PC desligou no meio): é apagada, com registro no log.
Sai sempre no `finally`: a trava que a rotina não adquiriu nunca é apagada.

Não usa o relógio do sistema: quem chama passa `agora` (relógio injetado).
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from processamento.saida.contrato import SP, data_hora_txt

log = logging.getLogger(__name__)


class ErroTrava(Exception):
    """Outra rotina está em andamento (trava recente). A mensagem diz desde quando e de qual processo."""


def _ler_trava(caminho: Path, agora: datetime) -> tuple[str, str, datetime]:
    """(criada_em, pid, instante da criação). Arquivo ilegível vale pela data de modificação."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        criada_txt = str(dados["criada_em"])
        instante = datetime.fromisoformat(criada_txt)
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=SP)
        return criada_txt, str(dados.get("pid", "desconhecido")), instante
    except (OSError, ValueError, KeyError, TypeError):
        instante = datetime.fromtimestamp(caminho.stat().st_mtime, SP)
        return data_hora_txt(instante), "desconhecido", instante


def _adquirir(caminho: Path, agora: datetime, validade: timedelta) -> None:
    """Cria a trava ou levanta `ErroTrava`. Trava abandonada é apagada e a criação tenta de novo."""
    conteudo = json.dumps({"pid": os.getpid(), "criada_em": data_hora_txt(agora)}, ensure_ascii=False)
    for _ in range(2):
        try:
            fd = os.open(str(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            criada_txt, pid, instante = _ler_trava(caminho, agora)
            if agora - instante <= validade:
                raise ErroTrava(f"outra rotina em andamento desde {criada_txt} (pid {pid})") from None
            log.warning("trava abandonada desde %s (pid %s): apagada", criada_txt, pid)
            caminho.unlink(missing_ok=True)
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
                arquivo.write(conteudo)
        except BaseException:
            caminho.unlink(missing_ok=True)
            raise
        return
    raise ErroTrava("não foi possível criar a trava da rotina")


@contextmanager
def trava(caminho: Path, agora: datetime, validade_horas: float):
    """Segura a trava durante o bloco; apaga o arquivo ao sair (inclusive por exceção)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    _adquirir(caminho, agora, timedelta(hours=validade_horas))
    try:
        yield caminho
    finally:
        caminho.unlink(missing_ok=True)
