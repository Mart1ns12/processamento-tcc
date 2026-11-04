"""Testes de processamento/painel/aba_execucoes.py: dias completos a partir dos logs dia-*.log.

Só usa pasta temporária (tmp_path): nenhum teste usa banco ou rede.
"""

from processamento.painel.aba_execucoes import bloco_execucoes, etapas_do_log, ler_logs_dia

LOG_ANTIGO = [
    "# painel: acao=dia inicio=2026-11-03T11:19:57-03:00 comando=python -m processamento.painel.dia --data 2026-11-03",
    "# dia: etapa=rotina inicio=11:19:58",
    "Saída de 2026-11-03 em saida/2026-11-03: status ok",
    "# dia: etapa=rotina fim codigo=0 detalhe=status ok",
    "# dia: etapa=carga inicio=11:25:25",
    "# dia: etapa=carga fim codigo=0 detalhe=status ok",
    "# dia: etapa=publicador inicio=11:30:30",
    "03/11/2026 publicado (modo normal, execução: ok) em 8,2 s",
    "  correções..................... 193 (fotos e pontos de série)",
    "# dia: etapa=publicador fim codigo=0 detalhe=publicado (completo)",
    "# dia: resultado=completa publicado no banco da API (completo)",
    "# painel: fim=2026-11-03T11:30:42-03:00 codigo=0",
]

LOG_NOVO = [
    "# painel: acao=dia inicio=2026-11-04T08:00:00-03:00 comando=python -m processamento.painel.dia --data 2026-11-04",
    "# dia: etapa=rotina inicio=2026-11-04T08:00:01-03:00",
    "# dia: etapa=rotina fim codigo=0 em=2026-11-04T08:05:01-03:00 detalhe=status ok",
    "# dia: etapa=carga inicio=2026-11-04T08:05:02-03:00",
    "# dia: etapa=carga fim codigo=0 em=2026-11-04T08:09:02-03:00 detalhe=status ok",
    "# dia: etapa=publicador inicio=2026-11-04T08:09:03-03:00",
    "# dia: etapa=publicador fim codigo=0 em=2026-11-04T08:09:13-03:00 detalhe=publicado (completo)",
    "# dia: resultado=completa publicado no banco da API (completo)",
    "# painel: fim=2026-11-04T08:09:14-03:00 codigo=0",
]

LOG_FALHOU = [
    "# painel: acao=dia inicio=2026-10-28T10:34:41-03:00 comando=python -m processamento.painel.dia --data 2026-10-28",
    "# dia: etapa=rotina inicio=10:34:42",
    "# dia: etapa=rotina fim codigo=4 detalhe=status falhou",
    "# dia: etapa=carga pulada motivo=a rotina falhou",
    "# dia: etapa=publicador inicio=10:35:05",
    "28/10/2026: só a execução foi gravada (sem carga completa)",
    "# dia: etapa=publicador fim codigo=0 detalhe=só a execução",
    "# dia: resultado=so_execucao só a execução gravada (a rotina falhou)",
    "# painel: fim=2026-10-28T10:35:06-03:00 codigo=0",
]


def _grava(pasta, nome, linhas):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _etapa(bloco, id_etapa):
    return next(e for e in bloco["etapas"] if e["id"] == id_etapa)


def test_log_antigo_so_tem_hora_e_fim_aproximado(tmp_path):
    _grava(tmp_path, "dia-2026-11-03_111957.log", LOG_ANTIGO)
    bloco = bloco_execucoes(ler_logs_dia(tmp_path))
    assert bloco["disponivel"] is True
    assert bloco["dias"]["2026-11-03"] == {
        "data": "2026-11-03", "arquivo": "dia-2026-11-03_111957.log", "inicio_hhmm": "11:19", "fim_hhmm": "11:30",
        "codigo": 0, "resultado": "completa", "resultado_texto": "publicado no banco da API (completo)",
        "etapas": [
            {"id": "rotina", "rotulo": "Rotina", "estado": "concluida", "detalhe": "status ok",
             "duracao_s": 327, "duracao_texto": "5 min 27 s", "aproximada": True},
            {"id": "carga", "rotulo": "Carga completa", "estado": "concluida", "detalhe": "status ok",
             "duracao_s": 305, "duracao_texto": "5 min 5 s", "aproximada": True},
            {"id": "publicador", "rotulo": "Publicador", "estado": "concluida", "detalhe": "publicado (completo)",
             "duracao_s": 12, "duracao_texto": "12 s", "aproximada": True},
        ],
        "maximo_s": 327, "aproximada": True, "execucoes_no_dia": 1,
    }


def test_log_novo_tem_fim_exato(tmp_path):
    _grava(tmp_path, "dia-2026-11-04_080000.log", LOG_NOVO)
    bloco = bloco_execucoes(ler_logs_dia(tmp_path))
    dia = bloco["dias"]["2026-11-04"]
    assert [e["duracao_s"] for e in dia["etapas"]] == [300, 240, 10]
    assert [e["duracao_texto"] for e in dia["etapas"]] == ["5 min 0 s", "4 min 0 s", "10 s"]
    assert all(e["aproximada"] is False for e in dia["etapas"])
    assert dia["aproximada"] is False
    assert dia["maximo_s"] == 300


def test_ultimo_log_e_cortes_de_linhas(tmp_path):
    _grava(tmp_path, "dia-2026-11-03_111957.log", LOG_ANTIGO)
    _grava(tmp_path, "dia-2026-11-04_080000.log", LOG_NOVO)
    bloco = bloco_execucoes(ler_logs_dia(tmp_path))
    ultimo = bloco["ultimo_log"]
    assert ultimo["arquivo"] == "dia-2026-11-04_080000.log"
    assert ultimo["data"] == "2026-11-04"
    assert ultimo["titulo"] == "04/11 · 08:00 → 08:09"
    assert ultimo["linhas"] == LOG_NOVO
    assert ultimo["cortadas"] == 0

    corte = bloco_execucoes(ler_logs_dia(tmp_path), max_linhas=3)["ultimo_log"]
    assert corte["linhas"] == LOG_NOVO[-3:]
    assert corte["cortadas"] == len(LOG_NOVO) - 3


def test_log_falhou_e_execucoes_no_dia(tmp_path):
    _grava(tmp_path, "dia-2026-10-28_103441.log", LOG_FALHOU)
    _grava(tmp_path, "dia-2026-10-28_111035.log", LOG_FALHOU)
    bloco = bloco_execucoes(ler_logs_dia(tmp_path))
    dia = bloco["dias"]["2026-10-28"]
    assert dia["arquivo"] == "dia-2026-10-28_111035.log"
    assert dia["execucoes_no_dia"] == 2
    assert dia["resultado"] == "so_execucao"
    assert dia["resultado_texto"] == "só a execução gravada (a rotina falhou)"

    rotina = _etapa(dia, "rotina")
    assert rotina["estado"] == "erro"
    assert rotina["duracao_s"] == 23
    assert rotina["aproximada"] is True

    carga = _etapa(dia, "carga")
    assert carga["estado"] == "pulada"
    assert carga["duracao_s"] is None
    assert carga["duracao_texto"] == "pulada"
    assert carga["aproximada"] is False

    publicador = _etapa(dia, "publicador")
    assert publicador["estado"] == "concluida"
    assert publicador["duracao_s"] == 1


def test_log_sem_rodape_fica_em_andamento(tmp_path):
    linhas = [
        "# painel: acao=dia inicio=2026-11-03T11:19:57-03:00 comando=python -m processamento.painel.dia --data 2026-11-03",
        "# dia: etapa=rotina inicio=11:19:58",
    ]
    _grava(tmp_path, "dia-2026-11-03_111957.log", linhas)
    bloco = bloco_execucoes(ler_logs_dia(tmp_path))
    assert bloco["ultimo_log"]["titulo"].endswith("→ em andamento ou interrompido")
    rotina = _etapa(bloco["dias"]["2026-11-03"], "rotina")
    assert rotina["estado"] == "agora"
    assert rotina["duracao_s"] is None
    assert rotina["duracao_texto"] == "em andamento"


def test_log_sem_data_no_comando_nao_entra_em_dias(tmp_path):
    linhas = [
        "# painel: acao=dia inicio=2026-11-03T11:19:57-03:00 comando=python -m processamento.painel.dia",
        "# painel: fim=2026-11-03T11:30:42-03:00 codigo=0",
    ]
    _grava(tmp_path, "dia-2026-11-03_111957.log", linhas)
    bloco = bloco_execucoes(ler_logs_dia(tmp_path))
    assert bloco["dias"] == {}
    assert bloco["ultimo_log"]["arquivo"] == "dia-2026-11-03_111957.log"


def test_log_antigo_cruzando_a_meia_noite(tmp_path):
    linhas = [
        "# painel: acao=dia inicio=2026-11-03T23:59:50-03:00 comando=python -m processamento.painel.dia --data 2026-11-03",
        "# dia: etapa=rotina inicio=23:59:55",
        "# dia: etapa=rotina fim codigo=0 detalhe=status ok",
        "# dia: etapa=carga inicio=00:00:10",
        "# dia: etapa=carga fim codigo=0 detalhe=status ok",
        "# painel: fim=2026-11-04T00:00:20-03:00 codigo=0",
    ]
    _grava(tmp_path, "dia-2026-11-03_235950.log", linhas)
    dia = bloco_execucoes(ler_logs_dia(tmp_path))["dias"]["2026-11-03"]
    assert _etapa(dia, "rotina")["duracao_s"] == 15
    assert _etapa(dia, "carga")["duracao_s"] == 10


def test_pasta_inexistente_sem_logs(tmp_path):
    logs = ler_logs_dia(tmp_path / "nao_existe")
    assert logs == []
    assert bloco_execucoes(logs) == {
        "disponivel": False,
        "motivo": "Nenhum dia completo rodado pelo painel ainda (logs/painel/dia-*.log).",
        "fonte": "logs/painel/dia-*.log (o painel guarda os 20 mais recentes)",
        "dias": {},
        "ultimo_log": None,
    }


def test_etapas_do_log_ignora_etapa_fim_e_usa_linhas_do_log(tmp_path):
    _grava(tmp_path, "dia-2026-11-04_080000.log", LOG_NOVO)
    log = ler_logs_dia(tmp_path)[0]
    etapas = etapas_do_log(log)
    assert [e["id"] for e in etapas] == ["rotina", "carga", "publicador"]
    assert all(e["estado"] == "concluida" for e in etapas)
