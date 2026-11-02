"""Equivalência de `var_lucro_aa`: a versão atual (réplica em listas) contra a versão antiga (pandas por entrega).

A versão antiga está copiada aqui como referência e usa as funções de `fatos.trimestres` (as que o painel usa), de
modo que qualquer divergência entre a réplica e essas funções aparece aqui. Comparação exata (`check_exact=True`,
NaN = NaN). Sem banco e sem rede.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fabrica_fundamentos import _a, balanco_de
from fabrica_precos import pregoes_uteis
from processamento.experimento.resultados import var_lucro_aa
from processamento.fatos.fundamentos import limite_do_balanco
from processamento.fatos.precos import indice_pregoes
from processamento.fatos.trimestres import ESTOQUE, FLUXO, estoques_no_fim, so_periodos_validos, trimestres_isolados

_COLUNAS_PERIODO = {"tipo_documento", "data_inicio_periodo", "data_fim_periodo"}
_COLUNAS_DA_CONTA = _COLUNAS_PERIODO | set(FLUXO) | set(ESTOQUE)
_MESES_RECORTE = 16


# --- versão antiga (referência): cópia do código anterior à réplica

def _grade_vazia(cal: list, empresas: list[str]) -> pd.DataFrame:
    return pd.DataFrame(np.nan, index=indice_pregoes(cal), columns=list(empresas), dtype=float)


def _linhas_validas(balancos: pd.DataFrame) -> pd.DataFrame:
    return so_periodos_validos(balancos[balancos["data_entrega"].notna() & balancos["data_fim_periodo"].notna()])


def _var_lucro_na_entrega_antiga(linhas: pd.DataFrame, cnpj: str, dia: pd.Timestamp) -> tuple[pd.Timestamp, float]:
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


def var_lucro_aa_antiga(balancos: pd.DataFrame, cal: list, empresas: list[str], meses_velho: int,
                        sem_balanco=()) -> pd.DataFrame:
    grade = _grade_vazia(cal, empresas)
    if not _COLUNAS_DA_CONTA <= set(balancos.columns):
        return grade
    idx = grade.index
    for cnpj, linhas in _linhas_validas(balancos).groupby("cnpj"):
        if cnpj not in grade.columns or cnpj in sem_balanco:
            continue
        entregas = pd.DatetimeIndex(linhas["data_entrega"].unique()).sort_values()
        contas = [_var_lucro_na_entrega_antiga(linhas, cnpj, dia) for dia in entregas]
        valores = np.array([v for _, v in contas], dtype=float)
        limites = pd.DatetimeIndex([limite_do_balanco(f, meses_velho) for f, _ in contas])
        pos = entregas.searchsorted(idx, side="right") - 1
        tem = pos >= 0
        coluna = np.full(len(idx), np.nan)
        coluna[tem] = valores[pos[tem]]
        coluna[tem & np.asarray(idx > limites[np.maximum(pos, 0)])] = np.nan
        grade[cnpj] = coluna
    return grade


def _compara(balancos, cal, empresas, meses_velho=15, sem_balanco=()):
    antiga = var_lucro_aa_antiga(balancos, cal, empresas, meses_velho, sem_balanco=sem_balanco)
    nova = var_lucro_aa(balancos, cal, empresas, meses_velho, sem_balanco=sem_balanco)
    pd.testing.assert_frame_equal(nova, antiga, check_exact=True)
    return nova


# --- (a) fixtures aleatórias

CAL_ALEATORIO = pregoes_uteis(1100, "2022-01-03")
EMPRESAS_ALEATORIO = [f"{k:014d}" for k in range(1, 9)] + ["00000000000010"]   # 10 não tem linha
SEM_BALANCO = {"00000000000003": "sem balanço"}


def _entrega(rng, ano: int, mes: int) -> str:
    """Entrega aleatória no mês (inclui fins de semana e dias de feriado)."""
    return (pd.Timestamp(year=ano, month=mes, day=1) + pd.Timedelta(days=int(rng.integers(0, 30)))).date().isoformat()


def _linhas_de_uma_empresa(rng) -> list[dict]:
    linhas = []

    def pl_aleatorio():
        if rng.random() < 0.05:   # PL vazio
            return None
        if rng.random() < 0.03:   # PL não positivo
            return float(rng.choice([-5.0, 0.0]))
        return float(rng.uniform(200, 1500))

    def add(tipo, ini, fim, entrega):
        lucro = None if rng.random() < 0.05 else float(rng.normal(30, 25))
        pl = pl_aleatorio()
        linha = _a(tipo, ini, fim, entrega, float(rng.uniform(100, 900)), float(rng.uniform(50, 300)), lucro, pl)
        linhas.append(linha)
        if rng.random() < 0.15:   # reapresentação: mesma conta, entrega tardia (pode mover a data)
            tarde = dict(linha)
            tarde["data_entrega"] = (pd.Timestamp(entrega) + pd.Timedelta(days=int(rng.integers(20, 300)))).date().isoformat()
            tarde["lucro_liquido"] = None if rng.random() < 0.1 else float(rng.normal(30, 25))
            linhas.append(tarde)

    for ano in range(2021, 2027):
        if rng.random() < 0.15:   # ano sem balanço: ano anterior ausente
            continue
        if rng.random() > 0.25:   # sem o 3m de T1 às vezes: o trimestre vem da diferença
            add("ITR", f"{ano}-01-01", f"{ano}-03-31", _entrega(rng, ano, 5))
        add("ITR", f"{ano}-04-01", f"{ano}-06-30", _entrega(rng, ano, 8))
        add("ITR", f"{ano}-01-01", f"{ano}-06-30", _entrega(rng, ano, 8))
        if rng.random() > 0.25:
            add("ITR", f"{ano}-07-01", f"{ano}-09-30", _entrega(rng, ano, 11))
        add("ITR", f"{ano}-01-01", f"{ano}-09-30", _entrega(rng, ano, 11))
        if ano < 2026 and rng.random() < 0.9:
            add("DFP", f"{ano}-01-01", f"{ano}-12-31", _entrega(rng, ano + 1, 3))
    if rng.random() < 0.3:   # período inválido: ITR de 12 meses, ITR de 4 meses, DFP de 9 meses
        linhas.append(_a("ITR", "2025-01-01", "2025-12-31", "2025-11-14", 1, 1, 9, 900))
    if rng.random() < 0.3:
        linhas.append(_a("ITR", "2024-01-01", "2024-04-30", "2024-05-20", 1, 1, 9, 900))
    if rng.random() < 0.3:
        linhas.append(_a("DFP", "2023-01-01", "2023-09-30", "2023-11-20", 1, 1, 9, 900))
    if rng.random() < 0.2:   # sem data de entrega: fora
        linhas.append(_a("ITR", "2023-07-01", "2023-09-30", None, 1, 1, 9, 900))
    if rng.random() < 0.2:   # outro tipo com período de 3 meses: vale como tipo classificado
        linhas.append(_a("OUTRO", "2022-07-01", "2022-09-30", "2022-11-08", 1, 1, 7, 800))
    return linhas


def _balancos_aleatorios(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    partes = [balanco_de(f"{k:014d}", _linhas_de_uma_empresa(rng)) for k in range(1, 9)]
    # empresa com linhas mas fora da lista `EMPRESAS_ALEATORIO`: não entra na grade
    partes.append(balanco_de("00000000000099", _linhas_de_uma_empresa(rng)))
    return pd.concat(partes, ignore_index=True)


@pytest.mark.parametrize("meses_velho", [15, 4])
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_var_aleatorio_igual_a_versao_antiga(seed, meses_velho):
    bal = _balancos_aleatorios(seed)
    resultado = _compara(bal, CAL_ALEATORIO, EMPRESAS_ALEATORIO, meses_velho, sem_balanco=SEM_BALANCO)
    assert resultado.notna().sum().sum() > 0   # o fixture exercita valores, não só NaN
    assert resultado["00000000000003"].isna().all()   # sem_balanco


def test_var_sem_colunas_do_contrato_tudo_nan():
    bal = _balancos_aleatorios(0).drop(columns=["lucro_liquido"])
    resultado = _compara(bal, CAL_ALEATORIO, EMPRESAS_ALEATORIO)
    assert resultado.isna().all().all()


# --- (b) casos dos gabaritos de tests/test_exp_protocolo_cde.py (mesmos dados)

LINHAS_VAR = [
    _a("ITR", "2024-07-01", "2024-09-30", "2024-11-10", 1, 1, 15, 800),
    _a("ITR", "2024-01-01", "2024-09-30", "2024-11-10", 1, 1, 50, 800),
    _a("DFP", "2024-01-01", "2024-12-31", "2025-03-20", 1, 1, 70, 850),
    _a("ITR", "2025-01-01", "2025-03-31", "2025-05-10", 1, 1, 10, 870),
    _a("ITR", "2025-07-01", "2025-09-30", "2025-11-10", 1, 1, 25, 900),
    _a("ITR", "2025-01-01", "2025-09-30", "2025-11-10", 1, 1, 60, 900),
    _a("DFP", "2025-01-01", "2025-12-31", "2026-03-20", 1, 1, 100, 1000),
    _a("ITR", "2026-01-01", "2026-03-31", "2026-05-16", 1, 1, 15, 1100),
]
CAL_VAR = pregoes_uteis(70, "2026-03-16")
CAL_LONGO = pregoes_uteis(320, "2024-11-04")


def _sem(indice):
    return [linha for i, linha in enumerate(LINHAS_VAR) if i != indice]


def _casos_gabarito():
    campos_pl = []
    for campo, valor in [("patrimonio_liquido", 0), ("patrimonio_liquido", -5), ("patrimonio_liquido", None),
                         ("lucro_liquido", None)]:
        linhas = [dict(linha) for linha in LINHAS_VAR]
        linhas[6][campo] = valor
        campos_pl.append(linhas)
    velho = [_a("ITR", "2023-07-01", "2023-09-30", "2023-11-10", 1, 1, 5, 100),
             _a("ITR", "2024-07-01", "2024-09-30", "2024-11-10", 1, 1, 8, 100)]
    invalido = _a("ITR", "2026-01-01", "2026-12-31", "2026-03-18", 1, 1, 999, 1)
    futura = _a("ITR", "2026-04-01", "2026-06-30", "2026-07-20", 1, 1, 500, 5)
    banco = [dict(linha, receita_liquida=None, lucro_bruto=None) for linha in LINHAS_VAR]
    lucro_vazio_no_3m = [dict(linha) for linha in LINHAS_VAR]
    lucro_vazio_no_3m[7]["lucro_liquido"] = None
    return [
        ("base", LINHAS_VAR, CAL_VAR, {}),
        ("sem_dfp_2024", _sem(2), CAL_VAR, {}),
        ("sem_9m_2024", _sem(1), CAL_VAR, {}),
        ("sem_9m_2025", _sem(5), CAL_VAR, {}),
        ("sem_dfp_2025", _sem(6), CAL_VAR, {}),
        ("periodo_invalido", LINHAS_VAR + [invalido], CAL_VAR, {}),
        ("pl_zero", campos_pl[0], CAL_VAR, {}),
        ("pl_negativo", campos_pl[1], CAL_VAR, {}),
        ("pl_vazio", campos_pl[2], CAL_VAR, {}),
        ("lucro_vazio", campos_pl[3], CAL_VAR, {}),
        ("balanco_velho", velho, CAL_LONGO, {}),
        ("entrega_futura", LINHAS_VAR + [futura], CAL_VAR, {}),
        ("sem_balanco", LINHAS_VAR, CAL_VAR, {"sem_balanco": {"1": "x"}}),
        ("banco_sem_receita", banco, CAL_VAR, {}),
        ("lucro_3m_vazio_usa_diferenca", lucro_vazio_no_3m, CAL_VAR, {}),
    ]


_CASOS = _casos_gabarito()


@pytest.mark.parametrize("caso", _CASOS, ids=[c[0] for c in _CASOS])
def test_var_gabaritos_iguais_a_versao_antiga(caso):
    _nome, linhas, cal, kw = caso
    _compara(balanco_de("1", linhas), cal, ["1"], 15, **kw)


def test_var_entrega_em_sabado_e_depois_do_calendario_iguais_a_versao_antiga():
    sabado = _a("ITR", "2026-04-01", "2026-06-30", "2026-06-13", 1, 1, 9, 300)
    depois = _a("ITR", "2026-04-01", "2026-06-30", "2026-07-26", 1, 1, 11, 300)
    _compara(balanco_de("1", LINHAS_VAR + [sabado, depois]), CAL_VAR, ["1"])
