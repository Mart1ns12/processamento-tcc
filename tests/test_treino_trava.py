"""Testes da trava do teste final (plano da etapa 6, fase 6c): `conferir_trava`, códigos de saída do `main`
e o teste final ponta a ponta com dados sintéticos. Nada de banco ou rede; o registro vai para tmp_path.
"""

import json
from datetime import date

import pandas as pd
import pytest

from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento.experimento import dataset, treino
from processamento.experimento.preparacao import COLUNAS_RANK
from processamento.experimento.validacao import dobras_teste_final

FIM = date(2026, 1, 20)


@pytest.fixture(autouse=True)
def registro_isolado(tmp_path, monkeypatch):
    """Nenhum teste deste arquivo pode tocar o registro real do teste final (docs/)."""
    monkeypatch.setattr(treino, "REGISTRO_TESTE_FINAL", tmp_path / "docs" / "teste_final_usado.json")


@pytest.fixture
def ambiente(tmp_path):
    datasets = tmp_path / "datasets"
    gravar_versoes(datasets, dataset_sintetico())
    return {
        "datasets": datasets,
        "saida": tmp_path / "saida",
        "modelos": tmp_path / "modelos",
        "registro": tmp_path / "docs" / "teste_final_usado.json",
    }


def _argv(amb, *extra):
    return [
        "--pasta-datasets", str(amb["datasets"]),
        "--pasta-saida", str(amb["saida"]),
        "--pasta-modelos", str(amb["modelos"]),
        *extra,
    ]


def _params_liberado(**trocas):
    return params_teste(teste_final_fim=FIM, teste_final_liberado=True, **trocas)


def _ler_metricas(pasta):
    return json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))


def _sem_campos_do_dataset(metricas):
    saida = {k: v for k, v in metricas.items() if k != "gerado_em"}
    saida["datasets"] = {
        nome: None if bloco is None else {k: v for k, v in bloco.items() if k not in ("sha256", "arquivo")}
        for nome, bloco in metricas["datasets"].items()
    }
    return saida


def _envenenar(df, mascara):
    """Cópia com as linhas marcadas estragadas (mesmo veneno de test_treino_pipeline.py)."""
    saida = df.copy()
    cols = list(dict.fromkeys([*COLUNAS_RANK, *dataset.COLUNAS_NOTICIAS]))
    saida.loc[mascara, cols] = saida.loc[mascara, cols] * -1
    saida.loc[mascara, "alvo"] = 1 - saida.loc[mascara, "alvo"]
    saida.loc[mascara, "ret_t1"] = 99.0
    return saida


@pytest.mark.parametrize(
    "pedido, liberado, fim, mensagem",
    [
        (False, False, None, None),
        (False, True, FIM, None),
        (True, True, None, "fim vazio"),
        (True, False, FIM, "liberado"),
    ],
)
def test_conferir_trava_na_ordem_certa(tmp_path, pedido, liberado, fim, mensagem):
    registro = tmp_path / "registro.json"
    if mensagem is None:
        treino.conferir_trava(pedido, liberado, fim, registro)
    else:
        with pytest.raises(treino.ErroTravaTesteFinal, match=mensagem):
            treino.conferir_trava(pedido, liberado, fim, registro)


def test_conferir_trava_passa_sem_registro(tmp_path):
    treino.conferir_trava(True, True, FIM, tmp_path / "registro.json")


def test_conferir_trava_bloqueia_com_registro(tmp_path):
    registro = tmp_path / "registro.json"
    registro.write_text("{}", encoding="utf-8")
    with pytest.raises(treino.ErroTravaTesteFinal, match="já foi usado"):
        treino.conferir_trava(True, True, FIM, registro)


def test_main_com_liberado_false_devolve_4_e_nada_e_gravado(ambiente, capsys):
    params = params_teste(teste_final_fim=FIM, teste_final_liberado=False)
    codigo = treino.main(_argv(ambiente, "--teste-final"), params=params, registro=ambiente["registro"])
    assert codigo == 4
    assert "liberado" in capsys.readouterr().out
    assert not ambiente["saida"].exists()
    assert not ambiente["modelos"].exists()
    assert not ambiente["registro"].exists()


def test_main_com_fim_vazio_devolve_4_e_nada_e_gravado(ambiente, capsys):
    params = params_teste(teste_final_fim=None, teste_final_liberado=True)
    codigo = treino.main(_argv(ambiente, "--teste-final"), params=params, registro=ambiente["registro"])
    assert codigo == 4
    assert "fim vazio" in capsys.readouterr().out
    assert not ambiente["saida"].exists()
    assert not ambiente["registro"].exists()


def test_teste_final_sem_treino_de_desenvolvimento_da_erro(ambiente, capsys):
    params = _params_liberado()
    with pytest.raises(treino.ErroPreRequisito, match="rode antes o treino de desenvolvimento"):
        treino.executar(
            ambiente["datasets"], ambiente["saida"], ambiente["modelos"],
            teste_final=True, params=params, registro=ambiente["registro"],
        )
    assert not ambiente["saida"].exists()
    assert not ambiente["registro"].exists()

    codigo = treino.main(_argv(ambiente, "--teste-final"), params=params, registro=ambiente["registro"])
    assert codigo == 2
    assert "rode antes o treino de desenvolvimento" in capsys.readouterr().out


@pytest.fixture
def teste_final_feito(ambiente):
    """Desenvolvimento e depois teste final com a trava aberta (fim = 2026-01-20)."""
    treino.executar(ambiente["datasets"], ambiente["saida"], ambiente["modelos"], params=params_teste())
    caminho = treino.executar(
        ambiente["datasets"], ambiente["saida"], ambiente["modelos"],
        teste_final=True, params=_params_liberado(), registro=ambiente["registro"],
    )
    return caminho


def test_teste_final_grava_relatorio_e_registro(ambiente, teste_final_feito):
    pasta = teste_final_feito.parent
    assert pasta.name.startswith("teste-final-")
    assert "TESTE FINAL" in teste_final_feito.read_text(encoding="utf-8")

    registro = json.loads(ambiente["registro"].read_text(encoding="utf-8"))
    chaves = {"usado_em", "teste_final_inicio", "teste_final_fim", "n_dias", "sha256_dataset",
              "configuracao", "relatorio", "resumo"}
    assert chaves <= set(registro)
    assert registro["teste_final_inicio"] == "2026-01-02"
    assert registro["teste_final_fim"] == "2026-01-20"
    assert registro["relatorio"] == f"{pasta.name}/relatorio.md"


def test_teste_final_so_preve_entre_inicio_e_fim(teste_final_feito):
    pasta = teste_final_feito.parent
    previsoes = pd.read_csv(pasta / "previsoes.csv", parse_dates=["data"])
    assert previsoes["data"].min() >= pd.Timestamp("2026-01-02")
    # dia do alvo (t+1) <= fim: a linha do próprio FIM (ter 2026-01-20) é a 1ª previsão ao vivo
    assert previsoes["data"].max() == pd.Timestamp("2026-01-19")
    metricas = _ler_metricas(pasta)
    assert [d["mes_teste"] for d in metricas["dobras"]] == ["2026-01"]
    assert metricas["periodo"]["teste_final_usado"] is True
    assert metricas["periodo"]["teste_final_fim"] == "2026-01-20"


def test_teste_final_treino_para_antes_do_embargo(teste_final_feito):
    """O treino da dobra termina no pregão anterior ao embargo (2026-01-01 fica de fora)."""
    dobra = _ler_metricas(teste_final_feito.parent)["dobras"][0]
    assert dobra["treino_fim"] == "2025-12-31"
    cal = sorted({pd.Timestamp(d).date() for d in dataset_sintetico()["data"]})
    dobra_ref = dobras_teste_final([d for d in cal if d <= FIM], date(2026, 1, 2), FIM, 1)[0]
    assert date(2026, 1, 1) not in dobra_ref.datas_treino
    assert max(dobra_ref.datas_treino) == date(2025, 12, 31)


def test_veneno_do_teste_ao_vivo_nao_muda_nada(tmp_path, ambiente, teste_final_feito):
    df = dataset_sintetico()
    envenenado = _envenenar(df, df["data"] >= pd.Timestamp(FIM))  # a linha do FIM já é ao vivo
    assert (df["data"] > pd.Timestamp(FIM)).any()
    datasets = tmp_path / "envenenado"
    gravar_versoes(datasets, envenenado)
    registro_2 = tmp_path / "outro" / "registro.json"
    estragado = treino.executar(
        datasets, tmp_path / "saida2", ambiente["modelos"],
        teste_final=True, params=_params_liberado(), registro=registro_2,
    )
    original = teste_final_feito.parent
    assert (original / "previsoes.csv").read_bytes() == (estragado.parent / "previsoes.csv").read_bytes()
    assert _sem_campos_do_dataset(_ler_metricas(original)) == _sem_campos_do_dataset(_ler_metricas(estragado.parent))


def test_segunda_chamada_do_teste_final_e_bloqueada(ambiente, teste_final_feito, capsys):
    with pytest.raises(treino.ErroTravaTesteFinal, match="já foi usado"):
        treino.executar(
            ambiente["datasets"], ambiente["saida"], ambiente["modelos"],
            teste_final=True, params=_params_liberado(), registro=ambiente["registro"],
        )
    codigo = treino.main(
        _argv(ambiente, "--teste-final"), params=_params_liberado(), registro=ambiente["registro"]
    )
    assert codigo == 4
    assert "já foi usado" in capsys.readouterr().out


def test_liberado_sem_a_opcao_roda_o_desenvolvimento_sem_registro(ambiente):
    codigo = treino.main(_argv(ambiente), params=_params_liberado(), registro=ambiente["registro"])
    assert codigo == 0
    assert not ambiente["registro"].exists()
    assert any(p.name.startswith("dev-") for p in ambiente["saida"].iterdir())
