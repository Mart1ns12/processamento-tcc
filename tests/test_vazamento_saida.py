"""Testes de vazamento temporal da saída (plano da etapa 7, seção 6; Fase 8).

Teste de veneno: a mesma rodada de D = 2025-10-22 com e sem dados "do futuro" (preços, balanço, provento,
notícias e CDI de 2025-10-22) tem que gerar arquivos iguais byte a byte, menos `execucao.json`.
Os testes explícitos conferem os valores esperados da seção 6 numa rodada envenenada.
Sem rede e sem banco real: `banco_teste` (SQLite de tests/dados) e modelos pequenos em tmp_path.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fabrica_saida import AGORA
from fabrica_treino import dataset_sintetico, params_teste
from processamento.experimento.preparacao import VERSAO_PREPARACAO
from processamento import fontes
from processamento.experimento import modelos, preparacao
from processamento.experimento.modelos import CHAVES_METADADOS
from processamento.saida.gerar import gerar
from processamento.saida.parametros import carregar_parametros_saida

D = date(2025, 10, 22)
PARAMS = params_teste()
FUTURO = "2025-10-22"


class _BancoRealProibido(BaseException):
    """BaseException de propósito: o `except Exception` de cada pacote não pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    def _proibido(*args, **kwargs):
        raise _BancoRealProibido("criar_engine chamado num teste: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


@pytest.fixture(scope="module")
def modelos_dir(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelos")
    prep = preparacao.preparar(dataset_sintetico(n_pregoes=130, n_tickers=12))
    treino = preparacao.linhas_de_treino(prep)
    for modelo_id, nome in (("3", "xgb-2025-10"), ("1", "xgb-m1-2025-10")):
        colunas = preparacao.colunas_do_modelo(modelo_id)
        modelo = modelos.treinar_xgb(treino[colunas], treino["alvo"], PARAMS.xgboost, PARAMS.semente)
        meta = {**{chave: None for chave in CHAVES_METADADOS}, "versao_preparacao": VERSAO_PREPARACAO}
        meta.update(modelo=modelo_id, colunas=colunas, provisorio=True, calibracao={"aprovada": False},
                    universo="composicao_atual")
        modelos.salvar_modelo(modelo, meta, pasta, nome)
    return pasta


# ---------------------------------------------------------------- envenenamento (dados de 2025-10-22)

def _linhas(df: pd.DataFrame, linhas: list[dict]) -> pd.DataFrame:
    """Acrescenta linhas (texto) às colunas de `df`; o que não for dado fica vazio."""
    return pd.concat([df, pd.DataFrame(linhas).reindex(columns=df.columns)], ignore_index=True)


def _precos_de_22(df: pd.DataFrame) -> pd.DataFrame:
    tickers = df["ticker"].drop_duplicates().tolist()
    return _linhas(df, [{"data": FUTURO, "ticker": t, "abertura": "99", "maxima": "99", "minima": "99",
                         "fechamento": "99", "fechamento_ajustado": "99", "volume": "1"} for t in tickers])


def _balanco_de_22(df: pd.DataFrame) -> pd.DataFrame:
    return _linhas(df, [{"cnpj": "33000167000101", "tipo_documento": "ITR", "data_inicio_periodo": "2025-07-01",
                         "data_fim_periodo": "2025-09-30", "data_entrega": FUTURO, "receita_liquida": "999999",
                         "lucro_bruto": "999999", "lucro_liquido": "999999", "patrimonio_liquido": "999999"}])


def _provento_de_22(df: pd.DataFrame) -> pd.DataFrame:
    return _linhas(df, [{"ticker": "PETR4", "tipo": "DIVIDENDO", "data_com": FUTURO, "valor_por_acao": "50"}])


def _cdi_de_22(df: pd.DataFrame) -> pd.DataFrame:
    return _linhas(df, [{"data": FUTURO, "indice": "CDI", "valor": "0.09"}])


def _noticia(id_: str, ticker: str, hora: str, prob: str = "0.99", titulo: str = "Noticia futura") -> dict:
    return {"id": id_, "ticker": ticker, "data_hora_publicacao": f"{FUTURO}T{hora}-03:00",
            "data_hora_coleta": "2026-09-07T17:38:43-03:00", "titulo": titulo, "fonte": "Fonte exemplo",
            "link": f"https://exemplo.invalid/{id_}", "prob_positivo": prob, "prob_neutro": "0.005",
            "prob_negativo": "0.005", "origem": "google_news", "data_publicacao": FUTURO,
            "momento_pregao": "durante"}


def _noticias_de_22(df: pd.DataFrame) -> pd.DataFrame:
    return _linhas(df, [_noticia("n000090", "PETR4", "08:00:01"), _noticia("n000091", "PETR4", "09:00:00")])


def _bordas_de_22(df: pd.DataFrame) -> pd.DataFrame:
    """Notícias da borda da janela do dia (uso só nos testes explícitos; ABEV3 não tem outras)."""
    return _linhas(df, [_noticia("n000101", "ABEV3", "07:59:59", "0.7", "Borda antes"),
                        _noticia("n000102", "ABEV3", "08:00:00", "0.7", "Borda inclusiva"),
                        _noticia("n000103", "ABEV3", "08:00:01", "0.7", "Borda depois")])


def _envenenado(banco_teste, extra_noticias=None):
    alterar = {
        "v1-precos": _precos_de_22, "v1-balancos": _balanco_de_22, "v1-proventos": _provento_de_22,
        "v1-indices": _cdi_de_22,
        "v1-noticias": (lambda df: extra_noticias(_noticias_de_22(df))) if extra_noticias else _noticias_de_22,
    }
    return banco_teste(alterar=alterar)


# Publica o top provisório para o veneno cobrir também experimento_top e experimento_historico (9 arquivos).
SAIDA_PUBLICA = dataclasses.replace(carregar_parametros_saida(), publicar_top_provisorio=True)


def _gerar(raiz: Path, ler, modelos_pasta: Path, usar_estado: bool = False) -> Path:
    return gerar(
        D, ler=ler, pasta_saida=raiz / "saida" / D.isoformat(), pasta_modelos=modelos_pasta,
        pasta_registros=raiz / "registros", pasta_estado=raiz / "estado", usar_estado=usar_estado,
        agora=AGORA, existe_composicao=False, params_treino=PARAMS, params_saida=SAIDA_PUBLICA,
    )


def _ler_json(pasta: Path, nome: str) -> dict:
    return json.loads((pasta / f"{nome}.json").read_text(encoding="utf-8"))


def _registros(pasta: Path, nome: str) -> list[dict]:
    return _ler_json(pasta, nome)["registros"]


def _por(registros: list[dict], **campos) -> dict:
    return next(r for r in registros if all(r[k] == v for k, v in campos.items()))


# ---------------------------------------------------------------- teste de veneno

def test_veneno_arquivos_iguais_byte_a_byte_menos_execucao(banco_teste, tmp_path, modelos_dir):
    limpo = _gerar(tmp_path / "limpo", banco_teste(), modelos_dir)
    envenenado = _gerar(tmp_path / "veneno", _envenenado(banco_teste), modelos_dir)

    nomes = sorted(p.name for p in limpo.iterdir() if p.name != "execucao.json")
    assert nomes == sorted(p.name for p in envenenado.iterdir() if p.name != "execucao.json")
    assert len(nomes) == 9
    for nome in nomes:
        assert (limpo / nome).read_bytes() == (envenenado / nome).read_bytes(), nome


# ---------------------------------------------------------------- testes explícitos (seção 6)

def test_resumo_petr4_nao_usa_balanco_nem_lucro_do_futuro(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, _envenenado(banco_teste), modelos_dir)

    petr4 = _por(_registros(pasta, "resumo_acao"), ticker="PETR4")
    assert petr4["balanco_referencia"]["data_entrega"] == "2025-08-10"
    assert petr4["pl"]["valor"] == pytest.approx(6.896551724137931, rel=1e-9)
    assert petr4["pl"]["valor"] != pytest.approx(999999)


def test_fundamentos_sem_entrega_depois_de_t(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, _envenenado(banco_teste), modelos_dir)

    entregas = [r["data_entrega"] for r in _registros(pasta, "fundamentos_trimestrais")]
    assert entregas
    assert max(entregas) <= "2025-10-21"


def test_series_terminam_em_t(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, _envenenado(banco_teste), modelos_dir)

    datas = [d for serie in _registros(pasta, "series_diarias") for d in serie["datas"]]
    assert datas
    assert max(datas) == "2025-10-21"


def test_proventos_sem_data_com_depois_de_t(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, _envenenado(banco_teste), modelos_dir)

    com = [r["data_com"] for r in _registros(pasta, "proventos")]
    assert com
    assert max(com) <= "2025-10-21"


def test_noticias_de_petr4_so_a_de_t(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, _envenenado(banco_teste), modelos_dir)

    petr4 = _por(_registros(pasta, "noticias_dia"), ticker="PETR4")
    assert [item["id"] for item in petr4["itens"]] == ["n000008"]


def test_bordas_da_janela_de_noticias(banco_teste, tmp_path, modelos_dir):
    """07:59:59 e 08:00:00 de D entram (08:00 é inclusivo); 08:00:01 não."""
    pasta = _gerar(tmp_path, _envenenado(banco_teste, extra_noticias=_bordas_de_22), modelos_dir)

    abev3 = _por(_registros(pasta, "noticias_dia"), ticker="ABEV3")
    ids = [item["id"] for item in abev3["itens"]]
    assert "n000101" in ids
    assert "n000102" in ids
    assert "n000103" not in ids


def test_cdi_do_dia_e_o_de_t(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, _envenenado(banco_teste), modelos_dir)

    mercado = _registros(pasta, "mercado_dia")[0]
    assert mercado["cdi_data"] == "2025-10-21"
    assert mercado["cdi_dia"]["valor"] == pytest.approx(0.0006, rel=1e-9)
