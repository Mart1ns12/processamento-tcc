import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("PROC_TESTES_COM_BANCO") == "1":
        return
    pular = pytest.mark.skip(reason="teste com banco real: rode com PROC_TESTES_COM_BANCO=1 pytest -q -m banco")
    for item in items:
        if "banco" in item.keywords:
            item.add_marker(pular)
