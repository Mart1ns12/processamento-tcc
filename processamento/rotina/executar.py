"""Rotina diária: `python -m processamento.rotina` (plano da etapa 8, seção 11; fase 8).

Fluxo de uma rodada de D: trava -> D é pregão previsto? -> t esperado -> espera a coleta (gatilho) ->
gera os pacotes (`gerar.gerar`) ou, sem entrega até o prazo, grava só o `execucao.json` `falhou`.
Códigos de saída: 0 = `ok`, `parcial` ou dia sem pregão; 2 = configuração; 3 = conexão ou sessão que
não é somente leitura; 4 = `falhou`; 5 = outra rotina em andamento (trava).

O relógio é injetado (`RelogioReal` em produção). Nenhum SQL aqui: a leitura passa por `ler` (ou
`fontes.executar_leitura`, via `exp_dataset._leitor_padrao`).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

from processamento import calendario, fontes
from processamento.experimento import dataset as exp_dataset
from processamento.experimento import treino
from processamento.experimento.parametros import ErroParametrosExperimento, carregar_parametros_treino
from processamento.rotina import retreino
from processamento.rotina.gatilho import ORIGENS_DAILY, Painel, RelogioReal, avaliar_painel, esperar_coleta
from processamento.rotina.parametros import ErroParametrosRotina, ParametrosRotina, carregar_parametros_rotina
from processamento.rotina.trava import ErroTrava, trava
from processamento.saida import gerar
from processamento.saida.contrato import SP
from processamento.saida.insumos import ErroSaida
from processamento.saida.parametros import ErroParametrosSaida, carregar_parametros_saida

log = logging.getLogger("processamento.rotina")  # pai de processamento.rotina.trava: o log da rodada recebe os dois

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ERROS_DE_CONFIGURACAO = (
    ErroParametrosRotina, ErroParametrosSaida, ErroParametrosExperimento, calendario.ErroCalendario,
    fontes.ErroConfiguracao,
)


@dataclass
class ResultadoRotina:
    """Resultado de uma rodada: código de saída, status e a pasta de D (None se não gravou nada)."""

    codigo: int
    status: str            # "sem_pregao", "ok", "parcial", "falhou", "trava", "configuracao", "sem_banco"
    d: date
    pasta: Path | None


class _Parar(Exception):
    """Interrompe a rodada com um resultado pronto (conexão, sessão ou configuração)."""

    def __init__(self, resultado: ResultadoRotina):
        super().__init__(resultado.status)
        self.resultado = resultado


def _data_argumento(texto: str) -> date:
    """Data em AAAA-MM-DD para o argparse."""
    try:
        return date.fromisoformat(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"data inválida (use AAAA-MM-DD): {texto}") from e


def montar_consulta(ler, d: date) -> Callable[[], Painel]:
    """Função `consultar` do gatilho: lê o painel de D, as etapas de cada daily de D e o último IBOV <= D − 1.

    As etapas são lidas para todos os dailys de D (não só o escolhido), para que a decisão de
    `avaliar_painel` tenha as etapas de qualquer daily que ela possa escolher.
    """
    inicio_utc = datetime.combine(d, time(0), tzinfo=SP)

    def consultar() -> Painel:
        execucoes = fontes.ler_painel_execucoes(inicio_utc, ler=ler)
        etapas = {}
        for _, linha in execucoes.iterrows():
            if linha["tipo"] != "daily" or linha["origem"] not in ORIGENS_DAILY:
                continue
            if pd.isna(linha["iniciada_em"]) or pd.Timestamp(linha["iniciada_em"]).date() != d:
                continue
            etapas[linha["id"]] = fontes.ler_painel_etapas(linha["id"], ler=ler)
        ultimo = fontes.ultimo_pregao_ibov(d - timedelta(days=1), ler=ler)
        return Painel(execucoes=execucoes, etapas=etapas, ultimo_ibov=ultimo)

    return consultar


def _texto_consulta(n: int, instante: datetime, painel: Painel, d: date, t_esperado: date,
                    params: ParametrosRotina) -> str:
    """Uma linha do log por consulta (seção 11): daily escolhido, status da entrega e a decisão."""
    decisao = avaliar_painel(painel, d, t_esperado, params)
    if decisao.execucao is None:
        quem = "nenhum daily de hoje"
    else:
        quem = f"daily {decisao.execucao['id']} ({decisao.execucao['origem']}, {decisao.execucao['status']})"
    entrega = decisao.etapas.get("entrega") or "ausente"
    acao = "gerar" if decisao.acao == "gerar" else f"esperar ({decisao.motivo})"
    return f"{instante:%H:%M:%S} consulta {n}: {quem}, entrega {entrega} -> {acao}"


@contextmanager
def _log_da_rodada(pasta_logs: Path, d: date) -> Iterator[None]:
    """Log da rodada no arquivo `logs/rotina-AAAA-MM-DD.log` e no console; os handlers saem no fim."""
    Path(pasta_logs).mkdir(parents=True, exist_ok=True)
    arquivo = logging.FileHandler(Path(pasta_logs) / f"rotina-{d.isoformat()}.log", encoding="utf-8")
    console = logging.StreamHandler(sys.stdout)
    formato = logging.Formatter("%(message)s")
    handlers = (arquivo, console)
    for handler in handlers:
        handler.setFormatter(formato)
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        yield
    finally:
        for handler in handlers:
            log.removeHandler(handler)
            handler.close()


def _definir_estado_de_energia(flags: int) -> None:
    """Pede ao Windows para não suspender (ou desfaz). Fora do Windows não faz nada; nunca levanta erro."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


@contextmanager
def _manter_acordado() -> Iterator[None]:
    """Enquanto espera a coleta, o PC não suspende (Windows); desfeito ao sair."""
    _definir_estado_de_energia(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        _definir_estado_de_energia(_ES_CONTINUOUS)


def _abrir_leitor():
    """Leitor somente leitura da coleta. Erros viram código 2 (configuração) ou 3 (conexão/sessão)."""
    try:
        return exp_dataset._leitor_padrao()
    except fontes.ErroConfiguracao as erro:
        log.info(f"Configuração do banco incompleta: {erro}")
        raise _Parar(ResultadoRotina(2, "configuracao", None, None)) from None
    except fontes.ErroSomenteLeitura as erro:
        log.info(f"{erro}. A coleta não foi alterada.")
        raise _Parar(ResultadoRotina(3, "sem_banco", None, None)) from None
    except Exception as erro:
        # Não mostra a mensagem original: ela pode conter host ou usuário.
        log.info(f"Falha ao conectar ao banco ({type(erro).__name__}). Nada foi gravado.")
        raise _Parar(ResultadoRotina(3, "sem_banco", None, None)) from None


def _gancho_retreino(pasta_modelos: Path, params_treino, relogio) -> Callable[[pd.DataFrame, dict, list, date], list[str]]:
    """Gancho do `gerar` (seção 7): só chama o retreino quando ele é preciso (`precisa_retreinar`)."""
    def gancho(df: pd.DataFrame, info: dict, cal: list, d: date) -> list[str]:
        if not retreino.precisa_retreinar(pasta_modelos, d, params_treino.teste_final_fim):
            return []
        return retreino.retreinar_mes(df, info, cal, d, pasta_modelos=pasta_modelos, params=params_treino,
                                      agora=relogio.agora())
    return gancho


def _rodar(d: date, *, relogio, params: ParametrosRotina, params_treino, params_saida, ler, consultar,
           sem_esperar: bool, pasta_dia: Path, pasta_modelos: Path, pasta_registros: Path,
           pasta_estado: Path, existe_composicao: bool | None) -> ResultadoRotina:
    """Corpo da rodada (depois da trava e do log). Levanta `_Parar` para os códigos de parada."""
    if not calendario.e_pregao_previsto(d):
        log.info(f"{d.isoformat()} não é pregão previsto ({calendario.motivo_sem_pregao(d)}): nada a gerar.")
        return ResultadoRotina(0, "sem_pregao", d, None)

    avisos_cal = calendario.avisos_validade(d, dias=params.aviso_calendario_dias)
    for aviso in avisos_cal:
        log.info(f"Aviso: {aviso}")
    t_esperado = calendario.pregao_anterior_previsto(d)
    leitor = ler if ler is not None else (_abrir_leitor() if consultar is None else None)
    consulta_base = consultar if consultar is not None else montar_consulta(leitor, d)

    contador = 0

    def consultar_logado() -> Painel:
        nonlocal contador
        contador += 1
        instante = relogio.agora()
        try:
            painel = consulta_base()
        except fontes.ErroSomenteLeitura:
            raise
        except Exception:
            # Sem o texto do erro: a mensagem pode conter host ou usuário do banco.
            log.info(f"{instante:%H:%M:%S} consulta {contador}: painel da coleta não lido")
            raise
        log.info(_texto_consulta(contador, instante, painel, d, t_esperado, params))
        return painel

    def ao_esgotar_prazo(parcial) -> None:
        aviso = parcial.aviso_desistencia()
        log.info(aviso)
        gerar.registrar_execucao(
            d, "falhou", coleta_status=parcial.coleta_status(), avisos=[aviso, *avisos_cal],
            agora=relogio.agora(), pasta_saida=pasta_dia, params_saida=params_saida,
        )

    with _manter_acordado():
        res = esperar_coleta(d, t_esperado, consultar_logado, relogio, params, sem_esperar=sem_esperar,
                             ao_esgotar_prazo=ao_esgotar_prazo)

    if not res.pronto:
        if params.prazo_tardio is not None:
            log.info(f"Coleta não terminou até {params.prazo_tardio:%H:%M}: pacotes de hoje não gerados.")
        return ResultadoRotina(4, "falhou", d, pasta_dia)

    try:
        pasta = gerar.gerar(
            d, ler=leitor, pasta_saida=pasta_dia, pasta_modelos=pasta_modelos, pasta_registros=pasta_registros,
            pasta_estado=pasta_estado, usar_estado=True, agora=relogio.agora(),
            coleta_status=res.coleta_status(), avisos_coleta=[*res.decisao.avisos, *avisos_cal],
            existe_composicao=existe_composicao, params_treino=params_treino, params_saida=params_saida,
            retreinar=_gancho_retreino(pasta_modelos, params_treino, relogio), checagem=params.checagem,
        )
    except ErroSaida as erro:
        log.info(f"Saída não gerada: {erro}")
        return ResultadoRotina(4, "falhou", d, pasta_dia)

    execucao = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))["registros"][0]
    log.info(f"Saída de {d.isoformat()} em {pasta}: status {execucao['status']}")
    for aviso in execucao["avisos"]:
        log.info(f"- {aviso}")
    codigo = 4 if execucao["status"] == "falhou" else 0
    return ResultadoRotina(codigo, execucao["status"], d, pasta)


def executar_rotina(d: date | None, *, relogio, ler=None, consultar=None, sem_esperar: bool = False,
                    params_rotina: ParametrosRotina | None = None, params_treino=None, params_saida=None,
                    pasta_saida: Path | None = None, pasta_modelos: Path | None = None,
                    pasta_registros: Path | None = None, pasta_estado: Path | None = None,
                    existe_composicao: bool | None = None) -> ResultadoRotina:
    """Uma rodada da rotina diária. `d` None = hoje em São Paulo. Devolve o `ResultadoRotina` (código e status).

    `pasta_saida` é a raiz (`saida/`); a pasta do dia é `pasta_saida / D`. `ler` é o leitor somente leitura
    (testes); `consultar` substitui a leitura do painel (testes). Sem eles, usa a conexão da coleta.
    """
    agora = relogio.agora()
    d = agora.astimezone(SP).date() if d is None else d
    try:
        params = carregar_parametros_rotina() if params_rotina is None else params_rotina
        params_treino = carregar_parametros_treino() if params_treino is None else params_treino
        params_saida = carregar_parametros_saida() if params_saida is None else params_saida
    except _ERROS_DE_CONFIGURACAO as erro:
        print(f"Configuração inválida: {erro}")
        return ResultadoRotina(2, "configuracao", d, None)

    raiz = params_saida.pasta if pasta_saida is None else Path(pasta_saida)
    pasta_dia = raiz / d.isoformat()
    modelos_dir = treino.PASTA_MODELOS_PADRAO if pasta_modelos is None else Path(pasta_modelos)
    registros_dir = params_saida.pasta_registros if pasta_registros is None else Path(pasta_registros)
    estado_dir = params_saida.pasta_estado if pasta_estado is None else Path(pasta_estado)
    caminho_trava = params.trava if pasta_estado is None else estado_dir / "rotina.trava"

    with _log_da_rodada(params.pasta_logs, d):
        log.info(f"Rotina de {d.isoformat()} (início {agora:%H:%M:%S}{', --sem-esperar' if sem_esperar else ''})")
        try:
            with trava(caminho_trava, agora, params.trava_validade_horas):
                return _rodar(
                    d, relogio=relogio, params=params, params_treino=params_treino, params_saida=params_saida,
                    ler=ler, consultar=consultar, sem_esperar=sem_esperar, pasta_dia=pasta_dia,
                    pasta_modelos=modelos_dir, pasta_registros=registros_dir, pasta_estado=estado_dir,
                    existe_composicao=existe_composicao,
                )
        except ErroTrava as erro:
            log.info(f"{erro}. Rodada cancelada; nada foi gravado.")
            return ResultadoRotina(5, "trava", d, None)
        except _Parar as parada:
            return ResultadoRotina(parada.resultado.codigo, parada.resultado.status, d, None)
        except fontes.ErroSomenteLeitura as erro:
            # Não é engolida: a rotina para com código 3 (a sessão do banco não está em somente leitura).
            log.info(f"{erro}. Rodada interrompida; a coleta não foi alterada.")
            return ResultadoRotina(3, "sem_banco", d, None)


def main(argv=None, *, relogio=None, ler=None, consultar=None, existe_composicao: bool | None = None) -> int:
    """Ponto de entrada (`python -m processamento.rotina`). Devolve o código da rodada (ver o módulo)."""
    parser = argparse.ArgumentParser(
        prog="python -m processamento.rotina",
        description="Rotina diária: espera a coleta de D e gera os pacotes. Só lê o banco da coleta.",
    )
    parser.add_argument("--data", type=_data_argumento, default=None,
                        help="D: pregão previsto (AAAA-MM-DD); sem ele, hoje (São Paulo)")
    parser.add_argument("--sem-esperar", action="store_true",
                        help="uma consulta ao painel e gera na hora, sem prazo nem rodada tardia")
    parser.add_argument("--pasta", type=Path, default=None,
                        help="pasta raiz da saída (padrão: parametros.yaml); os pacotes vão para PASTA/AAAA-MM-DD")
    parser.add_argument("--pasta-modelos", type=Path, default=None, help="pasta dos modelos (padrão: modelos)")
    parser.add_argument("--pasta-registros", type=Path, default=None,
                        help="pasta dos registros do experimento (padrão: parametros.yaml)")
    args = parser.parse_args(argv)
    relogio = RelogioReal() if relogio is None else relogio
    resultado = executar_rotina(
        args.data, relogio=relogio, ler=ler, consultar=consultar, sem_esperar=args.sem_esperar,
        pasta_saida=args.pasta, pasta_modelos=args.pasta_modelos, pasta_registros=args.pasta_registros,
        existe_composicao=existe_composicao,
    )
    return resultado.codigo
