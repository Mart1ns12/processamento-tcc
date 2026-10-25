# Plano: painel de operação local (`python -m processamento.painel`)

> Aprovado em 25/10/2026, com o **AJUSTE A1** abaixo (vale sobre o texto das fases F1, F3, F4 e F5). As sugestões do fim ficam para depois.

## AJUSTE A1 (aprovado): data da rotina = hoje, se for pregão; senão, o último pregão

O botão da rotina usa **hoje, se hoje for pregão previsto; senão, o último pregão previsto antes de hoje** (para a demonstração funcionar no fim de semana). A data é calculada **só pelo servidor**; o navegador continua mandando só o id. A tela mostra a data que será usada **antes** de confirmar. (O painel não lê o banco: "com coleta" é conferido pela própria rotina, que consulta o daily daquele dia e mostra o resultado no log.)

**F1 (`leitores.py`), função nova:**
```python
def data_rotina(agora: datetime, caminho_calendario: str | None = None) -> dict
    # d = agora.astimezone(SP).date()
    # calendario.e_pregao_previsto(d, cam)  -> {"data": d.isoformat(), "origem": "hoje", "erro": None}
    # senão -> {"data": calendario.pregao_anterior_previsto(d, cam).isoformat(), "origem": "ultimo_pregao", "erro": None}
    # calendario.ErroCalendario -> {"data": None, "origem": None, "erro": str(e)}
```
Testes (yaml real): `datetime(2026,10,23,9,0,tzinfo=SP)` → `{"data":"2026-10-23","origem":"hoje","erro":None}`; `datetime(2026,10,25,12,0,tzinfo=SP)` (domingo) → `{"data":"2026-10-23","origem":"ultimo_pregao","erro":None}`; `datetime(2026,10,12,9,0,tzinfo=SP)` (feriado, segunda) → `"2026-10-09"`, `"ultimo_pregao"`; `datetime(2026,10,24,2,0,tzinfo=timezone.utc)` → `"2026-10-23"`, `"hoje"`.

**F3 (`acoes.py`):** a assinatura passa a ser `montar_comando(acao_id, *, d_rotina: date | None, d_carga: date | None)`. `rotina`: `None` se `d_rotina is None`; senão `[sys.executable,"-m","processamento.rotina","--data",d_rotina.isoformat(),"--sem-esperar"]`. Os testes de F3 usam `d_rotina=` no lugar de `hoje=`.

**F4 (`servidor.py`):**
- `montar_painel` calcula `rotina_data = leitores.data_rotina(agora, caminho_calendario)` e devolve a chave nova `"data_rotina"` no JSON (as chaves esperadas no teste 3 passam a incluir `"data_rotina"`).
- `estado_botoes(params, trava, hoje, rotina_data, d_carga, executor, agora)`. Todo botão ganha a chave `"data"`: `rotina` → `rotina_data["data"]`; `carga` → `d_carga.isoformat()` ou `None`; os outros → `None`.
- Regras da `rotina` (substituem o item 3 do plano): (a) `teste_final.fim` preenchido → desabilitado (decisão 1, igual); (b) `rotina_data["erro"]` → desabilitado, `motivo f"Calendário: {erro}"`; (c) aviso com `origem "hoje"`: `f"Data usada: {data} (hoje). Com --sem-esperar, se a coleta de hoje ainda não terminou (antes das 08:00 ela nem começou), a rotina gera mesmo assim, com aviso. Regrava saida/{data}/, saida/estado/ e registros/experimento/{data}.top.json."`; com `origem "ultimo_pregao"`: `f"Hoje ({hoje['motivo']}) não é pregão: será usada a data {data}, o último pregão. A rotina confere a coleta desse dia no banco e regrava saida/{data}/, saida/estado/ e registros/experimento/{data}.top.json."`
- `montar_comando(id, d_rotina=date.fromisoformat(rotina_data["data"]) se houver, d_carga=...)`, também recalculado no servidor no POST.
- Testes extras: com o `RELOGIO` de sexta 23/10 10:00 → `botoes.rotina.data == "2026-10-23"`, comando `"python -m processamento.rotina --data 2026-10-23 --sem-esperar"`, `data_rotina.origem == "hoje"`. Com um segundo servidor de relógio `datetime(2026,10,25,12,0,tzinfo=SP)` (domingo) → `botoes.rotina.data == "2026-10-23"`, `botoes.rotina.habilitado is True`, comando com `--data 2026-10-23`, aviso contém `"2026-10-23"` e `"domingo"`, `data_rotina.origem == "ultimo_pregao"`.

**F5 (`pagina.html`):** embaixo do botão da rotina (e da carga), antes de qualquer clique, mostrar `"Data usada: dd/mm/aaaa (hoje)"` ou `"Data usada: dd/mm/aaaa (último pregão)"` a partir de `botoes[id].data` e `data_rotina.origem`. O `confirm` começa por `"Data: dd/mm/aaaa\n"` quando `data` existir. Teste de F5: a página contém `"Data usada"`.

**Testes que ESCREVEM o `.top.json` real:** nenhum. Os testes nunca rodam a rotina de verdade (comandos simulados), e o servidor de teste usa a raiz em `tmp_path`.

---

## Resumo em linguagem simples (para o usuário)
1. É uma página que abre no seu navegador e só funciona no seu computador (endereço 127.0.0.1).
2. Mostra o que o processamento fez: a última rodada (se deu certo, quando começou e terminou, quanto tempo levou) e se a coleta das 8h estava pronta.
3. Tem 4 botões: rodar a rotina de hoje, gerar a carga completa, rodar o diagnóstico do banco e rodar os testes. Enquanto um roda, a tela mostra o que ele escreve, linha a linha, e os outros botões ficam travados.
4. Mostra o histórico de todos os dias processados. Clicando num dia, aparecem os detalhes.
5. Mostra os passos de cada rodada, tirados dos arquivos de log que a rotina já grava.
6. Resume o diagnóstico do banco: divergências e observações principais.
7. Mostra a situação do experimento: modelo provisório, trava do teste final fechada e os números do último treino, com o aviso "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO".
8. Mostra o resultado do último `pytest` rodado pelo painel.
9. Não muda nada do que existe. É uma pasta nova (`processamento/painel/`) mais testes novos. O painel não acessa o banco e não lê o `.env`. Só chama os comandos que já existem.
10. Não precisa instalar nada: usa só o que já vem com o Python.

---

## 0. O que eu conferi no código (premissas, com arquivo:linha)

- **Rotina**: `processamento/rotina/executar.py:295-317`. Argumentos: `--data` (sem ele, usa hoje em SP, `:258`), `--sem-esperar`, `--pasta`, `--pasta-modelos`, `--pasta-registros`. Códigos de saída (`:5-6`): 0 = ok/parcial/sem pregão, 2 = configuração, 3 = banco, 4 = falhou, 5 = trava.
  - Dia sem pregão (`:182-184`): só escreve no log "`<D> não é pregão previsto (domingo): nada a gerar.`", sai com 0 e não grava nada.
  - `--sem-esperar` com a coleta ainda não pronta **gera mesmo assim**, com aviso (`rotina/gatilho.py:280-291`, motivo `sem_esperar`).
  - O log da rodada vai para `logs/rotina-<D>.log` e para o stdout (`executar.py:112-129`). O arquivo é aberto em modo de acréscimo, então cada rodada soma um bloco. O formato é `%(message)s`, sem hora por linha.
- **Trava**: `processamento/rotina/trava.py`. O arquivo tem `{"pid","criada_em"}` e vale por 6 h (`parametros.yaml` → `rotina.trava` = `"saida/estado/rotina.trava"`, `rotina.trava_validade_horas: 6`). `_ler_trava(caminho, agora) -> (criada_txt, pid, instante)` (`:30-41`) pode ser reaproveitada. Ela importa só `saida.contrato` (numpy/pandas). Conferi que importar `processamento.rotina.trava` e `processamento.calendario` **não** carrega `processamento.fontes`, `sqlalchemy` nem `dotenv`.
- **Saída / carga completa**: `processamento/saida/gerar.py:362-423`. `--data` é obrigatório. Sem `--pasta`, `--completo` grava em `saida_completa/` (`:49`, `:384-389`). Códigos: 0, 2, 3, 4. O LEIA-ME (`:90-97`) manda usar como D a pasta `saida/AAAA-MM-DD` mais nova.
- **Diagnóstico**: `processamento/diagnostico/__main__.py:84-148`. Não tem argumento obrigatório. Grava `docs/diagnostico_banco.md`. Códigos: 0, 2, 3.
- **`execucao.json` real** (`saida/2026-10-23/execucao.json`): é um envelope `{pacote, versao_contrato, chave, gerado_em, dados_ate, registros:[1 registro], removidos}`. Campos do registro: `data_referencia`, `rodada` (6), `inicio` (`2026-10-24T22:46:25-03:00`), `fim` (`…22:48:23-03:00`), `status`, `coleta_status{consultado, nota, motivo, execucao_id, origem, status_execucao, iniciada_em, finalizada_em, entrega_concluida_em, etapas{9}, consultas, …}`, `pacotes_enviados[{pacote,arquivo,registros,removidos}]` (7 itens), `avisos[]`.
  - Quando a rodada está `em_andamento`, `fim` é `null` (`gerar.py:152`).
  - Sem rotina, `coleta_status = {"consultado": false, "nota": "gatilho da coleta não consultado (etapa 8)"}` (`gerar.py:38`).
  - **Cada D guarda só a última rodada**: o arquivo é regravado a cada rodada.
- **Logs reais**: os blocos começam com `Rotina de D (início HH:MM:SS[, --sem-esperar])`. Depois vêm `HH:MM:SS consulta N: … -> gerar|esperar (…)`, `Saída de D em <pasta>: status X`, `- aviso`, `… não é pregão previsto (sábado): nada a gerar.` e `… Rodada cancelada; nada foi gravado.` (trava). **Não há hora de fim nem duração das etapas internas.** O número de blocos no log não corresponde ao `rodada` do JSON: o 23/10 tem 4 blocos e `rodada` 6, porque o `processamento.saida` também numera rodadas e não grava log.
- **Diagnóstico .md**: vem de `diagnostico/relatorio.py:76-112`. Tem o cabeçalho `- Gerado em: …`, depois `## Divergências × especificação` com "Nenhuma divergência encontrada." ou uma tabela `| # | Tema | Tabela | Detalhe |` (o caractere `|` dentro do texto aparece escapado como `\|`), depois as seções `## N. Título`, cada uma com bullets `- nota` e em seguida `### subtítulo` + tabela.
- **parametros.yaml**: `treino.teste_final.{inicio:"2026-06-23", fim:null, liberado:false}`, `treino.modelo_oficial:false`, `saida.publicar_top_provisorio:false`, `saida.pasta:"saida"`, `rotina.pasta_logs:"logs"`. A trava F2 também considera `docs/teste_final_usado.json` (ESPEC. 9, F2), que hoje não existe.
- **`modelos/*.meta.json`**: `modelo`, `provisorio`, `periodo_treino{inicio,fim}`, `n_linhas_treino`, `metricas_validacao{auc_geral, auc_medio_pregao, taxa_acerto_top5}`, `calibracao{…aprovada, chance_exibida}` (é `null` no m1), `aviso`, `gerado_em`, `teste_final{inicio,fim,usado}`.
- **`saida/experimento/treino/dev-AAAA-MM-DD/metricas.json`**: `modo`, `aviso_funcionamento`, `gerado_em`, `periodo{…}`, `acaso["5"]{media,p2_5,p97_5}`, `modelos{modelo_1,modelo_3,logistica,volatilidade}` com `auc_medio_pregao` e `topk["5"]{taxa_acerto, ic_taxa}` (algumas chaves são `null`), `veredito_modelo_3.texto`, `calibracao{ece,aprovada,chance_exibida}`. O `relatorio.md` começa com o aviso "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO".
- **.gitignore**: `*.log` é ignorado em qualquer pasta, assim como `/saida/`, `/saida_completa/`, `/modelos/` e `.env`.
  - Por isso os logs do painel em `logs/painel/*.log` **já ficam fora do git, sem editar o .gitignore**.
  - **Pegadinha**: uma fixture `.log` dentro de `tests/dados/` seria ignorada pelo git, e o teste quebraria num clone novo. Solução: as fixtures se chamam `*.log.txt` e o helper as renomeia ao copiar para `tmp_path`.
- `tests/test_estrutura.py` só importa pacotes, e nenhum teste varre os subpacotes de `processamento/`. Uma pasta nova não quebra nada.
- O Python da `.venv` é o 3.12.10. A suíte tem hoje 1743 testes coletados.
- O padrão do repo para pontos de entrada é `__main__.py` com `from … import main; raise SystemExit(main())`. As fixtures-fábrica ficam em `tests/fabrica_*.py`, importadas como `from fabrica_x import …`.

## 1. Decisões (uma rota cada)

- **Só stdlib** (`http.server.ThreadingHTTPServer` + `threading` + `subprocess`). Flask ou FastAPI exigiriam mexer no `requirements.txt`, o que a regra proíbe, e não trazem nada de que o painel precise.
- **Log ao vivo por polling** (`GET /api/acao?desde=N` a cada 1 s), não SSE. É mais simples, testável com `http.client` e não prende threads do servidor.
- **Onde fica o resultado do último pytest e os logs do painel**: `logs/painel/<acao>-AAAA-MM-DD_HHMMSS.log`. Cada arquivo tem uma linha de cabeçalho e uma de rodapé (com o código de saída) escritas pelo painel. Esses arquivos já são ignorados pelo git (`*.log`), então não precisa de pasta nova no .gitignore nem de arquivo de estado. O painel guarda os 20 mais recentes por ação e apaga só os seus próprios arquivos.
- **Cancelar**: só para **testes**. Matar a rotina no Windows (`terminate`) pula o `finally` e deixa `rotina.trava` presa por até 6 h. A carga completa e o diagnóstico são curtos e só leem o banco. Não há cancelamento para eles.
- **Data da rotina**: o servidor calcula "hoje" em SP. O navegador manda **só o id** da ação, nunca data, caminho ou argumento.
- **Carga completa**: D = a pasta `saida/AAAA-MM-DD` mais nova que tenha `execucao.json`, como manda o LEIA-ME. O comando é `python -m processamento.saida --data D --completo`, sem `--pasta`; o padrão já é `saida_completa`.
- **Leitura do `parametros.yaml` direto com `yaml.safe_load`**, sem os carregadores validados. O painel precisa abrir mesmo com o yaml inválido, que é justamente quando mais importa ver o problema, e assim não importa `fontes`. Para "hoje é pregão?" ele reutiliza `calendario.motivo_sem_pregao`, que é pura e lê o yaml real do código.
- **Botão da rotina bloqueado em produção** (com `treino.teste_final.fim` preenchido). Rodar `--sem-esperar` antes da coleta terminar gravaria o top 5 oficial do dia (uso único) com dados incompletos. Fora da produção, o botão pede confirmação e mostra o aviso. Se o usuário não quiser essa trava, basta tirar uma condição em `estado_botoes`.
- **Trava R14**: o painel só **lê** o arquivo. Com a trava ativa (outra rotina rodando, por exemplo pelo Agendador), ficam desabilitados a rotina, a carga e o diagnóstico (os que usam o banco). Os testes continuam liberados. O painel nunca cria nem apaga a trava. Trava com mais de 6 h aparece como "abandonada" e libera o botão, porque a própria rotina a apaga.

## 2. Arquitetura (arquivos novos; nenhum existente é alterado)

```
processamento/painel/__init__.py      docstring só
processamento/painel/__main__.py      from processamento.painel.servidor import main; raise SystemExit(main())
processamento/painel/leitores.py      execuções, trava, parâmetros, hoje, duração (F1)
processamento/painel/relatorios.py    logs da rotina, diagnóstico, experimento, último pytest (F2)
processamento/painel/acoes.py         lista fixa de ações, comandos, ambiente, Executor (F3)
processamento/painel/pagina.html      página única, HTML/CSS/JS inline, sem CDN (F5)
processamento/painel/servidor.py      HTTP, segurança, montagem do JSON, main() (F4)
tests/fabrica_painel.py               montar_raiz(tmp_path) (F0)
tests/dados/painel/raiz/...           fixtures estáticas (F0)
tests/test_painel_leitores.py | test_painel_relatorios.py | test_painel_acoes.py | test_painel_servidor.py | test_painel_pagina.py
```

### Ordem e paralelismo
- **F0** (fixtures), **F3** (acoes) e **F5** (página) podem começar juntas.
- **F1** e **F2** vêm depois de F0 e podem rodar em paralelo entre si e com F3/F5.
- **F4** (servidor) vem depois de F1, F2, F3 e F5.
- **F6** é a verificação final.
- Os arquivos não se sobrepõem, então não precisa de worktree.

---

## REGRAS PARA TODAS AS FASES (copiar em todo despacho)
- Projeto: `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc`, Python da `.venv` (`.venv/Scripts/python.exe`), Windows.
- **Não alterar NENHUM arquivo existente**: módulos, testes, `conftest.py`, `parametros.yaml`, `ESPECIFICACAO.md`, `.gitignore`, `requirements.txt`. Só criar os arquivos listados na fase.
- **Nunca abrir nem ler o `.env`.** Nunca importar `processamento.fontes`, `sqlalchemy` nem `dotenv` no painel. Nenhum SQL. Nunca rodar `python -m processamento.rotina`, `processamento.saida` ou `processamento.diagnostico` (acessam o banco). Testes sem rede externa e sem banco.
- Não fazer commit.
- Fuso: `from processamento.calendario import SP` (America/Sao_Paulo). Comparar datas e horas como `datetime.fromisoformat(...)`, nunca como texto.
- Arquivos: ler com `encoding="utf-8"` (logs: `errors="replace"`), gravar com `encoding="utf-8"`.
- Ausência nunca quebra: as funções de leitura **nunca levantam exceção** por arquivo ausente ou quebrado; devolvem `{"disponivel": False, "motivo": "..."}` ou `None` (como especificado).
- Caminhos devolvidos ao navegador sempre **relativos à raiz**, com `/` (`Path.relative_to(raiz).as_posix()`).
- Textos de interface em português simples, sem emoji. Início de módulo com `from __future__ import annotations` e docstring curta.
- Testes nunca escrevem em `tests/dados/`: usam `montar_raiz(tmp_path)` (de `tests/fabrica_painel.py`), que copia a árvore para `tmp_path`.
- Verificação: `.venv/Scripts/python.exe -m pytest -q <arquivo da fase>` e depois `.venv/Scripts/python.exe -m pytest -q` (os 1743 testes existentes têm que continuar passando, mais os novos).

---

## F0. Fixtures + fábrica (mecânica; nada de lógica)

Criar `tests/fabrica_painel.py`:
```python
DADOS = Path(__file__).parent / "dados" / "painel" / "raiz"
def montar_raiz(tmp_path: Path) -> Path:
    """Copia a árvore de fixtures para tmp_path/'raiz', renomeia *.log.txt -> *.log e cria um .env FALSO."""
    raiz = tmp_path / "raiz"; shutil.copytree(DADOS, raiz)
    for f in list(raiz.rglob("*.log.txt")): f.rename(f.with_name(f.name[:-4]))
    (raiz / ".env").write_text("SENHA_BANCO=segredo123\nUSER_BANCO=usuario_teste\n", encoding="utf-8")
    return raiz
```
O `.env` fica só no tmp, porque `.env` está no .gitignore. **Não criar um `.env` em `tests/dados`.**

Arquivos em `tests/dados/painel/raiz/` (conteúdo exato):

1. `processamento/config/parametros.yaml`
```yaml
treino:
  teste_final:
    inicio: "2026-06-23"
    fim: null
    liberado: false
  modelo_oficial: false
saida:
  pasta: "saida"
  publicar_top_provisorio: false
rotina:
  pasta_logs: "logs"
  trava: "saida/estado/rotina.trava"
  trava_validade_horas: 6
```
2. `saida/2026-10-23/execucao.json`: envelope com `"pacote":"execucao","versao_contrato":"1.0","chave":["data_referencia","rodada"],"gerado_em":"2026-10-24T22:46:25-03:00","dados_ate":"2026-10-23T08:00:00-03:00","removidos":[]` e `registros` com 1 registro:
   - `gerado_em` `"2026-10-24T22:46:25-03:00"`, `dados_ate` igual ao do envelope, `data_referencia` `"2026-10-23"`, `rodada` 6, `inicio` `"2026-10-24T22:46:25-03:00"`, `fim` `"2026-10-24T22:48:23-03:00"`, `status` `"ok"`.
   - `coleta_status`: `{"consultado":true,"nota":"Daily da agenda (origem cron).","motivo":"entrega_concluida","execucao_id":"2026-10-23-daily-080001","origem":"cron","status_execucao":"concluida","iniciada_em":"2026-10-23T08:00:01-03:00","finalizada_em":"2026-10-23T08:24:29-03:00","entrega_concluida_em":"2026-10-23T08:22:52-03:00","etapas":{"precos":"concluida","macro":"concluida","noticias":"concluida","ipe":"concluida","enriquecimento":"concluida","juiza":"concluida","cadastro":"concluida","entrega":"concluida","analise":"concluida"},"consultas":1,"espera_segundos":0}`.
   - `pacotes_enviados`: 7 itens `{"pacote":P,"arquivo":P+".json","registros":R,"removidos":0}` com (P, R) = (acoes, 0), (series_diarias, 0), (mercado_dia, 1), (resumo_acao, 85), (fundamentos_trimestrais, 8), (proventos, 0), (noticias_dia, 85).
   - `avisos`: `["Modelo provisório: treinado de 2024-01-02 a 2026-06-19 (cerca de 2,5 anos), só para testar a rotina.", "Gerado depois das 10h: não entra no histórico do experimento.", "Top 5 gerado e registrado só como teste de funcionamento (modelo não oficial): experimento_top e experimento_historico não enviados à interface (saida.publicar_top_provisorio = false)."]`
3. `saida/2026-10-22/execucao.json`: mesmo envelope (com `gerado_em` `"2026-10-22T09:45:00-03:00"` e `dados_ate` `"2026-10-22T08:00:00-03:00"`).
   - Registro: `gerado_em` `"2026-10-22T09:45:00-03:00"`, `data_referencia` `"2026-10-22"`, `rodada` 1, `inicio` e `fim` `"2026-10-22T09:45:00-03:00"`, `status` `"falhou"`.
   - `coleta_status`: `{"consultado":true,"nota":"Daily da agenda (origem cron).","motivo":"entrega_pendente","execucao_id":"2026-10-22-daily-080001","origem":"cron","status_execucao":"em_andamento","iniciada_em":"2026-10-22T08:00:01-03:00","finalizada_em":null,"entrega_concluida_em":null,"etapas":{"precos":"concluida","macro":"concluida","noticias":"em_andamento","ipe":"pendente","enriquecimento":"pendente","juiza":"pendente","cadastro":"pendente","entrega":"pendente","analise":"pendente"},"consultas":22}`.
   - `pacotes_enviados` `[]`, `avisos` `["Coleta não ficou pronta até 09:45: dados de ontem."]`.
4. `saida/2026-10-21/execucao.json`: exatamente `{ "pacote": "execucao", "registros": [` (JSON quebrado, de propósito).
5. `saida/2026-10-20/execucao.json`: envelope com 1 registro: `gerado_em` `"2026-10-20T08:30:00-03:00"`, `data_referencia` `"2026-10-20"`, `rodada` 2, `inicio` `"2026-10-20T08:30:00-03:00"`, `fim` `null`, `status` `"em_andamento"`, `coleta_status` `{"consultado":false,"nota":"gatilho da coleta não consultado (etapa 8)"}`, `pacotes_enviados` `[]`, `avisos` `[]`.
6. `saida/estado/acoes.json`: `{}`. Serve para provar que pastas que não são datas são ignoradas.
7. `saida_completa/2026-10-23/execucao.json`: 1 registro com `gerado_em` `"2026-10-24T23:00:00-03:00"`, `data_referencia` `"2026-10-23"`, `rodada` 1, `inicio` `"2026-10-24T23:00:00-03:00"`, `fim` `"2026-10-24T23:03:00-03:00"`, `status` `"ok"`, `coleta_status` `{"consultado":false,"nota":"gatilho da coleta não consultado (etapa 8)"}`, `pacotes_enviados` com 2 itens (acoes 85, series_diarias 120; removidos 0), `avisos` `["Carga completa."]`.
8. `logs/rotina-2026-10-23.log.txt`:
```
Rotina de 2026-10-23 (início 00:34:09, --sem-esperar)
00:34:09 consulta 1: daily 2026-10-23-daily-080001 (cron, concluida), entrega concluida -> gerar
Saída de 2026-10-23 em C:\x\saida\2026-10-23: status ok
- Composição do Ibovespa vazia: universo = composição atual (ações do cadastro).
- Gerado depois das 10h: não entra no histórico do experimento.
Rotina de 2026-10-23 (início 08:00:00)
08:00:00 consulta 1: daily 2026-10-23-daily-080001 (cron, em_andamento), entrega em_andamento -> esperar (entrega_pendente)
08:05:00 consulta 2: daily 2026-10-23-daily-080001 (cron, em_andamento), entrega concluida -> gerar
Saída de 2026-10-23 em C:\x\saida\2026-10-23: status parcial
- Pacote noticias_dia reprovado na validação.
Rotina de 2026-10-23 (início 09:00:00)
outra rotina em andamento desde 2026-10-23T08:00:00-03:00 (pid 999). Rodada cancelada; nada foi gravado.
```
9. `logs/rotina-2026-10-24.log.txt`:
```
Rotina de 2026-10-24 (início 00:33:35, --sem-esperar)
2026-10-24 não é pregão previsto (sábado): nada a gerar.
```
10. `logs/rotina-2026-10-26.log.txt`:
```
Rotina de 2026-10-26 (início 08:00:00)
08:00:00 consulta 1: nenhum daily de hoje, entrega ausente -> esperar (sem_daily)
```
11. `logs/painel/testes-2026-10-24_101500.log.txt`:
```
# painel: acao=testes inicio=2026-10-24T10:15:00-03:00 comando=python -m pytest -q
........................................................................ [  4%]
1700 passed, 43 skipped in 95.21s
# painel: fim=2026-10-24T10:16:36-03:00 codigo=0
```
12. `logs/painel/testes-2026-10-23_090000.log.txt`:
```
# painel: acao=testes inicio=2026-10-23T09:00:00-03:00 comando=python -m pytest -q
FAILED tests/test_x.py::test_y - assert 1 == 2
2 failed, 1698 passed, 43 skipped in 99.00s
# painel: fim=2026-10-23T09:01:39-03:00 codigo=1
```
13. `docs/diagnostico_banco.md`:
```
# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-10-24 21:08 (America/Sao_Paulo)
- Banco: banco_teste
- MySQL: 8.0.46

> Este relatório só leu o banco (SELECT/SHOW). Nada foi gravado.

## Divergências × especificação

| # | Tema | Tabela | Detalhe |
|---|---|---|---|
| 1 | coluna_faltando | v1-precos | falta a coluna volume |
| 2 | falha_consulta | - | Balanços: OperationalError: x \| y |

## 1. Existência das tabelas

- 8 de 8 tabelas do contrato existem.

### Existência

| tabela | grupo | existe |
|---|---|---|
| v1-noticias | contrato | sim |

## 2. Preços (v1-precos)

- 82 dias úteis sem pregão no IBOV (inclui feriados)
- AZUL3: 1 pregões faltando (pode ser suspensão)

### Pregões por ano (IBOV)

| ano | pregoes |
|---|---|
| 2025 | 250 |

## 3. Colunas vazias

_(sem dados)_
```
14. `modelos/xgb-2026-06.meta.json`:
```json
{"modelo":"3","provisorio":true,"periodo_treino":{"inicio":"2024-01-02","fim":"2026-06-19"},"n_linhas_treino":45765,"gerado_em":"2026-10-24T18:42:20-03:00","metricas_validacao":{"auc_geral":0.5148,"auc_medio_pregao":0.5174,"taxa_acerto_top5":0.5023},"calibracao":{"ece":0.0157,"aprovada":true,"chance_exibida":false},"aviso":"modelo provisório: treinado com ~1 ano; só teste de funcionamento","teste_final":{"inicio":"2026-06-23","fim":null,"usado":false}}
```
   `modelos/xgb-m1-2026-06.meta.json`: igual, mas com `"modelo":"1"`, `"calibracao":null` e `metricas_validacao` `{"auc_geral":0.5127,"auc_medio_pregao":0.5145,"taxa_acerto_top5":0.5088}`.
   `modelos/xgb-2026-05.meta.json`: igual ao primeiro, mas com `"gerado_em":"2026-06-01T10:00:00-03:00"` e `periodo_treino.fim` `"2026-05-15"`.
15. `saida/experimento/treino/dev-2026-10-22/metricas.json`: `{"modo":"desenvolvimento","aviso_funcionamento":true,"gerado_em":"2026-10-23T10:00:00-03:00"}`
   `saida/experimento/treino/dev-2026-10-23/metricas.json`:
```json
{"modo":"desenvolvimento","aviso_funcionamento":true,"gerado_em":"2026-10-24T18:42:18-03:00",
 "periodo":{"inicio":"2024-01-02","fim":"2026-06-19","n_pregoes":616,"n_linhas":45765,"n_tickers":80,"universo":"composicao_historica","teste_final_inicio":"2026-06-23","teste_final_fim":null,"teste_final_usado":false},
 "acaso":{"5":{"media":0.4811,"p2_5":0.4638,"p97_5":0.4987}},
 "modelos":{"modelo_1":{"auc_medio_pregao":0.5145,"topk":{"5":{"taxa_acerto":0.5088,"ic_taxa":[0.4894,0.5276]}}},
            "modelo_3":{"auc_medio_pregao":0.5174,"topk":{"5":{"taxa_acerto":0.5023,"ic_taxa":[0.4836,0.5204]}}},
            "logistica":{"auc_medio_pregao":0.5218,"topk":{"5":{"taxa_acerto":0.5305,"ic_taxa":[0.5117,0.5488]}}},
            "volatilidade":{"auc_medio_pregao":0.5175,"topk":{"5":{"taxa_acerto":0.5056,"ic_taxa":[0.4847,0.5268]}}},
            "modelo_3_principais":null},
 "veredito_modelo_3":{"texto":"No top 5, o modelo 3 ficou acima do acaso, mas não superou a regra da volatilidade nem a logística."},
 "calibracao":{"ece":0.0157,"aprovada":true,"chance_exibida":false}}
```
   `saida/experimento/treino/dev-2026-10-23/relatorio.md`:
```
> **AVISO: TESTE DE FUNCIONAMENTO, NÃO É RESULTADO.**

# AVALIAÇÃO DE DESENVOLVIMENTO

## 7. Veredito

- No top 5, o modelo 3 ficou acima do acaso, mas não superou a regra da volatilidade nem a logística.
```
16. `registros/experimento/2026-10-23.top.json`: `{}`. `registros/experimento/2026-10-22.resultado.json`: `{}`.

**Verificação F0**: `.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'tests'); import tempfile, pathlib; from fabrica_painel import montar_raiz; r=montar_raiz(pathlib.Path(tempfile.mkdtemp())); print(sorted(p.relative_to(r).as_posix() for p in r.rglob('*') if p.is_file()))"`. A lista tem que trazer os `.log` (sem `.txt`) e o `.env`. Conferir também `git check-ignore -v tests/dados/painel/raiz/logs/rotina-2026-10-23.log.txt`, que deve sair vazio (não ignorado).

---

## F1. `processamento/painel/leitores.py` + `tests/test_painel_leitores.py` (depende de F0)

Funções (todas puras, sem exceção para fora):
```python
RAIZ_PADRAO = Path(__file__).resolve().parents[2]
RE_DATA_PASTA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MOTIVOS_COLETA = {"entrega_concluida": "entrega concluída", "entrega_pendente": "entrega ainda não concluída",
  "entrega_falhou": "entrega falhou", "sem_daily": "nenhum daily de hoje", "daily_agendado": "daily agendado, ainda não começou",
  "dados_atrasados": "dados atrasados", "falha_consulta": "falha ao consultar o painel da coleta",
  "sem_esperar": "rodada com --sem-esperar (coleta não estava pronta)"}
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

def ler_json(caminho: Path) -> tuple[object | None, str | None]
    # (dados, None) | (None, "não encontrado") | (None, "JSON inválido") (JSONDecodeError/UnicodeDecodeError) | (None, "não foi possível ler") (OSError)
def duracao_segundos(inicio: str | None, fim: str | None) -> int | None
    # fromisoformat nos dois; int((fim-inicio).total_seconds()); None se faltar algum, se for inválido ou se fim < inicio
def formatar_duracao(segundos: int | None) -> str
    # None -> "—"; <60 -> "N s"; <3600 -> "M min S s"; senão "H h M min"
def ler_parametros(raiz: Path) -> dict
    # yaml.safe_load de raiz/"processamento/config/parametros.yaml". Valores padrão se faltar arquivo ou chave:
    # {"modelo_oficial": False, "teste_final": {"inicio": None, "fim": None, "liberado": False},
    #  "publicar_top_provisorio": False, "pasta_saida": "saida", "pasta_logs": "logs",
    #  "trava": "saida/estado/rotina.trava", "trava_validade_horas": 6.0, "erro": None}
    # Datas: str(valor) se não for None. Arquivo ausente -> erro "parametros.yaml não encontrado"; yaml inválido -> erro "parametros.yaml ilegível".
def ler_trava(raiz: Path, params: dict, agora: datetime) -> dict
    # caminho = raiz / params["trava"]. Ausente -> {"existe": False, "ativa": False, "abandonada": False, "criada_em": None, "pid": None, "idade_min": None, "validade_horas": v}
    # Presente -> criada_txt, pid, instante = processamento.rotina.trava._ler_trava(caminho, agora)  (REUSO; só leitura)
    #   idade = agora - instante; ativa = idade <= timedelta(hours=v); abandonada = not ativa; idade_min = int(idade.total_seconds() // 60)
    # NUNCA cria nem apaga o arquivo.
def info_hoje(agora: datetime, caminho_calendario: str | None = None) -> dict
    # d = agora.astimezone(SP).date(); motivo = calendario.motivo_sem_pregao(d, caminho_calendario)
    # {"data": d.isoformat(), "dia_semana": DIAS_SEMANA[d.weekday()], "pregao": motivo is None, "motivo": motivo, "erro": None}
    # calendario.ErroCalendario -> pregao None, erro str(e)
def resumir_execucao(dados: object, data_pasta: str, tipo: str, arquivo_rel: str) -> dict
def listar_execucoes(raiz: Path, pasta: str, tipo: str) -> list[dict]
    # subpastas de raiz/pasta cujo nome casa RE_DATA_PASTA, é data válida e tem execucao.json; ordem: data desc
def ultima_execucao(itens: list[dict]) -> dict | None   # maior gerado_em (datetime) entre os legíveis
def d_mais_recente(raiz: Path, pasta_saida: str) -> date | None   # pasta de data mais nova que tem execucao.json (legível ou não)
```
Formato do item (`resumir_execucao`). Os campos vêm de `dados["registros"][0]`:
```
{"data_referencia": data_pasta, "tipo": tipo, "arquivo": arquivo_rel, "legivel": True, "erro": None,
 "rodada", "status", "inicio", "fim", "gerado_em",
 "duracao_s": duracao_segundos(inicio, fim), "duracao_texto": formatar_duracao(...) | "em andamento" se status == "em_andamento",
 "n_pacotes": len(pacotes_enviados), "n_avisos": len(avisos),
 "pacotes": [{"pacote","registros","removidos"}], "avisos": [...],
 "coleta": {"consultado", "nota", "motivo", "motivo_texto": MOTIVOS_COLETA.get(m, m), "daily": execucao_id, "origem",
            "status_execucao", "entrega_concluida_em", "entrega_hhmm": "HH:MM" em SP ou None, "etapas": dict ou None}}
```
- Se o JSON não puder ser lido (`ler_json` com erro) ou não tiver `registros` (ou vier vazio): `{"data_referencia", "tipo", "arquivo", "legivel": False, "erro": <motivo ou "formato inesperado">}` e as demais chaves `None` ou `[]`, com `n_pacotes`/`n_avisos` iguais a `None`.
- Se `coleta_status` vier `None`: `coleta = None`.

Testes com os valores esperados (`raiz = montar_raiz(tmp_path)`):
- `duracao_segundos("2026-10-24T22:46:25-03:00","2026-10-24T22:48:23-03:00") == 118`
- `duracao_segundos("2026-10-24T23:59:30-03:00","2026-10-25T00:00:45-03:00") == 75`
- `duracao_segundos("2026-10-24T22:46:25-03:00","2026-10-25T01:46:25+00:00") == 0` (fusos diferentes)
- `duracao_segundos(fim antes do início) is None`; com `None` → `None`; com `"lixo"` → `None`
- `formatar_duracao`: 118 → `"1 min 58 s"`, 0 → `"0 s"`, 45 → `"45 s"`, 3725 → `"1 h 2 min"`, None → `"—"`
- `listar_execucoes(raiz, "saida", "diaria")`:
  - datas == `["2026-10-23","2026-10-22","2026-10-21","2026-10-20"]` (a pasta `estado` é ignorada)
  - item 0: rodada 6, status `"ok"`, duracao_s 118, duracao_texto `"1 min 58 s"`, n_pacotes 7, n_avisos 3, `coleta.entrega_hhmm == "08:22"`, `coleta.motivo_texto == "entrega concluída"`, `coleta.daily == "2026-10-23-daily-080001"`, `arquivo == "saida/2026-10-23/execucao.json"`
  - item 1: status `"falhou"`, duracao_s 0, n_pacotes 0, n_avisos 1, `coleta.entrega_hhmm is None`, `coleta.motivo_texto == "entrega ainda não concluída"`
  - item 2: `legivel False`, `erro == "JSON inválido"`
  - item 3: status `"em_andamento"`, duracao_s None, duracao_texto `"em andamento"`, `coleta.consultado is False`
- `listar_execucoes(raiz, "saida_completa", "completa")`: 1 item, duracao_s 180, duracao_texto `"3 min 0 s"`, n_pacotes 2, tipo `"completa"`
- `ultima_execucao(diarias)["data_referencia"] == "2026-10-23"`; `ultima_execucao([]) is None`
- `d_mais_recente(raiz, "saida") == date(2026,10,23)`; em tmp vazio → `None`; com a pasta `saida` ausente → `listar_execucoes` devolve `[]`
- `ler_parametros(raiz)` == o dicionário padrão acima (com `inicio "2026-06-23"`, `trava_validade_horas 6.0`, `erro None`); com o yaml apagado → mesmos padrões e `erro == "parametros.yaml não encontrado"`; com yaml `"treino: [\n"` → `erro == "parametros.yaml ilegível"`
- `ler_trava`, com `AG = datetime(2026,10,23,10,0,tzinfo=SP)`:
  - sem arquivo → `existe False`, `ativa False`
  - com `{"pid": 4321, "criada_em": "2026-10-23T09:00:00-03:00"}` → `existe True`, `ativa True`, `pid "4321"`, `idade_min 60`; com `agora = 2026-10-23T15:00:01-03:00` → `ativa False`, `abandonada True`
  - conteúdo `"lixo"` + `os.utime` com mtime = (AG − 1 h) → `ativa True`, `pid "desconhecido"`
  - depois de todas as chamadas, o arquivo continua existindo com o mesmo conteúdo
- `info_hoje` (yaml real; `caminho_calendario=None`):
  - `datetime(2026,10,25,12,0,tzinfo=SP)` → `{"data":"2026-10-25","dia_semana":"domingo","pregao":False,"motivo":"domingo","erro":None}`
  - `datetime(2026,10,23,9,0,tzinfo=SP)` → `pregao True`, `motivo None`
  - `datetime(2026,10,24,2,0,tzinfo=timezone.utc)` → `data "2026-10-23"` (fuso)
  - `datetime(2026,10,12,9,0,tzinfo=SP)` → `pregao False`, `motivo "Nossa Senhora Aparecida"`

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_leitores.py`.

---

## F2. `processamento/painel/relatorios.py` + `tests/test_painel_relatorios.py` (depende de F0; paralela a F1/F3/F5)

Não importa `leitores.py`. Recebe `params` como dicionário com as chaves do formato de `ler_parametros` (ver F1) e tem a sua própria `_ler_json` (5 linhas, mesmo contrato).

```python
RE_INICIO = re.compile(r"^Rotina de (\d{4}-\d{2}-\d{2}) \(início (\d{2}:\d{2}:\d{2})(, --sem-esperar)?\)$")
RE_CONSULTA = re.compile(r"^(\d{2}:\d{2}:\d{2}) consulta (\d+): (.*)$")
RE_SAIDA = re.compile(r"^Saída de \S+ em .+: status (\w+)$")
RE_SEM_PREGAO = re.compile(r"não é pregão previsto \((.+)\): nada a gerar\.$")
RE_LOG_ROTINA = re.compile(r"^rotina-(\d{4}-\d{2}-\d{2})\.log$")

def analisar_log_rotina(texto: str) -> list[dict]
def ler_logs_rotina(pasta_logs: Path, max_arquivos: int = 10) -> dict
def ler_diagnostico(caminho: Path) -> dict
def trava_teste_final(params: dict, raiz: Path) -> dict
def caminho_ultimo_relatorio(raiz: Path) -> Path | None
def ler_experimento(raiz: Path, params: dict) -> dict
def ler_ultimo_pytest(pasta_logs_painel: Path) -> dict
```

`analisar_log_rotina`:
- Uma rodada por linha que casa `RE_INICIO`: `{"data", "inicio", "sem_esperar": bool, "consultas": [{"hora","numero":int,"texto"}], "resultado": "incompleta", "detalhe": None, "avisos": [], "outras": []}`.
- Linhas antes da primeira rodada e linhas em branco são ignoradas. Usar `splitlines()`.
- Dentro da rodada, nesta ordem de teste:
  1. `RE_CONSULTA` → consulta.
  2. `RE_SAIDA` → `resultado = grupo 1`.
  3. `RE_SEM_PREGAO` (`search`) → `resultado "sem_pregao"`, `detalhe = grupo 1`.
  4. Começa com `"outra rotina em andamento"` → `"trava"`, `detalhe = linha`.
  5. Começa com `"Saída não gerada:"` ou `"Coleta não terminou até"` → `"falhou"`, `detalhe = linha`.
  6. Começa com `"Configuração do banco incompleta"` → `"configuracao"`, `detalhe = linha`.
  7. Começa com `"Falha ao conectar ao banco"` ou contém `"Rodada interrompida"` → `"sem_banco"`, `detalhe = linha`.
  8. Começa com `"- "` → `avisos.append(linha[2:])`; começa com `"Aviso: "` → `avisos.append(linha[7:])`.
  9. Qualquer outra → `outras`.

`ler_logs_rotina`:
- Lê os arquivos de `pasta_logs` que casam `RE_LOG_ROTINA`, ordenados por data desc, até `max_arquivos`.
- Devolve `{"disponivel": True, "motivo": None, "arquivos": [{"arquivo": nome, "data": d, "rodadas": [...]}]}`.
- Sem pasta ou sem arquivo → `{"disponivel": False, "motivo": "nenhum log da rotina em logs/", "arquivos": []}`.

`ler_diagnostico`:
- Ausente → `{"disponivel": False, "motivo": "docs/diagnostico_banco.md não encontrado (rode o diagnóstico)"}`.
- Sem a linha `## Divergências × especificação` → `{"disponivel": False, "motivo": "formato não reconhecido"}`.
- Senão, devolve `{"disponivel": True, "motivo": None, "gerado_em": <texto depois de "- Gerado em: ">, "sem_divergencias": bool, "divergencias": [...], "secoes": [...]}`.
- **Não devolver as linhas `Banco:` nem `MySQL:`.**
- As linhas de tabela entre o título das divergências e a primeira `## N.` viram divergências. Linhas que começam com `|`, menos o cabeçalho e a linha `|---`, são divididas com `re.split(r"(?<!\\)\|", linha.strip().strip("|"))`; cada célula passa por `.strip().replace("\\|", "|")` e gera `{"numero","tema","tabela","detalhe"}`.
- Seções: `^## (\d+)\. (.+)$` → `{"numero": int, "titulo"}`; `notas` = as linhas `"- "` (sem o prefixo) até o primeiro `### ` ou o próximo `## `.

`trava_teste_final`:
- `docs/teste_final_usado.json` existe → `estado "usado"`, texto "O teste final já foi usado (uso único)."
- Senão, `fim is None` → `"ativa"`, "Trava ativa: treino.teste_final.fim vazio; o teste final não roda."
- Senão, `not liberado` → `"definido_nao_liberado"`, "Fim definido, mas o teste final ainda não foi liberado (treino.teste_final.liberado = false)."
- Senão → `"liberado"`, "Liberado: falta rodar o treino com --teste-final (uso único)."
- O retorno sempre inclui `inicio`, `fim` e `liberado`.

`ler_experimento`:
- `top_publicado = modelo_oficial or publicar_top_provisorio`.
- `modelo_em_uso`: o mais novo `modelos/xgb-(\d{4}-\d{2})\.meta\.json` (pelo AAAA-MM). `modelo_sombra`: o mais novo `modelos/xgb-m1-(\d{4}-\d{2})\.meta\.json`. Cada um é resumido como `{"arquivo","mes","modelo","provisorio","periodo_treino","n_linhas_treino","gerado_em","auc_medio_pregao","acerto_top5" (de metricas_validacao.taxa_acerto_top5),"calibracao_aprovada" (None se calibracao for null),"chance_exibida","aviso"}`, ou `None`.
- `situacao_modelo = "oficial" if modelo_oficial and modelo_em_uso and modelo_em_uso["provisorio"] is False else "provisório"`.
- `n_meta` = quantidade de `modelos/*.meta.json`.
- `desenvolvimento`: a pasta `saida/experimento/treino/dev-AAAA-MM-DD` com a maior data no nome; resumo do `metricas.json` (formato no teste abaixo). Pula modelos `null` e segue a ordem `modelo_3, modelo_1, logistica, volatilidade`, com os rótulos "Modelo 3 (com notícias)", "Modelo 1 (sem notícias)", "Regressão logística", "Regra da volatilidade". Chaves `topk` e `acaso` são **texto** (`"5"`). `tem_relatorio` = existe `relatorio.md`. Sem pasta → `{"disponivel": False, "motivo": "nenhum treino de desenvolvimento em saida/experimento/treino/"}`.
- `registros`: `{"tops": n *.top.json, "resultados": n *.resultado.json, "ultimo_top": data do *.top.json mais novo ou None}` em `registros/experimento/`.
- `mostrar_aviso = (not modelo_oficial) or desenvolvimento.get("aviso_funcionamento") is not False`.
- `trava_teste_final` = `trava_teste_final(params, raiz)`.

`ler_ultimo_pytest`:
- Pega o arquivo mais novo (pelo nome) `testes-*.log` em `pasta_logs_painel`. Sem nenhum → `{"disponivel": False, "motivo": "nenhum pytest rodado pelo painel ainda"}`.
- Cabeçalho `^# painel: acao=\S+ inicio=(\S+) comando=` → `inicio`.
- Rodapé `^# painel: fim=(\S+) codigo=(-?\d+)` → `fim` e `codigo`.
- Resumo: a última linha que casa `^=*\s*(no tests ran|\d+ (passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?))`. `contagens` = todos os pares `(\d+) (\w+)` dessa linha, normalizando `error` → `errors` e `warning` → `warnings`. `tempo` = `re.search(r" in ([\d.]+s)", linha)`.
- `falhas` = as linhas que começam com `FAILED ` ou `ERROR ` (no máximo 20).
- `aprovado = codigo == 0` (ou `None` sem rodapé); `interrompido = rodapé ausente`.

Testes com os valores esperados (`raiz = montar_raiz(tmp_path)`):
- `ler_logs_rotina(raiz/"logs")`:
  - arquivos (datas) `["2026-10-26","2026-10-24","2026-10-23"]`
  - 10-26: 1 rodada, `resultado "incompleta"`, 1 consulta
  - 10-24: 1 rodada `{"inicio":"00:33:35","sem_esperar":True,"resultado":"sem_pregao","detalhe":"sábado"}`
  - 10-23: 3 rodadas
    - r0: `inicio "00:34:09"`, `sem_esperar True`, consultas `[{"hora":"00:34:09","numero":1,"texto":"daily 2026-10-23-daily-080001 (cron, concluida), entrega concluida -> gerar"}]`, `resultado "ok"`, 2 avisos (o 1º == "Composição do Ibovespa vazia: universo = composição atual (ações do cadastro).")
    - r1: `sem_esperar False`, 2 consultas, `resultado "parcial"`, `avisos == ["Pacote noticias_dia reprovado na validação."]`
    - r2: 0 consultas, `resultado "trava"`, `detalhe` == a linha inteira, `avisos []`
  - em pasta vazia → `disponivel False`
- `analisar_log_rotina("lixo\n")` → `[]`; texto com `"Configuração do banco incompleta: x"` dentro de uma rodada → `"configuracao"`
- `ler_diagnostico(raiz/"docs/diagnostico_banco.md")`:
  - `gerado_em "2026-10-24 21:08 (America/Sao_Paulo)"`, `sem_divergencias False`
  - `divergencias == [{"numero":"1","tema":"coluna_faltando","tabela":"v1-precos","detalhe":"falta a coluna volume"},{"numero":"2","tema":"falha_consulta","tabela":"-","detalhe":"Balanços: OperationalError: x | y"}]`
  - `secoes == [{"numero":1,"titulo":"Existência das tabelas","notas":["8 de 8 tabelas do contrato existem."]},{"numero":2,"titulo":"Preços (v1-precos)","notas":["82 dias úteis sem pregão no IBOV (inclui feriados)","AZUL3: 1 pregões faltando (pode ser suspensão)"]},{"numero":3,"titulo":"Colunas vazias","notas":[]}]`
  - `"banco_teste" not in json.dumps(resultado)`
  - arquivo tmp com `"## Divergências × especificação\n\nNenhuma divergência encontrada.\n\n## 1. X\n\n- a\n"` → `sem_divergencias True`, `divergencias []`, `secoes [{"numero":1,"titulo":"X","notas":["a"]}]`
  - arquivo ausente → `disponivel False`; arquivo `"oi"` → `motivo "formato não reconhecido"`
- `ler_experimento(raiz, PARAMS)`, com `PARAMS = {"modelo_oficial": False, "teste_final": {"inicio":"2026-06-23","fim":None,"liberado":False}, "publicar_top_provisorio": False, "pasta_saida":"saida","pasta_logs":"logs","trava":"saida/estado/rotina.trava","trava_validade_horas":6.0,"erro":None}`:
  - `situacao_modelo "provisório"`, `top_publicado False`, `mostrar_aviso True`, `trava_teste_final.estado "ativa"`, `n_meta 3`
  - `modelo_em_uso == {"arquivo":"xgb-2026-06.meta.json","mes":"2026-06","modelo":"3","provisorio":True,"periodo_treino":{"inicio":"2024-01-02","fim":"2026-06-19"},"n_linhas_treino":45765,"gerado_em":"2026-10-24T18:42:20-03:00","auc_medio_pregao":0.5174,"acerto_top5":0.5023,"calibracao_aprovada":True,"chance_exibida":False,"aviso":"modelo provisório: treinado com ~1 ano; só teste de funcionamento"}`
  - `modelo_sombra["arquivo"] == "xgb-m1-2026-06.meta.json"`, `modelo_sombra["calibracao_aprovada"] is None`
  - `desenvolvimento`: `disponivel True`, `pasta "dev-2026-10-23"`, `modo "desenvolvimento"`, `aviso_funcionamento True`, `gerado_em "2026-10-24T18:42:18-03:00"`, `periodo["n_pregoes"] == 616`, `acaso_top5 == {"media":0.4811,"faixa":[0.4638,0.4987]}`, `modelos == [{"nome":"modelo_3","rotulo":"Modelo 3 (com notícias)","auc_medio_pregao":0.5174,"acerto_top5":0.5023,"ic_top5":[0.4836,0.5204]},{"nome":"modelo_1","rotulo":"Modelo 1 (sem notícias)","auc_medio_pregao":0.5145,"acerto_top5":0.5088,"ic_top5":[0.4894,0.5276]},{"nome":"logistica","rotulo":"Regressão logística","auc_medio_pregao":0.5218,"acerto_top5":0.5305,"ic_top5":[0.5117,0.5488]},{"nome":"volatilidade","rotulo":"Regra da volatilidade","auc_medio_pregao":0.5175,"acerto_top5":0.5056,"ic_top5":[0.4847,0.5268]}]`, `veredito` == o texto do fixture, `calibracao == {"ece":0.0157,"aprovada":True,"chance_exibida":False}`, `tem_relatorio True`
  - `registros == {"tops":1,"resultados":1,"ultimo_top":"2026-10-23"}`
  - variações:
    - `modelo_oficial True` (o meta continua com `provisorio true`) → `situacao_modelo "provisório"`
    - `publicar_top_provisorio True` → `top_publicado True`
    - `fim "2026-11-30"` → `trava "definido_nao_liberado"`; mais `liberado True` → `"liberado"`; criando `docs/teste_final_usado.json` → `"usado"`
    - apagando `modelos/` e `saida/experimento` → `modelo_em_uso None` e `desenvolvimento.disponivel False`, sem exceção
- `caminho_ultimo_relatorio(raiz) == raiz/"saida/experimento/treino/dev-2026-10-23/relatorio.md"`; sem pasta → `None`
- `ler_ultimo_pytest(raiz/"logs/painel")`:
  - `{"disponivel":True,"arquivo":"testes-2026-10-24_101500.log","inicio":"2026-10-24T10:15:00-03:00","fim":"2026-10-24T10:16:36-03:00","codigo":0,"aprovado":True,"interrompido":False,"contagens":{"passed":1700,"skipped":43},"tempo":"95.21s","falhas":[]}`
  - apagando o arquivo de 10-24 → `codigo 1`, `aprovado False`, `contagens {"failed":2,"passed":1698,"skipped":43}`, `falhas ["FAILED tests/test_x.py::test_y - assert 1 == 2"]`
  - arquivo sem rodapé → `codigo None`, `aprovado None`, `interrompido True`
  - pasta vazia → `disponivel False`

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_relatorios.py`.

---

## F3. `processamento/painel/acoes.py` + `tests/test_painel_acoes.py` (independente; pode começar já)

```python
@dataclass(frozen=True)
class Acao:
    id: str; titulo: str; usa_banco: bool; pode_parar: bool

ACOES = {
  "rotina": Acao("rotina", "Rodar a rotina de hoje", True, False),
  "carga": Acao("carga", "Gerar a carga completa", True, False),
  "diagnostico": Acao("diagnostico", "Rodar o diagnóstico do banco", True, False),
  "testes": Acao("testes", "Rodar os testes (pytest)", False, True),
}
SIGNIFICADOS = {
  "rotina": {0: "ok, parcial ou dia sem pregão (veja o log)", 2: "configuração (banco, parâmetros ou calendário)",
             3: "conexão com o banco ou sessão que não é só leitura", 4: "falhou: coleta não ficou pronta ou nenhum pacote gerado",
             5: "outra rotina em andamento (trava)"},
  "carga": {0: "ok ou parcial", 2: "configuração ou pasta recusada", 3: "conexão com o banco", 4: "falhou"},
  "diagnostico": {0: "relatório gerado", 2: "configuração do banco incompleta", 3: "sessão não é só leitura ou falha de conexão"},
  "testes": {0: "todos os testes passaram", 1: "há testes falhando", 2: "interrompido", 3: "erro interno do pytest",
             4: "uso incorreto do pytest", 5: "nenhum teste encontrado"},
}
def significado(acao_id: str, codigo: int | None, parado: bool) -> str | None
    # parado -> "parado pelo painel"; None -> None; senão SIGNIFICADOS[acao_id].get(codigo, f"código {codigo}")
def montar_comando(acao_id: str, *, hoje: date, d_carga: date | None) -> list[str] | None
    # rotina: [sys.executable, "-m", "processamento.rotina", "--data", hoje.isoformat(), "--sem-esperar"]
    # carga: None se d_carga is None; senão [sys.executable, "-m", "processamento.saida", "--data", d_carga.isoformat(), "--completo"]
    # diagnostico: [sys.executable, "-m", "processamento.diagnostico"]
    # testes: [sys.executable, "-m", "pytest", "-q"]
    # id desconhecido: levanta KeyError
def comando_texto(argv: list[str]) -> str     # " ".join(["python", *argv[1:]])
def ambiente_filho(acao_id: str, base: Mapping[str, str]) -> dict[str, str]
    # dict(base) + PYTHONIOENCODING="utf-8" + PYTHONUNBUFFERED="1"; se acao_id == "testes": remove PROC_TESTES_COM_BANCO
    # NÃO definir PYTHONUTF8 (mudaria a codificação padrão de open() nos comandos existentes)

class Executor:
    def __init__(self, raiz: Path, pasta_logs_painel: Path, *, relogio=None, ambiente_base=None,
                 max_linhas: int = 5000, manter_logs: int = 20): ...
    def iniciar(self, acao_id: str, argv: list[str]) -> tuple[bool, str]
    def parar(self) -> tuple[bool, str]
    def rodando(self) -> bool
    def estado(self, desde: int | None = None) -> dict
    def esperar(self, timeout: float) -> bool    # para testes: True se terminou
```

Regras do Executor:
- Um `threading.Lock` protege todo o estado. **Uma ação por vez**: se já há uma rodando, `iniciar` devolve `(False, f"outra ação em andamento: {titulo}")`.
- `iniciar` recusa com `(False, "ação desconhecida")` se `acao_id not in ACOES`, e com `(False, "comando inválido")` se `argv` não for uma lista de `str` não vazia com `argv[0] == sys.executable`.
- `subprocess.Popen(argv, cwd=str(raiz), env=ambiente_filho(acao_id, ambiente_base or os.environ), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)`. **Nunca `shell=True`.** Um `OSError` vira `(False, f"não foi possível iniciar ({type(e).__name__})")`.
- Log em `pasta_logs_painel/f"{acao_id}-{inicio:%Y-%m-%d_%H%M%S}.log"`. Se o nome já existir, acrescentar `_2`, `_3`, etc.; criar a pasta com `mkdir(parents=True, exist_ok=True)`.
  - 1ª linha: `f"# painel: acao={acao_id} inicio={inicio.isoformat(timespec='seconds')} comando={comando_texto(argv)}"`.
  - Rodapé: `f"# painel: fim={fim_iso} codigo={codigo}"`, mais `" parado=sim"` se a ação foi parada.
  - **Esse formato é o que F2 lê.**
- Uma thread de leitura (daemon) faz `for linha in proc.stdout`: tira o `"\n"`/`"\r"`, acrescenta ao buffer (deque com `maxlen=max_linhas`, mais um contador total), grava no log e dá `flush`. No fim: `proc.wait()`, registra `codigo`, `fim` e `significado`, escreve o rodapé, marca `rodando=False` e apaga os logs mais antigos desse `acao_id` além de `manter_logs` (só arquivos `f"{acao_id}-*.log"` dentro de `pasta_logs_painel`).
- `parar`: só se estiver rodando e `ACOES[id].pode_parar`; faz `proc.terminate()`, marca `parado=True` e devolve `(True, "parando")`. Caso contrário devolve `(False, "esta ação não pode ser parada")` ou `(False, "nada rodando")`.
- `estado(desde)` devolve `{"id","titulo","rodando","inicio","fim","codigo","significado","pode_parar","arquivo_log" (relativo à raiz, posix),"linhas","proximo","total_linhas"}`.
  - `desde=None` → `linhas []`. Os índices são absolutos: devolver as linhas com índice ≥ `desde` que ainda estão no buffer; `proximo = total_linhas`.
  - Sem nenhuma ação ainda: `id None`, `rodando False`, `linhas []`, `proximo 0`.
- O relógio padrão é `lambda: datetime.now(SP)`.

Testes com os valores esperados (todos em `tmp_path`; os "comandos" são `sys.executable -c ...`, nunca a rotina de verdade):
- `montar_comando("rotina", hoje=date(2026,10,23), d_carga=None) == [sys.executable,"-m","processamento.rotina","--data","2026-10-23","--sem-esperar"]`
- `montar_comando("carga", hoje=..., d_carga=date(2026,10,23)) == [sys.executable,"-m","processamento.saida","--data","2026-10-23","--completo"]`; com `d_carga=None` → `None`
- `montar_comando("diagnostico", …)` → `[sys.executable,"-m","processamento.diagnostico"]`; `montar_comando("testes", …)` → `[sys.executable,"-m","pytest","-q"]`
- `pytest.raises(KeyError)` com `"apagar"`
- `comando_texto(montar_comando("carga", …)) == "python -m processamento.saida --data 2026-10-23 --completo"`
- `ambiente_filho("testes", {"PATH":"x","PROC_TESTES_COM_BANCO":"1"}) == {"PATH":"x","PYTHONIOENCODING":"utf-8","PYTHONUNBUFFERED":"1"}`; `ambiente_filho("rotina", {"PATH":"x"}) == {"PATH":"x","PYTHONIOENCODING":"utf-8","PYTHONUNBUFFERED":"1"}`; `"PYTHONUTF8" not in` nenhum dos dois
- `significado("rotina",5,False) == "outra rotina em andamento (trava)"`, `significado("testes",9,False) == "código 9"`, `significado("testes",1,True) == "parado pelo painel"`
- Executor:
  - `iniciar("testes", [sys.executable,"-c","print('linha 1'); print('Ação com acentuação: São Paulo'); raise SystemExit(3)"])` → `(True, …)`; `esperar(30)` → `True`
  - `estado(0)["linhas"] == ["linha 1","Ação com acentuação: São Paulo"]`, `codigo 3`, `rodando False`, `proximo 2`; `estado(1)["linhas"] == ["Ação com acentuação: São Paulo"]`; `estado(None)["linhas"] == []`
  - o log em `pasta_logs_painel` começa com `"# painel: acao=testes inicio="`, contém as 2 linhas e termina com `"codigo=3"`
- Ambiente: o filho com `print(os.environ.get('PYTHONIOENCODING'), os.environ.get('PROC_TESTES_COM_BANCO'))`, com `ambiente_base={"PROC_TESTES_COM_BANCO":"1", **os.environ}` e ação `"testes"` → a linha é `"utf-8 None"`
- Concorrência: inicia um filho com `time.sleep(5)`; um segundo `iniciar("rotina", [sys.executable,"-c","pass"])` devolve `(False, "outra ação em andamento: Rodar os testes (pytest)")`; `parar()` → `(True, "parando")`; `esperar(30)`; `significado == "parado pelo painel"`; o rodapé contém `"parado=sim"`
- Parar sem poder: `"diagnostico"` com sleep → `parar() == (False, "esta ação não pode ser parada")`; depois esperar terminar (usar `sleep(1)`)
- Recusas: `iniciar("apagar", [sys.executable,"-c","pass"]) == (False, "ação desconhecida")`; `iniciar("testes", ["cmd","/c","dir"]) == (False, "comando inválido")`; `iniciar("testes", "python") == (False, "comando inválido")`
- Retenção: criar 22 arquivos `testes-2026-01-01_0000NN.log` falsos, rodar uma ação `testes` (`pass`) e esperar → restam 20 arquivos `testes-*.log`, incluindo o novo

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_acoes.py`.

---

## F5. `processamento/painel/pagina.html` + `tests/test_painel_pagina.py` (independente; pode começar já)

É uma página única, com CSS e JS inline e **sem nenhum recurso externo** (sem `http://`/`https://`, sem CDN, sem fontes externas). O token entra pelo marcador literal `__TOKEN_PAINEL__`, numa linha `const TOKEN = "__TOKEN_PAINEL__";`.

**Regra de segurança obrigatória**: montar o DOM só com `document.createElement` + `textContent`. É **proibido** usar `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` e `eval`, porque avisos e linhas de log vêm de arquivos.

Dados (contrato do servidor, F4):
- `GET /api/painel` → JSON com as chaves `gerado_em, hoje, trava, agora, historico{diarias,completas}, etapas, saude, experimento, testes, acao, botoes`. Os formatos são os de F1, F2 e F3. `botoes[id] = {"titulo","comando","habilitado","motivo","aviso"}`; `agora` pode trazer `possivelmente_interrompida: bool`.
- `GET /api/acao?desde=N` → `estado` do Executor.
- `POST /api/acao/iniciar` com corpo `{"acao": id}` e cabeçalhos `Content-Type: application/json` e `X-Painel-Token: TOKEN` → 202 `{"ok":true}`, ou 4xx `{"erro": "..."}`.
- `POST /api/acao/parar` (mesmos cabeçalhos, corpo `{}`).
- `GET /api/relatorio` → texto do relatório (abre num link com `target="_blank"`).

Layout (de cima para baixo; cada seção com título e uma frase de explicação para a banca):
- Cabeçalho: "Painel de operação do processamento (TCC)". Subtítulo: "Mostra o que o processamento fez e permite rodar os comandos. Não mostra indicadores das ações."
- `#agora` "Agora":
  - hoje (data, dia da semana, "é pregão" ou "não é pregão: <motivo>"; ou o erro do calendário)
  - faixa da trava: se `trava.ativa` → "Uma rotina está rodando desde <criada_em> (pid N)"; se `abandonada` → "Trava antiga (mais de 6 h): a próxima rotina apaga sozinha"
  - última execução: status (selo colorido: ok verde, parcial amarelo, falhou vermelho, em_andamento azul), data, rodada, início, fim, duração; com `possivelmente_interrompida` → "em andamento, mas nada está rodando: pode ter sido interrompida"
  - coleta: daily, origem, "entrega concluída às HH:MM" (ou `motivo_texto`); as 9 etapas como selos
  - sem execução → "Nenhuma execução encontrada em saida/"
- `#comandos` "Comandos":
  - um botão por item de `botoes`, com o `comando` em fonte monoespaçada embaixo. Com `habilitado=false`, o botão fica `disabled` e o `motivo` aparece ao lado
  - ao clicar: `confirm(aviso + "\n\nComando: " + comando)`, depois POST
  - botão "Parar" visível só com `acao.rodando && acao.pode_parar`; botão "Atualizar"
  - `#log`: um `<pre>` com rolagem automática; status "rodando…" ou "terminou: código N (significado)"
- `#historico` "Histórico de execuções":
  - tabela com Data, Tipo (diária/carga completa), Rodada, Duração, Status, Pacotes, Avisos; linha ilegível → "arquivo ilegível (erro)"
  - clicar numa linha mostra `#detalhe` (avisos em lista, pacotes com registros/removidos, coleta e etapas)
  - nota: "Cada dia guarda só a última rodada; as anteriores aparecem em Etapas (logs)."
- `#etapas` "Etapas das rodadas (logs da rotina)": para cada arquivo (data), as rodadas da mais nova para a mais antiga, com início, `--sem-esperar`, consultas à coleta (hora e texto), resultado e detalhe, e avisos. Nota: "O log não registra a hora de fim nem o tempo de cada etapa interna."
- `#saude` "Saúde dos dados (diagnóstico do banco)": gerado em; "Nenhuma divergência" (verde) ou tabela Tema/Tabela/Detalhe; seções com as notas em lista (recolhíveis com `<details>`).
- `#experimento` "Experimento (XGBoost + notícias)":
  - com `mostrar_aviso`: uma faixa vermelha fixa **"TESTE DE FUNCIONAMENTO, NÃO É RESULTADO"**
  - situação do modelo (provisório/oficial); top 5 publicado na interface? (sim/não); trava do teste final (texto)
  - modelo em uso (mês, período de treino, linhas, AUC médio por pregão, acerto top 5); modelo sombra
  - último treino de desenvolvimento: período, tabela dos modelos (rótulo, AUC por pregão, acerto top 5, IC), faixa do acaso, veredito, link "Ver relatório completo" (`/api/relatorio`) quando `tem_relatorio`
  - registros (tops/resultados)
- `#testes` "Testes": último pytest do painel (fim, aprovado/reprovado, contagens, tempo, falhas); sem nenhum → "Nenhum pytest rodado pelo painel ainda."
- Rodapé: "Só neste computador (127.0.0.1). O painel não acessa o banco e não lê o .env; os botões chamam os comandos do projeto."

Formatação:
- Fração → `"50,2%"` (1 casa, vírgula). AUC com 3 casas e vírgula.
- ISO → `"24/10/2026 22:46"`.
- Qualquer seção com `disponivel === false` mostra o `motivo` em cinza.

Comportamento:
- Ao carregar, `GET /api/painel`. Se `acao.rodando`, faz polling de `/api/acao?desde=n` a cada 1000 ms, acrescentando linhas; ao terminar, recarrega `/api/painel`.
- Parado, recarrega `/api/painel` a cada 30 s.
- Erro de rede → mensagem "Painel sem resposta".

Testes (`tests/test_painel_pagina.py`; leem o arquivo com `encoding="utf-8"`):
- contém `"__TOKEN_PAINEL__"`, `"TESTE DE FUNCIONAMENTO, NÃO É RESULTADO"`, `'id="agora"'`, `'id="historico"'`, `'id="etapas"'`, `'id="saude"'`, `'id="experimento"'`, `'id="testes"'`, `'id="log"'`, `"/api/painel"`, `"/api/acao/iniciar"`, `"X-Painel-Token"`
- não contém: `"innerHTML"`, `"outerHTML"`, `"insertAdjacentHTML"`, `"document.write"`, `"eval("`, `"http://"`, `"https://"`

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_pagina.py`.

---

## F4. `processamento/painel/servidor.py` + `__init__.py` + `__main__.py` + `tests/test_painel_servidor.py` (depois de F1, F2, F3, F5)

```python
PORTA_PADRAO = 8765
def host_permitido(host: str | None, porta: int) -> bool      # host in {f"127.0.0.1:{porta}", f"localhost:{porta}"}
def origem_permitida(origem: str | None, porta: int) -> bool  # origem in {f"http://127.0.0.1:{porta}", f"http://localhost:{porta}"}
def estado_botoes(params, trava, hoje, d_carga, executor, agora) -> dict
def montar_painel(raiz: Path, executor: Executor, agora: datetime, caminho_calendario: str | None = None) -> dict
def criar_servidor(raiz: Path = leitores.RAIZ_PADRAO, porta: int = PORTA_PADRAO, *, executor: Executor | None = None,
                   montar_comando=acoes.montar_comando, relogio=None, caminho_calendario: str | None = None) -> ThreadingHTTPServer
def main(argv=None) -> int
```

`montar_painel`: cada parte vai dentro de `_seguro(func, *args)`, que devolve `{"disponivel": False, "motivo": f"erro ao ler ({type(e).__name__})"}` se houver exceção.
- `params = leitores.ler_parametros(raiz)`
- `trava = leitores.ler_trava(raiz, params, agora)`
- `hoje = leitores.info_hoje(agora, caminho_calendario)`
- `diarias = leitores.listar_execucoes(raiz, params["pasta_saida"], "diaria")`
- `completas = leitores.listar_execucoes(raiz, "saida_completa", "completa")`
- `agora_item = leitores.ultima_execucao(diarias)`; se não for `None`, recebe `possivelmente_interrompida = status == "em_andamento" and not trava["ativa"] and not executor.rodando()`
- `etapas = relatorios.ler_logs_rotina(raiz / params["pasta_logs"])`
- `saude = relatorios.ler_diagnostico(raiz / "docs" / "diagnostico_banco.md")`
- `experimento = relatorios.ler_experimento(raiz, params)`
- `testes = relatorios.ler_ultimo_pytest(raiz / params["pasta_logs"] / "painel")`
- `acao = executor.estado(None)`
- `botoes = estado_botoes(params, trava, hoje, leitores.d_mais_recente(raiz, params["pasta_saida"]), executor, agora)`
- `gerado_em = agora.isoformat(timespec="seconds")`
- Resultado: `{"gerado_em","hoje","trava","agora": agora_item,"historico":{"diarias","completas"},"etapas","saude","experimento","testes","acao","botoes"}`.

`estado_botoes`: para cada `id` em `ACOES` → `{"titulo","comando": comando_texto(argv) ou None,"habilitado","motivo","aviso"}`. Regras, na ordem:
1. Com `executor.rodando()`, todos ficam desabilitados, com `motivo f"Aguarde: {titulo em andamento} está rodando"`.
2. Com `trava["ativa"]`, os que têm `usa_banco` ficam desabilitados, com `motivo "Uma rotina já está rodando (trava de saida/estado/rotina.trava)"`.
3. `rotina`:
   - `params["teste_final"]["fim"]` preenchido → desabilitado, `"Em produção a rotina roda pelo Agendador de Tarefas; não rodar pelo painel."`
   - aviso: se `hoje["erro"]`, `f"Calendário: {erro}. A rotina vai sair com código 2."`; se `hoje["pregao"] is False`, `f"Hoje ({motivo}) não é pregão: a rotina sai sem gravar nada."`; senão, `"Com --sem-esperar, se a coleta de hoje ainda não terminou, a rotina gera mesmo assim, com aviso, e grava a pasta de hoje e o top 5 do dia."`
4. `carga`: com `d_carga None` → desabilitado, `"Nenhuma rotina diária ainda (pasta saida/AAAA-MM-DD)."`. Aviso: `f"Gera os pacotes inteiros em saida_completa/{d_carga}/; não mexe no envio diário nem nos registros."`
5. `diagnostico`: aviso `"Só lê o banco; reescreve docs/diagnostico_banco.md."`
6. `testes`: aviso `"Não usa o banco; leva alguns minutos."`

- "Hoje" = `agora.astimezone(SP).date()`. O argv vem de `montar_comando(id, hoje=..., d_carga=...)`.

Handler (classe interna; o contexto fica em atributos do servidor: `srv.raiz`, `srv.porta`, `srv.token`, `srv.executor`, `srv.montar_comando`, `srv.relogio`, `srv.caminho_calendario`, `srv.pagina`):
- **Todas as requisições**: se `host_permitido(self.headers.get("Host"), srv.porta)` for falso → 403 `{"erro":"host não permitido"}` (proteção contra DNS rebinding).
- `do_GET`: usa `urlsplit(self.path).path` **exato**. **Nunca servir arquivo do disco por caminho vindo da URL.**
  - `"/"` → `srv.pagina.replace("__TOKEN_PAINEL__", srv.token)`, `text/html; charset=utf-8`
  - `"/api/painel"` → `montar_painel(...)`
  - `"/api/acao"` → `executor.estado(desde)`; `desde = int(parse_qs(query).get("desde",["0"])[0])` limitado a ≥ 0 (valor inválido vira 0)
  - `"/api/relatorio"` → texto de `relatorios.caminho_ultimo_relatorio(raiz)` (`text/plain; charset=utf-8`), ou 404 `{"erro":"sem relatório"}`
  - qualquer outro caminho → 404 `{"erro":"não encontrado"}`
- `do_POST`:
  - Host conferido (acima)
  - `origem_permitida(self.headers.get("Origin"), porta)`; se falso → 403 `{"erro":"origem não permitida"}`
  - `hmac.compare_digest(self.headers.get("X-Painel-Token",""), token)`; se falso → 403 `{"erro":"token inválido"}`
  - `Content-Length` > 1024 → 413 `{"erro":"corpo grande demais"}`
  - `"/api/acao/iniciar"`:
    - corpo JSON com `acao` str em `ACOES`; senão 400 `{"erro":"ação desconhecida"}`
    - recalcula `montar_painel`/`estado_botoes` **no servidor**: botão não habilitado → 409 `{"erro": motivo}`
    - `argv = srv.montar_comando(id, hoje=..., d_carga=...)`; `None` → 409
    - `ok, msg = executor.iniciar(id, argv)` → 202 `{"ok":True,"acao":id}` ou 409 `{"erro":msg}`
  - `"/api/acao/parar"` → `executor.parar()` → 200 `{"ok":True}` ou 409 `{"erro":msg}`
  - outro caminho → 404
- Cabeçalhos de toda resposta: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`. No HTML, também `Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`.
- JSON com `json.dumps(..., ensure_ascii=False).encode("utf-8")` e `application/json; charset=utf-8`.
- `log_message` sobrescrito para não fazer nada (sem barulho no terminal).
- PUT/DELETE etc.: o padrão do `BaseHTTPRequestHandler` responde 501.

`criar_servidor`:
- `ThreadingHTTPServer(("127.0.0.1", porta), Handler)`, com `daemon_threads = True`.
- `srv.porta = srv.server_address[1]` (dá suporte à porta 0).
- `srv.token = secrets.token_urlsafe(24)`.
- `srv.pagina = (Path(__file__).parent / "pagina.html").read_text(encoding="utf-8")`.
- Executor padrão: `acoes.Executor(raiz, raiz / ler_parametros(raiz)["pasta_logs"] / "painel", relogio=relogio)`.
- Relógio padrão: `lambda: datetime.now(SP)`.

`main(argv)`:
- argparse com `prog="python -m processamento.painel"`, `--porta` (int, padrão 8765) e `--sem-navegador`.
- Tenta `criar_servidor(porta=args.porta)`; se der `OSError` (porta ocupada), tenta `porta=0` e imprime o aviso.
- Imprime `f"Painel em http://127.0.0.1:{srv.porta}  (Ctrl+C para sair)"`.
- `webbrowser.open(url)`, exceto com `--sem-navegador`.
- `serve_forever()`. No `KeyboardInterrupt`: imprime "Painel encerrado." e, se `executor.rodando()`, também "Atenção: a ação em andamento recebeu o Ctrl+C também."; depois `server_close()` e `return 0`.

`__main__.py`: `from processamento.painel.servidor import main` + `raise SystemExit(main())`. `__init__.py`: só a docstring.

Testes (`tests/test_painel_servidor.py`):
- Fixture `srv`: `raiz = montar_raiz(tmp_path)`; `RELOGIO = lambda: datetime(2026,10,23,10,0,tzinfo=SP)`; `montar_falso(acao_id, *, hoje, d_carga)` devolve `[sys.executable,"-c","import time; print('inicio', flush=True); time.sleep(4); print('fim')"]` para `testes` e `[sys.executable,"-c","print('ok')"]` para o resto; `s = criar_servidor(raiz, 0, montar_comando=montar_falso, relogio=RELOGIO)`; `threading.Thread(target=s.serve_forever, daemon=True).start()`; no teardown, `s.executor.parar()` (ignorar a resposta), `s.executor.esperar(30)`, `s.shutdown()`, `s.server_close()`.
- Helper `pedir(s, metodo, caminho, corpo=None, host=None, origem="padrão", token="padrão")` com `http.client.HTTPConnection("127.0.0.1", s.porta, timeout=10)` e `headers={"Host": host or f"127.0.0.1:{s.porta}", ...}`. Passar `Host` nos headers faz o `http.client` não enviar o dele. Devolve `(status, cabecalhos, corpo_bytes)`.
- Casos e valores esperados:
  1. `GET /` → 200; o corpo contém "Painel de operação" e `s.token`, e não contém `"__TOKEN_PAINEL__"`; o cabeçalho `Content-Security-Policy` está presente. Com `Host localhost:<p>` → 200.
  2. `Host "evil.example:<p>"` → 403; `Host "127.0.0.1:1"` → 403; vale para `GET /api/painel` também.
  3. `GET /api/painel` → 200; as chaves == `{"gerado_em","hoje","trava","agora","historico","etapas","saude","experimento","testes","acao","botoes"}`; `agora.data_referencia == "2026-10-23"`, `agora.rodada == 6`, `agora.duracao_s == 118`; as datas de `historico.diarias` == `["2026-10-23","2026-10-22","2026-10-21","2026-10-20"]`; `hoje.data == "2026-10-23"`, `hoje.pregao is True`; `botoes.carga.comando == "python -m processamento.saida --data 2026-10-23 --completo"`; `botoes.rotina.comando == "python -m processamento.rotina --data 2026-10-23 --sem-esperar"`; `botoes.rotina.habilitado is True`; `trava.existe is False`.
  4. **`.env` nunca servido**: para cada um de `"/.env"`, `"/../.env"`, `"/%2e%2e/.env"`, `"/api/../.env"`, `"/processamento/config/parametros.yaml"`, `"/saida/2026-10-23/execucao.json"` → 404. Para cada um de `"/"`, `"/api/painel"`, `"/api/acao?desde=0"`, `"/api/relatorio"` → `b"segredo123"` e `b"usuario_teste"` não aparecem no corpo.
  5. POST de iniciar:
     - `{"acao":"apagar_tudo"}` → 400; `{"acao":"rotina; del *"}` → 400; corpo `"lixo"` → 400
     - sem token → 403; `Origin "http://evil.example"` → 403; sem `Origin` → 403
     - corpo de 2000 bytes → 413
     - `GET /api/acao/iniciar` → 404
  6. Concorrência:
     - `POST {"acao":"testes"}` → 202
     - logo depois, `POST {"acao":"diagnostico"}` → 409, com "rodando" ou "em andamento" no erro
     - `GET /api/painel` → `botoes.rotina.habilitado is False`
     - polling de `GET /api/acao?desde=0` até aparecer `"inicio"` nas linhas (no máximo 10 s)
     - `POST /api/acao/parar` → 200; `executor.esperar(30)`; `GET /api/acao` → `rodando False`, `significado "parado pelo painel"`
  7. Trava (o painel não toca nela):
     - grava `raiz/saida/estado/rotina.trava` = `{"pid": 4321, "criada_em": "2026-10-23T09:30:00-03:00"}`
     - `GET /api/painel` → `trava.ativa True`, `trava.idade_min 30`, `botoes.rotina.habilitado False`, `botoes.carga.habilitado False`, `botoes.diagnostico.habilitado False`, `botoes.testes.habilitado True`
     - `POST rotina` → 409
     - o arquivo continua existindo e com o mesmo texto
     - com `criada_em "2026-10-23T03:00:00-03:00"` (7 h) → `trava.abandonada True` e `botoes.rotina.habilitado True` (não iniciar)
  8. Produção: no yaml do tmp, trocar `fim: null` por `fim: "2026-11-30"` → `botoes.rotina.habilitado False` e `POST rotina` → 409.
  9. Sem nenhuma execução: apagar `raiz/saida` → `GET /api/painel` 200, `agora is None`, `historico.diarias == []`, `botoes.carga.habilitado False`.
  10. `host_permitido("127.0.0.1:8765", 8765) is True`, `host_permitido("127.0.0.1", 8765) is False`, `host_permitido(None, 8765) is False`, `origem_permitida("http://localhost:8765", 8765) is True`, `origem_permitida("null", 8765) is False`.
  11. Isolamento do banco: `subprocess.run([sys.executable,"-c","import sys, processamento.painel.servidor; print('processamento.fontes' in sys.modules, 'sqlalchemy' in sys.modules, 'dotenv' in sys.modules)"], cwd=<raiz do repo>, capture_output=True, text=True)` → a saída, sem espaços nas pontas, é `"False False False"`.
  12. Sem SQL: o texto dos arquivos `processamento/painel/*.py` não contém `"SELECT"`, `"executar_leitura"`, `"create_engine"`, `"load_dotenv"`, `".env\""` nem `"shell=True"`.

Verificação: `.venv/Scripts/python.exe -m pytest -q tests/test_painel_servidor.py` e depois `.venv/Scripts/python.exe -m pytest -q`.

---

## F6. Verificação final (executor)
1. `.venv/Scripts/python.exe -m pytest -q` passa sem falhas: os 1743 existentes mais os novos.
2. `git status --porcelain` mostra **só arquivos novos** (`??`) em `processamento/painel/`, `tests/test_painel_*.py`, `tests/fabrica_painel.py` e `tests/dados/painel/`. Nenhum `M` (modificado).
3. Teste manual (o usuário): `.venv\Scripts\python.exe -m processamento.painel` abre o navegador; clicar em "Rodar os testes" e ver o log ao vivo. **Não** clicar em rotina, carga ou diagnóstico durante a verificação automática.

---

## Respostas pontuais às perguntas do pedido
- **Dia sem pregão**: a rotina sai com 0, grava só `logs/rotina-<D>.log` (cria e apaga a trava) e nenhum pacote. O painel avisa antes (no texto do botão e na confirmação) e depois (o log mostra "não é pregão previsto (domingo)"). Hoje, 25/10, é domingo.
- **Encoding**: `PYTHONIOENCODING=utf-8` e leitura do pipe com `encoding="utf-8", errors="replace"`. `PYTHONUNBUFFERED=1` é **obrigatório**: sem ele, o stdout em pipe sai em blocos e o log não fica "ao vivo". `PYTHONUTF8` fica de fora para não mudar o comportamento dos comandos existentes.
- **`sys.executable` e cwd**: `argv[0]` é sempre `sys.executable` (o Python da `.venv` que abriu o painel) e o `cwd` é a raiz do projeto.
- **CSRF / rebinding**: checagem de Host em tudo, Origin no POST e token por sessão embutido na página (`X-Painel-Token`), além do bind só em 127.0.0.1. Ações só por POST, com corpo de no máximo 1 KB.
- **Testes com banco**: a ação "testes" remove `PROC_TESTES_COM_BANCO` do ambiente do filho, então o pytest do painel nunca roda os testes `@banco`.

## Sugestões (exigiriam mudar o que existe; ficam fora do plano)
1. **Hora em cada linha do log da rotina** e **tempo de cada etapa interna** (Fase 1, fechamento do top, pacotes). Exige mudar o `Formatter` e acrescentar logs em `rotina/executar.py` e `saida/gerar.py`. Hoje só dá para ver o início e a hora das consultas, e a duração total vem do `execucao.json`.
2. **Guardar todas as rodadas de um dia** (por exemplo `saida/<D>/execucao-rodada-N.json` ou um `execucoes.jsonl`). Hoje o `execucao.json` é regravado e só a última rodada fica.
3. **Diagnóstico também em JSON** (além do .md), para o painel não depender do formato do markdown.
4. **Cancelar a rotina com segurança** (tratar o sinal e apagar a trava). Hoje matar o processo deixa a trava presa por até 6 h.
5. **Escolher a data da rotina pelo painel** (dia passado). Foi deixado de fora pela regra "o navegador manda só o id". Daria para aceitar uma data validada, se o usuário quiser.
6. **Resultado de pytest rodado fora do painel** (por exemplo `--junitxml` no `pytest.ini`). Hoje o painel só conhece os pytest que ele mesmo rodou.
7. **Próxima execução do Agendador** (`schtasks /Query /TN "TCC rotina diaria"`). Não exige mudar nada, mas ficou fora para não aumentar o escopo.

## Custos e riscos
- **Custo**: 6 arquivos novos de código (~900 linhas, das quais ~350 de HTML/JS), 5 arquivos de teste (~70 casos, poucos segundos; alguns sobem subprocessos Python curtos), ~20 fixtures pequenas e 0 dependências novas.
- **Rodar a rotina pelo painel é igual a rodar no terminal**: grava `saida/<hoje>/`, avança `saida/estado/` (envio "quando muda") e grava `registros/experimento/<D>.top.json`. Com `--sem-esperar` antes da coleta terminar, tudo isso sai com dados incompletos. Mitigações: confirmação com aviso e botão bloqueado em produção.
- **Formatos de texto**: o log e o diagnóstico são lidos pelo formato atual. Se mudarem, a seção mostra "formato não reconhecido" em vez de quebrar, e os testes do painel acusam.
- **API privada**: o painel usa `trava._ler_trava`. Se ela for renomeada, o teste do painel quebra e avisa.
- **Fechar a janela do terminal** com a rotina rodando pode matá-la sem o `finally`, e a trava fica presa até 6 h (depois disso a rotina seguinte apaga sozinha). O Ctrl+C chega aos dois processos e é seguro.
- **Porta 8765 ocupada**: o painel usa uma porta automática e imprime a URL.
- O pytest disparado pelo painel roda também os testes do próprio painel. Funciona, mas leva alguns minutos.

## Arquivos de referência
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\rotina\executar.py` (main `:295`, códigos `:5-6`, log `:112`, sem pregão `:182`)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\rotina\trava.py` (`_ler_trava` `:30`)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\rotina\gatilho.py:280` (`--sem-esperar` gera mesmo sem coleta)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\saida\gerar.py` (main `:362`, `PASTA_COMPLETA_PADRAO` `:49`, `COLETA_NAO_CONSULTADA` `:38`, em_andamento `:152`)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\diagnostico\__main__.py` e `relatorio.py:76`
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\calendario.py` (`SP` `:18`, `motivo_sem_pregao` `:367`)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\config\parametros.yaml` (`treino` `:190`, `saida` `:212`, `rotina` `:220`)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\LEIA-ME.md:76-104` (códigos de saída e carga completa)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\.gitignore` (`*.log` linha 59, `.env` linha 210, `/saida/`, `/saida_completa/`, `/modelos/`)
