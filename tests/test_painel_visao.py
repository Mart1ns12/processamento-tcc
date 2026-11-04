"""Testes de processamento/painel/visao.py: fluxo do dia, linha do tempo, carga completa e calendário.

Os dicionários são montados à mão (não dependem de leitores.py lendo arquivos). Usam o calendário
real (processamento/config/parametros.yaml) e, quando preciso, um yaml temporário. Sem banco e sem rede.
"""

from datetime import date
from pathlib import Path

from processamento.painel import visao
from processamento.painel.acoes import ACOES
from processamento.painel.ajuda import O_QUE_FAZER
from processamento.painel.saude import cartoes_saude
from processamento.painel.visao import (bloco_api, bloco_banco, calendario_meses, dia_curto, etapas_coleta, fluxo,
                                        frase_dia, hora_marco, linha_do_tempo, quando, resumo, tempo_curto,
                                        tempos_acoes)

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


# ---------- Fase 3: resumo, tempos e frase do dia ----------

FIXTURE_DIAG = Path(__file__).resolve().parent / "dados" / "painel" / "diagnostico_completo.md"
HOJE_OK = {"data": "2026-10-23", "dia_semana": "sexta", "pregao": True, "motivo": None, "erro": None}
TRAVA_VAZIA = {"existe": False, "ativa": False, "abandonada": False, "idade_min": None}
TESTES_OK = {"disponivel": True, "aprovado": True, "interrompido": False, "contagens": {"passed": 1700}}
SAUDE_OK = {"disponivel": True, "cartoes": [{"id": "contrato", "titulo": "Contrato com a coleta",
                                             "farol": "ok", "numero": "0 divergências"}]}
LT = linha_do_tempo(ITEM, "09:45")   # rotina em outro dia: folga None


def test_resumo_tudo_certo():
    assert resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, SAUDE_OK, TESTES_OK) == {
        "nivel": "ok", "frase": "Tudo certo", "pontos": []}


def test_resumo_atencao_com_os_cartoes_da_fixture():
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, cartoes_saude(FIXTURE_DIAG), TESTES_OK)
    assert r["nivel"] == "warn"
    assert r["frase"] == "Atenção: 4 pontos"
    assert [p["texto"] for p in r["pontos"]] == [
        "Quantidade de ações (19 empresas)", "Preços suspeitos (5 retornos)",
        "Lacunas nas séries (3 lacunas)", "Horário das notícias (90,8% sem hora real)"]
    assert [p["alvo"] for p in r["pontos"]] == [
        "saude-c-quantidade_acoes", "saude-c-retornos", "saude-c-lacunas", "saude-c-horario_noticias"]
    assert r["pontos"][0]["o_que_fazer"] == O_QUE_FAZER["saude_quantidade_acoes"]


def test_resumo_falhou_com_atencao():
    fluxo_falhou = fluxo(dict(ITEM, status="falhou", n_pacotes=0, pacotes=[]))
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo_falhou, LT, cartoes_saude(FIXTURE_DIAG), TESTES_OK)
    assert r["frase"] == "Falhou: Última rotina diária (23/10/2026) falhou · e 4 pontos de atenção"
    assert r["pontos"][0] == {"nivel": "bad", "texto": "Última rotina diária (23/10/2026) falhou",
                              "alvo": "fluxo-processamento", "o_que_fazer": O_QUE_FAZER["rotina_falhou"]}


def test_resumo_singular_e_parcial():
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(dict(ITEM, status="parcial")), LT, SAUDE_OK, TESTES_OK)
    assert r["frase"] == "Atenção: 1 ponto"
    assert r["pontos"] == [{"nivel": "warn", "texto": "Última rotina diária (23/10/2026) com pendências",
                            "alvo": "fluxo-processamento", "o_que_fazer": O_QUE_FAZER["rotina_parcial"]}]


def test_resumo_rotina_interrompida():
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(dict(ITEM, status="em_andamento", possivelmente_interrompida=True)),
               LT, SAUDE_OK, TESTES_OK)
    assert r["pontos"][0]["texto"] == "Última rotina diária (23/10/2026) pode ter sido interrompida"
    assert r["pontos"][0]["o_que_fazer"] == O_QUE_FAZER["rotina_interrompida"]


def test_resumo_coleta_com_problema():
    coleta = {"consultado": True, "motivo": "entrega_falhou", "iniciada_em": "2026-10-23T08:00:01-03:00"}
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(dict(ITEM, coleta=coleta, status="falhou", n_pacotes=0, pacotes=[])),
               LT, SAUDE_OK, TESTES_OK)
    assert r["frase"] == "Falhou: Coleta (entrega com problema); Última rotina diária (23/10/2026) falhou"
    assert r["pontos"][0] == {"nivel": "bad", "texto": "Coleta (entrega com problema)", "alvo": "fluxo-coleta",
                              "o_que_fazer": O_QUE_FAZER["coleta_bad"]}


def test_resumo_atraso_em_relacao_ao_prazo():
    lt = linha_do_tempo(dict(ITEM_MANHA, inicio="2026-10-23T09:50:00-03:00", fim="2026-10-23T09:52:30-03:00"), "09:45")
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), lt, SAUDE_OK, TESTES_OK)
    assert r["pontos"] == [{"nivel": "warn", "texto": "Rotina terminou depois do prazo (atraso de 7 min 30 s)",
                            "alvo": "linha-tempo", "o_que_fazer": O_QUE_FAZER["atraso_prazo"]}]


def test_resumo_testes_com_falhas_interrompidos_e_sem_resultado():
    def testes_com(**kw):
        return resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, SAUDE_OK, kw)["pontos"]

    falhou = testes_com(disponivel=True, aprovado=False, interrompido=False, contagens={"failed": 2, "passed": 1698})
    assert falhou == [{"nivel": "bad", "texto": "Testes automáticos com falhas (2 falhas)", "alvo": "testes",
                       "o_que_fazer": O_QUE_FAZER["testes_falhas"]}]
    assert testes_com(disponivel=True, aprovado=False, interrompido=False, contagens={"failed": 1})[0]["texto"] == (
        "Testes automáticos com falhas (1 falha)")
    sem_resultado = testes_com(disponivel=True, aprovado=False, interrompido=False, contagens={})
    assert sem_resultado[0]["nivel"] == "warn"
    assert sem_resultado[0]["texto"] == "Testes automáticos sem resultado completo"
    interrompido = testes_com(disponivel=True, aprovado=None, interrompido=True, contagens={})
    assert interrompido[0]["nivel"] == "warn"
    assert interrompido[0]["texto"] == "Testes automáticos interrompidos"
    assert testes_com(disponivel=False, motivo="x") == []


def test_resumo_trava_calendario_e_saude_indisponivel():
    r = resumo({"erro": "feriados inválidos"}, {"abandonada": True, "idade_min": 420}, fluxo(ITEM), LT,
               {"disponivel": False, "motivo": "x"}, TESTES_OK)
    assert r["pontos"] == [
        {"nivel": "warn", "texto": "Saúde dos dados: sem diagnóstico", "alvo": "saude",
         "o_que_fazer": O_QUE_FAZER["saude_sem_diagnostico"]},
        {"nivel": "bad", "texto": "Calendário da B3 com erro", "alvo": "historico",
         "o_que_fazer": O_QUE_FAZER["calendario_erro"]},
        {"nivel": "warn", "texto": "Trava da rotina esquecida (420 min)", "alvo": "comandos",
         "o_que_fazer": O_QUE_FAZER["trava_abandonada"]}]
    assert r["frase"] == "Falhou: Calendário da B3 com erro · e 2 pontos de atenção"


def test_resumo_cartao_cinza_conta_como_atencao():
    saude = {"disponivel": True, "cartoes": [{"id": "retornos", "titulo": "Preços suspeitos",
                                              "farol": "idle", "numero": "sem dados"}]}
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, saude, TESTES_OK)
    assert r["pontos"] == [{"nivel": "warn", "texto": "Preços suspeitos (sem dados)", "alvo": "saude-c-retornos",
                            "o_que_fazer": O_QUE_FAZER["saude_sem_dados"]}]


def test_resumo_sem_nada_nao_quebra():
    r = resumo(None, None, None, None, None, None)
    assert r["frase"] == "Atenção: 2 pontos"
    assert [p["texto"] for p in r["pontos"]] == ["Fluxo do dia: sem dados", "Saúde dos dados: sem diagnóstico"]


def test_tempo_curto_arredonda_para_o_botao():
    casos = {None: None, True: None, -1: None, 45: "menos de um minuto", 89: "~1 min", 90: "~2 min",
             96: "~2 min", 180: "~3 min", 295: "~5 min", 3599: "~1 h 0 min", 5400: "~1 h 30 min"}
    for entrada, esperado in casos.items():
        assert tempo_curto(entrada) == esperado, entrada


def test_tempos_acoes_prefere_o_log_do_painel():
    tempos = tempos_acoes({"rotina": 75, "carga": None, "diagnostico": None, "testes": 295},
                          dict(ITEM, duracao_s=118), dict(COMPLETA, duracao_s=180))
    assert tempos == {
        "dia": {"segundos": None, "curto": None, "texto": "Ainda sem medição: pode levar alguns minutos.",
                "origem": None},
        "rotina": {"segundos": 75, "curto": "~1 min", "texto": "Da última vez, pelo painel, levou 1 min 15 s.",
                   "origem": "painel"},
        "carga": {"segundos": 180, "curto": "~3 min", "texto": "A última carga completa levou 3 min 0 s.",
                  "origem": "execucao"},
        "diagnostico": {"segundos": None, "curto": None, "texto": "Ainda sem medição: pode levar alguns minutos.",
                        "origem": None},
        "testes": {"segundos": 295, "curto": "~5 min", "texto": "Da última vez, pelo painel, levou 4 min 55 s.",
                   "origem": "painel"}}


def test_tempos_acoes_ignora_execucao_que_falhou_ou_nao_terminou():
    tempos = tempos_acoes({}, dict(ITEM, status="falhou", duracao_s=0),
                          dict(COMPLETA, status="em_andamento", duracao_s=None))
    assert tempos["rotina"]["origem"] is None and tempos["carga"]["origem"] is None
    assert tempos["rotina"]["texto"] == tempos["carga"]["texto"] == "Ainda sem medição: pode levar alguns minutos."


def test_tempos_acoes_sem_nada_tem_todas_as_acoes():
    tempos = tempos_acoes(None, None, None)
    assert set(tempos) == set(ACOES)
    assert all(t["segundos"] is None for t in tempos.values())


def test_hora_marco():
    assert hora_marco(linha_do_tempo(ITEM_MANHA, "09:45"), "abertura") == "10:00"
    assert hora_marco(None, "abertura") is None
    assert hora_marco({"disponivel": False}, "prazo") is None


def test_frase_dia_domingo_com_ultima_rotina_de_sexta():
    assert frase_dia("2026-10-25", "2026-10-23") == (
        "Hoje é domingo, 25/10/2026 (sem pregão). A última rotina diária é do pregão de sex 23/10/2026.")


def test_frase_dia_pregao_sem_rotina_de_hoje_ainda():
    assert frase_dia("2026-10-23", "2026-10-22") == (
        "Hoje é sexta, 23/10/2026 (dia de pregão). A rotina de hoje ainda não rodou; "
        "a última é do pregão de qui 22/10/2026.")


def test_frase_dia_pregao_com_rotina_do_proprio_dia():
    assert frase_dia("2026-10-23", "2026-10-23") == (
        "Hoje é sexta, 23/10/2026 (dia de pregão). A última rotina diária é a de hoje.")


def test_frase_dia_sem_nenhuma_rotina():
    assert frase_dia("2026-10-25", None) == (
        "Hoje é domingo, 25/10/2026 (sem pregão). Nenhuma rotina diária encontrada.")


def test_frase_dia_feriado_mostra_o_motivo():
    assert frase_dia("2026-10-12", None) == (
        "Hoje é segunda, 12/10/2026 (sem pregão: Nossa Senhora Aparecida). Nenhuma rotina diária encontrada.")


# ---------- Fase 7: etapas da coleta, bloco da API, banco da API e pontos novos do resumo ----------

ETAPAS_DIA = {"precos": "concluida", "macro": "concluida", "noticias": "concluida", "ipe": "concluida",
              "enriquecimento": "concluida", "juiza": "concluida", "cadastro": "concluida", "entrega": "concluida",
              "analise": "falhou"}
ITEM_ETAPAS = {"coleta": {"etapas": ETAPAS_DIA, "consulta_hhmm": "10:49", "daily": "2026-10-27-daily-080001"}}


def test_etapas_coleta_resumo_e_destaque():
    r = etapas_coleta(ITEM_ETAPAS)
    assert r["disponivel"] is True and r["motivo"] is None
    assert r["resumo"] == "8 de 9 etapas concluídas · não concluíram: análise (falhou)"
    assert r["nao_concluidas"] == ["análise (falhou)"]
    assert r["etapas"][-1] == {"id": "analise", "rotulo": "análise", "status": "falhou", "texto": "falhou",
                               "destaque": True}
    assert r["etapas"][0]["destaque"] is False
    assert r["consulta_hhmm"] == "10:49" and r["daily"] == "2026-10-27-daily-080001"


def test_etapas_coleta_pendente_e_pulada():
    r = etapas_coleta({"coleta": {"etapas": {"ipe": None, "juiza": "pulada"}}})
    assert [e["texto"] for e in r["etapas"]] == ["pendente", "pulada"]
    assert r["resumo"] == "0 de 2 etapas concluídas · não concluíram: IPE (pendente), juíza (pulada)"


def test_etapas_coleta_sem_etapas_mostra_a_nota():
    nota = "Nenhum daily de hoje encontrado. Consulta única (--sem-esperar)."
    r = etapas_coleta({"coleta": {"nota": nota}})
    assert r["disponivel"] is False and r["motivo"] == nota
    assert r["etapas"] == [] and r["resumo"] is None
    assert etapas_coleta(None)["disponivel"] is False


AGORA_API = "2026-10-27T10:58:03-03:00"
OK_API = {"respondeu": True, "http": 200, "ms": 900, "status": "ok", "banco": "ok",
          "ultima_publicacao": "2026-10-27", "erro": None}
MEDICOES_API = [{"ms": 800}, {"ms": 1000}, {"ms": None}, {"ms": 900}]


def _situacao(consulta=None, medicoes=(), **extra):
    base = {"configurada": True, "erro_config": None, "timeout_s": 5.0, "consulta": consulta,
            "consultado_em": AGORA_API, "medicoes": list(medicoes)}
    base.update(extra)
    return base


def test_bloco_api_no_ar_com_tempos():
    r = bloco_api(_situacao(OK_API, MEDICOES_API), 2.0)
    assert r["estado"] == "ok" and r["titulo"] == "No ar" and r["pontos"] == []
    assert r["linhas"] == ["Status ok · banco ok", "Última publicação completa: 27/10/2026",
                           "Última: 0,90 s · média 0,90 s (3 de 4 com resposta)", "Consultada às 10:58:03"]
    assert r["ultima_publicacao"] == "2026-10-27" and r["consultado_em"] == "10:58:03"


def test_bloco_api_lenta_vira_aviso_com_um_ponto():
    r = bloco_api(_situacao(OK_API, MEDICOES_API), 0.5)
    assert r["estado"] == "warn"
    assert r["pontos"] == [{"nivel": "warn", "texto": "API lenta (média 0,90 s)", "chave": "api_lenta"}]


def test_bloco_api_sem_resposta_por_timeout():
    consulta = {"respondeu": False, "http": None, "ms": None, "status": None, "banco": None,
                "ultima_publicacao": None, "erro": "TimeoutError"}
    r = bloco_api(_situacao(consulta, [{"ms": None}]), 2.0)
    assert r["estado"] == "warn" and r["titulo"] == "Sem resposta"
    assert r["linhas"][0] == "Sem resposta em até 5 s (TimeoutError)"
    assert r["pontos"] == [{"nivel": "warn", "texto": "API sem resposta", "chave": "api_sem_resposta"}]


def test_bloco_api_503_e_banco_fora():
    r = bloco_api(_situacao(dict(OK_API, http=503, status=None, banco=None)), 2.0)
    assert r["estado"] == "bad" and r["titulo"] == "Banco da API fora"
    assert r["linhas"][0] == "Status sem dados · banco sem dados"
    assert r["pontos"] == [{"nivel": "bad", "texto": "Banco da API fora", "chave": "api_banco_fora"}]


def test_bloco_api_nao_configurada_e_sem_consulta_ficam_ociosas():
    nao = bloco_api({"configurada": False, "erro_config": "Sem painel.api_url no parametros.yaml.",
                     "consulta": None, "medicoes": []}, 2.0)
    assert nao["configurada"] is False and nao["estado"] == "idle" and nao["titulo"] == "Não configurada"
    assert nao["linhas"] == ["Sem painel.api_url no parametros.yaml."]
    sem_consulta = bloco_api(_situacao(None), 2.0)
    assert sem_consulta["estado"] == "idle" and sem_consulta["titulo"] == "sem dados"


def test_bloco_banco_em_dia_com_pregao():
    r = bloco_banco(_situacao(OK_API), "2026-10-27", "2026-10-26")
    assert r["estado"] == "ok" and r["titulo"] == "Em dia"
    assert r["linhas"] == ["Última publicação completa: 27/10/2026",
                           "Esperada: 27/10/2026 (pregão de 26/10/2026)"]
    assert r["pontos"] == []


def test_bloco_banco_atrasado_tem_ponto():
    r = bloco_banco(_situacao(dict(OK_API, ultima_publicacao="2026-10-23")), "2026-10-27", None)
    assert r["estado"] == "warn" and r["titulo"] == "Publicação atrasada"
    assert r["linhas"] == ["Última publicação completa: 23/10/2026", "Esperada: 27/10/2026"]
    assert r["pontos"] == [{"nivel": "warn",
                            "texto": "Banco da API: última publicação completa 23/10/2026, esperada 27/10/2026",
                            "chave": "banco_atrasado"}]


def test_bloco_banco_sem_resposta_fora_e_sem_comparacao():
    sem_resposta = bloco_banco(_situacao(dict(OK_API, respondeu=False, erro="TimeoutError")), "2026-10-27", None)
    assert sem_resposta["estado"] == "idle" and sem_resposta["linhas"] == ["Depende da resposta da API."]
    assert bloco_banco(_situacao(None), "2026-10-27", None)["estado"] == "idle"
    fora = bloco_banco(_situacao(dict(OK_API, http=503)), "2026-10-27", None)
    assert fora["estado"] == "bad" and fora["titulo"] == "Fora" and fora["pontos"] == []
    sem_esperado = bloco_banco(_situacao(OK_API), None, None)
    assert sem_esperado["estado"] == "idle" and sem_esperado["titulo"] == "sem rotina para comparar"
    assert sem_esperado["linhas"] == ["Última publicação completa: 27/10/2026"]
    nada = bloco_banco(_situacao(dict(OK_API, ultima_publicacao=None)), "2026-10-27", None)
    assert nada["estado"] == "warn" and nada["titulo"] == "Nada publicado ainda"
    assert nada["pontos"] == [{"nivel": "warn", "texto": "Banco da API: nada publicado ainda",
                               "chave": "banco_atrasado"}]


def test_resumo_pontos_de_api_banco_e_dia_atipico_na_ordem():
    banco = {"pontos": [{"nivel": "warn", "texto": "Banco da API: nada publicado ainda", "chave": "banco_atrasado"}]}
    api = {"pontos": [{"nivel": "warn", "texto": "API sem resposta", "chave": "api_sem_resposta"}]}
    atipico = {"pontos": [{"nivel": "warn",
                           "texto": "Dia atípico no pregão de 26/10/2026 (16 ações): "
                                    "aviso de evento de mercado, não erro dos dados",
                           "chave": "dia_atipico_amplo"}]}
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, SAUDE_OK, TESTES_OK, api=api, banco=banco, dia_atipico=atipico)
    assert [(p["alvo"], p["texto"]) for p in r["pontos"]] == [
        ("fluxo-banco", "Banco da API: nada publicado ainda"),
        ("fluxo-api", "API sem resposta"),
        ("dia-atipico", "Dia atípico no pregão de 26/10/2026 (16 ações): "
                        "aviso de evento de mercado, não erro dos dados")]
    assert r["pontos"][1]["o_que_fazer"] == O_QUE_FAZER["api_sem_resposta"]
    assert r["pontos"][2]["o_que_fazer"] == O_QUE_FAZER["dia_atipico_amplo"]
    assert r["frase"] == "Atenção: 3 pontos"


def test_resumo_ignora_pontos_malformados_dos_blocos_novos():
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, SAUDE_OK, TESTES_OK,
               api={"pontos": ["lixo", {"nivel": "warn"}, {"nivel": "x", "texto": "t", "chave": "c"}]},
               dia_atipico=None)
    assert r["pontos"] == []


def test_resumo_cartao_de_coerencia_tem_alvo_e_o_que_fazer():
    saude = {"disponivel": True, "cartoes": [{"id": "coerencia_mercado", "titulo": "Coerência do mercado",
                                              "farol": "warn", "numero": "1 sinal suspeito"}]}
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, saude, TESTES_OK)
    assert r["pontos"] == [{"nivel": "warn", "texto": "Coerência do mercado (1 sinal suspeito)",
                            "alvo": "saude-c-coerencia_mercado",
                            "o_que_fazer": O_QUE_FAZER["saude_coerencia_mercado"]}]


def test_resumo_sem_diagnostico_vem_antes_dos_cartoes():
    saude = {"disponivel": False, "cartoes": [{"id": "retornos", "titulo": "Preços suspeitos",
                                               "farol": "warn", "numero": "5 retornos"}]}
    r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, saude, TESTES_OK)
    assert [p["alvo"] for p in r["pontos"]] == ["saude", "saude-c-retornos"]


FLUXO_DIA_NOS = {
    "disponivel": True,
    "coleta": {"estado": "ok", "titulo": "Dados entregues", "entrega_hhmm": "08:22"},
    "processamento": {"estado": "warn", "titulo": "Gerado com pendências", "fim": "2026-10-23T11:02:30-03:00"},
    "interface": {"estado": "ok", "titulo": "7 pacotes prontos"},
    "carga": {"rotulo": "última carga completa: 24/10 23:00 · 2 pacotes"},
}
BANCO_NOS = {"estado": "ok", "titulo": "Em dia", "ultima_publicacao": "2026-10-23"}
API_NOS = {"estado": "ok", "titulo": "No ar", "consultado_em": "10:15:42"}


def test_fluxo_nos_cinco_nos_com_estado_horario_e_rodape():
    assert visao.fluxo_nos(FLUXO_DIA_NOS, BANCO_NOS, API_NOS) == {
        "disponivel": True,
        "nos": [
            {"id": "coleta", "nome": "Coleta", "estado": "ok", "texto": "Dados entregues",
             "quando": "08:22", "alvo": "fluxo-coleta"},
            {"id": "processamento", "nome": "Processamento", "estado": "warn", "texto": "Gerado com pendências",
             "quando": "11:02", "alvo": "fluxo-processamento"},
            {"id": "banco", "nome": "Banco da API", "estado": "ok", "texto": "Em dia",
             "quando": "23/10", "alvo": "fluxo-banco"},
            {"id": "api", "nome": "API", "estado": "ok", "texto": "No ar",
             "quando": "10:15", "alvo": "fluxo-api"},
            {"id": "interface", "nome": "Interface", "estado": "ok", "texto": "7 pacotes prontos",
             "quando": None, "alvo": "fluxo-interface"},
        ],
        "rodape": "última carga completa: 24/10 23:00 · 2 pacotes",
    }


def test_fluxo_nos_converte_fim_do_processamento_para_sao_paulo():
    fluxo_dia = {**FLUXO_DIA_NOS, "processamento": {"estado": "warn", "titulo": "Gerado com pendências",
                                                    "fim": "2026-10-23T14:02:30+00:00"}}
    no = visao.fluxo_nos(fluxo_dia, BANCO_NOS, API_NOS)["nos"][1]
    assert no["quando"] == "11:02"


def test_fluxo_nos_sem_fluxo_fica_sem_dados_e_banco_api_vem_dos_blocos():
    r = visao.fluxo_nos({"disponivel": False, "motivo": "x"}, {}, {})
    assert r["disponivel"] is False
    assert [n["id"] for n in r["nos"]] == ["coleta", "processamento", "banco", "api", "interface"]
    for no in r["nos"]:
        assert no["estado"] == "idle"
        assert no["texto"] == "sem dados"
        assert no["quando"] is None
    assert r["rodape"] == "última carga completa: sem dados"

    r = visao.fluxo_nos({"disponivel": False, "motivo": "x"}, BANCO_NOS, API_NOS)
    assert r["nos"][2]["estado"] == "ok"
    assert r["nos"][2]["quando"] == "23/10"
    assert r["nos"][3]["quando"] == "10:15"
    assert r["nos"][0]["estado"] == "idle"
