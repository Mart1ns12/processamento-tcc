"""Parâmetros da rotina diária (bloco `rotina` de config/parametros.yaml); plano da etapa 8, fase 0.

Pastas relativas são ancoradas em `fontes.RAIZ`. Nenhuma função daqui acessa banco ou rede.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from processamento import calendario, fontes
from processamento.diagnostico.esperado import ETAPAS_COLETA

_CHAVES = {
    "inicio_consulta",
    "intervalo_minutos",
    "prazo",
    "prazo_tardio",
    "etapas_conferidas",
    "pasta_logs",
    "trava",
    "trava_validade_horas",
    "aviso_calendario_dias",
    "checagem",
}
_CHAVES_CHECAGEM = {
    "acoes_minimo_fracao",
    "retorno_maximo_abs",
    "preco_parado_pregoes",
    "max_tickers_por_aviso",
}
# Etapas que a rotina confere para avisar (sem `entrega` e `analise`: são do fim do dia, não da coleta).
_ETAPAS_PERMITIDAS = tuple(e for e in ETAPAS_COLETA if e not in ("entrega", "analise"))
_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ErroParametrosRotina(Exception):
    """Bloco `rotina` inválido ou ausente (a mensagem diz o que corrigir)."""


@dataclass(frozen=True)
class ParametrosChecagem:
    """Parâmetros da checagem diária (bloco `rotina.checagem`)."""

    acoes_minimo_fracao: float
    retorno_maximo_abs: float
    preco_parado_pregoes: int
    max_tickers_por_aviso: int


@dataclass(frozen=True)
class ParametrosRotina:
    """Parâmetros do bloco `rotina` (pastas já ancoradas em `fontes.RAIZ`)."""

    inicio_consulta: time
    intervalo_minutos: int
    prazo: time
    prazo_tardio: time | None
    etapas_conferidas: tuple[str, ...]
    pasta_logs: Path
    trava: Path
    trava_validade_horas: float
    aviso_calendario_dias: int
    checagem: ParametrosChecagem


def _texto(valor: object, onde: str) -> str:
    """Confere texto não vazio; levanta `ErroParametrosRotina` se não bater."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErroParametrosRotina(f"{onde} deve ser um texto não vazio entre aspas (recebeu {valor!r})")
    return valor


def _hora(valor: object, onde: str) -> time:
    """Confere o horário HH:MM entre aspas; levanta `ErroParametrosRotina` se não bater."""
    if not isinstance(valor, str):
        raise ErroParametrosRotina(
            f"{onde} deve estar entre aspas no YAML (ex.: \"10:00\"; sem aspas o YAML lê o horário como número)"
        )
    if not _RE_HORA.match(valor):
        raise ErroParametrosRotina(f"{onde}: horário inválido {valor!r} (formato HH:MM)")
    return time.fromisoformat(valor)


def _inteiro_positivo(valor: object, onde: str) -> int:
    """Confere um inteiro > 0 (bool não conta); levanta `ErroParametrosRotina` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ErroParametrosRotina(f"{onde} deve ser um inteiro maior que zero (recebeu {valor!r})")
    return valor


def _inteiro_nao_negativo(valor: object, onde: str) -> int:
    """Confere um inteiro ≥ 0 (bool não conta); levanta `ErroParametrosRotina` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroParametrosRotina(f"{onde} deve ser um inteiro maior ou igual a zero (recebeu {valor!r})")
    return valor


def _numero(valor: object, onde: str) -> float:
    """Confere um número (bool não conta) e devolve float; quem chama confere o intervalo."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroParametrosRotina(f"{onde} deve ser um número (recebeu {valor!r})")
    return float(valor)


def _chaves_exatas(bloco: object, chaves: set[str], prefixo: str) -> None:
    """Confere que o bloco é um mapeamento com exatamente as `chaves`; as mensagens citam `prefixo.<chave>`."""
    if not isinstance(bloco, dict):
        raise ErroParametrosRotina(f"{prefixo} deve ser um mapeamento")
    presentes = {str(c) for c in bloco}
    desconhecidas = presentes - chaves
    if desconhecidas:
        nomes = ", ".join(f"{prefixo}.{c}" for c in sorted(desconhecidas))
        raise ErroParametrosRotina(f"chave desconhecida em {prefixo}: {nomes}")
    faltantes = chaves - presentes
    if faltantes:
        nomes = ", ".join(f"{prefixo}.{c}" for c in sorted(faltantes))
        raise ErroParametrosRotina(f"faltam chaves em {prefixo}: {nomes}")


def _etapas(valor: object) -> tuple[str, ...]:
    """Lista de etapas da coleta conferidas pela rotina (só nomes de `_ETAPAS_PERMITIDAS`)."""
    if not isinstance(valor, list):
        raise ErroParametrosRotina("rotina.etapas_conferidas deve ser uma lista de textos")
    for etapa in valor:
        if not isinstance(etapa, str) or etapa not in _ETAPAS_PERMITIDAS:
            raise ErroParametrosRotina(
                f"rotina.etapas_conferidas aceita só {list(_ETAPAS_PERMITIDAS)} (recebeu {etapa!r})"
            )
    return tuple(valor)


def _checagem(bloco: object) -> ParametrosChecagem:
    """Valida `rotina.checagem`: chaves exatas, frações em (0, 1] e contagens dentro do mínimo."""
    _chaves_exatas(bloco, _CHAVES_CHECAGEM, "rotina.checagem")
    fracao = _numero(bloco["acoes_minimo_fracao"], "rotina.checagem.acoes_minimo_fracao")
    if not (0 < fracao <= 1):
        raise ErroParametrosRotina(
            f"rotina.checagem.acoes_minimo_fracao deve estar entre 0 (exclusivo) e 1 (recebeu {fracao!r})"
        )
    retorno = _numero(bloco["retorno_maximo_abs"], "rotina.checagem.retorno_maximo_abs")
    if retorno <= 0:
        raise ErroParametrosRotina(f"rotina.checagem.retorno_maximo_abs deve ser maior que zero (recebeu {retorno!r})")
    pregoes = _inteiro_nao_negativo(bloco["preco_parado_pregoes"], "rotina.checagem.preco_parado_pregoes")
    if pregoes < 2:
        raise ErroParametrosRotina(f"rotina.checagem.preco_parado_pregoes deve ser pelo menos 2 (recebeu {pregoes})")
    max_tickers = _inteiro_positivo(bloco["max_tickers_por_aviso"], "rotina.checagem.max_tickers_por_aviso")
    return ParametrosChecagem(
        acoes_minimo_fracao=fracao,
        retorno_maximo_abs=retorno,
        preco_parado_pregoes=pregoes,
        max_tickers_por_aviso=max_tickers,
    )


def carregar_parametros_rotina(caminho: str | None = None) -> ParametrosRotina:
    """Lê o bloco `rotina` (do caminho dado ou do parametros.yaml) e valida cada chave."""
    bloco = calendario.carregar_parametros(caminho).get("rotina")
    if bloco is None:
        raise ErroParametrosRotina("falta o bloco rotina no arquivo de parâmetros")
    _chaves_exatas(bloco, _CHAVES, "rotina")

    inicio = _hora(bloco["inicio_consulta"], "rotina.inicio_consulta")
    prazo = _hora(bloco["prazo"], "rotina.prazo")
    if inicio >= prazo:
        raise ErroParametrosRotina(
            f"rotina.inicio_consulta ({inicio:%H:%M}) deve ser antes de rotina.prazo ({prazo:%H:%M})"
        )
    prazo_tardio = None
    if bloco["prazo_tardio"] is not None:
        prazo_tardio = _hora(bloco["prazo_tardio"], "rotina.prazo_tardio")
        if prazo_tardio <= prazo:
            raise ErroParametrosRotina(
                f"rotina.prazo_tardio ({prazo_tardio:%H:%M}) deve ser depois de rotina.prazo ({prazo:%H:%M}) ou null"
            )

    trava_validade = _numero(bloco["trava_validade_horas"], "rotina.trava_validade_horas")
    if trava_validade <= 0:
        raise ErroParametrosRotina(f"rotina.trava_validade_horas deve ser maior que zero (recebeu {trava_validade!r})")

    return ParametrosRotina(
        inicio_consulta=inicio,
        intervalo_minutos=_inteiro_positivo(bloco["intervalo_minutos"], "rotina.intervalo_minutos"),
        prazo=prazo,
        prazo_tardio=prazo_tardio,
        etapas_conferidas=_etapas(bloco["etapas_conferidas"]),
        pasta_logs=fontes.RAIZ / _texto(bloco["pasta_logs"], "rotina.pasta_logs"),
        trava=fontes.RAIZ / _texto(bloco["trava"], "rotina.trava"),
        trava_validade_horas=trava_validade,
        aviso_calendario_dias=_inteiro_nao_negativo(bloco["aviso_calendario_dias"], "rotina.aviso_calendario_dias"),
        checagem=_checagem(bloco["checagem"]),
    )
