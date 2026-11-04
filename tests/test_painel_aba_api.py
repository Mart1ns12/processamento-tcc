from __future__ import annotations

from processamento.painel.aba_api import publicacoes, publicador_do_log

LOG_PUB = """\
# painel: acao=dia inicio=2026-11-03T11:19:57-03:00 comando=python -m processamento.painel.dia --data 2026-11-03
# dia: etapa=publicador inicio=11:30:30
03/11/2026 publicado (modo normal, execução: ok) em 8,2 s
  resumo_acao................... 85 novos
  noticias_dia.................. 85 novos
  mercado_dia................... 1 novo
  execucao...................... 1 novo
  top 5 (experimento_top)....... não publicado (pacote ausente)
  series_diarias................ 177 pontos novos (177 séries)
  correções..................... 193 (fotos e pontos de série)
  ruído numérico................ 33.186 pontos com ruído numérico (< 1e-6)
  ajustes de série.............. 11
  fundamentos_trimestrais....... 30 versões novas, 36 fechadas, 0 corrigidas
  proventos..................... 13 versões novas, 0 fechadas, 0 corrigidas
# dia: etapa=publicador fim codigo=0 detalhe=publicado (completo)
# painel: fim=2026-11-03T11:30:42-03:00 codigo=0
"""

LOG_REPUB = """\
# painel: acao=dia inicio=2026-10-27T16:35:21-03:00 comando=python -m processamento.painel.dia --data 2026-10-27
# dia: etapa=publicador inicio=16:39:00
27/10/2026 publicado (modo republicacao, execução: ok) em 1,9 s
  execucao...................... 1 novo
# dia: etapa=publicador fim codigo=0 detalhe=publicado (completo)
# painel: fim=2026-10-27T16:40:00-03:00 codigo=0
"""

LOG_SO_EXECUCAO = """\
# painel: acao=dia inicio=2026-10-28T10:34:41-03:00 comando=python -m processamento.painel.dia --data 2026-10-28
# dia: etapa=publicador inicio=10:40:00
28/10/2026: só a execução foi gravada (sem carga completa)
# dia: etapa=publicador fim codigo=0 detalhe=publicado (parcial)
# painel: fim=2026-10-28T10:45:00-03:00 codigo=0
"""


def _log(arquivo: str, data: str, inicio: str, fim: str, texto: str) -> dict:
    return {"arquivo": arquivo, "data": data, "inicio": inicio, "fim": fim, "codigo": 0, "parado": False,
            "linhas": texto.splitlines()}


def test_publicador_do_log_le_cabecalho_itens_e_pacotes():
    pub = publicador_do_log(LOG_PUB.splitlines())
    assert pub["modo"] == "normal" and pub["execucao"] == "ok" and pub["segundos"] == 8.2
    assert pub["correcoes"] == 193 and pub["ruido"] == 33186 and pub["ajustes"] == 11
    assert [p["pacote"] for p in pub["pacotes"]] == [
        "resumo_acao", "noticias_dia", "mercado_dia", "execucao", "experimento_top",
        "series_diarias", "fundamentos_trimestrais", "proventos"]
    assert pub["pacotes"][4] == {"pacote": "experimento_top", "rotulo": "top 5 (experimento_top)",
                                 "texto": "não publicado (pacote ausente)", "estado": "retido"}
    assert pub["pacotes"][5]["texto"] == "177 pontos novos (177 séries)"


def test_publicador_do_log_republicacao_sem_linha_de_correcoes_fica_none():
    pub = publicador_do_log(LOG_REPUB.splitlines())
    assert pub["modo"] == "republicacao" and pub["segundos"] == 1.9
    assert pub["correcoes"] is None and pub["ruido"] is None and pub["ajustes"] is None


def test_publicador_do_log_sem_linha_de_publicacao_devolve_none():
    assert publicador_do_log(LOG_SO_EXECUCAO.splitlines()) is None
    assert publicador_do_log([]) is None


def test_publicacoes_ordena_correcoes_e_pega_a_ultima():
    logs = [
        _log("dia-2026-11-03_111957.log", "2026-11-03", "2026-11-03T11:19:57-03:00",
             "2026-11-03T11:30:42-03:00", LOG_PUB),
        _log("dia-2026-10-28_103441.log", "2026-10-28", "2026-10-28T10:34:41-03:00",
             "2026-10-28T10:45:00-03:00", LOG_SO_EXECUCAO),
        _log("dia-2026-10-27_163521.log", "2026-10-27", "2026-10-27T16:35:21-03:00",
             "2026-10-27T16:40:00-03:00", LOG_REPUB),
    ]
    r = publicacoes(logs)
    assert r["disponivel"] is True and r["motivo"] is None
    assert r["fonte"] == "logs/painel/dia-*.log (saída do publicador)"
    assert [c["data"] for c in r["correcoes"]] == ["2026-10-27", "2026-11-03"]
    assert r["correcoes"][0] == {"data": "2026-10-27", "data_texto": "27/10", "hhmm": "16:40",
                                 "arquivo": "dia-2026-10-27_163521.log", "modo": "republicacao",
                                 "correcoes": None, "ruido": None, "ajustes": None}
    assert r["correcoes"][1] == {"data": "2026-11-03", "data_texto": "03/11", "hhmm": "11:30",
                                 "arquivo": "dia-2026-11-03_111957.log", "modo": "normal",
                                 "correcoes": 193, "ruido": 33186, "ajustes": 11}
    assert r["maximo"] == 193
    ultima = r["ultima"]
    assert ultima["data"] == "2026-11-03" and ultima["data_texto"] == "03/11/2026" and ultima["hhmm"] == "11:30"
    assert ultima["modo"] == "normal" and ultima["execucao"] == "ok"
    assert ultima["segundos"] == 8.2 and ultima["segundos_texto"] == "8,2 s"
    assert ultima["n_pacotes"] == 7 and len(ultima["pacotes"]) == 8


def test_publicacoes_sem_nenhuma_publicacao_fica_indisponivel():
    for logs in ([], [_log("dia-2026-10-28_103441.log", "2026-10-28", "2026-10-28T10:34:41-03:00",
                           "2026-10-28T10:45:00-03:00", LOG_SO_EXECUCAO)]):
        r = publicacoes(logs)
        assert r["disponivel"] is False and r["correcoes"] == [] and r["maximo"] is None and r["ultima"] is None
        assert r["motivo"].startswith("Nenhuma publicação completa")
