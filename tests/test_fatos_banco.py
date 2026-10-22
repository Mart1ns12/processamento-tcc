"""Fatos da fase 1 sobre o banco real da coleta (teste de fumaça, etapa 3).

Opcional: só roda com `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`. Só lê, via `fontes.ler_tabela`
e a conexão somente leitura de `fontes.criar_engine()`. Sem a variável, os testes são pulados.
"""

from datetime import date

import pytest

from processamento import calendario, fontes
from processamento.exclusoes import carregar_exclusoes
from processamento.fatos.indices import calcular_indices, indices_no_dia
from processamento.fatos.precos import (
    HIST,
    OK,
    calcular_precos,
    carregar_parametros_precos,
    resumo_precos_no_dia,
)

pytestmark = pytest.mark.banco

T = date(2026, 10, 21)


@pytest.fixture(scope="module")
def ler():
    """Só cria a conexão quando um teste banco roda (testes pulados não chegam aqui)."""
    engine = fontes.criar_engine()
    fontes.verificar_sessao_somente_leitura(lambda s: fontes.executar_leitura(s, engine=engine))
    return lambda s, p=None: fontes.executar_leitura(s, p, engine=engine)


@pytest.fixture(scope="module")
def resumos(ler):
    precos = fontes.ler_tabela("precos", ler=ler)
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    indices = fontes.ler_tabela("indices", ler=ler)
    cal = calendario.pregoes(precos)
    params = carregar_parametros_precos()
    res = calcular_precos(precos, cadastro, cal, carregar_exclusoes(), params)
    ri = calcular_indices(precos, indices, cal, params)
    return resumo_precos_no_dia(res, T), indices_no_dia(ri, T)


def test_petr4_beta_e_a1_em_21_10_2026(resumos):
    r, _ = resumos
    beta = r[(r["ticker"] == "PETR4") & (r["indicador"] == "beta.valor")]
    a1 = r[(r["ticker"] == "PETR4") & (r["indicador"] == "rentabilidade.a1")]
    assert beta["status"].iloc[0] == OK
    assert a1["status"].iloc[0] == OK


def test_idiv_m1_historico_em_21_10_2026(resumos):
    _, ri = resumos
    linha = ri[(ri["indice"] == "IDIV") & (ri["janela"] == "m1")]
    assert linha["status"].iloc[0] == HIST
