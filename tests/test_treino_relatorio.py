"""Testes do relatório da Fase 6b (texto; função pura).

O dicionário de métricas é montado à mão, segundo o esquema do metricas.json (contrato 6a/6b/6c).
"""

from processamento.experimento.relatorio import gerar_relatorio, pct


def _topk(vs_acaso="acima"):
    return {
        "n_dias": 120,
        "taxa_acerto": 0.4834,
        "ic_taxa": [0.4512, 0.5141],
        "excesso_medio": 0.0008,
        "ic_excesso": [-0.0011, 0.0027],
        "taxa_ultimos": 0.5,
        "excesso_ultimos": 0.0012,
        "dif_top_ultimos": 0.0166,
        "vs_acaso": vs_acaso,
        "fracao_acaso_maior_ou_igual": 0.9,
    }


def _modelo(vs_acaso="acima"):
    return {
        "colunas": ["ret_t1", "volume_relativo"],
        "auc_geral": 0.5123,
        "auc_medio_pregao": 0.5087,
        "n_dias_auc": 118,
        "topk": {"5": _topk(vs_acaso), "3": _topk(vs_acaso)},
        "abertura": {
            "n_dias_validos": 80,
            "n_dias_total": 120,
            "auc_geral": 0.5,
            "topk": {
                "5": {"n_dias": 80, "taxa_acerto": 0.49, "vs_acaso": vs_acaso},
                "3": {"n_dias": 80, "taxa_acerto": 0.48, "vs_acaso": vs_acaso},
            },
        },
        "por_ano": [
            {"ano": 2025, "n_dias": 60, "taxa_acerto_5": 0.48, "excesso_5": 0.0003, "taxa_acerto_3": 0.47},
            {"ano": 2026, "n_dias": 60, "taxa_acerto_5": 0.49, "excesso_5": 0.0005, "taxa_acerto_3": 0.48},
        ],
        "sensibilidade": {"corte": "2026-01-01", "ultimo_ano": 2026, "anteriores": None},
    }


def _acaso_de(k):
    return {
        "media": 0.5,
        "p2_5": 0.46,
        "p97_5": 0.54,
        "excesso_media": 0.0,
        "excesso_p2_5": -0.002,
        "excesso_p97_5": 0.002,
        "n_sorteios": 200,
        "n_dias": 120,
    }


def _metricas(**trocas) -> dict:
    m = {
        "modo": "desenvolvimento",
        "aviso_funcionamento": True,
        "gerado_em": "2026-10-23T10:00:00",
        "datasets": {
            "todas": {
                "arquivo": "dataset-todas.csv",
                "sha256": "ab12cd34",
                "linhas": 1000,
                "cobertura_inicio": "2025-10-23",
                "info_noticias": {"versao_noticias": "todas", "lidas": 900},
            },
            "principais": {
                "arquivo": "dataset-principais.csv",
                "sha256": "ef56gh78",
                "linhas": 990,
                "cobertura_inicio": "2025-10-23",
                "info_noticias": {"lidas": 500, "fora_versao": 200, "papel_vazio_fora": 40},
            },
            "hora_real_noite": {
                "arquivo": "dataset-hora_real_noite.csv",
                "sha256": "ij90kl12",
                "linhas": 980,
                "cobertura_inicio": "2025-10-23",
                "info_noticias": {
                    "lidas": 500,
                    "fora_versao": 300,
                    "descartadas_fora_da_janela": 20,
                    "preparadas": 30,
                },
            },
        },
        "periodo": {
            "inicio": "2025-10-23",
            "fim": "2026-06-22",
            "n_pregoes": 160,
            "n_linhas": 1500,
            "n_tickers": 40,
            "universo": "ibov",
            "teste_final_inicio": "2026-06-23",
            "teste_final_fim": None,
            "teste_final_usado": False,
            "embargo_pregoes": 1,
        },
        "dobras": [
            {
                "numero": 1,
                "mes_teste": "2026-01",
                "treino_inicio": "2025-10-23",
                "treino_fim": "2025-12-31",
                "n_pregoes_treino": 50,
                "n_pregoes_teste": 20,
                "n_linhas_treino": 500,
                "n_linhas_teste": 200,
            }
        ],
        "selecao": {
            "blocos_preco": ["retorno_1m"],
            "noticias_contexto": ["tom"],
            "hiperparametros": {"max_depth": 2},
            "tentativas": [
                {"etapa": "blocos", "descricao": "bloco de preço A", "auc_medio": 0.51, "aceito": True}
            ],
        },
        "acaso": {"5": _acaso_de("5"), "3": _acaso_de("3"), "abertura": {"5": _acaso_de("5"), "3": _acaso_de("3")}},
        "modelos": {
            "modelo_1": _modelo(),
            "modelo_3": _modelo("dentro"),
            "logistica": _modelo(),
            "volatilidade": _modelo(),
            "modelo_3_principais": None,
            "modelo_3_hora_real_noite": None,
        },
        "comparacoes": [
            {
                "a": "modelo_3",
                "b": "modelo_1",
                "metrica": "acerto_top5_dia",
                "media_dif": 0.01,
                "ic": [-0.02, 0.04],
                "n_dias": 120,
            }
        ],
        "veredito_modelo_3": {
            "acaso": "dentro",
            "supera_volatilidade": False,
            "supera_logistica": False,
            "texto": "modelo 3 ainda não mostrou vantagem sobre o acaso no top 5.",
        },
        "modelo_3b": {
            "n_linhas": 800,
            "n_dias": 90,
            "auc_modelo_3": 0.52,
            "auc_modelo_1": 0.5,
            "auc_modelo_3_fora": 0.5,
            "auc_modelo_1_fora": 0.49,
        },
        "calibracao": {
            "ece": 0.03,
            "brier": 0.24,
            "n": 1000,
            "aprovada": False,
            "chance_exibida": False,
            "tabela": [{"faixa": "0-10%", "previsto": 0.05, "observado": 0.07, "n": 100}],
        },
        "exemplo_top": {
            "data": "2026-06-22",
            "top": [{"ticker": "AAAA3", "score": 0.61, "motivos": ["volume"]}],
            "sombra_modelo_1": ["BBBB3"],
            "sombra_volatilidade": ["CCCC3"],
        },
        "modelo_salvo": {
            "arquivo": "modelos/xgb-2026-06.json",
            "metadados": {"provisorio": True},
            "arquivo_m1": "modelos/xgb-m1-2026-06.json",
            "metadados_m1": {"provisorio": True},
        },
    }
    m.update(trocas)
    return m


def test_primeira_linha_nao_vazia_e_o_aviso_de_funcionamento():
    primeira = next(linha for linha in gerar_relatorio(_metricas()).splitlines() if linha.strip())
    assert "TESTE DE FUNCIONAMENTO" in primeira


def test_aviso_traz_inicio_do_teste_final_e_a_linha_da_trava():
    texto = gerar_relatorio(_metricas())
    assert "2026-06-23" in texto
    assert (
        "> O teste final vai até a véspera da entrada em produção "
        "(`treino.teste_final.fim`, hoje vazio = trava ativa); depois dele vem o teste ao vivo."
    ) in texto


def test_teste_final_com_fim_preenchido_mostra_a_data():
    m = _metricas()
    m["periodo"]["teste_final_fim"] = "2026-12-31"
    texto = gerar_relatorio(m)
    assert "2026-12-31" in texto
    assert "hoje vazio" not in texto


def test_texto_contem_data_e_rodape():
    texto = gerar_relatorio(_metricas())
    assert "2026-06-23" in texto
    assert "Não constitui recomendação de investimento." in texto


def test_recomendacao_aparece_uma_vez_so():
    texto = gerar_relatorio(_metricas())
    assert texto.lower().count("recomendação") == 1


def test_sem_linguagem_proibida():
    texto = gerar_relatorio(_metricas()).lower()
    for proibido in ("compre", "oportunidade", "melhores ações"):
        assert proibido not in texto


def test_com_vs_acaso_dentro_aparece_a_frase_do_acaso():
    texto = gerar_relatorio(_metricas())
    assert "ainda não mostrou vantagem sobre o acaso" in texto


def test_contagem_principais_usa_o_rotulo_do_papel_vazio_sobre_as_lidas():
    texto = gerar_relatorio(_metricas())
    assert "notícias sem julgamento da juíza, fora da versão: 40 (8,0% das lidas)" in texto


def test_sem_aviso_quando_aviso_funcionamento_falso():
    texto = gerar_relatorio(_metricas(aviso_funcionamento=False))
    assert "TESTE DE FUNCIONAMENTO" not in texto
    assert texto.splitlines()[0] == "# AVALIAÇÃO DE DESENVOLVIMENTO"


def test_modo_teste_final_muda_o_titulo_e_nao_diz_trava_fechada_quando_usado():
    m = _metricas(modo="teste_final")
    m["periodo"]["teste_final_usado"] = True
    m["periodo"]["teste_final_fim"] = "2026-12-31"
    texto = gerar_relatorio(m)
    assert "AVALIAÇÃO NO TESTE FINAL (uso único)" in texto
    assert "NÃO usado nem lido" not in texto


def test_modelos_extras_e_datasets_ausentes_viram_nao_encontrado_sem_quebrar():
    m = _metricas()
    m["datasets"]["principais"] = None
    m["datasets"]["hora_real_noite"] = None
    m["modelos"]["modelo_3_hora_real_noite"] = None
    texto = gerar_relatorio(m)
    assert "não encontrado" in texto


def test_campos_none_viram_nd_e_listas_vazias_nao_quebram():
    m = _metricas(dobras=[], comparacoes=[], calibracao=None, veredito_modelo_3=None, modelo_salvo=None)
    m["modelos"]["modelo_3"]["topk"]["5"]["taxa_acerto"] = None
    m["modelos"]["modelo_3"]["por_ano"] = []
    texto = gerar_relatorio(m)
    assert "n/d" in texto
    assert "Nenhuma dobra" in texto
    assert "Nenhuma comparação" in texto


def test_pct():
    assert pct(0.4834) == "48,3%"
    assert pct(None) == "n/d"
    assert pct(0.0008, 2) == "0,08%"
    assert pct(-0.0028, 2) == "-0,28%"
