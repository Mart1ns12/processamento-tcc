"""Testes do `coleta_status` ampliado no validador do pacote `execucao` (plano da etapa 8, Fase 4; seção 8).

Sem rede e sem banco: só registros montados aqui.
"""

from __future__ import annotations

import copy

import pytest

from processamento.saida import contrato as c
from processamento.saida.contrato import ErroContrato

META = c.meta("2026-10-26T08:05:00-03:00", "2026-10-26T08:05:00-03:00")

# Dicionário exato do caso A (seção 3 do plano).
CASO_A = {
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


def _execucao(coleta: dict) -> dict:
    """Registro `execucao` completo (campos da seção 4 do plano), com o `coleta_status` dado."""
    return {
        **copy.deepcopy(META), "data_referencia": "2026-10-26", "rodada": 1,
        "inicio": "2026-10-26T08:00:01-03:00", "fim": None, "status": "em_andamento",
        "coleta_status": coleta, "pacotes_enviados": [], "avisos": [],
    }


def _com(**alterar) -> dict:
    """Caso A com campos trocados (valor None remove o campo)."""
    coleta = copy.deepcopy(CASO_A)
    for campo, valor in alterar.items():
        if valor is None and campo in coleta:
            del coleta[campo]
        else:
            coleta[campo] = valor
    return coleta


def test_caso_a_do_plano_passa():
    c.validar("execucao", _execucao(copy.deepcopy(CASO_A)))


def test_formato_antigo_sem_coleta_consultada_continua_valido():
    antigo = {"consultado": False, "nota": "gatilho da coleta não consultado (etapa 8)"}
    c.validar("execucao", _execucao(antigo))


@pytest.mark.parametrize("motivo", c.MOTIVOS_COLETA)
def test_todo_motivo_da_lista_passa(motivo):
    c.validar("execucao", _execucao(_com(motivo=motivo)))


def test_lista_de_motivos_tem_os_8_da_fase_3():
    assert len(c.MOTIVOS_COLETA) == 8


def test_campo_desconhecido_no_coleta_status_recusado():
    with pytest.raises(ErroContrato, match=r"coleta_status\.xyz: campo desconhecido"):
        c.validar("execucao", _execucao(_com(xyz=1)))


def test_motivo_fora_da_lista_recusado():
    with pytest.raises(ErroContrato, match=r"coleta_status\.motivo"):
        c.validar("execucao", _execucao(_com(motivo="outro")))


def test_consultas_com_fracao_recusado():
    with pytest.raises(ErroContrato, match=r"coleta_status\.consultas: deveria ser inteiro"):
        c.validar("execucao", _execucao(_com(consultas=2.5)))


def test_data_hora_sem_t_e_sem_fuso_recusada():
    with pytest.raises(ErroContrato, match=r"coleta_status\.iniciada_em"):
        c.validar("execucao", _execucao(_com(iniciada_em="2026-10-26 08:00:01")))


def test_etapa_com_status_novo_da_coleta_passa():
    etapas = {**CASO_A["etapas"], "precos": "status_novo_da_coleta"}
    c.validar("execucao", _execucao(_com(etapas=etapas)))


def test_etapa_nula_sem_linha_passa():
    etapas = {**CASO_A["etapas"], "enriquecimento": None}
    c.validar("execucao", _execucao(_com(etapas=etapas)))


def test_etapa_desconhecida_recusada():
    etapas = {**CASO_A["etapas"], "xyz": "concluida"}
    with pytest.raises(ErroContrato, match=r"coleta_status\.etapas\.xyz: campo desconhecido"):
        c.validar("execucao", _execucao(_com(etapas=etapas)))


def test_campos_opcionais_podem_faltar():
    minimo = {"consultado": True, "nota": "Daily da agenda (origem cron)."}
    c.validar("execucao", _execucao(minimo))
