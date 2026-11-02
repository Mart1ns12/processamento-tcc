"""Dias de resultado do experimento: pregão em que cada empresa teve balanço (plano da etapa 5).

Cada `data_entrega` vira o instante D 23:59:59 (fuso de São Paulo) e passa pela janela de notícias
(`calendario.classificar_noticias`). Se a entrega cai na noite de t, a empresa tem resultado no
dia t. Também tem as colunas do protocolo de balanço e CVM (blocos C e E): `dias_desde_resultado`,
`var_lucro_aa` e `fato_relevante_cvm`. Funções puras: nada de banco ou rede.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from processamento import calendario
from processamento.experimento.parametros import mascara_sem_coleta
from processamento.fatos.fundamentos import limite_do_balanco
from processamento.fatos.precos import indice_pregoes
from processamento.fatos.trimestres import ESTOQUE, FLUXO, estoques_no_fim, so_periodos_validos, trimestres_isolados

_COLUNAS_PERIODO = {"tipo_documento", "data_inicio_periodo", "data_fim_periodo"}
_COLUNAS_DA_CONTA = _COLUNAS_PERIODO | set(FLUXO) | set(ESTOQUE)
ATRASO_MAX_ENTREGA_DIAS = 180   # entrega mais tardia que isto é reapresentação que moveu a data (dias_desde_resultado)
CATEGORIA_FATO_RELEVANTE = "Fato Relevante"
_TIPOS_REAPRESENTACAO = ("RE", "RR")   # Tipo_Apresentacao da CVM: "RE - Reapresentação Espontânea" e "RR - ..."; "AP" é a original
_MESES_RECORTE = 16   # o ano anterior e o acumulado de 9 meses dele terminam no máximo 15 meses antes do fim de referência


def _instantes_de_entrega(datas_entrega: pd.Series) -> pd.Series:
    """`data_entrega` às 23:59:59 de São Paulo (regra E11)."""
    datas = pd.to_datetime(datas_entrega).dt.normalize()
    return (datas + pd.Timedelta(hours=23, minutes=59, seconds=59)).dt.tz_localize(calendario.SP)


def dias_de_resultado(
    balancos: pd.DataFrame, cal: list, proximo_ao_vivo=None
) -> tuple[pd.DataFrame, dict]:
    """Pares (data, empresa) únicos: pregão t cuja noite contém a entrega de balanço.

    `empresa` é o CNPJ do balanço. Contagens: `sem_data` (data_entrega nula, ignorada) e `fora`
    (entrega fora do calendário, por linha de balanço). Linhas de período inválido (seção 6) saem
    antes, quando o DataFrame traz as colunas de período; sem elas, nada é filtrado.
    """
    if _COLUNAS_PERIODO <= set(balancos.columns):
        balancos = so_periodos_validos(balancos)
    sem_data = balancos["data_entrega"].isna()
    validos = balancos.loc[~sem_data].reset_index(drop=True)
    instantes = _instantes_de_entrega(validos["data_entrega"])
    entregas = pd.DataFrame({"empresa": validos["cnpj"], "data_hora_publicacao": instantes})

    classificadas = calendario.classificar_noticias(entregas, list(cal), proximo_ao_vivo)
    janelas = classificadas["janela"]
    contagens = {
        "sem_data": int(sem_data.sum()),
        "fora": int((janelas == "fora_do_calendario").sum()),
    }

    noite = classificadas.loc[janelas == "noite"]
    resultado = (
        pd.DataFrame({"data": pd.to_datetime(noite["pregao_ref"]), "empresa": noite["empresa"]})
        .drop_duplicates()
        .sort_values(["data", "empresa"])
        .reset_index(drop=True)
    )
    return resultado, contagens


def pregao_da_entrega(datas_entrega: pd.Series, cal: list, proximo_ao_vivo=None) -> pd.Series:
    """Pregão de referência de cada entrega: 23:59:59 da data, na noite do pregão (fim de semana vai para o anterior).

    Fora do calendário: NaT. Sem `proximo_ao_vivo`, a entrega depois do último pregão fica fora; com ele, entra até
    D − 1 dia (o corte das 08:00 de D exclui a entrega de D, que vale 23:59:59).
    """
    entregas = pd.DataFrame({"data_hora_publicacao": _instantes_de_entrega(datas_entrega)})
    classificadas = calendario.classificar_noticias(entregas, list(cal), proximo_ao_vivo)
    return pd.to_datetime(classificadas["pregao_ref"]).where(classificadas["janela"] == "noite")


def _grade_vazia(cal: list, empresas: list[str]) -> pd.DataFrame:
    return pd.DataFrame(np.nan, index=indice_pregoes(cal), columns=list(empresas), dtype=float)


def _linhas_validas(balancos: pd.DataFrame) -> pd.DataFrame:
    """Linhas com as duas datas e período válido (seção 6, "Período inválido")."""
    return so_periodos_validos(balancos[balancos["data_entrega"].notna() & balancos["data_fim_periodo"].notna()])


def dias_desde_resultado(balancos: pd.DataFrame, cal: list, empresas: list[str], meses_velho: int,
                         sem_balanco=(), proximo_ao_vivo=None) -> pd.DataFrame:
    """Pregões desde a última entrega válida, por pregão × empresa (entrega no pregão t = 0).

    A entrega só conta a partir do pregão dela (`pregao_da_entrega`), logo nunca antes do corte de t. Linha com
    `data_entrega − data_fim_periodo` acima de `ATRASO_MAX_ENTREGA_DIAS` não conta como entrega, mas ainda define a
    referência do balanço velho. Balanço velho em t, empresa em `sem_balanco` ou sem entrega: NaN.
    Sem as colunas de período (só fixtures antigas; a leitura real sempre traz): tudo NaN.
    """
    grade = _grade_vazia(cal, empresas)
    if not _COLUNAS_PERIODO <= set(balancos.columns):
        return grade
    linhas = _linhas_validas(balancos)
    if linhas.empty:
        return grade
    idx = grade.index
    linhas = linhas.assign(pos=idx.get_indexer(pregao_da_entrega(linhas["data_entrega"], cal, proximo_ao_vivo)))
    linhas = linhas[linhas["pos"] >= 0]
    posicoes = np.arange(len(idx))
    for cnpj, grupo in linhas.groupby("cnpj"):
        if cnpj not in grade.columns or cnpj in sem_balanco:
            continue
        atraso = (grupo["data_entrega"] - grupo["data_fim_periodo"]).dt.days
        validas = grupo.loc[atraso <= ATRASO_MAX_ENTREGA_DIAS, "pos"].to_numpy()
        ultima = np.full(len(idx), -1)
        ultima[validas] = validas
        ultima = np.maximum.accumulate(ultima)
        dias = np.where(ultima >= 0, (posicoes - ultima).astype(float), np.nan)
        fim = grupo.groupby("pos")["data_fim_periodo"].max().reindex(posicoes).ffill().cummax()
        limites = fim.map({f: limite_do_balanco(f, meses_velho) for f in fim.dropna().unique()})
        grade[cnpj] = np.where(idx.to_numpy() > limites.to_numpy(), np.nan, dias)
    return grade


def _var_lucro_na_entrega(linhas: pd.DataFrame, cnpj: str, dia: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    """(fim de referência, variação) com o que foi entregue até `dia`. `trimestres_isolados` e `estoques_no_fim` filtram a entrega."""
    fim = linhas.loc[linhas["data_entrega"] <= dia, "data_fim_periodo"].max()
    recorte = linhas[linhas["data_fim_periodo"] >= fim - pd.DateOffset(months=_MESES_RECORTE)]
    trimestres = trimestres_isolados(recorte, dia)
    meses = trimestres["data_fim_periodo"].dt.to_period("M")
    mes = pd.Timestamp(fim).to_period("M")
    atual = trimestres.loc[meses == mes, "lucro_liquido"]
    anterior = trimestres.loc[meses == mes - 12, "lucro_liquido"]
    pl = estoques_no_fim(recorte, cnpj, fim, dia)["patrimonio_liquido"][0]
    if atual.empty or anterior.empty or not pl > 0:
        return fim, np.nan
    return fim, float(atual.iloc[0] - anterior.iloc[0]) / pl


def var_lucro_aa(balancos: pd.DataFrame, cal: list, empresas: list[str], meses_velho: int, sem_balanco=()) -> pd.DataFrame:
    """(Lucro do trimestre de referência − lucro do mesmo trimestre do ano anterior) ÷ PL de referência, por pregão × empresa.

    Point-in-time: só `data_entrega <= t` (fim de semana só vale no pregão seguinte). A conta roda uma vez por data de
    entrega e vale até a próxima. Trimestre de referência sem valor isolado, ano anterior ausente, PL ≤ 0 ou vazio,
    balanço velho ou empresa em `sem_balanco`: NaN. Sem as colunas do contrato (só fixtures antigas): tudo NaN.
    """
    grade = _grade_vazia(cal, empresas)
    if not _COLUNAS_DA_CONTA <= set(balancos.columns):
        return grade
    idx = grade.index
    for cnpj, linhas in _linhas_validas(balancos).groupby("cnpj"):
        if cnpj not in grade.columns or cnpj in sem_balanco:
            continue
        entregas = pd.DatetimeIndex(linhas["data_entrega"].unique()).sort_values()
        contas = [_var_lucro_na_entrega(linhas, cnpj, dia) for dia in entregas]
        valores = np.array([v for _, v in contas], dtype=float)
        limites = pd.DatetimeIndex([limite_do_balanco(f, meses_velho) for f, _ in contas])
        pos = entregas.searchsorted(idx, side="right") - 1
        tem = pos >= 0
        coluna = np.full(len(idx), np.nan)
        coluna[tem] = valores[pos[tem]]
        coluna[tem & np.asarray(idx > limites[np.maximum(pos, 0)])] = np.nan
        grade[cnpj] = coluna
    return grade


def inicio_cobertura_cvm(documentos: pd.DataFrame | None) -> pd.Timestamp | None:
    """Menor `data_entrega` de qualquer categoria; None sem documento (sem cobertura)."""
    if documentos is None or not documentos["data_entrega"].notna().any():
        return None
    return documentos["data_entrega"].min()


def _reapresentacao(documentos: pd.DataFrame) -> pd.Series:
    """True na reapresentação: a original tem protocolo e data próprios, e a nova versão não é fato novo."""
    tipo = documentos["tipo_apresentacao"].map(lambda v: v.strip()[:2].upper() if isinstance(v, str) else "")
    return tipo.isin(_TIPOS_REAPRESENTACAO) | (pd.to_numeric(documentos["versao"], errors="coerce") > 1)


def fato_relevante_cvm(documentos: pd.DataFrame | None, cal: list, empresas: list[str], periodos_sem_coleta: tuple,
                       proximo_ao_vivo=None) -> pd.DataFrame:
    """1 se a empresa tem Fato Relevante com pregão de referência t; 0 se não tem, por pregão × empresa.

    NaN (nunca 0) sem documentos, antes da cobertura, nos `periodos_sem_coleta` e no último pregão sem
    `proximo_ao_vivo` (janela aberta, como as notícias).
    """
    grade = _grade_vazia(cal, empresas)
    cobertura = inicio_cobertura_cvm(documentos)
    if cobertura is None:
        return grade
    idx = grade.index
    fatos = documentos[(documentos["categoria"] == CATEGORIA_FATO_RELEVANTE) & documentos["data_entrega"].notna()
                       & ~_reapresentacao(documentos)]
    pos = idx.get_indexer(pregao_da_entrega(fatos["data_entrega"], cal, proximo_ao_vivo))
    grade.loc[:, :] = 0.0
    for cnpj, p in zip(fatos["cnpj"], pos):
        if p >= 0 and cnpj in grade.columns:
            grade.iloc[p, grade.columns.get_loc(cnpj)] = 1.0
    vazio = np.asarray(idx < cobertura) | mascara_sem_coleta(idx, periodos_sem_coleta)
    if proximo_ao_vivo is None and len(idx):
        vazio[-1] = True
    grade.loc[vazio, :] = np.nan
    return grade
