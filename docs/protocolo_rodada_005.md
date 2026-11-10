# Protocolo de teste de variáveis novas: rodada 005

**Exploratório:** `treino.modelo_oficial` é false. Nenhum número vale como conclusão do TCC.

Não constitui recomendação de investimento.

## 2. Identificação

- Rodada: 5
- Data: 2026-11-09
- Motivo: Rodada 5 oficial (D5, medida de 09/11/2026): dataset v7 de 2026-11-09; conferencia em docs/conferencia_rodada_005.md
- Situação: válida
- sha256 do dataset: 9f520c5fa7e91ebbb2a624a6cbb89d4caf33d8bb57ca3018be89ac43016e9928
- Arquivo do dataset: dataset-todas-2026-11-09.csv
- versao_preparacao: 7
- Período: 2021-01-04 a 2026-06-19
- Pregões: 1361
- Linhas: 94485
- Dobras: 63
- Semente: 20261023
- sha_parametros: 04ce153d729f35a3f3118dba48f6d616e65ca94afa4f3d49dea94bb285334023
- sha_regras: e275d3d6e8f1b65e4c781871062991d3e2503f3eaa0bb8836b864302390556b0
- sha_codigo: 290dca7e6f4dc2b9e0aacb8da130da3d906882766199b4e3742cfd73d02ee020
- Versões: xgboost 3.4.1, sklearn 1.9.1, pandas 3.1.0, numpy 2.5.4
- Hiperparâmetros: n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5

## 3. Passo 0: seleção dos blocos de base

| Etapa | Descrição | AUC médio | Aceito |
|---|---|---|---|
| modelo_1 | bloco preco_contexto | 0.51058 | não |
| modelo_1 | bloco macro | 0.50600 | não |
| modelo_3 | bloco noticias_contexto | 0.50966 | não |

- Base do modelo 1: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura
- Base do modelo 3: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom

## 4. Critérios

| Teste | Base | Ganho | IC 99% | Anos positivos | Pior ano | Queda top 5 (pp) | Ganho em 2024 (critério 5) | Ganho em 2023 (só relato) | C1 | C2 | C3 | C4 | C5 | Aprovado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Controle sorteado (controle) | modelo 1 | -0.00006 | [-0.00217; 0.00211] | 2 de 6 | -0.00195 | 0.90699 | 0.00168 | -0.00095 | não | não | não | não | não se aplica | não |
| A. Preço (bloco_a) | modelo 1 | 0.00857 | [0.00290; 0.01389] | 5 de 6 | -0.00157 | -1.18370 | 0.00547 | 0.00339 | sim | sim | sim | sim | não se aplica | sim |
| B. Contexto (bloco_b) | modelo 1 | -0.00235 | [-0.00671; 0.00189] | 2 de 6 | -0.00732 | 0.93774 | 0.00215 | -0.00553 | não | não | não | não | não se aplica | não |
| C. Balanço (bloco_c) | modelo 1 | 0.00256 | [-0.00153; 0.00651] | 3 de 6 | -0.00159 | 0.13836 | 0.00484 | -0.00074 | não | não | não | sim | não se aplica | não |
| D. Valor (bloco_d) | modelo 1 | 0.00019 | [-0.00263; 0.00304] | 4 de 6 | -0.00248 | 0.49193 | 0.00189 | 0.00049 | não | não | sim | sim | não se aplica | não |
| E. Notícias (bloco_e) | modelo 3 | 0.00034 | [-0.00240; 0.00308] | 4 de 6 | -0.00271 | -0.41507 | -0.00271 | -0.00138 | não | não | sim | sim | não | não |

## 5. Ganho por ano (número de pregões entre parênteses)

| Teste | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Controle sorteado (controle) | -0.00168 (187) | -0.00195 (250) | -0.00095 (248) | 0.00168 (251) | 0.00233 (250) | -0.00047 (115) |
| A. Preço (bloco_a) | 0.01269 (187) | 0.01591 (250) | 0.00339 (248) | 0.00547 (251) | 0.01109 (250) | -0.00157 (115) |
| B. Contexto (bloco_b) | -0.00732 (187) | 0.00036 (250) | -0.00553 (248) | 0.00215 (251) | -0.00258 (250) | -0.00260 (115) |
| C. Balanço (bloco_c) | -0.00159 (187) | 0.00671 (250) | -0.00074 (248) | 0.00484 (251) | 0.00413 (250) | -0.00094 (115) |
| D. Valor (bloco_d) | -0.00248 (187) | 0.00043 (250) | 0.00049 (248) | 0.00189 (251) | 0.00044 (250) | -0.00087 (115) |
| E. Notícias (bloco_e) | 0.00057 (187) | 0.00146 (250) | -0.00138 (248) | -0.00271 (251) | 0.00203 (250) | 0.00419 (115) |

## 6. Cobertura das colunas novas (fração preenchida por ano)

| Coluna | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| controle_sorteado | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| dias_desde_resultado | 98.4% | 99.8% | 97.8% | 98.6% | 99.9% | 100.0% |
| dy_12m | 99.7% | 100.0% | 99.9% | 100.0% | 100.0% | 100.0% |
| exposicao_small | 99.9% | 99.8% | 100.0% | 100.0% | 100.0% | 100.0% |
| fato_relevante_cvm | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| liquidez_20d | 99.7% | 98.1% | 99.3% | 99.0% | 99.9% | 100.0% |
| mom_12_1 | 95.6% | 97.1% | 99.6% | 99.1% | 100.0% | 100.0% |
| momento_setor_5d | 99.5% | 100.0% | 100.0% | 100.0% | 99.1% | 98.7% |
| posicao_fechamento | 100.0% | 99.9% | 100.0% | 99.9% | 100.0% | 100.0% |
| ret_idio_5d | 99.4% | 99.4% | 100.0% | 100.0% | 100.0% | 100.0% |
| var_lucro_aa | 65.3% | 99.4% | 97.2% | 97.2% | 97.7% | 97.1% |

## 7. Teste conjunto (blocos A a D aprovados)

- Situação: não se aplica
- Motivo: 1 bloco(s) aprovado(s); o conjunto só roda com 2 ou mais
- Blocos no conjunto: nenhum

## 8. Decisão

- Blocos adotados: A. Preço (bloco_a)
- Bloco E: não aprovado
- Colunas congeladas (modelo 1): ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d
- Colunas congeladas (modelo 3): ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d

## 9. Todas as tentativas do protocolo

| Rodada | Motivo | Situação | Motivos | sha256 dataset | Repete | Reproduziu |
|---|---|---|---|---|---|---|
| 1 | 1ª rodada | valida | - | 741e781122d0 | - | n/d |
| 2 | Repeticao_para_conferir_determinismo | valida | - | 741e781122d0 | 1 | sim |
| 3 | Rodada 3 oficial (D5 revista): dataset v7 com jan-jul/2025 preenchido, periodos_sem_coleta vazio; conferencia, D7 aceito e criterio 5 com premissa caida em docs/conferencia_rodada_003.md | valida | - | c954b437c55e | - | n/d |
| 4 | Reproducao da rodada 3 (mesmas entradas), antes de mudar treino.familia_producao para xgb | valida | - | c954b437c55e | 3 | sim |
| 5 | Rodada 5 oficial (D5, medida de 09/11/2026): dataset v7 de 2026-11-09; conferencia em docs/conferencia_rodada_005.md | valida | - | 9f520c5fa7e9 | - | n/d |

- Testes nesta rodada: 6. Testes acumulados: 30.
- sha256 do resultado: 614e9edc3c61a50ca13cb86756fe75419e7856d3c37378dda880405b6451acf1
