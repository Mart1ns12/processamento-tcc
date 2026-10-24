# ESPECIFICAÇÃO DO MÓDULO DE PROCESSAMENTO (fonte da verdade)

> Versão de 23/10/2026. Este arquivo descreve **só o que vale hoje** e deve ser seguido na implementação.
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

**Pergunta do TCC:** o sentimento das notícias, lido pelo FinBERT, ajuda a prever o desempenho das ações? Foco nas **notícias do dia t e da noite, até as 8h de t+1** (antes da abertura do pregão previsto). Como ~89% das notícias só têm a data (seção 7.2), não dá para isolar as publicadas depois do fechamento; esse efeito é medido num teste extra só com as notícias de hora real (seção 7.5).

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
└── rotina.py                # gatilho diário (seção 4)
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
| `v1-noticias` | `id`, `ticker` | `id`, `ticker`, `data_hora_publicacao`, `data_hora_coleta`, `titulo`, `fonte`, `link`, `prob_positivo`, `prob_neutro`, `prob_negativo`, `origem`, `papel`, `tipo_conteudo` | Datas são **texto ISO com fuso de São Paulo** (converter e validar). `data_hora_publicacao` vazia nos documentos da CVM (`origem = cvm_ipe`, só com a data). **Ignorar `momento_pregao`** (usa 18h fixo); calcular a própria janela. `papel`/`tipo_conteudo`/`evento`/`qualidade` vêm de uma IA sem busca ("juíza"), ainda não avaliada; filtro desligado na coleta (entram panoramas e opiniões) |
| `v1-precos` | `data`, `ticker` | todas | `fechamento` = sem dividendos (ajustado só por desdobramento); `fechamento_ajustado` = com dividendos. Inclui `IBOV`, `USDBRL`, `BRENT`, `IVVB11`. Volume vazio nos não-ações. **O histórico inteiro é regravado a cada dia** (o ajustado do passado pode mudar) |
| `v1-cadastro` | `ticker` | todas | `tipo_acao`: ON, PN, UNIT ou BDR. Units: KLBN11, BPAC11, ENGI11, IGTI11, SANB11, TAEE11. CRFB3 sem CNPJ nem setor |
| `v1-mudancas_ticker` | `ticker_antigo` | todas | `data_mudanca` hoje vazia |
| `v1-balancos` | `cnpj`, `tipo_documento`, `data_inicio_periodo`, `data_fim_periodo` | todas | Consolidado, em reais. Trimestre e acumulado do ano em linhas separadas. `data_entrega` = da última versão do documento. **Desde 22/10/2026 todas as colunas vêm preenchidas** (~90%, como `lucro_bruto`): `ebit`, `depreciacao_amortizacao` (sempre positiva), `emprestimos_*`, `caixa`, `aplicacoes_financeiras`; vazias nos bancos e seguradoras. Zeros suspeitos em `emprestimos_*` e `aplicacoes_financeiras`: ver seção 10 |
| `v1-acoes_emitidas` | `cnpj`, `data_referencia` | todas | — |
| `v1-proventos` | `ticker`, `tipo`, `data_com` | todas | Valor já ajustado por desdobramento, bonificação e grupamento. Units já somadas pela composição |
| `v1-indices` | `data`, `indice` | todas | CDI em % ao dia; IPCA em % no mês; IDIV, SMLL, IFIX em pontos |

### 3.2 Tabelas auxiliares (podem ser lidas)
- `raw_articles` (`lang`, `published_precision`, `published_at` em **UTC**); ligação: `v1-noticias.id` = `"n"` + `raw_articles.id` com zeros à esquerda (6 dígitos ou mais).
- `staging_article_sentiment` (`model`, `text_source`): modelo do FinBERT usado (`lucas-leme/FinBERT-PT-BR` para português, `ProsusAI/finbert` para inglês) e texto lido (`body` ou `title`).
- `v1-staging_noticias_julgamento`: julgamentos da juíza por versão.
- `v1-raw_ipe_docs`: fatos relevantes e comunicados (data de entrega).
- `v1-raw_b3_proventos`, `v1-raw_b3_suplemento`: eventos em ações (para conferir ajustes).
- `v1-raw_b3_cadastro`: `other_codes` (JSON) = códigos de negociação **atuais** de cada empresa na B3. Define quais classes existem (seção 6, "Ação → empresa").
- `v1-painel_execucoes`, `v1-painel_etapas`: estado da coleta do dia (gatilho, seção 4).

### 3.3 Regras de formato do contrato
Ticker sem `.SA`; datas `AAAA-MM-DD`; ponto decimal; vazio = `NULL` (nunca 0); balanços em reais; CNPJ só números; USDBRL em R$/US$; BRENT em US$/barril; volume em quantidade de ações.

### 3.4 Lacunas da coleta e o que o código faz enquanto isso
| Lacuna | Comportamento do processamento |
|---|---|
| EBITDA e endividamento com insumo vazio (colunas preenchidas desde 22/10/2026, mas ~10% das linhas sem valor) | `status = indisponivel` no indicador que dependia do valor vazio |
| Histórico curto (~1 ano hoje; meta de 5 anos) | Implementar tudo. **Não treinar o modelo "para valer"** até o histórico completo chegar; com 1 ano, só teste de funcionamento (sem conclusões) |
| Composição histórica do Ibovespa | Ver 3.5 |
| `data_mudanca` vazia | Unir históricos pela `v1-mudancas_ticker` assim mesmo; quando a data vier, usá-la |
| Ações deslistadas sem preço nas fontes: CRFB3, SRNA3, STBP3 (decidido com a coleta em 22/10/2026) | Fora do universo **em todas as datas**. Lista em `processamento/config/exclusoes.yaml` (`tickers_excluidos`). Entra na limitação de **viés de sobrevivência** do TCC |
| Classes extintas nos proventos (ex.: VALE5, AXIA6, CPLE5) | Classe que **não aparece** no `other_codes` da empresa em `v1-raw_b3_cadastro` é **extinta hoje**, mas existiu: seus proventos são reais e **contam normalmente** no histórico de proventos e no payout, ligados à empresa pela raiz (seção 6). **Units (final 11) continuam de fora** do payout (regra da unit). "Extinta" é só informação. Decidido em 22/10/2026 pelos números do diagnóstico: AXIA5, AXIA6 e CPLE5 pagaram dentro do período analisado |
| Empresas sem balanço nas fontes: CNPJs 03847461000192 e 06057223000171 (decidido com a coleta em 22/10/2026) | A empresa continua no painel de preços e no modelo; P/L, P/VP, ROE, margens, EBITDA, endividamento e payout saem com `status = indisponivel`. Lista em `exclusoes.yaml` (`cnpjs_sem_balanco`) |
| Itens acima no diagnóstico (etapa 1) | Aparecem como **nota "excluídos por decisão"**, não como divergência |

### 3.5 Universo de ações por data
- **Tabela da composição:** `` `v1-composicao_ibov` `` (criada pela coleta em 23/10/2026; **hoje vazia**). Colunas reais `ticker`, `vigencia_inicio`, `vigencia_fim`, `participacao`, `fonte`, mapeadas no `fontes.yaml` para `ticker`, `data_inicio`, `data_fim`, `participacao`, `fonte` (`participacao` e `fonte` só informativas por enquanto). `vigencia_fim` vazia = ainda vigente.
- **Cobertura por data (decidido em 23/10/2026):** uma data está coberta se alguma linha tem `data_inicio ≤ data` e (`data_fim` vazio ou `≥ data`). Data coberta: só entram as ações com vigência naquela data (`universo = 'composicao_historica'`; as outras ficam `fora_da_composicao`). Data não coberta (inclusive tabela inexistente ou vazia): todas as ações do `v1-cadastro` (`tipo_acao` ON, PN ou UNIT), `universo = 'composicao_atual'`; ticker que só está na composição fica `fora_da_composicao` nessa data.
- **Aviso no `execucao`:** tabela vazia → "Composição do Ibovespa vazia: universo = composição atual (ações do cadastro)."; cobertura parcial → quantos pregões a composição cobre e o período coberto; cobertura total ou tabela inexistente → sem aviso (`universo.aviso_composicao`).
- **Conversores aceitos:** intervalos (formato pedido); "fotos" das carteiras (`data_carteira`, `ticker` → a ação entra na primeira carteira em que aparece e sai na primeira em que some); colunas de entrada e saída no cadastro.
- **Sempre (decidido em 22/10/2026):** ação **sem preço numa data** fica fora do universo **naquela data**; os `tickers_excluidos` de `exclusoes.yaml` ficam fora em **todas** as datas.
- O filtro vale para o **modelo** e para o **histórico do experimento**. O painel de fatos usa as ações atuais.

---

## 4. Rotina diária

1. A coleta roda **uma vez por dia, às 8h** (Brasília).
2. A partir das **8h**, a cada **~5 minutos**, o processamento consulta:
   - em `v1-painel_execucoes`: o daily mais recente de hoje (`tipo = 'daily'`), com `iniciada_em` **no próprio dia e a partir das 08:00 de São Paulo**. **`iniciada_em` está em UTC**: converter para São Paulo antes de comparar data e hora. Vale **`origem` `cron` ou `manual`**; daily manual vira **nota** no pacote `execucao`. Execuções de outros tipos (ex.: `coletar`, com as etapas `cvm_itr_dfp`, `build_entrega` e `corrigir_horas`) não servem de gatilho. `origem = 'cron'` só é usada na conferência do horário no diagnóstico (decidido em 22/10/2026);
   - em `v1-painel_etapas` (por `execucao_id`): esperar **`etapa_id = 'entrega'` com `status = 'concluida'`**. **Não esperar o daily inteiro** (a etapa seguinte, `analise`, não interessa e, se falhar, deixa o daily `parcial`);
   - conferir se `precos`, `noticias` e `enriquecimento` também estão `concluida`. Se não: seguir, mas com aviso.
3. Com a entrega pronta: calcular a Fase 1, fechar o resultado do top 5 do pregão anterior, gerar o top 5 de hoje e enviar os pacotes (ordem na seção 8.5).
4. **Prazo: 9h45.** Se a entrega não terminou, gerar com os dados disponíveis e marcar com aviso.
5. O top 5 é gravado com `gerado_em`. **Se gerado depois das 10h, `valido_para_historico = false`.**

Etapas da coleta, em ordem: `precos`, `macro`, `noticias`, `ipe`, `enriquecimento`, `juiza`, `cadastro`, `entrega`, `analise`. Status de etapa: `pendente`, `em_andamento`, `concluida`, `falhou`, `pulada`.

---

## 5. Fase 1: indicadores do painel

Fonte dos dados: tabelas da seção 3. `fech` = `fechamento`; `aj` = `fechamento_ajustado`. Comparações com o setor usam a **mediana por empresa das outras empresas do mesmo setor** (decidido em 23/10/2026: a média era distorcida por um valor extremo, ex.: P/L 180 da BRAV3 levava o P/L do setor de petróleo a 43, contra mediana 12; a variável `ret_vs_setor` do modelo continua com a média, seção 7.3) (sem a própria empresa: tiram-se todas as ações do mesmo CNPJ, ex.: PETR3 não entra no setor da PETR4); se o setor tem menos de 3 empresas (CNPJs distintos, contando a própria), `setor_comparacao_fraca = true`. Só ON, PN e UNIT entram nos pares (setor e `posicao_pct`); BDR aparece no painel, mas fica fora dos pares (`posicao_pct = nao_se_aplica`). Janelas "1 dia, 1 mês, 6 meses, 1 ano" = **1, 21, 126 e 252 pregões** (decisões de 22/10/2026; detalhes na seção 9, etapa 3).

| Indicador | Cálculo | Observações / status |
|---|---|---|
| Cotação | `fech` do dia; variação = `fech(t)/fech(t−1) − 1` | — |
| Variação do preço | Mesmo cálculo com `fech` em 1 dia, 1 mês, 6 meses, 1 ano | Sem dividendos |
| Rentabilidade | `aj(t)/aj(t−n) − 1` em 1 dia, 1 mês, 6 meses, 1 ano; idem para IBOV e setor | Com dividendos |
| Comparação com Ibovespa | Rentabilidade da ação × do IBOV, mesmas janelas | Gráfico: séries rebaseadas pela interface |
| Comparação com o setor | Rentabilidade da ação × média do setor (sem a própria empresa), mesmas janelas | Na série do gráfico, o setor inclui todas as ações (diferença aceita) |
| Comparação com índices | Ação × CDI, IPCA, IDIV, SMLL, IFIX, IVVB11. **CDI e IPCA acumulados** (juros sobre juros) | IPCA é mensal |
| Volume total | `volume` do dia | — |
| Volume em relação ao normal | `volume(t) / mediana(volume das 20 sessões anteriores, sem t)` | `historico_insuficiente` com menos de 20 |
| Volatilidade | Desvio-padrão dos 20 últimos retornos diários de `aj` | `posicao_pct` = fração das ações do dia mais calmas que ela |
| Beta | Inclinação da regressão dos retornos diários da ação sobre os do IBOV, 252 pregões | Usa até 252 pregões; calcula a partir de **120**. Abaixo de 120: `historico_insuficiente` |
| Tom das notícias do dia | Contagem por rótulo (maior das 3 probabilidades) e tom médio `prob_positivo − prob_negativo` | Manchetes ordenadas por `destaque` (seção 8) |
| P/L | Valor de mercado ÷ lucro líquido 12m. Valor de mercado = Σ (preço de cada classe × quantidade) ou preço × (ON+PN) quando só uma classe é negociada | Lucro 12m ≤ 0: mostrar **o número e o aviso** (ex.: "P/L −5,2 · Empresa com prejuízo nos últimos 12 meses"), com `status = lucro_negativo`. Essa empresa **não entra na média do setor** |
| P/VP | Valor de mercado ÷ patrimônio líquido do balanço mais recente | — |
| ROE | Lucro líquido 12m ÷ patrimônio líquido mais recente | — |
| Margem bruta | Lucro bruto 12m ÷ receita líquida 12m | `nao_se_aplica` em bancos e seguradoras |
| Margem líquida | Lucro líquido 12m ÷ receita líquida 12m | `nao_se_aplica` em bancos e seguradoras |
| EBITDA | EBIT 12m + depreciação e amortização 12m; margem = EBITDA ÷ receita 12m | `nao_se_aplica` em bancos/seguradoras; `indisponivel` se faltar EBIT ou D&A. Rótulo: "EBITDA (cálculo padrão CVM)" |
| Endividamento | Dívida líquida = empréstimos CP + LP − caixa − aplicações; DL/PL; DL/EBITDA 12m | Sem arrendamentos (avisar). DL < 0 → `caixa_liquido = true`. `nao_se_aplica`/`indisponivel` como o EBITDA |
| Dividend yield | Σ proventos com `data_com` nos últimos 12 meses ÷ `fech` atual | — |
| Payout | Σ proventos pagos em 12 meses (valor × quantidade de ações da classe) ÷ lucro líquido 12m; também por ano | Somar só ON e PN, **nunca a unit** |
| Histórico de dividendos | Lista de proventos e soma por ano | 5 anos |

---

## 6. Regras de cálculo transversais

| Tema | Regra |
|---|---|
| Ação → empresa | Ligar pelo `cnpj` do `v1-cadastro`. Notícia da empresa vale para todas as suas ações (PETR3 e PETR4). **Classes fora do `v1-cadastro`** (ex.: ITUB3 nos proventos): aplicar antes a `v1-mudancas_ticker` e ligar pelas **4 primeiras letras** (raiz) à empresa do cadastro. Isso vale também para classes **extintas** (fora do `other_codes` da empresa em `v1-raw_b3_cadastro`): os proventos delas contam no histórico e no payout (seção 3.4). Classes 3 = ON; 4, 5 e 6 (PN, PNA, PNB) = **PN**; 11 = unit (decidido em 22/10/2026) |
| Units | Indicadores por ação da unit = indicador por ação × (`unit_qtd_on` + `unit_qtd_pn`) |
| Trimestre isolado | ITR traz o trimestre e o acumulado; usar a linha cujo período tem ~3 meses. **4º trimestre = DFP (ano) − acumulado de 9 meses do 3º ITR.** Depreciação (quando vier) pode estar só acumulada: calcular pela diferença |
| 12 meses | Soma dos 4 últimos trimestres isolados |
| Point-in-time | Em cada data, usar só balanços com `data_entrega ≤ data` |
| Bancos e seguradoras | Identificar pelo setor do cadastro |
| Calendário | Pregões = datas com preço do `IBOV` em `v1-precos` |
| Mudança de ticker | Unir os históricos pela `v1-mudancas_ticker` antes de qualquer cálculo |
| Empréstimos zerados | `emprestimos_curto_prazo = 0` **e** `emprestimos_longo_prazo = 0` na mesma linha = ausente (conta não achada pela coleta): dívida líquida, DL/PL, DL/EBITDA e `caixa_liquido` saem `indisponivel`. Só um dos dois = 0 continua valendo; `aplicacoes_financeiras = 0` continua valendo (decidido em 22/10/2026; pedido à coleta na seção 10) |
| Quantidade de ações suspeita | Em cada data, se o P/VP calculado (valor de mercado ÷ patrimônio líquido > 0) for **< 0,05** (`fundamentos.pvp_minimo_plausivel`), a quantidade de `v1-acoes_emitidas` daquela empresa é suspeita (gravada em milhares em ~25 empresas): valor de mercado, P/L, P/VP e payout (inclusive `payout_por_ano` e `payout_12m`, pela situação em t) saem `indisponivel` e ficam fora das comparações com o setor. **Não multiplicar por 1000.** ROE, margens, EBITDA, endividamento e yield não mudam. O diagnóstico lista as empresas suspeitas (decidido em 23/10/2026; pedido à coleta na seção 10) |
| Abertura ajustada | `abertura × aj / fech` do mesmo dia (para o salto da abertura não confundir dividendo com queda) |
| Checagem diária | Avisar: poucas ações no dia, retorno acima de 30% em módulo, volume zero, preço parado, indicador vazio |

---

## 7. Fase 2: o experimento

### 7.1 Alvo
- **Principal:** `alvo = 1` se `aj(t+1)/aj(t) − 1 > IBOV(t+1)/IBOV(t) − 1`; senão 0. Calculado por nós. Última data sem alvo não entra no treino.
- **Complementar:** salto da abertura de t+1 (abertura ajustada t+1 ÷ `aj(t)` − 1) maior que o do IBOV.

### 7.2 Janelas de notícias (horário de São Paulo)
- **Noite:** `data_hora_publicacao` **depois do fechamento da B3 no pregão t** e **até as 8h do pregão t+1** (inclui fins de semana e feriados: sexta à noite até segunda 8h). O horário de fechamento da B3 varia ao longo do ano: guardar em `config/parametros.yaml` e conferir os horários oficiais.
- **Pregão:** entre a abertura e o fechamento de t.
- **Sem horário:** notícias sem `data_hora_publicacao` (ex.: documentos da CVM) valem como publicadas às **23:59:59 da sua data** e entram na **noite** do pregão daquela data (fim de semana/feriado → noite do último pregão antes). É o horário mais tarde possível, então nunca adianta informação (E3, etapa 5). No painel (`noticias_dia`) continuam marcadas `sem_horario`.
- **Meia-noite do Pacífico = só data (decidido em 23/10/2026, N1-A):** ~91% das notícias do Google News chegam com `data_hora_publicacao` exatamente às 04:00:00 (horário de verão dos EUA) ou 05:00:00 (inverno) de São Paulo, ou seja, 00:00:00 em `America/Los_Angeles`: a fonte só deu a data. Usar esse horário jogaria a notícia do dia D na noite de D−1 (**vazamento**). Regra, aplicada na camada de leitura (`fontes.aplicar_regra_so_data`, vale para `v1-noticias` e `raw_articles`): instante que é 00:00:00 em Los Angeles → `precisao_hora = meia_noite_pacifico`, data = data em Los Angeles, sem hora, e segue a regra "sem horário" acima (23:59:59 da data → noite do pregão daquela data). 04:00:00 no inverno dos EUA (= 23:00 em LA) e qualquer outro horário (ex.: 04:00:01, 10:30) continuam com a hora real. Consequência: para essas notícias não há como separar pregão de noite; a janela efetiva delas é o dia t inteiro mais a noite, até 08:00 de t+1.
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
| `mudanca_tom` | Tom da janela − tom médio da empresa nos 30 pregões anteriores | Essencial |
| `tom_setor` | Tom médio das notícias das outras empresas do setor (mesma janela) | Complementar |
| `tom_mercado` | Tom médio de todas as notícias da janela | Complementar |

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

**Alvo:** `alvo` (7.1).

- Variáveis de preço, volume e mercado entram como **rank** dentro do pregão: `(posição média − 1) ÷ (n − 1)`, menor = 0, maior = 1, empates pela média, um único valor = 0,5, vazio continua vazio (E6, etapa 5). As 6 variáveis de notícias ficam **brutas** (E5); `tom_mercado` é igual para todas as ações do dia e também fica bruta.
- Filtro do universo **do modelo** por data (3.5: sem BDR, sem `tickers_excluidos`, sem ação sem preço no dia) antes de calcular os ranks; o rank usa **todas** as linhas do pregão, antes de descartar as linhas sem alvo.
- Detalhes das colunas (etapa 5): notícia da empresa vale para todas as suas ações (mesmo `id` conta 1 vez por empresa); `score = prob_positivo − prob_negativo`; `noticias_dia_extremo` = score de maior módulo, com sinal (empate de módulo = média dos empatados); `ret_1d/5d/20d` com base "as-of" (igual à rentabilidade do painel); `salto_abertura` exige o pregão anterior (E13); `dist_max_52s`/`dist_min_52s` com 252 pregões incluindo t, mínimo 120; `exposicao_*` = beta de 120 pregões (mínimo 60 pares) × variação do fator em t (E12); `ret_vs_setor` exclui a **empresa** inteira (E14, regra D10). Colunas de identificação: `data`, `ticker`, `empresa`, `setor`, `universo`, `dia_resultado`. Alvos guardados: `alvo`, `alvo_abertura`, `ret_t1`, `ret_ibov_t1`.

### 7.4 Modelos (definidos antes de rodar)
| Modelo | Variáveis | Responde |
|---|---|---|
| 1. Base | Preço, volume e mercado | Quanto o preço sozinho explica |
| 3. + notícias | 1 + `noticias_dia_qtd`, `noticias_dia_tom`, `noticias_dia_extremo` + `mudanca_tom` | **Hipótese principal:** as notícias **do dia t e da noite, até 08:00 de t+1**, ajudam a prever se a ação supera o Ibovespa em t+1? |

O **modelo 2** (+ notícias do pregão) **saiu** em 23/10/2026 (N2-A): com ~89% das notícias só com data, não há como separar pregão de noite (seção 7.2). A numeração 1/3/3b foi mantida para não confundir com o histórico.
| 3b. Dias de resultado | Modelo 3 só nos dias com balanço divulgado na janela | O efeito é maior em dia de balanço? |

**Notícias usadas pelo modelo (decidido em 21/10/2026):**
- **Versão principal: todas as notícias** de `v1-noticias` (sem filtro).
- **Teste extra: só as principais.** Recalcular as variáveis de notícias usando só as linhas com `origem = 'cvm_ipe'` **ou** (`tipo_conteudo = 'reportagem'` **e** `papel` em `protagonista` ou `citada_com_fato`). Notícias sem julgamento da juíza (`papel` vazio) ficam fora dessa versão; **contar quantas são e informar no relatório**. Comparar as duas versões com a mesma validação (seção 7.5). Se a filtrada for melhor, é um achado do TCC.
- O filtro é feito **no processamento**; a coleta mantém o filtro dela desligado (`ENTREGA_FILTRO_JUIZA=false`).

Ordem: primeiro só as **essenciais**; depois os **complementares**, um bloco por vez, mantendo só o que melhora na validação.
XGBoost, ponto de partida: `n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5`. Grade pequena escolhida pela validação.

### 7.5 Avaliação
- **Walk-forward mensal** (treina no passado, testa no mês seguinte, avança), com **embargo de 1 pregão**.
- **Conjunto de teste final** separado e usado **uma única vez** (decidido em 23/10/2026, F1/F2): de **23/06/2026** até a **véspera da entrada da rotina diária em produção** (data fixada na etapa 8). Fica em `parametros.yaml`, `treino.teste_final.inicio` e `treino.teste_final.fim`; **`fim` vazio = trava ativa** (o teste final não roda). Enquanto isso, o treino usa só o período de desenvolvimento (antes de 23/06/2026, menos o pregão de embargo).
- **Borda do `fim` (decidido em 23/10/2026):** o teste final avalia só as linhas cujo **dia do alvo (t+1) é ≤ `fim`**. A linha do próprio `fim` (o alvo dela é o primeiro pregão em produção) pertence ao **teste ao vivo**: é a primeira previsão ao vivo. Se o `fim` não for pregão, sai também o último pregão antes dele cujo t+1 passa do `fim`. Assim nenhum dia de alvo é contado nos dois testes (`validacao.linhas_com_alvo_ate`).
- **Teste ao vivo:** as previsões **a partir da linha do `fim`** formam um **segundo teste, independente**: o histórico do top 5 gravado no momento da geração (7.6 e 7.7), sem nenhuma escolha feita olhando esse período.
- **Corte principal: top 5** (o que vai para a tela). Avaliar também o **top 3** com as mesmas métricas, para mostrar que o resultado não depende do corte.
- Métricas: acerto do top 5 × **faixa do acaso** (10 mil sorteios aleatórios de 5 ações por dia, faixa de 95%); retorno médio do top 5 − IBOV; **top 5 × últimos 5**; AUC geral e AUC médio por pregão; IC por bootstrap em blocos de pregão; **robustez por ano**; se o universo for o atual, **análise de sensibilidade** (último ano × anteriores).
- **Teste extra "notícia depois do fechamento" (pedido em 23/10/2026; implementar na etapa 6):** recalcular as variáveis de notícias usando **só as notícias com hora real** (`precisao_hora = 'hora'`) e **só a noite** (do fechamento de t até 08:00 de t+1; `inicio_janela = "fechamento"`), e comparar com o modelo 3 na mesma validação. Mede o efeito das notícias publicadas depois do fechamento. Amostra pequena (~9% das notícias têm hora real, ~47% delas na noite): informar as contagens e tratar como exploratório.
- **Referências de comparação** (rodadas com a mesma validação): escolha ao acaso (faixa acima), regra simples só com a volatilidade (ações mais calmas primeiro) e **regressão logística** com as mesmas variáveis. O XGBoost só "ganha" se superar as três.
- Diferença dentro da faixa do acaso = "ainda não mostrou vantagem sobre o acaso".

### 7.6 Previsão diária (top 5)
- Ordenar as ações do dia pela probabilidade do modelo e pegar as 5 primeiras. Na tela: **"5 ações com maior chance de superar o Ibovespa (experimento)"**.
- **Motivos:** contribuições do XGBoost (`pred_contribs`), traduzidas em frases ("Notícias da noite com tom positivo (3 notícias)"), com efeito `ajudou`/`atrapalhou`/`neutro`.
- **Chance:** calculada, mas `exibir = false` até a calibração ser conferida (se o modelo diz 60%, ~60% acontecem). Quando exibida, vem ao lado da referência do acaso, 50% (`chance.referencia_acaso`); com a chance escondida, a referência também vai `null`, para a interface não mostrar "50%" por engano.
- Gravar o top 5 do dia no momento da geração (histórico nunca recalculado depois).
- No dia seguinte, fechar o resultado: `superou` = retorno da ação > retorno do IBOV no pregão previsto.

### 7.7 Modelo em uso no dia a dia
- **Qual modelo gera o top 5:** o **modelo 3** (com as notícias do dia e da noite, até 08:00 de t+1), porque é ele que testa a hipótese do TCC. Ele é mostrado mesmo que não supere o acaso: o selo "em avaliação" e o histórico existem para isso.
- **Comparação ao vivo:** todo dia, gravar também (sem mostrar na tela) o top 5 do **modelo 1** (sem notícias) e o da **regra da volatilidade**. Assim, o histórico mostra, com dados de verdade e daqui para frente, se as notícias fazem diferença.
- **Retreino mensal:** no primeiro dia útil de cada mês, treinar de novo com todo o histórico até o fim do mês anterior (o mesmo esquema do walk-forward). Os hiperparâmetros só mudam numa nova avaliação completa, nunca no retreino automático.
- **Arquivo do modelo:** salvar em `modelos/xgb-AAAA-MM.json`, com um arquivo de metadados ao lado: variáveis usadas, período de treino, hiperparâmetros, métricas da validação, universo (`composicao_atual` ou histórica) e um hash do dataset. O `modelo_versao` do pacote `experimento_top` aponta para esse arquivo (nome sem o dia, como no exemplo da 8.3). O modelo 1, usado no top 5 sombra, vai em `modelos/xgb-m1-AAAA-MM.json` (F17).
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
| Envio "quando muda" | `acoes`, `fundamentos_trimestrais`, `proventos` e `series_diarias` comparam com o estado do último envio (`saida/estado/`): só vai o novo ou alterado; o que sumiu vai em `removidos`; série com ponto antigo alterado vai inteira com `substituir_serie: true` |

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

**2. `mercado_dia`:** cada número é uma folha `{valor, status}` (8.1). `data_referencia` (t); `IBOV`, `USDBRL`, `BRENT`: `{fechamento, variacao_dia, unidade}`; `cdi_dia` (fração ao dia) e `cdi_data`; `ipca_12m`; `ipca_ate` (último mês de IPCA usado, `AAAA-MM`); `indices`: `{CDI, IPCA, IDIV, SMLL, IFIX, IVVB11}` × `{d1, m1, m6, a1}` (o % de cada índice por período, igual para todas as ações).

**3. `resumo_acao`** (um objeto por indicador, sempre com `valor`, `status` e, quando faz sentido, `setor`, `posicao_pct` e `texto`):
- `cotacao`: `fechamento`, `variacao_dia`
- `variacao_preco`: `d1`, `m1`, `m6`, `a1` (sem dividendos)
- `rentabilidade`: `d1`, `m1`, `m6`, `a1` (com dividendos) + as mesmas janelas do `IBOV` e do setor (`ibov`, `setor`), para a comparação lado a lado com seletor de 1 dia, 1 mês, 6 meses e 1 ano
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

**4. `series_diarias`** (formato compacto, só neste pacote): um registro por série com `ticker`, `tipo` (`acao`, `etf`, `indice`, `taxa`, `setor`), `nome`, `substituir_serie`, `inicio_janela`, `datas` (lista crescente, sem repetir), `valores` (uma lista por campo, do mesmo tamanho de `datas`, número ou `null`) e `status` (por campo, só para os pontos que não são `ok`, em trechos `{de, ate, status}` contíguos e sem sobreposição; `null` ⇔ coberto por um trecho; valor coberto por trecho só com `lucro_negativo`). Campos por tipo: ação: `fechamento`, `indice_retorno_total` (com dividendos), `volume`, `pl`, `pvp`, `dividend_yield` (point-in-time, mesmas regras e status do `resumo_acao`); `IVVB11`: fechamento, índice, volume; `IBOV`, `IDIV`, `SMLL`, `IFIX`: fechamento (pontos) e índice; `CDI`, `IPCA`: índice base 100 acumulado (CDI: taxas com data < d; IPCA: meses fechados até K(d)); `SETOR:<nome>`: índice e `n_empresas` (sem status). Números sem arredondar. **Janela:** só os últimos 253 pregões até t (`inicio_janela` = o 1º deles); a API apaga os pontos da série com data anterior a `inicio_janela`, e o ponto que sai pelo corte não conta como mudança. **Base 100 com âncora fixa** no 1º dia da série no histórico inteiro (o 1º valor enviado em geral não é 100); o pacote não rebaseia no início da janela, porque isso mudaria todos os pontos todo dia (reenvio inteiro diário) e exigiria três versões (1m, 6m, 1a). **Setor:** média igual por empresa dos retornos diários das ações ON, PN e UNIT do setor (BDR fora), **incluindo a própria**, com preço no dia e no pregão anterior, encadeada em base 100; dia sem nenhuma: ponto vazio (`indisponivel`) e a cadeia segue do último valor. A divisão de dois pontos dá a rentabilidade da janela do `resumo_acao`/`mercado_dia`. **A interface recorta o período e parte do mesmo ponto dividindo pelo primeiro valor do recorte.** Reenvio da série inteira (`substituir_serie: true`) quando algum ponto antigo dentro da janela muda (desdobramento, bonificação, reapresentação de balanço, histórico estendido); dividendo não muda o índice dos dias anteriores à data-ex. Envio diário: o mesmo formato só com as datas novas.

**5. `fundamentos_trimestrais`:** `ticker`, `data_fim_periodo`, `data_entrega`, `receita_trimestre`, `receita_12m`, `lucro_liquido_trimestre`, `lucro_liquido_12m`, `margem_bruta`, `margem_liquida`, `roe`, `ebitda_trimestre` (para o gráfico de barras por trimestre), `ebitda_12m`, `margem_ebitda`, `divida_liquida`, `dl_pl`, `dl_ebitda`, `payout_12m`, cada um com `status`. Margens, ROE e payout são sempre de 12 meses. Só os 8 trimestres mais recentes de cada ação (os mais antigos saem em `removidos`).

**6. `proventos`:** `ticker`, `tipo` (DIVIDENDO, JCP), `data_com`, `data_pagamento`, `valor_por_acao`. A soma por ano a interface faz (ou vem pronta em `resumo_acao`). Só os proventos com data-com no ano de t ou nos 4 anteriores.

**7. `noticias_dia`:** `data_referencia` (t), `ticker`, `janela_inicio`/`janela_fim` (08:00:01 de t até 08:00 de D, a mesma janela do modelo), `resumo` (`quantidade`, `positivas`, `neutras`, `negativas`, `tom_medio`, em folhas) e `itens` (`id`, `titulo`, `fonte`, `link`, `publicado_em`, `data_publicacao`, `precisao_hora`, `rotulo`, `prob_*`, `janela` = `pregao` (inclui a pré-abertura de t) / `noite` / `sem_horario` (sem hora real, inclusive "só data"), `destaque`, `status`). Rótulo: maior das 3 probabilidades; empate com o neutro, ou positivo = negativo, vira neutro. Destaque: protagonista primeiro, depois |positivo − negativo| e depois a mais recente. Sem notícia: quantidade 0 e `tom_medio` `nao_se_aplica`; antes do início da cobertura: tudo `indisponivel`.

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

**10. `execucao`:** `data_referencia` (D), `rodada`, `inicio`, `fim`, `status` (`em_andamento`, `ok`, `parcial`, `falhou`), `coleta_status` (o que se leu do painel da coleta; vazio até a etapa 8), `pacotes_enviados` (`pacote`, `arquivo`, `registros`, `removidos`), `avisos`.

### 8.4 Cobertura da planilha (conferida item a item)
Todas as 23 informações da planilha (`docs/planilha_final.xlsx`; cálculos na seção 5) têm origem num pacote: Top 5 e detalhes → `experimento_top` (+ `resumo_acao` e `noticias_dia`); Histórico do experimento → `experimento_historico`; Volume total, volume relativo, volatilidade, beta, cotação, variação do preço, rentabilidade, P/L, P/VP, ROE, yield, payout, margens, EBITDA e endividamento (valor atual) → `resumo_acao`; comparação com Ibovespa, setor e índices, gráficos de preço, rentabilidade e volume → `series_diarias` (+ `resumo_acao` para os % de cada período); gráficos trimestrais de margens, ROE, EBITDA e endividamento → `fundamentos_trimestrais`; gráfico do payout por ano → `resumo_acao.payout_por_ano`; dividend yield (barras) e histórico de dividendos → `proventos`; tom das notícias → `noticias_dia`. Comparação com índices: o % de cada índice por período vem em `mercado_dia.indices` (igual para todas as ações). P/L, P/VP e yield ao longo do tempo: `series_diarias` (pontos das ações). Linha do acerto acumulado do experimento: `experimento_historico.dia.taxa_acumulada`. As séries trazem 1 ano (253 pregões: 252 variações, para o gráfico de 1 ano bater com a `rentabilidade.a1`), os trimestres 8 e os proventos 5 anos.

### 8.5 Ordem diária de envio
1. `execucao` (início) → 2. `acoes` (se mudou) → 3. `series_diarias` → 4. `mercado_dia` → 5. `resumo_acao` → 6. `fundamentos_trimestrais` e `proventos` (se mudaram) → 7. `noticias_dia` → 8. `experimento_historico` (fecha o dia anterior) → 9. `experimento_top` (antes das 10h) → 10. `execucao` (fim).

Nomes dos arquivos: `execucao.json`, `acoes.json`, `series_diarias.json`, `mercado_dia.json`, `resumo_acao.json`, `fundamentos_trimestrais.json`, `proventos.json`, `noticias_dia.json`, `experimento_historico.json`, `experimento_top.json` (o `execucao.json` é regravado no fim da rodada). Cada pacote é validado antes de gravar; reprovado, não é gravado e a rodada fica `parcial`.

### 8.6 O que fica para a equipe da API e do banco decidir
- Autenticação, endereço e se o envio é um pacote por chamada ou em lote.
- Como o banco da interface guarda cada pacote (pode ser uma tabela por pacote, com a mesma chave).
- O processamento só garante: **mesmo formato, mesma chave e reenvio seguro (upsert)**.

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
- **IPCA:** só meses fechados, sem rateio por dia. Na data d valem os meses anteriores ao mês de d; o acumulado da janela é o produto dos meses entre o último mês conhecido na base e o último conhecido em t. Ao vivo, nos primeiros ~10 dias do mês o IPCA fica defasado: por isso a saída informa `ipca_ate`.
- **CDI:** entram as taxas com data em [base, t) (a taxa do dia d rende de d a d+1); a taxa de t não entra. `cdi_dia` = taxa da última data ≤ t.
- **Lacunas de preço:** rentabilidade e variação usam a base "as-of" (último preço até t−n). Volatilidade e volume relativo exigem os 20 pregões completos; senão `historico_insuficiente`. Beta conta só pares de retornos válidos, mínimo 120.
- **Volatilidade:** desvio-padrão amostral (ddof = 1), diário, sem anualizar.
- **`posicao_pct`:** do volume, calculada sobre o volume **relativo**. Fórmula: nº de pares estritamente menores ÷ (nº de pares válidos − 1); menor = 0, maior = 1; menos de 2 válidos: `indisponivel`.
- **Comparação com índices:** janelas d1, m1, m6 e a1.
- Enquanto a coleta não completar os índices (seção 10), as janelas sem dados saem `historico_insuficiente`/`indisponivel`. Isso está correto, não é bug.

**Decisões da etapa 4 (22/10/2026)**
- **Janela do payout (D1):** proventos com `data_com` em (t − 12 meses, t], igual ao yield (`data_pagamento` está 95,6% vazia). Parâmetros no `parametros.yaml`, bloco `fundamentos`.
- **Duas classes PN (D2):** média das classes PN que pagaram no evento × `qtd_pn` (limitação na seção 10).
- **Ações da época (D3):** cada provento usa a linha de `v1-acoes_emitidas` com a maior `data_referencia` ≤ `data_com`; sem ela, a mais antiga disponível.
- **Point-in-time das ações (D4):** uma linha de `v1-acoes_emitidas` só vale em t se o balanço do mesmo CNPJ com `data_fim_periodo` = `data_referencia` já foi entregue (`data_entrega` ≤ t).
- **Bancos e seguradoras (D5):** pelo **subsetor** do cadastro ("Intermediários Financeiros" e "Previdência e Seguros"), não pelo setor. Margens, EBITDA e endividamento: `nao_se_aplica`.
- **Patrimônio ≤ 0 (D6):** P/VP, ROE e DL/PL saem `nao_se_aplica`.
- **Lucro 12m = 0 e payout com prejuízo (D7):** P/L com lucro zero: sem valor, `lucro_negativo`. Payout com lucro ≤ 0: sem valor, `lucro_negativo`.
- **Sem provento na janela (D8):** yield e payout = 0,0 com `ok` (não pagar é um fato, não ausência de dado).
- **BDR (D9):** P/L, P/VP, yield e payout `indisponivel` (a coleta não traz proventos de BDR e a razão BDR/ação é desconhecida); ROE, margens, EBITDA e endividamento calculados se houver balanço.
- **Média do setor por empresa (D10, vale para as etapas 3 e 4):** exclui todas as ações do mesmo CNPJ e conta cada CNPJ uma vez (primeiro a média das ações da empresa com valor, depois a média entre empresas). Ticker sem CNPJ conta como empresa própria. A média só usa valores com status `ok`: no P/L, empresa com `lucro_negativo` não entra. **Atualizado em 23/10/2026:** no painel, a agregação entre empresas passou a ser a **mediana** (`media_setor(..., agregacao="mediana")`); a `ret_vs_setor` do modelo segue com a média.
- **Balanço de referência (D11):** o documento mais recente entregue até t. Os 12 meses exigem os 4 trimestres que terminam nele; senão `historico_insuficiente`.
- **Valor de mercado (D12):** "só uma classe negociada" = só uma classe no cadastro. Classe do cadastro sem preço no dia: `indisponivel`.
- **Proventos e mudança de ticker:** a `v1-mudancas_ticker` serve só para achar a empresa (CNPJ); a classe (ON/PN) sai do final do ticker **original** do provento. O yield (e a soma por ano e a lista do ticker) só usa proventos do ticker atual e de tickers antigos da **mesma classe** (ex.: ELET3 → AXIA3); em conversão de classe (ex.: CPLE6 PN → CPLE3 ON), o provento antigo fica fora do yield. O payout usa todas as classes ON e PN da empresa. Linha antiga da mesma classe que colide com uma do ticker atual (mesmo tipo e `data_com`) é descartada.
- **Payout por ano:** usa o lucro líquido da própria DFP do exercício.
- **Lista de proventos:** mostra o ticker atual.

**Decisões da etapa 5 (22/10/2026)**
- **E1 Horário:** vale `v1-noticias`; `raw_articles` só confere.
- **E2 Pré-abertura:** 08:00:01 até a abertura → pregão do mesmo dia (no painel). No modelo, desde N2-A, pré-abertura, pregão e noite formam uma janela só (seção 7.2).
- **E3 Sem horário:** 23:59:59 da data → noite do pregão daquela data (seção 7.2).
- **E4 Janela sem notícia:** `noticias_dia_qtd = 0`, tom/extremo vazios. Antes do início da cobertura de notícias (menor data de publicação no banco), todas as colunas de notícia ficam vazias, inclusive a quantidade.
- **E5 / E6 Ranks:** notícias brutas; preço, volume e mercado em rank `(pos − 1)/(n − 1)`, só entre as ações do universo do modelo no pregão, antes de descartar as linhas sem alvo.
- **E7 `mudanca_tom`:** base = todas as notícias da empresa (noite, pregão, pré-abertura) com pregão de referência nos 30 pregões anteriores a t (sem t); mínimo de 5 notícias com score.
- **E8 `tom_setor`:** média, entre as outras empresas do setor (sem o próprio CNPJ) presentes no universo do dia, do tom da janela (`noticias_dia_tom`) de cada empresa; cada empresa 1 voto.
- **E9 `tom_mercado`:** média dos scores da janela das empresas do universo do dia, cada `id` uma vez.
- **E10 Repetidas:** mesma empresa, mesma data de publicação e mesmo título normalizado contam uma vez (a mais cedo); documentos `cvm_ipe` não são deduplicados.
- **E11 Dias de resultado (modelo 3b):** `v1-balancos.data_entrega`, com a regra das 23:59:59 → `dia_resultado = true` no pregão cuja noite contém a entrega. Limitações: balanço reapresentado fica com a data da última versão; divulgação antes da abertura cai um pregão depois.
- **E12 Histórico mínimo:** retornos exigem o preço base; volatilidade e volume relativo 20 pregões completos; beta 252/120; exposições 120/60; 52 semanas 252/120; `mudanca_tom` 30 pregões.
- **E13** `ret_1d` usa o último preço disponível; `salto_abertura` exige o pregão anterior.
- **E14** `ret_vs_setor` exclui a empresa inteira (D10).
- **E15 Saída:** CSV + JSON (contagens, sha256, parâmetros) em `saida/experimento/` (fora do git).
- **E16 Última linha:** fica no dataset sem alvo (é a linha da previsão ao vivo); o treino a descarta. As variáveis da noite dela exigem a data do próximo pregão (informada pela rotina); sem ela, ficam vazias.
- **N1-A Meia-noite do Pacífico (23/10/2026):** notícias com 00:00:00 em Los Angeles (04:00/05:00 de SP; ~89% das notícias) viram "só data" na camada de leitura (`fontes.aplicar_regra_so_data`, coluna `precisao_hora`), em `v1-noticias` e `raw_articles`. `raw_articles.published_precision` não ajuda: marca `date` só nos documentos da CVM (as 131.616 de meia-noite vêm como `datetime`). Pedido de horário real à coleta na seção 10.
- **N2-A Janela única (23/10/2026):** colunas `noticias_dia_*` na janela 08:00:01 de t → 08:00 do próximo pregão; `noticias_pregao_tom` e o modelo 2 saem; `experimento.inicio_janela` no `parametros.yaml`.
- **Horários da B3 antes de 03/2024:** ainda não cadastrados; com o histórico de 5 anos o código para com aviso, e os horários de 2021–2024 serão cadastrados quando o histórico chegar.

**Decisões da etapa 6 (23/10/2026; plano completo, com os casos de teste, em `docs/plano_etapa6.md`)**
Com ~1 ano de histórico, a etapa 6 é **só teste de funcionamento** (3.4): o relatório gerado abre com o aviso "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO", e nenhum número dele vale como conclusão.
- **F1 Teste final:** de 23/06/2026 (período nunca olhado; jan–jun/2026 já foram vistos na avaliação da v1) até a véspera da entrada em produção (etapa 8), em `treino.teste_final.inicio`/`fim`. `fim` vazio = trava ativa. Entram só as linhas com dia do alvo (t+1) ≤ `fim`; a linha do `fim` em diante é o teste ao vivo (7.5).
- **F2 Trava:** o teste final só roda com `fim` preenchido, `treino.teste_final.liberado: true`, a opção `--teste-final` **e** sem o registro `docs/teste_final_usado.json` (criado no uso; uso único). No modo desenvolvimento, as linhas a partir de `inicio` e o pregão de embargo antes dele saem logo na leitura; no modo teste final, as linhas depois do `fim` também.
- **F3 Avaliação do teste final:** walk-forward mensal dentro do período, com a configuração (colunas e hiperparâmetros) congelada nos metadados do desenvolvimento, como no retreino da 7.7.
- **F4 Linhas:** todos os modelos usam só as linhas a partir do início da cobertura de notícias (hoje 01/08/2025), para comparar o modelo 1 com o 3 nas mesmas linhas.
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
- **F17 Modelos salvos:** `modelos/xgb-AAAA-MM.json` (modelo 3) e `modelos/xgb-m1-AAAA-MM.json` (modelo 1, top 5 sombra), cada um com `.meta.json` (colunas, período de treino, hiperparâmetros, semente, métricas, universo, sha256 do dataset, versões das bibliotecas). Antes do histórico completo: `provisorio: true`, treinados só com o desenvolvimento.
- **F18 Semente:** uma só, `20261023`, em tudo (XGBoost com `n_jobs=1`, sorteios, bootstrap, logística).
- **F19 Saídas:** `saida/experimento/treino/dev-<data do dataset>/` (fora do git): `relatorio.md`, `metricas.json`, previsões e resumos diários. O treino lê só os CSV do dataset (nunca o banco).

**Decisões da etapa 7 (23/10/2026; plano completo, com os casos de teste, em `docs/plano_etapa7.md`)**
- **S1 Datas:** D = dia da rotina (pregão previsto); t = último pregão antes de D. Fase 1 e notícias com `data_referencia = t`; `experimento_top` e `execucao` com D; `dados_ate` = 08:00 de D.
- **S2 Folha:** todo número de indicador em `{valor, status}`; cadastro pode ter texto nulo sem status.
- **S3 Arquivos:** um por pacote em `saida/D/`, com envelope de lote; cada registro com os metadados.
- **S4 Quando muda:** comparação com o estado do último envio (`saida/estado/`); `substituir_serie` quando um ponto antigo muda; `removidos` para o que sumiu; sem estado, vai tudo.
- **S5 Setor:** média por empresa dos retornos diários (preço em t e no pregão anterior) das ações ON/PN/UNIT do setor, inclusive a própria; BDR fora; dia sem retorno = ponto vazio e a cadeia segue.
- **S6 Índices base 100:** CDI com as taxas de datas < d; IPCA com meses fechados até K(d); lacuna = `indisponivel` dali em diante.
- **S7 % dos índices** em `mercado_dia.indices`.
- **S8 P/L, P/VP e yield diários** em `series_diarias`, calculados por trechos entre entregas de balanço (`fatos/multiplos.py`).
- **S9 Notícias do painel:** mesma janela do modelo; rótulo com empate = neutro; destaque protagonista → força do tom → mais recente.
- **S10 Top 5:** modelo do mês de D ou o mais recente anterior (com aviso); válido só com modelo oficial, até as 10h e depois do fim do teste final; sombras e probabilidades só no registro.
- **S11 Registro do top 5** em `registros/experimento/` (versionável). Com `treino.teste_final.fim` preenchido (produção), é de uso único: gravado na 1ª geração e nunca sobrescrito, e a rodada repetida do mesmo dia reconstrói o pacote do registro. Com `fim` vazio (testes de funcionamento), cada rodada gera de novo e sobrescreve o registro do dia.
- **S12 Histórico vazio até a produção;** nenhum dia do teste final é fechado.
- **S13 Validador próprio** (`saida/contrato.py`), sem dependência nova.
- **S14 Textos prontos** (`saida/textos.py`), com `tom_neutro = 0,05` e as faixas do beta.
- **S15 Acréscimos no `resumo_acao`:** `proventos_por_ano`, `ebitda.rotulo`, `endividamento.aviso`; sem status de grupo.
- **S16 `ativo_no_universo`** = candidata do experimento em t (tipo aceito, não excluída, na composição), mesmo sem preço no dia.
- **S17 Ponto de entrada** `python -m processamento.saida --data D`; a etapa 8 chama `gerar(...)` como função.
- **S18 Bloco `saida`** no `parametros.yaml` (limite das 10h, pastas, `tom_neutro`).
- **S19 Janelas do pacote:** a interface mostra 1m, 6m e 1a. `series_diarias` (inclusive P/L, P/VP e yield diários) com os últimos 253 pregões até t; base 100 sem rebasear (âncora no 1º dia da série; a interface divide pelo 1º valor do recorte); `inicio_janela` em cada série, e o ponto que sai pelo corte não dispara `substituir_serie`; `fundamentos_trimestrais` com os 8 trimestres mais recentes; `proventos` e `proventos_por_ano` com 5 anos; `experimento_historico` sem corte. As contas usam o histórico inteiro; P/L, P/VP e yield por trechos só nos 253 pregões (~8 s por rodada).
- **S20 Formato compacto só no `series_diarias`:** `datas` + `valores` (listas paralelas) + `status` em trechos `{de, ate, status}` só para os pontos que não são `ok`; números sem arredondar (2,6 MB no 1º envio com 253 pontos, contra 8,0 MB em folhas; ~47 KB por dia). Os outros pacotes seguem com a folha.

**Pendências internas por etapa**
- **Etapa 4 (payout), resolvida:** `v1-acoes_emitidas` só separa ON e PN. Em empresas com **duas classes PN** (ex.: USIM5 e USIM6), a quantidade de cada classe não é conhecida: regra de aproximação D2 (decisões da etapa 4; limitação na seção 10).
- **Etapa 8 (vindos da etapa 7):** (a) o calendário só conhece pregões passados: a rotina precisa saber se D é pregão (lista de feriados da B3 no `parametros.yaml` ou checagem no dia seguinte, com o dia descartado pelo `fechar_dia`); (b) checagem diária da seção 6 (poucas ações, retorno > 30%, volume zero, preço parado, indicador vazio) como avisos do `execucao`; (c) fixar `treino.teste_final.fim`, rodar o teste final uma vez e ligar o histórico ao vivo; (d) retreino mensal (`xgb-AAAA-MM`); (e) limpar `registros/experimento/` dos testes de funcionamento antes da produção; (f) medir o tempo da rodada contra o prazo das 9h45.

---

## 10. Pendências externas (não bloqueiam a implementação)

| Pendência | De quem |
|---|---|
| Zeros em `v1-balancos`: `emprestimos_curto_prazo` e `emprestimos_longo_prazo` = 0 **juntos** em 89 linhas de 12 empresas que não são banco (ex.: CSNA3, SBSP3, RDOR3, PCAR3, MGLU3, que têm dívida), e `aplicacoes_financeiras` = 0 em 134 linhas de 19 empresas. Provável conta não encontrada gravada como 0 (deveria ser `NULL`). Pedido à coleta: gravar `NULL` quando a conta não é achada. Enquanto isso, o processamento trata CP e LP = 0 juntos como ausente (seção 6, "Empréstimos zerados"); aplicações = 0 continuam valendo | Coleta |
| Histórico de 5 anos (e testar a cobertura de notícias em 2021–2022) | Coleta |
| Preencher a tabela `v1-composicao_ibov` (criada em 23/10/2026, ainda vazia; enquanto isso, universo = `composicao_atual`, seção 3.5) | Coleta |
| Etapa manual `corrigir_horas` (execução `tipo = 'coletar'`, vista `pendente` em 23/10/2026): provavelmente a correção do horário das notícias pedida abaixo. **Quando concluir, reavaliar a regra N1-A** (seção 7.2) | Coleta |
| Histórico de IDIV, SMLL e IFIX (hoje só 20 e 21/10/2026) e de CDI/IPCA desde jul/2024 (hoje desde jan/2025): prometido para depois da manutenção do Railway | Coleta |
| `data_mudanca` em `v1-mudancas_ticker` | Coleta |
| Autenticação, endereço e forma de envio da API | Equipe da API |
| Manter o filtro da juíza desligado na coleta e informar quantas notícias do histórico ficaram sem julgamento | Coleta |
| Validação do FinBERT: já feita pelo usuário; registrar os números (manchetes, % de acerto, por idioma) | Usuário |
| Empresa com duas classes PN (ex.: USIM5/USIM6, BRKM5/BRKM6): `v1-acoes_emitidas` traz só o total de PN, então o payout usa, em cada provento, a média das classes PN que pagaram naquele evento × qtd_pn. É exato quando as classes pagam igual; limitação registrada no TCC. Resolve-se com a quantidade por classe | Coleta |
| Balanço reapresentado: `v1-balancos` guarda só a última versão, com a sua `data_entrega`. Antes dessa data o período fica sem dado (`historico_insuficiente`); não há vazamento, mas a versão original não é recuperável. Limitação registrada no TCC. Resolve-se guardando as versões | Coleta |
| **Horário real das notícias do Google News:** ~91% vêm com 00:00 de Los Angeles (só a data). O processamento trata como "só data" (seção 7.2), o que impede separar pregão de noite. Pedido à coleta: obter o horário real de publicação (ex.: pela página da notícia, no enriquecimento) e marcar `published_precision = 'date'` quando só a data for conhecida | Coleta |
| Notícias coletadas retroativamente: `data_hora_coleta` começa em 07/09/2026 (mediana de ~133 dias entre publicação e coleta). O conjunto histórico pode diferir do que estaria disponível ao vivo em cada data (notícias apagadas ou que só apareceram depois). Limitação registrada no TCC; ao vivo, o corte vale desde set/2026 | Coleta |
| Abertura da ação = fechamento do pregão anterior em ~11% dos pares (ação, dia) (5.021 de 45.839, medido em 23/10/2026; maior em ações de preço baixo, ex.: RAIZ4 48%). Provável igualdade real (passo mínimo de R$ 0,01), **não confirmada**; afeta o `salto_abertura`. Limitação registrada no TCC | Coleta |
| Abertura do IBOV em `v1-precos` (fonte Yahoo): em 32,5% dos pares de pregões consecutivos (557 pares medidos em 23/10/2026), a `abertura` do IBOV é igual ao `fechamento` do pregão anterior (abertura não informada pela fonte). Nesses dias o `alvo_abertura` vira "a ação abriu em alta?", e não "abriu melhor que o Ibovespa?". **Na etapa 6, o `alvo_abertura` é avaliado só nos dias em que a abertura do IBOV ≠ fechamento anterior.** Nenhuma variável do modelo usa a abertura do IBOV (só o `alvo_abertura`); o alvo principal usa o fechamento e não é afetado. Limitação registrada no TCC. Resolve-se com a abertura real do índice | Coleta |
| **Notícias das versões "principais" e "hora real na noite" (medido em 23/10/2026, etapa 6):** antes de out/2026, só **3% a 15%** das linhas (ação, pregão) têm alguma notícia nessas versões (principais ~14–15%; hora real na noite ~3–5%), contra 71–89% na versão com todas as notícias; só em out/2026 sobem para ~60%. Motivos: 89% das notícias estão sem julgamento da juíza (`papel` vazio) e ~90% não têm hora real (N1-A). Consequência: os testes extras da 7.4/7.5 com essas versões **só terão sentido com o histórico novo ou no teste ao vivo**; no desenvolvimento atual, nas dobras de 2025, nenhuma árvore desses dois modelos usa as colunas de notícia, e as previsões das duas versões saíram idênticas entre si. Resolve-se com o julgamento da juíza no histórico e o horário real das notícias | Coleta |
| **Quantidade de ações em escala errada em `v1-acoes_emitidas`** (medido em 23/10/2026): ~25 empresas com a quantidade em **milhares** (ex.: Vibra 1.198.563 em vez de ~1,1 bilhão; VALE ~4,5 milhões; ITUB ~10,8 milhões), provavelmente porque a CVM informa a escala do formulário e ela não foi aplicada. Pedido à coleta: gravar sempre em **unidades**, aplicando a escala da CVM. Enquanto isso, o processamento marca a quantidade como suspeita quando o P/VP < 0,05 e deixa valor de mercado, P/L, P/VP e payout `indisponivel` (seção 6); o diagnóstico lista as empresas | Coleta |
| Desdobramento ou bonificação entre o último balanço e t: o valor de mercado usa o preço já ajustado × a quantidade antiga de `v1-acoes_emitidas` e fica errado pelo fator. Limitação registrada no TCC. Pode ser conferido no futuro com `v1-raw_b3_suplemento` | Coleta |

**Resolvidas em 22/10/2026** (as fontes não tinham os dados; não foi erro da coleta):
- CRFB3, SRNA3 e STBP3 sem preço → removidas da análise (seção 3.4). Registrar no TCC como **viés de sobrevivência**.
- Classes extintas nos proventos (VALE5, AXIA6, CPLE5 etc.) → identificadas pelo `other_codes`; seus proventos contam no histórico e no payout, ligados pela raiz; units ficam de fora (seções 3.4 e 6).
- CNPJs 03847461000192 e 06057223000171 sem balanço → indicadores de balanço `indisponivel` (seção 3.4).
- EBIT, depreciação, empréstimos, caixa e aplicações em `v1-balancos`: preenchidos pela coleta (~90%, como `lucro_bruto`). O diagnóstico passa a tratá-los como parciais; as etapas `cvm_itr_dfp` e `build_entrega` (execução manual `tipo = 'coletar'`) passam a ser conhecidas e só geram divergência se aparecerem num daily. Em 23/10/2026 entrou também `corrigir_horas` (mesma regra: nota).

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
