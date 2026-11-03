# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-11-03 13:09 (America/Sao_Paulo)
- Banco: tcc_scraper
- MySQL: 8.0.46-0ubuntu0.24.04.4
- Comando: `python -m processamento.diagnostico`

> Este relatório só leu o banco (SELECT/SHOW). Nada foi gravado.

## Divergências × especificação

| # | Tema | Tabela | Detalhe |
|---|---|---|---|
| 1 | noticia_sem_hora | v1-noticias | 2025: 1060 de 30654 sem hora e sem a marca 'só data' em raw_articles |
| 2 | noticia_sem_hora | v1-noticias | 2026: 4307 de 122505 sem hora e sem a marca 'só data' em raw_articles |

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
| v1-raw_ipe_docs | auxiliar | sim |
| v1-emissores_ticker | auxiliar | sim |
| v1-eventos_acoes | auxiliar | sim |

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
| situacao | varchar | NO |

### v1-acoes_emitidas

| coluna | tipo | nulo |
|---|---|---|
| cnpj | varchar | NO |
| data_referencia | date | NO |
| qtd_on | bigint | YES |
| qtd_pn | bigint | YES |
| data_entrega | date | YES |
| qtd_on_base_atual | bigint | YES |
| qtd_pn_base_atual | bigint | YES |
| situacao | varchar | NO |

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
| v1-balancos | 16 | — | — | cnpj, tipo_documento, data_inicio_periodo, data_fim_periodo | cnpj, tipo_documento, data_inicio_periodo, data_fim_periodo | igual |
| v1-acoes_emitidas | 8 | — | — | cnpj, data_referencia | cnpj, data_referencia | igual |
| v1-proventos | 5 | — | — | ticker, tipo, data_com | ticker, tipo, data_com | igual |
| v1-indices | 3 | — | — | data, indice | data, indice | igual |

## 3. Resumo das tabelas

- 409968 linhas = 294941 artigos; uma linha por par artigo×ticker

### Período e entidades

| tabela | linhas | inicio | fim | entidades | coluna_entidade |
|---|---|---|---|---|---|
| v1-noticias | 409968 | 2021-01-01 | 2026-11-03 | 88 | ticker |
| v1-precos | 145707 | 2019-12-30 | 2026-11-03 | 89 | ticker |
| v1-cadastro | 88 | NULL | NULL | 88 | ticker |
| v1-mudancas_ticker | 10 | 2025-05-02 | 2026-06-08 | 10 | ticker_antigo |
| v1-balancos | 3192 | 2020-03-31 | 2026-09-30 | 87 | cnpj |
| v1-acoes_emitidas | 2197 | 2020-03-31 | 2026-09-30 | 87 | cnpj |
| v1-proventos | 8433 | 1995-12-28 | 2026-10-30 | 149 | ticker |
| v1-indices | 6645 | 2019-12-30 | 2026-10-30 | 5 | indice |

### Índices

| indice | n | inicio | fim |
|---|---|---|---|
| CDI | 1464 | 2021-01-04 | 2026-10-30 |
| IDIV | 1704 | 2019-12-30 | 2026-10-30 |
| IFIX | 1704 | 2019-12-30 | 2026-10-30 |
| IPCA | 69 | 2021-01-01 | 2026-09-01 |
| SMLL | 1704 | 2019-12-30 | 2026-10-30 |

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
| mesma matéria (ticker, data, título) | 7686 | 8687 |
| mesmo link (ticker, link) | 1287 | 1288 |

## 5. Notícias (v1-noticias)

- 202252 notícias do Google News sem hora, marcadas 'só data' pela coleta (raw_articles.published_precision = 'date'): 2021: 12330, 2022: 13943, 2023: 21830, 2024: 28521, 2025: 28909, 2026: 96719
- formato classificado por grupo (tamanho + últimos 6 caracteres) usando os exemplos mínimo e máximo

### Probabilidades do FinBERT

| veredito | linhas |
|---|---|
| ok | 403408 |
| sem_prob | 6560 |
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

### Hora da publicação, por ano (artigos distintos)

| ano | total | hora_real | pct_hora_real | so_data_n1a | pct_so_data_n1a | sem_hora | pct_sem_hora |
|---|---|---|---|---|---|---|---|
| 2021 | 33273 | 16583 | 49.8 | 0 | 0 | 16690 | 50.2 |
| 2022 | 36735 | 18825 | 51.2 | 0 | 0 | 17910 | 48.8 |
| 2023 | 27773 | 2239 | 8.1 | 0 | 0 | 25534 | 91.9 |
| 2024 | 35417 | 3194 | 9 | 0 | 0 | 32223 | 91 |
| 2025 | 34341 | 685 | 2 | 0 | 0 | 33656 | 98 |
| 2026 | 127402 | 22760 | 17.9 | 772 | 0.6 | 103870 | 81.5 |

### Hora da publicação, por ano e origem (artigos distintos)

| ano | origem | total | hora_real | pct_hora_real | so_data_n1a | pct_so_data_n1a | sem_hora | pct_sem_hora |
|---|---|---|---|---|---|---|---|---|
| 2021 | cvm_ipe | 4360 | 0 | 0 | 0 | 0 | 4360 | 100 |
| 2021 | google_news | 13787 | 1457 | 10.6 | 0 | 0 | 12330 | 89.4 |
| 2021 | wordpress | 15126 | 15126 | 100 | 0 | 0 | 0 | 0 |
| 2022 | cvm_ipe | 3967 | 0 | 0 | 0 | 0 | 3967 | 100 |
| 2022 | google_news | 15328 | 1385 | 9 | 0 | 0 | 13943 | 91 |
| 2022 | wordpress | 17440 | 17440 | 100 | 0 | 0 | 0 | 0 |
| 2023 | cvm_ipe | 3704 | 0 | 0 | 0 | 0 | 3704 | 100 |
| 2023 | google_news | 24069 | 2239 | 9.3 | 0 | 0 | 21830 | 90.7 |
| 2024 | cvm_ipe | 3702 | 0 | 0 | 0 | 0 | 3702 | 100 |
| 2024 | google_news | 31715 | 3194 | 10.1 | 0 | 0 | 28521 | 89.9 |
| 2025 | cvm_ipe | 3687 | 0 | 0 | 0 | 0 | 3687 | 100 |
| 2025 | google_news | 30654 | 685 | 2.2 | 0 | 0 | 29969 | 97.8 |
| 2026 | cvm_ipe | 2844 | 0 | 0 | 0 | 0 | 2844 | 100 |
| 2026 | google_news | 122505 | 20707 | 16.9 | 772 | 0.6 | 101026 | 82.5 |
| 2026 | wordpress | 2053 | 2053 | 100 | 0 | 0 | 0 | 0 |

### Formatos de data/hora

| coluna | tam | fim | n | exemplo_min | exemplo_max | classe |
|---|---|---|---|---|---|---|
| data_hora_publicacao | 25 | -03:00 | 125618 | 2021-01-01T07:30:57-03:00 | 2026-11-03T08:06:49-03:00 | iso_com_fuso |
| data_hora_coleta | 25 | -03:00 | 409968 | 2026-09-07T17:38:43-03:00 | 2026-11-03T10:55:08-03:00 | iso_com_fuso |

### Fuso: data_hora_publicacao × raw_articles.published_at

| ano | amostra | batem | nao_batem |
|---|---|---|---|
| 2021 | 300 | 300 | 0 |
| 2022 | 300 | 300 | 0 |
| 2023 | 300 | 300 | 0 |
| 2024 | 300 | 300 | 0 |
| 2025 | 300 | 300 | 0 |
| 2026 | 300 | 300 | 0 |

### Idioma (raw_articles.lang)

| ano | lang | pares | artigos |
|---|---|---|---|
| 2021 | pt | 55921 | 33273 |
| 2022 | en | 28 | 28 |
| 2022 | pt | 65523 | 36707 |
| 2023 | en | 3868 | 3428 |
| 2023 | pt | 29303 | 24345 |
| 2024 | en | 5264 | 4644 |
| 2024 | pt | 37526 | 30773 |
| 2025 | en | 4876 | 4166 |
| 2025 | pt | 37943 | 30175 |
| 2026 | en | 18147 | 14926 |
| 2026 | pt | 151569 | 112476 |

### Modelo do FinBERT por idioma

| lang | model | text_source | n |
|---|---|---|---|
| pt | lucas-leme/FinBERT-PT-BR | title | 259398 |
| pt | lucas-leme/FinBERT-PT-BR | body | 111827 |
| en | ProsusAI/finbert | title | 32168 |
| en | ProsusAI/finbert | body | 15 |

### Formato do id

| ini | tam | n | exemplo_min | exemplo_max |
|---|---|---|---|---|
| n | 7 | 409968 | n005084 | n508827 |

## 6. Valores distintos

### Valores por coluna

| tabela | coluna | valor | n | permitido |
|---|---|---|---|---|
| v1-noticias | origem | google_news | 302441 | sim |
| v1-noticias | origem | wordpress | 83722 | sim |
| v1-noticias | origem | cvm_ipe | 23805 | sim |
| v1-noticias | papel | protagonista | 192646 | sim |
| v1-noticias | papel | mencao | 117498 | sim |
| v1-noticias | papel | citada_com_fato | 57862 | sim |
| v1-noticias | papel | errada | 33714 | sim |
| v1-noticias | papel | NULL | 7903 | — |
| v1-noticias | papel | matriz_estrangeira | 345 | sim |
| v1-noticias | tipo_conteudo | reportagem | 295139 | sim |
| v1-noticias | tipo_conteudo | resumo_mercado | 47057 | sim |
| v1-noticias | tipo_conteudo | outro | 18305 | sim |
| v1-noticias | tipo_conteudo | lista | 18083 | sim |
| v1-noticias | tipo_conteudo | opiniao | 10110 | sim |
| v1-noticias | tipo_conteudo | agenda | 8401 | sim |
| v1-noticias | tipo_conteudo | NULL | 7903 | — |
| v1-noticias | tipo_conteudo | patrocinado | 3293 | sim |
| v1-noticias | tipo_conteudo | podcast_video | 1434 | sim |
| v1-noticias | tipo_conteudo | newsletter | 243 | sim |
| v1-noticias | evento | outro | 117889 | sim |
| v1-noticias | evento | operacional | 95413 | sim |
| v1-noticias | evento | macro | 59121 | sim |
| v1-noticias | evento | fato_relevante | 24556 | sim |
| v1-noticias | evento | recomendacao | 18551 | sim |
| v1-noticias | evento | resultado | 18396 | sim |
| v1-noticias | evento | fusao_aquisicao | 17027 | sim |
| v1-noticias | evento | juridico | 16710 | sim |
| v1-noticias | evento | governanca | 13527 | sim |
| v1-noticias | evento | dividendo_jcp | 9625 | sim |
| v1-noticias | evento | regulatorio | 9032 | sim |
| v1-noticias | evento | NULL | 7903 | — |
| v1-noticias | evento | guidance | 1920 | sim |
| v1-noticias | evento | mudanca_ticker | 298 | sim |
| v1-cadastro | tipo_acao | ON | 67 | sim |
| v1-cadastro | tipo_acao | PN | 14 | sim |
| v1-cadastro | tipo_acao | UNIT | 6 | sim |
| v1-cadastro | tipo_acao | BDR | 1 | sim |
| v1-balancos | tipo_documento | ITR | 2696 | sim |
| v1-balancos | tipo_documento | DFP | 496 | sim |
| v1-balancos | situacao | ok | 3180 | sim |
| v1-balancos | situacao | ajuste_ifrs17 | 12 | sim |
| v1-acoes_emitidas | situacao | ok | 1577 | sim |
| v1-acoes_emitidas | situacao | corrigido_escala | 607 | sim |
| v1-acoes_emitidas | situacao | anulado | 11 | sim |
| v1-acoes_emitidas | situacao | corrigido_digito | 2 | sim |
| v1-proventos | tipo | JCP | 4605 | sim |
| v1-proventos | tipo | DIVIDENDO | 3828 | sim |
| v1-indices | indice | IDIV | 1704 | sim |
| v1-indices | indice | IFIX | 1704 | sim |
| v1-indices | indice | SMLL | 1704 | sim |
| v1-indices | indice | CDI | 1464 | sim |
| v1-indices | indice | IPCA | 69 | sim |

## 7. Preços (v1-precos)

- 83 dias úteis sem pregão no IBOV (inclui feriados)
- IVVB11: 1 pregões faltando (pode ser suspensão)
- linha fora do calendário (conhecida, pedida à coleta): JBSS32 2020-11-20, NATU3 2020-11-20

### Pregões por ano (IBOV)

| ano | pregoes |
|---|---|
| 2019 | 1 |
| 2020 | 248 |
| 2021 | 247 |
| 2022 | 250 |
| 2023 | 248 |
| 2024 | 251 |
| 2025 | 250 |
| 2026 | 209 |

### Dias úteis sem pregão (informativo, inclui feriados)

| data |
|---|
| 2019-12-31 |
| 2020-01-01 |
| 2020-02-24 |
| 2020-02-25 |
| 2020-04-10 |
| 2020-04-21 |
| 2020-05-01 |
| 2020-06-11 |
| 2020-09-07 |
| 2020-10-12 |
| 2020-11-02 |
| 2020-11-20 |
| 2020-12-24 |
| 2020-12-25 |
| 2020-12-31 |
| 2021-01-01 |
| 2021-01-25 |
| 2021-02-15 |
| 2021-02-16 |
| 2021-04-02 |
| 2021-04-21 |
| 2021-06-03 |
| 2021-07-09 |
| 2021-09-07 |
| 2021-10-12 |
| 2021-11-02 |
| 2021-11-15 |
| 2021-12-24 |
| 2021-12-31 |
| 2022-02-28 |
| 2022-03-01 |
| 2022-04-15 |
| 2022-04-21 |
| 2022-06-16 |
| 2022-09-07 |
| 2022-10-12 |
| 2022-11-02 |
| 2022-11-15 |
| 2022-12-30 |
| 2023-02-20 |
| 2023-02-21 |
| 2023-04-07 |
| 2023-04-21 |
| 2023-05-01 |
| 2023-06-08 |
| 2023-09-07 |
| 2023-10-12 |
| 2023-11-02 |
| 2023-11-15 |
| 2023-12-25 |
| 2023-12-29 |
| 2024-01-01 |
| 2024-02-12 |
| 2024-02-13 |
| 2024-03-29 |
| 2024-05-01 |
| 2024-05-30 |
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
| 2026-11-02 |

### Buracos por ticker (só os com problema)

| ticker | primeira | ultima | n_faltando | n_fora_do_pregao | exemplos (5 primeiros) |
|---|---|---|---|---|---|
| IVVB11 | 2019-12-30 | 2026-11-03 | 1 | 0 | 2025-10-24 |
| JBSS32 | 2019-12-30 | 2026-11-03 | 0 | 1 | — |
| NATU3 | 2019-12-30 | 2026-11-03 | 0 | 1 | — |

### Séries macro

| ticker | linhas | com_volume | inicio | fim |
|---|---|---|---|---|
| BRENT | 1724 | 0 | 2019-12-30 | 2026-11-03 |
| IBOV | 1704 | 0 | 2019-12-30 | 2026-11-03 |
| IVVB11 | 1703 | 1683 | 2019-12-30 | 2026-11-03 |
| USDBRL | 1995 | 0 | 2019-12-30 | 2026-11-03 |

## 8. Balanços (v1-balancos)

- receita_liquida: 3153 de 3192 valores são múltiplos de 1000 (informativo)
- patrimonio_liquido: 3085 de 3124 valores são múltiplos de 1000 (informativo)
- 3 linhas de balanço com período inválido, descartadas pelo processamento (seção 6): 03342704000130 ITR 2021-03-01→2021-03-31 (31 dias); 16590234000176 ITR 2021-01-01→2021-12-31 (365 dias); 92754738000162 ITR 2021-03-01→2021-03-31 (31 dias)

### Escala (ordem de grandeza)

| coluna | veredito | valores |
|---|---|---|
| receita_liquida | reais | 3120 |
| patrimonio_liquido | reais | 3117 |

### 5 maiores receitas (DFP), com nome

| cnpj | empresa | fim | receita |
|---|---|---|---|
| 33000167000101 | Petrobras | 2022-12-31 | 6.413e+11 |
| 33000167000101 | Petrobras | 2023-12-31 | 5.120e+11 |
| 33000167000101 | Petrobras | 2025-12-31 | 4.975e+11 |
| 33000167000101 | Petrobras | 2024-12-31 | 4.908e+11 |
| 49115815000105 | JBS | 2025-12-31 | 4.806e+11 |

### Períodos (tipo × classe de dias)

| tipo_documento | classe | n |
|---|---|---|
| DFP | 12m | 496 |
| ITR | 12m | 1 |
| ITR | 3m | 1629 |
| ITR | 6m | 565 |
| ITR | 9m | 499 |
| ITR | outro | 2 |

### Datas de entrega

| total | sem_entrega | entrega_antes_do_fim |
|---|---|---|
| 3192 | 0 | 0 |

## 9. Tickers e CNPJs

- 28 classes ligadas à empresa pela raiz (estão no other_codes): BPAC3 → BPAC11, BPAC5 → BPAC11, BRAP3 → BRAP4, BRKM3 → BRKM5, BRKM6 → BRKM5, CMIG3 → CMIG4, CPLE6 → CPLE3, CYRE4 → CYRE3, ENGI3 → ENGI11, ENGI4 → ENGI11, GGBR3 → GGBR4, GOAU3 → GOAU4, IGTI3 → IGTI11, IGTI4 → IGTI11, ISAE3 → ISAE4, ITSA3 → ITSA4, ITUB3 → ITUB4, KLBN3 → KLBN11, KLBN4 → KLBN11, POMO3 → POMO4, RAPT3 → RAPT4, RENT4 → RENT3, SANB3 → SANB11, SANB4 → SANB11, TAEE3 → TAEE11, TAEE4 → TAEE11, USIM3 → USIM5, USIM6 → USIM5
- 34 classes extintas (fora do other_codes): contam no histórico de proventos e no payout, ligadas pela raiz; units (final 11) ficam de fora do payout: AXIA5, AXIA6, BBAS4, COGN11, COGN4, CPLE11, CPLE4, CPLE5, CSAN11, EGIE5, EGIE6, EMBJ4, EMBJ5, EQTL11, EQTL4, LREN4, PCAR4, PCAR5, PCAR6, RADL5, RADL6, RAIL11, RAIL4, SUZB5, SUZB6, UGPA4, USIM4, VALE4, VALE5, VBBR4, VIVT4, WEGE4, YDUQ11, YDUQ4
- período analisado (pregões do IBOV): 2019-12-30 a 2026-11-03
- v1-proventos: 3 tickers do cadastro sem linhas (informativo)
- excluídos por decisão (config/exclusoes.yaml): CRFB3, SRNA3, STBP11, STBP3, STBP4
- exclusão a rever: 06057223000171 tem balanço

### Comparação de conjuntos

| comparacao | so_na_referencia | so_no_outro |
|---|---|---|
| cadastro × precos | CRFB3, SRNA3, STBP3 | BRENT, IBOV, IVVB11, USDBRL |
| cadastro × noticias | — | — |
| cadastro × proventos | AZUL3, CRFB3, SRNA3 | AXIA5, AXIA6, BBAS4, BPAC3, BPAC5, BRAP3, BRKM3, BRKM6, CMIG3, COGN11, COGN4, CPLE11, CPLE4, CPLE5, CPLE6, CSAN11, CYRE4, EGIE5, EGIE6, EMBJ4, EMBJ5, ENGI3, ENGI4, EQTL11, EQTL4, GGBR3, GOAU3, IGTI3, IGTI4, ISAE3, ITSA3, ITUB3, KLBN3, KLBN4, LREN4, PCAR4, PCAR5, PCAR6, POMO3, RADL5, RADL6, RAIL11, RAIL4, RAPT3, RENT4, SANB3, SANB4, STBP11, STBP4, SUZB5, SUZB6, TAEE3, TAEE4, UGPA4, USIM3, USIM4, USIM6, VALE4, VALE5, VBBR4, VIVT4, WEGE4, YDUQ11, YDUQ4 |
| cadastro × mudancas (ticker_novo) | ABEV3, ALOS3, ASAI3, AURE3, AZZA3, B3SA3, BBAS3, BBDC3, BBDC4, BBSE3, BEEF3, BPAC11, BRAP4, BRAV3, BRKM5, CMIG4, CMIN3, COGN3, CPFE3, CRFB3, CSAN3, CSNA3, CVCB3, CYRE3, DIRR3, EGIE3, ENEV3, ENGI11, EQTL3, FLRY3, GGBR4, GMAT3, GOAU4, HAPV3, HYPE3, IGTI11, IRBR3, ISAE4, ITSA4, ITUB4, KLBN11, LREN3, LWSA3, MBRF3, MGLU3, MRVE3, MULT3, PCAR3, PETR3, PETR4, POMO4, PRIO3, PSSA3, RADL3, RAIL3, RAIZ4, RAPT4, RDOR3, RECV3, RENT3, SANB11, SBSP3, SLCE3, SMTO3, SRNA3, STBP3, SUZB3, TAEE11, TIMS3, TOTS3, UGPA3, USIM5, VALE3, VAMO3, VBBR3, VIVA3, VIVT3, WEGE3, YDUQ3 | — |
| cadastro × balancos (cnpj) | — | 02916265000160, 32785497000197 |
| cadastro × acoes_emitidas (cnpj) | — | 02916265000160, 32785497000197 |

### Classes extintas: proventos

| ticker | proventos | primeira_data_com | ultima_data_com | no_periodo |
|---|---|---|---|---|
| CPLE5 | 55 | 1997-04-25 | 2025-04-24 | 17 |
| AXIA6 | 35 | 1996-04-25 | 2025-11-14 | 10 |
| AXIA5 | 34 | 1996-04-25 | 2025-11-14 | 9 |
| CPLE11 | 7 | 2021-04-29 | 2023-09-29 | 7 |
| VIVT4 | 102 | 1998-12-30 | 2020-09-28 | 7 |
| BBAS4 | 11 | 1997-09-29 | 2002-08-27 | 0 |
| COGN11 | 2 | 2009-04-03 | 2009-06-25 | 0 |
| COGN4 | 2 | 2009-04-03 | 2009-06-25 | 0 |
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
| WEGE4 | 15 | 2004-12-17 | 2007-03-15 | 0 |
| YDUQ11 | 1 | 2008-04-25 | 2008-04-25 | 0 |
| YDUQ4 | 1 | 2008-04-25 | 2008-04-25 | 0 |

## 10. Quantidade de ações suspeita

- nenhuma empresa com quantidade de ações suspeita em 2026-11-03

## 11. Emissores por período (v1-emissores_ticker)

- 90 linhas, 87 tickers; 2 com mais de um emissor
- Tickers do cadastro sem emissor em v1-emissores_ticker: CRFB3

### Tickers com mais de um emissor

| ticker | ordem | ticker_negociado | cnpj | empresa | vigencia_inicio | vigencia_fim | fator_acoes |
|---|---|---|---|---|---|---|---|
| JBSS32 | 1 | JBSS3 | 02916265000160 | JBS SA | NULL | 2025-06-08 | 0.5 |
| JBSS32 | 2 | JBSS32 | 49115815000105 | JBS N.V. | 2025-06-09 | NULL | 1 |
| NATU3 | 1 | NATU3 | 71673990000177 | NATURA COSMETICOS SA | NULL | 2019-12-17 | 1 |
| NATU3 | 2 | NTCO3 | 32785497000197 | NATURA & CO HOLDING S.A. | 2019-12-18 | 2025-07-01 | 1 |
| NATU3 | 3 | NATU3 | 71673990000177 | NATURA COSMETICOS SA | 2025-07-02 | NULL | 1 |

## 12. Ações emitidas: base atual e eventos

- 38 linhas incoerentes com os eventos (base_atual ≠ quantidade × fatores posteriores à entrega × fator_acoes, tolerância 1%; fatores arredondados como 0,000007 podem aparecer)

### Linhas incoerentes com os eventos

| cnpj | data_referencia | data_entrega | qtd_total | fator_eventos | fator_acoes | esperado | base_total | razao |
|---|---|---|---|---|---|---|---|---|
| 00000000000191 | 2024-03-31 | 2024-05-08 | 2.865e+09 | 1 | 1 | 2.865e+09 | 5.731e+09 | 2 |
| 02351877000152 | 2020-12-31 | 2021-03-24 | 1.259e+08 | 1 | 1 | 1.259e+08 | 5.036e+08 | 4 |
| 02558157000162 | 2025-03-31 | 2025-05-12 | 1.631e+09 | 1 | 1 | 1.631e+09 | 3.261e+09 | 2 |
| 09305994000129 | 2020-03-31 | 2020-05-14 | 1.259e+09 | 0 | 1 | 111.8822 | 3.297e+08 | 2.947e+06 |
| 09305994000129 | 2020-06-30 | 2020-08-13 | 1.259e+09 | 0 | 1 | 111.8822 | 3.297e+08 | 2.947e+06 |
| 09305994000129 | 2020-09-30 | 2020-11-16 | 1.259e+09 | 0 | 1 | 111.9001 | 3.299e+08 | 2.948e+06 |
| 09305994000129 | 2020-12-31 | 2021-03-04 | 1.261e+09 | 0 | 1 | 112.0548 | 3.316e+08 | 2.960e+06 |
| 09305994000129 | 2021-03-31 | 2021-05-06 | 1.263e+09 | 0 | 1 | 112.2241 | 3.335e+08 | 2.972e+06 |
| 09305994000129 | 2021-06-30 | 2021-08-12 | 1.263e+09 | 0 | 1 | 112.229 | 3.336e+08 | 2.973e+06 |
| 09305994000129 | 2021-09-30 | 2021-11-11 | 1.263e+09 | 0 | 1 | 112.2326 | 3.336e+08 | 2.973e+06 |
| 09305994000129 | 2021-12-31 | 2022-02-24 | 1.263e+09 | 0 | 1 | 112.2357 | 3.337e+08 | 2.973e+06 |
| 09305994000129 | 2022-03-31 | 2022-05-09 | 1.265e+09 | 0 | 1 | 112.4057 | 3.356e+08 | 2.986e+06 |
| 09305994000129 | 2022-06-30 | 2022-08-11 | 1.265e+09 | 0 | 1 | 112.4075 | 3.356e+08 | 2.986e+06 |
| 09305994000129 | 2022-09-30 | 2022-11-10 | 1.265e+09 | 0 | 1 | 112.4079 | 3.356e+08 | 2.986e+06 |
| 09305994000129 | 2022-12-31 | 2023-03-06 | 1.265e+09 | 0 | 1 | 112.4084 | 3.356e+08 | 2.986e+06 |
| 09305994000129 | 2023-03-31 | 2023-05-15 | 1.265e+09 | 0 | 1 | 112.4084 | 3.356e+08 | 2.986e+06 |
| 09305994000129 | 2023-06-30 | 2023-08-10 | 1.265e+09 | 0 | 1 | 112.415 | 3.357e+08 | 2.986e+06 |
| 09305994000129 | 2023-09-30 | 2023-12-08 | 1.265e+09 | 0 | 1 | 112.4195 | 3.357e+08 | 2.987e+06 |
| 09305994000129 | 2023-12-31 | 2024-04-12 | 1.265e+09 | 0 | 1 | 112.4195 | 3.357e+08 | 2.987e+06 |
| 09305994000129 | 2024-03-31 | 2024-05-13 | 1.265e+09 | 0 | 1 | 112.4197 | 3.358e+08 | 2.987e+06 |
| 09305994000129 | 2024-06-30 | 2024-08-12 | 1.265e+09 | 0 | 1 | 112.4197 | 3.358e+08 | 2.987e+06 |
| 09305994000129 | 2024-09-30 | 2024-11-14 | 1.265e+09 | 0 | 1 | 112.4197 | 3.358e+08 | 2.987e+06 |
| 09305994000129 | 2024-12-31 | 2025-02-24 | 1.265e+09 | 0 | 1 | 112.4197 | 3.358e+08 | 2.987e+06 |
| 09305994000129 | 2025-03-31 | 2025-05-14 | 1.361e+09 | 0 | 1 | 120.954 | 4.318e+08 | 3.570e+06 |
| 09305994000129 | 2025-06-30 | 2025-08-14 | 3.025e+09 | 0 | 1 | 268.8907 | 8.960e+08 | 3.332e+06 |
| 09305994000129 | 2025-09-30 | 2025-11-14 | 3.025e+09 | 0 | 1 | 268.8907 | 8.960e+08 | 3.332e+06 |
| 09305994000129 | 2025-12-31 | 2026-03-31 | 3.025e+09 | 0 | 1 | 20166.8 | 8.960e+08 | 44431.4389 |
| 09305994000129 | 2026-03-31 | 2026-05-07 | 5.473e+13 | 1 | 1 | 5.473e+13 | 3.649e+08 | 0 |
| 16614075000100 | 2025-06-30 | 2025-08-11 | 1.735e+08 | 1 | 1 | 1.735e+08 | 5.205e+08 | 3 |
| 30306294000145 | 2020-12-31 | 2024-12-23 | 2.713e+09 | 1 | 1 | 2.713e+09 | 1.085e+10 | 4 |
| 33611500000119 | 2024-03-31 | 2024-07-12 | 1.757e+09 | 1 | 1 | 1.757e+09 | 2.108e+09 | 1.2 |
| 43776517000180 | 2026-03-31 | 2026-05-07 | 7.049e+08 | 1 | 1 | 7.049e+08 | 3.525e+09 | 5 |
| 50746577000115 | 2021-03-31 | 2021-05-14 | 4.667e+08 | 1 | 1 | 4.667e+08 | 1.867e+09 | 4 |
| 53113791000122 | 2020-03-31 | 2022-05-25 | 1.926e+08 | 1 | 1 | 1.926e+08 | 5.779e+08 | 3 |
| 76483817000120 | 2020-03-31 | 2020-05-14 | 2.737e+08 | 10 | 1 | 2.737e+09 | 1.579e+09 | 0.577 |
| 76483817000120 | 2020-06-30 | 2020-08-13 | 2.737e+08 | 10 | 1 | 2.737e+09 | 1.579e+09 | 0.577 |
| 76483817000120 | 2020-09-30 | 2020-11-12 | 2.737e+08 | 10 | 1 | 2.737e+09 | 1.579e+09 | 0.577 |
| 84429695000111 | 2021-03-31 | 2021-04-28 | 2.099e+09 | 1 | 1 | 2.099e+09 | 4.197e+09 | 2 |

## 13. Retornos diários suspeitos

- 3 retornos diários suspeitos em 2 tickers (fechamento_ajustado contra o último pregão com preço, abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)

### Retornos diários suspeitos

| ticker | data | aj_anterior | aj | retorno_aj | retorno_fech |
|---|---|---|---|---|---|
| PCAR3 | 2021-03-01 | 10.2961 | 21.857 | 1.1228 | 1.1228 |
| PCAR3 | 2023-08-23 | 19.65 | 6.56 | -0.6662 | -0.6662 |
| UGPA3 | 2021-06-28 | 7.0026 | 15.3592 | 1.1933 | 1.1933 |

## 14. Lacunas nas séries de preços e índices

- nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker)
- nenhuma lacuna em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)

## 15. Notícias por mês

- 64 meses avaliados (mês abaixo de 25% da mediana dos até 12 meses anteriores; o último mês da coleta fica de fora por estar incompleto)

### Meses com poucas notícias

| mes | artigos | mediana_referencia | situacao |
|---|---|---|---|
| 2025-01 | 288 | 2698.5 | cadastrado |
| 2025-02 | 347 | 2698.5 | cadastrado |
| 2025-03 | 366 | 2698.5 | cadastrado |
| 2025-04 | 321 | 2698.5 | cadastrado |
| 2025-05 | 371 | 2698.5 | cadastrado |
| 2025-06 | 218 | 2698.5 | cadastrado |
| 2025-07 | 255 | 2698.5 | cadastrado |

## 16. Vazios e zeros

- `v1-noticias.titulo`: 3 textos vazios ('') (a leitura trata como vazio); ids (até 10): n326413, n380792, n395868
- `v1-mudancas_ticker.data_mudanca` preenchida em 10 de 10 linhas
- demais colunas 100% preenchidas

### Colunas com nulos, textos vazios ou zeros

| tabela | coluna | total | nulos | pct_nulo | situacao | textos_vazios | zeros |
|---|---|---|---|---|---|---|---|
| v1-noticias | data_hora_publicacao | 409968 | 284350 | 69.4 | parcial | 0 | 0 |
| v1-noticias | titulo | 409968 | 0 | 0 | cheia | 3 | 0 |
| v1-noticias | prob_positivo | 409968 | 6560 | 1.6 | parcial | 0 | 0 |
| v1-noticias | prob_neutro | 409968 | 6560 | 1.6 | parcial | 0 | 0 |
| v1-noticias | prob_negativo | 409968 | 6560 | 1.6 | parcial | 0 | 0 |
| v1-noticias | papel | 409968 | 7903 | 1.9 | parcial | 0 | 0 |
| v1-noticias | tipo_conteudo | 409968 | 7903 | 1.9 | parcial | 0 | 0 |
| v1-noticias | evento | 409968 | 7903 | 1.9 | parcial | 0 | 0 |
| v1-noticias | qualidade | 409968 | 7903 | 1.9 | parcial | 0 | 5923 |
| v1-precos | abertura | 145707 | 483 | 0.3 | parcial | 0 | 0 |
| v1-precos | volume | 145707 | 5502 | 3.8 | parcial | 0 | 0 |
| v1-cadastro | cnpj | 88 | 1 | 1.1 | parcial | 0 | 0 |
| v1-cadastro | setor | 88 | 1 | 1.1 | parcial | 0 | 0 |
| v1-cadastro | subsetor | 88 | 1 | 1.1 | parcial | 0 | 0 |
| v1-cadastro | unit_qtd_on | 88 | 82 | 93.2 | parcial | 0 | 0 |
| v1-cadastro | unit_qtd_pn | 88 | 82 | 93.2 | parcial | 0 | 0 |
| v1-mudancas_ticker | data_mudanca | 10 | 0 | 0 | cheia | 0 | 0 |
| v1-balancos | receita_liquida | 3192 | 0 | 0 | cheia | 0 | 72 |
| v1-balancos | lucro_bruto | 3192 | 286 | 9 | parcial | 0 | 33 |
| v1-balancos | lucro_liquido | 3192 | 146 | 4.6 | parcial | 0 | 9 |
| v1-balancos | patrimonio_liquido | 3192 | 68 | 2.1 | parcial | 0 | 7 |
| v1-balancos | ebit | 3192 | 286 | 9 | parcial | 0 | 9 |
| v1-balancos | depreciacao_amortizacao | 3192 | 334 | 10.5 | parcial | 0 | 7 |
| v1-balancos | emprestimos_curto_prazo | 3192 | 286 | 9 | parcial | 0 | 131 |
| v1-balancos | emprestimos_longo_prazo | 3192 | 286 | 9 | parcial | 0 | 153 |
| v1-balancos | caixa | 3192 | 286 | 9 | parcial | 0 | 7 |
| v1-balancos | aplicacoes_financeiras | 3192 | 286 | 9 | parcial | 0 | 644 |
| v1-acoes_emitidas | qtd_on | 2197 | 11 | 0.5 | parcial | 0 | 0 |
| v1-acoes_emitidas | qtd_pn | 2197 | 11 | 0.5 | parcial | 0 | 1537 |
| v1-acoes_emitidas | qtd_on_base_atual | 2197 | 11 | 0.5 | parcial | 0 | 0 |
| v1-acoes_emitidas | qtd_pn_base_atual | 2197 | 11 | 0.5 | parcial | 0 | 1537 |
| v1-proventos | data_pagamento | 8433 | 8045 | 95.4 | parcial | 0 | 0 |

## 17. Painel de execuções (v1-painel_execucoes e v1-painel_etapas)

- daily cron fora da agenda (11h/21h UTC): 0h: 1, 3h: 1, 19h: 1 execuções
- daily manual: 1 execuções (23h: 1)
- etapas de execuções manuais (fora do daily): b3_indices, build_entrega, corrigir_horas, cvm_itr_dfp
- v1-composicao_ibov: colunas faltando nenhum; extras nenhum
- v1-composicao_ibov: 137 linhas, data_inicio de 2021-01-01 a 2026-09-08, 76 vigentes (data_fim vazia); datas sem vigência usam composicao_atual (seção 3.5)

### Execuções por tipo e status

| tipo | status | n | primeira | ultima |
|---|---|---|---|---|
| coletar | concluida | 7 | 2026-10-22 21:56:25.015448 | 2026-10-31 12:25:36.464428 |
| coletar | parcial | 1 | 2026-10-30 19:17:38.592389 | 2026-10-30 19:17:38.592389 |
| daily | concluida | 9 | 2026-10-21 21:30:04.283650 | 2026-11-03 11:00:01.966590 |
| daily | parcial | 5 | 2026-10-21 00:46:43.367434 | 2026-10-31 11:00:05.262712 |
| etapa | concluida | 1 | 2026-10-20 14:45:13.211003 | 2026-10-20 14:45:13.211003 |

### Hora de início do daily (UTC)

| origem | hora | n |
|---|---|---|
| cron | 0 | 1 |
| cron | 3 | 1 |
| cron | 11 | 9 |
| cron | 19 | 1 |
| cron | 21 | 1 |
| manual | 23 | 1 |

### Etapas do painel

| etapa_id | ordem | status | n |
|---|---|---|---|
| corrigir_horas | 1 | concluida | 2 |
| cvm_itr_dfp | 1 | concluida | 3 |
| precos | 1 | concluida | 15 |
| juiza | 1 | concluida | 16 |
| juiza | 1 | falhou | 2 |
| macro | 2 | concluida | 14 |
| build_entrega | 2 | concluida | 6 |
| noticias | 3 | concluida | 13 |
| b3_indices | 3 | concluida | 1 |
| noticias | 3 | falhou | 1 |
| ipe | 4 | concluida | 13 |
| ipe | 4 | pulada | 1 |
| enriquecimento | 5 | concluida | 12 |
| enriquecimento | 5 | falhou | 1 |
| enriquecimento | 5 | pulada | 1 |
| juiza | 6 | pulada | 1 |
| cadastro | 7 | concluida | 13 |
| cadastro | 7 | pulada | 1 |
| entrega | 8 | concluida | 14 |
| analise | 9 | concluida | 4 |
| analise | 9 | falhou | 3 |
| analise | 9 | pulada | 7 |

## 18. Histórico novo: composição, corrigir_horas e cobertura do experimento

- Composição do Ibovespa: 49 de 136 tickers sem nenhum preço em v1-precos (8 código antigo de empresa do cadastro, 41 fora do cadastro); 29 estiveram no índice em 2024 ou depois. O preço é procurado com a união das mudanças de ticker (o código antigo vale pelo atual).
- corrigir_horas: execução mais recente 2026-10-29-coletar-175705 (status concluida), etapa concluida; iniciada em 2026-10-29 17:57, finalizada em 2026-10-29 18:01 (horário de São Paulo)
- Cobertura do experimento (universo com a composição, motivo ok): 119468 linhas em 1704 pregões, de 2019-12-30 a 2026-11-03.

### Composição do Ibovespa: tickers sem nenhum preço em v1-precos

| ticker | grupo | inicio | fim | no_indice_desde_2024 |
|---|---|---|---|---|
| AXIA6 | empresa_do_cadastro | 2025-11-10 | 2026-06-07 | sim |
| AXIA7 | empresa_do_cadastro | 2026-01-05 | 2026-05-03 | sim |
| CPLE5 | empresa_do_cadastro | 2025-11-10 | 2025-12-21 | sim |
| CRFB3 | empresa_do_cadastro | 2021-01-01 | 2025-06-01 | sim |
| CYRE4 | empresa_do_cadastro | 2026-01-05 | 2026-05-03 | sim |
| JBSS3 | empresa_do_cadastro | 2021-01-01 | 2025-06-08 | sim |
| RENT4 | empresa_do_cadastro | 2026-01-05 | 2026-05-03 | sim |
| STBP3 | empresa_do_cadastro | 2024-09-02 | 2025-10-05 | sim |
| ALPA4 | fora_do_cadastro | 2021-09-01 | 2025-01-05 | sim |
| ALSO3 | fora_do_cadastro | 2023-05-02 | 2024-01-01 | sim |
| AMER3 | fora_do_cadastro | 2021-09-01 | 2023-05-01 | não |
| AMOB3 | fora_do_cadastro | 2024-12-16 | 2025-05-04 | sim |
| ARZZ3 | fora_do_cadastro | 2023-01-02 | 2024-09-01 | sim |
| BHIA3 | fora_do_cadastro | 2024-01-02 | 2024-05-05 | sim |
| BIDI11 | fora_do_cadastro | 2021-05-03 | 2023-01-01 | não |
| BIDI4 | fora_do_cadastro | 2021-09-01 | 2022-01-02 | não |
| BPAN4 | fora_do_cadastro | 2021-09-01 | 2023-05-01 | não |
| BRDT3 | fora_do_cadastro | 2021-01-01 | 2022-01-02 | não |
| BRFS3 | fora_do_cadastro | 2021-01-01 | 2025-09-22 | sim |
| BRML3 | fora_do_cadastro | 2021-01-01 | 2023-05-01 | não |
| BTOW3 | fora_do_cadastro | 2021-01-01 | 2021-08-31 | não |
| CASH3 | fora_do_cadastro | 2021-09-01 | 2023-09-03 | não |
| CEAB3 | fora_do_cadastro | 2025-09-01 | vigente | sim |
| CIEL3 | fora_do_cadastro | 2021-01-01 | 2024-09-01 | sim |
| CSMG3 | fora_do_cadastro | 2026-01-05 | vigente | sim |
| CURY3 | fora_do_cadastro | 2025-09-01 | vigente | sim |
| CXSE3 | fora_do_cadastro | 2024-09-02 | vigente | sim |
| DXCO3 | fora_do_cadastro | 2021-09-01 | 2024-09-01 | sim |
| ECOR3 | fora_do_cadastro | 2021-01-01 | 2023-05-01 | não |
| ENBR3 | fora_do_cadastro | 2021-01-01 | 2023-09-03 | não |
| EZTC3 | fora_do_cadastro | 2021-01-01 | 2025-01-05 | sim |
| GNDI3 | fora_do_cadastro | 2021-01-01 | 2022-05-01 | não |
| GOLL4 | fora_do_cadastro | 2021-01-01 | 2024-05-05 | sim |
| HGTX3 | fora_do_cadastro | 2021-01-01 | 2022-01-02 | não |
| IGTA3 | fora_do_cadastro | 2021-01-01 | 2022-01-02 | não |
| JHSF3 | fora_do_cadastro | 2021-01-01 | 2023-01-01 | não |
| LAME4 | fora_do_cadastro | 2021-01-01 | 2022-05-01 | não |
| LCAM3 | fora_do_cadastro | 2021-01-01 | 2023-01-01 | não |
| MRFG3 | fora_do_cadastro | 2021-01-01 | 2025-09-22 | sim |
| POSI3 | fora_do_cadastro | 2022-01-03 | 2023-01-01 | não |
| QUAL3 | fora_do_cadastro | 2021-01-01 | 2023-05-01 | não |
| RRRP3 | fora_do_cadastro | 2022-01-03 | 2024-09-08 | sim |
| SMFT3 | fora_do_cadastro | 2025-05-05 | vigente | sim |
| SOMA3 | fora_do_cadastro | 2022-01-03 | 2024-09-01 | sim |
| SULA11 | fora_do_cadastro | 2021-01-01 | 2023-01-01 | não |
| TEND3 | fora_do_cadastro | 2026-09-08 | vigente | sim |
| TRPL4 | fora_do_cadastro | 2024-01-02 | 2024-11-17 | sim |
| VIIA3 | fora_do_cadastro | 2021-09-01 | 2024-01-01 | sim |
| VVAR3 | fora_do_cadastro | 2021-01-01 | 2021-08-31 | não |

### Cobertura do experimento por ano (universo com a composição, motivo ok)

| ano | pregoes | linhas_ok | min_por_pregao | mediana_por_pregao | max_por_pregao | universo |
|---|---|---|---|---|---|---|
| 2019 | 1 | 72 | 72 | 72 | 72 | composicao_atual |
| 2020 | 248 | 18174 | 72 | 73 | 76 | composicao_atual |
| 2021 | 247 | 14989 | 59 | 61 | 62 | composicao_historica |
| 2022 | 250 | 16419 | 65 | 66 | 66 | composicao_historica |
| 2023 | 248 | 16941 | 67 | 68 | 70 | composicao_historica |
| 2024 | 251 | 18256 | 71 | 72 | 76 | composicao_historica |
| 2025 | 250 | 19308 | 76 | 77 | 78 | composicao_historica |
| 2026 | 209 | 15309 | 70 | 73 | 77 | composicao_historica |
