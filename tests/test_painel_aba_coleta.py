"""Testes de processamento/painel/aba_coleta.py: indicadores da aba Coleta a partir do diagnóstico.

Usam tests/dados/painel/diagnostico_coleta.md (fixture) e arquivos .md montados em tmp_path.
Nenhum teste usa banco ou rede.
"""

from pathlib import Path

import pytest

from processamento.painel.aba_coleta import (
    FALTA_GOOGLE,
    FALTA_SERIE,
    contagem_finbert,
    contagem_juiza,
    falhas_etapas,
    indicadores_coleta,
    ler_md,
    noticias_ano_origem,
    noticias_mes,
)

FIXTURE = Path(__file__).resolve().parent / "dados" / "painel" / "diagnostico_coleta.md"

CABECALHO = (
    "# Diagnóstico do banco da coleta (só leitura)\n"
    "- Gerado em: 2026-11-03 13:09 (America/Sao_Paulo)\n"
    "## Divergências × especificação\n"
    "Nenhuma divergência encontrada.\n"
)


def _linhas(caminho: Path) -> list[str]:
    return caminho.read_text(encoding="utf-8").splitlines()


def _escrever(tmp_path: Path, texto: str) -> Path:
    caminho = tmp_path / "diagnostico_banco.md"
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def _com_linha_depois(texto: str, marca: str, nova: str) -> str:
    saida = []
    for linha in texto.splitlines():
        saida.append(linha)
        if linha.startswith(marca):
            saida.append(nova)
    return "\n".join(saida) + "\n"


def _fixture_sem_tabela_por_mes_origem() -> str:
    texto = FIXTURE.read_text(encoding="utf-8")
    inicio = texto.index("### Artigos por mês e origem")
    return texto[:inicio] + texto[texto.index("## 16."):]


def test_ler_md_devolve_diagnostico_e_linhas():
    lido = ler_md(FIXTURE)
    assert lido is not None
    diag, linhas = lido
    assert diag["disponivel"] is True
    assert diag["gerado_em"] == "2026-11-03 13:09 (America/Sao_Paulo)"
    assert linhas == _linhas(FIXTURE)


def test_ler_md_arquivo_inexistente_devolve_none(tmp_path):
    assert ler_md(tmp_path / "nao_existe.md") is None


def test_contagem_finbert_da_fixture():
    assert contagem_finbert(_linhas(FIXTURE)) == {
        "ok": 403408,
        "sem_prob": 6560,
        "total": 409968,
        "fonte": "Seção 5: Notícias (v1-noticias)",
    }


def test_contagem_juiza_da_fixture():
    assert contagem_juiza(_linhas(FIXTURE)) == {
        "total": 409968,
        "nulos": 7903,
        "fonte": "Seção 16: Vazios e zeros",
    }


def test_indicadores_coleta_da_fixture_bate_com_o_contrato():
    resultado = indicadores_coleta(FIXTURE)
    assert resultado == {
        "disponivel": True,
        "motivo": None,
        "gerado_em": "2026-11-03 13:09 (America/Sao_Paulo)",
        "itens": [
            {"id": "noticias", "nome": "Notícias no banco", "valor": 409968, "valor_texto": "409.968",
             "fracao": None, "aguardando": None,
             "nota": "294.941 artigos · 01/01/2021 a 03/11/2026",
             "fonte": "Seção 3: Resumo das tabelas"},
            {"id": "finbert", "nome": "Com FinBERT", "valor": pytest.approx(403408 / 409968),
             "valor_texto": "98,4%", "fracao": pytest.approx(403408 / 409968), "aguardando": 6560,
             "nota": "6.560 aguardando", "fonte": "Seção 5: Notícias (v1-noticias)"},
            {"id": "juiza", "nome": "Julgadas pela juíza", "valor": pytest.approx(402065 / 409968),
             "valor_texto": "98,1%", "fracao": pytest.approx(402065 / 409968), "aguardando": 7903,
             "nota": "7.903 aguardando", "fonte": "Seção 16: Vazios e zeros"},
        ],
    }


def test_indicadores_sem_nota_de_resumo_viram_sem_dados(tmp_path):
    texto = (
        CABECALHO
        + "## 3. Resumo das tabelas\n"
        + "### Período e entidades\n"
        + "| tabela | linhas | inicio | fim | entidades | coluna_entidade |\n"
        + "|---|---|---|---|---|---|\n"
        + "| v1-noticias | 409968 | 2021-01-01 | 2026-11-03 | 88 | ticker |\n"
    )
    resultado = indicadores_coleta(_escrever(tmp_path, texto))
    assert resultado["disponivel"] is True
    assert len(resultado["itens"]) == 3
    for item in resultado["itens"][1:]:
        assert item["valor"] is None
        assert item["valor_texto"] == "sem dados"
        assert item["nota"] == "sem dados"
        assert item["fonte"] is None


def test_indicadores_arquivo_inexistente(tmp_path):
    resultado = indicadores_coleta(tmp_path / "nao_existe.md")
    assert resultado["disponivel"] is False
    assert resultado["motivo"]
    assert len(resultado["itens"]) == 3
    assert all(item["valor"] is None and item["nota"] == "sem dados" for item in resultado["itens"])


def test_noticias_ano_origem_da_fixture_bate_com_o_contrato():
    assert noticias_ano_origem(FIXTURE) == {
        "disponivel": True,
        "motivo": None,
        "anos": ["2021", "2023", "2025", "2026"],
        "linhas": [
            {"origem": "google_news", "rotulo": "Google News", "valores": [13787, 24069, 30654, 122505]},
            {"origem": "cvm_ipe", "rotulo": "CVM", "valores": [4360, 3704, 3687, 2844]},
            {"origem": "wordpress", "rotulo": "WordPress", "valores": [15126, None, None, 2053]},
        ],
        "maximo": 122505,
        "fonte": "Seção 5: Notícias (v1-noticias) · artigos distintos",
    }


def test_noticias_ano_origem_origem_desconhecida_vai_por_ultimo(tmp_path):
    texto = _com_linha_depois(
        FIXTURE.read_text(encoding="utf-8"),
        "| 2026 | wordpress |",
        "| 2021 | nova_fonte | 10 | 5 | 50 | 0 | 0 | 5 | 50 |",
    )
    resultado = noticias_ano_origem(_escrever(tmp_path, texto))
    assert resultado["linhas"][-1]["origem"] == "nova_fonte"
    assert resultado["linhas"][-1]["rotulo"] == "nova_fonte"
    assert resultado["linhas"][-1]["valores"] == [10, None, None, None]


def test_noticias_ano_origem_sem_secao(tmp_path):
    resultado = noticias_ano_origem(_escrever(tmp_path, CABECALHO))
    assert resultado["disponivel"] is False
    assert resultado["motivo"] == "Seção não encontrada no diagnóstico."
    assert resultado["linhas"] == []


def test_noticias_mes_da_fixture():
    resultado = noticias_mes(FIXTURE)
    assert resultado["disponivel"] is True
    assert resultado["motivo"] is None
    assert resultado["nota"] == (
        "64 meses avaliados (mês abaixo de 25% da mediana dos até 12 meses anteriores; "
        "o último mês da coleta fica de fora por estar incompleto)"
    )
    assert resultado["serie_completa"] is True
    assert resultado["falta"] is None
    assert resultado["origens"] == ["cvm_ipe", "google_news", "wordpress"]
    assert resultado["google"] == {
        "origem": "google_news",
        "rotulo": "Google News",
        "meses": [
            {"mes": "2024-12", "mes_texto": "12/2024", "artigos": 2712, "estado": None},
            {"mes": "2025-01", "mes_texto": "01/2025", "artigos": 8, "estado": "conhecido"},
            {"mes": "2025-06", "mes_texto": "06/2025", "artigos": 13, "estado": "conhecido"},
            {"mes": "2025-07", "mes_texto": "07/2025", "artigos": 12, "estado": "conhecido"},
            {"mes": "2025-08", "mes_texto": "08/2025", "artigos": 2650, "estado": None},
        ],
        "maximo": 2712,
        "fonte": "Seção 15: Notícias por mês · Artigos por mês e origem (artigos distintos)",
    }
    assert resultado["fonte"] == "Seção 15: Notícias por mês"
    meses = resultado["meses"]
    assert [(m["mes"], m["artigos"], m["mediana"], m["estado"]) for m in meses] == [
        ("2025-01", 288, 2698.5, "conhecido"),
        ("2025-06", 218, 2698.5, "conhecido"),
        ("2025-07", 255, 2698.5, "conhecido"),
    ]
    assert meses[0]["mes_texto"] == "01/2025"
    assert meses[0]["fracao"] == pytest.approx(288 / 2698.5)


def test_noticias_mes_sem_tabela_por_mes_origem_vira_serie_incompleta(tmp_path):
    resultado = noticias_mes(_escrever(tmp_path, _fixture_sem_tabela_por_mes_origem()))
    assert resultado["disponivel"] is True
    assert resultado["serie_completa"] is False
    assert resultado["falta"] == FALTA_SERIE
    assert resultado["google"] is None
    assert resultado["origens"] == []
    assert len(resultado["meses"]) == 3


def test_noticias_mes_tabela_sem_coluna_google_news(tmp_path):
    texto = _fixture_sem_tabela_por_mes_origem().replace(
        "## 16.",
        "### Artigos por mês e origem (artigos distintos)\n\n| mes | cvm_ipe |\n|---|---|\n| 2025-01 | 280 |\n\n## 16.",
    )
    resultado = noticias_mes(_escrever(tmp_path, texto))
    assert resultado["serie_completa"] is True
    assert resultado["falta"] == FALTA_GOOGLE
    assert resultado["google"] is None
    assert resultado["origens"] == ["cvm_ipe"]


def test_noticias_mes_celula_invalida_do_google_vira_none(tmp_path):
    texto = FIXTURE.read_text(encoding="utf-8").replace(
        "| 2025-06 | 205 | 13 | 0 |", "| 2025-06 | 205 | x | 0 |"
    )
    google = noticias_mes(_escrever(tmp_path, texto))["google"]
    mes_junho = next(m for m in google["meses"] if m["mes"] == "2025-06")
    assert mes_junho["artigos"] is None
    assert google["maximo"] == 2712


def test_noticias_mes_situacao_rever(tmp_path):
    texto = _com_linha_depois(
        FIXTURE.read_text(encoding="utf-8"),
        "| 2025-07 | 255 |",
        "| 2024-03 | 500 | 2600 | rever: fora de periodos_sem_coleta |",
    )
    meses = noticias_mes(_escrever(tmp_path, texto))["meses"]
    assert meses[-1]["mes"] == "2024-03"
    assert meses[-1]["estado"] == "rever"


def test_noticias_mes_nota_de_nenhum_mes_sem_tabela(tmp_path):
    texto = (
        CABECALHO
        + "## 15. Notícias por mês\n"
        + "- 64 meses avaliados (mês abaixo de 25% da mediana)\n"
        + "- nenhum mês abaixo de 25% da mediana\n"
    )
    resultado = noticias_mes(_escrever(tmp_path, texto))
    assert resultado["disponivel"] is True
    assert resultado["meses"] == []


def test_noticias_mes_sem_secao(tmp_path):
    resultado = noticias_mes(_escrever(tmp_path, CABECALHO))
    assert resultado["disponivel"] is False
    assert resultado["motivo"] == "Seção não encontrada no diagnóstico."
    assert resultado["meses"] == []


def test_falhas_etapas_da_fixture():
    resultado = falhas_etapas(FIXTURE)
    assert resultado["disponivel"] is True
    assert resultado["fonte"] == (
        "Seção 17: Painel de execuções (v1-painel_execucoes e v1-painel_etapas)"
    )
    assert resultado["itens"] == [
        {"id": "analise", "rotulo": "análise", "falhou": 3},
        {"id": "juiza", "rotulo": "juíza", "falhou": 2},
        {"id": "enriquecimento", "rotulo": "enriquecimento", "falhou": 1},
        {"id": "noticias", "rotulo": "notícias", "falhou": 1},
    ]


def test_falhas_etapas_sem_secao(tmp_path):
    resultado = falhas_etapas(_escrever(tmp_path, CABECALHO))
    assert resultado["disponivel"] is False
    assert resultado["motivo"] == "Seção não encontrada no diagnóstico."
    assert resultado["itens"] == []
