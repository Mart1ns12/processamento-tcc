"""Testes da rotina diária ponta a ponta (plano da etapa 8, seção 11: casos 1 a 10, mais extras).

Sem banco real: `banco_teste` (SQLite de tests/dados), `consultar` falso (painel montado na mão), `RelogioFalso`
e todas as pastas em `tmp_path`. Nenhum teste lê o `.env`, a rede ou o relógio do sistema.
Cenário: D = 2025-10-22 (quarta), t esperado = 2025-10-21 (banco de teste).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy

from fabrica_rotina import RelogioFalso, etapas, execucao, linha_do_tempo, painel
from fabrica_treino import dataset_sintetico, params_teste
from processamento.experimento.preparacao import VERSAO_PREPARACAO
from processamento import fontes
from processamento.diagnostico.esperado import ETAPAS_COLETA
from processamento.experimento import modelos, preparacao
from processamento.experimento.modelos import CHAVES_METADADOS
from processamento.rotina import executar
from processamento.rotina.executar import executar_rotina, montar_consulta
from processamento.rotina.parametros import ParametrosChecagem, ParametrosRotina
from processamento.saida import contrato
from processamento.saida.parametros import carregar_parametros_saida

D = date(2025, 10, 22)
ID = "2025-10-22-daily-080001"
INICIO_UTC = "2025-10-22 11:00:01"       # 08:00:01 em São Paulo
T_ESPERADO = date(2025, 10, 21)
DADOS = Path(__file__).parent / "dados"
ORDEM_PACOTES = ["acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
                 "noticias_dia", "experimento_historico", "experimento_top"]
ARQUIVOS = [*ORDEM_PACOTES, "execucao"]
PARAMS = params_teste()  # teste final trancado (fim None)
CHECAGEM_E2E = [
    "Checagem: só 4 de 6 ações (ON, PN e UNIT) com preço em 2025-10-21.",
    "Checagem: indicador vazio em 2025-10-21: USDBRL.fechamento.",
]


class _BancoRealProibido(BaseException):
    """BaseException de propósito: nenhum `except Exception` do caminho pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Nenhum teste da rotina abre o banco da coleta."""
    def _proibido(*args, **kwargs):
        raise _BancoRealProibido("criar_engine chamado num teste da rotina: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


def _salvar_modelos(pasta: Path, mes: str) -> None:
    """Modelo 3 e modelo 1 pequenos do mês `mes` (provisórios), como em tests/test_saida_gerar.py."""
    prep = preparacao.preparar(dataset_sintetico(n_pregoes=130, n_tickers=12))
    treino = preparacao.linhas_de_treino(prep)
    for modelo_id, nome in (("3", f"xgb-{mes}"), ("1", f"xgb-m1-{mes}")):
        colunas = preparacao.colunas_do_modelo(modelo_id)
        modelo = modelos.treinar_xgb(treino[colunas], treino["alvo"], PARAMS.xgboost, PARAMS.semente)
        meta = {**{chave: None for chave in CHAVES_METADADOS}, "versao_preparacao": VERSAO_PREPARACAO}
        meta.update(modelo=modelo_id, colunas=colunas, provisorio=True, calibracao={"aprovada": False},
                    universo="composicao_atual")
        modelos.salvar_modelo(modelo, meta, pasta, nome)


@pytest.fixture(scope="module")
def modelos_dir(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelos_outubro")
    _salvar_modelos(pasta, "2025-10")
    return pasta


@pytest.fixture(scope="module")
def modelos_setembro(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelos_setembro")
    _salvar_modelos(pasta, "2025-09")
    return pasta


def _relogio(hora: str = "07:55", dia: int = 22) -> RelogioFalso:
    h, m = map(int, hora.split(":"))
    return RelogioFalso(datetime(2025, 10, dia, h, m, tzinfo=fontes.SP))


def _estado(entrega: str, *, status: str = "em_andamento", entrega_fim_utc: str | None = None,
            precos: str = "concluida", ibov: date | None = T_ESPERADO):
    """Painel de uma leitura: o daily de D com a etapa `entrega` no status dado e as demais concluídas."""
    situacao = {e: "concluida" for e in ETAPAS_COLETA}
    situacao.update(entrega=entrega, precos=precos)
    fim = {"entrega": entrega_fim_utc} if entrega_fim_utc else None
    return painel([execucao(ID, INICIO_UTC, status=status)], {ID: etapas(ID, situacao, fim)}, ibov)


def _params_rotina(tmp: Path, prazo_tardio: time | None = time(12)) -> ParametrosRotina:
    return ParametrosRotina(
        inicio_consulta=time(8), intervalo_minutos=5, prazo=time(9, 45), prazo_tardio=prazo_tardio,
        etapas_conferidas=("precos", "noticias", "enriquecimento"), pasta_logs=tmp / "logs",
        trava=tmp / "estado" / "rotina.trava", trava_validade_horas=6.0, aviso_calendario_dias=30,
        checagem=ParametrosChecagem(acoes_minimo_fracao=0.9, retorno_maximo_abs=0.30,
                                    preco_parado_pregoes=5, max_tickers_por_aviso=10),
    )


def _params_saida(tmp: Path):
    return dataclasses.replace(carregar_parametros_saida(), pasta=tmp / "saida", pasta_estado=tmp / "estado",
                               pasta_registros=tmp / "registros", publicar_top_provisorio=True)


def _executar(tmp: Path, relogio, consultar, ler, *, d: date = D, sem_esperar: bool = False,
              prazo_tardio: time | None = time(12), params_treino=PARAMS, modelos: Path | None = None):
    return executar_rotina(
        d, relogio=relogio, ler=ler, consultar=consultar, sem_esperar=sem_esperar,
        params_rotina=_params_rotina(tmp, prazo_tardio), params_treino=params_treino,
        params_saida=_params_saida(tmp), pasta_saida=tmp / "saida", pasta_modelos=modelos,
        pasta_registros=tmp / "registros", pasta_estado=tmp / "estado", existe_composicao=False,
    )


def _ler_json(pasta: Path, nome: str) -> dict:
    return json.loads((pasta / f"{nome}.json").read_text(encoding="utf-8"))


def _execucao(pasta: Path) -> dict:
    return _ler_json(pasta, "execucao")["registros"][0]


def _nada_consultado(**_kwargs):
    raise AssertionError("consultar chamado num dia sem pregão ou com trava ocupada")


# ---------------------------------------------------------------- caso 1: entrega às 08:05

def test_caso_1_entrega_as_0805_gera_os_dez_arquivos(banco_teste, tmp_path, modelos_dir):
    relogio = _relogio("07:55")
    consultar = linha_do_tempo(relogio, [(datetime(2025, 10, 22, 8, 0), _estado("em_andamento")),
                                         (datetime(2025, 10, 22, 8, 5), _estado(
                                             "concluida", entrega_fim_utc="2025-10-22 11:05:00"))])

    res = _executar(tmp_path, relogio, consultar, banco_teste(), modelos=modelos_dir)

    assert (res.codigo, res.status) == (0, "ok")
    assert relogio.sonos[0] == 300
    pasta = tmp_path / "saida" / D.isoformat()
    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in ARQUIVOS}
    for nome in ARQUIVOS:
        contrato.validar_lote(_ler_json(pasta, nome))

    execucao_d = _execucao(pasta)
    assert execucao_d["rodada"] == 1 and execucao_d["status"] == "ok"
    coleta = execucao_d["coleta_status"]
    assert coleta["consultas"] == 2 and coleta["espera_segundos"] == 300
    assert coleta["motivo"] == "entrega_concluida" and coleta["execucao_id"] == ID
    top = _ler_json(pasta, "experimento_top")["registros"][0]
    assert top["gerado_em"] == "2025-10-22T08:05:00-03:00"
    for aviso in CHECAGEM_E2E:
        assert aviso in execucao_d["avisos"]


# ---------------------------------------------------------------- caso 2: nunca conclui (sem prazo tardio)

def test_caso_2_sem_entrega_ate_0945_grava_so_o_falhou(banco_teste, tmp_path, modelos_dir):
    relogio = _relogio("07:55")
    consultar = linha_do_tempo(relogio, [(datetime(2025, 10, 22, 8, 0), _estado("em_andamento"))])

    res = _executar(tmp_path, relogio, consultar, banco_teste(), prazo_tardio=None, modelos=modelos_dir)

    assert (res.codigo, res.status) == (4, "falhou")
    pasta = tmp_path / "saida" / D.isoformat()
    assert [p.name for p in pasta.iterdir()] == ["execucao.json"]
    execucao_d = _execucao(pasta)
    assert execucao_d["status"] == "falhou" and execucao_d["pacotes_enviados"] == []
    assert "Coleta: a entrega de hoje não terminou até 09:45; pacotes de hoje não gerados." in execucao_d["avisos"]
    assert execucao_d["coleta_status"]["consultas"] == 22
    assert execucao_d["coleta_status"]["motivo"] == "entrega_pendente"


# ---------------------------------------------------------------- caso 3: rodada tardia (concluiu às 09:50)

def test_caso_3_entrega_tardia_sobrescreve_com_a_rodada_2(banco_teste, tmp_path, modelos_dir):
    relogio = _relogio("07:55")
    consultar = linha_do_tempo(relogio, [
        (datetime(2025, 10, 22, 8, 0), _estado("em_andamento")),
        (datetime(2025, 10, 22, 9, 50), _estado("concluida", entrega_fim_utc="2025-10-22 12:50:00")),
    ])

    res = _executar(tmp_path, relogio, consultar, banco_teste(), modelos=modelos_dir)

    assert (res.codigo, res.status) == (0, "ok")
    pasta = tmp_path / "saida" / D.isoformat()
    execucao_d = _execucao(pasta)
    assert execucao_d["rodada"] == 2 and execucao_d["status"] == "ok"
    assert execucao_d["gerado_em"] == "2025-10-22T09:50:00-03:00"
    top = _ler_json(pasta, "experimento_top")["registros"][0]
    assert top["valido_para_historico"] is False  # fim vazio (antes da produção)


# ---------------------------------------------------------------- caso 4: sábado e feriado

@pytest.mark.parametrize("dia", [date(2025, 10, 25), date(2025, 11, 20)])
def test_caso_4_sabado_e_feriado_saem_com_0_sem_consultar(banco_teste, tmp_path, dia):
    res = _executar(tmp_path, _relogio("07:55"), _nada_consultado, banco_teste(), d=dia)

    assert (res.codigo, res.status) == (0, "sem_pregao")
    assert not (tmp_path / "saida" / dia.isoformat()).exists()


# ---------------------------------------------------------------- caso 5: trava ocupada

def test_caso_5_trava_ocupada_sai_com_5_e_nao_grava(banco_teste, tmp_path):
    trava_arquivo = tmp_path / "estado" / "rotina.trava"
    trava_arquivo.parent.mkdir(parents=True)
    trava_arquivo.write_text(json.dumps({"pid": 777, "criada_em": "2025-10-22T07:50:00-03:00"}), encoding="utf-8")

    res = _executar(tmp_path, _relogio("07:55"), _nada_consultado, banco_teste())

    assert (res.codigo, res.status) == (5, "trava")
    assert not (tmp_path / "saida" / D.isoformat()).exists()
    assert trava_arquivo.is_file()  # a trava de outra rotina continua no lugar


# ---------------------------------------------------------------- caso 6: --sem-esperar com entrega pendente

def test_caso_6_sem_esperar_com_entrega_pendente_gera_na_hora(banco_teste, tmp_path, modelos_dir):
    relogio = _relogio("07:55")
    consultar = linha_do_tempo(relogio, [(datetime(2025, 10, 22, 7, 0), _estado("em_andamento"))])

    res = _executar(tmp_path, relogio, consultar, banco_teste(), sem_esperar=True, modelos=modelos_dir)

    assert (res.codigo, res.status) == (0, "ok")
    assert relogio.sonos == []
    pasta = tmp_path / "saida" / D.isoformat()
    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in ARQUIVOS}
    coleta = _execucao(pasta)["coleta_status"]
    assert coleta["motivo"] == "sem_esperar" and coleta["consultas"] == 1
    assert coleta["nota"].endswith("Consulta única (--sem-esperar).")
    assert ("Coleta: rodada com --sem-esperar; a coleta de hoje ainda não estava pronta (entrega_pendente)."
            in _execucao(pasta)["avisos"])


# ---------------------------------------------------------------- caso 7: duas rodadas seguidas

def test_caso_7_duas_rodadas_seguidas_dao_rodada_2(banco_teste, tmp_path, modelos_dir):
    def rodar():
        relogio = _relogio("07:55")
        consultar = linha_do_tempo(relogio, [(datetime(2025, 10, 22, 8, 0), _estado(
            "concluida", entrega_fim_utc="2025-10-22 11:01:00"))])
        return _executar(tmp_path, relogio, consultar, banco_teste(), modelos=modelos_dir)

    assert rodar().codigo == 0
    assert rodar().codigo == 0

    assert _execucao(tmp_path / "saida" / D.isoformat())["rodada"] == 2


# ---------------------------------------------------------------- caso 8: produção, retreino que falha

def test_caso_8_retreino_que_falha_vira_aviso_e_usa_o_modelo_anterior(banco_teste, tmp_path, modelos_setembro):
    params_producao = params_teste(teste_final_inicio=date(2025, 8, 1), teste_final_fim=date(2025, 10, 21))
    relogio = _relogio("07:55")
    consultar = linha_do_tempo(relogio, [(datetime(2025, 10, 22, 8, 0), _estado(
        "concluida", entrega_fim_utc="2025-10-22 11:01:00"))])

    res = _executar(tmp_path, relogio, consultar, banco_teste(), params_treino=params_producao,
                    modelos=modelos_setembro)

    assert (res.codigo, res.status) == (0, "ok")
    execucao_d = _execucao(tmp_path / "saida" / D.isoformat())
    assert "Retreino de 2025-10 falhou (ErroPreRequisito): usando o modelo anterior." in execucao_d["avisos"]
    assert "Modelo de 2025-09 (o do mês de D ainda não foi treinado)." in execucao_d["avisos"]
    assert _ler_json(tmp_path / "saida" / D.isoformat(), "experimento_top")["registros"]


# ---------------------------------------------------------------- caso 9: montar_consulta com SQLite próprio

def test_caso_9_montar_consulta_le_o_daily_as_etapas_e_o_ibov(tmp_path):
    engine = sqlalchemy.create_engine("sqlite://")
    pd.read_csv(DADOS / "precos.csv", dtype=str).to_sql("v1-precos", engine, index=False)
    execucoes = pd.DataFrame([
        execucao(ID, INICIO_UTC, status="em_andamento"),
        execucao("2025-10-22-coletar-0900", "2025-10-22 12:00:00", tipo="coletar", origem="manual",
                 status="concluida"),
    ], columns=["id", "tipo", "status", "iniciada_em", "finalizada_em", "origem", "aguardando"])
    execucoes.to_sql("v1-painel_execucoes", engine, index=False)
    situacao = {e: "concluida" for e in ETAPAS_COLETA}
    situacao["entrega"] = "em_andamento"
    etapas_df = etapas(ID, situacao).assign(iniciada_em=None)
    etapas_df.to_sql("v1-painel_etapas", engine, index=False)

    def ler(sql, params=None):
        return fontes.executar_leitura(sql, params, engine=engine)

    lido = montar_consulta(ler, D)()

    assert set(lido.execucoes["id"]) == {ID, "2025-10-22-coletar-0900"}
    assert set(lido.etapas) == {ID}
    entrega = lido.etapas[ID].set_index("etapa_id")["status"]
    assert entrega["entrega"] == "em_andamento"
    assert lido.ultimo_ibov == T_ESPERADO


# ---------------------------------------------------------------- caso 10: o banco real está bloqueado

def test_caso_10_sem_banco_real_a_trava_esta_ativa(banco_teste, tmp_path):
    with pytest.raises(_BancoRealProibido):
        fontes.criar_engine()


# ---------------------------------------------------------------- extras: código 3 e log sem texto de erro

def test_extra_erro_de_sessao_nao_e_engolido_e_sai_com_3(banco_teste, tmp_path):
    def consultar():
        raise fontes.ErroSomenteLeitura("comando não permitido: DELETE")

    res = _executar(tmp_path, _relogio("07:55"), consultar, banco_teste())

    assert (res.codigo, res.status) == (3, "sem_banco")
    assert not (tmp_path / "saida" / D.isoformat()).exists()


def test_extra_falha_de_consulta_nao_vaza_o_erro_no_log(banco_teste, tmp_path):
    def consultar():
        raise RuntimeError("host=10.0.0.1 user=segredo")

    res = _executar(tmp_path, _relogio("07:55"), consultar, banco_teste(), prazo_tardio=None)

    assert (res.codigo, res.status) == (4, "falhou")
    log_txt = (tmp_path / "logs" / "rotina-2025-10-22.log").read_text(encoding="utf-8")
    assert "segredo" not in log_txt and "10.0.0.1" not in log_txt
    assert "painel da coleta não lido" in log_txt
    execucao_d = _execucao(tmp_path / "saida" / D.isoformat())
    assert execucao_d["coleta_status"]["motivo"] == "falha_consulta"
    assert ("Coleta: o painel da coleta não pôde ser lido até 09:45; pacotes de hoje não gerados."
            in execucao_d["avisos"])


def test_extra_main_devolve_o_codigo_da_rodada(tmp_path, monkeypatch):
    monkeypatch.setattr(executar, "carregar_parametros_rotina", lambda *a, **k: _params_rotina(tmp_path))
    monkeypatch.setattr(executar, "carregar_parametros_saida", lambda *a, **k: _params_saida(tmp_path))

    codigo = executar.main(["--data", "2025-10-25"], relogio=_relogio("07:55"), ler=None,
                           consultar=_nada_consultado)

    assert codigo == 0
