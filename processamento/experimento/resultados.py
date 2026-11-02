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
from processamento.fatos.trimestres import ESTOQUE, FLUXO, meses_do_periodo, so_periodos_validos

_COLUNAS_PERIODO = {"tipo_documento", "data_inicio_periodo", "data_fim_periodo"}
_COLUNAS_DA_CONTA = _COLUNAS_PERIODO | set(FLUXO) | set(ESTOQUE)
ATRASO_MAX_ENTREGA_DIAS = 180   # entrega mais tardia que isto é reapresentação que moveu a data (dias_desde_resultado)
CATEGORIA_FATO_RELEVANTE = "Fato Relevante"
_TIPOS_REAPRESENTACAO = ("RE", "RR", "RC")   # Tipo_Apresentacao da CVM: "RE - Reapresentação Espontânea", "RR - ..." e "RC - Reapresentação por Exigência"; "AP" é a original
ATRASO_MAX_REAPRESENTACAO_DIAS = 10   # reapresentação sem original entregue até 10 dias depois de data_referencia conta como evento
JANELA_ORIGINAL_DIAS = 10   # original de Fato Relevante entregue nos 10 dias corridos antes da reapresentação
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


def _contas_da_empresa(linhas: pd.DataFrame, entregas: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, float]]:
    """(fim de referência, variação) de cada entrega da empresa, na ordem de `entregas`.

    Réplica de `trimestres_isolados` (só o lucro) e `estoques_no_fim` (só o PL) sobre listas: a versão com pandas
    era chamada uma vez por entrega e dominava o tempo da rotina. Linhas na ordem do balanço, porque "primeira
    linha" é a primeira nessa ordem. `tests/test_exp_var_lucro_equivalencia.py` compara com a versão pandas.
    """
    registros = [
        (inicio, fim, entrega, meses_do_periodo(inicio, fim), lucro, pl)
        for inicio, fim, entrega, lucro, pl in zip(
            linhas["data_inicio_periodo"].tolist(), linhas["data_fim_periodo"].tolist(),
            linhas["data_entrega"].tolist(), linhas["lucro_liquido"].tolist(),
            linhas["patrimonio_liquido"].tolist())
    ]
    corte: dict[pd.Timestamp, pd.Timestamp] = {}
    return [_variacao_na_entrega(registros, dia, corte) for dia in entregas]


def _variacao_na_entrega(registros: list, dia: pd.Timestamp, corte: dict) -> tuple[pd.Timestamp, float]:
    """Registro: (início, fim, entrega, meses, lucro, PL). `corte` guarda o limite do recorte por fim de referência."""
    fim = max(r[1] for r in registros if r[2] <= dia)
    if fim not in corte:
        corte[fim] = fim - pd.DateOffset(months=_MESES_RECORTE)
    recorte = [r for r in registros if r[1] >= corte[fim]]
    entregues = [r for r in recorte if r[2] <= dia]
    trimestres = _trimestres_entregues(entregues)
    mes = fim.to_period("M")
    atual = [lucro for f, lucro in trimestres if f.to_period("M") == mes]
    anterior = [lucro for f, lucro in trimestres if f.to_period("M") == mes - 12]
    pl = _pl_no_fim(entregues, fim)
    if not atual or not anterior or not pl > 0:
        return fim, np.nan
    return fim, float(atual[0] - anterior[0]) / pl


def _trimestres_entregues(entregues: list) -> list[tuple[pd.Timestamp, float]]:
    """(fim, lucro isolado) por fim de período, em ordem de fim. Mesma regra de `trimestres_isolados`: a linha de
    3 meses; sem ela ou com lucro nulo, a diferença entre o acumulado e o período anterior (ex.: DFP − 9 meses)."""
    grupos: dict[pd.Timestamp, list] = {}
    for r in entregues:
        grupos.setdefault(r[1], []).append(r)
    trimestres = []
    for fim in sorted(grupos):
        grupo = grupos[fim]
        linha3 = next((r for r in grupo if r[3] == 3), None)
        maior = max(r[3] for r in grupo)
        acum = next(r for r in grupo if r[3] == maior)
        ant = None
        if acum[3] > 3:
            ant = next((r for r in entregues if r[0] == acum[0] and r[3] == acum[3] - 3), None)
        if linha3 is None and ant is None:
            continue
        if linha3 is not None and pd.notna(linha3[4]):
            lucro = linha3[4]
        elif ant is not None:
            lucro = acum[4] - ant[4]
        else:
            lucro = np.nan
        trimestres.append((fim, lucro))
    return trimestres


def _pl_no_fim(entregues: list, fim: pd.Timestamp) -> float:
    """PL do período mais longo que termina em `fim` (empate: ordem do balanço); NaN se nenhum tem valor."""
    do_fim = sorted((r for r in entregues if r[1] == fim), key=lambda r: -r[3])
    for r in do_fim:
        if pd.notna(r[5]):
            return float(r[5])
    return np.nan


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
        contas = _contas_da_empresa(linhas, entregas)
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


def _tem_original(originais: pd.DataFrame | None, entrega: pd.Timestamp, referencia: pd.Timestamp) -> bool:
    """Há original da empresa entregue até `entrega` com a mesma referência ou nos JANELA_ORIGINAL_DIAS dias antes."""
    if originais is None:
        return False
    anteriores = originais[originais["data_entrega"] <= entrega]
    na_janela = anteriores["data_entrega"] >= entrega - pd.Timedelta(days=JANELA_ORIGINAL_DIAS)
    return bool(((anteriores["data_referencia"] == referencia) | na_janela).any())


def _eventos_fato_relevante(documentos: pd.DataFrame) -> pd.DataFrame:
    """Fatos Relevantes que contam como evento: as originais e as reapresentações órfãs.

    Órfã: `data_referencia` preenchida, entregue de 0 a ATRASO_MAX_REAPRESENTACAO_DIAS dias depois dela, e sem original
    da mesma empresa entregue até a sua entrega (`_tem_original`). Entre as órfãs da mesma empresa e referência, só a de
    menor `data_entrega` conta. Nunca olha original entregue depois da reapresentação.
    """
    fatos = documentos[(documentos["categoria"] == CATEGORIA_FATO_RELEVANTE) & documentos["data_entrega"].notna()]
    fatos = fatos.reset_index(drop=True)
    reap = _reapresentacao(fatos).to_numpy()
    originais = fatos[~reap]
    candidatas = fatos[reap & fatos["data_referencia"].notna().to_numpy()]
    atraso = (candidatas["data_entrega"] - candidatas["data_referencia"]).dt.days
    candidatas = candidatas[atraso.between(0, ATRASO_MAX_REAPRESENTACAO_DIAS).to_numpy()]
    por_cnpj = {cnpj: grupo for cnpj, grupo in originais.groupby("cnpj")}
    sem_original = np.array([
        not _tem_original(por_cnpj.get(cnpj), entrega, referencia)
        for cnpj, entrega, referencia in zip(candidatas["cnpj"], candidatas["data_entrega"], candidatas["data_referencia"])
    ], dtype=bool)
    orfas = candidatas[sem_original].sort_values("data_entrega", kind="stable")
    orfas = orfas.drop_duplicates(["cnpj", "data_referencia"])
    return pd.concat([originais, orfas])


def fato_relevante_cvm(documentos: pd.DataFrame | None, cal: list, empresas: list[str], periodos_sem_coleta: tuple,
                       proximo_ao_vivo=None) -> pd.DataFrame:
    """1 se a empresa tem Fato Relevante com pregão de referência t; 0 se não tem, por pregão × empresa.

    Conta o original e a reapresentação sem original (`_eventos_fato_relevante`), na `data_entrega`.
    NaN (nunca 0) sem documentos, antes da cobertura, nos `periodos_sem_coleta` e no último pregão sem
    `proximo_ao_vivo` (janela aberta, como as notícias).
    """
    grade = _grade_vazia(cal, empresas)
    cobertura = inicio_cobertura_cvm(documentos)
    if cobertura is None:
        return grade
    idx = grade.index
    eventos = _eventos_fato_relevante(documentos)
    pos = idx.get_indexer(pregao_da_entrega(eventos["data_entrega"], cal, proximo_ao_vivo))
    grade.loc[:, :] = 0.0
    for cnpj, p in zip(eventos["cnpj"], pos):
        if p >= 0 and cnpj in grade.columns:
            grade.iloc[p, grade.columns.get_loc(cnpj)] = 1.0
    vazio = np.asarray(idx < cobertura) | mascara_sem_coleta(idx, periodos_sem_coleta)
    if proximo_ao_vivo is None and len(idx):
        vazio[-1] = True
    grade.loc[vazio, :] = np.nan
    return grade
