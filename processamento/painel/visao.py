"""Dados da tela "Sala de Operação": fluxo do dia, linha do tempo, carga completa e calendário.

Só monta dicionários a partir de itens já lidos por leitores.py e do calendário. Nada de banco,
rede ou escrita. Ausência vira None ou "sem dados", nunca 0 inventado.
"""

from __future__ import annotations

import calendar as _cal
import re
from datetime import date, datetime, time

import yaml

from processamento import calendario
from processamento.calendario import SP
from processamento.painel.leitores import _instante, formatar_duracao

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
DIAS_CURTOS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
ROTULOS_TEMPO = {"coleta_inicio": "coleta começa", "entrega": "coleta entrega", "rotina_inicio": "rotina começa",
                 "rotina_fim": "pacotes prontos", "prazo": "prazo da rotina", "abertura": "bolsa abre"}
ERROS_CAL = (calendario.ErroCalendario, OSError, ValueError, yaml.YAMLError)
RE_HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
ESTADOS_PROCESSAMENTO = {"ok": ("ok", "Calculado e validado"), "parcial": ("warn", "Gerado com pendências"),
                         "falhou": ("bad", "Falhou"), "em_andamento": ("idle", "Em andamento")}


def dia_curto(d: date) -> str:
    """Dia da semana e data curtos: "sex 23/10"."""
    return f"{DIAS_CURTOS[d.weekday()]} {d:%d/%m}"


def _sp(txt: object) -> datetime | None:
    """Instante ISO convertido para São Paulo; None se vazio ou inválido."""
    instante = _instante(txt)
    return None if instante is None else instante.astimezone(SP)


def _data(txt: object) -> date | None:
    """Data ISO (AAAA-MM-DD); None se inválida."""
    try:
        return date.fromisoformat(txt)
    except (TypeError, ValueError):
        return None


def quando(iso: str | None) -> str | None:
    """Dia e hora em São Paulo: "sex 23/10 08:00"; None se vazio ou inválido."""
    inst = _sp(iso)
    if inst is None:
        return None
    return f"{dia_curto(inst.date())} {inst:%H:%M}"


def _bloco_coleta(item: dict) -> dict:
    """Estado da coleta da rotina diária, com dia, resumo e etapas."""
    coleta = item.get("coleta")
    if not isinstance(coleta, dict):
        coleta = {}
    ci = _sp(coleta.get("iniciada_em"))
    en = _sp(coleta.get("entrega_concluida_em"))
    motivo = coleta.get("motivo")

    if not coleta or coleta.get("consultado") is False:
        estado, titulo = "idle", "Coleta não consultada"
    elif motivo == "entrega_concluida" or coleta.get("entrega_concluida_em"):
        estado, titulo = "ok", "Dados entregues"
    elif motivo in ("entrega_falhou", "falha_consulta"):
        estado, titulo = "bad", "Entrega com problema"
    else:
        estado, titulo = "warn", "Entrega não concluída"

    etapas = coleta.get("etapas")
    etapas_total = etapas_concluidas = None
    if isinstance(etapas, dict) and etapas:
        status = [v.get("status") if isinstance(v, dict) else v for v in etapas.values()]
        etapas_total = len(status)
        etapas_concluidas = sum(1 for s in status if s == "concluida")

    dia = dia_curto(ci.date()) if ci is not None else None
    if ci is None:
        resumo = "sem dados"
    else:
        if en is None:
            trecho = "entrega não concluída"
        elif en.date() != ci.date():
            trecho = f"entregou {quando(coleta.get('entrega_concluida_em'))}"
        else:
            trecho = f"entregou {en:%H:%M}"
        resumo = f"{dia} · começou {ci:%H:%M} · {trecho}"

    return {"estado": estado, "titulo": titulo, "dia": dia, "resumo": resumo,
            "inicio_hhmm": coleta.get("iniciada_hhmm") or (None if ci is None else f"{ci:%H:%M}"),
            "entrega_hhmm": coleta.get("entrega_hhmm") or (None if en is None else f"{en:%H:%M}"),
            "etapas_concluidas": etapas_concluidas, "etapas_total": etapas_total,
            "nota": coleta.get("motivo_texto") or coleta.get("nota"), "daily": coleta.get("daily")}


def _bloco_processamento(item: dict) -> dict:
    """Estado do processamento (rotina diária): status, rótulo e quando."""
    status = item.get("status")
    estado, titulo = ESTADOS_PROCESSAMENTO.get(status, ("idle", status or "sem dados"))
    pacotes = item.get("pacotes") or []
    n_acoes = next((p.get("registros") for p in pacotes
                    if isinstance(p, dict) and p.get("pacote") == "resumo_acao"), None)

    inicio, fim = item.get("inicio"), item.get("fim")
    ini, fi = _sp(inicio), _sp(fim)
    rodada = item.get("rodada")
    if ini is None:
        rotulo = f"última rotina diária · rodada {rodada} · sem dados"
        quando_txt = None
    else:
        rotulo = f"última rotina diária · rodada {rodada} · de {ini:%d/%m %H:%M}"
        qi = quando(inicio)
        if fi is None:
            quando_txt = qi
        elif fi.date() != ini.date():
            quando_txt = quando(fim)
        else:
            quando_txt = f"{qi} → {fi:%H:%M}"

    return {"estado": estado, "titulo": titulo, "duracao_texto": item.get("duracao_texto"),
            "n_acoes": n_acoes, "n_avisos": item.get("n_avisos"), "rodada": rodada,
            "inicio": inicio, "fim": fim, "rotulo": rotulo, "quando": quando_txt}


def _bloco_interface(item: dict) -> dict:
    """Pacotes prontos para a interface (saida/)."""
    n = item.get("n_pacotes") or 0
    if n > 0:
        estado = "ok"
    elif item.get("status") == "falhou":
        estado = "bad"
    else:
        estado = "idle"
    if n == 0:
        titulo = "Nenhum pacote"
    elif n == 1:
        titulo = "1 pacote pronto"
    else:
        titulo = f"{n} pacotes prontos"
    pacotes = item.get("pacotes") or []
    registros_total = sum(p.get("registros") for p in pacotes
                          if isinstance(p, dict) and isinstance(p.get("registros"), int)
                          and not isinstance(p.get("registros"), bool))
    return {"estado": estado, "titulo": titulo, "n_pacotes": n,
            "versao_contrato": item.get("versao_contrato"), "registros_total": registros_total}


def _bloco_carga(completa: dict | None) -> dict:
    """Última carga completa (saida_completa/), mostrada separada da rotina diária."""
    if not isinstance(completa, dict) or not completa.get("legivel"):
        return {"disponivel": False, "rotulo": "última carga completa: sem dados"}
    ini = _sp(completa.get("inicio"))
    quando_txt = "sem dados" if ini is None else f"{ini:%d/%m %H:%M}"
    n = completa.get("n_pacotes") or 0
    pacotes = "1 pacote" if n == 1 else f"{n} pacotes"
    return {"disponivel": True, "rodada": completa.get("rodada"), "status": completa.get("status"),
            "n_pacotes": n, "rotulo": f"última carga completa: {quando_txt} · {pacotes}"}


def fluxo(item: dict | None, completa: dict | None = None) -> dict:
    """Fluxo do dia: coleta, processamento e interface da última rotina diária, mais a última carga completa."""
    if item is None:
        return {"disponivel": False, "motivo": "Nenhuma execução encontrada em saida/."}
    if not item.get("legivel"):
        return {"disponivel": False, "motivo": f"Arquivo da última execução ilegível ({item.get('erro')})."}
    return {"disponivel": True, "data": item.get("data_referencia"), "status": item.get("status"),
            "possivelmente_interrompida": item.get("possivelmente_interrompida", False),
            "coleta": _bloco_coleta(item), "processamento": _bloco_processamento(item),
            "interface": _bloco_interface(item), "carga": _bloco_carga(completa)}


def _prazo(d: date, prazo_hhmm: object) -> datetime | None:
    """Prazo da rotina no dia d, em São Paulo; None se não for HH:MM válido."""
    if not isinstance(prazo_hhmm, str) or not RE_HHMM.fullmatch(prazo_hhmm):
        return None
    return datetime.combine(d, time.fromisoformat(prazo_hhmm), tzinfo=SP)


def linha_do_tempo(item: dict | None, prazo_hhmm: str | None, caminho_calendario: str | None = None) -> dict:
    """Marcos e trechos da manhã do pregão (coleta, processamento, folga até o prazo)."""
    sem_dados = {"disponivel": False, "motivo": "Nenhuma rotina diária para mostrar."}
    if not isinstance(item, dict) or not item.get("legivel") or item.get("tipo") != "diaria":
        return sem_dados
    d = _data(item.get("data_referencia"))
    if d is None:
        return sem_dados

    avisos = []
    coleta = item.get("coleta") if isinstance(item.get("coleta"), dict) else {}

    def no_dia(txt: object) -> datetime | None:
        inst = _sp(txt)
        return inst if inst is not None and inst.date() == d else None

    pontos = {"coleta_inicio": no_dia(coleta.get("iniciada_em")),
              "entrega": no_dia(coleta.get("entrega_concluida_em")),
              "rotina_inicio": no_dia(item.get("inicio")),
              "rotina_fim": no_dia(item.get("fim")),
              "prazo": _prazo(d, prazo_hhmm)}
    try:
        abertura, _ = calendario.horario_b3(d, caminho_calendario)
        pontos["abertura"] = datetime.combine(d, abertura, tzinfo=SP)
    except ERROS_CAL as erro:
        avisos.append(f"Horário da B3 indisponível: {erro}")

    minutos = {k: v.hour * 60 + v.minute for k, v in pontos.items() if v is not None}
    marcos = [{"id": k, "rotulo": ROTULOS_TEMPO[k], "hora": f"{pontos[k]:%H:%M}", "minuto": minutos[k]}
              for k in pontos if k in minutos]
    marcos.sort(key=lambda m: m["minuto"])

    trechos = []
    if "coleta_inicio" in minutos and "entrega" in minutos and minutos["entrega"] >= minutos["coleta_inicio"]:
        trechos.append({"id": "coleta", "de": minutos["coleta_inicio"], "ate": minutos["entrega"]})
    if "rotina_inicio" in minutos and "rotina_fim" in minutos and minutos["rotina_fim"] >= minutos["rotina_inicio"]:
        trechos.append({"id": "processamento", "de": minutos["rotina_inicio"], "ate": minutos["rotina_fim"]})
    if "rotina_fim" in minutos and "prazo" in minutos and minutos["prazo"] > minutos["rotina_fim"]:
        trechos.append({"id": "folga", "de": minutos["rotina_fim"], "ate": minutos["prazo"]})

    folga_s = None
    if pontos["rotina_fim"] is not None and pontos["prazo"] is not None:
        folga_s = int((pontos["prazo"] - pontos["rotina_fim"]).total_seconds())
    if folga_s is None:
        folga_texto = None
    elif folga_s >= 0:
        folga_texto = formatar_duracao(folga_s)
    else:
        folga_texto = "atraso de " + formatar_duracao(-folga_s)

    inicio = _sp(item.get("inicio"))
    if inicio is not None and inicio.date() != d:
        avisos.append(f"A rotina deste pregão rodou em {inicio:%d/%m/%Y %H:%M}, "
                      "fora da manhã do pregão: sem folga a medir.")

    eixo = {"de": min(minutos.values()) - 5, "ate": max(minutos.values()) + 5} if minutos else None
    return {"disponivel": True, "data": d.isoformat(), "dia_rotulo": f"{dia_curto(d)}/{d.year}",
            "marcos": marcos, "trechos": trechos, "eixo": eixo, "folga_s": folga_s,
            "folga_texto": folga_texto, "avisos": avisos}


def _pregao(d: date, caminho_calendario: str | None) -> tuple[bool | None, str | None]:
    """(pregão?, motivo de não ser pregão); (None, None) se o calendário não puder responder."""
    try:
        motivo = calendario.motivo_sem_pregao(d, caminho_calendario)
    except ERROS_CAL:
        return None, None
    return motivo is None, motivo


def calendario_meses(diarias: list[dict], completas: list[dict], hoje_iso: str,
                     caminho_calendario: str | None = None, max_meses: int = 12) -> list[dict]:
    """Meses (mais novo primeiro) com os dias úteis, a situação de cada um e se há carga completa."""
    diaria_por_data = {}
    for item in diarias or []:
        d = _data(item.get("data_referencia"))
        if d is not None:
            diaria_por_data[d] = item
    completa_datas = set()
    for item in completas or []:
        d = _data(item.get("data_referencia"))
        if d is not None:
            completa_datas.add(d)

    meses = {(d.year, d.month) for d in list(diaria_por_data) + list(completa_datas)}
    hoje = _data(hoje_iso)
    if hoje is not None:
        meses.add((hoje.year, hoje.month))

    saida = []
    for ano, mes in sorted(meses, reverse=True)[:max_meses]:
        dias = []
        for dia_num in range(1, _cal.monthrange(ano, mes)[1] + 1):
            d = date(ano, mes, dia_num)
            if d.weekday() >= 5:
                continue
            pregao, motivo = _pregao(d, caminho_calendario)
            item = diaria_por_data.get(d)
            status = None
            if item is not None:
                status = "ilegivel" if not item.get("legivel") else item.get("status")
            dias.append({"data": d.isoformat(), "dia": d.day, "dia_semana": d.weekday(), "pregao": pregao,
                         "motivo": motivo, "status": status, "completa": d in completa_datas})
        saida.append({"ano": ano, "mes": mes, "titulo": f"{MESES[mes - 1]} de {ano}", "dias": dias})
    return saida
