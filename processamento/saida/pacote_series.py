"""Pacote `series_diarias` da saída (plano da etapa 7: seções 2.4, 4.4 e 8; Fase 6b).

Funções puras: insumos e grades entram, dicionários saem. Nenhuma acessa banco ou rede.
Formato compacto (S20): cada série leva `datas` e as listas paralelas `valores`; `status` só em
trechos. Janela (S19): os últimos 253 pregões até t. As grades são calculadas no histórico inteiro
(a base 100 nasce no 1º dia da série) e só depois cortadas: a série não é rebaseada no início da
janela. Envio "quando muda": compara com o estado do último envio (seção 2.4).
"""

from __future__ import annotations

import bisect
import math
from datetime import date

import numpy as np
import pandas as pd

from processamento.fatos.fundamentos import LUCRO_NEGATIVO
from processamento.experimento.relatorio import pct
from processamento.fatos.precos import (
    INDISPONIVEL,
    OK,
    Grade,
    ParametrosPrecos,
    carregar_parametros_precos,
    grade_de_precos,
    indice_pregoes,
    mapas_cadastro,
    montar_grade,
    pares_do_painel,
    retornos_suspeitos,
    tickers_do_painel,
)
from processamento.fatos.series import (
    ANTES_DO_INICIO,
    PREFIXO_SEM,
    indice_base_100,
    indice_cdi,
    indice_ipca,
    indice_pontos,
    indice_setor_sem_empresa,
)
from processamento.saida import contrato
from processamento.saida.insumos import Insumos

JANELA_PREGOES = 253  # 252 variações: o gráfico de 1 ano bate com rentabilidade.a1
ETFS = ("IVVB11",)
INDICES_PONTOS = ("IDIV", "SMLL", "IFIX")
_MANTEM = (OK, LUCRO_NEGATIVO)  # status com valor numérico no contrato (P/L com prejuízo, decisão da etapa 4)


def inicio_janela(cal: list[date], t: date, n: int = JANELA_PREGOES) -> date:
    """1º dos últimos `n` pregões de `cal` até `t` (inclusive); com menos de `n`, `cal[0]`.

    Conta só os pregões até `t`: datas depois de t não entram (ponto de vista de t).
    """
    fim = bisect.bisect_right(cal, t)
    if fim == 0:
        raise ValueError(f"nenhum pregão até {t}: não há janela")
    return cal[max(0, fim - n)]


AVISO_SUSPEITOS = ("Retornos diários suspeitos (abaixo de {minimo} ou acima de {maximo}) entre {ini} e {t}, "
                   "fora das séries e das medianas do setor: {lista}.")
MAX_TICKERS_AVISO = 10


def aviso_retornos_suspeitos(ins: Insumos, params_precos: ParametrosPrecos) -> str | None:
    """Aviso do `execucao` (seção 6): retornos suspeitos das ações ON/PN/UNIT com data em [inicio_janela, t].

    None se não houver. Mais de `MAX_TICKERS_AVISO` tickers: os primeiros e "e mais k".
    """
    pares = pares_do_painel(ins.cadastro, ins.exclusoes)
    g = grade_de_precos(ins.precos, ins.cal, "fechamento_ajustado", pares)
    susp = retornos_suspeitos(g, params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max,
                              params_precos.base_defasagem_max_pregoes, params_precos.eventos_retorno_suspeito)
    ini = inicio_janela(ins.cal, ins.t)
    dentro = (susp.index >= pd.Timestamp(ini)) & (susp.index <= pd.Timestamp(ins.t))
    janela = susp[dentro]
    itens = []
    for tk in sorted(janela.columns):
        dias = [d.strftime("%Y-%m-%d") for d in janela.index[janela[tk].to_numpy()]]
        if dias:
            itens.append(f"{tk} ({', '.join(dias)})")
    if not itens:
        return None
    lista = ", ".join(itens[:MAX_TICKERS_AVISO])
    if len(itens) > MAX_TICKERS_AVISO:
        lista += f" e mais {len(itens) - MAX_TICKERS_AVISO}"
    aviso = AVISO_SUSPEITOS.format(minimo=pct(params_precos.retorno_suspeito_min, 0),
                                   maximo=pct(params_precos.retorno_suspeito_max, 0),
                                   ini=ini.isoformat(), t=ins.t.isoformat(), lista=lista)
    eventos = _eventos_no_aviso(janela, params_precos.motivos_eventos_suspeitos)
    return aviso if eventos is None else f"{aviso} {eventos}"


def _eventos_no_aviso(janela: pd.DataFrame, motivos: tuple[tuple[str, date, str], ...]) -> str | None:
    """Eventos da lista explícita que estão marcados na janela, com o motivo; agrupados por ticker e motivo.

    Só entra o par (ticker, data) marcado como suspeito (o mesmo critério da lista do aviso, sem limite de tickers).
    None se nenhum evento da lista cair na janela.
    """
    grupos: dict[tuple[str, str], list[date]] = {}
    for tk, d, motivo in motivos:
        dia = pd.Timestamp(d)
        if dia in janela.index and tk in janela.columns and janela.at[dia, tk]:
            grupos.setdefault((tk, motivo), []).append(d)
    if not grupos:
        return None
    partes = [f"{tk} ({', '.join(x.isoformat() for x in sorted(datas))}): {motivo}."
              for (tk, motivo), datas in sorted(grupos.items())]
    return "Eventos conhecidos: " + " ".join(partes)


def _cotacao(g: pd.DataFrame) -> Grade:
    """Grade de `grade_de_precos` com status: NaN (sem linha no dia) vira `indisponivel`."""
    status = pd.DataFrame(np.where(g.isna(), INDISPONIVEL, OK), index=g.index, columns=g.columns, dtype=object)
    return montar_grade(g, status)


def _coluna(g: Grade, nome: str) -> tuple[np.ndarray, np.ndarray]:
    """(valor, status) de uma coluna da grade, como arrays alinhados aos pregões."""
    return g.valor[nome].to_numpy(dtype=float), g.status[nome].to_numpy(dtype=object)


def _multiplo(g: Grade, nome: str, idx: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Coluna de um múltiplo alinhada a `idx`; pregão fora da grade vira `indisponivel`."""
    valor = g.valor[nome].reindex(idx).to_numpy(dtype=float)
    status = g.status[nome].reindex(idx).fillna(INDISPONIVEL).to_numpy(dtype=object)
    return valor, status


def _serie(ticker: str, tipo: str, nome: str, campos: dict[str, tuple], datas_pregao: list[date],
           ini: date, t: date) -> dict | None:
    """Série no formato compacto, só com os pontos de [ini, t] a partir do início da série.

    Início = 1º pregão em que `indice_retorno_total` deixa de ser `antes_do_inicio`. Esse status nunca
    entra no JSON; `indisponivel` vira null com trecho; `n_empresas` nunca tem status. Sem nenhum
    ponto na janela, devolve None (a série não é emitida).
    """
    ref = campos["indice_retorno_total"][1]
    inicio = next((p for p, st in enumerate(ref) if st != ANTES_DO_INICIO), len(ref))
    pos = [p for p in range(inicio, len(datas_pregao)) if ini <= datas_pregao[p] <= t]
    if not pos:
        return None
    datas = [datas_pregao[p].isoformat() for p in pos]
    valores: dict[str, list] = {}
    status: dict[str, list] = {}
    for campo, (valor, st) in campos.items():
        if campo == "n_empresas":
            valores[campo] = [int(valor[p]) for p in pos]
            continue
        estados = [INDISPONIVEL if st[p] == ANTES_DO_INICIO else st[p] for p in pos]
        valores[campo] = [contrato.numero(valor[p]) if e in _MANTEM else None for p, e in zip(pos, estados)]
        trechos = contrato.trechos(datas, estados)
        if trechos:
            status[campo] = trechos
    return {"ticker": ticker, "tipo": tipo, "nome": nome, "inicio_janela": ini.isoformat(),
            "datas": datas, "valores": valores, "status": status}


def _nomes(cadastro: pd.DataFrame) -> dict[str, str]:
    """Nome de cada ação: `empresa` do cadastro; sem ele, o próprio ticker."""
    return {t: (e.strip() if isinstance(e, str) and e.strip() else t)
            for t, e in zip(cadastro["ticker"], cadastro["empresa"])}


def series_completas(ins: Insumos, multiplos: dict[str, Grade],
                     params_precos: ParametrosPrecos | None = None) -> dict[str, dict]:
    """Séries do pacote, por ticker, só com as datas de [inicio_janela, t]; sem `substituir_serie`.

    `multiplos`: `fatos.multiplos.multiplos_diarios` (chaves "pl", "pvp", "dividend_yield").
    As grades são calculadas no histórico inteiro e o corte da janela é feito por último.
    Séries `SETOR_SEM:<ticker>` (DS10) no lugar das `SETOR:<nome>`: o setor sem a própria empresa.
    """
    params_precos = carregar_parametros_precos() if params_precos is None else params_precos
    cal, t = ins.cal, ins.t
    ini = inicio_janela(cal, t)
    idx = indice_pregoes(cal)
    datas_pregao = list(cal)
    tickers = tickers_do_painel(ins.cadastro, ins.exclusoes)
    pares = pares_do_painel(ins.cadastro, ins.exclusoes)
    cols = list(dict.fromkeys([*tickers, "IBOV", *ETFS]))

    g_aj_bruto = grade_de_precos(ins.precos, cal, "fechamento_ajustado", cols)
    g_fech = _cotacao(grade_de_precos(ins.precos, cal, "fechamento", cols))
    g_vol = _cotacao(grade_de_precos(ins.precos, cal, "volume", cols))
    base_aj = indice_base_100(g_aj_bruto)
    pontos_base, pontos = indice_pontos(ins.indices, cal, INDICES_PONTOS)
    cdi = indice_cdi(ins.indices, cal)
    ipca = indice_ipca(ins.indices, cal, params_precos.ipca_defasagem_max_meses)
    suspeitos = retornos_suspeitos(g_aj_bruto, params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max,
                                   params_precos.base_defasagem_max_pregoes, params_precos.eventos_retorno_suspeito)
    sem, n_sem = indice_setor_sem_empresa(g_aj_bruto, ins.cadastro, pares, tickers, params_precos.setor_excluir,
                                          suspeitos=suspeitos)
    setor_de = mapas_cadastro(ins.cadastro)[0]
    nomes = _nomes(ins.cadastro)

    res: dict[str, dict] = {}

    def guarda(serie: dict | None) -> None:
        if serie is not None:
            res[serie["ticker"]] = serie

    for tk in tickers:
        campos = {
            "fechamento": _coluna(g_fech, tk),
            "indice_retorno_total": _coluna(base_aj, tk),
            "volume": _coluna(g_vol, tk),
            "pl": _multiplo(multiplos["pl"], tk, idx),
            "pvp": _multiplo(multiplos["pvp"], tk, idx),
            "dividend_yield": _multiplo(multiplos["dividend_yield"], tk, idx),
        }
        guarda(_serie(tk, "acao", nomes.get(tk, tk), campos, datas_pregao, ini, t))

    for tk in ETFS:
        campos = {
            "fechamento": _coluna(g_fech, tk),
            "indice_retorno_total": _coluna(base_aj, tk),
            "volume": _coluna(g_vol, tk),
        }
        guarda(_serie(tk, "etf", tk, campos, datas_pregao, ini, t))

    campos = {"fechamento": _coluna(g_fech, "IBOV"), "indice_retorno_total": _coluna(base_aj, "IBOV")}
    guarda(_serie("IBOV", "indice", "Ibovespa", campos, datas_pregao, ini, t))

    for nome in INDICES_PONTOS:
        campos = {
            "fechamento": (pontos[nome].to_numpy(dtype=float), pontos_base.status[nome].to_numpy(dtype=object)),
            "indice_retorno_total": _coluna(pontos_base, nome),
        }
        guarda(_serie(nome, "indice", nome, campos, datas_pregao, ini, t))

    for nome, grade in (("CDI", cdi), ("IPCA", ipca)):
        guarda(_serie(nome, "taxa", nome, {"indice_retorno_total": _coluna(grade, nome)}, datas_pregao, ini, t))

    for col in sem.valor.columns:   # DS10: uma série "setor sem a própria empresa" por ticker
        tk = col.removeprefix(PREFIXO_SEM)
        campos = {
            "indice_retorno_total": _coluna(sem, col),
            "n_empresas": (n_sem[col].to_numpy(dtype=float), None),
        }
        nome = f"{setor_de.get(tk)} sem {nomes.get(tk, tk)}"
        guarda(_serie(col, "setor_sem_empresa", nome, campos, datas_pregao, ini, t))

    return res


# ---------------------------------------------------------------- envio "quando muda"

def _status_por_ponto(serie: dict) -> dict[str, list[str]]:
    """Status de cada ponto e campo (`ok` fora dos trechos), alinhado a `datas`."""
    posicao = {d: i for i, d in enumerate(serie["datas"])}
    por_campo = {c: ["ok"] * len(serie["datas"]) for c in serie["valores"]}
    for campo, trechos in serie["status"].items():
        for tr in trechos:
            for i in range(posicao[tr["de"]], posicao[tr["ate"]] + 1):
                por_campo[campo][i] = tr["status"]
    return por_campo


def _pontos(serie: dict) -> dict[str, dict[str, tuple]]:
    """{data: {campo: (valor, status)}}: a forma de comparar um ponto com o do estado."""
    sts = _status_por_ponto(serie)
    return {d: {c: (serie["valores"][c][i], sts[c][i]) for c in serie["valores"]}
            for i, d in enumerate(serie["datas"])}


def _mesmo(a: tuple, b: tuple, tolerancia_relativa: float) -> bool:
    """Mesmo valor (rel `tolerancia_relativa`, abs 1e-12; None só é igual a None) e mesmo status."""
    (va, sa), (vb, sb) = a, b
    if sa != sb:
        return False
    if va is None or vb is None:
        return va is None and vb is None
    return math.isclose(va, vb, rel_tol=tolerancia_relativa, abs_tol=1e-12)


def _envio_da_serie(atual: dict, anterior: dict, tolerancia_relativa: float = 1e-6) -> dict | None:
    """Série a enviar frente ao estado: a inteira, só os pontos novos, ou None (nada a enviar).

    Ponto antigo conta como mudado só acima de `tolerancia_relativa` (ruído float32 da coleta).
    Ponto do estado com data < inicio_janela atual saiu pelo corte: não conta como sumido.
    """
    ini = atual["inicio_janela"]
    pa, pb = _pontos(atual), _pontos(anterior)
    ultima = max(anterior["datas"], default=None)
    inteira = set(atual["valores"]) != set(anterior["valores"])
    if not inteira:
        for d, campos_ant in pb.items():
            if d < ini:
                continue
            if d not in pa or not all(_mesmo(campos_ant[c], pa[d][c], tolerancia_relativa) for c in campos_ant):
                inteira = True
                break
    if not inteira and ultima is not None:
        inteira = any(d not in pb and d <= ultima for d in pa)
    if inteira:
        return {**atual, "substituir_serie": True}
    novas = {d for d in atual["datas"] if ultima is None or d > ultima}
    if not novas:
        return None
    return _recorte_novo(atual, novas)


def _recorte_novo(atual: dict, novas: set[str]) -> dict:
    """Série só com os pontos `novas` (valores e trechos recortados), `substituir_serie` False."""
    sts = _status_por_ponto(atual)
    pos = [i for i, d in enumerate(atual["datas"]) if d in novas]
    datas = [atual["datas"][i] for i in pos]
    valores = {c: [atual["valores"][c][i] for i in pos] for c in atual["valores"]}
    status = {}
    for c in atual["valores"]:
        trechos = contrato.trechos(datas, [sts[c][i] for i in pos])
        if trechos:
            status[c] = trechos
    return {**atual, "datas": datas, "valores": valores, "status": status, "substituir_serie": False}


def comparar_series(atuais: dict[str, dict], estado: dict[str, dict] | None,
                    tolerancia_relativa: float = 1e-6) -> tuple[list[dict], list[dict]]:
    """(séries a enviar, removidos [{"ticker"}]) frente ao estado do último envio (seção 2.4).

    `estado None` = primeira vez: manda tudo com `substituir_serie` True. Cada série enviada leva
    `substituir_serie`; as que não mudaram não vão. `tolerancia_relativa`: ver `_envio_da_serie`.
    """
    if estado is None:
        return [{**s, "substituir_serie": True} for s in atuais.values()], []
    enviar = []
    for ticker, atual in atuais.items():
        anterior = estado.get(ticker)
        registro = ({**atual, "substituir_serie": True} if anterior is None
                    else _envio_da_serie(atual, anterior, tolerancia_relativa))
        if registro is not None:
            enviar.append(registro)
    removidos = [{"ticker": t} for t in estado if t not in atuais] if estado is not None else []
    return enviar, removidos


def _registro(meta: dict, serie: dict) -> dict:
    """Registro do pacote: campos comuns da rodada e os da série, na ordem do contrato."""
    return {**meta, "ticker": serie["ticker"], "tipo": serie["tipo"], "nome": serie["nome"],
            "substituir_serie": serie["substituir_serie"], "inicio_janela": serie["inicio_janela"],
            "datas": serie["datas"], "valores": serie["valores"], "status": serie["status"]}


def montar_series_diarias(ins: Insumos, multiplos: dict[str, Grade], estado: list[dict] | None,
                          gerado_em: str, dados_ate: str,
                          params_precos: ParametrosPrecos | None = None,
                          tolerancia_relativa: float = 1e-6) -> tuple[list[dict], list[dict], list[dict]]:
    """(registros, removidos, novo_estado) do `series_diarias`.

    `estado` é o que `contrato.ler_estado("series_diarias")` devolve (lista de séries, ou None na
    primeira vez). `novo_estado` é a lista que `contrato.gravar_estado` grava depois do envio aceito.
    `tolerancia_relativa` (saida.tolerancia_serie_relativa) vai para `comparar_series`.
    Os registros não são validados aqui: a validação é do `contrato.gravar_lote`.
    """
    atuais = series_completas(ins, multiplos, params_precos)
    anterior = None if estado is None else {s["ticker"]: s for s in estado}
    enviar, removidos = comparar_series(atuais, anterior, tolerancia_relativa)
    meta = contrato.meta(gerado_em, dados_ate)
    registros = [_registro(meta, s) for s in enviar]
    return registros, removidos, list(atuais.values())
