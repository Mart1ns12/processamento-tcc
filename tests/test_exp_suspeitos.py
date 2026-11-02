"""Retorno diário suspeito no experimento (seção 6, "Retorno diário suspeito"): variáveis, alvo e fechamento do top.

Variáveis de preco (`variaveis_de_preco`), alvo (`alvos`) e `fechar_dia` leem a mesma máscara de suspeitos
(fora de [−75%, +100%], limites estritos). Dados escritos à mão com `fabrica_precos`; nenhum teste usa banco,
rede ou pasta real. Modelos: tests/test_beta_vol_suspeitos.py (V5) e tests/test_exp_alvo.py.
"""

from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import precos_de, pregoes_uteis, serie_por_retornos
from processamento.experimento.alvo import alvos
from processamento.experimento.parametros import ParametrosExperimento
from processamento.experimento.variaveis import variaveis_de_preco
from processamento.fatos import precos as fatos_precos
from processamento.fatos.precos import ParametrosPrecos, carregar_parametros_precos
from processamento.saida import pacotes_experimento as pe

SP = ZoneInfo("America/Sao_Paulo")

# ---------------------------------------------------------------- mundo das variáveis (50 pregões)

CAL50 = pregoes_uteis(50, "2025-01-02")
S = 25                                   # posição do pregão suspeito de AAAA3 (retorno de S−1 para S)
TICKERS = ["AAAA3", "BBBB3", "CCCC3"]    # mesmo setor S1, CNPJs diferentes
SETOR_DE = {"AAAA3": "S1", "BBBB3": "S1", "CCCC3": "S1"}
CNPJ_DE = {"AAAA3": "1", "BBBB3": "2", "CCCC3": "3"}


def _params_exp() -> ParametrosExperimento:
    """Parâmetros do experimento como em test_beta_vol_suspeitos (V5), com retornos 1/5/20 e extremos 10/5."""
    base = ParametrosExperimento(
        retornos={"ret_1d": 1, "ret_5d": 5, "ret_20d": 20},
        exposicao_pregoes=120,
        exposicao_minimo=60,
        extremos_pregoes=252,
        extremos_minimo=120,
        mudanca_tom_pregoes=30,
        mudanca_tom_minimo=5,
        sem_horario_na_noite=True,
        inicio_janela="manha",
        deduplicar_titulo=True,
        deduplicar_entre_origens=True,
        janela_dias_entre_origens=1,
        titulo_palavras_min_entre_origens=5,
        origens_principais=("cvm_ipe",),
        tipos_principais=("reportagem",),
        papeis_principais=("protagonista", "citada_com_fato"),
    )
    return replace(base, retornos={"ret_1d": 1, "ret_5d": 5, "ret_20d": 20}, extremos_pregoes=10, extremos_minimo=5)


def _params_precos() -> ParametrosPrecos:
    return ParametrosPrecos(
        janelas={"d1": 1}, volume_pregoes=20, volatilidade_retornos=20, beta_pregoes=252,
        beta_minimo=120, setor_minimo=3, setor_excluir="empresa",
    )


def _mundo(alta: float = 1.5):
    """Três ações com retornos pequenos e conhecidos; AAAA3 tem retorno `alta` no pregão S (+150% por padrão).

    Devolve (preços, retornos por ticker). `rets[t][i]` é o retorno que entra na posição i+1 do calendário.
    """
    rng = np.random.default_rng(25)
    rets = {t: rng.normal(0, 0.01, 49).tolist() for t in TICKERS}
    rets["AAAA3"][S - 1] = alta
    precos = pd.concat([
        precos_de("AAAA3", CAL50, serie_por_retornos(100.0, rets["AAAA3"])),
        precos_de("BBBB3", CAL50, serie_por_retornos(50.0, rets["BBBB3"])),
        precos_de("CCCC3", CAL50, serie_por_retornos(70.0, rets["CCCC3"])),
        precos_de("IBOV", CAL50, serie_por_retornos(1000.0, rng.normal(0, 0.01, 49).tolist())),
        precos_de("USDBRL", CAL50, serie_por_retornos(5.0, rng.normal(0, 0.005, 49).tolist())),
        precos_de("BRENT", CAL50, serie_por_retornos(70.0, rng.normal(0, 0.01, 49).tolist())),
    ], ignore_index=True)
    return precos, rets


def _variaveis(precos: pd.DataFrame) -> dict[str, pd.DataFrame]:
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(CAL50), columns=TICKERS)
    return variaveis_de_preco(precos, CAL50, TICKERS, mascara, SETOR_DE, CNPJ_DE, _params_exp(), _params_precos())


def _posicoes_nan(serie: pd.Series, aquecimento: int) -> list[int]:
    """Posições com NaN a partir de `aquecimento` (antes disso é o começo da janela, que não conta)."""
    return [p for p in range(aquecimento, len(serie)) if pd.isna(serie.iloc[p])]


# ---------------------------------------------------------------- 1 a 5: variáveis da ação suspeita

def test_ret_1d_so_some_no_pregao_suspeito():
    ret = _variaveis(_mundo()[0])["ret_1d"]["AAAA3"]
    assert _posicoes_nan(ret, 1) == [S]
    assert np.isfinite(ret.iloc[S - 1]) and np.isfinite(ret.iloc[S + 1])


def test_ret_5d_some_nas_cinco_janelas_que_contem_o_suspeito():
    ret = _variaveis(_mundo()[0])["ret_5d"]["AAAA3"]
    assert _posicoes_nan(ret, 5) == list(range(S, S + 5))      # 25..29
    assert np.isfinite(ret.iloc[S - 1]) and np.isfinite(ret.iloc[S + 5])   # 24 e 30


def test_ret_20d_some_nas_vinte_janelas_que_contem_o_suspeito():
    ret = _variaveis(_mundo()[0])["ret_20d"]["AAAA3"]
    assert _posicoes_nan(ret, 20) == list(range(S, S + 20))    # 25..44
    assert np.isfinite(ret.iloc[S - 1]) and np.isfinite(ret.iloc[S + 20])  # 24 e 45


def test_salto_abertura_some_so_no_pregao_suspeito():
    salto = _variaveis(_mundo()[0])["salto_abertura"]["AAAA3"]
    assert _posicoes_nan(salto, 1) == [S]
    assert np.isfinite(salto.iloc[S - 1]) and np.isfinite(salto.iloc[S + 1])   # 24 e 26


@pytest.mark.parametrize("nome", ["dist_max_52s", "dist_min_52s"])
def test_distancias_52s_somem_em_n_menos_1_pregoes(nome):
    serie = _variaveis(_mundo()[0])[nome]["AAAA3"]
    # janela de 10 com mínimo de 5: a primeira posição com valor é a 4
    assert _posicoes_nan(serie, 4) == list(range(S, S + 9))    # 25..33 (n−1 = 9 pregões)
    assert np.isfinite(serie.iloc[S - 1]) and np.isfinite(serie.iloc[S + 9])   # 24 e 34


# ---------------------------------------------------------------- 6: ret_vs_setor sem o suspeito

def test_ret_vs_setor_tira_a_acao_suspeita_da_media():
    precos, rets = _mundo()
    rvs = _variaveis(precos)["ret_vs_setor"]

    assert np.isnan(rvs["AAAA3"].iloc[S])
    # no pregão S, a média do setor (modo empresa) fica só com a outra empresa: AAAA3 é NaN e sai
    assert rvs["BBBB3"].iloc[S] == pytest.approx(rets["BBBB3"][S - 1] - rets["CCCC3"][S - 1], rel=1e-12, abs=1e-15)
    assert rvs["CCCC3"].iloc[S] == pytest.approx(rets["CCCC3"][S - 1] - rets["BBBB3"][S - 1], rel=1e-12, abs=1e-15)


def test_ret_vs_setor_antes_do_suspeito_tem_as_tres_empresas():
    precos, rets = _mundo()
    rvs = _variaveis(precos)["ret_vs_setor"]
    media_outras = np.mean([rets["AAAA3"][S - 2], rets["CCCC3"][S - 2]])   # pregão S−1: AAAA3 e CCCC3
    assert rvs["BBBB3"].iloc[S - 1] == pytest.approx(rets["BBBB3"][S - 2] - media_outras, rel=1e-12, abs=1e-15)


# ---------------------------------------------------------------- 7: as outras ações não perdem valor

@pytest.mark.parametrize("nome, aquecimento", [
    ("ret_1d", 1), ("ret_5d", 5), ("ret_20d", 20), ("salto_abertura", 1), ("dist_max_52s", 4), ("dist_min_52s", 4),
])
def test_outras_acoes_nao_ganham_nan_com_o_suspeito_de_aaaa3(nome, aquecimento):
    res = _variaveis(_mundo()[0])
    for ticker in ["BBBB3", "CCCC3"]:
        assert _posicoes_nan(res[nome][ticker], aquecimento) == []


# ---------------------------------------------------------------- 8: limite exato não é suspeito

def test_retorno_de_exatamente_100_por_cento_nao_e_suspeito():
    precos, _ = _mundo(alta=1.0)
    ret = _variaveis(precos)["ret_1d"]["AAAA3"]
    assert ret.iloc[S] == pytest.approx(1.0, rel=1e-12)
    assert _posicoes_nan(ret, 1) == []


# ---------------------------------------------------------------- 9: o preço não é mascarado

def test_variacao_do_painel_continua_com_valor_no_pregao_suspeito():
    precos, _ = _mundo()
    g_aj = fatos_precos.grade_de_precos(precos, CAL50, "fechamento_ajustado", TICKERS)
    var = fatos_precos.variacao(g_aj, 1, _params_precos().base_defasagem_max_pregoes).valor
    assert var["AAAA3"].iloc[S] == pytest.approx(1.5, rel=1e-12)


# ---------------------------------------------------------------- 10 a 14: alvo (t+1 suspeito)

CAL4 = pregoes_uteis(4, "2026-06-18")
D0, D1, D2, D3 = (pd.Timestamp(d) for d in CAL4)


def _precos_alvo() -> pd.DataFrame:
    """AAAA3 sobe 150% em t+1 de D1 (pregão 2); BBBB3 normal; IBOV 1000, 1010, 1020, 1030."""
    return pd.concat([
        precos_de("AAAA3", CAL4, [100, 100, 250, 250]),
        precos_de("BBBB3", CAL4, [100, 101, 102, 103]),
        precos_de("IBOV", CAL4, [1000, 1010, 1020, 1030]),
    ], ignore_index=True)


def test_linha_com_suspeito_em_t1_fica_sem_retorno_alvo_e_alvo_abertura():
    r = alvos(_precos_alvo(), CAL4, ["AAAA3", "BBBB3"])
    assert pd.isna(r["ret_t1"].loc[D1, "AAAA3"])
    assert pd.isna(r["alvo"].loc[D1, "AAAA3"])
    assert pd.isna(r["alvo_abertura"].loc[D1, "AAAA3"])
    assert r["ret_ibov_t1"].loc[D1, "AAAA3"] == pytest.approx(1020 / 1010 - 1, rel=1e-12)   # 0,00990099
    assert r["alvo_abertura_valido"].loc[D1, "AAAA3"] == r["alvo_abertura_valido"].loc[D1, "BBBB3"]
    assert r["alvo_abertura_valido"].loc[D1, "BBBB3"] == 1.0   # abertura do IBOV em D2 ≠ fechamento em D1


def test_linhas_vizinhas_do_suspeito_nao_somem():
    r = alvos(_precos_alvo(), CAL4, ["AAAA3", "BBBB3"])
    # t = D0: t+1 = D1 não é suspeito (o suspeito é D2)
    assert r["ret_t1"].loc[D0, "AAAA3"] == 0.0
    assert r["alvo"].loc[D0, "AAAA3"] == 0.0
    # t = D2: t+1 = D3, retorno 0: a linha não é mascarada, porque olha D3 e não D2
    assert r["ret_t1"].loc[D2, "AAAA3"] == 0.0
    assert r["alvo"].loc[D2, "AAAA3"] == 0.0


def test_outra_acao_sem_nan_nas_linhas_0_a_2_e_nan_no_ultimo():
    r = alvos(_precos_alvo(), CAL4, ["AAAA3", "BBBB3"])
    for chave in ["ret_t1", "alvo", "alvo_abertura"]:
        assert r[chave]["BBBB3"].iloc[:3].notna().all()
        assert pd.isna(r[chave].loc[D3, "BBBB3"])


def test_limite_de_100_por_cento_em_t1_nao_e_suspeito():
    cal2 = pregoes_uteis(2, "2026-06-18")
    precos = pd.concat([
        precos_de("AAAA3", cal2, [100, 200]),
        precos_de("IBOV", cal2, [1000, 1010]),
    ], ignore_index=True)
    r = alvos(precos, cal2, ["AAAA3"])
    t = pd.Timestamp(cal2[0])
    assert r["ret_t1"].loc[t, "AAAA3"] == 1.0
    assert r["alvo"].loc[t, "AAAA3"] == 1.0


def test_params_precos_padrao_igual_a_passar_none():
    precos = _precos_alvo()
    sem_param = alvos(precos, CAL4, ["AAAA3", "BBBB3"])
    com_param = alvos(precos, CAL4, ["AAAA3", "BBBB3"], params_precos=carregar_parametros_precos())
    assert sem_param.keys() == com_param.keys()
    for chave in sem_param:
        pd.testing.assert_frame_equal(sem_param[chave], com_param[chave])


# ---------------------------------------------------------------- 15: fechar_dia com ação suspeita no top

BASE = date(2026, 10, 30)
PREV = date(2026, 11, 3)
CANDIDATOS = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3"]


def _precos_com_salto() -> pd.DataFrame:
    """Pregão previsto PREV: AAAA3 sobe 150% (10 → 25); os outros fecham normalmente, IBOV +1%."""
    datas = [BASE, PREV]
    return pd.concat([
        precos_de("AAAA3", datas, [10, 25]),
        precos_de("BBBB3", datas, [10, 10.05]),
        precos_de("CCCC3", datas, [100, 100.5]),
        precos_de("DDDD3", datas, [10, 10.3]),
        precos_de("EEEE3", datas, [10, 10.2]),
        precos_de("FFFF3", datas, [10, 9.9]),
        precos_de("IBOV", datas, [100, 101]),
    ], ignore_index=True)


def _registro_fechamento() -> dict:
    return {
        "pacote": {
            "data_referencia": "2026-11-03",
            "pregao_previsto": "2026-11-03",
            "pregao_base": "2026-10-30",
            "valido_para_historico": True,
            "ranking": [{"ticker": t} for t in CANDIDATOS[:5]],
        },
        "interno": {
            "candidatos": CANDIDATOS,
            "sombra_modelo_1": None,
            "sombra_volatilidade": CANDIDATOS[:5],
        },
    }


def test_fechar_dia_tira_da_conta_a_acao_com_salto_no_pregao_previsto():
    agora = datetime(2026, 11, 3, 18, 0, tzinfo=SP)
    res = pe.fechar_dia(_registro_fechamento(), _precos_com_salto(), [BASE, PREV], agora)

    por_ticker = {item["ticker"]: item for item in res["resultado"]}
    assert por_ticker["AAAA3"]["retorno"] == pe._folha_retorno(None)
    assert por_ticker["AAAA3"]["retorno"]["valor"] is None
    assert por_ticker["AAAA3"]["superou"] is None
    assert res["resultado_incompleto"] is True
    # sem a máscara, AAAA3 seria 1 (superou o IBOV): com ela, não entra na conta de acertos
    assert res["acertos_dia"] == 2                 # DDDD3 e EEEE3
    assert res["alvos_candidatos"]["AAAA3"] is None

    # os outros tickers fecham normalmente
    assert por_ticker["BBBB3"]["retorno"]["valor"] == pytest.approx(0.005, abs=1e-9)
    assert por_ticker["DDDD3"]["retorno"]["valor"] == pytest.approx(0.03, abs=1e-9)
    assert por_ticker["BBBB3"]["superou"] is False
    assert por_ticker["CCCC3"]["superou"] is False
    assert por_ticker["DDDD3"]["superou"] is True
    assert por_ticker["EEEE3"]["superou"] is True
    assert res["alvos_candidatos"]["DDDD3"] == 1.0
    assert res["alvos_candidatos"]["BBBB3"] == 0.0
