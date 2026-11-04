"""Testes de processamento/painel/aba_diagnostico.py: seções do diagnóstico para a aba Diagnóstico.

Usam a fixture tests/dados/painel/diagnostico_coleta.md e arquivos em tmp_path, só para leitura.
Nenhum teste usa banco ou rede.
"""

from __future__ import annotations

from pathlib import Path

from processamento.painel.aba_diagnostico import diagnostico_aba, secoes_resumo
from processamento.painel.relatorios import ler_diagnostico
from processamento.painel.saude import cartoes_saude

FIX = Path(__file__).resolve().parent / "dados" / "painel" / "diagnostico_coleta.md"
CARTOES = cartoes_saude(FIX)["cartoes"]

TEXTO_ATENCAO = """# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-11-03 13:09 (America/Sao_Paulo)

## Divergências × especificação

Nenhuma divergência encontrada.

## 4. Seção comum

- Atenção: a tabela X ficou vazia.

## 9. Sem ligação

- Nota comum.

## 13. Retornos diários suspeitos

- Nota sem alerta.
"""


def _secoes(caminho: Path, cartoes=CARTOES) -> dict[int, dict]:
    diag = ler_diagnostico(caminho)
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return {s["numero"]: s for s in secoes_resumo(diag, linhas, cartoes)}


def test_aba_com_a_fixture_resume_as_secoes(tmp_path):
    resultado = diagnostico_aba(FIX, tmp_path / "logs" / "painel", CARTOES)

    assert resultado["disponivel"] is True
    assert resultado["motivo"] is None
    assert resultado["gerado_em_texto"] == "03/11/2026 13:09"
    assert resultado["n_secoes"] == 15
    assert len(resultado["secoes"]) == 15

    pontos = {s["numero"]: s["ponto"] for s in resultado["secoes"]}
    assert {n for n, p in pontos.items() if p == "at"} == {5, 13, 15}
    assert all(p == "ok" for n, p in pontos.items() if n not in (5, 13, 15))


def test_resumos_da_fixture(tmp_path):
    secoes = _secoes(FIX)

    assert secoes[1]["resumo"] == "8 de 8 tabelas do contrato existem."
    assert secoes[2]["resumo"] == "sem notas"
    nota_12 = secoes[12]["notas"][0]
    assert len(nota_12) > 90
    assert secoes[12]["resumo"] == nota_12[:89] + "…"


def test_nota_atencao_deixa_a_secao_em_at(tmp_path):
    caminho = tmp_path / "diagnostico.md"
    caminho.write_text(TEXTO_ATENCAO, encoding="utf-8")

    secoes = _secoes(caminho, cartoes=[])

    assert secoes[4]["ponto"] == "at"
    assert secoes[9]["ponto"] == "ok"


def test_cartao_ligado_idle_deixa_a_secao_em_idle_e_ignora_nao_dicts(tmp_path):
    caminho = tmp_path / "diagnostico.md"
    caminho.write_text(TEXTO_ATENCAO.replace("- Atenção: a tabela X ficou vazia.", "- Nota comum."), encoding="utf-8")

    secoes = _secoes(caminho, cartoes=["lixo", {"id": "retornos", "farol": "idle"}])

    assert secoes[13]["ponto"] == "idle"
    assert secoes[9]["ponto"] == "ok"


def test_docs_inexistente_fica_indisponivel(tmp_path):
    resultado = diagnostico_aba(tmp_path / "nao_existe.md", tmp_path / "logs" / "painel", CARTOES)

    assert resultado["disponivel"] is False
    assert resultado["motivo"]
    assert resultado["secoes"] == []
    assert resultado["divergencias"] is None
