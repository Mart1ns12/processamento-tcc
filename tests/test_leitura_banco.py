"""Leitura do banco real da coleta (teste de fumaça da camada de leitura).

Opcional: só roda com `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`. Usa a conexão somente
leitura de `fontes.criar_engine()` e NUNCA escreve nada. Sem a variável, os testes são pulados.
"""

from datetime import date

import pandas as pd
import pytest

from processamento import calendario, fontes
from processamento.exclusoes import carregar_exclusoes
from processamento.fontes import SP
from processamento.universo import montar_universo, tickers_do_dia

pytestmark = pytest.mark.banco

TABELAS_DO_CONTRATO = [
    "precos",
    "cadastro",
    "mudancas_ticker",
    "balancos",
    "acoes_emitidas",
    "proventos",
    "indices",
]


@pytest.fixture(scope="module")
def ler():
    """Só cria a conexão quando um teste banco roda (testes pulados não chegam aqui)."""
    engine = fontes.criar_engine()
    fontes.verificar_sessao_somente_leitura(lambda s: fontes.executar_leitura(s, engine=engine))
    return lambda s, p=None: fontes.executar_leitura(s, p, engine=engine)


@pytest.fixture(scope="module")
def pregoes_reais(ler):
    return calendario.pregoes(fontes.ler_tabela("precos", ler=ler))


@pytest.mark.parametrize("tabela", TABELAS_DO_CONTRATO)
def test_tabela_do_contrato_le_sem_erro(ler, tabela):
    df = fontes.ler_tabela(tabela, ler=ler)
    assert isinstance(df, pd.DataFrame)


def test_noticias_janela_recente_le_sem_erro(ler):
    df = fontes.ler_noticias(
        desde=date(2026, 10, 13),
        ate=pd.Timestamp("2026-10-20 08:00", tz=SP),
        ler=ler,
    )
    assert isinstance(df, pd.DataFrame)


def test_pregoes_reais_datas_de_referencia(pregoes_reais):
    assert date(2025, 3, 5) in pregoes_reais
    assert date(2025, 11, 21) in pregoes_reais
    for nao_pregao in [
        date(2025, 11, 20),
        date(2025, 12, 24),
        date(2025, 12, 31),
        date(2026, 2, 16),
        date(2026, 2, 17),
    ]:
        assert nao_pregao not in pregoes_reais
    assert sum(1 for d in pregoes_reais if d.year == 2025) == 250


def test_todo_pregao_real_desde_2024_07_29_tem_horario_b3(pregoes_reais):
    for d in pregoes_reais:
        if d >= date(2024, 7, 29):
            abertura, fechamento = calendario.horario_b3(d)
            assert abertura < fechamento


def test_universo_real_2026_10_21_tem_84_acoes(ler, pregoes_reais):
    precos = fontes.ler_tabela("precos", ler=ler)
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    uni = montar_universo(pregoes_reais, cadastro, precos, carregar_exclusoes())
    assert len(tickers_do_dia(uni, date(2026, 10, 21))) == 84


def test_universo_real_azul3_sem_preco_em_2026_01_30(ler, pregoes_reais):
    precos = fontes.ler_tabela("precos", ler=ler)
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    uni = montar_universo(pregoes_reais, cadastro, precos, carregar_exclusoes())
    linha = uni.loc[(uni["data"] == pd.Timestamp("2026-01-30")) & (uni["ticker"] == "AZUL3")]
    assert len(linha) == 1
    assert linha["motivo"].iloc[0] == "sem_preco"
