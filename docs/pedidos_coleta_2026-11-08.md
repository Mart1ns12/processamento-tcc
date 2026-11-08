# Pedidos à coleta — 08/11/2026

Fontes conferidas (só leitura): `processamento/config/pedidos_coleta.yaml`, `docs/diagnostico_banco.md`
(gerado em 08/11/2026 13:58), banco `tcc_scraper` via `fontes.executar_leitura` (sessão READ ONLY
conferida: `transaction_read_only = 1`) e a última publicação `saida/2026-11-06/resumo_acao.json`
(gerado em 07/11/2026 10:56, 85 ações).

## 1. Mensagem para a coleta (WhatsApp)

```
*Pedidos à coleta – 08/11/2026*
Conferi hoje no banco e na publicação de 06/11. Só está aqui o que ainda falta.

🔴 *URGENTE (deixa indicador vazio no painel)*

*1. Raízen: RAIZ4 → RAIZ55 desde 03/11*
(cotação por lote de 100, Ofício Circular B3 022/2026-VPE)
- Os preços continuam como RAIZ4 e pularam de R$ 0,30 (30/10) para R$ 27,10 (03/11), sem ajuste no fechamento_ajustado (vira um retorno de +8.900% em um dia).
- O cadastro da B3 já traz só RAIZ55, mas v1-mudancas_ticker não tem RAIZ4 → RAIZ55.
- *Pergunta:* depois de 03/11 vocês vão dividir o preço por 100 (para continuar por ação) ou só registrar a troca de ticker? Se for só a troca, o histórico ajustado de antes precisa ser corrigido.
- *Aumento de capital* (sem direito a partir de 09/11): v1-eventos_acoes não tem nenhuma linha da Raízen e hoje só tem desdobramento, grupamento e bonificação. Como vão registrar? E em v1-acoes_emitidas a quantidade nova entra só no próximo ITR?
- *Conferir:* em v1-acoes_emitidas o 2T26 (30/06/2026) caiu de 8,99 bi ON / 1,36 bi PN para 4,50 bi ON / 60,8 mi PN, sem nenhum evento. Está certo?

*2. Lucro e PL de bancos e seguradoras* (v1-balancos)
- Banco do Brasil (BBAS3): lucro_liquido e patrimonio_liquido vazios em todas as 29 linhas (DFP 2020 até ITR 2T26).
- Bradesco (BBDC3/BBDC4): os dois vazios em todas as 31 linhas (DFP 2020 até ITR 3T26).
- BB Seguridade (BBSE3): lucro_liquido vazio nas 39 linhas (1T20 a 2T26); receita_liquida veio 0. O PL veio.
- IRB (IRBR3): lucro_liquido vazio nas 39 linhas (1T20 a 2T26). O PL veio.

*3. Santander (SANB11)*
Não é só a DFP 2025: todas as DFPs (2020 a 2025) e o ITR 3T20 vieram com lucro_liquido e patrimonio_liquido vazios. Os ITRs estão ok.

*4. TIM (TIMS3)*
- ITR 1T24, 2T24, 3T24 e DFP 2024 e 2025 com tudo zerado (receita, lucro, PL, ebit, caixa, empréstimos).
- Os ITRs de 2025 (1T25 a 3T25) não existem no banco. Também faltam os ITRs de 2020 e o 1T22.
Isso derruba a TIM e as medianas do setor da Vivo.

*5. Assaí (ASAI3)*
Só há balanços de 1T20 a 3T21 (11 linhas). Falta tudo do 4T21 em diante (DFP 2021 a 2025 e ITRs até 2026).

*6. Bradespar (BRAP4)*
O último balanço é a DFP 2023. Faltam ITRs e DFPs de 2024, 2025 e 2026.

*7. Empréstimos zerados* (é real ou falta dado, ex.: debêntures?)
- Allos (ALOS3): curto e longo prazo = 0 em 34 de 39 linhas (só os ITRs de 2021 têm valor).
- Odontoprev (SAUD3): curto e longo = 0 em todas as 41 linhas.
- Locaweb (LWSA3): longo = 0 desde a DFP 2023; curto também = 0 desde o 1T25.

🟡 *IMPORTANTE*

*8. Ações emitidas × eventos (38 linhas não batem)*
- Azul (AZUL3), 25 linhas de 1T20 a 1T26: a base atual não fecha com os grupamentos de 18/02/2026 (fator 0,013333) e 17/04/2026 (fator gravado 0,000007). Pelo 1T26 (5,47 tri de ações → base 365 mi) o fator real parece 1/150.000 = 0,0000066667: dá para gravar com mais casas? E nas linhas até 4T25 a base dá uns 26% a 30% da quantidade, o que não bate com os eventos: como foi calculada?
- Copel (CPLE3), 1T20, 2T20 e 3T20: a base é 5,77× a quantidade, mas o único evento depois é o desdobramento ×10 de 11/03/2021.
- Outras 10 linhas (BB 1T24, Locaweb 4T20, Vivo 1T25, Direcional 2T25, BTG 4T20, Gerdau 1T24, Sabesp 1T26, Cosan 1T21, Totvs 1T20, WEG 1T21): o evento caiu entre o fim do período e a entrega do documento e vocês aplicaram o fator. Só confirmar: a quantidade do ITR/DFP é sempre a da data de referência, mesmo entregue depois do evento? (O BTG 4T20 foi entregue só em 23/12/2024.)

*9. Juíza nas notícias que ficaram para trás*
1.343 linhas (825 notícias) sem papel, tipo_conteudo, evento e qualidade. Todas do Google News:
- publicadas em mar/2026: 1.219 linhas (771 notícias), coletadas de 22/09 a 20/10/2026;
- abr/2026: 2 linhas (1 notícia), coletada em 22/09;
- out/2026: 122 linhas (53 notícias), coletadas em 26 e 27/10.

*10. Hora das notícias*
- 786 notícias do Google News de 2026 com hora exatamente meia-noite de Los Angeles (04h ou 05h de Brasília) e sem a marca 'só data': 771 de mar/2026 (o mesmo lote do item 9), 6 de jan, 6 de fev, 1 de abr e 2 de nov (04 e 05/11, então ainda acontece na coleta diária). Pedido: gravar como 'só data' (hora vazia + published_precision = 'date') ou trazer a hora real.
- 3 notícias sem hora e sem a marca (raw_articles diz 'datetime'): n029732 (BEEF3, 04/05/2026), n120786 (SMTO3, 28/04/2026) e n160066 (BEEF3, 04/05/2026), todas InfoMoney.

*11. EBITDA nos balanços*
Não existe a coluna ebitda. Serve também completar depreciacao_amortizacao nas não financeiras (o ebit já está completo). Vazia hoje em: Bradespar (todas as 24 linhas), GMAT3 1T20 a 3T21 (9), AURE3 1T21 a 2T22 (7) e 1 linha em BRAV3 2T20, LREN3 1T21, RECV3 1T21, TIMS3 2T22, SBSP3 3T23, JBSS32 2T25 e NATU3 2T25. Fora a TIM zerada do item 4.

*12. JBS (JBSS32), opcional*
Depois de 06/2025 só há 1 provento: data_com 18/05/2026 (4,276358, pago em 22/06/2026). Está completo? O valor é por BDR ou por ação da JBS N.V., e em que moeda? Qual a razão BDR/ação? Sem isso P/L, P/VP, DY, payout e proventos da JBS ficam indisponíveis.

🟢 *DETALHES*
- Preços em 20/11/2020 (sem pregão na B3): JBSS32 e NATU3 têm linha nesse dia. Dá para apagar?
- IVVB11: falta o pregão de 24/10/2025 (tem 23 e 27/10). Foi suspensão ou falha?
- 3 notícias com título vazio: n326413 (GGBR4, 21/11/2024), n380792 (SANB11, 26/10/2023) e n395868 (ABEV3, 22/11/2022). Todas Google News, fonte "Página 3".
- Proventos: data_pagamento vazia em 8.045 de 8.433 (95%). Vazia em todos com data_com até set/2025; preenchida quase sempre a partir de nov/2025. Dá para preencher o histórico (pelo menos 2020 a 2025)?

Obrigado!
```

## 2. Evidência por pedido

### Situação dos pedidos do YAML

| id | situação em 08/11 | evidência |
|---|---|---|
| google_news_2025 | parece entregue | §15: jan–jul/2025 com 1.611–2.039 artigos/mês do Google News; nenhum mês abaixo de 25% da mediana |
| finbert_juiza_cvm | parece entregue | §5: 586.136 linhas ok, 0 sem probabilidade |
| qtd_base_preco | entregue | §2: colunas qtd_*_base_atual existem; v1-eventos_acoes existe |
| cvm_2023_2025 | parece entregue | §5/§15: cvm_ipe 2023 = 3.704; 2025 = 3.687, com todos os meses de jan–jul/2025 |
| emissores_jbs_natura | entregue | §11: JBSS32 com 2 emissores, NATU3 com 3 |
| hapvida_ifrs17 | entregue | §6: 12 linhas situacao = ajuste_ifrs17 |
| indices_completos | entregue | §3: IDIV, IFIX e SMLL desde 2019-12-30 |
| juiza_historico | **pendente** | 1.343 nulos de papel = 0,2% (limite 0,1%) — item 9 |
| raiz4_raiz55 | **pendente** | divergência other_codes (§ divergências); v1-mudancas_ticker sem RAIZ |
| ebitda_balancos | **pendente** | v1-balancos tem 16 colunas, sem ebitda — item 11 |
| acoes_sem_evento | **pendente** (ampliado) | §12: 38 linhas (Azul 25, Copel 3, outras 10) — item 8 |
| linha_sem_pregao | **pendente** | §7: JBSS32 e NATU3 em 2020-11-20 |
| balanco_bancos_seguradoras | **pendente** | item 2 |
| dfp_2025_santander | **pendente** (maior que o pedido) | DFPs 2020–2025 + ITR 3T20 com LL e PL nulos |
| balancos_assai | **pendente** | 11 linhas, 2020-03-31 a 2021-09-30 |
| balancos_bradespar | **pendente** | 24 linhas, até 2023-12-31 |
| balancos_tim | **pendente** (maior que o pedido) | zeros em 1T24–3T24, DFP 2024 e DFP 2025; ITRs de 2025 ausentes |
| emprestimos_zerados | **pendente** | item 7 |
| proventos_bdr_jbs | **pendente** (opcional) | item 12 |

Novos (não estavam no YAML): 786 notícias com meia-noite de Los Angeles sem marca (§5), 3 sem hora e sem
marca (divergência 1), 3 títulos vazios (§16), IVVB11 em 24/10/2025 (§7), data_pagamento (§16),
quantidade da Raízen no 2T26, precisão do fator da Azul, ITRs de 2025 da TIM ausentes.

### Consultas (resumo)

- **Raízen** (33453598000123): v1-precos RAIZ4 30/10 = 0,30 → 03/11 = 27,10 → 06/11 = 28,00, ajustado
  igual ao fechamento; v1-raw_b3_cadastro other_codes = ["RAIZ55"] (fetched 08/11 11:15);
  v1-mudancas_ticker e v1-eventos_acoes sem linhas da Raízen; tipos de evento existentes: DESDOBRAMENTO (67),
  BONIFICACAO (61), GRUPAMENTO (49). v1-acoes_emitidas: 1T25–1T26 = 8.993.572.584 ON / 1.358.936.900 PN;
  2T26 = 4.496.786.292 ON / 60.810.825 PN.
- **Notícias sem juíza**: as 1.343 linhas têm também tipo_conteudo, evento e qualidade nulos. As 771 notícias
  de mar/2026 sem papel são exatamente as 771 com meia-noite de Los Angeles nesse mês.
- **data_pagamento**: 100% vazia para data_com de 2019 a 2024; 2025: 289 de 422 vazias (jan–set todas vazias,
  out 3/12, nov 2/41, dez 2/87); 2026: 0 de 255.
- **38 linhas de ações**: nas 10 empresas "comuns" o evento tem data_com entre data_referencia e data_entrega
  e a razão base/quantidade é exatamente o fator (BB ×2 em 15/04/2024, LWSA ×4 em 29/01/2021, VIVT ×2 em
  14/04/2025, DIRR ×3 em 08/08/2025, BPAC ×4 em 30/06/2021, GGBR ×1,2 em 17/04/2024, SBSP ×5 em 28/04/2026,
  CSAN ×4 em 05/05/2021, TOTS ×3 em 30/04/2020, WEGE ×2 em 27/04/2021). A checagem do §12 usa os fatores
  posteriores à **entrega**; a coleta aplicou os posteriores à **referência**.

## 3. Indicadores "indisponivel" na publicação de 06/11 e o dado que resolve

Contagem na publicação: 4.654 ok, 141 nao_se_aplica, 109 indisponivel, 78 lucro_negativo,
14 historico_insuficiente. `nao_se_aplica` (bancos sem margem/EBITDA/dívida) e `lucro_negativo` não
dependem da coleta.

| empresa | indicadores indisponíveis | dado da coleta que resolve |
|---|---|---|
| ASAI3 | P/L, P/VP, ROE, payout, margem bruta e líquida, EBITDA 12m e margem, dívida líquida, DL/PL, DL/EBITDA, caixa líquido, balanço de referência | balanços do 4T21 em diante (item 5) |
| BRAP4 | P/L, P/VP, ROE, payout, margens, EBITDA, endividamento (4) | balanços de 2024 a 2026 (item 6) |
| BBAS3, BBDC3, BBDC4 | P/L, P/VP, ROE, payout, payout por ano (5 anos) | lucro_liquido e patrimonio_liquido (item 2) |
| BBSE3, IRBR3 | P/L, ROE, payout, payout por ano (5 anos) | lucro_liquido (item 2) |
| SANB11 | P/L, ROE, payout, payout por ano (5 anos) | LL e PL das DFPs 2020–2025 (item 3) |
| JBSS32 | P/L, P/VP, DY, payout, proventos por ano (5 anos) | razão BDR/ação e proventos da N.V. (item 12, regra D9) |
| ALOS3, SAUD3, LWSA3 | dívida líquida, DL/PL, DL/EBITDA, caixa líquido | confirmar/completar empréstimos (item 7) |
| TIMS3 | P/L, ROE, payout, margens, EBITDA, DL/EBITDA (como historico_insuficiente) | balanços 2024–2025 da TIM (item 4) |
| VIVT3 | medianas do setor: P/L, ROE, payout, margens, EBITDA, DL/EBITDA | balanços da TIM (único par do setor) |
| TOTS3 | medianas do setor: P/L, payout, DL/PL, DL/EBITDA | em parte, empréstimos da LWSA3 (único par); o P/L e o payout do setor seguem vazios enquanto a LWSA3 tiver lucro negativo |
| IGTI11 | payout de 2021 | não identificado como dado da coleta (ver seção 4) |

## 4. Só para nós (não vai para a coleta)

- **"Exclusão a rever: 06057223000171 tem balanço" (§9):** é o Assaí. Ele está em
  `processamento/config/exclusoes.yaml` → `cnpjs_sem_balanco`, mas tem 11 balanços (1T20 a 3T21) no banco
  — o comentário do YAML diz "só 3 ITRs de 2021", o que não confere. É ajuste nosso (comentário/decisão da
  exclusão); a única ligação com a coleta é o pedido do item 5: quando os balanços do 4T21 em diante
  chegarem, tirar o CNPJ da lista.
- §15 avisa "período sem coleta com notícias normais em 2025-01 a 2025-07": rever
  `experimento.periodos_sem_coleta` (o Google News de 2025 parece entregue).
- IGTI11: payout de 2021 indisponível com DFP 2021 presente (LL 346 mi) e proventos de IGTI11 desde
  07/2020; investigar no cálculo antes de pedir algo.
- Atualizar `pedidos_coleta.yaml` quando o diagnóstico confirmar: os 7 pedidos "parece entregue" e os
  textos de dfp_2025_santander, balancos_tim e acoes_sem_evento (escopo maior que o registrado). Nada foi
  alterado nesta conferência.
