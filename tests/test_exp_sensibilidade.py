"""Análises de sensibilidade (processamento/experimento/sensibilidade.py): funções puras e dados sintéticos.

Sem banco, sem CSV real e sem treino de verdade: `prever` entra como dublê onde precisa.
"""

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from processamento.experimento import preparacao, sensibilidade as sens, treino

PARAMS = SimpleNamespace(topk=(5, 3), acaso_sorteios=30, semente=7)


def _pred(dias: dict) -> pd.DataFrame:
    """Previsões sintéticas: `dias` mapeia data -> lista de alvos (0 ou 1), um papel por alvo."""
    linhas = []
    for data, alvos in dias.items():
        for i, alvo in enumerate(alvos):
            linhas.append({
                "data": pd.Timestamp(data), "ticker": f"T{i:02d}3", "score": i / 10, "alvo": alvo,
                "alvo_abertura": alvo, "alvo_abertura_valido": 1, "ret_t1": 0.01, "ret_ibov_t1": 0.0,
                "dia_resultado": True,
            })
    return pd.DataFrame(linhas)


def _df_precos() -> pd.DataFrame:
    """Dataset bruto mínimo: as colunas de preço e alvo, com um NaN para checar a igualdade de ausentes."""
    colunas = preparacao.COLUNAS_PRECO + preparacao.COLUNAS_ALVO
    df = pd.DataFrame({c: [1.0, np.nan] for c in colunas})
    df["data"] = pd.to_datetime(["2025-01-02", "2025-01-02"])
    df["ticker"] = ["AAAA3", "BBBB3"]
    return df


def test_recorte_usa_qtd_bruta_e_nan_nao_conta_como_zero():
    df = pd.DataFrame({"noticias_dia_qtd": [0, 1, np.nan, 3]})
    assert list(sens.recorte_com_noticia(df)["noticias_dia_qtd"]) == [1, 3]


def test_dia_com_4_papeis_sai_e_com_5_fica_e_perda_conta_por_ano():
    pred = _pred({"2025-01-02": [1, 0, 1, 0], "2025-01-03": [1, 0, 1, 0, 1]})
    dias, perdidos = sens.dias_validos(pred)
    assert dias == [pd.Timestamp("2025-01-03")]
    assert perdidos == {2025: 1}


def test_dia_sem_as_duas_classes_de_alvo_sai():
    pred = _pred({"2025-01-02": [1, 1, 1, 1, 1], "2025-01-03": [0, 1, 0, 1, 0]})
    dias, perdidos = sens.dias_validos(pred)
    assert dias == [pd.Timestamp("2025-01-03")]
    assert perdidos == {2025: 1}


def test_n_dias_do_acaso_e_os_dias_do_recorte():
    pred = _pred({
        "2025-01-02": [1, 0, 1, 0, 1],
        "2025-01-03": [1, 0, 0, 0],        # 4 papéis: sai
        "2025-01-06": [0, 1, 0, 1, 1],
    })
    dias, perdidos = sens.dias_validos(pred)
    recorte = sens._so_dias(pred, dias)
    acaso = treino.calcular_acaso(recorte, PARAMS)
    assert perdidos == {2025: 1}
    assert len(dias) == 2
    assert acaso["5"]["n_dias"] == len(dias)


def test_precos_diferentes_levantam_erro():
    base = _df_precos()
    outra = _df_precos()
    outra["ret_1d"] = [0.03, np.nan]
    with pytest.raises(sens.ErroSensibilidade, match="ret_1d"):
        sens.conferir_precos_iguais(base, outra, "principais")


def test_precos_iguais_inclusive_ausentes_passam():
    base = _df_precos()
    sens.conferir_precos_iguais(base, base.copy(), "principais")


def test_analise_d_usa_exatamente_noticias_dia():
    chamadas = []

    def prever_falso(prep, dobras, colunas, tipo, params, hiper=None):
        chamadas.append((list(colunas), tipo, hiper))
        return _pred({"2025-01-02": [1, 0, 1, 0, 1]})

    sens._previsao_noticias(None, [], PARAMS, prever_falso)
    assert chamadas == [(list(preparacao.NOTICIAS_DIA), "logistica", None)]


def test_relatorio_nao_sobrescreve(tmp_path):
    (tmp_path / f"{sens.NOME_SAIDA}.md").write_text("antigo", encoding="utf-8")
    with pytest.raises(sens.ErroSensibilidade, match="já existe"):
        sens.gravar_saidas(tmp_path, "novo", {"x": 1})
    assert (tmp_path / f"{sens.NOME_SAIDA}.md").read_text(encoding="utf-8") == "antigo"
    assert not (tmp_path / f"{sens.NOME_SAIDA}.json").exists()


def test_relatorio_novo_grava_md_e_json(tmp_path):
    caminho_md, caminho_json = sens.gravar_saidas(tmp_path, "texto", {"modelo_oficial": False, "x": np.float64(0.5)})
    assert caminho_md.read_text(encoding="utf-8") == "texto"
    assert json.loads(caminho_json.read_text(encoding="utf-8")) == {"modelo_oficial": False, "x": 0.5}
