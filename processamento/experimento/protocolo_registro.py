"""Registro de tentativas do protocolo (docs/protocolo_tentativas.jsonl): só acréscimo, uma linha JSON por evento.

Cada linha guarda o sha256 do texto da linha anterior (`sha_anterior`; "" na primeira) e um `seq` contínuo.
Editar, apagar ou reordenar uma linha quebra a cadeia e `ler` levanta `ErroRegistro`. Limite: a última linha
não tem linha seguinte para guardar o seu hash, então uma edit só nela não aparece aqui.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from processamento.experimento import modelos, treino


class ErroRegistro(Exception):
    """Registro adulterado, incompleto ou ilegível."""


def _sha_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _linha_json(evento: dict) -> str:
    return json.dumps(evento, ensure_ascii=False, sort_keys=True)


def _linhas_brutas(caminho: Path) -> list[str]:
    """Linhas do arquivo, sem o "\\n" final. Arquivo ausente: lista vazia."""
    if not caminho.exists():
        return []
    texto = caminho.read_text(encoding="utf-8")
    if texto and not texto.endswith("\n"):
        raise ErroRegistro(f"{caminho.name}: última linha incompleta")
    return texto.split("\n")[:-1] if texto else []


def ler(caminho: Path) -> list[dict]:
    """Eventos do registro, na ordem. Arquivo ausente: lista vazia. Cadeia quebrada: ErroRegistro."""
    eventos: list[dict] = []
    sha_anterior = ""
    for numero, linha in enumerate(_linhas_brutas(caminho), start=1):
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError as erro:
            raise ErroRegistro(f"{caminho.name}: linha {numero} não é JSON ({erro})") from erro
        if evento.get("seq") != numero or evento.get("sha_anterior") != sha_anterior:
            raise ErroRegistro(f"{caminho.name}: cadeia quebrada na linha {numero}")
        eventos.append(evento)
        sha_anterior = _sha_texto(linha)
    return eventos


def acrescentar(caminho: Path, evento: dict) -> dict:
    """Acrescenta um evento (com `seq` e `sha_anterior`) e devolve o registro gravado. Confere a cadeia antes."""
    eventos = ler(caminho)
    linhas = _linhas_brutas(caminho)
    sha_anterior = _sha_texto(linhas[-1]) if linhas else ""
    registro = {**evento, "seq": len(eventos) + 1, "sha_anterior": sha_anterior}
    linha = _linha_json(treino._para_json(registro))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8", newline="\n") as arq:
        arq.write(linha + "\n")
    return json.loads(linha)


def proxima_rodada(eventos: list[dict], tipo: str) -> int:
    """Número da próxima rodada do tipo: conta os inícios, inclusive os sem fim (rodada interrompida)."""
    return sum(1 for e in eventos if e.get("tipo") == tipo and e.get("evento") == "inicio") + 1


def primeira_rodada_completa(eventos: list[dict], tipo: str) -> dict | None:
    """Primeiro evento "fim" do tipo (rodada que chegou ao relatório), ou None."""
    return next((e for e in eventos if e.get("tipo") == tipo and e.get("evento") == "fim"), None)


def rodadas_iguais(eventos: list[dict], tipo: str, assinatura: dict) -> list[dict]:
    """Eventos "fim" do tipo com a mesma assinatura (mesmas entradas)."""
    return [e for e in eventos if e.get("tipo") == tipo and e.get("evento") == "fim" and e.get("assinatura") == assinatura]


def sha_regras(doc_protocolo: Path, limites) -> str:
    """Hash das regras: texto da seção 3 até antes da seção 6 do protocolo (fim de linha normalizado), mais os limites."""
    texto = doc_protocolo.read_text(encoding="utf-8").replace("\r\n", "\n")
    inicio = texto.find("## 3.")
    if inicio == -1:
        raise ErroRegistro(f"{doc_protocolo.name}: seção 3 não encontrada")
    fim = texto.find("## 6.", inicio)
    trecho = texto[inicio:] if fim == -1 else texto[inicio:fim]
    return _sha_texto(trecho + "\n" + repr(limites))


def sha_parametros(params) -> str:
    """Hash dos parâmetros de treino (JSON ordenado)."""
    return _sha_texto(_linha_json(treino._para_json(dataclasses.asdict(params))))


def sha_codigo(arquivos: list[Path]) -> str:
    """Hash combinado dos arquivos de código, na ordem dada (nome e sha256 de cada um)."""
    return _sha_texto("".join(f"{Path(a).name}:{modelos.sha256_arquivo(Path(a))}\n" for a in arquivos))
