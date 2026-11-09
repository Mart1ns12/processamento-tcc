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
    "valor_distinto", "coluna_preenchida", "indices_desde", "divergencia_e_mudanca",
    "da_nao_financeiras",
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
    assert [i["estado"] for i in d["itens"]] == (
        ["pendente"] * 4 + ["entregue"] * 4 + ["pendente"] + ["entregue"] + ["sem_dados"] * 2
        + ["sem_checagem"] * 7)
    assert d["contagem"] == {"entregue": 5, "pendente": 5, "sem_dados": 2, "sem_checagem": 7, "erro": 0}
    assert [i["evidencia"] for i in d["itens"]] == [
        "Meses ainda com poucas notícias: 01/2025, 06/2025, 07/2025",
        "6.560 sem FinBERT",
        "38 linhas incoerentes com os eventos",
        "Ainda no diagnóstico: JBSS32 20/11/2020, NATU3 20/11/2020",
        "Tudo presente: qtd_on_base_atual, qtd_pn_base_atual, v1-eventos_acoes",
        "cvm_ipe: 2023: 3.704 · 2025: 3.687",
        "JBSS32: 2 emissores · NATU3: 3 emissores",
        "ajuste_ifrs17: 12 linhas em v1-balancos.situacao",
        "98,1% preenchida (7.903 vazias)",
        "IDIV, IFIX, SMLL desde 30/12/2019, sem lacunas.",
        "O diagnóstico ainda não lista as mudanças de ticker (rode o diagnóstico de novo).",
        "Seção não encontrada no diagnóstico.",
    ] + ["sem checagem automática"] * 7


def test_yaml_real_tem_os_itens_na_ordem():
    d = avaliar_pedidos(YAML_REAL, FIXTURE)
    assert [i["id"] for i in d["itens"]] == [
        "google_news_2025", "finbert_juiza_cvm", "acoes_sem_evento", "linha_sem_pregao",
        "qtd_base_preco", "cvm_2023_2025", "emissores_jbs_natura", "hapvida_ifrs17",
        "juiza_historico", "indices_completos", "raiz4_raiz55", "ebitda_balancos",
        "balanco_bancos_seguradoras", "dfp_2025_santander", "balancos_assai", "balancos_bradespar",
        "balancos_tim", "emprestimos_zerados", "proventos_bdr_jbs",
    ]
    assert d["itens"][0]["prioridade"] == "critico"
    assert d["itens"][0]["checagem"] == "meses_sem_poucas_noticias"
    assert d["itens"][1]["prioridade"] == "normal"


def test_registro_tem_exatamente_os_doze_nomes():
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
    com_checagem = [i for i in d["itens"] if i["checagem"]]
    assert all(i["estado"] == "sem_dados" for i in com_checagem)
    assert all(i["estado"] == "sem_checagem" for i in d["itens"] if not i["checagem"])
    assert {i["evidencia"] for i in com_checagem} == {
        "docs/diagnostico_banco.md não encontrado (rode o diagnóstico)"}
    assert d["contagem"]["sem_dados"] == 12


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
    ("divergencia_e_mudanca", '{tema: "other_codes", termo: "RAIZ4", antigo: "RAIZ4", novo: "RAIZ55"}'),
    ("da_nao_financeiras", "{excecoes: []}"),
])
def test_checagem_com_docs_vazio_nao_levanta(tmp_path, nome, params):
    docs = tmp_path / "vazio.md"
    docs.write_text("# Diagnóstico\n", encoding="utf-8")
    d = avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra=f'    checagem: "{nome}"\n    parametros: {params}\n')), docs)
    assert d["itens"][0]["estado"] in ("sem_dados", "erro")
    assert d["itens"][0]["estado"] != "entregue"


# ---------------------------------------------------------------- divergencia_e_mudanca

LINHA_DIV_RAIZ4 = ("| 1 | other_codes | v1-raw_b3_cadastro | "
                   "ticker fora do other_codes da empresa: RAIZ4 (33453598000123) |\n")
PEDIDO_RAIZ4 = ('    checagem: "divergencia_e_mudanca"\n'
                '    parametros: {tema: "other_codes", termo: "RAIZ4", antigo: "RAIZ4", novo: "RAIZ55"}\n')


def _docs_divergencias(tmp_path: Path, linhas_div: str = "", notas_secao9: list[str] | None = None) -> Path:
    """Diagnóstico mínimo: tabela de divergências e a §9 Tickers e CNPJs com as notas dadas."""
    docs = tmp_path / "diagnostico_banco.md"
    notas = "".join(f"- {n}\n" for n in notas_secao9 or [])
    docs.write_text(
        "# Diagnóstico do banco da coleta (só leitura)\n- Gerado em: 2026-11-08 13:04 (America/Sao_Paulo)\n\n"
        "## Divergências × especificação\n\n| # | Tema | Tabela | Detalhe |\n|---|---|---|---|\n"
        + linhas_div + "\n## 9. Tickers e CNPJs\n\n" + notas, encoding="utf-8")
    return docs


def _item_raiz4(tmp_path: Path, docs: Path) -> dict:
    return avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra=PEDIDO_RAIZ4)), docs)["itens"][0]


def test_divergencia_presente_sem_nota_fica_pendente(tmp_path):
    item = _item_raiz4(tmp_path, _docs_divergencias(tmp_path, LINHA_DIV_RAIZ4))
    assert item["estado"] == "pendente"
    assert item["evidencia"] == "Divergência other_codes da RAIZ4 ainda no diagnóstico"


def test_sem_divergencia_e_sem_nota_fica_sem_dados(tmp_path):
    item = _item_raiz4(tmp_path, _docs_divergencias(tmp_path))
    assert item["estado"] == "sem_dados"
    assert item["evidencia"] == "O diagnóstico ainda não lista as mudanças de ticker (rode o diagnóstico de novo)."


def test_nota_com_o_par_e_sem_divergencia_fica_entregue(tmp_path):
    docs = _docs_divergencias(tmp_path, notas_secao9=["mudanças registradas em v1-mudancas_ticker: "
                                                     "ELET3 → AXIA3, RAIZ4 → RAIZ55"])
    item = _item_raiz4(tmp_path, docs)
    assert item["estado"] == "entregue"
    assert item["evidencia"] == "RAIZ4 → RAIZ55 em v1-mudancas_ticker e sem divergência other_codes"


def test_nota_sem_o_par_e_sem_divergencia_fica_pendente(tmp_path):
    docs = _docs_divergencias(tmp_path, notas_secao9=["mudanças registradas em v1-mudancas_ticker: "
                                                     "ELET3 → AXIA3"])
    item = _item_raiz4(tmp_path, docs)
    assert item["estado"] == "pendente"
    assert item["evidencia"] == "RAIZ4 → RAIZ55 não está em v1-mudancas_ticker"


def test_nota_com_o_par_mas_divergencia_presente_fica_pendente(tmp_path):
    docs = _docs_divergencias(tmp_path, LINHA_DIV_RAIZ4,
                              notas_secao9=["mudanças registradas em v1-mudancas_ticker: RAIZ4 → RAIZ55"])
    item = _item_raiz4(tmp_path, docs)
    assert item["estado"] == "pendente"
    assert item["evidencia"] == "Divergência other_codes da RAIZ4 ainda no diagnóstico"


def test_sem_secao_de_divergencias_devolve_sem_dados_na_checagem():
    resultado = CHECAGENS["divergencia_e_mudanca"]({}, [], tema="other_codes", termo="RAIZ4",
                                                    antigo="RAIZ4", novo="RAIZ55")
    assert resultado == (None, "Seção de divergências não encontrada no diagnóstico.")


# ---------------------------------------------------------------- coluna_preenchida: estrito e contagem

def _docs_nulos(tmp_path: Path, total: int, nulos: int, pct: str) -> Path:
    docs = tmp_path / "diagnostico_banco.md"
    docs.write_text(
        "# Diagnóstico\n- Gerado em: 2026-11-08 13:04 (America/Sao_Paulo)\n\n"
        "## Divergências × especificação\n\nNenhuma divergência encontrada.\n\n"
        "## 16. Vazios e zeros\n\n### Colunas com nulos, textos vazios ou zeros\n\n"
        "| tabela | coluna | total | nulos | pct_nulo | situacao | textos_vazios | zeros |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"| v1-noticias | papel | {total} | {nulos} | {pct} | parcial | 0 | 0 |\n", encoding="utf-8")
    return docs


def _estado_papel(tmp_path: Path, docs: Path, estrito: bool) -> dict:
    flag = "true" if estrito else "false"
    extra = ('    checagem: "coluna_preenchida"\n'
             f'    parametros: {{tabela: "v1-noticias", coluna: "papel", max_pct_nulo: 0.1, estrito: {flag}}}\n')
    return avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra=extra)), docs)["itens"][0]


def test_coluna_estrito_compara_pela_contagem_e_entrega(tmp_path):
    # 6 de 10000 = 0,06%: o .md arredonda para 0.1, mas a contagem vale abaixo de 0,1%
    item = _estado_papel(tmp_path, _docs_nulos(tmp_path, 10000, 6, "0.1"), estrito=True)
    assert item["estado"] == "entregue"
    assert item["evidencia"] == "99,9% preenchida (6 vazias)"


def test_coluna_estrito_exatamente_no_limite_fica_pendente(tmp_path):
    # 10 de 10000 = 0,1% exato: com estrito, não é "abaixo de" 0,1%
    item = _estado_papel(tmp_path, _docs_nulos(tmp_path, 10000, 10, "0.1"), estrito=True)
    assert item["estado"] == "pendente"


def test_coluna_sem_estrito_aceita_o_limite_exato(tmp_path):
    item = _estado_papel(tmp_path, _docs_nulos(tmp_path, 10000, 10, "0.1"), estrito=False)
    assert item["estado"] == "entregue"


def test_finbert_so_finbert_ignora_a_juiza(tmp_path):
    bloco = _pedido(extra='    checagem: "finbert_e_juiza_completos"\n    parametros: {so_finbert: true}\n')
    d = avaliar_pedidos(_um_pedido(tmp_path, bloco), FIXTURE)
    assert d["itens"][0]["estado"] == "pendente"
    assert d["itens"][0]["evidencia"] == "6.560 sem FinBERT"


# ---------------------------------------------------------------- da_nao_financeiras

EXCECOES_DA = ('    checagem: "da_nao_financeiras"\n'
               '    parametros: {excecoes: [{ticker: "GMAT3", de: "1T20", ate: "3T21"}, '
               '{ticker: "BRAV3", de: "2T20", ate: "2T20"}]}\n')


def _docs_da(tmp_path: Path, tabela_linhas: str = "", notas: list[str] | None = None,
             com_secao: bool = True) -> Path:
    """Diagnóstico mínimo: a §4 Balanços com as notas e, se houver linhas, a tabela de D&A vazia."""
    docs = tmp_path / "diagnostico_banco.md"
    corpo = ""
    if com_secao:
        notas_md = "".join(f"- {n}\n" for n in notas or [])
        tabela = ""
        if tabela_linhas:
            tabela = ("\n### D&A vazia nas não financeiras\n\n"
                      "| ticker | cnpj | trimestre | linhas | situacao |\n|---|---|---|---|---|\n" + tabela_linhas)
        corpo = f"## 4. Balanços (v1-balancos)\n\n{notas_md}{tabela}\n"
    docs.write_text("# Diagnóstico do banco da coleta (só leitura)\n- Gerado em: 2026-11-09 10:00 (America/Sao_Paulo)\n\n"
                    "## Divergências × especificação\n\nNenhuma divergência encontrada.\n\n" + corpo,
                    encoding="utf-8")
    return docs


def _item_da(tmp_path: Path, docs: Path, excecoes: str = EXCECOES_DA) -> dict:
    return avaliar_pedidos(_um_pedido(tmp_path, _pedido(extra=excecoes)), docs)["itens"][0]


def test_da_so_com_linhas_explicadas_fica_entregue(tmp_path):
    tabela = ("| GMAT3 | 33333333000133 | 2T20 | 3 | ok |\n"
              "| BRAV3 | 44444444000144 | 2T20 | 1 | ok |\n"
              "| GMAT3 | 33333333000133 | 3T21 | 1 | ok |\n")
    item = _item_da(tmp_path, _docs_da(tmp_path, tabela))
    assert item["estado"] == "entregue"
    assert item["evidencia"] == "Só as exceções explicadas (3 trimestres): GMAT3 1T20–3T21, BRAV3 2T20"


def test_da_linha_fora_das_excecoes_fica_pendente_com_a_empresa(tmp_path):
    tabela = ("| GMAT3 | 33333333000133 | 2T20 | 3 | ok |\n"
              "| PETR4 | 55555555000155 | 1T22 | 1 | ok |\n"
              "| PETR4 | 55555555000155 | 2T22 | 1 | ok |\n")
    item = _item_da(tmp_path, _docs_da(tmp_path, tabela))
    assert item["estado"] == "pendente"
    assert item["evidencia"] == "D&A vazia fora das exceções: PETR4 1T22–2T22 (2 trimestres)"


def test_da_excecao_sem_periodo_vale_para_todos_os_trimestres(tmp_path):
    # 09/11/2026: BRAP4 (holding sem D&A) é exceção em todos os trimestres.
    excecoes = ('    checagem: "da_nao_financeiras"\n'
                '    parametros: {excecoes: [{ticker: "BRAV3", de: "2T20", ate: "2T20"}, {ticker: "BRAP4"}]}\n')
    tabela = ("| BRAP4 | 03847461000192 | 1T20 | 1 | ok |\n"
              "| BRAP4 | 03847461000192 | 2T26 | 2 | individual |\n"
              "| BRAV3 | 44444444000144 | 2T20 | 1 | ok |\n")
    item = _item_da(tmp_path, _docs_da(tmp_path, tabela), excecoes)
    assert item["estado"] == "entregue"
    assert item["evidencia"] == "Só as exceções explicadas (3 trimestres): BRAV3 2T20, BRAP4 (todos)"


def test_da_trimestre_ilegivel_nunca_e_explicado(tmp_path):
    tabela = "| GMAT3 | 33333333000133 | ?T21 | 1 | ok |\n"
    item = _item_da(tmp_path, _docs_da(tmp_path, tabela))
    assert item["estado"] == "pendente"
    assert item["evidencia"] == "D&A vazia fora das exceções: GMAT3 ?T21"


def test_da_lista_de_empresas_limitada_a_10_com_e_mais(tmp_path):
    tabela = "".join(f"| CMP{i:02d}3 | {i:014d} | 1T22 | 1 | ok |\n" for i in range(11))
    item = _item_da(tmp_path, _docs_da(tmp_path, tabela))
    assert item["estado"] == "pendente"
    assert item["evidencia"].endswith(" e mais 1")
    assert item["evidencia"].count(", ") == 9


def test_da_nenhuma_entregue_com_nota_nenhuma(tmp_path):
    docs = _docs_da(tmp_path, notas=["D&A vazia nas não financeiras: nenhuma"])
    item = _item_da(tmp_path, docs)
    assert item["estado"] == "entregue"
    assert item["evidencia"] == "D&A preenchida em todas as não financeiras."


def test_da_sem_a_secao_de_balancos_fica_sem_dados(tmp_path):
    item = _item_da(tmp_path, _docs_da(tmp_path, com_secao=False))
    assert item["estado"] == "sem_dados"
    assert item["evidencia"] == "Seção não encontrada no diagnóstico."


def test_da_excecao_com_rotulo_invalido_vira_erro(tmp_path):
    excecoes = ('    checagem: "da_nao_financeiras"\n'
                '    parametros: {excecoes: [{ticker: "GMAT3", de: "5T20", ate: "3T21"}]}\n')
    tabela = "| GMAT3 | 33333333000133 | 2T20 | 3 | ok |\n"
    item = _item_da(tmp_path, _docs_da(tmp_path, tabela), excecoes)
    assert item["estado"] == "erro"
