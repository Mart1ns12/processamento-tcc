"""Aba Coleta do painel: lê o docs/diagnostico_banco.md (só leitura) e devolve os indicadores da coleta.

Não acessa o banco nem a rede. Seção, tabela ou nota ausentes viram "sem dados" ou disponivel False;
nenhuma função levanta exceção por arquivo ausente ou quebrado.
"""

from __future__ import annotations

import re
from pathlib import Path

from processamento.painel.relatorios import ler_diagnostico
from processamento.painel.saude import _data_br, _milhar, _notas, _pct, _secao, tabela_md

FALTA_SERIE = (
    "O diagnóstico traz só os meses com poucas notícias, com todas as origens somadas; "
    "a contagem mês a mês do Google News não está no relatório."
)
ROTULOS_ORIGEM = {"google_news": "Google News", "cvm_ipe": "CVM", "wordpress": "WordPress"}
RE_KPI_NOTICIAS = re.compile(r"^(\d+) linhas = (\d+) artigos")
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
MOTIVO_SEM_SECAO = "Seção não encontrada no diagnóstico."
MOTIVO_SEM_TABELA = "Tabela não encontrada na seção."


# ---------------------------------------------------------------- auxiliares

def _int(texto: str) -> int | None:
    try:
        return int(texto)
    except (TypeError, ValueError):
        return None


def _float(texto: str) -> float | None:
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def ler_md(docs_md: Path) -> tuple[dict, list[str]] | None:
    """(diagnóstico, linhas) do .md; None se ausente, ilegível ou sem o formato reconhecido."""
    diag = ler_diagnostico(docs_md)
    if not diag.get("disponivel"):
        return None
    try:
        linhas = docs_md.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return diag, linhas


def _motivo(docs_md: Path) -> str:
    return ler_diagnostico(docs_md).get("motivo") or "docs/diagnostico_banco.md não pode ser lido"


def _item_sem_dados(id_: str, nome: str) -> dict:
    return {"id": id_, "nome": nome, "valor": None, "valor_texto": "sem dados", "fracao": None,
            "aguardando": None, "nota": "sem dados", "fonte": None}


def _item_fracao(id_: str, nome: str, fracao: float, aguardando: int, fonte: str) -> dict:
    return {"id": id_, "nome": nome, "valor": fracao, "valor_texto": _pct(fracao), "fracao": fracao,
            "aguardando": aguardando, "nota": f"{_milhar(aguardando)} aguardando", "fonte": fonte}


# ---------------------------------------------------------------- contagens do §5 e do §16

def contagem_finbert(linhas: list[str]) -> dict | None:
    """Veredito do FinBERT (§5, tabela 'Probabilidades do FinBERT'): ok, sem_prob e total de linhas."""
    achada = _secao(linhas, "Notícias (")
    if achada is None:
        return None
    numero, titulo, corpo = achada
    tabela = tabela_md(corpo, "Probabilidades do FinBERT")
    if not tabela:
        return None
    valores = {linha.get("veredito"): _int(linha.get("linhas", "")) for linha in tabela}
    if any(v is None for v in valores.values()) or "ok" not in valores or "sem_prob" not in valores:
        return None
    return {"ok": valores["ok"], "sem_prob": valores["sem_prob"], "total": sum(valores.values()),
            "fonte": f"Seção {numero}: {titulo}"}


def contagem_juiza(linhas: list[str]) -> dict | None:
    """Colunas de v1-noticias.papel na seção 'Vazios e zeros' (§16): total de linhas e nulos."""
    achada = _secao(linhas, "Vazios e zeros")
    if achada is None:
        return None
    numero, titulo, corpo = achada
    for linha in tabela_md(corpo, "Colunas com nulos, textos vazios ou zeros") or []:
        if linha.get("tabela") == "v1-noticias" and linha.get("coluna") == "papel":
            total, nulos = _int(linha.get("total", "")), _int(linha.get("nulos", ""))
            if total is None or nulos is None:
                return None
            return {"total": total, "nulos": nulos, "fonte": f"Seção {numero}: {titulo}"}
    return None


# ---------------------------------------------------------------- indicadores

def _item_noticias(diag: dict, linhas: list[str]) -> dict:
    id_, nome = "noticias", "Notícias no banco"
    achada = _secao(linhas, "Resumo das tabelas")
    if achada is None:
        return _item_sem_dados(id_, nome)
    numero, titulo, corpo = achada
    m = None
    for nota in _notas(diag, "Resumo das tabelas"):
        m = RE_KPI_NOTICIAS.match(nota)
        if m:
            break
    if m is None:
        return _item_sem_dados(id_, nome)
    n_linhas, artigos = int(m.group(1)), int(m.group(2))
    nota = f"{_milhar(artigos)} artigos"
    for linha in tabela_md(corpo, "Período e entidades") or []:
        if linha.get("tabela") == "v1-noticias":
            ini, fim = linha.get("inicio", ""), linha.get("fim", "")
            if RE_DATA.fullmatch(ini) and RE_DATA.fullmatch(fim):
                nota += f" · {_data_br(ini)} a {_data_br(fim)}"
            break
    return {"id": id_, "nome": nome, "valor": n_linhas, "valor_texto": _milhar(n_linhas),
            "fracao": None, "aguardando": None, "nota": nota, "fonte": f"Seção {numero}: {titulo}"}


def _item_finbert(linhas: list[str]) -> dict:
    id_, nome = "finbert", "Com FinBERT"
    cont = contagem_finbert(linhas)
    if cont is None or cont["total"] <= 0:
        return _item_sem_dados(id_, nome)
    return _item_fracao(id_, nome, cont["ok"] / cont["total"], cont["sem_prob"], cont["fonte"])


def _item_juiza(linhas: list[str]) -> dict:
    id_, nome = "juiza", "Julgadas pela juíza"
    cont = contagem_juiza(linhas)
    if cont is None or cont["total"] <= 0:
        return _item_sem_dados(id_, nome)
    fracao = (cont["total"] - cont["nulos"]) / cont["total"]
    return _item_fracao(id_, nome, fracao, cont["nulos"], cont["fonte"])


def indicadores_coleta(docs_md: Path) -> dict:
    """Três indicadores da coleta: notícias no banco, com FinBERT e julgadas pela juíza."""
    lido = ler_md(docs_md)
    if lido is None:
        return {"disponivel": False, "motivo": _motivo(docs_md), "gerado_em": None,
                "itens": [_item_sem_dados("noticias", "Notícias no banco"),
                          _item_sem_dados("finbert", "Com FinBERT"),
                          _item_sem_dados("juiza", "Julgadas pela juíza")]}
    diag, linhas = lido
    return {"disponivel": True, "motivo": None, "gerado_em": diag.get("gerado_em"),
            "itens": [_item_noticias(diag, linhas), _item_finbert(linhas), _item_juiza(linhas)]}


def noticias_ano_origem(docs_md: Path) -> dict:
    """Artigos distintos por ano e origem (§5, 'Hora da publicação, por ano e origem')."""
    vazio = {"anos": [], "linhas": [], "maximo": None, "fonte": None}
    lido = ler_md(docs_md)
    if lido is None:
        return {"disponivel": False, "motivo": _motivo(docs_md), **vazio}
    _diag, linhas = lido
    achada = _secao(linhas, "Notícias (")
    if achada is None:
        return {"disponivel": False, "motivo": MOTIVO_SEM_SECAO, **vazio}
    numero, titulo, corpo = achada
    tabela = tabela_md(corpo, "Hora da publicação, por ano e origem (artigos distintos)")
    if tabela is None:
        return {"disponivel": False, "motivo": MOTIVO_SEM_TABELA, **vazio}

    anos: list[str] = []
    valores: dict[str, dict[str, int | None]] = {}
    for linha in tabela:
        ano, origem = linha.get("ano", ""), linha.get("origem", "")
        if ano not in anos:
            anos.append(ano)
        valores.setdefault(origem, {})[ano] = _int(linha.get("total", ""))

    ordem = [o for o in ROTULOS_ORIGEM if o in valores]
    ordem += sorted(o for o in valores if o not in ROTULOS_ORIGEM)
    series = [{"origem": o, "rotulo": ROTULOS_ORIGEM.get(o, o), "valores": [valores[o].get(a) for a in anos]}
              for o in ordem]
    todos = [v for por_ano in valores.values() for v in por_ano.values() if v is not None]
    return {"disponivel": True, "motivo": None, "anos": anos, "linhas": series,
            "maximo": max(todos) if todos else None,
            "fonte": f"Seção {numero}: {titulo} · artigos distintos"}


def noticias_mes(docs_md: Path) -> dict:
    """Meses com poucas notícias (§15), com todas as origens somadas."""
    vazio = {"nota": None, "meses": [], "serie_completa": False, "falta": None, "fonte": None}
    lido = ler_md(docs_md)
    if lido is None:
        return {"disponivel": False, "motivo": _motivo(docs_md), **vazio}
    diag, linhas = lido
    achada = _secao(linhas, "Notícias por mês")
    if achada is None:
        return {"disponivel": False, "motivo": MOTIVO_SEM_SECAO, **vazio}
    numero, titulo, corpo = achada
    notas = _notas(diag, "Notícias por mês")
    tabela = tabela_md(corpo, "Meses com poucas notícias")
    if tabela is None:
        if not any(n.startswith("nenhum mês abaixo") for n in notas):
            return {"disponivel": False, "motivo": MOTIVO_SEM_TABELA, **vazio}
        tabela = []

    meses = []
    for linha in tabela:
        mes = linha.get("mes", "")
        artigos = _int(linha.get("artigos", ""))
        mediana = _float(linha.get("mediana_referencia", ""))
        situacao = linha.get("situacao", "")
        fracao = artigos / mediana if artigos is not None and mediana is not None and mediana > 0 else None
        if situacao == "cadastrado":
            estado = "conhecido"
        elif situacao.startswith("rever"):
            estado = "rever"
        else:
            estado = "outro"
        meses.append({"mes": mes, "mes_texto": _data_br(mes), "artigos": artigos, "mediana": mediana,
                      "fracao": fracao, "situacao": situacao, "estado": estado})
    return {"disponivel": True, "motivo": None, "nota": notas[0] if notas else None, "meses": meses,
            "serie_completa": False, "falta": FALTA_SERIE, "fonte": f"Seção {numero}: {titulo}"}


def falhas_etapas(docs_md: Path) -> dict:
    """Linhas com status 'falhou' por etapa (§17, 'Etapas do painel'), da que mais falhou para a que menos."""
    vazio = {"fonte": None, "itens": []}
    lido = ler_md(docs_md)
    if lido is None:
        return {"disponivel": False, "motivo": _motivo(docs_md), **vazio}
    _diag, linhas = lido
    achada = _secao(linhas, "Painel de execuções")
    if achada is None:
        return {"disponivel": False, "motivo": MOTIVO_SEM_SECAO, **vazio}
    numero, titulo, corpo = achada
    tabela = tabela_md(corpo, "Etapas do painel")
    if tabela is None:
        return {"disponivel": False, "motivo": MOTIVO_SEM_TABELA, **vazio}

    falhas: dict[str, int] = {}
    for linha in tabela:
        n = _int(linha.get("n", ""))
        if linha.get("status") != "falhou" or n is None:
            continue
        id_ = linha.get("etapa_id", "")
        falhas[id_] = falhas.get(id_, 0) + n

    # import local: visao importa outros módulos do painel e pode vir a importar esta aba
    from processamento.painel.visao import ROTULOS_ETAPA

    itens = [{"id": id_, "rotulo": ROTULOS_ETAPA.get(id_, id_), "falhou": n}
             for id_, n in sorted(falhas.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"disponivel": True, "motivo": None, "fonte": f"Seção {numero}: {titulo}", "itens": itens}
