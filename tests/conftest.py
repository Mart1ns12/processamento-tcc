import os
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy

from processamento import fontes


def pytest_collection_modifyitems(config, items):
    if os.environ.get("PROC_TESTES_COM_BANCO") == "1":
        return
    pular = pytest.mark.skip(reason="teste com banco real: rode com PROC_TESTES_COM_BANCO=1 pytest -q -m banco")
    for item in items:
        if "banco" in item.keywords:
            item.add_marker(pular)


DADOS = Path(__file__).parent / "dados"
ARQUIVOS = {"precos.csv": "v1-precos", "cadastro.csv": "v1-cadastro",
            "mudancas_ticker.csv": "v1-mudancas_ticker", "noticias.csv": "v1-noticias",
            "raw_b3_cadastro.csv": "v1-raw_b3_cadastro", "indices.csv": "v1-indices",
            "balancos.csv": "v1-balancos", "acoes_emitidas.csv": "v1-acoes_emitidas",
            "proventos.csv": "v1-proventos", "raw_articles.csv": "raw_articles",
            "raw_ipe_docs.csv": "v1-raw_ipe_docs"}


@pytest.fixture
def banco_teste():
    """Fábrica: SQLite em memória com tests/dados/*.csv. NUNCA o banco da coleta."""
    def _criar(alterar: dict | None = None, omitir: frozenset = frozenset()):
        eng = sqlalchemy.create_engine("sqlite://")
        for arq, tabela in ARQUIVOS.items():
            if tabela in omitir:
                continue
            df = pd.read_csv(DADOS / arq, dtype=str)
            if alterar and tabela in alterar:
                df = alterar[tabela](df)
            df.to_sql(tabela, eng, index=False)
        return lambda sql, params=None: fontes.executar_leitura(sql, params, engine=eng)
    return _criar
