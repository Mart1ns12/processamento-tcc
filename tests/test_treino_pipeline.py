"""Testes de ponta a ponta do treino (plano da etapa 6, fase 6c): `executar` e `main` sobre dados sintéticos.

Os CSV vêm de tests/fabrica_treino.py e vão para tmp_path. Nada de banco ou rede (o teste 6 prova isso
derrubando o acesso). A trava do teste final fica em test_treino_trava.py.
"""

import hashlib
import json

import pandas as pd
import pytest

from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento import fontes
from processamento.experimento import dataset, modelos, treino
from processamento.experimento.preparacao import BLOCOS_PROTOCOLO, COLUNAS_PROTOCOLO, COLUNAS_RANK, colunas_do_modelo
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
    assert not set(meta["colunas"]) & set(COLUNAS_PROTOCOLO)
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


# --- Fase 2.4: --configuracao (a configuração congelada vai ao treino de desenvolvimento) ------------


def _gravar_congelado(amb, caminho, **trocas):
    """JSON de configuração congelada no formato do protocolo, com o sha256 do CSV 'todas' de `amb`.

    Blocos de preço e de notícias, mais o bloco A nas duas colunas; hiperparâmetros fora da grade de teste.
    `trocas` sobrescreve campos (sha256_dataset, familia...).
    """
    csv = treino.localizar_datasets(amb["datasets"], None)["todas"]
    _, info = treino.ler_desenvolvimento(csv, params_teste())
    congelado = {
        "blocos_preco": ["preco_contexto"],
        "noticias_contexto": True,
        "colunas_1": colunas_do_modelo("1", ("preco_contexto",)) + BLOCOS_PROTOCOLO["bloco_a"],
        "colunas_3": colunas_do_modelo("3", ("preco_contexto", "noticias_contexto")) + BLOCOS_PROTOCOLO["bloco_a"],
        "colunas_3e": None,
        "hiperparametros": {**params_teste().xgboost, "max_depth": 3, "min_child_weight": 200},
        "extremo_em_rank": False,
        "sha256_dataset": info["sha256"],
        "rodada": 1,
    }
    congelado.update(trocas)
    caminho.write_text(json.dumps(congelado, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def test_configuracao_congela_colunas_e_hiperparametros(ambiente, tmp_path):
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json")
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params_teste()) == 0
    congelado = json.loads(caminho.read_text(encoding="utf-8"))
    meta3 = json.loads((ambiente["modelos"] / "xgb-2026-01.meta.json").read_text(encoding="utf-8"))
    meta1 = json.loads((ambiente["modelos"] / "xgb-m1-2026-01.meta.json").read_text(encoding="utf-8"))
    assert meta3["colunas"] == congelado["colunas_3"]
    assert set(BLOCOS_PROTOCOLO["bloco_a"]) <= set(meta3["colunas"])
    assert meta1["colunas"] == congelado["colunas_1"]
    assert meta3["hiperparametros"] == congelado["hiperparametros"]
    assert meta3["blocos"] == {"blocos_preco": ["preco_contexto"], "noticias_contexto": True}


def test_configuracao_grava_a_origem_nos_dois_metas(ambiente, tmp_path):
    origem = {"busca": 3, "protocolo": 3}
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json", rodadas_de_origem=origem, vencedor="referencia")
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params_teste()) == 0
    sha = hashlib.sha256(caminho.read_bytes()).hexdigest()
    esperado = {"arquivo": caminho.name, "sha256": sha, "rodadas_de_origem": origem, "vencedor": "referencia"}
    for nome in ("xgb-2026-01.meta.json", "xgb-m1-2026-01.meta.json"):
        meta = json.loads((ambiente["modelos"] / nome).read_text(encoding="utf-8"))
        assert meta["configuracao"] == esperado


def test_configuracao_sem_chaves_de_rodada_grava_none(ambiente, tmp_path):
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json")
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params_teste()) == 0
    meta3 = json.loads((ambiente["modelos"] / "xgb-2026-01.meta.json").read_text(encoding="utf-8"))
    assert meta3["configuracao"]["arquivo"] == caminho.name
    assert meta3["configuracao"]["sha256"] == hashlib.sha256(caminho.read_bytes()).hexdigest()
    assert meta3["configuracao"]["rodadas_de_origem"] is None
    assert meta3["configuracao"]["vencedor"] is None


def test_sem_configuracao_os_metas_trazem_configuracao_none(ambiente):
    _rodar(ambiente)
    for nome in ("xgb-2026-01.meta.json", "xgb-m1-2026-01.meta.json"):
        meta = json.loads((ambiente["modelos"] / nome).read_text(encoding="utf-8"))
        assert meta["configuracao"] is None


def test_configuracao_nao_roda_a_selecao(ambiente, tmp_path, monkeypatch):
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json")

    def proibido(*args, **kwargs):
        raise AssertionError("com --configuracao não pode haver seleção de configuração")

    monkeypatch.setattr(treino, "selecionar_configuracao", proibido)
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params_teste()) == 0


def test_configuracao_de_outro_dataset_devolve_2(ambiente, tmp_path, capsys):
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json", sha256_dataset="0" * 64)
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params_teste()) == 2
    assert "sha256" in capsys.readouterr().out


def test_configuracao_de_familia_lgbm_devolve_2(ambiente, tmp_path, capsys):
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json", familia="lgbm")
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params_teste()) == 2
    assert "lgbm" in capsys.readouterr().out


def test_configuracao_inexistente_devolve_2(ambiente, tmp_path, capsys):
    assert treino.main(_argv(ambiente, "--configuracao", str(tmp_path / "nao_existe.json")), params=params_teste()) == 2
    assert "configuração não encontrada" in capsys.readouterr().out


def test_configuracao_logistica_grava_os_modelos_da_logistica(ambiente, tmp_path):
    params = params_teste(familia_producao="logistica")
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json", familia="logistica", hiperparametros=None)
    assert treino.main(_argv(ambiente, "--configuracao", str(caminho)), params=params) == 0

    meta3 = json.loads((ambiente["modelos"] / "logistica-2026-01.meta.json").read_text(encoding="utf-8"))
    assert meta3["familia"] == "logistica"
    assert meta3["hiperparametros"] == {"C": 1.0}
    assert (ambiente["modelos"] / "logistica-m1-2026-01.json").is_file()
    assert not (ambiente["modelos"] / "xgb-2026-01.json").exists()
    modelo, _ = modelos.carregar_modelo(ambiente["modelos"] / "logistica-2026-01.json")
    assert isinstance(modelo, modelos.ModeloLogistico)
    # o teste final lê a configuração da família de produção, pela meta
    cfg = treino._configuracao_congelada(ambiente["modelos"], params)
    assert cfg["familia"] == "logistica" and cfg["hiperparametros"] == {"C": 1.0}


def test_ler_configuracao_recusa_familia_diferente_da_producao(ambiente, tmp_path):
    caminho = _gravar_congelado(ambiente, tmp_path / "congelado.json", familia="logistica", hiperparametros=None)
    sha = json.loads(caminho.read_text(encoding="utf-8"))["sha256_dataset"]
    with pytest.raises(treino.ErroPreRequisito, match="treino.familia_producao"):
        treino._ler_configuracao(caminho, sha, params_teste())  # produção xgb
    cfg = treino._ler_configuracao(caminho, sha, params_teste(familia_producao="logistica"))
    assert cfg["familia"] == "logistica" and cfg["hiperparametros"] == {"C": 1.0}
    assert cfg["colunas_3"] == json.loads(caminho.read_text(encoding="utf-8"))["colunas_3"]


def test_veredito_nomeia_a_terceira_referencia():
    def bloco(taxa_modelo, taxa_vol, taxa_ref):
        def top5(taxa, situacao="acima"):
            return {"topk": {"5": {"taxa_acerto": taxa, "vs_acaso": situacao}}}
        return {treino.MODELO_CALIBRADO: top5(taxa_modelo), "volatilidade": top5(taxa_vol), "logistica": top5(taxa_ref)}

    venceu = treino._veredito(bloco(0.6, 0.5, 0.4), "o XGBoost")
    assert venceu["supera_logistica"] is True and venceu["referencia_terceira"] == "o XGBoost"
    assert venceu["texto"].endswith("e o XGBoost neste período.")
    perdeu = treino._veredito(bloco(0.6, 0.5, 0.7), "o XGBoost")
    assert perdeu["texto"].endswith("mas não superou o XGBoost.")
    padrao = treino._veredito(bloco(0.6, 0.5, 0.4))
    assert padrao["texto"].endswith("e a logística neste período.") and padrao["referencia_terceira"] == "a logística"
