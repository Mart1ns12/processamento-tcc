"""media_setor no modo "empresa": cada CNPJ conta uma vez (plano da etapa 4, ajuste A1).

Grade de 1 pregão escrita à mão. Z3 tem status não ok (ex.: lucro_negativo), então
`montar_grade` o anula e ele fica fora das médias. Nenhum teste usa banco ou rede.
"""

import numpy as np
import pandas as pd
import pytest

from fabrica_precos import cadastro_de, pregoes_uteis
from processamento.fatos.precos import HIST, OK, indice_pregoes, mapas_cadastro, media_setor, montar_grade

# (ticker, cnpj, setor, valor, status)
LINHAS = [
    ("X3", "1", "S", 10.0, OK),
    ("X4", "1", "S", 20.0, OK),
    ("Y3", "2", "S", 40.0, OK),
    ("Z3", "3", "S", -5.0, "lucro_negativo"),
    ("W3", None, "S", 30.0, OK),
    ("Q3", "4", "T", 8.0, OK),
    ("R3", "5", "T", -2.0, "lucro_negativo"),
]
TICKERS = [t for t, *_ in LINHAS]


def _media(trocar: dict | None = None):
    linhas = [(t, c, s, (trocar or {}).get(t, (v, st))) for t, c, s, v, st in LINHAS]
    idx = indice_pregoes(pregoes_uteis(1))
    valores = pd.DataFrame([[v for *_, (v, _) in linhas]], index=idx, columns=TICKERS, dtype=float)
    status = pd.DataFrame([[st for *_, (_, st) in linhas]], index=idx, columns=TICKERS, dtype=object)
    setor_de, cnpj_de = mapas_cadastro(cadastro_de([(t, c, s, "ON") for t, c, s, _ in linhas]))
    return media_setor(montar_grade(valores, status), TICKERS, setor_de, cnpj_de, "empresa")


def _confere(res, ticker, valor, status):
    assert res.status[ticker].iloc[0] == status
    if valor is None:
        assert np.isnan(res.valor[ticker].iloc[0])
    else:
        assert res.valor[ticker].iloc[0] == pytest.approx(valor, rel=1e-9)


def test_cada_empresa_conta_uma_vez():
    res = _media()
    _confere(res, "X3", 35.0, OK)  # (Y 40 + W 30) / 2
    _confere(res, "X4", 35.0, OK)
    _confere(res, "Y3", 22.5, OK)  # (X 15 + W 30) / 2; por ação daria 20
    _confere(res, "W3", 27.5, OK)  # (X 15 + Y 40) / 2
    _confere(res, "Z3", 28.333333333333332, OK)  # (15 + 40 + 30) / 3


def test_empresa_com_uma_classe_sem_valor_usa_a_outra():
    res = _media({"X4": (float("nan"), HIST)})
    _confere(res, "Y3", 20.0, OK)  # (X 10 + W 30) / 2


# Mediana por empresa (painel, decidido em 23/10/2026): D3 e D4 são a mesma empresa (média 4.0).
LINHAS_MEDIANA = [
    ("A3", "1", "S", 1.0), ("B3", "2", "S", 2.0), ("C3", "3", "S", 10.0),
    ("D3", "4", "S", 3.0), ("D4", "4", "S", 5.0), ("E3", "5", "S", 7.0),
]


def _mediana(trocar: dict | None = None, agregacao: str = "mediana"):
    tickers = [t for t, *_ in LINHAS_MEDIANA]
    idx = indice_pregoes(pregoes_uteis(1))
    vals = [(trocar or {}).get(t, v) for t, _, _, v in LINHAS_MEDIANA]
    valores = pd.DataFrame([vals], index=idx, columns=tickers, dtype=float)
    status = pd.DataFrame([[OK if not np.isnan(v) else HIST for v in vals]], index=idx, columns=tickers, dtype=object)
    setor_de, cnpj_de = mapas_cadastro(cadastro_de([(t, c, s, "ON") for t, c, s, _ in LINHAS_MEDIANA]))
    return media_setor(montar_grade(valores, status), tickers, setor_de, cnpj_de, "empresa", agregacao=agregacao)


def test_mediana_por_empresa():
    res = _mediana()
    _confere(res, "A3", 5.5, OK)  # outras empresas: 2, 10, 4, 7 -> (4 + 7) / 2; a média daria 5.75
    _confere(res, "C3", 3.0, OK)  # 1, 2, 4, 7 -> (2 + 4) / 2; o extremo 10 não entra
    _confere(res, "D3", 4.5, OK)  # 1, 2, 10, 7 -> (2 + 7) / 2
    _confere(res, "D4", 4.5, OK)
    _confere(res, "E3", 3.0, OK)  # 1, 2, 10, 4 -> (2 + 4) / 2


def test_mediana_ignora_empresa_sem_valor_ok():
    res = _mediana({"B3": float("nan")})
    _confere(res, "A3", 7.0, OK)  # 10, 4, 7


def test_mediana_com_media_por_padrao_e_agregacao_invalida():
    _confere(_mediana(agregacao="media"), "A3", 5.75, OK)
    _confere(_media(), "Z3", 28.333333333333332, OK)  # padrão continua média
    with pytest.raises(ValueError, match="agregacao"):
        _mediana(agregacao="moda")


def test_unico_par_sem_valor_ok_fica_fora():
    res = _media()
    _confere(res, "Q3", None, HIST)  # R3 com lucro_negativo não entra
    _confere(res, "R3", 8.0, OK)
