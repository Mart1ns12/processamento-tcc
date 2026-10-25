"""Fábrica das fixtures do painel: copia a árvore de dados para uma pasta temporária."""

from __future__ import annotations

import shutil
from pathlib import Path

DADOS = Path(__file__).parent / "dados" / "painel" / "raiz"


def montar_raiz(tmp_path: Path) -> Path:
    """Copia a árvore de fixtures para tmp_path/'raiz', renomeia *.log.txt -> *.log e cria um .env FALSO."""
    raiz = tmp_path / "raiz"
    shutil.copytree(DADOS, raiz)
    for f in list(raiz.rglob("*.log.txt")):
        f.rename(f.with_name(f.name[:-4]))
    (raiz / ".env").write_text("SENHA_BANCO=segredo123\nUSER_BANCO=usuario_teste\n", encoding="utf-8")
    return raiz
