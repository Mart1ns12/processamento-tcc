"""Papéis ignorados de `v1-noticias` (`papeis_ignorados` no fontes.yaml; papel vazio fica).

A leitura tira as notícias com papel da lista (`fontes.ler_noticias` e `fontes.tratar_noticias_lidas`), conta
por papel em `df.attrs["papeis_ignorados"]` e os consumidores (fatos, dataset, rotina) não veem essas linhas.
Nenhum teste usa banco real ou rede: SQLite de tests/dados (`banco_teste`) e tabelas montadas à mão, com
tickers da fábrica. Modelo: tests/test_origens_ignoradas.py.
"""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fabrica_experimento import CADASTRO_INTEGRACAO, EXCLUSOES_INTEGRACAO, dados_de, integracao
from fabrica_rotina import etapas, execucao, painel

from processamento import fontes
from processamento.diagnostico.esperado import ETAPAS_COLETA
from processamento.experimento import noticias as exp_noticias
from processamento.experimento.dataset import montar_dataset
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.experimento.preparacao import NOTICIAS_DIA
from processamento.fatos import noticias as fatos_noticias
from processamento.fatos.precos import mapas_cadastro
from processamento.rotina.gatilho import avaliar_painel
from processamento.rotina.parametros import carregar_parametros_rotina

SP = ZoneInfo("America/Sao_Paulo")
PARAMS_EXP = carregar_parametros_experimento()
DIA = "2025-10-17"


class _BancoRealProibido(BaseException):
    """BaseException de propósito: o `except Exception` da leitura não pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Nenhum teste deste arquivo abre o banco da coleta (mesmo padrão de test_origens_ignoradas)."""
    def _proibido(*args, **kwargs):
        raise _BancoRealProibido("criar_engine chamado num teste: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


# ---------------------------------------------------------------- linhas e tabelas de teste

def _linha(id_: str, ticker: str, hora: str | None, dia, *, pp: str = "0.2", pn: str = "0.3",
           origem: str = "google_news", papel: str | None = None, titulo: str | None = None) -> dict:
    """Uma linha de `v1-noticias` como vem do banco (textos). Sem `hora`, a publicação não tem horário."""
    neutro = max(0.0, 1 - float(pp) - float(pn))
    return {
        "id": id_, "ticker": ticker,
        "data_hora_publicacao": None if hora is None else f"{dia}T{hora}-03:00",
        "data_hora_coleta": "2026-09-07T17:38:43-03:00",
        "titulo": titulo or f"Noticia {id_}", "fonte": "Fonte exemplo", "link": f"https://exemplo.invalid/{id_}",
        "prob_positivo": pp, "prob_neutro": f"{neutro:.4f}", "prob_negativo": pn,
        "origem": origem, "papel": papel, "tipo_conteudo": None, "evento": None, "qualidade": None,
        "data_publicacao": str(dia), "momento_pregao": "durante",
    }


def _acrescentar(*linhas: dict):
    """`alterar` do banco_teste: acrescenta estas linhas às de tests/dados/noticias.csv (papel vazio em todas)."""
    def _alterar(df: pd.DataFrame) -> pd.DataFrame:
        return pd.concat([df, pd.DataFrame(list(linhas), columns=df.columns)], ignore_index=True)
    return _alterar


def _so(*linhas: dict):
    """`alterar` do banco_teste: troca a tabela inteira por estas linhas."""
    def _alterar(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(list(linhas), columns=df.columns)
    return _alterar


SEM_PAPEL = _linha("p1", "PETR4", "10:00:00", DIA)
PROTAGONISTA = _linha("p2", "PETR4", "11:00:00", DIA, papel="protagonista")
ERRADA = _linha("p3", "PETR4", "12:00:00", DIA, papel="errada")


# ---------------------------------------------------------------- (a), (b), (c): leitura

def test_papel_errada_sai_e_papel_vazio_e_outros_papeis_ficam(banco_teste):
    ler = banco_teste(alterar={"v1-noticias": _acrescentar(SEM_PAPEL, PROTAGONISTA, ERRADA)})
    df = fontes.ler_noticias(ler=ler)

    ids = set(df["id"])
    assert "p3" not in ids
    assert {"p1", "p2"} <= ids
    assert df.loc[df["id"] == "p2", "papel"].iloc[0] == "protagonista"
    assert df.loc[df["id"] == "p1", "papel"].isna().all()
    assert "errada" not in set(df["papel"].dropna())
    assert df.attrs["papeis_ignorados"] == {"errada": 1}


def test_lista_vazia_nao_tira_nada(banco_teste):
    base = fontes.ler_noticias(ler=banco_teste(), papeis_ignorados=[])
    df = fontes.ler_noticias(ler=banco_teste(alterar={"v1-noticias": _acrescentar(ERRADA)}), papeis_ignorados=[])

    assert "p3" in set(df["id"])
    assert df.loc[df["id"] == "p3", "papel"].iloc[0] == "errada"
    assert len(df) == len(base) + 1
    assert df.attrs["papeis_ignorados"] == {}


def test_mapa_declara_so_a_papel_errada():
    assert fontes.papeis_ignorados() == ["errada"]


# ---------------------------------------------------------------- (d): tratar_noticias_lidas x ler_noticias

def test_tratar_e_ler_dao_o_mesmo_resultado_com_filtro_padrao(banco_teste):
    ler = banco_teste(alterar={"v1-noticias": _acrescentar(SEM_PAPEL, PROTAGONISTA, ERRADA)})
    colunas = fontes._conferir_tabela("noticias", ler)
    bruta = fontes._selecionar("noticias", colunas, [], None, ler)

    tratada = fontes.tratar_noticias_lidas(bruta, ler=ler)
    lida = fontes.ler_noticias(ler=ler)

    pd.testing.assert_frame_equal(tratada, lida)
    assert tratada.attrs == lida.attrs == {"origens_ignoradas": {}, "papeis_ignorados": {"errada": 1}}
    assert "p3" not in set(tratada["id"])


# ---------------------------------------------------------------- (e): ordem antes das repetidas

def test_copia_errada_mais_cedo_nao_vence_a_valida_na_deduplicacao(banco_teste):
    titulo = "Petrobras anuncia dividendos extraordinarios"
    errada = _linha("e_errada", "AAAA3", "09:00:00", DIA, papel="errada", titulo=titulo)
    valida = _linha("e_valida", "AAAA3", "11:00:00", DIA, papel="protagonista", titulo=titulo)
    ler = banco_teste(alterar={"v1-noticias": _acrescentar(errada, valida)})
    cnpj_de = mapas_cadastro(CADASTRO_INTEGRACAO)[1]

    com_filtro = fontes.ler_noticias(ler=ler)
    dedup, _ = exp_noticias.deduplicar(exp_noticias.ligar_empresa(com_filtro, cnpj_de, {}), PARAMS_EXP)
    assert set(dedup["id"]) & {"e_errada", "e_valida"} == {"e_valida"}

    # sem o filtro, a errada (mais cedo) é a que fica: é isso que o filtro evita
    sem_filtro = fontes.ler_noticias(ler=ler, papeis_ignorados=[])
    dedup_sem, _ = exp_noticias.deduplicar(exp_noticias.ligar_empresa(sem_filtro, cnpj_de, {}), PARAMS_EXP)
    assert set(dedup_sem["id"]) & {"e_errada", "e_valida"} == {"e_errada"}


# ---------------------------------------------------------------- (f): mesma notícia em duas classes da empresa

def test_mesma_noticia_em_duas_classes_da_mesma_empresa_fica_uma_vez(banco_teste):
    # mesmo id: AAAA3 (errada) e AAAA4 (protagonista); as duas são da mesma empresa (mesmo CNPJ)
    errada = _linha("f1", "AAAA3", "10:00:00", DIA, papel="errada")
    protagonista = _linha("f1", "AAAA4", "10:00:00", DIA, papel="protagonista")
    ler = banco_teste(alterar={"v1-noticias": _acrescentar(errada, protagonista)})
    cnpj_de = mapas_cadastro(CADASTRO_INTEGRACAO)[1]

    df = fontes.ler_noticias(ler=ler)
    assert (df["id"] == "f1").sum() == 1
    assert df.loc[df["id"] == "f1", "papel"].iloc[0] == "protagonista"
    assert df.attrs["papeis_ignorados"] == {"errada": 1}

    # sensibilidade: sem o filtro, o mesmo id aparece duas vezes na leitura
    sem = fontes.ler_noticias(ler=ler, papeis_ignorados=[])
    assert (sem["id"] == "f1").sum() == 2
    dedup, _ = exp_noticias.deduplicar(exp_noticias.ligar_empresa(df, cnpj_de, {}), PARAMS_EXP)
    assert (dedup["id"] == "f1").sum() == 1


# ---------------------------------------------------------------- (g): consumidores (fatos, dataset)

def _base_do_caso(cal: list) -> list[dict]:
    """Notícias do caso de integração, em texto de banco (t = cal[20]); sem papel errado."""
    return [
        _linha("b1", "AAAA4", "19:00:00", cal[20], pp="0.7", pn="0.1"),
        _linha("b2", "AAAA3", "10:00:00", cal[20], pp="0.3", pn="0.3"),
        _linha("b3", "BBBB3", None, cal[3], pp="0.5", pn="0.2", origem="cvm_ipe", papel="protagonista"),
        _linha("b4", "AAAA3", "09:00:00", cal[10], pp="0.6", pn="0.2"),
    ]


@pytest.fixture
def caso(banco_teste):
    i = integracao()
    return {"cal": i["cal"], "precos": i["precos"], "balancos": i["balancos"], "banco": banco_teste}


def _consumidores(linhas_extra: list[dict], caso: dict, papeis_ignorados: list[str] | None = None):
    """Leitura real (`ler_noticias` sobre o SQLite de teste) → dataset e janela de t.

    `papeis_ignorados` None usa a lista do mapa (["errada"]); `[]` deixa tudo entrar.
    """
    cal = caso["cal"]
    tabela = _base_do_caso(cal) + linhas_extra
    ler = caso["banco"](alterar={"v1-noticias": _so(*tabela)})
    noticias = fontes.ler_noticias(ler=ler, origens_ignoradas=[], papeis_ignorados=papeis_ignorados)
    mudancas = fontes.ler_mudancas(ler)
    dados = dados_de(cal, caso["precos"], CADASTRO_INTEGRACAO, noticias, caso["balancos"],
                     EXCLUSOES_INTEGRACAO, mudancas)
    df, info = montar_dataset(dados, cal)
    _, cnpj_de = mapas_cadastro(CADASTRO_INTEGRACAO)
    janela = fatos_noticias.noticias_da_janela(noticias, cal, cal[20], cal[21], cnpj_de, mudancas, PARAMS_EXP)
    return df, info, janela, noticias


def test_errada_nao_entra_na_janela_nem_no_noticias_dia_e_o_info_conta(caso):
    t = caso["cal"][20]
    # mesmo ticker e horário da b2 (dentro da janela de t): se entrasse, contaria no noticias_dia_qtd
    errada = _linha("g_errada", "AAAA3", "10:30:00", t, pp="0.95", pn="0.02", papel="errada")

    df_com, info, janela, noticias = _consumidores([errada], caso)
    df_sem, info_sem, _, noticias_sem = _consumidores([], caso)

    assert "g_errada" not in set(janela["id"])
    assert "g_errada" not in set(noticias["id"])
    assert set(NOTICIAS_DIA) <= set(df_com.columns)
    assert df_com[NOTICIAS_DIA].equals(df_sem[NOTICIAS_DIA])

    assert info["papel_ignoradas"] == 1
    assert info_sem["papel_ignoradas"] == 0
    assert info["papel_vazio"] == int(noticias["papel"].isna().sum())
    assert info["papel_vazio"] == info_sem["papel_vazio"]

    # sensibilidade: com a lista vazia a errada entra e muda o dataset
    df_vazia, info_vazia, _, _ = _consumidores([errada], caso, papeis_ignorados=[])
    assert not df_vazia[NOTICIAS_DIA].equals(df_sem[NOTICIAS_DIA])
    assert info_vazia["papel_ignoradas"] == 0


# ---------------------------------------------------------------- (h): etapa "juiza" na rotina

def test_juiza_esta_em_etapas_conferidas_do_yaml():
    assert "juiza" in carregar_parametros_rotina().etapas_conferidas


def test_juiza_falhou_gera_aviso_que_cita_a_etapa_e_a_rodada_segue():
    params = carregar_parametros_rotina()
    d, t = date(2026, 10, 26), date(2026, 10, 23)
    id_ = "2026-10-26-daily-080001"
    status = {e: "concluida" for e in ETAPAS_COLETA if e != "analise"}
    status.update(analise="pendente", juiza="falhou")
    pano = painel([execucao(id_, "2026-10-26 11:00:01", origem="cron", status="em_andamento")],
                  {id_: etapas(id_, status, {"entrega": "2026-10-26 12:00:00"})}, t)

    decisao = avaliar_painel(pano, d, t, params)

    assert decisao.acao == "gerar"
    assert decisao.motivo == "entrega_concluida"
    assert decisao.avisos == [
        "Coleta: etapa juiza falhou no daily de hoje; os dados podem estar incompletos."]
