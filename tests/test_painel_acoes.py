"""Testes de processamento/painel/acoes.py: comandos, ambiente, significado e Executor.

Nenhum teste roda a rotina, a carga ou o diagnóstico de verdade: os "comandos" são
`sys.executable -c ...` e tudo fica em tmp_path. Nenhum teste usa banco ou rede.
"""

import os
import sys
from datetime import date

import pytest

from processamento.painel.acoes import (
    ACOES,
    SIGNIFICADOS,
    Executor,
    ambiente_filho,
    comando_texto,
    montar_comando,
    significado,
)


def _executor(tmp_path, **kw):
    return Executor(tmp_path, tmp_path / "logs", **kw)


def _logs(tmp_path, acao_id):
    return sorted((tmp_path / "logs").glob(f"{acao_id}-*.log"))


def test_montar_comando_rotina_com_data():
    assert montar_comando("rotina", d_rotina=date(2026, 10, 23), d_carga=None) == [
        sys.executable, "-m", "processamento.rotina", "--data", "2026-10-23", "--sem-esperar",
    ]


def test_montar_comando_rotina_sem_data_devolve_none():
    assert montar_comando("rotina", d_rotina=None, d_carga=None) is None


def test_montar_comando_carga_com_data():
    assert montar_comando("carga", d_rotina=None, d_carga=date(2026, 10, 23)) == [
        sys.executable, "-m", "processamento.saida", "--data", "2026-10-23", "--completo",
    ]


def test_montar_comando_carga_sem_data_devolve_none():
    assert montar_comando("carga", d_rotina=date(2026, 10, 23), d_carga=None) is None


def test_montar_comando_diagnostico_e_testes():
    assert montar_comando("diagnostico", d_rotina=None, d_carga=None) == [
        sys.executable, "-m", "processamento.diagnostico",
    ]
    assert montar_comando("testes", d_rotina=None, d_carga=None) == [
        sys.executable, "-m", "pytest", "-q",
    ]


def test_montar_comando_wordpress_saiu_da_lista_fixa():
    with pytest.raises(KeyError):
        montar_comando("wordpress", d_rotina=None, d_carga=None)
    assert "wordpress" not in SIGNIFICADOS
    assert "wordpress" not in ACOES


def test_montar_comando_id_desconhecido_levanta_keyerror():
    with pytest.raises(KeyError):
        montar_comando("apagar", d_rotina=None, d_carga=None)


def test_comando_texto_sem_caminho_do_python():
    argv = montar_comando("carga", d_rotina=None, d_carga=date(2026, 10, 23))
    assert comando_texto(argv) == "python -m processamento.saida --data 2026-10-23 --completo"


def test_ambiente_filho_testes_remove_permissao_de_banco():
    env = ambiente_filho("testes", {"PATH": "x", "PROC_TESTES_COM_BANCO": "1"})
    assert env == {"PATH": "x", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


def test_ambiente_filho_rotina_mantem_base():
    env = ambiente_filho("rotina", {"PATH": "x"})
    assert env == {"PATH": "x", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


def test_ambiente_filho_nao_define_pythonutf8():
    assert "PYTHONUTF8" not in ambiente_filho("testes", {})
    assert "PYTHONUTF8" not in ambiente_filho("rotina", {})


def test_significado_por_acao_e_codigo():
    assert significado("rotina", 5, False) == "outra rotina em andamento (trava)"
    assert significado("testes", 9, False) == "código 9"
    assert significado("testes", 1, True) == "parado pelo painel"
    assert significado("testes", None, False) is None


def test_acoes_fixas():
    assert set(ACOES) == {"dia", "rotina", "carga", "diagnostico", "testes"}
    assert ACOES["testes"].pode_parar is True
    assert ACOES["rotina"].pode_parar is False


def test_dia_e_a_primeira_acao_e_nao_pode_parar():
    assert list(ACOES)[0] == "dia"
    assert ACOES["dia"].pode_parar is False


def test_montar_comando_dia_com_data():
    assert montar_comando("dia", d_rotina=date(2026, 10, 26), d_carga=None) == [
        sys.executable, "-m", "processamento.painel.dia", "--data", "2026-10-26"]


def test_montar_comando_dia_sem_data_devolve_none():
    assert montar_comando("dia", d_rotina=None, d_carga=date(2026, 10, 26)) is None


def test_significado_do_dia_com_codigo_seis():
    assert significado("dia", 6, False) == (
        "rotina falhou, mas há uma carga completa antiga deste dia: publicador não rodado")


def test_executor_estado_vazio(tmp_path):
    ex = _executor(tmp_path)
    estado = ex.estado()
    assert estado["id"] is None
    assert estado["rodando"] is False
    assert estado["linhas"] == []
    assert estado["proximo"] == 0


def test_executor_roda_e_guarda_linhas_e_log(tmp_path):
    ex = _executor(tmp_path)
    codigo = (
        "print('linha 1'); print('Ação com acentuação: São Paulo'); raise SystemExit(3)"
    )
    ok, _ = ex.iniciar("testes", [sys.executable, "-c", codigo])
    assert ok is True
    assert ex.esperar(30) is True

    estado = ex.estado(0)
    assert estado["linhas"] == ["linha 1", "Ação com acentuação: São Paulo"]
    assert estado["codigo"] == 3
    assert estado["significado"] == "erro interno do pytest"
    assert estado["rodando"] is False
    assert estado["proximo"] == 2
    assert ex.estado(1)["linhas"] == ["Ação com acentuação: São Paulo"]
    assert ex.estado(None)["linhas"] == []
    assert estado["arquivo_log"].startswith("logs/testes-")

    logs = _logs(tmp_path, "testes")
    assert len(logs) == 1
    linhas_log = logs[0].read_text(encoding="utf-8").splitlines()
    assert linhas_log[0].startswith("# painel: acao=testes inicio=")
    assert linhas_log[1:3] == ["linha 1", "Ação com acentuação: São Paulo"]
    assert linhas_log[-1].endswith("codigo=3")


def test_executor_passa_ambiente_utf8_e_tira_permissao_de_banco(tmp_path):
    base = {"PROC_TESTES_COM_BANCO": "1", **os.environ}
    ex = _executor(tmp_path, ambiente_base=base)
    codigo = (
        "import os; print(os.environ.get('PYTHONIOENCODING'), os.environ.get('PROC_TESTES_COM_BANCO'))"
    )
    ex.iniciar("testes", [sys.executable, "-c", codigo])
    assert ex.esperar(30) is True
    assert ex.estado(0)["linhas"] == ["utf-8 None"]


def test_executor_uma_acao_por_vez_e_parar(tmp_path):
    ex = _executor(tmp_path)
    ok, _ = ex.iniciar("testes", [sys.executable, "-c", "import time; time.sleep(5)"])
    assert ok is True
    assert ex.rodando() is True

    ok, msg = ex.iniciar("rotina", [sys.executable, "-c", "pass"])
    assert ok is False
    assert msg == "outra ação em andamento: Rodar os testes (pytest)"

    assert ex.parar() == (True, "parando")
    assert ex.esperar(30) is True
    estado = ex.estado(0)
    assert estado["significado"] == "parado pelo painel"
    assert estado["rodando"] is False
    linhas_log = _logs(tmp_path, "testes")[0].read_text(encoding="utf-8").splitlines()
    assert "parado=sim" in linhas_log[-1]


def test_executor_nao_para_acao_sem_permissao(tmp_path):
    ex = _executor(tmp_path)
    ex.iniciar("diagnostico", [sys.executable, "-c", "import time; time.sleep(1)"])
    assert ex.parar() == (False, "esta ação não pode ser parada")
    assert ex.esperar(30) is True


def test_executor_parar_sem_nada_rodando(tmp_path):
    ex = _executor(tmp_path)
    assert ex.parar() == (False, "nada rodando")


def test_executor_recusa_acao_e_comando_invalidos(tmp_path):
    ex = _executor(tmp_path)
    assert ex.iniciar("apagar", [sys.executable, "-c", "pass"]) == (False, "ação desconhecida")
    assert ex.iniciar("wordpress_livre", [sys.executable, "-c", "pass"]) == (False, "ação desconhecida")
    assert ex.iniciar("testes", ["cmd", "/c", "dir"]) == (False, "comando inválido")
    assert ex.iniciar("testes", "python") == (False, "comando inválido")
    assert ex.iniciar("testes", []) == (False, "comando inválido")
    assert ex.rodando() is False


def test_executor_falha_de_inicio_vira_mensagem(tmp_path):
    ex = _executor(tmp_path / "inexistente")
    ok, msg = ex.iniciar("testes", [sys.executable, "-c", "pass"])
    assert ok is False
    assert msg.startswith("não foi possível iniciar (")
    assert ex.rodando() is False


def test_executor_mantem_so_os_logs_mais_recentes(tmp_path):
    pasta = tmp_path / "logs"
    pasta.mkdir()
    for n in range(1, 23):
        (pasta / f"testes-2026-01-01_0000{n:02d}.log").write_text("antigo\n", encoding="utf-8")

    ex = _executor(tmp_path)
    ok, _ = ex.iniciar("testes", [sys.executable, "-c", "pass"])
    assert ok is True
    assert ex.esperar(30) is True

    restantes = sorted(p.name for p in pasta.glob("testes-*.log"))
    assert len(restantes) == 20
    assert "testes-2026-01-01_000001.log" not in restantes
    assert "testes-2026-01-01_000003.log" not in restantes
    assert "testes-2026-01-01_000004.log" in restantes
    novo = [nome for nome in restantes if not nome.startswith("testes-2026-01-01_")]
    assert len(novo) == 1


def test_nenhum_comando_destrava_o_teste_final():
    assert set(ACOES) == {"dia", "rotina", "carga", "diagnostico", "testes"}
    for acao_id in ACOES:
        argv = montar_comando(acao_id, d_rotina=date(2026, 10, 23), d_carga=date(2026, 10, 23))
        assert argv is not None
        assert "--teste-final" not in argv
        assert "processamento.experimento.treino" not in argv
