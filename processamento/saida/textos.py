"""Textos prontos da saída (plano da etapa 7, Fase 5; decisão S14).

Funções puras: recebem os valores e devolvem o texto, sem banco, sem rede e sem "hoje".
Valor nulo (None ou NaN) vira None, exceto em `texto_motivo`, que devolve a frase de "sem dado".
Linguagem: nunca "compre", "recomendação", "oportunidade" ou "melhores ações".
"""

from __future__ import annotations

import math

from processamento.experimento.relatorio import pct

MENOS = "−"  # U+2212, como no resto do texto


def _vazio(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def num_br(x: float, casas: int) -> str:
    """1.5 -> '1,5'; -5.0 -> '−5,0'; -0.04 com 1 casa -> '0,0'."""
    texto = f"{x:.{casas}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",").replace("-", MENOS)


def pct_br(x: float, casas: int = 1) -> str:
    """Como relatorio.pct, com o sinal de menos em U+2212."""
    return pct(x, casas).replace("-", MENOS)


def pct_sinal(x: float) -> str:
    """0.0123 -> '+1,2%'; -0.0083 -> '−0,8%'; 0 -> '0,0%'."""
    texto = pct_br(x, 1)
    if texto.startswith(MENOS) or texto == "0,0%":
        return texto
    return "+" + texto


def texto_volume(relativo) -> str | None:
    if _vazio(relativo):
        return None
    return f"{num_br(relativo, 1)}× o normal do último mês"


def texto_volatilidade(posicao_pct) -> str | None:
    if _vazio(posicao_pct):
        return None
    if posicao_pct >= 0.5:
        return f"mais agitada que {pct_br(posicao_pct, 0)} das ações"
    return f"mais calma que {pct_br(1 - posicao_pct, 0)} das ações"


def _faixa_beta(b: float) -> str:
    if abs(b) < 0.2:  # quase zero (24/10/2026): ex.: AZUL3 −0,01 não "anda na direção contrária"
        return "quase não acompanha o Ibovespa"
    if b < 0:
        return "costuma andar na direção contrária do Ibovespa"
    if b < 0.8:
        return "move-se bem menos que o Ibovespa"
    if b < 0.95:
        return "move-se um pouco menos que o Ibovespa"
    if b <= 1.05:
        return "move-se quase igual ao Ibovespa"
    if b <= 1.2:
        return "move-se um pouco mais que o Ibovespa"
    return "move-se bem mais que o Ibovespa"


def texto_beta(beta) -> str | None:
    if _vazio(beta):
        return None
    return f"{num_br(beta, 2)}: {_faixa_beta(beta)}"


def texto_pl(valor, status) -> str | None:
    """Só o caso de prejuízo (ou lucro zero) tem texto; os demais status devolvem None."""
    if status != "lucro_negativo":
        return None
    if _vazio(valor):
        return "Empresa sem lucro nos últimos 12 meses"
    return f"P/L {num_br(valor, 1)} · Empresa com prejuízo nos últimos 12 meses"


_ROTULOS_PRECO = {
    "ret_1d": "Retorno do último pregão",
    "ret_5d": "Retorno de 5 pregões",
    "ret_20d": "Retorno de 20 pregões",
    "volatilidade_20d": "Oscilação diária",
    "beta": "Beta",
    "volume_relativo": "Volume em relação ao normal",
    "salto_abertura": "Salto da abertura",
    "dist_max_52s": "Distância da máxima de 52 semanas",
    "dist_min_52s": "Distância da mínima de 52 semanas",
    "amplitude": "Amplitude do dia",
    "ret_vs_setor": "Retorno em relação ao setor",
    "exposicao_dolar": "Efeito do dólar",
    "exposicao_petroleo": "Efeito do petróleo",
    "posicao_fechamento": "Posição do fechamento no dia",
    "mom_12_1": "Retorno de 12 meses, sem o último mês",
    "liquidez_20d": "Giro típico por pregão",
    "ret_idio_5d": "Retorno em relação ao Ibovespa (5 pregões)",
}

_PERIODO_RETORNO = {
    "ret_1d": "no último pregão",
    "ret_5d": "nos últimos 5 pregões",
    "ret_20d": "nos últimos 20 pregões",
}

_SEM_DADO_NOTICIAS = {
    "noticias_dia_qtd": "Sem notícias no último pregão e na noite",
    "noticias_dia_tom": "Sem notícias no último pregão e na noite",
    "noticias_dia_extremo": "Sem notícias no último pregão e na noite",
    "mudanca_tom": "Sem base para comparar o tom com o habitual da empresa",
    "tom_setor": "Sem notícias das outras empresas do setor",
    "tom_mercado": "Sem notícias do mercado",
}


def _tom(v: float, tom_neutro: float) -> str:
    if v > tom_neutro:
        return "positivo"
    if v < -tom_neutro:
        return "negativo"
    return "neutro"


def _contagem(q: float) -> str:
    n = int(round(q))
    return f"{n} notícia" if n == 1 else f"{n} notícias"


def _sufixo_media_acoes(rank) -> str:
    if rank is None or _vazio(rank):
        return ""
    if rank > 0.5:
        return " (acima da média das ações)"
    if rank < 0.5:
        return " (abaixo da média das ações)"
    return ""


def _texto_preco(fator: str, v: float, rank) -> str:
    if fator in _PERIODO_RETORNO:
        periodo = _PERIODO_RETORNO[fator]
        if v == 0:
            return f"Ficou estável {periodo}"
        verbo = "Subiu" if v > 0 else "Caiu"
        return f"{verbo} {pct_br(abs(v))} {periodo}{_sufixo_media_acoes(rank)}"
    if fator == "volatilidade_20d":
        if rank is None or _vazio(rank) or rank == 0.5:
            comparacao = "na média das ações"
        elif rank > 0.5:
            comparacao = "mais agitada que a média"
        else:
            comparacao = "mais calma que a média"
        return f"Oscilação diária de {pct_br(v)} nos últimos 20 pregões ({comparacao})"
    if fator == "beta":
        return f"Beta {texto_beta(v)}"
    if fator == "volume_relativo":
        return f"Volume de {num_br(v, 1)}× o normal"
    if fator == "salto_abertura":
        if v > 0:
            return f"Abriu em alta de {pct_br(v)} no último pregão"
        if v < 0:
            return f"Abriu em queda de {pct_br(abs(v))} no último pregão"
        return "Abriu estável no último pregão"
    if fator == "dist_max_52s":
        if v == 0:
            return "Na máxima de 52 semanas"
        return f"{pct_br(abs(v))} abaixo da máxima de 52 semanas"
    if fator == "dist_min_52s":
        if v == 0:
            return "Na mínima de 52 semanas"
        return f"{pct_br(v)} acima da mínima de 52 semanas"
    if fator == "amplitude":
        return f"Amplitude de {pct_br(v)} entre a máxima e a mínima do último pregão"
    if fator == "ret_vs_setor":
        if v > 0:
            return f"{pct_br(v)} acima do setor no último pregão"
        if v < 0:
            return f"{pct_br(abs(v))} abaixo do setor no último pregão"
        return "Igual ao setor no último pregão"
    if fator == "exposicao_dolar":
        return f"Efeito estimado do dólar no último pregão: {pct_sinal(v)}"
    if fator == "posicao_fechamento":
        return f"Fechou em {pct_br(v, 0)} da faixa entre a mínima e a máxima do último pregão"
    if fator == "mom_12_1":
        if v == 0:
            verbo_mom = "Ficou estável"
        else:
            verbo_mom = "Subiu" if v > 0 else "Caiu"
        return f"{verbo_mom} {pct_br(abs(v))} em 12 meses, sem contar o último mês{_sufixo_media_acoes(rank)}"
    if fator == "liquidez_20d":
        return f"Giro típico de R$ {num_br(v / 1_000_000, 1)} mi por pregão"
    if fator == "ret_idio_5d":
        if v > 0:
            return f"{pct_br(v)} acima do esperado pelo Ibovespa nos últimos 5 pregões"
        if v < 0:
            return f"{pct_br(abs(v))} abaixo do esperado pelo Ibovespa nos últimos 5 pregões"
        return "Igual ao esperado pelo Ibovespa nos últimos 5 pregões"
    # exposicao_petroleo (único que sobra dos fatores de preço)
    return f"Efeito estimado do petróleo no último pregão: {pct_sinal(v)}"


def texto_motivo(fator: str, valor, rank, qtd_noticias, tom_neutro: float) -> str:
    """Frase de um dos 3 motivos do top 5.

    valor: valor bruto do dataset no fator; rank: rank do dia (só nos fatores de preço);
    qtd_noticias: noticias_dia_qtd bruto da linha; tom_neutro: |tom| até isto é "neutro".
    """
    if fator not in _ROTULOS_PRECO and fator not in _SEM_DADO_NOTICIAS:
        raise ValueError(f"fator de motivo desconhecido: {fator!r}")

    if _vazio(valor):
        if fator in _ROTULOS_PRECO:
            return f"{_ROTULOS_PRECO[fator]}: sem dado"
        return _SEM_DADO_NOTICIAS[fator]

    if fator == "noticias_dia_qtd":
        if valor == 0:
            return "Nenhuma notícia no último pregão e na noite"
        return f"{_contagem(valor)} no último pregão e na noite"

    if fator == "noticias_dia_tom":
        tom = _tom(valor, tom_neutro)
        if _vazio(qtd_noticias):
            return f"Notícias do último pregão e da noite com tom {tom}"
        return f"Notícias do último pregão e da noite com tom {tom} ({_contagem(qtd_noticias)})"

    if fator == "noticias_dia_extremo":
        if valor > tom_neutro:
            palavra = "positiva"
        elif valor < -tom_neutro:
            palavra = "negativa"
        else:
            palavra = "neutra"
        return f"Notícia de tom mais forte: {palavra} ({num_br(valor, 2)})"

    if fator == "mudanca_tom":
        if valor > tom_neutro:
            comparacao = "melhor que o habitual da empresa"
        elif valor < -tom_neutro:
            comparacao = "pior que o habitual da empresa"
        else:
            comparacao = "parecido com o habitual da empresa"
        return f"Tom das notícias {comparacao}"

    if fator == "tom_setor":
        return f"Notícias das outras empresas do setor com tom {_tom(valor, tom_neutro)}"

    if fator == "tom_mercado":
        return f"Notícias do mercado em geral com tom {_tom(valor, tom_neutro)}"

    return _texto_preco(fator, valor, rank)
