# Medida de dados novos (D5 esclarecida)

> Exploratório. Medida só do desenvolvimento, sem abrir o teste final. Não constitui recomendação de investimento.

Data da medida: 2026-11-10. Congelado: `protocolo_congelado_rodada_003.json` (rodada 3).

## Decisão

- Decisão: **nova rodada** (`nova_rodada`).
- Fração total: 42682 ÷ 94482 = 0,451747 (limite 0,01; exatamente o limite não passa).
- Parar e perguntar (D7): sim (fração de preço e alvo 0,108116).

## Frações por grupo

| Grupo | Colunas | Linhas mudadas | Fração |
|---|---|---|---|
| Preço (bloco A) | ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d | 10213 | 0,108095 |
| Notícias | noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom | 32645 | 0,345516 |
| Alvo | alvo | 2 | 0,000021 |
| Preço e alvo (regra D7) | ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d, alvo | 10215 | 0,108116 |

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
| 2021 | 14987 | 9762 | 0,651365 |
| 2022 | 16419 | 27 | 0,001644 |
| 2023 | 16940 | 7354 | 0,434120 |
| 2024 | 18256 | 10864 | 0,595092 |
| 2025 | 19308 | 7071 | 0,366221 |
| 2026 | 8572 | 7604 | 0,887074 |

## Tickers com mais linhas mudadas (até 10)

| Ticker | Linhas mudadas |
|---|---|
| PETR3 | 922 |
| PETR4 | 919 |
| ITUB4 | 913 |
| BBDC3 | 905 |
| BBAS3 | 901 |
| BBDC4 | 899 |
| BPAC11 | 886 |
| MGLU3 | 872 |
| VALE3 | 857 |
| B3SA3 | 835 |

## Datasets

| Papel | Arquivo | sha256 |
|---|---|---|
| Congelado (rodada oficial) | dataset-todas-2026-11-06.csv | c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa |
| Novo | dataset-todas-2026-11-09.csv | 9f520c5fa7e91ebbb2a624a6cbb89d4caf33d8bb57ca3018be89ac43016e9928 |

## Regras aplicadas

- Célula mudada: no preparado (ranks, o que o modelo recebe), vazia de um lado e preenchida do outro, ou |novo − congelado| > 1e-06 (estritamente maior); E no bruto (valor do CSV antes do rank, coluna de origem), o mesmo critério.
- Regra da medida: 2026-11-09: rank E bruto.
- Motivo do critério no bruto: ruído do float32 em valores quase empatados perto de zero (ex.: `salto_abertura` quando a abertura é igual ao fechamento anterior) muda o rank sem mudar o dado (medida de 09/11/2026, protocolo seção 8, nota da D5).
- Linha mudada: alguma célula mudada, ou a chave (data, ticker) existe em só um dos dois.
- Denominador: linhas com alvo preenchido no congelado. Linhas só no novo entram no numerador, não no denominador.
- Colunas: `colunas_3` do congelado mais `alvo`, com os valores que o modelo recebe (`preparacao.preparar`).
- Decisão: fração total > 0,01 → nova rodada; preço e alvo > 0,01 → parar e perguntar.
