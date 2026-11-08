# Sensibilidade da rodada 003: exploratório

**Exploratório.** `modelo_oficial`: false. Não muda hipótese, configuração congelada nem teste final. Não constitui recomendação de investimento.

- Contagem declarada à parte do protocolo: 4 análises e 7 escopos. Não entra em `docs/protocolo_tentativas.jsonl`.
- IC sem ajuste por múltiplas comparações.
- Só desenvolvimento (`treino.ler_desenvolvimento`): sem banco, sem teste final e sem gravar em modelos/.

## Identificação

- Dataset todas: `dataset-todas-2026-11-06.csv`; sha256 `c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa`; versao_preparacao 7; 94485 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Dataset principais: `dataset-principais-2026-11-06.csv`; sha256 `ca7d5bd161d159c133c07867bb44ff0c7a15b03d845978593f2f87cbf5446912`; versao_preparacao 7; 94485 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Dataset hora_real_noite: `dataset-hora_real_noite-2026-11-06.csv`; sha256 `d1909b4f5a6c77086a9fef92f80f6981217dc7521c79527a4486a6364adab28d`; versao_preparacao 7; 94485 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Data: 2026-11-06; semente: 20261023; top principal: 5; dobras walk-forward: 63; rodada congelada: 3
- sha_parametros: `2af43f4004c8ed1acb3c7a32b7da4a9c7af470339abf147949dededf51f5ba96`; versões: {'xgboost': '3.4.1', 'sklearn': '1.9.1', 'pandas': '3.1.0', 'numpy': '2.5.4'}
- Família: XGBoost; hiperparâmetros: {'colsample_bytree': 0.8, 'learning_rate': 0.03, 'max_depth': 3, 'min_child_weight': 50, 'n_estimators': 300, 'reg_lambda': 5, 'subsample': 0.8}; configuração: configuracao_final_rodada_003.json
- Colunas do modelo 1: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas do modelo 3: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas de notícia (análise d): noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom
- IC 95%: bloco de 5 pregões, 2000 reamostragens, percentis 2,5 e 97,5
- IC 99,5%: bloco de 5 pregões, 10000 reamostragens, percentis 0,25 e 99,75

## (a) Recorte com ≥ 1 notícia: modelo 1 × modelo 3 (dataset todas)

Treino em todas as linhas; avaliação só no recorte (`noticias_dia_qtd` bruto >= 1).

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 70268; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51555 | 0.51709 | 0.00154 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.00977; 0.02129] | [0.01143; 0.02252] | [-0.00125; 0.00431] |
| IC 99,5% (idem) | [0.00747; 0.02345] | [0.00902; 0.02500] | [-0.00246; 0.00559] |
| Top 5: taxa de acerto | 0.51068 | 0.51468 | 0.00400 |
| Top 5: acertos / dias | 3322 / 1301 | 3348 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00876; 0.01676] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1301 dias): média 0.48667; faixa 2,5%–97,5%: [0.47533; 0.49808].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00252 |
| 2022 | 250 | 0.00169 |
| 2023 | 248 | 0.00047 |
| 2024 | 251 | 0.00349 |
| 2025 | 250 | -0.00098 |
| 2026 | 115 | 0.00314 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 42.93 | 0 |
| 2022 | 250 | 49.07 | 0 |
| 2023 | 248 | 53.42 | 0 |
| 2024 | 251 | 55.35 | 0 |
| 2025 | 250 | 60.50 | 0 |
| 2026 | 115 | 67.00 | 0 |

## (b) Dataset principais: modelo 3 treinado no dataset principais × modelo 1 de todas

### Todas as linhas

- Linhas: 90943; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51598 | 0.51665 | 0.00067 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01070; 0.02099] | [0.01133; 0.02189] | [-0.00200; 0.00315] |
| IC 99,5% (idem) | [0.00857; 0.02337] | [0.00897; 0.02409] | [-0.00302; 0.00412] |
| Top 5: taxa de acerto | 0.50515 | 0.51268 | 0.00753 |
| Top 5: acertos / dias | 3286 / 1301 | 3335 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00538; 0.02045] |

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00294 |
| 2022 | 250 | 0.00301 |
| 2023 | 248 | 0.00000 |
| 2024 | 251 | 0.00046 |
| 2025 | 250 | 0.00073 |
| 2026 | 115 | 0.00327 |

### Recorte ≥ 1 notícia (qtd bruta da própria versão)

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 47937; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51706 | 0.51712 | 0.00007 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01043; 0.02325] | [0.01056; 0.02340] | [-0.00432; 0.00408] |
| IC 99,5% (idem) | [0.00758; 0.02660] | [0.00746; 0.02647] | [-0.00595; 0.00590] |
| Top 5: taxa de acerto | 0.51653 | 0.51668 | 0.00015 |
| Top 5: acertos / dias | 3360 / 1301 | 3361 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.01215; 0.01184] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1301 dias): média 0.48971; faixa 2,5%–97,5%: [0.47855; 0.50085].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00086 |
| 2022 | 250 | 0.00733 |
| 2023 | 248 | -0.00384 |
| 2024 | 251 | -0.00262 |
| 2025 | 250 | -0.00424 |
| 2026 | 115 | 0.00943 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 30.62 | 0 |
| 2022 | 250 | 32.20 | 0 |
| 2023 | 248 | 33.97 | 0 |
| 2024 | 251 | 37.80 | 0 |
| 2025 | 250 | 41.86 | 0 |
| 2026 | 115 | 50.30 | 0 |

## (c) Dataset hora_real_noite: modelo 3 treinado no dataset hora_real_noite × modelo 1 de todas

**Cobertura baixa**: a tabela de papéis por dia por ano no recorte mostra quantos papéis cada dia tem; o top 5 depende de dias com ao menos 5 papéis.

### Todas as linhas

- Linhas: 90943; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51598 | 0.51639 | 0.00041 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01070; 0.02099] | [0.01121; 0.02167] | [-0.00167; 0.00259] |
| IC 99,5% (idem) | [0.00857; 0.02337] | [0.00872; 0.02381] | [-0.00257; 0.00371] |
| Top 5: taxa de acerto | 0.50515 | 0.52083 | 0.01568 |
| Top 5: acertos / dias | 3286 / 1301 | 3388 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [0.00276; 0.02721] |

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00098 |
| 2022 | 250 | -0.00065 |
| 2023 | 248 | 0.00017 |
| 2024 | 251 | -0.00137 |
| 2025 | 250 | 0.00274 |
| 2026 | 115 | 0.00113 |

### Recorte ≥ 1 notícia (qtd bruta da própria versão)

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 41399; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51768 | 0.51816 | 0.00048 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01094; 0.02424] | [0.01131; 0.02505] | [-0.00330; 0.00435] |
| IC 99,5% (idem) | [0.00774; 0.02721] | [0.00787; 0.02781] | [-0.00498; 0.00603] |
| Top 5: taxa de acerto | 0.51407 | 0.51422 | 0.00015 |
| Top 5: acertos / dias | 3344 / 1301 | 3345 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.01122; 0.01046] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1301 dias): média 0.48936; faixa 2,5%–97,5%: [0.47840; 0.50038].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00628 |
| 2022 | 250 | -0.00155 |
| 2023 | 248 | 0.00192 |
| 2024 | 251 | -0.00302 |
| 2025 | 250 | -0.00205 |
| 2026 | 115 | 0.00546 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 24.50 | 0 |
| 2022 | 250 | 30.21 | 0 |
| 2023 | 248 | 35.21 | 0 |
| 2024 | 251 | 32.11 | 0 |
| 2025 | 250 | 33.02 | 0 |
| 2026 | 115 | 36.70 | 0 |

## (d) Só notícias: XGBoost com `preparacao.NOTICIAS_DIA` (dataset todas)

Sem comparação contra o modelo 1. A referência é o acaso: AUC 0,5 e a faixa do top 5.

### Principal: recorte ≥ 1 notícia

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 70268; dias: 1301; dias com AUC: 1301

| Métrica | Valor |
|---|---|
| AUC médio por pregão | 0.50397 |
| AUC − 0,5 (referência do acaso: 0,5) | 0.00397 |
| IC 95% de AUC − 0,5 | [-0.00088; 0.00874] |
| IC 99,5% de AUC − 0,5 | [-0.00284; 0.01059] |
| Top 5: taxa de acerto | 0.49547 |
| Top 5: acertos / dias | 3223 / 1301 |
| Top 5 frente ao acaso | dentro da faixa do acaso |

Acaso do top 5 (1301 dias): média 0.48667; faixa 2,5%–97,5%: [0.47533; 0.49808].

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 42.93 | 0 |
| 2022 | 250 | 49.07 | 0 |
| 2023 | 248 | 53.42 | 0 |
| 2024 | 251 | 55.35 | 0 |
| 2025 | 250 | 60.50 | 0 |
| 2026 | 115 | 67.00 | 0 |

### Secundária: todas as linhas

- Linhas: 90943; dias: 1301; dias com AUC: 1301

| Métrica | Valor |
|---|---|
| AUC médio por pregão | 0.50293 |
| AUC − 0,5 (referência do acaso: 0,5) | 0.00293 |
| IC 95% de AUC − 0,5 | [-0.00137; 0.00712] |
| IC 99,5% de AUC − 0,5 | [-0.00326; 0.00889] |
| Top 5: taxa de acerto | 0.49408 |
| Top 5: acertos / dias | 3214 / 1301 |
| Top 5 frente ao acaso | dentro da faixa do acaso |

Acaso do top 5 (1301 dias): média 0.48622; faixa 2,5%–97,5%: [0.47486; 0.49777].

Ressalvas da secundária:

- Dias sem notícia dão score empatado: o top 5 desses dias sai em ordem alfabética de ticker.
- No período sem coleta (NaN de `noticias_dia_qtd`, jan–jul/2025), o AUC é 0,5 exato.
- Não é recorte: os números misturam dias com e sem notícia.

