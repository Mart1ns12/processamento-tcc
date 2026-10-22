"""Testes de processamento/universo.py: universo de ações por data (seção 3.5).

DataFrames montados no próprio teste; as exclusões são as reais (config/exclusoes.yaml).
Nenhum teste usa banco ou rede.
"""

from datetime import date

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from processamento.exclusoes import carregar_exclusoes
from processamento.universo import montar_universo, tickers_do_dia

D1 = date(2025, 10, 16)
D2 = date(2025, 10, 17)
D3 = date(2025, 10, 20)
D4 = date(2025, 10, 21)
PREGOES = [D1, D2, D3, D4]


def _cadastro() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["PETR3", "PETR4", "TAEE11", "ABEV3", "NOVA3", "JBSS32", "ITUB4", "CRFB3"],
            "tipo_acao": ["ON", "PN", "UNIT", "ON", "ON", "BDR", "PN", "ON"],
        }
    )


def _linhas_preco(ticker: str, datas: list[date], valor: float = 10.0) -> list[tuple]:
    return [(d.isoformat(), ticker, valor) for d in datas]


def _precos() -> pd.DataFrame:
    linhas = []
    linhas += _linhas_preco("IBOV", PREGOES)
    linhas += _linhas_preco("BRENT", PREGOES + [date(2025, 10, 18)])
    linhas += _linhas_preco("PETR3", PREGOES)
    linhas += _linhas_preco("PETR4", PREGOES)
    linhas += _linhas_preco("TAEE11", [D1, D2, D4])
    linhas += _linhas_preco("ABEV3", [D1, D2, D3])
    linhas += [(D4.isoformat(), "ABEV3", float("nan"))]
    linhas += _linhas_preco("NOVA3", [D3, D4])
    linhas += _linhas_preco("JBSS32", PREGOES)
    return pd.DataFrame(linhas, columns=["data", "ticker", "fechamento_ajustado"])


def _composicao() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["PETR3", "PETR4", "ABEV3", "TAEE11", "NOVA3"],
            "data_inicio": [
                pd.Timestamp("2025-01-01"),
                pd.Timestamp("2025-01-01"),
                pd.Timestamp("2025-01-01"),
                pd.Timestamp("2025-10-20"),
                pd.Timestamp("2025-10-21"),
            ],
            "data_fim": [
                pd.NaT,
                pd.Timestamp("2025-10-17"),
                pd.Timestamp("2025-10-16"),
                pd.NaT,
                pd.NaT,
            ],
        }
    )


def _motivo(universo: pd.DataFrame, d: date, t: str) -> str:
    linha = universo.loc[(universo["data"] == pd.Timestamp(d)) & (universo["ticker"] == t), "motivo"]
    assert len(linha) == 1, f"linha ausente ou duplicada: {d} {t}"
    return linha.iloc[0]


def test_caso_a_sem_composicao_tickers_por_dia():
    universo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes())
    assert tickers_do_dia(universo, D1) == ["ABEV3", "PETR3", "PETR4", "TAEE11"]
    assert tickers_do_dia(universo, D2) == ["ABEV3", "PETR3", "PETR4", "TAEE11"]
    assert tickers_do_dia(universo, D3) == ["ABEV3", "NOVA3", "PETR3", "PETR4"]
    assert tickers_do_dia(universo, D4) == ["NOVA3", "PETR3", "PETR4", "TAEE11"]
    assert set(universo["universo"]) == {"composicao_atual"}


@pytest.mark.parametrize(
    "d, t, motivo",
    [
        (D3, "TAEE11", "sem_preco"),
        (D4, "ABEV3", "sem_preco"),
        (D1, "NOVA3", "sem_preco"),
        (D1, "JBSS32", "tipo_nao_aceito"),
        (D1, "CRFB3", "excluido_por_decisao"),
        (D1, "ITUB4", "sem_preco"),
    ],
)
def test_caso_a_motivos(d, t, motivo):
    universo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes())
    assert _motivo(universo, d, t) == motivo


def test_caso_a_colunas_e_tipos():
    universo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes())
    assert list(universo.columns) == ["data", "ticker", "tipo_acao", "no_universo", "motivo", "universo"]
    assert pd.api.types.is_datetime64_any_dtype(universo["data"])
    assert universo["no_universo"].dtype == bool
    assert universo["no_universo"].tolist() == [m == "ok" for m in universo["motivo"]]


def test_caso_a_excluido_fica_fora_em_todas_as_datas():
    universo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes())
    for d in PREGOES:
        assert "CRFB3" not in tickers_do_dia(universo, d)


def test_caso_b_composicao_em_intervalos():
    universo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes(), _composicao())
    assert tickers_do_dia(universo, D1) == ["ABEV3", "PETR3", "PETR4"]
    assert tickers_do_dia(universo, D2) == ["PETR3", "PETR4"]
    assert tickers_do_dia(universo, D3) == ["PETR3"]
    assert tickers_do_dia(universo, D4) == ["NOVA3", "PETR3", "TAEE11"]
    assert set(universo["universo"]) == {"composicao_historica"}


def test_caso_b_motivos():
    universo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes(), _composicao())
    assert _motivo(universo, D3, "TAEE11") == "sem_preco"
    assert _motivo(universo, D3, "PETR4") == "fora_da_composicao"
    assert _motivo(universo, D1, "NOVA3") == "fora_da_composicao"


def test_caso_c_ponto_no_tempo_nao_muda_o_passado():
    precos_ate_d2 = _precos()
    precos_ate_d2 = precos_ate_d2.loc[pd.to_datetime(precos_ate_d2["data"]) <= pd.Timestamp(D2)]
    completo = montar_universo(PREGOES, _cadastro(), _precos(), carregar_exclusoes())
    esperado = completo.loc[completo["data"] <= pd.Timestamp(D2)].reset_index(drop=True)
    resultado = montar_universo([D1, D2], _cadastro(), precos_ate_d2, carregar_exclusoes()).reset_index(drop=True)
    assert_frame_equal(resultado, esperado)


def test_tipo_sem_cadastro_vem_da_classe():
    precos = pd.DataFrame(
        {
            "data": [D1.isoformat(), D1.isoformat()],
            "ticker": ["ABCD4", "ABCD9"],
            "fechamento_ajustado": [10.0, 10.0],
        }
    )
    composicao = pd.DataFrame(
        {
            "ticker": ["ABCD4", "ABCD9"],
            "data_inicio": [pd.NaT, pd.NaT],
            "data_fim": [pd.NaT, pd.NaT],
        }
    )
    cadastro = pd.DataFrame({"ticker": [], "tipo_acao": []})
    universo = montar_universo([D1], cadastro, precos, carregar_exclusoes(), composicao)
    assert _motivo(universo, D1, "ABCD4") == "ok"
    assert universo.loc[universo["ticker"] == "ABCD4", "tipo_acao"].iloc[0] == "PN"
    assert _motivo(universo, D1, "ABCD9") == "tipo_nao_aceito"
