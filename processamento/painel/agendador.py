"""Agendador de Tarefas (só leitura da chave `agendador` do painel.yaml): texto e próxima execução."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from processamento import calendario
from processamento.calendario import SP

DIAS_CURTOS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
INDICE = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}


def _texto_dias(dias_semana: list[int]) -> str:
    if dias_semana == [0, 1, 2, 3, 4]:
        return "seg a sex"
    if dias_semana == list(range(7)):
        return "todos os dias"
    return ", ".join(DIAS_CURTOS[i] for i in dias_semana)


def bloco_agendador(cfg: dict | None, agora: datetime, caminho_calendario: str | None = None) -> dict:
    """Texto do agendador e a próxima execução (informativo; o painel não cria nem confere a tarefa)."""
    if cfg is None:
        return {"configurado": False, "texto": "Agendador: não configurado",
                "detalhe": "Sem a chave agendador (dias e hora) em processamento/config/painel.yaml, ou com valor inválido.",
                "dias_semana": [], "hora": None, "proxima": None, "proxima_texto": None, "proxima_pregao": None}
    dias_semana = sorted({INDICE[d] for d in cfg["dias"]})
    hora = cfg["hora"]
    hh, mm = (int(p) for p in hora.split(":"))
    descricao = cfg.get("descricao") or None
    agora_sp = agora.astimezone(SP) if agora.tzinfo else agora.replace(tzinfo=SP)
    alvo = None
    for deslocamento in range(8):
        dia = agora_sp.date() + timedelta(days=deslocamento)
        if dia.weekday() not in dias_semana:
            continue
        candidato = datetime.combine(dia, time(hh, mm), tzinfo=SP)
        if candidato > agora_sp:
            alvo = candidato
            break
    wd = alvo.weekday()
    try:
        motivo = calendario.motivo_sem_pregao(alvo.date(), caminho_calendario)
        proxima_pregao = motivo is None
    except (calendario.ErroCalendario, OSError, ValueError):
        motivo, proxima_pregao = None, None
    if proxima_pregao is False:
        detalhe = (f"{descricao} · " if descricao else "") + (
            f"A próxima execução cai em dia sem pregão ({motivo}): a rotina roda, mas não gera nada.")
    else:
        detalhe = descricao
    return {"configurado": True,
            "texto": f"Agendador: {_texto_dias(dias_semana)}, {hora} · próxima {DIAS_CURTOS[wd]} {alvo:%d/%m}",
            "detalhe": detalhe, "dias_semana": dias_semana, "hora": hora,
            "proxima": alvo.isoformat(timespec="seconds"),
            "proxima_texto": f"{DIAS_CURTOS[wd]} {alvo:%d/%m} {hora}",
            "proxima_pregao": proxima_pregao}
