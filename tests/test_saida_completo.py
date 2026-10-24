"""Testes da carga completa (seção 8.7 da especificação, decidida em 24/10/2026).

A carga completa (`gerar(..., completo=True)` e `python -m processamento.saida --completo`) gera os 9 pacotes
inteiros, sem o envio "quando muda", sem fechar dias, sem gravar registros do experimento e sem retreino.

Sem rede e sem banco real: `banco_teste` (SQLite de tests/dados), modelos pequenos salvos em tmp_path e
pastas temporárias. Nunca `fontes.criar_engine`: o fixture `_sem_banco_real` troca essa função por uma que interrompe o teste.
Cenário: D = 2025-10-22, t = 2025-10-21 (banco de teste).
"""

from __future__ import annotations

import importlib
import json
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from fabrica_saida import AGORA
from fabrica_treino import dataset_sintetico, params_teste
from processamento import fontes
from processamento.experimento import modelos, preparacao
from processamento.experimento import dataset as exp_dataset
from processamento.experimento.modelos import CHAVES_METADADOS
from processamento.saida import contrato
from processamento.saida.gerar import AVISO_COMPLETO, gerar, main

D = date(2025, 10, 22)
ORDEM_PACOTES = ["acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
                 "noticias_dia", "experimento_historico", "experimento_top"]
ARQUIVOS = [*ORDEM_PACOTES, "execucao"]
PARAMS = params_teste()  # teste final trancado (fim None)
PARAMS_FIM = params_teste(teste_final_fim=date(2025, 10, 21))  # produção simulada (teste final já passou)


class _BancoRealProibido(BaseException):
    """BaseException de propósito: o `except Exception` de cada pacote não pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Nenhum teste deste arquivo abre o banco da coleta."""
    def _proibido(*args, **kwargs):
        raise _BancoRealProibido("criar_engine chamado num teste: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


def _salvar_modelos(pasta: Path, inverter: bool = False) -> None:
    """Modelo 3 e modelo 1 pequenos de 2025-10 (provisórios, calibração não aprovada).

    `inverter`: treina com o alvo invertido, para que as probabilidades (e o top 5) mudem entre rodadas.
    """
    prep = preparacao.preparar(dataset_sintetico(n_pregoes=130, n_tickers=12))
    treino = preparacao.linhas_de_treino(prep)
    alvo = 1 - treino["alvo"] if inverter else treino["alvo"]
    for modelo_id, nome in (("3", "xgb-2025-10"), ("1", "xgb-m1-2025-10")):
        colunas = preparacao.colunas_do_modelo(modelo_id)
        modelo = modelos.treinar_xgb(treino[colunas], alvo, PARAMS.xgboost, PARAMS.semente)
        meta = {chave: None for chave in CHAVES_METADADOS}
        meta.update(modelo=modelo_id, colunas=colunas, provisorio=True, calibracao={"aprovada": False},
                    universo="composicao_atual")
        modelos.salvar_modelo(modelo, meta, pasta, nome)


@pytest.fixture(scope="module")
def modelos_dir(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelos")
    _salvar_modelos(pasta)
    return pasta


def _gerar_em(pasta: Path, *, ler, modelos: Path, registros: Path, estado: Path | None = None,
              usar_estado: bool = False, params=None, d: date = D, **kw) -> Path:
    """Chama `gerar` com as pastas dadas (saída é a pasta de D; registros e estado explícitos)."""
    return gerar(
        d, ler=ler, pasta_saida=pasta, pasta_modelos=modelos, pasta_registros=registros, pasta_estado=estado,
        usar_estado=usar_estado, agora=AGORA, existe_composicao=False,
        params_treino=PARAMS if params is None else params, **kw,
    )


def _preparar_estado(tmp: Path, banco_teste, modelos_dir: Path) -> tuple[Path, Path]:
    """Duas rodadas incrementais de D com o mesmo estado (a 2ª com a pasta de saída B2).

    Devolve (pasta do estado, pasta dos registros). Os registros do experimento são compartilhados (como na produção).
    """
    estado, registros = tmp / "estado", tmp / "registros"
    for pasta in ("B", "B2"):
        _gerar_em(tmp / pasta / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                  registros=registros, estado=estado, usar_estado=True)
    return estado, registros


def _arquivos(pasta: Path) -> dict[str, bytes]:
    """Nome e conteúdo (bytes) de cada arquivo da pasta (sem subpastas)."""
    return {p.name: p.read_bytes() for p in pasta.iterdir() if p.is_file()}


def _ler_json(pasta: Path, nome: str) -> dict:
    return json.loads((pasta / f"{nome}.json").read_text(encoding="utf-8"))


def _registros(pasta: Path, nome: str) -> list[dict]:
    return _ler_json(pasta, nome)["registros"]


def _execucao(pasta: Path) -> dict:
    return _registros(pasta, "execucao")[0]


def _chave_de(nome: str) -> list[str]:
    """Chave dos registros de cada pacote. `series_diarias` é uma série por ticker (sem campo `data`)."""
    return ["ticker"] if nome == "series_diarias" else contrato.CHAVES[nome]


def _com_pregao_de_22(df: pd.DataFrame) -> pd.DataFrame:
    """Banco com um pregão a mais (2025-10-22): cópia dos preços de 2025-10-21."""
    dia = df[df["data"] == "2025-10-21"].copy()
    dia["data"] = "2025-10-22"
    return pd.concat([df, dia], ignore_index=True)


def _contagens(pasta: Path) -> dict[str, int]:
    return {nome: len(_registros(pasta, nome)) for nome in ARQUIVOS}


# ---------------------------------------------------------------- caso 1: a carga completa repete a 1ª rodada

def test_caso_1_carga_completa_tem_o_mesmo_conteudo_da_rodada_sem_estado(banco_teste, tmp_path, modelos_dir):
    # A: sem estado (manda tudo): o gabarito da carga completa
    pasta_a = _gerar_em(tmp_path / "A" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                        registros=tmp_path / "A" / "registros")
    estado, registros = _preparar_estado(tmp_path, banco_teste, modelos_dir)

    # o achado: a 2ª rodada incremental vem sem estes pacotes (já enviados)
    pasta_b2 = tmp_path / "B2" / "saida" / D.isoformat()
    for nome in ("acoes", "series_diarias", "fundamentos_trimestrais", "proventos"):
        assert _registros(pasta_b2, nome) == [], nome

    pasta_c = _gerar_em(tmp_path / "C" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                        registros=registros, estado=estado, usar_estado=True, completo=True)

    assert _contagens(pasta_c) == _contagens(pasta_a)
    for nome in ARQUIVOS:
        regs_a, regs_c = _registros(pasta_a, nome), _registros(pasta_c, nome)
        chaves_a = {tuple(r[c] for c in _chave_de(nome)) for r in regs_a}
        chaves_c = {tuple(r[c] for c in _chave_de(nome)) for r in regs_c}
        assert chaves_c == chaves_a, nome
        assert _ler_json(pasta_c, nome)["removidos"] == [], nome
    assert all(s["substituir_serie"] is True for s in _registros(pasta_c, "series_diarias"))

    # gabarito absoluto (rodada de D = 2025-10-22, banco de teste)
    n = _contagens(pasta_c)
    assert n["acoes"] == 7
    assert n["series_diarias"] == 14
    assert n["mercado_dia"] == 1
    assert n["resumo_acao"] == 7
    assert n["fundamentos_trimestrais"] == 16
    assert n["proventos"] == 4
    assert n["noticias_dia"] == 7
    assert n["experimento_historico"] == 1
    assert n["experimento_top"] == 1
    assert n["execucao"] == 1


# ---------------------------------------------------------------- caso 2: o estado do envio não muda

def test_caso_2_carga_completa_nao_altera_nem_cria_nem_apaga_o_estado(banco_teste, tmp_path, modelos_dir):
    estado, registros = _preparar_estado(tmp_path, banco_teste, modelos_dir)
    antes = _arquivos(estado)
    assert antes, "o estado de teste não pode estar vazio"

    _gerar_em(tmp_path / "C" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
              registros=registros, estado=estado, usar_estado=True, completo=True)

    assert _arquivos(estado) == antes


# ---------------------------------------------------------------- caso 3: os registros do experimento não mudam

def _registro_pendente(tmp: Path, banco_teste, modelos_dir: Path) -> Path:
    """Registros com o top de D' = 2025-10-22 pendente, que a rodada normal de 2025-10-23 fecharia.

    Os modelos de teste são provisórios, e um top provisório nunca entra no histórico. Por isso, só neste teste,
    o registro gerado é marcado como válido (`valido_para_historico` e `modelo_provisorio`).
    """
    registros = tmp / "registros_base"
    _gerar_em(tmp / "base" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir, registros=registros)
    arquivo = registros / "2025-10-22.top.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    dados["pacote"]["valido_para_historico"] = True
    dados["pacote"]["modelo_provisorio"] = False
    arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return registros


def test_caso_3_carga_completa_nao_fecha_dias_nem_grava_registros(banco_teste, tmp_path, modelos_dir):
    d2 = date(2025, 10, 23)
    base = _registro_pendente(tmp_path, banco_teste, modelos_dir)

    # controle: a rodada normal de D2, com o teste final já passado, fecha o 2025-10-22
    controle = tmp_path / "controle" / "registros"
    shutil.copytree(base, controle)
    _gerar_em(tmp_path / "controle" / "saida" / d2.isoformat(), ler=banco_teste(alterar={"v1-precos": _com_pregao_de_22}),
              modelos=modelos_dir, registros=controle, params=PARAMS_FIM, d=d2)
    assert (controle / "2025-10-22.resultado.json").is_file()

    # carga completa de D2 sobre os mesmos registros
    registros = tmp_path / "completo" / "registros"
    shutil.copytree(base, registros)
    antes = _arquivos(registros)
    pasta_d2 = _gerar_em(tmp_path / "completo" / "saida" / d2.isoformat(),
                         ler=banco_teste(alterar={"v1-precos": _com_pregao_de_22}), modelos=modelos_dir,
                         registros=registros, params=PARAMS_FIM, d=d2, completo=True)

    assert list(registros.glob("*.resultado.json")) == []
    assert list(registros.glob("*.descartado.json")) == []
    assert not (registros / "2025-10-23.top.json").exists()
    assert _arquivos(registros) == antes
    assert len(_registros(pasta_d2, "experimento_top")) == 1

    # com `<D>.top.json` já gravado, o experimento_top da carga completa é o pacote do registro
    pasta_d1 = _gerar_em(tmp_path / "completo" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                         registros=registros, params=PARAMS_FIM, completo=True)
    registro = json.loads((registros / "2025-10-22.top.json").read_text(encoding="utf-8"))
    assert _registros(pasta_d1, "experimento_top")[0] == registro["pacote"]
    assert _arquivos(registros) == antes


# ---------------------------------------------------------------- caso 4: sem retreino

def test_caso_4_carga_completa_nunca_retreina(banco_teste, tmp_path, modelos_dir):
    chamadas: list[tuple] = []

    def retreinar(*args):
        chamadas.append(args)
        raise RuntimeError("retreino chamado na carga completa")

    pasta = _gerar_em(tmp_path / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                      registros=tmp_path / "registros", completo=True, retreinar=retreinar)

    assert chamadas == []
    assert not any(aviso.startswith("Retreino de") for aviso in _execucao(pasta)["avisos"])
    assert len(_registros(pasta, "experimento_top")) == 1


# ---------------------------------------------------------------- caso 5: execução e contrato

def test_caso_5_execucao_com_aviso_e_todos_os_arquivos_passam_no_contrato(banco_teste, tmp_path, modelos_dir):
    pasta_a = _gerar_em(tmp_path / "A" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                        registros=tmp_path / "A" / "registros")

    pasta = _gerar_em(tmp_path / "C" / "saida" / D.isoformat(), ler=banco_teste(), modelos=modelos_dir,
                      registros=tmp_path / "C" / "registros", completo=True)

    ex = _execucao(pasta)
    assert ex["status"] == _execucao(pasta_a)["status"] == "ok"
    assert AVISO_COMPLETO in ex["avisos"]
    assert not any(aviso.startswith("falha ao gerar") for aviso in ex["avisos"])
    for nome in ARQUIVOS:
        contrato.validar_lote(_ler_json(pasta, nome))


# ---------------------------------------------------------------- caso 6: CLI

def test_caso_6_cli_cria_os_dez_arquivos_na_pasta_dada(banco_teste, tmp_path, modelos_dir):
    raiz = tmp_path / "completa"
    argv = ["--data", "2025-10-22", "--completo", "--pasta", str(raiz), "--pasta-modelos", str(modelos_dir),
            "--pasta-registros", str(tmp_path / "registros")]

    assert main(argv, ler=banco_teste(), existe_composicao=False) == 0

    assert {p.name for p in (raiz / "2025-10-22").iterdir()} == {f"{nome}.json" for nome in ARQUIVOS}


def test_caso_6_cli_recusa_a_pasta_do_envio_diario_sem_gravar(banco_teste, tmp_path, modelos_dir, monkeypatch):
    envio = tmp_path / "envio"
    gerar_modulo = importlib.import_module("processamento.saida.gerar")
    monkeypatch.setattr(gerar_modulo, "carregar_parametros_saida", lambda *a, **k: SimpleNamespace(pasta=envio))
    argv = ["--data", "2025-10-22", "--completo", "--pasta", str(envio), "--pasta-modelos", str(modelos_dir),
            "--pasta-registros", str(tmp_path / "registros")]

    assert main(argv, ler=banco_teste(), existe_composicao=False) == 2
    assert not envio.exists()
