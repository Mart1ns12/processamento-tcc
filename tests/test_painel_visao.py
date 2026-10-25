"""Testes de processamento/painel/visao.py: fluxo do dia, linha do tempo, carga completa e calendário.

Os dicionários são montados à mão (não dependem de leitores.py lendo arquivos). Usam o calendário
real (processamento/config/parametros.yaml) e, quando preciso, um yaml temporário. Sem banco e sem rede.
"""

from datetime import date
from pathlib import Path

from processamento.painel import visao
from processamento.painel.visao import calendario_meses, dia_curto, fluxo, linha_do_tempo, quando

COLETA = {
    "consultado": True,
    "motivo": "entrega_concluida",
    "motivo_texto": "entrega concluída",
    "iniciada_em": "2026-10-23T08:00:01-03:00",
    "iniciada_hhmm": "08:00",
    "entrega_hhmm": "08:22",
    "entrega_concluida_em": "2026-10-23T08:22:52-03:00",
    "daily": "2026-10-23-daily-080001",
    "etapas": {"precos": "concluida", "noticias": "concluida", "entrega": "em_andamento"},
}

ITEM = {
    "legivel": True,
    "tipo": "diaria",
    "data_referencia": "2026-10-23",
    "status": "ok",
    "rodada": 6,
    "inicio": "2026-10-24T22:46:25-03:00",
    "fim": "2026-10-24T22:48:23-03:00",
    "duracao_texto": "1 min 58 s",
    "n_pacotes": 7,
    "n_avisos": 3,
    "versao_contrato": "1.0",
    "pacotes": [
        {"pacote": "acoes", "registros": 0},
        {"pacote": "series_diarias", "registros": 0},
        {"pacote": "mercado_dia", "registros": 1},
        {"pacote": "resumo_acao", "registros": 85},
        {"pacote": "fundamentos_trimestrais", "registros": 8},
        {"pacote": "proventos", "registros": 0},
        {"pacote": "noticias_dia", "registros": 85},
    ],
    "coleta": COLETA,
}

COMPLETA = {"legivel": True, "data_referencia": "2026-10-23", "rodada": 1, "status": "ok", "n_pacotes": 2,
            "inicio": "2026-10-24T23:00:00-03:00"}

# Item da manhã do pregão de 23/10 (rotina de 08:23 a 08:27, depois da coleta).
ITEM_MANHA = {
    "legivel": True,
    "tipo": "diaria",
    "data_referencia": "2026-10-23",
    "status": "ok",
    "inicio": "2026-10-23T08:23:10-03:00",
    "fim": "2026-10-23T08:27:05-03:00",
    "coleta": {"iniciada_em": "2026-10-23T11:00:01+00:00", "entrega_concluida_em": "2026-10-23T08:22:52-03:00"},
}


# ---------- dia_curto e quando ----------

def test_dia_curto_mostra_dia_da_semana_e_data():
    assert dia_curto(date(2026, 10, 23)) == "sex 23/10"
    assert dia_curto(date(2026, 10, 25)) == "dom 25/10"


def test_quando_converte_para_sao_paulo_e_trata_vazio_e_lixo():
    assert quando("2026-10-23T11:00:01+00:00") == "sex 23/10 08:00"
    assert quando(None) is None
    assert quando("lixo") is None


# ---------- fluxo ----------

def test_fluxo_sem_item_e_item_ilegivel():
    assert fluxo(None) == {"disponivel": False, "motivo": "Nenhuma execução encontrada em saida/."}
    ilegivel = {"legivel": False, "erro": "JSON inválido"}
    assert fluxo(ilegivel) == {"disponivel": False,
                               "motivo": "Arquivo da última execução ilegível (JSON inválido)."}


def test_fluxo_coleta_com_dia_e_resumo():
    coleta = fluxo(ITEM)["coleta"]
    assert coleta == {"estado": "ok", "titulo": "Dados entregues", "dia": "sex 23/10",
                      "resumo": "sex 23/10 · começou 08:00 · entregou 08:22",
                      "inicio_hhmm": "08:00", "entrega_hhmm": "08:22",
                      "etapas_concluidas": 2, "etapas_total": 3,
                      "nota": "entrega concluída", "daily": "2026-10-23-daily-080001"}


def test_fluxo_processamento_com_rotulo_e_quando():
    proc = fluxo(ITEM)["processamento"]
    assert proc["estado"] == "ok"
    assert proc["titulo"] == "Calculado e validado"
    assert proc["n_acoes"] == 85
    assert proc["rotulo"] == "última rotina diária · rodada 6 · de 24/10 22:46"
    assert proc["quando"] == "sáb 24/10 22:46 → 22:48"


def test_fluxo_interface_pacotes_e_registros():
    assert fluxo(ITEM)["interface"] == {"estado": "ok", "titulo": "7 pacotes prontos", "n_pacotes": 7,
                                        "versao_contrato": "1.0", "registros_total": 179}


def test_fluxo_coleta_sem_consulta_nao_tem_etapas():
    item = dict(ITEM, coleta={"consultado": False, "nota": "x"})
    coleta = fluxo(item)["coleta"]
    assert (coleta["estado"], coleta["titulo"]) == ("idle", "Coleta não consultada")
    assert coleta["etapas_total"] is None
    assert coleta["etapas_concluidas"] is None
    assert coleta["resumo"] == "sem dados"


def test_fluxo_falhou_sem_pacotes():
    item = dict(ITEM, status="falhou", n_pacotes=0, pacotes=[])
    f = fluxo(item)
    assert f["interface"]["estado"] == "bad"
    assert f["interface"]["titulo"] == "Nenhum pacote"
    assert f["processamento"]["estado"] == "bad"
    assert f["processamento"]["titulo"] == "Falhou"


def test_fluxo_entrega_em_outro_dia_mostra_dia_da_entrega():
    coleta = dict(COLETA, entrega_concluida_em="2026-10-24T08:22:52-03:00")
    resumo = fluxo(dict(ITEM, coleta=coleta))["coleta"]["resumo"]
    assert resumo == "sex 23/10 · começou 08:00 · entregou sáb 24/10 08:22"


def test_fluxo_sem_entrega_mostra_entrega_nao_concluida():
    coleta = {"consultado": True, "motivo": "entrega_falhou", "iniciada_em": "2026-10-23T08:00:01-03:00"}
    c = fluxo(dict(ITEM, coleta=coleta))["coleta"]
    assert c["estado"] == "bad"
    assert c["resumo"] == "sex 23/10 · começou 08:00 · entrega não concluída"


def test_fluxo_carga_completa_com_rotulo():
    f = fluxo(ITEM, COMPLETA)
    assert f["carga"] == {"disponivel": True, "rodada": 1, "status": "ok", "n_pacotes": 2,
                          "rotulo": "última carga completa: 24/10 23:00 · 2 pacotes"}


def test_fluxo_sem_carga_completa():
    assert fluxo(ITEM)["carga"] == {"disponivel": False, "rotulo": "última carga completa: sem dados"}


def test_fluxo_carga_com_um_pacote_e_sem_inicio():
    completa = {"legivel": True, "data_referencia": "2026-10-23", "rodada": 2, "status": "ok", "n_pacotes": 1,
                "inicio": None}
    assert fluxo(ITEM, completa)["carga"]["rotulo"] == "última carga completa: sem dados · 1 pacote"


# ---------- linha_do_tempo ----------

def test_linha_do_tempo_manha_completa_com_marcos_trechos_e_folga():
    lt = linha_do_tempo(ITEM_MANHA, "09:45")
    assert lt["marcos"] == [
        {"id": "coleta_inicio", "rotulo": "coleta começa", "hora": "08:00", "minuto": 480},
        {"id": "entrega", "rotulo": "coleta entrega", "hora": "08:22", "minuto": 502},
        {"id": "rotina_inicio", "rotulo": "rotina começa", "hora": "08:23", "minuto": 503},
        {"id": "rotina_fim", "rotulo": "pacotes prontos", "hora": "08:27", "minuto": 507},
        {"id": "prazo", "rotulo": "prazo da rotina", "hora": "09:45", "minuto": 585},
        {"id": "abertura", "rotulo": "bolsa abre", "hora": "10:00", "minuto": 600},
    ]
    assert lt["trechos"] == [
        {"id": "coleta", "de": 480, "ate": 502},
        {"id": "processamento", "de": 503, "ate": 507},
        {"id": "folga", "de": 507, "ate": 585},
    ]
    assert lt["eixo"] == {"de": 475, "ate": 605}
    assert lt["folga_s"] == 4675
    assert lt["folga_texto"] == "1 h 17 min"
    assert lt["avisos"] == []
    assert lt["dia_rotulo"] == "sex 23/10/2026"


def test_linha_do_tempo_rotina_em_outro_dia_sem_folga():
    item = dict(ITEM_MANHA, inicio="2026-10-24T22:46:25-03:00", fim="2026-10-24T22:48:23-03:00")
    lt = linha_do_tempo(item, "09:45")
    assert [m["id"] for m in lt["marcos"]] == ["coleta_inicio", "entrega", "prazo", "abertura"]
    assert lt["trechos"] == [{"id": "coleta", "de": 480, "ate": 502}]
    assert lt["folga_s"] is None
    assert lt["folga_texto"] is None
    assert lt["avisos"] == [
        "A rotina deste pregão rodou em 24/10/2026 22:46, fora da manhã do pregão: sem folga a medir."]


def test_linha_do_tempo_atraso_em_relacao_ao_prazo():
    item = dict(ITEM_MANHA, inicio="2026-10-23T09:50:00-03:00", fim="2026-10-23T09:52:30-03:00")
    lt = linha_do_tempo(item, "09:45")
    assert lt["folga_s"] == -450
    assert lt["folga_texto"] == "atraso de 7 min 30 s"
    assert "folga" not in [t["id"] for t in lt["trechos"]]


def test_linha_do_tempo_feriado_de_quarta_de_cinzas_usa_abertura_as_13h():
    item = {"legivel": True, "tipo": "diaria", "data_referencia": "2026-02-18",
            "coleta": None, "inicio": None, "fim": None}
    lt = linha_do_tempo(item, "09:45")
    assert [m["id"] for m in lt["marcos"]] == ["prazo", "abertura"]
    abertura = lt["marcos"][1]
    assert abertura["hora"] == "13:00"
    assert abertura["minuto"] == 780


def test_linha_do_tempo_com_calendario_invalido_avisa_e_segue(tmp_path: Path):
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text("fuso: x\n", encoding="utf-8")
    lt = linha_do_tempo(ITEM_MANHA, "09:45", str(caminho))
    assert "abertura" not in [m["id"] for m in lt["marcos"]]
    assert lt["avisos"][0].startswith("Horário da B3 indisponível")
    assert lt["folga_s"] == 4675


def test_linha_do_tempo_sem_prazo_nao_tem_folga():
    lt = linha_do_tempo(ITEM_MANHA, None)
    assert "prazo" not in [m["id"] for m in lt["marcos"]]
    assert lt["folga_s"] is None
    assert lt["folga_texto"] is None


def test_linha_do_tempo_sem_rotina_diaria():
    vazio = {"disponivel": False, "motivo": "Nenhuma rotina diária para mostrar."}
    assert linha_do_tempo(None, "09:45") == vazio
    assert linha_do_tempo(dict(ITEM_MANHA, tipo="completa"), "09:45") == vazio


# ---------- calendario_meses ----------

DIARIAS = [
    {"data_referencia": "2026-10-23", "legivel": True, "status": "ok"},
    {"data_referencia": "2026-10-22", "legivel": True, "status": "falhou"},
    {"data_referencia": "2026-10-21", "legivel": False, "status": None},
    {"data_referencia": "2026-10-20", "legivel": True, "status": "em_andamento"},
]
COMPLETAS_CAL = [{"data_referencia": "2026-10-23", "legivel": True, "status": "ok"}]


def test_calendario_meses_outubro_de_2026():
    meses = calendario_meses(DIARIAS, COMPLETAS_CAL, "2026-10-23")
    assert len(meses) == 1
    mes = meses[0]
    assert mes["titulo"] == "outubro de 2026"
    dias = mes["dias"]
    assert len(dias) == 22
    assert dias[0] == {"data": "2026-10-01", "dia": 1, "dia_semana": 3, "pregao": True,
                       "motivo": None, "status": None, "completa": False}
    por_dia = {d["dia"]: d for d in dias}
    assert por_dia[12]["pregao"] is False
    assert por_dia[12]["motivo"] == "Nossa Senhora Aparecida"
    assert por_dia[23]["status"] == "ok"
    assert por_dia[23]["completa"] is True
    assert por_dia[22]["status"] == "falhou"
    assert por_dia[21]["status"] == "ilegivel"
    assert por_dia[20]["status"] == "em_andamento"


def test_calendario_meses_inclui_mes_de_hoje_primeiro():
    meses = calendario_meses(DIARIAS, COMPLETAS_CAL, "2026-11-02")
    assert [m["titulo"] for m in meses] == ["novembro de 2026", "outubro de 2026"]


def test_calendario_meses_respeita_limite():
    meses = calendario_meses(DIARIAS, COMPLETAS_CAL, "2026-11-02", max_meses=1)
    assert [m["titulo"] for m in meses] == ["novembro de 2026"]


def test_visao_nao_importa_banco_nem_configuracao_secreta():
    texto = Path(visao.__file__).read_text(encoding="utf-8")
    for proibido in ("processamento.fontes", "sqlalchemy", "dotenv", "SELECT", "executar_leitura"):
        assert proibido not in texto
