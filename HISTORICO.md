# HISTÓRICO E CONTEXTO DO TCC (consulta)

> **Este arquivo é histórico.** A especificação que deve ser seguida na implementação é a `ESPECIFICACAO.md`. Em caso de conflito, **vale a ESPECIFICACAO.md**. Aqui ficam o porquê das decisões, os resultados dos testes antigos, o dataset v1, o texto original da planilha e a evolução das decisões (inclusive coisas que mudaram depois, como o top 3, que virou top 5). Os scripts, datasets e PDFs antigos citados aqui **não estão na pasta do projeto** (foram arquivados à parte) e não devem ser procurados.

# (conteúdo original: CONTEXTO DO TCC, versão 21/10/2026)

> Este arquivo reúne **tudo o que foi decidido** nas conversas com o Claude até 21/10/2026 (a seção 14 descreve o banco real da coleta). Ele serve para continuar o trabalho na IDE sem perder nada.
> Ele **substitui** o `CONTEXTO_TCC.md` antigo (de 13/10/2026). O conteúdo útil daquele arquivo está na seção 12.

---

## 0. Instruções para o Claude (leia primeiro)

**Quem é o usuário:** estudante, autor do TCC, responsável pelo **módulo de processamento**. Ele fala português.

**Como conversar com ele:**
- Seja **direto e simples**. Ele pediu explicitamente: "converse comigo como se eu fosse uma batata". Explique sem jargão, com analogias do dia a dia, e só depois o termo técnico.
- Use **tabelas** para comparações e listas de itens; ele monta tudo em planilhas.
- Quando ele pedir "só a parte X", mande **só** aquela parte.
- Seja **honesto** sobre limitações e resultados fracos. Ele prefere a verdade ("o modelo ainda não mostrou vantagem sobre o acaso") a números bonitos.
- Avise quando um número for **ilustrativo** e não real (já houve confusão com isso).
- Quando revisar algo que ele montou, confira **cada informação até a coluna de dado que a alimenta**. Uma revisão superficial já deixou lacunas passarem.

**Antes de tocar no banco, leia a seção 14** (o banco real, as tabelas proibidas e as divergências em relação ao combinado). **A saída do processamento segue o contrato da seção 15.**

**Regra de ouro do projeto:** nada do futuro pode vazar para a previsão. Toda variável usa só o que se sabia **antes da abertura** do pregão previsto.

**Linguagem do produto:** nunca "compre", "recomendação", "oportunidade" ou "melhores ações". Use "estimativa", "experimento" e "maior chance segundo o modelo". Aviso fixo: **"Não constitui recomendação de investimento."**

---

## 1. O projeto

- **Título do TCC:** "Módulo Inteligente para Análise de Sentimento e Predição de Ativos Financeiros".
- **3 módulos (cada um feito por membros do grupo):**
  1. **Coleta/extração:** busca notícias, preços, balanços etc. e grava num **banco de dados**.
  2. **Processamento (a parte do usuário):** calcula indicadores, monta o dataset, treina e roda o modelo, e gera os dados prontos para a tela.
  3. **Interface:** mostra tudo ao investidor.
- **Entrevista com especialista** em bolsa (já feita). O que ele disse e que guiou as decisões:
  - Volume é "essencial". A comparação com o Ibovespa é útil, e com o **setor** também.
  - Quer P/L, P/VP, endividamento, dividend yield e ROE. Dólar e petróleo importam para as empresas expostas.
  - **Manchetes** são úteis ("pela manchete o investidor vê se tem interesse"); a **quantidade** de notícias, não.
  - Notícias publicadas **depois do fechamento** (ex.: balanço à noite) mexem com a **abertura**.
  - Desconfia de "58% de chance" e não mostraria isso, mas acha que "vale mostrar o histórico".
  - Olha primeiro o comportamento do preço, com destaque para o longo prazo.

---

## 2. Organização em 2 fases (decisão central)

| Fase | O que é | Natureza |
|---|---|---|
| **Fase 1: Painel de fatos** | Informações **100% confirmadas e calculáveis**: cotação, rentabilidade, comparação com Ibovespa e setor, volume, volatilidade, beta, P/L, P/VP, ROE, margens, EBITDA, endividamento, dividendos, índices. **Nenhuma previsão.** | Produto: útil ao investidor hoje |
| **Fase 2: Experimento científico** | XGBoost + FinBERT tentando prever quais ações superam o Ibovespa no **próximo pregão**. Aparece numa **aba "Experimento"**, separada, com selo "em avaliação" e histórico de acertos. | Ciência: é a pergunta do TCC |

**Por quê:** o modelo testado até agora não mostrou vantagem sobre o acaso (seção 4). Separar as fases evita que a tela "prometa" algo não comprovado e transforma o modelo num **experimento honesto e verificável**.

---

## 3. Fase 2: o experimento

### 3.1 Pergunta do TCC
> **"O sentimento das notícias, lido pelo FinBERT, ajuda a prever o desempenho das ações?"**

Foco escolhido (o mais forte academicamente): **notícias publicadas depois do fechamento → reação na abertura e no pregão seguinte.**
Motivo: a notícia publicada durante o pregão **já entra no preço** até o fechamento (os testes confirmaram isso). A única notícia que o preço **ainda não viu** é a que sai depois do fechamento.

### 3.2 Hipóteses
| Hipótese | Enunciado | Situação |
|---|---|---|
| H1 | Notícias **do dia** ajudam a prever o pregão seguinte | Testada com 1 ano: **sem ganho comprovado** |
| H2 | Notícias **da noite** (fechamento → abertura) ajudam a prever o pregão seguinte | **Principal.** Depende do horário das notícias |
| H3 | Notícias da noite ajudam a prever o **salto da abertura** | Análise complementar |

### 3.3 Alvo
- **Alvo principal:** `alvo = 1` se o retorno da ação no **próximo pregão** for maior que o retorno do Ibovespa no mesmo pregão (ambos pelo **fechamento ajustado**). Senão, 0.
- **Alvo complementar (H3):** 1 se o salto da abertura da ação em t+1 (abertura t+1 ÷ fechamento t − 1, com preços ajustados) for maior que o do Ibovespa.
- O alvo é **calculado por nós**, não pela coleta. O último dia fica sem alvo e não entra no treino.

### 3.4 Horizonte
**Próximo pregão** (e não 30 dias). Motivos:
- O efeito da notícia é curto ("notícia é como pão quente: vale no dia").
- Em 1 ano, são ~250 avaliações diárias, contra só 12 mensais.
- Com 30 dias, as previsões de dias seguidos se sobrepõem (29 de 30 dias iguais) e enganam a estatística.
- Os prazos longos (1 mês, 6 meses, 1 ano) ficam na **Fase 1**, como fatos já acontecidos.

### 3.5 Modelos (definidos antes de rodar)
| Modelo | Variáveis | Responde |
|---|---|---|
| 1. Base | Só preço, volume e mercado | Quanto o preço sozinho explica |
| 2. + notícias do pregão | Modelo 1 + notícias do pregão | H1 |
| 3. + notícias da noite | Modelo 2 + notícias da noite | **H2 (principal)** |
| 3b. Dias de resultado | Modelo 3 só em dias com balanço divulgado à noite | O efeito é maior em dia de balanço? |

Ordem de inclusão: primeiro só os **essenciais**, depois os **complementares**, um bloco por vez, ficando só com o que melhorar de verdade. Com pouco dado, muita variável faz o modelo decorar coincidências.

### 3.6 Colunas do dataset de treinamento
(Na planilha, célula E26. "Parâmetros" é jargão errado; usar **"variáveis explicativas"** ou **"features"**. Em aprendizado de máquina, "parâmetros" são os ajustes internos do modelo.)

```
Colunas do dataset de treinamento:

Identificação (não entra no aprendizado, só organiza as linhas):
- data, ticker, setor

Variáveis explicativas (o que o modelo lê para estimar):
- Notícias: quantidade da noite, tom da noite, notícia mais forte da noite,
  mudança de tom, tom do pregão, tom do setor, tom do mercado
- Preço e volume: retorno de 1, 5 e 20 dias, volatilidade (20 dias), beta,
  distância da máxima e da mínima de 52 semanas, volume em relação ao normal,
  salto da abertura de hoje, amplitude do dia, retorno em relação ao setor
- Mercado: exposição ao dólar, exposição ao petróleo

Alvo (o gabarito que o modelo tenta acertar):
- supera o Ibovespa no próximo pregão (1 = sim, 0 = não)
```

**Definições de cálculo de cada variável** (uma linha = uma ação num pregão t):

| Variável | Fórmula / regra | Essencial? |
|---|---|---|
| Quantidade de notícias da noite | Nº de notícias com `data_hora_publicacao` entre o **fechamento da B3 em t** e as **8h de t+1** (inclui fim de semana e feriado; sexta à noite vale para segunda) | Essencial |
| Tom das notícias da noite | Média de `prob_positivo − prob_negativo` dessas notícias (−1 a +1) | Essencial |
| Notícia mais forte da noite | O score de maior valor absoluto da noite | Essencial |
| Mudança de tom | Tom da noite − tom médio da empresa nos 30 pregões anteriores | Essencial |
| Tom das notícias do pregão | Mesmo cálculo, para notícias publicadas com a bolsa aberta em t | Essencial |
| Tom do setor | Tom médio das notícias das **outras** empresas do mesmo setor | Complementar |
| Tom do mercado | Tom médio de todas as notícias da janela | Complementar |
| Retorno de 1, 5 e 20 dias | Variação do fechamento ajustado | Essencial |
| Volatilidade (20 dias) | Desvio-padrão dos 20 últimos retornos diários | Essencial |
| Beta | Inclinação dos retornos da ação contra os do Ibovespa em 252 pregões | Essencial |
| Volume em relação ao normal | Volume de t ÷ **mediana** do volume dos 20 pregões anteriores | Essencial |
| Salto da abertura de hoje | Abertura de t ÷ fechamento de t−1 − 1 (com abertura ajustada = abertura × fechamento_ajustado ÷ fechamento) | Essencial |
| Distância da máxima e da mínima de 52 semanas | Fechamento ajustado ÷ máxima (ou mínima) dos últimos 252 pregões − 1 | Complementar |
| Amplitude do dia | (Máxima − mínima) ÷ fechamento | Complementar |
| Retorno em relação ao setor | Retorno da ação − retorno médio do setor (sem a própria ação) | Complementar |
| Exposição ao dólar | Beta da ação contra o dólar (120 pregões) × variação do dólar no dia | Complementar |
| Exposição ao petróleo | Mesma ideia, com o Brent | Complementar |

- Variáveis de preço, volume e mercado entram como **rank** (percentil entre as ações do mesmo pregão, 0 a 1). Empates recebem a média das posições; vazio continua vazio (o XGBoost trata).
- **Notícia sem horário:** fica num grupo à parte ("sem horário") e não entra como "da noite". Se tiver `data_hora_coleta`, ela pelo menos limita quando a notícia saiu.
- Treino e previsão diária usam **a mesma função** de preparação (`preparacao.py`).

### 3.7 Metodologia de avaliação
- **Dados:** meta de **5 anos** de dataset (+1 ano antes, só de preços, para o beta e as 52 semanas).
- **Validação walk-forward mensal:** treina com o passado, testa no mês seguinte e avança. Embargo de 1 pregão entre treino e teste (o alvo usa t+1).
- **Conjunto de teste final usado uma única vez.**
- **Métricas:**
  1. Acerto do top 3 (quantas vezes as 3 primeiras superaram o Ibovespa) contra a **faixa do acaso** (simulação de 10 mil "escolhedores aleatórios" por dia).
  2. Retorno médio do top 3 menos o retorno do Ibovespa.
  3. **Top 3 contra os últimos 3** (a prova mais clara de que o modelo ordena bem).
  4. AUC geral e AUC médio por pregão.
  5. Intervalo de confiança por bootstrap em blocos de pregão.
  6. **Robustez por ano:** o efeito aparece em todos os anos ou só em um?
- **Com 5 anos**, a faixa do acaso do top 3 fica em cerca de ±2 pontos percentuais. Com 1 ano, fica larga demais para concluir algo.
- **Validação do FinBERT:** classificar **100 a 200 manchetes à mão** e medir quanto o FinBERT concorda. O FinBERT original (ProsusAI) é em **inglês**; se as notícias estão em português, isso precisa estar resolvido (tradução, ou um modelo em português como o FinBERT-PT-BR). O avaliador vai perguntar.
- **Viés de sobrevivência:** usar as ações que fizeram parte do Ibovespa em cada época, não só as de hoje.
- Resultado nulo também é resultado: "coerente com a hipótese de mercado eficiente".

### 3.8 Como o experimento aparece na interface
- **Tela principal (aba "Experimento"):** "Top 3 para o próximo pregão", com a **posição** (1º, 2º, 3º) e **sem %**, mais o selo **"em avaliação"**, a faixa "Experimento acadêmico (TCC): testa se as notícias ajudam a prever ações. Não é recomendação de investimento." e o **histórico**: "O top 3 superou o Ibovespa em X% das vezes (ações ao acaso: Y%)".
- **Botão "detalhes"** de cada ação: os motivos da posição (contribuições do XGBoost via `pred_contribs`, ex.: "notícias da noite: tom positivo (+0,42), 3 notícias ↑ ajudou"), as notícias usadas (manchete e link) e os fatos da Fase 1.
- **Chance em %:** só nos detalhes e **sempre ao lado da média (50%)**. Só deve ser mostrada **depois de conferida a calibração** (se o modelo diz 60%, ~60% dos casos dão certo).
- **Horário:** o top 3 é gerado **depois que a coleta das 8h termina** (o processamento verifica o painel de execuções a partir das 8h; prazo 9h45; ver 14.7), antes da abertura das 10h, e **gravado numa tabela nossa** no momento da previsão. Assim, o histórico mostra exatamente o que o modelo disse naquele dia, mesmo que os preços do passado sejam reajustados depois.
- **Resposta pronta para "Então para que isso serve?":**
  > "O sistema tem duas partes. A primeira é um painel com informações confirmadas, que servem ao investidor hoje. A segunda é o experimento do TCC: testar se o sentimento das notícias, lido pelo FinBERT, ajuda a prever as ações. O top 3 é a forma de fazer esse teste às claras: todo dia o modelo registra a aposta antes da abertura e o sistema confere depois. Não dá para escolher só os dias bons. Se não funcionar, também é resultado: mostra que o mercado absorve as notícias rápido, coerente com a teoria de mercado eficiente, e serve de alerta contra ferramentas que vendem 'sinais' sem mostrar o histórico."

---

## 4. O que já foi feito e os resultados (dados de 1 ano)

### 4.1 Dados recebidos
- `dataset_completo.csv`: 21.073 linhas, 85 tickers, 250 pregões (01/09/2025 a 31/08/2026). Colunas: data, ticker, quant_noticias, positivo, neutro, negativo, score_finbert, retorno_1d, retorno_5d, retorno_20d, volatilidade_20d, volume_relativo, retorno_ibovespa, target.
- `raw_prices.csv` (Yahoo): ticker, date, open, high, low, close, adj_close, volume. Contém 88 códigos, incluindo ^BVSP, USDBRL=X e BZ=F. A maioria começa em 18/07/2025; ^BVSP, PETR4, VALE3, ITUB4, dólar e Brent começam em 09/2024. Vai até 01/09/2026.
- O raw_prices confirmou: `retorno_1d` = variação do adj_close; `volume_relativo` antigo = volume ÷ **média** dos 20 anteriores (**decidimos trocar por mediana**).
- Problemas de dado: AZUL3 quebrada na fonte; **bonificações de AXIA3 (0,2628 PNC, ex 22/12/2025) e CYRE3 (0,18 PN, ex 02/01/2026) não ajustadas pelo Yahoo**; EMBJ3 com barra faltando em 03/11/2025. Saltos a conferir: CSAN3 em 22/09/2025 e ENEV3 em 10/02/2026.

### 4.2 Dataset v1 congelado
Ver seção 12. Em resumo: 20.311 linhas, 82 tickers, divisão cronológica treino/validação/teste com embargo, features em rank e hash SHA-256 registrado.

### 4.3 Resultados dos testes (validação walk-forward)
| Teste | Resultado |
|---|---|
| Todas as representações (brutos, ranks, z-score, misturas) | AUC ≈ 0,50 |
| Ranks contra brutos | **Mesma precisão**, mas **metade da oscilação** mensal do AUC (KS ≈ 0,01). Ranks escolhidos pela **estabilidade**, não por acerto |
| Top 3 (modelo v1) | 42,8% (77/180) contra 48,3% do acaso (faixa de 41,7% a 55,6%). 7,2% dos escolhedores aleatórios foram tão mal ou pior |
| Horizonte de 5 dias | Top 3: 45,6% |
| Prever volatilidade | Spearman 0,438 (XGBoost) contra 0,436 da regra simples (vol20): previsível, mas a regra simples basta |
| **Teste mais recente (116 pregões, jan–jun/2026, 5 sementes)** | M1 (preço + volume + gap + beta): AUC 0,495, top 3 45,1% · M2 (+ notícias do dia, mudança de tom, notícias relativas): AUC 0,502 (+0,007; IC [−0,004; +0,019]), top 3 48,0% · M4 (+ dólar e Brent): AUC 0,503, top 3 48,6% · **acaso: 47,4%** |
| Conclusão | **H1 sem ganho comprovado.** Dólar e petróleo não ajudaram. H2 bloqueada pela falta de horário nas notícias |

Hiperparâmetros usados: `n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5`.

**Como falar disso:** "o modelo ainda não mostrou vantagem sobre o acaso". Nunca "o modelo é pior que um chute": a diferença está dentro da faixa da sorte.

---

## 5. Fase 1: painel de fatos (tabela final da planilha)

Relevância por tier: **S** (mais alta) > **A** > **B**.

| Relevância | Informação | O que é? | Visualização | Cálculo? | Como calcular | O que pedir à extração | Objetivo |
|---|---|---|---|---|---|---|---|
| S | Top 3 do experimento | As 3 ações com maior chance, segundo o modelo, de superar o Ibovespa no próximo pregão | Lista do 1º ao 3º + botão “detalhes” (Com chances) + selo “em avaliação” + aviso “experimento acadêmico, não é recomendação de investimento” | Sim | Modelo XGBoost treinado com as colunas listadas em “Colunas do dataset de treinamento” | Pedidos 1 a 4 (notícias com hora, preços diários, cadastro das ações e mudanças de ticker) | Responder à pergunta do TCC: as notícias, lidas pelo FinBERT, ajudam a prever o desempenho das ações? |
| A | Histórico do experimento | Quantas vezes o top 3 superou o Ibovespa, comparado com ações escolhidas ao acaso | % (ex.: “48% das vezes · acaso 47%”) + gráfico de linha do acerto acumulado | Sim | Top 3 registrado antes da abertura de cada pregão + resultado de cada ação contra o Ibovespa no fim do dia | Pedido 2 (preços diários) | Mostrar com honestidade a confiabilidade do modelo em teste |
| S | Volume Total | Quantas ações trocaram de mão no dia | Valor (ex.: 39 milhões de ações) | Não | ---- | Volume diário de cada ação | Mostrar o tamanho do movimento do dia em números absolutos |
| S | Volume em relação ao normal | Quantas vezes o volume de hoje é maior ou menor que o habitual da ação no último mês (conta com fatos) | Valor (ex.: “3,9× o normal do último mês”) + gráfico de barras dos últimos 20 pregões | Sim | Volume de hoje ÷ mediana do volume dos 20 pregões anteriores Obs: Uso de mediana para prevenção de outliers. | Volume diário de cada ação (com pelo menos 21 pregões de histórico) | Sinalizar que “algo diferente aconteceu hoje” e levar o investidor a procurar o motivo;<br>junto com a variação do preço, indicar se o movimento foi de alta ou de queda com muita participação.<br>É a base do destaque “ações com volume fora do normal” |
| A | Grau de endividamento | Quanto a empresa deve, já descontado o dinheiro que tem em caixa, em relação ao patrimônio dos acionistas e ao quanto ela gera com a operação. Não se aplica a bancos e seguradoras (na tela: “não se aplica”). | Dois valores lado a lado, com a média do setor:<br>- “Dívida líquida/PL: 0,45 (setor: 0,60)”<br>- “Dívida líquida/EBITDA: 1,2× (setor: 1,8×)” + gráfico de linha dos dois nos últimos trimestres.<br>Abaixo, em letra menor: “Dívida líquida sem arrendamentos.” Se a dívida líquida for negativa: mostrar “Caixa líquido: R$ 12,3 bi” no lugar dos dois valores.<br>Bancos e seguradoras: “não se aplica”. | Sim | Dívida líquida = empréstimos e financiamentos (curto + longo prazo) − caixa − aplicações financeiras, do balanço mais recente.<br>Dívida líquida/PL = dívida líquida ÷ patrimônio líquido.<br>Dívida líquida/EBITDA = dívida líquida ÷ EBITDA dos últimos 12 meses | ITR e DFP de cada empresa (dados abertos da CVM), com empréstimos e financiamentos de curto e de longo prazo (incluindo debêntures), caixa e equivalentes de caixa e aplicações financeiras de cada período, além do patrimônio líquido, do EBITDA e da data de entrega (já pedidos) | Mostrar se a empresa está muito ou pouco endividada, e em quantos anos de geração de caixa ela pagaria a dívida, comparando com empresas do mesmo setor |
| A | Comparação com o Ibovespa | Quanto a ação subiu ou caiu em relação ao mercado no mesmo período (conta com fatos) | % lado a lado (ex.: “CMIG4 −11,0% · Ibovespa −7,3%”) + gráfico de linhas das duas partindo do mesmo ponto, com seletor de 1 dia, 1 mês, 6 meses e 1 ano | Sim | Variação diária da ação e do Ibovespa de todos os dias | Fechamento ajustado de todos os pregões, de cada ação e do Ibovespa, (com pelo menos 1 ano de histórico) | Mostrar se a ação está acompanhando o mercado, indo melhor ou pior |
| S | Comparação com o setor | Quanto a ação subiu ou caiu em relação às outras empresas do mesmo setor, no mesmo período | % lado a lado (ex.: “CMIG4 −11,0% · Setor elétrico −6,2% · Ibovespa −7,3%”) + linha do setor no mesmo gráfico da comparação com o Ibovespa, com seletor de 1 dia, 1 mês, 6 meses e 1 ano | Sim | Variação diária da ação e das outras ações do mesmo setor de todos os dias O setor é a média das ações que acompanhamos, sem contar a própria ação.<br>Setores com menos de 3 empresas: avisar na tela que a comparação é fraca. | Fechamento ajustado de todos os pregões de cada ação (já pedido) + cadastro das ações:<br>ação → setor (classificação da B3) | Mostrar se a ação vai bem ou mal dentro do seu ramo: “saber se o setor está bem precificado e se existem outras empresas com maiores perspectivas”, segundo o especialista |
| S | Volatilidade | O quanto o preço da ação costuma oscilar de um dia para o outro | % (ex.: “costuma variar cerca de 1,0% por dia”) + comparação com as outras ações (ex.: “mais calma que 96% das ações”) | Sim | Variação diária da ação nos últimos 20 pregões (desvio-padrão) | Fechamento ajustado de todos os pregões de cada ação | Mostrar o risco próprio da ação:<br>o quanto ela costuma “balançar” |
| A | Beta | O quanto a ação costuma se mover quando o Ibovespa se move | Valor (ex.: “0,91: move-se um pouco menos que o Ibovespa”) | Sim | Variação diária da ação e do Ibovespa no último ano (252 pregões) | Fechamento ajustado de todos os pregões, de cada ação e do Ibovespa, (com pelo menos 1 ano de histórico) | Mostrar o risco da ação em relação ao mercado, se é mais “especulativa” ou mais “defensiva” |
| A | Tom das notícias do dia | Se as notícias publicadas hoje sobre a empresa são positivas, neutras ou negativas, segundo a leitura do FinBERT | Lista das manchetes do dia, cada uma com o rótulo (positiva, neutra ou negativa) e o link + resumo do dia (ex.: “8 notícias: 5 positivas, 2 neutras, 1 negativa”) OBS: Mostrar principais manchetes do dia | Sim | Classificação de cada notícia pelo FinBERT e contagem por tom, por empresa e por dia | Cada notícia separada: manchete, data e hora, fonte, link e empresa relacionada, com o resultado do FinBERT de cada uma (probabilidade positiva, neutra e negativa) | Mostrar rapidamente o que está sendo dito sobre a empresa e deixar o investidor escolher o que ler (“pela manchete o investidor vê se tem interesse”) |
| S | P/L (preço sobre lucro) | Em quantos anos o lucro da empresa “pagaria” o preço da ação, se o lucro se mantivesse igual | Valor (ex.: “P/L 6,1”) + comparação com a média do setor (ex.: “setor: 8,4”) | Sim | Preço atual da ação ÷ lucro por ação dos últimos 12 meses (lucro líquido dos últimos 4 trimestres ÷ número de ações) | Fechamento diário de cada ação (já temos) + ITR e DFP de cada empresa (dados abertos da CVM), com o lucro líquido, o patrimônio líquido e a data de entrega de cada documento + quantidade de ações ON e PN de cada empresa, com a data de referência. | Mostrar se a ação está “cara” ou “barata” em relação ao lucro que a empresa gera, principalmente comparada com empresas do mesmo setor |
| S | P/VP (preço sobre valor patrimonial) | Quanto o mercado paga pela ação em relação ao patrimônio da empresa:<br>1 = paga exatamente o patrimônio;<br>acima de 1 = paga mais;<br>abaixo de 1 = paga menos | Valor (ex.: “P/VP 1,2”) + comparação com a média do setor (ex.: “setor: 1,5”) | Sim | Preço atual da ação ÷ valor patrimonial por ação (patrimônio líquido do balanço mais recente ÷ número total de ações) | Fechamento diário de cada ação (já temos) + ITR e DFP de cada empresa (dados abertos da CVM), com o lucro líquido, o patrimônio líquido e a data de entrega de cada documento + quantidade de ações ON e PN de cada empresa, com a data de referência. | Mostrar se o mercado está pagando caro ou barato pelo que a empresa tem, principalmente comparada com empresas do mesmo setor |
| S | Dividend yield | Quanto a ação pagou em proventos (dividendos + JCP) nos últimos 12 meses, em relação ao preço atual | % (ex.: “Yield 9,2%”) + gráfico de barras com os proventos pagos por mês ou ano | Sim | Soma dos proventos por ação com data-com nos últimos 12 meses ÷ preço atual da ação | Fechamento diário de cada ação (já temos) + proventos de cada ação: tipo (dividendo ou JCP), valor por ação, já ajustado por desdobramentos e bonificações, data-com e data de pagamento (B3) | Mostrar quanto a ação “devolve” em dinheiro ao acionista, um dos pontos que o especialista olha (“distribuição de proventos:<br>dividendos e juros de capital próprio”) |
| S | ROE (retorno sobre o patrimônio) | Quanto lucro a empresa gerou nos últimos 12 meses para cada real que pertence aos acionistas | % (ex.: “ROE 19%”) + comparação com a média do setor + gráfico de linha com o ROE dos últimos trimestres | Sim | Lucro líquido dos últimos 12 meses (4 trimestres) ÷ patrimônio líquido do balanço mais recente | ITR e DFP de cada empresa (dados abertos da CVM), com o lucro líquido, o patrimônio líquido e a data de entrega de cada documento (P/L E P/VP já contempla) | Mostrar se a empresa é eficiente em transformar o dinheiro dos acionistas em lucro, comparando com outras do mesmo setor |
| S | Cotação | Preço da ação no fechamento do pregão e quanto ele subiu ou caiu em relação ao dia anterior | Valor (ex.: “R$ 10,68”) + % do dia (ex.: “▼ −0,37%”) + gráfico de linha do preço em 1 mês, 6 meses e 1 ano | Não para o preço Sim para a variação do dia | Variação do dia: fechamento de hoje ÷ fechamento do pregão anterior − 1 (fechamento sem descontar dividendos) | Fechamento diário de cada ação, ajustado só por desdobramentos e bonificações (já temos) | Mostrar o comportamento do preço, que é “a primeira coisa” que o especialista olha |
| S | Variação do preço | Quanto o preço da ação subiu ou caiu em cada período | % por período (ex.: “Dia −0,37% · Mês −5,99% · 6 meses +4,2% · 1 ano −11,0%”) + gráfico de linha do preço | Sim | Variação diária do fechamento da ação de todos os dias, sem descontar dividendos | Fechamento diário de cada ação, ajustado só por desdobramentos e bonificações (sem descontar dividendos), com pelo menos 1 ano de histórico (já temos) | Mostrar como o preço se comportou em diferentes prazos, com destaque para o longo prazo, que o especialista valoriza |
| B | Margem bruta | Quanto sobra das vendas depois de descontar só o custo dos produtos ou serviços vendidos Não se aplica a bancos e seguradoras (ex.: ITUB4, BBDC4, BBAS3, BBSE3). Na tela: “não se aplica”. | % (ex.: “Margem bruta 32%”) + comparação com a média do setor + gráfico de linha com a margem dos últimos trimestres | Sim | Lucro bruto dos últimos 12 meses ÷ receita líquida dos últimos 12 meses (soma dos 4 trimestres mais recentes) | ITR e DFP de cada empresa (dados abertos da CVM), com receita líquida, lucro bruto, lucro líquido, patrimônio líquido e a data de entrega de cada documento. | Mostrar se a empresa ganha bem com o que vende antes das outras despesas, e se essa eficiência está melhorando ou piorando. Atende ao “acompanhamento das receitas e dos custos” citado pelo especialista |
| B | Margem líquida | Porcentagem das vendas (receita líquida) que sobra como lucro depois de descontar todos os custos, despesas, juros e impostos.<br>Não se aplica a bancos e seguradoras (ex.: ITUB4, BBDC4, BBAS3, BBSE3). Na tela: “não se aplica”. | % (ex.: “Margem líquida 12%”) + comparação com a média do setor + gráfico de linha com a margem dos últimos trimestres | Sim | Lucro líquido dos últimos 12 meses ÷ receita líquida dos últimos 12 meses (soma dos 4 trimestres mais recentes) | ITR e DFP de cada empresa (dados abertos da CVM), com a receita líquida, o lucro líquido e a data de entrega de cada documento (já pedido) | Mostrar quanto das vendas realmente vira lucro para a empresa, e se isso está melhorando ou piorando |
| S | Ebitda | Quanto a empresa gera de dinheiro com a operação, antes de juros, impostos, depreciação e amortização. Não se aplica a bancos e seguradoras (na tela: “não se aplica”). | Valor dos últimos 12 meses (ex.: “EBITDA R$ 48,2 bi”) + margem EBITDA em % (ex.: “Margem EBITDA 39%”) + comparação da margem com a média do setor + gráfico de barras por trimestre | Sim | EBITDA = lucro operacional (EBIT) + depreciação e amortização, somando os 4 trimestres mais recentes.<br>Margem EBITDA = EBITDA ÷ receita líquida dos mesmos 12 meses | ITR e DFP de cada empresa (dados abertos da CVM), com o resultado antes do resultado financeiro e dos tributos (EBIT) e a depreciação e amortização de cada período, além da receita líquida e da data de entrega (já pedidas) | Mostrar a força da operação da empresa, sem o efeito de dívidas, impostos e contabilidade, e comparar com empresas do mesmo setor pela margem |
| A | Payout | Porcentagem do lucro que a empresa distribuiu aos acionistas como dividendos e JCP | % (ex.: “Payout 60%”) + gráfico de barras com o payout dos últimos anos | Sim | Total de proventos distribuídos nos últimos 12 meses ÷ lucro líquido dos últimos 12 meses | 1. Proventos de cada ação (B3): para cada pagamento, o código da ação (ex.: CMIG3, CMIG4), o tipo (dividendo ou JCP), valor por ação já ajustado por desdobramentos e bonificações e a data-com.<br>2. Lucro líquido de cada empresa (ITR e DFP da CVM), com a data de entrega de cada documento.<br>3. Quantidade de ações de cada tipo de cada empresa (CVM): quantas ações ordinárias (ON) e quantas preferenciais (PN) existem. | Mostrar o perfil da empresa: se ela distribui a maior parte do lucro ou reinveste para crescer, que é o que interessa a quem busca renda com dividendos |
| S | Histórico de dividendos | Todos os proventos (dividendos e JCP) pagos pela ação ao longo dos anos | Gráfico de barras com o total pago por ação em cada ano (ex.: 2022 a 2026) + tabela com cada pagamento (data-com, data de pagamento, tipo e valor por ação) | Sim | Soma dos proventos por ação em cada ano | Proventos de cada ação (B3): código da ação, tipo (dividendo ou JCP), valor por ação, já ajustado por desdobramentos e bonificações, data-com e data de pagamento, com pelo menos 5 anos de histórico | Mostrar se a empresa paga proventos com regularidade e se os valores estão crescendo, caindo ou estáveis, o que interessa a quem investe pensando em renda |
| A | Comparação com índices (CDI, IPCA, IDIV, SMLL, IFIX e IVVB11) | Quanto a ação rendeu comparada a outras formas de investir e à inflação, no mesmo período | Gráfico de linhas partindo do mesmo ponto, com cada índice ligado ou desligado pela legenda + % de cada um no período, com seletor de 1 mês, 6 meses e 1 ano | Sim | Variação diária da ação e de cada índice de todos os dias.<br>CDI e IPCA vêm como taxa e precisam ser acumulados (juros sobre juros) no período | Taxa diária do CDI (Banco Central) + taxa mensal do IPCA (Banco Central/IBGE) + fechamento diário de IDIV, SMLL e IFIX (B3) + fechamento diário do IVVB11 (pedido 2), com pelo menos 1 ano de histórico | Mostrar se a ação valeu a pena comparada às alternativas:<br>renda fixa (CDI), inflação (IPCA), ações pagadoras de dividendos (IDIV), empresas menores (SMLL), fundos imobiliários (IFIX) e bolsa americana (IVVB11) |
| S | Rentabilidade | Quanto o investidor ganhou ou perdeu se tivesse comprado a ação no início do período, contando os dividendos.<br>É mostrada em 1 mês, 6 meses e 1 ano. | % em cada período, com um gráfico de linha da evolução | Sim | Fechamento ajustado da ação em todos os dias | Fechamento ajustado de todos os pregões de cada ação (com pelo menos 1 ano de histórico) (já pedido) | Mostrar o ganho real de quem tinha a ação, e não só a subida ou a queda do preço |

---

## 6. Contrato com a coleta (texto final da planilha, célula A26)

> Horários de entrega deste texto (20h e 9h) foram substituídos pela coleta única às 8h (seção 14.7).

```
**** Para montar o dataset do modelo, a coleta precisa mandar 4 coisas: ****

1. Notícias
Arquivo: noticias.csv
Cada notícia com:
- código único da notícia (id)
- data e hora da coleta
- data e hora de publicação (com fuso horário)
- empresa (ticker)
- título
- fonte e link
- resultado do FinBERT: probabilidade de positivo, neutro e negativo
Colunas: id, data_hora_publicacao, data_hora_coleta, ticker, titulo, fonte, link,
prob_positivo, prob_neutro, prob_negativo

2. Preços diários
Arquivo: precos.csv
De cada ação, do Ibovespa, do dólar (USD/BRL), do petróleo Brent e do IVVB11:
- abertura
- máxima
- mínima
- fechamento (ajustado só por desdobramentos e bonificações)
- fechamento ajustado (ajustado também por dividendos)
- volume
Colunas: data, ticker, abertura, maxima, minima, fechamento, fechamento_ajustado, volume
(Ibovespa, dólar, Brent e IVVB11 entram como tickers: IBOV, USDBRL, BRENT, IVVB11)
- Para IBOV, USDBRL e BRENT: fechamento ajustado = fechamento; volume em branco quando não existir

3. Cadastro das ações
Arquivo: cadastro.csv
- ticker, CNPJ e nome da empresa
- setor e subsetor (classificação da B3)
- tipo da ação: ON, PN ou UNIT
- nas units: quantas ações ON e quantas PN formam cada unit (ex.: KLBN11 = 1 ON + 4 PN)
Colunas: ticker, cnpj, empresa, setor, subsetor, tipo_acao, unit_qtd_on, unit_qtd_pn

4. Mudanças de ticker
Arquivo: mudancas_ticker.csv
- código antigo, código novo e data da mudança (ex.: ELET3 → AXIA3)
Colunas: ticker_antigo, ticker_novo, data_mudanca

Período
- Notícias: o mesmo período do dataset, mais 1 mês antes (para calcular a mudança de tom).
- Preços: o período do dataset mais 1 ano antes. O beta (252 pregões) e a distância da
máxima e da mínima de 52 semanas precisam de 1 ano de história.
Sem esse ano extra, os primeiros meses do dataset ficam sem esses valores.
- Ideal: 5 anos de dataset, que é o que deixa os resultados conclusivos.

**** Para o cálculo dos outros fatores descritos na tabela acima: ****

5. Balanços das empresas (ITR e DFP, da CVM)
Arquivo: balancos.csv
- CNPJ da empresa
- tipo do documento (ITR ou DFP)
- data de início e de fim do período de cada valor
(para saber se é do trimestre ou acumulado no ano)
- data de entrega de cada balanço
- receita líquida
- lucro bruto (em bancos e seguradoras, em branco)
- lucro líquido
- EBIT: resultado antes do resultado financeiro e dos tributos (em bancos e seguradoras, em branco)
- depreciação e amortização (da demonstração do fluxo de caixa; em bancos e seguradoras, em branco)
- patrimônio líquido
- empréstimos e financiamentos de curto prazo (passivo circulante, incluindo debêntures)
- empréstimos e financiamentos de longo prazo (passivo não circulante, incluindo debêntures)
- caixa e equivalentes de caixa
- aplicações financeiras (do ativo circulante)
- valores do balanço patrimonial (patrimônio, empréstimos, caixa e aplicações) são a posição
  no fim do período e se repetem nas linhas do trimestre e do acumulado
(em bancos e seguradoras, empréstimos, caixa e aplicações ficam em branco)
- sempre o balanço consolidado
- período: pelo menos 2 anos (ideal: 5 anos, igual aos proventos, para o gráfico de payout)
Colunas: cnpj, tipo_documento, data_inicio_periodo, data_fim_periodo, data_entrega,
receita_liquida, lucro_bruto, ebit, depreciacao_amortizacao, lucro_liquido, patrimonio_liquido,
emprestimos_curto_prazo, emprestimos_longo_prazo, caixa, aplicacoes_financeiras

6. Quantidade de ações
Arquivo: acoes_emitidas.csv
- CNPJ da empresa, data de referência, número de ações ON e número de ações PN
Colunas: cnpj, data_referencia, qtd_on, qtd_pn
- período: o mesmo dos balanços

7. Proventos (B3)
Arquivo: proventos.csv
- código da ação
- tipo (dividendo ou JCP)
- valor por ação, já ajustado por desdobramentos e bonificações
- data-com
- data de pagamento
- período: pelo menos 5 anos
Colunas: ticker, tipo, valor_por_acao, data_com, data_pagamento

8. Índices
Arquivo: indices.csv
- CDI diário e IPCA mensal (Banco Central)
- IDIV, SMLL e IFIX diários (B3)
- CDI e IPCA vêm como taxa em % (ex.: CDI diário 0.0551 = 0,0551% ao dia; IPCA 0.26 = 0,26% no mês); IDIV, SMLL e IFIX vêm em pontos
- no IPCA, a data é o dia 1 do mês (ex.: 2026-06-01)
- período: o mesmo dos preços
Colunas: data, indice, valor

**** Regras para "combinar" os módulos: ****
- Mesmo código de ação em todos (ex.: PETR4, sem sufixos como .SA).
- Datas no formato AAAA-MM-DD, e hora com fuso nas notícias.
- Ponto como separador decimal e codificação UTF-8.
- Valores vazios em branco, sem 0 no lugar de "não tem".
- Nomes das colunas exatamente como listados acima.
- Valores dos balanços em reais, sem escala (a CVM costuma publicar em milhares; converter para reais).
- Unidades: preços das ações em reais; USDBRL em reais por dólar; BRENT em dólares por barril;
  volume em quantidade de ações negociadas (não em reais).
- CNPJ só com números (ex.: 33000167000101).
- Todas as tabelas têm a coluna atualizado_em: data e hora (com fuso) em que a linha
  foi gravada ou corrigida pela última vez. Preenchida automaticamente pelo banco; não faz parte da chave.

**** Quais ações e como entregar: ****

Ações a coletar
- Todas as ações que fizeram parte do Ibovespa em algum momento do período
  coletado (não só as de hoje), para evitar o viés de sobrevivência.

Entrega (banco de dados)
- Cada arquivo vira uma tabela no banco, com os mesmos nomes de colunas.
- Histórico: carga inicial completa das 8 tabelas.
- Atualização diária: todo dia de pregão, até as 20h (horário de Brasília).
- Notícias: uma segunda atualização às 9h (antes da abertura das 10h),
  com as notícias publicadas durante a noite.

Como atualizar cada tabela
- Notícias, índices, mudanças de ticker e quantidade de ações: acrescentar as linhas novas.
- Preços: todo dia, conferir o fechamento ajustado do pregão anterior de cada ação.
  Se for diferente do que está no banco (houve dividendo, desdobramento ou bonificação),
  substituir o histórico completo só daquela ação; senão, só acrescentar o dia novo.
- Proventos, balanços e cadastro: acrescentar os novos e corrigir os que mudarem.

Linhas nunca podem se repetir
- Usar "upsert": se a linha já existe (mesma chave), atualiza; se não existe, cria.
- Chaves de cada tabela:
  noticias (id + ticker)
  precos (data + ticker)
  indices (data + indice)
  proventos (ticker + data_com + tipo)
  balancos (cnpj + tipo_documento + data_inicio_periodo + data_fim_periodo)
  acoes_emitidas (cnpj + data_referencia)
  cadastro (ticker)
  mudancas_ticker (ticker_antigo)
```

### 6.1 Tabela de exemplos dos 8 arquivos
Os valores são **ilustrativos**; o que vale são as colunas e os formatos. 🔑 = faz parte da chave.

| Arquivo | Coluna | Chave | O que é | Exemplo (ilustrativo) |
|---|---|---|---|---|
| noticias.csv | `id` | 🔑 | Código único da notícia | `n000123` |
|  | `ticker` | 🔑 | Ação da empresa citada | `PETR4` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T20:06:00-03:00` |
|  | `data_hora_publicacao` |  | Quando a notícia foi publicada, com fuso (em branco se não houver) | `2026-06-18T19:42:00-03:00` |
|  | `data_hora_coleta` |  | Quando a coleta pegou a notícia | `2026-06-18T20:05:00-03:00` |
|  | `titulo` |  | Manchete | `Petrobras anuncia novo campo no pré-sal` |
|  | `fonte` |  | Site de origem | `InfoMoney` |
|  | `link` |  | Endereço da notícia | `https://...` |
|  | `prob_positivo` |  | Probabilidade de tom positivo (FinBERT) | `0.81` |
|  | `prob_neutro` |  | Probabilidade de tom neutro (FinBERT) | `0.15` |
|  | `prob_negativo` |  | Probabilidade de tom negativo (FinBERT) | `0.04` |
| precos.csv | `data` | 🔑 | Dia do pregão | `2026-06-18` |
|  | `ticker` | 🔑 | Ação ou ativo (inclui IBOV, USDBRL, BRENT, IVVB11) | `PETR4` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T19:12:00-03:00` |
|  | `abertura` |  | Primeiro preço do dia | `37.12` |
|  | `maxima` |  | Maior preço do dia | `37.80` |
|  | `minima` |  | Menor preço do dia | `36.95` |
|  | `fechamento` |  | Último preço, ajustado só por desdobramentos e bonificações | `37.45` |
|  | `fechamento_ajustado` |  | Último preço, ajustado também por dividendos | `35.98` |
|  | `volume` |  | Quantidade de ações negociadas no dia | `41250300` |
| cadastro.csv | `ticker` | 🔑 | Código da ação | `KLBN11` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T19:12:00-03:00` |
|  | `cnpj` |  | CNPJ da empresa, só números | `89637490000145` |
|  | `empresa` |  | Nome da empresa | `Klabin` |
|  | `setor` |  | Setor (classificação da B3) | `Materiais Básicos` |
|  | `subsetor` |  | Subsetor (classificação da B3) | `Madeira e Papel` |
|  | `tipo_acao` |  | ON, PN ou UNIT | `UNIT` |
|  | `unit_qtd_on` |  | Ações ON em cada unit (só nas units) | `1` |
|  | `unit_qtd_pn` |  | Ações PN em cada unit (só nas units) | `4` |
| mudancas_ticker.csv | `ticker_antigo` | 🔑 | Código anterior | `ELET3` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T19:12:00-03:00` |
|  | `ticker_novo` |  | Código atual | `AXIA3` |
|  | `data_mudanca` |  | Primeiro dia com o código novo | `2025-11-10` |
| balancos.csv | `cnpj` | 🔑 | CNPJ da empresa, só números | `33000167000101` |
|  | `tipo_documento` | 🔑 | ITR (trimestre) ou DFP (ano) | `ITR` |
|  | `data_inicio_periodo` | 🔑 | Começo do período do valor | `2026-04-01` |
|  | `data_fim_periodo` | 🔑 | Fim do período do valor | `2026-06-30` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-08-07T20:30:00-03:00` |
|  | `data_entrega` |  | Quando o balanço foi entregue à CVM | `2026-08-07` |
|  | `receita_liquida` |  | Vendas, já sem impostos, em reais (sem escala) | `121500000000` |
|  | `lucro_bruto` |  | Receita menos o custo do que foi vendido, em reais (em branco em bancos e seguradoras) | `58300000000` |
|  | `ebit` |  | Resultado antes do resultado financeiro e dos tributos, em reais (em branco em bancos e seguradoras) | `38900000000` |
|  | `depreciacao_amortizacao` |  | Depreciação e amortização do período, em reais, sempre positiva (em branco em bancos e seguradoras) | `9300000000` |
|  | `lucro_liquido` |  | Lucro final, depois de tudo, em reais | `26700000000` |
|  | `patrimonio_liquido` |  | O que pertence aos acionistas no fim do período, em reais | `412000000000` |
|  | `emprestimos_curto_prazo` |  | Empréstimos, financiamentos e debêntures a pagar em até 1 ano, em reais (em branco em bancos e seguradoras) | `32100000000` |
|  | `emprestimos_longo_prazo` |  | Empréstimos, financiamentos e debêntures a pagar depois de 1 ano, em reais (em branco em bancos e seguradoras) | `198400000000` |
|  | `caixa` |  | Caixa e equivalentes de caixa no fim do período, em reais (em branco em bancos e seguradoras) | `41800000000` |
|  | `aplicacoes_financeiras` |  | Aplicações financeiras de curto prazo no fim do período, em reais (em branco em bancos e seguradoras) | `12600000000` |
| acoes_emitidas.csv | `cnpj` | 🔑 | CNPJ da empresa, só números | `33000167000101` |
|  | `data_referencia` | 🔑 | Data em que a contagem vale | `2026-06-30` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T19:12:00-03:00` |
|  | `qtd_on` |  | Número de ações ordinárias | `7442454142` |
|  | `qtd_pn` |  | Número de ações preferenciais | `5602042788` |
| proventos.csv | `ticker` | 🔑 | Ação que recebe o provento | `PETR4` |
|  | `tipo` | 🔑 | DIVIDENDO ou JCP | `JCP` |
|  | `data_com` | 🔑 | Último dia para ter a ação e receber | `2026-06-02` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T19:12:00-03:00` |
|  | `valor_por_acao` |  | Valor por ação, já ajustado por desdobramentos e bonificações | `0.4512` |
|  | `data_pagamento` |  | Quando o dinheiro cai na conta | `2026-08-20` |
| indices.csv | `data` | 🔑 | Dia (no IPCA, o dia 1 do mês) | `2026-06-18` |
|  | `indice` | 🔑 | CDI, IPCA, IDIV, SMLL ou IFIX | `CDI` |
|  | `atualizado_em` |  | Data e hora em que a linha foi gravada ou corrigida pela última vez (preenchida pelo banco) | `2026-06-18T19:12:00-03:00` |
|  | `valor` |  | CDI e IPCA: taxa em % (0.0551 = 0,0551% ao dia); IDIV, SMLL e IFIX: pontos | `0.0551` |

---

## 7. Regras de cálculo que ficam no NOSSO código

Estes cuidados não são pedidos à coleta. São regras do processamento:

| Tema | Regra |
|---|---|
| Ação → empresa | Ligar pelo `cnpj` do `cadastro`. Uma notícia da Petrobras vale para PETR3 **e** PETR4 |
| Units | P/L e P/VP da unit = preço da unit ÷ (indicador por ação × (unit_qtd_on + unit_qtd_pn)). **No payout, somar só ON e PN**, sem a unit, para não contar o provento duas vezes |
| Lucro dos 12 meses | Somar os 4 trimestres mais recentes. **4º trimestre = DFP (ano) − acumulado de 9 meses do 3º ITR**. Usar `data_inicio_periodo` e `data_fim_periodo` para separar o trimestre do acumulado. A depreciação (DFC) vem só acumulada no ITR, então calcular a diferença |
| Point-in-time | Em cada data, usar só balanços com `data_entrega` ≤ aquela data |
| Variação do preço × rentabilidade | **Cotação e variação do preço** usam `fechamento` (sem descontar dividendos). **Rentabilidade, comparação com Ibovespa e índices, volatilidade, beta e modelo** usam `fechamento_ajustado` |
| Salto da abertura | Usar a abertura ajustada (abertura × fechamento_ajustado ÷ fechamento) para o dividendo não parecer "notícia ruim" |
| Volume em relação ao normal | Dividir pela **mediana** (não pela média) dos 20 pregões **anteriores** (sem o dia) |
| Setor | Média das ações que acompanhamos, **sem a própria ação**. Setor com menos de 3 empresas: avisar "comparação fraca" |
| Bancos e seguradoras | Margem bruta, margem líquida, EBITDA e endividamento: "não se aplica" (identificar pelo setor) |
| EBITDA | EBIT + depreciação e amortização, em 12 meses, pela **definição padrão da CVM**. Na tela: "EBITDA (cálculo padrão CVM)" |
| Endividamento | Dívida líquida = empréstimos de curto + longo prazo − caixa − aplicações. **Sem arrendamentos** (avisar na tela). Se negativa: mostrar "Caixa líquido: R$ X" |
| Índices | CDI e IPCA chegam como taxa em % e precisam ser **acumulados** (juros sobre juros) no período |
| Dividend yield | Soma dos proventos com data-com nos últimos 12 meses ÷ preço atual (`fechamento`) |
| Janela das notícias da noite | Do fechamento da B3 em t até as 8h de t+1, usando os pregões do `precos` (sexta → segunda; feriados) |
| Mudança de ticker | Unir os históricos pela `mudancas_ticker` antes de qualquer cálculo |
| Checagem diária (`checar_dia`) | Avisar quando faltar ação, houver retorno acima de 30%, volume zero, preço parado ou indicador vazio |
| Checagem da 1ª entrega | Colunas certas, datas no formato, probabilidades somando 1, tickers batendo entre tabelas, buracos nos dados |

---

## 8. Decisões tomadas (resumo rápido)

1. Duas fases: painel de fatos (produto) e XGBoost + FinBERT (experimento).
2. Pergunta do TCC: as notícias, lidas pelo FinBERT, ajudam a prever? Foco nas **notícias da noite**.
3. Horizonte: **próximo pregão**. Top 3 **por posição**; o % só nos detalhes, ao lado da média e depois de calibrado.
4. Na tela: "detalhes", selo "em avaliação", aviso acadêmico e **histórico obrigatório**.
5. Ranks no lugar dos valores brutos (pela estabilidade).
6. Volume relativo pela **mediana** de 20 pregões.
7. Meta de **5 anos** de dados e **horário das notícias** (o pedido mais importante).
8. Coleta → **banco de dados** com 8 tabelas, chaves e upsert. Preços: substituir o histórico só da ação que teve evento.
9. Coleta única às **8h**; o processamento espera a etapa `entrega` da coleta terminar (painel de execuções) e gera o top 3 antes das 10h (ver 14.7).
10. Eventos (dia de balanço e fato relevante) **fora** por enquanto. Se precisar, marcar "dia de resultado" pelas palavras das manchetes.
11. Índice de Basileia: **fora** (só se sobrar tempo).
12. Petróleo e dólar mantidos como **complementares**, mesmo sem ganho no teste.

---

## 9. Pendências e decisões em aberto

| Item | Situação / recomendação |
|---|---|
| Colunas `texto_classificado` e `modelo_sentimento` em `noticias` | **Recomendado** (permite refazer o FinBERT e responde ao avaliador). Ainda não está na planilha |
| Amostra de ~100 linhas de cada tabela antes da carga completa | **Recomendado.** Ainda não está na planilha |
| "Se não for possível, usar a composição atual do Ibovespa e avisar" | Ainda não está na planilha |
| Balanços em formato "longo" (uma linha por conta da CVM) | Alternativa mais flexível, que evita pedir colunas novas a cada indicador. Vale se a coleta ainda não começou esse código |
| D2 "(Com chances)" | Sugestão: "(motivos de cada posição, notícias usadas e chance estimada ao lado da média de 50%)" |
| Relevâncias | Sugestão: Histórico do experimento = S (anda junto com o Top 3); Comparação com o Ibovespa no mesmo nível da do setor; Tom das notícias talvez S |
| Contrato **processamento → interface** | **Definido na seção 15** (pacotes JSON para uma API que grava no banco da interface). Falta a equipe da API decidir autenticação, endereço e forma de envio |
| Validação do FinBERT (100–200 manchetes à mão) | A fazer |
| Idioma das notícias × FinBERT em inglês | Confirmar com a coleta |
| Quantas notícias com horário existem por ano | Pedir à coleta (mostra se os 5 anos são viáveis) |
| Prazo do TCC | Não informado. Pedir para dividir as etapas |

---

## 10. Próximos passos: implementação

Ordem sugerida, com a dificuldade de cada parte:

| # | Etapa | Dificuldade |
|---|---|---|
| 1 | Ler as 8 tabelas e **checar a amostra** (formato, chaves, unidades, buracos) | Baixa |
| 2 | Limpeza: tickers que mudaram, bonificações, notícias sem hora, buracos | **A mais trabalhosa** (depende dos dados) |
| 3 | Painel Fase 1: cotação, variação, rentabilidade, comparações, volume, volatilidade, beta, índices | Baixa |
| 4 | Indicadores de balanço: P/L, P/VP, ROE, margens, EBITDA, endividamento, yield, payout, histórico de dividendos (point-in-time, 4º trimestre, units) | Média |
| 5 | Dataset do modelo (colunas da seção 3.6 + alvo), com a janela das notícias da noite | Média |
| 6 | Treino e avaliação: walk-forward, modelos 1/2/3/3b, acaso, bootstrap, robustez por ano | Média (o código base existe) |
| 7 | Saída para a interface conforme a seção 15 (pacotes JSON; arquivos até a API existir) + histórico do top 3 | Baixa |
| 8 | Rotina diária automática: a partir das 8h, esperar a coleta terminar (14.7), atualizar os fatos e gerar o top 3 antes das 10h | Média |

Opções de automação já discutidas: Agendador de Tarefas do Windows (PC ligado) ou **GitHub Actions** com cron (ex.: disparar às 8h em dias úteis e verificar a coleta a cada 5 minutos). Como agora a coleta grava num banco, o processamento pode rodar em qualquer servidor com acesso a ele.

**O que trazer para a sessão de implementação:** a amostra das 8 tabelas (~100 linhas cada), o acesso ou o formato do banco, a cobertura de notícias com horário por ano e o prazo do TCC.

---

## 11. Referencial teórico sugerido
- Hipótese de mercado eficiente: Fama (1970). Explica por que é difícil prever.
- Notícias e preços: Tetlock (2007), sobre o pessimismo da mídia e o mercado.
- FinBERT: Araci (2019). XGBoost: Chen e Guestrin (2016).
- Estudos brasileiros sobre sentimento de notícias e a B3; o FinBERT-PT-BR, se usado.
- Validação temporal e vazamento de dados em finanças (walk-forward, embargo).

---

## 12. Histórico técnico (dataset v1 e arquivos existentes)

### 12.1 Arquivos do pacote (`pacote_tcc.zip`)
| Arquivo | O que é |
|---|---|
| `dados/dataset_completo.csv` | Base original. Não alterar |
| `dados/dataset_tcc_v1.csv` | Base congelada (20.311 linhas, 82 tickers, 249 pregões). SHA-256 `1aa893d7ae065fe297c265f116bfed4d933f5d3f8604339d27da26ec0edb311c` |
| `dados/dataset_tcc_v1_manifesto.json` / `_exclusoes.csv` | Regras, features e divisão; as 762 linhas removidas e o motivo de cada uma |
| `scripts/gerar_dataset_v1.py` | Gera a v1 (reprodutível) |
| `scripts/auditoria_dataset.py` | Auditoria da base original |
| `scripts/preparacao.py` | `preparar_features()` (ranks por data) e `checar_dia()`. **Usar no treino e na previsão** |
| `scripts/comparar_representacoes.py` | Comparação justa brutos × ranks × z-score × misturas |
| `scripts/teste_modelos.py` | Teste M1/M2/M4 com features do raw_prices (gap, beta, volume pela mediana, dólar e Brent) |
| `scripts/horizonte_5d.py` | Modelo de 5 pregões |
| `scripts/gerar_saida_exemplo.py` + `saida_processamento_2026-06-19.json` | Exemplo de saída real (top 3 de 19/06/2026: ITSA4, CMIG4, KLBN11, com motivos) |
| PDFs | `ranks_vs_valores_brutos.pdf`, `fluxo_diario_processamento.pdf`, `resumo_modulo_processamento.pdf`, `perguntas_especialista.pdf` |
| Protótipo do painel | Artifact privado em claude.ai (dados reais de 19/06/2026) |

### 12.2 Auditoria da base original
- Sem duplicatas (data, ticker). As 250 datas são pregões da B3.
- `target` confere com `retorno_1d(t+1) > retorno_ibovespa(t+1)` em 100% das linhas verificáveis.
- `retorno_ibovespa` é do **mesmo dia t**, sem vazamento. `retorno_1d(t)` é o retorno **do dia t**.
- `retorno_5d` e `retorno_20d` são compostos nas janelas que terminam em t. `volatilidade_20d` usa ddof=1.

### 12.3 Limpeza da v1 (762 linhas)
AZUL3 inteira (158; dado quebrado), AXIA3 inteira (250) e CYRE3 inteira (250) (bonificações não ajustadas), último pregão 31/08 (82; sem alvo), AUAU3 com as 20 primeiras linhas (20; sem histórico) e EMBJ3 em 31/10 e 03/11/2025 (2; barra ausente).

### 12.4 Divisão da v1
| Conjunto | Pregões | Linhas | Período |
|---|---|---|---|
| treino | 149 | 12.111 | 01/09/2025 – 07/04/2026 |
| validação | 49 | 4.018 | 09/04/2026 – 19/06/2026 |
| teste | 49 | 4.018 | 23/06/2026 – 28/08/2026 (**nunca usado**) |
| embargo | 2 | 164 | 08/04/2026 e 22/06/2026 |

Features da v1: `rk_retorno_1d, rk_retorno_5d, rk_retorno_20d, rk_volatilidade_20d, rk_volume_relativo, quant_noticias, positivo, neutro, negativo, score_finbert`.

### 12.5 Achados da exploração (v1)
- Único sinal estável: **volatilidade** (as ações mais calmas superam o Ibovespa um pouco mais vezes).
- O sentimento de t se relaciona com o retorno do **próprio dia t** (0,08), e não com o de t+1 (0,01): **a notícia já está no preço**. Essa é a base para focar nas notícias da noite.
- A fração diária de ações que superam o Ibovespa varia de 24% a 82%: um forte "efeito do dia", imprevisível.

---

## 13. Glossário rápido
- **Rank:** posição da ação entre as do mesmo dia (0 = menor, 1 = maior).
- **Walk-forward:** treinar com o passado e testar no período seguinte, avançando no tempo.
- **Embargo:** intervalo entre treino e teste para o alvo não "vazar".
- **Faixa do acaso:** o intervalo em que caem 95% dos "escolhedores aleatórios". Ficar dentro dela = não dá para dizer que o modelo é melhor ou pior que a sorte.
- **Calibração:** se o modelo diz 60%, cerca de 60% dos casos acontecem.
- **Point-in-time:** usar só o que já era conhecido naquela data.
- **Upsert:** gravar uma linha atualizando se a chave já existe, ou criando se não existe.
- **Fechamento × fechamento ajustado:** o primeiro corrige só desdobramentos e bonificações; o segundo também desconta os dividendos.
- **ITR / DFP:** balanço trimestral / balanço anual entregues à CVM.
- **Unit:** pacote de ações (ex.: KLBN11 = 1 ON + 4 PN).

---

## 14. O banco real da coleta (conferido no código da extração em 21/10/2026)

O código da extração (repositório `extracao-dados-tcc-main`) foi lido por inteiro, junto com a sua documentação (`docs/05-entrega.md` é a referência das 8 tabelas). **Só leitura: o processamento nunca altera esse código nem as tabelas da coleta.**

### 14.1 Nomes e regras gerais
- As 8 tabelas do contrato se chamam `` `v1-noticias` ``, `` `v1-precos` ``, `` `v1-cadastro` ``, `` `v1-mudancas_ticker` ``, `` `v1-balancos` ``, `` `v1-acoes_emitidas` ``, `` `v1-proventos` `` e `` `v1-indices` ``. O hífen exige **crase** no SQL.
- Colunas e chaves batem com o contrato. **Nenhuma tem `atualizado_em`.**
- A coleta rodava uma vez por dia, às 18:30 (Brasília); **passa para as 8h** (ver 14.7). Ela regrava as 8 tabelas por upsert.
- Timestamps internos (`raw_*`) estão em **UTC**. As colunas de data e hora da `v1-noticias` vêm como **texto ISO com o fuso de São Paulo** (ex.: `2026-06-18T19:42:00-03:00`).

### 14.2 O que cada tabela realmente traz

| Tabela | Como é montada | Atenção |
|---|---|---|
| `v1-noticias` | Google News + documentos da CVM (IPE). `id` = `n` + id do `raw_articles` com 6 dígitos | `data_hora_publicacao` vazia **só** nos documentos da CVM (que têm só a data) |
| ↳ sentimento | FinBERT **por idioma**: `pt` → `lucas-leme/FinBERT-PT-BR`; `en` → `ProsusAI/finbert` (idioma detectado com py3langid). Lê o **corpo** do artigo quando existe; senão, o **título** (`staging_article_sentiment.text_source`) | Modelo e texto usados ficam em `staging_article_sentiment` (`model`, `text_source`), ligado por `raw_articles.id` |
| ↳ colunas extras | `data_publicacao`; `momento_pregao` (`antes_abertura` < 10h, `durante` 10h–17h59, `apos_fechamento` ≥ 18h, `sem_pregao`, `desconhecido`); `origem` (`google_news`, `cvm_ipe`); `papel`, `tipo_conteudo`, `evento`, `qualidade` (da **"juíza"**: Gemini **sem** busca na web classificando título + 300 caracteres) | **Não usar `momento_pregao`**: ele usa 18h fixo, e o fechamento da B3 muda ao longo do ano (conferir os horários oficiais). Calcular a nossa própria janela. O filtro da juíza está **desligado**, então entram panoramas e opiniões. `qualidade` é um número gerado por IA, e o conjunto-ouro de avaliação da juíza **não existe** |
| `v1-precos` | Yahoo. `fechamento` = close (ajustado por desdobramentos); `fechamento_ajustado` = adj_close. Ações + `IBOV`, `USDBRL`, `BRENT`, `IVVB11`. Volume zero vira vazio | **O histórico inteiro é baixado de novo a cada dia**, então o ajustado do passado se atualiza sozinho ✅. Bonificações que o Yahoo não ajusta (AXIA3, CYRE3) continuam sendo problema |
| `v1-cadastro` | B3 + CVM. `tipo_acao` também pode ser `BDR` (ex.: JBSS32). Units: KLBN11, BPAC11, ENGI11, IGTI11, SANB11, TAEE11 | CRFB3 sem CNPJ nem setor |
| `v1-mudancas_ticker` | 10 trocas fixas no código (EMBR3→EMBJ3, ELET3/ELET6→AXIA3, JBSS3→JBSS32, CPLE6→CPLE3, NTCO3→NATU3, ODPV3→SAUD3, AZUL4→AZUL3, PETZ3→AUAU3, CCRO3→MOTV3) | **`data_mudanca` vazia em todas** |
| `v1-balancos` | CVM, DRE e BPP **consolidados**; escala MIL × 1.000 ✅; só a maior versão de cada documento; trimestre e acumulado em linhas separadas ✅ | **Só preenche** receita, lucro bruto, lucro líquido e patrimônio. **`ebit`, `depreciacao_amortizacao`, `emprestimos_*`, `caixa` e `aplicacoes_financeiras` existem, mas ficam SEMPRE vazias**: o coletor só baixa as contas 3.01, 3.03, 3.09/3.11, 2.03/2.08. `data_entrega` é a da última versão (conservador, sem vazamento) |
| `v1-acoes_emitidas` | CVM (composição do capital). DFP vence ITR; maior versão | — |
| `v1-proventos` | B3. Valor já ajustado por desdobramento, bonificação e grupamento ✅. Units = soma pela composição ✅. Mesma chave → valores somados | A conferência dos fatores de ajuste ainda está pendente na coleta. Outros rótulos (rendimentos, restituição de capital) ficam de fora |
| `v1-indices` | CDI (SGS 12, % ao dia), IPCA (SGS 433, % ao mês), IDIV/SMLL/IFIX (Yahoo, fechamento) | — |

### 14.3 Tabelas que o processamento NUNCA deve usar como variável
- `staging_llm_*`, `raw_llm_runs`, `raw_llm_prompts`: **análise diária do Gemini COM busca no Google** ("direção esperada", "confiança", resumos). Para datas passadas, a busca encontra notícias posteriores e causaria **vazamento de informação futura**. Elas não alimentam a `v1-noticias` (conferido).
- `v1-painel_*`, `raw_collection_runs`: controle interno da coleta.
- `features_dataset_v1`: o dataset antigo de 14 colunas (média de volume, janela de 24 h). Só como referência histórica.

### 14.4 Tabelas auxiliares que podem ser lidas
- `raw_articles` (`lang`, `published_precision`, `published_at` em UTC), `raw_article_bodies` (texto do corpo), `staging_article_sentiment` (`model`, `text_source`) e `v1-staging_noticias_julgamento` (juíza por versão do prompt).
- `v1-raw_ipe_docs`: fatos relevantes, comunicados e avisos aos acionistas, com `data_entrega` (só a data).
- `v1-raw_b3_proventos` / `v1-raw_b3_suplemento`: eventos em ações (desdobramento, bonificação), úteis para checar ajustes.
- `v1-raw_cvm_balancos`: **não** tem todas as contas da CVM, só as 5 que a coleta usa.

### 14.5 Divergências entre o banco e o combinado (status em 21/10/2026)

| # | Divergência | Impacto | O que pedir à coleta |
|---|---|---|---|
| 1 | Balanços sem EBIT, depreciação, empréstimos, caixa e aplicações | **EBITDA e endividamento impossíveis** | Baixar também a DRE 3.05 (EBIT), o BPA (1.01.01 caixa; 1.01.02 aplicações), o BPP (2.01.04 e 2.02.01, empréstimos e financiamentos) e a DFC (depreciação e amortização, por descrição) e preencher as colunas |
| 2 | Coleta só às 18:30; **não há atualização das notícias às 9h** | O top 3 das 9h30 não vê as notícias da madrugada | Um segundo disparo pela manhã (~9h) só de notícias: coleta, corpo, FinBERT e `v1-noticias` |
| 3 | `DATA_START=2025-09-01` (~1 ano). Ir para 5 anos é "decisão pendente do autor" na coleta. A documentação fala em ~2 anos de histórico de notícias no Google News | A meta de 5 anos pode não ser viável para as **notícias** | Testar a cobertura de notícias em 2021–2022 antes de decidir; separar o início dos preços do início das notícias |
| 4 | Universo = Ibovespa atual + 3 deslistadas (as datas de entrada e saída estão em TODO) | Viés de sobrevivência continua | Levantar a composição histórica do Ibovespa, ou registrar como limitação no TCC |
| 5 | `data_mudanca` vazia | Sem saber quando o código mudou | Preencher pelas datas dos avisos da B3 |
| 6 | `momento_pregao` com fechamento fixo às 18h | Classificação errada nos meses em que a B3 fecha mais cedo | Nada: o processamento calcula a própria janela |
| 7 | Filtro da juíza desligado; sem conjunto-ouro | Panoramas e opiniões entram nas notícias | Decidir se o modelo filtra por `papel`/`tipo_conteudo` (com a ressalva de que é classificação por IA, ainda não avaliada) |
| 8 | Sem `atualizado_em` | Só auditoria | Acrescentar ou tirar do contrato |

**Responsáveis:** os itens 1 a 5 são da coleta. O 6 é nosso. O 7 é decisão do grupo. O 8 é opcional.

### 14.6 Decisões de 21/10/2026 sobre as divergências
- **Itens 1, 2 e 3: a coleta vai corrigir.** O processamento é implementado **já contando com isso**:
  - EBITDA e endividamento são implementados e testados com dados de teste. Enquanto as colunas vierem vazias, a tela mostra "dado ainda não disponível" (nunca 0) e a validação com dados reais acontece quando a coleta entregar.
  - Resolvido em 14.7: coleta única às 8h, com o processamento esperando a coleta terminar.
  - **O modelo NÃO é treinado para valer até o histórico completo chegar.** Toda a parte de treino e avaliação é implementada e testada com o 1 ano atual só para conferir se o código funciona (os resultados desse teste não valem como conclusão).
- **Item 4 (viés de sobrevivência)** e **item 5 (`data_mudanca`)**: explicados ao usuário; aguardam a coleta. Se não forem resolvidos, entram como limitação no TCC.

### 14.7 Horário da coleta e gatilho do processamento (combinado em 21/10/2026)
- A coleta passa a rodar **uma vez por dia, às 8h** (Brasília), no lugar das 18:30. Ela traz o fechamento do pregão anterior e as notícias até ~8h.
- **Janela das "notícias da noite" = do fechamento da B3 em t até as 8h de t+1**, no treino e ao vivo (corte fixo às 8h; substitui o "até as 9h" das seções anteriores).
- **Gatilho do processamento:** a partir das 8h, a cada ~5 minutos, consultar o painel de execuções da coleta:
  1. Achar o daily do dia em `` `v1-painel_execucoes` `` (`tipo = 'daily'`, o mais recente com `iniciada_em` no dia de hoje). **`iniciada_em` está em UTC**: converter para São Paulo antes de comparar a data.
  2. Em `` `v1-painel_etapas` `` (ligada por `execucao_id`), esperar **`etapa_id = 'entrega'` com `status = 'concluida'`**. É ela que grava as 8 tabelas. **Não esperar o daily inteiro**: a última etapa (`analise`, Gemini) roda depois da entrega e não interessa ao processamento, e sua falha deixa o daily `parcial` mesmo com os dados completos.
  3. Conferir também se `precos`, `noticias` e `enriquecimento` (FinBERT) terminaram como `concluida`. Se alguma falhou, rodar mesmo assim, mas com aviso.
  4. **Prazo limite: 9h45.** Se a entrega não tiver terminado, gerar o top 3 com os dados disponíveis e marcá-lo com aviso, ou não gerar no dia (decisão a registrar).
  5. O top 3 é gravado com o horário de geração. **Se for gerado depois das 10h (abertura), não conta no histórico do experimento.**
- Etapas do daily da coleta, em ordem: `precos`, `macro`, `noticias`, `ipe`, `enriquecimento`, `juiza`, `cadastro`, `entrega`, `analise`. Status de etapa: `pendente`, `em_andamento`, `concluida`, `falhou`, `pulada`.

### 14.8 Universo de ações por data (viés de sobrevivência)
- Pedido feito à coleta (21/10/2026): tabela `` `v1-composicao_ibov` `` (`ticker`, `data_inicio`, `data_fim` vazio se ainda está no índice; chave `ticker` + `data_inicio`), a partir das carteiras teóricas da B3, mais a coleta de preços e notícias das ações que saíram do índice.
- **Implementar já, sem esperar:** uma única função de universo por data.
  - Se `v1-composicao_ibov` existir e tiver linhas: em cada pregão, só entram as ações com `data_inicio ≤ data` e (`data_fim` vazio ou `data_fim ≥ data`).
  - Senão: usar todos os tickers de ações do `v1-cadastro` (composição atual) e marcar o dataset e o histórico com `universo = 'composicao_atual'`.
- O filtro vale para o **modelo** e para o **histórico do experimento** (cálculo do acaso). O painel de fatos não depende dele.
- Se a composição histórica não vier: declarar a limitação no TCC e fazer a **análise de sensibilidade** (comparar o acerto do top 3 e o AUC do último ano com os dos anos anteriores). Nota na aba do experimento: "Histórico calculado com as ações que compõem o Ibovespa atualmente."

### 14.9 Camada de leitura: pronta para nomes e formatos diferentes
Regra de arquitetura: **o resto do código nunca lê o banco direto.** Toda leitura passa por um único módulo de leitura (ex.: `processamento/fontes.py`), que entrega DataFrames sempre no formato **padrão do contrato** (seção 6).

1. **Mapa de nomes num arquivo de configuração** (ex.: `config/fontes.yaml`): para cada tabela, o nome real no banco e o "de → para" de cada coluna. Se a coleta entregar `` `v1-composicao_ibovespa` `` com `entrada`/`saida` no lugar de `data_inicio`/`data_fim`, muda-se só esse arquivo, e nenhuma linha de cálculo.
2. **Validação na leitura**, com erro claro: tabela existe? colunas obrigatórias presentes? tipos e formatos (datas, números, ISO com fuso nas notícias)? chave sem duplicatas? Se falhar, **parar com uma mensagem legível** ("tabela X sem a coluna Y"), nunca seguir com dado errado.
3. **Conversores para formatos alternativos conhecidos.** Para a composição do Ibovespa, aceitar:
   - **intervalos** (`ticker`, `data_inicio`, `data_fim`): o formato pedido;
   - **fotos das carteiras** (`data_carteira`, `ticker`, com uma linha por ação em cada carteira): converter para intervalos (a ação entra na primeira carteira em que aparece e sai na primeira em que deixa de aparecer);
   - **colunas no cadastro** (ex.: `data_entrada`/`data_saida` em `v1-cadastro`): converter para intervalos.
   Os três viram o mesmo formato interno antes de qualquer uso.
4. **Teste para cada conversor**, com exemplos pequenos de cada formato.
5. Quando algo novo chegar diferente do previsto: escrever o conversor e o teste, ajustar o mapa e registrar a mudança nesta seção.

---

## 15. Contrato de SAÍDA: processamento → API → banco da interface (definido em 21/10/2026)

**Arquitetura:** o processamento calcula tudo e envia **pacotes JSON** para uma **API** (a ser construída depois, junto com o banco da interface). A API grava num **banco próprio da interface**, que a tela consulta. O processamento **não** grava no banco da coleta nem no da interface diretamente: só envia à API.

Enquanto a API não existe, o processamento **gera os mesmos pacotes como arquivos JSON** numa pasta (ex.: `saida/AAAA-MM-DD/`). Trocar o "gravar arquivo" pelo "enviar à API" deve ser a única mudança depois.

### 15.1 Convenções (valem para todos os pacotes)
| Regra | Definição |
|---|---|
| Formato | JSON, UTF-8 |
| Versão | Todo pacote tem `versao_contrato` (começa em `"1.0"`). Mudou um campo → sobe a versão |
| Datas | `AAAA-MM-DD`; data e hora em ISO com fuso de São Paulo (`2026-06-19T09:12:00-03:00`) |
| Ticker | Sem `.SA` (ex.: `PETR4`); o Ibovespa é `IBOV` |
| Percentuais | **Fração decimal**: `0.0123` = 1,23%. A interface formata |
| Dinheiro | Reais, sem escala (`48200000000` = R$ 48,2 bi). A interface abrevia |
| Ausência | Valor `null` **sempre acompanhado de `status`** (nunca 0 no lugar de vazio) |
| `status` de cada indicador | `ok` · `nao_se_aplica` (ex.: margem de banco) · `indisponivel` (dado ainda não veio da coleta, ex.: EBITDA hoje) · `historico_insuficiente` (ex.: beta com menos de 252 pregões) |
| Textos prontos | Opcionais, em campos `texto` (ex.: `"mais calma que 96% das ações"`). O número sempre vem junto; a interface pode usar um ou outro |
| Chave de gravação | Cada pacote declara a chave (`data_referencia` + `ticker` etc.). A API grava por **upsert**: reenviar substitui, nunca duplica |
| Metadados | Todo pacote tem `gerado_em` e `dados_ate` (até quando os dados da coleta vão) |

### 15.2 Os pacotes

| # | Pacote | Uma unidade por | Chave | Quando é enviado | Alimenta na tela |
|---|---|---|---|---|---|
| 1 | `acoes` | ação | `ticker` | Quando muda (cadastro) | Nome, setor, tipo de ação, busca |
| 2 | `mercado_dia` | dia | `data_referencia` | Todo dia | Faixa do mercado: Ibovespa, dólar, Brent, CDI |
| 3 | `resumo_acao` | ação × dia | `data_referencia` + `ticker` | Todo dia | O card da ação: todos os indicadores da Fase 1 (valor atual) |
| 4 | `series_diarias` | ação (ou índice) × dia | `ticker` + `data` | Todo dia (dia novo); **reenvio da série inteira** da ação que teve dividendo, desdobramento ou bonificação (o ajustado do passado muda) | Gráficos de preço, rentabilidade, comparação com Ibovespa, setor e índices, volume |
| 5 | `fundamentos_trimestrais` | ação × trimestre | `ticker` + `data_fim_periodo` | Quando sai balanço novo | Gráficos de margens, ROE, EBITDA, endividamento |
| 6 | `proventos` | provento | `ticker` + `tipo` + `data_com` | Quando há provento novo | Histórico de dividendos (tabela e barras por ano) |
| 7 | `noticias_dia` | ação × dia | `data_referencia` + `ticker` | Todo dia | Manchetes com rótulo e resumo do tom |
| 8 | `experimento_top3` | dia | `data_referencia` | Todo dia, **antes das 10h** | Aba Experimento: o top 3 e os "detalhes" |
| 9 | `experimento_historico` | dia (+ resumo) | `data_referencia` | Todo dia (o resultado do dia anterior só se conhece depois do fechamento) | Histórico de acertos × acaso |
| 10 | `execucao` | rodada | `data_referencia` + `rodada` | Ao fim de cada rodada | Status do sistema e avisos ("dados de hoje incompletos") |

### 15.3 Campos de cada pacote

**1. `acoes`:** `ticker`, `empresa`, `setor`, `subsetor`, `tipo_acao` (ON, PN, UNIT, BDR), `ativo_no_universo` (bool).

**2. `mercado_dia`:** `data_referencia`, e para `IBOV`, `USDBRL`, `BRENT`: `fechamento`, `variacao_dia`; `cdi_dia` (fração ao dia); `ipca_12m`.

**3. `resumo_acao`** (um objeto por indicador, sempre com `valor`, `status` e, quando faz sentido, `setor`, `posicao_pct` e `texto`):
- `cotacao`: `fechamento`, `variacao_dia`
- `variacao_preco`: `d1`, `m1`, `m6`, `a1` (sem dividendos)
- `rentabilidade`: `d1`, `m1`, `m6`, `a1` (com dividendos) + as mesmas janelas do `IBOV` e do setor (`ibov`, `setor`), para a comparação lado a lado com seletor de 1 dia, 1 mês, 6 meses e 1 ano
- `volume`: `total`, `relativo` (÷ mediana de 20), `mediana_20` (para a linha de referência do gráfico de barras), `posicao_pct`
- `volatilidade_20d`: `valor` (desvio diário), `posicao_pct` (fração de ações mais calmas)
- `beta`: `valor`, `status`
- `pl`, `pvp`, `roe`, `dividend_yield`, `payout`, `margem_bruta`, `margem_liquida`: `valor`, `setor` (média do setor sem a própria ação), `status`
- `payout_por_ano`: lista (`ano`, `valor`, `status`) dos últimos anos, para o gráfico de barras do payout
- `ebitda`: `valor_12m`, `margem`, `setor_margem`, `status`
- `endividamento`: `divida_liquida`, `dl_pl`, `dl_ebitda`, `caixa_liquido` (bool), `setor_dl_pl`, `setor_dl_ebitda`, `status`
- `setor_comparacao_fraca` (bool: setor com menos de 3 empresas)
- `balanco_referencia`: `data_fim_periodo` e `data_entrega` do balanço usado

**4. `series_diarias`:** `ticker`, `data`, `fechamento` (sem dividendos), `indice_retorno_total` (base 100 no início da série, com dividendos), `volume`. Também para `IBOV`, para cada setor (`SETOR:<nome>`, média de todas as ações do setor; **no gráfico, a linha do setor inclui a própria ação**, diferente dos valores do `resumo_acao`, que a excluem; diferença pequena, registrada como decisão) e para os índices (`CDI`, `IPCA`, `IDIV`, `SMLL`, `IFIX`, `IVVB11`), em base 100 acumulada. **A interface recorta o período e "parte do mesmo ponto" dividindo pelo primeiro valor do recorte.** Campo `substituir_serie: true` quando a série inteira da ação está sendo reenviada.

**5. `fundamentos_trimestrais`:** `ticker`, `data_fim_periodo`, `data_entrega`, `receita_trimestre`, `receita_12m`, `lucro_liquido_trimestre`, `lucro_liquido_12m`, `margem_bruta`, `margem_liquida`, `roe`, `ebitda_trimestre` (para o gráfico de barras por trimestre), `ebitda_12m`, `margem_ebitda`, `divida_liquida`, `dl_pl`, `dl_ebitda`, `payout_12m`, cada um com `status`. Margens, ROE e payout são sempre de 12 meses.

**6. `proventos`:** `ticker`, `tipo` (DIVIDENDO, JCP), `data_com`, `data_pagamento`, `valor_por_acao`. A soma por ano a interface faz (ou vem pronta em `resumo_acao`).

**7. `noticias_dia`:** `data_referencia`, `ticker`, `resumo` (`quantidade`, `positivas`, `neutras`, `negativas`, `tom_medio`) e `itens` (lista: `id`, `titulo`, `fonte`, `link`, `publicado_em`, `rotulo` = maior das 3 probabilidades, `prob_positivo`, `prob_neutro`, `prob_negativo`, `janela` = `pregao` / `noite` / `sem_horario`, `destaque` = ordem para "principais manchetes"). Critério do `destaque`: primeiro as notícias em que a empresa é protagonista (juíza: `papel = protagonista`, quando houver), depois a força do tom (\|positivo − negativo\|) e por fim a mais recente.

**8. `experimento_top3`:**
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
  "top3": [
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

**9. `experimento_historico`:** por dia: `data_referencia`, `top3` (tickers), `resultado` (para cada um: `retorno`, `retorno_ibov`, `superou`), `acertos_dia` (0 a 3). E um resumo: `periodo_inicio`, `periodo_fim`, `n_dias`, `taxa_acerto`, `acaso_media`, `acaso_faixa` (`[min, max]` de 95%), `universo`, `nota` (ex.: "Histórico calculado com as ações que compõem o Ibovespa atualmente.").

**10. `execucao`:** `data_referencia`, `rodada`, `inicio`, `fim`, `status` (`ok`, `parcial`, `falhou`), `coleta_status` (o que se leu do painel da coleta), `pacotes_enviados`, `avisos` (lista de textos).

### 15.4 Cobertura da planilha (conferida item a item)
Todas as 23 informações da planilha (seção 5) têm origem num pacote: Top 3 e detalhes → `experimento_top3` (+ `resumo_acao` e `noticias_dia`); Histórico do experimento → `experimento_historico`; Volume total, volume relativo, volatilidade, beta, cotação, variação do preço, rentabilidade, P/L, P/VP, ROE, yield, payout, margens, EBITDA e endividamento (valor atual) → `resumo_acao`; comparação com Ibovespa, setor e índices, gráficos de preço, rentabilidade e volume → `series_diarias` (+ `resumo_acao` para os % de cada período); gráficos trimestrais de margens, ROE, EBITDA e endividamento → `fundamentos_trimestrais`; gráfico do payout por ano → `resumo_acao.payout_por_ano`; dividend yield (barras) e histórico de dividendos → `proventos`; tom das notícias → `noticias_dia`.

### 15.5 Ordem diária de envio
1. `execucao` (início) → 2. `acoes` (se mudou) → 3. `series_diarias` → 4. `mercado_dia` → 5. `resumo_acao` → 6. `fundamentos_trimestrais` e `proventos` (se mudaram) → 7. `noticias_dia` → 8. `experimento_historico` (fecha o dia anterior) → 9. `experimento_top3` (antes das 10h) → 10. `execucao` (fim).

### 15.6 O que fica para a equipe da API e do banco decidir
- Autenticação, endereço e se o envio é um pacote por chamada ou em lote.
- Como o banco da interface guarda cada pacote (pode ser uma tabela por pacote, com a mesma chave).
- O processamento só garante: **mesmo formato, mesma chave e reenvio seguro (upsert)**.
