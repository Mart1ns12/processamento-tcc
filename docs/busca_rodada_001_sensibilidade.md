# Sensibilidade da rodada 001: exploratório

**Exploratório.** `modelo_oficial`: false. Não muda hipótese, configuração congelada nem teste final. Não constitui recomendação de investimento.

- Contagem declarada à parte do protocolo: 4 análises e 7 escopos. Não entra em `docs/protocolo_tentativas.jsonl`.
- IC sem ajuste por múltiplas comparações.
- Só desenvolvimento (`treino.ler_desenvolvimento`): sem banco, sem teste final e sem gravar em modelos/.

## Identificação

- Dataset todas: `dataset-todas-2026-10-30.csv`; sha256 `741e781122d073e0f8fdab363998e34e39fa4f811d19c00a04412dedf548c980`; versao_preparacao 6; 92267 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Dataset principais: `dataset-principais-2026-10-30.csv`; sha256 `434f34bb808ea6ce88fc599b45dc04b8fec9dc2004eb42840fd6db652952c33e`; versao_preparacao 6; 92267 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Dataset hora_real_noite: `dataset-hora_real_noite-2026-10-30.csv`; sha256 `80fa10f3627568d81b89f99fd1e0963f706732ba3169d1a6655c04c1ae64b4db`; versao_preparacao 6; 92267 linhas; 1361 pregões; 2021-01-04 a 2026-06-19
- Data: 2026-10-30; semente: 20261023; top principal: 5; dobras walk-forward: 63; rodada congelada: 1
- sha_parametros: `d3cee30e3cb8b1b5595be7d0d4f7901f9a4188eab304867d6747b0a6a0360e35`; versões: {'xgboost': '3.4.1', 'sklearn': '1.9.1', 'pandas': '3.1.0', 'numpy': '2.5.4'}
- Colunas do modelo 1: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas do modelo 3: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas de notícia (análise d): noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom
- IC 95%: bloco de 5 pregões, 2000 reamostragens, percentis 2,5 e 97,5
- IC 99,5%: bloco de 5 pregões, 10000 reamostragens, percentis 0,25 e 99,75

## (a) Recorte com ≥ 1 notícia: modelo 1 × modelo 3 (dataset todas)

Treino em todas as linhas; avaliação só no recorte (`noticias_dia_qtd` bruto >= 1).

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 50311; dias: 1156; dias com AUC: 1156

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.51935 | 0.51901 | -0.00035 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01145; 0.02683] | [0.01141; 0.02613] | [-0.00309; 0.00253] |
| IC 99,5% (idem) | [0.00844; 0.02972] | [0.00798; 0.02924] | [-0.00439; 0.00375] |
| Top 5: taxa de acerto | 0.51436 | 0.51280 | -0.00156 |
| Top 5: acertos / dias | 2973 / 1156 | 2964 / 1156 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.01090; 0.00813] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1156 dias): média 0.48474; faixa 2,5%–97,5%: [0.47266; 0.49654].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00180 |
| 2022 | 250 | -0.00011 |
| 2023 | 248 | -0.00042 |
| 2024 | 251 | 0.00017 |
| 2025 | 105 | -0.00682 |
| 2026 | 115 | 0.00640 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 41.10 | 0 |
| 2022 | 250 | 47.24 | 0 |
| 2023 | 248 | 29.21 | 0 |
| 2024 | 251 | 40.57 | 0 |
| 2025 | 105 | 56.91 | 0 |
| 2026 | 115 | 64.45 | 0 |

## (b) Dataset principais: modelo 3 treinado no dataset principais × modelo 1 de todas

### Todas as linhas

- Linhas: 88841; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.52151 | 0.52227 | 0.00076 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01524; 0.02764] | [0.01625; 0.02824] | [-0.00102; 0.00259] |
| IC 99,5% (idem) | [0.01291; 0.03072] | [0.01398; 0.03083] | [-0.00173; 0.00331] |
| Top 5: taxa de acerto | 0.51284 | 0.52145 | 0.00861 |
| Top 5: acertos / dias | 3336 / 1301 | 3392 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00077; 0.01752] |

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00121 |
| 2022 | 250 | -0.00079 |
| 2023 | 248 | 0.00047 |
| 2024 | 251 | 0.00160 |
| 2025 | 250 | -0.00046 |
| 2026 | 115 | 0.00484 |

### Recorte ≥ 1 notícia (qtd bruta da própria versão)

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 35065; dias: 1156; dias com AUC: 1156

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.52318 | 0.52609 | 0.00291 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01388; 0.03170] | [0.01696; 0.03458] | [-0.00142; 0.00740] |
| IC 99,5% (idem) | [0.01026; 0.03599] | [0.01298; 0.03857] | [-0.00351; 0.00930] |
| Top 5: taxa de acerto | 0.51384 | 0.51955 | 0.00571 |
| Top 5: acertos / dias | 2970 / 1156 | 3003 / 1156 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00519; 0.01592] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (1156 dias): média 0.48564; faixa 2,5%–97,5%: [0.47405; 0.49706].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | 0.00198 |
| 2022 | 250 | 0.00020 |
| 2023 | 248 | 0.00413 |
| 2024 | 251 | 0.00523 |
| 2025 | 105 | -0.00362 |
| 2026 | 115 | 0.00857 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 29.18 | 0 |
| 2022 | 250 | 30.84 | 0 |
| 2023 | 248 | 18.62 | 0 |
| 2024 | 251 | 29.54 | 0 |
| 2025 | 105 | 41.17 | 0 |
| 2026 | 115 | 48.22 | 0 |

## (c) Dataset hora_real_noite: modelo 3 treinado no dataset hora_real_noite × modelo 1 de todas

**Cobertura baixa**: a tabela de papéis por dia por ano no recorte mostra quantos papéis cada dia tem; o top 5 depende de dias com ao menos 5 papéis.

### Todas as linhas

- Linhas: 88841; dias: 1301; dias com AUC: 1301

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.52151 | 0.52072 | -0.00079 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.01524; 0.02764] | [0.01449; 0.02687] | [-0.00173; 0.00005] |
| IC 99,5% (idem) | [0.01291; 0.03072] | [0.01201; 0.02994] | [-0.00208; 0.00045] |
| Top 5: taxa de acerto | 0.51284 | 0.51268 | -0.00015 |
| Top 5: acertos / dias | 3336 / 1301 | 3335 / 1301 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00646; 0.00615] |

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00120 |
| 2022 | 250 | -0.00264 |
| 2023 | 248 | 0.00054 |
| 2024 | 251 | -0.00105 |
| 2025 | 250 | -0.00033 |
| 2026 | 115 | 0.00065 |

### Recorte ≥ 1 notícia (qtd bruta da própria versão)

Dias perdidos pela regra de dia curto (por ano): 2023: 142; 2024: 107; 2025: 68; 2026: 53.

- Linhas: 14535; dias: 720; dias com AUC: 720

| Métrica | modelo 1 | modelo 3 | Diferença (3 − 1) |
|---|---|---|---|
| AUC médio por pregão | 0.52360 | 0.52162 | -0.00198 |
| IC 95% (AUC − 0,5 nos modelos; ganho na diferença) | [0.00799; 0.03947] | [0.00560; 0.03845] | [-0.00757; 0.00377] |
| IC 99,5% (idem) | [0.00106; 0.04649] | [-0.00161; 0.04465] | [-0.00985; 0.00634] |
| Top 5: taxa de acerto | 0.51333 | 0.51306 | -0.00028 |
| Top 5: acertos / dias | 1848 / 720 | 1847 / 720 | – |
| IC 95% do top 5 diário (diferença) | – | – | [-0.00945; 0.00862] |
| Top 5 frente ao acaso | acima do acaso | acima do acaso | – |

Acaso do top 5 no mesmo recorte (720 dias): média 0.49577; faixa 2,5%–97,5%: [0.48306; 0.50861].

Ganho (AUC, 3 − 1) e pregões por ano:

| Ano | Pregões | Ganho |
|---|---|---|
| 2021 | 187 | -0.00371 |
| 2022 | 250 | -0.00721 |
| 2023 | 86 | -0.00462 |
| 2024 | 137 | 0.00570 |
| 2025 | 22 | -0.00439 |
| 2026 | 38 | 0.02055 |

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 23.65 | 0 |
| 2022 | 250 | 29.33 | 0 |
| 2023 | 228 | 4.39 | 142 |
| 2024 | 244 | 5.78 | 107 |
| 2025 | 90 | 3.44 | 68 |
| 2026 | 91 | 11.24 | 53 |

## (d) Só notícias: logística com `preparacao.NOTICIAS_DIA` (dataset todas)

Sem comparação contra o modelo 1. A referência é o acaso: AUC 0,5 e a faixa do top 5.

### Principal: recorte ≥ 1 notícia

Dias perdidos pela regra de dia curto: nenhum.

- Linhas: 50311; dias: 1156; dias com AUC: 1156

| Métrica | Valor |
|---|---|
| AUC médio por pregão | 0.50648 |
| AUC − 0,5 (referência do acaso: 0,5) | 0.00648 |
| IC 95% de AUC − 0,5 | [-0.00076; 0.01317] |
| IC 99,5% de AUC − 0,5 | [-0.00315; 0.01612] |
| Top 5: taxa de acerto | 0.50502 |
| Top 5: acertos / dias | 2919 / 1156 |
| Top 5 frente ao acaso | acima do acaso |

Acaso do top 5 (1156 dias): média 0.48474; faixa 2,5%–97,5%: [0.47266; 0.49654].

Cobertura no recorte (antes da regra de dia curto):

| Ano | Dias no recorte | Papéis por dia (média) | Dias perdidos |
|---|---|---|---|
| 2021 | 187 | 41.10 | 0 |
| 2022 | 250 | 47.24 | 0 |
| 2023 | 248 | 29.21 | 0 |
| 2024 | 251 | 40.57 | 0 |
| 2025 | 105 | 56.91 | 0 |
| 2026 | 115 | 64.45 | 0 |

### Secundária: todas as linhas

- Linhas: 88841; dias: 1301; dias com AUC: 1301

| Métrica | Valor |
|---|---|
| AUC médio por pregão | 0.50346 |
| AUC − 0,5 (referência do acaso: 0,5) | 0.00346 |
| IC 95% de AUC − 0,5 | [-0.00109; 0.00781] |
| IC 99,5% de AUC − 0,5 | [-0.00260; 0.00983] |
| Top 5: taxa de acerto | 0.50561 |
| Top 5: acertos / dias | 3289 / 1301 |
| Top 5 frente ao acaso | acima do acaso |

Acaso do top 5 (1301 dias): média 0.48596; faixa 2,5%–97,5%: [0.47425; 0.49762].

Ressalvas da secundária:

- Dias sem notícia dão score empatado: o top 5 desses dias sai em ordem alfabética de ticker.
- No período sem coleta (NaN de `noticias_dia_qtd`, jan–jul/2025), o AUC é 0,5 exato.
- Não é recorte: os números misturam dias com e sem notícia.

