# Medição da deduplicação entre origens

Parâmetros: janela de 1 dia(s), mínimo de 5 palavras no título, deduplicar_titulo=True. Medição só de leitura; nada foi gravado no banco. Gerado por `python -m processamento.diagnostico.dedup_origens`.

## 1. Cópias removidas por regra

| regra | cópias removidas |
|---|---|
| titulo_mesmo_dia | 1340 |
| titulo_janela | 76 |
| url | 33 |

Cópias de título que também casam por URL: 914. Cópias de título que o mínimo de 5 palavras segurou (rodando com mínimo 0): 1.

### Por ano

| ano | titulo_mesmo_dia | titulo_janela | url | total |
|---|---|---|---|---|
| 2021 | 194 | 32 | 0 | 226 |
| 2022 | 95 | 18 | 0 | 113 |
| 2025 | 0 | 0 | 4 | 4 |
| 2026 | 1051 | 26 | 29 | 1106 |

### Pares por origem removida × mantida

| origem removida | origem mantida | pares |
|---|---|---|
| google_news | wordpress | 1356 |
| wordpress | google_news | 93 |

## 2. Pares por URL entre origens (todos, antes de remover)

| medida | pares |
|---|---|
| total | 1293 |
| dentro de ±1 dia | 1263 |
| fora de ±1 dia | 30 |
| sem data (não entram nas faixas) | 0 |
| fora: 2 a 7 dias | 3 |
| fora: 8 a 30 dias | 5 |
| fora: mais de 30 dias | 22 |
| remoções da regra url fora de ±1 dia | 27 |

## 3. Amostra de pares removidos

20 pares, sorteio com semente 20261101, estratificado (até 8 titulo_mesmo_dia, até 6 titulo_janela, até 6 url). Detalhes em `docs/medicao_dedup_origens_amostra.csv`.

| ticker removido | ticker mantido | regra | origem removida | origem mantida | data removida | data mantida |
|---|---|---|---|---|---|---|
| GGBR4 | GGBR4 | titulo_mesmo_dia | google_news | wordpress | 2022-02-17 | 2022-02-17 |
| PETR3 | PETR3 | titulo_mesmo_dia | google_news | wordpress | 2022-05-13 | 2022-05-13 |
| BBAS3 | BBAS3 | titulo_mesmo_dia | google_news | wordpress | 2021-06-04 | 2021-06-04 |
| BBAS3 | BBAS3 | titulo_mesmo_dia | google_news | wordpress | 2026-03-30 | 2026-03-30 |
| YDUQ3 | YDUQ3 | titulo_mesmo_dia | google_news | wordpress | 2026-03-11 | 2026-03-11 |
| SANB11 | SANB11 | titulo_mesmo_dia | google_news | wordpress | 2026-03-11 | 2026-03-11 |
| MGLU3 | MGLU3 | titulo_mesmo_dia | google_news | wordpress | 2026-03-13 | 2026-03-13 |
| B3SA3 | B3SA3 | titulo_mesmo_dia | wordpress | google_news | 2026-10-26 | 2026-10-26 |
| BBDC3 | BBDC3 | titulo_janela | google_news | wordpress | 2022-05-14 | 2022-05-13 |
| EMBJ3 | EMBJ3 | titulo_janela | google_news | wordpress | 2026-03-06 | 2026-03-05 |
| SLCE3 | SLCE3 | titulo_janela | google_news | wordpress | 2021-12-17 | 2021-12-16 |
| MGLU3 | MGLU3 | titulo_janela | google_news | wordpress | 2021-05-23 | 2021-05-24 |
| RENT3 | RENT3 | titulo_janela | google_news | wordpress | 2021-12-24 | 2021-12-25 |
| SLCE3 | SLCE3 | titulo_janela | google_news | wordpress | 2026-03-13 | 2026-03-12 |
| IRBR3 | IRBR3 | url | google_news | wordpress | 2026-06-02 | 2022-10-25 |
| WEGE3 | WEGE3 | url | google_news | wordpress | 2026-06-02 | 2022-10-18 |
| ENEV3 | ENEV3 | url | google_news | wordpress | 2026-06-02 | 2026-03-27 |
| CMIG4 | CMIG4 | url | google_news | wordpress | 2026-03-24 | 2026-03-19 |
| VALE3 | VALE3 | url | google_news | wordpress | 2026-03-24 | 2026-03-24 |
| RAIZ4 | RAIZ4 | url | google_news | wordpress | 2026-06-02 | 2022-12-23 |

## 4. Invariância (versão 'todas', antiga × nova)

Antiga: wordpress ignorada e sem deduplicação entre origens. Nova: configuração do plano. Linhas comparadas (anos 2023, 2024, 2025): 98563 antigas × 98559 novas. **Diferenças: 4.**

| id | ticker | janela_antiga | pregao_ref_antiga | momento_antiga | score_antiga | janela_nova | pregao_ref_nova | momento_nova | score_nova |
|---|---|---|---|---|---|---|---|---|---|
| n013122 | B3SA3 | dia | 2025-11-10 | 2025-11-10 23:59:59-03:00 | 0.4272288978099823 | NULL | NULL | NULL | NULL |
| n014519 | BBAS3 | dia | 2025-11-17 | 2025-11-17 23:59:59-03:00 | 0.8611072469502687 | NULL | NULL | NULL | NULL |
| n067228 | IRBR3 | dia | 2025-11-05 | 2025-11-05 23:59:59-03:00 | 0.05945396423339844 | NULL | NULL | NULL | NULL |
| n070419 | JBSS32 | dia | 2025-11-10 | 2025-11-10 23:59:59-03:00 | 0.8864755462855101 | NULL | NULL | NULL | NULL |

## 5. Tempos (mediana de 3 execuções)

| medida | tempo | linhas |
|---|---|---|
| ler_noticias sem URL resolvida | 10.029 s | 401743 |
| ler_noticias com URL resolvida | 10.870 s | 401743 |
| ler_urls_resolvidas | 0.745 s | 22808 |
| deduplicar com regra entre origens ligada | 8.485 s | 401743 |
| deduplicar com regra entre origens desligada | 2.223 s | 401743 |
