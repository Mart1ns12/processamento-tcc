"""Leitura dos insumos da saída com os cortes do ponto de vista de D (plano da etapa 7, fase 4; seção 6).

Único módulo novo que lê o banco, e só pelas funções de `fontes.py` (nenhum SQL aqui). Recebe o
leitor `ler` (conexão somente leitura, ou um leitor de teste). Cortes:
- preços com `ate = D − 1 dia`; t = último pregão lido (`cal[-1]`);
- balanços, proventos e índices até t (proventos sem unir as mudanças de ticker: `ligar_proventos` faz isso);
- notícias até `corte_manha(D)`; cadastro, ações emitidas e mudanças de ticker sem corte.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd

from processamento import calendario, fontes
from processamento.exclusoes import Exclusoes, carregar_exclusoes
from processamento.saida import contrato


class ErroSaida(Exception):
    """Insumo que impede a rodada (ex.: não há pregão antes de D). A mensagem diz o que foi encontrado."""


@dataclass(frozen=True)
class Insumos:
    """Tabelas da coleta já cortadas para a rodada de D. `t` é o último pregão antes de D."""

    d: date
    t: date
    cal: list[date]
    precos: pd.DataFrame
    cadastro: pd.DataFrame
    mudancas: dict[str, str]
    balancos: pd.DataFrame
    acoes_emitidas: pd.DataFrame
    proventos: pd.DataFrame
    indices: pd.DataFrame
    noticias: pd.DataFrame
    composicao: pd.DataFrame | None
    exclusoes: Exclusoes
    noticias_ignoradas: dict[str, int] = field(default_factory=dict)   # origem -> notícias descartadas


def ler_insumos(d: date, ler: Callable[..., pd.DataFrame], existe_composicao: bool | None = None) -> Insumos:
    """Lê a coleta pelos cortes da seção 6 do plano. Sem nenhum pregão antes de D: `ErroSaida`."""
    precos = fontes.ler_tabela("precos", ate=d - timedelta(days=1), ler=ler)
    cal = calendario.pregoes(precos)
    if not cal:
        raise ErroSaida(f"nenhum pregão com preço antes de {d}: não há o que gerar")
    t = cal[-1]
    if t >= d:
        raise ErroSaida(f"o último pregão lido ({t}) não é anterior a {d}")
    mudancas = fontes.ler_mudancas(ler)
    noticias = fontes.ler_noticias(ate=calendario.corte_manha(d), ler=ler, com_url_resolvida=True)
    return Insumos(
        d=d,
        t=t,
        cal=cal,
        precos=precos,
        cadastro=fontes.ler_tabela("cadastro", ler=ler),
        mudancas=mudancas,
        balancos=fontes.ler_tabela("balancos", ate=t, ler=ler),
        acoes_emitidas=fontes.ler_tabela("acoes_emitidas", ler=ler),
        proventos=fontes.ler_tabela("proventos", ate=t, ler=ler, unir_mudancas=False),
        indices=fontes.ler_tabela("indices", ate=t, ler=ler),
        noticias=noticias,
        composicao=fontes.ler_composicao(ler=ler, existe=existe_composicao),
        exclusoes=carregar_exclusoes(),
        noticias_ignoradas=dict(noticias.attrs.get("origens_ignoradas", {})),
    )


def instantes(ins: Insumos, agora: datetime) -> tuple[str, str]:
    """(gerado_em, dados_ate) da rodada em texto ISO com fuso de São Paulo."""
    return contrato.data_hora_txt(agora), contrato.data_hora_txt(calendario.corte_manha(ins.d))
