# Conferência do dataset da rodada 5

Registrado em 10/11/2026, **antes de rodar o protocolo e a busca da rodada 5**. A rodada 5 é a oficial pela D5 revista (`docs/protocolo_variaveis.md`, seção 8, medida de 09/11/2026). Este arquivo é registro: não muda as seções 1 a 7 do protocolo, os critérios nem os limites.

**Exploratório:** `treino.modelo_oficial` é false. Não constitui recomendação de investimento.

## 1. Identificação

| Item | Valor |
|---|---|
| Gerado depois de | Daily `2026-11-10-daily-080002` (entrega concluída às 08:26:56); último pregão 09/11/2026 |
| `versao_preparacao` | 7 (sem mudança) |
| Linhas do treino | Desde 2021-01-01 (`treino.inicio_experimento`) |
| Teste final | Desde 23/06/2026, **trancado**: `fim` vazio, `liberado: false` |
| Dataset de comparação (rodadas 3 e 4) | `dataset-todas-2026-11-06.csv`, sha256 `c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa` (cópia congelada, intacta) |

| Versão | Arquivo (em `saida/experimento/`) | sha256 | Gerado em |
|---|---|---|---|
| `todas` | `dataset-todas-2026-11-09.csv` | `9f520c5fa7e91ebbb2a624a6cbb89d4caf33d8bb57ca3018be89ac43016e9928` | 2026-11-10 11:46 |
| `principais` | `dataset-principais-2026-11-09.csv` | `bc7797c959378118f9d511434d69e54e648198df143a06cce3b530954d4803cc` | 2026-11-10 11:46 |
| `hora_real_noite` | `dataset-hora_real_noite-2026-11-09.csv` | `ca6f9e3eff04e2ffffe801662ecc27dbd80461a2ebb1b8b21f9773e10541d8af` | 2026-11-10 11:47 |

As três versões têm 119.823 linhas e 1.709 pregões, de 30/12/2019 a 09/11/2026. Todas as contagens abaixo são do **desenvolvimento** (2021-01-01 até 22/06/2026, 94.558 linhas). As 6.944 linhas a partir de 23/06/2026 só foram contadas, nunca abertas.

## 2. Linhas e notícias por ano

| Ano | Linhas | Pregões | Com alvo | % pregão × ação com notícia, r5 | r3 | Notícias por linha, r5 | r3 | `mudanca_tom` preenchida | `fato_relevante_cvm` preenchida |
|---|---|---|---|---|---|---|---|---|---|
| 2021 | 14.989 | 247 | 14.987 | 69,5% | 69,5% | 3,26 | 3,26 | 61,5% | 100% |
| 2022 | 16.419 | 250 | 16.419 | 74,7% | 74,7% | 3,66 | 3,66 | 74,7% | 100% |
| 2023 | 16.941 | 248 | 16.940 | 78,2% | 78,2% | 4,05 | 4,06 | 78,1% | 100% |
| 2024 | 18.256 | 251 | 18.256 | 75,9% | 76,1% | 3,85 | 3,86 | 75,8% | 100% |
| 2025 | 19.308 | 250 | 19.308 | 78,1% | 78,3% | 4,43 | 4,45 | 78,1% | 100% |
| 2026 (até 22/06) | 8.645 | 116 | 8.645 | 89,1% | 89,8% | 8,58 | 8,67 | 89,1% | 100% |
| **Total** | **94.558** | 1.362 | 94.555 | **76,7%** | **76,9%** | | | | |

- Mesmas linhas da rodada 3: nenhuma linha (data, ticker) entra ou sai no desenvolvimento.
- Conferência: a contagem refeita de notícias por (pregão, empresa) bate com `noticias_dia_qtd` em 94.558 de 94.558 linhas.
- 2025 continua completo: jan–jul entre 2,8 e 3,8 notícias por linha; ago–dez entre 5,5 e 6,9.

## 3. Notícias por origem

Notícias que entram no dataset, depois do filtro de papel e das repetidas, só de empresas do universo (rodada 3 entre parênteses):

| Ano | `google_news` | `wordpress` | `cvm_ipe` | Total |
|---|---|---|---|---|
| 2021 | 10.991 (10.991) | 26.929 (26.929) | 3.421 (3.421) | 41.341 (41.341) |
| 2022 | 13.020 (13.022) | 34.261 (34.260) | 3.186 (3.186) | 50.467 (50.468) |
| 2023 | 20.599 (21.245) | 35.095 (34.540) | 3.042 (3.042) | 58.736 (58.827) |
| 2024 | 26.261 (27.458) | 31.001 (30.032) | 3.122 (3.122) | 60.384 (60.612) |
| 2025 | 40.589 (42.540) | 30.488 (28.846) | 3.330 (3.330) | 74.407 (74.716) |
| 2026 (até 22/06) | 45.781 (50.223) | 15.562 (11.919) | 1.596 (1.596) | 62.939 (63.738) |

% das linhas (pregão × ação) com pelo menos 1 notícia de cada origem:

| Ano | `google_news` | `wordpress` | `cvm_ipe` |
|---|---|---|---|
| 2021 | 39,2% | 52,7% | 19,5% |
| 2022 | 40,4% | 61,2% | 16,7% |
| 2023 | 46,9% | 63,4% | 15,4% |
| 2024 | 51,7% | 57,8% | 14,8% |
| 2025 | 59,2% | 56,5% | 14,2% |
| 2026 (até 22/06) | 82,1% | 61,0% | 15,5% |

A troca de `google_news` por `wordpress` em 2023–2026 é a republicação contada uma vez (medida de 09/11/2026): a cópia mais cedo vence (E10), e a coleta passou a entregar a cópia da `wordpress` de várias matérias.

## 4. Contagens do JSON do dataset

| Chave | r3 (`c954…`) | r5 (`9f52…`) |
|---|---|---|
| Notícias lidas | 546.621 | 529.793 |
| Preparadas | 460.946 | 460.077 |
| Repetidas por `id` | 63.526 | 62.192 |
| Cópias por título | 5.985 | 5.746 |
| Cópias por título no mesmo dia | 15.189 | 999 |
| Cópias por título em ±1 dia | 184 | 212 |
| Cópias por URL | 263 | 147 |
| Sem horário | 217.941 | 217.512 |
| `meia_noite_pacifico` (N1-A) | 254 | 50 |
| Pré-abertura | 34.104 | 33.865 |
| Fora do calendário | 528 | 420 |
| Ignoradas por papel `errada` | 39.515 | 38.950 |
| Papel vazio | 1.343 | 0 |
| Linhas / pregões | 119.678 / 1.707 | 119.823 / 1.709 |

As cópias "no mesmo dia" caem de 15.189 para 999 porque a coleta passou a remover as republicações na entrega (medida de 09/11/2026). Papel vazio = 0: todas as notícias têm julgamento da juíza.

## 5. Medida formal (regra "rank E bruto")

`docs/medida_dados_novos_2026-11-10.md` (congelado `c954…`, novo `9f52…`, protocolo congelado da rodada 3):

| Grupo | Linhas mudadas | Fração | Medida de 09/11, regra refinada |
|---|---|---|---|
| Total | 42.682 | 45,17% | 44,88% (42.407) |
| Preço e bloco A | 10.213 | 10,81% | 10,34% (9.765) |
| Notícias | 32.645 | 34,55% | 34,55% (32.645) |
| Alvo | 2 | 0,002% | 0,002% (2) |

| Ano | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Fração de linhas mudadas | 65,1% | 0,2% | 43,4% | 59,5% | 36,6% | 88,7% |

Decisão da regra: nova rodada (já decidida em 09/11). A regra D7 pede parar (preço e alvo 10,81% > 1%).

## 6. D7: o que mudou no preço e por quê

Comparação direta dos CSVs, valores brutos, diferença absoluta > 1e-6. Tabelas completas em `C:\Users\danie\AppData\Local\Temp\claude\e42aeef0c247a8f6\943bdbcd-0382-4d0f-bdb1-a2cbcce98127\scratchpad\d7_1dia.md` e `d7_raiz.txt`. "Ontem" é o dataset da medida de 09/11 (sha `7c9d305b…`, gerado depois do daily de 09/11).

| Causa | Já conhecida (D7 aceita em 09/11)? | Onde |
|---|---|---|
| Pregão de 20/11/2020 nas janelas de 252 pregões | Sim | `beta` e `mom_12_1` em 2021 (`ret_idio_5d` acompanha) |
| Ruído do float32 na regravação diária | Sim | Todas as ações; fora da RAIZ4, no máximo 7e-6 (`beta`), nenhuma célula acima de 1e-5 nas colunas do modelo |
| **Ajuste de proventos da RAIZ4 regravado no daily de 10/11** | **Não: causa nova** | RAIZ4, de 2023 a 2025 |

**A causa nova.** Entre ontem e hoje, o `fechamento_ajustado` da RAIZ4 mudou nos 6 pregões seguintes a cada `data_com` de 2023–2024 em `v1-proventos`:

| `data_com` | Provento | Pregão | Retorno sem provento | Ontem (= c954) | Hoje | Fração do provento no ajuste de hoje |
|---|---|---|---|---|---|---|
| 16/03/2023 | 0,089066 | 17/03/2023 | −9,52% | −6,47% | −8,33% | 40,0% |
| 26/07/2023 | 0,024211 | 27/07/2023 | −3,55% | −3,00% | −3,33% | 39,9% |
| 17/10/2023 | 0,024210 | 18/10/2023 | −0,86% | −0,17% | −0,58% | 40,0% |
| 20/12/2023 | 0,129032 (JCP) | 21/12/2023 | +0,25% | +3,57% | +1,55% | 40,0% |
| 21/03/2024 | 0,016230 | 22/03/2024 | −3,13% | −2,68% | −2,95% | 40,0% |
| 02/08/2024 | 0,010014 | 05/08/2024 | 0,00% | 0,00% | +0,14% | 40,0% |

- O valor de ontem (e da rodada 3) é exatamente o ajuste padrão, fator 1 − provento ÷ fechamento anterior. Ex.: 17/03/2023, 2,47 ÷ (2,73 − 0,089066) − 1 = −6,473%.
- O de hoje equivale a usar 40% de cada provento, igual nos 6 casos. O valor em `v1-proventos` não mudou. Provável ligação com a correção RAIZ4/RAIZ55 que a coleta entregou em 09/11 (não confirmado).
- Efeito no dataset: `ret_1d`, `salto_abertura` e `ret_t1` nesses 6 pregões (até 2,0 pontos percentuais), as janelas que os contêm (`ret_5d`, `ret_20d`, `volatilidade_20d`, `beta`, `mom_12_1`, `ret_idio_5d`, `dist_*_52s`, `exposicao_*`) de 2023 a 2025, e o `ret_vs_setor` das outras empresas do setor nesses dias. A RAIZ4 tem 797 linhas no desenvolvimento (02/01/2023 a 12/03/2026). No grupo de preço da medida, são as cerca de 448 linhas a mais que na medida de 09/11.
- **Alvo:** nenhum `alvo` da RAIZ4 mudou (os 6 `ret_t1` mudaram sem trocar de lado frente ao IBOV). Mudaram 2 `alvo_abertura` da RAIZ4 (complementar, fora do modelo).

**Os 2 `alvo` mudados contra o `c954…`:** BRAP4 em 16/02/2023 (`ret_t1` −0,0054774 × IBOV −0,0054775) e ALOS3 em 06/01/2026 (empate exato, já registrado na rodada 3). Os dois são empates com o IBOV decididos pelo ruído do float32 (limitação 15 de `docs/regras_dataset.md`). A SBSP3 em 12/08/2024, que mudou na medida de 09/11, voltou ao valor do `c954…`.

**Decisão do usuário (10/11/2026, PARADA 1): D7 aceita.**

| Tema | Decisão |
|---|---|
| Causa nova | Ajuste do `fechamento_ajustado` da RAIZ4 com 40% do provento nos 6 pregões após cada `data_com` de 2023–2024, regravado no daily de 10/11/2026 |
| Tamanho | 1 ação, ~0,5% das linhas do desenvolvimento; nenhum `alvo` muda |
| Tratamento | Limitação registrada; o preço não é corrigido pelo processamento. A coleta é avisada |
| Se a coleta corrigir | A mudança fica abaixo de 1% na regra da D5 (nota da D5, seção 8 do protocolo): a rodada 5 continua oficial |
| Demais causas | Ruído do float32 e pregão de 20/11/2020, como na D7 aceita em 09/11/2026 |

Ao rodar o protocolo da rodada 5, citar este arquivo no `--motivo`.

## 7. Outras colunas que mudam contra a rodada 3 (mesmas causas da medida de 09/11)

| Grupo | Causa |
|---|---|
| Colunas de notícias, `tom_setor`, `tom_mercado` | Republicações contadas uma vez e julgamentos novos da juíza (papel vazio 1.343 → 0; `errada` 39.515 → 38.950) |
| `dia_resultado`, `dias_desde_resultado`, `var_lucro_aa` | Balanços novos e a `situacao` `individual` (ex.: ASAI3, SBSP3, BRAP4, BBSE3) |
| `momento_setor_5d`, `exposicao_small` (fora do modelo) | Ruído do float32 e o pregão de 20/11/2020, como no preço |
