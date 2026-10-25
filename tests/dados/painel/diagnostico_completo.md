# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-10-24 21:08 (America/Sao_Paulo)
- Banco: banco_teste
- MySQL: 8.0.46

## Divergências × especificação

Nenhuma divergência encontrada.

## 5. Notícias (v1-noticias)

- 27259 notícias do Google News sem hora, marcadas 'só data' pela coleta (raw_articles.published_precision = 'date'): 2024: 27224, 2025: 35

### Hora da publicação, por ano (artigos distintos)

| ano | total | hora_real | pct_hora_real | so_data_n1a | pct_so_data_n1a | sem_hora | pct_sem_hora |
|---|---|---|---|---|---|---|---|
| 2024 | 33895 | 3010 | 8.9 | 15 | 0 | 30870 | 91.1 |
| 2025 | 32201 | 685 | 2.1 | 29932 | 93 | 1584 | 4.9 |
| 2026 | 117547 | 13144 | 11.2 | 101689 | 86.5 | 2714 | 2.3 |

### Hora da publicação, por ano e origem (artigos distintos)

| ano | origem | total | hora_real | pct_hora_real | so_data_n1a | pct_so_data_n1a | sem_hora | pct_sem_hora |
|---|---|---|---|---|---|---|---|---|
| 2026 | google_news | 114833 | 13144 | 11.4 | 101689 | 88.6 | 0 | 0 |

## 10. Quantidade de ações suspeita

- quantidade de ações suspeita (P/VP < 0,05; v1-acoes_emitidas provavelmente em milhares) em 19 empresas em 2026-10-23: valor de mercado, P/L, P/VP e payout = indisponivel (seção 6)

### Empresas com quantidade de ações suspeita

| tickers | cnpj | data_referencia | acoes | pvp |
|---|---|---|---|---|
| AXIA3 | 00001180000126 | 2026-06-30 | 2943220 | 0.0014 |
| ENEV3 | 04423567000121 | 2026-06-30 | 1937030 | 0.0028 |
| ABEV3 | 07526557000100 | 2026-06-30 | 15763665 | 0.003 |
| EMBJ3 | 07689002000189 | 2026-06-30 | 740465 | 0.0033 |

## 11. Retornos diários suspeitos

- 5 retornos diários suspeitos em 3 tickers (fechamento_ajustado contra o último pregão com preço, abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)

### Retornos diários suspeitos

| ticker | data | aj_anterior | aj | retorno_aj | retorno_fech |
|---|---|---|---|---|---|
| AZUL3 | 2026-02-10 | 7.42 | 341.25 | 44.9906 | 44.9906 |
| AZUL3 | 2026-04-09 | 217 | 3.060e+07 | 141012.1244 | 141012.1244 |
| AZUL3 | 2026-04-20 | 3.225e+07 | 30.54 | -1 | -1 |
| PCAR3 | 2021-03-01 | 10.2961 | 21.857 | 1.1228 | 1.1228 |
| UGPA3 | 2021-06-28 | 7.0026 | 15.3592 | 1.1933 | 1.1933 |

## 12. Lacunas nas séries de preços e índices

- nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker)
- 3 lacunas em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)

### Lacunas em v1-indices

| serie | inicio | fim | tamanho | unidade |
|---|---|---|---|---|
| IDIV | 2025-01-02 | 2026-10-19 | 449 | pregões |
| IFIX | 2025-01-02 | 2026-10-19 | 449 | pregões |
| SMLL | 2025-01-02 | 2026-10-19 | 449 | pregões |

## 15. Histórico novo: composição, corrigir_horas e cobertura do experimento

- Composição do Ibovespa: 48 de 136 tickers sem nenhum preço em v1-precos (7 código antigo de empresa do cadastro, 41 fora do cadastro); 28 estiveram no índice em 2024 ou depois.
- Cobertura do experimento (universo com a composição, motivo ok): 117435 linhas em 1698 pregões, de 2019-12-30 a 2026-10-23.
