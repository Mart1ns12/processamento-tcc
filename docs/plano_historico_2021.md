# Plano: histórico desde 2021 (26/10/2026)

Contexto: a coleta carregou histórico novo em 26/10/2026 (índices, balanços e ações emitidas desde 2021; notícias desde 2023).
O diagnóstico de 26/10 (11:50) mostrou os pontos abaixo. Plano aprovado pelo usuário em 26/10/2026 com as decisões
marcadas em cada item. O dataset do experimento **não** é regerado nesta etapa (fica para depois).

Números conferidos no banco em 26/10/2026, só leitura (`fontes.executar_leitura`).

---

## 1. Períodos inválidos em `v1-balancos`

| Empresa | CNPJ | data_fim_periodo | Tipo | Período | O que é |
|---|---|---|---|---|---|
| PetroReconcavo (RECV3) | 03342704000130 | 2021-03-31 | ITR | outro (01/03 a 31/03, 31 dias) | Linha lixo: um mês, receita e lucro 0 |
| Lojas Renner (LREN3) | 92754738000162 | 2021-03-31 | ITR | outro (01/03 a 31/03, 31 dias) | Idem |
| Azzas 2154 (AZZA3) | 16590234000176 | 2021-12-31 | ITR | 12m (01/01 a 31/12) | Cópia da DFP 2021, entregue em 10/03/2022 (DFP em 11/03); há também ITR do 4T (3m) com o mesmo valor de DFP − 9m |

**Como era:** `trimestres_isolados`/`doze_meses` já descartavam o "outro" (`_com_meses`); a ITR 12m da Azzas não mudava
valor (a linha de 3m do 4T vem primeiro). Mas `referencia` e `estoques_no_fim` não filtravam o tamanho do período:
se a linha certa tivesse uma conta vazia, o 0 da linha lixo de mesmo fim entraria como `ok` (zero no lugar de vazio).
Efeito nos pacotes de hoje: nenhum (tudo de 2021).

**Regra (aprovada):** linha de balanço com período inválido é descartada antes de qualquer conta: ITR só vale com 3, 6
ou 9 meses; DFP só com 12 meses (classes de `diagnostico.regras.classificar_dias_periodo`). Aplicada em
`fatos/trimestres.entregues_ate` (por onde passam referência, estoques, trimestres, 12 meses e payout) e em
`experimento/resultados.dias_de_resultado`. No diagnóstico, essas linhas viram **nota** ("descartadas pelo
processamento", com a lista cnpj, tipo, início, fim, dias), não divergência. DFP fora de 12m também vira nota.

**Testes (valores esperados):**
- ITR 2021-01-01 a 2021-03-31 (receita 100, caixa vazio) + ITR 2021-03-01 a 2021-03-31 (tudo 0), entregues em 2021-05-10:
  em t = 2021-06-01, trimestre de 2021-03-31 com receita 100; `estoques_no_fim(...)["caixa"]` = (NaN, `indisponivel`)
  (antes: (0.0, `ok`)); `entregues_ate` não traz a linha de 31 dias.
- DFP 2021 (receita 400, entrega 2022-03-11) + ITR 2021-01-01 a 2021-12-31 (receita 400, entrega 2022-03-10) + ITR do 4T
  2021-10-01 a 2021-12-31 (receita 100, entrega 2022-03-10) + ITRs de 3m, 6m e 9m de 2021: em t = 2022-03-10, `entregues_ate`
  não traz a ITR de 12m; o trimestre de 2021-12-31 vale 100; nenhuma linha de 12 meses entregue (payout por ano sem 2021);
  em t = 2022-03-11 a DFP aparece.
- `dias_de_resultado`: linha de período inválido não gera dia de resultado sozinha.
- Diagnóstico: ITR "12m"/"outro" e DFP fora de 12m saem como nota com a lista, não como divergência.

## 2. Exclusões a rever (`cnpjs_sem_balanco`)

Atenção: 06057223000171 é o **Assaí (ASAI3)**; a **Bradespar (BRAP4)** é 03847461000192.

- Bradespar: 18 linhas, 1T21 até a DFP 2023 (última entrega 27/03/2024); nada de 2024–2026. Receita 0 (holding),
  empréstimos CP e LP 0, quantidade de ações em milhares.
- Assaí: só 5 linhas (1T21 a 3T21, entrega até 28/10/2021). Parece falha da coleta.

**Decisão:** tirar **só a Bradespar** do `exclusoes.yaml`; o Assaí fica. Pedidos à coleta na seção 10.

**O que muda nos pacotes da BRAP4** (simulado em memória para t = 23/10/2026):

| Campo | Antes | Depois |
|---|---|---|
| `resumo_acao`: P/L, P/VP, ROE, margens, EBITDA, endividamento, payout | `indisponivel` (exclusão) | `indisponivel` (balanço velho: referência 31/12/2023 vale até 31/03/2025) |
| `balanco_referencia` | vazio | 2023-12-31 (entrega 2024-03-27) |
| `fundamentos_trimestrais` | nada | 8 trimestres (1T22 a 4T23): receita 0, lucro, ROE 0,24 a 0,95; margens, EBITDA, endividamento e payout `indisponivel` |
| `payout_por_ano` | vazio | 2021 a 2023 `indisponivel` (quantidade de ações suspeita) |
| Medianas do setor, experimento | — | sem mudança |

## 3. Notícias sem probabilidade do FinBERT

Em 26/10/2026 (leitura após o diagnóstico): **0** notícias sem probabilidade (264.623 linhas; a coleta preencheu as 13.248).
Linhas do dataset afetadas hoje: 0.

O experimento já trata a notícia sem probabilidade como **ausente** (score NaN; tom, extremo, `tom_setor`, `tom_mercado`
ignoram; `mudanca_tom` conta só notícias com score). `noticias_dia_qtd` conta todas as notícias (mantido).
O painel continua rígido: uma notícia sem probabilidade deixa o resumo do dia `indisponivel` (mantido).

**Mudanças (aprovadas):**
- Repetidas (E10): entre as cópias de uma mesma notícia, fica a mais cedo **entre as que têm probabilidade**; sem nenhuma
  com probabilidade, a mais cedo (como antes). Vale para o experimento e o painel (mesma função).
- JSON do dataset ganha `sem_probabilidade` (notícias preparadas com score vazio).
- `execucao` ganha aviso quando `sem_probabilidade > 0`.

**Testes:** janela com scores 0,4, −0,2 e vazio → qtd 3, tom 0,1, extremo 0,4. `mudanca_tom` com 5 notícias com score + 2 sem
→ tem valor; com 4 com score + 3 sem → vazia. Repetidas: cópia das 09:00 sem probabilidade e das 10:00 com → fica a das
10:00; duas sem probabilidade → fica a mais cedo. Contagem no JSON e aviso no `execucao`.

## 4. Calendário 2021–2022

Coberto: horários contínuos de 04/11/2019 a 31/12/2027, quartas de cinzas 2020–2027, feriados de 31/12/2019 a 12/10/2026
conferidos com a B3 e com o banco. Nada a acrescentar.

**Mudanças:** casos novos em `tests/test_calendario.py` para as trocas 2021-03-15, 2022-03-14, 2022-11-07 e 2023-03-13
(e o dia anterior de cada uma); rodar uma vez `PROC_TESTES_COM_BANCO=1 pytest -q -m banco tests/test_calendario_feriados.py`.

Comportamento que mudou com o histórico novo (sem código novo): base 100 de CDI, IPCA, IDIV, SMLL e IFIX reancorada em 2021
(fator constante: CDI +4,4%, IPCA +10,4%, IDIV ≈ −6,7%, SMLL −18,1%, IFIX ≈ −2,5%; % das janelas iguais; reenvio inteiro uma
vez, já no pacote de 26/10); experimento passa a começar em 2023 (cobertura de notícias) quando o dataset for regerado.

## 5. `indice_retorno_total` mudando na 7ª casa

Nosso código é todo float64. O float32 vem da coleta: `fechamento_ajustado` gravado como float32 dentro de um double
(ex.: PETR4 `58.68000030517578`) e regravado todo dia. Medido entre as cargas completas de 23/10 e 26/10 (mesmo t):
152 de 177 séries mudaram (21 só por fator constante, a âncora; 131 também na forma, até 7e-7); IBOV e IVVB11, 0.
Com a tolerância de 1e-9 em `pacote_series._mesmo`, quase toda série ia inteira (`substituir_serie`) todo dia.

**Decisão:** só a tolerância `saida.tolerancia_serie_relativa: 1e-6` (parametros.yaml) em `_mesmo`; a âncora continua no
1º dia da série. Pedido à coleta: gravar o ajustado em float64.

**Testes:** ponto × (1 + 7e-7) → série não vai inteira; × (1 + 2e-6) → vai com `substituir_serie`; status diferente → vai;
parâmetro ausente, negativo ou não numérico → erro legível.

**Experimento:** retornos são razão de dois preços (a âncora não entra); ruído ~1e-7. No dataset de 23/10, 11 de 117.364
linhas têm |ret_t1 − ret_ibov_t1| < 1e-6 (2 abaixo de 1e-7): o alvo delas pode trocar a cada regeração, e o sha256 do
dataset muda mesmo sem dado novo. Registrado como limitação (seção 10).

---

## Ordem e verificação
1 → 2 → 3 → 4 → 5; especificação atualizada (3.4, 6, 8.1, 9, 10); `pytest -q` sem falhas; sem commit.
