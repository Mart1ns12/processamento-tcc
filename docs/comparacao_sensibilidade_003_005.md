# Sensibilidade: rodada 3 × rodada 5 (exploratório)

Registrado em 10/11/2026. As fontes são `docs/busca_rodada_003_sensibilidade.md` e `docs/busca_rodada_005_sensibilidade.md`. Nenhuma das duas entra em `docs/protocolo_tentativas.jsonl`, e os IC não têm ajuste por comparações múltiplas. Não constitui recomendação de investimento.

| Item | Rodada 3 | Rodada 5 |
|---|---|---|
| Família | XGBoost 3/50 (configuração final 003) | XGBoost 3/50 (configuração final 005, mesmos hiperparâmetros) |
| Dataset `todas` | v7, `c954b437c55e…` | v7, `9f520c5fa7e9…` |
| `principais` / `hora_real_noite` | `ca7d5bd161d1…` / `d1909b4f5a6c…` | `bc7797c95937…` / `ca6f9e3eff04…` |
| Colunas | Congelado 003 (bloco A) | Congelado 005 (as mesmas colunas) |

**Conferência:** o modelo 1 de `todas` na rodada 5 tem AUC médio por pregão 0,5163000547795387, idêntico ao `final.modelos.modelo_1.auc_medio_pregao` da busca 005. São as mesmas previsões.

## Ganho das notícias (AUC médio por pregão, modelo 3 − modelo 1; IC 95%)

| Caso | Rodada 3 | Rodada 5 |
|---|---|---|
| Principal, todas as linhas (busca) | +0,00051 [−0,00178; 0,00287] | +0,00046 [−0,00199; 0,00286] |
| (a) Recorte com ≥ 1 notícia | +0,00154 [−0,00125; 0,00431] | +0,00148 [−0,00146; 0,00442] |
| (b) `principais`, todas as linhas | +0,00067 [−0,00200; 0,00315] | +0,00052 [−0,00208; 0,00301] |
| (b) `principais`, recorte | +0,00007 [−0,00432; 0,00408] | +0,00147 [−0,00287; 0,00564] |
| (c) `hora_real_noite`, todas as linhas | +0,00041 [−0,00167; 0,00259] | +0,00045 [−0,00177; 0,00255] |
| (c) `hora_real_noite`, recorte | +0,00048 [−0,00330; 0,00435] | +0,00020 [−0,00383; 0,00428] |

## Top 5 (taxa de acerto, modelo 3 − modelo 1, em pontos percentuais)

| Caso | Rodada 3 | Rodada 5 |
|---|---|---|
| Principal, todas as linhas (busca) | +1,15 (IC 95% [−0,15; +2,40]) | −0,38 (IC 95% [−1,66; +0,92]) |
| (a) Recorte | +0,40 (IC 95% [−0,88; +1,68]) | +0,75 (IC 95% [−0,40; +1,97]) |
| (b) Todas as linhas / recorte | +0,75 / +0,02 | −0,78 / +0,25 |
| (c) Todas as linhas / recorte | +1,57 / +0,02 | +0,17 / +0,29 |

## (d) Só notícias (as 4 colunas de notícia sozinhas, XGBoost)

| Medida | Rodada 3 | Rodada 5 |
|---|---|---|
| AUC, recorte (principal), IC 95% de AUC − 0,5 | 0,50397 [−0,00088; 0,00874] | 0,50397 [−0,00105; 0,00870] |
| AUC, todas as linhas | 0,50293 [−0,00137; 0,00712] | 0,50378 [−0,00059; 0,00795] |
| Top 5 no recorte | 0,49547, dentro da faixa do acaso [0,47533; 0,49808] | 0,48978, dentro da faixa [0,47532; 0,49823] |
| Top 5 em todas as linhas | 0,49408, dentro da faixa [0,47486; 0,49777] | 0,48839, dentro da faixa [0,47487; 0,49777] |

**Leitura.** O resultado da rodada 3 se mantém no AUC. Nas duas rodadas, nenhum caso tem IC 95% do ganho acima de zero, e todos os ganhos de AUC são positivos e pequenos (até +0,0015). As notícias sozinhas ficam perto de 0,5 de AUC, e o top 5 delas não se distingue do acaso. O top 5 é a parte instável: na linha principal e no caso (b) com todas as linhas, a diferença do modelo 3 sobre o 1 trocou de sinal entre as rodadas (+1,15 para −0,38 pp e +0,75 para −0,78 pp), sempre com IC contendo o zero. A medida primária (D3) é o AUC por pregão, e ela quase não mudou.
