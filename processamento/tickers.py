"""Códigos de negociação: raiz, classe, tipo, mudanças de ticker e ligação com a empresa.

Funções puras, sem banco nem rede. Regras da seção 6 da especificação ("Ação → empresa"),
e a classe só existe se estiver no `other_codes` da empresa em `v1-raw_b3_cadastro` (seção 3.4).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

import pandas as pd

_RE_CLASSE = re.compile(r"[0-9]+")
_TIPO_POR_CLASSE = {
    3: "ON",
    4: "PN",
    5: "PN",
    6: "PN",
    11: "UNIT",
    32: "BDR",
    33: "BDR",
    34: "BDR",
    35: "BDR",
}


def raiz(t: str) -> str:
    """Quatro primeiras letras do código (ex.: 'ITUB3' -> 'ITUB')."""
    return t[:4]


def classe(t: str) -> int | None:
    """Número da classe, a partir do sufixo do código (ex.: 'KLBN11' -> 11). None se não houver."""
    sufixo = t[4:]
    if _RE_CLASSE.fullmatch(sufixo):
        return int(sufixo)
    return None


def tipo_por_classe(c: int | None) -> str | None:
    """Tipo de ação da classe: 3 = ON; 4, 5 e 6 = PN; 11 = UNIT; 32 a 35 = BDR. Outras: None."""
    return _TIPO_POR_CLASSE.get(c)


def aplicar_mudancas(t: str, mudancas: dict[str, str]) -> str:
    """Segue a cadeia de mudanças de ticker (antigo -> novo) até o código atual.

    Se a cadeia voltar a um código já visitado (ciclo), para e devolve o último código.
    """
    atual = t
    visitados = {t}
    while atual in mudancas:
        proximo = mudancas[atual]
        if proximo in visitados:
            break
        visitados.add(proximo)
        atual = proximo
    return atual


CLASSES_DE_ACAO = {3, 4, 5, 6, 11}


def troca_acao_para_bdr(antigo: str, novo: str, tipo_de: dict[str, str]) -> bool:
    """True se a mudança troca uma ação (classe 3, 4, 5, 6 ou 11) por uma BDR: os históricos não se unem.

    BDR = `tipo_acao` "BDR" no cadastro (`tipo_de`); fora do cadastro, classe 32 a 35 (ex.: JBSS3 -> JBSS32).
    """
    if classe(antigo) not in CLASSES_DE_ACAO:
        return False
    if novo in tipo_de:
        return tipo_de[novo] == "BDR"
    return tipo_por_classe(classe(novo)) == "BDR"


def parse_other_codes(v: object) -> list[str]:
    """Lê o campo `other_codes` (JSON) e devolve a lista de códigos, sem nulos nem vazios.

    Aceita None, bytes (UTF-8), texto JSON ou lista. Não-lista ou JSON inválido levanta ValueError.
    """
    if v is None:
        return []
    if isinstance(v, bytes):
        try:
            v = v.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"other_codes inválido: {v!r}") from e
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"other_codes inválido: {v!r}") from e
    if not isinstance(v, list):
        raise ValueError(f"other_codes inválido: {v!r}")
    codigos = []
    for item in v:
        if not isinstance(item, str):
            continue
        limpo = item.strip()
        if limpo:
            codigos.append(limpo)
    return codigos


def codigos_por_cnpj(linhas: Iterable[tuple[str | None, object]]) -> dict[str, set[str]]:
    """Une os códigos atuais de cada empresa (CNPJ) a partir das linhas (cnpj, other_codes).

    Linhas sem CNPJ são ignoradas. Empresa sem códigos aparece com conjunto vazio.
    """
    resultado: dict[str, set[str]] = {}
    for cnpj, other_codes in linhas:
        if not cnpj:
            continue
        codigos = resultado.setdefault(cnpj, set())
        codigos.update(parse_other_codes(other_codes))
    return resultado


def ligar_a_cnpj(
    t: str, cadastro: dict[str, str | None], mudancas: dict[str, str]
) -> tuple[str | None, str]:
    """Descobre a empresa (CNPJ) de um código e como ela foi encontrada.

    Ordem: o código atual está no cadastro com CNPJ ("cadastro"); senão, as empresas com a
    mesma raiz: uma só ("raiz"), nenhuma ("sem_empresa") ou mais de uma ("ambiguo").
    """
    t2 = aplicar_mudancas(t, mudancas)
    if cadastro.get(t2):
        return cadastro[t2], "cadastro"
    raiz_t = raiz(t2)
    cnpjs = {c for tk, c in cadastro.items() if c and raiz(tk) == raiz_t}
    if len(cnpjs) == 1:
        return cnpjs.pop(), "raiz"
    if not cnpjs:
        return None, "sem_empresa"
    return None, "ambiguo"


def mapas_por_empresa(
    tickers, setor_de: dict, cnpj_de: dict, mudancas: dict
) -> tuple[dict, dict, dict[str, tuple[str, str | None]]]:
    """Estende `setor_de`/`cnpj_de` (do cadastro) aos tickers fora do cadastro ligados a uma empresa dele.

    Herda o CNPJ (ligar_a_cnpj) e o setor da empresa (setor único entre as ações do cadastro com esse CNPJ;
    mais de um setor distinto = sem setor). Devolve (setor_de, cnpj_de, herdados), herdados = {ticker: (cnpj, setor)}.
    Não altera os dicionários de entrada.
    """
    setor_de2 = dict(setor_de)
    cnpj_de2 = dict(cnpj_de)
    herdados: dict[str, tuple[str, str | None]] = {}
    for t in tickers:
        if t in cnpj_de:
            continue
        cnpj, _ = ligar_a_cnpj(t, cnpj_de, mudancas)
        if not cnpj:
            continue
        setores = {setor_de[x] for x, c in cnpj_de.items() if c == cnpj and setor_de.get(x)}
        setor = setores.pop() if len(setores) == 1 else None
        cnpj_de2[t] = cnpj
        if setor is not None:
            setor_de2[t] = setor
        herdados[t] = (cnpj, setor)
    return setor_de2, cnpj_de2, herdados


def classificar_classe(
    t: str,
    cadastro: dict[str, str | None],
    mudancas: dict[str, str],
    codigos: dict[str, set[str]],
) -> dict:
    """Diz se a classe ainda existe na B3: 'existe', 'extinta' ou o motivo de não ligar à empresa.

    Devolve `ticker_atual` (código após as mudanças), `cnpj` e `situacao`.
    """
    t2 = aplicar_mudancas(t, mudancas)
    cnpj, motivo = ligar_a_cnpj(t, cadastro, mudancas)
    if cnpj is None:
        situacao = motivo
    elif not codigos.get(cnpj):
        situacao = "sem_other_codes"
    elif t2 in codigos[cnpj]:
        situacao = "existe"
    else:
        situacao = "extinta"
    return {"ticker_atual": t2, "cnpj": cnpj, "situacao": situacao}


_COLUNAS_CLASSES = ["ticker", "ticker_atual", "cnpj", "tipo", "situacao", "ligacao"]


def tabela_classes(
    tickers: Iterable[str],
    cadastro: dict[str, str | None],
    tipos_cadastro: dict[str, str],
    mudancas: dict[str, str],
    codigos: dict[str, set[str]],
) -> pd.DataFrame:
    """Uma linha por código, ordenada por ticker: situação e ligação à empresa de cada um.

    `tipo` vem do cadastro (pelo código atual); sem ele, da classe. Ausência = None, nunca 0 ou "".
    """
    linhas = []
    for t in tickers:
        info = classificar_classe(t, cadastro, mudancas, codigos)
        t_atual = info["ticker_atual"]
        cnpj, ligacao = ligar_a_cnpj(t, cadastro, mudancas)
        tipo = tipos_cadastro.get(t_atual) or tipo_por_classe(classe(t_atual))
        linhas.append((t, t_atual, cnpj, tipo, info["situacao"], ligacao))
    df = pd.DataFrame(linhas, columns=_COLUNAS_CLASSES, dtype=object)
    return df.sort_values("ticker").reset_index(drop=True)
