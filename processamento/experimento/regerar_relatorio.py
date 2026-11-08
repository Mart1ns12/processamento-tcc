"""Regera só o `relatorio.md` de uma pasta do treino, a partir do `metricas.json` já gravado (sem retreinar).

Uso: `.venv/Scripts/python.exe -m processamento.experimento.regerar_relatorio <pasta>`

O veredito é recalculado com `treino._veredito` sobre `metricas["modelos"]` (mesma regra e mesmo texto
do treino), e o `metricas.json` não é alterado. Não lê banco nem dados brutos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from processamento.experimento import relatorio, treino


def regerar(pasta: Path | str) -> Path:
    pasta = Path(pasta)
    metricas = json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))
    anterior = metricas.get("veredito_modelo_3") or {}
    if metricas.get("modelos") and anterior.get("referencia_terceira"):
        metricas["veredito_modelo_3"] = treino._veredito(metricas["modelos"], anterior["referencia_terceira"])
    caminho = pasta / "relatorio.md"
    caminho.write_text(relatorio.gerar_relatorio(metricas), encoding="utf-8")
    return caminho


if __name__ == "__main__":
    print(regerar(sys.argv[1]))
