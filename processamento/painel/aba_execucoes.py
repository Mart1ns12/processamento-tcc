"""Aba Execuções do painel: dias completos (logs/painel/dia-*.log) com as três etapas, duração e log da última execução.

Só lê a pasta de logs do painel (nada de caminho vindo do navegador). Log antigo, que só traz a hora do início de cada
etapa, ganha um fim aproximado (início da etapa seguinte ou rodapé do painel) e vem marcado como aproximada.
Arquivo ausente ou ilegível vira ausência, nunca exceção.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from processamento.calendario import SP
from processamento.painel.leitores import _instante, formatar_duracao
from processamento.painel.marcos import ROTULOS_PROGRESSO, marcos_dia
from processamento.painel.relatorios import (
    IDS_ETAPAS_DIA,
    RE_DIA_FIM,
    RE_DIA_INICIO,
    _arquivos_da_acao,
    _cabecalho_rodape,
    _ler_texto,
)

RE_CABECALHO_DIA = re.compile(r"^# painel: acao=dia inicio=\S+ comando=.*--data (\d{4}-\d{2}-\d{2})")
RE_RESULTADO = re.compile(r"^# dia: resultado=(\w+) (.*)$")
RE_HORA = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")
MAX_LINHAS_LOG = 400
FONTE = "logs/painel/dia-*.log (o painel guarda os 20 mais recentes)"
TEXTO_SEM_DURACAO = {"pulada": "pulada", "erro": "erro", "agora": "em andamento", "espera": "não começou"}


def ler_logs_dia(pasta_logs_painel: Path, max_arquivos: int = 20) -> list[dict]:
    """[{"arquivo","data","inicio","fim","codigo","parado","linhas"}], do log mais novo para o mais antigo."""
    if not pasta_logs_painel.is_dir():
        return []
    logs = []
    for arquivo in _arquivos_da_acao(pasta_logs_painel, "dia", max_arquivos):
        linhas = _ler_texto(arquivo).splitlines()
        inicio, fim, codigo, parado = _cabecalho_rodape(linhas)
        data = None
        for linha in linhas:
            m = RE_CABECALHO_DIA.match(linha)
            if m:
                data = m.group(1)
                break
        logs.append({"arquivo": arquivo.name, "data": data, "inicio": inicio, "fim": fim,
                     "codigo": codigo, "parado": parado, "linhas": linhas})
    return logs


def _instante_do_inicio(texto: str, base: datetime | None) -> datetime | None:
    """Início de uma etapa: ISO com fuso, ou só a hora (HH:MM:SS) no dia do cabeçalho (dia seguinte se cruzar a meia-noite)."""
    instante = _instante(texto)
    if instante is not None:
        return instante
    m = RE_HORA.match(texto)
    if m is None or base is None:
        return None
    t = base.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=int(m.group(3)), microsecond=0)
    if t < base - timedelta(seconds=60):
        t += timedelta(days=1)
    return t


def etapas_do_log(log: dict) -> list[dict]:
    """Rotina, carga e publicador do log: estado, detalhe, duração e se o fim é aproximado."""
    linhas = log["linhas"]
    base = _instante(log["inicio"])
    estados = {e["id"]: e for e in marcos_dia(linhas, rodando=log["fim"] is None, codigo=log["codigo"],
                                              significado=None) if e["id"] != "fim"}
    inicios: dict[str, datetime | None] = {}
    fins: dict[str, datetime | None] = {}
    for linha in linhas:
        m = RE_DIA_INICIO.match(linha)
        if m and m.group(1) in IDS_ETAPAS_DIA:
            inicios[m.group(1)] = _instante_do_inicio(m.group(2), base)
            continue
        m = RE_DIA_FIM.match(linha)
        if m and m.group(1) in IDS_ETAPAS_DIA and m.group(3):
            fins[m.group(1)] = _instante(m.group(3))

    rodape = _instante(log["fim"])
    itens = []
    for id_etapa in IDS_ETAPAS_DIA:
        est = estados.get(id_etapa)
        if est is None:
            continue
        ini = inicios.get(id_etapa)
        fim = fins.get(id_etapa)
        aproximada = False
        if fim is None and est["estado"] in ("concluida", "erro") and ini is not None:
            posteriores = [t for outro, t in inicios.items() if outro != id_etapa and t is not None and t > ini]
            fim = min(posteriores, default=rodape)
            aproximada = fim is not None
        duracao = int((fim - ini).total_seconds()) if ini is not None and fim is not None and fim >= ini else None
        texto = formatar_duracao(duracao) if duracao is not None else TEXTO_SEM_DURACAO.get(est["estado"], "sem dados")
        itens.append({"id": id_etapa, "rotulo": ROTULOS_PROGRESSO[id_etapa], "estado": est["estado"],
                      "detalhe": est["detalhe"], "duracao_s": duracao, "duracao_texto": texto,
                      "aproximada": aproximada})
    return itens


def _resumo_dia(log: dict, execucoes: int) -> dict:
    etapas = etapas_do_log(log)
    resultado = resultado_texto = None
    for linha in log["linhas"]:
        m = RE_RESULTADO.match(linha)
        if m:
            resultado, resultado_texto = m.group(1), m.group(2)
    ini = _instante(log["inicio"])
    fim = _instante(log["fim"])
    duracoes = [e["duracao_s"] for e in etapas if e["duracao_s"] is not None]
    return {"data": log["data"], "arquivo": log["arquivo"],
            "inicio_hhmm": ini.astimezone(SP).strftime("%H:%M") if ini is not None else None,
            "fim_hhmm": fim.astimezone(SP).strftime("%H:%M") if fim is not None else None,
            "codigo": log["codigo"], "resultado": resultado, "resultado_texto": resultado_texto,
            "etapas": etapas, "maximo_s": max(duracoes, default=None),
            "aproximada": any(e["aproximada"] for e in etapas), "execucoes_no_dia": execucoes}


def _titulo_do_log(log: dict) -> str:
    ini = _instante(log["inicio"])
    if ini is None:
        return log["arquivo"]
    ini = ini.astimezone(SP)
    txt = f"{ini:%d/%m} · {ini:%H:%M} → "
    fim = _instante(log["fim"])
    if fim is None:
        return txt + "em andamento ou interrompido"
    return txt + f"{fim.astimezone(SP):%H:%M}"


def bloco_execucoes(logs: list[dict], max_linhas: int = MAX_LINHAS_LOG) -> dict:
    """Bloco da aba Execuções: um resumo por dia (o log mais novo da data) e o log da última execução."""
    if not logs:
        return {"disponivel": False,
                "motivo": "Nenhum dia completo rodado pelo painel ainda (logs/painel/dia-*.log).",
                "fonte": FONTE, "dias": {}, "ultimo_log": None}
    contagem = Counter(log["data"] for log in logs if log["data"])
    dias: dict[str, dict] = {}
    for log in logs:
        data = log["data"]
        if data is None or data in dias:
            continue
        dias[data] = _resumo_dia(log, contagem[data])
    ultimo = logs[0]
    linhas = ultimo["linhas"]
    mantidas = linhas[-max_linhas:] if max_linhas > 0 else []
    return {"disponivel": True, "motivo": None, "fonte": FONTE, "dias": dias,
            "ultimo_log": {"arquivo": ultimo["arquivo"], "data": ultimo["data"], "titulo": _titulo_do_log(ultimo),
                           "linhas": mantidas, "cortadas": len(linhas) - len(mantidas)}}
