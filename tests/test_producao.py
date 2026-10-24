"""Testes da entrada em produção (plano da etapa 8, seção 10; fase 9): conferências, confirmação de uso único e
códigos de saída do `main`. Todas as pastas vão para tmp_path; nada toca registros/ nem docs/ reais.
"""

import json
from datetime import date, datetime

import pytest

from fabrica_treino import params_teste
from processamento import producao
from processamento.experimento import modelos, treino
from processamento.saida import contrato

HOJE = date(2026, 10, 23)
D0 = date(2026, 11, 3)  # terça; fim = 2026-10-30 (2 de novembro não é pregão previsto)
AGORA = datetime(2026, 10, 23, 15, 0, tzinfo=contrato.SP)


@pytest.fixture(autouse=True)
def caminhos_isolados(tmp_path, monkeypatch):
    """Nenhum teste pode tocar o registro do teste final nem o producao.json reais."""
    monkeypatch.setattr(treino, "REGISTRO_TESTE_FINAL", tmp_path / "docs" / "teste_final_usado.json")
    monkeypatch.setattr(producao, "ARQUIVO_PRODUCAO_PADRAO", tmp_path / "docs" / "producao.json")


@pytest.fixture
def pastas(tmp_path):
    p = {
        "modelos": tmp_path / "modelos",
        "registros": tmp_path / "registros" / "experimento",
        "registro_teste": tmp_path / "docs" / "teste_final_usado.json",
        "producao": tmp_path / "docs" / "producao.json",
    }
    p["modelos"].mkdir()
    p["registros"].mkdir(parents=True)
    _escrever_dev(p["modelos"], _params(), provisorio=False)  # treino de desenvolvimento oficial
    return p


def _params(**trocas):
    return params_teste(**{"modelo_oficial": True, **trocas})


def _nome_dev(params):
    return modelos.nome_modelo(params.teste_final_inicio.strftime("%Y-%m"), "3")


def _escrever_dev(pasta_modelos, params, provisorio=False):
    caminho = pasta_modelos / f"{_nome_dev(params)}.meta.json"
    caminho.write_text(json.dumps({"provisorio": provisorio}), encoding="utf-8")


def _conferir(pastas, d0=D0, params=None):
    params = _params() if params is None else params
    return producao.conferir_entrada(d0, HOJE, params, pastas["modelos"], pastas["registros"],
                                     pastas["registro_teste"])


def _main(pastas, argv, params=None, hoje=HOJE):
    params = _params() if params is None else params
    return producao.main(
        argv, hoje=hoje, agora=AGORA, params_treino=params, pasta_modelos=pastas["modelos"],
        pasta_registros=pastas["registros"], registro_teste_final=pastas["registro_teste"],
        arquivo_producao=pastas["producao"],
    )


def test_tudo_certo_sem_problemas(pastas):
    fim, problemas, passos = _conferir(pastas)
    assert problemas == []
    assert fim == date(2026, 10, 30)
    assert any("2026-11-03" in passo for passo in passos)
    assert any('treino.teste_final.fim: "2026-10-30"' in passo for passo in passos)


def test_d0_que_nao_e_pregao(pastas):
    fim, problemas, _ = _conferir(pastas, d0=date(2026, 11, 2))
    assert problemas == ["2026-11-02 não é pregão previsto"]
    assert fim is None


def test_d0_nao_e_depois_de_hoje(pastas):
    fim, problemas, _ = _conferir(pastas, d0=HOJE)
    assert problemas == ["D0 precisa ser depois de hoje (2026-10-23)"]
    assert fim == date(2026, 10, 22)


def test_modelo_provisorio_e_problema(pastas):
    _, problemas, _ = _conferir(pastas, params=_params(modelo_oficial=False))
    assert problemas == [
        "modelo ainda provisório (treino.modelo_oficial: false): com o histórico curto o modelo não é treinado "
        "para valer (pegadinha 13) e nenhum dia entraria no histórico"
    ]


def test_registro_do_teste_final_existente_e_problema(pastas):
    pastas["registro_teste"].parent.mkdir(parents=True, exist_ok=True)
    pastas["registro_teste"].write_text("{}", encoding="utf-8")
    _, problemas, _ = _conferir(pastas)
    assert problemas == ["teste final já usado (docs/teste_final_usado.json)"]


def test_fim_ja_preenchido_com_outra_data_e_problema(pastas):
    _, problemas, _ = _conferir(pastas, params=_params(teste_final_fim=date(2026, 10, 29)))
    assert problemas == ["treino.teste_final.fim já está preenchido com 2026-10-29"]


def test_fim_ja_igual_ao_calculado_nao_e_problema(pastas):
    _, problemas, _ = _conferir(pastas, params=_params(teste_final_fim=date(2026, 10, 30)))
    assert problemas == []


def test_resultado_fechado_na_pasta_e_problema(pastas):
    (pastas["registros"] / "2026-10-22.resultado.json").write_text("{}", encoding="utf-8")
    _, problemas, _ = _conferir(pastas)
    assert problemas == [
        "já existe resultado fechado em registros/experimento: conferir antes de entrar em produção"
    ]


def test_resultado_em_subpasta_nao_conta(pastas):
    sub = pastas["registros"] / "funcionamento-2026-10-01"
    sub.mkdir()
    (sub / "2026-10-01.resultado.json").write_text("{}", encoding="utf-8")
    _, problemas, _ = _conferir(pastas)
    assert problemas == []


def test_dev_provisorio_e_problema(pastas):
    params = _params()
    _escrever_dev(pastas["modelos"], params, provisorio=True)
    _, problemas, _ = producao.conferir_entrada(D0, HOJE, params, pastas["modelos"], pastas["registros"],
                                                pastas["registro_teste"])
    assert len(problemas) == 1
    assert "provisorio: false" in problemas[0]


def test_dev_ausente_e_problema(pastas):
    params = _params()
    (pastas["modelos"] / f"{_nome_dev(params)}.meta.json").unlink()
    _, problemas, _ =producao.conferir_entrada(D0, HOJE, params, pastas["modelos"], pastas["registros"],
                                                pastas["registro_teste"])
    assert len(problemas) == 1
    assert _nome_dev(params) in problemas[0]


def test_passos_com_fim_vazio_quando_d0_nao_e_pregao(pastas):
    _, _, passos = _conferir(pastas, d0=date(2026, 11, 2))
    assert any('"<fim>"' in passo for passo in passos)


def test_confirmar_move_tops_e_grava_producao(pastas):
    top = pastas["registros"] / "2026-10-23.top.json"
    conteudo = {"pacote": {"candidatos": ["PETR4"]}, "interno": {"ok": True}}
    top.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")

    assert _main(pastas, ["--inicio", "2026-11-03", "--confirmar"]) == 0

    assert not top.exists()
    movido = pastas["registros"] / "funcionamento-2026-10-23" / "2026-10-23.top.json"
    assert json.loads(movido.read_text(encoding="utf-8")) == conteudo
    producao = json.loads(pastas["producao"].read_text(encoding="utf-8"))
    assert producao == {
        "inicio": "2026-11-03",
        "fim": "2026-10-30",
        "confirmado_em": "2026-10-23T15:00:00-03:00",
        "registros_arquivados": ["2026-10-23.top.json"],
    }


def test_confirmar_com_problema_nao_move_nada(pastas, capsys):
    top = pastas["registros"] / "2026-10-23.top.json"
    top.write_text("{}", encoding="utf-8")

    codigo = _main(pastas, ["--inicio", "2026-11-03", "--confirmar"], params=_params(modelo_oficial=False))

    assert codigo == 1
    assert top.exists()
    assert not (pastas["registros"] / "funcionamento-2026-10-23").exists()
    assert not pastas["producao"].exists()
    assert "Nada foi movido nem gravado." in capsys.readouterr().out


def test_confirmar_e_de_uso_unico(pastas):
    (pastas["registros"] / "2026-10-23.top.json").write_text("{}", encoding="utf-8")
    assert _main(pastas, ["--inicio", "2026-11-03", "--confirmar"]) == 0

    # Segunda chamada: producao.json já existe, então recusa e não grava outro.
    antes = pastas["producao"].read_text(encoding="utf-8")
    assert _main(pastas, ["--inicio", "2026-11-03", "--confirmar"]) == 1
    assert pastas["producao"].read_text(encoding="utf-8") == antes


def test_sem_confirmar_nao_grava_nem_move(pastas, capsys):
    top = pastas["registros"] / "2026-10-23.top.json"
    top.write_text("{}", encoding="utf-8")

    assert _main(pastas, ["--inicio", "2026-11-03"]) == 0

    assert top.exists()
    assert not pastas["producao"].exists()
    assert not (pastas["registros"] / "funcionamento-2026-10-23").exists()
    saida = capsys.readouterr().out
    assert "Nada foi gravado." in saida
    assert "treino.teste_final.fim" in saida


def test_main_com_problema_sai_com_codigo_1(pastas, capsys):
    assert _main(pastas, ["--inicio", "2026-11-02"]) == 1
    saida = capsys.readouterr().out
    assert "2026-11-02 não é pregão previsto" in saida
    assert "Nada foi movido nem gravado." in saida


def test_data_invalida_no_argumento(pastas):
    with pytest.raises(SystemExit) as erro:
        _main(pastas, ["--inicio", "03/11/2026"])
    assert erro.value.code == 2


def test_confirmar_entrada_recusa_sem_fim(pastas):
    with pytest.raises(producao.ErroProducao):
        producao.confirmar_entrada(date(2026, 11, 2), None, HOJE, pastas["registros"], pastas["producao"], AGORA)
    assert not pastas["producao"].exists()
