"""Testes da execução da busca (processamento/experimento/busca_execucao.py): travas, pré-requisitos do congelado,
determinismo, veneno no teste final e uma rodada ponta a ponta pequena. Dados sintéticos em tmp_path; nada de
banco ou rede; o registro do teste final é sempre um arquivo inexistente dentro de tmp_path.

Os testes de rodada completa treinam de verdade (poucas árvores, grade pequena), por isso usam fixtures de módulo.
"""

import json
import shutil
from dataclasses import replace

import pandas as pd
import pytest

from fabrica_protocolo import doc_de_teste
from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento.experimento import busca, busca_execucao, dataset, modelos, treino
from processamento.experimento import protocolo_registro as reg
from processamento.experimento.preparacao import BLOCOS_PROTOCOLO, COLUNAS_PROTOCOLO, COLUNAS_RANK, colunas_do_modelo

PARAMS = params_teste(grade={"max_depth": (2, 3)})
LIM = replace(busca.LIMITES_BUSCA, anos=(2025,), anos_positivos_minimos=1, reamostragens=50)
CANDIDATOS_PEQUENOS = ["logistica", "xgb_2_50", "lgbm_2_50", "lgbm_3_50", "combinacao"]


def _ambiente(pasta):
    """Dataset sintético (só 'todas'), documento do protocolo e pastas, tudo dentro de `pasta`."""
    datasets = pasta / "datasets"
    gravados = gravar_versoes(datasets, dataset_sintetico(), versoes=("todas",))
    _, info = treino.ler_desenvolvimento(gravados["todas"], PARAMS)
    doc_de_teste(pasta / "docs")
    return {
        "datasets": datasets,
        "docs": pasta / "docs",
        "registro_teste_final": pasta / "docs" / "teste_final_usado.json",
        "data": treino._data_do_arquivo(gravados["todas"]),
        "sha": info["sha256"],
    }


def _gravar_congelado(amb, caminho, **trocas):
    """Configuração congelada no formato do protocolo (bloco A nas duas colunas), para o sha de `amb`."""
    congelado = {
        "colunas_1": colunas_do_modelo("1", ("preco_contexto",)) + BLOCOS_PROTOCOLO["bloco_a"],
        "colunas_3": colunas_do_modelo("3", ("preco_contexto", "noticias_contexto")) + BLOCOS_PROTOCOLO["bloco_a"],
        "colunas_3e": None,
        "hiperparametros": dict(PARAMS.xgboost),
        "extremo_em_rank": False,
        "blocos_preco": ["preco_contexto"],
        "noticias_contexto": True,
        "sha256_dataset": amb["sha"],
        "rodada": 1,
    }
    congelado.update(trocas)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(congelado, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def _registrar_protocolo(amb, status="valida", rodada=1, sha=None, docs=None):
    """Registro do protocolo com a rodada informada (inicio e fim), em `docs` (padrão: a pasta de `amb`)."""
    caminho = (docs or amb["docs"]) / "protocolo_tentativas.jsonl"
    assinatura = {"sha256_dataset": sha or amb["sha"]}
    reg.acrescentar(caminho, {"tipo": "protocolo", "evento": "inicio", "rodada": rodada, "motivo": "",
                              "em": "2026-11-02T10:00:00", "assinatura": assinatura})
    reg.acrescentar(caminho, {"tipo": "protocolo", "evento": "fim", "rodada": rodada, "em": "2026-11-02T10:05:00",
                              "assinatura": assinatura, "status": status, "motivos": [], "adotados": [],
                              "bloco_e_aprovado": False, "aprovados": [], "n_testes": 6,
                              "relatorio": f"protocolo_rodada_{rodada:03d}.md", "sha_resultado": "0" * 64,
                              "repete_rodada": None, "reproduziu": None})
    return caminho


def _argv(amb, congelado, motivo="", docs=None, datasets=None):
    argv = ["--data", amb["data"].isoformat(), "--pasta-datasets", str(datasets or amb["datasets"]),
            "--pasta-docs", str(docs or amb["docs"]), "--motivo", motivo]
    if congelado is not None:
        argv += ["--congelado", str(congelado)]
    return argv


def _rodar(amb, congelado, motivo="", docs=None, datasets=None):
    return busca_execucao.main(
        _argv(amb, congelado, motivo, docs, datasets), params=PARAMS, lim=LIM,
        registro_teste_final=amb["registro_teste_final"],
    )


def _envenenar(df, mascara):
    """Cópia com as linhas marcadas estragadas (inclui as colunas do protocolo): sinal trocado, alvo invertido, ret_t1 = 99."""
    saida = df.copy()
    cols = list(dict.fromkeys([*COLUNAS_RANK, *dataset.COLUNAS_NOTICIAS, *COLUNAS_PROTOCOLO]))
    saida.loc[mascara, cols] = saida.loc[mascara, cols] * -1
    saida.loc[mascara, "alvo"] = 1 - saida.loc[mascara, "alvo"]
    saida.loc[mascara, "ret_t1"] = 99.0
    return saida


# --- Travas e pré-requisitos (sem treinar) ----------------------------------------------------------


def test_sem_congelado_devolve_2(tmp_path, capsys):
    amb = _ambiente(tmp_path)
    assert _rodar(amb, None) == 2
    assert "--congelado" in capsys.readouterr().out
    assert not amb["docs"].exists() or not list(amb["docs"].glob("busca_rodada_*"))


def test_congelado_de_rodada_invalida_devolve_2(tmp_path, capsys):
    amb = _ambiente(tmp_path)
    _registrar_protocolo(amb, status="invalida")
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json")
    assert _rodar(amb, congelado) == 2
    assert "inválida" in capsys.readouterr().out
    assert not list(amb["docs"].glob("busca_rodada_*"))


def test_rodada_do_congelado_sem_registro_devolve_2(tmp_path, capsys):
    amb = _ambiente(tmp_path)
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json")
    assert _rodar(amb, congelado) == 2
    assert "não tem fim" in capsys.readouterr().out


def test_sha_do_congelado_diferente_devolve_2(tmp_path, capsys):
    amb = _ambiente(tmp_path)
    _registrar_protocolo(amb)
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json", sha256_dataset="0" * 64)
    assert _rodar(amb, congelado) == 2
    assert "sha256" in capsys.readouterr().out
    assert not list(amb["docs"].glob("busca_rodada_*"))


def test_teste_final_usado_devolve_4_e_nada_e_gravado(tmp_path):
    amb = _ambiente(tmp_path)
    _registrar_protocolo(amb)
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json")
    amb["registro_teste_final"].parent.mkdir(parents=True, exist_ok=True)
    amb["registro_teste_final"].write_text("{}", encoding="utf-8")
    assert _rodar(amb, congelado) == 4
    assert not list(amb["docs"].glob("busca_rodada_*"))
    assert len(reg.ler(amb["docs"] / "protocolo_tentativas.jsonl")) == 2


def test_segunda_rodada_exige_motivo(tmp_path, capsys):
    amb = _ambiente(tmp_path)
    _registrar_protocolo(amb)
    reg.acrescentar(amb["docs"] / "protocolo_tentativas.jsonl",
                    {"tipo": "busca", "evento": "inicio", "rodada": 1, "motivo": "", "em": "x",
                     "assinatura": {"sha256_dataset": amb["sha"]}})
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json")
    assert _rodar(amb, congelado, motivo="") == 2
    assert "motivo" in capsys.readouterr().out


def test_nunca_sobrescreve_o_relatorio(tmp_path):
    amb = _ambiente(tmp_path)
    _registrar_protocolo(amb)
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json")
    amb["docs"].mkdir(parents=True, exist_ok=True)
    (amb["docs"] / "busca_rodada_001.md").write_text("original", encoding="utf-8")
    assert _rodar(amb, congelado) == 2
    assert (amb["docs"] / "busca_rodada_001.md").read_text(encoding="utf-8") == "original"


# --- Rodadas completas (treinam de verdade, poucas árvores) ------------------------------------------


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """Duas rodadas da busca no mesmo registro: a 1ª (sem motivo) e a 2ª (com motivo)."""
    amb = _ambiente(tmp_path_factory.mktemp("busca_base"))
    _registrar_protocolo(amb)
    congelado = _gravar_congelado(amb, tmp_path_factory.mktemp("congelado") / "congelado.json")
    primeira = _rodar(amb, congelado, motivo="")
    segunda = _rodar(amb, congelado, motivo="2ª rodada")
    return {"amb": amb, "congelado": congelado, "codigo1": primeira, "codigo2": segunda}


def test_rodada_completa_grava_relatorio_json_e_configuracao(base):
    amb = base["amb"]
    docs = amb["docs"]
    assert base["codigo1"] == 0
    for nome in ("busca_rodada_001.md", "busca_rodada_001.json", "configuracao_final_rodada_001.json"):
        assert (docs / nome).is_file(), nome

    relatorio = (docs / "busca_rodada_001.md").read_text(encoding="utf-8")
    assert "Não constitui recomendação de investimento." in relatorio
    for nome in CANDIDATOS_PEQUENOS:
        assert nome in relatorio, nome
    assert "Vencedor" in relatorio

    configuracao = json.loads((docs / "configuracao_final_rodada_001.json").read_text(encoding="utf-8"))
    congelado = json.loads(base["congelado"].read_text(encoding="utf-8"))
    assert configuracao["familia"] in ("logistica", "xgb", "lgbm")
    assert configuracao["colunas_3"] == congelado["colunas_3"]
    assert configuracao["colunas_1"] == congelado["colunas_1"]
    assert configuracao["sha256_dataset"] == amb["sha"]
    assert configuracao["rodadas_de_origem"] == {"protocolo": 1, "busca": 1}
    assert configuracao["extremo_em_rank"] is False
    assert "NaN" not in (docs / "busca_rodada_001.json").read_text(encoding="utf-8")


def test_configuracao_final_serve_ao_treino_de_desenvolvimento_quando_xgb(base):
    """Com a família XGBoost, o `--configuracao` do treino aceita o arquivo (a busca não grava em modelos/)."""
    amb = base["amb"]
    configuracao = json.loads((amb["docs"] / "configuracao_final_rodada_001.json").read_text(encoding="utf-8"))
    if configuracao["familia"] != "xgb":
        pytest.skip("o vencedor não é XGBoost: a leitura pelo treino ainda não existe (fase C2)")
    cfg = treino._ler_configuracao(amb["docs"] / "configuracao_final_rodada_001.json", amb["sha"], params_teste())
    assert cfg["colunas_3"] == configuracao["colunas_3"]


def test_segunda_rodada_repete_e_reproduz(base):
    assert base["codigo2"] == 0
    registro = reg.ler(base["amb"]["docs"] / "protocolo_tentativas.jsonl")
    fins = [e for e in registro if e.get("tipo") == "busca" and e.get("evento") == "fim"]
    assert [e["rodada"] for e in fins] == [1, 2]
    assert fins[1]["repete_rodada"] == 1
    assert fins[1]["reproduziu"] is True
    relatorio = (base["amb"]["docs"] / "busca_rodada_002.md").read_text(encoding="utf-8")
    assert "Todas as tentativas" in relatorio and "| 1 |" in relatorio


def test_determinismo_em_outra_pasta(base, tmp_path):
    amb = base["amb"]
    docs = tmp_path / "docs"
    doc_de_teste(docs)
    _registrar_protocolo(amb, docs=docs)
    assert _rodar(amb, base["congelado"], motivo="", docs=docs) == 0
    fim_base = next(e for e in reg.ler(amb["docs"] / "protocolo_tentativas.jsonl")
                    if e.get("tipo") == "busca" and e.get("evento") == "fim" and e["rodada"] == 1)
    fim_novo = next(e for e in reg.ler(docs / "protocolo_tentativas.jsonl")
                    if e.get("tipo") == "busca" and e.get("evento") == "fim" and e["rodada"] == 1)
    assert fim_novo["sha_resultado"] == fim_base["sha_resultado"]
    assert (docs / "configuracao_final_rodada_001.json").read_bytes() == \
        (amb["docs"] / "configuracao_final_rodada_001.json").read_bytes()


def test_mudar_a_secao_6_depois_da_1a_busca_invalida_a_rodada(base, tmp_path, capsys):
    amb = base["amb"]
    docs = tmp_path / "docs"
    shutil.copytree(amb["docs"], docs)
    doc = docs / "protocolo_variaveis.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace("texto da seção 6", "regra alterada"), encoding="utf-8")
    assert _rodar(amb, base["congelado"], motivo="regra alterada", docs=docs) == 2
    assert "Rodada inválida" in capsys.readouterr().out
    assert "Rodada inválida" in (docs / "busca_rodada_003.md").read_text(encoding="utf-8")
    assert not (docs / "configuracao_final_rodada_003.json").exists()
    fim = [e for e in reg.ler(docs / "protocolo_tentativas.jsonl") if e.get("tipo") == "busca" and e.get("evento") == "fim"][-1]
    assert (fim["rodada"], fim["status"]) == (3, "invalida")


def test_sha_das_regras_da_busca_so_olha_a_secao_6_e_os_limites(tmp_path):
    doc = doc_de_teste(tmp_path)
    original = doc.read_text(encoding="utf-8")
    sha = busca_execucao._sha_regras_busca(doc, LIM)
    doc.write_text(original + "## 7. Executor\ntexto novo\n", encoding="utf-8")
    assert busca_execucao._sha_regras_busca(doc, LIM) == sha
    assert busca_execucao._sha_regras_busca(doc, replace(LIM, reamostragens=51)) != sha
    doc.write_text(original.replace("texto da seção 6", "outra regra"), encoding="utf-8")
    assert busca_execucao._sha_regras_busca(doc, LIM) != sha
    doc.write_text("## 3. Só isto\n", encoding="utf-8")
    with pytest.raises(busca_execucao.ErroProtocolo):
        busca_execucao._sha_regras_busca(doc, LIM)


def test_veneno_no_teste_final_nao_muda_o_resultado(base, tmp_path):
    amb = base["amb"]
    df = dataset_sintetico()
    envenenado_pasta = tmp_path / "envenenado"
    gravados = gravar_versoes(envenenado_pasta, _envenenar(df, df["data"] >= pd.Timestamp("2026-01-01")),
                              versoes=("todas",))
    _, info = treino.ler_desenvolvimento(gravados["todas"], PARAMS)
    docs = tmp_path / "docs"
    doc_de_teste(docs)
    _registrar_protocolo(amb, docs=docs, sha=info["sha256"])
    congelado = _gravar_congelado({**amb, "sha": info["sha256"]}, tmp_path / "congelado.json")
    assert _rodar(amb, congelado, motivo="", docs=docs, datasets=envenenado_pasta) == 0
    fim_base = next(e for e in reg.ler(amb["docs"] / "protocolo_tentativas.jsonl")
                    if e.get("tipo") == "busca" and e.get("evento") == "fim" and e["rodada"] == 1)
    fim_novo = next(e for e in reg.ler(docs / "protocolo_tentativas.jsonl")
                    if e.get("tipo") == "busca" and e.get("evento") == "fim" and e["rodada"] == 1)
    assert fim_novo["sha_resultado"] == fim_base["sha_resultado"]


def test_nao_grava_em_modelos_nem_usa_o_teste_final(tmp_path, monkeypatch):
    amb = _ambiente(tmp_path)
    _registrar_protocolo(amb)
    congelado = _gravar_congelado(amb, tmp_path / "congelado.json")

    def proibido(*args, **kwargs):
        raise AssertionError("a busca não pode salvar modelo, ler o teste final nem chamar o treino completo")

    monkeypatch.setattr(modelos, "salvar_modelo", proibido)
    monkeypatch.setattr(treino, "ler_teste_final", proibido)
    monkeypatch.setattr(treino, "executar", proibido)
    assert _rodar(amb, congelado) == 0
    assert not (tmp_path / "modelos").exists()
