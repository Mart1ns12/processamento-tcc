# Plano: redesenho "Sala de Operação" do painel

> Aprovado em 25/10/2026 com os **AJUSTES V1 a V4** abaixo, que valem sobre as fases A–G.

## AJUSTES APROVADOS (V1–V4)

**Continua valendo:** servidor só em 127.0.0.1, lista fixa de comandos, nunca ler nem servir o `.env`, banco só pelos comandos existentes (que usam `fontes.executar_leitura`), nenhuma mudança em `saida`, `rotina`, `diagnostico` ou treino. Sem commit.

### V1. Todo horário mostra o dia (Fase D + Fase F)
Num domingo, o painel não pode parecer que a coleta rodou hoje.
- Em `visao.py`:
  - `DIAS_CURTOS = ["seg","ter","qua","qui","sex","sáb","dom"]`;
  - `dia_curto(d: date) -> str` → `"sex 23/10"`;
  - `quando(iso: str | None) -> str | None` → `"sex 23/10 08:00"` (instante em SP; `None` se vazio ou inválido; usa `leitores._instante`).
- `fluxo(...)["coleta"]` ganha:
  - `"dia"`: `dia_curto` da data em SP de `iniciada_em` (ou `None`);
  - `"resumo"`: `f"{dia} · começou {HH:MM} · entregou {HH:MM}"`. Regras:
    - se a entrega caiu noutro dia, o trecho vira `f"entregou {quando(entrega)}"`;
    - sem entrega, o trecho vira `"entrega não concluída"`;
    - sem `iniciada_em`, o resumo vira `"sem dados"`.
  - Ex. com a fixture: `"sex 23/10 · começou 08:00 · entregou 08:22"`.
- `fluxo(...)["processamento"]` ganha:
  - `"rotulo"`: `f"última rotina diária · rodada {rodada} · de {DD/MM HH:MM do inicio em SP}"`. Ex. da fixture: `"última rotina diária · rodada 6 · de 24/10 22:46"`. Sem `inicio`: `"última rotina diária · rodada {rodada} · sem dados"`;
  - `"quando"`: `f"{quando(inicio)} → {HH:MM do fim}"`, ou `quando(fim)` completo se o fim caiu noutro dia. Ex.: `"sáb 24/10 22:46 → 22:48"`.
- `linha_do_tempo` ganha `"dia_rotulo"`: `dia_curto(d) + "/" + ano`, ex. `"sex 23/10/2026"`. Na página, o título do cartão é `"A manhã do pregão de " + dia_rotulo`. O selo do dia no topo continua dizendo "Domingo · sem pregão", e o título do fluxo diz "pregão de sex 23/10/2026".
- Testes novos (Fase D):
  - `dia_curto(date(2026,10,23)) == "sex 23/10"`; `dia_curto(date(2026,10,25)) == "dom 25/10"`;
  - `quando("2026-10-23T11:00:01+00:00") == "sex 23/10 08:00"`; `quando(None) is None`; `quando("lixo") is None`;
  - no item de fluxo da Fase D (com `inicio "2026-10-24T22:46:25-03:00"`, `fim "2026-10-24T22:48:23-03:00"`, `coleta.iniciada_em "2026-10-23T08:00:01-03:00"`, `entrega_concluida_em "2026-10-23T08:22:52-03:00"`): `coleta["resumo"] == "sex 23/10 · começou 08:00 · entregou 08:22"`, `processamento["rotulo"] == "última rotina diária · rodada 6 · de 24/10 22:46"`, `processamento["quando"] == "sáb 24/10 22:46 → 22:48"`;
  - `linha_do_tempo(item_23_10, "09:45")["dia_rotulo"] == "sex 23/10/2026"`.
- Fase F:
  - **toda** hora exibida na página vem com o dia (usar `resumo`, `rotulo`, `quando`, `dia_rotulo`; no histórico, na saúde e nos testes, formato `"sex 23/10 08:00"` ou `dd/mm/aaaa HH:MM`);
  - a linha do tempo mostra só as horas daquele `dia_rotulo`.

### V2. Rotina diária e carga completa nunca se misturam (Fase D + E + F)
- `fluxo(item, completa=None)`: `item` é **sempre** a última rotina diária (`ultima_execucao(diarias)`, pasta `saida/`), como já é hoje. Os números de Coleta, Processamento e Interface vêm só dela.
- Chave nova `fluxo["carga"]`:
  - com `completa` (resultado de `ultima_execucao(completas)`, pasta `saida_completa/`) legível: `{"disponivel": True, "rodada", "status", "n_pacotes", "rotulo": f"última carga completa: {DD/MM HH:MM do inicio em SP} · {n_pacotes} pacotes"}`. Com 1 pacote, `"1 pacote"`; sem `inicio`, a data vira `"sem dados"`;
  - sem completa: `{"disponivel": False, "rotulo": "última carga completa: sem dados"}`.
- Fase E: `"fluxo": _seguro(visao.fluxo, agora_item, leitores.ultima_execucao(itens_completas))`.
- Testes:
  - Fase D: `fluxo(item, {"legivel":True,"data_referencia":"2026-10-23","rodada":1,"status":"ok","n_pacotes":2,"inicio":"2026-10-24T23:00:00-03:00"})["carga"]["rotulo"] == "última carga completa: 24/10 23:00 · 2 pacotes"`; `fluxo(item)["carga"] == {"disponivel": False, "rotulo": "última carga completa: sem dados"}`.
  - Fase E, com as fixtures: `visao.fluxo.processamento.rotulo == "última rotina diária · rodada 6 · de 24/10 22:46"`, `visao.fluxo.carga.rotulo == "última carga completa: 24/10 23:00 · 2 pacotes"`, `visao.fluxo.interface.n_pacotes == 7`.
- Fase F:
  - o estágio 2 mostra o `processamento.rotulo`;
  - embaixo do fluxo, uma linha separada `p.note#carga-linha` com o `carga.rotulo`;
  - na tabela do histórico, a coluna Tipo continua separando "Rotina diária" e "Carga completa".

### V3. Gráfico e cadeado do experimento (Fase F + testes)
- O gráfico tem um título ou legenda **fixo** acima dele: `"Teste de funcionamento (treino " + pasta + "), não é o resultado do TCC"`, onde `pasta` = `desenvolvimento.pasta` (ex.: `dev-2026-10-23`; sem pasta → `"sem dados"`). Ao lado, o selo `span.pill.idle` **"em avaliação"**.
- A faixa do acaso é desenhada como **faixa**: `rect.acaso` do `p2_5` ao `p97_5`, altura de todo o gráfico, com a linha da média por cima. A legenda embaixo diz "faixa cinza = acaso (95% dos sorteios)".
- O cadeado é **só leitura**: nenhum botão, link ou comando do painel destranca o teste final ou usa `--teste-final`. A lista fixa continua com só 4 ações (`rotina`, `carga`, `diagnostico`, `testes`).
- Testes novos:
  - em `test_painel_pagina.py`: a página contém `"não é o resultado do TCC"` e `"em avaliação"`, e não contém `"--teste-final"` nem `"teste_final_usado"`;
  - em `test_painel_acoes.py`: `set(ACOES) == {"rotina","carga","diagnostico","testes"}`, e para cada id `montar_comando(id, d_rotina=date(2026,10,23), d_carga=date(2026,10,23))` não contém `"--teste-final"` nem `"processamento.experimento.treino"`;
  - em `test_painel_servidor.py`: `POST /api/acao/iniciar` com `{"acao":"teste_final"}` → 400.

### V4. Verificação final (Fase G)
O `git status --porcelain` só pode mostrar arquivos dentro de `processamento/painel/`, `tests/test_painel_*.py`, `tests/fabrica_painel.py`, `tests/dados/painel/`, `docs/plano_painel.md`, `docs/plano_painel_visual.md` e `docs/painel_referencia.html`. O painel da 1ª versão ainda não foi commitado, então eles aparecem como `??`. **Qualquer outro arquivo modificado → parar e avisar o usuário.** Também entregar prints da página nos temas claro e escuro (Edge headless `--screenshot`, servidor do painel na raiz real, sem clicar em nada).

---

Li o protótipo inteiro, `docs/plano_painel.md`, os 5 arquivos do painel, os testes, as fixtures e os arquivos reais. Não editei nada e não rodei nada que acesse o banco (só `pytest -q tests/test_painel_pagina.py`, `--version` e leituras de JSON/YAML).

---

## (A) PLANO CURTO PARA O USUÁRIO

A página nova segue o protótipo: mesma ordem, cores, cartões, tema claro/escuro e fontes do sistema (nada baixado da internet). Nenhum número fica escrito à mão. Tudo vem dos arquivos, e o que não existe aparece como "sem dados".

| Elemento do protótipo | Fonte (arquivo → chave) | O que mostra hoje (dados reais) |
|---|---|---|
| Selo geral do topo | último `saida/*/execucao.json` → `status`; trava; ação rodando | "Última rotina: ok" |
| Selo do dia | calendário da B3 (`calendario.motivo_sem_pregao`) | "Domingo · sem pregão" |
| Fluxo: Coleta | `execucao.json` → `coleta_status.iniciada_em`, `entrega_concluida_em`, `etapas` | Dados entregues · começou 08:00 · entregou 08:22 · 9 de 9 etapas |
| Fluxo: Processamento | `execucao.json` → `status`, `inicio`/`fim`, pacote `resumo_acao`, `avisos` | Calculado e validado · 1 min 58 s · 85 ações · rodada 6 · 7 avisos |
| Fluxo: Interface | `execucao.json` → `pacotes_enviados`, `versao_contrato`; `parametros.yaml` → `publicar_top_provisorio` | 7 pacotes prontos · contrato 1.0 · 179 registros · top 5 retido |
| Linha do tempo | coleta (acima) + `inicio`/`fim` da rotina + `parametros.yaml → rotina.prazo` ("09:45") + abertura da B3 (`calendario.horario_b3`) | 08:00 coleta começa · 08:22 entrega · 09:45 prazo · 10:00 bolsa abre. A rotina de 23/10 rodou em **24/10 às 22:46**, fora da manhã, então a **folga fica "sem dados"** (com aviso) |
| Ações (4 botões) | os mesmos de hoje; as etapas acendem pelas **linhas reais** do log | Rotina usaria 23/10/2026 (hoje é domingo) |
| Saúde: contrato | `docs/diagnostico_banco.md` → "Divergências" | 0 divergências (verde) |
| Saúde: quantidade de ações | seção "Quantidade de ações suspeita" | 19 empresas (amarelo) |
| Saúde: preços suspeitos | seção "Retornos diários suspeitos" | 5 retornos: AZUL3 (3), PCAR3, UGPA3 (amarelo) |
| Saúde: lacunas | seção "Lacunas nas séries…" | 3 lacunas: IDIV, IFIX, SMLL, 449 pregões (amarelo) |
| Saúde: horário das notícias | seção 5, tabela "Hora da publicação, por ano" | 90,8% sem hora real (amarelo) |
| Saúde: histórico | seção 15, nota "Cobertura do experimento" | 117.435 linhas · 1.698 pregões (verde) |
| Cadeado do teste final | `parametros.yaml → treino.teste_final` + `docs/teste_final_usado.json` | Trancado desde 23/06/2026 |
| Gráfico de acerto × acaso | `saida/experimento/treino/dev-2026-10-23/metricas.json` | Acaso 48,1% (faixa 46,4–49,9%); Modelo 3: 50,2%, Modelo 1: 50,9%, Logística: 53,0%, Volatilidade: 50,6% |
| Modelo | `modelos/xgb-2026-06.meta.json` | xgb-2026-06 · provisório · 02/01/2024 a 19/06/2026 · 45.765 linhas |
| Calendário + tabela | pastas `saida/` e `saida_completa/` | Outubro/2026: 23/10 ok com carga completa, 12/10 sem pregão. Tabela com 2 linhas: rotina 1 min 58 s e carga 1 min 48 s |
| Testes | `logs/painel/testes-*.log` | **"sem dados"**: a pasta `logs/painel/` não existe; aparece depois do 1º clique em "Rodar os testes" |

**O que fica "sem dados" ou sai do protótipo, por não ter fonte:**
- a folga da linha do tempo (enquanto a rotina rodar fora da manhã);
- o tempo de cada etapa nas Ações, porque o log não tem hora por linha;
- os "17.123 valores conferidos";
- as frases "pedido enviado à coleta" e "correção agendada";
- os rótulos fixos dos testes ("vazamento testado…"), trocados por arquivo, tempo e código de saída;
- o resultado do pytest, até o painel rodar um.

**Mudanças no servidor (só dentro de `processamento/painel/`):**
- uma chave nova `visao` em `/api/painel` (fluxo, linha do tempo, cartões de saúde e calendário, calculados em Python);
- uma chave nova `marcos` em `/api/acao` com as etapas;
- campos novos na execução: hora de início da coleta e versão do contrato.

Muda **1 linha** de teste existente (a lista exata das chaves do JSON).

**Riscos:**
- se mudarem os textos do diagnóstico ou do log, o cartão vira "sem dados" (não quebra) e os testes acusam;
- a carga completa e o diagnóstico não escrevem nada até o fim, então a 1ª etapa fica "rodando" até o código de saída;
- a página continua um arquivo único e grande.

---

## (B) PLANO DETALHADO PARA OS IMPLEMENTADORES

### Decisões (uma rota cada)
1. **Etapas das ações ficam no servidor** (`processamento/painel/marcos.py`, função pura testada com pytest), devolvidas em `/api/acao` e em `acao` como `marcos`. O JS só desenha. É testável com valores esperados e não exige mudar o Executor: o servidor chama `executor.estado(0)` e corta as linhas.
2. **Dados da tela num bloco novo `visao`** (`visao.py` e `saude.py`), sem mexer no formato de `saude`, `historico`, `experimento` e `etapas`, que os testes atuais conferem com `==`.
3. **Prazo**: `parametros.yaml → rotina.prazo` (linha ~222, `prazo: "09:45"`), lido por uma função nova `leitores.ler_prazo_rotina`. `ler_parametros` não muda, porque o teste em `tests/test_painel_leitores.py:121` compara o dicionário inteiro.
4. **Abertura da B3**: `calendario.horario_b3(d, caminho)` (`processamento/calendario.py:192`). É pura e usa `carregar_parametros` com `lru_cache`. Não importa fontes/sqlalchemy/dotenv; o painel já importa `calendario`.
5. **Navegação do calendário**: o servidor manda até 12 meses prontos em `visao.calendario`. Não há rota nova, então a superfície de segurança não muda.
6. **Ids antigos mantidos** para os testes existentes continuarem valendo:
   - `id="agora"` vai para o cartão do Fluxo;
   - `id="etapas"` vai para um `<details>` dentro do Histórico;
   - `id="log"` é o `<pre>` de "Ver o log completo";
   - `<title>` contém "Painel de operação" (exigido por `tests/test_painel_servidor.py:113`).

### REGRAS PARA TODAS AS FASES (copiar em todo despacho)
- Projeto `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc`, Windows. Python: `.venv/Scripts/python.exe`.
- **Só mexer** em `processamento/painel/`, `tests/test_painel_*.py`, `tests/fabrica_painel.py` e `tests/dados/painel/`. Nada fora disso (nem o `parametros.yaml` real, nem `ESPECIFICACAO.md`, `conftest.py`, `requirements.txt` ou `.gitignore`).
- **Nunca ler o `.env`.** Nunca importar `processamento.fontes`, `sqlalchemy` nem `dotenv` no painel. Nenhum SQL.
- Nunca rodar `python -m processamento.rotina`, `processamento.saida` ou `processamento.diagnostico`: eles acessam o banco, e o usuário atual do banco tem permissão de escrita.
- Testes sem banco e sem rede. Não fazer commit.
- Os `processamento/painel/*.py` não podem conter os textos `SELECT`, `executar_leitura`, `create_engine`, `load_dotenv`, `.env"` nem `shell=True` (teste 12 do servidor).
- Fuso:
  - usar `from processamento.calendario import SP`;
  - ISO sem fuso = São Paulo (reusar `leitores._instante`);
  - converter com `.astimezone(SP)` antes de comparar data ou hora;
  - nunca comparar datas como texto. Ex.: `"2026-10-23T11:00:01+00:00"` é 08:00 em SP.
- Funções de leitura **nunca levantam exceção** por arquivo ausente ou quebrado: devolvem `{"disponivel": False, "motivo": ...}` ou `None`. Ausência = `None` ou "sem dados", **nunca 0 inventado**.
- Ler arquivos com `encoding="utf-8"` (logs com `errors="replace"`).
- Todo módulo começa com `from __future__ import annotations` e uma docstring curta. Textos em português simples, sem emoji.
- Testes usam `montar_raiz(tmp_path)` (`from fabrica_painel import montar_raiz`) e nunca escrevem em `tests/dados/`. Fixture de log se chama `*.log.txt` (o `.gitignore` ignora `*.log`).
- YAML: `HH:MM` sem aspas vira inteiro (`10:00` → 600; `09:45` fica texto). Só aceitar `str` que case `^([01]\d|2[0-3]):[0-5]\d$`.
- Verificação da fase: `.venv/Scripts/python.exe -m pytest -q <arquivo de teste da fase>`, depois `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`.

### Paralelismo
**A, B, C, D e F podem rodar em paralelo** (arquivos não se sobrepõem). **E** vem depois de A, B, C e D. **G** é a verificação final.

---

### FASE A — `leitores.py` + fixture do yaml + testes (independente)
Arquivos: `processamento/painel/leitores.py`, `tests/dados/painel/raiz/processamento/config/parametros.yaml`, `tests/test_painel_leitores.py` (só acrescentar).

1. `_resumir_coleta` (leitores.py:188): acrescentar ao dicionário
```python
"iniciada_em": coleta.get("iniciada_em"),
"iniciada_hhmm": _hhmm_sp(coleta.get("iniciada_em")),
"finalizada_em": coleta.get("finalizada_em"),
```
2. `resumir_execucao` (:209): depois de `reg = registros[0]`, fazer `versao = reg.get("versao_contrato") or dados.get("versao_contrato")` e acrescentar `"versao_contrato": versao` ao retorno. Em `_item_ilegivel` (:201), acrescentar `"versao_contrato": None`.
3. Função nova:
```python
RE_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
def ler_prazo_rotina(raiz: Path) -> str | None:
    """`rotina.prazo` do parametros.yaml da raiz ("HH:MM"); None se faltar, for inválido ou o arquivo não abrir."""
    # yaml.safe_load de raiz/"processamento/config/parametros.yaml"; qualquer OSError/ValueError/yaml.YAMLError -> None
    # valor tem que ser str e casar RE_HHMM (int sexagesimal -> None)
```
4. Fixture: no bloco `rotina:` do yaml da fixture, acrescentar a linha `  prazo: "09:45"`. Nenhum teste existente é afetado: `ler_parametros` ignora a chave, e os `replace("fim: null", …)` continuam funcionando.

Testes novos (valores esperados):
- Em `listar_execucoes(raiz,"saida","diaria")`:
  - `[0]["coleta"]["iniciada_em"] == "2026-10-23T08:00:01-03:00"`, `["iniciada_hhmm"] == "08:00"`, `["finalizada_em"] == "2026-10-23T08:24:29-03:00"`; `[0]["versao_contrato"] == "1.0"` (vem do envelope, porque o registro da fixture não tem a chave);
  - `[1]["coleta"]["iniciada_hhmm"] == "08:00"` e `["finalizada_em"] is None`;
  - `[2]["versao_contrato"] is None` (ilegível);
  - `[3]["coleta"]["iniciada_hhmm"] is None`.
- `resumir_execucao({"registros":[{"status":"ok","coleta_status":{"iniciada_em":"2026-10-23T11:00:01+00:00"}}]},"2026-10-23","diaria","x")`: `coleta["iniciada_hhmm"] == "08:00"` e `versao_contrato is None`.
- `ler_prazo_rotina(raiz) == "09:45"`. Trocando a linha por `  prazo: "9h"` → `None`. Por `  prazo: 10:00` → `None`. Apagando o yaml → `None`.

---

### FASE B — `relatorios.resultado_terminal` + `marcos.py` + testes (independente)
Arquivos: `processamento/painel/relatorios.py`, `processamento/painel/marcos.py` (novo), `tests/test_painel_marcos.py` (novo), `tests/test_painel_relatorios.py` (só acrescentar).

1. Em relatorios.py, função nova. O `_classificar_linha` (:99) passa a usá-la no lugar dos 5 blocos entre `RE_SEM_PREGAO` e `sem_banco`; `RE_CONSULTA` e `RE_SAIDA` continuam antes:
```python
def resultado_terminal(linha: str) -> tuple[str, str] | None:
    m = RE_SEM_PREGAO.search(linha)
    if m: return "sem_pregao", m.group(1)
    if linha.startswith("outra rotina em andamento"): return "trava", linha
    if linha.startswith(("Saída não gerada:", "Coleta não terminou até")): return "falhou", linha
    if linha.startswith(("Configuração do banco incompleta", "Configuração inválida")): return "configuracao", linha
    if linha.startswith("Falha ao conectar ao banco") or "Rodada interrompida" in linha or linha.endswith("A coleta não foi alterada."):
        return "sem_banco", linha
    return None
# em _classificar_linha, depois do bloco RE_SAIDA:
#     fim = resultado_terminal(linha)
#     if fim is not None:
#         rodada["resultado"], rodada["detalhe"] = fim
#         return
```
   Os textos conferem com `processamento/rotina/executar.py:157-291`. O de "Configuração inválida" vem do `print` em `:264`.

2. `marcos.py`:
```python
from dataclasses import dataclass
from processamento.painel.relatorios import RE_CONSULTA, RE_INICIO, RE_PYTEST_RESUMO, RE_SAIDA, resultado_terminal
RE_PROGRESSO = re.compile(r"\[\s*(\d{1,3})%\]\s*$")
RE_RELATORIO = re.compile(r"^Relatório: .+ \| divergências: (\d+)$")
@dataclass(frozen=True)
class Etapa:
    id: str; rotulo: str
    conclui: Callable[[str], str | None] | None = None   # detalhe (str) se a linha conclui a etapa
    progresso: Callable[[str], str | None] | None = None # detalhe parcial
FIM = Etapa("fim", "Encerrado")
ETAPAS: dict[str, list[Etapa]]   # a última de cada lista é FIM
def marcos_acao(acao_id: str | None, linhas: list[str], *, rodando: bool, codigo: int | None,
                significado: str | None) -> list[dict]   # [{"id","rotulo","estado","detalhe"}]
```
   Estados possíveis: `espera`, `agora`, `concluida`, `erro`, `pulada`.

**Etapas e detalhes por ação:**
- **rotina**:
  - `inicio` "Rotina iniciada": conclui com `RE_INICIO` → `f"início {g2}"` + `" (--sem-esperar)"` se houver g3;
  - `coleta` "Conferindo se a coleta do dia terminou": conclui com `RE_CONSULTA` cujo texto termina em `"-> gerar"` → `f"consulta {n} às {hora}: coleta pronta"`; progresso com qualquer `RE_CONSULTA` → `f"consulta {n} às {hora}: {texto.rsplit(' -> ', 1)[-1]}"`;
  - `calculo` "Calculando indicadores, top 5 e pacotes (só leitura do banco)": sem marcador;
  - `saida` "Gravando os pacotes do dia": `RE_SAIDA` → `f"status {g1}"`;
  - `FIM`.
  - Terminal: `resultado_terminal`. `sem_pregao` → tipo `"pula"`, detalhe `f"não é pregão previsto ({motivo}): nada a gerar"`. Os demais → `"erro"`, detalhe = linha.
- **carga**:
  - `calculo` "Lendo o banco (só leitura) e montando os pacotes inteiros": sem marcador;
  - `saida` "Gravando em saida_completa/": `RE_SAIDA` → `"status X"`;
  - `FIM`.
  - Terminal `_terminal_banco`.
- **diagnostico**:
  - `leitura` "Lendo o banco da coleta (só leitura) e conferindo as seções": sem marcador;
  - `relatorio` "Gravando docs/diagnostico_banco.md": `RE_RELATORIO` → `"0 divergências"` / `"1 divergência"` / `"N divergências"`;
  - `FIM`.
  - Terminal `_terminal_banco`.
- **testes**:
  - `coleta` "Encontrando os testes": `RE_PROGRESSO` → `"testes encontrados"`;
  - `execucao` "Rodando os testes (sem o banco)": conclui com `RE_PYTEST_RESUMO.match` → `linha.strip().strip("=").strip()`; progresso com `RE_PROGRESSO` → `f"{n}%"`;
  - `FIM`.
  - Sem terminal.
- `_terminal_banco(linha)` → `("erro", linha)` se a linha começa com "Configuração do banco incompleta", "Falha ao conectar ao banco", "Saída não gerada:" ou "A carga completa precisa de outra pasta", ou se termina com "Nada foi gravado." ou "A coleta não foi alterada.". Os textos conferem com `processamento/saida/gerar.py:388-422` e `processamento/diagnostico/__main__.py:105-145`.

**Algoritmo** (exato):
```
se acao_id not in ETAPAS: return []
meio = etapas[:-1]; est = [{"id","rotulo","estado":"espera","detalhe":None} ...]; atual = 0; nota_final = None
para cada linha:
  term = TERMINAL(linha)
  se term: tipo, det = term
     se atual < len(meio): est[atual].estado = "erro" se tipo=="erro" senão "pulada"; se erro: est[atual].detalhe = det
                           est[atual+1 : len(meio)].estado = "pulada"
     se tipo == "pula": nota_final = det
     atual = len(meio); break
  procurar j em range(atual, len(meio)) com meio[j].conclui(linha) -> det not None:
     est[atual:j].estado = "concluida"; est[j].estado="concluida"; est[j].detalhe = det or est[j].detalhe; atual = j+1
     se atual < len(meio) e meio[atual].progresso: p = progresso(linha); se p is not None: est[atual].detalhe = p
  se nenhum j: se atual < len(meio) e meio[atual].progresso: p = ...; se p: est[atual].detalhe = p
terminou = not rodando and codigo is not None
se terminou:
  codigo == 0: est[atual:len(meio)] = "concluida"; fim = "concluida"
  senão: se atual < len(meio): est[atual]="erro"; est[atual+1:len(meio)]="pulada"
         fim = "erro"
  fim.detalhe = nota_final or significado
senão se rodando: est[atual] = "agora" se atual < len(meio), senão fim = "agora"
```

**Testes** (`tests/test_painel_marcos.py`, valores esperados; `estados(r)` = lista dos `estado`):
- **T1** rotina com `codigo=0`, `significado="ok, parcial ou dia sem pregão (veja o log)"`, `rodando=False` e as linhas
  `["Rotina de 2026-10-23 (início 08:00:00)", "08:00:00 consulta 1: daily 2026-10-23-daily-080001 (cron, em_andamento), entrega em_andamento -> esperar (entrega_pendente)", "08:05:00 consulta 2: daily 2026-10-23-daily-080001 (cron, concluida), entrega concluida -> gerar", "Saída de 2026-10-23 em C:\\x\\saida\\2026-10-23: status ok", "- Gerado depois das 10h: não entra no histórico do experimento."]`
  → resultado `==` `[{"id":"inicio","rotulo":"Rotina iniciada","estado":"concluida","detalhe":"início 08:00:00"},{"id":"coleta","rotulo":"Conferindo se a coleta do dia terminou","estado":"concluida","detalhe":"consulta 2 às 08:05:00: coleta pronta"},{"id":"calculo","rotulo":"Calculando indicadores, top 5 e pacotes (só leitura do banco)","estado":"concluida","detalhe":None},{"id":"saida","rotulo":"Gravando os pacotes do dia","estado":"concluida","detalhe":"status ok"},{"id":"fim","rotulo":"Encerrado","estado":"concluida","detalhe":"ok, parcial ou dia sem pregão (veja o log)"}]`.
- **T2** as 2 primeiras linhas de T1, `rodando=True`, `codigo=None`: estados `["concluida","agora","espera","espera","espera"]`; coleta detalhe `"consulta 1 às 08:00:00: esperar (entrega_pendente)"`.
- **T3** as 3 primeiras linhas, `rodando=True`: `["concluida","concluida","agora","espera","espera"]`.
- **T4** `["Rotina de 2026-10-24 (início 00:33:35, --sem-esperar)", "2026-10-24 não é pregão previsto (sábado): nada a gerar."]`, codigo 0: estados `["concluida","pulada","pulada","pulada","concluida"]`; inicio detalhe `"início 00:33:35 (--sem-esperar)"`; fim detalhe `"não é pregão previsto (sábado): nada a gerar"`.
- **T5** `["Rotina de 2026-10-23 (início 09:00:00)", "outra rotina em andamento desde 2026-10-23T08:00:00-03:00 (pid 999). Rodada cancelada; nada foi gravado."]`, codigo 5, significado `"outra rotina em andamento (trava)"`: estados `["concluida","erro","pulada","pulada","erro"]`; coleta detalhe = a 2ª linha; fim detalhe = o significado.
- **T6** `["Rotina de 2026-10-23 (início 08:00:00)", "Traceback (most recent call last):"]`, codigo 1, significado `"código 1"`: `["concluida","erro","pulada","pulada","erro"]`; coleta detalhe `None`; fim `"código 1"`.
- **T7** testes `["........ [ 50%]", "....s... [100%]", "15 passed, 1 skipped in 2.00s"]`, codigo 0, significado `"todos os testes passaram"`: todos `concluida`; detalhes `["testes encontrados", "15 passed, 1 skipped in 2.00s", "todos os testes passaram"]`.
- **T8** testes `["........ [ 50%]"]`, `rodando=True`: `["concluida","agora","espera"]`; execucao detalhe `"50%"`.
- **T9** testes `["inicio"]`, codigo 1, significado `"parado pelo painel"`: `["erro","pulada","erro"]`; fim detalhe `"parado pelo painel"`.
- **T10** diagnostico `["Relatório: C:\\x\\docs\\diagnostico_banco.md | divergências: 0"]`, codigo 0, significado `"relatório gerado"`: todos concluida; relatorio detalhe `"0 divergências"`. Com `| divergências: 1` → `"1 divergência"`.
- **T11** diagnostico `["Configuração do banco incompleta: falta IP_BANCO"]`, codigo 2: `["erro","pulada","erro"]`; leitura detalhe = a linha.
- **T12** carga `["Saída de 2026-10-23 em C:\\x\\saida_completa\\2026-10-23: status ok", "- Carga completa."]`, codigo 0, significado `"ok ou parcial"`: `["concluida","concluida","concluida"]`; saida detalhe `"status ok"`.
- **T13** `marcos_acao(None, [], rodando=False, codigo=None, significado=None) == []`.
- **T14** diagnostico `[]`, `rodando=True`: `["agora","espera","espera"]`.
- **T15** rotina `["Configuração inválida: rotina.prazo"]`, codigo 2: `["erro","pulada","pulada","pulada","erro"]`; inicio detalhe = a linha.

Em `test_painel_relatorios.py`, acrescentar os testes de `resultado_terminal`:
- `"2026-10-24 não é pregão previsto (sábado): nada a gerar."` → `("sem_pregao","sábado")`;
- linha de trava → `("trava", linha)`;
- `"Saída não gerada: x"` e `"Coleta não terminou até 12:00: pacotes de hoje não gerados."` → `("falhou", linha)`;
- `"Configuração do banco incompleta: x"` e `"Configuração inválida: y"` → `("configuracao", linha)`;
- `"Falha ao conectar ao banco (OperationalError). Nada foi gravado."` e `"x. Rodada interrompida; a coleta não foi alterada."` → `("sem_banco", linha)`;
- `"Saída de D em P: status ok"` e `"- aviso"` → `None`.

Os testes atuais de `analisar_log_rotina` têm que continuar passando.

---

### FASE C — `saude.py` + fixture + testes (independente)
Arquivos: `processamento/painel/saude.py` (novo), `tests/test_painel_saude.py` (novo), `tests/dados/painel/diagnostico_completo.md` (novo, **fora** de `raiz/`; nenhum teste existente é afetado).

```python
from processamento.painel.relatorios import RE_SECAO, RE_SEPARADOR, _celulas, ler_diagnostico
def tabela_md(linhas: list[str], subtitulo: str) -> list[dict[str, str]] | None
    # 1ª linha == "### " + subtitulo (igualdade exata); depois dela, pula linhas vazias; linhas que começam com "|":
    # 1ª = cabeçalho (_celulas), separador (RE_SEPARADOR) pulado, demais -> dict(zip(cab, celulas)); para na 1ª linha que não começa com "|".
    # None se o subtítulo não existe.
def cartoes_saude(caminho: Path) -> dict
    # diag = ler_diagnostico(caminho); indisponível -> {"disponivel":False,"motivo":diag["motivo"],"gerado_em":None,"cartoes":[]}
    # senão {"disponivel":True,"motivo":None,"gerado_em":diag["gerado_em"],"cartoes":[6 cartões nesta ordem]}
    # cada cartão em try/except -> cartão idle. Cartão: {"id","titulo","farol":"ok|warn|bad|idle","numero","texto","fonte"}
```
- A seção é achada pelo **começo do título**, nunca pelo número.
- As linhas da seção vão do `## N. Título` até o próximo `## ` e são lidas do texto (`read_text(encoding="utf-8", errors="replace")`).
- As notas vêm de `diag["secoes"][i]["notas"]`.
- Fonte do cartão: `f"Seção {numero}: {titulo}"`.
- Seção ausente → `farol "idle"`, `numero "sem dados"`, `texto "Seção não encontrada no diagnóstico."`, `fonte None`.
- Seção presente sem nota reconhecida → idle, `"sem dados"`, `"Formato da nota não reconhecido."`, com a fonte da seção.
- Auxiliares:
  - `_milhar(n)` = `f"{n:,}".replace(",", ".")`;
  - `_pct(x)` = `f"{x*100:.1f}".replace(".", ",") + "%"`;
  - `_data_br`: `AAAA-MM-DD` → `DD/MM/AAAA`, `AAAA-MM` → `MM/AAAA`, outro texto fica como está;
  - `_plural(n, s, p)` = `f"{n} {s if n == 1 else p}"`.

**Os 6 cartões:**
1. `contrato` "Contrato com a coleta" (fonte `"Divergências × especificação"`).
   - n = `len(diag["divergencias"])`.
   - 0 → ok, `"0 divergências"`, `"Tabelas, colunas e formatos batem com a especificação."`.
   - n > 0 → bad, `_plural(n,"divergência","divergências")`, `"Temas: " + ", ".join(temas únicos na ordem) + "."`.
2. `quantidade_acoes` "Quantidade de ações" (prefixo "Quantidade de ações suspeita").
   - Regex na nota: `em (\d+) empresas em (\d{4}-\d{2}-\d{2})` (search); zero: `^nenhuma empresa com quantidade de ações suspeita em (\d{4}-\d{2}-\d{2})`.
   - n > 0 → warn, `_plural(n,"empresa","empresas")`, `f"Provavelmente em milhares (ex.: {3 primeiros 'tickers' da tabela 'Empresas com quantidade de ações suspeita'}). Valor de mercado, P/L, P/VP e payout delas saem indisponível em {data_br}."`. Sem a tabela, o trecho " (ex.: …)" sai.
   - 0 → ok, `"0 empresas"`, `f"Nenhuma empresa com quantidade de ações fora do plausível em {data_br}."`.
3. `retornos` "Preços suspeitos" (prefixo "Retornos diários suspeitos").
   - Regex: `^(\d+) retornos diários suspeitos em (\d+) tickers`; zero: `^nenhum retorno diário suspeito`.
   - n > 0 → warn, `_plural(n,"retorno","retornos")`, `f"{lista}: ficam fora das séries e das medianas do setor; o preço não é corrigido."`. A `lista` são os tickers da tabela "Retornos diários suspeitos" na ordem em que aparecem, com `(k)` só se k > 1. Sem a tabela, usar `_plural(t,"ticker","tickers")`.
   - 0 → ok, `"0 retornos"`, `"Nenhum retorno diário suspeito."`.
4. `lacunas` "Lacunas nas séries" (prefixo "Lacunas nas séries").
   - Preços: `^(\d+) lacunas de mais de \d+ pregões em \d+ tickers de v1-precos` / zero `^nenhuma lacuna de mais de \d+ pregões em v1-precos`.
   - Índices: `^(\d+) lacunas em v1-indices` / zero `^nenhuma lacuna em v1-indices`.
   - Os dois não reconhecidos → idle. Senão n = soma dos reconhecidos; 0 → ok, senão warn; numero `_plural(n,"lacuna","lacunas")`.
   - Texto = `" ".join` das partes:
     - `"Preços: nenhuma lacuna."` ou `f"Preços: {_plural(np,'lacuna','lacunas')}."`;
     - `"Índices: nenhuma lacuna."` ou `"Índices: " + "; ".join(f"{', '.join(series)}: {tamanho} {unidade} ({_data_br(ini)} a {_data_br(fim)})") + "."`, agrupando a tabela "Lacunas em v1-indices" por (inicio, fim, tamanho, unidade) na ordem. Sem a tabela: `f"Índices: {_plural(ni,…)}."`.
5. `horario_noticias` "Horário das notícias" (prefixo "Notícias").
   - Tabela "Hora da publicação, por ano (artigos distintos)": somar `int` de total, hora_real, so_data_n1a e sem_hora. Tabela ou coluna ausente, ou total 0 → idle.
   - `sem = (total-hora_real)/total`; farol ok se `sem <= 0.10`, senão warn; numero `f"{_pct(sem)} sem hora real"`.
   - Texto: `f"Com hora real: {_pct(hr/t)} · só data (regra N1-A): {_pct(sd/t)} · sem hora: {_pct(sh/t)}. Notícias sem hora entram na janela do dia de forma conservadora."`.
   - Fonte: `f"Seção {n}: {titulo} · {_milhar(total)} artigos"`.
6. `cobertura` "Histórico disponível" (prefixo "Histórico novo").
   - Regex: `^Cobertura do experimento \([^)]*\): (\d+) linhas em (\d+) pregões, de (\d{4}-\d{2}-\d{2}) a (\d{4}-\d{2}-\d{2})`.
   - Linhas > 0 → ok, senão warn. Numero `f"{_milhar(linhas)} linhas"`; texto `f"{_milhar(pregoes)} pregões, de {d1} a {d2}, no dataset do experimento."`.

**Fixture `tests/dados/painel/diagnostico_completo.md`** (trechos copiados do `docs/diagnostico_banco.md` real; conteúdo exato):
```
# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-10-24 21:08 (America/Sao_Paulo)
- Banco: banco_teste
- MySQL: 8.0.46

## Divergências × especificação

Nenhuma divergência encontrada.

## 5. Notícias (v1-noticias)

- 27259 notícias do Google News sem hora, marcadas 'só data' pela coleta (raw_articles.published_precision = 'date'): 2024: 27224, 2025: 35

### Hora da publicação, por ano (artigos distintos)

| ano | total | hora_real | pct_hora_real | so_data_n1a | pct_so_data_n1a | sem_hora | pct_sem_hora |
|---|---|---|---|---|---|---|---|
| 2024 | 33895 | 3010 | 8.9 | 15 | 0 | 30870 | 91.1 |
| 2025 | 32201 | 685 | 2.1 | 29932 | 93 | 1584 | 4.9 |
| 2026 | 117547 | 13144 | 11.2 | 101689 | 86.5 | 2714 | 2.3 |

### Hora da publicação, por ano e origem (artigos distintos)

| ano | origem | total | hora_real | pct_hora_real | so_data_n1a | pct_so_data_n1a | sem_hora | pct_sem_hora |
|---|---|---|---|---|---|---|---|---|
| 2026 | google_news | 114833 | 13144 | 11.4 | 101689 | 88.6 | 0 | 0 |

## 10. Quantidade de ações suspeita

- quantidade de ações suspeita (P/VP < 0,05; v1-acoes_emitidas provavelmente em milhares) em 19 empresas em 2026-10-23: valor de mercado, P/L, P/VP e payout = indisponivel (seção 6)

### Empresas com quantidade de ações suspeita

| tickers | cnpj | data_referencia | acoes | pvp |
|---|---|---|---|---|
| AXIA3 | 00001180000126 | 2026-06-30 | 2943220 | 0.0014 |
| ENEV3 | 04423567000121 | 2026-06-30 | 1937030 | 0.0028 |
| ABEV3 | 07526557000100 | 2026-06-30 | 15763665 | 0.003 |
| EMBJ3 | 07689002000189 | 2026-06-30 | 740465 | 0.0033 |

## 11. Retornos diários suspeitos

- 5 retornos diários suspeitos em 3 tickers (fechamento_ajustado contra o último pregão com preço, abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)

### Retornos diários suspeitos

| ticker | data | aj_anterior | aj | retorno_aj | retorno_fech |
|---|---|---|---|---|---|
| AZUL3 | 2026-02-10 | 7.42 | 341.25 | 44.9906 | 44.9906 |
| AZUL3 | 2026-04-09 | 217 | 3.060e+07 | 141012.1244 | 141012.1244 |
| AZUL3 | 2026-04-20 | 3.225e+07 | 30.54 | -1 | -1 |
| PCAR3 | 2021-03-01 | 10.2961 | 21.857 | 1.1228 | 1.1228 |
| UGPA3 | 2021-06-28 | 7.0026 | 15.3592 | 1.1933 | 1.1933 |

## 12. Lacunas nas séries de preços e índices

- nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker)
- 3 lacunas em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)

### Lacunas em v1-indices

| serie | inicio | fim | tamanho | unidade |
|---|---|---|---|---|
| IDIV | 2025-01-02 | 2026-10-19 | 449 | pregões |
| IFIX | 2025-01-02 | 2026-10-19 | 449 | pregões |
| SMLL | 2025-01-02 | 2026-10-19 | 449 | pregões |

## 15. Histórico novo: composição, corrigir_horas e cobertura do experimento

- Composição do Ibovespa: 48 de 136 tickers sem nenhum preço em v1-precos (7 código antigo de empresa do cadastro, 41 fora do cadastro); 28 estiveram no índice em 2024 ou depois.
- Cobertura do experimento (universo com a composição, motivo ok): 117435 linhas em 1698 pregões, de 2019-12-30 a 2026-10-23.
```

**Testes com valores esperados:**
- `cartoes_saude(diagnostico_completo.md)`: `disponivel True`, `gerado_em "2026-10-24 21:08 (America/Sao_Paulo)"`, e `cartoes ==`:
  - `{"id":"contrato","titulo":"Contrato com a coleta","farol":"ok","numero":"0 divergências","texto":"Tabelas, colunas e formatos batem com a especificação.","fonte":"Divergências × especificação"}`
  - `{"id":"quantidade_acoes","titulo":"Quantidade de ações","farol":"warn","numero":"19 empresas","texto":"Provavelmente em milhares (ex.: AXIA3, ENEV3, ABEV3). Valor de mercado, P/L, P/VP e payout delas saem indisponível em 23/10/2026.","fonte":"Seção 10: Quantidade de ações suspeita"}`
  - `{"id":"retornos","titulo":"Preços suspeitos","farol":"warn","numero":"5 retornos","texto":"AZUL3 (3), PCAR3, UGPA3: ficam fora das séries e das medianas do setor; o preço não é corrigido.","fonte":"Seção 11: Retornos diários suspeitos"}`
  - `{"id":"lacunas","titulo":"Lacunas nas séries","farol":"warn","numero":"3 lacunas","texto":"Preços: nenhuma lacuna. Índices: IDIV, IFIX, SMLL: 449 pregões (02/01/2025 a 19/10/2026).","fonte":"Seção 12: Lacunas nas séries de preços e índices"}`
  - `{"id":"horario_noticias","titulo":"Horário das notícias","farol":"warn","numero":"90,8% sem hora real","texto":"Com hora real: 9,2% · só data (regra N1-A): 71,7% · sem hora: 19,2%. Notícias sem hora entram na janela do dia de forma conservadora.","fonte":"Seção 5: Notícias (v1-noticias) · 183.643 artigos"}`
  - `{"id":"cobertura","titulo":"Histórico disponível","farol":"ok","numero":"117.435 linhas","texto":"1.698 pregões, de 30/12/2019 a 23/10/2026, no dataset do experimento.","fonte":"Seção 15: Histórico novo: composição, corrigir_horas e cobertura do experimento"}`
  - Contas: 16839/183643 = 9,2%; 131636/183643 = 71,7%; 35168/183643 = 19,2%; 166804/183643 = 90,8%.
- Fixture da raiz (`montar_raiz(tmp_path)/"docs/diagnostico_banco.md"`): `cartoes[0] == {"id":"contrato","titulo":"Contrato com a coleta","farol":"bad","numero":"2 divergências","texto":"Temas: coluna_faltando, falha_consulta.","fonte":"Divergências × especificação"}`; faróis `["bad","idle","idle","idle","idle","idle"]`; `cartoes[1]["numero"] == "sem dados"` e `["fonte"] is None`.
- Arquivo tmp com zeros (`"- Gerado em: 2026-10-25 08:00 (America/Sao_Paulo)\n## Divergências × especificação\nNenhuma divergência encontrada.\n## 10. Quantidade de ações suspeita\n- nenhuma empresa com quantidade de ações suspeita em 2026-10-23\n## 11. Retornos diários suspeitos\n- nenhum retorno diário suspeito (fechamento_ajustado abaixo de -75% ou acima de 100%)\n## 12. Lacunas nas séries de preços e índices\n- nenhuma lacuna de mais de 5 pregões em v1-precos (regra)\n- nenhuma lacuna em v1-indices (regra)\n"`):
  - faróis `["ok","ok","ok","ok","idle","idle"]`;
  - quantidade: `"0 empresas"`, `"Nenhuma empresa com quantidade de ações fora do plausível em 23/10/2026."`;
  - retornos: `"0 retornos"`, `"Nenhum retorno diário suspeito."`;
  - lacunas: `"0 lacunas"`, `"Preços: nenhuma lacuna. Índices: nenhuma lacuna."`;
  - horário: texto `"Seção não encontrada no diagnóstico."`.
- Seção 11 só com a nota `"- Esta seção não pôde ser concluída; as demais continuaram."` → retornos idle, `"Formato da nota não reconhecido."`, `fonte "Seção 11: Retornos diários suspeitos"`.
- Arquivo ausente → `{"disponivel":False,"motivo":"docs/diagnostico_banco.md não encontrado (rode o diagnóstico)","gerado_em":None,"cartoes":[]}`.
- `tabela_md(["### X","","| a | b |","|---|---|","| 1 | 2 \\| 3 |",""], "X") == [{"a":"1","b":"2 | 3"}]`; com o subtítulo `"Y"` → `None`.

---

### FASE D — `visao.py` + testes (independente)
Arquivos: `processamento/painel/visao.py` (novo), `tests/test_painel_visao.py` (novo). Os testes montam os dicionários à mão, então não dependem da Fase A.

```python
import calendar as _cal; import yaml
from processamento import calendario
from processamento.calendario import SP
from processamento.painel.leitores import _instante, formatar_duracao
MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
ROTULOS_TEMPO = {"coleta_inicio":"coleta começa","entrega":"coleta entrega","rotina_inicio":"rotina começa",
                 "rotina_fim":"pacotes prontos","prazo":"prazo da rotina","abertura":"bolsa abre"}
ERROS_CAL = (calendario.ErroCalendario, OSError, ValueError, yaml.YAMLError)
def fluxo(item: dict | None) -> dict
def linha_do_tempo(item: dict | None, prazo_hhmm: str | None, caminho_calendario: str | None = None) -> dict
def calendario_meses(diarias: list[dict], completas: list[dict], hoje_iso: str,
                     caminho_calendario: str | None = None, max_meses: int = 12) -> list[dict]
```

**`fluxo`:**
- `None` → `{"disponivel":False,"motivo":"Nenhuma execução encontrada em saida/."}`; `legivel False` → `{"disponivel":False,"motivo":f"Arquivo da última execução ilegível ({erro})."}`.
- Senão: `{"disponivel":True,"data","status","possivelmente_interrompida": item.get(...,False),"coleta","processamento","interface"}`.
- **coleta**:
  - estado: coleta vazia ou `consultado False` → `("idle","Coleta não consultada")`; `motivo == "entrega_concluida"` ou `entrega_concluida_em` preenchido → `("ok","Dados entregues")`; motivo em (`entrega_falhou`, `falha_consulta`) → `("bad","Entrega com problema")`; senão `("warn","Entrega não concluída")`;
  - campos `{"estado","titulo","inicio_hhmm": coleta.iniciada_hhmm,"entrega_hhmm","etapas_concluidas","etapas_total","nota": motivo_texto or nota,"daily"}`;
  - etapas: valores `v` ou `v["status"]`; conta os `"concluida"`. Sem etapas → `None`/`None`.
- **processamento**:
  - status `ok` → `("ok","Calculado e validado")`, `parcial` → `("warn","Gerado com pendências")`, `falhou` → `("bad","Falhou")`, `em_andamento` → `("idle","Em andamento")`; outro → `("idle", status or "sem dados")`;
  - campos `{"estado","titulo","duracao_texto","n_acoes": registros do pacote resumo_acao ou None,"n_avisos","rodada","inicio","fim"}`.
- **interface**:
  - n = `n_pacotes or 0`; estado ok se n > 0, bad se status falhou, senão idle;
  - título `"1 pacote pronto"` / `f"{n} pacotes prontos"` / `"Nenhum pacote"`;
  - campos `{"estado","titulo","n_pacotes","versao_contrato","registros_total": soma dos registros int}`.

**`linha_do_tempo`:**
- Item `None`, ilegível ou com tipo diferente de `"diaria"` → `{"disponivel":False,"motivo":"Nenhuma rotina diária para mostrar."}`.
- `d = data_referencia`. `no_dia(txt)` = `_instante(txt).astimezone(SP)` se a data em SP for `d`, senão `None`.
- Pontos:
  - `coleta_inicio` = coleta.iniciada_em; `entrega` = coleta.entrega_concluida_em; `rotina_inicio` = item.inicio; `rotina_fim` = item.fim;
  - `prazo` = `datetime.combine(d, time.fromisoformat(prazo_hhmm), tzinfo=SP)` se `prazo_hhmm` for HH:MM válido;
  - `abertura` = `horario_b3(d, caminho)[0]`; com `ERROS_CAL` o ponto sai e o aviso `f"Horário da B3 indisponível: {erro}"` entra.
- `marcos` = `[{"id","rotulo","hora":"HH:MM","minuto":h*60+m}]` ordenados por minuto (sort estável, na ordem acima).
- `trechos`:
  - `coleta` (ci → en, se en >= ci);
  - `processamento` (ri → rf);
  - `folga` (rf → prazo, se prazo > rf);
  - cada um `{"id","de","ate"}` em minutos.
- `folga_s` = `int((prazo-rf).total_seconds())` se houver os dois. `folga_texto` = `formatar_duracao(folga_s)` se ≥ 0, senão `"atraso de " + formatar_duracao(-folga_s)`.
- Se `_instante(inicio)` existe mas não cai no dia `d` → aviso `f"A rotina deste pregão rodou em {inst:%d/%m/%Y %H:%M}, fora da manhã do pregão: sem folga a medir."`.
- `eixo` = `{"de": min-5, "ate": max+5}`, ou `None` sem marcos.
- Retorno: `{"disponivel":True,"data","marcos","trechos","eixo","folga_s","folga_texto","avisos":[...]}`.

**`calendario_meses`:**
- Meses = os de `data_referencia` válidas de diárias e completas, mais o mês de `hoje_iso`; ordem decrescente; corta em `max_meses`.
- Por mês: `{"ano","mes","titulo": f"{MESES[m-1]} de {a}","dias":[...]}`.
- Cada dia **só de segunda a sexta**: `{"data","dia","dia_semana": weekday(),"pregao","motivo","status","completa"}`.
  - `motivo = calendario.motivo_sem_pregao(dia, caminho)`; com `ERROS_CAL` → `pregao None`, `motivo None`;
  - `status` = `None` sem diária; `"ilegivel"` se `legivel False`; senão `item.status`;
  - `completa` = há completa nessa data.

**Testes** (yaml real do calendário, `caminho_calendario=None`):
- `item = {"legivel":True,"tipo":"diaria","data_referencia":"2026-10-23","status":"ok","inicio":"2026-10-23T08:23:10-03:00","fim":"2026-10-23T08:27:05-03:00","coleta":{"iniciada_em":"2026-10-23T11:00:01+00:00","entrega_concluida_em":"2026-10-23T08:22:52-03:00"}}` com prazo `"09:45"`:
  - `marcos == [{"id":"coleta_inicio","rotulo":"coleta começa","hora":"08:00","minuto":480},{"id":"entrega","rotulo":"coleta entrega","hora":"08:22","minuto":502},{"id":"rotina_inicio","rotulo":"rotina começa","hora":"08:23","minuto":503},{"id":"rotina_fim","rotulo":"pacotes prontos","hora":"08:27","minuto":507},{"id":"prazo","rotulo":"prazo da rotina","hora":"09:45","minuto":585},{"id":"abertura","rotulo":"bolsa abre","hora":"10:00","minuto":600}]`;
  - `trechos == [{"id":"coleta","de":480,"ate":502},{"id":"processamento","de":503,"ate":507},{"id":"folga","de":507,"ate":585}]`;
  - `eixo == {"de":475,"ate":605}`, `folga_s == 4675`, `folga_texto == "1 h 17 min"`, `avisos == []`.
- Mesmo item com `inicio "2026-10-24T22:46:25-03:00"`, `fim "2026-10-24T22:48:23-03:00"`:
  - ids `["coleta_inicio","entrega","prazo","abertura"]`; `trechos == [{"id":"coleta","de":480,"ate":502}]`;
  - `folga_s is None`, `folga_texto is None`;
  - `avisos == ["A rotina deste pregão rodou em 24/10/2026 22:46, fora da manhã do pregão: sem folga a medir."]`.
- `inicio "2026-10-23T09:50:00-03:00"`, `fim "2026-10-23T09:52:30-03:00"` → `folga_s == -450`, `folga_texto == "atraso de 7 min 30 s"`, sem trecho `folga`.
- `{"legivel":True,"tipo":"diaria","data_referencia":"2026-02-18","coleta":None,"inicio":None,"fim":None}` com prazo `"09:45"` → ids `["prazo","abertura"]`; a abertura tem `"hora":"13:00","minuto":780` (quarta-feira de cinzas).
- Com `caminho_calendario` = yaml tmp `"fuso: x\n"` → sem marco `abertura`; `avisos[0].startswith("Horário da B3 indisponível")`.
- `prazo_hhmm=None` → sem marco `prazo` e `folga_s None`. `linha_do_tempo(None, "09:45") == {"disponivel":False,"motivo":"Nenhuma rotina diária para mostrar."}`.
- `fluxo(None)["motivo"] == "Nenhuma execução encontrada em saida/."`.
- `fluxo` com `{"legivel":True,"data_referencia":"2026-10-23","status":"ok","duracao_texto":"1 min 58 s","n_pacotes":7,"n_avisos":3,"rodada":6,"versao_contrato":"1.0","pacotes":[{"pacote":"acoes","registros":0},{"pacote":"series_diarias","registros":0},{"pacote":"mercado_dia","registros":1},{"pacote":"resumo_acao","registros":85},{"pacote":"fundamentos_trimestrais","registros":8},{"pacote":"proventos","registros":0},{"pacote":"noticias_dia","registros":85}],"coleta":{"consultado":True,"motivo":"entrega_concluida","motivo_texto":"entrega concluída","iniciada_hhmm":"08:00","entrega_hhmm":"08:22","entrega_concluida_em":"2026-10-23T08:22:52-03:00","daily":"2026-10-23-daily-080001","etapas":{"precos":"concluida","noticias":"concluida","entrega":"em_andamento"}}}`:
  - `coleta == {"estado":"ok","titulo":"Dados entregues","inicio_hhmm":"08:00","entrega_hhmm":"08:22","etapas_concluidas":2,"etapas_total":3,"nota":"entrega concluída","daily":"2026-10-23-daily-080001"}`;
  - `processamento["estado"] == "ok"`, `["titulo"] == "Calculado e validado"`, `["n_acoes"] == 85`;
  - `interface == {"estado":"ok","titulo":"7 pacotes prontos","n_pacotes":7,"versao_contrato":"1.0","registros_total":179}`.
- Variações de `fluxo`: `status "falhou"`, `n_pacotes 0` → interface `("bad","Nenhum pacote")`, processamento `("bad","Falhou")`. Coleta `{"consultado":False,"nota":"x"}` → `("idle","Coleta não consultada")`, `etapas_total None`.
- `calendario_meses(diarias, completas, "2026-10-23")` com `diarias = [{"data_referencia":"2026-10-23","legivel":True,"status":"ok"},{"data_referencia":"2026-10-22","legivel":True,"status":"falhou"},{"data_referencia":"2026-10-21","legivel":False,"status":None},{"data_referencia":"2026-10-20","legivel":True,"status":"em_andamento"}]` e `completas = [{"data_referencia":"2026-10-23","legivel":True,"status":"ok"}]`:
  - 1 mês, `titulo "outubro de 2026"`, `len(dias) == 22`;
  - `dias[0] == {"data":"2026-10-01","dia":1,"dia_semana":3,"pregao":True,"motivo":None,"status":None,"completa":False}`;
  - dia 12: `pregao False`, `motivo "Nossa Senhora Aparecida"`;
  - dia 23: `status "ok"`, `completa True`; dia 22 `"falhou"`; dia 21 `"ilegivel"`; dia 20 `"em_andamento"`.
- Com `hoje_iso "2026-11-02"` → títulos `["novembro de 2026","outubro de 2026"]`.

---

### FASE E — `servidor.py` + testes (depois de A, B, C e D)
Arquivos: `processamento/painel/servidor.py`, `tests/test_painel_servidor.py`.

```python
from processamento.painel import acoes, leitores, marcos, relatorios, saude, visao

def estado_com_marcos(executor: acoes.Executor, desde: int | None) -> dict:
    """Estado do Executor com as linhas a partir de `desde` e as etapas calculadas sobre todo o buffer."""
    completo = executor.estado(0)
    todas = completo["linhas"]
    if desde is None:
        linhas = []
    else:
        primeiro = completo["total_linhas"] - len(todas)
        linhas = todas[max(desde, primeiro) - primeiro:]
    return {**completo, "linhas": linhas,
            "marcos": marcos.marcos_acao(completo["id"], todas, rodando=completo["rodando"],
                                         codigo=completo["codigo"], significado=completo["significado"])}
```
- Em `montar_painel` (:117), com `itens_completas = completas if isinstance(completas, list) else []`:
  - `"acao": _seguro(estado_com_marcos, executor, None)`;
  - nova chave `"visao": {"fluxo": _seguro(visao.fluxo, agora_item), "linha_tempo": _seguro(visao.linha_do_tempo, agora_item, leitores.ler_prazo_rotina(raiz), caminho_calendario), "saude": _seguro(saude.cartoes_saude, raiz / "docs" / "diagnostico_banco.md"), "calendario": _seguro(visao.calendario_meses, itens_diarias, itens_completas, agora.astimezone(SP).date().isoformat(), caminho_calendario)}`.
- Rota `/api/acao` (:224): `self._json(200, estado_com_marcos(srv.executor, _desde(partes.query)))`.
- Nada mais muda: Host, Origin, token, rotas exatas, CSP, cabeçalhos, `_iniciar`.
- **Teste existente que muda:** `test_api_painel_chaves_e_valores` (linha 141). O conjunto passa a incluir `"visao"`. Motivo: chave nova.

**Testes novos:**
- `GET /api/painel` com `RELOGIO` (23/10 10:00):
  - `set(dados["visao"]) == {"fluxo","linha_tempo","saude","calendario"}`;
  - fluxo: `coleta.estado "ok"`, `etapas_concluidas 9`, `etapas_total 9`, `inicio_hhmm "08:00"`, `entrega_hhmm "08:22"`; `processamento.duracao_texto "1 min 58 s"`, `n_acoes 85`; `interface.titulo "7 pacotes prontos"`, `versao_contrato "1.0"`, `registros_total 179`;
  - linha_tempo: ids `["coleta_inicio","entrega","prazo","abertura"]`, `avisos[0].startswith("A rotina deste pregão rodou em 24/10/2026 22:46")`, `folga_s is None`;
  - saude: `cartoes[0]["numero"] == "2 divergências"`, faróis `["bad","idle","idle","idle","idle","idle"]`;
  - calendario: `[0]["titulo"] == "outubro de 2026"`; o dia 23 tem `status "ok"` e `completa True`;
  - `dados["acao"]["marcos"] == []`.
- Teste "parar com etapas": POST `testes` → espera `"inicio"` nas linhas (como no teste atual) → parar → `executor.esperar(30)` → `GET /api/acao?desde=0` → ids `["coleta","execucao","fim"]`, `marcos[-1] == {"id":"fim","rotulo":"Encerrado","estado":"erro","detalhe":"parado pelo painel"}`.
- `estado_com_marcos` direto: `ex = acoes.Executor(tmp_path, tmp_path/"logs")`; `ex.iniciar("testes", [sys.executable,"-c","print('..... [100%]'); print('5 passed in 0.10s')"])`; `ex.esperar(30)`. Depois:
  - `r = estado_com_marcos(ex, 0)`: `r["linhas"] == ["..... [100%]","5 passed in 0.10s"]`; estados `["concluida","concluida","concluida"]`; `r["marcos"][1]["detalhe"] == "5 passed in 0.10s"`; `r["marcos"][2]["detalhe"] == "todos os testes passaram"`;
  - `estado_com_marcos(ex,1)["linhas"] == ["5 passed in 0.10s"]`;
  - `estado_com_marcos(ex,None)["linhas"] == []` com 3 marcos.
- Os testes 11 (isolamento de imports) e 12 (textos proibidos) continuam passando sem mudança.

---

### FASE F — `pagina.html` + testes da página (paralela; depende só do contrato acima)
Arquivos: `processamento/painel/pagina.html` (reescrita), `tests/test_painel_pagina.py` (só acrescentar). O implementador lê `docs/painel_referencia.html` (CSS e estrutura) e o `pagina.html` atual (funções a reaproveitar). Se ficar grande demais para um despacho, dividir em F1 (estrutura, CSS, rede/polling, ações e etapas, tema) e F2 (render de fluxo, linha do tempo, saúde, experimento, histórico e testes), uma depois da outra.

**Regras da página (copiar):**
- DOM só com `document.createElement`/`createElementNS` + `textContent`/`setAttribute`. **Proibido** `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`.
- **Nenhum `http://` nem `https://` literal.** O namespace do SVG sai de `const NS_SVG = ["http:", "", "www.w3.org", "2000", "svg"].join("/");`.
- Sem `<link>`, sem `@import`, sem Google Fonts / IBM Plex.
- Fontes: `--f-sans:"Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif; --f-mono:ui-monospace, "Cascadia Mono", Consolas, "Courier New", monospace;`.
- `localStorage` só dentro de `try { … } catch (e) {}` **na mesma linha**.
- Nunca usar "compre", "oportunidade" nem "melhores ações".
- Manter estes textos literais, exigidos pelos testes atuais: `const TOKEN = "__TOKEN_PAINEL__";`, `TESTE DE FUNCIONAMENTO, NÃO É RESULTADO`, `id="agora"`, `id="historico"`, `id="etapas"`, `id="saude"`, `id="experimento"`, `id="testes"`, `id="log"`, `/api/painel`, `/api/acao/iniciar`, `X-Painel-Token`, `"Content-Type": "application/json"`, `"X-Painel-Token": TOKEN`, `Data usada`, `"Data: "`, `Painel sem resposta`, `Nenhuma execução encontrada em saida/.`, `Nenhum pytest rodado pelo painel ainda.`, `Só neste computador (127.0.0.1).`, e "Painel de operação" no `<title>` (`<title>Sala de Operação · Painel de operação do processamento (TCC)</title>`).
- O navegador manda só `{acao: id}`. Polling: `/api/acao?desde=N` a cada 1000 ms enquanto roda; `/api/painel` a cada 30 s quando parado. **Nada de `setTimeout` simulando etapas.**

**CSS:**
- Copiar as linhas 8–131 do protótipo: tokens `:root`, o bloco dark com `@media` e `:root[data-theme="dark"]`, e todas as classes. Só trocar as fontes.
- Acrescentar:
  - `body{margin:0}` e `[hidden]{display:none!important}`;
  - cor da barra dos estágios: `.stage.ok::before{background:var(--ok)}`, `.stage.warn::before{background:var(--warn)}`, `.stage.bad::before{background:var(--bad)}`, `.stage.idle::before{background:var(--idle)}`;
  - `.hc.idle{border-left-color:var(--idle)}`;
  - etapas: `.steps li.bad .ic{background:var(--bad);border-color:var(--bad)}`, `.steps li.skip{color:var(--muted)}`;
  - calendário: `.cal .d.warn{background:var(--warn);color:#fff}`, `.cal .d.run{background:var(--accent);color:#fff}`, `.cal .d.comp{box-shadow:inset 0 -3px 0 var(--accent)}`, `.cal .d[data-clicavel]{cursor:pointer}`;
  - gráfico: `.chart .acaso{fill:var(--track)}`, `.chart .media{stroke:var(--idle);stroke-dasharray:3 3}`, `.chart .ic{stroke:var(--line);stroke-width:2}`, `.chart circle.ok{fill:var(--ok)}`, `.chart circle.idle{fill:var(--idle)}`, `.chart .valor{fill:var(--ink)}`;
  - `.erro-rede` (fundo `--bad-soft`, cor `--bad`), `.detalhe`, `.comando` (mono, fundo `--track`), `tbody tr.clicavel{cursor:pointer}`, `tr.selecionada{background:var(--accent-soft)}`;
  - nas cores do SVG usar classes, não `fill="var(...)"`.

**Estrutura** (ordem do protótipo):
1. `header.top`:
   - `span.lbl` "TCC · Módulo de processamento", `h1` "Sala de Operação", `p.sub` (texto do protótipo), `p#atualizado.note`;
   - `.state` com `span#pill-geral.pill`, `span#pill-hoje.pill`, `button#tema.toggle` "Tema" e `button#btn-atualizar.toggle` "Atualizar";
   - `div#erro-rede.erro-rede hidden` "Painel sem resposta".
2. `section.card#agora`: `h2#h-fluxo`, `span#pill-fluxo`, `div.flow#fluxo` e `p#fluxo-vazio.note hidden`.
   - Título: `"Última atualização · pregão de " + diaSemana + ", " + dd/mm/aaaa`.
   - 3 `div.stage <estado>` + 2 `span.arrow` "→".
   - Estágio 1: lbl "1 · Coleta (outro módulo)"; big = `coleta.titulo`; "Começou HH:MM · entregou HH:MM"; `"N de M etapas concluídas"` (ou a nota).
   - Estágio 2: "2 · Processamento (este módulo)"; big = `titulo`; "Duração X · N ações" (omite N se `null`); "Rodada R · N avisos".
   - Estágio 3: "3 · Interface"; big = `titulo`; "Contrato V · N registros"; `experimento.top_publicado` true → "Top 5 publicado na interface", false → "Top 5 retido (não enviado à interface)".
   - Selo do cartão: ok "Concluída" (ok), parcial "Concluída com pendências" (warn), falhou "Falhou" (bad), em_andamento "Em andamento" (idle), ou "Pode ter sido interrompida" (warn) se `possivelmente_interrompida`.
   - Se `disponivel false`: mostrar o `motivo`.
3. `section.card#linha-tempo`: `h2` "A manhã de um pregão"; `p.why#tl-why` = "A rotina precisa terminar antes da abertura da bolsa para o top 5 valer no histórico do experimento." + (`folga_texto` ? " Folga na última execução: X." : ""); `div.tl#tl`; legenda (do protótipo, com "Processamento" e "Folga até o prazo"); `p.note#tl-avisos` (avisos).
   - Posição: `(m - eixo.de)/(eixo.ate - eixo.de)*100 + "%"`.
   - Trechos: coleta = `var(--accent)`, processamento = `var(--ok)`, folga = `var(--warn-soft)` com borda `1px solid var(--warn)`.
   - Marcos `.mk` alternando `down` pelo índice ímpar, montados com `createElement` (hora em `.t`, rótulo, `.stem`).
4. `section.card#comandos`: `h2` "Ações", `p.why` "Cada botão chama um comando do projeto. Nenhum escreve no banco da coleta."; `div.actions#botoes`; `div.run#run hidden` com `h3#run-t`, `span#run-p.pill`, `p#log-status.note aria-live="polite"`, `ol.steps#steps`, `button#btn-parar hidden` "Parar", e `details` com `summary` "Ver o log completo" e `pre#log`.
   - Cartão `.act` por botão: `h3` = `b.titulo`; `p.what` com a descrição fixa por id:
     - rotina: "Espera a coleta do dia (aqui com --sem-esperar), calcula os indicadores e grava os pacotes desse pregão.";
     - carga: "Gera todos os pacotes inteiros, para a interface começar do zero.";
     - diagnostico: "Confere o banco da coleta contra a especificação e reescreve o relatório.";
     - testes: "Roda os testes automáticos, sem o banco. Pode ser interrompido.".
   - Depois: `p.safe.muted` = `b.aviso`; "Data usada: dd/mm/aaaa (hoje|último pregão|última rotina diária)"; `code.comando`; botão ("Gerar" na carga, "Rodar" nos outros), `disabled` com `b.motivo` ao lado.
   - Clique: `confirm(("Data: …\n" se houver) + aviso + "\n\nComando: " + comando)`, depois POST. Reaproveitar `pedirAcao`, `pararAcao`, `buscarLog`, `sondarLog`, `carregarPainel` e `acrescentarLinhas` do arquivo atual.
   - `renderMarcos(estado)` a cada resposta de `/api/acao` e do `/api/painel` (`d.acao.marcos`). `li` com classe por estado:
     - `concluida` → `done`, ícone "✓";
     - `agora` → `now`;
     - `espera` → `wait`;
     - `erro` → `bad`, ícone "✗";
     - `pulada` → `skip`, ícone "–".
     - Coluna `.tm` = `detalhe`.
   - `#run` aparece se `acao.id`. Selo:
     - rodando → idle "em andamento";
     - código 0 → ok "concluído";
     - `significado === "parado pelo painel"` → warn "parado";
     - outro → bad `"falhou (código N)"`.
5. `section.card#saude`: `h2` "Saúde dos dados", `p.why` (texto do protótipo), `p.note#saude-gerado` ("Diagnóstico de dd/mm/aaaa HH:MM"), `div.health#saude-cartoes`.
   - Cada `div.hc <farol>` tem `span.lbl` (título), `span.n` (número), `p` (texto) e `span.so` (fonte).
   - Embaixo, `details` "Ver o diagnóstico completo" com a tabela de divergências e as notas por seção (reaproveitar `renderSaude` com `d.saude`).
   - `visao.saude.disponivel false` → motivo.
6. `section.card#experimento`: cabeçalho com `h2` "Experimento: top 5 com maior chance de superar o Ibovespa" e `span#faixa-teste.banner` "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO" (oculto só se `mostrar_aviso === false`).
   - Coluna esquerda:
     - `div.lock` com dois SVG estáticos `#cadeado-fechado` e `#cadeado-aberto` (copiar o do protótipo; o aberto com a alça deslocada), `h3#lock-t`, `p#lock-p.note`. Por `trava_teste_final.estado`:
       - `ativa` → fechado, "Teste final trancado", `` `O período a partir de ${dd/mm/aaaa(inicio)} fica fora do desenvolvimento. Ele será aberto uma única vez, na avaliação final.` ``;
       - `definido_nao_liberado` → fechado, "Teste final definido, ainda trancado" + `texto`;
       - `liberado` → aberto, "Teste final liberado (uso único)" + `texto`;
       - `usado` → aberto, "Teste final já usado" + `texto`;
       - outro → "Teste final: sem dados".
     - `dl.kv#exp-kv`:
       - Modelo = `arquivo` sem ".meta.json" + " · " + `situacao_modelo`;
       - Treinado com = período + " · " + linhas `toLocaleString("pt-BR")`;
       - Último treino de desenvolvimento = `pasta · n_pregoes pregões`;
       - Top 5 na interface = Publicado / Retido (não enviado à interface);
       - Chance exibida = Sim / Escondida até a calibração ser liberada / sem dados;
       - Modelo sombra = arquivo · acerto top 5;
       - Registros = `N tops · M resultados`.
   - Coluna direita:
     - `h3` "Acerto do top 5 no desenvolvimento" e `p.note` "Em quantos % dos pregões a ação escolhida superou o Ibovespa no pregão seguinte. A faixa cinza é o que se consegue escolhendo ao acaso; o traço é o intervalo de confiança.";
     - `div.chart#grafico`: SVG por `createElementNS(NS_SVG, …)` com `W=520`, `pl=170`, `pr=60`, `pt=18`, `pb=24` e `H = pt+pb+36*n`.
       - Valores: acertos, ICs, faixa e média. `mn = floor((min-0.005)*100)/100`, `mx = ceil((max+0.005)*100)/100`.
       - Ticks em % inteiros com passo `max(1, ceil((mx-mn)*100/5))`.
       - Elementos: `rect.acaso` da faixa; `line.media`; texto "acaso"; por modelo, texto `.lab` com o rótulo, `line.ic` de ic0 a ic1, `circle` (ok se `v > faixa[1]`, senão idle), texto `.valor` com `pct(v)`.
       - `role="img"` e `aria-label`. Sem dados → "sem dados".
     - `p.note#exp-veredito` com o `veredito`; `a#link-relatorio` "Ver relatório completo" (`href="/api/relatorio"`, `target="_blank"`, `rel="noopener"`) visível se `tem_relatorio`; `p.note` "Não constitui recomendação de investimento.".
7. `div.two`:
   - `section.card#historico`:
     - `h2` "Histórico de execuções"; navegação com `button#mes-ant` "‹", `span#mes-titulo.note` e `button#mes-prox` "›" (índice em `ESTADO.mesIdx`; 0 = mês mais novo de `visao.calendario`);
     - `div.cal#cal`: 5 cabeçalhos seg…sex, `dias[0].dia_semana` brancos e as células `.d`:
       - ok → `ok`; parcial → `warn`; falhou ou ilegivel → `bad`; em_andamento → `run`;
       - `pregao === false` → `hol` com `title` = motivo;
       - `completa` → acrescenta `comp`;
       - clique num dia com diária abre o detalhe;
     - legenda: rodou ok / com pendências / falhou / sem execução / sem pregão / carga completa;
     - `div.tbl#hist-tabela`: colunas Pregão, Tipo ("Rotina diária"/"Carga completa"), Duração, Pacotes, Status (pill). Linha clicável abre `#detalhe` (reaproveitar `itensHistorico` e `mostrarDetalhe`);
     - `p.note` "Cada dia guarda só a última rodada; as anteriores aparecem no log da rotina, abaixo.";
     - `<details id="etapas">` com `summary` "Rodadas registradas no log da rotina" e o conteúdo de `renderEtapas` atual.
   - `section.card#testes`: `h2` "Testes automáticos", `span#pill-testes`.
     - Selo: interrompido → warn; aprovado → ok "todos passando"; reprovado → bad "com falhas"; indisponível → idle "sem dados" + "Nenhum pytest rodado pelo painel ainda.".
     - Contas: `passed`; `falhas = failed + errors`; `pulados = skipped`; `total` = soma com xfailed e xpassed.
     - Big = passed `toLocaleString("pt-BR")` + " testes passaram"; `.meter` com larguras %.
     - Nota `"N falhas · M pulados"`; kv: Rodado em, Tempo, Arquivo (`logs/painel/` + arquivo), Código de saída. Lista de falhas, se houver.
8. `footer` `p.note` "Só neste computador (127.0.0.1). O painel não acessa o banco e não lê o .env; os botões chamam os comandos do projeto."

**Selos do topo:**
- `#pill-geral`:
  - `acao.rodando` → idle "Rodando: <titulo>";
  - `trava.ativa` → warn "Rotina em andamento (trava)";
  - sem `agora` → idle "Sem execução"; ilegível → bad "Última execução ilegível";
  - ok/parcial/falhou → ok/warn/bad "Última rotina: <status>";
  - em_andamento → warn "Última rotina: interrompida?" se `possivelmente_interrompida`, senão idle "Rotina em andamento".
- `#pill-hoje`: `erro` → bad "Calendário com erro"; senão `Capitalizado(dia_semana) + " · " + (pregao ? "dia de pregão" : (motivo === dia_semana ? "sem pregão" : "sem pregão (" + motivo + ")"))`, classe ok se for pregão, idle se não.

**Tema** (cada uso de `localStorage` numa linha com `try`):
```js
const CHAVE_TEMA = "painel-tema";
function aplicarTema(t) { if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t); }
try { aplicarTema(localStorage.getItem(CHAVE_TEMA)); } catch (e) {}
// clique: escuro = data-theme==="dark" || (!data-theme && matchMedia("(prefers-color-scheme: dark)").matches); novo = escuro ? "light" : "dark"
// try { localStorage.setItem(CHAVE_TEMA, novo); } catch (e) {}
```

**Testes novos em `test_painel_pagina.py`:**
- contém `'id="linha-tempo"'`, `'id="tl"'`, `'id="comandos"'`, `'id="run"'`, `'id="steps"'`, `'id="saude-cartoes"'`, `'id="grafico"'`, `'id="cal"'`, `'id="tema"'`, `"Sala de Operação"`, `"Ver o log completo"`, `"Não constitui recomendação de investimento"`, `"createElementNS"`, `"/api/acao?desde="`, `"marcos"`, `"visao"`, `"localStorage"`;
- não contém `"fonts.googleapis"`, `"IBM Plex"`, `"<link"`, `"@import"`, `"compre"`, `"oportunidade"`, `"melhores ações"`;
- toda linha que contém `localStorage` também contém `try`.

---

### FASE G — Verificação final (executor)
1. `.venv/Scripts/python.exe -m pytest -q tests/test_painel_*.py`: os 89 atuais mais os novos.
2. `.venv/Scripts/python.exe -m pytest -q`: a suíte inteira sem falhas.
3. `git status --porcelain`: só mudanças em `processamento/painel/`, `tests/test_painel_*.py`, `tests/fabrica_painel.py` e `tests/dados/painel/`.
4. Busca: `pagina.html` sem `innerHTML|outerHTML|insertAdjacentHTML|document.write|eval(|http://|https://`.
5. Teste manual (usuário): `.venv\Scripts\python.exe -m processamento.painel`, alternar o tema e clicar "Rodar os testes" para ver as etapas acenderem. Não clicar em rotina, carga ou diagnóstico na verificação automática.

### Riscos (para o implementador)
- Os formatos do diagnóstico e dos logs são lidos por regex. Se mudarem, o cartão ou a etapa vira "sem dados" / "agora até o fim". Os testes com os textos literais acusam.
- `estado_com_marcos` copia até 5000 linhas por consulta (1 por segundo): custo desprezível. Se o pytest tiver mais de 5000 linhas de traceback, o 1º marcador some, mas a regra de "pular para a frente" conclui pela linha de resumo.
- O cálculo de `visao` roda também no POST de iniciar (dentro de `montar_painel`): fica alguns milissegundos mais lento, sem efeito na segurança.

### Arquivos de referência
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\docs\painel_referencia.html` (CSS nas linhas 8–131)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\servidor.py` (`montar_painel` :117, rota `/api/acao` :224)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\leitores.py` (`_resumir_coleta` :188, `resumir_execucao` :209, `_item_ilegivel` :201)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\relatorios.py` (`_classificar_linha` :99, regex :13-30)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\acoes.py` (`Executor.estado` :215)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\painel\pagina.html` (funções a reaproveitar)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\calendario.py` (`horario_b3` :192, `motivo_sem_pregao` :367, `carregar_parametros` com cache :132)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\rotina\executar.py` (textos do log :98-108, :157-291)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\saida\gerar.py` (:388-422), `processamento\diagnostico\__main__.py` (:105-145), `processamento\diagnostico\temas.py` (:1119-1180), `lacunas.py` (:92-116), `historico.py` (:87)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\config\parametros.yaml` (`rotina.prazo` ~:222)
- `C:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\tests\test_painel_servidor.py:141` (único teste existente que muda)