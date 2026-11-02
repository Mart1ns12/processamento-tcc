"""Testes do núcleo de treino.py (etapa 6, fase 6a): leitura do dataset, previsões walk-forward,
seleção de configuração e avaliação. Dados sintéticos de tests/fabrica_treino.py; nada de banco ou rede.
"""

import json

import pandas as pd
import pytest

from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento.experimento import treino, validacao
from processamento.experimento.preparacao import COLUNAS_PROTOCOLO, colunas_do_modelo

BLOCOS_TODOS = ("preco_contexto", "macro", "noticias_contexto")


@pytest.fixture(scope="module")
def dev(tmp_path_factory):
    """Dataset sintético gravado, lido como desenvolvimento e preparado (uma vez por módulo)."""
    pasta = tmp_path_factory.mktemp("treino")
    gravados = gravar_versoes(pasta, dataset_sintetico())
    params = params_teste()
    df_dev, info = treino.ler_desenvolvimento(gravados["todas"], params)
    prep, cal = treino.preparar_dev(df_dev)
    dobras = validacao.dobras_walk_forward(cal, params.treino_minimo_meses, params.embargo_pregoes)
    return {"pasta": pasta, "gravados": gravados, "params": params, "df_dev": df_dev,
            "info": info, "prep": prep, "cal": cal, "dobras": dobras}


def _pares(df: pd.DataFrame) -> set:
    return {(pd.Timestamp(d), t) for d, t in zip(df["data"], df["ticker"])}


def test_localizar_pega_a_maior_data_e_as_versoes_da_mesma_data(tmp_path):
    gravar_versoes(tmp_path, dataset_sintetico(n_pregoes=20))
    gravar_versoes(tmp_path, dataset_sintetico(n_pregoes=25))
    ultima = pd.bdate_range("2025-08-01", periods=25)[-1].strftime("%Y-%m-%d")
    maior = treino.localizar_datasets(tmp_path, None)
    assert maior["todas"].name == f"dataset-todas-{ultima}.csv"
    assert maior["principais"].name == f"dataset-principais-{ultima}.csv"
    assert maior["hora_real_noite"].name == f"dataset-hora_real_noite-{ultima}.csv"

    antiga_data = pd.bdate_range("2025-08-01", periods=20)[-1].date()
    antiga = treino.localizar_datasets(tmp_path, antiga_data)
    assert antiga["todas"].name == f"dataset-todas-{antiga_data:%Y-%m-%d}.csv"


def test_localizar_sem_todas_da_erro(tmp_path):
    with pytest.raises(treino.ErroDataset, match="dataset-todas"):
        treino.localizar_datasets(tmp_path, None)


def test_ler_desenvolvimento_nunca_devolve_teste_final(dev):
    df = dev["df_dev"]
    assert df["data"].max() < pd.Timestamp("2026-01-01")
    assert df["data"].max() == pd.Timestamp("2025-12-31")
    assert len(df) > 0
    assert "sha256" in dev["info"]


def test_ler_desenvolvimento_aplica_inicio_da_cobertura_e_de_data(dev):
    df_cobertura, info = treino.ler_desenvolvimento(dev["gravados"]["todas"], dev["params"])
    assert df_cobertura["data"].min() == pd.Timestamp(info["cobertura_inicio"])

    params_data = params_teste(inicio_experimento="2025-09-01")
    df_data, _ = treino.ler_desenvolvimento(dev["gravados"]["todas"], params_data)
    assert df_data["data"].min() == pd.Timestamp("2025-09-01")


def test_sha_alterado_da_erro(dev):
    csv = dev["gravados"]["principais"]
    original = csv.read_bytes()
    csv.write_bytes(original + b"\n")
    try:
        with pytest.raises(treino.ErroDataset, match="sha256"):
            treino.ler_desenvolvimento(csv, dev["params"])
    finally:
        csv.write_bytes(original)


def test_csv_sem_alvo_abertura_valido_pede_regerar(tmp_path):
    sem_coluna = dataset_sintetico().drop(columns=["alvo_abertura_valido"])
    csv = gravar_versoes(tmp_path, sem_coluna, versoes=("todas",))["todas"]
    with pytest.raises(treino.ErroDataset, match="regenere"):
        treino.ler_desenvolvimento(csv, params_teste())


def test_preparar_dev_calendario_e_linhas_com_alvo(dev):
    prep, cal = dev["prep"], dev["cal"]
    assert cal == sorted(set(cal))
    assert len(cal) == dev["df_dev"]["data"].nunique()
    assert prep["alvo"].notna().all()
    assert dev["dobras"], "as dobras de desenvolvimento não podem estar vazias"


def test_tres_tipos_avaliam_as_mesmas_linhas(dev):
    prep, dobras, params = dev["prep"], dev["dobras"], dev["params"]
    colunas = colunas_do_modelo("3", BLOCOS_TODOS)
    esperado = set()
    for dobra in dobras:
        _, teste = validacao.linhas_da_dobra(prep, dobra)
        esperado |= _pares(teste)

    for tipo in ("xgb", "logistica", "volatilidade"):
        pred = treino.prever_walk_forward(prep, dobras, colunas, tipo, params)
        assert _pares(pred) == esperado, tipo
        assert len(pred) == len(esperado), f"{tipo}: par repetido"
        assert pred["dobra"].isin([d.numero for d in dobras]).all()


def test_selecionar_configuracao_roda_duas_vezes_igual(dev):
    prep, dobras, params = dev["prep"], dev["dobras"], dev["params"]
    primeira, tab1 = treino.selecionar_configuracao(prep, dobras, params)
    segunda, tab2 = treino.selecionar_configuracao(prep, dobras, params)
    assert primeira == segunda
    pd.testing.assert_frame_equal(tab1, tab2)
    assert set(primeira) == {
        "blocos_preco", "noticias_contexto", "extremo_em_rank", "hiperparametros", "colunas_1", "colunas_3",
    }
    assert set(primeira["blocos_preco"]) <= {"preco_contexto", "macro"}
    assert isinstance(primeira["noticias_contexto"], bool)
    assert primeira["hiperparametros"]["max_depth"] == 2
    assert tab1["aceito"].sum() >= 1  # a grade sempre marca a escolhida


def test_avaliar_monta_o_bloco_e_as_faixas_sao_uma_so(dev):
    prep, dobras, params = dev["prep"], dev["dobras"], dev["params"]
    colunas = colunas_do_modelo("3", BLOCOS_TODOS)
    pred = treino.prever_walk_forward(prep, dobras, colunas, "xgb", params)
    pred_vol = treino.prever_walk_forward(prep, dobras, colunas, "volatilidade", params)

    acaso = treino.calcular_acaso(pred, params)
    acaso_vol = treino.calcular_acaso(pred_vol, params)
    assert set(acaso) == {"5", "3", "abertura"}
    assert set(acaso["abertura"]) == {"5", "3"}
    for k in ("5", "3"):  # a faixa depende só das linhas candidatas, não do modelo
        assert acaso[k]["p2_5"] == acaso_vol[k]["p2_5"]
        assert acaso[k]["p97_5"] == acaso_vol[k]["p97_5"]

    bloco = treino.avaliar(pred, params, acaso, colunas=colunas)
    assert set(bloco) == {"colunas", "auc_geral", "auc_medio_pregao", "n_dias_auc", "topk", "abertura", "por_ano", "sensibilidade"}
    assert set(bloco["topk"]) == {"5", "3"}
    assert bloco["topk"]["5"]["vs_acaso"] in ("acima", "dentro", "abaixo")
    assert len(bloco["topk"]["5"]["ic_taxa"]) == 2
    assert bloco["abertura"]["n_dias_total"] >= bloco["abertura"]["n_dias_validos"]
    assert {"ano", "n_dias", "taxa_acerto_5", "excesso_5", "taxa_acerto_3"} <= set(bloco["por_ano"][0])
    assert set(bloco["sensibilidade"]) == {"corte", "ultimo_ano", "anteriores"}
    json.dumps(bloco)  # só tipos que o JSON grava


def test_avaliar_sem_colunas_grava_none(dev):
    prep, dobras, params = dev["prep"], dev["dobras"], dev["params"]
    pred = treino.prever_walk_forward(prep, dobras, colunas_do_modelo("1"), "volatilidade", params)
    bloco = treino.avaliar(pred, params, treino.calcular_acaso(pred, params))
    assert bloco["colunas"] is None


# ---------------------------------------------------------------- versão de preparação e extremo em rank


@pytest.mark.parametrize("versao", [None, 1, 2])
def test_csv_de_outra_versao_de_preparacao_pede_regerar(tmp_path, versao):
    import json

    csv = gravar_versoes(tmp_path, dataset_sintetico(), versoes=("todas",))["todas"]
    caminho = csv.with_suffix(".json")
    info = json.loads(caminho.read_text(encoding="utf-8"))
    if versao is None:
        info.pop("versao_preparacao")
    else:
        info["versao_preparacao"] = versao
    caminho.write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(treino.ErroDataset, match="regenere"):
        treino.ler_desenvolvimento(csv, params_teste())


@pytest.mark.parametrize("ganho, adotado", [(0.01, True), (0.004, False), (0.0, False)])
def test_extremo_em_rank_so_entra_se_o_ganho_passar_do_minimo(monkeypatch, ganho, adotado):
    from processamento.experimento import preparacao

    monkeypatch.setattr(treino, "prever_walk_forward", lambda prep, dobras, colunas, tipo, params, hiper=None: colunas)
    monkeypatch.setattr(
        treino, "auc_medio_wf", lambda colunas: 0.5 + (ganho if preparacao.EXTREMO_RANK in colunas else 0.0)
    )
    cfg, tentativas = treino.selecionar_configuracao(None, [], params_teste())
    assert cfg["extremo_em_rank"] is adotado
    assert (preparacao.EXTREMO_RANK in cfg["colunas_3"]) is adotado
    assert ("noticias_dia_extremo" in cfg["colunas_3"]) is not adotado
    assert preparacao.EXTREMO_RANK not in cfg["colunas_1"]
    linha = tentativas[tentativas["descricao"] == "noticias_dia_extremo em rank"]
    assert len(linha) == 1 and bool(linha["aceito"].iloc[0]) is adotado


def test_selecionar_configuracao_nao_usa_os_blocos_do_protocolo(monkeypatch):
    vistas = []
    monkeypatch.setattr(treino, "prever_walk_forward",
                        lambda prep, dobras, colunas, tipo, params, hiper=None: vistas.append(list(colunas)) or colunas)
    monkeypatch.setattr(treino, "auc_medio_wf", lambda colunas: 0.9)
    cfg, _ = treino.selecionar_configuracao(None, [], params_teste())
    assert vistas
    for colunas in vistas:
        assert not set(colunas) & set(COLUNAS_PROTOCOLO)
    assert not set(cfg["colunas_1"]) & set(COLUNAS_PROTOCOLO)
    assert not set(cfg["colunas_3"]) & set(COLUNAS_PROTOCOLO)


def test_selecionar_blocos_sem_grade_nem_extremo(monkeypatch):
    from processamento.experimento import preparacao

    vistas = []
    monkeypatch.setattr(treino, "prever_walk_forward",
                        lambda prep, dobras, colunas, tipo, params, hiper=None: vistas.append(list(colunas)) or colunas)
    monkeypatch.setattr(treino, "auc_medio_wf", lambda colunas: 0.9)
    sel = treino.selecionar_blocos(None, [], params_teste())
    esperado = [
        preparacao.colunas_do_modelo("1", ()),
        preparacao.colunas_do_modelo("1", ("preco_contexto",)),
        preparacao.colunas_do_modelo("1", ("macro",)),
        preparacao.colunas_do_modelo("3", ()),
        preparacao.colunas_do_modelo("3", ("noticias_contexto",)),
    ]
    assert vistas == esperado
    for colunas in vistas:
        assert "noticias_dia_extremo_rank" not in colunas
        assert not set(colunas) & set(COLUNAS_PROTOCOLO)
    assert sel["blocos"] == []
    assert sel["noticias_contexto"] is False
    assert len(sel["tentativas"]) == 3


def test_selecionar_blocos_aceita_acima_do_ganho(monkeypatch):
    vistas = []
    monkeypatch.setattr(treino, "prever_walk_forward",
                        lambda prep, dobras, colunas, tipo, params, hiper=None: vistas.append(list(colunas)) or colunas)
    monkeypatch.setattr(treino, "auc_medio_wf", lambda colunas: 0.506 if "dist_max_52s" in colunas else 0.5)
    sel = treino.selecionar_blocos(None, [], params_teste())
    assert len(vistas) == 5
    assert sel["blocos"] == ["preco_contexto"]
    assert sel["noticias_contexto"] is False


def test_selecionar_blocos_recusa_ganho_igual_ao_minimo(monkeypatch):
    monkeypatch.setattr(treino, "prever_walk_forward",
                        lambda prep, dobras, colunas, tipo, params, hiper=None: colunas)
    monkeypatch.setattr(treino, "auc_medio_wf", lambda colunas: 0.75 if "dist_max_52s" in colunas else 0.5)
    sel = treino.selecionar_blocos(None, [], params_teste(ganho_minimo_bloco=0.25))
    assert sel["blocos"] == []
    assert sel["noticias_contexto"] is False
