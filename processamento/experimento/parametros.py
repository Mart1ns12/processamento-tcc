"""Parâmetros do dataset do experimento (bloco `experimento` de config/parametros.yaml).

Seção 7.3 da especificação; plano da etapa 5. Nenhuma função daqui acessa banco ou rede.
"""

from __future__ import annotations

from dataclasses import dataclass

from processamento import calendario

_CHAVES = {
    "retornos",
    "exposicao_pregoes",
    "exposicao_minimo",
    "extremos_pregoes",
    "extremos_minimo",
    "mudanca_tom_pregoes",
    "mudanca_tom_minimo",
    "sem_horario_na_noite",
    "inicio_janela",
    "deduplicar_titulo",
    "principais",
}
_CHAVES_PRINCIPAIS = {"origens", "tipos_conteudo", "papeis"}
_INICIOS_JANELA = ("manha", "fechamento")


class ErroParametrosExperimento(Exception):
    """Bloco `experimento` inválido ou ausente (a mensagem diz o que corrigir)."""


@dataclass(frozen=True)
class ParametrosExperimento:
    """Parâmetros do bloco `experimento` (janelas em PREGÕES do calendário)."""

    retornos: dict[str, int]
    exposicao_pregoes: int
    exposicao_minimo: int
    extremos_pregoes: int
    extremos_minimo: int
    mudanca_tom_pregoes: int
    mudanca_tom_minimo: int
    sem_horario_na_noite: bool
    inicio_janela: str
    deduplicar_titulo: bool
    origens_principais: tuple[str, ...]
    tipos_principais: tuple[str, ...]
    papeis_principais: tuple[str, ...]


def _inteiro_positivo(valor: object, onde: str) -> int:
    """Confere um inteiro > 0 (bool não conta); levanta `ErroParametrosExperimento` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ErroParametrosExperimento(f"{onde} deve ser um inteiro maior que zero (recebeu {valor!r})")
    return valor


def _booleano(valor: object, onde: str) -> bool:
    """Confere true/false do YAML (sem aspas); levanta `ErroParametrosExperimento` se não bater."""
    if not isinstance(valor, bool):
        raise ErroParametrosExperimento(f"{onde} deve ser true ou false (recebeu {valor!r})")
    return valor


def _escolha(valor: object, onde: str, opcoes: tuple[str, ...]) -> str:
    """Confere um texto entre as opções aceitas; levanta `ErroParametrosExperimento` se não bater."""
    if not isinstance(valor, str) or valor not in opcoes:
        raise ErroParametrosExperimento(f"{onde} deve ser um de {list(opcoes)} (recebeu {valor!r})")
    return valor


def _lista_de_textos(valor: object, onde: str) -> tuple[str, ...]:
    """Confere lista não vazia de textos não vazios; levanta `ErroParametrosExperimento` se não bater."""
    if not isinstance(valor, list) or not valor:
        raise ErroParametrosExperimento(f"{onde} deve ser uma lista não vazia de textos")
    for item in valor:
        if not isinstance(item, str) or not item.strip():
            raise ErroParametrosExperimento(f"{onde} aceita só textos não vazios (recebeu {item!r})")
    return tuple(valor)


def _minimo_nao_passa(minimo: int, pregoes: int, nome_min: str, nome_pregoes: str) -> None:
    """O mínimo de observações não pode ser maior que a janela."""
    if minimo > pregoes:
        raise ErroParametrosExperimento(
            f"experimento.{nome_min} ({minimo}) não pode passar de experimento.{nome_pregoes} ({pregoes})"
        )


def carregar_parametros_experimento(caminho: str | None = None) -> ParametrosExperimento:
    """Lê o bloco `experimento` (do caminho dado ou do parametros.yaml) e valida cada chave."""
    bloco = calendario.carregar_parametros(caminho).get("experimento")
    if not isinstance(bloco, dict):
        raise ErroParametrosExperimento("falta o bloco experimento no arquivo de parâmetros")
    desconhecidas = set(bloco) - _CHAVES
    if desconhecidas:
        raise ErroParametrosExperimento(f"chave desconhecida no bloco experimento: {sorted(desconhecidas)}")
    faltantes = _CHAVES - set(bloco)
    if faltantes:
        raise ErroParametrosExperimento(f"faltam chaves no bloco experimento: {sorted(faltantes)}")

    retornos = bloco["retornos"]
    if not isinstance(retornos, dict) or not retornos:
        raise ErroParametrosExperimento("experimento.retornos deve ser um mapeamento não vazio (ex.: ret_1d: 1)")
    for nome, n in retornos.items():
        if not isinstance(nome, str):
            raise ErroParametrosExperimento(f"nome de retorno inválido em experimento.retornos: {nome!r}")
        _inteiro_positivo(n, f"experimento.retornos.{nome}")

    principais = bloco["principais"]
    if not isinstance(principais, dict):
        raise ErroParametrosExperimento("experimento.principais deve ser um mapeamento")
    desconhecidas = set(principais) - _CHAVES_PRINCIPAIS
    if desconhecidas:
        raise ErroParametrosExperimento(f"chave desconhecida em experimento.principais: {sorted(desconhecidas)}")
    faltantes = _CHAVES_PRINCIPAIS - set(principais)
    if faltantes:
        raise ErroParametrosExperimento(f"faltam chaves em experimento.principais: {sorted(faltantes)}")

    exposicao_pregoes = _inteiro_positivo(bloco["exposicao_pregoes"], "experimento.exposicao_pregoes")
    exposicao_minimo = _inteiro_positivo(bloco["exposicao_minimo"], "experimento.exposicao_minimo")
    extremos_pregoes = _inteiro_positivo(bloco["extremos_pregoes"], "experimento.extremos_pregoes")
    extremos_minimo = _inteiro_positivo(bloco["extremos_minimo"], "experimento.extremos_minimo")
    mudanca_tom_pregoes = _inteiro_positivo(bloco["mudanca_tom_pregoes"], "experimento.mudanca_tom_pregoes")
    mudanca_tom_minimo = _inteiro_positivo(bloco["mudanca_tom_minimo"], "experimento.mudanca_tom_minimo")
    _minimo_nao_passa(exposicao_minimo, exposicao_pregoes, "exposicao_minimo", "exposicao_pregoes")
    _minimo_nao_passa(extremos_minimo, extremos_pregoes, "extremos_minimo", "extremos_pregoes")
    _minimo_nao_passa(mudanca_tom_minimo, mudanca_tom_pregoes, "mudanca_tom_minimo", "mudanca_tom_pregoes")

    return ParametrosExperimento(
        retornos=dict(retornos),
        exposicao_pregoes=exposicao_pregoes,
        exposicao_minimo=exposicao_minimo,
        extremos_pregoes=extremos_pregoes,
        extremos_minimo=extremos_minimo,
        mudanca_tom_pregoes=mudanca_tom_pregoes,
        mudanca_tom_minimo=mudanca_tom_minimo,
        sem_horario_na_noite=_booleano(bloco["sem_horario_na_noite"], "experimento.sem_horario_na_noite"),
        inicio_janela=_escolha(bloco["inicio_janela"], "experimento.inicio_janela", _INICIOS_JANELA),
        deduplicar_titulo=_booleano(bloco["deduplicar_titulo"], "experimento.deduplicar_titulo"),
        origens_principais=_lista_de_textos(principais["origens"], "experimento.principais.origens"),
        tipos_principais=_lista_de_textos(principais["tipos_conteudo"], "experimento.principais.tipos_conteudo"),
        papeis_principais=_lista_de_textos(principais["papeis"], "experimento.principais.papeis"),
    )
