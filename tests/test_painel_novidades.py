"""Testes de processamento/painel/novidades.py: comparação entre diagnósticos e cópias em logs/painel.

Usam as fixtures tests/dados/painel/novidades (atual.md e anterior.md), só para leitura, e a árvore
montar_raiz (tmp_path) para o ciclo das cópias. Nenhum teste usa banco ou rede.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fabrica_painel import montar_raiz

from processamento.painel.novidades import ANTERIOR, VISTO, comparar, novidades

PASTA_FIXTURE = Path(__file__).resolve().parent / "dados" / "painel" / "novidades"
FIX_ATUAL = PASTA_FIXTURE / "atual.md"
FIX_ANTERIOR = PASTA_FIXTURE / "anterior.md"


def _preparar(tmp_path: Path, origem: Path) -> tuple[Path, Path]:
    """Árvore de fixtures em tmp_path com o diagnóstico `origem` como docs/diagnostico_banco.md."""
    raiz = montar_raiz(tmp_path)
    docs = raiz / "docs" / "diagnostico_banco.md"
    shutil.copyfile(origem, docs)
    return docs, raiz / "logs" / "painel"


def test_comparar_lista_mudancas_na_ordem_do_plano():
    resultado = comparar(FIX_ATUAL, FIX_ANTERIOR)

    assert resultado["disponivel"] is True
    assert resultado["motivo"] is None
    assert resultado["atual_em"] == "27/10/2026 10:44"
    assert resultado["anterior_em"] == "25/10/2026 12:48"
    assert [i["texto"] for i in resultado["itens"]] == [
        "+474 balanços",
        "índices desde 01/01/2021 (antes 02/01/2025)",
        "1 divergência a menos",
        "quantidade de ações corrigida em 18 empresas (saiu da lista: AXIA3)",
        "1 preço suspeito a menos (saiu: AZUL3 em 10/02/2026)",
        "lacuna de IDIV, IFIX, SMLL: 449 → 250 pregões (agora de 02/01/2025 a 30/12/2025)",
        "Contrato com a coleta: vermelho → verde",
        "+170 preços",
        "+3.578 pontos de índices",
        "+70 linhas no dataset do experimento (1.699 pregões, até 26/10/2026)",
    ]
    assert [i["tipo"] for i in resultado["itens"]] == [
        "mudanca", "mudanca", "mudanca", "mudanca", "mudanca", "mudanca", "mudanca",
        "crescimento", "crescimento", "crescimento",
    ]
    assert resultado["frase"] == (
        "+474 balanços; índices desde 01/01/2021 (antes 02/01/2025); 1 divergência a menos; "
        "quantidade de ações corrigida em 18 empresas (saiu da lista: AXIA3) · e mais 6 mudanças"
    )


def test_comparar_igual_nao_tem_mudancas():
    resultado = comparar(FIX_ATUAL, FIX_ATUAL)

    assert resultado["disponivel"] is True
    assert resultado["itens"] == []
    assert resultado["frase"] == "Nenhuma mudança desde o diagnóstico de 27/10/2026 10:44."


def test_comparar_sem_diagnostico_fica_indisponivel(tmp_path):
    resultado = comparar(tmp_path / "nao_existe.md", FIX_ANTERIOR)

    assert resultado["disponivel"] is False
    assert resultado["motivo"]
    assert resultado["frase"] is None
    assert resultado["itens"] == []


def test_primeira_chamada_sem_anterior_cria_visto(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)

    resultado = novidades(docs, pasta)

    assert resultado["disponivel"] is False
    assert resultado["motivo"].startswith("Ainda sem diagnóstico anterior guardado")
    assert resultado["atual_em"] == "25/10/2026 12:48"
    assert resultado["anterior_em"] is None
    assert resultado["itens"] == []
    assert (pasta / VISTO).is_file()
    assert not (pasta / ANTERIOR).exists()


def test_ciclo_das_copias(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta)

    shutil.copyfile(FIX_ATUAL, docs)
    resultado = novidades(docs, pasta)

    anterior = pasta / ANTERIOR
    assert "Gerado em: 2026-10-25 12:48" in anterior.read_text(encoding="utf-8")
    assert resultado["disponivel"] is True
    assert resultado["anterior_em"] == "25/10/2026 12:48"
    assert len(resultado["itens"]) == 10
    assert (pasta / VISTO).read_bytes() == FIX_ATUAL.read_bytes()

    conteudo_anterior = anterior.read_bytes()
    novidades(docs, pasta)
    assert anterior.read_bytes() == conteudo_anterior
