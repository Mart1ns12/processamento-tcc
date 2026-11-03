"""Contrato da saída (seção 8 da especificação; plano da etapa 7, fase 4).

Converte valores (numpy, NaN) para o formato do JSON, confere cada registro dos pacotes contra o
esquema da seção 4 do plano, compara com o último envio ("quando muda") e grava os arquivos de
forma atômica. Nenhuma função daqui acessa banco ou rede.

Mini-linguagem dos esquemas (`ESQUEMAS`):
- texto: "texto", "texto?" (aceita null), "data", "data?", "data_hora", "data_hora?", "inteiro",
  "numero", "numero?", "bool", "bool?", "objeto", "versao" (== "1.0"), "modelo" (xgb-AAAA-MM ou logistica-AAAA-MM);
- folhas: "folha" (número), "folha_bool", "folha_texto", "folha_data", "chance";
- compostos: ("enum", opções), ("lista", tipo), ("folha+", {campos extras}) (folha com campos
  extras), ("ou_nulo", tipo), ("opcional", tipo) (pode faltar);
- {...}: objeto com exatamente esses campos (campo a mais ou faltando = erro).
`series_diarias` não usa esquema de folhas (S20): `validar` chama `validar_serie`.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

VERSAO_CONTRATO = "1.0"
SP = ZoneInfo("America/Sao_Paulo")
STATUS = ("ok", "nao_se_aplica", "indisponivel", "historico_insuficiente", "lucro_negativo")
STATUS_CHANCE = ("ok", "calibracao_nao_conferida")
PACOTES = ("acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
           "noticias_dia", "experimento_historico", "experimento_top", "execucao")   # ordem da 2.5 (sem a execucao inicial)
CHAVES = {"acoes": ["ticker"], "mercado_dia": ["data_referencia"], "resumo_acao": ["data_referencia", "ticker"],
          "series_diarias": ["ticker", "data"], "fundamentos_trimestrais": ["ticker", "data_fim_periodo"],
          "proventos": ["ticker", "tipo", "data_com"], "noticias_dia": ["data_referencia", "ticker"],
          "experimento_top": ["data_referencia"], "experimento_historico": ["data_referencia"],
          "execucao": ["data_referencia", "rodada"]}
QUANDO_MUDA = ("acoes", "fundamentos_trimestrais", "proventos", "series_diarias")
CAMPOS_SERIE = {"acao": ("fechamento", "indice_retorno_total", "volume", "pl", "pvp", "dividend_yield"),
                "etf": ("fechamento", "indice_retorno_total", "volume"), "indice": ("fechamento", "indice_retorno_total"),
                "taxa": ("indice_retorno_total",),
                "setor_sem_empresa": ("indice_retorno_total", "n_empresas")}

_META_CAMPOS = ("versao_contrato", "gerado_em", "dados_ate")
_CAMPOS_LOTE = ("pacote", "versao_contrato", "chave", "gerado_em", "dados_ate", "registros", "removidos")
_CAMPOS_TRIMESTRAIS = ("receita_trimestre", "receita_12m", "lucro_liquido_trimestre", "lucro_liquido_12m",
                       "margem_bruta", "margem_liquida", "roe", "ebitda_trimestre", "ebitda_12m", "margem_ebitda",
                       "divida_liquida", "dl_pl", "dl_ebitda", "payout_12m")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_DATA_HORA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
_RE_MODELO = re.compile(r"^(xgb|logistica)-\d{4}-\d{2}$")


class ErroContrato(ValueError):
    """Valor, registro ou lote fora do contrato (a mensagem traz o caminho do campo)."""


# ---------------------------------------------------------------- conversão de valores

def _ausente(x: object) -> bool:
    """True para None, pd.NA, NaT e NaN."""
    if x is None or x is pd.NA or x is pd.NaT:
        return True
    return isinstance(x, (float, np.floating)) and math.isnan(x)


def numero(x: object) -> int | float | None:
    """Número do contrato: numpy vira Python, NaN e None viram None; bool é recusado."""
    if isinstance(x, (bool, np.bool_)):
        raise TypeError(f"booleano não é número no contrato: {x!r}")
    if _ausente(x):
        return None
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        if math.isinf(f):
            raise ErroContrato(f"infinito não é valor do contrato: {f}")
        return f
    raise TypeError(f"tipo não numérico no contrato: {type(x).__name__}")


def _conferir_status(valor: object, status: str) -> None:
    """Regra da folha: ok exige valor; valor só com ok ou lucro_negativo."""
    if status not in STATUS:
        raise ErroContrato(f"status desconhecido: {status!r}")
    if valor is None and status == "ok":
        raise ErroContrato("status ok exige valor (sem valor, use outro status)")
    if valor is not None and status not in ("ok", "lucro_negativo"):
        raise ErroContrato(f"valor com status {status}: sem valor use null, não 0")


def folha(valor: object, status: str, **extras: object) -> dict:
    """Folha `{valor, status}` de um indicador (número ou null)."""
    v = numero(valor)
    _conferir_status(v, status)
    return {"valor": v, "status": status, **extras}


def folha_bool(valor: object, status: str) -> dict:
    """Folha de valor booleano (ex.: caixa_liquido)."""
    v = None if _ausente(valor) else bool(valor)
    _conferir_status(v, status)
    return {"valor": v, "status": status}


def folha_texto(valor: str | None, status: str) -> dict:
    """Folha de valor texto (ex.: ipca_ate = "2025-09")."""
    v = None if _ausente(valor) else str(valor)
    _conferir_status(v, status)
    return {"valor": v, "status": status}


def folha_data(valor: object, status: str) -> dict:
    """Folha de data (ex.: data_pagamento)."""
    v = data_txt(valor)
    _conferir_status(v, status)
    return {"valor": v, "status": status}


def data_txt(x: object) -> str | None:
    """Data (date, Timestamp ou texto ISO) em "AAAA-MM-DD"; ausente vira None."""
    if _ausente(x):
        return None
    if isinstance(x, str):
        return date.fromisoformat(x).isoformat()
    if isinstance(x, (date, datetime)):
        return x.strftime("%Y-%m-%d")
    raise TypeError(f"data não reconhecida: {type(x).__name__}")


def data_hora_txt(x: object) -> str | None:
    """Data-hora com fuso em ISO no horário de São Paulo (`-03:00`); ausente vira None."""
    if _ausente(x):
        return None
    if not isinstance(x, datetime) or x.tzinfo is None:
        raise ValueError("data-hora sem fuso horário não entra no contrato")
    return x.astimezone(SP).isoformat(timespec="seconds")


def meta(gerado_em: str, dados_ate: str) -> dict:
    """Campos comuns a todo registro: versão do contrato e os dois instantes da rodada."""
    return {"versao_contrato": VERSAO_CONTRATO, "gerado_em": gerado_em, "dados_ate": dados_ate}


# ---------------------------------------------------------------- validação

def _erro(caminho: str, motivo: str) -> ErroContrato:
    return ErroContrato(f"{caminho}: {motivo}")


def _opcional(spec: object) -> bool:
    return isinstance(spec, tuple) and spec[0] == "opcional"


def _conferir_numero(valor: object, caminho: str) -> None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise _erro(caminho, f"deveria ser número (recebeu {type(valor).__name__})")
    if isinstance(valor, float):
        if math.isnan(valor):
            raise _erro(caminho, "NaN não é valor (use null com um status)")
        if math.isinf(valor):
            raise _erro(caminho, "infinito não é valor do contrato")


def _conferir_data(valor: object, caminho: str) -> None:
    if not isinstance(valor, str) or not _RE_DATA.match(valor):
        raise _erro(caminho, f"data deveria ser AAAA-MM-DD (recebeu {valor!r})")
    try:
        date.fromisoformat(valor)
    except ValueError as e:
        raise _erro(caminho, f"data inválida {valor!r}") from e


def _conferir_data_hora(valor: object, caminho: str) -> None:
    if not isinstance(valor, str) or not _RE_DATA_HORA.match(valor):
        raise _erro(caminho, f"data-hora deveria ser AAAA-MM-DDTHH:MM:SS com fuso (recebeu {valor!r})")
    try:
        datetime.fromisoformat(valor)
    except ValueError as e:
        raise _erro(caminho, f"data-hora inválida {valor!r}") from e


def _checar_tipo(tipo: str, valor: object, caminho: str) -> None:
    """Confere um valor contra um tipo escalar da mini-linguagem (sufixo `?` aceita null)."""
    opcional = tipo.endswith("?")
    base = tipo[:-1] if opcional else tipo
    if valor is None:
        if opcional:
            return
        raise _erro(caminho, "não pode ser null")
    if base == "texto":
        if not isinstance(valor, str):
            raise _erro(caminho, f"deveria ser texto (recebeu {type(valor).__name__})")
    elif base == "data":
        _conferir_data(valor, caminho)
    elif base == "data_hora":
        _conferir_data_hora(valor, caminho)
    elif base == "numero":
        _conferir_numero(valor, caminho)
    elif base == "bool":
        if not isinstance(valor, bool):
            raise _erro(caminho, "deveria ser true ou false")
    elif base == "inteiro":
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise _erro(caminho, "deveria ser inteiro")
    elif base == "objeto":
        if not isinstance(valor, dict):
            raise _erro(caminho, "deveria ser um objeto")
    elif base == "versao":
        if valor != VERSAO_CONTRATO:
            raise _erro(caminho, f"versao_contrato deveria ser {VERSAO_CONTRATO!r} (recebeu {valor!r})")
    elif base == "modelo":
        if not isinstance(valor, str) or not _RE_MODELO.match(valor):
            raise _erro(caminho, f"modelo deveria ser xgb-AAAA-MM ou logistica-AAAA-MM (recebeu {valor!r})")
    elif base == "chance":
        _checar_chance(valor, caminho)
    elif base in ("folha", "folha_bool", "folha_texto", "folha_data"):
        tipo_valor = {"folha": "numero", "folha_bool": "bool", "folha_texto": "texto", "folha_data": "data"}[base]
        _checar_folha(valor, caminho, tipo_valor)
    else:
        raise ValueError(f"tipo de esquema desconhecido: {tipo!r}")


def _checar_folha(valor: object, caminho: str, tipo_valor: str = "numero", extras: dict | None = None) -> None:
    """Folha `{valor, status}` (+ campos extras). Ausência é null com status, nunca 0."""
    if not isinstance(valor, dict):
        raise _erro(caminho, "deveria ser uma folha {valor, status}")
    extras = extras or {}
    for campo in valor:
        if campo not in ("valor", "status") and campo not in extras:
            raise _erro(f"{caminho}.{campo}", "campo desconhecido")
    for campo in ("valor", "status"):
        if campo not in valor:
            raise _erro(f"{caminho}.{campo}", "campo obrigatório ausente")
    status = valor["status"]
    if status not in STATUS:
        raise _erro(f"{caminho}.status", f"status desconhecido {status!r}")
    v = valor["valor"]
    if v is not None:
        _checar_tipo(tipo_valor, v, f"{caminho}.valor")
    if v is None and status == "ok":
        raise _erro(caminho, "status ok exige valor")
    if v is not None and status not in ("ok", "lucro_negativo"):
        raise _erro(caminho, f"valor com status {status} (sem valor use null, não 0)")
    for campo, sub in extras.items():
        if campo not in valor:
            if _opcional(sub):
                continue
            raise _erro(f"{caminho}.{campo}", "campo obrigatório ausente")
        _checar(sub, valor[campo], f"{caminho}.{campo}")


_CAMPOS_CHANCE = ("valor", "referencia_acaso", "exibir", "status")


def _checar_chance(valor: object, caminho: str) -> None:
    """Chance do experimento: escondida (exibir false, sem valor) ou liberada (exibir true, com valor e referência)."""
    if not isinstance(valor, dict):
        raise _erro(caminho, "deveria ser um objeto de chance")
    for campo in valor:
        if campo not in _CAMPOS_CHANCE:
            raise _erro(f"{caminho}.{campo}", "campo desconhecido")
    for campo in _CAMPOS_CHANCE:
        if campo not in valor:
            raise _erro(f"{caminho}.{campo}", "campo obrigatório ausente")
    if not isinstance(valor["exibir"], bool):
        raise _erro(f"{caminho}.exibir", "deveria ser true ou false")
    if valor["status"] not in STATUS_CHANCE:
        raise _erro(f"{caminho}.status", f"status desconhecido {valor['status']!r}")
    if not valor["exibir"]:
        if valor["valor"] is not None:
            raise _erro(f"{caminho}.valor", "com exibir false o valor deveria ser null")
        if valor["referencia_acaso"] is not None:
            raise _erro(f"{caminho}.referencia_acaso", "com exibir false a referência deveria ser null")
        if valor["status"] != "calibracao_nao_conferida":
            raise _erro(f"{caminho}.status", "com exibir false o status deveria ser calibracao_nao_conferida")
        return
    if valor["status"] != "ok":
        raise _erro(f"{caminho}.status", "com exibir true o status deveria ser ok")
    _conferir_numero(valor["valor"], f"{caminho}.valor")
    if not 0 <= valor["valor"] <= 1:
        raise _erro(f"{caminho}.valor", f"probabilidade deveria estar em [0, 1] (recebeu {valor['valor']!r})")
    _conferir_numero(valor["referencia_acaso"], f"{caminho}.referencia_acaso")
    if not 0 < valor["referencia_acaso"] < 1:
        raise _erro(f"{caminho}.referencia_acaso", f"referência deveria estar em (0, 1) (recebeu {valor['referencia_acaso']!r})")


def _checar_objeto(spec: dict, valor: object, caminho: str) -> None:
    if not isinstance(valor, dict):
        raise _erro(caminho, "deveria ser um objeto")
    for campo in valor:
        if campo not in spec:
            raise _erro(f"{caminho}.{campo}", "campo desconhecido")
    for campo, sub in spec.items():
        if campo not in valor:
            if _opcional(sub):
                continue
            raise _erro(f"{caminho}.{campo}", "campo obrigatório ausente")
        _checar(sub, valor[campo], f"{caminho}.{campo}")


def _checar_composto(spec: tuple, valor: object, caminho: str) -> None:
    tipo = spec[0]
    if tipo == "enum":
        if valor not in spec[1]:
            raise _erro(caminho, f"valor {valor!r} fora de {list(spec[1])}")
    elif tipo == "lista":
        if not isinstance(valor, list):
            raise _erro(caminho, "deveria ser uma lista")
        for i, item in enumerate(valor):
            _checar(spec[1], item, f"{caminho}[{i}]")
    elif tipo == "folha+":
        _checar_folha(valor, caminho, "numero", spec[1])
    elif tipo == "ou_nulo":
        if valor is not None:
            _checar(spec[1], valor, caminho)
    elif tipo == "opcional":
        _checar(spec[1], valor, caminho)
    else:
        raise ValueError(f"tipo de esquema desconhecido: {tipo!r}")


def _checar(spec: object, valor: object, caminho: str) -> None:
    if isinstance(spec, dict):
        _checar_objeto(spec, valor, caminho)
    elif isinstance(spec, tuple):
        _checar_composto(spec, valor, caminho)
    else:
        _checar_tipo(spec, valor, caminho)


_COTACAO = {"fechamento": "folha", "variacao_dia": "folha", "unidade": "texto"}
_JANELAS = {"d1": "folha", "m1": "folha", "m6": "folha", "a1": "folha"}
_ANO = ("folha+", {"ano": "inteiro"})
_SETOR = ("folha+", {"setor": "folha"})
_TEXTO = ("folha+", {"texto": "texto?"})
_STATUS_ENUM = ("enum", STATUS)
_ITEM_NOTICIA = {
    "id": "texto", "titulo": "texto", "fonte": "texto?", "link": "texto?", "publicado_em": "data_hora?",
    "data_publicacao": "data", "precisao_hora": ("enum", ("hora", "sem_hora", "meia_noite_pacifico")),
    "janela": ("enum", ("pregao", "noite", "sem_horario")),
    "rotulo": ("enum", ("positivo", "neutro", "negativo", None)),
    "prob_positivo": "numero?", "prob_neutro": "numero?", "prob_negativo": "numero?",
    "destaque": "inteiro", "status": ("enum", ("ok", "indisponivel")),
}
_DIA_HISTORICO = {
    "data_referencia": "data", "pregao_base": "data", "ranking": ("lista", "texto"),
    "resultado": ("lista", {"ticker": "texto", "retorno": "folha", "retorno_ibov": "folha",
                            "superou": ("ou_nulo", "bool")}),
    "acertos_dia": "inteiro", "acertos_top3": "inteiro", "resultado_incompleto": "bool",
    "taxa_acumulada": "folha",
}

# Motivos da decisão do gatilho da coleta (seção 8 do plano da etapa 8). Fica aqui para o contrato não importar `rotina`.
MOTIVOS_COLETA = ("entrega_concluida", "entrega_pendente", "entrega_falhou", "sem_daily", "daily_agendado",
                  "dados_atrasados", "falha_consulta", "sem_esperar")
_ETAPAS_COLETA = ("precos", "macro", "noticias", "ipe", "enriquecimento", "juiza", "cadastro", "entrega", "analise")
# `consultado` e `nota` são o formato antigo (sem coleta consultada); o resto é opcional e vem do painel e do laço.
_COLETA_STATUS = {
    "consultado": "bool", "nota": "texto",
    "motivo": ("opcional", ("enum", MOTIVOS_COLETA)),
    "execucao_id": ("opcional", "texto?"), "origem": ("opcional", "texto?"), "status_execucao": ("opcional", "texto?"),
    "iniciada_em": ("opcional", "data_hora?"), "finalizada_em": ("opcional", "data_hora?"),
    "entrega_concluida_em": ("opcional", "data_hora?"),
    "etapas": ("opcional", {e: ("opcional", "texto?") for e in _ETAPAS_COLETA}),
    "consultas": ("opcional", "inteiro"), "espera_segundos": ("opcional", "inteiro"),
    "primeira_consulta_em": ("opcional", "data_hora?"), "ultima_consulta_em": ("opcional", "data_hora?"),
    "prazo": ("opcional", "data_hora?"),
    "t_esperado": ("opcional", "data?"), "ultimo_pregao_lido": ("opcional", "data?"),
}

# Um esquema por pacote, exatamente os campos da seção 4 do plano (`series_diarias` fica de fora: validar_serie).
ESQUEMAS: dict[str, dict] = {
    "acoes": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "ticker": "texto", "empresa": "texto?", "setor": "texto?", "subsetor": "texto?",
        "tipo_acao": ("enum", ("ON", "PN", "UNIT", "BDR")), "ativo_no_universo": "bool",
    },
    "mercado_dia": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "data_referencia": "data", "IBOV": _COTACAO, "USDBRL": _COTACAO, "BRENT": _COTACAO,
        "cdi_dia": "folha", "cdi_data": "data?", "ipca_12m": "folha", "ipca_ate": "folha_texto",
        "indices": {k: _JANELAS for k in ("CDI", "IPCA", "IDIV", "SMLL", "IFIX", "IVVB11")},
    },
    "resumo_acao": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "data_referencia": "data", "ticker": "texto",
        "cotacao": {"fechamento": "folha", "variacao_dia": "folha"},
        "variacao_preco": _JANELAS,
        "rentabilidade": {**_JANELAS, "ibov": _JANELAS, "setor": _JANELAS},
        "volume": {"total": "folha", "relativo": _TEXTO, "mediana_20": "folha", "posicao_pct": "folha"},
        "volatilidade_20d": ("folha+", {"texto": "texto?", "posicao_pct": "folha"}),
        "beta": _TEXTO,
        "pl": ("folha+", {"texto": "texto?", "setor": "folha"}),
        "pvp": _SETOR, "roe": _SETOR, "dividend_yield": _SETOR, "payout": _SETOR,
        "margem_bruta": _SETOR, "margem_liquida": _SETOR,
        "payout_por_ano": ("lista", _ANO),
        "proventos_por_ano": ("lista", _ANO),
        "ebitda": {"rotulo": "texto", "valor_12m": "folha", "margem": "folha", "setor_margem": "folha"},
        "endividamento": {
            "divida_liquida": "folha", "dl_pl": "folha", "dl_ebitda": "folha", "caixa_liquido": "folha_bool",
            "setor_dl_pl": "folha", "setor_dl_ebitda": "folha", "aviso": "texto",
        },
        "setor_comparacao_fraca": "bool",
        "balanco_referencia": {"data_fim_periodo": "data?", "data_entrega": "data?", "status": _STATUS_ENUM},
    },
    "fundamentos_trimestrais": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "ticker": "texto", "data_fim_periodo": "data", "data_entrega": "data",
        **{c: "folha" for c in _CAMPOS_TRIMESTRAIS},
    },
    "proventos": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "ticker": "texto", "tipo": ("enum", ("DIVIDENDO", "JCP")), "data_com": "data",
        "data_pagamento": "folha_data", "valor_por_acao": "folha",
    },
    "noticias_dia": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "data_referencia": "data", "ticker": "texto", "janela_inicio": "data_hora", "janela_fim": "data_hora",
        "resumo": {"quantidade": "folha", "positivas": "folha", "neutras": "folha", "negativas": "folha",
                   "tom_medio": "folha"},
        "itens": ("lista", _ITEM_NOTICIA),
    },
    "experimento_top": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "data_referencia": "data", "pregao_previsto": "data", "pregao_base": "data",
        "valido_para_historico": "bool", "modelo_versao": "modelo", "modelo_provisorio": "bool",
        "universo": "texto", "n_candidatas": "inteiro", "selo": ("enum", ("em_avaliacao",)),
        "titulo": "texto", "aviso_fixo": "texto", "avisos": ("lista", "texto"),
        "ranking": ("lista", {
            "posicao": "inteiro", "ticker": "texto", "chance": "chance",
            "motivos": ("lista", {"fator": "texto", "valor": "numero?",
                                  "efeito": ("enum", ("ajudou", "atrapalhou", "neutro")), "texto": "texto"}),
            "noticias_usadas": ("lista", "texto"),
        }),
    },
    "experimento_historico": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "data_referencia": "data", "dia": ("ou_nulo", _DIA_HISTORICO),
        "resumo": {
            "periodo_inicio": "data?", "periodo_fim": "data?", "n_dias": "inteiro", "taxa_acerto": "folha",
            "acaso_media": "folha", "acaso_faixa": ("ou_nulo", ("lista", "numero")), "universo": "texto",
            "nota": "texto",
        },
    },
    "execucao": {
        **{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
        "data_referencia": "data", "rodada": "inteiro", "inicio": "data_hora", "fim": ("ou_nulo", "data_hora"),
        "status": ("enum", ("em_andamento", "ok", "parcial", "falhou")),
        "coleta_status": _COLETA_STATUS,
        "pacotes_enviados": ("lista", {"pacote": ("enum", PACOTES), "arquivo": "texto",
                                        "registros": "inteiro", "removidos": "inteiro"}),
        "avisos": ("lista", "texto"),
    },
}


def _rotulo(pacote: str, registro: dict) -> str:
    """Caminho inicial das mensagens: `pacote[chave]` (sem a data de referência, que é a mesma do lote)."""
    if not isinstance(registro, dict):
        return pacote
    partes = [str(registro[c]) for c in CHAVES[pacote] if c != "data_referencia" and c in registro]
    return f"{pacote}[{'/'.join(partes)}]" if partes else pacote


def _exigir_chaves(objeto: object, esperadas: tuple | list, caminho: str) -> None:
    """Campos exatos de um objeto: campo a mais ou faltando é erro."""
    if not isinstance(objeto, dict):
        raise _erro(caminho, "deveria ser um objeto")
    for campo in objeto:
        if campo not in esperadas:
            raise _erro(f"{caminho}.{campo}", "campo desconhecido")
    for campo in esperadas:
        if campo not in objeto:
            raise _erro(f"{caminho}.{campo}", "campo obrigatório ausente")


def validar(pacote: str, registro: dict) -> None:
    """Confere um registro contra o esquema do pacote. Levanta `ErroContrato` com o caminho do campo."""
    if pacote == "series_diarias":
        validar_serie(registro)
        return
    if pacote not in ESQUEMAS:
        raise ErroContrato(f"pacote desconhecido: {pacote!r}")
    _checar(ESQUEMAS[pacote], registro, _rotulo(pacote, registro))


def trechos(datas: list, status_por_ponto: list[str]) -> list[dict]:
    """Agrupa posições seguidas com o mesmo status (≠ ok) em `{de, ate, status}`."""
    if len(datas) != len(status_por_ponto):
        raise ValueError("datas e status_por_ponto com tamanhos diferentes")
    datas_txt = [data_txt(d) for d in datas]
    resultado: list[dict] = []
    i = 0
    n = len(datas_txt)
    while i < n:
        st = status_por_ponto[i]
        if st == "ok":
            i += 1
            continue
        j = i
        while j + 1 < n and status_por_ponto[j + 1] == st:
            j += 1
        resultado.append({"de": datas_txt[i], "ate": datas_txt[j], "status": st})
        i = j + 1
    return resultado


def validar_serie(registro: dict) -> None:
    """Confere uma série do `series_diarias` no formato compacto (seção 4.4 do plano)."""
    if not isinstance(registro, dict):
        raise ErroContrato("series_diarias: o registro deve ser um objeto")
    rotulo = f"series_diarias[{registro.get('ticker')}]"
    topo = {**{c: "versao" if c == "versao_contrato" else "data_hora" for c in _META_CAMPOS},
            "ticker": "texto", "tipo": ("enum", tuple(CAMPOS_SERIE)), "nome": "texto",
            "substituir_serie": "bool", "inicio_janela": "data", "datas": ("lista", "data"),
            "valores": "objeto", "status": "objeto"}
    _checar(topo, registro, rotulo)
    campos = CAMPOS_SERIE[registro["tipo"]]
    datas = registro["datas"]
    if not datas:
        raise _erro(f"{rotulo}.datas", "série sem pontos (não se emite série vazia)")
    for i in range(1, len(datas)):
        if datas[i] <= datas[i - 1]:
            raise _erro(f"{rotulo}.datas", f"datas fora de ordem ou repetidas ({datas[i - 1]}, {datas[i]})")
    if datas[0] < registro["inicio_janela"]:
        raise _erro(f"{rotulo}.datas", f"data {datas[0]} anterior a inicio_janela {registro['inicio_janela']}")
    limite = registro["dados_ate"][:10]
    if datas[-1] >= limite:
        raise _erro(f"{rotulo}.datas", f"data {datas[-1]} não é anterior à rodada ({limite}): vazamento")
    n = len(datas)
    indice = {d: i for i, d in enumerate(datas)}
    valores = registro["valores"]
    _exigir_chaves(valores, campos, f"{rotulo}.valores")
    for campo in campos:
        if not isinstance(valores[campo], list) or len(valores[campo]) != n:
            raise _erro(f"{rotulo}.valores.{campo}", f"deveria ter {n} valores (um por data)")
    estados = {campo: ["ok"] * n for campo in campos}
    status = registro["status"]
    for campo, trechos_campo in status.items():
        caminho = f"{rotulo}.status.{campo}"
        if campo not in campos:
            raise _erro(caminho, "campo desconhecido nesta série")
        if campo == "n_empresas":
            raise _erro(caminho, "n_empresas nunca tem status (0 quando nenhuma empresa entrou)")
        if not isinstance(trechos_campo, list):
            raise _erro(caminho, "deveria ser uma lista de trechos")
        fim_anterior = -1
        for k, trecho in enumerate(trechos_campo):
            cam_t = f"{caminho}[{k}]"
            _exigir_chaves(trecho, ("de", "ate", "status"), cam_t)
            if trecho["status"] not in STATUS or trecho["status"] == "ok":
                raise _erro(cam_t, f"status de trecho inválido: {trecho['status']!r}")
            for chave_data in ("de", "ate"):
                if trecho[chave_data] not in indice:
                    raise _erro(f"{cam_t}.{chave_data}", f"data {trecho[chave_data]!r} não está em datas")
            i0, i1 = indice[trecho["de"]], indice[trecho["ate"]]
            if i1 < i0:
                raise _erro(cam_t, "trecho com 'ate' antes de 'de'")
            if i0 <= fim_anterior:
                raise _erro(cam_t, "trechos sobrepostos ou fora de ordem")
            for p in range(i0, i1 + 1):
                estados[campo][p] = trecho["status"]
            fim_anterior = i1
    for campo in campos:
        lista = valores[campo]
        if campo == "n_empresas":
            for p, v in enumerate(lista):
                if isinstance(v, bool) or not isinstance(v, int):
                    raise _erro(f"{rotulo}.valores.{campo}[{p}]", "n_empresas deveria ser inteiro (0 se nenhuma)")
            continue
        for p, v in enumerate(lista):
            st = estados[campo][p]
            cam_p = f"{rotulo}.valores.{campo}[{p}]"
            if v is None:
                if st == "ok":
                    raise _erro(cam_p, "vazio sem trecho de status (informe o status)")
                continue
            _conferir_numero(v, cam_p)
            if v == 0 and st != "ok":
                raise _erro(cam_p, f"0 no lugar de vazio (status {st})")
            if st != "ok" and not (st == "lucro_negativo" and campo == "pl"):
                raise _erro(cam_p, f"valor numérico coberto por trecho de status {st}")


# ---------------------------------------------------------------- lote, gravação e "quando muda"

def _chave_registro(pacote: str) -> list[str]:
    """Campos que identificam um registro (na série, o registro é o ticker)."""
    return ["ticker"] if pacote == "series_diarias" else CHAVES[pacote]


def validar_lote(lote: dict) -> None:
    """Confere o envelope (pacote, chave, instantes) e cada registro do lote."""
    _exigir_chaves(lote, _CAMPOS_LOTE, "lote")
    pacote = lote["pacote"]
    if pacote not in PACOTES:
        raise ErroContrato(f"pacote desconhecido: {pacote!r}")
    _checar("versao", lote["versao_contrato"], f"{pacote}.versao_contrato")
    if list(lote["chave"]) != CHAVES[pacote]:
        raise ErroContrato(f"{pacote}: chave {lote['chave']} diferente de {CHAVES[pacote]}")
    _checar_tipo("data_hora", lote["gerado_em"], f"{pacote}.gerado_em")
    _checar_tipo("data_hora", lote["dados_ate"], f"{pacote}.dados_ate")
    if not isinstance(lote["registros"], list):
        raise ErroContrato(f"{pacote}.registros deveria ser uma lista")
    vistos: set[tuple] = set()
    for r in lote["registros"]:
        validar(pacote, r)
        chave_reg = tuple(r[c] for c in _chave_registro(pacote))
        if chave_reg in vistos:
            raise ErroContrato(f"{pacote}: registro repetido {chave_reg}")
        vistos.add(chave_reg)
    removidos = lote["removidos"]
    if not isinstance(removidos, list):
        raise ErroContrato(f"{pacote}.removidos deveria ser uma lista")
    if removidos and pacote not in QUANDO_MUDA:
        raise ErroContrato(f"{pacote}: removidos só existe nos pacotes 'quando muda'")
    for k, item in enumerate(removidos):
        if not isinstance(item, dict) or set(item) != set(_chave_registro(pacote)):
            raise ErroContrato(f"{pacote}.removidos[{k}]: deveria ter só os campos {_chave_registro(pacote)}")


def lote(pacote: str, registros: list[dict], gerado_em: str, dados_ate: str, removidos: list | tuple = ()) -> dict:
    """Envelope de um pacote: `pacote`, `versao_contrato`, `chave`, instantes, registros e removidos."""
    return {
        "pacote": pacote, "versao_contrato": VERSAO_CONTRATO, "chave": list(CHAVES.get(pacote, [])),
        "gerado_em": gerado_em, "dados_ate": dados_ate,
        "registros": list(registros), "removidos": list(removidos),
    }


def _gravar_atomico(arquivo: Path, texto: str) -> None:
    """Grava em `<nome>.tmp` e renomeia: nunca deixa arquivo pela metade."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_name(arquivo.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    os.replace(tmp, arquivo)


def gravar_lote(pasta: Path, lote: dict, compacto: bool = False) -> Path:
    """Valida o lote e grava `<pacote>.json` em `pasta` (UTF-8). Sem NaN; compacto só no series_diarias."""
    validar_lote(lote)
    texto = json.dumps(
        lote, ensure_ascii=False, allow_nan=False,
        indent=None if compacto else 2,
        separators=(",", ":") if compacto else None,
    )
    arquivo = Path(pasta) / f"{lote['pacote']}.json"
    _gravar_atomico(arquivo, texto)
    return arquivo


_CAMPOS_NAO_COMPARADOS = ("versao_contrato", "gerado_em", "dados_ate")


def _iguais(x: object, y: object) -> bool:
    """Igualdade do conteúdo: números com tolerância (rel 1e-9, abs 1e-12); bool não se confunde com número."""
    if isinstance(x, dict) and isinstance(y, dict):
        return set(x) == set(y) and all(_iguais(x[k], y[k]) for k in x)
    if isinstance(x, list) and isinstance(y, list):
        return len(x) == len(y) and all(_iguais(a, b) for a, b in zip(x, y, strict=True))
    if isinstance(x, bool) or isinstance(y, bool):
        return type(x) is type(y) and x == y
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)
    return x == y


def comparar_registros(atuais: list[dict], estado: list[dict] | None,
                       chave: list[str]) -> tuple[list[dict], list[dict]]:
    """Devolve (a_enviar, removidos) frente ao último envio. `estado None` = primeira vez: manda tudo."""
    if estado is None:
        return list(atuais), []
    mapa_estado = {tuple(r[c] for c in chave): r for r in estado}
    chaves_atuais: set[tuple] = set()
    a_enviar: list[dict] = []
    for r in atuais:
        k = tuple(r[c] for c in chave)
        chaves_atuais.add(k)
        anterior = mapa_estado.get(k)
        if anterior is None or not _iguais(
            {c: v for c, v in r.items() if c not in _CAMPOS_NAO_COMPARADOS},
            {c: v for c, v in anterior.items() if c not in _CAMPOS_NAO_COMPARADOS},
        ):
            a_enviar.append(r)
    removidos = [dict(zip(chave, k, strict=True)) for k in mapa_estado if k not in chaves_atuais]
    return a_enviar, removidos


def ler_estado(pasta: Path | None, pacote: str) -> list[dict] | None:
    """Último envio do pacote (lista de registros), ou None se não há estado (ou `pasta` é None)."""
    if pasta is None:
        return None
    arquivo = Path(pasta) / f"{pacote}.json"
    if not arquivo.exists():
        return None
    return json.loads(arquivo.read_text(encoding="utf-8"))


def gravar_estado(pasta: Path | None, pacote: str, registros: list[dict]) -> None:
    """Regrava o estado do pacote logo depois do envio. `pasta` None = não grava."""
    if pasta is None:
        return
    texto = json.dumps(registros, ensure_ascii=False, allow_nan=False)
    _gravar_atomico(Path(pasta) / f"{pacote}.json", texto)
