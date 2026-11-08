# Comparação das rodadas 1 e 3 (protocolo e busca)

Registrado em 08/11/2026, depois da busca da rodada 3. **Exploratório:** `treino.modelo_oficial` é false. Não constitui recomendação de investimento. Fontes: `docs/protocolo_rodada_001.md`, `docs/protocolo_rodada_003.md`, `docs/busca_rodada_001.md`, `docs/busca_rodada_003.md`. A rodada 2 repetiu a 1 com as mesmas entradas e reproduziu o resultado.

| Item | Rodada 1 | Rodada 3 |
|---|---|---|
| Dataset | v6, `741e781122d0…`, 92.267 linhas | v7, `c954b437c55e…`, 94.485 linhas |
| `sha_regras` (protocolo / busca) | `e275d3d6e8f1…` / `dd967e28c1eb…` | iguais |
| `sha_parametros` | `d3cee30e3cb8…` | `2af43f4004c8…` (`periodos_sem_coleta` vazio e lista manual) |

## Protocolo: critérios por bloco

Ganho de AUC médio por pregão contra a base. C1: ganho > 0,005. C2: IC 99% acima de 0. C3: ≥ 4 de 6 anos positivos e nenhum abaixo de −0,005. C4: queda do top 5 ≤ 0,5 pp. C5: ganho em 2024 (só bloco E).

| Bloco | Rodada | Ganho | IC 99% | Anos + | Pior ano | Queda top 5 (pp) | 2024 | C1 | C2 | C3 | C4 | C5 | Aprovado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Controle | 1 | −0,00078 | [−0,00311; 0,00153] | 2 | −0,00334 | 0,06 | 0,00077 | não | não | não | sim | – | não |
| Controle | 3 | 0,00013 | [−0,00200; 0,00238] | 4 | −0,00196 | 0,63 | 0,00172 | não | não | sim | não | – | não |
| A. Preço | 1 | 0,00768 | [0,00262; 0,01346] | 5 | −0,00429 | −1,32 | 0,00450 | sim | sim | sim | sim | – | **sim** |
| A. Preço | 3 | 0,00881 | [0,00327; 0,01441] | 6 | 0,00029 | −1,14 | 0,00692 | sim | sim | sim | sim | – | **sim** |
| B. Contexto | 1 | −0,00239 | [−0,00658; 0,00165] | 1 | −0,00420 | 0,57 | −0,00420 | não | não | não | não | – | não |
| B. Contexto | 3 | −0,00178 | [−0,00586; 0,00246] | 2 | −0,00474 | 0,12 | 0,00035 | não | não | não | sim | – | não |
| C. Balanço | 1 | 0,00086 | [−0,00304; 0,00501] | 3 | −0,00237 | −0,57 | 0,00025 | não | não | não | sim | – | não |
| C. Balanço | 3 | 0,00191 | [−0,00241; 0,00606] | 4 | −0,00232 | −0,91 | 0,00337 | não | não | sim | sim | – | não |
| D. Valor | 1 | −0,00057 | [−0,00314; 0,00200] | 2 | −0,00372 | 0,37 | −0,00002 | não | não | não | sim | – | não |
| D. Valor | 3 | 0,00039 | [−0,00232; 0,00310] | 3 | −0,00139 | −0,61 | 0,00233 | não | não | não | sim | – | não |
| E. Notícias | 1 | 0,00042 | [−0,00209; 0,00309] | 4 | −0,00191 | −0,23 | −0,00052 | não | não | sim | sim | não | não |
| E. Notícias | 3 | 0,00040 | [−0,00222; 0,00316] | 4 | −0,00317 | −0,42 | −0,00317 | não | não | sim | sim | não | não |

**Resultado:** nas duas rodadas, só o bloco A foi adotado e o controle foi reprovado. As colunas congeladas são as mesmas.

## Busca: candidatos contra a referência (XGBoost 3/50, modelo 3)

C1: ganho > 0,005. C2: IC 99,5% acima de 0. C3: ≥ 4 de 6 anos positivos e nenhum abaixo de −0,005. C4: queda do top 5 ≤ 0,5 pp.

| Candidato | Rodada 1: ganho | IC 99,5% | Queda top 5 | Aprovado | Rodada 3: ganho | IC 99,5% | Anos + | Pior ano | Queda top 5 | Aprovado |
|---|---|---|---|---|---|---|---|---|---|---|
| Logística | 0,00575 | [0,00055; 0,01092] | 0,08 | **sim** | 0,00482 | [−0,00018; 0,00981] | 6 | 0,00060 | 0,55 | não (C1, C2, C4) |
| LightGBM 2/50 | 0,00264 | [0,00016; 0,00519] | −0,66 | não | 0,00204 | [−0,00028; 0,00449] | 6 | 0,00026 | 1,00 | não |
| Combinação (não pode vencer) | 0,00370 | [0,00150; 0,00590] | −1,00 | não | 0,00267 | [0,00063; 0,00471] | 6 | 0,00097 | 0,38 | não |

Os demais candidatos (XGBoost 2/200, 2/50, 3/200; LightGBM 2/200, 3/200, 3/50) não foram aprovados em nenhuma das duas rodadas.

**Vencedor:** rodada 1, regressão logística. Rodada 3, **referência (XGBoost do ponto de partida)**, porque nenhum candidato foi aprovado.

## Modelo 3 × modelo 1 no desenvolvimento (família do vencedor)

| Item | Rodada 1 (logística) | Rodada 3 (XGBoost 3/50) |
|---|---|---|
| AUC médio por pregão, modelo 3 | 0,52111 | 0,51649 |
| AUC médio por pregão, modelo 1 | 0,52151 | 0,51598 |
| Ganho das notícias no AUC por pregão (3 − 1) | −0,00040 [−0,00201; 0,00118] | +0,00051 [−0,00178; 0,00287] |
| Acerto do top 5, modelo 3 × modelo 1 | 0,50945 × 0,51284 (−0,34 pp) | 0,51668 × 0,50515 (+1,15 pp, IC [−0,15; +2,40] pp) |
| Calibração (ECE) | 0,00661 | 0,01560 |

Os IC desta tabela são os do relatório da busca (bootstrap pareado), sem ajuste para comparações múltiplas. Nas duas rodadas o ganho das notícias não é distinguível de zero.
