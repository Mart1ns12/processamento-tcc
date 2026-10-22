"""Teste do diagnóstico contra o banco real. Opcional: `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`.

Só lê o banco (SELECT/SHOW). Não testa escrita.
"""

import pytest

from processamento import fontes
from processamento.diagnostico.__main__ import coletar

pytestmark = pytest.mark.banco


def test_diagnostico_sem_falha_de_consulta_nem_tabela_do_contrato_ausente():
    engine = fontes.criar_engine()

    def ler(sql, params=None):
        return fontes.executar_leitura(sql, params, engine=engine)

    fontes.verificar_sessao_somente_leitura(ler)

    mapa = fontes.carregar_mapa()
    tabelas_contrato = {cfg["nome_real"] for cfg in mapa["tabelas"].values()}
    assert len(tabelas_contrato) == 8

    secoes = coletar(ler, mapa)
    divergencias = [d for secao in secoes for d in secao["divergencias"]]

    assert not [d for d in divergencias if d["tema"] == "falha_consulta"]
    assert not [
        d for d in divergencias
        if d["tema"] == "tabela_ausente" and d["tabela"] in tabelas_contrato
    ]
