"""Lacunas nas séries de preços e índices (nota do diagnóstico; seção 6 da especificação, "Base velha"),
e meses com poucas notícias (`secao_noticias_por_mes`).

Só notas e tabelas (não é divergência). Lê só por `fontes.ler_tabela` / `fontes.ler_noticias` (camada de leitura, sessão só leitura).
"""

from __future__ import annotations

from datetime import date
from statistics import median

import pandas as pd

from processamento import calendario, fontes
from processamento.diagnostico.regras import adicionar_tabela, nova_secao
from processamento.diagnostico.temas import _existe, _pulada
from processamento.experimento.parametros import carregar_parametros_experimento
from processamento.fatos.precos import carregar_parametros_precos

INDICES_PREGOES = ("CDI", "IDIV", "IFIX", "SMLL")   # ordem da tabela (alfabética); o IPCA vem por último, em meses
COLUNAS = ["serie", "inicio", "fim", "tamanho", "unidade"]
REGRA_INDICES = ("IDIV, SMLL e IFIX: mais de {n} pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e "
                 "mais de {n} no fim; IPCA: meses faltando e atraso de mais de {m} meses no fim")
REFERENCIA_NOTICIAS = 12        # meses anteriores que formam a mediana de referência
MINIMO_REFERENCIA_NOTICIAS = 6  # abaixo disso o mês não é avaliado
COLUNAS_NOTICIAS = ["mes", "artigos", "mediana_referencia", "situacao"]


def lacunas_em_pregoes(datas_com_valor, cal: list, minimo: int,
                       minimo_fim: int | None = None) -> list[tuple[date, date, int]]:
    """Trechos de pregões de `cal` sem valor: (1º pregão sem valor, último, nº de pregões).

    No meio (entre o 1º e o último pregão com valor): só trechos com mais de `minimo` pregões. Com `minimo_fim`,
    também o trecho final (depois do último valor até o último pregão de `cal`) se tiver mais de `minimo_fim`.
    Começo tardio não é lacuna. Datas fora de `cal` são ignoradas. Sem valor: [].
    """
    cal = [pd.Timestamp(d).date() for d in cal]
    tem = {pd.Timestamp(d).date() for d in datas_com_valor}
    pos = [i for i, d in enumerate(cal) if d in tem]
    if not pos:
        return []
    res = []
    i = pos[0]
    while i <= pos[-1]:
        if cal[i] in tem:
            i += 1
            continue
        j = i
        while cal[j + 1] not in tem:   # termina: cal[pos[-1]] tem valor
            j += 1
        if j - i + 1 > minimo:
            res.append((cal[i], cal[j], j - i + 1))
        i = j + 1
    final = len(cal) - 1 - pos[-1]
    if minimo_fim is not None and final > minimo_fim:
        res.append((cal[pos[-1] + 1], cal[-1], final))
    return res


def lacunas_em_meses(meses, ate: pd.Period | None = None) -> list[tuple[str, str, int]]:
    """Trechos de meses sem valor entre o 1º e o último mês conhecidos ("AAAA-MM", "AAAA-MM", nº de meses).

    Com `ate`: também do mês seguinte ao último conhecido até `ate` (inclusive), se `ate` passa do último.
    """
    ms = sorted({pd.Period(m, "M") for m in meses})
    if not ms:
        return []
    res = [(str(a + 1), str(b - 1), (b - a).n - 1) for a, b in zip(ms[:-1], ms[1:]) if (b - a).n > 1]
    if ate is not None and ate > ms[-1]:
        res.append((str(ms[-1] + 1), str(ate), (ate - ms[-1]).n))
    return res


def secao_lacunas(ler, mapa: dict, existentes: set) -> dict:
    """Lacunas de v1-precos (por ticker) e de v1-indices (IDIV, SMLL, IFIX e CDI em pregões; IPCA em meses)."""
    secao = nova_secao("Lacunas nas séries de preços e índices")
    if not _existe(mapa, existentes, "precos"):
        secao["notas"].append(_pulada(mapa, "precos"))
        return secao
    params = carregar_parametros_precos()
    n, m = params.base_defasagem_max_pregoes, params.ipca_defasagem_max_meses
    precos = fontes.ler_tabela("precos", ler=ler)
    cal = calendario.pregoes(precos)
    if not cal:
        secao["notas"].append("sem pregão com preço do IBOV: checagem não feita")
        return secao

    validos = precos.dropna(subset=["fechamento_ajustado"])
    linhas = []
    for tk, grupo in validos.groupby("ticker", sort=True):
        if tk == "IBOV":
            continue
        for ini, fim, tam in lacunas_em_pregoes(pd.to_datetime(grupo["data"]).dt.date, cal, n):
            linhas.append([tk, ini.isoformat(), fim.isoformat(), tam, "pregões"])
    regra = "fechamento_ajustado, só dentro do período com preço de cada ticker"
    if linhas:
        secao["notas"].append(
            f"{len(linhas)} lacunas de mais de {n} pregões em {len({l[0] for l in linhas})} tickers de v1-precos "
            f"({regra}): as janelas com base dentro delas saem historico_insuficiente "
            f"(fase1.base_defasagem_max_pregoes = {n})")
        adicionar_tabela(secao, f"Lacunas em v1-precos (mais de {n} pregões)", COLUNAS, linhas)
    else:
        secao["notas"].append(f"nenhuma lacuna de mais de {n} pregões em v1-precos ({regra})")

    if not _existe(mapa, existentes, "indices"):
        secao["notas"].append(_pulada(mapa, "indices"))
        return secao
    indices = fontes.ler_tabela("indices", ler=ler).dropna(subset=["valor"])
    linhas = []
    for nome in INDICES_PREGOES:
        datas = pd.to_datetime(indices.loc[indices["indice"] == nome, "data"]).dt.date
        for ini, fim, tam in lacunas_em_pregoes(datas, cal, 0 if nome == "CDI" else n, minimo_fim=n):
            linhas.append([nome, ini.isoformat(), fim.isoformat(), tam, "pregões"])
    meses = pd.to_datetime(indices.loc[indices["indice"] == "IPCA", "data"]).dt.to_period("M")
    for ini, fim, tam in lacunas_em_meses(meses, pd.Timestamp(cal[-1]).to_period("M") - m):
        linhas.append(["IPCA", ini, fim, tam, "meses"])
    regra = REGRA_INDICES.format(n=n, m=m)
    if linhas:
        secao["notas"].append(f"{len(linhas)} lacunas em v1-indices ({regra})")
        adicionar_tabela(secao, "Lacunas em v1-indices", COLUNAS, linhas)
    else:
        secao["notas"].append(f"nenhuma lacuna em v1-indices ({regra})")
    return secao


def _sobrepoe(mes: pd.Period, periodos) -> bool:
    """Diz se o mês cruza algum período de `periodos` (datas inclusivas)."""
    ini, fim = mes.start_time.date(), mes.end_time.date()
    return any(ini <= p_fim and fim >= p_ini for p_ini, p_fim in periodos)


def _avaliar_meses_noticias(contagem: dict, fracao: float, periodos, referencia: int,
                            minimo_referencia: int) -> tuple[list[dict], list[str], int]:
    """Núcleo de `meses_com_poucas_noticias`: devolve (meses baixos, meses do período sem baixa, nº avaliado)."""
    if not contagem:
        return [], [], 0
    ms = sorted(pd.Period(m, "M") for m in contagem)
    todos = pd.period_range(ms[0], ms[-1], freq="M")
    baixos, rever, avaliados = [], [], 0
    usaveis: list[int] = []   # artigos dos meses de referência (não baixos e fora do período), em ordem
    for mes in todos[:-1]:   # o último mês da contagem é incompleto: não avalia nem entra na referência
        rotulo = str(mes)
        artigos = contagem.get(rotulo, 0)
        do_periodo = _sobrepoe(mes, periodos)
        ref = usaveis[-referencia:]
        if len(ref) < minimo_referencia:
            if not do_periodo:
                usaveis.append(artigos)
            continue
        avaliados += 1
        mediana = median(ref)
        if artigos < fracao * mediana:
            situacao = "cadastrado" if do_periodo else "rever: fora de periodos_sem_coleta"
            mediana_ref = int(mediana) if mediana == int(mediana) else round(mediana, 1)
            baixos.append({"mes": rotulo, "artigos": artigos, "mediana_referencia": mediana_ref,
                           "situacao": situacao})
        elif do_periodo:
            rever.append(rotulo)
        else:
            usaveis.append(artigos)
    return baixos, rever, avaliados


def meses_com_poucas_noticias(contagem: dict[str, int], fracao: float, periodos: tuple[tuple[date, date], ...],
                              referencia: int = REFERENCIA_NOTICIAS,
                              minimo_referencia: int = MINIMO_REFERENCIA_NOTICIAS) -> tuple[list[dict], list[str]]:
    """Meses com poucas notícias e meses do período que não ficaram baixos.

    `contagem`: "AAAA-MM" -> artigos distintos. O último mês da contagem é incompleto: não é avaliado. Meses
    ausentes entre o 1º e o último valem 0. Referência de um mês: até `referencia` meses anteriores que não são
    baixos nem do período; com menos de `minimo_referencia`, o mês não é avaliado. Baixo: artigos < fracao × mediana.
    Devolve (linhas dos baixos: mes, artigos, mediana_referencia, situacao; "AAAA-MM" do período sem baixa, com
    referência suficiente, que sugere rever `periodos_sem_coleta`).
    """
    baixos, rever, _ = _avaliar_meses_noticias(contagem, fracao, periodos, referencia, minimo_referencia)
    return baixos, rever


def secao_noticias_por_mes(ler, mapa: dict, existentes: set) -> dict:
    """Meses com poucas notícias (nota e tabela; nunca divergência). Parâmetros em `experimento` (parametros.yaml)."""
    secao = nova_secao("Notícias por mês")
    if not _existe(mapa, existentes, "noticias"):
        secao["notas"].append(_pulada(mapa, "noticias"))
        return secao
    params = carregar_parametros_experimento()
    fracao = params.noticias_mes_fracao_minima
    noticias = fontes.ler_noticias(ler=ler)
    meses = pd.to_datetime(noticias["data_publicacao"], errors="coerce").dt.to_period("M")
    validos = pd.DataFrame({"mes": meses, "id": noticias["id"]}).dropna(subset=["mes"])
    contagem = {str(m): int(n) for m, n in validos.groupby("mes")["id"].nunique().items()}
    baixos, rever, avaliados = _avaliar_meses_noticias(
        contagem, fracao, params.periodos_sem_coleta, REFERENCIA_NOTICIAS, MINIMO_REFERENCIA_NOTICIAS)
    limite = f"{fracao * 100:g}%"
    secao["notas"].append(
        f"{avaliados} meses avaliados (mês abaixo de {limite} da mediana dos até {REFERENCIA_NOTICIAS} meses "
        f"anteriores; o último mês da coleta fica de fora por estar incompleto)")
    if baixos:
        adicionar_tabela(secao, "Meses com poucas notícias", COLUNAS_NOTICIAS,
                         [[l[c] for c in COLUNAS_NOTICIAS] for l in baixos])
    else:
        secao["notas"].append(f"nenhum mês abaixo de {limite} da mediana dos meses anteriores")
    fora = sum(1 for l in baixos if l["situacao"].startswith("rever: fora"))
    if fora:
        secao["notas"].append(
            f"Atenção: {fora} mês(es) com poucas notícias fora de experimento.periodos_sem_coleta: rever o parâmetro.")
    if rever:
        secao["notas"].append(
            f"Atenção: período sem coleta com notícias normais em {', '.join(rever)}: a coleta pode ter preenchido; "
            f"rever experimento.periodos_sem_coleta.")
    return secao
