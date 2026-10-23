"""Séries base 100 da saída (etapa 7; plano seções 4.4 e 7): ação, IBOV, índices, CDI, IPCA e setor.

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Ausência é NaN + `status` (nunca 0). Antes do início da série o status é `ANTES_DO_INICIO`:
é status interno, o ponto não vai para o JSON. A grade inteira é calculada no histórico que
chega; o corte da janela de 253 pregões fica para o pacote (Fase 6b).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento.fatos.indices import _k, _meses_ipca, _serie_cdi, grade_de_indices
from processamento.fatos.precos import (
    INDISPONIVEL,
    OK,
    Grade,
    indice_pregoes,
    mapas_cadastro,
    montar_grade,
    retornos_diarios,
)

ANTES_DO_INICIO = "antes_do_inicio"  # status interno: o ponto não é emitido (nunca vai para o JSON)


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


def indice_ipca(indices: pd.DataFrame, cal: list) -> Grade:
    """IPCA em base 100: 100 × Π(1 + ipca_m) dos meses em (K(início), K(d)], sem rateio por dia.

    Início = 1º pregão com K definido (`indices._k`). Antes disso: `ANTES_DO_INICIO`.
    Mês faltando no intervalo: `indisponivel`.
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
    ret = retornos_diarios(g_aj[membros_todos])
    valor, status, contagem = {}, {}, {}
    for setor in sorted({setor_de[p] for p in membros_todos}):
        membros = [p for p in membros_todos if setor_de[p] == setor]
        existe = g_aj[membros].notna().any(axis=1).to_numpy()
        if not existe.any():
            continue
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
        nome = f"SETOR:{setor}"
        valor[nome], status[nome], contagem[nome] = nivel, st, cont
    cols = list(valor)
    valor_df = pd.DataFrame(valor, index=dias, columns=cols)
    status_df = pd.DataFrame(status, index=dias, columns=cols)
    n_df = pd.DataFrame(contagem, index=dias, columns=cols)
    return montar_grade(valor_df, status_df), n_df
