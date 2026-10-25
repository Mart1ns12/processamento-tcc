# Plano: painel em tela inteira, logo, ajuda "?", faixa de resumo e "O que fazer"

> Aprovado em 25/10/2026 com as **CORREÇÕES L1–L6** abaixo. Elas valem sobre o texto das seções A e B.

## CORREÇÕES APROVADAS (L1–L6): valem sobre o resto do plano

### L1. Escolhas
- Texto da logo: **"Painel do Processamento"** (não "Interface do Processamento").
- Extras **E1, E2 e E3 aprovados**: entram nas fases indicadas em L5.
- **Sem estimativa fixa de tempo.** Vale só a regra de A.6: duração medida ou "ainda sem medição".

### L2. Fatos conferidos no código (25/10/2026), que os textos seguem
- **Retornos suspeitos:**
  - saem da série `SETOR_SEM` e da rentabilidade do setor (`fatos/precos.py:462-471`, `series.py:171-264`);
  - saem das medianas de P/L, P/VP e yield do setor: a empresa inteira, por 21 pregões (`saida/pacotes_fatos.py:70-79`);
  - saem do beta e da volatilidade do painel (`precos.py:480-484`).
  - **No experimento**, a volatilidade, o beta e as exposições ao dólar e ao petróleo **já excluem** esses dias (`experimento/variaveis.py:111-125`). `ret_1d/5d/20d`, `ret_vs_setor` e o alvo **ainda usam** o preço como veio (`variaveis.py:107-110`, `alvo.py:23-71`).
  - Isso diverge da ESPECIFICACAO seção 10 e do CLAUDE.md item 17 ("o experimento ainda não trata"). Fica avisado ao usuário; o painel não muda a especificação.
- **Quantidade de ações suspeita** (`fatos/fundamentos.py:256-261`):
  - ficam indisponíveis o P/L e o P/VP (do dia e os pontos diários do `series_diarias`) e o payout (12 meses, `payout_por_ano` e `payout_12m` dos trimestrais);
  - **o payout depende da quantidade** (`fatos/proventos.py:145`, valor × ações da classe);
  - a empresa sai das medianas desses indicadores;
  - **não mudam:** dividend yield, ROE, margens, EBITDA e endividamento. O valor de mercado só é usado por dentro, não é campo de saída.
- **Registro do top 5 ao rodar de novo:**
  - com `treino.teste_final.fim` vazio (hoje), o `.top.json` do dia é **regravado** a cada rodada (`saida/pacotes_experimento.py:271-297`) com `gerado_em` novo, e a regra de validade é recalculada (`:131-149`);
  - depois de `saida.limite_valido_historico`, o registro novo sai com `valido_para_historico = false` e o aviso "Gerado depois das 10h…";
  - hoje, antes da produção, ele já sai `false` (motivo `antes_producao`);
  - em produção (`fim` preenchido), o registro é de uso único: modo "x", nunca sobrescrito.
  - **Conclusão: o código marca a geração fora do horário.** A condição de parada do usuário não se aplica.
- **Veredito do modelo 3** (`experimento/treino.py:557-579`): compara o acerto do top 5 do modelo 3 com a faixa do acaso (acima de p97,5), com a regra da volatilidade e com a regressão logística. **O modelo 1 não entra no veredito**; ele aparece só nas comparações pareadas (`treino.py:517-537`). A regra simples é "ações mais calmas primeiro": score = 1 − rank da `volatilidade_20d` (`experimento/modelos.py:95-101`).
- **Modelo sombra:** `modelos/xgb-m1-AAAA-MM.json` = modelo 1, sem notícias (meta `"modelo": "1"`). Todo dia são gravados, só no registro interno, o top 5 do modelo 1 e o da regra da volatilidade (`pacotes_experimento.py:242-253`); não vão para o pacote.

### L3. Textos de AJUDA que SUBSTITUEM os da tabela A.3 (mesmos ids e títulos, salvo indicação)
Atenção à regra do teste: nenhum dígito escrito à mão (só `{campos}`, "top 5" e "95%").
- **saude_quantidade_acoes**: 'O que é: para saber quanto a empresa vale na bolsa (valor de mercado), o processamento multiplica o preço pela quantidade de ações. Por que está amarelo: em algumas empresas a coleta gravou essa quantidade em milhares, ou seja, mil vezes menor. O processamento percebe quando o preço dividido pelo patrimônio (P/VP) fica abaixo de {pvp_min}. Nessas empresas saem como "indisponível", sem chute: o P/L e o P/VP (o valor do dia e os pontos diários dos gráficos) e o payout (o dos últimos doze meses, o de cada ano e o dos balanços trimestrais), porque o payout soma os dividendos pagos multiplicando pelo número de ações. Essas empresas também saem das medianas do setor desses indicadores. O dividend yield, o ROE, as margens, o EBITDA e o endividamento não mudam, porque não dependem da quantidade de ações. Quando a coleta corrigir: esses indicadores voltam sozinhos no próximo cálculo.'
- **saude_retornos**: 'O que é: procura preços que mudaram de um dia para o outro de um jeito muito estranho (variação abaixo de {retorno_min} ou acima de {retorno_max} num só dia). Por que está amarelo: alguns desses casos são erro da coleta; outros são eventos reais, como a cisão de uma empresa. As ações e a quantidade de casos estão no cartão. O processamento não mexe no preço da própria ação: só tira esses dias da série e da rentabilidade do setor, das medianas do setor (P/L, P/VP e dividend yield), do beta e da volatilidade, para um caso desses não contaminar as outras ações. No experimento, a volatilidade, o beta e as exposições ao dólar e ao petróleo também já deixam esses dias de fora, mas os retornos da ação, a comparação com o setor e o alvo do modelo ainda usam o preço como veio: essa decisão fica pendente para antes do treino definitivo. Quando a coleta corrigir os casos que são erro: esses dias voltam a entrar sozinhos.'
- **saude_horario_noticias**: 'O que é: mostra quantas notícias têm a hora exata em que foram publicadas. Por que está amarelo: a maioria das notícias chega sem um horário confiável (vem um horário fixo da madrugada, que não é o real), então é tratada como "só a data". Sem a hora, não dá para saber se a notícia saiu antes ou depois do fechamento da bolsa. Por isso o modelo usa uma janela larga, das {corte_noite} de um pregão até as {corte_noite} do pregão seguinte, e nunca usa notícia que ainda não tinha saído. Quando a coleta trouxer a hora real: dá para separar as notícias da noite das do dia.'
- **acao_rotina**: 'O que faz: lê o banco da coleta (só leitura), calcula os indicadores do pregão, grava os pacotes em saida/ e o top 5 do dia em registros/experimento/. Pelo painel ela roda sem esperar a coleta terminar (--sem-esperar). Muda algo: sim, regrava a pasta do dia e o estado do envio. Enquanto a rotina não está em produção, o registro do top 5 daquele dia também é refeito a cada rodada: o registro novo guarda a hora em que foi gerado e, se foi depois de {limite_historico}, sai marcado como "não vale para o histórico" (hoje, antes da produção, nenhum top 5 vale). Em produção, o registro do dia é gravado uma única vez e nunca é refeito. Nunca escreve no banco. Em produção, quem roda a rotina é o Agendador de Tarefas do Windows, não o painel.'
- **grafico**: 'Para cada pregão do período de desenvolvimento, conta se as ações escolhidas renderam mais que o Ibovespa no pregão seguinte. A bolinha é o acerto médio; o tracinho é o intervalo de confiança (onde o acerto verdadeiro provavelmente está). Aparecem quatro jeitos de escolher: o modelo com notícias, o mesmo modelo sem notícias, um modelo mais simples (regressão logística) e uma regra simples (as ações mais calmas, de menor volatilidade, primeiro). O modelo com notícias só "ganha" se o acerto dele ficar à direita da faixa do acaso e acima da regra simples e da regressão logística. A comparação com o modelo sem notícias responde outra pergunta: se as notícias ajudam.'
- **modelo_sombra**: 'É o modelo sem notícias (chamado de modelo um no TCC): igual ao principal, mas sem as colunas de notícias. Todo dia ele escolhe o próprio top 5, junto com o top 5 da regra simples (as ações mais calmas primeiro). Os dois ficam só no registro interno (pasta registros/experimento/), sem ir para o site, para comparar com dados de verdade se o modelo com notícias acerta mais.'

### L4. "O que fazer" que SUBSTITUEM os da tabela A.4
- **saude_quantidade_acoes**: 'Nada: aguardando a coleta gravar a quantidade de ações em unidades. P/L, P/VP e payout dessas empresas já saem "indisponível".'
- **saude_retornos**: 'Nada: aguardando a coleta corrigir os casos que são erro. Esses dias já ficam fora das comparações com o setor, do beta e da volatilidade.'

### L5. Extras: onde entram
- **E1** (frase "hoje × dados de"): `visao.frase_dia` na Fase 3; `visao.dia` no JSON, na Fase 4; `<p id="frase-dia">` na Fase 5b. Testes da Fase 3:
  - `frase_dia` com hoje domingo 25/10/2026 e última rotina diária de 23/10/2026 → `"Hoje é domingo, 25/10/2026 (sem pregão). A última rotina diária é do pregão de sex 23/10/2026."`;
  - com hoje sexta 23/10/2026, pregão, e última rotina de 22/10 → `"Hoje é sexta, 23/10/2026 (dia de pregão). A rotina de hoje ainda não rodou; a última é do pregão de qui 22/10/2026."`;
  - com a última rotina do próprio dia → `"Hoje é sexta, 23/10/2026 (dia de pregão). A última rotina diária é a de hoje."`;
  - sem rotina → `"Hoje é domingo, 25/10/2026 (sem pregão). Nenhuma rotina diária encontrada."`;
  - feriado: `"(sem pregão: Nossa Senhora Aparecida)"`.
- **E2** (glossário): `ajuda.GLOSSARIO` na Fase 1, com os textos de L6, testados como em A.3 (sem dígitos nem palavras proibidas); `visao.glossario` no JSON, na Fase 4; `<details id="glossario">` "Palavras do painel" no rodapé, na Fase 5b.
- **E3** (impressão): `@media print` na Fase 5b, como na seção "Extras". Teste: `"@media print" in pagina`.

### L6. Textos do glossário (E2), em `ajuda.GLOSSARIO` (lista de pares termo → texto, nesta ordem)
1. Pregão: Um dia de negociação na bolsa brasileira (B3). Fim de semana e feriado não têm pregão.
2. Ibovespa: O principal índice da bolsa brasileira, uma "cesta" das ações mais negociadas. Serve de régua: o experimento pergunta se uma ação vai render mais que ele no pregão seguinte.
3. Indicador: Um número calculado sobre a ação ou a empresa, como a cotação, a rentabilidade, o P/L ou o dividend yield.
4. Indisponível: O dado necessário não veio da coleta, ou veio com um defeito conhecido. O painel mostra "indisponível" em vez de zero ou de um chute.
5. Histórico insuficiente: Existe dado, mas não o bastante para a conta, por exemplo poucos pregões para calcular o beta, ou um buraco longo na série.
6. Pacote: Um arquivo com um tipo de informação pronta para o site (resumo das ações, séries dos gráficos, balanços, dividendos, notícias, registro da rodada).
7. Rodada: Cada vez que a rotina roda para um mesmo dia. A pasta do dia guarda só a última.
8. Diagnóstico: O "termômetro" que confere o banco da coleta contra o que foi combinado na especificação e gera o relatório da seção Saúde dos dados.
9. Walk-forward: Um jeito de testar o modelo como na vida real: treina só com o passado, testa no mês seguinte e avança, mês a mês, sem nunca olhar o futuro.
10. Faixa do acaso: Onde cai a taxa de acerto de quem escolhe ações por sorteio, em quase todos os sorteios. Ficar dentro dela quer dizer que o modelo ainda não mostrou vantagem sobre sortear.
11. Calibração: Conferir se a chance que o modelo diz bate com o que acontece: se ele diz "seis em cada dez" para um grupo de casos, cerca de seis em cada dez devem acontecer.
12. P/L: O preço da ação dividido pelo lucro por ação dos últimos doze meses. Diz quantos anos de lucro "cabem" no preço.
13. P/VP: O preço da ação dividido pelo valor patrimonial por ação, ou seja, o patrimônio da empresa no balanço dividido pelo número de ações.
14. Payout: A parte do lucro dos últimos doze meses que a empresa pagou aos acionistas como dividendos e juros sobre capital próprio.
15. Dividend yield: Os dividendos pagos nos últimos doze meses divididos pelo preço atual da ação.

---

Li o código real do painel inteiro: `pagina.html`, `servidor.py`, `visao.py`, `saude.py`, `leitores.py`, `relatorios.py` e `acoes.py`. Li também os testes `test_painel_pagina`, `_servidor`, `_visao`, `_saude` e `_leitores`, as fixtures, as seções 4, 6, 7.5–7.7, 8 e 10 da especificação, o `docs/diagnostico_banco.md` real, os logs reais de `logs/painel/` e o print claro. Não editei nada e não rodei nada que acesse o banco. Também não li o `.env`.

## Premissas conferidas no código

- **O favicon hoje seria bloqueado.** A CSP (`servidor.py:27-30`) tem `default-src 'none'` e nenhum `img-src`, então qualquer imagem cai em `'none'`. Basta acrescentar `img-src data:` à CSP. Nenhum teste compara a CSP inteira: `test_painel_servidor.py:117` só confere se o cabeçalho existe.
- **O ícone da aba precisa do endereço do SVG, que o teste proíbe.** Um SVG usado como `data:` precisa de `xmlns="http://www.w3.org/2000/svg"`, e `test_sem_recurso_externo` proíbe "http://" escrito na página. Saída: o JS clona o SVG da logo e o converte em texto com `XMLSerializer`, que acrescenta o `xmlns` sozinho. Depois cria o `<link rel="icon">` com `document.createElement("link")`. Assim a página nunca tem `<link` nem "http" escritos, e o teste `test_sem_fontes_externas_nem_link_de_estilo` continua como está.
- **Nenhum teste depende da ordem das seções.** `test_painel_pagina.py` só usa `in`, então mover Ações para o fim é seguro.
- **Textos que os testes exigem e que ficam:**
  - `<title>…Painel de operação…</title>` (`test_painel_servidor.py:114`);
  - `<h1>Sala de Operação</h1>`;
  - "Saúde dos dados", "Histórico de execuções", "Testes automáticos", "Experimento: top 5 com maior chance de superar o Ibovespa", "Última atualização", "A manhã do pregão de ";
  - os 4 textos de `DESCRICAO`;
  - os ids `agora`, `linha-tempo`, `comandos`, `saude`, `experimento`, `historico`, `testes`, `carga-linha` e os demais da linha 87.
- **Palavras proibidas na página** (`test_painel_pagina.py:171`):
  - os termos são "compre", "oportunidade", "melhores ações" e "recomendação". Atenção: "compreender" contém "compre";
  - também não podem aparecer "simular" nem "passo(" (`:183`).
- **Palavras proibidas no código Python do painel** (`test_painel_servidor.py:417`): "SELECT", "executar_leitura", "create_engine", "load_dotenv", `.env"` e "shell=True". Isso vale também para os textos de ajuda.
- **Duração real das ações:**
  - O Executor grava em todo log de `logs/painel/` uma linha `# painel: acao=X inicio=…` no começo e `# painel: fim=… codigo=N[ parado=sim]` no fim (`acoes.py:177-181, 292-295`).
  - O pytest real de hoje levou de 02:31:33 a 02:36:28 (295 s, "~5 min").
  - A rotina e a carga também têm a duração no `execucao.json` (`duracao_s`).
- **O prazo e os outros valores vêm do yaml real:** `rotina.prazo` "09:45", `prazo_tardio` "12:00", `inicio_consulta` "08:00", `intervalo_minutos` 5, `saida.limite_valido_historico` "10:00", `corte_noite` "08:00", `fase1.retorno_suspeito_min/max` −0.75/1.0, `base_defasagem_max_pregoes` 5, `fundamentos.pvp_minimo_plausivel` 0.05, `treino.acaso_sorteios` 10000, `treino.teste_final.inicio` "2026-06-23".
- **A trava abandonada é apagada pela próxima rotina** (`processamento/rotina/trava.py:4-5, 53`).

---

# (A) PLANO PARA O USUÁRIO

## A.1 Como a página fica

**Tela larga (a partir de 1280 px), ocupando toda a largura:**
```
+------------------------------------------------------------------------------------------------+
| [chip] Interface do Processamento          [Última rotina: ok] [Domingo · sem pregão] [Tema] [Atualizar] |
| Sala de Operação                                                                               |
| Acompanha o que o processamento faz todo dia...            Dados de 25/10/2026 02:13            |
+------------------------------------------------------------------------------------------------+
| (1) Resumo (?)                                                                                 |
| | Atenção: 4 pontos   <- clicar leva ao 1º ponto                                               |
| | [Quantidade de ações (19 empresas) · O que fazer: Nada: aguardando...] [Preços suspeitos ...] |
| | [Lacunas nas séries (3 lacunas) · ...]  [Horário das notícias (90,8% sem hora real) · ...]   |
+------------------------------------------------------------------------------------------------+
| (2) Fluxo do dia                                                                               |
| +-- Última atualização · pregão de sex 23/10 (?) ---+  +-- A manhã do pregão (?) -------------+ |
| | Coleta(?) --> Processamento(?) --> Interface(?)   |  | prazo (?)                            | |
| | última carga completa: ... (?)                    |  | 08:00 ===08:22 ......... 09:45  10:00| |
| +------------------------- 7/12 --------------------+  +---------------- 5/12 ----------------+ |
| (3) Saúde dos dados (?)                                                                        |
| [Contrato (?)]        [Quantidade de ações (?)]   [Preços suspeitos (?)]                        |
| [Lacunas (?)]         [Horário das notícias (?)]  [Histórico disponível (?)]                    |
|        (a partir de 1700 px: os 6 cartões numa linha só)                                        |
| (4) Experimento                         7/12   | (5) Histórico                        5/12      |
| [cadeado (?)] [modelo, top 5 retido (?), ...]  | [calendário] [tabela] [detalhe]                |
| [gráfico acerto x acaso (?) faixa (?)]         |                                                |
| (6) Ações                                                                                      |
| [Rotina (?)] [Carga (?)] [Diagnóstico (?)] [Testes (?)]  8/12 | [Testes automáticos (?)] 4/12   |
|  "Tempo: leva ~2 min. Da última vez..."                       |                                 |
| [andamento + log da ação]                                     |                                 |
+------------------------------------------------------------------------------------------------+
```

**Tela estreita (abaixo de 900 px): tudo em uma coluna, na ordem 1 a 6:**
```
[chip] Interface do Processamento
[pílulas] [Tema] [Atualizar]          (quebram linha)
Sala de Operação
(1) Resumo
(2) Fluxo do dia: Coleta / v / Processamento / v / Interface  (empilhados)
    A manhã do pregão
(3) Saúde: 2 colunas (600–899 px) ou 1 coluna (abaixo de 600 px)
(4) Experimento: cadeado e dados em cima, gráfico embaixo
(5) Histórico
(6) Ações: botões um abaixo do outro; Testes automáticos por último
```

**Larguras de corte:**

| Largura | O que muda |
|---|---|
| abaixo de 600 | Saúde em 1 coluna; margens menores |
| de 600 a 899 | Saúde em 2 colunas |
| de 900 a 1279 | Saúde em 3 colunas; cartões empilhados |
| 1280 ou mais | Fluxo ao lado da Linha do tempo; Experimento ao lado do Histórico; Ações ao lado dos Testes |
| 1700 ou mais | Saúde com os 6 cartões numa linha |

Dentro de cada cartão, o fluxo e o experimento se ajustam ao espaço do próprio cartão (consulta de contêiner do CSS). Assim, o fluxo vira coluna quando o cartão fica estreito, mesmo em tela larga.

## A.2 Logo e ícone da aba

- No canto superior esquerdo fica o desenho de um chip (quadrado com "perninhas"), feito no próprio código, com o texto "Interface do Processamento". O título "Sala de Operação" continua logo abaixo.
- O mesmo desenho vira o ícone da aba do navegador, gerado pela página sem nenhum arquivo externo.
- Para isso, a regra de segurança da página (CSP) ganha só `img-src data:`. Isso libera apenas imagens embutidas na própria página; nada da internet.
- **Ponto para você decidir:** "Interface" no painel já é o nome do site (o estágio 3 do fluxo). O texto "Interface do Processamento" pode confundir a banca. Mantenho o que você pediu, mas uma alternativa seria "Painel do Processamento".

## A.3 Textos de ajuda ("?"): lista completa

**Onde ficam:** num único arquivo Python, `processamento/painel/ajuda.py`, em dois dicionários (`AJUDA` e `O_QUE_FAZER`). Escolhi um arquivo Python, e não um dicionário dentro do `pagina.html`, por três motivos:
1. É um arquivo curto, só de textos, fácil de revisar e de testar automaticamente (palavras proibidas, nenhum número escrito à mão, nenhum campo esquecido).
2. Os valores entre chaves, como `{prazo}`, são preenchidos no servidor com o valor real do `parametros.yaml`. Campo sem valor vira "sem dados".
3. Os mesmos textos alimentam a faixa de resumo, que é calculada no servidor.

O servidor manda os textos prontos em `visao.ajuda` no JSON.

**Como a caixinha funciona:**
- Abre ao passar o mouse, ao clicar ou ao tocar. No teclado: Tab até o "?" e Enter ou Espaço.
- Fecha com Esc (o foco volta para o "?") ou com clique fora. Só uma fica aberta por vez.
- O "?" é um botão com o rótulo "Ajuda: <título>", e a caixinha é ligada a ele para leitores de tela.

Os únicos números escritos nos textos são "top 5" (nome do produto) e "95%" (a definição da faixa do acaso, que já está na legenda aprovada).

| id | Título | Onde fica | Texto |
|---|---|---|---|
| resumo | Resumo | título da seção 1 | Uma frase que junta tudo o que está amarelo ou vermelho no painel. "Tudo certo": nada pede atenção. "Atenção": há pontos para acompanhar, mas nada quebrou (em geral, defeitos conhecidos da coleta que o processamento já contorna, ou um dado que não pôde ser lido). "Falhou": algo quebrou de verdade, como a rotina do dia, os testes automáticos, o calendário ou o formato combinado com a coleta. Clique num item da lista para ir direto a ele. |
| fluxo | Última atualização | título do cartão do fluxo | Mostra o caminho dos dados no último pregão processado, em três passos: a coleta (outro módulo) busca os dados e grava num banco; o processamento (este módulo) lê esse banco, calcula e confere; a interface (o site) recebe os pacotes prontos. A data no título é a do pregão, que pode não ser hoje: fim de semana e feriado não têm pregão. |
| coleta | Coleta | rótulo do estágio 1 | É o outro módulo do TCC. Em todo dia de pregão ele baixa preços, balanços e notícias e grava tudo num banco de dados. Quando termina a parte que interessa, marca a etapa "entrega" como concluída. O processamento começa a perguntar se a entrega ficou pronta às {inicio_consulta} e repete a pergunta a cada {intervalo} minutos. O processamento só lê esse banco; nunca escreve nele. |
| processamento | Processamento | rótulo do estágio 2 | É este módulo. Quando a coleta entrega, ele lê o banco (só leitura), calcula os indicadores de cada ação, confere se os números fazem sentido e monta os pacotes para o site. Se a entrega não chegar até {prazo}, a rodada fica como "falhou" e nenhum pacote novo sai: o site continua com os dados do pregão anterior. Mesmo assim, ele continua tentando até {prazo_tardio}. |
| interface | Interface | rótulo do estágio 3 | É o site que as pessoas vão usar. Ele não lê o banco da coleta: recebe do processamento os pacotes já prontos. Enquanto o site não existe, os pacotes ficam guardados como arquivos na pasta saida/, uma pasta por dia. |
| pacotes | Pacotes | título do estágio 3 ("7 pacotes prontos") | Um pacote é um arquivo com um tipo de informação para o site: o resumo de cada ação, as séries dos gráficos, os balanços, os dividendos, as notícias do dia e o registro da rodada. Os registros são as linhas dentro dos pacotes (uma por ação, por dia ou por série). Alguns pacotes só levam o que mudou desde o último envio; por isso, um pacote com zero registros não é erro. |
| contrato | Versão do contrato | linha "Contrato 1.0 · 179 registros" | O contrato é o combinado entre o processamento e o site sobre o formato dos pacotes: o nome de cada campo, o formato das datas e como mostrar um valor que não existe (vazio e com o motivo, nunca zero). Se um campo mudar, a versão sobe e o site sabe que precisa se adaptar. |
| rodada | Rodada e avisos | linha "Rodada 6 · 7 avisos" | Cada vez que a rotina roda de novo para o mesmo dia, o número da rodada aumenta. A pasta do dia guarda só a última rodada; as anteriores ficam no log da rotina (seção Histórico). Avisos são observações que não impedem os pacotes de sair, por exemplo uma etapa da coleta que não terminou ou um preço que mudou muito num dia. |
| carga_vs_rotina | Carga completa e rotina diária | linha "última carga completa" | A rotina diária manda só o que é novo ou mudou desde o último envio, para não repetir tudo todo dia. A carga completa manda tudo de uma vez (todas as ações, um ano de séries, os balanços e os dividendos), para quando o site começar do zero ou perder o próprio banco. Ela grava numa pasta separada (saida_completa/) e não mexe no envio diário nem nos registros do experimento. |
| linha_tempo | A manhã do pregão | título do cartão da linha do tempo | Uma régua com os horários da manhã: quando a coleta começou e entregou, quando a rotina rodou, o prazo da rotina ({prazo}) e a abertura da bolsa ({abertura}). A rotina precisa terminar antes da abertura para o top 5 valer como previsão de verdade. Se a rotina rodou em outro dia (por exemplo, à mão, à noite), ela não aparece na régua e a folga fica sem medida. |
| prazo | Prazo da rotina | ao lado da frase explicativa da linha do tempo | É o horário-limite para a coleta entregar os dados: {prazo}, lido do arquivo de configuração (parametros.yaml). Sem entrega até lá, a rodada é registrada como "falhou" e só o arquivo da rodada é gravado, para o site avisar que os dados são do pregão anterior. A rotina continua tentando até {prazo_tardio}, mas um top 5 feito depois de {limite_historico} não conta para o histórico do experimento. |
| folga | Folga | legenda "Folga até o prazo" | É o tempo que sobrou entre o fim da rotina e o prazo. Folga grande quer dizer margem de segurança se a coleta atrasar. Se a rotina terminar depois do prazo, aparece "atraso" no lugar da folga. |
| saude | Saúde dos dados | título da seção 3 | Antes de usar os dados, o processamento passa um "termômetro" no banco da coleta (o diagnóstico) e confere se tudo está no formato combinado. Verde: sem problema. Amarelo: um defeito conhecido da coleta, que o processamento já contorna (mostra "indisponível" em vez de um número errado). Vermelho: algo mudou e precisa ser olhado. Cinza: o painel não conseguiu ler esse cartão no relatório. Os números vêm do arquivo docs/diagnostico_banco.md, na data mostrada acima dos cartões. |
| saude_contrato | Contrato com a coleta | canto do cartão | O que é: confere se as tabelas e colunas que o processamento lê existem e têm o formato combinado. Aqui não há amarelo: ou bate (verde) ou há divergência (vermelho). Vermelho quer dizer que a coleta mudou alguma coisa e algum cálculo pode sair errado. Quando a coleta corrigir: o próximo diagnóstico volta a mostrar nenhuma divergência. |
| saude_quantidade_acoes | Quantidade de ações | canto do cartão | O que é: para saber quanto a empresa vale na bolsa (valor de mercado), o processamento multiplica o preço pela quantidade de ações. Por que está amarelo: em algumas empresas a coleta gravou essa quantidade em milhares, ou seja, mil vezes menor, e o valor de mercado fica absurdo. O processamento percebe quando o preço dividido pelo patrimônio (P/VP) fica abaixo de {pvp_min}; nessas empresas, valor de mercado, P/L, P/VP e payout aparecem como "indisponível", sem chute. Quando a coleta corrigir: esses indicadores voltam sozinhos no próximo cálculo. |
| saude_retornos | Preços suspeitos | canto do cartão | O que é: procura preços que mudaram de um dia para o outro de um jeito impossível (variação abaixo de {retorno_min} ou acima de {retorno_max} num só dia). Por que está amarelo: a coleta tem alguns preços com erro de escala (as ações e a quantidade de casos estão no cartão). O processamento não mexe no preço: só tira esses dias das médias do setor e das comparações, para o erro de uma ação não contaminar as outras. Quando a coleta corrigir: esses dias voltam a entrar sozinhos. |
| saude_lacunas | Lacunas nas séries | canto do cartão | O que é: procura buracos nas séries de preços e de índices, ou seja, muitos dias seguidos sem dado. Por que está amarelo: alguns índices (listados no cartão) estão sem dados num trecho longo. Quando a comparação precisaria de um dia que cai no buraco, e o dado mais próximo está a mais de {defasagem} pregões, o resultado sai "histórico insuficiente" em vez de um número enganoso. Quando a coleta preencher o buraco: as comparações com esses índices voltam a ter número. |
| saude_horario_noticias | Horário das notícias | canto do cartão | O que é: mostra quantas notícias têm a hora exata em que foram publicadas. Por que está amarelo: a maioria das notícias chega só com a data, sem a hora. Sem a hora, não dá para saber se a notícia saiu antes ou depois do fechamento da bolsa. Por isso o modelo usa uma janela larga, das {corte_noite} de um pregão até as {corte_noite} do pregão seguinte, e nunca usa notícia que ainda não tinha saído. Quando a coleta trouxer a hora real: dá para separar as notícias da noite e refazer esse teste. |
| saude_cobertura | Histórico disponível | canto do cartão | O que é: quantas linhas existem para treinar e testar o modelo do experimento (uma linha por ação por pregão) e de que data a que data. Verde: há histórico. Mesmo assim, enquanto o modelo não for declarado oficial no arquivo de configuração, tudo o que é treinado com ele é teste de funcionamento. |
| experimento | Experimento | título do cartão do experimento | É a parte de pesquisa do TCC. Um modelo de computador (XGBoost) olha os números de cada ação e o tom das notícias (lido por outro modelo, o FinBERT) e estima quais ações têm mais chance de render mais que o Ibovespa no pregão seguinte. Tudo o que aparece aqui é teste de funcionamento: prova que o caminho todo roda, mas não é o resultado do TCC. |
| teste_funcionamento | Teste de funcionamento | ao lado da faixa amarela | Quer dizer que o modelo foi treinado só para conferir se a máquina funciona do começo ao fim. Os números podem mudar bastante quando o modelo oficial for treinado. O resultado do TCC sai do teste final (o cadeado) e do acompanhamento ao vivo, depois que a rotina entrar em produção. |
| cadeado | Cadeado do teste final | título do cadeado | Um pedaço do histórico, a partir de {teste_final_inicio}, foi separado e trancado. Ninguém olha esse período enquanto o modelo é ajustado, para não "colar na prova". Ele será aberto uma única vez, na avaliação final, e não pode ser reaproveitado depois. Este painel não tem nenhum botão que destranque o cadeado. |
| modelo | Modelo em uso | linha "Modelo" | Nome do arquivo do modelo (xgb, seguido do ano e do mês do treino), o período de dados usado para treinar e se ele é provisório ou oficial. Provisório quer dizer treinado só para teste de funcionamento. |
| top5_retido | Top 5 retido | linha "Top 5 na interface" | Todo dia o processamento calcula as cinco ações que o modelo vê com mais chance de superar o Ibovespa no pregão seguinte e guarda esse registro (pasta registros/experimento/). Enquanto o modelo for só de teste, esse top 5 não é enviado ao site: fica retido. Ele só vai para o site quando houver modelo oficial ou quando a publicação for ligada no arquivo de configuração. |
| chance | Chance escondida e calibração | linha "Chance exibida" | O modelo calcula uma probabilidade para cada ação. Antes de mostrar esse número, é preciso conferir a calibração: se o modelo diz "chance alta" num grupo de dias, a fração de acertos nesses dias tem que ser parecida com a chance dita. Até essa conferência passar, e até a exibição ser ligada no arquivo de configuração, a chance fica escondida, para ninguém ler um número ainda não validado. |
| modelo_sombra | Modelo sombra | linha "Modelo sombra" | É um segundo modelo, igual ao principal mas sem as notícias. Ele roda escondido todo dia só para comparar: se o modelo com notícias não acertar mais que ele, as notícias não estão ajudando. |
| grafico | Acerto do top 5 | título "Acerto do top 5 no desenvolvimento" | Para cada pregão do período de desenvolvimento, conta se as ações escolhidas renderam mais que o Ibovespa no pregão seguinte. A bolinha é o acerto médio; o tracinho é o intervalo de confiança (onde o acerto verdadeiro provavelmente está). São comparados quatro jeitos de escolher: o modelo com notícias, o mesmo sem notícias, um modelo mais simples (regressão logística) e uma regra simples (as ações mais calmas primeiro). O modelo com notícias só "ganha" se superar os outros três e ficar à direita da faixa do acaso. |
| faixa_acaso | Faixa do acaso | legenda "faixa cinza = acaso" | Imagine escolher ações por sorteio todo dia e repetir isso {sorteios} vezes. A faixa cinza mostra onde caem 95% desses sorteios. Ficar dentro da faixa quer dizer "ainda não mostrou vantagem sobre sortear". Só a bolinha verde, à direita da faixa, indica acerto acima do acaso, e mesmo assim, aqui, é teste de funcionamento. |
| historico | Histórico de execuções | título do cartão do histórico | Cada quadradinho do calendário é um dia útil. Verde: a rotina rodou bem. Amarelo: rodou com pendências. Vermelho: falhou. Azul: rodando agora. Cinza: não rodou. Tracejado: feriado (sem pregão). Um traço azul embaixo do dia indica que houve carga completa. Clique num dia ou numa linha da tabela para ver os detalhes. Cada dia guarda só a última rodada; as anteriores aparecem no log da rotina. |
| testes | Testes automáticos | título do cartão de testes | São verificações automáticas do código (pytest) que rodam sem o banco e sem internet, com dados pequenos de exemplo. Entre outras coisas, conferem que nenhum cálculo olha o futuro e que dado ausente vira "indisponível", nunca zero. Aqui aparece o resultado da última vez em que os testes foram rodados pelo painel. |
| acao_rotina | Rodar a rotina do dia | título do botão | O que faz: lê o banco da coleta (só leitura), calcula os indicadores do pregão, grava os pacotes em saida/ e o top 5 em registros/experimento/. Pelo painel ela roda sem esperar a coleta terminar (--sem-esperar). Muda algo: sim, regrava a pasta do dia, o estado do envio e o registro do top 5 daquele dia. Nunca escreve no banco. Em produção, quem roda a rotina é o Agendador de Tarefas do Windows, não o painel. |
| acao_carga | Gerar a carga completa | título do botão | O que faz: gera todos os pacotes inteiros do último dia processado, para o site começar do zero. Muda algo: só grava na pasta saida_completa/; não mexe no envio diário nem nos registros do experimento. Lê o banco da coleta (só leitura). |
| acao_diagnostico | Rodar o diagnóstico do banco | título do botão | O que faz: passa o termômetro no banco da coleta e reescreve o relatório docs/diagnostico_banco.md, que alimenta os cartões de Saúde dos dados. Muda algo: só reescreve esse relatório; no banco, só lê. |
| acao_testes | Rodar os testes | título do botão | O que faz: roda os testes automáticos (pytest). Não usa o banco nem a internet. Muda algo: não muda nenhum dado; só grava o registro da execução na pasta logs/painel/. É a única ação que pode ser parada no meio. |

**Valores reais que preenchem os campos hoje:**

| Campo | Valor |
|---|---|
| `{prazo}` | 09:45 |
| `{prazo_tardio}` | 12:00 |
| `{inicio_consulta}` | 08:00 |
| `{intervalo}` | 5 |
| `{limite_historico}` | 10:00 |
| `{corte_noite}` | 08:00 |
| `{retorno_min}` | -75% |
| `{retorno_max}` | +100% |
| `{defasagem}` | 5 |
| `{pvp_min}` | 0,05 |
| `{sorteios}` | 10.000 |
| `{teste_final_inicio}` | 23/06/2026 |
| `{abertura}` | vem da linha do tempo (10:00 em 23/10) |

## A.4 "O que fazer" de cada farol amarelo ou vermelho (também em `ajuda.py`)

A linha "O que fazer: …" aparece embaixo do item na tela e também na lista do Resumo.

| Chave | Quando aparece | Texto |
|---|---|---|
| saude_contrato | cartão Contrato vermelho | Ver no diagnóstico completo qual tabela ou coluna mudou e avisar a coleta. Depois da correção, rodar o diagnóstico de novo. |
| saude_quantidade_acoes | cartão Quantidade amarelo | Nada: aguardando a coleta gravar a quantidade de ações em unidades. Os indicadores afetados já saem "indisponível". |
| saude_retornos | cartão Preços suspeitos amarelo | Nada: aguardando a coleta corrigir esses preços. Esses dias já ficam fora das médias do setor. |
| saude_lacunas | cartão Lacunas amarelo | Nada: aguardando a coleta preencher o histórico desses índices. As comparações afetadas já saem "histórico insuficiente". |
| saude_horario_noticias | cartão Horário amarelo | Nada: aguardando a coleta trazer o horário real das notícias. O modelo já usa a janela larga. |
| saude_cobertura | cartão Histórico amarelo (zero linhas) | Conferir o dataset do experimento: sem linhas, o modelo não tem com o que treinar. |
| saude_sem_dados | qualquer cartão cinza ("sem dados") | Rodar o diagnóstico do banco de novo (seção Ações). Se o cartão continuar sem dados, o formato do relatório mudou e o painel precisa ser ajustado. |
| saude_sem_diagnostico | relatório do diagnóstico ausente ou ilegível | Rodar o diagnóstico do banco (seção Ações). Ele só lê o banco e grava o relatório que alimenta estes cartões. |
| coleta_warn | estágio Coleta amarelo | Abrir o dia no Histórico para ver o motivo. Se a coleta terminar depois, rodar a rotina de novo. |
| coleta_bad | estágio Coleta vermelho | Avisar a coleta. Até lá, o site continua com os dados do pregão anterior. |
| rotina_falhou | última rotina falhou | Abrir o dia no Histórico para ver o motivo. Se a coleta já entregou, rodar a rotina de novo (seção Ações). |
| rotina_parcial | última rotina parcial | Abrir o dia no Histórico e ler os avisos. Os pacotes que passaram na conferência já foram gravados. |
| rotina_interrompida | rotina possivelmente interrompida | Ver se o computador desligou ou a janela foi fechada no meio. Depois, rodar a rotina de novo. |
| sem_rotina | nenhuma rotina diária para mostrar | Rodar a rotina do dia (seção Ações) ou esperar a rotina agendada. |
| atraso_prazo | rotina terminou depois do prazo | Ver no log da rotina se a demora foi da coleta ou do cálculo. |
| calendario_erro | calendário com erro | Conferir o calendário de feriados no parametros.yaml. Enquanto isso, a rotina não sabe se hoje tem pregão. |
| testes_falhas | testes com falhas | Abrir o log dos testes, ver qual falhou e corrigir o código antes de confiar nos números. |
| testes_interrompidos | testes interrompidos ou sem resumo | Rodar os testes de novo até o fim. |
| trava_abandonada | trava velha da rotina | Nada, se nenhuma rotina estiver rodando: a próxima rotina apaga a trava velha sozinha. |

## A.5 Regra da faixa de resumo (calculada no servidor, função `visao.resumo`)

**Pontos, na ordem em que aparecem na página:**
1. **Fluxo do dia.**
   - Sem rotina diária para mostrar → atenção: "Fluxo do dia: sem dados".
   - Estágio Coleta amarelo → atenção; vermelho → falhou: "Coleta (entrega não concluída)" ou "Coleta (entrega com problema)".
   - Última rotina `falhou` → falhou: "Última rotina diária (23/10/2026) falhou".
   - `parcial` → atenção: "… com pendências".
   - `em_andamento` e possivelmente interrompida → atenção: "… pode ter sido interrompida".
2. **Linha do tempo:** rotina terminou depois do prazo → atenção: "Rotina terminou depois do prazo (atraso de 7 min 30 s)".
3. **Saúde:**
   - cada cartão amarelo vira atenção e cada vermelho vira falhou: "Quantidade de ações (19 empresas)";
   - cartão cinza ("sem dados") vira atenção, porque ausente nunca é "tudo certo";
   - relatório ausente → atenção: "Saúde dos dados: sem diagnóstico".
4. **Calendário com erro** → falhou: "Calendário da B3 com erro".
5. **Testes do painel:**
   - com falhas → falhou: "Testes automáticos com falhas (2 falhas)";
   - interrompidos → atenção: "Testes automáticos interrompidos";
   - reprovados sem linha de resumo (por exemplo, parados) → atenção: "Testes automáticos sem resultado completo";
   - nunca rodados → não conta.
6. **Trava abandonada** → atenção: "Trava da rotina esquecida (420 min)".

**A frase:**
- se há algum "falhou": `Falhou: <textos dos que falharam, separados por "; ">`, e no fim ` · e N ponto(s) de atenção` se também houver atenção;
- senão, se há atenção: `Atenção: 1 ponto` ou `Atenção: N pontos`;
- senão: `Tudo certo`.

Clicar na frase leva ao primeiro ponto. Cada ponto da lista é um link que rola até o item e põe o foco nele.

**O que aparece hoje:**
- Com os dados reais: "Atenção: 4 pontos" (Quantidade de ações, Preços suspeitos, Lacunas, Horário das notícias).
- Com as fixtures dos testes: "Falhou: Contrato com a coleta (2 divergências) · e 5 pontos de atenção". O diagnóstico das fixtures tem 1 cartão vermelho e 5 cinzas.

## A.6 Botões de Ações: descrição e tempo

A descrição de uma linha que já existe continua. Entra uma linha nova "Tempo:", que nunca usa número escrito à mão:
1. Se existe log do painel daquela ação que terminou normalmente: "Tempo: leva ~5 min. Da última vez, pelo painel, levou 4 min 55 s."
2. Senão, para rotina e carga, usa o `execucao.json` da última rodada que terminou ok ou parcial: "Tempo: leva ~2 min. A última rotina diária levou 1 min 58 s."
3. Senão: "Tempo: Ainda sem medição: pode levar alguns minutos."

Hoje ficaria assim: rotina ~2 min, carga ~2 min, diagnóstico "ainda sem medição", testes ~5 min.

**Opção para você aprovar:** se preferir uma estimativa fixa quando não houver medição, ela seria um número escrito à mão. Por isso não está no plano.

## A.7 Arquivos que mudam (todos dentro do painel)

- novo `processamento/painel/ajuda.py` (os textos);
- `visao.py`: resumo, tempos, hora da abertura;
- `leitores.py`: lê os valores do yaml para os textos;
- `relatorios.py`: duração das ações nos logs do painel;
- `servidor.py`: 3 chaves novas dentro de `visao` e `img-src data:` na CSP;
- `pagina.html`;
- testes: novo `tests/test_painel_ajuda.py`; acréscimos em `test_painel_leitores.py`, `test_painel_relatorios.py`, `test_painel_visao.py` e `test_painel_pagina.py`; uma linha mudada em `test_painel_servidor.py`;
- fixture `tests/dados/painel/raiz/processamento/config/parametros.yaml` (ganha as chaves que os textos citam).

O JSON só ganha chaves: `visao.resumo`, `visao.tempos` e `visao.ajuda`.

## A.8 Testes que mudam

Só um teste existente muda: `test_painel_servidor.py::test_api_painel_visao_com_as_fixtures`, na linha 190. Ela compara o conjunto exato de chaves de `visao`, que agora ganha `resumo`, `tempos` e `ajuda`. Todos os outros testes existentes ficam como estão.

## A.9 Melhorias extras (aprovar uma a uma; não entram sem aprovação)

- **E1. Frase "hoje × dados de" no topo.** Exemplo: "Hoje é domingo, 25/10/2026 (sem pregão). A última rotina diária é do pregão de sex 23/10/2026." Em dia de pregão sem rotina ainda: "A rotina de hoje ainda não rodou; a última é do pregão de …". É calculada no servidor (`visao.frase_dia`) e evita a impressão de que a coleta rodou hoje.
- **E2. Glossário rápido no rodapé.** Um bloco recolhível "Palavras do painel", com uma linha para cada termo: pregão, Ibovespa, indicador, indisponível, histórico insuficiente, pacote, rodada, diagnóstico, walk-forward, faixa do acaso, calibração, P/L, P/VP, payout, dividend yield. Os textos também ficam em `ajuda.py` (`GLOSSARIO`). Eu escrevo os textos se você aprovar.
- **E3. Versão para imprimir ou salvar em PDF, para a banca.** No modo de impressão do navegador, a página esconde botões, "?" e log, abre os blocos recolhidos e usa uma coluna. Só CSS, sem mudar nada no servidor.

## A.10 Riscos

- A linha do tempo fica mais estreita (5/12 da tela) e os rótulos de horários próximos podem encostar. A régua alterna rótulos acima e abaixo; confiro nos prints.
- O ícone da aba depende do `XMLSerializer` e do `img-src data:`. Se o navegador recusar, só o ícone some; nada quebra.
- O JSON cresce uns 15 KB por atualização (a cada 30 s, local). É irrelevante.
- Se o texto do diagnóstico mudar, os cartões ficam cinzas e o Resumo passa a mostrar "Atenção". Isso é de propósito.
- `pagina.html` continua um arquivo único e grande, que fica maior (cerca de +300 linhas).

---

# (B) PLANO DETALHADO PARA OS IMPLEMENTADORES (Haiku)

## Regras para todas as fases (copiar em todo despacho)

- Projeto `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc`, Windows. Python: `.venv/Scripts/python.exe`. Responder em português. Não fazer commit.
- **Só mexer** em `processamento/painel/`, `tests/test_painel_*.py`, `tests/fabrica_painel.py` e `tests/dados/painel/`. Nada fora disso: nem o `parametros.yaml` real, nem a especificação, nem `conftest.py`.
- **Nunca ler o `.env`.** No painel, nunca importar `processamento.fontes`, `sqlalchemy` nem `dotenv`. Nenhum SQL.
  - Os `processamento/painel/*.py` não podem conter "SELECT", "executar_leitura", "create_engine", "load_dotenv", `.env"` nem "shell=True". Isso vale também para os textos.
  - Nunca rodar `python -m processamento.rotina`, `processamento.saida` nem `processamento.diagnostico`: eles acessam o banco, e o usuário atual do banco tem permissão de escrita.
- Funções de leitura nunca levantam exceção por arquivo ausente ou quebrado. Ausência = `None` ou "sem dados", nunca 0. Fuso: `from processamento.calendario import SP`; ISO sem fuso = São Paulo (`leitores._instante`).
- Todo módulo novo começa com `from __future__ import annotations` e uma docstring curta. Sem emoji.
- Testes:
  - usam `montar_raiz(tmp_path)` (`from fabrica_painel import montar_raiz`) e nunca escrevem em `tests/dados/`;
  - fixture de log se chama `*.log.txt`.
- **Página (`pagina.html`):**
  - DOM só com `createElement`/`createElementNS` + `textContent`/`createTextNode`;
  - proibido `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` e `eval(`;
  - nenhum "http://" ou "https://" escrito e nenhum `<link` escrito;
  - nunca escrever "simular" nem "passo(";
  - não usar `localStorage` (as linhas que já usam têm `try`);
  - palavras proibidas: "compre" (cuidado com "compreender"), "oportunidade", "melhores ações" e "recomendação", exceto a frase exata "Não constitui recomendação de investimento.";
  - nunca pôr um botão "?" dentro de um elemento cujo `textContent` o JS reescreve (`h-fluxo`, `h-tl`, `lock-t`, `grafico-tit`, `carga-linha`, `tl-why`). O "?" vai como irmão, dentro de um `<div class="tit-linha">`.
- **Verificação de cada fase:** primeiro `.venv/Scripts/python.exe -m pytest -q <arquivo de teste da fase>`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`.

## Ordem e paralelismo

| Onda | Fases (em paralelo dentro da onda) | Depende de |
|---|---|---|
| 1 | Fase 1 (`ajuda.py`) ∥ Fase 2 (`leitores`, `relatorios`, fixture yaml) ∥ Fase 5a (página: layout, logo, favicon) | — |
| 2 | Fase 3 (`visao.py`) ∥ Fase 5b (página: ajuda, resumo, "O que fazer", tempos) | 3 depende de 1; 5b depende de 1 e 5a |
| 3 | Fase 4 (`servidor.py`) | 1, 2, 3 |
| 4 | Fase 6 (verificação, pelo executor) | todas |

Dentro de cada onda, as fases não mexem nos mesmos arquivos.

---

### FASE 1: `processamento/painel/ajuda.py` + `tests/test_painel_ajuda.py` (independente)

Crie o arquivo `processamento/painel/ajuda.py`:
```python
"""Textos de ajuda ("?") e de "O que fazer" do painel, num lugar só, para revisar fácil.

Nenhum número escrito à mão: valores como o prazo vêm do parametros.yaml ou dos arquivos do projeto
e entram nos campos {entre chaves}. Campo sem valor vira "sem dados".
"""

from __future__ import annotations

import string

SEM_DADOS = "sem dados"

CAMPOS = frozenset({
    "prazo", "prazo_tardio", "inicio_consulta", "intervalo", "limite_historico", "corte_noite",
    "retorno_min", "retorno_max", "defasagem", "pvp_min", "sorteios", "teste_final_inicio", "abertura",
})

# id -> (título, texto). Strings entre aspas simples: os textos usam aspas duplas e nunca apóstrofo.
AJUDA: dict[str, tuple[str, str]] = {
    "resumo": ('Resumo', '...'),
    # ... os 34 ids, na ordem da tabela A.3
}

# chave -> texto curto de "O que fazer".
O_QUE_FAZER: dict[str, str] = {
    "saude_contrato": '...',
    # ... as 19 chaves da tabela A.4
}


def campos_do_texto(texto: str) -> set[str]:
    """Nomes dos campos {assim} usados num texto."""
    return {nome for _, nome, _, _ in string.Formatter().parse(texto) if nome}


class _Valores(dict):
    def __missing__(self, chave: str) -> str:
        return SEM_DADOS


def montar_ajuda(valores: dict | None) -> dict[str, dict[str, str]]:
    """Textos de ajuda com os campos preenchidos; campo sem valor (ou não-texto) vira "sem dados"."""
    limpos = _Valores({k: v for k, v in (valores or {}).items() if isinstance(v, str) and v})
    return {id_: {"titulo": titulo, "texto": texto.format_map(limpos)} for id_, (titulo, texto) in AJUDA.items()}
```
- Copie os textos **exatos** da tabela A.3: coluna "Título" e coluna "Texto", com os `{campos}` como estão. Use os 34 ids, na mesma ordem.
- Copie os textos **exatos** da tabela A.4 para `O_QUE_FAZER`, com as 19 chaves.
- Delimite as strings com aspas simples. Os textos contêm aspas duplas e nenhum apóstrofo.

Crie o arquivo `tests/test_painel_ajuda.py`:
```python
import re
from pathlib import Path
from processamento.painel import ajuda
from processamento.painel.ajuda import AJUDA, CAMPOS, O_QUE_FAZER, campos_do_texto, montar_ajuda

IDS = {"resumo", "fluxo", "coleta", "processamento", "interface", "pacotes", "contrato", "rodada",
       "carga_vs_rotina", "linha_tempo", "prazo", "folga", "saude", "saude_contrato",
       "saude_quantidade_acoes", "saude_retornos", "saude_lacunas", "saude_horario_noticias",
       "saude_cobertura", "experimento", "teste_funcionamento", "cadeado", "modelo", "top5_retido",
       "chance", "modelo_sombra", "grafico", "faixa_acaso", "historico", "testes", "acao_rotina",
       "acao_carga", "acao_diagnostico", "acao_testes"}
CHAVES_FAZER = {"saude_contrato", "saude_quantidade_acoes", "saude_retornos", "saude_lacunas",
                "saude_horario_noticias", "saude_cobertura", "saude_sem_dados", "saude_sem_diagnostico",
                "coleta_warn", "coleta_bad", "rotina_falhou", "rotina_parcial", "rotina_interrompida",
                "sem_rotina", "atraso_prazo", "calendario_erro", "testes_falhas", "testes_interrompidos",
                "trava_abandonada"}

def _todos():
    return [t for par in AJUDA.values() for t in par] + list(O_QUE_FAZER.values())
```
Testes do arquivo, com os valores esperados:
1. `set(AJUDA) == IDS`, e cada valor é uma tupla de 2 strings não vazias. `set(O_QUE_FAZER) == CHAVES_FAZER`.
2. Para cada texto, `campos_do_texto(texto) <= CAMPOS`. A união dos campos de todos os textos de `AJUDA` é `== CAMPOS` (todo campo é usado). Os textos de `O_QUE_FAZER` não têm campos.
3. Nenhum número escrito à mão. Para cada texto `t` de `_todos()`:
   `s = re.sub(r"\{[a-z_]+\}", "", t).replace("top 5", "").replace("95%", "")`, depois `assert not re.search(r"\d", s), t`.
4. Linguagem: em `t.lower()` de `_todos()` não aparecem "compre", "oportunidade", "melhores ações", "recomendação", "http" nem "select".
5. O experimento deixa claro que é teste:
   - "teste de funcionamento" em `AJUDA["experimento"][1]`;
   - "não é o resultado do TCC" em `AJUDA["experimento"][1]`;
   - "teste de funcionamento" em `AJUDA["teste_funcionamento"][1].lower()`;
   - "nenhum botão que destranque" em `AJUDA["cadeado"][1]`.
6. Montagem: `a = montar_ajuda({"prazo": "09:45", "prazo_tardio": "12:00", "limite_historico": "10:00", "abertura": None, "lixo": "x"})`.
   - `set(a) == IDS`;
   - `a["prazo"] == {"titulo": "Prazo da rotina", "texto": "É o horário-limite para a coleta entregar os dados: 09:45, lido do arquivo de configuração (parametros.yaml). Sem entrega até lá, a rodada é registrada como \"falhou\" e só o arquivo da rodada é gravado, para o site avisar que os dados são do pregão anterior. A rotina continua tentando até 12:00, mas um top 5 feito depois de 10:00 não conta para o histórico do experimento."}`;
   - `"o prazo da rotina (09:45) e a abertura da bolsa (sem dados)" in a["linha_tempo"]["texto"]`.
7. `all("{" not in v["texto"] and "}" not in v["texto"] for v in montar_ajuda({}).values())`. `montar_ajuda(None)` também funciona.
8. O código-fonte de `ajuda.py` (`Path(ajuda.__file__).read_text(encoding="utf-8")`) não contém "SELECT", ".env" nem "executar_leitura".

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_ajuda.py`.

---

### FASE 2: leitores, relatorios, fixture yaml + testes (independente)

**2.1 Fixture `tests/dados/painel/raiz/processamento/config/parametros.yaml`.** Acrescente as chaves abaixo sem apagar nem mudar as que já existem. Mantenha `  prazo: "09:45"` e `fim: null` exatamente assim, porque `test_ler_prazo_rotina` e `test_producao_desabilita_a_rotina` fazem `replace` nesses textos. O arquivo final:
```yaml
corte_noite: "08:00"
treino:
  teste_final:
    inicio: "2026-06-23"
    fim: null
    liberado: false
  modelo_oficial: false
  acaso_sorteios: 10000
fase1:
  retorno_suspeito_min: -0.75
  retorno_suspeito_max: 1.0
  base_defasagem_max_pregoes: 5
fundamentos:
  pvp_minimo_plausivel: 0.05
saida:
  pasta: "saida"
  publicar_top_provisorio: false
  limite_valido_historico: "10:00"
rotina:
  pasta_logs: "logs"
  trava: "saida/estado/rotina.trava"
  trava_validade_horas: 6
  prazo: "09:45"
  prazo_tardio: "12:00"
  inicio_consulta: "08:00"
  intervalo_minutos: 5
```

**2.2 `leitores.py`.** Acrescente depois de `ler_prazo_rotina` (linha 134). Não mude `ler_parametros`, porque `test_painel_leitores.py:121` compara o dicionário inteiro.
```python
CHAVES_AJUDA = ("prazo", "prazo_tardio", "inicio_consulta", "intervalo", "limite_historico", "corte_noite",
                "retorno_min", "retorno_max", "defasagem", "pvp_min", "sorteios", "teste_final_inicio")


def _inteiro(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _hhmm_valido(v: object) -> str | None:
    return v if isinstance(v, str) and RE_HHMM.match(v) else None


def ler_valores_ajuda(raiz: Path) -> dict[str, str | None]:
    """Valores do parametros.yaml citados nos textos de ajuda, já formatados; None se faltar ou for inválido."""
    vazio: dict[str, str | None] = dict.fromkeys(CHAVES_AJUDA)
    caminho = Path(raiz) / "processamento" / "config" / "parametros.yaml"
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return vazio
    if not isinstance(dados, dict):
        return vazio
    rotina, saida, fase1 = _secao(dados, "rotina"), _secao(dados, "saida"), _secao(dados, "fase1")
    fund, treino = _secao(dados, "fundamentos"), _secao(dados, "treino")
    teste = _secao(treino, "teste_final")
    rmin, rmax = fase1.get("retorno_suspeito_min"), fase1.get("retorno_suspeito_max")
    intervalo, defas = rotina.get("intervalo_minutos"), fase1.get("base_defasagem_max_pregoes")
    pvp, sorteios = fund.get("pvp_minimo_plausivel"), treino.get("acaso_sorteios")
    inicio = teste.get("inicio")
    if isinstance(inicio, date):
        inicio = inicio.isoformat()
    try:
        tf = date.fromisoformat(inicio).strftime("%d/%m/%Y") if isinstance(inicio, str) else None
    except ValueError:
        tf = None
    return {
        "prazo": _hhmm_valido(rotina.get("prazo")),
        "prazo_tardio": _hhmm_valido(rotina.get("prazo_tardio")),
        "inicio_consulta": _hhmm_valido(rotina.get("inicio_consulta")),
        "intervalo": str(intervalo) if _inteiro(intervalo) else None,
        "limite_historico": _hhmm_valido(saida.get("limite_valido_historico")),
        "corte_noite": _hhmm_valido(dados.get("corte_noite")),
        "retorno_min": f"{round(rmin * 100):+d}%" if _numero(rmin) else None,
        "retorno_max": f"{round(rmax * 100):+d}%" if _numero(rmax) else None,
        "defasagem": str(defas) if _inteiro(defas) else None,
        "pvp_min": f"{pvp:g}".replace(".", ",") if _numero(pvp) else None,
        "sorteios": f"{sorteios:,}".replace(",", ".") if _inteiro(sorteios) else None,
        "teste_final_inicio": tf,
    }
```
`date` já está importado (linha 11). `RE_HHMM` existe (linha 22).

**2.3 `relatorios.py`.** Acrescente no fim do arquivo, mais o import no topo:
```python
from processamento.painel.leitores import duracao_segundos   # no topo, com os outros imports

CODIGOS_COMPLETOS = {"testes": {0, 1}}   # pytest com falhas também rodou até o fim


def duracao_ultima_acao(pasta_logs_painel: Path, acao_id: str, max_arquivos: int = 20) -> int | None:
    """Segundos da execução mais recente da ação, pelos logs do painel (cabeçalho inicio= e rodapé fim=).

    Ignora execução sem rodapé (em andamento ou interrompida), parada pelo painel (parado=sim)
    ou com código de saída de erro. None se nenhuma servir.
    """
    arquivos = [p for p in _listar(pasta_logs_painel)
                if p.name.startswith(acao_id + "-") and p.name.endswith(".log") and p.is_file()]
    for arquivo in sorted(arquivos, key=lambda p: p.name, reverse=True)[:max_arquivos]:
        inicio = fim = codigo = None
        parado = False
        for linha in _ler_texto(arquivo).splitlines():
            m = RE_PYTEST_INICIO.match(linha)
            if m and inicio is None:
                inicio = m.group(1)
                continue
            m = RE_PYTEST_FIM.match(linha)
            if m:
                fim, codigo, parado = m.group(1), int(m.group(2)), "parado=sim" in linha
        if inicio is None or fim is None or parado or codigo not in CODIGOS_COMPLETOS.get(acao_id, {0}):
            continue
        segundos = duracao_segundos(inicio, fim)
        if segundos is not None:
            return segundos
    return None


def duracoes_painel(pasta_logs_painel: Path, ids: list[str]) -> dict[str, int | None]:
    """{id da ação: segundos da última execução completa pelo painel, ou None}."""
    return {acao_id: duracao_ultima_acao(pasta_logs_painel, acao_id) for acao_id in ids}
```
`RE_PYTEST_INICIO` (linha 24) é genérico (`acao=\S+`), então serve para as 4 ações.

**2.4 Testes.**

Em `tests/test_painel_leitores.py`, acrescente dois testes:
- `test_ler_valores_ajuda_da_fixture(tmp_path)`: com `raiz = montar_raiz(tmp_path)`, `leitores.ler_valores_ajuda(raiz) == {"prazo": "09:45", "prazo_tardio": "12:00", "inicio_consulta": "08:00", "intervalo": "5", "limite_historico": "10:00", "corte_noite": "08:00", "retorno_min": "-75%", "retorno_max": "+100%", "defasagem": "5", "pvp_min": "0,05", "sorteios": "10.000", "teste_final_inicio": "23/06/2026"}`.
- `test_ler_valores_ajuda_invalidos_e_ausente(tmp_path)`:
  - troque no yaml da raiz `'prazo_tardio: "12:00"'` por `"prazo_tardio: 12:00"` e `"intervalo_minutos: 5"` por `"intervalo_minutos: true"`;
  - confira `v["prazo_tardio"] is None`, `v["intervalo"] is None` e `v["prazo"] == "09:45"`;
  - depois `caminho.unlink()` → `ler_valores_ajuda(raiz) == dict.fromkeys(leitores.CHAVES_AJUDA)`.

Em `tests/test_painel_relatorios.py`, acrescente `test_duracao_ultima_acao_e_duracoes_painel(tmp_path)`. Comece com `raiz = montar_raiz(tmp_path)` e `pasta = raiz / "logs" / "painel"`.
1. `relatorios.duracao_ultima_acao(pasta, "testes") == 96`. O log mais novo da fixture vai de 10:15:00 a 10:16:36, código 0.
2. Escreva `pasta / "testes-2026-10-25_080000.log"` com:
   `"# painel: acao=testes inicio=2026-10-25T08:00:00-03:00 comando=python -m pytest -q\n# painel: fim=2026-10-25T08:00:10-03:00 codigo=1 parado=sim\n"`.
   Confira que continua `== 96`.
3. Escreva `diagnostico-2026-10-24_120000.log` com:
   `"# painel: acao=diagnostico inicio=2026-10-24T12:00:00-03:00 comando=python -m processamento.diagnostico\nok\n# painel: fim=2026-10-24T12:02:05-03:00 codigo=0\n"`.
   Escreva `diagnostico-2026-10-25_090000.log` com:
   `"# painel: acao=diagnostico inicio=2026-10-25T09:00:00-03:00 comando=python -m processamento.diagnostico\n# painel: fim=2026-10-25T09:00:03-03:00 codigo=3\n"`.
   Confira `duracao_ultima_acao(pasta, "diagnostico") == 125`.
4. Escreva `carga-2026-10-25_100000.log` só com o cabeçalho: `"# painel: acao=carga inicio=2026-10-25T10:00:00-03:00 comando=python -m processamento.saida --data 2026-10-23 --completo\nrodando\n"`. Confira que dá `None`.
5. `duracao_ultima_acao(pasta, "rotina") is None` e `duracao_ultima_acao(tmp_path / "nao_existe", "testes") is None`.
6. `relatorios.duracoes_painel(pasta, ["rotina", "carga", "diagnostico", "testes"]) == {"rotina": None, "carga": None, "diagnostico": 125, "testes": 96}`.

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_leitores.py tests/test_painel_relatorios.py`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`. Os testes de servidor e saúde devem continuar passando com a fixture yaml nova.

---

### FASE 3: `visao.py` + `tests/test_painel_visao.py` (depois da Fase 1)

Acrescente os imports no topo de `visao.py`:
```python
from processamento.painel.acoes import ACOES
from processamento.painel.ajuda import O_QUE_FAZER
```

Acrescente no fim do arquivo:
```python
TEXTO_SEM_MEDICAO = "Ainda sem medição: pode levar alguns minutos."
ROTULO_EXECUCAO = {"rotina": "A última rotina diária", "carga": "A última carga completa"}


def _dic(valor: object) -> dict:
    return valor if isinstance(valor, dict) else {}


def _inteiro(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _ponto(nivel: str, texto: str, alvo: str, chave: str) -> dict:
    return {"nivel": nivel, "texto": texto, "alvo": alvo, "o_que_fazer": O_QUE_FAZER.get(chave)}


def pontos_de_atencao(hoje: object, trava: object, fluxo_dia: object, linha_tempo: object,
                      saude_visao: object, testes: object) -> list[dict]:
    """Faróis amarelos (warn) e vermelhos (bad) da tela, na ordem em que aparecem na página."""
    hoje, trava, fluxo_dia, linha_tempo, saude_visao, testes = (
        _dic(v) for v in (hoje, trava, fluxo_dia, linha_tempo, saude_visao, testes))
    pontos: list[dict] = []
    if fluxo_dia.get("disponivel") is True:
        coleta = _dic(fluxo_dia.get("coleta"))
        if coleta.get("estado") in ("warn", "bad"):
            titulo = str(coleta.get("titulo") or "sem dados").lower()
            pontos.append(_ponto(coleta["estado"], f"Coleta ({titulo})", "fluxo-coleta", "coleta_" + coleta["estado"]))
        d = _data(fluxo_dia.get("data"))
        dia = d.strftime("%d/%m/%Y") if d else "sem data"
        status = fluxo_dia.get("status")
        if status == "falhou":
            pontos.append(_ponto("bad", f"Última rotina diária ({dia}) falhou", "fluxo-processamento", "rotina_falhou"))
        elif status == "parcial":
            pontos.append(_ponto("warn", f"Última rotina diária ({dia}) com pendências", "fluxo-processamento",
                                 "rotina_parcial"))
        elif status == "em_andamento" and fluxo_dia.get("possivelmente_interrompida"):
            pontos.append(_ponto("warn", f"Última rotina diária ({dia}) pode ter sido interrompida",
                                 "fluxo-processamento", "rotina_interrompida"))
    else:
        pontos.append(_ponto("warn", "Fluxo do dia: sem dados", "agora", "sem_rotina"))
    folga = linha_tempo.get("folga_s")
    if _inteiro(folga) and folga < 0:
        pontos.append(_ponto("warn", f"Rotina terminou depois do prazo ({linha_tempo.get('folga_texto')})",
                             "linha-tempo", "atraso_prazo"))
    if saude_visao.get("disponivel") is True:
        for c in saude_visao.get("cartoes") or []:
            c = _dic(c)
            farol, id_ = c.get("farol"), c.get("id")
            if not isinstance(id_, str):
                continue
            texto = f"{c.get('titulo')} ({c.get('numero')})"
            if farol in ("warn", "bad"):
                pontos.append(_ponto(farol, texto, f"saude-c-{id_}", f"saude_{id_}"))
            elif farol == "idle":
                pontos.append(_ponto("warn", texto, f"saude-c-{id_}", "saude_sem_dados"))
    else:
        pontos.append(_ponto("warn", "Saúde dos dados: sem diagnóstico", "saude", "saude_sem_diagnostico"))
    if hoje.get("erro") or hoje.get("disponivel") is False:
        pontos.append(_ponto("bad", "Calendário da B3 com erro", "historico", "calendario_erro"))
    if testes.get("disponivel") is True:
        contagens = _dic(testes.get("contagens"))
        falhas = sum(v for k, v in contagens.items() if k in ("failed", "errors") and _inteiro(v))
        if testes.get("interrompido"):
            pontos.append(_ponto("warn", "Testes automáticos interrompidos", "testes", "testes_interrompidos"))
        elif testes.get("aprovado") is False and falhas > 0:
            pontos.append(_ponto("bad", f"Testes automáticos com falhas ({_plural(falhas, 'falha', 'falhas')})",
                                 "testes", "testes_falhas"))
        elif testes.get("aprovado") is False:
            pontos.append(_ponto("warn", "Testes automáticos sem resultado completo", "testes", "testes_interrompidos"))
    if trava.get("abandonada") is True:
        idade = trava.get("idade_min")
        texto = f"Trava da rotina esquecida ({idade} min)" if _inteiro(idade) else "Trava da rotina esquecida"
        pontos.append(_ponto("warn", texto, "comandos", "trava_abandonada"))
    return pontos


def resumo(hoje: object, trava: object, fluxo_dia: object, linha_tempo: object,
           saude_visao: object, testes: object) -> dict:
    """Frase única do topo ("Tudo certo", "Atenção: N pontos" ou "Falhou: ...") e a lista de pontos."""
    pontos = pontos_de_atencao(hoje, trava, fluxo_dia, linha_tempo, saude_visao, testes)
    ruins = [p for p in pontos if p["nivel"] == "bad"]
    atencao = [p for p in pontos if p["nivel"] == "warn"]
    if ruins:
        frase = "Falhou: " + "; ".join(p["texto"] for p in ruins)
        if atencao:
            frase += " · e " + _plural(len(atencao), "ponto de atenção", "pontos de atenção")
        nivel = "bad"
    elif atencao:
        frase, nivel = "Atenção: " + _plural(len(atencao), "ponto", "pontos"), "warn"
    else:
        frase, nivel = "Tudo certo", "ok"
    return {"nivel": nivel, "frase": frase, "pontos": pontos}


def tempo_curto(segundos: object) -> str | None:
    """Tempo arredondado para o botão: "menos de um minuto", "~2 min", "~1 h 30 min"; None se não houver."""
    if not _inteiro(segundos) or segundos < 0:
        return None
    if segundos < 60:
        return "menos de um minuto"
    minutos = (segundos + 30) // 60
    if minutos < 60:
        return f"~{minutos} min"
    return f"~{minutos // 60} h {minutos % 60} min"


def tempos_acoes(duracoes_painel: object, rotina: object, completa: object) -> dict[str, dict]:
    """Tempo de cada ação: log do painel; senão execucao.json (rotina e carga ok/parcial); senão sem medição."""
    duracoes = _dic(duracoes_painel)
    itens = {"rotina": _dic(rotina), "carga": _dic(completa)}
    saida: dict[str, dict] = {}
    for acao_id in ACOES:
        s = duracoes.get(acao_id)
        if _inteiro(s) and s >= 0:
            saida[acao_id] = {"segundos": s, "curto": tempo_curto(s),
                              "texto": f"Da última vez, pelo painel, levou {formatar_duracao(s)}.", "origem": "painel"}
            continue
        item = itens.get(acao_id, {})
        s = item.get("duracao_s")
        if item.get("legivel") and item.get("status") in ("ok", "parcial") and _inteiro(s) and s >= 0:
            saida[acao_id] = {"segundos": s, "curto": tempo_curto(s),
                              "texto": f"{ROTULO_EXECUCAO[acao_id]} levou {formatar_duracao(s)}.", "origem": "execucao"}
        else:
            saida[acao_id] = {"segundos": None, "curto": None, "texto": TEXTO_SEM_MEDICAO, "origem": None}
    return saida


def hora_marco(linha_tempo: object, id_: str) -> str | None:
    """Hora (HH:MM) do marco `id_` da linha do tempo; None se não houver."""
    for m in _dic(linha_tempo).get("marcos") or []:
        if isinstance(m, dict) and m.get("id") == id_ and isinstance(m.get("hora"), str):
            return m["hora"]
    return None
```

Testes em `tests/test_painel_visao.py`. Reaproveite `ITEM`, `ITEM_MANHA` e `COMPLETA`, que já existem no arquivo, e acrescente:
```python
from processamento.painel.acoes import ACOES
from processamento.painel.ajuda import O_QUE_FAZER
from processamento.painel.saude import cartoes_saude
from processamento.painel.visao import hora_marco, resumo, tempo_curto, tempos_acoes

FIXTURE_DIAG = Path(__file__).resolve().parent / "dados" / "painel" / "diagnostico_completo.md"
HOJE_OK = {"data": "2026-10-23", "dia_semana": "sexta", "pregao": True, "motivo": None, "erro": None}
TRAVA_VAZIA = {"existe": False, "ativa": False, "abandonada": False, "idade_min": None}
TESTES_OK = {"disponivel": True, "aprovado": True, "interrompido": False, "contagens": {"passed": 1700}}
SAUDE_OK = {"disponivel": True, "cartoes": [{"id": "contrato", "titulo": "Contrato com a coleta",
                                             "farol": "ok", "numero": "0 divergências"}]}
LT = linha_do_tempo(ITEM, "09:45")   # rotina em outro dia: folga None
```
Casos e valores esperados:

1. **Tudo certo:** `resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, SAUDE_OK, TESTES_OK) == {"nivel": "ok", "frase": "Tudo certo", "pontos": []}`.
2. **Atenção com os cartões da fixture:** `r = resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), LT, cartoes_saude(FIXTURE_DIAG), TESTES_OK)`.
   - `r["nivel"] == "warn"` e `r["frase"] == "Atenção: 4 pontos"`;
   - textos: `["Quantidade de ações (19 empresas)", "Preços suspeitos (5 retornos)", "Lacunas nas séries (3 lacunas)", "Horário das notícias (90,8% sem hora real)"]`;
   - alvos: `["saude-c-quantidade_acoes", "saude-c-retornos", "saude-c-lacunas", "saude-c-horario_noticias"]`;
   - `r["pontos"][0]["o_que_fazer"] == O_QUE_FAZER["saude_quantidade_acoes"]`.
3. **Falhou com atenção:** `resumo(HOJE_OK, TRAVA_VAZIA, fluxo(dict(ITEM, status="falhou", n_pacotes=0, pacotes=[])), LT, cartoes_saude(FIXTURE_DIAG), TESTES_OK)`.
   - `["frase"] == "Falhou: Última rotina diária (23/10/2026) falhou · e 4 pontos de atenção"`;
   - `["pontos"][0] == {"nivel": "bad", "texto": "Última rotina diária (23/10/2026) falhou", "alvo": "fluxo-processamento", "o_que_fazer": O_QUE_FAZER["rotina_falhou"]}`.
4. **Singular e parcial:** com `fluxo(dict(ITEM, status="parcial"))` e `SAUDE_OK`:
   - frase `"Atenção: 1 ponto"`;
   - `pontos == [{"nivel": "warn", "texto": "Última rotina diária (23/10/2026) com pendências", "alvo": "fluxo-processamento", "o_que_fazer": O_QUE_FAZER["rotina_parcial"]}]`.
5. **Interrompida:** `fluxo(dict(ITEM, status="em_andamento", possivelmente_interrompida=True))` gera o ponto com texto `"Última rotina diária (23/10/2026) pode ter sido interrompida"` e chave `rotina_interrompida`.
6. **Coleta com problema:** `coleta = {"consultado": True, "motivo": "entrega_falhou", "iniciada_em": "2026-10-23T08:00:01-03:00"}` e `fluxo(dict(ITEM, coleta=coleta, status="falhou", n_pacotes=0, pacotes=[]))`, com `SAUDE_OK`.
   - frase `"Falhou: Coleta (entrega com problema); Última rotina diária (23/10/2026) falhou"`;
   - `pontos[0] == {"nivel": "bad", "texto": "Coleta (entrega com problema)", "alvo": "fluxo-coleta", "o_que_fazer": O_QUE_FAZER["coleta_bad"]}`.
7. **Atraso no prazo:** `lt = linha_do_tempo(dict(ITEM_MANHA, inicio="2026-10-23T09:50:00-03:00", fim="2026-10-23T09:52:30-03:00"), "09:45")` e `resumo(HOJE_OK, TRAVA_VAZIA, fluxo(ITEM), lt, SAUDE_OK, TESTES_OK)["pontos"] == [{"nivel": "warn", "texto": "Rotina terminou depois do prazo (atraso de 7 min 30 s)", "alvo": "linha-tempo", "o_que_fazer": O_QUE_FAZER["atraso_prazo"]}]`.
8. **Testes:**
   - `{"disponivel": True, "aprovado": False, "interrompido": False, "contagens": {"failed": 2, "passed": 1698}}` → frase `"Falhou: Testes automáticos com falhas (2 falhas)"`, alvo `"testes"`, chave `testes_falhas`;
   - `contagens {"failed": 1}` → texto `"Testes automáticos com falhas (1 falha)"`;
   - `contagens {}` com `aprovado False` → warn, `"Testes automáticos sem resultado completo"`;
   - `{"disponivel": True, "aprovado": None, "interrompido": True, "contagens": {}}` → warn, `"Testes automáticos interrompidos"`;
   - `{"disponivel": False, "motivo": "x"}` → nenhum ponto.
9. **Trava, calendário e saúde indisponível:** `resumo({"erro": "feriados inválidos"}, {"abandonada": True, "idade_min": 420}, fluxo(ITEM), LT, {"disponivel": False, "motivo": "x"}, TESTES_OK)`.
   - pontos == `[{"nivel": "warn", "texto": "Saúde dos dados: sem diagnóstico", "alvo": "saude", "o_que_fazer": O_QUE_FAZER["saude_sem_diagnostico"]}, {"nivel": "bad", "texto": "Calendário da B3 com erro", "alvo": "historico", "o_que_fazer": O_QUE_FAZER["calendario_erro"]}, {"nivel": "warn", "texto": "Trava da rotina esquecida (420 min)", "alvo": "comandos", "o_que_fazer": O_QUE_FAZER["trava_abandonada"]}]`;
   - frase `"Falhou: Calendário da B3 com erro · e 2 pontos de atenção"`.
10. **Cartão cinza conta:** saúde `{"disponivel": True, "cartoes": [{"id": "retornos", "titulo": "Preços suspeitos", "farol": "idle", "numero": "sem dados"}]}` → `pontos == [{"nivel": "warn", "texto": "Preços suspeitos (sem dados)", "alvo": "saude-c-retornos", "o_que_fazer": O_QUE_FAZER["saude_sem_dados"]}]`.
11. **Nada não quebra:** `r = resumo(None, None, None, None, None, None)` → `r["frase"] == "Atenção: 2 pontos"` e `[p["texto"] for p in r["pontos"]] == ["Fluxo do dia: sem dados", "Saúde dos dados: sem diagnóstico"]`.
12. **`tempo_curto`:**

    | Entrada | Saída |
    |---|---|
    | `None` | `None` |
    | `True` | `None` |
    | `-1` | `None` |
    | `45` | `"menos de um minuto"` |
    | `89` | `"~1 min"` |
    | `90` | `"~2 min"` |
    | `96` | `"~2 min"` |
    | `180` | `"~3 min"` |
    | `295` | `"~5 min"` |
    | `3599` | `"~1 h 0 min"` |
    | `5400` | `"~1 h 30 min"` |

13. **`tempos_acoes` prefere o log do painel:** `tempos_acoes({"rotina": 75, "carga": None, "diagnostico": None, "testes": 295}, dict(ITEM, duracao_s=118), dict(COMPLETA, duracao_s=180)) ==`
```python
{"rotina": {"segundos": 75, "curto": "~1 min", "texto": "Da última vez, pelo painel, levou 1 min 15 s.", "origem": "painel"},
 "carga": {"segundos": 180, "curto": "~3 min", "texto": "A última carga completa levou 3 min 0 s.", "origem": "execucao"},
 "diagnostico": {"segundos": None, "curto": None, "texto": "Ainda sem medição: pode levar alguns minutos.", "origem": None},
 "testes": {"segundos": 295, "curto": "~5 min", "texto": "Da última vez, pelo painel, levou 4 min 55 s.", "origem": "painel"}}
```
14. **`tempos_acoes` ignora o que falhou:** `tempos_acoes({}, dict(ITEM, status="falhou", duracao_s=0), dict(COMPLETA, status="em_andamento", duracao_s=None))` deixa rotina e carga com `origem None` e o texto de sem medição. `tempos_acoes(None, None, None)` tem chaves `== set(ACOES)`, todas com `"segundos": None`.
15. **`hora_marco`:** `hora_marco(linha_do_tempo(ITEM_MANHA, "09:45"), "abertura") == "10:00"`, `hora_marco(None, "abertura") is None`, `hora_marco({"disponivel": False}, "prazo") is None`.

O teste que já existe, `test_visao_nao_importa_banco_nem_configuracao_secreta`, precisa continuar passando: `visao.py` não pode ter "SELECT" nem "dotenv".

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_visao.py`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`.

---

### FASE 4: `servidor.py` + `tests/test_painel_servidor.py` (depois de 1, 2 e 3)

**4.1 Import e CSP.** Linha 21: `from processamento.painel import acoes, ajuda, leitores, marcos, relatorios, saude, visao`. Linhas 27-30:
```python
CSP_PAGINA = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
```

**4.2 `montar_painel` (linhas 131-170).** Antes do `return`, calcule as partes da visão em variáveis e reaproveite-as. As outras chaves continuam iguais.
```python
    completa_item = leitores.ultima_execucao(itens_completas)
    pasta_painel = raiz / params["pasta_logs"] / "painel"
    testes = _seguro(relatorios.ler_ultimo_pytest, pasta_painel)
    fluxo_v = _seguro(visao.fluxo, agora_item, completa_item)
    linha_v = _seguro(visao.linha_do_tempo, agora_item, leitores.ler_prazo_rotina(raiz), caminho_calendario)
    saude_v = _seguro(saude.cartoes_saude, raiz / "docs" / "diagnostico_banco.md")
    duracoes = _seguro(relatorios.duracoes_painel, pasta_painel, list(acoes.ACOES))
    valores_ajuda = {**_seguro(leitores.ler_valores_ajuda, raiz), "abertura": visao.hora_marco(linha_v, "abertura")}
```
No dicionário devolvido:
- `"testes": testes`;
- em `"visao"`, use `"fluxo": fluxo_v`, `"linha_tempo": linha_v`, `"saude": saude_v` e mantenha `"calendario"` como está;
- acrescente:
```python
            "resumo": _seguro(visao.resumo, hoje, trava, fluxo_v, linha_v, saude_v, testes),
            "tempos": _seguro(visao.tempos_acoes, duracoes, agora_item, completa_item),
            "ajuda": _seguro(ajuda.montar_ajuda, valores_ajuda),
```

**4.3 Testes em `tests/test_painel_servidor.py`.**
1. **Muda** `test_api_painel_visao_com_as_fixtures`, linha 190: `assert set(dados["visao"]) == {"fluxo", "linha_tempo", "saude", "calendario", "resumo", "tempos", "ajuda"}`.
2. **Novo** `test_api_painel_resumo_tempos_e_ajuda(srv)`:
   - `r = dados["visao"]["resumo"]`;
   - `r["nivel"] == "bad"` e `r["frase"] == "Falhou: Contrato com a coleta (2 divergências) · e 5 pontos de atenção"`;
   - `[p["alvo"] for p in r["pontos"]] == ["saude-c-contrato", "saude-c-quantidade_acoes", "saude-c-retornos", "saude-c-lacunas", "saude-c-horario_noticias", "saude-c-cobertura"]`;
   - `r["pontos"][0]["o_que_fazer"] == ajuda.O_QUE_FAZER["saude_contrato"]`;
   - `r["pontos"][1]["texto"] == "Quantidade de ações (sem dados)"` e `r["pontos"][1]["o_que_fazer"] == ajuda.O_QUE_FAZER["saude_sem_dados"]`;
   - `dados["visao"]["tempos"] ==`
```python
     {"rotina": {"segundos": 118, "curto": "~2 min", "texto": "A última rotina diária levou 1 min 58 s.", "origem": "execucao"},
      "carga": {"segundos": 180, "curto": "~3 min", "texto": "A última carga completa levou 3 min 0 s.", "origem": "execucao"},
      "diagnostico": {"segundos": None, "curto": None, "texto": "Ainda sem medição: pode levar alguns minutos.", "origem": None},
      "testes": {"segundos": 96, "curto": "~2 min", "texto": "Da última vez, pelo painel, levou 1 min 36 s.", "origem": "painel"}}
```
   - `a = dados["visao"]["ajuda"]`;
   - `set(a) == set(ajuda.AJUDA)`;
   - `a["prazo"]["texto"] == ajuda.AJUDA["prazo"][1].format(prazo="09:45", prazo_tardio="12:00", limite_historico="10:00")`;
   - `"(09:45)" in a["linha_tempo"]["texto"]` e `"(10:00)" in a["linha_tempo"]["texto"]`;
   - `all("{" not in v["texto"] and "sem dados" not in v["texto"] for v in a.values())`. Todos os campos existem na fixture yaml, e a abertura de 23/10 é 10:00.
3. **Acréscimo** em `test_trava_abandonada_nao_bloqueia`:
   - `r = dados["visao"]["resumo"]`;
   - `r["pontos"][-1] == {"nivel": "warn", "texto": "Trava da rotina esquecida (420 min)", "alvo": "comandos", "o_que_fazer": ajuda.O_QUE_FAZER["trava_abandonada"]}`;
   - `r["frase"].endswith("· e 6 pontos de atenção")`.
4. **Acréscimo** em `test_get_raiz_serve_pagina_com_token_e_csp`:
   - `cab["content-security-policy"] == CSP_PAGINA`;
   - `"img-src data:" in CSP_PAGINA`;
   - `"http" not in CSP_PAGINA`;
   - importe `CSP_PAGINA` de `processamento.painel.servidor`.
5. **Novo** `test_campos_da_ajuda_batem_com_o_yaml(tmp_path)`: `set(leitores.ler_valores_ajuda(montar_raiz(tmp_path))) | {"abertura"} == ajuda.CAMPOS`.

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_servidor.py`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`.

---

### FASE 5a: `pagina.html` (layout, logo, favicon, seções numeradas) + `test_painel_pagina.py` (independente)

**CSS** (bloco `<style>`, linhas 7-202):

Troque a linha 31 (`.wrap{…}`) por:
```css
.wrap{margin:0;padding-block:18px 48px;padding-left:max(clamp(16px,2.2vw,40px), env(safe-area-inset-left, 0px));padding-right:max(clamp(16px,2.2vw,40px), env(safe-area-inset-right, 0px));display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:22px 20px;align-items:start}
.wrap > *{grid-column:1 / -1;min-width:0}
.secao{display:grid;gap:10px;align-content:start;min-width:0}
.secao-tit{font-size:1.15rem;font-weight:700;display:flex;align-items:center;gap:10px}
.secao-tit .num{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;font-size:.9rem;font-family:var(--f-mono)}
.card-tit{font-size:1.02rem;font-weight:600}
.tit-linha{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}
.faixa{display:grid;gap:18px;grid-template-columns:minmax(0,1fr);align-items:stretch}
.card{container-type:inline-size}
[tabindex="-1"]:focus{outline:2px solid var(--accent);outline-offset:3px}
@media (min-width:1280px){
  .wrap > #sec-experimento{grid-column:span 7}
  .wrap > #sec-historico{grid-column:span 5}
  .faixa-fluxo{grid-template-columns:minmax(0,7fr) minmax(0,5fr)}
  .faixa-acoes{grid-template-columns:minmax(0,8fr) minmax(0,4fr)}
}
@media (max-width:599px){.tl{margin:6px 24px 0}.card{padding:14px}}
```
- No bloco "topo" (linhas 49-58), troque `.top{…}` por:
  - `.top{display:grid;gap:14px}`;
  - `.barra{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between}`;
  - `.logo{display:flex;align-items:center;gap:10px;color:var(--accent);font-weight:700;font-size:1rem}`;
  - `.logo-ic{width:32px;height:32px;flex:none}`;
  - `.logo-txt{color:var(--ink)}`.
  - Mantenha `.cabeca`, `.sub`, `.state` e `.toggle`.
- Linha 71: troque `@media (max-width:820px){.flow…}` por `@container (max-width:640px){.flow{grid-template-columns:1fr}.arrow{transform:rotate(90deg);justify-self:center}}`.
- Linha 72: troque `#carga-linha{…}` por `.linha-ajuda{font-size:.8rem;color:var(--muted);display:flex;align-items:center;gap:6px;flex-wrap:wrap}`.
- Linha 126 (`.health`): troque por:
```css
.health{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}
@media (min-width:600px){.health{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:900px){.health{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (min-width:1700px){.health{grid-template-columns:repeat(6,minmax(0,1fr))}}
```
- Linha 137: troque `@media (max-width:820px){.exp…}` por `@container (max-width:720px){.exp{grid-template-columns:1fr}}`.
- Linhas 159-160: apague `.two{…}` e o `@media` dele.

**HTML:** troque o corpo das linhas 207–357, de `<div class="wrap">` até `</footer>`, pelo esqueleto abaixo.

Nele, `AJ(x)` significa exatamente:
`<button class="ajuda-btn" type="button" data-ajuda="x" aria-label="Ajuda" aria-expanded="false" aria-controls="ajuda-caixa" hidden>?</button>`

São **14** usos de `AJ(...)`. Os trechos marcados "(igual)" devem ser copiados do arquivo atual sem mudança.
```html
<div class="wrap" id="topo">
  <header class="top">
    <div class="barra">
      <div class="logo">
        <svg id="logo-ic" class="logo-ic" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
          <rect x="8" y="8" width="16" height="16" rx="3" fill="none" stroke="currentColor" stroke-width="2"/>
          <rect x="12.5" y="12.5" width="7" height="7" rx="1.5" fill="currentColor"/>
          <path d="M12 3v4M16 3v4M20 3v4M12 25v4M16 25v4M20 25v4M3 12h4M3 16h4M3 20h4M25 12h4M25 16h4M25 20h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span class="logo-txt">Interface do Processamento</span>
      </div>
      <div class="state"> (igual: pill-geral, pill-hoje, botões tema e btn-atualizar) </div>
    </div>
    <div class="cabeca">
      <h1>Sala de Operação</h1>
      <p class="sub">(igual)</p>
      <p class="note" id="atualizado"></p>
    </div>
  </header>
  <div id="erro-rede" class="erro-rede" hidden>Painel sem resposta</div>

  <section class="secao" id="sec-resumo" aria-labelledby="h-sec-resumo">
    <div class="tit-linha"><h2 class="secao-tit" id="h-sec-resumo"><span class="num">1</span> Resumo</h2>AJ(resumo)</div>
    <div class="card resumo idle" id="resumo">
      <button type="button" class="resumo-frase" id="resumo-frase" disabled>carregando…</button>
      <ul class="resumo-lista" id="resumo-lista"></ul>
    </div>
  </section>

  <section class="secao" id="sec-fluxo" aria-labelledby="h-sec-fluxo">
    <h2 class="secao-tit" id="h-sec-fluxo"><span class="num">2</span> Fluxo do dia</h2>
    <div class="faixa faixa-fluxo">
      <section class="card" id="agora" aria-labelledby="h-fluxo">
        <div class="cardhead">
          <div class="tit-linha"><h3 class="card-tit" id="h-fluxo">Última atualização</h3>AJ(fluxo)</div>
          <span class="pill idle" id="pill-fluxo">carregando…</span>
        </div>
        <div class="flow" id="fluxo"></div>
        <p class="note" id="fluxo-vazio" hidden></p>
        <p class="linha-ajuda"><span id="carga-linha">última carga completa: sem dados</span>AJ(carga_vs_rotina)</p>
        <p class="fazer" data-fazer="agora" hidden></p>
      </section>
      <section class="card" id="linha-tempo" aria-labelledby="h-tl">
        <div class="cardhead"><div class="tit-linha"><h3 class="card-tit" id="h-tl">A manhã do pregão</h3>AJ(linha_tempo)</div></div>
        <div class="tit-linha"><p class="why" id="tl-why"></p>AJ(prazo)</div>
        <div class="tl" id="tl" aria-label="Linha do tempo da manhã do pregão"></div>
        <div class="legend">
          <span><i class="lg-accent"></i>Coleta trabalhando</span>
          <span><i class="lg-ok"></i>Processamento</span>
          <span><i class="lg-folga"></i>Folga até o prazo AJ(folga)</span>
        </div>
        <p class="note" id="tl-avisos" hidden></p>
        <p class="fazer" data-fazer="linha-tempo" hidden></p>
      </section>
    </div>
  </section>

  <section class="secao" id="sec-saude" aria-labelledby="h-saude">
    <div class="tit-linha"><h2 class="secao-tit" id="h-saude"><span class="num">3</span> Saúde dos dados</h2>AJ(saude)</div>
    <section class="card" id="saude" aria-labelledby="h-saude">
      <p class="why">(igual: "O processamento confere os dados da coleta…")</p>
      <p class="note" id="saude-gerado"></p>
      <div class="health" id="saude-cartoes"></div>
      <p class="fazer" data-fazer="saude" hidden></p>
      <details><summary>Ver o diagnóstico completo</summary><div id="saude-completa"></div></details>
    </section>
  </section>

  <section class="secao" id="sec-experimento" aria-labelledby="h-sec-experimento">
    <h2 class="secao-tit" id="h-sec-experimento"><span class="num">4</span> Experimento</h2>
    <section class="card" id="experimento" aria-labelledby="h-exp">
      <div class="cardhead">
        <div class="tit-linha"><h3 class="card-tit" id="h-exp">Experimento: top 5 com maior chance de superar o Ibovespa</h3>AJ(experimento)</div>
        <div class="tit-linha"><span class="banner" id="faixa-teste">TESTE DE FUNCIONAMENTO, NÃO É RESULTADO</span>AJ(teste_funcionamento)</div>
      </div>
      (igual: <p class="why">, <div class="exp"> inteiro), com 3 mudanças:
        - no .lock, troque <div><h3 id="lock-t">Teste final</h3><p ...></div> por
          <div><div class="tit-linha"><h3 id="lock-t">Teste final</h3>AJ(cadeado)</div><p class="note" id="lock-p"></p></div>
        - troque <h3>Acerto do top 5 no desenvolvimento</h3> por
          <div class="tit-linha"><h3>Acerto do top 5 no desenvolvimento</h3>AJ(grafico)</div>
        - na legenda: <span><i class="lg-track"></i>faixa cinza = acaso (95% dos sorteios) AJ(faixa_acaso)</span>
    </section>
  </section>

  <section class="secao" id="sec-historico" aria-labelledby="h-sec-historico">
    <h2 class="secao-tit" id="h-sec-historico"><span class="num">5</span> Histórico</h2>
    <section class="card" id="historico" aria-labelledby="h-hist">
      <div class="cardhead">
        <div class="tit-linha"><h3 class="card-tit" id="h-hist">Histórico de execuções</h3>AJ(historico)</div>
        (igual: <div class="navmes">…</div>)
      </div>
      (igual: #cal, legenda, p.why, #hist-tabela, #detalhe, p.note)
      <p class="fazer" data-fazer="historico" hidden></p>
      (igual: <details id="etapas">…</details>)
    </section>
  </section>

  <section class="secao" id="sec-acoes" aria-labelledby="h-sec-acoes">
    <h2 class="secao-tit" id="h-sec-acoes"><span class="num">6</span> Ações</h2>
    <div class="faixa faixa-acoes">
      <section class="card" id="comandos" aria-labelledby="h-sec-acoes">
        <p class="why">Cada botão chama um comando do projeto. Nenhum escreve no banco da coleta.</p>
        <p class="fazer" data-fazer="comandos" hidden></p>
        <div class="actions" id="botoes"></div>
        (igual: <div class="run" id="run" hidden>…</div> inteiro)
      </section>
      <section class="card" id="testes" aria-labelledby="h-test">
        <div class="cardhead"><div class="tit-linha"><h3 class="card-tit" id="h-test">Testes automáticos</h3>AJ(testes)</div><span class="pill idle" id="pill-testes">carregando…</span></div>
        <div class="tests" id="testes-corpo"></div>
        <p class="fazer" data-fazer="testes" hidden></p>
      </section>
    </div>
  </section>
</div>

<footer class="wrap" style="padding-top:0"> (igual) </footer>

<div id="ajuda-caixa" class="ajuda-caixa" role="tooltip" hidden>
  <p class="ajuda-tit" id="ajuda-titulo"></p>
  <p class="ajuda-txt" id="ajuda-texto" aria-live="polite"></p>
</div>
```

**JS:** logo depois de `try { aplicarTema(localStorage.getItem(CHAVE_TEMA)); } catch (e) {}` (linha 1233), acrescente:
```js
// Ícone da aba: o mesmo SVG da logo, serializado (o XMLSerializer põe o xmlns sozinho).
function instalarFavicon() {
  const icone = $("logo-ic");
  if (!icone || typeof XMLSerializer === "undefined") return;
  const copia = icone.cloneNode(true);
  copia.removeAttribute("id");
  copia.removeAttribute("class");
  copia.setAttribute("width", "64");
  copia.setAttribute("height", "64");
  copia.setAttribute("color", "#1f5fd1");
  const link = document.createElement("link");
  link.rel = "icon";
  link.type = "image/svg+xml";
  link.href = "data:image/svg+xml," + encodeURIComponent(new XMLSerializer().serializeToString(copia));
  document.head.appendChild(link);
}
```
Na última linha do script (`carregarPainel();`, linha 1390), ponha `instalarFavicon();` antes dela.

**Testes novos em `test_painel_pagina.py`.** Os existentes ficam todos.
1. `test_secoes_numeradas_na_ordem_de_leitura`:
   - as posições de `'id="sec-resumo"'`, `'id="sec-fluxo"'`, `'id="sec-saude"'`, `'id="sec-experimento"'`, `'id="sec-historico"'` e `'id="sec-acoes"'` estão em ordem crescente;
   - para `(1, "Resumo"), (2, "Fluxo do dia"), (3, "Saúde dos dados"), (4, "Experimento"), (5, "Histórico"), (6, "Ações")`, vale `f'<span class="num">{n}</span> {nome}</h2>' in texto`.
2. `test_cartoes_dentro_das_secoes`: as posições seguem `sec-fluxo < id="agora" < id="linha-tempo" < sec-saude < id="saude" < sec-experimento < id="experimento" < sec-historico < id="historico" < sec-acoes < id="comandos" < id="testes"`.
3. `test_tela_inteira_e_breakpoints`:
   - `"max-width:1180px" not in texto` e `'class="two"' not in texto`;
   - estão no texto: `"grid-template-columns:repeat(12,minmax(0,1fr))"`, `"@media (min-width:600px)"`, `"@media (min-width:900px)"`, `"@media (min-width:1280px)"`, `"@media (min-width:1700px)"`, `"container-type:inline-size"`, `"@container (max-width:640px)"` e `"@container (max-width:720px)"`.
4. `test_logo_e_favicon_sem_link_literal`: estão no texto `"Interface do Processamento"`, `'id="logo-ic"'`, `'createElement("link")'`, `'"data:image/svg+xml,"'`, `"XMLSerializer"` e `'link.rel = "icon"'`, e `"<link" not in texto`.

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_pagina.py`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`.

---

### FASE 5b: `pagina.html` (ajuda, resumo, "O que fazer", tempos) + `test_painel_pagina.py` (depois de 1 e 5a)

Localize cada ponto pelo nome da função, porque as linhas mudaram na 5a.

**CSS:** acrescente no fim do `<style>`:
```css
.ajuda-btn{font:inherit;font-size:.7rem;font-weight:700;line-height:1;width:20px;height:20px;padding:0;border-radius:50%;border:1px solid var(--line);background:var(--surface);color:var(--muted);cursor:pointer;display:inline-grid;place-items:center;flex:none;vertical-align:middle}
.ajuda-btn:hover,.ajuda-btn[aria-expanded="true"]{color:var(--accent);border-color:var(--accent)}
.ajuda-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (pointer:coarse){.ajuda-btn{width:28px;height:28px}}
.ajuda-caixa{position:absolute;z-index:50;max-width:min(360px, calc(100vw - 24px));background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;box-shadow:0 8px 24px rgba(0,0,0,.18);font-size:.85rem;line-height:1.45;display:grid;gap:6px}
.ajuda-tit{font-weight:600}
.hc .tit-linha{justify-content:space-between;flex-wrap:nowrap}
.resumo{border-left:6px solid var(--idle)}
.resumo.ok{border-left-color:var(--ok)} .resumo.warn{border-left-color:var(--warn)} .resumo.bad{border-left-color:var(--bad)}
.resumo-frase{font:inherit;font-size:1.3rem;font-weight:700;text-align:left;background:none;border:0;padding:0;color:var(--ink);cursor:pointer;justify-self:start}
.resumo.ok .resumo-frase{color:var(--ok)} .resumo.warn .resumo-frase{color:var(--warn)} .resumo.bad .resumo-frase{color:var(--bad)}
.resumo-frase:disabled{cursor:default;opacity:1}
.resumo-frase:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.resumo-lista{list-style:none;margin:0;padding:0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}
.ponto{border:1px solid var(--line);border-left:4px solid var(--idle);border-radius:8px;padding:8px 10px;font-size:.86rem;display:grid;gap:2px}
.ponto.warn{border-left-color:var(--warn)} .ponto.bad{border-left-color:var(--bad)}
.fazer,.fazer-curto{font-size:.8rem;color:var(--muted)}
.fazer{border-top:1px dashed var(--line);padding-top:6px}
.fazer strong,.fazer-curto strong{color:var(--ink)}
.tempo{font-size:.8rem}
```

**JS:**

1. **`ESTADO`:** acrescente `ajuda: null,`, `timerAjuda: null,` e `pontos: new Map(),`.

2. **Funções novas**, depois de `motivo(texto)`:
```js
// ---- ajuda ("?"): textos vêm prontos do servidor em visao.ajuda ----
function botaoAjuda(id) {
  const b = criar("button", "?", "ajuda-btn");
  b.type = "button";
  b.setAttribute("data-ajuda", id);
  b.setAttribute("aria-label", "Ajuda");
  b.setAttribute("aria-expanded", "false");
  b.setAttribute("aria-controls", "ajuda-caixa");
  return b;
}

function textoAjuda(id) {
  const a = (((ESTADO.painel || {}).visao || {}).ajuda || {})[id];
  return a && typeof a.titulo === "string" && typeof a.texto === "string" ? a : null;
}

function rotularAjudas() {
  document.querySelectorAll(".ajuda-btn").forEach((b) => {
    const a = textoAjuda(b.getAttribute("data-ajuda"));
    b.hidden = !a;
    b.setAttribute("aria-label", a ? "Ajuda: " + a.titulo : "Ajuda");
  });
}

function posicionarAjuda(botao) {
  const caixa = $("ajuda-caixa");
  const r = botao.getBoundingClientRect();
  const margem = 12;
  const maxEsq = window.scrollX + document.documentElement.clientWidth - caixa.offsetWidth - margem;
  const esq = Math.max(window.scrollX + margem, Math.min(r.left + window.scrollX, maxEsq));
  caixa.style.left = esq + "px";
  caixa.style.top = (r.bottom + window.scrollY + 6) + "px";
}

function desmarcarAjuda(b) {
  b.setAttribute("aria-expanded", "false");
  b.removeAttribute("aria-describedby");
}

function abrirAjuda(botao, fixa) {
  const a = textoAjuda(botao.getAttribute("data-ajuda"));
  if (!a) return;
  clearTimeout(ESTADO.timerAjuda);
  if (ESTADO.ajuda && ESTADO.ajuda.botao !== botao) desmarcarAjuda(ESTADO.ajuda.botao);
  $("ajuda-titulo").textContent = a.titulo;
  $("ajuda-texto").textContent = a.texto;
  $("ajuda-caixa").hidden = false;
  botao.setAttribute("aria-expanded", "true");
  botao.setAttribute("aria-describedby", "ajuda-caixa");
  ESTADO.ajuda = { botao: botao, id: botao.getAttribute("data-ajuda"), fixa: Boolean(fixa) };
  posicionarAjuda(botao);
}

function fecharAjuda(devolverFoco) {
  clearTimeout(ESTADO.timerAjuda);
  if (!ESTADO.ajuda) return;
  const b = ESTADO.ajuda.botao;
  desmarcarAjuda(b);
  $("ajuda-caixa").hidden = true;
  ESTADO.ajuda = null;
  if (devolverFoco && b.isConnected) b.focus();
}

function alternarAjuda(botao) {
  if (ESTADO.ajuda && ESTADO.ajuda.botao === botao && ESTADO.ajuda.fixa) fecharAjuda(false);
  else abrirAjuda(botao, true);
}

// Depois de redesenhar: os "?" dinâmicos foram recriados; a caixa aberta passa para o botão novo.
function reancorarAjuda() {
  rotularAjudas();
  if (!ESTADO.ajuda) return;
  const atual = ESTADO.ajuda;
  const botao = atual.botao.isConnected ? atual.botao
    : Array.from(document.querySelectorAll(".ajuda-btn")).find((b) => b.getAttribute("data-ajuda") === atual.id);
  if (!botao || botao.hidden) {
    $("ajuda-caixa").hidden = true;
    ESTADO.ajuda = null;
    return;
  }
  abrirAjuda(botao, atual.fixa);
}

// ---- resumo e "O que fazer" ----
function irPara(alvo) {
  const el = $(alvo);
  if (!el) return;
  if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  const reduzir = matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduzir ? "auto" : "smooth", block: "center" });
  el.focus({ preventScroll: true });
}

function linhaFazer(alvo) {
  const p = ESTADO.pontos.get(alvo);
  if (!p || !p.o_que_fazer) return null;
  const el = criar("p", null, "fazer");
  el.appendChild(criar("strong", "O que fazer: "));
  el.appendChild(document.createTextNode(String(p.o_que_fazer)));
  return el;
}

function renderFazerCartoes() {
  document.querySelectorAll("[data-fazer]").forEach((slot) => {
    const p = ESTADO.pontos.get(slot.getAttribute("data-fazer"));
    if (!p || !p.o_que_fazer) {
      slot.replaceChildren();
      slot.hidden = true;
      return;
    }
    slot.replaceChildren(criar("strong", "O que fazer: "), document.createTextNode(String(p.o_que_fazer)));
    slot.hidden = false;
  });
}

function renderResumo(d) {
  const r = (d.visao || {}).resumo || {};
  const pontos = listaSegura(r.pontos).filter((p) => p && typeof p.alvo === "string");
  ESTADO.pontos = new Map(pontos.map((p) => [p.alvo, p]));
  $("resumo").className = "card resumo " + farol(r.nivel);
  const frase = $("resumo-frase");
  frase.textContent = txt(r.frase);
  frase.disabled = pontos.length === 0;
  frase.onclick = pontos.length ? () => irPara(pontos[0].alvo) : null;
  $("resumo-lista").replaceChildren(...pontos.map((p) => {
    const li = criar("li", null, "ponto " + farol(p.nivel));
    const a = criar("a", txt(p.texto));
    a.href = "#" + p.alvo;
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      irPara(p.alvo);
    });
    li.appendChild(a);
    if (p.o_que_fazer) {
      const f = criar("span", null, "fazer-curto");
      f.appendChild(criar("strong", "O que fazer: "));
      f.appendChild(document.createTextNode(String(p.o_que_fazer)));
      li.appendChild(f);
    }
    return li;
  }));
}

function metaComAjuda(texto, botao) {
  const s = criar("span", texto, "meta");
  s.appendChild(botao);
  return s;
}

function linhaTempoAcao(id, d) {
  const t = (((d.visao || {}).tempos) || {})[id] || {};
  const p = criar("p", null, "tempo");
  p.appendChild(criar("strong", "Tempo: "));
  const partes = [];
  if (typeof t.curto === "string") partes.push("leva " + t.curto + ".");
  partes.push(txt(t.texto));
  p.appendChild(document.createTextNode(partes.join(" ")));
  return p;
}
```

3. **`estagio`:** substitua a função inteira.
```js
function estagio(bloco, rotulo, linhas, alvo, ajudaRotulo, ajudaTitulo) {
  const b = bloco || {};
  const e = criar("div", null, "stage " + farol(b.estado));
  e.id = alvo;
  const cab = criar("div", null, "tit-linha");
  cab.appendChild(criar("span", rotulo, "lbl"));
  if (ajudaRotulo) cab.appendChild(ajudaRotulo);
  e.appendChild(cab);
  const tit = criar("div", null, "tit-linha");
  tit.appendChild(criar("span", txt(b.titulo), "big"));
  if (ajudaTitulo) tit.appendChild(ajudaTitulo);
  e.appendChild(tit);
  linhas.forEach((l) => e.appendChild(l instanceof Node ? l : criar("span", l, "meta")));
  const fazer = linhaFazer(alvo);
  if (fazer) e.appendChild(fazer);
  return e;
}
```

4. **`renderFluxo`:** troque as 3 chamadas a `estagio`.
```js
const coleta = estagio(c, "1 · Coleta (outro módulo)", [txt(c.resumo), etapas], "fluxo-coleta", botaoAjuda("coleta"));
const processamento = estagio(p, "2 · Processamento (este módulo)",
  [txt(p.quando), txt(p.rotulo), duracao, metaComAjuda(rodada, botaoAjuda("rodada"))],
  "fluxo-processamento", botaoAjuda("processamento"));
const interfaceNo = estagio(i, "3 · Interface", [metaComAjuda(contrato, botaoAjuda("contrato")), publicado],
  "fluxo-interface", botaoAjuda("interface"), botaoAjuda("pacotes"));
```

5. **`cartaoSaude`:** reescreva a função.
```js
function cartaoSaude(c) {
  const cartao = criar("div", null, "hc " + farol(c.farol));
  const id = typeof c.id === "string" ? c.id : "";
  const cab = criar("div", null, "tit-linha");
  cab.appendChild(criar("span", txt(c.titulo), "lbl"));
  if (id) {
    cartao.id = "saude-c-" + id;
    cab.appendChild(botaoAjuda("saude_" + id));
  }
  cartao.appendChild(cab);
  cartao.appendChild(criar("span", txt(c.numero), "n"));
  cartao.appendChild(criar("p", txt(c.texto)));
  if (c.fonte) cartao.appendChild(criar("span", c.fonte, "so"));
  const fazer = id ? linhaFazer("saude-c-" + id) : null;
  if (fazer) cartao.appendChild(fazer);
  return cartao;
}
```

6. **`preencherKv`:** aceite um 3º item opcional (o botão de ajuda).
```js
function preencherKv(id, pares) {
  const nos = [];
  pares.forEach(([termo, valor, ajudaBotao]) => {
    const dt = criar("dt", termo);
    if (ajudaBotao) {
      dt.appendChild(document.createTextNode(" "));
      dt.appendChild(ajudaBotao);
    }
    nos.push(dt);
    nos.push(criar("dd", valor));
  });
  $(id).replaceChildren(...nos);
}
```
Em `renderExperimento`, mude 4 pares:
- `["Modelo", modelo, botaoAjuda("modelo")]`;
- `["Top 5 na interface", publicado, botaoAjuda("top5_retido")]`;
- `["Chance exibida", chance, botaoAjuda("chance")]`;
- `["Modelo sombra", modeloSombra, botaoAjuda("modelo_sombra")]`.

7. **`cartaoBotao`:** troque `cartao.appendChild(criar("h3", b.titulo || id));` por:
```js
  const tit = criar("div", null, "tit-linha");
  tit.appendChild(criar("h3", b.titulo || id));
  tit.appendChild(botaoAjuda("acao_" + id));
  cartao.appendChild(tit);
```
Logo depois da linha da descrição (`DESCRICAO.get(id)`), acrescente `cartao.appendChild(linhaTempoAcao(id, d));`.

8. **`renderizarPainel`:** nova ordem.
```js
function renderizarPainel(d) {
  ESTADO.painel = d;
  $("atualizado").textContent = d.gerado_em ? "Dados de " + dataBr(d.gerado_em) : "";
  renderResumo(d);
  pillGeral(d);
  pillHoje(d);
  renderFluxo(d);
  renderLinhaTempo(d);
  renderSaudeCartoes(d);
  renderSaude(d);
  renderExperimento(d);
  renderHistorico(d);
  renderCalendario(d);
  renderEtapas(d);
  renderBotoes(d);
  renderRun(d.acao || {});
  renderTestes(d);
  renderFazerCartoes();
  reancorarAjuda();
}
```

9. **Eventos:** antes de `instalarFavicon(); carregarPainel();`, acrescente:
```js
document.addEventListener("click", (ev) => {
  const b = ev.target.closest ? ev.target.closest(".ajuda-btn") : null;
  if (b) {
    alternarAjuda(b);
    return;
  }
  if (ESTADO.ajuda && !$("ajuda-caixa").contains(ev.target)) fecharAjuda(false);
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && ESTADO.ajuda) {
    ev.preventDefault();
    fecharAjuda(true);
  }
});
document.addEventListener("pointerover", (ev) => {
  if (ev.pointerType !== "mouse" || !ev.target.closest) return;
  const b = ev.target.closest(".ajuda-btn");
  if (b) {
    if (!ESTADO.ajuda || !ESTADO.ajuda.fixa) abrirAjuda(b, false);
    return;
  }
  if (ev.target.closest("#ajuda-caixa")) clearTimeout(ESTADO.timerAjuda);
});
document.addEventListener("pointerout", (ev) => {
  if (ev.pointerType !== "mouse" || !ESTADO.ajuda || ESTADO.ajuda.fixa || !ev.target.closest) return;
  if (!ev.target.closest(".ajuda-btn, #ajuda-caixa")) return;
  const para = ev.relatedTarget && ev.relatedTarget.closest ? ev.relatedTarget.closest(".ajuda-btn, #ajuda-caixa") : null;
  if (para) return;
  clearTimeout(ESTADO.timerAjuda);
  ESTADO.timerAjuda = setTimeout(() => fecharAjuda(false), 250);
});
window.addEventListener("resize", () => {
  if (ESTADO.ajuda) posicionarAjuda(ESTADO.ajuda.botao);
});
```

**Testes novos em `test_painel_pagina.py`:**
```python
import re
from processamento.painel.acoes import ACOES
from processamento.painel.ajuda import AJUDA
from processamento.painel.saude import _CARTOES
```
1. `test_ids_de_ajuda_batem_com_o_dicionario`:
   - `estaticos = set(re.findall(r'data-ajuda="([a-z0-9_]+)"', texto))`;
   - `literais = set(re.findall(r'botaoAjuda\("([a-z0-9_]+)"\)', texto))`;
   - `dinamicos = {"saude_" + c[0] for c in _CARTOES} | {"acao_" + a for a in ACOES}`;
   - `estaticos | literais | dinamicos == set(AJUDA)`;
   - `len(estaticos) == 14`;
   - `'botaoAjuda("saude_" + id)' in texto` e `'botaoAjuda("acao_" + id)' in texto`.
2. `test_botoes_de_ajuda_estaticos_acessiveis`: `tags = re.findall(r'<button class="ajuda-btn"[^>]*>', texto)`, com `len(tags) == 14`. Cada tag contém `'type="button"'`, `'aria-label="Ajuda"'`, `'aria-expanded="false"'`, `'aria-controls="ajuda-caixa"'` e `' hidden'`.
3. `test_caixa_de_ajuda_teclado_e_resumo`: estão no texto `'id="ajuda-caixa"'`, `'role="tooltip"'`, `'"aria-describedby"'`, `'"Escape"'`, `"pointerover"`, `"pointerout"`, `"isConnected"`, `'"O que fazer: "'`, `"data-fazer"`, `'id="resumo-frase"'`, `'id="resumo-lista"'`, `"irPara("`, `"scrollIntoView"`, `"preventScroll"`, `".resumo"`, `".tempos"`, `".ajuda"`, `'"Tempo: "'` e `'"leva "'`.

Os testes antigos `test_linguagem_sem_termos_proibidos`, `test_sem_insercao_de_html_nem_eval`, `test_sem_recurso_externo` e `test_sem_etapas_simuladas_por_tempo` precisam continuar passando.

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_pagina.py`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`.

---

### FASE 6: verificação final (executor)

1. `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`, depois `.venv/Scripts/python.exe -m pytest -q`. Os dois sem falhas.
2. `git status --porcelain`: só pode mostrar `processamento/painel/*`, `tests/test_painel_*.py` e `tests/dados/painel/raiz/processamento/config/parametros.yaml`. Qualquer outro arquivo: parar e avisar.
3. Prints com o Edge headless, como na rodada anterior:
   - servidor `python -m processamento.painel --sem-navegador` na raiz real (só lê arquivos; não acessa o banco);
   - larguras 1920, 1100 e 390, nos temas claro e escuro, sem clicar em nada.
4. Conferir nos prints:
   - Resumo "Atenção: 4 pontos";
   - Fluxo ao lado da Linha do tempo em 1920;
   - Saúde em 6 colunas em 1920 e em 2 colunas em 390;
   - Experimento ao lado do Histórico;
   - Ações e Testes no fim;
   - "Tempo: leva ~5 min…" no botão de testes;
   - logo no canto.

### Extras (só se o usuário aprovar; cada um é uma fase pequena, depois da Fase 6)

- **E1:** `visao.frase_dia(hoje, fluxo_dia) -> str | None` + `visao.dia` no JSON + `<p class="dia" id="frase-dia">` abaixo do h1. Testes com domingo 25/10 e sexta 23/10.
- **E2:** `ajuda.GLOSSARIO: list[tuple[str, str]]` + `visao.glossario` + `<details>` no rodapé, montado com `createElement`. Testes de linguagem e de números iguais aos da Fase 1.
- **E3:** `@media print{…}` esconde `.ajuda-btn`, `.toggle`, `#comandos .actions`, `#run` e `#erro-rede`; uma coluna; `details` abertos via JS em `beforeprint`. Teste: `"@media print" in texto`.

## Arquivos de referência

- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\pagina.html`
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\servidor.py` (CSP nas linhas 27-30; `montar_painel` nas linhas 131-170)
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\visao.py`
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\saude.py` (`_CARTOES` nas linhas 262-269)
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\leitores.py` (`ler_prazo_rotina` nas linhas 124-134)
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\relatorios.py` (`RE_PYTEST_INICIO`/`RE_PYTEST_FIM` nas linhas 24-25; `ler_ultimo_pytest` nas linhas 384-428)
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\acoes.py` (cabeçalho e rodapé dos logs nas linhas 177-181 e 292-295)
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\tests\test_painel_pagina.py`
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\tests\test_painel_servidor.py` (a linha 190 muda)
- `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\tests\dados\painel\raiz\processamento\config\parametros.yaml`
