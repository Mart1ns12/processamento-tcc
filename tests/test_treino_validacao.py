"""Testes de validacao.py (etapa 6, fase 2): períodos, dobras e embargo.

Calendário de 14 pregões e tickers fictícios A e B, montados à mão. Nenhum teste usa banco ou rede.
Gabaritos conferidos à mão no plano (docs/plano_etapa6.md, seção "Fase 2").
"""

from dataclasses import replace
from datetime import date

import pandas as pd

from processamento.experimento.validacao import (
    aplicar_inicio,
    dobras_teste_final,
    dobras_walk_forward,
    linhas_com_alvo_ate,
    linhas_da_dobra,
    periodo_desenvolvimento,
    periodo_teste_final,
)


def _d(texto: str) -> date:
    return date.fromisoformat(texto)


CAL14 = [
    _d(s)
    for s in [
        "2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03", "2025-11-19", "2025-11-21", "2025-11-28",
        "2025-12-01", "2025-12-23", "2025-12-26", "2025-12-30", "2026-01-02", "2026-01-05", "2026-01-30",
    ]
]


def _base_caso2() -> pd.DataFrame:
    """Tickers A e B em todas as 14 datas, alvo 1.0, exceto (B, 2025-11-19) com alvo NaN."""
    linhas = []
    for d in CAL14:
        for ticker in ("A", "B"):
            alvo = float("nan") if (ticker == "B" and d == _d("2025-11-19")) else 1.0
            linhas.append({"data": d, "ticker": ticker, "alvo": alvo})
    return pd.DataFrame(linhas)


def _datas_unicas(df: pd.DataFrame) -> list[date]:
    return sorted({pd.Timestamp(x).date() for x in df["data"]})


# Caso 1: calendário de 14 pregões, treino mínimo de 1 mês (3 dobras)

def test_caso1_treino_minimo_1_gera_tres_dobras():
    dobras = dobras_walk_forward(CAL14, treino_minimo_meses=1)
    assert [d.numero for d in dobras] == [1, 2, 3]
    assert [d.mes_teste for d in dobras] == ["2025-11", "2025-12", "2026-01"]

    assert dobras[0].datas_treino == (_d("2025-10-29"), _d("2025-10-30"))
    assert dobras[0].datas_teste == (_d("2025-11-03"), _d("2025-11-19"), _d("2025-11-21"), _d("2025-11-28"))

    assert dobras[1].datas_treino == tuple(
        _d(s) for s in ["2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03", "2025-11-19", "2025-11-21"]
    )
    assert dobras[1].datas_teste == tuple(_d(s) for s in ["2025-12-01", "2025-12-23", "2025-12-26", "2025-12-30"])

    assert dobras[2].datas_treino == tuple(
        _d(s)
        for s in [
            "2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03", "2025-11-19",
            "2025-11-21", "2025-11-28", "2025-12-01", "2025-12-23", "2025-12-26",
        ]
    )
    assert dobras[2].datas_teste == tuple(_d(s) for s in ["2026-01-02", "2026-01-05", "2026-01-30"])


def _renumerada(dobra, numero):
    return replace(dobra, numero=numero)


def test_caso1_treino_minimo_2_gera_so_as_duas_ultimas_numeradas_1_e_2():
    dobras = dobras_walk_forward(CAL14, treino_minimo_meses=2)
    completas = dobras_walk_forward(CAL14, treino_minimo_meses=1)
    assert [d.numero for d in dobras] == [1, 2]
    assert [d.mes_teste for d in dobras] == ["2025-12", "2026-01"]
    assert dobras[0] == _renumerada(completas[1], 1)
    assert dobras[1] == _renumerada(completas[2], 2)


# Caso 2: nenhuma linha de teste no treino, e o embargo

def test_caso2_nenhuma_data_de_teste_no_treino_e_embargo_respeitado():
    dobras = dobras_walk_forward(CAL14, treino_minimo_meses=1)
    for dobra in dobras:
        treino, teste = set(dobra.datas_treino), set(dobra.datas_teste)
        assert treino.isdisjoint(teste)
        assert max(dobra.datas_treino) < dobra.datas_teste[0]

        idx = CAL14.index(dobra.datas_teste[0])
        pregao_anterior = CAL14[idx - 1]
        assert pregao_anterior not in treino

        for d in dobra.datas_treino:
            assert CAL14[CAL14.index(d) + 1] < dobra.datas_teste[0]


def test_caso2_linhas_de_cada_dobra_treino_e_teste():
    base = _base_caso2()
    dobras = dobras_walk_forward(CAL14, treino_minimo_meses=1)
    contagens = []
    for dobra in dobras:
        treino, teste = linhas_da_dobra(base, dobra)
        contagens.append((len(treino), len(teste)))
    assert contagens == [(4, 7), (11, 8), (19, 6)]


def test_caso2_periodo_desenvolvimento_inicio_2026_01_01():
    base = _base_caso2()
    dev = periodo_desenvolvimento(base, _d("2026-01-01"))
    datas = _datas_unicas(dev)
    assert datas == [
        _d("2025-10-29"), _d("2025-10-30"), _d("2025-10-31"), _d("2025-11-03"), _d("2025-11-19"),
        _d("2025-11-21"), _d("2025-11-28"), _d("2025-12-01"), _d("2025-12-23"), _d("2025-12-26"),
    ]
    assert len(datas) == 10
    assert _d("2025-12-30") not in datas
    assert all(d < _d("2026-01-01") for d in datas)


def test_caso2_periodo_desenvolvimento_inicio_2026_01_05_embargo_atravessa_a_virada():
    base = _base_caso2()
    dev = periodo_desenvolvimento(base, _d("2026-01-05"))
    datas = _datas_unicas(dev)
    assert len(datas) == 11
    assert datas[-1] == _d("2025-12-30")
    assert _d("2026-01-02") not in datas


def test_caso2_walk_forward_sobre_desenvolvimento_2026_01_01():
    base = _base_caso2()
    dev = periodo_desenvolvimento(base, _d("2026-01-01"))
    dobras = dobras_walk_forward(_datas_unicas(dev), treino_minimo_meses=1)

    assert [d.mes_teste for d in dobras] == ["2025-11", "2025-12"]
    assert dobras[0].datas_treino == (_d("2025-10-29"), _d("2025-10-30"))
    assert dobras[0].datas_teste == (_d("2025-11-03"), _d("2025-11-19"), _d("2025-11-21"), _d("2025-11-28"))

    assert dobras[1].datas_treino == tuple(
        _d(s) for s in ["2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03", "2025-11-19", "2025-11-21"]
    )
    assert dobras[1].datas_teste == tuple(_d(s) for s in ["2025-12-01", "2025-12-23", "2025-12-26"])


def test_caso2_teste_final_fim_2026_01_30_duas_dobras():
    dobras = dobras_teste_final(CAL14, _d("2025-12-15"), _d("2026-01-30"))
    assert [d.mes_teste for d in dobras] == ["2025-12", "2026-01"]

    a, b = dobras
    assert a.datas_teste == (_d("2025-12-23"), _d("2025-12-26"), _d("2025-12-30"))
    assert a.datas_treino == tuple(
        _d(s)
        for s in [
            "2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03",
            "2025-11-19", "2025-11-21", "2025-11-28",
        ]
    )
    assert len(a.datas_treino) == 7
    assert _d("2025-12-01") not in a.datas_treino

    assert b.datas_teste == (_d("2026-01-02"), _d("2026-01-05"), _d("2026-01-30"))
    assert b.datas_treino == tuple(
        _d(s)
        for s in [
            "2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03", "2025-11-19",
            "2025-11-21", "2025-11-28", "2025-12-01", "2025-12-23", "2025-12-26",
        ]
    )
    assert len(b.datas_treino) == 10


def test_caso2_teste_final_fim_2026_01_05_no_meio_do_mes():
    dobras = dobras_teste_final(CAL14, _d("2025-12-15"), _d("2026-01-05"))
    assert [d.mes_teste for d in dobras] == ["2025-12", "2026-01"]

    a, b = dobras
    assert a.datas_teste == (_d("2025-12-23"), _d("2025-12-26"), _d("2025-12-30"))
    assert len(a.datas_treino) == 7

    assert b.datas_teste == (_d("2026-01-02"), _d("2026-01-05"))
    assert _d("2026-01-30") not in b.datas_teste
    assert len(b.datas_treino) == 10
    assert max(b.datas_treino) == _d("2025-12-26")


def test_caso2_teste_final_fim_2025_12_26_uma_dobra_so():
    dobras = dobras_teste_final(CAL14, _d("2025-12-15"), _d("2025-12-26"))
    assert len(dobras) == 1
    assert dobras[0].mes_teste == "2025-12"
    assert dobras[0].datas_teste == (_d("2025-12-23"), _d("2025-12-26"))
    assert dobras[0].datas_treino == tuple(
        _d(s)
        for s in [
            "2025-10-29", "2025-10-30", "2025-10-31", "2025-11-03",
            "2025-11-19", "2025-11-21", "2025-11-28",
        ]
    )
    assert len(dobras[0].datas_treino) == 7


def test_caso2_periodo_teste_final_ate_2026_01_05():
    """Só linhas com dia do alvo (t+1) <= fim: 01-05 (alvo em 01-30) já é a 1ª previsão ao vivo."""
    base = _base_caso2()
    teste = periodo_teste_final(base, _d("2025-12-15"), _d("2026-01-05"))
    assert _datas_unicas(teste) == [_d("2025-12-23"), _d("2025-12-26"), _d("2025-12-30"), _d("2026-01-02")]
    assert len(teste) == 8
    assert set(teste["ticker"]) == {"A", "B"}


def test_linhas_com_alvo_ate_o_fim():
    base = _base_caso2()
    # fim num pregão (seg 2026-01-05): 01-02 fica (alvo em 01-05); 01-05 e 01-30 saem
    ate = linhas_com_alvo_ate(base, _d("2026-01-05"))
    assert _datas_unicas(ate) == CAL14[:12]
    assert max(_datas_unicas(ate)) == _d("2026-01-02")
    assert len(ate) == 24  # 12 datas × 2 tickers (o alvo NaN de B em 11-19 não é filtrado aqui)
    # fim num domingo (2026-01-04): o alvo de 01-02 é 01-05 > fim, então 01-02 já é ao vivo; última = 12-30
    ate_dom = linhas_com_alvo_ate(base, _d("2026-01-04"))
    assert max(_datas_unicas(ate_dom)) == _d("2025-12-30")
    assert len(_datas_unicas(ate_dom)) == 11
    # dobras do teste final sobre o que sobrou (fim 01-05): dez = [12-23, 12-26, 12-30], jan = [01-02]
    dobras = dobras_teste_final(_datas_unicas(ate), _d("2025-12-15"), _d("2026-01-05"))
    assert [d.datas_teste for d in dobras] == [
        (_d("2025-12-23"), _d("2025-12-26"), _d("2025-12-30")),
        (_d("2026-01-02"),),
    ]


def test_teste_final_nenhuma_data_depois_do_fim_entra_em_treino_ou_teste():
    fim = _d("2026-01-05")
    for dobra in dobras_teste_final(CAL14, _d("2025-12-15"), fim):
        assert all(d <= fim for d in dobra.datas_treino)
        assert all(d <= fim for d in dobra.datas_teste)


def test_aplicar_inicio_mantem_datas_a_partir_do_inicio_e_none_mantem_tudo():
    base = _base_caso2()
    assert _datas_unicas(aplicar_inicio(base, _d("2026-01-01"))) == [_d("2026-01-02"), _d("2026-01-05"), _d("2026-01-30")]
    assert len(aplicar_inicio(base, None)) == len(base)


def test_teste_final_sem_treino_antes_levanta():
    import pytest

    with pytest.raises(ValueError, match="não tem pregões de treino"):
        dobras_teste_final(CAL14, _d("2025-10-01"), _d("2025-10-31"))
