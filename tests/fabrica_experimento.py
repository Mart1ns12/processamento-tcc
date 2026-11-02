"""Fábrica de dados para o dataset do experimento (tests/test_exp_dataset.py e test_vazamento_experimento.py).

Tickers fictícios (AAAA3 etc.), séries geradas com numpy. Os nomes de colunas são os de
`fontes.ler_tabela` (precos, cadastro, balancos) e `fontes.ler_noticias` (noticias). Nenhuma
função usa banco ou rede.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from fabrica_precos import cadastro_de, indices_de, precos_de, pregoes_uteis, serie_por_retornos
from processamento import calendario, fontes
from processamento.exclusoes import Exclusoes
from processamento.experimento.dataset import DadosExperimento
from processamento.universo import montar_universo

SP = ZoneInfo("America/Sao_Paulo")
N_MUNDO = 300
T_INDICE = 260

CADASTRO_MUNDO = cadastro_de([
    ("AAAA3", "1", "S1", "ON"),
    ("AAAA4", "1", "S1", "PN"),
    ("BBBB3", "2", "S1", "ON"),
    ("CCCC3", "3", "S1", "ON"),
    ("DDDD3", "4", "S2", "ON"),
])
TICKERS_MUNDO = ["AAAA3", "AAAA4", "BBBB3", "CCCC3", "DDDD3"]
INDICES_MUNDO = ["IBOV", "USDBRL", "BRENT"]

CADASTRO_INTEGRACAO = cadastro_de([
    ("AAAA3", "1", "S1", "ON"),
    ("AAAA4", "1", "S1", "PN"),
    ("BBBB3", "2", "S1", "ON"),
    ("BDRX34", "4", "S2", "BDR"),
    ("CRFB3", "3", "S2", "ON"),
])
EXCLUSOES_INTEGRACAO = Exclusoes(tickers_excluidos={"CRFB3": "teste"})


def _instante(dia, hora: str) -> pd.Timestamp:
    """Instante de São Paulo: `dia` às `hora` ("HH:MM" ou "HH:MM:SS")."""
    return pd.Timestamp(f"{pd.Timestamp(dia):%Y-%m-%d} {hora}").tz_localize(SP)


def noticias_de(linhas: list[tuple], campos: dict | None = None) -> pd.DataFrame:
    """Linhas de `fontes.ler_noticias`, a partir de (id, ticker, instante, dia, pp, pn, origem, papel, tipo).

    `instante` é `data_hora_publicacao` (SP) ou None (sem hora). `momento_ref` segue `ler_noticias`:
    a hora, ou 23:59:59 do dia de publicação. Depois, `fontes.aplicar_regra_so_data` (como na leitura
    real): 04:00 ou 05:00 de SP vira "só data" (meia-noite do Pacífico).
    `campos` (id -> dict com `titulo`, `link`, `resolved_url`) troca o título padrão ("titulo <id>") e
    preenche as URLs; sem ele, `link` e `resolved_url` ficam nulos.
    """
    registros = []
    for id_, ticker, instante, dia, pp, pn, origem, papel, tipo in linhas:
        data_pub = pd.Timestamp(dia).normalize()
        fim_do_dia = data_pub.tz_localize(SP) + pd.Timedelta(hours=23, minutes=59, seconds=59)
        extra = (campos or {}).get(id_, {})
        registros.append({
            "id": id_,
            "ticker": ticker,
            "data_hora_publicacao": instante,
            "data_publicacao": data_pub,
            "momento_ref": fim_do_dia if instante is None else instante,
            "titulo": extra.get("titulo", f"titulo {id_}"),
            "link": extra.get("link"),
            "resolved_url": extra.get("resolved_url"),
            "prob_positivo": float(pp),
            "prob_neutro": 1.0 - float(pp) - float(pn),
            "prob_negativo": float(pn),
            "origem": origem,
            "papel": papel,
            "tipo_conteudo": tipo,
        })
    df = pd.DataFrame(registros)
    for coluna in ("data_hora_publicacao", "momento_ref"):
        df[coluna] = pd.to_datetime(df[coluna], utc=True).dt.tz_convert(SP)
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"])
    return fontes.aplicar_regra_so_data(df)


def dados_de(
    cal: list,
    precos: pd.DataFrame,
    cadastro: pd.DataFrame,
    noticias: pd.DataFrame,
    balancos: pd.DataFrame,
    exclusoes: Exclusoes | None = None,
    mudancas: dict | None = None,
    indices: pd.DataFrame | None = None,
) -> DadosExperimento:
    """`DadosExperimento` com o universo refeito para estes preços e este calendário."""
    universo = montar_universo(list(cal), cadastro, precos, exclusoes or Exclusoes())
    return DadosExperimento(
        precos=precos,
        cadastro=cadastro,
        noticias=noticias,
        balancos=balancos,
        universo=universo,
        mudancas=mudancas or {},
        indices=indices,
    )


# ---------------------------------------------------------------- mundo de 300 pregões (vazamento)


def _precos_do_mundo(cal: list, rng: np.random.Generator) -> pd.DataFrame:
    """Preços de cada ação e dos índices (IBOV, USDBRL, BRENT) em todos os pregões de `cal`."""
    partes = []
    for ticker in TICKERS_MUNDO + INDICES_MUNDO:
        n = len(cal)
        aj = serie_por_retornos(100.0, rng.normal(0, 0.015, n - 1).tolist())
        fech = aj if ticker in INDICES_MUNDO else [x * 1.05 for x in aj]
        ruido = rng.normal(0, 0.005, n)
        abertura = [f * (1 + r) for f, r in zip(fech, ruido)]
        maxima = [max(a, f) * (1 + abs(r)) for a, f, r in zip(abertura, fech, ruido)]
        minima = [min(a, f) * (1 - abs(r)) for a, f, r in zip(abertura, fech, ruido)]
        volume = rng.integers(1000, 5000, size=n).tolist()
        parte = precos_de(ticker, cal, fech, aj, volume)
        parte["abertura"] = abertura
        parte["maxima"] = maxima
        parte["minima"] = minima
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def _noticias_do_mundo(cal: list, t, t1, rng: np.random.Generator) -> pd.DataFrame:
    """Notícias aleatórias (11:00, 19:00, 07:00 e 08:00:01 do dia seguinte), um cvm_ipe sem hora a
    cada 20 pregões e as notícias fixas de t e t1 (f4 é "só data" de t1, às 04:00 SP)."""
    linhas = []
    n = len(cal)

    def nova(ticker, instante, dia, origem="google_news", papel=None, tipo="reportagem"):
        pp = rng.uniform(0.0, 1.0)
        pn = rng.uniform(0.0, 1.0 - pp)
        linhas.append((f"r{len(linhas)}", ticker, instante, dia, pp, pn, origem, papel, tipo))

    papeis = ["protagonista", "mencao", "citada_com_fato"]
    for i in range(n):
        for ticker in TICKERS_MUNDO:
            if rng.random() < 0.5:
                nova(ticker, _instante(cal[i], "11:00"), cal[i], papel=papeis[rng.integers(3)])
            if rng.random() < 0.5:
                nova(ticker, _instante(cal[i], "19:00"), cal[i], papel=papeis[rng.integers(3)])
            if i + 1 < n and rng.random() < 0.3:
                nova(ticker, _instante(cal[i + 1], "07:00"), cal[i + 1], papel=papeis[rng.integers(3)])
            if i + 1 < n and rng.random() < 0.3:
                nova(ticker, _instante(cal[i + 1], "08:00:01"), cal[i + 1], papel=papeis[rng.integers(3)])
        if i % 20 == 10:
            nova("AAAA3", None, cal[i], origem="cvm_ipe", papel="protagonista", tipo="comunicado")

    fixas = [
        ("f1", "AAAA3", _instante(t, "19:00"), t, 0.6, 0.2),
        ("f2", "AAAA3", _instante(t1, "08:00:00"), t1, 0.5, 0.3),
        ("f3", "AAAA3", _instante(t1, "08:00:01"), t1, 0.4, 0.4),
        # "só data" de t1 (04:00 SP = 00:00 PDT, horário de verão de 2026-06-02): vai para o dia de t1
        ("f4", "AAAA3", _instante(t1, "04:00:00"), t1, 0.7, 0.1),
    ]
    for id_, ticker, instante, dia, pp, pn in fixas:
        linhas.append((id_, ticker, instante, dia, pp, pn, "google_news", "protagonista", "reportagem"))
    return noticias_de(linhas)


def _indices_do_mundo(cal: list) -> pd.DataFrame:
    """SMLL em todos os pregões de `cal` (rng próprio: não muda os preços nem as notícias do mundo)."""
    rng = np.random.default_rng(8)
    serie = serie_por_retornos(1000.0, rng.normal(0, 0.012, len(cal) - 1).tolist())
    return indices_de([(d.isoformat(), "SMLL", v) for d, v in zip(cal, serie)])


def _balancos_do_mundo(cal: list) -> pd.DataFrame:
    """Balanços do CNPJ "1" (cal[5]) e do CNPJ "2" (cal[200]); todos antes de t."""
    return pd.DataFrame({
        "cnpj": ["1", "2"],
        "tipo": ["ITR", "ITR"],
        "data_entrega": [pd.Timestamp(cal[5]), pd.Timestamp(cal[200])],
    })


def mundo() -> dict:
    """Mundo de 300 pregões (a partir de 2025-06-02) com preços, notícias, balanços e índices (SMLL).

    Devolve `cal`, `precos`, `noticias`, `balancos`, `indices`, `t` (cal[260]) e `t1` (cal[261]).
    """
    rng = np.random.default_rng(7)
    cal = pregoes_uteis(N_MUNDO, "2025-06-02")
    t, t1 = cal[T_INDICE], cal[T_INDICE + 1]
    precos = _precos_do_mundo(cal, rng)
    noticias = _noticias_do_mundo(cal, t, t1, rng)
    return {
        "cal": cal,
        "precos": precos,
        "noticias": noticias,
        "balancos": _balancos_do_mundo(cal),
        "indices": _indices_do_mundo(cal),
        "t": t,
        "t1": t1,
    }


def cortado(m: dict) -> dict:
    """Só o que se saberia no fim de t (preços, balanços e índices até t; notícias até 08:00 de t1)."""
    t, t1 = m["t"], m["t1"]
    corte_t = pd.Timestamp(t)
    corte_noticia = calendario.corte_manha(t1)
    precos = m["precos"][m["precos"]["data"] <= corte_t].reset_index(drop=True)
    noticias = m["noticias"][m["noticias"]["momento_ref"] <= corte_noticia].reset_index(drop=True)
    balancos = m["balancos"][m["balancos"]["data_entrega"] <= corte_t].reset_index(drop=True)
    indices = m["indices"][m["indices"]["data"] <= corte_t].reset_index(drop=True)
    cal = [d for d in m["cal"] if d <= t]
    return {"cal": cal, "precos": precos, "noticias": noticias, "balancos": balancos, "indices": indices}


def alterado(m: dict) -> dict:
    """Mundo cheio com o futuro de t alterado: preços após t ×3 (volume ×10, índices inclusos),
    SMLL após t ×3, notícias após 08:00 de t1 com pp e pn trocados, notícias novas às 08:00:01 de t1,
    um cvm_ipe datado de t1 e um balanço do CNPJ "1" entregue em t1."""
    t, t1 = m["t"], m["t1"]
    corte_t = pd.Timestamp(t)
    precos = m["precos"].copy()
    depois = precos["data"] > corte_t
    colunas_preco = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"]
    precos.loc[depois, colunas_preco] = precos.loc[depois, colunas_preco] * 3
    precos.loc[depois, "volume"] = precos.loc[depois, "volume"] * 10
    indices = m["indices"].copy()
    linhas_smll = (indices["data"] > corte_t) & (indices["indice"] == "SMLL")
    indices.loc[linhas_smll, "valor"] = indices.loc[linhas_smll, "valor"] * 3

    noticias = m["noticias"].copy()
    trocar = noticias["momento_ref"] > calendario.corte_manha(t1)
    # Atribuição com .to_numpy(): sem ele o pandas alinha pelo nome das colunas e não troca nada.
    noticias.loc[trocar, ["prob_positivo", "prob_negativo"]] = noticias.loc[
        trocar, ["prob_negativo", "prob_positivo"]
    ].to_numpy()
    novas = [
        (f"n-{ticker}", ticker, _instante(t1, "08:00:01"), t1, 0.9, 0.05, "google_news", "protagonista", "reportagem")
        for ticker in TICKERS_MUNDO
    ]
    novas.append(("cvm-t1", "AAAA3", None, t1, 0.5, 0.2, "cvm_ipe", "protagonista", "comunicado"))
    noticias = pd.concat([noticias, noticias_de(novas)], ignore_index=True)

    balancos = pd.concat(
        [m["balancos"], pd.DataFrame({"cnpj": ["1"], "tipo": ["ITR"], "data_entrega": [pd.Timestamp(t1)]})],
        ignore_index=True,
    )
    return {"cal": m["cal"], "precos": precos, "noticias": noticias, "balancos": balancos, "indices": indices}


def em_t(m: dict, indice: int) -> dict:
    """Cópia de `m` com t = cal[indice] e t1 = cal[indice + 1]: o mesmo mundo, outro dia de corte."""
    return {**m, "t": m["cal"][indice], "t1": m["cal"][indice + 1]}


def sem_pregao(m: dict, dia) -> dict:
    """Cópia de `m` sem o pregão `dia` (feriado): sai de cal, de precos e das notícias datadas nele."""
    d = pd.Timestamp(dia)
    return {
        **m,
        "cal": [x for x in m["cal"] if x != dia],
        "precos": m["precos"][m["precos"]["data"] != d].reset_index(drop=True),
        "noticias": m["noticias"][m["noticias"]["data_publicacao"] != d].reset_index(drop=True),
    }


def so_t1_alterado(m: dict) -> dict:
    """Só os preços de t+1 mudam (×1.05, todos menos IBOV). Volumes e notícias ficam iguais.

    Nas linhas de t só as colunas de alvo podem mudar (ret_t1, alvo, alvo_abertura...). ×1.05 é
    pequeno de propósito: um salto de ×3 cairia no retorno suspeito e zeraria o alvo. O SMLL de t+1 também ×1.05.
    """
    t1 = pd.Timestamp(m["t1"])
    precos = m["precos"].copy()
    mascara = (precos["data"] == t1) & (precos["ticker"] != "IBOV")
    colunas_preco = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"]
    precos.loc[mascara, colunas_preco] = precos.loc[mascara, colunas_preco] * 1.05
    indices = m["indices"].copy()
    linhas_smll = (indices["data"] == t1) & (indices["indice"] == "SMLL")
    indices.loc[linhas_smll, "valor"] = indices.loc[linhas_smll, "valor"] * 1.05
    return {"cal": m["cal"], "precos": precos, "noticias": m["noticias"], "balancos": m["balancos"],
            "indices": indices}


def depois_de_t1_alterado(m: dict) -> dict:
    """Preços, volumes e SMLL de todas as datas depois de t+1 mudam (×3 e ×10, como em `alterado`).

    As linhas de t, inclusive as colunas de alvo, têm de ficar iguais: o alvo olha só t+1.
    """
    t1 = pd.Timestamp(m["t1"])
    precos = m["precos"].copy()
    depois = precos["data"] > t1
    colunas_preco = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"]
    precos.loc[depois, colunas_preco] = precos.loc[depois, colunas_preco] * 3
    precos.loc[depois, "volume"] = precos.loc[depois, "volume"] * 10
    indices = m["indices"].copy()
    linhas_smll = (indices["data"] > t1) & (indices["indice"] == "SMLL")
    indices.loc[linhas_smll, "valor"] = indices.loc[linhas_smll, "valor"] * 3
    return {"cal": m["cal"], "precos": precos, "noticias": m["noticias"], "balancos": m["balancos"],
            "indices": indices}


def mexer_no_futuro(m, *, so_t1=False, acoes_preco=1.0, acoes_volume=1.0, smll=1.0, ibov=1.0) -> dict:
    """Multiplica só depois de t (ou só em t+1). Ações, IBOV e SMLL são independentes."""
    t, t1 = pd.Timestamp(m["t"]), pd.Timestamp(m["t1"])
    alvo = (lambda d: d == t1) if so_t1 else (lambda d: d > t)
    colunas = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"]
    precos = m["precos"].copy()
    futuro, acao = alvo(precos["data"]), precos["ticker"].isin(TICKERS_MUNDO)
    precos.loc[futuro & acao, colunas] = precos.loc[futuro & acao, colunas] * acoes_preco
    precos.loc[futuro & acao, "volume"] = precos.loc[futuro & acao, "volume"] * acoes_volume
    e_ibov = precos["ticker"] == "IBOV"
    precos.loc[futuro & e_ibov, colunas] = precos.loc[futuro & e_ibov, colunas] * ibov
    indices = m["indices"].copy()
    linhas = alvo(indices["data"]) & (indices["indice"] == "SMLL")
    indices.loc[linhas, "valor"] = indices.loc[linhas, "valor"] * smll
    return {**m, "precos": precos, "indices": indices}


# ---------------------------------------------------------- mundo pequeno com casos exatos (integração)


def integracao() -> dict:
    """30 pregões a partir de 2026-05-04, com ações AAAA3, AAAA4 (CNPJ 1), BBBB3 (CNPJ 2, sem preço
    em cal[10]), BDRX34 (BDR) e CRFB3 (excluída). BDRX34 e CRFB3 sobem 50% em cal[15].

    Notícias: BBBB3 sem hora em cal[3] (cvm_ipe) e AAAA4 às 19:00 de cal[20] (sem papel).
    Balanço do CNPJ "1" com entrega em cal[5].
    """
    rng = np.random.default_rng(3)
    cal = pregoes_uteis(30, "2026-05-04")
    partes = []
    for ticker in ["AAAA3", "AAAA4", "BBBB3", "BDRX34", "CRFB3", "IBOV", "USDBRL", "BRENT"]:
        rets = rng.normal(0, 0.02, len(cal) - 1).tolist()
        if ticker in ("BDRX34", "CRFB3"):
            rets[14] = 0.5
        aj = serie_por_retornos(100.0, rets)
        datas, precos_ = list(cal), aj
        if ticker == "BBBB3":
            datas = [d for i, d in enumerate(cal) if i != 10]
            precos_ = [p for i, p in enumerate(aj) if i != 10]
        partes.append(precos_de(ticker, datas, precos_, precos_, [1000] * len(datas)))
    precos = pd.concat(partes, ignore_index=True)

    noticias = noticias_de([
        ("c3", "BBBB3", None, cal[3], 0.5, 0.2, "cvm_ipe", "protagonista", "comunicado"),
        ("a20", "AAAA4", _instante(cal[20], "19:00"), cal[20], 0.7, 0.1, "google_news", None, "reportagem"),
    ])
    balancos = pd.DataFrame({"cnpj": ["1"], "tipo": ["ITR"], "data_entrega": [pd.Timestamp(cal[5])]})
    return {"cal": cal, "precos": precos, "noticias": noticias, "balancos": balancos}
