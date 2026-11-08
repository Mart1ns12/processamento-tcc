"""Medida de dados novos (processamento/experimento/medida_dados_novos.py): funções puras com dados sintéticos,
gravação e uma ponta-a-ponta com dois CSV em tmp_path. Sem banco, sem CSV real."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento.experimento import medida_dados_novos as md, preparacao

COLUNAS = ["ret_1d", "ret_5d", "noticias_dia_tom", "noticias_dia_extremo", "mudanca_tom", "alvo"]
GRUPOS = ["preco_bloco_a", "noticias", "alvo", "preco_e_alvo"]
DATA = "2025-03-03"


def _df(n: int = 200) -> pd.DataFrame:
    """Linhas preparadas sintéticas: um pregão, um ticker por linha (T0000, T0001, ...), alvo 0 ou 1 alternado."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame({c: rng.normal(0, 1, n) for c in COLUNAS if c != "alvo"})
    df["alvo"] = (np.arange(n) % 2).astype(float)
    df.insert(0, "ticker", [f"T{i:04d}" for i in range(n)])
    df.insert(0, "data", pd.Timestamp(DATA))
    return df


def _com(df: pd.DataFrame, linha: int, coluna: str, valor) -> pd.DataFrame:
    """Cópia de `df` com uma célula trocada (o índice é o padrão, 0..n-1)."""
    saida = df.copy()
    saida.loc[linha, coluna] = valor
    return saida


def _somar(df: pd.DataFrame, linhas: list[int], coluna: str, delta: float = 1.0) -> pd.DataFrame:
    """Cópia de `df` com `delta` somado a `coluna` nas `linhas` dadas."""
    saida = df.copy()
    for i in linhas:
        saida.loc[i, coluna] = saida.loc[i, coluna] + delta
    return saida


def test_iguais_nao_mudam_nada():
    res = md.medir(_df(), _df(), COLUNAS)
    assert res["fracao_total"] == 0
    assert res["linhas_mudadas"] == 0
    assert res["decisao"] == "rodada_oficial_continua"
    assert res["parar_e_perguntar"] is False
    assert res["denominador"] == 200


@pytest.mark.parametrize("delta, esperado", [(2e-6, 1), (5e-7, 0), (1e-6, 0)])
def test_diferenca_em_ret_1d_so_conta_acima_de_1e6(delta, esperado):
    base = _df()
    novo = _com(base, 5, "ret_1d", base.loc[5, "ret_1d"] + delta)
    res = md.medir(base, novo, COLUNAS)
    assert res["linhas_mudadas"] == esperado
    assert res["grupos"]["preco_bloco_a"]["linhas_mudadas"] == esperado


def test_vazio_para_valor_em_noticia_conta_no_grupo_noticias():
    base = _df()
    base.loc[3, "noticias_dia_tom"] = np.nan
    novo = _com(base, 3, "noticias_dia_tom", 0.5)
    res = md.medir(base, novo, COLUNAS)
    assert res["grupos"]["noticias"]["linhas_mudadas"] == 1
    assert res["grupos"]["preco_bloco_a"]["linhas_mudadas"] == 0
    assert res["linhas_mudadas"] == 1


def test_linha_so_no_novo_conta_no_total_e_em_todos_os_grupos():
    base = _df()
    extra = base.iloc[[0]].copy()
    extra["ticker"] = "T9999"
    novo = pd.concat([base, extra], ignore_index=True)
    res = md.medir(base, novo, COLUNAS)
    assert res["linhas_mudadas"] == 1
    assert all(res["grupos"][g]["linhas_mudadas"] == 1 for g in GRUPOS)
    assert res["contagens"]["so_novo"] == 1 and res["contagens"]["so_congelado"] == 0
    assert res["denominador"] == 200


def test_linha_so_no_congelado_conta_no_total_e_em_todos_os_grupos():
    base = _df()
    extra = base.iloc[[0]].copy()
    extra["ticker"] = "T9999"
    congelado = pd.concat([base, extra], ignore_index=True)
    res = md.medir(congelado, base, COLUNAS)
    assert res["linhas_mudadas"] == 1
    assert all(res["grupos"][g]["linhas_mudadas"] == 1 for g in GRUPOS)
    assert res["contagens"]["so_congelado"] == 1 and res["contagens"]["so_novo"] == 0
    assert res["denominador"] == 201


def test_linha_sem_alvo_no_congelado_fica_fora_do_denominador_mas_entra_se_mudar():
    base = _df()
    base.loc[7, "alvo"] = np.nan
    assert md.medir(base, base.copy(), COLUNAS)["denominador"] == 199
    res = md.medir(base, _com(base, 7, "alvo", 1.0), COLUNAS)
    assert res["denominador"] == 199
    assert res["linhas_mudadas"] == 1
    assert res["grupos"]["alvo"]["linhas_mudadas"] == 1
    assert res["fracao_total"] == pytest.approx(1 / 199)


def test_um_por_cento_exato_nao_passa():
    base = _df(200)
    res = md.medir(base, _somar(base, [0, 1], "ret_5d"), COLUNAS)
    assert res["denominador"] == 200 and res["linhas_mudadas"] == 2
    assert res["fracao_total"] == 0.01
    assert res["decisao"] == "rodada_oficial_continua"


def test_acima_de_um_por_cento_vira_nova_rodada():
    base = _df(200)
    res = md.medir(base, _somar(base, [0, 1, 2], "ret_5d"), COLUNAS)
    assert res["linhas_mudadas"] == 3
    assert res["decisao"] == "nova_rodada"


def test_preco_e_alvo_acima_de_um_por_cento_pede_parar_mesmo_com_total_acima():
    base = _df(200)
    novo = _somar(base, [0, 1], "ret_1d")
    novo.loc[2, "alvo"] = 1 - novo.loc[2, "alvo"]
    res = md.medir(base, novo, COLUNAS)
    assert res["linhas_mudadas"] == 3
    assert res["grupos"]["alvo"]["linhas_mudadas"] == 1
    assert res["grupos"]["preco_e_alvo"]["linhas_mudadas"] == 3
    assert res["decisao"] == "nova_rodada"
    assert res["parar_e_perguntar"] is True


def test_alvo_sozinho_nao_pede_parar():
    base = _df(200)
    novo = base.copy()
    novo.loc[2, "alvo"] = 1 - novo.loc[2, "alvo"]
    res = md.medir(base, novo, COLUNAS)
    assert res["grupos"]["alvo"]["linhas_mudadas"] == 1
    assert res["grupos"]["preco_e_alvo"]["linhas_mudadas"] == 1
    assert res["decisao"] == "rodada_oficial_continua"
    assert res["parar_e_perguntar"] is False


def test_colunas_comparadas_sao_colunas_3_mais_alvo_e_extremo_como_rank_quando_congelado():
    congelado = {"colunas_3": ["ret_1d", "noticias_dia_extremo"], "extremo_em_rank": False}
    assert md.colunas_comparadas(congelado) == ["ret_1d", "noticias_dia_extremo", "alvo"]
    congelado["extremo_em_rank"] = True
    assert md.colunas_comparadas(congelado) == ["ret_1d", preparacao.EXTREMO_RANK, "alvo"]


def test_segunda_gravacao_da_mesma_data_da_erro_e_nao_grava_nada(tmp_path):
    data = date(2026, 11, 8)
    md.gravar_saidas(tmp_path, "primeiro", {"x": 1}, data)
    with pytest.raises(md.ErroMedida, match="já existe"):
        md.gravar_saidas(tmp_path, "segundo", {"x": 2}, data)
    assert (tmp_path / "medida_dados_novos_2026-11-08.md").read_text(encoding="utf-8") == "primeiro"
    assert json.loads((tmp_path / "medida_dados_novos_2026-11-08.json").read_text(encoding="utf-8")) == {"x": 1}


def test_se_so_o_json_existe_nada_novo_e_gravado(tmp_path):
    (tmp_path / "medida_dados_novos_2026-11-08.json").write_text("{}", encoding="utf-8")
    with pytest.raises(md.ErroMedida, match="já existe"):
        md.gravar_saidas(tmp_path, "texto", {"x": 1}, date(2026, 11, 8))
    assert not (tmp_path / "medida_dados_novos_2026-11-08.md").exists()


def test_ponta_a_ponta_com_dois_csv_e_uma_alteracao_conhecida(tmp_path):
    base = dataset_sintetico()
    csv_congelado = gravar_versoes(tmp_path / "congelado", base, versoes=("todas",))["todas"]
    alterado = base.copy()
    alterado.loc[0, "mudanca_tom"] = alterado.loc[0, "mudanca_tom"] + 1.0   # linha 0: primeiro pregão, no desenvolvimento
    csv_novo = gravar_versoes(tmp_path / "novo", alterado, versoes=("todas",))["todas"]

    sha_congelado = json.loads(csv_congelado.with_suffix(".json").read_text(encoding="utf-8"))["sha256"]
    protocolo = tmp_path / "protocolo_congelado_teste.json"
    protocolo.write_text(json.dumps({
        "rodada": 3,
        "sha256_dataset": sha_congelado,
        "colunas_3": ["ret_1d", "ret_5d", "noticias_dia_tom", "noticias_dia_extremo", "mudanca_tom"],
        "extremo_em_rank": False,
    }), encoding="utf-8")

    caminho_md, caminho_json = md.executar(csv_congelado, csv_novo, protocolo, tmp_path / "docs",
                                           data=date(2026, 11, 8), params=params_teste())
    res = json.loads(caminho_json.read_text(encoding="utf-8"))
    assert res["linhas_mudadas"] == 1
    assert res["grupos"]["noticias"]["linhas_mudadas"] == 1
    assert res["grupos"]["preco_bloco_a"]["linhas_mudadas"] == 0
    assert res["contagens"]["so_novo"] == 0 and res["contagens"]["so_congelado"] == 0
    assert res["decisao"] == "rodada_oficial_continua"
    assert res["parar_e_perguntar"] is False
    assert res["congelado"]["sha256"] == sha_congelado
    texto = caminho_md.read_text(encoding="utf-8")
    assert texto.startswith("# Medida de dados novos (D5 esclarecida)")
    assert "Não constitui recomendação de investimento." in texto
