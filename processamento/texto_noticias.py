"""Normalização de título e de URL para comparar notícias (usada por diagnóstico e pela deduplicação).

Funções puras: valor entra, valor sai. Ausência é None, nunca texto vazio.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

import pandas as pd

_RE_SUFIXO_VEICULO = re.compile(r" - [^-]{1,40}$")
_RE_NAO_ALFANUM = re.compile(r"[^a-z0-9]+")


def _nulo(v) -> bool:
    """True para None, NaN e NaT."""
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def normalizar_titulo(titulo) -> str | None:
    """Título para comparar: sem o sufixo " - Veículo" final, minúsculo, sem acento e sem pontuação.

    Devolve None se não sobrar texto.
    """
    if _nulo(titulo):
        return None
    texto = _RE_SUFIXO_VEICULO.sub("", str(titulo).strip())
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _RE_NAO_ALFANUM.sub(" ", texto).strip()
    return texto or None


def dominio(url) -> str | None:
    """Host do link sem "www."; None se vazio ou sem host."""
    if _nulo(url) or not str(url).strip():
        return None
    bruto = str(url).strip()
    if "://" not in bruto:
        bruto = "http://" + bruto
    try:
        host = urlsplit(bruto).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def chave_url(url) -> str | None:
    """Chave para comparar links: domínio + caminho, sem esquema (http/https), sem barra final e sem query."""
    host = dominio(url)
    if host is None:
        return None
    bruto = str(url).strip()
    if "://" not in bruto:
        bruto = "http://" + bruto
    caminho = urlsplit(bruto).path.rstrip("/")
    return f"{host}{caminho}"
