"""Fábrica para os testes da saída (tests/test_saida_contrato.py): insumos do banco de teste e
registros mínimos válidos de cada pacote, montados a partir da seção 4 do plano (etapa 7).

Cenário: D = 2025-10-22, t = 2025-10-21 (banco de teste tests/dados). Nenhuma função usa banco ou rede.
"""

from __future__ import annotations

from datetime import date, datetime

from processamento import fontes
from processamento.saida.contrato import folha, folha_bool, folha_data, folha_texto
from processamento.saida.insumos import ler_insumos

AGORA = datetime(2025, 10, 22, 9, 0, tzinfo=fontes.SP)
GERADO = "2025-10-22T09:00:00-03:00"
DADOS_ATE = "2025-10-22T08:00:00-03:00"
STATUS_HIST = "historico_insuficiente"


def insumos_de_teste(ler, d: date = date(2025, 10, 22)):
    """Insumos da rodada de `d` lidos pelo leitor `ler` (use `banco_teste()` do conftest)."""
    return ler_insumos(d, ler, existe_composicao=False)


def _meta() -> dict:
    return {"versao_contrato": "1.0", "gerado_em": GERADO, "dados_ate": DADOS_ATE}


def _janelas_nulas() -> dict:
    return {k: folha(None, "indisponivel") for k in ("d1", "m1", "m6", "a1")}


def _janelas_hist(d1: dict) -> dict:
    return {"d1": d1, "m1": folha(None, STATUS_HIST), "m6": folha(None, STATUS_HIST), "a1": folha(None, STATUS_HIST)}


def _serie_taee11() -> dict:
    datas = ["2025-10-16", "2025-10-17", "2025-10-20", "2025-10-21"]
    pl = 6.896551724137931
    pvp = 0.8333333333333334
    sem = {"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}
    return {
        **_meta(), "ticker": "TAEE11", "tipo": "acao", "nome": "TAESA", "substituir_serie": True,
        "inicio_janela": "2025-10-16", "datas": datas,
        "valores": {
            "fechamento": [10.0, 10.0, None, 10.0],
            "indice_retorno_total": [100.0, 100.0, None, 100.0],
            "volume": [1000.0, 1000.0, None, 1000.0],
            "pl": [pl, pl, None, pl],
            "pvp": [pvp, pvp, None, pvp],
            "dividend_yield": [0.09, 0.09, None, 0.09],
        },
        "status": {c: [dict(sem)] for c in ("fechamento", "indice_retorno_total", "volume", "pl", "pvp",
                                             "dividend_yield")},
    }


def _resumo_petr4() -> dict:
    sub_nulo = folha(None, "indisponivel")
    return {
        **_meta(), "data_referencia": "2025-10-21", "ticker": "PETR4",
        "cotacao": {"fechamento": folha(10.0, "ok"), "variacao_dia": folha(0.0, "ok")},
        "variacao_preco": {**_janelas_hist(folha(0.0, "ok")), "s1": folha(None, STATUS_HIST)},
        "rentabilidade": {**_janelas_hist(folha(0.0, "ok")), "s1": folha(None, STATUS_HIST),
                          "ibov": _janelas_hist(folha(0.0, "ok")), "setor": _janelas_nulas()},
        "volume": {"total": folha(1000.0, "ok"), "relativo": {"valor": None, "status": STATUS_HIST, "texto": None},
                   "mediana_20": folha(None, STATUS_HIST), "posicao_pct": folha(None, STATUS_HIST)},
        "volatilidade_20d": {"valor": None, "status": STATUS_HIST, "texto": None,
                             "posicao_pct": folha(None, STATUS_HIST)},
        "beta": {"valor": None, "status": STATUS_HIST, "texto": None},
        "pl": {"valor": 6.896551724137931, "status": "ok", "texto": None, "setor": sub_nulo},
        "pvp": {**folha(0.8333333333333334, "ok"), "setor": sub_nulo},
        "roe": {**folha(0.12083333333333333, "ok"), "setor": sub_nulo},
        "dividend_yield": {**folha(0.05, "ok"), "setor": sub_nulo},
        "payout": {**folha(0.3448275862068966, "ok"), "setor": sub_nulo},
        "margem_bruta": {**folha(0.3900709219858156, "ok"), "setor": sub_nulo},
        "margem_liquida": {**folha(0.10283687943262411, "ok"), "setor": sub_nulo},
        "payout_por_ano": [{"ano": 2024, **folha(0.2153846153846154, "ok")}],
        "proventos_por_ano": [{"ano": ano, **folha(v, "ok")} for ano, v in
                              ((2021, 0.0), (2022, 0.0), (2023, 0.0), (2024, 0.7), (2025, 0.5))],
        "ebitda": {"rotulo": "EBITDA (cálculo padrão CVM)", "valor_12m": sub_nulo,
                   "margem": folha(None, "indisponivel"), "setor_margem": folha(None, "indisponivel")},
        "endividamento": {
            "divida_liquida": folha(None, "indisponivel"), "dl_pl": folha(None, "indisponivel"),
            "dl_ebitda": folha(None, "indisponivel"), "caixa_liquido": folha_bool(None, "indisponivel"),
            "setor_dl_pl": folha(None, "indisponivel"), "setor_dl_ebitda": folha(None, "indisponivel"),
            "aviso": "Dívida líquida sem arrendamentos.",
        },
        "setor_comparacao_fraca": True,
        "balanco_referencia": {"data_fim_periodo": "2025-06-30", "data_entrega": "2025-08-10", "status": "ok"},
    }


def _experimento_top() -> dict:
    motivos = [
        {"fator": f"fator {i}", "valor": None, "efeito": "neutro", "texto": f"Motivo {i} em texto."}
        for i in range(1, 4)
    ]
    return {
        **_meta(), "data_referencia": "2025-10-22", "pregao_previsto": "2025-10-22", "pregao_base": "2025-10-21",
        "valido_para_historico": False, "modelo_versao": "xgb-2026-06", "modelo_provisorio": True,
        "universo": "composicao_atual", "n_candidatas": 4, "selo": "em_avaliacao",
        "titulo": "5 ações com maior chance de superar o Ibovespa (experimento)",
        "aviso_fixo": "Não constitui recomendação de investimento.",
        "avisos": ["Modelo provisório: treinado com cerca de 1 ano de dados, só para testar a rotina."],
        "ranking": [{
            "posicao": 1, "ticker": "PETR4",
            "chance": {"valor": None, "referencia_acaso": None, "exibir": False, "status": "calibracao_nao_conferida"},
            "motivos": motivos, "noticias_usadas": ["n000008"],
        }],
    }


def exemplo(pacote: str) -> dict:
    """Registro mínimo válido do pacote (um novo a cada chamada, pode ser alterado nos testes)."""
    if pacote == "acoes":
        return {**_meta(), "ticker": "PETR4", "empresa": "PETROBRAS", "setor": "Petroleo",
                "subsetor": "Petroleo e gas", "tipo_acao": "PN", "ativo_no_universo": True}
    if pacote == "mercado_dia":
        return {
            **_meta(), "data_referencia": "2025-10-21",
            "IBOV": {"fechamento": folha(10.0, "ok"), "variacao_dia": folha(0.0, "ok"), "unidade": "pontos"},
            "USDBRL": {"fechamento": folha(None, "indisponivel"), "variacao_dia": folha(None, "indisponivel"),
                       "unidade": "BRL/USD"},
            "BRENT": {"fechamento": folha(None, "indisponivel"), "variacao_dia": folha(None, "indisponivel"),
                      "unidade": "USD/barril"},
            "cdi_dia": folha(0.0006, "ok"), "cdi_data": "2025-10-21",
            "ipca_12m": folha(None, STATUS_HIST), "ipca_ate": folha_texto("2025-09", "ok"),
            "selic_meta": folha(0.15, "ok"), "selic_data": "2025-10-21",
            "indices": {
                "CDI": _janelas_hist(folha(0.0005, "ok")),
                "IPCA": _janelas_hist(folha(0.0, "ok")),
                "IDIV": _janelas_hist(folha(0.01, "ok")),
                "SMLL": _janelas_nulas(), "IFIX": _janelas_nulas(), "IVVB11": _janelas_nulas(),
                "USDBRL": _janelas_nulas(), "BRENT": _janelas_hist(folha(0.0, "ok")),
            },
            "ipca_mensal": [{"mes_ref": "2025-09", "variacao": folha(0.01, "ok")}],
            "cdi_mensal": [{"mes_ref": "2025-09", "variacao": folha(None, STATUS_HIST)}],
        }
    if pacote == "resumo_acao":
        return _resumo_petr4()
    if pacote == "series_diarias":
        return _serie_taee11()
    if pacote == "fundamentos_trimestrais":
        valores = {
            "receita_trimestre": folha(360.0, "ok"), "receita_12m": folha(1410.0, "ok"),
            "lucro_liquido_trimestre": folha(40.0, "ok"), "lucro_liquido_12m": folha(145.0, "ok"),
            "margem_bruta": folha(0.3900709219858156, "ok"), "margem_liquida": folha(0.10283687943262411, "ok"),
            "roe": folha(0.12083333333333333, "ok"),
            "payout_12m": folha(0.19310344827586207, "ok"),
        }
        for campo in ("ebitda_trimestre", "ebitda_12m", "margem_ebitda", "divida_liquida", "dl_pl", "dl_ebitda"):
            valores[campo] = folha(None, "indisponivel")
        return {**_meta(), "ticker": "PETR4", "data_fim_periodo": "2025-06-30", "data_entrega": "2025-08-10",
                **valores}
    if pacote == "proventos":
        return {**_meta(), "ticker": "PETR4", "tipo": "DIVIDENDO", "data_com": "2025-08-20",
                "data_pagamento": folha_data("2025-09-10", "ok"), "valor_por_acao": folha(0.5, "ok")}
    if pacote == "noticias_dia":
        item = {
            "id": "n000008", "titulo": "Petrobras anuncia investimento", "fonte": "Fonte exemplo",
            "link": "https://exemplo.invalid/noticia-8", "publicado_em": "2025-10-21T09:00:00-03:00",
            "data_publicacao": "2025-10-21", "precisao_hora": "hora", "janela": "pregao", "rotulo": "neutro",
            "prob_positivo": 0.2, "prob_neutro": 0.5, "prob_negativo": 0.3, "destaque": 1, "status": "ok",
        }
        return {
            **_meta(), "data_referencia": "2025-10-21", "ticker": "PETR4",
            "janela_inicio": "2025-10-21T08:00:01-03:00", "janela_fim": "2025-10-22T08:00:00-03:00",
            "resumo": {"quantidade": folha(1, "ok"), "positivas": folha(0, "ok"), "neutras": folha(1, "ok"),
                       "negativas": folha(0, "ok"), "tom_medio": folha(-0.1, "ok")},
            "itens": [item],
        }
    if pacote == "experimento_top":
        return _experimento_top()
    if pacote == "experimento_historico":
        return {
            **_meta(), "data_referencia": "2025-10-22", "dia": None,
            "resumo": {
                "periodo_inicio": None, "periodo_fim": None, "n_dias": 0,
                "taxa_acerto": folha(None, "indisponivel"), "acaso_media": folha(None, "indisponivel"),
                "acaso_faixa": None, "universo": "composicao_atual",
                "nota": ("Histórico calculado com as ações que compõem o Ibovespa atualmente. "
                         "O histórico começa na entrada em produção (teste ao vivo). "
                         "Antes disso, os top 5 são testes de funcionamento e não entram aqui."),
            },
        }
    if pacote == "execucao":
        return {
            **_meta(), "data_referencia": "2025-10-22", "rodada": 1, "inicio": GERADO, "fim": None,
            "status": "em_andamento",
            "coleta_status": {"consultado": False, "nota": "gatilho da coleta não consultado (etapa 8)"},
            "pacotes_enviados": [], "avisos": [],
        }
    raise KeyError(f"pacote sem exemplo: {pacote!r}")
