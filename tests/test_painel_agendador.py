"""Testes de processamento/painel/agendador.py (texto e próxima execução do Agendador de Tarefas).

Usa o calendário real (processamento/config/parametros.yaml), só leitura. Sem banco, sem rede e sem schtasks.
"""

from __future__ import annotations

from datetime import datetime

from processamento.calendario import SP
from processamento.painel import agendador

CFG = {"dias": ["seg", "ter", "qua", "qui", "sex"], "hora": "07:55"}


def _agora(ano, mes, dia, hora, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=SP)


def test_proxima_execucao_e_amanha_quando_ainda_nao_passou_do_horario():
    b = agendador.bloco_agendador(CFG, _agora(2026, 11, 3, 19, 42))
    assert b["configurado"] is True
    assert b["proxima"] == "2026-11-04T07:55:00-03:00"
    assert b["proxima_texto"] == "qua 04/11 07:55"
    assert b["texto"] == "Agendador: seg a sex, 07:55 · próxima qua 04/11"
    assert b["proxima_pregao"] is True
    assert b["detalhe"] is None
    assert b["dias_semana"] == [0, 1, 2, 3, 4]
    assert b["hora"] == "07:55"


def test_proxima_execucao_e_hoje_quando_ainda_nao_passou_do_horario():
    b = agendador.bloco_agendador(CFG, _agora(2026, 11, 4, 7, 0))
    assert b["proxima"] == "2026-11-04T07:55:00-03:00"
    assert b["proxima_texto"] == "qua 04/11 07:55"


def test_horario_igual_ao_agora_nao_conta_como_proxima():
    b = agendador.bloco_agendador(CFG, _agora(2026, 11, 4, 7, 55))
    assert b["proxima"] == "2026-11-05T07:55:00-03:00"
    assert b["proxima_texto"] == "qui 05/11 07:55"


def test_sexta_depois_do_horario_pula_fim_de_semana():
    b = agendador.bloco_agendador(CFG, _agora(2026, 11, 6, 8, 0))
    assert b["proxima_texto"] == "seg 09/11 07:55"
    assert b["texto"] == "Agendador: seg a sex, 07:55 · próxima seg 09/11"


def test_proxima_em_feriado_avisa_que_nao_ha_pregao():
    cfg = {"dias": ["seg"], "hora": "07:55", "descricao": "rotina"}
    b = agendador.bloco_agendador(cfg, _agora(2026, 11, 1, 10, 0))
    assert b["proxima"] == "2026-11-02T07:55:00-03:00"
    assert b["proxima_pregao"] is False
    assert b["detalhe"] == ("rotina · A próxima execução cai em dia sem pregão (Finados (a conferir)): "
                            "a rotina roda, mas não gera nada.")


def test_sem_configuracao_devolve_nao_configurado_exato():
    assert agendador.bloco_agendador(None, _agora(2026, 11, 3, 19, 42)) == {
        "configurado": False,
        "texto": "Agendador: não configurado",
        "detalhe": "Sem a chave agendador (dias e hora) em processamento/config/painel.yaml, ou com valor inválido.",
        "dias_semana": [],
        "hora": None,
        "proxima": None,
        "proxima_texto": None,
        "proxima_pregao": None,
    }


def test_texto_dos_dias_todos_e_lista_curta():
    todos = {"dias": ["seg", "ter", "qua", "qui", "sex", "sab", "dom"], "hora": "07:55"}
    assert agendador.bloco_agendador(todos, _agora(2026, 11, 3, 19, 42))["texto"] == (
        "Agendador: todos os dias, 07:55 · próxima qua 04/11")
    qua_sex = {"dias": ["qua", "sex"], "hora": "07:55"}
    assert agendador.bloco_agendador(qua_sex, _agora(2026, 11, 3, 19, 42))["texto"] == (
        "Agendador: qua, sex, 07:55 · próxima qua 04/11")
    assert agendador.bloco_agendador(qua_sex, _agora(2026, 11, 3, 19, 42))["dias_semana"] == [2, 4]
