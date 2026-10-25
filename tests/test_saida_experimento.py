"""Testes de processamento/saida/pacotes_experimento.py (etapa 7, fase 7; seção 8 e 4.8/4.9 do plano).

Gabaritos do plano (docs/plano_etapa7.md): os 8 casos da fase 7, com os testes 1 a 3 e 5 a 6 da seção 8.
Dados sintéticos e preços de fábrica; nenhum teste usa banco, rede ou as pastas reais (só tmp_path).
"""

import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from fabrica_precos import precos_de
from fabrica_treino import dataset_sintetico, params_teste
from processamento.experimento import modelos, preparacao, previsao
from processamento.fatos import noticias as fatos_noticias
from processamento.saida import contrato, pacotes_experimento as pe
from processamento.saida.parametros import ParametrosSaida

SP = ZoneInfo("America/Sao_Paulo")
LIMITE = time(10, 0)
DADOS_ATE = "2026-10-23T08:00:00-03:00"
GERADO = datetime(2026, 10, 23, 9, 0, tzinfo=SP)
D = date(2026, 10, 23)


def _saida(pasta: Path) -> ParametrosSaida:
    """Parâmetros da saída com as pastas apontando para tmp_path (nada do yaml real)."""
    return ParametrosSaida(
        limite_valido_historico=LIMITE, pasta=pasta, pasta_estado=pasta, pasta_registros=pasta, tom_neutro=0.05,
    )


def _resultado(data: str, ranking: list[str], alvos: dict[str, float]) -> dict:
    """Resultado fechado com os acertos calculados a partir dos alvos (sem preço faltando)."""
    acertos = [alvos[t] == 1.0 for t in ranking]
    return {
        "data_referencia": data,
        "pregao_base": "2026-01-01",
        "valido_para_historico": True,
        "fechado_em": "2026-01-02T10:00:00-03:00",
        "ranking": ranking,
        "resultado": [
            {
                "ticker": t,
                "retorno": contrato.folha(0.01, "ok"),
                "retorno_ibov": contrato.folha(0.0, "ok"),
                "superou": alvos[t] == 1.0,
            }
            for t in ranking
        ],
        "acertos_dia": sum(acertos),
        "acertos_top3": sum(acertos[:3]),
        "resultado_incompleto": False,
        "alvos_candidatos": alvos,
        "acertos_sombra_modelo_1": None,
        "acertos_sombra_volatilidade": None,
    }


# Produção simulada (seção 4.9): ranking e alvos de AAAA3..FFFF3 em cada pregão previsto.
TICKERS_SIM = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3"]


def _alvos_sim(valores: list[float]) -> dict[str, float]:
    return dict(zip(TICKERS_SIM, valores))


def _resultados_simulados() -> list[dict]:
    """10-30 (válido, ≤ fim: fica de fora), 11-03, 11-04, 11-05 (entram) e 11-06 (inválido: fica de fora)."""
    fora_antes = _resultado("2026-10-30", TICKERS_SIM[:5], _alvos_sim([1, 1, 1, 1, 1, 1]))
    fora_depois = _resultado("2026-11-06", TICKERS_SIM[:5], _alvos_sim([0, 0, 0, 0, 0, 0]))
    fora_depois["valido_para_historico"] = False
    return [
        fora_antes,
        _resultado("2026-11-03", TICKERS_SIM[:5], _alvos_sim([1, 0, 1, 1, 0, 1])),
        _resultado("2026-11-04", TICKERS_SIM[1:], _alvos_sim([1, 1, 0, 0, 1, 0])),
        _resultado("2026-11-05", ["FFFF3", "EEEE3", "DDDD3", "CCCC3", "BBBB3"], _alvos_sim([0, 1, 1, 1, 1, 1])),
        fora_depois,
    ]


# ---------------------------------------------------------------- 1. escolher_modelo

def _pasta_com(tmp_path: Path, nome: str, arquivos: list[str]) -> Path:
    pasta = tmp_path / nome
    pasta.mkdir()
    for arquivo in arquivos:
        (pasta / arquivo).write_bytes(b"")
    return pasta


def test_escolher_modelo_usa_o_do_mes_com_aviso_no_anterior(tmp_path):
    pasta = _pasta_com(tmp_path, "a", ["xgb-2026-06.json", "xgb-m1-2026-06.json"])
    m3, m1, avisos = pe.escolher_modelo(pasta, D)
    assert (m3.name, m1.name) == ("xgb-2026-06.json", "xgb-m1-2026-06.json")
    assert avisos == ["Modelo de 2026-06 (o do mês de D ainda não foi treinado)."]


def test_escolher_modelo_do_mes_de_d_sem_aviso_e_sem_m1(tmp_path):
    pasta = _pasta_com(tmp_path, "b", ["xgb-2026-06.json", "xgb-m1-2026-06.json", "xgb-2026-10.json"])
    m3, m1, avisos = pe.escolher_modelo(pasta, D)
    assert m3.name == "xgb-2026-10.json"
    assert m1 is None
    assert avisos == []


def test_escolher_modelo_so_de_mes_posterior_nao_serve(tmp_path):
    pasta = _pasta_com(tmp_path, "c", ["xgb-2026-11.json"])
    assert pe.escolher_modelo(pasta, D) == (None, None, [])


def test_escolher_modelo_m1_sozinho_nunca_e_modelo_3(tmp_path):
    pasta = _pasta_com(tmp_path, "d", ["xgb-m1-2026-10.json"])
    assert pe.escolher_modelo(pasta, D) == (None, None, [])


# ---------------------------------------------------------------- 2. valido_para_historico

def test_valido_provisorio_antes_da_producao_as_0900():
    valido, razoes = pe.valido_para_historico(
        {"provisorio": True}, datetime(2026, 10, 23, 9, 0, tzinfo=SP), D, None, LIMITE
    )
    assert valido is False
    assert razoes == ["provisorio", "antes_producao"]


def test_valido_antes_das_10h_depois_do_teste_final():
    valido, razoes = pe.valido_para_historico(
        {"provisorio": False}, datetime(2026, 11, 3, 9, 59, 59, tzinfo=SP),
        date(2026, 11, 3), date(2026, 11, 2), LIMITE,
    )
    assert (valido, razoes) == (True, [])


def test_valido_limite_das_10h_inclusivo():
    no_limite, razoes_limite = pe.valido_para_historico(
        {"provisorio": False}, datetime(2026, 11, 3, 10, 0, 0, tzinfo=SP),
        date(2026, 11, 3), date(2026, 11, 2), LIMITE,
    )
    depois, razoes_depois = pe.valido_para_historico(
        {"provisorio": False}, datetime(2026, 11, 3, 10, 0, 1, tzinfo=SP),
        date(2026, 11, 3), date(2026, 11, 2), LIMITE,
    )
    assert (no_limite, razoes_limite) == (True, [])
    assert (depois, razoes_depois) == (False, ["depois_10h"])


def test_valido_dia_do_teste_final_nao_entra():
    valido, razoes = pe.valido_para_historico(
        {"provisorio": False}, datetime(2026, 11, 2, 9, 0, tzinfo=SP),
        date(2026, 11, 2), date(2026, 11, 2), LIMITE,
    )
    assert (valido, razoes) == (False, ["teste_final"])


# ---------------------------------------------------------------- 3 e 4. gerar_top e chance

@pytest.fixture(scope="module")
def cenario(tmp_path_factory):
    """Dataset sintético de 130 pregões e um modelo 3 pequeno treinado nele (sem tocar em modelos/)."""
    df = dataset_sintetico(n_pregoes=130, n_tickers=12)
    t = sorted(df["data"].dt.date.unique())[-1]
    colunas = preparacao.colunas_do_modelo("3")
    params = params_teste()
    prep = preparacao.preparar(df)
    treino = preparacao.linhas_de_treino(prep)
    modelo = modelos.treinar_xgb(treino[colunas], treino["alvo"], params.xgboost, params.semente)
    return {"df": df, "t": t, "colunas": colunas, "modelo": modelo, "params": params,
            "pasta": tmp_path_factory.mktemp("saida")}


def _gerar(cenario: dict, meta: dict, params=None) -> tuple[dict, dict]:
    return pe.gerar_top(
        cenario["df"], cenario["t"], D, cenario["modelo"], meta, None, None,
        pd.DataFrame(columns=fatos_noticias.COLUNAS_JANELA), {}, params or cenario["params"],
        _saida(cenario["pasta"]), GERADO, DADOS_ATE, "xgb-2025-08", [],
    )


def _meta(cenario: dict, aprovada: bool = False) -> dict:
    return {"colunas": cenario["colunas"], "calibracao": {"aprovada": aprovada}, "provisorio": True}


def test_gerar_top_formato_e_chance_sem_valor(cenario):
    pacote, interno = _gerar(cenario, _meta(cenario))
    esperado = previsao.top_do_dia(
        preparacao.preparar(cenario["df"]).loc[(cenario["df"]["data"] == pd.Timestamp(cenario["t"])).to_numpy()],
        cenario["df"].loc[(cenario["df"]["data"] == pd.Timestamp(cenario["t"])).to_numpy()],
        cenario["modelo"], _meta(cenario), cenario["params"],
    )

    assert [item["posicao"] for item in pacote["ranking"]] == [1, 2, 3, 4, 5]
    assert [item["ticker"] for item in pacote["ranking"]] == [item["ticker"] for item in esperado]
    for item in pacote["ranking"]:
        assert item["chance"] == {"valor": None, "referencia_acaso": None, "exibir": False, "status": "calibracao_nao_conferida"}
        assert len(item["motivos"]) == 3
        for motivo in item["motivos"]:
            assert set(motivo) == {"fator", "valor", "efeito", "texto"}
            assert motivo["texto"]
        assert item["noticias_usadas"] == []

    texto = json.dumps(pacote, ensure_ascii=False)
    assert "prob" not in texto
    assert "contribuicao" not in texto
    assert '"media"' not in texto
    assert pacote["modelo_versao"] == "xgb-2025-08"
    assert pacote["valido_para_historico"] is False
    contrato.validar("experimento_top", pacote)
    assert len(interno["sombra_volatilidade"]) == 5
    assert len(interno["probabilidades"]) == 12
    assert len(interno["candidatos"]) == 12


def test_chance_liberada_com_calibracao_aprovada(cenario):
    params = params_teste(liberar_chance=True)
    pacote, interno = _gerar(cenario, _meta(cenario, aprovada=True), params)
    for item in pacote["ranking"]:
        chance = item["chance"]
        assert chance["exibir"] is True
        assert chance["status"] == "ok"
        assert chance["referencia_acaso"] == 0.5
        assert chance["valor"] == pytest.approx(interno["probabilidades"][item["ticker"]], abs=1e-12)
        assert "media" not in chance
    assert '"media"' not in json.dumps(pacote, ensure_ascii=False)
    contrato.validar("experimento_top", pacote)


# ---------------------------------------------------------------- 5. registro do top (S11)

def test_registro_com_fim_e_de_uso_unico(tmp_path):
    p1 = {"data_referencia": "2026-11-03", "marca": "primeiro"}
    p2 = {"data_referencia": "2026-11-03", "marca": "segundo"}
    fim = date(2026, 11, 2)
    assert pe.gravar_registro_top(tmp_path, p1, {"x": 1}, fim) == (p1, True)
    arquivo = tmp_path / "2026-11-03.top.json"
    antes = arquivo.read_bytes()
    assert pe.gravar_registro_top(tmp_path, p2, {"x": 2}, fim) == (p1, False)
    assert arquivo.read_bytes() == antes
    assert pe.registro_existente(tmp_path, date(2026, 11, 3), fim) == p1


def test_registro_sem_fim_sobrescreve_e_nao_e_reaproveitado(tmp_path):
    p1 = {"data_referencia": "2026-11-03", "marca": "primeiro"}
    p2 = {"data_referencia": "2026-11-03", "marca": "segundo"}
    assert pe.gravar_registro_top(tmp_path, p1, {"x": 1}, None) == (p1, True)
    assert pe.gravar_registro_top(tmp_path, p2, {"x": 2}, None) == (p2, True)
    gravado = json.loads((tmp_path / "2026-11-03.top.json").read_text(encoding="utf-8"))
    assert gravado["pacote"] == p2
    assert pe.registro_existente(tmp_path, date(2026, 11, 3), None) is None


# ---------------------------------------------------------------- 6. pode_fechar e montar_historico

def _registro(pregao_previsto: str, valido: bool = True) -> dict:
    return {"pacote": {"pregao_previsto": pregao_previsto, "valido_para_historico": valido}, "interno": {}}


def test_pode_fechar_nunca_sem_fim():
    for dia in ["2026-11-03", "2026-06-23"]:
        assert pe.pode_fechar(_registro(dia), None) is False


def test_pode_fechar_depois_do_fim_e_valido():
    fim = date(2026, 11, 2)
    assert pe.pode_fechar(_registro("2026-11-02"), fim) is False
    assert pe.pode_fechar(_registro("2026-11-03"), fim) is True
    assert pe.pode_fechar(_registro("2026-11-03", valido=False), fim) is False
    assert pe.pode_fechar(None, fim) is False


def test_historico_produção_simulada_gabarito():
    params = params_teste(acaso_sorteios=10000)
    historico = pe.montar_historico(
        _resultados_simulados(), date(2026, 11, 6), date(2026, 11, 2), "composicao_atual",
        params, GERADO, DADOS_ATE,
    )
    resumo = historico["resumo"]
    assert historico["data_referencia"] == "2026-11-05"
    assert resumo["n_dias"] == 3
    assert resumo["periodo_inicio"] == "2026-11-03"
    assert resumo["periodo_fim"] == "2026-11-05"
    assert resumo["taxa_acerto"] == {"valor": pytest.approx(10 / 15, abs=1e-12), "status": "ok"}
    assert resumo["acaso_media"] == {"valor": pytest.approx(2 / 3, abs=1e-12), "status": "ok"}
    assert resumo["acaso_faixa"] == pytest.approx([0.6, 0.8], abs=1e-12)
    dia = historico["dia"]
    assert dia["data_referencia"] == "2026-11-05"
    assert dia["acertos_dia"] == 5
    assert dia["acertos_top3"] == 3
    assert dia["taxa_acumulada"] == {"valor": pytest.approx(10 / 15, abs=1e-12), "status": "ok"}
    contrato.validar("experimento_historico", historico)


def test_historico_sem_fim_nao_mostra_nenhum_dia_fechado(tmp_path):
    envenenados = [
        _resultado("2026-06-23", TICKERS_SIM[:5], _alvos_sim([1, 1, 1, 1, 1, 1])),
        _resultado("2026-07-01", TICKERS_SIM[:5], _alvos_sim([1, 1, 1, 1, 1, 1])),
        _resultado("2026-10-22", TICKERS_SIM[:5], _alvos_sim([1, 1, 1, 1, 1, 1])),
    ]
    historico = pe.montar_historico(
        envenenados, D, None, "composicao_atual", params_teste(), GERADO, DADOS_ATE,
    )
    assert historico["resumo"]["n_dias"] == 0
    assert historico["dia"] is None
    assert historico["data_referencia"] == "2026-10-23"
    texto = json.dumps(historico, ensure_ascii=False)
    for data in ["2026-06-23", "2026-07-01", "2026-10-22"]:
        assert data not in texto
    assert "O histórico começa na entrada em produção" in historico["resumo"]["nota"]
    contrato.validar("experimento_historico", historico)


@pytest.mark.parametrize("universo, frase", [
    ("composicao_atual", "Histórico calculado com as ações que compõem o Ibovespa atualmente."),
    ("composicao_historica", "Histórico calculado com as ações que compunham o Ibovespa em cada data."),
])
def test_historico_nota_por_universo(universo, frase):
    historico = pe.montar_historico([], D, None, universo, params_teste(), GERADO, DADOS_ATE)
    assert historico["resumo"]["nota"] == frase + " " + pe.NOTA_SEM_DIAS
    assert historico["resumo"]["universo"] == universo


# ---------------------------------------------------------------- 7. fechar_dia (gabarito da seção 8)

BASE = date(2026, 10, 30)
PREV = date(2026, 11, 3)
CANDIDATOS = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3"]


def _precos_fechamento() -> pd.DataFrame:
    datas = [BASE, PREV]
    return pd.concat([
        precos_de("AAAA3", datas, [10, 10.2]),
        precos_de("BBBB3", datas, [10, 10.05]),
        precos_de("CCCC3", datas, [100, 101]),
        precos_de("DDDD3", datas, [10, 10.3]),
        precos_de("EEEE3", datas, [10, None]),
        precos_de("FFFF3", datas, [10, 9.9]),
        precos_de("IBOV", datas, [100, 101]),
    ], ignore_index=True)


def _registro_fechamento(valido: bool = True) -> dict:
    return {
        "pacote": {
            "data_referencia": "2026-11-03",
            "pregao_previsto": "2026-11-03",
            "pregao_base": "2026-10-30",
            "valido_para_historico": valido,
            "ranking": [{"ticker": t} for t in CANDIDATOS[:5]],
        },
        "interno": {
            "candidatos": CANDIDATOS,
            "sombra_modelo_1": None,
            "sombra_volatilidade": CANDIDATOS[:5],
        },
    }


def test_fechar_dia_gabarito():
    agora = datetime(2026, 11, 3, 18, 0, tzinfo=SP)
    res = pe.fechar_dia(_registro_fechamento(), _precos_fechamento(), [BASE, PREV], agora)

    assert res["data_referencia"] == "2026-11-03"
    assert res["pregao_base"] == "2026-10-30"
    assert res["fechado_em"] == "2026-11-03T18:00:00-03:00"
    assert res["ranking"] == CANDIDATOS[:5]
    assert res["acertos_dia"] == 2
    assert res["acertos_top3"] == 1
    assert res["resultado_incompleto"] is True
    assert res["alvos_candidatos"] == {
        "AAAA3": 1.0, "BBBB3": 0.0, "CCCC3": 0.0, "DDDD3": 1.0, "EEEE3": None, "FFFF3": 0.0,
    }
    assert res["acertos_sombra_volatilidade"] == 2
    assert res["acertos_sombra_modelo_1"] is None

    por_ticker = {item["ticker"]: item for item in res["resultado"]}
    assert por_ticker["AAAA3"]["retorno"]["valor"] == pytest.approx(0.02, abs=1e-9)
    assert por_ticker["BBBB3"]["retorno"]["valor"] == pytest.approx(0.005, abs=1e-9)
    assert por_ticker["CCCC3"]["retorno"]["valor"] == pytest.approx(0.01, abs=1e-9)
    assert por_ticker["DDDD3"]["retorno"]["valor"] == pytest.approx(0.03, abs=1e-9)
    assert por_ticker["EEEE3"]["retorno"] == {"valor": None, "status": "indisponivel"}
    assert por_ticker["AAAA3"]["superou"] is True
    assert por_ticker["BBBB3"]["superou"] is False
    assert por_ticker["CCCC3"]["superou"] is False
    assert por_ticker["DDDD3"]["superou"] is True
    assert por_ticker["EEEE3"]["superou"] is None
    assert por_ticker["AAAA3"]["retorno_ibov"]["valor"] == pytest.approx(0.01, abs=1e-9)


def test_fechar_dia_descartado_sem_pregao_anterior_ou_invalido():
    agora = datetime(2026, 11, 4, 18, 0, tzinfo=SP)
    # D' = 2026-11-03 não está no calendário seguido de 2026-10-30 (cal tem 11-04 no lugar).
    assert pe.fechar_dia(_registro_fechamento(), _precos_fechamento(), [BASE, date(2026, 11, 4)], agora) is None
    assert pe.fechar_dia(_registro_fechamento(valido=False), _precos_fechamento(), [BASE, PREV], agora) is None


# ---------------------------------------------------------------- 8. linguagem dos pacotes

def test_linguagem_dos_pacotes(cenario):
    pacote, _ = _gerar(cenario, _meta(cenario))
    historico = pe.montar_historico(
        _resultados_simulados(), D, date(2026, 11, 2), "composicao_atual",
        params_teste(acaso_sorteios=200), GERADO, DADOS_ATE,
    )
    proibidas = ["compre", "oportunidade", "melhores ações"]
    for documento in (pacote, historico):
        texto = json.dumps(documento, ensure_ascii=False).lower()
        for palavra in proibidas:
            assert palavra not in texto
        sem_aviso = {k: v for k, v in documento.items() if k != "aviso_fixo"}
        assert "recomenda" not in json.dumps(sem_aviso, ensure_ascii=False).lower()
    assert pacote["aviso_fixo"] == "Não constitui recomendação de investimento."


def test_aviso_provisorio_usa_o_periodo_de_treino_dos_metadados():
    """Aviso do modelo provisório (24/10/2026): período de treino do `.meta.json`, não um texto fixo."""
    from processamento.saida.pacotes_experimento import aviso_provisorio

    assert aviso_provisorio({"periodo_treino": {"inicio": "2024-01-02", "fim": "2026-06-19"}}) == (
        "Modelo provisório: treinado de 2024-01-02 a 2026-06-19 (cerca de 2,5 anos), só para testar a rotina."
    )
    assert aviso_provisorio({}) == "Modelo provisório: período de treino não informado, só para testar a rotina."
