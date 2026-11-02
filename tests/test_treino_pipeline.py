"""Testes de ponta a ponta do treino (plano da etapa 6, fase 6c): `executar` e `main` sobre dados sintéticos.

Os CSV vêm de tests/fabrica_treino.py e vão para tmp_path. Nada de banco ou rede (o teste 6 prova isso
derrubando o acesso). A trava do teste final fica em test_treino_trava.py.
"""

import json

import pandas as pd
import pytest

from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento import fontes
from processamento.experimento import dataset, modelos, treino
from processamento.experimento.preparacao import COLUNAS_RANK
from processamento.experimento.preparacao import VERSAO_PREPARACAO as preparacao_atual


@pytest.fixture(autouse=True)
def registro_isolado(tmp_path, monkeypatch):
    """Nenhum teste deste arquivo pode tocar o registro real do teste final (docs/)."""
    monkeypatch.setattr(treino, "REGISTRO_TESTE_FINAL", tmp_path / "docs" / "teste_final_usado.json")


@pytest.fixture
def ambiente(tmp_path):
    datasets = tmp_path / "datasets"
    gravar_versoes(datasets, dataset_sintetico())
    return {"datasets": datasets, "saida": tmp_path / "saida", "modelos": tmp_path / "modelos"}


def _rodar(amb, pasta_saida=None, pasta_modelos=None, datasets=None, params=None):
    return treino.executar(
        datasets or amb["datasets"],
        pasta_saida or amb["saida"],
        pasta_modelos or amb["modelos"],
        params=params or params_teste(),
    )


def _argv(amb, *extra):
    return [
        "--pasta-datasets", str(amb["datasets"]),
        "--pasta-saida", str(amb["saida"]),
        "--pasta-modelos", str(amb["modelos"]),
        *extra,
    ]


def _unica_pasta(pasta, prefixo):
    achadas = [p for p in pasta.iterdir() if p.name.startswith(prefixo)]
    assert len(achadas) == 1
    return achadas[0]


def _ler_metricas(pasta):
    return json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))


def _sem_campos_do_dataset(metricas):
    """Tira o que muda quando só o dataset muda (hash e nome de arquivo) e o horário de geração."""
    saida = {k: v for k, v in metricas.items() if k != "gerado_em"}
    saida["datasets"] = {
        nome: None if bloco is None else {k: v for k, v in bloco.items() if k not in ("sha256", "arquivo")}
        for nome, bloco in metricas["datasets"].items()
    }
    if metricas.get("modelo_salvo"):
        ms = dict(metricas["modelo_salvo"])
        for chave in ("metadados", "metadados_m1"):
            ms[chave] = {k: v for k, v in ms[chave].items() if k != "dataset"}
        saida["modelo_salvo"] = ms
    return saida


def _envenenar(df, mascara):
    """Cópia com as linhas marcadas estragadas: variáveis brutas e de notícias com sinal trocado,
    alvo invertido e ret_t1 = 99. Se o treino olhasse essas linhas, o resultado mudaria."""
    saida = df.copy()
    cols = list(dict.fromkeys([*COLUNAS_RANK, *dataset.COLUNAS_NOTICIAS]))
    saida.loc[mascara, cols] = saida.loc[mascara, cols] * -1
    saida.loc[mascara, "alvo"] = 1 - saida.loc[mascara, "alvo"]
    saida.loc[mascara, "ret_t1"] = 99.0
    return saida


def test_dev_grava_arquivos_e_modelos_provisorios(ambiente):
    caminho = _rodar(ambiente)
    pasta = _unica_pasta(ambiente["saida"], "dev-")
    assert caminho == pasta / "relatorio.md"
    for nome in ("relatorio.md", "metricas.json", "previsoes.csv", "diario.csv", "selecao.csv"):
        assert (pasta / nome).is_file()
    for nome in ("xgb-2026-01.json", "xgb-2026-01.meta.json", "xgb-m1-2026-01.json", "xgb-m1-2026-01.meta.json"):
        assert (ambiente["modelos"] / nome).is_file()

    primeira = next(linha for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip())
    assert "TESTE DE FUNCIONAMENTO" in primeira
    assert "Não constitui recomendação de investimento." in caminho.read_text(encoding="utf-8")

    metricas = _ler_metricas(pasta)
    assert metricas["modo"] == "desenvolvimento"
    assert metricas["aviso_funcionamento"] is True
    assert metricas["periodo"]["teste_final_fim"] is None
    assert metricas["periodo"]["teste_final_usado"] is False
    assert len(metricas["exemplo_top"]["top"]) == 5
    assert "NaN" not in (pasta / "metricas.json").read_text(encoding="utf-8")

    meta = json.loads((ambiente["modelos"] / "xgb-2026-01.meta.json").read_text(encoding="utf-8"))
    assert all(chave in meta for chave in modelos.CHAVES_METADADOS)
    assert meta["provisorio"] is True
    assert meta["aviso"] == "modelo provisório (treino.modelo_oficial: false): só teste de funcionamento"
    assert meta["versao_preparacao"] == preparacao_atual
    assert meta["teste_final"] == {"inicio": "2026-01-02", "fim": None, "usado": False}


def test_nada_do_teste_final_nas_saidas(ambiente):
    caminho = _rodar(ambiente)
    previsoes = pd.read_csv(caminho.parent / "previsoes.csv", parse_dates=["data"])
    diario = pd.read_csv(caminho.parent / "diario.csv", parse_dates=["data"])
    assert previsoes["data"].max() == pd.Timestamp("2025-12-31")
    assert diario["data"].max() < pd.Timestamp("2026-01-01")


def test_mesmas_linhas_entre_os_modelos(ambiente):
    caminho = _rodar(ambiente)
    previsoes = pd.read_csv(caminho.parent / "previsoes.csv", dtype={"ticker": str, "modelo": str})
    pares = {nome: set(zip(g["data"], g["ticker"])) for nome, g in previsoes.groupby("modelo")}
    assert {"modelo_1", "modelo_3", "logistica", "volatilidade"} <= set(pares)
    base = pares["modelo_1"]
    for nome in ("modelo_3", "logistica", "volatilidade", "modelo_3_principais", "modelo_3_hora_real_noite"):
        assert pares[nome] == base
    assert not previsoes.duplicated(["modelo", "data", "ticker"]).any()


def test_reprodutivel(tmp_path, ambiente):
    primeira = _rodar(ambiente, pasta_saida=tmp_path / "s1", pasta_modelos=tmp_path / "m1")
    segunda = _rodar(ambiente, pasta_saida=tmp_path / "s2", pasta_modelos=tmp_path / "m2")
    assert (primeira.parent / "previsoes.csv").read_bytes() == (segunda.parent / "previsoes.csv").read_bytes()
    assert (primeira.parent / "diario.csv").read_bytes() == (segunda.parent / "diario.csv").read_bytes()
    metricas_1 = _ler_metricas(primeira.parent)
    metricas_2 = _ler_metricas(segunda.parent)
    assert {k: v for k, v in metricas_1.items() if k != "gerado_em"} == {
        k: v for k, v in metricas_2.items() if k != "gerado_em"
    }


def test_veneno_no_teste_final_nao_muda_as_saidas(tmp_path, ambiente):
    original = _rodar(ambiente, pasta_saida=tmp_path / "s1", pasta_modelos=tmp_path / "m1")
    df = dataset_sintetico()
    envenenado = _envenenar(df, df["data"] >= pd.Timestamp("2026-01-01"))
    datasets = tmp_path / "envenenado"
    gravar_versoes(datasets, envenenado)
    estragado = _rodar(ambiente, pasta_saida=tmp_path / "s2", pasta_modelos=tmp_path / "m2", datasets=datasets)

    assert (original.parent / "previsoes.csv").read_bytes() == (estragado.parent / "previsoes.csv").read_bytes()
    assert _sem_campos_do_dataset(_ler_metricas(original.parent)) == _sem_campos_do_dataset(
        _ler_metricas(estragado.parent)
    )


def test_sem_banco(ambiente, monkeypatch):
    def proibido(*args, **kwargs):
        raise AssertionError("o treino não pode acessar o banco")

    monkeypatch.setattr(fontes, "criar_engine", proibido)
    monkeypatch.setattr(fontes, "executar_leitura", proibido)
    assert treino.main(_argv(ambiente), params=params_teste()) == 0


def test_extras_ausentes_viram_null_e_nao_encontrado(tmp_path):
    datasets = tmp_path / "datasets"
    gravar_versoes(datasets, dataset_sintetico(), versoes=("todas",))
    amb = {"datasets": datasets, "saida": tmp_path / "saida", "modelos": tmp_path / "modelos"}
    caminho = _rodar(amb)
    metricas = _ler_metricas(caminho.parent)
    assert metricas["datasets"]["principais"] is None
    assert metricas["datasets"]["hora_real_noite"] is None
    assert metricas["modelos"]["modelo_3_principais"] is None
    assert metricas["modelos"]["modelo_3_hora_real_noite"] is None
    assert all("principais" not in c["a"] and "hora_real_noite" not in c["a"] for c in metricas["comparacoes"])
    assert "principais: não encontrado" in caminho.read_text(encoding="utf-8")


def test_csv_sem_coluna_nova_devolve_2_e_manda_regenerar(ambiente, capsys):
    sem_coluna = dataset_sintetico().drop(columns=["alvo_abertura_valido"])
    gravar_versoes(ambiente["datasets"], sem_coluna)
    assert treino.main(_argv(ambiente), params=params_teste()) == 2
    assert "regenere" in capsys.readouterr().out


def test_sha_alterado_devolve_2(ambiente, capsys):
    gravados = gravar_versoes(ambiente["datasets"], dataset_sintetico())
    with open(gravados["todas"], "a", encoding="utf-8") as arquivo:
        arquivo.write("\n")
    assert treino.main(_argv(ambiente), params=params_teste()) == 2
    assert "sha256" in capsys.readouterr().out
