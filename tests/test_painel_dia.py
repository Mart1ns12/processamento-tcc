"""Testes de processamento/painel/dia.py: rodar o dia completo (rotina, carga e publicador).

Nenhum teste roda a rotina, a carga ou o publicador de verdade: `rodar` é um executor falso que grava
as chamadas e devolve o código e as linhas programados. Tudo fica em tmp_path. Nenhum teste usa banco ou rede.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from fabrica_painel import montar_raiz
from processamento.calendario import SP
from processamento.painel import dia
from processamento.painel.acoes import SIGNIFICADOS
from processamento.painel.marcos import marcos_acao

D = date(2026, 10, 26)
AGORA = datetime(2026, 10, 26, 10, 0, 0, tzinfo=SP)
GERADO_OK = "2026-10-26T10:00:00-03:00"
AMBIENTE = {"PATH": "caminho-de-teste", "PYTHONPATH": "nao-deve-passar"}
PUBLICOU_COMPLETO = "26/10/2026 publicado (modo normal, execução: ok) em 1,2 s"
SO_EXECUCAO = "26/10/2026: só a execução foi gravada (sem carga completa)"


def _relogio():
    return AGORA


def _api(tmp_path: Path) -> Path:
    """Pasta falsa do projeto da API: só o Python (arquivo vazio) e o publicador (arquivo vazio)."""
    api = tmp_path / "api"
    (api / ".venv" / "Scripts").mkdir(parents=True)
    (api / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    (api / "publicador").mkdir()
    (api / "publicador" / "__main__.py").write_text("", encoding="utf-8")
    return api


@pytest.fixture
def cenario(tmp_path):
    raiz = montar_raiz(tmp_path)
    api = _api(tmp_path)
    return raiz, api, {"dir_api": str(api)}


class Falso:
    """Executor falso: grava (argv, cwd, env) e devolve (código, linhas) programados por etapa."""

    def __init__(self, raiz, *, status=None, gerado_em=GERADO_OK, rotina=(0, []), carga=(0, []),
                 publicador=(0, [])):
        self.raiz = raiz
        self.status = status
        self.gerado_em = gerado_em
        self.respostas = {"processamento.rotina": rotina, "processamento.saida": carga, "publicador": publicador}
        self.chamadas = []

    def __call__(self, argv, cwd, env):
        self.chamadas.append((list(argv), Path(cwd), dict(env)))
        if argv[2] == "processamento.rotina" and self.status is not None:
            pasta = self.raiz / "saida" / D.isoformat()
            pasta.mkdir(parents=True, exist_ok=True)
            registro = {"status": self.status, "gerado_em": self.gerado_em}
            (pasta / "execucao.json").write_text(json.dumps({"registros": [registro]}), encoding="utf-8")
        codigo, linhas = self.respostas[argv[2]]
        return codigo, list(linhas)

    def etapas(self):
        nomes = {"processamento.rotina": "rotina", "processamento.saida": "carga", "publicador": "publicador"}
        return [nomes[argv[2]] for argv, _cwd, _env in self.chamadas]


def _executar(raiz, params, falso, ambiente=None):
    saida = []
    codigo = dia.executar_dia(D, raiz, params, rodar=falso, imprimir=saida.append, relogio=_relogio,
                              ambiente=AMBIENTE if ambiente is None else ambiente)
    return codigo, saida


def test_status_ok_roda_as_tres_etapas(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="ok", publicador=(0, [PUBLICOU_COMPLETO]))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 0
    assert falso.etapas() == ["rotina", "carga", "publicador"]
    assert saida[-1].startswith("# dia: resultado=completa ")


def test_status_parcial_tambem_roda_a_carga(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="parcial", carga=(0, ["Saída de 2026-10-26 em X: status parcial"]),
                  publicador=(0, [PUBLICOU_COMPLETO]))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 0
    assert falso.etapas() == ["rotina", "carga", "publicador"]
    assert "# dia: etapa=carga fim codigo=0 em=2026-10-26T10:00:00-03:00 detalhe=status parcial" in saida


def test_rotina_falhou_sem_carga_antiga_publica_so_a_execucao(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="falhou", rotina=(4, []), publicador=(0, [SO_EXECUCAO]))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 0
    assert falso.etapas() == ["rotina", "publicador"]
    assert "# dia: etapa=carga pulada motivo=a rotina falhou" in saida
    assert saida[-1].startswith("# dia: resultado=so_execucao ")


def test_rotina_falhou_com_carga_antiga_nao_roda_o_publicador(cenario):
    raiz, api, params = cenario
    (raiz / "saida_completa" / D.isoformat()).mkdir(parents=True)
    falso = Falso(raiz, status="falhou", rotina=(4, []))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 6
    assert falso.etapas() == ["rotina"]
    assert any("etapa=publicador pulada" in linha and "saida_completa/2026-10-26/" in linha for linha in saida)


def test_rotina_nao_gera_nada_devolve_3(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status=None, rotina=(0, []))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 3
    assert falso.etapas() == ["rotina"]
    assert saida[-1].startswith("# dia: resultado=sem_saida ")


def test_execucao_de_outro_dia_nao_conta_como_saida_nova(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="ok", gerado_em="2026-10-25T10:00:00-03:00")
    codigo, _saida = _executar(raiz, params, falso)
    assert codigo == 3
    assert falso.etapas() == ["rotina"]


def test_status_em_andamento_nao_e_saida_nova(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="em_andamento")
    codigo, _saida = _executar(raiz, params, falso)
    assert codigo == 3
    assert falso.etapas() == ["rotina"]


def test_dia_sem_pregao_devolve_3_e_explica(cenario):
    raiz, api, params = cenario
    linha = "Rotina: não é pregão previsto (fim de semana): nada a gerar."
    falso = Falso(raiz, status=None, rotina=(0, [linha]))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 3
    assert "# dia: etapa=rotina fim codigo=0 em=2026-10-26T10:00:00-03:00 detalhe=dia sem pregão" in saida


def test_marcas_de_inicio_levam_data_e_hora_com_fuso(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="parcial", carga=(0, ["Saída de 2026-10-26 em X: status parcial"]),
                  publicador=(0, [PUBLICOU_COMPLETO]))
    _codigo, saida = _executar(raiz, params, falso)
    inicios = [linha for linha in saida if " inicio=" in linha]
    assert len(inicios) == 3
    assert all(linha.endswith(" inicio=2026-10-26T10:00:00-03:00") for linha in inicios)
    r = marcos_acao("dia", saida, rodando=False, codigo=0, significado=SIGNIFICADOS["dia"][0])
    assert r[1]["detalhe"] == "status parcial"
    assert "em=" not in r[1]["detalhe"]


def test_carga_que_falha_devolve_4_e_nao_publica(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="ok", carga=(4, []))
    codigo, saida = _executar(raiz, params, falso)
    assert codigo == 4
    assert falso.etapas() == ["rotina", "carga"]
    assert "# dia: etapa=publicador pulada motivo=a carga completa falhou" in saida


@pytest.mark.parametrize("codigo_pub, esperado", [(1, 1), (2, 5)])
def test_publicador_com_erro(cenario, codigo_pub, esperado):
    raiz, api, params = cenario
    linhas = ["Publicação de 26/10/2026 recusada (validação)"] if codigo_pub == 1 else ["erro"]
    falso = Falso(raiz, status="ok", publicador=(codigo_pub, linhas))
    codigo, _saida = _executar(raiz, params, falso)
    assert codigo == esperado
    assert falso.etapas() == ["rotina", "carga", "publicador"]


def test_sem_configuracao_do_publicador_nao_roda_nada(cenario):
    raiz, api, _params = cenario
    falso = Falso(raiz, status="ok")
    codigo, saida = _executar(raiz, {}, falso)
    assert codigo == 2
    assert falso.chamadas == []
    assert saida[-1].startswith("# dia: resultado=configuracao ")


def test_argv_e_cwd_fixos_sem_forcar(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="ok", publicador=(0, [PUBLICOU_COMPLETO]))
    _executar(raiz, params, falso)
    argvs = [argv for argv, _cwd, _env in falso.chamadas]
    assert argvs[0] == [sys.executable, "-m", "processamento.rotina", "--data", "2026-10-26", "--sem-esperar"]
    assert argvs[1] == [sys.executable, "-m", "processamento.saida", "--data", "2026-10-26", "--completo"]
    assert argvs[2] == [str(api / ".venv" / "Scripts" / "python.exe"), "-m", "publicador", "--data", "2026-10-26"]
    assert falso.chamadas[2][1] == api
    for argv in argvs:
        assert "--forcar" not in argv
        assert "--criar-tabelas" not in argv


def test_ambiente_do_publicador_nao_leva_banco_nem_proc(tmp_path):
    base = {"PATH": "p", "SENHA_BANCO": "x", "USER_BANCO": "u", "PROC_API_CHAVES": "k", "PYTHONPATH": "z",
            "IP_BANCO": "i", "SENHA_ESCRITA": "e"}
    env = dia.ambiente_publicador(base, tmp_path)
    assert env["PATH"] == "p"
    assert env["PROC_DIR_PROCESSAMENTO"] == str(tmp_path)
    for nome in ("SENHA_BANCO", "USER_BANCO", "PROC_API_CHAVES", "PYTHONPATH", "IP_BANCO", "SENHA_ESCRITA"):
        assert nome not in env


def test_segredo_do_processamento_nao_chega_ao_publicador_nem_a_saida(cenario):
    raiz, api, params = cenario
    segredo = "chave-secreta-xyz"
    ambiente = {"PATH": "p", "PROC_API_CHAVES": segredo, "SENHA_BANCO": segredo}
    falso = Falso(raiz, status="ok", publicador=(0, [PUBLICOU_COMPLETO]))
    codigo, saida = _executar(raiz, params, falso, ambiente=ambiente)
    assert codigo == 0
    env_publicador = falso.chamadas[2][2]
    assert segredo not in env_publicador.values()
    assert all(segredo not in linha for linha in saida)


def test_verificar_publicador_sem_dir_api(tmp_path):
    api = dia.verificar_publicador(tmp_path, {})
    assert api["dir_api"] is None and api["python"] is None
    assert "dir_api" in api["motivo"]


def test_verificar_publicador_pasta_inexistente(tmp_path):
    api = dia.verificar_publicador(tmp_path, {"dir_api": "nao-existe"})
    assert api["motivo"].startswith("Pasta do projeto da API não encontrada")


def test_verificar_publicador_sem_python_ou_sem_publicador(tmp_path):
    api = tmp_path / "api"
    api.mkdir()
    assert "Python do projeto da API" in dia.verificar_publicador(tmp_path, {"dir_api": str(api)})["motivo"]
    (api / ".venv" / "Scripts").mkdir(parents=True)
    (api / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    assert "Publicador não encontrado" in dia.verificar_publicador(tmp_path, {"dir_api": str(api)})["motivo"]


def test_verificar_publicador_completo(cenario):
    raiz, api, params = cenario
    r = dia.verificar_publicador(raiz, params)
    assert r == {"dir_api": str(api), "python": str(api / ".venv" / "Scripts" / "python.exe"), "motivo": None}


@pytest.mark.parametrize("linhas, esperado", [
    ([SO_EXECUCAO], "so_execucao"),
    ([PUBLICOU_COMPLETO], "completa"),
    (["Não publicado: sem pregão"], "recusada"),
    (["Publicação de 26/10/2026 recusada (validação)"], "recusada"),
    (["qualquer outra linha"], None),
    ([], None),
])
def test_resultado_publicador(linhas, esperado):
    assert dia.resultado_publicador(linhas) == esperado


def test_main_rejeita_data_invalida_sem_rodar_nada():
    with pytest.raises(SystemExit) as erro:
        dia.main(["--data", "nao-e-data"])
    assert erro.value.code == 2


def test_integracao_com_os_marcos_no_caso_so_execucao(cenario):
    raiz, api, params = cenario
    falso = Falso(raiz, status="falhou", rotina=(4, []), publicador=(0, [SO_EXECUCAO]))
    _codigo, saida = _executar(raiz, params, falso)
    r = marcos_acao("dia", saida, rodando=False, codigo=0, significado=SIGNIFICADOS["dia"][0])
    assert [e["estado"] for e in r] == ["erro", "pulada", "concluida", "concluida"]
    assert r[0]["detalhe"] == "status falhou"
    assert r[2]["detalhe"] == "só a execução"
