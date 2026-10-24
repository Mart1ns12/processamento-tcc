"""Gatilho da rotina diária (seção 4 da especificação; plano da etapa 8, fase 3).

Decide, a cada consulta ao painel da coleta, se a rotina pode gerar os pacotes de D, e espera
até lá. Não lê o banco nem o `.env`: recebe o painel pronto (`consultar`) e o relógio (injetado),
então os testes simulam a manhã inteira sem rede, sem banco e sem espera real.

Convenções: horários do painel (`iniciada_em`, `finalizada_em`) são UTC sem fuso, como no banco;
toda data-hora deste módulo sai com fuso de São Paulo (`contrato.SP`).
"""

from __future__ import annotations

import time as _relogio_sistema
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Callable, Protocol

import pandas as pd

from processamento import fontes
from processamento.diagnostico.esperado import ETAPAS_COLETA
from processamento.rotina.parametros import ParametrosRotina
from processamento.saida.contrato import SP, data_hora_txt

# Mesmos 8 motivos de `contrato.MOTIVOS_COLETA` (um teste confere a igualdade).
MOTIVOS = ("entrega_concluida", "entrega_pendente", "entrega_falhou", "sem_daily", "daily_agendado",
           "dados_atrasados", "falha_consulta", "sem_esperar")
ORIGENS_DAILY = ("cron", "manual")

# Textos da seção 2.4 (desistência no prazo, um por motivo de espera).
_AVISOS_DESISTENCIA = {
    "sem_daily": "Coleta: nenhum daily de hoje (a partir das 08:00) até {prazo}; pacotes de hoje não gerados.",
    "daily_agendado": ("Coleta: o daily de hoje ainda não começou até {prazo} (aguardando a carga histórica); "
                       "pacotes de hoje não gerados."),
    "entrega_pendente": "Coleta: a entrega de hoje não terminou até {prazo}; pacotes de hoje não gerados.",
    "entrega_falhou": "Coleta: a etapa entrega falhou no daily de hoje; pacotes de hoje não gerados.",
    "dados_atrasados": ("Coleta: preços de {t_esperado} ainda não chegaram (último pregão no banco: {ultimo}); "
                        "pacotes de hoje não gerados."),
    "falha_consulta": "Coleta: o painel da coleta não pôde ser lido até {prazo}; pacotes de hoje não gerados.",
}


@dataclass(frozen=True)
class Painel:
    """Uma leitura do painel: execuções, etapas por execução e o último pregão do IBOV no banco.

    `execucoes`: formato de `fontes.ler_painel_execucoes`; `etapas`: execucao_id -> formato de
    `fontes.ler_painel_etapas`. Horários em São Paulo (a fábrica converte de UTC).
    """

    execucoes: pd.DataFrame
    etapas: dict[str, pd.DataFrame]
    ultimo_ibov: date | None


@dataclass(frozen=True)
class Decisao:
    """Resultado de `avaliar_painel` para uma leitura do painel."""

    acao: str                              # "esperar" | "gerar"
    motivo: str
    execucao: dict | None                  # id, origem, status, iniciada_em, finalizada_em
    etapas: dict[str, str | None]          # as 9 de ETAPAS_COLETA (None = sem linha)
    entrega_concluida_em: datetime | None
    avisos: list[str] = field(default_factory=list)
    nota: str = ""


@dataclass
class ResultadoGatilho:
    """Resultado de `esperar_coleta`: se a rotina pode gerar, e o histórico das consultas."""

    pronto: bool
    decisao: Decisao
    consultas: int
    primeira_consulta_em: datetime | None
    ultima_consulta_em: datetime | None
    prazo: datetime
    t_esperado: date
    ultimo_pregao_lido: date | None = None

    def espera_segundos(self) -> int:
        """Segundos entre a primeira e a última consulta."""
        if self.primeira_consulta_em is None or self.ultima_consulta_em is None:
            return 0
        return int((self.ultima_consulta_em - self.primeira_consulta_em).total_seconds())

    def coleta_status(self) -> dict:
        """Bloco `coleta_status` do `execucao.json` (formato da seção 8 do plano)."""
        d = self.decisao
        status = {
            "consultado": d.motivo != "falha_consulta",
            "nota": d.nota,
            "motivo": d.motivo,
        }
        if d.execucao is not None:
            status.update({
                "execucao_id": d.execucao["id"],
                "origem": d.execucao["origem"],
                "status_execucao": d.execucao["status"],
                "iniciada_em": data_hora_txt(d.execucao["iniciada_em"]),
                "finalizada_em": data_hora_txt(d.execucao["finalizada_em"]),
                "entrega_concluida_em": data_hora_txt(d.entrega_concluida_em),
                "etapas": dict(d.etapas),
            })
        status.update({
            "consultas": self.consultas,
            "espera_segundos": self.espera_segundos(),
            "primeira_consulta_em": data_hora_txt(self.primeira_consulta_em),
            "ultima_consulta_em": data_hora_txt(self.ultima_consulta_em),
            "prazo": data_hora_txt(self.prazo),
            "t_esperado": self.t_esperado.isoformat(),
            "ultimo_pregao_lido": self.ultimo_pregao_lido.isoformat() if self.ultimo_pregao_lido else None,
        })
        return status

    def aviso_desistencia(self) -> str:
        """Texto da seção 2.4 para o motivo da espera (só faz sentido sem pronto)."""
        motivo = self.decisao.motivo
        if motivo not in _AVISOS_DESISTENCIA:
            raise ValueError(f"motivo {motivo!r} não tem aviso de desistência")
        ultimo = self.ultimo_pregao_lido.isoformat() if self.ultimo_pregao_lido else "nenhum"
        return _AVISOS_DESISTENCIA[motivo].format(
            prazo=self.prazo.strftime("%H:%M"), t_esperado=self.t_esperado.isoformat(), ultimo=ultimo)


class Relogio(Protocol):
    """Relógio injetado: `agora()` devolve datetime com fuso; `dormir()` espera em segundos."""

    def agora(self) -> datetime: ...

    def dormir(self, segundos: float) -> None: ...


class RelogioReal:
    """Relógio de produção (o único lugar com `datetime.now` e `time.sleep` deste módulo)."""

    def agora(self) -> datetime:
        return datetime.now(SP)

    def dormir(self, segundos: float) -> None:
        _relogio_sistema.sleep(segundos)


def _datetime_sp(valor: object) -> datetime | None:
    """Converte para datetime de São Paulo; texto/datetime sem fuso é UTC (como no banco). Ausente vira None."""
    if valor is None or pd.isna(valor):
        return None
    ts = pd.Timestamp(valor)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(SP).to_pydatetime()


def _etapas_da_execucao(painel: Painel, execucao_id: str) -> tuple[dict[str, str | None], dict[str, datetime | None]]:
    """Status e horário de término de cada etapa da ETAPAS_COLETA (ausente = None)."""
    status = {e: None for e in ETAPAS_COLETA}
    final = {e: None for e in ETAPAS_COLETA}
    tabela = painel.etapas.get(execucao_id)
    if tabela is None or tabela.empty:
        return status, final
    for _, linha in tabela.iterrows():
        etapa = linha["etapa_id"]
        if etapa in status:
            status[etapa] = None if pd.isna(linha["status"]) else str(linha["status"])
            final[etapa] = _datetime_sp(linha.get("finalizada_em"))
    return status, final


def _nota_origem(origem: str) -> str:
    if origem == "manual":
        return "Daily manual (origem manual): disparado fora da agenda."
    return f"Daily da agenda (origem {origem})."


def _decisao_sem(motivo: str, nota: str, execucao: dict | None = None) -> Decisao:
    return Decisao(acao="esperar", motivo=motivo, execucao=execucao,
                   etapas={e: None for e in ETAPAS_COLETA}, entrega_concluida_em=None, nota=nota)


def escolher_daily(execucoes: pd.DataFrame, d: date, inicio: time) -> pd.Series | None:
    """Daily que serve para D: tipo `daily`, origem cron/manual, início em D a partir de `inicio` (SP).

    Vale o de maior `iniciada_em`. Outros tipos e origens são ignorados.
    """
    if execucoes is None or execucoes.empty:
        return None
    candidatos = []
    for _, linha in execucoes.iterrows():
        if linha["tipo"] != "daily" or linha["origem"] not in ORIGENS_DAILY:
            continue
        ini = _datetime_sp(linha["iniciada_em"])
        if ini is None or ini.date() != d or ini.time() < inicio:
            continue
        candidatos.append((ini, linha))
    if not candidatos:
        return None
    return max(candidatos, key=lambda c: c[0])[1]


def avaliar_painel(painel: Painel, d: date, t_esperado: date, params: ParametrosRotina) -> Decisao:
    """Decisão de uma leitura do painel (seção 2.2 do plano). Função pura."""
    daily = escolher_daily(painel.execucoes, d, params.inicio_consulta)
    if daily is None:
        return _decisao_sem("sem_daily", "Nenhum daily de hoje encontrado.")

    execucao = {
        "id": daily["id"],
        "origem": daily["origem"],
        "status": daily["status"],
        "iniciada_em": _datetime_sp(daily["iniciada_em"]),
        "finalizada_em": _datetime_sp(daily.get("finalizada_em")),
    }
    nota = _nota_origem(daily["origem"])
    if daily["status"] == "agendada":
        return _decisao_sem("daily_agendado", nota, execucao)

    etapas, final = _etapas_da_execucao(painel, daily["id"])
    if etapas["entrega"] == "concluida":
        ibov_sem_t = painel.ultimo_ibov is None or painel.ultimo_ibov < t_esperado
        if etapas["precos"] != "concluida" and ibov_sem_t:
            return _decisao_sem("dados_atrasados", nota, execucao)
        avisos = []
        for etapa in params.etapas_conferidas:
            if etapas[etapa] != "concluida":
                status_txt = etapas[etapa] or "ausente"
                avisos.append(f"Coleta: etapa {etapa} {status_txt} no daily de hoje; "
                              "os dados podem estar incompletos.")
        if etapas["precos"] == "concluida" and ibov_sem_t:
            ultimo = painel.ultimo_ibov.isoformat() if painel.ultimo_ibov else "nenhum"
            avisos.append(f"Sem preço do IBOV em {t_esperado.isoformat()} (último no banco: {ultimo}): "
                          "a B3 pode não ter aberto nesse dia; conferir feriados_b3 no parametros.yaml.")
        return Decisao(acao="gerar", motivo="entrega_concluida", execucao=execucao, etapas=etapas,
                       entrega_concluida_em=final["entrega"], avisos=avisos, nota=nota)

    if etapas["entrega"] == "falhou" or daily["status"] == "falhou":
        return Decisao(acao="esperar", motivo="entrega_falhou", execucao=execucao, etapas=etapas,
                       entrega_concluida_em=None, nota=nota)
    return Decisao(acao="esperar", motivo="entrega_pendente", execucao=execucao, etapas=etapas,
                   entrega_concluida_em=None, nota=nota)


def _uma_consulta(consultar: Callable[[], Painel], d: date, t_esperado: date,
                  params: ParametrosRotina) -> tuple[Decisao, date | None]:
    """Lê o painel e decide. Erro de leitura vira `falha_consulta`; `ErroSomenteLeitura` sobe."""
    try:
        painel = consultar()
    except fontes.ErroSomenteLeitura:
        raise
    except Exception:
        return _decisao_sem("falha_consulta", "Painel da coleta não lido nesta consulta."), None
    return avaliar_painel(painel, d, t_esperado, params), painel.ultimo_ibov


def esperar_coleta(d: date, t_esperado: date, consultar: Callable[[], Painel], relogio: Relogio,
                   params: ParametrosRotina, *, sem_esperar: bool = False,
                   ao_esgotar_prazo: Callable[[ResultadoGatilho], None] | None = None) -> ResultadoGatilho:
    """Consulta o painel a partir de `inicio_consulta` até ficar pronto ou esgotar o prazo.

    Consultas na grade de `intervalo_minutos`, com uma consulta exatamente no `prazo` (09:45) e no
    `prazo_tardio` (12:00, se houver). Na primeira consulta com `agora >= prazo` sem estar pronto,
    chama `ao_esgotar_prazo` uma vez. Sem `prazo_tardio`, para no `prazo`.
    `sem_esperar`: uma única consulta, sem dormir; sem pronto vira `gerar` com motivo `sem_esperar`.
    """
    prazo = datetime.combine(d, params.prazo, tzinfo=SP)
    limite = datetime.combine(d, params.prazo_tardio, tzinfo=SP) if params.prazo_tardio else prazo
    inicio = datetime.combine(d, params.inicio_consulta, tzinfo=SP)
    intervalo = timedelta(minutes=params.intervalo_minutos)

    consultas = 0
    primeira = ultima = None
    ultimo_lido: date | None = None
    esgotou = False

    def resultado(decisao: Decisao, pronto: bool) -> ResultadoGatilho:
        return ResultadoGatilho(pronto=pronto, decisao=decisao, consultas=consultas,
                                primeira_consulta_em=primeira, ultima_consulta_em=ultima,
                                prazo=prazo, t_esperado=t_esperado, ultimo_pregao_lido=ultimo_lido)

    if sem_esperar:
        agora = relogio.agora()
        decisao, ultimo = _uma_consulta(consultar, d, t_esperado, params)
        consultas, primeira, ultima = 1, agora, agora
        ultimo_lido = ultimo or ultimo_lido
        nota = f"{decisao.nota} Consulta única (--sem-esperar)."
        if decisao.acao == "gerar":
            return resultado(replace(decisao, nota=nota), True)
        aviso = ("Coleta: rodada com --sem-esperar; a coleta de hoje ainda não estava pronta "
                 f"({decisao.motivo}).")
        nova = replace(decisao, acao="gerar", motivo="sem_esperar", avisos=[aviso], nota=nota)
        return resultado(nova, True)

    t = max(relogio.agora(), inicio)
    while True:
        agora = relogio.agora()
        if t > agora:
            relogio.dormir((t - agora).total_seconds())
        agora = relogio.agora()
        decisao, ultimo = _uma_consulta(consultar, d, t_esperado, params)
        consultas += 1
        primeira = primeira or agora
        ultima = agora
        ultimo_lido = ultimo or ultimo_lido

        if decisao.acao == "gerar":
            return resultado(decisao, True)
        if agora >= prazo and not esgotou and ao_esgotar_prazo is not None:
            esgotou = True
            ao_esgotar_prazo(resultado(decisao, False))
        if t >= limite:
            return resultado(decisao, False)

        proxima = t + intervalo
        if t < prazo:
            proxima = min(proxima, prazo)
        t = min(proxima, limite)
