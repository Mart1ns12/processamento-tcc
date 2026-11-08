"""Aba Experimento do painel: só a operação do modelo (modelo em produção, dataset, teste final, rodadas e checklist).

Lê arquivos (só leitura): docs/protocolo_tentativas.jsonl, docs/busca_rodada_NNN_sensibilidade.json,
docs/protocolo_variaveis.md, saida/experimento/dataset-*.json e processamento/config/parametros.yaml.
Não mostra métrica de desempenho nem ação do top 5. Não acessa o banco nem a rede.
Arquivo ausente ou quebrado vira disponivel False, "sem dados" ou None; nenhuma função levanta exceção por isso.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from processamento import calendario
from processamento.calendario import SP
from processamento.experimento import preparacao
from processamento.painel.leitores import _instante, ler_json
from processamento.painel.saude import tabela_md

RE_DATASET = re.compile(r"^dataset-(\w+)-(\d{4}-\d{2}-\d{2})\.json$")
RE_SENSIBILIDADE = re.compile(r"^busca_rodada_(\d{3})_sensibilidade\.json$")
SUBTITULO_CHECKLIST = "Checklist antes do teste final (D1 a D10)"
IDS_CHECKLIST = [f"D{n}" for n in range(1, 11)]
FONTE_CHECKLIST = "docs/protocolo_variaveis.md, seção 8"
FAMILIAS = {"logistica": "Regressão logística", "xgb": "XGBoost"}
TITULOS_TESTE = {"ativa": "Travado", "definido_nao_liberado": "Fim definido, ainda travado",
                 "liberado": "Liberado (uso único)", "usado": "Já usado"}


# ---------------------------------------------------------------- auxiliares

def _inteiro(v: object) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _dia(txt: object) -> date | None:
    """Data AAAA-MM-DD como date; None se não for data."""
    if not isinstance(txt, str):
        return None
    try:
        return date.fromisoformat(txt)
    except ValueError:
        return None


def _dia_do_instante(txt: object) -> date | None:
    """Dia em São Paulo de um instante ISO (sem fuso = São Paulo); None se inválido."""
    instante = _instante(txt)
    return instante.astimezone(SP).date() if instante is not None else None


def _br(dia: date | None) -> str | None:
    return dia.strftime("%d/%m/%Y") if dia is not None else None


def _tabela_checklist(texto: str) -> list[dict[str, str]] | None:
    """Primeira tabela depois do `### Checklist...`, mesmo com parágrafo entre o título e a tabela; None se não há."""
    linhas = texto.splitlines()
    cabecalho = "### " + SUBTITULO_CHECKLIST
    i = next((k for k, linha in enumerate(linhas) if linha == cabecalho), None)
    if i is None:
        return None
    fim = next((k for k in range(i + 1, len(linhas)) if linhas[k].startswith("#")), len(linhas))
    inicio = next((k for k in range(i + 1, fim) if linhas[k].startswith("|")), None)
    if inicio is None:
        return None
    return tabela_md([cabecalho, *linhas[inicio:fim]], SUBTITULO_CHECKLIST)


def _registro(raiz: Path) -> tuple[list[dict], str | None]:
    """(eventos, erro) do registro do protocolo. Arquivo ausente: ([], None). Import ou leitura com problema: ([], motivo)."""
    caminho = Path(raiz) / "docs" / "protocolo_tentativas.jsonl"
    if not caminho.exists():
        return [], None
    try:
        from processamento.experimento import protocolo_registro
        return protocolo_registro.ler(caminho), None
    except Exception as erro:
        return [], str(erro) or type(erro).__name__


# ---------------------------------------------------------------- modelo em produção

def _familia_do_vencedor(v: object) -> str | None:
    """Família do vencedor da busca: "referencia" é o XGBoost do ponto de partida."""
    if not isinstance(v, str):
        return None
    if v == "referencia" or v.startswith("xgb"):
        return "xgb"
    if v.startswith("lgbm"):
        return "lgbm"
    return v


def _configuracao(eventos: list[dict] | None, familia: str | None) -> str | None:
    """Rodada da busca que escolheu a família e a rodada que a reproduziu, ex.: "busca rodada 001 (reproduzida na 002)"."""
    if not eventos or not familia:
        return None
    fins = [e for e in eventos if e.get("tipo") == "busca" and e.get("evento") == "fim"]
    candidatas = [e for e in fins
                  if e.get("repete_rodada") is None and e.get("status") != "invalida"
                  and _familia_do_vencedor(e.get("vencedor")) == familia]
    # a mais nova é a oficial
    n = max((r for r in (_inteiro(e.get("rodada")) for e in candidatas) if r is not None), default=None)
    if _inteiro(n) is None:
        return None
    k = next((e.get("rodada") for e in fins
              if e.get("repete_rodada") == n and e.get("reproduziu") is True), None)
    texto = f"busca rodada {n:03d}"
    if _inteiro(k) is not None:
        texto += f" (reproduzida na {k:03d})"
    return texto


def modelo_producao(params: dict, experimento: dict, eventos: list[dict] | None) -> dict:
    """Modelo em produção (modelos/, o mais novo da família). `eventos` None = registro com problema."""
    m = experimento.get("modelo_em_uso")
    m = m if isinstance(m, dict) else None
    familia = (m.get("familia") if m else None) or params.get("familia_producao")
    situacao = experimento.get("situacao_modelo")
    top_publicado = experimento.get("top_publicado")
    registros = experimento.get("registros") if isinstance(experimento.get("registros"), dict) else {}
    tops, resultados = _inteiro(registros.get("tops")), _inteiro(registros.get("resultados"))
    if tops is None or resultados is None:
        registros_texto = "sem dados"
    else:
        registros_texto = (f"{tops} {'top' if tops == 1 else 'tops'} · "
                           f"{resultados} {'resultado' if resultados == 1 else 'resultados'}")
    base = {
        "familia": familia,
        "familia_texto": FAMILIAS.get(familia, familia),
        "situacao": situacao,
        "oficial_texto": "sim (oficial)" if situacao == "oficial" else "não (provisório)",
        "configuracao": _configuracao(eventos, familia),
        "top_publicado": top_publicado,
        "top_texto": {True: "publicado na interface", False: "retido (não enviado à interface)"}.get(top_publicado, "sem dados"),
        "registros_texto": registros_texto,
    }
    if m is None:
        return {"disponivel": False, "arquivo": None, "treinado_em": None, "treinado_em_texto": None,
                "versao_preparacao": None, "periodo_texto": None, "linhas_treino": None, **base}
    gerado = _dia_do_instante(m.get("gerado_em"))
    periodo = m.get("periodo_treino") if isinstance(m.get("periodo_treino"), dict) else {}
    ini, fim = _dia(periodo.get("inicio")), _dia(periodo.get("fim"))
    return {
        "disponivel": True,
        "arquivo": m.get("arquivo"),
        "treinado_em": gerado.isoformat() if gerado else None,
        "treinado_em_texto": _br(gerado),
        "versao_preparacao": _inteiro(m.get("versao_preparacao")),
        "periodo_texto": f"{_br(ini)} a {_br(fim)}" if ini and fim else None,
        "linhas_treino": _inteiro(m.get("n_linhas_treino")),
        **base,
    }


# ---------------------------------------------------------------- dataset

def _sem_coleta(raiz: Path) -> list[str] | None:
    """Períodos de experimento.periodos_sem_coleta do parametros.yaml como "DD/MM/AAAA a DD/MM/AAAA"; None se ausente ou inválido."""
    try:
        dados = yaml.safe_load((Path(raiz) / "processamento" / "config" / "parametros.yaml").read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return None
    exp = dados.get("experimento") if isinstance(dados, dict) else None
    periodos = exp.get("periodos_sem_coleta") if isinstance(exp, dict) else None
    if not isinstance(periodos, list):
        return None
    textos = []
    for p in periodos:
        if not isinstance(p, dict):
            return None
        ini, fim = _br(_dia(p.get("inicio"))), _br(_dia(p.get("fim")))
        if ini is None or fim is None:
            return None
        textos.append(f"{ini} a {fim}")
    return textos


def dataset_info(raiz: Path, versao_modelo: int | None, versao_noticias: str | None = None) -> dict:
    """Versão de preparação do código, do modelo em produção e do último dataset gerado para a mesma versão de notícias."""
    codigo = preparacao.VERSAO_PREPARACAO
    versao = versao_noticias if isinstance(versao_noticias, str) and versao_noticias else "todas"
    candidatos = []
    for arq in (Path(raiz) / "saida" / "experimento").glob("dataset-*.json"):
        m = RE_DATASET.match(arq.name)
        if m and m.group(1) == versao:
            candidatos.append((m.group(2), arq))
    ultimo = None
    if candidatos:
        data, arq = max(candidatos, key=lambda c: c[0])
        dados, _ = ler_json(arq)
        dados = dados if isinstance(dados, dict) else {}
        gerado = _dia_do_instante(dados.get("gerado_em"))
        sha = dados.get("sha256")
        ultimo = {
            "arquivo": arq.name,
            "data": data,
            "versao_preparacao": _inteiro(dados.get("versao_preparacao")),
            "gerado_em_texto": _br(gerado),
            "sha256_curto": sha[:12] if isinstance(sha, str) and sha else None,
            "linhas": _inteiro(dados.get("linhas")),
            "pregoes": _inteiro(dados.get("pregoes")),
        }
    ultimo_texto = None
    titulo, estado = "sem dados", "idle"
    if ultimo is not None:
        uv = ultimo["versao_preparacao"]
        ultimo_texto = " · ".join([f"v{uv}" if uv is not None else "versão sem dados",
                                   ultimo["gerado_em_texto"] or "data sem dados"])
        if uv == codigo and versao_modelo == codigo:
            titulo, estado = f"Versão {codigo} em uso", "ok"
        elif uv == codigo:
            titulo, estado = f"Versão {codigo} gerada, falta treinar", "warn"
        else:
            titulo, estado = f"Versão {codigo} pendente", "warn"
    sem_coleta = _sem_coleta(raiz)
    if sem_coleta is None:
        sem_coleta_texto = "sem dados"
    else:
        sem_coleta_texto = "; ".join(sem_coleta) or "nenhum"
    return {
        "versao_codigo": codigo,
        "versao_modelo": versao_modelo,
        "titulo": titulo,
        "estado": estado,
        "ultimo": ultimo,
        "ultimo_texto": ultimo_texto,
        "sem_coleta": sem_coleta,
        "sem_coleta_texto": sem_coleta_texto,
    }


# ---------------------------------------------------------------- teste final

def _pregoes_ate_ontem(inicio: date | None, fim: date | None, hoje_iso: str, caminho_calendario: str | None) -> int | None:
    """Pregões de inicio até o fim (ou até ontem), sem os feriados da B3; None se faltar dado ou o calendário falhar."""
    hoje = _dia(hoje_iso)
    if inicio is None or hoje is None:
        return None
    ate = hoje - timedelta(days=1)
    if fim is not None and fim < ate:
        ate = fim
    try:
        feriados = calendario.feriados_b3(caminho_calendario)
    except (calendario.ErroCalendario, OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        return None
    contagem = 0
    dia = inicio
    while dia <= ate:
        if dia.weekday() < 5 and dia not in feriados:
            contagem += 1
        dia += timedelta(days=1)
    return contagem


def teste_final_info(trava: dict, hoje_iso: str, caminho_calendario: str | None = None) -> dict:
    """Estado do teste final (uso único) a partir de `trava_teste_final` do experimento."""
    trava = trava if isinstance(trava, dict) else {}
    estado = trava.get("estado")
    inicio = _dia(trava.get("inicio"))
    fim_bruto = trava.get("fim")
    fim = _dia(fim_bruto)
    return {
        "estado": estado,
        "titulo": TITULOS_TESTE.get(estado, "sem dados"),
        "texto": trava.get("texto"),
        "inicio": trava.get("inicio"),
        "inicio_texto": _br(inicio),
        "fim": fim_bruto,
        "fim_texto": _br(fim) or ("a definir (D2)" if fim_bruto is None else None),
        "pregoes": _pregoes_ate_ontem(inicio, fim, hoje_iso, caminho_calendario),
        "uso_texto": "já usado (uso único)" if estado == "usado" else "nenhum (uso único)",
    }


# ---------------------------------------------------------------- rodadas do registro

def _nome_rodada(tipo: object, rodada: object) -> str:
    rotulo = "Protocolo" if tipo == "protocolo" else "Busca"
    numero = f"{rodada:03d}" if _inteiro(rodada) is not None else "sem dados"
    return f"{rotulo} · rodada {numero}"


def _data_do_evento(evento: dict) -> str:
    return _br(_dia_do_instante(evento.get("em"))) or "sem dados"


def _item_fim(evento: dict) -> dict:
    nome = _nome_rodada(evento.get("tipo"), evento.get("rodada"))
    relatorio = evento.get("relatorio")
    sufixo = f" · {relatorio}" if isinstance(relatorio, str) and relatorio else ""
    data = _data_do_evento(evento)
    repete = evento.get("repete_rodada")
    if _inteiro(repete) is not None:
        status_texto, estado, conferencia = {
            True: ("reproduziu", "ok", "mesmo resultado"),
            False: ("não reproduziu", "bad", "resultado diferente"),
        }.get(evento.get("reproduziu"), ("repetição", "warn", "sem conferência"))
        detalhe = f"{data} · repetição da rodada {repete:03d}, {conferencia}{sufixo}"
    else:
        status = evento.get("status")
        status = status if isinstance(status, str) else None
        status_texto = {"valida": "válida", "concluida": "concluída", "invalida": "inválida"}.get(status, status or "sem dados")
        estado = "ok" if status in ("valida", "concluida") else ("bad" if status == "invalida" else "warn")
        if evento.get("tipo") == "protocolo":
            adotados = evento.get("adotados")
            resumo = ("adotados: " + ", ".join(str(a) for a in adotados)) if isinstance(adotados, list) and adotados \
                else "nenhum bloco adotado"
        else:
            vencedor = evento.get("vencedor")
            resumo = f"vencedor: {vencedor}" if vencedor else "sem vencedor"
        detalhe = f"{data} · {resumo}{sufixo}"
    return {"nome": nome, "status_texto": status_texto, "estado": estado, "detalhe": detalhe}


def _itens_sensibilidade(raiz: Path) -> list[dict]:
    itens = []
    arquivos = sorted((Path(raiz) / "docs").glob("busca_rodada_*_sensibilidade.json"), key=lambda p: p.name)
    for arq in arquivos:
        m = RE_SENSIBILIDADE.match(arq.name)
        if not m:
            continue
        dados, _ = ler_json(arq)
        dados = dados if isinstance(dados, dict) else {}
        data = _br(_dia(dados.get("data")))
        contagem = dados.get("contagem") if isinstance(dados.get("contagem"), dict) else {}
        analises = _inteiro(contagem.get("analises"))
        trecho_data = f"dados de {data}" if data else "dados sem data"
        trecho_analises = f"{analises} análises" if analises is not None else "análises sem dados"
        itens.append({
            "nome": f"Sensibilidade (exploratória) · rodada {m.group(1)}",
            "status_texto": "registrada",
            "estado": "info",
            "detalhe": f"{trecho_data} · {trecho_analises} · fora da contagem do protocolo",
        })
    return itens


def rodadas(raiz: Path, registro: tuple[list[dict], str | None] | None = None) -> dict:
    """Registro do protocolo (rodadas, interrompidas, sensibilidade e próxima rodada pendente)."""
    eventos, erro = registro if registro is not None else _registro(raiz)
    if erro is not None:
        return {"disponivel": False, "motivo": f"Registro do protocolo com problema: {erro}",
                "integridade": "quebrada", "itens": []}
    caminho = Path(raiz) / "docs" / "protocolo_tentativas.jsonl"
    motivo = None
    integridade = "ok"
    if not caminho.exists():
        motivo = "Nenhuma rodada registrada (docs/protocolo_tentativas.jsonl ausente)."
        integridade = None

    itens = [_item_fim(e) for e in eventos if e.get("evento") == "fim"]
    fins = {(e.get("tipo"), e.get("rodada")) for e in eventos if e.get("evento") == "fim"}
    for e in eventos:
        if e.get("evento") == "inicio" and (e.get("tipo"), e.get("rodada")) not in fins:
            itens.append({"nome": _nome_rodada(e.get("tipo"), e.get("rodada")), "status_texto": "interrompida",
                          "estado": "warn", "detalhe": f"{_data_do_evento(e)} · começou e não terminou"})
    itens.extend(_itens_sensibilidade(raiz))

    versoes = [_inteiro((e.get("assinatura") or {}).get("versao_preparacao")) for e in eventos
               if e.get("evento") == "fim" and isinstance(e.get("assinatura"), dict)]
    versoes = [v for v in versoes if v is not None]
    atual = preparacao.VERSAO_PREPARACAO
    if versoes and atual > max(versoes):
        itens.append({
            "nome": "Próxima rodada (dados novos)",
            "status_texto": "aguardando",
            "estado": "warn",
            "detalhe": (f"O código está na versão de preparação {atual} e as rodadas registradas usaram a "
                        f"{max(versoes)}. Pela D5, dados novos antes do teste final geram nova rodada, "
                        "que passa a ser a oficial."),
        })
    return {"disponivel": True, "motivo": motivo, "integridade": integridade, "itens": itens}


# ---------------------------------------------------------------- checklist D1 a D10

def checklist(raiz: Path, params: dict) -> dict:
    """Tabela do checklist antes do teste final (docs/protocolo_variaveis.md, seção 8), item a item."""
    vazio = {"disponivel": False, "motivo": None, "fonte": FONTE_CHECKLIST, "n_fechadas": None,
             "n_total": len(IDS_CHECKLIST), "itens": []}
    caminho = Path(raiz) / "docs" / "protocolo_variaveis.md"
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**vazio, "motivo": "docs/protocolo_variaveis.md não encontrado"}
    except (OSError, ValueError):
        return {**vazio, "motivo": "docs/protocolo_variaveis.md ilegível"}
    tabela = _tabela_checklist(texto)
    if tabela is None:
        return {**vazio, "motivo": "A tabela do checklist (D1 a D10) não está em docs/protocolo_variaveis.md, seção 8."}

    por_id = {(linha.get("Id") or "").strip(): linha for linha in tabela}
    itens, faltam = [], []
    for id_ in IDS_CHECKLIST:
        linha = por_id.get(id_)
        if linha is None:
            faltam.append(id_)
            item = {"id": id_, "texto": None, "situacao": None, "cumprida": None, "automatica": False}
        else:
            situacao = (linha.get("Situação") or "").strip().lower() or None
            item = {"id": id_,
                    "texto": (linha.get("Decisão") or "").strip() or None,
                    "situacao": situacao,
                    "cumprida": {"fechada": True, "pendente": False}.get(situacao),
                    "automatica": False}
        itens.append(item)

    teste = params.get("teste_final") if isinstance(params.get("teste_final"), dict) else {}
    fim = teste.get("fim")
    if fim:
        d2 = next(i for i in itens if i["id"] == "D2")
        d2.update({"situacao": "fechada", "cumprida": True, "automatica": True,
                   "texto": f"Data de fim do teste final: {_br(_dia(fim)) or fim}"})

    return {
        "disponivel": True,
        "motivo": f"Faltam no protocolo: {', '.join(faltam)}" if faltam else None,
        "fonte": FONTE_CHECKLIST,
        "n_fechadas": sum(1 for i in itens if i["cumprida"] is True),
        "n_total": len(IDS_CHECKLIST),
        "itens": itens,
    }


# ---------------------------------------------------------------- aviso e operação

def aviso(familia: str | None, modelo: dict, versao_codigo: int) -> dict | None:
    """Aviso da aba: modelo ausente, ou modelo de versão de preparação diferente do código."""
    if not modelo.get("disponivel"):
        return {"nivel": "warn", "texto": f"Nenhum modelo da família {familia} em modelos/: o top 5 interno não é gerado."}
    versao_modelo = modelo.get("versao_preparacao")
    if versao_modelo is not None and versao_modelo != versao_codigo:
        return {"nivel": "warn",
                "texto": (f"Top 5 interno pausado: o modelo em produção é da versão de preparação {versao_modelo} "
                          f"e o código está na {versao_codigo}. Volta quando o modelo for treinado com um dataset "
                          f"da versão {versao_codigo}.")}
    return None


def operacao(raiz: Path, params: dict, experimento: dict, hoje_iso: str, caminho_calendario: str | None = None) -> dict:
    """Operação do modelo (aba Experimento): modelo em produção, dataset, teste final, rodadas e checklist."""
    params = params if isinstance(params, dict) else {}
    experimento = experimento if isinstance(experimento, dict) else {}
    registro = _registro(raiz)
    eventos = registro[0] if registro[1] is None else None
    modelo = modelo_producao(params, experimento, eventos)
    m = experimento.get("modelo_em_uso")
    versao_noticias = m.get("versao_noticias") if isinstance(m, dict) else None
    return {
        "situacao": experimento.get("situacao_modelo"),
        "aviso": aviso(params.get("familia_producao"), modelo, preparacao.VERSAO_PREPARACAO),
        "modelo": modelo,
        "dataset": dataset_info(raiz, modelo["versao_preparacao"], versao_noticias),
        "teste_final": teste_final_info(experimento.get("trava_teste_final"), hoje_iso, caminho_calendario),
        "rodadas": rodadas(raiz, registro),
        "checklist": checklist(raiz, params),
    }
