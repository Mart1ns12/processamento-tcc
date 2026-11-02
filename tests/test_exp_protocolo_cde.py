"""Variáveis do protocolo: blocos C, D, E e controle. Valores do gabarito do plano da Parte B. Sem banco e sem rede."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from fabrica_fundamentos import _a, balanco_de, documentos_de, proventos_de
from fabrica_precos import cadastro_de, pregoes_uteis
from processamento.experimento.resultados import (
    dias_de_resultado,
    dias_desde_resultado,
    fato_relevante_cvm,
    pregao_da_entrega,
    var_lucro_aa,
)
from processamento.experimento.variaveis import controle_sorteado, dy_12m
from processamento.fatos import precos as fatos_precos
from processamento.fatos.fundamentos import balanco_velho
from processamento.fatos.proventos import dividend_yield, ligar_proventos, somas_na_janela

NAN = float("nan")
FR, CM = "Fato Relevante", "Comunicado ao Mercado"
AP, RE = "AP - Apresentação", "RE - Reapresentação Espontânea"
RR = "RR - Reapresentação por Solicitação da CVM"
PERIODOS = ((date(2023, 1, 1), date(2023, 12, 31)), (date(2025, 1, 1), date(2025, 7, 31)))
CAL10 = pregoes_uteis(10, "2026-06-15")   # seg 15/06 a sex 26/06 (sex 19/06, seg 22/06)
CAL5 = pregoes_uteis(5, "2026-06-25")     # 25, 26, 29, 30/06 e 01/07
CAL_LONGO = pregoes_uteis(320, "2024-11-04")


def _iguais(obtido, esperado):
    np.testing.assert_allclose(np.asarray(obtido, dtype=float), np.asarray(esperado, dtype=float),
                               rtol=0, atol=1e-12, equal_nan=True)


def _itr(entrega="2026-06-17", lucro=1, pl=None, ini="2026-01-01", fim="2026-03-31"):
    return _a("ITR", ini, fim, entrega, 1, 1, lucro, pl)


def _dfp(entrega):
    return _a("DFP", "2025-01-01", "2025-12-31", entrega, 1, 1, 1, 1)


def _dias(linhas, cal=CAL10, **kw):
    return dias_desde_resultado(balanco_de("1", linhas), cal, ["1"], 15, **kw)["1"]


# --- pregao_da_entrega

@pytest.mark.parametrize("entrega, esperado", [
    ("2026-06-19", "2026-06-19"),   # sexta: a própria
    ("2026-06-20", "2026-06-19"),   # sábado
    ("2026-06-21", "2026-06-19"),   # domingo
    ("2026-06-22", "2026-06-22"),   # segunda
    ("2026-06-14", None),           # antes do calendário
    ("2026-06-27", None),           # depois do último pregão, sem próximo
])
def test_pregao_da_entrega(entrega, esperado):
    obtido = pregao_da_entrega(pd.Series([pd.Timestamp(entrega)]), CAL10).iloc[0]
    assert pd.isna(obtido) if esperado is None else obtido == pd.Timestamp(esperado)


# --- dias_desde_resultado

@pytest.mark.parametrize("entrega, esperado", [
    ("2026-06-17", [NAN, NAN, 0, 1, 2, 3, 4, 5, 6, 7]),       # em t = 0; em t−1 ainda não existe
    ("2026-06-20", [NAN, NAN, NAN, NAN, 0, 1, 2, 3, 4, 5]),   # sábado: 0 na sexta
    ("2026-06-21", [NAN, NAN, NAN, NAN, 0, 1, 2, 3, 4, 5]),   # domingo: 0 na sexta
])
def test_dias_entrega_em_t_e_no_fim_de_semana(entrega, esperado):
    _iguais(_dias([_itr(entrega)]), esperado)


def test_dias_entrega_em_feriado_vai_para_o_pregao_anterior():
    cal = [d for d in CAL10 if d != date(2026, 6, 19)]
    _iguais(_dias([_itr("2026-06-19")], cal=cal), [NAN, NAN, NAN, 0, 1, 2, 3, 4, 5])


def test_dias_atraso_de_180_conta_e_de_181_nao():
    assert (pd.Timestamp("2026-06-29") - pd.Timestamp("2025-12-31")).days == 180
    _iguais(_dias([_dfp("2026-06-29")], cal=CAL5), [NAN, NAN, 0, 1, 2])
    _iguais(_dias([_dfp("2026-06-30")], cal=CAL5), [NAN] * 5)


def test_dias_reapresentacao_nao_zera_a_contagem():
    base = _itr("2026-06-25")
    _iguais(_dias([base, _dfp("2026-06-29")], cal=CAL5), [0, 1, 0, 1, 2])
    _iguais(_dias([base, _dfp("2026-06-30")], cal=CAL5), [0, 1, 2, 3, 4])


def test_dias_periodo_invalido_nao_conta():
    invalido = _a("ITR", "2026-03-01", "2026-03-31", "2026-06-17", 1, 1, 1, 1)
    _iguais(_dias([invalido]), [NAN] * 10)
    assert dias_de_resultado(balanco_de("1", [invalido]), CAL10)[0].empty   # a mesma regra do dia_resultado


def test_dias_balanco_velho_e_nova_entrega():
    linha = _itr("2024-11-10", ini="2024-07-01", fim="2024-09-30")   # 10/11/2024 é domingo: pregão 08/11
    r = _dias([linha], cal=CAL_LONGO)
    for dia, esperado in [("2024-11-07", NAN), ("2024-11-08", 0), ("2024-11-11", 1), ("2025-12-31", 298),
                          ("2026-01-01", NAN), ("2026-01-02", NAN)]:
        _iguais([r[pd.Timestamp(dia)]], [esperado])
    assert balanco_velho("2024-09-30", "2025-12-31", 15) is False
    assert balanco_velho("2024-09-30", "2026-01-01", 15) is True
    r = _dias([linha, _itr("2026-01-05", ini="2025-10-01", fim="2025-12-31")], cal=CAL_LONGO)
    for dia, esperado in [("2026-01-02", NAN), ("2026-01-05", 0), ("2026-01-06", 1)]:
        _iguais([r[pd.Timestamp(dia)]], [esperado])


def test_dias_empresa_sem_balanco_e_empresa_sem_linha():
    balancos = balanco_de("1", [_itr()])
    _iguais(dias_desde_resultado(balancos, CAL10, ["1"], 15, sem_balanco={"1": "x"})["1"], [NAN] * 10)
    _iguais(dias_desde_resultado(balancos, CAL10, ["9"], 15)["9"], [NAN] * 10)


def test_dias_ao_vivo_fim_de_semana_conta_em_t_e_a_entrega_de_d_nao():
    cal = [date(2026, 6, 18), date(2026, 6, 19)]
    com_sabado = [_itr("2026-06-18"), _dfp("2026-06-20")]
    _iguais(_dias(com_sabado, cal=cal, proximo_ao_vivo=date(2026, 6, 22)), [0, 0])
    _iguais(_dias(com_sabado, cal=cal), [0, 1])      # sem próximo: a janela de sexta ainda não fechou
    _iguais(_dias([_itr("2026-06-18"), _dfp("2026-06-22")], cal=cal, proximo_ao_vivo=date(2026, 6, 22)), [0, 1])


def test_dias_sem_colunas_de_periodo_e_tudo_nan():
    antigo = pd.DataFrame({"cnpj": ["1"], "tipo": ["ITR"], "data_entrega": [pd.Timestamp("2026-06-17")]})
    _iguais(dias_desde_resultado(antigo, CAL10, ["1"], 15)["1"], [NAN] * 10)


# --- var_lucro_aa

LINHAS_VAR = [
    _a("ITR", "2024-07-01", "2024-09-30", "2024-11-10", 1, 1, 15, 800),
    _a("ITR", "2024-01-01", "2024-09-30", "2024-11-10", 1, 1, 50, 800),
    _a("DFP", "2024-01-01", "2024-12-31", "2025-03-20", 1, 1, 70, 850),
    _a("ITR", "2025-01-01", "2025-03-31", "2025-05-10", 1, 1, 10, 870),
    _a("ITR", "2025-07-01", "2025-09-30", "2025-11-10", 1, 1, 25, 900),
    _a("ITR", "2025-01-01", "2025-09-30", "2025-11-10", 1, 1, 60, 900),
    _a("DFP", "2025-01-01", "2025-12-31", "2026-03-20", 1, 1, 100, 1000),
    _a("ITR", "2026-01-01", "2026-03-31", "2026-05-16", 1, 1, 15, 1100),   # 16/05/2026 é sábado
]
CAL_VAR = pregoes_uteis(70, "2026-03-16")
VINTE = pd.Timestamp("2026-03-20")


def _var(linhas=LINHAS_VAR, cal=CAL_VAR, **kw):
    return var_lucro_aa(balanco_de("1", linhas), cal, ["1"], 15, **kw)["1"]


@pytest.mark.parametrize("dia, esperado", [
    ("2026-03-19", (25 - 15) / 900),     # t+1 da DFP: ainda o 3º trimestre
    ("2026-03-20", (40 - 20) / 1000),    # entrega em t. 4º tri = DFP − 9 meses: 100 − 60 e 70 − 50
    ("2026-03-23", (40 - 20) / 1000),
    ("2026-05-15", (40 - 20) / 1000),    # entrega no sábado seguinte: ainda não vale na sexta
    ("2026-05-18", (15 - 10) / 1100),    # vale na segunda
])
def test_var_lucro_bordas_de_entrega(dia, esperado):
    assert _var()[pd.Timestamp(dia)] == pytest.approx(esperado, abs=1e-12)


def test_var_e_dias_divergem_de_proposito_na_entrega_de_sabado():
    assert _dias(LINHAS_VAR, cal=CAL_VAR)[pd.Timestamp("2026-05-15")] == 0
    assert _var()[pd.Timestamp("2026-05-15")] == pytest.approx(0.02, abs=1e-12)


def _sem(indice):
    return [linha for i, linha in enumerate(LINHAS_VAR) if i != indice]


@pytest.mark.parametrize("linhas, esperado", [
    (_sem(2), NAN),                 # sem a DFP 2024: não há 4º tri de 2024
    (_sem(1), NAN),                 # sem os 9 meses de 2024: idem
    (_sem(5), NAN),                 # sem os 9 meses de 2025: não há 4º tri de 2025
    (_sem(6), (25 - 15) / 900),     # sem a DFP 2025: a referência continua o 3º tri de 2025
], ids=["ano_anterior_sem_dfp", "ano_anterior_sem_9m", "trimestre_atual_sem_9m", "sem_a_dfp_atual"])
def test_var_ano_anterior_ou_trimestre_ausente(linhas, esperado):
    _iguais([_var(linhas)[VINTE]], [esperado])


def test_var_periodo_invalido_nao_entra():
    invalido = _a("ITR", "2026-01-01", "2026-12-31", "2026-03-18", 1, 1, 999, 1)   # ITR de 12 meses
    pd.testing.assert_series_equal(_var(LINHAS_VAR + [invalido]), _var())


@pytest.mark.parametrize("campo, valor", [
    ("patrimonio_liquido", 0), ("patrimonio_liquido", -5), ("patrimonio_liquido", None), ("lucro_liquido", None),
])
def test_var_pl_nao_positivo_ou_insumo_vazio(campo, valor):
    linhas = [dict(linha) for linha in LINHAS_VAR]
    linhas[6][campo] = valor
    _iguais([_var(linhas)[VINTE]], [NAN])


def test_var_balanco_velho():
    linhas = [_a("ITR", "2023-07-01", "2023-09-30", "2023-11-10", 1, 1, 5, 100),
              _a("ITR", "2024-07-01", "2024-09-30", "2024-11-10", 1, 1, 8, 100)]
    r = _var(linhas, cal=CAL_LONGO)
    assert r[pd.Timestamp("2024-11-11")] == pytest.approx(0.03, abs=1e-12)
    assert r[pd.Timestamp("2025-12-31")] == pytest.approx(0.03, abs=1e-12)
    assert np.isnan(r[pd.Timestamp("2026-01-01")])


def test_var_entrega_futura_presente_nos_dados_nao_muda_o_passado():
    futura = _a("ITR", "2026-04-01", "2026-06-30", "2026-07-20", 1, 1, 500, 5)
    r = var_lucro_aa(balanco_de("1", LINHAS_VAR + [futura]), CAL_VAR, ["1"], 15)["1"]
    pd.testing.assert_series_equal(r, _var())


def test_var_empresa_sem_balanco_e_banco_sem_receita():
    _iguais(_var(sem_balanco={"1": "x"}), [NAN] * 70)
    linhas = [dict(linha, receita_liquida=None, lucro_bruto=None) for linha in LINHAS_VAR]
    assert _var(linhas)[VINTE] == pytest.approx(0.02, abs=1e-12)


# --- dy_12m

CAD = cadastro_de([("AAAA3", "1", "S1", "ON"), ("AAAA4", "1", "S1", "PN"), ("BBBB3", "2", "S1", "ON")])
PROV = proventos_de([
    ("AAAA3", "DIVIDENDO", "2025-03-18", 1.0, None),   # exatamente t − 12 meses de 18/03/2026: fora nesse t
    ("AAAA3", "DIVIDENDO", "2025-03-19", 0.5, None),
    ("AAAA3", "JCP", "2026-03-18", 0.25, None),        # exatamente t: entra
    ("AAAA3", "DIVIDENDO", "2026-03-19", 8.0, None),   # t + 1: nunca em t
    ("ZZZZ3", "DIVIDENDO", "2025-06-02", 0.1, None),   # ticker antigo da mesma classe: entra
    ("ZZZZ6", "DIVIDENDO", "2025-06-03", 9.0, None),   # conversão de classe: fora
    ("AAAA4", "DIVIDENDO", "2025-12-01", 2.0, None),
])
LIGADOS = ligar_proventos(PROV, CAD, {"ZZZZ3": "AAAA3", "ZZZZ6": "AAAA3"})
CAL_DY = pregoes_uteis(5, "2026-03-16")


def _grade_dy(aaaa3=20.0, aaaa4=40.0, bbbb3=10.0):
    return pd.DataFrame({"AAAA3": [aaaa3] * 5, "AAAA4": [aaaa4] * 5, "BBBB3": [bbbb3] * 5},
                        index=fatos_precos.indice_pregoes(CAL_DY))


def _sem_suspeita(g):
    return pd.DataFrame(False, index=g.index, columns=g.columns)


def test_dy_bordas_da_janela_duas_classes_e_sem_provento():
    g = _grade_dy()
    r = dy_12m(LIGADOS, g, _sem_suspeita(g), 12)
    _iguais(r["AAAA3"], [0.08, 0.08, 0.0425, 0.4175, 0.4175])
    _iguais(r["AAAA4"], [0.05] * 5)   # cada classe com o próprio provento e o próprio preço
    _iguais(r["BBBB3"], [0.0] * 5)    # D8


def test_dy_igual_ao_do_painel():
    g = _grade_dy()
    r = dy_12m(LIGADOS, g, _sem_suspeita(g), 12)
    for t in CAL_DY:
        for ticker, preco in (("AAAA3", 20.0), ("AAAA4", 40.0), ("BBBB3", 10.0)):
            valor, _ = dividend_yield(LIGADOS, ticker, "ON", preco, t, 12)
            assert r.loc[pd.Timestamp(t), ticker] == pytest.approx(valor, abs=1e-12)


def test_dy_futuro_nos_dados_nao_entra():
    g = _grade_dy()
    sem_futuro = ligar_proventos(PROV[PROV["data_com"] <= pd.Timestamp("2026-03-18")], CAD,
                                 {"ZZZZ3": "AAAA3", "ZZZZ6": "AAAA3"})
    com, sem = dy_12m(LIGADOS, g, _sem_suspeita(g), 12), dy_12m(sem_futuro, g, _sem_suspeita(g), 12)
    assert com.loc[pd.Timestamp("2026-03-18"), "AAAA3"] == sem.loc[pd.Timestamp("2026-03-18"), "AAAA3"]
    assert com.loc[pd.Timestamp("2026-03-19"), "AAAA3"] != sem.loc[pd.Timestamp("2026-03-19"), "AAAA3"]   # prova de efeito


def test_dy_29_de_fevereiro():
    prov = proventos_de([("AAAA3", "DIVIDENDO", "2023-02-28", 1.0, None), ("AAAA3", "DIVIDENDO", "2023-03-01", 2.0, None),
                         ("AAAA3", "DIVIDENDO", "2024-02-28", 4.0, None), ("AAAA3", "DIVIDENDO", "2024-02-29", 8.0, None)])
    datas = fatos_precos.indice_pregoes([date(2024, 2, 29), date(2025, 2, 28)])
    _iguais(somas_na_janela(ligar_proventos(prov, CAD, {}), "AAAA3", datas, 12), [14.0, 8.0])


def test_dy_sem_preco_ou_preco_nao_positivo_e_nan():
    g = _grade_dy(aaaa3=NAN, aaaa4=0.0, bbbb3=-1.0)
    assert dy_12m(LIGADOS, g, _sem_suspeita(g), 12).isna().all(axis=None)


def test_dy_retorno_suspeito_anula_20_sessoes_com_t():
    cal = pregoes_uteis(32, "2026-01-05")
    g = pd.DataFrame({"AAAA3": [10.0] * 10 + [30.0] * 22}, index=fatos_precos.indice_pregoes(cal))
    suspeitos = fatos_precos.retornos_suspeitos(g, -0.75, 1.0, 5)
    ligados = ligar_proventos(proventos_de([("AAAA3", "DIVIDENDO", "2025-12-01", 3.0, None)]), CAD, {})
    _iguais(dy_12m(ligados, g, suspeitos, 12)["AAAA3"], [0.3] * 10 + [NAN] * 20 + [0.1, 0.1])


# --- fato_relevante_cvm

CAL_BURACO = [date(2022, 12, 28), date(2022, 12, 29), date(2023, 1, 2), date(2023, 12, 28), date(2024, 1, 2),
              date(2024, 1, 3), date(2025, 7, 31), date(2025, 8, 1), date(2025, 8, 4)]
DOCS_BURACO = documentos_de([
    ("c", "1", CM, "2021-01-04", AP, 1),
    ("a", "1", FR, "2022-12-28", AP, 1),
    ("b", "2", FR, "2022-12-31", AP, 1),   # sábado: vale em 29/12/2022, que tem valor
    ("x", "1", FR, "2024-01-01", AP, 1),   # feriado: vale em 28/12/2023, vazio
    ("d", "2", FR, "2024-01-02", AP, 1),
    ("e", "1", FR, "2025-07-31", AP, 1),
    ("f", "1", FR, "2025-08-01", AP, 1),
    ("g", "2", FR, "2025-08-01", RE, 2),   # reapresentação: não marca
    ("h", "2", CM, "2025-08-01", AP, 1),   # outra categoria: não marca
])


def test_fato_buraco_2023_2025_bordas_e_janela_aberta():
    r = fato_relevante_cvm(DOCS_BURACO, CAL_BURACO, ["1", "2", "3"], PERIODOS)
    _iguais(r["1"], [1, 0, NAN, NAN, 0, 0, NAN, 1, NAN])
    _iguais(r["2"], [0, 1, NAN, NAN, 1, 0, NAN, 0, NAN])
    _iguais(r["3"], [0, 0, NAN, NAN, 0, 0, NAN, 0, NAN])   # sem documento e com cobertura: 0, nunca vazio


def test_fato_janela_fechada_com_proximo():
    r = fato_relevante_cvm(DOCS_BURACO, CAL_BURACO, ["1", "2", "3"], PERIODOS, proximo_ao_vivo=date(2025, 8, 5))
    _iguais(r.iloc[-1], [0, 0, 0])


def test_fato_antes_da_cobertura_e_vazio_e_sem_documentos_tudo_vazio():
    r = fato_relevante_cvm(DOCS_BURACO.iloc[2:], CAL_BURACO, ["1"], PERIODOS)   # cobertura = 31/12/2022
    _iguais(r["1"].iloc[:2], [NAN, NAN])
    assert fato_relevante_cvm(DOCS_BURACO.iloc[0:0], CAL_BURACO, ["1"], PERIODOS).isna().all(axis=None)
    assert fato_relevante_cvm(None, CAL_BURACO, ["1"], PERIODOS).isna().all(axis=None)


def test_fato_fim_de_semana_vai_para_o_ultimo_pregao_antes():
    cal = pregoes_uteis(4, "2026-06-18")   # qui, sex, seg, ter
    docs = documentos_de([
        ("c", "9", CM, "2021-01-04", AP, 1), ("s", "1", FR, "2026-06-20", AP, 1), ("d", "2", FR, "2026-06-21", AP, 1),
        ("m", "3", FR, "2026-06-22", AP, 1), ("n", "4", FR, "2026-06-19", AP, 1),
    ])
    r = fato_relevante_cvm(docs, cal, ["1", "2", "3", "4"], (), proximo_ao_vivo=date(2026, 6, 24))
    _iguais(r.loc[pd.Timestamp("2026-06-19")], [1, 1, 0, 1])
    _iguais(r.loc[pd.Timestamp("2026-06-22")], [0, 0, 1, 0])


def test_fato_ao_vivo_entrega_de_d_fica_fora():
    docs = documentos_de([("c", "9", CM, "2021-01-04", AP, 1), ("s", "1", FR, "2026-06-20", AP, 1),
                          ("d", "2", FR, "2026-06-22", AP, 1)])
    r = fato_relevante_cvm(docs, [date(2026, 6, 19)], ["1", "2"], (), proximo_ao_vivo=date(2026, 6, 22))
    _iguais(r.iloc[0], [1, 0])


@pytest.mark.parametrize("tipo, versao, esperado", [
    (AP, 1, 1), (RE, 2, 0), (RR, 2, 0), (AP, 2, 0), (None, None, 1), (None, 2, 0),
])
def test_fato_reapresentacao_nao_marca(tipo, versao, esperado):
    docs = documentos_de([("c", "9", CM, "2021-01-04", AP, 1), ("x", "1", FR, "2026-06-19", tipo, versao)])
    r = fato_relevante_cvm(docs, [date(2026, 6, 19)], ["1"], (), proximo_ao_vivo=date(2026, 6, 22))
    assert r.iloc[0, 0] == esperado


# --- fato_relevante_cvm: reapresentação sem original conta na data_entrega (regra de 02/11/2026)

RC = "RC - Reapresentação por Exigência"
CAL_OUT = pregoes_uteis(20, "2025-10-06")   # pregões de 06/10 a 31/10/2025
FECHO_OUT = date(2025, 11, 3)                # fecha 31/10 com proximo_ao_vivo


def _dia(n):
    return None if n is None else f"2025-10-{n:02d}"


def _docs(*linhas):
    """Linhas (protocolo, cnpj, categoria, dia de entrega, tipo, versão, dia de referência) de out/2025, mais o
    comunicado de 06/10 que cobre a série."""
    convertidas = [(p, c, cat, _dia(e), tipo, v, _dia(r)) for p, c, cat, e, tipo, v, r in linhas]
    return documentos_de([("cob", "9", CM, "2025-10-06", AP, 1), *convertidas])


@pytest.mark.parametrize("docs, dias_x, dias_y", [
    (_docs(("a", "1", FR, 8, AP, 1, 8)), [8], []),                                              # original
    (_docs(("a", "1", FR, 10, RE, 2, 10)), [10], []),                                           # órfã mesmo dia
    (_docs(("a", "1", FR, 20, RE, 2, 10)), [20], []),                                           # atraso 10
    (_docs(("a", "1", FR, 21, RE, 2, 10)), [], []),                                             # atraso 11
    (_docs(("a", "1", FR, 21, RE, 2, 22)), [], []),                                             # atraso negativo
    (_docs(("a", "1", FR, 21, RE, 2, None)), [], []),                                           # sem referência
    (_docs(("a", "1", FR, 8, AP, 1, 8), ("b", "1", FR, 9, RE, 2, 8)), [8], []),                 # tem original, mesma referência
    (_docs(("a", "1", FR, 7, AP, 1, 7), ("b", "1", FR, 17, RE, 2, 15)), [7], []),               # original a 10 dias
    (_docs(("a", "1", FR, 6, AP, 1, 6), ("b", "1", FR, 17, RE, 2, 15)), [6, 17], []),           # original a 11 dias
    (_docs(("a", "1", FR, 10, RE, 2, 10), ("b", "1", FR, 14, AP, 1, 10)), [10, 14], []),        # original só depois
    (_docs(("a", "1", FR, 10, RE, 2, 10), ("b", "1", FR, 13, RE, 3, 10)), [10], []),            # duas órfãs, mesma referência
    (_docs(("a", "1", FR, 10, RC, 2, 10)), [10], []),                                           # RC
    (_docs(("a", "2", FR, 10, AP, 1, 10), ("b", "1", FR, 10, RE, 2, 10)), [10], [10]),          # original de outra empresa
    (_docs(("a", "1", FR, 11, RE, 2, 10)), [10], []),                                           # sábado: vale na sexta
    (_docs(("a", "1", CM, 10, RE, 2, 10)), [], []),                                             # outra categoria
], ids=["original", "orfa_mesmo_dia", "atraso_10", "atraso_11", "atraso_negativo", "sem_referencia",
        "original_mesma_referencia", "original_outra_referencia_10_dias", "original_outra_referencia_11_dias",
        "original_so_depois", "duas_orfas_mesma_referencia", "rc", "original_de_outra_empresa", "sabado",
        "outra_categoria"])
def test_fato_reapresentacao_sem_original_conta_na_entrega(docs, dias_x, dias_y):
    r = fato_relevante_cvm(docs, CAL_OUT, ["1", "2"], (), proximo_ao_vivo=FECHO_OUT)
    _iguais(r["1"], [1.0 if d.day in dias_x else 0.0 for d in CAL_OUT])
    _iguais(r["2"], [1.0 if d.day in dias_y else 0.0 for d in CAL_OUT])


def test_fato_orfa_mesmo_dia_dentro_de_periodo_sem_coleta_e_nan():
    docs = _docs(("a", "1", FR, 10, RE, 2, 10))
    r = fato_relevante_cvm(docs, CAL_OUT, ["1", "2"], ((date(2025, 10, 9), date(2025, 10, 10)),),
                           proximo_ao_vivo=FECHO_OUT)
    assert np.isnan(r.loc[pd.Timestamp("2025-10-10"), "1"])
    assert r.loc[pd.Timestamp("2025-10-13"), "1"] == 0.0


# --- controle_sorteado

MODELO = pd.DataFrame({"data": pd.to_datetime(["2026-06-18"] * 3 + ["2026-06-19"] * 2),
                       "ticker": ["CCCC3", "AAAA3", "BBBB3", "AAAA3", "BBBB3"]})


def test_controle_gabarito_e_formula():
    r = controle_sorteado(MODELO, 20261023)
    # ordinal de 18/06/2026 = 739785; AAAA3, BBBB3 e CCCC3 recebem o 1º, o 2º e o 3º sorteio
    assert r.iloc[1] == pytest.approx(0.08058276119567642, abs=1e-15)
    assert r.iloc[2] == pytest.approx(0.022672414046066902, abs=1e-15)
    assert r.iloc[0] == pytest.approx(0.5605511317615336, abs=1e-15)
    assert r.iloc[3] == pytest.approx(0.16313227098022987, abs=1e-15)
    assert r.iloc[4] == pytest.approx(0.6967140581639493, abs=1e-15)
    assert ((r >= 0) & (r < 1)).all()


def test_controle_outros_dias_nao_mudam_t_mas_o_proprio_dia_muda():
    base = controle_sorteado(MODELO, 20261023)
    so_dia_18 = controle_sorteado(MODELO[MODELO["data"] == pd.Timestamp("2026-06-18")], 20261023)
    pd.testing.assert_series_equal(base.iloc[:3], so_dia_18)
    sem_aaaa = MODELO[~((MODELO["data"] == pd.Timestamp("2026-06-18")) & (MODELO["ticker"] == "AAAA3"))]
    outro = controle_sorteado(sem_aaaa, 20261023)
    pd.testing.assert_series_equal(base.iloc[3:], outro.iloc[2:])   # o dia 19 não muda
    assert outro.iloc[1] != base.iloc[2]                            # no dia 18, BBBB3 passa a ser o 1º sorteio


def test_controle_nao_depende_da_ordem_das_linhas():
    invertido = controle_sorteado(MODELO.iloc[::-1], 20261023)
    pd.testing.assert_series_equal(invertido.sort_index(), controle_sorteado(MODELO, 20261023))
