"""Servidor HTTP do painel de operação: só em 127.0.0.1, com Host, Origin e token conferidos.

Não lê o banco nem o `.env`. Serve a página, o JSON com a situação e os comandos do projeto (via `acoes`).
O navegador manda só o id da ação; a data da rotina e da carga é calculada aqui, a cada pedido.
"""

from __future__ import annotations

import argparse
import functools
import hmac
import json
import secrets
import webbrowser
from collections.abc import Callable
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from processamento.calendario import SP
from processamento.painel import (acoes, ajuda, aba_api, aba_coleta, aba_diagnostico, aba_execucoes, aba_experimento,
                                  agendador, api, dia, leitores, marcos, mercado, novidades, pedidos, relatorios,
                                  saude, visao)

PORTA_PADRAO = 8765
LIMITE_CORPO = 1024
LIMITE_DESCARTE = 65536
PLACEHOLDER_TOKEN = "__TOKEN_PAINEL__"
CSP_PAGINA = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
MOTIVO_PRODUCAO = "Em produção a rotina roda pelo Agendador de Tarefas; não rodar pelo painel."
MOTIVO_TRAVA = "Uma rotina já está rodando (trava de saida/estado/rotina.trava)"


def host_permitido(host: str | None, porta: int) -> bool:
    """Só aceita o endereço local (protege contra DNS rebinding)."""
    return host in {f"127.0.0.1:{porta}", f"localhost:{porta}"}


def origem_permitida(origem: str | None, porta: int) -> bool:
    """Só aceita a própria página como origem dos pedidos de escrita."""
    return origem in {f"http://127.0.0.1:{porta}", f"http://localhost:{porta}"}


def _seguro(func: Callable[..., object], *args: object) -> object:
    """Chama a leitura; se levantar exceção, devolve o motivo no lugar do resultado."""
    try:
        return func(*args)
    except Exception as e:
        return {"disponivel": False, "motivo": f"erro ao ler ({type(e).__name__})"}


AVISO_REGISTRO_TOP = (
    " Fora de produção, o top 5 regravado fica marcado como fora do histórico; em produção, "
    "o registro do dia é gravado uma vez só e nunca é refeito."
)


def _aviso_rotina(rotina_data: dict, hoje: dict) -> str | None:
    """Aviso do botão da rotina, conforme a data usada é hoje ou o último pregão."""
    data = rotina_data.get("data")
    if data is None:
        return None
    if rotina_data.get("origem") == "hoje":
        return (
            f"Data usada: {data} (hoje). Com --sem-esperar, se a coleta de hoje ainda não terminou "
            "(antes das 08:00 ela nem começou), a rotina gera mesmo assim, com aviso. "
            f"Regrava saida/{data}/, saida/estado/ e registros/experimento/{data}.top.json."
            + AVISO_REGISTRO_TOP
        )
    motivo = hoje.get("motivo") or "não é pregão"
    return (
        f"Hoje ({motivo}) não é pregão: será usada a data {data}, o último pregão. "
        "A rotina confere a coleta desse dia no banco e regrava "
        f"saida/{data}/, saida/estado/ e registros/experimento/{data}.top.json."
        + AVISO_REGISTRO_TOP
    )


def estado_botoes(params: dict, trava: dict, hoje: dict, rotina_data: dict, d_carga: date | None,
                  executor: acoes.Executor, agora: datetime, motivo_publicador: str | None = None) -> dict:
    """Título, comando, data, habilitação, motivo e aviso de cada ação. O primeiro motivo de bloqueio vale."""
    rodando = executor.rodando()
    titulo_atual = executor.estado(None).get("titulo") if rodando else None
    d_rotina = date.fromisoformat(rotina_data["data"]) if rotina_data.get("data") else None
    botoes: dict[str, dict] = {}
    for acao_id, acao in acoes.ACOES.items():
        motivo: str | None = None
        aviso: str | None = None
        data: str | None = None
        if rodando:
            motivo = f"Aguarde: {titulo_atual} está rodando"
        elif trava.get("ativa") and acao.usa_banco:
            motivo = MOTIVO_TRAVA
        if acao_id == "dia":
            data = rotina_data.get("data")
            if params["teste_final"]["fim"]:
                motivo = motivo or MOTIVO_PRODUCAO
            if rotina_data.get("erro"):
                motivo = motivo or f"Calendário: {rotina_data['erro']}"
            motivo = motivo or motivo_publicador
            if data is not None:
                aviso = (f"Data usada: {data}. Em sequência: rotina (--sem-esperar) → carga completa em "
                         f"saida_completa/{data}/; publicador do projeto da API (python -m publicador --data {data}), "
                         "que grava no banco da API. Se a rotina falhar, a carga não roda e o publicador grava só "
                         "a execução. Não pode ser parado no meio.")
        elif acao_id == "rotina":
            data = rotina_data.get("data")
            if params["teste_final"]["fim"]:
                motivo = motivo or MOTIVO_PRODUCAO
            if rotina_data.get("erro"):
                motivo = motivo or f"Calendário: {rotina_data['erro']}"
            aviso = _aviso_rotina(rotina_data, hoje)
        elif acao_id == "carga":
            if d_carga is None:
                motivo = motivo or "Nenhuma rotina diária ainda (pasta saida/AAAA-MM-DD)."
            else:
                data = d_carga.isoformat()
                aviso = (f"Gera os pacotes inteiros em saida_completa/{data}/; "
                         "não mexe no envio diário nem nos registros.")
        elif acao_id == "diagnostico":
            aviso = "Só lê o banco; reescreve docs/diagnostico_banco.md."
        elif acao_id == "testes":
            aviso = "Não usa o banco; leva alguns minutos."
        argv = acoes.montar_comando(acao_id, d_rotina=d_rotina, d_carga=d_carga)
        botoes[acao_id] = {
            "titulo": acao.titulo,
            "comando": acoes.comando_texto(argv) if argv else None,
            "habilitado": motivo is None,
            "motivo": motivo,
            "aviso": aviso,
            "data": data,
        }
    return botoes


def estado_com_marcos(executor: acoes.Executor, desde: int | None, *, pasta_logs_painel: Path | None = None,
                      n_media: int | None = None, agora: datetime | None = None) -> dict:
    """Estado do Executor com as linhas a partir de `desde`, as etapas calculadas sobre todo o buffer e,
    no dia completo, o progresso (tempo estimado pelas médias dos logs do painel)."""
    completo = executor.estado(0)
    todas = completo["linhas"]
    if desde is None:
        linhas = []
    else:
        primeiro = completo["total_linhas"] - len(todas)
        linhas = todas[max(desde, primeiro) - primeiro:]
    marcos_lista = marcos.marcos_acao(completo["id"], todas, rodando=completo["rodando"],
                                      codigo=completo["codigo"], significado=completo["significado"])
    return {**completo, "linhas": linhas, "marcos": marcos_lista,
            "progresso": _progresso_dia(completo, todas, marcos_lista, pasta_logs_painel, n_media, agora)}


def _progresso_dia(completo: dict, todas: list[str], marcos_lista: list[dict], pasta_logs_painel: Path | None,
                   n_media: int | None, agora: datetime | None) -> dict | None:
    """Progresso só do dia completo (None nas outras ações). Erro na conta vira None, nunca derruba a tela."""
    if completo["id"] != "dia":
        return None
    try:
        med = (relatorios.medias_etapas_dia(pasta_logs_painel, n_media) if pasta_logs_painel is not None
               else {"medias": {}, "amostras": {}})
        return marcos.progresso_dia(todas, marcos_lista, med["medias"], med["amostras"],
                                    agora or datetime.now(SP), completo["rodando"])
    except Exception:
        return None


def _juntar_saude(saude_base: dict, coer: dict, afet: dict, afetadas_max: int | None,
                  indisp: dict | None = None) -> dict:
    """Saúde da tela: cartões do diagnóstico + "Coerência do mercado" e "Indicadores indisponíveis" (mesmo sem
    diagnóstico) e linhas afetadas."""
    saude_v = dict(saude_base)
    cartoes = list(saude_v.get("cartoes") or [])
    cartao = coer.get("cartao")
    if isinstance(cartao, dict):
        cartoes.append(cartao)
    indisp = indisp if isinstance(indisp, dict) else {}
    if isinstance(indisp.get("cartao"), dict):
        cartoes.append(indisp["cartao"])
    saude_v["cartoes"] = cartoes
    afetadas = dict(afet) if isinstance(afet, dict) and "disponivel" not in afet else {}
    if coer.get("afetadas"):
        afetadas["coerencia_mercado"] = coer["afetadas"]
    if indisp.get("afetadas"):
        afetadas["indicadores_indisponiveis"] = indisp["afetadas"]
    saude_v["afetadas"] = afetadas
    saude_v["afetadas_max"] = afetadas_max
    return saude_v


def montar_painel(raiz: Path, executor: acoes.Executor, agora: datetime, caminho_calendario: str | None = None,
                  monitor: api.MonitorApi | None = None) -> dict:
    """Situação completa para a página (cada parte isolada: uma leitura quebrada não derruba as outras)."""
    params = leitores.ler_parametros(raiz)
    trava = _seguro(leitores.ler_trava, raiz, params, agora)
    hoje = _seguro(leitores.info_hoje, agora, caminho_calendario)
    rotina_data = _seguro(leitores.data_rotina, agora, caminho_calendario)
    if "origem" not in rotina_data:
        rotina_data = {"data": None, "origem": None, "erro": rotina_data.get("motivo")}
    carga = _seguro(leitores.d_mais_recente, raiz, params["pasta_saida"])
    d_carga = carga if isinstance(carga, date) else None
    diarias = _seguro(leitores.listar_execucoes, raiz, params["pasta_saida"], "diaria")
    completas = _seguro(leitores.listar_execucoes, raiz, "saida_completa", "completa")
    itens_diarias = diarias if isinstance(diarias, list) else []
    itens_completas = completas if isinstance(completas, list) else []
    agora_item = leitores.ultima_execucao(itens_diarias)
    if agora_item is not None:
        agora_item = {**agora_item, "possivelmente_interrompida": (
            agora_item.get("status") == "em_andamento" and not trava.get("ativa") and not executor.rodando())}
    completa_item = leitores.ultima_execucao(itens_completas)
    pasta_painel = raiz / params["pasta_logs"] / "painel"
    painel_p = _seguro(leitores.ler_parametros_painel, raiz)
    painel_p = painel_p if "disponivel" not in painel_p else {}
    logs_dia = _seguro(aba_execucoes.ler_logs_dia, pasta_painel)
    logs_dia = logs_dia if isinstance(logs_dia, list) else []
    agend = _seguro(agendador.bloco_agendador, painel_p.get("agendador"), agora, caminho_calendario)
    exp_v = _seguro(relatorios.ler_experimento, raiz, params)
    valida = leitores.ultima_execucao_valida(itens_diarias)
    d_valida = valida.get("data_referencia") if valida else None
    dados_dia = _seguro(mercado.ler_dia, raiz, params["pasta_saida"], d_valida)
    serie = _seguro(mercado.serie_ibov, raiz, params["pasta_saida"], d_valida, painel_p.get("mercado_pregoes_linha"))
    serie = serie if isinstance(serie, list) else []
    api_sit = (_seguro(monitor.situacao, painel_p, agora) if monitor is not None
               else {"configurada": False, "erro_config": "Monitor da API ausente."})
    api_v = _seguro(visao.bloco_api, api_sit, painel_p.get("api_tempo_limite_s"))
    banco_v = _seguro(visao.bloco_banco, api_sit, d_valida, dados_dia.get("data_pregao"))
    atipico_v = _seguro(mercado.dia_atipico, dados_dia, {
        "retorno_abs": painel_p.get("retorno_dia_abs"), "min_acoes": painel_p.get("dia_atipico_min_acoes"),
        "ibov_amplo": painel_p.get("dia_atipico_ibov_amplo"), "max": painel_p.get("afetadas_max")})
    coer = _seguro(mercado.cartao_coerencia, dados_dia, {
        "ivvb11_min": painel_p.get("coerencia_ivvb11_min_abs"), "dif_min": painel_p.get("coerencia_ibov_mediana_dif")})
    docs_md = raiz / "docs" / "diagnostico_banco.md"
    novid = _seguro(novidades.novidades, docs_md, pasta_painel, painel_p.get("diagnosticos_manter"))
    afet = _seguro(saude.afetadas_saude, docs_md)
    pub = _seguro(dia.verificar_publicador, raiz, painel_p)
    motivo_pub = pub.get("motivo") if isinstance(pub, dict) else "erro ao conferir o projeto da API"
    testes = _seguro(relatorios.ler_ultimo_pytest, pasta_painel)
    fluxo_v = _seguro(visao.fluxo, agora_item, completa_item)
    linha_v = _seguro(visao.linha_do_tempo, agora_item, leitores.ler_prazo_rotina(raiz), caminho_calendario)
    saude_base = _seguro(saude.cartoes_saude, docs_md)
    indisp = _seguro(mercado.cartao_indisponiveis, dados_dia)
    saude_v = _juntar_saude(saude_base, coer, afet, painel_p.get("afetadas_max"), indisp)
    duracoes = _seguro(relatorios.duracoes_painel, pasta_painel, list(acoes.ACOES))
    valores_ajuda = {**_seguro(leitores.ler_valores_ajuda, raiz), "abertura": visao.hora_marco(linha_v, "abertura")}
    hoje_iso = agora.astimezone(SP).date().isoformat()
    data_ultima = fluxo_v.get("data") if isinstance(fluxo_v, dict) and fluxo_v.get("disponivel") else None
    botoes_v = _seguro(functools.partial(estado_botoes, motivo_publicador=motivo_pub),
                       params, trava, hoje, rotina_data, d_carga, executor, agora)
    resumo_v = _seguro(functools.partial(visao.resumo, api=api_v, banco=banco_v, dia_atipico=atipico_v),
                       hoje, trava, fluxo_v, linha_v, saude_v, testes)
    return {
        "gerado_em": agora.isoformat(timespec="seconds"),
        "hoje": hoje,
        "trava": trava,
        "agora": agora_item,
        "historico": {"diarias": diarias, "completas": completas},
        "etapas": _seguro(relatorios.ler_logs_rotina, raiz / params["pasta_logs"]),
        "saude": _seguro(relatorios.ler_diagnostico, docs_md),
        "experimento": exp_v,
        "testes": testes,
        "acao": _seguro(functools.partial(estado_com_marcos, pasta_logs_painel=pasta_painel,
                                         n_media=painel_p.get("dia_media_execucoes"), agora=agora),
                        executor, None),
        "botoes": botoes_v,
        "data_rotina": rotina_data,
        "visao": {
            "fluxo": fluxo_v,
            "linha_tempo": linha_v,
            "saude": saude_v,
            "calendario": _seguro(visao.calendario_meses, itens_diarias, itens_completas,
                                  agora.astimezone(SP).date().isoformat(), caminho_calendario),
            "resumo": resumo_v,
            "tempos": _seguro(visao.tempos_acoes, duracoes, agora_item, completa_item),
            "ajuda": _seguro(ajuda.montar_ajuda, valores_ajuda),
            "dia": _seguro(visao.frase_dia, hoje_iso, data_ultima, caminho_calendario),
            "glossario": [list(par) for par in ajuda.GLOSSARIO],
            "api": api_v,
            "banco": banco_v,
            "coleta_etapas": _seguro(visao.etapas_coleta, agora_item),
            "novidades": novid,
            "dia_atipico": atipico_v,
            "mercado": _seguro(mercado.bloco_mercado, dados_dia, serie),
            "fluxo_nos": _seguro(visao.fluxo_nos, fluxo_v, banco_v, api_v),
            "coleta_indicadores": _seguro(aba_coleta.indicadores_coleta, docs_md),
            "noticias_ano_origem": _seguro(aba_coleta.noticias_ano_origem, docs_md),
            "noticias_mes": _seguro(aba_coleta.noticias_mes, docs_md),
            "coleta_falhas": _seguro(aba_coleta.falhas_etapas, docs_md),
            "pedidos": _seguro(pedidos.avaliar_pedidos,
                               raiz / "processamento" / "config" / "pedidos_coleta.yaml", docs_md),
            "diagnostico": _seguro(aba_diagnostico.diagnostico_aba, docs_md, pasta_painel,
                                   saude_base.get("cartoes") or []),
            "execucoes": _seguro(aba_execucoes.bloco_execucoes, logs_dia),
            "agendador": agend,
            "proxima_execucao": agend.get("proxima_texto"),
            "api_publicacoes": _seguro(aba_api.publicacoes, logs_dia),
            "experimento_operacao": _seguro(aba_experimento.operacao, raiz, params, exp_v, hoje_iso,
                                            caminho_calendario),
        },
    }


def _data_do_botao(botoes: dict, acao_id: str) -> date | None:
    """Data já calculada para o botão (no servidor); None se o botão não tem data."""
    botao = botoes.get(acao_id)
    data = botao.get("data") if isinstance(botao, dict) else None
    return date.fromisoformat(data) if isinstance(data, str) else None


def _desde(consulta: str) -> int:
    """Índice da primeira linha pedida pelo log (inválido ou negativo vira 0)."""
    try:
        return max(0, int(parse_qs(consulta).get("desde", ["0"])[0]))
    except ValueError:
        return 0


class _Servidor(ThreadingHTTPServer):
    """Servidor com o contexto que o handler usa (raiz, executor, token e página)."""

    daemon_threads = True
    raiz: Path
    porta: int
    token: str
    pagina: str
    relogio: Callable[[], datetime]
    montar_comando: Callable[..., list[str] | None]
    caminho_calendario: str | None
    executor: acoes.Executor
    monitor: api.MonitorApi
    pasta_painel: Path


class _Handler(BaseHTTPRequestHandler):
    """Rotas exatas do painel. Nada de arquivo do disco por caminho vindo da URL."""

    server_version = "PainelTCC"
    sys_version = ""
    server: _Servidor

    def log_message(self, *_args: object) -> None:
        return

    def _enviar(self, status: int, tipo: str, corpo: bytes, extras: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for nome, valor in (extras or {}).items():
            self.send_header(nome, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, status: int, dados: object) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self._enviar(status, "application/json; charset=utf-8", corpo)

    def _host_ok(self) -> bool:
        if host_permitido(self.headers.get("Host"), self.server.porta):
            return True
        self._json(403, {"erro": "host não permitido"})
        return False

    def do_GET(self) -> None:
        if not self._host_ok():
            return
        srv = self.server
        partes = urlsplit(self.path)
        caminho = partes.path
        if caminho == "/":
            corpo = srv.pagina.replace(PLACEHOLDER_TOKEN, srv.token).encode("utf-8")
            self._enviar(200, "text/html; charset=utf-8", corpo, {"Content-Security-Policy": CSP_PAGINA})
        elif caminho == "/api/painel":
            dados = montar_painel(srv.raiz, srv.executor, srv.relogio(), srv.caminho_calendario, srv.monitor)
            self._json(200, dados)
        elif caminho == "/api/acao":
            self._json(200, estado_com_marcos(
                srv.executor, _desde(partes.query), pasta_logs_painel=srv.pasta_painel,
                n_media=leitores.ler_parametros_painel(srv.raiz).get("dia_media_execucoes"), agora=srv.relogio()))
        elif caminho == "/api/diagnostico-md":
            arquivo = srv.raiz / "docs" / "diagnostico_banco.md"
            if not arquivo.is_file():
                self._json(404, {"erro": "sem diagnóstico"})
                return
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
            self._enviar(200, "text/plain; charset=utf-8", texto.encode("utf-8"))
        else:
            self._json(404, {"erro": "não encontrado"})

    def do_POST(self) -> None:
        if not self._host_ok():
            return
        srv = self.server
        if not origem_permitida(self.headers.get("Origin"), srv.porta):
            self._json(403, {"erro": "origem não permitida"})
            return
        recebido = self.headers.get("X-Painel-Token", "")
        if not hmac.compare_digest(recebido.encode("utf-8"), srv.token.encode("utf-8")):
            self._json(403, {"erro": "token inválido"})
            return
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if tamanho < 0:
            self._json(400, {"erro": "corpo inválido"})
            return
        if tamanho > LIMITE_CORPO:
            if tamanho <= LIMITE_DESCARTE:
                self.rfile.read(tamanho)  # consome o corpo para o cliente receber a resposta
            self._json(413, {"erro": "corpo grande demais"})
            return
        corpo = self.rfile.read(tamanho)
        caminho = urlsplit(self.path).path
        if caminho == "/api/acao/iniciar":
            self._iniciar(corpo)
        elif caminho == "/api/acao/parar":
            ok, msg = srv.executor.parar()
            if ok:
                self._json(200, {"ok": True})
            else:
                self._json(409, {"erro": msg})
        elif caminho == "/api/conferir-api":
            self._conferir_api()
        else:
            self._json(404, {"erro": "não encontrado"})

    def _conferir_api(self) -> None:
        """Consulta a API agora (sem esperar api_intervalo_s) e devolve o bloco da API."""
        srv = self.server
        painel_p = leitores.ler_parametros_painel(srv.raiz)
        situacao = srv.monitor.situacao(painel_p, srv.relogio(), forcar=True)
        if situacao.get("configurada") is not True:
            self._json(409, {"erro": situacao.get("erro_config") or "API não configurada."})
            return
        self._json(200, {"ok": True, "api": visao.bloco_api(situacao, painel_p.get("api_tempo_limite_s"))})

    def _iniciar(self, corpo: bytes) -> None:
        srv = self.server
        try:
            dados = json.loads(corpo.decode("utf-8"))
        except ValueError:
            dados = None
        acao_id = dados.get("acao") if isinstance(dados, dict) else None
        if not isinstance(acao_id, str) or acao_id not in acoes.ACOES:
            self._json(400, {"erro": "ação desconhecida"})
            return
        botoes = montar_painel(srv.raiz, srv.executor, srv.relogio(), srv.caminho_calendario,
                               srv.monitor).get("botoes")
        botoes = botoes if isinstance(botoes, dict) else {}
        botao = botoes.get(acao_id)
        if not isinstance(botao, dict) or botao.get("habilitado") is not True:
            motivo = botao.get("motivo") if isinstance(botao, dict) else None
            self._json(409, {"erro": motivo or "ação indisponível"})
            return
        argv = srv.montar_comando(acao_id, d_rotina=_data_do_botao(botoes, "rotina"),
                                  d_carga=_data_do_botao(botoes, "carga"))
        if argv is None:
            self._json(409, {"erro": "ação indisponível"})
            return
        ok, msg = srv.executor.iniciar(acao_id, argv)
        if ok:
            self._json(202, {"ok": True, "acao": acao_id})
        else:
            self._json(409, {"erro": msg})


def criar_servidor(raiz: Path = leitores.RAIZ_PADRAO, porta: int = PORTA_PADRAO, *,
                   executor: acoes.Executor | None = None,
                   montar_comando: Callable[..., list[str] | None] = acoes.montar_comando,
                   relogio: Callable[[], datetime] | None = None,
                   caminho_calendario: str | None = None,
                   consultar_api: Callable[..., dict] | None = None) -> _Servidor:
    """Cria o servidor (ainda não atende). Porta 0 escolhe uma livre; a porta real fica em `srv.porta`.

    `consultar_api` substitui a consulta HTTP à API (usado nos testes; sem ele, a consulta real só roda se
    `painel.api_url` estiver configurada).
    """
    raiz = Path(raiz)
    relogio = relogio or (lambda: datetime.now(SP))
    pagina = (Path(__file__).parent / "pagina.html").read_text(encoding="utf-8")
    pasta_logs = leitores.ler_parametros(raiz)["pasta_logs"]
    if executor is None:
        executor = acoes.Executor(raiz, raiz / pasta_logs / "painel", relogio=relogio)
    srv = _Servidor(("127.0.0.1", porta), _Handler)
    srv.raiz = raiz
    srv.pasta_painel = raiz / pasta_logs / "painel"
    srv.porta = srv.server_address[1]
    srv.token = secrets.token_urlsafe(24)
    srv.pagina = pagina
    srv.relogio = relogio
    srv.montar_comando = montar_comando
    srv.caminho_calendario = caminho_calendario
    srv.executor = executor
    srv.monitor = api.MonitorApi(raiz / pasta_logs / "painel", consultar=consultar_api or api.consultar_saude)
    return srv


def main(argv: list[str] | None = None) -> int:
    """Sobe o painel na porta pedida (ou numa livre, se ela estiver ocupada) e abre o navegador."""
    parser = argparse.ArgumentParser(prog="python -m processamento.painel",
                                     description="Painel de operação local (roda os comandos do projeto).")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO, help=f"porta (padrão {PORTA_PADRAO})")
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador")
    args = parser.parse_args(argv)
    try:
        srv = criar_servidor(porta=args.porta)
    except OSError:
        srv = criar_servidor(porta=0)
        print(f"Porta {args.porta} ocupada: o painel usa a porta {srv.porta}.")
    url = f"http://127.0.0.1:{srv.porta}"
    print(f"Painel em {url}  (Ctrl+C para sair)")
    if not args.sem_navegador:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Painel encerrado.")
        if srv.executor.rodando():
            print("Atenção: a ação em andamento recebeu o Ctrl+C também.")
    finally:
        srv.server_close()
    return 0
