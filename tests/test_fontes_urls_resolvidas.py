"""resolved_url de raw_articles na leitura de v1-noticias: `ler_urls_resolvidas` e `ler_noticias(com_url_resolvida=True)`.

Só leitura, sobre o SQLite de tests/dados (`banco_teste`); nenhum teste usa banco ou rede.
Ids: raw_articles.id 1 vira "n000001" (6 dígitos com zeros à esquerda); 1234567 vira "n1234567".
"""

from __future__ import annotations

import pandas as pd
from fabrica_saida import insumos_de_teste

from processamento import fontes

COLUNAS_V1 = [
    "id", "ticker", "data_hora_publicacao", "data_hora_coleta", "titulo", "fonte", "link",
    "prob_positivo", "prob_neutro", "prob_negativo", "origem", "papel", "tipo_conteudo", "evento",
    "qualidade", "data_publicacao", "momento_pregao",
]
LINK_GN = "https://exemplo.invalid/gn/{}"


def _raw(*linhas):
    """`alterar` do banco_teste para raw_articles: troca a tabela inteira pelas linhas dadas."""
    def _alterar(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(list(linhas), columns=df.columns)
    return _alterar


def _v1(id_: str, ticker: str, origem: str, hora: str, dia: str) -> dict:
    """Uma linha de v1-noticias (texto, como no banco)."""
    return {
        "id": id_, "ticker": ticker, "data_hora_publicacao": f"{dia}T{hora}-03:00",
        "data_hora_coleta": "2026-09-07T17:38:43-03:00", "titulo": f"Noticia {id_}", "fonte": "Fonte",
        "link": f"https://exemplo.invalid/{id_}", "prob_positivo": "0.2", "prob_neutro": "0.5",
        "prob_negativo": "0.3", "origem": origem, "papel": None, "tipo_conteudo": None, "evento": None,
        "qualidade": None, "data_publicacao": dia, "momento_pregao": "durante",
    }


def _acrescentar(*linhas: dict):
    def _alterar(df: pd.DataFrame) -> pd.DataFrame:
        return pd.concat([df, pd.DataFrame(list(linhas), columns=df.columns)], ignore_index=True)
    return _alterar


# raw_articles: google_news com URL (1 e 1234567), google_news sem URL (2, nula; 3, só espaços),
# wordpress com URL (99: origem fora de origens_so_data, não entra)
RAW = [
    (1, "en", "2025-10-17 19:59:00", "minute", "google_news", "https://veiculo.invalid/n1"),
    (1234567, "pt", "2025-10-17 13:00:00", "minute", "google_news", "https://veiculo.invalid/n1234567"),
    (2, "pt", "2025-10-17 13:00:00", "minute", "google_news", None),
    (3, "pt", "2025-10-17 13:00:00", "minute", "google_news", "   "),
    (99, "pt", "2025-10-17 13:00:00", "minute", "wordpress", "https://veiculo.invalid/wp99"),
]
V1_EXTRAS = [
    _v1("n1234567", "PETR4", "google_news", "10:00:00", "2025-10-17"),
    _v1("n000099", "PETR4", "wordpress", "11:00:00", "2025-10-17"),
]


def _espiao(ler):
    """Leitor que guarda o SQL de cada consulta (para ver se raw_articles foi consultada)."""
    sqls: list[str] = []

    def _ler(sql, params=None):
        sqls.append(sql)
        return ler(sql, params)

    return _ler, sqls


def test_ler_urls_resolvidas_formato_do_id_e_ausencias(banco_teste):
    ler = banco_teste(alterar={"raw_articles": _raw(*RAW)})
    urls = fontes.ler_urls_resolvidas(ler=ler)

    assert list(urls.columns) == ["id", "resolved_url"]
    # 1 vira n000001 (6 dígitos); 1234567 vira n1234567; nula e só espaços ficam de fora; wordpress também
    assert dict(zip(urls["id"], urls["resolved_url"])) == {
        "n000001": "https://veiculo.invalid/n1",
        "n1234567": "https://veiculo.invalid/n1234567",
    }
    assert urls["id"].is_unique


def test_ler_urls_resolvidas_sem_origens_so_data_nao_consulta(banco_teste, monkeypatch):
    monkeypatch.setitem(fontes._entrada("noticias"), "origens_so_data", [])
    ler, sqls = _espiao(banco_teste(alterar={"raw_articles": _raw(*RAW)}))
    urls = fontes.ler_urls_resolvidas(ler=ler)

    assert urls.empty and list(urls.columns) == ["id", "resolved_url"]
    assert not any("resolved_url" in s and "IS NOT NULL" in s for s in sqls)


def test_ler_noticias_com_url_resolvida_junta_por_id_sem_multiplicar(banco_teste):
    ler = banco_teste(alterar={"raw_articles": _raw(*RAW), "v1-noticias": _acrescentar(*V1_EXTRAS)})
    sem = fontes.ler_noticias(ler=ler)
    com = fontes.ler_noticias(ler=ler, com_url_resolvida=True)

    assert len(com) == len(sem)  # o merge não multiplica linhas
    assert "resolved_url" in com.columns and "resolved_url" not in sem.columns
    por_id = com.set_index("id")["resolved_url"]
    assert por_id["n000001"] == "https://veiculo.invalid/n1"
    assert por_id["n1234567"] == "https://veiculo.invalid/n1234567"
    assert pd.isna(por_id["n000099"])  # wordpress: sem URL resolvida
    assert por_id.loc["n000002"].isna().all()  # google_news com URL nula na raw (2 tickers)
    assert pd.isna(por_id.loc["n000003"])  # URL só com espaços


def test_ler_noticias_sem_com_url_resolvida_nao_consulta_raw_articles(banco_teste):
    ler, sqls = _espiao(banco_teste(alterar={"raw_articles": _raw(*RAW)}))
    fontes.ler_noticias(ler=ler)
    assert not any("raw_articles" in s for s in sqls)

    ler, sqls = _espiao(banco_teste(alterar={"raw_articles": _raw(*RAW)}))
    fontes.ler_noticias(ler=ler, com_url_resolvida=True)
    assert any("raw_articles" in s for s in sqls)


def test_insumos_pedem_url_resolvida(banco_teste):
    ins = insumos_de_teste(banco_teste())
    assert "resolved_url" in ins.noticias.columns


def test_dataset_pede_url_resolvida(banco_teste, monkeypatch, tmp_path):
    from processamento.experimento import dataset

    chamadas: list[dict] = []
    original = fontes.ler_noticias

    def espiao(*args, **kwargs):
        chamadas.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(fontes, "ler_noticias", espiao)
    dataset.executar("todas", None, None, tmp_path, ler=banco_teste(), existe_composicao=False)

    assert chamadas and all(c.get("com_url_resolvida") is True for c in chamadas)
