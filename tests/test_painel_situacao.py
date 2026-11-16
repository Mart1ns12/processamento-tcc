"""Testes do cartão "Situação de hoje" (visao.resumo com os casos aceitos e o top 5) e de processamento/painel/situacao.py.

Sem rede e sem banco: as leituras usam tmp_path; o único arquivo real lido é o painel_aceitos.yaml (só leitura).
"""

from datetime import datetime
from pathlib import Path

from processamento.calendario import SP
from processamento.painel import situacao, visao
from processamento.painel.ajuda import O_QUE_FAZER

RAIZ_REAL = Path(__file__).resolve().parents[1]
AGORA = datetime(2026, 11, 16, 10, 30, tzinfo=SP)
HOJE = {"data": "2026-11-16", "dia_semana": "segunda", "pregao": True, "motivo": None, "erro": None}
TRAVA = {"existe": False, "ativa": False, "abandonada": False, "idade_min": None}
TESTES = {"disponivel": True, "aprovado": True, "interrompido": False, "contagens": {"passed": 10}}
SAUDE = {"disponivel": True, "cartoes": [{"id": "contrato", "titulo": "Contrato com a coleta", "farol": "ok",
                                         "numero": "0 divergências"}]}
TOP5_OK = {"disponivel": True, "motivo": None, "valido_para_historico": True, "avisos": [], "n_ranking": 5,
           "gerado_em": "2026-11-16T08:40:00-03:00"}
CONSULTA_OK = {"respondeu": True, "http": 200, "ms": 800, "status": "ok", "banco": "ok",
               "ultima_publicacao": "2026-11-16", "erro": None}
SAUDE_COM_CONTRATO_E_RETORNOS = {"disponivel": True, "cartoes": [
    {"id": "contrato", "titulo": "Contrato com a coleta", "farol": "ok", "numero": "0 divergências"},
    {"id": "retornos", "titulo": "Preços suspeitos", "farol": "ok", "numero": "nenhum retorno"}]}
ACEITOS_REAL = situacao.ler_aceitos(RAIZ_REAL / "processamento" / "config" / "painel_aceitos.yaml")


def rotina(**kw) -> dict:
    """Rotina diária de 16/11/2026: coleta entregue às 08:25, rotina de 08:36 a 08:39."""
    base = {"legivel": True, "tipo": "diaria", "data_referencia": "2026-11-16", "status": "ok", "rodada": 1,
            "inicio": "2026-11-16T08:36:00-03:00", "fim": "2026-11-16T08:39:00-03:00",
            "coleta": {"consultado": True, "motivo": "entrega_concluida", "iniciada_em": "2026-11-16T08:00:01-03:00",
                       "entrega_concluida_em": "2026-11-16T08:25:00-03:00"},
            "pacotes": [{"pacote": "resumo_acao", "registros": 85}]}
    base.update(kw)
    return base


def api(medicoes=(), consulta=CONSULTA_OK, timeout=5.0, limite=2.0):
    sit = {"configurada": True, "erro_config": None, "timeout_s": timeout, "consulta": consulta,
           "consultado_em": "2026-11-16T10:29:00-03:00", "medicoes": list(medicoes)}
    return visao.bloco_api(sit, limite), visao.bloco_banco(sit, "2026-11-16", "2026-11-13")


def rotina_de_ontem(**kw) -> dict:
    """Rotina de 13/11/2026 (pregão anterior), com a coleta do próprio dia 13."""
    coleta = {"consultado": True, "motivo": "entrega_concluida", "iniciada_em": "2026-11-13T08:00:01-03:00",
              "entrega_concluida_em": "2026-11-13T08:25:00-03:00"}
    return rotina(data_referencia="2026-11-13", inicio="2026-11-13T08:36:00-03:00",
                  fim="2026-11-13T08:39:00-03:00", coleta=coleta, **kw)


def situacao_de(item, *, top5=TOP5_OK, saude=SAUDE, prazo="09:45", agora=AGORA, medicoes=(), consulta=CONSULTA_OK,
                **extra):
    """resumo() com a rotina `item`, a API e o banco montados; `extra` vai direto para o resumo."""
    api_v, banco_v = api(medicoes, consulta)
    return visao.resumo(HOJE, TRAVA, visao.fluxo(item), visao.linha_do_tempo(item, prazo), saude, TESTES,
                        api=api_v, banco=banco_v, top5=top5, agora=agora, prazo_hhmm=prazo, coleta_normal="08:35",
                        **extra)


def textos(r: dict) -> list[str]:
    return [p["texto"] for p in r["pontos"]]


# ---------- cenários da spec (seção 7) ----------

def test_verde_tudo_funcionando():
    r = situacao_de(rotina())
    assert r["nivel"] == "ok" and r["frase"] == "Tudo funcionando"
    assert r["pontos"] == []


def test_amarelo_top5_fora_do_historico():
    top5 = dict(TOP5_OK, valido_para_historico=False,
                avisos=["Gerado depois das 10h: não entra no histórico do experimento."])
    r = situacao_de(rotina(), top5=top5)
    assert r["nivel"] == "warn" and r["frase"] == "Funcionou, com ressalvas"
    assert len(r["pontos"]) == 1
    assert r["pontos"][0] == {
        "nivel": "warn",
        "texto": "Top 5 fora do histórico do experimento "
                 "(Gerado depois das 10h: não entra no histórico do experimento.)",
        "alvo": "fluxo-processamento", "o_que_fazer": O_QUE_FAZER["top5_tarde"]}


def test_vermelho_rotina_falhou():
    r = situacao_de(rotina(status="falhou", n_pacotes=0, pacotes=[]))
    assert r["nivel"] == "bad" and r["frase"] == "Não funcionou"


def test_vermelho_coleta_sem_entrega_depois_do_prazo():
    coleta = {"consultado": True, "motivo": "entrega_pendente", "iniciada_em": "2026-11-16T08:00:01-03:00"}
    r = situacao_de(rotina(coleta=coleta))
    assert r["nivel"] == "bad" and r["frase"] == "Não funcionou"
    assert r["pontos"][0] == {"nivel": "bad", "texto": "Coleta não entregou até 09:45", "alvo": "fluxo-coleta",
                              "o_que_fazer": O_QUE_FAZER["coleta_sem_entrega"]}


def test_so_observacoes_nao_mudam_a_cor():
    medicoes = [{"ms": 900, "ok": True}, {"ms": 900, "ok": True}]
    horario = {"id": "horario_noticias", "titulo": "Horário das notícias", "farol": "warn", "numero": "90% sem hora"}
    saude = {"disponivel": True, "cartoes": [
        {"id": "contrato", "titulo": "Contrato com a coleta", "farol": "warn", "numero": "1 divergência"},
        {"id": "retornos", "titulo": "Preços suspeitos", "farol": "warn", "numero": "3 retornos"},
        horario]}
    divergencias = [{"numero": "1", "tema": "other_codes", "tabela": "v1-cadastro",
                     "detalhe": "RAIZ4 ainda aparece nos códigos antigos"}]
    suspeitos = [{"ticker": "RAIZ4", "data": "2026-11-09"}, {"ticker": "PCAR3", "data": "2023-08-23"},
                 {"ticker": "UGPA3", "data": "2021-06-28"}]
    eventos = situacao.eventos_tratados(RAIZ_REAL)
    assert ("PCAR3", "2023-08-23") in eventos
    lt_atrasada = rotina(inicio="2026-11-16T09:50:00-03:00", fim="2026-11-16T09:52:30-03:00")
    api_v, banco_v = api(medicoes, limite=0.5)   # média 0,90 s acima de 0,5 s: API lenta (observação)
    r = visao.resumo(HOJE, TRAVA, visao.fluxo(lt_atrasada), visao.linha_do_tempo(lt_atrasada, "09:45"), saude,
                     TESTES, api=api_v, banco=banco_v, top5=TOP5_OK, agora=AGORA, prazo_hhmm="09:45",
                     coleta_normal="08:35", divergencias=divergencias, suspeitos=suspeitos, eventos=eventos,
                     aceitos=ACEITOS_REAL)
    assert r["nivel"] == "ok" and r["frase"] == "Tudo funcionando"
    assert r["pontos"] == []
    obs = [o["texto"] for o in r["observacoes"]]
    assert obs == [
        "API lenta (média 0,90 s)",
        "Rotina terminou depois do prazo (atraso de 7 min 30 s)",
        "Divergência aceita: other_codes (RAIZ4 ainda aparece nos códigos antigos)",
        "Preço suspeito aceito: RAIZ4 em 09/11/2026",
        "Preços suspeitos já tratados: PCAR3 23/08/2023, UGPA3 28/06/2021",
        "Horário das notícias (90% sem hora)"]
    assert all(o["nivel"] == "obs" for o in r["observacoes"])


# ---------- regras de nível ----------

def test_divergencia_estrutural_nao_aceita_e_bad():
    divergencias = [{"numero": "1", "tema": "coluna_faltando", "tabela": "v1-precos", "detalhe": "falta a coluna volume"}]
    r = situacao_de(rotina(), saude=SAUDE_COM_CONTRATO_E_RETORNOS, divergencias=divergencias, suspeitos=[],
                    eventos=set(), aceitos=ACEITOS_REAL)
    assert r["nivel"] == "bad"
    assert r["pontos"][0] == {"nivel": "bad",
                              "texto": "Divergência estrutural no contrato: coluna_faltando (falta a coluna volume)",
                              "alvo": "saude-c-contrato", "o_que_fazer": O_QUE_FAZER["saude_contrato"]}


def test_divergencia_de_dado_nao_aceita_e_warn():
    divergencias = [{"numero": "1", "tema": "noticia_sem_hora", "tabela": "v1-noticias", "detalhe": "x"}]
    r = situacao_de(rotina(), saude=SAUDE_COM_CONTRATO_E_RETORNOS, divergencias=divergencias, suspeitos=[],
                    eventos=set(), aceitos=ACEITOS_REAL)
    assert r["nivel"] == "warn"
    assert textos(r) == ["Divergência nova com a coleta: noticia_sem_hora (x)"]


def test_suspeito_recente_nao_aceito_e_warn():
    suspeitos = [{"ticker": "ABCD3", "data": "2026-11-09"}]
    r = situacao_de(rotina(), saude=SAUDE_COM_CONTRATO_E_RETORNOS, divergencias=[], suspeitos=suspeitos,
                    eventos=set(), aceitos=ACEITOS_REAL)
    assert r["nivel"] == "warn"
    assert textos(r) == ["Preço suspeito novo: ABCD3 em 09/11/2026"]


def test_coleta_entregue_depois_do_normal_e_warn():
    coleta = {"consultado": True, "motivo": "entrega_concluida", "iniciada_em": "2026-11-16T08:00:01-03:00",
              "entrega_concluida_em": "2026-11-16T09:10:00-03:00"}
    r = situacao_de(rotina(coleta=coleta))
    assert r["nivel"] == "warn"
    assert r["pontos"] == [{"nivel": "warn", "texto": "Coleta entregou atrasada (09:10; o normal é até 08:35)",
                            "alvo": "fluxo-coleta", "o_que_fazer": O_QUE_FAZER["coleta_atrasada"]}]


def test_coleta_entregue_depois_do_prazo_e_bad():
    coleta = {"consultado": True, "motivo": "entrega_concluida", "iniciada_em": "2026-11-16T08:00:01-03:00",
              "entrega_concluida_em": "2026-11-16T09:50:00-03:00"}
    r = situacao_de(rotina(coleta=coleta))
    assert r["nivel"] == "bad"
    assert r["pontos"][0]["texto"] == "Coleta entregou às 09:50, depois do prazo de 09:45"


def test_banco_atrasado_e_bad():
    api_v, banco_v = api()
    banco_v = visao.bloco_banco({"configurada": True, "consultado_em": None, "medicoes": [], "timeout_s": 5.0,
                                 "consulta": dict(CONSULTA_OK, ultima_publicacao="2026-11-13")},
                                "2026-11-16", "2026-11-13")
    r = visao.resumo(HOJE, TRAVA, visao.fluxo(rotina()), visao.linha_do_tempo(rotina(), "09:45"), SAUDE, TESTES,
                     api=api_v, banco=banco_v, top5=TOP5_OK, agora=AGORA, prazo_hhmm="09:45", coleta_normal="08:35")
    assert r["nivel"] == "bad"
    assert r["pontos"][0]["alvo"] == "fluxo-banco" and r["pontos"][0]["nivel"] == "bad"


def test_api_sem_resposta_com_medicao_ok_e_intermitente():
    sem_resposta = dict(CONSULTA_OK, respondeu=False, http=None, status=None, banco=None, erro="TimeoutError")
    r = situacao_de(rotina(), medicoes=[{"ms": 800, "ok": True}], consulta=sem_resposta)
    assert r["nivel"] == "warn"
    assert r["pontos"][0]["texto"] == "API com erro intermitente (sem resposta na última consulta)"


def test_api_sem_resposta_em_todas_as_medicoes_e_fora_do_ar():
    sem_resposta = dict(CONSULTA_OK, respondeu=False, http=None, status=None, banco=None, erro="TimeoutError")
    r = situacao_de(rotina(), medicoes=[{"ms": None, "ok": False}], consulta=sem_resposta)
    assert r["nivel"] == "bad"
    assert r["pontos"][0] == {"nivel": "bad", "texto": "API fora do ar", "alvo": "fluxo-api",
                              "o_que_fazer": O_QUE_FAZER["api_fora"]}


def test_api_respondeu_com_falhas_antes_e_intermitente():
    r = situacao_de(rotina(), medicoes=[{"ms": 800, "ok": True}, {"ms": None, "ok": False}])
    assert r["nivel"] == "warn"
    assert textos(r) == ["API com erro intermitente (1 de 2 consultas sem resposta)"]


def test_sem_top5_com_rotina_ok_e_warn():
    r = situacao_de(rotina(), top5={"disponivel": False, "motivo": "experimento_top.json não encontrado"})
    assert r["nivel"] == "warn"
    assert r["pontos"][0]["texto"] == "Top 5 não gerado (experimento_top.json não encontrado)"


def test_rotina_de_hoje_nao_rodou_depois_do_prazo_e_bad():
    r = situacao_de(rotina_de_ontem(), agora=datetime(2026, 11, 16, 10, 30, tzinfo=SP), top5=None)
    assert r["nivel"] == "bad" and r["frase"] == "Não funcionou"
    assert r["pontos"][0] == {"nivel": "bad",
                              "texto": "Rotina de hoje (16/11) não rodou até 09:45: nada publicado para hoje",
                              "alvo": "agora", "o_que_fazer": O_QUE_FAZER["rotina_nao_rodou"]}


def test_rotina_de_hoje_ainda_nao_rodou_antes_do_prazo_e_so_observacao():
    r = situacao_de(rotina_de_ontem(), agora=datetime(2026, 11, 16, 8, 0, tzinfo=SP), top5=None)
    assert r["nivel"] == "ok" and r["pontos"] == []
    assert r["observacoes"][0] == {"nivel": "obs", "texto": "Rotina de hoje ainda não rodou (mostrando a de 13/11/2026)",
                                   "alvo": "agora", "o_que_fazer": O_QUE_FAZER["rotina_ainda_nao"]}


def test_sem_rotina_e_bad_com_mensagem_nova():
    r = visao.resumo(HOJE, TRAVA, visao.fluxo(None), None, SAUDE, TESTES)
    assert r["nivel"] == "bad" and r["frase"] == "Não funcionou"
    assert r["pontos"][0] == {"nivel": "bad", "texto": "Nenhuma rotina encontrada: nada publicado", "alvo": "agora",
                              "o_que_fazer": O_QUE_FAZER["sem_rotina"]}


def test_cartao_aceito_vira_observacao_com_o_que_fazer_de_aceite():
    horario = {"id": "horario_noticias", "titulo": "Horário das notícias", "farol": "warn", "numero": "90% sem hora"}
    saude = {"disponivel": True, "cartoes": [horario]}
    r = situacao_de(rotina(), saude=saude, aceitos=ACEITOS_REAL)
    motivo = situacao.aceito_cartao(ACEITOS_REAL, "horario_noticias")["motivo"]
    assert r["nivel"] == "ok" and r["pontos"] == []
    assert r["observacoes"] == [{"nivel": "obs", "texto": "Horário das notícias (90% sem hora)",
                                 "alvo": "saude-c-horario_noticias",
                                 "o_que_fazer": f"Nada: caso aceito em 16/11/2026 ({motivo})."}]


def test_resumo_sem_listas_novas_mantem_a_regra_antiga_do_contrato():
    saude = {"disponivel": True, "cartoes": [{"id": "contrato", "titulo": "Contrato com a coleta", "farol": "warn",
                                              "numero": "1 divergência"}]}
    r = situacao_de(rotina(), saude=saude)
    assert r["nivel"] == "warn"
    assert textos(r) == ["Contrato com a coleta (1 divergência)"]


# ---------- situacao.py ----------

def test_arquivo_real_de_aceitos_carrega_3_itens_validos():
    assert ACEITOS_REAL["disponivel"] is True
    assert len(ACEITOS_REAL["itens"]) == 3
    assert ACEITOS_REAL["invalidos"] == 0
    assert sorted(i["tipo"] for i in ACEITOS_REAL["itens"]) == ["cartao", "divergencia", "preco_suspeito"]


def test_ler_aceitos_arquivo_ausente_e_vazio(tmp_path):
    ausente = situacao.ler_aceitos(tmp_path / "nao_existe.yaml")
    assert ausente["disponivel"] is False and ausente["itens"] == [] and ausente["motivo"]
    quebrado = tmp_path / "quebrado.yaml"
    quebrado.write_text("aceitos: [\n", encoding="utf-8")
    assert situacao.ler_aceitos(quebrado)["disponivel"] is False
    sem_lista = tmp_path / "sem_lista.yaml"
    sem_lista.write_text('outra: "x"\n', encoding="utf-8")
    assert situacao.ler_aceitos(sem_lista)["disponivel"] is False


def test_ler_aceitos_ignora_item_invalido_e_conta(tmp_path):
    caminho = tmp_path / "aceitos.yaml"
    caminho.write_text(
        'aceitos:\n'
        '  - tipo: "cartao"\n'
        '    cartao: "horario_noticias"\n'
        '    motivo: "ok"\n'
        '    desde: "2026-11-16"\n'
        '  - tipo: "preco_suspeito"\n'
        '    ticker: "RAIZ4"\n'
        '    data: "09/11/2026"\n'          # data fora de AAAA-MM-DD
        '    motivo: "x"\n'
        '    desde: "2026-11-16"\n'
        '  - tipo: "tipo_desconhecido"\n'
        '    motivo: "x"\n'
        '    desde: "2026-11-16"\n'
        '  - tipo: "divergencia"\n'
        '    tema: "other_codes"\n'
        '    termo: "RAIZ4"\n'
        '    motivo: ""\n'                  # motivo vazio
        '    desde: "2026-11-16"\n'
        '  - tipo: "cartao"\n'
        '    cartao: "cobertura"\n'
        '    motivo: "x"\n'
        '    desde: 2026-11-16\n',          # sem aspas: vira data, não texto
        encoding="utf-8")
    r = situacao.ler_aceitos(caminho)
    assert r["disponivel"] is True
    assert [i["cartao"] for i in r["itens"]] == ["horario_noticias"]
    assert r["invalidos"] == 4


def test_aceito_divergencia_preco_e_cartao():
    div = {"tema": "other_codes", "detalhe": "RAIZ4 ainda aparece"}
    assert situacao.aceito_divergencia(ACEITOS_REAL, div)["termo"] == "RAIZ4"
    assert situacao.aceito_divergencia(ACEITOS_REAL, {"tema": "other_codes", "detalhe": "PETR4"}) is None
    assert situacao.aceito_divergencia(ACEITOS_REAL, {"tema": "outro", "detalhe": "RAIZ4"}) is None
    assert situacao.aceito_preco(ACEITOS_REAL, "RAIZ4", "2026-11-09")["tipo"] == "preco_suspeito"
    assert situacao.aceito_preco(ACEITOS_REAL, "RAIZ4", "2026-11-10") is None
    assert situacao.aceito_cartao(ACEITOS_REAL, "horario_noticias")["tipo"] == "cartao"
    assert situacao.aceito_cartao(None, "horario_noticias") is None
    assert situacao.aceito_preco("lixo", "RAIZ4", "2026-11-09") is None


def test_retornos_suspeitos_le_a_tabela_e_trata_ausencias(tmp_path):
    md = tmp_path / "diagnostico_banco.md"
    md.write_text(
        "## 13. Retornos diários suspeitos\n\n"
        "### Retornos diários suspeitos\n\n"
        "| ticker | data | aj_anterior | aj | retorno_aj | retorno_fech |\n"
        "|---|---|---|---|---|---|\n"
        "| PCAR3 | 2021-03-01 | 10.2961 | 21.857 | 1.1228 | 1.1228 |\n"
        "| RAIZ4 | 2026-11-09 | 0.1119 | 0.244 | 1.18 | 1.18 |\n",
        encoding="utf-8")
    assert situacao.retornos_suspeitos(md) == [{"ticker": "PCAR3", "data": "2021-03-01"},
                                               {"ticker": "RAIZ4", "data": "2026-11-09"}]
    sem_tabela = tmp_path / "sem_tabela.md"
    sem_tabela.write_text("## 13. Retornos\n- nenhum retorno diário suspeito\n", encoding="utf-8")
    assert situacao.retornos_suspeitos(sem_tabela) is None
    assert situacao.retornos_suspeitos(tmp_path / "nao_existe.md") == []


def test_eventos_tratados_le_o_parametros_yaml(tmp_path):
    cfg = tmp_path / "processamento" / "config"
    cfg.mkdir(parents=True)
    (cfg / "parametros.yaml").write_text(
        'fase1:\n'
        '  eventos_retorno_suspeito:\n'
        '    - ticker: "PCAR3"\n'
        '      datas: ["2023-08-23"]\n'
        '      motivo: "Cisão"\n',
        encoding="utf-8")
    assert situacao.eventos_tratados(tmp_path) == {("PCAR3", "2023-08-23")}
    assert situacao.eventos_tratados(tmp_path / "vazio") == set()


def test_ler_top5_casos(tmp_path):
    pasta = tmp_path / "saida" / "2026-11-16"
    pasta.mkdir(parents=True)
    ausente = situacao.ler_top5(tmp_path, "saida", "2026-11-16")
    assert ausente["disponivel"] is False and ausente["motivo"] == "experimento_top.json não encontrado"
    (pasta / "experimento_top.json").write_text('{"registros": []}', encoding="utf-8")
    assert situacao.ler_top5(tmp_path, "saida", "2026-11-16")["motivo"] == "sem registros"
    (pasta / "experimento_top.json").write_text(
        '{"registros": [{"valido_para_historico": false, "avisos": ["aviso"], '
        '"ranking": [1, 2, 3], "gerado_em": "2026-11-16T10:40:00-03:00"}]}', encoding="utf-8")
    r = situacao.ler_top5(tmp_path, "saida", "2026-11-16")
    assert r == {"disponivel": True, "motivo": None, "valido_para_historico": False, "avisos": ["aviso"],
                 "n_ranking": 3, "gerado_em": "2026-11-16T10:40:00-03:00"}
    assert situacao.ler_top5(tmp_path, "saida", None)["disponivel"] is False


def test_parametros_novos_do_painel_sao_validados():
    from processamento.painel import leitores
    p = leitores.ler_parametros_painel(RAIZ_REAL)
    assert p["coleta_entrega_normal"] == "08:35"
    assert p["suspeito_novo_dias"] == 30
    assert leitores._hora_hhmm("25:00") is False and leitores._hora_hhmm("08:35") is True
