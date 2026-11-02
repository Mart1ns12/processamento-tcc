"""Indicadores fundamentalistas e proventos (seções 5 e 6 da especificação).

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Ausência é NaN + `status` (nunca 0). Os parâmetros vêm do bloco `fundamentos` de
`config/parametros.yaml`.
"""

from __future__ import annotations

import dataclasses
import math
import unicodedata
from dataclasses import dataclass

import pandas as pd

from processamento import calendario
from processamento.exclusoes import Exclusoes
from processamento.fatos.precos import (
    HIST,
    INDISPONIVEL,
    NAO_SE_APLICA,
    OK,
    Grade,
    grade_de_precos,
    indice_pregoes,
    mapas_cadastro,
    media_setor,
    montar_grade,
    pares_do_painel,
    tickers_do_painel,
)
from processamento.fatos.proventos import (
    acoes_disponiveis,
    acoes_na_data,
    dividend_yield,
    inicio_janela,
    ligar_proventos,
    total_pago,
)
from processamento.fatos.trimestres import (
    FotoBalanco,
    entregues_ate,
    foto_balanco,
    meses_do_periodo,
    trimestres_isolados,
)

LUCRO_NEGATIVO = "lucro_negativo"

_CHAVES_FUNDAMENTOS = {
    "subsetores_financeiros", "meses_janela", "anos_payout", "anos_historico_proventos", "pvp_minimo_plausivel",
    "pvp_maximo_plausivel_x1000", "balanco_idade_max_meses",
}


class ErroParametrosFundamentos(Exception):
    """Bloco `fundamentos` inválido ou ausente (a mensagem diz o que corrigir)."""


@dataclass(frozen=True)
class ParametrosFundamentos:
    """Parâmetros de fundamentos (bloco `fundamentos` de config/parametros.yaml)."""

    subsetores_financeiros: tuple[str, ...]
    meses_janela: int
    anos_payout: int
    anos_historico_proventos: int
    pvp_minimo_plausivel: float
    balanco_idade_max_meses: int = 15
    pvp_maximo_plausivel_x1000: float = math.inf


def _inteiro_positivo(valor: object, onde: str) -> int:
    """Confere um inteiro > 0 (bool não conta); levanta `ErroParametrosFundamentos` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ErroParametrosFundamentos(f"{onde} deve ser um inteiro maior que zero (recebeu {valor!r})")
    return valor


def _numero_entre_zero_e_um(valor: object, onde: str) -> float:
    """Confere um número com 0 < valor < 1 (bool não conta; NaN é recusado); senão levanta o erro."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 < valor < 1:
        raise ErroParametrosFundamentos(f"{onde} deve ser um número maior que zero e menor que um (recebeu {valor!r})")
    return float(valor)


def _numero_maior_que_zero(valor: object, onde: str) -> float:
    """Confere um número > 0 (bool e texto não contam; NaN é recusado); senão levanta o erro."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not valor > 0:
        raise ErroParametrosFundamentos(f"{onde} deve ser um número maior que zero (recebeu {valor!r})")
    return float(valor)


def carregar_parametros_fundamentos(caminho: str | None = None) -> ParametrosFundamentos:
    """Lê o bloco `fundamentos` (do caminho dado ou do parametros.yaml) e valida cada chave."""
    bloco = calendario.carregar_parametros(caminho).get("fundamentos")
    if not isinstance(bloco, dict):
        raise ErroParametrosFundamentos("falta o bloco fundamentos no arquivo de parâmetros")
    desconhecidas = set(bloco) - _CHAVES_FUNDAMENTOS
    if desconhecidas:
        raise ErroParametrosFundamentos(f"chave desconhecida no bloco fundamentos: {sorted(desconhecidas)}")
    faltantes = _CHAVES_FUNDAMENTOS - set(bloco)
    if faltantes:
        raise ErroParametrosFundamentos(f"faltam chaves no bloco fundamentos: {sorted(faltantes)}")

    subsetores = bloco["subsetores_financeiros"]
    if not isinstance(subsetores, list) or not subsetores:
        raise ErroParametrosFundamentos("fundamentos.subsetores_financeiros deve ser uma lista não vazia")
    for nome in subsetores:
        if not isinstance(nome, str) or not nome.strip():
            raise ErroParametrosFundamentos(
                f"subsetor inválido em fundamentos.subsetores_financeiros: {nome!r} (use texto entre aspas)"
            )

    return ParametrosFundamentos(
        subsetores_financeiros=tuple(subsetores),
        meses_janela=_inteiro_positivo(bloco["meses_janela"], "fundamentos.meses_janela"),
        anos_payout=_inteiro_positivo(bloco["anos_payout"], "fundamentos.anos_payout"),
        anos_historico_proventos=_inteiro_positivo(
            bloco["anos_historico_proventos"], "fundamentos.anos_historico_proventos"
        ),
        pvp_minimo_plausivel=_numero_entre_zero_e_um(bloco["pvp_minimo_plausivel"], "fundamentos.pvp_minimo_plausivel"),
        pvp_maximo_plausivel_x1000=_numero_maior_que_zero(
            bloco["pvp_maximo_plausivel_x1000"], "fundamentos.pvp_maximo_plausivel_x1000"
        ),
        balanco_idade_max_meses=_inteiro_positivo(
            bloco["balanco_idade_max_meses"], "fundamentos.balanco_idade_max_meses"
        ),
    )


def normalizar_texto(texto: object) -> str | None:
    """Texto sem acento, em minúsculas e sem espaços sobrando; None, NaN e vazio viram None."""
    if not isinstance(texto, str):
        return None
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    limpo = " ".join(sem_acento.split()).casefold()
    return limpo or None


def eh_financeiro(subsetor: object, params: ParametrosFundamentos) -> bool:
    """True se o subsetor (sem acento e sem caixa) está na lista de subsetores financeiros."""
    alvo = normalizar_texto(subsetor)
    if alvo is None:
        return False
    return alvo in {normalizar_texto(nome) for nome in params.subsetores_financeiros}


def _falha(status: str) -> tuple[float, str]:
    """Par (NaN, status): ausência com o motivo."""
    return (math.nan, status)


def _primeiro_nao_ok(*statuses: str) -> str | None:
    """Primeiro status diferente de ok, na ordem dada; None se todos forem ok."""
    return next((s for s in statuses if s != OK), None)


def _media_preco(tickers: list[str], fech: dict[str, float]) -> float | None:
    """Média dos fechamentos dos tickers; None se não houver ticker ou se faltar algum preço."""
    precos = [fech.get(ticker) for ticker in tickers]
    if not precos or any(p is None or pd.isna(p) for p in precos):
        return None
    return sum(precos) / len(precos)


def valor_de_mercado(
    cnpj: str | None,
    fech: dict[str, float],
    cadastro: pd.DataFrame,
    painel: list[str],
    qtd: tuple[float, float, str],
) -> tuple[float, str]:
    """Valor de mercado da empresa em t (seção 5 da especificação).

    Entram só as ações do `painel` com esse CNPJ e classe ON, PN ou UNIT. `fech` é o
    fechamento (sem dividendos) de cada ticker em t; `qtd` é (qtd_on, qtd_pn, status) das
    ações emitidas. Sem preço ou composição válida, devolve (NaN, indisponivel).
    """
    qtd_on, qtd_pn, qtd_status = qtd
    if not isinstance(cnpj, str) or qtd_status != OK or not (qtd_on + qtd_pn > 0):
        return _falha(INDISPONIVEL)

    do_cnpj = cadastro[
        (cadastro["cnpj"] == cnpj)
        & cadastro["ticker"].isin(painel)
        & cadastro["tipo_acao"].isin(["ON", "PN", "UNIT"])
    ]
    classes = set(do_cnpj["tipo_acao"])
    on = do_cnpj.loc[do_cnpj["tipo_acao"] == "ON", "ticker"].tolist()
    pn = do_cnpj.loc[do_cnpj["tipo_acao"] == "PN", "ticker"].tolist()
    total = qtd_on + qtd_pn

    if {"ON", "PN"} <= classes:
        media_on = _media_preco(on, fech)
        media_pn = _media_preco(pn, fech)
        if media_on is None or media_pn is None:
            return _falha(INDISPONIVEL)
        return (float(media_on * qtd_on + media_pn * qtd_pn), OK)

    if classes in ({"ON"}, {"PN"}):
        media = _media_preco(on if classes == {"ON"} else pn, fech)
        if media is None:
            return _falha(INDISPONIVEL)
        return (float(media * total), OK)

    if classes == {"UNIT"}:
        unit = do_cnpj[do_cnpj["tipo_acao"] == "UNIT"].iloc[0]
        preco = fech.get(unit["ticker"])
        composicao = unit["unit_qtd_on"] + unit["unit_qtd_pn"]
        if preco is None or pd.isna(preco) or not (composicao > 0):
            return _falha(INDISPONIVEL)
        return (float(preco / composicao * total), OK)

    return _falha(INDISPONIVEL)


def quantidade_suspeita(vm: tuple[float, str], foto: FotoBalanco, limite: float, teto_x1000: float) -> bool:
    """True se a quantidade de ações da empresa parece estar em milhares (seção 10).

    Suspeita quando o valor de mercado e o patrimônio líquido têm status ok, o PL é > 0, valor de mercado ÷ PL
    é menor que `limite` (estrito: exatamente igual ao limite não é suspeito) e valor de mercado ÷ PL × 1000
    é menor ou igual a `teto_x1000` (acima disso, multiplicar as ações por 1000 daria P/VP implausível, logo a
    quantidade não está em milhares).
    """
    valor_mercado, vm_s = vm
    pl, pl_s = foto.estoque["patrimonio_liquido"]
    if vm_s != OK or pl_s != OK or not pl > 0:
        return False
    p = valor_mercado / pl
    return p < limite and p * 1000 <= teto_x1000


def limite_do_balanco(data_fim_periodo, meses: int) -> pd.Timestamp:
    """Último dia em que o balanço vale: fim do mês de (data_fim_periodo + `meses` meses)."""
    return pd.Timestamp(data_fim_periodo).normalize() + pd.DateOffset(months=meses) + pd.offsets.MonthEnd(0)


def balanco_velho(data_fim_periodo, t, meses: int) -> bool:
    """True se o balanço de referência é velho em t: fim do mês de (data_fim_periodo + `meses` meses) < t.

    Estrito: no último dia desse mês o balanço ainda vale (ex.: 2024-09-30 + 15 meses -> 2025-12-31, velho
    a partir de 2026-01-01). Sem data (None/NaT) não é velho.
    """
    if data_fim_periodo is None or pd.isna(data_fim_periodo):
        return False
    return bool(limite_do_balanco(data_fim_periodo, meses) < pd.Timestamp(t).normalize())


def foto_dentro_do_prazo(foto: FotoBalanco, t, meses: int) -> FotoBalanco:
    """A própria foto, ou uma cópia com `status_base = indisponivel` se o balanço de referência é velho em t.

    Usada só no painel do dia e nos múltiplos diários (seção 6, "Balanço velho"); payout por ano, tabela
    trimestral e balanço de referência continuam com a foto original.
    """
    if foto.status_base == OK and balanco_velho(foto.data_fim_periodo, t, meses):
        return dataclasses.replace(foto, status_base=INDISPONIVEL)
    return foto


def indicadores_empresa(
    foto: FotoBalanco,
    vm: tuple[float, str],
    pago: tuple[float, str],
    financeiro: bool,
    pvp_minimo: float | None = None,
    pvp_maximo_x1000: float = math.inf,
) -> dict[str, tuple[float, str]]:
    """Indicadores da empresa em t: P/L, P/VP, ROE, payout, margens, EBITDA e endividamento.

    Cada indicador devolve (valor, status). A primeira regra que se aplica vence (ordem da
    tabela da F3a do plano). P/L com lucro negativo mantém o valor (vm/L) e o status
    `lucro_negativo`; com lucro zero o valor é NaN.
    Se `pvp_minimo` não for None e a quantidade de ações for suspeita (`quantidade_suspeita`, com
    `pvp_maximo_x1000` como teto de P/VP × 1000), valor de mercado e pago viram indisponíveis antes das contas:
    P/L, P/VP e payout saem indisponíveis.
    """
    if pvp_minimo is not None and quantidade_suspeita(vm, foto, pvp_minimo, pvp_maximo_x1000):
        vm = _falha(INDISPONIVEL)
        pago = _falha(INDISPONIVEL)
    base = foto.status_base
    lucro, lucro_s = foto.fluxo_12m["lucro_liquido"]
    receita, receita_s = foto.fluxo_12m["receita_liquida"]
    lucro_bruto, lucro_bruto_s = foto.fluxo_12m["lucro_bruto"]
    ebit, ebit_s = foto.fluxo_12m["ebit"]
    depreciacao, depreciacao_s = foto.fluxo_12m["depreciacao_amortizacao"]
    pl, pl_s = foto.estoque["patrimonio_liquido"]
    emp_cp, emp_cp_s = foto.estoque["emprestimos_curto_prazo"]
    emp_lp, emp_lp_s = foto.estoque["emprestimos_longo_prazo"]
    caixa, caixa_s = foto.estoque["caixa"]
    aplic, aplic_s = foto.estoque["aplicacoes_financeiras"]
    valor_mercado, vm_s = vm
    pago_valor, pago_s = pago

    # Múltiplos e rentabilidade
    falha = _primeiro_nao_ok(base, lucro_s, vm_s)
    if falha:
        pl_valor = _falha(falha)
    elif lucro < 0:
        pl_valor = (valor_mercado / lucro, LUCRO_NEGATIVO)
    elif lucro == 0:
        pl_valor = _falha(LUCRO_NEGATIVO)
    else:
        pl_valor = (valor_mercado / lucro, OK)

    falha = _primeiro_nao_ok(base, pl_s, vm_s)
    if falha:
        pvp = _falha(falha)
    elif pl <= 0:
        pvp = _falha(NAO_SE_APLICA)
    else:
        pvp = (valor_mercado / pl, OK)

    falha = _primeiro_nao_ok(base, lucro_s, pl_s)
    if falha:
        roe = _falha(falha)
    elif pl <= 0:
        roe = _falha(NAO_SE_APLICA)
    else:
        roe = (lucro / pl, OK)

    falha = _primeiro_nao_ok(base, lucro_s, pago_s)
    if falha:
        payout = _falha(falha)
    elif lucro <= 0:
        payout = _falha(LUCRO_NEGATIVO)
    else:
        payout = (pago_valor / lucro, OK)

    # Margens
    falha = _primeiro_nao_ok(base, receita_s, lucro_bruto_s)
    if financeiro:
        margem_bruta = _falha(NAO_SE_APLICA)
    elif falha:
        margem_bruta = _falha(falha)
    elif receita <= 0:
        margem_bruta = _falha(INDISPONIVEL)
    else:
        margem_bruta = (lucro_bruto / receita, OK)

    falha = _primeiro_nao_ok(base, receita_s, lucro_s)
    if financeiro:
        margem_liquida = _falha(NAO_SE_APLICA)
    elif falha:
        margem_liquida = _falha(falha)
    elif receita <= 0:
        margem_liquida = _falha(INDISPONIVEL)
    else:
        margem_liquida = (lucro / receita, OK)

    # EBITDA (ebit + D&A; sem ebit ou D&A não há EBITDA)
    if financeiro:
        ebitda = _falha(NAO_SE_APLICA)
    else:
        falha = _primeiro_nao_ok(base, ebit_s, depreciacao_s)
        ebitda = _falha(falha) if falha else (ebit + depreciacao, OK)
    ebitda_valor, ebitda_s = ebitda

    falha = _primeiro_nao_ok(base, ebitda_s, receita_s)
    if financeiro:
        ebitda_margem = _falha(NAO_SE_APLICA)
    elif falha:
        ebitda_margem = _falha(falha)
    elif receita <= 0:
        ebitda_margem = _falha(INDISPONIVEL)
    else:
        ebitda_margem = (ebitda_valor / receita, OK)

    # Endividamento (dívida líquida = empréstimos CP + LP − caixa − aplicações)
    if financeiro:
        divida = _falha(NAO_SE_APLICA)
    else:
        falha = _primeiro_nao_ok(base, emp_cp_s, emp_lp_s, caixa_s, aplic_s)
        if falha:
            divida = _falha(falha)
        elif emp_cp == 0 and emp_lp == 0:
            # CP e LP = 0 juntos: conta não achada pela coleta, não dívida zero (decisão de 22/10/2026)
            divida = _falha(INDISPONIVEL)
        else:
            divida = (emp_cp + emp_lp - caixa - aplic, OK)
    divida_valor, divida_s = divida

    falha = _primeiro_nao_ok(divida_s, pl_s)
    if falha:
        divida_pl = _falha(falha)
    elif pl <= 0:
        divida_pl = _falha(NAO_SE_APLICA)
    else:
        divida_pl = (divida_valor / pl, OK)

    falha = _primeiro_nao_ok(divida_s, ebitda_s)
    if falha:
        divida_ebitda = _falha(falha)
    elif ebitda_valor <= 0:
        divida_ebitda = _falha(NAO_SE_APLICA)
    else:
        divida_ebitda = (divida_valor / ebitda_valor, OK)

    if divida_s != OK:
        caixa_liquido = _falha(divida_s)
    else:
        caixa_liquido = (1.0 if divida_valor < 0 else 0.0, OK)

    return {
        "pl.valor": pl_valor,
        "pvp.valor": pvp,
        "roe.valor": roe,
        "payout.valor": payout,
        "margem_bruta.valor": margem_bruta,
        "margem_liquida.valor": margem_liquida,
        "ebitda.valor_12m": ebitda,
        "ebitda.margem": ebitda_margem,
        "endividamento.divida_liquida": divida,
        "endividamento.dl_pl": divida_pl,
        "endividamento.dl_ebitda": divida_ebitda,
        "endividamento.caixa_liquido": caixa_liquido,
    }


# ---------------------------------------------------------------------------
# F3b: montagem no dia t, setor, payout por ano e balanço de referência
# ---------------------------------------------------------------------------

INDICADORES = (
    "pl.valor", "pl.setor", "pvp.valor", "pvp.setor", "roe.valor", "roe.setor",
    "dividend_yield.valor", "dividend_yield.setor", "payout.valor", "payout.setor",
    "margem_bruta.valor", "margem_bruta.setor", "margem_liquida.valor", "margem_liquida.setor",
    "ebitda.valor_12m", "ebitda.margem", "ebitda.setor_margem",
    "endividamento.divida_liquida", "endividamento.dl_pl", "endividamento.dl_ebitda",
    "endividamento.caixa_liquido", "endividamento.setor_dl_pl", "endividamento.setor_dl_ebitda",
)

# Indicadores da empresa (saem de `indicadores_empresa`); o yield é por ticker.
_CHAVES_EMPRESA = (
    "pl.valor", "pvp.valor", "roe.valor", "payout.valor", "margem_bruta.valor",
    "margem_liquida.valor", "ebitda.valor_12m", "ebitda.margem", "endividamento.divida_liquida",
    "endividamento.dl_pl", "endividamento.dl_ebitda", "endividamento.caixa_liquido",
)

# D9: indicadores de BDR sempre indisponíveis (o yield já sai assim em `dividend_yield`).
_BDR_INDISPONIVEL = ("pl.valor", "pvp.valor", "payout.valor")

# Campo de setor -> indicador de empresa de onde ele sai (a média é feita sobre esse valor).
_ORIGEM_SETOR = {
    "pl.setor": "pl.valor",
    "pvp.setor": "pvp.valor",
    "roe.setor": "roe.valor",
    "dividend_yield.setor": "dividend_yield.valor",
    "payout.setor": "payout.valor",
    "margem_bruta.setor": "margem_bruta.valor",
    "margem_liquida.setor": "margem_liquida.valor",
    "ebitda.setor_margem": "ebitda.margem",
    "endividamento.setor_dl_pl": "endividamento.dl_pl",
    "endividamento.setor_dl_ebitda": "endividamento.dl_ebitda",
}

# Campos de setor que ficam `nao_se_aplica` quando a própria empresa é financeira.
_SETOR_SEM_FINANCEIRA = {
    "margem_bruta.setor", "margem_liquida.setor", "ebitda.setor_margem",
    "endividamento.setor_dl_pl", "endividamento.setor_dl_ebitda",
}

# Campos de setor que usam o preço de t: a empresa com retorno suspeito recente fica fora (seção 6).
_SETOR_COM_PRECO = frozenset({"pl.setor", "pvp.setor", "dividend_yield.setor"})


@dataclass(frozen=True)
class DadosFundamentos:
    """Tabelas já lidas (`fontes.ler_tabela`). `proventos` traz os tickers ORIGINAIS.

    `mudancas` é o mapa de troca de ticker, usado para ligar os proventos à empresa.
    """

    precos: pd.DataFrame
    cadastro: pd.DataFrame
    balancos: pd.DataFrame
    acoes_emitidas: pd.DataFrame
    proventos: pd.DataFrame
    mudancas: dict[str, str]


def _grade_do_dia(ts: pd.Timestamp, tickers: list[str], celulas: dict[str, tuple[float, str]]) -> Grade:
    """Grade de uma linha (o dia `ts`) com um par (valor, status) por ticker.

    O valor fica NaN quando o status não é ok, exceto `pl.valor` com `lucro_negativo`, que
    mantém o valor (seção 3 do plano). Por isso não usa `montar_grade`.
    """
    idx = pd.DatetimeIndex([ts], name="data")
    valores = [float(celulas[k][0]) if celulas[k][1] in (OK, LUCRO_NEGATIVO) else math.nan for k in tickers]
    status = [celulas[k][1] for k in tickers]
    return Grade(
        pd.DataFrame([valores], index=idx, columns=tickers, dtype=float),
        pd.DataFrame([status], index=idx, columns=tickers, dtype=object),
    )


def calcular_fundamentos_no_dia(t, cal, dados: DadosFundamentos, exclusoes: Exclusoes,
                                params: ParametrosFundamentos, modo_setor: str,
                                fora_do_setor_preco: frozenset[str] = frozenset()) -> dict[str, Grade]:
    """Indicadores de todos os tickers do painel em `t`: uma linha por grade (índice [t]).

    Chaves na ordem de `INDICADORES`. `ValueError` se `t` não é pregão em `cal`.
    Cada campo de setor é `media_setor` sobre o indicador da empresa, com `montar_grade` antes:
    a empresa com prejuízo fica fora da média do P/L. `historico_insuficiente` vira indisponivel.
    `fora_do_setor_preco`: tickers com retorno suspeito recente (`fatos.precos.tickers_com_suspeita`);
    a empresa inteira (mesmo CNPJ) sai das medianas de P/L, P/VP e yield. Os valores da própria empresa não mudam.
    """
    ts = pd.Timestamp(t).normalize()
    if ts not in indice_pregoes(cal):
        raise ValueError(f"{t} não é pregão")

    tickers = tickers_do_painel(dados.cadastro, exclusoes)
    pares = pares_do_painel(dados.cadastro, exclusoes)
    setor_de, cnpj_de = mapas_cadastro(dados.cadastro)
    subsetor_de = dict(zip(dados.cadastro["ticker"], dados.cadastro["subsetor"]))
    tipo_de = dict(zip(dados.cadastro["ticker"], dados.cadastro["tipo_acao"]))
    fech = grade_de_precos(dados.precos, [ts], "fechamento", tickers).iloc[0].to_dict()
    ligados = ligar_proventos(dados.proventos, dados.cadastro, dados.mudancas)
    disp = acoes_disponiveis(dados.acoes_emitidas, dados.balancos, ts)
    cnpjs_com_classe_paga = {cnpj_de[p] for p in pares if cnpj_de.get(p)}

    # Indicadores por empresa (CNPJ): uma vez por CNPJ, copiados para cada ticker.
    por_empresa: dict[str, dict[str, tuple[float, str]]] = {}
    financeira_cnpj: dict[str, bool] = {}
    for cnpj in sorted({cnpj_de[k] for k in tickers if cnpj_de.get(k)}):
        foto = foto_dentro_do_prazo(foto_balanco(dados.balancos, cnpj, ts, exclusoes), ts, params.balanco_idade_max_meses)
        vm = valor_de_mercado(cnpj, fech, dados.cadastro, tickers, acoes_na_data(disp, cnpj, ts))
        if cnpj in cnpjs_com_classe_paga:
            pago = total_pago(ligados, disp, cnpj, inicio_janela(ts, params.meses_janela), ts)
        else:
            pago = _falha(INDISPONIVEL)
        financeira_cnpj[cnpj] = any(
            eh_financeiro(subsetor_de.get(k), params) for k in tickers if cnpj_de.get(k) == cnpj
        )
        por_empresa[cnpj] = indicadores_empresa(foto, vm, pago, financeira_cnpj[cnpj],
                                                pvp_minimo=params.pvp_minimo_plausivel,
                                                pvp_maximo_x1000=params.pvp_maximo_plausivel_x1000)

    celulas: dict[str, dict[str, tuple[float, str]]] = {}
    financeira_de: dict[str, bool] = {}
    for k in tickers:
        cnpj = cnpj_de.get(k)
        if cnpj:
            celulas[k] = dict(por_empresa[cnpj])
            financeira_de[k] = financeira_cnpj[cnpj]
        else:
            celulas[k] = {c: _falha(INDISPONIVEL) for c in _CHAVES_EMPRESA}
            financeira_de[k] = eh_financeiro(subsetor_de.get(k), params)
        if tipo_de.get(k) == "BDR":  # D9: razão BDR/ação desconhecida, sempre indisponível
            for c in _BDR_INDISPONIVEL:
                celulas[k][c] = _falha(INDISPONIVEL)
        celulas[k]["dividend_yield.valor"] = dividend_yield(
            ligados, k, tipo_de.get(k), fech.get(k), ts, params.meses_janela
        )

    cnpjs_fora = {cnpj_de[k] for k in fora_do_setor_preco if cnpj_de.get(k)}
    excluir = {k for k in tickers
               if k in fora_do_setor_preco or (cnpj_de.get(k) is not None and cnpj_de.get(k) in cnpjs_fora)}
    for campo, origem in _ORIGEM_SETOR.items():
        tira = excluir if campo in _SETOR_COM_PRECO else set()
        bruta = _grade_do_dia(ts, tickers, {k: (_falha(INDISPONIVEL) if k in tira else celulas[k][origem])
                                            for k in tickers})
        media = media_setor(montar_grade(bruta.valor, bruta.status), pares, setor_de, cnpj_de, modo_setor,
                            agregacao="mediana")
        for k in tickers:
            valor, status = media.valor.iloc[0][k], media.status.iloc[0][k]
            if status == HIST:
                valor, status = math.nan, INDISPONIVEL
            if campo in _SETOR_SEM_FINANCEIRA and financeira_de[k]:
                valor, status = math.nan, NAO_SE_APLICA
            celulas[k][campo] = (float(valor), status)

    return {campo: _grade_do_dia(ts, tickers, {k: celulas[k][campo] for k in tickers}) for campo in INDICADORES}


def _cnpjs_com_quantidade_suspeita(ts: pd.Timestamp, dados: DadosFundamentos, exclusoes: Exclusoes,
                                   params: ParametrosFundamentos) -> set[str]:
    """CNPJs do painel cuja quantidade de ações é suspeita em `ts` (mesma conta de `calcular_fundamentos_no_dia`)."""
    tickers = tickers_do_painel(dados.cadastro, exclusoes)
    _, cnpj_de = mapas_cadastro(dados.cadastro)
    fech = grade_de_precos(dados.precos, [ts], "fechamento", tickers).iloc[0].to_dict()
    disp = acoes_disponiveis(dados.acoes_emitidas, dados.balancos, ts)
    suspeitas = set()
    for cnpj in {cnpj_de[k] for k in tickers if cnpj_de.get(k)}:
        vm = valor_de_mercado(cnpj, fech, dados.cadastro, tickers, acoes_na_data(disp, cnpj, ts))
        foto = foto_balanco(dados.balancos, cnpj, ts, exclusoes)
        if quantidade_suspeita(vm, foto, params.pvp_minimo_plausivel, params.pvp_maximo_plausivel_x1000):
            suspeitas.add(cnpj)
    return suspeitas


def _payout_das_dfps(ts: pd.Timestamp, cnpj: str, dados: DadosFundamentos, exclusoes: Exclusoes,
                     params: ParametrosFundamentos, ligados: pd.DataFrame,
                     disp: pd.DataFrame, suspeita: bool = False) -> list[tuple[int, float, str]]:
    """(ano, payout, status) das últimas `anos_payout` DFPs do CNPJ entregues até `ts`.

    Com `suspeita` (quantidade de ações suspeita em `ts`) todas saem indisponíveis, como em `indicadores_empresa`.
    """
    if foto_balanco(dados.balancos, cnpj, ts, exclusoes).status_base != OK:
        return []
    entregues = entregues_ate(dados.balancos, ts)
    do_cnpj = entregues[entregues["cnpj"] == cnpj]
    anuais = do_cnpj[pd.Series(
        [meses_do_periodo(i, f) == 12 for i, f in zip(do_cnpj["data_inicio_periodo"], do_cnpj["data_fim_periodo"])],
        index=do_cnpj.index, dtype=bool,
    )]
    saida = []
    for fim in sorted({pd.Timestamp(f) for f in anuais["data_fim_periodo"]})[-params.anos_payout:]:
        linha = anuais[anuais["data_fim_periodo"] == fim].sort_values("data_entrega").iloc[-1]
        lucro = linha["lucro_liquido"]
        if suspeita or pd.isna(lucro):
            valor, status = math.nan, INDISPONIVEL
        elif lucro <= 0:
            valor, status = math.nan, LUCRO_NEGATIVO
        else:
            inicio = pd.Timestamp(linha["data_inicio_periodo"]) - pd.Timedelta(days=1)
            pago, status_pago = total_pago(ligados, disp, cnpj, inicio, fim)
            valor, status = (pago / lucro, OK) if status_pago == OK else (math.nan, INDISPONIVEL)
        saida.append((fim.year, valor, status))
    return saida


def payout_por_ano(t, dados: DadosFundamentos, exclusoes: Exclusoes, params: ParametrosFundamentos) -> pd.DataFrame:
    """Payout de cada DFP entregue até `t` (últimas `anos_payout`, seção 6).

    Por DFP: L é o lucro líquido da própria DFP. L ≤ 0 sai `lucro_negativo`; senão o total pago
    com data_com em (início da DFP − 1 dia, fim da DFP] dividido por L. Só tickers ON, PN ou UNIT
    com CNPJ e base ok; empresa só com BDR fica sem linhas. Colunas: ticker, ano, valor, status.
    """
    ts = pd.Timestamp(t).normalize()
    pares = pares_do_painel(dados.cadastro, exclusoes)
    _, cnpj_de = mapas_cadastro(dados.cadastro)
    ligados = ligar_proventos(dados.proventos, dados.cadastro, dados.mudancas)
    disp = acoes_disponiveis(dados.acoes_emitidas, dados.balancos, ts)

    suspeitas = _cnpjs_com_quantidade_suspeita(ts, dados, exclusoes, params)
    por_cnpj: dict[str, list[tuple[int, float, str]]] = {}
    registros = []
    for ticker in pares:
        cnpj = cnpj_de.get(ticker)
        if not cnpj:
            continue
        if cnpj not in por_cnpj:
            por_cnpj[cnpj] = _payout_das_dfps(ts, cnpj, dados, exclusoes, params, ligados, disp,
                                              suspeita=cnpj in suspeitas)
        for ano, valor, status in por_cnpj[cnpj]:
            registros.append({"ticker": ticker, "ano": ano, "valor": valor, "status": status})
    return (
        pd.DataFrame(registros, columns=["ticker", "ano", "valor", "status"])
        .sort_values(["ticker", "ano"])
        .reset_index(drop=True)
    )


def balanco_referencia_no_dia(t, dados: DadosFundamentos, exclusoes: Exclusoes) -> pd.DataFrame:
    """Balanço de referência de cada ticker do painel em `t` (ver `trimestres.foto_balanco`).

    Colunas: ticker, data_fim_periodo, data_entrega, status (ok, historico_insuficiente ou
    indisponivel). Sem balanço utilizável, as datas saem None.
    """
    ts = pd.Timestamp(t).normalize()
    _, cnpj_de = mapas_cadastro(dados.cadastro)
    registros = []
    for ticker in tickers_do_painel(dados.cadastro, exclusoes):
        foto = foto_balanco(dados.balancos, cnpj_de.get(ticker), ts, exclusoes)
        registros.append({
            "ticker": ticker,
            "data_fim_periodo": foto.data_fim_periodo,
            "data_entrega": foto.data_entrega,
            "status": foto.status_base,
        })
    return pd.DataFrame(registros, columns=["ticker", "data_fim_periodo", "data_entrega", "status"])


# ---------------------------------------------------------------------------
# F4: tabela trimestral (pacote 5 da seção 8.3)
# ---------------------------------------------------------------------------

CAMPOS_TRIMESTRAIS = (
    "receita_trimestre", "receita_12m", "lucro_liquido_trimestre", "lucro_liquido_12m",
    "margem_bruta", "margem_liquida", "roe", "ebitda_trimestre", "ebitda_12m",
    "margem_ebitda", "divida_liquida", "dl_pl", "dl_ebitda", "payout_12m",
)

_COLUNAS_TABELA_TRIMESTRAL = [
    "ticker", "cnpj", "data_fim_periodo", "data_entrega",
    *(c for campo in CAMPOS_TRIMESTRAIS for c in (campo, f"{campo}_status")),
]


def _ebitda_trimestre(foto: FotoBalanco, financeiro: bool) -> tuple[float, str]:
    """EBITDA do trimestre (ebit + D&A do próprio trimestre); empresa financeira sai nao_se_aplica."""
    if financeiro:
        return _falha(NAO_SE_APLICA)
    ebit, ebit_s = foto.fluxo_trimestre["ebit"]
    da, da_s = foto.fluxo_trimestre["depreciacao_amortizacao"]
    falha = _primeiro_nao_ok(foto.status_base, ebit_s, da_s)
    return _falha(falha) if falha else (ebit + da, OK)


def _linhas_da_empresa(ts: pd.Timestamp, cnpj: str, dados: DadosFundamentos, exclusoes: Exclusoes,
                       params: ParametrosFundamentos, ligados: pd.DataFrame, disp: pd.DataFrame,
                       com_classe_paga: bool, financeiro: bool, suspeita: bool = False) -> list[dict]:
    """Uma linha por trimestre entregue até `ts` da empresa (sem o ticker), com os pares (valor, status).

    Empresa sem base ok em `ts` não gera linha. O payout de 12 meses fica indisponível quando a
    empresa só tem BDR no painel (`com_classe_paga` falso) ou quando a quantidade de ações é suspeita (`suspeita`).
    """
    if foto_balanco(dados.balancos, cnpj, ts, exclusoes).status_base != OK:
        return []
    trimestres = trimestres_isolados(dados.balancos[dados.balancos["cnpj"] == cnpj], ts)
    linhas = []
    for _, linha in trimestres.iterrows():
        fim = linha["data_fim_periodo"]
        foto = foto_balanco(dados.balancos, cnpj, ts, exclusoes, fim=fim)
        if com_classe_paga and not suspeita:
            pago = total_pago(ligados, disp, cnpj, inicio_janela(fim, params.meses_janela), fim)
        else:
            pago = _falha(INDISPONIVEL)
        ind = indicadores_empresa(foto, _falha(INDISPONIVEL), pago, financeiro)
        linhas.append({
            "data_fim_periodo": fim,
            "data_entrega": linha["data_entrega"],
            "receita_trimestre": foto.fluxo_trimestre["receita_liquida"],
            "receita_12m": foto.fluxo_12m["receita_liquida"],
            "lucro_liquido_trimestre": foto.fluxo_trimestre["lucro_liquido"],
            "lucro_liquido_12m": foto.fluxo_12m["lucro_liquido"],
            "margem_bruta": ind["margem_bruta.valor"],
            "margem_liquida": ind["margem_liquida.valor"],
            "roe": ind["roe.valor"],
            "ebitda_trimestre": _ebitda_trimestre(foto, financeiro),
            "ebitda_12m": ind["ebitda.valor_12m"],
            "margem_ebitda": ind["ebitda.margem"],
            "divida_liquida": ind["endividamento.divida_liquida"],
            "dl_pl": ind["endividamento.dl_pl"],
            "dl_ebitda": ind["endividamento.dl_ebitda"],
            "payout_12m": ind["payout.valor"],
        })
    return linhas


def tabela_trimestral(t, dados: DadosFundamentos, exclusoes: Exclusoes,
                      params: ParametrosFundamentos) -> pd.DataFrame:
    """Tabela trimestral de cada ticker do painel com empresa em base ok até `t` (seção 8.3).

    Uma linha por (ticker, trimestre de `trimestres.trimestres_isolados`). Colunas: ticker, cnpj,
    data_fim_periodo, data_entrega e, para cada campo de `CAMPOS_TRIMESTRAIS`, o par `campo` e
    `campo_status`. Ausência é NaN com status diferente de ok. Ordenada por ticker e fim do período.
    Só entram balanços com `data_entrega` ≤ `t` e proventos com `data_com` ≤ `t`.
    """
    ts = pd.Timestamp(t).normalize()
    tickers = tickers_do_painel(dados.cadastro, exclusoes)
    _, cnpj_de = mapas_cadastro(dados.cadastro)
    subsetor_de = dict(zip(dados.cadastro["ticker"], dados.cadastro["subsetor"]))
    pares = pares_do_painel(dados.cadastro, exclusoes)
    cnpjs_com_classe_paga = {cnpj_de[p] for p in pares if cnpj_de.get(p)}
    ligados = ligar_proventos(dados.proventos, dados.cadastro, dados.mudancas)
    disp = acoes_disponiveis(dados.acoes_emitidas, dados.balancos, ts)

    suspeitas = _cnpjs_com_quantidade_suspeita(ts, dados, exclusoes, params)
    por_cnpj: dict[str, list[dict]] = {}
    registros = []
    for ticker in tickers:
        cnpj = cnpj_de.get(ticker)
        if not cnpj:
            continue
        if cnpj not in por_cnpj:
            financeiro = any(
                eh_financeiro(subsetor_de.get(k), params) for k in tickers if cnpj_de.get(k) == cnpj
            )
            por_cnpj[cnpj] = _linhas_da_empresa(
                ts, cnpj, dados, exclusoes, params, ligados, disp,
                cnpj in cnpjs_com_classe_paga, financeiro, suspeita=cnpj in suspeitas,
            )
        for linha in por_cnpj[cnpj]:
            registro = {"ticker": ticker, "cnpj": cnpj, "data_fim_periodo": linha["data_fim_periodo"],
                        "data_entrega": linha["data_entrega"]}
            for campo in CAMPOS_TRIMESTRAIS:
                valor, status = linha[campo]
                registro[campo] = float(valor)
                registro[f"{campo}_status"] = status
            registros.append(registro)
    tabela = pd.DataFrame(registros, columns=_COLUNAS_TABELA_TRIMESTRAL)
    return tabela.sort_values(["ticker", "data_fim_periodo"]).reset_index(drop=True)
