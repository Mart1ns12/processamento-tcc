# Comparação das rodadas 3 e 5 (protocolo e busca)

Registrado em 10/11/2026, depois da busca da rodada 5 e antes da sensibilidade. **Exploratório:** `treino.modelo_oficial` é false. Não constitui recomendação de investimento. Fontes: `docs/protocolo_rodada_003.md`, `docs/protocolo_rodada_005.md`, `docs/busca_rodada_003.md`, `docs/busca_rodada_005.md`. A rodada 4 repetiu a 3 com as mesmas entradas e reproduziu o resultado.

| Item | Rodada 3 | Rodada 5 |
|---|---|---|
| Dataset | v7, `c954b437c55e…`, 94.485 linhas | v7, `9f520c5fa7e9…`, 94.485 linhas (conferência em `docs/conferencia_rodada_005.md`) |
| `sha_regras` (protocolo / busca) | `e275d3d6e8f1…` / `dd967e28c1eb…` | iguais |
| `sha_parametros` | `2af43f4004c8…` | `04ce153d729f…` (`treino.familia_producao: "xgb"`, depois da rodada 4) |
| Colunas congeladas (`colunas_1`, `colunas_3`) e hiperparâmetros | | iguais aos da rodada 3 |
| Configuração final | `configuracao_final_rodada_003.json` | `configuracao_final_rodada_005.json`: mesma família e hiperparâmetros; mudam só o dataset e as rodadas de origem |

## Protocolo: critérios por bloco

Ganho de AUC médio por pregão contra a base. C1: ganho > 0,005. C2: IC 99% acima de 0. C3: ≥ 4 de 6 anos positivos e nenhum abaixo de −0,005. C4: queda do top 5 ≤ 0,5 pp. C5: ganho em 2024 (só bloco E).

| Bloco | Rodada | Ganho | IC 99% | Anos + | Pior ano | Queda top 5 (pp) | 2024 | C1 | C2 | C3 | C4 | C5 | Aprovado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Controle | 3 | 0,00013 | [−0,00200; 0,00238] | 4 | −0,00196 | 0,63 | 0,00172 | não | não | sim | não | – | não |
| Controle | 5 | −0,00006 | [−0,00217; 0,00211] | 2 | −0,00195 | 0,91 | 0,00168 | não | não | não | não | – | não |
| A. Preço | 3 | 0,00881 | [0,00327; 0,01441] | 6 | 0,00029 | −1,14 | 0,00692 | sim | sim | sim | sim | – | **sim** |
| A. Preço | 5 | 0,00857 | [0,00290; 0,01389] | 5 | −0,00157 | −1,18 | 0,00547 | sim | sim | sim | sim | – | **sim** |
| B. Contexto | 3 | −0,00178 | [−0,00586; 0,00246] | 2 | −0,00474 | 0,12 | 0,00035 | não | não | não | sim | – | não |
| B. Contexto | 5 | −0,00235 | [−0,00671; 0,00189] | 2 | −0,00732 | 0,94 | 0,00215 | não | não | não | não | – | não |
| C. Balanço | 3 | 0,00191 | [−0,00241; 0,00606] | 4 | −0,00232 | −0,91 | 0,00337 | não | não | sim | sim | – | não |
| C. Balanço | 5 | 0,00256 | [−0,00153; 0,00651] | 3 | −0,00159 | 0,14 | 0,00484 | não | não | não | sim | – | não |
| D. Valor | 3 | 0,00039 | [−0,00232; 0,00310] | 3 | −0,00139 | −0,61 | 0,00233 | não | não | não | sim | – | não |
| D. Valor | 5 | 0,00019 | [−0,00263; 0,00304] | 4 | −0,00248 | 0,49 | 0,00189 | não | não | sim | sim | – | não |
| E. Notícias | 3 | 0,00040 | [−0,00222; 0,00316] | 4 | −0,00317 | −0,42 | −0,00317 | não | não | sim | sim | não | não |
| E. Notícias | 5 | 0,00034 | [−0,00240; 0,00308] | 4 | −0,00271 | −0,42 | −0,00271 | não | não | sim | sim | não | não |

**Resultado:** nas duas rodadas, só o bloco A foi adotado e o controle foi reprovado. As colunas congeladas são as mesmas. Na rodada 5, o bloco A teve 2026 negativo (−0,00157, 115 pregões), dentro do limite de −0,005 do C3.

## Busca: candidatos contra a referência (XGBoost 3/50, modelo 3)

C1: ganho > 0,005. C2: IC 99,5% acima de 0. C3: ≥ 4 de 6 anos positivos e nenhum abaixo de −0,005. C4: queda do top 5 ≤ 0,5 pp.

| Candidato | Rodada 3: ganho | IC 99,5% | Anos + | Queda top 5 | Rodada 5: ganho | IC 99,5% | Anos + | Pior ano | Queda top 5 | Aprovado (3 / 5) |
|---|---|---|---|---|---|---|---|---|---|---|
| Logística | 0,00482 | [−0,00018; 0,00981] | 6 | 0,55 | 0,00453 | [−0,00058; 0,00933] | 6 | 0,00007 | −0,06 | não / não (C1, C2) |
| XGBoost 2/200 | 0,00112 | [−0,00136; 0,00370] | 4 | 0,08 | 0,00092 | [−0,00180; 0,00375] | 3 | −0,00276 | −0,05 | não / não |
| XGBoost 2/50 | 0,00124 | [−0,00070; 0,00315] | 5 | 0,14 | 0,00125 | [−0,00074; 0,00328] | 4 | −0,00205 | −0,98 | não / não |
| XGBoost 3/200 | −0,00006 | [−0,00236; 0,00229] | 3 | 0,68 | −0,00034 | [−0,00282; 0,00221] | 2 | −0,00417 | −0,28 | não / não |
| LightGBM 2/200 | 0,00126 | [−0,00138; 0,00397] | 4 | 0,65 | 0,00088 | [−0,00196; 0,00372] | 3 | −0,00170 | 0,20 | não / não |
| LightGBM 2/50 | 0,00204 | [−0,00028; 0,00449] | 6 | 1,00 | 0,00142 | [−0,00095; 0,00374] | 4 | −0,00166 | 0,34 | não / não |
| LightGBM 3/200 | 0,00025 | [−0,00221; 0,00283] | 4 | 1,06 | 0,00010 | [−0,00246; 0,00273] | 3 | −0,00363 | 0,11 | não / não |
| LightGBM 3/50 | 0,00069 | [−0,00116; 0,00264] | 5 | 0,81 | 0,00054 | [−0,00144; 0,00255] | 4 | −0,00201 | 0,17 | não / não |
| Combinação (não pode vencer) | 0,00267 | [0,00063; 0,00471] | 6 | 0,38 | 0,00286 | [0,00078; 0,00487] | 6 | 0,00038 | −0,38 | não / não |

**Vencedor:** nas duas rodadas, a **referência (XGBoost do ponto de partida)**, porque nenhum candidato foi aprovado. A logística continua o achado "quase venceu": ganho 0,00453 (≤ 0,005) e IC 99,5% com limite inferior abaixo de 0. Na rodada 5 o top 5 dela não cai (−0,06 pp), então ela reprova só por C1 e C2.

## Modelo 3 × modelo 1 no desenvolvimento (XGBoost 3/50)

| Item | Rodada 3 | Rodada 5 |
|---|---|---|
| AUC médio por pregão, modelo 3 | 0,51649 | 0,51676 |
| AUC médio por pregão, modelo 1 | 0,51598 | 0,51630 |
| AUC geral, modelo 3 | 0,51595 | 0,51618 |
| AUC médio por pregão, logística / volatilidade | 0,52130 / 0,51235 | 0,52129 / 0,51235 |
| Ganho das notícias no AUC por pregão (3 − 1) | +0,00051 [−0,00178; 0,00287] | +0,00046 [−0,00199; 0,00286] |
| Acerto do top 5, modelo 3 × modelo 1 | 0,51668 × 0,50515 (+1,15 pp, IC [−0,15; +2,40] pp) | 0,50992 × 0,51376 (−0,38 pp, IC [−1,66; +0,92] pp) |
| Acerto do top 5, logística / volatilidade | – | 0,51053 / 0,49869 |
| Calibração (ECE) | 0,01560 | 0,01369 (aprovada) |

Os IC desta tabela são os do relatório da busca (bootstrap pareado), sem ajuste para comparações múltiplas. Nas duas rodadas o ganho das notícias no AUC é quase o mesmo e não é distinguível de zero. **O top 5 trocou de sinal:** na rodada 3 o modelo 3 acertava 1,15 pp mais que o modelo 1; na rodada 5, 0,38 pp menos. Os dois IC contêm o zero, então a diferença de top 5 entre os modelos não é distinguível de zero em nenhuma das duas rodadas. É sinal de que o top 5 é sensível a pequenas mudanças nos dados (as notícias mudaram em 34,5% das linhas, conferência seção 5), e o AUC por pregão, a medida primária (D3), é mais estável.
