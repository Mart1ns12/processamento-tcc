"""Testes de processamento/painel/saude.py: cartões de saúde a partir do diagnóstico.

Usam tests/dados/painel/diagnostico_completo.md (fixture), a árvore raiz de fabrica_painel (tmp_path)
e, só para leitura, o docs/diagnostico_banco.md real. Nenhum teste usa banco ou rede.
"""

from pathlib import Path

import pytest
from fabrica_painel import montar_raiz

from processamento.painel.saude import afetadas_saude, cartoes_saude, tabela_md

FIXTURE = Path(__file__).resolve().parent / "dados" / "painel" / "diagnostico_completo.md"
REAL = Path(__file__).resolve().parents[1] / "docs" / "diagnostico_banco.md"
NOVIDADES = Path(__file__).resolve().parent / "dados" / "painel" / "novidades"

DIAG_ZEROS = (
    "- Gerado em: 2026-10-25 08:00 (America/Sao_Paulo)\n"
    "## Divergências × especificação\n"
    "Nenhuma divergência encontrada.\n"
    "## 10. Quantidade de ações suspeita\n"
    "- nenhuma empresa com quantidade de ações suspeita em 2026-10-23\n"
    "## 11. Retornos diários suspeitos\n"
    "- nenhum retorno diário suspeito (fechamento_ajustado abaixo de -75% ou acima de 100%)\n"
    "## 12. Lacunas nas séries de preços e índices\n"
    "- nenhuma lacuna de mais de 5 pregões em v1-precos (regra)\n"
    "- nenhuma lacuna em v1-indices (regra)\n"
)


def _escrever(tmp_path: Path, texto: str) -> Path:
    caminho = tmp_path / "diagnostico_banco.md"
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def _farois(resultado: dict) -> list[str]:
    return [c["farol"] for c in resultado["cartoes"]]


def test_fixture_seis_cartoes_com_valores_esperados():
    resultado = cartoes_saude(FIXTURE)

    assert resultado["disponivel"] is True
    assert resultado["motivo"] is None
    assert resultado["gerado_em"] == "2026-10-24 21:08 (America/Sao_Paulo)"
    assert resultado["cartoes"] == [
        {"id": "contrato", "titulo": "Contrato com a coleta", "farol": "ok",
         "numero": "0 divergências",
         "texto": "Tabelas, colunas e formatos batem com a especificação.",
         "fonte": "Divergências × especificação"},
        {"id": "quantidade_acoes", "titulo": "Quantidade de ações", "farol": "warn",
         "numero": "19 empresas",
         "texto": ("Provavelmente em milhares (ex.: AXIA3, ENEV3, ABEV3). P/L, P/VP e payout delas saem "
                   "indisponível em 23/10/2026; yield, ROE, margens, EBITDA e endividamento não mudam."),
         "fonte": "Seção 10: Quantidade de ações suspeita"},
        {"id": "retornos", "titulo": "Preços suspeitos", "farol": "warn",
         "numero": "5 retornos",
         "texto": ("AZUL3 (3), PCAR3, UGPA3: ficam fora das séries e das medianas do setor; "
                   "o preço não é corrigido."),
         "fonte": "Seção 11: Retornos diários suspeitos"},
        {"id": "lacunas", "titulo": "Lacunas nas séries", "farol": "warn",
         "numero": "3 lacunas",
         "texto": ("Preços: nenhuma lacuna. Índices: IDIV, IFIX, SMLL: 449 pregões "
                   "(02/01/2025 a 19/10/2026)."),
         "fonte": "Seção 12: Lacunas nas séries de preços e índices"},
        {"id": "horario_noticias", "titulo": "Horário das notícias", "farol": "warn",
         "numero": "90,8% sem hora real",
         "texto": ("Com hora real: 9,2% · só data (regra N1-A): 71,7% · sem hora: 19,2%. "
                   "Notícias sem hora entram na janela do dia de forma conservadora."),
         "fonte": "Seção 5: Notícias (v1-noticias) · 183.643 artigos"},
        {"id": "cobertura", "titulo": "Histórico disponível", "farol": "ok",
         "numero": "117.435 linhas",
         "texto": "1.698 pregões, de 30/12/2019 a 23/10/2026, no dataset do experimento.",
         "fonte": ("Seção 15: Histórico novo: composição, corrigir_horas e cobertura do experimento")},
    ]


def test_tabela_md_le_tabelas_da_fixture():
    linhas = FIXTURE.read_text(encoding="utf-8").splitlines()

    lacunas = tabela_md(linhas, "Lacunas em v1-indices")
    assert [r["serie"] for r in lacunas] == ["IDIV", "IFIX", "SMLL"]
    assert lacunas[0]["tamanho"] == "449"

    empresas = tabela_md(linhas, "Empresas com quantidade de ações suspeita")
    assert len(empresas) == 4
    assert empresas[0]["tickers"] == "AXIA3"

    horas = tabela_md(linhas, "Hora da publicação, por ano (artigos distintos)")
    assert [r["ano"] for r in horas] == ["2024", "2025", "2026"]

    assert tabela_md(linhas, "Subtítulo que não existe") is None


def test_arquivo_ausente_fica_indisponivel(tmp_path):
    resultado = cartoes_saude(tmp_path / "nao_existe.md")

    assert resultado["disponivel"] is False
    assert resultado["motivo"]
    assert resultado["gerado_em"] is None
    assert resultado["cartoes"] == []


def test_secao_ausente_vira_cartao_idle(tmp_path):
    resultado = cartoes_saude(_escrever(tmp_path, DIAG_ZEROS))

    horario = resultado["cartoes"][4]
    assert horario["id"] == "horario_noticias"
    assert horario["farol"] == "idle"
    assert horario["numero"] == "sem dados"
    assert horario["texto"] == "Seção não encontrada no diagnóstico."
    assert horario["fonte"] is None

    cobertura = resultado["cartoes"][5]
    assert cobertura["farol"] == "idle"
    assert cobertura["numero"] == "sem dados"
    assert cobertura["fonte"] is None


def test_nota_nao_reconhecida_vira_idle_com_fonte(tmp_path):
    texto = DIAG_ZEROS.replace(
        "- nenhuma empresa com quantidade de ações suspeita em 2026-10-23",
        "- texto que o painel não conhece",
    )
    resultado = cartoes_saude(_escrever(tmp_path, texto))

    quantidade = resultado["cartoes"][1]
    assert quantidade["farol"] == "idle"
    assert quantidade["numero"] == "sem dados"
    assert quantidade["texto"] == "Formato da nota não reconhecido."
    assert quantidade["fonte"] == "Seção 10: Quantidade de ações suspeita"


def test_zeros_viram_cartoes_ok(tmp_path):
    resultado = cartoes_saude(_escrever(tmp_path, DIAG_ZEROS))

    assert resultado["disponivel"] is True
    assert resultado["gerado_em"] == "2026-10-25 08:00 (America/Sao_Paulo)"
    assert _farois(resultado) == ["ok", "ok", "ok", "ok", "idle", "idle"]

    quantidade, retornos, lacunas = resultado["cartoes"][1:4]
    assert quantidade["numero"] == "0 empresas"
    assert quantidade["texto"] == "Nenhuma empresa com quantidade de ações fora do plausível em 23/10/2026."
    assert retornos["numero"] == "0 retornos"
    assert retornos["texto"] == "Nenhum retorno diário suspeito."
    assert lacunas["numero"] == "0 lacunas"
    assert lacunas["texto"] == "Preços: nenhuma lacuna. Índices: nenhuma lacuna."


def test_diagnostico_da_raiz_de_fixture(tmp_path):
    raiz = montar_raiz(tmp_path)

    resultado = cartoes_saude(raiz / "docs" / "diagnostico_banco.md")

    assert resultado["disponivel"] is True
    assert resultado["cartoes"][0] == {
        "id": "contrato", "titulo": "Contrato com a coleta", "farol": "bad",
        "numero": "2 divergências", "texto": "Temas: coluna_faltando, falha_consulta.",
        "fonte": "Divergências × especificação",
    }
    assert _farois(resultado) == ["bad", "idle", "idle", "idle", "idle", "idle"]
    assert resultado["cartoes"][1]["numero"] == "sem dados"
    assert resultado["cartoes"][1]["fonte"] is None


def test_afetadas_fixture_quantidade_retornos_e_lacunas():
    afetadas = afetadas_saude(FIXTURE)

    assert "contrato" not in afetadas
    assert [i["rotulo"] for i in afetadas["quantidade_acoes"]["itens"]] == ["AXIA3", "ENEV3", "ABEV3", "EMBJ3"]
    assert afetadas["quantidade_acoes"]["total"] == 4
    assert afetadas["quantidade_acoes"]["titulo"] == "Empresas afetadas"
    assert [(i["rotulo"], i["detalhe"]) for i in afetadas["retornos"]["itens"]] == [
        ("AZUL3", "10/02/2026"), ("AZUL3", "09/04/2026"), ("AZUL3", "20/04/2026"),
        ("PCAR3", "01/03/2021"), ("UGPA3", "28/06/2021"),
    ]
    assert afetadas["retornos"]["titulo"] == "Ações afetadas"
    assert [(i["rotulo"], i["detalhe"]) for i in afetadas["lacunas"]["itens"]] == [
        ("IDIV", "02/01/2025 a 19/10/2026"),
        ("IFIX", "02/01/2025 a 19/10/2026"),
        ("SMLL", "02/01/2025 a 19/10/2026"),
    ]
    assert afetadas["lacunas"]["titulo"] == "Séries afetadas"


def test_afetadas_contrato_da_raiz_de_fixture(tmp_path):
    raiz = montar_raiz(tmp_path)

    afetadas = afetadas_saude(raiz / "docs" / "diagnostico_banco.md")

    assert afetadas["contrato"] == {
        "titulo": "Tabelas afetadas",
        "itens": [{"rotulo": "v1-precos", "detalhe": "coluna_faltando"}],
        "total": 1,
    }


def test_afetadas_diagnostico_atual_da_novidades():
    afetadas = afetadas_saude(NOVIDADES / "atual.md")

    assert [i["rotulo"] for i in afetadas["quantidade_acoes"]["itens"]] == ["HAPV3"]
    assert [(i["rotulo"], i["detalhe"]) for i in afetadas["retornos"]["itens"]] == [
        ("PCAR3", "01/03/2021"), ("UGPA3", "28/06/2021"),
    ]
    assert [(i["rotulo"], i["detalhe"]) for i in afetadas["lacunas"]["itens"]] == [
        ("IDIV", "02/01/2025 a 30/12/2025"),
        ("IFIX", "02/01/2025 a 30/12/2025"),
        ("SMLL", "02/01/2025 a 30/12/2025"),
    ]
    assert "contrato" not in afetadas


def test_afetadas_arquivo_ausente_vira_dict_vazio(tmp_path):
    assert afetadas_saude(tmp_path / "nao_existe.md") == {}


@pytest.mark.skipif(not REAL.is_file(), reason="docs/diagnostico_banco.md não existe neste checkout")
def test_diagnostico_real_nenhum_cartao_idle():
    # Só leitura: o diagnóstico real precisa reconhecer todos os seis cartões.
    resultado = cartoes_saude(REAL)

    assert resultado["disponivel"] is True
    assert [c["id"] for c in resultado["cartoes"]] == [
        "contrato", "quantidade_acoes", "retornos", "lacunas", "horario_noticias", "cobertura",
    ]
    idle = [c["id"] for c in resultado["cartoes"] if c["farol"] == "idle"]
    assert idle == []
