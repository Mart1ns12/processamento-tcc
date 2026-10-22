"""Exclusões decididas manualmente: tickers fora do universo e CNPJs sem balanço.

Lê `config/exclusoes.yaml` (seção 3.4 da especificação). As classes extintas não ficam aqui:
são calculadas pelo `other_codes` da B3 (ver `tickers.py`).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CAMINHO_EXCLUSOES = Path(__file__).resolve().parent / "config" / "exclusoes.yaml"
_CHAVES_DE_TOPO = {"tickers_excluidos", "cnpjs_sem_balanco"}
_RE_TICKER = re.compile(r"^[A-Z0-9]{4}[0-9]{1,2}$")
_RE_CNPJ = re.compile(r"^[0-9]{14}$")


class ErroExclusoes(Exception):
    """Arquivo de exclusões inválido (a mensagem diz o que corrigir)."""


@dataclass(frozen=True)
class Exclusoes:
    """Exclusões carregadas: ticker -> motivo e CNPJ -> motivo."""

    tickers_excluidos: dict[str, str] = field(default_factory=dict)
    cnpjs_sem_balanco: dict[str, str] = field(default_factory=dict)


def _validar_ticker(chave: object) -> None:
    """Confere o formato do ticker (ex.: 'PETR4'); levanta `ErroExclusoes` se não bater."""
    if not isinstance(chave, str) or not _RE_TICKER.match(chave):
        raise ErroExclusoes(
            f"ticker inválido em tickers_excluidos: {chave!r} "
            "(4 letras/números maiúsculos + 1 ou 2 dígitos, ex.: PETR4)"
        )


def _validar_cnpj(chave: object) -> None:
    """Confere o CNPJ (14 dígitos entre aspas); levanta `ErroExclusoes` se não bater."""
    if not isinstance(chave, str):
        raise ErroExclusoes(
            f"CNPJ {chave} em cnpjs_sem_balanco deve estar entre aspas no YAML "
            "(sem aspas, o número perde os zeros à esquerda)"
        )
    if not _RE_CNPJ.match(chave):
        raise ErroExclusoes(f"CNPJ inválido em cnpjs_sem_balanco: {chave!r} (14 dígitos)")


def _validar_secao(nome: str, secao: object, validar_chave: Callable[[object], None]) -> dict[str, str]:
    """Valida uma seção do arquivo (chaves e motivos) e devolve o dicionário chave -> motivo."""
    if secao is None:
        return {}
    if not isinstance(secao, dict):
        raise ErroExclusoes(f"a seção {nome} deve ser um mapeamento")
    resultado = {}
    for chave, motivo in secao.items():
        validar_chave(chave)
        if not isinstance(motivo, str) or not motivo.strip():
            raise ErroExclusoes(f"{nome}: o motivo de {chave} deve ser um texto não vazio")
        resultado[chave] = motivo
    return resultado


@functools.lru_cache
def carregar_exclusoes(caminho: str | None = None) -> Exclusoes:
    """Lê o `exclusoes.yaml` (ou o caminho dado) e devolve as exclusões validadas."""
    arquivo = Path(caminho) if caminho else CAMINHO_EXCLUSOES
    with arquivo.open(encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    if dados is None:
        return Exclusoes()
    if not isinstance(dados, dict):
        raise ErroExclusoes("o arquivo de exclusões deve ser um mapeamento")
    for chave in dados:
        if chave not in _CHAVES_DE_TOPO:
            raise ErroExclusoes(f"chave desconhecida no arquivo de exclusões: {chave!r}")
    return Exclusoes(
        tickers_excluidos=_validar_secao(
            "tickers_excluidos", dados.get("tickers_excluidos"), _validar_ticker
        ),
        cnpjs_sem_balanco=_validar_secao(
            "cnpjs_sem_balanco", dados.get("cnpjs_sem_balanco"), _validar_cnpj
        ),
    )
