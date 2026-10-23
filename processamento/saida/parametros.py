"""Parâmetros da saída (bloco `saida` de config/parametros.yaml); plano da etapa 7, fase 0.

Pastas relativas são ancoradas em `fontes.RAIZ`. Nenhuma função daqui acessa banco ou rede.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from processamento import calendario, fontes

_CHAVES = {"limite_valido_historico", "pasta", "pasta_estado", "pasta_registros", "tom_neutro"}
_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ErroParametrosSaida(Exception):
    """Bloco `saida` inválido ou ausente (a mensagem diz o que corrigir)."""


@dataclass(frozen=True)
class ParametrosSaida:
    """Parâmetros do bloco `saida` (pastas já ancoradas em `fontes.RAIZ`)."""

    limite_valido_historico: time
    pasta: Path
    pasta_estado: Path
    pasta_registros: Path
    tom_neutro: float


def _texto(valor: object, onde: str) -> str:
    """Confere texto não vazio; levanta `ErroParametrosSaida` se não bater."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErroParametrosSaida(f"{onde} deve ser um texto não vazio entre aspas (recebeu {valor!r})")
    return valor


def _hora(valor: object, onde: str) -> time:
    """Confere o horário HH:MM entre aspas; levanta `ErroParametrosSaida` se não bater."""
    if not isinstance(valor, str):
        raise ErroParametrosSaida(
            f"{onde} deve estar entre aspas no YAML (ex.: \"10:00\"; sem aspas o YAML lê o horário como número)"
        )
    if not _RE_HORA.match(valor):
        raise ErroParametrosSaida(f"{onde}: horário inválido {valor!r} (formato HH:MM)")
    return time.fromisoformat(valor)


def _tom_neutro(valor: object, onde: str) -> float:
    """Número ≥ 0 e < 1 (bool não conta); levanta `ErroParametrosSaida` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroParametrosSaida(f"{onde} deve ser um número (recebeu {valor!r})")
    if not (0 <= valor < 1):
        raise ErroParametrosSaida(f"{onde} deve ser maior ou igual a zero e menor que um (recebeu {valor!r})")
    return float(valor)


def carregar_parametros_saida(caminho: str | None = None) -> ParametrosSaida:
    """Lê o bloco `saida` (do caminho dado ou do parametros.yaml) e valida cada chave."""
    bloco = calendario.carregar_parametros(caminho).get("saida")
    if bloco is None:
        raise ErroParametrosSaida("falta o bloco saida no arquivo de parâmetros")
    if not isinstance(bloco, dict):
        raise ErroParametrosSaida("saida deve ser um mapeamento")
    presentes = {str(c) for c in bloco}
    desconhecidas = presentes - _CHAVES
    if desconhecidas:
        nomes = ", ".join(f"saida.{c}" for c in sorted(desconhecidas))
        raise ErroParametrosSaida(f"chave desconhecida no bloco saida: {nomes}")
    faltantes = _CHAVES - presentes
    if faltantes:
        nomes = ", ".join(f"saida.{c}" for c in sorted(faltantes))
        raise ErroParametrosSaida(f"faltam chaves no bloco saida: {nomes}")

    return ParametrosSaida(
        limite_valido_historico=_hora(bloco["limite_valido_historico"], "saida.limite_valido_historico"),
        pasta=fontes.RAIZ / _texto(bloco["pasta"], "saida.pasta"),
        pasta_estado=fontes.RAIZ / _texto(bloco["pasta_estado"], "saida.pasta_estado"),
        pasta_registros=fontes.RAIZ / _texto(bloco["pasta_registros"], "saida.pasta_registros"),
        tom_neutro=_tom_neutro(bloco["tom_neutro"], "saida.tom_neutro"),
    )
