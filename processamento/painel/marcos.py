"""Etapas de cada ação do painel (marcos), a partir das linhas do log.

Função pura: recebe as linhas da ação e devolve a lista de etapas com estado e detalhe.
O servidor usa isto em `/api/acao`; a página só desenha. Nenhum SQL, nenhum banco.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processamento.calendario import SP
from processamento.painel.leitores import _instante, duracao_segundos, formatar_duracao
from processamento.painel.relatorios import (
    IDS_ETAPAS_DIA,
    RE_CONSULTA,
    RE_DIA_FIM,
    RE_DIA_INICIO,
    RE_DIA_PULADA,
    RE_INICIO,
    RE_PYTEST_RESUMO,
    RE_SAIDA,
    resultado_terminal,
    tempos_etapas_dia,
)

RE_PROGRESSO = re.compile(r"\[\s*(\d{1,3})%\]\s*$")
RE_RELATORIO = re.compile(r"^Relatório: .+ \| divergências: (\d+)$")

_ETAPAS_DIA = [
    ("rotina", "Rotina do dia (só leitura do banco da coleta)"),
    ("carga", "Carga completa em saida_completa/"),
    ("publicador", "Publicador (grava no banco da API)"),
    ("fim", "Encerrado"),
]

# Linhas que terminam a ação com erro, nos scripts que não usam `resultado_terminal` (carga e diagnóstico).
_INICIO_TERMINAL_BANCO = (
    "Configuração do banco incompleta",
    "Falha ao conectar ao banco",
    "Saída não gerada:",
    "A carga completa precisa de outra pasta",
)
_FIM_TERMINAL_BANCO = ("Nada foi gravado.", "A coleta não foi alterada.")


def _inicio(linha: str) -> str | None:
    m = RE_INICIO.match(linha)
    if not m:
        return None
    return f"início {m.group(2)}" + (" (--sem-esperar)" if m.group(3) else "")


def _consulta_pronta(linha: str) -> str | None:
    m = RE_CONSULTA.match(linha)
    if m and m.group(3).endswith("-> gerar"):
        return f"consulta {m.group(2)} às {m.group(1)}: coleta pronta"
    return None


def _consulta_andamento(linha: str) -> str | None:
    m = RE_CONSULTA.match(linha)
    if not m:
        return None
    return f"consulta {m.group(2)} às {m.group(1)}: {m.group(3).rsplit(' -> ', 1)[-1]}"


def _saida(linha: str) -> str | None:
    m = RE_SAIDA.match(linha)
    return f"status {m.group(1)}" if m else None


def _relatorio(linha: str) -> str | None:
    m = RE_RELATORIO.match(linha)
    if not m:
        return None
    n = int(m.group(1))
    if n == 1:
        return "1 divergência"
    return f"{n} divergências" if n else "0 divergências"


def _testes_encontrados(linha: str) -> str | None:
    return "testes encontrados" if RE_PROGRESSO.search(linha) else None


def _resumo_pytest(linha: str) -> str | None:
    if RE_PYTEST_RESUMO.match(linha):
        return linha.strip().strip("=").strip()
    return None


def _percentual(linha: str) -> str | None:
    m = RE_PROGRESSO.search(linha)
    return f"{m.group(1)}%" if m else None


def _terminal_rotina(linha: str) -> tuple[str, str] | None:
    """Rotina: `resultado_terminal`; dia sem pregão pula as etapas, o resto é erro com a própria linha."""
    fim = resultado_terminal(linha)
    if fim is None:
        return None
    tipo, detalhe = fim
    if tipo == "sem_pregao":
        return "pula", f"não é pregão previsto ({detalhe}): nada a gerar"
    return "erro", linha


def _terminal_banco(linha: str) -> tuple[str, str] | None:
    """Carga e diagnóstico: erros de banco, configuração ou pasta recusada."""
    if linha.startswith(_INICIO_TERMINAL_BANCO) or linha.endswith(_FIM_TERMINAL_BANCO):
        return "erro", linha
    return None


@dataclass(frozen=True)
class Etapa:
    id: str
    rotulo: str
    conclui: Callable[[str], str | None] | None = None
    progresso: Callable[[str], str | None] | None = None


FIM = Etapa("fim", "Encerrado")

ETAPAS: dict[str, list[Etapa]] = {
    "rotina": [
        Etapa("inicio", "Rotina iniciada", conclui=_inicio),
        Etapa("coleta", "Conferindo se a coleta do dia terminou",
              conclui=_consulta_pronta, progresso=_consulta_andamento),
        Etapa("calculo", "Calculando indicadores, top 5 e pacotes (só leitura do banco)"),
        Etapa("saida", "Gravando os pacotes do dia", conclui=_saida),
        FIM,
    ],
    "carga": [
        Etapa("calculo", "Lendo o banco (só leitura) e montando os pacotes inteiros"),
        Etapa("saida", "Gravando em saida_completa/", conclui=_saida),
        FIM,
    ],
    "diagnostico": [
        Etapa("leitura", "Lendo o banco da coleta (só leitura) e conferindo as seções"),
        Etapa("relatorio", "Gravando docs/diagnostico_banco.md", conclui=_relatorio),
        FIM,
    ],
    "testes": [
        Etapa("coleta", "Encontrando os testes", conclui=_testes_encontrados),
        Etapa("execucao", "Rodando os testes (sem o banco)", conclui=_resumo_pytest, progresso=_percentual),
        FIM,
    ],
}

# Função que reconhece a linha que termina a ação (None = a ação não tem linha terminal).
TERMINAIS: dict[str, Callable[[str], tuple[str, str] | None] | None] = {
    "rotina": _terminal_rotina,
    "carga": _terminal_banco,
    "diagnostico": _terminal_banco,
    "testes": None,
}


def marcos_dia(linhas: list[str], *, rodando: bool, codigo: int | None, significado: str | None) -> list[dict]:
    """Etapas do dia completo, a partir dos marcadores `# dia: ...` (rotina, carga, publicador e fim)."""
    est = {i: {"id": i, "rotulo": r, "estado": "espera", "detalhe": None} for i, r in _ETAPAS_DIA}
    comecou = False
    for linha in linhas:
        m = RE_DIA_INICIO.match(linha)
        if m and m.group(1) in IDS_ETAPAS_DIA:
            est[m.group(1)]["estado"] = "agora"
            comecou = True
            continue
        m = RE_DIA_FIM.match(linha)
        if m and m.group(1) in IDS_ETAPAS_DIA:
            est[m.group(1)]["estado"] = "concluida" if int(m.group(2)) == 0 else "erro"
            est[m.group(1)]["detalhe"] = m.group(4)
            continue
        m = RE_DIA_PULADA.match(linha)
        if m and m.group(1) in IDS_ETAPAS_DIA:
            est[m.group(1)]["estado"] = "pulada"
            est[m.group(1)]["detalhe"] = m.group(2)

    terminou = not rodando and codigo is not None
    for i in IDS_ETAPAS_DIA:
        if terminou and est[i]["estado"] == "agora":
            est[i]["estado"] = "erro"
        elif terminou and est[i]["estado"] == "espera":
            est[i]["estado"] = "pulada"
    if rodando and not comecou:
        est["rotina"]["estado"] = "agora"
    if terminou:
        est["fim"]["estado"] = "concluida" if codigo == 0 else "erro"
        est["fim"]["detalhe"] = significado
    return [est[i] for i, _ in _ETAPAS_DIA]


ROTULOS_PROGRESSO = {"rotina": "Rotina", "carga": "Carga completa", "publicador": "Publicador"}


def _decorrido(inicio: str | None, agora: datetime) -> int | None:
    """Segundos desde o início (ISO do log) até `agora`; None sem horário."""
    ini = _instante(inicio)
    if ini is None:
        return None
    return max(0, int((agora - ini).total_seconds()))


def _percentual_etapa(estado: str, decorrido: int | None, media: int | None) -> int | None:
    if estado in ("concluida", "erro"):
        return 100
    if estado in ("espera", "pulada"):
        return 0
    if estado == "agora" and decorrido is not None and media:
        return min(99, decorrido * 100 // media)
    return None


def _info_etapa(estado: str, percentual: int | None, duracao: int | None, media: int | None) -> str:
    if estado == "concluida":
        return formatar_duracao(duracao) if duracao is not None else "concluída"
    if estado == "agora":
        return f"{percentual}%" if percentual is not None else "em andamento"
    if estado == "espera":
        return f"≈ {formatar_duracao(media)}" if media is not None else "sem média ainda"
    if estado == "pulada":
        return "pulada"
    return "erro"


def progresso_dia(linhas: list[str], marcos: list[dict], medias: dict, amostras: dict, agora: datetime,
                  rodando: bool) -> dict:
    """Progresso do dia completo: por etapa, estado, percentual e tempo estimado; e o que falta (estimativa).

    `marcos` é a saída de `marcos_dia`; `medias` e `amostras` vêm de `relatorios.medias_etapas_dia`.
    Sem média ou sem horário a estimativa fica None ("sem média ainda"); ausência nunca vira 0.
    """
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=SP)
    tempos = tempos_etapas_dia(linhas)
    estados = {m["id"]: m["estado"] for m in marcos}
    etapas = []
    for i, rotulo in ROTULOS_PROGRESSO.items():
        estado = estados.get(i, "espera")
        t = tempos[i]
        media = medias.get(i)
        decorrido = _decorrido(t["inicio"], agora)
        percentual = _percentual_etapa(estado, decorrido, media)
        duracao = duracao_segundos(t["inicio"], t["fim"])
        etapas.append({"id": i, "rotulo": rotulo, "estado": estado, "percentual": percentual,
                       "inicio": t["inicio"], "fim": t["fim"], "duracao_s": duracao, "media_s": media,
                       "info": _info_etapa(estado, percentual, duracao, media)})
    if not rodando:
        return {"etapas": etapas, "restante_s": None, "restante_texto": None, "amostras": None}

    pendentes = [e for e in etapas if e["estado"] in ("espera", "agora")]
    if not pendentes:
        return {"etapas": etapas, "restante_s": 0, "restante_texto": "terminando", "amostras": None}
    k = min(amostras.get(e["id"], 0) for e in pendentes)
    if any(e["media_s"] is None for e in pendentes):
        return {"etapas": etapas, "restante_s": None, "restante_texto": "sem média ainda", "amostras": k}

    restante = 0
    for e in pendentes:
        if e["estado"] == "agora":
            # Sem horário, a etapa em andamento conta a média inteira.
            decorrido = _decorrido(e["inicio"], agora)
            restante += e["media_s"] if decorrido is None else max(0, e["media_s"] - decorrido)
        else:
            restante += e["media_s"]
    return {"etapas": etapas, "restante_s": restante,
            "restante_texto": f"faltam ≈ {formatar_duracao(restante)} (média das últimas {k})", "amostras": k}


def marcos_acao(acao_id: str | None, linhas: list[str], *, rodando: bool, codigo: int | None,
                significado: str | None) -> list[dict]:
    """Etapas da ação com `estado` (espera, agora, concluida, erro, pulada) e `detalhe`.

    `acao_id` desconhecido ou None devolve lista vazia. `significado` é o texto do código de saída.
    """
    if acao_id == "dia":
        return marcos_dia(linhas, rodando=rodando, codigo=codigo, significado=significado)
    if acao_id not in ETAPAS:
        return []
    etapas = ETAPAS[acao_id]
    terminal = TERMINAIS[acao_id]
    meio = etapas[:-1]
    est = [{"id": e.id, "rotulo": e.rotulo, "estado": "espera", "detalhe": None} for e in etapas]
    atual = 0
    nota_final = None

    for linha in linhas:
        term = terminal(linha) if terminal is not None else None
        if term is not None:
            tipo, det = term
            if atual < len(meio):
                est[atual]["estado"] = "erro" if tipo == "erro" else "pulada"
                if tipo == "erro":
                    est[atual]["detalhe"] = det
                for k in range(atual + 1, len(meio)):
                    est[k]["estado"] = "pulada"
            if tipo == "pula":
                nota_final = det
            atual = len(meio)
            break

        for j in range(atual, len(meio)):
            det = meio[j].conclui(linha) if meio[j].conclui is not None else None
            if det is not None:
                for k in range(atual, j + 1):
                    est[k]["estado"] = "concluida"
                est[j]["detalhe"] = det or est[j]["detalhe"]
                atual = j + 1
                break

        if atual < len(meio) and meio[atual].progresso is not None:
            p = meio[atual].progresso(linha)
            if p is not None:
                est[atual]["detalhe"] = p

    if not rodando and codigo is not None:
        if codigo == 0:
            for k in range(atual, len(meio)):
                est[k]["estado"] = "concluida"
            fim_estado = "concluida"
        else:
            if atual < len(meio):
                est[atual]["estado"] = "erro"
                for k in range(atual + 1, len(meio)):
                    est[k]["estado"] = "pulada"
            fim_estado = "erro"
        est[-1]["estado"] = fim_estado
        est[-1]["detalhe"] = nota_final or significado
    elif rodando:
        if atual < len(meio):
            est[atual]["estado"] = "agora"
        else:
            est[-1]["estado"] = "agora"

    return est
