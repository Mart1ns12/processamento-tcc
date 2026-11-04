"""Aba Diagnóstico do painel: seções do docs/diagnostico_banco.md com resumo, ponto (at/ok/idle) e divergências.

Só lê o diagnóstico e o resumo anterior guardado (novidades.historico_divergencias não grava nada).
Seção, nota ou tabela ausentes viram ausência, nunca exceção.
"""

from __future__ import annotations

from pathlib import Path

from processamento.painel.novidades import _ler_linhas, _momento_br, historico_divergencias
from processamento.painel.relatorios import ler_diagnostico
from processamento.painel.saude import _secao, tabela_md

# Seção do diagnóstico (pelo início do título) → id do cartão de Saúde que ela detalha.
CARTAO_DA_SECAO = (
    ("Notícias (", "horario_noticias"),
    ("Quantidade de ações suspeita", "quantidade_acoes"),
    ("Retornos diários suspeitos", "retornos"),
    ("Lacunas nas séries", "lacunas"),
    ("Histórico novo", "cobertura"),
)
TITULO_MESES_BAIXOS = "Notícias por mês"
TABELA_MESES_BAIXOS = "Meses com poucas notícias"
LIMITE_RESUMO = 90


def _cartao_ligado(titulo: str, cartoes: list) -> dict | None:
    id_ = next((c_id for prefixo, c_id in CARTAO_DA_SECAO if titulo.startswith(prefixo)), None)
    if id_ is None:
        return None
    return next((c for c in cartoes if isinstance(c, dict) and c.get("id") == id_), None)


def _meses_baixos(titulo: str, linhas: list[str]) -> bool:
    """True se a seção 'Notícias por mês' tem ao menos um mês com poucas notícias."""
    if not titulo.startswith(TITULO_MESES_BAIXOS):
        return False
    achada = _secao(linhas, TITULO_MESES_BAIXOS)
    if achada is None:
        return False
    return len(tabela_md(achada[2], TABELA_MESES_BAIXOS) or []) >= 1


def _resumo(notas: list[str]) -> str:
    if not notas:
        return "sem notas"
    nota = notas[0]
    return nota if len(nota) <= LIMITE_RESUMO else nota[:LIMITE_RESUMO - 1] + "…"


def _ponto(secao: dict, linhas: list[str], cartoes: list) -> str:
    cartao = _cartao_ligado(secao["titulo"], cartoes)
    farol = cartao.get("farol") if cartao else None
    if farol in ("warn", "bad") or any(n.startswith("Atenção") for n in secao["notas"]) \
            or _meses_baixos(secao["titulo"], linhas):
        return "at"
    if farol == "idle":
        return "idle"
    return "ok"


def secoes_resumo(diag: dict, linhas: list[str], cartoes: list) -> list[dict]:
    """Seções do diagnóstico com resumo (1ª nota) e ponto (at, ok ou idle); `cartoes` são os de cartoes_saude."""
    return [{"numero": s["numero"], "titulo": s["titulo"], "resumo": _resumo(s["notas"]),
             "ponto": _ponto(s, linhas, cartoes or []), "notas": s["notas"]}
            for s in diag["secoes"]]


def diagnostico_aba(docs_md: Path, pasta_painel: Path, cartoes: list) -> dict:
    """Bloco `diagnostico` do /api/painel. Arquivo ausente ou ilegível: disponivel False, sem seções."""
    diag = ler_diagnostico(docs_md)
    if not diag.get("disponivel"):
        return {"disponivel": False, "motivo": diag.get("motivo"), "gerado_em": None, "gerado_em_texto": None,
                "n_secoes": None, "secoes": [], "divergencias": None}
    linhas = _ler_linhas(docs_md) or []
    return {"disponivel": True, "motivo": None, "gerado_em": diag["gerado_em"],
            "gerado_em_texto": _momento_br(diag["gerado_em"]), "n_secoes": len(diag["secoes"]),
            "secoes": secoes_resumo(diag, linhas, cartoes),
            "divergencias": historico_divergencias(docs_md, pasta_painel)}
