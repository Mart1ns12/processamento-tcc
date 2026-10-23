# PLANO: ETAPA 7, SAÍDA (os 10 pacotes JSON)

> **ESTADO DA IMPLEMENTAÇÃO (23/10/2026, parada a pedido do usuário):**
> - **Prontas:** Fase 0 (parâmetros), 1 (`fatos/series.py`), 2 (`fatos/multiplos.py`), 3 (`fatos/noticias.py`), 4 (`saida/contrato.py`, `saida/insumos.py`, `tests/fabrica_saida.py`), 5 (`saida/textos.py`). `ESPECIFICACAO.md` já atualizada (seção 13 deste plano, S1–S20, janela de 253).
> - **Faltam:** 6a (`pacotes_fatos.py`), 6b (`pacote_series.py`), 6c (`pacote_noticias.py`), 7 (`pacotes_experimento.py`) — podem rodar em paralelo — e depois a 8 (`gerar.py`, `__main__.py`, teste ponta a ponta e de vazamento). O comando `python -m processamento.saida` ainda não existe.
> - **Testes:** `pytest -q` = 1046 passaram, 22 pulados, 1 xfail; com `PROC_TESTES_COM_BANCO=1`: 1068 passaram, 1 xfail.
> - **ATENÇÃO antes do commit:** o `.gitignore` (linha 211, `saida/`) também ignora o código em `processamento/saida/`. Trocar por `/saida/` (só a pasta de saída da raiz) e conferir com `git status`.
> - **Pendências achadas:** (1) xfail em `tests/test_saida_contrato.py` (caso 10): bug antigo em `fontes.unir_historicos` (~linha 623): `resultado[manter]` com lista vazia perde as colunas e dá `KeyError 'data'` quando não há preço até D; correção sugerida `resultado.loc[manter]`; ao corrigir, tirar o xfail (strict). (2) BDR: `multiplos_diarios` segue `calcular_fundamentos_no_dia`, que dá P/L e P/VP de BDR `historico_insuficiente` antes do 1º balanço e `indisponivel` depois, enquanto a D9 diz `indisponivel` sempre; decidir se corrige a etapa 4 (e o oráculo) ou mantém. (3) Ajustes menores das fases 3, 4 e 5 relatados (ex.: `noticias_dia` com probabilidade ausente → contagens `indisponivel`; `coleta_status` do `execucao` aceita só `{consultado, nota}` — a Fase 8/etapa 8 precisa ampliar o esquema; `validar_serie` confere datas < D, não ≤ t).

> **Aprovado pelo usuário em 23/10/2026:** S1 a S18 com as recomendações, S11 com ajuste (uso único só com `treino.teste_final.fim` preenchido) e duas decisões novas: **S19** (janelas: séries com os últimos 253 pregões, trimestres 8, proventos 5 anos) e **S20** (formato compacto só no `series_diarias`). Plano já atualizado com elas. Nada foi implementado.
> Quando o plano foi feito: `pytest -q` = 911 testes com os de banco ligados (informado). Ambiente: Python 3.12 (.venv), pandas 3.1.0, numpy 2.5.4, xgboost 3.4.1. **O venv não tem `openpyxl` nem `jsonschema`** (a planilha foi lida abrindo o .xlsx como zip).
> Os valores marcados **(conferido)** foram calculados rodando as funções que já existem sobre as fábricas de teste (`tests/dados` em SQLite e `tests/fabrica_fundamentos.py`), sem banco e sem rede. Os outros foram feitos à mão e estão com a conta ao lado.

## Resumo

A etapa entrega `python -m processamento.saida --data AAAA-MM-DD`. A data é o **dia da rotina** (D, o pregão que o top 5 tenta prever). O comando lê a coleta só por `fontes.py`, corta tudo no ponto certo (preços, balanços, proventos e índices até o último pregão antes de D, que chamamos de **t**; notícias até 08:00 de D) e grava os 10 pacotes em `saida/D/`, um arquivo por pacote, na ordem da seção 8.5. Cada arquivo é um "lote" com o envelope (`pacote`, `chave`, `versao_contrato`) e os registros; cada registro traz `versao_contrato: "1.0"`, `gerado_em` e `dados_ate`. Todo pacote passa por um **validador próprio** antes de ser gravado (sem dependência nova).

O que é conta nova vai para `processamento/fatos/` como função pura com teste: séries base 100 (ação, IBOV, setor, CDI, IPCA, IDIV/SMLL/IFIX), **P/L, P/VP e yield diários** (calculados por trechos entre entregas de balanço: ~10 s para 346 pregões × 81 empresas, **medido** num protótipo, contra ~14 min do jeito ingênuo) e as notícias da janela do painel (rótulo, destaque, resumo). O resto (`processamento/saida/`) só empacota.

O experimento continua trancado: antes da produção, o `experimento_top` sai com o modelo provisório (`xgb-2026-06`), `valido_para_historico: false`, chance escondida (`valor: null`) e avisos; o `experimento_historico` sai **vazio** (`n_dias: 0`, com nota), e nenhum dia do teste final (pregão previsto ≥ 23/06/2026) é sequer fechado. O top 5 de cada dia fica num registro em `registros/experimento/` (de uso único só em produção, com `treino.teste_final.fim` preenchido; antes disso cada rodada sobrescreve), de onde sai o histórico ao vivo depois da produção. As séries levam só os últimos 253 pregões (S19), no formato compacto (S20).

**Pronto quando (seção 9, etapa 7):** "Os 10 pacotes da seção 8 gerados em JSON, validados contra o contrato". Traduzindo:
- (a) `.venv\Scripts\python.exe -m pytest -q` sem falhas (os 911 + ~120 novos);
- (b) o teste ponta a ponta gera os 10 arquivos a partir de `tests/dados` (SQLite), todos aprovados pelo validador, com os valores conferidos da seção 4;
- (c) o teste de vazamento (dados "envenenados" depois de t e depois de 08:00 de D) dá arquivos idênticos;
- (d) **ação do usuário** (lê o banco, o subagente não roda): `python -m processamento.saida --data 2026-10-23` sai com código 0 e cria `saida/2026-10-23/` com os 10 arquivos.

---

## 1. O que já existe e será reusado (não reescrever)

| Para quê | Função | Onde |
|---|---|---|
| Grade pregão × ticker de uma coluna de preço | `grade_de_precos` | `processamento/fatos/precos.py:125` |
| Variação as-of (cotação do dia, IBOV/USDBRL/BRENT) | `variacao(g, 1)` | `precos.py:137` |
| Retorno diário sem preencher lacunas (setor) | `retornos_diarios` | `precos.py:145` |
| Todos os indicadores de preço do painel em grades | `calcular_precos` | `precos.py:316` |
| Formato longo de um dia | `resumo_precos_no_dia` | `precos.py:366` |
| Tickers do painel / pares (sem BDR) / setor e CNPJ | `tickers_do_painel`, `pares_do_painel`, `mapas_cadastro` | `precos.py:295`, `:300`, `:213` |
| Status, `Grade`, `montar_grade`, `indice_pregoes` | — | `precos.py:18-21`, `:101`, `:115`, `:120` |
| % de CDI, IPCA, IDIV, SMLL, IFIX, IVVB11 por janela | `calcular_indices`, `indices_no_dia` | `processamento/fatos/indices.py:154`, `:172` |
| CDI do dia, IPCA 12m, "IPCA até" | `cdi_dia`, `ipca_12m`, `ipca_ate` | `indices.py:120`, `:129`, `:148` |
| Taxas do CDI, meses do IPCA, K(d) | `_serie_cdi`, `_meses_ipca`, `_k` | `indices.py:39`, `:46`, `:53` |
| Grade dos índices em pontos | `grade_de_indices` | `indices.py:27` |
| Fundamentos de todos os tickers em t | `calcular_fundamentos_no_dia` (+ `INDICADORES`) | `processamento/fatos/fundamentos.py:413` (`:346`) |
| Valor de mercado, indicadores da empresa | `valor_de_mercado`, `indicadores_empresa`, `LUCRO_NEGATIVO` | `fundamentos.py:140`, `:191`, `:48` |
| Regra "P/L com prejuízo mantém o valor" | `_grade_do_dia` | `fundamentos.py:398` |
| Payout por ano, balanço de referência, tabela trimestral | `payout_por_ano`, `balanco_referencia_no_dia`, `tabela_trimestral` (`CAMPOS_TRIMESTRAIS`) | `fundamentos.py:506`, `:536`, `:623` (`:560`) |
| Proventos | `ligar_proventos`, `_do_ticker`, `dividend_yield`, `acoes_disponiveis`, `acoes_na_data`, `soma_por_ano`, `lista_proventos`, `inicio_janela` | `processamento/fatos/proventos.py:25`, `:58`, `:70`, `:83`, `:99`, `:154`, `:174`, `:20` |
| Foto do balanço point-in-time | `foto_balanco` | `processamento/fatos/trimestres.py:206` |
| Pregões, corte das 08:00, janelas | `pregoes`, `corte_manha`, `proximo_pregao`, `classificar_noticias` | `processamento/calendario.py:160`, `:210`, `:217`, `:278` |
| Chaves de topo do yaml | `_CHAVES_DE_TOPO` | `calendario.py:21` |
| Universo do dia | `montar_universo` | `processamento/universo.py:43` |
| Leitura (única com SQL) | `ler_tabela`, `ler_noticias`, `ler_composicao`, `mudancas_como_dict`, `RAIZ`, `SP` | `processamento/fontes.py:383`, `:419`, `:680`, `:597`, `:26`, `:222` |
| Leitor READ ONLY e códigos de erro do CLI | `_leitor_padrao`, `main` | `processamento/experimento/dataset.py:144`, `:253-289` |
| Dataset ao vivo (linha de t, noite fechada em D) | `DadosExperimento`, `montar_dataset(..., proximo_ao_vivo=D)` | `dataset.py:43`, `:79` |
| Notícias: empresa e duplicadas (E10) | `ligar_empresa`, `deduplicar` | `processamento/experimento/noticias.py:54`, `:65` |
| Ranks (mesma função do treino) | `preparar` | `processamento/experimento/preparacao.py:47` |
| Top do dia, motivos, chance (F16), sombras | `top_do_dia`, `motivos`, `chance`, `top_sombra_modelo`, `top_sombra_volatilidade` | `processamento/experimento/previsao.py:84`, `:29`, `:51`, `:124`, `:119` |
| Como montar `preparado_dia`/`bruto_dia` | `_exemplo_top` (modelo a copiar) | `processamento/experimento/treino.py:596-618` |
| Modelo e `.meta.json` | `carregar_modelo`, `nome_modelo`, `CHAVES_METADADOS`, `salvar_modelo`, `treinar_xgb` | `processamento/experimento/modelos.py:138`, `:116`, `:26`, `:123`, `:47` |
| Aviso do modelo provisório | `AVISO_PROVISORIO` | `treino.py:361` |
| Alvo t → t+1 (fechar o dia) | `alvos` | `processamento/experimento/alvo.py:42` |
| Faixa do acaso | `faixa_do_acaso` | `processamento/experimento/avaliacao.py:128` |
| Parâmetros do treino | `carregar_parametros_treino` | `processamento/experimento/parametros.py:320` |
| Percentual em português; rodapé fixo | `pct`, `RODAPE` | `processamento/experimento/relatorio.py:40`, `:14` |
| Fábricas de teste | `banco_teste`, `mundo()`, `precos_de`, `cadastro_de`, `indices_de`, `noticias_de`, `dataset_sintetico`, `params_teste` | `tests/conftest.py:29`, `tests/fabrica_fundamentos.py:270`, `tests/fabrica_precos.py:32/63/54`, `tests/fabrica_experimento.py:50`, `tests/fabrica_treino.py:26/109` |

**Lacuna encontrada:** a seção 2.1 prevê `processamento/fatos/noticias.py` ("resumo do tom e manchetes do dia"), mas ele nunca foi criado. A Fase 3 cria.

---

## 2. Convenções gerais da saída

### 2.1 Datas de referência (decisão S1)
- **D** = dia da rotina (`--data`) = pregão previsto. **t** = último pregão com preço do IBOV **antes** de D (preços lidos com `ate = D − 1 dia`).
- `mercado_dia`, `resumo_acao`, `noticias_dia`: `data_referencia = t` (é a data do fechamento mostrado).
- `experimento_top`, `execucao`: `data_referencia = D`. O `experimento_top` também traz `pregao_base = t`.
- `experimento_historico`: `data_referencia` = dia fechado (pregão previsto cujo resultado acabou de sair); sem dia fechado, D.
- `series_diarias`: chave `ticker` + `data` (cada ponto); a última data é t.
- `dados_ate` = `corte_manha(D)` em ISO (ex.: `"2026-10-23T08:00:00-03:00"`), igual em todos os pacotes da rodada. `gerado_em` = instante da geração (`datetime.now(SP).isoformat(timespec="seconds")`; nos testes, injetado).

### 2.2 Folha (decisão S2)
Todo número de indicador vira uma **folha**: `{"valor": <número ou null>, "status": <status>}`. O validador confere:
- `status` ∈ `ok`, `nao_se_aplica`, `indisponivel`, `historico_insuficiente`, `lucro_negativo`;
- `status == "ok"` ⇒ `valor` não nulo; `valor` nulo ⇒ `status != "ok"`;
- `valor` não nulo com `status != "ok"` só com `lucro_negativo` (P/L com prejuízo, decisão da etapa 4);
- nunca NaN nem Infinity (JSON gravado com `allow_nan=False`).

Variantes: **folha bool** (`caixa_liquido`), **folha texto** (`ipca_ate`: `"2025-09"`), **folha data** (`data_pagamento`). Algumas folhas levam `texto` (texto pronto ou null) e sub-folhas (`setor`, `posicao_pct`). Campos de cadastro (`empresa`, `setor`, `subsetor`) podem ser `null` sem status (não são indicadores). Campos que não se aplicam a um tipo de série ficam **ausentes** (não `null`).

### 2.3 Arquivo, envelope e registros (decisão S3)
Um arquivo por pacote em `saida/D/<pacote>.json` (UTF-8):
```json
{"pacote": "resumo_acao", "versao_contrato": "1.0", "chave": ["data_referencia", "ticker"],
 "gerado_em": "2025-10-22T09:00:00-03:00", "dados_ate": "2025-10-22T08:00:00-03:00",
 "registros": [{"versao_contrato": "1.0", "gerado_em": "...", "dados_ate": "...", "...": "..."}],
 "removidos": []}
```
Cada registro repete `versao_contrato`, `gerado_em` e `dados_ate` (a API pode receber um por chamada ou em lote, seção 8.6). `removidos` (lista de objetos só com os campos da chave) existe só nos pacotes "quando muda" (nos outros, lista vazia).

**Exceção (S20):** o `series_diarias` não usa folhas; cada série vai no formato compacto (listas paralelas `datas`/`valores` e trechos de `status`), descrito na 4.4.

### 2.4 Envio "quando muda" (decisão S4)
`acoes`, `fundamentos_trimestrais`, `proventos` e `series_diarias` comparam com o **estado do último envio** (`saida/estado/<pacote>.json`):
- sem estado (primeira vez, estado apagado ou `--sem-estado`): manda tudo (nas séries, `substituir_serie: true`);
- registro novo ou alterado: vai; registro que sumiu: a chave vai em `removidos`;
- série com **qualquer ponto antigo alterado ou sumido**: vai a série inteira com `substituir_serie: true`; senão, só os pontos com data maior que a última do estado, com `substituir_serie: false`; sem novidade, a série não vai; série que sumiu: o `ticker` vai em `removidos`;
- **janela das séries (S19):** cada série leva só os pontos com data ≥ `inicio_janela` (o 1º dos últimos 253 pregões até t). Ponto do estado com data < `inicio_janela` atual saiu **pelo corte**: **não** conta como sumido (não dispara `substituir_serie`); a API apaga sozinha os pontos da série com data < `inicio_janela`. Sumido de verdade = ponto do estado com data ≥ `inicio_janela` atual que não está mais na série. Exemplo: no dia seguinte, com 1 pregão novo, o mais antigo sai da janela → vai só o ponto novo, `substituir_serie: false`, `inicio_janela` avança 1 pregão;
- **trimestres e proventos (S19):** o que sai do corte (9º trimestre mais antigo; provento de ano fora dos 5) some da lista atual e vai em `removidos` pela regra normal;
- números comparados com `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)` (a coleta regrava o histórico todo dia); `gerado_em`, `dados_ate` e `versao_contrato` não entram na comparação;
- o estado é regravado logo depois de gravar o pacote (com a API, será depois do envio aceito).

**Por que dividendo não obriga reenvio, mas desdobramento sim:** `indice_retorno_total(d) = aj(d)/aj(início) × 100`, com início = 1º dia da série no histórico inteiro (âncora fixa, não o início da janela). Quando sai um dividendo, a coleta multiplica todo `aj` anterior à data-ex pelo mesmo fator f; para d antes da data-ex, `f·aj(d) / (f·aj(início))` não muda. Já um desdobramento muda o `fechamento` de todos os dias antigos, e uma reapresentação de balanço muda P/L e P/VP antigos. A comparação com o estado pega todos os casos sem precisar saber o motivo. Também pega a chegada do histórico de 5 anos (o início da série muda: reenvio inteiro, uma vez).

### 2.5 Ordem e nomes dos arquivos (seção 8.5)
1. `execucao.json` (status `em_andamento`); 2. `acoes.json`; 3. `series_diarias.json`; 4. `mercado_dia.json`; 5. `resumo_acao.json`; 6. `fundamentos_trimestrais.json` e `proventos.json`; 7. `noticias_dia.json`; 8. `experimento_historico.json`; 9. `experimento_top.json`; 10. `execucao.json` regravado (status final).
Escrita atômica (grava `<nome>.json.tmp` e renomeia com `os.replace`). `indent=2`, exceto `series_diarias` e `proventos` (compactos, `separators=(",", ":")`).

---

## 3. Pegadinhas para copiar em TODO despacho ao implementador

1. **Banco:** nenhum módulo novo faz SQL. A leitura acontece só em `processamento/saida/insumos.py`, via `fontes.ler_tabela`/`ler_noticias`/`ler_composicao`. Nos testes, use `banco_teste` (SQLite de `tests/dados`, `tests/conftest.py:29`) ou DataFrames das fábricas; nunca `fontes.criar_engine`; nunca rodar `pytest -m banco`. A pasta `extracao-dados-tcc-main/` é só consulta: nunca executar nem importar.
2. **Ausência = None/NaN + status, nunca 0.** Exceções já decididas: yield e payout 0.0 `ok` sem provento (D8); `noticias_dia` com quantidade 0 `ok`. Nada de `fillna(0)`.
3. **JSON:** `json.dumps(..., ensure_ascii=False, allow_nan=False)`. Converter numpy para Python e NaN para None **antes** (use `contrato.folha`). Datas `"AAAA-MM-DD"`; data-hora `isoformat(timespec="seconds")` no fuso de São Paulo (`-03:00`).
4. **Unidades:** percentuais em fração (`0.05` = 5%); dinheiro em reais sem escala; BRENT em US$/barril e USDBRL em R$/US$ (campo `unidade`).
5. **YAML:** horas, datas e caminhos entre aspas. O bloco novo `saida` precisa entrar em `calendario._CHAVES_DE_TOPO` (`calendario.py:21`). `carregar_parametros` tem `lru_cache`: nos testes, passe o caminho de um yaml temporário.
6. **pandas 3.1:** Copy-on-Write (use `.loc`/`assign`, nada de atribuição encadeada); texto é o dtype padrão; CNPJ é texto (zero à esquerda).
7. **Linguagem:** nunca "compre", "recomendação", "oportunidade", "melhores ações". Use "estimativa", "experimento", "maior chance segundo o modelo". O aviso fixo `"Não constitui recomendação de investimento."` (`relatorio.RODAPE`) é a única ocorrência permitida de "recomendação".
8. **Teste final trancado:** nenhum pacote pode trazer resultado (acerto, retorno do dia previsto) de pregão previsto ≥ 2026-06-23. Com `treino.teste_final.fim` vazio (hoje), **nenhum dia é fechado**.
9. **Point-in-time:** toda função recebe `t` (e `D`) explícitos. Nunca use `cal[-1]`, `max(data)` ou "hoje" como data de referência dentro das funções puras.
10. **Não altere** as funções existentes de `fatos/` e `experimento/` (só reuse). Se algo não encaixar, pare e avise.
11. **Testes:** sem rede e sem banco; o gabarito é só o deste plano; comando `.venv\Scripts\python.exe -m pytest -q <arquivos>`. Não fazer commit.
12. **Cortes do pacote (S19) não mudam as contas:** séries com os últimos 253 pregões até t (252 variações), trimestres com os 8 mais recentes, proventos com 5 anos. Os cálculos usam o histórico inteiro (base 100 desde o 1º dia da série, 12 meses, beta etc.); só o pacote é cortado. **Não rebasear** a série no início da janela.
13. **`series_diarias` é compacto (S20):** `datas` + `valores` (listas do mesmo tamanho) + `status` em trechos; os outros pacotes seguem com a folha `{valor, status}`. Números sem arredondar.

---

## 4. Os 10 pacotes: campos, status, chave e gabaritos (item A)

Notação: **F** = folha `{valor: número|null, status}`; **F+t** = folha com `texto` (texto ou null); **Fb** = folha bool; **Ftx** = folha texto; **Fd** = folha data. "Meta" = `versao_contrato` ("1.0"), `gerado_em` (data-hora), `dados_ate` (data-hora), obrigatórios em todo registro.

**Cenário E2E (usado nos gabaritos):** banco de teste `tests/dados` (SQLite) com **D = 2025-10-22**. Pregões lidos: 2025-10-16, 10-17, 10-20, 10-21, logo **t = 2025-10-21**. Painel (cadastro sem CRFB3): ABEV3, ITUB4, JBSS32, NOVA3, PETR3, PETR4, TAEE11. `dados_ate = "2025-10-22T08:00:00-03:00"`; nos testes, `agora = 2025-10-22 09:00:00` de SP, então `gerado_em = "2025-10-22T09:00:00-03:00"`.

### 4.1 `acoes` (chave `ticker`; "quando muda")
Um registro por ticker de `tickers_do_painel` (cadastro sem os excluídos; BDR entra).

| campo | tipo | obrigatório | origem |
|---|---|---|---|
| Meta | — | sim | — |
| `ticker` | texto | sim | cadastro |
| `empresa`, `setor`, `subsetor` | texto ou null | sim | cadastro |
| `tipo_acao` | "ON", "PN", "UNIT" ou "BDR" | sim | cadastro |
| `ativo_no_universo` | bool | sim | `montar_universo` em t: `motivo` ∈ {"ok", "sem_preco"} (S16) |

**Gabarito E2E (conferido):** 7 registros, em ordem de ticker; `ativo_no_universo` = false só em JBSS32 (motivo `tipo_nao_aceito`); ABEV3 e ITUB4 = true (motivo `sem_preco` em t); CRFB3 não aparece. PETR4: `empresa = "PETROBRAS"`, `setor = "Petroleo"`, `subsetor = "Petroleo e gas"`, `tipo_acao = "PN"`.

### 4.2 `mercado_dia` (chave `data_referencia`; todo dia)
| campo | tipo | origem |
|---|---|---|
| Meta, `data_referencia` (= t) | — | — |
| `IBOV`, `USDBRL`, `BRENT` | objeto `{fechamento: F, variacao_dia: F, unidade}`; unidade "pontos", "BRL/USD", "USD/barril" | `grade_de_precos(precos, cal, "fechamento", [..])` na linha t; `variacao(g, 1)` na linha t; fechamento NaN → `indisponivel` |
| `cdi_dia` | F (fração ao dia) | `indices.cdi_dia(indices, t)` |
| `cdi_data` | data ou null | 3º item de `cdi_dia` |
| `ipca_12m` | F | `indices.ipca_12m(indices, t)` |
| `ipca_ate` | Ftx ("AAAA-MM") | `indices.ipca_ate(indices, t)`; None → `{valor: null, status: "indisponivel"}` |
| `indices` | objeto `{CDI, IPCA, IDIV, SMLL, IFIX, IVVB11}`, cada um `{d1, m1, m6, a1}` de F | `calcular_indices(precos, indices, cal, params_precos)` na linha t (S7) |

**Gabarito E2E (conferido):** `data_referencia = "2025-10-21"`; IBOV `{fechamento: {10.0, ok}, variacao_dia: {0.0, ok}}`; BRENT igual (a variação usa a base as-of de 10-20); USDBRL `{fechamento: {null, indisponivel}, variacao_dia: {null, indisponivel}}` (não está no banco de teste); `cdi_dia = {0.0006, ok}`, `cdi_data = "2025-10-21"`; `ipca_12m = {null, historico_insuficiente}`; `ipca_ate = {"2025-09", ok}`; `indices.CDI.d1 = {0.0005, ok}` e `m1/m6/a1` `historico_insuficiente`; `indices.IDIV.d1 = {0.01, ok}`; `indices.IPCA.d1 = {0.0, ok}`; IFIX, SMLL e IVVB11: as quatro janelas `{null, indisponivel}`.

### 4.3 `resumo_acao` (chave `data_referencia` + `ticker`; todo dia)
Um registro por ticker do painel. Origem: `resumo_precos_no_dia(calcular_precos(...), t)`, `calcular_fundamentos_no_dia(t, ...)`, `payout_por_ano(t, ...)`, `soma_por_ano(...)`, `balanco_referencia_no_dia(t, ...)`.

| campo | tipo | chave interna de origem |
|---|---|---|
| Meta, `data_referencia` (= t), `ticker` | — | — |
| `cotacao` | `{fechamento: F, variacao_dia: F}` | `cotacao.fechamento`, `cotacao.variacao_dia` |
| `variacao_preco` | `{d1, m1, m6, a1}` de F | `variacao_preco.<j>` |
| `rentabilidade` | `{d1, m1, m6, a1}` de F + `ibov: {d1..a1}` + `setor: {d1..a1}` | `rentabilidade.<j>`, `rentabilidade.ibov.<j>`, `rentabilidade.setor.<j>` |
| `volume` | `{total: F, relativo: F+t, mediana_20: F, posicao_pct: F}` | `volume.total`, `volume.relativo`, `volume.mediana_20`, `volume.posicao_pct` |
| `volatilidade_20d` | F+t com sub-folha `posicao_pct: F` | `volatilidade_20d.valor`, `volatilidade_20d.posicao_pct` |
| `beta` | F+t | `beta.valor` |
| `pl` | F+t com sub-folha `setor: F` | `pl.valor`, `pl.setor` (valor mantido com `lucro_negativo`) |
| `pvp`, `roe`, `dividend_yield`, `payout`, `margem_bruta`, `margem_liquida` | F com sub-folha `setor: F` | `<x>.valor`, `<x>.setor` |
| `payout_por_ano` | lista `{ano: inteiro, valor, status}` | `payout_por_ano(t)` do ticker |
| `proventos_por_ano` | lista `{ano: inteiro, valor, status}` (5 anos; S15) | `soma_por_ano(ligados, ticker, tipo_acao, t, anos_historico_proventos)` |
| `ebitda` | `{rotulo: "EBITDA (cálculo padrão CVM)", valor_12m: F, margem: F, setor_margem: F}` | `ebitda.valor_12m`, `ebitda.margem`, `ebitda.setor_margem` |
| `endividamento` | `{divida_liquida, dl_pl, dl_ebitda: F; caixa_liquido: Fb; setor_dl_pl, setor_dl_ebitda: F; aviso: "Dívida líquida sem arrendamentos."}` | `endividamento.*` (caixa_liquido 1.0/0.0 → true/false) |
| `setor_comparacao_fraca` | bool | `setor_comparacao_fraca` (1.0 → true) |
| `balanco_referencia` | `{data_fim_periodo: data ou null, data_entrega: data ou null, status}` | `balanco_referencia_no_dia(t)` |

Textos (`saida/textos.py`, seção 12, Fase 5): `volume.relativo.texto = texto_volume(valor)`; `volatilidade_20d.texto = texto_volatilidade(posicao_pct)`; `beta.texto = texto_beta(valor)`; `pl.texto = texto_pl(valor, status)`; com valor nulo, `texto = null`.

**Gabarito E2E, PETR4 (conferido):**
- `cotacao`: fechamento `{10.0, ok}`, variacao_dia `{0.0, ok}`; `variacao_preco.d1 = {0.0, ok}`, m1/m6/a1 `historico_insuficiente`;
- `rentabilidade.d1 = {0.0, ok}`, m1/m6/a1 `historico_insuficiente`; `ibov.d1 = {0.0, ok}`, demais `historico_insuficiente`; `setor.*` todos `{null, indisponivel}` (setor "Petroleo" só tem a Petrobras);
- `volume.total = {1000.0, ok}`; relativo, mediana_20 e posicao_pct `historico_insuficiente`; `volatilidade_20d` e `beta` `historico_insuficiente`, texto null;
- `pl = {6.896551724137931, ok}` (1000/145: valor de mercado 10×60 + 10×40, lucro 12m 30+40+35+40), `pl.setor = {null, indisponivel}`, `pl.texto = null`;
- `pvp = {0.8333333333333334, ok}`; `roe = {0.12083333333333333, ok}`; `dividend_yield = {0.05, ok}` (0,50 ÷ 10; o JCP de 2024-10-21 fica fora porque a janela começa exclusiva); `payout = {0.3448275862068966, ok}` (50/145); `margem_bruta = {0.3900709219858156, ok}`; `margem_liquida = {0.10283687943262411, ok}`;
- `payout_por_ano = [{ano: 2024, valor: 0.2153846153846154, status: ok}]`; `proventos_por_ano` = 2021 0.0, 2022 0.0, 2023 0.0, 2024 0.7, 2025 0.5, todos `ok`;
- `ebitda.valor_12m`, `margem`, `setor_margem` e todo o `endividamento` `{null, indisponivel}` (sem EBIT e sem dívida no banco de teste); `caixa_liquido = {null, indisponivel}`;
- `setor_comparacao_fraca = true`; `balanco_referencia = {data_fim_periodo: "2025-06-30", data_entrega: "2025-08-10", status: "ok"}`.

Outros (conferido): ABEV3 `rentabilidade.d1 = {null, indisponivel}` (sem `aj` em t) e `cotacao.fechamento = {10.0, ok}`; JBSS32 (BDR) `volatilidade_20d.posicao_pct = {null, nao_se_aplica}`, `pl = {null, indisponivel}`, `dividend_yield = {null, indisponivel}`.

**Gabarito unitário do P/L com prejuízo** (`fabrica_fundamentos.mundo()`, t = 2026-03-16, conferido): PREJ3 `pl = {valor: -5.0, status: "lucro_negativo", texto: "P/L −5,0 · Empresa com prejuízo nos últimos 12 meses"}`; AAAA3 `pl = {5.75, ok}` e `pvp = {0.7076923076923077, ok}`.

### 4.4 `series_diarias` (chave dos pontos `ticker` + `data`; "quando muda"; formato compacto S20; janela S19)
Um registro por série, **no formato compacto** (só este pacote; os outros seguem com folhas):
```json
{"versao_contrato": "1.0", "gerado_em": "...", "dados_ate": "...",
 "ticker": "TAEE11", "tipo": "acao", "nome": "TAESA", "substituir_serie": true, "inicio_janela": "2025-10-16",
 "datas": ["2025-10-16", "2025-10-17", "2025-10-20", "2025-10-21"],
 "valores": {"fechamento": [10.0, 10.0, null, 10.0], "indice_retorno_total": [100.0, 100.0, null, 100.0], "...": "..."},
 "status": {"fechamento": [{"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}], "...": "..."}}
```
Regras do formato (o validador confere, Fase 4):
- `datas` crescentes, sem repetir, todas ≥ `inicio_janela` e ≤ t; cada lista de `valores` tem o mesmo tamanho de `datas`; só os campos do `tipo` (tabela abaixo), todos presentes;
- `status` só para pontos ≠ `ok`, em trechos contíguos (posições seguidas de `datas`) com o mesmo status, `de`/`ate` inclusivos e iguais a datas de `datas`; trechos do mesmo campo não se sobrepõem; campo sem nenhum ponto ≠ `ok` fica fora de `status` (série toda `ok` → `"status": {}`);
- valor `null` ⇔ coberto por exatamente um trecho; valor numérico coberto por trecho só com `lucro_negativo` (P/L); nunca 0 no lugar de vazio;
- `n_empresas` (só setor) nunca tem status (0 quando nenhuma empresa entrou no dia);
- números sem arredondar (arredondar a 6 casas daria 1,7 MB em vez de 2,6 MB, mas quebraria a igualdade exata "nível(d)/nível(d−n) − 1 = rentabilidade do resumo");
- envio incremental: mesmo formato, só com as datas novas (e os trechos dessas datas).

**Janela (S19):** `inicio_janela` = o 1º dos **últimos 252 pregões até t (inclusive)** do calendário (com menos de 252 pregões, o 1º do calendário). Série que começa depois tem `datas` começando no seu 1º ponto, mas o mesmo `inicio_janela`. A base 100 **não** é rebaseada: a âncora continua sendo o 1º ponto da série no histórico inteiro, então o 1º valor enviado em geral é ≠ 100; a interface divide pelo 1º valor do recorte (8.3). **Por que não rebasear:** se a base fosse o início da janela, todos os 252 pontos mudariam todo dia (a janela anda 1 pregão), o que obrigaria reenvio da série inteira diariamente e três versões (1m, 6m, 1a). Os cálculos (12 meses, beta, base 100, P/L por trechos) continuam usando o histórico inteiro; só o pacote é cortado.

| `tipo` | séries | campos de `valores` |
|---|---|---|
| `acao` | cada ticker do painel (BDR inclusive) | `fechamento`, `indice_retorno_total`, `volume`, `pl`, `pvp`, `dividend_yield` |
| `etf` | `IVVB11` (de `v1-precos`) | `fechamento`, `indice_retorno_total`, `volume` |
| `indice` | `IBOV` (de `v1-precos`), `IDIV`, `SMLL`, `IFIX` (de `v1-indices`, em pontos) | `fechamento` (pontos), `indice_retorno_total` |
| `taxa` | `CDI`, `IPCA` | `indice_retorno_total` |
| `setor` | `SETOR:<nome do setor>` (seção 7) | `indice_retorno_total`, `n_empresas` |

`nome`: ação → `empresa` do cadastro (ou o ticker); IBOV → "Ibovespa"; setor → nome do setor; os outros → o próprio código. Série sem nenhum ponto na janela (ex.: IVVB11 no banco de teste) não é emitida e vira aviso no `execucao`. Dias antes do início da série não entram em `datas`; buraco depois do início entra como `null` com trecho `indisponivel`.

Cálculos (todos em `processamento/fatos/`, Fases 1 e 2, sobre o histórico inteiro):
- `indice_retorno_total` da ação/ETF/IBOV = `aj(d)/aj(início) × 100`, início = 1º pregão com `aj` no histórico inteiro;
- IDIV/SMLL/IFIX = `valor(d)/valor(início) × 100`;
- CDI = `100 × C(d)/C(início)`, com `C(x)` = produto de (1 + taxa/100) das datas do CDI **< x** (a taxa do dia d rende de d a d+1, como em `rentabilidade_cdi`); ponto `ok` só se todo pregão p com início ≤ p < d tem taxa; senão `indisponivel`;
- IPCA = `100 × Π (1 + ipca_m/100)` dos meses m em (K(início), K(d)], com K(d) = último mês conhecido antes do mês de d (`indices._k`); mês faltando no intervalo → `indisponivel`;
- assim, para qualquer recorte, `nível(d)/nível(d−n) − 1` = a rentabilidade da janela no `resumo_acao`/`mercado_dia` (teste de consistência na Fase 1);
- `pl`, `pvp`, `dividend_yield` diários: `fatos/multiplos.py` (Fase 2), só nos pregões da janela, mesmas regras e status de `calcular_fundamentos_no_dia`.

**Tamanho** (medido pelo coordenador com dados sintéticos: 112 séries = 85 ações × 6 campos, IVVB11, 4 índices, 2 taxas, 20 setores; floats sem arredondar; JSON compacto):

| pontos por série | folha | **compacto** |
|---|---|---|
| 253 (janela adotada) | 8,0 MB | **2,6 MB** |
| 555 (histórico atual inteiro) | 17,6 MB | 5,2 MB |
| 1260 (5 anos) | 40,3 MB | 13,2 MB |
| envio diário de 1 ponto | 54 KB | 47 KB |

**Gabarito E2E** (banco de teste: só 4 pregões, então `inicio_janela = "2025-10-16"` em todas as séries; `datas` = 2025-10-16, 10-17, 10-20, 10-21 salvo indicação; conferido onde indicado):
- PETR4 (`acao`): `fechamento [10.0, 10.0, 10.0, 10.0]`, `indice_retorno_total [100.0]*4`, `volume [1000.0]*4`, `pl [6.896551724137931]*4`, `pvp [0.8333333333333334]*4`, `dividend_yield [0.12, 0.12, 0.12, 0.05]` (JCP 0,70 de 2024-10-21 + 0,50 de 2025-08-20, ÷ 10; em 10-21 o JCP sai da janela de 12 meses; conferido em 10-21, os outros pela mesma regra); `status {}`.
- TAEE11: `fechamento [10.0, 10.0, null, 10.0]`, `indice_retorno_total [100.0, 100.0, null, 100.0]`, `volume [1000.0, 1000.0, null, 1000.0]`, `pl [6.896551724137931, 6.896551724137931, null, 6.896551724137931]`, `pvp [0.8333333333333334, 0.8333333333333334, null, 0.8333333333333334]`, `dividend_yield [0.09, 0.09, null, 0.09]` (provento da unit 0,90 de 2025-05-15); `status` com o trecho `{"de": "2025-10-20", "ate": "2025-10-20", "status": "indisponivel"}` em **cada um** dos 6 campos (sem preço da unit no dia, valor de mercado e yield também ficam `indisponivel`).
- NOVA3: `datas ["2025-10-20", "2025-10-21"]`, `inicio_janela "2025-10-16"`. ITUB4: sem preço nenhum, série não emitida.
- IBOV (`indice`): `fechamento [10.0]*4`, `indice_retorno_total [100.0]*4`, `status {}`.
- IDIV: `datas ["2025-10-20", "2025-10-21"]`, `fechamento [1000.0, 1010.0]`, `indice_retorno_total [100.0, 101.0]`.
- CDI (`taxa`): `indice_retorno_total [100.0, 100.05, 100.09002, 100.14006501]` (tolerância 1e-9), `status {}`.
- IPCA: `indice_retorno_total [100.0]*4` (K = 2025-09 em todo o mês de outubro).
- `SETOR:Petroleo`: `indice_retorno_total [100.0]*4`, `n_empresas [0, 1, 1, 1]`; `SETOR:Energia`: `[100.0, 100.0, null, null]`, `n_empresas [0, 1, 0, 0]`, `status {"indice_retorno_total": [{"de": "2025-10-20", "ate": "2025-10-21", "status": "indisponivel"}]}` (um trecho só: os dois nulos são contíguos); `SETOR:Varejo` (NOVA3) `datas ["2025-10-20", "2025-10-21"]`, `[100.0, 100.0]`; `SETOR:Bebidas` (ABEV3) `[100.0, 100.0, 100.0, null]` com trecho em 10-21; não há `SETOR:Alimentos` (só BDR) nem `SETOR:Financeiro` (ITUB4 sem preço).
- Primeira geração sem estado: todas as séries com `substituir_serie: true`.

**Gabarito do corte de 253 (Fase 6b, fábrica pequena):** `cal = pregoes_uteis(260)` (2025-01-02 a 2025-12-31), IBOV constante e AAAA3 com `aj = serie_por_retornos(10.0, [0.001] * 259)`, t = 2025-12-31: a série tem **253** datas, `inicio_janela = "2025-01-13"` (8º pregão), 1º valor de `indice_retorno_total` = `aj(8º)/aj(1º) × 100 = 100.70210350350199` (≠ 100), último = `129.54661428719584` (approx 1e-9); `nível(t)/nível(inicio_janela) − 1` = `rentabilidade.a1` do resumo (252 variações). No dia seguinte (estado = série com t = 2025-12-30, janela 2025-01-10 a 2025-12-30; atual com t = 2025-12-31): vai só o ponto de 2025-12-31, `substituir_serie: false`, `inicio_janela` avança de "2025-01-10" para "2025-01-13", e o ponto de 2025-01-10 que saiu **não** conta como sumido.

### 4.5 `fundamentos_trimestrais` (chave `ticker` + `data_fim_periodo`; "quando muda")
Um registro por linha de `tabela_trimestral(t, ...)`, **só os 8 trimestres mais recentes de cada ticker** (por `data_fim_periodo`, entregues até t; S19); o 9º que sai do corte vai em `removidos` (regra normal da 2.4). Campos: Meta + `ticker`, `data_fim_periodo` (data), `data_entrega` (data) e uma folha F para cada um dos 14 `CAMPOS_TRIMESTRAIS` (`receita_trimestre`, `receita_12m`, `lucro_liquido_trimestre`, `lucro_liquido_12m`, `margem_bruta`, `margem_liquida`, `roe`, `ebitda_trimestre`, `ebitda_12m`, `margem_ebitda`, `divida_liquida`, `dl_pl`, `dl_ebitda`, `payout_12m`).

**Gabarito E2E (conferido):** 16 registros (ITUB4, PETR3, PETR4 e TAEE11 × trimestres 2024-09-30, 2024-12-31, 2025-03-31, 2025-06-30; menos de 8 por ticker, o corte não tira nada); nenhum com `data_entrega` > 2025-10-21 (o trimestre 2025-09-30, entregue em 2025-11-10, não aparece). PETR4 2025-06-30: `data_entrega "2025-08-10"`, `receita_trimestre {360.0, ok}`, `receita_12m {1410.0, ok}`, `lucro_liquido_trimestre {40.0, ok}`, `lucro_liquido_12m {145.0, ok}`, `margem_bruta {0.3900709219858156, ok}`, `margem_liquida {0.10283687943262411, ok}`, `roe {0.12083333333333333, ok}`, `payout_12m {0.19310344827586207, ok}`; `ebitda_trimestre`, `ebitda_12m`, `margem_ebitda`, `divida_liquida`, `dl_pl`, `dl_ebitda` `{null, indisponivel}`. PETR4 2024-09-30: `receita_trimestre {300.0, ok}`, `lucro_liquido_12m {null, historico_insuficiente}`.

### 4.6 `proventos` (chave `ticker` + `tipo` + `data_com`; "quando muda")
Um registro por linha de `lista_proventos(ligar_proventos(proventos, cadastro, mudancas), tickers_do_painel, t)` **com `data_com` no ano de t ou nos 4 anteriores** (mesma regra de anos de `anos_historico_proventos` = 5 que o `proventos_por_ano` já usa; S19); o que sai do corte vai em `removidos`. Campos: Meta + `ticker`, `tipo` ("DIVIDENDO" ou "JCP"), `data_com` (data), `data_pagamento` Fd (null → `indisponivel`), `valor_por_acao` F.

**Gabarito E2E (conferido):** 4 registros, nesta ordem: PETR3 DIVIDENDO 2025-08-20 (`valor_por_acao {0.5, ok}`, `data_pagamento {null, indisponivel}`); PETR4 JCP 2024-10-21 (0.7; pagamento nulo); PETR4 DIVIDENDO 2025-08-20 (0.5; `data_pagamento {"2025-09-10", ok}`); TAEE11 DIVIDENDO 2025-05-15 (0.9). Ficam de fora: PETR4 2025-11-20 (data_com > t), TAEE3/TAEE4 (classes fora do painel), ELET6 (vira AXIA6, fora do cadastro). O corte de 5 anos (2021 a 2025) não tira nada aqui: o JCP de 2024-10-21 continua dentro.

### 4.7 `noticias_dia` (chave `data_referencia` + `ticker`; todo dia)
Um registro por ticker do painel. Janela do painel = **a mesma do modelo**: de 08:00:01 de t até 08:00 de D (S9). Notícia da empresa vale para todas as suas ações; mesmo `id` conta uma vez por empresa; repetidas por título (E10) saem.

| campo | tipo |
|---|---|
| Meta, `data_referencia` (= t), `ticker` | — |
| `janela_inicio`, `janela_fim` | data-hora (`corte_manha(t) + 1 s`, `corte_manha(D)`) |
| `resumo` | `{quantidade, positivas, neutras, negativas, tom_medio}`, cada um F |
| `itens` | lista, na ordem do `destaque`, de `{id, titulo, fonte, link, publicado_em (data-hora ou null), data_publicacao (data), precisao_hora ("hora", "sem_hora" ou "meia_noite_pacifico"), janela ("pregao", "noite" ou "sem_horario"), rotulo ("positivo", "neutro", "negativo" ou null), prob_positivo, prob_neutro, prob_negativo (número ou null), destaque (inteiro 1..n), status ("ok" ou "indisponivel" se faltar probabilidade)}` |

Regras (Fase 3): `janela = "sem_horario"` quando a notícia não tem hora real (`sem_hora` ou `meia_noite_pacifico`); senão `"pregao"` (pregão de t ou pré-abertura de t, E2) ou `"noite"`. `rotulo` = maior das 3 probabilidades; empate que envolve o neutro, ou empate entre positivo e negativo, vira `"neutro"`. `destaque`: primeiro as notícias em que a empresa é protagonista (`papel = "protagonista"` em qualquer linha daquele `id` da empresa), depois |positivo − negativo| decrescente, depois a mais recente (`momento` decrescente), depois `id` crescente. `resumo`: com quantidade 0 → `quantidade/positivas/neutras/negativas = {0, ok}` e `tom_medio = {null, nao_se_aplica}`; t antes do início da cobertura (menor `data_publicacao` lida) → as 5 folhas `{null, indisponivel}` e `itens = []`. `tom_medio` = média de `prob_positivo − prob_negativo`.

**Gabarito E2E (pela regra de janelas):** PETR4 e PETR3: 1 item, `n000008` (2025-10-21 09:00, pré-abertura de t → `janela "pregao"`, `rotulo "neutro"` com 0,2/0,5/0,3, `destaque 1`); `resumo` = quantidade 1, positivas 0, neutras 1, negativas 0, `tom_medio {-0.1, ok}` (0,2 − 0,3; approx 1e-12). `n000004` (10-20 08:00:00) e `n000005` (10-20 08:00:01) não entram (são de t−1). TAEE11: `itens = []`, quantidade `{0, ok}`, `tom_medio {null, nao_se_aplica}` (as duas da CVM são de 10-17 e 10-20).
O gabarito unitário completo (7 notícias, destaque e empates) está na Fase 3.

### 4.8 `experimento_top` (chave `data_referencia`; todo dia, antes das 10h)
| campo | tipo | regra |
|---|---|---|
| Meta, `data_referencia` (= D), `pregao_previsto` (= D), `pregao_base` (= t) | — | — |
| `valido_para_historico` | bool | S10: true só se (modelo não provisório) **e** (`gerado_em` ≤ 10:00 de D) **e** (`treino.teste_final.fim` preenchido **e** D > fim) |
| `modelo_versao` | texto `"xgb-AAAA-MM"` (sem o dia) | nome do arquivo usado |
| `modelo_provisorio` | bool | `metadados["provisorio"]` |
| `universo` | texto | `universo` das linhas de t no dataset ("composicao_atual") |
| `n_candidatas` | inteiro | linhas de t no dataset |
| `selo` | `"em_avaliacao"` | fixo |
| `titulo` | `"5 ações com maior chance de superar o Ibovespa (experimento)"` | fixo |
| `aviso_fixo` | `"Não constitui recomendação de investimento."` | `relatorio.RODAPE` |
| `avisos` | lista de textos | ver abaixo |
| `ranking` | lista de até 5 `{posicao, ticker, chance, motivos, noticias_usadas}` | `previsao.top_do_dia` + textos |
| `chance` | `{valor: número ou null, media: 0.5, exibir: bool, status: "ok" ou "calibracao_nao_conferida"}` | `previsao.chance` (F16) |
| `motivos` | lista (3) de `{fator, valor (bruto ou null), efeito, texto}`; efeito ∈ "ajudou", "atrapalhou", "neutro" | `previsao.motivos` + `textos.texto_motivo` |
| `noticias_usadas` | lista de `id` (ordem do destaque) | as notícias da janela da empresa (as mesmas do `noticias_dia`) |

`avisos` possíveis (texto exato):
- "Modelo provisório: treinado com cerca de 1 ano de dados, só para testar a rotina."
- "Antes da entrada em produção: este top 5 é um teste de funcionamento e não entra no histórico do experimento."
- "Dia do período de teste final: não entra no histórico do experimento."
- "Gerado depois das 10h: não entra no histórico do experimento."
- "Modelo de AAAA-MM (o do mês de D ainda não foi treinado)."
- "Só N ações no universo do dia (menos de 5)."

A contribuição numérica (log-odds), as sombras (modelo 1 e regra da volatilidade) e as probabilidades **não** vão no pacote: ficam só no registro interno (seção 8).

**Antes da produção (hoje), para D = 2026-10-23:** `modelo_versao "xgb-2026-06"`, `modelo_provisorio true`, `valido_para_historico false`, `chance = {valor: null, media: 0.5, exibir: false, status: "calibracao_nao_conferida"}` em todas as posições; avisos = provisório, antes da produção e "Modelo de 2026-06 (o do mês de D ainda não foi treinado).".

**Gabarito E2E (estrutura; o ranking depende do modelo de teste):** com um modelo pequeno salvo em `tmp/modelos/xgb-2025-10.json` (e `xgb-m1-2025-10.json`): `n_candidatas = 4` (NOVA3, PETR3, PETR4, TAEE11; ABEV3 e ITUB4 sem preço em t, JBSS32 é BDR, CRFB3 excluída; conferido em `montar_universo`); `ranking` com 4 itens, `posicao` 1..4, tickers distintos e dentro desse conjunto, cada um com 3 motivos de `texto` não vazio e `chance.valor is None`; `avisos` contém o de provisório, o de antes da produção e "Só 4 ações no universo do dia (menos de 5)."; `valido_para_historico false`; `noticias_usadas` de PETR4 (se estiver no ranking) = `["n000008"]`, de TAEE11 = `[]`.

### 4.9 `experimento_historico` (chave `data_referencia`; todo dia)
| campo | tipo |
|---|---|
| Meta, `data_referencia` (dia fechado, ou D se nenhum) | — |
| `dia` | null ou `{data_referencia, pregao_base, ranking (5 tickers), resultado, acertos_dia (0..5), acertos_top3 (0..3), resultado_incompleto (bool), taxa_acumulada (F)}`; `resultado` = lista de `{ticker, retorno: F, retorno_ibov: F, superou: bool ou null}` |
| `resumo` | `{periodo_inicio: data ou null, periodo_fim: data ou null, n_dias: inteiro, taxa_acerto: F, acaso_media: F, acaso_faixa: [min, max] ou null, universo: texto, nota: texto}` |

Regras (S12): só entram dias com `valido_para_historico = true` **e** pregão previsto > `treino.teste_final.fim` (com `fim` vazio, nenhum). `superou` = retorno da ação > retorno do IBOV (empate = false; sem preço = null, com `retorno {null, indisponivel}` e `resultado_incompleto: true`). `acertos_dia` conta só os `true`; a taxa do dia é `acertos_dia/5`; `taxa_acerto` = soma dos acertos ÷ (5 × n_dias). Faixa do acaso = `avaliacao.faixa_do_acaso` sobre as candidatas (com alvo) de todos os dias válidos, k = 5, `acaso_sorteios` e `semente` do bloco `treino`, `com_retorno=False`; `acaso_faixa = [p2_5, p97_5]`.
`nota`: universo `composicao_atual` → "Histórico calculado com as ações que compõem o Ibovespa atualmente."; sem dias, acrescenta (separado por um espaço) "O histórico começa na entrada em produção (teste ao vivo). Antes disso, os top 5 são testes de funcionamento e não entram aqui."

**Antes da produção (hoje):** `data_referencia = D`, `dia = null`, `resumo = {periodo_inicio: null, periodo_fim: null, n_dias: 0, taxa_acerto: {null, indisponivel}, acaso_media: {null, indisponivel}, acaso_faixa: null, universo: "composicao_atual", nota: <as duas frases>}`.

**Gabarito com produção simulada** (Fase 7; `fim = 2026-11-02`; 6 candidatas por dia; k = 5; `acaso_sorteios = 10000`; `semente = 20261023`; conferido em `faixa_do_acaso`):

| dia (pregão previsto) | ranking | alvo de AAAA3, BBBB3, CCCC3, DDDD3, EEEE3, FFFF3 | acertos_dia | acertos_top3 |
|---|---|---|---|---|
| 2026-11-03 | AAAA3, BBBB3, CCCC3, DDDD3, EEEE3 | 1, 0, 1, 1, 0, 1 | 3 | 2 |
| 2026-11-04 | BBBB3, CCCC3, DDDD3, EEEE3, FFFF3 | 1, 1, 0, 0, 1, 0 | 2 | 1 |
| 2026-11-05 | FFFF3, EEEE3, DDDD3, CCCC3, BBBB3 | 0, 1, 1, 1, 1, 1 | 5 | 3 |

Também existem, e **não** podem entrar: 2026-10-30 com `valido_para_historico: true` (≤ fim) e 2026-11-06 com `false`.
Esperado no pacote do dia 2026-11-05: `n_dias = 3`, `periodo_inicio "2026-11-03"`, `periodo_fim "2026-11-05"`, `taxa_acerto {0.6666666666666666, ok}` (10/15), `acaso_media {0.6666666666666667, ok}` (approx 1e-12), `acaso_faixa = [0.6, 0.8]` (approx 1e-12; o p97,5 sai 0.7999999999999999), `dia.acertos_dia = 5`, `dia.acertos_top3 = 3`, `dia.taxa_acumulada {0.6666666666666666, ok}`.

### 4.10 `execucao` (chave `data_referencia` + `rodada`; início e fim de cada rodada)
| campo | tipo |
|---|---|
| Meta, `data_referencia` (= D), `rodada` (inteiro: 1, ou a do `execucao.json` já existente na pasta + 1) | — |
| `inicio` | data-hora |
| `fim` | data-hora ou null (null só com `em_andamento`) |
| `status` | "em_andamento", "ok", "parcial" ou "falhou" |
| `coleta_status` | objeto; nesta etapa `{consultado: false, nota: "gatilho da coleta não consultado (etapa 8)"}`; a etapa 8 passa o que leu do painel |
| `pacotes_enviados` | lista de `{pacote, arquivo, registros (inteiro), removidos (inteiro)}`, na ordem da 2.5 |
| `avisos` | lista de textos (do experimento, séries sem dados, falhas de pacote e os da coleta vindos da etapa 8) |

`status`: "ok" = os 9 pacotes gravados; "parcial" = algum falhou ou foi pulado (ex.: sem arquivo de modelo → sem `experimento_top`); "falhou" = nenhum gravado. **Gabarito E2E:** `status "ok"`, `rodada 1`, 9 itens em `pacotes_enviados` na ordem da 2.5; uma segunda chamada na mesma pasta dá `rodada 2`.

---

## 5. Validar "contra o contrato" (item B; decisão S13)

**Recomendação: validador próprio** em `processamento/saida/contrato.py`, com um dicionário de esquema por pacote (Fase 4). Motivos: sem dependência nova; mensagens em português com o caminho do campo (`resumo_acao[PETR4].pl.setor.valor: ...`); confere as regras que são nossas e que o JSON Schema só faz com muito `if/then` (folha com `ok` ⇒ valor; valor nulo ⇒ status ≠ ok; "0 no lugar de vazio" com status ≠ ok é erro; P/L com `lucro_negativo` pode ter valor). Alternativa: `jsonschema>=4.23` (nova dependência no `requirements.txt`), com a vantagem de entregar à equipe da API arquivos de esquema padrão; dá para gerar esses arquivos depois a partir do nosso dicionário, se pedirem.

O validador roda **antes** de gravar cada arquivo; pacote reprovado não é gravado, vira aviso e a rodada fica `parcial`.

Regras gerais (todo registro): `versao_contrato == "1.0"`; `gerado_em` e `dados_ate` no formato `AAAA-MM-DDTHH:MM:SS-03:00` (aceitar também `-02:00`); datas `AAAA-MM-DD` válidas; campo desconhecido = erro (pega erro de digitação); campo obrigatório ausente = erro; número = `int` ou `float` finito e não `bool`; envelope com `pacote` conhecido, `chave` igual à do pacote e `registros` lista.

---

## 6. Point-in-time (item C)

Duas camadas, cada uma com teste:
1. **Leitura cortada** (`saida/insumos.py`): preços com `ate = D − 1 dia`; t = último pregão lido; balanços (`data_entrega`), proventos (`data_com`) e índices (`data`) com `ate = t`; notícias com `ate = corte_manha(D)`; `acoes_emitidas` sem corte (a regra D4 já filtra pelo balanço entregue).
2. **Funções puras com t explícito:** os montadores recebem t e não olham `cal[-1]`. Teste: chamar os montadores com as tabelas **sem corte** e `t` dado dá o mesmo resultado que com as tabelas cortadas.

**Teste de veneno (Fase 8, E2E):** gerar D = 2025-10-22 duas vezes, com `agora` fixo e pastas separadas: (a) banco de teste original; (b) banco com, a mais: preços de 2025-10-22 para todos os tickers com fechamento 99 e volume 1; balanço PETR (CNPJ 33000167000101) ITR 2025-07-01 a 2025-09-30 com `data_entrega 2025-10-22` e lucro 999999; provento PETR4 DIVIDENDO `data_com 2025-10-22` valor 50; notícias PETR4 em `2025-10-22T08:00:01-03:00` e `2025-10-22T09:00:00-03:00` com prob_positivo 0,99; CDI de 2025-10-22. Esperado: todos os arquivos, menos `execucao.json`, **byte a byte iguais**.

**Testes explícitos (valores esperados):**
- `resumo_acao` PETR4: `balanco_referencia.data_entrega = "2025-08-10"` (o ITR de 2025-09-30, entregue em 2025-11-10, e o envenenado de 2025-10-22 não aparecem); `pl = 6.896551724137931`, não 999999;
- `fundamentos_trimestrais`: nenhum `data_entrega` > "2025-10-21";
- `series_diarias`: a maior data em `datas` de toda série é "2025-10-21";
- `proventos`: nenhum `data_com` > "2025-10-21";
- `noticias_dia`: PETR4 só com `n000008` (as de 08:00:01 e 09:00 de D ficam fora); uma notícia em `2025-10-22T07:59:59-03:00` **entra** (noite de t) e uma em `08:00:00` também entra (borda inclusiva); `08:00:01` não;
- a linha `0.0006` do CDI é a de 10-21 (`cdi_data = "2025-10-21"`), não a de 10-22.

---

## 7. Série do setor em base 100 (item D; decisão S5)

Regra (Fase 1, `fatos/series.py::indice_setor`):
- membros do setor s = **pares do painel** (`pares_do_painel`: ON, PN e UNIT, sem excluídos; **BDR fora**) com `setor == s`, **incluindo a própria ação** (8.3); ticker sem setor não entra;
- retorno diário de cada ação = `retornos_diarios(g_aj)` (exige preço em t **e** no pregão anterior; sem preencher lacunas);
- **média por empresa** (como D10): primeiro a média das ações da mesma empresa com retorno no dia, depois a média simples entre empresas; ticker sem CNPJ conta como empresa própria;
- início = 1º pregão em que algum membro tem `aj` → nível 100, `n_empresas = 0`;
- dia com pelo menos uma empresa com retorno: `nível = último nível válido × (1 + média)`, status `ok`; dia sem nenhuma: ponto `{null, indisponivel}`, `n_empresas = 0`, e a cadeia continua do último nível válido;
- ação que entra (IPO, ou primeiro preço no histórico) passa a contar a partir do seu 2º dia com preço; ação que sai (sem preço) para de contar. Não há rebalanceamento: cada dia é a média dos que têm retorno;
- setor só com BDR, ou sem nenhum preço: série não emitida.

**Exemplo (gabarito da Fase 1).** Setor "S" com 3 empresas: AAAA3 (empresa 1), BBBB3 (empresa 2), CCCC3 e CCCC4 (empresa 3; CCCC4 começa no dia 3). Pregões d0..d4 = 2025-01-02, 01-03, 01-06, 01-07, 01-08 (`pregoes_uteis(5)`).

| dia | AAAA3 aj | BBBB3 aj | CCCC3 aj | CCCC4 aj | ret AAAA3 | ret BBBB3 | ret empresa 3 | média (por empresa) | n_empresas | nível |
|---|---|---|---|---|---|---|---|---|---|---|
| d0 | 10.00 | 20.00 | 50.00 | — | — | — | — | — | 0 | **100.000000** |
| d1 | 10.50 | 19.00 | 51.00 | — | +0.05 | −0.05 | +0.02 | +0.0066666667 | 3 | **100.666667** |
| d2 | 10.29 | **sem preço** | 51.51 | — | −0.02 | — | +0.01 | −0.005 | 2 | **100.163333** |
| d3 | 10.4958 | 19.00 | 50.9949 | 30.00 | +0.02 | — (d2 sem preço) | −0.01 (só CCCC3) | +0.005 | 2 | **100.664150** |
| d4 | 10.600758 | 19.38 | 52.524747 | 30.90 | +0.01 | +0.02 | (+0.03 +0.03)/2 = +0.03 | +0.02 | 3 | **102.677433** |

Valores exatos para o teste (approx abs 1e-9): 100.0, 100.66666666666666, 100.16333333333331, 100.66414999999996, 102.67743299999997. Se fosse média **por ação** (alternativa), d4 daria (0,01 + 0,02 + 0,03 + 0,03)/4 = 0,0225 e nível 102.929093375: o teste confirma que **não** é isso.

**Segundo exemplo (setor de uma ação só, com buraco):** ZZZZ3 aj = 10, 11, sem preço, 12.1, 12.1 → níveis 100.0, 110.0 (approx), null `indisponivel`, null `indisponivel`, 110.0 (approx; d4 tem retorno 0). `n_empresas` = 0, 1, 0, 0, 1. **Limitação registrada:** o movimento de 11 para 12,1 (+10%) se perde porque nenhum dia tem os dois preços seguidos; a série da própria ação (base 100) vai a 121. Com várias empresas no setor o efeito é pequeno; a alternativa "retorno as-of" (S5) evitaria isso, mas joga o retorno de vários dias num dia só.

---

## 8. O experimento antes da produção (itens 4 e E; decisões S10, S11, S12)

**O que existe hoje:** só o modelo provisório `modelos/xgb-2026-06.json` (modelo 3, colunas essenciais, treinado de 2025-08-01 a 2026-06-19; `provisorio: true`; calibração **não** aprovada: ECE 0,0204 > 0,02) e o `xgb-m1-2026-06.json`. Não existe teste ao vivo: `treino.teste_final.fim` está vazio.

**`experimento_top` hoje:** é gerado (serve para testar a rotina, 7.7), com o modelo do mês de D ou, se não houver, o mais recente anterior (`xgb-2026-06` + aviso). Sai com `valido_para_historico: false`, `modelo_provisorio: true`, chance `null`/`calibracao_nao_conferida`, e os avisos de provisório e de antes da produção. Gerar o top 5 de um dia dentro do período do teste final **não** é avaliar o teste final (não há resultado); por isso é permitido. O que não pode é calcular acerto desses dias.

**Registro do top 5 (S11, aprovada com ajuste)** em `registros/experimento/` (pasta do `parametros.yaml`, fora de `saida/`). **Uso único só em produção:** com `treino.teste_final.fim` preenchido, o registro é gravado uma vez e nunca sobrescrito; com `fim` vazio (hoje, testes de funcionamento), cada rodada **gera de novo e sobrescreve** o `D.top.json`.
- `AAAA-MM-DD.top.json` (D): `{"pacote": <o experimento_top completo>, "interno": {"modelo_arquivo", "modelo_m1_arquivo", "sombra_modelo_1": [5 tickers] ou null, "sombra_volatilidade": [5 tickers], "candidatos": [tickers de t], "probabilidades": {ticker: prob}}}`. Com `fim` preenchido: gravado na **primeira** geração do dia e nunca sobrescrito (`open(..., "x")`); uma rodada seguinte do mesmo D **reconstrói o pacote a partir do registro** (não recalcula): "gravado no momento da geração, nunca recalculado" (7.6). Com `fim` vazio: cada rodada recalcula o top 5 e sobrescreve o arquivo (escrita atômica).
- `AAAA-MM-DD.resultado.json` (D' fechado): `{"data_referencia", "pregao_base", "fechado_em", "ranking", "resultado", "acertos_dia", "acertos_top3", "resultado_incompleto", "alvos_candidatos": {ticker: 1.0, 0.0 ou null}, "acertos_sombra_modelo_1", "acertos_sombra_volatilidade"}`. Só existe em produção (com `fim` vazio nenhum dia é fechado) e é de uso único. As sombras ficam aqui para a comparação ao vivo da 7.7 (não vão para a tela).

**Fechar um dia** (`fechar_dia`): na rodada de D, o dia fechado é D' = t (o top 5 gerado na manhã de t). Só fecha se existir `t.top.json` com `valido_para_historico: true`, **e** `teste_final.fim` preenchido, **e** t > fim, **e** o pregão base do registro for o pregão imediatamente anterior a t no calendário (senão, D' não foi pregão: aviso "pregão previsto <D'> não houve; dia descartado"). Retornos com `alvo.alvos(precos, [pregao_base, t], candidatos)` na linha do pregão base.

**`experimento_historico` hoje (recomendação S12): vazio.** `n_dias = 0`, `dia = null`, nota explicando que o histórico começa na produção. Alternativa: mostrar o desenvolvimento (walk-forward, `saida/experimento/treino/dev-*/diario.csv`) marcado como `origem: "desenvolvimento"` e fora do resumo; não recomendo, porque esses números são otimistas (blocos e grade escolhidos nas mesmas dobras, F7) e a tela misturaria isso com o teste ao vivo.

**Testes que garantem que o teste final não aparece (Fase 7 e Fase 8):**
1. `pode_fechar(registro, fim=None)` = False para qualquer data; `pode_fechar` com `fim = 2026-11-02`: D' = 2026-11-02 → False, 2026-11-03 → True; registro com `valido_para_historico: false` → False.
2. `montar_historico` com `fim = None` e registros fechados "envenenados" (datas 2026-06-23, 2026-07-01, 2026-10-22, todos com `valido_para_historico: true`) → `n_dias = 0`, `dia is None`, e o JSON do pacote não contém nenhuma das strings `"2026-06-23"`, `"2026-07-01"`, `"2026-10-22"`.
3. Com `fim = 2026-11-02`, um registro fechado de 2026-10-30 com `valido: true` não entra (gabarito da 4.9).
4. E2E: com `fim = None`, gerar D = 2025-10-22 e depois D = 2025-10-23 (o segundo com preços de 10-22 acrescentados) na mesma pasta de registros: existem `2025-10-22.top.json` e `2025-10-23.top.json`, **nenhum** `*.resultado.json`, e `experimento_historico.n_dias = 0` nos dois dias.
5. `valido_para_historico` (função pura): (a) provisório, 09:00, fim None → false, razões [provisório, antes da produção]; (b) não provisório, `2026-11-03T09:59:59`, fim 2026-11-02, D 2026-11-03 → true; (c) idem às 10:00:00 → true (limite inclusivo); às 10:00:01 → false (razão "depois das 10h"); (d) não provisório, fim 2026-11-02, D 2026-11-02 → false (razão "dia do teste final").
6. Registro do top (S11): (a) `fim` vazio, duas rodadas no mesmo D com dados diferentes (ex.: probabilidades trocadas) → o 2º registro **substitui** o 1º (arquivo com o 2º pacote; o pacote da 2ª rodada é o recalculado); (b) `fim = 2026-11-02` e D = 2026-11-03, duas rodadas → a 2ª **reconstrói do 1º** (pacote igual ao da 1ª rodada; o arquivo fica com os mesmos bytes).

**Gabarito de `fechar_dia`** (preços à mão; cal = [2026-10-30, 2026-11-03]; registro D' = 2026-11-03, pregão base 2026-10-30, ranking AAAA3..EEEE3, candidatos AAAA3..FFFF3, válido, fim = 2026-11-02):

| ticker | aj 10-30 | aj 11-03 | retorno | superou |
|---|---|---|---|---|
| IBOV | 100 | 101 | 0.010000000000000009 | — |
| AAAA3 | 10 | 10.2 | ≈ 0.02 | true |
| BBBB3 | 10 | 10.05 | ≈ 0.005 | false |
| CCCC3 | 100 | 101 | igual ao IBOV | false (empate) |
| DDDD3 | 10 | 10.3 | ≈ 0.03 | true |
| EEEE3 | 10 | sem preço | `{null, indisponivel}` | null |
| FFFF3 | 10 | 9.9 | ≈ −0.01 | (fora do ranking) |

Esperado: `acertos_dia = 2`, `acertos_top3 = 1`, `resultado_incompleto = true`, `alvos_candidatos = {AAAA3: 1.0, BBBB3: 0.0, CCCC3: 0.0, DDDD3: 1.0, EEEE3: None, FFFF3: 0.0}`. Com cal = [2026-10-30, 2026-11-04] e D' = 2026-11-03 → `None` (dia descartado).

---

## 9. Onde aparece cada um dos 23 itens da planilha (item F)

| # | Item da planilha | Pacote | Campos |
|---|---|---|---|
| 1 | Top 5 do experimento | `experimento_top` (+ `resumo_acao`, `noticias_dia` no "detalhes") | `ranking[].posicao/ticker/chance/motivos/noticias_usadas`, `titulo`, `selo`, `aviso_fixo`, `avisos` |
| 2 | Histórico do experimento | `experimento_historico` | `resumo.taxa_acerto`, `resumo.acaso_media`, `resumo.acaso_faixa`, `nota`; linha do acerto acumulado: `dia.taxa_acumulada` (vazio até a produção) |
| 3 | Volume total | `resumo_acao` (+ `series_diarias`) | `volume.total`; `valores.volume` |
| 4 | Volume em relação ao normal | `resumo_acao` + `series_diarias` | `volume.relativo` (+ texto), `volume.mediana_20`, `volume.posicao_pct`; barras dos 20 pregões: `valores.volume` |
| 5 | Grau de endividamento | `resumo_acao` + `fundamentos_trimestrais` | `endividamento.*` (inclui `aviso` e `caixa_liquido`); linhas por trimestre: `dl_pl`, `dl_ebitda`, `divida_liquida` |
| 6 | Comparação com o Ibovespa | `resumo_acao` + `series_diarias` | `rentabilidade.{d1,m1,m6,a1}` e `rentabilidade.ibov.*`; gráfico: `indice_retorno_total` da ação e do `IBOV` |
| 7 | Comparação com o setor | `resumo_acao` + `series_diarias` + `acoes` | `rentabilidade.setor.*`, `setor_comparacao_fraca`, `acoes.setor`; gráfico: `SETOR:<nome>` |
| 8 | Volatilidade | `resumo_acao` | `volatilidade_20d` (valor, `posicao_pct`, texto) |
| 9 | Beta | `resumo_acao` | `beta` (valor, status, texto) |
| 10 | Tom das notícias do dia | `noticias_dia` | `resumo` + `itens` (rótulo, link, `destaque`) |
| 11 | P/L | `resumo_acao` (+ `series_diarias`) | `pl` (+ `setor`, texto do prejuízo); `valores.pl` (janela de 253 pregões) |
| 12 | P/VP | `resumo_acao` (+ `series_diarias`) | `pvp` (+ `setor`); `valores.pvp` |
| 13 | Dividend yield | `resumo_acao` + `proventos` (+ `series_diarias`) | `dividend_yield` (+ `setor`); barras: `proventos` e `proventos_por_ano`; `valores.dividend_yield` |
| 14 | ROE | `resumo_acao` + `fundamentos_trimestrais` | `roe` (+ `setor`); `roe` por trimestre |
| 15 | Cotação | `resumo_acao` + `series_diarias` | `cotacao.*`; gráfico: `valores.fechamento` |
| 16 | Variação do preço | `resumo_acao` + `series_diarias` | `variacao_preco.*`; `valores.fechamento` |
| 17 | Margem bruta | `resumo_acao` + `fundamentos_trimestrais` | `margem_bruta` (+ `setor`); por trimestre |
| 18 | Margem líquida | `resumo_acao` + `fundamentos_trimestrais` | `margem_liquida` (+ `setor`); por trimestre |
| 19 | EBITDA | `resumo_acao` + `fundamentos_trimestrais` | `ebitda.*` (com `rotulo`); barras: `ebitda_trimestre` (+ `ebitda_12m`, `margem_ebitda`) |
| 20 | Payout | `resumo_acao` (+ `fundamentos_trimestrais`) | `payout` (+ `setor`); barras: `payout_por_ano`; `payout_12m` por trimestre |
| 21 | Histórico de dividendos | `proventos` + `resumo_acao` | tabela: `data_com`, `data_pagamento`, `tipo`, `valor_por_acao`; barras: `proventos_por_ano` |
| 22 | Comparação com índices | `series_diarias` + **`mercado_dia`** | gráfico: `CDI`, `IPCA`, `IDIV`, `SMLL`, `IFIX`, `IVVB11`; % por período: **`mercado_dia.indices`** |
| 23 | Rentabilidade | `resumo_acao` + `series_diarias` | `rentabilidade.{d1,m1,m6,a1}`; gráfico: `indice_retorno_total` |

**Conferência com a 8.4: um buraco real.** A planilha pede "% de cada um [índice] no período, com seletor de 1 mês, 6 meses e 1 ano" e a 8.4 manda esses % para o `resumo_acao`, mas a 8.3 não lista o campo em nenhum pacote. O cálculo já existe (`calcular_indices`); a proposta (S7) é publicá-lo uma vez por dia em `mercado_dia.indices` (é igual para todas as ações). Os outros 22 itens já tinham origem na 8.3; os acréscimos (`proventos_por_ano`, `taxa_acumulada`, `aviso_fixo`, textos) só deixam pronto o que a interface teria de calcular.

---

## 10. Gráficos que a interface pode montar e custo do histórico de múltiplos (item G)

Períodos conferidos em `docs/diagnostico_banco.md` (22/10/2026) e no `.meta.json` do modelo. **A interface mostra só 1m, 6m e 1a (S19):** as séries levam os últimos **253 pregões até t** (hoje, de ~meados de out/2025 a 21/10/2026), os trimestres os 8 mais recentes e os proventos 5 anos. As contas usam o histórico inteiro; com o histórico de 5 anos, só a âncora da base 100 muda (reenvio inteiro uma vez, seção 2.4).

| Gráfico | Pacote | Campos | Período disponível hoje |
|---|---|---|---|
| Preço (1m, 6m, 1a) | `series_diarias` (acao) | `valores.fechamento` | 253 pregões (o banco tem ~555, desde 2024-07-29) |
| Rentabilidade (evolução) | `series_diarias` | `valores.indice_retorno_total` | 253 pregões (base 100 ancorada no 1º dia do histórico) |
| Ação × Ibovespa | `series_diarias` | ação + `IBOV` | 253 pregões |
| Ação × setor | `series_diarias` | ação + `SETOR:<nome>` | 253 pregões |
| Ação × índices | `series_diarias` | `CDI`, `IPCA`, `IDIV`, `SMLL`, `IFIX`, `IVVB11` | CDI, IPCA e IVVB11: os 253 pregões; **IDIV, SMLL e IFIX só 20 e 21/10/2026 (2 pontos)** |
| Volume (20 pregões + mediana) | `series_diarias` + `resumo_acao` | `valores.volume`, `volume.mediana_20` | 253 pregões |
| P/L no tempo | `series_diarias` | `valores.pl` | dos 253, `ok` só depois da DFP 2025 (4 trimestres; entregue ~mar/2026): ~150; antes, `historico_insuficiente` |
| P/VP no tempo | `series_diarias` | `valores.pvp` | os 253 (desde ~mai/2025 há ITR entregue) |
| Yield no tempo | `series_diarias` | `valores.dividend_yield` | os 253 (proventos desde 1995) |
| Margens, ROE, EBITDA 12m, DL/EBITDA por trimestre | `fundamentos_trimestrais` | campos de 12 meses | até 8 trimestres; hoje há 6 (2025-03-31 a 2026-06-30) e os de 12 meses só de 2025-12-31 em diante (**3 pontos**) |
| Trimestre isolado, EBITDA do trimestre, DL/PL | `fundamentos_trimestrais` | `*_trimestre`, `dl_pl` | 6 trimestres (máximo 8) |
| Payout por ano | `resumo_acao` | `payout_por_ano` | **1 barra** (DFP 2025; a DFP 2024 não está no banco) |
| Proventos por ano / tabela | `proventos`, `resumo_acao` | `proventos_por_ano`, lista | 5 anos (ano de t + 4 anteriores) |
| Acerto acumulado do experimento | `experimento_historico` | `dia.taxa_acumulada` | **nenhum dia** até a produção; depois, sem corte |
| Tom das notícias | `noticias_dia` | `resumo` | só o dia (tom ao longo do tempo exigiria guardar os pacotes diários) |

### Custo de P/L, P/VP e yield diários (decisão S8, aprovada: por trechos)

Com a janela de 253 (S19), P/L, P/VP e yield só precisam ser calculados nos 253 pregões da janela (o histórico inteiro continua sendo lido para as fotos do balanço e os 12 meses de proventos).

| | Ingênuo (função da etapa 4 em cada pregão) | **Por trechos (aprovado)** | Só fim de mês | Só daqui para frente |
|---|---|---|---|---|
| Como | `calcular_fundamentos_no_dia` em cada data | foto do balanço e ações emitidas só nas datas de entrega de cada empresa (entre duas entregas elas não mudam); valor de mercado e P/L/P/VP por dia com `valor_de_mercado` e `indicadores_empresa`; yield por somas acumuladas | ingênuo nas ~12 datas de fim de mês | 1 cálculo por dia, guardado em estado |
| Tempo (85 ações, 253 pregões da janela) | ~6,4 min por rodada (1,53 s por data, medido com 81 empresas, 96 tickers e 8.000 proventos sintéticos) | **~8 s** (estimado do protótipo medido: 10,4 s para 346 pregões, 0 divergência contra a função da etapa 4); com 5 anos de histórico continua ~8 s, porque só a janela é calculada | ~18 s | ~1,5 s por dia |
| Código novo | ~15 linhas | ~110 linhas | ~25 linhas | ~60 linhas + estado |
| Testes | 2 | ~9 (com teste-oráculo e o da janela) | 3 | ~5 |
| Problema | apertado para o prazo das 9h45 | — | só pontos mensais | sem histórico na estreia; estado pode se perder |

Nenhuma leitura extra do banco (usa as tabelas já lidas). As funções da etapa 4 calculam uma data por vez e refazem `ligar_proventos` e os filtros de balanço em cada chamada; por isso o ingênuo é lento. O "por trechos" reusa `foto_balanco`, `acoes_na_data`, `valor_de_mercado` e `indicadores_empresa`, então o resultado é o mesmo por construção (o teste-oráculo confere).

Tamanho do `series_diarias`: ver a tabela da 4.4 (compacto, 253 pontos: **2,6 MB** no primeiro envio; ~47 KB por dia depois, salvo reenvios).

---

## 11. Ponto de entrada, ordem e `execucao` (item H; decisão S17)

```
python -m processamento.saida --data AAAA-MM-DD [--pasta saida] [--pasta-modelos modelos]
                              [--pasta-registros registros/experimento] [--sem-estado]
```
- `--data` (obrigatório) = D. Sem gatilho: lê o que houver na coleta (é a etapa 8 que espera a entrega).
- Saída em `saida/D/` (fora do git: `.gitignore` já tem `saida/`); estado em `saida/estado/`; registros do experimento em `registros/experimento/` (S11).
- `--sem-estado`: não lê nem grava o estado (manda tudo; para testes e para regerar dias antigos sem bagunçar o estado).
- Códigos de saída: 0 = `ok` ou `parcial` (os avisos são impressos); 2 = configuração do banco incompleta; 3 = conexão falhou ou sessão não está READ ONLY (nada gravado); 4 = `falhou` (nenhum pacote gravado). Mesmo padrão de `dataset.main` (`dataset.py:253-289`, sem mostrar a mensagem original da conexão).

**Como a etapa 8 vai chamar:** como função, não como subprocesso:
```python
from processamento.saida.gerar import gerar
pasta = gerar(d, ler=leitor, agora=None, coleta_status={...lido do painel...}, avisos_coleta=["dados de hoje incompletos"], usar_estado=True)
```
A etapa 8 decide **quando** chamar (gatilho, prazo 9h45, rodadas), preenche `coleta_status`/`avisos_coleta`, fixa `treino.teste_final.fim` e, no dia da produção, liga o histórico. O `gerar` já calcula `valido_para_historico` com o limite das 10h do `parametros.yaml`.

**Fluxo de `gerar(d, ...)`** (Fase 8): 1) `execucao` em andamento; 2) `ler_insumos`; 3) grades da Fase 1 em t (`calcular_precos`, `calcular_indices`, `calcular_fundamentos_no_dia`, `payout_por_ano`, `balanco_referencia_no_dia`, `tabela_trimestral`, `ligar_proventos`); 4) para cada pacote, na ordem da 2.5: montar → validar → comparar com o estado (se for "quando muda") → gravar → atualizar o estado; erro num pacote vira aviso e a rodada segue (`parcial`); 5) `experimento_historico`: fecha t se puder (seção 8) e monta; 6) `experimento_top`: com `treino.teste_final.fim` preenchido e `D.top.json` já existente, reconstrói dele (S11); senão (inclusive sempre que `fim` está vazio) monta o dataset ao vivo (`montar_dataset(..., proximo_ao_vivo=d)`), escolhe o modelo, gera, grava o registro e o pacote; 7) `execucao` final.

---

## 12. Fases para o implementador (item I)

| Fase | Arquivos | Depende de | Pode rodar junto com |
|---|---|---|---|
| 0 | `processamento/config/parametros.yaml` (bloco `saida`), `processamento/calendario.py:21`, `processamento/saida/__init__.py`, `processamento/saida/parametros.py`, `tests/test_saida_parametros.py` | — | 1, 2, 3, 4, 5 |
| 1 | `processamento/fatos/series.py`, `tests/test_fatos_series.py` | — | 0, 2, 3, 4, 5 |
| 2 | `processamento/fatos/multiplos.py`, `tests/test_fatos_multiplos.py` | — | 0, 1, 3, 4, 5 |
| 3 | `processamento/fatos/noticias.py`, `tests/test_fatos_noticias.py` | — | 0, 1, 2, 4, 5 |
| 4 | `processamento/saida/contrato.py`, `processamento/saida/insumos.py`, `tests/fabrica_saida.py`, `tests/test_saida_contrato.py` | — | 0, 1, 2, 3, 5 |
| 5 | `processamento/saida/textos.py`, `tests/test_saida_textos.py` | — | 0, 1, 2, 3, 4 |
| 6a | `processamento/saida/pacotes_fatos.py`, `tests/test_saida_pacotes_fatos.py` | 4, 5 | 6b, 6c, 7 |
| 6b | `processamento/saida/pacote_series.py`, `tests/test_saida_series.py` | 1, 2, 4 | 6a, 6c, 7 |
| 6c | `processamento/saida/pacote_noticias.py`, `tests/test_saida_noticias.py` | 3, 4 | 6a, 6b, 7 |
| 7 | `processamento/saida/pacotes_experimento.py`, `tests/test_saida_experimento.py` | 0, 3, 4, 5 | 6a, 6b, 6c |
| 8 | `processamento/saida/gerar.py`, `processamento/saida/__main__.py`, `tests/test_saida_gerar.py`, `tests/test_vazamento_saida.py` | todas | — |

`processamento/saida/__init__.py` pode ser criado pela Fase 0 ou pela 4 (quem chegar primeiro), sempre com o mesmo conteúdo: `"""Pacotes JSON da seção 8 da especificação (etapa 7)."""`. Ao fim de cada fase, rodar a verificação da fase e depois `.venv\Scripts\python.exe -m pytest -q` (o projeto inteiro).

### Fase 0: parâmetros da saída

**`processamento/calendario.py:21`:** acrescentar `"saida"` a `_CHAVES_DE_TOPO`.

**`processamento/config/parametros.yaml`**, no fim:
```yaml
# Saída: pacotes JSON da seção 8 (plano da etapa 7). HORAS E CAMINHOS ENTRE ASPAS.
saida:
  limite_valido_historico: "10:00"          # top 5 gerado depois disso: valido_para_historico = false (seção 4)
  pasta: "saida"                            # saida/AAAA-MM-DD/ (fora do git)
  pasta_estado: "saida/estado"              # último envio dos pacotes "quando muda"
  pasta_registros: "registros/experimento"  # top 5 do dia e resultado (uso único; S11)
  tom_neutro: 0.05                          # |tom| até isto = "tom neutro" nos textos
```

**`processamento/saida/parametros.py`** (mesmo estilo de `experimento/parametros.py`):
```python
class ErroParametrosSaida(Exception): ...
@dataclass(frozen=True)
class ParametrosSaida:
    limite_valido_historico: time
    pasta: Path; pasta_estado: Path; pasta_registros: Path   # relativos a fontes.RAIZ
    tom_neutro: float
def carregar_parametros_saida(caminho: str | None = None) -> ParametrosSaida
```
Valida: conjunto exato de chaves (falta ou sobra → erro `saida.<chave> ...`); `limite_valido_historico` texto "HH:MM" (sem aspas o YAML lê número → erro com "aspas"); pastas texto não vazio; `tom_neutro` número ≥ 0 e < 1, sem aceitar bool.

**Testes (`tests/test_saida_parametros.py`, com yaml temporário montado a partir do real):**
- o yaml real carrega: `limite_valido_historico == time(10, 0)`, `pasta == fontes.RAIZ / "saida"`, `pasta_registros == fontes.RAIZ / "registros" / "experimento"`, `tom_neutro == 0.05`;
- `limite_valido_historico: 10:00` sem aspas → erro com "aspas"; `"25:00"` → erro;
- chave a mais → erro; chave faltando → erro;
- `tom_neutro: true` → erro; `tom_neutro: -0.1` → erro;
- `calendario.carregar_parametros(caminho)` aceita o bloco `saida`.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_parametros.py tests/test_calendario.py tests/test_treino_parametros.py tests/test_exp_parametros.py`

---

### Fase 1: `processamento/fatos/series.py` (séries base 100; funções puras)

```python
ANTES_DO_INICIO = "antes_do_inicio"   # status interno: o ponto não é emitido (nunca vai para o JSON)
def indice_base_100(g: pd.DataFrame) -> Grade
    # por coluna: base = 1º valor não nulo; valor = g/base*100; status ok onde há valor;
    # NaN depois do início -> indisponivel; antes do início -> ANTES_DO_INICIO
def indice_pontos(indices: pd.DataFrame, cal: list, nomes=("IDIV", "SMLL", "IFIX")) -> tuple[Grade, pd.DataFrame]
    # (indice_base_100(grade_de_indices(...)), grade_de_indices(...) = os pontos)
def indice_cdi(indices: pd.DataFrame, cal: list) -> Grade            # coluna "CDI"
def indice_ipca(indices: pd.DataFrame, cal: list) -> Grade           # coluna "IPCA"
def indice_setor(g_aj: pd.DataFrame, cadastro: pd.DataFrame, pares: list[str]) -> tuple[Grade, pd.DataFrame]
    # colunas "SETOR:<nome>"; 2º item = n_empresas (inteiros) com as mesmas colunas
```
Regras: seção 4.4 (CDI e IPCA) e seção 7 (setor). Reusar `indices._serie_cdi`, `indices._meses_ipca`, `indices._k`, `indices.grade_de_indices`, `precos.retornos_diarios`, `precos.mapas_cadastro`, `precos.Grade`, `precos.indice_pregoes`. `indice_cdi`: início = 1º pregão ≥ 1ª data do CDI; `C(x)` = produto de (1 + taxa) das datas < x (a mesma conta da função interna `C` de `rentabilidade_cdi`, `indices.py:67`).

**Casos de teste (`tests/test_fatos_series.py`; tolerância 1e-9 salvo indicação):**
1. `indice_base_100` com coluna X = [NaN, 10, 11, NaN, 12.1] e Y = [NaN]*5: X → valores [NaN, 100, 110, NaN, 121], status [antes_do_inicio, ok, ok, indisponivel, ok]; Y → todos antes_do_inicio.
2. `indice_pontos` com cal = 2025-10-16, 10-17, 10-20, 10-21 e IDIV (10-20: 1000, 10-21: 1010): IDIV = [antes, antes, 100.0, 101.0]; pontos [NaN, NaN, 1000, 1010]; SMLL e IFIX todos antes_do_inicio.
3. `indice_cdi`, mesmo cal, CDI = 0.05, 0.04, 0.05, 0.06 (%, datas 10-16 a 10-21): [100.0, 100.05, 100.09002, 100.14006501], todos ok. Consistência: `nivel[10-21]/nivel[10-20] − 1` == `rentabilidade_cdi(indices, cal, 1).valor` em 10-21 (= 0.0005; approx 1e-12).
4. CDI sem a taxa de 10-17: [100.0 ok, 100.05 ok, NaN indisponivel, NaN indisponivel].
5. CDI começando em 10-17 com cal desde 10-16: 10-16 antes_do_inicio, 10-17 = 100.0.
6. `indice_ipca`, cal = 2025-08-29, 09-01, 09-30, 10-01, 11-03; meses 2025-07 = 0.26, 08 = 0.50, 09 = 1.00 (datas no dia 1): [100.0, 100.5, 100.5, 101.505, 101.505]; consistência com `rentabilidade_ipca(indices, cal, 4)` em 11-03 = 0.01505 (approx 1e-12).
7. IPCA sem o mês 08: [100.0, 100.0, 100.0, NaN indisponivel, NaN indisponivel] (K(09-01) = 07; K(10-01) = 09 exige 08).
8. IPCA só com o mês 2025-08 e cal começando em 2025-08-29: 08-29 antes_do_inicio (K = None); 09-01 = 100.0.
9. `indice_setor`, exemplo da seção 7 (cadastro com `cadastro_de`: AAAA3 cnpj "1", BBBB3 "2", CCCC3 e CCCC4 "3", todos setor "S", tipo ON/ON/ON/PN): `SETOR:S` = 100.0, 100.66666666666666, 100.16333333333331, 100.66414999999996, 102.67743299999997; `n_empresas` = 0, 3, 2, 2, 3; e **não** 102.929093375 no d4.
10. Setor de uma ação com buraco (ZZZZ3, setor "Z", aj 10, 11, NaN, 12.1, 12.1): [100.0, 110.0, NaN indisponivel, NaN indisponivel, 110.0]; `n_empresas` 0, 1, 0, 0, 1.
11. BDR no setor não entra: acrescentar ao caso 9 um `BDRX34` (BDR, setor "S", aj 1, 100, 1, 100, 1) e passar `pares` sem ele (como `pares_do_painel` faz): mesmo resultado do caso 9. Setor só com BDR: sem coluna.
12. Ticker sem setor (`setor` None) não gera coluna nem entra em nenhum setor.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_fatos_series.py tests/test_fatos_indices.py`

---

### Fase 2: `processamento/fatos/multiplos.py` (P/L, P/VP e yield diários; função pura)

```python
def multiplos_diarios(dados: DadosFundamentos, cal: list, exclusoes: Exclusoes,
                      params: ParametrosFundamentos, desde: date | None = None) -> dict[str, Grade]
    # chaves "pl", "pvp", "dividend_yield"; Grade pregão × tickers_do_painel (mesma ordem)
    # desde (S19): só calcula os pregões de cal com data >= desde (gerar passa o inicio_janela: os 253 da janela);
    # as tabelas continuam inteiras (fotos do balanço e janela de 12 meses usam o histórico todo). idx = só esses pregões
    # valor mantido quando status ∈ {ok, lucro_negativo} (regra de _grade_do_dia, fundamentos.py:398); senão NaN
```
Algoritmo (validado num protótipo com 0 divergência; copiar):
```python
tick = tickers_do_painel(dados.cadastro, exclusoes); idx = indice_pregoes(cal)
gf = grade_de_precos(dados.precos, cal, "fechamento", tick)
_, cnpj_de = mapas_cadastro(dados.cadastro); tipo_de = dict(zip(dados.cadastro["ticker"], dados.cadastro["tipo_acao"]))
lig = ligar_proventos(dados.proventos, dados.cadastro, dados.mudancas)
ini = idx - pd.DateOffset(months=params.meses_janela)          # janela (ini, t], igual a dividend_yield
# yield, por ticker: BDR -> (NaN, indisponivel) em tudo; senão
l = _do_ticker(lig, k).sort_values("data_com"); dc = l["data_com"].to_numpy()
cs = np.concatenate([[0.0], np.cumsum(l["valor_por_acao"].to_numpy(float))])
soma = cs[np.searchsorted(dc, idx.to_numpy(), side="right")] - cs[np.searchsorted(dc, ini.to_numpy(), side="right")]
# yield = soma / fech (ok) onde fech é número > 0; senão (NaN, indisponivel)
# P/L e P/VP, por CNPJ (só os CNPJs dos tickers do painel):
cad_c = dados.cadastro[dados.cadastro["cnpj"] == cnpj]
entregas = sorted(set(dados.balancos.loc[dados.balancos["cnpj"] == cnpj, "data_entrega"].dropna()))
cache = {}
for i, ts in enumerate(idx):
    s = bisect.bisect_right(entregas, ts) - 1                   # trecho entre duas entregas
    if s not in cache:                                          # calcula no 1º pregão do trecho
        cache[s] = (foto_balanco(dados.balancos, cnpj, ts, exclusoes),
                    acoes_na_data(acoes_disponiveis(dados.acoes_emitidas, dados.balancos, ts), cnpj, ts))
    foto, qtd = cache[s]
    vm = valor_de_mercado(cnpj, gf.iloc[i].to_dict(), cad_c, tick, qtd)
    ind = indicadores_empresa(foto, vm, (math.nan, INDISPONIVEL), False)   # pago e financeiro não afetam P/L e P/VP
    # pl = ind["pl.valor"], pvp = ind["pvp.valor"]
# ticker sem CNPJ: (NaN, indisponivel) nos dois
```
Por que os trechos são exatos: `foto_balanco` e `acoes_na_data(acoes_disponiveis(...))` só dependem dos balanços com `data_entrega ≤ t` daquele CNPJ (regra D4), que só mudam numa data de entrega.

**Casos de teste (`tests/test_fatos_multiplos.py`, com `fabrica_fundamentos.mundo()`, `EXCL` e `carregar_parametros_fundamentos()`):**
1. **Oráculo:** para cada t em [2025-01-02, 2025-03-19, 2025-03-20, 2025-03-31, 2025-04-15, 2025-05-09, 2025-05-12, 2025-08-08, 2025-08-11, 2025-11-07, 2025-11-10, 2026-03-13, 2026-03-16, 2026-04-10, 2026-04-15, 2026-04-30] e os 12 tickers: `status` igual ao de `calcular_fundamentos_no_dia(t, cal, dados, EXCL, params, "empresa")[ind]` e valor igual (approx rel 1e-12; NaN = NaN), com ind = `pl.valor`, `pvp.valor`, `dividend_yield.valor`.
2. **Valores explícitos (conferido):**

| t | AAAA3 pl | AAAA3 pvp | AAAA3 yield | PREJ3 pl | UUUU11 pl | DDDD3 pl |
|---|---|---|---|---|---|---|
| 2025-03-31 | null `historico_insuficiente` | null `indisponivel` | 0.139 | — | — | — |
| 2025-05-12 | null `historico_insuficiente` | 0.782608695652174 | 0.129 | — | — | — |
| 2025-08-11 | 6.206896551724138 (900/145) | 0.75 | 0.129 | null `indisponivel` | 20.689655172413794 | null `historico_insuficiente` |
| 2025-11-10 | 5.625 (900/160) | 0.72 | 0.149 | null `indisponivel` | 18.75 | null `historico_insuficiente` |
| 2026-03-16 | 5.75 (920/160) | 0.7076923076923077 | 0.149 | −5.0 `lucro_negativo` | 18.75 | 20.0 |
| 2026-04-15 | 5.75 | 0.7076923076923077 | 0.07 | −5.0 `lucro_negativo` | 18.75 | 20.0 |

Também: BDRX32 yield `indisponivel` em todas as datas; SEMB3 e NOBA3 pl `indisponivel` em todas; AAAA3 yield 2025-04-15 = 0.169 e 2026-04-10 = 0.1 (o provento de 2025-04-15 sai da janela em 2026-04-15, que é exclusiva no início).
3. **Point-in-time (conferido):** acrescentar ao mundo `balanco_de(CNPJ["A"], [_a("ITR", "2026-01-01", "2026-03-31", "2026-04-20", 400, 160, 1000, 9999)])`: em 2026-04-17 AAAA3 continua `pl 5.75`, `pvp 0.7076923076923077`; em 2026-04-20 vira `pl 0.8177777777777778` (920/1125) e `pvp 0.09200920092009202` (920/9999).
4. **Formato:** as 3 grades têm índice = pregões de `cal`, colunas = `tickers_do_painel` (12, em ordem alfabética), e `valor` é NaN exatamente onde `status ∉ {ok, lucro_negativo}`.
5. **Janela (S19):** `multiplos_diarios(..., desde=date(2026, 3, 13))` devolve grades só com os pregões ≥ 2026-03-13 (índice começando em 2026-03-13), com valores e status iguais às linhas correspondentes do cálculo sem `desde` (ex.: AAAA3 `pl` 5.625 em 2026-03-13 e 5.75 em 2026-03-16; yield 0.149 em 2026-03-13, que depende de proventos de antes do `desde`).

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_fatos_multiplos.py tests/test_fund_no_dia.py`

---

### Fase 3: `processamento/fatos/noticias.py` (notícias da janela do painel; funções puras)

```python
COLUNAS_JANELA = ["id", "empresa", "titulo", "fonte", "link", "publicado_em", "data_publicacao", "precisao_hora",
                  "janela", "momento", "prob_positivo", "prob_neutro", "prob_negativo", "score", "rotulo", "protagonista"]
def rotulo(pp, pneu, pneg) -> str | None
    # None se alguma for NaN; senão a maior; empate que envolve o neutro, ou positivo == negativo no máximo -> "neutro"
def noticias_da_janela(noticias, cal, t, proximo, cnpj_de, mudancas, params: ParametrosExperimento) -> pd.DataFrame
def destaque(df_empresa: pd.DataFrame) -> pd.DataFrame       # ordenado + coluna "destaque" 1..n
def resumo_noticias(df_empresa: pd.DataFrame, coberta: bool) -> dict[str, tuple[float, str]]
    # chaves quantidade, positivas, neutras, negativas, tom_medio -> (valor, status)
def ids_da_empresa(janela: pd.DataFrame, empresa: str) -> list[str]
    # ids da empresa na ordem do destaque (usado no noticias_dia e no experimento_top)
```
`noticias_da_janela` (entrada = DataFrame de `fontes.ler_noticias`, já com `momento_ref` e `precisao_hora`):
1. `e = experimento.noticias.ligar_empresa(noticias, cnpj_de, mudancas)`;
2. `protagonista` = `e.groupby(["empresa", "id"])["papel"].transform(lambda s: s.eq("protagonista").any())` (antes de tirar as duplicadas);
3. `u, _ = experimento.noticias.deduplicar(e, params)` (E10);
4. `momento = u["data_hora_publicacao"].fillna(u["momento_ref"])`; `c = calendario.classificar_noticias(u.assign(data_hora_publicacao=momento), cal, proximo_ao_vivo=proximo)`;
5. ficam as linhas com `janela` ∈ {noite, pregao, pre_abertura} **e** `pregao_ref == t`;
6. `janela` do painel: `"sem_horario"` se a `data_hora_publicacao` original é NaT; senão `"pregao"` (pregao ou pre_abertura) ou `"noite"`;
7. `publicado_em` = `data_hora_publicacao` original; `score = prob_positivo − prob_negativo`; `rotulo`.
`destaque`: ordenar por `protagonista` desc, `|score|` desc, `momento` desc, `id` asc. `resumo_noticias`: regras da seção 4.7 (contagem por `rotulo`; `tom_medio` = média de `score`).

**Caso de teste (prototipado com as funções existentes; conferido):** cal = 2026-10-19, 10-20, 10-21, 10-22; t = 2026-10-22; proximo = 2026-10-23; `cnpj_de = {"AAAA3": "1", "AAAA4": "1", "BBBB3": "2", "CCCC3": "3"}`; notícias com `fabrica_experimento.noticias_de` (tupla: id, ticker, instante SP, dia, pp, pneg, origem, papel, tipo; `prob_neutro = 1 − pp − pneg`), acrescentando `fonte = "Fonte X"` e `link = "https://exemplo.invalid/<id>"`, e trocando o `titulo` de n10 por `"titulo n05"`:

| id | ticker | publicação (SP) | pp | pneg | origem / papel | esperado |
|---|---|---|---|---|---|---|
| n01 | AAAA4 | 2026-10-22 08:00:00 | 0.5 | 0.1 | google_news | fora (noite de 10-21) |
| n02 | AAAA4 e AAAA3 (mesmo id) | 2026-10-22 08:00:01 | 0.70 | 0.10 | google_news | entra uma vez; `janela "pregao"` (pré-abertura); positivo; score 0.6 |
| n03 | AAAA3 | 2026-10-22 14:30:00 | 0.05 | 0.85 | google_news / **protagonista** | `pregao`; negativo; −0.8 |
| n04 | AAAA4 | 2026-10-22 17:00:00 | 0.30 | 0.30 | google_news | `pregao` (fechamento exato); neutro; 0.0 |
| n05 | AAAA3 | 2026-10-22 19:42:00 | 0.60 | 0.20 | google_news | `noite`; positivo; 0.4 |
| n06 | AAAA3 | 2026-10-22 04:00:00 (= 00:00 em Los Angeles) | 0.10 | 0.10 | google_news | só data → `sem_horario`, `precisao_hora "meia_noite_pacifico"`, `publicado_em` NaT; neutro; 0.0 |
| n07 | AAAA3 | sem hora, dia 2026-10-22 | 0.20 | 0.30 | cvm_ipe | `sem_horario`, `precisao_hora "sem_hora"`; neutro; −0.1 |
| n08 | AAAA4 | 2026-10-23 07:59:59 | 0.15 | 0.70 | google_news | `noite`; negativo; −0.55 |
| n09 | AAAA4 | 2026-10-23 08:00:01 | 0.5 | 0.1 | google_news | fora (depois do corte) |
| n10 | AAAA4 | 2026-10-22 19:50:00 (título igual ao de n05) | 0.60 | 0.20 | google_news | fora (repetida, E10) |
| n11 | BBBB3 | 2026-10-22 11:00:00 | 0.50 | 0.10 | google_news | só na empresa 2; `pregao`; positivo; 0.4 |

Esperado:
- empresa "1" (vale para AAAA3 e AAAA4): `ids_da_empresa(janela, "1")` = **[n03, n02, n08, n05, n07, n06, n04]** (destaque 1..7; n06 antes de n04 porque `momento` 23:59:59 > 17:00);
- `resumo_noticias(empresa 1, True)` = quantidade (7, ok), positivas (2, ok), neutras (3, ok), negativas (2, ok), tom_medio (−0.06428571428571427, ok) (approx 1e-12; = −0,45/7);
- empresa "2": só n11, positivo; empresa "3": nenhuma → `resumo_noticias(vazio, True)` = quantidade/positivas/neutras/negativas (0.0, ok) e tom_medio (NaN, nao_se_aplica);
- `resumo_noticias(qualquer, False)` = as 5 com (NaN, indisponivel);
- `rotulo(0.5, 0.3, 0.2) == "positivo"`; `rotulo(0.2, 0.3, 0.5) == "negativo"`; `rotulo(0.4, 0.2, 0.4) == "neutro"`; `rotulo(0.4, 0.4, 0.2) == "neutro"`; `rotulo(0.3, 0.4, 0.3) == "neutro"`; `rotulo(float("nan"), 0.5, 0.5) is None`;
- point-in-time: com t = 2026-10-21 e proximo = 2026-10-22, só n01 entra para a empresa 1 (noite de 10-21, até 08:00:00 de 10-22, inclusivo).

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_fatos_noticias.py tests/test_exp_noticias.py tests/test_exp_janelas.py`

---

### Fase 4: `processamento/saida/contrato.py`, `processamento/saida/insumos.py` e `tests/fabrica_saida.py`

**`contrato.py`** (sem pandas nos tipos de saída; só Python puro):
```python
VERSAO_CONTRATO = "1.0"
STATUS = ("ok", "nao_se_aplica", "indisponivel", "historico_insuficiente", "lucro_negativo")
STATUS_CHANCE = ("ok", "calibracao_nao_conferida")
PACOTES = ("acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
           "noticias_dia", "experimento_historico", "experimento_top", "execucao")   # ordem da 2.5 (sem a execucao inicial)
CHAVES = {"acoes": ["ticker"], "mercado_dia": ["data_referencia"], "resumo_acao": ["data_referencia", "ticker"],
          "series_diarias": ["ticker", "data"], "fundamentos_trimestrais": ["ticker", "data_fim_periodo"],
          "proventos": ["ticker", "tipo", "data_com"], "noticias_dia": ["data_referencia", "ticker"],
          "experimento_top": ["data_referencia"], "experimento_historico": ["data_referencia"],
          "execucao": ["data_referencia", "rodada"]}
QUANDO_MUDA = ("acoes", "fundamentos_trimestrais", "proventos", "series_diarias")
class ErroContrato(Exception): ...
def numero(x) -> float | int | None        # numpy -> Python; NaN/None -> None; bool -> TypeError
def folha(valor, status: str, **extras) -> dict
    # {"valor": numero(valor), "status": status, **extras}; ErroContrato se status fora de STATUS,
    # se status == "ok" e valor ausente, ou se valor presente com status ∉ {"ok", "lucro_negativo"}
    # (exceção: folha de texto/data/bool: usar folha_texto/folha_bool, mesma regra)
def folha_bool(valor, status) -> dict; def folha_texto(valor: str | None, status) -> dict
def data_txt(x) -> str | None              # date/Timestamp -> "AAAA-MM-DD"; NaT/None -> None
def data_hora_txt(x) -> str | None         # Timestamp com fuso -> isoformat(timespec="seconds") em SP
def meta(gerado_em: str, dados_ate: str) -> dict   # {"versao_contrato": "1.0", "gerado_em", "dados_ate"}
ESQUEMAS: dict[str, dict]                  # um por pacote, exatamente os campos da seção 4
def validar(pacote: str, registro: dict) -> None          # ErroContrato("<pacote>[<chave>].<caminho>: <motivo>")
def lote(pacote: str, registros: list[dict], gerado_em: str, dados_ate: str, removidos: list[dict] = ()) -> dict
def validar_lote(lote: dict) -> None
def gravar_lote(pasta: Path, lote: dict, compacto: bool = False) -> Path
    # valida, json.dumps(ensure_ascii=False, allow_nan=False, indent=None se compacto senão 2), grava <pacote>.json.tmp e os.replace
def comparar_registros(atuais: list[dict], estado: list[dict] | None, chave: list[str]) -> tuple[list[dict], list[dict]]
    # (a_enviar, removidos); estado None -> (atuais, []); ignora gerado_em, dados_ate e versao_contrato na comparação;
    # números com math.isclose(rel_tol=1e-9, abs_tol=1e-12) em qualquer profundidade (dicts e listas)
def ler_estado(pasta: Path | None, pacote: str) -> list[dict] | None ; def gravar_estado(pasta: Path | None, pacote: str, registros: list[dict]) -> None
    # pasta None = sem estado (não lê nem grava)
```
Mini-linguagem dos esquemas (para o Haiku implementar `validar`): `"texto"`, `"texto?"` (ou null), `"data"`, `"data?"`, `"data_hora"`, `"data_hora?"`, `"inteiro"`, `"numero"`, `"numero?"`, `"bool"`, `"bool?"`, `"versao"` (== "1.0"), `"folha"`, `"folha_bool"`, `"folha_texto"`, `"folha_data"`, `"chance"`, `("enum", {...})`, `("lista", tipo)`, `("folha+", {sub-campos})` (folha com campos extras declarados, ex.: `{"setor": "folha", "texto": "texto?"}`), `{...}` (objeto com exatamente esses campos), `("opcional", tipo)` (pode faltar). **`series_diarias` não usa a mini-linguagem de folhas (S20):** `validar("series_diarias", r)` chama `validar_serie(r)`, que confere as regras do formato compacto da 4.4 (campos de topo `ticker`, `tipo`, `nome`, `substituir_serie`, `inicio_janela`, `datas`, `valores`, `status` + meta; `CAMPOS_SERIE[tipo]` = os campos de `valores` da tabela da 4.4).
```python
CAMPOS_SERIE = {"acao": ("fechamento", "indice_retorno_total", "volume", "pl", "pvp", "dividend_yield"),
                "etf": ("fechamento", "indice_retorno_total", "volume"), "indice": ("fechamento", "indice_retorno_total"),
                "taxa": ("indice_retorno_total",), "setor": ("indice_retorno_total", "n_empresas")}
def trechos(datas: list[str], status_por_ponto: list[str]) -> list[dict]
    # agrupa posições seguidas com o mesmo status ≠ "ok" em {"de", "ate", "status"} (usado pela Fase 6b)
def validar_serie(registro: dict) -> None
```

**`insumos.py`:**
```python
@dataclass(frozen=True)
class Insumos:
    d: date; t: date; cal: list[date]
    precos: pd.DataFrame; cadastro: pd.DataFrame; mudancas: dict[str, str]
    balancos: pd.DataFrame; acoes_emitidas: pd.DataFrame; proventos: pd.DataFrame
    indices: pd.DataFrame; noticias: pd.DataFrame; composicao: pd.DataFrame | None; exclusoes: Exclusoes
class ErroSaida(Exception): ...
def ler_insumos(d: date, ler, existe_composicao: bool | None = None) -> Insumos
    # cortes da seção 6 (preços ate d − 1 dia; t = cal[-1]; balanços, proventos (unir_mudancas=False) e índices ate t;
    # notícias ate corte_manha(d); acoes_emitidas sem corte); sem pregão antes de d -> ErroSaida
def instantes(ins: Insumos, agora: datetime) -> tuple[str, str]   # (gerado_em, dados_ate) em texto
```

**`tests/fabrica_saida.py`:** `insumos_de_teste(ler, d=date(2025, 10, 22))` = `ler_insumos(d, ler, existe_composicao=False)`; `AGORA = datetime(2025, 10, 22, 9, 0, tzinfo=SP)`; `GERADO = "2025-10-22T09:00:00-03:00"`; `DADOS_ATE = "2025-10-22T08:00:00-03:00"`; e um exemplo mínimo válido de registro para cada pacote (montado a partir da seção 4), usado nos testes do validador.

**Casos de teste (`tests/test_saida_contrato.py`):**
1. `folha(0.05, "ok") == {"valor": 0.05, "status": "ok"}`; `folha(np.float64(0.1), "ok")["valor"]` é `float`; `folha(float("nan"), "indisponivel") == {"valor": None, "status": "indisponivel"}`.
2. `folha(None, "ok")` → ErroContrato; `folha(0.0, "indisponivel")` → ErroContrato ("valor com status indisponivel": é o "0 no lugar de vazio"); `folha(-5.0, "lucro_negativo")` passa; `folha(1.0, "xpto")` → ErroContrato; `numero(True)` → TypeError.
3. `validar("acoes", exemplo)` passa; sem `gerado_em` → erro com "gerado_em"; `versao_contrato "1.1"` → erro; `gerado_em "2026-10-23T09:00:00"` (sem fuso) → erro; `"2026-10-23T09:00:00-03:00"` passa; data `"23/10/2026"` → erro; campo a mais `"cor"` → erro com "campo desconhecido"; `tipo_acao "ETF"` → erro.
4. `validar("resumo_acao", ...)` com `pl = {"valor": float("nan"), "status": "ok"}` → erro com "NaN"; com `cotacao.fechamento.valor = True` → erro; o exemplo mínimo passa; a mensagem de erro traz o caminho (`resumo_acao[PETR4].pl.valor`).
5. `validar("experimento_top", ...)` com `chance = {"valor": None, "media": 0.5, "exibir": False, "status": "calibracao_nao_conferida"}` passa; com `exibir: True` e `valor: None` → erro; `modelo_versao "xgb-2026-11-01"` → erro (exige `xgb-AAAA-MM`).
6. `validar_lote` com `chave` diferente de `CHAVES[pacote]` → erro; `pacote "xpto"` → erro.
7. `gravar_lote(tmp, lote)` cria `<pacote>.json` (UTF-8, `"ç"` legível, sem `.tmp` sobrando) e relido com `json.loads` dá o mesmo dicionário; registro com NaN escondido num campo `numero` → ValueError (por `allow_nan=False`) e nenhum arquivo criado.
8. `comparar_registros`: estado None → tudo, `removidos = []`; estado igual → `([], [])`; um registro com valor 0.1 → 0.1 + 1e-12 → não vai; 0.1 → 0.2 → vai; registro que sumiu → `removidos == [{"ticker": "BBBB3"}]` (chave de `acoes`); diferença só em `gerado_em` → nada vai.
9. `ler_estado(None, "acoes") is None`; `gravar_estado(tmp, "acoes", regs)` e `ler_estado(tmp, "acoes") == regs`.
10. `ler_insumos(date(2025, 10, 22), banco_teste(), existe_composicao=False)` (conferido): `t == date(2025, 10, 21)`, `cal[-1] == t`, nenhum preço com data > t, `balancos["data_entrega"].max() == 2025-08-10`, `proventos["data_com"].max() == 2025-08-20`, notícias com `momento_ref` ≤ `2025-10-22 08:00 -03:00`. `ler_insumos(date(2025, 10, 16), ...)` → ErroSaida (sem pregão antes).
11. `trechos(["d1","d2","d3","d4","d5"] (datas reais), ["ok", "indisponivel", "indisponivel", "ok", "historico_insuficiente"])` = `[{de: d2, ate: d3, status: indisponivel}, {de: d5, ate: d5, status: historico_insuficiente}]`; tudo `ok` → `[]`; `["indisponivel", "historico_insuficiente"]` → dois trechos (status diferentes não se juntam).
12. `validar_serie` (série `acao` de 4 datas, TAEE11 da 4.4 como exemplo válido, passa) — cada um destes dá ErroContrato: (a) `valores.volume` com 3 itens (tamanho diferente de `datas`); (b) um `null` em `fechamento` sem trecho que o cubra; (c) trecho `indisponivel` cobrindo um valor numérico de `pvp` (só `lucro_negativo` pode cobrir valor); (d) dois trechos de `fechamento` sobrepostos (10-17 a 10-20 e 10-20 a 10-20); (e) trecho com `de` = "2025-10-18" (data fora de `datas`); (f) `datas` fora de ordem ou repetida; (g) data < `inicio_janela`; (h) campo de `valores` que não é do tipo (`pl` numa série `indice`) ou campo faltando; (i) `n_empresas` com status ou com `null`; (j) valor 0 coberto por trecho ≠ ok. Passam: `pl` −5.0 coberto por trecho `lucro_negativo`; `status {}` com todos os valores numéricos.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_contrato.py`

---

### Fase 5: `processamento/saida/textos.py` (textos prontos; funções puras; decisão S14)

```python
def num_br(x: float, casas: int) -> str     # f"{x:.{casas}f}" com vírgula; sinal "−" (U+2212); "−0,0" vira "0,0"
def pct_br(x: float, casas: int = 1) -> str # relatorio.pct(x, casas) com "-" trocado por "−"
def pct_sinal(x: float) -> str              # "+1,2%", "−0,8%", "0,0%"
def texto_volume(relativo) -> str | None    # "3,9× o normal do último mês"
def texto_volatilidade(posicao_pct) -> str | None   # pos >= 0.5: "mais agitada que {pct_br(pos, 0)} das ações"; senão "mais calma que {pct_br(1 − pos, 0)} das ações"
def texto_beta(beta) -> str | None          # "{num_br(b, 2)}: {faixa}"
def texto_pl(valor, status) -> str | None   # só com lucro_negativo
def texto_motivo(fator: str, valor, rank, qtd_noticias, tom_neutro: float) -> str
```
Faixas do beta: b < 0 → "costuma andar na direção contrária do Ibovespa"; 0 ≤ b < 0,8 → "move-se bem menos que o Ibovespa"; 0,8 ≤ b < 0,95 → "move-se um pouco menos que o Ibovespa"; 0,95 ≤ b ≤ 1,05 → "move-se quase igual ao Ibovespa"; 1,05 < b ≤ 1,2 → "move-se um pouco mais que o Ibovespa"; b > 1,2 → "move-se bem mais que o Ibovespa".
`texto_pl`: `lucro_negativo` com valor → `"P/L {num_br(v, 1)} · Empresa com prejuízo nos últimos 12 meses"`; `lucro_negativo` sem valor (lucro zero) → `"Empresa sem lucro nos últimos 12 meses"`; outro status → None. Valor None em qualquer função (menos `texto_motivo`) → None.

`texto_motivo` (v = valor bruto do dataset; r = rank do dia em `preparado_dia`, só nas 13 variáveis de preço; q = `noticias_dia_qtd` bruto da linha; tn = `tom_neutro`; "N notícias" vira "1 notícia" quando q = 1; "tom" = positivo se v > tn, negativo se v < −tn, senão neutro):

| fator | texto |
|---|---|
| `noticias_dia_qtd` | q = 0: "Nenhuma notícia no último pregão e na noite"; q ≥ 1: "{q} notícias no último pregão e na noite" |
| `noticias_dia_tom` | "Notícias do último pregão e da noite com tom {tom} ({q} notícias)" |
| `noticias_dia_extremo` | "Notícia de tom mais forte: {positiva/negativa/neutra} ({num_br(v, 2)})" |
| `mudanca_tom` | v > tn: "Tom das notícias melhor que o habitual da empresa"; v < −tn: "pior que o habitual da empresa"; senão "parecido com o habitual da empresa" (sempre começando com "Tom das notícias ") |
| `tom_setor` | "Notícias das outras empresas do setor com tom {tom}" |
| `tom_mercado` | "Notícias do mercado em geral com tom {tom}" |
| `ret_1d`, `ret_5d`, `ret_20d` | "{Subiu / Caiu} {pct_br(|v|)} {no último pregão / nos últimos 5 pregões / nos últimos 20 pregões}{sufixo}"; v = 0: "Ficou estável {período}"; sufixo: r > 0,5 " (acima da média das ações)", r < 0,5 " (abaixo da média das ações)", senão "" |
| `volatilidade_20d` | "Oscilação diária de {pct_br(v)} nos últimos 20 pregões ({mais agitada / mais calma} que a média)"; r = 0,5 ou None: "(na média das ações)" |
| `beta` | "Beta " + `texto_beta(v)` |
| `volume_relativo` | "Volume de {num_br(v, 1)}× o normal" |
| `salto_abertura` | v > 0: "Abriu em alta de {pct_br(v)} no último pregão"; v < 0: "Abriu em queda de {pct_br(|v|)} no último pregão"; 0: "Abriu estável no último pregão" |
| `dist_max_52s` | v = 0: "Na máxima de 52 semanas"; senão "{pct_br(|v|)} abaixo da máxima de 52 semanas" |
| `dist_min_52s` | v = 0: "Na mínima de 52 semanas"; senão "{pct_br(v)} acima da mínima de 52 semanas" |
| `amplitude` | "Amplitude de {pct_br(v)} entre a máxima e a mínima do último pregão" |
| `ret_vs_setor` | v > 0: "{pct_br(v)} acima do setor no último pregão"; v < 0: "{pct_br(|v|)} abaixo do setor no último pregão"; 0: "Igual ao setor no último pregão" |
| `exposicao_dolar` / `exposicao_petroleo` | "Efeito estimado do {dólar / petróleo} no último pregão: {pct_sinal(v)}" |
| v None (notícias) | "Sem notícias no último pregão e na noite" (`noticias_dia_*`), "Sem base para comparar o tom com o habitual da empresa" (`mudanca_tom`), "Sem notícias das outras empresas do setor" (`tom_setor`), "Sem notícias do mercado" (`tom_mercado`) |
| v None (preço) | "{rótulo}: sem dado", rótulos: Retorno do último pregão, Retorno de 5 pregões, Retorno de 20 pregões, Oscilação diária, Beta, Volume em relação ao normal, Salto da abertura, Distância da máxima de 52 semanas, Distância da mínima de 52 semanas, Amplitude do dia, Retorno em relação ao setor, Efeito do dólar, Efeito do petróleo |
| fator desconhecido | ValueError |

**Casos de teste (`tests/test_saida_textos.py`, valores exatos):**
- `texto_motivo("noticias_dia_tom", 0.42, None, 3, 0.05) == "Notícias do último pregão e da noite com tom positivo (3 notícias)"`;
- `texto_motivo("noticias_dia_tom", -0.05, None, 1, 0.05) == "Notícias do último pregão e da noite com tom neutro (1 notícia)"`;
- `texto_motivo("ret_5d", -0.031, 0.2, None, 0.05) == "Caiu 3,1% nos últimos 5 pregões (abaixo da média das ações)"`;
- `texto_motivo("ret_1d", 0.0123, 0.9, None, 0.05) == "Subiu 1,2% no último pregão (acima da média das ações)"`;
- `texto_motivo("ret_1d", 0.0, 0.5, None, 0.05) == "Ficou estável no último pregão"`;
- `texto_motivo("volatilidade_20d", 0.0182, 0.75, None, 0.05) == "Oscilação diária de 1,8% nos últimos 20 pregões (mais agitada que a média)"`;
- `texto_motivo("beta", 0.91, 0.4, None, 0.05) == "Beta 0,91: move-se um pouco menos que o Ibovespa"`;
- `texto_motivo("volume_relativo", 3.94, 0.9, None, 0.05) == "Volume de 3,9× o normal"`;
- `texto_motivo("salto_abertura", -0.0049, 0.1, None, 0.05) == "Abriu em queda de 0,5% no último pregão"`;
- `texto_motivo("exposicao_dolar", -0.0083, 0.3, None, 0.05) == "Efeito estimado do dólar no último pregão: −0,8%"`;
- `texto_motivo("dist_max_52s", -0.153, 0.2, None, 0.05) == "15,3% abaixo da máxima de 52 semanas"`;
- `texto_motivo("mudanca_tom", 0.3, None, 4, 0.05) == "Tom das notícias melhor que o habitual da empresa"`;
- `texto_motivo("noticias_dia_qtd", 0.0, None, 0.0, 0.05) == "Nenhuma notícia no último pregão e na noite"`;
- `texto_motivo("beta", None, None, None, 0.05) == "Beta: sem dado"`; `texto_motivo("xpto", 1.0, 0.5, None, 0.05)` → ValueError;
- `texto_volume(3.94) == "3,9× o normal do último mês"`; `texto_volatilidade(0.04) == "mais calma que 96% das ações"`; `texto_volatilidade(0.75) == "mais agitada que 75% das ações"`; `texto_volatilidade(0.5) == "mais agitada que 50% das ações"`; `texto_volatilidade(None) is None`;
- `texto_beta(0.91) == "0,91: move-se um pouco menos que o Ibovespa"`; `texto_beta(1.0) == "1,00: move-se quase igual ao Ibovespa"`; `texto_beta(1.05)` "quase igual"; `texto_beta(1.2)` "um pouco mais"; `texto_beta(1.3) == "1,30: move-se bem mais que o Ibovespa"`; `texto_beta(0.79)` "bem menos"; `texto_beta(-0.2) == "−0,20: costuma andar na direção contrária do Ibovespa"`;
- `texto_pl(-5.0, "lucro_negativo") == "P/L −5,0 · Empresa com prejuízo nos últimos 12 meses"`; `texto_pl(None, "lucro_negativo") == "Empresa sem lucro nos últimos 12 meses"`; `texto_pl(6.9, "ok") is None`;
- linguagem: para todos os fatores e valores de um grid pequeno, nenhum texto contém (sem distinguir maiúsculas) "compre", "recomendação", "oportunidade" ou "melhores ações".

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_textos.py tests/test_treino_relatorio.py`

---

### Fase 6a: `processamento/saida/pacotes_fatos.py` (acoes, mercado_dia, resumo_acao, fundamentos_trimestrais, proventos)

```python
@dataclass(frozen=True)
class GradesDoDia:          # calculadas uma vez por rodada (gerar.py) e passadas aos montadores
    precos: dict[str, Grade]          # calcular_precos(ins.precos, ins.cadastro, ins.cal, ins.exclusoes, params_precos)
    indices: dict[str, Grade]         # calcular_indices(ins.precos, ins.indices, ins.cal, params_precos)
    fundamentos: dict[str, Grade]     # calcular_fundamentos_no_dia(ins.t, ins.cal, dados_fund, ins.exclusoes, params_fund, params_precos.setor_excluir)
def dados_fundamentos(ins: Insumos) -> DadosFundamentos
def calcular_grades(ins, params_precos, params_fund) -> GradesDoDia
def montar_acoes(ins, universo_t: pd.DataFrame, gerado_em, dados_ate) -> list[dict]
def montar_mercado_dia(ins, grades, gerado_em, dados_ate) -> list[dict]          # 1 registro
def montar_resumo_acao(ins, grades, params_fund, gerado_em, dados_ate) -> list[dict]
def montar_fundamentos_trimestrais(ins, params_fund, gerado_em, dados_ate) -> list[dict]
def montar_proventos(ins, gerado_em, dados_ate) -> list[dict]
```
- Todos usam `ins.t` (nunca `cal[-1]`) e `contrato.folha`; os registros saem em ordem de chave.
- `resumo_acao`: transformar `resumo_precos_no_dia(grades.precos, t)` e as linhas de `grades.fundamentos` no aninhamento da 4.3 (tabela "chave interna de origem"); `payout_por_ano(t, ...)` filtrado pelo ticker; `soma_por_ano(ligar_proventos(...), ticker, tipo_acao, t, params_fund.anos_historico_proventos)`; `balanco_referencia_no_dia(t, ...)`; textos da Fase 5. `caixa_liquido` e `setor_comparacao_fraca`: 1.0 → true, 0.0 → false.
- `mercado_dia`: seção 4.2. `acoes`: seção 4.1 (`universo_t` = linhas de t de `montar_universo`). `fundamentos_trimestrais`: `tabela_trimestral(t, ...)` e, por ticker, só as 8 linhas de maior `data_fim_periodo` (S19). `proventos`: `lista_proventos(ligar_proventos(ins.proventos, ins.cadastro, ins.mudancas), tickers_do_painel(...), t)` só com `data_com.year >= t.year - (params_fund.anos_historico_proventos - 1)` (S19; mesma regra de anos do `soma_por_ano`). O que sai desses cortes vai em `removidos` pelo `contrato.comparar_registros`.

**Casos de teste (`tests/test_saida_pacotes_fatos.py`; `banco_teste` + `fabrica_saida.insumos_de_teste`, D = 2025-10-22, `GERADO`, `DADOS_ATE`):**
1. Os gabaritos E2E das seções 4.1, 4.2, 4.3, 4.5 e 4.6 (valores conferidos; approx 1e-12 nos números).
2. Todo registro passa em `contrato.validar(<pacote>, registro)`; todos têm `versao_contrato == "1.0"`, `gerado_em == GERADO`, `dados_ate == DADOS_ATE`.
3. Ausência: em todos os registros, nenhuma folha tem `valor == 0` com status ≠ ok (varre recursivamente); PETR4 `ebitda.valor_12m == {"valor": None, "status": "indisponivel"}`.
4. Frações: `resumo_acao[PETR4].dividend_yield.valor == 0.05` (não 5.0); `mercado_dia.cdi_dia.valor == 0.0006` (não 0.06).
5. Point-in-time das funções: montar com `Insumos` cujas tabelas **não** foram cortadas (preços com uma linha de 2025-10-22 a 99, balanço de PETR com `data_entrega 2025-10-22`, provento PETR4 de `data_com 2025-10-22`), mas com o mesmo `t = 2025-10-21` e `cal` até t: os 5 pacotes saem iguais aos do caso 1.
6. P/L com prejuízo: `montar_resumo_acao` sobre `fabrica_fundamentos.mundo()` em t = 2026-03-16 (Insumos montado à mão com `cal = CAL` até t, índices vazios, notícias vazias) dá o gabarito unitário da 4.3 (PREJ3 e AAAA3).
7. **Corte de 8 trimestres (S19):** ticker ZZZZ3 (empresa nova) com 10 ITRs de 3 meses (`_a("ITR", ini, fim, entrega, 100, 40, 10, 1000)` com fins 2024-03-31, 2024-06-30, ..., 2026-06-30 e entrega = fim + 40 dias), t = 2026-09-30: `montar_fundamentos_trimestrais` devolve **8** registros de ZZZZ3, de 2024-09-30 a 2026-06-30 (os de 2024-03-31 e 2024-06-30 ficam fora). Com o estado de uma rodada anterior em que eram 9 trimestres entregues (t = 2026-07-31, 8 enviados: 2024-06-30 a 2026-03-31), `comparar_registros` dá `removidos == [{"ticker": "ZZZZ3", "data_fim_periodo": "2024-06-30"}]` e envia o de 2026-06-30 (mais os que mudaram de valor, se houver).
8. **Corte de 5 anos dos proventos (S19):** com t = 2025-10-21 e proventos de PETR4 em 2020-12-30 e 2021-01-04 acrescentados, o de 2020-12-30 não aparece e o de 2021-01-04 aparece (anos 2021 a 2025).

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_pacotes_fatos.py tests/test_saida_contrato.py`

---

### Fase 6b: `processamento/saida/pacote_series.py` (series_diarias; formato compacto S20, janela S19)

```python
JANELA_PREGOES = 253  # 252 variações: o gráfico de 1 ano bate com rentabilidade.a1
def inicio_janela(cal: list[date], t: date, n: int = JANELA_PREGOES) -> date
    # o 1º dos últimos n pregões de cal até t (inclusive); com menos de n pregões, cal[0]
def series_completas(ins: Insumos, multiplos: dict[str, Grade]) -> dict[str, dict]
    # {ticker: {"ticker", "tipo", "nome", "inicio_janela", "datas", "valores", "status"}} só com datas em [inicio_janela, t];
    # as grades de fatos.series são calculadas no histórico inteiro (âncora da base 100 = 1º dia da série) e só depois cortadas;
    # ANTES_DO_INICIO não entra em "datas"; status montado com contrato.trechos; n_empresas sem status
def comparar_series(atuais: dict[str, dict], estado: dict[str, dict] | None) -> tuple[list[dict], list[dict]]
    # (series_a_enviar, removidas [{"ticker"}]); regras da 2.4 com a janela:
    # 1) estado None ou ticker ausente do estado -> série inteira, substituir_serie True
    # 2) pontos do estado com data < inicio_janela atual: ignorados (saíram pelo corte, NÃO são "sumidos")
    # 3) algum ponto do estado com data >= inicio_janela atual ausente da série atual, ou com valor/status diferente
    #    (math.isclose rel 1e-9, abs 1e-12; None só é igual a None) -> série inteira, substituir_serie True
    # 4) senão: só as datas > última data do estado (valores e trechos recortados para elas), substituir_serie False;
    #    sem datas novas -> a série não vai
    # 5) série do estado que não existe mais -> {"ticker"} em removidas
def montar_series_diarias(ins, multiplos, estado, gerado_em, dados_ate) -> tuple[list[dict], list[dict], dict]
    # (registros com meta + substituir_serie, removidos, novo_estado = series_completas atuais)
```
`multiplos = fatos.multiplos.multiplos_diarios(..., desde=inicio_janela(ins.cal, ins.t))` (passado pronto por `gerar`). Números sem arredondar.

**Casos de teste (`tests/test_saida_series.py`):**
1. Gabarito E2E da 4.4 no formato compacto (PETR4, TAEE11 com os 6 trechos de 10-20, NOVA3, IBOV, IDIV, CDI, IPCA e os setores, inclusive o trecho único 10-20 a 10-21 de `SETOR:Energia`; ITUB4, IVVB11, SMLL, IFIX, `SETOR:Alimentos` e `SETOR:Financeiro` ausentes; `inicio_janela "2025-10-16"` em todas).
2. Toda série passa em `contrato.validar("series_diarias", serie)`; a maior data de `datas` é "2025-10-21"; `datas` crescentes e sem repetição; listas de `valores` do mesmo tamanho de `datas`.
3. **Corte de 253** (gabarito da 4.4, fábrica de 260 pregões): 253 datas, `inicio_janela "2025-01-13"`, 1º `indice_retorno_total` = 100.70210350350199, último = 129.54661428719584 (approx 1e-9); `inicio_janela(cal, cal[259]) == cal[7]` e `inicio_janela(cal[:4], cal[3]) == cal[0]`.
4. **Janela andando (2.4):** estado = `series_completas` com t = 2025-12-30 (janela 2025-01-10 a 2025-12-30); atual com t = 2025-12-31 → AAAA3 vai com `datas ["2025-12-31"]`, `substituir_serie: false`, `inicio_janela "2025-01-13"`; o ponto de 2025-01-10 não dispara reenvio.
5. `comparar_series` no banco de teste: (a) estado None → todas com `substituir_serie: true`; (b) estado = atual sem a última data de PETR4 → só PETR4, com 1 data e `substituir_serie: false`; (c) estado com `fechamento` de PETR4 em 10-16 = 5.0 (desdobramento) → PETR4 inteira (4 datas) com `substituir_serie: true`; (d) diferença de 1e-12 relativo → igual; (e) estado em que o ponto de 10-20 de TAEE11 tinha valor (hoje é `null` com trecho) → TAEE11 inteira; (f) série do estado que não existe mais → `removidos == [{"ticker": ...}]`; (g) nada mudou → lista vazia.
6. **Dividendo não força reenvio (2.4):** estado = `series_completas` com t = 2025-10-20 (D = 2025-10-21); atual com t = 2025-10-21 (D = 2025-10-22) e o `fechamento_ajustado` de PETR4 **anterior** a 10-21 multiplicado por 0.98 (data-ex em 10-21) → os valores 10-16 a 10-20 do índice ficam 100.0 (approx 1e-9) e PETR4 vai só com 10-21 (`substituir_serie: false`; índice 10/9.8 × 100 = 102.04081632653062). Com o `fechamento` de PETR4 anterior a 10-21 dividido por 2 (desdobramento), PETR4 vai inteira com `substituir_serie: true`.
7. **Incremental com trecho:** se o único ponto novo for `null` (ex.: TAEE11 sem preço em t), o registro enviado tem `datas` de 1 item, `valores` com `null` e o trecho `{de: t, ate: t, status: "indisponivel"}` em cada campo.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_series.py tests/test_fatos_series.py tests/test_fatos_multiplos.py tests/test_saida_contrato.py`

---

### Fase 6c: `processamento/saida/pacote_noticias.py` (noticias_dia)

```python
def janela_do_dia(ins: Insumos, params_exp) -> pd.DataFrame     # fatos.noticias.noticias_da_janela(ins.noticias, ins.cal, ins.t, ins.d, cnpj_de, ins.mudancas, params_exp)
def montar_noticias_dia(ins, janela, gerado_em, dados_ate) -> list[dict]
```
Empresa do ticker = `cnpj_de[ticker]` ou o próprio ticker. Cobertura = menor `data_publicacao` de `ins.noticias` (como `montar_dataset`); `coberta = t >= cobertura`.

**Casos de teste (`tests/test_saida_noticias.py`):**
1. Gabarito E2E da 4.7 (PETR4, PETR3, TAEE11).
2. Gabarito da Fase 3 embalado: com Insumos montado à mão (cal da Fase 3, t = 2026-10-22, d = 2026-10-23, notícias da tabela da Fase 3, cadastro com AAAA3, AAAA4, BBBB3, CCCC3): AAAA3 e AAAA4 com os mesmos 7 itens na ordem n03, n02, n08, n05, n07, n06, n04 e `destaque` 1..7; n06 com `publicado_em None`, `precisao_hora "meia_noite_pacifico"`, `janela "sem_horario"`; n02 com `publicado_em "2026-10-22T08:00:01-03:00"`, `janela "pregao"`; `janela_inicio "2026-10-22T08:00:01-03:00"`, `janela_fim "2026-10-23T08:00:00-03:00"`; CCCC3 com `itens []` e `tom_medio {null, nao_se_aplica}`.
3. Antes da cobertura (todas as notícias de 2026-10-22, t = 2026-10-21): as 5 folhas do resumo `{null, indisponivel}`, `itens []`.
4. Todos os registros passam em `contrato.validar("noticias_dia", ...)`.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_noticias.py tests/test_fatos_noticias.py`

---

### Fase 7: `processamento/saida/pacotes_experimento.py` (experimento_top, registro, fechamento, experimento_historico)

```python
AVISOS = {...}   # os 6 textos exatos da 4.8 (com {mes} e {n} onde precisa)
TITULO = "5 ações com maior chance de superar o Ibovespa (experimento)"
def escolher_modelo(pasta_modelos: Path, d: date) -> tuple[Path | None, Path | None, list[str]]
    # xgb-<AAAA-MM de d>.json; senão o maior xgb-AAAA-MM.json com AAAA-MM < mês de d (regex ^xgb-(\d{4}-\d{2})\.json$, ignora xgb-m1-*)
    # + aviso "Modelo de AAAA-MM (o do mês de D ainda não foi treinado)."; m1 = xgb-m1-<mesmo mês>.json se existir; nenhum -> (None, None, [])
def valido_para_historico(meta: dict, gerado_em: datetime, d: date, fim: date | None, limite: time) -> tuple[bool, list[str]]
    # razões (chaves de AVISOS): "provisorio" se meta["provisorio"]; "depois_10h" se gerado_em > d às `limite`;
    # "antes_producao" se fim is None; "teste_final" se fim e d <= fim. Válido = sem razões.
def gerar_top(dataset_df: pd.DataFrame, t: date, d: date, modelo, meta: dict, modelo_m1, meta_m1, janela: pd.DataFrame,
              cnpj_de: dict, params_treino, params_saida, gerado_em: datetime, dados_ate: str, nome_modelo: str,
              avisos_modelo: list[str]) -> tuple[dict, dict]
    # (pacote, interno). Copiar o padrão de treino._exemplo_top (treino.py:596-618):
    # completo = preparacao.preparar(dataset_df); mascara = data == t; preparado_dia, bruto_dia = completo[m], dataset_df[m]
    # itens = previsao.top_do_dia(preparado_dia, bruto_dia, modelo, meta, params_treino)
    # para cada motivo: texto = textos.texto_motivo(fator, valor, rank = preparado_dia[fator] da linha se fator for de preço, q = bruto noticias_dia_qtd, params_saida.tom_neutro)
    # noticias_usadas = fatos.noticias.ids_da_empresa(janela, cnpj_de.get(ticker) or ticker)
    # tirar "contribuicao" de cada motivo; interno = sombras (previsao.top_sombra_modelo / top_sombra_volatilidade), candidatos, probabilidades
def registro_existente(pasta: Path, d: date, fim: date | None) -> dict | None
    # S11: só com fim preenchido devolve o pacote de <D>.top.json (se existir); com fim vazio devolve sempre None (gera de novo)
def gravar_registro_top(pasta: Path, pacote: dict, interno: dict, fim: date | None) -> tuple[dict, bool]
    # fim preenchido: se <D>.top.json existe, devolve o pacote gravado e False (nada é sobrescrito); senão grava com open(..., "x") -> (pacote, True)
    # fim vazio: sempre grava (escrita atômica, sobrescreve) -> (pacote, True)
def pode_fechar(registro_top: dict | None, fim: date | None) -> bool
def fechar_dia(registro_top: dict, precos: pd.DataFrame, cal: list[date], agora: datetime) -> dict | None   # seção 8
def gravar_resultado(pasta: Path, resultado: dict) -> bool    # uso único, como o top
def montar_historico(resultados: list[dict], d: date, fim: date | None, universo: str, params_treino,
                     gerado_em, dados_ate) -> dict             # regras e gabaritos da 4.9
```
O valor bruto dos motivos é o do dataset (antes do rank); o rank só serve para o texto. O top 5 só é montado se houver linhas de t no dataset; senão o pacote não sai e a rodada fica `parcial`.

**Casos de teste (`tests/test_saida_experimento.py`):**
1. `escolher_modelo` (arquivos vazios criados em `tmp_path`): com `xgb-2026-06.json`, `xgb-m1-2026-06.json` e d = 2026-10-23 → (`xgb-2026-06.json`, `xgb-m1-2026-06.json`, ["Modelo de 2026-06 (o do mês de D ainda não foi treinado)."]); acrescentando `xgb-2026-10.json` → ele, sem aviso, e m1 None; com `xgb-2026-11.json` só → (None, None, []); `xgb-m1-2026-10.json` sozinho nunca é escolhido como modelo 3.
2. `valido_para_historico`: os 4 casos da seção 8 (item 5).
3. `gerar_top` com `fabrica_treino.dataset_sintetico(n_pregoes=130, n_tickers=12)` (t = último pregão, sem alvo) e um modelo treinado nele (`modelos.treinar_xgb` com `colunas_do_modelo("3")`, `n_estimators=20`), `meta = {"colunas": colunas_do_modelo("3"), "calibracao": {"aprovada": False}, "provisorio": True}`, `params_treino = fabrica_treino.params_teste()` (`liberar_chance` false): 5 itens, posições 1..5, tickers = `previsao.top_do_dia(...)` na mesma ordem; todo `chance == {"valor": None, "media": 0.5, "exibir": False, "status": "calibracao_nao_conferida"}`; 3 motivos por item, cada um com `fator`, `valor`, `efeito`, `texto` e **sem** `contribuicao`; `json.dumps(pacote)` não contém "prob" nem "contribuicao"; `modelo_versao == "xgb-2025-08"` (passado em `nome_modelo`); `pacote` passa em `contrato.validar("experimento_top", ...)`; `interno["sombra_volatilidade"]` com 5 tickers e `interno["probabilidades"]` com 12. Usar `janela` vazia (`pd.DataFrame(columns=fatos.noticias.COLUNAS_JANELA)`): todo `noticias_usadas == []`.
4. Com `params_treino` com `liberar_chance=True` e `meta["calibracao"]["aprovada"] = True`: `chance.exibir is True`, `status "ok"` e `valor` = a probabilidade do XGBoost (approx 1e-12).
5. `gravar_registro_top` e `registro_existente` (S11): (a) `fim = date(2026, 11, 2)`, D = 2026-11-03: 1ª chamada grava e devolve True; 2ª com outro pacote devolve o **primeiro** pacote e False; o arquivo não muda (mesmos bytes); `registro_existente` devolve o 1º pacote; (b) `fim = None`: a 2ª chamada devolve o **segundo** pacote e True, o arquivo passa a ter o 2º pacote, e `registro_existente` devolve None.
6. `pode_fechar` e `montar_historico`: os testes 1 a 3 da seção 8 e o gabarito da 4.9 (produção simulada).
7. `fechar_dia`: o gabarito da seção 8 (preços com `fabrica_precos.precos_de`; `aj` = `fech`).
8. Linguagem: nenhum texto dos pacotes contém "compre", "oportunidade", "melhores ações"; "recomendação" só no `aviso_fixo`.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_experimento.py tests/test_treino_previsao.py`

---

### Fase 8: `processamento/saida/gerar.py` e `processamento/saida/__main__.py` (orquestração e CLI)

```python
def gerar(d: date, *, ler=None, pasta_saida: Path | None = None, pasta_modelos: Path | None = None,
          pasta_registros: Path | None = None, pasta_estado: Path | None = None, usar_estado: bool = False,
          agora: datetime | None = None, coleta_status: dict | None = None, avisos_coleta: list[str] = (),
          existe_composicao: bool | None = None, params_treino=None, params_saida=None) -> Path   # pasta saida/D
def main(argv=None, ler=None) -> int
```
`__main__.py`: `from processamento.saida.gerar import main; raise SystemExit(main())`.
Fluxo da seção 11. Padrões: `pasta_saida = params_saida.pasta / D.isoformat()`; `pasta_modelos = treino.PASTA_MODELOS_PADRAO`; `pasta_registros = params_saida.pasta_registros`; estado em `params_saida.pasta_estado` só se `usar_estado` (o CLI liga por padrão; `--sem-estado` desliga). `agora` None → `datetime.now(fontes.SP)`. O dataset ao vivo: `DadosExperimento(precos, cadastro, noticias, balancos, universo=montar_universo(cal, cadastro, precos, exclusoes, composicao), mudancas)` e `montar_dataset(dados, cal, versao_noticias="todas", proximo_ao_vivo=d)`. Rodada: ler `execucao.json` da pasta (se existir) e somar 1. Cada pacote num `try/except Exception`: erro vira aviso `"falha ao gerar <pacote>: <tipo do erro>: <mensagem>"` e `status = "parcial"`.

**Casos de teste (`tests/test_saida_gerar.py`; `banco_teste`, `existe_composicao=False`, `agora = fabrica_saida.AGORA`, pastas em `tmp_path`, modelo pequeno salvo em `tmp_path/modelos` como `xgb-2025-10` e `xgb-m1-2025-10` com `modelos.salvar_modelo` e metadados com todas as `CHAVES_METADADOS`, `provisorio: True`, `calibracao: {"aprovada": False}`):**
1. **Os 10 arquivos:** `gerar(date(2025, 10, 22), ...)` cria exatamente `acoes.json`, `series_diarias.json`, `mercado_dia.json`, `resumo_acao.json`, `fundamentos_trimestrais.json`, `proventos.json`, `noticias_dia.json`, `experimento_historico.json`, `experimento_top.json`, `execucao.json`; cada um passa em `contrato.validar_lote`; nenhum `.tmp` sobra.
2. **Gabaritos E2E** da seção 4 (amostra): `resumo_acao` PETR4 (`pl`, `pvp`, `dividend_yield`, `balanco_referencia`), `mercado_dia` (`cdi_dia`, `ipca_ate`), `experimento_top` (estrutura da 4.8), `experimento_historico` vazio (4.9 "antes da produção"), `execucao` (4.10).
3. **Ordem:** `execucao.pacotes_enviados[*].pacote` = ["acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos", "noticias_dia", "experimento_historico", "experimento_top"].
4. **Rodada 2 (S11):** chamar de novo na mesma pasta → `execucao.rodada == 2`. (a) Com `fim` vazio (padrão), trocando o modelo entre as rodadas: o `experimento_top.json` e o `2025-10-22.top.json` passam a ser os da 2ª rodada (o 2º registro substitui o 1º). (b) Com `params_treino` de `fim = date(2025, 10, 21)` (produção simulada; D = 2025-10-22 > fim), trocando o modelo: o `experimento_top.json` da 2ª rodada é igual ao da 1ª (reconstruído do registro) e o `.top.json` não muda.
5. **Sem modelo:** `pasta_modelos` vazia → 9 arquivos (sem `experimento_top.json`), `status "parcial"`, aviso com "experimento_top".
6. **Estado:** com `usar_estado=True`, 1ª rodada → `series_diarias` com todas as séries `substituir_serie: true`; 2ª rodada idêntica → `series_diarias.registros == []`, `acoes.registros == []`, `proventos.registros == []`.
7. **Teste final:** com `fim = None` (padrão), gerar D = 2025-10-22 e depois D = 2025-10-23 (banco com preços de 10-22 a mais) na mesma `pasta_registros` → existem `2025-10-22.top.json` e `2025-10-23.top.json`, nenhum `*.resultado.json`, e `experimento_historico` com `n_dias == 0` nos dois dias.
8. **CLI:** `main(["--data", "2025-10-22", "--pasta", str(tmp), "--pasta-modelos", ..., "--pasta-registros", ..., "--sem-estado"], ler=banco_teste())` devolve 0; `--data 2025-13-01` → erro do argparse (SystemExit 2); `--data 2025-10-16` (sem pregão antes) → 4; com `monkeypatch` em `dataset._leitor_padrao` levantando `fontes.ErroConfiguracao` → 2, e `fontes.ErroSomenteLeitura` → 3, sem criar a pasta.
9. **Sem banco real:** com `monkeypatch` fazendo `fontes.criar_engine` levantar erro, os testes 1 a 8 passam (só usam `ler` injetado).

**`tests/test_vazamento_saida.py` (seção 6):** o teste de veneno (arquivos byte a byte iguais, menos `execucao.json`) e os testes explícitos da seção 6.

**Verificação:** `.venv\Scripts\python.exe -m pytest -q tests/test_saida_gerar.py tests/test_vazamento_saida.py` e depois `.venv\Scripts\python.exe -m pytest -q` (projeto inteiro).

**Ação do usuário depois da Fase 8** (lê o banco; o subagente não roda): `python -m processamento.saida --data 2026-10-23`. Esperado: código 0; `saida/2026-10-23/` com os 10 arquivos; `experimento_top.modelo_versao == "xgb-2026-06"`, `valido_para_historico == false`; `experimento_historico.resumo.n_dias == 0`; nenhum arquivo `*.resultado.json` em `registros/experimento/`. Medir o tempo da rodada (para o prazo das 9h45 da etapa 8).

---

## 13. Mudanças propostas na ESPECIFICACAO.md (item J; texto pronto, aplicar depois da aprovação)

**13.1 Seção 2.1**, trocar a linha `├── saida/ ...` por:
```
├── saida/                   # pacotes da seção 8 (arquivo JSON hoje; API depois): contrato.py (validador),
│                            # insumos.py (leitura cortada), textos.py, pacotes_*.py, gerar.py (python -m processamento.saida)
```
e acrescentar em `fatos/`: `series.py` (séries base 100), `multiplos.py` (P/L, P/VP e yield diários), `noticias.py` (notícias da janela do painel). Acrescentar a pasta `registros/experimento/` (top 5 do dia e resultado; uso único).

**13.2 Seção 8.1**, acrescentar à tabela:

| Regra | Definição |
|---|---|
| Folha | Todo número de indicador vai como `{"valor": ..., "status": ...}`. `ok` exige valor; valor nulo exige status ≠ `ok`; valor com status ≠ `ok` só em `lucro_negativo`. **Exceção: o `series_diarias` usa o formato compacto (item 4 da 8.3)** |
| Janelas do pacote | A interface mostra 1m, 6m e 1a: `series_diarias` leva os últimos 253 pregões até t; `fundamentos_trimestrais`, os 8 trimestres mais recentes de cada ação; `proventos` e `proventos_por_ano`, 5 anos (ano de t e os 4 anteriores); `experimento_historico`, tudo desde a produção. Os cálculos usam o histórico inteiro; só o pacote é cortado |
| `status` da chance | `ok` ou `calibracao_nao_conferida` (só no `chance` do `experimento_top`) |
| Arquivos | Um arquivo por pacote em `saida/AAAA-MM-DD/<pacote>.json` (D = dia da rotina), com envelope `{pacote, versao_contrato, chave, gerado_em, dados_ate, registros, removidos}`; cada registro repete os metadados |
| Datas de referência | D = dia da rotina = pregão previsto; t = último pregão antes de D. `mercado_dia`, `resumo_acao`, `noticias_dia` usam t; `experimento_top` e `execucao` usam D; `dados_ate` = 08:00 de D |
| Envio "quando muda" | `acoes`, `fundamentos_trimestrais`, `proventos` e `series_diarias` comparam com o estado do último envio (`saida/estado/`): só vai o novo ou alterado; o que sumiu vai em `removidos`; série com ponto antigo alterado vai inteira com `substituir_serie: true` |

**13.3 Seção 8.3**, substituir os itens 2, 3, 4, 7, 9 e 10 pelos textos abaixo, e acrescentar ao fim do item 5: "Só os 8 trimestres mais recentes de cada ação (os mais antigos saem em `removidos`)." e ao fim do item 6: "Só os proventos com data-com no ano de t ou nos 4 anteriores."

**2. `mercado_dia`:** `data_referencia` (t); `IBOV`, `USDBRL`, `BRENT`: `{fechamento, variacao_dia, unidade}`; `cdi_dia` (fração ao dia) e `cdi_data`; `ipca_12m`; `ipca_ate` (último mês de IPCA usado, `AAAA-MM`); `indices`: `{CDI, IPCA, IDIV, SMLL, IFIX, IVVB11}` × `{d1, m1, m6, a1}` (o % de cada índice por período, igual para todas as ações).

**3. `resumo_acao`:** como antes, com cada número em folha; acrescenta `proventos_por_ano` (soma por ano, 5 anos), `ebitda.rotulo` ("EBITDA (cálculo padrão CVM)"), `endividamento.aviso` ("Dívida líquida sem arrendamentos."); textos prontos em `volume.relativo`, `volatilidade_20d`, `beta` e `pl` (prejuízo). Sem `status` de grupo no `ebitda` e no `endividamento` (cada campo tem o seu).

**4. `series_diarias`** (formato compacto, só neste pacote): um registro por série com `ticker`, `tipo` (`acao`, `etf`, `indice`, `taxa`, `setor`), `nome`, `substituir_serie`, `inicio_janela`, `datas` (lista crescente, sem repetir), `valores` (uma lista por campo, do mesmo tamanho de `datas`, número ou `null`) e `status` (por campo, só para os pontos que não são `ok`, em trechos `{de, ate, status}` contíguos e sem sobreposição; `null` ⇔ coberto por um trecho; valor coberto por trecho só com `lucro_negativo`). Campos por tipo: ação: `fechamento`, `indice_retorno_total` (com dividendos), `volume`, `pl`, `pvp`, `dividend_yield` (point-in-time, mesmas regras e status do `resumo_acao`); `IVVB11`: fechamento, índice, volume; `IBOV`, `IDIV`, `SMLL`, `IFIX`: fechamento (pontos) e índice; `CDI`, `IPCA`: índice base 100 acumulado (CDI: taxas com data < d; IPCA: meses fechados até K(d)); `SETOR:<nome>`: índice e `n_empresas` (sem status). Números sem arredondar. **Janela:** só os últimos 253 pregões até t (`inicio_janela` = o 1º deles); a API apaga os pontos da série com data anterior a `inicio_janela`, e o ponto que sai pelo corte não conta como mudança. **Base 100 com âncora fixa** no 1º dia da série no histórico inteiro (o 1º valor enviado em geral não é 100); o pacote não rebaseia no início da janela, porque isso mudaria todos os pontos todo dia (reenvio inteiro diário) e exigiria três versões (1m, 6m, 1a). **Setor:** média igual por empresa dos retornos diários das ações ON, PN e UNIT do setor (BDR fora), **incluindo a própria**, com preço no dia e no pregão anterior, encadeada em base 100; dia sem nenhuma: ponto vazio (`indisponivel`) e a cadeia segue do último valor. A divisão de dois pontos dá a rentabilidade da janela do `resumo_acao`/`mercado_dia`. **A interface recorta o período e parte do mesmo ponto dividindo pelo primeiro valor do recorte.** Reenvio da série inteira (`substituir_serie: true`) quando algum ponto antigo dentro da janela muda (desdobramento, bonificação, reapresentação de balanço, histórico estendido); dividendo não muda o índice dos dias anteriores à data-ex. Envio diário: o mesmo formato só com as datas novas.

**7. `noticias_dia`:** `data_referencia` (t), `ticker`, `janela_inicio`/`janela_fim` (08:00:01 de t até 08:00 de D, a mesma janela do modelo), `resumo` (`quantidade`, `positivas`, `neutras`, `negativas`, `tom_medio`, em folhas) e `itens` (`id`, `titulo`, `fonte`, `link`, `publicado_em`, `data_publicacao`, `precisao_hora`, `rotulo`, `prob_*`, `janela` = `pregao` (inclui a pré-abertura de t) / `noite` / `sem_horario` (sem hora real, inclusive "só data"), `destaque`, `status`). Rótulo: maior das 3 probabilidades; empate com o neutro, ou positivo = negativo, vira neutro. Destaque: protagonista primeiro, depois |positivo − negativo| e depois a mais recente. Sem notícia: quantidade 0 e `tom_medio` `nao_se_aplica`; antes do início da cobertura: tudo `indisponivel`.

**9. `experimento_historico`:** `data_referencia` (dia fechado); `dia` (`ranking`, `resultado` com `retorno`, `retorno_ibov`, `superou` de cada ação, `acertos_dia`, `acertos_top3`, `resultado_incompleto`, `taxa_acumulada`) ou `null`; `resumo` (`periodo_inicio`, `periodo_fim`, `n_dias`, `taxa_acerto`, `acaso_media`, `acaso_faixa`, `universo`, `nota`). Só entram dias com `valido_para_historico = true` e pregão previsto depois de `treino.teste_final.fim`; até a produção, `n_dias = 0` e a nota explica. O resultado de cada dia é gravado uma vez (`registros/experimento/AAAA-MM-DD.resultado.json`) e nunca recalculado.

**10. `execucao`:** `data_referencia` (D), `rodada`, `inicio`, `fim`, `status` (`em_andamento`, `ok`, `parcial`, `falhou`), `coleta_status` (o que se leu do painel da coleta; vazio até a etapa 8), `pacotes_enviados` (`pacote`, `arquivo`, `registros`, `removidos`), `avisos`.

**8. `experimento_top`** (substituir o texto e o exemplo): lista `ranking` com as **5** ações (posição 1 a 5), cada uma com chance, motivos (com texto) e notícias usadas.
```json
{
  "versao_contrato": "1.0",
  "gerado_em": "2026-11-03T09:12:00-03:00",
  "dados_ate": "2026-11-03T08:00:00-03:00",
  "data_referencia": "2026-11-03",
  "pregao_previsto": "2026-11-03",
  "pregao_base": "2026-10-30",
  "valido_para_historico": true,
  "modelo_versao": "xgb-2026-11",
  "modelo_provisorio": false,
  "universo": "composicao_atual",
  "n_candidatas": 84,
  "selo": "em_avaliacao",
  "titulo": "5 ações com maior chance de superar o Ibovespa (experimento)",
  "aviso_fixo": "Não constitui recomendação de investimento.",
  "avisos": [],
  "ranking": [
    {
      "posicao": 1,
      "ticker": "CMIG4",
      "chance": {"valor": null, "media": 0.5, "exibir": false, "status": "calibracao_nao_conferida"},
      "motivos": [
        {"fator": "noticias_dia_tom", "valor": 0.42, "efeito": "ajudou", "texto": "Notícias do último pregão e da noite com tom positivo (3 notícias)"},
        {"fator": "ret_5d", "valor": -0.031, "efeito": "ajudou", "texto": "Caiu 3,1% nos últimos 5 pregões (abaixo da média das ações)"}
      ],
      "noticias_usadas": ["n000123", "n000124", "n000125"]
    }
  ]
}
```
(valores ilustrativos; 02/11 é feriado, por isso o pregão base é 30/10.) `valido_para_historico = true` só com modelo não provisório, gerado até as 10h de D e D depois do fim do teste final (`treino.teste_final.fim`). `chance.valor` fica `null` (`calibracao_nao_conferida`) até a calibração ser aprovada **e** `liberar_chance: true` (F16); então vem o número, com `exibir: true` e `status: "ok"`. `modelo_versao` aponta para `modelos/xgb-AAAA-MM.json` (sem o dia). Os fatores dos motivos são os nomes das colunas do dataset (seção 7.3), com o valor bruto; os textos falam da janela única do modelo (08:00:01 de t até 08:00 de D: "último pregão e noite"). As sombras (modelo 1 e regra da volatilidade) e as probabilidades ficam só no registro interno (`registros/experimento/`), não no pacote.

**13.4 Seção 8.4**, acrescentar no fim: "Comparação com índices: o % de cada índice por período vem em `mercado_dia.indices` (igual para todas as ações). P/L, P/VP e yield ao longo do tempo: `series_diarias` (pontos das ações). Linha do acerto acumulado do experimento: `experimento_historico.dia.taxa_acumulada`. As séries trazem 1 ano (253 pregões: 252 variações, para o gráfico de 1 ano bater com a `rentabilidade.a1`), os trimestres 8 e os proventos 5 anos."

**13.5 Seção 8.5**, acrescentar: "Nomes dos arquivos: `execucao.json`, `acoes.json`, `series_diarias.json`, `mercado_dia.json`, `resumo_acao.json`, `fundamentos_trimestrais.json`, `proventos.json`, `noticias_dia.json`, `experimento_historico.json`, `experimento_top.json` (o `execucao.json` é regravado no fim da rodada). Cada pacote é validado antes de gravar; reprovado, não é gravado e a rodada fica `parcial`."

**13.6 Seção 7.7**, trocar "(nome **sem o dia**; o exemplo da 8.3 é acertado na etapa 7)" por "(nome sem o dia, como no exemplo da 8.3)". **Seção 9, decisão F16**, trocar "(o exemplo da 8.3 é acertado na etapa 7)" por "(como no exemplo da 8.3)".

**13.7 Seção 9**, apagar o item "Etapa 7 (vindos da etapa 3, não implementados nela)" das pendências internas e acrescentar, depois das decisões da etapa 6:

**Decisões da etapa 7 (AAAA-MM-DD; plano completo, com os casos de teste, em `docs/plano_etapa7.md`)**
- **S1 Datas:** D = dia da rotina (pregão previsto); t = último pregão antes de D. Fase 1 e notícias com `data_referencia = t`; `experimento_top` e `execucao` com D; `dados_ate` = 08:00 de D.
- **S2 Folha:** todo número de indicador em `{valor, status}`; cadastro pode ter texto nulo sem status.
- **S3 Arquivos:** um por pacote em `saida/D/`, com envelope de lote; cada registro com os metadados.
- **S4 Quando muda:** comparação com o estado do último envio (`saida/estado/`); `substituir_serie` quando um ponto antigo muda; `removidos` para o que sumiu; sem estado, vai tudo.
- **S5 Setor:** média por empresa dos retornos diários (preço em t e no pregão anterior) das ações ON/PN/UNIT do setor, inclusive a própria; BDR fora; dia sem retorno = ponto vazio e a cadeia segue.
- **S6 Índices base 100:** CDI com as taxas de datas < d; IPCA com meses fechados até K(d); lacuna = `indisponivel` dali em diante.
- **S7 % dos índices** em `mercado_dia.indices`.
- **S8 P/L, P/VP e yield diários** em `series_diarias`, calculados por trechos entre entregas de balanço (`fatos/multiplos.py`).
- **S9 Notícias do painel:** mesma janela do modelo; rótulo com empate = neutro; destaque protagonista → força do tom → mais recente.
- **S10 Top 5:** modelo do mês de D ou o mais recente anterior (com aviso); válido só com modelo oficial, até as 10h e depois do fim do teste final; sombras e probabilidades só no registro.
- **S11 Registro do top 5** em `registros/experimento/` (versionável). Com `treino.teste_final.fim` preenchido (produção), é de uso único: gravado na 1ª geração e nunca sobrescrito, e a rodada repetida do mesmo dia reconstrói o pacote do registro. Com `fim` vazio (testes de funcionamento), cada rodada gera de novo e sobrescreve o registro do dia.
- **S12 Histórico vazio até a produção;** nenhum dia do teste final é fechado.
- **S13 Validador próprio** (`saida/contrato.py`), sem dependência nova.
- **S14 Textos prontos** (`saida/textos.py`), com `tom_neutro = 0,05` e as faixas do beta.
- **S15 Acréscimos no `resumo_acao`:** `proventos_por_ano`, `ebitda.rotulo`, `endividamento.aviso`; sem status de grupo.
- **S16 `ativo_no_universo`** = candidata do experimento em t (tipo aceito, não excluída, na composição), mesmo sem preço no dia.
- **S17 Ponto de entrada** `python -m processamento.saida --data D`; a etapa 8 chama `gerar(...)` como função.
- **S18 Bloco `saida`** no `parametros.yaml` (limite das 10h, pastas, `tom_neutro`).
- **S19 Janelas do pacote:** a interface mostra 1m, 6m e 1a. `series_diarias` (inclusive P/L, P/VP e yield diários) com os últimos 253 pregões até t; base 100 sem rebasear (âncora no 1º dia da série; a interface divide pelo 1º valor do recorte); `inicio_janela` em cada série, e o ponto que sai pelo corte não dispara `substituir_serie`; `fundamentos_trimestrais` com os 8 trimestres mais recentes; `proventos` e `proventos_por_ano` com 5 anos; `experimento_historico` sem corte. As contas usam o histórico inteiro; P/L, P/VP e yield por trechos só nos 253 pregões (~8 s por rodada).
- **S20 Formato compacto só no `series_diarias`:** `datas` + `valores` (listas paralelas) + `status` em trechos `{de, ate, status}` só para os pontos que não são `ok`; números sem arredondar (2,6 MB no 1º envio com 252 pontos, contra 8,0 MB em folhas; ~47 KB por dia). Os outros pacotes seguem com a folha.

E nas pendências internas, acrescentar **"Etapa 8 (vindos da etapa 7)":** (a) o calendário só conhece pregões passados: a rotina precisa saber se D é pregão (lista de feriados da B3 no `parametros.yaml` ou checagem no dia seguinte, com o dia descartado pelo `fechar_dia`); (b) checagem diária da seção 6 (poucas ações, retorno > 30%, volume zero, preço parado, indicador vazio) como avisos do `execucao`; (c) fixar `treino.teste_final.fim`, rodar o teste final uma vez e ligar o histórico ao vivo; (d) retreino mensal (`xgb-AAAA-MM`); (e) limpar `registros/experimento/` dos testes de funcionamento antes da produção; (f) medir o tempo da rodada contra o prazo das 9h45.

---

## 14. Decisões (todas aprovadas pelo usuário em 23/10/2026)

1. **APROVADA (23/10/2026)** **S1 Datas de referência.** Recomendo: Fase 1 e notícias com `data_referencia = t` (data do fechamento mostrado); experimento e execução com D; `dados_ate` = 08:00 de D. Alternativa: tudo com D, mais um campo `data_pregao = t` nos pacotes da Fase 1.
2. **APROVADA (23/10/2026)** **S2 Folha `{valor, status}` em todo número.** Recomendo (uniforme; o validador confere "nulo ⇔ status"). Alternativa: campos planos com `<campo>_status` ao lado (JSON menor, regra mais difícil de conferir).
3. **APROVADA (23/10/2026)** **S3 Um arquivo por pacote com envelope de lote** (`saida/D/<pacote>.json`). Alternativa: um arquivo por registro (milhares de arquivos por dia).
4. **APROVADA (23/10/2026)** **S4 "Quando muda" pelo estado do último envio** (`saida/estado/`), com `substituir_serie` e `removidos`. Alternativa mais simples: mandar tudo todo dia, com `substituir_serie: true` sempre (~15 MB por dia; sem estado para perder; a API apaga e regrava).
5. **APROVADA (23/10/2026): média por empresa** **S5 Série do setor:** média **por empresa**, retornos que exigem preço em t e no pregão anterior, BDR fora, a própria ação dentro, dia sem retorno = ponto vazio e a cadeia segue. Alternativas: média **por ação** (PETR3 e PETR4 contam 2 vezes); retorno **as-of** (não perde o movimento depois de um buraco, mas joga vários dias num só).
6. **APROVADA (23/10/2026)** **S6 Índices base 100** definidos para bater com a rentabilidade das janelas (CDI com taxas de datas < d; IPCA por meses fechados até K(d)); lacuna no CDI ou no IPCA deixa os pontos seguintes `indisponivel`. Alternativa: seguir a cadeia pulando a lacuna (gráfico contínuo, mas com rendimento zero inventado no dia que falta).
7. **APROVADA (23/10/2026)** **S7 % dos índices em `mercado_dia.indices`** (fecha o buraco da 8.3/8.4). Alternativas: repetir em cada `resumo_acao` (85 cópias iguais por dia) ou deixar a interface calcular pela série.
8. **APROVADA (23/10/2026): por trechos** **S8 P/L, P/VP e yield diários no `series_diarias`, por trechos** (~17 s por rodada hoje, ~40 s com 5 anos; ~110 linhas e ~8 testes). Alternativas: só fim de mês (~40 s, ~25 linhas, gráfico mensal); só daqui para frente (rápido, sem histórico na estreia); deixar de fora (a planilha não pede gráfico desses três no tempo).
9. **APROVADA (23/10/2026)** **S9 Notícias do painel na mesma janela do modelo** (08:00:01 de t até 08:00 de D), com `janela` pregão/noite/sem_horario, rótulo com empate = neutro e destaque protagonista → força → recente. Alternativa: "notícias do dia" = data de publicação = t, sem a noite (aí o `noticias_dia` deixa de bater com as `noticias_usadas` do top 5).
10. **APROVADA (23/10/2026)** **S10 `experimento_top` antes da produção:** gerar com o modelo mais recente (hoje `xgb-2026-06`, com aviso), `valido_para_historico: false`, chance `null`; válido só com modelo oficial + até as 10h + D depois do fim do teste final; sombras e probabilidades fora do pacote. Alternativa: não gerar o top 5 até a produção (a rotina não é testada de ponta a ponta).
11. **APROVADA COM AJUSTE (23/10/2026)** **S11 Registro de uso único em `registros/experimento/`** (versionável, para auditoria do teste ao vivo); rodada repetida do mesmo dia reconstrói o pacote do registro (a primeira geração vale). Alternativas: guardar em `saida/registros/` (fora do git, pode se perder); ou deixar a 2ª rodada substituir a 1ª se ainda for antes das 10h (pode ficar para a etapa 8). **Ajuste aprovado:** o uso único (`open("x")` e reconstrução na 2ª rodada) só vale com `treino.teste_final.fim` preenchido; com `fim` vazio, cada rodada gera de novo e sobrescreve o `D.top.json`.
12. **APROVADA (23/10/2026)** **S12 `experimento_historico` vazio até a produção** (`n_dias = 0`, nota), sem fechar nenhum dia do teste final. Alternativa: mostrar o walk-forward do desenvolvimento, marcado e fora do resumo (números otimistas, F7; não recomendo).
13. **APROVADA (23/10/2026)** **S13 Validador próprio** em Python. Alternativa: `jsonschema>=4.23` (dependência nova; dá arquivos de esquema padrão para a equipe da API).
14. **APROVADA (23/10/2026)** **S14 Textos prontos:** os modelos da Fase 5 (tom neutro até ±0,05; faixas do beta 0,8 / 0,95 / 1,05 / 1,2; "último pregão e noite" para a janela). Alternativa: não mandar textos e ficar só com os números.
15. **APROVADA (23/10/2026)** **S15 Acréscimos no `resumo_acao`:** `proventos_por_ano` pronto, `ebitda.rotulo`, `endividamento.aviso`, sem status de grupo. Alternativa: manter só os campos da 8.3 atual.
16. **APROVADA (23/10/2026)** **S16 `ativo_no_universo`** = candidata do experimento em t, mesmo sem preço naquele dia. Alternativa: exatamente "entrou no ranking de t" (oscila quando falta um preço).
17. **APROVADA (23/10/2026)** **S17 Ponto de entrada** `python -m processamento.saida --data D` e, para a etapa 8, a função `gerar(...)`. Alternativa: só a rotina da etapa 8 gera os pacotes.
18. **APROVADA (23/10/2026)** **S18 Bloco `saida` no `parametros.yaml`** (limite "10:00", pastas, `tom_neutro`). Alternativa: constantes no código.
19. **APROVADA (23/10/2026)** **S19 Janelas do pacote (decisão nova do usuário):** a interface mostra só 1m, 6m e 1a; `series_diarias` (inclusive P/L, P/VP e yield) com os últimos 253 pregões até t, base 100 sem rebasear (âncora fixa no 1º dia da série), `inicio_janela` em cada série e corte que não dispara reenvio; `fundamentos_trimestrais` com 8 trimestres; `proventos` e `proventos_por_ano` com 5 anos; `experimento_historico` sem corte. P/L, P/VP e yield por trechos só nos 253 pregões (~8 s).
20. **APROVADA (23/10/2026)** **S20 Formato compacto só no `series_diarias` (decisão nova do usuário):** `datas` + `valores` + trechos de `status`; sem arredondar (2,6 MB × 8,0 MB em folhas com 252 pontos; arredondar a 6 casas daria 1,7 MB, mas quebraria a consistência exata com a rentabilidade do resumo).

---

## 15. Onde os dados ou a especificação não batem (listado, não resolvido)

1. **A 8.3 não tem os % dos índices por período** que a planilha e a 8.4 pedem (S7).
2. **`fatos/noticias.py`, previsto na 2.1, nunca foi criado**; a Fase 3 cria.
3. **O exemplo da 8.3** usa `"modelo_versao": "xgb-2026-11-01"`, `"tom_noticias_noite"`, `"retorno_5d"`, "Notícias da noite" e `chance.valor` preenchido: tudo anterior à N2-A e à F16. O texto novo está na 13.3.
4. **O calendário só conhece pregões passados** (datas com IBOV). A etapa 7 assume que D é pregão; se não for (feriado), o top 5 daquele dia nunca fecha (`fechar_dia` descarta com aviso). Fica para a etapa 8 (13.7).
5. **A checagem diária da seção 6** não tem etapa definida; proposta: etapa 8, como avisos do `execucao`.
6. **IPCA ao regerar dias antigos:** K(d) usa o mês anterior mesmo nos primeiros ~10 dias do mês, quando o IBGE ainda não publicou; num dia antigo regerado, o IPCA aparece alguns dias antes do que estaria disponível ao vivo (ao vivo isso não acontece: o mês ainda não está no banco). Afeta só o painel, não o modelo. Limitação a registrar.
7. **IDIV, SMLL e IFIX têm 2 dias**: janelas e gráficos desses índices ficam `historico_insuficiente`/`indisponivel` até a coleta completar (seção 10). Correto, não é bug.
8. **Payout por ano tem 1 barra** (só a DFP 2025 no banco) e os gráficos trimestrais de 12 meses têm 3 pontos. Correto com o histórico atual.
9. **A planilha cita a coluna `atualizado_em`** em todas as tabelas; a 3.1 diz que nenhuma tem. Não afeta a saída (o reenvio é detectado pela comparação com o estado).
10. **A planilha pede o aviso "experimento acadêmico, não é recomendação de investimento"**; a especificação fixa "Não constitui recomendação de investimento.". O plano usa o da especificação em `aviso_fixo`.
11. **Setor com buraco de preço** perde o movimento do dia do buraco e do seguinte (seção 7, segundo exemplo). Limitação a registrar (alternativa em S5).
12. **Janela × rentabilidade de 1 ano (S19): RESOLVIDO (23/10/2026).** O usuário escolheu **253** pregões (252 variações), para o gráfico de 1 ano bater exatamente com `rentabilidade.a1`.
13. **S19 diz que a interface mostra só 1m, 6m e 1a**, mas o `resumo_acao` e o `mercado_dia.indices` continuam com `d1` (a 8.3 pede; é também a variação do dia da cotação). **Decidido pelo usuário (23/10/2026): manter o `d1`.**
14. **A instrução pedia S19 a S22**, mas só chegaram duas decisões novas (janelas e formato compacto); ficaram como S19 e S20.

---

## 16. Arquivos

- **A alterar:** `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\config\parametros.yaml` (bloco `saida`), `...\processamento\calendario.py` (linha 21), `...\ESPECIFICACAO.md` (seção 13 deste plano, depois da aprovação).
- **A criar em `...\processamento\fatos\`:** `series.py`, `multiplos.py`, `noticias.py`.
- **A criar em `...\processamento\saida\`:** `__init__.py`, `__main__.py`, `parametros.py`, `contrato.py`, `insumos.py`, `textos.py`, `pacotes_fatos.py`, `pacote_series.py`, `pacote_noticias.py`, `pacotes_experimento.py`, `gerar.py`.
- **A criar em `...\tests\`:** `fabrica_saida.py`, `test_saida_parametros.py`, `test_fatos_series.py`, `test_fatos_multiplos.py`, `test_fatos_noticias.py`, `test_saida_contrato.py`, `test_saida_textos.py`, `test_saida_pacotes_fatos.py`, `test_saida_series.py`, `test_saida_noticias.py`, `test_saida_experimento.py`, `test_saida_gerar.py`, `test_vazamento_saida.py`.
- **Saídas geradas:** `...\saida\AAAA-MM-DD\*.json` e `...\saida\estado\*.json` (fora do git); `...\registros\experimento\AAAA-MM-DD.top.json` e `.resultado.json` (versionáveis; S11).
- Nenhuma dependência nova (S13).
