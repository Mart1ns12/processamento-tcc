# Busca pelo melhor modelo, rodada 002

Exploratório: `treino.modelo_oficial` é false.

Não constitui recomendação de investimento.

## Identificação

- Data: 2026-10-30; motivo: Repeticao_para_conferir_determinismo
- Rodada do protocolo de origem: 1
- Dataset: dataset-todas-2026-10-30.csv, sha256 741e781122d073e0f8fdab363998e34e39fa4f811d19c00a04412dedf548c980
- versao_preparacao: 6; semente: 20261023
- sha_parametros: d3cee30e3cb8b1b5595be7d0d4f7901f9a4188eab304867d6747b0a6a0360e35; sha_regras: dd967e28c1eb71f5d8d2751264b850b68ed25d51695c697f5fcb7fdafdde7156
- sha_codigo: cf0956f9c62f0aa2d90b5b4ba5a88ee9d4b7959ff432e128756781b65c6b3216
- Versões: {'xgboost': '3.4.1', 'sklearn': '1.9.1', 'pandas': '3.1.0', 'numpy': '2.5.4'}
- Referência (ponto de partida): XGBoost {'n_estimators': 300, 'max_depth': 3, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.8, 'min_child_weight': 50, 'reg_lambda': 5}

## Candidatos contra a referência (modelo 3, critérios 1 a 4 da busca)

| Candidato | Família | Ganho | IC 99,5% | Anos positivos | Pior ano | Queda do top 5 (pontos) | Aprovado |
|---|---|---|---|---|---|---|---|
| logistica | logistica | 0.00575 | [0.00055; 0.01092] | 5 de 6 | -0.00103 | 0.07686 | sim |
| xgb_2_200 | xgb | 0.00273 | [-0.00007; 0.00558] | 5 de 6 | -0.00088 | 0.00000 | não |
| xgb_2_50 | xgb | 0.00213 | [-0.00021; 0.00450] | 5 de 6 | -0.00129 | -0.32283 | não |
| xgb_3_200 | xgb | 0.00107 | [-0.00130; 0.00332] | 4 de 6 | -0.00244 | 0.01537 | não |
| lgbm_2_200 | lgbm | 0.00309 | [0.00022; 0.00600] | 5 de 6 | -0.00158 | -0.73789 | não |
| lgbm_2_50 | lgbm | 0.00264 | [0.00016; 0.00519] | 5 de 6 | -0.00075 | -0.66103 | não |
| lgbm_3_200 | lgbm | 0.00083 | [-0.00191; 0.00353] | 3 de 6 | -0.00262 | -0.52267 | não |
| lgbm_3_50 | lgbm | 0.00107 | [-0.00102; 0.00320] | 4 de 6 | -0.00083 | -0.83013 | não |
| combinacao | combinação por rank (só relato) | 0.00370 | [0.00150; 0.00590] | 6 de 6 | 0.00230 | -0.99923 | não |

A combinação não pode vencer. Referência: XGBoost do ponto de partida (max_depth 3, min_child_weight 50).

## Escolha

- Vencedor: logistica
- Melhor (maior ganho entre os aprovados): logistica
- Aprovados: logistica
- Combinação aprovada (não vence): não
- Motivo: logistica tem o maior ganho e nenhum mais simples fica sem diferença clara
- A logística venceu: a referência logística passa a ser o XGBoost do ponto de partida.

## Métricas no desenvolvimento do vencedor

- Família: logistica; hiperparâmetros: None
- Veredito: No top 5, o modelo 3 ficou acima do acaso, mas não superou a logística.
- Calibração: ECE 0.00661, aprovada: sim

| Modelo | Taxa de acerto do top 5 | Frente ao acaso |
|---|---|---|
| modelo_1 | 0.51284 | acima |
| modelo_3 | 0.50945 | acima |
| logistica | 0.51022 | acima |
| volatilidade | 0.49869 | acima |

| A | B | Métrica | Diferença média | IC | Dias |
|---|---|---|---|---|---|
| modelo_3 | modelo_1 | acerto_top5_dia | -0.00338 | [-0.01184; 0.00523] | 1301 |
| modelo_3 | modelo_1 | auc_dia | -0.00040 | [-0.00201; 0.00118] | 1301 |
| modelo_3 | logistica | acerto_top5_dia | -0.00077 | [-0.01430; 0.01338] | 1301 |
| modelo_3 | logistica | auc_dia | 0.00575 | [0.00205; 0.00943] | 1301 |
| modelo_3 | volatilidade | acerto_top5_dia | 0.01076 | [-0.00692; 0.02967] | 1301 |
| modelo_3 | volatilidade | auc_dia | 0.00864 | [0.00207; 0.01531] | 1301 |

## Todas as tentativas da busca

| Rodada | Situação | Vencedor | sha do resultado | Repete rodada | Não reproduziu |
|---|---|---|---|---|---|
| 1 | concluida | logistica | 777c527b54d99263de9512e41a567fbbdc5acb78f215f6193cc86dddd0d4d61f | n/d |  |
| 2 | esta rodada | n/d | n/d | n/d |  |
