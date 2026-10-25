# Plano: base velha nas janelas e pasta limpa na saída (24/10/2026)

Arquiteto, 24/10/2026. Decisões do usuário fechadas (não reabrir): (1) a base de uma janela só vale a no máximo N
pregões da data-alvo, senão `historico_insuficiente`; (2) antes de gravar, a pasta da rodada perde os pacotes que não
serão gravados. Nenhum número aqui veio do banco. **(conferido)** = valor obtido rodando um protótipo do código novo
(cópia do repositório numa pasta temporária) sobre a fábrica, sem banco e sem rede. Com o protótipo, a suíte
inteira (`pytest -q`: 1626 passaram, 23 pulados) continua verde: **nenhum teste existente muda de gabarito**,
exceto o teste de banco do IDIV (seção 0, item 1).

---

## Resumo

| Item | O quê | Fase |
|---|---|---|
| 1a | Regra da base velha em `fatos.precos.variacao` (`defasagem_max`) + parâmetros `fase1.base_defasagem_max_pregoes: 5` e `fase1.ipca_defasagem_max_meses: 2`; ação, IBOV, `variacao_dia` e `rentabilidade.setor` (`SETOR_SEM`) | **1** |
| 1b | Índices: IDIV/SMLL/IFIX/IVVB11 (mesma regra), `cdi_dia` com atraso > N pregões e IPCA com atraso > 2 meses → `indisponivel`; `mercado_dia` (IBOV/USDBRL/BRENT); pontos do IPCA no `series_diarias`; teste de banco do IDIV | **2** (depois da 1) |
| 1c | Experimento: `ret_1d`, `ret_5d`, `ret_20d` e o retorno do dia da `ret_vs_setor` com a mesma regra | **3** (depois da 1) |
| 1d | Diagnóstico: seção nova "Lacunas nas séries de preços e índices" (só notas e tabelas) | **4** (depois da 1) |
| 2 | Pasta limpa: toda rodada que gera pacotes apaga os 9 arquivos de pacote antigos antes de gravar; rodada `falhou` não apaga e avisa | **5** (independente) |
| - | Textos da `ESPECIFICACAO.md` | **6** (o usuário aprova) |

---

## 0. Onde o código não permite seguir a decisão à risca (listado, não resolvido)

1. **H5 vira o contrário.** A decisão H5 ("com o histórico novo, o m1 do IDIV em 21/10/2026 é `ok`") só era `ok`
   por causa do bug: a base m1 (21/09/2026) cai no buraco de 2025 e a efetiva é de 2024. Com a regra, o m1 do IDIV em
   21/10/2026 sai `historico_insuficiente` e o d1 sai `ok` (base 20/10/2026). O teste de banco
   `tests/test_fatos_banco.py::test_idiv_m1_ok_em_21_10_2026` muda de gabarito (Fase 2); só o usuário roda.
2. **CDI já é mais estrito que a regra.** `rentabilidade_cdi` (`fatos/indices.py:60-84`) exige a taxa de **todos** os
   pregões em [base, t) e sai `indisponivel` com qualquer lacuna (`:77-79`). Não dá para "aceitar até N pregões sem
   taxa" sem perder juros na conta; fica como está (valor e status `indisponivel`, não `historico_insuficiente`).
   O ponto final `cdi_dia` (`:120-126`) usava a última taxa ≤ t sem limite: passa a ter o limite de N pregões.
3. **Séries base 100 do `series_diarias` não têm status por janela.** Os pontos sem valor já saem `indisponivel`
   (`fatos/series.py:32-56`), mas a interface "parte do mesmo ponto dividindo pelo primeiro valor do recorte"
   (8.3 item 4): no IDIV de hoje, o recorte de 1 ano tem só 3 pontos `ok` (20 a 22/10/2026) e o gráfico mostraria
   ~+0,4% "em 1 ano", enquanto o `mercado_dia` diz `historico_insuficiente`. O processamento não resolve isso; a
   Fase 6 propõe um texto para a equipe da interface (mostrar o % do recorte só se o 1º ponto do recorte, ou um até
   5 pregões antes dele, tiver valor).
4. **CDI base 100 morre na 1ª lacuna** (`series.py:84-96`, S6: "lacuna = indisponivel dali em diante"). Não muda
   aqui; com uma lacuna real no CDI, o gráfico do CDI fica vazio daí em diante.
5. **Retorno diário suspeito continua sem limite** (`precos.py:175-187`, "contra o último pregão com preço", seção
   6). Um retorno através de uma lacuna longa pode cair fora de [−75%, +100%] e ser marcado suspeito (falso
   positivo: tira a empresa das medianas de P/L, P/VP e yield por 21 pregões e entra no aviso). Não é janela do
   painel nem do modelo; deixar como está, ou aplicar a regra também ali, é decisão do usuário (são 5 chamadores).
6. **Pasta limpa x "quando muda":** numa rodada repetida com estado (envio diário), os pacotes "quando muda"
   (`acoes`, `series_diarias`, `fundamentos_trimestrais`, `proventos`) da rodada 1 já foram marcados como enviados no
   `saida/estado/`; a rodada 2 já hoje os sobrescreve com 0 registros. Com a limpeza, se um desses pacotes **falhar**
   na rodada 2, o arquivo da rodada 1 some (antes ficava). Só importa se alguém usar a pasta como fila de envio
   antes de existir a API.
7. **Rodada `falhou` depois de uma `ok` do mesmo D:** escolhi **não apagar** (os pacotes da rodada `ok` são de D e
   de uma entrega concluída; apagar tiraria dados válidos sem pôr nada no lugar; na futura API eles já teriam sido
   enviados). O `execucao.json` da rodada `falhou` ganha o aviso "Pacotes de uma rodada anterior de D continuam na
   pasta ...". A especificação (8.3 item 10) diz "o `execucao.json` é o único arquivo **da rodada**": continua
   verdade (os outros são da rodada anterior), mas a pasta fica com `falhou` + pacotes. Decisão do usuário se
   preferir apagar.
8. **Dataset do experimento muda:** linhas depois de uma lacuna de mais de 5 pregões perdem `ret_*` e
   `ret_vs_setor` (vazio). O sha256 do dataset muda; os modelos provisórios em `modelos/` não são retreinados
   sozinhos (sem efeito no TCC enquanto `treino.modelo_oficial: false`).
9. **`ipca_ate` continua mostrando o mês velho** com status `ok` (é informativo), enquanto `ipca_12m` e as
   janelas do IPCA saem `indisponivel`. `cdi_data` fica vazio (`null`) quando o `cdi_dia` sai `indisponivel`
   (mesmo formato de "sem taxa"; o contrato aceita: `contrato.py:386`, `"cdi_data": "data?"`).

---

## 1. Problema 1: base velha nas janelas

### 1.1 Regra (definição fixada)

- k = posição de t no calendário de pregões (datas com IBOV); janela de n pregões.
- **Data-alvo da base** = cal[k−n]. **Data efetiva** = a última data ≤ data-alvo **com valor** na grade
  (a grade só tem pregões: valor em dia sem pregão não conta).
- **Defasagem** = posição(data-alvo) − posição(efetiva), em pregões do calendário (0 = a própria data-alvo tem valor).
- A base vale se **defasagem ≤ N** (`fase1.base_defasagem_max_pregoes`, padrão 5; inteiro ≥ 0; 0 = base exata).
  Defasagem N vale; N+1 não vale → `historico_insuficiente`.
- Sem nenhum valor até a data-alvo → `historico_insuficiente` (como hoje). Ponto final: **já exige valor em t**
  (`precos.py:166`, `g.isna() → indisponivel`): não muda.
- Exemplos com o calendário real (pregões previstos), t = 22/10/2026, IDIV com último valor de 2024 em 30/12/2024 e
  de novo desde 20/10/2026: d1 alvo 21/10/2026 (defasagem 0, ok); m1 alvo 22/09/2026 (defasagem 431); m6 alvo
  23/04/2026 (326); a1 alvo 16/10/2025 (200) → m1, m6, a1 `historico_insuficiente` (hoje saem +60,7% nas três).
  Se faltasse o 21/10, a efetiva do d1 seria 20/10 (defasagem 1, ok).

**IPCA (meses):** atraso(d) = mês de d − K(d), em meses (K(d) = maior mês conhecido antes do mês de d,
`indices.py:53-57`). Normal: 1 (mês anterior já divulgado) ou 2 (primeiros ~10 dias do mês). Vale se
atraso ≤ M (`fase1.ipca_defasagem_max_meses`, padrão 2; inteiro ≥ 1); senão `indisponivel` em: janelas do IPCA
(no ponto t), `ipca_12m` e os pontos do índice IPCA do `series_diarias`. Mês faltando **dentro** da janela já era
`indisponivel` (`indices.py:103-113`): não muda. A base do IPCA não precisa de regra própria: se K(base) está
velho, os meses que faltam caem dentro de (K(base), K(t)] e já dão `indisponivel`.
Ex.: t = 22/10/2026 com K = 2026-09 → 1, ok; t = 05/10/2026 com K = 2026-08 → 2, ok; K = 2026-07 → 3,
`indisponivel`; IPCA parado em 2024-12 → 22, `indisponivel` (hoje: a1 = 0% `ok` e `ipca_12m` = 2024 inteiro `ok`).

**CDI:** janelas sem mudança (seção 0, item 2). `cdi_dia`: nº de pregões do calendário em (data da última taxa, t];
se > N → `(NaN, indisponivel, None)`.

**Status:** base velha = `historico_insuficiente` (decisão do usuário); ponto final velho (CDI do dia, IPCA) =
`indisponivel` (o dado de hoje não veio, como `g(t)` vazio hoje).

### 1.2 Mapa de TODOS os cálculos de janela (arquivo:linha atual)

| Cálculo | Onde | O que muda |
|---|---|---|
| Variação as-of (núcleo) | `processamento/fatos/precos.py:162-167` (`variacao`) | ganha `defasagem_max` (Fase 1) |
| `cotacao.variacao_dia` | `precos.py:400` | passa N |
| `variacao_preco.{d1,m1,m6,a1}` | `precos.py:408` | passa N |
| `rentabilidade.{janela}` (ação) | `precos.py:407,409` | passa N |
| `rentabilidade.ibov.{janela}` | `precos.py:410` (IBOV define o calendário: nunca tem lacuna; passa N por uniformidade) | passa N |
| `rentabilidade.setor.{janela}` (razão da `SETOR_SEM:<ticker>`) | `precos.py:402-405` → `fatos/series.py:234-260` (`variacao` em `:252`) | parâmetro novo `defasagem_max` |
| IDIV, SMLL, IFIX e IVVB11 (`mercado_dia.indices`) | `fatos/indices.py:163-164` (`calcular_indices`) | passa N (Fase 2) |
| IPCA nas janelas | `indices.py:87-117` (`rentabilidade_ipca`), chamado em `:162` | atraso > M → `indisponivel` |
| CDI nas janelas | `indices.py:60-84` | **não muda** (já exige todas as taxas) |
| `cdi_dia` (ponto final as-of) | `indices.py:120-126`; usado em `saida/pacotes_fatos.py:159` | atraso > N pregões → `indisponivel` |
| `ipca_12m` | `indices.py:129-145`; usado em `pacotes_fatos.py:160` | atraso > M → `indisponivel` |
| `variacao_dia` de IBOV/USDBRL/BRENT no `mercado_dia` | `saida/pacotes_fatos.py:143-153` (`_cotacao_de_indice`, `variacao` em `:147`) | passa N |
| Pontos do IPCA base 100 | `fatos/series.py:113-137` (`indice_ipca`), chamado em `saida/pacote_series.py:171` | atraso > M → `indisponivel` |
| `ret_1d`, `ret_5d`, `ret_20d` | `experimento/variaveis.py:96-97` | passa N (Fase 3) |
| retorno do dia da `ret_vs_setor` | `experimento/variaveis.py:99,108` | passa N |

**Não é janela (fica como está):** volatilidade (`precos.py:210-213`, retornos estritos + 20 completos), volume
relativo (`:195-207`, 20 anteriores completos), beta (`:234-255`, só pares de retornos estritos, mínimo 120),
`salto_abertura` (`variaveis.py:22-28`, anterior estrito), `dist_max_52s`/`dist_min_52s` (`variaveis.py:31-37`,
252 pregões com mínimo 120), exposições (`variaveis.py:49-52`, beta estrito), alvo (`experimento/alvo.py`, t+1
estrito), cadeia `SETOR_SEM` (`series.py:168-204`, retornos estritos), checagem diária (`rotina/checagem.py:93`,
retornos estritos), retorno suspeito (seção 0, item 5), séries base 100 de ações/IBOV/IDIV/SMLL/IFIX
(`series.py:32-62`: ponto sem valor já é `indisponivel`; seção 0, item 3) e CDI base 100 (seção 0, item 4).

### 1.3 Decisões técnicas

- **D1 assinatura:** `variacao(g, n, defasagem_max: int | None = None)`. `None` = sem limite (comportamento antigo,
  mantém os testes que chamam `variacao(g, n)`); **todo chamador de produção passa o parâmetro**.
- **D2 conta:** `defasagem_pregoes(g)` = pregões desde o último valor de cada coluna (0 com valor; NaN antes do 1º
  valor); a base de t é velha se `defasagem_pregoes(g).shift(n) > defasagem_max`. Só olha para trás.
  Ordem das regras de status: `g(t)` vazio → `indisponivel`; base vazia → HIST; base velha → HIST; base ≤ 0 →
  `indisponivel`.
- **D3 parâmetros:** dois campos novos no `ParametrosPrecos` com padrão (5 e 2), obrigatórios no bloco `fase1` do
  yaml (como os outros). Os testes que montam `ParametrosPrecos(...)` à mão herdam 5 e 2 sem mudar.
- **D4 `mercado_dia`:** `montar_mercado_dia(..., params_precos=None)`; sem ele, lê o yaml
  (`carregar_parametros_precos()`). Assim o `gerar.py` não muda na Fase 2 (fica só para a Fase 5).
- **D5 experimento:** usa o mesmo N do bloco `fase1` (como volatilidade, volume e beta).

### 1.4 Casos de teste com VALORES ESPERADOS (conferidos)

Todas as fábricas: `tests/fabrica_precos.py` (`pregoes_uteis`, `precos_de`, `indices_de`, `cadastro_de`).
`pregoes_uteis(n)` = dias úteis seg-sex desde 2025-01-02 (sem feriados).

**A. `defasagem_pregoes`:** coluna `X` = `[NaN, 1, NaN, NaN, 4, NaN]` em `pregoes_uteis(6)` →
`[NaN, 0.0, 1.0, 2.0, 0.0, 1.0]`.

**B. `variacao` com borda.** `CAL = pregoes_uteis(12)` (índice 6 = 2025-01-10, 7 = 2025-01-13, 8 = 2025-01-14);
fechamento (None = sem preço):
- `AAAA3` = `[100, None×5, 106, 107, 108, 109, 110, 111]` (5 pregões faltando)
- `BBBB3` = `[100, None×6, 107, 108, 109, 110, 111]` (6 faltando)
- `CCCC3` = `[100, 101, None, 103, 104, 105, 106, 107, 108, 109, 110, 111]` (1 faltando)

`g = grade_de_precos(precos, CAL, "fechamento", ["AAAA3","BBBB3","CCCC3"])`:

| n | defasagem_max | ticker | linha (data) | valor | status |
|---|---|---|---|---|---|
| 1 | 5 | AAAA3 | 6 (2025-01-10) | 0.06000000000000005 | ok (defasagem 5 = N, vale) |
| 1 | 5 | BBBB3 | 7 (2025-01-13) | NaN | historico_insuficiente (defasagem 6 = N+1) |
| 1 | None | BBBB3 | 7 | 0.07000000000000006 | ok (comportamento antigo) |
| 1 | 5 | BBBB3 | 8 (2025-01-14) | 0.009345794392523255 | ok |
| 1 | 5 | CCCC3 | 3 (2025-01-07) | 0.01980198019801982 | ok (1 pregão faltando na base: vale, como hoje) |
| 1 | 0 | CCCC3 | 3 | NaN | historico_insuficiente |
| 1 | 0 | AAAA3 | 7 | 0.009433962264151052 | ok |
| 2 | 5 | AAAA3 | 7 | 0.07000000000000006 | ok |
| 2 | 5 | BBBB3 | 8 | NaN | historico_insuficiente |
| 2 | None | BBBB3 | 8 | 0.08000000000000007 | ok |
| 2 | 0 | CCCC3 | 3 | 0.01980198019801982 | ok (alvo = linha 1, com valor) |

**C. `calcular_precos` com a regra** (mesmos preços do caso B + `precos_de("IBOV", CAL, [1000 + i for i in range(12)])`;
`cadastro_de([("AAAA3","1","S","ON"), ("BBBB3","2","S","ON"), ("CCCC3","3","S","ON")])`;
`ParametrosPrecos(janelas={"d1": 1, "n2": 2}, volume_pregoes=20, volatilidade_retornos=20, beta_pregoes=252,
beta_minimo=120, setor_minimo=3, setor_excluir="empresa")` (N = 5 pelo padrão); `Exclusoes()`), em t = CAL[7]:

| indicador | AAAA3 | BBBB3 |
|---|---|---|
| `cotacao.variacao_dia` | 0.009433962264151052 ok | NaN historico_insuficiente |
| `variacao_preco.d1` | 0.009433962264151052 ok | NaN historico_insuficiente |
| `rentabilidade.d1` | 0.009433962264151052 ok | NaN historico_insuficiente |
| `rentabilidade.n2` | 0.07000000000000006 ok | 0.07000000000000006 ok (defasagem 5) |
| `rentabilidade.ibov.d1` | 0.0009940357852882276 ok | idem |
| `rentabilidade.setor.d1` | 0.009433962264151052 ok | idem |
| `rentabilidade.setor.n2` | 0.01904761904761898 ok | idem |

Com `dataclasses.replace(params, base_defasagem_max_pregoes=10**9)`: BBBB3 `cotacao.variacao_dia`,
`variacao_preco.d1` e `rentabilidade.d1` = 0.07000000000000006 ok; o resto igual.

**D. `rentabilidade.setor` (razão da `SETOR_SEM`).** `CALS = pregoes_uteis(16)` (linha 15 = 2025-01-23);
`AAAA3 = [10 + i for i in range(16)]`; `BBBB3 = [20, 21, 22] + [None]*10 + [25, 26, 27.3]`;
`cad = cadastro_de([("AAAA3","1","S","ON"), ("BBBB3","2","S","ON")])`;
`gaj = grade_de_precos(precos, CALS, "fechamento_ajustado", ["AAAA3","BBBB3"])`;
`r = rentabilidade_setor_sem_empresa(gaj, cad, ["AAAA3","BBBB3"], ["AAAA3","BBBB3"], {"d1":1,"n2":2,"n3":3},
"empresa", defasagem_max=5)`, coluna `AAAA3`, linha 15:
d1 = 0.050000000000000044 ok; n2 = NaN historico_insuficiente; n3 = NaN historico_insuficiente.
Com `defasagem_max=None`: d1 = 0.050000000000000044, n2 = 0.09200000000000008, n3 = 0.09200000000000008 (todos ok:
o bug, a base cai no buraco e a efetiva é a linha 2).

**E. Sem lacunas, nada muda.** Grade sintética:
~~~python
rng = np.random.default_rng(20261024)
idx = indice_pregoes([d.date() for d in pd.bdate_range("2024-01-02", periods=400)])
g = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (400, 3)), axis=0), index=idx, columns=["A", "B", "C"])
g.iloc[50:55, 0] = np.nan; g.iloc[100:103, 1] = np.nan; g.iloc[300, 2] = np.nan   # lacunas de 5, 3 e 1
~~~
Para n em (1, 21, 126, 252): `variacao(g, n, 5).valor.equals(variacao(g, n).valor)` e o mesmo com `.status` → True.
Depois `g.iloc[50:56, 0] = np.nan` (lacuna de 6): para cada n, exatamente **1** célula de status difere, na coluna
A, na data `idx[55 + n]`: n=1 → 2024-03-20; n=21 → 2024-04-17; n=126 → 2024-09-11; n=252 → 2025-03-06 (lá o novo é
historico_insuficiente).

**F. Sem vazamento.** Com a grade de E (lacuna de 6), para n em (1, 21) e para t em `idx[[60, 76, 120, 399]]`:
`variacao(g.loc[:t], n, 5)` na linha t == `variacao(g, n, 5)` na linha t (valor igual ou NaN dos dois lados;
status igual).

**G. IDIV real reduzido (Fase 2).** `cal = [d.date() for d in pd.bdate_range("2024-12-30", "2026-10-22")]` (474
pregões); `ind = indices_de([("2024-12-30","IDIV",1000), ("2026-10-20","IDIV",1600), ("2026-10-21","IDIV",1605),
("2026-10-22","IDIV",1607)])`; `precos = precos_de("PETR4", cal, [1.0]*474)`; params com
`janelas={"d1":1,"m1":21,"m6":126,"a1":252}` (N = 5 pelo padrão); `res = calcular_indices(precos, ind, cal, params)`.
Datas-alvo neste calendário: d1 2026-10-21, m1 2026-09-23, m6 2026-04-29, a1 2025-11-04.

| t | d1 | m1 | m6 | a1 |
|---|---|---|---|---|
| 2026-10-22 | 0.0012461059190032042 ok (base 21/10) | NaN HIST | NaN HIST | NaN HIST |
| 2026-10-21 | 0.0031250000000000444 ok (base 20/10) | NaN HIST | NaN HIST | NaN HIST |
| 2026-10-20 | NaN HIST (alvo 19/10, efetiva 30/12/2024) | NaN HIST | NaN HIST | NaN HIST |

Com `base_defasagem_max_pregoes=10**9` (o bug): em 2026-10-22, m1 = m6 = a1 = 0.607 ok (`approx`, abs 1e-12).

**H. `cdi_dia` (Fase 2).** `CALC = pregoes_uteis(10)`; CDI 0.05 só em CALC[0..3] (até 2025-01-07):
- t = CALC[8] (2025-01-14): `cdi_dia(ind, t, CALC, 5)` = `(0.0005, "ok", Timestamp("2025-01-07"))` (5 pregões de atraso).
- t = CALC[9] (2025-01-15): `cdi_dia(ind, t, CALC, 5)` = `(NaN, "indisponivel", None)` (6); sem `cal`:
  `(0.0005, "ok", Timestamp("2025-01-07"))` (antigo).

**I. IPCA (Fase 2).** `IPCA_12` e `IPCA_TAB` copiados de `tests/test_fatos_indices.py:42-49`:
- `ipca_12m(indices_de(IPCA_12), date(2026,3,10), 2)` = `(0.061677811864498056, "ok")` (approx 1e-12; atraso 2);
  `ipca_12m(..., date(2026,4,10), 2)` = `(NaN, "indisponivel")` (atraso 3); sem o parâmetro: `(0.0616778..., "ok")`.
- `rentabilidade_ipca(indices_de(IPCA_TAB), CAL_IPCA, n, 2)` com `CAL_IPCA = pregoes_uteis(120, inicio="2025-01-01")`
  e n = nº de pregões de 2025-02-14 até t: t = 2025-05-14 → 0.01201999999999992 ok (atraso 2); t = 2025-06-16 →
  NaN `indisponivel` (atraso 3); t = 2025-06-16 sem o parâmetro → 0.01201999999999992 ok.
- `indice_ipca(indices_de([("2025-07-01","IPCA",0.26), ("2025-08-01","IPCA",0.50)]), cal, 2)` com
  `cal = [date(2025,8,15), date(2025,9,15), date(2025,10,15), date(2025,11,14), date(2025,12,15)]`:
  valores `[100.0, 100.49999999999999, 100.49999999999999, NaN, NaN]` (approx 1e-9), status
  `[ok, ok, ok, indisponivel, indisponivel]`. Sem o parâmetro: `[100.0, 100.5, 100.5, 100.5, 100.5]`, todos `ok`.

**J. `variacao_dia` do `mercado_dia` (Fase 2).** `CALM = pregoes_uteis(10)`;
`BRENT = [80, None×6, 84, 85, 86]`; `USDBRL = [5.0, None×5, 5.3, 5.4, 5.5, 5.6]`;
`ins = SimpleNamespace(precos=<as duas>, cal=CALM, t=CALM[7])`:
`_cotacao_de_indice(ins, "BRENT", "USD/barril", 5)` → `variacao_dia` = `{"valor": None, "status": "historico_insuficiente"}`,
`fechamento` = `{"valor": 84.0, "status": "ok"}`; `_cotacao_de_indice(ins, "USDBRL", "BRL/USD", 5)` em t = CALM[7] →
`variacao_dia.valor` = 0.018867924528301883 ok; em t = CALM[6] → 0.06000000000000005 ok (defasagem 5).

**K. Experimento (Fase 3).** `cal = pregoes_uteis(30)` (linha 26 = 2025-02-07, 29 = 2025-02-12);
`AAAA3 = [10 + 0.1*i for i in range(20)] + [None]*6 + [13.0, 13.1, 13.2, 13.3]`;
`BBBB3 = [20 + 0.1*i for i in range(21)] + [None]*5 + [25.0, 25.1, 25.2, 25.3]`;
mais `IBOV = [100 + i for i in range(30)]`, `USDBRL = [5.0]*30`, `BRENT = [80.0]*30`; `mascara` toda True; setor `S`
para os dois; CNPJ "1" e "2"; `_params()` e `_params_precos()` de `tests/test_exp_variaveis.py` (N = 5 pelo padrão).

| variável | linha | AAAA3 | BBBB3 |
|---|---|---|---|
| ret_1d | 26 | NaN | 0.13636363636363646 |
| ret_1d | 27 | 0.007692307692307665 | 0.0040000000000000036 |
| ret_5d | 26 | 0.09243697478991586 | 0.13636363636363646 |
| ret_5d | 29 | 0.11764705882352944 | 0.15000000000000013 |
| ret_20d | 29 | 0.22018348623853212 | 0.2105263157894739 |
| ret_vs_setor | 26 | NaN | NaN |
| ret_vs_setor | 27 | 0.0036923076923076614 | -0.0036923076923076614 |

Com `base_defasagem_max_pregoes=10**9`: ret_1d linha 26 AAAA3 = 0.09243697478991586; ret_vs_setor linha 26 =
-0.043926661573720605 (AAAA3) e 0.043926661573720605 (BBBB3); o resto igual.

---

## 2. Diagnóstico: lacunas (Fase 4)

### 2.1 O que já existe e é reusado

| Para quê | Onde |
|---|---|
| Leitura pela camada (sem SQL próprio) | `fontes.ler_tabela("precos")`, `fontes.ler_tabela("indices")` (como `temas.secao_retornos_suspeitos`, `temas.py:1141-1181`) |
| Calendário | `calendario.pregoes(precos)` (`calendario.py:184-189`) |
| Seção, tabela, nota "pulada" | `regras.nova_secao`, `regras.adicionar_tabela` (`regras.py:49-56`); `temas._existe`, `temas._pulada` (`temas.py:127-134`; `historico.py:14` já importa assim) |
| Registro da seção | `diagnostico/__main__.py:62-77` (lista `secoes`) |
| Parecido (não serve direto: lista dias, não trechos, e não vê o fim) | `regras.buracos_por_ticker` (`regras.py:286-305`) |

### 2.2 Regras

- **v1-precos:** cada ticker menos `IBOV`, linhas com `fechamento_ajustado` preenchido, só nos pregões; trechos de
  pregões sem valor com **mais de N** pregões, **só entre o 1º e o último valor do ticker** (ação que ainda não
  existia ou que saiu não é acusada).
- **v1-indices:** IDIV, SMLL e IFIX: trechos com mais de N pregões entre o 1º valor e o último, **e** o trecho final
  (depois do último valor até o último pregão) se tiver mais de N. CDI: **qualquer** pregão sem taxa no meio (a
  janela do CDI exige todas as taxas) e o trecho final com mais de N (o CDI de t pode chegar depois). IPCA: meses
  faltando entre o 1º e o último mês, e o atraso no fim: do mês seguinte ao último até (mês do último pregão − M).
- Nota, não divergência. Tabelas com colunas `["serie", "inicio", "fim", "tamanho", "unidade"]`, datas em texto ISO
  (`"2025-01-06"`; IPCA `"2025-01"`), unidade `"pregões"` ou `"meses"`, ordem: série, depois início.

### 2.3 Casos com VALORES ESPERADOS (conferidos)

`cal = pregoes_uteis(20)`: 0 = 2025-01-02, 1 = 01-03, 2 = 01-06, 3 = 01-07, 4 = 01-08, 5 = 01-09, 6 = 01-10,
7 = 01-13, 8 = 01-14, 9 = 01-15, 10 = 01-16, 11 = 01-17, 12 = 01-20, 13 = 01-21, 14 = 01-22, 15 = 01-23, 16 = 01-24,
17 = 01-27, 18 = 01-28, 19 = 01-29.

**L1 `lacunas_em_pregoes(datas, cal, minimo, minimo_fim=None)`**, `v = [cal[i] for i in (0,1,8,9,10,11,12,14,15)]`:
- `(v, cal, 5)` → `[(date(2025,1,6), date(2025,1,13), 6)]`
- `(v, cal, 0)` → `[(date(2025,1,6), date(2025,1,13), 6), (date(2025,1,21), date(2025,1,21), 1)]`
- `(v, cal, 5, minimo_fim=3)` → `[(date(2025,1,6), date(2025,1,13), 6), (date(2025,1,24), date(2025,1,29), 4)]`
- `(v, cal, 5, minimo_fim=5)` → `[(date(2025,1,6), date(2025,1,13), 6)]`
- `([cal[i] for i in (0,6,7)], cal, 5)` → `[]` (lacuna de exatamente 5)
- `([], cal, 5)` → `[]`; `([cal[i] for i in range(10,20)], cal, 5)` → `[]` (começo tardio não é lacuna);
  `([date(2025,1,4)], cal, 5)` → `[]` (sábado: fora do calendário, ignorado).

**L2 `lacunas_em_meses(meses, ate=None)`**, `m = ["2024-11", "2024-12", "2025-03", "2025-04"]`:
- `(m)` → `[("2025-01", "2025-02", 2)]`
- `(m, pd.Period("2025-08", "M"))` → `[("2025-01", "2025-02", 2), ("2025-05", "2025-08", 4)]`
- `(m, pd.Period("2025-04", "M"))` → `[("2025-01", "2025-02", 2)]`; `([], pd.Period("2025-04", "M"))` → `[]`.

**L3 seção** (`fontes.ler_tabela` trocado por `monkeypatch` que devolve `PRECOS` ou `INDICES` pelo nome; `mapa =
fontes.carregar_mapa()`; `existentes = {fontes.nome_real("precos"), fontes.nome_real("indices")}`; yaml real:
N = 5, M = 2). `sel = lambda idx: [cal[i] for i in idx]`.
- PRECOS (`precos_de(t, datas, [10.0]*len(datas))`): `IBOV` em todos; `AAAA3` em `[0,1]+range(8,20)`;
  `BBBB3` em `range(10,20)`; `CCCC3` em `range(13)`; `DDDD3` em `[0..4]+range(10,20)` (lacuna de 5: não entra).
- INDICES (`indices_de`): `IDIV` em `[0..3]+range(10,14)`; `SMLL` em todos menos 7..11 (5: não entra); `CDI` em todos
  menos o 15; `IPCA` em `"2024-08-01"`, `"2024-10-01"`, `"2024-11-01"` (último pregão 2025-01-29 → `ate` = 2024-11).
- Tabela "Lacunas em v1-precos (mais de 5 pregões)": `[["AAAA3", "2025-01-06", "2025-01-13", 6, "pregões"]]`.
- Tabela "Lacunas em v1-indices": `[["CDI", "2025-01-23", "2025-01-23", 1, "pregões"], ["IDIV", "2025-01-08",
  "2025-01-15", 6, "pregões"], ["IDIV", "2025-01-22", "2025-01-29", 6, "pregões"], ["IPCA", "2024-09", "2024-09", 1,
  "meses"]]`.
- `secao["notas"]` == as duas frases abaixo; `secao["divergencias"] == []`:
  1. `"1 lacunas de mais de 5 pregões em 1 tickers de v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker): as janelas com base dentro delas saem historico_insuficiente (fase1.base_defasagem_max_pregoes = 5)"`
  2. `"4 lacunas em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)"`
- Só `IBOV` em PRECOS e `INDICES = indices_de([])`: notas
  `["nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker)", "nenhuma lacuna em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e mais de 5 no fim; IPCA: meses faltando e atraso de mais de 2 meses no fim)"]`, `tabelas == []`.
- PRECOS sem `IBOV`: notas `["sem pregão com preço do IBOV: checagem não feita"]`.
- `existentes = set()`: 1 nota começando com `"pulada: tabela ausente"`; `existentes` só com precos: 2 notas, a 1ª
  é a de precos e a 2ª começa com `"pulada: tabela ausente"`.

---

## 3. Problema 2: pasta limpa (Fase 5)

### 3.1 Decisão

**Apagar, não pasta nova.** Logo depois de ler os insumos (rodada que vai gerar pacotes), `gerar` apaga da pasta de D
os arquivos com os 9 nomes de pacote da 8.5 (`acoes.json` ... `experimento_top.json`); depois grava o que esta rodada
gerar. No fim, a pasta tem exatamente os pacotes de `pacotes_enviados` + `execucao.json` + arquivos estranhos.
Por que não pasta nova: o `execucao.json` (rodada em andamento e numeração `_rodada_anterior`, `gerar.py:60-65`)
já é gravado na pasta antes da leitura, e trocar de pasta mudaria a numeração das rodadas e o `--pasta` do CLI.
Apagar os 9 de uma vez (e não só os "não publicados") também resolve o pacote que falha na rodada 2 e deixaria o
arquivo velho da rodada 1.
- Nunca apaga `execucao.json` (traz a rodada), nem `*.tmp`, nem qualquer outro nome (ex.: `notas.txt`).
- Vale para a carga completa (`saida_completa/<D>/`) e para o envio diário (`saida/<D>/`): os dois usam o mesmo `gerar`.
- **Trava:** não apaga nada se a pasta for a pasta do estado (`saida/estado/`, que tem arquivos com os mesmos nomes).
- **Rodada `falhou`** (`registrar_execucao`, `gerar.py:313-325`, e erro de leitura, `gerar.py:126-135`): não apaga;
  se houver pacotes de rodada anterior, o `execucao.json` ganha o aviso
  `"Pacotes de uma rodada anterior de {d} continuam na pasta (não refeitos nesta rodada): {lista}."` (lista na ordem
  de `ORDEM`, separada por ", "). Ver seção 0, item 7.

### 3.2 Casos com VALORES ESPERADOS (conferidos)

Fixtures e auxiliares de `tests/test_saida_gerar.py` (`banco_teste`, `modelos_dir`, `_gerar`, `_execucao`,
`D = 2025-10-22`, `PARAMS`, `SAIDA_NAO`, `SAIDA_SIM`, `SETE`, `ARQUIVOS`, `AGORA`).
`NOVE = "acoes.json, series_diarias.json, mercado_dia.json, resumo_acao.json, fundamentos_trimestrais.json, proventos.json, noticias_dia.json, experimento_historico.json, experimento_top.json"`.

- **P1 carga completa com resíduo:** `pasta = tmp_path / "saida_completa" / "2025-10-22"`; antes, criar
  `experimento_top.json` e `experimento_historico.json` (texto `"{}"`) e `notas.txt` (texto `"minhas notas"`).
  `gerar(D, ler=banco_teste(), pasta_saida=pasta, pasta_modelos=modelos_dir, pasta_registros=tmp_path / "registros",
  agora=AGORA, existe_composicao=False, params_treino=PARAMS, params_saida=SAIDA_NAO, completo=True)`.
  `sorted(p.name for p in pasta.iterdir())` == `["acoes.json", "execucao.json", "fundamentos_trimestrais.json",
  "mercado_dia.json", "notas.txt", "noticias_dia.json", "proventos.json", "resumo_acao.json", "series_diarias.json"]`;
  `notas.txt` continua `"minhas notas"`; execução rodada 1, `ok`, `[p["pacote"] for p in pacotes_enviados] == SETE`.
- **P2 envio diário repetido:** `_gerar(tmp_path, banco_teste(), modelos=modelos_dir, params_saida=SAIDA_SIM)` e
  depois o mesmo com `params_saida=SAIDA_NAO`: lista == `["acoes.json", "execucao.json", "fundamentos_trimestrais.json",
  "mercado_dia.json", "noticias_dia.json", "proventos.json", "resumo_acao.json", "series_diarias.json"]`; rodada 2, `ok`.
- **P3 `falhou` depois de `ok`:** `pasta = _gerar(..., params_saida=SAIDA_SIM)`; criar `notas.txt` (`"x"`);
  `registrar_execucao(D, "falhou", coleta_status={"consultado": False, "nota": "teste"}, avisos=["aviso da coleta"],
  agora=AGORA, pasta_saida=pasta, params_saida=SAIDA_SIM)`. Nomes == `{f"{n}.json" for n in ARQUIVOS} | {"notas.txt"}`
  (nada apagado); execução: rodada 2, `falhou`, `pacotes_enviados == []`, `avisos == ["aviso da coleta",
  "Pacotes de uma rodada anterior de 2025-10-22 continuam na pasta (não refeitos nesta rodada): " + NOVE + "."]`.
- **P4 erro de leitura depois de `ok`:** `pasta = _gerar(..., params_saida=SAIDA_SIM)`; depois
  `_gerar(tmp_path, ler_quebrado, modelos=modelos_dir, params_saida=SAIDA_SIM)` com `ler_quebrado` levantando
  `RuntimeError("host=10.0.0.1 user=segredo")` → `pytest.raises(ErroSaida)` (`from processamento.saida.insumos
  import ErroSaida`). Nomes == os 10 de `ARQUIVOS`; execução rodada 2, `falhou`, `avisos == ["falha ao ler a coleta
  (RuntimeError)", "Pacotes de uma rodada anterior de 2025-10-22 continuam na pasta (não refeitos nesta rodada): " + NOVE + "."]`.
- **P5 `_limpar_pacotes` (unidade):** em `tmp_path / "d"`, criar `acoes.json`, `experimento_top.json`, `execucao.json`,
  `notas.txt`, `acoes.json.tmp` → `_limpar_pacotes(pasta)` == `["acoes.json", "experimento_top.json"]`; sobram
  `{"execucao.json", "notas.txt", "acoes.json.tmp"}`. Em `tmp_path / "estado"` com `acoes.json`:
  `_limpar_pacotes(estado, proibida=estado)` == `[]` e o arquivo continua.
- **Não mudam:** `tests/test_rotina_executar.py::test_caso_2_sem_entrega_ate_0945_grava_so_o_falhou` (`["execucao.json"]`)
  e `tests/test_saida_gerar.py::test_caso_8_erro_na_leitura_fecha_a_execucao_como_falhou` (pasta sem pacotes: sem aviso novo).

---

## 4. Testes existentes que mudam de gabarito

| Teste | Motivo |
|---|---|
| `tests/test_fatos_banco.py::test_idiv_m1_ok_em_21_10_2026` (banco; só o usuário roda) | base m1 de 21/10/2026 cai no buraco de 2025: esperado passa a `historico_insuficiente`; d1 `ok` (seção 0, item 1) |

Nenhum outro (protótipo com a suíte inteira verde). Ganham asserts novos sem mudar os antigos:
`tests/test_fatos_parametros.py::test_yaml_real_traz_o_bloco_fase1` (as 2 chaves) e a lista parametrizada de erros.

---

## 5. Pegadinhas para copiar em TODO despacho

- Projeto em `C:/Users/danie/Desktop/TCC/Arquivos/processamento-tcc`, Python 3.12, `./.venv/Scripts/python.exe`.
  Responder em português. **Não fazer commits.**
- **Banco da coleta é só leitura e o usuário do `.env` TEM permissão de escrita:** não conectar no banco, não ler o
  `.env`, não rodar `python -m processamento.diagnostico`, `python -m processamento.saida`,
  `python -m processamento.rotina` nem `pytest -m banco`. **SQL só em `processamento/fontes.py` ou em
  `processamento/diagnostico/`, e só executado por `fontes.executar_leitura`** (aqui: nenhum SQL novo; a seção nova
  usa `fontes.ler_tabela`).
- **Testes sem rede e sem banco real:** `banco_teste` (SQLite em memória, `tests/conftest.py`), fábricas de
  `tests/fabrica_*.py` ou `monkeypatch` de `fontes.ler_tabela`.
- **Não ler, não executar e não importar nada de `extracao-dados-tcc-main/`** (nem `tcc_scraper`).
- **YAML:** números e booleanos sem aspas (`5`, `false`); datas, horas e caminhos entre aspas.
- **Ausência = NaN/None + `status`, nunca 0.**
- **Vazamento temporal é bug:** em t, só dados até t (a regra só olha para trás: `ffill` e `shift`).
- pandas 3 (Copy-on-Write): nada de atribuição encadeada (`df[c][i] = x`); use `.loc`, `.iloc` num DataFrame
  próprio, `where`, `mask`.
- Funções de `fatos/` e as puras do diagnóstico não fazem I/O.
- Não inventar gabarito: os valores esperados estão neste plano. Se um teste não bater, **reportar o valor obtido**
  em vez de mudar o esperado. Floats: `pytest.approx(x, abs=1e-12)` (IPCA base 100: `abs=1e-9`).
- Pronto = `./.venv/Scripts/python.exe -m pytest -q` sem falhas (mais o comando da fase). Durante fases em paralelo,
  falha num arquivo de outra fase: rodar só os testes da sua fase e avisar.

---

## 6. Ordem e paralelismo

- **Fase 5 a qualquer momento** (independente de tudo).
- **Fase 1 primeiro** entre as do problema 1 (põe as chaves obrigatórias no yaml e o parâmetro novo da `variacao`).
- Depois da Fase 1, **em paralelo:** Fases 2, 3 e 4 (arquivos disjuntos).
- Fase 6 (especificação) depois da aprovação do usuário; pode correr junto.
- Verificação final (executor): `pytest -q` com tudo junto.

| Fase | O quê | Arquivos | Depende de |
|---|---|---|---|
| 1 | núcleo da regra | `processamento/config/parametros.yaml` (bloco `fase1`), `processamento/fatos/precos.py`, `processamento/fatos/series.py` (só `rentabilidade_setor_sem_empresa`), `tests/test_base_velha.py` (novo), `tests/test_fatos_parametros.py` | - |
| 2 | índices, CDI, IPCA, mercado_dia | `processamento/fatos/indices.py`, `processamento/fatos/series.py` (só `indice_ipca`), `processamento/saida/pacotes_fatos.py`, `processamento/saida/pacote_series.py`, `tests/test_base_velha_indices.py` (novo), `tests/test_fatos_banco.py` | 1 |
| 3 | experimento | `processamento/experimento/variaveis.py`, `tests/test_base_velha_experimento.py` (novo) | 1 |
| 4 | diagnóstico | `processamento/diagnostico/lacunas.py` (novo), `processamento/diagnostico/__main__.py`, `tests/test_diagnostico_lacunas.py` (novo) | 1 |
| 5 | pasta limpa | `processamento/saida/gerar.py`, `tests/test_saida_gerar.py` | - |
| 6 | especificação | `ESPECIFICACAO.md` | aprovação |

---

## 7. Fases para o implementador

### Fase 1: núcleo da regra

**1.1 `processamento/config/parametros.yaml`**, bloco `fase1`, logo depois da linha `  setor_excluir: "empresa"  # ...`
(antes de `retorno_suspeito_min`):
~~~yaml
  base_defasagem_max_pregoes: 5        # janela: a base (último valor até a data-alvo t−n) só vale se estiver no máximo N pregões antes da data-alvo; senão historico_insuficiente (seção 6, "Base velha")
  ipca_defasagem_max_meses: 2          # IPCA: último mês conhecido no máximo N meses antes do mês de t (1 = normal; 2 = início do mês); senão indisponivel
~~~

**1.2 `processamento/fatos/precos.py`**
- `_CHAVES_FASE1` (`:23-34`): acrescentar `"base_defasagem_max_pregoes"` e `"ipca_defasagem_max_meses"`.
- `ParametrosPrecos` (`:42-55`): no fim, `base_defasagem_max_pregoes: int = 5` e `ipca_defasagem_max_meses: int = 2`.
- Depois de `_inteiro_positivo` (`:58-62`), função nova:
~~~python
def _inteiro_nao_negativo(valor: object, onde: str) -> int:
    """Confere um inteiro >= 0 (bool não conta); levanta `ErroParametrosPrecos` se não bater."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroParametrosPrecos(f"{onde} deve ser um inteiro maior ou igual a zero (recebeu {valor!r})")
    return valor
~~~
- `carregar_parametros_precos`, dentro do `ParametrosPrecos(...)` (`:99-112`), depois de `retorno_suspeito_pregoes_nivel=...,`:
~~~python
        base_defasagem_max_pregoes=_inteiro_nao_negativo(
            bloco["base_defasagem_max_pregoes"], "fase1.base_defasagem_max_pregoes"
        ),
        ipca_defasagem_max_meses=_inteiro_positivo(bloco["ipca_defasagem_max_meses"], "fase1.ipca_defasagem_max_meses"),
~~~
- Trocar a função `variacao` inteira (`:162-167`) por:
~~~python
def defasagem_pregoes(g: pd.DataFrame) -> pd.DataFrame:
    """Pregões desde o último valor de cada coluna, em cada linha (0 = tem valor no próprio pregão).

    NaN antes do 1º valor da coluna. Só olha para trás (sem vazamento).
    """
    pos = np.arange(len(g), dtype=float)[:, None]
    ultimo = pd.DataFrame(np.where(g.notna().to_numpy(), pos, np.nan), index=g.index, columns=g.columns).ffill()
    return pd.DataFrame(pos - ultimo.to_numpy(), index=g.index, columns=g.columns)


def variacao(g: pd.DataFrame, n: int, defasagem_max: int | None = None) -> Grade:
    """Variação contra a última cotação até a data-alvo t−n (base as-of: `ffill` antes do `shift`).

    `defasagem_max` (seção 6, "Base velha"): a base só vale se a data efetiva (último valor até a data-alvo) está
    no máximo `defasagem_max` pregões antes da data-alvo; senão `historico_insuficiente`. None = sem limite (só
    testes antigos; o código de produção sempre passa `fase1.base_defasagem_max_pregoes`). Valor em t é exigido.
    """
    base = g.ffill().shift(n)
    valor = g / base - 1
    regras = [(g.isna(), INDISPONIVEL), (base.isna(), HIST)]
    if defasagem_max is not None:
        regras.append((defasagem_pregoes(g).shift(n) > defasagem_max, HIST))
    regras.append((base <= 0, INDISPONIVEL))
    return montar_grade(valor, _status(g, regras))
~~~
- `calcular_precos` (`:399-411`): logo antes de `res["cotacao.variacao_dia"] = ...` (`:400`), criar
  `n_max = params.base_defasagem_max_pregoes` e passar `n_max` como 3º argumento em **todas** as chamadas de
  `variacao` da função: `:400` `variacao(g_fech, 1, n_max)`; `:407` `variacao(g_aj, n, n_max)`; `:408`
  `variacao(g_fech, n, n_max)`; `:410` `variacao(ibov_aj, n, n_max)`; e em `:404-405`
  `rentabilidade_setor_sem_empresa(..., params.setor_excluir, suspeitos=suspeitos, defasagem_max=n_max)`.
- **Retorno suspeito (decisão do usuário, 24/10/2026, substitui a seção 0 item 5):** variação através de lacuna
  maior que N pregões não é retorno diário: conta como ausente (NaN), nunca como suspeita. `retornos_suspeitos(g_aj,
  minimo, maximo, defasagem_max=None)`: com `defasagem_max`, o retorno as-of do dia só vale onde a defasagem do retorno
  de 1 pregão (data-alvo = pregão anterior; mesma `defasagem_pregoes` da regra) é ≤ `defasagem_max`; acima, NaN (não
  suspeito). Todos os chamadores passam `params.base_defasagem_max_pregoes` (`precos.py` ~:368 e ~:403,
  `diagnostico/temas.py` `secao_retornos_suspeitos`, e qualquer outro achado por grep). `retornos_asof` não muda.
  **Casos (tests/test_base_velha.py, 1G):** um ticker, pregões p0..p8 consecutivos do calendário:
  (a) 10.0 em p0, vazio de p1 a p6, 30.0 em p7, 30.0 em p8 → com `defasagem_max=5`: p7 **não** suspeito e retorno
  ausente (defasagem 6); p8 retorno 0.0; sem `defasagem_max` (comportamento antigo): p7 suspeito (+200%).
  (b) 10.0 em p0, vazio de p1 a p5, 30.0 em p6 → defasagem 5: p6 suspeito (retorno 2.0), igual ao antigo.
  (c) série sem lacunas com um salto de +150% → suspeito com e sem a regra.

**1.3 `processamento/fatos/series.py`** (só `rentabilidade_setor_sem_empresa`, `:234-260`)
- Assinatura: trocar `suspeitos: pd.DataFrame | None = None) -> dict[str, Grade]:` por
  `suspeitos: pd.DataFrame | None = None, defasagem_max: int | None = None) -> dict[str, Grade]:`.
- Docstring: acrescentar "base velha (mais de `defasagem_max` pregões antes da data-alvo): HIST".
- `:252`: `v = variacao(serie.valor[[col]], n, defasagem_max)`.

**1.4 Testes**
- `tests/test_fatos_parametros.py`: em `test_yaml_real_traz_o_bloco_fase1`, acrescentar
  `assert params.base_defasagem_max_pregoes == 5` e `assert params.ipca_defasagem_max_meses == 2`; na lista
  parametrizada de `test_parametros_invalidos_levantam_erro`, acrescentar 4 tuplas:
  `(lambda d: d["fase1"].__setitem__("base_defasagem_max_pregoes", -1), "fase1.base_defasagem_max_pregoes")`,
  `(lambda d: d["fase1"].__setitem__("base_defasagem_max_pregoes", True), "fase1.base_defasagem_max_pregoes")`,
  `(lambda d: d["fase1"].__setitem__("ipca_defasagem_max_meses", 0), "fase1.ipca_defasagem_max_meses")`,
  `(lambda d: d["fase1"].pop("base_defasagem_max_pregoes"), "faltam chaves")`.
  E um teste novo: com `base_defasagem_max_pregoes = 0` no yaml temporário, carrega e o campo vale 0.
- `tests/test_base_velha.py` (novo): casos **A, B, C, D, E, F** da seção 1.4. Imports: `from fabrica_precos import
  cadastro_de, pregoes_uteis, precos_de`; de `processamento.fatos.precos`: `HIST, OK, ParametrosPrecos,
  calcular_precos, defasagem_pregoes, grade_de_precos, indice_pregoes, variacao`; `from processamento.fatos.series
  import rentabilidade_setor_sem_empresa`; `from processamento.exclusoes import Exclusoes`; `dataclasses`, `numpy`,
  `pandas`, `pytest`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_base_velha.py tests/test_fatos_parametros.py tests/test_fatos_variacao.py tests/test_fatos_series.py tests/test_fatos_setor_empresa.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 2: índices, CDI, IPCA e `mercado_dia` (depois da Fase 1)

**2.1 `processamento/fatos/indices.py`**
- Depois de `_k` (`:53-57`), função nova:
~~~python
def _atraso_meses(d, k: pd.Period) -> int:
    """Meses entre o mês de d e K(d) (1 = mês anterior já conhecido, o normal)."""
    return (pd.Timestamp(d).to_period("M") - k).n
~~~
- `rentabilidade_ipca` (`:87`): assinatura `(indices, cal, n, defasagem_max_meses: int | None = None)`; logo depois
  do bloco `if kb is None or kt is None: ... continue` (`:99-102`), inserir:
~~~python
        if defasagem_max_meses is not None and _atraso_meses(t, kt) > defasagem_max_meses:
            valores.append(np.nan)
            status.append(INDISPONIVEL)
            continue
~~~
- `cdi_dia` (`:120-126`): assinatura `(indices, t, cal: list | None = None, defasagem_max: int | None = None)`;
  depois do `if ate.empty: return (np.nan, INDISPONIVEL, None)`, inserir:
~~~python
    if cal is not None and defasagem_max is not None:
        idx = indice_pregoes(cal)
        atraso = int(((idx > ate.index[-1]) & (idx <= pd.Timestamp(t).normalize())).sum())
        if atraso > defasagem_max:   # última taxa velha demais (seção 6, "Base velha")
            return (np.nan, INDISPONIVEL, None)
~~~
  Docstring: "com `cal` e `defasagem_max`: mais de `defasagem_max` pregões entre a última taxa e t → indisponivel".
- `ipca_12m` (`:129-145`): assinatura `(indices, t, defasagem_max_meses: int | None = None)`; logo depois de
  `if kt is None or not meses: return (np.nan, HIST)`, inserir
  `if defasagem_max_meses is not None and _atraso_meses(t, kt) > defasagem_max_meses: return (np.nan, INDISPONIVEL)`
  (em duas linhas, com o `return` indentado).
- `calcular_indices` (`:161-164`): `rentabilidade_ipca(indices, cal, n, params.ipca_defasagem_max_meses)`,
  `variacao(grade_pontos, n, params.base_defasagem_max_pregoes)`, `variacao(grade_ivvb, n, params.base_defasagem_max_pregoes)`.
  `rentabilidade_cdi` **não muda**.

**2.2 `processamento/fatos/series.py`** (só `indice_ipca`, `:113-137`)
- import (`:14`): acrescentar `_atraso_meses` ao `from processamento.fatos.indices import ...`.
- Assinatura: `indice_ipca(indices, cal, defasagem_max_meses: int | None = None)`; logo depois de
  `fator = _fator_ipca(meses, ks[inicio], ks[i])` (`:129`), inserir:
~~~python
        if fator is not None and defasagem_max_meses is not None and _atraso_meses(idx[i], ks[i]) > defasagem_max_meses:
            fator = None   # IPCA parado: o ponto não fica "reto", sai indisponivel
~~~
- Docstring: "Com `defasagem_max_meses`: ponto com K(d) mais de N meses antes do mês de d: `indisponivel`".

**2.3 `processamento/saida/pacote_series.py`** `:171`: `ipca = indice_ipca(ins.indices, cal, params_precos.ipca_defasagem_max_meses)`.

**2.4 `processamento/saida/pacotes_fatos.py`**
- import (`:26-35`): acrescentar `carregar_parametros_precos`.
- `_cotacao_de_indice` (`:143-153`): assinatura `(ins, ticker, unidade, defasagem_max: int | None = None)`; `:147`:
  `var = variacao(g_fech, 1, defasagem_max)`.
- `montar_mercado_dia` (`:156`): assinatura
  `(ins, grades, gerado_em, dados_ate, params_precos: ParametrosPrecos | None = None)`; primeiras linhas:
  `params_precos = carregar_parametros_precos() if params_precos is None else params_precos`,
  `n_max = params_precos.base_defasagem_max_pregoes`, `m_max = params_precos.ipca_defasagem_max_meses`; trocar
  `cdi_dia(ins.indices, ins.t)` por `cdi_dia(ins.indices, ins.t, ins.cal, n_max)` e `ipca_12m(ins.indices, ins.t)`
  por `ipca_12m(ins.indices, ins.t, m_max)`; as 3 chamadas de `_cotacao_de_indice` ganham `n_max` como 4º argumento.
  **Não** mexer em `gerar.py` (a Fase 5 é dona dele; o padrão lê o mesmo yaml).

**2.5 Testes**
- `tests/test_base_velha_indices.py` (novo): casos **G, H, I, J** da seção 1.4 (para J: `from types import
  SimpleNamespace`; `from processamento.saida.pacotes_fatos import _cotacao_de_indice`; para G, `ParametrosPrecos`
  com os 7 campos obrigatórios, como `_params` de `tests/test_fatos_indices.py:65-74`).
- `tests/test_fatos_banco.py`: trocar `test_idiv_m1_ok_em_21_10_2026` por
  `test_idiv_m1_historico_insuficiente_e_d1_ok_em_21_10_2026` (docstring: "IDIV com 2022-2024 e desde 20/10/2026
  (2025 falta): a base m1 cai no buraco (seção 6, Base velha)"): linha m1 com `status == HIST` (importar `HIST` de
  `processamento.fatos.precos`) e linha d1 com `status == OK`. **Não rodar** (é de banco; o usuário roda).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_base_velha_indices.py tests/test_fatos_indices.py tests/test_fatos_series.py tests/test_saida_pacotes_fatos.py tests/test_saida_series.py tests/test_vazamento_fatos.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 3: experimento (depois da Fase 1)

**3.1 `processamento/experimento/variaveis.py`**
- `:97`: `res[nome] = fatos_precos.variacao(g_aj, n, params_precos.base_defasagem_max_pregoes).valor`
- `:99`: `ret_dia = fatos_precos.variacao(g_aj, 1, params_precos.base_defasagem_max_pregoes).valor`
- Docstring de `variaveis_de_preco`: acrescentar "retornos com base as-of até `fase1.base_defasagem_max_pregoes`
  pregões antes da data-alvo (seção 6, Base velha)".

**3.2 Testes:** `tests/test_base_velha_experimento.py` (novo): caso **K** da seção 1.4 (`from test_exp_variaveis
import _params, _params_precos`; `from processamento.experimento.variaveis import variaveis_de_preco`;
`from processamento.fatos import precos as fatos_precos`; `import dataclasses`). Em `tests/test_exp_variaveis.py:244`
nada muda (fábrica sem lacunas).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_base_velha_experimento.py tests/test_exp_variaveis.py tests/test_exp_dataset.py tests/test_vazamento_experimento.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 4: diagnóstico, lacunas (depois da Fase 1)

**4.1 `processamento/diagnostico/lacunas.py` (novo; código conferido no protótipo contra L1-L3)**
~~~python
"""Lacunas nas séries de preços e índices (nota do diagnóstico; seção 6 da especificação, "Base velha").

Só notas e tabelas (não é divergência). Lê só por `fontes.ler_tabela` (camada de leitura, sessão só leitura).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from processamento import calendario, fontes
from processamento.diagnostico.regras import adicionar_tabela, nova_secao
from processamento.diagnostico.temas import _existe, _pulada
from processamento.fatos.precos import carregar_parametros_precos

INDICES_PREGOES = ("CDI", "IDIV", "IFIX", "SMLL")   # ordem da tabela (alfabética); o IPCA vem por último, em meses
COLUNAS = ["serie", "inicio", "fim", "tamanho", "unidade"]
REGRA_INDICES = ("IDIV, SMLL e IFIX: mais de {n} pregões, inclusive no fim; CDI: qualquer pregão sem taxa no meio e "
                 "mais de {n} no fim; IPCA: meses faltando e atraso de mais de {m} meses no fim")


def lacunas_em_pregoes(datas_com_valor, cal: list, minimo: int,
                       minimo_fim: int | None = None) -> list[tuple[date, date, int]]:
    """Trechos de pregões de `cal` sem valor: (1º pregão sem valor, último, nº de pregões).

    No meio (entre o 1º e o último pregão com valor): só trechos com mais de `minimo` pregões. Com `minimo_fim`,
    também o trecho final (depois do último valor até o último pregão de `cal`) se tiver mais de `minimo_fim`.
    Começo tardio não é lacuna. Datas fora de `cal` são ignoradas. Sem valor: [].
    """
    cal = [pd.Timestamp(d).date() for d in cal]
    tem = {pd.Timestamp(d).date() for d in datas_com_valor}
    pos = [i for i, d in enumerate(cal) if d in tem]
    if not pos:
        return []
    res = []
    i = pos[0]
    while i <= pos[-1]:
        if cal[i] in tem:
            i += 1
            continue
        j = i
        while cal[j + 1] not in tem:   # termina: cal[pos[-1]] tem valor
            j += 1
        if j - i + 1 > minimo:
            res.append((cal[i], cal[j], j - i + 1))
        i = j + 1
    final = len(cal) - 1 - pos[-1]
    if minimo_fim is not None and final > minimo_fim:
        res.append((cal[pos[-1] + 1], cal[-1], final))
    return res


def lacunas_em_meses(meses, ate: pd.Period | None = None) -> list[tuple[str, str, int]]:
    """Trechos de meses sem valor entre o 1º e o último mês conhecidos ("AAAA-MM", "AAAA-MM", nº de meses).

    Com `ate`: também do mês seguinte ao último conhecido até `ate` (inclusive), se `ate` passa do último.
    """
    ms = sorted({pd.Period(m, "M") for m in meses})
    if not ms:
        return []
    res = [(str(a + 1), str(b - 1), (b - a).n - 1) for a, b in zip(ms[:-1], ms[1:]) if (b - a).n > 1]
    if ate is not None and ate > ms[-1]:
        res.append((str(ms[-1] + 1), str(ate), (ate - ms[-1]).n))
    return res
~~~
(continuação do mesmo arquivo)
~~~python
def secao_lacunas(ler, mapa: dict, existentes: set) -> dict:
    """Lacunas de v1-precos (por ticker) e de v1-indices (IDIV, SMLL, IFIX e CDI em pregões; IPCA em meses)."""
    secao = nova_secao("Lacunas nas séries de preços e índices")
    if not _existe(mapa, existentes, "precos"):
        secao["notas"].append(_pulada(mapa, "precos"))
        return secao
    params = carregar_parametros_precos()
    n, m = params.base_defasagem_max_pregoes, params.ipca_defasagem_max_meses
    precos = fontes.ler_tabela("precos", ler=ler)
    cal = calendario.pregoes(precos)
    if not cal:
        secao["notas"].append("sem pregão com preço do IBOV: checagem não feita")
        return secao

    validos = precos.dropna(subset=["fechamento_ajustado"])
    linhas = []
    for tk, grupo in validos.groupby("ticker", sort=True):
        if tk == "IBOV":
            continue
        for ini, fim, tam in lacunas_em_pregoes(pd.to_datetime(grupo["data"]).dt.date, cal, n):
            linhas.append([tk, ini.isoformat(), fim.isoformat(), tam, "pregões"])
    regra = "fechamento_ajustado, só dentro do período com preço de cada ticker"
    if linhas:
        secao["notas"].append(
            f"{len(linhas)} lacunas de mais de {n} pregões em {len({l[0] for l in linhas})} tickers de v1-precos "
            f"({regra}): as janelas com base dentro delas saem historico_insuficiente "
            f"(fase1.base_defasagem_max_pregoes = {n})")
        adicionar_tabela(secao, f"Lacunas em v1-precos (mais de {n} pregões)", COLUNAS, linhas)
    else:
        secao["notas"].append(f"nenhuma lacuna de mais de {n} pregões em v1-precos ({regra})")

    if not _existe(mapa, existentes, "indices"):
        secao["notas"].append(_pulada(mapa, "indices"))
        return secao
    indices = fontes.ler_tabela("indices", ler=ler).dropna(subset=["valor"])
    linhas = []
    for nome in INDICES_PREGOES:
        datas = pd.to_datetime(indices.loc[indices["indice"] == nome, "data"]).dt.date
        for ini, fim, tam in lacunas_em_pregoes(datas, cal, 0 if nome == "CDI" else n, minimo_fim=n):
            linhas.append([nome, ini.isoformat(), fim.isoformat(), tam, "pregões"])
    meses = pd.to_datetime(indices.loc[indices["indice"] == "IPCA", "data"]).dt.to_period("M")
    for ini, fim, tam in lacunas_em_meses(meses, pd.Timestamp(cal[-1]).to_period("M") - m):
        linhas.append(["IPCA", ini, fim, tam, "meses"])
    regra = REGRA_INDICES.format(n=n, m=m)
    if linhas:
        secao["notas"].append(f"{len(linhas)} lacunas em v1-indices ({regra})")
        adicionar_tabela(secao, "Lacunas em v1-indices", COLUNAS, linhas)
    else:
        secao["notas"].append(f"nenhuma lacuna em v1-indices ({regra})")
    return secao
~~~

**4.2 `processamento/diagnostico/__main__.py`**
- import (`:17`): `from processamento.diagnostico import consultas, historico, lacunas, temas`.
- Na lista `secoes` (`:62-77`), logo depois da linha de `"Retornos diários suspeitos"`:
  `_seguro("Lacunas nas séries de preços e índices", lacunas.secao_lacunas, ler, mapa, existentes),`.

**4.3 Testes:** `tests/test_diagnostico_lacunas.py` (novo): casos **L1, L2, L3** da seção 2.3. `mapa` como fixture
(`return fontes.carregar_mapa()`); `ler` = `None` (a seção não faz SQL: tudo passa pelo `ler_tabela` trocado);
servir as tabelas com um dicionário mutável `tabs = {"precos": PRECOS, "indices": INDICES}` e
`monkeypatch.setattr(fontes, "ler_tabela", lambda tabela, **_kw: tabs[tabela].copy())`.
`INDICES` vazio = `indices_de([])`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_diagnostico_lacunas.py tests/test_diagnostico_main.py tests/test_diagnostico_temas.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`. **Não** rodar `python -m processamento.diagnostico` (lê o banco).

### Fase 5: pasta limpa (independente)

**5.1 `processamento/saida/gerar.py`**
- Depois de `PASTA_COMPLETA_PADRAO = ...` (`:49`):
~~~python
ARQUIVOS_PACOTES = tuple(f"{nome}.json" for nome in ORDEM)   # os 9 pacotes da 8.5; o execucao.json fica (traz a rodada)
AVISO_PACOTES_ANTERIORES = ("Pacotes de uma rodada anterior de {d} continuam na pasta (não refeitos nesta rodada): "
                            "{lista}.")


def _limpar_pacotes(pasta: Path, proibida: Path | None = None) -> list[str]:
    """Apaga da pasta de D os pacotes de rodadas anteriores (só os nomes de `ARQUIVOS_PACOTES`; seção 8.5).

    Nunca apaga o `execucao.json`, `*.tmp` nem outros arquivos. Não faz nada se `pasta` for a `proibida` (a pasta
    do estado do envio, que tem arquivos com os mesmos nomes). Devolve os nomes apagados, na ordem de `ORDEM`.
    """
    if proibida is not None and Path(pasta).resolve() == Path(proibida).resolve():
        return []
    apagados = []
    for nome in ARQUIVOS_PACOTES:
        arquivo = Path(pasta) / nome
        if arquivo.is_file():
            arquivo.unlink()
            apagados.append(nome)
    return apagados


def _aviso_pacotes_anteriores(pasta: Path, d: date) -> list[str]:
    """Aviso da rodada `falhou` quando ficam na pasta pacotes de uma rodada anterior de D (lista vazia se não há)."""
    presentes = [nome for nome in ARQUIVOS_PACOTES if (Path(pasta) / nome).is_file()]
    if not presentes:
        return []
    return [AVISO_PACOTES_ANTERIORES.format(d=d.isoformat(), lista=", ".join(presentes))]
~~~
- Erro de leitura (`:131-132`): a lista de avisos `[motivo]` do `_execucao(...)` vira
  `[motivo, *_aviso_pacotes_anteriores(pasta, d)]`.
- Logo depois do bloco `try/except` da leitura (antes de `aviso = aviso_composicao(...)`, `:137`):
~~~python
    # 2b) pasta limpa (seção 8.5): os pacotes de rodadas anteriores saem antes de gravar os desta rodada
    _limpar_pacotes(pasta, proibida=Path(pasta_estado) if pasta_estado is not None else params_saida.pasta_estado)
~~~
- `registrar_execucao` (`:323-324`): `list(avisos)` vira `[*avisos, *_aviso_pacotes_anteriores(pasta, d)]`.
- Docstring de `gerar`: acrescentar "Antes de gravar, apaga da pasta os pacotes de rodadas anteriores (só os 9
  nomes da 8.5); a rodada `falhou` não apaga e avisa".

**5.2 Testes:** no fim de `tests/test_saida_gerar.py`, casos **P1 a P5** da seção 3.2 (imports novos:
`from processamento.saida.gerar import AVISO_PACOTES_ANTERIORES, _limpar_pacotes, registrar_execucao`;
`from processamento.saida.insumos import ErroSaida`; `ARQUIVOS`, `SETE`, `AGORA`, `PARAMS` já estão no arquivo).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_saida_gerar.py tests/test_saida_completo.py tests/test_rotina_executar.py tests/test_vazamento_saida.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`. **Não** rodar `python -m processamento.saida` (lê o banco).

### Fase 6: especificação (só `ESPECIFICACAO.md`; o usuário aprova)

1. Seção 5, linha "Rentabilidade": `(base as-of)` → `(base as-of, no máximo 5 pregões antes da data-alvo; seção 6, "Base velha")`.
2. Seção 6, linha nova logo depois de "Retorno diário suspeito":
   `| Base velha (24/10/2026) | Toda janela de n pregões (variação do preço, rentabilidade da ação, do IBOV, do IVVB11, do IDIV, SMLL e IFIX, rentabilidade.setor, variacao_dia de IBOV/USDBRL/BRENT e ret_1d/ret_5d/ret_20d/ret_vs_setor do modelo) usa a base as-of: o último valor até a **data-alvo** cal[k−n] (k = posição de t no calendário). **Defasagem** = nº de pregões entre a data efetiva e a data-alvo; a base vale com defasagem ≤ fase1.base_defasagem_max_pregoes (5); acima, historico_insuficiente. O ponto final já exige valor em t. Ex.: IDIV com dados até 2024 e de novo desde 20/10/2026: em 22/10/2026, d1 ok (base 21/10) e m1, m6, a1 historico_insuficiente (antes saíam +60,7%). CDI: a janela exige a taxa de todos os pregões em [base, t) (lacuna = indisponivel); cdi_dia sai indisponivel se a última taxa tem mais de 5 pregões de atraso. IPCA: com o último mês conhecido mais de fase1.ipca_defasagem_max_meses (2) meses antes do mês de t, as janelas, o ipca_12m e os pontos do índice IPCA saem indisponivel. Não mudam: volatilidade, volume relativo, beta, 52 semanas, exposições, salto_abertura, a cadeia SETOR_SEM e as séries base 100 (ponto sem valor já é indisponivel). Retorno diário através de lacuna maior que 5 pregões não é retorno diário: conta como ausente, nunca como suspeito. O diagnóstico lista as lacunas |`
   (pôr crases nos nomes de campos, como no resto da tabela).
3. Seção 7.3, detalhes: depois de `ret_1d/5d/20d com base "as-of" (igual à rentabilidade do painel)` acrescentar
   `, no máximo 5 pregões antes da data-alvo (seção 6, "Base velha")`.
4. Seção 8.3 item 2 (`mercado_dia`): depois de `` `cdi_dia` (fração ao dia) e `cdi_data` `` acrescentar
   `(com a última taxa mais de 5 pregões antes de t: indisponivel e cdi_data vazio)`.
5. Seção 8.3 item 4 (`series_diarias`), depois de "A interface recorta o período e parte do mesmo ponto dividindo pelo
   primeiro valor do recorte.": `Para a interface (decidido em 24/10/2026): se o primeiro ponto do recorte estiver `indisponivel`, não desenhar a linha e mostrar "histórico insuficiente" (como no resumo_acao/mercado_dia). O IPCA com mais de 2 meses de atraso sai indisponivel nos pontos.`
6. Seção 8.5, depois do parágrafo "Nomes dos arquivos": `**Pasta limpa (24/10/2026):** toda rodada que gera pacotes (envio diário e carga completa) apaga, antes de gravar, os arquivos de pacote de rodadas anteriores da pasta de D (só os 9 nomes acima; o execucao.json e qualquer outro arquivo ficam). A pasta termina com os pacotes de pacotes_enviados + execucao.json. A rodada falhou (só o execucao.json) não apaga nada: os pacotes de uma rodada anterior do mesmo D continuam e o execucao avisa ("Pacotes de uma rodada anterior de D continuam na pasta ...").`
7. Seção 9, "Decisões da etapa 3": bullet "Lacunas de preço": acrescentar `Desde 24/10/2026, a base vale só até 5 pregões de defasagem (seção 6, "Base velha").`; bullet "IPCA": acrescentar `Desde 24/10/2026: último mês conhecido mais de 2 meses antes do mês de t → indisponivel.`; bullet "CDI": depois de `cdi_dia = taxa da última data ≤ t` acrescentar `(indisponivel com mais de 5 pregões de atraso)`.
8. Seção 9, "Decisões da etapa 5", E13: `ret_1d usa o último preço disponível` → `ret_1d usa o último preço disponível até 5 pregões antes da data-alvo (seção 6, "Base velha")`.
9. Seção 9, "Acréscimo de 24/10/2026 (histórico novo)", H5: trocar por `**H5 IDIV:** substituída pela regra da base velha (24/10/2026): com 2025 faltando, o m1 do IDIV em 21/10/2026 sai historico_insuficiente (o ok vinha da base de 2024).`
10. Seção 9, bloco novo no fim: `**Acréscimo de 24/10/2026 (base velha e pasta limpa; plano em docs/plano_base_velha.md)**` com 4 itens: BV1 regra (seção 6, "Base velha"; fase1.base_defasagem_max_pregoes: 5, fase1.ipca_defasagem_max_meses: 2); BV2 experimento com a mesma regra nos ret_*; BV3 diagnóstico: seção "Lacunas nas séries de preços e índices" (nota); BV4 pasta limpa (8.5).
11. Seção 10, linha "Histórico de IDIV, SMLL e IFIX (hoje só 20 e 21/10/2026) ...": trocar o parêntese por
    `(hoje de 2022 a 2024 e desde 20/10/2026; 2025 inteiro falta: janelas com base no buraco saem historico_insuficiente, seção 6)`.

**Verificação:** nenhuma (texto). Sugestão à sessão principal (inline, não é do implementador): pegadinha nova no
`CLAUDE.md`: "18. Base velha: janela com base mais de 5 pregões antes da data-alvo = `historico_insuficiente`
(`fase1.base_defasagem_max_pregoes`); IPCA com mais de 2 meses de atraso = `indisponivel`; a pasta de D é limpa antes
de gravar (seção 8.5)."

---

## 8. Riscos

- **Fase 1 quebra cópias do yaml:** as duas chaves passam a ser obrigatórias no bloco `fase1`. No protótipo nenhum
  teste quebrou (os testes copiam o yaml real); um yaml antigo fora do repositório quebraria com "faltam chaves".
- **Desempenho:** `defasagem_pregoes` é uma passada numpy por chamada de `variacao`; a `rentabilidade.setor` chama
  `variacao` por ticker e por janela (~90 × 4 colunas de ~1.700 linhas): custo desprezível frente aos ~2 min da rodada.
- **Teste de banco do IDIV** muda (seção 4); o usuário roda `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`.
- **Conferir no pacote real** (usuário): `python -m processamento.saida --data 2026-10-23 --completo` → em
  `mercado_dia.indices`, IDIV/SMLL/IFIX com m1, m6, a1 `historico_insuficiente` e d1 `ok`; a pasta
  `saida_completa/2026-10-23/` sem `experimento_top.json` e `experimento_historico.json`; depois rodar o
  diagnóstico para ver as lacunas reais (ações e índices) e quantas linhas do experimento perdem `ret_*`.
