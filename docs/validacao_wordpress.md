# Validação da fonte wordpress em v1-noticias (só leitura)
- Gerado em: 2026-11-01 18:42 (America/Sao_Paulo)
- Comando: `python -m processamento.diagnostico.wordpress`
> Este relatório só leu o banco (SELECT). Nada foi gravado no banco; a amostra manual é o único arquivo escrito, e só se ainda não existir.

## 0. Prontidão

Ano mínimo do veredito: 2022. Anos anteriores ficam fora do veredito.

| ano | artigos wordpress em raw_articles | artigos wordpress distintos na v1-noticias | situação |
|---|---|---|---|
| 2021 | 15126 | 15126 | em processamento (fora do veredito) |
| 2022 | 17440 | 17440 | ok |
| 2026 | 2019 | 2019 | ok |

## 1. Volume por ano, ano-mês, origem e ticker

### Por ano (artigos distintos e pares)

| ano | artigos cvm_ipe | artigos google_news | artigos wordpress | pares cvm_ipe | pares google_news | pares wordpress |
|---|---|---|---|---|---|---|
| 2021 | 4237 | 13787 | 15126 | 4599 | 15920 | 35279 |
| 2022 | 3866 | 15328 | 17440 | 4179 | 17842 | 43429 |
| 2023 | 0 | 24069 | 0 | 0 | 29147 | 0 |
| 2024 | 3646 | 31715 | 0 | 3882 | 38852 | 0 |
| 2025 | 1549 | 30654 | 0 | 1603 | 38967 | 0 |
| 2026 | 2844 | 121383 | 2019 | 2989 | 160127 | 4928 |

### Por ano-mês (artigos distintos e pares)

| mês | artigos cvm_ipe | artigos google_news | artigos wordpress | pares cvm_ipe | pares google_news | pares wordpress |
|---|---|---|---|---|---|---|
| 2021-01 | 303 | 963 | 989 | 321 | 1113 | 2331 |
| 2021-02 | 329 | 1010 | 1374 | 360 | 1242 | 3135 |
| 2021-03 | 428 | 1089 | 1328 | 470 | 1257 | 2867 |
| 2021-04 | 380 | 1174 | 1212 | 424 | 1354 | 2693 |
| 2021-05 | 372 | 1084 | 1254 | 399 | 1211 | 2882 |
| 2021-06 | 306 | 1142 | 1248 | 338 | 1317 | 2901 |
| 2021-07 | 286 | 1080 | 1225 | 310 | 1237 | 2825 |
| 2021-08 | 378 | 1306 | 1396 | 404 | 1471 | 3384 |
| 2021-09 | 308 | 1187 | 1181 | 329 | 1356 | 2847 |
| 2021-10 | 339 | 1234 | 1328 | 364 | 1464 | 3217 |
| 2021-11 | 406 | 1273 | 1464 | 445 | 1470 | 3473 |
| 2021-12 | 402 | 1245 | 1127 | 435 | 1428 | 2724 |
| 2022-01 | 265 | 1096 | 1102 | 280 | 1300 | 2801 |
| 2022-02 | 347 | 1073 | 1438 | 370 | 1258 | 3443 |
| 2022-03 | 410 | 1298 | 1613 | 440 | 1495 | 3961 |
| 2022-04 | 356 | 1203 | 1342 | 388 | 1380 | 3422 |
| 2022-05 | 375 | 1449 | 1736 | 406 | 1711 | 4311 |
| 2022-06 | 286 | 1322 | 1508 | 325 | 1619 | 3791 |
| 2022-07 | 269 | 1288 | 1453 | 300 | 1521 | 3739 |
| 2022-08 | 341 | 1371 | 1701 | 366 | 1537 | 4124 |
| 2022-09 | 259 | 1219 | 1274 | 274 | 1390 | 3076 |
| 2022-10 | 257 | 1330 | 1445 | 274 | 1535 | 3765 |
| 2022-11 | 362 | 1353 | 1518 | 389 | 1568 | 3642 |
| 2022-12 | 339 | 1326 | 1310 | 367 | 1528 | 3354 |
| 2023-01 | 0 | 1832 | 0 | 0 | 2249 | 0 |
| 2023-02 | 0 | 1616 | 0 | 0 | 1944 | 0 |
| 2023-03 | 0 | 1949 | 0 | 0 | 2412 | 0 |
| 2023-04 | 0 | 1654 | 0 | 0 | 1991 | 0 |
| 2023-05 | 0 | 2058 | 0 | 0 | 2625 | 0 |
| 2023-06 | 0 | 2028 | 0 | 0 | 2425 | 0 |
| 2023-07 | 0 | 1845 | 0 | 0 | 2225 | 0 |
| 2023-08 | 0 | 2103 | 0 | 0 | 2474 | 0 |
| 2023-09 | 0 | 1942 | 0 | 0 | 2397 | 0 |
| 2023-10 | 0 | 2295 | 0 | 0 | 2707 | 0 |
| 2023-11 | 0 | 2143 | 0 | 0 | 2618 | 0 |
| 2023-12 | 0 | 2604 | 0 | 0 | 3080 | 0 |
| 2024-01 | 262 | 2185 | 0 | 279 | 2806 | 0 |
| 2024-02 | 257 | 2162 | 0 | 277 | 2742 | 0 |
| 2024-03 | 329 | 2488 | 0 | 350 | 3054 | 0 |
| 2024-04 | 349 | 2746 | 0 | 379 | 3463 | 0 |
| 2024-05 | 381 | 2864 | 0 | 414 | 3686 | 0 |
| 2024-06 | 246 | 2386 | 0 | 267 | 2883 | 0 |
| 2024-07 | 254 | 2829 | 0 | 262 | 3325 | 0 |
| 2024-08 | 311 | 2751 | 0 | 328 | 3385 | 0 |
| 2024-09 | 277 | 2731 | 0 | 291 | 3323 | 0 |
| 2024-10 | 294 | 2989 | 0 | 310 | 3581 | 0 |
| 2024-11 | 351 | 2594 | 0 | 374 | 3101 | 0 |
| 2024-12 | 335 | 2990 | 0 | 351 | 3503 | 0 |
| 2025-01 | 0 | 38 | 0 | 0 | 42 | 0 |
| 2025-08 | 352 | 4180 | 0 | 364 | 5163 | 0 |
| 2025-09 | 243 | 6057 | 0 | 251 | 7465 | 0 |
| 2025-10 | 269 | 6722 | 0 | 279 | 8741 | 0 |
| 2025-11 | 357 | 6786 | 0 | 371 | 8543 | 0 |
| 2025-12 | 328 | 6871 | 0 | 338 | 9013 | 0 |
| 2026-01 | 281 | 7079 | 0 | 288 | 9442 | 0 |
| 2026-02 | 279 | 7718 | 0 | 294 | 9845 | 0 |
| 2026-03 | 393 | 10793 | 1625 | 414 | 14188 | 3975 |
| 2026-04 | 341 | 10740 | 0 | 366 | 14100 | 0 |
| 2026-05 | 320 | 11582 | 0 | 339 | 14836 | 0 |
| 2026-06 | 255 | 10642 | 0 | 265 | 13639 | 0 |
| 2026-07 | 205 | 12312 | 0 | 215 | 15995 | 0 |
| 2026-08 | 330 | 16261 | 0 | 342 | 21436 | 0 |
| 2026-09 | 196 | 13009 | 0 | 207 | 17463 | 0 |
| 2026-10 | 244 | 21215 | 391 | 259 | 29134 | 950 |
| 2026-11 | 0 | 32 | 3 | 0 | 49 | 3 |

### Por origem

| origem | artigos | pares |
|---|---|---|
| cvm_ipe | 16142 | 17252 |
| google_news | 236936 | 300855 |
| wordpress | 34585 | 83636 |

### Por ticker (40 com maior participação wordpress)

| ticker | pares | pares wordpress | participação wordpress |
|---|---|---|---|
| AUAU3 | 499 | 299 | 59.9% |
| LWSA3 | 1427 | 837 | 58.7% |
| CVCB3 | 1468 | 861 | 58.7% |
| CSNA3 | 2623 | 1497 | 57.1% |
| B3SA3 | 4898 | 2497 | 51.0% |
| VIVT3 | 1541 | 735 | 47.7% |
| ITUB4 | 8792 | 4070 | 46.3% |
| MRVE3 | 1749 | 785 | 44.9% |
| COGN3 | 1496 | 629 | 42.0% |
| IRBR3 | 1223 | 514 | 42.0% |
| BEEF3 | 2226 | 895 | 40.2% |
| TIMS3 | 2445 | 966 | 39.5% |
| RDOR3 | 2110 | 818 | 38.8% |
| MGLU3 | 6697 | 2573 | 38.4% |
| UGPA3 | 1687 | 602 | 35.7% |
| PRIO3 | 2310 | 815 | 35.3% |
| VALE3 | 13144 | 4385 | 33.4% |
| RAIL3 | 1605 | 511 | 31.8% |
| PCAR3 | 2746 | 870 | 31.7% |
| BRAP4 | 845 | 262 | 31.0% |
| BPAC11 | 7907 | 2382 | 30.1% |
| DIRR3 | 876 | 258 | 29.5% |
| ITSA4 | 1630 | 476 | 29.2% |
| HYPE3 | 1489 | 434 | 29.1% |
| VBBR3 | 1835 | 529 | 28.8% |
| USIM5 | 3575 | 1027 | 28.7% |
| LREN3 | 2501 | 704 | 28.1% |
| PETR4 | 38640 | 10367 | 26.8% |
| YDUQ3 | 2021 | 540 | 26.7% |
| CRFB3 | 132 | 35 | 26.5% |
| CMIN3 | 1784 | 464 | 26.0% |
| BBSE3 | 2052 | 532 | 25.9% |
| RECV3 | 1729 | 439 | 25.4% |
| PETR3 | 36720 | 9209 | 25.1% |
| VAMO3 | 1015 | 253 | 24.9% |
| CYRE3 | 2688 | 662 | 24.6% |
| AZUL3 | 4008 | 966 | 24.1% |
| TAEE11 | 1699 | 401 | 23.6% |
| RADL3 | 1453 | 337 | 23.2% |
| EGIE3 | 1755 | 392 | 22.3% |

Tickers sem nenhum artigo wordpress: 1 de 88. Primeiros: SRNA3.

### Nº de tickers por artigo wordpress

| nº de tickers | artigos |
|---|---|
| 1 | 16717 |
| 2 | 9368 |
| 3 | 3211 |
| 4 | 1615 |
| 5 | 1040 |
| 6 | 611 |
| 7 | 493 |
| 8 | 340 |
| 9 | 264 |
| 10 | 191 |
| 11 | 133 |
| 12 | 94 |
| 13 | 77 |
| 14 | 58 |
| 15 | 30 |
| 16 | 38 |
| 17 | 36 |
| 18 | 26 |
| 19 | 30 |
| 20 | 24 |
| 21 | 21 |
| 22 | 17 |
| 23 | 19 |
| 24 | 15 |
| 25 | 19 |
| 26 | 10 |
| 27 | 14 |
| 28 | 11 |
| 29 | 6 |
| 30 | 12 |
| 31 | 9 |
| 32 | 7 |
| 33 | 6 |
| 34 | 4 |
| 35 | 3 |
| 36 | 2 |
| 37 | 2 |
| 38 | 3 |
| 39 | 1 |
| 40 | 1 |
| 42 | 2 |
| 44 | 1 |
| 46 | 1 |
| 47 | 1 |
| 52 | 1 |
| 54 | 1 |

## 2. Fontes e domínios

### Top 30 `fonte`

| fonte | artigos |
|---|---|
| Money Times | 17783 |
| InfoMoney | 9020 |
| Exame | 7782 |

### Top 30 domínio do link

| domínio | artigos |
|---|---|
| moneytimes.com.br | 17783 |
| infomoney.com.br | 9020 |
| exame.com | 7782 |

### Comparação com a raw_articles

| comparação | comparáveis | iguais | diferentes | sem valor (nos dois lados) |
|---|---|---|---|---|
| domínio do link × source_domain (raw) | 34585 | 34585 | 0 | 0 |
| fonte × source_name (raw) | 34585 | 34585 | 0 | 0 |

Links vazios: 0 linhas de wordpress e 0 artigos distintos.
Links repetidos: 0 links aparecem em mais de um artigo (0 artigos ao todo).

## 3. Duplicatas com google_news

Artigos wordpress com par no google_news: 1194 de 34585 (3.5%). Por título (mesmo ticker, ±1 dia): 1143; por URL (link × resolved_url): 742.

### Por ano

| ano | artigos wordpress | % com título | % com URL | % com algum |
|---|---|---|---|---|
| 2021 | 15126 | 1.4% | 0.0% | 1.4% |
| 2022 | 17440 | 0.6% | 0.1% | 0.7% |
| 2026 | 2019 | 41.0% | 35.9% | 42.6% |
| total | 34585 | 3.3% | 2.1% | 3.5% |

Duplicatas em que o wordpress tem hora real e o google_news não tem: 1031 artigos (1061 pares).

## 4. Hora, fuso, data e momento_pregao

### Fuso do texto de data_hora_publicacao

| origem | linhas com horário | terminam em -03:00 |
|---|---|---|
| wordpress | 83636 | 100.0% |
| google_news | 210577 | 100.0% |

### Comparação com published_at (UTC → São Paulo), todas as linhas

| origem | linhas | iguais | diferentes | sem horário | sem raw_articles |
|---|---|---|---|---|---|
| cvm_ipe | 17252 | 0 | 0 | 17252 | 0 |
| google_news | 300855 | 210577 | 0 | 90278 | 0 |
| wordpress | 83636 | 83636 | 0 | 0 | 0 |

Fuso do wordpress (critério): 83636 de 83636 linhas com horário batem com published_at.

### Histograma da hora (São Paulo)

| hora | wordpress | google_news |
|---|---|---|
| 00h | 45 | 518 |
| 01h | 16 | 377 |
| 02h | 18 | 330 |
| 03h | 4 | 371 |
| 04h | 22 | 132768 |
| 05h | 314 | 40028 |
| 06h | 1777 | 1058 |
| 07h | 6105 | 1585 |
| 08h | 7443 | 2267 |
| 09h | 6602 | 2746 |
| 10h | 6927 | 2728 |
| 11h | 4450 | 2813 |
| 12h | 5790 | 2443 |
| 13h | 4370 | 2252 |
| 14h | 3674 | 2306 |
| 15h | 3905 | 2542 |
| 16h | 3948 | 2407 |
| 17h | 12186 | 2576 |
| 18h | 9309 | 2642 |
| 19h | 3611 | 1958 |
| 20h | 1943 | 1508 |
| 21h | 889 | 972 |
| 22h | 216 | 767 |
| 23h | 72 | 615 |

Wordpress: 429 de 83636 horários são em ponto (minuto e segundo zero). Horas em ponto suspeitas (00:00, 03:00, 04:00, 05:00):

| hora em ponto | linhas | % dos horários wordpress |
|---|---|---|
| 00:00 | 1 | 0.0% |
| 03:00 | 0 | 0.0% |
| 04:00 | 0 | 0.0% |
| 05:00 | 73 | 0.1% |

### Fim de semana

| origem | linhas com horário | sábado ou domingo | % |
|---|---|---|---|
| wordpress | 83636 | 5011 | 6.0% |
| google_news | 210577 | 19471 | 9.2% |

### Publicação após a coleta, datas futuras e data_publicacao × data de São Paulo

| origem | linhas com horário | publicação > coleta | data_publicacao no futuro (> dia da coleta) | data_publicacao = data SP de data_hora_publicacao |
|---|---|---|---|---|
| wordpress | 83636 | 0 | 0 | 100.0% |
| google_news | 210577 | 0 | 0 | 100.0% |

### momento_pregao × horário (informativo, wordpress; regra das 18h não especificada)

| momento_pregao | 18h ou depois | antes de 18h |
|---|---|---|
| antes_abertura | 0 | 20613 |
| apos_fechamento | 15296 | 0 |
| durante | 0 | 42050 |
| sem_pregao | 744 | 4933 |

### Precisão do horário (wordpress)

| precisão | linhas | % |
|---|---|---|
| hora real | 83636 | 100.0% |

N1-A (`fontes.aplicar_regra_so_data`) trataria 0 linhas wordpress com horário como só data (meia-noite do Pacífico). Por ano: 2021: 0, 2022: 0, 2026: 0. Só reportado; a regra não foi alterada.

## 5. FinBERT

### Probabilidades vazias (prob_positivo)

| origem | linhas | vazias | % |
|---|---|---|---|
| cvm_ipe | 17252 | 0 | 0.0% |
| google_news | 300855 | 0 | 0.0% |
| wordpress | 83636 | 0 | 0.0% |

### model × lang × text_source (artigos wordpress com FinBERT)

| model | lang | text_source | artigos |
|---|---|---|---|
| lucas-leme/FinBERT-PT-BR | pt | body | 34582 |
| lucas-leme/FinBERT-PT-BR | pt | title | 3 |

Artigos wordpress distintos sem linha em staging_article_sentiment: 0 de 34585.

### Distribuição do score (prob_positivo − prob_negativo)

| origem | n | média | p10 | p50 | p90 |
|---|---|---|---|---|---|
| wordpress | 83636 | -0.100 | -0.891 | -0.084 | 0.846 |
| google_news | 300855 | -0.028 | -0.898 | 0.039 | 0.801 |

Concordância do score nas duplicatas (1250 pares com score nos dois lados): correlação 0.854; mesmo sinal em 87.7% dos pares.

## 6. Juíza (papel, tipo, evento, qualidade)

### % julgado (papel preenchido)

| origem | linhas | julgadas | % |
|---|---|---|---|
| cvm_ipe | 17252 | 17252 | 100.0% |
| google_news | 300855 | 299512 | 99.6% |
| wordpress | 83636 | 83636 | 100.0% |

### Distribuição de papel (wordpress × google_news; top 25)

| papel | wordpress | % wp | google_news | % gn |
|---|---|---|---|---|
| mencao | 34334 | 41.1% | 82432 | 27.4% |
| protagonista | 24986 | 29.9% | 149801 | 49.8% |
| citada_com_fato | 23068 | 27.6% | 34634 | 11.5% |
| errada | 1228 | 1.5% | 32320 | 10.7% |
| matriz_estrangeira | 20 | 0.0% | 325 | 0.1% |
| (vazio) | 0 | 0.0% | 1343 | 0.4% |

### Distribuição de tipo_conteudo (wordpress × google_news; top 25)

| tipo_conteudo | wordpress | % wp | google_news | % gn |
|---|---|---|---|---|
| reportagem | 44910 | 53.7% | 231770 | 77.0% |
| resumo_mercado | 29466 | 35.2% | 17460 | 5.8% |
| lista | 7246 | 8.7% | 10776 | 3.6% |
| agenda | 995 | 1.2% | 7278 | 2.4% |
| opiniao | 736 | 0.9% | 9323 | 3.1% |
| patrocinado | 98 | 0.1% | 3191 | 1.1% |
| podcast_video | 95 | 0.1% | 1325 | 0.4% |
| outro | 54 | 0.1% | 18188 | 6.0% |
| newsletter | 36 | 0.0% | 201 | 0.1% |
| (vazio) | 0 | 0.0% | 1343 | 0.4% |

### Distribuição de evento (wordpress × google_news; top 25)

| evento | wordpress | % wp | google_news | % gn |
|---|---|---|---|---|
| outro | 28670 | 34.3% | 88618 | 29.5% |
| macro | 24455 | 29.2% | 34351 | 11.4% |
| recomendacao | 7594 | 9.1% | 10925 | 3.6% |
| resultado | 5919 | 7.1% | 12434 | 4.1% |
| operacional | 5026 | 6.0% | 89845 | 29.9% |
| fusao_aquisicao | 3102 | 3.7% | 13911 | 4.6% |
| governanca | 2846 | 3.4% | 10666 | 3.5% |
| dividendo_jcp | 2550 | 3.0% | 7039 | 2.3% |
| fato_relevante | 1087 | 1.3% | 6214 | 2.1% |
| juridico | 1061 | 1.3% | 15601 | 5.2% |
| regulatorio | 1029 | 1.2% | 7989 | 2.7% |
| guidance | 283 | 0.3% | 1635 | 0.5% |
| mudanca_ticker | 14 | 0.0% | 284 | 0.1% |
| (vazio) | 0 | 0.0% | 1343 | 0.4% |

### Distribuição de qualidade (wordpress × google_news; top 25)

| qualidade | wordpress | % wp | google_news | % gn |
|---|---|---|---|---|
| 0.7 | 21110 | 25.2% | 6663 | 2.2% |
| 0.1 | 17709 | 21.2% | 21791 | 7.2% |
| 0.2 | 11984 | 14.3% | 14170 | 4.7% |
| 0.3 | 3912 | 4.7% | 17641 | 5.9% |
| 0.4 | 3222 | 3.9% | 12500 | 4.2% |
| 0.5 | 1514 | 1.8% | 10098 | 3.4% |
| 0.35 | 1126 | 1.3% | 2050 | 0.7% |
| 0.25 | 621 | 0.7% | 1886 | 0.6% |
| 0.6 | 568 | 0.7% | 7170 | 2.4% |
| 0.45 | 517 | 0.6% | 1438 | 0.5% |
| 0.15 | 273 | 0.3% | 2889 | 1.0% |
| 0.4575 | 153 | 0.2% | 511 | 0.2% |
| 0.47 | 152 | 0.2% | 485 | 0.2% |
| 0.415 | 146 | 0.2% | 583 | 0.2% |
| 0.48 | 144 | 0.2% | 499 | 0.2% |
| 0.4075 | 140 | 0.2% | 552 | 0.2% |
| 0.4025 | 138 | 0.2% | 544 | 0.2% |
| 0.455 | 138 | 0.2% | 510 | 0.2% |
| 0.4725 | 135 | 0.2% | 474 | 0.2% |
| 0.515 | 135 | 0.2% | 465 | 0.2% |
| 0.435 | 134 | 0.2% | 514 | 0.2% |
| 0.44 | 133 | 0.2% | 512 | 0.2% |
| 0.475 | 133 | 0.2% | 496 | 0.2% |
| 0.51 | 133 | 0.2% | 443 | 0.1% |
| 0.425 | 132 | 0.2% | 533 | 0.2% |

### Taxa de 'errada' por ticker (top 15 com maior diferença wordpress − google_news; só julgadas)

| ticker | wp julgadas | wp errada | taxa wp | gn julgadas | gn errada | taxa gn | diferença |
|---|---|---|---|---|---|---|---|
| BBDC3 | 2287 | 258 | 11.3% | 11459 | 844 | 7.4% | +3.9 p.p. |
| BBDC4 | 2820 | 292 | 10.4% | 11671 | 1056 | 9.0% | +1.3 p.p. |
| AZUL3 | 966 | 33 | 3.4% | 2782 | 110 | 4.0% | -0.5 p.p. |
| ITUB4 | 4070 | 271 | 6.7% | 4452 | 352 | 7.9% | -1.2 p.p. |
| MBRF3 | 226 | 8 | 3.5% | 709 | 37 | 5.2% | -1.7 p.p. |
| EQTL3 | 490 | 2 | 0.4% | 2451 | 52 | 2.1% | -1.7 p.p. |
| CVCB3 | 861 | 17 | 2.0% | 484 | 18 | 3.7% | -1.7 p.p. |
| PETR3 | 9209 | 49 | 0.5% | 26418 | 653 | 2.5% | -1.9 p.p. |
| EMBJ3 | 885 | 2 | 0.2% | 18495 | 449 | 2.4% | -2.2 p.p. |
| ENGI11 | 371 | 0 | 0.0% | 4598 | 111 | 2.4% | -2.4 p.p. |
| SBSP3 | 509 | 0 | 0.0% | 6627 | 160 | 2.4% | -2.4 p.p. |
| RDOR3 | 818 | 0 | 0.0% | 1148 | 28 | 2.4% | -2.4 p.p. |
| PETR4 | 10367 | 8 | 0.1% | 27180 | 692 | 2.5% | -2.5 p.p. |
| CPLE3 | 405 | 8 | 2.0% | 3858 | 172 | 4.5% | -2.5 p.p. |
| AZZA3 | 375 | 34 | 9.1% | 1272 | 150 | 11.8% | -2.7 p.p. |

## 7. Amostra manual

Arquivo: `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\docs\validacao_wordpress_amostra.csv` (lida do CSV já existente (não sobrescrito)).

Preencher `ticker_correto` com S (ticker certo), N (ticker errado) ou ? (dúvida). Vazio = ainda não revisado. O critério exige 27 de 30 com S.

| id | ticker | data_hora_publicacao | titulo | fonte | papel | evento | ticker_correto |
|---|---|---|---|---|---|---|---|
| n444163 | BBDC3 | 2021-02-17T17:07:55-03:00 | Klabin continuará aproveitando dinâmica favorável da celulose nos próximos meses | Money Times | errada | recomendacao |  |
| n443412 | PETR3 | 2021-02-24T09:28:10-03:00 | Prévia da inflação sobe 0,48% em fevereiro, diz IBGE | Exame | citada_com_fato | governanca |  |
| n446295 | B3SA3 | 2021-04-08T17:30:05-03:00 | Ação da Embraer salta 8,8% com possível negociação com indiana; Magalu dispara 8% seguindo techs dos EUA e Usiminas sobe 3,7% | InfoMoney | mencao | macro |  |
| n448936 | ITUB4 | 2021-06-15T17:23:16-03:00 | Ações da Eletrobras fecham em direções distintas às vésperas de votação da MP; Viver salta 30% após pedido para sair de recuperação judicial | InfoMoney | errada | outro |  |
| n454059 | RDOR3 | 2021-10-07T17:20:06-03:00 | Ações de educacionais saltam até 10% após dados de captação da Ser, Vale sobe 3% e varejistas voltam a ter queda; CVC cai 4,7% | InfoMoney | mencao | outro |  |
| n453956 | PETR4 | 2021-10-29T07:15:38-03:00 | Repercussão de Vale e Petrobras, inflação na Europa e o que move o mercado | Exame | protagonista | outro |  |
| n455874 | AZUL3 | 2021-11-11T06:30:47-03:00 | Ponte Aérea Rio-São Paulo: Depois do Zoom, ela já não é mais a mesma (para azar da Azul e da Gol) | Money Times | protagonista | outro |  |
| n455174 | NATU3 | 2021-11-19T10:00:44-03:00 | Black Friday: 30 itens de moda, eletrônicos, decoração e viagens | Exame | citada_com_fato | operacional |  |
| n456241 | TIMS3 | 2021-11-24T11:54:59-03:00 | KKR pode subir oferta por Telecom Itália para convencer Vivendi | Money Times | matriz_estrangeira | fusao_aquisicao |  |
| n456248 | TIMS3 | 2021-11-24T14:33:55-03:00 | Mais de 25% das ações da Telecom Italia com direito a voto trocaram de mão desde oferta da KKR | Money Times | matriz_estrangeira | fusao_aquisicao |  |
| n402152 | BBDC4 | 2022-02-22T15:41:34-03:00 | Movida (MOVI3): Lucro duplica e ação dispara; há espaço para alta de até 80%, dizem analistas | Money Times | errada | resultado |  |
| n401110 | PETR3 | 2022-02-24T12:56:42-03:00 | Ao vivo: Ibovespa minimiza perdas após fala de Biden sobre Rússia | Exame | citada_com_fato | resultado |  |
| n403183 | TIMS3 | 2022-03-03T11:40:18-03:00 | Telecom Italia aponta vantagens em plano de reorganização, mas ações desabam após balanço | Money Times | matriz_estrangeira | fusao_aquisicao |  |
| n406383 | ABEV3 | 2022-05-05T07:16:00-03:00 | AB InBev lucra menos no 1º trimestre, mas amplia receita e Ebitda | Money Times | matriz_estrangeira | resultado |  |
| n405893 | VIVT3 | 2022-05-06T18:50:45-03:00 | Locaweb (LWSA3) e Totvs (TOTS3) são alguns dos destaques negativos da Bolsa nesta sexta-feira | InfoMoney | mencao | outro |  |
| n409232 | BBDC3 | 2022-07-30T11:34:52-03:00 | Bancos elevam previsão de alta do PIB para até 2,5% | Exame | citada_com_fato | macro |  |
| n411689 | PETR3 | 2022-08-12T17:00:51-03:00 | Por que Petrobras (PETR4) subiu 7% apesar de dividendos já pagos e petróleo em queda? | Money Times | protagonista | dividendo_jcp |  |
| n411169 | USIM5 | 2022-08-26T17:50:00-03:00 | Usiminas (USIM5) eleva projeções de investimentos em reformas e reparos; ações fecham em queda de 6,7% | InfoMoney | protagonista | operacional |  |
| n415284 | PCAR3 | 2022-11-22T13:49:05-03:00 | Como comprar pneu com desconto na Black Friday 2022? | Exame | mencao | outro |  |
| n417875 | NATU3 | 2022-12-27T09:12:21-03:00 | Com recorde de exportação de carne fresca, frigoríficos se preparam para 2023 quando muito igual | Money Times | errada | macro |  |
| n394201 | B3SA3 | 2026-03-03T18:32:09-03:00 | Ibovespa tem pior queda desde dezembro, com quase todos os ativos no vermelho | InfoMoney |  |  |  |
| n394393 | CMIN3 | 2026-03-11T17:34:55-03:00 | Ibovespa consegue nova alta, com impulso da Petrobras, na contramão do exterior | InfoMoney |  |  |  |
| n395029 | RAIL3 | 2026-03-11T10:35:48-03:00 | Cosan (CSAN3) nega ‘engajamento’ para venda de participação na Rumo (RAIL3); entenda | Money Times | protagonista | fusao_aquisicao |  |
| n395171 | BBAS3 | 2026-03-17T12:48:18-03:00 | Operação Concorrência Simulada: PF cumpre mandados de busca e apreensão e de prisão preventiva contra fraude em concursos públicos | Money Times | mencao | outro |  |
| n394583 | POMO4 | 2026-03-19T05:00:00-03:00 | Como investir em ações com Selic em queda e petróleo acima de US$ 100 | InfoMoney | mencao | outro |  |
| n398577 | ITUB4 | 2026-10-27T11:32:58-03:00 | Gerdau sobe no circuit breaker e CEO vê ‘aspecto muito positivo’ na reeleição | Exame | errada | macro |  |
| n398643 | BPAC11 | 2026-10-27T12:41:33-03:00 | Como se posicionar em ações de bancos após as eleições? UBS BB aponta preferências | InfoMoney | protagonista | recomendacao |  |
| n477863 | LREN3 | 2026-10-28T09:30:48-03:00 | BTG lista 26 ações que ficaram baratas depois do tombo pós-eleição | Exame | citada_com_fato | recomendacao |  |
| n477888 | AZZA3 | 2026-10-28T17:28:32-03:00 | Ibovespa tem baixa forte, com fiscal no radar e decisão do Fed; dólar cai a R$ 5,34 | InfoMoney | citada_com_fato | macro |  |
| n477890 | ITUB4 | 2026-10-28T17:41:40-03:00 | Hypera (HYPE3) sobe na contramão do Ibovespa após balanço positivo no 3º tri | InfoMoney | errada | outro |  |

## 8. Impacto com × sem wordpress

v1-noticias lida uma vez só (na carga, com wordpress); os dois cenários saem em memória pelo mesmo tratamento do `ler_noticias` (`tratar_noticias_lidas`). Com = nenhuma origem ignorada. Sem = tira a origem wordpress (lista explícita, não `origens_ignoradas` do mapa, que pode estar vazia). Versão de notícias 'todas', como no dataset; 117785 pares pregão × ação do universo; 1703 pregões.

### Deduplicação e preparo

| leitura | lidas | duplicadas por id | duplicadas por título | preparadas | sem probabilidade |
|---|---|---|---|---|---|
| com wordpress | 401743 | 47494 | 5461 | 346644 | 0 |
| sem wordpress | 318107 | 36067 | 5418 | 276022 | 0 |

### Pares pregão × ação com ≥1 notícia na janela do dia (noticias_dia_qtd > 0)

| ano | pares | com wordpress | sem wordpress | diferença |
|---|---|---|---|---|
| 2019 | 70 | 0 | 0 | 0 |
| 2020 | 17678 | 0 | 0 | 0 |
| 2021 | 14742 | 10416 | 7498 | 2918 |
| 2022 | 16169 | 12223 | 8107 | 4116 |
| 2023 | 16693 | 7998 | 7998 | 0 |
| 2024 | 18005 | 11039 | 11039 | 0 |
| 2025 | 19189 | 6165 | 6166 | -1 |
| 2026 | 15239 | 13704 | 13642 | 62 |
| total | 117785 | 61545 | 54450 | 7095 |

Correlação de noticias_dia_qtd (com × sem): 0.950. Linhas com quantidade diferente: 18826.
Correlação de noticias_dia_tom (com × sem): 0.925.

### 10 maiores diferenças de noticias_dia_tom

| data | ticker | tom com | tom sem | diferença absoluta |
|---|---|---|---|---|
| 2022-02-17 | GGBR4 | -0.707 | 0.852 | 1.559 |
| 2022-07-20 | CYRE3 | 0.754 | -0.710 | 1.465 |
| 2022-08-04 | PRIO3 | 0.541 | -0.893 | 1.435 |
| 2021-07-05 | CSNA3 | -0.545 | 0.875 | 1.419 |
| 2021-02-17 | TIMS3 | -0.530 | 0.860 | 1.390 |
| 2022-08-01 | BRKM5 | -0.533 | 0.831 | 1.363 |
| 2022-06-22 | GGBR4 | -0.582 | 0.775 | 1.357 |
| 2022-05-05 | TOTS3 | -0.424 | 0.916 | 1.340 |
| 2022-07-26 | MGLU3 | -0.703 | 0.632 | 1.334 |
| 2021-08-19 | CVCB3 | -0.450 | 0.869 | 1.319 |

### Últimos 5 pregões: notícias por ação (leitura até o corte da manhã)

| pregão | notícias com | notícias sem | diferença | ações com notícia (com) | ações com notícia (sem) | maiores diferenças por ação |
|---|---|---|---|---|---|---|
| 2026-10-26 | 393003 | 310264 | 82739 | 89 | 89 | PETR4 (+10299), PETR3 (+9147), VALE3 (+4335) |
| 2026-10-27 | 395213 | 312301 | 82912 | 89 | 89 | PETR4 (+10313), PETR3 (+9159), VALE3 (+4341) |
| 2026-10-28 | 396762 | 313668 | 83094 | 89 | 89 | PETR4 (+10327), PETR3 (+9171), VALE3 (+4350) |
| 2026-10-29 | 398087 | 314840 | 83247 | 89 | 89 | PETR4 (+10340), PETR3 (+9184), VALE3 (+4359) |
| 2026-10-30 | 399859 | 316427 | 83432 | 89 | 89 | PETR4 (+10353), PETR3 (+9196), VALE3 (+4371) |

## 9. Veredito

| critério | valor | limite | status |
|---|---|---|---|
| Fuso: 100% das linhas batem com published_at (UTC→SP) | 100.00% | 100% | OK |
| Cobertura FinBERT (wordpress) ≥ 99% | 100.00% | ≥ 99% | OK |
| Taxa de papel='errada' (wordpress) ≤ google_news + 5 p.p. | wordpress 1.47% × google_news 10.79% | ≤ google_news + 5 p.p. | OK |
| Anos com wordpress em raw_articles presentes na v1-noticias (≥ ano_min) | nenhum | nenhum faltando | OK |
| N1-A não trata fonte com hora real (wordpress) como só data | 0 | 0 linhas | OK |
| Amostra manual ≥ 27/30 'S' | 0/30 'S', 30 sem revisão | ≥ 27/30 'S' | PENDENTE |

**Recomendação: liberar só depois de resolver os pendentes.**

### Precisa resolver antes de liberar

- Papel 'errada': o código não filtra papel='errada' na versão 'todas' (padrão do dataset, `fontes.ler_noticias` não filtra papel). Só a versão 'principais' filtra papéis (experimento.principais.papeis). Só reportado: nada foi alterado.

### Perguntas para a coleta

- Quais sites entram na fonte wordpress, e com que critério?
- Como o ticker é atribuído a cada artigo (busca no título, no corpo, ou outra regra)?
- A coleta usa `date` ou `date_gmt`? Isso muda o fuso e a hora usados aqui.
- Os artigos têm corpo (body)? Hoje a análise só vê título e link.
- Por que 2023, 2024 e 2025 não aparecem na entrega (ver seção 0)?
- Qual é o status de 2021 (em processamento, descartado ou fora do escopo)?
