# Conferência do dataset da rodada 3

Registrado em 08/11/2026, **antes de rodar o protocolo e a busca da rodada 3**. A rodada 3 é a rodada oficial pela D5 revista (`docs/protocolo_variaveis.md`, seção 8): a coleta preencheu jan–jul/2025 nas 3 origens antes do teste final. Este arquivo é registro: não muda as seções 1 a 7 do protocolo, os critérios nem os limites.

**Exploratório:** `treino.modelo_oficial` é false. Não constitui recomendação de investimento.

## 1. Identificação

| Item | Valor |
|---|---|
| Parâmetro alterado | `experimento.periodos_sem_coleta: []` (antes, 01/01 a 31/07/2025) |
| `versao_preparacao` | 7 |
| Linhas do treino | Desde 2021-01-01 (`treino.inicio_experimento`) |
| Teste final | Desde 23/06/2026, **trancado**: `fim` vazio, `liberado: false`, sem `docs/teste_final_usado.json` |
| Dataset de comparação (rodadas 1 e 2) | `dataset-todas-2026-10-30.csv`, versão 6, sha256 `741e781122d073e0f8fdab363998e34e39fa4f811d19c00a04412dedf548c980` |

| Versão | Arquivo (em `saida/experimento/`) | sha256 | Gerado em |
|---|---|---|---|
| `todas` | `dataset-todas-2026-11-06.csv` | `c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa` | 2026-11-08 14:15 |
| `principais` | `dataset-principais-2026-11-06.csv` | `ca7d5bd161d159c133c07867bb44ff0c7a15b03d845978593f2f87cbf5446912` | 2026-11-08 14:17 |
| `hora_real_noite` | `dataset-hora_real_noite-2026-11-06.csv` | `d1909b4f5a6c77086a9fef92f80f6981217dc7521c79527a4486a6364adab28d` | 2026-11-08 14:18 |

As três versões têm 119.678 linhas e 1.707 pregões, de 30/12/2019 a 06/11/2026. Todas as contagens abaixo são do **desenvolvimento** (2021-01-01 até 22/06/2026). As 14.472 linhas a partir de 23/06/2026 só foram contadas, nunca abertas.

## 2. Decisões do usuário (08/11/2026)

| Tema | Decisão |
|---|---|
| D7 (preços reescritos) | **Aceito.** A diferença entre v7 e v6 nos retornos é ruído de float32: no máximo 1,8e-6 absoluto (`ret_1d`, `ret_t1`), 6e-6 no `beta`, nenhum caso acima de 1e-4; `ret_ibov_t1` é idêntico. A tolerância relativa de 1e-6 "estoura" só porque o retorno pequeno amplia o ruído do preço. Um único `alvo` mudou fora da NATU3: ALOS3 em 06/01/2026, um empate exato com o IBOV (`ret_t1` = `ret_ibov_t1` = −0,01032; limitação 15 de `docs/regras_dataset.md`) |
| Critério 5 do bloco E | **Mantido como está escrito** (pregões de 2024). **A premissa caiu:** com a recarga, a `wordpress` existe em 2023–2025 (34.540, 30.032 e 28.846 notícias no dataset), então "2023–2024 sem `wordpress`" não vale mais. O critério passa a medir só a robustez do bloco E em 2024, não um regime sem `wordpress` |
| RAIZ4 | Lista manual temporária `fundamentos.quantidade_suspeita_manual` (RAIZ4 desde 2026-11-03): mesmo tratamento da quantidade de ações suspeita, com aviso no `execucao`. Não afeta o dataset (seção 6) |

Ao rodar o protocolo da rodada 3, citar este arquivo no `--motivo` para que o relatório `docs/protocolo_rodada_003.md` aponte para estas decisões.

## 3. Linhas e notícias por ano

| Ano | Linhas v7 | Linhas v6 | Pregões | Com alvo (v7) | % pregão × ação com notícia, v7 | v6 | Notícias por linha, v7 | `mudanca_tom` preenchida, v7 | `fato_relevante_cvm` preenchida, v7 | v6 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 14.989 | 14.495 | 247 | 14.987 | 69,5% | 68,8% | 3,26 | 61,5% | 100% | 100% |
| 2022 | 16.419 | 15.919 | 250 | 16.419 | 74,7% | 74,2% | 3,66 | 74,7% | 100% | 100% |
| 2023 | 16.941 | 16.445 | 248 | 16.940 | 78,2% | 44,1% | 4,06 | 78,1% | 100% | **0%** |
| 2024 | 18.256 | 17.754 | 251 | 18.256 | 76,1% | 57,4% | 3,86 | 76,0% | 100% | 100% |
| 2025 | 19.308 | 19.082 | 250 | 19.308 | 78,3% | 31,3% | 4,45 | 78,3% | 100% | 42,1% |
| 2026 (até 22/06) | 8.645 | 8.645 | 116 | 8.645 | 89,8% | 86,4% | 8,67 | 89,8% | 100% | 100% |
| **Total** | **94.558** | **92.340** | 1.362 | | **76,9%** | | | | | |

- Em 2025 a v6 tinha `noticias_dia_qtd` vazia em jan–jul (só 8.040 linhas preenchidas). Na v7 todas as linhas estão preenchidas, e jan–jul fica entre 2,8 e 3,8 notícias por linha (ago–dez: 5,5 a 7,0).
- Conferência: a contagem refeita de notícias por (pregão, empresa) bate com `noticias_dia_qtd` em 94.558 de 94.558 linhas.
- O volume de notícias continua crescendo: 2026 tem cerca de 2× a média por linha de 2021–2025 (limitação 1 de `docs/regras_dataset.md`).

## 4. Notícias por origem

Notícias que entram no dataset, depois do filtro de papel e das repetidas, só de empresas do universo:

| Ano | `google_news` | `wordpress` | `cvm_ipe` | Total |
|---|---|---|---|---|
| 2021 | 10.991 | 26.929 | 3.421 | 41.341 |
| 2022 | 13.022 | 34.260 | 3.186 | 50.468 |
| 2023 | 21.245 | 34.540 | 3.042 | 58.827 |
| 2024 | 27.458 | 30.032 | 3.122 | 60.612 |
| 2025 | 42.540 | 28.846 | 3.330 | 74.716 |
| 2026 (até 22/06) | 50.223 | 11.919 | 1.596 | 63.738 |

% das linhas (pregão × ação) com pelo menos 1 notícia de cada origem:

| Ano | `google_news` | `wordpress` | `cvm_ipe` |
|---|---|---|---|
| 2021 | 39,2% | 52,7% | 19,5% |
| 2022 | 40,4% | 61,2% | 16,7% |
| 2023 | 47,9% | 63,1% | 15,4% |
| 2024 | 53,5% | 57,1% | 14,8% |
| 2025 | 60,1% | 55,5% | 14,2% |
| 2026 (até 22/06) | 84,7% | 55,2% | 15,5% |

## 5. Diferenças em relação ao dataset das rodadas 1 e 2

### 5.1 Contagens do JSON do dataset

| Chave | v6 | v7 |
|---|---|---|
| Notícias lidas | 368.866 | 546.621 |
| Preparadas | 315.866 | 460.946 |
| Repetidas por `id` | 45.603 | 63.526 |
| Cópias por título no mesmo dia | 1.329 | 15.189 |
| Cópias por título em ±1 dia | 77 | 184 |
| Cópias por URL | 33 | 263 |
| `meia_noite_pacifico` (N1-A) | 130.382 | 254 |
| Ignoradas por papel `errada` | 33.626 | 39.515 |
| Pregões sem coleta (notícias / CVM) | 145 / 393 | 0 / 0 |

O salto das cópias por título vem da sobreposição `google_news` × `wordpress` em 2023–2025, que não existia antes da recarga. A queda da N1-A vem da coleta: desde 03/11/2026 ela grava a hora vazia nas notícias só com data (pegadinha 14).

### 5.2 Linhas

- **2.218 linhas novas e nenhuma removida:** NATU3 com 1.115 (04/01/2021 a 25/06/2025, pela holding) e JBSS32 com 1.103 (04/01/2021 a 06/06/2025, como ON da JBS S.A.). É efeito da versão 7 (emissor por período e composição mapeada).

### 5.3 Colunas, nas 92.340 linhas comuns

| Grupo | O que muda | Causa |
|---|---|---|
| Preço e alvo (`ret_*`, `volatilidade_20d`, `beta`, `salto_abertura`, `dist_*`, `mom_12_1`, `ret_idio_5d`, `exposicao_*`, `ret_t1`) | Diferença absoluta ≤ 2e-6 (beta ≤ 6,4e-6) | Ruído do float32 na regravação diária (D7, aceito) |
| `alvo` | 5 linhas: 4 da NATU3 e ALOS3 em 06/01/2026 | NATU3 pelo emissor; ALOS3 pelo empate exato |
| `volume_relativo`, `amplitude`, `posicao_fechamento`, `liquidez_20d`, `dy_12m` | Até 24 linhas, só NATU3 em 2025 | NATU3 saiu de `eventos_retorno_suspeito` (versão 7) |
| Colunas de notícias e `tom_mercado` | Quase todas as linhas de 2023–2025 | Recarga de `google_news` e `wordpress`; jan–jul/2025 preenchido |
| `fato_relevante_cvm` | 27.487 linhas, de vazio para valor | 2023 e jan–jul/2025 da CVM preenchidos (`periodos_sem_coleta_cvm` vazia desde 03/11) |
| `momento_setor_5d`, `ret_vs_setor`, `tom_setor` | Muitas linhas | NATU3 e JBSS32 entraram nos setores |
| `controle_sorteado` | 34.059 linhas | O sorteio é feito sobre os tickers do dia, em ordem alfabética: com tickers novos no dia, os valores se redistribuem (comportamento esperado) |
| `dia_resultado`, `dias_desde_resultado`, `var_lucro_aa` | 53, 5.115 e 12.860 linhas | Seção 5.4 |

### 5.4 Colunas de balanço: investigação por causa

**Resultado: nenhum bug.** Toda a diferença vem de duas causas: os balanços de 2020 que a coleta entregou, e o emissor por período da NATU3. Nenhuma mudança vem da regra da `data_entrega`: as entregas que a v6 via continuam todas na v7 (0 removidas). Do lado do código, a única mudança nessas três colunas entre a versão 6 e a 7 foi a chave da junção (`empresa` → `cnpj_emissor`), e ela só difere da `empresa` na NATU3 e na JBSS32.

**Balanços novos.** No diagnóstico de 01/11/2026, `v1-balancos` tinha 2.694 linhas, começando em 2021. No de 08/11/2026 tem 3.192: chegaram os de 2020 (81 DFP e 378 ITR, de 81 CNPJs). Eles faltavam no dataset da v6, gerado em 02/11 às 13:40. A tabela não tem data de carga, então não dá para confirmar o dia exato da entrega. A seção 3.4 da especificação ainda diz "balanços desde 2021".

| Coluna | Linhas | Balanços de 2020 | Emissor (NATU3) | Data de entrega | Bug |
|---|---|---|---|---|---|
| `dia_resultado` | 53 (todas de falso para verdadeiro, em 2021) | 53 | 0 | 0 | 0 |
| `dias_desde_resultado` | 5.115 | 5.087 (5.037 de vazio para valor em 2021–2022; 50 de valor para outro valor, RAIL3 em 2021) | 28 (de valor para vazio, 02/07 a 08/08/2025) | 0 | 0 |
| `var_lucro_aa` | 12.860 | 12.613 (de vazio para valor: 7.947 em 2021 e 4.666 em 2022) | 247 (243 de valor para vazio e 4 de valor para outro valor, de 26/06/2025 a 22/06/2026) | 0 | 0 |

**Por que cada caso acontece:**

- **`dia_resultado`:** o DFP 2020, entregue em fev–abr/2021, agora marca o dia de resultado (51 entregas novas de empresas, 53 tickers).
- **`dias_desde_resultado`:** antes da 1ª entrega de 2021 não havia entrega anterior. Agora o ITR do 3T20 (nov/2020) e o DFP 2020 dão a referência.
- **`var_lucro_aa`:** o trimestre de 2021 precisa do mesmo trimestre de 2020, que agora existe. Em 2022, os casos são as linhas que ainda usavam um balanço de 2021 como referência (o 4T21 até o ITR do 1T22).

**Os 10 tickers com mais linhas mudadas:**

| `dias_desde_resultado` | Linhas | `var_lucro_aa` | Linhas |
|---|---|---|---|
| BBDC4 | 255 | MRVE3 | 410 |
| BBDC3 | 255 | ITSA4 | 258 |
| BBAS3 | 246 | BEEF3 | 254 |
| RAIL3 | 138 | EQTL3 | 254 |
| AXIA3 | 107 | TAEE11 | 254 |
| ENGI11 | 90 | CSNA3 | 253 |
| COGN3 | 89 | B3SA3 | 253 |
| CMIG4 | 89 | MULT3 | 253 |
| CVCB3 | 89 | FLRY3 | 253 |
| CSAN3 | 89 | ITUB4 | 253 |

**Exemplos concretos (balanço antes × agora):**

| Caso | v6 | v7 | Balanço que explica |
|---|---|---|---|
| ITUB4, `var_lucro_aa` em 03/05/2021 | vazio (1º valor só em 09/05/2022) | 0,01591 | ITR 1T20 (lucro 3,678 bi, entregue em 04/05/2020) agora existe. Conta: (6,220 bi − 3,678 bi) ÷ PL 159,774 bi = 0,01591 |
| ITUB4, 25/02/2021 | `dia_resultado` falso, `dias_desde_resultado` vazio | verdadeiro, 0 | DFP 2020 entregue em 25/02/2021. A `var_lucro_aa` continua vazia, corretamente: o 4T19 não existe |
| BBDC4, 09/03/2021 | `dias_desde_resultado` vazio (1º valor em 17/03/2022) | 0 | DFP 2020 entregue em 09/03/2021 (o banco tem só DFP em 2020–2021); vale até 31/03/2022 (balanço velho, 15 meses), daí as 255 linhas |
| RAIL3, de 01/06 a 11/08/2021 | `dias_desde_resultado` 13 … 62 | 0 … 49 | DFP 2020 entregue em 01/06/2021 (152 dias de atraso, abaixo de 180): é uma entrega nova no meio de 2021 |
| MRVE3, 2022 inteiro | `var_lucro_aa` vazia | 0,00764 | A empresa não tem ITR de 2022 no banco, e o DFP 2021 só foi entregue em 06/07/2023. A referência fica no 3T21: (194,5 mi − 3T20 145,8 mi) ÷ PL 6.373,7 mi = 0,00764, válida até o fim de 12/2022 pela regra do balanço velho |
| NATU3, de 26/06 a 01/07/2025 | 0,01730 | 0,05192 | A v7 usa a holding (32785497000197): (1T25 −151,4 mi − 1T24 −935,1 mi) ÷ PL 15.095 mi = 0,05192 |
| NATU3, desde 02/07/2025 | valores | vazia | Natura Cosméticos (71673990000177) só tem balanços desde 06/2025: sem o mesmo trimestre do ano anterior e sem entrega até 11/08/2025. É o comportamento previsto (especificação, seção 3.4) |

**Observação, sem diferença entre v6 e v7:** BBDC3/BBDC4 (60746948000112) e BBAS3 (00000000000191) têm `lucro_liquido` vazio em todas as linhas de balanço (31 e 29). Por isso a `var_lucro_aa` desses bancos fica sempre vazia, nas duas versões.

## 6. RAIZ4

- **Máscara de retorno suspeito:** o diagnóstico de 08/11 lista RAIZ4 em 03/11/2026 (0,30 → 27,10, +8.933%). A volatilidade do painel já sai `historico_insuficiente`.
- **Fora da rodada 3:** 03/11/2026 é posterior a 23/06/2026, e a RAIZ4 está fora do universo do modelo desde 12/03/2026 (saiu da composição do Ibovespa). O dataset não tem nenhuma linha dela depois dessa data.
- **Pacotes publicados desde 03/11:**
  - P/VP: `nao_se_aplica` (patrimônio ≤ 0).
  - P/L: de −0,051 para −4,59 (90×, a razão dos preços), porque o valor de mercado embutido ficou cerca de 100× maior.
  - Rentabilidade: 1 mês em +7.483% e 1 ano em +2.867%.
  - As medianas de setor das outras ações não são afetadas.
- **Tratamento até a coleta corrigir:** a lista manual da seção 2. A rentabilidade da própria ação continua como veio, porque o preço não é corrigido.

## 7. Testes alterados

- `tests/test_vazamento_experimento.py`: o caso `logo_depois_sem_coleta` passa a usar um período sem coleta fixo do próprio teste (01/01 a 31/07/2025). Antes ele lia o do `parametros.yaml`, que agora está vazio. A borda continua testada.
- `tests/test_exp_parametros.py`: o arquivo real agora tem `periodos_sem_coleta == ()`.
