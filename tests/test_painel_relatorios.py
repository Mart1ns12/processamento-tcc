"""Testes de processamento/painel/relatorios.py: logs da rotina, diagnóstico, experimento e pytest.

Usam a árvore de fixtures de tests/dados/painel/raiz copiada por montar_raiz (tmp_path).
Nenhum teste usa banco ou rede, nem grava em tests/dados/.
"""

import json
import shutil

from fabrica_painel import montar_raiz

from processamento.painel import relatorios
from processamento.painel.relatorios import (
    analisar_log_rotina,
    caminho_ultimo_relatorio,
    ler_diagnostico,
    ler_experimento,
    ler_logs_rotina,
    ler_ultimo_pytest,
    resultado_terminal,
    trava_teste_final,
)

PARAMS = {
    "modelo_oficial": False,
    "teste_final": {"inicio": "2026-06-23", "fim": None, "liberado": False},
    "publicar_top_provisorio": False,
    "pasta_saida": "saida",
    "pasta_logs": "logs",
    "trava": "saida/estado/rotina.trava",
    "trava_validade_horas": 6.0,
    "erro": None,
}


def _com(**alterar):
    """Cópia de PARAMS com chaves trocadas."""
    return {**PARAMS, **alterar}


# ---------------------------------------------------------------- logs da rotina

def test_logs_rotina_arquivos_e_rodadas(tmp_path):
    raiz = montar_raiz(tmp_path)
    resultado = ler_logs_rotina(raiz / "logs")

    assert resultado["disponivel"] is True
    assert resultado["motivo"] is None
    assert [a["data"] for a in resultado["arquivos"]] == ["2026-10-26", "2026-10-24", "2026-10-23"]

    dia_26, dia_24, dia_23 = (a["rodadas"] for a in resultado["arquivos"])

    assert len(dia_26) == 1
    assert dia_26[0]["resultado"] == "incompleta"
    assert len(dia_26[0]["consultas"]) == 1

    assert len(dia_24) == 1
    assert dia_24[0]["inicio"] == "00:33:35"
    assert dia_24[0]["sem_esperar"] is True
    assert dia_24[0]["resultado"] == "sem_pregao"
    assert dia_24[0]["detalhe"] == "sábado"

    assert len(dia_23) == 3
    r0, r1, r2 = dia_23
    assert r0["inicio"] == "00:34:09"
    assert r0["sem_esperar"] is True
    assert r0["consultas"] == [{
        "hora": "00:34:09",
        "numero": 1,
        "texto": "daily 2026-10-23-daily-080001 (cron, concluida), entrega concluida -> gerar",
    }]
    assert r0["resultado"] == "ok"
    assert len(r0["avisos"]) == 2
    assert r0["avisos"][0] == "Composição do Ibovespa vazia: universo = composição atual (ações do cadastro)."

    assert r1["inicio"] == "08:00:00"
    assert r1["sem_esperar"] is False
    assert len(r1["consultas"]) == 2
    assert r1["resultado"] == "parcial"
    assert r1["avisos"] == ["Pacote noticias_dia reprovado na validação."]

    assert r2["inicio"] == "09:00:00"
    assert r2["consultas"] == []
    assert r2["resultado"] == "trava"
    assert r2["detalhe"].startswith("outra rotina em andamento desde 2026-10-23T08:00:00-03:00")
    assert r2["avisos"] == []


def test_logs_rotina_pasta_vazia_ou_ausente(tmp_path):
    (tmp_path / "vazio").mkdir()
    for pasta in (tmp_path / "vazio", tmp_path / "nao_existe"):
        resultado = ler_logs_rotina(pasta)
        assert resultado == {"disponivel": False, "motivo": "nenhum log da rotina em logs/", "arquivos": []}


def test_analisar_texto_sem_rodada_e_configuracao():
    assert analisar_log_rotina("lixo\n") == []

    texto = (
        "linha solta antes\n"
        "Rotina de 2026-10-23 (início 00:00:00)\n"
        "Configuração do banco incompleta: x\n"
    )
    rodadas = analisar_log_rotina(texto)
    assert len(rodadas) == 1
    assert rodadas[0]["resultado"] == "configuracao"
    assert rodadas[0]["detalhe"] == "Configuração do banco incompleta: x"
    assert rodadas[0]["sem_esperar"] is False


# ---------------------------------------------------------------- diagnóstico

def test_diagnostico_fixture(tmp_path):
    raiz = montar_raiz(tmp_path)
    resultado = ler_diagnostico(raiz / "docs" / "diagnostico_banco.md")

    assert resultado["disponivel"] is True
    assert resultado["motivo"] is None
    assert resultado["gerado_em"] == "2026-10-24 21:08 (America/Sao_Paulo)"
    assert resultado["sem_divergencias"] is False
    assert resultado["divergencias"] == [
        {"numero": "1", "tema": "coluna_faltando", "tabela": "v1-precos", "detalhe": "falta a coluna volume"},
        {"numero": "2", "tema": "falha_consulta", "tabela": "-", "detalhe": "Balanços: OperationalError: x | y"},
    ]
    assert resultado["secoes"] == [
        {"numero": 1, "titulo": "Existência das tabelas", "notas": ["8 de 8 tabelas do contrato existem."]},
        {
            "numero": 2,
            "titulo": "Preços (v1-precos)",
            "notas": [
                "82 dias úteis sem pregão no IBOV (inclui feriados)",
                "AZUL3: 1 pregões faltando (pode ser suspensão)",
            ],
        },
        {"numero": 3, "titulo": "Colunas vazias", "notas": []},
    ]
    assert "banco_teste" not in json.dumps(resultado)
    assert "MySQL" not in json.dumps(resultado)


def test_diagnostico_sem_divergencias(tmp_path):
    arquivo = tmp_path / "diagnostico.md"
    arquivo.write_text(
        "# Diagnóstico\n\n## Divergências × especificação\n\nNenhuma divergência encontrada.\n\n## 1. X\n\n- a\n",
        encoding="utf-8",
    )
    resultado = ler_diagnostico(arquivo)
    assert resultado["sem_divergencias"] is True
    assert resultado["divergencias"] == []
    assert resultado["secoes"] == [{"numero": 1, "titulo": "X", "notas": ["a"]}]


def test_diagnostico_ausente_e_formato_desconhecido(tmp_path):
    ausente = ler_diagnostico(tmp_path / "nao_existe.md")
    assert ausente == {
        "disponivel": False,
        "motivo": "docs/diagnostico_banco.md não encontrado (rode o diagnóstico)",
    }

    arquivo = tmp_path / "oi.md"
    arquivo.write_text("oi", encoding="utf-8")
    assert ler_diagnostico(arquivo) == {"disponivel": False, "motivo": "formato não reconhecido"}


# ---------------------------------------------------------------- experimento

def test_experimento_resumo(tmp_path):
    raiz = montar_raiz(tmp_path)
    resultado = ler_experimento(raiz, PARAMS)

    assert resultado["situacao_modelo"] == "provisório"
    assert resultado["top_publicado"] is False
    assert resultado["mostrar_aviso"] is True
    assert resultado["trava_teste_final"]["estado"] == "ativa"
    assert resultado["n_meta"] == 3

    assert resultado["modelo_em_uso"] == {
        "arquivo": "xgb-2026-06.meta.json",
        "mes": "2026-06",
        "modelo": "3",
        "provisorio": True,
        "periodo_treino": {"inicio": "2024-01-02", "fim": "2026-06-19"},
        "n_linhas_treino": 45765,
        "gerado_em": "2026-10-24T18:42:20-03:00",
        "auc_medio_pregao": 0.5174,
        "acerto_top5": 0.5023,
        "calibracao_aprovada": True,
        "chance_exibida": False,
        "aviso": "modelo provisório: treinado com ~1 ano; só teste de funcionamento",
    }
    assert resultado["modelo_sombra"]["arquivo"] == "xgb-m1-2026-06.meta.json"
    assert resultado["modelo_sombra"]["calibracao_aprovada"] is None

    dev = resultado["desenvolvimento"]
    assert dev["disponivel"] is True
    assert dev["pasta"] == "dev-2026-10-23"
    assert dev["modo"] == "desenvolvimento"
    assert dev["aviso_funcionamento"] is True
    assert dev["gerado_em"] == "2026-10-24T18:42:18-03:00"
    assert dev["periodo"]["n_pregoes"] == 616
    assert dev["acaso_top5"] == {"media": 0.4811, "faixa": [0.4638, 0.4987]}
    assert dev["modelos"] == [
        {"nome": "modelo_3", "rotulo": "Modelo 3 (com notícias)", "auc_medio_pregao": 0.5174,
         "acerto_top5": 0.5023, "ic_top5": [0.4836, 0.5204]},
        {"nome": "modelo_1", "rotulo": "Modelo 1 (sem notícias)", "auc_medio_pregao": 0.5145,
         "acerto_top5": 0.5088, "ic_top5": [0.4894, 0.5276]},
        {"nome": "logistica", "rotulo": "Regressão logística", "auc_medio_pregao": 0.5218,
         "acerto_top5": 0.5305, "ic_top5": [0.5117, 0.5488]},
        {"nome": "volatilidade", "rotulo": "Regra da volatilidade", "auc_medio_pregao": 0.5175,
         "acerto_top5": 0.5056, "ic_top5": [0.4847, 0.5268]},
    ]
    assert dev["veredito"] == "No top 5, o modelo 3 ficou acima do acaso, mas não superou a regra da volatilidade nem a logística."
    assert dev["calibracao"] == {"ece": 0.0157, "aprovada": True, "chance_exibida": False}
    assert dev["tem_relatorio"] is True

    assert resultado["registros"] == {"tops": 1, "resultados": 1, "ultimo_top": "2026-10-23"}


def test_experimento_modelo_oficial_continua_provisorio(tmp_path):
    raiz = montar_raiz(tmp_path)
    resultado = ler_experimento(raiz, _com(modelo_oficial=True))
    assert resultado["situacao_modelo"] == "provisório"
    assert resultado["top_publicado"] is True
    assert resultado["mostrar_aviso"] is True


def test_experimento_publicar_provisorio(tmp_path):
    raiz = montar_raiz(tmp_path)
    resultado = ler_experimento(raiz, _com(publicar_top_provisorio=True))
    assert resultado["top_publicado"] is True


def test_experimento_trava_teste_final(tmp_path):
    raiz = montar_raiz(tmp_path)

    definido = _com(teste_final={"inicio": "2026-06-23", "fim": "2026-11-30", "liberado": False})
    assert ler_experimento(raiz, definido)["trava_teste_final"]["estado"] == "definido_nao_liberado"

    liberado = _com(teste_final={"inicio": "2026-06-23", "fim": "2026-11-30", "liberado": True})
    trava = ler_experimento(raiz, liberado)["trava_teste_final"]
    assert trava["estado"] == "liberado"
    assert trava["inicio"] == "2026-06-23"
    assert trava["fim"] == "2026-11-30"
    assert trava["liberado"] is True

    (raiz / "docs" / "teste_final_usado.json").write_text("{}", encoding="utf-8")
    assert ler_experimento(raiz, liberado)["trava_teste_final"]["estado"] == "usado"


def test_trava_teste_final_direto(tmp_path):
    raiz = montar_raiz(tmp_path)
    trava = trava_teste_final(PARAMS, raiz)
    assert trava["estado"] == "ativa"
    assert trava["texto"] == "Trava ativa: treino.teste_final.fim vazio; o teste final não roda."
    assert set(trava) >= {"inicio", "fim", "liberado"}


def test_experimento_sem_modelos_e_sem_treino(tmp_path):
    raiz = montar_raiz(tmp_path)
    shutil.rmtree(raiz / "modelos")
    shutil.rmtree(raiz / "saida" / "experimento")

    resultado = ler_experimento(raiz, PARAMS)
    assert resultado["modelo_em_uso"] is None
    assert resultado["modelo_sombra"] is None
    assert resultado["desenvolvimento"]["disponivel"] is False
    assert resultado["n_meta"] == 0
    assert caminho_ultimo_relatorio(raiz) is None


def test_experimento_meta_quebrado_nao_levanta(tmp_path):
    raiz = montar_raiz(tmp_path)
    (raiz / "modelos" / "xgb-2026-06.meta.json").write_text("{não é json", encoding="utf-8")
    resultado = ler_experimento(raiz, PARAMS)
    assert resultado["modelo_em_uso"] is None
    assert resultado["situacao_modelo"] == "provisório"


def test_caminho_ultimo_relatorio(tmp_path):
    raiz = montar_raiz(tmp_path)
    assert caminho_ultimo_relatorio(raiz) == raiz / "saida/experimento/treino/dev-2026-10-23/relatorio.md"
    assert caminho_ultimo_relatorio(tmp_path / "sem_raiz") is None


# ---------------------------------------------------------------- último pytest

def test_ultimo_pytest_aprovado(tmp_path):
    raiz = montar_raiz(tmp_path)
    resultado = ler_ultimo_pytest(raiz / "logs" / "painel")
    assert resultado == {
        "disponivel": True,
        "arquivo": "testes-2026-10-24_101500.log",
        "inicio": "2026-10-24T10:15:00-03:00",
        "fim": "2026-10-24T10:16:36-03:00",
        "codigo": 0,
        "aprovado": True,
        "interrompido": False,
        "contagens": {"passed": 1700, "skipped": 43},
        "tempo": "95.21s",
        "falhas": [],
    }


def test_ultimo_pytest_com_falha(tmp_path):
    raiz = montar_raiz(tmp_path)
    (raiz / "logs" / "painel" / "testes-2026-10-24_101500.log").unlink()
    resultado = ler_ultimo_pytest(raiz / "logs" / "painel")
    assert resultado["arquivo"] == "testes-2026-10-23_090000.log"
    assert resultado["codigo"] == 1
    assert resultado["aprovado"] is False
    assert resultado["interrompido"] is False
    assert resultado["contagens"] == {"failed": 2, "passed": 1698, "skipped": 43}
    assert resultado["falhas"] == ["FAILED tests/test_x.py::test_y - assert 1 == 2"]


def test_ultimo_pytest_sem_rodape(tmp_path):
    pasta = tmp_path / "painel"
    pasta.mkdir()
    (pasta / "testes-2026-10-25_080000.log").write_text(
        "# painel: acao=testes inicio=2026-10-25T08:00:00-03:00 comando=python -m pytest -q\n"
        "........ [  4%]\n",
        encoding="utf-8",
    )
    resultado = ler_ultimo_pytest(pasta)
    assert resultado["codigo"] is None
    assert resultado["aprovado"] is None
    assert resultado["interrompido"] is True
    assert resultado["inicio"] == "2026-10-25T08:00:00-03:00"


def test_ultimo_pytest_pasta_vazia(tmp_path):
    (tmp_path / "vazia").mkdir()
    assert ler_ultimo_pytest(tmp_path / "vazia") == {
        "disponivel": False,
        "motivo": "nenhum pytest rodado pelo painel ainda",
    }


# ---------------------------------------------------------------- resultado_terminal

def test_resultado_terminal_sem_pregao():
    assert resultado_terminal("2026-10-24 não é pregão previsto (sábado): nada a gerar.") == ("sem_pregao", "sábado")


def test_resultado_terminal_trava():
    linha = "outra rotina em andamento desde 2026-10-23T08:00:00-03:00 (pid 999). Rodada cancelada; nada foi gravado."
    assert resultado_terminal(linha) == ("trava", linha)


def test_resultado_terminal_falhou():
    assert resultado_terminal("Saída não gerada: x") == ("falhou", "Saída não gerada: x")
    linha = "Coleta não terminou até 12:00: pacotes de hoje não gerados."
    assert resultado_terminal(linha) == ("falhou", linha)


def test_resultado_terminal_configuracao():
    assert resultado_terminal("Configuração do banco incompleta: x") == (
        "configuracao", "Configuração do banco incompleta: x",
    )
    assert resultado_terminal("Configuração inválida: y") == ("configuracao", "Configuração inválida: y")


def test_resultado_terminal_sem_banco():
    linha = "Falha ao conectar ao banco (OperationalError). Nada foi gravado."
    assert resultado_terminal(linha) == ("sem_banco", linha)
    linha = "x. Rodada interrompida; a coleta não foi alterada."
    assert resultado_terminal(linha) == ("sem_banco", linha)


def test_resultado_terminal_linhas_comuns_nao_terminam():
    assert resultado_terminal("Saída de D em P: status ok") is None
    assert resultado_terminal("- aviso") is None


def test_duracao_ultima_acao_e_duracoes_painel(tmp_path):
    raiz = montar_raiz(tmp_path)
    pasta = raiz / "logs" / "painel"
    # log mais novo da fixture: 10:15:00 a 10:16:36, código 0
    assert relatorios.duracao_ultima_acao(pasta, "testes") == 96
    # execução parada pelo painel (parado=sim) é ignorada
    (pasta / "testes-2026-10-25_080000.log").write_text(
        "# painel: acao=testes inicio=2026-10-25T08:00:00-03:00 comando=python -m pytest -q\n"
        "# painel: fim=2026-10-25T08:00:10-03:00 codigo=1 parado=sim\n",
        encoding="utf-8",
    )
    assert relatorios.duracao_ultima_acao(pasta, "testes") == 96
    # código de erro (3) é ignorado; vale a execução anterior com código 0
    (pasta / "diagnostico-2026-10-24_120000.log").write_text(
        "# painel: acao=diagnostico inicio=2026-10-24T12:00:00-03:00 comando=python -m processamento.diagnostico\n"
        "ok\n"
        "# painel: fim=2026-10-24T12:02:05-03:00 codigo=0\n",
        encoding="utf-8",
    )
    (pasta / "diagnostico-2026-10-25_090000.log").write_text(
        "# painel: acao=diagnostico inicio=2026-10-25T09:00:00-03:00 comando=python -m processamento.diagnostico\n"
        "# painel: fim=2026-10-25T09:00:03-03:00 codigo=3\n",
        encoding="utf-8",
    )
    assert relatorios.duracao_ultima_acao(pasta, "diagnostico") == 125
    # execução sem rodapé (em andamento) não conta
    (pasta / "carga-2026-10-25_100000.log").write_text(
        "# painel: acao=carga inicio=2026-10-25T10:00:00-03:00 comando=python -m processamento.saida --data 2026-10-23 --completo\n"
        "rodando\n",
        encoding="utf-8",
    )
    assert relatorios.duracao_ultima_acao(pasta, "carga") is None
    assert relatorios.duracao_ultima_acao(pasta, "rotina") is None
    assert relatorios.duracao_ultima_acao(tmp_path / "nao_existe", "testes") is None
    assert relatorios.duracoes_painel(pasta, ["rotina", "carga", "diagnostico", "testes"]) == {
        "rotina": None, "carga": None, "diagnostico": 125, "testes": 96,
    }
