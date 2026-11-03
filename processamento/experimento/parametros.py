"""Parâmetros do dataset do experimento (bloco `experimento` de config/parametros.yaml) e do treino (bloco `treino`).

Seção 7.3 da especificação; plano da etapa 5. Bloco `treino`: seções 7.4 a 7.7; plano da etapa 6.
Nenhuma função daqui acessa banco ou rede.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

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
    "deduplicar_entre_origens",
    "janela_dias_entre_origens",
    "titulo_palavras_min_entre_origens",
    "periodos_sem_coleta",
    "periodos_sem_coleta_cvm",
    "noticias_mes_fracao_minima",
    "principais",
}
_CHAVES_PRINCIPAIS = {"origens", "tipos_conteudo", "papeis"}
_INICIOS_JANELA = ("manha", "fechamento")
_CHAVES_TREINO = {
    "semente",
    "inicio_experimento",
    "treino_minimo_meses",
    "embargo_pregoes",
    "teste_final",
    "topk",
    "xgboost",
    "grade",
    "ganho_minimo_bloco",
    "logistica_c",
    "acaso_sorteios",
    "bootstrap_reamostragens",
    "bootstrap_bloco_pregoes",
    "motivos_qtd",
    "motivos_limiar",
    "calibracao",
}
FAMILIAS_PRODUCAO = ("xgb", "logistica")
_CHAVES_TESTE_FINAL = {"inicio", "fim", "liberado"}
_CHAVES_XGBOOST = {
    "n_estimators",
    "max_depth",
    "learning_rate",
    "subsample",
    "colsample_bytree",
    "min_child_weight",
    "reg_lambda",
}
_INTEIROS_XGBOOST = {"n_estimators", "max_depth"}
_CHAVES_CALIBRACAO = {"bins", "ece_maximo", "linhas_minimas", "liberar_chance"}
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    deduplicar_entre_origens: bool
    janela_dias_entre_origens: int
    titulo_palavras_min_entre_origens: int
    origens_principais: tuple[str, ...]
    tipos_principais: tuple[str, ...]
    papeis_principais: tuple[str, ...]
    periodos_sem_coleta: tuple[tuple[date, date], ...] = ()
    periodos_sem_coleta_cvm: tuple[tuple[date, date], ...] = ()
    noticias_mes_fracao_minima: float = 0.25


def mascara_sem_coleta(datas, periodos: tuple[tuple[date, date], ...]) -> np.ndarray:
    """True nas datas dentro de algum período sem coleta de notícias (limites inclusivos)."""
    indice = pd.DatetimeIndex(pd.to_datetime(list(datas))).normalize()
    mascara = np.zeros(len(indice), dtype=bool)
    for inicio, fim in periodos:
        mascara |= np.asarray((indice >= pd.Timestamp(inicio)) & (indice <= pd.Timestamp(fim)))
    return mascara


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


def _familia_producao(valor: object, onde: str) -> str:
    """"xgb" ou "logistica" (entre aspas no YAML); levanta `ErroParametrosExperimento` se não bater."""
    if valor not in FAMILIAS_PRODUCAO:
        raise ErroParametrosExperimento(f"{onde} deve ser um de {FAMILIAS_PRODUCAO} (recebeu {valor!r})")
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
        deduplicar_entre_origens=_booleano(bloco["deduplicar_entre_origens"], "experimento.deduplicar_entre_origens"),
        janela_dias_entre_origens=_inteiro_nao_negativo(
            bloco["janela_dias_entre_origens"], "experimento.janela_dias_entre_origens"
        ),
        titulo_palavras_min_entre_origens=_inteiro_nao_negativo(
            bloco["titulo_palavras_min_entre_origens"], "experimento.titulo_palavras_min_entre_origens"
        ),
        origens_principais=_lista_de_textos(principais["origens"], "experimento.principais.origens"),
        tipos_principais=_lista_de_textos(principais["tipos_conteudo"], "experimento.principais.tipos_conteudo"),
        papeis_principais=_lista_de_textos(principais["papeis"], "experimento.principais.papeis"),
        periodos_sem_coleta=_periodos_sem_coleta(bloco["periodos_sem_coleta"]),
        periodos_sem_coleta_cvm=_periodos_sem_coleta(
            bloco["periodos_sem_coleta_cvm"], "experimento.periodos_sem_coleta_cvm"
        ),
        noticias_mes_fracao_minima=_real(
            bloco["noticias_mes_fracao_minima"], "experimento.noticias_mes_fracao_minima", True
        ),
    )


@dataclass(frozen=True)
class ParametrosTreino:
    """Parâmetros do bloco `treino` (seções 7.4 a 7.7 da especificação; plano da etapa 6)."""

    semente: int
    inicio_experimento: str
    treino_minimo_meses: int
    embargo_pregoes: int
    teste_final_inicio: date
    teste_final_fim: date | None
    teste_final_liberado: bool
    topk: tuple[int, ...]
    xgboost: dict
    grade: dict[str, tuple]
    ganho_minimo_bloco: float
    logistica_c: float
    acaso_sorteios: int
    bootstrap_reamostragens: int
    bootstrap_bloco_pregoes: int
    motivos_qtd: int
    motivos_limiar: float
    calibracao_bins: int
    calibracao_ece_maximo: float
    calibracao_linhas_minimas: int
    liberar_chance: bool
    modelo_oficial: bool = False
    familia_producao: str = "xgb"   # família do modelo que a rotina publica ("xgb" ou "logistica")


def _inteiro_nao_negativo(valor: object, onde: str) -> int:
    """Confere um inteiro ≥ 0 (bool não conta); levanta `ErroParametrosExperimento` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroParametrosExperimento(f"{onde} deve ser um inteiro maior ou igual a zero (recebeu {valor!r})")
    return valor


def _real(valor: object, onde: str, positivo: bool) -> float:
    """Confere um número (bool não conta): > 0 se `positivo`, senão ≥ 0. Devolve float."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroParametrosExperimento(f"{onde} deve ser um número (recebeu {valor!r})")
    if valor < 0 or (positivo and valor == 0):
        exigido = "maior que zero" if positivo else "maior ou igual a zero"
        raise ErroParametrosExperimento(f"{onde} deve ser {exigido} (recebeu {valor!r})")
    return float(valor)


def _data_em_texto(valor: object, onde: str) -> date:
    """Confere data AAAA-MM-DD entre aspas (sem aspas o YAML lê outro tipo); levanta `ErroParametrosExperimento` se não bater."""
    if not isinstance(valor, str):
        raise ErroParametrosExperimento(
            f"{onde} deve ser uma data entre aspas (ex.: \"2026-06-23\"); sem aspas o YAML lê {valor!r} como outro tipo"
        )
    if not _RE_DATA.match(valor):
        raise ErroParametrosExperimento(f"{onde}: data inválida {valor!r} (use AAAA-MM-DD)")
    try:
        return date.fromisoformat(valor)
    except ValueError as erro:
        raise ErroParametrosExperimento(f"{onde}: data inválida {valor!r} ({erro})") from erro


def _periodos_sem_coleta(valor: object, onde: str = "experimento.periodos_sem_coleta") -> tuple[tuple[date, date], ...]:
    """Lista (pode ser vazia) de {inicio, fim}, com datas entre aspas e inicio <= fim."""
    if not isinstance(valor, list):
        raise ErroParametrosExperimento(f"{onde} deve ser uma lista de {{inicio, fim}} (vazia = nenhum período)")
    periodos = []
    for item in valor:
        _chaves_exatas(item, {"inicio", "fim"}, onde)
        inicio = _data_em_texto(item["inicio"], f"{onde}.inicio")
        fim = _data_em_texto(item["fim"], f"{onde}.fim")
        if inicio > fim:
            raise ErroParametrosExperimento(f"{onde}: inicio {inicio} depois do fim {fim}")
        periodos.append((inicio, fim))
    return tuple(periodos)


def _chaves_exatas(bloco: object, chaves: set[str], prefixo: str) -> None:
    """Confere que o bloco é um mapeamento com exatamente as `chaves`; as mensagens citam `prefixo.<chave>`."""
    if not isinstance(bloco, dict):
        raise ErroParametrosExperimento(f"{prefixo} deve ser um mapeamento")
    presentes = {str(c) for c in bloco}
    desconhecidas = presentes - chaves
    if desconhecidas:
        nomes = ", ".join(f"{prefixo}.{c}" for c in sorted(desconhecidas))
        raise ErroParametrosExperimento(f"chave desconhecida em {prefixo}: {nomes}")
    faltantes = chaves - presentes
    if faltantes:
        nomes = ", ".join(f"{prefixo}.{c}" for c in sorted(faltantes))
        raise ErroParametrosExperimento(f"faltam chaves em {prefixo}: {nomes}")


def _inicio_experimento(valor: object) -> str:
    """'cobertura' ou data AAAA-MM-DD entre aspas."""
    if valor == "cobertura":
        return valor
    _data_em_texto(valor, "treino.inicio_experimento")
    return valor


def _teste_final(bloco: object) -> tuple[date, date | None, bool]:
    """Valida `treino.teste_final`: início e fim são datas entre aspas; `fim: null` = trava ativa."""
    _chaves_exatas(bloco, _CHAVES_TESTE_FINAL, "treino.teste_final")
    inicio = _data_em_texto(bloco["inicio"], "treino.teste_final.inicio")
    fim = None
    if bloco["fim"] is not None:
        fim = _data_em_texto(bloco["fim"], "treino.teste_final.fim")
        if fim < inicio:
            raise ErroParametrosExperimento(
                f"treino.teste_final.fim ({fim}) não pode ser antes de treino.teste_final.inicio ({inicio})"
            )
    liberado = _booleano(bloco["liberado"], "treino.teste_final.liberado")
    return inicio, fim, liberado


def _topk(valor: object) -> tuple[int, ...]:
    """Lista não vazia de inteiros > 0 distintos."""
    if not isinstance(valor, list) or not valor:
        raise ErroParametrosExperimento("treino.topk deve ser uma lista não vazia de inteiros maiores que zero")
    ks = tuple(_inteiro_positivo(k, "treino.topk") for k in valor)
    if len(set(ks)) != len(ks):
        raise ErroParametrosExperimento(f"treino.topk não pode repetir valores (recebeu {list(ks)})")
    return ks


def _xgboost(valor: object) -> dict:
    """Exatamente as 7 chaves; `n_estimators` e `max_depth` inteiros > 0, as demais números > 0."""
    _chaves_exatas(valor, _CHAVES_XGBOOST, "treino.xgboost")
    for chave in sorted(_CHAVES_XGBOOST):
        onde = f"treino.xgboost.{chave}"
        if chave in _INTEIROS_XGBOOST:
            _inteiro_positivo(valor[chave], onde)
        else:
            _real(valor[chave], onde, positivo=True)
    return dict(valor)


def _grade(valor: object, xgboost: dict) -> dict[str, tuple]:
    """Chaves contidas nas do xgboost; cada uma com lista não vazia de valores válidos."""
    if not isinstance(valor, dict):
        raise ErroParametrosExperimento("treino.grade deve ser um mapeamento (hiperparâmetro: lista de valores)")
    saida = {}
    for chave, valores in valor.items():
        onde = f"treino.grade.{chave}"
        if chave not in xgboost:
            raise ErroParametrosExperimento(f"{onde} não é hiperparâmetro de treino.xgboost")
        if not isinstance(valores, list) or not valores:
            raise ErroParametrosExperimento(f"{onde} deve ser uma lista não vazia de valores")
        for v in valores:
            if chave in _INTEIROS_XGBOOST:
                _inteiro_positivo(v, onde)
            else:
                _real(v, onde, positivo=True)
        saida[chave] = tuple(valores)
    return saida


def carregar_parametros_treino(caminho: str | None = None) -> ParametrosTreino:
    """Lê o bloco `treino` (do caminho dado ou do parametros.yaml) e valida cada chave."""
    bloco = calendario.carregar_parametros(caminho).get("treino")
    if bloco is None:
        raise ErroParametrosExperimento("falta o bloco treino no arquivo de parâmetros")
    # `modelo_oficial` e `familia_producao` são opcionais (ausente = false / xgb), para não quebrar yamls de teste.
    opcionais = {"modelo_oficial", "familia_producao"} & set(bloco) if isinstance(bloco, dict) else set()
    _chaves_exatas(bloco, _CHAVES_TREINO | opcionais, "treino")
    inicio, fim, liberado = _teste_final(bloco["teste_final"])
    calibracao = bloco["calibracao"]
    _chaves_exatas(calibracao, _CHAVES_CALIBRACAO, "treino.calibracao")
    xgboost = _xgboost(bloco["xgboost"])

    return ParametrosTreino(
        semente=_inteiro_nao_negativo(bloco["semente"], "treino.semente"),
        inicio_experimento=_inicio_experimento(bloco["inicio_experimento"]),
        treino_minimo_meses=_inteiro_positivo(bloco["treino_minimo_meses"], "treino.treino_minimo_meses"),
        embargo_pregoes=_inteiro_positivo(bloco["embargo_pregoes"], "treino.embargo_pregoes"),
        teste_final_inicio=inicio,
        teste_final_fim=fim,
        teste_final_liberado=liberado,
        topk=_topk(bloco["topk"]),
        xgboost=xgboost,
        grade=_grade(bloco["grade"], xgboost),
        ganho_minimo_bloco=_real(bloco["ganho_minimo_bloco"], "treino.ganho_minimo_bloco", positivo=False),
        logistica_c=_real(bloco["logistica_c"], "treino.logistica_c", positivo=True),
        acaso_sorteios=_inteiro_positivo(bloco["acaso_sorteios"], "treino.acaso_sorteios"),
        bootstrap_reamostragens=_inteiro_positivo(bloco["bootstrap_reamostragens"], "treino.bootstrap_reamostragens"),
        bootstrap_bloco_pregoes=_inteiro_positivo(bloco["bootstrap_bloco_pregoes"], "treino.bootstrap_bloco_pregoes"),
        motivos_qtd=_inteiro_positivo(bloco["motivos_qtd"], "treino.motivos_qtd"),
        motivos_limiar=_real(bloco["motivos_limiar"], "treino.motivos_limiar", positivo=False),
        calibracao_bins=_inteiro_positivo(calibracao["bins"], "treino.calibracao.bins"),
        calibracao_ece_maximo=_real(calibracao["ece_maximo"], "treino.calibracao.ece_maximo", positivo=False),
        calibracao_linhas_minimas=_inteiro_positivo(calibracao["linhas_minimas"], "treino.calibracao.linhas_minimas"),
        liberar_chance=_booleano(calibracao["liberar_chance"], "treino.calibracao.liberar_chance"),
        modelo_oficial=_booleano(bloco.get("modelo_oficial", False), "treino.modelo_oficial"),
        familia_producao=_familia_producao(bloco.get("familia_producao", "xgb"), "treino.familia_producao"),
    )
