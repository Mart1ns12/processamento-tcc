# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-11-03 13:09 (America/Sao_Paulo)
- Banco: banco_teste
- MySQL: 8.0.46

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
| v1-acoes_emitidas | contrato | sim |
| v1-eventos_acoes | auxiliar | sim |

## 2. Colunas e chaves

### v1-acoes_emitidas

| coluna | tipo | nulo |
|---|---|---|
| cnpj | varchar | NO |
| data_referencia | date | NO |
| qtd_on_base_atual | bigint | YES |
| qtd_pn_base_atual | bigint | YES |

## 3. Resumo das tabelas

- 409968 linhas = 294941 artigos; uma linha por par artigo×ticker

### Período e entidades

| tabela | linhas | inicio | fim | entidades | coluna_entidade |
|---|---|---|---|---|---|
| v1-noticias | 409968 | 2021-01-01 | 2026-11-03 | 88 | ticker |
| v1-precos | 145707 | 2019-12-30 | 2026-11-03 | 89 | ticker |

### Índices

| indice | n | inicio | fim |
|---|---|---|---|
| CDI | 1464 | 2021-01-04 | 2026-10-30 |
| IDIV | 1704 | 2019-12-30 | 2026-10-30 |
| IFIX | 1704 | 2019-12-30 | 2026-10-30 |
| SMLL | 1704 | 2019-12-30 | 2026-10-30 |

## 5. Notícias (v1-noticias)

- 202252 notícias do Google News sem hora, marcadas 'só data' pela coleta (raw_articles.published_precision = 'date'): 2021: 12330, 2022: 13943, 2023: 21830, 2024: 28521, 2025: 28909, 2026: 96719

### Probabilidades do FinBERT

| veredito | linhas |
|---|---|
| ok | 403408 |
| sem_prob | 6560 |
| parcial | 0 |
| fora_intervalo | 0 |
| soma_errada | 0 |

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
| 2023 | cvm_ipe | 3704 | 0 | 0 | 0 | 0 | 3704 | 100 |
| 2023 | google_news | 24069 | 2239 | 9.3 | 0 | 0 | 21830 | 90.7 |
| 2025 | cvm_ipe | 3687 | 0 | 0 | 0 | 0 | 3687 | 100 |
| 2025 | google_news | 30654 | 685 | 2.2 | 0 | 0 | 29969 | 97.8 |
| 2026 | cvm_ipe | 2844 | 0 | 0 | 0 | 0 | 2844 | 100 |
| 2026 | google_news | 122505 | 20707 | 16.9 | 772 | 0.6 | 101026 | 82.5 |
| 2026 | wordpress | 2053 | 2053 | 100 | 0 | 0 | 0 | 0 |

## 6. Valores distintos

### Valores por coluna

| tabela | coluna | valor | n | permitido |
|---|---|---|---|---|
| v1-noticias | papel | mencao | 117498 | sim |
| v1-noticias | papel | matriz_estrangeira | 345 | sim |
| v1-balancos | situacao | ok | 3180 | sim |
| v1-balancos | situacao | ajuste_ifrs17 | 12 | sim |

## 7. Preços (v1-precos)

- 83 dias úteis sem pregão no IBOV (inclui feriados)
- IVVB11: 1 pregões faltando (pode ser suspensão)
- linha fora do calendário (conhecida, pedida à coleta): JBSS32 2020-11-20, NATU3 2020-11-20

### Buracos por ticker (só os com problema)

| ticker | primeira | ultima | n_faltando | n_fora_do_pregao | exemplos (5 primeiros) |
|---|---|---|---|---|---|
| IVVB11 | 2019-12-30 | 2026-11-03 | 1 | 0 | 2025-10-24 |
| JBSS32 | 2019-12-30 | 2026-11-03 | 0 | 1 | — |
| NATU3 | 2019-12-30 | 2026-11-03 | 0 | 1 | — |

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
| v1-noticias | prob_positivo | 409968 | 6560 | 1.6 | parcial | 0 | 0 |
| v1-noticias | papel | 409968 | 7903 | 1.9 | parcial | 0 | 0 |

## 17. Painel de execuções (v1-painel_execucoes e v1-painel_etapas)

- daily cron fora da agenda (11h/21h UTC): 0h: 1, 3h: 1, 19h: 1 execuções
- daily manual: 1 execuções (23h: 1)

### Etapas do painel

| etapa_id | ordem | status | n |
|---|---|---|---|
| juiza | 1 | concluida | 16 |
| juiza | 1 | falhou | 2 |
| noticias | 3 | concluida | 13 |
| noticias | 3 | falhou | 1 |
| enriquecimento | 5 | falhou | 1 |
| analise | 9 | concluida | 4 |
| analise | 9 | falhou | 3 |
| analise | 9 | pulada | 7 |

## 18. Histórico novo: composição, corrigir_horas e cobertura do experimento

- Composição do Ibovespa: 49 de 136 tickers sem nenhum preço em v1-precos (8 código antigo de empresa do cadastro, 41 fora do cadastro); 29 estiveram no índice em 2024 ou depois. O preço é procurado com a união das mudanças de ticker (o código antigo vale pelo atual).
- corrigir_horas: execução mais recente 2026-10-29-coletar-175705 (status concluida), etapa concluida; iniciada em 2026-10-29 17:57, finalizada em 2026-10-29 18:01 (horário de São Paulo)
- Cobertura do experimento (universo com a composição, motivo ok): 119468 linhas em 1704 pregões, de 2019-12-30 a 2026-11-03.
