# Sensibilidade: rodada 1 × rodada 3 (exploratório)

Registrado em 08/11/2026. As fontes são `docs/busca_rodada_001_sensibilidade.md` e `docs/busca_rodada_003_sensibilidade.md`. Nenhuma das duas entra em `docs/protocolo_tentativas.jsonl`, e os IC não têm ajuste por comparações múltiplas. Não constitui recomendação de investimento.

| Item | Rodada 1 | Rodada 3 |
|---|---|---|
| Família | Logística | XGBoost 3/50 (configuração final 003) |
| Dataset `todas` | v6, `741e781122d0…` | v7, `c954b437c55e…` |
| Colunas | Congelado 001 (bloco A) | Congelado 003 (bloco A, as mesmas colunas) |

**Conferência:** o modelo 1 de `todas` na rodada 3 tem AUC médio por pregão 0,5159763261127491, idêntico ao da busca 003. São as mesmas previsões.

## Ganho das notícias (AUC médio por pregão, modelo 3 − modelo 1; IC 95%)

| Caso | Rodada 1 | Rodada 3 |
|---|---|---|
| Principal, todas as linhas (busca) | −0,00040 [−0,00201; 0,00118] | +0,00051 [−0,00178; 0,00287] |
| (a) Recorte com ≥ 1 notícia | −0,00035 [−0,00309; 0,00253] | +0,00154 [−0,00125; 0,00431] |
| (b) `principais`, todas as linhas | +0,00076 [−0,00102; 0,00259] | +0,00067 [−0,00200; 0,00315] |
| (b) `principais`, recorte | +0,00291 [−0,00142; 0,00740] | +0,00007 [−0,00432; 0,00408] |
| (c) `hora_real_noite`, todas as linhas | −0,00079 [−0,00173; 0,00005] | +0,00041 [−0,00167; 0,00259] |
| (c) `hora_real_noite`, recorte | −0,00198 [−0,00757; 0,00377] | +0,00048 [−0,00330; 0,00435] |

## Top 5 (taxa de acerto, modelo 3 − modelo 1, em pontos percentuais)

| Caso | Rodada 1 | Rodada 3 |
|---|---|---|
| (a) Recorte | −0,16 | +0,40 (IC 95% [−0,88; +1,68]) |
| (b) Todas as linhas / recorte | +0,86 / +0,57 | +0,75 / +0,02 |
| (c) Todas as linhas / recorte | −0,02 / −0,03 | +1,57 / +0,02 |

## (d) Só notícias (as 4 colunas de notícia sozinhas)

| Medida | Rodada 1 (logística) | Rodada 3 (XGBoost) |
|---|---|---|
| AUC, recorte (principal) | 0,50648, IC 95% de AUC − 0,5 [−0,00076; 0,01317] | 0,50397 [−0,00088; 0,00874] |
| AUC, todas as linhas | 0,50346 [−0,00109; 0,00781] | 0,50293 [−0,00137; 0,00712] |
| Top 5 no recorte | 0,50502, acima do acaso | 0,49547, **dentro** da faixa do acaso [0,47533; 0,49808] |
| Top 5 em todas as linhas | 0,50561, acima do acaso | 0,49408, **dentro** da faixa [0,47486; 0,49777] |

**Leitura.** Nas duas rodadas, nenhum caso tem IC 95% do ganho acima de zero. Na rodada 3, todos os ganhos de AUC são positivos, mas pequenos (até +0,0015). As notícias sozinhas ficam perto de 0,5 de AUC, e o top 5 delas não se distingue do acaso.
