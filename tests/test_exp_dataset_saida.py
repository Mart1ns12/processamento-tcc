"""Testes da gravação e da linha de comando do dataset do experimento (etapa 5, fase 9).

`salvar_dataset` e `executar` rodam sobre fixtures pequenas (SQLite de tests/dados, `tmp_path`).
Nenhum teste usa rede. O teste de banco real (`@pytest.mark.banco`) só lê e só roda com
`PROC_TESTES_COM_BANCO=1 pytest -q -m banco`.
"""

import hashlib
import json
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from processamento import calendario, fontes
from processamento.experimento.dataset import AVISO_SMLL_AUSENTE, COLUNAS_DATASET, executar, main, salvar_dataset


def _df_pequeno() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2026-05-05", "2026-05-04", "2026-05-05"]),
            "ticker": ["AAAA3", "AAAA3", "BBBB3"],
            "valor": [0.1 + 0.2, np.nan, -3.5],
            "alvo": [1.0, 0.0, np.nan],
        }
    )


def _info_pequeno() -> dict:
    return {"versao_noticias": "todas", "linhas": 3, "pregoes": 2, "cobertura_inicio": None,
            "parametros": {"experimento": {"papeis": ("protagonista",)}}}


def test_salvar_nome_com_ultima_data_e_csv_relido_igual(tmp_path):
    df = _df_pequeno()
    csv = salvar_dataset(df, _info_pequeno(), tmp_path)
    assert csv == tmp_path / "dataset-todas-2026-05-05.csv"
    lido = pd.read_csv(csv, dtype={"ticker": str}, parse_dates=["data"])
    assert_frame_equal(lido, df, check_dtype=False)
    texto = csv.read_text(encoding="utf-8")
    assert texto.splitlines()[0] == "data,ticker,valor,alvo"
    assert "2026-05-04" in texto


def test_json_traz_info_sha_e_horario_de_sao_paulo(tmp_path):
    csv = salvar_dataset(_df_pequeno(), _info_pequeno(), tmp_path)
    registro = json.loads((tmp_path / "dataset-todas-2026-05-05.json").read_text(encoding="utf-8"))
    assert registro["sha256"] == hashlib.sha256(csv.read_bytes()).hexdigest()
    assert registro["arquivo"] == csv.name
    assert registro["linhas"] == 3 and registro["pregoes"] == 2
    assert registro["parametros"]["experimento"]["papeis"] == ["protagonista"]
    gerado = datetime.fromisoformat(registro["gerado_em"])
    assert gerado.utcoffset() == timedelta(hours=-3)


def test_json_converte_tipos_do_numpy(tmp_path):
    info = {**_info_pequeno(), "linhas": np.int64(3), "noticias_dia_qtd": np.int64(0),
            "sem_data": np.bool_(False)}
    salvar_dataset(_df_pequeno(), info, tmp_path)
    registro = json.loads((tmp_path / "dataset-todas-2026-05-05.json").read_text(encoding="utf-8"))
    assert registro["linhas"] == 3 and isinstance(registro["linhas"], int)
    assert registro["sem_data"] is False


def test_salvar_dataset_vazio_levanta(tmp_path):
    with pytest.raises(ValueError, match="vazio"):
        salvar_dataset(_df_pequeno().iloc[0:0], _info_pequeno(), tmp_path)


def test_executar_versao_desconhecida_levanta_sem_ler_o_banco(tmp_path):
    with pytest.raises(ValueError, match="versão"):
        executar("xpto", None, None, tmp_path)


def test_executar_grava_csv_e_json_do_banco_de_teste(banco_teste, tmp_path):
    ler = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler))
    csv = executar("todas", None, None, tmp_path, ler=ler, existe_composicao=False)

    assert csv == tmp_path / f"dataset-todas-{cal[-1].isoformat()}.csv"
    df = pd.read_csv(csv, dtype={"ticker": str, "empresa": str, "setor": str}, parse_dates=["data"])
    assert list(df.columns) == COLUNAS_DATASET
    assert not df.duplicated(["data", "ticker"]).any()
    assert df["data"].max().date() == cal[-1]

    registro = json.loads(csv.with_suffix(".json").read_text(encoding="utf-8"))
    assert registro["pregoes"] == len(cal)
    assert registro["sha256"] == hashlib.sha256(csv.read_bytes()).hexdigest()
    assert registro["parametros"]["experimento"]["retornos"] == {"ret_1d": 1, "ret_5d": 5, "ret_20d": 20}
    assert "setor_excluir" in registro["parametros"]["precos"]
    assert registro["sem_probabilidade"] == 0


def test_executar_conta_sem_probabilidade_no_json(banco_teste, tmp_path):
    # Sem probabilidade do FinBERT em todas as notícias: o JSON traz as preparadas como sem probabilidade
    ler = banco_teste(alterar={"v1-noticias": lambda df: df.assign(prob_positivo=None)})
    csv = executar("todas", None, None, tmp_path, ler=ler, existe_composicao=False)
    registro = json.loads(csv.with_suffix(".json").read_text(encoding="utf-8"))
    assert registro["preparadas"] > 0
    assert registro["sem_probabilidade"] == registro["preparadas"]


def test_executar_sem_tabela_de_indices_para_com_erro_legivel(banco_teste, tmp_path):
    ler = banco_teste(omitir=frozenset({"v1-indices"}))
    with pytest.raises(fontes.ErroLeitura, match="v1-indices"):
        executar("todas", None, None, tmp_path, ler=ler, existe_composicao=False)


def test_executar_sem_smll_na_tabela_grava_coluna_vazia_e_avisa(banco_teste, tmp_path, capsys):
    ler = banco_teste()   # tests/dados/indices.csv não tem SMLL
    csv = executar("todas", None, None, tmp_path, ler=ler, existe_composicao=False)
    df = pd.read_csv(csv, dtype={"ticker": str, "empresa": str, "setor": str}, parse_dates=["data"])
    assert df["exposicao_small"].isna().all()
    registro = json.loads(csv.with_suffix(".json").read_text(encoding="utf-8"))
    assert registro["smll_pregoes"] == 0
    assert AVISO_SMLL_AUSENTE in capsys.readouterr().out


def test_executar_ate_corta_os_pregoes(banco_teste, tmp_path):
    ler = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler))
    ate = cal[1]
    csv = executar("todas", ate, None, tmp_path, ler=ler, existe_composicao=False)
    assert csv.name == f"dataset-todas-{ate.isoformat()}.csv"
    registro = json.loads(csv.with_suffix(".json").read_text(encoding="utf-8"))
    assert registro["pregoes"] == 2


def test_executar_com_proximo_roda_e_grava_ate_o_ultimo_pregao(banco_teste, tmp_path):
    ler = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler))
    csv = executar("todas", cal[2], cal[3], tmp_path, ler=ler, existe_composicao=False)
    assert csv.name == f"dataset-todas-{cal[2].isoformat()}.csv"
    registro = json.loads(csv.with_suffix(".json").read_text(encoding="utf-8"))
    assert registro["pregoes"] == 3


def test_proximo_nao_pode_ser_o_ultimo_pregao(banco_teste, tmp_path):
    ler = banco_teste()
    cal = calendario.pregoes(fontes.ler_tabela("precos", ler=ler))
    with pytest.raises(ValueError, match="--proximo"):
        executar("todas", None, cal[-1], tmp_path, ler=ler, existe_composicao=False)


def test_main_recusa_data_invalida_e_versao_desconhecida(capsys):
    with pytest.raises(SystemExit) as erro:
        main(["--ate", "2026-13-01", "--pasta", "x"], ler=lambda sql, params=None: None)
    assert erro.value.code == 2
    with pytest.raises(SystemExit) as erro:
        main(["--versao", "xpto"], ler=lambda sql, params=None: None)
    assert erro.value.code == 2


@pytest.mark.banco
def test_dataset_do_banco_real_so_leitura(tmp_path):
    """Só lê o banco: confere colunas, chave, alvo e a abertura do IBOV contra o fechamento anterior."""
    engine = fontes.criar_engine()

    def ler(sql, params=None):
        return fontes.executar_leitura(sql, params, engine=engine)

    fontes.verificar_sessao_somente_leitura(ler)
    csv = executar("todas", None, None, tmp_path, ler=ler)
    df = pd.read_csv(csv, dtype={"ticker": str, "empresa": str, "setor": str}, parse_dates=["data"])

    assert list(df.columns) == COLUNAS_DATASET
    assert not df.duplicated(["data", "ticker"]).any()
    assert df["alvo"].dropna().isin([0, 1]).all()

    precos = fontes.ler_tabela("precos", ler=ler)
    ibov = precos.loc[precos["ticker"] == "IBOV", ["data", "abertura", "fechamento"]].sort_values("data")
    ibov["fech_ant"] = ibov["fechamento"].shift(1)
    validos = ibov.dropna(subset=["abertura", "fech_ant"])
    assert len(validos) > 0
    pct = float(np.isclose(validos["abertura"], validos["fech_ant"], rtol=0, atol=1e-9).mean())
    print(f"\nIBOV: abertura = fechamento do pregão anterior em {pct:.1%} dos pregões ({len(validos)} pares)")
    assert 0 <= pct <= 1


def test_executar_sem_tabela_de_documentos_para_com_erro_legivel(banco_teste, tmp_path):
    ler = banco_teste(omitir=frozenset({"v1-raw_ipe_docs"}))
    with pytest.raises(fontes.ErroLeitura, match="v1-raw_ipe_docs"):
        executar("todas", None, None, tmp_path, ler=ler, existe_composicao=False)


def _abev3_com_preco_em_21(df):
    """Em tests/dados/precos.csv a ABEV3 está sem ajustado em 21/10 (fora do universo); estes testes precisam da linha."""
    df = df.copy()
    df.loc[(df["ticker"] == "ABEV3") & (df["data"].astype(str).str[:10] == "2025-10-21"), "fechamento_ajustado"] = "10.00"
    return df


def test_executar_grava_as_colunas_novas(banco_teste, tmp_path):
    ler = banco_teste(alterar={"v1-precos": _abev3_com_preco_em_21})
    csv = executar("todas", date(2025, 10, 21), date(2025, 10, 22), tmp_path, ler=ler, existe_composicao=False)
    df = pd.read_csv(csv, dtype={"ticker": str, "empresa": str, "setor": str}, parse_dates=["data"])

    def linha(dia, ticker):
        return df[(df["data"] == pd.Timestamp(dia)) & (df["ticker"] == ticker)].iloc[0]

    assert linha("2025-10-20", "PETR4")["fato_relevante_cvm"] == 1   # IPE0002
    assert linha("2025-10-21", "PETR4")["fato_relevante_cvm"] == 0   # IPE0003 é reapresentação
    assert linha("2025-10-21", "ABEV3")["fato_relevante_cvm"] == 0   # IPE0004 é outra categoria
    assert linha("2025-10-21", "PETR4")["dy_12m"] == pytest.approx(0.05, abs=1e-12)    # 0,70 em 21/10/2024 fica fora
    assert linha("2025-10-20", "PETR4")["dy_12m"] == pytest.approx(0.12, abs=1e-12)    # ainda dentro
    assert linha("2025-10-21", "ABEV3")["dy_12m"] == 0.0                               # D8
    assert linha("2025-10-21", "TAEE11")["dy_12m"] == pytest.approx(0.09, abs=1e-12)
    assert pd.isna(linha("2025-10-21", "PETR4")["var_lucro_aa"])          # sem o 2º tri de 2024
    assert pd.isna(linha("2025-10-21", "PETR4")["dias_desde_resultado"])  # última entrega antes do 1º pregão do calendário
    assert df["controle_sorteado"].between(0, 1, inclusive="left").all()
    registro = json.loads(csv.with_suffix(".json").read_text(encoding="utf-8"))
    assert registro["cvm_cobertura_inicio"] == "2024-03-01"
    assert registro["pregoes_sem_coleta_cvm"] == 0
    assert registro["semente_controle"] == 20261023
    assert registro["parametros"]["fundamentos"]["meses_janela"] == 12
