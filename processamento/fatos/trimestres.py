"""Trimestres, 12 meses e foto do balanço em t (seção 6 da especificação).

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Point-in-time: só entra balanço com `data_entrega <= t`. Ausência é NaN + `status` (nunca 0).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from processamento.diagnostico.regras import classificar_dias_periodo
from processamento.exclusoes import Exclusoes
from processamento.fatos.precos import HIST, INDISPONIVEL, OK

FLUXO = ("receita_liquida", "lucro_bruto", "lucro_liquido", "ebit", "depreciacao_amortizacao")
ESTOQUE = ("patrimonio_liquido", "emprestimos_curto_prazo", "emprestimos_longo_prazo", "caixa",
           "aplicacoes_financeiras")

_COLUNAS_TRIMESTRE = ["cnpj", "data_fim_periodo", "data_entrega", "origem", *FLUXO]


@dataclass(frozen=True)
class FotoBalanco:
    """Foto do balanço de um CNPJ em t: status da base, datas da referência e os valores.

    Cada valor dos dicionários é o par (valor, status). Ausência é NaN com status diferente de ok.
    """

    status_base: str
    data_fim_periodo: pd.Timestamp | None
    data_entrega: pd.Timestamp | None
    fluxo_12m: dict[str, tuple[float, str]]
    fluxo_trimestre: dict[str, tuple[float, str]]
    estoque: dict[str, tuple[float, str]]


def meses_do_periodo(ini, fim) -> int | None:
    """Quantidade de meses do período (3, 6, 9 ou 12) pela contagem de dias; None se não for um deles."""
    if pd.isna(ini) or pd.isna(fim):
        return None
    dias = (pd.Timestamp(fim) - pd.Timestamp(ini)).days + 1
    classe = classificar_dias_periodo(dias)
    return None if classe == "outro" else int(classe[:-1])


def periodo_valido(tipo, ini, fim) -> bool:
    """Período aceito na linha de balanço: ITR com 3, 6 ou 9 meses; DFP com 12; outro tipo, se classificado."""
    meses = meses_do_periodo(ini, fim)
    if meses is None:
        return False
    if tipo == "ITR":
        return meses in (3, 6, 9)
    if tipo == "DFP":
        return meses == 12
    return True


def so_periodos_validos(balancos: pd.DataFrame) -> pd.DataFrame:
    """Linhas de balanço com período válido (ver `periodo_valido`); as demais saem antes de qualquer conta.

    Sem a coluna `tipo_documento`, vale só a regra de meses (3, 6, 9 ou 12). Sem as colunas de
    período, nada é filtrado (DataFrame vazio de fixtures que só trazem cnpj e datas de entrega).
    """
    if not {"data_inicio_periodo", "data_fim_periodo"} <= set(balancos.columns):
        return balancos
    if "tipo_documento" in balancos.columns:
        validas = [periodo_valido(t, i, f) for t, i, f in zip(
            balancos["tipo_documento"], balancos["data_inicio_periodo"], balancos["data_fim_periodo"])]
    else:
        validas = [meses_do_periodo(i, f) in (3, 6, 9, 12) for i, f in zip(
            balancos["data_inicio_periodo"], balancos["data_fim_periodo"])]
    return balancos[pd.Series(validas, index=balancos.index, dtype=bool)]


def entregues_ate(balancos: pd.DataFrame, t) -> pd.DataFrame:
    """Linhas com `data_entrega <= t` e período válido (seção 6). Linha sem data de entrega (NaT) fica de fora."""
    limite = pd.Timestamp(t)
    return so_periodos_validos(balancos[balancos["data_entrega"] <= limite])


def _com_meses(entregues: pd.DataFrame) -> pd.DataFrame:
    """Cópia das linhas com a coluna `meses`; linhas de período não classificado saem."""
    meses = [meses_do_periodo(i, f)
             for i, f in zip(entregues["data_inicio_periodo"], entregues["data_fim_periodo"])]
    base = entregues.assign(meses=meses)
    base = base[base["meses"].notna()].copy()
    base["meses"] = base["meses"].astype(int)
    return base


def _primeira(linhas: pd.DataFrame) -> pd.Series | None:
    """Primeira linha do DataFrame ou None se vazio."""
    return linhas.iloc[0] if len(linhas) else None


def trimestres_isolados(balancos: pd.DataFrame, t) -> pd.DataFrame:
    """Trimestres isolados entregues até t.

    Para cada (cnpj, fim): o valor vem da linha de 3 meses; se ela não existir ou a conta
    for nula, sai da diferença entre o acumulado e o período anterior (ex.: DFP − 9m).
    """
    base = _com_meses(entregues_ate(balancos, t))
    registros = []
    for (cnpj, fim), grupo in base.groupby(["cnpj", "data_fim_periodo"], sort=True):
        linha3 = _primeira(grupo[grupo["meses"] == 3])
        acum = _primeira(grupo[grupo["meses"] == grupo["meses"].max()])
        ant = None
        if acum["meses"] > 3:
            ant = _primeira(base[(base["cnpj"] == cnpj)
                                 & (base["data_inicio_periodo"] == acum["data_inicio_periodo"])
                                 & (base["meses"] == acum["meses"] - 3)])
        if linha3 is None and ant is None:
            continue
        valores = {}
        diferenca_usada = False
        for c in FLUXO:
            if linha3 is not None and pd.notna(linha3[c]):
                valores[c] = linha3[c]
            elif ant is not None:
                valores[c] = acum[c] - ant[c]
                diferenca_usada = True
            else:
                valores[c] = np.nan
        usadas = [linha3] if linha3 is not None else []
        if diferenca_usada:
            usadas += [acum, ant]
        registros.append({
            "cnpj": cnpj,
            "data_fim_periodo": fim,
            "data_entrega": max(linha["data_entrega"] for linha in usadas),
            "origem": "itr_3m" if linha3 is not None else "diferenca",
            **valores,
        })
    trimestres = pd.DataFrame(registros, columns=_COLUNAS_TRIMESTRE)
    trimestres["data_fim_periodo"] = pd.to_datetime(trimestres["data_fim_periodo"])
    trimestres["data_entrega"] = pd.to_datetime(trimestres["data_entrega"])
    for c in FLUXO:
        trimestres[c] = trimestres[c].astype(float)
    return trimestres.sort_values(["cnpj", "data_fim_periodo"], ignore_index=True)


def doze_meses(trimestres: pd.DataFrame, cnpj: str, fim) -> dict[str, tuple[float, str]]:
    """Soma dos 4 trimestres que terminam em `fim` e nos 3 meses anteriores (12 meses).

    Trimestre presente com a conta nula: indisponivel. Menos de 4 trimestres: historico_insuficiente.
    """
    fim = pd.Timestamp(fim)
    esperados = [fim.to_period("M") - k for k in (0, 3, 6, 9)]
    do_cnpj = trimestres[trimestres["cnpj"] == cnpj]
    presentes = do_cnpj[do_cnpj["data_fim_periodo"].dt.to_period("M").isin(esperados)]
    resultado = {}
    for c in FLUXO:
        valores = presentes[c]
        if valores.isna().any():
            resultado[c] = (np.nan, INDISPONIVEL)
        elif len(presentes) < 4:
            resultado[c] = (np.nan, HIST)
        else:
            resultado[c] = (float(valores.sum()), OK)
    return resultado


def referencia(balancos: pd.DataFrame, cnpj: str, t) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Maior `data_fim_periodo` entregue até t e a maior `data_entrega` das linhas com esse fim."""
    do_cnpj = entregues_ate(balancos, t)
    do_cnpj = do_cnpj[do_cnpj["cnpj"] == cnpj]
    if do_cnpj.empty:
        return None, None
    fim = do_cnpj["data_fim_periodo"].max()
    if pd.isna(fim):
        return None, None
    return fim, _entrega_do_fim(do_cnpj, fim)


def _entrega_do_fim(entregues: pd.DataFrame, fim) -> pd.Timestamp:
    """Maior data de entrega entre as linhas entregues com esse fim."""
    return entregues.loc[entregues["data_fim_periodo"] == fim, "data_entrega"].max()


def estoques_no_fim(balancos: pd.DataFrame, cnpj: str, fim, t) -> dict[str, tuple[float, str]]:
    """Saldo de balanço no fim do período: 1º valor não nulo entre as linhas entregues com esse fim.

    Período mais longo primeiro (a DFP vale mais que o ITR de mesmo fim).
    """
    fim = pd.Timestamp(fim)
    base = entregues_ate(balancos, t)
    linhas = base[(base["cnpj"] == cnpj) & (base["data_fim_periodo"] == fim)]
    prazos = [meses_do_periodo(i, f) or 0
              for i, f in zip(linhas["data_inicio_periodo"], linhas["data_fim_periodo"])]
    linhas = linhas.iloc[sorted(range(len(linhas)), key=lambda i: -prazos[i])]
    resultado = {}
    for c in ESTOQUE:
        valores = linhas[c].dropna()
        if len(valores):
            resultado[c] = (float(valores.iloc[0]), OK)
        else:
            resultado[c] = (np.nan, INDISPONIVEL)
    return resultado


def _sem_base(status: str) -> FotoBalanco:
    """Foto sem balanço utilizável: todos os pares com NaN e o status da base."""
    return FotoBalanco(
        status_base=status,
        data_fim_periodo=None,
        data_entrega=None,
        fluxo_12m={c: (np.nan, status) for c in FLUXO},
        fluxo_trimestre={c: (np.nan, status) for c in FLUXO},
        estoque={c: (np.nan, status) for c in ESTOQUE},
    )


def _status_base(cnpj, do_cnpj: pd.DataFrame, entregues: pd.DataFrame, exclusoes: Exclusoes) -> str:
    """indisponivel (sem CNPJ, excluído ou sem linhas); historico_insuficiente (nada entregue até t); ok."""
    if not isinstance(cnpj, str) or cnpj in exclusoes.cnpjs_sem_balanco or do_cnpj.empty:
        return INDISPONIVEL
    if entregues.empty:
        return HIST
    return OK


def _trimestre_do_fim(trimestres: pd.DataFrame, cnpj: str, fim) -> dict[str, tuple[float, str]]:
    """Valores do trimestre que termina em `fim` (historico_insuficiente se ele não existe)."""
    do_fim = trimestres[(trimestres["cnpj"] == cnpj) & (trimestres["data_fim_periodo"] == fim)]
    if do_fim.empty:
        return {c: (np.nan, HIST) for c in FLUXO}
    linha = do_fim.iloc[0]
    return {c: ((float(linha[c]), OK) if pd.notna(linha[c]) else (np.nan, INDISPONIVEL))
            for c in FLUXO}


def foto_balanco(balancos: pd.DataFrame, cnpj: str, t, exclusoes: Exclusoes,
                 fim=None) -> FotoBalanco:
    """Foto do balanço do CNPJ em t (point-in-time).

    `fim=None` usa a referência (maior fim entregue). Um `fim` informado precisa ter linha
    entregue até t; senão levanta `ValueError`.
    """
    t = pd.Timestamp(t)
    do_cnpj = balancos[balancos["cnpj"] == cnpj] if isinstance(cnpj, str) else balancos.iloc[0:0]
    entregues = entregues_ate(do_cnpj, t)
    if fim is not None:
        fim = pd.Timestamp(fim)
        if not (entregues["data_fim_periodo"] == fim).any():
            raise ValueError(f"fim {fim.date()} sem balanço entregue até {t.date()} (cnpj {cnpj})")
    status = _status_base(cnpj, do_cnpj, entregues, exclusoes)
    if status != OK:
        return _sem_base(status)
    if fim is None:
        fim, entrega = referencia(do_cnpj, cnpj, t)
    else:
        entrega = _entrega_do_fim(entregues, fim)
    trimestres = trimestres_isolados(do_cnpj, t)
    return FotoBalanco(
        status_base=OK,
        data_fim_periodo=fim,
        data_entrega=entrega,
        fluxo_12m=doze_meses(trimestres, cnpj, fim),
        fluxo_trimestre=_trimestre_do_fim(trimestres, cnpj, fim),
        estoque=estoques_no_fim(do_cnpj, cnpj, fim, t),
    )
