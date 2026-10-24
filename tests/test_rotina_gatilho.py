"""Testes do gatilho da rotina diária (plano da etapa 8, seções 2 e 3; fase 3).

Simulam a manhã inteira com `RelogioFalso` e `linha_do_tempo` (tests/fabrica_rotina.py): nada de rede,
banco, `.env` ou espera real. D = 2026-10-26 (segunda), t esperado = 2026-10-23 (sexta).
"""

from datetime import date, datetime, time
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from fabrica_rotina import RelogioFalso, etapas, execucao, linha_do_tempo, painel
from processamento import fontes
from processamento.diagnostico.esperado import ETAPAS_COLETA
from processamento.rotina.gatilho import (
    MOTIVOS,
    Decisao,
    ResultadoGatilho,
    avaliar_painel,
    escolher_daily,
    esperar_coleta,
)
from processamento.rotina.parametros import ParametrosChecagem, ParametrosRotina
from processamento.saida.contrato import MOTIVOS_COLETA

D = date(2026, 10, 26)
T = date(2026, 10, 23)
ID_CRON = "2026-10-26-daily-080001"
INI_CRON = "2026-10-26 11:00:01.489947"            # 08:00:01 SP
ID_MANUAL = "2026-10-26-daily-091000"
INI_MANUAL = "2026-10-26 12:10:00"                 # 09:10 SP


def sp(h: int, m: int = 0, s: int = 0) -> datetime:
    return datetime(2026, 10, 26, h, m, s, tzinfo=fontes.SP)


def _params(prazo_tardio: time | None = time(12, 0)) -> ParametrosRotina:
    return ParametrosRotina(
        inicio_consulta=time(8, 0), intervalo_minutos=5, prazo=time(9, 45), prazo_tardio=prazo_tardio,
        etapas_conferidas=("precos", "noticias", "enriquecimento"), pasta_logs=Path("logs-teste"),
        trava=Path("trava-teste"), trava_validade_horas=6.0, aviso_calendario_dias=30,
        checagem=ParametrosChecagem(0.9, 0.30, 5, 10),
    )


def _status(**mudancas: str) -> dict[str, str]:
    """Todas as etapas concluídas, `analise` pendente (como no caso A); `mudancas` sobrescreve."""
    base = {e: "concluida" for e in ETAPAS_COLETA if e != "analise"}
    base["analise"] = "pendente"
    base.update(mudancas)
    return base


def _dia(*, entrega: str = "em_andamento", fim_entrega: str | None = None, daily_status: str = "em_andamento",
         origem: str = "cron", iniciada: str = INI_CRON, id_: str = ID_CRON, ultimo: date | None = T,
         extra: dict[str, str] | None = None):
    """Painel com um único daily de D (padrão: cron 08:00:01, entrega em andamento)."""
    status = _status(entrega=entrega, **(extra or {}))
    fim = {"entrega": fim_entrega} if fim_entrega else None
    return painel([execucao(id_, iniciada, origem=origem, status=daily_status)],
                  {id_: etapas(id_, status, fim)}, ultimo)


def _rodar(estados, relogio, *, params=None, sem_esperar=False):
    """Roda `esperar_coleta` sobre a linha do tempo; devolve (resultado, chamadas de ao_esgotar, registro)."""
    base = linha_do_tempo(relogio, estados)
    params = params or _params()
    registro = []

    def consultar():
        lido = base()
        registro.append((relogio.agora(), avaliar_painel(lido, D, T, params).motivo))
        return lido

    chamadas = []
    resultado = esperar_coleta(D, T, consultar, relogio, params, sem_esperar=sem_esperar,
                               ao_esgotar_prazo=chamadas.append)
    return resultado, chamadas, registro


# ---------------------------------------------------------------------------
# Casos da seção 3 do plano
# ---------------------------------------------------------------------------

def test_caso_a_entrega_as_0805_pronto_na_segunda_consulta():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(8, 5), _dia(entrega="concluida", fim_entrega="2026-10-26 11:05:00"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is True
    assert resultado.consultas == 2
    assert resultado.espera_segundos() == 300
    assert chamadas == []
    assert resultado.decisao.motivo == "entrega_concluida"
    assert resultado.decisao.acao == "gerar"
    assert resultado.coleta_status() == {
        "consultado": True, "nota": "Daily da agenda (origem cron).", "motivo": "entrega_concluida",
        "execucao_id": "2026-10-26-daily-080001", "origem": "cron", "status_execucao": "em_andamento",
        "iniciada_em": "2026-10-26T08:00:01-03:00", "finalizada_em": None,
        "entrega_concluida_em": "2026-10-26T08:05:00-03:00",
        "etapas": {"precos": "concluida", "macro": "concluida", "noticias": "concluida", "ipe": "concluida",
                   "enriquecimento": "concluida", "juiza": "concluida", "cadastro": "concluida",
                   "entrega": "concluida", "analise": "pendente"},
        "consultas": 2, "primeira_consulta_em": "2026-10-26T08:00:00-03:00",
        "ultima_consulta_em": "2026-10-26T08:05:00-03:00", "espera_segundos": 300,
        "prazo": "2026-10-26T09:45:00-03:00", "t_esperado": "2026-10-23", "ultimo_pregao_lido": "2026-10-23",
    }


def test_caso_b_entrega_as_0950_depois_do_prazo_com_aviso():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(9, 50), _dia(entrega="concluida", fim_entrega="2026-10-26 12:50:00"))]
    resultado, chamadas, registro = _rodar(estados, relogio)

    assert resultado.pronto is True
    assert resultado.consultas == 23
    assert resultado.espera_segundos() == 6600
    assert len(chamadas) == 1
    assert chamadas[0].consultas == 22
    assert chamadas[0].decisao.motivo == "entrega_pendente"
    assert chamadas[0].pronto is False
    assert registro[21] == (sp(9, 45), "entrega_pendente")


def test_caso_b2_sem_prazo_tardio_para_as_0945():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(9, 50), _dia(entrega="concluida", fim_entrega="2026-10-26 12:50:00"))]
    resultado, chamadas, _ = _rodar(estados, relogio, params=_params(prazo_tardio=None))

    assert resultado.pronto is False
    assert resultado.consultas == 22
    assert resultado.espera_segundos() == 6300
    assert resultado.decisao.motivo == "entrega_pendente"
    assert len(chamadas) == 1


def test_caso_c_entrega_nunca_conclui_consulta_ate_1200():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is False
    assert resultado.consultas == 49
    assert resultado.espera_segundos() == 14400
    assert len(chamadas) == 1
    assert chamadas[0].consultas == 22
    assert chamadas[0].decisao.motivo == "entrega_pendente"


def test_caso_d_daily_manual_das_0910_pronto_as_0930():
    relogio = RelogioFalso(sp(8, 0))
    estados = [
        (sp(9, 10), _dia(id_=ID_MANUAL, iniciada=INI_MANUAL, origem="manual", entrega="em_andamento")),
        (sp(9, 30), _dia(id_=ID_MANUAL, iniciada=INI_MANUAL, origem="manual", entrega="concluida",
                         fim_entrega="2026-10-26 12:30:00")),
    ]
    resultado, chamadas, registro = _rodar(estados, relogio)

    assert all(motivo == "sem_daily" for hora, motivo in registro if hora < sp(9, 10))
    assert resultado.pronto is True
    assert resultado.consultas == 19
    assert resultado.espera_segundos() == 5400
    assert resultado.decisao.execucao["origem"] == "manual"
    assert resultado.decisao.nota == "Daily manual (origem manual): disparado fora da agenda."
    assert resultado.decisao.avisos == []
    assert chamadas == []


def test_caso_e_armadilha_do_fuso_00h30_utc_e_dia_anterior():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0), painel(
        [execucao(ID_CRON, "2026-10-26 00:30:00", status="concluida")],
        {ID_CRON: etapas(ID_CRON, _status(entrega="concluida"),
                         {"entrega": "2026-10-26 00:40:00"})}, T))]
    base = linha_do_tempo(relogio, estados)

    assert escolher_daily(base().execucoes, D, time(8, 0)) is None
    resultado, chamadas, _ = _rodar(estados, relogio)
    assert resultado.pronto is False
    assert len(chamadas) == 1
    assert chamadas[0].decisao.motivo == "sem_daily"


def test_caso_f_armadilha_do_fuso_10h50_utc_sao_0750_sp():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0), painel(
        [execucao(ID_CRON, "2026-10-26 10:50:00", status="em_andamento")],
        {ID_CRON: etapas(ID_CRON, _status(entrega="concluida"), {"entrega": "2026-10-26 11:30:00"})}, T))]
    base = linha_do_tempo(relogio, estados)

    assert escolher_daily(base().execucoes, D, time(8, 0)) is None
    resultado, chamadas, _ = _rodar(estados, relogio)
    assert resultado.pronto is False
    assert chamadas[0].decisao.motivo == "sem_daily"


def test_caso_g_cron_falhou_e_manual_das_0900_pronto_as_0925():
    relogio = RelogioFalso(sp(8, 0))
    cron = execucao(ID_CRON, INI_CRON, status="em_andamento")
    manual = execucao(ID_MANUAL, "2026-10-26 12:00:00", origem="manual", status="em_andamento")
    estados = [
        (sp(8, 0, 1), _dia(entrega="em_andamento")),
        (sp(8, 40), _dia(entrega="falhou")),
        (sp(9, 0), painel([cron, manual],
                          {ID_CRON: etapas(ID_CRON, _status(entrega="falhou")),
                           ID_MANUAL: etapas(ID_MANUAL, _status(entrega="em_andamento"))}, T)),
        (sp(9, 25), painel([cron, manual],
                           {ID_CRON: etapas(ID_CRON, _status(entrega="falhou")),
                            ID_MANUAL: etapas(ID_MANUAL, _status(entrega="concluida"),
                                              {"entrega": "2026-10-26 12:25:00"})}, T)),
    ]
    resultado, _, registro = _rodar(estados, relogio)

    falhou = [hora.strftime("%H:%M") for hora, motivo in registro if motivo == "entrega_falhou"]
    assert falhou == ["08:40", "08:45", "08:50", "08:55"]
    assert registro[12] == (sp(9, 0), "entrega_pendente")
    assert resultado.pronto is True
    assert resultado.decisao.execucao["id"] == ID_MANUAL
    assert resultado.consultas == 18


def test_caso_h_entrega_falhou_sem_outro_daily_esgota_o_prazo_com_motivo_falhou():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(8, 40), _dia(entrega="falhou"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is False
    assert resultado.consultas == 49
    assert len(chamadas) == 1
    assert chamadas[0].decisao.motivo == "entrega_falhou"


def test_caso_i_daily_parcial_com_analise_falhou_nao_gera_aviso():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(9, 10), _dia(entrega="concluida", fim_entrega="2026-10-26 12:10:00",
                                daily_status="parcial", extra={"analise": "falhou"}))]
    resultado, _, _ = _rodar(estados, relogio)

    assert resultado.pronto is True
    assert resultado.consultas == 15
    assert resultado.decisao.avisos == []


def test_caso_j_enriquecimento_falhou_gera_aviso_e_pronto_as_0900():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(9, 0), _dia(entrega="concluida", fim_entrega="2026-10-26 12:00:00",
                               extra={"enriquecimento": "falhou"}))]
    resultado, _, _ = _rodar(estados, relogio)

    assert resultado.pronto is True
    assert resultado.consultas == 13
    assert resultado.decisao.avisos == [
        "Coleta: etapa enriquecimento falhou no daily de hoje; os dados podem estar incompletos."]


def test_caso_k_daily_agendado_a_manha_toda_esgota_com_motivo_agendado():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(daily_status="agendada"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is False
    assert len(chamadas) == 1
    assert chamadas[0].decisao.motivo == "daily_agendado"
    assert resultado.decisao.motivo == "daily_agendado"


def test_caso_k2_agendado_ate_0920_depois_em_andamento_pronto_as_1030():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(daily_status="agendada")),
               (sp(9, 20), _dia(entrega="em_andamento")),
               (sp(10, 30), _dia(entrega="concluida", fim_entrega="2026-10-26 13:30:00"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert len(chamadas) == 1
    assert chamadas[0].consultas == 22
    assert chamadas[0].decisao.motivo == "entrega_pendente"
    assert resultado.pronto is True
    assert resultado.consultas == 31


def test_caso_l_precos_falhou_com_ibov_de_22_esgota_com_dados_atrasados_e_texto():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento", ultimo=date(2026, 10, 22))),
               (sp(9, 0), _dia(entrega="concluida", fim_entrega="2026-10-26 12:00:00",
                               ultimo=date(2026, 10, 22), extra={"precos": "falhou"}))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is False
    assert len(chamadas) == 1
    assert chamadas[0].decisao.motivo == "dados_atrasados"
    assert resultado.ultimo_pregao_lido == date(2026, 10, 22)
    assert resultado.aviso_desistencia() == (
        "Coleta: preços de 2026-10-23 ainda não chegaram (último pregão no banco: 2026-10-22); "
        "pacotes de hoje não gerados.")


def test_caso_l2_precos_ok_com_ibov_de_22_pronto_com_aviso_do_ibov():
    relogio = RelogioFalso(sp(8, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento", ultimo=date(2026, 10, 22))),
               (sp(9, 0), _dia(entrega="concluida", fim_entrega="2026-10-26 12:00:00",
                               ultimo=date(2026, 10, 22)))]
    resultado, _, _ = _rodar(estados, relogio)

    assert resultado.pronto is True
    assert resultado.consultas == 13
    assert resultado.decisao.avisos == [
        "Sem preço do IBOV em 2026-10-23 (último no banco: 2026-10-22): a B3 pode não ter aberto nesse dia; "
        "conferir feriados_b3 no parametros.yaml."]


def test_caso_m_relogio_comeca_0837_usa_a_hora_atual_e_a_grade_a_partir_dela():
    relogio = RelogioFalso(sp(8, 37))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(8, 50), _dia(entrega="concluida", fim_entrega="2026-10-26 11:50:00"))]
    resultado, _, registro = _rodar(estados, relogio)

    assert [hora for hora, _ in registro] == [sp(8, 37), sp(8, 42), sp(8, 47), sp(8, 52)]
    assert resultado.pronto is True
    assert resultado.consultas == 4
    assert resultado.espera_segundos() == 900


def test_caso_n_relogio_comeca_0730_dorme_1800_s_e_consulta_as_0800():
    relogio = RelogioFalso(sp(7, 30))
    estados = [(sp(8, 0, 1), _dia(entrega="concluida", fim_entrega="2026-10-26 11:00:01"))]
    resultado, _, registro = _rodar(estados, relogio)

    assert relogio.sonos[0] == 1800
    assert registro[0][0] == sp(8, 0)
    assert resultado.primeira_consulta_em == sp(8, 0)


def test_caso_o_pc_ligado_as_1100_com_entrega_das_0900_pronto_na_primeira_consulta():
    relogio = RelogioFalso(sp(11, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento")),
               (sp(9, 0), _dia(entrega="concluida", fim_entrega="2026-10-26 12:00:00"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is True
    assert resultado.consultas == 1
    assert chamadas == []
    assert relogio.sonos == []


def test_caso_o2_pc_ligado_as_1100_sem_entrega_esgota_na_primeira_consulta():
    relogio = RelogioFalso(sp(11, 0))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento"))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert resultado.pronto is False
    assert resultado.consultas == 13
    assert len(chamadas) == 1
    assert chamadas[0].consultas == 1


def test_caso_p_erro_do_banco_nao_sobe_e_a_consulta_seguinte_funciona():
    relogio = RelogioFalso(sp(8, 0))
    base = linha_do_tempo(relogio, [(sp(8, 0, 1), _dia(entrega="em_andamento")),
                                    (sp(8, 5), _dia(entrega="concluida", fim_entrega="2026-10-26 11:05:00"))])

    def consultar():
        if relogio.agora() < sp(8, 5):
            raise OperationalError("SELECT 1", {}, Exception("banco fora do ar"))
        return base()

    params = _params()
    resultado = esperar_coleta(D, T, consultar, relogio, params)

    assert resultado.pronto is True
    assert resultado.consultas == 2


def test_caso_p2_erro_de_somente_leitura_sobe_na_hora_sem_esperar():
    relogio = RelogioFalso(sp(8, 0))

    def consultar():
        raise fontes.ErroSomenteLeitura("escrita recusada")

    with pytest.raises(fontes.ErroSomenteLeitura):
        esperar_coleta(D, T, consultar, relogio, _params())
    assert relogio.sonos == []


def test_caso_q_execucao_coletar_nao_serve_de_daily():
    relogio = RelogioFalso(sp(8, 0))
    coletar = execucao("2026-10-26-coletar-091500", "2026-10-26 12:00:00", tipo="coletar", origem="manual",
                       status="concluida", finalizada_utc="2026-10-26 12:00:00")
    estados = [(sp(9, 0), painel([coletar], {}, T))]
    resultado, chamadas, _ = _rodar(estados, relogio)

    assert escolher_daily(painel([coletar], {}, T).execucoes, D, time(8, 0)) is None
    assert resultado.pronto is False
    assert chamadas[0].decisao.motivo == "sem_daily"


def test_caso_r_sem_esperar_uma_consulta_e_gera_com_aviso():
    relogio = RelogioFalso(sp(8, 10))
    estados = [(sp(8, 0, 1), _dia(entrega="em_andamento"))]
    resultado, chamadas, registro = _rodar(estados, relogio, sem_esperar=True)

    assert len(registro) == 1
    assert relogio.sonos == []
    assert resultado.pronto is True
    assert resultado.consultas == 1
    assert resultado.decisao.motivo == "sem_esperar"
    assert resultado.decisao.acao == "gerar"
    assert resultado.decisao.avisos == [
        "Coleta: rodada com --sem-esperar; a coleta de hoje ainda não estava pronta (entrega_pendente)."]
    assert resultado.decisao.nota.endswith(" Consulta única (--sem-esperar).")
    assert resultado.coleta_status()["motivo"] == "sem_esperar"
    assert chamadas == []


# ---------------------------------------------------------------------------
# Testes extras: escolha do daily, nota, textos e motivos
# ---------------------------------------------------------------------------

def test_escolher_daily_ignora_tipos_e_origens_que_nao_servem():
    brutas = [
        execucao("2026-10-26-coletar-1", "2026-10-26 12:30:00", tipo="coletar", origem="manual"),
        execucao("2026-10-26-etapa-1", "2026-10-26 12:31:00", tipo="etapa", origem="cron"),
        execucao("2026-10-26-daily-outra", "2026-10-26 12:32:00", origem="outra"),
    ]
    assert escolher_daily(painel(brutas, {}, T).execucoes, D, time(8, 0)) is None

    com_cron = painel(brutas + [execucao(ID_CRON, INI_CRON)], {}, T)
    escolhido = escolher_daily(com_cron.execucoes, D, time(8, 0))
    assert escolhido is not None
    assert escolhido["id"] == ID_CRON


def test_escolher_daily_vale_o_de_maior_inicio_entre_cron_e_manual():
    dois = painel([execucao(ID_CRON, INI_CRON), execucao(ID_MANUAL, INI_MANUAL, origem="manual")], {}, T)
    assert escolher_daily(dois.execucoes, D, time(8, 0))["id"] == ID_MANUAL


def test_avaliar_painel_nota_de_daily_manual():
    decisao = avaliar_painel(
        _dia(id_=ID_MANUAL, iniciada=INI_MANUAL, origem="manual", entrega="em_andamento"),
        D, T, _params())
    assert decisao.nota == "Daily manual (origem manual): disparado fora da agenda."
    assert decisao.motivo == "entrega_pendente"


def test_motivos_batem_com_o_contrato():
    assert MOTIVOS == MOTIVOS_COLETA
    assert len(MOTIVOS) == 8


@pytest.mark.parametrize("motivo, esperado", [
    ("sem_daily", "Coleta: nenhum daily de hoje (a partir das 08:00) até 09:45; pacotes de hoje não gerados."),
    ("daily_agendado", "Coleta: o daily de hoje ainda não começou até 09:45 (aguardando a carga histórica); "
                       "pacotes de hoje não gerados."),
    ("entrega_pendente", "Coleta: a entrega de hoje não terminou até 09:45; pacotes de hoje não gerados."),
    ("entrega_falhou", "Coleta: a etapa entrega falhou no daily de hoje; pacotes de hoje não gerados."),
    ("dados_atrasados", "Coleta: preços de 2026-10-23 ainda não chegaram (último pregão no banco: 2026-10-22); "
                        "pacotes de hoje não gerados."),
    ("falha_consulta", "Coleta: o painel da coleta não pôde ser lido até 09:45; pacotes de hoje não gerados."),
])
def test_aviso_desistencia_tem_o_texto_de_cada_motivo(motivo, esperado):
    decisao = Decisao(acao="esperar", motivo=motivo, execucao=None,
                      etapas={e: None for e in ETAPAS_COLETA}, entrega_concluida_em=None)
    resultado = ResultadoGatilho(pronto=False, decisao=decisao, consultas=22, primeira_consulta_em=sp(8, 0),
                                 ultima_consulta_em=sp(9, 45), prazo=sp(9, 45), t_esperado=T,
                                 ultimo_pregao_lido=date(2026, 10, 22))
    assert resultado.aviso_desistencia() == esperado


def test_aviso_desistencia_recusa_motivo_que_nao_e_espera():
    decisao = Decisao(acao="gerar", motivo="entrega_concluida", execucao=None,
                      etapas={e: None for e in ETAPAS_COLETA}, entrega_concluida_em=None)
    resultado = ResultadoGatilho(pronto=True, decisao=decisao, consultas=1, primeira_consulta_em=sp(8, 0),
                                 ultima_consulta_em=sp(8, 0), prazo=sp(9, 45), t_esperado=T)
    with pytest.raises(ValueError):
        resultado.aviso_desistencia()
