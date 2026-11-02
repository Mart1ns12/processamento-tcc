"""Testes da orquestração `gerar` e da CLI (plano da etapa 7, Fase 8; casos 1 a 9).

Sem rede e sem banco real: `banco_teste` (SQLite de tests/dados), modelos pequenos salvos em tmp_path e
pastas temporárias. Nunca `fontes.criar_engine`: o caso 9 troca essa função por uma que interrompe o teste.
Cenário: D = 2025-10-22, t = 2025-10-21 (banco de teste).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fabrica_saida import AGORA
from fabrica_treino import dataset_sintetico, params_teste
from processamento.experimento.preparacao import VERSAO_PREPARACAO
from processamento import fontes
from processamento.experimento import modelos, preparacao
from processamento.experimento import dataset as exp_dataset
from processamento.experimento.modelos import CHAVES_METADADOS
from processamento.saida import contrato, pacotes_experimento
from processamento.saida.gerar import NOTA_TOP_NAO_PUBLICADO, _limpar_pacotes, gerar, main, registrar_execucao
from processamento.saida.insumos import ErroSaida
from processamento.saida.parametros import carregar_parametros_saida

D = date(2025, 10, 22)
ORDEM_PACOTES = ["acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
                 "noticias_dia", "experimento_historico", "experimento_top"]
ARQUIVOS = [*ORDEM_PACOTES, "execucao"]
COLETA_NAO_CONSULTADA = {"consultado": False, "nota": "gatilho da coleta não consultado (etapa 8)"}
PARAMS = params_teste()  # teste final trancado (fim None)
SAIDA_NAO = dataclasses.replace(carregar_parametros_saida(), publicar_top_provisorio=False)
SAIDA_SIM = dataclasses.replace(carregar_parametros_saida(), publicar_top_provisorio=True)
SETE = ORDEM_PACOTES[:-2]  # sem os dois pacotes do experimento (top não publicado)


class _BancoRealProibido(BaseException):
    """BaseException de propósito: o `except Exception` de cada pacote não pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    """Caso 9: nenhum teste deste arquivo abre o banco da coleta."""
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
        meta = {**{chave: None for chave in CHAVES_METADADOS}, "versao_preparacao": VERSAO_PREPARACAO}
        meta.update(modelo=modelo_id, colunas=colunas, provisorio=True, calibracao={"aprovada": False},
                    universo="composicao_atual")
        modelos.salvar_modelo(modelo, meta, pasta, nome)


@pytest.fixture(scope="module")
def modelos_dir(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelos")
    _salvar_modelos(pasta)
    return pasta


@pytest.fixture(scope="module")
def modelos_invertidos_dir(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelos_invertidos")
    _salvar_modelos(pasta, inverter=True)
    return pasta


def _gerar(tmp: Path, ler, *, modelos: Path, d: date = D, usar_estado: bool = False, params=None, **kw) -> Path:
    """Chama `gerar` com todas as pastas em `tmp` (saída, registros e estado)."""
    kw.setdefault("params_saida", SAIDA_SIM)  # o yaml real traz publicar_top_provisorio: false; estes testes esperam os 10
    return gerar(
        d, ler=ler, pasta_saida=tmp / "saida" / d.isoformat(), pasta_modelos=modelos,
        pasta_registros=tmp / "registros", pasta_estado=tmp / "estado", usar_estado=usar_estado,
        agora=AGORA, existe_composicao=False, params_treino=PARAMS if params is None else params, **kw,
    )


def _ler_json(pasta: Path, nome: str) -> dict:
    return json.loads((pasta / f"{nome}.json").read_text(encoding="utf-8"))


def _registros(pasta: Path, nome: str) -> list[dict]:
    return _ler_json(pasta, nome)["registros"]


def _execucao(pasta: Path) -> dict:
    return _registros(pasta, "execucao")[0]


def _por(registros: list[dict], **campos) -> dict:
    return next(r for r in registros if all(r[k] == v for k, v in campos.items()))


def _com_pregao_de_22(df: pd.DataFrame) -> pd.DataFrame:
    """Banco com um pregão a mais (2025-10-22): cópia dos preços de 2025-10-21."""
    dia = df[df["data"] == "2025-10-21"].copy()
    dia["data"] = "2025-10-22"
    return pd.concat([df, dia], ignore_index=True)


# ---------------------------------------------------------------- caso 1: os 10 arquivos

def test_caso_1_gera_os_dez_arquivos_e_todos_passam_no_contrato(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir)

    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in ARQUIVOS}
    for nome in ARQUIVOS:
        contrato.validar_lote(_ler_json(pasta, nome))
    assert list(pasta.glob("*.tmp")) == []


# ---------------------------------------------------------------- caso 2: gabaritos (amostra da seção 4)

def test_caso_2_gabaritos_de_amostra(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir)

    petr4 = _por(_registros(pasta, "resumo_acao"), ticker="PETR4")
    assert petr4["data_referencia"] == "2025-10-21"
    assert petr4["pl"]["valor"] == pytest.approx(6.896551724137931, rel=1e-9)
    assert petr4["pl"]["status"] == "ok"
    assert petr4["pvp"]["valor"] == pytest.approx(0.8333333333333334, rel=1e-9)
    assert petr4["dividend_yield"]["valor"] == pytest.approx(0.05, rel=1e-9)
    assert petr4["balanco_referencia"]["data_entrega"] == "2025-08-10"

    mercado = _registros(pasta, "mercado_dia")[0]
    assert mercado["data_referencia"] == "2025-10-21"
    assert mercado["cdi_dia"]["valor"] == pytest.approx(0.0006, rel=1e-9)
    assert mercado["cdi_data"] == "2025-10-21"
    assert mercado["ipca_ate"]["valor"] == "2025-09"
    assert mercado["ipca_ate"]["status"] == "ok"

    top = _registros(pasta, "experimento_top")[0]
    assert top["data_referencia"] == "2025-10-22"
    assert top["pregao_previsto"] == "2025-10-22"
    assert top["pregao_base"] == "2025-10-21"
    assert top["valido_para_historico"] is False
    assert top["modelo_versao"] == "xgb-2025-10"
    assert top["modelo_provisorio"] is True
    assert top["selo"] == "em_avaliacao"
    assert top["ranking"], "o ranking não pode estar vazio"
    for item in top["ranking"]:
        assert item["chance"]["valor"] is None
        assert item["chance"]["status"] == "calibracao_nao_conferida"
        assert item["chance"]["exibir"] is False
    assert any(a == pacotes_experimento.AVISOS["provisorio_sem_periodo"] for a in top["avisos"])
    assert pacotes_experimento.AVISOS["antes_producao"] in top["avisos"]

    hist = _registros(pasta, "experimento_historico")[0]
    assert hist["data_referencia"] == "2025-10-22"
    assert hist["dia"] is None
    assert hist["resumo"]["n_dias"] == 0
    assert hist["resumo"]["taxa_acerto"]["valor"] is None
    assert hist["resumo"]["taxa_acerto"]["status"] == "indisponivel"

    ex = _execucao(pasta)
    assert ex["data_referencia"] == "2025-10-22"
    assert ex["rodada"] == 1
    assert ex["status"] == "ok"
    assert ex["fim"] is not None
    assert ex["coleta_status"] == COLETA_NAO_CONSULTADA
    # os avisos do experimento (provisório sem período na fixture, antes da produção) entram; falha de pacote não pode haver
    assert any(a == pacotes_experimento.AVISOS["provisorio_sem_periodo"] for a in ex["avisos"])
    assert not any(aviso.startswith("falha ao gerar") for aviso in ex["avisos"])


# ---------------------------------------------------------------- caso 3: ordem

def test_caso_3_ordem_dos_pacotes_enviados(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir)

    enviados = _execucao(pasta)["pacotes_enviados"]
    assert [p["pacote"] for p in enviados] == ORDEM_PACOTES
    assert [p["arquivo"] for p in enviados] == [f"{nome}.json" for nome in ORDEM_PACOTES]


# ---------------------------------------------------------------- caso 4: rodada 2

def test_caso_4a_rodada_2_substitui_o_registro_do_top_sem_teste_final(banco_teste, tmp_path, modelos_dir,
                                                                      modelos_invertidos_dir):
    _gerar(tmp_path, banco_teste(), modelos=modelos_dir)
    probs_1 = pacotes_experimento.ler_registro_top(tmp_path / "registros", D)["interno"]["probabilidades"]

    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_invertidos_dir)

    assert _execucao(pasta)["rodada"] == 2
    registro_2 = pacotes_experimento.ler_registro_top(tmp_path / "registros", D)
    assert registro_2["interno"]["probabilidades"] != probs_1
    assert _registros(pasta, "experimento_top")[0] == registro_2["pacote"]


def test_caso_4b_rodada_2_com_teste_final_reconstroi_do_registro(banco_teste, tmp_path, modelos_dir,
                                                                 modelos_invertidos_dir):
    params = params_teste(teste_final_fim=date(2025, 10, 21))
    _gerar(tmp_path, banco_teste(), modelos=modelos_dir, params=params)
    top_1 = (tmp_path / "saida" / D.isoformat() / "experimento_top.json").read_bytes()
    registro_1 = (tmp_path / "registros" / "2025-10-22.top.json").read_bytes()

    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_invertidos_dir, params=params)

    assert _execucao(pasta)["rodada"] == 2
    assert (pasta / "experimento_top.json").read_bytes() == top_1
    assert (tmp_path / "registros" / "2025-10-22.top.json").read_bytes() == registro_1


# ---------------------------------------------------------------- caso 5: sem modelo

def test_caso_5_sem_modelo_sai_sem_experimento_top_e_parcial(banco_teste, tmp_path):
    vazio = tmp_path / "vazio"
    vazio.mkdir()

    pasta = _gerar(tmp_path, banco_teste(), modelos=vazio)

    assert not (pasta / "experimento_top.json").exists()
    assert len(list(pasta.glob("*.json"))) == 9  # 8 pacotes + execucao
    ex = _execucao(pasta)
    assert ex["status"] == "parcial"
    assert [p["pacote"] for p in ex["pacotes_enviados"]] == ORDEM_PACOTES[:-1]
    assert any("experimento_top" in aviso for aviso in ex["avisos"])


# ---------------------------------------------------------------- caso 6: estado

def test_caso_6_estado_manda_tudo_na_primeira_e_nada_na_segunda(banco_teste, tmp_path, modelos_dir):
    _gerar(tmp_path, banco_teste(), modelos=modelos_dir, usar_estado=True)
    series_1 = _registros(tmp_path / "saida" / D.isoformat(), "series_diarias")
    assert series_1 and all(s["substituir_serie"] is True for s in series_1)
    assert (tmp_path / "estado" / "series_diarias.json").is_file()

    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, usar_estado=True)

    assert _registros(pasta, "series_diarias") == []
    assert _registros(pasta, "acoes") == []
    assert _registros(pasta, "proventos") == []


# ---------------------------------------------------------------- caso 7: teste final trancado

def test_caso_7_teste_final_trancado_nao_fecha_nem_mostra_dia(banco_teste, tmp_path, modelos_dir):
    _gerar(tmp_path, banco_teste(), modelos=modelos_dir)
    d2 = date(2025, 10, 23)
    pasta_2 = _gerar(tmp_path, banco_teste(alterar={"v1-precos": _com_pregao_de_22}), modelos=modelos_dir, d=d2)

    registros = tmp_path / "registros"
    assert (registros / "2025-10-22.top.json").is_file()
    assert (registros / "2025-10-23.top.json").is_file()
    assert list(registros.glob("*.resultado.json")) == []
    assert _registros(tmp_path / "saida" / D.isoformat(), "experimento_historico")[0]["resumo"]["n_dias"] == 0
    assert _registros(pasta_2, "experimento_historico")[0]["resumo"]["n_dias"] == 0


# ---------------------------------------------------------------- Fase 7: publicação do top (seção 8.5)

def test_caso_7a_top_nao_publicado_manda_os_sete_e_avisa(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, usar_estado=True, params_saida=SAIDA_NAO)

    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in [*SETE, "execucao"]}
    ex = _execucao(pasta)
    assert ex["status"] == "ok"
    assert [p["pacote"] for p in ex["pacotes_enviados"]] == SETE
    assert ex["avisos"].count(NOTA_TOP_NAO_PUBLICADO) == 1
    assert (tmp_path / "registros" / "2025-10-22.top.json").is_file()
    assert not [p for p in (tmp_path / "estado").glob("*") if "experimento" in p.name]


@pytest.mark.parametrize("oficial, publicar", [(False, True), (True, False), (True, True)])
def test_caso_7bcd_top_publicado_manda_os_dez(banco_teste, tmp_path, modelos_dir, oficial, publicar):
    params = dataclasses.replace(PARAMS, modelo_oficial=oficial)
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, params=params,
                   params_saida=SAIDA_SIM if publicar else SAIDA_NAO)

    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in ARQUIVOS}
    ex = _execucao(pasta)
    assert ex["status"] == "ok"
    assert [p["pacote"] for p in ex["pacotes_enviados"]] == ORDEM_PACOTES
    assert NOTA_TOP_NAO_PUBLICADO not in ex["avisos"]
    assert (tmp_path / "registros" / "2025-10-22.top.json").is_file()


# ---------------------------------------------------------------- caso 8: CLI

def test_caso_8_cli_codigos_de_saida(banco_teste, tmp_path, modelos_dir, monkeypatch):
    # o CLI lê o yaml real (top não publicado); este teste confere a gravação do top, então liga a publicação
    monkeypatch.setattr("processamento.saida.gerar.carregar_parametros_saida", lambda *a, **k: SAIDA_SIM)
    raiz = tmp_path / "saida"
    argv = ["--data", "2025-10-22", "--pasta", str(raiz), "--pasta-modelos", str(modelos_dir),
            "--pasta-registros", str(tmp_path / "registros"), "--sem-estado"]

    assert main(argv, ler=banco_teste(), existe_composicao=False) == 0
    assert (raiz / "2025-10-22" / "experimento_top.json").is_file()

    with pytest.raises(SystemExit) as erro:
        main(["--data", "2025-13-01"], ler=banco_teste(), existe_composicao=False)
    assert erro.value.code == 2

    sem_pregao = ["--data", "2025-10-16", "--pasta", str(tmp_path / "fora"),
                  "--pasta-modelos", str(modelos_dir), "--pasta-registros", str(tmp_path / "registros")]
    assert main(sem_pregao, ler=banco_teste(), existe_composicao=False) == 4


def test_caso_8_erro_na_leitura_fecha_a_execucao_como_falhou(tmp_path, modelos_dir):
    def ler_quebrado(*args, **kwargs):
        raise RuntimeError("host=10.0.0.1 user=segredo")

    raiz = tmp_path / "saida"
    argv = ["--data", "2025-10-22", "--pasta", str(raiz), "--pasta-modelos", str(modelos_dir),
            "--pasta-registros", str(tmp_path / "registros"), "--sem-estado"]
    assert main(argv, ler=ler_quebrado, existe_composicao=False) == 4
    execucao = _execucao(raiz / "2025-10-22")
    assert execucao["status"] == "falhou"
    assert execucao["avisos"] == ["falha ao ler a coleta (RuntimeError)"]
    assert "segredo" not in (raiz / "2025-10-22" / "execucao.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("erro, codigo", [
    (fontes.ErroConfiguracao("variáveis do banco faltando"), 2),
    (fontes.ErroSomenteLeitura("sessão com escrita liberada"), 3),
])
def test_caso_8_erros_de_conexao_saem_sem_criar_pasta(tmp_path, monkeypatch, erro, codigo):
    def _levanta():
        raise erro
    monkeypatch.setattr(exp_dataset, "_leitor_padrao", _levanta)
    raiz = tmp_path / "saida"

    assert main(["--data", "2025-10-22", "--pasta", str(raiz)]) == codigo
    assert not raiz.exists()


# ---------------------------------------------------------------- caso 9: sem banco real

def test_caso_9_sem_banco_real_a_trava_esta_ativa_e_o_gerar_funciona(banco_teste, tmp_path, modelos_dir):
    with pytest.raises(_BancoRealProibido):
        fontes.criar_engine()

    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir)

    assert _execucao(pasta)["status"] == "ok"


# ---------------------------------------------------------------- caso 3f: retorno suspeito vira aviso (DS7)

def _salto_petr4(df: pd.DataFrame) -> pd.DataFrame:
    """PETR4 com fechamento_ajustado 1.000.000 em 2025-10-20 (leitor de texto do banco_teste)."""
    df = df.copy()
    m = (df["ticker"] == "PETR4") & (df["data"] == "2025-10-20")
    df.loc[m, "fechamento_ajustado"] = "1000000.0"
    return df


def test_caso_3f_retorno_suspeito_vira_aviso_e_a_rodada_segue(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste({"v1-precos": _salto_petr4}), modelos=modelos_dir)

    ex = _execucao(pasta)
    assert ex["status"] == "ok"
    assert ("Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2025-10-16 e 2025-10-21, "
            "fora das séries e das medianas do setor: PETR4 (2025-10-20, 2025-10-21).") in ex["avisos"]
    assert not any(a.startswith("falha ao gerar") for a in ex["avisos"])


def test_caso_3g_sem_probabilidade_vira_aviso_na_rodada_e_sem_aviso_quando_zero(banco_teste, tmp_path, modelos_dir):
    # sem probabilidade do FinBERT em todas as notícias: a rodada monta o dataset e avisa com a contagem
    ler = banco_teste({"v1-noticias": lambda df: df.assign(prob_positivo=None)})
    pasta = _gerar(tmp_path / "com", ler, modelos=modelos_dir)
    ex = _execucao(pasta)
    avisos = [a for a in ex["avisos"] if "sem probabilidade do FinBERT" in a]
    assert len(avisos) == 1
    k = avisos[0].split(" notícias")[0]
    assert k.isdigit() and int(k) > 0
    assert avisos[0] == (f"{k} notícias sem probabilidade do FinBERT na janela do dataset: tratadas como ausentes "
                         "(não neutras).")

    # com probabilidade em todas: nenhum aviso desse tipo
    pasta_zero = _gerar(tmp_path / "sem", banco_teste(), modelos=modelos_dir)
    assert not any("sem probabilidade do FinBERT" in a for a in _execucao(pasta_zero)["avisos"])


def _com_smll_ate_22(df: pd.DataFrame) -> pd.DataFrame:
    """v1-indices com SMLL em 20/10, 21/10 e 22/10 (o de 22/10 é depois de t = 21/10: o corte tem de tirá-lo)."""
    smll = pd.DataFrame({"data": ["2025-10-20", "2025-10-21", "2025-10-22"], "indice": ["SMLL"] * 3,
                         "valor": ["1000", "1010", "1020"]})
    return pd.concat([df, smll], ignore_index=True)


def test_gerar_passa_ao_dataset_os_indices_so_ate_t(banco_teste, tmp_path, modelos_dir, monkeypatch):
    chamadas = []
    original = exp_dataset.montar_dataset

    def espiao(dados, cal, **kw):
        chamadas.append(dados)
        return original(dados, cal, **kw)

    monkeypatch.setattr("processamento.saida.gerar.montar_dataset", espiao)
    pasta = _gerar(tmp_path, banco_teste(alterar={"v1-indices": _com_smll_ate_22}), modelos=modelos_dir)
    assert _execucao(pasta)["status"] == "ok"
    assert len(chamadas) == 1
    indices = chamadas[0].indices
    assert indices is not None and not indices.empty
    smll = indices.loc[indices["indice"] == "SMLL", "data"]
    assert smll.max() == pd.Timestamp("2025-10-21")   # t é 21/10; o SMLL de 22/10 não entra


def test_gerar_sem_tabela_de_indices_para_como_as_outras_tabelas(banco_teste, tmp_path, modelos_dir):
    with pytest.raises(ErroSaida):
        _gerar(tmp_path, banco_teste(omitir=frozenset({"v1-indices"})), modelos=modelos_dir)
    pasta = tmp_path / "saida" / D.isoformat()
    assert _execucao(pasta)["status"] == "falhou"
    assert not (pasta / "mercado_dia.json").exists()


def test_aviso_de_smll_so_quando_nao_ha_smll(banco_teste, tmp_path, modelos_dir):
    sem = _gerar(tmp_path / "sem", banco_teste(), modelos=modelos_dir)
    assert sum(a == exp_dataset.AVISO_SMLL_AUSENTE for a in _execucao(sem)["avisos"]) == 1
    com = _gerar(tmp_path / "com", banco_teste(alterar={"v1-indices": _com_smll_ate_22}), modelos=modelos_dir)
    assert not any(a == exp_dataset.AVISO_SMLL_AUSENTE for a in _execucao(com)["avisos"])

# ---------------------------------------------------------------- pasta limpa (Fase 5; seção 3 do plano)

NOVE = ("acoes.json, series_diarias.json, mercado_dia.json, resumo_acao.json, fundamentos_trimestrais.json, "
        "proventos.json, noticias_dia.json, experimento_historico.json, experimento_top.json")
AVISO_ANTERIORES = ("Pacotes de uma rodada anterior de 2025-10-22 continuam na pasta (não refeitos nesta rodada): "
                    + NOVE + ".")


def test_p1_carga_completa_apaga_so_os_pacotes_e_mantem_o_resto(banco_teste, tmp_path, modelos_dir):
    pasta = tmp_path / "saida_completa" / "2025-10-22"
    pasta.mkdir(parents=True)
    (pasta / "experimento_top.json").write_text("{}", encoding="utf-8")
    (pasta / "experimento_historico.json").write_text("{}", encoding="utf-8")
    (pasta / "notas.txt").write_text("minhas notas", encoding="utf-8")

    gerar(D, ler=banco_teste(), pasta_saida=pasta, pasta_modelos=modelos_dir, pasta_registros=tmp_path / "registros",
          agora=AGORA, existe_composicao=False, params_treino=PARAMS, params_saida=SAIDA_NAO, completo=True)

    assert sorted(p.name for p in pasta.iterdir()) == [
        "acoes.json", "execucao.json", "fundamentos_trimestrais.json", "mercado_dia.json", "notas.txt",
        "noticias_dia.json", "proventos.json", "resumo_acao.json", "series_diarias.json",
    ]
    assert (pasta / "notas.txt").read_text(encoding="utf-8") == "minhas notas"
    ex = _execucao(pasta)
    assert ex["rodada"] == 1
    assert ex["status"] == "ok"
    assert [p["pacote"] for p in ex["pacotes_enviados"]] == SETE


def test_p2_envio_diario_repetido_apaga_o_top_que_nao_sai(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, params_saida=SAIDA_SIM)
    assert (pasta / "experimento_top.json").is_file()

    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, params_saida=SAIDA_NAO)

    assert sorted(p.name for p in pasta.iterdir()) == [
        "acoes.json", "execucao.json", "fundamentos_trimestrais.json", "mercado_dia.json",
        "noticias_dia.json", "proventos.json", "resumo_acao.json", "series_diarias.json",
    ]
    ex = _execucao(pasta)
    assert ex["rodada"] == 2
    assert ex["status"] == "ok"


def test_p3_falhou_depois_de_ok_mantem_os_pacotes_e_avisa(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, params_saida=SAIDA_SIM)
    (pasta / "notas.txt").write_text("x", encoding="utf-8")

    registrar_execucao(D, "falhou", coleta_status={"consultado": False, "nota": "teste"},
                       avisos=["aviso da coleta"], agora=AGORA, pasta_saida=pasta, params_saida=SAIDA_SIM)

    assert {p.name for p in pasta.iterdir()} == {f"{n}.json" for n in ARQUIVOS} | {"notas.txt"}
    ex = _execucao(pasta)
    assert ex["rodada"] == 2
    assert ex["status"] == "falhou"
    assert ex["pacotes_enviados"] == []
    assert ex["avisos"] == ["aviso da coleta", AVISO_ANTERIORES]


def test_p4_erro_de_leitura_depois_de_ok_mantem_os_pacotes(banco_teste, tmp_path, modelos_dir):
    pasta = _gerar(tmp_path, banco_teste(), modelos=modelos_dir, params_saida=SAIDA_SIM)

    def ler_quebrado(*args, **kwargs):
        raise RuntimeError("host=10.0.0.1 user=segredo")

    with pytest.raises(ErroSaida):
        _gerar(tmp_path, ler_quebrado, modelos=modelos_dir, params_saida=SAIDA_SIM)

    assert {p.name for p in pasta.iterdir()} == {f"{n}.json" for n in ARQUIVOS}
    ex = _execucao(pasta)
    assert ex["rodada"] == 2
    assert ex["status"] == "falhou"
    assert ex["avisos"] == ["falha ao ler a coleta (RuntimeError)", AVISO_ANTERIORES]


def test_p5_limpar_pacotes_so_os_nomes_da_8_5(tmp_path):
    pasta = tmp_path / "d"
    pasta.mkdir()
    for nome in ("acoes.json", "experimento_top.json", "execucao.json", "notas.txt", "acoes.json.tmp"):
        (pasta / nome).write_text("{}", encoding="utf-8")

    assert _limpar_pacotes(pasta) == ["acoes.json", "experimento_top.json"]
    assert {p.name for p in pasta.iterdir()} == {"execucao.json", "notas.txt", "acoes.json.tmp"}

    estado = tmp_path / "estado"
    estado.mkdir()
    (estado / "acoes.json").write_text("{}", encoding="utf-8")
    assert _limpar_pacotes(estado, proibida=estado) == []
    assert (estado / "acoes.json").is_file()


# ---------------------------------------------------------------- trava de versão: só o top fica de fora


def _modelos_de_outra_versao(origem: Path, destino: Path, nomes=("xgb-2025-10", "xgb-m1-2025-10")) -> Path:
    shutil.copytree(origem, destino)
    for nome in nomes:
        caminho = destino / f"{nome}.meta.json"
        meta = json.loads(caminho.read_text(encoding="utf-8"))
        meta.pop("versao_preparacao")   # modelo anterior à trava
        caminho.write_text(json.dumps(meta), encoding="utf-8")
    return destino


def test_modelo_de_outra_versao_com_top_nao_publicado_manda_os_sete_e_a_rodada_fica_ok(banco_teste, tmp_path, modelos_dir):
    antigos = _modelos_de_outra_versao(modelos_dir, tmp_path / "antigos")
    pasta = _gerar(tmp_path, banco_teste(), modelos=antigos, usar_estado=True, params_saida=SAIDA_NAO)

    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in [*SETE, "execucao"]}
    ex = _execucao(pasta)
    assert ex["status"] == "ok"
    assert [p["pacote"] for p in ex["pacotes_enviados"]] == SETE
    assert any("outra versão de preparação" in aviso for aviso in ex["avisos"])
    assert not (tmp_path / "registros" / "2025-10-22.top.json").exists()


def test_modelo_de_outra_versao_com_top_publicado_manda_o_resto_e_a_rodada_fica_parcial(banco_teste, tmp_path, modelos_dir):
    antigos = _modelos_de_outra_versao(modelos_dir, tmp_path / "antigos")
    pasta = _gerar(tmp_path, banco_teste(), modelos=antigos, params_saida=SAIDA_SIM)

    esperados = [nome for nome in ORDEM_PACOTES if nome != "experimento_top"]
    assert {p.name for p in pasta.iterdir()} == {f"{nome}.json" for nome in [*esperados, "execucao"]}
    ex = _execucao(pasta)
    assert ex["status"] == "parcial"
    assert [p["pacote"] for p in ex["pacotes_enviados"]] == esperados
    assert any("outra versão de preparação" in aviso for aviso in ex["avisos"])


def test_so_o_modelo_sombra_de_outra_versao_tambem_tira_o_top(banco_teste, tmp_path, modelos_dir):
    antigos = _modelos_de_outra_versao(modelos_dir, tmp_path / "antigos", nomes=("xgb-m1-2025-10",))
    pasta = _gerar(tmp_path, banco_teste(), modelos=antigos, params_saida=SAIDA_NAO)

    assert [p["pacote"] for p in _execucao(pasta)["pacotes_enviados"]] == SETE
    assert not (tmp_path / "registros" / "2025-10-22.top.json").exists()


def test_pacotes_de_fatos_sao_iguais_com_modelo_de_outra_versao(banco_teste, tmp_path, modelos_dir):
    antigos = _modelos_de_outra_versao(modelos_dir, tmp_path / "antigos")
    atual = _gerar(tmp_path / "a", banco_teste(), modelos=modelos_dir, params_saida=SAIDA_NAO)
    velho = _gerar(tmp_path / "b", banco_teste(), modelos=antigos, params_saida=SAIDA_NAO)
    for nome in SETE:
        assert _ler_json(atual, nome) == _ler_json(velho, nome), nome


# ---------------------------------------------------------------- dia_resultado ao vivo (E11)


def test_insumos_balancos_ate_t_e_para_dia_de_resultado_ate_a_vespera_de_d(banco_teste, monkeypatch):
    from datetime import timedelta

    import pandas as pd

    from processamento import fontes
    from processamento.saida.insumos import ler_insumos

    ler = banco_teste()
    original = fontes.ler_tabela
    precos = original("precos", ler=ler)
    t = precos.loc[precos["ticker"] == "IBOV", "data"].max().date()
    d = t + timedelta(days=3)   # entre t e D há dias sem pregão (como um fim de semana)
    sabado = pd.Timestamp(t + timedelta(days=1))
    base = original("balancos", ler=ler).iloc[:2].copy()
    assert len(base) == 2
    base["data_entrega"] = [pd.Timestamp(t), sabado]

    def lendo(tabela, *, desde=None, ate=None, ler=None, unir_mudancas=True):
        if tabela == "balancos":
            return base[base["data_entrega"] <= pd.Timestamp(ate)].reset_index(drop=True)
        return original(tabela, desde=desde, ate=ate, ler=ler, unir_mudancas=unir_mudancas)

    monkeypatch.setattr(fontes, "ler_tabela", lendo)
    ins = ler_insumos(d, ler, existe_composicao=False)
    assert ins.t == t
    assert ins.balancos["data_entrega"].tolist() == [pd.Timestamp(t)]
    assert ins.balancos_resultado["data_entrega"].tolist() == [pd.Timestamp(t), sabado]
