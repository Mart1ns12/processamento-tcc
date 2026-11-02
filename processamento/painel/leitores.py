"""Leitura dos arquivos gerados pela rotina e pelo experimento, para o painel de operação.

Só lê: nunca cria, altera nem apaga arquivo; não acessa banco e não importa `fontes`. Funções de leitura
não levantam exceção por arquivo ausente ou quebrado: devolvem o motivo no próprio resultado.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from processamento import calendario
from processamento.calendario import SP
from processamento.rotina.trava import _ler_trava

RAIZ_PADRAO = Path(__file__).resolve().parents[2]
RE_DATA_PASTA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MOTIVOS_COLETA = {"entrega_concluida": "entrega concluída", "entrega_pendente": "entrega ainda não concluída",
                  "entrega_falhou": "entrega falhou", "sem_daily": "nenhum daily de hoje",
                  "daily_agendado": "daily agendado, ainda não começou", "dados_atrasados": "dados atrasados",
                  "falha_consulta": "falha ao consultar o painel da coleta",
                  "sem_esperar": "rodada com --sem-esperar (coleta não estava pronta)"}
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def ler_json(caminho: Path) -> tuple[object | None, str | None]:
    """(dados, None) se leu; senão (None, motivo): não encontrado, JSON inválido ou não foi possível ler."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "não encontrado"
    except ValueError:
        return None, "JSON inválido"
    except OSError:
        return None, "não foi possível ler"
    try:
        return json.loads(texto), None
    except ValueError:
        return None, "JSON inválido"


def _instante(txt: object) -> datetime | None:
    """Data e hora ISO como datetime com fuso de São Paulo (sem fuso = São Paulo); None se inválido."""
    if not isinstance(txt, str):
        return None
    try:
        instante = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=SP)
    return instante


def duracao_segundos(inicio: str | None, fim: str | None) -> int | None:
    """Segundos entre inicio e fim (ISO com fuso); None se faltar algum, for inválido ou fim < inicio."""
    ini, fi = _instante(inicio), _instante(fim)
    if ini is None or fi is None:
        return None
    segundos = (fi - ini).total_seconds()
    if segundos < 0:
        return None
    return int(segundos)


def formatar_duracao(segundos: int | None) -> str:
    """Duração legível: "45 s", "1 min 58 s", "1 h 2 min"; None vira "—"."""
    if segundos is None:
        return "—"
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        return f"{segundos // 60} min {segundos % 60} s"
    return f"{segundos // 3600} h {(segundos % 3600) // 60} min"


def ler_parametros(raiz: Path) -> dict:
    """Parâmetros que o painel usa, lidos direto do yaml (sem os carregadores validados); padrões se faltar."""
    params = {"modelo_oficial": False, "teste_final": {"inicio": None, "fim": None, "liberado": False},
              "publicar_top_provisorio": False, "pasta_saida": "saida", "pasta_logs": "logs",
              "trava": "saida/estado/rotina.trava", "trava_validade_horas": 6.0, "erro": None}
    caminho = Path(raiz) / "processamento" / "config" / "parametros.yaml"
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        params["erro"] = "parametros.yaml não encontrado"
        return params
    except (OSError, ValueError):
        params["erro"] = "parametros.yaml ilegível"
        return params
    try:
        dados = yaml.safe_load(texto)
    except (yaml.YAMLError, ValueError):
        params["erro"] = "parametros.yaml ilegível"
        return params
    if not isinstance(dados, dict):
        dados = {}

    treino = _secao(dados, "treino")
    teste = _secao(treino, "teste_final")
    saida = _secao(dados, "saida")
    rotina = _secao(dados, "rotina")

    params["modelo_oficial"] = _valor(treino, "modelo_oficial", False)
    params["teste_final"] = {"inicio": _texto(_valor(teste, "inicio", None)),
                             "fim": _texto(_valor(teste, "fim", None)),
                             "liberado": _valor(teste, "liberado", False)}
    params["publicar_top_provisorio"] = _valor(saida, "publicar_top_provisorio", False)
    params["pasta_saida"] = _texto(_valor(saida, "pasta", "saida"))
    params["pasta_logs"] = _texto(_valor(rotina, "pasta_logs", "logs"))
    params["trava"] = _texto(_valor(rotina, "trava", "saida/estado/rotina.trava"))
    try:
        params["trava_validade_horas"] = float(_valor(rotina, "trava_validade_horas", 6.0))
    except (TypeError, ValueError):
        params["trava_validade_horas"] = 6.0
    return params


def ler_prazo_rotina(raiz: Path) -> str | None:
    """`rotina.prazo` do parametros.yaml da raiz ("HH:MM"); None se faltar, for inválido ou o arquivo não abrir."""
    caminho = Path(raiz) / "processamento" / "config" / "parametros.yaml"
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return None
    prazo = _secao(dados, "rotina").get("prazo") if isinstance(dados, dict) else None
    if isinstance(prazo, str) and RE_HHMM.match(prazo):
        return prazo
    return None


CHAVES_AJUDA = ("prazo", "prazo_tardio", "inicio_consulta", "intervalo", "limite_historico", "corte_noite",
                "retorno_min", "retorno_max", "defasagem", "pvp_min", "pvp_max_x1000", "sorteios", "teste_final_inicio",
                "tempo_limite_api", "atipico_min_acoes", "atipico_retorno", "atipico_ibov", "coerencia_ivvb11",
                "coerencia_dif", "etapas_conferidas", "eventos_suspeitos")


def _inteiro(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _hhmm_valido(v: object) -> str | None:
    return v if isinstance(v, str) and RE_HHMM.match(v) else None


def ler_valores_ajuda(raiz: Path) -> dict[str, str | None]:
    """Valores do parametros.yaml citados nos textos de ajuda, já formatados; None se faltar ou for inválido."""
    vazio: dict[str, str | None] = dict.fromkeys(CHAVES_AJUDA)
    caminho = Path(raiz) / "processamento" / "config" / "parametros.yaml"
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return vazio
    if not isinstance(dados, dict):
        return vazio
    rotina, saida, fase1 = _secao(dados, "rotina"), _secao(dados, "saida"), _secao(dados, "fase1")
    fund, treino = _secao(dados, "fundamentos"), _secao(dados, "treino")
    teste = _secao(treino, "teste_final")
    rmin, rmax = fase1.get("retorno_suspeito_min"), fase1.get("retorno_suspeito_max")
    intervalo, defas = rotina.get("intervalo_minutos"), fase1.get("base_defasagem_max_pregoes")
    pvp, sorteios = fund.get("pvp_minimo_plausivel"), treino.get("acaso_sorteios")
    pvp_max_x1000 = fund.get("pvp_maximo_plausivel_x1000")
    painel, checagem = _ler_painel_yaml(raiz), _secao(rotina, "checagem")
    tempo_lim, n_min = painel.get("api_tempo_limite_s"), painel.get("dia_atipico_min_acoes")
    ret_abs, ibov_amp = checagem.get("retorno_maximo_abs"), painel.get("dia_atipico_ibov_amplo")
    ivvb_min, dif_min = painel.get("coerencia_ivvb11_min_abs"), painel.get("coerencia_ibov_mediana_dif")
    etapas = rotina.get("etapas_conferidas")
    inicio = teste.get("inicio")
    if isinstance(inicio, date):
        inicio = inicio.isoformat()
    try:
        tf = date.fromisoformat(inicio).strftime("%d/%m/%Y") if isinstance(inicio, str) else None
    except ValueError:
        tf = None
    return {
        "prazo": _hhmm_valido(rotina.get("prazo")),
        "prazo_tardio": _hhmm_valido(rotina.get("prazo_tardio")),
        "inicio_consulta": _hhmm_valido(rotina.get("inicio_consulta")),
        "intervalo": str(intervalo) if _inteiro(intervalo) else None,
        "limite_historico": _hhmm_valido(saida.get("limite_valido_historico")),
        "corte_noite": _hhmm_valido(dados.get("corte_noite")),
        "retorno_min": f"{round(rmin * 100):+d}%" if _numero(rmin) else None,
        "retorno_max": f"{round(rmax * 100):+d}%" if _numero(rmax) else None,
        "defasagem": str(defas) if _inteiro(defas) else None,
        "pvp_min": f"{pvp:g}".replace(".", ",") if _numero(pvp) else None,
        "pvp_max_x1000": f"{pvp_max_x1000:g}".replace(".", ",") if _numero(pvp_max_x1000) else None,
        "sorteios": f"{sorteios:,}".replace(",", ".") if _inteiro(sorteios) else None,
        "teste_final_inicio": tf,
        "tempo_limite_api": f"{tempo_lim:g}".replace(".", ",") + " s" if _numero(tempo_lim) else None,
        "atipico_min_acoes": str(n_min) if _inteiro(n_min) else None,
        "atipico_retorno": _percentual(ret_abs),
        "atipico_ibov": _percentual(ibov_amp),
        "coerencia_ivvb11": _percentual(ivvb_min),
        "coerencia_dif": _percentual(dif_min),
        "etapas_conferidas": ", ".join(etapas) if _lista_de_textos(etapas) else None,
        "eventos_suspeitos": _eventos_suspeitos(fase1.get("eventos_retorno_suspeito")),
    }


def _eventos_suspeitos(eventos: object) -> str | None:
    """Frase com os eventos de `fase1.eventos_retorno_suspeito` (ticker, datas e motivo), agrupados por ticker e motivo.

    None se a lista estiver vazia, faltar ou tiver itens inválidos sem nenhum evento utilizável.
    """
    grupos: dict[tuple[str, str], list[date]] = {}
    for item in eventos if isinstance(eventos, list) else []:
        if not isinstance(item, dict):
            continue
        ticker, datas, motivo = item.get("ticker"), item.get("datas"), item.get("motivo")
        if not (isinstance(ticker, str) and ticker.strip() and isinstance(datas, list)
                and isinstance(motivo, str) and motivo.strip()):
            continue
        for d in datas:
            try:
                dia = d if isinstance(d, date) else date.fromisoformat(d)
            except (TypeError, ValueError):
                continue
            grupos.setdefault((ticker, motivo), []).append(dia)
    if not grupos:
        return None
    partes = [f"{tk} ({', '.join(x.strftime('%d/%m/%Y') for x in sorted(datas))}): {motivo}."
              for (tk, motivo), datas in sorted(grupos.items())]
    return "Também são tratados como suspeitos, mesmo dentro dos limites, os eventos da lista do parametros.yaml: " + " ".join(partes)


def _percentual(v: object) -> str | None:
    """Fração do parametro em percentual, sem sinal ("0.3" vira "30%"); None se não for número."""
    return f"{v * 100:g}".replace(".", ",") + "%" if _numero(v) else None


def _lista_de_textos(v: object) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(e, str) for e in v)


def _nao_vazio(v: object) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _positivo(v: object) -> bool:
    return _numero(v) and v > 0


def _nao_negativo(v: object) -> bool:
    return _numero(v) and v >= 0


def _inteiro_positivo(v: object) -> bool:
    return _inteiro(v) and v > 0


def _ler_painel_yaml(raiz: Path) -> dict:
    """Conteúdo do `processamento/config/painel.yaml` (só o painel lê); {} se faltar ou estiver quebrado."""
    caminho = Path(raiz) / "processamento" / "config" / "painel.yaml"
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return {}
    return dados if isinstance(dados, dict) else {}


# Parâmetros do painel (`painel.yaml` e `rotina.checagem.retorno_maximo_abs` do parametros.yaml) e o validador de cada um.
PARAMETROS_PAINEL = {
    "api_url": _nao_vazio, "api_timeout_s": _positivo, "api_intervalo_s": _nao_negativo,
    "api_tempo_limite_s": _positivo, "api_medicoes": _inteiro_positivo, "dir_api": _nao_vazio,
    "dia_atipico_min_acoes": _inteiro_positivo, "dia_atipico_ibov_amplo": _positivo,
    "coerencia_ivvb11_min_abs": _positivo, "coerencia_ibov_mediana_dif": _positivo,
    "afetadas_max": _inteiro_positivo, "retorno_dia_abs": _positivo,
}


def ler_parametros_painel(raiz: Path) -> dict:
    """Parâmetros do painel, validados; valor que falta ou é inválido vira None (nunca há padrão escrito no código)."""
    caminho = Path(raiz) / "processamento" / "config" / "parametros.yaml"
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    brutos = {**_ler_painel_yaml(raiz),
              "retorno_dia_abs": _secao(_secao(dados, "rotina"), "checagem").get("retorno_maximo_abs")}
    return {chave: (brutos.get(chave) if valida(brutos.get(chave)) else None)
            for chave, valida in PARAMETROS_PAINEL.items()}


def _secao(dados: dict, chave: str) -> dict:
    """dados[chave] se for mapeamento; senão {}."""
    valor = dados.get(chave)
    return valor if isinstance(valor, dict) else {}


def _valor(secao: dict, chave: str, padrao: object) -> object:
    """secao[chave], ou padrao se a chave faltar ou vier vazia (None)."""
    valor = secao.get(chave)
    return padrao if valor is None else valor


def _texto(valor: object) -> str | None:
    """str(valor), ou None se valor for None."""
    return None if valor is None else str(valor)


def ler_trava(raiz: Path, params: dict, agora: datetime) -> dict:
    """Situação da trava da rotina (só leitura). Trava com mais de `trava_validade_horas` é abandonada."""
    validade = params["trava_validade_horas"]
    vazio = {"existe": False, "ativa": False, "abandonada": False, "criada_em": None, "pid": None,
             "idade_min": None, "validade_horas": validade}
    caminho = Path(raiz) / params["trava"]
    if not caminho.is_file():
        return vazio
    try:
        criada_txt, pid, instante = _ler_trava(caminho, agora)
    except OSError:
        # Existe mas não dá para ler: não se sabe a idade. Trata como ativa, para não liberar o banco por engano.
        return {**vazio, "existe": True, "ativa": True, "pid": "desconhecido"}
    idade = agora - instante
    ativa = idade <= timedelta(hours=validade)
    return {"existe": True, "ativa": ativa, "abandonada": not ativa, "criada_em": criada_txt, "pid": pid,
            "idade_min": int(idade.total_seconds() // 60), "validade_horas": validade}


def data_rotina(agora: datetime, caminho_calendario: str | None = None) -> dict:
    """Data que o botão da rotina usa: hoje, se for pregão previsto; senão, o último pregão previsto."""
    d = agora.astimezone(SP).date()
    try:
        if calendario.e_pregao_previsto(d, caminho_calendario):
            return {"data": d.isoformat(), "origem": "hoje", "erro": None}
        anterior = calendario.pregao_anterior_previsto(d, caminho_calendario)
        return {"data": anterior.isoformat(), "origem": "ultimo_pregao", "erro": None}
    except (calendario.ErroCalendario, OSError, ValueError, yaml.YAMLError) as erro:
        return {"data": None, "origem": None, "erro": str(erro)}


def info_hoje(agora: datetime, caminho_calendario: str | None = None) -> dict:
    """Data de hoje em São Paulo e se é pregão previsto (com o motivo, quando não é)."""
    d = agora.astimezone(SP).date()
    base = {"data": d.isoformat(), "dia_semana": DIAS_SEMANA[d.weekday()]}
    try:
        motivo = calendario.motivo_sem_pregao(d, caminho_calendario)
    except (calendario.ErroCalendario, OSError, ValueError, yaml.YAMLError) as erro:
        return {**base, "pregao": None, "motivo": None, "erro": str(erro)}
    return {**base, "pregao": motivo is None, "motivo": motivo, "erro": None}


def _hhmm_sp(txt: object) -> str | None:
    """Hora (HH:MM) de um instante ISO no fuso de São Paulo; None se inválido."""
    instante = _instante(txt)
    return None if instante is None else instante.astimezone(SP).strftime("%H:%M")


def _resumir_coleta(coleta: dict) -> dict:
    """Resumo do `coleta_status` da execução, com o texto do motivo e a hora da entrega."""
    motivo = coleta.get("motivo")
    etapas = coleta.get("etapas")
    return {"consultado": coleta.get("consultado"), "nota": coleta.get("nota"), "motivo": motivo,
            "motivo_texto": MOTIVOS_COLETA.get(motivo, motivo) if isinstance(motivo, str) else motivo,
            "daily": coleta.get("execucao_id"), "origem": coleta.get("origem"),
            "status_execucao": coleta.get("status_execucao"),
            "iniciada_em": coleta.get("iniciada_em"),
            "iniciada_hhmm": _hhmm_sp(coleta.get("iniciada_em")),
            "finalizada_em": coleta.get("finalizada_em"),
            "entrega_concluida_em": coleta.get("entrega_concluida_em"),
            "entrega_hhmm": _hhmm_sp(coleta.get("entrega_concluida_em")),
            "consulta_hhmm": _hhmm_sp(coleta.get("ultima_consulta_em")),
            "etapas": etapas if isinstance(etapas, dict) else None}


def _item_ilegivel(data_pasta: str, tipo: str, arquivo_rel: str, erro: str) -> dict:
    """Item de execução que não pôde ser lido: `legivel` False, com o motivo e o resto vazio."""
    return {"data_referencia": data_pasta, "tipo": tipo, "arquivo": arquivo_rel, "legivel": False, "erro": erro,
            "rodada": None, "status": None, "inicio": None, "fim": None, "gerado_em": None,
            "duracao_s": None, "duracao_texto": None, "n_pacotes": None, "n_avisos": None,
            "pacotes": [], "avisos": [], "coleta": None, "versao_contrato": None}


def resumir_execucao(dados: object, data_pasta: str, tipo: str, arquivo_rel: str) -> dict:
    """Resumo do `execucao.json` (último registro); sem registros válidos vira item ilegível."""
    registros = dados.get("registros") if isinstance(dados, dict) else None
    if not isinstance(registros, list) or not registros or not isinstance(registros[0], dict):
        return _item_ilegivel(data_pasta, tipo, arquivo_rel, "formato inesperado")
    reg = registros[0]
    versao = reg.get("versao_contrato") or dados.get("versao_contrato")
    status = reg.get("status")
    duracao = duracao_segundos(reg.get("inicio"), reg.get("fim"))
    texto = "em andamento" if status == "em_andamento" else formatar_duracao(duracao)
    pacotes_enviados = reg.get("pacotes_enviados")
    pacotes_enviados = pacotes_enviados if isinstance(pacotes_enviados, list) else []
    avisos = reg.get("avisos")
    avisos = avisos if isinstance(avisos, list) else []
    coleta = reg.get("coleta_status")
    return {"data_referencia": data_pasta, "tipo": tipo, "arquivo": arquivo_rel, "legivel": True, "erro": None,
            "rodada": reg.get("rodada"), "status": status, "inicio": reg.get("inicio"), "fim": reg.get("fim"),
            "gerado_em": reg.get("gerado_em"), "duracao_s": duracao, "duracao_texto": texto,
            "n_pacotes": len(pacotes_enviados), "n_avisos": len(avisos),
            "pacotes": [{"pacote": p.get("pacote"), "registros": p.get("registros"), "removidos": p.get("removidos")}
                        for p in pacotes_enviados if isinstance(p, dict)],
            "avisos": avisos,
            "coleta": _resumir_coleta(coleta) if isinstance(coleta, dict) else None,
            "versao_contrato": versao}


def _datas_com_execucao(base: Path) -> list[tuple[date, Path]]:
    """(data, pasta) das subpastas de base com nome de data válido e execucao.json; [] se base não existir."""
    try:
        pastas = list(base.iterdir())
    except OSError:
        return []
    achadas = []
    for pasta in pastas:
        if not RE_DATA_PASTA.match(pasta.name) or not pasta.is_dir():
            continue
        try:
            d = date.fromisoformat(pasta.name)
        except ValueError:
            continue
        if (pasta / "execucao.json").is_file():
            achadas.append((d, pasta))
    return achadas


def listar_execucoes(raiz: Path, pasta: str, tipo: str) -> list[dict]:
    """Execuções de raiz/pasta (uma por dia, a última rodada), da data mais nova para a mais antiga."""
    raiz = Path(raiz)
    itens = []
    for d, sub in sorted(_datas_com_execucao(raiz / pasta), key=lambda par: par[0], reverse=True):
        arquivo = sub / "execucao.json"
        arquivo_rel = arquivo.relative_to(raiz).as_posix()
        dados, erro = ler_json(arquivo)
        if erro is not None:
            itens.append(_item_ilegivel(sub.name, tipo, arquivo_rel, erro))
        else:
            itens.append(resumir_execucao(dados, sub.name, tipo, arquivo_rel))
    return itens


def ultima_execucao(itens: list[dict]) -> dict | None:
    """Item legível com o maior `gerado_em`; None se não houver nenhum."""
    melhor, melhor_instante = None, None
    for item in itens:
        if not item.get("legivel"):
            continue
        instante = _instante(item.get("gerado_em"))
        if instante is None:
            continue
        if melhor_instante is None or instante > melhor_instante:
            melhor, melhor_instante = item, instante
    return melhor


def ultima_execucao_valida(itens: list[dict]) -> dict | None:
    """Última execução legível com status ok ou parcial (ignora falhou e em andamento); None se não houver."""
    return ultima_execucao([i for i in itens if i.get("legivel") and i.get("status") in ("ok", "parcial")])


def d_mais_recente(raiz: Path, pasta_saida: str) -> date | None:
    """Data mais nova de raiz/pasta_saida que tem execucao.json (legível ou não); None se não houver."""
    datas = [d for d, _ in _datas_com_execucao(Path(raiz) / pasta_saida)]
    return max(datas, default=None)
