"""Fábrica da rotina diária (tests/test_rotina_gatilho.py e, depois, a fase 8): relógio falso, painel
simulado e linha do tempo de leituras do painel (plano da etapa 8, seção 3 e fase 3).

Os horários de execução e de etapa entram em UTC sem fuso, como no banco, e são convertidos para
São Paulo por `fontes.para_sao_paulo_de_utc`. Nenhuma função usa banco, rede ou relógio do sistema.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pandas as pd

from processamento import fontes
from processamento.diagnostico.esperado import ETAPAS_COLETA
from processamento.rotina.gatilho import Painel

_COLUNAS_EXECUCOES = ["id", "tipo", "status", "iniciada_em", "finalizada_em", "origem", "aguardando"]
_COLUNAS_ETAPAS = ["execucao_id", "etapa_id", "ordem", "status", "finalizada_em"]


def _sp(instante: datetime) -> datetime:
    """Datetime com fuso de São Paulo (um naive é tomado como horário de São Paulo)."""
    return instante.replace(tzinfo=fontes.SP) if instante.tzinfo is None else instante


class RelogioFalso:
    """Relógio que só avança quando `dormir` é chamado. Guarda os tempos dormidos em `.sonos`."""

    def __init__(self, inicio: datetime):
        self._agora = _sp(inicio)
        self.sonos: list[float] = []

    def agora(self) -> datetime:
        return self._agora

    def dormir(self, segundos: float) -> None:
        self.sonos.append(segundos)
        self._agora = self._agora + timedelta(seconds=segundos)


def execucao(id: str, iniciada_utc: str, *, origem: str = "cron", status: str = "em_andamento",
             tipo: str = "daily", aguardando: str | None = None, finalizada_utc: str | None = None) -> dict:
    """Uma linha de `v1-painel_execucoes` (horários em UTC sem fuso, como no banco)."""
    return {"id": id, "tipo": tipo, "status": status, "iniciada_em": iniciada_utc,
            "finalizada_em": finalizada_utc, "origem": origem, "aguardando": aguardando}


def etapas(execucao_id: str, status: dict[str, str], finalizada_utc: dict[str, str] | None = None) -> pd.DataFrame:
    """Linhas de `v1-painel_etapas` de uma execução. Etapa fora de `status` não tem linha (ausente)."""
    finalizada_utc = finalizada_utc or {}
    linhas = [
        {"execucao_id": execucao_id, "etapa_id": e, "ordem": ETAPAS_COLETA.index(e), "status": status[e],
         "finalizada_em": finalizada_utc.get(e)}
        for e in ETAPAS_COLETA if e in status
    ]
    return pd.DataFrame(linhas, columns=_COLUNAS_ETAPAS)


def painel(execucoes: list[dict], etapas_por_execucao: dict[str, pd.DataFrame], ultimo_ibov: date | None) -> Painel:
    """Painel com os horários convertidos de UTC para São Paulo (formato de `fontes.ler_painel_*`)."""
    exe = pd.DataFrame(execucoes, columns=_COLUNAS_EXECUCOES)
    for coluna in ("iniciada_em", "finalizada_em"):
        exe[coluna] = fontes.para_sao_paulo_de_utc(exe[coluna])
    etapas_sp = {}
    for execucao_id, tabela in etapas_por_execucao.items():
        tabela = tabela.copy()
        tabela["finalizada_em"] = fontes.para_sao_paulo_de_utc(tabela["finalizada_em"])
        etapas_sp[execucao_id] = tabela
    return Painel(execucoes=exe, etapas=etapas_sp, ultimo_ibov=ultimo_ibov)


def linha_do_tempo(relogio: RelogioFalso, estados: list[tuple[datetime, Painel]]) -> Callable[[], Painel]:
    """Função `consultar` que devolve o último estado com horário <= `relogio.agora()`.

    Antes do primeiro estado, devolve um painel vazio (sem execuções e sem IBOV).
    """
    ordenados = sorted(((_sp(h), p) for h, p in estados), key=lambda item: item[0])

    def consultar() -> Painel:
        agora = relogio.agora()
        escolhido = painel([], {}, None)
        for horario, estado in ordenados:
            if horario <= agora:
                escolhido = estado
        return escolhido

    return consultar
