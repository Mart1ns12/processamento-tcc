# Regras do dataset do experimento

Regras do código em 01/11/2026, depois das correções das partes A e B da revisão (seção 11). Os números vêm de `docs/diagnostico_banco.md`, `docs/validacao_wordpress.md` e `docs/medicao_dedup_origens.md`, medidos **antes** dessas correções, e são contagens brutas do banco, antes dos filtros, salvo aviso.

> **Os CSVs em `saida/experimento/` e os modelos em `modelos/` não seguem estas regras** e são de outra versão de preparação: o treino recusa esses CSVs (é preciso regenerar as 3 versões), e o modelo `xgb-2026-06` deixa o top 5 de fora, com aviso, até o próximo treino. O relatório `treino/dev-2026-10-23` também é anterior a estas regras.

---

## 1. Objetivo

- **O que prevê:** para cada ação e pregão t, a probabilidade de o retorno com dividendos da ação **superar o do Ibovespa no próximo pregão** (t+1). É classificação binária.
- **Horizonte:** 1 pregão, de fechamento a fechamento.
- **Uso:** ordenar as ações do dia e pegar as 5 primeiras. O corte de informação é **08:00 de t+1**.
- **Pergunta do TCC:** as notícias do dia t e da noite, lidas pelo FinBERT, melhoram essa previsão? Compara-se o modelo 3 (com notícias) ao modelo 1 (sem notícias).

## 2. Universo e período

Regras em `universo.py:94-113`. Vale o primeiro motivo que se aplicar:

| Ordem | Saem | Motivo |
|---|---|---|
| 1 | CRFB3, SRNA3, STBP3 (`exclusoes.yaml`) | `excluido_por_decisao`, em todas as datas |
| 2 | BDR ou tipo desconhecido | `tipo_nao_aceito`: só entram ON, PN e UNIT |
| 3 | Fora da composição daquela data | `fora_da_composicao` |
| 4 | `fechamento_ajustado` vazio em t | `sem_preco`, só naquela data |

| Situação da data | Quem é candidato | Coluna `universo` |
|---|---|---|
| Coberta por `v1-composicao_ibov` (desde 01/01/2021) | Ações com vigência na data | `composicao_historica` |
| Não coberta (2019–2020) | Ações do `v1-cadastro` de hoje | `composicao_atual` |

Tickers antigos da composição passam pela `v1-mudancas_ticker` (`fontes.py:869`). O Assaí fica no universo mesmo sem balanço, porque balanço não é variável.

**Tamanho (diagnóstico de 01/11/2026):** ~117,8 mil linhas (ação × pregão), com mediana de 60 ações por pregão em 2021 a 77 em 2025.

| Período | Início | Fim | Regra no código |
|---|---|---|---|
| Linhas do dataset | 30/12/2019 (1º preço) | Último pregão lido, ou `--ate` | `dataset.py:224-225` |
| Linhas usadas no treino | 2021-01-01 (`treino.inicio_experimento`) | | 1º pregão em 04/01/2021; 1ª dobra de teste em 04/2021 |
| Desenvolvimento | 2021-01-01 | Antes de 23/06/2026, menos 1 pregão de embargo (~5,5 anos) | `validacao.py:57-62` |
| Teste final | 23/06/2026 | `treino.teste_final.fim`, hoje vazio = **trava ativa** | Só linhas com t+1 ≤ `fim`; uso único |
| Teste ao vivo | Linha do `fim` em diante | | Top 5 gravado no dia da geração |

## 3. Alvo

Código em `experimento/alvo.py`. Todos usam `fechamento_ajustado` (aj). t+1 é a **linha seguinte do calendário**, e o calendário são as datas com fechamento do IBOV.

| Coluna | Definição | Observação |
|---|---|---|
| `ret_t1` | aj(t+1) / aj(t) − 1 | Vazia se faltar preço em t+1 ou houver suspeito em t+1 |
| `ret_ibov_t1` | Mesma conta no IBOV | Nunca recebe a máscara de suspeito |
| `alvo` | 1 se `ret_t1` > `ret_ibov_t1`; senão 0 | **Empate = 0**. Vazio se faltar um lado. Alvo principal |
| `alvo_abertura` | Abertura ajustada de t+1 / aj(t) − 1, comparada com o mesmo cálculo no IBOV | Abertura ajustada = abertura × aj / fechamento do mesmo dia |
| `alvo_abertura_valido` | 1 se a abertura do IBOV em t+1 ≠ fechamento em t | O Yahoo repete o fechamento em ~32% dos dias; só os dias válidos são avaliados |

- **Dias sem pregão:** não existem na grade; sexta aponta para segunda. Feriados não definem o calendário, quem define é o preço do IBOV.
- **Ação sem preço em t+1:** alvo vazio. Não se procura o preço seguinte, diferente dos `ret_*`, que usam base as-of.
- **Retorno suspeito em t+1** (fora de [−75%, +100%], limites exatos não contam): `ret_t1`, `alvo` e `alvo_abertura` ficam vazios (`alvo.py:66-74`). A linha continua no dataset e sai do treino e da avaliação. O preço não é corrigido.
- **Variação através de lacuna maior que 5 pregões:** não é retorno diário, logo não é suspeita.
- **Última data:** sem alvo. É a linha da previsão ao vivo.

## 4. Variáveis

São 36 colunas (`COLUNAS_DATASET`, em `dataset.py`). **O CSV guarda os valores brutos:** o rank é aplicado depois, em `preparacao.preparar`, com a mesma função no treino e na previsão.

- **Rank:** `(posição média − 1) / (n − 1)` dentro do pregão, entre as ações do universo, antes de tirar as linhas sem alvo. Vazio continua vazio; um único valor vira 0,5.
- **`noticias_dia_qtd` também entra em rank.** As outras 5 de notícias ficam brutas.
- **Coluna "Modelo":** **M1** = modelo 1 e 3; **M3** = só modelo 3; **Bloco** = candidata, entra só se o AUC médio por pregão subir mais de 0,005; **Não** = nunca é entrada.

### Identificação

| Coluna | Definição | Modelo |
|---|---|---|
| `data`, `ticker` | Pregão t e código atual | Não |
| `empresa` | CNPJ do cadastro; sem CNPJ, o próprio ticker | Não |
| `setor` | Setor do cadastro **de hoje**; ticker antigo herda o da empresa | Não |
| `universo` | `composicao_historica` ou `composicao_atual` | Não |
| `dia_resultado` | Empresa com `data_entrega` na noite de t | Não: só recorta a avaliação do 3b |

### Preço e retorno (todas em rank)

| Coluna | Fórmula | Janela e mínimo | Modelo |
|---|---|---|---|
| `ret_1d`, `ret_5d`, `ret_20d` | aj(t) / aj(t−n) − 1 | n = 1, 5, 20; base as-of até 5 pregões antes da data-alvo | M1 |
| `salto_abertura` | Abertura ajustada(t) / aj(t−1) − 1 | Exige o pregão anterior exato | M1 |
| `volume_relativo` | volume(t) / mediana do volume | 20 pregões anteriores completos, sem t | M1 |
| `dist_max_52s`, `dist_min_52s` | aj(t) / máx (mín) de aj − 1 | 252 pregões com t, mínimo 120 | Bloco `preco_contexto` |
| `amplitude` | (máxima − mínima) / fechamento | Dia t | Bloco `preco_contexto` |

### Risco (todas em rank)

| Coluna | Fórmula | Janela e mínimo | Modelo |
|---|---|---|---|
| `volatilidade_20d` | Desvio-padrão amostral dos retornos diários, sem anualizar | 20 retornos completos | M1 |
| `beta` | Inclinação (MQO) da ação contra o IBOV | 252 pregões, mínimo 120 pares | M1 |

### Fundamentos

**Nenhuma variável.** O dataset não usa P/L, P/VP, ROE, margens, endividamento nem proventos; essas contas são só do painel. De balanços, usa apenas `data_entrega`, para `dia_resultado`. Proventos entram só de forma implícita, no `fechamento_ajustado`.

### Notícias

| Coluna | Fórmula, com score = `prob_positivo − prob_negativo` | Janela e mínimo | Modelo |
|---|---|---|---|
| `noticias_dia_qtd` | Nº de notícias da empresa, inclusive sem score; **em rank** no modelo | Janela do modelo | M3 |
| `noticias_dia_tom` | Média dos scores | Janela do modelo | M3 |
| `noticias_dia_extremo` | Score de maior módulo, com sinal; empate = média. Bruta, ou em rank (`noticias_dia_extremo_rank`) se o desenvolvimento aceitar | Janela do modelo | M3 |
| `mudanca_tom` | Tom de t − média dos scores da empresa antes de t, com peso por notícia | 30 pregões anteriores, sem t; mínimo 5 notícias com score | M3 |
| `tom_mercado` | Média dos scores das empresas do universo, cada `id` uma vez | Janela do modelo | Bloco `noticias_contexto` |

### Setor

| Coluna | Fórmula | Janela | Tratamento | Modelo |
|---|---|---|---|---|
| `ret_vs_setor` | ret_1d − média do setor, sem a empresa inteira; cada empresa 1 voto; só ações do universo | Dia t | Rank | Bloco `preco_contexto` |
| `tom_setor` | Média do tom das outras empresas do setor no universo; cada empresa 1 voto | Janela do modelo | Bruta | Bloco `noticias_contexto` |

### Macro e índices (em rank)

| Coluna | Fórmula | Janela e mínimo | Modelo |
|---|---|---|---|
| `exposicao_dolar` | Beta contra USDBRL × variação do USDBRL em t | 120 pregões, mínimo 60 pares | Bloco `macro` |
| `exposicao_petroleo` | Beta contra BRENT × variação do BRENT em t | 120 pregões, mínimo 60 pares | Bloco `macro` |

CDI, IPCA, IDIV, IFIX e IVVB11 **não entram**. O IBOV entra no `beta`, no `ret_idio_5d`, na `exposicao_small` e nos alvos. O SMLL é lido só para a `exposicao_small`.

### Colunas do protocolo (em rank; fora dos modelos atuais)

Só entram nos testes de bloco de `docs/protocolo_variaveis.md`.

| Coluna | Fórmula | Janela e mínimo | Bloco |
|---|---|---|---|
| `posicao_fechamento` | (fechamento − mínima) / (máxima − mínima) | Dia t; máxima ≤ mínima = vazio | A |
| `mom_12_1` | aj(t−21) / aj(t−252) − 1 | Base as-of até 5 pregões antes de cada data-alvo | A |
| `liquidez_20d` | Mediana de fechamento × volume | 20 sessões completas, com t | A |
| `ret_idio_5d` | `ret_5d` − `beta` × retorno de 5 pregões do IBOV | Base as-of até 5 pregões | A |
| `momento_setor_5d` | Média de `ret_5d` das outras empresas do setor; cada empresa 1 voto | Dia t | B |
| `exposicao_small` | Beta contra (ret SMLL − ret IBOV) × esse fator em t | 120 pregões, mínimo 60 pares | B |

### Alvo

`alvo`, `alvo_abertura`, `alvo_abertura_valido`, `ret_t1`, `ret_ibov_t1` (seção 3). Nunca são entrada do modelo.

## 5. Regras de tempo e vazamento

**Por leitura do código, não achei nenhuma variável que olhe depois do corte:** as contas usam `shift(1)` ou `rolling` para trás, e só `alvo.py` usa `shift(-1)`.

| Informação | Quando conta | Código |
|---|---|---|
| Preços, volume, USDBRL, BRENT, SMLL | Até o fechamento de t | `variaveis.py`; ao vivo, `saida/insumos.py` corta os índices em t |
| Notícia com hora real | Até 08:00:00 de t+1; 08:00:01 já é de t+1 | `calendario.py:277-302` |
| Notícia sem hora (CVM, "só data") | Vale 23:59:59 da sua data, ou seja, a noite do pregão daquela data | `fontes.py:557-586` |
| Fim de semana e feriado | Vai para o último pregão antes, até 08:00 do próximo | `calendario.py:297-302` |
| Última data, sem `--proximo` | Janela aberta: as 6 colunas de notícias ficam vazias | `dataset.py:122`, `tom.py:135-151` |
| Última data, ao vivo | Notícias cortadas em 08:00 de D; `proximo_ao_vivo = D` | `saida/insumos.py:57`, `saida/gerar.py:213` |
| Balanço | `data_entrega` às 23:59:59 cai na noite daquela data; só marca `dia_resultado`. Ao vivo, lido até D − 1 dia | `experimento/resultados.py`, `saida/insumos.py` |
| Proventos | Não são lidos; só o efeito no preço ajustado | |
| Rank | Só linhas do mesmo pregão | `preparacao.py:28-34` |

**"Só data" não adianta informação:** a data vem de Los Angeles, e qualquer instante depois das 08:00 de São Paulo já é o dia seguinte em Los Angeles.

**Testes que cobrem essas regras** (não rodados nesta avaliação):

| Regra | Teste |
|---|---|
| Janelas e bordas | `test_exp_janelas.py::test_classificar_noticias_casos_da_tabela`, `::test_janela_noite`; `test_calendario.py::test_janela_noite_vai_do_fechamento_ate_8h_do_proximo_pregao` |
| Só data e N1-A por origem | `test_fontes_so_data.py::test_regra_so_vale_para_origens_so_data`, `::test_janela_so_data_segue_regra_das_sem_horario` |
| Noite aberta ou fechada | `test_exp_dataset.py::test_noite_do_ultimo_pregao_aberta_sem_proximo_ao_vivo`, `::test_noite_do_ultimo_pregao_fechada_com_proximo_ao_vivo` |
| `mudanca_tom` sem futuro | `test_exp_tom.py::test_mudanca_tom_nao_olha_pregao_depois_de_t` |
| Salto com anterior estrito | `test_exp_variaveis.py::test_salto_pregao_anterior_e_estrito_sem_preencher` |
| Máscara de suspeitos | `test_exp_suspeitos.py` |
| Última data sem alvo | `test_exp_dataset.py::test_ultima_data_sem_alvo_com_ret_1d` |
| Rank antes de tirar linhas sem alvo | `test_exp_preparacao.py::test_preparar_faz_rank_antes_de_descartar_sem_alvo` |
| Entrega de balanço | `test_exp_resultados.py` |
| Embargo e separação treino/teste | `test_treino_validacao.py::test_caso2_nenhuma_data_de_teste_no_treino_e_embargo_respeitado` |
| Dataset inteiro: 4 datas de t, mudança só em t+1, mudança depois de t+1, dados não lidos, cópias posteriores | `test_vazamento_experimento.py` |
| Teste final e teste ao vivo | `test_treino_trava.py::test_veneno_do_teste_ao_vivo_nao_muda_nada`, `::test_segunda_chamada_do_teste_final_e_bloqueada` |

**Vazamento do dataset inteiro:** `test_vazamento_experimento.py` compara as linhas de t entre o cenário cortado em t e o cenário com o futuro alterado (preços, volumes, notícias e balanço), antes e depois dos ranks.

**O que não é "conhecido na data", mesmo sem vazar preço:**

- O setor e o CNPJ vêm do cadastro de hoje.
- As notícias foram coletadas depois: `data_hora_coleta` começa em 07/09/2026, com mediana de ~133 dias entre publicação e coleta.
- FinBERT e juíza rodaram depois da publicação. A juíza não tem busca, mas pode julgar ao vivo diferente do histórico.
- Uma notícia publicada pouco antes das 08:00 pode não ter sido capturada ao vivo.

## 6. Notícias

**Sequência** (`fontes.py:502-515`, depois `noticias.py:294-304`): leitura → N1-A → tira `papel = errada` → filtro de versão → liga à empresa → repetidas → janela e score → variáveis.

### Origens

Artigos distintos por ano, antes dos filtros (2021–2022 e 2026 somam as três origens):

| Ano | `google_news` | `wordpress` | `cvm_ipe` | Hora real |
|---|---|---|---|---|
| 2021 | 13.787 | 15.126 | 4.237 | 50,0% |
| 2022 | 15.328 | 17.440 | 3.866 | 51,4% |
| 2023 | 24.069 | 0 | **0** | 9,3% |
| 2024 | 31.715 | 0 | 3.646 | 9,0% |
| 2025 | 30.654 | 0 | 1.549 | 2,1% |
| 2026 | 121.383 | 2.019 (03 e 10–11) | 2.844 | 17,1% |

### Regras

- **N1-A:** só em `origens_so_data` (`google_news`). 00:00:00 em Los Angeles vira "só data". Na `wordpress`, 05:00:00 é hora real. `precisao_hora` fica `hora`, `meia_noite_pacifico` ou `sem_hora`.
- **Filtro de papel:** `papel = errada` sai antes das repetidas, em todas as versões. Papel vazio fica (1.343 linhas, 0,33%). Corte desigual: `google_news` 10,7%, `wordpress` 1,5%, `cvm_ipe` 0%.
- **Repetidas, passo 1:** mesma empresa e mesmo `id` contam uma vez.
- **Repetidas, passo 2:** dentro da mesma origem, fora `cvm_ipe`, mesma empresa + `data_publicacao` + título normalizado contam uma vez. Fica a de momento mais cedo; no mesmo momento, a com probabilidade; depois o menor `id`.
- **Repetidas, passo 3 (entre origens, fora `cvm_ipe`):** casa com uma cópia já mantida de outra origem, sem fechamento transitivo, por:
  - título (`normalizar_titulo`, sem o sufixo " - Veículo"), com ≥ 5 palavras e até 1 dia de distância; ou
  - URL (`resolved_url`, senão `link`; domínio + caminho), sem limite de data nem de palavras.
- **Quem fica entre origens:** momento mais cedo (a hora real, ou 23:59:59 da data sem hora) → com probabilidade → hora real → menor `id`. Assim, uma cópia posterior nunca muda o passado.
- **Efeito medido (antes do filtro de papel e da regra do momento mais cedo; refazer ao regenerar):** 1.449 cópias removidas (1.340 título no mesmo dia, 76 título em ±1 dia, 33 URL), quase todas em 2021–2022 e 2026.

### Janelas

| Janela | Intervalo | Onde vale |
|---|---|---|
| **Do modelo** (`inicio_janela: "manha"`) | 08:00:01 de t até 08:00:00 do próximo pregão | Versões `todas` e `principais`, e `noticias_dia` |
| Pré-abertura | 08:00:01 até a abertura | Classificação; dentro da janela do modelo |
| Pregão | Abertura até o fechamento (inclusive) | Classificação; dentro da janela do modelo |
| Noite | Depois do fechamento até 08:00 do próximo pregão | Única janela da `hora_real_noite` |

Fechamento às 17h ou 18h conforme `horarios_b3`; quartas de cinzas abrem às 13h.

### Versões

Cada uma gera um CSV com as mesmas linhas; só as colunas de notícias mudam. O filtro de versão vem **antes** das repetidas.

| Versão | Notícias | Janela | Uso |
|---|---|---|---|
| `todas` | Todas, menos `errada` | Modelo | Principal; ao vivo |
| `principais` | `cvm_ipe`, ou `tipo_conteudo = reportagem` com `papel` em `protagonista`/`citada_com_fato` | Modelo | Teste extra |
| `hora_real_noite` | Só `precisao_hora = hora` | Só noite | Exploratório; exclui `cvm_ipe` e "só data" |

Notícia da empresa vale para todas as suas classes: PETR3 e PETR4 recebem os mesmos valores.

## 7. Dados faltantes

| Situação | Resultado | Por quê |
|---|---|---|
| Antes de `cobertura_inicio` | As 6 colunas vazias, inclusive `qtd` | Não havia coleta |
| Pregão em `experimento.periodos_sem_coleta` (01/01 a 31/07/2025) | As 6 colunas vazias, inclusive `qtd`; `noticias_dia` `indisponivel` | Não houve coleta, logo não é "sem notícia" |
| Base da `mudanca_tom` tocando o período | `mudanca_tom` vazia (até ~meados de set/2025) | A base exige a janela inteira coberta |
| Data coberta sem notícia | `qtd = 0`; tom, extremo e `mudanca_tom` vazios | É tratado como fato: "não houve notícia" |
| Notícia sem probabilidade | Conta em `qtd`; fora dos scores | Ausente, nunca neutra |
| Histórico curto | Variável vazia | Mínimos da seção 4 |
| Base as-of a mais de 5 pregões | `ret_*` e `ret_vs_setor` vazios | Base velha |
| Suspeito no dia s | `ret_1d` e `salto_abertura` em s; `ret_5d` de s a s+4; `ret_20d` de s a s+19; `dist_*` de s a s+250; `ret_vs_setor` em s | A conta atravessa o salto; a ação também sai da média do setor das outras |
| Suspeito em `mom_12_1` | Vazia se o salto estiver em (t−252, t−21] | A conta atravessa o salto; dentro do mês pulado, não |
| Suspeito em `liquidez_20d` | Vazia enquanto o salto estiver nas 20 sessões | O `fechamento` também pode vir errado |
| SMLL ausente na `v1-indices` | `exposicao_small` vazia, com aviso | Nunca 0. Sem a tabela, a leitura para |
| Suspeito em `volatilidade_20d` | Janela incompleta: vazia | Exige 20 retornos |
| Suspeito em `beta` e `exposicao_*` | O par sai; vazio só se cair abaixo do mínimo | |
| `volume_relativo` e `amplitude` no suspeito | Não mudam | Não usam o ajustado |
| Fator sem cotação em t | `exposicao_*` vazia | |
| Sem setor ou sem outra empresa | `ret_vs_setor` e `tom_setor` vazios | |

**O que é descartado:**

| O quê | Onde |
|---|---|
| Linha fora do universo | Nunca entra no dataset |
| Notícia `errada`, cópia repetida, ou fora do calendário | Na preparação |
| Balanço com período inválido | `dias_de_resultado` |
| Linha sem `alvo` | Treino e avaliação (continua no CSV) |
| Linha antes da cobertura; teste final e embargo | Na leitura do treino |

**O XGBoost usa os vazios como estão.** Só a logística imputa: mediana + indicador de vazio, dentro de cada ajuste. Vazio nunca vira 0 nas variáveis; `qtd = 0` só em data com coleta.

## 8. Validação e treino

- **Divisão:** seção 2. Grade e blocos são escolhidos só no desenvolvimento.
- **Walk-forward mensal e expansivo:** cada dobra testa 1 mês e treina em **todos** os pregões anteriores, menos o último (embargo de 1 pregão, cujo alvo olha o 1º dia de teste). Não há janela deslizante (`validacao.py:83-97`).
- **Treino mínimo:** 3 meses antes da 1ª dobra.
- **Teste final:** mesmo esquema, com a configuração congelada nos metadados do desenvolvimento. Exige `fim` preenchido, `liberado: true`, a opção `--teste-final` e nenhum registro de uso anterior.

| Modelo | Entradas | Papel |
|---|---|---|
| Modelo 1, XGBoost | 7 essenciais de preço + blocos aceitos | Quanto o preço explica |
| Modelo 3, XGBoost | Modelo 1 + 4 de notícias (+ `noticias_contexto` se aceito) | **Hipótese do TCC** |
| "3b" | **Só avaliação:** previsões do 3 e do 1 nos dias de resultado | Efeito em dia de balanço |
| Modelo 3 principais / hora real | Colunas do 3 com outro CSV | Testes extras |
| Regressão logística | Colunas do 3 | Referência |
| Regra da volatilidade | 1 − rank da volatilidade; vazio = 0,5 | Referência sem treino |
| Acaso | 10 mil sorteios de k ações por dia; faixa p2,5–p97,5 | Referência |

- **XGBoost:** `n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5`; grade `max_depth {2,3} × min_child_weight {50,200}`; semente 20261023; `n_jobs=1`.
- **Seleção (só no desenvolvimento):** `preco_contexto` e `macro` no modelo 1; `noticias_contexto` no modelo 3; `noticias_dia_extremo` em rank no modelo 3 (mesma regra de ganho); depois a grade, no modelo 3.
- **Versão:** dataset de outra `versao_preparacao` é recusado pelo treino. Modelo de outra versão deixa só o top 5 de fora, com aviso; os outros pacotes saem normalmente (rodada `ok` com o top não publicado, `parcial` com o top publicado).
- **Métricas:** taxa de acerto do top 5 (e top 3) × faixa do acaso; excesso de retorno contra o IBOV; top × últimos k; AUC geral e por pregão; IC por bootstrap circular (blocos de 5, 2000 reamostragens); diferenças pareadas; robustez por ano; sensibilidade do último ano; `alvo_abertura` só nos dias válidos; calibração (ECE ≤ 0,02 com ≥ 5000 linhas).
- **Critério:** o modelo 3 só "ganha" no top 5 se ficar acima do acaso **e** superar volatilidade e logística (`treino.py:561-579`).

## 9. Parâmetros que afetam o dataset

Todos em `processamento/config/parametros.yaml`, salvo aviso.

| Chave | Valor | Afeta |
|---|---|---|
| `fuso`, `corte_noite` | São Paulo; 08:00 | Corte das janelas |
| `horarios_b3`, `dias_especiais` | Por período | Pregão × noite × pré-abertura |
| `experimento.inicio_janela` | `manha` | Janela do modelo |
| `experimento.sem_horario_na_noite` | `true` | Sem hora entra às 23:59:59 ou sai |
| `experimento.deduplicar_titulo` | `true` | Repetidas por título |
| `experimento.deduplicar_entre_origens` | `true` | Passo 3 das repetidas |
| `experimento.janela_dias_entre_origens` | 1 | Distância máxima por título |
| `experimento.titulo_palavras_min_entre_origens` | 5 | Mínimo de palavras |
| `experimento.principais.*` | `cvm_ipe`; `reportagem`; `protagonista`, `citada_com_fato` | Versão `principais` |
| `experimento.periodos_sem_coleta` | 2025-01-01 a 2025-07-31 | Colunas de notícias vazias |
| `experimento.noticias_mes_fracao_minima` | 0,25 | Só o aviso do diagnóstico |
| `experimento.retornos` | 1, 5, 20 | `ret_*` |
| `experimento.exposicao_pregoes` / `_minimo` | 120 / 60 | `exposicao_*` |
| `experimento.extremos_pregoes` / `_minimo` | 252 / 120 | `dist_*` |
| `experimento.mudanca_tom_pregoes` / `_minimo` | 30 / 5 | `mudanca_tom` |
| `fase1.volatilidade_retornos` | 20 | `volatilidade_20d` |
| `fase1.volume_pregoes` | 20 | `volume_relativo` |
| `fase1.beta_pregoes` / `beta_minimo` | 252 / 120 | `beta` |
| `fase1.base_defasagem_max_pregoes` | 5 | `ret_*`, `ret_vs_setor`, suspeitos |
| `fase1.retorno_suspeito_min` / `_max` | −0,75 / +1,00 | Máscaras e alvo |

**Sem efeito no dataset:** `fase1.setor_excluir` (a `ret_vs_setor` sempre exclui a empresa inteira), `fase1.setor_minimo` e `fase1.retorno_suspeito_pregoes_nivel`.

**Afetam quais linhas o treino usa (não o CSV):** `treino.inicio_experimento`, `treino.treino_minimo_meses`, `treino.embargo_pregoes`, `treino.teste_final.*`.

**Fora do `parametros.yaml`:** `fontes.yaml` (`origens_ignoradas: []`, `origens_so_data: [google_news]`, `papeis_ignorados: [errada]`) e `exclusoes.yaml` (`tickers_excluidos`).

## 10. Limitações e pontos em aberto

### Notícias

1. **Volume crescente e mudança de regime.** O volume varia até 9 vezes entre períodos. `noticias_dia_qtd` entra em rank para reduzir o efeito, mas o rank não elimina: com mais notícias, menos ações ficam em zero, e `noticias_dia_extremo` bruta também tende a crescer com o volume. Pares ação × notícia por mês, antes dos filtros:

   | Período | Pares/mês | Composição |
   |---|---|---|
   | 2021 | ~4.650 | `wordpress` + `google_news` + CVM |
   | 2022 | ~5.450 | `wordpress` + `google_news` + CVM |
   | 2023 | ~2.430 | Só `google_news` |
   | 2024 | ~3.560 | `google_news` + CVM |
   | 08–12/2025 | ~8.100 | `google_news` + CVM |
   | 01–06/2026 | ~13.700 | Com `wordpress` em 03/2026 |
   | 07–10/2026 | ~21.500 | Com `wordpress` em 10/2026 |

   **O teste final (desde 23/06/2026) tem bem mais notícias por mês do que o desenvolvimento.**
2. **Buraco de jan–jul/2025.** Janeiro tem 38 artigos e fevereiro a julho têm zero, em todas as origens. Tratado por `periodos_sem_coleta`; o diagnóstico avisa quando a coleta preencher.
3. **`cvm_ipe` não existe em 2023** nem de 02 a 07/2025. A especificação não registra o de 2023.
4. **`wordpress` marca mais ações por artigo:** ~2,3 pares por artigo em 2021, contra ~1,15 no `google_news`. Isso muda `qtd` e o tom por empresa nos anos com essa origem.
5. **A amostra manual da `wordpress`** (`docs/validacao_wordpress.md`) não foi revisada; a origem entrou por decisão, com a coleta confirmando a fonte.
6. **Juíza não avaliada.** O filtro `errada` depende dela, corta de forma desigual entre origens, e ao vivo uma notícia sem `papel` entra e pode sair depois de julgada.
7. **Hora real rara.** ~90% do `google_news` não tem hora, então não dá para separar pregão de noite. `hora_real_noite` fica concentrada em 2021, 2022 e 2026. A reavaliação da N1-A depende do `corrigir_horas`, que estava pendente.
8. **Histórico × ao vivo:** uma cópia ao vivo pode ser trocada no histórico por outra publicada antes e coletada depois, mudando o pregão da notícia. Isso não vaza futuro. A regra por URL não tem limite de data: 22 pares têm mais de 30 dias de distância. Cópia mais cedo sem probabilidade fica, e o painel do dia sai `indisponivel` nesse caso (raro: hoje todas têm probabilidade).

### Universo e preços

9. **Viés de sobrevivência:** 46 tickers da composição sem nenhum preço, mais os 3 excluídos.
10. **Composição não oficial:** 115 de 137 linhas vêm de `paccafelipe_csv`.
11. **Classes da mesma empresa:** PETR3 e PETR4 têm as mesmas notícias e podem ocupar duas vagas do top 5. As linhas não são independentes.
12. **`tom_mercado` é igual para todas as ações do dia:** só ajuda por interação com outras variáveis.
13. **Abertura da ação = fechamento anterior** em ~11% dos pares: afeta `salto_abertura`.
14. **Abertura do IBOV com defeito** em ~32% dos dias: afeta só `alvo_abertura`.
15. **Float32 no ajustado:** cerca de 0,01% das linhas têm alvo sensível a empate, e o sha256 muda a cada regeração.
16. **Balanço reapresentado** guarda só a última `data_entrega`: `dia_resultado` pode cair na data errada.

### Estado do experimento

17. `modelo_oficial: false`: nenhum resultado vale como conclusão até o usuário declarar o histórico completo.
18. Os índices estão completos desde 02/11/2026: IDIV, SMLL e IFIX desde 30/12/2019; CDI e IPCA desde 01/2021.
19. Os três CSVs precisam ser regenerados para valer estas regras. A avaliação de desenvolvimento precisa ser refeita depois disso, e até lá o top 5 fica de fora.

## 11. Divergências encontradas na revisão: todas tratadas

| # | Assunto | O que foi feito |
|---|---|---|
| D1 | `qtd = 0` no buraco de 2025 | **Código:** `experimento.periodos_sem_coleta`; colunas vazias |
| D2 | Três datas de início da cobertura | **Especificação e parâmetro:** início fixo em 2021-01-01 |
| D3 | Teste de vazamento | **Testes e código:** teste ampliado; cópia posterior não muda mais o passado (o teste já existia) |
| D4 | `setor_excluir` não afeta o modelo | **Comentário do yaml:** `"empresa"` fixo, como decide a E14 |
| D5 | `dia_resultado` no fim de semana | **Código:** ao vivo, balanços até D − 1 dia só para o dataset |
| D6 | Alvos guardados | **Especificação:** inclui `alvo_abertura_valido` |
| D7 | `tom_setor`, `tom_mercado`, `mudanca_tom` | **Especificação:** 7.3 alinhada a E7, E8 e E9 |
| D8 | "89% sem julgamento" | **Especificação:** medição marcada para refazer ao regenerar |
| D9 | "~89%/~91% só data" | **Especificação:** percentuais por período |
| D10 | Sensibilidade | **Especificação:** sempre calculada |
| D11 | Modelo 3b | **Especificação e código:** só avaliação; `"3b"` e o prefixo `xgb-m3b-` removidos |
| D12 | Textos com "~1 ano" | **Código e comentário:** atualizados |

### Pontos em aberto

- **`noticias_dia_extremo` em rank:** a decisão sai da próxima avaliação de desenvolvimento (etapa `noticias_dia_extremo em rank` em `selecao.csv`).
- **Efeito das regras novas nos dados reais:** só se mede ao regenerar: linhas afetadas pela regra do momento mais cedo, seção "Notícias por mês" do diagnóstico e cobertura das versões `principais` e `hora_real_noite`.
