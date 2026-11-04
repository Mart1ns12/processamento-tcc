"""Testes de processamento/painel/novidades.py: comparação entre diagnósticos e resumos em logs/painel/diagnosticos.

Usam as fixtures tests/dados/painel/novidades (atual.md e anterior.md), só para leitura, e a árvore
montar_raiz (tmp_path) para o ciclo dos resumos. Nenhum teste usa banco ou rede.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fabrica_painel import montar_raiz

from processamento.painel.novidades import (
    ANTERIOR,
    MOTIVO_SEM_ANTERIOR,
    MOTIVO_SEM_LISTA,
    PASTA_RESUMOS,
    VISTO,
    _chave,
    comparar,
    comparar_resumos,
    historico_divergencias,
    novidades,
    resumir,
)

PASTA_FIXTURE = Path(__file__).resolve().parent / "dados" / "painel" / "novidades"
FIX_ATUAL = PASTA_FIXTURE / "atual.md"
FIX_ANTERIOR = PASTA_FIXTURE / "anterior.md"


def _preparar(tmp_path: Path, origem: Path) -> tuple[Path, Path]:
    """Árvore de fixtures em tmp_path com o diagnóstico `origem` como docs/diagnostico_banco.md."""
    raiz = montar_raiz(tmp_path)
    docs = raiz / "docs" / "diagnostico_banco.md"
    shutil.copyfile(origem, docs)
    return docs, raiz / "logs" / "painel"


def _resumos(pasta: Path) -> list[str]:
    """Nomes dos resumos guardados em pasta/diagnosticos (lista vazia se a pasta não existe)."""
    return sorted(p.name for p in (pasta / PASTA_RESUMOS).glob("*.json")) if (pasta / PASTA_RESUMOS).is_dir() else []


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


def test_primeira_chamada_sem_anterior_guarda_so_o_resumo_atual(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)

    resultado = novidades(docs, pasta)

    assert resultado["disponivel"] is False
    assert resultado["motivo"].startswith("Ainda sem diagnóstico anterior guardado")
    assert resultado["atual_em"] == "25/10/2026 12:48"
    assert resultado["anterior_em"] is None
    assert resultado["itens"] == []
    assert _resumos(pasta) == ["2026-10-25_1248.json"]
    assert not (pasta / VISTO).exists()


def test_ciclo_dos_resumos(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta)

    shutil.copyfile(FIX_ATUAL, docs)
    resultado = novidades(docs, pasta)

    assert _resumos(pasta) == ["2026-10-25_1248.json", "2026-10-27_1044.json"]
    assert resultado["disponivel"] is True
    assert resultado["anterior_em"] == "25/10/2026 12:48"
    assert resultado["itens"] == comparar(FIX_ATUAL, FIX_ANTERIOR)["itens"]
    assert len(resultado["itens"]) == 10
    assert resultado["frase"] == comparar(FIX_ATUAL, FIX_ANTERIOR)["frase"]

    conteudo = {n: (pasta / PASTA_RESUMOS / n).read_bytes() for n in _resumos(pasta)}
    novidades(docs, pasta)
    assert _resumos(pasta) == ["2026-10-25_1248.json", "2026-10-27_1044.json"]
    assert {n: (pasta / PASTA_RESUMOS / n).read_bytes() for n in _resumos(pasta)} == conteudo


def test_comparar_resumos_com_json_ida_e_volta_igual_a_comparar(tmp_path):
    ra = resumir(FIX_ATUAL)
    rb = json.loads(json.dumps(resumir(FIX_ANTERIOR)))

    assert comparar_resumos(ra, rb) == comparar(FIX_ATUAL, FIX_ANTERIOR)


def test_resumo_tem_chaves_do_plano(tmp_path):
    resumo = resumir(FIX_ATUAL)

    assert set(resumo) == {"versao", "gerado_em", "periodo", "divergencias", "divergencias_lista",
                           "quantidade_acoes", "retornos", "lacunas", "cobertura", "farois"}
    assert resumo["gerado_em"] == "2026-10-27 10:44 (America/Sao_Paulo)"
    assert resumo["versao"] == 1


def test_rotacao_apaga_os_mais_antigos_com_manter(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta, manter=2)
    shutil.copyfile(FIX_ATUAL, docs)
    novidades(docs, pasta, manter=2)

    terceiro = FIX_ATUAL.read_text(encoding="utf-8")
    assert terceiro.count("- Gerado em: 2026-10-27 10:44") == 1
    docs.write_text(terceiro.replace("- Gerado em: 2026-10-27 10:44", "- Gerado em: 2026-10-28 09:00"), encoding="utf-8")
    resultado = novidades(docs, pasta, manter=2)

    assert _resumos(pasta) == ["2026-10-27_1044.json", "2026-10-28_0900.json"]
    assert resultado["itens"] == []
    assert resultado["frase"] == "Nenhuma mudança desde o diagnóstico de 27/10/2026 10:44."


def test_sem_manter_nao_apaga_nenhum_resumo(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta)
    shutil.copyfile(FIX_ATUAL, docs)
    novidades(docs, pasta)
    terceiro = FIX_ATUAL.read_text(encoding="utf-8").replace("- Gerado em: 2026-10-27 10:44", "- Gerado em: 2026-10-28 09:00")
    docs.write_text(terceiro, encoding="utf-8")
    novidades(docs, pasta)

    assert len(_resumos(pasta)) == 3


def test_migracao_usa_os_logs_antigos_quando_nao_ha_resumos(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ATUAL)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ANTERIOR).write_bytes(FIX_ANTERIOR.read_bytes())

    resultado = novidades(docs, pasta)

    assert _resumos(pasta) == ["2026-10-25_1248.json", "2026-10-27_1044.json"]
    assert resultado["disponivel"] is True
    assert len(resultado["itens"]) == 10


def test_docs_inexistente_fica_indisponivel_e_nao_cria_arquivos(tmp_path):
    pasta = tmp_path / "logs" / "painel"

    resultado = novidades(tmp_path / "nao_existe.md", pasta, manter=5)

    assert resultado["disponivel"] is False
    assert resultado["motivo"]
    assert resultado["itens"] == []
    assert _resumos(pasta) == []
    assert not (pasta / PASTA_RESUMOS).exists()


# ---------------------------------------------------------------- divergências: identidade e histórico

LINHA_1 = "| 1 | coluna_faltando | v1-precos | falta a coluna volume |"
LINHA_2025 = "| 2 | noticia_sem_hora | v1-noticias | 2025: 1060 de 30654 sem hora |"
LINHA_2025_NOVA = "| 2 | noticia_sem_hora | v1-noticias | 2025: 1100 de 30700 sem hora |"
LINHA_CADASTRO = "| 3 | coluna_faltando | v1-cadastro | falta a coluna setor |"
TEXTO_A = FIX_ANTERIOR.read_text(encoding="utf-8")
TEXTO_B = (TEXTO_A.replace("- Gerado em: 2026-10-25 12:48", "- Gerado em: 2026-10-26 09:00")
           .replace(LINHA_1, LINHA_1 + "\n" + LINHA_2025))
TEXTO_C = (TEXTO_B.replace("- Gerado em: 2026-10-26 09:00", "- Gerado em: 2026-10-27 09:00")
           .replace(LINHA_2025, LINHA_2025_NOVA))
TEXTO_D = TEXTO_C.replace(LINHA_2025_NOVA, LINHA_2025_NOVA + "\n" + LINHA_CADASTRO)


def test_resumo_guarda_a_lista_de_divergencias():
    assert resumir(FIX_ANTERIOR)["divergencias_lista"] == [["coluna_faltando", "v1-precos", "falta a coluna volume"]]


def test_chave_troca_numeros_e_mantem_anos():
    assert _chave("noticia_sem_hora", "v1-noticias", "2025: 1.060 de 30654 sem hora") == (
        "noticia_sem_hora", "v1-noticias", "2025: # de # sem hora")


def test_historico_resolvida_contra_o_anterior(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta)

    resultado = historico_divergencias(FIX_ATUAL, pasta)

    assert resultado["atual"] == 0
    assert resultado["anterior"] == 1
    assert resultado["anterior_em"] == "25/10/2026 12:48"
    assert resultado["resolvidas"] == [{"tema": "coluna_faltando", "tabela": "v1-precos", "detalhe": "falta a coluna volume"}]
    assert resultado["novas"] == []
    assert resultado["lista"] == []
    assert resultado["motivo_comparacao"] is None


def test_historico_desde_quando_cada_divergencia_aparece(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta)
    docs.write_text(TEXTO_B, encoding="utf-8")
    novidades(docs, pasta)
    docs.write_text(TEXTO_C, encoding="utf-8")

    resultado = historico_divergencias(docs, pasta)

    assert [i["desde_texto"] for i in resultado["lista"]] == ["25/10/2026 ou antes", "26/10/2026"]
    assert resultado["resolvidas"] == []
    assert resultado["novas"] == []


def test_historico_nova_divergencia_aparece_como_nova(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    novidades(docs, pasta)
    docs.write_text(TEXTO_B, encoding="utf-8")
    novidades(docs, pasta)
    docs.write_text(TEXTO_D, encoding="utf-8")

    resultado = historico_divergencias(docs, pasta)

    assert [i["desde_texto"] for i in resultado["lista"]] == ["25/10/2026 ou antes", "26/10/2026", "nova"]
    assert resultado["novas"] == [{"tema": "coluna_faltando", "tabela": "v1-cadastro", "detalhe": "falta a coluna setor"}]
    assert resultado["resolvidas"] == []


def test_historico_resumo_anterior_sem_lista(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)
    sem_lista = {k: v for k, v in resumir(FIX_ANTERIOR).items() if k != "divergencias_lista"}
    (pasta / PASTA_RESUMOS).mkdir(parents=True)
    (pasta / PASTA_RESUMOS / "2026-10-25_1248.json").write_text(json.dumps(sem_lista, ensure_ascii=False), encoding="utf-8")

    resultado = historico_divergencias(FIX_ATUAL, pasta)

    assert resultado["anterior"] == 1
    assert resultado["resolvidas"] is None
    assert resultado["novas"] is None
    assert resultado["motivo_comparacao"] == MOTIVO_SEM_LISTA


def test_historico_sem_anterior_guardado(tmp_path):
    docs, pasta = _preparar(tmp_path, FIX_ANTERIOR)

    resultado = historico_divergencias(docs, pasta)

    assert resultado["anterior"] is None
    assert resultado["anterior_em"] is None
    assert resultado["resolvidas"] is None
    assert resultado["novas"] is None
    assert resultado["motivo_comparacao"] == MOTIVO_SEM_ANTERIOR
    assert [(i["desde"], i["desde_texto"]) for i in resultado["lista"]] == [(None, "sem dados")]
    assert not (pasta / PASTA_RESUMOS).exists()
