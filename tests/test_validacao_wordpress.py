"""Testes da validação da fonte wordpress (`wordpress_analise` e `wordpress`), sem rede e sem banco real.

Nenhum teste abre o banco da coleta: a fixture autouse proíbe `fontes.criar_engine`. Os dados vêm de
tests/dados (SQLite em memória) mais linhas de wordpress montadas aqui, no formato de texto do banco.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy

from processamento import calendario, fontes
from processamento.diagnostico import wordpress as wp_main
from processamento.diagnostico import wordpress_analise as an

DADOS = Path(__file__).parent / "dados"
ARQUIVOS = {"precos.csv": "v1-precos", "cadastro.csv": "v1-cadastro",
            "mudancas_ticker.csv": "v1-mudancas_ticker", "noticias.csv": "v1-noticias",
            "raw_b3_cadastro.csv": "v1-raw_b3_cadastro", "indices.csv": "v1-indices",
            "balancos.csv": "v1-balancos", "acoes_emitidas.csv": "v1-acoes_emitidas",
            "proventos.csv": "v1-proventos"}
SECOES = ["## 0. Prontidão", "## 1. Volume", "## 2. Fontes e domínios", "## 3. Duplicatas",
          "## 4. Hora, fuso", "## 5. FinBERT", "## 6. Juíza", "## 7. Amostra manual",
          "## 8. Impacto", "## 9. Veredito"]


class _BancoRealProibido(BaseException):
    """BaseException de propósito: o `except Exception` das seções não pode engolir a trava."""


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    def _proibido(*args, **kwargs):
        raise _BancoRealProibido("criar_engine chamado num teste: o banco real não pode ser usado")
    monkeypatch.setattr(fontes, "criar_engine", _proibido)


# ---------------------------------------------------------------- linhas de teste (formato de texto do banco)

def _noticia(id_: str, ticker: str, hora: str | None, dia: str, *, origem: str = "google_news",
             papel: str | None = None, titulo: str | None = None, link: str | None = None,
             pp: str = "0.2", pn: str = "0.3") -> dict:
    """Uma linha de `v1-noticias` como o banco devolve (texto). Sem `hora`, a publicação não tem horário."""
    return {
        "id": id_, "ticker": ticker,
        "data_hora_publicacao": None if hora is None else f"{dia}T{hora}-03:00",
        "data_hora_coleta": "2026-09-07T17:38:43-03:00",
        "titulo": titulo or f"Noticia {id_}", "fonte": "Fonte WP" if origem == "wordpress" else "Fonte exemplo",
        "link": link or f"https://wp-exemplo.invalid/{id_}",
        "prob_positivo": pp, "prob_neutro": "0.5", "prob_negativo": pn,
        "origem": origem, "papel": papel, "tipo_conteudo": None, "evento": None, "qualidade": None,
        "data_publicacao": dia, "momento_pregao": "durante",
    }


def _raw(id_: int, origem: str, published_at: str, resolved_url: str | None = None) -> dict:
    return {
        "id": str(id_), "url": f"https://wp-exemplo.invalid/{id_}", "resolved_url": resolved_url or "",
        "title": "titulo", "source_name": "Fonte WP", "source_domain": "wp-exemplo.invalid",
        "published_at": published_at, "lang": "pt", "collected_at": "2026-09-07 20:38:00",
        "origem": origem, "published_precision": "datetime",
    }


WP_LINHAS = [
    _noticia("n000101", "PETR4", "10:00:00", "2025-10-17", origem="wordpress", papel="errada",
             titulo="Lucro da Petro - Veículo X", link="https://www.wp-exemplo.invalid/101"),
    _noticia("n000102", "PETR4", "19:00:00", "2025-10-20", origem="wordpress", papel="mencao",
             titulo="Outra notícia", link="https://wp-exemplo.invalid/102"),
    _noticia("n000103", "VALE3", "09:30:00", "2024-03-02", origem="wordpress", papel=None,
             titulo="Vale sobe", link="https://wp-exemplo.invalid/103"),
]
GN_LINHAS = [
    _noticia("n000201", "PETR4", "04:00:00", "2025-10-18", titulo="Lucro da petro",
             link="https://news.invalid/201", papel="protagonista"),
]
EXTRAS = WP_LINHAS + GN_LINHAS
RAW_LINHAS = [
    _raw(101, "wordpress", "2025-10-17 13:00:00", "https://wp-exemplo.invalid/101"),
    _raw(102, "wordpress", "2025-10-20 22:00:00", "https://wp-exemplo.invalid/102"),
    _raw(103, "wordpress", "2024-03-02 12:30:00", "https://wp-exemplo.invalid/103"),
    _raw(201, "google_news", "2025-10-18 07:00:00", "https://wp-exemplo.invalid/101"),
]
STG_LINHAS = [
    {"article_id": "101", "model": "finbert", "prob_pos": "0.8", "prob_neu": "0.1", "prob_neg": "0.1",
     "text_source": "title"},
    {"article_id": "102", "model": "finbert", "prob_pos": "0.3", "prob_neu": "0.4", "prob_neg": "0.3",
     "text_source": "title"},
]


@pytest.fixture
def banco():
    """Fábrica: SQLite com tests/dados mais wordpress (v1-noticias, raw_articles e staging)."""
    def _criar(noticias_extra=(), raw=RAW_LINHAS, stg=STG_LINHAS):
        eng = sqlalchemy.create_engine("sqlite://")
        for arq, tabela in ARQUIVOS.items():
            df = pd.read_csv(DADOS / arq, dtype=str)
            if tabela == "v1-noticias" and noticias_extra:
                df = pd.concat([df, pd.DataFrame(list(noticias_extra), columns=df.columns)], ignore_index=True)
            df.to_sql(tabela, eng, index=False)
        pd.DataFrame(list(raw)).to_sql("raw_articles", eng, index=False)
        pd.DataFrame(list(stg)).to_sql("staging_article_sentiment", eng, index=False)
        return _ler_de(eng)
    return _criar


def _ler_de(eng):
    """`ler` falso: responde a contagem de tabela de information_schema como 'não existe' e o resto pelo SQLite."""
    def ler(sql, params=None):
        if "information_schema" in sql:
            return pd.DataFrame({"n": [0]})
        return fontes.executar_leitura(sql, params, engine=eng)
    return ler


def _tabela_wp(*linhas_dict) -> pd.DataFrame:
    """Frame com as colunas que as funções puras usam (instantes já em São Paulo)."""
    linhas = []
    for d in linhas_dict:
        linhas.append({
            "id": d["id"], "ticker": d["ticker"], "titulo": d["titulo"], "link": d["link"],
            "fonte": d.get("fonte", "F"), "papel": d.get("papel"), "evento": d.get("evento"),
            "origem": d.get("origem", "wordpress"),
            "data_publicacao": pd.Timestamp(d["data_publicacao"]),
            "data_hora_publicacao": pd.Timestamp(d["hora"]).tz_convert("America/Sao_Paulo")
            if d.get("hora") else pd.NaT,
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- normalizar_titulo e dominio

@pytest.mark.parametrize("entrada, esperado", [
    ("Petrobras anuncia lucro - Veículo Valor Econômico", "petrobras anuncia lucro"),
    ("Ação: PETR4 sobe 3%!", "acao petr4 sobe 3"),
    ("  Vale   —  preço  ", "vale preco"),
    ("Ação de bancos - Estadão - Notícias", "acao de bancos estadao"),
    ("", None),
    (None, None),
])
def test_normalizar_titulo(entrada, esperado):
    assert an.normalizar_titulo(entrada) == esperado


def test_normalizar_titulo_sufixo_longo_nao_e_removido():
    # depois do último " - " há mais de 40 caracteres: não é sufixo de veículo
    longo = "x" * 45
    assert an.normalizar_titulo(f"Caso importante - {longo}") == f"caso importante {longo}"


def test_dominio_tira_www_e_mantem_subdominio():
    assert an.dominio("https://www.exemplo.com.br/x?q=1") == "exemplo.com.br"
    assert an.dominio("https://noticias.exemplo.com/a") == "noticias.exemplo.com"
    assert an.dominio("exemplo.com/a") == "exemplo.com"


@pytest.mark.parametrize("entrada", ["", "   ", None, "http://"])
def test_dominio_vazio_ou_invalido_e_none(entrada):
    assert an.dominio(entrada) is None


# ---------------------------------------------------------------- duplicatas_google

def _wp_gn(titulo_gn: str = "Lucro da petro", data_gn: str = "2025-10-18", url_gn: str | None = None,
           ticker_gn: str = "PETR4", data_wp: str = "2025-10-17"):
    wp = pd.DataFrame({"id": ["w1"], "ticker": ["PETR4"], "titulo": ["Lucro da Petro - Veículo X"],
                       "link": ["https://www.exemplo.invalid/a"], "data_publicacao": [pd.Timestamp(data_wp)]})
    gn = pd.DataFrame({"id": ["g1"], "ticker": [ticker_gn], "titulo": [titulo_gn],
                       "resolved_url": [url_gn or "https://outro.invalid/z"],
                       "data_publicacao": [pd.Timestamp(data_gn)]})
    return wp, gn


def test_duplicata_por_titulo_com_um_dia_de_diferenca():
    wp, gn = _wp_gn(data_gn="2025-10-18")
    pares = an.duplicatas_google(wp, gn)
    assert len(pares) == 1
    assert bool(pares["por_titulo"].iloc[0]) is True
    assert bool(pares["por_url"].iloc[0]) is False


def test_duplicata_por_titulo_com_dois_dias_nao_casa():
    wp, gn = _wp_gn(data_gn="2025-10-19")
    assert an.duplicatas_google(wp, gn).empty


def test_duplicata_por_titulo_exige_mesmo_ticker():
    wp, gn = _wp_gn(ticker_gn="VALE3")
    assert an.duplicatas_google(wp, gn).empty


def test_duplicata_por_url_ignora_http_barra_final_e_query():
    wp, gn = _wp_gn(titulo_gn="Outro título", data_gn="2025-12-01",
                    url_gn="http://exemplo.invalid/a/?utm=1")
    wp = wp.assign(link=["https://exemplo.invalid/a"])
    pares = an.duplicatas_google(wp, gn)
    assert len(pares) == 1
    assert bool(pares["por_url"].iloc[0]) is True
    assert bool(pares["por_titulo"].iloc[0]) is False


def test_duplicatas_sem_correspondencia_vazio():
    wp, gn = _wp_gn(titulo_gn="Assunto diferente", data_gn="2025-10-18", url_gn="https://outro.invalid/z")
    assert an.duplicatas_google(wp, gn).empty


# ---------------------------------------------------------------- afetados_n1a

def test_afetados_n1a_conta_so_meia_noite_do_pacifico():
    # 04:00 de São Paulo em outubro = 00:00 em Los Angeles (PDT): hora "só data" pela N1-A (só google_news)
    df = _tabela_wp(
        {"id": "a", "ticker": "T", "titulo": "x", "link": "l", "data_publicacao": "2025-10-17",
         "hora": "2025-10-17 04:00:00-03:00", "origem": "google_news"},
        {"id": "b", "ticker": "T", "titulo": "y", "link": "l", "data_publicacao": "2025-10-17",
         "hora": "2025-10-17 10:00:00-03:00"},
        {"id": "c", "ticker": "T", "titulo": "z", "link": "l", "data_publicacao": "2025-10-17", "hora": None},
    )
    assert an.afetados_n1a(df) == 1


def test_afetados_n1a_sem_linhas_so_meia_noite_e_zero():
    df = _tabela_wp({"id": "a", "ticker": "T", "titulo": "x", "link": "l", "data_publicacao": "2025-10-17",
                     "hora": "2025-10-17 10:00:00-03:00"})
    assert an.afetados_n1a(df) == 0


def test_afetados_n1a_wordpress_com_04h_nao_e_so_data():
    # a regra N1-A só vale para as origens de origens_so_data (google_news): wordpress com 04:00 é hora real
    df = _tabela_wp({"id": "a", "ticker": "T", "titulo": "x", "link": "l", "data_publicacao": "2025-10-17",
                     "hora": "2025-10-17 04:00:00-03:00"})
    assert an.afetados_n1a(df) == 0


# ---------------------------------------------------------------- sortear_amostra

def _wp_grande(n: int = 60) -> pd.DataFrame:
    linhas = []
    for i in range(n):
        linhas.append({
            "id": f"n{i:06d}", "ticker": f"T{i % 20}", "titulo": f"t{i}", "link": f"https://l/{i}",
            "fonte": "F", "papel": None if i % 7 == 0 else ("errada" if i % 9 == 0 else "mencao"),
            "evento": "resultado", "data_publicacao": pd.Timestamp("2022-01-01" if i % 2 else "2023-01-01"),
            "data_hora_publicacao": pd.Timestamp("2025-10-17 10:00", tz="America/Sao_Paulo"),
        })
    return pd.DataFrame(linhas)


def test_amostra_tem_30_itens_e_colunas_certas():
    amostra = an.sortear_amostra(_wp_grande(), n=30, semente=42, max_por_ticker=3)
    assert len(amostra) == 30
    assert list(amostra.columns) == ["id", "ticker", "data_hora_publicacao", "titulo", "fonte", "link",
                                     "papel", "evento", "ticker_correto"]
    assert (amostra["ticker_correto"] == "").all()


def test_amostra_reprodutivel_com_mesma_semente():
    a = an.sortear_amostra(_wp_grande(), n=30, semente=42)
    b = an.sortear_amostra(_wp_grande(), n=30, semente=42)
    pd.testing.assert_frame_equal(a, b)


def test_amostra_respeita_maximo_por_ticker():
    amostra = an.sortear_amostra(_wp_grande(), n=30, semente=42, max_por_ticker=3)
    assert amostra["ticker"].value_counts().max() <= 3


def test_amostra_inclui_papeis_raros_quando_existem():
    amostra = an.sortear_amostra(_wp_grande(), n=30, semente=42, max_por_ticker=3)
    papeis = set(amostra["papel"])
    assert "errada" in papeis
    assert "mencao" in papeis
    assert "" in papeis  # papel vazio


def test_ler_amostra_preenchida_conta_veredictos(tmp_path):
    caminho = tmp_path / "amostra.csv"
    pd.DataFrame({"id": ["a", "b", "c", "d", "e"], "ticker_correto": ["S", "N", "?", "", " s "]}).to_csv(
        caminho, index=False, encoding="utf-8")
    assert an.ler_amostra_preenchida(caminho) == (2, 1, 1, 1)


# ---------------------------------------------------------------- avaliar_criterios e recomendar

def _metricas_ok(**mudancas) -> dict:
    base = {
        "fuso_pct": 1.0, "finbert_cobertura": 0.995, "errada_wp": 0.10, "errada_gn": 0.08,
        "anos_faltando": [], "n1a_wp": 0, "amostra_s": 30, "amostra_vazias": 0, "amostra_total": 30,
    }
    base.update(mudancas)
    return base


def _status(criterios: list[dict]) -> dict:
    return {c["chave"]: c["status"] for c in criterios}


def test_criterios_todos_ok_recomenda_liberar():
    criterios = an.avaliar_criterios(_metricas_ok())
    assert set(c["status"] for c in criterios) == {"OK"}
    assert {"criterio", "valor", "limite", "status"} <= set(criterios[0])
    assert an.recomendar(criterios) == "liberar"


def test_criterios_falha_de_fuso_recomenda_nao_liberar():
    criterios = an.avaliar_criterios(_metricas_ok(fuso_pct=0.99))
    assert _status(criterios)["fuso"] == "FALHA"
    assert an.recomendar(criterios) == "não liberar"


def test_criterios_falha_de_errada_recomenda_liberar_so_depois_dos_pendentes():
    criterios = an.avaliar_criterios(_metricas_ok(errada_wp=0.20, errada_gn=0.05))
    assert _status(criterios)["errada"] == "FALHA"
    assert an.recomendar(criterios) == "liberar só depois de resolver os pendentes"


def test_criterios_falha_de_n1a_recomenda_liberar_so_depois_dos_pendentes():
    criterios = an.avaliar_criterios(_metricas_ok(n1a_wp=4))
    assert _status(criterios)["n1a"] == "FALHA"
    assert an.recomendar(criterios) == "liberar só depois de resolver os pendentes"


def test_criterios_amostra_sem_preencher_fica_pendente():
    criterios = an.avaliar_criterios(_metricas_ok(amostra_s=5, amostra_vazias=25, amostra_total=30))
    assert _status(criterios)["amostra"] == "PENDENTE"
    assert an.recomendar(criterios) == "liberar só depois de resolver os pendentes"


def test_criterios_amostra_completa_com_poucos_s_falha():
    criterios = an.avaliar_criterios(_metricas_ok(amostra_s=20, amostra_vazias=0, amostra_total=30))
    assert _status(criterios)["amostra"] == "FALHA"
    assert an.recomendar(criterios) == "não liberar"


def test_criterios_ausencia_de_metrica_fica_pendente():
    criterios = an.avaliar_criterios({})
    assert set(c["status"] for c in criterios) == {"PENDENTE"}


def test_criterio_anos_faltando_falha_com_lista_de_anos():
    criterios = an.avaliar_criterios(_metricas_ok(anos_faltando=[2023, 2024]))
    anos = [c for c in criterios if c["chave"] == "anos"][0]
    assert anos["status"] == "FALHA"
    assert "2023" in anos["valor"] and "2024" in anos["valor"]


# ---------------------------------------------------------------- ler_noticias com origens_ignoradas

def test_ler_noticias_com_lista_vazia_inclui_wordpress(banco):
    ler = banco(noticias_extra=EXTRAS)
    com = fontes.ler_noticias(ler=ler, origens_ignoradas=[])
    padrao = fontes.ler_noticias(ler=ler)
    sem = fontes.ler_noticias(ler=ler, origens_ignoradas=["wordpress"])

    # o mapa agora tem origens_ignoradas vazia: o padrão já inclui wordpress
    assert "wordpress" in set(com["origem"])
    assert "wordpress" in set(padrao["origem"])
    assert padrao.attrs["origens_ignoradas"] == {}
    assert "wordpress" not in set(sem["origem"])
    assert sem.attrs["origens_ignoradas"] == {"wordpress": 3}


def test_cenario_sem_continua_diferente_do_com_com_mapa_vazio(banco):
    # com o mapa sem origens ignoradas, 'com' e 'sem' ainda diferem: 'sem' tira a origem wordpress explicitamente
    ler = banco(noticias_extra=EXTRAS)
    bruta = wp_main.carregar(ler).v1_bruta
    com = fontes.tratar_noticias_lidas(bruta, ler=ler, origens_ignoradas=[])
    sem = wp_main._sem_ignoradas(com)

    assert "wordpress" in set(com["origem"])
    assert "wordpress" not in set(sem["origem"])
    assert len(sem) < len(com)


# ---------------------------------------------------------------- main (relatório, código 3 e CSV preservado)

def test_main_gera_relatorio_com_secoes_0_a_9(banco, tmp_path):
    ler = banco(noticias_extra=EXTRAS)
    saida = tmp_path / "relatorio.md"
    amostra = tmp_path / "amostra.csv"

    assert wp_main.main(["--saida", str(saida), "--amostra", str(amostra)], ler=ler) == 0

    texto = saida.read_text(encoding="utf-8")
    assert texto.startswith("# Validação da fonte wordpress em v1-noticias (só leitura)")
    for secao in SECOES:
        assert secao in texto
    assert "Recomendação:" in texto
    assert "Precisa resolver antes de liberar" in texto
    assert "Perguntas para a coleta" in texto
    assert amostra.exists()


def test_main_recusa_sessao_que_nao_e_somente_leitura(tmp_path, monkeypatch):
    saida = tmp_path / "r.md"
    amostra = tmp_path / "a.csv"
    monkeypatch.setattr(fontes, "criar_engine", lambda: object())
    monkeypatch.setattr(fontes, "executar_leitura", lambda sql, params=None, engine=None: pd.DataFrame({"ro": [0]}))

    assert wp_main.main(["--saida", str(saida), "--amostra", str(amostra)]) == 3
    assert not saida.exists()
    assert not amostra.exists()


def test_main_com_configuracao_incompleta_devolve_2(tmp_path, monkeypatch):
    saida = tmp_path / "r.md"

    def criar_engine_sem_config():
        raise fontes.ErroConfiguracao("faltam no .env: SENHA_BANCO")

    monkeypatch.setattr(fontes, "criar_engine", criar_engine_sem_config)

    assert wp_main.main(["--saida", str(saida)]) == 2
    assert not saida.exists()


def test_main_nao_sobrescreve_amostra_preenchida(banco, tmp_path):
    ler = banco(noticias_extra=EXTRAS)
    amostra = tmp_path / "amostra.csv"
    preenchida = "id,ticker,data_hora_publicacao,titulo,fonte,link,papel,evento,ticker_correto\n" \
                 "n000101,PETR4,2025-10-17T10:00:00-03:00,t,f,l,errada,,S\n"
    amostra.write_text(preenchida, encoding="utf-8")

    assert wp_main.main(["--saida", str(tmp_path / "r.md"), "--amostra", str(amostra)], ler=ler) == 0

    assert amostra.read_text(encoding="utf-8") == preenchida
    assert "lida do CSV já existente" in (tmp_path / "r.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- uma leitura só de v1-noticias
def _contar_leituras(ler):
    """Envolve `ler` e conta os SELECT de dados em v1-noticias (o `LIMIT 0` de conferência não lê linhas)."""
    contagem = {"n": 0}

    def contado(sql, params=None):
        if "`v1-noticias`" in sql and "LIMIT 0" not in sql:
            contagem["n"] += 1
        return ler(sql, params)

    return contado, contagem


def test_main_le_v1_noticias_uma_vez_so(banco, tmp_path):
    ler, contagem = _contar_leituras(banco(noticias_extra=EXTRAS))
    saida = tmp_path / "relatorio.md"

    assert wp_main.main(["--saida", str(saida), "--amostra", str(tmp_path / "a.csv")], ler=ler) == 0

    assert contagem["n"] == 1
    texto = saida.read_text(encoding="utf-8")
    assert "Últimos 5 pregões" in texto
    assert "não concluída" not in texto


def test_cenarios_em_memoria_iguais_a_ler_noticias(banco):
    ler = banco(noticias_extra=EXTRAS)
    bruta = wp_main.carregar(ler).v1_bruta

    # o cenário espelha o caminho de produção: ler_noticias(com_url_resolvida=True)
    com = fontes.tratar_noticias_lidas(bruta, ler=ler, origens_ignoradas=[])
    pd.testing.assert_frame_equal(com, fontes.ler_noticias(ler=ler, origens_ignoradas=[], com_url_resolvida=True))
    pd.testing.assert_frame_equal(
        wp_main._sem_ignoradas(com),
        fontes.ler_noticias(ler=ler, origens_ignoradas=["wordpress"], com_url_resolvida=True),
    )

    datas = sorted(pd.to_datetime(bruta["data_publicacao"]).dt.date.unique())
    for d in datas:
        ate = calendario.corte_manha(d)
        recorte = wp_main._ate_corte(bruta, com, ate)
        # mesmo conteúdo; em colunas só com vazios (ex.: papel) o tipo e o vazio (nan × None) podem diferir
        pd.testing.assert_frame_equal(
            _vazios_iguais(recorte),
            _vazios_iguais(fontes.ler_noticias(ate=ate, ler=ler, origens_ignoradas=[], com_url_resolvida=True)),
            check_dtype=False,
        )


def _vazios_iguais(df: pd.DataFrame) -> pd.DataFrame:
    """Troca qualquer vazio por None (em object) para comparar só o conteúdo."""
    return df.astype(object).where(df.notna(), None)
