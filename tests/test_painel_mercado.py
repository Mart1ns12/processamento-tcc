"""Testes de processamento/painel/mercado.py: dia atípico e coerência do mercado.

CASO REAL conferido pelo usuário nas notícias (pasta saida/2026-10-27/, pregão de 26/10/2026):
o pregão foi real, com circuit breaker. O Ibovespa caiu cerca de 13% e o dólar subiu cerca de 8%
(o IVVB11 +8,96% é coerente com isso). Só o USDBRL −1,45% está errado na coleta, já reportado.
Comportamento travado aqui:
- dia atípico ativo, 16 ações, Ibovespa −13,88%, SMLL −26,92%, "Movimento amplo do mercado (provável evento real)";
- coerência amarela com 1 sinal suspeito (dólar −1,45% × IVVB11 +8,96%), que aponta o USDBRL errado;
- Ibovespa × mediana das ações (−13,88% × −17,46%): mesmo sentido, dentro do esperado.

Nenhum teste usa banco, rede ou escreve em tests/dados/ (as fixtures são copiadas para tmp_path).
"""

import shutil
from pathlib import Path

import pytest

from fabrica_painel import montar_raiz
from processamento.painel.mercado import cartao_coerencia, dia_atipico, ler_dia, pct0, pct2

DADOS = Path(__file__).parent / "dados" / "painel"

LIMITES_DIA = {"retorno_abs": 0.30, "min_acoes": 5, "ibov_amplo": 0.05, "max": 5}
LIMITES_COERENCIA = {"ivvb11_min": 0.03, "dif_min": 0.02}


@pytest.fixture
def pregao(tmp_path):
    """Raiz com o pregão 26/10/2026 em saida/2026-10-27/ (recorte da saída real)."""
    shutil.copytree(DADOS / "pregao_2026-10-26", tmp_path / "saida" / "2026-10-27")
    return tmp_path


@pytest.fixture
def dia(pregao):
    return ler_dia(pregao, "saida", "2026-10-27")


def test_formatos_brasileiros():
    assert pct2(-0.014503686980626429) == "-1,45%"
    assert pct2(0.0896279268486555) == "+8,96%"
    assert pct0(0.30) == "30%"
    assert pct0(0.03) == "3%"


def test_ler_dia_pregao_real(dia):
    assert dia["disponivel"] is True
    assert dia["data_pregao"] == "2026-10-26"
    assert len(dia["retornos"]) == 85
    assert dia["usd"] == -0.014503686980626429
    assert dia["ivvb11"] == 0.0896279268486555
    assert dia["ibov"] == -0.1388462232364457
    assert dia["smll"] == -0.2691564967695621
    assert dia["fonte"] == "saida/2026-10-27/mercado_dia.json e resumo_acao.json"


def test_dia_atipico_caso_real(dia):
    r = dia_atipico(dia, LIMITES_DIA)
    assert r["ativo"] is True
    assert r["n"] == 16
    assert r["amplo"] is True
    assert r["texto"] == "16 ações com retorno do dia acima de 30% em módulo no pregão de 26/10/2026."
    assert r["ibov_texto"] == "Ibovespa -13,88%"
    assert r["smll_texto"] == "SMLL -26,92%"
    assert r["frase"] == "Movimento amplo do mercado (provável evento real)"
    assert [a["ticker"] for a in r["acoes"]][:5] == ["MGLU3", "VAMO3", "HAPV3", "RAPT4", "CSAN3"]
    assert r["acoes"][0]["texto"] == "-58,23%"
    assert r["acoes"][-1] == {"ticker": "GMAT3", "texto": "-30,94%"}
    assert r["max"] == 5
    assert r["pontos"] == [{
        "nivel": "warn",
        "texto": "Dia atípico no pregão de 26/10/2026 (16 ações): aviso de evento de mercado, não erro dos dados",
        "chave": "dia_atipico_amplo",
    }]


def test_dia_atipico_isolado_quando_ibov_abaixo_do_limite(dia):
    r = dia_atipico(dia, {**LIMITES_DIA, "ibov_amplo": 0.20})
    assert r["amplo"] is False
    assert r["frase"] == "Movimento isolado: conferir os dados da coleta"
    assert r["pontos"][0]["chave"] == "dia_atipico_isolado"
    assert r["pontos"][0]["texto"] == "Dia atípico no pregão de 26/10/2026 (16 ações): conferir os dados da coleta"


def test_dia_atipico_inativo_com_min_acoes_acima_do_total(dia):
    r = dia_atipico(dia, {**LIMITES_DIA, "min_acoes": 17})
    assert r["ativo"] is False
    assert r["pontos"] == []


def test_dia_atipico_sem_ibov_fica_isolado(dia):
    dia["ibov"] = None
    r = dia_atipico(dia, LIMITES_DIA)
    assert r["amplo"] is None
    assert r["frase"] == "Sem a variação do Ibovespa: conferir os dados da coleta"
    assert r["ibov_texto"] == "Ibovespa sem dados"
    assert r["pontos"][0]["chave"] == "dia_atipico_isolado"


def test_dia_atipico_limite_ausente_vira_indisponivel(dia):
    r = dia_atipico(dia, {**LIMITES_DIA, "max": None})
    assert r["disponivel"] is False
    assert r["ativo"] is False
    assert r["pontos"] == []


def test_coerencia_caso_real(dia):
    c = cartao_coerencia(dia, LIMITES_COERENCIA)
    cartao = c["cartao"]
    assert cartao["id"] == "coerencia_mercado"
    assert cartao["titulo"] == "Coerência do mercado"
    assert cartao["farol"] == "warn"
    assert cartao["numero"] == "1 sinal suspeito"
    assert cartao["texto"] == (
        "Dólar -1,45% × IVVB11 +8,96%: sentidos opostos, com o IVVB11 acima de 3% em módulo (suspeito). "
        "Ibovespa -13,88% × mediana das ações -17,46%: dentro do esperado."
    )
    assert cartao["fonte"] == "saida/2026-10-27/mercado_dia.json e resumo_acao.json · pregão de 26/10/2026"
    assert c["afetadas"] == {
        "titulo": "Séries afetadas",
        "itens": [{"rotulo": "Dólar (USDBRL)", "detalhe": "-1,45%"}, {"rotulo": "IVVB11", "detalhe": "+8,96%"}],
        "total": 2,
    }


def test_coerencia_pregao_23_sem_suspeito(tmp_path):
    """Fixture raiz: saida/2026-10-23 (recorte com ABEV3, PETR4 e VALE3; mediana +0,14%)."""
    raiz = montar_raiz(tmp_path)
    dia = ler_dia(raiz, "saida", "2026-10-23")
    assert dia_atipico(dia, LIMITES_DIA)["ativo"] is False
    c = cartao_coerencia(dia, LIMITES_COERENCIA)
    assert c["cartao"]["farol"] == "ok"
    assert c["cartao"]["numero"] == "0 sinais suspeitos"
    assert c["cartao"]["texto"] == (
        "Dólar +0,26% × IVVB11 -0,90%: dentro do esperado. "
        "Ibovespa -1,15% × mediana das ações +0,14%: dentro do esperado."
    )
    assert c["afetadas"] is None


def test_coerencia_com_dif_min_menor_vira_suspeito(tmp_path):
    raiz = montar_raiz(tmp_path)
    dia = ler_dia(raiz, "saida", "2026-10-23")
    c = cartao_coerencia(dia, {"ivvb11_min": 0.03, "dif_min": 0.01})
    assert c["cartao"]["farol"] == "warn"
    assert c["cartao"]["numero"] == "1 sinal suspeito"
    assert c["cartao"]["texto"] == (
        "Dólar +0,26% × IVVB11 -0,90%: dentro do esperado. "
        "Ibovespa -1,15% × mediana das ações +0,14%: sentidos opostos, diferença de 1,29% (suspeito)."
    )
    assert c["afetadas"]["itens"] == [
        {"rotulo": "Ibovespa", "detalhe": "-1,15%"},
        {"rotulo": "Mediana das ações", "detalhe": "+0,14%"},
    ]


def test_sem_dia_de_referencia_vira_sem_dados(tmp_path):
    dia = ler_dia(tmp_path, "saida", None)
    assert dia["disponivel"] is False
    assert dia["motivo"]
    assert dia_atipico(dia, LIMITES_DIA)["disponivel"] is False
    c = cartao_coerencia(dia, LIMITES_COERENCIA)
    assert c["cartao"]["farol"] == "idle"
    assert c["cartao"]["numero"] == "sem dados"
    assert c["afetadas"] is None


def test_pasta_inexistente_nao_levanta(tmp_path):
    dia = ler_dia(tmp_path, "saida", "2026-01-01")
    assert dia["disponivel"] is False
    assert dia["motivo"] == "pasta de saída não encontrada"


def test_mercado_dia_quebrado_nao_levanta(pregao):
    (pregao / "saida" / "2026-10-27" / "mercado_dia.json").write_text("{ruim", encoding="utf-8")
    dia = ler_dia(pregao, "saida", "2026-10-27")
    assert dia["disponivel"] is False
    assert dia["motivo"] == "mercado_dia.json: JSON inválido"
    assert cartao_coerencia(dia, LIMITES_COERENCIA)["cartao"]["farol"] == "idle"
