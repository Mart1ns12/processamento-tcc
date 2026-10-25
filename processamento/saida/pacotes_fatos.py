"""Montagem dos pacotes da saída que vêm dos fatos: acoes, mercado_dia, resumo_acao,
fundamentos_trimestrais e proventos (plano da etapa 7, fase 6a; seção 4).

As contas são as dos fatos (`processamento/fatos/`); aqui só se monta o formato do pacote.
- Ponto de vista explícito: toda função usa `ins.t` (nunca `cal[-1]` nem "hoje").
- Ausência vira `folha` com `valor` null e `status` (contrato); nunca 0.
- Não faz SQL: recebe os `Insumos` já cortados por `saida/insumos.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from processamento.fatos.fundamentos import (
    CAMPOS_TRIMESTRAIS,
    DadosFundamentos,
    ParametrosFundamentos,
    balanco_referencia_no_dia,
    calcular_fundamentos_no_dia,
    payout_por_ano,
    tabela_trimestral,
)
from processamento.fatos.indices import INDICES, calcular_indices, cdi_dia, ipca_12m, ipca_ate
from processamento.fatos.precos import (
    Grade,
    ParametrosPrecos,
    calcular_precos,
    carregar_parametros_precos,
    grade_de_precos,
    resumo_precos_no_dia,
    tickers_com_suspeita,
    tickers_do_painel,
    variacao,
)
from processamento.fatos.proventos import ligar_proventos, lista_proventos, soma_por_ano
from processamento.saida import contrato, textos
from processamento.saida.insumos import Insumos

JANELAS = ("d1", "m1", "m6", "a1")
TRIMESTRES_NO_PACOTE = 8  # S19: os 8 trimestres entregues mais recentes de cada ticker
AVISO_DIVIDA = "Dívida líquida sem arrendamentos."
ROTULO_EBITDA = "EBITDA (cálculo padrão CVM)"


@dataclass(frozen=True)
class GradesDoDia:
    """Grades calculadas uma vez por rodada (gerar.py) e passadas aos montadores."""

    precos: dict[str, Grade]       # calcular_precos(...): chave = indicador de preço (ex.: "cotacao.fechamento")
    indices: dict[str, Grade]      # calcular_indices(...): chave = janela (d1, m1, m6, a1); colunas = INDICES
    fundamentos: dict[str, Grade]  # calcular_fundamentos_no_dia(...): chave = indicador (INDICADORES)


def dados_fundamentos(ins: Insumos) -> DadosFundamentos:
    """Tabelas dos fundamentos já cortadas por t (`proventos` com os tickers originais)."""
    return DadosFundamentos(
        precos=ins.precos,
        cadastro=ins.cadastro,
        balancos=ins.balancos,
        acoes_emitidas=ins.acoes_emitidas,
        proventos=ins.proventos,
        mudancas=ins.mudancas,
    )


def calcular_grades(ins: Insumos, params_precos: ParametrosPrecos, params_fund: ParametrosFundamentos) -> GradesDoDia:
    """Calcula as três grades da rodada no ponto de vista de `ins.t`."""
    fora = tickers_com_suspeita(ins.precos, ins.cal, ins.t, tickers_do_painel(ins.cadastro, ins.exclusoes),
                                params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max,
                                params_precos.retorno_suspeito_pregoes_nivel,
                                params_precos.base_defasagem_max_pregoes)
    return GradesDoDia(
        precos=calcular_precos(ins.precos, ins.cadastro, ins.cal, ins.exclusoes, params_precos),
        indices=calcular_indices(ins.precos, ins.indices, ins.cal, params_precos),
        fundamentos=calcular_fundamentos_no_dia(
            ins.t, ins.cal, dados_fundamentos(ins), ins.exclusoes, params_fund, params_precos.setor_excluir,
            fora_do_setor_preco=frozenset(fora),
        ),
    )


# ---------------------------------------------------------------- auxiliares

def _ts(ins: Insumos) -> pd.Timestamp:
    return pd.Timestamp(ins.t).normalize()


def _texto(x: object) -> str | None:
    """Texto do cadastro; NaN e vazio viram None (campo de cadastro, sem status)."""
    if pd.isna(x) or str(x).strip() == "":
        return None
    return str(x)


def _status_de(valor: object) -> str:
    """`ok` quando há valor; `indisponivel` quando o dado veio vazio."""
    return "indisponivel" if pd.isna(valor) else "ok"


def _folha_celula(celulas: dict, ticker: str, indicador: str) -> dict:
    """Folha `{valor, status}` de um (ticker, indicador) já calculado em t."""
    valor, status = celulas[(ticker, indicador)]
    return contrato.folha(valor, status)


def _celulas_do_dia(ins: Insumos, grades: GradesDoDia) -> dict[tuple[str, str], tuple[float, str]]:
    """(ticker, indicador) -> (valor, status) de t, juntando grades de preço e de fundamentos."""
    celulas: dict[tuple[str, str], tuple[float, str]] = {}
    for grade_por_indicador in (grades.precos, grades.fundamentos):
        for linha in resumo_precos_no_dia(grade_por_indicador, ins.t).to_dict("records"):
            celulas[(linha["ticker"], linha["indicador"])] = (linha["valor"], linha["status"])
    return celulas


def _cadastro_por_ticker(ins: Insumos) -> dict[str, dict]:
    return {linha["ticker"]: linha for linha in ins.cadastro.to_dict("records")}


# ---------------------------------------------------------------- acoes

def montar_acoes(ins: Insumos, universo_t: pd.DataFrame, gerado_em: str, dados_ate: str) -> list[dict]:
    """Um registro por ticker do painel (seção 4.1). `universo_t`: linhas de t de `montar_universo`."""
    # S16: sem preço em t (`sem_preco`) ainda conta como ativo do universo; só `tipo_nao_aceito` etc. ficam de fora.
    ativo = {linha["ticker"]: linha["motivo"] in ("ok", "sem_preco") for linha in universo_t.to_dict("records")}
    cadastro = _cadastro_por_ticker(ins)
    registros = []
    for ticker in tickers_do_painel(ins.cadastro, ins.exclusoes):
        linha = cadastro[ticker]
        registros.append({
            **contrato.meta(gerado_em, dados_ate),
            "ticker": ticker,
            "empresa": _texto(linha["empresa"]),
            "setor": _texto(linha["setor"]),
            "subsetor": _texto(linha["subsetor"]),
            "tipo_acao": linha["tipo_acao"],
            "ativo_no_universo": ativo.get(ticker, False),
        })
    return registros


# ---------------------------------------------------------------- mercado_dia

def _cotacao_de_indice(ins: Insumos, ticker: str, unidade: str, defasagem_max: int | None = None) -> dict:
    """IBOV, USDBRL ou BRENT em t: fechamento, variação do dia (base as-of) e unidade."""
    ts = _ts(ins)
    g_fech = grade_de_precos(ins.precos, ins.cal, "fechamento", [ticker])
    var = variacao(g_fech, 1, defasagem_max)
    fech = g_fech.at[ts, ticker]
    return {
        "fechamento": contrato.folha(fech, _status_de(fech)),
        "variacao_dia": contrato.folha(var.valor.at[ts, ticker], var.status.at[ts, ticker]),
        "unidade": unidade,
    }


def montar_mercado_dia(ins: Insumos, grades: GradesDoDia, gerado_em: str, dados_ate: str,
                       params_precos: ParametrosPrecos | None = None) -> list[dict]:
    """Um registro (seção 4.2): cotações de t, CDI, IPCA e % dos índices por janela."""
    params_precos = carregar_parametros_precos() if params_precos is None else params_precos
    n_max = params_precos.base_defasagem_max_pregoes
    m_max = params_precos.ipca_defasagem_max_meses
    ts = _ts(ins)
    taxa, status_cdi, data_cdi = cdi_dia(ins.indices, ins.t, ins.cal, n_max)
    ipca, status_ipca = ipca_12m(ins.indices, ins.t, m_max)
    ate = ipca_ate(ins.indices, ins.t)
    indices = {
        indice: {
            janela: contrato.folha(grades.indices[janela].valor.at[ts, indice],
                                   grades.indices[janela].status.at[ts, indice])
            for janela in JANELAS
        }
        for indice in INDICES
    }
    return [{
        **contrato.meta(gerado_em, dados_ate),
        "data_referencia": contrato.data_txt(ins.t),
        "IBOV": _cotacao_de_indice(ins, "IBOV", "pontos", n_max),
        "USDBRL": _cotacao_de_indice(ins, "USDBRL", "BRL/USD", n_max),
        "BRENT": _cotacao_de_indice(ins, "BRENT", "USD/barril", n_max),
        "cdi_dia": contrato.folha(taxa, status_cdi),
        "cdi_data": contrato.data_txt(data_cdi),
        "ipca_12m": contrato.folha(ipca, status_ipca),
        "ipca_ate": (contrato.folha_texto(ate, "ok") if ate is not None
                     else contrato.folha_texto(None, "indisponivel")),
        "indices": indices,
    }]


# ---------------------------------------------------------------- resumo_acao

def _janelas(celulas: dict, ticker: str, prefixo: str) -> dict:
    return {j: _folha_celula(celulas, ticker, f"{prefixo}.{j}") for j in JANELAS}


def _com_setor(celulas: dict, ticker: str, nome: str) -> dict:
    """Indicador da empresa com a sub-folha `setor` (média do setor)."""
    return {**_folha_celula(celulas, ticker, f"{nome}.valor"),
            "setor": _folha_celula(celulas, ticker, f"{nome}.setor")}


def _bool_de(celulas: dict, ticker: str, indicador: str) -> bool:
    """Flag de 0/1 do cálculo (ex.: caixa_liquido, setor_comparacao_fraca) virando true/false."""
    valor, _ = celulas[(ticker, indicador)]
    return bool(valor)


def montar_resumo_acao(ins: Insumos, grades: GradesDoDia, params_fund: ParametrosFundamentos,
                       gerado_em: str, dados_ate: str) -> list[dict]:
    """Um registro por ticker do painel em t (seção 4.3). Nomes internos: ver `_celulas_do_dia`."""
    ts = _ts(ins)
    celulas = _celulas_do_dia(ins, grades)
    dados = dados_fundamentos(ins)
    cadastro = _cadastro_por_ticker(ins)
    pagos = payout_por_ano(ins.t, dados, ins.exclusoes, params_fund)
    ligados = ligar_proventos(ins.proventos, ins.cadastro, ins.mudancas)
    balancos = balanco_referencia_no_dia(ins.t, dados, ins.exclusoes).set_index("ticker")
    registros = []
    for ticker in tickers_do_painel(ins.cadastro, ins.exclusoes):
        tipo = cadastro[ticker]["tipo_acao"]
        volume_rel = _folha_celula(celulas, ticker, "volume.relativo")
        volat = _folha_celula(celulas, ticker, "volatilidade_20d.valor")
        volat_pos = _folha_celula(celulas, ticker, "volatilidade_20d.posicao_pct")
        beta = _folha_celula(celulas, ticker, "beta.valor")
        pl = _folha_celula(celulas, ticker, "pl.valor")
        pagos_t = pagos[pagos["ticker"] == ticker]
        soma = soma_por_ano(ligados, ticker, tipo, ins.t, params_fund.anos_historico_proventos)
        bal = balancos.loc[ticker]
        registros.append({
            **contrato.meta(gerado_em, dados_ate),
            "data_referencia": contrato.data_txt(ins.t),
            "ticker": ticker,
            "cotacao": {
                "fechamento": _folha_celula(celulas, ticker, "cotacao.fechamento"),
                "variacao_dia": _folha_celula(celulas, ticker, "cotacao.variacao_dia"),
            },
            "variacao_preco": _janelas(celulas, ticker, "variacao_preco"),
            "rentabilidade": {
                **_janelas(celulas, ticker, "rentabilidade"),
                "ibov": _janelas(celulas, ticker, "rentabilidade.ibov"),
                "setor": _janelas(celulas, ticker, "rentabilidade.setor"),
            },
            "volume": {
                "total": _folha_celula(celulas, ticker, "volume.total"),
                "relativo": {**volume_rel, "texto": textos.texto_volume(volume_rel["valor"])},
                "mediana_20": _folha_celula(celulas, ticker, "volume.mediana_20"),
                "posicao_pct": _folha_celula(celulas, ticker, "volume.posicao_pct"),
            },
            "volatilidade_20d": {**volat, "texto": textos.texto_volatilidade(volat_pos["valor"]),
                                 "posicao_pct": volat_pos},
            "beta": {**beta, "texto": textos.texto_beta(beta["valor"])},
            "pl": {**pl, "texto": textos.texto_pl(pl["valor"], pl["status"]),
                   "setor": _folha_celula(celulas, ticker, "pl.setor")},
            "pvp": _com_setor(celulas, ticker, "pvp"),
            "roe": _com_setor(celulas, ticker, "roe"),
            "dividend_yield": _com_setor(celulas, ticker, "dividend_yield"),
            "payout": _com_setor(celulas, ticker, "payout"),
            "margem_bruta": _com_setor(celulas, ticker, "margem_bruta"),
            "margem_liquida": _com_setor(celulas, ticker, "margem_liquida"),
            "payout_por_ano": [
                {"ano": int(linha["ano"]), **contrato.folha(linha["valor"], linha["status"])}
                for linha in pagos_t.to_dict("records")
            ],
            "proventos_por_ano": [
                {"ano": int(linha["ano"]), **contrato.folha(linha["valor"], linha["status"])}
                for linha in soma.to_dict("records")
            ],
            "ebitda": {
                "rotulo": ROTULO_EBITDA,
                "valor_12m": _folha_celula(celulas, ticker, "ebitda.valor_12m"),
                "margem": _folha_celula(celulas, ticker, "ebitda.margem"),
                "setor_margem": _folha_celula(celulas, ticker, "ebitda.setor_margem"),
            },
            "endividamento": {
                "divida_liquida": _folha_celula(celulas, ticker, "endividamento.divida_liquida"),
                "dl_pl": _folha_celula(celulas, ticker, "endividamento.dl_pl"),
                "dl_ebitda": _folha_celula(celulas, ticker, "endividamento.dl_ebitda"),
                "caixa_liquido": contrato.folha_bool(*celulas[(ticker, "endividamento.caixa_liquido")]),
                "setor_dl_pl": _folha_celula(celulas, ticker, "endividamento.setor_dl_pl"),
                "setor_dl_ebitda": _folha_celula(celulas, ticker, "endividamento.setor_dl_ebitda"),
                "aviso": AVISO_DIVIDA,
            },
            "setor_comparacao_fraca": _bool_de(celulas, ticker, "setor_comparacao_fraca"),
            "balanco_referencia": {
                "data_fim_periodo": contrato.data_txt(bal["data_fim_periodo"]),
                "data_entrega": contrato.data_txt(bal["data_entrega"]),
                "status": str(bal["status"]),
            },
        })
    return registros


# ---------------------------------------------------------------- fundamentos_trimestrais

def montar_fundamentos_trimestrais(ins: Insumos, params_fund: ParametrosFundamentos,
                                   gerado_em: str, dados_ate: str) -> list[dict]:
    """Os 8 trimestres entregues mais recentes de cada ticker (seção 4.5; S19)."""
    tabela = tabela_trimestral(ins.t, dados_fundamentos(ins), ins.exclusoes, params_fund)
    tabela = tabela.sort_values(["ticker", "data_fim_periodo"]).reset_index(drop=True)
    recentes = tabela.groupby("ticker", sort=True).tail(TRIMESTRES_NO_PACOTE)
    registros = []
    for linha in recentes.to_dict("records"):
        registros.append({
            **contrato.meta(gerado_em, dados_ate),
            "ticker": linha["ticker"],
            "data_fim_periodo": contrato.data_txt(linha["data_fim_periodo"]),
            "data_entrega": contrato.data_txt(linha["data_entrega"]),
            **{campo: contrato.folha(linha[campo], linha[f"{campo}_status"]) for campo in CAMPOS_TRIMESTRAIS},
        })
    return registros


# ---------------------------------------------------------------- proventos

def montar_proventos(ins: Insumos, params_fund: ParametrosFundamentos, gerado_em: str, dados_ate: str) -> list[dict]:
    """Proventos dos tickers do painel com data_com até t, dos últimos 5 anos (seção 4.6; S19).

    `params_fund` entra para o corte de anos (`anos_historico_proventos`), que o plano exige.
    """
    ligados = ligar_proventos(ins.proventos, ins.cadastro, ins.mudancas)
    linhas = lista_proventos(ligados, tickers_do_painel(ins.cadastro, ins.exclusoes), ins.t)
    primeiro_ano = ins.t.year - (params_fund.anos_historico_proventos - 1)
    dentro = linhas[pd.to_datetime(linhas["data_com"]).dt.year >= primeiro_ano]
    registros = []
    for linha in dentro.to_dict("records"):
        pagamento = contrato.data_txt(linha["data_pagamento"])
        registros.append({
            **contrato.meta(gerado_em, dados_ate),
            "ticker": linha["ticker"],
            "tipo": linha["tipo"],
            "data_com": contrato.data_txt(linha["data_com"]),
            "data_pagamento": contrato.folha_data(pagamento, "ok" if pagamento else "indisponivel"),
            "valor_por_acao": contrato.folha(linha["valor_por_acao"], _status_de(linha["valor_por_acao"])),
        })
    return registros
