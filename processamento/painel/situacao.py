"""Dados extras do cartão "Situação de hoje": casos aceitos, retornos suspeitos, eventos tratados e top 5 do dia.

Só leitura. Nenhuma função levanta exceção: arquivo ausente ou quebrado vira vazio (ou disponivel False).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

from processamento.painel import saude
from processamento.painel.leitores import ler_json

TIPOS_ACEITOS = {"divergencia": ("tema", "termo"), "preco_suspeito": ("ticker", "data"), "cartao": ("cartao",)}
RE_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _data_iso(valor: object) -> bool:
    """Texto AAAA-MM-DD de uma data real."""
    if not isinstance(valor, str) or RE_DATA_ISO.fullmatch(valor) is None:
        return False
    try:
        date.fromisoformat(valor)
    except ValueError:
        return False
    return True


def _texto_preenchido(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _item_valido(item: object) -> bool:
    """Item de `aceitos` com tipo conhecido, campos do tipo preenchidos, motivo e data de aceite válidos."""
    if not isinstance(item, dict):
        return False
    tipo = item.get("tipo")
    if tipo not in TIPOS_ACEITOS:
        return False
    if not all(_texto_preenchido(item.get(campo)) for campo in TIPOS_ACEITOS[tipo]):
        return False
    if tipo == "preco_suspeito" and not _data_iso(item.get("data")):
        return False
    return _texto_preenchido(item.get("motivo")) and _data_iso(item.get("desde"))


def ler_aceitos(caminho: Path) -> dict:
    """Casos aceitos de `processamento/config/painel_aceitos.yaml`; itens inválidos são ignorados e contados."""
    vazio = {"disponivel": False, "motivo": None, "itens": [], "invalidos": 0}
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**vazio, "motivo": "painel_aceitos.yaml não encontrado"}
    except (OSError, ValueError):
        return {**vazio, "motivo": "painel_aceitos.yaml não pode ser lido"}
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError:
        return {**vazio, "motivo": "painel_aceitos.yaml com YAML inválido"}
    lista = dados.get("aceitos") if isinstance(dados, dict) else None
    if not isinstance(lista, list):
        return {**vazio, "motivo": "painel_aceitos.yaml sem a lista aceitos"}
    itens = [i for i in lista if _item_valido(i)]
    return {"disponivel": True, "motivo": None, "itens": itens, "invalidos": len(lista) - len(itens)}


def _itens(aceitos: object, tipo: str) -> list[dict]:
    if not isinstance(aceitos, dict) or not isinstance(aceitos.get("itens"), list):
        return []
    return [i for i in aceitos["itens"] if isinstance(i, dict) and i.get("tipo") == tipo]


def aceito_divergencia(aceitos: object, div: object) -> dict | None:
    """Item aceito que casa com a divergência (mesmo tema e termo no detalhe); None se não houver."""
    if not isinstance(div, dict):
        return None
    detalhe = str(div.get("detalhe") or "")
    for item in _itens(aceitos, "divergencia"):
        if item.get("tema") == div.get("tema") and item.get("termo") in detalhe:
            return item
    return None


def _iso(valor: object) -> object:
    return valor.isoformat() if isinstance(valor, date) else valor


def aceito_preco(aceitos: object, ticker: object, data: object) -> dict | None:
    """Item aceito para o retorno suspeito de (ticker, data); None se não houver."""
    for item in _itens(aceitos, "preco_suspeito"):
        if item.get("ticker") == ticker and item.get("data") == _iso(data):
            return item
    return None


def aceito_cartao(aceitos: object, id_: object) -> dict | None:
    """Item aceito para o cartão de saúde `id_`; None se não houver."""
    for item in _itens(aceitos, "cartao"):
        if item.get("cartao") == id_:
            return item
    return None


def retornos_suspeitos(caminho_md: Path) -> list[dict] | None:
    """Linhas (ticker, data) da tabela "Retornos diários suspeitos" do diagnóstico.

    [] se o arquivo não existir; None se o arquivo não tiver a tabela (aí o cartão segue a regra antiga).
    """
    try:
        linhas = Path(caminho_md).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    tabela = saude.tabela_md(linhas, "Retornos diários suspeitos")
    if tabela is None:
        return None
    return [{"ticker": r["ticker"], "data": r["data"]} for r in tabela if r.get("ticker") and r.get("data")]


def eventos_tratados(raiz: Path) -> set[tuple[str, str]]:
    """(ticker, data) de `fase1.eventos_retorno_suspeito` do parametros.yaml. Só leitura."""
    caminho = Path(raiz) / "processamento" / "config" / "parametros.yaml"
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return set()
    fase1 = dados.get("fase1") if isinstance(dados, dict) else None
    eventos = fase1.get("eventos_retorno_suspeito") if isinstance(fase1, dict) else None
    saida: set[tuple[str, str]] = set()
    for evento in eventos if isinstance(eventos, list) else []:
        if not isinstance(evento, dict) or not isinstance(evento.get("ticker"), str):
            continue
        for d in evento.get("datas") if isinstance(evento.get("datas"), list) else []:
            if isinstance(d, date):
                d = d.isoformat()
            if isinstance(d, str):
                saida.add((evento["ticker"], d))
    return saida


def ler_top5(raiz: Path, pasta_saida: str, d: str | None) -> dict:
    """Top 5 do dia `d` (saida/<d>/experimento_top.json): se foi gerado, se vale para o histórico e os avisos."""
    vazio = {"disponivel": False, "motivo": None, "valido_para_historico": None, "avisos": [], "n_ranking": 0,
             "gerado_em": None}
    if not isinstance(d, str) or not d:
        return {**vazio, "motivo": "sem rotina diária para o top 5"}
    dados, erro = ler_json(Path(raiz) / pasta_saida / d / "experimento_top.json")
    if erro is not None:
        motivo = "experimento_top.json não encontrado" if erro == "não encontrado" else f"experimento_top.json ({erro})"
        return {**vazio, "motivo": motivo}
    registros = dados.get("registros") if isinstance(dados, dict) else dados
    if not isinstance(registros, list) or not registros or not isinstance(registros[0], dict):
        return {**vazio, "motivo": "sem registros"}
    reg = registros[0]
    valido = reg.get("valido_para_historico")
    avisos = reg.get("avisos") if isinstance(reg.get("avisos"), list) else []
    ranking = reg.get("ranking") if isinstance(reg.get("ranking"), list) else []
    gerado = reg.get("gerado_em")
    return {"disponivel": True, "motivo": None,
            "valido_para_historico": valido if isinstance(valido, bool) else None,
            "avisos": [a for a in avisos if isinstance(a, str)], "n_ranking": len(ranking),
            "gerado_em": gerado if isinstance(gerado, str) else None}
