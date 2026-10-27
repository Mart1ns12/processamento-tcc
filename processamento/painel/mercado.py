"""Dia atípico e coerência do mercado no painel, a partir de `mercado_dia.json` e `resumo_acao.json`.

Funções puras sobre a pasta `saida/<D>/` do último processamento. Nenhum limite é escrito aqui: os limites
chegam pelo dicionário, vindos do bloco `painel:` do `parametros.yaml`. Ausência de dado vira None ou
"sem dados", nunca 0. Nenhum SQL, nenhum banco, nenhuma rede.
"""

from __future__ import annotations

import math
import re
import statistics
from pathlib import Path

from processamento.painel.leitores import ler_json

RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def pct2(x: float) -> str:
    """Percentual com sinal e duas casas: -0.0145 vira "-1,45%"."""
    return f"{x*100:+.2f}".replace(".", ",") + "%"


def pct0(x: float) -> str:
    """Percentual de parâmetro: 0.30 vira "30%"."""
    return f"{x*100:g}".replace(".", ",") + "%"


def _data_br(iso: object) -> str | None:
    """"2026-10-26" vira "26/10/2026"; qualquer outra coisa vira None."""
    if not isinstance(iso, str):
        return None
    m = RE_DATA_ISO.match(iso)
    if not m:
        return None
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"


def _numero(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _sub(dados: object, *chaves: str) -> object | None:
    """Desce por chaves aninhadas; qualquer degrau que não seja dict vira None."""
    atual = dados
    for chave in chaves:
        if not isinstance(atual, dict):
            return None
        atual = atual.get(chave)
    return atual


def _valor_ok(bloco: object) -> float | None:
    """`valor` de um bloco {"valor", "status"}: só conta se o status for "ok" e o valor for número."""
    if not isinstance(bloco, dict) or bloco.get("status") != "ok":
        return None
    v = bloco.get("valor")
    return float(v) if _numero(v) else None


def ler_dia(raiz: Path, pasta_saida: str, d: str | None) -> dict:
    """{"disponivel","motivo","d","data_pregao","ibov","usd","ivvb11","smll","retornos":[[ticker, valor]],"fonte"}.

    mercado_dia registros[0]: IBOV.variacao_dia, USDBRL.variacao_dia, indices.IVVB11.d1, indices.SMLL.d1.
    resumo_acao: (ticker, rentabilidade.d1.valor) só com status "ok".
    disponivel só é True quando o mercado_dia tem um registro. Pasta ou arquivo ausente/quebrado vira motivo.
    """
    vazio = {"disponivel": False, "motivo": None, "d": d, "data_pregao": None, "ibov": None, "usd": None,
             "ivvb11": None, "smll": None, "retornos": [], "fonte": None}
    if not isinstance(d, str) or not d:
        return {**vazio, "motivo": "sem dia de referência"}
    pasta = Path(raiz) / pasta_saida / d
    fonte = f"{pasta_saida}/{d}/mercado_dia.json e resumo_acao.json"
    if not pasta.is_dir():
        return {**vazio, "motivo": "pasta de saída não encontrada", "fonte": fonte}

    mercado, erro = ler_json(pasta / "mercado_dia.json")
    registros = mercado.get("registros") if isinstance(mercado, dict) else None
    reg = registros[0] if isinstance(registros, list) and registros and isinstance(registros[0], dict) else None
    if reg is None:
        motivo = f"mercado_dia.json: {erro}" if erro else "mercado_dia.json sem registros"
        return {**vazio, "motivo": motivo, "fonte": fonte}

    resumo, _ = ler_json(pasta / "resumo_acao.json")
    lista = resumo.get("registros") if isinstance(resumo, dict) else None
    retornos = []
    for x in lista if isinstance(lista, list) else []:
        if isinstance(x, dict) and isinstance(x.get("ticker"), str):
            v = _valor_ok(_sub(x, "rentabilidade", "d1"))
            if v is not None:
                retornos.append([x["ticker"], v])

    data = reg.get("data_referencia")
    return {
        "disponivel": True,
        "motivo": None,
        "d": d,
        "data_pregao": data if _data_br(data) else None,
        "ibov": _valor_ok(_sub(reg, "IBOV", "variacao_dia")),
        "usd": _valor_ok(_sub(reg, "USDBRL", "variacao_dia")),
        "ivvb11": _valor_ok(_sub(reg, "indices", "IVVB11", "d1")),
        "smll": _valor_ok(_sub(reg, "indices", "SMLL", "d1")),
        "retornos": retornos,
        "fonte": fonte,
    }


def dia_atipico(dados: dict, limites: dict) -> dict:
    """Cartão "Dia atípico": ativo quando min_acoes ações passam de retorno_abs em módulo no mesmo pregão.

    limites: retorno_abs, min_acoes, ibov_amplo, max (itens mostrados na lista; a página corta o resto).
    """
    chaves = ("retorno_abs", "min_acoes", "ibov_amplo", "max")
    if not dados.get("disponivel") or any(limites.get(c) is None for c in chaves):
        motivo = dados.get("motivo") if not dados.get("disponivel") else "limite do dia atípico ausente"
        return {"disponivel": False, "ativo": False, "motivo": motivo, "pontos": []}

    retorno_abs = limites["retorno_abs"]
    min_acoes = limites["min_acoes"]
    ibov_amplo = limites["ibov_amplo"]
    ibov = dados.get("ibov")
    smll = dados.get("smll")
    data_txt = _data_br(dados.get("data_pregao")) or "data não informada"

    grandes = sorted([(t, v) for t, v in dados.get("retornos", []) if abs(v) > retorno_abs],
                     key=lambda x: (-abs(x[1]), x[0]))
    n = len(grandes)
    ativo = n >= min_acoes
    amplo = None if ibov is None else abs(ibov) > ibov_amplo
    if amplo is None:
        frase = "Sem a variação do Ibovespa: conferir os dados da coleta"
    elif amplo:
        frase = "Movimento amplo do mercado (provável evento real)"
    else:
        frase = "Movimento isolado: conferir os dados da coleta"

    pontos = []
    if ativo:
        if amplo:
            texto_ponto = (f"Dia atípico no pregão de {data_txt} ({n} ações): "
                           "aviso de evento de mercado, não erro dos dados")
        else:
            texto_ponto = f"Dia atípico no pregão de {data_txt} ({n} ações): conferir os dados da coleta"
        pontos.append({"nivel": "warn", "texto": texto_ponto,
                       "chave": "dia_atipico_amplo" if amplo else "dia_atipico_isolado"})

    return {
        "disponivel": True,
        "ativo": ativo,
        "motivo": None,
        "data_pregao": dados.get("data_pregao"),
        "n": n,
        "texto": f"{n} ações com retorno do dia acima de {pct0(retorno_abs)} em módulo no pregão de {data_txt}.",
        "ibov_texto": f"Ibovespa {pct2(ibov)}" if ibov is not None else "Ibovespa sem dados",
        "smll_texto": f"SMLL {pct2(smll)}" if smll is not None else "SMLL sem dados",
        "amplo": amplo,
        "frase": frase,
        "acoes": [{"ticker": t, "texto": pct2(v)} for t, v in grandes],
        "max": limites["max"],
        "fonte": dados.get("fonte"),
        "pontos": pontos,
    }


def cartao_coerencia(dados: dict, limites: dict) -> dict:
    """Cartão "Coerência do mercado": dólar × IVVB11 e Ibovespa × mediana das ações.

    limites: ivvb11_min, dif_min. Devolve {"cartao": {...}, "afetadas": {...} | None}.
    """
    ivvb11_min = limites.get("ivvb11_min")
    dif_min = limites.get("dif_min")
    usd = dados.get("usd")
    ivvb11 = dados.get("ivvb11")
    ibov = dados.get("ibov")
    valores = [v for _, v in dados.get("retornos", [])]

    textos = []
    itens = []
    avaliados = 0
    suspeitos = 0

    if usd is not None and ivvb11 is not None and ivvb11_min is not None:
        avaliados += 1
        if usd * ivvb11 < 0 and abs(ivvb11) > ivvb11_min:
            suspeitos += 1
            textos.append(f"Dólar {pct2(usd)} × IVVB11 {pct2(ivvb11)}: sentidos opostos, "
                          f"com o IVVB11 acima de {pct0(ivvb11_min)} em módulo (suspeito).")
            itens += [{"rotulo": "Dólar (USDBRL)", "detalhe": pct2(usd)},
                      {"rotulo": "IVVB11", "detalhe": pct2(ivvb11)}]
        else:
            textos.append(f"Dólar {pct2(usd)} × IVVB11 {pct2(ivvb11)}: dentro do esperado.")
    else:
        textos.append("Dólar × IVVB11: sem dados.")

    if ibov is not None and valores and dif_min is not None:
        med = statistics.median(valores)
        avaliados += 1
        if ibov * med < 0 and abs(ibov - med) > dif_min:
            suspeitos += 1
            diferenca = f"{abs(ibov - med) * 100:.2f}".replace(".", ",")
            textos.append(f"Ibovespa {pct2(ibov)} × mediana das ações {pct2(med)}: sentidos opostos, "
                          f"diferença de {diferenca}% (suspeito).")
            itens += [{"rotulo": "Ibovespa", "detalhe": pct2(ibov)},
                      {"rotulo": "Mediana das ações", "detalhe": pct2(med)}]
        else:
            textos.append(f"Ibovespa {pct2(ibov)} × mediana das ações {pct2(med)}: dentro do esperado.")
    else:
        textos.append("Ibovespa × mediana das ações: sem dados.")

    if suspeitos:
        farol = "warn"
        numero = "1 sinal suspeito" if suspeitos == 1 else f"{suspeitos} sinais suspeitos"
    elif avaliados:
        farol = "ok"
        numero = "0 sinais suspeitos"
    else:
        farol = "idle"
        numero = "sem dados"

    data = _data_br(dados.get("data_pregao"))
    partes = [p for p in (dados.get("fonte"), f"pregão de {data}" if data else None) if p]
    cartao = {
        "id": "coerencia_mercado",
        "titulo": "Coerência do mercado",
        "farol": farol,
        "numero": numero,
        "texto": " ".join(textos),
        "fonte": " · ".join(partes) or None,
    }
    afetadas = {"titulo": "Séries afetadas", "itens": itens, "total": len(itens)} if suspeitos else None
    return {"cartao": cartao, "afetadas": afetadas}
