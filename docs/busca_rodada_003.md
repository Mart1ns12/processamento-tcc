# Busca pelo melhor modelo, rodada 003

Exploratório: `treino.modelo_oficial` é false.

Não constitui recomendação de investimento.

## Identificação

- Data: 2026-11-06; motivo: Rodada 3 oficial (D5 revista): busca com o conjunto congelado da rodada 3 do protocolo (so bloco A); conferencia em docs/conferencia_rodada_003.md
- Rodada do protocolo de origem: 3
- Dataset: dataset-todas-2026-11-06.csv, sha256 c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa
- versao_preparacao: 7; semente: 20261023
- sha_parametros: 2af43f4004c8ed1acb3c7a32b7da4a9c7af470339abf147949dededf51f5ba96; sha_regras: dd967e28c1eb71f5d8d2751264b850b68ed25d51695c697f5fcb7fdafdde7156
- sha_codigo: 0d923d64b2ca5c66b1e1725e1522f45dd97d1f1c9ce9c9607e312589af69f99a
- Versões: {'xgboost': '3.4.1', 'sklearn': '1.9.1', 'pandas': '3.1.0', 'numpy': '2.5.4'}
- Referência (ponto de partida): XGBoost {'n_estimators': 300, 'max_depth': 3, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.8, 'min_child_weight': 50, 'reg_lambda': 5}

## Candidatos contra a referência (modelo 3, critérios 1 a 4 da busca)

| Candidato | Família | Ganho | IC 99,5% | Anos positivos | Pior ano | Queda do top 5 (pontos) | Aprovado |
|---|---|---|---|---|---|---|---|
| logistica | logistica | 0.00482 | [-0.00018; 0.00981] | 6 de 6 | 0.00060 | 0.55342 | não |
| xgb_2_200 | xgb | 0.00112 | [-0.00136; 0.00370] | 4 de 6 | -0.00078 | 0.07686 | não |
| xgb_2_50 | xgb | 0.00124 | [-0.00070; 0.00315] | 5 de 6 | -0.00146 | 0.13836 | não |
| xgb_3_200 | xgb | -0.00006 | [-0.00236; 0.00229] | 3 de 6 | -0.00212 | 0.67640 | não |
| lgbm_2_200 | lgbm | 0.00126 | [-0.00138; 0.00397] | 4 de 6 | -0.00197 | 0.64566 | não |
| lgbm_2_50 | lgbm | 0.00204 | [-0.00028; 0.00449] | 6 de 6 | 0.00026 | 0.99923 | não |
| lgbm_3_200 | lgbm | 0.00025 | [-0.00221; 0.00283] | 4 de 6 | -0.00117 | 1.06072 | não |
| lgbm_3_50 | lgbm | 0.00069 | [-0.00116; 0.00264] | 5 de 6 | -0.00027 | 0.81476 | não |
| combinacao | combinação por rank (só relato) | 0.00267 | [0.00063; 0.00471] | 6 de 6 | 0.00097 | 0.38432 | não |

A combinação não pode vencer. Referência: XGBoost do ponto de partida (max_depth 3, min_child_weight 50).

## Escolha

- Vencedor: referencia
- Melhor (maior ganho entre os aprovados): nenhum
- Aprovados: nenhum
- Combinação aprovada (não vence): não
- Motivo: nenhum candidato aprovado: fica a referência

## Métricas no desenvolvimento do vencedor

- Família: xgb; hiperparâmetros: {'n_estimators': 300, 'max_depth': 3, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.8, 'min_child_weight': 50, 'reg_lambda': 5}
- Veredito: No top 5, o modelo 3 ficou acima do acaso e superou a regra da volatilidade e a logística neste período.
- Calibração: ECE 0.01560, aprovada: sim

| Modelo | Taxa de acerto do top 5 | Frente ao acaso |
|---|---|---|
| modelo_1 | 0.50515 | acima |
| modelo_3 | 0.51668 | acima |
| logistica | 0.51115 | acima |
| volatilidade | 0.49869 | acima |

| A | B | Métrica | Diferença média | IC | Dias |
|---|---|---|---|---|---|
| modelo_3 | modelo_1 | acerto_top5_dia | 0.01153 | [-0.00154; 0.02398] | 1301 |
| modelo_3 | modelo_1 | auc_dia | 0.00051 | [-0.00178; 0.00287] | 1301 |
| modelo_3 | logistica | acerto_top5_dia | 0.00553 | [-0.00846; 0.01968] | 1301 |
| modelo_3 | logistica | auc_dia | -0.00482 | [-0.00821; -0.00129] | 1301 |
| modelo_3 | volatilidade | acerto_top5_dia | 0.01799 | [-0.00169; 0.03689] | 1301 |
| modelo_3 | volatilidade | auc_dia | 0.00414 | [-0.00195; 0.01051] | 1301 |

## Todas as tentativas da busca

| Rodada | Situação | Vencedor | sha do resultado | Repete rodada | Não reproduziu |
|---|---|---|---|---|---|
| 1 | concluida | logistica | 777c527b54d99263de9512e41a567fbbdc5acb78f215f6193cc86dddd0d4d61f | n/d |  |
| 2 | concluida | logistica | 777c527b54d99263de9512e41a567fbbdc5acb78f215f6193cc86dddd0d4d61f | 1 |  |
| 3 | esta rodada | n/d | n/d | n/d |  |
