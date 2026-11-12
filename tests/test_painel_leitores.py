"""Testes de processamento/painel/leitores.py (plano docs/plano_painel.md, fase F1 e AJUSTE A1).

Usa a árvore de fixtures de tests/dados/painel/raiz (copiada para tmp_path pela fábrica) e o yaml real de
calendário para os feriados. Nenhum teste usa banco, rede ou o `.env`; nenhum escreve em tests/dados/.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fabrica_painel import montar_raiz
from processamento.calendario import SP
from processamento.painel import leitores

REPO = Path(__file__).resolve().parents[1]


def test_duracao_segundos_valores_do_plano():
    assert leitores.duracao_segundos("2026-10-24T22:46:25-03:00", "2026-10-24T22:48:23-03:00") == 118
    assert leitores.duracao_segundos("2026-10-24T23:59:30-03:00", "2026-10-25T00:00:45-03:00") == 75
    # fusos diferentes, mesmo instante
    assert leitores.duracao_segundos("2026-10-24T22:46:25-03:00", "2026-10-25T01:46:25+00:00") == 0


def test_duracao_segundos_casos_invalidos():
    assert leitores.duracao_segundos("2026-10-24T22:48:23-03:00", "2026-10-24T22:46:25-03:00") is None
    assert leitores.duracao_segundos(None, "2026-10-24T22:46:25-03:00") is None
    assert leitores.duracao_segundos("2026-10-24T22:46:25-03:00", None) is None
    assert leitores.duracao_segundos("lixo", "2026-10-24T22:46:25-03:00") is None


def test_formatar_duracao():
    assert leitores.formatar_duracao(118) == "1 min 58 s"
    assert leitores.formatar_duracao(0) == "0 s"
    assert leitores.formatar_duracao(45) == "45 s"
    assert leitores.formatar_duracao(3725) == "1 h 2 min"
    assert leitores.formatar_duracao(None) == "—"


def test_ler_json_motivos(tmp_path):
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{ isto não é json", encoding="utf-8")
    assert leitores.ler_json(tmp_path / "nao_existe.json") == (None, "não encontrado")
    assert leitores.ler_json(ruim) == (None, "JSON inválido")
    bom = tmp_path / "bom.json"
    bom.write_text('{"a": 1}', encoding="utf-8")
    assert leitores.ler_json(bom) == ({"a": 1}, None)


def test_listar_execucoes_saida_diaria(tmp_path):
    raiz = montar_raiz(tmp_path)
    itens = leitores.listar_execucoes(raiz, "saida", "diaria")
    assert [i["data_referencia"] for i in itens] == ["2026-10-23", "2026-10-22", "2026-10-21", "2026-10-20"]

    dia23 = itens[0]
    assert dia23["rodada"] == 6
    assert dia23["status"] == "ok"
    assert dia23["duracao_s"] == 118
    assert dia23["duracao_texto"] == "1 min 58 s"
    assert dia23["n_pacotes"] == 7
    assert dia23["n_avisos"] == 3
    assert dia23["coleta"]["entrega_hhmm"] == "08:22"
    assert dia23["coleta"]["motivo_texto"] == "entrega concluída"
    assert dia23["coleta"]["daily"] == "2026-10-23-daily-080001"
    assert dia23["arquivo"] == "saida/2026-10-23/execucao.json"

    dia22 = itens[1]
    assert dia22["status"] == "falhou"
    assert dia22["duracao_s"] == 0
    assert dia22["n_pacotes"] == 0
    assert dia22["n_avisos"] == 1
    assert dia22["coleta"]["entrega_hhmm"] is None
    assert dia22["coleta"]["motivo_texto"] == "entrega ainda não concluída"

    dia21 = itens[2]
    assert dia21["legivel"] is False
    assert dia21["erro"] == "JSON inválido"

    dia20 = itens[3]
    assert dia20["status"] == "em_andamento"
    assert dia20["duracao_s"] is None
    assert dia20["duracao_texto"] == "em andamento"
    assert dia20["coleta"]["consultado"] is False


def test_listar_execucoes_saida_completa(tmp_path):
    raiz = montar_raiz(tmp_path)
    itens = leitores.listar_execucoes(raiz, "saida_completa", "completa")
    assert len(itens) == 1
    item = itens[0]
    assert item["duracao_s"] == 180
    assert item["duracao_texto"] == "3 min 0 s"
    assert item["n_pacotes"] == 2
    assert item["tipo"] == "completa"


def test_ultima_execucao(tmp_path):
    raiz = montar_raiz(tmp_path)
    diarias = leitores.listar_execucoes(raiz, "saida", "diaria")
    assert leitores.ultima_execucao(diarias)["data_referencia"] == "2026-10-23"
    assert leitores.ultima_execucao([]) is None


def test_d_mais_recente(tmp_path):
    raiz = montar_raiz(tmp_path)
    assert leitores.d_mais_recente(raiz, "saida") == date(2026, 10, 23)
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    assert leitores.d_mais_recente(vazio, "saida") is None


def test_pasta_saida_ausente_lista_vazia(tmp_path):
    raiz = tmp_path / "raiz_sem_saida"
    raiz.mkdir()
    assert leitores.listar_execucoes(raiz, "saida", "diaria") == []
    assert leitores.d_mais_recente(raiz, "saida") is None


def test_ler_parametros_valores_padrao_e_yaml_real(tmp_path):
    raiz = montar_raiz(tmp_path)
    assert leitores.ler_parametros(raiz) == {
        "modelo_oficial": False,
        "familia_producao": "xgb",  # montar_raiz não traz o yaml de produção: vale o padrão
        "teste_final": {"inicio": "2026-06-23", "fim": None, "liberado": False},
        "publicar_top_provisorio": False,
        "pasta_saida": "saida",
        "pasta_logs": "logs",
        "trava": "saida/estado/rotina.trava",
        "trava_validade_horas": 6.0,
        "erro": None,
    }


def test_ler_parametros_arquivo_ausente(tmp_path):
    raiz = montar_raiz(tmp_path)
    (raiz / "processamento" / "config" / "parametros.yaml").unlink()
    params = leitores.ler_parametros(raiz)
    assert params["erro"] == "parametros.yaml não encontrado"
    assert params["trava"] == "saida/estado/rotina.trava"
    assert params["trava_validade_horas"] == 6.0
    assert params["teste_final"] == {"inicio": None, "fim": None, "liberado": False}


def test_ler_parametros_yaml_quebrado(tmp_path):
    raiz = montar_raiz(tmp_path)
    (raiz / "processamento" / "config" / "parametros.yaml").write_text("treino: [\n", encoding="utf-8")
    params = leitores.ler_parametros(raiz)
    assert params["erro"] == "parametros.yaml ilegível"
    assert params["pasta_saida"] == "saida"


AG = datetime(2026, 10, 23, 10, 0, tzinfo=SP)


def test_ler_trava_sem_arquivo(tmp_path):
    raiz = montar_raiz(tmp_path)
    params = leitores.ler_parametros(raiz)
    situacao = leitores.ler_trava(raiz, params, AG)
    assert situacao["existe"] is False
    assert situacao["ativa"] is False
    assert situacao["validade_horas"] == 6.0


def test_ler_trava_ativa_e_abandonada(tmp_path):
    raiz = montar_raiz(tmp_path)
    params = leitores.ler_parametros(raiz)
    caminho = raiz / "saida" / "estado" / "rotina.trava"
    conteudo = '{"pid": 4321, "criada_em": "2026-10-23T09:00:00-03:00"}'
    caminho.write_text(conteudo, encoding="utf-8")

    situacao = leitores.ler_trava(raiz, params, AG)
    assert situacao["existe"] is True
    assert situacao["ativa"] is True
    assert situacao["pid"] == "4321"
    assert situacao["idade_min"] == 60
    assert situacao["criada_em"] == "2026-10-23T09:00:00-03:00"

    depois = datetime(2026, 10, 23, 15, 0, 1, tzinfo=SP)
    situacao = leitores.ler_trava(raiz, params, depois)
    assert situacao["ativa"] is False
    assert situacao["abandonada"] is True

    # a leitura nunca altera a trava
    assert caminho.exists()
    assert caminho.read_text(encoding="utf-8") == conteudo


def test_ler_trava_ilegivel_vale_pela_data_de_modificacao(tmp_path):
    raiz = montar_raiz(tmp_path)
    params = leitores.ler_parametros(raiz)
    caminho = raiz / "saida" / "estado" / "rotina.trava"
    caminho.write_text("lixo", encoding="utf-8")
    mtime = (AG - timedelta(hours=1)).timestamp()
    os.utime(caminho, (mtime, mtime))

    situacao = leitores.ler_trava(raiz, params, AG)
    assert situacao["ativa"] is True
    assert situacao["pid"] == "desconhecido"
    assert caminho.exists()
    assert caminho.read_text(encoding="utf-8") == "lixo"


def test_info_hoje_yaml_real():
    assert leitores.info_hoje(datetime(2026, 10, 25, 12, 0, tzinfo=SP)) == {
        "data": "2026-10-25", "dia_semana": "domingo", "pregao": False, "motivo": "domingo", "erro": None}
    hoje = leitores.info_hoje(datetime(2026, 10, 23, 9, 0, tzinfo=SP))
    assert hoje["pregao"] is True
    assert hoje["motivo"] is None
    assert leitores.info_hoje(datetime(2026, 10, 24, 2, 0, tzinfo=timezone.utc))["data"] == "2026-10-23"
    feriado = leitores.info_hoje(datetime(2026, 10, 12, 9, 0, tzinfo=SP))
    assert feriado["pregao"] is False
    assert feriado["motivo"] == "Nossa Senhora Aparecida"


def test_data_rotina_hoje_e_pregao():
    assert leitores.data_rotina(datetime(2026, 10, 23, 9, 0, tzinfo=SP)) == {
        "data": "2026-10-23", "origem": "hoje", "erro": None}


def test_data_rotina_domingo_usa_ultimo_pregao():
    assert leitores.data_rotina(datetime(2026, 10, 25, 12, 0, tzinfo=SP)) == {
        "data": "2026-10-23", "origem": "ultimo_pregao", "erro": None}


def test_data_rotina_feriado_usa_ultimo_pregao():
    assert leitores.data_rotina(datetime(2026, 10, 12, 9, 0, tzinfo=SP)) == {
        "data": "2026-10-09", "origem": "ultimo_pregao", "erro": None}


def test_data_rotina_converte_fuso_utc_para_sao_paulo():
    assert leitores.data_rotina(datetime(2026, 10, 24, 2, 0, tzinfo=timezone.utc)) == {
        "data": "2026-10-23", "origem": "hoje", "erro": None}


def test_data_rotina_erro_do_calendario_nao_levanta(tmp_path):
    caminho = tmp_path / "parametros_quebrados.yaml"
    caminho.write_text("treino: [\n", encoding="utf-8")
    resultado = leitores.data_rotina(datetime(2026, 10, 23, 9, 0, tzinfo=SP), str(caminho))
    assert resultado["data"] is None
    assert resultado["origem"] is None
    assert resultado["erro"]


def test_info_hoje_erro_do_calendario_nao_levanta(tmp_path):
    caminho = tmp_path / "parametros_quebrados.yaml"
    caminho.write_text("treino: [\n", encoding="utf-8")
    resultado = leitores.info_hoje(datetime(2026, 10, 23, 9, 0, tzinfo=SP), str(caminho))
    assert resultado["data"] == "2026-10-23"
    assert resultado["pregao"] is None
    assert resultado["erro"]


def test_listar_execucoes_coleta_inicio_e_versao(tmp_path):
    raiz = montar_raiz(tmp_path)
    itens = leitores.listar_execucoes(raiz, "saida", "diaria")
    dia23 = itens[0]
    assert dia23["coleta"]["iniciada_em"] == "2026-10-23T08:00:01-03:00"
    assert dia23["coleta"]["iniciada_hhmm"] == "08:00"
    assert dia23["coleta"]["finalizada_em"] == "2026-10-23T08:24:29-03:00"
    assert dia23["versao_contrato"] == "1.0"
    assert itens[1]["coleta"]["iniciada_hhmm"] == "08:00"
    assert itens[1]["coleta"]["finalizada_em"] is None
    assert itens[2]["versao_contrato"] is None
    assert itens[3]["coleta"]["iniciada_hhmm"] is None


def test_resumir_execucao_hora_em_sao_paulo_e_sem_versao():
    dados = {"registros": [{"status": "ok", "coleta_status": {"iniciada_em": "2026-10-23T11:00:01+00:00"}}]}
    item = leitores.resumir_execucao(dados, "2026-10-23", "diaria", "x")
    assert item["coleta"]["iniciada_hhmm"] == "08:00"
    assert item["versao_contrato"] is None


def test_ler_prazo_rotina(tmp_path):
    raiz = montar_raiz(tmp_path)
    caminho = raiz / "processamento" / "config" / "parametros.yaml"
    assert leitores.ler_prazo_rotina(raiz) == "09:45"
    texto = caminho.read_text(encoding="utf-8")
    caminho.write_text(texto.replace('  prazo: "09:45"', '  prazo: "9h"'), encoding="utf-8")
    assert leitores.ler_prazo_rotina(raiz) is None
    caminho.write_text(texto.replace('  prazo: "09:45"', "  prazo: 10:00"), encoding="utf-8")
    assert leitores.ler_prazo_rotina(raiz) is None
    caminho.unlink()
    assert leitores.ler_prazo_rotina(raiz) is None


def test_ler_valores_ajuda_da_fixture(tmp_path):
    raiz = montar_raiz(tmp_path)
    assert leitores.ler_valores_ajuda(raiz) == {
        "prazo": "09:45", "prazo_tardio": "12:00", "inicio_consulta": "08:00", "intervalo": "5",
        "limite_historico": "10:00", "corte_noite": "08:00", "retorno_min": "-75%", "retorno_max": "+100%",
        "defasagem": "5", "pvp_min": "0,05", "pvp_max_x1000": "20",
        "teste_final_inicio": "23/06/2026",
        "tempo_limite_api": "2 s", "atipico_min_acoes": "5", "atipico_retorno": "30%", "atipico_ibov": "5%",
        "coerencia_ivvb11": "3%", "coerencia_dif": "2%", "etapas_conferidas": "precos, noticias, enriquecimento",
        "eventos_suspeitos": None,   # fixture com eventos_retorno_suspeito: [] (nenhuma frase sobre eventos)
    }


def test_ler_valores_ajuda_invalidos_e_ausente(tmp_path):
    raiz = montar_raiz(tmp_path)
    caminho = raiz / "processamento" / "config" / "parametros.yaml"
    texto = caminho.read_text(encoding="utf-8")
    assert 'prazo_tardio: "12:00"' in texto and "intervalo_minutos: 5" in texto
    assert "pvp_maximo_plausivel_x1000: 20.0" in texto
    texto = texto.replace('prazo_tardio: "12:00"', "prazo_tardio: 12:00")
    texto = texto.replace("intervalo_minutos: 5", "intervalo_minutos: true")
    texto = texto.replace("pvp_maximo_plausivel_x1000: 20.0", "pvp_maximo_plausivel_x1000: true")
    caminho.write_text(texto, encoding="utf-8")
    v = leitores.ler_valores_ajuda(raiz)
    assert v["prazo_tardio"] is None
    assert v["intervalo"] is None
    assert v["pvp_max_x1000"] is None
    assert v["prazo"] == "09:45"
    caminho.unlink()
    assert leitores.ler_valores_ajuda(raiz) == dict.fromkeys(leitores.CHAVES_AJUDA)


def test_ler_parametros_painel_da_fixture(tmp_path):
    raiz = montar_raiz(tmp_path)
    p = leitores.ler_parametros_painel(raiz)
    assert p["api_url"] is None
    assert p["dir_api"] is None
    assert p["api_timeout_s"] == 5
    assert p["api_tempo_limite_s"] == 2.0
    assert p["retorno_dia_abs"] == 0.30
    assert p["afetadas_max"] == 5
    assert p["dia_media_execucoes"] == 3
    assert p["diagnosticos_manter"] == 10
    assert p["mercado_pregoes_linha"] == 7


def test_ler_parametros_painel_real_so_leitura():
    p = leitores.ler_parametros_painel(REPO)
    assert p["api_url"] == "https://api-processamento-tcc-production.up.railway.app"
    assert p["dir_api"] == "../api-tcc"
    assert p["retorno_dia_abs"] == 0.30
    assert p["dia_atipico_ibov_amplo"] == 0.05
    assert p["agendador"] == {"dias": ["seg", "ter", "qua", "qui", "sex"], "hora": "08:35",
                              "descricao": "dia completo esperando a coleta (scripts/agendar_dia.ps1)"}


def test_ler_parametros_painel_invalidos_viram_none(tmp_path):
    raiz = montar_raiz(tmp_path)
    caminho = raiz / "processamento" / "config" / "painel.yaml"
    caminho.write_text('api_medicoes: true\napi_timeout_s: "x"\n', encoding="utf-8")
    p = leitores.ler_parametros_painel(raiz)
    assert p["api_medicoes"] is None
    assert p["api_timeout_s"] is None
    assert p["retorno_dia_abs"] == 0.30  # vem do parametros.yaml, não do painel.yaml


def test_ler_parametros_painel_sem_painel_yaml(tmp_path):
    raiz = montar_raiz(tmp_path)
    (raiz / "processamento" / "config" / "painel.yaml").unlink()
    p = leitores.ler_parametros_painel(raiz)
    assert all(p[c] is None for c in leitores.PARAMETROS_PAINEL if c != "retorno_dia_abs")
    assert p["retorno_dia_abs"] == 0.30
    assert leitores.ler_valores_ajuda(raiz)["tempo_limite_api"] is None


def test_ler_parametros_painel_agendador_valido(tmp_path):
    raiz = montar_raiz(tmp_path)
    caminho = raiz / "processamento" / "config" / "painel.yaml"
    caminho.write_text('agendador:\n  dias: ["seg", "ter"]\n  hora: "07:55"\n  descricao: "rotina"\n', encoding="utf-8")
    p = leitores.ler_parametros_painel(raiz)
    assert p["agendador"] == {"dias": ["seg", "ter"], "hora": "07:55", "descricao": "rotina"}


def test_ler_parametros_painel_agendador_invalido_vira_none(tmp_path):
    raiz = montar_raiz(tmp_path)
    caminho = raiz / "processamento" / "config" / "painel.yaml"
    casos = ['agendador:\n  dias: ["seg"]\n  hora: 755\n',
             'agendador:\n  dias: ["seg", "seg"]\n  hora: "07:55"\n',
             'agendador:\n  dias: ["segunda"]\n  hora: "07:55"\n',
             'agendador:\n  dias: [["seg"]]\n  hora: "07:55"\n',
             'agendador: "07:55"\n']
    for texto in casos:
        caminho.write_text(texto, encoding="utf-8")
        assert leitores.ler_parametros_painel(raiz)["agendador"] is None, texto


def test_ler_parametros_painel_sem_chave_agendador_vira_none(tmp_path):
    raiz = montar_raiz(tmp_path)
    assert leitores.ler_parametros_painel(raiz)["agendador"] is None


def test_parametros_yaml_real_continua_valido_para_o_calendario():
    """O bloco do painel não pode ir para o parametros.yaml: o calendário rejeita chave de topo desconhecida."""
    from processamento import calendario
    dados = calendario.carregar_parametros(str(REPO / "processamento" / "config" / "parametros.yaml"))
    assert "painel" not in dados


def test_ultima_execucao_valida_ignora_falhou():
    itens = [
        {"legivel": True, "status": "ok", "gerado_em": "2026-10-27T09:00:00-03:00"},
        {"legivel": True, "status": "falhou", "gerado_em": "2026-10-27T10:00:00-03:00"},
    ]
    assert leitores.ultima_execucao_valida(itens) is itens[0]
    assert leitores.ultima_execucao_valida([]) is None


def test_resumir_execucao_consulta_hhmm():
    dados = {"registros": [{"status": "ok", "coleta_status": {"ultima_consulta_em": "2026-10-27T10:49:32-03:00"}}]}
    item = leitores.resumir_execucao(dados, "2026-10-27", "rotina", "saida/2026-10-27/execucao.json")
    assert item["coleta"]["consulta_hhmm"] == "10:49"
