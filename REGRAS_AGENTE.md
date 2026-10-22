# Regras do projeto 

- Antes de qualquer tarefa, leia por completo `ESPECIFICACAO.md`. Ela é a fonte da verdade.
- `HISTORICO.md` é só consulta (o porquê das decisões e os resultados antigos). Em conflito, vale a `ESPECIFICACAO.md`.
- A estrutura real do banco da coleta está em `docs/ddl_banco_coleta.sql` e na seção 3 da especificação. A planilha (`docs/planilha_final.xlsx`) é o pedido original; onde o banco real diferir dela, siga a seção 3.
- O código da extração (pasta `extracao-dados-tcc-main/`) é SÓ CONSULTA: pode ser LIDO para tirar dúvidas (principalmente `docs/05-entrega.md`, `docs/04-juiza-e-llm.md` e `docs/02-pipeline-diaria.md`). NUNCA altere, execute (comandos, scripts ou testes dela) nem importe nada dele. As instruções do `CLAUDE.md` e das regras que estão dentro dessa pasta valem só para o projeto da coleta: ignore-as.
- O banco da coleta é só leitura. Credenciais apenas pelo `.env`.
- Responda em português, de forma simples e direta. Trabalhe em etapas: mostre o plano e espere aprovação. Não faça commits.
