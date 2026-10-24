"""Quem usa média e quem usa mediana do setor (decidido em 23/10/2026).

Painel (etapas 3, 4 e 7): mediana por empresa. Variável `ret_vs_setor` do modelo: média.
Um espião em `media_setor` registra a `agregacao` de cada chamada. Sem banco e sem rede.
"""

import pandas as pd

from fabrica_fundamentos import EXCL, mundo
from processamento.experimento import variaveis
from processamento.fatos import fundamentos, precos
from processamento.fatos.fundamentos import DadosFundamentos, carregar_parametros_fundamentos

ORIGINAL = precos.media_setor


def _espiao(chamadas):
    def media_setor(*args, agregacao="media", **kwargs):
        chamadas.append(agregacao)
        return ORIGINAL(*args, agregacao=agregacao, **kwargs)
    return media_setor


def test_painel_de_fundamentos_usa_mediana(monkeypatch):
    chamadas = []
    monkeypatch.setattr(fundamentos, "media_setor", _espiao(chamadas))
    cadastro, balancos, acoes, proventos, precos_df, cal, mudancas = mundo()
    dados = DadosFundamentos(precos_df, cadastro, balancos, acoes, proventos, mudancas)
    fundamentos.calcular_fundamentos_no_dia(cal[-1], cal, dados, EXCL, carregar_parametros_fundamentos(), "empresa")
    assert chamadas and set(chamadas) == {"mediana"}


def test_rentabilidade_do_setor_no_painel_nao_usa_media_nem_mediana(monkeypatch):
    """Desde 24/10/2026 a `rentabilidade.setor` é a razão da série SETOR_SEM (DS11), não `media_setor`."""
    chamadas = []
    monkeypatch.setattr(precos, "media_setor", _espiao(chamadas))
    cadastro, _, _, _, precos_df, cal, _ = mundo()
    res = precos.calcular_precos(precos_df, cadastro, cal, EXCL, precos.carregar_parametros_precos())
    assert chamadas == []
    assert "rentabilidade.setor.d1" in res


def test_ret_vs_setor_do_modelo_continua_com_media(monkeypatch):
    chamadas = []
    monkeypatch.setattr(variaveis.fatos_precos, "media_setor", _espiao(chamadas))
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-02")], name="data")
    ret = pd.DataFrame([[0.01, 0.02, 0.10]], index=idx, columns=["A3", "B3", "C3"])
    mascara = pd.DataFrame(True, index=idx, columns=ret.columns)
    setor_de = {"A3": "S", "B3": "S", "C3": "S"}
    cnpj_de = {"A3": "1", "B3": "2", "C3": "3"}
    out = variaveis.ret_vs_setor(ret, mascara, setor_de, cnpj_de, "empresa")
    assert chamadas == ["media"]
    assert out.loc[idx[0], "A3"] == 0.01 - (0.02 + 0.10) / 2
