"""Testes do contrato da saída e dos insumos (plano da etapa 7, fase 4; casos 1 a 12 da seção da Fase 4).

Sem rede e sem banco: `banco_teste` é o SQLite de tests/dados (conftest). Nunca `fontes.criar_engine`.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from fabrica_saida import AGORA, DADOS_ATE, GERADO, exemplo, insumos_de_teste
from processamento import fontes
from processamento.saida import contrato as c
from processamento.saida.contrato import ErroContrato, folha, numero
from processamento.saida.insumos import ErroSaida, ler_insumos, instantes


# ---------------------------------------------------------------- 1 a 2: folha e número

def test_folha_basica_e_conversao_numpy():
    assert folha(0.05, "ok") == {"valor": 0.05, "status": "ok"}
    assert isinstance(folha(np.float64(0.1), "ok")["valor"], float)
    assert folha(float("nan"), "indisponivel") == {"valor": None, "status": "indisponivel"}


def test_folha_recusa_valor_sem_status_ok_e_status_desconhecido():
    with pytest.raises(ErroContrato):
        folha(None, "ok")
    with pytest.raises(ErroContrato, match="valor com status indisponivel"):
        folha(0.0, "indisponivel")
    assert folha(-5.0, "lucro_negativo") == {"valor": -5.0, "status": "lucro_negativo"}
    with pytest.raises(ErroContrato):
        folha(1.0, "xpto")
    with pytest.raises(TypeError):
        numero(True)


# ---------------------------------------------------------------- 3 a 5: validador de registros

def test_validar_acoes_envelope_e_formatos():
    c.validar("acoes", exemplo("acoes"))
    r = exemplo("acoes")
    del r["gerado_em"]
    with pytest.raises(ErroContrato, match="gerado_em"):
        c.validar("acoes", r)
    r = exemplo("acoes")
    r["versao_contrato"] = "1.1"
    with pytest.raises(ErroContrato):
        c.validar("acoes", r)
    r = exemplo("acoes")
    r["gerado_em"] = "2026-10-23T09:00:00"
    with pytest.raises(ErroContrato):
        c.validar("acoes", r)
    r = exemplo("acoes")
    r["gerado_em"] = "2026-10-23T09:00:00-03:00"
    c.validar("acoes", r)
    r = exemplo("mercado_dia")
    r["data_referencia"] = "23/10/2026"
    with pytest.raises(ErroContrato):
        c.validar("mercado_dia", r)
    r = exemplo("acoes")
    r["cor"] = "azul"
    with pytest.raises(ErroContrato, match="campo desconhecido"):
        c.validar("acoes", r)
    r = exemplo("acoes")
    r["tipo_acao"] = "ETF"
    with pytest.raises(ErroContrato):
        c.validar("acoes", r)


def test_validar_resumo_acao_nan_bool_e_caminho():
    r = exemplo("resumo_acao")
    r["pl"]["valor"] = float("nan")
    with pytest.raises(ErroContrato, match="NaN") as info:
        c.validar("resumo_acao", r)
    assert "resumo_acao[PETR4].pl.valor" in str(info.value)
    r = exemplo("resumo_acao")
    r["cotacao"]["fechamento"]["valor"] = True
    with pytest.raises(ErroContrato):
        c.validar("resumo_acao", r)
    c.validar("resumo_acao", exemplo("resumo_acao"))


def test_validar_experimento_top_chance_e_modelo():
    c.validar("experimento_top", exemplo("experimento_top"))
    r = exemplo("experimento_top")
    r["ranking"][0]["chance"] = {"valor": None, "referencia_acaso": None, "exibir": True, "status": "calibracao_nao_conferida"}
    with pytest.raises(ErroContrato):
        c.validar("experimento_top", r)
    r = exemplo("experimento_top")
    r["modelo_versao"] = "xgb-2026-11-01"
    with pytest.raises(ErroContrato, match="xgb-AAAA-MM"):
        c.validar("experimento_top", r)


# ---------------------------------------------------------------- chance do experimento (contrato 1.0)

CHANCE_ESCONDIDA = {"valor": None, "referencia_acaso": None, "exibir": False, "status": "calibracao_nao_conferida"}
CHANCE_LIBERADA = {"valor": 0.58, "referencia_acaso": 0.5, "exibir": True, "status": "ok"}


def _com_chance(chance: dict) -> dict:
    r = exemplo("experimento_top")
    r["ranking"][0]["chance"] = chance
    return r


def test_chance_escondida_e_liberada_passam():
    c.validar("experimento_top", _com_chance(dict(CHANCE_ESCONDIDA)))
    c.validar("experimento_top", _com_chance(dict(CHANCE_LIBERADA)))


def test_chance_escondida_com_referencia_recusada():
    with pytest.raises(ErroContrato):
        c.validar("experimento_top", _com_chance({**CHANCE_ESCONDIDA, "referencia_acaso": 0.5}))


def test_chance_liberada_sem_valor_recusada():
    with pytest.raises(ErroContrato):
        c.validar("experimento_top", _com_chance({**CHANCE_LIBERADA, "valor": None}))


def test_chance_liberada_sem_referencia_recusada():
    with pytest.raises(ErroContrato):
        c.validar("experimento_top", _com_chance({**CHANCE_LIBERADA, "referencia_acaso": None}))


def test_chance_com_media_recusada_com_nome_do_campo():
    chance = {"valor": None, "media": 0.5, "exibir": False, "status": "calibracao_nao_conferida"}
    with pytest.raises(ErroContrato, match="media"):
        c.validar("experimento_top", _com_chance(chance))


def test_chance_escondida_com_valor_recusada():
    with pytest.raises(ErroContrato):
        c.validar("experimento_top", _com_chance({**CHANCE_ESCONDIDA, "valor": 0.58}))


# ---------------------------------------------------------------- 6 a 7: lote e gravação

def test_validar_lote_chave_e_pacote(tmp_path):
    regs = [exemplo("acoes")]
    bom = c.lote("acoes", regs, GERADO, DADOS_ATE)
    c.validar_lote(bom)
    ruim = copy.deepcopy(bom)
    ruim["chave"] = ["ticker", "x"]
    with pytest.raises(ErroContrato):
        c.validar_lote(ruim)
    with pytest.raises(ErroContrato):
        c.validar_lote(c.lote("xpto", regs, GERADO, DADOS_ATE))


def test_gravar_lote_utf8_sem_tmp_e_relido_igual(tmp_path):
    r = exemplo("acoes")
    r["empresa"] = "Ação Ç"
    lote = c.lote("acoes", [r], GERADO, DADOS_ATE)
    arquivo = c.gravar_lote(tmp_path, lote)
    assert arquivo == tmp_path / "acoes.json"
    texto = arquivo.read_text(encoding="utf-8")
    assert "Ação Ç" in texto
    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads(texto) == lote


def test_gravar_lote_recusa_nan_sem_criar_arquivo(tmp_path):
    r = exemplo("mercado_dia")
    r["cdi_dia"] = {"valor": float("nan"), "status": "ok"}
    lote = c.lote("mercado_dia", [r], GERADO, DADOS_ATE)
    with pytest.raises(ValueError):
        c.gravar_lote(tmp_path, lote)
    assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------- 8 a 9: "quando muda" e estado

def test_comparar_registros_regras_do_envio():
    atuais = [{"ticker": "AAAA3", "x": 0.1 + 1e-12, "gerado_em": GERADO}, {"ticker": "CCCC3", "x": 1.0}]
    estado = [{"ticker": "AAAA3", "x": 0.1, "gerado_em": "2025-10-21T09:00:00-03:00"}]
    assert c.comparar_registros(atuais, None, ["ticker"]) == (atuais, [])
    enviar, removidos = c.comparar_registros(atuais, estado, ["ticker"])
    assert enviar == [atuais[1]]
    assert removidos == []

    mudou = [{"ticker": "AAAA3", "x": 0.2}]
    assert c.comparar_registros(mudou, estado, ["ticker"]) == ([mudou[0]], [])

    sumiu = [{"ticker": "AAAA3", "x": 0.1}]
    estado2 = [{"ticker": "AAAA3", "x": 0.1}, {"ticker": "BBBB3", "x": 2.0}]
    assert c.comparar_registros(sumiu, estado2, ["ticker"]) == ([], [{"ticker": "BBBB3"}])

    so_meta = [{"ticker": "AAAA3", "x": 0.1, "gerado_em": "2026-01-01T00:00:00-03:00", "dados_ate": DADOS_ATE}]
    assert c.comparar_registros(so_meta, estado, ["ticker"]) == ([], [])


def test_estado_sem_pasta_e_ida_e_volta(tmp_path):
    assert c.ler_estado(None, "acoes") is None
    c.gravar_estado(None, "acoes", [])
    regs = [exemplo("acoes")]
    c.gravar_estado(tmp_path, "acoes", regs)
    assert c.ler_estado(tmp_path, "acoes") == regs
    assert c.ler_estado(tmp_path, "proventos") is None


# ---------------------------------------------------------------- 10: insumos (banco de teste)

def test_ler_insumos_cortes_do_banco_de_teste(banco_teste):
    ler = banco_teste()
    ins = ler_insumos(date(2025, 10, 22), ler, existe_composicao=False)
    assert ins.t == date(2025, 10, 21)
    assert ins.cal[-1] == ins.t
    assert ins.precos["data"].max() <= pd.Timestamp("2025-10-21")
    assert ins.balancos["data_entrega"].max() == pd.Timestamp("2025-08-10")
    assert ins.proventos["data_com"].max() == pd.Timestamp("2025-08-20")
    assert (ins.noticias["momento_ref"] <= pd.Timestamp("2025-10-22 08:00", tz=fontes.SP)).all()
    assert ins.documentos_cvm["data_entrega"].max() == pd.Timestamp("2025-10-21")
    assert instantes(ins, AGORA) == (GERADO, DADOS_ATE)


def test_ler_insumos_sem_pregao_antes_de_d(banco_teste):
    with pytest.raises(ErroSaida, match="nenhum pregão com preço antes de 2025-10-16"):
        ler_insumos(date(2025, 10, 16), banco_teste(), existe_composicao=False)


def test_insumos_de_teste_usa_a_fabrica(banco_teste):
    ins = insumos_de_teste(banco_teste())
    assert ins.d == date(2025, 10, 22) and ins.composicao is None


# ---------------------------------------------------------------- 11: trechos

def test_trechos_agrupa_status_iguais_contiguos():
    datas = [date(2025, 10, 16), date(2025, 10, 17), date(2025, 10, 20), date(2025, 10, 21), date(2025, 10, 22)]
    assert c.trechos(datas, ["ok", "indisponivel", "indisponivel", "ok", "historico_insuficiente"]) == [
        {"de": "2025-10-17", "ate": "2025-10-20", "status": "indisponivel"},
        {"de": "2025-10-22", "ate": "2025-10-22", "status": "historico_insuficiente"},
    ]
    assert c.trechos(datas, ["ok"] * 5) == []
    assert c.trechos(datas[:2], ["indisponivel", "historico_insuficiente"]) == [
        {"de": "2025-10-16", "ate": "2025-10-16", "status": "indisponivel"},
        {"de": "2025-10-17", "ate": "2025-10-17", "status": "historico_insuficiente"},
    ]


# ---------------------------------------------------------------- 12: validar_serie

def test_validar_serie_exemplo_taee11_passa():
    c.validar_serie(exemplo("series_diarias"))


def test_validar_serie_serie_toda_ok_com_status_vazio_passa():
    r = exemplo("series_diarias")
    r["valores"] = {k: [1.0, 2.0, 3.0, 4.0] for k in r["valores"]}
    r["status"] = {}
    c.validar_serie(r)
    r["valores"]["pl"][0] = -5.0
    r["status"] = {"pl": [{"de": "2025-10-16", "ate": "2025-10-16", "status": "lucro_negativo"}]}
    c.validar_serie(r)


def _serie_com(alterar):
    r = exemplo("series_diarias")
    alterar(r)
    return r


def _sem_status(r):
    r["status"] = {}


CASOS_SERIE_INVALIDA = {
    "a_volume_tamanho_diferente": lambda r: r["valores"].__setitem__("volume", [1000.0, 1000.0, None]),
    "b_null_sem_trecho": lambda r: r["status"].pop("fechamento"),
    "c_trecho_indisponivel_sobre_valor": lambda r: r["status"].__setitem__(
        "pvp", [{"de": "2025-10-16", "ate": "2025-10-16", "status": "indisponivel"},
                {"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}]),
    "d_trechos_sobrepostos": lambda r: r["status"].__setitem__(
        "fechamento", [{"de": "2025-10-17", "ate": "2025-10-20", "status": "indisponivel"},
                       {"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}]),
    "e_trecho_data_fora": lambda r: r["status"].__setitem__(
        "fechamento", [{"de": "2025-10-18", "ate": "2025-10-20", "status": "indisponivel"}]),
    "f_datas_fora_de_ordem": lambda r: r.__setitem__("datas", ["2025-10-17", "2025-10-16", "2025-10-20", "2025-10-21"]),
    "f_datas_repetidas": lambda r: r.__setitem__("datas", ["2025-10-16", "2025-10-16", "2025-10-20", "2025-10-21"]),
    "g_data_antes_da_janela": lambda r: r.__setitem__("inicio_janela", "2025-10-17"),
    "g_data_na_rodada_vazamento": lambda r: r.__setitem__("datas", ["2025-10-16", "2025-10-17", "2025-10-20", "2025-10-22"]),
    "h_campo_de_outro_tipo": lambda r: (r.__setitem__("tipo", "indice"), r["valores"].__setitem__("pl", [1.0] * 4)),
    "h_campo_faltando": lambda r: r["valores"].pop("volume"),
    "i_n_empresas_com_status": lambda r: (
        r.__setitem__("tipo", "setor_sem_empresa"),
        r["valores"].clear(),
        r["valores"].update({"indice_retorno_total": [100.0, 100.0, None, 100.0],
                             "n_empresas": [0, 1, 0, 1]}),
        r["status"].clear(),
        r["status"].update({"n_empresas": [{"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}]}),
    ),
    "i_n_empresas_nulo": lambda r: (
        r.__setitem__("tipo", "setor_sem_empresa"),
        r["valores"].clear(),
        r["valores"].update({"indice_retorno_total": [100.0] * 4, "n_empresas": [0, None, 1, 1]}),
        r["status"].clear(),
    ),
    "j_zero_coberto_por_trecho": lambda r: (
        r["valores"]["fechamento"].__setitem__(0, 0.0),
        r["status"].__setitem__("fechamento", [{"de": "2025-10-16", "ate": "2025-10-16", "status": "indisponivel"},
                                              {"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}]),
    ),
}


@pytest.mark.parametrize("caso", sorted(CASOS_SERIE_INVALIDA))
def test_validar_serie_recusa_casos_invalidos(caso):
    r = _serie_com(CASOS_SERIE_INVALIDA[caso])
    with pytest.raises(ErroContrato):
        c.validar_serie(r)


def test_serie_setor_sem_empresa_passa_e_tipo_setor_recusado():
    """DS10: o tipo do setor sem a própria empresa tem `n_empresas` inteiro; o tipo antigo `setor` sai do contrato."""
    r = _serie_com(CASOS_SERIE_INVALIDA["i_n_empresas_nulo"])
    r["valores"]["n_empresas"] = [0, 1, 1, 1]
    c.validar_serie(r)
    r["tipo"] = "setor"
    with pytest.raises(ErroContrato):
        c.validar_serie(r)


# ---------------------------------------------------------------- complementares

def test_numero_inf_e_datas_hora_sem_fuso():
    with pytest.raises(ErroContrato):
        numero(float("inf"))
    assert numero(None) is None
    assert c.data_txt(pd.Timestamp("2025-10-21")) == "2025-10-21"
    with pytest.raises(ValueError):
        c.data_hora_txt(datetime(2025, 10, 22, 8, 0))
    assert c.data_hora_txt(pd.Timestamp("2025-10-22 08:00", tz=fontes.SP)) == "2025-10-22T08:00:00-03:00"


def test_folha_bool_texto_data():
    assert c.folha_bool(np.bool_(True), "ok") == {"valor": True, "status": "ok"}
    assert c.folha_texto("2025-09", "ok") == {"valor": "2025-09", "status": "ok"}
    assert c.folha_data(pd.Timestamp("2025-09-10"), "ok") == {"valor": "2025-09-10", "status": "ok"}
    with pytest.raises(ErroContrato):
        c.folha_data(None, "ok")


def test_validar_lote_removidos_so_em_quando_muda_e_chave_da_serie():
    lote_acoes = c.lote("acoes", [exemplo("acoes")], GERADO, DADOS_ATE, removidos=[{"ticker": "BBBB3"}])
    c.validar_lote(lote_acoes)
    lote_mercado = c.lote("mercado_dia", [exemplo("mercado_dia")], GERADO, DADOS_ATE, removidos=[{"data_referencia": "x"}])
    with pytest.raises(ErroContrato):
        c.validar_lote(lote_mercado)
    lote_serie = c.lote("series_diarias", [exemplo("series_diarias")], GERADO, DADOS_ATE,
                        removidos=[{"ticker": "ZZZZ3"}])
    c.validar_lote(lote_serie)


def test_gravar_lote_compacto_sem_espacos(tmp_path):
    lote_serie = c.lote("series_diarias", [exemplo("series_diarias")], GERADO, DADOS_ATE)
    arquivo = c.gravar_lote(tmp_path, lote_serie, compacto=True)
    texto = arquivo.read_text(encoding="utf-8")
    assert "\n" not in texto and ": " not in texto
    assert json.loads(texto) == lote_serie


def test_modelo_aceita_logistica_e_recusa_outros_nomes():
    for nome in ("xgb-2026-11", "logistica-2026-11"):
        r = exemplo("experimento_top")
        r["modelo_versao"] = nome
        c.validar("experimento_top", r)
    for nome in ("logistica-2026-11-01", "lgbm-2026-11", "logistica-m1-2026-11"):
        r = exemplo("experimento_top")
        r["modelo_versao"] = nome
        with pytest.raises(ErroContrato, match="ou logistica-AAAA-MM"):
            c.validar("experimento_top", r)
