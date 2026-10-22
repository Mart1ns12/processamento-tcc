# ESPECIFICAÇÃO DO MÓDULO DE PROCESSAMENTO (fonte da verdade)

> Versão de 21/10/2026. Este arquivo descreve **só o que vale hoje** e deve ser seguido na implementação.
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

**Pergunta do TCC:** o sentimento das notícias, lido pelo FinBERT, ajuda a prever o desempenho das ações? Foco nas **notícias publicadas entre o fechamento e a manhã seguinte**.

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
│   └── noticias.py          # resumo do tom e manchetes do dia
├── experimento/             # Fase 2
│   ├── dataset.py           # variáveis + alvo (seção 7)
│   ├── preparacao.py        # ranks e tratamento (mesma função no treino e na previsão)
│   ├── treino.py            # walk-forward, modelos 1/2/3/3b
│   ├── avaliacao.py         # acaso, bootstrap, top 5 (e top 3) × últimos 5, robustez por ano
│   └── previsao.py          # top 5 do dia + motivos
├── saida/                   # pacotes da seção 8 (arquivo JSON hoje; API depois)
└── rotina.py                # gatilho diário (seção 4)
tests/                       # na raiz do projeto (pytest.ini: testpaths = tests); fixtures em tests/dados/
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
| `v1-balancos` | `cnpj`, `tipo_documento`, `data_inicio_periodo`, `data_fim_periodo` | todas | Consolidado, em reais. Trimestre e acumulado do ano em linhas separadas. `data_entrega` = da última versão do documento. **Hoje só vêm receita, lucro bruto, lucro líquido e patrimônio**; `ebit`, `depreciacao_amortizacao`, `emprestimos_*`, `caixa`, `aplicacoes_financeiras` estão vazias até a coleta corrigir |
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
| EBITDA e endividamento sem dados | Implementar e testar com dados de teste. Com colunas vazias: `status = indisponivel` |
| Histórico curto (~1 ano hoje; meta de 5 anos) | Implementar tudo. **Não treinar o modelo "para valer"** até o histórico completo chegar; com 1 ano, só teste de funcionamento (sem conclusões) |
| Composição histórica do Ibovespa | Ver 3.5 |
| `data_mudanca` vazia | Unir históricos pela `v1-mudancas_ticker` assim mesmo; quando a data vier, usá-la |
| Ações deslistadas sem preço nas fontes: CRFB3, SRNA3, STBP3 (decidido com a coleta em 22/10/2026) | Fora do universo **em todas as datas**. Lista em `processamento/config/exclusoes.yaml` (`tickers_excluidos`). Entra na limitação de **viés de sobrevivência** do TCC |
| Classes extintas nos proventos (ex.: VALE5, AXIA6, CPLE5) | Classe que **não aparece** no `other_codes` da empresa em `v1-raw_b3_cadastro` é **extinta hoje**, mas existiu: seus proventos são reais e **contam normalmente** no histórico de proventos e no payout, ligados à empresa pela raiz (seção 6). **Units (final 11) continuam de fora** do payout (regra da unit). "Extinta" é só informação. Decidido em 22/10/2026 pelos números do diagnóstico: AXIA5, AXIA6 e CPLE5 pagaram dentro do período analisado |
| Empresas sem balanço nas fontes: CNPJs 03847461000192 e 06057223000171 (decidido com a coleta em 22/10/2026) | A empresa continua no painel de preços e no modelo; P/L, P/VP, ROE, margens, EBITDA, endividamento e payout saem com `status = indisponivel`. Lista em `exclusoes.yaml` (`cnpjs_sem_balanco`) |
| Itens acima no diagnóstico (etapa 1) | Aparecem como **nota "excluídos por decisão"**, não como divergência |

### 3.5 Universo de ações por data
- Se existir a tabela da composição (pedida como `` `v1-composicao_ibov` ``: `ticker`, `data_inicio`, `data_fim`): em cada pregão, só entram ações com `data_inicio ≤ data` e (`data_fim` vazio ou `≥ data`).
- Senão: todas as ações do `v1-cadastro` (`tipo_acao` ON, PN ou UNIT) e marcar `universo = 'composicao_atual'`.
- **Conversores aceitos:** intervalos (formato pedido); "fotos" das carteiras (`data_carteira`, `ticker` → a ação entra na primeira carteira em que aparece e sai na primeira em que some); colunas de entrada e saída no cadastro.
- **Sempre (decidido em 22/10/2026):** ação **sem preço numa data** fica fora do universo **naquela data**; os `tickers_excluidos` de `exclusoes.yaml` ficam fora em **todas** as datas.
- O filtro vale para o **modelo** e para o **histórico do experimento**. O painel de fatos usa as ações atuais.

---

## 4. Rotina diária

1. A coleta roda **uma vez por dia, às 8h** (Brasília).
2. A partir das **8h**, a cada **~5 minutos**, o processamento consulta:
   - em `v1-painel_execucoes`: o daily mais recente de hoje (`tipo = 'daily'`). **`iniciada_em` está em UTC**: converter para São Paulo antes de comparar a data;
   - em `v1-painel_etapas` (por `execucao_id`): esperar **`etapa_id = 'entrega'` com `status = 'concluida'`**. **Não esperar o daily inteiro** (a etapa seguinte, `analise`, não interessa e, se falhar, deixa o daily `parcial`);
   - conferir se `precos`, `noticias` e `enriquecimento` também estão `concluida`. Se não: seguir, mas com aviso.
3. Com a entrega pronta: calcular a Fase 1, fechar o resultado do top 5 do pregão anterior, gerar o top 5 de hoje e enviar os pacotes (ordem na seção 8.5).
4. **Prazo: 9h45.** Se a entrega não terminou, gerar com os dados disponíveis e marcar com aviso.
5. O top 5 é gravado com `gerado_em`. **Se gerado depois das 10h, `valido_para_historico = false`.**

Etapas da coleta, em ordem: `precos`, `macro`, `noticias`, `ipe`, `enriquecimento`, `juiza`, `cadastro`, `entrega`, `analise`. Status de etapa: `pendente`, `em_andamento`, `concluida`, `falhou`, `pulada`.

---

## 5. Fase 1: indicadores do painel

Fonte dos dados: tabelas da seção 3. `fech` = `fechamento`; `aj` = `fechamento_ajustado`. Comparações com o setor usam a **média das ações das outras empresas do mesmo setor** (sem a própria empresa: tiram-se todas as ações do mesmo CNPJ, ex.: PETR3 não entra no setor da PETR4); se o setor tem menos de 3 empresas (CNPJs distintos, contando a própria), `setor_comparacao_fraca = true`. Só ON, PN e UNIT entram nos pares (setor e `posicao_pct`); BDR aparece no painel, mas fica fora dos pares (`posicao_pct = nao_se_aplica`). Janelas "1 dia, 1 mês, 6 meses, 1 ano" = **1, 21, 126 e 252 pregões** (decisões de 22/10/2026; detalhes na seção 9, etapa 3).

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
| EBITDA | EBIT 12m + depreciação e amortização 12m; margem = EBITDA ÷ receita 12m | `nao_se_aplica` em bancos/seguradoras; `indisponivel` enquanto a coleta não preencher. Rótulo: "EBITDA (cálculo padrão CVM)" |
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
- **Sem horário:** notícias sem `data_hora_publicacao` (ex.: documentos da CVM) ficam num grupo à parte, pela data.
- O mesmo corte das 8h vale no **treino** e **ao vivo**.

### 7.3 Colunas do dataset (uma linha por ação por pregão t)

**Identificação** (não entra no aprendizado): `data`, `ticker`, `setor`.

**Variáveis explicativas**

| Variável | Cálculo | Grupo |
|---|---|---|
| `noticias_noite_qtd` | Nº de notícias da janela da noite | Essencial |
| `noticias_noite_tom` | Média de `prob_positivo − prob_negativo` na janela | Essencial |
| `noticias_noite_extremo` | O score de maior valor absoluto na janela | Essencial |
| `mudanca_tom` | Tom da noite − tom médio da empresa nos 30 pregões anteriores | Essencial |
| `noticias_pregao_tom` | Tom das notícias da janela do pregão | Essencial |
| `tom_setor` | Tom médio das notícias das outras empresas do setor (janela da noite) | Complementar |
| `tom_mercado` | Tom médio de todas as notícias da janela da noite | Complementar |
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

- Variáveis de preço, volume e mercado entram como **rank** dentro do pregão (percentil 0–1; empates pela média; vazio continua vazio).
- Filtro do universo por data (3.5) antes de calcular os ranks.

### 7.4 Modelos (definidos antes de rodar)
| Modelo | Variáveis | Responde |
|---|---|---|
| 1. Base | Preço, volume e mercado | Quanto o preço sozinho explica |
| 2. + notícias do pregão | 1 + `noticias_pregao_tom` | Notícias do dia ajudam? |
| 3. + notícias da noite | 2 + notícias da noite + `mudanca_tom` | **Hipótese principal** |
| 3b. Dias de resultado | Modelo 3 só nos dias com balanço divulgado na janela | O efeito é maior em dia de balanço? |

**Notícias usadas pelo modelo (decidido em 21/10/2026):**
- **Versão principal: todas as notícias** de `v1-noticias` (sem filtro).
- **Teste extra: só as principais.** Recalcular as variáveis de notícias usando só as linhas com `origem = 'cvm_ipe'` **ou** (`tipo_conteudo = 'reportagem'` **e** `papel` em `protagonista` ou `citada_com_fato`). Notícias sem julgamento da juíza (`papel` vazio) ficam fora dessa versão; **contar quantas são e informar no relatório**. Comparar as duas versões com a mesma validação (seção 7.5). Se a filtrada for melhor, é um achado do TCC.
- O filtro é feito **no processamento**; a coleta mantém o filtro dela desligado (`ENTREGA_FILTRO_JUIZA=false`).

Ordem: primeiro só as **essenciais**; depois os **complementares**, um bloco por vez, mantendo só o que melhora na validação.
XGBoost, ponto de partida: `n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5`. Grade pequena escolhida pela validação.

### 7.5 Avaliação
- **Walk-forward mensal** (treina no passado, testa no mês seguinte, avança), com **embargo de 1 pregão**.
- **Conjunto de teste final** separado e usado **uma única vez**.
- **Corte principal: top 5** (o que vai para a tela). Avaliar também o **top 3** com as mesmas métricas, para mostrar que o resultado não depende do corte.
- Métricas: acerto do top 5 × **faixa do acaso** (10 mil sorteios aleatórios de 5 ações por dia, faixa de 95%); retorno médio do top 5 − IBOV; **top 5 × últimos 5**; AUC geral e AUC médio por pregão; IC por bootstrap em blocos de pregão; **robustez por ano**; se o universo for o atual, **análise de sensibilidade** (último ano × anteriores).
- **Referências de comparação** (rodadas com a mesma validação): escolha ao acaso (faixa acima), regra simples só com a volatilidade (ações mais calmas primeiro) e **regressão logística** com as mesmas variáveis. O XGBoost só "ganha" se superar as três.
- Diferença dentro da faixa do acaso = "ainda não mostrou vantagem sobre o acaso".

### 7.6 Previsão diária (top 5)
- Ordenar as ações do dia pela probabilidade do modelo e pegar as 5 primeiras. Na tela: **"5 ações com maior chance de superar o Ibovespa (experimento)"**.
- **Motivos:** contribuições do XGBoost (`pred_contribs`), traduzidas em frases ("Notícias da noite com tom positivo (3 notícias)"), com efeito `ajudou`/`atrapalhou`/`neutro`.
- **Chance:** calculada, mas `exibir = false` até a calibração ser conferida (se o modelo diz 60%, ~60% acontecem). Mostrar sempre ao lado da média de 50%.
- Gravar o top 5 do dia no momento da geração (histórico nunca recalculado depois).
- No dia seguinte, fechar o resultado: `superou` = retorno da ação > retorno do IBOV no pregão previsto.

### 7.7 Modelo em uso no dia a dia
- **Qual modelo gera o top 5:** o **modelo 3** (com as notícias da noite), porque é ele que testa a hipótese do TCC. Ele é mostrado mesmo que não supere o acaso: o selo "em avaliação" e o histórico existem para isso.
- **Comparação ao vivo:** todo dia, gravar também (sem mostrar na tela) o top 5 do **modelo 1** (sem notícias) e o da **regra da volatilidade**. Assim, o histórico mostra, com dados de verdade e daqui para frente, se as notícias fazem diferença.
- **Retreino mensal:** no primeiro dia útil de cada mês, treinar de novo com todo o histórico até o fim do mês anterior (o mesmo esquema do walk-forward). Os hiperparâmetros só mudam numa nova avaliação completa, nunca no retreino automático.
- **Arquivo do modelo:** salvar em `modelos/xgb-AAAA-MM.json`, com um arquivo de metadados ao lado: variáveis usadas, período de treino, hiperparâmetros, métricas da validação, universo (`composicao_atual` ou histórica) e um hash do dataset. O `modelo_versao` do pacote `experimento_top` aponta para esse arquivo.
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
| `status` de cada indicador | `ok` · `nao_se_aplica` (ex.: margem de banco) · `indisponivel` (dado ainda não veio da coleta, ex.: EBITDA hoje) · `historico_insuficiente` (ex.: beta com menos de 120 pregões) · `lucro_negativo` (P/L de empresa com prejuízo: valor mostrado com aviso) |
| Textos prontos | Opcionais, em campos `texto` (ex.: `"mais calma que 96% das ações"`). O número sempre vem junto; a interface pode usar um ou outro |
| Chave de gravação | Cada pacote declara a chave (`data_referencia` + `ticker` etc.). A API grava por **upsert**: reenviar substitui, nunca duplica |
| Metadados | Todo pacote tem `gerado_em` e `dados_ate` (até quando os dados da coleta vão) |

### 8.2 Os pacotes

| # | Pacote | Uma unidade por | Chave | Quando é enviado | Alimenta na tela |
|---|---|---|---|---|---|
| 1 | `acoes` | ação | `ticker` | Quando muda (cadastro) | Nome, setor, tipo de ação, busca |
| 2 | `mercado_dia` | dia | `data_referencia` | Todo dia | Faixa do mercado: Ibovespa, dólar, Brent, CDI |
| 3 | `resumo_acao` | ação × dia | `data_referencia` + `ticker` | Todo dia | O card da ação: todos os indicadores da Fase 1 (valor atual) |
| 4 | `series_diarias` | ação (ou índice) × dia | `ticker` + `data` | Todo dia (dia novo); **reenvio da série inteira** da ação que teve dividendo, desdobramento ou bonificação (o ajustado do passado muda) | Gráficos de preço, rentabilidade, comparação com Ibovespa, setor e índices, volume |
| 5 | `fundamentos_trimestrais` | ação × trimestre | `ticker` + `data_fim_periodo` | Quando sai balanço novo | Gráficos de margens, ROE, EBITDA, endividamento |
| 6 | `proventos` | provento | `ticker` + `tipo` + `data_com` | Quando há provento novo | Histórico de dividendos (tabela e barras por ano) |
| 7 | `noticias_dia` | ação × dia | `data_referencia` + `ticker` | Todo dia | Manchetes com rótulo e resumo do tom |
| 8 | `experimento_top` | dia | `data_referencia` | Todo dia, **antes das 10h** | Aba Experimento: as 5 ações e os "detalhes" |
| 9 | `experimento_historico` | dia (+ resumo) | `data_referencia` | Todo dia (o resultado do dia anterior só se conhece depois do fechamento) | Histórico de acertos × acaso |
| 10 | `execucao` | rodada | `data_referencia` + `rodada` | Ao fim de cada rodada | Status do sistema e avisos ("dados de hoje incompletos") |

### 8.3 Campos de cada pacote

**1. `acoes`:** `ticker`, `empresa`, `setor`, `subsetor`, `tipo_acao` (ON, PN, UNIT, BDR), `ativo_no_universo` (bool).

**2. `mercado_dia`:** `data_referencia`, e para `IBOV`, `USDBRL`, `BRENT`: `fechamento`, `variacao_dia`; `cdi_dia` (fração ao dia); `ipca_12m`; `ipca_ate` (último mês de IPCA usado, `AAAA-MM`, para a interface mostrar "IPCA até <mês>").

**3. `resumo_acao`** (um objeto por indicador, sempre com `valor`, `status` e, quando faz sentido, `setor`, `posicao_pct` e `texto`):
- `cotacao`: `fechamento`, `variacao_dia`
- `variacao_preco`: `d1`, `m1`, `m6`, `a1` (sem dividendos)
- `rentabilidade`: `d1`, `m1`, `m6`, `a1` (com dividendos) + as mesmas janelas do `IBOV` e do setor (`ibov`, `setor`), para a comparação lado a lado com seletor de 1 dia, 1 mês, 6 meses e 1 ano
- `volume`: `total`, `relativo` (÷ mediana de 20), `mediana_20` (para a linha de referência do gráfico de barras), `posicao_pct`
- `volatilidade_20d`: `valor` (desvio diário), `posicao_pct` (fração de ações mais calmas)
- `beta`: `valor`, `status`
- `pl`, `pvp`, `roe`, `dividend_yield`, `payout`, `margem_bruta`, `margem_liquida`: `valor`, `setor` (média do setor sem a própria empresa), `status`
- `payout_por_ano`: lista (`ano`, `valor`, `status`) dos últimos anos, para o gráfico de barras do payout
- `ebitda`: `valor_12m`, `margem`, `setor_margem`, `status`
- `endividamento`: `divida_liquida`, `dl_pl`, `dl_ebitda`, `caixa_liquido` (bool), `setor_dl_pl`, `setor_dl_ebitda`, `status`
- `setor_comparacao_fraca` (bool: setor com menos de 3 empresas)
- `balanco_referencia`: `data_fim_periodo` e `data_entrega` do balanço usado

**4. `series_diarias`:** `ticker`, `data`, `fechamento` (sem dividendos), `indice_retorno_total` (base 100 no início da série, com dividendos), `volume`. Também para `IBOV`, para cada setor (`SETOR:<nome>`, média de todas as ações do setor; **no gráfico, a linha do setor inclui a própria ação**, diferente dos valores do `resumo_acao`, que a excluem; diferença pequena, registrada como decisão) e para os índices (`CDI`, `IPCA`, `IDIV`, `SMLL`, `IFIX`, `IVVB11`), em base 100 acumulada. **A interface recorta o período e "parte do mesmo ponto" dividindo pelo primeiro valor do recorte.** Campo `substituir_serie: true` quando a série inteira da ação está sendo reenviada.

**5. `fundamentos_trimestrais`:** `ticker`, `data_fim_periodo`, `data_entrega`, `receita_trimestre`, `receita_12m`, `lucro_liquido_trimestre`, `lucro_liquido_12m`, `margem_bruta`, `margem_liquida`, `roe`, `ebitda_trimestre` (para o gráfico de barras por trimestre), `ebitda_12m`, `margem_ebitda`, `divida_liquida`, `dl_pl`, `dl_ebitda`, `payout_12m`, cada um com `status`. Margens, ROE e payout são sempre de 12 meses.

**6. `proventos`:** `ticker`, `tipo` (DIVIDENDO, JCP), `data_com`, `data_pagamento`, `valor_por_acao`. A soma por ano a interface faz (ou vem pronta em `resumo_acao`).

**7. `noticias_dia`:** `data_referencia`, `ticker`, `resumo` (`quantidade`, `positivas`, `neutras`, `negativas`, `tom_medio`) e `itens` (lista: `id`, `titulo`, `fonte`, `link`, `publicado_em`, `rotulo` = maior das 3 probabilidades, `prob_positivo`, `prob_neutro`, `prob_negativo`, `janela` = `pregao` / `noite` / `sem_horario`, `destaque` = ordem para "principais manchetes"). Critério do `destaque`: primeiro as notícias em que a empresa é protagonista (juíza: `papel = protagonista`, quando houver), depois a força do tom (\|positivo − negativo\|) e por fim a mais recente.

**8. `experimento_top`:** lista `ranking` com as **5** ações (posição 1 a 5), cada uma com chance, motivos e notícias usadas.
```json
{
  "versao_contrato": "1.0",
  "data_referencia": "2026-06-22",
  "pregao_previsto": "2026-06-22",
  "gerado_em": "2026-06-22T09:12:00-03:00",
  "dados_ate": "2026-06-22T08:00:00-03:00",
  "valido_para_historico": true,
  "modelo_versao": "xgb-2026-11-01",
  "universo": "composicao_atual",
  "selo": "em_avaliacao",
  "avisos": [],
  "ranking": [
    {
      "posicao": 1,
      "ticker": "CMIG4",
      "chance": {"valor": 0.54, "media": 0.50, "exibir": false},
      "motivos": [
        {"fator": "tom_noticias_noite", "valor": 0.42, "efeito": "ajudou", "texto": "Notícias da noite com tom positivo (3 notícias)"},
        {"fator": "retorno_5d", "valor": -0.031, "efeito": "ajudou", "texto": "Caiu mais que a média nos últimos 5 dias"}
      ],
      "noticias_usadas": ["n000123", "n000124"]
    }
  ]
}
```
(valores ilustrativos) `valido_para_historico = false` se for gerado depois das 10h. `chance.exibir` só vira `true` depois que a calibração for conferida.

**9. `experimento_historico`:** por dia: `data_referencia`, `ranking` (os 5 tickers), `resultado` (para cada um: `retorno`, `retorno_ibov`, `superou`), `acertos_dia` (0 a 5), `acertos_top3` (0 a 3, só para a avaliação). E um resumo: `periodo_inicio`, `periodo_fim`, `n_dias`, `taxa_acerto`, `acaso_media`, `acaso_faixa` (`[min, max]` de 95%), `universo`, `nota` (ex.: "Histórico calculado com as ações que compõem o Ibovespa atualmente.").

**10. `execucao`:** `data_referencia`, `rodada`, `inicio`, `fim`, `status` (`ok`, `parcial`, `falhou`), `coleta_status` (o que se leu do painel da coleta), `pacotes_enviados`, `avisos` (lista de textos).

### 8.4 Cobertura da planilha (conferida item a item)
Todas as 23 informações da planilha (`docs/planilha_final.xlsx`; cálculos na seção 5) têm origem num pacote: Top 5 e detalhes → `experimento_top` (+ `resumo_acao` e `noticias_dia`); Histórico do experimento → `experimento_historico`; Volume total, volume relativo, volatilidade, beta, cotação, variação do preço, rentabilidade, P/L, P/VP, ROE, yield, payout, margens, EBITDA e endividamento (valor atual) → `resumo_acao`; comparação com Ibovespa, setor e índices, gráficos de preço, rentabilidade e volume → `series_diarias` (+ `resumo_acao` para os % de cada período); gráficos trimestrais de margens, ROE, EBITDA e endividamento → `fundamentos_trimestrais`; gráfico do payout por ano → `resumo_acao.payout_por_ano`; dividend yield (barras) e histórico de dividendos → `proventos`; tom das notícias → `noticias_dia`.

### 8.5 Ordem diária de envio
1. `execucao` (início) → 2. `acoes` (se mudou) → 3. `series_diarias` → 4. `mercado_dia` → 5. `resumo_acao` → 6. `fundamentos_trimestrais` e `proventos` (se mudaram) → 7. `noticias_dia` → 8. `experimento_historico` (fecha o dia anterior) → 9. `experimento_top` (antes das 10h) → 10. `execucao` (fim).

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
- **Setor:** modo "empresa" (seção 5). Ação sem setor ou sem outra empresa no setor: `indisponivel`; há outras, mas nenhuma com valor: `historico_insuficiente`.
- **BDR:** entra no painel, fora dos pares (setor e `posicao_pct`).
- **IPCA:** só meses fechados, sem rateio por dia. Na data d valem os meses anteriores ao mês de d; o acumulado da janela é o produto dos meses entre o último mês conhecido na base e o último conhecido em t. Ao vivo, nos primeiros ~10 dias do mês o IPCA fica defasado: por isso a saída informa `ipca_ate`.
- **CDI:** entram as taxas com data em [base, t) (a taxa do dia d rende de d a d+1); a taxa de t não entra. `cdi_dia` = taxa da última data ≤ t.
- **Lacunas de preço:** rentabilidade e variação usam a base "as-of" (último preço até t−n). Volatilidade e volume relativo exigem os 20 pregões completos; senão `historico_insuficiente`. Beta conta só pares de retornos válidos, mínimo 120.
- **Volatilidade:** desvio-padrão amostral (ddof = 1), diário, sem anualizar.
- **`posicao_pct`:** do volume, calculada sobre o volume **relativo**. Fórmula: nº de pares estritamente menores ÷ (nº de pares válidos − 1); menor = 0, maior = 1; menos de 2 válidos: `indisponivel`.
- **Comparação com índices:** janelas d1, m1, m6 e a1.
- Enquanto a coleta não completar os índices (seção 10), as janelas sem dados saem `historico_insuficiente`/`indisponivel`. Isso está correto, não é bug.

**Pendências internas por etapa**
- **Etapa 7 (vindos da etapa 3, não implementados nela):** (a) `mercado_dia`: `fechamento` e `variacao_dia` de `IBOV`, `USDBRL` e `BRENT` (reusar `grade_de_precos` + `variacao(g_fech, 1)` de `processamento/fatos/precos.py`); (b) `series_diarias` (seção 8.3, pacote 4): `fechamento`, `indice_retorno_total` base 100 (`aj(t)/aj(início) × 100`), `volume`, para cada ação, `IBOV`, `SETOR:<nome>` e índices (`CDI`, `IPCA`, `IDIV`, `SMLL`, `IFIX`, `IVVB11`) em base 100 acumulada (reusar o acumulado de CDI/IPCA de `processamento/fatos/indices.py`). Os cálculos ficam em `processamento/fatos/` (funções puras com teste); a etapa 7 só empacota. **A decidir no plano da etapa 7:** como montar a série `SETOR:<nome>` (média dos retornos diários das ações do setor, encadeada em base 100, é o candidato) e o que fazer com ações que entram/saem do setor no meio da série.
- **Etapa 4 (payout):** `v1-acoes_emitidas` só separa ON e PN. Em empresas com **duas classes PN** (ex.: USIM5 e USIM6), a quantidade de cada classe não é conhecida: o payout vai precisar de uma **regra de aproximação**, a decidir no plano da etapa 4.

---

## 10. Pendências externas (não bloqueiam a implementação)

| Pendência | De quem |
|---|---|
| Preencher EBIT, depreciação, empréstimos, caixa e aplicações em `v1-balancos` | Coleta |
| Histórico de 5 anos (e testar a cobertura de notícias em 2021–2022) | Coleta |
| Tabela `v1-composicao_ibov` | Coleta |
| Histórico de IDIV, SMLL e IFIX (hoje só 20 e 21/10/2026) e de CDI/IPCA desde jul/2024 (hoje desde jan/2025): prometido para depois da manutenção do Railway | Coleta |
| `data_mudanca` em `v1-mudancas_ticker` | Coleta |
| Autenticação, endereço e forma de envio da API | Equipe da API |
| Manter o filtro da juíza desligado na coleta e informar quantas notícias do histórico ficaram sem julgamento | Coleta |
| Validação do FinBERT: já feita pelo usuário; registrar os números (manchetes, % de acerto, por idioma) | Usuário |

**Resolvidas em 22/10/2026** (as fontes não tinham os dados; não foi erro da coleta):
- CRFB3, SRNA3 e STBP3 sem preço → removidas da análise (seção 3.4). Registrar no TCC como **viés de sobrevivência**.
- Classes extintas nos proventos (VALE5, AXIA6, CPLE5 etc.) → identificadas pelo `other_codes`; seus proventos contam no histórico e no payout, ligados pela raiz; units ficam de fora (seções 3.4 e 6).
- CNPJs 03847461000192 e 06057223000171 sem balanço → indicadores de balanço `indisponivel` (seção 3.4).

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
