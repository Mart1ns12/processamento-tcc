"""Pacote `noticias_dia` (plano da etapa 7, Fase 6c; seções 4.7 e 2.1).

Um registro por ticker do painel, com a janela do painel = a mesma do modelo (de 08:00:01 de t até 08:00 de D).
Notícia da empresa vale para todas as suas ações. Funções puras sobre `Insumos`: nenhuma lê banco ou rede.
"""

from __future__ import annotations

import pandas as pd

from processamento import calendario, tickers
from processamento.experimento.parametros import ParametrosExperimento, mascara_sem_coleta
from processamento.fatos import noticias as fatos_noticias
from processamento.fatos.precos import mapas_cadastro, tickers_do_painel
from processamento.saida import contrato
from processamento.saida.insumos import Insumos


def janela_do_dia(ins: Insumos, params_exp: ParametrosExperimento) -> pd.DataFrame:
    """Notícias de t na janela do painel, com `t` e `D` de `ins` (ponto de vista de D)."""
    _, cnpj_de = mapas_cadastro(ins.cadastro)
    return fatos_noticias.noticias_da_janela(
        ins.noticias, ins.cal, ins.t, ins.d, cnpj_de, ins.mudancas, params_exp
    )


def montar_noticias_dia(
    ins: Insumos, janela: pd.DataFrame, gerado_em: str, dados_ate: str, periodos_sem_coleta: tuple = ()
) -> list[dict]:
    """Um registro por ticker do painel (ordem alfabética), com `resumo` e `itens` no formato do contrato.

    Pregão t em período sem coleta fica como antes da cobertura: tudo `indisponivel`, nunca zero.
    """
    _, cnpj_de = mapas_cadastro(ins.cadastro)
    coberta = _coberta(ins) and not mascara_sem_coleta([ins.t], periodos_sem_coleta)[0]
    inicio_janela = calendario.corte_manha(ins.t) + pd.Timedelta(seconds=1)
    registros = []
    for ticker in tickers_do_painel(ins.cadastro, ins.exclusoes):
        cnpj, _ = tickers.ligar_a_cnpj(ticker, cnpj_de, ins.mudancas)
        ordenado = fatos_noticias.destaque(janela[janela["empresa"] == (cnpj or ticker)])
        resumo = fatos_noticias.resumo_noticias(ordenado, coberta)
        registros.append({
            **contrato.meta(gerado_em, dados_ate),
            "data_referencia": contrato.data_txt(ins.t),
            "ticker": ticker,
            "janela_inicio": contrato.data_hora_txt(inicio_janela),
            "janela_fim": contrato.data_hora_txt(calendario.corte_manha(ins.d)),
            "resumo": {chave: _folha_resumo(chave, valor, status) for chave, (valor, status) in resumo.items()},
            "itens": [_item(linha) for _, linha in ordenado.iterrows()] if coberta else [],
        })
    return registros


def _coberta(ins: Insumos) -> bool:
    """t não é anterior ao início da cobertura (menor `data_publicacao` de `ins.noticias`).

    Sem nenhuma notícia lida não há como afirmar cobertura: fica "não coberta" (indisponível), não zero.
    """
    datas = pd.to_datetime(ins.noticias["data_publicacao"]).dropna()
    if datas.empty:
        return False
    return pd.Timestamp(ins.t) >= datas.min().normalize()


def _folha_resumo(chave: str, valor: float, status: str) -> dict:
    """Folha do resumo; contagens inteiras quando `ok` (tom_medio fica número)."""
    if chave != "tom_medio" and status == "ok":
        valor = int(valor)
    return contrato.folha(valor, status)


def _texto_ou_nulo(valor: object) -> str | None:
    return None if pd.isna(valor) else str(valor)


def _item(linha: pd.Series) -> dict:
    """Uma notícia do `itens`, na ordem do destaque (campos da seção 4.7)."""
    return {
        "id": str(linha["id"]),
        "titulo": str(linha["titulo"]),
        "fonte": _texto_ou_nulo(linha["fonte"]),
        "link": _texto_ou_nulo(linha["link"]),
        "publicado_em": contrato.data_hora_txt(linha["publicado_em"]),
        "data_publicacao": contrato.data_txt(linha["data_publicacao"]),
        "precisao_hora": str(linha["precisao_hora"]),
        "janela": str(linha["janela"]),
        "rotulo": _texto_ou_nulo(linha["rotulo"]),
        "prob_positivo": contrato.numero(linha["prob_positivo"]),
        "prob_neutro": contrato.numero(linha["prob_neutro"]),
        "prob_negativo": contrato.numero(linha["prob_negativo"]),
        "destaque": int(linha["destaque"]),
        "status": str(linha["status"]),
    }
