# Busca pelo melhor modelo, rodada 005

Exploratório: `treino.modelo_oficial` é false.

Não constitui recomendação de investimento.

## Identificação

- Data: 2026-11-09; motivo: Rodada 5 oficial: busca com o conjunto congelado da rodada 5 do protocolo; conferencia em docs/conferencia_rodada_005.md
- Rodada do protocolo de origem: 5
- Dataset: dataset-todas-2026-11-09.csv, sha256 9f520c5fa7e91ebbb2a624a6cbb89d4caf33d8bb57ca3018be89ac43016e9928
- versao_preparacao: 7; semente: 20261023
- sha_parametros: 04ce153d729f35a3f3118dba48f6d616e65ca94afa4f3d49dea94bb285334023; sha_regras: dd967e28c1eb71f5d8d2751264b850b68ed25d51695c697f5fcb7fdafdde7156
- sha_codigo: 8f533e57f9243941d1d0b6adc9135423664f12d3b2e3033049f529b007f43707
- Versões: {'xgboost': '3.4.1', 'sklearn': '1.9.1', 'pandas': '3.1.0', 'numpy': '2.5.4'}
- Referência (ponto de partida): XGBoost {'n_estimators': 300, 'max_depth': 3, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.8, 'min_child_weight': 50, 'reg_lambda': 5}

## Candidatos contra a referência (modelo 3, critérios 1 a 4 da busca)

| Candidato | Família | Ganho | IC 99,5% | Anos positivos | Pior ano | Queda do top 5 (pontos) | Aprovado |
|---|---|---|---|---|---|---|---|
| logistica | logistica | 0.00453 | [-0.00058; 0.00933] | 6 de 6 | 0.00007 | -0.06149 | não |
| xgb_2_200 | xgb | 0.00092 | [-0.00180; 0.00375] | 3 de 6 | -0.00276 | -0.04612 | não |
| xgb_2_50 | xgb | 0.00125 | [-0.00074; 0.00328] | 4 de 6 | -0.00205 | -0.98386 | não |
| xgb_3_200 | xgb | -0.00034 | [-0.00282; 0.00221] | 2 de 6 | -0.00417 | -0.27671 | não |
| lgbm_2_200 | lgbm | 0.00088 | [-0.00196; 0.00372] | 3 de 6 | -0.00170 | 0.19985 | não |
| lgbm_2_50 | lgbm | 0.00142 | [-0.00095; 0.00374] | 4 de 6 | -0.00166 | 0.33820 | não |
| lgbm_3_200 | lgbm | 0.00010 | [-0.00246; 0.00273] | 3 de 6 | -0.00363 | 0.10761 | não |
| lgbm_3_50 | lgbm | 0.00054 | [-0.00144; 0.00255] | 4 de 6 | -0.00201 | 0.16910 | não |
| combinacao | combinação por rank (só relato) | 0.00286 | [0.00078; 0.00487] | 6 de 6 | 0.00038 | -0.38432 | não |

A combinação não pode vencer. Referência: XGBoost do ponto de partida (max_depth 3, min_child_weight 50).

## Escolha

- Vencedor: referencia
- Melhor (maior ganho entre os aprovados): nenhum
- Aprovados: nenhum
- Combinação aprovada (não vence): não
- Motivo: nenhum candidato aprovado: fica a referência

## Métricas no desenvolvimento do vencedor

- Família: xgb; hiperparâmetros: {'n_estimators': 300, 'max_depth': 3, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.8, 'min_child_weight': 50, 'reg_lambda': 5}
- Veredito: No top 5, o modelo 3 ficou acima do acaso, superou a regra da volatilidade (0,5099 × 0,4987), mas não superou a logística (0,5099 × 0,5105); no AUC por pregão, superou a regra da volatilidade (0,5168 × 0,5124), mas não superou a logística (0,5168 × 0,5213) neste período.
- Calibração: ECE 0.01369, aprovada: sim

| Modelo | Taxa de acerto do top 5 | Frente ao acaso |
|---|---|---|
| modelo_1 | 0.51376 | acima |
| modelo_3 | 0.50992 | acima |
| logistica | 0.51053 | acima |
| volatilidade | 0.49869 | acima |

| A | B | Métrica | Diferença média | IC | Dias |
|---|---|---|---|---|---|
| modelo_3 | modelo_1 | acerto_top5_dia | -0.00384 | [-0.01660; 0.00922] | 1301 |
| modelo_3 | modelo_1 | auc_dia | 0.00046 | [-0.00199; 0.00286] | 1301 |
| modelo_3 | logistica | acerto_top5_dia | -0.00061 | [-0.01400; 0.01276] | 1301 |
| modelo_3 | logistica | auc_dia | -0.00453 | [-0.00796; -0.00098] | 1301 |
| modelo_3 | volatilidade | acerto_top5_dia | 0.01122 | [-0.00631; 0.02936] | 1301 |
| modelo_3 | volatilidade | auc_dia | 0.00441 | [-0.00154; 0.01074] | 1301 |

## Todas as tentativas da busca

| Rodada | Situação | Vencedor | sha do resultado | Repete rodada | Não reproduziu |
|---|---|---|---|---|---|
| 1 | concluida | logistica | 777c527b54d99263de9512e41a567fbbdc5acb78f215f6193cc86dddd0d4d61f | n/d |  |
| 2 | concluida | logistica | 777c527b54d99263de9512e41a567fbbdc5acb78f215f6193cc86dddd0d4d61f | 1 |  |
| 3 | concluida | referencia | 9f9c5f74dc5d64f631d0a614fec962ffc3af465a3a30c74f0c1b2adc4568ac69 | n/d |  |
| 4 | concluida | referencia | 9f9c5f74dc5d64f631d0a614fec962ffc3af465a3a30c74f0c1b2adc4568ac69 | 3 |  |
| 5 | esta rodada | n/d | n/d | n/d |  |
