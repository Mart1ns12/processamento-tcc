# Protocolo de teste de variáveis novas

Registrado em 02/11/2026, **antes de rodar qualquer teste**. Depois da primeira rodada, as regras abaixo não mudam. Qualquer alteração vira uma tentativa nova, contada e relatada.

## 1. Escopo

- **Objetivo:** decidir se variáveis novas melhoram a previsão de quem supera o Ibovespa no pregão seguinte.
- **A comparação do TCC não muda:** continua sendo o **modelo 3 × modelo 1, com as notícias atuais** (seção 7.4 da especificação). O bloco E é uma versão separada e não substitui o modelo 3 nessa comparação.
- **Período:** só o desenvolvimento (de 01/2021 até antes de 23/06/2026, menos o pregão de embargo). `treino.teste_final.fim` e `liberado` não são alterados.
- **Situação:** exploratório enquanto `treino.modelo_oficial` for `false`. Nenhum número vale como conclusão do TCC antes disso.

## 2. Blocos

| Bloco | Variáveis | Base de comparação |
|---|---|---|
| A. Preço | `posicao_fechamento`, `mom_12_1`, `liquidez_20d`, `ret_idio_5d` | Modelo 1 |
| B. Contexto | `momento_setor_5d`, `exposicao_small` | Modelo 1 |
| C. Balanço | `dias_desde_resultado`, `var_lucro_aa` | Modelo 1 |
| D. Valor | `dy_12m` | Modelo 1 |
| E. Notícias | `fato_relevante_cvm` | Modelo 3, como versão separada |
| Controle | `controle_sorteado` (valor sorteado dentro de cada pregão, semente fixa) | Modelo 1 |

**Fora por enquanto:** `pvp`, que depende do erro ações × preço (seção 10 da especificação), e `tom_evento_firme`, que depende da avaliação da juíza. Se voltarem, contam como blocos novos.

**Base de comparação:** o modelo 1 e o modelo 3 depois da seleção atual dos blocos `preco_contexto`, `macro` e `noticias_contexto` (decisão F6), com os hiperparâmetros do ponto de partida (seção 7.4). As colunas novas não entram nesses modelos por padrão.

## 3. Critérios de adoção

Um bloco só é aprovado se cumprir **todos** os critérios que se aplicam a ele.

| # | Critério | Limite | Vale para |
|---|---|---|---|
| 1 | Ganho de AUC médio por pregão | Maior que +0,005 | Todos |
| 2 | Intervalo do ganho (pareado, bootstrap circular em blocos de 5 pregões, 2000 reamostragens) | IC de 99% acima de 0, para compensar os 5 testes | Todos |
| 3 | Robustez por ano | Ganho positivo em pelo menos 4 dos 6 anos, e nenhum ano abaixo de −0,005 | Todos |
| 4 | Top 5 | Taxa de acerto não cai mais que 0,5 ponto percentual | Todos |
| 5 | Dependência de regime | Ganho positivo também em 2023–2024, período sem `wordpress` | Bloco E |

**Critério 5 no bloco E:** `fato_relevante_cvm` fica vazio em 2023, então esse critério mede só os pregões de 2024. O ganho de 2023 aparece no relatório, mas não decide: nesse ano a variável não existe, e o valor seria só ruído.

**Controle:** o `controle_sorteado` passa pelos critérios 1 a 4 e **não pode ser aprovado**. Se for, a rodada é considerada inválida: nenhum bloco é adotado e o fato é relatado para investigar a causa.

## 4. Ordem de execução

1. Regenerar o dataset, com a `versao_preparacao` atual.
2. Rodar a seleção atual dos blocos para definir a base.
3. Testar o controle e cada bloco **sozinho** contra a sua base, nas mesmas linhas e nas mesmas dobras (walk-forward mensal, embargo de 1 pregão), com hiperparâmetros fixos.
4. Testar juntos os blocos A a D aprovados, repetindo os critérios 1 a 4. Se falharem, fica só o aprovado de maior ganho de AUC.
5. Congelar o conjunto aprovado.
6. Só depois disso rodar a busca pelo melhor modelo (seção 6).
7. No fim, rodar o teste final, de **uso único**, com a configuração congelada.

## 5. Regras de relato

- **Relatar todas as tentativas**, inclusive blocos reprovados e rodadas inválidas, com os 5 critérios de cada uma.
- Bloco reprovado fica de fora. Mudar a fórmula conta como bloco novo e entra na contagem de testes do relatório.
- Mudar um limite depois de ver um resultado invalida a rodada.
- Nenhum dado a partir de 23/06/2026 é olhado para escolher variáveis ou modelo.

## 6. Busca pelo melhor modelo

**Implementado em `processamento/experimento/busca*.py`; ainda não rodado.** Comando: `python -m processamento.experimento.busca_execucao --data AAAA-MM-DD --congelado docs/protocolo_congelado_rodada_NNN.json --motivo "..."`. Vale só depois de uma rodada válida do protocolo, só no desenvolvimento, com o conjunto de colunas congelado e sem o bloco E. Mudar esta seção ou os limites depois da primeira busca completa invalida a rodada, e ela não gera configuração final.

**Candidatos, do mais simples para o mais complexo:**

| Ordem | Modelo | Papel |
|---|---|---|
| 0 | XGBoost do ponto de partida (`max_depth` 3, `min_child_weight` 50) | Referência: fica se ninguém passar |
| 1 | Regressão logística (C = 1) | Candidato |
| 2 a 4 | XGBoost: 2/200, 2/50, 3/200 | Candidatos |
| 5 a 8 | LightGBM, mesmos parâmetros: 2/200, 2/50, 3/200, 3/50 | Candidatos |
| 9 | Média dos ranks por pregão dos modelos 0, 8 e 1 | Só relato: não pode vencer |

A grade continua com as 4 combinações de `max_depth` {2, 3} × `min_child_weight` {50, 200}. O número de árvores e a taxa de aprendizado ficam fixos. A combinação não pode vencer porque não tem probabilidade calibrável nem motivos únicos, e exigiria 3 retreinos por mês. Se passar, é um achado relatado.

**Quando um candidato é aprovado.** Todos os itens, contra a referência, nas mesmas dobras e linhas, usando as colunas do modelo 3:

| # | Critério | Limite |
|---|---|---|
| 1 | Ganho de AUC médio por pregão | Maior que +0,005 |
| 2 | Intervalo do ganho (pareado, bootstrap circular em blocos de 5 pregões, 10 mil reamostragens) | IC de 99,5% acima de 0, para compensar até 10 comparações |
| 3 | Robustez por ano | Ganho positivo em pelo menos 4 dos 6 anos, e nenhum ano abaixo de −0,005 |
| 4 | Top 5 | Taxa de acerto não cai mais que 0,5 ponto percentual |

**Como sai o vencedor:**

1. Nenhum aprovado: fica a referência.
2. Com aprovados: "melhor" é o de maior ganho. Vence o mais simples entre os aprovados cuja diferença para o melhor não é clara (IC de 99,5% da diferença tocando ou cruzando 0).
3. O modelo 1 não influencia a escolha. As referências da seção 7.5 da especificação são relatadas e não mudam o vencedor.

**Efeito da escolha:**

- A comparação do TCC continua sendo modelo 3 × modelo 1, sempre com a mesma família e os mesmos hiperparâmetros nos dois.
- As referências continuam sendo o acaso, a regra da volatilidade e a regressão logística. O modelo escolhido só "ganha" se superar as três. Se a logística vencer, o XGBoost do ponto de partida passa a ser a terceira referência.
- Esta regra substitui a da decisão F7 (maior AUC da grade) quando o treino recebe `--configuracao` com a configuração final. Sem essa opção, o treino continua como antes.
- Top 5 ao vivo, motivos, calibração e arquivos em `modelos/`: sem mudança se o vencedor for XGBoost. Se não for, nada entra em produção antes de ajustar o código e a especificação, e isso é registrado.
- Relatam-se todos os candidatos, inclusive os reprovados. O teste final continua de uso único, no fim, com a configuração congelada.

**Tempo estimado:** a soma de 10 walk-forwards, acaso e avaliação dá de ~22 a ~35 minutos, conforme o número de colunas.

## 7. Executor do protocolo

**Implementado em `processamento/experimento/protocolo*.py`; ainda não rodado.** Comando: `python -m processamento.experimento.protocolo_execucao --data AAAA-MM-DD --motivo "1ª rodada"`. Ele faz, nesta ordem, nas mesmas dobras e linhas e com os hiperparâmetros do ponto de partida:

1. Seleção atual dos blocos `preco_contexto`, `macro` e `noticias_contexto`, sem grade, para definir as bases.
2. Controle e blocos A a E, cada um sozinho contra a sua base.
3. Teste conjunto dos blocos A a D aprovados, se forem 2 ou mais.
4. Aplicação automática dos critérios, decisão e relatório.

**Travas: o executor recusa rodar, sem gravar nada, quando:**

- o início do teste final é depois de 23/06/2026, ou o teste final já foi usado;
- o dataset é de outra `versao_preparacao` ou tem sha256 diferente;
- os anos das dobras não são de 2021 a 2026, ou uma coluna nova está toda vazia;
- o registro de tentativas foi adulterado.

Ele só lê o período de desenvolvimento, não abre o teste final e não grava em `modelos/`.

**Como os critérios são aplicados:**

| Ponto | Regra |
|---|---|
| Comparação com limite | Sem arredondar. Ganho igual a 0,005 reprova; IC tocando 0 reprova; ano em −0,005 exato passa; ano em −0,0051 reprova |
| Top 5 | Conta exata de acertos. Queda de exatamente 0,5 ponto passa |
| Anos | O ano é o da data do pregão. 2021 (abril a dezembro) e 2026 (janeiro a junho) contam como anos normais, sem peso: são sempre 6 anos. Ganho igual a zero não conta como positivo |
| Critério 5 | Média do ganho nos pregões de 2024; o relatório mostra 2023 só para constar |
| Bloco E | Testado uma vez contra o modelo 3 da seleção atual, sem A a D. Aprovado, vira versão separada, fora da comparação do TCC |
| Modelo 3 | Os blocos A a D adotados entram no modelo 1 e são herdados pelo modelo 3 (decisão F6) |
| `noticias_dia_extremo` em rank | Não é testada pelo executor; a base usa a coluna atual |
| Teste conjunto | Com 0 ou 1 bloco aprovado, não se aplica. Com 2 ou mais e falha, fica só o de maior ganho; no empate, o primeiro na ordem A a D |
| Controle aprovado | Rodada inválida: nenhum bloco adotado, nada congelado, o conjunto não roda, e tudo é relatado |
| Contagem de testes | O IC de 99% fica fixo; o relatório mostra quantos testes foram feitos |

**Registro de tentativas:** `docs/protocolo_tentativas.jsonl`, só com acréscimo e encadeado por hash.

- A abertura é gravada antes de treinar, então rodadas interrompidas aparecem.
- Da segunda rodada em diante é obrigatório informar o motivo.
- Rodada com as mesmas entradas fica marcada como repetição e o resultado é conferido.
- Mudar as seções 3 a 5 ou os limites depois da primeira rodada completa invalida a rodada.
- Vale a última rodada válida. Todas continuam no relatório, e o registro deve ser versionado no git após cada rodada.

**Relatório:** `docs/protocolo_rodada_NNN.md`, nunca sobrescrito. Traz o sha256 do dataset, o hash dos parâmetros, das regras e do código, a semente e as versões. Traz também os critérios de todos os testes, o ganho por ano, a cobertura das colunas novas, a decisão e todas as tentativas anteriores. Rodada válida gera também `docs/protocolo_congelado_rodada_NNN.json`.

**Determinismo:** semente única e uma só thread. As mesmas entradas têm de dar o mesmo resultado; se não derem, o relatório avisa em destaque.

**Tempo estimado:** até 12 walk-forwards de XGBoost, de ~30 a ~48 minutos, conforme o número de colunas.

**Conferências de zeros falsos (só leitura, 02/11/2026; universo aproximado):**

| Conferência | Resultado |
|---|---|
| CNPJs de `v1-raw_ipe_docs` | Todos válidos e no cadastro |
| Empresa × ano coberto no universo, sem nenhum documento | 0 casos em 82.489 linhas |
| Ticker do universo sem nenhum provento | 0 casos em 98.934 linhas |
| Reapresentações de Fato Relevante | 197 de 3.487; 60 sem original (mesma referência ou até 10 dias antes). **Corrigido:** contam como evento na própria `data_entrega`, se entregues até 10 dias depois da referência (58 das 60) |
| JBS | `v1-precos` tem JBSS3 de 30/12/2019 a 06/06/2025 e JBSS32 de 09/06/2025 em diante; nenhum provento dos dois códigos; documentos da CVM só desde 2025. **Decidido (02/11/2026): a JBS fica fora do universo por exclusão explícita em `exclusoes.yaml`**; dy_12m e fato_relevante_cvm seriam zeros falsos. Volta quando a coleta trouxer proventos, balanços e documentos da CVM do período. Limitação do TCC (seção 3.4 da especificação) |

## 8. Situação após a rodada 1 e análises exploratórias

Registrado em 02/11/2026, **antes de rodar a sensibilidade**. Esta seção é registro: não muda as seções 1 a 7, os critérios, os limites nem a configuração congelada.

**Situação.** O protocolo e a busca foram rodados (as seções 6 e 7 foram escritas antes disso). Protocolo: bloco A adotado; B, C, D, E e o controle reprovados. Busca: venceu a regressão logística. Cada um foi repetido com as mesmas entradas e reproduziu o `sha_resultado` (protocolo `07544273dffe`, busca `777c527b54d9`). Pela seção 6, nada entra em produção antes de ajustar o código e a especificação para a logística: isso está pendente.

**Análises de sensibilidade de modelo 3 × modelo 1.** São exploratórias, relatadas à parte em `docs/busca_rodada_001_sensibilidade.md`, sem mudar a hipótese, a configuração congelada, a escolha do modelo nem o teste final. Ficam fora de `docs/protocolo_tentativas.jsonl` e da contagem de testes do protocolo, e os IC não têm ajuste por comparações múltiplas. Família logística, colunas de `docs/protocolo_congelado_rodada_001.json`, mesmas dobras e semente, só no desenvolvimento:

| Caso | Treino | Avaliação |
|---|---|---|
| a) Linhas com notícia | Todas as linhas de `todas` | Só linhas com `noticias_dia_qtd` bruto ≥ 1; NaN sai, não vira zero |
| b) `principais` | Modelo 3 nessa versão × modelo 1 de `todas` | Todas as linhas e o recorte com notícia da própria versão |
| c) `hora_real_noite` | Modelo 3 nessa versão × modelo 1 de `todas` | Todas as linhas e o recorte com notícia da própria versão |
| d) Só notícias | Logística só com as colunas de notícias de `todas` | Frente ao acaso; o resultado principal é o recorte com notícia |

No recorte, o dia só entra com pelo menos 5 linhas com alvo e as duas classes; o acaso é recalculado nele, e os dias perdidos são relatados por ano.

**Decisões do usuário para o teste final (02/11/2026):**

| Tema | Decisão |
|---|---|
| Histórico | 2021 em diante, com a lacuna de jan–jul/2025 como limitação, conta como histórico completo. `modelo_oficial` muda antes do treino final, não agora |
| Medida primária | Ganho de AUC por pregão, modelo 3 − modelo 1, com IC 95% acima de 0. Secundária: top 5 frente ao acaso |
| Congelado | Logística, configuração final da rodada 001; referências: acaso, volatilidade e XGBoost do ponto de partida |
| Jan–jul/2025 preenchido depois | **Substituída pela D5 revista (03/11/2026), abaixo.** Texto original: fica vazio no resultado principal; depois do teste, só como sensibilidade |
| Dataset | Treino no sha `741e781122d0…`, com cópia guardada; o sha do dataset do teste é registrado antes de rodar |
| Preços reescritos | Comparar a parte de desenvolvimento, nova × congelada, sem abrir o teste, com tolerância 1e-6; acima disso, parar e perguntar |
| Custos | Bruto como primário; líquido com um custo único definido antes do teste |
| Eventos depois de 23/06/2026 | Auditar só retornos, antes do treino final. Evento novo gera nova versão e refaz protocolo e busca. Depois de congelar, nada muda: exclusão só como sensibilidade |
| `liberar_chance` | Continua `false` até o teste ao vivo |
| Fim do teste final | **Ainda não definido** |

**Decisões do usuário de 03/11/2026 (registradas antes de regenerar o dataset):**

| Tema | Decisão |
|---|---|
| D5 revista (dados novos antes do teste final) | Se a coleta preencher jan–jul/2025 (ou outras pendências) **antes** do teste final, regeneramos o dataset e rodamos uma nova rodada do protocolo e da busca, que passa a ser a oficial; as rodadas anteriores continuam no registro. Depois do teste final, dados novos ficam restritos a sensibilidade |
| Critério 5 com a recarga da WordPress | Fica como está escrito (seção 3; pregões de 2024, seção 7), apesar de a recarga de 2023 a 2025 desfazer a premissa "2023–2024 sem `wordpress`". O relatório registra a mudança de regime |
| P/VP na rodada 3 | Fica fora (seção 2). A correção do valor de mercado (quantidade na base atual, 03/11/2026) não o traz de volta nesta rodada |

Implementação (02/11/2026): a rotina passa a publicar a família da configuração congelada (`treino.familia_producao: "logistica"`); o modelo logístico é gravado em JSON (`logistica-AAAA-MM.json`, sem pickle), e a configuração da rodada 001 vale sem mudança.

### Rodada 3 (08/11/2026): resultado, decisão e desenho da sensibilidade

Registrado em 08/11/2026, **antes de rodar a sensibilidade da rodada 3**. Como o resto desta seção, é registro: não muda as seções 1 a 7.

**Situação.** O dataset é a v7 (`dataset-todas-2026-11-06.csv`, sha256 `c954b437c55e…`, conferência em `docs/conferencia_rodada_003.md`). É a rodada oficial pela D5 revista. Os hashes das regras são os mesmos das rodadas 1 e 2 (`sha_regras` `e275d3d6e8f1…` no protocolo e `dd967e28c1eb…` na busca).
- Protocolo (`docs/protocolo_rodada_003.md`): só o bloco A foi adotado, e o controle foi reprovado (igual à rodada 1).
- Busca (`docs/busca_rodada_003.md`): nenhum candidato foi aprovado, então fica a referência, XGBoost do ponto de partida (`docs/configuracao_final_rodada_003.json`).
- A logística reprovou nos critérios 1 (ganho 0,00482 ≤ 0,005), 2 (IC 99,5% [−0,00018; 0,00981]) e 4 (queda do top 5 de 0,55 pp). Comparação com a rodada 1 em `docs/comparacao_rodadas_001_003.md`.

**Decisões do usuário (08/11/2026):**

| Tema | Decisão |
|---|---|
| Vencedor | Segue o protocolo: a rodada 3 é a oficial e o vencedor é o XGBoost do ponto de partida. A logística entra no TCC só como achado ("quase venceu"), nunca escolhida por fora das regras |
| Efeito da seção 6 | Top 5, motivos (`pred_contribs`), calibração e `modelos/xgb-AAAA-MM.json` voltam ao desenho original. A terceira referência volta a ser a logística. O código da família logística em produção fica no código, testado, para uma rodada futura |
| "Sem notícias" nos motivos | No XGBoost, como já acontecia na logística, as contribuições de `noticias_dia_qtd`, `noticias_dia_tom` e `noticias_dia_extremo` de um dia sem tom são somadas num único motivo "Sem notícias". **É só o texto do motivo:** o `pred_contribs` e a previsão não mudam |
| Reprodução | A rodada 3 do protocolo e da busca é repetida com as mesmas entradas antes de mudar `treino.familia_producao` (que entra no `sha_parametros`) |
| Congelado (substitui a linha de 02/11) | XGBoost 3/50 da configuração final da rodada 003 e colunas de `docs/protocolo_congelado_rodada_003.json`; referências: acaso, volatilidade e logística |
| Dataset (substitui a linha de 02/11) | Treino no sha `c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa`, com cópia guardada fora do repositório; o sha do dataset do teste é registrado antes de rodar |
| Modelos antigos | Arquivados em `modelos/antigos/`, sem apagar |
| Sensibilidade | Só com a família vencedora |

**Desenho da sensibilidade da rodada 3** (exploratória; fora de `docs/protocolo_tentativas.jsonl` e da contagem de testes; IC sem ajuste por comparações múltiplas):
- Casos a, b, c e d iguais aos da rodada 1 (tabela acima), com as mesmas regras de recorte.
- Família XGBoost com os hiperparâmetros da configuração final 003; colunas de `docs/protocolo_congelado_rodada_003.json`; as mesmas 63 dobras e a mesma semente; só no desenvolvimento.
- Datasets de 2026-11-06: `todas` `c954b437c55e…`, `principais` `ca7d5bd161d1…` e `hora_real_noite` `d1909b4f5a6c…`.
- Saída em `docs/busca_rodada_003_sensibilidade.md` e `.json`.

### Checklist antes do teste final (D1 a D10)

Registrado em 04/11/2026 a partir das decisões acima, para o painel (aba Experimento) ler. Não muda as seções 1 a 7. Situação: `fechada` (decisão tomada) ou `pendente`. A D2 passa a contar como fechada sozinha quando `treino.teste_final.fim` for preenchido no `parametros.yaml`.

| Id | Decisão | Situação |
|---|---|---|
| D1 | Histórico desde 2021, com as lacunas como limitação | fechada |
| D2 | Data de fim do teste final (a definir) | pendente |
| D3 | Hipótese e medida principal: ganho de AUC por pregão do modelo 3 sobre o 1, com IC 95% acima de 0 | fechada |
| D4 | Família, colunas e referências congeladas | fechada |
| D5 | Dados novos antes do teste final geram nova rodada | fechada |
| D6 | Dataset congelado com hash registrado | pendente |
| D7 | Conferência de preços reescritos (tolerância 1e-6) | fechada |
| D8 | Custos definidos antes | pendente |
| D9 | Auditoria de eventos após 23/06 | pendente |
| D10 | Chance oculta até o teste ao vivo | fechada |
