# Plano: retornos diários suspeitos (item 1) e série do setor sem a própria empresa (item 2)

Arquiteto, 24/10/2026. **Versão 2** (decisões do usuário de 24/10/2026): DS1 a DS9 aprovados, com o DS9 indo
para a seção 10 da especificação; item 2 = **opção D** (uma série "setor sem a própria empresa" por ação, e a
tabela sai da razão dela); o DS4 deixa de existir. Fases 1 a 6 para implementar.
Nenhum número aqui veio do banco: os casos reais saem do pacote local `saida_completa/2026-10-23/`
(arquivos JSON já gerados) e os gabaritos dos testes saem das fábricas (`tests/fabrica_*.py`,
`banco_teste`). "(conferido)" = valor obtido rodando o código atual sobre a fábrica; para a série nova, um
protótipo cujo resultado foi conferido contra o `indice_setor` atual aplicado a cada subconjunto de empresas.
---

## 0. O caso real (pacote `saida_completa/2026-10-23`, 253 pregões de 16/10/2025 a 22/10/2026)

Retornos diários de `fechamento_ajustado` fora de [-75%, +100%] (os de `fechamento` são idênticos):

| ticker | data | retorno | leitura |
|---|---|---|---|
| AZUL3 | 2026-02-10 | +4.499% (× 46) | salto sem volta: provável grupamento não ajustado no `fechamento_ajustado` (também é erro da coleta) |
| AZUL3 | 2026-04-09 | +14.101.212% | 217 → 30.599.848 |
| AZUL3 | 2026-04-20 | -99,9997% | 32.249.838 → 30,54 (21/04 é feriado) |

Nenhuma outra ação passa dos limites (AZUL3 -56,6% em 14/01 e +60% em 20/02 ficam dentro).
`SETOR:Bens Industriais` (7 empresas, todas no universo): hoje +11.400.822% em 1 ano; com a regra
abaixo, **-10,07%** em 1 ano (m6 +1,53% e m1 +8,02% não mudam). Em t = 22/10 as medianas do
`resumo_acao` **não mudam**: a1 da AZUL3 é `historico_insuficiente` e as bases de m1/m6 já são
posteriores a 20/04. O item 1 corrige o gráfico do setor e passa a proteger os dias futuros.

---
A série `SETOR:<nome>` sai do pacote na versão 2 (DS15); os números acima servem só para medir o caso.
Na série nova, a `SETOR_SEM:EMBJ3` (Bens Industriais sem a Embraer) teria o mesmo problema sem a regra.

---
## 1. Decisões do item 1 (do arquiteto; aprovadas pelo usuário em 24/10/2026)

- **DS1 Base do retorno:** `fechamento_ajustado` (a mesma da série do setor, S5), **contra o último
  preço anterior com valor** (base as-of, como a `variacao`). Assim um salto escondido atrás de um dia
  sem preço também é pego (com `retornos_diarios`, que não preenche lacunas, ele passaria). Limites
  **estritos**: -75% e +100% exatos NÃO são suspeitos. NaN nunca é suspeito.
- **DS2 Parâmetros:** bloco `fase1` do `parametros.yaml` (é regra do painel), números sem aspas:
  `retorno_suspeito_min: -0.75`, `retorno_suspeito_max: 1.0`, `retorno_suspeito_pregoes_nivel: 21`.
  Validação: min com -1 < min < 0; max > 0; pregões inteiro > 0. Os campos novos de
  `ParametrosPrecos` têm valor padrão (os testes que montam `ParametrosPrecos(...)` à mão seguem
  valendo). Efeito colateral aceito: o JSON do dataset do experimento (`asdict(params_precos)`) passa a
  listar as 3 chaves; o CSV não muda.
- **DS3 Série do setor (vale para a série nova `SETOR_SEM:<ticker>`, DS10):** o retorno suspeito da ação **naquele dia** sai da média daquele dia (a
  empresa conta com as outras ações dela, se houver; senão não conta e `n_empresas` cai 1). Os dias
  entre os dois saltos ficam (são razões entre dois preços errados na mesma escala, ex.: +5%). A
  cadeia fica certa: exemplo numérico na Fase 2 (caso 2c). Trade-off: o movimento real da ação nos
  dias dos saltos se perde (ela fica ausente nesses dias, não zero).
- **DS4 (retirado na versão 2):** a máscara própria das medianas de rentabilidade não existe mais. A
  `rentabilidade.setor` passa a ser a razão da série `SETOR_SEM:<ticker>` (DS11), que já não conta o retorno
  suspeito do dia (DS3).
- **DS5 Medianas de nível (`pl.setor`, `pvp.setor`, `dividend_yield.setor`, as que usam `fech(t)`):**
  a **empresa inteira** (todas as ações do CNPJ, porque o valor de mercado soma as classes) fica fora
  dessas três medianas em t se alguma ação dela teve retorno suspeito nos últimos
  `retorno_suspeito_pregoes_nivel` = 21 pregões até t. ROE, margens, payout, EBITDA e endividamento
  não usam preço: não mudam. **Alternativas avaliadas:** (a) 252 pregões: mais seguro, mas hoje tiraria
  a AZUL3 (P/L 3,42, possivelmente correto depois do grupamento) e mudaria o `pl.setor` da MOTV3 de
  16,29 para 27,66 num setor de 7 empresas: custo alto num caso em que o preço já está certo;
  (b) emparelhar o salto de ida com o de volta ("dentro do trecho"): mais exato, mas exige regra de
  pareamento frágil (o caso de 10/02 não tem volta). Escolha: 21 pregões, sem pareamento. Limitação:
  um trecho errado com mais de 21 pregões voltaria às medianas de nível depois do 21º (o aviso e o
  diagnóstico continuam listando os saltos).
- **DS6 O valor da própria ação não muda:** cotação, rentabilidade, variação, P/L, P/VP, yield, beta,
  volatilidade e a série da ação seguem com o preço como veio (o usuário pediu "não corrigir").
  Também não mudam: `posicao_pct` (volume e volatilidade) e `setor_comparacao_fraca`.
- **DS7 Aviso no `execucao`:** só para retornos suspeitos com data dentro da janela do pacote
  (`inicio_janela` .. t, os 253 pregões do `series_diarias`), só das ações ON/PN/UNIT do painel
  (`pares_do_painel`, as que entram nas séries e nas medianas do setor). Sai em toda rodada que gera pacotes
  (diária e carga completa), não depende da checagem diária. Texto exato:
  `Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre {ini} e {t}, fora das séries e das medianas do setor: {lista}.`
  `{lista}` = `TICKER (AAAA-MM-DD, AAAA-MM-DD)` por ticker, em ordem alfabética, separados por
  ", "; mais de 10 tickers: os 10 primeiros e " e mais k". Hoje sairia:
  `... entre 2025-10-16 e 2026-10-22, ...: AZUL3 (2026-02-10, 2026-04-09, 2026-04-20).`
- **DS8 Diagnóstico:** seção nova "Retornos diários suspeitos" em `diagnostico/temas.py`, calculada
  em pandas sobre `fontes.ler_tabela("precos")` (nenhum SQL novo), histórico inteiro, todos os tickers
  de `v1-precos`, com a mesma função `retornos_suspeitos` do processamento. É **nota + tabela** (como
  "Quantidade de ações suspeita"), não divergência. Só a coluna ajustada decide (um desdobramento
  real derruba o `fechamento` mas não o ajustado); a tabela mostra também o retorno do `fechamento`.
- **DS9 Pendência do experimento (não muda nesta tarefa; vai para a SEÇÃO 10 da especificação, "resolver
  antes do treino definitivo"):** a `ret_vs_setor` (média do setor, 7.3) e outras variáveis também são
  contaminadas. AZUL3 está no universo (`ativo_no_universo = true`). Impacto medido no pacote: em 09/04 a
  `ret_vs_setor` das outras 6 de Bens Industriais fica perto de -23.500 e em 20/04 perto de +0,17 (12 linhas;
  como a coluna vira rank por pregão, o efeito é "pior/melhor do dia"); nas linhas da própria AZUL3:
  `ret_1d/5d/20d`, volatilidade e beta por até 252 pregões, `dist_max_52s` perto de -100% por 1 ano, e o
  **alvo** de 08/04 (1) e 17/04 (0). Proposta: mesma máscara no `ret_vs_setor` e descarte das linhas cujas
  variáveis ou alvo tocam um retorno suspeito. Obrigatório antes do treino "para valer" (pegadinha 13).

## 1b. Decisões do item 2 (opção D, aprovada pelo usuário em 24/10/2026; detalhes pelo arquiteto)

Motivo do usuário: a planilha e o TCC definem o setor "sem contar a própria ação".

- **DS10 Série nova no `series_diarias`:** `ticker = "SETOR_SEM:<TICKER>"` (ex.: `SETOR_SEM:PETR4`),
  `tipo = "setor_sem_empresa"` (valor novo no enum `tipo`), `nome = "<setor> sem <empresa>"` (empresa do
  cadastro; sem ela, o ticker; ex.: "Petróleo, Gás e Biocombustíveis sem Petrobras"), campos
  `indice_retorno_total` e `n_empresas` (iguais aos do antigo tipo `setor`: `n_empresas` inteiro e sem status;
  `status` em trechos `{de, ate, status}` só no índice). Nenhum campo novo no registro: a chave da série já é o
  `ticker`, e a interface acha a série da ação X por `"SETOR_SEM:" + X`.
  - **Quem tem série:** cada ticker do painel (`tickers_do_painel`, BDR inclusive) com pelo menos uma outra
    empresa no setor que tenha preço em algum dia até t.
  - **Membros:** as ações ON/PN/UNIT (`pares_do_painel`) do mesmo setor, **sem nenhuma ação do mesmo CNPJ**
    (PETR3 sai da série da PETR4; regra `_outros_do_setor` com `fase1.setor_excluir`, hoje "empresa"); ticker
    sem CNPJ é empresa à parte; BDR nunca é membro.
  - **Conta:** a mesma da S5 sobre esses membros: retorno do dia (preço no dia e no pregão anterior, sem os
    suspeitos do DS3); média das ações de cada empresa; média igual entre empresas; encadeada em base 100 no
    1º pregão com preço de algum membro. Dia sem nenhuma outra empresa com retorno: ponto vazio
    (`indisponivel`, trecho no índice) e a cadeia segue do último valor; `n_empresas` = empresas que contaram.
  - Janela de 253 pregões e âncora fixa, como as outras séries (S19).
- **DS11 Tabela = razão da série:** `resumo_acao.rentabilidade.setor.{d1,m1,m6,a1}` =
  `N(t) / N(base) - 1`, com N = índice `SETOR_SEM:<ticker>` e base as-of em t-n (a conta da `variacao`).
  Gráfico e tabela batem por construção. Status:
  - sem setor, ou nenhuma outra empresa no setor (só a própria, mesmo com várias classes) → `indisponivel`, sem série;
  - há outras empresas, mas nenhuma com preço até t → `historico_insuficiente`, sem série;
  - ponto de t vazio (nenhuma outra empresa com retorno em t) → `indisponivel`;
  - base antes do início da série → `historico_insuficiente`.
  Muda o significado: média por empresa encadeada, não mais a mediana das rentabilidades da janela (a mediana
  continua nos indicadores de valor: P/L, P/VP, ROE, yield, payout, margens, endividamento; DS5 vale para P/L,
  P/VP e yield). Tabela nova × atual no pacote, |diferença| em pontos percentuais (mediana / p90 / máx, 85
  ações): m1 2,1 / 11,3 / 13,6; m6 3,2 / 6,3 / 11,7; a1 4,7 / 25,9 / 39,5. **Caso real PETR4 6 meses:
  +9,62% na linha e na tabela** (+9,6232%; hoje +11,92% na linha `SETOR:` e +4,61% na tabela). PETR4 m1
  +17,11% (hoje 17,94%), a1 +36,64% (hoje 43,15%); `n_empresas` 7 em t.
- **DS12 BDR:** tem a sua série e a sua `rentabilidade.setor` (como hoje: JBSS32 m6 = 15,04% com `ok`), mas
  nunca entra na série de outra ação.
- **DS13 "Quando muda":** nada novo no código: `comparar_series` trata as séries novas como as outras (chave
  `ticker`). Ponto novo → só o ponto; ponto antigo mudou (empresa entrou ou saiu do setor, CNPJ mudou, coleta
  corrigiu um preço passado, histórico estendido) → série inteira com `substituir_serie: true`; série que sumiu
  (ação saiu do painel, ou o setor ficou só com ela) → `removidos`. Dividendo não muda os pontos anteriores à
  data-ex (a série usa retornos diários, como a S5).
- **DS14 Tamanho e tempo** (medidos com o pacote de 23/10 e com 85 ações × 1.260 pregões sintéticos):
  +85 séries = 826.708 bytes na carga completa (+0,83 MB) e 33.934 bytes por dia no envio diário. Sem as 10
  `SETOR:` (96.655 bytes), o `series_diarias.json` de 23/10 iria de 2,34 MB para ~3,07 MB. Tempo: 0,13 s para
  as 85 séries com 5 anos; ~0,5 s com a rentabilidade; a conta roda 2 vezes por rodada (pacote e resumo): < 1,5 s.
- **DS15 A série `SETOR:<nome>` (todas as empresas) sai do pacote** (recomendação do arquiteto; confirmar
  com o usuário). Para que ainda serviria: uma futura "página do setor" sem ação escolhida; nenhuma das 23
  informações da planilha usa. Manter custa pouco em tamanho (97 KB na carga, ~4 KB/dia) e nada em código,
  mas deixa duas linhas "setor" diferentes no contrato (a mesma confusão que o usuário apontou) e exige
  explicar as duas na especificação. Tirar custa: trocar o tipo `setor` por `setor_sem_empresa` no
  `contrato.CAMPOS_SERIE`, refazer um bloco do teste de gabarito (`tests/test_saida_series.py`, linhas 110-112 e
  159-176) e a interface deixar de usar `SETOR:` (ela já precisa mudar para `SETOR_SEM:`). No próximo envio
  diário as `SETOR:` vão em `removidos` sozinhas (o estado as tem e `comparar_series` as dá como sumidas).
  A função `indice_setor` fica no código (o núcleo dela é reusado pela série nova) com os seus testes.
- `versao_contrato` continua "1.0" (contrato ainda não está em uso, como em R9).

---
## 2. Regras do projeto que valem em TODAS as fases (copiar no despacho)

- Projeto em `C:/Users/danie/Desktop/TCC/Arquivos/processamento-tcc`, Python 3.12, `./.venv/Scripts/python.exe`.
  Responder em português. Não fazer commits.
- **Banco da coleta é só leitura e o usuário do `.env` TEM permissão de escrita:** não conectar no
  banco, não ler o `.env`, não rodar `python -m processamento.diagnostico`, `python -m processamento.saida`
  nem `python -m processamento.rotina`. Nada de SQL fora de `fontes.executar_leitura` (o diagnóstico lê
  só por `fontes.ler_tabela`). Testes não usam rede nem banco real (só `banco_teste` do conftest,
  SQLite em memória).
- Não mexer em `extracao-dados-tcc-main/` (só consulta) nem importar `tcc_scraper`.
- **Ausência = NaN/None + `status`, nunca 0.** Na `Grade`, valor é NaN sse status != "ok".
- **YAML:** números sem aspas (`-0.75`, `1.0`, `21`); textos, datas e "ON"/"PN" entre aspas.
- **pandas 3 (Copy-on-Write):** nada de atribuição encadeada (`df[c][i] = x`); use `.loc`, `mask`,
  `where` (devolvem cópia); `reindex(..., fill_value=False)` para máscaras booleanas.
- Funções de `fatos/` e `saida/pacote_*.py` são puras (DataFrames entram e saem; sem I/O).
- Não inventar gabarito: os valores esperados estão abaixo. Se um teste não bater, reportar o valor
  obtido em vez de mudar o esperado.
- Pronto = `./.venv/Scripts/python.exe -m pytest -q` sem falhas.

---


## 3. Ordem e paralelismo

- **Fase 1** primeiro, sozinha. **Fase 2** (núcleo da série nova em `fatos/series.py`) logo depois, sozinha.
- Depois da Fase 2: **Fases 3, 4 e 5 em paralelo** (arquivos disjuntos).
- **Fase 6** (especificação) pode rodar em paralelo com qualquer outra (só `.md`).
- Verificação final: `pytest -q` com tudo junto.

| Fase | O quê | Arquivos | Depende de |
|---|---|---|---|
| 1 | parâmetros e funções de suspeito | `processamento/config/parametros.yaml`, `processamento/fatos/precos.py`, `tests/test_fatos_suspeitos.py` (novo), `tests/test_fatos_parametros.py` | - |
| 2 | núcleo: série sem a própria e a sua rentabilidade | `processamento/fatos/series.py`, `tests/test_fatos_series.py` | 1 |
| 3 | pacote `series_diarias`, contrato, aviso | `processamento/saida/pacote_series.py`, `processamento/saida/contrato.py`, `processamento/saida/gerar.py`, `tests/test_saida_series.py`, `tests/test_saida_gerar.py` | 2 |
| 4 | `resumo_acao`: rentabilidade do setor e medianas de nível | `processamento/fatos/precos.py` (só `calcular_precos`), `processamento/fatos/fundamentos.py`, `processamento/saida/pacotes_fatos.py`, `tests/test_setor_suspeitos.py` (novo) | 2 |
| 5 | diagnóstico | `processamento/diagnostico/temas.py`, `processamento/diagnostico/__main__.py`, `tests/test_diagnostico_temas.py` | 1 |
| 6 | especificação | `ESPECIFICACAO.md` | - |

A Fase 5 só precisa da Fase 1 (pode começar junto com a 2). Fases 1 e 4 mexem no mesmo `precos.py`, por isso a 4
só começa depois da 1.

---

## 4. Fases do implementador

### Fase 1: parâmetros e funções puras (`fatos/precos.py`)

**1.1 `processamento/config/parametros.yaml`**, bloco `fase1`, logo depois da linha
`  setor_excluir: "empresa"  # ...`:
```yaml
  retorno_suspeito_min: -0.75          # retorno diário (fechamento_ajustado, contra o último preço) abaixo disto = suspeito (erro da coleta; seção 6)
  retorno_suspeito_max: 1.0            # acima disto = suspeito (ex.: AZUL3 com 30.599.848 de 09/04 a 17/04/2026)
  retorno_suspeito_pregoes_nivel: 21   # P/L, P/VP e yield: empresa fora das medianas do setor se teve retorno suspeito nos últimos N pregões até t
```

**1.2 `processamento/fatos/precos.py`**
- `_CHAVES_FASE1` (linha 23): acrescentar `"retorno_suspeito_min"`, `"retorno_suspeito_max"`,
  `"retorno_suspeito_pregoes_nivel"`.
- `ParametrosPrecos` (linha 40): acrescentar NO FIM, com padrão:
  ```python
      retorno_suspeito_min: float = -0.75
      retorno_suspeito_max: float = 1.0
      retorno_suspeito_pregoes_nivel: int = 21
  ```
- Depois de `_inteiro_positivo` (linha 52), função nova:
  ```python
  def _numero(valor: object, onde: str) -> float:
      """Confere um número finito (bool não conta); levanta `ErroParametrosPrecos` se não bater."""
      if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not np.isfinite(valor):
          raise ErroParametrosPrecos(f"{onde} deve ser um número (recebeu {valor!r})")
      return float(valor)
  ```
- Em `carregar_parametros_precos`, antes de `params = ParametrosPrecos(`:
  ```python
      minimo = _numero(bloco["retorno_suspeito_min"], "fase1.retorno_suspeito_min")
      if not -1 < minimo < 0:
          raise ErroParametrosPrecos(f"fase1.retorno_suspeito_min deve ficar entre -1 e 0 (recebeu {minimo!r})")
      maximo = _numero(bloco["retorno_suspeito_max"], "fase1.retorno_suspeito_max")
      if not maximo > 0:
          raise ErroParametrosPrecos(f"fase1.retorno_suspeito_max deve ser maior que zero (recebeu {maximo!r})")
  ```
  e no `ParametrosPrecos(...)` acrescentar `retorno_suspeito_min=minimo, retorno_suspeito_max=maximo,` e
  `retorno_suspeito_pregoes_nivel=_inteiro_positivo(bloco["retorno_suspeito_pregoes_nivel"], "fase1.retorno_suspeito_pregoes_nivel"),`.
- Logo depois de `retornos_diarios` (linhas 145-147), três funções novas:
  ```python
  def retornos_asof(g: pd.DataFrame) -> pd.DataFrame:
      """Retorno do dia contra o último preço anterior com valor (base as-of); NaN onde g(t) é NaN."""
      return g / g.ffill().shift(1) - 1


  def retornos_suspeitos(g_aj: pd.DataFrame, minimo: float, maximo: float) -> pd.DataFrame:
      """True onde o retorno as-of do dia é < `minimo` ou > `maximo` (estrito; NaN nunca é suspeito).

      Erro da coleta (seção 6, "Retorno diário suspeito"): o preço não é corrigido, só isolado
      (fora das séries e das medianas do setor).
      """
      r = retornos_asof(g_aj)
      return (r < minimo) | (r > maximo)


  def suspeita_na_janela(suspeitos: pd.DataFrame, n: int) -> pd.DataFrame:
      """True em t se houve retorno suspeito em algum dos `n` pregões até t, inclusive: o intervalo (t-n, t]."""
      return suspeitos.astype(float).rolling(n, min_periods=1).max() > 0
  ```
- Depois de `pares_do_painel` (linhas 305-310), função nova:
  ```python
  def tickers_com_suspeita(precos: pd.DataFrame, cal: list, t, tickers: list[str], minimo: float,
                           maximo: float, n: int) -> set[str]:
      """Tickers com retorno suspeito (fechamento_ajustado) em algum dos `n` pregões até t.

      `ValueError` se t não é pregão de `cal`. Só olha preços até t (sem vazamento).
      """
      ts = pd.Timestamp(t).normalize()
      g = grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
      if ts not in g.index:
          raise ValueError(f"{t} não é pregão")
      linha = suspeita_na_janela(retornos_suspeitos(g, minimo, maximo), n).loc[ts]
      return {tk for tk, v in linha.items() if bool(v)}
  ```

**1.3 Testes**

`tests/test_fatos_parametros.py`:
- em `test_yaml_real_traz_o_bloco_fase1` acrescentar `assert params.retorno_suspeito_min == -0.75`,
  `assert params.retorno_suspeito_max == 1.0`, `assert params.retorno_suspeito_pregoes_nivel == 21`;
- na lista do `@pytest.mark.parametrize` de `test_parametros_invalidos_levantam_erro` acrescentar:
  ```python
  (lambda d: d["fase1"].__setitem__("retorno_suspeito_min", 0.1), "fase1.retorno_suspeito_min"),
  (lambda d: d["fase1"].__setitem__("retorno_suspeito_min", True), "fase1.retorno_suspeito_min"),
  (lambda d: d["fase1"].__setitem__("retorno_suspeito_max", -1.0), "fase1.retorno_suspeito_max"),
  (lambda d: d["fase1"].__setitem__("retorno_suspeito_pregoes_nivel", 0), "fase1.retorno_suspeito_pregoes_nivel"),
  (lambda d: d["fase1"].pop("retorno_suspeito_max"), "faltam chaves"),
  ```

`tests/test_fatos_suspeitos.py` (novo), dados da fábrica:
```python
from datetime import date
import pandas as pd
import pytest
from fabrica_precos import precos_de, pregoes_uteis
from processamento.fatos.precos import (grade_de_precos, retornos_asof, retornos_diarios,
                                        retornos_suspeitos, suspeita_na_janela, tickers_com_suspeita)

CAL = pregoes_uteis(6, "2026-04-06")   # 06, 07, 08, 09, 10 e 13/04/2026
AZUL = [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0]   # bug x20000 em 08 e 09/04
GAPX = [10.0, None, 25.0, 25.0, 25.0, 25.0]                  # salto escondido atrás de um dia sem preço
LIMI = [100.0, 25.0, 50.0, 100.0, 24.99, 50.0]               # limites exatos
TICKERS = ["AZUL3", "GAPX3", "LIMI3"]
PRECOS = pd.concat([precos_de("AZUL3", CAL, AZUL), precos_de("GAPX3", CAL, GAPX), precos_de("LIMI3", CAL, LIMI)])
G = grade_de_precos(PRECOS, CAL, "fechamento_ajustado", TICKERS)
S = retornos_suspeitos(G, -0.75, 1.0)
```
Gabarito (conferido; T = True, F = False; compare com `.tolist()`, NaN com `pd.isna`, números com
`pytest.approx(..., rel=1e-12)`):

| caso | chamada | esperado |
|---|---|---|
| 1a | `retornos_asof(G)["AZUL3"]` | `[nan, 0.020000000000000018, 19999.0, 0.050000000000000044, -0.9999509803921569, 0.0]` |
| 1b | `retornos_asof(G)["GAPX3"]` | `[nan, nan, 1.5, 0.0, 0.0, 0.0]`; e `retornos_diarios(G)["GAPX3"].iloc[2]` é NaN (por isso a base as-of) |
| 1c | `retornos_asof(G)["LIMI3"]` | `[nan, -0.75, 1.0, 1.0, -0.7501, 1.0008003201280515]` |
| 1d | `S` por coluna | AZUL3 `[F,F,T,F,T,F]`; GAPX3 `[F,F,T,F,F,F]`; LIMI3 `[F,F,F,F,T,T]` (-75% e +100% exatos não são suspeitos) |
| 1e | `suspeita_na_janela(S, 1)` | igual a 1d |
| 1f | `suspeita_na_janela(S, 2)` | AZUL3 `[F,F,T,T,T,T]`; GAPX3 `[F,F,T,T,F,F]`; LIMI3 `[F,F,F,F,T,T]` |
| 1g | `suspeita_na_janela(S, 3)` | AZUL3 `[F,F,T,T,T,T]`; GAPX3 `[F,F,T,T,T,F]`; LIMI3 `[F,F,F,F,T,T]` |
| 1h | `tickers_com_suspeita(PRECOS, CAL, date(2026,4,13), TICKERS, -0.75, 1.0, n)` | n=1 `{"LIMI3"}`; n=2 `{"AZUL3","LIMI3"}`; n=4 `{"AZUL3","GAPX3","LIMI3"}` |
| 1i | idem com `date(2026,4,7)`, n=21 | `set()` |
| 1j | idem com `date(2026,4,4)` (sábado) | `pytest.raises(ValueError)` |
| 1k | sem vazamento | `PRECOS` cortado em `data <= 2026-04-09` e `CAL[:4]`, t = 09/04, n=1: `set()`; com os preços inteiros e o mesmo t: também `set()` |

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_fatos_suspeitos.py tests/test_fatos_parametros.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.


---

### Fase 2: núcleo da série "setor sem a própria empresa" (`fatos/series.py`; depois da Fase 1)

**2.1 `processamento/fatos/series.py`**
- Imports: acrescentar `HIST`, `_outros_do_setor` e `variacao` ao `from processamento.fatos.precos import (...)`.
- Constante: `PREFIXO_SEM = "SETOR_SEM:"  # série do setor sem a própria empresa, uma por ticker (DS10)`.
- Extrair o miolo de `indice_setor` (linhas 148-172) em duas funções privadas, sem mudar o resultado:
  ```python
  def _retornos_dos_membros(g_aj: pd.DataFrame, membros: list[str], suspeitos: pd.DataFrame | None) -> pd.DataFrame:
      """Retorno do dia de cada membro (`retornos_diarios`); com `suspeitos`, o retorno suspeito do dia vira NaN (seção 6)."""
      ret = retornos_diarios(g_aj[membros])
      if suspeitos is not None:
          fora = suspeitos.reindex(index=ret.index, columns=ret.columns, fill_value=False).astype(bool)
          ret = ret.mask(fora)
      return ret


  def _cadeia(ret: pd.DataFrame, g_aj: pd.DataFrame, membros: list[str],
              cnpj_de: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
      """(nível, status, n_empresas) da média igual por empresa dos retornos de `membros`, em base 100.

      Início = 1º pregão com preço de algum membro (nível 100). Dia sem nenhuma empresa com retorno:
      `indisponivel` e a cadeia segue do último nível. None se nenhum membro tem preço.
      """
      # corpo = o que hoje está dentro do `for setor in ...` de indice_setor, das linhas
      # `existe = ...` até montar `nivel`, `st` e `cont` (trocar `continue` por `return None`)
  ```
  `indice_setor(g_aj, cadastro, pares)` continua com a mesma assinatura e o mesmo resultado; passa a chamar
  `ret = _retornos_dos_membros(g_aj, membros_todos, None)` e `_cadeia(ret, g_aj, membros, cnpj_de)` por setor
  (setor com `None` não aparece). Ela sai do pacote (DS15), mas fica como núcleo testado.
- Funções novas, depois de `indice_setor`:
  ```python
  def indice_setor_sem_empresa(g_aj: pd.DataFrame, cadastro: pd.DataFrame, pares: list[str], tickers: list[str],
                               modo: str, suspeitos: pd.DataFrame | None = None) -> tuple[Grade, pd.DataFrame]:
      """Série `SETOR_SEM:<ticker>` de cada ticker: índice base 100 do setor dele sem a própria empresa (DS10).

      Membros: `pares` do mesmo setor sem o próprio ticker e, no modo "empresa", sem nenhuma ação do mesmo CNPJ
      (`fatos.precos._outros_do_setor`). Conta de `_cadeia` (média igual por empresa dos retornos diários, sem os
      suspeitos). Ticker sem outro membro, ou cujos membros nunca têm preço, não ganha coluna.
      Devolve (grade com colunas `SETOR_SEM:<ticker>`, n_empresas com as mesmas colunas).
      """
      setor_de, cnpj_de = mapas_cadastro(cadastro)
      validos = [p for p in pares if p in g_aj.columns]
      ret = _retornos_dos_membros(g_aj, validos, suspeitos)
      valor, status, contagem = {}, {}, {}
      for tk in tickers:
          outros = _outros_do_setor(tk, validos, setor_de, cnpj_de, modo)
          if not outros:
              continue
          cadeia = _cadeia(ret, g_aj, outros, cnpj_de)
          if cadeia is None:
              continue
          nome = f"{PREFIXO_SEM}{tk}"
          valor[nome], status[nome], contagem[nome] = cadeia
      idx, cols = g_aj.index, list(valor)
      return (montar_grade(pd.DataFrame(valor, index=idx, columns=cols), pd.DataFrame(status, index=idx, columns=cols)),
              pd.DataFrame(contagem, index=idx, columns=cols))


  def rentabilidade_setor_sem_empresa(g_aj: pd.DataFrame, cadastro: pd.DataFrame, pares: list[str], tickers: list[str],
                                      janelas: dict[str, int], modo: str,
                                      suspeitos: pd.DataFrame | None = None) -> dict[str, Grade]:
      """`rentabilidade.setor` por janela (chave = nome da janela; colunas = `tickers`): razão da série (DS11).

      N(t)/N(base) − 1 pela `variacao` (base as-of). Sem outro membro no setor: `indisponivel`; membros sem
      nenhum preço: `historico_insuficiente`; ponto de t vazio: `indisponivel`; base antes do início: HIST.
      """
      setor_de, cnpj_de = mapas_cadastro(cadastro)
      validos = [p for p in pares if p in g_aj.columns]
      serie, _ = indice_setor_sem_empresa(g_aj, cadastro, pares, tickers, modo, suspeitos)
      idx = g_aj.index
      res = {}
      for nome_janela, n in janelas.items():
          valor, status = {}, {}
          for tk in tickers:
              col = f"{PREFIXO_SEM}{tk}"
              if col in serie.valor.columns:
                  v = variacao(serie.valor[[col]], n)
                  valor[tk], status[tk] = v.valor[col], v.status[col]
              else:
                  tem_outros = bool(_outros_do_setor(tk, validos, setor_de, cnpj_de, modo))
                  valor[tk] = pd.Series(np.nan, index=idx)
                  status[tk] = pd.Series(HIST if tem_outros else INDISPONIVEL, index=idx, dtype=object)
          res[nome_janela] = montar_grade(pd.DataFrame(valor, index=idx, columns=tickers),
                                          pd.DataFrame(status, index=idx, columns=tickers))
      return res
  ```

**2.2 Testes** (`tests/test_fatos_series.py`; acrescentar `serie_por_retornos` ao import de `fabrica_precos` e
`indice_setor_sem_empresa`, `rentabilidade_setor_sem_empresa` ao de `processamento.fatos.series`; os testes atuais
de `indice_setor` têm de continuar passando sem mudança).

Caso 2a: membros, outras classes da mesma empresa, BDR e ação sem setor (dias `PREFIXO`, preços de
`_precos_setor_s` + extras):
```python
precos = pd.concat([_precos_setor_s(),
                    precos_de("BDRX34", PREFIXO, [1.0, 100.0, 1.0, 100.0, 1.0]),
                    precos_de("XXXX3", PREFIXO, [5.0, 6.0, 7.0, 8.0, 9.0]),
                    precos_de("ZZZZ3", PREFIXO, [10.0, 11.0, None, 12.1, 12.1])])
cadastro = _cadastro_setor_s(extra=[("BDRX34", "5", "S", "BDR"), ("XXXX3", "7", None, "ON"), ("ZZZZ3", "9", "Z", "ON")])
tickers = ["AAAA3", "BBBB3", "BDRX34", "CCCC3", "CCCC4", "XXXX3", "ZZZZ3"]
pares = ["AAAA3", "BBBB3", "CCCC3", "CCCC4", "XXXX3", "ZZZZ3"]          # como pares_do_painel: sem BDR
g_aj = _g_aj(precos, PREFIXO, tickers)
g, n = indice_setor_sem_empresa(g_aj, cadastro, pares, tickers, "empresa")
```
Esperado (conferido: cada coluna = `indice_setor` atual sobre os outros membros):

| coluna | valor | n_empresas |
|---|---|---|
| `SETOR_SEM:AAAA3` (B + empresa C) | `[100.0, 98.5, 99.485, 98.49015000000001, 100.95240375]` | `[0, 2, 1, 1, 2]` |
| `SETOR_SEM:BBBB3` (A + C) | `[100.0, 103.50000000000001, 102.9825, 103.49741250000001, 105.56736075]` | `[0, 2, 2, 2, 2]` |
| `SETOR_SEM:BDRX34` (A + B + C = setor inteiro) | `[100.0, 100.66666666666666, 100.16333333333331, 100.66414999999999, 102.677433]` (= `SETOR_S`) | `[0, 3, 2, 2, 3]` |
| `SETOR_SEM:CCCC3` (A + B; CCCC4 também sai) | `[100.0, 100.0, 97.99999999999999, 99.96, 101.4594]` | `[0, 2, 1, 1, 2]` |
| `SETOR_SEM:CCCC4` (A + B; CCCC3 também sai) | igual à CCCC3 | `[0, 2, 1, 1, 2]` |

`list(g.valor.columns) == ["SETOR_SEM:AAAA3", "SETOR_SEM:BBBB3", "SETOR_SEM:BDRX34", "SETOR_SEM:CCCC3", "SETOR_SEM:CCCC4"]`
(XXXX3 sem setor e ZZZZ3 sozinha no setor Z não ganham série; a BDR nunca é membro); todos os status `OK`.
Modo "acao" (`indice_setor_sem_empresa(..., "acao")`): `SETOR_SEM:CCCC4` = `[100.0, 100.66666666666666, 100.16333333333331, 100.66414999999999, 102.677433]`, n `[0, 3, 2, 2, 3]` (a CCCC3 entra).

Caso 2b: dia sem nenhuma outra empresa (setor Z com YYYY3 e ZZZZ3):
`precos = pd.concat([precos_de("YYYY3", PREFIXO, [10.0, 11.0, None, 12.1, 12.1]), precos_de("ZZZZ3", PREFIXO, [5.0] * 5)])`,
cadastro `[("YYYY3", "8", "Z", "ON"), ("ZZZZ3", "9", "Z", "ON")]`, pares = tickers = `["YYYY3", "ZZZZ3"]`:
- `SETOR_SEM:ZZZZ3` = `[100.0, 110.00000000000001, nan, nan, 110.00000000000001]`, status `[OK, OK, INDISPONIVEL, INDISPONIVEL, OK]`, n `[0, 1, 0, 0, 1]`;
- `SETOR_SEM:YYYY3` = `[100.0] * 5`, status `[OK] * 5`, n `[0, 1, 1, 1, 1]`;
- `rentabilidade_setor_sem_empresa(..., {"d1": 1}, "empresa")["d1"]` da ZZZZ3: valor `[nan, 0.10000000000000009, nan, nan, 0.0]`,
  status `[HIST, OK, INDISPONIVEL, INDISPONIVEL, OK]` (no último dia a base as-of é o 110 do 2º pregão).

Caso 2c: retornos suspeitos (dados da AZUL3; DS3 na série nova):
```python
cal = pregoes_uteis(8, "2026-04-06")   # 06, 07, 08, 09, 10, 13, 14 e 15/04/2026
precos = pd.concat([
    precos_de("AZUL3", cal, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105]),
    precos_de("EMBR3", cal, serie_por_retornos(50.0, [0.02, -0.01, 0.02, -0.01, 0.01, 0.0, 0.01])),
    precos_de("WEGE3", cal, serie_por_retornos(40.0, [0.0, 0.01, -0.02, 0.03, 0.0, 0.01, -0.01])),
    precos_de("RAIL3", cal, serie_por_retornos(20.0, [0.03, 0.0, -0.01, 0.02, 0.01, -0.02, 0.0])),
    precos_de("SOLO3", cal, [10.0] * 8),
])
cadastro = cadastro_de([("AZUL3", "1", "BI", "ON"), ("EMBR3", "2", "BI", "ON"), ("WEGE3", "3", "BI", "ON"),
                        ("RAIL3", "4", "BI", "ON"), ("SOLO3", "5", "Y", "ON"), ("NOPX3", "6", "Y", "ON")])
tickers = ["AZUL3", "EMBR3", "NOPX3", "RAIL3", "SOLO3", "WEGE3"]   # NOPX3 está no cadastro mas não tem preço
g_aj = _g_aj(precos, cal, tickers)
susp = retornos_suspeitos(g_aj, -0.75, 1.0)            # de processamento.fatos.precos (Fase 1)
g, n = indice_setor_sem_empresa(g_aj, cadastro, tickers, tickers, "empresa", suspeitos=susp)
r = rentabilidade_setor_sem_empresa(g_aj, cadastro, tickers, tickers, {"d1": 1, "m1": 3, "m6": 5}, "empresa", suspeitos=susp)
```
Esperado (conferido):
- colunas `["SETOR_SEM:AZUL3", "SETOR_SEM:EMBR3", "SETOR_SEM:NOPX3", "SETOR_SEM:RAIL3", "SETOR_SEM:WEGE3"]`
  (SOLO3 não tem série: o único outro do setor Y, NOPX3, nunca tem preço);
- `SETOR_SEM:EMBR3` = `[100.0, 101.66666666666666, 102.17499999999998, 102.85616666666664, 105.42757083333329, 105.77899606944442, 105.77899606944442, 105.77899606944442]`,
  n `[0, 3, 2, 3, 2, 3, 3, 3]` (a AZUL3 fica fora em 08/04 e 10/04; +5% de 09/04 entra);
  sem `suspeitos` daria `[100.0, 101.66666666666666, 677845.8944444443, 682364.8670740739, 466293.8089200137, 467848.1216164138, 467848.1216164138, 467848.1216164138]`;
- `SETOR_SEM:AZUL3` (não tem a AZUL3, não muda) = `[100.0, 101.66666666666666, 101.66666666666666, 101.32777777777777, 102.67881481481481, 103.36334024691357, 103.01879577942385, 103.01879577942385]`, n `[0, 3, 3, 3, 3, 3, 3, 3]`;
- `r["d1"]` EMBR3: `[nan, 0.016666666666666607, 0.004999999999999893, 0.006666666666666599, 0.02499999999999991, 0.0033333333333334103, 0.0, 0.0]`, status `[HIST] + [OK] * 7`;
- `r["m1"]` EMBR3: `[nan, nan, nan, 0.028561666666666374, 0.03699249999999976, 0.03527277777777771, 0.028416666666666757, 0.0033333333333334103]`, status `[HIST] * 3 + [OK] * 5`;
- `r["m6"]` EMBR3: `[nan] * 5 + [0.05778996069444409, 0.04044914166666658, 0.03527277777777771]`, status `[HIST] * 5 + [OK] * 3`;
- `r["d1"]` SOLO3: último status `HIST`; NOPX3: último status `OK` (a série dela é a da SOLO3).

Caso 2d: tabela = razão da série. Para cada coluna `SETOR_SEM:<tk>` do caso 2c,
`r["m1"].valor[tk].iloc[-1] == pytest.approx(g.valor[col].iloc[-1] / g.valor[col].iloc[-4] - 1)` e
`r["m6"].valor[tk].iloc[-1] == pytest.approx(g.valor[col].iloc[-1] / g.valor[col].iloc[-6] - 1)`.

Caso 2e: sem vazamento. `indice_setor_sem_empresa(g_aj.iloc[:3], ...)` do caso 2a dá os mesmos 3 primeiros pontos
de `SETOR_SEM:AAAA3` que o cálculo com os 5 dias.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_fatos_series.py` e depois
`./.venv/Scripts/python.exe -m pytest -q`.

---

### Fase 3: pacote `series_diarias`, contrato e aviso (depois da Fase 2)

**3.1 `processamento/saida/contrato.py`**, `CAMPOS_SERIE` (linha 42-44): trocar a entrada
`"setor": ("indice_retorno_total", "n_empresas")` por `"setor_sem_empresa": ("indice_retorno_total", "n_empresas")`
(o resto do `validar_serie` já trata `n_empresas` pelo nome do campo).

**3.2 `processamento/saida/pacote_series.py`**
- Imports: de `processamento.fatos.precos` acrescentar `ParametrosPrecos`, `carregar_parametros_precos`,
  `mapas_cadastro`, `retornos_suspeitos`; de `processamento.fatos.series` trocar `indice_setor` por
  `PREFIXO_SEM, indice_setor_sem_empresa`; e `from processamento.experimento.relatorio import pct`.
- `series_completas(ins, multiplos, params_precos: ParametrosPrecos | None = None)`: no começo,
  `params_precos = carregar_parametros_precos() if params_precos is None else params_precos`.
  Trocar a linha 132 (`setor, n_setor = indice_setor(g_aj_bruto, ins.cadastro, pares)`) por:
  ```python
      suspeitos = retornos_suspeitos(g_aj_bruto, params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max)
      sem, n_sem = indice_setor_sem_empresa(g_aj_bruto, ins.cadastro, pares, tickers, params_precos.setor_excluir,
                                            suspeitos=suspeitos)
      setor_de = mapas_cadastro(ins.cadastro)[0]
  ```
  e trocar o último laço (linhas 173-178, as séries `SETOR:`) por:
  ```python
      for col in sem.valor.columns:   # DS10: uma série "setor sem a própria empresa" por ticker
          tk = col.removeprefix(PREFIXO_SEM)
          campos = {
              "indice_retorno_total": _coluna(sem, col),
              "n_empresas": (n_sem[col].to_numpy(dtype=float), None),
          }
          nome = f"{setor_de.get(tk)} sem {nomes.get(tk, tk)}"
          guarda(_serie(col, "setor_sem_empresa", nome, campos, datas_pregao, ini, t))
  ```
  A série da própria ação continua com `base_aj` sem máscara (DS6). Atualizar o docstring do módulo/função:
  "séries `SETOR_SEM:<ticker>` (DS10) no lugar das `SETOR:<nome>`".
- `montar_series_diarias(ins, multiplos, estado, gerado_em, dados_ate, params_precos: ParametrosPrecos | None = None)`
  repassa `params_precos` a `series_completas`.
- Constantes e função nova (logo depois de `inicio_janela`):
  ```python
  AVISO_SUSPEITOS = ("Retornos diários suspeitos (abaixo de {minimo} ou acima de {maximo}) entre {ini} e {t}, "
                     "fora das séries e das medianas do setor: {lista}.")
  MAX_TICKERS_AVISO = 10


  def aviso_retornos_suspeitos(ins: Insumos, params_precos: ParametrosPrecos) -> str | None:
      """Aviso do `execucao` (seção 6): retornos suspeitos das ações ON/PN/UNIT com data em [inicio_janela, t].

      None se não houver. Mais de `MAX_TICKERS_AVISO` tickers: os primeiros e "e mais k".
      """
      pares = pares_do_painel(ins.cadastro, ins.exclusoes)
      g = grade_de_precos(ins.precos, ins.cal, "fechamento_ajustado", pares)
      susp = retornos_suspeitos(g, params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max)
      ini = inicio_janela(ins.cal, ins.t)
      dentro = (susp.index >= pd.Timestamp(ini)) & (susp.index <= pd.Timestamp(ins.t))
      janela = susp[dentro]
      itens = []
      for tk in sorted(janela.columns):
          dias = [d.strftime("%Y-%m-%d") for d in janela.index[janela[tk].to_numpy()]]
          if dias:
              itens.append(f"{tk} ({', '.join(dias)})")
      if not itens:
          return None
      lista = ", ".join(itens[:MAX_TICKERS_AVISO])
      if len(itens) > MAX_TICKERS_AVISO:
          lista += f" e mais {len(itens) - MAX_TICKERS_AVISO}"
      return AVISO_SUSPEITOS.format(minimo=pct(params_precos.retorno_suspeito_min, 0),
                                    maximo=pct(params_precos.retorno_suspeito_max, 0),
                                    ini=ini.isoformat(), t=ins.t.isoformat(), lista=lista)
  ```
  (`pct(-0.75, 0)` = "-75%" e `pct(1.0, 0)` = "100%", conferido.)

**3.3 `processamento/saida/gerar.py`**
- Constante nova junto das outras (linha ~41):
  `AVISO_SUSPEITOS_FALHA = "falha na checagem de retornos suspeitos ({tipo}): aviso não gerado."`
- Logo depois de `params_exp = carregar_parametros_experimento()` (linha 135):
  ```python
      try:
          aviso_suspeitos = pacote_series.aviso_retornos_suspeitos(ins, params_precos)
      except Exception as erro:
          aviso_suspeitos = AVISO_SUSPEITOS_FALHA.format(tipo=type(erro).__name__)
      if aviso_suspeitos is not None:
          avisos.append(aviso_suspeitos)
  ```
- Em `series()` (linhas 177-178): passar `params_precos=params_precos` a `montar_series_diarias`.

**3.4 Testes**

Caso 3a (`tests/test_saida_series.py`, `test_gabarito_e2e_formato_compacto`): no banco de teste todo setor tem
uma empresa só (PETR3 e PETR4 são a mesma), então **não há série de setor**. Trocar as linhas 110-112 por
```python
    assert {"PETR4", "TAEE11", "NOVA3", "IBOV", "IDIV", "CDI", "IPCA"} <= set(a)
    assert not any(k.startswith("SETOR") for k in a)   # DS10/DS15: sem SETOR: e sem SETOR_SEM: (setores de 1 empresa)
    for ausente in ("ITUB4", "IVVB11", "SMLL", "IFIX", "CRFB3"):
        assert ausente not in a
```
e apagar o bloco das linhas 159-176 (`petro = a["SETOR:Petroleo"]` até o assert da `bebidas`).

Caso 3b (`tests/test_saida_contrato.py`): nos casos `i_n_empresas_com_status` e `i_n_empresas_nulo` (linhas 292 e
300) trocar `"setor"` por `"setor_sem_empresa"`. Teste novo: o registro do caso `i_n_empresas_nulo` com
`n_empresas = [0, 1, 1, 1]` e `tipo = "setor_sem_empresa"` passa no `contrato.validar_serie`; com `tipo = "setor"`
é recusado (`ErroContrato`).

Caso 3c (`tests/test_saida_series.py`, teste novo `test_series_setor_sem_a_propria`): Insumos montado como
`_ins_sintetico`, com IBOV `[10.0] * 8` e as 4 ações do caso 2c da Fase 2 (AZUL3, EMBR3, WEGE3, RAIL3, mesmos
preços e `cal = pregoes_uteis(8, "2026-04-06")`; cadastro `cadastro_de([("AZUL3", "1", "BI", "ON"), ("EMBR3", "2", "BI", "ON"), ("WEGE3", "3", "BI", "ON"), ("RAIL3", "4", "BI", "ON")])`;
`d = cal[-1] + timedelta(days=1)`). `a = series_completas(ins, _multiplos(ins))`:
- `sorted(k for k in a if k.startswith("SETOR"))` == `["SETOR_SEM:AZUL3", "SETOR_SEM:EMBR3", "SETOR_SEM:RAIL3", "SETOR_SEM:WEGE3"]`;
- `a["SETOR_SEM:EMBR3"]`: `tipo == "setor_sem_empresa"`, `nome == "BI sem EMBR3"` (a fábrica usa o ticker como
  empresa), `inicio_janela == "2026-04-06"`, `datas` = os 8 pregões, `valores["indice_retorno_total"]` = a lista
  `SETOR_SEM:EMBR3` do caso 2c, `valores["n_empresas"] == [0, 3, 2, 3, 2, 3, 3, 3]`, `status == {}`;
- `a["AZUL3"]["valores"]["indice_retorno_total"] == [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105]` (DS6);
- `montar_series_diarias(ins, _multiplos(ins), None, GERADO_8, DADOS_ATE_8)` com `GERADO_8 = "2026-04-16T09:00:00-03:00"`
  e `DADOS_ATE_8 = "2026-04-16T08:00:00-03:00"`: todo registro passa em `contrato.validar_serie` e os
  `SETOR_SEM:` vêm com `substituir_serie: True`;
- `aviso_retornos_suspeitos(ins, carregar_parametros_precos())` ==
  `"Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2026-04-06 e 2026-04-15, fora das séries e das medianas do setor: AZUL3 (2026-04-08, 2026-04-10)."`

Caso 3d ("quando muda", `tests/test_saida_series.py`): com o Insumos do caso 3c cortado em 7 pregões como estado
e o de 8 pregões como atual (`comparar_series(atuais, estado)`), a `SETOR_SEM:EMBR3` vai só com a data
`2026-04-15` e `substituir_serie: False`. Trocando o cadastro do atual para pôr a RAIL3 noutro setor ("XX"), a
`SETOR_SEM:EMBR3` vai inteira com `substituir_serie: True` (os pontos antigos mudam) e a `SETOR_SEM:RAIL3` vai
em `removidos` (ficou sozinha no setor XX).

Caso 3e (`tests/test_saida_series.py`): banco de teste com salto na PETR4.
```python
def _salto_petr4(df: pd.DataFrame) -> pd.DataFrame:
    """PETR4 com fechamento_ajustado 1.000.000 em 2025-10-20 (leitor de texto do banco_teste)."""
    df = df.copy()
    m = (df["ticker"] == "PETR4") & (df["data"] == "2025-10-20")
    df.loc[m, "fechamento_ajustado"] = "1000000.0"
    return df
```
`ins = insumos_de_teste(banco_teste({"v1-precos": _salto_petr4}))`:
- `aviso_retornos_suspeitos(ins, carregar_parametros_precos())` ==
  `"Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2025-10-16 e 2025-10-21, fora das séries e das medianas do setor: PETR4 (2025-10-20, 2025-10-21)."`;
- `series_completas(ins, _multiplos(ins))["PETR4"]["valores"]["indice_retorno_total"] == [100.0, 100.0, 10000000.0, 100.0]` (conferido; a série da ação não muda);
- banco de teste sem alteração: `aviso_retornos_suspeitos(...)` é `None`;
- salto antes da janela: `cal = pregoes_uteis(255)`, `aj = [10.0] + [30.0] * 254`, `ins = _ins_sintetico(cal, aj, aj)`
  (salto em `cal[1]`; `inicio_janela` = `cal[2]`): `None`;
- mais de 10 tickers: 12 ações `f"T{i:02d}3"` (i = 1..12; cadastro `(tk, str(i), "S", "ON")`), `cal = pregoes_uteis(3)`,
  preços `[10.0, 30.0, 30.0]` em todas, IBOV `[10.0] * 3`:
  `"Retornos diários suspeitos (abaixo de -75% ou acima de 100%) entre 2025-01-02 e 2025-01-06, fora das séries e das medianas do setor: T013 (2025-01-03), T023 (2025-01-03), T033 (2025-01-03), T043 (2025-01-03), T053 (2025-01-03), T063 (2025-01-03), T073 (2025-01-03), T083 (2025-01-03), T093 (2025-01-03), T103 (2025-01-03) e mais 2."`

Caso 3f (`tests/test_saida_gerar.py`, teste novo; copiar `_salto_petr4`):
`pasta = _gerar(tmp_path, banco_teste({"v1-precos": _salto_petr4}), modelos=modelos_dir)`; `ex = _execucao(pasta)`:
o texto do caso 3e está em `ex["avisos"]`; `ex["status"] == "ok"` (conferido no código atual com esse banco);
nenhum aviso começa com "falha ao gerar".

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_saida_series.py tests/test_saida_contrato.py tests/test_saida_gerar.py tests/test_saida_completo.py tests/test_vazamento_saida.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

---

### Fase 4: `resumo_acao`, rentabilidade do setor e medianas de nível (depois da Fase 2)

**4.1 `processamento/fatos/precos.py`, `calcular_precos` (linha 321)**: a `rentabilidade.setor` passa a sair da
série sem a própria empresa (DS11). Antes do `for nome, n in params.janelas.items():`:
```python
    # import local: fatos/series.py importa este módulo (importar no topo daria importação circular)
    from processamento.fatos.series import rentabilidade_setor_sem_empresa
    suspeitos = retornos_suspeitos(g_aj, params.retorno_suspeito_min, params.retorno_suspeito_max)
    setor_rent = rentabilidade_setor_sem_empresa(g_aj, cadastro, pares, tickers, params.janelas,
                                                 params.setor_excluir, suspeitos=suspeitos)
```
e, dentro do laço, trocar as duas linhas do `res[f"rentabilidade.setor.{nome}"] = media_setor(...)` por
```python
        res[f"rentabilidade.setor.{nome}"] = setor_rent[nome]   # DS11: razão da série SETOR_SEM:<ticker>
```
`res[f"rentabilidade.{nome}"] = rent` continua igual (o valor da própria ação não muda). `media_setor` continua
sendo usada pelos fundamentos e pelo experimento; não apagar.
**4.2 `processamento/fatos/fundamentos.py`**
- Constante nova logo depois de `_SETOR_SEM_FINANCEIRA` (linha 410):
  ```python
  # Campos de setor que usam o preço de t: a empresa com retorno suspeito recente fica fora (seção 6).
  _SETOR_COM_PRECO = frozenset({"pl.setor", "pvp.setor", "dividend_yield.setor"})
  ```
- `calcular_fundamentos_no_dia(t, cal, dados, exclusoes, params, modo_setor, fora_do_setor_preco: frozenset[str] = frozenset())`.
  Docstring: "`fora_do_setor_preco`: tickers com retorno suspeito recente (`fatos.precos.tickers_com_suspeita`);
  a empresa inteira (mesmo CNPJ) sai das medianas de P/L, P/VP e yield. Os valores da própria empresa não mudam."
- Antes do laço `for campo, origem in _ORIGEM_SETOR.items():` (linha 501):
  ```python
      cnpjs_fora = {cnpj_de[k] for k in fora_do_setor_preco if cnpj_de.get(k)}
      excluir = {k for k in tickers
                 if k in fora_do_setor_preco or (cnpj_de.get(k) is not None and cnpj_de.get(k) in cnpjs_fora)}
  ```
  e trocar a linha do `bruta = ...` por:
  ```python
          tira = excluir if campo in _SETOR_COM_PRECO else set()
          bruta = _grade_do_dia(ts, tickers, {k: (_falha(INDISPONIVEL) if k in tira else celulas[k][origem])
                                              for k in tickers})
  ```
  (`celulas` não é alterado: o valor da própria empresa continua no pacote.)

**4.3 `processamento/saida/pacotes_fatos.py`, `calcular_grades` (linha 66)**
```python
def calcular_grades(ins: Insumos, params_precos: ParametrosPrecos, params_fund: ParametrosFundamentos) -> GradesDoDia:
    """Calcula as três grades da rodada no ponto de vista de `ins.t`."""
    fora = tickers_com_suspeita(ins.precos, ins.cal, ins.t, tickers_do_painel(ins.cadastro, ins.exclusoes),
                                params_precos.retorno_suspeito_min, params_precos.retorno_suspeito_max,
                                params_precos.retorno_suspeito_pregoes_nivel)
    return GradesDoDia(
        precos=calcular_precos(ins.precos, ins.cadastro, ins.cal, ins.exclusoes, params_precos),
        indices=calcular_indices(ins.precos, ins.indices, ins.cal, params_precos),
        fundamentos=calcular_fundamentos_no_dia(
            ins.t, ins.cal, dados_fundamentos(ins), ins.exclusoes, params_fund, params_precos.setor_excluir,
            fora_do_setor_preco=frozenset(fora),
        ),
    )
```
(importar `tickers_com_suspeita` de `processamento.fatos.precos`; `tickers_do_painel` já é importado.)

**4.4 Testes** (`tests/test_setor_suspeitos.py`, novo)

Caso 4a: rentabilidade do setor no `calcular_precos`.
```python
from dataclasses import replace
import pandas as pd
import pytest
from fabrica_precos import cadastro_de, precos_de, pregoes_uteis, serie_por_retornos
from processamento.exclusoes import Exclusoes
from processamento.fatos.precos import HIST, OK, calcular_precos, carregar_parametros_precos

CAL = pregoes_uteis(8, "2026-04-06")
PRECOS = pd.concat([
    precos_de("IBOV", CAL, [10.0] * 8),
    precos_de("AZUL3", CAL, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0, 106.05, 107.1105]),
    precos_de("EMBR3", CAL, serie_por_retornos(50.0, [0.02, -0.01, 0.02, -0.01, 0.01, 0.0, 0.01])),
    precos_de("WEGE3", CAL, serie_por_retornos(40.0, [0.0, 0.01, -0.02, 0.03, 0.0, 0.01, -0.01])),
    precos_de("RAIL3", CAL, serie_por_retornos(20.0, [0.03, 0.0, -0.01, 0.02, 0.01, -0.02, 0.0])),
    precos_de("SOLO3", CAL, [10.0] * 8),
])
CADASTRO = cadastro_de([("AZUL3", "1", "BI", "ON"), ("EMBR3", "2", "BI", "ON"), ("WEGE3", "3", "BI", "ON"),
                        ("RAIL3", "4", "BI", "ON"), ("SOLO3", "5", "Y", "ON"), ("NOPX3", "6", "Y", "ON")])
PARAMS = replace(carregar_parametros_precos(), janelas={"d1": 1, "m1": 3, "m6": 5})
RES = calcular_precos(PRECOS, CADASTRO, CAL, Exclusoes(), PARAMS)
```
Esperado: `RES["rentabilidade.setor.d1"]`, `["rentabilidade.setor.m1"]` e `["rentabilidade.setor.m6"]` da EMBR3
iguais às listas `r["d1"]`, `r["m1"]` e `r["m6"]` do caso 2c da Fase 2 (valores e status); SOLO3 com `HIST` e
NOPX3 com `OK` no último dia. Valores da própria ação sem mudança: `RES["rentabilidade.d1"]` AZUL3 em 08/04 =
19999.0 com `ok`; `RES["rentabilidade.m1"]` AZUL3 em 09/04 = 21419.0 com `ok`.
Os testes atuais de `tests/test_fatos_montagem.py` continuam valendo sem mudança: PETR4 `rentabilidade.setor.d1`
`indisponivel` (PETR3 é a mesma empresa); no modo "acao", 0.0 com `ok` (série só da PETR3, preço parado);
ABEV3 `indisponivel` (Bebidas sem outra empresa).

Caso 4b: ligação com o núcleo. Para cada janela e cada ticker do caso 4a, `RES[f"rentabilidade.setor.{j}"]`
(valor e status) é igual a `rentabilidade_setor_sem_empresa(g_aj, CADASTRO, pares, tickers, PARAMS.janelas, "empresa", suspeitos)[j]`,
com `g_aj = grade_de_precos(PRECOS, CAL, "fechamento_ajustado", tickers)`,
`tickers = tickers_do_painel(CADASTRO, Exclusoes())`, `pares = pares_do_painel(CADASTRO, Exclusoes())` e
`suspeitos = retornos_suspeitos(g_aj, -0.75, 1.0)`.

Caso 4c: medianas de nível. Mundo de `tests/fabrica_fundamentos.py` em T = 2026-03-31, como em
`tests/test_fund_no_dia.py` (`from fabrica_fundamentos import EXCL, T, mundo`;
`CADASTRO, BALANCOS, ACOES, PROVENTOS, PRECOS, CAL, MUDANCAS = mundo()`; `DADOS = DadosFundamentos(...)`;
`PARAMS = carregar_parametros_fundamentos()`; copiar os auxiliares `_celula`, `_ok` e `_sem_valor` de lá).
Setor S1 = AAAA (AAAA3 e AAAA4, mesmo CNPJ), UUUU11 e PREJ3.
`r = resumo_precos_no_dia(calcular_fundamentos_no_dia(T, CAL, DADOS, EXCL, PARAMS, "empresa", fora_do_setor_preco=frozenset({"AAAA4"})), T)`
(só a AAAA4 é suspeita: a empresa AAAA inteira sai). Esperado (conferido: igual a rodar o código atual com o
fechamento da AAAA3 e da AAAA4 vazio em T):

| ticker | indicador | esperado | hoje |
|---|---|---|---|
| UUUU11 | pl.setor | NaN, `indisponivel` | 5.75 |
| PREJ3 | pl.setor | 18.75 | 12.25 |
| UUUU11 | pvp.setor | 0.3076923076923077 | 0.5076923076923077 |
| PREJ3 | pvp.setor | 2.3076923076923075 | 1.5076923076923077 |
| UUUU11 | dividend_yield.setor | 0.025 | 0.0421875 |
| PREJ3 | dividend_yield.setor | 0.08 | 0.0696875 |
| UUUU11 | roe.setor | 0.03076923076923077 (não muda) | igual |
| PREJ3 | roe.setor | 0.12307692307692308 (não muda) | igual |
| UUUU11 | payout.setor | 0.328125 (não muda) | igual |
| PREJ3 | payout.setor | 0.9140625 (não muda) | igual |
| AAAA3 | pl.valor | 5.75 `ok` (não muda) | igual |
| AAAA4 | pvp.valor | 0.7076923076923077 `ok` (não muda) | igual |
| AAAA4 | dividend_yield.valor | 0.06875 `ok` (não muda) | igual |
| AAAA3 | pl.setor | 18.75 (o setor dela não muda) | igual |
| AAAA3 | pvp.setor | 1.3076923076923075 | igual |

Caso 4d: ligação no `calcular_grades`. Com `monkeypatch`, trocar `pacotes_fatos.calcular_fundamentos_no_dia`
por um embrulho que guarda os kwargs e chama a original. Com
`ins = insumos_de_teste(banco_teste({"v1-precos": _salto_petr4}))` (copiar `_salto_petr4` do caso 3e da Fase 3;
`insumos_de_teste` vem de `fabrica_saida`) e
`pacotes_fatos.calcular_grades(ins, carregar_parametros_precos(), carregar_parametros_fundamentos())`:
`fora_do_setor_preco == frozenset({"PETR4"})`. Com `banco_teste()` sem alteração: `frozenset()`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_setor_suspeitos.py tests/test_fund_no_dia.py tests/test_fatos_montagem.py tests/test_fatos_setor.py tests/test_saida_pacotes_fatos.py tests/test_exp_variaveis.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

---

### Fase 5: checagem nova no diagnóstico (depois da Fase 1; pode rodar junto com as Fases 2, 3 e 4)

**5.1 `processamento/diagnostico/temas.py`**
- Imports: acrescentar `carregar_parametros_precos, retornos_asof, retornos_suspeitos` ao
  `from processamento.fatos.precos import ...` (linha 60) e `from processamento.experimento.relatorio import pct`
  (já usado em `rotina/checagem.py`).
- No fim do arquivo, depois de `secao_quantidade_acoes`:
  ```python
  # ---------------------------------------------------------------------------
  # Retornos diários suspeitos (seção 6 da especificação; pendência da coleta, seção 10)
  # ---------------------------------------------------------------------------

  TABELAS_RETORNOS = ("precos",)


  def secao_retornos_suspeitos(ler, mapa: dict, existentes: set) -> dict:
      """Retornos diários do `fechamento_ajustado` fora de [fase1.retorno_suspeito_min, fase1.retorno_suspeito_max].

      Nota + tabela (não é divergência): o processamento isola esses retornos (seção 6). Histórico inteiro,
      todos os tickers de `v1-precos`, nos pregões do IBOV, contra o último pregão com preço. Lê só por
      `fontes.ler_tabela`; a conta é a de `fatos.precos.retornos_suspeitos`.
      """
      secao = nova_secao("Retornos diários suspeitos")
      faltam = [c for c in TABELAS_RETORNOS if not _existe(mapa, existentes, c)]
      if faltam:
          for c in faltam:
              secao["notas"].append(_pulada(mapa, c))
          return secao
      params = carregar_parametros_precos()
      precos = fontes.ler_tabela("precos", ler=ler)
      cal = calendario.pregoes(precos)
      if not cal:
          secao["notas"].append("sem pregão com preço do IBOV: checagem não feita")
          return secao
      tickers = sorted(precos["ticker"].dropna().unique())
      g_aj = grade_de_precos(precos, cal, "fechamento_ajustado", tickers)
      g_fech = grade_de_precos(precos, cal, "fechamento", tickers)
      suspeitos = retornos_suspeitos(g_aj, params.retorno_suspeito_min, params.retorno_suspeito_max)
      anterior = g_aj.ffill().shift(1)
      r_aj, r_fech = retornos_asof(g_aj), retornos_asof(g_fech)
      linhas = []
      for tk in tickers:
          for d in g_aj.index[suspeitos[tk].to_numpy()]:
              linhas.append([tk, d.date(), float(anterior.at[d, tk]), float(g_aj.at[d, tk]),
                             float(r_aj.at[d, tk]), float(r_fech.at[d, tk])])
      limites = f"abaixo de {pct(params.retorno_suspeito_min, 0)} ou acima de {pct(params.retorno_suspeito_max, 0)}"
      if not linhas:
          secao["notas"].append(f"nenhum retorno diário suspeito (fechamento_ajustado {limites})")
          return secao
      secao["notas"].append(
          f"{len(linhas)} retornos diários suspeitos em {len({l[0] for l in linhas})} tickers "
          f"(fechamento_ajustado contra o último pregão com preço, {limites}): saem das séries e das medianas "
          "do setor; o preço não é corrigido (seção 6)")
      adicionar_tabela(secao, "Retornos diários suspeitos",
                       ["ticker", "data", "aj_anterior", "aj", "retorno_aj", "retorno_fech"], linhas)
      return secao
  ```
  `float(r_fech.at[d, tk])` pode dar NaN se o `fechamento` estiver vazio; tudo bem (o relatório formata NaN).

**5.2 `processamento/diagnostico/__main__.py`**, em `coletar`, logo depois da linha
`_seguro("Quantidade de ações suspeita", temas.secao_quantidade_acoes, ler, mapa, existentes),`:
```python
        _seguro("Retornos diários suspeitos", temas.secao_retornos_suspeitos, ler, mapa, existentes),
```

**5.3 Testes** (`tests/test_diagnostico_temas.py`, no fim). Mesmo padrão da fixture `tabelas_quantidade`:
`monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: PRECOS_R.copy())`, leitor `_ler_sem_banco`,
existentes = `{fontes.nome_real("precos")}`; importar `secao_retornos_suspeitos` e
`from fabrica_precos import precos_de, pregoes_uteis`.
```python
CAL_R = pregoes_uteis(6, "2026-04-06")
PRECOS_R = pd.concat([
    precos_de("IBOV", CAL_R, [10.0] * 6),
    precos_de("AZUL3", CAL_R, [100.0, 102.0, 2040000.0, 2142000.0, 105.0, 105.0]),
    precos_de("GAPX3", CAL_R, [10.0, None, 25.0, 25.0, 25.0, 25.0]),
    precos_de("SPLT3", CAL_R, [40.0, 40.0, 10.0, 10.0, 10.0, 10.0], aj=[10.0] * 6),  # desdobramento real: fora
], ignore_index=True)
```
| caso | esperado (conferido) |
|---|---|
| 5a | `secao["notas"] == ["3 retornos diários suspeitos em 2 tickers (fechamento_ajustado contra o último pregão com preço, abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)"]`; `secao["divergencias"] == []` |
| 5b | 1 tabela, colunas `["ticker", "data", "aj_anterior", "aj", "retorno_aj", "retorno_fech"]`; linhas `["AZUL3", date(2026,4,8), 102.0, 2040000.0, 19999.0, 19999.0]`, `["AZUL3", date(2026,4,10), 2142000.0, 105.0, -0.9999509803921569, -0.9999509803921569]`, `["GAPX3", date(2026,4,8), 10.0, 25.0, 1.5, 1.5]` (números com `pytest.approx`) |
| 5c | só IBOV e SPLT3: notas `["nenhum retorno diário suspeito (fechamento_ajustado abaixo de -75% ou acima de 100%)"]`, sem tabelas |
| 5d | sem IBOV: notas `["sem pregão com preço do IBOV: checagem não feita"]` |
| 5e | `existentes = set()`: uma nota que começa com "pulada: tabela ausente"; `_ler_sem_banco` não é chamado |

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_diagnostico_temas.py tests/test_diagnostico_main.py tests/test_diagnostico_relatorio.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`. **Não** rodar `python -m processamento.diagnostico`
(lê o banco real): o `docs/diagnostico_banco.md` é regerado pelo usuário.

---

### Fase 6: especificação (pode rodar em paralelo; só `ESPECIFICACAO.md`)

Trocas exatas (procurar o trecho citado e substituir):
1. **Seção 5, abertura** (parágrafo "Fonte dos dados..."): depois de "(sem a própria empresa: tiram-se todas as
   ações do mesmo CNPJ, ex.: PETR3 não entra no setor da PETR4)" inserir:
   ` **Exceção (24/10/2026): a rentabilidade do setor não é mediana:** é a razão de dois pontos da série `SETOR_SEM:<ticker>` (8.3, item 4), a mesma do gráfico, com as mesmas outras empresas;`
2. **Seção 5, linha "Rentabilidade"**: trocar "idem para IBOV e setor" por
   "idem para IBOV; setor = `SETOR_SEM:<ticker>(t) / SETOR_SEM:<ticker>(t−n) − 1` (base as-of)".
3. **Seção 5, linha "Comparação com o setor"**: a linha inteira passa a ser
   `| Comparação com o setor | Rentabilidade da ação × rentabilidade do setor sem a própria empresa (série `SETOR_SEM:<ticker>`: média igual por empresa dos retornos diários das outras empresas do setor, encadeada), mesmas janelas | Gráfico e tabela usam a mesma série e batem |`
   (sai o "Na série do gráfico, o setor inclui todas as ações (diferença aceita)").
4. **Seção 6**, linha nova logo depois de "Quantidade de ações suspeita":
   `| Retorno diário suspeito | Retorno do dia do `fechamento_ajustado` (contra o último pregão com preço) **abaixo de −75% ou acima de +100%** (`fase1.retorno_suspeito_min`/`_max`; os limites exatos não contam) = erro da coleta (ex.: AZUL3 com 30.599.848 de 09/04 a 17/04/2026). **O preço não é corrigido:** o valor da própria ação (cotação, rentabilidade, série, P/L etc.) sai como veio. Só isola: (a) o retorno daquele dia não entra nas séries `SETOR_SEM:<ticker>` (nem, por isso, na `rentabilidade.setor`); (b) a empresa inteira fica fora das medianas de P/L, P/VP e yield do setor se alguma ação dela teve retorno suspeito nos últimos 21 pregões (`fase1.retorno_suspeito_pregoes_nivel`); (c) aviso no `execucao` com os suspeitos dos 253 pregões do pacote; (d) o diagnóstico lista todos (decidido em 24/10/2026; pedido à coleta na seção 10) |`
5. **Seção 8.3, item 3**, bullet `rentabilidade`: acrescentar no fim
   "; `setor` = razão de dois pontos da série `SETOR_SEM:<ticker>` (item 4, base as-of), a mesma do gráfico".
6. **Seção 8.3, item 4**:
   - "`tipo` (`acao`, `etf`, `indice`, `taxa`, `setor`)" → "`tipo` (`acao`, `etf`, `indice`, `taxa`, `setor_sem_empresa`)";
   - "`SETOR:<nome>`: índice e `n_empresas` (sem status)" → "`SETOR_SEM:<ticker>` (uma por ação do painel com outra empresa no setor, BDR inclusive; `nome` = "<setor> sem <empresa>"): índice e `n_empresas` (sem status)";
   - o trecho que começa em "**Setor:** média igual por empresa dos retornos diários" e vai até "a cadeia segue do último valor." passa a ser:
     `**Setor sem a própria empresa (`SETOR_SEM:<ticker>`, decidido em 24/10/2026):** média igual por empresa dos retornos diários das ações ON, PN e UNIT do setor da ação (BDR nunca entra), **sem nenhuma ação da mesma empresa (CNPJ)**, com preço no dia e no pregão anterior e sem os retornos suspeitos (seção 6), encadeada em base 100; dia sem nenhuma outra empresa: ponto vazio (`indisponivel`) e a cadeia segue do último valor. Sem setor ou sem outra empresa no setor: sem série e `rentabilidade.setor` `indisponivel`; outras empresas sem nenhum preço: sem série e `historico_insuficiente`. A série `SETOR:<nome>` (todas as empresas) não é mais enviada; no envio seguinte ela vai em `removidos`.`
   - a frase "A divisão de dois pontos dá a rentabilidade da janela do `resumo_acao`/`mercado_dia`." fica (agora vale também para o setor).
7. **Seção 8.4**: depois de "→ `series_diarias` (+ `resumo_acao` para os % de cada período)" inserir
   " (o setor de cada ação é a série `SETOR_SEM:<ticker>`; o % do setor no `resumo_acao` é a razão dela)".
8. **Seção 9, S5**: a decisão inteira passa a ser
   `- **S5 Setor (atualizado em 24/10/2026):** uma série por ação, `SETOR_SEM:<ticker>`: média por empresa dos retornos diários (preço em t e no pregão anterior) das ações ON/PN/UNIT do setor, sem a própria empresa; BDR nunca entra; retorno suspeito (seção 6) não entra; dia sem retorno = ponto vazio e a cadeia segue. A `rentabilidade.setor` do `resumo_acao` é a razão dela. A antiga `SETOR:<nome>` (com a própria) saiu.`
9. **Seção 9, S19**: acrescentar no fim "; as séries `SETOR_SEM:<ticker>` seguem a mesma janela e a mesma âncora".
10. **Seção 9, S20**: depois de "~47 KB por dia)" inserir
    "; com as séries `SETOR_SEM` (24/10/2026): +0,83 MB na carga completa (~3,1 MB no pacote de 23/10) e +34 KB por dia".
11. **Seção 9, D10**: depois de "a `ret_vs_setor` do modelo segue com a média." inserir
    " **Atualizado em 24/10/2026:** a rentabilidade do setor no painel sai da série `SETOR_SEM:<ticker>` (média igual por empresa dos retornos diários, sem a própria empresa); a mediana fica para os indicadores de valor."
12. **Seção 9**, depois do bloco "Acréscimo de 24/10/2026 (carga completa, seção 8.7)", um bloco novo:
    - título `**Acréscimo de 24/10/2026 (retornos suspeitos e setor sem a própria empresa; plano em `docs/plano_suspeitos_setor.md`)**`
    - `- **Retorno suspeito:** retorno diário do ajustado fora de [−75%, +100%] (base as-of, limites estritos); não corrige o preço, só isola (séries do setor, medianas de P/L, P/VP e yield por 21 pregões, aviso, diagnóstico). Parâmetros no bloco `fase1`.`
    - `- **Setor sem a própria empresa:** série `SETOR_SEM:<ticker>` por ação (tipo `setor_sem_empresa`), e a `rentabilidade.setor` é a razão dela (gráfico e tabela batem). Motivo: a planilha e o TCC definem o setor sem a própria ação. A `SETOR:<nome>` saiu do pacote. A versão do contrato continua "1.0" (contrato ainda não está em uso).`
    - `- **Experimento:** não muda nesta etapa (pendência na seção 10).`
13. **Seção 10**, duas linhas novas na tabela:
    - `| **Preços com erro de escala em `v1-precos`** (medido em 24/10/2026 no pacote): AZUL3 com `fechamento` e `fechamento_ajustado` ~141 mil vezes maiores de 09/04 a 17/04/2026 (30.599.848 contra ~217), e salto de ×46 em 10/02/2026 sem volta (provável grupamento não ajustado no `fechamento_ajustado`). Pedido à coleta: corrigir o histórico. Enquanto isso, o processamento isola os retornos suspeitos (seção 6) | Coleta |`
    - `| **Experimento × retornos suspeitos (resolver antes do treino definitivo):** a `ret_vs_setor` (média do setor) e as variáveis e o alvo da própria ação usam o preço como veio. AZUL3 (no universo) contamina 09/04 e 20/04/2026 (rank da `ret_vs_setor` das outras 6 de Bens Industriais) e, nas linhas dela, `ret_*`, volatilidade, beta, `dist_max_52s` (1 ano) e o alvo de 08/04 e 17/04. Resolver com a máscara de retornos suspeitos no `ret_vs_setor` e o descarte das linhas afetadas | Processamento |`

O `CLAUDE.md` NÃO é editado pelo implementador (a sessão principal edita). Texto da pegadinha 17, ajustado:
`17. **Setor sem a própria empresa e retorno suspeito:** a comparação de rentabilidade com o setor usa a série `SETOR_SEM:<ticker>` (uma por ação, sem nenhuma ação do mesmo CNPJ; a `rentabilidade.setor` é a razão dela; a `SETOR:<nome>` saiu). Retorno diário do ajustado fora de [−75%, +100%] (bloco `fase1`) é erro da coleta (AZUL3 abr/2026): não corrigir o preço; ele sai dessas séries e das medianas de P/L, P/VP e yield do setor (seção 6). O experimento ainda não trata (seção 10).`

**Verificação:** nenhuma de código; reler os trechos alterados.

---

## 5. Verificação final (sessão principal, via executor)

```bash
./.venv/Scripts/python.exe -m pytest -q
```
Depois, pelo usuário (lê o banco real; não delegar): `python -m processamento.diagnostico` (a seção nova deve
listar AZUL3 em 2026-02-10, 2026-04-09 e 2026-04-20, e talvez datas anteriores a 16/10/2025, que o pacote não
mostra) e `python -m processamento.saida --data 2026-10-23 --completo`. Conferir: 85 séries `SETOR_SEM:` e
nenhuma `SETOR:`; `SETOR_SEM:PETR4` e `resumo_acao` da PETR4 com +9,62% em 6 meses (a razão de dois pontos da
série = `rentabilidade.setor.m6`); `n_empresas` das séries de Bens Industriais menor em 10/02, 09/04 e 20/04;
o aviso no `execucao.json`; `series_diarias.json` perto de 3,1 MB.

---

## 6. Riscos

- Ação com movimento real acima de +100% num dia (ex.: OPA, saída de recuperação judicial) também sai das séries
  do setor naquele dia. Raro; o aviso e o diagnóstico mostram. Ajustável no YAML.
- Desdobramento ou grupamento que a coleta não ajustar no `fechamento_ajustado` vira suspeito (é o desejado: o
  ajustado errado também é erro).
- `n_empresas` cai nos dias com suspeito: a interface não deve tratar isso como "setor mudou".
- A interface do protótipo usa `SETOR:<nome>`: tem de passar a usar `SETOR_SEM:<ticker>` da ação mostrada.
- Setores pequenos (Tecnologia da Informação e Comunicações têm 2 empresas): a série de cada ação é a da outra
  empresa sozinha. É a definição pedida; o `setor_comparacao_fraca` continua avisando.
- A `rentabilidade.setor` muda de valor para quase todas as ações (de mediana para média encadeada: DS11).

---

## 7. ITEM 2: decidido = opção D (24/10/2026). Registro da análise

**Problema.** A linha do gráfico (`SETOR:<nome>`, S5 antiga) era a **média** por empresa dos **retornos diários**,
encadeada, **com a própria empresa**; a tabela (`resumo_acao.rentabilidade.setor`) era a **mediana** por empresa
da **rentabilidade da janela**, **sem a própria empresa**. A mediana de retornos diários encadeada não é a
mediana das rentabilidades da janela.

**Exemplo (3 empresas, 2 dias; A +10% e +10%; B -2% e +3%; C +4% e -6%):** janelas A +21,00%, B +0,94%,
C -2,24%; mediana das janelas +0,94%; mediana diária encadeada +7,12%; média diária encadeada +6,43%; sem A:
mediana das janelas -0,65%, média diária encadeada -0,52%.

**Medido no pacote local** (84 ações ON/PN/UNIT, 10 setores, sem os suspeitos da AZUL3). |linha − tabela| em pontos
percentuais, mediana / p90 / máximo:

| opção para a linha | m1 | m6 | a1 |
|---|---|---|---|
| antiga (média diária, com a própria) | 2,5 / 10,8 / 12,0 | 3,5 / 7,5 / 13,1 | 6,5 / 29,5 / 36,2 |
| A: mediana diária, com a própria | 2,7 / 7,2 / 8,5 | 3,0 / 15,3 / 20,1 | 5,5 / 18,8 / 44,6 |
| B: mediana diária, sem a própria | 2,6 / 5,6 / 11,1 | 2,8 / 13,3 / 22,0 | 4,2 / 17,5 / 53,9 |
| C: tabela = razão da `SETOR:` (com a própria) | 0 | 0 | 0 |
| **D (escolhida): série sem a própria por ação, tabela = razão dela** | **0** | **0** | **0** |

PETR4 em 6 meses: antes, linha +11,92% × tabela +4,61%; **com D, +9,62% nas duas**.
Custo de D: DS14. Contrato: DS10 e DS15.
