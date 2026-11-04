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
from processamento.painel.acoes import ACOES
from processamento.painel.ajuda import O_QUE_FAZER
from processamento.painel.api import resumo_tempos
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


TEXTO_SEM_MEDICAO = "Ainda sem medição: pode levar alguns minutos."
ROTULO_EXECUCAO = {"rotina": "A última rotina diária", "carga": "A última carga completa"}
DIAS_LONGOS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _dic(valor: object) -> dict:
    return valor if isinstance(valor, dict) else {}


def _inteiro(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _ponto(nivel: str, texto: str, alvo: str, chave: str) -> dict:
    return {"nivel": nivel, "texto": texto, "alvo": alvo, "o_que_fazer": O_QUE_FAZER.get(chave)}


ROTULOS_ETAPA = {"precos": "preços", "macro": "macro", "noticias": "notícias", "ipe": "IPE",
                 "enriquecimento": "enriquecimento", "juiza": "juíza", "cadastro": "cadastro", "entrega": "entrega",
                 "analise": "análise"}
TEXTO_ETAPA = {"concluida": "concluída", "falhou": "falhou", "pulada": "pulada", "em_andamento": "em andamento"}


def _real(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _data_de(valor: object) -> date | None:
    """Data de um date, de um datetime ou de texto AAAA-MM-DD; None se inválida."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return _data(valor)


def _dd_mm_aaaa(valor: object) -> str | None:
    d = _data_de(valor)
    return None if d is None else f"{d:%d/%m/%Y}"


def etapas_coleta(item: object) -> dict:
    """Etapas do daily da coleta, com a situação de cada uma na consulta da rotina (foto do execucao.json)."""
    coleta = _dic(_dic(item).get("coleta"))
    consulta_hhmm, daily = coleta.get("consulta_hhmm"), coleta.get("daily")
    etapas = coleta.get("etapas")
    if not (isinstance(etapas, dict) and etapas):
        motivo = coleta.get("nota") or coleta.get("motivo_texto") or "Coleta não consultada."
        return {"disponivel": False, "motivo": motivo, "consulta_hhmm": consulta_hhmm, "daily": daily,
                "etapas": [], "nao_concluidas": [], "resumo": None}
    lista = []
    for id_, valor in etapas.items():
        status = valor.get("status") if isinstance(valor, dict) else valor
        if not isinstance(status, str):
            status = None
        texto = "pendente" if status is None else TEXTO_ETAPA.get(status, status)
        lista.append({"id": id_, "rotulo": ROTULOS_ETAPA.get(id_, id_), "status": status, "texto": texto,
                      "destaque": status != "concluida"})
    nao = [f"{e['rotulo']} ({e['texto']})" for e in lista if e["destaque"]]
    concluidas = sum(1 for e in lista if e["status"] == "concluida")
    frase = f"{concluidas} de {len(lista)} etapas concluídas"
    if nao:
        frase += " · não concluíram: " + ", ".join(nao)
    return {"disponivel": True, "motivo": None, "consulta_hhmm": consulta_hhmm, "daily": daily,
            "etapas": lista, "nao_concluidas": nao, "resumo": frase}


def _banco_fora(consulta: dict) -> bool:
    """A API respondeu, mas diz que o banco dela não responde (HTTP 503 ou banco diferente de "ok")."""
    return consulta.get("http") == 503 or consulta.get("banco") != "ok"


def _ponto_api(nivel: str, texto: str, chave: str) -> dict:
    return {"nivel": nivel, "texto": texto, "chave": chave}


def bloco_api(situacao: object, limite_s: object) -> dict:
    """Bloco "API": se o serviço respondeu, se o banco dele respondeu e quanto tempo a resposta levou."""
    s = _dic(situacao)
    limite = limite_s if _real(limite_s) else None
    medicoes = [m for m in s.get("medicoes") or [] if isinstance(m, dict)]
    tempo = resumo_tempos(medicoes, limite)
    if s.get("configurada") is not True:
        return {"configurada": False, "estado": "idle", "titulo": "Não configurada", "status": None, "banco": None,
                "ultima_publicacao": None, "consultado_em": None, "tempo": tempo,
                "linhas": [s.get("erro_config") or "API não configurada."], "pontos": []}
    consulta = s.get("consulta")
    if not isinstance(consulta, dict):
        return {"configurada": True, "estado": "idle", "titulo": "sem dados", "status": None, "banco": None,
                "ultima_publicacao": None, "consultado_em": None, "tempo": tempo, "linhas": [], "pontos": []}

    hora = _sp(s.get("consultado_em"))
    ultima = _data_de(consulta.get("ultima_publicacao"))
    status, banco, http = consulta.get("status"), consulta.get("banco"), consulta.get("http")
    linhas, pontos = [], []
    if consulta.get("respondeu") is not True:
        timeout = s.get("timeout_s")
        timeout_txt = f"{timeout:g}".replace(".", ",") if _real(timeout) else "sem dados"
        estado, titulo = "warn", "Sem resposta"
        linhas.append(f"Sem resposta em até {timeout_txt} s ({consulta.get('erro') or 'sem detalhe'})")
        pontos.append(_ponto_api("warn", "API sem resposta", "api_sem_resposta"))
    elif _banco_fora(consulta):
        estado, titulo = "bad", "Banco da API fora"
        linhas.append(f"Status {status or 'sem dados'} · banco {banco or 'sem dados'}")
        pontos.append(_ponto_api("bad", "Banco da API fora", "api_banco_fora"))
    elif http == 200 and status == "ok" and banco == "ok":
        estado, titulo = "ok", "No ar"
        linhas.append("Status ok · banco ok")
    else:
        estado, titulo = "warn", f"Resposta inesperada (HTTP {http or 'sem dados'})"
        linhas.append(f"Status {status or 'sem dados'} · banco {banco or 'sem dados'}")
        pontos.append(_ponto_api("warn", f"API com resposta inesperada (HTTP {http or 'sem dados'})",
                                 "api_sem_resposta"))

    if ultima is not None:
        linhas.append(f"Última publicação completa: {ultima:%d/%m/%Y}")
    linhas.append(tempo["texto"])
    if hora is not None:
        linhas.append(f"Consultada às {hora:%H:%M:%S}")
    if estado == "ok" and tempo["acima_limite"]:
        estado = "warn"
        media = f"{tempo['media_s']:.2f}".replace(".", ",")
        pontos.append(_ponto_api("warn", f"API lenta (média {media} s)", "api_lenta"))
    return {"configurada": True, "estado": estado, "titulo": titulo, "status": status, "banco": banco,
            "ultima_publicacao": None if ultima is None else ultima.isoformat(),
            "consultado_em": None if hora is None else f"{hora:%H:%M:%S}", "tempo": tempo,
            "linhas": linhas, "pontos": pontos}


def bloco_banco(situacao: object, esperado: object, pregao: object) -> dict:
    """Bloco "Banco da API": a última publicação completa, informada pela API, comparada com a data esperada."""
    s = _dic(situacao)
    consulta = s.get("consulta")
    if s.get("configurada") is not True or not isinstance(consulta, dict) or consulta.get("respondeu") is not True:
        return {"estado": "idle", "titulo": "sem dados", "ultima_publicacao": None, "esperada": None,
                "linhas": ["Depende da resposta da API."], "pontos": []}
    if _banco_fora(consulta):
        return {"estado": "bad", "titulo": "Fora", "ultima_publicacao": None, "esperada": None,
                "linhas": ["A API respondeu que o banco dela não responde."], "pontos": []}

    ultima = _data_de(consulta.get("ultima_publicacao"))
    esp = _data_de(esperado)
    pregao_txt = _dd_mm_aaaa(pregao)
    sufixo = f" (pregão de {pregao_txt})" if pregao_txt else ""
    linhas = []
    if ultima is not None:
        linhas.append(f"Última publicação completa: {ultima:%d/%m/%Y}")
    if esp is not None:
        linhas.append(f"Esperada: {esp:%d/%m/%Y}{sufixo}")
    datas = {"ultima_publicacao": None if ultima is None else ultima.isoformat(),
             "esperada": None if esp is None else esp.isoformat()}
    if ultima is None:
        return {"estado": "warn", "titulo": "Nada publicado ainda", **datas, "linhas": linhas,
                "pontos": [{"nivel": "warn", "texto": "Banco da API: nada publicado ainda", "chave": "banco_atrasado"}]}
    if esp is None:
        return {"estado": "idle", "titulo": "sem rotina para comparar", **datas, "linhas": linhas, "pontos": []}
    if ultima >= esp:
        return {"estado": "ok", "titulo": "Em dia", **datas, "linhas": linhas, "pontos": []}
    texto = f"Banco da API: última publicação completa {ultima:%d/%m/%Y}, esperada {esp:%d/%m/%Y}"
    return {"estado": "warn", "titulo": "Publicação atrasada", **datas, "linhas": linhas,
            "pontos": [{"nivel": "warn", "texto": texto, "chave": "banco_atrasado"}]}


def _estado_titulo(bloco: dict) -> tuple[str, str]:
    """Estado e título de um nó do fluxo; bloco vazio ou sem estado conhecido vira "idle" e "sem dados"."""
    estado, titulo = bloco.get("estado"), bloco.get("titulo")
    if estado not in ("ok", "warn", "bad", "idle") or not isinstance(titulo, str):
        return "idle", "sem dados"
    return estado, titulo


def fluxo_nos(fluxo_dia: object, banco: object, api: object) -> dict:
    """Os cinco nós do fluxo do painel (coleta, processamento, banco da API, API, interface), com cor e horário.

    Sem fluxo do dia, coleta, processamento e interface ficam "sem dados"; banco e API vêm dos blocos deles.
    rodape: a última carga completa (ou "sem dados").
    """
    f = _dic(fluxo_dia)
    disponivel = f.get("disponivel") is True
    coleta = _dic(f.get("coleta")) if disponivel else {}
    proc = _dic(f.get("processamento")) if disponivel else {}
    interface = _dic(f.get("interface")) if disponivel else {}
    carga = _dic(f.get("carga")) if disponivel else {}
    b, a = _dic(banco), _dic(api)

    fim = _sp(proc.get("fim"))
    ultima = _data_de(b.get("ultima_publicacao"))
    consultado = a.get("consultado_em")
    nos = [
        ("coleta", "Coleta", coleta, coleta.get("entrega_hhmm"), "fluxo-coleta"),
        ("processamento", "Processamento", proc, None if fim is None else f"{fim:%H:%M}", "fluxo-processamento"),
        ("banco", "Banco da API", b, None if ultima is None else f"{ultima:%d/%m}", "fluxo-banco"),
        ("api", "API", a, consultado[:5] if isinstance(consultado, str) and consultado else None, "fluxo-api"),
        ("interface", "Interface", interface, None, "fluxo-interface"),
    ]
    saida = []
    for id_, nome, bloco, quando, alvo in nos:
        estado, texto = _estado_titulo(bloco)
        saida.append({"id": id_, "nome": nome, "estado": estado, "texto": texto, "quando": quando, "alvo": alvo})
    rotulo = carga.get("rotulo")
    rodape = rotulo if isinstance(rotulo, str) else "última carga completa: sem dados"
    return {"disponivel": disponivel, "nos": saida, "rodape": rodape}


def _pontos_do_bloco(bloco: object, alvo: str) -> list[dict]:
    """Pontos (warn/bad) que um bloco já traz (API, Banco, dia atípico), com o alvo da tela."""
    saida = []
    for p in _dic(bloco).get("pontos") or []:
        p = _dic(p)
        if p.get("nivel") in ("warn", "bad") and isinstance(p.get("texto"), str) and isinstance(p.get("chave"), str):
            saida.append(_ponto(p["nivel"], p["texto"], alvo, p["chave"]))
    return saida


def pontos_de_atencao(hoje: object, trava: object, fluxo_dia: object, linha_tempo: object,
                      saude_visao: object, testes: object, *, api: object = None, banco: object = None,
                      dia_atipico: object = None) -> list[dict]:
    """Faróis amarelos (warn) e vermelhos (bad) da tela, na ordem em que aparecem na página."""
    hoje, trava, fluxo_dia, linha_tempo, saude_visao, testes = (
        _dic(v) for v in (hoje, trava, fluxo_dia, linha_tempo, saude_visao, testes))
    pontos: list[dict] = []
    if fluxo_dia.get("disponivel") is True:
        coleta = _dic(fluxo_dia.get("coleta"))
        if coleta.get("estado") in ("warn", "bad"):
            titulo = str(coleta.get("titulo") or "sem dados").lower()
            pontos.append(_ponto(coleta["estado"], f"Coleta ({titulo})", "fluxo-coleta", "coleta_" + coleta["estado"]))
        d = _data(fluxo_dia.get("data"))
        dia = d.strftime("%d/%m/%Y") if d else "sem data"
        status = fluxo_dia.get("status")
        if status == "falhou":
            pontos.append(_ponto("bad", f"Última rotina diária ({dia}) falhou", "fluxo-processamento", "rotina_falhou"))
        elif status == "parcial":
            pontos.append(_ponto("warn", f"Última rotina diária ({dia}) com pendências", "fluxo-processamento",
                                 "rotina_parcial"))
        elif status == "em_andamento" and fluxo_dia.get("possivelmente_interrompida"):
            pontos.append(_ponto("warn", f"Última rotina diária ({dia}) pode ter sido interrompida",
                                 "fluxo-processamento", "rotina_interrompida"))
    else:
        pontos.append(_ponto("warn", "Fluxo do dia: sem dados", "agora", "sem_rotina"))
    pontos += _pontos_do_bloco(banco, "fluxo-banco")
    pontos += _pontos_do_bloco(api, "fluxo-api")
    folga = linha_tempo.get("folga_s")
    if _inteiro(folga) and folga < 0:
        pontos.append(_ponto("warn", f"Rotina terminou depois do prazo ({linha_tempo.get('folga_texto')})",
                             "linha-tempo", "atraso_prazo"))
    pontos += _pontos_do_bloco(dia_atipico, "dia-atipico")
    if saude_visao.get("disponivel") is not True:
        pontos.append(_ponto("warn", "Saúde dos dados: sem diagnóstico", "saude", "saude_sem_diagnostico"))
    for c in saude_visao.get("cartoes") or []:
        c = _dic(c)
        farol, id_ = c.get("farol"), c.get("id")
        if not isinstance(id_, str):
            continue
        texto = f"{c.get('titulo')} ({c.get('numero')})"
        if farol in ("warn", "bad"):
            pontos.append(_ponto(farol, texto, f"saude-c-{id_}", f"saude_{id_}"))
        elif farol == "idle":
            pontos.append(_ponto("warn", texto, f"saude-c-{id_}", "saude_sem_dados"))
    if hoje.get("erro") or hoje.get("disponivel") is False:
        pontos.append(_ponto("bad", "Calendário da B3 com erro", "historico", "calendario_erro"))
    if testes.get("disponivel") is True:
        contagens = _dic(testes.get("contagens"))
        falhas = sum(v for k, v in contagens.items() if k in ("failed", "errors") and _inteiro(v))
        if testes.get("interrompido"):
            pontos.append(_ponto("warn", "Testes automáticos interrompidos", "testes", "testes_interrompidos"))
        elif testes.get("aprovado") is False and falhas > 0:
            pontos.append(_ponto("bad", f"Testes automáticos com falhas ({_plural(falhas, 'falha', 'falhas')})",
                                 "testes", "testes_falhas"))
        elif testes.get("aprovado") is False:
            pontos.append(_ponto("warn", "Testes automáticos sem resultado completo", "testes", "testes_interrompidos"))
    if trava.get("abandonada") is True:
        idade = trava.get("idade_min")
        texto = f"Trava da rotina esquecida ({idade} min)" if _inteiro(idade) else "Trava da rotina esquecida"
        pontos.append(_ponto("warn", texto, "comandos", "trava_abandonada"))
    return pontos


def resumo(hoje: object, trava: object, fluxo_dia: object, linha_tempo: object,
           saude_visao: object, testes: object, *, api: object = None, banco: object = None,
           dia_atipico: object = None) -> dict:
    """Frase única do topo ("Tudo certo", "Atenção: N pontos" ou "Falhou: ...") e a lista de pontos."""
    pontos = pontos_de_atencao(hoje, trava, fluxo_dia, linha_tempo, saude_visao, testes,
                               api=api, banco=banco, dia_atipico=dia_atipico)
    ruins = [p for p in pontos if p["nivel"] == "bad"]
    atencao = [p for p in pontos if p["nivel"] == "warn"]
    if ruins:
        frase = "Falhou: " + "; ".join(p["texto"] for p in ruins)
        if atencao:
            frase += " · e " + _plural(len(atencao), "ponto de atenção", "pontos de atenção")
        nivel = "bad"
    elif atencao:
        frase, nivel = "Atenção: " + _plural(len(atencao), "ponto", "pontos"), "warn"
    else:
        frase, nivel = "Tudo certo", "ok"
    return {"nivel": nivel, "frase": frase, "pontos": pontos}


def tempo_curto(segundos: object) -> str | None:
    """Tempo arredondado para o botão: "menos de um minuto", "~2 min", "~1 h 30 min"; None se não houver."""
    if not _inteiro(segundos) or segundos < 0:
        return None
    if segundos < 60:
        return "menos de um minuto"
    minutos = (segundos + 30) // 60
    if minutos < 60:
        return f"~{minutos} min"
    return f"~{minutos // 60} h {minutos % 60} min"


def tempos_acoes(duracoes_painel: object, rotina: object, completa: object) -> dict[str, dict]:
    """Tempo de cada ação: log do painel; senão execucao.json (rotina e carga ok/parcial); senão sem medição."""
    duracoes = _dic(duracoes_painel)
    itens = {"rotina": _dic(rotina), "carga": _dic(completa)}
    saida: dict[str, dict] = {}
    for acao_id in ACOES:
        s = duracoes.get(acao_id)
        if _inteiro(s) and s >= 0:
            saida[acao_id] = {"segundos": s, "curto": tempo_curto(s),
                              "texto": f"Da última vez, pelo painel, levou {formatar_duracao(s)}.", "origem": "painel"}
            continue
        item = itens.get(acao_id, {})
        s = item.get("duracao_s")
        if item.get("legivel") and item.get("status") in ("ok", "parcial") and _inteiro(s) and s >= 0:
            saida[acao_id] = {"segundos": s, "curto": tempo_curto(s),
                              "texto": f"{ROTULO_EXECUCAO[acao_id]} levou {formatar_duracao(s)}.", "origem": "execucao"}
        else:
            saida[acao_id] = {"segundos": None, "curto": None, "texto": TEXTO_SEM_MEDICAO, "origem": None}
    return saida


def hora_marco(linha_tempo: object, id_: str) -> str | None:
    """Hora (HH:MM) do marco `id_` da linha do tempo; None se não houver."""
    for m in _dic(linha_tempo).get("marcos") or []:
        if isinstance(m, dict) and m.get("id") == id_ and isinstance(m.get("hora"), str):
            return m["hora"]
    return None


def _dia_curto_ano(d: date) -> str:
    """Dia da semana curto e data com ano: "sex 23/10/2026"."""
    return f"{DIAS_CURTOS[d.weekday()]} {d:%d/%m/%Y}"


def frase_dia(hoje_iso: object, data_ultima: object, caminho_calendario: str | None = None) -> str:
    """Frase do topo (E1): o que é hoje (pregão ou não) e de qual pregão é a última rotina diária.

    `data_ultima` é a data de referência da última rotina diária (AAAA-MM-DD), ou None se não há nenhuma.
    """
    hoje = _data(hoje_iso)
    if hoje is None:
        return "Não foi possível saber a data de hoje."
    pregao, motivo = _pregao(hoje, caminho_calendario)
    cabeca = f"Hoje é {DIAS_LONGOS[hoje.weekday()]}, {hoje:%d/%m/%Y}"
    if pregao is None:
        situacao = "(não foi possível saber se há pregão)"
    elif pregao:
        situacao = "(dia de pregão)"
    elif hoje.weekday() >= 5:
        situacao = "(sem pregão)"
    else:
        situacao = f"(sem pregão: {motivo})"
    ultima = _data(data_ultima)
    if ultima is None:
        cauda = "Nenhuma rotina diária encontrada."
    elif ultima == hoje:
        cauda = "A última rotina diária é a de hoje."
    elif pregao and ultima < hoje:
        cauda = f"A rotina de hoje ainda não rodou; a última é do pregão de {_dia_curto_ano(ultima)}."
    else:
        cauda = f"A última rotina diária é do pregão de {_dia_curto_ano(ultima)}."
    return f"{cabeca} {situacao}. {cauda}"
