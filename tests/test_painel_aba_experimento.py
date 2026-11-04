"""Testes de processamento/painel/aba_experimento.py: operação do modelo, sem métrica de desempenho.

A raiz de cada teste é montada em tmp_path; o registro do protocolo, a sensibilidade e o protocolo_variaveis.md
são copiados do repositório (só leitura). Nenhum teste usa banco ou rede.
"""

import json
import shutil
from pathlib import Path

from processamento.experimento import preparacao
from processamento.painel import aba_experimento as ae
from processamento.painel.aba_experimento import (
    aviso,
    checklist,
    dataset_info,
    modelo_producao,
    operacao,
    rodadas,
)

REPO = Path(__file__).resolve().parents[1]
HOJE = "2026-11-04"
PARAMETROS_PADRAO = 'experimento:\n  periodos_sem_coleta:\n    - {inicio: "2025-01-01", fim: "2025-07-31"}\n'
DATASET_6 = {"versao_preparacao": 6, "gerado_em": "2026-11-02T13:40:30-03:00",
             "sha256": "741e781122d073e0f8fdab363998e34e39fa4f811d19c00a04412dedf548c980",
             "linhas": 116682, "pregoes": 1703}

EXPERIMENTO = {
    "situacao_modelo": "provisório",
    "top_publicado": False,
    "n_meta": 4,
    "registros": {"tops": 3, "resultados": 2, "ultimo_top": "2026-11-03"},
    "trava_teste_final": {"estado": "ativa", "texto": "Trava ativa", "inicio": "2026-06-23", "fim": None, "liberado": False},
    "modelo_em_uso": {
        "arquivo": "logistica-2026-06.meta.json", "mes": "2026-06", "familia": "logistica", "modelo": "3",
        "versao_preparacao": 6, "versao_noticias": "todas", "provisorio": True,
        "periodo_treino": {"inicio": "2021-01-04", "fim": "2026-06-19"}, "n_linhas_treino": 92260,
        "gerado_em": "2026-11-02T23:33:27-03:00",
        "dataset": {"arquivo": "dataset-todas-2026-10-30.csv", "sha256": "741e781122d0"}, "aviso": "x",
    },
}
PARAMS = {"teste_final": {"inicio": "2026-06-23", "fim": None, "liberado": False}, "familia_producao": "logistica"}

TEXTOS_CHECKLIST = [
    "Histórico desde 2021, com as lacunas como limitação",
    "Data de fim do teste final (a definir)",
    "Hipótese e medida principal: ganho de AUC por pregão do modelo 3 sobre o 1, com IC 95% acima de 0",
    "Família, colunas e referências congeladas",
    "Dados novos antes do teste final geram nova rodada",
    "Dataset congelado com hash registrado",
    "Conferência de preços reescritos (tolerância 1e-6)",
    "Custos definidos antes",
    "Auditoria de eventos após 23/06",
    "Chance oculta até o teste ao vivo",
]


def _montar(tmp_path, *, jsonl="real", md="real", dataset=True, parametros=PARAMETROS_PADRAO):
    """Raiz de teste. `jsonl`/`md`: "real" copia do repositório, None não cria, texto grava esse texto."""
    raiz = tmp_path / "raiz"
    (raiz / "docs").mkdir(parents=True)
    for nome, fonte in (("protocolo_tentativas.jsonl", jsonl), ("protocolo_variaveis.md", md)):
        if fonte == "real":
            shutil.copy(REPO / "docs" / nome, raiz / "docs" / nome)
        elif fonte is not None:
            (raiz / "docs" / nome).write_text(fonte, encoding="utf-8")
    shutil.copy(REPO / "docs" / "busca_rodada_001_sensibilidade.json", raiz / "docs" / "busca_rodada_001_sensibilidade.json")
    if dataset:
        pasta = raiz / "saida" / "experimento"
        pasta.mkdir(parents=True)
        (pasta / "dataset-todas-2026-10-30.json").write_text(json.dumps(DATASET_6), encoding="utf-8")
    if parametros is not None:
        (raiz / "processamento" / "config").mkdir(parents=True)
        (raiz / "processamento" / "config" / "parametros.yaml").write_text(parametros, encoding="utf-8")
    return raiz


def _op(raiz, experimento=EXPERIMENTO, params=PARAMS, hoje=HOJE):
    return operacao(raiz, params, experimento, hoje, None)


def _chaves(obj):
    if isinstance(obj, dict):
        for chave, valor in obj.items():
            yield str(chave)
            yield from _chaves(valor)
    elif isinstance(obj, list):
        for item in obj:
            yield from _chaves(item)


# ---------------------------------------------------------------- operação completa

def test_operacao_contrato_com_versao_7(tmp_path, monkeypatch):
    monkeypatch.setattr(preparacao, "VERSAO_PREPARACAO", 7)
    r = _op(_montar(tmp_path))
    assert r["situacao"] == "provisório"
    assert r["aviso"] == {"nivel": "warn", "texto": (
        "Top 5 interno pausado: o modelo em produção é da versão de preparação 6 e o código está na 7. "
        "Volta quando o modelo for treinado com um dataset da versão 7.")}
    assert r["modelo"] == {
        "disponivel": True, "familia": "logistica", "familia_texto": "Regressão logística",
        "arquivo": "logistica-2026-06.meta.json", "treinado_em": "2026-11-02", "treinado_em_texto": "02/11/2026",
        "versao_preparacao": 6, "situacao": "provisório", "oficial_texto": "não (provisório)",
        "configuracao": "busca rodada 001 (reproduzida na 002)", "periodo_texto": "04/01/2021 a 19/06/2026",
        "linhas_treino": 92260, "top_publicado": False, "top_texto": "retido (não enviado à interface)",
        "registros_texto": "3 tops · 2 resultados",
    }
    assert r["dataset"] == {
        "versao_codigo": 7, "versao_modelo": 6, "titulo": "Versão 7 pendente", "estado": "warn",
        "ultimo": {"arquivo": "dataset-todas-2026-10-30.json", "data": "2026-10-30", "versao_preparacao": 6,
                   "gerado_em_texto": "02/11/2026", "sha256_curto": "741e781122d0", "linhas": 116682, "pregoes": 1703},
        "ultimo_texto": "v6 · 02/11/2026", "sem_coleta": ["01/01/2025 a 31/07/2025"],
        "sem_coleta_texto": "01/01/2025 a 31/07/2025",
    }
    assert r["teste_final"] == {
        "estado": "ativa", "titulo": "Travado", "texto": "Trava ativa", "inicio": "2026-06-23",
        "inicio_texto": "23/06/2026", "fim": None, "fim_texto": "a definir (D2)", "pregoes": 93,
        "uso_texto": "nenhum (uso único)",
    }


def test_rodadas_itens_na_ordem_do_registro(tmp_path, monkeypatch):
    monkeypatch.setattr(preparacao, "VERSAO_PREPARACAO", 7)
    r = _op(_montar(tmp_path))["rodadas"]
    assert r["disponivel"] is True and r["motivo"] is None and r["integridade"] == "ok"
    assert [(i["nome"], i["status_texto"], i["estado"], i["detalhe"]) for i in r["itens"]] == [
        ("Protocolo · rodada 001", "válida", "ok", "02/11/2026 · adotados: bloco_a · protocolo_rodada_001.md"),
        ("Busca · rodada 001", "concluída", "ok", "02/11/2026 · vencedor: logistica · busca_rodada_001.md"),
        ("Busca · rodada 002", "reproduziu", "ok", "02/11/2026 · repetição da rodada 001, mesmo resultado · busca_rodada_002.md"),
        ("Protocolo · rodada 002", "reproduziu", "ok", "02/11/2026 · repetição da rodada 001, mesmo resultado · protocolo_rodada_002.md"),
        ("Sensibilidade (exploratória) · rodada 001", "registrada", "info",
         "dados de 30/10/2026 · 4 análises · fora da contagem do protocolo"),
        ("Próxima rodada (dados novos)", "aguardando", "warn",
         "O código está na versão de preparação 7 e as rodadas registradas usaram a 6. Pela D5, dados novos "
         "antes do teste final geram nova rodada, que passa a ser a oficial."),
    ]


def test_versao_6_sem_proxima_rodada_nem_aviso(tmp_path, monkeypatch):
    monkeypatch.setattr(preparacao, "VERSAO_PREPARACAO", 6)
    r = _op(_montar(tmp_path))
    assert r["aviso"] is None
    assert all(i["nome"] != "Próxima rodada (dados novos)" for i in r["rodadas"]["itens"])
    assert r["dataset"]["titulo"] == "Versão 6 em uso"
    assert r["dataset"]["estado"] == "ok"


def test_jsonl_adulterado_vira_registro_quebrado(tmp_path):
    real = (REPO / "docs" / "protocolo_tentativas.jsonl").read_text(encoding="utf-8")
    raiz = _montar(tmp_path, jsonl=real.replace("bloco_a", "bloco_b", 1))
    r = rodadas(raiz)
    assert r["disponivel"] is False
    assert r["integridade"] == "quebrada"
    assert r["motivo"].startswith("Registro do protocolo com problema: protocolo_tentativas.jsonl: cadeia quebrada na linha 3")
    assert r["itens"] == []


def test_sem_jsonl_mostra_so_a_sensibilidade(tmp_path, monkeypatch):
    monkeypatch.setattr(preparacao, "VERSAO_PREPARACAO", 7)
    r = _op(_montar(tmp_path, jsonl=None))
    assert r["rodadas"]["motivo"] == "Nenhuma rodada registrada (docs/protocolo_tentativas.jsonl ausente)."
    assert r["rodadas"]["integridade"] is None
    assert [i["nome"] for i in r["rodadas"]["itens"]] == ["Sensibilidade (exploratória) · rodada 001"]
    assert r["modelo"]["configuracao"] is None


# ---------------------------------------------------------------- checklist

def test_checklist_com_o_protocolo_real():
    r = checklist(REPO, PARAMS)
    assert r["disponivel"] is True and r["motivo"] is None
    assert r["n_fechadas"] == 7 and r["n_total"] == 10
    assert [i["id"] for i in r["itens"]] == [f"D{n}" for n in range(1, 11)]
    assert [i["situacao"] for i in r["itens"]] == [
        "fechada", "pendente", "fechada", "fechada", "fechada", "pendente", "fechada", "fechada", "pendente", "fechada"]
    assert [i["texto"] for i in r["itens"]] == TEXTOS_CHECKLIST


def test_checklist_com_fim_do_teste_final_fecha_d2(tmp_path):
    raiz = _montar(tmp_path)
    r = checklist(raiz, {"teste_final": {"fim": "2027-03-31"}})
    d2 = r["itens"][1]
    assert d2 == {"id": "D2", "texto": "Data de fim do teste final: 31/03/2027", "situacao": "fechada",
                  "cumprida": True, "automatica": True}
    assert r["n_fechadas"] == 8


def test_checklist_sem_d10_marca_faltando(tmp_path):
    md = (REPO / "docs" / "protocolo_variaveis.md").read_text(encoding="utf-8")
    sem_d10 = "\n".join(l for l in md.splitlines() if not l.startswith("| D10 |"))
    r = checklist(_montar(tmp_path, md=sem_d10), PARAMS)
    assert r["disponivel"] is True
    assert r["motivo"] == "Faltam no protocolo: D10"
    d10 = r["itens"][9]
    assert d10["id"] == "D10" and d10["cumprida"] is None and d10["texto"] is None


def test_checklist_sem_tabela_ou_sem_arquivo(tmp_path):
    md = (REPO / "docs" / "protocolo_variaveis.md").read_text(encoding="utf-8")
    sem_tabela = md.replace("### Checklist antes do teste final (D1 a D10)", "### Outra coisa")
    r = checklist(_montar(tmp_path / "a", md=sem_tabela), PARAMS)
    assert r["disponivel"] is False
    assert "não está em docs/protocolo_variaveis.md" in r["motivo"]
    r2 = checklist(_montar(tmp_path / "b", md=None), PARAMS)
    assert r2["disponivel"] is False
    assert r2["motivo"] == "docs/protocolo_variaveis.md não encontrado"


# ---------------------------------------------------------------- teste final

def test_teste_final_conta_pregoes_ate_o_fim_e_marca_uso():
    trava = {"estado": "ativa", "texto": "x", "inicio": "2026-06-23", "fim": "2026-06-30", "liberado": False}
    assert ae.teste_final_info(trava, HOJE, None)["pregoes"] == 6
    assert ae.teste_final_info({**trava, "inicio": None}, HOJE, None)["pregoes"] is None
    usado = ae.teste_final_info({"estado": "usado", "texto": "x", "inicio": None, "fim": None}, HOJE, None)
    assert usado["titulo"] == "Já usado"
    assert usado["uso_texto"] == "já usado (uso único)"


# ---------------------------------------------------------------- modelo, dataset, aviso

def test_modelo_em_uso_none_gera_aviso(tmp_path):
    r = _op(_montar(tmp_path), experimento={**EXPERIMENTO, "modelo_em_uso": None})
    assert r["modelo"]["disponivel"] is False
    assert r["modelo"]["familia"] == "logistica"
    assert r["aviso"] == {"nivel": "warn", "texto": "Nenhum modelo da família logistica em modelos/: o top 5 interno não é gerado."}


def test_dataset_sem_arquivo_fica_idle(tmp_path):
    r = dataset_info(_montar(tmp_path, dataset=False), 6, "todas")
    assert r["titulo"] == "sem dados"
    assert r["estado"] == "idle"
    assert r["ultimo"] is None


def test_parametros_sem_chave_experimento_vira_sem_dados(tmp_path):
    r = dataset_info(_montar(tmp_path, parametros="outra: 1\n"), 6, "todas")
    assert r["sem_coleta"] is None
    assert r["sem_coleta_texto"] == "sem dados"


def test_sem_coleta_lista_vazia_vira_nenhum(tmp_path):
    r = dataset_info(_montar(tmp_path, parametros="experimento:\n  periodos_sem_coleta: []\n"), 6, "todas")
    assert r["sem_coleta"] == []
    assert r["sem_coleta_texto"] == "nenhum"


def test_modelo_producao_sem_eventos_mantem_familia_do_params():
    m = modelo_producao(PARAMS, {"modelo_em_uso": None, "top_publicado": True,
                                 "registros": {"tops": 1, "resultados": 0}}, None)
    assert m["disponivel"] is False
    assert m["top_texto"] == "publicado na interface"
    assert m["registros_texto"] == "1 top · 0 resultados"
    assert m["configuracao"] is None


def test_aviso_sem_modelo_nem_defasagem_fica_none():
    assert aviso("xgb", {"disponivel": True, "versao_preparacao": 7}, 7) is None


# ---------------------------------------------------------------- tolerância e regras de apresentação

def test_nenhuma_chave_traz_metrica_de_desempenho(tmp_path, monkeypatch):
    monkeypatch.setattr(preparacao, "VERSAO_PREPARACAO", 7)
    r = _op(_montar(tmp_path))
    proibidas = ["acerto", "auc", "ic_", "acaso", "veredito", "chance"]
    for chave in _chaves(r):
        assert not any(p in chave.lower() for p in proibidas), chave


def test_experimento_de_erro_nao_levanta(tmp_path):
    r = _op(_montar(tmp_path), experimento={"erro": "falha"})
    assert r["situacao"] is None
    assert r["modelo"]["disponivel"] is False
    assert r["teste_final"]["pregoes"] is None
    assert r["checklist"]["disponivel"] is True
