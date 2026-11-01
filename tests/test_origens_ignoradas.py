"""Origens ignoradas de `v1-noticias` (medida temporária de 28/10/2026, origem "wordpress").

A origem está em `origens_ignoradas` do mapa (fontes.yaml): passa pela conferência de valores permitidos,
sai da leitura depois do filtro de janela, é contada em `df.attrs` e avisada na saída (execucao.json) e no
diagnóstico (nota). Nenhum teste usa banco real ou rede: SQLite de tests/dados (`banco_teste`) e tabelas
montadas à mão, com tickers da fábrica.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fabrica_experimento import CADASTRO_INTEGRACAO, EXCLUSOES_INTEGRACAO, dados_de, integracao
from fabrica_saida import AGORA, insumos_de_teste
from fabrica_treino import dataset_sintetico, params_teste

from processamento import fontes
from processamento.diagnostico import consultas as c
from processamento.experimento import modelos, preparacao
from processamento.experimento.dataset import montar_dataset
from processamento.experimento.modelos import CHAVES_METADADOS
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.experimento.preparacao import NOTICIAS_DIA
from processamento.fatos import noticias as fatos_noticias
from processamento.fatos.precos import mapas_cadastro
from processamento.fontes import ErroLeitura
from processamento.saida.gerar import AVISO_ORIGEM_IGNORADA, gerar
from processamento.saida.parametros import carregar_parametros_saida

SP = ZoneInfo("America/Sao_Paulo")
PARAMS_EXP = carregar_parametros_experimento()
PARAMS_TREINO = params_teste()  # teste final trancado (fim None)
SAIDA_SIM = dataclasses.replace(carregar_parametros_saida(), publicar_top_provisorio=True)
D = date(2025, 10, 22)
ORDEM_PACOTES = ["acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
                 "noticias_dia", "experimento_historico", "experimento_top"]
COLUNAS_TABELA = [
    "id", "ticker", "data_hora_publicacao", "data_hora_coleta", "titulo", "fonte", "link",
    "prob_positivo", "prob_neutro", "prob_negativo", "origem", "papel", "tipo_conteudo", "evento",
    "qualidade", "data_publicacao", "momento_pregao",
]
AVISO_WORDPRESS = "3 notícias da origem wordpress ignoradas (fonte nova, aguardando definição)"


class _BancoRealProibido(BaseException):
    """BaseException de propósito: o `except Exception` de cada pacote não pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Nenhum teste deste arquivo abre o banco da coleta (mesmo padrão de test_saida_gerar)."""
    def _proibido(*args, **kwargs):
        raise _BancoRealProibido("criar_engine chamado num teste: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


# ---------------------------------------------------------------- linhas e tabelas de teste

def _linha(id_: str, ticker: str, hora: str | None, dia, *, pp: str = "0.2", pn: str = "0.3",
           origem: str = "google_news", papel: str | None = None, tipo: str | None = None) -> dict:
    """Uma linha de `v1-noticias` como vem do banco (textos). Sem `hora`, a publicação não tem horário."""
    neutro = max(0.0, 1 - float(pp) - float(pn))
    return {
        "id": id_, "ticker": ticker,
        "data_hora_publicacao": None if hora is None else f"{dia}T{hora}-03:00",
        "data_hora_coleta": "2026-09-07T17:38:43-03:00",
        "titulo": f"Noticia {id_}", "fonte": "Fonte exemplo", "link": f"https://exemplo.invalid/{id_}",
        "prob_positivo": pp, "prob_neutro": f"{neutro:.4f}", "prob_negativo": pn,
        "origem": origem, "papel": papel, "tipo_conteudo": tipo, "evento": None, "qualidade": None,
        "data_publicacao": str(dia), "momento_pregao": "durante",
    }


def _acrescentar(*linhas: dict):
    """`alterar` do banco_teste: acrescenta estas linhas às de tests/dados/noticias.csv."""
    def _alterar(df: pd.DataFrame) -> pd.DataFrame:
        return pd.concat([df, pd.DataFrame(list(linhas), columns=df.columns)], ignore_index=True)
    return _alterar


def _so(*linhas: dict):
    """`alterar` do banco_teste: troca a tabela inteira por estas linhas."""
    def _alterar(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(list(linhas), columns=df.columns)
    return _alterar


# wordpress nos dados de tests/dados (datas de 2025-10, como o restante da base de teste)
W1 = _linha("w000001", "PETR4", "10:00:00", "2025-10-17", origem="wordpress", pp="0.9", pn="0.05")
W2 = _linha("w000002", "PETR3", "10:00:00", "2025-10-20", origem="wordpress", pp="0.8", pn="0.1")
W3 = _linha("w000003", "PETR4", "19:00:00", "2025-10-21", origem="wordpress", pp="0.95", pn="0.02")


# ---------------------------------------------------------------- (a), (b), (c): leitura

def test_origens_ignoradas_vem_do_mapa():
    # o mapa de produção não ignora nenhuma origem (lista vazia = todas entram; wordpress entra)
    assert fontes.origens_ignoradas() == []


def test_wordpress_nao_levanta_e_sai_do_resultado(banco_teste):
    # o mecanismo é testado com a lista explícita (o mapa agora está vazio)
    base = fontes.ler_noticias(ler=banco_teste(), origens_ignoradas=["wordpress"])
    df = fontes.ler_noticias(ler=banco_teste(alterar={"v1-noticias": _acrescentar(W1)}),
                             origens_ignoradas=["wordpress"])

    assert "w000001" not in set(df["id"])
    assert "wordpress" not in set(df["origem"])
    assert len(df) == len(base)
    assert df.attrs["origens_ignoradas"] == {"wordpress": 1}


def test_wordpress_fora_da_janela_ate_nao_entra_na_contagem(banco_teste):
    ate = pd.Timestamp("2025-10-17 23:59:59", tz=SP)
    lista = ["wordpress"]

    # a única wordpress é de 2025-10-20, depois de `ate`: a janela já a deixa de fora
    so_depois = banco_teste(alterar={"v1-noticias": _acrescentar(W2)})
    assert fontes.ler_noticias(ate=ate, ler=so_depois, origens_ignoradas=lista).attrs["origens_ignoradas"] == {}

    # com uma dentro da janela e outra fora, só a de dentro conta
    ambas = banco_teste(alterar={"v1-noticias": _acrescentar(W1, W2)})
    assert fontes.ler_noticias(ate=ate, ler=ambas, origens_ignoradas=lista).attrs["origens_ignoradas"] == {
        "wordpress": 1}


def test_lista_vazia_mantem_o_comportamento_antigo(banco_teste, monkeypatch):
    monkeypatch.setitem(fontes._entrada("noticias"), "origens_ignoradas", [])
    assert fontes.origens_ignoradas() == []

    df = fontes.ler_noticias(ler=banco_teste(alterar={"v1-noticias": _acrescentar(W1)}))

    assert "w000001" in set(df["id"])
    assert df.loc[df["id"] == "w000001", "origem"].iloc[0] == "wordpress"
    assert df.attrs["origens_ignoradas"] == {}


def test_valor_realmente_desconhecido_continua_erro(banco_teste):
    desconhecida = _linha("x000001", "PETR4", "10:00:00", "2025-10-17", origem="xyz")
    with pytest.raises(ErroLeitura) as info:
        fontes.ler_noticias(ler=banco_teste(alterar={"v1-noticias": _acrescentar(desconhecida)}))
    assert "origem" in str(info.value)
    assert "xyz" in str(info.value)


# ---------------------------------------------------------------- (d): consumidores (fatos, tom, dataset)

def _base_do_caso(cal: list) -> list[dict]:
    """Notícias do caso de integração, em texto de banco (t = cal[20]); sem nenhuma wordpress."""
    return [
        _linha("b1", "AAAA4", "19:00:00", cal[20], pp="0.7", pn="0.1", papel=None),
        _linha("b2", "AAAA3", "10:00:00", cal[20], pp="0.3", pn="0.3"),
        _linha("b3", "BBBB3", None, cal[3], pp="0.5", pn="0.2", origem="cvm_ipe", papel="protagonista"),
        _linha("b4", "AAAA3", "09:00:00", cal[10], pp="0.6", pn="0.2"),
    ]


def _consumidores(linhas_extra: list[dict], caso: dict, origens_ignoradas: list[str] | None = None):
    """Leitura real (`ler_noticias` sobre o SQLite de teste) → dataset do experimento e janela de t.

    Por padrão, wordpress fica de fora (lista explícita); `origens_ignoradas=[]` deixa tudo entrar.
    """
    cal = caso["cal"]
    tabela = _base_do_caso(cal) + linhas_extra
    ler = caso["banco"](alterar={"v1-noticias": _so(*tabela)})
    lista = ["wordpress"] if origens_ignoradas is None else origens_ignoradas
    noticias = fontes.ler_noticias(ler=ler, origens_ignoradas=lista)
    mudancas = fontes.ler_mudancas(ler)
    dados = dados_de(cal, caso["precos"], CADASTRO_INTEGRACAO, noticias, caso["balancos"],
                     EXCLUSOES_INTEGRACAO, mudancas)
    df, _ = montar_dataset(dados, cal)
    _, cnpj_de = mapas_cadastro(CADASTRO_INTEGRACAO)
    janela = fatos_noticias.noticias_da_janela(noticias, cal, cal[20], cal[21], cnpj_de, mudancas, PARAMS_EXP)
    return df, janela


@pytest.fixture
def caso(banco_teste):
    i = integracao()
    return {"cal": i["cal"], "precos": i["precos"], "balancos": i["balancos"], "banco": banco_teste}


def test_wordpress_nao_muda_fatos_nem_dataset_com_lista_padrao(caso):
    df_sem, janela_sem = _consumidores([], caso)
    df_com, janela_com = _consumidores([_linha("w1", "AAAA4", "19:00:00", caso["cal"][20], pp="0.95",
                                                pn="0.02", origem="wordpress")], caso)

    pd.testing.assert_frame_equal(df_com, df_sem)
    pd.testing.assert_frame_equal(janela_com, janela_sem)


def test_wordpress_muda_fatos_e_dataset_com_lista_vazia(caso):
    """Prova de sensibilidade: com a lista vazia a mesma notícia entra e muda o tom e a janela."""
    df_sem, janela_sem = _consumidores([], caso)
    df_vazia, janela_vazia = _consumidores([_linha("w1", "AAAA4", "19:00:00", caso["cal"][20], pp="0.95",
                                                    pn="0.02", origem="wordpress")], caso, origens_ignoradas=[])

    assert set(NOTICIAS_DIA) <= set(df_sem.columns)
    assert not df_vazia[NOTICIAS_DIA].equals(df_sem[NOTICIAS_DIA])
    assert not janela_vazia.equals(janela_sem)


# ---------------------------------------------------------------- (e): aviso (insumos e execucao.json)

def test_ler_insumos_preenche_noticias_ignoradas(banco_teste, monkeypatch):
    monkeypatch.setitem(fontes._entrada("noticias"), "origens_ignoradas", ["wordpress"])
    ler = banco_teste(alterar={"v1-noticias": _acrescentar(W1, W2, W3)})
    ins = insumos_de_teste(ler)
    assert ins.noticias_ignoradas == {"wordpress": 3}
    assert "wordpress" not in set(ins.noticias["origem"])


def test_ler_insumos_sem_wordpress_fica_vazio(banco_teste):
    assert insumos_de_teste(banco_teste()).noticias_ignoradas == {}


@pytest.fixture(scope="module")
def modelos_dir(tmp_path_factory):
    """Modelo 3 e modelo 1 pequenos (provisórios), como em test_saida_gerar."""
    pasta = tmp_path_factory.mktemp("modelos_origens")
    prep = preparacao.preparar(dataset_sintetico(n_pregoes=130, n_tickers=12))
    treino = preparacao.linhas_de_treino(prep)
    for modelo_id, nome in (("3", "xgb-2025-10"), ("1", "xgb-m1-2025-10")):
        colunas = preparacao.colunas_do_modelo(modelo_id)
        modelo = modelos.treinar_xgb(treino[colunas], treino["alvo"], PARAMS_TREINO.xgboost, PARAMS_TREINO.semente)
        meta = {chave: None for chave in CHAVES_METADADOS}
        meta.update(modelo=modelo_id, colunas=colunas, provisorio=True, calibracao={"aprovada": False},
                    universo="composicao_atual")
        modelos.salvar_modelo(modelo, meta, pasta, nome)
    return pasta


def _gerar(tmp: Path, ler, modelos: Path) -> Path:
    """`gerar` com pastas em `tmp`, como em test_saida_gerar._gerar."""
    return gerar(
        D, ler=ler, pasta_saida=tmp / "saida" / D.isoformat(), pasta_modelos=modelos,
        pasta_registros=tmp / "registros", pasta_estado=tmp / "estado", usar_estado=False,
        agora=AGORA, existe_composicao=False, params_treino=PARAMS_TREINO, params_saida=SAIDA_SIM,
    )


def _pacotes(pasta: Path) -> dict:
    return {nome: json.loads((pasta / f"{nome}.json").read_text(encoding="utf-8")) for nome in ORDEM_PACOTES}


def _avisos(pasta: Path) -> list[str]:
    return json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))["registros"][0]["avisos"]


def test_gerar_avisa_origem_ignorada_no_execucao(banco_teste, tmp_path, modelos_dir, monkeypatch):
    monkeypatch.setitem(fontes._entrada("noticias"), "origens_ignoradas", ["wordpress"])
    pasta = _gerar(tmp_path / "com", banco_teste(alterar={"v1-noticias": _acrescentar(W1, W2, W3)}), modelos_dir)

    assert AVISO_ORIGEM_IGNORADA.format(n=3, origem="wordpress") == AVISO_WORDPRESS
    assert AVISO_WORDPRESS in _avisos(pasta)


def test_gerar_sem_wordpress_nao_avisa(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path / "sem", banco_teste(), modelos_dir)
    assert not any("ignoradas (fonte nova" in aviso for aviso in _avisos(pasta))


# ---------------------------------------------------------------- (d) no pacote noticias_dia (gerar inteiro)

def test_pacotes_da_saida_nao_mudam_com_wordpress(banco_teste, tmp_path, modelos_dir, monkeypatch):
    """Com wordpress na lista de ignoradas, os pacotes (noticias_dia incluso) são iguais aos da base sem ela."""
    monkeypatch.setitem(fontes._entrada("noticias"), "origens_ignoradas", ["wordpress"])
    sem = _gerar(tmp_path / "sem", banco_teste(), modelos_dir)
    com = _gerar(tmp_path / "com", banco_teste(alterar={"v1-noticias": _acrescentar(W1, W2, W3)}), modelos_dir)

    assert _pacotes(com) == _pacotes(sem)


def test_pacote_noticias_dia_muda_com_lista_vazia(banco_teste, tmp_path, modelos_dir, monkeypatch):
    """Prova de sensibilidade: com a lista vazia a wordpress entra no noticias_dia."""
    sem = _gerar(tmp_path / "sem", banco_teste(), modelos_dir)
    monkeypatch.setitem(fontes._entrada("noticias"), "origens_ignoradas", [])
    vazia = _gerar(tmp_path / "vazia", banco_teste(alterar={"v1-noticias": _acrescentar(W1, W2, W3)}), modelos_dir)

    assert _pacotes(vazia)["noticias_dia"] != _pacotes(sem)["noticias_dia"]


# ---------------------------------------------------------------- (f): diagnóstico

def _ler_distintos(valores_origem: list[tuple[str, int]]):
    """Só a coluna `origem` tem valores; as outras colunas com lista permitida vêm vazias."""
    def ler(sql):
        if "`origem`" in sql:
            return pd.DataFrame({"valor": [v for v, _ in valores_origem], "n": [n for _, n in valores_origem]})
        return pd.DataFrame({"valor": [], "n": []})
    return ler


def test_diagnostico_wordpress_nao_diverge_e_tem_nota_com_contagem():
    mapa = copy.deepcopy(fontes.carregar_mapa())
    mapa["tabelas"]["noticias"]["origens_ignoradas"] = ["wordpress"]
    secao = c.secao_distintos(_ler_distintos([("google_news", 10), ("wordpress", 3)]), mapa, {"v1-noticias"})

    assert not [d for d in secao["divergencias"] if d["tema"] == "valor_desconhecido"]
    assert (
        "v1-noticias.origem = wordpress: 3 linhas ignoradas pela leitura "
        "(origens_ignoradas; fonte nova, aguardando definição)"
    ) in secao["notas"]


def test_diagnostico_origem_realmente_desconhecida_diverge():
    secao = c.secao_distintos(
        _ler_distintos([("google_news", 10), ("xyz", 1)]), fontes.carregar_mapa(), {"v1-noticias"}
    )

    divergencias = [d for d in secao["divergencias"] if d["tema"] == "valor_desconhecido"]
    assert len(divergencias) == 1
    assert "origem: xyz" in divergencias[0]["detalhe"]
    assert not any("ignoradas pela leitura" in n for n in secao["notas"])
