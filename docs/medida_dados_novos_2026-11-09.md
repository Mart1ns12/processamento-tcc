# Medida de dados novos (D5 esclarecida)

> Exploratório. Medida só do desenvolvimento, sem abrir o teste final. Não constitui recomendação de investimento.

Data da medida: 2026-11-09. Congelado: `protocolo_congelado_rodada_003.json` (rodada 3).

## Decisão

- Decisão: **nova rodada** (`nova_rodada`).
- Fração total: 48554 ÷ 94482 = 0,513897 (limite 0,01; exatamente o limite não passa).
- Parar e perguntar (D7): sim (fração de preço e alvo 0,173800).

## Frações por grupo

| Grupo | Colunas | Linhas mudadas | Fração |
|---|---|---|---|
| Preço (bloco A) | ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d | 16419 | 0,173779 |
| Notícias | noticias_dia_qtd, noticias_dia_tom, noticias_dia_extremo, mudanca_tom | 35004 | 0,370483 |
| Alvo | alvo | 2 | 0,000021 |
| Preço e alvo (regra D7) | ret_1d, ret_5d, ret_20d, volatilidade_20d, beta, volume_relativo, salto_abertura, posicao_fechamento, mom_12_1, liquidez_20d, ret_idio_5d, alvo | 16421 | 0,173800 |

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
| 2021 | 14987 | 10066 | 0,671649 |
| 2022 | 16419 | 852 | 0,051891 |
| 2023 | 16940 | 8575 | 0,506198 |
| 2024 | 18256 | 12498 | 0,684597 |
| 2025 | 19308 | 8569 | 0,443806 |
| 2026 | 8572 | 7994 | 0,932571 |

## Tickers com mais linhas mudadas (até 10)

| Ticker | Linhas mudadas |
|---|---|
| BBDC3 | 942 |
| PETR4 | 936 |
| PETR3 | 934 |
| BBAS3 | 929 |
| ITUB4 | 927 |
| BBDC4 | 919 |
| BPAC11 | 905 |
| MGLU3 | 899 |
| B3SA3 | 871 |
| VALE3 | 867 |

## Datasets

| Papel | Arquivo | sha256 |
|---|---|---|
| Congelado (rodada oficial) | dataset-todas-2026-11-06.csv | c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa |
| Novo | dataset-todas-2026-11-06.csv | 7c9d305b4a4403842bac11615758c3da22496127616698f51730adc4a10621af |

## Regras aplicadas

- Célula mudada: vazia de um lado e preenchida do outro, ou |novo − congelado| > 1e-06 (estritamente maior).
- Linha mudada: alguma célula mudada, ou a chave (data, ticker) existe em só um dos dois.
- Denominador: linhas com alvo preenchido no congelado. Linhas só no novo entram no numerador, não no denominador.
- Colunas: `colunas_3` do congelado mais `alvo`, com os valores que o modelo recebe (`preparacao.preparar`).
- Decisão: fração total > 0,01 → nova rodada; preço e alvo > 0,01 → parar e perguntar.

## Investigação do `salto_abertura` (D7, 09/11/2026)

Feita só com a leitura dos dois CSVs (congelado `c954b437c55e…` × novo `7c9d305b4a44…`), no desenvolvimento, comparando o valor **bruto**, antes do rank.

**Conclusão:** a mudança não é dado novo nem erro. É o ruído do float32 na regravação dos preços (pegadinha 6), ampliado pelo rank em valores quase empatados perto de zero. Esses quase empates são as aberturas iguais ao fechamento anterior (defeito do Yahoo, limitação 13 de `docs/regras_dataset.md`). Na prática, a variável que o modelo recebe não mudou.

| Medida | Resultado |
|---|---|
| Células (data, ticker) comparadas | 94.558 |
| Células brutas com alguma diferença | 56.438; diferença mediana 1,05e-7, máxima 1,75e-6 |
| Células brutas com diferença > 1e-6 | **72**, todas de valor para outro valor (nenhuma de vazio para valor ou o contrário) |
| Tickers dessas 72 | ITUB4 28, BBDC4 23, BBDC3 11, VIVT3 7, WEGE3 2, ITSA4 1 (pagadores frequentes de dividendos, com o ajustado recalculado mais vezes); 2021 a 2023 |
| Abertura implícita (abertura ÷ fechamento do dia = (1 + salto) ÷ (1 + `ret_1d`)) nessas 72 | Igual até a 6ª casa antes e depois |
| Linhas com o **rank** mudado | 6.952, em 1.011 pregões (mediana de 6 linhas por pregão) |
| Delas, com \|salto bruto\| < 1e-5 | 6.848 (98,5%); em 2.666 o valor bruto da própria linha é idêntico (mudou o de uma vizinha empatada) |

**Exemplos de abertura implícita (abertura ÷ fechamento do dia), antes × depois:**

| Data | Ticker | `salto_abertura` antes → depois | Abertura ÷ fechamento antes → depois |
|---|---|---|---|
| 27/06/2023 | ITUB4 | 0,005238 → 0,005240 | 1,016602 → 1,016602 |
| 10/02/2021 | ITUB4 | 0,000360 → 0,000358 | 1,007584 → 1,007584 |
| 12/07/2021 | BBDC4 | 0,005286 → 0,005287 | 0,980563 → 0,980563 |

**Como o rank amplia o ruído (04/01/2021):** a VIVT3 tinha salto −4,5e-7 e passou a +4,5e-7. Com isso ela trocou de posição com a BBSE3 (−8,7e-9, sem mudança), e o rank das duas mudou em 0,017 (de 0,0345 para 0,0517 e o contrário).

**Efeito na decisão:** não muda. Sem o `salto_abertura`, o grupo de preço ainda passa de 1% por causa de `beta` (4.528 linhas) e `mom_12_1` (7.693 linhas) em 2021, que é o efeito estrutural do pregão novo de 20/11/2020 nas janelas de 252 pregões (o `ret_idio_5d` acompanha o beta). As notícias, com 37%, já bastam para a nova rodada.

**Ponto para a regra (não aplicado):** comparar depois do rank transforma empates quase exatos em mudança. Uma forma de evitar isso seria contar a célula como mudada só quando o valor **bruto** também muda mais que 1e-6. Isso seria uma mudança na regra da nota da D5 e teria de ser registrada antes da próxima medida.
