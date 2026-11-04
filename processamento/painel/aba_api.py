"""Aba API do painel: lê a saída do publicador nos logs do dia (logs/painel/dia-*.log) e devolve as publicações.

Só trabalha com os logs já lidos pelo painel (aba_execucoes.ler_logs_dia); não consulta a API (isso fica em api.py)
e não acessa banco nem rede. Linha ausente ou fora do formato vira None, nunca 0 nem exceção.
"""

from __future__ import annotations

import re
from datetime import date

from processamento.calendario import SP
from processamento.painel.leitores import _instante

RE_PUB = re.compile(r"^(\d{2}/\d{2}/\d{4}) publicado \(modo (\w+), execução: (\w+)\) em ([\d,]+) s$")
RE_ITEM = re.compile(r"^  (\S.*?)\.{2,}\s*(.*)$")
RE_NUMERO = re.compile(r"^(\d[\d.]*)")
RE_PACOTE = re.compile(r"\((\w+)\)$")
ESPECIAIS = {"correções": "correcoes", "ruído numérico": "ruido", "ajustes de série": "ajustes"}
FIM_PUBLICADOR = "# dia: etapa=publicador fim"
FONTE = "logs/painel/dia-*.log (saída do publicador)"
MOTIVO_SEM_PUBLICACAO = "Nenhuma publicação completa nos logs do dia completo (logs/painel/dia-*.log)."


# ---------------------------------------------------------------- auxiliares

def _numero(texto: str) -> int | None:
    m = RE_NUMERO.match(texto)
    return int(m.group(1).replace(".", "")) if m else None


def _segundos(texto: str) -> float | None:
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def _data_texto(data: object, com_ano: bool) -> str | None:
    """'AAAA-MM-DD' → 'DD/MM' (ou 'DD/MM/AAAA'); None se inválida."""
    if not isinstance(data, str):
        return None
    try:
        d = date.fromisoformat(data)
    except ValueError:
        return None
    return f"{d:%d/%m/%Y}" if com_ano else f"{d:%d/%m}"


def _hhmm(instante: object) -> str | None:
    dt = _instante(instante)
    return None if dt is None else f"{dt.astimezone(SP):%H:%M}"


def _chave_inicio(log: dict) -> str:
    inicio = log.get("inicio")
    return inicio if isinstance(inicio, str) else ""


# ---------------------------------------------------------------- leitura

def publicador_do_log(linhas: list[str]) -> dict | None:
    """Saída do publicador num log do dia: modo, execução, segundos, correções, ruído, ajustes e pacotes.

    Usa a última linha "publicado (modo ...)"; sem ela → None. Os itens valem até a linha de fim da etapa publicador.
    Correções, ruído e ajustes ausentes ficam None (log antigo sem a linha).
    """
    cabecalho, inicio = None, None
    for i, linha in enumerate(linhas):
        m = RE_PUB.match(linha)
        if m:
            cabecalho, inicio = m, i
    if cabecalho is None:
        return None
    pacotes, especiais = [], {"correcoes": None, "ruido": None, "ajustes": None}
    for linha in linhas[inicio + 1:]:
        if linha.startswith(FIM_PUBLICADOR):
            break
        item = RE_ITEM.match(linha)
        if item is None:
            continue
        nome, texto = item.group(1).strip(), item.group(2)
        if nome in ESPECIAIS:
            especiais[ESPECIAIS[nome]] = _numero(texto)
            continue
        pacote = RE_PACOTE.search(nome)
        pacotes.append({"pacote": pacote.group(1) if pacote else nome, "rotulo": nome, "texto": texto,
                        "estado": "retido" if texto.startswith("não publicado") else "publicado"})
    return {"modo": cabecalho.group(2), "execucao": cabecalho.group(3), "segundos": _segundos(cabecalho.group(4)),
            **especiais, "pacotes": pacotes}


def publicacoes(logs: list[dict]) -> dict:
    """Publicações completas dos logs do dia (mais novo primeiro, como em aba_execucoes.ler_logs_dia).

    `correcoes`: uma linha por log com saída do publicador, da mais antiga para a mais nova. `ultima`: a publicação
    mais recente. Sem nenhuma → disponivel False.
    """
    achados = []
    for log in logs:
        if not isinstance(log, dict):
            continue
        pub = publicador_do_log(log.get("linhas") or [])
        if pub is not None:
            achados.append((log, pub))
    if not achados:
        return {"disponivel": False, "motivo": MOTIVO_SEM_PUBLICACAO, "fonte": FONTE,
                "correcoes": [], "maximo": None, "ultima": None}
    achados.sort(key=lambda par: _chave_inicio(par[0]))
    correcoes = [{"data": log.get("data"), "data_texto": _data_texto(log.get("data"), False),
                  "hhmm": _hhmm(log.get("fim")), "arquivo": log.get("arquivo"), "modo": pub["modo"],
                  "correcoes": pub["correcoes"], "ruido": pub["ruido"], "ajustes": pub["ajustes"]}
                 for log, pub in achados]
    valores = [c["correcoes"] for c in correcoes if isinstance(c["correcoes"], int)]
    log, pub = achados[-1]
    segundos = pub["segundos"]
    ultima = {"data": log.get("data"), "data_texto": _data_texto(log.get("data"), True),
              "hhmm": _hhmm(log.get("fim")), "modo": pub["modo"], "execucao": pub["execucao"],
              "segundos": segundos,
              "segundos_texto": None if segundos is None else f"{segundos:.1f}".replace(".", ",") + " s",
              "n_pacotes": sum(1 for p in pub["pacotes"] if p["estado"] == "publicado"),
              "pacotes": pub["pacotes"]}
    return {"disponivel": True, "motivo": None, "fonte": FONTE, "correcoes": correcoes,
            "maximo": max(valores) if valores else None, "ultima": ultima}
