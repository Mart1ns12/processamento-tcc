"""Fábricas do protocolo para teste: limites pequenos e documento do protocolo curto (seções 3 a 6).
Os testes escrevem tudo em tmp_path; nada aqui toca docs/ real."""

from dataclasses import replace
from pathlib import Path

from processamento.experimento.protocolo import LIMITES


def lim_teste():
    """Limites de teste: um ano só (2025), 1 ano positivo basta e 50 reamostragens."""
    return replace(LIMITES, anos=(2025,), anos_positivos_minimos=1, reamostragens=50)


def doc_de_teste(pasta: Path) -> Path:
    """Documento do protocolo com as seções 3 a 6 curtas, em `pasta/protocolo_variaveis.md`."""
    doc = pasta / "protocolo_variaveis.md"
    texto = (
        "# Protocolo de teste (fixture)\n\n"
        "## 1. Escopo\ntexto da seção 1\n\n"
        "## 2. Blocos\ntexto da seção 2\n\n"
        "## 3. Critérios de adoção\nGanho de AUC maior que +0,005.\n\n"
        "## 4. Ordem de execução\ntexto da seção 4\n\n"
        "## 5. Regras de relato\ntexto da seção 5\n\n"
        "## 6. Busca pelo melhor modelo\ntexto da seção 6\n"
    )
    pasta.mkdir(parents=True, exist_ok=True)
    doc.write_bytes(texto.encode("utf-8"))
    return doc
