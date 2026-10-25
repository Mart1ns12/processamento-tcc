"""Etapas de cada ação do painel (marcos), a partir das linhas do log.

Função pura: recebe as linhas da ação e devolve a lista de etapas com estado e detalhe.
O servidor usa isto em `/api/acao`; a página só desenha. Nenhum SQL, nenhum banco.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from processamento.painel.relatorios import (
    RE_CONSULTA,
    RE_INICIO,
    RE_PYTEST_RESUMO,
    RE_SAIDA,
    resultado_terminal,
)

RE_PROGRESSO = re.compile(r"\[\s*(\d{1,3})%\]\s*$")
RE_RELATORIO = re.compile(r"^Relatório: .+ \| divergências: (\d+)$")

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


def marcos_acao(acao_id: str | None, linhas: list[str], *, rodando: bool, codigo: int | None,
                significado: str | None) -> list[dict]:
    """Etapas da ação com `estado` (espera, agora, concluida, erro, pulada) e `detalhe`.

    `acao_id` desconhecido ou None devolve lista vazia. `significado` é o texto do código de saída.
    """
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
