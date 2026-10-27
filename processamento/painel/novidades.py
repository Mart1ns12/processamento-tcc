"""Novidades do painel: compara o diagnóstico visto com o anterior guardado em logs/painel (arquivos .log).

Só `atualizar_copias` grava, e só dentro da pasta do painel. Nenhuma função acessa banco ou rede.
Arquivo ausente ou ilegível vira `disponivel` False ou lista vazia, nunca exceção.
"""

from __future__ import annotations

import os
import re
import shutil
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


# ---------------------------------------------------------------- auxiliares

def _ler_linhas(caminho: Path) -> list[str] | None:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def _gerado_em(caminho: Path) -> str | None:
    linhas = _ler_linhas(caminho)
    if linhas is None:
        return None
    return next((linha[len("- Gerado em: "):].strip() for linha in linhas if linha.startswith("- Gerado em: ")), None)


def _momento_br(gerado: str | None) -> str | None:
    """'AAAA-MM-DD HH:MM (…)' vira 'DD/MM/AAAA HH:MM'; outro texto vira None."""
    m = RE_MOMENTO.match(gerado or "")
    if not m:
        return None
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)} {m.group(4)}"


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


# ---------------------------------------------------------------- cópias

def atualizar_copias(docs_md: Path, pasta_painel: Path) -> None:
    """Mantém VISTO (o diagnóstico visto por último) e ANTERIOR (o que era VISTO antes de mudar). Só grava em pasta_painel."""
    gerado = _gerado_em(docs_md)
    if gerado is None:
        return
    visto = pasta_painel / VISTO
    try:
        if visto.is_file():
            if _gerado_em(visto) == gerado:
                return
            os.replace(visto, pasta_painel / ANTERIOR)
        pasta_painel.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(docs_md, visto)
    except OSError:
        return


# ---------------------------------------------------------------- comparação

def _periodo_entidades(la: list[str], lb: list[str]) -> list[dict]:
    antes = {r.get("tabela"): r for r in tabela_md(lb, "Período e entidades") or []}
    achados: list[dict] = []
    for r in tabela_md(la, "Período e entidades") or []:
        tabela = r.get("tabela")
        if not tabela or tabela not in antes:
            continue
        a = antes[tabela]
        n_atual, n_antes = _inteiro(r.get("linhas")), _inteiro(a.get("linhas"))
        if n_atual is not None and n_antes is not None and n_atual != n_antes:
            d = n_atual - n_antes
            tipo = "crescimento" if tabela in TABELAS_DIARIAS else "mudanca"
            sinal = "+" if d > 0 else "-"
            achados.append(_achado(f"{sinal}{_milhar(abs(d))} {NOMES_LINHAS.get(tabela, tabela)}", tipo))
        ini, ini_antes = r.get("inicio"), a.get("inicio")
        if _valor(ini) and _valor(ini_antes) and ini != ini_antes:
            curto = NOMES_CURTOS.get(tabela, tabela)
            if ini < ini_antes:
                texto = f"{curto} desde {_data_br(ini)} (antes {_data_br(ini_antes)})"
            else:
                texto = f"{curto} só a partir de {_data_br(ini)} (antes {_data_br(ini_antes)})"
            achados.append(_achado(texto, "mudanca"))
    return achados


def _divergencias(diag_a: dict, diag_b: dict) -> list[dict]:
    d = len(diag_a["divergencias"]) - len(diag_b["divergencias"])
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


def _quantidade(diag_a: dict, la: list[str], diag_b: dict, lb: list[str]) -> list[dict]:
    atual, anterior = _qtd_acoes(diag_a, la), _qtd_acoes(diag_b, lb)
    if atual is None or anterior is None or atual[0] == anterior[0]:
        return []
    n_a, tickers_a = atual
    n_b, tickers_b = anterior
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


def _retornos(diag_a: dict, la: list[str], diag_b: dict, lb: list[str]) -> list[dict]:
    atual, anterior = _suspeitos(diag_a, la), _suspeitos(diag_b, lb)
    if atual is None or anterior is None or atual[0] == anterior[0]:
        return []
    n_a, pares_a = atual
    n_b, pares_b = anterior
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


def _lacunas_indices(la: list[str], lb: list[str]) -> list[dict]:
    atual, anterior = _lacunas(la), _lacunas(lb)
    if atual is None or anterior is None:
        return []
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


def _cobertura(diag_a: dict, diag_b: dict) -> list[dict]:
    atual, anterior = _cobertura_nota(diag_a), _cobertura_nota(diag_b)
    if atual is None or anterior is None:
        return []
    d = atual[0] - anterior[0]
    if d == 0:
        return []
    sinal = "+" if d > 0 else "-"
    texto = (f"{sinal}{_milhar(abs(d))} linhas no dataset do experimento "
             f"({_milhar(atual[1])} pregões, até {_data_br(atual[3])})")
    return [_achado(texto, "crescimento")]


def _cartoes(atual: Path, anterior: Path) -> list[dict]:
    ca = {c["id"]: c for c in cartoes_saude(atual)["cartoes"]}
    cb = {c["id"]: c for c in cartoes_saude(anterior)["cartoes"]}
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


def comparar(atual: Path, anterior: Path) -> dict:
    """Mudanças e crescimentos de `atual` em relação a `anterior` (dois diagnósticos). Só leitura."""
    diag_a, diag_b = ler_diagnostico(atual), ler_diagnostico(anterior)
    atual_em = _momento_br(diag_a.get("gerado_em"))
    anterior_em = _momento_br(diag_b.get("gerado_em"))
    if not diag_a.get("disponivel"):
        return _indisponivel(diag_a.get("motivo"), atual_em, anterior_em)
    if not diag_b.get("disponivel"):
        return _indisponivel(diag_b.get("motivo"), atual_em, anterior_em)
    la, lb = _ler_linhas(atual), _ler_linhas(anterior)
    if la is None or lb is None:
        return _indisponivel("diagnóstico não pode ser lido", atual_em, anterior_em)

    achados = (_periodo_entidades(la, lb)
               + _divergencias(diag_a, diag_b)
               + _quantidade(diag_a, la, diag_b, lb)
               + _retornos(diag_a, la, diag_b, lb)
               + _lacunas_indices(la, lb)
               + _cobertura(diag_a, diag_b)
               + _cartoes(atual, anterior))
    itens = [i for i in achados if i["tipo"] == "mudanca"] + [i for i in achados if i["tipo"] == "crescimento"]
    return {"disponivel": True, "motivo": None, "atual_em": atual_em, "anterior_em": anterior_em,
            "frase": _frase(itens, anterior_em), "itens": itens}


def novidades(docs_md: Path, pasta_painel: Path) -> dict:
    """Atualiza as cópias e compara o diagnóstico atual com o anterior guardado (ANTERIOR)."""
    atualizar_copias(docs_md, pasta_painel)
    anterior = pasta_painel / ANTERIOR
    if not anterior.is_file():
        return {"disponivel": False,
                "motivo": "Ainda sem diagnóstico anterior guardado: as novidades aparecem a partir do próximo diagnóstico.",
                "atual_em": _momento_br(_gerado_em(docs_md)), "anterior_em": None, "frase": None, "itens": []}
    return comparar(docs_md, anterior)
