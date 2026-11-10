# Sensibilidade da rodada 005: exploratório

**Exploratório.** `modelo_oficial`: false. Não muda hipótese, configuração congelada nem teste final. Não constitui recomendação de investimento.

- Contagem declarada à parte do protocolo: 4 análises e 7 escopos. Não entra em `docs/protocolo_tentativas.jsonl`.
- IC sem ajuste por múltiplas comparações.
- Só desenvolvimento (`treino.ler_desenvolvimento`): sem banco, sem teste final e sem gravar em modelos/.

## Identificação

- Dataset todas: `dataset-todas-2026-11-09.csv`; sha256 `9f520c5fa7e91ebbb2a624a6cbb89d4caf33d8bb57ca3018be89ac43016e9928`; versao_preparacao 7; 94485 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Dataset principais: `dataset-principais-2026-11-09.csv`; sha256 `bc7797c959378118f9d511434d69e54e648198df143a06cce3b530954d4803cc`; versao_preparacao 7; 94485 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Dataset hora_real_noite: `dataset-hora_real_noite-2026-11-09.csv`; sha256 `ca6f9e3eff04e2ffffe801662ecc27dbd80461a2ebb1b8b21f9773e10541d8af`; versao_preparacao 7; 94485 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Data: 2026-11-09; semente: 20261023; top principal: 5; dobras walk-forward: 63; rodada congelada: 5
- sha_parametros: `04ce153d729f35a3f3118dba48f6d616e65ca94afa4f3d49dea94bb285334023`; versões: {'xgboost': '3.4.1', 'sklearn': '1.9.1', 'pandas': '3.1.0', 'numpy': '2.5.4'}
- Família: XGBoost; hiperparâmetros: {'colsample_bytree': 0.8, 'learning_rate': 0.03, 'max_depth': 3, 'min_child_weight': 50, 'n_estimators': 300, 'reg_lambda': 5, 'subsample': 0.8}; configuração: configuracao_final_rodada_005.json
- Colunas do modelo 1: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas do modelo 3: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas de notícia (análise d): noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom
- IC 95%: bloco de 5 pregões, 2000 reamostragens, percentis 2,5 e 97,5
- IC 99,5%: bloco de 5 pregões, 10000 reamostragens, percentis 0,25 e 99,75

## (a) Recorte com ≥ 1 notícia: modelo 1 × modelo 3 (dataset todas)

Treino em todas as linhas; avaliação só no recorte (`noticias_dia_qtd` bruto >= 1).

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 70110; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51571 | 0.51719 | 0.00148 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01005; 0.02136] | [0.01148; 0.02282] | [-0.00146; 0.00442] |
| IC 99,5% (idem) | [0.00740; 0.02381] | [0.00898; 0.02525] | [-0.00282; 0.00561] |
| Top 5: taxa de acerto | 0.50638 | 0.51391 | 0.00753 |
| Top 5: acertos / dias | 3294 / 1301 | 3343 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00400; 0.01968] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1301 dias): média 0.48672; faixa 2,5%–97,5%: [0.47532; 0.49823].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00049 |
| 2022 | 250 | -0.00208 |
| 2023 | 248 | 0.00036 |
| 2024 | 251 | 0.00647 |
| 2025 | 250 | 0.00077 |
| 2026 | 115 | 0.00542 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 42.93 | 0 |
| 2022 | 250 | 49.07 | 0 |
| 2023 | 248 | 53.38 | 0 |
| 2024 | 251 | 55.18 | 0 |
| 2025 | 250 | 60.35 | 0 |
| 2026 | 115 | 66.42 | 0 |

## (b) Dataset principais: modelo 3 treinado no dataset principais × modelo 1 de todas

### Todas as linhas

- Linhas: 90943; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51630 | 0.51682 | 0.00052 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01125; 0.02157] | [0.01160; 0.02200] | [-0.00208; 0.00301] |
| IC 99,5% (idem) | [0.00886; 0.02367] | [0.00914; 0.02415] | [-0.00312; 0.00410] |
| Top 5: taxa de acerto | 0.51376 | 0.50592 | -0.00784 |
| Top 5: acertos / dias | 3342 / 1301 | 3291 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.02137; 0.00508] |

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00455 |
| 2022 | 250 | 0.00135 |
| 2023 | 248 | -0.00146 |
| 2024 | 251 | 0.00339 |
| 2025 | 250 | 0.00084 |
| 2026 | 115 | 0.00426 |

### Recorte ≥ 1 notícia (qtd bruta da própria versão)

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 47884; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51654 | 0.51801 | 0.00147 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01006; 0.02294] | [0.01140; 0.02433] | [-0.00287; 0.00564] |
| IC 99,5% (idem) | [0.00711; 0.02595] | [0.00860; 0.02737] | [-0.00465; 0.00738] |
| Top 5: taxa de acerto | 0.51038 | 0.51284 | 0.00246 |
| Top 5: acertos / dias | 3320 / 1301 | 3336 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00938; 0.01476] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1301 dias): média 0.48976; faixa 2,5%–97,5%: [0.47840; 0.50100].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00129 |
| 2022 | 250 | 0.00786 |
| 2023 | 248 | -0.00423 |
| 2024 | 251 | 0.00226 |
| 2025 | 250 | -0.00210 |
| 2026 | 115 | 0.01044 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 30.62 | 0 |
| 2022 | 250 | 32.20 | 0 |
| 2023 | 248 | 33.95 | 0 |
| 2024 | 251 | 37.76 | 0 |
| 2025 | 250 | 41.81 | 0 |
| 2026 | 115 | 50.06 | 0 |

## (c) Dataset hora_real_noite: modelo 3 treinado no dataset hora_real_noite × modelo 1 de todas

**Cobertura baixa**: a tabela de papéis por dia por ano no recorte mostra quantos papéis cada dia tem; o top 5 depende de dias com ao menos 5 papéis.

### Todas as linhas

- Linhas: 90943; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51630 | 0.51675 | 0.00045 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01125; 0.02157] | [0.01173; 0.02196] | [-0.00177; 0.00255] |
| IC 99,5% (idem) | [0.00886; 0.02367] | [0.00924; 0.02418] | [-0.00263; 0.00363] |
| Top 5: taxa de acerto | 0.51376 | 0.51545 | 0.00169 |
| Top 5: acertos / dias | 3342 / 1301 | 3353 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00968; 0.01415] |

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00020 |
| 2022 | 250 | -0.00206 |
| 2023 | 248 | -0.00139 |
| 2024 | 251 | 0.00056 |
| 2025 | 250 | 0.00405 |
| 2026 | 115 | 0.00223 |

### Recorte ≥ 1 notícia (qtd bruta da própria versão)

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 41253; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51797 | 0.51817 | 0.00020 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01087; 0.02478] | [0.01107; 0.02509] | [-0.00383; 0.00428] |
| IC 99,5% (idem) | [0.00785; 0.02771] | [0.00789; 0.02826] | [-0.00560; 0.00590] |
| Top 5: taxa de acerto | 0.50761 | 0.51053 | 0.00292 |
| Top 5: acertos / dias | 3302 / 1301 | 3321 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00769; 0.01414] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1301 dias): média 0.48943; faixa 2,5%–97,5%: [0.47825; 0.50038].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00519 |
| 2022 | 250 | -0.00205 |
| 2023 | 248 | -0.00369 |
| 2024 | 251 | 0.00049 |
| 2025 | 250 | -0.00053 |
| 2026 | 115 | 0.00628 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 24.50 | 0 |
| 2022 | 250 | 30.21 | 0 |
| 2023 | 248 | 35.19 | 0 |
| 2024 | 251 | 31.96 | 0 |
| 2025 | 250 | 32.81 | 0 |
| 2026 | 115 | 36.22 | 0 |

## (d) Só notícias: XGBoost com `preparacao.NOTICIAS_DIA` (dataset todas)

Sem comparação contra o modelo 1. A referência é o acaso: AUC 0,5 e a faixa do top 5.

### Principal: recorte ≥ 1 notícia

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 70110; dias: 1301; dias com AUC: 1301

| Métrica | Valor |
|---|---|
| AUC médio por pregão | 0.50397 |
| AUC − 0,5 (referência do acaso: 0,5) | 0.00397 |
| IC 95% de AUC − 0,5 | [-0.00105; 0.00870] |
| IC 99,5% de AUC − 0,5 | [-0.00304; 0.01079] |
| Top 5: taxa de acerto | 0.48978 |
| Top 5: acertos / dias | 3186 / 1301 |
| Top 5 frente ao acaso | dentro da faixa do acaso |

Acaso do top 5 (1301 dias): média 0.48672; faixa 2,5%–97,5%: [0.47532; 0.49823].

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 42.93 | 0 |
| 2022 | 250 | 49.07 | 0 |
| 2023 | 248 | 53.38 | 0 |
| 2024 | 251 | 55.18 | 0 |
| 2025 | 250 | 60.35 | 0 |
| 2026 | 115 | 66.42 | 0 |

### Secundária: todas as linhas

- Linhas: 90943; dias: 1301; dias com AUC: 1301

| Métrica | Valor |
|---|---|
| AUC médio por pregão | 0.50378 |
| AUC − 0,5 (referência do acaso: 0,5) | 0.00378 |
| IC 95% de AUC − 0,5 | [-0.00059; 0.00795] |
| IC 99,5% de AUC − 0,5 | [-0.00238; 0.00985] |
| Top 5: taxa de acerto | 0.48839 |
| Top 5: acertos / dias | 3177 / 1301 |
| Top 5 frente ao acaso | dentro da faixa do acaso |

Acaso do top 5 (1301 dias): média 0.48624; faixa 2,5%–97,5%: [0.47487; 0.49777].

Ressalvas da secundária:

- Dias sem notícia dão score empatado: o top 5 desses dias sai em ordem alfabética de ticker.
- No período sem coleta (NaN de `noticias_dia_qtd`, jan–jul/2025), o AUC é 0,5 exato.
- Não é recorte: os números misturam dias com e sem notícia.

