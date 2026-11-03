# Anexo da busca, rodada 001: modelo 3 × modelo 1 e acaso

Exploratório: `treino.modelo_oficial` é false. Nenhum número vale como conclusão do TCC. Não constitui recomendação de investimento.

Só desenvolvimento (dataset `dataset-todas-2026-10-30.csv`, sha256 741e781122d0..., versão 6; pregões avaliados: 1.301, de 2021 a 19/06/2026). Colunas de `docs/protocolo_congelado_rodada_001.json`. Mesmas dobras e semente da busca (20261023).

Este anexo foi calculado depois da busca, a pedido do usuário, por `docs/busca_rodada_001_comparacao_tcc.py`. Não faz parte do registro de tentativas e não muda a escolha do vencedor. Números completos em `docs/busca_rodada_001_comparacao_tcc.json`.

## Modelo 3 × modelo 1

Ganho = modelo 3 − modelo 1. "Logística" é a família vencedora da busca e é a comparação do TCC. "XGBoost" é só sensibilidade, com o ponto de partida.

| Medida | Logística (vencedor) | XGBoost (sensibilidade) |
|---|---|---|
| AUC médio por pregão, modelo 1 | 0,52151 | 0,51661 |
| AUC médio por pregão, modelo 3 | 0,52111 | 0,51536 |
| Ganho de AUC | −0,00040 | −0,00126 |
| IC 95% do ganho | −0,00201 a 0,00118 | −0,00392 a 0,00135 |
| IC 99,5% do ganho | −0,00279 a 0,00186 | −0,00509 a 0,00250 |
| Top 5, modelo 1 | 51,28% (3.336 acertos) | 51,13% (3.326) |
| Top 5, modelo 3 | 50,95% (3.314 acertos) | 51,02% (3.319) |
| Diferença no top 5 (pontos) | −0,34 | −0,11 |
| IC 95% da diferença no top 5 (pontos) | −1,18 a 0,52 | −1,32 a 1,12 |

Ganho de AUC por ano:

| Família | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Logística | −0,00119 | +0,00010 | −0,00090 | −0,00106 | −0,00168 | +0,00513 |
| XGBoost | +0,00110 | −0,00090 | −0,00498 | +0,00197 | −0,00468 | +0,00258 |
| Pregões | 187 | 250 | 248 | 251 | 250 | 115 |

## Cada modelo frente ao acaso (logística)

Acaso no top 5: 10 mil sorteios nas mesmas linhas; média 48,60%, faixa de 2,5% a 97,5% de 47,43% a 49,76%. Acaso no AUC: 0,5.

| Medida | Modelo 1 | Modelo 3 |
|---|---|---|
| Top 5 | 51,28%, acima da faixa | 50,95%, acima da faixa |
| IC 95% do top 5 | 49,93% a 52,67% | 49,62% a 52,24% |
| Sorteios com taxa igual ou maior | 0 de 10 mil | 0 de 10 mil |
| IC 95% do AUC | 0,5152 a 0,5276 | 0,5151 a 0,5271 |
| IC 99,5% do AUC | 0,5129 a 0,5307 | 0,5126 a 0,5298 |
| Excesso médio por dia no top 5 | +0,035% | +0,040% |
| IC 95% do excesso | −0,019% a +0,088% | −0,014% a +0,090% |

Faixa do acaso para o excesso: −0,062% a +0,032%. O excesso não desconta custos.

Taxa de acerto do top 5 por ano:

| Modelo | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Modelo 1 | 53,37% | 49,36% | 50,00% | 54,26% | 52,08% | 46,61% |
| Modelo 3 | 52,83% | 49,68% | 50,40% | 52,27% | 51,36% | 48,00% |
