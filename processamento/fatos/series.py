"""Séries base 100 da saída (etapa 7; plano seções 4.4 e 7): ação, IBOV, índices, CDI, IPCA e setor.

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Ausência é NaN + `status` (nunca 0). Antes do início da série o status é `ANTES_DO_INICIO`:
é status interno, o ponto não vai para o JSON. A grade inteira é calculada no histórico que
chega; o corte da janela de 253 pregões fica para o pacote (Fase 6b).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.fatos.indices import _atraso_meses, _k, _meses_ipca, _serie_cdi, grade_de_indices
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    OK,
    Grade,
    _outros_do_setor,
    indice_pregoes,
    mapas_cadastro,
    montar_grade,
    retornos_diarios,
    variacao,
)

ANTES_DO_INICIO = "antes_do_inicio"  # status interno: o ponto não é emitido (nunca vai para o JSON)
PREFIXO_SEM = "SETOR_SEM:"  # série do setor sem a própria empresa, uma por ticker (DS10)


def indice_base_100(g: pd.DataFrame) -> Grade:
    """Cada coluna em base 100 no seu 1º valor não nulo.

    Antes desse valor: `ANTES_DO_INICIO`. Depois, NaN vira `indisponivel`.
    """
    valor, status = {}, {}
    for col in g.columns:
        s = g[col].astype(float)
        existe = s.notna().to_numpy()
        if not existe.any():
            valor[col] = pd.Series(np.nan, index=g.index)
            status[col] = pd.Series(ANTES_DO_INICIO, index=g.index, dtype=object)
            continue
        primeiro = int(existe.argmax())
        antes = np.arange(len(s)) < primeiro
        valor[col] = s / s.iloc[primeiro] * 100
        status[col] = pd.Series(
            np.select([antes, existe], [ANTES_DO_INICIO, OK], default=INDISPONIVEL),
            index=g.index, dtype=object,
        )
    cols = list(g.columns)
    return montar_grade(
        pd.DataFrame(valor, index=g.index, columns=cols),
        pd.DataFrame(status, index=g.index, columns=cols),
    )


def indice_pontos(indices: pd.DataFrame, cal: list, nomes=("IDIV", "SMLL", "IFIX")) -> tuple[Grade, pd.DataFrame]:
    """Índices em pontos (`v1-indices`) em base 100. Devolve (base 100, pontos)."""
    pontos = grade_de_indices(indices, cal, tuple(nomes))
    return indice_base_100(pontos), pontos


def indice_cdi(indices: pd.DataFrame, cal: list) -> Grade:
    """CDI em base 100: 100 × C(d)/C(início), com C(x) = produto de (1 + taxa) das datas < x.

    Início = 1º pregão ≥ a 1ª data do CDI. Antes do início: `ANTES_DO_INICIO`. O ponto d só é
    `ok` se todo pregão p com início ≤ p < d tem taxa; depois da 1ª falha, tudo é `indisponivel`.
    """
    idx = indice_pregoes(cal)
    taxa = _serie_cdi(indices)
    datas = set(taxa.index)
    fator = (1 + taxa).cumprod()

    def C(x) -> float:
        pos = fator.index.searchsorted(x, side="left")
        return 1.0 if pos == 0 else float(fator.iloc[pos - 1])

    inicio = int(idx.searchsorted(taxa.index[0], side="left")) if not taxa.empty else len(idx)
    base = C(idx[inicio]) if inicio < len(idx) else 1.0
    valor, status = [], []
    faltou = False
    for i, d in enumerate(idx):
        if i < inicio:
            valor.append(np.nan)
            status.append(ANTES_DO_INICIO)
            continue
        if faltou:
            valor.append(np.nan)
            status.append(INDISPONIVEL)
        else:
            valor.append(100 * C(d) / base)
            status.append(OK)
        if d not in datas:
            faltou = True
    return montar_grade(pd.DataFrame({"CDI": valor}, index=idx),
                        pd.DataFrame({"CDI": status}, index=idx))


def _fator_ipca(meses: dict, kb, kt) -> float | None:
    """Produto de (1 + ipca_m) para os meses m em (kb, kt]; None se algum mês não é conhecido."""
    fator = 1.0
    m = kb + 1
    while m <= kt:
        if m not in meses:
            return None
        fator *= 1 + meses[m]
        m += 1
    return fator


def indice_ipca(indices: pd.DataFrame, cal: list, defasagem_max_meses: int | None = None) -> Grade:
    """IPCA em base 100: 100 × Π(1 + ipca_m) dos meses em (K(início), K(d)], sem rateio por dia.

    Início = 1º pregão com K definido (`indices._k`). Antes disso: `ANTES_DO_INICIO`.
    Mês faltando no intervalo: `indisponivel`.
    Com `defasagem_max_meses`: ponto com K(d) mais de N meses antes do mês de d: `indisponivel`.
    """
    idx = indice_pregoes(cal)
    meses = _meses_ipca(indices)
    ks = [_k(meses, d) for d in idx]
    inicio = next((i for i, k in enumerate(ks) if k is not None), len(idx))
    valor, status = [], []
    for i in range(len(idx)):
        if i < inicio:
            valor.append(np.nan)
            status.append(ANTES_DO_INICIO)
            continue
        fator = _fator_ipca(meses, ks[inicio], ks[i])
        if fator is not None and defasagem_max_meses is not None and _atraso_meses(idx[i], ks[i]) > defasagem_max_meses:
            fator = None   # IPCA parado: o ponto não fica "reto", sai indisponivel
        if fator is None:
            valor.append(np.nan)
            status.append(INDISPONIVEL)
        else:
            valor.append(100 * fator)
            status.append(OK)
    return montar_grade(pd.DataFrame({"IPCA": valor}, index=idx),
                        pd.DataFrame({"IPCA": status}, index=idx))


def indice_setor(g_aj: pd.DataFrame, cadastro: pd.DataFrame, pares: list[str]) -> tuple[Grade, pd.DataFrame]:
    """Índice de cada setor em base 100 (colunas `SETOR:<nome>`) e nº de empresas que contam em cada dia.

    Membros: `pares` (pares do painel, sem BDR) com setor, a própria ação incluída. Retorno do dia
    de cada ação (`retornos_diarios`, sem preencher lacunas); média por empresa (CNPJ; ticker sem
    CNPJ é empresa própria) e depois média simples entre empresas. Início = 1º pregão com preço de
    algum membro: nível 100. Dia sem nenhuma empresa com retorno: `indisponivel`, e a cadeia segue
    do último nível válido. Setor sem nenhum preço não aparece.
    """
    setor_de, cnpj_de = mapas_cadastro(cadastro)
    dias = g_aj.index
    membros_todos = [p for p in pares if p in g_aj.columns and setor_de.get(p) is not None]
    ret = _retornos_dos_membros(g_aj, membros_todos, None)
    valor, status, contagem = {}, {}, {}
    for setor in sorted({setor_de[p] for p in membros_todos}):
        membros = [p for p in membros_todos if setor_de[p] == setor]
        cadeia = _cadeia(ret, g_aj, membros, cnpj_de)
        if cadeia is None:
            continue
        nome = f"SETOR:{setor}"
        valor[nome], status[nome], contagem[nome] = cadeia
    cols = list(valor)
    valor_df = pd.DataFrame(valor, index=dias, columns=cols)
    status_df = pd.DataFrame(status, index=dias, columns=cols)
    n_df = pd.DataFrame(contagem, index=dias, columns=cols)
    return montar_grade(valor_df, status_df), n_df


def _retornos_dos_membros(g_aj: pd.DataFrame, membros: list[str], suspeitos: pd.DataFrame | None) -> pd.DataFrame:
    """Retorno do dia de cada membro (`retornos_diarios`); com `suspeitos`, o retorno suspeito do dia vira NaN (seção 6)."""
    ret = retornos_diarios(g_aj[membros])
    if suspeitos is not None:
        fora = suspeitos.reindex(index=ret.index, columns=ret.columns, fill_value=False).astype(bool)
        ret = ret.mask(fora)
    return ret


def _cadeia(ret: pd.DataFrame, g_aj: pd.DataFrame, membros: list[str],
            cnpj_de: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """(nível, status, n_empresas) da média igual por empresa dos retornos de `membros`, em base 100.

    Início = 1º pregão com preço de algum membro (nível 100). Dia sem nenhuma empresa com retorno:
    `indisponivel` e a cadeia segue do último nível. None se nenhum membro tem preço.
    """
    dias = g_aj.index
    existe = g_aj[membros].notna().any(axis=1).to_numpy()
    if not existe.any():
        return None
    por_empresa = ret[membros].T.groupby([cnpj_de.get(p) or p for p in membros], sort=False).mean().T
    n = por_empresa.notna().sum(axis=1).to_numpy()
    media = por_empresa.mean(axis=1).to_numpy()
    primeiro = int(existe.argmax())
    nivel = np.full(len(dias), np.nan)
    st = np.full(len(dias), ANTES_DO_INICIO, dtype=object)
    cont = np.zeros(len(dias), dtype=int)
    ultimo = 100.0
    for i in range(primeiro, len(dias)):
        if i == primeiro:
            nivel[i], st[i] = 100.0, OK
        elif n[i] > 0:
            ultimo = ultimo * (1 + media[i])
            nivel[i], st[i], cont[i] = ultimo, OK, n[i]
        else:
            st[i] = INDISPONIVEL
    return nivel, st, cont


def indice_setor_sem_empresa(g_aj: pd.DataFrame, cadastro: pd.DataFrame, pares: list[str], tickers: list[str],
                             modo: str, suspeitos: pd.DataFrame | None = None) -> tuple[Grade, pd.DataFrame]:
    """Série `SETOR_SEM:<ticker>` de cada ticker: índice base 100 do setor dele sem a própria empresa (DS10).

    Membros: `pares` do mesmo setor sem o próprio ticker e, no modo "empresa", sem nenhuma ação do mesmo CNPJ
    (`fatos.precos._outros_do_setor`). Conta de `_cadeia` (média igual por empresa dos retornos diários, sem os
    suspeitos). Ticker sem outro membro, ou cujos membros nunca têm preço, não ganha coluna.
    Devolve (grade com colunas `SETOR_SEM:<ticker>`, n_empresas com as mesmas colunas).
    """
    setor_de, cnpj_de = mapas_cadastro(cadastro)
    validos = [p for p in pares if p in g_aj.columns]
    ret = _retornos_dos_membros(g_aj, validos, suspeitos)
    valor, status, contagem = {}, {}, {}
    for tk in tickers:
        outros = _outros_do_setor(tk, validos, setor_de, cnpj_de, modo)
        if not outros:
            continue
        cadeia = _cadeia(ret, g_aj, outros, cnpj_de)
        if cadeia is None:
            continue
        nome = f"{PREFIXO_SEM}{tk}"
        valor[nome], status[nome], contagem[nome] = cadeia
    idx, cols = g_aj.index, list(valor)
    return (montar_grade(pd.DataFrame(valor, index=idx, columns=cols), pd.DataFrame(status, index=idx, columns=cols)),
            pd.DataFrame(contagem, index=idx, columns=cols))


def rentabilidade_setor_sem_empresa(g_aj: pd.DataFrame, cadastro: pd.DataFrame, pares: list[str], tickers: list[str],
                                    janelas: dict[str, int], modo: str,
                                    suspeitos: pd.DataFrame | None = None,
                                    defasagem_max: int | None = None) -> dict[str, Grade]:
    """`rentabilidade.setor` por janela (chave = nome da janela; colunas = `tickers`): razão da série (DS11).

    N(t)/N(base) − 1 pela `variacao` (base as-of). Sem outro membro no setor: `indisponivel`; membros sem
    nenhum preço: `historico_insuficiente`; ponto de t vazio: `indisponivel`; base antes do início: HIST;
    base velha (mais de `defasagem_max` pregões antes da data-alvo): HIST.
    """
    setor_de, cnpj_de = mapas_cadastro(cadastro)
    validos = [p for p in pares if p in g_aj.columns]
    serie, _ = indice_setor_sem_empresa(g_aj, cadastro, pares, tickers, modo, suspeitos)
    idx = g_aj.index
    res = {}
    for nome_janela, n in janelas.items():
        valor, status = {}, {}
        for tk in tickers:
            col = f"{PREFIXO_SEM}{tk}"
            if col in serie.valor.columns:
                v = variacao(serie.valor[[col]], n, defasagem_max)
                valor[tk], status[tk] = v.valor[col], v.status[col]
            else:
                tem_outros = bool(_outros_do_setor(tk, validos, setor_de, cnpj_de, modo))
                valor[tk] = pd.Series(np.nan, index=idx)
                status[tk] = pd.Series(HIST if tem_outros else INDISPONIVEL, index=idx, dtype=object)
        res[nome_janela] = montar_grade(pd.DataFrame(valor, index=idx, columns=tickers),
                                        pd.DataFrame(status, index=idx, columns=tickers))
    return res
