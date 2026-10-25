"""Testes de processamento/painel/servidor.py: rotas, cabeçalhos, validações, concorrência e trava.

O servidor sobe em 127.0.0.1 na porta 0, numa thread, com a raiz copiada para tmp_path. Os comandos
são `sys.executable -c ...` (nada de rotina, carga ou diagnóstico de verdade). Nenhum teste usa banco ou rede.
"""

import http.client
import json
import shutil
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from pathlib import Path

import pytest

from fabrica_painel import montar_raiz
from processamento.calendario import SP
from processamento.painel import acoes
from processamento.painel.servidor import criar_servidor, estado_com_marcos, host_permitido, origem_permitida

REPO = Path(__file__).resolve().parents[1]
RELOGIO = lambda: datetime(2026, 10, 23, 10, 0, tzinfo=SP)  # noqa: E731
RELOGIO_DOMINGO = lambda: datetime(2026, 10, 25, 12, 0, tzinfo=SP)  # noqa: E731

CODIGO_TESTES = "import time; print('inicio', flush=True); time.sleep(4); print('fim')"


def _montar_falso(chamadas: list):
    """Fábrica de comando de mentira: registra cada chamada em `chamadas` e roda um `python -c` inofensivo."""

    def montar(acao_id, *, d_rotina, d_carga):
        chamadas.append((acao_id, d_rotina, d_carga))
        if acao_id == "testes":
            return [sys.executable, "-c", CODIGO_TESTES]
        return [sys.executable, "-c", "print('ok')"]

    return montar


def pedir(s, metodo, caminho, corpo=None, *, host=None, origem="padrao", token="padrao"):
    """Faz uma requisição ao servidor de teste. Devolve (status, cabeçalhos em minúsculas, corpo em bytes)."""
    cabecalhos = {"Host": host or f"127.0.0.1:{s.porta}"}
    if origem == "padrao":
        cabecalhos["Origin"] = f"http://127.0.0.1:{s.porta}"
    elif origem is not None:
        cabecalhos["Origin"] = origem
    if token == "padrao":
        cabecalhos["X-Painel-Token"] = s.token
    elif token is not None:
        cabecalhos["X-Painel-Token"] = token
    dados = None
    if corpo is not None:
        if isinstance(corpo, bytes):
            dados = corpo
        elif isinstance(corpo, str):
            dados = corpo.encode("utf-8")
        else:
            dados = json.dumps(corpo).encode("utf-8")
        cabecalhos["Content-Type"] = "application/json"
    conn = http.client.HTTPConnection("127.0.0.1", s.porta, timeout=10)
    try:
        conn.request(metodo, caminho, body=dados, headers=cabecalhos)
        resposta = conn.getresponse()
        return resposta.status, {k.lower(): v for k, v in resposta.getheaders()}, resposta.read()
    finally:
        conn.close()


def _json(corpo: bytes):
    return json.loads(corpo.decode("utf-8"))


def _encerrar(s):
    if s.executor.rodando():
        s.executor.parar()
        s.executor.esperar(30)
    s.shutdown()
    s.server_close()


@pytest.fixture
def subir(tmp_path):
    """Sobe servidores de teste (uma raiz nova em tmp_path/<nome> para cada um) e os encerra no fim."""
    ativos = []

    def _subir(relogio=RELOGIO, nome="a"):
        raiz = montar_raiz(tmp_path / nome)
        chamadas: list = []
        s = criar_servidor(raiz, 0, montar_comando=_montar_falso(chamadas), relogio=relogio)
        s.chamadas = chamadas
        threading.Thread(target=s.serve_forever, daemon=True).start()
        ativos.append(s)
        return s

    yield _subir
    for s in ativos:
        _encerrar(s)


@pytest.fixture
def srv(subir):
    return subir()


# ---------------------------------------------------------------- páginas e Host

def test_get_raiz_serve_pagina_com_token_e_csp(srv):
    status, cab, corpo = pedir(srv, "GET", "/")
    assert status == 200
    texto = corpo.decode("utf-8")
    assert "Painel de operação" in texto
    assert srv.token in texto
    assert "__TOKEN_PAINEL__" not in texto
    assert "content-security-policy" in cab
    assert cab["cache-control"] == "no-store"
    assert cab["x-content-type-options"] == "nosniff"


def test_host_localhost_e_aceito(srv):
    status, _, _ = pedir(srv, "GET", "/", host=f"localhost:{srv.porta}")
    assert status == 200


def test_host_estranho_e_recusado(srv):
    for host in ["evil.example:" + str(srv.porta), "127.0.0.1:1"]:
        status, _, corpo = pedir(srv, "GET", "/", host=host)
        assert status == 403
        assert _json(corpo) == {"erro": "host não permitido"}
        status, _, _ = pedir(srv, "GET", "/api/painel", host=host)
        assert status == 403


# ---------------------------------------------------------------- painel (JSON)

def test_api_painel_chaves_e_valores(srv):
    status, _, corpo = pedir(srv, "GET", "/api/painel")
    assert status == 200
    dados = _json(corpo)
    assert set(dados) == {"gerado_em", "hoje", "trava", "agora", "historico", "etapas", "saude",
                          "experimento", "testes", "acao", "botoes", "data_rotina", "visao"}
    assert dados["agora"]["data_referencia"] == "2026-10-23"
    assert dados["agora"]["rodada"] == 6
    assert dados["agora"]["duracao_s"] == 118
    assert [d["data_referencia"] for d in dados["historico"]["diarias"]] == [
        "2026-10-23", "2026-10-22", "2026-10-21", "2026-10-20"]
    assert dados["hoje"]["data"] == "2026-10-23"
    assert dados["hoje"]["pregao"] is True
    assert dados["botoes"]["carga"]["comando"] == "python -m processamento.saida --data 2026-10-23 --completo"
    assert dados["botoes"]["rotina"]["comando"] == "python -m processamento.rotina --data 2026-10-23 --sem-esperar"
    assert dados["botoes"]["rotina"]["habilitado"] is True
    assert dados["trava"]["existe"] is False


def test_api_painel_data_da_rotina_e_data_dos_botoes(srv):
    _, _, corpo = pedir(srv, "GET", "/api/painel")
    dados = _json(corpo)
    assert dados["data_rotina"] == {"data": "2026-10-23", "origem": "hoje", "erro": None}
    assert dados["botoes"]["rotina"]["data"] == "2026-10-23"
    assert dados["botoes"]["carga"]["data"] == "2026-10-23"
    assert dados["botoes"]["diagnostico"]["data"] is None
    assert dados["botoes"]["testes"]["data"] is None
    assert dados["botoes"]["rotina"]["aviso"].startswith("Data usada: 2026-10-23 (hoje).")


def test_domingo_usa_o_ultimo_pregao(subir):
    s = subir(relogio=RELOGIO_DOMINGO)
    _, _, corpo = pedir(s, "GET", "/api/painel")
    dados = _json(corpo)
    assert dados["botoes"]["rotina"]["data"] == "2026-10-23"
    assert dados["botoes"]["rotina"]["habilitado"] is True
    assert dados["botoes"]["rotina"]["comando"] == "python -m processamento.rotina --data 2026-10-23 --sem-esperar"
    assert "2026-10-23" in dados["botoes"]["rotina"]["aviso"]
    assert "domingo" in dados["botoes"]["rotina"]["aviso"]
    assert dados["data_rotina"]["origem"] == "ultimo_pregao"
    # O POST recalcula a data no servidor (sem confiar no navegador) e passa a data certa ao comando.
    status, _, _ = pedir(s, "POST", "/api/acao/iniciar", {"acao": "rotina"})
    assert status == 202
    assert s.chamadas[0] == ("rotina", date(2026, 10, 23), date(2026, 10, 23))
    assert s.executor.esperar(30)


# ---------------------------------------------------------------- visão (fluxo, linha do tempo, saúde, calendário)

def test_api_painel_visao_com_as_fixtures(srv):
    _, _, corpo = pedir(srv, "GET", "/api/painel")
    dados = _json(corpo)
    assert set(dados["visao"]) == {"fluxo", "linha_tempo", "saude", "calendario"}
    fluxo = dados["visao"]["fluxo"]
    assert fluxo["coleta"]["estado"] == "ok"
    assert fluxo["coleta"]["etapas_concluidas"] == 9
    assert fluxo["coleta"]["etapas_total"] == 9
    assert fluxo["coleta"]["inicio_hhmm"] == "08:00"
    assert fluxo["coleta"]["entrega_hhmm"] == "08:22"
    assert fluxo["processamento"]["duracao_texto"] == "1 min 58 s"
    assert fluxo["processamento"]["n_acoes"] == 85
    assert fluxo["processamento"]["rotulo"] == "última rotina diária · rodada 6 · de 24/10 22:46"
    assert fluxo["carga"]["rotulo"] == "última carga completa: 24/10 23:00 · 2 pacotes"
    assert fluxo["interface"]["titulo"] == "7 pacotes prontos"
    assert fluxo["interface"]["n_pacotes"] == 7
    assert fluxo["interface"]["versao_contrato"] == "1.0"
    assert fluxo["interface"]["registros_total"] == 179
    linha = dados["visao"]["linha_tempo"]
    assert [m["id"] for m in linha["marcos"]] == ["coleta_inicio", "entrega", "prazo", "abertura"]
    assert linha["avisos"][0].startswith("A rotina deste pregão rodou em 24/10/2026 22:46")
    assert linha["folga_s"] is None
    cartoes = dados["visao"]["saude"]["cartoes"]
    assert cartoes[0]["numero"] == "2 divergências"
    assert [c["farol"] for c in cartoes] == ["bad", "idle", "idle", "idle", "idle", "idle"]
    meses = dados["visao"]["calendario"]
    assert meses[0]["titulo"] == "outubro de 2026"
    dia_23 = next(d for d in meses[0]["dias"] if d["data"] == "2026-10-23")
    assert dia_23["status"] == "ok"
    assert dia_23["completa"] is True
    assert dados["acao"]["marcos"] == []


# ---------------------------------------------------------------- arquivos sensíveis

def test_env_e_arquivos_fora_das_rotas_nao_sao_servidos(srv):
    for caminho in ["/.env", "/../.env", "/%2e%2e/.env", "/api/../.env",
                    "/processamento/config/parametros.yaml", "/saida/2026-10-23/execucao.json"]:
        status, _, _ = pedir(srv, "GET", caminho)
        assert status == 404, caminho


def test_segredos_do_env_nao_aparecem_nas_respostas(srv):
    for caminho in ["/", "/api/painel", "/api/acao?desde=0", "/api/relatorio"]:
        _, _, corpo = pedir(srv, "GET", caminho)
        assert b"segredo123" not in corpo, caminho
        assert b"usuario_teste" not in corpo, caminho


# ---------------------------------------------------------------- POST: validações

def test_post_iniciar_recusa_acao_desconhecida_e_corpo_invalido(srv):
    for corpo in [{"acao": "apagar_tudo"}, {"acao": "rotina; del *"}, "lixo"]:
        status, _, dados = pedir(srv, "POST", "/api/acao/iniciar", corpo)
        assert status == 400, corpo
        assert _json(dados) == {"erro": "ação desconhecida"}


def test_post_sem_token_ou_com_origem_errada_e_recusado(srv):
    status, _, _ = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "testes"}, token=None)
    assert status == 403
    status, _, _ = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "testes"}, origem="http://evil.example")
    assert status == 403
    status, _, _ = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "testes"}, origem=None)
    assert status == 403


def test_post_corpo_grande_recebe_413(srv):
    status, _, corpo = pedir(srv, "POST", "/api/acao/iniciar", b"x" * 2000)
    assert status == 413
    assert _json(corpo) == {"erro": "corpo grande demais"}


def test_get_em_rota_de_post_e_404(srv):
    status, _, _ = pedir(srv, "GET", "/api/acao/iniciar")
    assert status == 404


# ---------------------------------------------------------------- concorrência

def test_uma_acao_por_vez_e_parar(srv):
    status, _, _ = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "testes"})
    assert status == 202
    status, _, corpo = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "diagnostico"})
    assert status == 409
    erro = _json(corpo)["erro"]
    assert "rodando" in erro or "em andamento" in erro
    _, _, corpo = pedir(srv, "GET", "/api/painel")
    assert _json(corpo)["botoes"]["rotina"]["habilitado"] is False

    prazo = time.monotonic() + 10
    while True:
        _, _, corpo = pedir(srv, "GET", "/api/acao?desde=0")
        if "inicio" in _json(corpo)["linhas"]:
            break
        assert time.monotonic() < prazo, "a saída do teste não apareceu no log"
        time.sleep(0.1)

    status, _, _ = pedir(srv, "POST", "/api/acao/parar", {})
    assert status == 200
    assert srv.executor.esperar(30)
    _, _, corpo = pedir(srv, "GET", "/api/acao")
    dados = _json(corpo)
    assert dados["rodando"] is False
    assert dados["significado"] == "parado pelo painel"


def test_parar_com_etapas_no_historico_da_acao(srv):
    status, _, _ = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "testes"})
    assert status == 202
    prazo = time.monotonic() + 10
    while True:
        _, _, corpo = pedir(srv, "GET", "/api/acao?desde=0")
        if "inicio" in _json(corpo)["linhas"]:
            break
        assert time.monotonic() < prazo, "a saída do teste não apareceu no log"
        time.sleep(0.1)

    status, _, _ = pedir(srv, "POST", "/api/acao/parar", {})
    assert status == 200
    assert srv.executor.esperar(30)
    _, _, corpo = pedir(srv, "GET", "/api/acao?desde=0")
    dados = _json(corpo)
    assert [m["id"] for m in dados["marcos"]] == ["coleta", "execucao", "fim"]
    assert dados["marcos"][-1] == {"id": "fim", "rotulo": "Encerrado", "estado": "erro",
                                   "detalhe": "parado pelo painel"}


def test_post_iniciar_nao_aceita_teste_final(srv):
    status, _, corpo = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "teste_final"})
    assert status == 400
    assert _json(corpo) == {"erro": "ação desconhecida"}
    assert srv.chamadas == []


def test_estado_com_marcos_fatia_linhas_e_calcula_etapas(tmp_path):
    ex = acoes.Executor(tmp_path, tmp_path / "logs")
    iniciou, msg = ex.iniciar("testes", [sys.executable, "-c",
                                         "print('..... [100%]'); print('5 passed in 0.10s')"])
    assert iniciou, msg
    ex.esperar(30)

    r = estado_com_marcos(ex, 0)
    assert r["linhas"] == ["..... [100%]", "5 passed in 0.10s"]
    assert [m["estado"] for m in r["marcos"]] == ["concluida", "concluida", "concluida"]
    assert r["marcos"][1]["detalhe"] == "5 passed in 0.10s"
    assert r["marcos"][2]["detalhe"] == "todos os testes passaram"
    assert estado_com_marcos(ex, 1)["linhas"] == ["5 passed in 0.10s"]
    sem_linhas = estado_com_marcos(ex, None)
    assert sem_linhas["linhas"] == []
    assert len(sem_linhas["marcos"]) == 3


# ---------------------------------------------------------------- trava

def test_trava_ativa_bloqueia_banco_e_nao_e_mexida(srv):
    trava = srv.raiz / "saida" / "estado" / "rotina.trava"
    conteudo = json.dumps({"pid": 4321, "criada_em": "2026-10-23T09:30:00-03:00"})
    trava.write_text(conteudo, encoding="utf-8")
    _, _, corpo = pedir(srv, "GET", "/api/painel")
    dados = _json(corpo)
    assert dados["trava"]["ativa"] is True
    assert dados["trava"]["idade_min"] == 30
    assert dados["botoes"]["rotina"]["habilitado"] is False
    assert dados["botoes"]["carga"]["habilitado"] is False
    assert dados["botoes"]["diagnostico"]["habilitado"] is False
    assert dados["botoes"]["testes"]["habilitado"] is True

    status, _, corpo = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "rotina"})
    assert status == 409
    assert "trava" in _json(corpo)["erro"]
    assert trava.exists()
    assert trava.read_text(encoding="utf-8") == conteudo


def test_trava_abandonada_nao_bloqueia(srv):
    trava = srv.raiz / "saida" / "estado" / "rotina.trava"
    trava.write_text(json.dumps({"pid": 4321, "criada_em": "2026-10-23T03:00:00-03:00"}), encoding="utf-8")
    _, _, corpo = pedir(srv, "GET", "/api/painel")
    dados = _json(corpo)
    assert dados["trava"]["abandonada"] is True
    assert dados["botoes"]["rotina"]["habilitado"] is True


# ---------------------------------------------------------------- produção

def test_producao_desabilita_a_rotina(srv):
    yaml = srv.raiz / "processamento" / "config" / "parametros.yaml"
    texto = yaml.read_text(encoding="utf-8")
    assert "fim: null" in texto
    yaml.write_text(texto.replace("fim: null", 'fim: "2026-11-30"', 1), encoding="utf-8")
    _, _, corpo = pedir(srv, "GET", "/api/painel")
    rotina = _json(corpo)["botoes"]["rotina"]
    assert rotina["habilitado"] is False
    assert "Agendador de Tarefas" in rotina["motivo"]
    status, _, _ = pedir(srv, "POST", "/api/acao/iniciar", {"acao": "rotina"})
    assert status == 409


# ---------------------------------------------------------------- sem execuções

def test_sem_nenhuma_execucao_nao_quebra(srv):
    shutil.rmtree(srv.raiz / "saida")
    status, _, corpo = pedir(srv, "GET", "/api/painel")
    assert status == 200
    dados = _json(corpo)
    assert dados["agora"] is None
    assert dados["historico"]["diarias"] == []
    assert dados["botoes"]["carga"]["habilitado"] is False


# ---------------------------------------------------------------- funções puras e isolamento

def test_host_e_origem_permitidos():
    assert host_permitido("127.0.0.1:8765", 8765) is True
    assert host_permitido("127.0.0.1", 8765) is False
    assert host_permitido(None, 8765) is False
    assert origem_permitida("http://localhost:8765", 8765) is True
    assert origem_permitida("null", 8765) is False


def test_modulo_do_painel_nao_importa_banco_nem_env():
    codigo = ("import sys, processamento.painel.servidor; "
              "print('processamento.fontes' in sys.modules, 'sqlalchemy' in sys.modules, 'dotenv' in sys.modules)")
    resultado = subprocess.run([sys.executable, "-c", codigo], cwd=str(REPO), capture_output=True, text=True,
                               timeout=120)
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "False False False"


def test_codigo_do_painel_nao_tem_sql_nem_shell():
    proibidos = ["SELECT", "executar_leitura", "create_engine", "load_dotenv", '.env"', "shell=True"]
    for arquivo in sorted((REPO / "processamento" / "painel").glob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for termo in proibidos:
            assert termo not in texto, f"{arquivo.name} contém {termo!r}"
