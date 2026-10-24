# PLANO: ETAPA 8, ROTINA DIÁRIA (gatilho da seção 4, prazos e avisos)

> **ESTADO (23/10/2026): fases 0 a 10 implementadas.** `pytest -q` = 1387 passaram, 23 pulados; com `PROC_TESTES_COM_BANCO=1`: 1410 passaram. Falta a ação do usuário: rodar `python -m processamento.rotina --sem-esperar` contra o banco real e criar a tarefa do Agendador (`LEIA-ME.md`).
> **Aprovado pelo usuário em 23/10/2026:** R1 a R15 como recomendado. **R2 com detalhe:** mesmo com `falhou`, o `execucao.json` é gravado (status `falhou`, `coleta_status.motivo`, horários da consulta e o aviso da desistência), para a interface mostrar "dados de ontem; a atualização de hoje falhou"; os outros 9 pacotes não são gerados. **R13:** PC + Agendador agora; a escolha para a produção fica para depois.
> Base: commit `0c4d892` (etapa 7 completa). `pytest -q` = ~1220 testes com os de banco (informado), todos passando.
> Ambiente: Python 3.12 (.venv), pandas 3.1, xgboost 3.4.1. Sem dependência nova neste plano.
> Valores marcados **(conferido)** foram calculados rodando as funções que já existem sobre as fábricas de teste (sem banco e sem rede). Os outros foram feitos à mão, com a conta ao lado.
> **Medido (saída real que o usuário gerou em 23/10/2026, `saida/2026-10-23/execucao.json`, rodada 2):** `gerar` levou **1 min 54 s** (21:40:08 → 21:42:02) com ~1 ano de histórico: leitura ~11 s, `series_diarias` ~33 s, `noticias_dia` ~32 s, `fundamentos_trimestrais` ~16 s, `experimento_top` ~10 s. **Medido agora:** treino do XGBoost (300 árvores, `n_jobs=1`, 11 colunas) = 0,6 s com 25 mil linhas e 2,5 s com 110 mil (≈ 5 anos); os dois modelos do retreino somam ~1,2 s hoje e ~5 s com 5 anos.

## Resumo

A etapa entrega `python -m processamento.rotina` (sem `--data` = hoje em São Paulo; `--data AAAA-MM-DD`; `--sem-esperar`). A rotina: (1) confere se D é pregão por uma **lista de feriados da B3** no `parametros.yaml` (sem pregão: sai sem gravar nada); (2) a partir das 08:00, a cada 5 min, lê `v1-painel_execucoes` e `v1-painel_etapas` (só por `fontes.py`, READ ONLY) e espera a `entrega` do daily de hoje ficar `concluida`; (3) com a entrega pronta, chama o `gerar` da etapa 7 (Fase 1, fecha os tops pendentes, retreina no 1º pregão do mês, top 5, pacotes) passando o `coleta_status` ampliado e os avisos; (4) sem entrega até 09:45, grava só um `execucao` com status `falhou` e continua esperando até 12:00 por uma rodada tardia (top 5 depois das 10h não vale para o histórico).

O relógio e a espera são injetáveis (`Relogio.agora()` / `Relogio.dormir()`), e a leitura do painel também (`consultar()`), então os testes simulam a manhã inteira em milissegundos. Uma trava em arquivo impede duas rotinas ao mesmo tempo. A checagem diária da seção 6 vira avisos do `execucao`. O fechamento do histórico passa a varrer **todos** os tops pendentes (hoje só olha o de t), e um dia que se descobre não ter sido pregão é descartado com registro próprio. O retreino mensal fica dentro da rotina (medido: segundos) e só liga em produção. A entrada em produção ganha um comando de conferência (`python -m processamento.producao --inicio D0`), mas **é decisão e ação do usuário**, e só faz sentido depois do histórico completo (pegadinha 13).

**Pronto quando (seção 9, etapa 8): "Gatilho da seção 4, prazos e avisos funcionando".** Traduzindo:
- (a) `.venv\Scripts\python.exe -m pytest -q` sem falhas (os ~1220 + ~150 novos);
- (b) os testes de linha do tempo da seção 3 passam (coleta às 08:05, às 09:50, nunca; manual; daily de ontem às 21h; daily às 07:50; dois dailies; entrega `falhou`; `agendada`; dados atrasados; PC ligado tarde), com os valores esperados deste plano;
- (c) o teste ponta a ponta da rotina (SQLite de `tests/dados` + painel simulado + relógio falso) gera os 10 arquivos com `coleta_status` preenchido e aprovado pelo validador, e o caso "coleta não terminou" gera só o `execucao.json` com `falhou`;
- (d) **ação do usuário** (lê o banco; o subagente não roda): `python -m processamento.rotina --data <próximo pregão> --sem-esperar` sai com código 0 e o `execucao.json` traz `coleta_status.consultado = true`; e uma manhã real com o Agendador (seção 12) termina com status `ok`.

---

## 1. O que já existe e será reusado (não reescrever)

| Para quê | Função / constante | Onde |
|---|---|---|
| Orquestração dos 10 pacotes; `coleta_status` e `avisos_coleta` já são parâmetros | `gerar(d, *, ler, ..., agora, coleta_status, avisos_coleta, ...)` | `processamento/saida/gerar.py:71` |
| Rodada = a do `execucao.json` da pasta + 1 | `_rodada_anterior` | `gerar.py:48` |
| Registro e gravação do `execucao` | `_execucao`, `_gravar_execucao` | `gerar.py:56`, `:66` |
| Fechamento do dia anterior (hoje só o registro de t) | bloco `historico()` | `gerar.py:182-198` |
| Top do dia, escolha do modelo, registro (S11) | bloco `top()` | `gerar.py:200-219` |
| Coleta não consultada (formato atual) | `COLETA_NAO_CONSULTADA`, `AVISO_NAO_HOUVE` | `gerar.py:35`, `:37` |
| Códigos de saída da CLI (2, 3, 4) e leitor READ ONLY | `main`, `_leitor_padrao` | `gerar.py:261-310`, `processamento/experimento/dataset.py:144` |
| Modelo do mês ou o mais recente anterior (com aviso) | `escolher_modelo` | `processamento/saida/pacotes_experimento.py:85` |
| Validade do top (provisório, 10h, teste final) | `valido_para_historico` | `pacotes_experimento.py:112` |
| Sombras (modelo 1 e volatilidade) e probabilidades no registro interno | `gerar_top` (bloco `interno`) | `pacotes_experimento.py:135` (`:214-228`) |
| Registro de uso único do top (S11) | `ler_registro_top`, `registro_existente`, `gravar_registro_top` | `pacotes_experimento.py:238`, `:246`, `:254` |
| Fechar um dia (acerto, retorno vs IBOV, `resultado_incompleto`, sombras) | `pode_fechar`, `fechar_dia`, `gravar_resultado`, `ler_resultados` | `pacotes_experimento.py:277`, `:287`, `:347`, `:359` |
| Histórico (taxa acumulada, faixa do acaso) | `montar_historico` | `pacotes_experimento.py:369` |
| Validador (mini-linguagem com `"opcional"`, `"ou_nulo"`, `"enum"`) | `ESQUEMAS["execucao"]`, `_checar_objeto` | `processamento/saida/contrato.py:431-439`, `:291` |
| Data-hora em ISO de SP sem microssegundos | `data_hora_txt`, `SP` | `contrato.py:134`, `:31` |
| Leitura com trava (validador de SQL; READ ONLY por conexão) | `executar_leitura`, `verificar_sessao_somente_leitura`, `criar_engine` | `processamento/fontes.py:202`, `:181`, `:120` |
| Montar SELECT com nomes reais e crases | `_conferir_tabela`, `_selecionar`, `tabela_sql`, `coluna_sql` | `fontes.py:300`, `:318`, `:76`, `:81` |
| UTC sem fuso para São Paulo (**conferido** com o texto que o SQLite devolve: "2026-10-26 00:30:00" vira 2026-10-25 21:30-03:00) | `para_sao_paulo_de_utc` | `fontes.py:562` |
| Mapa das tabelas do painel (hoje sem `aguardando` e sem os horários das etapas) | `auxiliares.painel_execucoes`, `painel_etapas` | `processamento/config/fontes.yaml:79-84` |
| SQL do painel no diagnóstico (modelo de consulta) | `secao_painel` | `processamento/diagnostico/temas.py:809` |
| Etapas e status conhecidos da coleta | `ETAPAS_COLETA`, `STATUS_ETAPA`, `HORAS_DAILY_UTC` | `processamento/diagnostico/esperado.py:11`, `:15`, `:20` |
| Calendário, horários da B3, corte das 08:00 (`lru_cache`) | `carregar_parametros`, `_validar_data`, `_validar_hora`, `pregoes`, `horario_b3`, `corte_manha` | `processamento/calendario.py:110`, `:32`, `:47`, `:160`, `:168`, `:210` |
| Chaves de topo do yaml | `_CHAVES_DE_TOPO` | `calendario.py:21` |
| Padrão de bloco de parâmetros com validação | `carregar_parametros_saida` | `processamento/saida/parametros.py:62` |
| Parâmetros do treino | `ParametrosTreino`, `_CHAVES_TREINO`, `carregar_parametros_treino` | `processamento/experimento/parametros.py:183`, `:30`, `:320` |
| Configuração congelada (colunas + hiperparâmetros do desenvolvimento) | `_configuracao_congelada` | `processamento/experimento/treino.py:806` |
| Metadados, versões, início do experimento, registro do teste final | `_metadados`, `_versoes`, `_inicio_experimento`, `REGISTRO_TESTE_FINAL`, `AVISO_PROVISORIO`, `ErroPreRequisito` | `treino.py:743`, `:442`, `:74`, `:357`, `:361`, `:380` |
| Treinar e salvar | `treinar_xgb`, `salvar_modelo`, `nome_modelo`, `CHAVES_METADADOS` | `processamento/experimento/modelos.py:47`, `:123`, `:116`, `:26` |
| Ranks e linhas com alvo (mesma função do treino) | `preparar`, `linhas_de_treino`, `colunas_do_modelo` | `processamento/experimento/preparacao.py:47`, `:55`, `:60` |
| Walk-forward (mesmo corte do retreino) | `dobras_walk_forward` | `processamento/experimento/validacao.py:83` |
| Retornos, grade, pares do painel | `retornos_diarios`, `grade_de_precos`, `pares_do_painel` | `processamento/fatos/precos.py:145`, `:125`, `:305` |
| Percentual em português | `pct` | `processamento/experimento/relatorio.py:40` |
| Insumos de D (`t`, `cal`, `precos`, `cadastro`, `exclusoes`) | `Insumos`, `ler_insumos` | `processamento/saida/insumos.py:28`, `:46` |
| Fábricas de teste | `banco_teste`, `AGORA`, `dataset_sintetico`, `params_teste`, `precos_de`, `pregoes_uteis`, `cadastro_de`, `_salvar_modelos` (modelo pequeno), `_sem_banco_real` | `tests/conftest.py:29`, `tests/fabrica_saida.py:15`, `tests/fabrica_treino.py:26`, `:109`, `tests/fabrica_precos.py:32`, `:14`, `:63`, `tests/test_saida_gerar.py:46`, `:38` |

**O que a etapa 7 já faz e não muda:** `rodada` incrementa; S11 (com `fim` preenchido, a 2ª rodada reconstrói o top do registro; com `fim` vazio, sobrescreve); `fechar_dia` (ação sem preço → `superou: null`, `retorno {null, indisponivel}`, `resultado_incompleto: true`); `gravar_resultado` de uso único (`open("x")`); `montar_historico` só com dias válidos e depois do `fim`; sombras gravadas todo dia no registro interno.

**O que falta (esta etapa):** gatilho e espera; dia sem pregão; dados atrasados; trava; `coleta_status` ampliado; checagem diária; fechar **todos** os pendentes (o top de um dia em que a rotina não rodou nunca é fechado hoje) e descartar dia que não foi pregão; retreino mensal; comando de entrada em produção; script do Agendador.

---

## 2. Linha do tempo de um dia e os casos (item 1; decisões R2, R3, R4, R5)

Exemplo: **D = 2026-10-26 (segunda)**; t esperado = 2026-10-23 (sexta). `iniciada_em` vem em **UTC sem fuso**: 08:00 SP = 11:00 UTC (diagnóstico: `2026-10-23 11:00:01.489947`).

```
07:55  Agendador inicia a rotina -> trava -> D é pregão? -> t_esperado -> dorme até 08:00
08:00  consulta 1 (painel) ... a cada 5 min ...
       entrega concluida (+ preços frescos) -> gerar(D) ~2 min -> execucao ok -> solta a trava
09:45  prazo: sem entrega -> grava execucao "falhou" (sem pacotes) e CONTINUA consultando (R4)
12:00  prazo tardio: desiste; log "coleta não terminou até 12:00"
```

### 2.1 Escolha do daily (regra da seção 4)
Entre as execuções lidas: `tipo == "daily"`, `origem` em {`cron`, `manual`}, `iniciada_em` convertida para SP com **data == D** e **hora >= 08:00:00**; vale a de maior `iniciada_em`. Outros tipos (`coletar`, `etapa`) nunca servem. `manual` vira **nota** ("Daily manual (origem manual): disparado fora da agenda."). A consulta SQL já corta por `iniciada_em >= D 00:00 SP em UTC` (`D 03:00:00` UTC); a função pura refaz o filtro em SP (defesa em dobro).

### 2.2 Decisão a cada consulta (função pura `avaliar_painel`)
Em ordem:
1. Nenhum daily válido → `esperar`, motivo `sem_daily`.
2. Daily `agendada` (carga histórica com prioridade) → `esperar`, `daily_agendado`.
3. `entrega` = `concluida`:
   - `precos` diferente de `concluida` **e** o IBOV do banco não tem `t_esperado` → `esperar`, `dados_atrasados` (pode vir um daily manual mais novo);
   - senão → **`gerar`**, `entrega_concluida`; avisos: cada etapa de `etapas_conferidas` (`precos`, `noticias`, `enriquecimento`) que não está `concluida`; e, se `precos` concluída mas o IBOV não tem `t_esperado`, o aviso "a B3 pode não ter aberto" (R3).
4. `entrega` = `falhou`, ou execução `falhou` → `esperar`, `entrega_falhou` (um daily manual mais novo pode resolver; vale o mais recente).
5. Senão → `esperar`, `entrega_pendente`.
6. Exceção ao ler o painel (rede, MySQL) → `esperar`, `falha_consulta`. **A exceção `fontes.ErroSomenteLeitura` nunca é engolida**: a rotina para com código 3.

O laço (`esperar_coleta`) consulta em `max(agora, 08:00)` e depois a cada `intervalo`; se a próxima consulta passaria do prazo, consulta exatamente no prazo. Na primeira consulta com `agora >= 09:45` sem estar pronto, chama **uma vez** `ao_esgotar_prazo(resultado_parcial)` (a rotina grava o `execucao` `falhou`) e continua até `prazo_tardio` (12:00; `null` desliga e para às 09:45).

### 2.3 O que sai em cada caso (R2: recomendação; a seção 4, item 4, diz "gerar com os dados disponíveis")

| Caso | Fase 1 (`acoes` a `noticias_dia`) | `experimento_historico` (fecha pendentes) | `experimento_top` | `execucao` |
|---|---|---|---|---|
| Entrega `concluida` até 09:45, etapas ok | sim | sim | sim (validade pela 8.3) | `ok` (ou `parcial` se algum pacote falhar) |
| Daily `parcial` (ex.: só `analise` falhou) com entrega `concluida` | sim | sim | sim | `ok`; sem aviso (a `analise` não interessa) |
| Entrega `concluida`, `noticias`/`enriquecimento` não concluídas | sim + aviso | sim | sim + aviso; **validade não muda** (R5) | `ok` + aviso |
| Entrega `concluida`, `precos` não concluída e IBOV sem `t_esperado` (dados atrasados) | não | não | não | `falhou` às 09:45 (aviso) |
| Entrega `concluida`, `precos` concluída, IBOV sem `t_esperado` | sim (com o t real do banco) + aviso | sim | sim + aviso (se D−1 foi pregão de fato, o fechamento descarta o dia: seção 6) | `ok` + aviso |
| Entrega `falhou` / execução `falhou` (e nenhum daily mais novo) | não | não | não | `falhou` às 09:45 |
| Daily não começou / `agendada` / inexistente até 09:45 | não | não | não | `falhou` às 09:45 |
| Entrega ainda em andamento às 09:45 | não | não | não | `falhou` às 09:45 |
| Depois do `falhou`, a entrega conclui antes de 12:00 (R4) | sim (rodada 2) | sim | sim; `valido_para_historico = false` se gerado depois das 10:00 (o aviso já existe) | `ok`, rodada 2 |
| `--sem-esperar` | sim | sim | sim | conforme os pacotes; `coleta_status.motivo = "sem_esperar"` |

**Por que não "gerar com os dados disponíveis" (texto literal da 4.4):** as 8 tabelas da entrega são regravadas **por upsert, tabela por tabela, sem transação única** (`extracao-dados-tcc-main/docs/05-entrega.md`, "Gravação"). Antes da entrega de hoje, o `v1-precos` só vai até D−2 (o daily de ontem rodou às 8h, antes do pregão de ontem): o t lido seria D−2, a Fase 1 repetiria a de ontem e o top 5 usaria a linha de D−2 com uma janela de notícias de dois dias que o modelo nunca viu no treino. Durante uma entrega em andamento, a leitura ainda mistura tabelas novas e velhas. Gerar nesse estado entrega número errado com cara de certo. A alternativa "só a Fase 1" tem o mesmo problema da Fase 1 velha.

### 2.4 Textos exatos dos avisos e notas da coleta
- Etapa conferida não concluída: `"Coleta: etapa {etapa} {status} no daily de hoje; os dados podem estar incompletos."` (`status` = o texto do painel, ou `ausente` se a etapa não tem linha).
- IBOV sem t esperado, preços concluídos: `"Sem preço do IBOV em {t_esperado} (último no banco: {ultimo}): a B3 pode não ter aberto nesse dia; conferir feriados_b3 no parametros.yaml."`
- Desistência no prazo (`{prazo}` = `"09:45"`), um por motivo:
  - `sem_daily`: `"Coleta: nenhum daily de hoje (a partir das 08:00) até {prazo}; pacotes de hoje não gerados."`
  - `daily_agendado`: `"Coleta: o daily de hoje ainda não começou até {prazo} (aguardando a carga histórica); pacotes de hoje não gerados."`
  - `entrega_pendente`: `"Coleta: a entrega de hoje não terminou até {prazo}; pacotes de hoje não gerados."`
  - `entrega_falhou`: `"Coleta: a etapa entrega falhou no daily de hoje; pacotes de hoje não gerados."`
  - `dados_atrasados`: `"Coleta: preços de {t_esperado} ainda não chegaram (último pregão no banco: {ultimo}); pacotes de hoje não gerados."`
  - `falha_consulta`: `"Coleta: o painel da coleta não pôde ser lido até {prazo}; pacotes de hoje não gerados."`
- `--sem-esperar` com a coleta não pronta: `"Coleta: rodada com --sem-esperar; a coleta de hoje ainda não estava pronta ({motivo})."`
- Notas (`coleta_status.nota`): `"Daily da agenda (origem cron)."`; `"Daily manual (origem manual): disparado fora da agenda."`; `"Nenhum daily de hoje encontrado."`; com `--sem-esperar`, acrescenta `" Consulta única (--sem-esperar)."`.

---

## 3. Casos de teste do gatilho com VALORES ESPERADOS (item 2)

Parâmetros: `inicio_consulta 08:00`, `intervalo 5 min`, `prazo 09:45`, `prazo_tardio 12:00`. D = 2026-10-26, `t_esperado` = 2026-10-23, `ultimo_ibov` = 2026-10-23 salvo dito. Daily cron padrão: `id "2026-10-26-daily-080001"`, `iniciada_em` UTC `"2026-10-26 11:00:01.489947"`. Contas: de 08:00 a 09:45 são 105 min ÷ 5 = 21 intervalos → **22 consultas**; de 08:00 a 12:00, 240 ÷ 5 = 48 → **49 consultas**. `espera_segundos` = última consulta − primeira.

| # | Linha do tempo (horário SP) | Esperado |
|---|---|---|
| A | entrega `concluida` às 08:05:00 (`finalizada_em` UTC `11:05:00`) | pronto na 2ª consulta (08:00, 08:05); `consultas 2`, `espera_segundos 300`; `ao_esgotar_prazo` 0 vezes; `entrega_concluida_em "2026-10-26T08:05:00-03:00"`; motivo `entrega_concluida` |
| B | entrega conclui às 09:50 | 22 consultas até 09:45 com `entrega_pendente`; `ao_esgotar_prazo` 1 vez, chamado com `consultas 22`; pronto às 09:50: `consultas 23`, `espera_segundos 6600` (110 min) |
| B2 | idem, com `prazo_tardio: null` | não pronto; `consultas 22`, `espera_segundos 6300`; motivo `entrega_pendente` |
| C | entrega nunca conclui | não pronto; `consultas 49`, `espera_segundos 14400`; `ao_esgotar_prazo` 1 vez (às 09:45) |
| D | só daily **manual** `id "2026-10-26-daily-091000"`, `iniciada_em` UTC `12:10:00` (09:10 SP), entrega conclui 09:30 | motivo `sem_daily` até 09:05; pronto às 09:30: `consultas 19` (90 ÷ 5 + 1), `espera_segundos 5400`; `origem "manual"`; `nota "Daily manual (origem manual): disparado fora da agenda."`; avisos `[]` |
| E | **armadilha do fuso:** só um daily `concluida` com `iniciada_em` UTC `"2026-10-26 00:30:00"` (= **2026-10-25 21:30 SP**; em UTC a data é D!) | `escolher_daily` → `None`; não pronto; `ao_esgotar_prazo` com motivo `sem_daily` |
| F | só um daily com `iniciada_em` UTC `"2026-10-26 10:50:00"` (= **07:50 SP**; em UTC a hora passa de 08), entrega concluída 08:30 | `escolher_daily` → `None`; motivo `sem_daily` |
| G | dois dailies: cron 08:00:01 com entrega `falhou` às 08:40; manual `iniciada_em` UTC `12:00:00` (09:00 SP) com entrega concluída 09:25 | motivo `entrega_falhou` de 08:40 a 08:55; às 09:00 vale o manual (`entrega_pendente`); pronto às 09:25 com `execucao_id "2026-10-26-daily-090000"`; `consultas 18` (85 ÷ 5 + 1) |
| H | entrega `falhou` às 08:40, sem outro daily | `ao_esgotar_prazo` com motivo `entrega_falhou`; não pronto; `consultas 49` |
| I | daily `parcial`: entrega concluída 09:10, `analise` `falhou` | pronto às 09:10; `consultas 15`; avisos `[]` |
| J | entrega concluída 09:00, `enriquecimento` `falhou` | pronto às 09:00 (`consultas 13`); avisos `["Coleta: etapa enriquecimento falhou no daily de hoje; os dados podem estar incompletos."]` |
| K | `agendada` (aguardando `historico`) a manhã inteira | `ao_esgotar_prazo` com motivo `daily_agendado`; não pronto |
| K2 | `agendada` até 09:20, depois `em_andamento`, entrega conclui 10:30 | `ao_esgotar_prazo` às 09:45 com `entrega_pendente`; pronto às 10:30, `consultas 31` (150 ÷ 5 + 1) |
| L | entrega concluída 09:00, `precos` `falhou`, `ultimo_ibov = 2026-10-22` | nunca pronto; `ao_esgotar_prazo` com `dados_atrasados`; texto `"Coleta: preços de 2026-10-23 ainda não chegaram (último pregão no banco: 2026-10-22); pacotes de hoje não gerados."` |
| L2 | entrega e `precos` concluídas às 09:00, `ultimo_ibov = 2026-10-22` | pronto às 09:00 com o aviso `"Sem preço do IBOV em 2026-10-23 (último no banco: 2026-10-22): a B3 pode não ter aberto nesse dia; conferir feriados_b3 no parametros.yaml."` |
| M | relógio começa 08:37:00; entrega concluída 08:50 | consultas 08:37, 08:42, 08:47, 08:52 → pronto; `consultas 4`, `espera_segundos 900` |
| N | relógio começa 07:30:00 | o 1º `dormir` é de 1800 s; 1ª consulta às 08:00:00 |
| O | relógio começa 11:00 (PC ligado tarde); entrega concluída às 09:00 | pronto na 1ª consulta; `consultas 1`; `ao_esgotar_prazo` 0 vezes |
| O2 | relógio começa 11:00; entrega nunca conclui | `ao_esgotar_prazo` na 1ª consulta (11:00); consultas de 11:00 a 12:00 = 13; não pronto |
| P | `consultar` levanta `OperationalError` às 08:00 e funciona às 08:05 (entrega concluída) | pronto às 08:05; `consultas 2`; o erro não sobe |
| P2 | `consultar` levanta `fontes.ErroSomenteLeitura` | a exceção sobe na hora (nada de esperar) |
| Q | execução `tipo "coletar"` concluída às 09:00 (sem daily) | `escolher_daily` → `None` |
| R | `--sem-esperar` com entrega pendente às 08:10 | 1 consulta; `pronto = True`; `motivo "sem_esperar"`; aviso `"Coleta: rodada com --sem-esperar; a coleta de hoje ainda não estava pronta (entrega_pendente)."` |

**`coleta_status` esperado no caso A** (dicionário exato):
```json
{"consultado": true, "nota": "Daily da agenda (origem cron).", "motivo": "entrega_concluida",
 "execucao_id": "2026-10-26-daily-080001", "origem": "cron", "status_execucao": "em_andamento",
 "iniciada_em": "2026-10-26T08:00:01-03:00", "finalizada_em": null,
 "entrega_concluida_em": "2026-10-26T08:05:00-03:00",
 "etapas": {"precos": "concluida", "macro": "concluida", "noticias": "concluida", "ipe": "concluida",
            "enriquecimento": "concluida", "juiza": "concluida", "cadastro": "concluida",
            "entrega": "concluida", "analise": "pendente"},
 "consultas": 2, "primeira_consulta_em": "2026-10-26T08:00:00-03:00",
 "ultima_consulta_em": "2026-10-26T08:05:00-03:00", "espera_segundos": 300,
 "prazo": "2026-10-26T09:45:00-03:00", "t_esperado": "2026-10-23", "ultimo_pregao_lido": "2026-10-23"}
```
(os microssegundos de `iniciada_em` somem porque `contrato.data_hora_txt` usa `timespec="seconds"`).

---

## 4. D é pregão? Feriados da B3 (item 3; decisões R1, R8)

**Hoje:** o calendário só conhece pregões passados (datas com IBOV, `calendario.pregoes`, `calendario.py:160`). Sem saber se D é pregão, a rotina geraria top 5 em feriado e, pior, fecharia a janela de notícias de t às 08:00 de D, quando o próximo pregão de verdade é D+1 (o modelo foi treinado com a janela até o próximo pregão real).

**Recomendação (R1): lista de feriados da B3 no `parametros.yaml`**, com validade (`feriados_b3_valido_ate`), conferida automaticamente contra os pregões do banco (teste `@pytest.mark.banco`) e aviso 30 dias antes de vencer. Alternativas: biblioteca (`exchange_calendars`, calendário `BVMF`: dependência nova e pesada, que precisa ser atualizada a cada feriado novo, como o 20/11 nacional desde 2024); só "conferir no dia seguinte" (gera tops em feriado e janelas erradas; o fechamento descartaria o dia, mas a Fase 1 sairia repetida).

**Conferência com o banco:** os 25 dias úteis sem IBOV de 2024-07-29 a 2026-10-22 (`docs/diagnostico_banco.md`, seção 7) são exatamente os feriados abaixo até 2026-10-12. 09/07 (Revolução Constitucionalista) **teve pregão** em 2025 e 2026 (não está na lista de dias sem pregão), então não entra. 25/01 (aniversário de SP) caiu em fim de semana em 2025 e 2026: não dá para conferir no banco; a B3 abre nesse dia desde 2022 (**conferir**; em 2027 é segunda).

**Lista proposta** (dias úteis, seg a sex; sábados e domingos não entram: 2026-11-15 é domingo; 2027-05-01, 11-20 e 12-25 são sábado). **2026 depois de 12/10 e 2027 inteiro precisam ser conferidos no calendário oficial da B3** (b3.com.br, "Calendário de negociação"):

| Ano | Datas (motivo) |
|---|---|
| 2024 (conferido com o banco) | 11-15 (Proclamação da República), 11-20 (Consciência Negra), 12-24 (véspera de Natal, sem pregão), 12-25 (Natal), 12-31 (último dia do ano, sem pregão) |
| 2025 (conferido com o banco) | 01-01, 03-03 e 03-04 (Carnaval), 04-18 (Sexta-feira Santa), 04-21 (Tiradentes), 05-01, 06-19 (Corpus Christi), 11-20, 12-24, 12-25, 12-31 |
| 2026 | 01-01, 02-16 e 02-17 (Carnaval), 04-03 (Sexta Santa), 04-21, 05-01, 06-04 (Corpus Christi), 09-07, 10-12 (todos conferidos com o banco) + **11-02 (Finados, seg), 11-20 (sex), 12-24 (qui), 12-25 (sex), 12-31 (qui)** (a conferir) |
| 2027 (a conferir) | 01-01 (sex), 02-08 e 02-09 (Carnaval; Páscoa em 28/03), 03-26 (Sexta Santa), 04-21 (qua), 05-27 (Corpus Christi, qui), 09-07 (ter), 10-12 (ter), 11-02 (ter), 11-15 (seg), 12-24 (sex), 12-31 (sex) |

(Dias da semana e datas móveis conferidos com `dateutil.easter`.)

**Quarta-feira de Cinzas** (B3 abre às 13h): **é pregão**; o horário já é tratado em `dias_especiais` (`"2026-02-18": {abertura: "13:00"}`), que muda a janela do pregão no painel (`noticias_dia`). Acrescentar `"2027-02-10": {abertura: "13:00", motivo: "quarta-feira de cinzas"}` (a conferir). A janela do modelo (08:00:01 de t até 08:00 do próximo pregão) não depende da abertura. O limite das 10h da validade continua fixo (seção 15, item 6).

**Horários da B3 vencem em 2027-03-12** (`horarios_b3_valido_ate`): a partir de 13/03/2027, `calendario.horario_b3` levanta erro e a rotina pararia. Acrescentar (a conferir na B3): `{a_partir_de: "2027-03-15", abertura: "10:00", fechamento: "17:00"}` (o horário de verão dos EUA começa em 14/03/2027) e `{a_partir_de: "2027-11-08", abertura: "10:00", fechamento: "18:00"}` (termina em 07/11/2027), com `horarios_b3_valido_ate: "2027-12-31"`.

**Funções novas (`calendario.py`) e valores esperados:**
- `e_pregao_previsto(d)`: 2026-10-26 (seg) `True`; 2026-10-24 (sáb) e 2026-10-25 (dom) `False`; 2026-11-02 `False`; 2026-11-03 `True`; 2026-11-20 `False`; 2026-12-24 `False`; 2026-12-31 `False`; 2026-07-09 `True`; 2027-02-08 e 02-09 `False`; 2027-02-10 (Cinzas) `True`; 2028-01-03 → `ErroCalendario` ("lista de feriados da B3 vale até 2027-12-31; atualizar config/parametros.yaml").
- `pregao_anterior_previsto(d)`: (2026-10-26) → 2026-10-23; (2026-11-03) → 2026-10-30; (2026-11-23) → 2026-11-19 (20/11 é sexta de feriado); (2026-12-28) → 2026-12-23 (24 e 25 fechados); (2027-01-04) → 2026-12-30 (31/12 e 01/01 fechados); (2027-02-10) → 2027-02-05; (2025-10-22) → 2025-10-21.
- `primeiro_pregao_do_mes(d)`: 2026-11-03 `True`; 2026-11-04 `False`; 2026-12-01 `True`; 2027-01-04 `True`; 2026-11-02 `False` (não é pregão); 2026-10-26 `False`.
- `avisos_validade(d, dias=30)`: d = 2027-12-01 → `["Feriados da B3 cadastrados só até 2027-12-31: atualizar feriados_b3 no parametros.yaml.", "Horários da B3 cadastrados só até 2027-12-31: atualizar horarios_b3 no parametros.yaml."]`; d = 2027-11-30 → `[]` (31 dias); d = 2026-10-26 → `[]`.
- `conferir_feriados(cal, desde, ate)` → `{"sem_pregao_fora_da_lista": [...], "listados_com_pregao": [...]}`: com `cal` = dias úteis de 2026-10-19 a 2026-10-23 sem o 2026-10-21 e a lista real → `{"sem_pregao_fora_da_lista": ["2026-10-21"], "listados_com_pregao": []}`; com `cal` = todos os dias úteis de 2026-10-05 a 2026-10-16 (inclusive 2026-10-12) → `listados_com_pregao: ["2026-10-12"]`.

**Dia sem pregão (R8):** a rotina sai com código 0, sem gravar nada em `saida/` (só a linha no log: `"2026-11-02 não é pregão (Finados): nada a fazer."`). Não grava `execucao`: o enum de status do contrato não tem "sem pregão", e a interface continua mostrando o último dia.

**Dia que se descobre não ter sido pregão** (B3 fechou sem aviso; a lista errou): na rotina seguinte, o IBOV não tem o t esperado mas `precos` concluiu → segue com aviso (caso L2). O top gerado nesse dia é descartado pelo fechamento (seção 6, `nao_houve_pregao`).

---

## 5. Rodar duas vezes e trava (item 4; decisão R14)

- **Já implementado:** `rodada` = `_rodada_anterior + 1` (`gerar.py:48`); S11 (registro de uso único com `fim` preenchido; com `fim` vazio, sobrescreve); `gravar_resultado` com `open("x")`. A API grava por upsert: reenviar não duplica.
- **O `execucao` `falhou` gravado pela rotina** usa a mesma pasta e a mesma numeração (função nova `gerar.registrar_execucao`): o falhou das 09:45 é a rodada 1; a tardia é a rodada 2.
- **Rodar de novo no mesmo dia é permitido** (ex.: o usuário roda à mão depois de um `falhou`): a nova rodada consulta o painel, acha a entrega concluída na 1ª consulta e gera. Com `fim` preenchido, o top não muda (S11).
- **Trava (R14): arquivo** `saida/estado/rotina.trava` criado com `os.open(..., O_CREAT | O_EXCL | O_WRONLY)` (atômico no Windows e no Linux), com `{"pid", "criada_em"}`. Já existe e tem menos de 6 h → `ErroTrava` (código 5, nada gravado, mensagem `"outra rotina em andamento desde {criada_em} (pid {pid})"`). Mais velha que 6 h → é considerada abandonada (o PC desligou no meio): apaga, registra no log e segue. Sai sempre no `finally`. Alternativa: `msvcrt.locking`/`fcntl` (difere entre sistemas; a trava some sozinha se o processo morre, mas é mais difícil de testar).
- Casos de teste: (1) duas travas aninhadas → a 2ª levanta `ErroTrava`; (2) arquivo com `criada_em` 7 h antes do relógio → adquire; (3) com 5 h → `ErroTrava`; (4) exceção dentro do bloco → arquivo apagado; (5) E2E: rotina com a trava ocupada → código 5 e nenhuma pasta `saida/D/` criada.

---

## 6. Fechar o histórico (item 5; decisão R12)

**O que já faz:** na rodada de D, fecha só o registro de t (`gerar.py:185-191`). **Buraco:** se a rotina não rodar num dia (PC desligado), o top da véspera nunca é fechado; o top de um dia que não foi pregão nunca é fechado nem marcado.

**Recomendação (R12): `fechar_pendentes`** em `pacotes_experimento.py`: varre todos os `AAAA-MM-DD.top.json` com pregão previsto D' <= t, sem `.resultado.json` nem `.descartado.json`:
1. `pode_fechar(registro, fim)` falso (registro inválido, `fim` vazio, D' <= `fim`) → ignora, sem aviso;
2. D' no calendário e o pregão anterior a D' no calendário igual ao `pregao_base` do registro → `fechar_dia` → `gravar_resultado`;
3. D' no calendário, mas o anterior diferente do `pregao_base` → grava `D'.descartado.json` com motivo `pregao_base_diferente` e o aviso `"top 5 de {D'} foi gerado com pregão base {base}, mas o pregão anterior a {D'} foi {real}; dia descartado"`;
4. D' fora do calendário e existe pregão no calendário depois de D' → `D'.descartado.json` com motivo `nao_houve_pregao` e o aviso que já existe: `"pregão previsto {D'} não houve; dia descartado"`;
5. D' fora do calendário e nenhum pregão depois → espera (não faz nada).

`AAAA-MM-DD.descartado.json` = `{"data_referencia", "motivo", "descartado_em"}`, de uso único (`open("x")`). `ler_resultados` continua lendo só `*.resultado.json`. Nada é recalculado: arquivo existente nunca é tocado.

**Gabarito (conferido com `fechar_dia` e `montar_historico` sobre `precos_de`):** cal = [2026-10-30, 2026-11-03, 2026-11-04]; `fim = 2026-11-02`; candidatos AAAA3 a FFFF3; `aj` por pregão:

| ticker | 10-30 | 11-03 | 11-04 |
|---|---|---|---|
| IBOV | 100 | 101,5 | 102,515 |
| AAAA3 | 20 | 20,5 | 20,5 |
| BBBB3 | 50 | 50,5 | 51,5 |
| CCCC3 | 10 | 10,2 | 10,0 |
| DDDD3 | 8 | 7,9 | 8,1 |
| EEEE3 | 40 | 41 | 41,2 |
| FFFF3 | 10 | 10,3 | 10,4 |

- Registro **2026-11-03** (base 10-30), ranking AAAA3, BBBB3, CCCC3, DDDD3, EEEE3; sombras: modelo 1 [FFFF3, AAAA3, BBBB3, CCCC3, DDDD3], volatilidade [BBBB3, DDDD3, EEEE3, FFFF3, AAAA3]. Retorno do IBOV `0.014999999999999902`; AAAA3 `0.02499999999999991` (superou), BBBB3 `0.010000000000000009` (não), CCCC3 `0.020000000000000018` (sim), DDDD3 `-0.012499999999999956` (não), EEEE3 `0.02499999999999991` (sim). → `acertos_dia 3`, `acertos_top3 2`, `resultado_incompleto false`, `alvos_candidatos {AAAA3: 1.0, BBBB3: 0.0, CCCC3: 1.0, DDDD3: 0.0, EEEE3: 1.0, FFFF3: 1.0}`, `acertos_sombra_modelo_1 3`, `acertos_sombra_volatilidade 3`.
- Registro **2026-11-04** (base 11-03), ranking BBBB3, DDDD3, FFFF3, EEEE3, CCCC3; sombras: modelo 1 [AAAA3, BBBB3, CCCC3, DDDD3, EEEE3], volatilidade igual à de cima. IBOV `0.010000000000000009`; BBBB3 `0.01980198019801982` (sim), DDDD3 `0.025316455696202445` (sim), FFFF3 `0.009708737864077666` (não), EEEE3 `0.004878048780487809` (não), CCCC3 `-0.019607843137254832` (não) → `acertos_dia 2`, `acertos_top3 2`, sombras 2 e 2.
- `montar_historico` com os dois (D = 2026-11-05, `acaso_sorteios 10000`, `semente 20261023`): `n_dias 2`, `periodo_inicio "2026-11-03"`, `periodo_fim "2026-11-04"`, `taxa_acerto {0.5, ok}` (5 ÷ 10), `acaso_media {0.4997400000000001, ok}` (approx 1e-9), `acaso_faixa [0.4, 0.6000000000000001]` (approx 1e-9), `dia.data_referencia "2026-11-04"`, `dia.taxa_acumulada {0.5, ok}`.

**Casos de teste (Fase 5):**
1. "Rotina pulou um dia": só o registro 11-03; `fechar_pendentes(pasta, precos, cal, t=2026-11-04, fim=2026-11-02, agora)` → cria `2026-11-03.resultado.json` com os valores acima; avisos `[]`. (Com o código de hoje, a rodada de 11-05 procuraria o registro de 11-04, que não existe, e o 11-03 nunca fecharia.)
2. Chamar de novo → nada muda (bytes iguais), avisos `[]`.
3. Registros 11-03 e 11-04 → os dois resultados; o histórico dá os números acima.
4. Registro 11-03 com `valido_para_historico: false` → nenhum arquivo, avisos `[]`.
5. `fim = None` com registro válido → nenhum arquivo.
6. Registro D' = 2026-11-25 (base 11-24), cal = [11-24, 11-26], t = 11-26 → `2026-11-25.descartado.json` com motivo `nao_houve_pregao`; aviso `"pregão previsto 2026-11-25 não houve; dia descartado"`. Com cal = [11-24] e t = 11-24 → nada (D' > t).
7. Registro D' = 2026-11-26 com base 11-24 e cal = [11-24, 11-25, 11-26] → descartado `pregao_base_diferente`; aviso `"top 5 de 2026-11-26 foi gerado com pregão base 2026-11-24, mas o pregão anterior a 2026-11-26 foi 2026-11-25; dia descartado"`.
8. Ação do ranking sem preço em D' (gabarito da etapa 7, `docs/plano_etapa7.md` seção 8: EEEE3 sem preço) → `resultado_incompleto true`, `acertos_dia 2`.
9. Registro com D' = t + 1 (o top de hoje) → ignorado.

---

## 7. Retreino mensal (item 6; decisões R6, R7)

**Quando (R6): dentro da rotina, depois da entrega e antes do top**, no `gerar` (gancho `retreinar`), sempre que o arquivo `modelos/xgb-<mês de D>.json` não existir **e** `treino.teste_final.fim` estiver preenchido (produção). Motivo: o corte precisa do preço do último pregão do mês anterior, que só chega no daily do 1º pregão do mês quando esse pregão é o dia seguinte; e o treino leva segundos (medido). Alternativas: tarefa noturna (o preço do último pregão pode ainda não estar no banco; mais uma tarefa agendada); depois da rotina (o top do 1º dia do mês sairia com o modelo do mês anterior).
- **Corte fixo:** treino = pregões do dataset **antes do dia 1 do mês de D**, menos o último deles (embargo de 1 pregão), a partir do início da cobertura de notícias (F4), só linhas com alvo. É o mesmo treino da dobra do mês no walk-forward (`dobras_walk_forward`). Por isso, se o retreino falhar no 1º pregão e rodar no 2º, o modelo sai **idêntico** (mesmas linhas).
- **Configuração congelada:** colunas do modelo 3 e do modelo 1, blocos e hiperparâmetros vêm de `treino._configuracao_congelada` (metadados do desenvolvimento, `xgb-<mês de teste_final.inicio>`); nunca re-escolhidos.
- **Grava** primeiro `xgb-m1-AAAA-MM.json` (+ `.meta.json`), depois `xgb-AAAA-MM.json` (o arquivo do modelo 3 é o sinal de "pronto").
- **Metadados** (todas as `CHAVES_METADADOS`, mais `retreino`): `modelo`, `versao_noticias "todas"`, `colunas`, `blocos`, `hiperparametros`, `semente`, `periodo_treino {inicio, fim}`, `n_linhas_treino`, `dataset {"arquivo": null, "sha256": <sha256 do CSV das linhas de treino: data, ticker, colunas, alvo>}`, `universo`, `metricas_validacao` (copiadas do desenvolvimento, com `"origem": "desenvolvimento"`: o retreino não valida de novo), `calibracao` (a do desenvolvimento no modelo 3; `null` no 1), `provisorio` (R7), `aviso`, `versoes`, `gerado_em`, `teste_final {inicio, fim, usado}`, `retreino {"mes", "configuracao_de", "corte_antes_de"}`.
- **Falha** (qualquer exceção) → aviso `"Retreino de {mes} falhou ({TipoDoErro}): usando o modelo anterior."`, e o `escolher_modelo` já cai no mais recente com o aviso `"Modelo de AAAA-MM (o do mês de D ainda não foi treinado)."` (S10).
- **Antes da produção** (`fim` vazio): sem retreino; segue o `xgb-2026-06` provisório com o aviso de sempre.
- **Provisório (R7):** chave nova `treino.modelo_oficial: false`. O usuário só põe `true` quando o histórico completo chegar e o desenvolvimento for refeito com ele (pegadinha 13). `provisorio = not modelo_oficial` no retreino e em `treino._metadados` (hoje fixo em `True`, `treino.py:764`).
- **Sombras:** já gravadas todo dia (`interno.sombra_modelo_1`, `sombra_volatilidade`) e conferidas no fechamento (`acertos_sombra_*`). Nada a fazer.
- **Tempo contra o prazo:** retreino ~1,2 s hoje e ~5 s com 5 anos (medido); `gerar` 1 min 54 s hoje (medido); com 5 anos, estimativa de 3 a 5 min (as grades crescem; as séries só calculam a janela de 253). Entrega concluída às 09:45 → pacotes prontos por volta de 09:50, antes das 10:00. O `gerado_em` é o início da rodada.

**Casos de teste (Fase 6)**, dataset `dataset_sintetico(inicio="2026-08-03", n_pregoes=70, n_tickers=12)` (pregões de 2026-08-03 a 2026-11-06, dias úteis; conferido), `params = params_teste(teste_final_fim=date(2026, 10, 30))` (o dev fica em `xgb-2026-01`), metadados de desenvolvimento salvos em `tmp/modelos/xgb-2026-01.meta.json` e `xgb-m1-2026-01.meta.json`, `info = {"cobertura_inicio": "2026-08-03"}`:
1. D = 2026-11-03, dataset cortado em `data <= 2026-10-30` com o alvo de 10-30 apagado (como ao vivo): `datas_de_treino(cal, "2026-11", 1)` = 64 pregões, de 2026-08-03 a 2026-10-29 (conferido); grava os 4 arquivos; `meta["n_linhas_treino"] == 768` (64 × 12; conferido); `periodo_treino == {"inicio": "2026-08-03", "fim": "2026-10-29"}`; `retreino.corte_antes_de == "2026-11-01"`; `colunas` e `hiperparametros` iguais aos do dev; `provisorio is True`; avisos `[]`.
2. Chamar de novo → `[]` e arquivos com os mesmos bytes (não retreina).
3. D = 2026-11-04 com o dataset até 2026-11-03 (alvo de 10-30 agora preenchido, alvo de 11-03 apagado) numa pasta nova → mesmo `n_linhas_treino` 768 e mesmo período; probabilidades do modelo nas linhas de 10-30 iguais às do caso 1 (`np.allclose`, atol 0).
4. Vazamento: inverter o alvo de todas as linhas com data >= 2026-11-01 → probabilidades idênticas.
5. `teste_final_fim = None` → `[]` e nenhum arquivo.
6. Sem os metadados do dev → `ErroPreRequisito` (o gancho do `gerar` transforma em aviso).
7. `params` com `modelo_oficial=True` → `provisorio is False`, `aviso is None`.

---

## 8. `coleta_status` ampliado (item 7; decisão R9)

Campos novos **opcionais** (o formato atual `{consultado: false, nota: ...}` continua válido, e os testes da etapa 7 não mudam). Status lidos do painel ficam como **texto** (não enum): se a coleta criar um status novo, o `execucao` continua sendo gravado.

| Campo | Tipo no validador | Origem |
|---|---|---|
| `consultado` | `bool` | painel lido |
| `nota` | `texto` | seção 2.4 |
| `motivo` | opcional, enum `entrega_concluida`, `entrega_pendente`, `entrega_falhou`, `sem_daily`, `daily_agendado`, `dados_atrasados`, `falha_consulta`, `sem_esperar` | decisão da última consulta |
| `execucao_id`, `origem`, `status_execucao` | opcional `texto?` | `v1-painel_execucoes` |
| `iniciada_em`, `finalizada_em`, `entrega_concluida_em` | opcional `data_hora?` (SP) | `iniciada_em`/`finalizada_em` (UTC para SP) |
| `etapas` | opcional; objeto com as 9 etapas, cada uma opcional `texto?` | `v1-painel_etapas` (`null` = sem linha) |
| `consultas`, `espera_segundos` | opcional `inteiro` | laço |
| `primeira_consulta_em`, `ultima_consulta_em`, `prazo` | opcional `data_hora?` | relógio |
| `t_esperado`, `ultimo_pregao_lido` | opcional `data?` | calendário e `fontes.ultimo_pregao_ibov` |

**`versao_contrato` continua `"1.0"`**: a 8.3 registra que o contrato ainda não está em uso (a etapa 7 já trocou o `chance` sem subir). Registrar a mudança na 8.3 (seção 13).

**Testes (Fase 4):** o dicionário do caso A (seção 3) passa; o `COLETA_NAO_CONSULTADA` atual passa; campo desconhecido (`"xyz": 1`) → erro com `coleta_status.xyz: campo desconhecido`; `motivo: "outro"` → erro; `consultas: 2.5` → erro; `iniciada_em: "2026-10-26 08:00:01"` (sem `T` nem fuso) → erro; `etapas.precos: "status_novo_da_coleta"` → passa; `etapas.xyz` → erro.

---

## 9. Checagem diária da seção 6 (item 8; decisão R10)

Avisos no `execucao` (nunca bloqueiam nada). Limites no bloco `rotina.checagem`. Funções puras em `processamento/rotina/checagem.py`; o `gerar` chama depois de montar os pacotes (só se receber `checagem`).

| Regra | Definição | Texto exato |
|---|---|---|
| Poucas ações | ações dos pares do painel (ON, PN, UNIT, sem excluídos; `pares_do_painel`) com `fechamento_ajustado` em t (a mesma regra de "sem preço" do universo, `universo.py:78`) < `acoes_minimo_fracao` (0,9) × total | `"Checagem: só {n} de {m} ações (ON, PN e UNIT) com preço em {t}."` |
| Retorno acima de 30% | módulo de `aj(t)/aj(t−1) − 1` > `retorno_maximo_abs` (0,30) (`retornos_diarios`; precisa dos dois preços) | `"Checagem: retorno do dia acima de 30% em módulo em {t}: AAAA3 (35,0%), BBBB3 (-31,0%)."` (`pct`, em ordem de ticker) |
| Volume zero | `volume == 0` (não vazio) em t | `"Checagem: volume zero em {t}: {tickers}."` |
| Preço parado | mesmo `fechamento` nos últimos `preco_parado_pregoes` (5) pregões do calendário até t, todos preenchidos (pares + IBOV) | `"Checagem: preço parado (mesmo fechamento nos últimos 5 pregões até {t}): {tickers}."` |
| Indicador vazio (mercado) | `status == "indisponivel"` em `IBOV.fechamento`, `USDBRL.fechamento`, `BRENT.fechamento`, `cdi_dia`, `ipca_12m` do `mercado_dia` (`historico_insuficiente` não conta) | `"Checagem: indicador vazio em {t}: USDBRL.fechamento."` |
| Indicador vazio (ações) | `indisponivel` em **todas** as ações do `resumo_acao` para `cotacao.fechamento`, `rentabilidade.d1`, `volume.total`, `volatilidade_20d`, `beta`, `pvp`, `dividend_yield` | `"Checagem: indicador vazio em todas as ações em {t}: pvp."` |

Listas com mais de `max_tickers_por_aviso` (10) tickers: os 10 primeiros e `" e mais {k}"` antes do ponto final.

**Gabarito (Fase 7, à mão):** `cal = pregoes_uteis(6)` = 2025-01-02, 01-03, 01-06, 01-07, 01-08, 01-09; t = 2025-01-09; pares AAAA3 a JJJJ3 (10); IBOV com fechamento 100, 101, 102, 101, 103, 104.
- AAAA3 fech 10; 10,1; 10,2; 10,3; 10; 13,5 → retorno 0,35 (13,5/10 − 1 = 0.3500000000000001) → listada "35,0%";
- BBBB3 10; 10; 10,1; 10,2; 10; 6,9 → −0,31 → "-31,0%";
- CCCC3 10; 10,1; 10,2; 10,3; 10; 12,9 → 0,29 → não entra;
- DDDD3 10; 10,1; 10,2; 10,1; 10,2; 10,3 com volume 1000 nos 5 primeiros e **0** em t → volume zero;
- EEEE3 9; 10; 10; 10; 10; 10 → 5 iguais → parado; FFFF3 9; 9,5; 10; 10; 10; 10 → só 4 iguais → não entra;
- GGGG3 e HHHH3 variando; IIII3 e JJJJ3 sem preço em t → 8 de 10 (8 < 9).

Esperado, nesta ordem: `["Checagem: só 8 de 10 ações (ON, PN e UNIT) com preço em 2025-01-09.", "Checagem: retorno do dia acima de 30% em módulo em 2025-01-09: AAAA3 (35,0%), BBBB3 (-31,0%).", "Checagem: volume zero em 2025-01-09: DDDD3.", "Checagem: preço parado (mesmo fechamento nos últimos 5 pregões até 2025-01-09): EEEE3."]`. Com 4 pregões só (`pregoes_uteis(4)`), a regra do preço parado não roda. Com 12 tickers de volume zero e máximo 10 → `"...: AAAA3, BBBB3, CCCC3, DDDD3, EEEE3, FFFF3, GGGG3, HHHH3, IIII3, JJJJ3 e mais 2."`.
Indicadores: `mercado` com USDBRL `{null, indisponivel}` e `ipca_12m {null, historico_insuficiente}` → `["Checagem: indicador vazio em 2025-10-21: USDBRL.fechamento."]`; `resumo` com 2 ações e `pvp` `indisponivel` nas duas → `["Checagem: indicador vazio em todas as ações em 2025-10-21: pvp."]`; uma das duas com `pvp` ok → `[]`.
**No E2E** (`banco_teste`, t = 2025-10-21): pares = ABEV3, ITUB4, NOVA3, PETR3, PETR4, TAEE11 (6; JBSS32 é BDR, CRFB3 excluída), com preço em t só NOVA3, PETR3, PETR4 e TAEE11 (as 4 candidatas do gabarito da etapa 7) → o `execucao` contém `"Checagem: só 4 de 6 ações (ON, PN e UNIT) com preço em 2025-10-21."` e `"Checagem: indicador vazio em 2025-10-21: USDBRL.fechamento."` (o USDBRL não está no banco de teste). O implementador confere esses dois rodando; se não baterem, para e avisa.

---

## 10. Entrada em produção (item 9; decisão R11): decisão e ação do usuário

**Ponto central (pegadinha 13):** enquanto o modelo for provisório, `valido_para_historico` é `false` em todo dia (`valido_para_historico`, `pacotes_experimento.py:121`). Entrar em produção agora gastaria o teste final (uso único) com a configuração escolhida em ~1 ano e deixaria o histórico ao vivo vazio. **Recomendação: entrar em produção só depois do histórico completo**, com o desenvolvimento refeito (blocos e grade escolhidos com 5 anos) e `treino.modelo_oficial: true`. Até lá, a rotina roda todo dia em "teste de funcionamento" (`fim` vazio): Fase 1 de verdade, top 5 marcado como provisório, histórico vazio, sem retreino. Esse já é o comportamento de hoje.

**Ordem dos passos** (D0 = 1º dia em produção; recomendo D0 = 1º pregão de um mês, para o teste ao vivo começar com um modelo retreinado e alinhado aos meses do walk-forward):
1. Histórico completo no banco; regerar os datasets e rodar o treino de desenvolvimento com `modelo_oficial: true` (o `.meta.json` do dev sai com `provisorio: false`).
2. `python -m processamento.producao --inicio D0` (conferências, sem gravar nada): D0 é pregão previsto e futuro; `fim = pregao_anterior_previsto(D0)`; `treino.teste_final.fim` vazio (ou já igual a esse `fim`); `docs/teste_final_usado.json` não existe; `modelo_oficial: true` e dev não provisório; nenhum `*.resultado.json` em `registros/experimento/`. Imprime os problemas e o que fazer.
3. `python -m processamento.producao --inicio D0 --confirmar`: move os `*.top.json` dos testes de funcionamento para `registros/experimento/funcionamento-<hoje>/` (não apaga; `ler_resultados` e `fechar_pendentes` só olham a pasta de cima) e grava `docs/producao.json` (`inicio`, `fim`, `confirmado_em`, `registros_arquivados`). **Não edita o `parametros.yaml`.**
4. O usuário edita o `parametros.yaml`: `treino.teste_final.fim: "<fim>"` e `liberado: true` (data entre aspas). Daqui em diante, a rotina de D0 grava registros de uso único, fecha os dias, e o `experimento_historico` passa a ter dias.
5. Em D0 ou depois (o preço do `fim` já está no banco): `python -m processamento.experimento.dataset --versao <todas|principais|hora_real_noite> --ate <fim> --proximo <D0>` (as três versões) e `python -m processamento.experimento.treino --data <data do arquivo> --teste-final` **uma única vez** (trava F2). O teste final não afeta o teste ao vivo.

`fim` = pregão anterior a D0 (equivale à "véspera" da 7.5 pela regra da borda: a linha do `fim` tem o alvo em D0 e é a 1ª previsão ao vivo).

**Casos de teste (Fase 9)**, hoje = 2026-10-23, pastas temporárias: D0 = 2026-11-03 com tudo certo → `fim 2026-10-30`, problemas `[]`; D0 = 2026-11-02 → problema `"2026-11-02 não é pregão previsto"`; D0 = 2026-10-23 → `"D0 precisa ser depois de hoje (2026-10-23)"`; `modelo_oficial False` → `"modelo ainda provisório (treino.modelo_oficial: false): com o histórico curto o modelo não é treinado para valer (pegadinha 13) e nenhum dia entraria no histórico"`; registro do teste final existente → `"teste final já usado (docs/teste_final_usado.json)"`; `fim` já preenchido com 2026-10-29 → `"treino.teste_final.fim já está preenchido com 2026-10-29"`; um `*.resultado.json` na pasta → problema `"já existe resultado fechado em registros/experimento: conferir antes de entrar em produção"`; `--confirmar` move `2026-10-23.top.json` para `funcionamento-2026-10-23/` e grava `producao.json` com `{"inicio": "2026-11-03", "fim": "2026-10-30", ...}`; com problemas, `--confirmar` não move nada (código 1).

---

## 11. Ponto de entrada e fluxo (`python -m processamento.rotina`)

```
python -m processamento.rotina [--data AAAA-MM-DD] [--sem-esperar]
                               [--pasta saida] [--pasta-modelos modelos] [--pasta-registros registros/experimento]
```
- Sem `--data`: D = `relogio.agora().date()` em São Paulo.
- `--sem-esperar`: uma consulta ao painel (informativa), gera na hora (motivo `sem_esperar`), sem prazo nem rodada tardia.
- Códigos: 0 = `ok`, `parcial` ou dia sem pregão; 2 = configuração (banco ou parâmetros/calendário vencido); 3 = conexão ou sessão não READ ONLY; 4 = `falhou` (coleta não pronta ou `gerar` sem nenhum pacote); 5 = outra rotina em andamento (trava).
- Log em `logs/rotina-AAAA-MM-DD.log` (o `.gitignore` já ignora `*.log`) e no console: uma linha por consulta (`"08:05:00 consulta 2: daily 2026-10-26-daily-080001 (cron, em_andamento), entrega concluida -> gerar"`), o resultado e os avisos. Nunca o texto original de erro de conexão (pode ter host ou usuário).
- No Windows, enquanto espera, pede ao sistema para não suspender (`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` por `ctypes`, desfeito no fim; nada fora do Windows).

**Fluxo de `executar_rotina`:**
1. D; trava; `e_pregao_previsto(D)` (não → log e código 0); `t_esperado = pregao_anterior_previsto(D)`; `avisos_validade(D)`.
2. Leitor READ ONLY (`dataset._leitor_padrao`); `consultar` = `montar_consulta(ler, D)` (lê as execuções desde D 00:00 SP, escolhe o daily, lê as etapas dele e o último IBOV <= D − 1 dia).
3. `esperar_coleta(...)` com `ao_esgotar_prazo` = grava o `execucao` `falhou` (`gerar.registrar_execucao`) com o aviso da desistência + os avisos de calendário.
4. Pronto → `gerar(D, ler=..., agora=relogio.agora(), coleta_status=res.coleta_status(), avisos_coleta=res.decisao.avisos + avisos_calendario, usar_estado=True, retreinar=<gancho>, checagem=params.checagem, ...)`.
5. Código pelo status do `execucao.json`.

**Mudanças no `gerar` (Fase 8; parâmetros novos com padrão `None`, os testes atuais não mudam):**
- `retreinar: Callable[[pd.DataFrame, dict, list[date], date], list[str]] | None`: chamado em `top()` antes de `escolher_modelo`, dentro de `try`; exceção → aviso de falha do retreino (seção 7).
- `checagem: ParametrosChecagem | None`: depois do laço dos pacotes, `avisos_do_dia(ins.precos, ins.cal, ins.t, pares_do_painel(ins.cadastro, ins.exclusoes), checagem)` + `avisos_indicadores(<registro do mercado_dia>, <registros do resumo_acao>, ins.t, checagem)`.
- `dataset()` guarda `(df, info)`; `top()` usa o `df`; o gancho recebe os dois.
- `historico()`: troca o bloco do registro de t por `avisos.extend(pacotes_experimento.fechar_pendentes(pasta_registros, ins.precos, ins.cal, ins.t, fim, agora))`.
- Função pública nova `registrar_execucao(d, status, *, coleta_status, avisos, agora, pasta_saida=None, params_saida=None) -> Path` (usa `_rodada_anterior`, `_execucao`, `_gravar_execucao`; `inicio = fim = agora`; `pacotes_enviados = []`).

**Teste ponta a ponta (Fase 8)**, `banco_teste` (D = 2025-10-22, quarta; t = 2025-10-21 = `pregao_anterior_previsto`), modelos pequenos (`_salvar_modelos` de `tests/test_saida_gerar.py`), relógio falso, `consultar` falso (painel montado na mão), todas as pastas em `tmp_path`:
1. Relógio 07:55; daily cron `iniciada_em` UTC `"2025-10-22 11:00:01"`; entrega concluída às 08:05 → 1º `dormir` de 300 s; `saida/2025-10-22/` com os 10 arquivos, todos aprovados por `contrato.validar_lote`; `execucao.rodada 1`, `status "ok"`; `coleta_status.consultas 2`, `espera_segundos 300`, `motivo "entrega_concluida"`, `execucao_id "2025-10-22-daily-080001"`; `experimento_top.gerado_em "2025-10-22T08:05:00-03:00"`; os avisos contêm as duas linhas de checagem da seção 9; código 0.
2. Entrega nunca conclui, `prazo_tardio null` → só o `execucao.json`, `status "falhou"`, `pacotes_enviados []`, avisos com `"Coleta: a entrega de hoje não terminou até 09:45; pacotes de hoje não gerados."`; `coleta_status.consultas 22`; código 4.
3. Entrega conclui às 09:50 (`prazo_tardio 12:00`) → `execucao.json` final com `rodada 2`, `status "ok"`, `gerado_em "2025-10-22T09:50:00-03:00"`; o `experimento_top` tem `valido_para_historico false`.
4. D = 2025-10-25 (sábado) e D = 2025-11-20 (feriado) → código 0, `consultar` nunca chamado, a pasta `saida/<D>` não existe.
5. Trava ocupada → código 5, nada gravado.
6. `--sem-esperar` com entrega pendente → 10 arquivos; `coleta_status.motivo "sem_esperar"`; o aviso da seção 2.4.
7. Duas execuções seguidas da rotina (entrega concluída) → `execucao.rodada 2`.
8. Produção simulada: `params_treino` com `teste_final_fim = 2025-10-21` e a pasta de modelos só com `xgb-2025-09` (+ m1) → o gancho tenta o retreino de 2025-10 e falha (sem os metadados do dev) → avisos com `"Retreino de 2025-10 falhou (ErroPreRequisito): usando o modelo anterior."` e `"Modelo de 2025-09 (o do mês de D ainda não foi treinado)."`; `experimento_top` gerado; status `ok`.
9. `montar_consulta` com SQLite próprio (tabelas `v1-painel_execucoes`, `v1-painel_etapas` e `v1-precos` gravadas com `DataFrame.to_sql`) devolve o `Painel` esperado (o daily de D, as etapas dele, `ultimo_ibov`).
10. `_sem_banco_real` (troca `fontes.criar_engine` por uma função que interrompe o teste) ativo em todos os testes da rotina.

---

## 12. Onde a rotina roda todo dia às 8h (item 10; decisão R13): decisão do usuário

O banco da coleta fica num servidor MySQL acessado pela internet; a porta 3306 já está aberta para origens variáveis porque o Railway não tem IP fixo (`extracao-dados-tcc-main/docs/08-operacao-e-deploy.md`, seção 4). O estado do processamento é local: `.env`, `modelos/` (fora do git), `registros/experimento/` (versionável), `saida/estado/` (fora do git, ~3,4 MB hoje) e os logs.

| | (a) PC do usuário + Agendador de Tarefas | (b1) Mesmo servidor do MySQL (cron) | (b2) Railway (cron) ou VM pequena | (c) GitHub Actions agendado |
|---|---|---|---|---|
| Custo | zero | zero (se a equipe da coleta deixar) | Railway: plano que a coleta já usa + volume (~US$ 0,25/GB por mês); VM: ~US$ 4 a 6 por mês | zero em repositório público; privado: 2.000 min/mês grátis, e a espera de 08:00 a 09:45 gasta ~105 min/dia (~2.200 min/mês) |
| Confiabilidade | baixa a média: PC desligado, suspenso, sem internet, reinício do Windows Update, viagem | alta | alta | média: o cron atrasa de 5 a 30 min em horário cheio e às vezes pula; a agenda é desligada após 60 dias sem atividade no repositório |
| PC desligado ou suspenso | "Acordar o computador para executar" (só sai da suspensão, não liga o PC); "Executar o mais cedo possível após uma inicialização perdida" roda quando o PC volta (depois das 10h o top não vale; depois das 12h, só gera se a entrega já estiver pronta) | não se aplica | não se aplica | não se aplica |
| Acesso ao MySQL | IP de casa (precisa estar liberado no firewall do servidor) | local (`localhost`), sem expor nada | IP variável (já é o caso do Railway) | IP variável a cada execução |
| `.env` | arquivo local | arquivo no servidor | variáveis do Railway / arquivo na VM | segredos do GitHub |
| `modelos/`, `registros/`, `saida/estado/` | disco local | disco do servidor | Railway: **volume obrigatório** (o disco é efêmero); VM: disco | não persistem: commitar de volta (registros sim; estado e modelos incham o git) ou cache/artefatos (o cache some em 7 dias sem uso) |
| Logs | `logs/` local | `logs/` no servidor | painel do Railway / disco | página da execução (90 dias) |
| Alerta de falha | nenhum nativo (ver o `execucao.json` ou o log) | e-mail do cron, se configurado | notificação do Railway | e-mail automático de execução que falhou |
| Horário exato | relógio do PC | `CRON_TZ=America/Sao_Paulo` | Railway: cron em **UTC** (`55 10 * * 1-5` = 07:55 SP) | cron em UTC, com atraso |
| Esforço | baixo (script + tarefa) | médio (acesso SSH, Python 3.12, venv) | médio (Dockerfile, volume) | alto (estado em git, minutos) |

**Recomendação:** para os testes de funcionamento de agora, (a) no PC. Para a produção (teste ao vivo de meses, em que cada dia perdido é um dia a menos no histórico), (b1) se a equipe da coleta permitir (mais simples e confiável, com o usuário só de leitura); senão, (b2). (c) não compensa: o estado diário não cabe bem no git e a espera gasta os minutos.

**Detalhes de (a)** (a Fase 10 cria o script; o usuário cria a tarefa):
- `scripts/rotina_diaria.ps1`: `Set-Location` na raiz do projeto; `& .\.venv\Scripts\python.exe -m processamento.rotina`; `exit $LASTEXITCODE`. O log é gravado pelo próprio Python (sem redirecionamento, que depende do idioma do Windows).
- Tarefa: semanal, de segunda a sexta, às 07:55 (a rotina dorme até 08:00); ação `powershell -NoProfile -ExecutionPolicy Bypass -File "<raiz>\scripts\rotina_diaria.ps1"`; marcar "Executar estando o usuário conectado ou não" (pede a senha do Windows); em Condições, marcar "Acordar o computador para executar esta tarefa" e desmarcar "Iniciar somente se estiver usando energia CA" (notebook); em Configurações, marcar "Executar a tarefa o mais cedo possível após uma inicialização agendada ter sido perdida", "Parar a tarefa se ela for executada por mais de 5 horas" e "Se a tarefa já estiver em execução: não iniciar uma nova instância". Plano de energia: suspensão "nunca" na tomada, ou deixar a rotina segurar a suspensão (seção 11).
- Linha de comando equivalente (o usuário roda): `schtasks /Create /TN "TCC rotina diaria" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:55 /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\scripts\rotina_diaria.ps1"` (as opções de acordar e de "o mais cedo possível" ficam na interface gráfica).

---

## 13. Mudanças propostas na ESPECIFICACAO.md (aplicar depois da aprovação)

- **2.1:** `rotina.py` vira o pacote `rotina/` (`parametros.py`, `gatilho.py`, `checagem.py`, `retreino.py`, `trava.py`, `executar.py`, `__main__.py`); mais `producao.py` (entrada em produção).
- **4, item 2:** acrescentar "daily `agendada` = ainda não começou: esperar"; "entrega `falhou`: esperar um daily mais novo até o prazo"; "`precos` não concluída e sem o IBOV do pregão anterior previsto: esperar (dados atrasados)".
- **4, item 4 (R2/R4):** "Prazo: 9h45. Sem a entrega concluída, a rodada é registrada no `execucao` com status `falhou` e nenhum outro pacote (os dados disponíveis são os de ontem e misturariam tabelas). A rotina continua consultando até 12h; se a entrega concluir, gera uma rodada tardia (o top 5 gerado depois das 10h não vale para o histórico)."
- **4, item novo:** "D só é dia de rotina se for pregão previsto: dia útil fora de `feriados_b3` (`parametros.yaml`, conferido com a B3 e com os pregões do banco). Sem pregão, nada é gravado."
- **6, "Checagem diária":** os limites da seção 9 deste plano (`rotina.checagem`).
- **7.6 / 8.3 item 9:** fechamento de todos os tops pendentes; `AAAA-MM-DD.descartado.json` (motivos `nao_houve_pregao`, `pregao_base_diferente`).
- **7.7:** "Retreino na própria rotina, depois da entrega e antes do top, sempre que o modelo do mês não existir e a rotina estiver em produção; corte = pregões antes do dia 1 do mês, menos o de embargo; metadados com `retreino` e as métricas do desenvolvimento". Chave `treino.modelo_oficial` (R7).
- **8.3 item 10:** os campos do `coleta_status` (seção 8 deste plano); "a versão continua 1.0".
- **9:** "Decisões da etapa 8" (R1 a R15 aprovadas) e a pendência (c) reescrita: "entrada em produção só depois do histórico completo e de `modelo_oficial: true`; comando `python -m processamento.producao`".
- **10:** o risco do daily `agendada` durante a carga de 5 anos; o horário do daily na coleta (`DAILY_HORA` padrão 18:30 nos documentos dela).

---

## 14. Decisões a aprovar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| R1 | Como saber se D é pregão | lista de feriados no yaml + conferência com o banco · biblioteca (`exchange_calendars`) · só conferir no dia seguinte | **lista no yaml** (seção 4), sem dependência, conferida contra o banco e com aviso 30 dias antes de vencer |
| R2 | Entrega falhou / não terminou / sem daily até 09:45 | `falhou` sem nenhum pacote (pedido do usuário) · gerar tudo com os dados disponíveis (4.4 literal) · só a Fase 1 | **`falhou` sem pacotes** (seção 2.3: os "dados disponíveis" são de D−2 e misturados) |
| R3 | IBOV sem o pregão anterior previsto | sempre esperar · esperar só se `precos` não concluiu, senão seguir com aviso · ignorar | **esperar só se `precos` não concluiu**; concluída → segue com aviso (a B3 pode ter fechado; o fechamento descarta o dia se for o caso) |
| R4 | Depois das 09:45 | parar · continuar até 12:00 e gerar rodada tardia | **continuar até 12:00** (a Fase 1 do dia chega mesmo com a coleta atrasada; o top tardio já sai inválido) |
| R5 | `noticias`/`enriquecimento` não concluídas e a validade do top | só aviso, validade pela 8.3 · marcar `valido_para_historico = false` | **só aviso** (a regra da 8.3 fica como está; o `coleta_status` fica no `execucao` para análise de sensibilidade no TCC) |
| R6 | Quando retreinar | na rotina, antes do top · tarefa noturna · depois da rotina | **na rotina, antes do top**, só em produção, repetindo nos pregões seguintes do mês se faltar (mesmo corte, mesmo modelo) |
| R7 | Quem decide se o modelo é provisório | chave `treino.modelo_oficial` · regra automática por anos de histórico · as duas | **chave manual** `modelo_oficial: false` (decisão explícita do usuário, pegadinha 13) |
| R8 | Dia sem pregão | sair sem gravar nada · gravar `execucao` com status novo | **sair sem gravar** (sem mudar o contrato) |
| R9 | `coleta_status` e versão | campos novos opcionais, "1.0" · subir para "1.1" | **opcionais, "1.0"** (8.3: o contrato ainda não é usado) |
| R10 | Limites da checagem | 0,9 das ações; 30%; 5 pregões parados; indisponível em todas as ações | **os propostos** (só avisos; ajustáveis no yaml) |
| R11 | Entrada em produção | comando que confere e arquiva, e o usuário edita o yaml · comando que também edita o yaml · tudo à mão | **comando que confere e arquiva; o usuário edita `fim` e `liberado`**; só com `modelo_oficial: true`; D0 = 1º pregão de um mês |
| R12 | Fechar o histórico | varrer todos os pendentes + `.descartado.json` · só o registro de t (hoje) | **varrer todos** |
| R13 | Onde roda | PC (Agendador) · servidor do MySQL · Railway/VM · GitHub Actions | **PC agora; na produção, o servidor do MySQL (ou Railway/VM)**: decisão do usuário |
| R14 | Trava contra duas rotinas | arquivo com validade de 6 h · `msvcrt`/`fcntl` | **arquivo** |
| R15 | Daily válido | o mais recente de hoje (4, literal) · o mais recente com entrega concluída | **o mais recente** (texto da 4; um daily manual mais novo em andamento faz esperar, porque ele está regravando as tabelas) |

---

## 15. Onde a especificação, a coleta e o código não batem (listado, não resolvido)

1. **Seção 4, item 4 × pedido do usuário:** "gerar com os dados disponíveis" × "falhou, sem top 5" (R2).
2. **Horário do daily:** os documentos da coleta dizem `DAILY_HORA` padrão **18:30** (`02-pipeline-diaria.md`, `07-executor-e-painel.md`, `.env.example` da coleta); a especificação diz 08:00 (confirmado pelo painel: 11:00 UTC). Se a coleta voltar ao padrão, a rotina falha todo dia com `sem_daily`. Pedir confirmação de que `DAILY_HORA=08:00` está fixado no Railway.
3. **Carga histórica de 5 anos:** enquanto ela roda (`em_andamento`/`pausando`), o daily nasce `agendada` e só começa quando a carga pausa ou termina (`03-carga-historica.md`, seção 7). A rotina vai dar `falhou` (`daily_agendado`) nesses dias. Combinar com a coleta de pausar a carga antes das 08:00 nos dias úteis.
4. **`iniciada_em` de uma execução `agendada`:** a coluna é `NOT NULL`, e o documento diz que o orçamento conta "do instante em que ela de fato começa". Não está claro se o valor é regravado quando a `agendada` começa. A regra "a partir das 08:00 SP" funciona nos dois casos se o daily foi criado às 08:00.
5. **Entrega sem transação única:** um daily manual que começa a regravar as 8 tabelas durante o nosso `gerar` mistura dados. Risco baixo (a rotina leva ~2 min); fica registrado.
6. **Limite das 10h:** compara o `gerado_em`, que é o **início** da rodada (o top sai 1 a 2 min depois). Na Quarta de Cinzas a B3 abre às 13h e o limite continua 10h (fixo na 4.5). Manter.
7. **"Primeiro dia útil do mês" (7.7)** interpretado como primeiro pregão.
8. **A 2.1 fala em `rotina.py`**; o plano usa o pacote `rotina/` (o comando é o mesmo).
9. **Retreino antes da produção:** a 7.7 não diz; o plano só retreina com `fim` preenchido (R6). As "métricas da validação" do retreino são copiadas do desenvolvimento (não há validação nova).
10. **`treino._metadados` grava `provisorio: true` fixo** (`treino.py:764`): sem a chave nova (R7), nem o desenvolvimento refeito com 5 anos sairia oficial.
11. **Pegadinha 13 × teste final:** fixar o `fim` e rodar o teste final antes do histórico completo gastaria o uso único com a configuração de ~1 ano. Por isso a produção espera o histórico completo (seção 10). O teste final cresce enquanto isso (bom: mais dias de teste).
12. **`v1-painel_etapas.iniciada_em`/`finalizada_em`** existem no DDL (`docs/ddl_banco_coleta.sql:614-615`), mas não estão no `fontes.yaml`; `v1-painel_execucoes.aguardando` também não. A Fase 2 acrescenta.
13. **Execução `tipo = "etapa"`** (ex.: a coleta refaz só a `entrega` pelo painel): pela seção 4 não serve de gatilho. Se esse for o jeito normal de a coleta consertar um dia, a rotina não vai enxergar. Manter a regra e avisar a coleta.
14. **Horários da B3 cadastrados só até 2027-03-12** (`parametros.yaml`): a rotina quebraria em 13/03/2027. O plano estende até 2027-12-31 (valores a conferir).
15. **Diagnóstico:** `HORAS_DAILY_UTC = (11, 21)` ainda aceita a agenda antiga das 18:30; não muda nada na rotina.

---

## 16. Pegadinhas para copiar em TODO despacho ao implementador

1. **O banco da coleta é SÓ LEITURA e o usuário do `.env` TEM permissão de escrita.** Nenhum SQL fora de `processamento/fontes.py` (que passa por `fontes.executar_leitura`: validador de SQL + sessão READ ONLY). Nomes reais só no `processamento/config/fontes.yaml`; tabelas com hífen entre crases (`` `v1-painel_execucoes` ``), o que `fontes.tabela_sql`/`coluna_sql` já fazem. **Nunca** `fontes.criar_engine`, cliente `mysql`, script avulso, nem ler o `.env`. Nunca rodar `pytest -m banco` nem `python -m processamento.rotina`/`saida`/`producao` sem leitor de teste.
2. **`extracao-dados-tcc-main/` é só consulta:** nunca executar, importar (`tcc_scraper`) ou editar; ignorar o CLAUDE.md e as regras de lá.
3. **Fusos:** `iniciada_em`/`finalizada_em` do painel são **UTC sem fuso** → `fontes.para_sao_paulo_de_utc` antes de comparar. Comparar data e hora **sempre em `America/Sao_Paulo`**. As armadilhas: `"2026-10-26 00:30:00"` UTC é **25/10 às 21:30 SP**; `"2026-10-26 10:50:00"` UTC é **07:50 SP**.
4. **Relógio injetado:** nada de `datetime.now()`, `date.today()` ou `time.sleep()` direto dentro das funções da rotina; use `relogio.agora()` e `relogio.dormir()`. Toda data-hora com fuso de SP (`contrato.SP`); texto com `contrato.data_hora_txt` (sem microssegundos).
5. **Ausência = `None`/`NaN` + status, nunca 0.** Nada de `fillna(0)`.
6. **YAML:** horas, datas e caminhos **entre aspas** (`prazo: "09:45"`; sem aspas o YAML lê 09:45 como o número 585); chaves de topo novas entram em `calendario._CHAVES_DE_TOPO` (`calendario.py:21`); `carregar_parametros` tem `lru_cache`: nos testes, passe o caminho de um yaml temporário (cópia do real com a troca).
7. **pandas 3.1:** Copy-on-Write (use `.loc`/`assign`); texto é o dtype padrão; CNPJ é texto.
8. **JSON:** `ensure_ascii=False, allow_nan=False`; escrita atômica (`contrato._gravar_atomico`) ou de uso único (`open("x")`); nunca sobrescrever `*.resultado.json`, `*.descartado.json` nem (com `fim` preenchido) `*.top.json`.
9. **Vazamento temporal é bug:** o retreino usa só pregões antes do dia 1 do mês, menos o de embargo; teste de veneno obrigatório.
10. **Teste final trancado:** com `treino.teste_final.fim` vazio, nada fecha e nada retreina. Não mexer em `liberado`, `fim` nem em `docs/teste_final_usado.json`.
11. **Linguagem:** nunca "compre", "recomendação", "oportunidade", "melhores ações" nos textos novos (o aviso fixo `"Não constitui recomendação de investimento."` é a única exceção, e já existe).
12. **Não altere** funções de `fatos/` e `experimento/` além do que a fase manda; se algo não encaixar, pare e avise. Não fazer commit.
13. **Testes sem rede e sem banco real:** `banco_teste` (SQLite de `tests/dados`, `tests/conftest.py:29`), DataFrames das fábricas ou SQLite em memória criado no próprio teste; o gabarito é o deste plano. Verificação: `.venv\Scripts\python.exe -m pytest -q <arquivos da fase>` e depois `.venv\Scripts\python.exe -m pytest -q` (o projeto inteiro).

---

## 17. Fases para o implementador

| Fase | Arquivos | Depende de | Pode rodar junto com |
|---|---|---|---|
| 0 | `processamento/config/parametros.yaml`, `processamento/calendario.py` (só `_CHAVES_DE_TOPO`), `processamento/rotina/__init__.py`, `processamento/rotina/parametros.py`, `processamento/experimento/parametros.py`, `tests/test_rotina_parametros.py`, `tests/test_treino_parametros.py` (se precisar) | — | — (rodar primeiro) |
| 1 | `processamento/calendario.py`, `tests/test_calendario_feriados.py` | 0 | 2, 3, 4, 5, 6, 7 |
| 2 | `processamento/fontes.py`, `processamento/config/fontes.yaml`, `tests/test_fontes_painel.py` | 0 | 1, 3, 4, 5, 6, 7 |
| 3 | `processamento/rotina/gatilho.py`, `tests/fabrica_rotina.py`, `tests/test_rotina_gatilho.py` | 0 | 1, 2, 4, 5, 6, 7 |
| 4 | `processamento/saida/contrato.py`, `tests/test_saida_contrato_coleta.py` | — | 1, 2, 3, 5, 6, 7 |
| 5 | `processamento/saida/pacotes_experimento.py`, `tests/test_saida_fechar_pendentes.py` | — | 1, 2, 3, 4, 6, 7 |
| 6 | `processamento/rotina/retreino.py`, `processamento/experimento/treino.py` (só `_metadados`), `tests/test_rotina_retreino.py` | 0 | 1, 2, 3, 4, 5, 7 |
| 7 | `processamento/rotina/checagem.py`, `tests/test_rotina_checagem.py` | 0 | 1, 2, 3, 4, 5, 6 |
| 8 | `processamento/saida/gerar.py`, `processamento/rotina/trava.py`, `processamento/rotina/executar.py`, `processamento/rotina/__main__.py`, `tests/test_rotina_trava.py`, `tests/test_rotina_executar.py` | todas de 0 a 7 | 9 |
| 9 | `processamento/producao.py`, `tests/test_producao.py` | 0, 1 | 8 |
| 10 | `scripts/rotina_diaria.ps1`, `ESPECIFICACAO.md` (seção 13 deste plano), `LEIA-ME.md` (como agendar) | 8, 9 e aprovação | — |

As fases 1 a 7 mexem em arquivos diferentes e podem ir em paralelo. A 4 e a 5 não dependem nem da 0.

### Fase 0: parâmetros

**`processamento/config/parametros.yaml`**: acrescentar (manter o resto):
1. Em `horarios_b3`, no fim da lista: `- {a_partir_de: "2027-03-15", abertura: "10:00", fechamento: "17:00"}` e `- {a_partir_de: "2027-11-08", abertura: "10:00", fechamento: "18:00"}`; trocar `horarios_b3_valido_ate: "2027-03-12"` por `"2027-12-31"`; comentário `# 2027: conferir no site da B3`.
2. Em `dias_especiais`: `"2027-02-10": {abertura: "13:00", motivo: "quarta-feira de cinzas"}`.
3. Depois de `dias_especiais`, o bloco de feriados da seção 4 (todas as datas da tabela, uma por linha, `"AAAA-MM-DD": "motivo"`), com o comentário `# Feriados da B3: dias úteis sem pregão. 2024 a 2026-10-12 conferidos com os dias úteis sem IBOV do banco (docs/diagnostico_banco.md). O resto: conferir no calendário oficial da B3. DATAS ENTRE ASPAS. 09/07 tem pregão; 25/01 tem pregão desde 2022 (conferir).` e a chave `feriados_b3_valido_ate: "2027-12-31"`.
4. No bloco `treino`, depois de `teste_final`: `modelo_oficial: false            # true SÓ quando o histórico completo chegar e o desenvolvimento for refeito com ele (pegadinha 13)`.
5. No fim do arquivo, o bloco `rotina`:
```yaml
# Rotina diária (seção 4 da especificação; plano da etapa 8). HORAS E CAMINHOS ENTRE ASPAS.
rotina:
  inicio_consulta: "08:00"        # 1ª consulta ao painel da coleta (São Paulo)
  intervalo_minutos: 5            # entre consultas
  prazo: "09:45"                  # sem entrega até aqui: execucao "falhou", sem pacotes
  prazo_tardio: "12:00"           # continua consultando até aqui (rodada tardia); null = desliga
  etapas_conferidas: ["precos", "noticias", "enriquecimento"]   # não concluídas: aviso
  pasta_logs: "logs"
  trava: "saida/estado/rotina.trava"
  trava_validade_horas: 6
  aviso_calendario_dias: 30
  checagem:
    acoes_minimo_fracao: 0.9
    retorno_maximo_abs: 0.30
    preco_parado_pregoes: 5
    max_tickers_por_aviso: 10
```
**`calendario.py:21`:** acrescentar `"feriados_b3_valido_ate"`, `"feriados_b3"` e `"rotina"` a `_CHAVES_DE_TOPO` (só isso nesta fase).
**`processamento/experimento/parametros.py`:** campo novo no fim do dataclass `ParametrosTreino`: `modelo_oficial: bool = False`. Em `carregar_parametros_treino`, a chave é opcional (ausente = `False`, para não quebrar yamls de teste montados à mão): conferir as chaves com `_CHAVES_TREINO | ({"modelo_oficial"} if "modelo_oficial" in bloco else set())` e ler com `_booleano(bloco.get("modelo_oficial", False), "treino.modelo_oficial")`.
**`processamento/rotina/__init__.py`:** só a docstring `"""Rotina diária: gatilho da seção 4, prazos e avisos (plano da etapa 8)."""`.
**`processamento/rotina/parametros.py`** (copiar o padrão de `processamento/saida/parametros.py`):
```python
@dataclass(frozen=True)
class ParametrosChecagem:
    acoes_minimo_fracao: float
    retorno_maximo_abs: float
    preco_parado_pregoes: int
    max_tickers_por_aviso: int

@dataclass(frozen=True)
class ParametrosRotina:
    inicio_consulta: time
    intervalo_minutos: int
    prazo: time
    prazo_tardio: time | None
    etapas_conferidas: tuple[str, ...]
    pasta_logs: Path
    trava: Path
    trava_validade_horas: float
    aviso_calendario_dias: int
    checagem: ParametrosChecagem

class ErroParametrosRotina(Exception): ...
def carregar_parametros_rotina(caminho: str | None = None) -> ParametrosRotina
```
Validações (mensagens com o nome da chave): chaves exatas (desconhecida ou faltando → erro); horas `"HH:MM"` entre aspas; `inicio_consulta < prazo`; `prazo_tardio` `null` ou maior que `prazo`; `intervalo_minutos` inteiro > 0; `etapas_conferidas` lista de textos contida em `processamento.diagnostico.esperado.ETAPAS_COLETA` e sem `entrega`/`analise`; `trava_validade_horas` > 0; `aviso_calendario_dias` inteiro >= 0; frações em (0, 1]; `preco_parado_pregoes` >= 2; `max_tickers_por_aviso` >= 1; pastas ancoradas em `fontes.RAIZ`.
**Testes (`tests/test_rotina_parametros.py`)**, com yaml temporário copiado do real: o real carrega com `inicio_consulta == time(8, 0)`, `prazo == time(9, 45)`, `prazo_tardio == time(12, 0)`, `intervalo_minutos == 5`, `etapas_conferidas == ("precos", "noticias", "enriquecimento")`, `trava == fontes.RAIZ / "saida/estado/rotina.trava"`, `checagem.retorno_maximo_abs == 0.30`; `prazo: 09:45` sem aspas → erro com "entre aspas"; `prazo: "07:00"` → erro (antes do início); `prazo_tardio: null` → `None`; `prazo_tardio: "09:00"` → erro; `etapas_conferidas: ["entrega"]` → erro; chave `xyz` → erro. Treino: o real carrega com `modelo_oficial is False`; yaml sem a chave → `False`; `modelo_oficial: "sim"` → erro; `params_teste()` continua funcionando. `calendario.carregar_parametros()` aceita o yaml novo.
**Pegadinhas:** 6, 7, 12, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_rotina_parametros.py tests/test_treino_parametros.py tests/test_calendario.py` e depois o projeto inteiro.

### Fase 1: feriados no calendário (`processamento/calendario.py`)
- Validação em `carregar_parametros` (função nova `_validar_feriados(feriados, valido_ate, especiais)`, chamada se `feriados_b3` existir): mapeamento; chave = data entre aspas (`_validar_data`); valor = texto não vazio; **dia útil** (sábado ou domingo → `ErroCalendario("feriados_b3[2026-11-15]: cai no fim de semana; não precisa entrar")`); não pode estar também em `dias_especiais`; `feriados_b3_valido_ate` obrigatório e maior ou igual a todas as datas.
- Funções públicas novas (todas com `caminho: str | None = None` repassado a `carregar_parametros`): `feriados_b3() -> dict[date, str]`; `e_pregao_previsto(d) -> bool` (dia útil e fora da lista; `d > feriados_b3_valido_ate` → `ErroCalendario` com o texto da seção 4); `motivo_sem_pregao(d) -> str | None` ("sábado", "domingo" ou o motivo da lista; `None` se é pregão); `pregao_anterior_previsto(d) -> date` (volta dia a dia, no máximo 15 dias); `primeiro_pregao_do_mes(d) -> bool`; `avisos_validade(d, dias) -> list[str]` (textos exatos da seção 4; vence quando `valido_ate − d <= dias`); `conferir_feriados(cal, desde, ate) -> dict` (datas como texto `AAAA-MM-DD`, ordenadas).
- **Testes (`tests/test_calendario_feriados.py`):** todos os valores da seção 4 (com o yaml real); validação com yaml temporário (data sem aspas → erro "entre aspas"; feriado num domingo → erro; feriado também em `dias_especiais` → erro; data depois de `feriados_b3_valido_ate` → erro); `motivo_sem_pregao(date(2026, 11, 2))` = o texto do yaml para Finados e `motivo_sem_pregao(date(2026, 10, 24)) == "sábado"`. Um teste `@pytest.mark.banco` (o usuário roda): `conferir_feriados(calendario.pregoes(fontes.ler_tabela("precos")), date(2024, 8, 1), <último pregão>)` → as duas listas vazias.
- **Pegadinhas:** 6, 12, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_calendario_feriados.py tests/test_calendario.py`.

### Fase 2: leitura do painel (`processamento/fontes.py`, `processamento/config/fontes.yaml`)
- `fontes.yaml`: em `auxiliares.painel_execucoes.colunas`, acrescentar `aguardando: aguardando`; em `painel_etapas.colunas`, `iniciada_em: iniciada_em, finalizada_em: finalizada_em` (existem no DDL, `docs/ddl_banco_coleta.sql:225-239` e `:604-621`).
- Funções (sempre com `ler` injetável; SQL montado com `_conferir_tabela` + `_selecionar`, como em `ler_raw_b3_cadastro`, `fontes.py:505`):
```python
def ler_painel_execucoes(desde_utc: datetime, ler=None) -> pd.DataFrame
    # colunas: id, tipo, origem, status, aguardando, iniciada_em, finalizada_em (as duas tz-aware em SP)
    # WHERE `iniciada_em` >= :desde ; :desde = desde_utc em UTC sem fuso, "AAAA-MM-DD HH:MM:SS"; ordena por iniciada_em
def ler_painel_etapas(execucao_id: str, ler=None) -> pd.DataFrame
    # colunas: execucao_id, etapa_id, ordem, status, iniciada_em, finalizada_em (SP); WHERE `execucao_id` = :id ; ordena por ordem
def ultimo_pregao_ibov(ate: date, ler=None) -> date | None
    # SELECT MAX(`data`) AS ultima FROM `v1-precos` WHERE `ticker` = :ticker AND `fechamento` IS NOT NULL AND `data` <= :ate
```
  Textos vazios viram `None` (`_vazio_como_nulo`); horários com `para_sao_paulo_de_utc`. `desde_utc` com fuso é convertido para UTC; sem fuso, é tratado como UTC. O resultado do `MAX` vem como data (MySQL) ou texto (SQLite): normalizar com `pd.to_datetime(...).date()`.
- **Testes (`tests/test_fontes_painel.py`)**, SQLite em memória criado no próprio teste (`sqlalchemy.create_engine("sqlite://")`, `DataFrame.to_sql("v1-painel_execucoes", ...)` com tudo em texto, `ler = lambda sql, params=None: fontes.executar_leitura(sql, params, engine=eng)`): linhas `("2026-10-25-daily-213000", "daily", "cron", "concluida", None, "2026-10-26 00:30:00", "2026-10-26 01:10:00")` e `("2026-10-26-daily-080001", "daily", "cron", "em_andamento", None, "2026-10-26 11:00:01.489947", None)`; `ler_painel_execucoes(datetime(2026, 10, 26, 3, 0), ler)` → 1 linha, `id "2026-10-26-daily-080001"`, `iniciada_em == pd.Timestamp("2026-10-26 08:00:01.489947", tz="America/Sao_Paulo")` (conferido), `finalizada_em` NaT, `aguardando` None; com `desde = datetime(2026, 10, 26, 0, 0, tzinfo=SP)` (= 03:00 UTC) → o mesmo; etapas: 3 linhas da execução e 1 de outra → só as 3, na ordem de `ordem`, com `finalizada_em` convertido; `ultimo_pregao_ibov` com `banco_teste()`: `ate=date(2025, 10, 21)` → `date(2025, 10, 21)`; `ate=date(2025, 10, 19)` → `date(2025, 10, 17)`; `ate=date(2025, 10, 15)` → `None`; tabela sem a coluna `aguardando` → `ErroLeitura` "sem a coluna aguardando"; o SQL gerado passa por `validar_sql_leitura` e contém `` `v1-painel_execucoes` `` com crase.
- **Pegadinhas:** 1, 2, 3, 5, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_fontes_painel.py tests/test_fontes.py tests/test_diagnostico_consultas.py tests/test_diagnostico_temas.py`.

### Fase 3: gatilho puro (`processamento/rotina/gatilho.py`, `tests/fabrica_rotina.py`)
```python
MOTIVOS = ("entrega_concluida", "entrega_pendente", "entrega_falhou", "sem_daily", "daily_agendado",
           "dados_atrasados", "falha_consulta", "sem_esperar")

@dataclass(frozen=True)
class Painel:
    execucoes: pd.DataFrame              # formato de fontes.ler_painel_execucoes
    etapas: dict[str, pd.DataFrame]      # execucao_id -> formato de fontes.ler_painel_etapas
    ultimo_ibov: date | None

@dataclass(frozen=True)
class Decisao:
    acao: str                            # "esperar" | "gerar"
    motivo: str
    execucao: dict | None                # id, origem, status, iniciada_em, finalizada_em
    etapas: dict[str, str | None]        # as 9 de ETAPAS_COLETA
    entrega_concluida_em: datetime | None
    avisos: list[str]
    nota: str

@dataclass
class ResultadoGatilho:
    pronto: bool
    decisao: Decisao
    consultas: int
    primeira_consulta_em: datetime | None
    ultima_consulta_em: datetime | None
    prazo: datetime
    t_esperado: date
    def espera_segundos(self) -> int
    def coleta_status(self) -> dict      # formato da seção 8 (exemplo exato no caso A da seção 3)
    def aviso_desistencia(self) -> str   # textos da seção 2.4, por motivo

class Relogio(Protocol):
    def agora(self) -> datetime: ...
    def dormir(self, segundos: float) -> None: ...

class RelogioReal: ...                   # datetime.now(SP) e time.sleep

def escolher_daily(execucoes: pd.DataFrame, d: date, inicio: time) -> pd.Series | None
def avaliar_painel(painel: Painel, d: date, t_esperado: date, params: ParametrosRotina) -> Decisao
def esperar_coleta(d: date, t_esperado: date, consultar: Callable[[], Painel], relogio: Relogio,
                   params: ParametrosRotina, *, sem_esperar: bool = False,
                   ao_esgotar_prazo: Callable[[ResultadoGatilho], None] | None = None) -> ResultadoGatilho
```
Regras: seções 2.1, 2.2 e 2.4. `ETAPAS_COLETA` vem de `processamento.diagnostico.esperado`. Um `consultar` que levanta `fontes.ErroSomenteLeitura` faz a exceção subir; qualquer outra `Exception` conta como consulta, com decisão `esperar`/`falha_consulta`.
**`tests/fabrica_rotina.py`:** `RelogioFalso(inicio: datetime)` (`agora()` devolve o instante atual; `dormir(s)` soma `s` segundos e guarda em `.sonos`); `execucao(id, iniciada_utc, *, origem="cron", status="em_andamento", tipo="daily", aguardando=None, finalizada_utc=None) -> dict`; `etapas(execucao_id, status: dict[str, str], finalizada_utc: dict[str, str] | None = None) -> pd.DataFrame` (etapa sem status = sem linha); `painel(execucoes: list[dict], etapas: dict[str, pd.DataFrame], ultimo_ibov) -> Painel` (converte os horários com `fontes.para_sao_paulo_de_utc`); `linha_do_tempo(relogio, estados: list[tuple[datetime, Painel]]) -> Callable[[], Painel]` (devolve o último estado com horário <= `relogio.agora()`; antes do primeiro, painel vazio). A Fase 8 reusa esta fábrica.
**Testes (`tests/test_rotina_gatilho.py`):** todos os casos de A a R da seção 3, com os números da tabela e o dicionário exato do caso A; mais: `escolher_daily` com tipo `coletar`, tipo `etapa` e origem `outra` → ignorados; nota de manual; `aviso_desistencia` com os 6 textos.
**Pegadinhas:** 3, 4, 5, 13 (e a 1: este módulo não lê nada do banco; só a fábrica usa `fontes.para_sao_paulo_de_utc`). **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_rotina_gatilho.py`.

### Fase 4: `coleta_status` no validador (`processamento/saida/contrato.py`)
- Em `ESQUEMAS["execucao"]` (`contrato.py:435`), trocar `{"consultado": "bool", "nota": "texto"}` pelo esquema da seção 8, com `("opcional", ...)` em todos os campos novos. Etapas: `("opcional", {e: ("opcional", "texto?") for e in ("precos", "macro", "noticias", "ipe", "enriquecimento", "juiza", "cadastro", "entrega", "analise")})`. `motivo`: `("opcional", ("enum", MOTIVOS_COLETA))`, com a constante nova `MOTIVOS_COLETA` (os mesmos 8 da Fase 3; definida aqui para o contrato não importar `rotina`).
- **Testes (`tests/test_saida_contrato_coleta.py`):** os da seção 8 (registro `execucao` completo, montado com `contrato.meta`).
- **Pegadinhas:** 5, 8, 12, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_contrato_coleta.py tests/test_saida_contrato.py tests/test_saida_gerar.py`.

### Fase 5: fechar pendentes (`processamento/saida/pacotes_experimento.py`)
- Constantes: `AVISO_NAO_HOUVE = "pregão previsto {dia} não houve; dia descartado"` (o mesmo texto de `gerar.py:37`) e `AVISO_BASE_DIFERENTE` (texto da seção 6). Funções: `listar_registros_top(pasta) -> list[date]` (nomes `AAAA-MM-DD.top.json` só da pasta de cima, ordenados); `gravar_descartado(pasta, dia, motivo, agora) -> bool` (uso único); `fechar_pendentes(pasta, precos, cal, t, fim, agora) -> list[str]` (regras 1 a 5 da seção 6; reusa `ler_registro_top`, `pode_fechar`, `fechar_dia`, `gravar_resultado`). Não mexer em `fechar_dia`, `montar_historico` nem nas outras funções.
- **Testes (`tests/test_saida_fechar_pendentes.py`):** os 9 casos da seção 6, com os registros escritos como JSON mínimo (`{"pacote": {"pregao_previsto", "pregao_base", "data_referencia", "valido_para_historico", "ranking": [{"ticker"}]}, "interno": {"candidatos", "sombra_modelo_1", "sombra_volatilidade"}}`), preços com `precos_de` e `params_teste(acaso_sorteios=10000)` para o histórico.
- **Pegadinhas:** 5, 8, 10, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_fechar_pendentes.py tests/test_saida_experimento.py`.

### Fase 6: retreino (`processamento/rotina/retreino.py`, `treino._metadados`)
```python
def datas_de_treino(cal: list[date], mes: str, embargo: int) -> list[date]   # pregões < dia 1 de `mes`, menos os `embargo` últimos
def precisa_retreinar(pasta_modelos: Path, d: date, fim: date | None) -> bool  # fim preenchido e sem xgb-<mês de D>.json
def retreinar_mes(df: pd.DataFrame, info: dict, cal: list[date], d: date, *, pasta_modelos: Path,
                  params: ParametrosTreino, agora: datetime) -> list[str]
```
Passos e metadados: seção 7. `cal` = as datas distintas do `df` quando o chamador não tiver outro. Reusar `treino._configuracao_congelada`, `treino._inicio_experimento(params.inicio_experimento, info)`, `treino._versoes`, `treino.REGISTRO_TESTE_FINAL` (só para `teste_final.usado` = o arquivo existe), `preparacao.preparar`, `modelos.treinar_xgb`, `modelos.salvar_modelo`, `modelos.nome_modelo`. Sem linhas de treino → `treino.ErroPreRequisito("retreino de {mes}: nenhuma linha de treino antes de {mes}-01")`. Em `treino._metadados` (`treino.py:764-765`): `"provisorio": not params.modelo_oficial` e `"aviso": AVISO_PROVISORIO if not params.modelo_oficial else None` (nada mais).
**Testes (`tests/test_rotina_retreino.py`):** os 7 casos da seção 7. Metadados do dev para o teste: `{chave: None for chave in CHAVES_METADADOS}` + `colunas` (`preparacao.colunas_do_modelo("3")` e `("1")`), `blocos {"blocos_preco": [], "noticias_contexto": false}`, `hiperparametros = params.xgboost`, `calibracao {"aprovada": false}`, `metricas_validacao {"auc_geral": 0.51}`, salvos com `modelos.salvar_modelo` de um modelo qualquer em `tmp/modelos/xgb-2026-01` e `xgb-m1-2026-01`.
**Pegadinhas:** 5, 9, 10, 12, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_rotina_retreino.py tests/test_treino_pipeline.py tests/test_treino_modelos.py`.

### Fase 7: checagem (`processamento/rotina/checagem.py`)
```python
def avisos_do_dia(precos: pd.DataFrame, cal: list[date], t: date, pares: list[str], params: ParametrosChecagem) -> list[str]
def avisos_indicadores(mercado: dict | None, resumo: list[dict] | None, t: date, params: ParametrosChecagem) -> list[str]
```
Regras, textos e ordem: seção 9 (ordem: poucas ações, retorno, volume zero, preço parado; depois mercado; depois ações). Reusar `grade_de_precos`, `retornos_diarios` (`fatos/precos.py`) e `relatorio.pct` (1 casa nos tickers; o limite no texto com 0 casas: `pct(0.30, 0)` = "30%"). Regras que precisam de um pregão anterior ou de N pregões não rodam se eles faltarem.
**Testes (`tests/test_rotina_checagem.py`):** os gabaritos da seção 9 (montar `precos` com `precos_de` e `pregoes_uteis`; `mercado` e `resumo` como dicionários mínimos com as folhas usadas).
**Pegadinhas:** 5, 7, 11, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_rotina_checagem.py`.

### Fase 8: integração (`gerar.py`, `rotina/trava.py`, `rotina/executar.py`, `rotina/__main__.py`)
- `gerar.py`: as mudanças da seção 11 (parâmetros `retreinar` e `checagem` com padrão `None`; `dataset()` com `(df, info)`; `historico()` com `fechar_pendentes`; `registrar_execucao`). Texto do aviso de falha do retreino: `"Retreino de {mes} falhou ({type(erro).__name__}): usando o modelo anterior."`.
- `rotina/trava.py`: `class ErroTrava(Exception)`; `@contextmanager def trava(caminho: Path, agora: datetime, validade_horas: float)` (seção 5).
- `rotina/executar.py`:
```python
@dataclass
class ResultadoRotina:
    codigo: int
    status: str            # "sem_pregao", "ok", "parcial", "falhou", "trava"
    d: date
    pasta: Path | None

def montar_consulta(ler, d: date) -> Callable[[], Painel]
def executar_rotina(d: date | None, *, relogio: Relogio, ler=None, consultar=None, sem_esperar: bool = False,
                    params_rotina=None, params_treino=None, params_saida=None, pasta_saida: Path | None = None,
                    pasta_modelos: Path | None = None, pasta_registros: Path | None = None,
                    pasta_estado: Path | None = None, existe_composicao: bool | None = None) -> ResultadoRotina
def main(argv=None, *, relogio=None, ler=None, consultar=None, existe_composicao=None) -> int
```
  Fluxo e códigos: seção 11. Aqui `pasta_saida` é a raiz (`saida/`); a pasta do dia é `pasta_saida / D`. O gancho do retreino é `functools.partial(retreino.retreinar_mes, pasta_modelos=..., params=params_treino, agora=relogio.agora())`, chamado só se `retreino.precisa_retreinar(...)`. Log com `logging` (arquivo `params.pasta_logs / f"rotina-{D}.log"` + console). No Windows, `SetThreadExecutionState` por `ctypes` enquanto espera (função `_manter_acordado()` que não faz nada fora do Windows e nunca levanta erro).
- `rotina/__main__.py`: `from processamento.rotina.executar import main` e `raise SystemExit(main())`.
- **Testes:** `tests/test_rotina_trava.py` (os 4 casos da seção 5) e `tests/test_rotina_executar.py` (os 10 casos da seção 11, com `_sem_banco_real` copiado de `tests/test_saida_gerar.py:38`, `banco_teste`, modelos pequenos como em `tests/test_saida_gerar.py:46`, `RelogioFalso` e `linha_do_tempo` da Fase 3). Os testes atuais de `tests/test_saida_gerar.py` continuam passando sem mudança.
- **Pegadinhas:** todas (1 a 13). **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_rotina_trava.py tests/test_rotina_executar.py tests/test_saida_gerar.py tests/test_vazamento_saida.py` e depois o projeto inteiro.

### Fase 9: entrada em produção (`processamento/producao.py`)
```python
def conferir_entrada(d0: date, hoje: date, params_treino: ParametrosTreino, pasta_modelos: Path,
                     pasta_registros: Path, registro_teste_final: Path) -> tuple[date | None, list[str], list[str]]
    # (fim, problemas, passos); fim = calendario.pregao_anterior_previsto(d0) se d0 for pregão previsto
def confirmar_entrada(d0, fim, hoje, pasta_registros, arquivo_producao: Path, agora: datetime) -> list[str]
    # move os *.top.json para pasta_registros / f"funcionamento-{hoje}" e grava arquivo_producao (uso único)
def main(argv=None, *, hoje=None, agora=None, params_treino=None, pasta_modelos=None,
         pasta_registros=None, registro_teste_final=None, arquivo_producao=None) -> int
    # python -m processamento.producao --inicio AAAA-MM-DD [--confirmar]; 0 = sem problemas; 1 = problemas
```
  Nunca edita o `parametros.yaml`, nunca lê o banco, nunca roda o treino. Os passos impressos são os da seção 10 (com as datas preenchidas). "Dev não provisório" = `xgb-<mês de teste_final_inicio>.meta.json` com `provisorio: false`.
- **Testes (`tests/test_producao.py`):** os casos da seção 10 (pastas temporárias; `params_teste(modelo_oficial=True)` e metadados de dev com `provisorio: false` para o caso "tudo certo").
- **Pegadinhas:** 6, 8, 10, 12, 13. **Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_producao.py`.

### Fase 10: script e documentos (depois da aprovação e das fases 8 e 9)
`scripts/rotina_diaria.ps1` (seção 12); o texto da seção 13 na `ESPECIFICACAO.md`; um parágrafo no `LEIA-ME.md` com o comando `schtasks` e as opções da interface gráfica. **Verificação:** `.venv\Scripts\python.exe -m pytest -q`.

**Ação do usuário depois da Fase 8** (lê o banco; o subagente não roda): `python -m processamento.rotina --data <próximo pregão> --sem-esperar` (código 0; conferir o `coleta_status` e o tempo da rodada no `execucao.json`); `PROC_TESTES_COM_BANCO=1 pytest -q -m banco` (inclui a conferência dos feriados); depois, criar a tarefa do Agendador e acompanhar uma manhã real.

---

## 18. Arquivos

Novos: `processamento/rotina/__init__.py`, `parametros.py`, `gatilho.py`, `checagem.py`, `retreino.py`, `trava.py`, `executar.py`, `__main__.py`; `processamento/producao.py`; `scripts/rotina_diaria.ps1`; `tests/fabrica_rotina.py`; `tests/test_rotina_parametros.py`, `test_rotina_gatilho.py`, `test_rotina_checagem.py`, `test_rotina_retreino.py`, `test_rotina_trava.py`, `test_rotina_executar.py`, `test_calendario_feriados.py`, `test_fontes_painel.py`, `test_saida_contrato_coleta.py`, `test_saida_fechar_pendentes.py`, `test_producao.py`.
Alterados: `processamento/config/parametros.yaml`, `processamento/config/fontes.yaml`, `processamento/calendario.py`, `processamento/fontes.py`, `processamento/experimento/parametros.py`, `processamento/experimento/treino.py` (só `_metadados`), `processamento/saida/contrato.py`, `processamento/saida/pacotes_experimento.py`, `processamento/saida/gerar.py`, `ESPECIFICACAO.md`, `LEIA-ME.md`.
Gerados em uso: fora do git, `logs/rotina-AAAA-MM-DD.log` e `saida/estado/rotina.trava`; versionáveis, `registros/experimento/*.descartado.json` e `docs/producao.json`.
