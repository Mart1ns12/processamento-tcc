# Plano: 8 melhorias no painel (API, Banco, dia completo, novidades, dia atípico, coerência, etapas da coleta, empresas afetadas)

Li o código real do painel (`servidor.py`, `visao.py`, `saude.py`, `leitores.py`, `relatorios.py`, `acoes.py`, `marcos.py`, `ajuda.py` e as âncoras do `pagina.html`), os testes do painel, a fábrica, as fixtures, o `parametros.yaml`, o `.gitignore`, os pacotes reais `saida/2026-10-23`, `2026-10-26` e `2026-10-27`, os logs da rotina e o `docs/diagnostico_banco.md` real. No `api-tcc` li só código e documentação: `api/rotas.py`, `api/repositorio.py`, `publicador/*`, `comum/config.py`, `CLAUDE.md` e `docs/plano_api.md`. Não abri nenhum `.env`, não rodei nada que acesse banco ou rede e não editei nada.

## APROVADO EM 27/10/2026 (vale sobre o resto do plano)

- **P1 a P5 aprovados como recomendados:** arquivos `.log` em `logs/painel/` (sem mexer no `.gitignore`); publicador não roda se a rotina falhou e já existe `saida_completa/D/` (código 6); data esperada do Banco = D da última rotina diária ok ou parcial; etapas da coleta = foto do `execucao.json`.
- **P4 com ajuste de texto:** o dia atípico "amplo" entra no Resumo como amarelo, mas o texto deixa claro que é **aviso de evento de mercado, não erro dos dados**:
  - ponto do Resumo (amplo): `f"Dia atípico no pregão de {dd/mm/aaaa} ({n} ações): aviso de evento de mercado, não erro dos dados"`;
  - ponto do Resumo (isolado): `f"Dia atípico no pregão de {dd/mm/aaaa} ({n} ações): conferir os dados da coleta"`;
  - "O que fazer" `dia_atipico_amplo`: 'Nada no processamento: é um aviso de evento de mercado, não um erro dos dados. O mercado inteiro se moveu junto. Vale só confirmar no noticiário o que aconteceu nesse pregão.'
- **Parâmetros do painel em arquivo próprio (decidido pelo usuário em 27/10/2026):** o bloco `painel:` de A.6 NÃO vai para o `parametros.yaml`, porque `calendario.py:21` (`_CHAVES_DE_TOPO`) rejeita chave de topo desconhecida e todos os blocos existentes validam chaves exatas. As mesmas chaves de A.6 ficam, sem o nível `painel:`, em `processamento/config/painel.yaml`, lido só por `leitores._ler_painel_yaml`. `retorno_dia_abs` continua vindo de `rotina.checagem.retorno_maximo_abs` do `parametros.yaml`. A fixture equivalente é `tests/dados/painel/raiz/processamento/config/painel.yaml`. O `parametros.yaml` e o `calendario.py` não mudam.
- **Exemplo real de referência: o pregão de 26/10/2026 (pasta `saida/2026-10-27/`).** Conferido pelo usuário nas notícias: o pregão foi real, o Ibovespa caiu cerca de 13% com circuit breaker e o dólar **subiu** cerca de 8% (o IVVB11 +8,96% é coerente com isso). **O dado errado é só o USDBRL (−1,45%)**, já reportado à coleta. Comportamento esperado, que os testes travam:
  - Dia atípico: ativo, 16 ações, Ibovespa −13,88%, SMLL −26,92%, "Movimento amplo do mercado (provável evento real)" → **correto**;
  - Coerência do mercado: amarelo, 1 sinal suspeito (dólar −1,45% × IVVB11 +8,96%) → **correto**: aponta o USDBRL errado;
  - Ibovespa × mediana das ações (−13,88% × −17,46%): mesmo sentido, dentro do esperado.
  - O risco 3 de A.9 não se confirmou neste caso: o "amplo" estava certo e a Coerência pegou o único dado errado.

## 0. Correções ao pedido e fatos conferidos (valem sobre o resto)

1. **Os números de 26/10 estão em `saida/2026-10-27/`, não em `saida/2026-10-26/`.** A pasta é a data D da rotina; o pregão vem em `data_referencia`.
   - `saida/2026-10-27/mercado_dia.json`, `registros[0]`, tem `data_referencia` "2026-10-26". Valores:
     - `USDBRL.variacao_dia.valor` = −0.014503686980626429 (−1,45%);
     - `indices.IVVB11.d1.valor` = 0.0896279268486555 (+8,96%);
     - `IBOV.variacao_dia.valor` = −0.1388462232364457 (−13,88%);
     - `indices.SMLL.d1.valor` = −0.2691564967695621 (−26,92%).
   - Já `saida/2026-10-26/` traz o pregão de 23/10: dólar −0,33% e IVVB11 −1,50%, mesmo sentido, nada suspeito.
   - **Conferido:** com os limites propostos, 26/10 acende amarelo (dólar × IVVB11).
2. **Retorno do dia de cada ação:** `resumo_acao.json` → `registros[].rentabilidade.d1` (`valor` e `status`), com dividendos, a mesma base da checagem da rotina (`rotina/checagem.py:93-98`).
   - Em `saida/2026-10-27`: 85 ações, todas com status ok, e 16 acima de 30% em módulo. É a mesma lista do aviso "Checagem: retorno do dia acima de 30%…" do `execucao.json`.
   - Mediana: −0.17462931018161998 (−17,46%).
3. **O limite de 30% já existe:** `rotina.checagem.retorno_maximo_abs: 0.30` (`parametros.yaml:233`). Reuso esse valor só para leitura.
   - **Não dá para acrescentar chaves dentro de `rotina:`, `rotina.checagem:` nem `treino:`.** Esses blocos são validados com chaves exatas (`rotina/parametros.py:137,163`; `experimento/parametros.py:266,328`), e uma chave a mais quebraria a rotina.
   - Por isso os parâmetros novos ficam num bloco novo de primeiro nível, `painel:`. Nenhum carregador confere as chaves do nível de cima.
4. **`/v1/saude`** (`api-tcc/api/rotas.py:139-151`):
   - é pública (`api/main.py:19`);
   - devolve `{"status":"ok","banco":"ok","ultima_publicacao": <data_publicacao>}`, ou HTTP 503 com `{"status":"erro","banco":"fora"}`;
   - `ultima_publicacao` só conta publicações com status "completa" (`api/repositorio.py:20-21,156-158`);
   - essa data é D, a data da pasta, não o pregão (`api-tcc/CLAUDE.md`, "D ≠ data_referencia").
   - **A resposta não traz a data do pregão.**
5. **Publicador.**
   - Uso: `python -m publicador (--criar-tabelas | --data D [--forcar] | --conferir)`. Sai com 0 se ok, 1 se recusou, 2 se é configuração ou banco (`publicador/__main__.py:1-4`).
   - Lê só `saida/D/execucao.json` e, se a pasta existir, `saida_completa/D/*` (`publicador/leitor.py:44-84`).
   - **Publicar "só a execução" já é automático:** sem `saida_completa/D/`, o plano vira `so_execucao` (`publicador/planejador.py:38-42`; `docs/plano_api.md:286`). Não precisa de flag nem de mudança na API.
   - Linhas que ele imprime (`publicador/resumo.py:48-51`): "DD/MM/AAAA: só a execução foi gravada (sem carga completa)" e "DD/MM/AAAA publicado (modo …, execução: …) em …". Na recusa: "Publicação de D recusada: …" ou "Não publicado: …" (`__main__.py:72,78,90`).
   - Configuração: o publicador lê o próprio `.env` com `load_dotenv(override=False)` (`comum/config.py:62`). A pasta do processamento vem de `PROC_DIR_PROCESSAMENTO` ou, na falta dela, de `RAIZ.parent/"processamento-tcc"` (`config.py:84-85`).
   - O Python do projeto da API existe em `api-tcc/.venv/Scripts/python.exe`.
6. **Como o painel roda as ações hoje** (`acoes.py`):
   - lista fixa `ACOES` (`:30-35`);
   - o argv tem de começar por `sys.executable` (`:108-114`) e o cwd é a raiz (`:164`);
   - log em `logs/painel/<id>-AAAA-MM-DD_HHMMSS.log` com `# painel: acao=… inicio=…` (`:176-181`) e `# painel: fim=… codigo=N[ parado=sim]` (`:292-295`);
   - guarda os 20 últimos logs (`:303-309`); só ação com `pode_parar` para (`:197-209`);
   - a trava bloqueia as ações com `usa_banco` (`servidor.py:93-94`).
   - O status da rotina está em `saida/D/execucao.json` → `registros[0].status` (`leitores.py:286-288`). O código de saída da rotina é 0 para ok, parcial ou sem pregão e 4 para falhou (`acoes.py:38-44`; `rotina/executar.py:243`).
7. **Etapas da coleta sem SQL:** a rotina já grava `coleta_status.etapas` no `execucao.json` (`rotina/gatilho.py:104`), e o painel já repassa isso (`leitores.py:260,270`).
   - A ordem é `ETAPAS_COLETA` (`diagnostico/esperado.py:11`). O valor None quer dizer "sem linha" (`gatilho.py:155-169`). Status reais: concluida, falhou, pulada (`docs/diagnostico_banco.md:672-692`).
   - **Não confere com o pedido:**
     - `saida/2026-10-26` não tem daily (`coleta_status.motivo` "sem_esperar", nota "Nenhum daily de hoje encontrado").
     - `saida/2026-10-27` tem o daily 2026-10-27-daily-080001 (parcial) só com **análise** falhou; notícias aparece concluída.
     - "notícias falhou" aparece só no total do diagnóstico (`docs/diagnostico_banco.md:680`).
   - É uma foto tirada na hora em que a rotina consultou a coleta, não o estado ao vivo.
8. **Empresas afetadas:** as tabelas do diagnóstico já trazem os tickers.
   - "Empresas com quantidade de ações suspeita" → coluna `tickers` (`diagnostico/temas.py:1167`). No real: HAPV3.
   - "Retornos diários suspeitos" → `ticker` e `data` (`temas.py:1220`). No real: PCAR3 em 01/03/2021 e UGPA3 em 28/06/2021.
   - "Lacunas em v1-indices" e "Lacunas em v1-precos (mais de N pregões)" → colunas `serie, inicio, fim, tamanho, unidade` (`diagnostico/lacunas.py:18,95,114`). No real: IDIV, IFIX e SMLL de 02/01/2025 a 30/12/2025.
   - O `saude.py` já lê essas tabelas (`tabela_md`, `saude.py:54-75`).
9. **`.gitignore`:** ignora `*.log` (linha 59) e `/saida/` (linha 211), mas **não ignora `logs/`**. Então `logs/painel/api_tempos.json` ou `logs/painel/diagnostico_anterior.md` entrariam no git. Uso nomes terminados em `.log`, que já são ignorados sem mexer no `.gitignore`.
10. **Testes que vão quebrar e precisam ser atualizados:**
    - `test_painel_acoes.py:93,214` (lista exata de ações);
    - `test_painel_servidor.py:199-200` (chaves de `visao`), `:221` (faróis dos cartões) e `:241-250` (tempos);
    - `test_painel_pagina.py:280` (ids de ajuda dinâmicos);
    - `test_painel_ajuda.py:9-19` (IDS e CHAVES_FAZER) e `:30-33` (exceções de dígitos, porque "IVVB11" tem dígitos).
    - Os testes de igualdade exata de `saude.cartoes_saude` (`test_painel_saude.py:47`) e de `fluxo()["coleta"]` (`test_painel_visao.py:92`) **ficam como estão**: os dados novos entram em chaves separadas.

---

# (A) PLANO PARA O USUÁRIO

## A.1 Como a página fica

**Tela larga (a partir de 1280 px):**
```
(1) Resumo  ... igual, com pontos novos: API, Banco, Dia atípico, Coerência do mercado
(2) Fluxo do dia
+-- Última atualização · pregão de seg 26/10/2026 (?) ------------------------------------- [Concluída] -+
| 1·Coleta(?)        -> 2·Processamento(?) -> 3·Banco da API(?)   -> 4·API(?)              -> 5·Interface(?) |
| Dados entregues       Calculado e           Em dia                  No ar                    7 pacotes     |
| 8 de 9 etapas         validado              Última publ. 27/10      Status ok · banco ok     Contrato 1.0  |
| v preços v macro ...  ...                   Esperada 27/10          Última 0,84 s · média    Top 5 retido  |
| x análise (falhou)                          (pregão de 26/10)       0,91 s (10 de 10)(?)                   |
| Situação na consulta das 10:49 (?)                                  Consultada às 10:58:03                 |
| última carga completa: ... (?)                                                               12/12 da tela |
+----------------------------------------------------------------------------------------------------------+
+-- A manhã do pregão (?) ------------------------ 7/12 -+  +-- Dia atípico (?) ------------- 5/12 -+
| 08:00 ===08:15 ............ 09:45  10:00              |  | 16 ações com retorno do dia acima de   |
|                                                       |  | 30% em módulo no pregão de 26/10/2026. |
|                                                       |  | Ibovespa -13,88% · SMLL -26,92%        |
|                                                       |  | Movimento amplo do mercado (provável   |
|                                                       |  | evento real)                           |
|                                                       |  | MGLU3 -58,23%, VAMO3 -56,79%, ... e    |
|                                                       |  | mais 11  [ver todas (16)]              |
+-------------------------------------------------------+  | O que fazer: ...                       |
   (sem dia atípico, o cartão some e a manhã usa 12/12)    +----------------------------------------+
(3) Saúde dos dados (?)
| Novidades da coleta (?) · diagnóstico de 27/10/2026 10:44 comparado com o de 25/10/2026 12:48       |
| +474 balanços; índices desde 01/01/2021 (antes 02/01/2025); 1 divergência a menos; ... · e mais 6    |
| [ver tudo]                                                                                          |
| [Contrato] [Quantidade de ações · Empresas afetadas: HAPV3] [Preços suspeitos · PCAR3 (01/03/2021),  |
| UGPA3 (28/06/2021)] [Lacunas · IDIV, IFIX, SMLL (02/01/2025 a 30/12/2025)] [Horário] [Histórico]     |
| [Coerência do mercado: 1 sinal suspeito]   (a partir de 1700 px: os 7 numa linha)                    |
(4) Experimento 7/12 | (5) Histórico 5/12     (iguais)
(6) Ações
| [Rodar o dia completo (?)] [Rotina (?)] [Carga (?)] [Diagnóstico (?)] [Testes (?)]  8/12 | Testes 4/12 |
```

**Tela estreita:** o fluxo vira 2 colunas sem setas quando o cartão tem menos de 1100 px e 1 coluna abaixo de 640 px. O Dia atípico fica embaixo da manhã. O resto não muda.

## A.2 Item por item: de onde vem cada número e cada texto

**1. Fluxo completo e cartões API e Banco**
- Quem consulta é o **servidor** do painel, não o navegador: `GET <painel.api_url>/v1/saude`, sem chave.
  - Só dois cabeçalhos fixos: `Accept: application/json` e `User-Agent: painel-processamento-tcc`.
  - O tempo-limite é `painel.api_timeout_s`.
  - Consulta no máximo uma vez a cada `painel.api_intervalo_s`; nos outros pedidos usa a última resposta.
- **API:** `status`, `banco` e `ultima_publicacao` vêm da resposta (`api-tcc/api/rotas.py:147-151`). O tempo é medido pelo painel com o cronômetro em volta da chamada.
  - Sem resposta (tempo esgotado, rede ou DNS): "Sem resposta", amarelo; a página continua funcionando.
  - HTTP 503 ou `banco` diferente de "ok": "Banco da API fora", vermelho.
  - Sem `painel.api_url`: "Não configurada", cinza, e não entra no Resumo.
- **Banco:** a "última publicação completa" vem do mesmo `/v1/saude`.
  - **Data esperada = D da última rotina diária com status ok ou parcial em `saida/`.** Uso o `data_referencia` do item, que é o nome da pasta (`leitores.py:296`).
  - Motivo: uma manhã que falhou publica só a execução e **não muda** `ultima_publicacao` (`repositorio.py:20-21`). Se a esperada viesse do calendário, o cartão ficaria amarelo justamente quando o painel fez o certo.
  - O pregão mostrado entre parênteses vem de `saida/D/mercado_dia.json` → `registros[0].data_referencia`.
  - Verde "Em dia" se a última publicação for igual ou mais nova que a esperada. Amarelo "Publicação atrasada" se for mais velha. Amarelo "Nada publicado ainda" se a API responder sem nenhuma publicação. Cinza se a API não respondeu.

**2. Botão "Rodar o dia completo":** ver A.3.

**3. Novidades da coleta**
- Compara `docs/diagnostico_banco.md` com uma cópia guardada pelo painel.
  - Arquivos: `logs/painel/diagnostico_visto.log` (o último diagnóstico que o painel viu) e `logs/painel/diagnostico_anterior.log` (o de antes).
  - A cada atualização da página, se o "Gerado em" do relatório mudou, o visto vira anterior e o atual vira visto.
  - **Escolha:** isso funciona mesmo se o diagnóstico rodar pelo terminal ou falhar no meio. Se a cópia fosse feita "ao apertar o botão", um diagnóstico que falhou apagaria a cópia boa.
- O que entra, com as fontes:
  - linhas e início de cada tabela ("### Período e entidades", `diagnostico/consultas.py:260`);
  - número de divergências (`relatorios.ler_diagnostico`);
  - empresas com quantidade de ações suspeita (nota e tabela da seção 10);
  - retornos suspeitos (nota e tabela da seção 11);
  - lacunas de índices (tabela da seção 12);
  - cobertura do experimento (nota da seção 15);
  - cor de cada cartão de saúde (`saude.cartoes_saude` aplicado nas duas cópias).
- O "fim" das tabelas é ignorado, porque anda todo dia. Preços, notícias e índices crescem todo pregão, então vão para o fim da lista.
- **Primeira vez:** como ainda não há cópia, o cartão diz que as novidades aparecem a partir do próximo diagnóstico.

**4. Dia atípico**
- Fontes:
  - `saida/D/resumo_acao.json` → `rentabilidade.d1` (só status ok);
  - `saida/D/mercado_dia.json` → `IBOV.variacao_dia` e `indices.SMLL.d1`.
- D é a mesma da Banco (última diária ok ou parcial).
- Aparece quando pelo menos `painel.dia_atipico_min_acoes` ações têm |retorno| acima de `rotina.checagem.retorno_maximo_abs`.
- A frase é "Movimento amplo do mercado (provável evento real)" se |Ibovespa| passar de `painel.dia_atipico_ibov_amplo`. Senão: "Movimento isolado: conferir os dados da coleta".
- A lista vai do maior módulo para o menor e mostra os primeiros `painel.afetadas_max`, com "e mais N" e "ver todas (N)".

**5. Coerência do mercado** (cartão de saúde novo, mesmas fontes do item 4)
- Dólar × IVVB11: suspeito se tiverem sinais opostos e |IVVB11| for maior que `painel.coerencia_ivvb11_min_abs`.
- Ibovespa × mediana dos `rentabilidade.d1`: suspeito se tiverem sinais opostos e |Ibovespa − mediana| for maior que `painel.coerencia_ibov_mediana_dif`.
- Farol: amarelo se houver suspeito, verde se não houver, cinza se faltar arquivo.
- No real 26/10: "Dólar -1,45% × IVVB11 +8,96%: sentidos opostos, com o IVVB11 acima de 3% em módulo (suspeito). Ibovespa -13,88% × mediana das ações -17,46%: dentro do esperado." Resultado: **1 sinal suspeito, amarelo.**

**6. Detalhe da coleta do dia**
- Fonte: `saida/D/execucao.json` → `registros[0].coleta_status.etapas`, na ordem do arquivo, mais `ultima_consulta_em` (vira "Situação na consulta das HH:MM").
- Status mostrados: concluída, falhou, pulada, pendente (None) e "em andamento". Os que não concluíram ficam destacados.
- **Limite:** é a foto tirada quando a rotina consultou a coleta. Para ter o estado ao vivo seria preciso ler `v1-painel_etapas`, o que o painel não pode fazer (proibido: SQL e `executar_leitura`), ou mudar a rotina, que fica fora do painel (ponto P5).

**7. Empresas afetadas em cada cartão de saúde:** vêm das tabelas citadas no item 8 dos fatos.
- Contrato: coluna `Tabela` das divergências; o "-" é ignorado.
- Coerência: as séries envolvidas.
- Horário das notícias e Histórico disponível não têm lista.
- Mostra os primeiros `painel.afetadas_max`, depois "e mais N" e o bloco "ver todas (N)".

**8. Tempo de resposta da API**
- Cada consulta real grava uma linha JSON em `logs/painel/api_tempos.log`: `{"em": ISO, "ms": int|null, "http": int|null, "ok": bool}`. Fica só com as últimas `painel.api_medicoes`.
- A média usa só as medições com resposta. O cartão mostra a última e a média.
- Média acima de `painel.api_tempo_limite_s` deixa o cartão amarelo, com "O que fazer: Conferir a região do Railway (US East é a mais próxima do Brasil)."

## A.3 "Rodar o dia completo": o que acontece em cada caso

**Pede confirmação:** sim, o mesmo `confirm()` dos outros botões (`pagina.html:1670-1672`). O texto traz a data, as 3 etapas e o aviso de que grava no banco da API.

**Bloqueios do botão:**
- outra ação rodando;
- trava da rotina ativa;
- produção (`treino.teste_final.fim` preenchido; mesma regra do botão da rotina);
- calendário com erro;
- `painel.dir_api` ausente;
- pasta ou `.venv` do projeto da API não encontrados;
- `publicador/__main__.py` ausente.

**Não pode ser parado no meio.**

| Rotina | Carga completa | Publicador | Resultado na API | Código |
|---|---|---|---|---|
| ok | roda | roda | publicação completa de D; `/v1/saude` passa a mostrar D | 0 |
| parcial | roda | roda | publicação completa de D, com as pendências no `execucao` | 0 |
| falhou (sem `saida_completa/D/`) | pulada | roda e grava **só a execução** (`so_execucao`) | `ultima_publicacao` não muda; `/v1/execucao/ultima` mostra "falhou" | 0 |
| falhou e `saida_completa/D/` já existe de antes | pulada | **não roda** (publicaria a carga antiga junto) | nada | 6 |
| não gerou execução nova (sem pregão, configuração, banco, trava) | pulada | não roda | nada | 3 |
| ok ou parcial, mas a carga falhou | falhou | não roda | nada | 4 |
| publicador recusou (validação) | — | código 1 | publicador registra "rejeitada" | 1 |
| publicador: configuração ou banco | — | código 2 | nada | 5 |
| painel sem a pasta ou o Python da API | não roda nada | — | nada | 2 |

A rotina usa `--sem-esperar`, como o botão da rotina. O publicador roda sempre com argv fixo: `<api>/.venv/Scripts/python.exe -m publicador --data D`, com cwd na pasta da API. **Nunca** usa `--forcar` nem `--criar-tabelas`.

## A.4 Textos novos de ajuda ("?"), para o `ajuda.py`

Sem dígitos escritos à mão. "IVVB11" passa a ser exceção do teste, como "B3".

| id | Título | Texto |
|---|---|---|
| api | API | É o serviço na internet que entrega ao site os dados já publicados. O painel pergunta só se ela está no ar, numa rota pública que não pede chave, e nunca envia chave nem senha. Mostra se a API respondeu, se o banco dela respondeu, a data da última publicação completa e quanto tempo a resposta levou. Se a API não responder a tempo, aparece "sem resposta" e o resto do painel continua funcionando. A consulta é feita por este computador, não pelo navegador, e se repete de tempos em tempos. |
| banco_api | Banco da API | É o banco onde o publicador grava os pacotes do processamento e de onde a API lê. A data mostrada é a da última publicação completa (com a carga completa), informada pela própria API. Ela é comparada com a data da última rotina diária que terminou bem (ok ou com pendências): se for mais antiga, falta publicar essa data. Uma manhã em que a rotina falhou publica só o registro da execução e não muda essa data. A data é a da pasta da rotina (a manhã); o pregão dos dados é o pregão anterior. |
| tempo_api | Tempo de resposta da API | Quanto tempo a API levou para responder, medido por este computador. O painel guarda as últimas medições na pasta logs/painel/ e mostra a última e a média. Média acima de {tempo_limite_api} fica amarela. A distância até o servidor pesa: um servidor longe do Brasil responde mais devagar. |
| novidades | Novidades da coleta | Compara o relatório do diagnóstico atual com o anterior, que o painel guarda na pasta logs/painel/ sempre que percebe um diagnóstico novo. Mostra só o que mudou de verdade: linhas e início das tabelas, divergências, empresas com quantidade de ações suspeita, preços suspeitos, lacunas, o histórico do experimento e a cor dos cartões de saúde. Tabelas que crescem todo pregão (preços, notícias e índices) aparecem no fim da lista. A primeira comparação aparece depois do segundo diagnóstico visto pelo painel. |
| dia_atipico | Dia atípico | Aparece quando pelo menos {atipico_min_acoes} ações tiveram, no mesmo pregão, retorno acima de {atipico_retorno} em módulo, para cima ou para baixo. Para separar um evento real de um erro da coleta, o cartão mostra também a variação do Ibovespa e do índice de empresas menores (SMLL) no mesmo dia. Se o Ibovespa se moveu mais que {atipico_ibov}, o movimento foi amplo e provavelmente real. Se não, as ações se moveram sozinhas e vale conferir os dados da coleta. Os números vêm dos pacotes do último pregão processado (pasta saida/). |
| etapas_coleta | Etapas da coleta | Lista as etapas do daily da coleta usado pela rotina, com a situação de cada uma no momento em que a rotina consultou o painel da coleta: concluída, falhou, pulada ou pendente (sem registro ainda). As que não concluíram ficam destacadas. O processamento espera a etapa "entrega"; se uma destas não concluir, vira aviso na rodada: {etapas_conferidas}. Se a coleta terminar uma etapa depois, a lista só muda quando a rotina rodar de novo. |
| saude_coerencia_mercado | Coerência do mercado | O que é: confere se os números do mercado no último pregão processado fazem sentido juntos. Dólar e IVVB11 (fundo que segue a bolsa americana, cotado em reais): se andam em sentidos opostos e o IVVB11 se move mais de {coerencia_ivvb11}, é suspeito, porque a bolsa americana teria de ter se movido ainda mais. Ibovespa e a mediana dos retornos das ações: se andam em sentidos opostos com diferença maior que {coerencia_dif}, também é suspeito. Por que está amarelo: um desses pares não bateu. O processamento não muda nenhum número por causa deste cartão: ele só avisa. Quando a coleta corrigir: o cartão volta ao verde na próxima rotina. |
| acao_dia | Rodar o dia completo | O que faz: em sequência, roda a rotina do dia, gera a carga completa e chama o publicador do projeto da API, que grava os pacotes no banco da API. É a única ação do painel que grava num banco. Se a rotina terminar ok ou com pendências, a carga completa e o publicador rodam. Se a rotina falhar, a carga completa não roda e o publicador grava só o registro da execução, para o site avisar que os dados são do pregão anterior. Se a rotina não gerar nada (dia sem pregão, configuração, banco ou trava), nada é publicado. O publicador roda com o Python do projeto da API, que lê as próprias configurações: o painel não lê nem envia nenhuma senha ou chave. Não pode ser parado no meio. Nunca escreve no banco da coleta. |

**Campos novos e valores com o yaml real:**
- `{tempo_limite_api}` = "2 s";
- `{atipico_min_acoes}` = "5";
- `{atipico_retorno}` = "30%" (vem de `rotina.checagem.retorno_maximo_abs`);
- `{atipico_ibov}` = "5%";
- `{coerencia_ivvb11}` = "3%";
- `{coerencia_dif}` = "2%";
- `{etapas_conferidas}` = "precos, noticias, enriquecimento" (vem de `rotina.etapas_conferidas`, `parametros.yaml:226`).

## A.5 Textos novos de "O que fazer"

| Chave | Quando aparece | Texto |
|---|---|---|
| api_sem_resposta | API sem resposta, ou resposta inesperada | Abrir o endereço da API no navegador. Se continuar sem resposta, ver no painel do Railway se o serviço está no ar. Enquanto isso, o site fica sem dados novos. |
| api_banco_fora | 503 ou banco diferente de "ok" | A API está no ar, mas o banco dela não respondeu. Ver no painel do Railway se o banco está ligado. |
| api_lenta | média acima do limite | Conferir a região do Railway (US East é a mais próxima do Brasil). |
| banco_atrasado | publicação mais velha que a esperada, ou nada publicado | Rodar o dia completo (seção Ações) ou, no projeto da API, o publicador para a data esperada. |
| saude_coerencia_mercado | Coerência amarela | Conferir na coleta os preços do dólar, do IVVB11 e do Ibovespa nesse pregão. Se forem erro, avisar a coleta e rodar a rotina de novo depois da correção. |
| dia_atipico_amplo | dia atípico com Ibovespa acima do limite | Nada no processamento: é um aviso de evento de mercado, não um erro dos dados. O mercado inteiro se moveu junto. Vale só confirmar no noticiário o que aconteceu nesse pregão. |
| dia_atipico_isolado | dia atípico sem movimento amplo | Conferir na coleta os preços dessas ações nesse pregão antes de confiar nos indicadores do dia. Se for erro, avisar a coleta e rodar a rotina de novo depois da correção. |

## A.6 Parâmetros novos (`processamento/config/parametros.yaml`, acrescentados no fim do arquivo)

```yaml
# Painel de operação (processamento/painel). Só o painel lê este bloco. URLs, caminhos e horas ENTRE ASPAS.
painel:
  api_url: "https://api-processamento-tcc-production.up.railway.app"  # base da API publicada; o painel consulta só /v1/saude (pública, sem chave)
  api_timeout_s: 5                 # espera máxima da consulta; passou disso = "sem resposta"
  api_intervalo_s: 60              # no máximo uma consulta a cada N segundos (a página atualiza a cada 30 s)
  api_tempo_limite_s: 2.0          # média do tempo de resposta acima disto = amarelo
  api_medicoes: 10                 # medições guardadas em logs/painel/api_tempos.log
  dir_api: "../api-tcc"            # pasta do projeto da API (relativa a esta raiz); o publicador roda com o .venv de lá
  dia_atipico_min_acoes: 5         # dia atípico: pelo menos N ações com |retorno do dia| acima de rotina.checagem.retorno_maximo_abs
  dia_atipico_ibov_amplo: 0.05     # |variação do Ibovespa| acima disto = movimento amplo (provável evento real)
  coerencia_ivvb11_min_abs: 0.03   # dólar × IVVB11 em sentidos opostos e |IVVB11| acima disto = suspeito
  coerencia_ibov_mediana_dif: 0.02 # Ibovespa × mediana das ações em sentidos opostos e diferença acima disto = suspeito
  afetadas_max: 5                  # itens mostrados por cartão antes de "e mais N"
```

Parâmetro que falta ou é inválido vira None, e o cartão correspondente diz qual parâmetro falta. Não há valor padrão escrito no código.

## A.7 Arquivos que mudam (todos dentro do escopo permitido)

- **Novos:**
  - `processamento/painel/api.py` (consulta ao `/v1/saude` e tempos);
  - `processamento/painel/mercado.py` (dia atípico e coerência);
  - `processamento/painel/novidades.py` (cópias e comparação do diagnóstico);
  - `processamento/painel/dia.py` (orquestrador do dia completo).
- **Mudam:** `leitores.py`, `ajuda.py`, `saude.py` (função nova, sem mudar as atuais), `visao.py`, `acoes.py`, `marcos.py`, `servidor.py`, `pagina.html` e `processamento/config/parametros.yaml` (bloco `painel`).
- **Testes novos:** `tests/test_painel_api.py`, `test_painel_mercado.py`, `test_painel_novidades.py`, `test_painel_dia.py`. Acréscimos nos testes existentes listados no item 10 dos fatos.
- **Fixtures:**
  - `tests/dados/painel/raiz/processamento/config/parametros.yaml` (bloco `painel` sem `api_url` e sem `dir_api`, mais `rotina.checagem` e `rotina.etapas_conferidas`);
  - `tests/dados/painel/raiz/saida/2026-10-23/{mercado_dia,resumo_acao}.json`;
  - `tests/dados/painel/pregao_2026-10-26/{mercado_dia,resumo_acao}.json` (cópias recortadas dos arquivos reais);
  - `tests/dados/painel/novidades/{anterior,atual}.md`.
- **Arquivos gravados pelo painel em uso** (todos `.log`, já ignorados pelo git): `logs/painel/api_tempos.log`, `diagnostico_visto.log`, `diagnostico_anterior.log` e `dia-*.log`.

## A.8 Testes (resumo; os valores exatos estão nas fases da parte B)

- **Caso real de 26/10, item 4:** a fixture é recortada de `saida/2026-10-27/`.
  - Resultado: ativo, 16 ações, "Ibovespa -13,88%", "SMLL -26,92%", "Movimento amplo do mercado (provável evento real)".
  - Primeiras 5: MGLU3 -58,23%, VAMO3 -56,79%, HAPV3 -54,93%, RAPT4 -48,39%, CSAN3 -46,73%.
  - Com `ibov_amplo` de 0,20, a frase vira a do movimento isolado.
- **Caso real de 26/10, item 5:** amarelo, "1 sinal suspeito", dólar "-1,45%" × IVVB11 "+8,96%". O Ibovespa (-13,88%) e a mediana (-17,46%) ficam dentro do esperado.
- **Caso de fronteira (pregão de 22/10, valores reais de `saida/2026-10-23/`):**
  - dólar +0,26% × IVVB11 -0,90%: sentidos opostos, mas abaixo de 3%, então ok;
  - Ibovespa -1,15% × mediana +0,14%: sentidos opostos com diferença de 1,29%, abaixo de 2%, então ok;
  - com o limite em 1%, vira suspeito.
- **Chave da API:**
  - o pedido montado tem só os cabeçalhos accept e user-agent (sem authorization, x-api-key, cookie), método GET, URL `<base>/v1/saude` e corpo vazio;
  - nenhum arquivo do painel contém "X-API-Key", "Authorization", ".env" ou "load_dotenv";
  - com um `.env` falso numa pasta de API temporária, o `/api/painel` não devolve o segredo e nenhuma função do painel abre arquivo terminado em ".env" (`open` e `io.open` monitorados);
  - o ambiente do publicador não leva as variáveis do banco nem `PROC_*`.
- **Nenhum teste usa rede:** a chamada HTTP é injetada, e um fixture automático bloqueia `socket.connect` nos testes da API.

## A.9 Riscos

1. A consulta à API acontece dentro do pedido da página, no máximo uma vez a cada 60 s e com até 5 s de espera. Uma atualização a cada minuto pode demorar até 5 s. Ela fica isolada por `_seguro` e pelo cache.
2. As etapas da coleta são uma foto do momento em que a rotina consultou a coleta, não o estado ao vivo (ver P5).
3. O "Dia atípico" usa o Ibovespa da própria coleta. Se o erro atingir a base inteira (por exemplo, todos os preços de uma fonte errada), o cartão vai dizer "amplo (provável evento real)". 26/10 cai exatamente nesse caso (Ibovespa -13,88%, SMLL -26,92%), então vale conferir fora do painel.
4. Cinco estágios no fluxo apertam a tela; por isso o fluxo passa a ocupar 12/12 e a manhã desce.
5. É a primeira ação do painel que grava num banco (o da API). Os cuidados: argv fixo, sem `--forcar`, confirmação e bloqueio em produção.

## A.10 Pontos para você decidir (com minha recomendação)

- **P1. Nomes dos arquivos em `logs/painel/`:** `logs/` não está no `.gitignore`. **Recomendo** a extensão `.log` (já ignorada) em vez de mexer no `.gitignore`. Alternativa: você acrescenta `/logs/` ao `.gitignore`.
- **P2. Rotina falhou, mas já existe `saida_completa/D/` antiga:** o publicador publicaria essa carga antiga junto. **Recomendo** não rodar o publicador (código 6) e explicar no log.
- **P3. "Pregão esperado" do cartão Banco:** **recomendo** a D da última rotina diária ok ou parcial, e não o calendário (motivo em A.2, item 1).
- **P4. Dia atípico "amplo" entra no Resumo?** **Recomendo** que sim, amarelo, com "O que fazer: Nada no processamento…". Alternativa: só mostrar o cartão, sem contar como ponto.
- **P5. Etapas da coleta ao vivo:** exigiria mexer **fora do painel** (a rotina gravar um arquivo de status) ou ler o banco (proibido no painel). **Recomendo** aceitar agora a foto do `execucao.json` e decidir depois.

---

# (B) PLANO PARA OS IMPLEMENTADORES (Haiku)

## Regras para todas as fases (copiar em todo despacho)

- Projeto `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc`, Windows. Python: `.venv\Scripts\python.exe`. Responder em português. **Não fazer commit.**
- **Só mexer em:** `processamento/painel/`, `tests/test_painel_*.py`, `tests/fabrica_painel.py`, `tests/dados/painel/` e (só na Fase 1) `processamento/config/parametros.yaml`. Não mexer em `conftest.py`, na especificação nem no `.gitignore`.
- **Nunca abrir nenhum arquivo `.env`** (nem deste projeto nem do `C:\Users\danie\Desktop\TCC\Arquivos\api-tcc`).
  - Não rodar nada que acesse banco ou rede: nada de `python -m processamento.rotina`, `processamento.saida`, `processamento.diagnostico`, `publicador`, nem de servidor de verdade.
  - Não rodar comandos do `api-tcc`.
- Os `processamento/painel/*.py` **não podem conter** "SELECT", "executar_leitura", "create_engine", "load_dotenv", `.env"` nem "shell=True" (`test_painel_servidor.py:484-489`).
  - Nos arquivos novos (`api.py`, `dia.py`, `mercado.py`, `novidades.py`), não escrever ".env", "X-API-Key" nem "Authorization", nem em comentário.
  - Não importar `processamento.fontes`, `sqlalchemy` nem `dotenv` (`test_painel_servidor.py:475-481`).
  - Não importar `processamento.experimento.*` nem `processamento.diagnostico.*` no painel.
- **Nada de número escrito à mão:** todo valor vem do yaml, dos arquivos de `saida/` ou `docs/`, ou da resposta HTTP. Parâmetro ausente vira None.
- **Funções de leitura** nunca levantam exceção por arquivo ausente ou quebrado. Ausência = None ou "sem dados", nunca 0. Fuso: `from processamento.calendario import SP`; ISO sem fuso = São Paulo (`leitores._instante`).
- Todo módulo novo começa com docstring curta e `from __future__ import annotations`. Sem emoji.
- **Formatação brasileira:**
  - percentuais com sinal: `f"{x*100:+.2f}".replace(".", ",") + "%"` (−0.0145 → "-1,45%");
  - percentual de parâmetro: `f"{v*100:g}".replace(".", ",") + "%"` (0.30 → "30%");
  - segundos: `f"{ms/1000:.2f}".replace(".", ",") + " s"`;
  - data: dd/mm/aaaa;
  - milhar com ponto: `f"{n:,}".replace(",", ".")`.
- **Testes:**
  - usam `montar_raiz(tmp_path)` (`from fabrica_painel import montar_raiz`) e nunca escrevem em `tests/dados/` durante o teste;
  - não usam rede (HTTP injetado; nos testes de API, bloquear `socket.socket.connect` com monkeypatch);
  - não usam banco.
- **Página (`pagina.html`):**
  - DOM só com `createElement`/`createElementNS` + `textContent`/`createTextNode`;
  - proibidos `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` e `eval(`;
  - nenhum "http://", "https://" ou `<link` escrito;
  - nunca escrever "simular" nem "passo(";
  - palavras proibidas: "compre" (cuidado com "compreender"), "oportunidade", "melhores ações" e "recomendação" (exceto a frase exata já existente);
  - botões "?" novos criados **pelo JS** com `botaoAjuda("id")` literal, para manter as 14 ajudas estáticas (`test_painel_pagina.py:282,290`);
  - nunca pôr "?" dentro de um elemento cujo `textContent` o JS reescreve.
- **Textos do `ajuda.py`:** sem dígitos fora de `{campos}`, "top 5", "B3", "95%" e (novo) "IVVB11". Sem "http" nem "select" em minúsculas (`test_painel_ajuda.py:23,54-64`).
- **Verificação de cada fase:** rodar **só os arquivos de teste da fase**: `.venv\Scripts\python -m pytest -q <arquivos>`. Os testes que cruzam fases só passam depois da Onda 3.

## Ordem e paralelismo

| Onda | Fases (em paralelo dentro da onda; arquivos não se cruzam) | Depende de |
|---|---|---|
| 1 | F1 (yaml + leitores) ∥ F2 (ajuda) ∥ F3 (api) ∥ F4 (mercado) ∥ F5 (novidades + saude.afetadas) | — |
| 2 | F6 (dia.py + acoes + marcos) ∥ F7 (visao) | F6 depende de F1; F7 depende de F2 |
| 3 | F8 (servidor) ∥ F9 (página) | F8 de F1–F7; F9 de F2, F5, F6 (testes de ids) |
| 4 | F10: verificação (executor): `.venv\Scripts\python -m pytest -q tests/test_painel_*.py` e depois `.venv\Scripts\python -m pytest -q` | todas |

## Contrato JSON novo (`/api/painel` → `visao`), que F7, F8 e F9 seguem

```
visao.api = {"configurada": bool, "estado": "ok|warn|bad|idle", "titulo": str, "status": str|None, "banco": str|None,
             "ultima_publicacao": "AAAA-MM-DD"|None, "consultado_em": "HH:MM:SS"|None,
             "tempo": {"ultima_s","media_s","n","n_com_resposta","limite_s","acima_limite","texto"},
             "linhas": [str], "pontos": [{"nivel","texto","chave"}]}
visao.banco = {"estado","titulo","ultima_publicacao","esperada","linhas":[str],"pontos":[...]}
visao.coleta_etapas = {"disponivel": bool, "motivo": str|None, "consulta_hhmm": str|None, "daily": str|None,
                       "etapas": [{"id","rotulo","status","texto","destaque"}], "nao_concluidas": [str], "resumo": str|None}
visao.novidades = {"disponivel": bool, "motivo": str|None, "atual_em": str|None, "anterior_em": str|None,
                   "frase": str|None, "itens": [{"texto","tipo":"mudanca|crescimento"}]}
visao.dia_atipico = {"disponivel": bool, "ativo": bool, "motivo", "data_pregao", "n", "texto", "ibov_texto",
                     "smll_texto", "amplo": bool|None, "frase", "acoes": [{"ticker","texto"}], "max", "fonte", "pontos"}
visao.saude = {...como hoje..., "cartoes": [6 do diagnóstico + coerencia_mercado], "afetadas": {id: {"titulo","itens":[{"rotulo","detalhe"}],"total"}}, "afetadas_max": int|None}
botoes.dia = {"titulo": "Rodar o dia completo", "comando", "habilitado", "motivo", "aviso", "data"}
```

---

### F1: parâmetros e leitores (Onda 1)

**Arquivos:**
- `processamento/config/parametros.yaml` (acrescentar no fim, depois da linha 235, o bloco de A.6 exatamente);
- `tests/dados/painel/raiz/processamento/config/parametros.yaml`;
- `processamento/painel/leitores.py`;
- `tests/test_painel_leitores.py`.

**Fixture yaml.** Dentro de `rotina:` acrescentar:
```yaml
  etapas_conferidas: ["precos", "noticias", "enriquecimento"]
  checagem:
    retorno_maximo_abs: 0.30
```
E no fim do arquivo (sem `api_url` e sem `dir_api`, de propósito: assim os testes do servidor não chamam rede e o botão do dia fica bloqueado):
```yaml
painel:
  api_timeout_s: 5
  api_intervalo_s: 60
  api_tempo_limite_s: 2.0
  api_medicoes: 10
  dia_atipico_min_acoes: 5
  dia_atipico_ibov_amplo: 0.05
  coerencia_ivvb11_min_abs: 0.03
  coerencia_ibov_mediana_dif: 0.02
  afetadas_max: 5
```

**`leitores.py`:**
1. Nova `ler_parametros_painel(raiz: Path) -> dict`. Lê o yaml como `ler_valores_ajuda` faz (`leitores.py:156-161`) e devolve **todas** as chaves, com None se faltar ou for inválido. Validação:

   | Chave | Validação |
   |---|---|
   | `api_url` | str não vazia |
   | `api_timeout_s` | número > 0 |
   | `api_intervalo_s` | número ≥ 0 |
   | `api_tempo_limite_s` | número > 0 |
   | `api_medicoes` | int > 0 |
   | `dir_api` | str não vazia |
   | `dia_atipico_min_acoes` | int > 0 |
   | `dia_atipico_ibov_amplo` | número > 0 |
   | `coerencia_ivvb11_min_abs` | número > 0 |
   | `coerencia_ibov_mediana_dif` | número > 0 |
   | `afetadas_max` | int > 0 |
   | `retorno_dia_abs` | `rotina.checagem.retorno_maximo_abs`, número > 0 |

   Usar `_numero`/`_inteiro` (`:141-146`); bool não conta como número.
2. Nova `ultima_execucao_valida(itens: list[dict]) -> dict | None` = `ultima_execucao([i for i in itens if i.get("legivel") and i.get("status") in ("ok", "parcial")])`.
3. Em `_resumir_coleta` (`:257-270`), acrescentar `"consulta_hhmm": _hhmm_sp(coleta.get("ultima_consulta_em"))`.
4. Estender `CHAVES_AJUDA` (`:137-138`) com "tempo_limite_api", "atipico_min_acoes", "atipico_retorno", "atipico_ibov", "coerencia_ivvb11", "coerencia_dif", "etapas_conferidas". Em `ler_valores_ajuda` (`:176-189`), preencher:
   - tempo_limite_api = `f"{v:g}".replace(".", ",") + " s"`;
   - atipico_min_acoes = `str(int)`;
   - atipico_retorno, atipico_ibov, coerencia_ivvb11 e coerencia_dif = `f"{v*100:g}".replace(".", ",") + "%"`;
   - etapas_conferidas = `", ".join(lista)` se for lista de str.

   O `vazio` (`:155`) continua sendo `dict.fromkeys(CHAVES_AJUDA)`.

**Testes (`test_painel_leitores.py`, acrescentar):**
- Com `montar_raiz`, `ler_parametros_painel(raiz)` dá: `api_url` None, `dir_api` None, `api_timeout_s` 5, `api_tempo_limite_s` 2.0, `retorno_dia_abs` 0.30, `afetadas_max` 5.
- Real (só leitura): `ler_parametros_painel(REPO)` dá `api_url == "https://api-processamento-tcc-production.up.railway.app"`, `dir_api == "../api-tcc"`, `retorno_dia_abs == 0.30`, `dia_atipico_ibov_amplo == 0.05`.
- yaml com `painel: {api_medicoes: true, api_timeout_s: "x"}` em tmp: os dois viram None.
- `ler_valores_ajuda(raiz)` (fixture) dá "tempo_limite_api" "2 s", "atipico_retorno" "30%", "atipico_ibov" "5%", "coerencia_ivvb11" "3%", "coerencia_dif" "2%", "atipico_min_acoes" "5", "etapas_conferidas" "precos, noticias, enriquecimento".
- `ultima_execucao_valida`: lista com um item "falhou" (gerado_em mais novo) e um "ok" devolve o "ok"; lista vazia devolve None.
- `resumir_execucao` com `coleta_status.ultima_consulta_em = "2026-10-27T10:49:32-03:00"` dá `coleta["consulta_hhmm"] == "10:49"`.

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_leitores.py`

---

### F2: textos (`ajuda.py`) (Onda 1)

**Arquivos:** `processamento/painel/ajuda.py`, `tests/test_painel_ajuda.py`.
- Acrescentar a `CAMPOS` (`ajuda.py:13-16`): "tempo_limite_api", "atipico_min_acoes", "atipico_retorno", "atipico_ibov", "coerencia_ivvb11", "coerencia_dif", "etapas_conferidas".
- Acrescentar a `AJUDA` os 8 ids da tabela A.4: api, banco_api, tempo_api, novidades, dia_atipico, etapas_coleta, saude_coerencia_mercado, acao_dia. Títulos e textos **exatamente** como estão lá, entre aspas simples (os textos usam aspas duplas e nunca apóstrofo).
- Acrescentar a `O_QUE_FAZER` as 7 chaves da tabela A.5, com os textos exatos.
- **No teste:**
  - `IDS` (`:9-14`) recebe os 8 ids novos;
  - `CHAVES_FAZER` (`:15-19`) recebe as 7 chaves novas;
  - em `_sem_placeholders_e_excecoes` (`:30-33`), acrescentar `.replace("IVVB11", "")`.
- **Teste novo:** `montar_ajuda({"atipico_min_acoes": "5", "atipico_retorno": "30%", "atipico_ibov": "5%", "coerencia_ivvb11": "3%", "coerencia_dif": "2%", "tempo_limite_api": "2 s", "etapas_conferidas": "precos, noticias, enriquecimento"})`:
  - "pelo menos 5 ações", "acima de 30% em módulo" e "mais que 5%" estão em `["dia_atipico"]["texto"]`;
  - "mais de 3%" e "maior que 2%" estão em `["saude_coerencia_mercado"]["texto"]`;
  - "Média acima de 2 s fica amarela" está em `["tempo_api"]["texto"]`;
  - "nunca envia chave nem senha" está em `["api"]["texto"]`.

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_ajuda.py`

---

### F3: `api.py` (consulta ao `/v1/saude` e tempos) (Onda 1)

**Arquivos:** novo `processamento/painel/api.py`, novo `tests/test_painel_api.py`.

**Funções:**
```python
ARQUIVO_TEMPOS = "api_tempos.log"
LIMITE_CORPO = 65536
CABECALHOS = {"Accept": "application/json", "User-Agent": "painel-processamento-tcc"}

def validar_url(texto: object) -> tuple[str | None, str | None]:
    """(base sem barra final, None) ou (None, motivo). Aceita só https://host[:porta] ou http://127.0.0.1|localhost[:porta]."""
def consultar_saude(url_base: str, timeout_s: float, *, abrir=None, cronometro=time.perf_counter) -> dict:
    """GET <base>/v1/saude sem chave. {"respondeu","http","ms","status","banco","ultima_publicacao","erro"}."""
def ler_medicoes(arquivo: Path) -> list[dict]
def gravar_medicao(arquivo: Path, medicao: dict, manter: int) -> None   # OSError é engolido
def resumo_tempos(medicoes: list[dict], limite_s: float | None) -> dict
class MonitorApi:
    def __init__(self, pasta_painel: Path, *, consultar=consultar_saude, monotonic=time.monotonic): ...
    def situacao(self, params_painel: dict, agora: datetime) -> dict:
        """{"configurada","erro_config","timeout_s","consulta","consultado_em","medicoes"}; usa cache por api_intervalo_s (threading.Lock)."""
```

**Detalhes de `validar_url`:**
- regex https: `^https://[A-Za-z0-9.-]+(:\d{1,5})?/?$`;
- regex local: `^http://(127\.0\.0\.1|localhost)(:\d{1,5})?/?$`;
- recusar se tiver "@", caminho ou consulta;
- motivos: None → "Sem painel.api_url no parametros.yaml."; inválida → "painel.api_url inválida: use https://domínio, sem usuário, senha, caminho ou consulta."

**Detalhes de `consultar_saude`:**
- `abrir = abrir or urllib.request.urlopen`, resolvido **dentro** da função;
- `urllib.request.Request(url_base + "/v1/saude", method="GET", headers=dict(CABECALHOS))`;
- `HTTPError` → usa `e.code` e `e.read(LIMITE_CORPO)`;
- `URLError`, `TimeoutError`, `OSError` ou `ValueError` → `{"respondeu": False, "http": None, "ms": None, "status": None, "banco": None, "ultima_publicacao": None, "erro": type(e).__name__}`;
- `ms = int(round((t1 - t0) * 1000))`;
- JSON inválido → status, banco e ultima_publicacao None;
- `ultima_publicacao` só se casar `^\d{4}-\d{2}-\d{2}$`.

**Detalhes de `MonitorApi.situacao`:**
- url inválida, ou `api_timeout_s`, `api_intervalo_s` ou `api_medicoes` None → `configurada False`, `consulta None` e `erro_config` com o motivo; para parâmetros: "Parâmetros painel.api_* incompletos no parametros.yaml.";
- consulta nova → grava `{"em": agora.isoformat(timespec="seconds"), "ms", "http", "ok": respondeu}` em `pasta_painel/api_tempos.log`, guardando as `api_medicoes` últimas linhas (uma linha JSON por medição);
- `consultado_em` = ISO de quando consultou.

**Detalhes de `resumo_tempos`:**
- n = len(medicoes); com = medições com ms int; media_s = média(ms)/1000 ou None; ultima_s = ms da última medição /1000, ou None;
- `acima_limite = media_s is not None and limite_s is not None and media_s > limite_s`;
- texto = `f"Última: {ult} · média {med} ({len(com)} de {n} com resposta)"`, com `ult` = "0,90 s" ou "sem resposta" e `med` = "0,90 s" ou "sem medição".

**Testes (todos com fixture autouse que faz `monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(OSError("rede bloqueada no teste")))`):**
1. `consultar_saude("https://api.exemplo.invalid", 5, abrir=falso, cronometro=iter([10.0, 10.84]).__next__)`, com o falso gravando o Request e devolvendo um objeto de contexto com `.status = 200` e `.read(n) = b'{"status":"ok","banco":"ok","ultima_publicacao":"2026-10-27"}'`.
   - Resultado == `{"respondeu": True, "http": 200, "ms": 840, "status": "ok", "banco": "ok", "ultima_publicacao": "2026-10-27", "erro": None}`.
   - Request: `get_method() == "GET"`, `full_url == "https://api.exemplo.invalid/v1/saude"`, `data is None`, `{k.lower() for k, _ in req.header_items()} == {"accept", "user-agent"}`.
2. Falso levantando `urllib.error.HTTPError(url, 503, "x", {}, io.BytesIO(b'{"status":"erro","banco":"fora"}'))` → respondeu True, http 503, banco "fora".
3. Falso levantando `urllib.error.URLError("x")` → respondeu False, erro "URLError", ms None.
4. `validar_url`:
   - "https://api-processamento-tcc-production.up.railway.app/" → ("https://api-processamento-tcc-production.up.railway.app", None);
   - "http://127.0.0.1:8000" ok;
   - "http://exemplo.com", "https://u:s@x.com", "https://x.com/v1" e "https://x.com?a=1" → (None, motivo);
   - None → (None, "Sem painel.api_url no parametros.yaml.").
5. `MonitorApi(tmp, consultar=falso_contador, monotonic=lambda: t[0])` com params {api_url válida, timeout 5, intervalo 60, medicoes 3}:
   - 2 chamadas com t=0 e t=30 → falso chamado 1 vez;
   - t=61 → 2 vezes;
   - depois de 5 consultas (avançando o tempo), `api_tempos.log` tem 3 linhas.
6. `resumo_tempos([{"ms":800},{"ms":1000},{"ms":None},{"ms":900}], 2.0)` → media_s 0.9, ultima_s 0.9, n 4, n_com_resposta 3, acima_limite False, texto "Última: 0,90 s · média 0,90 s (3 de 4 com resposta)". Com limite 0.5 → acima_limite True.
7. Fonte de `api.py` sem "X-API-Key", "Authorization", ".env", "load_dotenv" e "environ".

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_api.py`

---

### F4: `mercado.py` (dia atípico e coerência) e fixtures (Onda 1)

**Arquivos:**
- novo `processamento/painel/mercado.py`;
- novo `tests/test_painel_mercado.py`;
- fixtures `tests/dados/painel/pregao_2026-10-26/` e `tests/dados/painel/raiz/saida/2026-10-23/{mercado_dia,resumo_acao}.json`.

**Gerar as fixtures uma vez** a partir dos arquivos reais (só lê `saida/`; não acessa banco). Na raiz, rodar `.venv\Scripts\python -c "<script>"`:
```python
import json, shutil
from pathlib import Path
def recorte(src, dst, tickers=None):
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "mercado_dia.json", dst / "mercado_dia.json")
    env = json.loads((src / "resumo_acao.json").read_text(encoding="utf-8"))
    regs = [{"ticker": r["ticker"], "data_referencia": r["data_referencia"], "rentabilidade": {"d1": r["rentabilidade"]["d1"]}}
            for r in env["registros"] if tickers is None or r["ticker"] in tickers]
    (dst / "resumo_acao.json").write_text(json.dumps({"pacote": "resumo_acao", "registros": regs}, ensure_ascii=False, indent=1), encoding="utf-8")
recorte(Path("saida/2026-10-27"), Path("tests/dados/painel/pregao_2026-10-26"))
recorte(Path("saida/2026-10-23"), Path("tests/dados/painel/raiz/saida/2026-10-23"), {"ABEV3", "PETR4", "VALE3"})
```
**Cuidado:** a pasta `raiz/saida/2026-10-23/` já tem o `execucao.json` da fixture. **Não** sobrescrever esse arquivo; só acrescentar os dois.

**Funções:**
```python
def pct2(x: float) -> str          # f"{x*100:+.2f}".replace(".", ",") + "%"
def ler_dia(raiz: Path, pasta_saida: str, d: str | None) -> dict:
    """{"disponivel","motivo","d","data_pregao","ibov","usd","ivvb11","smll","retornos":[[ticker, valor]],"fonte"}.
    mercado_dia registros[0]: IBOV.variacao_dia, USDBRL.variacao_dia, indices.IVVB11.d1, indices.SMLL.d1 (valor só se status=="ok" e número).
    resumo_acao: (ticker, rentabilidade.d1.valor) só com status "ok". fonte = f"{pasta_saida}/{d}/mercado_dia.json e resumo_acao.json"."""
def dia_atipico(dados: dict, limites: dict) -> dict      # limites: retorno_abs, min_acoes, ibov_amplo, max
def cartao_coerencia(dados: dict, limites: dict) -> dict # limites: ivvb11_min, dif_min -> {"cartao": {...}, "afetadas": {...}|None}
```

**Regras de `dia_atipico`:**
- `grandes = sorted([(t, v) for t, v in retornos if abs(v) > retorno_abs], key=lambda x: (-abs(x[1]), x[0]))`;
- `ativo = len(grandes) >= min_acoes`;
- `amplo = None if ibov is None else abs(ibov) > ibov_amplo`;
- frase: amplo → "Movimento amplo do mercado (provável evento real)"; False → "Movimento isolado: conferir os dados da coleta"; None → "Sem a variação do Ibovespa: conferir os dados da coleta";
- texto = `f"{n} ações com retorno do dia acima de {pct0(retorno_abs)} em módulo no pregão de {dd/mm/aaaa}."`;
- ibov_texto = `f"Ibovespa {pct2(ibov)}"`; smll_texto = `f"SMLL {pct2(smll)}"` ou "SMLL sem dados";
- acoes = `[{"ticker", "texto": pct2(v)}]`;
- pontos = `[{"nivel": "warn", "texto": <texto>, "chave": "dia_atipico_amplo" se amplo, senão "dia_atipico_isolado"}]` se ativo, senão []; `<texto>` = amplo → `f"Dia atípico no pregão de {dd/mm/aaaa} ({n} ações): aviso de evento de mercado, não erro dos dados"`; senão → `f"Dia atípico no pregão de {dd/mm/aaaa} ({n} ações): conferir os dados da coleta"` (P4 aprovado);
- dados indisponíveis ou limite None → `{"disponivel": False, "ativo": False, "motivo": ..., "pontos": []}`.

**Regras de `cartao_coerencia`:**
- Par 1, quando usd e ivvb11 existem: suspeito se `usd*ivvb11 < 0 and abs(ivvb11) > ivvb11_min`.
  - Texto suspeito: `f"Dólar {pct2(usd)} × IVVB11 {pct2(ivvb11)}: sentidos opostos, com o IVVB11 acima de {pct0(ivvb11_min)} em módulo (suspeito)."`
  - Texto ok: `f"Dólar {..} × IVVB11 {..}: dentro do esperado."`
  - Sem dados: "Dólar × IVVB11: sem dados."
- Par 2, quando ibov e retornos existem: med = `statistics.median(valores)`; suspeito se `ibov*med < 0 and abs(ibov - med) > dif_min`.
  - Texto suspeito: `f"Ibovespa {pct2(ibov)} × mediana das ações {pct2(med)}: sentidos opostos, diferença de {f'{abs(ibov-med)*100:.2f}'.replace('.', ',')}% (suspeito)."`
  - Texto ok: `"...: dentro do esperado."`
  - Sem dados: "Ibovespa × mediana das ações: sem dados."
- Cartão: `{"id": "coerencia_mercado", "titulo": "Coerência do mercado", "farol", "numero", "texto": " ".join(textos), "fonte": f"{fonte} · pregão de {dd/mm/aaaa}"}`.
  - farol "warn" se houver suspeito; "ok" se pelo menos um par foi avaliado sem suspeito; "idle" se nenhum par foi avaliado (numero "sem dados").
  - numero = "1 sinal suspeito" ou "N sinais suspeitos".
- afetadas (só se houver suspeito): `{"titulo": "Séries afetadas", "itens": [{"rotulo": "Dólar (USDBRL)", "detalhe": pct2(usd)}, {"rotulo": "IVVB11", "detalhe": pct2(ivvb11)}], "total": 2}`. No par 2, os rótulos são "Ibovespa" e "Mediana das ações".

**Testes:** copiar `tests/dados/painel/pregao_2026-10-26/*` para `tmp_path/"saida"/"2026-10-27"/` e usar `ler_dia(tmp_path, "saida", "2026-10-27")`.
- `ler_dia`: data_pregao "2026-10-26", 85 retornos, usd -0.014503686980626429, ivvb11 0.0896279268486555.
- `dia_atipico(dados, {"retorno_abs": 0.30, "min_acoes": 5, "ibov_amplo": 0.05, "max": 5})`:
  - ativo True, n 16, amplo True;
  - texto "16 ações com retorno do dia acima de 30% em módulo no pregão de 26/10/2026.";
  - ibov_texto "Ibovespa -13,88%", smll_texto "SMLL -26,92%", frase "Movimento amplo do mercado (provável evento real)";
  - `[a["ticker"] for a in acoes][:5] == ["MGLU3","VAMO3","HAPV3","RAPT4","CSAN3"]`, `acoes[0]["texto"] == "-58,23%"`, `acoes[-1] == {"ticker": "GMAT3", "texto": "-30,94%"}`;
  - pontos[0]["chave"] == "dia_atipico_amplo" e pontos[0]["texto"] == "Dia atípico no pregão de 26/10/2026 (16 ações): aviso de evento de mercado, não erro dos dados".
  - Docstring do teste: caso real conferido pelo usuário (pregão real com circuit breaker; só o USDBRL −1,45% está errado na coleta).
- Com ibov_amplo 0.20: frase "Movimento isolado: conferir os dados da coleta", chave "dia_atipico_isolado". Com min_acoes 17: ativo False, pontos [].
- `cartao_coerencia(dados, {"ivvb11_min": 0.03, "dif_min": 0.02})["cartao"]`:
  - farol "warn", numero "1 sinal suspeito";
  - texto == "Dólar -1,45% × IVVB11 +8,96%: sentidos opostos, com o IVVB11 acima de 3% em módulo (suspeito). Ibovespa -13,88% × mediana das ações -17,46%: dentro do esperado."
- Fixture raiz (`ler_dia(montar_raiz(tmp_path), "saida", "2026-10-23")`):
  - texto == "Dólar +0,26% × IVVB11 -0,90%: dentro do esperado. Ibovespa -1,15% × mediana das ações +0,14%: dentro do esperado.", farol "ok", numero "0 sinais suspeitos";
  - com dif_min 0.01, o par 2 vira "Ibovespa -1,15% × mediana das ações +0,14%: sentidos opostos, diferença de 1,29% (suspeito).";
  - `dia_atipico` → ativo False.
- `ler_dia(tmp_path, "saida", None)` e pasta inexistente → disponivel False; o cartão vira idle "sem dados".

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_mercado.py`

---

### F5: `novidades.py` e `saude.afetadas_saude` (Onda 1)

**Arquivos:**
- novo `processamento/painel/novidades.py`;
- `processamento/painel/saude.py` (só **acrescentar** uma função; as atuais não mudam);
- fixtures `tests/dados/painel/novidades/anterior.md` e `atual.md`;
- novo `tests/test_painel_novidades.py`;
- acréscimos em `tests/test_painel_saude.py`.

**Fixture `atual.md`** (copiar exatamente):
```
# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-10-27 10:44 (America/Sao_Paulo)
- Banco: banco_teste

## Divergências × especificação

Nenhuma divergência encontrada.

## 3. Resumo das tabelas

### Período e entidades

| tabela | linhas | inicio | fim | entidades | coluna_entidade |
|---|---|---|---|---|---|
| v1-precos | 143686 | 2019-12-30 | 2026-10-27 | 89 | ticker |
| v1-balancos | 2694 | 2021-03-31 | 2026-09-30 | 85 | cnpj |
| v1-indices | 5128 | 2021-01-01 | 2026-10-26 | 5 | indice |

## 10. Quantidade de ações suspeita

- quantidade de ações suspeita (P/VP < 0,05; v1-acoes_emitidas provavelmente em milhares) em 1 empresas em 2026-10-26: valor de mercado, P/L, P/VP e payout = indisponivel (seção 6)

### Empresas com quantidade de ações suspeita

| tickers | cnpj | data_referencia | acoes | pvp |
|---|---|---|---|---|
| HAPV3 | 05197443000138 | 2026-06-30 | 502630884 | 0.0416 |

## 11. Retornos diários suspeitos

- 2 retornos diários suspeitos em 2 tickers (fechamento_ajustado contra o último pregão com preço, abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)

### Retornos diários suspeitos

| ticker | data | aj_anterior | aj | retorno_aj | retorno_fech |
|---|---|---|---|---|---|
| PCAR3 | 2021-03-01 | 10.2961 | 21.857 | 1.1228 | 1.1228 |
| UGPA3 | 2021-06-28 | 7.0026 | 15.3592 | 1.1933 | 1.1933 |

## 12. Lacunas nas séries de preços e índices

- nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker)
- 3 lacunas em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim)

### Lacunas em v1-indices

| serie | inicio | fim | tamanho | unidade |
|---|---|---|---|---|
| IDIV | 2025-01-02 | 2025-12-30 | 250 | pregões |
| IFIX | 2025-01-02 | 2025-12-30 | 250 | pregões |
| SMLL | 2025-01-02 | 2025-12-30 | 250 | pregões |

## 15. Histórico novo: composição, corrigir_horas e cobertura do experimento

- Cobertura do experimento (universo com a composição, motivo ok): 117505 linhas em 1699 pregões, de 2019-12-30 a 2026-10-26.
```

**Fixture `anterior.md`:** igual ao atual, com estas diferenças:
- "Gerado em: 2026-10-25 12:48 (America/Sao_Paulo)";
- divergências em tabela: `| # | Tema | Tabela | Detalhe |`, `|---|---|---|---|`, `| 1 | coluna_faltando | v1-precos | falta a coluna volume |`;
- Período e entidades: v1-precos `143516 | 2019-12-30 | 2026-10-23`, v1-balancos `2220 | 2021-03-31 | 2026-06-30`, v1-indices `1550 | 2025-01-02 | 2026-10-23` (mesmas entidades);
- seção 10: "em 19 empresas em 2026-10-23", com tabela AXIA3 (`00001180000126 | 2026-06-30 | 2943220 | 0.0014`) e HAPV3 (a mesma linha do atual);
- seção 11: "3 retornos diários suspeitos em 3 tickers (…mesmo resto…)", com a linha `| AZUL3 | 2026-02-10 | 7.42 | 341.25 | 44.9906 | 44.9906 |` antes de PCAR3 e UGPA3;
- seção 12: as três lacunas com fim `2026-10-19` e tamanho `449`;
- seção 15: "117435 linhas em 1698 pregões, de 2019-12-30 a 2026-10-23".

**`saude.py`:** nova `afetadas_saude(caminho: Path) -> dict[str, dict]`. Reusar `tabela_md` e `_data_br`. Para tabela de lacunas de preços, usar um helper por prefixo: a primeira linha que começa com "### Lacunas em v1-precos".
- "contrato": a partir de `ler_diagnostico(caminho)["divergencias"]`, itens `{"rotulo": tabela, "detalhe": tema}` para `tabela not in ("", "-")`; título "Tabelas afetadas".
- "quantidade_acoes": cada célula `tickers` dividida por ", ", com `detalhe` None; título "Empresas afetadas".
- "retornos": `{"rotulo": ticker, "detalhe": _data_br(data)}` na ordem da tabela; título "Ações afetadas".
- "lacunas": linhas de preços e depois de índices, `{"rotulo": serie, "detalhe": f"{_data_br(inicio)} a {_data_br(fim)}"}`; título "Séries afetadas".
- Só inclui a chave se houver itens. `total = len(itens)`. Arquivo ausente → `{}`.

**`novidades.py`:**
```python
VISTO, ANTERIOR = "diagnostico_visto.log", "diagnostico_anterior.log"
TABELAS_DIARIAS = {"v1-precos", "v1-noticias", "v1-indices"}
NOMES_LINHAS = {"v1-noticias": "notícias", "v1-precos": "preços", "v1-cadastro": "empresas no cadastro",
                "v1-mudancas_ticker": "mudanças de ticker", "v1-balancos": "balanços",
                "v1-acoes_emitidas": "registros de quantidade de ações", "v1-proventos": "proventos",
                "v1-indices": "pontos de índices"}
NOMES_CURTOS = {"v1-noticias": "notícias", "v1-precos": "preços", "v1-cadastro": "cadastro",
                "v1-mudancas_ticker": "mudanças de ticker", "v1-balancos": "balanços",
                "v1-acoes_emitidas": "quantidade de ações", "v1-proventos": "proventos", "v1-indices": "índices"}
FAROL_NOME = {"ok": "verde", "warn": "amarelo", "bad": "vermelho", "idle": "cinza"}
def atualizar_copias(docs_md: Path, pasta_painel: Path) -> None
def comparar(atual: Path, anterior: Path) -> dict
def novidades(docs_md: Path, pasta_painel: Path) -> dict    # atualizar_copias + comparar(docs_md, ANTERIOR)
```
- **`atualizar_copias`** (o único lugar deste módulo que grava, e só em `pasta_painel`; `OSError` é engolido):
  - lê o "- Gerado em:" de `docs_md` (ausente → return);
  - sem VISTO → copia docs → VISTO;
  - "Gerado em" do VISTO diferente do de docs → `os.replace(VISTO, ANTERIOR)` e depois copia docs → VISTO;
  - igual → nada.
- **`novidades`:** sem ANTERIOR → `{"disponivel": False, "motivo": "Ainda sem diagnóstico anterior guardado: as novidades aparecem a partir do próximo diagnóstico.", "atual_em": <dd/mm/aaaa HH:MM>, "anterior_em": None, "frase": None, "itens": []}`.
- **`comparar`**, nesta ordem (itens `{"texto", "tipo"}`):
  - "Período e entidades": para cada tabela do atual que também está no anterior:
    - delta de linhas ≠ 0 → `f"{'+' if d>0 else '-'}{milhar(abs(d))} {NOMES_LINHAS[t]}"`, tipo "crescimento" se t estiver em TABELAS_DIARIAS, senão "mudanca";
    - início mais cedo → `f"{NOMES_CURTOS[t]} desde {dd/mm/aaaa} (antes {dd/mm/aaaa})"`, "mudanca";
    - início mais tarde → `f"{curto} só a partir de {data} (antes {data})"`;
    - "NULL" é ignorado; o fim é ignorado.
  - Divergências (n atual − n anterior): < 0 → "1 divergência a menos" / "N divergências a menos"; > 0 → "1 divergência nova" / "N divergências novas".
  - Quantidade (contagens pelas regex `saude.RE_QTD_ACOES` e `RE_QTD_ACOES_ZERO`; saíram e entraram pelos tickers da tabela):
    - queda → `f"quantidade de ações corrigida em {N} empresa(s)"` + (" (saiu da lista: X)" se 1, " (saíram da lista: X, Y)" se vários, nada se nenhum);
    - aumento → `f"quantidade de ações suspeita em mais {N} empresa(s)"` + " (entrou: …)" ou " (entraram: …)".
  - Retornos (contagens por `saude.RE_RETORNOS`/`RE_RETORNOS_ZERO`; pares (ticker, data)):
    - queda → `"1 preço suspeito a menos"` / `f"{N} preços suspeitos a menos"` + " (saiu: AZUL3 em 10/02/2026)" ou " (saíram: …)";
    - aumento → `"1 preço suspeito novo"` / `f"{N} preços suspeitos novos"` + " (entrou: …)".
  - Lacunas de índices, por série (inicio, fim, tamanho, unidade):
    - mudou → agrupar as séries com o mesmo par (antes, depois): `f"lacuna de {', '.join(series)}: {tam_antes} → {tam_depois} {unidade} (agora de {ini} a {fim})"`;
    - sumiu → `f"lacuna de {series} fechada"`;
    - nova → `f"lacuna nova em {series}: {tam} {unidade} ({ini} a {fim})"`.
  - Cobertura (`saude.RE_COBERTURA`): delta ≠ 0 → `f"{'+'|'-'}{milhar} linhas no dataset do experimento ({milhar(pregões)} pregões, até {dd/mm/aaaa})"`, tipo "crescimento".
  - Cartões: `saude.cartoes_saude` dos dois arquivos, por id, farol diferente → `f"{titulo}: {FAROL_NOME[antes]} → {FAROL_NOME[depois]}"`, "mudanca".
  - Saída: `itens = [mudanças em ordem] + [crescimentos em ordem]`.
  - frase = os 4 primeiros itens do tipo "mudanca" juntados por "; " + (`f" · e mais {resto} mudanças"` se `resto = len(itens) - 4 > 0`). Se só houver crescimento, usar os 4 primeiros itens. Sem itens: `f"Nenhuma mudança desde o diagnóstico de {anterior_em}."`
  - atual_em e anterior_em = "dd/mm/aaaa HH:MM", tirados de "AAAA-MM-DD HH:MM (…)".

**Testes (`test_painel_novidades.py`):** `comparar(atual.md, anterior.md)`:
- disponivel True, atual_em "27/10/2026 10:44", anterior_em "25/10/2026 12:48";
- `[i["texto"] for i in itens] ==`
  ```
  ["+474 balanços",
   "índices desde 01/01/2021 (antes 02/01/2025)",
   "1 divergência a menos",
   "quantidade de ações corrigida em 18 empresas (saiu da lista: AXIA3)",
   "1 preço suspeito a menos (saiu: AZUL3 em 10/02/2026)",
   "lacuna de IDIV, IFIX, SMLL: 449 → 250 pregões (agora de 02/01/2025 a 30/12/2025)",
   "Contrato com a coleta: vermelho → verde",
   "+170 preços",
   "+3.578 pontos de índices",
   "+70 linhas no dataset do experimento (1.699 pregões, até 26/10/2026)"]
  ```
- frase == "+474 balanços; índices desde 01/01/2021 (antes 02/01/2025); 1 divergência a menos; quantidade de ações corrigida em 18 empresas (saiu da lista: AXIA3) · e mais 6 mudanças";
- `comparar(atual, atual)` → itens [] e frase "Nenhuma mudança desde o diagnóstico de 27/10/2026 10:44.".

**Ciclo das cópias** (tmp, copiando os .md para `docs_md`):
1. 1ª chamada de `novidades` → disponivel False e VISTO criado;
2. troca docs pelo atual (outro "Gerado em") → ANTERIOR tem o "Gerado em" do primeiro e disponivel True;
3. chamar de novo sem mudar docs → ANTERIOR não muda (conteúdo igual).

**Testes (`test_painel_saude.py`, acrescentar):**
- `afetadas_saude(FIXTURE)` (`diagnostico_completo.md`):
  - quantidade_acoes: rotulos ["AXIA3","ENEV3","ABEV3","EMBJ3"], total 4;
  - retornos: `[(i["rotulo"], i["detalhe"]) ...] == [("AZUL3","10/02/2026"),("AZUL3","09/04/2026"),("AZUL3","20/04/2026"),("PCAR3","01/03/2021"),("UGPA3","28/06/2021")]`;
  - lacunas: `[("IDIV","02/01/2025 a 19/10/2026"),("IFIX",...),("SMLL",...)]`;
  - "contrato" fora do dict.
- Raiz da fixture (2 divergências): `contrato == {"titulo": "Tabelas afetadas", "itens": [{"rotulo": "v1-precos", "detalhe": "coluna_faltando"}], "total": 1}`.
- `atual.md`: quantidade [HAPV3]; retornos [("PCAR3","01/03/2021"),("UGPA3","28/06/2021")]; lacunas IDIV, IFIX e SMLL com "02/01/2025 a 30/12/2025". São os exemplos do pedido.
- Arquivo ausente → {}.

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_novidades.py tests/test_painel_saude.py`

---

### F6: dia completo (`dia.py`, `acoes.py`, `marcos.py`) (Onda 2; depende de F1)

**Arquivos:**
- novo `processamento/painel/dia.py`;
- `processamento/painel/acoes.py`;
- `processamento/painel/marcos.py`;
- novo `tests/test_painel_dia.py`;
- `tests/test_painel_acoes.py`;
- `tests/test_painel_marcos.py`.

**`acoes.py`:**
- Em `ACOES` (`:30-35`), pôr **primeiro**: `"dia": Acao("dia", "Rodar o dia completo", True, False)`.
- Em `SIGNIFICADOS` (`:37-64`), acrescentar:
  ```python
  "dia": {0: "publicado: completo, ou só a execução quando a rotina falhou (veja o log)",
          1: "publicador recusou a publicação (motivo no log)",
          2: "configuração do painel: pasta ou Python do projeto da API não encontrados",
          3: "a rotina não gerou saída nova (sem pregão, configuração, banco ou trava): nada publicado",
          4: "carga completa falhou: nada publicado",
          5: "publicador: configuração ou banco da API",
          6: "rotina falhou, mas há uma carga completa antiga deste dia: publicador não rodado"}
  ```
- Em `montar_comando` (`:76-90`), antes do "rotina": `if acao_id == "dia": return None if d_rotina is None else [sys.executable, "-m", "processamento.painel.dia", "--data", d_rotina.isoformat()]`.
- O Executor **não muda**: o filho é `sys.executable`, o que respeita `_argv_valido` (`:108-114`).

**`dia.py`** (roda como filho do painel; nunca é importado pelos testes com execução real):
```python
"""Rodar o dia completo: rotina -> carga completa -> publicador do projeto da API, em sequência.

Roda como filho do painel (python -m processamento.painel.dia --data AAAA-MM-DD). Não acessa banco nem
rede por conta própria: só chama os três comandos fixos e lê saida/D/execucao.json.
"""
def verificar_publicador(raiz: Path, params_painel: dict) -> dict:
    """{"dir_api": str|None, "python": str|None, "motivo": str|None}. Só is_dir/is_file; nunca lê arquivo da API."""
def ambiente_publicador(base: Mapping[str, str], raiz: Path) -> dict[str, str]:
    """Copia base sem IP_BANCO, PORTA_BANCO, NOME_BANCO, USER_BANCO, SENHA_BANCO, USER_ESCRITA, SENHA_ESCRITA,
    USER_LEITURA, SENHA_LEITURA, PYTHONPATH, PYTHONHOME, VIRTUAL_ENV e qualquer chave que comece com PROC_
    (comparar em maiúsculas); define PROC_DIR_PROCESSAMENTO=str(raiz), PYTHONIOENCODING=utf-8, PYTHONUNBUFFERED=1."""
def status_rotina(raiz: Path, pasta_saida: str, d: date, desde: datetime) -> str | None:
    """registros[0].status do saida/D/execucao.json se registros[0].gerado_em >= desde - 1 s; senão None."""
def resultado_publicador(linhas: list[str]) -> str | None:  # "so_execucao" | "completa" | "recusada" | None
def executar_dia(d: date, raiz: Path, params_painel: dict, *, rodar, imprimir=print, relogio=None, ambiente=None) -> int
def main(argv: list[str] | None = None) -> int
```

**Detalhes de `dia.py`:**
- `verificar_publicador`, motivos:
  - "Projeto da API não configurado: falta painel.dir_api no parametros.yaml.";
  - `f"Pasta do projeto da API não encontrada ({pasta})."`;
  - "Python do projeto da API não encontrado em .venv (crie o ambiente virtual lá)." (procurar `.venv/Scripts/python.exe`, senão `.venv/bin/python`);
  - "Publicador não encontrado na pasta do projeto da API." (`publicador/__main__.py`).
  - `dir_api` relativo é resolvido em relação à raiz.
- `resultado_publicador`: regex `^\d{2}/\d{2}/\d{4}: só a execução foi gravada` → "so_execucao"; `^\d{2}/\d{2}/\d{4} publicado \(modo` → "completa"; `^Publicação de .* recusada` ou `^Não publicado:` → "recusada".
- `rodar(argv, cwd, env) -> tuple[int, list[str]]`. O real usa `subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)`, imprime cada linha com `print(linha, flush=True)` e guarda as últimas 500. **Sem `shell=True`.**
- **Marcadores impressos** (exatos):
  - `# dia: etapa=<rotina|carga|publicador> inicio=HH:MM:SS`
  - `# dia: etapa=<e> fim codigo=<N> detalhe=<texto>`
  - `# dia: etapa=<e> pulada motivo=<texto>`
  - no fim, `# dia: resultado=<chave> <frase>`
- **Fluxo:**
  1. `verificar_publicador`: com motivo → imprime "# dia: resultado=configuracao <motivo>" e retorna 2, sem rodar nada.
  2. **Rotina:** `[sys.executable, "-m", "processamento.rotina", "--data", D, "--sem-esperar"]`, cwd raiz, env `ambiente`.
     - Depois, `status_rotina(...)`. O detalhe do fim é `f"status {s}"`, ou "dia sem pregão" se alguma linha casar `relatorios.RE_SEM_PREGAO`, ou `f"código {c}, sem saída nova"`.
     - status None ou "em_andamento" → carga e publicador "pulada" com motivo "a rotina não gerou saída nova"; resultado "sem_saida"; retorna 3.
  3. **status ok ou parcial → carga:** `[sys.executable, "-m", "processamento.saida", "--data", D, "--completo"]`, cwd raiz. O detalhe é `f"status {X}"` pela linha `relatorios.RE_SAIDA` (`relatorios.py:17`), ou `f"código {c}"`. Código ≠ 0 → publicador "pulada" com motivo "a carga completa falhou"; retorna 4.
  4. **status falhou:** carga "pulada" com motivo "a rotina falhou". Se `(raiz/"saida_completa"/D).is_dir()` → publicador "pulada" com motivo `f"saida_completa/{D}/ já existe de uma carga anterior: o publicador publicaria essa carga junto"`; retorna 6.
  5. **Publicador:** `[python_api, "-m", "publicador", "--data", D]`, cwd dir_api, env `ambiente_publicador(ambiente, raiz)`. Detalhe: so_execucao → "só a execução"; completa → "publicado (completo)"; recusada → "recusado"; senão `f"código {c}"`.
     - Código 0 → retorna 0. 1 → retorna 1. Outro → retorna 5.
- `main`: argparse `--data AAAA-MM-DD`; raiz = `leitores.RAIZ_PADRAO`; `params = leitores.ler_parametros_painel(raiz)`; `rodar` real; `sys.exit(main())` sob `if __name__ == "__main__":`.

**`marcos.py`:**
- Regex: `RE_DIA_INICIO = r"^# dia: etapa=(\w+) inicio=(\S+)$"`, `RE_DIA_FIM = r"^# dia: etapa=(\w+) fim codigo=(-?\d+) detalhe=(.*)$"`, `RE_DIA_PULADA = r"^# dia: etapa=(\w+) pulada motivo=(.*)$"`.
- Nova `marcos_dia(linhas, *, rodando, codigo, significado) -> list[dict]` com 4 etapas:
  - ("rotina", "Rotina do dia (só leitura do banco da coleta)");
  - ("carga", "Carga completa em saida_completa/");
  - ("publicador", "Publicador (grava no banco da API)");
  - ("fim", "Encerrado").
- Estado de cada etapa: começou e não terminou → "agora" se rodando, senão "erro"; fim com código 0 → "concluida" com o detalhe; código ≠ 0 → "erro" com o detalhe; pulada → "pulada" com o motivo.
- Terminado (`not rodando and codigo is not None`): as etapas que nunca começaram viram "pulada". "fim" vira "concluida" se codigo == 0, senão "erro", com detalhe = significado.
- Rodando sem nada iniciado: rotina "agora".
- Em `marcos_acao` (`:148-156`), primeira linha: `if acao_id == "dia": return marcos_dia(linhas, rodando=rodando, codigo=codigo, significado=significado)`.

**Testes (`test_painel_dia.py`)** usam `raiz = montar_raiz(tmp_path)` e uma pasta de API falsa `api = tmp_path/"api"` com:
- `.venv/Scripts/python.exe` (arquivo vazio);
- `publicador/__main__.py` (vazio);
- `.env` com `PROC_API_CHAVES=chave-secreta-xyz`.

`params = {"dir_api": str(api)}`. O `rodar` falso grava as chamadas (argv, cwd, env). Na rotina, ele escreve `saida/2026-10-26/execucao.json` com `{"registros": [{"status": S, "gerado_em": "2026-10-26T10:00:00-03:00"}]}`, e o relogio fixo devolve 2026-10-26 10:00 SP. No publicador, devolve as linhas da resposta. D = `date(2026, 10, 26)`.

| Caso | Chamadas (etapas) | Retorno |
|---|---|---|
| S=ok, publicador imprime "26/10/2026 publicado (modo normal, execução: ok) em 1,2 s" | rotina, carga, publicador | 0 |
| S=parcial | rotina, carga, publicador | 0 |
| S=falhou, publicador imprime "26/10/2026: só a execução foi gravada (sem carga completa)" | rotina, publicador; saída contém "# dia: etapa=carga pulada motivo=a rotina falhou" | 0 |
| S=falhou e existe `saida_completa/2026-10-26/` | rotina | 6 |
| rotina não escreve nada | rotina | 3 |
| rotina escreve com gerado_em de 2026-10-25 | rotina | 3 |
| S=ok, carga devolve 4 | rotina, carga | 4 |
| publicador devolve 1 / 2 | 3 etapas | 1 / 5 |
| params `{}` | nenhuma | 2 |

Checar também:
- argv do publicador == `[str(api/".venv"/"Scripts"/"python.exe"), "-m", "publicador", "--data", "2026-10-26"]` e cwd == api;
- em nenhum argv aparecem "--forcar" ou "--criar-tabelas";
- `env` do publicador, com `ambiente={"PATH": "p", "SENHA_BANCO": "x", "USER_BANCO": "u", "PROC_API_CHAVES": "k", "PYTHONPATH": "z"}`: não tem SENHA_BANCO, USER_BANCO, PROC_API_CHAVES nem PYTHONPATH; tem PATH e `PROC_DIR_PROCESSAMENTO == str(raiz)`;
- "chave-secreta-xyz" não aparece em nenhum env nem na saída;
- monitorando `builtins.open` e `io.open` com monkeypatch (falhar se o caminho terminar em ".env") durante `verificar_publicador` e `executar_dia`, nada é aberto;
- **integração com os marcos:** pegar as linhas impressas no caso "falhou só execução" e passar para `marcos.marcos_acao("dia", linhas, rodando=False, codigo=0, significado=SIGNIFICADOS["dia"][0])` → estados ["erro", "pulada", "concluida", "concluida"]. O detalhe da rotina é "status falhou" (o falso devolve código 4 na rotina) e o do publicador é "só a execução".

**Testes (`test_painel_acoes.py`):**
- `:93` e `:214` passam a esperar `{"dia", "rotina", "carga", "diagnostico", "testes"}`;
- novo: `montar_comando("dia", d_rotina=date(2026,10,26), d_carga=None) == [sys.executable, "-m", "processamento.painel.dia", "--data", "2026-10-26"]`; com d_rotina None → None;
- `significado("dia", 6, False)` == o texto do código 6;
- `ACOES["dia"].pode_parar is False` e `list(ACOES)[0] == "dia"`.

**Testes (`test_painel_marcos.py`):** rodando com só "# dia: etapa=rotina inicio=10:00:00" → estados ["agora", "espera", "espera", "espera"].

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_dia.py tests/test_painel_acoes.py tests/test_painel_marcos.py`

---

### F7: `visao.py` (blocos API, Banco, etapas da coleta e resumo) (Onda 2; depende de F2)

**Arquivos:** `processamento/painel/visao.py`, `tests/test_painel_visao.py`.

**Funções novas (sem mudar `fluxo` nem `_bloco_coleta`, cujo teste exige igualdade exata em `test_painel_visao.py:92`):**
```python
ROTULOS_ETAPA = {"precos": "preços", "macro": "macro", "noticias": "notícias", "ipe": "IPE", "enriquecimento": "enriquecimento",
                 "juiza": "juíza", "cadastro": "cadastro", "entrega": "entrega", "analise": "análise"}
TEXTO_ETAPA = {"concluida": "concluída", "falhou": "falhou", "pulada": "pulada", "em_andamento": "em andamento"}
def etapas_coleta(item: object) -> dict
def bloco_api(situacao: object, limite_s: object) -> dict
def bloco_banco(situacao: object, esperado: object, pregao: object) -> dict
```

**`etapas_coleta`:**
- Coleta sem etapas dict → `{"disponivel": False, "motivo": coleta.get("nota") or coleta.get("motivo_texto") or "Coleta não consultada.", ...}` com etapas [], resumo None.
- Com etapas: para cada id na ordem do dict, status = v ou v["status"]; texto = TEXTO_ETAPA.get(status, status) ou "pendente" se None; destaque = status != "concluida".
- `nao_concluidas = [f"{rotulo} ({texto})" ...]`.
- resumo = `f"{k} de {n} etapas concluídas"` + (`" · não concluíram: " + ", ".join(nao)` se houver).
- consulta_hhmm e daily vêm do item.

**`bloco_api`** (situação vinda de `api.MonitorApi.situacao`):
- Não configurada → `{"configurada": False, "estado": "idle", "titulo": "Não configurada", "linhas": [erro_config], "pontos": [], ...}`.
- consulta None → idle, titulo "sem dados".
- `respondeu False` → estado "warn", titulo "Sem resposta", linhas[0] `f"Sem resposta em até {f'{timeout_s:g}'.replace('.', ',')} s ({erro})"`, pontos `[{"nivel": "warn", "texto": "API sem resposta", "chave": "api_sem_resposta"}]`.
- http 503 ou banco ≠ "ok" → "bad", "Banco da API fora", linhas[0] `f"Status {status or 'sem dados'} · banco {banco or 'sem dados'}"`, pontos `[{"nivel": "bad", "texto": "Banco da API fora", "chave": "api_banco_fora"}]`.
- http 200, status ok e banco ok → "ok", "No ar", linhas[0] "Status ok · banco ok".
- Outro http → "warn", `f"Resposta inesperada (HTTP {http})"`, chave api_sem_resposta.
- Depois:
  - se `ultima_publicacao`, acrescenta `f"Última publicação completa: {dd/mm/aaaa}"`;
  - acrescenta `tempo["texto"]` (`api.resumo_tempos`; importar `from processamento.painel.api import resumo_tempos`);
  - acrescenta `f"Consultada às {HH:MM:SS}"`.
- Se estado == "ok" e `tempo["acima_limite"]` → estado "warn" e pontos `[{"nivel": "warn", "texto": f"API lenta (média {media})", "chave": "api_lenta"}]`. **No máximo um ponto.**

**`bloco_banco`:**
- API não configurada, sem consulta ou sem resposta → idle "sem dados", linhas ["Depende da resposta da API."].
- API "Banco da API fora" → "bad", "Fora", linhas ["A API respondeu que o banco dela não responde."], pontos [].
- ultima None → "warn" "Nada publicado ainda", pontos `[{"nivel": "warn", "texto": "Banco da API: nada publicado ainda", "chave": "banco_atrasado"}]`.
- esperado None → idle "sem rotina para comparar", linhas ["Última publicação completa: dd/mm/aaaa"].
- ultima ≥ esperado → "ok" "Em dia". ultima < esperado → "warn" "Publicação atrasada", pontos `[{"nivel": "warn", "texto": f"Banco da API: última publicação completa {u}, esperada {e}", "chave": "banco_atrasado"}]`.
- linhas = `[f"Última publicação completa: {u}", f"Esperada: {e}" + (f" (pregão de {p})" if pregao else "")]`.

**`pontos_de_atencao` e `resumo`** (`visao.py:314-389`):
- Ganham os kwargs `*, api=None, banco=None, dia_atipico=None`, repassados por `resumo`.
- Logo depois do bloco do fluxo (antes da folga, `:338`): para (banco, "fluxo-banco") e depois (api, "fluxo-api"), para cada p em `_dic(bloco).get("pontos") or []`: `pontos.append(_ponto(p["nivel"], p["texto"], alvo, p["chave"]))`.
- Depois da folga: o mesmo para (dia_atipico, "dia-atipico").
- **Saúde** (`:342-354`): passar a percorrer `saude_visao.get("cartoes") or []` sempre. O ponto "Saúde dos dados: sem diagnóstico" entra **antes** dos cartões quando `disponivel is not True`. Os testes `:365-375` e `:386-389` não mudam, porque nesses casos não há cartões.

**Testes:**
- **etapas_coleta**, com `item = {"coleta": {"etapas": {"precos": "concluida", "macro": "concluida", "noticias": "concluida", "ipe": "concluida", "enriquecimento": "concluida", "juiza": "concluida", "cadastro": "concluida", "entrega": "concluida", "analise": "falhou"}, "consulta_hhmm": "10:49", "daily": "2026-10-27-daily-080001"}}` (os valores reais de `saida/2026-10-27/execucao.json`):
  - resumo "8 de 9 etapas concluídas · não concluíram: análise (falhou)";
  - nao_concluidas ["análise (falhou)"];
  - `etapas[-1] == {"id": "analise", "rotulo": "análise", "status": "falhou", "texto": "falhou", "destaque": True}`;
  - `etapas[0]["destaque"] is False`.
  - Com {"ipe": None, "juiza": "pulada"} → textos "pendente" e "pulada".
  - Com `{"coleta": {"nota": "Nenhum daily de hoje encontrado. Consulta única (--sem-esperar)."}}` → disponivel False com essa nota.
- **bloco_api:**
  - ok com ms 900 e medições [800, 1000, None, 900], limite 2.0, consultado_em "2026-10-27T10:58:03-03:00", ultima_publicacao "2026-10-27" → linhas == ["Status ok · banco ok", "Última publicação completa: 27/10/2026", "Última: 0,90 s · média 0,90 s (3 de 4 com resposta)", "Consultada às 10:58:03"], estado "ok", pontos [];
  - limite 0.5 → estado "warn", pontos [{"nivel":"warn","texto":"API lenta (média 0,90 s)","chave":"api_lenta"}];
  - sem resposta (timeout 5, erro "TimeoutError", medições [{"ms": None}]) → linhas[0] "Sem resposta em até 5 s (TimeoutError)";
  - 503 → estado "bad", titulo "Banco da API fora";
  - não configurada → idle.
- **bloco_banco:**
  - ("2026-10-27", esperado "2026-10-27", pregão "2026-10-26") → "Em dia", linhas ["Última publicação completa: 27/10/2026", "Esperada: 27/10/2026 (pregão de 26/10/2026)"];
  - ("2026-10-23", "2026-10-27") → "Publicação atrasada" com o ponto descrito acima;
  - sem resposta → idle.
- **resumo:**
  - `resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, SAUDE_OK, TESTES_OK, api={"pontos": [{"nivel": "warn", "texto": "API sem resposta", "chave": "api_sem_resposta"}]})["pontos"] == [{"nivel": "warn", "texto": "API sem resposta", "alvo": "fluxo-api", "o_que_fazer": O_QUE_FAZER["api_sem_resposta"]}]`;
  - com banco, api e dia_atipico juntos, a ordem é banco, api, dia atípico;
  - um cartão "coerencia_mercado" warn em saude dá alvo "saude-c-coerencia_mercado" e `o_que_fazer == O_QUE_FAZER["saude_coerencia_mercado"]`.
- Todos os testes existentes continuam iguais.

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_visao.py`

---

### F8: integração no `servidor.py` (Onda 3)

**Arquivos:** `processamento/painel/servidor.py`, `tests/test_painel_servidor.py`.

- **Import** (`:21`): acrescentar `api, dia, mercado, novidades`.
- **`criar_servidor`** (`:346-367`): novo kwarg `consultar_api: Callable | None = None`. Criar `srv.monitor = api.MonitorApi(raiz / pasta_logs / "painel", consultar=consultar_api or api.consultar_saude)`. O `pasta_logs` sai de `leitores.ler_parametros(raiz)["pasta_logs"]`, como em `:356`.
- **`montar_painel`** (`:139-192`): novo kwarg `monitor=None`. Passar `srv.monitor` nas chamadas de `:267` e `:327`. Depois de `completa_item` (`:157`), acrescentar:
  ```python
  painel_p = _seguro(leitores.ler_parametros_painel, raiz)
  painel_p = painel_p if "disponivel" not in painel_p else {}
  valida = leitores.ultima_execucao_valida(itens_diarias)
  d_valida = valida.get("data_referencia") if valida else None
  dados_dia = _seguro(mercado.ler_dia, raiz, params["pasta_saida"], d_valida)
  api_sit = _seguro(monitor.situacao, painel_p, agora) if monitor is not None else {"configurada": False, "erro_config": "Monitor da API ausente."}
  api_v = _seguro(visao.bloco_api, api_sit, painel_p.get("api_tempo_limite_s"))
  banco_v = _seguro(visao.bloco_banco, api_sit, d_valida, dados_dia.get("data_pregao"))
  atipico_v = _seguro(mercado.dia_atipico, dados_dia, {"retorno_abs": painel_p.get("retorno_dia_abs"), "min_acoes": painel_p.get("dia_atipico_min_acoes"), "ibov_amplo": painel_p.get("dia_atipico_ibov_amplo"), "max": painel_p.get("afetadas_max")})
  coer = _seguro(mercado.cartao_coerencia, dados_dia, {"ivvb11_min": painel_p.get("coerencia_ivvb11_min_abs"), "dif_min": painel_p.get("coerencia_ibov_mediana_dif")})
  docs_md = raiz / "docs" / "diagnostico_banco.md"
  novid = _seguro(novidades.novidades, docs_md, pasta_painel)
  afet = _seguro(saude.afetadas_saude, docs_md)
  pub = _seguro(dia.verificar_publicador, raiz, painel_p)
  ```
  (`pasta_painel` já existe em `:158`; mover a linha para cima se precisar.)
- **Saúde:** `saude_v = _juntar_saude(_seguro(saude.cartoes_saude, docs_md), coer, afet, painel_p.get("afetadas_max"))`.
  - Função nova `_juntar_saude`: copia o dict, acrescenta `coer["cartao"]` ao fim de `cartoes` (também quando `disponivel` é False), `afetadas = afet` (ou {} se for erro) e `afetadas["coerencia_mercado"] = coer["afetadas"]` se houver, e `afetadas_max`.
- **Resumo:** `_seguro(visao.resumo, hoje, trava, fluxo_v, linha_v, saude_v, testes)` não aceita kwargs. Usar `functools.partial(visao.resumo, api=api_v, banco=banco_v, dia_atipico=atipico_v)` ou uma lambda dentro de `_seguro`.
- **`visao`** (`:180-191`) ganha `"api": api_v, "banco": banco_v, "coleta_etapas": _seguro(visao.etapas_coleta, agora_item), "novidades": novid, "dia_atipico": atipico_v`.
- **`estado_botoes`** (`:80-122`): novo kwarg `motivo_publicador: str | None = None`. Para `acao_id == "dia"`: data = `rotina_data.get("data")`; motivos na ordem: rodando, trava, produção (`MOTIVO_PRODUCAO`), calendário, `motivo_publicador`. Aviso:
  ```python
  (f"Data usada: {data}. Em sequência: rotina (--sem-esperar) → carga completa em saida_completa/{data}/ → "
   f"publicador do projeto da API (python -m publicador --data {data}), que grava no banco da API. "
   "Se a rotina falhar, a carga não roda e o publicador grava só a execução. Não pode ser parado no meio.")
  ```
  Chamar com `motivo_publicador=pub.get("motivo") if isinstance(pub, dict) else "erro ao conferir o projeto da API"`.
- **`_iniciar`** (`:334-335`): continua passando `d_rotina=_data_do_botao(botoes, "rotina")`; o "dia" usa a mesma data.

**Testes que mudam:**
- `:199-200`: as chaves de `visao` ganham `{"api", "banco", "coleta_etapas", "novidades", "dia_atipico"}`.
- `:221`: `["bad", "idle", "idle", "idle", "idle", "idle", "ok"]` (o 7º é a coerência do pregão de 22/10 da fixture).
- `:241-250`: o dict de tempos ganha `"dia": {"segundos": None, "curto": None, "texto": "Ainda sem medição: pode levar alguns minutos.", "origem": None}`.
- `:235-237` e `:431` **não mudam**: a fixture não tem `api_url` nem dia atípico, e a coerência dá ok.

**Testes novos:**
1. Com as fixtures:
   - `visao.api.estado == "idle"` e `titulo == "Não configurada"`; `visao.banco.estado == "idle"`;
   - `visao.dia_atipico.ativo is False`;
   - `visao.coleta_etapas.resumo == "9 de 9 etapas concluídas"`;
   - `visao.novidades.disponivel is False` e `(raiz/"logs"/"painel"/"diagnostico_visto.log").is_file()`;
   - `botoes["dia"]["habilitado"] is False` e `motivo == "Projeto da API não configurado: falta painel.dir_api no parametros.yaml."`;
   - `list(botoes)[0] == "dia"`;
   - `visao.saude.afetadas["contrato"]["total"] == 1`.
2. API configurada com HTTP falso:
   - em tmp, trocar no yaml `"painel:\n"` por `'painel:\n  api_url: "https://api.exemplo.invalid"\n  dir_api: "<tmp_api>"\n'`, com `tmp_api` contendo `.venv/Scripts/python.exe`, `publicador/__main__.py` e `.env` com `PROC_API_CHAVES=chave-secreta-xyz`;
   - `criar_servidor(raiz, 0, montar_comando=_montar_falso([]), relogio=RELOGIO, consultar_api=falso)`, com o falso contando chamadas e devolvendo `{"respondeu": True, "http": 200, "ms": 840, "status": "ok", "banco": "ok", "ultima_publicacao": "2026-10-23", "erro": None}`;
   - dois GET `/api/painel` → falso chamado 1 vez; `visao.api.titulo == "No ar"`; `visao.banco.titulo == "Em dia"`; `api_tempos.log` com 1 linha; `botoes["dia"]["habilitado"] is True`;
   - `b"chave-secreta-xyz" not in corpo`.
3. Estático: nenhum `processamento/painel/*.py` contém "X-API-Key" nem "Authorization".
4. POST `{"acao": "dia"}` nesse servidor → 202 e `s.chamadas[0] == ("dia", date(2026,10,23), date(2026,10,23))`. É o comando falso; nada roda de verdade.

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_servidor.py`

---

### F9: `pagina.html` (Onda 3)

**Arquivos:** `processamento/painel/pagina.html`, `tests/test_painel_pagina.py`.

**HTML:**
1. Em `#sec-fluxo` (`:297-323`): o `<div class="faixa faixa-fluxo">` fica só com `#agora`. Depois dele, um `<div class="faixa faixa-manha" id="faixa-manha">` com o `#linha-tempo` (mover sem mudar o conteúdo) e um cartão novo:
   ```html
   <section class="card" id="dia-atipico" aria-labelledby="h-atip" hidden><div class="cardhead"><div class="tit-linha" id="atip-tit"><h3 class="card-tit" id="h-atip">Dia atípico</h3></div><span class="pill warn" id="pill-atip"></span></div><p id="atip-texto"></p><p class="note" id="atip-indices"></p><p class="why" id="atip-frase"></p><div id="atip-acoes"></div><p class="note" id="atip-fonte"></p><p class="fazer" data-fazer="dia-atipico" hidden></p></section>
   ```
2. Em `#saude` (`:327-333`), logo depois do `<p class="why">`:
   ```html
   <div class="novidades" id="novidades"><div class="tit-linha" id="novid-tit"><h3 class="card-tit">Novidades da coleta</h3></div><p id="novid-frase"></p><p class="note" id="novid-quando"></p><details id="novid-det"><summary>ver tudo</summary><ul id="novid-lista"></ul></details></div>
   ```

**CSS:**
- `.flow` (`:81`): `grid-template-columns:1fr auto 1fr auto 1fr auto 1fr auto 1fr`.
- Antes da regra de 640 (`:91`): `@container (max-width:1100px){.flow{grid-template-columns:repeat(2,minmax(0,1fr))}.flow .arrow{display:none}}`. **Manter** a regra de 640 como está (é exigida em `test_painel_pagina.py:253`).
- `@media (min-width:1280px)` (`:41-46`): `.faixa-fluxo{grid-template-columns:minmax(0,1fr)}`; acrescentar `.faixa-manha{grid-template-columns:minmax(0,7fr) minmax(0,5fr)} .faixa-manha.uma{grid-template-columns:minmax(0,1fr)}`.
- `.health` a partir de 1700 px (`:149`): `repeat(7,minmax(0,1fr))`.
- `.etapa.destaque{font-weight:600}` e `.afetadas{font-size:.8rem}`.
- Impressão (`:251`): acrescentar `.faixa-manha`.

**JS:**
- `DESCRICAO` (`:471-476`): acrescentar `["dia", "Roda a rotina, a carga completa e o publicador da API, em sequência, e leva os dados do dia até o banco da API."]`.
- `const CLASSE_ETAPA = new Map([["concluida","ok"],["falhou","bad"],["pulada","warn"],["em_andamento","idle"]]);`
- `origemData` (`:1006-1011`): tratar "dia" igual a "rotina".
- **`renderFluxo`** (`:906-953`):
  - na coleta, trocar a linha `etapas` por `(v.coleta_etapas && v.coleta_etapas.resumo) || etapas` e acrescentar `etapasColetaNode(v.coleta_etapas)`. Cada etapa vira um span com a pílula `"pill " + (CLASSE_ETAPA.get(status) || "idle")` e o rótulo; quando `destaque`, classe "destaque" e o texto entre parênteses. Depois, a linha `metaComAjuda("Situação na consulta das " + ce.consulta_hhmm, botaoAjuda("etapas_coleta"))`. Se `disponivel` não for true, mostrar `ce.motivo`.
  - criar `const banco = estagio(v.banco, "3 · Banco da API", listaSegura((v.banco||{}).linhas), "fluxo-banco", botaoAjuda("banco_api"));`
  - criar `apiNo = estagio(v.api, "4 · API", linhasApi, "fluxo-api", botaoAjuda("api"))`, com `linhasApi` = as `linhas` da API, mas a linha igual a `api.tempo.texto` vai como `metaComAjuda(texto, botaoAjuda("tempo_api"))`.
  - renomear "3 · Interface" para "5 · Interface";
  - `fluxo.replaceChildren(coleta, seta(), processamento, seta(), banco, seta(), apiNo, seta(), interfaceNo)`.
- **`renderDiaAtipico(d)`:**
  - `card.hidden = da.ativo !== true`; `$("faixa-manha").classList.toggle("uma", card.hidden)`;
  - pôr o "?" uma vez: `if (!$("atip-tit").querySelector(".ajuda-btn")) $("atip-tit").appendChild(botaoAjuda("dia_atipico"))`;
  - preencher texto, `ibov_texto + " · " + smll_texto`, frase, fonte;
  - lista via `listaComMais(acoes.map(a => a.ticker + " " + a.texto), da.max)`;
  - pílula `da.amplo ? "amplo" : "isolado"`.
- **`listaComMais(textos, max)`:** devolve um `<div class="afetadas">` com o texto dos primeiros `max` juntados por ", ", mais " e mais N" se houver resto. Quando houver resto, acrescenta `<details><summary>ver todas (total)</summary><ul>…</ul></details>`. Se `max` não for número, mostra todos.
- **`renderNovidades(d)`:**
  - "?" uma vez em `#novid-tit` com `botaoAjuda("novidades")`;
  - `disponivel !== true` → `novid-frase` = motivo e `novid-det` escondido;
  - senão: frase; quando = "Diagnóstico de " + atual_em + " comparado com o de " + anterior_em; lista de itens.
- **`cartaoSaude(c, sv)`** (`:1258-1274`): depois do texto, `const af = sv && sv.afetadas ? sv.afetadas[id] : null;`. Se houver itens: `p` com `criar("strong", af.titulo + ": ")` e `listaComMais(af.itens.map(i => i.rotulo + (i.detalhe ? " (" + i.detalhe + ")" : "")), sv.afetadas_max)`.
- **`renderSaudeCartoes`** (`:1276-1286`): passar `sv` para `cartaoSaude`. Quando `disponivel !== true`, `cont.replaceChildren(motivo(...), ...listaSegura(sv.cartoes).map((c) => cartaoSaude(c, sv)))`.
- **`renderizarPainel`** (`:1514-1535`): chamar `renderDiaAtipico(d)` depois de `renderLinhaTempo(d)` e `renderNovidades(d)` depois de `renderSaudeCartoes(d)`, sempre antes de `renderFazerCartoes()`.

**Testes (`test_painel_pagina.py`):**
- `:280`: `dinamicos = {"saude_" + c[0] for c in _CARTOES} | {"saude_coerencia_mercado"} | {"acao_" + a for a in ACOES}`. As contagens 14 (`:282,290`) **não mudam**.
- `:221`: acrescentar o trecho "Roda a rotina, a carga completa e o publicador da API".
- `:237`: a ordem passa a ser `['id="sec-fluxo"', 'id="agora"', 'id="linha-tempo"', 'id="dia-atipico"', 'id="sec-saude"', 'id="saude"', 'id="novidades"', 'id="sec-experimento"', ...resto igual]`.
- Teste novo: estão presentes '"fluxo-banco"', '"fluxo-api"', 'botaoAjuda("api")', 'botaoAjuda("banco_api")', 'botaoAjuda("tempo_api")', 'botaoAjuda("etapas_coleta")', 'botaoAjuda("dia_atipico")', 'botaoAjuda("novidades")', "coleta_etapas", "afetadas", "e mais ", "ver todas", 'id="faixa-manha"', "repeat(7,minmax(0,1fr))".

**Verificação:** `.venv\Scripts\python -m pytest -q tests/test_painel_pagina.py`

---

### F10: verificação final (executor, Onda 4)

1. `.venv\Scripts\python -m pytest -q tests/test_painel_*.py`, sem falhas.
2. `.venv\Scripts\python -m pytest -q` (suíte inteira), para confirmar que o bloco `painel:` no `parametros.yaml` não quebra os carregadores da rotina, do experimento e da fase 1.
3. **Não** subir o painel de verdade: ele chamaria a API real. Quem faz o primeiro teste manual é o usuário.

**Escalonamento:** se uma fase falhar na verificação duas vezes com o Haiku, redespachar com sonnet.