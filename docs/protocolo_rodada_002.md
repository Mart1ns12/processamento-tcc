# Protocolo de teste de variáveis novas: rodada 002

**Exploratório:** `treino.modelo_oficial` é false. Nenhum número vale como conclusão do TCC.

Não constitui recomendação de investimento.

## 2. Identificação

- Rodada: 2
- Data: 2026-10-30
- Motivo: Repeticao_para_conferir_determinismo
- Situação: válida
- sha256 do dataset: 741e781122d073e0f8fdab363998e34e39fa4f811d19c00a04412dedf548c980
- Arquivo do dataset: dataset-todas-2026-10-30.csv
- versao_preparacao: 6
- Período: 2021-01-04 a 2026-06-19
- Pregões: 1361
- Linhas: 92267
- Dobras: 63
- Semente: 20261023
- sha_parametros: d3cee30e3cb8b1b5595be7d0d4f7901f9a4188eab304867d6747b0a6a0360e35
- sha_regras: e275d3d6e8f1b65e4c781871062991d3e2503f3eaa0bb8836b864302390556b0
- sha_codigo: 4c612df58dcb318dc5ba44fc22c51c369947d45a2d371949aefa17096295e7e1
- Versões: xgboost 3.4.1, sklearn 1.9.1, pandas 3.1.0, numpy 2.5.4
- Hiperparâmetros: n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5

## 3. Passo 0: seleção dos blocos de base

| Etapa | Descrição | AUC médio | Aceito |
|---|---|---|---|
| modelo_1 | bloco preco_contexto | 0.50955 | não |
| modelo_1 | bloco macro | 0.50856 | não |
| modelo_3 | bloco noticias_contexto | 0.51041 | não |

- Base do modelo 1: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura
- Base do modelo 3: ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom

## 4. Critérios

| Teste | Base | Ganho | IC 99% | Anos positivos | Pior ano | Queda top 5 (pp) | Ganho em 2024 (critério 5) | Ganho em 2023 (só relato) | C1 | C2 | C3 | C4 | C5 | Aprovado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Controle sorteado (controle) | modelo 1 | -0.00078 | [-0.00311; 0.00153] | 2 de 6 | -0.00334 | 0.06149 | 0.00077 | -0.00188 | não | não | não | sim | não se aplica | não |
| A. Preço (bloco_a) | modelo 1 | 0.00768 | [0.00262; 0.01346] | 5 de 6 | -0.00429 | -1.32206 | 0.00450 | 0.00449 | sim | sim | sim | sim | não se aplica | sim |
| B. Contexto (bloco_b) | modelo 1 | -0.00239 | [-0.00658; 0.00165] | 1 de 6 | -0.00420 | 0.56879 | -0.00420 | -0.00382 | não | não | não | não | não se aplica | não |
| C. Balanço (bloco_c) | modelo 1 | 0.00086 | [-0.00304; 0.00501] | 3 de 6 | -0.00237 | -0.56879 | 0.00025 | -0.00221 | não | não | não | sim | não se aplica | não |
| D. Valor (bloco_d) | modelo 1 | -0.00057 | [-0.00314; 0.00200] | 2 de 6 | -0.00372 | 0.36895 | -0.00002 | 0.00085 | não | não | não | sim | não se aplica | não |
| E. Notícias (bloco_e) | modelo 3 | 0.00042 | [-0.00209; 0.00309] | 4 de 6 | -0.00191 | -0.23059 | -0.00052 | -0.00191 | não | não | sim | sim | não | não |

## 5. Ganho por ano (número de pregões entre parênteses)

| Teste | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Controle sorteado (controle) | -0.00225 (187) | -0.00334 (250) | -0.00188 (248) | 0.00077 (251) | 0.00268 (250) | -0.00140 (115) |
| A. Preço (bloco_a) | 0.01350 (187) | 0.01056 (250) | 0.00449 (248) | 0.00450 (251) | 0.01234 (250) | -0.00429 (115) |
| B. Contexto (bloco_b) | -0.00398 (187) | -0.00099 (250) | -0.00382 (248) | -0.00420 (251) | -0.00068 (250) | 0.00042 (115) |
| C. Balanço (bloco_c) | -0.00237 (187) | 0.00814 (250) | -0.00221 (248) | 0.00025 (251) | 0.00069 (250) | -0.00140 (115) |
| D. Valor (bloco_d) | -0.00372 (187) | -0.00084 (250) | 0.00085 (248) | -0.00002 (251) | 0.00065 (250) | -0.00177 (115) |
| E. Notícias (bloco_e) | 0.00117 (187) | 0.00348 (250) | -0.00191 (248) | -0.00052 (251) | 0.00018 (250) | 0.00014 (115) |

## 6. Cobertura das colunas novas (fração preenchida por ano)

| Coluna | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| controle_sorteado | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| dias_desde_resultado | 58.9% | 94.1% | 94.9% | 97.2% | 97.7% | 97.3% |
| dy_12m | 99.7% | 100.0% | 99.9% | 100.0% | 99.9% | 100.0% |
| exposicao_small | 99.9% | 99.8% | 100.0% | 100.0% | 99.7% | 100.0% |
| fato_relevante_cvm | 100.0% | 100.0% | 0.0% | 100.0% | 42.1% | 100.0% |
| liquidez_20d | 99.7% | 98.0% | 99.3% | 99.0% | 99.8% | 100.0% |
| mom_12_1 | 95.1% | 97.1% | 99.6% | 99.1% | 99.3% | 98.7% |
| momento_setor_5d | 99.4% | 100.0% | 100.0% | 100.0% | 99.1% | 98.7% |
| posicao_fechamento | 100.0% | 99.9% | 100.0% | 99.9% | 100.0% | 100.0% |
| ret_idio_5d | 99.4% | 99.4% | 100.0% | 100.0% | 99.4% | 100.0% |
| var_lucro_aa | 0.0% | 56.1% | 86.2% | 86.2% | 87.9% | 87.6% |

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

- Testes nesta rodada: 6. Testes acumulados: 12.
- sha256 do resultado: 07544273dffe7257b9187d4f217015323650fbc65a02b1b264b431fee5e21e7b
