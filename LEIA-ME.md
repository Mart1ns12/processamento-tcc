# Kit do módulo de processamento

| Arquivo / pasta | O que é |
|---|---|
| `ESPECIFICACAO.md` | O que deve ser implementado (fonte da verdade) |
| `HISTORICO.md` | Contexto, decisões e resultados antigos (consulta) |
| `CLAUDE.md` | Stack, comandos de rodar e testar e pegadinhas (lido automaticamente pelo agente) |
| `REGRAS_AGENTE.md` | Texto para o arquivo de regras do Antigravity |
| `PROMPT_INICIAL.md` | Primeira mensagem para o agente |
| `docs/planilha_final.xlsx` | A planilha combinada com a coleta e o painel |
| `docs/ddl_banco_coleta.sql` | A estrutura real do banco da coleta |
| `.env.example` | Modelo do arquivo de conexão (copiar para `.env` e preencher) |
| `.gitignore` | Impede `.env`, modelos e saídas de irem para o git |

## O que VOCÊ acrescenta
1. A pasta da extração (`extracao-dados-tcc-main/`) dentro desta pasta (ou ajuste o caminho no `REGRAS_AGENTE.md`).
2. O arquivo `.env` com o acesso ao banco (de preferência um usuário só de leitura).
3. `git init` (os commits você faz).

## Rotina diária no Agendador de Tarefas (Windows)

A rotina roda de segunda a sexta. A tarefa abre às 07:55; a rotina espera a coleta (que começa às 08:00) e termina quando a entrega do dia fica pronta, ou às 12:00. Em dia sem pregão, sai sem gravar nada.

- Script: `scripts/rotina_diaria.ps1` (não precisa editar).
- Log: `logs/rotina-AAAA-MM-DD.log`.
- Resultado do dia: `saida/AAAA-MM-DD/execucao.json`.
- Antes: `.env` preenchido e `.venv` criado (`pip install -r requirements.txt`).
- Este passo a passo é para o PC (testes de funcionamento). Onde a rotina vai rodar na produção ainda não foi decidido.

### Criar a tarefa pela interface

1. Abra o **Agendador de Tarefas** (Menu Iniciar, digite "Agendador de Tarefas").
2. No painel da direita, clique em **Criar Tarefa...** (não em "Criar Tarefa Básica": ela não mostra todas as abas abaixo).
3. Aba **Geral**:
   - Nome: `TCC rotina diaria`.
   - Marque **Executar estando o usuário conectado ou não** (o Windows pede a senha da conta).
4. Aba **Disparadores** > **Novo**:
   - Iniciar a tarefa: **Em uma programação**; configurações: **Semanalmente**, a cada 1 semana.
   - Marque **Segunda, Terça, Quarta, Quinta e Sexta**.
   - Hora: **07:55:00**. Clique em OK.
5. Aba **Ações** > **Novo**:
   - Ação: **Iniciar um programa**.
   - Programa/script: `powershell`
   - Adicionar argumentos: `-NoProfile -ExecutionPolicy Bypass -File "C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\scripts\rotina_diaria.ps1"`
   - Deixe "Iniciar em" vazio (o script já vai para a pasta do projeto).
6. Aba **Condições**:
   - Marque **Acordar o computador para executar esta tarefa**.
   - Desmarque **Iniciar a tarefa somente se o computador estiver ligado à rede elétrica CA** (só importa em notebook).
7. Aba **Configurações**:
   - Marque **Executar a tarefa o mais cedo possível após uma inicialização agendada ter sido perdida**.
   - Marque **Parar a tarefa se ela for executada por mais de**, com **5 horas**.
   - Em **Se a tarefa já estiver em execução, aplicar a seguinte regra**: **Não iniciar uma nova instância**.
8. Clique em OK e informe a senha do Windows.

**Plano de energia** (Painel de Controle > Opções de Energia > plano em uso > Alterar configurações do plano): em "Suspender o computador", quando estiver na tomada, escolha **Nunca**. A rotina também pede ao Windows para não suspender enquanto espera.

### Linha de comando equivalente

```
schtasks /Create /TN "TCC rotina diaria" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:55 /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\scripts\rotina_diaria.ps1"
```

O `schtasks` cria só o disparo e a ação. Depois, abra as propriedades da tarefa e faça os passos 3, 6 e 7 (conta, condições e configurações), que a linha de comando não cobre.

### Como testar

1. No Agendador, clique com o botão direito em **TCC rotina diaria** > **Executar**.
2. Espere terminar. Teste em dia de pregão, de preferência depois das 08:00 (a rotina espera a coleta).
3. Confira:
   - `logs/rotina-AAAA-MM-DD.log`: uma linha por consulta e o resultado;
   - `saida/AAAA-MM-DD/execucao.json`: `status` (`ok`, `parcial` ou `falhou`) e `coleta_status`.
4. Na coluna **Resultado da última execução** do Agendador aparece o código de saída em hexadecimal (`0x0` = 0, `0x4` = 4).

Em sábado, domingo ou feriado, a rotina sai com código 0 e não grava nada. Isso é o esperado.

### Códigos de saída

| Código | Quando |
|---|---|
| 0 | `ok`, `parcial` ou dia sem pregão (nada gravado) |
| 2 | Configuração: banco, parâmetros ou calendário vencido |
| 3 | Conexão com o banco, ou sessão que não é só leitura |
| 4 | `falhou`: a coleta não ficou pronta até 09:45 (ou o `gerar` não gerou nenhum pacote) |
| 5 | Outra rotina em andamento (trava). A trava vence sozinha depois de 6 horas |

## Carga completa da interface

Use quando a interface é ligada depois da rotina diária, ou quando o banco dela foi recriado. A rotina diária só manda o que mudou desde o último envio; a carga completa manda tudo: todas as ações, séries de 253 pregões, 8 trimestres de fundamentos e 5 anos de proventos. Detalhes na seção 8.7 da especificação.

1. Veja qual é a data da rotina diária mais recente (a pasta `saida\AAAA-MM-DD` com a data mais nova).
2. Na pasta do projeto, gere a carga com essa data:

```
.venv\Scripts\python.exe -m processamento.saida --data AAAA-MM-DD --completo --pasta saida_completa
```

Os 10 arquivos saem em `saida_completa\AAAA-MM-DD\`. A carga não mexe no envio diário, no `saida\estado\` nem nos registros do experimento, e não retreina o modelo. Não use `--pasta saida`: é a pasta do envio diário, e o comando recusa (código 2).

3. Envie os 10 arquivos para a interface nesta ordem: `acoes`, `series_diarias`, `mercado_dia`, `resumo_acao`, `fundamentos_trimestrais`, `proventos`, `noticias_dia`, `experimento_historico`, `experimento_top` e, por último, `execucao`.
4. Daí em diante, o envio diário segue de `saida\` como antes.

**Recarga do zero** (o banco da interface foi apagado ou recriado): apague o banco da interface, rode o comando do passo 2 com a data mais recente e envie os 10 arquivos de novo. Não precisa apagar `saida\estado\`: a interface recebe por substituição, então reenviar é seguro.

Limitação: o `experimento_historico` traz todo o histórico dos resultados já fechados (não há corte).
