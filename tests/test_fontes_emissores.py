"""Leitura do emissor e da base atual (03/11/2026): v1-emissores_ticker, trocas cobertas pelo emissor,
v1-acoes_emitidas (data_entrega, base atual, situacao), v1-balancos.situacao, v1-eventos_acoes e a
N1-A com hora vazia (Google News). Gabaritos do plano (T4).

Banco de teste em SQLite (fixture `banco_teste`). Sem rede, sem banco real.
"""

from datetime import date

import pandas as pd
import pytest

from fabrica_emissores import emissores_de
from processamento import fontes, tickers


# --- Fixtures de alteração do banco de teste ---------------------------------------------

def _emissor_jbs_coberto(df):
    """A JBSS32 da fixture vira duas linhas: ação ON da JBS S.A. até 08/06/2025 e BDR depois.

    Cobre a troca JBSS3 -> JBSS32 (linha do código novo com `ticker_negociado` = código antigo).
    """
    resto = df[df["ticker"] != "JBSS32"]
    jbs = pd.DataFrame([
        {"ticker": "JBSS32", "ordem": "1", "ticker_negociado": "JBSS3", "cd_cvm": "1005",
         "cnpj": "02916265000160", "empresa": "JBS SA", "vigencia_inicio": None,
         "vigencia_fim": "2025-06-08", "fator_acoes": "0.5"},
        {"ticker": "JBSS32", "ordem": "2", "ticker_negociado": "JBSS32", "cd_cvm": "1005",
         "cnpj": "22222222000122", "empresa": "JBS", "vigencia_inicio": "2025-06-09",
         "vigencia_fim": None, "fator_acoes": "1.0"},
    ])
    return pd.concat([resto, jbs], ignore_index=True)


def _emissor_jbs_sobreposto(df):
    """Acrescenta uma JBSS32 ordem 2 que começa em 01/06/2025, sobreposta à linha identidade da fixture."""
    extra = pd.DataFrame([
        {"ticker": "JBSS32", "ordem": "2", "ticker_negociado": "JBSS32", "cd_cvm": "1005",
         "cnpj": "22222222000122", "empresa": "JBS", "vigencia_inicio": "2025-06-01",
         "vigencia_fim": None, "fator_acoes": "1.0"},
    ])
    return pd.concat([df, extra], ignore_index=True)


def _mudanca_jbs(df):
    extra = pd.DataFrame({"ticker_antigo": ["JBSS3"], "ticker_novo": ["JBSS32"], "data_mudanca": ["2025-06-09"]})
    return pd.concat([df, extra], ignore_index=True)


def _mudancas_jbs_e_natura(df):
    extra = pd.DataFrame({
        "ticker_antigo": ["JBSS3", "NTCO3"],
        "ticker_novo": ["JBSS32", "NATU3"],
        "data_mudanca": ["2025-06-09", "2025-07-02"],
    })
    return pd.concat([df, extra], ignore_index=True)


def _precos_jbss32_com_ibov(df):
    """JBSS32 em 05/06, 06/06 e 09/06/2025 (com IBOV, como em test_corte_bdr)."""
    linhas = []
    for data, fech in [("2025-06-05", "78.00"), ("2025-06-06", "78.06"), ("2025-06-09", "78.20")]:
        linhas.append({"data": data, "ticker": "JBSS32", "abertura": fech, "maxima": fech, "minima": fech,
                       "fechamento": fech, "fechamento_ajustado": fech, "volume": "1000"})
        linhas.append({"data": data, "ticker": "IBOV", "abertura": "100.00", "maxima": "100.00",
                       "minima": "100.00", "fechamento": "100.00", "fechamento_ajustado": "100.00",
                       "volume": None})
    return pd.concat([df, pd.DataFrame(linhas)], ignore_index=True)


def _noticia_jbss3_em_1_jun(df):
    """Notícia nova `nj0` com ticker JBSS3 em 01/06/2025 (antes da mudança para o código novo)."""
    linha = df.iloc[[0]].copy()
    linha["id"] = "nj0"
    linha["ticker"] = "JBSS3"
    linha["data_publicacao"] = "2025-06-01"
    linha["data_hora_publicacao"] = "2025-06-01T12:00:00-03:00"
    return pd.concat([df, linha], ignore_index=True)


COMPOSICAO = pd.DataFrame({
    "ticker": ["JBSS3", "NTCO3", "NATU3"],
    "vigencia_inicio": ["2021-01-01", "2021-01-01", "2025-07-02"],
    "vigencia_fim": ["2025-06-08", "2025-07-01", None],
    "participacao": ["1.0", "1.0", "1.0"],
    "fonte": ["teste", "teste", "teste"],
})


def _pares_composicao(df):
    return [
        (t, i.date(), None if pd.isna(f) else f.date())
        for t, i, f in zip(df["ticker"], df["data_inicio"], df["data_fim"], strict=True)
    ]


# --- 1 a 3: leitura estrita de v1-emissores_ticker -----------------------------------------

def test_1_emissores_da_fixture(banco_teste):
    df = fontes.ler_emissores(banco_teste())
    assert len(df) == 7
    assert df["vigencia_inicio"].isna().all()
    assert df["vigencia_fim"].isna().all()
    assert (df["fator_acoes"] == 1.0).all()


def test_2_sem_a_tabela_do_emissor_e_erro_de_leitura(banco_teste):
    with pytest.raises(fontes.ErroLeitura):
        fontes.ler_emissores(banco_teste(omitir=frozenset({"v1-emissores_ticker"})))


def test_3_vigencias_sobrepostas_sao_erro_de_leitura(banco_teste):
    with pytest.raises(fontes.ErroLeitura, match="sobrepostas"):
        fontes.ler_emissores(banco_teste(alterar={"v1-emissores_ticker": _emissor_jbs_sobreposto}))


# --- 4 e 5: troca coberta pelo emissor une sem corte; sem cobertura mantém o corte -------

def test_4_troca_coberta_pelo_emissor_une_sem_corte(banco_teste):
    ler = banco_teste(alterar={
        "v1-emissores_ticker": _emissor_jbs_coberto,
        "v1-mudancas_ticker": _mudanca_jbs,
        "v1-precos": _precos_jbss32_com_ibov,
        "v1-noticias": _noticia_jbss3_em_1_jun,
    })
    assert fontes.ler_cortes_bdr(ler) == []
    mudancas = fontes.ler_mudancas(ler)
    assert mudancas["JBSS3"] == "JBSS32"
    assert mudancas["ELET3"] == "AXIA3"

    precos = fontes.ler_tabela("precos", ler=ler)
    datas_jbss32 = precos[
        (precos["ticker"] == "JBSS32") & precos["data"].between(pd.Timestamp("2025-06-01"), pd.Timestamp("2025-06-30"))
    ]["data"].dt.strftime("%Y-%m-%d").tolist()
    assert datas_jbss32 == ["2025-06-05", "2025-06-06", "2025-06-09"]
    assert not (precos["ticker"] == "JBSS3").any()

    noticias = fontes.ler_noticias(ler=ler)
    assert noticias.set_index("id")["ticker"]["nj0"] == "JBSS32"


def test_5_sem_cobertura_mantem_o_corte(banco_teste):
    ler = banco_teste(alterar={"v1-mudancas_ticker": _mudanca_jbs})
    assert "JBSS3" not in fontes.ler_mudancas(ler)
    assert fontes.ler_cortes_bdr(ler) == [("JBSS3", "JBSS32", date(2025, 6, 9))]


# --- 6: composição do IBOV com o código negociado ---------------------------------------

def test_6_composicao_coberta_pelo_emissor(banco_teste):
    ler = banco_teste(
        alterar={
            "v1-emissores_ticker": _emissor_jbs_coberto,
            "v1-mudancas_ticker": _mudancas_jbs_e_natura,
        },
        extras={"v1-composicao_ibov": COMPOSICAO},
    )
    out = fontes.ler_composicao(ler=ler, existe=True)
    assert _pares_composicao(out) == [
        ("JBSS32", date(2021, 1, 1), date(2025, 6, 8)),
        ("NATU3", date(2021, 1, 1), date(2025, 7, 1)),
        ("NATU3", date(2025, 7, 2), None),
    ]


def test_6_composicao_com_emissor_passado_mapeia_o_codigo_negociado(banco_teste):
    ler = banco_teste(
        alterar={"v1-mudancas_ticker": _mudancas_jbs_e_natura},
        extras={"v1-composicao_ibov": COMPOSICAO},
    )
    emissores = emissores_de([
        ("JBSS32", 1, "JBSS3", "02916265000160", "JBS SA", None, "2025-06-08", 0.5),
        ("JBSS32", 2, "JBSS32", "49115815000105", "JBS N.V.", "2025-06-09", None, 1.0),
    ])
    out = fontes.ler_composicao(ler=ler, existe=True, emissores=emissores)
    assert ("JBSS32", date(2021, 1, 1), date(2025, 6, 8)) in _pares_composicao(out)


def test_6_composicao_sem_cobertura_e_sem_emissor_continua_jbss3(banco_teste):
    ler = banco_teste(
        alterar={"v1-mudancas_ticker": _mudancas_jbs_e_natura},
        extras={"v1-composicao_ibov": COMPOSICAO},
    )
    out = fontes.ler_composicao(ler=ler, existe=True, emissores=None)
    assert out["ticker"].iloc[0] == "JBSS3"


# --- 7 e 8: v1-acoes_emitidas (data_entrega, base atual, situacao) e v1-balancos.situacao -

def test_7_acoes_emitidas_traz_entrega_e_base_atual(banco_teste):
    df = fontes.ler_tabela("acoes_emitidas", ler=banco_teste())
    assert pd.api.types.is_datetime64_any_dtype(df["data_entrega"])
    linha = df[(df["cnpj"] == "33000167000101") & (df["data_referencia"] == pd.Timestamp("2025-09-30"))]
    assert linha["data_entrega"].iloc[0] == pd.Timestamp("2025-11-10")
    assert linha["qtd_on_base_atual"].iloc[0] == pytest.approx(999.0)
    assert linha["qtd_pn_base_atual"].iloc[0] == pytest.approx(999.0)
    assert linha["situacao"].iloc[0] == "ok"


def test_7_situacao_fora_do_contrato_e_erro_de_leitura(banco_teste):
    def _situacao_xyz(df):
        df = df.copy()
        df.loc[0, "situacao"] = "xyz"
        return df

    with pytest.raises(fontes.ErroLeitura, match="fora do contrato"):
        fontes.ler_tabela("acoes_emitidas", ler=banco_teste(alterar={"v1-acoes_emitidas": _situacao_xyz}))


def test_8_balancos_aceita_ajuste_ifrs17(banco_teste):
    def _ajuste(df):
        df = df.copy()
        df.loc[0, "situacao"] = "ajuste_ifrs17"
        return df

    df = fontes.ler_tabela("balancos", ler=banco_teste(alterar={"v1-balancos": _ajuste}))
    assert "ajuste_ifrs17" in set(df["situacao"])


def test_8_balancos_aceita_individual(banco_teste):
    # 09/11/2026: balanço individual da controladora (sem consolidado na CVM, ou consolidado zerado).
    def _individual(df):
        df = df.copy()
        df.loc[0, "situacao"] = "individual"
        return df

    df = fontes.ler_tabela("balancos", ler=banco_teste(alterar={"v1-balancos": _individual}))
    assert "individual" in set(df["situacao"])


def test_8_balancos_situacao_fora_do_contrato_e_erro_de_leitura(banco_teste):
    def _xyz(df):
        df = df.copy()
        df.loc[0, "situacao"] = "xyz"
        return df

    with pytest.raises(fontes.ErroLeitura, match="fora do contrato"):
        fontes.ler_tabela("balancos", ler=banco_teste(alterar={"v1-balancos": _xyz}))


# --- 9: v1-eventos_acoes (só diagnóstico) -----------------------------------------------

EVENTOS_HAPV3 = pd.DataFrame({
    "ticker": ["HAPV3", "HAPV3"],
    "data_com": ["2020-11-24", "2025-06-05"],
    "tipo": ["DESDOBRAMENTO", "GRUPAMENTO"],
    "fator": ["5.0", "0.066667"],
    "isin": [None, None],
    "isin_emitido": [None, None],
    "cnpj": [None, None],
    "data_aprovacao": [None, None],
})


def test_9_eventos_acoes_le_desdobramento_e_grupamento(banco_teste):
    df = fontes.ler_eventos_acoes(ler=banco_teste(extras={"v1-eventos_acoes": EVENTOS_HAPV3}))
    assert len(df) == 2
    assert df["fator"].tolist() == pytest.approx([5.0, 0.066667])


def test_9_eventos_acoes_tipo_fora_do_contrato_e_erro_de_leitura(banco_teste):
    cisao = EVENTOS_HAPV3.assign(tipo=["CISAO", "GRUPAMENTO"])
    with pytest.raises(fontes.ErroLeitura, match="fora do contrato"):
        fontes.ler_eventos_acoes(ler=banco_teste(extras={"v1-eventos_acoes": cisao}))


# --- 10: linhas de preço fora do calendário conhecidas (mapa) --------------------------

def test_10_fora_do_pregao_conhecidas_no_mapa():
    assert fontes._entrada("precos")["fora_do_pregao_conhecidas"] == {
        "JBSS32": ["2020-11-20"],
        "NATU3": ["2020-11-20"],
    }


# --- 11: N1-A com hora vazia (Google News só com data) ---------------------------------

def test_11_google_news_sem_hora_vira_sem_hora_e_23_59_59():
    hora = pd.Series(
        pd.to_datetime([None, "2026-10-05T04:00:00-03:00"], utc=True)
    ).dt.tz_convert("America/Sao_Paulo")
    df = pd.DataFrame({
        "origem": ["google_news", "google_news"],
        "data_hora_publicacao": hora,
        "data_publicacao": pd.to_datetime(["2026-10-05", "2026-10-05"]),
    })
    out = fontes.aplicar_regra_so_data(df)
    assert out["precisao_hora"].tolist() == ["sem_hora", "meia_noite_pacifico"]
    assert out["data_publicacao"].tolist() == [pd.Timestamp("2026-10-05"), pd.Timestamp("2026-10-05")]
    fim = pd.Timestamp("2026-10-05 23:59:59", tz="America/Sao_Paulo")
    assert out["momento_ref"].tolist() == [fim, fim]


# --- 12: troca coberta pelo emissor, nas funções puras de tickers e fontes -----------------

MUDANCA_JBS = pd.DataFrame({
    "ticker_antigo": ["JBSS3"],
    "ticker_novo": ["JBSS32"],
    "data_mudanca": pd.to_datetime(["2025-06-09"]),
})


def test_12_cortes_nao_cortam_troca_coberta():
    assert tickers.cortes_acao_para_bdr(MUDANCA_JBS, {"JBSS32": "BDR"}, frozenset({("JBSS3", "JBSS32")})) == []


def test_12_mudancas_unem_troca_coberta():
    cobertas = frozenset({("JBSS3", "JBSS32")})
    assert fontes.mudancas_como_dict(MUDANCA_JBS, {"JBSS32": "BDR"}, cobertas) == {"JBSS3": "JBSS32"}


def test_12_sem_cobertura_nao_une_e_corta():
    assert fontes.mudancas_como_dict(MUDANCA_JBS, {"JBSS32": "BDR"}) == {}
    assert tickers.cortes_acao_para_bdr(MUDANCA_JBS, {"JBSS32": "BDR"}) == [("JBSS3", "JBSS32", date(2025, 6, 9))]
