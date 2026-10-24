"""Testes do pacote `series_diarias` (plano da etapa 7, Fase 6b; seções 2.4 e 4.4; casos 1 a 7 da Fase 6b).

Sem rede e sem banco: `banco_teste` é o SQLite de tests/dados (conftest). Nunca `fontes.criar_engine`.
Os cortes de 253 pregões e a janela andando usam fábricas pequenas (tests/fabrica_precos.py).
"""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta

import pandas as pd
import pytest

from fabrica_fundamentos import acoes_de, proventos_de
from fabrica_precos import cadastro_de, indices_de, precos_de, pregoes_uteis, serie_por_retornos
from fabrica_saida import DADOS_ATE, GERADO, insumos_de_teste
from processamento.exclusoes import Exclusoes
from processamento.fatos.fundamentos import DadosFundamentos, carregar_parametros_fundamentos
from processamento.fatos.multiplos import multiplos_diarios
from processamento.fatos.precos import carregar_parametros_precos
from processamento.saida import contrato
from processamento.saida.insumos import Insumos
from processamento.saida.pacote_series import (
    JANELA_PREGOES,
    aviso_retornos_suspeitos,
    comparar_series,
    inicio_janela,
    montar_series_diarias,
    series_completas,
)

PARAMS = carregar_parametros_fundamentos()
DATAS4 = ["2025-10-16", "2025-10-17", "2025-10-20", "2025-10-21"]
CAMPOS_TAEE11 = ("fechamento", "indice_retorno_total", "volume", "pl", "pvp", "dividend_yield")
SEM_10_20 = [{"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}]


# ---------------------------------------------------------------- fábricas e auxiliares

def _multiplos(ins: Insumos) -> dict:
    """Múltiplos do pacote como a Fase 8 passa: `desde` = início da janela."""
    dados = DadosFundamentos(
        precos=ins.precos, cadastro=ins.cadastro, balancos=ins.balancos,
        acoes_emitidas=ins.acoes_emitidas, proventos=ins.proventos, mudancas=ins.mudancas,
    )
    return multiplos_diarios(dados, ins.cal, ins.exclusoes, PARAMS, desde=inicio_janela(ins.cal, ins.t))


def _ins_sintetico(cal: list[date], fech: list[float], aj: list[float]) -> Insumos:
    """Insumos de uma ação AAAA3 (sem CNPJ) e do IBOV constante, com os pregões `cal`."""
    precos = pd.concat([
        precos_de("IBOV", cal, [10.0] * len(cal)),
        precos_de("AAAA3", cal, fech, aj=aj),
    ])
    return Insumos(
        d=cal[-1] + timedelta(days=1), t=cal[-1], cal=cal, precos=precos,
        cadastro=cadastro_de([("AAAA3", None, None, "ON")]), mudancas={},
        balancos=pd.DataFrame(columns=["cnpj", "data_entrega"]), acoes_emitidas=acoes_de([]),
        proventos=proventos_de([]), indices=indices_de([]), noticias=pd.DataFrame(),
        composicao=None, exclusoes=Exclusoes(),
    )


def _ajusta_pre_21(df: pd.DataFrame, coluna: str, fator: float) -> pd.DataFrame:
    """PETR4 antes de 2025-10-21 com `coluna` multiplicada por `fator` (leitor de texto do banco_teste)."""
    df = df.copy()
    mascara = (df["ticker"] == "PETR4") & (df["data"] < "2025-10-21")
    df.loc[mascara, coluna] = df.loc[mascara, coluna].astype(float).mul(fator).map(repr)
    return df


def _recortar(serie: dict, n: int) -> dict:
    """A série só com os `n` primeiros pontos (trechos recalculados)."""
    todas = serie["datas"]
    datas = todas[:n]
    status = {}
    for campo, trechos in serie["status"].items():
        por_ponto = ["ok"] * len(todas)
        for tr in trechos:
            for i in range(todas.index(tr["de"]), todas.index(tr["ate"]) + 1):
                por_ponto[i] = tr["status"]
        novos = contrato.trechos(datas, por_ponto[:n])
        if novos:
            status[campo] = novos
    return {**serie, "datas": datas, "valores": {k: v[:n] for k, v in serie["valores"].items()},
            "status": status}


def _perto(obtida: list, esperada: list) -> None:
    """Listas iguais, com números a 1e-9 relativo e None só por None."""
    assert len(obtida) == len(esperada), (obtida, esperada)
    for o, e in zip(obtida, esperada):
        if e is None:
            assert o is None, (obtida, esperada)
        else:
            assert o == pytest.approx(e, rel=1e-9, abs=1e-12), (obtida, esperada)


@pytest.fixture
def atuais_banco(banco_teste):
    """Séries completas do banco de teste (t = 2025-10-21, D = 2025-10-22)."""
    ins = insumos_de_teste(banco_teste())
    return series_completas(ins, _multiplos(ins))


# ---------------------------------------------------------------- 1: gabarito E2E (formato compacto)

def test_gabarito_e2e_formato_compacto(atuais_banco):
    a = atuais_banco
    assert {"PETR4", "TAEE11", "NOVA3", "IBOV", "IDIV", "CDI", "IPCA"} <= set(a)
    assert not any(k.startswith("SETOR") for k in a)   # DS10/DS15: sem SETOR: e sem SETOR_SEM: (setores de 1 empresa)
    for ausente in ("ITUB4", "IVVB11", "SMLL", "IFIX", "CRFB3"):
        assert ausente not in a
    assert all(s["inicio_janela"] == "2025-10-16" for s in a.values())

    p = a["PETR4"]
    assert p["tipo"] == "acao" and p["nome"] == "PETROBRAS"
    assert p["datas"] == DATAS4
    _perto(p["valores"]["fechamento"], [10.0] * 4)
    _perto(p["valores"]["indice_retorno_total"], [100.0] * 4)
    _perto(p["valores"]["volume"], [1000.0] * 4)
    _perto(p["valores"]["pl"], [6.896551724137931] * 4)
    _perto(p["valores"]["pvp"], [0.8333333333333334] * 4)
    _perto(p["valores"]["dividend_yield"], [0.12, 0.12, 0.12, 0.05])
    assert p["status"] == {}

    t11 = a["TAEE11"]
    assert t11["datas"] == DATAS4
    _perto(t11["valores"]["fechamento"], [10.0, 10.0, None, 10.0])
    _perto(t11["valores"]["indice_retorno_total"], [100.0, 100.0, None, 100.0])
    _perto(t11["valores"]["volume"], [1000.0, 1000.0, None, 1000.0])
    _perto(t11["valores"]["pl"], [6.896551724137931, 6.896551724137931, None, 6.896551724137931])
    _perto(t11["valores"]["pvp"], [0.8333333333333334, 0.8333333333333334, None, 0.8333333333333334])
    _perto(t11["valores"]["dividend_yield"], [0.09, 0.09, None, 0.09])
    assert t11["status"] == {campo: SEM_10_20 for campo in CAMPOS_TAEE11}

    nova = a["NOVA3"]
    assert nova["datas"] == ["2025-10-20", "2025-10-21"]

    ibov = a["IBOV"]
    assert ibov["tipo"] == "indice" and ibov["nome"] == "Ibovespa"
    _perto(ibov["valores"]["fechamento"], [10.0] * 4)
    _perto(ibov["valores"]["indice_retorno_total"], [100.0] * 4)
    assert ibov["status"] == {}

    idiv = a["IDIV"]
    assert idiv["datas"] == ["2025-10-20", "2025-10-21"]
    _perto(idiv["valores"]["fechamento"], [1000.0, 1010.0])
    _perto(idiv["valores"]["indice_retorno_total"], [100.0, 101.0])
    assert idiv["status"] == {}

    cdi = a["CDI"]
    assert cdi["tipo"] == "taxa"
    _perto(cdi["valores"]["indice_retorno_total"], [100.0, 100.05, 100.09002, 100.14006501])
    assert cdi["status"] == {}

    _perto(a["IPCA"]["valores"]["indice_retorno_total"], [100.0] * 4)



# ---------------------------------------------------------------- 2: validador e datas

def test_registros_passam_no_validador_e_datas_crescentes(banco_teste):
    ins = insumos_de_teste(banco_teste())
    registros, removidos, novo_estado = montar_series_diarias(ins, _multiplos(ins), None, GERADO, DADOS_ATE)
    assert removidos == []
    assert registros and all(r["substituir_serie"] is True for r in registros)
    for r in registros:
        contrato.validar("series_diarias", r)
        datas = r["datas"]
        assert datas[-1] == "2025-10-21"
        assert all(datas[i] < datas[i + 1] for i in range(len(datas) - 1))
        assert all(len(v) == len(datas) for v in r["valores"].values())

    # O estado é a lista que o contrato grava e lê: ida e volta pelo JSON, sem diferença, não envia nada.
    estado = json.loads(json.dumps(novo_estado, ensure_ascii=False, allow_nan=False))
    registros2, removidos2, _ = montar_series_diarias(ins, _multiplos(ins), estado, GERADO, DADOS_ATE)
    assert registros2 == [] and removidos2 == []


# ---------------------------------------------------------------- 3: corte de 253 pregões

def test_corte_de_253_pregoes():
    cal = pregoes_uteis(260)
    assert cal[7] == date(2025, 1, 13)
    assert JANELA_PREGOES == 253
    assert inicio_janela(cal, cal[259]) == cal[7]
    assert inicio_janela(cal[:4], cal[3]) == cal[0]

    aj = serie_por_retornos(10.0, [0.001] * 259)
    ins = _ins_sintetico(cal, aj, aj)
    serie = series_completas(ins, _multiplos(ins))["AAAA3"]
    assert len(serie["datas"]) == 253
    assert serie["inicio_janela"] == "2025-01-13"
    assert serie["datas"][0] == "2025-01-13" and serie["datas"][-1] == "2025-12-31"
    ret = serie["valores"]["indice_retorno_total"]
    assert ret[0] == pytest.approx(100.70210350350199, rel=1e-9)  # base do histórico inteiro, não da janela
    assert ret[-1] == pytest.approx(129.54661428719584, rel=1e-9)


def test_inicio_janela_ignora_pregoes_depois_de_t():
    cal = pregoes_uteis(400)
    assert inicio_janela(cal, cal[259]) == cal[7]  # os pregões depois de t não entram na contagem
    assert inicio_janela(cal, cal[399]) == cal[147]


# ---------------------------------------------------------------- 4: janela andando (seção 2.4)

def test_janela_andando_manda_so_o_ponto_novo():
    cal = pregoes_uteis(260)
    aj = serie_por_retornos(10.0, [0.001] * 259)
    ins_est = _ins_sintetico(cal[:259], aj[:259], aj[:259])
    ins_atu = _ins_sintetico(cal, aj, aj)
    estado = series_completas(ins_est, _multiplos(ins_est))
    atuais = series_completas(ins_atu, _multiplos(ins_atu))
    assert estado["AAAA3"]["inicio_janela"] == "2025-01-10"

    enviar, removidos = comparar_series(atuais, estado)
    por_ticker = {r["ticker"]: r for r in enviar}
    assert removidos == []  # o ponto de 2025-01-10 saiu pelo corte: não é sumido
    r = por_ticker["AAAA3"]
    assert r["datas"] == ["2025-12-31"]
    assert r["substituir_serie"] is False
    assert r["inicio_janela"] == "2025-01-13"


# ---------------------------------------------------------------- 5: comparar_series no banco de teste

def test_comparar_estado_none_manda_tudo(atuais_banco):
    enviar, removidos = comparar_series(atuais_banco, None)
    assert len(enviar) == len(atuais_banco)
    assert all(r["substituir_serie"] is True for r in enviar)
    assert removidos == []


def test_comparar_ponto_novo_manda_so_o_ponto(atuais_banco):
    estado = dict(atuais_banco)
    estado["PETR4"] = _recortar(atuais_banco["PETR4"], 3)
    enviar, removidos = comparar_series(atuais_banco, estado)
    assert [r["ticker"] for r in enviar] == ["PETR4"]
    assert enviar[0]["datas"] == ["2025-10-21"]
    assert enviar[0]["substituir_serie"] is False
    assert removidos == []


def test_comparar_desdobramento_manda_a_serie_inteira(atuais_banco):
    estado = copy.deepcopy(atuais_banco)
    estado["PETR4"]["valores"]["fechamento"][0] = 5.0
    enviar, removidos = comparar_series(atuais_banco, estado)
    assert [r["ticker"] for r in enviar] == ["PETR4"]
    assert enviar[0]["substituir_serie"] is True
    assert enviar[0]["datas"] == DATAS4
    assert removidos == []


def test_comparar_diferenca_de_ponto_flutuante_nao_conta(atuais_banco):
    estado = copy.deepcopy(atuais_banco)
    estado["PETR4"]["valores"]["indice_retorno_total"][0] = 100.0 * (1 + 1e-12)
    enviar, removidos = comparar_series(atuais_banco, estado)
    assert enviar == [] and removidos == []


def test_comparar_ponto_que_virou_vazio_manda_a_serie_inteira(atuais_banco):
    estado = copy.deepcopy(atuais_banco)
    estado["TAEE11"]["valores"]["fechamento"][2] = 10.0  # antes tinha valor
    estado["TAEE11"]["status"].pop("fechamento")
    enviar, _ = comparar_series(atuais_banco, estado)
    assert [r["ticker"] for r in enviar] == ["TAEE11"]
    assert enviar[0]["substituir_serie"] is True
    assert enviar[0]["datas"] == DATAS4


def test_comparar_serie_que_sumiu_vai_em_removidos(atuais_banco):
    estado = copy.deepcopy(atuais_banco)
    estado["XXXX3"] = {**copy.deepcopy(atuais_banco["PETR4"]), "ticker": "XXXX3"}
    enviar, removidos = comparar_series(atuais_banco, estado)
    assert removidos == [{"ticker": "XXXX3"}]
    assert enviar == []


def test_comparar_nada_mudou_nao_envia(atuais_banco):
    enviar, removidos = comparar_series(atuais_banco, copy.deepcopy(atuais_banco))
    assert enviar == [] and removidos == []


# ---------------------------------------------------------------- 6: dividendo não força reenvio

def test_dividendo_nao_forca_reenvio(banco_teste):
    ins_est = insumos_de_teste(banco_teste(), date(2025, 10, 21))
    estado = series_completas(ins_est, _multiplos(ins_est))
    ins_atu = insumos_de_teste(banco_teste({"v1-precos": lambda df: _ajusta_pre_21(df, "fechamento_ajustado", 0.98)}))
    atuais = series_completas(ins_atu, _multiplos(ins_atu))

    enviar, removidos = comparar_series(atuais, estado)
    petr4 = {r["ticker"]: r for r in enviar}["PETR4"]
    assert petr4["substituir_serie"] is False
    assert petr4["datas"] == ["2025-10-21"]
    assert petr4["valores"]["indice_retorno_total"][0] == pytest.approx(102.04081632653062, rel=1e-9)
    assert removidos == []


def test_desdobramento_forca_reenvio_da_serie(banco_teste):
    ins_est = insumos_de_teste(banco_teste(), date(2025, 10, 21))
    estado = series_completas(ins_est, _multiplos(ins_est))
    ins_atu = insumos_de_teste(banco_teste({"v1-precos": lambda df: _ajusta_pre_21(df, "fechamento", 0.5)}))
    atuais = series_completas(ins_atu, _multiplos(ins_atu))

    enviar, _ = comparar_series(atuais, estado)
    petr4 = {r["ticker"]: r for r in enviar}["PETR4"]
    assert petr4["substituir_serie"] is True
    assert petr4["datas"] == DATAS4


# ---------------------------------------------------------------- 7: incremental com trecho

def test_incremental_com_ponto_nulo(banco_teste):
    ins_est = insumos_de_teste(banco_teste(), date(2025, 10, 20))  # t = 2025-10-17
    estado = series_completas(ins_est, _multiplos(ins_est))
    ins_atu = insumos_de_teste(banco_teste(), date(2025, 10, 21))  # t = 2025-10-20: TAEE11 sem preço
    atuais = series_completas(ins_atu, _multiplos(ins_atu))

    enviar, _ = comparar_series(atuais, estado)
    r = {x["ticker"]: x for x in enviar}["TAEE11"]
    assert r["substituir_serie"] is False
    assert r["datas"] == ["2025-10-20"]
    for campo in CAMPOS_TAEE11:
        assert r["valores"][campo] == [None]
    assert r["status"] == {campo: SEM_10_20 for campo in CAMPOS_TAEE11}
    contrato.validar("series_diarias", {**contrato.meta(GERADO, DADOS_ATE), **r})


# ---------------------------------------------------------------- 3c-3e: setor sem a própria empresa e aviso (DS7, DS10, DS13)

GERADO_8 = "2026-04-16T09:00:00-03:00"
DADOS_ATE_8 = "2026-04-16T08:00:00-03:00"
PRECOS_2C = {   # mesmos preços do caso 2c da Fase 2 (tests/test_fatos_series.py)
    "AZUL3": [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105],
    "EMBR3": serie_por_retornos(50.0, [0.02, -0.01, 0.02, -0.01, 0.01, 0.0, 0.01]),
    "WEGE3": serie_por_retornos(40.0, [0.0, 0.01, -0.02, 0.03, 0.0, 0.01, -0.01]),
    "RAIL3": serie_por_retornos(20.0, [0.03, 0.0, -0.01, 0.02, 0.01, -0.02, 0.0]),
}
CADASTRO_2C = [("AZUL3", "1", "BI", "ON"), ("EMBR3", "2", "BI", "ON"), ("WEGE3", "3", "BI", "ON"),
               ("RAIL3", "4", "BI", "ON")]
AVISO_2C = ("Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2026-04-06 e 2026-04-15, "
            "fora das séries e das medianas do setor: AZUL3 (2026-04-08, 2026-04-10).")


def _ins_de_acoes(cal: list[date], acoes: dict[str, list[float]], cadastro: list[tuple]) -> Insumos:
    """Insumos com IBOV constante e uma ação por entrada de `acoes` (fechamento = ajustado)."""
    precos = pd.concat([precos_de("IBOV", cal, [10.0] * len(cal))] + [precos_de(tk, cal, p) for tk, p in acoes.items()])
    return Insumos(
        d=cal[-1] + timedelta(days=1), t=cal[-1], cal=cal, precos=precos,
        cadastro=cadastro_de(cadastro), mudancas={},
        balancos=pd.DataFrame(columns=["cnpj", "data_fim_periodo", "data_entrega"]), acoes_emitidas=acoes_de([]),
        proventos=proventos_de([]), indices=indices_de([]), noticias=pd.DataFrame(),
        composicao=None, exclusoes=Exclusoes(),
    )


def _ins_2c(n: int, cadastro: list[tuple] = CADASTRO_2C) -> Insumos:
    """Caso 2c com os `n` primeiros pregões de 06/04/2026."""
    cal = pregoes_uteis(8, "2026-04-06")[:n]
    return _ins_de_acoes(cal, {tk: p[:n] for tk, p in PRECOS_2C.items()}, cadastro)


def test_series_setor_sem_a_propria():
    ins = _ins_2c(8)
    a = series_completas(ins, _multiplos(ins))
    assert sorted(k for k in a if k.startswith("SETOR")) == [
        "SETOR_SEM:AZUL3", "SETOR_SEM:EMBR3", "SETOR_SEM:RAIL3", "SETOR_SEM:WEGE3"]
    emb = a["SETOR_SEM:EMBR3"]
    assert emb["tipo"] == "setor_sem_empresa" and emb["nome"] == "BI sem EMBR3"
    assert emb["inicio_janela"] == "2026-04-06"
    assert emb["datas"] == [d.isoformat() for d in ins.cal]
    _perto(emb["valores"]["indice_retorno_total"], [100.0, 101.66666666666666, 102.17499999999998,
                                                    102.85616666666664, 105.42757083333329, 105.77899606944442,
                                                    105.77899606944442, 105.77899606944442])
    assert emb["valores"]["n_empresas"] == [0, 3, 2, 3, 2, 3, 3, 3]
    assert emb["status"] == {}
    _perto(a["AZUL3"]["valores"]["indice_retorno_total"],
           [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105])   # DS6: a própria ação não muda

    registros, removidos, _ = montar_series_diarias(ins, _multiplos(ins), None, GERADO_8, DADOS_ATE_8)
    assert removidos == []
    for r in registros:
        contrato.validar_serie(r)
    sem = [r for r in registros if r["ticker"].startswith("SETOR_SEM:")]
    assert sem and all(r["substituir_serie"] is True for r in sem)

    assert aviso_retornos_suspeitos(ins, carregar_parametros_precos()) == AVISO_2C


def test_series_setor_sem_quando_muda():
    ins7, ins8 = _ins_2c(7), _ins_2c(8)
    estado = series_completas(ins7, _multiplos(ins7))
    atuais = series_completas(ins8, _multiplos(ins8))
    enviar, removidos = comparar_series(atuais, estado)
    emb = {r["ticker"]: r for r in enviar}["SETOR_SEM:EMBR3"]
    assert emb["datas"] == ["2026-04-15"] and emb["substituir_serie"] is False
    assert removidos == []

    # RAIL3 vai para o setor XX: a EMBR3 perde um membro (pontos antigos mudam) e a SETOR_SEM:RAIL3 some
    cadastro_xx = [*CADASTRO_2C[:3], ("RAIL3", "4", "XX", "ON")]
    atuais_xx = series_completas(_ins_2c(8, cadastro_xx), _multiplos(_ins_2c(8, cadastro_xx)))
    enviar, removidos = comparar_series(atuais_xx, estado)
    emb = {r["ticker"]: r for r in enviar}["SETOR_SEM:EMBR3"]
    assert emb["substituir_serie"] is True and len(emb["datas"]) == 8
    assert {"ticker": "SETOR_SEM:RAIL3"} in removidos


def _salto_petr4(df: pd.DataFrame) -> pd.DataFrame:
    """PETR4 com fechamento_ajustado 1.000.000 em 2025-10-20 (leitor de texto do banco_teste)."""
    df = df.copy()
    m = (df["ticker"] == "PETR4") & (df["data"] == "2025-10-20")
    df.loc[m, "fechamento_ajustado"] = "1000000.0"
    return df


def test_aviso_com_salto_no_banco_de_teste(banco_teste):
    ins = insumos_de_teste(banco_teste({"v1-precos": _salto_petr4}))
    params = carregar_parametros_precos()
    assert aviso_retornos_suspeitos(ins, params) == (
        "Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2025-10-16 e 2025-10-21, "
        "fora das séries e das medianas do setor: PETR4 (2025-10-20, 2025-10-21).")
    assert series_completas(ins, _multiplos(ins))["PETR4"]["valores"]["indice_retorno_total"] == [
        100.0, 100.0, 10000000.0, 100.0]   # DS6: a série da própria ação não muda

    assert aviso_retornos_suspeitos(insumos_de_teste(banco_teste()), params) is None


def test_aviso_salto_antes_da_janela_nao_sai():
    cal = pregoes_uteis(255)
    aj = [10.0] + [30.0] * 254   # salto em cal[1]; inicio_janela = cal[2]
    ins = _ins_sintetico(cal, aj, aj)
    assert aviso_retornos_suspeitos(ins, carregar_parametros_precos()) is None


def test_aviso_com_mais_de_dez_tickers():
    cal = pregoes_uteis(3)
    acoes = {f"T{i:02d}3": [10.0, 30.0, 30.0] for i in range(1, 13)}
    cadastro = [(tk, str(i), "S", "ON") for i, tk in enumerate(acoes, start=1)]
    ins = _ins_de_acoes(cal, acoes, cadastro)
    assert aviso_retornos_suspeitos(ins, carregar_parametros_precos()) == (
        "Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2025-01-02 e 2025-01-06, "
        "fora das séries e das medianas do setor: T013 (2025-01-03), T023 (2025-01-03), T033 (2025-01-03), "
        "T043 (2025-01-03), T053 (2025-01-03), T063 (2025-01-03), T073 (2025-01-03), T083 (2025-01-03), "
        "T093 (2025-01-03), T103 (2025-01-03) e mais 2.")
