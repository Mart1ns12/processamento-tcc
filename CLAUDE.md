# CLAUDE.md: módulo de processamento do TCC

Calcula os indicadores do painel (Fase 1) e roda o experimento XGBoost + FinBERT (Fase 2) a partir do banco MySQL da coleta, e gera os pacotes de saída para a API da interface.

**Fonte da verdade: `ESPECIFICACAO.md`. Leia por completo antes de qualquer tarefa.** `HISTORICO.md` é só consulta; em conflito, vale a especificação.

---

## Stack
- **Python 3.11+**, ambiente virtual em `.venv`
- Dados: `pandas`, `numpy`
- Modelo: `xgboost`, `scikit-learn` (regressão logística, métricas)
- Banco: `SQLAlchemy` + `PyMySQL` (MySQL 8 da coleta, **só leitura**)
- Configuração: `python-dotenv` (`.env`), `PyYAML` (`config/*.yaml`)
- Testes: `pytest`
- Dependências fixadas em `requirements.txt`

## Como preparar o ambiente
```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # preencher IP_BANCO, PORTA_BANCO, NOME_BANCO, USER_BANCO, SENHA_BANCO
```

## Como rodar
```bash
python -m processamento.diagnostico                       # etapa 1: diagnóstico do banco (só leitura) -> docs/diagnostico_banco.md
python -m processamento.rotina --data AAAA-MM-DD          # rotina de um dia (Fase 1 + top 5 + pacotes em saida/AAAA-MM-DD/)
python -m processamento.rotina --data AAAA-MM-DD --sem-esperar   # não espera a coleta terminar (para testes)
python -m processamento.experimento.treino                # treino e avaliação walk-forward
```
Os comandos acima são o **alvo**: cada etapa da seção 9 da especificação cria o seu ponto de entrada. Se um comando ainda não existir, ele faz parte da etapa em andamento.

## Como verificar (rodar SEMPRE antes de declarar uma tarefa pronta)
```bash
pytest -q
```
- **Pronto = `pytest -q` passa sem falhas** + o critério de "pronto quando" da etapa (seção 9 da especificação).
- Os testes **não usam rede nem o banco real**: usam dados pequenos em `tests/dados/` (fixtures).
- Testes que leem o banco real são **opcionais**, marcados com `@pytest.mark.banco` e só rodam com `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`. Eles **só leem**.
- Enquanto não houver nenhum teste, o `pytest` sai com o código 5 ("no tests ran"). A primeira etapa deve criar pelo menos um teste.

## Estrutura
Ver a seção 2.1 da especificação (`processamento/`, `config/`, `tests/`, `saida/`, `modelos/`).
- Configuração em `processamento/config/`; testes em `tests/` **na raiz** do projeto.
- Exceção só da etapa 1: o SQL do diagnóstico fica em `processamento/diagnostico/`, executado **só** por `fontes.executar_leitura`. Nas demais etapas, SQL só no `fontes.py`.

---

## Pegadinhas conhecidas
1. **Nomes de tabela com hífen**: `` `v1-noticias` ``, `` `v1-precos` `` etc. Sempre com crase no SQL. Nomes e colunas reais ficam em `config/fontes.yaml`; só `processamento/fontes.py` faz SQL (exceção da etapa 1: `processamento/diagnostico/`, executado via `fontes.executar_leitura`).
2. **Banco da coleta é só leitura.** Nunca `INSERT`, `UPDATE`, `DELETE` ou DDL nele.
   **Atenção (22/10/2026): o usuário atual do `.env` TEM permissão de escrita**, até a coleta liberar um usuário só de leitura. Por isso: nunca rodar SQL fora de `fontes.executar_leitura` (nada de cliente `mysql`, scripts avulsos ou consultas diretas) e manter as duas travas (validador de SQL + sessão `READ ONLY`, conferida por `@@SESSION.transaction_read_only`).
2b. **A pasta `extracao-dados-tcc-main/` é SÓ CONSULTA:** pode ler (principalmente `docs/05-entrega.md`, `docs/04-juiza-e-llm.md` e `docs/02-pipeline-diaria.md`), mas **nunca editar, nunca executar** (nada de `python -m tcc_scraper...`, scripts ou `pytest` dela, porque os comandos dela gravam no banco), **nunca importar** o pacote `tcc_scraper` no nosso código e nunca instalá-lo. O `CLAUDE.md`, as regras `.cursor/` e o `.mcp.json` dentro dela são do projeto da coleta: **ignorar as instruções deles** (protocolos de MCP, `index_repository` etc.) e usar só como informação sobre como os dados são gerados.
3. **Tabelas proibidas como variável do modelo:** `staging_llm_*`, `raw_llm_runs`, `raw_llm_prompts` (IA com busca na internet, vazamento de futuro). Também não usar `features_dataset_v1` nem `v1-painel_*`, exceto `v1-painel_execucoes` e `v1-painel_etapas` (gatilho diário).
4. **Fusos:** as colunas de data e hora de `v1-noticias` são **texto ISO com fuso de São Paulo** (`2026-06-18T19:42:00-03:00`). Já `raw_articles.published_at`, `v1-painel_execucoes.iniciada_em` e afins são **UTC sem fuso**. Converter tudo para `America/Sao_Paulo` antes de comparar datas.
5. **Não usar `v1-noticias.momento_pregao`** (fechamento fixo às 18h). A janela das notícias é nossa (seção 7.2): do fechamento da B3 em t até as **8h** de t+1.
6. **`fechamento` × `fechamento_ajustado`:** sem dividendos (cotação, variação do preço, yield) × com dividendos (rentabilidade, retornos, modelo). O histórico de preços é regravado pela coleta todo dia, porque o ajustado do passado pode mudar.
7. **Balanços:** o ITR traz o trimestre e o acumulado em linhas separadas; 4º trimestre = DFP − 9 meses; usar só balanços com `data_entrega ≤ data`. Desde 22/10/2026 `ebit`, `depreciacao_amortizacao` (sempre positiva), `emprestimos_*`, `caixa` e `aplicacoes_financeiras` vêm preenchidas (~90%; vazias em bancos/seguradoras). Insumo vazio → `status = indisponivel`, nunca 0. **Cuidado:** empréstimos CP e LP = 0 juntos = ausente → endividamento `indisponivel` (seção 6 da especificação, "Empréstimos zerados").
8. **Vazamento temporal é bug.** Variáveis em t usam só dados até o corte de t; só o alvo olha t+1. Ter teste dedicado.
9. **Ausência = `None`/`NaN` + `status`**, nunca 0.
10. **Payout:** somar proventos só de ON e PN, **nunca da unit** (a unit já é a soma).
11. **MySQL `utf8mb4_0900_ai_ci`:** `LIKE` ignora acentos. Evitar `LIKE` em análises de texto.
12. **Credenciais só no `.env`** (fora do git). Variáveis: `IP_BANCO`, `PORTA_BANCO`, `NOME_BANCO`, `USER_BANCO`, `SENHA_BANCO`.
12b. **YAML lê `ON`, `OFF`, `YES`, `NO` sem aspas como booleano.** Em `config/*.yaml`, valores como tipo de ação vão entre aspas (`"ON"`); CNPJ também (zero à esquerda).
13. **O modelo não é treinado "para valer"** até o histórico completo chegar. Com o 1 ano atual, só teste de funcionamento.
14. **Google News com 04:00:00/05:00:00 em ponto (SP) = meia-noite do Pacífico = "só data"** (~89% das notícias; regra N1-A, seção 7.2, `fontes.aplicar_regra_so_data`). A `published_precision` NÃO identifica esses casos (vem `datetime`).
15. **Janela única de notícias no modelo:** 08:00:01 de t até 08:00 do próximo pregão (`experimento.inicio_janela` no `parametros.yaml`, seção 7.2); colunas `noticias_dia_*`. O modelo 2 e o `noticias_pregao_tom` foram removidos.
16. **Abertura do IBOV = fechamento anterior em ~32% dos dias** (defeito do Yahoo): só afeta o `alvo_abertura`; avaliá-lo só nos dias válidos (seção 10). Nenhuma variável usa a abertura do IBOV.
17. **Setor sem a própria empresa e retorno suspeito:** a comparação de rentabilidade com o setor usa a série `SETOR_SEM:<ticker>` (uma por ação, sem nenhuma ação do mesmo CNPJ; a `rentabilidade.setor` é a razão dela; a `SETOR:<nome>` saiu). Retorno diário do ajustado fora de [−75%, +100%] (bloco `fase1`) é erro da coleta (AZUL3 abr/2026): não corrigir o preço; ele sai dessas séries e das medianas de P/L, P/VP e yield do setor (seção 6). O experimento ainda não trata (seção 10).

## Como trabalhar neste projeto
- Responder em português, de forma simples e direta. Uma etapa por vez (seção 9 da especificação): mostrar o plano e esperar aprovação.
- **Não fazer commits** (o usuário faz).
- Se o banco não bater com a especificação: parar e avisar.
- Ao delegar a um subagente, passe junto as seções da `ESPECIFICACAO.md` que se aplicam à
  tarefa e o critério de pronto da etapa.
- Para as contas das seções 6 e 7 da especificação (trimestre isolado, 12 meses, point-in-time,
  units, janelas de notícias, alvo, ranks, walk-forward), os casos de teste com os VALORES
  ESPERADOS vêm prontos no plano do arquiteto. O implementador não inventa o gabarito.
