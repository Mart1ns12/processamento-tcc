"""Testes de processamento/painel/pedidos.py: pedidos à coleta conferidos contra o diagnóstico.

Usam tests/dados/painel/diagnostico_coleta.md (fixture), o YAML real de processamento/config e
arquivos montados em tmp_path. Nenhum teste usa banco ou rede.
"""

from pathlib import Path

import pytest

from processamento.painel import pedidos
from processamento.painel.pedidos import CHECAGENS, avaliar_pedidos

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / "tests" / "dados" / "painel" / "diagnostico_coleta.md"
YAML_REAL = RAIZ / "processamento" / "config" / "pedidos_coleta.yaml"
DOCS_REAL = RAIZ / "docs" / "diagnostico_banco.md"

NOMES_CHECAGENS = {
    "meses_sem_poucas_noticias", "finbert_e_juiza_completos", "acoes_coerentes_com_eventos",
    "sem_linha_fora_do_calendario", "colunas_existem", "origem_nos_anos", "emissores_por_periodo",
    "valor_distinto", "coluna_preenchida", "indices_desde",
}


def _yaml(tmp_path: Path, texto: str) -> Path:
    caminho = tmp_path / "pedidos_coleta.yaml"
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def _um_pedido(tmp_path: Path, bloco: str) -> Path:
    return _yaml(tmp_path, "pedidos:\n" + bloco)


def _pedido(id_: str = "p1", extra: str = "", prioridade: str = "normal") -> str:
    return (f'  - id: "{id_}"\n    texto: "Texto de {id_}"\n    detalhe: "Detalhe"\n'
            f'    prioridade: "{prioridade}"\n{extra}')


# ---------------------------------------------------------------- YAML real com a fixture

def test_yaml_real_com_fixture_bate_com_o_gabarito():
    d = avaliar_pedidos(YAML_REAL, FIXTURE)
    assert d["disponivel"] is True
    assert d["motivo"] is None
    assert d["gerado_em"] == "2026-11-03 13:09 (America/Sao_Paulo)"
    assert [i["estado"] for i in d["itens"]] == ["pendente"] * 4 + ["entregue"] * 6
    assert d["contagem"] == {"entregue": 6, "pendente": 4, "sem_dados": 0, "sem_checagem": 0, "erro": 0}
    assert [i["evidencia"] for i in d["itens"]] == [
        "Meses ainda com poucas notícias: 01/2025, 06/2025, 07/2025",
        "6.560 sem FinBERT · 7.903 sem juíza",
        "38 linhas incoerentes com os eventos",
        "Ainda no diagnóstico: JBSS32 20/11/2020, NATU3 20/11/2020",
        "Tudo presente: qtd_on_base_atual, qtd_pn_base_atual, v1-eventos_acoes",
        "cvm_ipe: 2023: 3.704 · 2025: 3.687",
        "JBSS32: 2 emissores · NATU3: 3 emissores",
        "ajuste_ifrs17: 12 linhas em v1-balancos.situacao",
        "98,1% preenchida (7.903 vazias)",
        "IDIV, IFIX, SMLL desde 30/12/2019, sem lacunas.",
    ]


def test_yaml_real_tem_os_dez_itens_na_ordem_do_plano():
    d = avaliar_pedidos(YAML_REAL, FIXTURE)
    assert [i["id"] for i in d["itens"]] == [
        "google_news_2025", "finbert_juiza_cvm", "acoes_sem_evento", "linha_sem_pregao",
        "qtd_base_preco", "cvm_2023_2025", "emissores_jbs_natura", "hapvida_ifrs17",
        "juiza_historico", "indices_completos",
    ]
    assert d["itens"][0]["prioridade"] == "critico"
    assert d["itens"][0]["checagem"] == "meses_sem_poucas_noticias"
    assert d["itens"][1]["prioridade"] == "normal"


def test_registro_tem_exatamente_os_dez_nomes():
    assert set(CHECAGENS) == NOMES_CHECAGENS


# ---------------------------------------------------------------- erros de arquivo

def test_arquivo_ausente_fica_indisponivel(tmp_path):
    d = avaliar_pedidos(tmp_path / "nao_existe.yaml", FIXTURE)
    assert d["disponivel"] is False
    assert d["motivo"] == "processamento/config/pedidos_coleta.yaml não encontrado"
    assert d["itens"] == []


def test_yaml_ilegivel_fica_indisponivel(tmp_path):
    d = avaliar_pedidos(_yaml(tmp_path, "pedidos: [\n"), FIXTURE)
    assert d["disponivel"] is False
    assert d["motivo"] == "pedidos_coleta.yaml ilegível"


def test_pedidos_que_nao_e_lista_fica_indisponivel(tmp_path):
    d = avaliar_pedidos(_yaml(tmp_path, "pedidos: 3\n"), FIXTURE)
    assert d["disponivel"] is False
    assert d["motivo"] == "pedidos_coleta.yaml ilegível"


def test_docs_inexistente_vira_sem_dados_com_motivo(tmp_path):
    d = avaliar_pedidos(YAML_REAL, tmp_path / "sem_diagnostico.md")
    assert d["disponivel"] is True
    assert d["gerado_em"] is None
    assert all(i["estado"] == "sem_dados" for i in d["itens"])
    assert {i["evidencia"] for i in d["itens"]} == {
        "docs/diagnostico_banco.md não encontrado (rode o diagnóstico)"}
    assert d["contagem"]["sem_dados"] == 10


# ---------------------------------------------------------------- regras do YAML

def test_checagem_desconhecida_vira_sem_checagem(tmp_path):
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra='    checagem: "nao_existe"\n')), FIXTURE)
    assert d["itens"][0]["estado"] == "sem_checagem"
    assert d["itens"][0]["evidencia"] == "checagem desconhecida: nao_existe"


def test_sem_checagem_vira_sem_checagem_automatica(tmp_path):
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido()), FIXTURE)
    assert d["itens"][0]["estado"] == "sem_checagem"
    assert d["itens"][0]["evidencia"] == "sem checagem automática"
    assert d["itens"][0]["checagem"] is None


def test_parametro_desconhecido_vira_erro(tmp_path):
    bloco = _pedido(extra='    checagem: "valor_distinto"\n    parametros: {xyz: 1}\n')
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), FIXTURE)
    assert d["itens"][0]["estado"] == "erro"
    assert d["itens"][0]["evidencia"] == "erro na checagem (TypeError)"


def test_prioridade_invalida_vira_erro(tmp_path):
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(prioridade="urgente")), FIXTURE)
    assert d["itens"][0]["estado"] == "erro"
    assert d["itens"][0]["evidencia"] == "prioridade inválida"


def test_id_repetido_gera_erro_no_segundo(tmp_path):
    bloco = _pedido("igual") + _pedido("igual")
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), FIXTURE)
    assert [i["estado"] for i in d["itens"]] == ["sem_checagem", "erro"]
    assert d["itens"][1]["evidencia"] == "id repetido"


def test_item_sem_id_ou_texto_e_ignorado(tmp_path):
    bloco = ('  - texto: "sem id"\n'
             '  - id: "sem_texto"\n'
             + _pedido("ok"))
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), FIXTURE)
    assert [i["id"] for i in d["itens"]] == ["ok"]


def test_excecao_da_checagem_vira_erro(tmp_path, monkeypatch):
    def _explode(diag, linhas):
        raise RuntimeError("falhou")

    monkeypatch.setitem(CHECAGENS, "boom", _explode)
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra='    checagem: "boom"\n')), FIXTURE)
    assert d["itens"][0]["estado"] == "erro"
    assert d["itens"][0]["evidencia"] == "erro na checagem (RuntimeError)"


def test_parametros_nao_dict_vira_erro(tmp_path):
    bloco = _pedido(extra='    checagem: "valor_distinto"\n    parametros: [1, 2]\n')
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), FIXTURE)
    assert d["itens"][0]["estado"] == "erro"


def test_resultado_fora_do_contrato_nunca_vira_entregue(tmp_path, monkeypatch):
    monkeypatch.setitem(CHECAGENS, "devolve_texto", lambda diag, linhas: ("sim", "x"))
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra='    checagem: "devolve_texto"\n')), FIXTURE)
    assert d["itens"][0]["estado"] == "erro"


def test_checagem_que_devolve_none_vira_sem_dados(tmp_path, monkeypatch):
    monkeypatch.setitem(CHECAGENS, "nada", lambda diag, linhas: (None, "sem informação"))
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra='    checagem: "nada"\n')), FIXTURE)
    assert d["itens"][0]["estado"] == "sem_dados"
    assert d["itens"][0]["evidencia"] == "sem informação"


# ---------------------------------------------------------------- checagens: ramos de ausência

def test_checagem_sem_secao_devolve_sem_dados(tmp_path):
    docs = tmp_path / "diagnostico_banco.md"
    docs.write_text("# Diagnóstico\n- Gerado em: 2026-11-03 13:09 (America/Sao_Paulo)\n"
                    "## Divergências × especificação\nNenhuma divergência encontrada.\n", encoding="utf-8")
    bloco = _pedido(extra='    checagem: "meses_sem_poucas_noticias"\n'
                          '    parametros: {de: "2025-01", ate: "2025-07"}\n')
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), docs)
    assert d["itens"][0]["estado"] == "sem_dados"
    assert d["itens"][0]["evidencia"] == "Seção não encontrada no diagnóstico."


def test_calendario_sem_nota_nem_tabela_nunca_vira_entregue(tmp_path):
    docs = tmp_path / "diagnostico_banco.md"
    docs.write_text("# Diagnóstico\n- Gerado em: 2026-11-03 13:09 (America/Sao_Paulo)\n"
                    "## Divergências × especificação\nNenhuma divergência encontrada.\n\n"
                    "## 7. Preços (v1-precos)\n\n- 145707 linhas.\n", encoding="utf-8")
    bloco = _pedido(extra='    checagem: "sem_linha_fora_do_calendario"\n'
                          '    parametros: {tickers: ["JBSS32", "NATU3"]}\n')
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), docs)
    assert d["itens"][0]["estado"] == "sem_dados"


@pytest.mark.parametrize("nome, params", [
    ("finbert_e_juiza_completos", "{}"),
    ("acoes_coerentes_com_eventos", "{}"),
    ("sem_linha_fora_do_calendario", '{tickers: ["JBSS32"]}'),
    ("origem_nos_anos", '{origem: "cvm_ipe", anos: [2023]}'),
    ("emissores_por_periodo", '{tickers: ["JBSS32"]}'),
    ("valor_distinto", '{tabela: "v1-balancos", coluna: "situacao", valor: "ajuste_ifrs17"}'),
    ("coluna_preenchida", '{tabela: "v1-noticias", coluna: "papel", max_pct_nulo: 5}'),
    ("indices_desde", '{indices: ["IDIV"], inicio_ate: "2019-12-30"}'),
])
def test_checagem_com_docs_vazio_nao_levanta(tmp_path, nome, params):
    docs = tmp_path / "vazio.md"
    docs.write_text("# Diagnóstico\n", encoding="utf-8")
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra=f'    checagem: "{nome}"\n    parametros: {params}\n')), docs)
    assert d["itens"][0]["estado"] in ("sem_dados", "erro")
    assert d["itens"][0]["estado"] != "entregue"
