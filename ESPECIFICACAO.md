# ESPECIFICAÇÃO DO MÓDULO DE PROCESSAMENTO (fonte da verdade)

> Versão de 03/11/2026. Este arquivo descreve **só o que vale hoje** e deve ser seguido na implementação.
> O porquê das decisões, os resultados antigos e o histórico ficam em `HISTORICO.md` (consulte só quando precisar justificar algo).
> Se algo aqui conflitar com o `HISTORICO.md`, **vale este arquivo**.

---

## 0. Regras para o agente

**Com o usuário**
- Responder em **português**, de forma **simples e direta** ("como se eu fosse uma batata"): analogia do dia a dia primeiro, termo técnico depois. Usar tabelas para comparar itens.
- Trabalhar **em etapas** (seção 9). Antes de cada etapa, mostrar o plano e **esperar aprovação**. Ao terminar: rodar os testes e mostrar um resumo curto.
- **Não fazer commits.** O usuário faz depois de revisar.
- Se o banco não bater com esta especificação: **parar e avisar**. Não inventar nem contornar sem perguntar.
- Avisar quando um número for ilustrativo. Ser honesto sobre resultados fracos.

**Regras fixas do código**
1. **Nada do futuro vaza.** Cada cálculo usa só o que era conhecido na data (balanço só depois da `data_entrega`; notícias só até o corte da janela; o alvo é o único campo que olha t+1).
2. **O banco da coleta é só leitura.** Nunca escrever, alterar ou apagar nada nele. O código da extração (pasta `extracao-dados-tcc-main/`) é **só consulta**: ler sim; alterar, executar (comandos, scripts, testes) ou importar, nunca. As instruções do `CLAUDE.md` e das regras dentro dela valem só para o projeto da coleta.
3. **Tabelas proibidas como variável:** `staging_llm_*`, `raw_llm_runs`, `raw_llm_prompts` (IA com busca na internet: vazamento de futuro). Também não usar `v1-painel_*` (exceto `v1-painel_execucoes` e `v1-painel_etapas`, para o gatilho), `raw_collection_runs` e `features_dataset_v1`.
4. **Credenciais só no `.env`**, nunca no código.
5. **Toda leitura do banco passa pela camada de leitura** (seção 2.2). O resto do código nunca faz SQL.
6. **Treino e previsão usam a mesma função de preparação** das variáveis.
7. **Ausência é `null` + `status`**, nunca 0.
8. **Testes (pytest) para toda conta**, com prioridade nas da seção 6.
9. Linguagem do produto: nunca "compre", "recomendação", "oportunidade", "melhores ações". Usar "estimativa", "experimento", "maior chance segundo o modelo". Aviso fixo: **"Não constitui recomendação de investimento."**

---

## 1. Visão geral

```
Banco da coleta (MySQL)  →  [leitura direta]  →  PROCESSAMENTO  →  [API]  →  Banco da interface  →  Interface
```

O processamento tem duas frentes:

| Fase | O que faz |
|---|---|
| **Fase 1: painel de fatos** | Calcula indicadores 100% confirmados (cotação, rentabilidade, comparações, risco, valuation, dividendos). **Nenhuma previsão** |
| **Fase 2: experimento** | XGBoost + sentimento do FinBERT estimam quais ações têm maior chance de **superar o Ibovespa no próximo pregão**. Mostrado como **"5 ações com maior chance de superar o Ibovespa (experimento)"**, com selo "em avaliação" e histórico de acertos contra o acaso |

**Pergunta do TCC:** o sentimento das notícias, lido pelo FinBERT, ajuda a prever o desempenho das ações? Foco nas **notícias do dia t e da noite, até as 8h de t+1** (antes da abertura do pregão previsto). Como a maioria das notícias do Google News só tem a data (cerca de 90% por ano; só a `wordpress` tem hora em tudo, seção 7.2), não dá para isolar as publicadas depois do fechamento; esse efeito é medido num teste extra só com as notícias de hora real (seção 7.5).

---

## 2. Arquitetura do código

### 2.1 Estrutura sugerida
```
processamento/
├── config/
│   ├── fontes.yaml          # mapa de nomes: tabela/coluna real no banco → nome do contrato
│   └── parametros.yaml      # horários, prazos, janelas, hiperparâmetros
├── fontes.py                # camada de leitura + validação + conversores (única que faz SQL; exceção: diagnostico/)
├── diagnostico/             # etapa 1: SQL próprio, executado só por fontes.executar_leitura
├── calendario.py            # pregões (datas com preço do IBOV), fechamento, janelas de notícias
├── universo.py              # ações válidas em cada data (seção 3.5)
├── fatos/                   # Fase 1
│   ├── precos.py            # cotação, variação, rentabilidade, volume, volatilidade, beta, comparações
│   ├── fundamentos.py       # 12 meses, P/L, P/VP, ROE, margens, EBITDA, endividamento, payout
│   ├── proventos.py         # yield, histórico por ano
│   ├── series.py            # séries base 100
│   ├── multiplos.py         # P/L, P/VP e yield diários
│   └── noticias.py          # notícias da janela do painel (resumo do tom e manchetes do dia)
├── experimento/             # Fase 2
│   ├── dataset.py           # variáveis + alvo (seção 7)
│   ├── preparacao.py        # ranks e tratamento (mesma função no treino e na previsão)
│   ├── treino.py            # walk-forward, modelos 1/3/3b (o modelo 2 saiu em 23/10/2026, N2-A)
│   ├── avaliacao.py         # acaso, bootstrap, top 5 (e top 3) × últimos 5, robustez por ano
│   └── previsao.py          # top 5 do dia + motivos
├── saida/                   # pacotes da seção 8 (arquivo JSON hoje; API depois): contrato.py (validador),
│                            # insumos.py (leitura cortada), textos.py, pacotes_*.py, gerar.py (python -m processamento.saida)
├── rotina/                  # gatilho diário (seção 4): parametros.py, gatilho.py, checagem.py, retreino.py, trava.py, executar.py, __main__.py
└── producao.py              # entrada em produção (seção 9, R11)
tests/                       # na raiz do projeto (pytest.ini: testpaths = tests); fixtures em tests/dados/
registros/experimento/       # na raiz do projeto (versionável): top 5 do dia e resultado (S11)
```

**Decisões de estrutura (22/10/2026):**
- A configuração fica em `processamento/config/` e os testes em `tests/`, na raiz do projeto (não dentro de `processamento/`).
- **Exceção só da etapa 1:** o SQL do diagnóstico fica em `processamento/diagnostico/`, mas é executado **só** por `fontes.executar_leitura` (com a trava de só leitura) e usa os nomes de tabela e coluna do `fontes.yaml`. Nas demais etapas, SQL só no `fontes.py`.

### 2.2 Camada de leitura (`fontes.py`)
- Entrega DataFrames **sempre no formato do contrato** (nomes da seção 3), não importa como a coleta guardou.
- **`config/fontes.yaml`** guarda o nome real de cada tabela e o "de → para" das colunas. Se a coleta mudar um nome, muda só esse arquivo.
- **Valida na leitura:** a tabela existe? Colunas obrigatórias presentes? Tipos e formatos certos (datas; ISO com fuso nas notícias)? Chave sem duplicatas? Se falhar, **para com uma mensagem legível** ("tabela X sem a coluna Y").
- **Conversores** para formatos alternativos conhecidos (ver 3.5), cada um com teste.
- Nomes de tabela com hífen exigem crase no SQL: `` `v1-precos` ``.
- **Conexão:** lida do `.env` na raiz do projeto, com os mesmos nomes de variáveis da coleta: `IP_BANCO`, `PORTA_BANCO`, `NOME_BANCO` (`tcc_scraper`), `USER_BANCO`, `SENHA_BANCO`. Usuário de preferência **só de leitura**. Manter um `.env.example` com os nomes, sem valores. O `.env` nunca vai para o git.

---

## 3. Entrada: o banco da coleta

### 3.1 As 8 tabelas do contrato
Nomes reais (com crase): `v1-noticias`, `v1-precos`, `v1-cadastro`, `v1-mudancas_ticker`, `v1-balancos`, `v1-acoes_emitidas`, `v1-proventos`, `v1-indices`. Nenhuma tem `atualizado_em`.

| Tabela | Chave | Colunas usadas | O que saber |
|---|---|---|---|
| `v1-noticias` | `id`, `ticker` | `id`, `ticker`, `data_hora_publicacao`, `data_hora_coleta`, `titulo`, `fonte`, `link`, `prob_positivo`, `prob_neutro`, `prob_negativo`, `origem`, `papel`, `tipo_conteudo` | Datas são **texto ISO com fuso de São Paulo** (converter e validar). `data_hora_publicacao` vazia nos documentos da CVM (`origem = cvm_ipe`, só com a data). **Ignorar `momento_pregao`** (usa 18h fixo); calcular a própria janela. `papel`/`tipo_conteudo`/`evento`/`qualidade` vêm de uma IA sem busca ("juíza"), ainda não avaliada; filtro desligado na coleta (entram panoramas e opiniões). **`papel = 'errada'` sai na leitura (decidido em 01/11/2026):** `papeis_ignorados` no `fontes.yaml`, aplicado em `fontes.tratar_noticias_lidas`, antes das repetidas; vale igual para o dataset (todas as versões), a rotina e o `noticias_dia`. Notícia sem julgamento (`papel` vazio) fica. **Origens (decidido em 01/11/2026):** `google_news`, `cvm_ipe` e `wordpress` entram por igual, acumulando fontes para a maior cobertura possível; cópias da mesma matéria entre origens contam uma vez (E10). A `wordpress` (Money Times, InfoMoney e Exame; 2021, 2022, 03/2026 e desde 10/2026; nada em 2023–2025) foi liberada por decisão do usuário, com a coleta confirmando a fonte (a amostra manual de `docs/validacao_wordpress.md` não foi revisada). `origens_ignoradas` no `fontes.yaml` fica **vazia**: é o mecanismo para uma fonte futura ser aceita na leitura e descartada logo depois, com aviso no `execucao` e nota no diagnóstico |
| `v1-precos` | `data`, `ticker` | todas | `fechamento` = sem dividendos (ajustado só por desdobramento); `fechamento_ajustado` = com dividendos. Inclui `IBOV`, `USDBRL`, `BRENT`, `IVVB11`. Volume vazio nos não-ações. **O histórico inteiro é regravado a cada dia** (o ajustado do passado pode mudar) |
| `v1-cadastro` | `ticker` | todas | `tipo_acao`: ON, PN, UNIT ou BDR. Units: KLBN11, BPAC11, ENGI11, IGTI11, SANB11, TAEE11. CRFB3 sem CNPJ nem setor |
| `v1-mudancas_ticker` | `ticker_antigo` | todas | `data_mudanca` preenchida nas 10 linhas desde 24/10/2026 (só informativa: a união dos históricos não depende dela). Troca de ação por BDR não une, salvo quando o `v1-emissores_ticker` a descreve (seção 6, "Mudança de ticker") |
| `v1-balancos` | `cnpj`, `tipo_documento`, `data_inicio_periodo`, `data_fim_periodo` | todas | Consolidado, em reais. Trimestre e acumulado do ano em linhas separadas. `data_entrega` = da última versão do documento. **Desde 22/10/2026 todas as colunas vêm preenchidas** (~90%, como `lucro_bruto`): `ebit`, `depreciacao_amortizacao` (sempre positiva), `emprestimos_*`, `caixa`, `aplicacoes_financeiras`; vazias nos bancos e seguradoras. Zeros suspeitos em `emprestimos_*` e `aplicacoes_financeiras`: ver seção 10. Coluna `situacao` (03/11/2026) ∈ {`ok`, `ajuste_ifrs17`, `reapresentado`, `individual`} (`valores_permitidos` no `fontes.yaml`; outro valor = erro de leitura): todas são versões válidas e entram nas contas como `ok`; o diagnóstico conta por situação (03/11/2026: 3.180 `ok`, 12 `ajuste_ifrs17`, só HAPV3, 0 `reapresentado`). **`individual` (09/11/2026; 119 linhas):** balanço individual da controladora, gravado quando a CVM não tem o consolidado ou ele vem zerado (ex.: Bradespar desde 2024) |
| `v1-acoes_emitidas` | `cnpj`, `data_referencia` | todas | `data_entrega` (sempre preenchida): a linha vale em t só se `data_entrega` ≤ t (D4). `qtd_on_base_atual`/`qtd_pn_base_atual`: quantidade na base de ações de hoje, já multiplicada pelos fatores de todos os desdobramentos, bonificações e grupamentos posteriores (e, na JBS S.A., pelo `fator_acoes` 0,5 do BDR); é a usada no valor de mercado e no payout, porque `fechamento` e proventos já vêm ajustados para trás. `qtd_on`/`qtd_pn` = quantidade da época (só diagnóstico). `situacao` ∈ {`ok`, `corrigido_escala`, `corrigido_digito`, `anulado`}; `anulado` (11 linhas) = as duas `base_atual` vazias → quantidade `indisponivel`. **PN extinta (09/11/2026):** `qtd_pn_base_atual` vazia com `qtd_on_base_atual` preenchida (73 linhas: Eletrobras 00001180000126, Azul 09305994000129, Copel 76483817000120, antes da troca de PN por ON, porque a PN deixou de existir) não é divergência: no **valor de mercado** a PN vale **zero** (`proventos.acoes_na_data`); no **payout** (12m, por ano e trimestral), evento com provento de PN e PN da base vazia deixa o payout `indisponivel` (a PN existia e recebia: zerar subestimaria), e evento só com provento de ON continua valendo. O diagnóstico só conta numa nota. ON vazia continua `indisponivel` |
| `v1-proventos` | `ticker`, `tipo`, `data_com` | todas | Valor já ajustado por desdobramento, bonificação e grupamento. Units já somadas pela composição |
| `v1-indices` | `data`, `indice` | todas | CDI em % ao dia; IPCA em % no mês; IDIV, SMLL, IFIX em pontos |

### 3.2 Tabelas auxiliares (podem ser lidas)
- `raw_articles` (`lang`, `published_precision`, `published_at` em **UTC**, `resolved_url`: endereço final da matéria no Google News, usado para achar cópias entre origens, E10); ligação: `v1-noticias.id` = `"n"` + `raw_articles.id` com zeros à esquerda (6 dígitos ou mais).
- `staging_article_sentiment` (`model`, `text_source`): modelo do FinBERT usado (`lucas-leme/FinBERT-PT-BR` para português, `ProsusAI/finbert` para inglês) e texto lido (`body` ou `title`).
- `v1-staging_noticias_julgamento`: julgamentos da juíza por versão.
- `v1-raw_ipe_docs` (`protocolo_entrega`, `cnpj`, `categoria`, `data_entrega`, `tipo_apresentacao`, `versao`): fatos relevantes, comunicados e avisos aos acionistas, um protocolo por entrega, só com a data. Lida pelo dataset e pela rotina para `fato_relevante_cvm` (7.3), com leitura estrita: tabela ausente ou sem coluna para a execução (2.2).
- `v1-raw_b3_proventos`, `v1-raw_b3_suplemento`: eventos em ações (para conferir ajustes).
- `v1-raw_b3_cadastro`: `other_codes` (JSON) = códigos de negociação **atuais** de cada empresa na B3. Define quais classes existem (seção 6, "Ação → empresa").
- `v1-painel_execucoes`, `v1-painel_etapas`: estado da coleta do dia (gatilho, seção 4).
- `v1-emissores_ticker` (03/11/2026; 90 linhas; leitura estrita, como `v1-raw_ipe_docs`): empresa emissora de cada ticker por período (`ordem`, `ticker_negociado`, `cd_cvm`, `cnpj`, `empresa`, `vigencia_inicio` vazia = sem limite, `vigencia_fim` vazia = vigente, `fator_acoes`). Vigências do mesmo ticker sobrepostas = erro de leitura. Só JBSS32 (JBS S.A. como JBSS3 até 08/06/2025, `fator_acoes` 0,5; JBS N.V. desde 09/06/2025) e NATU3 (Natura Cosméticos até 17/12/2019; holding como NTCO3 de 18/12/2019 a 01/07/2025; Natura Cosméticos desde 02/07/2025) têm mais de uma linha. Regra na seção 6.
- `v1-eventos_acoes` (03/11/2026; 177 linhas): desdobramentos, bonificações e grupamentos. **Só diagnóstico, nunca variável do modelo:** coerência de `v1-acoes_emitidas` (`base_atual` ≈ quantidade × fatores com `data_com` > `data_referencia` × `fator_acoes`, tolerância 1%, só linhas `ok`, sem bonificação com `isin_emitido` de outra classe; desde 09/11/2026 pela `data_referencia`, porque a coleta confirmou que a quantidade é a da data de referência) e retorno suspeito na data de um evento ("evento não ajustado no preço", ex.: AZUL3).

### 3.3 Regras de formato do contrato
Ticker sem `.SA`; datas `AAAA-MM-DD`; ponto decimal; vazio = `NULL` (nunca 0); balanços em reais; CNPJ só números; USDBRL em R$/US$; BRENT em US$/barril; volume em quantidade de ações.

### 3.4 Lacunas da coleta e o que o código faz enquanto isso
| Lacuna | Comportamento do processamento |
|---|---|
| EBITDA e endividamento com insumo vazio (colunas preenchidas desde 22/10/2026, mas ~10% das linhas sem valor) | `status = indisponivel` no indicador que dependia do valor vazio |
| Histórico (medido em 02/11/2026): preços, IDIV, SMLL e IFIX desde 30/12/2019; CDI, IPCA e ações emitidas desde 2021; balanços desde 2020 (08/11/2026: a coleta entregou os de 2020, 81 DFP e 378 ITR de 81 CNPJs; efeito no dataset em `docs/conferencia_rodada_003.md`, seção 5.4); notícias desde 01/2021, sem coleta em jan–jul/2025 (`experimento.periodos_sem_coleta`, E4; a maioria sem hora); documentos da CVM completos desde 2021 (03/11/2026: `experimento.periodos_sem_coleta_cvm` vazia, mecanismo mantido) | Implementar tudo. **Não treinar o modelo "para valer"** até o usuário declarar o histórico completo (`treino.modelo_oficial: true`, R7); até lá, só teste de funcionamento (sem conclusões) |
| Composição histórica do Ibovespa | Ver 3.5 |
| Troca de ação por BDR da JBS (JBSS3 → JBSS32 em 09/06/2025). Medido em 03/11/2026: `v1-precos` só tem JBSS32 (1.705 linhas desde 30/12/2019, sem salto em 06–09/06/2025); proventos da JBSS32 em R$ por BDR; balanços da JBS S.A. (26 ITR e 5 DFP, 2020–2025) e da JBS N.V. (desde 30/06/2025); CVM da JBS S.A. de 2021 a 2025 | Resolvida pelo emissor (seção 6, "Ação → empresa"): até 08/06/2025 a JBSS32 é ação ON da JBS S.A. (universo do modelo, P/L, P/VP, yield e payout, setor do cadastro; a quantidade já vem na base do BDR); desde 09/06/2025 é BDR (fora do universo e dos pares, D9). JBSS3 saiu de `exclusoes.yaml`. Limitação: no painel, as séries de setor (`SETOR_SEM`, posição percentual) usam os pares pelo tipo de hoje, então a JBSS32 não entra no setor de outras ações nem antes de 09/06/2025 |
| Natura (medido em 03/11/2026): NATU3 com 1.705 linhas desde 30/12/2019, sem retorno acima de 30% e sem os 4 dias de preço parado; balanços da holding (32785497000197) de 03/2020 a 03/2025 e da Natura Cosméticos desde 06/2025 | Resolvida pelo emissor: de 18/12/2019 a 01/07/2025 a NATU3 usa o CNPJ da holding (balanços, ações, CVM, payout); desde 02/07/2025, o da Natura Cosméticos (12 meses `historico_insuficiente` até haver 4 trimestres). NATU3 saiu de `fase1.eventos_retorno_suspeito` |
| Linha de preço fora do calendário: JBSS32 e NATU3 em 20/11/2020 | A grade de preços (calendário do IBOV) descarta; diagnóstico: nota "linha fora do calendário (conhecida, pedida à coleta)" para os pares de `precos.fora_do_pregao_conhecidas` no `fontes.yaml`; outro par continua divergência |
| Ações deslistadas sem preço nas fontes: CRFB3, SRNA3, STBP3 (decidido com a coleta em 22/10/2026) | Fora do universo **em todas as datas**. Lista em `processamento/config/exclusoes.yaml` (`tickers_excluidos`). Entra na limitação de **viés de sobrevivência** do TCC |
| Classes extintas nos proventos (ex.: VALE5, AXIA6, CPLE5) | Classe que **não aparece** no `other_codes` da empresa em `v1-raw_b3_cadastro` é **extinta hoje**, mas existiu: seus proventos são reais e **contam normalmente** no histórico de proventos e no payout, ligados à empresa pela raiz (seção 6). **Units (final 11) continuam de fora** do payout (regra da unit). "Extinta" é só informação. Decidido em 22/10/2026 pelos números do diagnóstico: AXIA5, AXIA6 e CPLE5 pagaram dentro do período analisado |
| Empresa sem balanço utilizável nas fontes: CNPJ 06057223000171 (Assaí, ASAI3: só 3 ITRs de 2021; pedido à coleta na seção 10). A Bradespar (03847461000192) saiu da lista em 26/10/2026: tem balanços de 2021 a 2023, e a regra do balanço velho cuida do resto | A empresa continua no painel de preços e no modelo; P/L, P/VP, ROE, margens, EBITDA, endividamento e payout saem com `status = indisponivel`. Lista em `exclusoes.yaml` (`cnpjs_sem_balanco`) |
| Empresa que parou de entregar balanço | Balanço de referência vencido em t (passou o fim do mês de `data_fim_periodo` + `fundamentos.balanco_idade_max_meses`, 15 meses; seção 6, "Balanço velho"): P/L, P/VP, ROE, margens, EBITDA, endividamento e payout 12m saem `indisponivel` |
| Itens acima no diagnóstico (etapa 1) | Aparecem como **nota "excluídos por decisão"**, não como divergência |

### 3.5 Universo de ações por data
- **Tabela da composição:** `` `v1-composicao_ibov` `` (criada pela coleta em 23/10/2026; preenchida em 24/10/2026: 137 linhas, 136 tickers, vigências de 01/01/2021 até hoje; fontes `paccafelipe_csv` (115 linhas, não oficial, seção 10) e `rebalanceamento` (22); 2020 não é coberto: nesses pregões vale a composição atual). Colunas reais `ticker`, `vigencia_inicio`, `vigencia_fim`, `participacao`, `fonte`, mapeadas no `fontes.yaml` para `ticker`, `data_inicio`, `data_fim`, `participacao`, `fonte` (`participacao` e `fonte` só informativas por enquanto). `vigencia_fim` vazia = ainda vigente.
- **Cobertura por data (decidido em 23/10/2026):** uma data está coberta se alguma linha tem `data_inicio ≤ data` e (`data_fim` vazio ou `≥ data`). Data coberta: só entram as ações com vigência naquela data (`universo = 'composicao_historica'`; as outras ficam `fora_da_composicao`). Data não coberta (inclusive tabela inexistente ou vazia): todas as ações do `v1-cadastro` (`tipo_acao` ON, PN ou UNIT), `universo = 'composicao_atual'`; ticker que só está na composição fica `fora_da_composicao` nessa data.
- **Aviso no `execucao`:** tabela vazia → "Composição do Ibovespa vazia: universo = composição atual (ações do cadastro)."; cobertura parcial → quantos pregões a composição cobre e o período coberto; cobertura total ou tabela inexistente → sem aviso (`universo.aviso_composicao`).
- **Conversores aceitos:** intervalos (formato pedido); "fotos" das carteiras (`data_carteira`, `ticker` → a ação entra na primeira carteira em que aparece e sai na primeira em que some); colunas de entrada e saída no cadastro.
- **Sempre (decidido em 22/10/2026):** ação **sem preço numa data** fica fora do universo **naquela data**; os `tickers_excluidos` de `exclusoes.yaml` ficam fora em **todas** as datas.
- O filtro vale para o **modelo** e para o **histórico do experimento**. O painel de fatos usa as ações atuais.
- **Mapeamento da composição (03/11/2026):** cada ticker da composição vira o atual antes do filtro: primeiro pelo `v1-emissores_ticker` (`ticker_negociado` → `ticker`: JBSS3 → JBSS32, NTCO3 → NATU3), depois pela `v1-mudancas_ticker`. O tipo da ação é o do período (seção 6).

---

## 4. Rotina diária

1. A coleta roda **uma vez por dia, às 8h** (Brasília).
2. A partir das **8h**, a cada **~5 minutos**, o processamento consulta:
   - em `v1-painel_execucoes`: o daily mais recente de hoje (`tipo = 'daily'`), com `iniciada_em` **no próprio dia e a partir das 08:00 de São Paulo**. **`iniciada_em` está em UTC**: converter para São Paulo antes de comparar data e hora. Vale **`origem` `cron` ou `manual`**; daily manual vira **nota** no pacote `execucao`. Execuções de outros tipos (ex.: `coletar`, com as etapas `cvm_itr_dfp`, `build_entrega` e `corrigir_horas`) não servem de gatilho. `origem = 'cron'` só é usada na conferência do horário no diagnóstico (decidido em 22/10/2026);
   - em `v1-painel_etapas` (por `execucao_id`): esperar **`etapa_id = 'entrega'` com `status = 'concluida'`**. **Não esperar o daily inteiro** (a etapa seguinte, `analise`, não interessa e, se falhar, deixa o daily `parcial`);
   - conferir se `precos`, `noticias` e `enriquecimento` também estão `concluida`. Se não: seguir, mas com aviso.
   - daily `agendada` = ainda não começou: esperar;
   - entrega `falhou` (ou execução `falhou`): esperar um daily mais novo até o prazo;
   - `precos` não concluída e sem o IBOV do pregão anterior previsto: esperar (dados atrasados). Com `precos` concluída e sem esse IBOV: seguir com aviso (a B3 pode ter fechado; o fechamento descarta o dia, se for o caso; R3).
3. Com a entrega pronta: calcular a Fase 1, fechar o resultado do top 5 do pregão anterior, gerar o top 5 de hoje e enviar os pacotes (ordem na seção 8.5).
4. **Prazo: 9h45.** Sem a entrega concluída (entrega ou execução `falhou`, daily não começou, `agendada` ou inexistente, ou entrega ainda em andamento), a rodada é registrada no `execucao` com status `falhou` e **nenhum outro pacote**: os dados disponíveis são os de ontem e misturariam tabelas. Só o `execucao.json` é gravado, com `coleta_status.motivo`, os horários das consultas e o aviso, para a interface mostrar "dados de ontem; a atualização de hoje falhou". A rotina continua consultando até 12h; se a entrega concluir antes disso, gera uma rodada tardia (o top 5 gerado depois das 10h não vale para o histórico).
5. O top 5 é gravado com `gerado_em`. **Se gerado depois das 10h, `valido_para_historico = false`.**
6. D só é dia de rotina se for pregão previsto: dia útil fora de `feriados_b3` (`parametros.yaml`, conferido com a B3 e com os pregões do banco). Sem pregão, nada é gravado.

Etapas da coleta, em ordem: `precos`, `macro`, `noticias`, `ipe`, `enriquecimento`, `juiza`, `cadastro`, `entrega`, `analise`. Status de etapa: `pendente`, `em_andamento`, `concluida`, `falhou`, `pulada`.

---

## 5. Fase 1: indicadores do painel

Fonte dos dados: tabelas da seção 3. `fech` = `fechamento`; `aj` = `fechamento_ajustado`. Comparações de valor com o setor (P/L, P/VP, ROE, yield, payout, margens, EBITDA, endividamento) usam a **mediana por empresa das outras empresas do mesmo setor** (decidido em 23/10/2026: a média era distorcida por um valor extremo, ex.: P/L 180 da BRAV3 levava o P/L do setor de petróleo a 43, contra mediana 12; a variável `ret_vs_setor` do modelo continua com a média, seção 7.3) (sem a própria empresa: tiram-se todas as ações do mesmo CNPJ, ex.: PETR3 não entra no setor da PETR4) **Exceção (24/10/2026): a rentabilidade do setor não é mediana:** é a razão de dois pontos da série `SETOR_SEM:<ticker>` (8.3, item 4), a mesma do gráfico, com as mesmas outras empresas; se o setor tem menos de 3 empresas (CNPJs distintos, contando a própria), `setor_comparacao_fraca = true`. Só ON, PN e UNIT entram nos pares (setor e `posicao_pct`); BDR aparece no painel, mas fica fora dos pares (`posicao_pct = nao_se_aplica`). Janelas "1 dia, 1 mês, 6 meses, 1 ano" = **1, 21, 126 e 252 pregões** (decisões de 22/10/2026; detalhes na seção 9, etapa 3).

| Indicador | Cálculo | Observações / status |
|---|---|---|
| Cotação | `fech` do dia; variação = `fech(t)/fech(t−1) − 1` | — |
| Variação do preço | Mesmo cálculo com `fech` em 1 dia, 1 mês, 6 meses, 1 ano | Sem dividendos |
| Rentabilidade | `aj(t)/aj(t−n) − 1` em 1 dia, 1 mês, 6 meses, 1 ano; idem para IBOV; setor = `SETOR_SEM:<ticker>(t) / SETOR_SEM:<ticker>(t−n) − 1` (base as-of, no máximo 5 pregões antes da data-alvo; seção 6, "Base velha") | Com dividendos |
| Comparação com Ibovespa | Rentabilidade da ação × do IBOV, mesmas janelas | Gráfico: séries rebaseadas pela interface |
| Comparação com o setor | Rentabilidade da ação × rentabilidade do setor sem a própria empresa (série `SETOR_SEM:<ticker>`: média igual por empresa dos retornos diários das outras empresas do setor, encadeada), mesmas janelas | Gráfico e tabela usam a mesma série e batem |
| Comparação com índices | Ação × CDI, IPCA, IDIV, SMLL, IFIX, IVVB11. **CDI e IPCA acumulados** (juros sobre juros) | IPCA é mensal |
| Volume total | `volume` do dia | — |
| Volume em relação ao normal | `volume(t) / mediana(volume das 20 sessões anteriores, sem t)` | `historico_insuficiente` com menos de 20 |
| Volatilidade | Desvio-padrão dos 20 últimos retornos diários de `aj` | `posicao_pct` = fração das ações do dia mais calmas que ela. Retorno suspeito (seção 6) não entra: a janela fica incompleta → `historico_insuficiente` (24/10/2026) |
| Beta | Inclinação da regressão dos retornos diários da ação sobre os do IBOV, 252 pregões | Usa até 252 pregões; calcula a partir de **120**. Abaixo de 120: `historico_insuficiente`. Retorno suspeito da ação (seção 6) não entra nos pares (24/10/2026) |
| Tom das notícias do dia | Contagem por rótulo (maior das 3 probabilidades) e tom médio `prob_positivo − prob_negativo` | Manchetes ordenadas por `destaque` (seção 8) |
| P/L | Valor de mercado ÷ lucro líquido 12m. Valor de mercado = Σ (preço de cada classe × quantidade na base atual, `qtd_*_base_atual`) ou preço × (ON+PN) quando só uma classe é negociada | Lucro 12m ≤ 0: mostrar **o número e o aviso** (ex.: "P/L −5,2 · Empresa com prejuízo nos últimos 12 meses"), com `status = lucro_negativo`. Essa empresa **não entra na média do setor** |
| P/VP | Valor de mercado ÷ patrimônio líquido do balanço mais recente | — |
| ROE | Lucro líquido 12m ÷ patrimônio líquido mais recente | — |
| Margem bruta | Lucro bruto 12m ÷ receita líquida 12m | `nao_se_aplica` em bancos e seguradoras |
| Margem líquida | Lucro líquido 12m ÷ receita líquida 12m | `nao_se_aplica` em bancos e seguradoras |
| EBITDA | EBIT 12m + depreciação e amortização 12m; margem = EBITDA ÷ receita 12m | `nao_se_aplica` em bancos/seguradoras; `indisponivel` se faltar EBIT ou D&A. Rótulo: "EBITDA (cálculo padrão CVM)" |
| Endividamento | Dívida líquida = empréstimos CP + LP − caixa − aplicações; DL/PL; DL/EBITDA 12m | Sem arrendamentos (avisar). DL < 0 → `caixa_liquido = true`. `nao_se_aplica`/`indisponivel` como o EBITDA |
| Dividend yield | Σ proventos com `data_com` nos últimos 12 meses ÷ `fech` atual | — |
| Payout | Σ proventos pagos em 12 meses (valor × quantidade na base atual da linha vigente na `data_com`) ÷ lucro líquido 12m; também por ano | Somar só ON e PN, **nunca a unit** |
| Histórico de dividendos | Lista de proventos e soma por ano | 5 anos |

---

## 6. Regras de cálculo transversais

| Tema | Regra |
|---|---|
| Ação → empresa | **Por período (03/11/2026):** CNPJ e tipo de cada ticker vêm do `v1-emissores_ticker` vigente na data (balanços, ações emitidas, `v1-raw_ipe_docs`, `dia_resultado`, `dias_desde_resultado`, proventos → empresa e payout, valor de mercado). Se o `ticker_negociado` da linha é outro código, o tipo é o da classe dele (JBSS3 → ON). Fora de vigência ou sem linha: CNPJ do `v1-cadastro`. Notícias, setor e "setor sem a própria empresa" continuam pela empresa do cadastro (o diagnóstico acusa CNPJ de emissor que seja de outro ticker do cadastro). Painel do dia, `payout_por_ano` e `fundamentos_trimestrais` usam o emissor vigente em t; os pontos diários de P/L, P/VP e yield, o de cada data. Ligar pelo `cnpj` do `v1-cadastro`. Notícia da empresa vale para todas as suas ações (PETR3 e PETR4). **Classes fora do `v1-cadastro`** (ex.: ITUB3 nos proventos): aplicar antes a `v1-mudancas_ticker` e ligar pelas **4 primeiras letras** (raiz) à empresa do cadastro. Isso vale também para classes **extintas** (fora do `other_codes` da empresa em `v1-raw_b3_cadastro`): os proventos delas contam no histórico e no payout (seção 3.4). Classes 3 = ON; 4, 5 e 6 (PN, PNA, PNB) = **PN**; 11 = unit (decidido em 22/10/2026) |
| Units | Indicadores por ação da unit = indicador por ação × (`unit_qtd_on` + `unit_qtd_pn`) |
| Trimestre isolado | ITR traz o trimestre e o acumulado; usar a linha cujo período tem ~3 meses. **4º trimestre = DFP (ano) − acumulado de 9 meses do 3º ITR.** Depreciação (quando vier) pode estar só acumulada: calcular pela diferença |
| Período inválido (26/10/2026) | Linha de `v1-balancos` com período fora do esperado é **descartada antes de qualquer conta** (referência, saldos, trimestres, 12 meses, payout, dias de resultado): ITR só vale com 3, 6 ou 9 meses; DFP só com 12 (classes de dias do diagnóstico). Ex.: ITR de 01/03 a 31/03/2021 com tudo 0 (RECV3, LREN3) e ITR de 12 meses copiando a DFP 2021 (AZZA3). O diagnóstico lista essas linhas como nota |
| 12 meses | Soma dos 4 últimos trimestres isolados |
| Point-in-time | Em cada data, usar só balanços com `data_entrega ≤ data` |
| Balanço velho | Em t, o balanço de referência (D11) vale até o **fim do mês** de `data_fim_periodo` + `fundamentos.balanco_idade_max_meses` (15) meses de calendário (decidido em 24/10/2026: o limite é o fim do mês, não o dia exato; ex.: fim 31/12/2023 vale até 31/03/2025; fim 30/09/2024 vale até 31/12/2025; fim 29/02/2024 vale até 31/05/2025). Depois disso, P/L, P/VP, ROE, margens bruta e líquida, EBITDA (valor e margem), endividamento (DL, DL/PL, DL/EBITDA, caixa líquido) e payout 12m saem `indisponivel`, também nos pontos diários de P/L e P/VP do `series_diarias`; a empresa sai das medianas do setor desses indicadores. Não mudam: yield, `payout_por_ano`, `proventos_por_ano`, `fundamentos_trimestrais` e `balanco_referencia` (continua mostrando o balanço usado). Bancos e seguradoras seguem `nao_se_aplica` onde já eram (decidido em 24/10/2026) |
| Bancos, seguradoras e holdings | Identificar pelo subsetor do cadastro (D5; "Holdings Diversificadas" desde 24/10/2026) |
| Calendário | Pregões = datas com preço do `IBOV` em `v1-precos` |
| Mudança de ticker | Unir os históricos pela `v1-mudancas_ticker` antes de qualquer cálculo. **Exceção (24/10/2026, trocada em 03/11/2026): troca de ação (classe 3, 4, 5, 6 ou 11) por BDR** (`tipo_acao` BDR no cadastro; fora dele, classe 32 a 35) não une, **salvo quando o `v1-emissores_ticker` a descreve** (linha do código novo com `ticker_negociado` = código antigo, ex.: JBSS32 ordem 1 = JBSS3): aí une sem corte, e tipo e CNPJ vêm do período. Troca por BDR sem essa linha segue o corte por data (`tickers.cortes_acao_para_bdr`). A empresa é a mesma (raiz/CNPJ): notícias e proventos do código antigo valem para ela |
| Setor herdado (24/10/2026) | Ticker fora do `v1-cadastro` ligado a uma empresa do cadastro (mudança de ticker pela `v1-mudancas_ticker` ou raiz de 4 letras com um único CNPJ) herda o CNPJ e o setor dessa empresa **no dataset do experimento** (regra geral; a JBS não depende disto desde 03/11/2026: a JBSS32 tem o histórico inteiro e a empresa vem do `v1-emissores_ticker`, seção 3.4). Vale para `empresa`, `setor`, `ret_vs_setor` e `tom_setor`; os tickers que herdaram ficam em `setor_herdado` no JSON do dataset |
| Empréstimos zerados | `emprestimos_curto_prazo = 0` **e** `emprestimos_longo_prazo = 0` na mesma linha = ausente (conta não achada pela coleta): dívida líquida, DL/PL, DL/EBITDA e `caixa_liquido` saem `indisponivel`. Só um dos dois = 0 continua valendo; `aplicacoes_financeiras = 0` continua valendo (decidido em 22/10/2026; pedido à coleta na seção 10) |
| Quantidade de ações suspeita | Em cada data, se o P/VP calculado (valor de mercado ÷ patrimônio líquido > 0) for **< 0,05** (`fundamentos.pvp_minimo_plausivel`) **e** P/VP × 1000 for **≤ 20** (`fundamentos.pvp_maximo_plausivel_x1000`), a quantidade de `v1-acoes_emitidas` daquela empresa é suspeita (em 23/10/2026, gravada em milhares em ~25 empresas; em 30/10/2026, nenhuma cai nesta regra, seção 10). O teto existe por causa da HAPV3: em 30/10/2026 o P/VP real era 0,0439 (quantidade e preço corretos, após queda de 55% em 26/10/2026), e × 1000 daria 43,9, implausível, logo a quantidade não está em milhares. Se suspeita: valor de mercado, P/L, P/VP e payout (inclusive `payout_por_ano` e `payout_12m`, pela situação em t) saem `indisponivel` e ficam fora das comparações com o setor. **Não multiplicar por 1000.** ROE, margens, EBITDA, endividamento e yield não mudam. O diagnóstico lista as empresas suspeitas (decidido em 23/10/2026; pedido à coleta na seção 10). Mantida em 03/11/2026 como proteção, agora sobre a `base_atual`. **Lista manual temporária (08/11/2026):** `fundamentos.quantidade_suspeita_manual` (`ticker`, `desde`, `motivo`) torna suspeita a quantidade da empresa do ticker a partir de `desde` (inclusive), com o mesmo tratamento acima (painel do dia, `payout_por_ano`, `payout_12m`, pontos diários de P/L e P/VP, fora das medianas), um aviso por entrada ativa no `execucao` e a lista no diagnóstico. Hoje: vazia. A RAIZ4 (desde 03/11/2026: virou RAIZ55, cotada por lote de 100, Ofício Circular B3 022/2026-VPE) saiu em 09/11/2026, quando a coleta corrigiu o preço para preço por ação. O preço não é corrigido pelo processamento. Tirar cada entrada quando a coleta corrigir. |
| Retorno diário suspeito | Retorno do dia do `fechamento_ajustado` (contra o último pregão com preço) **abaixo de −75% ou acima de +100%** (`fase1.retorno_suspeito_min`/`_max`; os limites exatos não contam) = erro da coleta (ex.: AZUL3 com 30.599.848 de 09/04 a 17/04/2026). Além dos limites, a lista explícita `fase1.eventos_retorno_suspeito` marca como suspeito, com a mesma máscara, o retorno dos pares (ticker, data) listados, valendo para painel, experimento e diagnóstico: PCAR3 em 23/08/2023 (cisão do Éxito, sem ajuste no preço). NATU3 saiu da lista em 03/11/2026 (a coleta trouxe o histórico). Ressalva do PCAR3: as manchetes indicam cerca de 19% de queda depois de descontar a cisão, e não dá para separar; o retorno do dia sai inteiro. **O preço não é corrigido:** o valor da própria ação (cotação, rentabilidade, série, P/L etc.) sai como veio. Só isola: (a) o retorno daquele dia não entra nas séries `SETOR_SEM:<ticker>` (nem, por isso, na `rentabilidade.setor`); (b) a empresa inteira fica fora das medianas de P/L, P/VP e yield do setor se alguma ação dela teve retorno suspeito nos últimos 21 pregões (`fase1.retorno_suspeito_pregoes_nivel`); (c) aviso no `execucao` com os suspeitos dos 253 pregões do pacote; (d) o diagnóstico lista todos (decidido em 24/10/2026; pedido à coleta na seção 10); (e) no experimento (decidido em 01/11/2026), toda conta de preço que atravessa o salto fica `NaN`, seção 7.3, e o alvo também, seção 7.1; a linha continua no dataset; variação através de lacuna maior que `fase1.base_defasagem_max_pregoes` (5) pregões não é retorno diário: conta como ausente, nunca como suspeita (24/10/2026) |
| Base velha (24/10/2026) | Toda janela de n pregões (variação do preço, rentabilidade da ação, do IBOV, do IVVB11, do IDIV, SMLL e IFIX, `rentabilidade.setor`, `variacao_dia` de IBOV/USDBRL/BRENT e `ret_1d`/`ret_5d`/`ret_20d`/`ret_vs_setor` do modelo) usa a base as-of: o último valor até a **data-alvo** `cal[k−n]` (k = posição de t no calendário). **Defasagem** = nº de pregões entre a data efetiva e a data-alvo; a base vale com defasagem ≤ `fase1.base_defasagem_max_pregoes` (5); acima, `historico_insuficiente`. O ponto final já exige valor em t. Ex. (situação de 22/10/2026; a lacuna já foi preenchida, seção 10): IDIV com dados até 2024 e de novo desde 20/10/2026: em 22/10/2026, `d1` `ok` (base 21/10) e `m1`, `m6`, `a1` `historico_insuficiente` (antes saíam +60,7%). CDI: a janela exige a taxa de todos os pregões em [base, t) (lacuna = `indisponivel`); `cdi_dia` sai `indisponivel` se a última taxa tem mais de 5 pregões de atraso. IPCA: com o último mês conhecido mais de `fase1.ipca_defasagem_max_meses` (2) meses antes do mês de t, as janelas, o `ipca_12m` e os pontos do índice IPCA saem `indisponivel`. Não mudam: volatilidade, volume relativo, beta, 52 semanas, exposições, `salto_abertura`, a cadeia `SETOR_SEM` e as séries base 100 (ponto sem valor já é `indisponivel`). Retorno diário através de lacuna maior que 5 pregões não é retorno diário: conta como ausente, nunca como suspeito. O diagnóstico lista as lacunas |
| Abertura ajustada | `abertura × aj / fech` do mesmo dia (para o salto da abertura não confundir dividendo com queda) |
| Checagem diária | Só avisos no `execucao` (nunca bloqueiam; limites no bloco `rotina.checagem` do `parametros.yaml`): **poucas ações** (menos de 90% das ações ON, PN e UNIT com preço em t); **retorno acima de 30%** em módulo no dia; **volume zero** em t; **preço parado** (mesmo fechamento nos últimos 5 pregões até t); **indicador vazio** no mercado (IBOV, USDBRL, BRENT, CDI, IPCA 12m) ou em todas as ações (cotação, rentabilidade d1, volume, volatilidade, beta, P/VP, yield). Lista com mais de 10 tickers: os 10 primeiros e "e mais k" |

---

## 7. Fase 2: o experimento

### 7.1 Alvo
- **Principal:** `alvo = 1` se `aj(t+1)/aj(t) − 1 > IBOV(t+1)/IBOV(t) − 1`; senão 0. Calculado por nós. Última data sem alvo não entra no treino.
- **Complementar:** salto da abertura de t+1 (abertura ajustada t+1 ÷ `aj(t)` − 1) maior que o do IBOV.
- **Retorno suspeito em t+1 (seção 6; decidido em 01/11/2026):** `alvo`, `alvo_abertura` e `ret_t1` de t ficam `NaN`, e a linha sai do treino e da avaliação como qualquer linha sem alvo. `ret_ibov_t1` e `alvo_abertura_valido` não mudam.

### 7.2 Janelas de notícias (horário de São Paulo)
- **Noite:** `data_hora_publicacao` **depois do fechamento da B3 no pregão t** e **até as 8h do pregão t+1** (inclui fins de semana e feriados: sexta à noite até segunda 8h). O horário de fechamento da B3 varia ao longo do ano: guardar em `config/parametros.yaml` e conferir os horários oficiais.
- **Pregão:** entre a abertura e o fechamento de t.
- **Sem horário:** notícias sem `data_hora_publicacao` (ex.: documentos da CVM) valem como publicadas às **23:59:59 da sua data** e entram na **noite** do pregão daquela data (fim de semana/feriado → noite do último pregão antes). É o horário mais tarde possível, então nunca adianta informação (E3, etapa 5). No painel (`noticias_dia`) continuam marcadas `sem_horario`.
- **Meia-noite do Pacífico = só data (decidido em 23/10/2026, N1-A):** de 2025 em diante, a maior parte das notícias do Google News (97,6% em 2025 e 83,8% em 2026) chega com `data_hora_publicacao` exatamente às 04:00:00 (horário de verão dos EUA) ou 05:00:00 (inverno) de São Paulo, ou seja, 00:00:00 em `America/Los_Angeles`: a fonte só deu a data. Usar esse horário jogaria a notícia do dia D na noite de D−1 (**vazamento**). **Só vale para as origens de `origens_so_data` no `fontes.yaml` (hoje `google_news`; decidido em 01/11/2026):** nas outras, o mesmo horário é hora real (ex.: matéria da `wordpress` agendada para as 05:00:00). Regra, aplicada na camada de leitura (`fontes.aplicar_regra_so_data`): instante de uma dessas origens que é 00:00:00 em Los Angeles → `precisao_hora = meia_noite_pacifico`, data = data em Los Angeles, sem hora, e segue a regra "sem horário" acima (23:59:59 da data → noite do pregão daquela data). 04:00:00 no inverno dos EUA (= 23:00 em LA) e qualquer outro horário (ex.: 04:00:01, 10:30) continuam com a hora real. Consequência: para essas notícias não há como separar pregão de noite; a janela efetiva delas é o dia t inteiro mais a noite, até 08:00 de t+1. Desde 03/11/2026 a coleta grava `data_hora_publicacao` vazia (e `momento_pregao = 'desconhecido'`, coluna ignorada) nas 260.545 notícias do Google News só com data: chegam como `sem_hora` (23:59:59 da `data_publicacao`), com o mesmo efeito. A N1-A continua para as 1.174 que ainda vêm com 04:00/05:00 (seção 10).
- **Janela do modelo (decidido em 23/10/2026, N2-A):** o modelo usa **uma janela só** por pregão t: **de 08:00:01 de t até 08:00:00 do próximo pregão** (pré-abertura + pregão + noite de t; fins de semana e feriados vão para o último pregão antes). As notícias "só data" e as de hora real são tratadas igual. O início da janela é parâmetro (`parametros.yaml`, `experimento.inicio_janela`: `"manha"` = esta janela; `"fechamento"` = só a noite, do fechamento de t até 08:00, para usar se a coleta trouxer o horário real). As definições de noite, pregão e pré-abertura abaixo continuam valendo para o painel (`noticias_dia`) e para o teste extra da 7.5.
- **Pré-abertura:** notícia entre 08:00:01 e a abertura de t+1 entra no **pregão de t+1** (E2, etapa 5). Bordas: fechamento exato (ex.: 17:00:00) = pregão; 08:00:00 = noite; 08:00:01 = pré-abertura do dia.
- O mesmo corte das 8h vale no **treino** e **ao vivo**. O daily da coleta começa às 8h (confirmado pelo painel em 22/10/2026: 11:00 UTC). **Limitação:** notícia publicada pouco antes das 8h pode ainda não ter sido capturada ao vivo, embora esteja no histórico do treino.
- Horário que manda: `v1-noticias.data_hora_publicacao` (contrato, fuso de SP); `raw_articles.published_at` (UTC) só para conferência (E1, etapa 5).

### 7.3 Colunas do dataset (uma linha por ação por pregão t)

**Identificação** (não entra no aprendizado): `data`, `ticker`, `setor`.

**Variáveis explicativas**

| Variável | Cálculo | Grupo |
|---|---|---|
| `noticias_dia_qtd` | Nº de notícias da janela do modelo (08:00:01 de t até 08:00 de t+1, seção 7.2) | Essencial |
| `noticias_dia_tom` | Média de `prob_positivo − prob_negativo` na janela | Essencial |
| `noticias_dia_extremo` | O score de maior valor absoluto na janela | Essencial |
| `mudanca_tom` | Tom da janela − média dos scores da empresa nos 30 pregões anteriores, com peso por notícia (E7) | Essencial |
| `tom_setor` | Média do tom das outras empresas do setor no universo do dia, cada empresa 1 voto (E8) | Complementar |
| `tom_mercado` | Média dos scores da janela das empresas do universo do dia, cada `id` uma vez (E9) | Complementar |

(`noticias_pregao_tom` saiu em 23/10/2026, N2-A: com ~89% das notícias só com data, ele mediria só a minoria com hora real.)
| `ret_1d`, `ret_5d`, `ret_20d` | Retornos de `aj` | Essencial |
| `volatilidade_20d` | Desvio-padrão de 20 retornos | Essencial |
| `beta` | 252 pregões contra o IBOV | Essencial |
| `volume_relativo` | Volume ÷ mediana de 20 sessões anteriores | Essencial |
| `salto_abertura` | Abertura ajustada de t ÷ `aj(t−1)` − 1 | Essencial |
| `dist_max_52s`, `dist_min_52s` | `aj` ÷ máxima (mínima) de 252 pregões − 1 | Complementar |
| `amplitude` | (máxima − mínima) ÷ fechamento | Complementar |
| `ret_vs_setor` | Retorno do dia − média do setor (sem a ação) | Complementar |
| `exposicao_dolar` | Beta contra o USDBRL (120 pregões) × variação do dólar no dia | Complementar |
| `exposicao_petroleo` | Idem com o BRENT | Complementar |

**Colunas do protocolo** (`docs/protocolo_variaveis.md`; decidido em 02/11/2026). Ficam no dataset, em rank na preparação. O **bloco A** (`posicao_fechamento`, `mom_12_1`, `liquidez_20d`, `ret_idio_5d`) foi adotado nas rodadas 1 e 3 e **entra no modelo em produção** (XGBoost, ao vivo, com a configuração congelada da rodada 3). Os blocos B, C, D, E e o controle ficam **fora dos modelos**: só nos testes de bloco (`preparacao.BLOCOS_PROTOCOLO`).

| Variável | Cálculo | Bloco |
|---|---|---|
| `posicao_fechamento` | (fechamento − mínima) ÷ (máxima − mínima) em t; máxima ≤ mínima = vazio; sem máscara de suspeito | A |
| `mom_12_1` | `aj(t−21)` ÷ `aj(t−252)` − 1, base as-of até 5 pregões antes de cada data-alvo; vazio se houver retorno suspeito em (t−252, t−21] | A |
| `liquidez_20d` | Mediana de fechamento × volume das 20 sessões até t, completas; vazio se houver retorno suspeito na janela | A |
| `ret_idio_5d` | `ret_5d` − `beta` × retorno de 5 pregões do IBOV (mesma base as-of) | A |
| `momento_setor_5d` | Média de `ret_5d` das outras empresas do setor no universo do dia, cada empresa 1 voto | B |
| `exposicao_small` | Beta contra (ret SMLL − ret IBOV), 120 pregões, mínimo 60 pares, × esse fator em t; dia sem SMLL = vazio | B |
| `dias_desde_resultado` | Pregões entre o pregão da última entrega válida e t (entrega em t = 0). Pregão da entrega: E11. Ignora período inválido e `data_entrega − data_fim_periodo` > 180 dias. Sem entrega, balanço velho ou `cnpjs_sem_balanco` = vazio | C |
| `var_lucro_aa` | (Lucro do trimestre isolado do balanço de referência − lucro do mesmo trimestre do ano anterior) ÷ PL de referência, só com `data_entrega` ≤ t. Trimestre sem valor isolado, ano anterior ausente, PL ≤ 0, insumo vazio ou balanço velho = vazio. Mesmo valor para as classes da empresa; bancos entram | C |
| `dy_12m` | Soma de `valor_por_acao` com `data_com` em (t − 12 meses, t] ÷ `fechamento(t)`, ticker atual e antigos da mesma classe; sem provento = 0,0 com preço válido (D8). Sem preço ou com retorno suspeito nas 20 sessões até t = vazio | D |
| `fato_relevante_cvm` | 1 se a empresa tem `categoria = 'Fato Relevante'` em `v1-raw_ipe_docs` com pregão de referência t (23:59:59 da `data_entrega`), original ou reapresentação sem original (Q4); senão 0. Vazio antes da cobertura, em `experimento.periodos_sem_coleta_cvm` e no último pregão sem `--proximo` | E |
| `controle_sorteado` | Uniforme em [0, 1) por pregão, `np.random.default_rng([treino.semente, ordinal da data])`, sobre os tickers do dia em ordem alfabética. Só depende de semente, data e tickers do dia | Controle |

**Entrega de fim de semana:** `dias_desde_resultado` e `fato_relevante_cvm` seguem a noite do pregão (E11): sábado depois de t sexta vale em t. `var_lucro_aa` só usa `data_entrega` ≤ t, então a mesma entrega só muda o valor na segunda. Ao vivo, balanços e documentos são lidos até D − 1 dia; proventos, até t. Com `--proximo`, o dataset segue a mesma regra.

**Alvo:** `alvo` (7.1).

- Variáveis de preço, volume e mercado entram como **rank** dentro do pregão: `(posição média − 1) ÷ (n − 1)`, menor = 0, maior = 1, empates pela média, um único valor = 0,5, vazio continua vazio (E6, etapa 5). `noticias_dia_qtd` também entra como rank (decidido em 01/11/2026: o volume muda de regime entre os anos); as outras 5 de notícias ficam **brutas** (E5); `tom_mercado` é igual para todas as ações do dia e também fica bruta. O CSV guarda sempre os valores brutos: o rank é feito em `preparacao.preparar`.
- **Retorno suspeito (seção 6; decidido em 01/11/2026), com s = dia do salto:** ficam `NaN` `ret_1d` e `salto_abertura` em s; `ret_5d` de s a s+4; `ret_20d` de s a s+19; `dist_max_52s` e `dist_min_52s` de s a s+250 (enquanto a janela de 252 preços contém s−1 e s); `ret_vs_setor` da própria ação em s. A ação também sai da média do setor das outras em s. `volatilidade_20d`, `beta` e `exposicao_*` já excluíam o retorno suspeito. `amplitude` e `volume_relativo` não mudam (não usam o ajustado). O preço não é corrigido.
- Filtro do universo **do modelo** por data (3.5: sem BDR, sem `tickers_excluidos`, sem ação sem preço no dia) antes de calcular os ranks; o rank usa **todas** as linhas do pregão, antes de descartar as linhas sem alvo.
- Detalhes das colunas (etapa 5): notícia da empresa vale para todas as suas ações (mesmo `id` conta 1 vez por empresa); `score = prob_positivo − prob_negativo`; `noticias_dia_extremo` = score de maior módulo, com sinal (empate de módulo = média dos empatados); `ret_1d/5d/20d` com base "as-of" (igual à rentabilidade do painel), no máximo 5 pregões antes da data-alvo (seção 6, "Base velha"); `salto_abertura` exige o pregão anterior (E13); `dist_max_52s`/`dist_min_52s` com 252 pregões incluindo t, mínimo 120; `exposicao_*` = beta de 120 pregões (mínimo 60 pares) × variação do fator em t (E12); `ret_vs_setor` exclui a **empresa** inteira (E14, regra D10). Colunas de identificação: `data`, `ticker`, `empresa`, `setor`, `universo`, `dia_resultado`. Alvos guardados: `alvo`, `alvo_abertura`, `alvo_abertura_valido` (F13), `ret_t1`, `ret_ibov_t1`.

### 7.4 Modelos (definidos antes de rodar)
| Modelo | Variáveis | Responde |
|---|---|---|
| 1. Base | Preço, volume e mercado | Quanto o preço sozinho explica |
| 3. + notícias | 1 + `noticias_dia_qtd`, `noticias_dia_tom`, `noticias_dia_extremo` + `mudanca_tom` | **Hipótese principal:** as notícias **do dia t e da noite, até 08:00 de t+1**, ajudam a prever se a ação supera o Ibovespa em t+1? |

O **modelo 2** (+ notícias do pregão) **saiu** em 23/10/2026 (N2-A): com ~89% das notícias só com data, não há como separar pregão de noite (seção 7.2). A numeração 1/3/3b foi mantida para não confundir com o histórico.
| 3b. Dias de resultado | Sem treino próprio: as previsões do modelo 3 (e do 1) avaliadas só nos dias com balanço divulgado na janela (F12) | O efeito é maior em dia de balanço? |

**Notícias usadas pelo modelo (decidido em 21/10/2026):**
- **Versão principal: todas as notícias** de `v1-noticias`, menos `papel = 'errada'` (seção 3.1; decidido em 01/11/2026). Notícia sem julgamento fica.
- **Teste extra: só as principais.** Recalcular as variáveis de notícias usando só as linhas com `origem = 'cvm_ipe'` **ou** (`tipo_conteudo = 'reportagem'` **e** `papel` em `protagonista` ou `citada_com_fato`). Notícias sem julgamento da juíza (`papel` vazio) ficam fora dessa versão; **contar quantas são e informar no relatório**. Comparar as duas versões com a mesma validação (seção 7.5). Se a filtrada for melhor, é um achado do TCC.
- O filtro é feito **no processamento**; a coleta mantém o filtro dela desligado (`ENTREGA_FILTRO_JUIZA=false`).

Ordem: primeiro só as **essenciais**; depois os **complementares**, um bloco por vez, mantendo só o que melhora na validação.
XGBoost, ponto de partida: `n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5`. **É o modelo em produção** (rodada 3: nenhum candidato passou na busca, então fica a referência; `docs/configuracao_final_rodada_003.json`). Sem `--configuracao`, a grade pequena é escolhida pela validação (F7).

### 7.5 Avaliação
- **Walk-forward mensal** (treina no passado, testa no mês seguinte, avança), com **embargo de 1 pregão**.
- **Conjunto de teste final** separado e usado **uma única vez** (decidido em 23/10/2026, F1/F2): de **23/06/2026** até a **véspera da entrada da rotina diária em produção** (data fixada na etapa 8). Fica em `parametros.yaml`, `treino.teste_final.inicio` e `treino.teste_final.fim`; **`fim` vazio = trava ativa** (o teste final não roda). Enquanto isso, o treino usa só o período de desenvolvimento (antes de 23/06/2026, menos o pregão de embargo).
- **Borda do `fim` (decidido em 23/10/2026):** o teste final avalia só as linhas cujo **dia do alvo (t+1) é ≤ `fim`**. A linha do próprio `fim` (o alvo dela é o primeiro pregão em produção) pertence ao **teste ao vivo**: é a primeira previsão ao vivo. Se o `fim` não for pregão, sai também o último pregão antes dele cujo t+1 passa do `fim`. Assim nenhum dia de alvo é contado nos dois testes (`validacao.linhas_com_alvo_ate`).
- **Teste ao vivo:** as previsões **a partir da linha do `fim`** formam um **segundo teste, independente**: o histórico do top 5 gravado no momento da geração (7.6 e 7.7), sem nenhuma escolha feita olhando esse período.
- **Corte principal: top 5** (o que vai para a tela). Avaliar também o **top 3** com as mesmas métricas, para mostrar que o resultado não depende do corte.
- Métricas: acerto do top 5 × **faixa do acaso** (10 mil sorteios aleatórios de 5 ações por dia, faixa de 95%); retorno médio do top 5 − IBOV; **top 5 × últimos 5**; AUC geral e AUC médio por pregão; IC por bootstrap em blocos de pregão; **robustez por ano**; **análise de sensibilidade** (último ano × anteriores), sempre calculada.
- **Teste extra "notícia depois do fechamento" (pedido em 23/10/2026; implementar na etapa 6):** recalcular as variáveis de notícias usando **só as notícias com hora real** (`precisao_hora = 'hora'`) e **só a noite** (do fechamento de t até 08:00 de t+1; `inicio_janela = "fechamento"`), e comparar com o modelo 3 na mesma validação. Mede o efeito das notícias publicadas depois do fechamento. No Google News a amostra é pequena (~9% com hora real, ~47% delas na noite). A `wordpress` tem hora real em tudo (seção 3.1), então a amostra fica concentrada em 2021, 2022 e nos meses de 2026 com essa origem: informar as contagens por ano e por origem e tratar como exploratório.
- **Referências de comparação** (rodadas com a mesma validação): escolha ao acaso (faixa acima), regra simples só com a volatilidade (ações mais calmas primeiro) e **regressão logística** com as mesmas variáveis (se uma rodada escolher a logística, a terceira referência passa a ser o XGBoost do ponto de partida; protocolo, seção 6). O XGBoost em produção só "ganha" se superar as três.
- Diferença dentro da faixa do acaso = "ainda não mostrou vantagem sobre o acaso".

### 7.6 Previsão diária (top 5)
- Ordenar as ações do dia pela probabilidade do modelo e pegar as 5 primeiras. Na tela: **"5 ações com maior chance de superar o Ibovespa (experimento)"**.
- **Motivos:** contribuições do XGBoost em produção (`pred_contribs`; na logística, mantida no código, a parte de cada variável no logit, com o viés). Em ação sem tom no dia, as contribuições de `noticias_dia_qtd`, `noticias_dia_tom` e `noticias_dia_extremo` somam-se num único motivo "Sem notícias", em qualquer família; só o texto muda, não as contribuições (decidido em 08/11/2026). As contribuições são traduzidas em frases ("Notícias da noite com tom positivo (3 notícias)"), com efeito `ajudou`/`atrapalhou`/`neutro`.
- **Chance:** calculada, mas `exibir = false` até a calibração ser conferida (se o modelo diz 60%, ~60% acontecem). Quando exibida, vem ao lado da referência do acaso, 50% (`chance.referencia_acaso`); com a chance escondida, a referência também vai `null`, para a interface não mostrar "50%" por engano.
- Gravar o top 5 do dia no momento da geração (histórico nunca recalculado depois).
- No dia seguinte, fechar o resultado: `superou` = retorno da ação > retorno do IBOV no pregão previsto. Retorno suspeito nesse pregão (seção 6): retorno `null`, `superou` vazio, não conta como acerto, e `resultado_incompleto = true`.

### 7.7 Modelo em uso no dia a dia
- **Qual modelo gera o top 5:** o **modelo 3** (com as notícias do dia e da noite, até 08:00 de t+1), porque é ele que testa a hipótese do TCC. Ele é mostrado mesmo que não supere o acaso: o selo "em avaliação" e o histórico existem para isso.
- **Comparação ao vivo:** todo dia, gravar também (sem mostrar na tela) o top 5 do **modelo 1** (sem notícias) e o da **regra da volatilidade**. Assim, o histórico mostra, com dados de verdade e daqui para frente, se as notícias fazem diferença.
- **Retreino mensal:** no primeiro pregão de cada mês, na própria rotina, depois da entrega e antes do top, sempre que o modelo do mês não existir e a rotina estiver em produção (`treino.teste_final.fim` preenchido). Corte = pregões antes do dia 1 do mês, menos o de embargo (o mesmo esquema do walk-forward). Metadados com `retreino` e as métricas do desenvolvimento (a validação não é refeita). Se faltar no mês, repete nos pregões seguintes (mesmo corte, mesmo modelo). A chave `treino.modelo_oficial` (R7) diz se o modelo é oficial. Os hiperparâmetros só mudam numa nova avaliação completa, nunca no retreino automático. Modelo de desenvolvimento de outra `versao_preparacao` impede o retreino (vira aviso; a rodada segue).
- **Arquivo do modelo:** salvar em `modelos/<família>-AAAA-MM.json` (o prefixo é `treino.familia_producao`: `xgb-AAAA-MM.json` desde a rodada 3, em JSON nativo do XGBoost; o código aceita também `logistica-AAAA-MM.json`; nunca pickle), com um arquivo de metadados ao lado: `versao_preparacao`, `familia`, variáveis usadas, período de treino, hiperparâmetros, a configuração de origem (`configuracao`: arquivo, sha256, rodadas e vencedor), métricas da validação, universo (`composicao_atual` ou histórica) e um hash do dataset. O `modelo_versao` do pacote `experimento_top` aponta para esse arquivo (nome sem o dia, como no exemplo da 8.3). O modelo 1, usado no top 5 sombra, vai em `modelos/<família>-m1-AAAA-MM.json` (F17).
- **Antes do histórico completo:** o modelo pode ser treinado com o 1 ano atual **só para testar a rotina** (top 5 marcado com aviso "modelo provisório"; `valido_para_historico = false`). O modelo "oficial" e o histórico que vale para o TCC começam quando o histórico completo chegar.

---

## 8. Saída: pacotes para a API

**Arquitetura:** o processamento calcula tudo e envia **pacotes JSON** para uma **API** (a ser construída depois, junto com o banco da interface). A API grava num **banco próprio da interface**, que a tela consulta. O processamento **não** grava no banco da coleta nem no da interface diretamente: só envia à API.

Enquanto a API não existe, o processamento **gera os mesmos pacotes como arquivos JSON** numa pasta (ex.: `saida/AAAA-MM-DD/`). Trocar o "gravar arquivo" pelo "enviar à API" deve ser a única mudança depois.

### 8.1 Convenções (valem para todos os pacotes)
| Regra | Definição |
|---|---|
| Formato | JSON, UTF-8 |
| Versão | Todo pacote tem `versao_contrato` (começa em `"1.0"`). Mudou um campo → sobe a versão |
| Datas | `AAAA-MM-DD`; data e hora em ISO com fuso de São Paulo (`2026-06-19T09:12:00-03:00`) |
| Ticker | Sem `.SA` (ex.: `PETR4`); o Ibovespa é `IBOV` |
| Percentuais | **Fração decimal**: `0.0123` = 1,23%. A interface formata |
| Dinheiro | Reais, sem escala (`48200000000` = R$ 48,2 bi). A interface abrevia |
| Ausência | Valor `null` **sempre acompanhado de `status`** (nunca 0 no lugar de vazio) |
| `status` de cada indicador | `ok` · `nao_se_aplica` (ex.: margem de banco) · `indisponivel` (dado não veio da coleta, ex.: empresa sem balanço nas fontes) · `historico_insuficiente` (ex.: beta com menos de 120 pregões) · `lucro_negativo` (P/L de empresa com prejuízo: valor mostrado com aviso) |
| Textos prontos | Opcionais, em campos `texto` (ex.: `"mais calma que 96% das ações"`). O número sempre vem junto; a interface pode usar um ou outro |
| Chave de gravação | Cada pacote declara a chave (`data_referencia` + `ticker` etc.). A API grava por **upsert**: reenviar substitui, nunca duplica |
| Metadados | Todo pacote tem `gerado_em` e `dados_ate` (até quando os dados da coleta vão) |
| Folha | Todo número de indicador vai como `{"valor": ..., "status": ...}`. `ok` exige valor; valor nulo exige status ≠ `ok`; valor com status ≠ `ok` só em `lucro_negativo`. **Exceção: o `series_diarias` usa o formato compacto (item 4 da 8.3)** |
| Janelas do pacote | A interface mostra 1m, 6m e 1a: `series_diarias` leva os últimos 253 pregões até t; `fundamentos_trimestrais`, os 8 trimestres mais recentes de cada ação; `proventos` e `proventos_por_ano`, 5 anos (ano de t e os 4 anteriores); `experimento_historico`, tudo desde a produção. Os cálculos usam o histórico inteiro; só o pacote é cortado |
| `status` da chance | `ok` ou `calibracao_nao_conferida` (só no `chance` do `experimento_top`) |
| Arquivos | Um arquivo por pacote em `saida/AAAA-MM-DD/<pacote>.json` (D = dia da rotina), com envelope `{pacote, versao_contrato, chave, gerado_em, dados_ate, registros, removidos}`; cada registro repete os metadados |
| Datas de referência | D = dia da rotina = pregão previsto; t = último pregão antes de D. `mercado_dia`, `resumo_acao`, `noticias_dia` usam t; `experimento_top` e `execucao` usam D; `dados_ate` = 08:00 de D |
| Envio "quando muda" | `acoes`, `fundamentos_trimestrais`, `proventos` e `series_diarias` comparam com o estado do último envio (`saida/estado/`): só vai o novo ou alterado; o que sumiu vai em `removidos`; série com ponto antigo alterado vai inteira com `substituir_serie: true`. No `series_diarias`, ponto antigo só conta como alterado com diferença relativa acima de `saida.tolerancia_serie_relativa` (1e-6) ou status diferente (26/10/2026: a coleta grava o ajustado em float32 e regrava o histórico todo dia, ruído de até ~7e-7; os valores continuam sem arredondar) |

### 8.2 Os pacotes

| # | Pacote | Uma unidade por | Chave | Quando é enviado | Alimenta na tela |
|---|---|---|---|---|---|
| 1 | `acoes` | ação | `ticker` | Quando muda (cadastro) | Nome, setor, tipo de ação, busca |
| 2 | `mercado_dia` | dia | `data_referencia` | Todo dia | Faixa do mercado: Ibovespa, dólar, Brent, CDI |
| 3 | `resumo_acao` | ação × dia | `data_referencia` + `ticker` | Todo dia | O card da ação: todos os indicadores da Fase 1 (valor atual) |
| 4 | `series_diarias` | ação (ou índice) × dia | `ticker` + `data` | Todo dia (dia novo); **reenvio da série inteira** (`substituir_serie: true`) quando algum ponto antigo dentro da janela muda: desdobramento, bonificação, reapresentação de balanço ou histórico estendido (dividendo não muda o índice dos dias anteriores à data-ex; ver 8.3) | Gráficos de preço, rentabilidade, comparação com Ibovespa, setor e índices, volume |
| 5 | `fundamentos_trimestrais` | ação × trimestre | `ticker` + `data_fim_periodo` | Quando sai balanço novo | Gráficos de margens, ROE, EBITDA, endividamento |
| 6 | `proventos` | provento | `ticker` + `tipo` + `data_com` | Quando há provento novo | Histórico de dividendos (tabela e barras por ano) |
| 7 | `noticias_dia` | ação × dia | `data_referencia` + `ticker` | Todo dia | Manchetes com rótulo e resumo do tom |
| 8 | `experimento_top` | dia | `data_referencia` | Todo dia, **antes das 10h** | Aba Experimento: as 5 ações e os "detalhes" |
| 9 | `experimento_historico` | dia (+ resumo) | `data_referencia` | Todo dia (o resultado do dia anterior só se conhece depois do fechamento) | Histórico de acertos × acaso |
| 10 | `execucao` | rodada | `data_referencia` + `rodada` | Ao fim de cada rodada | Status do sistema e avisos ("dados de hoje incompletos") |

### 8.3 Campos de cada pacote

**1. `acoes`:** `ticker`, `empresa`, `setor`, `subsetor`, `tipo_acao` (ON, PN, UNIT, BDR), `ativo_no_universo` (bool).

**2. `mercado_dia`:** cada número é uma folha `{valor, status}` (8.1). `data_referencia` (t); `IBOV`, `USDBRL`, `BRENT`: `{fechamento, variacao_dia, unidade}`; `cdi_dia` (fração ao dia) e `cdi_data` (com a última taxa mais de 5 pregões antes de t: `indisponivel` e `cdi_data` vazio); `ipca_12m`; `ipca_ate` (último mês de IPCA usado, `AAAA-MM`); `indices`: `{CDI, IPCA, IDIV, SMLL, IFIX, IVVB11}` × `{d1, m1, m6, a1}` (o % de cada índice por período, igual para todas as ações).

**3. `resumo_acao`** (um objeto por indicador, sempre com `valor`, `status` e, quando faz sentido, `setor`, `posicao_pct` e `texto`):
- `cotacao`: `fechamento`, `variacao_dia`
- `variacao_preco`: `d1`, `m1`, `m6`, `a1` (sem dividendos)
- `rentabilidade`: `d1`, `m1`, `m6`, `a1` (com dividendos) + as mesmas janelas do `IBOV` e do setor (`ibov`, `setor`), para a comparação lado a lado com seletor de 1 dia, 1 mês, 6 meses e 1 ano; `setor` = razão de dois pontos da série `SETOR_SEM:<ticker>` (item 4, base as-of), a mesma do gráfico
- `volume`: `total`, `relativo` (÷ mediana de 20), `mediana_20` (para a linha de referência do gráfico de barras), `posicao_pct`
- `volatilidade_20d`: `valor` (desvio diário), `posicao_pct` (fração de ações mais calmas)
- `beta`: `valor`, `status`
- `pl`, `pvp`, `roe`, `dividend_yield`, `payout`, `margem_bruta`, `margem_liquida`: `valor`, `setor` (mediana por empresa do setor, sem a própria empresa), `status`
- `payout_por_ano`: lista (`ano`, `valor`, `status`) dos últimos anos, para o gráfico de barras do payout
- `ebitda`: `valor_12m`, `margem`, `setor_margem`, cada um com o seu `status`, e `rotulo` ("EBITDA (cálculo padrão CVM)")
- `endividamento`: `divida_liquida`, `dl_pl`, `dl_ebitda`, `caixa_liquido` (bool), `setor_dl_pl`, `setor_dl_ebitda`, cada um com o seu `status`, e `aviso` ("Dívida líquida sem arrendamentos.")
- `setor_comparacao_fraca` (bool: setor com menos de 3 empresas)
- `balanco_referencia`: `data_fim_periodo` e `data_entrega` do balanço usado

Acréscimos: `proventos_por_ano` (soma por ano, 5 anos, com `ano`, `valor` e `status`); textos prontos (campo `texto`) em `volume.relativo`, `volatilidade_20d`, `beta` e `pl` (prejuízo).

**4. `series_diarias`** (formato compacto, só neste pacote): um registro por série com `ticker`, `tipo` (`acao`, `etf`, `indice`, `taxa`, `setor_sem_empresa`), `nome`, `substituir_serie`, `inicio_janela`, `datas` (lista crescente, sem repetir), `valores` (uma lista por campo, do mesmo tamanho de `datas`, número ou `null`) e `status` (por campo, só para os pontos que não são `ok`, em trechos `{de, ate, status}` contíguos e sem sobreposição; `null` ⇔ coberto por um trecho; valor coberto por trecho só com `lucro_negativo`). Campos por tipo: ação: `fechamento`, `indice_retorno_total` (com dividendos), `volume`, `pl`, `pvp`, `dividend_yield` (point-in-time, mesmas regras e status do `resumo_acao`); `IVVB11`: fechamento, índice, volume; `IBOV`, `IDIV`, `SMLL`, `IFIX`: fechamento (pontos) e índice; `CDI`, `IPCA`: índice base 100 acumulado (CDI: taxas com data < d; IPCA: meses fechados até K(d)); `SETOR_SEM:<ticker>` (uma por ação do painel com outra empresa no setor, BDR inclusive; `nome` = "<setor> sem <empresa>"): índice e `n_empresas` (sem status). Números sem arredondar. **Janela:** só os últimos 253 pregões até t (`inicio_janela` = o 1º deles); a API apaga os pontos da série com data anterior a `inicio_janela`, e o ponto que sai pelo corte não conta como mudança. **Base 100 com âncora fixa** no 1º dia da série no histórico inteiro (o 1º valor enviado em geral não é 100); o pacote não rebaseia no início da janela, porque isso mudaria todos os pontos todo dia (reenvio inteiro diário) e exigiria três versões (1m, 6m, 1a). **Setor sem a própria empresa (`SETOR_SEM:<ticker>`, decidido em 24/10/2026):** média igual por empresa dos retornos diários das ações ON, PN e UNIT do setor da ação (BDR nunca entra), **sem nenhuma ação da mesma empresa (CNPJ)**, com preço no dia e no pregão anterior e sem os retornos suspeitos (seção 6), encadeada em base 100; dia sem nenhuma outra empresa: ponto vazio (`indisponivel`) e a cadeia segue do último valor. Sem setor ou sem outra empresa no setor: sem série e `rentabilidade.setor` `indisponivel`; outras empresas sem nenhum preço: sem série e `historico_insuficiente`. A série `SETOR:<nome>` (todas as empresas) não é mais enviada; no envio seguinte ela vai em `removidos`. A divisão de dois pontos dá a rentabilidade da janela do `resumo_acao`/`mercado_dia`. **A interface recorta o período e parte do mesmo ponto dividindo pelo primeiro valor do recorte. Para a interface (decidido em 24/10/2026): se o primeiro ponto do recorte estiver `indisponivel`, não desenhar a linha e mostrar "histórico insuficiente" (como no `resumo_acao`/`mercado_dia`). O IPCA com mais de 2 meses de atraso sai `indisponivel` nos pontos.** Reenvio da série inteira (`substituir_serie: true`) quando algum ponto antigo dentro da janela muda (desdobramento, bonificação, reapresentação de balanço, histórico estendido); dividendo não muda o índice dos dias anteriores à data-ex. Envio diário: o mesmo formato só com as datas novas.

**5. `fundamentos_trimestrais`:** `ticker`, `data_fim_periodo`, `data_entrega`, `receita_trimestre`, `receita_12m`, `lucro_liquido_trimestre`, `lucro_liquido_12m`, `margem_bruta`, `margem_liquida`, `roe`, `ebitda_trimestre` (para o gráfico de barras por trimestre), `ebitda_12m`, `margem_ebitda`, `divida_liquida`, `dl_pl`, `dl_ebitda`, `payout_12m`, cada um com `status`. Margens, ROE e payout são sempre de 12 meses. Só os 8 trimestres mais recentes de cada ação (os mais antigos saem em `removidos`).

**6. `proventos`:** `ticker`, `tipo` (DIVIDENDO, JCP), `data_com`, `data_pagamento`, `valor_por_acao`. A soma por ano a interface faz (ou vem pronta em `resumo_acao`). Só os proventos com data-com no ano de t ou nos 4 anteriores.

**7. `noticias_dia`:** `data_referencia` (t), `ticker`, `janela_inicio`/`janela_fim` (08:00:01 de t até 08:00 de D, a mesma janela do modelo), `resumo` (`quantidade`, `positivas`, `neutras`, `negativas`, `tom_medio`, em folhas) e `itens` (`id`, `titulo`, `fonte`, `link`, `publicado_em`, `data_publicacao`, `precisao_hora`, `rotulo`, `prob_*`, `janela` = `pregao` (inclui a pré-abertura de t) / `noite` / `sem_horario` (sem hora real, inclusive "só data"), `destaque`, `status`). Rótulo: maior das 3 probabilidades; empate com o neutro, ou positivo = negativo, vira neutro. Destaque: protagonista primeiro, depois |positivo − negativo| e depois a mais recente. Sem notícia: quantidade 0 e `tom_medio` `nao_se_aplica`; antes do início da cobertura ou em período sem coleta (E4): tudo `indisponivel`.

**8. `experimento_top`:** lista `ranking` com as **5** ações (posição 1 a 5), cada uma com chance, motivos (com texto) e notícias usadas.
```json
{
  "versao_contrato": "1.0",
  "gerado_em": "2026-11-03T09:12:00-03:00",
  "dados_ate": "2026-11-03T08:00:00-03:00",
  "data_referencia": "2026-11-03",
  "pregao_previsto": "2026-11-03",
  "pregao_base": "2026-10-30",
  "valido_para_historico": true,
  "modelo_versao": "xgb-2026-11",
  "modelo_provisorio": false,
  "universo": "composicao_atual",
  "n_candidatas": 84,
  "selo": "em_avaliacao",
  "titulo": "5 ações com maior chance de superar o Ibovespa (experimento)",
  "aviso_fixo": "Não constitui recomendação de investimento.",
  "avisos": [],
  "ranking": [
    {
      "posicao": 1,
      "ticker": "CMIG4",
      "chance": {"valor": null, "referencia_acaso": null, "exibir": false, "status": "calibracao_nao_conferida"},
      "motivos": [
        {"fator": "noticias_dia_tom", "valor": 0.42, "efeito": "ajudou", "texto": "Notícias do último pregão e da noite com tom positivo (3 notícias)"},
        {"fator": "ret_5d", "valor": -0.031, "efeito": "ajudou", "texto": "Caiu 3,1% nos últimos 5 pregões (abaixo da média das ações)"}
      ],
      "noticias_usadas": ["n000123", "n000124", "n000125"]
    }
  ]
}
```
(valores ilustrativos; 02/11 é feriado, por isso o pregão base é 30/10.) `valido_para_historico = true` só com modelo não provisório, gerado até as 10h de D e D depois do fim do teste final (`treino.teste_final.fim`). `chance.valor` fica `null` (`calibracao_nao_conferida`) até a calibração ser aprovada **e** `liberar_chance: true` (F16); então vem o número, com `referencia_acaso: 0.5`, `exibir: true` e `status: "ok"`. Com `exibir: false`, `valor` e `referencia_acaso` são `null` (o validador exige; decidido em 23/10/2026, no lugar do antigo campo `media`, que a interface poderia mostrar como "50%"). A `versao_contrato` continua "1.0" (contrato ainda não está em uso). `modelo_versao` aponta para `modelos/xgb-AAAA-MM.json` (sem o dia). Os fatores dos motivos são os nomes das colunas do dataset (seção 7.3), com o valor bruto; os textos falam da janela única do modelo (08:00:01 de t até 08:00 de D: "último pregão e noite"). As sombras (modelo 1 e regra da volatilidade) e as probabilidades ficam só no registro interno (`registros/experimento/`), não no pacote.

**9. `experimento_historico`:** `data_referencia` (dia fechado); `dia` (`ranking`, `resultado` com `retorno`, `retorno_ibov`, `superou` de cada ação, `acertos_dia`, `acertos_top3`, `resultado_incompleto`, `taxa_acumulada`) ou `null`; `resumo` (`periodo_inicio`, `periodo_fim`, `n_dias`, `taxa_acerto`, `acaso_media`, `acaso_faixa`, `universo`, `nota`). Só entram dias com `valido_para_historico = true` e pregão previsto depois de `treino.teste_final.fim`; até a produção, `n_dias = 0` e a nota explica. A nota começa pelo universo: `composicao_atual` → "Histórico calculado com as ações que compõem o Ibovespa atualmente."; `composicao_historica` → "Histórico calculado com as ações que compunham o Ibovespa em cada data." O resultado de cada dia é gravado uma vez (`registros/experimento/AAAA-MM-DD.resultado.json`) e nunca recalculado.

**10. `execucao`:** `data_referencia` (D), `rodada`, `inicio`, `fim`, `status` (`em_andamento`, `ok`, `parcial`, `falhou`), `coleta_status` (o que se leu do painel da coleta; campos opcionais; a versão continua `"1.0"`, porque o contrato ainda não está em uso): `consultado`, `nota`, `motivo` (enum `entrega_concluida`, `entrega_pendente`, `entrega_falhou`, `sem_daily`, `daily_agendado`, `dados_atrasados`, `falha_consulta`, `sem_esperar`), `execucao_id`, `origem`, `status_execucao`, `iniciada_em`, `finalizada_em`, `entrega_concluida_em` (SP), `etapas` (as 9 etapas; `null` = sem linha), `consultas`, `espera_segundos`, `primeira_consulta_em`, `ultima_consulta_em`, `prazo`, `t_esperado`, `ultimo_pregao_lido`. Status lidos do painel são texto: se a coleta criar um status novo, o `execucao` continua sendo gravado. Com `falhou` às 9h45, o `execucao.json` é o único arquivo da rodada; `pacotes_enviados` (`pacote`, `arquivo`, `registros`, `removidos`) e `avisos` como antes.

### 8.4 Cobertura da planilha (conferida item a item)
Todas as 23 informações da planilha (`docs/planilha_final.xlsx`; cálculos na seção 5) têm origem num pacote: Top 5 e detalhes → `experimento_top` (+ `resumo_acao` e `noticias_dia`); Histórico do experimento → `experimento_historico`; Volume total, volume relativo, volatilidade, beta, cotação, variação do preço, rentabilidade, P/L, P/VP, ROE, yield, payout, margens, EBITDA e endividamento (valor atual) → `resumo_acao`; comparação com Ibovespa, setor e índices, gráficos de preço, rentabilidade e volume → `series_diarias` (+ `resumo_acao` para os % de cada período) (o setor de cada ação é a série `SETOR_SEM:<ticker>`; o % do setor no `resumo_acao` é a razão dela); gráficos trimestrais de margens, ROE, EBITDA e endividamento → `fundamentos_trimestrais`; gráfico do payout por ano → `resumo_acao.payout_por_ano`; dividend yield (barras) e histórico de dividendos → `proventos`; tom das notícias → `noticias_dia`. Comparação com índices: o % de cada índice por período vem em `mercado_dia.indices` (igual para todas as ações). P/L, P/VP e yield ao longo do tempo: `series_diarias` (pontos das ações). Linha do acerto acumulado do experimento: `experimento_historico.dia.taxa_acumulada`. As séries trazem 1 ano (253 pregões: 252 variações, para o gráfico de 1 ano bater com a `rentabilidade.a1`), os trimestres 8 e os proventos 5 anos.

### 8.5 Ordem diária de envio
1. `execucao` (início) → 2. `acoes` (se mudou) → 3. `series_diarias` → 4. `mercado_dia` → 5. `resumo_acao` → 6. `fundamentos_trimestrais` e `proventos` (se mudaram) → 7. `noticias_dia` → 8. `experimento_historico` (fecha o dia anterior) → 9. `experimento_top` (antes das 10h) → 10. `execucao` (fim).

Nomes dos arquivos: `execucao.json`, `acoes.json`, `series_diarias.json`, `mercado_dia.json`, `resumo_acao.json`, `fundamentos_trimestrais.json`, `proventos.json`, `noticias_dia.json`, `experimento_historico.json`, `experimento_top.json` (o `execucao.json` é regravado no fim da rodada). Cada pacote é validado antes de gravar; reprovado, não é gravado e a rodada fica `parcial`.

**Pasta limpa (24/10/2026):** toda rodada que gera pacotes (envio diário e carga completa) apaga, antes de gravar, os arquivos de pacote de rodadas anteriores da pasta de D (só os 9 nomes acima; o `execucao.json` e qualquer outro arquivo ficam). A pasta termina com os pacotes de `pacotes_enviados` + `execucao.json`. A rodada falhou (só o `execucao.json`) não apaga nada: os pacotes de uma rodada anterior do mesmo D continuam e o `execucao` avisa ("Pacotes de uma rodada anterior de D continuam na pasta ...").

**Top 5 provisório (24/10/2026):** enquanto `treino.modelo_oficial` e `saida.publicar_top_provisorio` forem `false`, o top 5 continua gerado e registrado em `registros/experimento/` (e os resultados continuam sendo fechados), mas `experimento_top` e `experimento_historico` **não são gravados** em `saida/<D>/` (passos 8 e 9 pulados; a ordem dos outros não muda), nem na carga completa (8.7). Eles são validados mesmo assim. `pacotes_enviados` lista os outros 7, a rodada não vira `parcial` por isso, e `avisos` traz: "Top 5 gerado e registrado só como teste de funcionamento (modelo não oficial): experimento_top e experimento_historico não enviados à interface (saida.publicar_top_provisorio = false)." Com `modelo_oficial: true` ou `publicar_top_provisorio: true`, vão os 10.

### 8.6 O que fica para a equipe da API e do banco decidir
- Autenticação, endereço e se o envio é um pacote por chamada ou em lote.
- Como o banco da interface guarda cada pacote (pode ser uma tabela por pacote, com a mesma chave).
- O processamento só garante: **mesmo formato, mesma chave e reenvio seguro (upsert)**.

### 8.7 Carga completa (carga inicial e recarga do zero)
Decidido em 24/10/2026.

- **Por que existe:** o envio "quando muda" (8.1 e S4) marca o que já foi enviado em `saida/estado/`, mesmo sem API. Se a interface for ligada depois, ou se o banco dela for recriado, ela fica sem o histórico: séries, fundamentos e proventos só saem uma vez.
- **Comando:** `python -m processamento.saida --data AAAA-MM-DD --completo`. Sem `--pasta`, a saída vai para `saida_completa/AAAA-MM-DD/`. Se `--pasta` for a pasta do envio diário, o comando recusa (código 2) e não grava nada.
- **O que sai:** os 10 pacotes inteiros (8 enquanto o top 5 não é publicado, 8.5): todas as ações; séries de 253 pregões com `substituir_serie: true`; 8 trimestres de fundamentos; 5 anos de proventos; `removidos` vazio.
- **O que NÃO muda:** o estado do envio (`saida/estado/`), os registros do experimento (`registros/`), nenhum retreino e nenhum dia fechado (não grava `.resultado.json` nem `.descartado.json`). O top 5 de D: se `<D>.top.json` já existe, sai esse mesmo registro; se não existe, é gerado na hora, sem ser gravado.
- **Carga inicial:** rodar com D = o dia da rotina diária mais recente; enviar os 10 arquivos pela ordem da 8.5. Daí em diante o envio diário segue de `saida/`.
- **Recarga do zero:** apagar o banco da interface; rodar a carga completa com o D mais recente; enviar os 10 arquivos. Não precisa apagar `saida/estado/`: o upsert da API (8.6) torna o reenvio seguro.
- **Limitação:** o `experimento_historico` traz o histórico inteiro dos resultados já gravados (não há corte). Quem recarrega do zero recebe esse histórico todo.

---

## 9. Ordem de implementação

| # | Etapa | Pronto quando |
|---|---|---|
| 1 | **Diagnóstico do banco (só leitura)** | Relatório `docs/diagnostico_banco.md` com: existência, colunas e chaves das 8 tabelas × seção 3; linhas, período e nº de tickers; duplicatas; probabilidades somando 1; % de notícias com hora **por ano**; idioma; formatos ISO das datas; escala dos balanços; tickers batendo entre tabelas; buracos nos pregões; colunas vazias (EBITDA etc.); valores distintos de `origem`, `papel`, `tipo_conteudo`, `evento` |
| 2 | Camada de leitura + calendário + universo | `fontes.py` com mapa, validação e conversores testados; calendário e janelas de notícias testados (sexta → segunda, feriados) |
| 3 | Fase 1: preços | Indicadores de preço, volume e comparações com testes |
| 4 | Fase 1: fundamentos e proventos | Trimestre isolado, 12 meses, point-in-time, units e `status` testados |
| 5 | Dataset do experimento | Seção 7.3 + alvo, com teste de "sem vazamento" |
| 6 | Treino e avaliação | Pipeline completo rodando com o 1 ano atual (**teste de funcionamento, não conclusão**) |
| 7 | Saída | Os 10 pacotes da seção 8 gerados em JSON, validados contra o contrato |
| 8 | Rotina diária | Gatilho da seção 4, prazos e avisos funcionando |

**Decisões da etapa 3 (22/10/2026)**
- **Janelas:** contadas em pregões do calendário: d1 = 1, m1 = 21, m6 = 126, a1 = 252 (`parametros.yaml`, bloco `fase1`).
- **Setor:** modo "empresa" (seção 5). Ação sem setor ou sem outra empresa no setor: `indisponivel`; há outras, mas nenhuma com valor: `historico_insuficiente`. Atualizado na etapa 4: conta cada empresa uma vez (ver D10).
- **BDR:** entra no painel, fora dos pares (setor e `posicao_pct`).
- **IPCA:** só meses fechados, sem rateio por dia. Na data d valem os meses anteriores ao mês de d; o acumulado da janela é o produto dos meses entre o último mês conhecido na base e o último conhecido em t. Ao vivo, nos primeiros ~10 dias do mês o IPCA fica defasado: por isso a saída informa `ipca_ate`. Desde 24/10/2026: último mês conhecido mais de 2 meses antes do mês de t → `indisponivel`.
- **CDI:** entram as taxas com data em [base, t) (a taxa do dia d rende de d a d+1); a taxa de t não entra. `cdi_dia` = taxa da última data ≤ t (`indisponivel` com mais de 5 pregões de atraso).
- **Lacunas de preço:** rentabilidade e variação usam a base "as-of" (último preço até t−n). Volatilidade e volume relativo exigem os 20 pregões completos; senão `historico_insuficiente`. Beta conta só pares de retornos válidos, mínimo 120. Desde 24/10/2026, a base vale só até 5 pregões de defasagem (seção 6, "Base velha").
- **Volatilidade:** desvio-padrão amostral (ddof = 1), diário, sem anualizar.
- **`posicao_pct`:** do volume, calculada sobre o volume **relativo**. Fórmula: nº de pares estritamente menores ÷ (nº de pares válidos − 1); menor = 0, maior = 1; menos de 2 válidos: `indisponivel`.
- **Comparação com índices:** janelas d1, m1, m6 e a1.
- Índice com lacuna: as janelas sem dados saem `historico_insuficiente`/`indisponivel`. Isso está correto, não é bug.

**Decisões da etapa 4 (22/10/2026)**
- **Janela do payout (D1):** proventos com `data_com` em (t − 12 meses, t], igual ao yield (`data_pagamento` está 95,6% vazia). Parâmetros no `parametros.yaml`, bloco `fundamentos`.
- **Duas classes PN (D2):** média das classes PN que pagaram no evento × `qtd_pn` (limitação na seção 10).
- **Ações da época (D3):** cada provento usa a linha de `v1-acoes_emitidas` com a maior `data_referencia` ≤ `data_com`; sem ela, a mais antiga disponível. (03/11/2026: a quantidade é a `base_atual`.)
- **Point-in-time das ações (D4):** uma linha de `v1-acoes_emitidas` só vale em t se o balanço do mesmo CNPJ com `data_fim_periodo` = `data_referencia` já foi entregue (`data_entrega` ≤ t). **Substituída em 03/11/2026:** a linha vale em t se a sua própria `data_entrega` ≤ t (ex.: HAPV3 ref. 31/03/2023 só vale desde 29/11/2024).
- **Bancos e seguradoras (D5):** pelo **subsetor** do cadastro ("Intermediários Financeiros", "Previdência e Seguros" e, desde 24/10/2026, "Holdings Diversificadas": ITSA4, cuja receita de holding dava margem líquida de 215%), não pelo setor. Margens, EBITDA e endividamento: `nao_se_aplica`.
- **Patrimônio ≤ 0 (D6):** P/VP, ROE e DL/PL saem `nao_se_aplica`.
- **Lucro 12m = 0 e payout com prejuízo (D7):** P/L com lucro zero: sem valor, `lucro_negativo`. Payout com lucro ≤ 0: sem valor, `lucro_negativo`.
- **Sem provento na janela (D8):** yield e payout = 0,0 com `ok` (não pagar é um fato, não ausência de dado).
- **BDR (D9):** P/L, P/VP, yield e payout `indisponivel` (a coleta não traz proventos de BDR e a razão BDR/ação é desconhecida); ROE, margens, EBITDA e endividamento calculados se houver balanço (pelo tipo do período: JBSS32 até 08/06/2025 é ON).
- **Média do setor por empresa (D10, vale para as etapas 3 e 4):** exclui todas as ações do mesmo CNPJ e conta cada CNPJ uma vez (primeiro a média das ações da empresa com valor, depois a média entre empresas). Ticker sem CNPJ conta como empresa própria. A média só usa valores com status `ok`: no P/L, empresa com `lucro_negativo` não entra. **Atualizado em 23/10/2026:** no painel, a agregação entre empresas passou a ser a **mediana** (`media_setor(..., agregacao="mediana")`); a `ret_vs_setor` do modelo segue com a média. **Atualizado em 24/10/2026:** a rentabilidade do setor no painel sai da série `SETOR_SEM:<ticker>` (média igual por empresa dos retornos diários, sem a própria empresa); a mediana fica para os indicadores de valor.
- **Balanço de referência (D11):** o documento mais recente entregue até t. Os 12 meses exigem os 4 trimestres que terminam nele; senão `historico_insuficiente`.
- **Valor de mercado (D12):** "só uma classe negociada" = só uma classe no cadastro. Classe do cadastro sem preço no dia: `indisponivel`. Quantidade = `base_atual`.
- **Proventos e mudança de ticker:** a `v1-mudancas_ticker` serve só para achar a empresa (CNPJ); a classe (ON/PN) sai do final do ticker **original** do provento. O yield (e a soma por ano e a lista do ticker) só usa proventos do ticker atual e de tickers antigos da **mesma classe** (ex.: ELET3 → AXIA3); em conversão de classe (ex.: CPLE6 PN → CPLE3 ON), o provento antigo fica fora do yield. O payout usa todas as classes ON e PN da empresa. Linha antiga da mesma classe que colide com uma do ticker atual (mesmo tipo e `data_com`) é descartada.
- **Payout por ano:** usa o lucro líquido da própria DFP do exercício.
- **Lista de proventos:** mostra o ticker atual.

**Decisões da etapa 5 (22/10/2026)**
- **E1 Horário:** vale `v1-noticias`; `raw_articles` só confere.
- **E2 Pré-abertura:** 08:00:01 até a abertura → pregão do mesmo dia (no painel). No modelo, desde N2-A, pré-abertura, pregão e noite formam uma janela só (seção 7.2).
- **E3 Sem horário:** 23:59:59 da data → noite do pregão daquela data (seção 7.2).
- **E4 Janela sem notícia:** `noticias_dia_qtd = 0`, tom/extremo vazios. Antes do início da cobertura de notícias (menor data de publicação no banco) **e nos pregões de `experimento.periodos_sem_coleta`** (hoje 01/01/2025 a 31/07/2025; decidido em 01/11/2026), todas as colunas de notícia ficam vazias, inclusive a quantidade: não houve coleta, logo não é "sem notícia". A `mudanca_tom` também fica vazia enquanto a base de 30 pregões tocar o período (mesma regra da cobertura).
- **E5 / E6 Ranks:** notícias brutas, menos `noticias_dia_qtd` (rank desde 01/11/2026); preço, volume e mercado em rank `(pos − 1)/(n − 1)`, só entre as ações do universo do modelo no pregão, antes de descartar as linhas sem alvo.
- **E7 `mudanca_tom`:** base = todas as notícias da empresa (noite, pregão, pré-abertura) com pregão de referência nos 30 pregões anteriores a t (sem t); mínimo de 5 notícias com score.
- **E8 `tom_setor`:** média, entre as outras empresas do setor (sem o próprio CNPJ) presentes no universo do dia, do tom da janela (`noticias_dia_tom`) de cada empresa; cada empresa 1 voto.
- **E9 `tom_mercado`:** média dos scores da janela das empresas do universo do dia, cada `id` uma vez.
- **E10 Repetidas:** mesma empresa, mesma data de publicação e mesmo título normalizado contam uma vez (a de **momento de publicação mais cedo**; no mesmo momento, a com probabilidade do FinBERT; desde 01/11/2026); documentos `cvm_ipe` não são deduplicados. **Entre origens (decidido em 01/11/2026; `deduplicar_entre_origens` no `parametros.yaml`):** a regra acima passa a valer só dentro da mesma origem, e duas linhas da mesma empresa em origens diferentes (fora `cvm_ipe`) contam uma vez se tiverem (a) o mesmo título normalizado sem o sufixo " - Veículo" e sem pontuação (`normalizar_titulo`), com pelo menos `titulo_palavras_min_entre_origens` (5) palavras e `data_publicacao` a até `janela_dias_entre_origens` (1) dia, ou (b) a mesma URL (`link` × `resolved_url`, domínio + caminho, sem janela de data e sem mínimo de palavras). Fica a de **momento de publicação mais cedo** (decidido em 01/11/2026; a hora real, ou 23:59:59 da data sem hora: cópia posterior nunca muda o passado); no mesmo momento, a com probabilidade, depois a com **hora real** e o menor `id`. A comparação é só contra as cópias mantidas, sem fechamento transitivo. Notícia sem probabilidade é **ausente** (nunca neutra): conta em `noticias_dia_qtd`, fica fora do tom, do extremo, da `mudanca_tom` (mínimo de 5 conta só as com score), do `tom_setor` e do `tom_mercado`; o JSON do dataset traz `sem_probabilidade` e o `execucao` avisa quando > 0. No painel, uma notícia sem probabilidade deixa o resumo do dia `indisponivel`.
- **E11 Dias de resultado (modelo 3b):** `v1-balancos.data_entrega`, com a regra das 23:59:59 → `dia_resultado = true` no pregão cuja noite contém a entrega. Ao vivo, os balanços para esta marca são lidos até D − 1 dia (entrega no fim de semana cai na noite de t); os do painel continuam até t. Limitações: balanço reapresentado fica com a data da última versão; divulgação antes da abertura cai um pregão depois.
- **E12 Histórico mínimo:** retornos exigem o preço base; volatilidade e volume relativo 20 pregões completos; beta 252/120; exposições 120/60; 52 semanas 252/120; `mudanca_tom` 30 pregões.
- **E13** `ret_1d` usa o último preço disponível até 5 pregões antes da data-alvo (seção 6, "Base velha"); `salto_abertura` exige o pregão anterior.
- **E14** `ret_vs_setor` exclui a empresa inteira (D10).
- **E15 Saída:** CSV + JSON (contagens, sha256, parâmetros) em `saida/experimento/` (fora do git).
- **E16 Última linha:** fica no dataset sem alvo (é a linha da previsão ao vivo); o treino a descarta. As variáveis da noite dela exigem a data do próximo pregão (informada pela rotina); sem ela, ficam vazias.
- **N1-A Meia-noite do Pacífico (23/10/2026):** notícias com 00:00:00 em Los Angeles (04:00/05:00 de SP; ~89% das notícias) viram "só data" na camada de leitura (`fontes.aplicar_regra_so_data`, coluna `precisao_hora`), em `v1-noticias` e `raw_articles`. `raw_articles.published_precision` não ajuda: marca `date` só nos documentos da CVM (as 131.616 de meia-noite vêm como `datetime`). Pedido de horário real à coleta na seção 10.
- **N2-A Janela única (23/10/2026):** colunas `noticias_dia_*` na janela 08:00:01 de t → 08:00 do próximo pregão; `noticias_pregao_tom` e o modelo 2 saem; `experimento.inicio_janela` no `parametros.yaml`.
- **Horários da B3 desde 04/11/2019 (cadastrados em 24/10/2026):** períodos de 17h/18h e quartas de cinzas (abertura às 13h) de 2020 a 2024 no `parametros.yaml` (fontes: B3 OC 020/2022 e OC 125/2022; os demais por notícias da época; o início em 04/11/2019 a conferir). O calendário só exige o horário do pregão que cai na data de uma notícia (ou de uma entrega de balanço, E11) a classificar: pregão sem horário e sem notícia não gera erro.

**Acréscimo de 03/11/2026 (emissor, base atual, JBS, Natura, CVM)**
- R1 emissor por período (`processamento/emissores.py`, `cadastro_na_data`; dataset com `cnpj_emissor` interno, `empresa` inalterada);
- R2 base atual (substitui a correção do "erro ações × preço"; não é vazamento: preço ajustado × qtd base atual = valor da época);
- R3 D4 pela entrega das ações (os trechos do `multiplos_diarios` incluem essas entregas);
- R4 `situacao` das duas tabelas;
- R5 `v1-emissores_ticker` estrita (motivo: sem ela, JBS e Natura sairiam com CNPJ e zeros falsos);
- R6 corte BDR só para troca não coberta;
- R7 eventos só no diagnóstico (`substituir_serie` não usa: o envio "quando muda" já substitui a série cujos pontos antigos mudam);
- R8 composição mapeada;
- R9 `fora_do_pregao_conhecidas`;
- R10 CVM sem períodos vazios, NATU3 fora dos eventos, JBSS3 fora das exclusões, `VERSAO_PREPARACAO` 7 (modelo da versão 6: top 5 fica de fora até retreinar; `sha_parametros` muda);
- R11 limitação dos pares de setor do painel;
- Registrado em `docs/protocolo_variaveis.md`, seção 8: D5 revista (dados novos antes do teste final geram nova rodada oficial do protocolo e da busca), critério 5 mantido como escrito e P/VP fora da rodada 3.

**Decisões da etapa 6 (23/10/2026; plano completo, com os casos de teste, em `docs/plano_etapa6.md`)**
Com ~1 ano de histórico, a etapa 6 é **só teste de funcionamento** (3.4): o relatório gerado abre com o aviso "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO", e nenhum número dele vale como conclusão.
- **F1 Teste final:** de 23/06/2026 (período nunca olhado; jan–jun/2026 já foram vistos na avaliação da v1) até a véspera da entrada em produção (etapa 8), em `treino.teste_final.inicio`/`fim`. `fim` vazio = trava ativa. Entram só as linhas com dia do alvo (t+1) ≤ `fim`; a linha do `fim` em diante é o teste ao vivo (7.5).
- **F2 Trava:** o teste final só roda com `fim` preenchido, `treino.teste_final.liberado: true`, a opção `--teste-final` **e** sem o registro `docs/teste_final_usado.json` (criado no uso; uso único). Desde 08/11/2026, exige também a medida de dados novos do mesmo dia (`docs/medida_dados_novos_<hoje>.json`, de `python -m processamento.experimento.medida_dados_novos`). O `novo` dela tem de ser o dataset do teste final, e o `congelado`, o dataset dos metadados dos modelos. A decisão tem de ser `rodada_oficial_continua`, sem `parar_e_perguntar` (protocolo, seção 8, nota da D5). Sem isso, a recusa sai com código 2 e nada é gravado. No modo desenvolvimento, as linhas a partir de `inicio` e o pregão de embargo antes dele saem logo na leitura; no modo teste final, as linhas depois do `fim` também.
- **F3 Avaliação do teste final:** walk-forward mensal dentro do período, com a configuração (colunas e hiperparâmetros) congelada nos metadados do desenvolvimento, como no retreino da 7.7.
- **F4 Linhas:** todos os modelos usam só as linhas a partir de `treino.inicio_experimento` (fixo em 2021-01-01, decidido em 01/11/2026), para comparar o modelo 1 com o 3 nas mesmas linhas.
- **F5 Walk-forward:** treino mínimo de 3 meses; cada dobra testa um mês. O treino tem todos os pregões antes do 1º dia de teste, **menos o imediatamente anterior** (embargo de 1 pregão: o alvo dele olha o 1º dia de teste).
- **F6 Blocos complementares (7.4):** os de preço são escolhidos no modelo 1 e herdados pelo 3; o de notícias (`tom_setor`, `tom_mercado`) é testado só no 3. Um bloco entra se o AUC médio por pregão subir mais de 0,005.
- **F7 Grade:** `max_depth` {2, 3} × `min_child_weight` {50, 200} sobre o ponto de partida da 7.4, escolhida no modelo 3 **só nas dobras de desenvolvimento** e aplicada a todos os XGBoost. As métricas de desenvolvimento ficam otimistas (escolha e medida nas mesmas dobras): o número honesto é o do teste final.
- **F8 Desempate do top k:** score decrescente, depois ticker crescente. "Últimos k" = os k finais da mesma ordem.
- **F9 Faixa do acaso:** 10 mil sorteadores, com semente fixa, cada um sorteando k ações por pregão; faixa = percentis 2,5 e 97,5 da taxa de acerto **do período**. Uma faixa só para todos os modelos (as linhas são as mesmas).
- **F10 Regra da volatilidade:** ações mais calmas primeiro (score = 1 − rank da `volatilidade_20d`); volatilidade vazia = score neutro 0,5.
- **F11 Regressão logística:** mediana + indicador de vazio, padronização, C = 1, as mesmas colunas do modelo 3.
- **F12 Modelo 3b:** as previsões do modelo 3 avaliadas só nos dias de resultado (AUC do 3 × do 1, dentro e fora desses dias), sem treino separado.
- **F13 `alvo_abertura`:** coluna nova `alvo_abertura_valido` no dataset (abertura do IBOV em t+1 ≠ fechamento em t). As mesmas previsões são avaliadas só nos dias válidos (seção 10).
- **F14 Teste "hora real na noite" (7.5):** versão de dataset `hora_real_noite` (`precisao_hora = 'hora'` e `inicio_janela = "fechamento"`). Exploratório: a `mudanca_tom` fica quase toda vazia.
- **F15 Bootstrap:** circular, em blocos de 5 pregões, 2000 reamostragens.
- **F16 Calibração e chance:** ECE com 10 faixas; aprovada se ECE ≤ 0,02 com pelo menos 5000 linhas. A chance só é exibida com calibração aprovada **e** `liberar_chance: true` (decisão manual); até lá sai `valor: null`, `exibir: false`, `status: calibracao_nao_conferida` (como no exemplo da 8.3).
- **F17 Modelos salvos:** `modelos/<família>-AAAA-MM.json` (modelo 3) e `modelos/<família>-m1-AAAA-MM.json` (modelo 1, top 5 sombra); a família é a de `treino.familia_producao` (`xgb` desde a rodada 3), cada um com `.meta.json` (colunas, período de treino, hiperparâmetros, configuração de origem, semente, métricas, universo, sha256 do dataset, versões das bibliotecas). Antes do histórico completo: `provisorio: true`, treinados só com o desenvolvimento.
- **F18 Semente:** uma só, `20261023`, em tudo (XGBoost com `n_jobs=1`, sorteios, bootstrap, logística).
- **F19 Saídas:** `saida/experimento/treino/dev-<data do dataset>/` (fora do git): `relatorio.md`, `metricas.json`, previsões e resumos diários. O treino lê só os CSV do dataset (nunca o banco).

**Decisões da etapa 7 (23/10/2026; plano completo, com os casos de teste, em `docs/plano_etapa7.md`)**
- **S1 Datas:** D = dia da rotina (pregão previsto); t = último pregão antes de D. Fase 1 e notícias com `data_referencia = t`; `experimento_top` e `execucao` com D; `dados_ate` = 08:00 de D.
- **S2 Folha:** todo número de indicador em `{valor, status}`; cadastro pode ter texto nulo sem status.
- **S3 Arquivos:** um por pacote em `saida/D/`, com envelope de lote; cada registro com os metadados.
- **S4 Quando muda:** comparação com o estado do último envio (`saida/estado/`); `substituir_serie` quando um ponto antigo muda; `removidos` para o que sumiu; sem estado, vai tudo.
- **S5 Setor (atualizado em 24/10/2026):** uma série por ação, `SETOR_SEM:<ticker>`: média por empresa dos retornos diários (preço em t e no pregão anterior) das ações ON/PN/UNIT do setor, sem a própria empresa; BDR nunca entra; retorno suspeito (seção 6) não entra; dia sem retorno = ponto vazio e a cadeia segue. A `rentabilidade.setor` do `resumo_acao` é a razão dela. A antiga `SETOR:<nome>` (com a própria) saiu.
- **S6 Índices base 100:** CDI com as taxas de datas < d; IPCA com meses fechados até K(d); lacuna = `indisponivel` dali em diante.
- **S7 % dos índices** em `mercado_dia.indices`.
- **S8 P/L, P/VP e yield diários** em `series_diarias`, calculados por trechos entre entregas de balanço (`fatos/multiplos.py`).
- **S9 Notícias do painel:** mesma janela do modelo; rótulo com empate = neutro; destaque protagonista → força do tom → mais recente.
- **S10 Top 5:** modelo do mês de D ou o mais recente anterior (com aviso); válido só com modelo oficial, até as 10h e depois do fim do teste final; sombras e probabilidades só no registro.
- **S11 Registro do top 5** em `registros/experimento/` (versionável). Com `treino.teste_final.fim` preenchido (produção), é de uso único: gravado na 1ª geração e nunca sobrescrito, e a rodada repetida do mesmo dia reconstrói o pacote do registro. Com `fim` vazio (testes de funcionamento), cada rodada gera de novo e sobrescreve o registro do dia.
- **S12 Histórico vazio até a produção;** nenhum dia do teste final é fechado.
- **S13 Validador próprio** (`saida/contrato.py`), sem dependência nova.
- **S14 Textos prontos** (`saida/textos.py`), com `tom_neutro = 0,05` e as faixas do beta (desde 24/10/2026, |beta| < 0,2 = "quase não acompanha o Ibovespa").
- **S15 Acréscimos no `resumo_acao`:** `proventos_por_ano`, `ebitda.rotulo`, `endividamento.aviso`; sem status de grupo.
- **S16 `ativo_no_universo`** = candidata do experimento em t (tipo aceito, não excluída, na composição), mesmo sem preço no dia.
- **S17 Ponto de entrada** `python -m processamento.saida --data D`; a etapa 8 chama `gerar(...)` como função.
- **S18 Bloco `saida`** no `parametros.yaml` (limite das 10h, pastas, `tom_neutro`).
- **S19 Janelas do pacote:** a interface mostra 1m, 6m e 1a. `series_diarias` (inclusive P/L, P/VP e yield diários) com os últimos 253 pregões até t; base 100 sem rebasear (âncora no 1º dia da série; a interface divide pelo 1º valor do recorte); `inicio_janela` em cada série, e o ponto que sai pelo corte não dispara `substituir_serie`; `fundamentos_trimestrais` com os 8 trimestres mais recentes; `proventos` e `proventos_por_ano` com 5 anos; `experimento_historico` sem corte. As contas usam o histórico inteiro; P/L, P/VP e yield por trechos só nos 253 pregões (~8 s por rodada); as séries `SETOR_SEM:<ticker>` seguem a mesma janela e a mesma âncora.
- **S20 Formato compacto só no `series_diarias`:** `datas` + `valores` (listas paralelas) + `status` em trechos `{de, ate, status}` só para os pontos que não são `ok`; números sem arredondar (2,6 MB no 1º envio com 253 pontos, contra 8,0 MB em folhas; ~47 KB por dia); com as séries `SETOR_SEM` (24/10/2026): +0,83 MB na carga completa (~3,1 MB no pacote de 23/10) e +34 KB por dia. Os outros pacotes seguem com a folha.

**Decisões da etapa 8 (23/10/2026; plano completo, com os casos de teste, em `docs/plano_etapa8.md`)**
- **R1 Dia de pregão:** lista `feriados_b3` no `parametros.yaml`, conferida contra os pregões do banco, com aviso 30 dias antes de `feriados_b3_valido_ate` vencer.
- **R2 Sem entrega até 09:45:** rodada `falhou` que grava **só o `execucao.json`** (`coleta_status.motivo`, horários das consultas e o aviso); os outros 9 pacotes não são gerados (ajuste aprovado em 23/10/2026).
- **R3 IBOV sem o pregão anterior previsto:** espera só se `precos` não concluiu; concluída → segue com aviso.
- **R4 Depois das 09:45:** continua consultando até 12:00 para uma rodada tardia (o top gerado depois das 10h sai com `valido_para_historico = false`).
- **R5 `noticias` ou `enriquecimento` não concluídas:** só aviso; a validade do top segue a 8.3.
- **R6 Retreino:** na rotina, antes do top, só em produção (`treino.teste_final.fim` preenchido); se faltar no mês, repete nos pregões seguintes.
- **R7 Modelo oficial:** chave manual `treino.modelo_oficial` (`false` até decisão explícita do usuário; pegadinha 13).
- **R8 Dia sem pregão:** sai sem gravar nada e sem mudar o contrato.
- **R9 `coleta_status`:** campos opcionais; versão continua `"1.0"`.
- **R10 Checagem diária:** limites da seção 6; só avisos, ajustáveis no bloco `rotina.checagem`.
- **R11 Entrada em produção:** `python -m processamento.producao --inicio D0` confere e arquiva; o usuário edita `fim` e `liberado`; só com `modelo_oficial: true`; D0 = 1º pregão de um mês.
- **R12 Fechar o histórico:** varre todos os tops pendentes; dia que não foi pregão ganha `AAAA-MM-DD.descartado.json` (motivos `nao_houve_pregao`, `pregao_base_diferente`).
- **R13 Onde roda:** PC + Agendador de Tarefas do Windows agora (`scripts/rotina_diaria.ps1`); a escolha para a produção fica pendente (ajuste aprovado em 23/10/2026).
- **R14 Trava:** arquivo `saida/estado/rotina.trava` com validade de 6 h; outra rotina em andamento → código 5.
- **R15 Daily válido:** o daily mais recente de hoje; um daily manual mais novo em andamento faz esperar.

**Pendências internas por etapa**
- **Etapa 4 (payout), resolvida:** `v1-acoes_emitidas` só separa ON e PN. Em empresas com **duas classes PN** (ex.: USIM5 e USIM6), a quantidade de cada classe não é conhecida: regra de aproximação D2 (decisões da etapa 4; limitação na seção 10).
- **Etapa 8 (vindos da etapa 7):** (a) dia de pregão: resolvido (R1); (b) checagem diária: resolvida (seção 6, R10); (c) **entrada em produção** só depois do histórico completo (5 anos) e de `treino.modelo_oficial: true`; então `python -m processamento.producao --inicio D0` confere e arquiva, o usuário fixa `treino.teste_final.fim` e o teste final roda uma vez (R11). **Onde rodar na produção (R13): a decidir.** (d) retreino mensal: resolvido (R6, 7.7); (e) limpar `registros/experimento/` dos testes de funcionamento: pendente, junto com (c), antes da produção; (f) tempo da rodada contra o prazo das 9h45: `gerar` levou ~2 min (medido em 23/10/2026); conferir o tempo no `execucao.json` da primeira rodada real.

**Acréscimo de 24/10/2026 (carga completa, seção 8.7)**
- **Carga completa:** `gerar(..., completo=True)` e `python -m processamento.saida --completo`. Não muda o contrato (versão `1.0`) nem os 10 pacotes; não mexe no estado do envio, nos registros do experimento, nem faz retreino ou fechamento de dias.

**Acréscimo de 24/10/2026 (retornos suspeitos e setor sem a própria empresa; plano em `docs/plano_suspeitos_setor.md`)**
- **Retorno suspeito:** retorno diário do ajustado fora de [−75%, +100%] (base as-of, limites estritos); não corrige o preço, só isola (séries do setor, medianas de P/L, P/VP e yield por 21 pregões, aviso, diagnóstico). Parâmetros no bloco `fase1`.
- **Setor sem a própria empresa:** série `SETOR_SEM:<ticker>` por ação (tipo `setor_sem_empresa`), e a `rentabilidade.setor` é a razão dela (gráfico e tabela batem). Motivo: a planilha e o TCC definem o setor sem a própria ação. A `SETOR:<nome>` saiu do pacote. A versão do contrato continua "1.0" (contrato ainda não está em uso).
- **Experimento:** não muda nesta etapa (pendência na seção 10).

**Acréscimo de 24/10/2026 (histórico novo; plano em `docs/plano_historico_novo.md`)**
- **H1 Calendário:** horários desde 04/11/2019, quartas de cinzas 2020-2024 e 57 feriados (31/12/2019 a 30/05/2024) conferidos com a B3 e com os dias úteis sem IBOV; horário exigido só nos pregões com notícia a classificar.
- **H2 Balanço velho:** `fundamentos.balanco_idade_max_meses: 15`, com o limite no fim do mês (seção 6).
- **H3 Diagnóstico:** `data_mudanca` e texto vazio no título viram nota; hora das notícias em três grupos por ano (hora real, "só data" N1-A, sem hora); `noticia_sem_hora` só sem a marca "date" de `raw_articles.published_precision`; seção nova com a composição sem preço, o status do `corrigir_horas` e a cobertura do experimento por ano.
- **H4 Troca de ação por BDR** não une os históricos (seção 6).
- **H5 IDIV:** substituída pela regra da base velha (24/10/2026): com 2025 faltando, o m1 do IDIV em 21/10/2026 sai `historico_insuficiente` (o `ok` vinha da base de 2024).
- **H6 Especificação** atualizada (3.1, 3.4, 3.5, 6, 8.5, 8.7, 10).
- **H7 Top 5 provisório:** `saida.publicar_top_provisorio` (padrão `false`; seção 8.5).
- **H8 Setor herdado:** ticker fora do `v1-cadastro` ligado a uma empresa do cadastro (mudança de ticker ou raiz de 4 letras com CNPJ único) herda o CNPJ e o setor dela no dataset do experimento (ex. antigo: JBSS3 até 06/06/2025 → setor do JBSS32; desde 03/11/2026 a JBSS3 não tem mais linhas próprias e a JBS entra pelo `v1-emissores_ticker`); os tickers que herdaram ficam em `setor_herdado` no JSON do dataset (seção 6).

**Acréscimo de 24/10/2026 (base velha e pasta limpa; plano em `docs/plano_base_velha.md`)**
- **BV1 Regra:** seção 6, "Base velha"; `fase1.base_defasagem_max_pregoes`: 5, `fase1.ipca_defasagem_max_meses`: 2.
- **BV2 Experimento:** a mesma regra nos `ret_*` (7.3 e E13).
- **BV3 Diagnóstico:** seção "Lacunas nas séries de preços e índices" (nota).
- **BV4 Pasta limpa:** seção 8.5.

**Acréscimo de 26/10/2026 (histórico desde 2021; plano em `docs/plano_historico_2021.md`)**
- **HN1 Período inválido:** ITR fora de 3/6/9 meses e DFP fora de 12 meses são descartadas antes de qualquer conta (seção 6); o diagnóstico lista como nota.
- **HN2 Bradespar:** 03847461000192 sai de `cnpjs_sem_balanco`; o Assaí (06057223000171) fica (seção 3.4).
- **HN3 Notícia sem probabilidade:** ausente, nunca neutra; repetidas preferem a cópia com probabilidade (só no mesmo momento desde 01/11/2026; E10); `sem_probabilidade` no JSON do dataset e aviso no `execucao` (E10).
- **HN4 Calendário:** horários e feriados já cobriam 2021–2022; casos novos de teste nas trocas de horário de 2021 a 2023. Com os índices desde 2021, a base 100 de CDI, IPCA, IDIV, SMLL e IFIX foi reancorada uma vez (fator constante; % das janelas iguais).
- **HN5 Tolerância das séries:** `saida.tolerancia_serie_relativa` (1e-6) na comparação do envio "quando muda" do `series_diarias` (8.1); a âncora da base 100 continua no 1º dia da série.

**Acréscimo de 01/11/2026 (todas as origens; validação em `docs/validacao_wordpress.md`, medição em `docs/medicao_dedup_origens.md`)**
- **O1 Origens:** `wordpress` aceita como as demais; `origens_ignoradas` vazia (seção 3.1).
- **O2 N1-A:** só nas origens de `origens_so_data` (seção 7.2).
- **O3 Cópias entre origens:** regra na E10; o painel e o dataset usam a mesma função (`experimento.noticias.deduplicar`).
- **O4 Publicação:** o contrato continua `1.0`. O `noticias_dia` só traz o pregão t de cada D, então o histórico de 2021–2022 não gera correções na API; a mudança vale dos próximos D em diante. O histórico só muda no dataset, que precisa ser regenerado.
- **O5 Limitação do experimento (registrar no TCC):** a `wordpress` não existe em 2023–2025 nem de 04 a 09/2026, e `noticias_dia_qtd` entra bruta: há mudança de regime no volume de notícias entre os anos. Olhar a robustez por ano (7.5). Ao vivo, uma cópia "só data" do Google News pode aparecer em D e, no histórico, ser trocada por uma cópia de outra origem **publicada antes** (E10), mudando o pregão da notícia no treino; cópia posterior nunca a substitui.
- **O6 `papel = errada`:** substituída pelo acréscimo abaixo (P1).

**Acréscimo de 01/11/2026 (papel `errada` e retornos suspeitos no experimento)**
- **P1 `papel = errada`:** sai na leitura, em todas as versões, na rotina e no `noticias_dia` (seção 3.1). O filtro vem antes das repetidas: cópia `errada` nunca vence uma válida. Com `errada` numa classe e outro papel em outra classe da mesma empresa, a notícia fica e conta uma vez. O JSON do dataset traz `papel_ignoradas` e `papel_vazio`. Os diagnósticos `wordpress` e `dedup_origens` leem sem o filtro, para continuarem comparáveis.
- **P2 Notícia sem julgamento:** fica (1.343 linhas, 0,33%, medido em 01/11/2026). `juiza` entra em `rotina.etapas_conferidas`: etapa não concluída gera só aviso.
- **P3 Limitações do filtro (registrar no TCC):** a juíza ainda não foi avaliada e o corte é desigual (`google_news` 10,7%, `wordpress` 1,5%, `cvm_ipe` 0%), o que aumenta um pouco a mudança de regime da O5. Ao vivo, com a juíza falhando, uma notícia sem `papel` entra, e pode sair do histórico depois de julgada.
- **P4 Retorno suspeito no experimento:** máscara em `ret_*`, `ret_vs_setor`, `salto_abertura`, `dist_*_52s` e no alvo (7.1, 7.3, 7.6). Só em `experimento/variaveis.py` e `experimento/alvo.py`: a máscara nova das contas do experimento não altera o painel. Mas a lista explícita `fase1.eventos_retorno_suspeito` (02/11/2026) vale também para o painel, porque é uma única definição de suspeito para painel, experimento e diagnóstico (seção 6).
- **P5 Publicação:** o contrato continua `1.0`. Os dias já publicados de `noticias_dia` não mudam; a regra vale dos próximos D em diante. O dataset precisa ser regenerado nas três versões.

**Acréscimo de 01/11/2026 (cobertura, início do treino e vazamento; revisão em `docs/regras_dataset.md`)**
- **C1 Período sem coleta:** `experimento.periodos_sem_coleta` (E4); vale no dataset (`experimento/tom.py`) e no `noticias_dia`; o JSON do dataset traz `pregoes_sem_coleta`.
- **C2 Diagnóstico:** seção "Notícias por mês": avisa mês completo abaixo de `experimento.noticias_mes_fracao_minima` (25%) da mediana dos 12 meses anteriores e período cadastrado que voltou a ter notícias. Só nota.
- **C3 Início do treino:** `treino.inicio_experimento: "2021-01-01"` (F4). O desenvolvimento vai de 01/2021 a 06/2026.
- **C4 Cópias:** o momento de publicação mais cedo vence, entre origens e dentro da mesma origem; probabilidade e hora real só desempatam no mesmo momento (E10). Consequência aceita: cópia mais cedo sem probabilidade fica e a posterior com probabilidade sai.
- **C5 Teste de vazamento:** `tests/test_vazamento_experimento.py` cobre vários pregões, mudança só em t+1, mudança depois de t+1, cópia futura entre origens, cópia depois do corte que mudaria o pregão; o dataset lê `v1-indices` (SMLL), `v1-proventos` e `v1-raw_ipe_docs`, e não lê `v1-acoes_emitidas`. Desde 02/11/2026 o teste também cobre balanços, proventos e documentos futuros, inclusive trimestre antigo entregue depois de t, reapresentação futura e o sorteio do controle.

**Acréscimo de 01/11/2026 (rank da quantidade e versão de preparação)**
- **V1 `noticias_dia_qtd` em rank** (7.3, E5). O CSV continua bruto; os motivos do top usam o valor bruto.
- **V2 `noticias_dia_extremo` em rank:** só variante testada no desenvolvimento (coluna `noticias_dia_extremo_rank`, criada em `preparar`); entra no lugar da bruta se o AUC médio por pregão subir mais de `treino.ganho_minimo_bloco`. Os motivos falam sempre da coluna do dataset.
- **V3 `versao_preparacao`** (`preparacao.VERSAO_PREPARACAO`, hoje 5): sobe quando mudam ranks, colunas ou regras que afetam os valores. Vai no JSON do dataset e nos metadados do modelo. O treino recusa dataset de outra versão.
- **V4 Trava sem parar a publicação:** modelo 3 ou modelo 1 de outra versão: **só o top 5 fica de fora**, com aviso no `execucao` e sem registro; os outros pacotes saem normalmente. Com o top não publicado (8.5) a rodada fica `ok`; com o top publicado, `parcial`.

**Acréscimo de 02/11/2026 (protocolo de variáveis, blocos A e B; `docs/protocolo_variaveis.md`)**
- **Q1 Colunas:** 7.3, "Colunas do protocolo"; `VERSAO_PREPARACAO` = 5. A comparação do TCC continua modelo 3 × modelo 1 com as notícias atuais.
- **Q2 SMLL:** sem SMLL na `v1-indices`, `exposicao_small` fica vazia, com aviso no `execucao` e `smll_pregoes = 0` no JSON do dataset. Sem a tabela `v1-indices`, a leitura para (seção 2.2), como nas outras tabelas do contrato.

**Acréscimo de 02/11/2026 (protocolo, blocos C, D, E e controle)**
- **Q3 Leitura:** o dataset passa a ler `v1-proventos` (tickers originais) e `v1-raw_ipe_docs`; continua sem ler `v1-acoes_emitidas`. A proteção contra o futuro fica dentro de cada conta, além do corte da leitura.
- **Q4 Reapresentações:** em `v1-balancos`, a coleta guarda só a última versão e move `data_entrega`. Por isso `dias_desde_resultado` ignora atraso acima de 180 dias, e uma reapresentação de até 180 dias não se distingue de entrega normal. Regerar o dataset depois de uma reapresentação pode mudar valores antigos dessa empresa (a linha some do passado): não é vazamento, porque nunca se usa valor com `data_entrega` depois de t. Em `v1-raw_ipe_docs`, cada versão tem protocolo e data próprios. Marcam `fato_relevante_cvm` a apresentação original e, desde 02/11/2026, a **reapresentação sem original**, na própria `data_entrega`: `data_referencia` preenchida, entrega de 0 a 10 dias depois dela, e nenhum original da empresa já entregue com a mesma referência ou nos 10 dias anteriores. Das órfãs com a mesma referência, só a primeira conta. Medido em 02/11/2026: 60 reapresentações sem original, 58 delas dentro dos 10 dias. Original entregue depois nunca desfaz a marca: a conta não olha o futuro.
- **Q5 Cobertura da CVM:** começa na menor `data_entrega` de qualquer categoria. Documento em dia sem pregão vai para o último pregão antes, mesmo que esse pregão esteja vazio (ex.: entrega em 01/01/2024 cai em 28/12/2023).
- **Q6 Controle:** semente = `treino.semente`. Se aprovado nos critérios 1 a 4, a rodada é inválida (`docs/protocolo_variaveis.md`).

**Acréscimo de 02/11/2026 (executor do protocolo; `docs/protocolo_variaveis.md`, seção 7)**
- **Q7 Executor:** `python -m processamento.experimento.protocolo_execucao`, em `experimento/protocolo.py` (regras), `protocolo_registro.py`, `protocolo_relatorio.py` e `protocolo_execucao.py`. Só lê o CSV de desenvolvimento; não abre o teste final, não grava em `modelos/` e não lê o banco. `avaliacao.ic_bootstrap_blocos` ganhou `percentis` (padrão igual) e `treino.selecionar_blocos` foi extraída de `selecionar_configuracao`, sem mudar resultados.
- **Q9 Busca:** `python -m processamento.experimento.busca_execucao`, em `experimento/busca.py` (regra) e `busca_execucao.py`, com as regras de `docs/protocolo_variaveis.md`, seção 6. Exige a configuração congelada de uma rodada válida; só lê o CSV de desenvolvimento e não grava em `modelos/`. `modelos.py` e `prever_walk_forward` ganharam o LightGBM (`lightgbm==4.7.0`; só a busca importa). `treino --configuracao` usa a configuração final no desenvolvimento em vez de `selecionar_configuracao` (família XGBoost ou logística, a de `treino.familia_producao`; recusado no teste final). Sem a opção, nada muda.
- **Q8 `var_lucro_aa`:** conta própria de lucro e PL por empresa em `experimento/resultados.py`, ~50 vezes mais rápida, com a mesma regra de `fatos/trimestres.py`. `tests/test_exp_var_lucro_equivalencia.py` compara as duas: mudança na regra de trimestres precisa valer nas duas.

---

**Acréscimo de 02/11/2026 (resultado da rodada 1; `docs/protocolo_variaveis.md`, seção 8)**

- **Protocolo:** bloco A (`posicao_fechamento`, `mom_12_1`, `liquidez_20d`, `ret_idio_5d`) adotado; B, C, D, E e o controle reprovados; `preco_contexto`, `macro` e `noticias_contexto` fora da base. Colunas em `docs/protocolo_congelado_rodada_001.json`. Relatório: `docs/protocolo_rodada_001.md`.
- **Busca:** a regressão logística (C = 1) venceu: ganho de AUC +0,00575 contra o XGBoost do ponto de partida, que passa a ser a terceira referência. Configuração: `docs/configuracao_final_rodada_001.json`. Relatório: `docs/busca_rodada_001.md`.
- **Reprodução:** protocolo e busca repetidos com as mesmas entradas deram o mesmo `sha_resultado`.
- **Comparação do TCC no desenvolvimento (exploratória, `modelo_oficial` false):** modelo 3 × modelo 1 com a logística, ganho de AUC −0,00040 (IC 95% de −0,00201 a 0,00118). Anexo: `docs/busca_rodada_001_comparacao_tcc.md`. Sensibilidade: `docs/busca_rodada_001_sensibilidade.md`.
- **Produção:** passou para a logística em 02/11/2026 (commit 7ccdf88, com os textos dos motivos do bloco A) e voltou ao XGBoost com a rodada 3 (acréscimo de 08/11/2026, abaixo).

**Acréscimo de 08/11/2026 (resultado da rodada 3; `docs/protocolo_variaveis.md`, seção 8)**

- **Dataset:** v7, `dataset-todas-2026-11-06.csv`, sha256 `c954b437c55e…` (conferência em `docs/conferencia_rodada_003.md`). Cópia congelada fora do repositório e no Google Drive do usuário (D6 fechada).
- **Protocolo:** só o bloco A adotado; B, C, D, E e o controle reprovados. Reprodução (rodada 4) com o mesmo `sha_resultado`.
- **Busca:** nenhum candidato aprovado, então vence a referência, o XGBoost do ponto de partida (`docs/configuracao_final_rodada_003.json`). A logística entra no TCC só como achado ("quase venceu"): ganho de 0,00482 (≤ 0,005), IC 99,5% [−0,00018; 0,00981], queda do top 5 de 0,55 ponto percentual. Comparação com a rodada 1 em `docs/comparacao_rodadas_001_003.md`.
- **Produção:** `treino.familia_producao: "xgb"`. Os modelos `modelos/xgb-2026-06.json` e `xgb-m1-2026-06.json` são provisórios (`modelo_oficial` false), treinados de 04/01/2021 a 19/06/2026, e reproduzem exatamente as métricas da busca 003. Os modelos antigos estão em `modelos/antigos/`.
- **Comparação do TCC no desenvolvimento (exploratória):** modelo 3 × modelo 1 com o XGBoost, ganho de AUC por pregão de +0,00051 (IC 95% de −0,00178 a 0,00287). Top 5: 0,5167 × 0,5051. Sensibilidade em `docs/busca_rodada_003_sensibilidade.md` e comparação com a rodada 1 em `docs/comparacao_sensibilidade_001_003.md`.
- **Hashes:** a mudança da família muda `sha_parametros`, e a da chave `configuracao` nos metadados muda `sha_codigo`. Uma rodada nova com as mesmas entradas não conta como repetição da 3.

## 10. Pendências externas (não bloqueiam a implementação)

| Pendência | De quem |
|---|---|
| Zeros em `v1-balancos`: `emprestimos_curto_prazo` e `emprestimos_longo_prazo` = 0 **juntos** em 89 linhas de 12 empresas que não são banco (ex.: CSNA3, SBSP3, RDOR3, PCAR3, MGLU3, que têm dívida), e `aplicacoes_financeiras` = 0 em 134 linhas de 19 empresas. Provável conta não encontrada gravada como 0 (deveria ser `NULL`). Pedido à coleta: gravar `NULL` quando a conta não é achada. Enquanto isso, o processamento trata CP e LP = 0 juntos como ausente (seção 6, "Empréstimos zerados"); aplicações = 0 continuam valendo | Coleta |
| Notícias de jan–jul/2025 (sem coleta: 38 artigos em janeiro e nenhum de fevereiro a julho; ao preencher, rever `experimento.periodos_sem_coleta`; o diagnóstico avisa) e horário real das de 2021 a 2024 no Google News (~90% sem hora) | Coleta |
| Etapa manual `corrigir_horas`: a execução `2026-10-23-coletar-135621` (tipo `coletar`) está `agendada`, com a etapa `pendente`, desde 23/10/2026: não rodou. Provavelmente a correção do horário das notícias pedida abaixo. **Quando concluir, reavaliar a regra N1-A** (seção 7.2); o diagnóstico mostra o status | Coleta |
| Composição do Ibovespa de fonte não oficial: 115 das 137 linhas de `v1-composicao_ibov` vêm de `paccafelipe_csv` (as outras 22, de `rebalanceamento`). Conferir contra as carteiras oficiais da B3; 2020 não é coberto | Coleta |
| 46 tickers da composição sem nenhum preço em `v1-precos` (ex.: ALPA4, BRML3, CIEL3, GOLL4, VIIA3; lista no diagnóstico): ficam fora do universo nas datas em que estavam no índice. O viés de sobrevivência continua (seção 3.4); limitação registrada no TCC | Coleta |
| Histórico antigo faltando depois da troca de ticker: AZUL4 e PETZ3 não têm preço em `v1-precos`; AZUL3 e AUAU3 só têm desde 13/01/2026 e 05/01/2026 | Coleta |
| GMAT3, RAPT4 e SAUD3 estão no cadastro e nunca na composição: ficam fora do universo nas datas cobertas pela composição | Coleta (conferir) |
| Autenticação, endereço e forma de envio da API | Equipe da API |
| Manter o filtro da juíza desligado na coleta e informar quantas notícias do histórico ficaram sem julgamento | Coleta |
| Validação do FinBERT: já feita pelo usuário; registrar os números (manchetes, % de acerto, por idioma) | Usuário |
| Empresa com duas classes PN (ex.: USIM5/USIM6, BRKM5/BRKM6): `v1-acoes_emitidas` traz só o total de PN, então o payout usa, em cada provento, a média das classes PN que pagaram naquele evento × qtd_pn. É exato quando as classes pagam igual; limitação registrada no TCC. Resolve-se com a quantidade por classe | Coleta |
| Balanço reapresentado: `v1-balancos` guarda só a última versão, com a sua `data_entrega`. Antes dessa data o período fica sem dado (`historico_insuficiente`); não há vazamento, mas a versão original não é recuperável. Limitação registrada no TCC. Resolve-se guardando as versões | Coleta |
| **Horário real das notícias do Google News:** ~91% vêm com 00:00 de Los Angeles (só a data). O processamento trata como "só data" (seção 7.2), o que impede separar pregão de noite. Pedido à coleta: obter o horário real de publicação (ex.: pela página da notícia, no enriquecimento) e marcar `published_precision = 'date'` quando só a data for conhecida | Coleta |
| Notícias coletadas retroativamente: `data_hora_coleta` começa em 07/09/2026 (mediana de ~133 dias entre publicação e coleta). O conjunto histórico pode diferir do que estaria disponível ao vivo em cada data (notícias apagadas ou que só apareceram depois). Limitação registrada no TCC; ao vivo, o corte vale desde set/2026 | Coleta |
| Abertura da ação = fechamento do pregão anterior em ~11% dos pares (ação, dia) (5.021 de 45.839, medido em 23/10/2026; maior em ações de preço baixo, ex.: RAIZ4 48%). Provável igualdade real (passo mínimo de R$ 0,01), **não confirmada**; afeta o `salto_abertura`. Limitação registrada no TCC | Coleta |
| Abertura do IBOV em `v1-precos` (fonte Yahoo): em 32,5% dos pares de pregões consecutivos (557 pares medidos em 23/10/2026), a `abertura` do IBOV é igual ao `fechamento` do pregão anterior (abertura não informada pela fonte). Nesses dias o `alvo_abertura` vira "a ação abriu em alta?", e não "abriu melhor que o Ibovespa?". **Na etapa 6, o `alvo_abertura` é avaliado só nos dias em que a abertura do IBOV ≠ fechamento anterior.** Nenhuma variável do modelo usa a abertura do IBOV (só o `alvo_abertura`); o alvo principal usa o fechamento e não é afetado. Limitação registrada no TCC. Resolve-se com a abertura real do índice | Coleta |
| **Notícias das versões "principais" e "hora real na noite":** a medição de 23/10/2026 (3% a 15% das linhas com alguma notícia antes de out/2026) é anterior ao julgamento do histórico (hoje 0,33% sem julgamento, P2) e à união das origens: **refazer ao regenerar o dataset**. Na "hora real na noite", a amostra continua pequena fora de 2021, 2022 e 2026 (~90% do Google News sem hora real, N1-A), e a `mudanca_tom` fica quase toda vazia (F14) | Coleta |
| **Quantidade de ações em escala errada em `v1-acoes_emitidas`** (remedido em 02/11/2026): as ~25 empresas em milhares de 23/10/2026 não caem mais na regra de suspeita em 30/10/2026. Restam saltos isolados: AZUL3 em 03/2026 (54,7 trilhões, ×18.093, e volta em 06/2026), IGTI11 antes de 12/2021 (×12.812), AUAU3 antes de 03/2025 (×111) e CMIN3 em 12/2025 (×9,9, e volta ÷10 em 03/2026). Pedido à coleta: conferir esses casos e gravar sempre em **unidades**. O processamento continua marcando a quantidade como suspeita quando o P/VP < 0,05 e o P/VP × 1000 ≤ 20, e deixa valor de mercado, P/L, P/VP e payout `indisponivel` (seção 6); o diagnóstico lista as empresas. Esses saltos só caem na regra quando deixam o P/VP baixo demais. Desde 03/11/2026 a coleta marca `situacao` (`corrigido_escala`/`corrigido_digito`) e grava a `base_atual` corrigida | Coleta |
| Carga histórica de 5 anos: enquanto roda (`em_andamento`/`pausando`), o daily nasce `agendada` e só começa quando a carga pausa ou termina; a rotina dá `falhou` (`daily_agendado`) nesses dias. Combinar com a coleta de pausar a carga antes das 08:00 nos dias úteis | Coleta |
| Horário do daily: os documentos da coleta dizem `DAILY_HORA` padrão **18:30** (`02-pipeline-diaria.md`, `07-executor-e-painel.md`, `.env.example` da coleta); a especificação usa 08:00 (confirmado pelo painel: 11:00 UTC). Confirmar que `DAILY_HORA=08:00` está fixado no Railway; se voltar ao padrão, a rotina dá `sem_daily` todo dia | Coleta |
| Execução `tipo = 'etapa'` (ex.: a coleta refaz só a `entrega` pelo painel): a rotina não usa como gatilho (seção 4). Se esse for o jeito normal de consertar um dia, a rotina não enxerga: avisar a coleta | Coleta |
| **Preços com erro de escala em `v1-precos`** (medido em 24/10/2026 no pacote): AZUL3 com `fechamento` e `fechamento_ajustado` ~141 mil vezes maiores de 09/04 a 17/04/2026 (30.599.848 contra ~217), e salto de ×46 em 10/02/2026 sem volta (provável grupamento não ajustado no `fechamento_ajustado`). Pedido à coleta: corrigir o histórico. Enquanto isso, o processamento isola os retornos suspeitos (seção 6) | Coleta |
| **Preço ajustado em float32** (medido em 26/10/2026): `fechamento_ajustado` (e `fechamento`) vêm com precisão de float32 dentro de um `double` (ex.: PETR4 `58.68000030517578`) e o histórico é regravado todo dia, então cada preço ajustado muda alguns bits por dia: o `indice_retorno_total` varia até ~7e-7 relativo sem mudança real (152 de 177 séries entre as cargas de 23/10 e 26/10; as `SETOR_SEM` herdam). Pedido à coleta: calcular e gravar o ajustado em **float64**. Enquanto isso, o envio "quando muda" ignora diferenças abaixo de 1e-6 (8.1) | Coleta |
| **Alvo perto do empate com o IBOV** (limitação, medida em 26/10/2026 no dataset de 23/10): pelo ruído de float32 acima, a cada regeração do dataset os retornos mudam ~1e-7. Em 11 de 117.364 linhas, \|`ret_t1` − `ret_ibov_t1`\| < 1e-6 (2 abaixo de 1e-7): o `alvo` delas pode trocar entre 0 e 1, e o sha256 do dataset muda mesmo sem dado novo. Efeito desprezível (0,01% das linhas); registrado no TCC. Resolve-se com o ajustado em float64 | Coleta |
| **Balanços faltando:** Bradespar (03847461000192) só tem de 2021 até a DFP 2023 (falta 2024 a 2026); Assaí (06057223000171) só tem os ITRs do 1º ao 3º trimestre de 2021 (falta do 4º trimestre de 2021 em diante). Pedido à coleta: carregar esses balanços | Coleta |
| 1.174 notícias Google News "só data" ainda com 04:00/05:00 SP (as outras 260.545 já vêm com hora vazia); N1-A cuida delas; pedido: hora vazia também nelas | Coleta |
| JBSS32 e NATU3 com linha em 20/11/2020 (dia sem IBOV); a grade descarta; pedido: apagar ou conferir | Coleta |
| 6.560 notícias CVM sem FinBERT e sem juíza: seguem a regra de notícia sem probabilidade (E10) e de papel vazio (fica); pedido: processar | Coleta |

**Resolvidas em 03/11/2026:**
- Erro ações × preço: o valor de mercado usa a quantidade da base atual (`qtd_*_base_atual`, seção 6).
- JBS: resolvida pelo emissor por período (seção 6).
- Natura: histórico desde 30/12/2019, emissor por período e sem eventos de retorno suspeito (NATU3 fora de `fase1.eventos_retorno_suspeito`).
- CVM 2023 e jan–jul/2025: períodos vazios (`experimento.periodos_sem_coleta_cvm` vazia; o mecanismo fica).
- Nota: o protocolo (seções 3 a 6) não muda; P/L e P/VP como variável só numa rodada futura.

**Resolvidas em 02/11/2026 (medido no banco):**
- Índices completos: IDIV, SMLL e IFIX desde 30/12/2019, sem lacuna, inclusive em 2025; CDI e IPCA desde 01/2021. A regra da base velha (seção 6) continua valendo para lacunas futuras.

**Resolvidas em 01/11/2026:**
- Experimento × retornos suspeitos: toda conta de preço que atravessa o salto e o alvo ficam `NaN` (seções 6, 7.1 e 7.3; P4). Em 01/11/2026 são 2 casos no banco: PCAR3 em 01/03/2021 (+112,3%) e UGPA3 em 28/06/2021 (+119,3%).

**Resolvidas em 26/10/2026:**
- Notícias sem probabilidade do FinBERT (13.248 no diagnóstico das 11:50, quase todas de 2023): preenchidas pela coleta no mesmo dia (0 na leitura seguinte, de 264.623). A regra para o caso continua (E10).

**Resolvidas em 22/10/2026** (as fontes não tinham os dados; não foi erro da coleta):
- CRFB3, SRNA3 e STBP3 sem preço → removidas da análise (seção 3.4). Registrar no TCC como **viés de sobrevivência**.
- Classes extintas nos proventos (VALE5, AXIA6, CPLE5 etc.) → identificadas pelo `other_codes`; seus proventos contam no histórico e no payout, ligados pela raiz; units ficam de fora (seções 3.4 e 6).
- CNPJs 03847461000192 e 06057223000171 sem balanço → indicadores de balanço `indisponivel` (seção 3.4).
- EBIT, depreciação, empréstimos, caixa e aplicações em `v1-balancos`: preenchidos pela coleta (~90%, como `lucro_bruto`). O diagnóstico passa a tratá-los como parciais; as etapas `cvm_itr_dfp` e `build_entrega` (execução manual `tipo = 'coletar'`) passam a ser conhecidas e só geram divergência se aparecerem num daily. Em 23/10/2026 entrou também `corrigir_horas` (mesma regra: nota).

**Resolvidas em 24/10/2026:**
- `data_mudanca` preenchida em todas as linhas de `v1-mudancas_ticker` (seção 3.1).
- `v1-composicao_ibov` preenchida de 01/01/2021 até hoje (seção 3.5; a fonte não oficial e os tickers sem preço continuam pendentes acima).

---

## Apêndice: glossário rápido
- **Rank:** posição da ação entre as do mesmo dia (0 = menor, 1 = maior).
- **Walk-forward:** treinar com o passado e testar no período seguinte, avançando no tempo.
- **Embargo:** intervalo entre treino e teste para o alvo não vazar.
- **Faixa do acaso:** intervalo em que caem 95% dos escolhedores aleatórios.
- **Calibração:** se o modelo diz 60%, cerca de 60% dos casos acontecem.
- **Point-in-time:** usar só o que já era conhecido naquela data.
- **Upsert:** gravar atualizando se a chave existe, criando se não existe.
- **ITR / DFP:** balanço trimestral / anual entregue à CVM.
- **Unit:** pacote de ações (ex.: KLBN11 = 1 ON + 4 PN).
