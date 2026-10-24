# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-10-23 21:31 (America/Sao_Paulo)
- Banco: tcc_scraper
- MySQL: 8.0.46-0ubuntu0.24.04.4
- Comando: `python -m processamento.diagnostico`

> Este relatório só leu o banco (SELECT/SHOW). Nada foi gravado.

## Divergências × especificação

Nenhuma divergência encontrada.

## 1. Existência das tabelas

- 8 de 8 tabelas do contrato existem.

### Existência

| tabela | grupo | existe |
|---|---|---|
| v1-noticias | contrato | sim |
| v1-precos | contrato | sim |
| v1-cadastro | contrato | sim |
| v1-mudancas_ticker | contrato | sim |
| v1-balancos | contrato | sim |
| v1-acoes_emitidas | contrato | sim |
| v1-proventos | contrato | sim |
| v1-indices | contrato | sim |
| raw_articles | auxiliar | sim |
| staging_article_sentiment | auxiliar | sim |
| v1-painel_execucoes | auxiliar | sim |
| v1-painel_etapas | auxiliar | sim |
| v1-composicao_ibov | auxiliar | sim |
| v1-raw_b3_cadastro | auxiliar | sim |

## 2. Colunas e chaves

### v1-noticias

| coluna | tipo | nulo |
|---|---|---|
| id | varchar | NO |
| ticker | varchar | NO |
| data_hora_publicacao | varchar | YES |
| data_hora_coleta | varchar | NO |
| titulo | text | NO |
| fonte | varchar | YES |
| link | text | YES |
| prob_positivo | double | YES |
| prob_neutro | double | YES |
| prob_negativo | double | YES |
| data_publicacao | date | NO |
| momento_pregao | varchar | NO |
| origem | varchar | NO |
| papel | varchar | YES |
| tipo_conteudo | varchar | YES |
| evento | varchar | YES |
| qualidade | double | YES |

### v1-precos

| coluna | tipo | nulo |
|---|---|---|
| data | date | NO |
| ticker | varchar | NO |
| abertura | double | YES |
| maxima | double | YES |
| minima | double | YES |
| fechamento | double | YES |
| fechamento_ajustado | double | YES |
| volume | bigint | YES |

### v1-cadastro

| coluna | tipo | nulo |
|---|---|---|
| ticker | varchar | NO |
| cnpj | varchar | YES |
| empresa | varchar | NO |
| setor | varchar | YES |
| subsetor | varchar | YES |
| tipo_acao | varchar | NO |
| unit_qtd_on | smallint | YES |
| unit_qtd_pn | smallint | YES |

### v1-mudancas_ticker

| coluna | tipo | nulo |
|---|---|---|
| ticker_antigo | varchar | NO |
| ticker_novo | varchar | NO |
| data_mudanca | date | YES |

### v1-balancos

| coluna | tipo | nulo |
|---|---|---|
| cnpj | varchar | NO |
| tipo_documento | varchar | NO |
| data_inicio_periodo | date | NO |
| data_fim_periodo | date | NO |
| data_entrega | date | YES |
| receita_liquida | double | YES |
| lucro_bruto | double | YES |
| lucro_liquido | double | YES |
| patrimonio_liquido | double | YES |
| ebit | double | YES |
| depreciacao_amortizacao | double | YES |
| emprestimos_curto_prazo | double | YES |
| emprestimos_longo_prazo | double | YES |
| caixa | double | YES |
| aplicacoes_financeiras | double | YES |

### v1-acoes_emitidas

| coluna | tipo | nulo |
|---|---|---|
| cnpj | varchar | NO |
| data_referencia | date | NO |
| qtd_on | bigint | YES |
| qtd_pn | bigint | YES |

### v1-proventos

| coluna | tipo | nulo |
|---|---|---|
| ticker | varchar | NO |
| tipo | varchar | NO |
| data_com | date | NO |
| valor_por_acao | double | NO |
| data_pagamento | date | YES |

### v1-indices

| coluna | tipo | nulo |
|---|---|---|
| data | date | NO |
| indice | varchar | NO |
| valor | double | NO |

### Resumo por tabela

| tabela | n_colunas | faltando | extras | chave_esperada | chave_real | veredito_chave |
|---|---|---|---|---|---|---|
| v1-noticias | 17 | — | — | id, ticker | id, ticker | igual |
| v1-precos | 8 | — | — | data, ticker | data, ticker | igual |
| v1-cadastro | 8 | — | — | ticker | ticker | igual |
| v1-mudancas_ticker | 3 | — | — | ticker_antigo | ticker_antigo | igual |
| v1-balancos | 15 | — | — | cnpj, tipo_documento, data_inicio_periodo, data_fim_periodo | cnpj, tipo_documento, data_inicio_periodo, data_fim_periodo | igual |
| v1-acoes_emitidas | 4 | — | — | cnpj, data_referencia | cnpj, data_referencia | igual |
| v1-proventos | 5 | — | — | ticker, tipo, data_com | ticker, tipo, data_com | igual |
| v1-indices | 3 | — | — | data, indice | data, indice | igual |

## 3. Resumo das tabelas

- 193395 linhas = 149712 artigos; uma linha por par artigo×ticker

### Período e entidades

| tabela | linhas | inicio | fim | entidades | coluna_entidade |
|---|---|---|---|---|---|
| v1-noticias | 193395 | 2025-08-01 | 2026-10-23 | 88 | ticker |
| v1-precos | 48829 | 2024-07-28 | 2026-10-23 | 89 | ticker |
| v1-cadastro | 88 | NULL | NULL | 88 | ticker |
| v1-mudancas_ticker | 10 | NULL | NULL | 10 | ticker_antigo |
| v1-balancos | 740 | 2025-03-31 | 2026-06-30 | 83 | cnpj |
| v1-acoes_emitidas | 510 | 2025-03-31 | 2026-06-30 | 85 | cnpj |
| v1-proventos | 8392 | 1995-12-28 | 2026-09-30 | 148 | ticker |
| v1-indices | 483 | 2025-01-01 | 2026-10-22 | 5 | indice |

### Índices

| indice | n | inicio | fim |
|---|---|---|---|
| CDI | 453 | 2025-01-02 | 2026-10-21 |
| IDIV | 3 | 2026-10-20 | 2026-10-22 |
| IFIX | 3 | 2026-10-20 | 2026-10-22 |
| IPCA | 21 | 2025-01-01 | 2026-09-01 |
| SMLL | 3 | 2026-10-20 | 2026-10-22 |

## 4. Duplicatas

### Chave primária

| tabela | chave | grupos | linhas_extras |
|---|---|---|---|
| v1-noticias | id, ticker | 0 | 0 |
| v1-precos | data, ticker | 0 | 0 |
| v1-cadastro | ticker | 0 | 0 |
| v1-mudancas_ticker | ticker_antigo | 0 | 0 |
| v1-balancos | cnpj, tipo_documento, data_inicio_periodo, data_fim_periodo | 0 | 0 |
| v1-acoes_emitidas | cnpj, data_referencia | 0 | 0 |
| v1-proventos | ticker, tipo, data_com | 0 | 0 |
| v1-indices | data, indice | 0 | 0 |

### Repetições de notícias (informativo)

| verificação | grupos | linhas_extras |
|---|---|---|
| mesma matéria (ticker, data, título) | 4898 | 5525 |
| mesmo link (ticker, link) | 239 | 239 |

## 5. Notícias (v1-noticias)

- formato classificado por grupo (tamanho + últimos 6 caracteres) usando os exemplos mínimo e máximo

### Probabilidades do FinBERT

| veredito | linhas |
|---|---|
| ok | 193395 |
| sem_prob | 0 |
| parcial | 0 |
| fora_intervalo | 0 |
| soma_errada | 0 |

### Faixa de prob_positivo

| minimo | maximo |
|---|---|
| 0.0061 | 0.9602 |

### Faixa de prob_neutro

| minimo | maximo |
|---|---|
| 0.0091 | 0.9563 |

### Faixa de prob_negativo

| minimo | maximo |
|---|---|
| 0.0057 | 0.9781 |

### Percentual com hora, por ano

| ano | pct_com_hora |
|---|---|
| 2025 | 96 |
| 2026 | 98.1 |

### Percentual com hora, por ano e origem

| ano | origem | total | com_hora |
|---|---|---|---|
| 2025 | cvm_ipe | 1603 | 0 |
| 2025 | google_news | 38714 | 38714 |
| 2026 | cvm_ipe | 2852 | 0 |
| 2026 | google_news | 150226 | 150226 |

### Formatos de data/hora

| coluna | tam | fim | n | exemplo_min | exemplo_max | classe |
|---|---|---|---|---|---|---|
| data_hora_publicacao | 25 | -03:00 | 188940 | 2025-08-01T04:00:00-03:00 | 2026-10-23T08:04:19-03:00 | iso_com_fuso |
| data_hora_coleta | 25 | -03:00 | 193395 | 2026-09-07T17:38:43-03:00 | 2026-10-23T08:07:52-03:00 | iso_com_fuso |

### Fuso: data_hora_publicacao × raw_articles.published_at

| ano | amostra | batem | nao_batem |
|---|---|---|---|
| 2025 | 300 | 300 | 0 |
| 2026 | 300 | 300 | 0 |

### Idioma (raw_articles.lang)

| ano | lang | pares | artigos |
|---|---|---|---|
| 2025 | en | 4861 | 4159 |
| 2025 | pt | 35456 | 28006 |
| 2026 | en | 17420 | 14341 |
| 2026 | pt | 135658 | 103206 |

### Modelo do FinBERT por idioma

| lang | model | text_source | n |
|---|---|---|---|
| pt | lucas-leme/FinBERT-PT-BR | title | 150407 |
| en | ProsusAI/finbert | title | 22269 |
| pt | lucas-leme/FinBERT-PT-BR | body | 20707 |
| en | ProsusAI/finbert | body | 12 |

### Formato do id

| ini | tam | n | exemplo_min | exemplo_max |
|---|---|---|---|---|
| n | 7 | 193395 | n005084 | n308623 |

## 6. Valores distintos

### Valores por coluna

| tabela | coluna | valor | n | permitido |
|---|---|---|---|---|
| v1-noticias | origem | google_news | 188940 | sim |
| v1-noticias | origem | cvm_ipe | 4455 | sim |
| v1-noticias | papel | NULL | 176983 | — |
| v1-noticias | papel | protagonista | 7574 | sim |
| v1-noticias | papel | mencao | 3944 | sim |
| v1-noticias | papel | errada | 3291 | sim |
| v1-noticias | papel | citada_com_fato | 1572 | sim |
| v1-noticias | papel | matriz_estrangeira | 31 | sim |
| v1-noticias | tipo_conteudo | NULL | 176983 | — |
| v1-noticias | tipo_conteudo | reportagem | 9834 | sim |
| v1-noticias | tipo_conteudo | outro | 3076 | sim |
| v1-noticias | tipo_conteudo | resumo_mercado | 2378 | sim |
| v1-noticias | tipo_conteudo | lista | 524 | sim |
| v1-noticias | tipo_conteudo | opiniao | 382 | sim |
| v1-noticias | tipo_conteudo | agenda | 186 | sim |
| v1-noticias | tipo_conteudo | podcast_video | 28 | sim |
| v1-noticias | tipo_conteudo | patrocinado | 4 | sim |
| v1-noticias | evento | NULL | 176983 | — |
| v1-noticias | evento | outro | 6393 | sim |
| v1-noticias | evento | operacional | 3646 | sim |
| v1-noticias | evento | macro | 2054 | sim |
| v1-noticias | evento | recomendacao | 1008 | sim |
| v1-noticias | evento | resultado | 842 | sim |
| v1-noticias | evento | governanca | 596 | sim |
| v1-noticias | evento | juridico | 512 | sim |
| v1-noticias | evento | fato_relevante | 413 | sim |
| v1-noticias | evento | fusao_aquisicao | 404 | sim |
| v1-noticias | evento | regulatorio | 294 | sim |
| v1-noticias | evento | dividendo_jcp | 202 | sim |
| v1-noticias | evento | guidance | 45 | sim |
| v1-noticias | evento | mudanca_ticker | 3 | sim |
| v1-cadastro | tipo_acao | ON | 67 | sim |
| v1-cadastro | tipo_acao | PN | 14 | sim |
| v1-cadastro | tipo_acao | UNIT | 6 | sim |
| v1-cadastro | tipo_acao | BDR | 1 | sim |
| v1-balancos | tipo_documento | ITR | 655 | sim |
| v1-balancos | tipo_documento | DFP | 85 | sim |
| v1-proventos | tipo | JCP | 4592 | sim |
| v1-proventos | tipo | DIVIDENDO | 3800 | sim |
| v1-indices | indice | CDI | 453 | sim |
| v1-indices | indice | IPCA | 21 | sim |
| v1-indices | indice | IDIV | 3 | sim |
| v1-indices | indice | IFIX | 3 | sim |
| v1-indices | indice | SMLL | 3 | sim |

## 7. Preços (v1-precos)

- 25 dias úteis sem pregão no IBOV (inclui feriados)
- AZUL3: 1 pregões faltando (pode ser suspensão)
- IVVB11: 1 pregões faltando (pode ser suspensão)

### Pregões por ano (IBOV)

| ano | pregoes |
|---|---|
| 2024 | 107 |
| 2025 | 250 |
| 2026 | 202 |

### Dias úteis sem pregão (informativo, inclui feriados)

| data |
|---|
| 2024-11-15 |
| 2024-11-20 |
| 2024-12-24 |
| 2024-12-25 |
| 2024-12-31 |
| 2025-01-01 |
| 2025-03-03 |
| 2025-03-04 |
| 2025-04-18 |
| 2025-04-21 |
| 2025-05-01 |
| 2025-06-19 |
| 2025-11-20 |
| 2025-12-24 |
| 2025-12-25 |
| 2025-12-31 |
| 2026-01-01 |
| 2026-02-16 |
| 2026-02-17 |
| 2026-04-03 |
| 2026-04-21 |
| 2026-05-01 |
| 2026-06-04 |
| 2026-09-07 |
| 2026-10-12 |

### Buracos por ticker (só os com problema)

| ticker | primeira | ultima | n_faltando | n_fora_do_pregao | exemplos (5 primeiros) |
|---|---|---|---|---|---|
| AZUL3 | 2026-01-13 | 2026-10-22 | 1 | 0 | 2026-01-30 |
| IVVB11 | 2024-07-29 | 2026-10-22 | 1 | 0 | 2025-10-24 |

### Séries macro

| ticker | linhas | com_volume | inicio | fim |
|---|---|---|---|---|
| BRENT | 565 | 0 | 2024-07-29 | 2026-10-23 |
| IBOV | 559 | 0 | 2024-07-29 | 2026-10-22 |
| IVVB11 | 558 | 558 | 2024-07-29 | 2026-10-22 |
| USDBRL | 581 | 0 | 2024-07-28 | 2026-10-23 |

## 8. Balanços (v1-balancos)

- receita_liquida: 731 de 740 valores são múltiplos de 1000 (informativo)
- patrimonio_liquido: 712 de 721 valores são múltiplos de 1000 (informativo)

### Escala (ordem de grandeza)

| coluna | veredito | valores |
|---|---|---|
| receita_liquida | reais | 729 |
| patrimonio_liquido | reais | 720 |

### 5 maiores receitas (DFP), com nome

| cnpj | empresa | fim | receita |
|---|---|---|---|
| 33000167000101 | Petrobras | 2025-12-31 | 4.975e+11 |
| 49115815000105 | JBS | 2025-12-31 | 4.806e+11 |
| 60872504000123 | Itau Unibanco | 2025-12-31 | 3.871e+11 |
| 00000000000191 | Banco do Brasil | 2025-12-31 | 3.195e+11 |
| 60746948000112 | Bradesco | 2025-12-31 | 2.702e+11 |

### Períodos (tipo × classe de dias)

| tipo_documento | classe | n |
|---|---|---|
| DFP | 12m | 85 |
| ITR | 3m | 410 |
| ITR | 6m | 163 |
| ITR | 9m | 82 |

### Datas de entrega

| total | sem_entrega | entrega_antes_do_fim |
|---|---|---|
| 740 | 0 | 0 |

## 9. Tickers e CNPJs

- 28 classes ligadas à empresa pela raiz (estão no other_codes): BPAC3 → BPAC11, BPAC5 → BPAC11, BRAP3 → BRAP4, BRKM3 → BRKM5, BRKM6 → BRKM5, CMIG3 → CMIG4, CPLE6 → CPLE3, CYRE4 → CYRE3, ENGI3 → ENGI11, ENGI4 → ENGI11, GGBR3 → GGBR4, GOAU3 → GOAU4, IGTI3 → IGTI11, IGTI4 → IGTI11, ISAE3 → ISAE4, ITSA3 → ITSA4, ITUB3 → ITUB4, KLBN3 → KLBN11, KLBN4 → KLBN11, POMO3 → POMO4, RAPT3 → RAPT4, RENT4 → RENT3, SANB3 → SANB11, SANB4 → SANB11, TAEE3 → TAEE11, TAEE4 → TAEE11, USIM3 → USIM5, USIM6 → USIM5
- 34 classes extintas (fora do other_codes): contam no histórico de proventos e no payout, ligadas pela raiz; units (final 11) ficam de fora do payout: AXIA5, AXIA6, BBAS4, COGN11, COGN4, CPLE11, CPLE4, CPLE5, CSAN11, EGIE5, EGIE6, EMBJ4, EMBJ5, EQTL11, EQTL4, LREN4, PCAR4, PCAR5, PCAR6, RADL5, RADL6, RAIL11, RAIL4, SUZB5, SUZB6, UGPA4, USIM4, VALE4, VALE5, VBBR4, VIVT4, WEGE4, YDUQ11, YDUQ4
- período analisado (pregões do IBOV): 2024-07-29 a 2026-10-22
- v1-proventos: 4 tickers do cadastro sem linhas (informativo)
- excluídos por decisão (config/exclusoes.yaml): CRFB3, SRNA3, STBP11, STBP3, STBP4
- sem balanço por decisão (config/exclusoes.yaml): 03847461000192, 06057223000171

### Comparação de conjuntos

| comparacao | so_na_referencia | so_no_outro |
|---|---|---|
| cadastro × precos | CRFB3, SRNA3, STBP3 | BRENT, IBOV, IVVB11, USDBRL |
| cadastro × noticias | — | — |
| cadastro × proventos | AZUL3, CRFB3, JBSS32, SRNA3 | AXIA5, AXIA6, BBAS4, BPAC3, BPAC5, BRAP3, BRKM3, BRKM6, CMIG3, COGN11, COGN4, CPLE11, CPLE4, CPLE5, CPLE6, CSAN11, CYRE4, EGIE5, EGIE6, EMBJ4, EMBJ5, ENGI3, ENGI4, EQTL11, EQTL4, GGBR3, GOAU3, IGTI3, IGTI4, ISAE3, ITSA3, ITUB3, KLBN3, KLBN4, LREN4, PCAR4, PCAR5, PCAR6, POMO3, RADL5, RADL6, RAIL11, RAIL4, RAPT3, RENT4, SANB3, SANB4, STBP11, STBP4, SUZB5, SUZB6, TAEE3, TAEE4, UGPA4, USIM3, USIM4, USIM6, VALE4, VALE5, VBBR4, VIVT4, WEGE4, YDUQ11, YDUQ4 |
| cadastro × mudancas (ticker_novo) | ABEV3, ALOS3, ASAI3, AURE3, AZZA3, B3SA3, BBAS3, BBDC3, BBDC4, BBSE3, BEEF3, BPAC11, BRAP4, BRAV3, BRKM5, CMIG4, CMIN3, COGN3, CPFE3, CRFB3, CSAN3, CSNA3, CVCB3, CYRE3, DIRR3, EGIE3, ENEV3, ENGI11, EQTL3, FLRY3, GGBR4, GMAT3, GOAU4, HAPV3, HYPE3, IGTI11, IRBR3, ISAE4, ITSA4, ITUB4, KLBN11, LREN3, LWSA3, MBRF3, MGLU3, MRVE3, MULT3, PCAR3, PETR3, PETR4, POMO4, PRIO3, PSSA3, RADL3, RAIL3, RAIZ4, RAPT4, RDOR3, RECV3, RENT3, SANB11, SBSP3, SLCE3, SMTO3, SRNA3, STBP3, SUZB3, TAEE11, TIMS3, TOTS3, UGPA3, USIM5, VALE3, VAMO3, VBBR3, VIVA3, VIVT3, WEGE3, YDUQ3 | — |
| cadastro × balancos (cnpj) | 03847461000192, 06057223000171 | — |
| cadastro × acoes_emitidas (cnpj) | — | — |

### Classes extintas: proventos

| ticker | proventos | primeira_data_com | ultima_data_com | no_periodo |
|---|---|---|---|---|
| AXIA6 | 35 | 1996-04-25 | 2025-11-14 | 4 |
| CPLE5 | 55 | 1997-04-25 | 2025-04-24 | 4 |
| AXIA5 | 34 | 1996-04-25 | 2025-11-14 | 3 |
| BBAS4 | 11 | 1997-09-29 | 2002-08-27 | 0 |
| COGN11 | 2 | 2009-04-03 | 2009-06-25 | 0 |
| COGN4 | 2 | 2009-04-03 | 2009-06-25 | 0 |
| CPLE11 | 7 | 2021-04-29 | 2023-09-29 | 0 |
| CPLE4 | 1 | 1996-04-23 | 1996-04-23 | 0 |
| CSAN11 | 3 | 2014-10-15 | 2015-09-11 | 0 |
| EGIE5 | 9 | 2002-04-04 | 2005-05-18 | 0 |
| EGIE6 | 9 | 2002-04-04 | 2005-05-18 | 0 |
| EMBJ4 | 27 | 1999-09-28 | 2005-12-20 | 0 |
| EMBJ5 | 2 | 1998-09-18 | 1999-03-30 | 0 |
| EQTL11 | 2 | 2007-04-05 | 2007-12-28 | 0 |
| EQTL4 | 2 | 2007-04-05 | 2007-12-28 | 0 |
| LREN4 | 6 | 1996-04-29 | 2001-04-27 | 0 |
| PCAR4 | 45 | 1996-04-09 | 2019-06-27 | 0 |
| PCAR5 | 7 | 2009-08-11 | 2011-03-31 | 0 |
| PCAR6 | 1 | 2010-04-29 | 2010-04-29 | 0 |
| RADL5 | 2 | 1997-04-30 | 2006-12-28 | 0 |
| RADL6 | 2 | 1997-04-30 | 2006-12-28 | 0 |
| RAIL11 | 8 | 2005-04-01 | 2010-04-30 | 0 |
| RAIL4 | 9 | 2004-12-30 | 2010-04-30 | 0 |
| SUZB5 | 22 | 2004-09-21 | 2017-04-28 | 0 |
| SUZB6 | 22 | 2004-09-21 | 2017-04-28 | 0 |
| UGPA4 | 24 | 2000-03-09 | 2011-03-02 | 0 |
| USIM4 | 8 | 1996-03-07 | 1998-11-27 | 0 |
| VALE4 | 5 | 1996-04-10 | 1998-04-23 | 0 |
| VALE5 | 52 | 1998-08-05 | 2017-04-20 | 0 |
| VBBR4 | 10 | 1996-03-19 | 2002-12-23 | 0 |
| VIVT4 | 102 | 1998-12-30 | 2020-09-28 | 0 |
| WEGE4 | 15 | 2004-12-17 | 2007-03-15 | 0 |
| YDUQ11 | 1 | 2008-04-25 | 2008-04-25 | 0 |
| YDUQ4 | 1 | 2008-04-25 | 2008-04-25 | 0 |

## 10. Quantidade de ações suspeita

- quantidade de ações suspeita (P/VP < 0,05; v1-acoes_emitidas provavelmente em milhares) em 19 empresas em 2026-10-22: valor de mercado, P/L, P/VP e payout = indisponivel (seção 6)

### Empresas com quantidade de ações suspeita

| tickers | cnpj | data_referencia | acoes | pvp |
|---|---|---|---|---|
| AXIA3 | 00001180000126 | 2026-06-30 | 2943220 | 0.0014 |
| ENEV3 | 04423567000121 | 2026-06-30 | 1937030 | 0.0028 |
| ABEV3 | 07526557000100 | 2026-06-30 | 15763665 | 0.003 |
| EMBJ3 | 07689002000189 | 2026-06-30 | 740465 | 0.0033 |
| TAEE11 | 07859971000130 | 2026-06-30 | 1033497 | 0.0019 |
| MRVE3 | 08343492000120 | 2026-06-30 | 562836 | 0.0009 |
| YDUQ3 | 08807432000110 | 2026-06-30 | 274089 | 0.0013 |
| CMIG4 | 17155730000164 | 2026-06-30 | 2861782 | 0.0011 |
| AURE3 | 28594234000123 | 2026-06-30 | 1050378 | 0.0012 |
| VALE3 | 33592510000154 | 2026-06-30 | 4255763 | 0.0013 |
| VBBR3 | 34274233000102 | 2026-06-30 | 1198563 | 0.0019 |
| PCAR3 | 47508411000156 | 2026-06-30 | 492577 | 0.0036 |
| ITUB4 | 60872504000123 | 2026-06-30 | 11026869 | 0.0023 |
| ITSA4 | 61532644000115 | 2026-06-30 | 11213687 | 0.0017 |
| NATU3 | 71673990000177 | 2026-06-30 | 1374558 | 0.0008 |
| CYRE3 | 73178600000118 | 2026-06-30 | 453446 | 0.0012 |
| RAPT4 | 89086144000116 | 2026-06-30 | 349725 | 0.0006 |
| SANB11 | 90400888000142 | 2026-06-30 | 7498531 | 0.0008 |
| LREN3 | 92754738000162 | 2026-06-30 | 1006845 | 0.0014 |

## 11. Vazios e zeros

- demais colunas 100% preenchidas

### Colunas com nulos, textos vazios ou zeros

| tabela | coluna | total | nulos | pct_nulo | situacao | textos_vazios | zeros |
|---|---|---|---|---|---|---|---|
| v1-noticias | data_hora_publicacao | 193395 | 4455 | 2.3 | parcial | 0 | 0 |
| v1-noticias | papel | 193395 | 176983 | 91.5 | parcial | 0 | 0 |
| v1-noticias | tipo_conteudo | 193395 | 176983 | 91.5 | parcial | 0 | 0 |
| v1-noticias | evento | 193395 | 176983 | 91.5 | parcial | 0 | 0 |
| v1-noticias | qualidade | 193395 | 176983 | 91.5 | parcial | 0 | 2178 |
| v1-precos | volume | 48829 | 1716 | 3.5 | parcial | 0 | 0 |
| v1-cadastro | cnpj | 88 | 1 | 1.1 | parcial | 0 | 0 |
| v1-cadastro | setor | 88 | 1 | 1.1 | parcial | 0 | 0 |
| v1-cadastro | subsetor | 88 | 1 | 1.1 | parcial | 0 | 0 |
| v1-cadastro | unit_qtd_on | 88 | 82 | 93.2 | parcial | 0 | 0 |
| v1-cadastro | unit_qtd_pn | 88 | 82 | 93.2 | parcial | 0 | 0 |
| v1-mudancas_ticker | data_mudanca | 10 | 10 | 100 | vazia | 0 | 0 |
| v1-balancos | receita_liquida | 740 | 0 | 0 | cheia | 0 | 11 |
| v1-balancos | lucro_bruto | 740 | 72 | 9.7 | parcial | 0 | 2 |
| v1-balancos | lucro_liquido | 740 | 37 | 5 | parcial | 0 | 1 |
| v1-balancos | patrimonio_liquido | 740 | 19 | 2.6 | parcial | 0 | 1 |
| v1-balancos | ebit | 740 | 72 | 9.7 | parcial | 0 | 1 |
| v1-balancos | depreciacao_amortizacao | 740 | 74 | 10 | parcial | 0 | 1 |
| v1-balancos | emprestimos_curto_prazo | 740 | 72 | 9.7 | parcial | 0 | 89 |
| v1-balancos | emprestimos_longo_prazo | 740 | 72 | 9.7 | parcial | 0 | 89 |
| v1-balancos | caixa | 740 | 72 | 9.7 | parcial | 0 | 1 |
| v1-balancos | aplicacoes_financeiras | 740 | 72 | 9.7 | parcial | 0 | 134 |
| v1-acoes_emitidas | qtd_pn | 510 | 0 | 0 | cheia | 0 | 361 |
| v1-proventos | data_pagamento | 8392 | 8023 | 95.6 | parcial | 0 | 0 |

## 12. Painel de execuções (v1-painel_execucoes e v1-painel_etapas)

- daily cron fora da agenda (11h/21h UTC): 0h: 1 execuções
- etapas de execuções manuais (fora do daily): build_entrega, corrigir_horas, cvm_itr_dfp
- v1-composicao_ibov: colunas faltando nenhum; extras nenhum
- v1-composicao_ibov existe mas está vazia: universo = composicao_atual em todas as datas (seção 3.5)

### Execuções por tipo e status

| tipo | status | n | primeira | ultima |
|---|---|---|---|---|
| coletar | agendada | 1 | 2026-10-23 16:56:21.200957 | 2026-10-23 16:56:21.200957 |
| coletar | concluida | 1 | 2026-10-22 21:56:25.015448 | 2026-10-22 21:56:25.015448 |
| daily | concluida | 3 | 2026-10-21 21:30:04.283650 | 2026-10-23 11:00:01.489947 |
| daily | parcial | 1 | 2026-10-21 00:46:43.367434 | 2026-10-21 00:46:43.367434 |
| etapa | concluida | 1 | 2026-10-20 14:45:13.211003 | 2026-10-20 14:45:13.211003 |

### Hora de início do daily (UTC)

| origem | hora | n |
|---|---|---|
| cron | 0 | 1 |
| cron | 11 | 2 |
| cron | 21 | 1 |

### Etapas do painel

| etapa_id | ordem | status | n |
|---|---|---|---|
| precos | 1 | concluida | 5 |
| cvm_itr_dfp | 1 | concluida | 1 |
| corrigir_horas | 1 | pendente | 1 |
| macro | 2 | concluida | 4 |
| build_entrega | 2 | concluida | 1 |
| noticias | 3 | concluida | 4 |
| ipe | 4 | concluida | 4 |
| enriquecimento | 5 | concluida | 3 |
| enriquecimento | 5 | falhou | 1 |
| juiza | 6 | concluida | 4 |
| cadastro | 7 | concluida | 4 |
| entrega | 8 | concluida | 4 |
| analise | 9 | concluida | 4 |
