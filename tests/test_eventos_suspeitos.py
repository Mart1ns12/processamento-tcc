"""Eventos conhecidos tratados como retorno suspeito (seção 6, "Retorno diário suspeito"; fase1.eventos_retorno_suspeito).

Grade de exemplo com pregões seguidos e tickers A e B; a máscara é a mesma do painel, do experimento e do diagnóstico.
Dados escritos à mão com `fabrica_precos`. Nenhum teste usa banco, rede ou pasta real.
"""

from dataclasses import asdict, replace
from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

import test_exp_suspeitos as sus
from fabrica_precos import cadastro_de, precos_de, pregoes_uteis
from processamento import calendario
from processamento.exclusoes import carregar_exclusoes
from processamento.experimento.alvo import alvos
from processamento.experimento.variaveis import variaveis_de_preco
from processamento.fatos import precos as fatos_precos
from processamento.fatos.precos import (
    ErroParametrosPrecos,
    carregar_parametros_precos,
    retornos_suspeitos,
    suspeita_na_janela,
    tickers_com_suspeita,
)
from processamento.universo import montar_universo

# ---------------------------------------------------------------- grade de exemplo

DATAS = pregoes_uteis(6, "2026-04-06")
PRECOS_A = [10, 10, 10, 3, 3, 3]            # 4ª data: −70%, dentro de −75%
PRECOS_B = [10, 11, 12, 13, 14, 15]
MINIMO, MAXIMO, DEFASAGEM = -0.75, 1.0, 5
QUARTA = pd.Timestamp(DATAS[3])   # índice da grade é DatetimeIndex: a busca com .loc usa Timestamp


def _g(a: list = PRECOS_A) -> pd.DataFrame:
    precos = pd.concat([precos_de("A", DATAS, a), precos_de("B", DATAS, PRECOS_B)], ignore_index=True)
    return fatos_precos.grade_de_precos(precos, DATAS, "fechamento_ajustado", ["A", "B"])


def _yaml_com_eventos(tmp_path, eventos) -> str:
    """Copia o parametros.yaml real com `fase1.eventos_retorno_suspeito` trocado por `eventos`."""
    dados = yaml.safe_load(calendario.CAMINHO_PARAMETROS.read_text(encoding="utf-8"))
    dados["fase1"]["eventos_retorno_suspeito"] = eventos
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return str(caminho)


# ---------------------------------------------------------------- máscara: retornos_suspeitos

def test_sem_evento_a_queda_de_70_por_cento_nao_e_suspeita():
    susp = retornos_suspeitos(_g(), MINIMO, MAXIMO, DEFASAGEM)
    assert not susp.to_numpy().any()


def test_com_evento_so_marca_a_quarta_data_de_a():
    susp = retornos_suspeitos(_g(), MINIMO, MAXIMO, DEFASAGEM, [("A", QUARTA)])
    assert susp.loc[QUARTA, "A"]
    assert int(susp.to_numpy().sum()) == 1
    assert not susp["B"].any()


def test_evento_vazio_e_igual_ao_resultado_atual():
    g = fatos_precos.grade_de_precos(
        pd.concat([precos_de("A", DATAS, [10, 10, 10, 30, 3, 3]), precos_de("B", DATAS, PRECOS_B)], ignore_index=True),
        DATAS, "fechamento_ajustado", ["A", "B"],
    )
    r = fatos_precos.retornos_asof(g)
    atual = (r < MINIMO) | (r > MAXIMO)
    assert atual.to_numpy().any()   # há salto de +200% em A, então o teste não é vazio
    pd.testing.assert_frame_equal(retornos_suspeitos(g, MINIMO, MAXIMO, DEFASAGEM, ()), atual)
    pd.testing.assert_frame_equal(retornos_suspeitos(g, MINIMO, MAXIMO, DEFASAGEM), atual)


def test_evento_fora_da_grade_e_ignorado_sem_erro():
    eventos = [("Z", QUARTA), ("A", date(2030, 1, 1)), ("A", date(2026, 4, 4))]   # ticker, data e data fora da grade
    susp = retornos_suspeitos(_g(), MINIMO, MAXIMO, DEFASAGEM, eventos)
    assert not susp.to_numpy().any()


def test_evento_com_preco_nan_continua_falso():
    g = _g([10, 10, 10, None, 3, 3])
    susp = retornos_suspeitos(g, MINIMO, MAXIMO, DEFASAGEM, [("A", QUARTA)])
    assert not susp.loc[QUARTA, "A"]
    assert not susp.to_numpy().any()


def test_eventos_nao_alteram_a_grade_de_entrada():
    g = _g()
    antes = g.copy()
    retornos_suspeitos(g, MINIMO, MAXIMO, DEFASAGEM, [("A", QUARTA)])
    pd.testing.assert_frame_equal(g, antes)


def test_suspeita_na_janela_com_evento_n_2_marca_quarta_e_quinta_de_a():
    susp = retornos_suspeitos(_g(), MINIMO, MAXIMO, DEFASAGEM, [("A", QUARTA)])
    janela = suspeita_na_janela(susp, 2)
    assert janela["A"].tolist() == [False, False, False, True, True, False]
    assert not janela["B"].any()


def test_tickers_com_suspeita_recebe_os_eventos():
    precos = pd.concat([precos_de("A", DATAS, PRECOS_A), precos_de("B", DATAS, PRECOS_B)], ignore_index=True)
    assert tickers_com_suspeita(precos, DATAS, QUARTA, ["A", "B"], MINIMO, MAXIMO, 1, DEFASAGEM) == set()
    assert tickers_com_suspeita(precos, DATAS, QUARTA, ["A", "B"], MINIMO, MAXIMO, 1, DEFASAGEM,
                                [("A", QUARTA)]) == {"A"}


# ---------------------------------------------------------------- carga e validação de fase1.eventos_retorno_suspeito

def test_carga_do_yaml_real_traz_so_pcar3():
    p = carregar_parametros_precos()
    assert [d for t, d in p.eventos_retorno_suspeito if t == "PCAR3"] == [date(2023, 8, 23)]
    assert [d for t, d in p.eventos_retorno_suspeito if t == "NATU3"] == []
    assert len(p.eventos_retorno_suspeito) == 1


def test_motivos_do_yaml_real_pcar3_com_1_data():
    p = carregar_parametros_precos()
    pcar3 = [(d, m) for t, d, m in p.motivos_eventos_suspeitos if t == "PCAR3"]
    assert pcar3 == [(date(2023, 8, 23), "Cisão do Éxito, sem ajuste no preço")]
    assert len(p.motivos_eventos_suspeitos) == 1
    # mesmos pares de antes: o formato de eventos_retorno_suspeito não mudou
    assert tuple((t, d) for t, d, _ in p.motivos_eventos_suspeitos) == p.eventos_retorno_suspeito


def test_dataclass_com_eventos_e_serializavel_e_comparavel():
    p = carregar_parametros_precos()
    assert asdict(p)["eventos_retorno_suspeito"] == p.eventos_retorno_suspeito
    assert asdict(p)["motivos_eventos_suspeitos"] == p.motivos_eventos_suspeitos
    assert replace(p) == p


@pytest.mark.parametrize("eventos", [
    pytest.param([{"datas": ["2023-08-23"], "motivo": "x"}], id="sem_ticker"),
    pytest.param([{"ticker": "PCAR3", "motivo": "x"}], id="sem_datas"),
    pytest.param([{"ticker": "PCAR3", "datas": ["2023-08-23"]}], id="sem_motivo"),
    pytest.param([{"ticker": 3, "datas": ["2023-08-23"], "motivo": "x"}], id="ticker_nao_texto"),
    pytest.param([{"ticker": " ", "datas": ["2023-08-23"], "motivo": "x"}], id="ticker_vazio"),
    pytest.param([{"ticker": "PCAR3", "datas": [], "motivo": "x"}], id="datas_vazia"),
    pytest.param([{"ticker": "PCAR3", "datas": ["2023-02-30"], "motivo": "x"}], id="data_inexistente"),
    pytest.param([{"ticker": "PCAR3", "datas": ["23/08/2023"], "motivo": "x"}], id="data_fora_do_formato"),
    pytest.param([{"ticker": "PCAR3", "datas": [date(2023, 8, 23)], "motivo": "x"}], id="data_sem_aspas"),
    pytest.param([{"ticker": "PCAR3", "datas": ["2023-08-23"], "motivo": "  "}], id="motivo_vazio"),
    pytest.param("PCAR3", id="eventos_nao_lista"),
    pytest.param(None, id="eventos_null"),
    pytest.param(["PCAR3"], id="item_nao_mapeamento"),
])
def test_validacao_levanta_erro_para_cada_caso_invalido(tmp_path, eventos):
    with pytest.raises(ErroParametrosPrecos, match="eventos_retorno_suspeito"):
        carregar_parametros_precos(_yaml_com_eventos(tmp_path, eventos))


def test_sem_a_chave_eventos_levanta_erro(tmp_path):
    # obrigatória desde 02/11/2026: a ausência não vira "nenhum evento" em silêncio
    dados = yaml.safe_load(calendario.CAMINHO_PARAMETROS.read_text(encoding="utf-8"))
    dados["fase1"].pop("eventos_retorno_suspeito")
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErroParametrosPrecos, match="faltam chaves no bloco fase1"):
        carregar_parametros_precos(str(caminho))


def test_lista_vazia_e_permitida_e_carrega_como_tupla_vazia(tmp_path):
    p = carregar_parametros_precos(_yaml_com_eventos(tmp_path, []))
    assert p.eventos_retorno_suspeito == ()
    assert p.motivos_eventos_suspeitos == ()


# ---------------------------------------------------------------- ponta a ponta: variáveis e alvo do experimento

def test_evento_na_data_t_tira_alvo_de_t_menos_1_e_ret_1d_de_t(tmp_path):
    precos, _ = sus._mundo(alta=0.0)   # sem salto: só o evento pode mascarar
    t = sus.CAL50[25]
    t_menos_1 = sus.CAL50[24]
    com = replace(sus._params_precos(), eventos_retorno_suspeito=(("AAAA3", t),))
    sem = sus._params_precos()
    mascara = pd.DataFrame(True, index=fatos_precos.indice_pregoes(sus.CAL50), columns=sus.TICKERS)

    res_com = variaveis_de_preco(precos, sus.CAL50, sus.TICKERS, mascara, sus.SETOR_DE, sus.CNPJ_DE,
                                 sus._params_exp(), com)
    res_sem = variaveis_de_preco(precos, sus.CAL50, sus.TICKERS, mascara, sus.SETOR_DE, sus.CNPJ_DE,
                                 sus._params_exp(), sem)
    assert pd.isna(res_com["ret_1d"].loc[pd.Timestamp(t), "AAAA3"])
    assert np.isfinite(res_sem["ret_1d"].loc[pd.Timestamp(t), "AAAA3"])
    pd.testing.assert_series_equal(res_com["ret_1d"]["BBBB3"], res_sem["ret_1d"]["BBBB3"])

    alvo_com = alvos(precos, sus.CAL50, sus.TICKERS, com)["alvo"]
    alvo_sem = alvos(precos, sus.CAL50, sus.TICKERS, sem)["alvo"]
    assert pd.isna(alvo_com.loc[pd.Timestamp(t_menos_1), "AAAA3"])
    assert np.isfinite(alvo_sem.loc[pd.Timestamp(t_menos_1), "AAAA3"])


# ---------------------------------------------------------------- exclusões: JBSS3

def test_exclusoes_reais_nao_contem_mais_jbss3():
    assert "JBSS3" not in carregar_exclusoes().tickers_excluidos


def test_jbss3_entra_com_as_exclusoes_reais():
    cal = DATAS[:3]
    cadastro = cadastro_de([("JBSS3", "22222222000122", "Alimentos", "ON")])
    precos = precos_de("JBSS3", cal, [10, 10, 10])
    composicao = pd.DataFrame({"ticker": ["JBSS3"], "data_inicio": [pd.Timestamp(cal[0])], "data_fim": [pd.NaT]})

    uni = montar_universo(cal, cadastro, precos, carregar_exclusoes(), composicao)
    assert set(uni["motivo"]) == {"ok"}
