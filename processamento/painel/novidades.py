"""Novidades do painel: compara o diagnóstico atual com o anterior guardado em logs/painel/diagnosticos.

Cada diagnóstico vira um resumo JSON (só os dados que as comparações usam). Só `atualizar_resumos` grava,
e só dentro da pasta do painel. Nenhuma função acessa banco ou rede.
Arquivo ausente ou ilegível vira `disponivel` False ou lista vazia, nunca exceção.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections import Counter
from pathlib import Path

from processamento.painel.relatorios import ler_diagnostico
from processamento.painel.saude import (
    RE_COBERTURA,
    RE_QTD_ACOES,
    RE_QTD_ACOES_ZERO,
    RE_RETORNOS,
    RE_RETORNOS_ZERO,
    _data_br,
    _milhar,
    _notas,
    _plural,
    _secao,
    cartoes_saude,
    tabela_md,
)

VISTO, ANTERIOR = "diagnostico_visto.log", "diagnostico_anterior.log"
PASTA_RESUMOS = "diagnosticos"
VERSAO_RESUMO = 1
TABELAS_DIARIAS = {"v1-precos", "v1-noticias", "v1-indices"}
NOMES_LINHAS = {"v1-noticias": "notícias", "v1-precos": "preços", "v1-cadastro": "empresas no cadastro",
                "v1-mudancas_ticker": "mudanças de ticker", "v1-balancos": "balanços",
                "v1-acoes_emitidas": "registros de quantidade de ações", "v1-proventos": "proventos",
                "v1-indices": "pontos de índices"}
NOMES_CURTOS = {"v1-noticias": "notícias", "v1-precos": "preços", "v1-cadastro": "cadastro",
                "v1-mudancas_ticker": "mudanças de ticker", "v1-balancos": "balanços",
                "v1-acoes_emitidas": "quantidade de ações", "v1-proventos": "proventos", "v1-indices": "índices"}
FAROL_NOME = {"ok": "verde", "warn": "amarelo", "bad": "vermelho", "idle": "cinza"}
MAX_FRASE = 4

RE_MOMENTO = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})")
RE_NOME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}\.json$")
MOTIVO_SEM_ANTERIOR = ("Ainda sem diagnóstico anterior guardado: "
                       "as novidades aparecem a partir do próximo diagnóstico.")
MOTIVO_SEM_LISTA = ("O resumo anterior é de antes de o painel guardar a lista de divergências: "
                    "resolvidas e novas aparecem a partir do próximo diagnóstico.")


# ---------------------------------------------------------------- auxiliares

def _ler_linhas(caminho: Path) -> list[str] | None:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def _momento_br(gerado: str | None) -> str | None:
    """'AAAA-MM-DD HH:MM (…)' vira 'DD/MM/AAAA HH:MM'; outro texto vira None."""
    m = RE_MOMENTO.match(gerado or "")
    if not m:
        return None
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)} {m.group(4)}"


def _nome_resumo(gerado: str | None) -> str | None:
    """'AAAA-MM-DD HH:MM (…)' vira 'AAAA-MM-DD_HHMM.json'; outro texto vira None."""
    m = RE_MOMENTO.match(gerado or "")
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}_{m.group(4).replace(':', '')}.json"


def _inteiro(texto: str | None) -> int | None:
    try:
        return int(texto)
    except (TypeError, ValueError):
        return None


def _valor(texto: str | None) -> bool:
    return texto not in (None, "", "NULL")


def _achado(texto: str, tipo: str) -> dict:
    return {"texto": texto, "tipo": tipo}


def _lista(nomes: list[str], singular: str, plural: str) -> str:
    if not nomes:
        return ""
    return f" ({singular if len(nomes) == 1 else plural}: {', '.join(nomes)})"


def _ler_resumo(caminho: Path) -> dict | None:
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dado if isinstance(dado, dict) else None


# ---------------------------------------------------------------- resumo

def resumir(docs_md: Path) -> dict | None:
    """Resumo JSON do diagnóstico (só os dados que as comparações usam); None se não puder ser lido."""
    diag = ler_diagnostico(docs_md)
    if not diag.get("disponivel"):
        return None
    linhas = _ler_linhas(docs_md)
    if linhas is None:
        return None
    periodo: dict[str, dict] = {}
    for r in tabela_md(linhas, "Período e entidades") or []:
        if r.get("tabela"):
            periodo[r["tabela"]] = {"linhas": _inteiro(r.get("linhas")), "inicio": r.get("inicio")}
    qtd = _qtd_acoes(diag, linhas)
    ret = _suspeitos(diag, linhas)
    lac = _lacunas(linhas)
    cob = _cobertura_nota(diag)
    return {
        "versao": VERSAO_RESUMO,
        "gerado_em": diag.get("gerado_em"),
        "periodo": periodo,
        "divergencias": len(diag["divergencias"]),
        "divergencias_lista": [[d["tema"], d["tabela"], d["detalhe"]] for d in diag["divergencias"]],
        "quantidade_acoes": {"n": qtd[0], "tickers": qtd[1]} if qtd is not None else None,
        "retornos": {"n": ret[0], "pares": [list(p) for p in ret[1]]} if ret is not None else None,
        "lacunas": {s: list(v) for s, v in lac.items()} if lac is not None else None,
        "cobertura": list(cob) if cob is not None else None,
        "farois": {c["id"]: {"titulo": c["titulo"], "farol": c["farol"]}
                   for c in cartoes_saude(docs_md).get("cartoes") or []},
    }


# ---------------------------------------------------------------- guarda dos resumos

def _nomes_resumos(pasta: Path) -> list[str]:
    """Nomes AAAA-MM-DD_HHMM.json guardados, do mais antigo para o mais novo."""
    try:
        return sorted(p.name for p in pasta.iterdir() if p.is_file() and RE_NOME.match(p.name))
    except OSError:
        return []


def _gravar_resumo(pasta: Path, resumo: dict) -> None:
    """Grava o resumo se o arquivo do seu momento ainda não existir. Escrita atômica (tmp + os.replace)."""
    nome = _nome_resumo(resumo.get("gerado_em"))
    if nome is None or (pasta / nome).exists():
        return
    pasta.mkdir(parents=True, exist_ok=True)
    tmp = pasta / f".{nome}.{os.getpid()}-{threading.get_ident()}.tmp"
    try:
        tmp.write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, pasta / nome)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def atualizar_resumos(docs_md: Path, pasta_painel: Path, manter: int | None) -> None:
    """Guarda o resumo do diagnóstico atual em pasta_painel/diagnosticos. Só grava lá.

    Migração: se a pasta ainda não tem nenhum .json, guarda também o resumo de ANTERIOR e de VISTO (logs antigos).
    Se `manter` é inteiro > 0, apaga os resumos mais antigos além desse número. Erro de disco: retorna em silêncio.
    """
    atual = resumir(docs_md)
    if atual is None:
        return
    pasta = pasta_painel / PASTA_RESUMOS
    try:
        if not any(pasta.glob("*.json")):
            for caminho in (pasta_painel / ANTERIOR, pasta_painel / VISTO):
                antigo = resumir(caminho) if caminho.is_file() else None
                if antigo is not None:
                    _gravar_resumo(pasta, antigo)
        _gravar_resumo(pasta, atual)
        if isinstance(manter, int) and not isinstance(manter, bool) and manter > 0:
            for nome in _nomes_resumos(pasta)[:-manter]:
                (pasta / nome).unlink(missing_ok=True)
    except OSError:
        return


# ---------------------------------------------------------------- comparação

def _periodo_entidades(ra: dict, rb: dict) -> list[dict]:
    antes = rb["periodo"]
    achados: list[dict] = []
    for tabela, a in ra["periodo"].items():
        if tabela not in antes:
            continue
        b = antes[tabela]
        n_atual, n_antes = a["linhas"], b["linhas"]
        if n_atual is not None and n_antes is not None and n_atual != n_antes:
            d = n_atual - n_antes
            tipo = "crescimento" if tabela in TABELAS_DIARIAS else "mudanca"
            sinal = "+" if d > 0 else "-"
            achados.append(_achado(f"{sinal}{_milhar(abs(d))} {NOMES_LINHAS.get(tabela, tabela)}", tipo))
        ini, ini_antes = a["inicio"], b["inicio"]
        if _valor(ini) and _valor(ini_antes) and ini != ini_antes:
            curto = NOMES_CURTOS.get(tabela, tabela)
            if ini < ini_antes:
                texto = f"{curto} desde {_data_br(ini)} (antes {_data_br(ini_antes)})"
            else:
                texto = f"{curto} só a partir de {_data_br(ini)} (antes {_data_br(ini_antes)})"
            achados.append(_achado(texto, "mudanca"))
    return achados


def _divergencias(ra: dict, rb: dict) -> list[dict]:
    d = ra["divergencias"] - rb["divergencias"]
    if d < 0:
        return [_achado(_plural(-d, "divergência", "divergências") + " a menos", "mudanca")]
    if d > 0:
        return [_achado(_plural(d, "divergência nova", "divergências novas"), "mudanca")]
    return []


def _qtd_acoes(diag: dict, linhas: list[str]) -> tuple[int, list[str]] | None:
    """(número de empresas da nota, tickers da tabela); None se a seção ou a nota não existem."""
    if _secao(linhas, "Quantidade de ações suspeita") is None:
        return None
    n = None
    for nota in _notas(diag, "Quantidade de ações suspeita"):
        m = RE_QTD_ACOES.search(nota)
        if m:
            n = int(m.group(1))
            break
        if RE_QTD_ACOES_ZERO.match(nota):
            n = 0
            break
    if n is None:
        return None
    tab = tabela_md(_secao(linhas, "Quantidade de ações suspeita")[2], "Empresas com quantidade de ações suspeita") or []
    tickers = [t for r in tab for t in (r.get("tickers") or "").split(", ") if t]
    return n, tickers


def _quantidade(ra: dict, rb: dict) -> list[dict]:
    atual, anterior = ra["quantidade_acoes"], rb["quantidade_acoes"]
    if atual is None or anterior is None or atual["n"] == anterior["n"]:
        return []
    n_a, tickers_a = atual["n"], atual["tickers"]
    n_b, tickers_b = anterior["n"], anterior["tickers"]
    if n_a < n_b:
        saiu = [t for t in tickers_b if t not in tickers_a]
        texto = f"quantidade de ações corrigida em {_plural(n_b - n_a, 'empresa', 'empresas')}"
        return [_achado(texto + _lista(saiu, "saiu da lista", "saíram da lista"), "mudanca")]
    entrou = [t for t in tickers_a if t not in tickers_b]
    texto = f"quantidade de ações suspeita em mais {_plural(n_a - n_b, 'empresa', 'empresas')}"
    return [_achado(texto + _lista(entrou, "entrou", "entraram"), "mudanca")]


def _suspeitos(diag: dict, linhas: list[str]) -> tuple[int, list[tuple[str, str]]] | None:
    """(número de retornos da nota, pares (ticker, data) da tabela); None se a seção ou a nota não existem."""
    achada = _secao(linhas, "Retornos diários suspeitos")
    if achada is None:
        return None
    n = None
    for nota in _notas(diag, "Retornos diários suspeitos"):
        m = RE_RETORNOS.match(nota)
        if m:
            n = int(m.group(1))
            break
        if RE_RETORNOS_ZERO.match(nota):
            n = 0
            break
    if n is None:
        return None
    tab = tabela_md(achada[2], "Retornos diários suspeitos") or []
    pares = [(r["ticker"], _data_br(r.get("data", ""))) for r in tab if r.get("ticker")]
    return n, pares


def _retornos(ra: dict, rb: dict) -> list[dict]:
    atual, anterior = ra["retornos"], rb["retornos"]
    if atual is None or anterior is None or atual["n"] == anterior["n"]:
        return []
    n_a, pares_a = atual["n"], [tuple(p) for p in atual["pares"]]
    n_b, pares_b = anterior["n"], [tuple(p) for p in anterior["pares"]]
    if n_a < n_b:
        saiu = [f"{t} em {d}" for t, d in pares_b if (t, d) not in pares_a]
        texto = _plural(n_b - n_a, "preço suspeito", "preços suspeitos") + " a menos"
        return [_achado(texto + _lista(saiu, "saiu", "saíram"), "mudanca")]
    entrou = [f"{t} em {d}" for t, d in pares_a if (t, d) not in pares_b]
    texto = _plural(n_a - n_b, "preço suspeito novo", "preços suspeitos novos")
    return [_achado(texto + _lista(entrou, "entrou", "entraram"), "mudanca")]


def _lacunas(linhas: list[str]) -> dict[str, tuple[str, str, str, str]] | None:
    """Série -> (inicio, fim, tamanho, unidade) das lacunas de v1-indices; None se a seção não existe."""
    achada = _secao(linhas, "Lacunas nas séries")
    if achada is None:
        return None
    lacunas: dict[str, tuple[str, str, str, str]] = {}
    for r in tabela_md(achada[2], "Lacunas em v1-indices") or []:
        if r.get("serie"):
            lacunas[r["serie"]] = (r.get("inicio", ""), r.get("fim", ""), r.get("tamanho", ""), r.get("unidade", ""))
    return lacunas


def _agrupar(series: list[str], chave_de) -> dict[tuple, list[str]]:
    grupos: dict[tuple, list[str]] = {}
    for s in series:
        grupos.setdefault(chave_de(s), []).append(s)
    return grupos


def _lacunas_indices(ra: dict, rb: dict) -> list[dict]:
    atual, anterior = ra["lacunas"], rb["lacunas"]
    if atual is None or anterior is None:
        return []
    atual = {s: tuple(v) for s, v in atual.items()}
    anterior = {s: tuple(v) for s, v in anterior.items()}
    achados: list[dict] = []
    mudou = [s for s in anterior if s in atual and anterior[s] != atual[s]]
    for (antes, depois), series in _agrupar(mudou, lambda s: (anterior[s], atual[s])).items():
        ini, fim, tam, uni = depois
        texto = (f"lacuna de {', '.join(series)}: {antes[2]} → {tam} {uni} "
                 f"(agora de {_data_br(ini)} a {_data_br(fim)})")
        achados.append(_achado(texto, "mudanca"))
    fechou = [s for s in anterior if s not in atual]
    if fechou:
        achados.append(_achado(f"lacuna de {', '.join(fechou)} fechada", "mudanca"))
    novas = [s for s in atual if s not in anterior]
    for (ini, fim, tam, uni), series in _agrupar(novas, lambda s: atual[s]).items():
        texto = f"lacuna nova em {', '.join(series)}: {tam} {uni} ({_data_br(ini)} a {_data_br(fim)})"
        achados.append(_achado(texto, "mudanca"))
    return achados


def _cobertura_nota(diag: dict) -> tuple[int, int, str, str] | None:
    for nota in _notas(diag, "Histórico novo"):
        m = RE_COBERTURA.match(nota)
        if m:
            return int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
    return None


def _cobertura(ra: dict, rb: dict) -> list[dict]:
    atual, anterior = ra["cobertura"], rb["cobertura"]
    if atual is None or anterior is None:
        return []
    d = atual[0] - anterior[0]
    if d == 0:
        return []
    sinal = "+" if d > 0 else "-"
    texto = (f"{sinal}{_milhar(abs(d))} linhas no dataset do experimento "
             f"({_milhar(atual[1])} pregões, até {_data_br(atual[3])})")
    return [_achado(texto, "crescimento")]


def _cartoes(ra: dict, rb: dict) -> list[dict]:
    ca, cb = ra["farois"], rb["farois"]
    achados: list[dict] = []
    for id_, c in ca.items():
        antes = cb.get(id_)
        if antes and antes["farol"] != c["farol"]:
            texto = (f"{c['titulo']}: {FAROL_NOME.get(antes['farol'], antes['farol'])} → "
                     f"{FAROL_NOME.get(c['farol'], c['farol'])}")
            achados.append(_achado(texto, "mudanca"))
    return achados


def _frase(itens: list[dict], anterior_em: str | None) -> str:
    if not itens:
        return f"Nenhuma mudança desde o diagnóstico de {anterior_em}."
    mudancas = [i["texto"] for i in itens if i["tipo"] == "mudanca"]
    if mudancas:
        texto = "; ".join(mudancas[:MAX_FRASE])
        resto = len(itens) - MAX_FRASE
        return texto + (f" · e mais {_plural(resto, 'mudança', 'mudanças')}" if resto > 0 else "")
    return "; ".join(i["texto"] for i in itens[:MAX_FRASE])


def _indisponivel(motivo: str | None, atual_em: str | None, anterior_em: str | None) -> dict:
    return {"disponivel": False, "motivo": motivo, "atual_em": atual_em, "anterior_em": anterior_em,
            "frase": None, "itens": []}


def comparar_resumos(ra: dict, rb: dict) -> dict:
    """Mudanças e crescimentos do resumo `ra` (atual) em relação ao resumo `rb` (anterior). Sem I/O."""
    atual_em = _momento_br(ra.get("gerado_em"))
    anterior_em = _momento_br(rb.get("gerado_em"))
    achados = (_periodo_entidades(ra, rb)
               + _divergencias(ra, rb)
               + _quantidade(ra, rb)
               + _retornos(ra, rb)
               + _lacunas_indices(ra, rb)
               + _cobertura(ra, rb)
               + _cartoes(ra, rb))
    itens = [i for i in achados if i["tipo"] == "mudanca"] + [i for i in achados if i["tipo"] == "crescimento"]
    return {"disponivel": True, "motivo": None, "atual_em": atual_em, "anterior_em": anterior_em,
            "frase": _frase(itens, anterior_em), "itens": itens}


def comparar(atual: Path, anterior: Path) -> dict:
    """Mudanças e crescimentos de `atual` em relação a `anterior` (dois diagnósticos). Só leitura."""
    diag_a, diag_b = ler_diagnostico(atual), ler_diagnostico(anterior)
    atual_em = _momento_br(diag_a.get("gerado_em"))
    anterior_em = _momento_br(diag_b.get("gerado_em"))
    if not diag_a.get("disponivel"):
        return _indisponivel(diag_a.get("motivo"), atual_em, anterior_em)
    if not diag_b.get("disponivel"):
        return _indisponivel(diag_b.get("motivo"), atual_em, anterior_em)
    ra, rb = resumir(atual), resumir(anterior)
    if ra is None or rb is None:
        return _indisponivel("diagnóstico não pode ser lido", atual_em, anterior_em)
    return comparar_resumos(ra, rb)


def novidades(docs_md: Path, pasta_painel: Path, manter: int | None = None) -> dict:
    """Guarda o resumo do diagnóstico atual e compara com o resumo imediatamente anterior guardado."""
    atualizar_resumos(docs_md, pasta_painel, manter)
    atual = resumir(docs_md)
    if atual is None:
        diag = ler_diagnostico(docs_md)
        return _indisponivel(diag.get("motivo") or "diagnóstico não pode ser lido", None, None)
    atual_em = _momento_br(atual["gerado_em"])
    nome = _nome_resumo(atual["gerado_em"])
    pasta = pasta_painel / PASTA_RESUMOS
    anteriores = [n for n in _nomes_resumos(pasta) if nome is not None and n < nome]
    if not anteriores:
        return _indisponivel(MOTIVO_SEM_ANTERIOR, atual_em, None)
    ra = _ler_resumo(pasta / nome) or atual
    rb = _ler_resumo(pasta / anteriores[-1])
    if rb is None:
        return _indisponivel("diagnóstico anterior não pode ser lido", atual_em, None)
    return comparar_resumos(ra, rb)


# ---------------------------------------------------------------- divergências: identidade e histórico

def _chave(tema: str, tabela: str, detalhe: str) -> tuple[str, str, str]:
    """Identidade de uma divergência: detalhe com cada número trocado por '#', exceto anos (19xx/20xx)."""
    return tema, tabela, re.sub(r"\d+(?:[.,]\d+)*",
                                lambda m: m.group(0) if re.fullmatch(r"(19|20)\d{2}", m.group(0)) else "#",
                                detalhe)


def _identidade(item: dict) -> tuple[str, str, str]:
    return _chave(item["tema"], item["tabela"], item["detalhe"])


def _lista_resumo(resumo: dict) -> list | None:
    lista = resumo.get("divergencias_lista")
    return lista if isinstance(lista, list) else None


def _itens(lista: list) -> list[dict]:
    """Lista [[tema, tabela, detalhe], ...] do resumo como dicts; entradas malformadas ficam de fora."""
    itens = []
    for e in lista:
        if isinstance(e, list) and len(e) == 3:
            itens.append({"tema": e[0], "tabela": e[1], "detalhe": e[2]})
    return itens


def _diferenca(origem: list[dict], outra: list[dict]) -> list[dict]:
    """Itens de `origem` sem correspondente em `outra` (comparação por multiconjunto de identidades)."""
    restante = Counter(_identidade(i) for i in outra)
    sobra = []
    for item in origem:
        chave = _identidade(item)
        if restante[chave] > 0:
            restante[chave] -= 1
        else:
            sobra.append(item)
    return sobra


def _dia_br(gerado: str | None) -> str | None:
    m = RE_MOMENTO.match(gerado or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else None


def _desde(chave: tuple, cadeia: list[tuple[str | None, list | None]]) -> tuple[str | None, str]:
    """(desde, desde_texto) de uma divergência.

    `cadeia` vai do resumo mais novo ao mais antigo, como (gerado_em, lista ou None). A divergência começa
    no resumo mais antigo da sequência contínua em que aparece; parar sem lista ou sem a chave encerra a busca.
    """
    desde, achou = None, 0
    for gerado, lista in cadeia:
        if lista is None:
            return (desde, f"{_dia_br(desde)} ou antes") if achou else (None, "sem dados")
        if chave not in {_identidade(i) for i in _itens(lista)}:
            if achou == 0:
                return None, "nova"
            return desde, _dia_br(desde)
        desde, achou = gerado, achou + 1
    if achou == 0:
        return None, "sem dados"
    return desde, f"{_dia_br(desde)} ou antes"


def historico_divergencias(docs_md: Path, pasta_painel: Path) -> dict | None:
    """Divergências do diagnóstico atual em relação ao resumo anterior guardado. Só lê; não grava nada.

    Formato de `diagnostico.divergencias` do painel. None se o diagnóstico não pode ser resumido.
    """
    atual = resumir(docs_md)
    if atual is None:
        return None
    itens = _itens(atual["divergencias_lista"])
    nome = _nome_resumo(atual["gerado_em"])
    pasta = pasta_painel / PASTA_RESUMOS
    anteriores = [n for n in _nomes_resumos(pasta) if nome is not None and n < nome]
    lidos = [_ler_resumo(pasta / n) for n in reversed(anteriores)]
    cadeia = [(r.get("gerado_em"), _lista_resumo(r)) if r is not None else (None, None) for r in lidos]
    lista = []
    for item in itens:
        desde, texto = _desde(_identidade(item), cadeia)
        lista.append({**item, "desde": desde, "desde_texto": texto})
    base = {"atual": len(itens), "lista": lista}
    if not anteriores:
        return {**base, "anterior": None, "anterior_em": None, "resolvidas": None, "novas": None,
                "motivo_comparacao": MOTIVO_SEM_ANTERIOR}
    rb = lidos[0]
    if rb is None:
        return {**base, "anterior": None, "anterior_em": None, "resolvidas": None, "novas": None,
                "motivo_comparacao": "diagnóstico anterior não pode ser lido"}
    anterior_em = _momento_br(rb.get("gerado_em"))
    lista_anterior = _lista_resumo(rb)
    if lista_anterior is None:
        return {**base, "anterior": rb.get("divergencias"), "anterior_em": anterior_em,
                "resolvidas": None, "novas": None, "motivo_comparacao": MOTIVO_SEM_LISTA}
    antes = _itens(lista_anterior)
    return {**base, "anterior": rb.get("divergencias"), "anterior_em": anterior_em,
            "resolvidas": _diferenca(antes, itens), "novas": _diferenca(itens, antes), "motivo_comparacao": None}
