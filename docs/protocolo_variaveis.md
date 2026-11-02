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

**Critério 5 no bloco E:** `fato_relevante_cvm` fica vazio em 2023, então na prática esse critério mede 2024.

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

A registrar antes de rodar, depois da Parte B da implementação.
