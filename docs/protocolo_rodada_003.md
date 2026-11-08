# Protocolo de teste de variáveis novas: rodada 003

**Exploratório:** `treino.modelo_oficial` é false. Nenhum número vale como conclusão do TCC.

Não constitui recomendação de investimento.

## 2. Identificação

- Rodada: 3
- Data: 2026-11-06
- Motivo: Rodada 3 oficial (D5 revista): dataset v7 com jan-jul/2025 preenchido, periodos_sem_coleta vazio; conferencia, D7 aceito e criterio 5 com premissa caida em docs/conferencia_rodada_003.md
- Situação: válida
- sha256 do dataset: c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa
- Arquivo do dataset: dataset-todas-2026-11-06.csv
- versao_preparacao: 7
- Período: 2021-01-04 a 2026-06-19
- Pregões: 1361
- Linhas: 94485
- Dobras: 63
- Semente: 20261023
- sha_parametros: 2af43f4004c8ed1acb3c7a32b7da4a9c7af470339abf147949dededf51f5ba96
- sha_regras: e275d3d6e8f1b65e4c781871062991d3e2503f3eaa0bb8836b864302390556b0
- sha_codigo: 5d6a5b939f81b4ee167bd7d56ee793f870ed08df71559fb41ceb70636478830b
- Versões: xgboost 3.4.1, sklearn 1.9.1, pandas 3.1.0, numpy 2.5.4
- Hiperparâmetros: n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5

## 3. Passo 0: seleção dos blocos de base

| Etapa | Descrição | AUC médio | Aceito |
|---|---|---|---|
| modelo_1 | bloco preco_contexto | 0.51046 | não |
| modelo_1 | bloco macro | 0.50533 | não |
| modelo_3 | bloco noticias_contexto | 0.50991 | não |

- Base do modelo 1: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura
- Base do modelo 3: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom

## 4. Critérios

| Teste | Base | Ganho | IC 99% | Anos positivos | Pior ano | Queda top 5 (pp) | Ganho em 2024 (critério 5) | Ganho em 2023 (só relato) | C1 | C2 | C3 | C4 | C5 | Aprovado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Controle sorteado (controle) | modelo 1 | 0.00013 | [-0.00200; 0.00238] | 4 de 6 | -0.00196 | 0.63028 | 0.00172 | 0.00097 | não | não | sim | não | não se aplica | não |
| A. Preço (bloco_a) | modelo 1 | 0.00881 | [0.00327; 0.01441] | 6 de 6 | 0.00029 | -1.13759 | 0.00692 | 0.00450 | sim | sim | sim | sim | não se aplica | sim |
| B. Contexto (bloco_b) | modelo 1 | -0.00178 | [-0.00586; 0.00246] | 2 de 6 | -0.00474 | 0.12298 | 0.00035 | -0.00474 | não | não | não | sim | não se aplica | não |
| C. Balanço (bloco_c) | modelo 1 | 0.00191 | [-0.00241; 0.00606] | 4 de 6 | -0.00232 | -0.90699 | 0.00337 | -0.00232 | não | não | sim | sim | não se aplica | não |
| D. Valor (bloco_d) | modelo 1 | 0.00039 | [-0.00232; 0.00310] | 3 de 6 | -0.00139 | -0.61491 | 0.00233 | 0.00029 | não | não | não | sim | não se aplica | não |
| E. Notícias (bloco_e) | modelo 3 | 0.00040 | [-0.00222; 0.00316] | 4 de 6 | -0.00317 | -0.41507 | -0.00317 | 0.00065 | não | não | sim | sim | não | não |

## 5. Ganho por ano (número de pregões entre parênteses)

| Teste | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Controle sorteado (controle) | -0.00103 (187) | -0.00196 (250) | 0.00097 (248) | 0.00172 (251) | 0.00042 (250) | 0.00058 (115) |
| A. Preço (bloco_a) | 0.01438 (187) | 0.01291 (250) | 0.00450 (248) | 0.00692 (251) | 0.01062 (250) | 0.00029 (115) |
| B. Contexto (bloco_b) | -0.00327 (187) | 0.00072 (250) | -0.00474 (248) | 0.00035 (251) | -0.00239 (250) | -0.00175 (115) |
| C. Balanço (bloco_c) | -0.00033 (187) | 0.00733 (250) | -0.00232 (248) | 0.00337 (251) | 0.00028 (250) | 0.00325 (115) |
| D. Valor (bloco_d) | -0.00089 (187) | -0.00011 (250) | 0.00029 (248) | 0.00233 (251) | 0.00082 (250) | -0.00139 (115) |
| E. Notícias (bloco_e) | -0.00079 (187) | 0.00003 (250) | 0.00065 (248) | -0.00317 (251) | 0.00148 (250) | 0.00807 (115) |

## 6. Cobertura das colunas novas (fração preenchida por ano)

| Coluna | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| controle_sorteado | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| dias_desde_resultado | 92.8% | 95.2% | 95.1% | 97.3% | 97.6% | 97.3% |
| dy_12m | 99.7% | 100.0% | 99.9% | 100.0% | 100.0% | 100.0% |
| exposicao_small | 99.9% | 99.8% | 100.0% | 100.0% | 100.0% | 100.0% |
| fato_relevante_cvm | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| liquidez_20d | 99.7% | 98.1% | 99.3% | 99.0% | 99.9% | 100.0% |
| mom_12_1 | 95.2% | 97.1% | 99.6% | 99.1% | 100.0% | 100.0% |
| momento_setor_5d | 99.5% | 100.0% | 100.0% | 100.0% | 99.1% | 98.7% |
| posicao_fechamento | 100.0% | 99.9% | 100.0% | 99.9% | 100.0% | 100.0% |
| ret_idio_5d | 99.4% | 99.4% | 100.0% | 100.0% | 100.0% | 100.0% |
| var_lucro_aa | 55.2% | 85.9% | 86.6% | 86.6% | 87.4% | 86.3% |

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

- Testes nesta rodada: 6. Testes acumulados: 18.
- sha256 do resultado: 4bebb74d20bf0f94f00ed6d0dbad990535a10e27158fe23513186666089b554b
