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
