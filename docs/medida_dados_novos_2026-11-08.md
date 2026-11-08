# Medida de dados novos (D5 esclarecida)

> Exploratório. Medida só do desenvolvimento, sem abrir o teste final. Não constitui recomendação de investimento.

Data da medida: 2026-11-08. Congelado: `protocolo_congelado_rodada_003.json` (rodada 3).

## Decisão

- Decisão: **rodada oficial continua** (`rodada_oficial_continua`).
- Fração total: 0 ÷ 94482 = 0,000000 (limite 0,01; exatamente o limite não passa).
- Parar e perguntar (D7): não (fração de preço e alvo 0,000000).

## Frações por grupo

| Grupo | Colunas | Linhas mudadas | Fração |
|---|---|---|---|
| Preço (bloco A) | ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d | 0 | 0,000000 |
| Notícias | noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom | 0 | 0,000000 |
| Alvo | alvo | 0 | 0,000000 |
| Preço e alvo (regra D7) | ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d, alvo | 0 | 0,000000 |

## Contagens

| Item | Valor |
|---|---|
| Linhas do congelado (desenvolvimento) | 94485 |
| Linhas do novo (desenvolvimento) | 94485 |
| Linhas comparadas (nos dois) | 94485 |
| Só no congelado | 0 |
| Só no novo | 0 |
| Denominador (alvo preenchido no congelado) | 94482 |

## Por ano (ano da data)

| Ano | Denominador | Linhas mudadas | Fração |
|---|---|---|---|
| 2021 | 14987 | 0 | 0,000000 |
| 2022 | 16419 | 0 | 0,000000 |
| 2023 | 16940 | 0 | 0,000000 |
| 2024 | 18256 | 0 | 0,000000 |
| 2025 | 19308 | 0 | 0,000000 |
| 2026 | 8572 | 0 | 0,000000 |

## Tickers com mais linhas mudadas (até 10)

Nenhuma linha mudada.

## Datasets

| Papel | Arquivo | sha256 |
|---|---|---|
| Congelado (rodada oficial) | dataset-todas-2026-11-06.csv | c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa |
| Novo | dataset-todas-2026-11-06.csv | c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa |

## Regras aplicadas

- Célula mudada: vazia de um lado e preenchida do outro, ou |novo − congelado| > 1e-06 (estritamente maior).
- Linha mudada: alguma célula mudada, ou a chave (data, ticker) existe em só um dos dois.
- Denominador: linhas com alvo preenchido no congelado. Linhas só no novo entram no numerador, não no denominador.
- Colunas: `colunas_3` do congelado mais `alvo`, com os valores que o modelo recebe (`preparacao.preparar`).
- Decisão: fração total > 0,01 → nova rodada; preço e alvo > 0,01 → parar e perguntar.
