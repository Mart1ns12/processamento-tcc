"""Indicadores de preço, volume e comparações (seção 5 da especificação).

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Ausência é NaN + `status` (nunca 0). `fechamento` é cotação; `fechamento_ajustado` é rentabilidade.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from processamento import calendario
from processamento.exclusoes import Exclusoes
from processamento.universo import TIPOS_ACEITOS

OK = "ok"
INDISPONIVEL = "indisponivel"
HIST = "historico_insuficiente"
NAO_SE_APLICA = "nao_se_aplica"

_CHAVES_FASE1 = {
    "janelas",
    "volume_pregoes",
    "volatilidade_retornos",
    "beta_pregoes",
    "beta_minimo",
    "setor_minimo",
    "setor_excluir",
    "retorno_suspeito_min",
    "retorno_suspeito_max",
    "retorno_suspeito_pregoes_nivel",
    "base_defasagem_max_pregoes",
    "ipca_defasagem_max_meses",
}
_SETOR_EXCLUIR = ("acao", "empresa")


class ErroParametrosPrecos(Exception):
    """Bloco `fase1` inválido ou ausente (a mensagem diz o que corrigir)."""


@dataclass(frozen=True)
class ParametrosPrecos:
    """Parâmetros da fase 1 (bloco `fase1` de config/parametros.yaml)."""

    janelas: dict[str, int]
    volume_pregoes: int
    volatilidade_retornos: int
    beta_pregoes: int
    beta_minimo: int
    setor_minimo: int
    setor_excluir: str
    retorno_suspeito_min: float = -0.75
    retorno_suspeito_max: float = 1.0
    retorno_suspeito_pregoes_nivel: int = 21
    base_defasagem_max_pregoes: int = 5
    ipca_defasagem_max_meses: int = 2


def _inteiro_positivo(valor: object, onde: str) -> int:
    """Confere um inteiro > 0 (bool não conta); levanta `ErroParametrosPrecos` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ErroParametrosPrecos(f"{onde} deve ser um inteiro maior que zero (recebeu {valor!r})")
    return valor


def _inteiro_nao_negativo(valor: object, onde: str) -> int:
    """Confere um inteiro >= 0 (bool não conta); levanta `ErroParametrosPrecos` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroParametrosPrecos(f"{onde} deve ser um inteiro maior ou igual a zero (recebeu {valor!r})")
    return valor


def _numero(valor: object, onde: str) -> float:
    """Confere um número finito (bool não conta); levanta `ErroParametrosPrecos` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not np.isfinite(valor):
        raise ErroParametrosPrecos(f"{onde} deve ser um número (recebeu {valor!r})")
    return float(valor)


def carregar_parametros_precos(caminho: str | None = None) -> ParametrosPrecos:
    """Lê o bloco `fase1` (do caminho dado ou do parametros.yaml) e valida cada chave."""
    bloco = calendario.carregar_parametros(caminho).get("fase1")
    if not isinstance(bloco, dict):
        raise ErroParametrosPrecos("falta o bloco fase1 no arquivo de parâmetros")
    desconhecidas = set(bloco) - _CHAVES_FASE1
    if desconhecidas:
        raise ErroParametrosPrecos(f"chave desconhecida no bloco fase1: {sorted(desconhecidas)}")
    faltantes = _CHAVES_FASE1 - set(bloco)
    if faltantes:
        raise ErroParametrosPrecos(f"faltam chaves no bloco fase1: {sorted(faltantes)}")

    janelas = bloco["janelas"]
    if not isinstance(janelas, dict) or not janelas:
        raise ErroParametrosPrecos("fase1.janelas deve ser um mapeamento não vazio (ex.: d1: 1)")
    for nome, n in janelas.items():
        if not isinstance(nome, str):
            raise ErroParametrosPrecos(f"nome de janela inválido em fase1.janelas: {nome!r}")
        _inteiro_positivo(n, f"fase1.janelas.{nome}")

    minimo = _numero(bloco["retorno_suspeito_min"], "fase1.retorno_suspeito_min")
    if not -1 < minimo < 0:
        raise ErroParametrosPrecos(f"fase1.retorno_suspeito_min deve ficar entre -1 e 0 (recebeu {minimo!r})")
    maximo = _numero(bloco["retorno_suspeito_max"], "fase1.retorno_suspeito_max")
    if not maximo > 0:
        raise ErroParametrosPrecos(f"fase1.retorno_suspeito_max deve ser maior que zero (recebeu {maximo!r})")

    params = ParametrosPrecos(
        janelas=dict(janelas),
        volume_pregoes=_inteiro_positivo(bloco["volume_pregoes"], "fase1.volume_pregoes"),
        volatilidade_retornos=_inteiro_positivo(bloco["volatilidade_retornos"], "fase1.volatilidade_retornos"),
        beta_pregoes=_inteiro_positivo(bloco["beta_pregoes"], "fase1.beta_pregoes"),
        beta_minimo=_inteiro_positivo(bloco["beta_minimo"], "fase1.beta_minimo"),
        setor_minimo=_inteiro_positivo(bloco["setor_minimo"], "fase1.setor_minimo"),
        setor_excluir=bloco["setor_excluir"],
        retorno_suspeito_min=minimo,
        retorno_suspeito_max=maximo,
        retorno_suspeito_pregoes_nivel=_inteiro_positivo(
            bloco["retorno_suspeito_pregoes_nivel"], "fase1.retorno_suspeito_pregoes_nivel"
        ),
        base_defasagem_max_pregoes=_inteiro_nao_negativo(
            bloco["base_defasagem_max_pregoes"], "fase1.base_defasagem_max_pregoes"
        ),
        ipca_defasagem_max_meses=_inteiro_positivo(bloco["ipca_defasagem_max_meses"], "fase1.ipca_defasagem_max_meses"),
    )
    if params.beta_minimo > params.beta_pregoes:
        raise ErroParametrosPrecos(
            f"fase1.beta_minimo ({params.beta_minimo}) não pode passar de "
            f"fase1.beta_pregoes ({params.beta_pregoes})"
        )
    if not isinstance(params.setor_excluir, str) or params.setor_excluir not in _SETOR_EXCLUIR:
        raise ErroParametrosPrecos(
            f"fase1.setor_excluir deve ser \"acao\" ou \"empresa\" (recebeu {params.setor_excluir!r})"
        )
    return params


@dataclass(frozen=True)
class Grade:
    """Valor e status por pregão (índice) × ticker (colunas). Valor é NaN sse status != ok."""

    valor: pd.DataFrame
    status: pd.DataFrame


def _status(ref: pd.DataFrame, regras: list[tuple[object, object]]) -> pd.DataFrame:
    """Status de cada célula de `ref`: a 1ª regra verdadeira vence; sem regra, `ok`."""
    conds = [np.asarray(m, dtype=bool) for m, _ in regras]
    escolhas = [s if isinstance(s, str) else np.asarray(s, dtype=object) for _, s in regras]
    return pd.DataFrame(np.select(conds, escolhas, default=OK), index=ref.index, columns=ref.columns)


def montar_grade(valor: pd.DataFrame, status: pd.DataFrame) -> Grade:
    """Grade com o valor anulado (NaN) onde o status não é `ok`."""
    return Grade(valor.where(status == OK), status)


def indice_pregoes(cal: list) -> pd.DatetimeIndex:
    """Datas do calendário (pregões) como índice `data`."""
    return pd.DatetimeIndex(pd.to_datetime(list(cal)), name="data")


def grade_de_precos(precos: pd.DataFrame, cal: list, coluna: str, tickers: list[str]) -> pd.DataFrame:
    """Matriz pregão × ticker com os valores de `coluna`; pregão sem linha vira NaN."""
    idx = indice_pregoes(cal)
    df = precos.loc[precos["ticker"].isin(tickers), ["data", "ticker", coluna]].copy()
    df["data"] = pd.to_datetime(df["data"]).dt.normalize()
    df = df[df["data"].isin(idx)]
    g = df.pivot(index="data", columns="ticker", values=coluna)
    g = g.reindex(index=idx, columns=list(tickers)).astype(float)
    g.columns.name = "ticker"
    return g


def defasagem_pregoes(g: pd.DataFrame) -> pd.DataFrame:
    """Pregões desde o último valor de cada coluna, em cada linha (0 = tem valor no próprio pregão).

    NaN antes do 1º valor da coluna. Só olha para trás (sem vazamento).
    """
    pos = np.arange(len(g), dtype=float)[:, None]
    ultimo = pd.DataFrame(np.where(g.notna().to_numpy(), pos, np.nan), index=g.index, columns=g.columns).ffill()
    return pd.DataFrame(pos - ultimo.to_numpy(), index=g.index, columns=g.columns)


def variacao(g: pd.DataFrame, n: int, defasagem_max: int | None = None) -> Grade:
    """Variação contra a última cotação até a data-alvo t−n (base as-of: `ffill` antes do `shift`).

    `defasagem_max` (seção 6, "Base velha"): a base só vale se a data efetiva (último valor até a data-alvo) está
    no máximo `defasagem_max` pregões antes da data-alvo; senão `historico_insuficiente`. None = sem limite (só
    testes antigos; o código de produção sempre passa `fase1.base_defasagem_max_pregoes`). Valor em t é exigido.
    """
    base = g.ffill().shift(n)
    valor = g / base - 1
    regras = [(g.isna(), INDISPONIVEL), (base.isna(), HIST)]
    if defasagem_max is not None:
        regras.append((defasagem_pregoes(g).shift(n) > defasagem_max, HIST))
    regras.append((base <= 0, INDISPONIVEL))
    return montar_grade(valor, _status(g, regras))


def retornos_diarios(g: pd.DataFrame) -> pd.DataFrame:
    """Retorno do dia: g(t)/g(t−1) − 1, sem preencher lacunas."""
    return g / g.shift(1) - 1


def retornos_asof(g: pd.DataFrame) -> pd.DataFrame:
    """Retorno do dia contra o último preço anterior com valor (base as-of); NaN onde g(t) é NaN."""
    return g / g.ffill().shift(1) - 1


def retornos_suspeitos(g_aj: pd.DataFrame, minimo: float, maximo: float,
                       defasagem_max: int | None = None) -> pd.DataFrame:
    """True onde o retorno as-of do dia é < `minimo` ou > `maximo` (estrito; NaN nunca é suspeito).

    Erro da coleta (seção 6, "Retorno diário suspeito"): o preço não é corrigido, só isolado
    (fora das séries e das medianas do setor).

    `defasagem_max` (seção 6, "Base velha"): o retorno só vale onde a base (pregão anterior) tem valor a no máximo
    `defasagem_max` pregões de distância; acima disso é variação através de lacuna, não retorno diário: NaN (não
    suspeito). None = sem limite (comportamento antigo).
    """
    r = retornos_asof(g_aj)
    if defasagem_max is not None:
        r = r.where(defasagem_pregoes(g_aj).shift(1) <= defasagem_max)
    return (r < minimo) | (r > maximo)


def suspeita_na_janela(suspeitos: pd.DataFrame, n: int) -> pd.DataFrame:
    """True em t se houve retorno suspeito em algum dos `n` pregões até t, inclusive: o intervalo (t-n, t]."""
    return suspeitos.astype(float).rolling(n, min_periods=1).max() > 0


def volume_relativo(gv: pd.DataFrame, n: int) -> tuple[Grade, Grade, Grade]:
    """Volume total, volume relativo (volume(t) ÷ mediana dos n anteriores) e a mediana.

    A mediana exige os `n` pregões anteriores completos; a janela não inclui t.
    """
    mediana = gv.shift(1).rolling(n, min_periods=n).median()
    total = montar_grade(gv, _status(gv, [(gv.isna(), INDISPONIVEL)]))
    med = montar_grade(mediana, _status(gv, [(mediana.isna(), HIST)]))
    rel = montar_grade(
        gv / mediana,
        _status(gv, [(gv.isna(), INDISPONIVEL), (mediana.isna(), HIST), (mediana <= 0, INDISPONIVEL)]),
    )
    return total, rel, med


def _sem_excluidos(ret: pd.DataFrame, excluir: pd.DataFrame | None) -> pd.DataFrame:
    """Retornos com NaN onde `excluir` é True (células ausentes = False); `None` devolve `ret` como está.

    Retorno diário suspeito (seção 6, "Retorno diário suspeito"): sai do cálculo; o preço não muda.
    """
    if excluir is None:
        return ret
    mascara = excluir.reindex(index=ret.index, columns=ret.columns, fill_value=False).astype(bool)
    return ret.mask(mascara)


def volatilidade(g_aj: pd.DataFrame, n: int, excluir: pd.DataFrame | None = None) -> Grade:
    """Desvio-padrão amostral (ddof = 1) dos n últimos retornos diários de `aj`, sem anualizar.

    `excluir` (seção 6, "Retorno diário suspeito"): máscara bool dos retornos da ação que não contam. Janela
    com algum deles fica incompleta → `historico_insuficiente`.
    """
    v = _sem_excluidos(retornos_diarios(g_aj), excluir).rolling(n, min_periods=n).std(ddof=1)
    return montar_grade(v, _status(g_aj, [(g_aj.isna(), INDISPONIVEL), (v.isna(), HIST)]))


def posicao_pct(gr: Grade, pares: list[str]) -> Grade:
    """Fração dos pares válidos do dia estritamente menores que o valor (menor = 0, maior = 1).

    Só pares contam; não-pares saem `nao_se_aplica`. Menos de 2 pares válidos: indisponivel.
    """
    v = gr.valor[pares]
    menores = v.rank(axis=1, method="min") - 1
    n = v.notna().sum(axis=1)
    pos = menores.div((n - 1).where(n > 1), axis=0).reindex(columns=gr.valor.columns)
    nao_par = pd.DataFrame(
        np.tile(~gr.valor.columns.isin(pares), (len(gr.valor), 1)),
        index=gr.valor.index,
        columns=gr.valor.columns,
    )
    st = _status(gr.valor, [(nao_par, NAO_SE_APLICA), (gr.status != OK, gr.status.to_numpy()), (pos.isna(), INDISPONIVEL)])
    return montar_grade(pos, st)


def beta_sobre_retornos(g_aj: pd.DataFrame, ret_fator: pd.Series, janela: int, minimo: int,
                        excluir: pd.DataFrame | None = None) -> Grade:
    """Beta MQO dos retornos diários da ação sobre `ret_fator` (retorno diário do fator), só nos pares válidos.

    Janela de `janela` pregões até t; calcula a partir de `minimo` pares válidos.
    `excluir` (seção 6, "Retorno diário suspeito"): máscara bool dos retornos da ação que não contam; o par sai
    e, com menos de `minimo` pares, `historico_insuficiente`.
    """
    ra = _sem_excluidos(retornos_diarios(g_aj), excluir)
    ri = ret_fator.reindex(ra.index)
    ri_m = pd.DataFrame(np.repeat(ri.to_numpy()[:, None], ra.shape[1], axis=1), index=ra.index, columns=ra.columns)
    valido = ra.notna() & ri_m.notna()
    x = ri_m.where(valido, 0.0)
    y = ra.where(valido, 0.0)

    def _soma(d: pd.DataFrame) -> pd.DataFrame:
        return d.rolling(janela, min_periods=1).sum()

    n = _soma(valido.astype(float))
    sx, sy, sxy, sxx = _soma(x), _soma(y), _soma(x * y), _soma(x * x)
    cov = (sxy - sx * sy / n) / (n - 1)
    var = (sxx - sx * sx / n) / (n - 1)
    b = cov / var
    st = _status(g_aj, [(g_aj.isna(), INDISPONIVEL), (n < minimo, HIST), (~(var > 0), INDISPONIVEL)])
    return montar_grade(b, st)


def beta(g_aj: pd.DataFrame, ibov_aj: pd.Series, janela: int, minimo: int,
         excluir: pd.DataFrame | None = None) -> Grade:
    """Beta contra o IBOV: `beta_sobre_retornos` com o retorno diário do IBOV."""
    return beta_sobre_retornos(g_aj, ibov_aj / ibov_aj.shift(1) - 1, janela, minimo, excluir)


def mapas_cadastro(cadastro: pd.DataFrame) -> tuple[dict, dict]:
    """(setor_de, cnpj_de) por ticker; vazio ou NaN vira None."""

    def _texto(v: object) -> str | None:
        return v if isinstance(v, str) and v.strip() else None

    setor_de = {t: _texto(s) for t, s in zip(cadastro["ticker"], cadastro["setor"])}
    cnpj_de = {t: _texto(c) for t, c in zip(cadastro["ticker"], cadastro["cnpj"])}
    return setor_de, cnpj_de


def _conferir_modo(modo: str) -> None:
    if modo not in _SETOR_EXCLUIR:
        raise ValueError(f"modo de setor deve ser \"acao\" ou \"empresa\" (recebeu {modo!r})")


def _outros_do_setor(t: str, pares: list[str], setor_de: dict, cnpj_de: dict, modo: str) -> list[str]:
    """Pares do mesmo setor de `t`, sem o próprio `t`; no modo "empresa", sem o mesmo CNPJ."""
    s = setor_de.get(t)
    if s is None:
        return []
    outros = []
    for p in pares:
        if p == t or setor_de.get(p) != s:
            continue
        if modo == "empresa" and cnpj_de.get(p) is not None and cnpj_de.get(p) == cnpj_de.get(t):
            continue
        outros.append(p)
    return outros


def media_setor(gr: Grade, pares: list[str], setor_de: dict, cnpj_de: dict, modo: str,
                agregacao: str = "media") -> Grade:
    """Média (ou mediana) dos valores dos outros pares do setor de cada ticker.

    No modo "empresa", cada CNPJ conta uma vez: primeiro a média das suas ações com valor,
    depois a média (ou mediana) entre empresas (ticker sem CNPJ conta como empresa à parte).
    `agregacao`: "media" (variável `ret_vs_setor` do modelo) ou "mediana" (painel, decidido em
    23/10/2026: um valor extremo não distorce a comparação).
    Sem setor ou sem outro par: indisponivel. Outros pares existem mas nenhum tem valor: HIST.
    """
    _conferir_modo(modo)
    if agregacao not in ("media", "mediana"):
        raise ValueError(f"agregacao do setor deve ser \"media\" ou \"mediana\" (recebeu {agregacao!r})")
    idx = gr.valor.index
    valor, status = {}, {}
    for t in gr.valor.columns:
        outros = _outros_do_setor(t, pares, setor_de, cnpj_de, modo)
        if outros:
            bloco = gr.valor[outros]
            if modo == "empresa":
                bloco = bloco.T.groupby([cnpj_de.get(p) or p for p in outros], sort=False).mean().T
            cnt = bloco.notna().sum(axis=1).to_numpy()
            valor[t] = bloco.median(axis=1) if agregacao == "mediana" else bloco.mean(axis=1)
            status[t] = pd.Series(np.select([cnt == 0], [HIST], default=OK), index=idx, dtype=object)
        else:
            valor[t] = pd.Series(np.nan, index=idx)
            status[t] = pd.Series(INDISPONIVEL, index=idx, dtype=object)
    cols = list(gr.valor.columns)
    return montar_grade(
        pd.DataFrame(valor, index=idx, columns=cols),
        pd.DataFrame(status, index=idx, columns=cols),
    )


def comparacao_fraca(tickers: list[str], pares: list[str], setor_de: dict, cnpj_de: dict,
                     modo: str, minimo: int) -> pd.Series:
    """True para cada ticker cujo setor tem menos de `minimo` empresas (CNPJs distintos no modo "empresa").

    A própria empresa conta. Sem setor: True.
    """
    _conferir_modo(modo)
    res = {}
    for t in tickers:
        s = setor_de.get(t)
        if s is None:
            res[t] = True
            continue
        membros = [p for p in pares if setor_de.get(p) == s]
        if modo == "acao":
            tamanho = len(membros)
        else:
            tamanho = len({cnpj_de.get(p) or p for p in membros})
        res[t] = tamanho < minimo
    return pd.Series(res, dtype=bool)


def tickers_do_painel(cadastro: pd.DataFrame, exclusoes: Exclusoes) -> list[str]:
    """Tickers do cadastro sem os excluídos, em ordem alfabética."""
    return sorted(t for t in cadastro["ticker"] if t not in exclusoes.tickers_excluidos)


def pares_do_painel(cadastro: pd.DataFrame, exclusoes: Exclusoes) -> list[str]:
    """Tickers do painel com tipo de ação em `TIPOS_ACEITOS` (ON, PN, UNIT); BDR fica de fora."""
    painel = set(tickers_do_painel(cadastro, exclusoes))
    return sorted(
        t for t, k in zip(cadastro["ticker"], cadastro["tipo_acao"]) if t in painel and k in TIPOS_ACEITOS
    )


def tickers_com_suspeita(precos: pd.DataFrame, cal: list, t, tickers: list[str], minimo: float,
                         maximo: float, n: int, defasagem_max: int | None = None) -> set[str]:
    """Tickers com retorno suspeito (fechamento_ajustado) em algum dos `n` pregões até t.

    `ValueError` se t não é pregão de `cal`. Só olha preços até t (sem vazamento).
    `defasagem_max`: repassado a `retornos_suspeitos` (produção passa `fase1.base_defasagem_max_pregoes`).
    """
    ts = pd.Timestamp(t).normalize()
    g = grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    if ts not in g.index:
        raise ValueError(f"{t} não é pregão")
    linha = suspeita_na_janela(retornos_suspeitos(g, minimo, maximo, defasagem_max), n).loc[ts]
    return {tk for tk, v in linha.items() if bool(v)}


def _repetir(g: Grade, tickers: list[str]) -> Grade:
    """Grade de uma coluna só (ex.: IBOV) repetida em todas as colunas de `tickers`."""
    n = len(tickers)
    valor = pd.DataFrame(np.repeat(g.valor.to_numpy(), n, axis=1), index=g.valor.index, columns=tickers)
    status = pd.DataFrame(np.repeat(g.status.to_numpy(), n, axis=1), index=g.status.index, columns=tickers)
    return montar_grade(valor, status)


def calcular_precos(
    precos: pd.DataFrame,
    cadastro: pd.DataFrame,
    cal: list,
    exclusoes: Exclusoes,
    params: ParametrosPrecos,
) -> dict[str, Grade]:
    """Indicadores de preço, volume e comparações do painel; chave = indicador (ver seção 5)."""
    tickers = tickers_do_painel(cadastro, exclusoes)
    pares = pares_do_painel(cadastro, exclusoes)
    setor_de, cnpj_de = mapas_cadastro(cadastro)
    idx = indice_pregoes(cal)

    g_fech = grade_de_precos(precos, cal, "fechamento", tickers)
    g_aj = grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
    gv = grade_de_precos(precos, cal, "volume", tickers)
    ibov_aj = grade_de_precos(precos, cal, "fechamento_ajustado", ["IBOV"])

    res: dict[str, Grade] = {}
    res["cotacao.fechamento"] = montar_grade(g_fech, _status(g_fech, [(g_fech.isna(), INDISPONIVEL)]))
    n_max = params.base_defasagem_max_pregoes
    res["cotacao.variacao_dia"] = variacao(g_fech, 1, n_max)
    # import local: fatos/series.py importa este módulo (importar no topo daria importação circular)
    from processamento.fatos.series import rentabilidade_setor_sem_empresa
    suspeitos = retornos_suspeitos(g_aj, params.retorno_suspeito_min, params.retorno_suspeito_max, n_max)
    setor_rent = rentabilidade_setor_sem_empresa(g_aj, cadastro, pares, tickers, params.janelas,
                                                 params.setor_excluir, suspeitos=suspeitos, defasagem_max=n_max)
    for nome, n in params.janelas.items():
        rent = variacao(g_aj, n, n_max)
        res[f"variacao_preco.{nome}"] = variacao(g_fech, n, n_max)
        res[f"rentabilidade.{nome}"] = rent
        res[f"rentabilidade.ibov.{nome}"] = _repetir(variacao(ibov_aj, n, n_max), tickers)
        res[f"rentabilidade.setor.{nome}"] = setor_rent[nome]   # DS11: razão da série SETOR_SEM:<ticker>

    total, relativo, mediana = volume_relativo(gv, params.volume_pregoes)
    res["volume.total"] = total
    res["volume.relativo"] = relativo
    res[f"volume.mediana_{params.volume_pregoes}"] = mediana
    res["volume.posicao_pct"] = posicao_pct(relativo, pares)

    k = params.volatilidade_retornos
    vol = volatilidade(g_aj, k, excluir=suspeitos)
    res[f"volatilidade_{k}d.valor"] = vol
    res[f"volatilidade_{k}d.posicao_pct"] = posicao_pct(vol, pares)

    res["beta.valor"] = beta(g_aj, ibov_aj["IBOV"], params.beta_pregoes, params.beta_minimo, excluir=suspeitos)

    fraca = comparacao_fraca(tickers, pares, setor_de, cnpj_de, params.setor_excluir, params.setor_minimo)
    fraca_valor = np.repeat(fraca.reindex(tickers).astype(float).to_numpy()[None, :], len(idx), axis=0)
    res["setor_comparacao_fraca"] = Grade(
        pd.DataFrame(fraca_valor, index=idx, columns=tickers),
        pd.DataFrame(OK, index=idx, columns=tickers, dtype=object),
    )
    return res


def resumo_precos_no_dia(grades: dict[str, Grade], t) -> pd.DataFrame:
    """Formato longo [ticker, indicador, valor, status] de t; ValueError se t não for pregão."""
    ts = pd.Timestamp(t).normalize()
    linhas = []
    for indicador, grade in grades.items():
        if ts not in grade.valor.index:
            raise ValueError(f"{t} não é pregão")
        for ticker in grade.valor.columns:
            linhas.append({
                "ticker": ticker,
                "indicador": indicador,
                "valor": float(grade.valor.at[ts, ticker]),
                "status": grade.status.at[ts, ticker],
            })
    df = pd.DataFrame(linhas, columns=["ticker", "indicador", "valor", "status"])
    return df.sort_values(["ticker", "indicador"]).reset_index(drop=True)
