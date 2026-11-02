"""Testes do retreino mensal (plano da etapa 8, fase 6; seção 7): os 7 casos com os valores do plano.

Dados sintéticos de tests/fabrica_treino.py, em tmp_path. Nada de banco ou rede. O registro do teste final
é isolado em tmp_path (o real, docs/teste_final_usado.json, não é tocado).
"""

import json
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from fabrica_treino import dataset_sintetico, params_teste
from processamento.experimento import modelos, preparacao, treino
from processamento.rotina import retreino
from processamento.saida import contrato

AGORA = datetime(2026, 11, 3, 9, 0, tzinfo=contrato.SP)
INFO = {"cobertura_inicio": "2026-08-03"}
D1 = date(2026, 11, 3)
D2 = date(2026, 11, 4)


@pytest.fixture(autouse=True)
def registro_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(treino, "REGISTRO_TESTE_FINAL", tmp_path / "docs" / "teste_final_usado.json")


@pytest.fixture(scope="module")
def completo():
    """70 pregões de 2026-08-03 a 2026-11-06, 12 tickers (dias úteis)."""
    return dataset_sintetico(inicio="2026-08-03", n_pregoes=70, n_tickers=12)


def _dia(df):
    return pd.to_datetime(df["data"]).dt.normalize()


def _ate(df, dia):
    """Linhas até `dia` (inclusive), como o dataset ao vivo naquele dia."""
    return df.loc[_dia(df) <= pd.Timestamp(dia)].copy()


def _apagar_alvo(df, dia):
    """Alvo dos pregões de `dia` vira NaN (o pregão seguinte ainda não existe no dataset)."""
    df = df.copy()
    df.loc[_dia(df) == pd.Timestamp(dia), "alvo"] = np.nan
    return df


def _inverter_alvo_a_partir(df, dia):
    """Veneno: inverte o alvo (1 - alvo) de todas as linhas com data >= `dia` que têm alvo."""
    df = df.copy()
    mascara = (_dia(df) >= pd.Timestamp(dia)) & df["alvo"].notna()
    df.loc[mascara, "alvo"] = 1.0 - df.loc[mascara, "alvo"]
    return df


def _cal(df):
    return sorted(_dia(df).dt.date.unique())


def _ler(pasta, nome):
    return json.loads((pasta / nome).read_text(encoding="utf-8"))


def _meta_dev(modelo, colunas, params, calibracao):
    meta = {chave: None for chave in modelos.CHAVES_METADADOS}
    meta.update({
        "modelo": modelo,
        "versao_noticias": "todas",
        "versao_preparacao": preparacao.VERSAO_PREPARACAO,
        "colunas": colunas,
        "blocos": {"blocos_preco": [], "noticias_contexto": False},
        "hiperparametros": params.xgboost,
        "semente": params.semente,
        "periodo_treino": {"inicio": "2025-08-01", "fim": "2025-12-31"},
        "metricas_validacao": {"auc_geral": 0.51},
        "calibracao": calibracao,
        "provisorio": True,
        "aviso": treino.AVISO_PROVISORIO,
        "teste_final": {"inicio": "2026-01-02", "fim": None, "usado": False},
    })
    return meta


def _pasta_dev(tmp_path, nome="modelos", params=None):
    """Pasta com os metadados do desenvolvimento (xgb-2026-01 e xgb-m1-2026-01), como o treino de dev grava."""
    params = params or params_teste()
    pasta = tmp_path / nome
    rng = np.random.default_rng(0)
    cols3 = preparacao.colunas_do_modelo("3")
    cols1 = preparacao.colunas_do_modelo("1")
    X = pd.DataFrame(rng.normal(size=(60, len(cols3))), columns=cols3)
    y = pd.Series(rng.integers(0, 2, 60))
    modelo = modelos.treinar_xgb(X, y, params.xgboost, params.semente)
    mes = params.teste_final_inicio.strftime("%Y-%m")
    modelos.salvar_modelo(modelo, _meta_dev("3", cols3, params, {"aprovada": False}), pasta,
                          modelos.nome_modelo(mes, "3"))
    modelos.salvar_modelo(modelo, _meta_dev("1", cols1, params, None), pasta, modelos.nome_modelo(mes, "1"))
    return pasta


def _treinar(tmp_path, nome, df, params, d=D2):
    pasta = _pasta_dev(tmp_path, nome, params)
    retreino.retreinar_mes(df, INFO, _cal(df), d, pasta_modelos=pasta, params=params, agora=AGORA)
    return pasta


def _prob_do_dia(pasta, completo, dia):
    """Probabilidades do modelo 3 do mês 2026-11 nas linhas de `dia` (features de `completo`)."""
    modelo, _ = modelos.carregar_modelo(pasta / "xgb-2026-11.json")
    colunas = _ler(pasta, "xgb-2026-11.meta.json")["colunas"]
    prep = preparacao.preparar(completo)
    linhas = prep.loc[_dia(prep) == pd.Timestamp(dia)]
    return modelos.prob_xgb(modelo, linhas[colunas])


def test_caso_1_grava_os_quatro_arquivos_com_o_corte_certo(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30))
    pasta = _pasta_dev(tmp_path, params=params)
    df = _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30")
    cal = _cal(df)

    treinar = retreino.datas_de_treino(cal, "2026-11", 1)
    assert len(treinar) == 64
    assert treinar[0] == date(2026, 8, 3) and treinar[-1] == date(2026, 10, 29)

    avisos = retreino.retreinar_mes(df, INFO, cal, D1, pasta_modelos=pasta, params=params, agora=AGORA)
    assert avisos == []
    for nome in ("xgb-m1-2026-11.json", "xgb-m1-2026-11.meta.json", "xgb-2026-11.json", "xgb-2026-11.meta.json"):
        assert (pasta / nome).is_file()

    meta = _ler(pasta, "xgb-2026-11.meta.json")
    dev = _ler(pasta, "xgb-2026-01.meta.json")
    assert all(chave in meta for chave in modelos.CHAVES_METADADOS)
    assert meta["n_linhas_treino"] == 768
    assert meta["periodo_treino"] == {"inicio": "2026-08-03", "fim": "2026-10-29"}
    assert meta["retreino"]["corte_antes_de"] == "2026-11-01"
    assert meta["colunas"] == dev["colunas"]
    assert meta["hiperparametros"] == dev["hiperparametros"]
    assert meta["provisorio"] is True
    assert meta["aviso"] == treino.AVISO_PROVISORIO
    assert meta["calibracao"] == {"aprovada": False}
    assert meta["metricas_validacao"] == {"auc_geral": 0.51, "origem": "desenvolvimento"}
    assert meta["teste_final"]["fim"] == "2026-10-30"
    assert meta["retreino"]["configuracao_de"] == "xgb-2026-01"
    assert _ler(pasta, "xgb-m1-2026-11.meta.json")["calibracao"] is None


def test_caso_2_segunda_chamada_nao_retreina(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30))
    pasta = _pasta_dev(tmp_path, params=params)
    df = _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30")
    cal = _cal(df)
    retreino.retreinar_mes(df, INFO, cal, D1, pasta_modelos=pasta, params=params, agora=AGORA)
    antes = {arq.name: arq.read_bytes() for arq in pasta.iterdir()}

    assert retreino.retreinar_mes(df, INFO, cal, D1, pasta_modelos=pasta, params=params, agora=AGORA) == []
    depois = {arq.name: arq.read_bytes() for arq in pasta.iterdir()}
    assert depois == antes


def test_caso_3_pregao_seguinte_chega_ao_mesmo_modelo(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30))
    p1 = _treinar(tmp_path, "um", _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30"), params, D1)
    df3 = _apagar_alvo(_ate(completo, "2026-11-03"), "2026-11-03")
    p3 = _treinar(tmp_path, "tres", df3, params, D2)

    meta = _ler(p3, "xgb-2026-11.meta.json")
    assert meta["n_linhas_treino"] == 768
    assert meta["periodo_treino"] == {"inicio": "2026-08-03", "fim": "2026-10-29"}
    assert np.allclose(_prob_do_dia(p1, completo, "2026-10-30"), _prob_do_dia(p3, completo, "2026-10-30"),
                       rtol=0, atol=0)


def test_caso_4_veneno_no_alvo_futuro_nao_muda_o_modelo(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30))
    df3 = _apagar_alvo(_ate(completo, "2026-11-03"), "2026-11-03")
    df4 = _inverter_alvo_a_partir(df3, "2026-11-01")
    # o veneno de fato mudou o alvo de 11-02 (senão o teste não provaria nada)
    assert not np.array_equal(
        df4.loc[_dia(df4) == pd.Timestamp("2026-11-02"), "alvo"].to_numpy(),
        df3.loc[_dia(df3) == pd.Timestamp("2026-11-02"), "alvo"].to_numpy(),
    )
    p3 = _treinar(tmp_path, "limpo", df3, params, D2)
    p4 = _treinar(tmp_path, "veneno", df4, params, D2)
    assert np.allclose(_prob_do_dia(p3, completo, "2026-10-30"), _prob_do_dia(p4, completo, "2026-10-30"),
                       rtol=0, atol=0)


def test_caso_5_sem_fim_nao_retreina_nem_grava(tmp_path, completo):
    params = params_teste()  # teste_final_fim = None: produção ainda não começou
    pasta = _pasta_dev(tmp_path, params=params)
    df = _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30")
    antes = sorted(arq.name for arq in pasta.iterdir())

    assert retreino.retreinar_mes(df, INFO, _cal(df), D1, pasta_modelos=pasta, params=params, agora=AGORA) == []
    assert sorted(arq.name for arq in pasta.iterdir()) == antes
    assert retreino.precisa_retreinar(pasta, D1, None) is False


def test_caso_6_sem_metadados_do_dev_levanta_pre_requisito(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30))
    df = _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30")
    pasta = tmp_path / "vazia"
    pasta.mkdir()
    with pytest.raises(treino.ErroPreRequisito):
        retreino.retreinar_mes(df, INFO, _cal(df), D1, pasta_modelos=pasta, params=params, agora=AGORA)


def test_caso_7_modelo_oficial_tira_o_provisorio(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30), modelo_oficial=True)
    df = _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30")
    pasta = _treinar(tmp_path, "oficial", df, params, D1)
    for nome in ("xgb-2026-11.meta.json", "xgb-m1-2026-11.meta.json"):
        meta = _ler(pasta, nome)
        assert meta["provisorio"] is False
        assert meta["aviso"] is None


def test_metadados_do_treino_de_dev_seguem_modelo_oficial():
    res = {
        "cfg": {"blocos_preco": [], "noticias_contexto": False, "hiperparametros": {"max_depth": 2}},
        "prep": pd.DataFrame({"data": pd.to_datetime(["2026-08-03", "2026-08-04"])}),
    }
    bloco = {"auc_geral": 0.5, "auc_medio_pregao": 0.5, "topk": {"5": {"taxa_acerto": 0.5}}}
    for oficial, provisorio in ((False, True), (True, False)):
        params = params_teste(modelo_oficial=oficial)
        meta = treino._metadados("3", ["a"], res, {}, params, [], "2026-11-03T09:00:00-03:00", bloco, None)
        assert meta["provisorio"] is provisorio
        assert meta["aviso"] == (treino.AVISO_PROVISORIO if provisorio else None)


def test_sem_linhas_antes_do_mes_levanta_pre_requisito(tmp_path, completo):
    params = params_teste(teste_final_fim=date(2026, 10, 30))
    df = _apagar_alvo(_ate(completo, "2026-10-30"), "2026-10-30")
    pasta = _pasta_dev(tmp_path, params=params)
    with pytest.raises(treino.ErroPreRequisito, match="nenhuma linha de treino antes de 2026-08-01"):
        retreino.retreinar_mes(df, INFO, _cal(df), date(2026, 8, 1), pasta_modelos=pasta, params=params, agora=AGORA)


def test_queda_na_gravacao_pede_retreino_do_par_inteiro(tmp_path):
    """Falta o `.meta.json` do modelo 3 (ou o par do modelo 1) -> precisa retreinar, mesmo com o `.json` do 3."""
    pasta = tmp_path / "modelos"
    pasta.mkdir()
    fim = date(2026, 10, 30)
    arquivos = ["xgb-2026-11.json", "xgb-2026-11.meta.json", "xgb-m1-2026-11.json", "xgb-m1-2026-11.meta.json"]

    assert retreino.precisa_retreinar(pasta, D1, fim) is True
    for nome in arquivos:
        (pasta / nome).write_text("{}", encoding="utf-8")
        falta = [outro for outro in arquivos if not (pasta / outro).exists()]
        assert retreino.precisa_retreinar(pasta, D1, fim) is bool(falta)
    assert retreino.precisa_retreinar(pasta, D1, fim) is False

    (pasta / "xgb-2026-11.meta.json").unlink()
    assert retreino.precisa_retreinar(pasta, D1, fim) is True
    (pasta / "xgb-2026-11.meta.json").write_text("{}", encoding="utf-8")
    (pasta / "xgb-m1-2026-11.meta.json").unlink()
    assert retreino.precisa_retreinar(pasta, D1, fim) is True
