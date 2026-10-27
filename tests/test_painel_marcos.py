"""Testes de processamento/painel/marcos.py: etapas de cada ação a partir das linhas do log.

Função pura: nenhum teste usa banco, rede ou arquivo. Os valores esperados vêm do plano visual (T1 a T15).
"""

from processamento.painel.marcos import marcos_acao


def estados(resultado):
    return [e["estado"] for e in resultado]


def detalhes(resultado):
    return [e["detalhe"] for e in resultado]


ROTINA_OK = [
    "Rotina de 2026-10-23 (início 08:00:00)",
    "08:00:00 consulta 1: daily 2026-10-23-daily-080001 (cron, em_andamento), entrega em_andamento -> esperar (entrega_pendente)",
    "08:05:00 consulta 2: daily 2026-10-23-daily-080001 (cron, concluida), entrega concluida -> gerar",
    "Saída de 2026-10-23 em C:\\x\\saida\\2026-10-23: status ok",
    "- Gerado depois das 10h: não entra no histórico do experimento.",
]

SIGNIFICADO_OK = "ok, parcial ou dia sem pregão (veja o log)"


def test_t1_rotina_concluida_com_codigo_zero():
    r = marcos_acao("rotina", ROTINA_OK, rodando=False, codigo=0, significado=SIGNIFICADO_OK)
    assert r == [
        {"id": "inicio", "rotulo": "Rotina iniciada", "estado": "concluida", "detalhe": "início 08:00:00"},
        {"id": "coleta", "rotulo": "Conferindo se a coleta do dia terminou", "estado": "concluida",
         "detalhe": "consulta 2 às 08:05:00: coleta pronta"},
        {"id": "calculo", "rotulo": "Calculando indicadores, top 5 e pacotes (só leitura do banco)",
         "estado": "concluida", "detalhe": None},
        {"id": "saida", "rotulo": "Gravando os pacotes do dia", "estado": "concluida", "detalhe": "status ok"},
        {"id": "fim", "rotulo": "Encerrado", "estado": "concluida", "detalhe": SIGNIFICADO_OK},
    ]


def test_t2_rotina_rodando_na_primeira_consulta():
    r = marcos_acao("rotina", ROTINA_OK[:2], rodando=True, codigo=None, significado=None)
    assert estados(r) == ["concluida", "agora", "espera", "espera", "espera"]
    assert r[1]["detalhe"] == "consulta 1 às 08:00:00: esperar (entrega_pendente)"


def test_t3_rotina_rodando_depois_da_coleta_pronta():
    r = marcos_acao("rotina", ROTINA_OK[:3], rodando=True, codigo=None, significado=None)
    assert estados(r) == ["concluida", "concluida", "agora", "espera", "espera"]


def test_t4_dia_sem_pregao_pula_as_etapas():
    linhas = [
        "Rotina de 2026-10-24 (início 00:33:35, --sem-esperar)",
        "2026-10-24 não é pregão previsto (sábado): nada a gerar.",
    ]
    r = marcos_acao("rotina", linhas, rodando=False, codigo=0, significado=SIGNIFICADO_OK)
    assert estados(r) == ["concluida", "pulada", "pulada", "pulada", "concluida"]
    assert r[0]["detalhe"] == "início 00:33:35 (--sem-esperar)"
    assert r[-1]["detalhe"] == "não é pregão previsto (sábado): nada a gerar"


def test_t5_trava_erra_a_coleta():
    linhas = [
        "Rotina de 2026-10-23 (início 09:00:00)",
        "outra rotina em andamento desde 2026-10-23T08:00:00-03:00 (pid 999). Rodada cancelada; nada foi gravado.",
    ]
    r = marcos_acao("rotina", linhas, rodando=False, codigo=5, significado="outra rotina em andamento (trava)")
    assert estados(r) == ["concluida", "erro", "pulada", "pulada", "erro"]
    assert r[1]["detalhe"] == linhas[1]
    assert r[-1]["detalhe"] == "outra rotina em andamento (trava)"


def test_t6_traceback_sem_marcador_erra_a_etapa_atual():
    linhas = ["Rotina de 2026-10-23 (início 08:00:00)", "Traceback (most recent call last):"]
    r = marcos_acao("rotina", linhas, rodando=False, codigo=1, significado="código 1")
    assert estados(r) == ["concluida", "erro", "pulada", "pulada", "erro"]
    assert r[1]["detalhe"] is None
    assert r[-1]["detalhe"] == "código 1"


def test_t7_testes_concluidos_com_resumo_do_pytest():
    linhas = ["........ [ 50%]", "....s... [100%]", "15 passed, 1 skipped in 2.00s"]
    r = marcos_acao("testes", linhas, rodando=False, codigo=0, significado="todos os testes passaram")
    assert estados(r) == ["concluida", "concluida", "concluida"]
    assert detalhes(r) == ["testes encontrados", "15 passed, 1 skipped in 2.00s", "todos os testes passaram"]


def test_t8_testes_em_andamento_mostram_percentual():
    r = marcos_acao("testes", ["........ [ 50%]"], rodando=True, codigo=None, significado=None)
    assert estados(r) == ["concluida", "agora", "espera"]
    assert r[1]["detalhe"] == "50%"


def test_t9_testes_parados_pelo_painel():
    r = marcos_acao("testes", ["inicio"], rodando=False, codigo=1, significado="parado pelo painel")
    assert estados(r) == ["erro", "pulada", "erro"]
    assert r[-1]["detalhe"] == "parado pelo painel"


def test_t10_diagnostico_relatorio_sem_divergencias():
    linhas = ["Relatório: C:\\x\\docs\\diagnostico_banco.md | divergências: 0"]
    r = marcos_acao("diagnostico", linhas, rodando=False, codigo=0, significado="relatório gerado")
    assert estados(r) == ["concluida", "concluida", "concluida"]
    assert r[1]["detalhe"] == "0 divergências"


def test_t10_diagnostico_relatorio_uma_divergencia():
    linhas = ["Relatório: C:\\x\\docs\\diagnostico_banco.md | divergências: 1"]
    r = marcos_acao("diagnostico", linhas, rodando=False, codigo=0, significado="relatório gerado")
    assert r[1]["detalhe"] == "1 divergência"


def test_t11_diagnostico_configuracao_incompleta_erra_a_leitura():
    linhas = ["Configuração do banco incompleta: falta IP_BANCO"]
    r = marcos_acao("diagnostico", linhas, rodando=False, codigo=2, significado="configuração do banco incompleta")
    assert estados(r) == ["erro", "pulada", "erro"]
    assert r[0]["detalhe"] == "Configuração do banco incompleta: falta IP_BANCO"


def test_t12_carga_concluida():
    linhas = [
        "Saída de 2026-10-23 em C:\\x\\saida_completa\\2026-10-23: status ok",
        "- Carga completa.",
    ]
    r = marcos_acao("carga", linhas, rodando=False, codigo=0, significado="ok ou parcial")
    assert estados(r) == ["concluida", "concluida", "concluida"]
    assert r[1]["detalhe"] == "status ok"


def test_t13_acao_sem_etapas_devolve_lista_vazia():
    assert marcos_acao(None, [], rodando=False, codigo=None, significado=None) == []
    assert marcos_acao("apagar", [], rodando=False, codigo=None, significado=None) == []


def test_t14_diagnostico_rodando_sem_linhas():
    r = marcos_acao("diagnostico", [], rodando=True, codigo=None, significado=None)
    assert estados(r) == ["agora", "espera", "espera"]


def test_t15_configuracao_invalida_na_rotina():
    linhas = ["Configuração inválida: rotina.prazo"]
    r = marcos_acao("rotina", linhas, rodando=False, codigo=2, significado="configuração (banco, parâmetros ou calendário)")
    assert estados(r) == ["erro", "pulada", "pulada", "pulada", "erro"]
    assert r[0]["detalhe"] == "Configuração inválida: rotina.prazo"


def test_dia_rodando_so_com_a_rotina_iniciada():
    r = marcos_acao("dia", ["# dia: etapa=rotina inicio=10:00:00"], rodando=True, codigo=None, significado=None)
    assert estados(r) == ["agora", "espera", "espera", "espera"]
    assert [e["id"] for e in r] == ["rotina", "carga", "publicador", "fim"]


def test_dia_falhou_so_execucao_termina_com_marcos_certos():
    linhas = [
        "# dia: etapa=rotina inicio=10:00:00",
        "# dia: etapa=rotina fim codigo=4 detalhe=status falhou",
        "# dia: etapa=carga pulada motivo=a rotina falhou",
        "# dia: etapa=publicador inicio=10:00:05",
        "# dia: etapa=publicador fim codigo=0 detalhe=só a execução",
    ]
    r = marcos_acao("dia", linhas, rodando=False, codigo=0, significado="publicado: completo, ou só a execução")
    assert estados(r) == ["erro", "pulada", "concluida", "concluida"]
    assert r[0]["detalhe"] == "status falhou"
    assert r[1]["detalhe"] == "a rotina falhou"
    assert r[2]["detalhe"] == "só a execução"


def test_dia_parado_no_meio_marca_etapa_atual_como_erro():
    linhas = ["# dia: etapa=rotina inicio=10:00:00", "# dia: etapa=rotina fim codigo=0 detalhe=status ok",
              "# dia: etapa=carga inicio=10:01:00"]
    r = marcos_acao("dia", linhas, rodando=False, codigo=1, significado="parado pelo painel")
    assert estados(r) == ["concluida", "erro", "pulada", "erro"]
    assert r[3]["detalhe"] == "parado pelo painel"
