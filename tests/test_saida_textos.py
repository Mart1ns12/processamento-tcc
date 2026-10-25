"""Testes dos textos prontos da saída (Fase 5 do plano da etapa 7; funções puras).

Os valores esperados são os do plano (seção 12, Fase 5). Sem rede e sem banco.
"""

import itertools

import pytest

from processamento.saida.textos import (
    num_br,
    pct_br,
    pct_sinal,
    texto_beta,
    texto_motivo,
    texto_pl,
    texto_volatilidade,
    texto_volume,
)


def test_num_br_e_pct_br_formato():
    assert num_br(3.94, 1) == "3,9"
    assert num_br(-5.0, 1) == "−5,0"
    assert num_br(-0.04, 1) == "0,0"
    assert pct_br(-0.0028, 2) == "−0,28%"
    assert pct_br(0.0123, 1) == "1,2%"


def test_pct_sinal():
    assert pct_sinal(0.0123) == "+1,2%"
    assert pct_sinal(-0.0083) == "−0,8%"
    assert pct_sinal(0.0) == "0,0%"
    assert pct_sinal(-0.0001) == "0,0%"


def test_texto_volume():
    assert texto_volume(3.94) == "3,9× o normal do último mês"
    assert texto_volume(None) is None
    assert texto_volume(float("nan")) is None


def test_texto_volatilidade():
    assert texto_volatilidade(0.04) == "mais calma que 96% das ações"
    assert texto_volatilidade(0.75) == "mais agitada que 75% das ações"
    assert texto_volatilidade(0.5) == "mais agitada que 50% das ações"
    assert texto_volatilidade(None) is None


def test_texto_beta_faixas():
    assert texto_beta(0.91) == "0,91: move-se um pouco menos que o Ibovespa"
    assert texto_beta(1.0) == "1,00: move-se quase igual ao Ibovespa"
    assert texto_beta(1.05) == "1,05: move-se quase igual ao Ibovespa"
    assert texto_beta(1.2) == "1,20: move-se um pouco mais que o Ibovespa"
    assert texto_beta(1.3) == "1,30: move-se bem mais que o Ibovespa"
    assert texto_beta(0.79) == "0,79: move-se bem menos que o Ibovespa"
    assert texto_beta(-0.2) == "−0,20: costuma andar na direção contrária do Ibovespa"
    assert texto_beta(None) is None


def test_texto_beta_quase_zero():
    """|beta| < 0,2 (24/10/2026): quase não acompanha; as bordas 0,2 e −0,2 seguem as faixas antigas."""
    assert texto_beta(-0.010806382467914228) == "−0,01: quase não acompanha o Ibovespa"
    assert texto_beta(0.0) == "0,00: quase não acompanha o Ibovespa"
    assert texto_beta(0.19) == "0,19: quase não acompanha o Ibovespa"
    assert texto_beta(-0.19) == "−0,19: quase não acompanha o Ibovespa"
    assert texto_beta(0.2) == "0,20: move-se bem menos que o Ibovespa"
    assert texto_beta(-0.2) == "−0,20: costuma andar na direção contrária do Ibovespa"


def test_texto_pl():
    assert texto_pl(-5.0, "lucro_negativo") == "P/L −5,0 · Empresa com prejuízo nos últimos 12 meses"
    assert texto_pl(None, "lucro_negativo") == "Empresa sem lucro nos últimos 12 meses"
    assert texto_pl(6.9, "ok") is None


CASOS_MOTIVO = [
    (("noticias_dia_tom", 0.42, None, 3, 0.05), "Notícias do último pregão e da noite com tom positivo (3 notícias)"),
    (("noticias_dia_tom", -0.05, None, 1, 0.05), "Notícias do último pregão e da noite com tom neutro (1 notícia)"),
    (("ret_5d", -0.031, 0.2, None, 0.05), "Caiu 3,1% nos últimos 5 pregões (abaixo da média das ações)"),
    (("ret_1d", 0.0123, 0.9, None, 0.05), "Subiu 1,2% no último pregão (acima da média das ações)"),
    (("ret_1d", 0.0, 0.5, None, 0.05), "Ficou estável no último pregão"),
    (("volatilidade_20d", 0.0182, 0.75, None, 0.05),
     "Oscilação diária de 1,8% nos últimos 20 pregões (mais agitada que a média)"),
    (("beta", 0.91, 0.4, None, 0.05), "Beta 0,91: move-se um pouco menos que o Ibovespa"),
    (("volume_relativo", 3.94, 0.9, None, 0.05), "Volume de 3,9× o normal"),
    (("salto_abertura", -0.0049, 0.1, None, 0.05), "Abriu em queda de 0,5% no último pregão"),
    (("exposicao_dolar", -0.0083, 0.3, None, 0.05), "Efeito estimado do dólar no último pregão: −0,8%"),
    (("dist_max_52s", -0.153, 0.2, None, 0.05), "15,3% abaixo da máxima de 52 semanas"),
    (("mudanca_tom", 0.3, None, 4, 0.05), "Tom das notícias melhor que o habitual da empresa"),
    (("noticias_dia_qtd", 0.0, None, 0.0, 0.05), "Nenhuma notícia no último pregão e na noite"),
    (("beta", None, None, None, 0.05), "Beta: sem dado"),
]


@pytest.mark.parametrize("argumentos, esperado", CASOS_MOTIVO)
def test_texto_motivo_casos_do_plano(argumentos, esperado):
    assert texto_motivo(*argumentos) == esperado


def test_texto_motivo_fator_desconhecido_levanta_erro():
    with pytest.raises(ValueError):
        texto_motivo("xpto", 1.0, 0.5, None, 0.05)


def test_linguagem_sem_termos_proibidos():
    proibidos = ["compre", "recomendação", "oportunidade", "melhores ações"]
    fatores = [
        "noticias_dia_qtd", "noticias_dia_tom", "noticias_dia_extremo", "mudanca_tom",
        "tom_setor", "tom_mercado", "ret_1d", "ret_5d", "ret_20d", "volatilidade_20d", "beta",
        "volume_relativo", "salto_abertura", "dist_max_52s", "dist_min_52s", "amplitude",
        "ret_vs_setor", "exposicao_dolar", "exposicao_petroleo",
    ]
    valores = [None, 0.0, 0.0123, -0.031, 3.94, 1.3, -0.2, 0.42, -0.42, 0.3, 3.0]
    ranks = [None, 0.1, 0.5, 0.9]
    qtds = [None, 0.0, 1.0, 3.0]

    textos = [
        texto_motivo(fator, valor, rank, qtd, 0.05)
        for fator, valor, rank, qtd in itertools.product(fatores, valores, ranks, qtds)
    ]
    assert textos
    for texto in textos:
        minusculo = texto.lower()
        for termo in proibidos:
            assert termo not in minusculo, (termo, texto)
