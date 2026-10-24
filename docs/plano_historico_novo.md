# Plano: histórico novo (24/10/2026), decisões 1 a 7

Arquiteto, 24/10/2026. Decisões do usuário fechadas (não reabrir). Nenhum número aqui veio do banco: os
fatos do banco são os medidos pelo usuário (enunciado); os gabaritos dos testes saem das fábricas
(`tests/fabrica_*.py`, `tests/dados/`, `banco_teste`). **(conferido)** = valor obtido rodando o código atual
(ou um protótipo do código novo, comparado com o atual) sobre a fábrica, sem banco e sem rede.

---

## Resumo

| Item | O quê | Fase |
|---|---|---|
| 1 | **URGENTE (rotina real segunda 26/10 às 8h).** (a) horários da B3 desde 04/11/2019, quartas de cinzas 2020-2024 e 57 feriados (2019-12-31 a 2024-05-30) no `parametros.yaml`; (b) `classificar_noticias` só pede o horário do pregão que cai na **data da notícia** (cálculo preguiçoso) | **1** (sozinha, primeiro) |
| 2 | Balanço velho: `fundamentos.balanco_idade_max_meses: 15`; `data_fim_periodo + 15 meses < t` → P/L, P/VP, ROE, margens, EBITDA, endividamento e payout 12m `indisponivel` (também P/L e P/VP diários) | 2 |
| 3a, 3c | Diagnóstico: `data_mudanca` vira nota; texto vazio em `v1-noticias.titulo` vira nota com até 10 ids | 3 |
| 3b | Diagnóstico: hora real / "só data" N1-A / sem hora por ano (e ano × origem); divergência `noticia_sem_hora` só sem a marca "date" | 4 |
| 3d | Diagnóstico: seção nova (composição sem preço; `corrigir_horas`; cobertura do experimento) | 5 |
| 3e | Troca de ação por BDR não une históricos (JBSS3 → JBSS32) | 6 |
| 4 | Teste de banco do IDIV espera `ok` | inline (sessão principal) |
| 6 | Textos da `ESPECIFICACAO.md` | 8 |
| 7 | `saida.publicar_top_provisorio` (padrão `false`): top 5 gerado e registrado, mas `experimento_top`/`experimento_historico` não gravados | 7 |

**Por que a Fase 1 resolve a segunda-feira:** hoje o calendário começa em 30/12/2019 (IBOV) e
`classificar_noticias` (`processamento/calendario.py:311-313`) calcula `fechamento/abertura` de **todos** os
pregões: qualquer pregão antes de 11/03/2024 levanta `ErroCalendario`. Ela é chamada por três caminhos, e os
três quebram na rotina real: dataset do experimento (`experimento/noticias.py:108`, pacote
`experimento_top`), painel de notícias (`fatos/noticias.py:66`, pacote `noticias_dia`) e dias de resultado
E11 (`experimento/resultados.py:29`, balanços desde 2022). (a) sozinho já cobre tudo desde 04/11/2019; (b)
deixa o calendário robusto a qualquer pregão antigo sem notícia.

**Teste recomendado ao usuário antes de segunda (lê o banco; o subagente NÃO roda):**
`python -m processamento.saida --data 2026-10-23 --completo` (grava só em `saida_completa/`, não mexe em
`saida/estado/` nem em `registros/`). Conferir: sai sem `ErroCalendario`, status `ok`, e o **tempo da rodada**
(o histórico de preços passou de ~1 para ~7 anos: o `execucao.json` mostra `inicio`/`fim`; o prazo é 9h45 e
o top vale até 10h). E `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`.

---

## 0. Onde o código não permite seguir a decisão à risca (listado, não resolvido)

1. **Item 7, "`pacotes_enviados` lista só os 8 restantes":** `pacotes_enviados` nunca listou o `execucao`
   (`gerar.py:259-273`, `ORDEM` tem 9 pacotes). Sem os dois do experimento, a lista fica com **7** pacotes; a
   pasta `saida/<D>/` fica com **8 arquivos** (os 7 + `execucao.json`). O plano segue assim.
2. **Item 1(b), notícia que "precisa" de um pregão sem horário:** com a regra preguiçosa, só a notícia cuja
   **data** (São Paulo) é um pregão sem horário levanta erro. Notícia de sábado depois de uma sexta sem
   horário, ou de antes das 08:00 do pregão seguinte, vai para a noite da sexta **sem erro** (não precisa do
   fechamento da sexta: o dia já acabou). O resultado é idêntico ao do algoritmo antigo sempre que o antigo não
   levanta erro (conferido em 6.573 instantes; seção 1.3, caso 1D).
3. **Item 3e, JBSS3 no dataset sem setor:** `montar_dataset` tira o setor do cadastro **pelo ticker**
   (`experimento/dataset.py:99,105`); JBSS3 não está no cadastro, então `setor` = vazio: `ret_vs_setor` e
   `tom_setor` vazios nas linhas dele, e ele não entra na média do setor das outras. É o mesmo que já acontece
   com todo ticker que só está na composição. A empresa sai certa (CNPJ da JBS pela raiz). Herdar o setor pela
   empresa fica para decisão do usuário.
4. **Item 3e, efeitos colaterais:** a série `JBSS32` do `series_diarias` muda de âncora (1º dia passa a ser
   09/06/2025): no próximo envio diário ela vai inteira com `substituir_serie: true` (uma vez). O diagnóstico
   `secao_tickers` monta o próprio mapa de mudanças por SQL (`temas.py:605-611`) e continua unindo JBSS3 →
   JBSS32 (só classifica classes de proventos; não muda nenhum número do painel).
5. **Item 2, borda:** RESOLVIDO pelo usuário (24/10/2026): conta até o fim do mês (`+ MonthEnd(0)`): 30/09/2024 →
   31/12/2025; 29/02/2024 → 31/05/2025; 30/11/2024 → 28/02/2026.
   **Bradespar** (03847461000192) continua em `cnpjs_sem_balanco` (tudo `indisponivel`, inclusive o histórico
   2022-2023 de `fundamentos_trimestrais`/`payout_por_ano`); com a regra nova ela poderia sair da lista e
   mostrar o histórico, com os indicadores atuais `indisponivel` automaticamente. Decisão do usuário.
6. **Item 3b, contagem:** a tabela atual conta **linhas** (pares id × ticker); a nova conta **artigos
   distintos** (`COUNT(DISTINCT id)`), como os números medidos pelo usuário (8,9% / 0,0% / 91,1% em 2024).
7. **Item 7, sem modelo / texto da nota na carga completa:** se não há modelo, o top falha e a rodada continua
   `parcial` (como hoje: o top 5 não foi gerado nem registrado). Na carga completa a nota diz "registrado",
   embora a carga completa nunca grave registro (texto único, mais simples).
8. **Item 1, teste de banco do dataset:** só o usuário roda. Além do calendário, o dataset com 2019-2026 pode
   expor outro problema (tempo, memória, dado novo); não há como conferir sem banco.

---

## 1. Item 1: calendário (Fase 1)

### 1.1 O que já existe e é reusado

| Para quê | Onde |
|---|---|
| Validação do yaml (aspas, ordem crescente, feriado em dia útil e fora de `dias_especiais`) | `calendario.py:71-129` (`_validar_periodos`, `_validar_dias_especiais`, `_validar_feriados`) |
| Horário de um dia com dia especial; erro "anterior ao primeiro período" | `calendario.py:192-217` (`horario_b3(d, caminho)`) |
| Instante em SP | `calendario.py:172` (`_instante`) |
| Classificação (a trocar) | `calendario.py:277-324` (`_classificar_instante`, `classificar_noticias`) |
| Únicos chamadores de `classificar_noticias` (todos se beneficiam sem mudança) | `experimento/noticias.py:108`, `fatos/noticias.py:66`, `experimento/resultados.py:29` (E11) |
| `janela_noite`/`janela_pregao` pedem horário só do `t` dado (não mudam); `saida/*` usa só `corte_manha` (não precisa de horário) | `calendario.py:248-274`; `saida/gerar.py:109,310`, `saida/insumos.py:67,75`, `saida/pacote_noticias.py:31,42` |
| Conferência dos feriados contra os pregões reais | `calendario.py:406` (`conferir_feriados`); teste de banco `tests/test_calendario_feriados.py:207-213` |

### 1.2 Decisões técnicas

- **D1-1 yaml:** 9 períodos novos antes de `"2024-03-11"`, 5 quartas de cinzas em `dias_especiais`, 57
  feriados em `feriados_b3` (todos conferidos: dia útil, nenhum em `dias_especiais`; o `parametros.yaml`
  resultante carrega com 99 feriados, conferido).
- **D1-2 regra preguiçosa (por que funciona):** para um instante `ts` de data `dia` (em São Paulo), todo pregão
  de data anterior já fechou antes de `ts`, e todo pregão de data posterior abre depois do corte das 08:00
  dele. Então o algoritmo só precisa do horário do pregão **da própria data**, se houver. Os cortes (08:00)
  não dependem do horário da B3. Caches locais por chamada (`dict`) para horário e corte.
- **D1-3 `caminho`:** `classificar_noticias(..., caminho=None)` e `corte_manha(d, caminho=None)` ganham o
  parâmetro (repassado a `horario_b3`/`carregar_parametros`), para o teste com yaml temporário. Nenhum
  chamador muda.
- **D1-4 `cal`:** normalizar com `_data` no início (`cal = [_data(p) for p in cal]`), como o código antigo
  fazia implicitamente ao chamar `fechamento(p)`.

### 1.3 Casos de teste com VALORES ESPERADOS

**1A `horario_b3` com o yaml real (conferido com o yaml novo):**

| dia | (abertura, fechamento) |
|---|---|
| 2019-11-04 | (10:00, 18:00) |
| 2020-02-26 | (13:00, 18:00) (cinzas) |
| 2020-03-06 | (10:00, 18:00) |
| 2020-03-09 | (10:00, 17:00) |
| 2021-11-05 | (10:00, 17:00) |
| 2021-11-08 | (10:00, 18:00) |
| 2022-03-02 | (13:00, 18:00) (cinzas) |
| 2023-11-03 | (10:00, 17:00) |
| 2023-11-06 | (10:00, 18:00) |
| 2024-02-14 | (13:00, 18:00) (cinzas) |
| 2024-03-08 | (10:00, 18:00) |
| 2024-03-11 | (10:00, 17:00) |
| 2019-11-01 | `ErroCalendario`, mensagem contém "horário da B3 não cadastrado para 2019-11-01: anterior ao primeiro período" |

O teste atual `test_horario_b3_antes_do_primeiro_periodo_erro` (`tests/test_calendario.py:118-120`) usa
2024-03-08, que agora é coberto: trocar por `date(2019, 11, 1)`.

**1B Classificação com o yaml real.** `CAL` = dias úteis que são pregão previsto
(`[d.date() for d in pd.bdate_range(a, b) if e_pregao_previsto(d.date())]`) nos intervalos
2020-02-17..2020-03-13, 2021-11-01..2021-11-19, 2023-10-30..2023-11-10, 2024-03-04..2024-03-15
(50 pregões; sem 2020-02-24/25, 2021-11-02, 2021-11-15, 2023-11-02). `proximo_ao_vivo=None`. (conferido)

| instante (SP) | janela | pregao_ref |
|---|---|---|
| 2020-02-21 18:00:00 | pregao | 2020-02-21 |
| 2020-02-21 18:00:01 | noite | 2020-02-21 |
| 2020-02-25 12:00:00 (Carnaval) | noite | 2020-02-21 |
| 2020-02-26 08:00:00 | noite | 2020-02-21 |
| 2020-02-26 08:00:01 | pre_abertura | 2020-02-26 |
| 2020-02-26 10:30:00 | pre_abertura | 2020-02-26 |
| 2020-02-26 12:59:59 | pre_abertura | 2020-02-26 |
| 2020-02-26 13:00:00 | pregao | 2020-02-26 |
| 2020-02-26 18:00:00 | pregao | 2020-02-26 |
| 2020-02-26 18:00:01 | noite | 2020-02-26 |
| 2020-03-06 17:30:00 | pregao | 2020-03-06 |
| 2020-03-09 17:30:00 | noite | 2020-03-09 |
| 2021-11-05 17:00:00 | pregao | 2021-11-05 |
| 2021-11-05 17:00:01 | noite | 2021-11-05 |
| 2021-11-05 17:30:00 | noite | 2021-11-05 |
| 2021-11-06 12:00:00 | noite | 2021-11-05 |
| 2021-11-08 08:00:00 | noite | 2021-11-05 |
| 2021-11-08 08:00:01 | pre_abertura | 2021-11-08 |
| 2021-11-08 17:30:00 | pregao | 2021-11-08 |
| 2021-11-08 18:00:00 | pregao | 2021-11-08 |
| 2021-11-08 18:00:01 | noite | 2021-11-08 |
| 2021-11-15 12:00:00 (feriado) | noite | 2021-11-12 |
| 2023-11-03 17:30:00 | noite | 2023-11-03 |
| 2023-11-06 17:30:00 | pregao | 2023-11-06 |
| 2024-03-08 17:30:00 | pregao | 2024-03-08 |
| 2024-03-11 17:30:00 | noite | 2024-03-11 |
| NaT | sem_horario | NaT |

**1C Preguiçoso com yaml temporário** (cabeçalho `_CABECALHO_YAML` de `tests/test_calendario.py:56` +
`horarios_b3:` com só `{a_partir_de: "2024-03-11", abertura: "10:00", fechamento: "17:00"}`);
`cal = [d.date() for d in pd.bdate_range("2023-12-27", "2024-03-15")]` (inclui pregões sem horário);
`classificar_noticias(..., caminho=caminho)`. (conferido com o protótipo)

| instante | janela | pregao_ref |
|---|---|---|
| 2024-03-12 09:00:00 | pre_abertura | 2024-03-12 |
| 2024-03-12 17:30:00 | noite | 2024-03-12 |
| 2024-03-13 12:00:00 | pregao | 2024-03-13 |
| 2024-03-15 17:00:00 | pregao | 2024-03-15 |
| 2024-03-11 07:00:00 | noite | 2024-03-08 (sem erro: não precisa do horário de 08/03) |
| 2024-03-09 12:00:00 (sábado) | noite | 2024-03-08 (sem erro) |
| NaT | sem_horario | NaT |

E: uma notícia "2024-03-08 12:00:00" → `pytest.raises(ErroCalendario, match="horário da B3 não cadastrado para 2024-03-08")`.

**1D Igualdade com o algoritmo antigo:** função de referência `_classificar_ingenuo` (código na Fase 1, cópia
do antigo) × `classificar_noticias` novo, yaml real, `CAL` = pregões previstos de 2025-02-24..2025-03-14 e
2025-10-13..2025-11-07; instantes: para cada dia de 2025-02-20..2025-03-18 e 2025-10-09..2025-11-12, um a cada
15 minutos (00:00 a 23:45) mais 08:00:00, 08:00:01, 09:59:59, 10:00:00, 13:00:00, 17:00:00, 17:00:01,
18:00:00, 18:00:01, 23:59:59, e um NaT (6.573 linhas). Para `proximo_ao_vivo` em `None` e
`date(2025, 11, 10)`: `pd.testing.assert_frame_equal(novo, antigo)`. E com os mesmos instantes convertidos
para UTC (`.dt.tz_convert("UTC")`): coluna `janela` igual. (conferido: 0 diferenças)

**1E Feriados (yaml real):** `len(feriados_b3()) == 99`; `e_pregao_previsto`: 2019-12-31 False,
2020-02-25 False, 2020-02-26 True (cinzas), 2021-01-25 False, 2021-07-09 False, 2022-01-25 True,
2023-12-29 False, 2024-05-30 False; `pregao_anterior_previsto(date(2020, 2, 26)) == date(2020, 2, 21)`.
Teste de banco `test_banco_feriados_conferem_com_pregoes_reais`: trocar `date(2024, 8, 1)` por
`date(2019, 12, 30)`; esperado (usuário roda) as duas listas vazias.

---

## 2. Item 2: balanço velho (Fase 2)

### 2.1 O que já existe e é reusado

| Para quê | Onde |
|---|---|
| Foto do balanço de referência (D11), `status_base` | `fatos/trimestres.py:206-235` (`foto_balanco`), `FotoBalanco` frozen `:25-37` |
| Todos os 12 indicadores da empresa começam por `_primeiro_nao_ok(base, ...)`; financeira vem antes (`nao_se_aplica`) | `fatos/fundamentos.py:215-369` (`indicadores_empresa`) |
| Painel no dia | `fundamentos.py:477-488` (laço por CNPJ em `calcular_fundamentos_no_dia`) |
| P/L e P/VP diários (foto por trecho entre entregas) | `fatos/multiplos.py:115-127` |
| Medianas do setor só com status ok (empresa velha sai sozinha) | `fundamentos.py:510-522` + `precos.montar_grade`/`media_setor` (D10) |
| Não mudam (chamam `foto_balanco` direto, sem a regra): `_payout_das_dfps`, `_linhas_da_empresa`, `balanco_referencia_no_dia`, `_cnpjs_com_quantidade_suspeita`, `diagnostico/temas._suspeitas_em` | `fundamentos.py:527-623`, `:652-690`; `temas.py:979` |
| Yield é por ticker, não usa a foto | `fundamentos.py:503-505` |
| Experimento não usa fundamentos (só `normalizar_texto`) | `experimento/noticias.py:15` (único import de `fatos.fundamentos` no experimento) |

### 2.2 Decisões técnicas

- **D2-1 Borda (decidida pelo usuário em 24/10/2026: conta até o FIM DO MÊS):** limite = fim do mês de
  `data_fim + DateOffset(months=meses)` (`+ pd.offsets.MonthEnd(0)`); velho ⇔ `limite < t` (estrito). Ex.: 30/09/2024 vale até
  31/12/2025; 29/02/2024 até 31/05/2025.
- **D2-2 Mecanismo:** `foto_dentro_do_prazo(foto, t, meses)` devolve a foto com `status_base = indisponivel`
  (`dataclasses.replace`) se velha. Aplicada **só** em `calcular_fundamentos_no_dia` e `multiplos_diarios`
  (por dia, depois do cache por trecho, porque a idade cruza 15 meses no meio de um trecho). Como todo
  indicador começa pelo `status_base`, os 12 saem `indisponivel`; bancos e seguradoras continuam
  `nao_se_aplica` onde já eram (a regra da financeira vem antes). Não toca `foto_balanco`, para não mexer em
  `payout_por_ano`, `fundamentos_trimestrais` e `balanco_referencia` (que continua `ok` com as datas do
  balanço usado).
- **D2-3 Parâmetro:** obrigatório no bloco `fundamentos` (como os outros), inteiro > 0; campo do dataclass
  com padrão 15 (testes que montam `ParametrosFundamentos(...)` à mão continuam valendo).

### 2.3 Casos de teste com VALORES ESPERADOS

**2A `balanco_velho(data_fim, t, meses)`** (conferido com `pd.DateOffset`):

| data_fim | t | meses | esperado |
|---|---|---|---|
| 2023-12-31 | 2025-03-31 | 15 | False |
| 2023-12-31 | 2025-04-01 | 15 | True |
| 2024-02-29 | 2025-05-31 | 15 | False |
| 2024-02-29 | 2025-06-01 | 15 | True |
| 2024-09-30 | 2025-12-31 | 15 | False |
| 2024-09-30 | 2026-01-01 | 15 | True |
| 2024-11-30 | 2026-02-28 | 15 | False |
| 2024-11-30 | 2026-03-02 | 15 | True |
| 2025-12-31 | 2026-03-31 | 3 | False |
| 2025-12-31 | 2026-04-01 | 3 | True |
| None | 2026-04-01 | 3 | False |
| pd.NaT | 2026-04-01 | 3 | False |

**2B Integração na fábrica** (`tests/fabrica_fundamentos.py`, `mundo()`), com duas linhas novas para
U e PREJ ficarem "novas" (referência 2026-03-31) e as outras empresas "velhas" (referência 2025-12-31):
```python
cadastro, balancos, acoes, proventos, precos, cal, mudancas = mundo()
extra = pd.concat([
    balanco_de(CNPJ["U"], [_a("ITR", "2026-01-01", "2026-03-31", "2026-03-31", 400, 160, 50, 1350)]),
    balanco_de(CNPJ["PREJ"], [_a("ITR", "2026-01-01", "2026-03-31", "2026-03-31", 400, 160, -40, 1250)]),
])
BAL2 = pd.concat([balancos, extra], ignore_index=True)
DADOS2 = DadosFundamentos(precos, cadastro, BAL2, acoes, proventos, mudancas)
P15 = carregar_parametros_fundamentos()
P3 = dataclasses.replace(P15, balanco_idade_max_meses=3)
```
`g3 = calcular_fundamentos_no_dia(date(2026, 4, 1), cal, DADOS2, EXCL, P3, "empresa")`; `g15` idem com P15.
Velhas em 01/04/2026 com 3 meses: A, BANC, D, BDRX, DUPN, EXTI, K (fim 2025-12-31 + 3 meses = 2026-03-31 < 01/04).
Valores (conferido; ler `g[campo].valor.iloc[0][ticker]` e `g[campo].status.iloc[0][ticker]`; números com
`pytest.approx(rel=1e-12)`; "indisp" = valor NaN e status `indisponivel`):

| ticker | campo | g15 (hoje) | g3 (esperado) |
|---|---|---|---|
| AAAA3 | pl.valor | 5.75 ok | indisp |
| AAAA3 | pvp.valor | 0.7076923076923077 ok | indisp |
| AAAA3 | roe.valor | 0.12307692307692308 ok | indisp |
| AAAA3 | payout.valor | 0.328125 ok | indisp |
| AAAA3 | margem_bruta.valor | 0.41333333333333333 ok | indisp |
| AAAA3 | margem_liquida.valor | 0.10666666666666667 ok | indisp |
| AAAA3 | dividend_yield.valor | 0.05 ok | 0.05 ok (não muda) |
| AAAA3 | pl.setor | 17.142857142857142 ok | 17.142857142857142 ok |
| AAAA3 | pvp.setor | 1.271111111111111 ok | 1.271111111111111 ok |
| UUUU11 | pl.valor | 17.142857142857142 ok | 17.142857142857142 ok |
| UUUU11 | pl.setor | 5.75 ok | indisp (A velha; PREJ com prejuízo) |
| UUUU11 | pvp.setor | 0.5138461538461538 ok | 0.32 ok |
| UUUU11 | roe.setor | 0.02153846153846154 ok | -0.08 ok |
| UUUU11 | payout.setor | 0.328125 ok | indisp |
| UUUU11 | margem_bruta.setor | 0.41311827956989244 ok | 0.4129032258064516 ok |
| PREJ3 | pl.valor | -4.0 lucro_negativo | -4.0 lucro_negativo |
| PREJ3 | pl.setor | 11.446428571428571 ok | 17.142857142857142 ok |
| PREJ3 | pvp.setor | 1.464957264957265 ok | 2.2222222222222223 ok |
| PREJ3 | roe.setor | 0.12635327635327637 ok | 0.12962962962962962 ok |
| PREJ3 | payout.setor | 0.8497767857142857 ok | 1.3714285714285714 ok |
| DDDD3 | ebitda.valor_12m | 111.0 ok | indisp |
| DDDD3 | ebitda.margem | 0.2642857142857143 ok | indisp |
| DDDD3 | endividamento.divida_liquida | 100.0 ok | indisp |
| DDDD3 | endividamento.dl_pl | 0.18518518518518517 ok | indisp |
| DDDD3 | endividamento.caixa_liquido | 0.0 ok | indisp |
| BANC4 | pl.valor | 12.5 ok | indisp |
| BANC4 | pvp.valor | 1.5384615384615385 ok | indisp |
| BANC4 | margem_bruta.valor | NaN nao_se_aplica | NaN nao_se_aplica |
| BANC4 | ebitda.valor_12m | NaN nao_se_aplica | NaN nao_se_aplica |
| BANC4 | endividamento.dl_pl | NaN nao_se_aplica | NaN nao_se_aplica |
| BANC4 | dividend_yield.valor | 0.0 ok | 0.0 ok |
| KKKK3 | pl.valor | 18.75 ok | indisp |
| KKKK3 | dividend_yield.valor | 0.013000000000000001 ok | 0.013000000000000001 ok |

E: com P3 em `t = 2026-03-31` (borda: 2025-12-31 + 3 meses = 2026-03-31, ainda vale), `pl.valor` de AAAA3 = 5.75 ok.

**2C Não mudam:** com `t = date(2026, 4, 1)`, `payout_por_ano(t, DADOS2, EXCL, P3)` ==
`payout_por_ano(t, DADOS2, EXCL, P15)`; idem `tabela_trimestral(t, DADOS2, EXCL, P3/P15)` e
`balanco_referencia_no_dia(t, DADOS2, EXCL)` (`pd.testing.assert_frame_equal`). `balanco_referencia_no_dia`
de AAAA3: `data_fim_periodo` 2025-12-31, `data_entrega` 2026-03-15, status `ok`.

**2D Diários:** `m = multiplos_diarios(DADOS2, cal, EXCL, P3, desde=date(2026, 3, 31))`:
`m["pl"]` em 2026-03-31: AAAA3 5.75 ok; em 2026-04-01: AAAA3 NaN `indisponivel`, UUUU11
17.142857142857142 ok, PREJ3 -4.0 `lucro_negativo`, DDDD3 NaN `indisponivel`. `m["pvp"]` em 2026-04-01:
AAAA3 NaN `indisponivel`, UUUU11 2.2222222222222223 ok, PREJ3 0.32 ok. `m["dividend_yield"]` igual ao de
P15 (`assert_frame_equal` em `.valor` e `.status`). Com P15, `m["pl"]` em 2026-04-01 AAAA3 = 5.75 ok.

**2E Parâmetros:** `test_yaml_real_traz_o_bloco_fundamentos` (`tests/test_fund_parametros.py:33`) ganha
`balanco_idade_max_meses=15`; na lista de inválidos (`:56-75`) acrescentar:
`(lambda d: d["fundamentos"].pop("balanco_idade_max_meses"), "faltam chaves")`,
`(lambda d: d["fundamentos"].__setitem__("balanco_idade_max_meses", 0), "fundamentos.balanco_idade_max_meses")`,
`(lambda d: d["fundamentos"].__setitem__("balanco_idade_max_meses", True), "fundamentos.balanco_idade_max_meses")`,
`(lambda d: d["fundamentos"].__setitem__("balanco_idade_max_meses", "15"), "fundamentos.balanco_idade_max_meses")`.

---

## 3. Item 3: diagnóstico (Fases 3, 4 e 5)

### 3.1 O que já existe e é reusado

| Para quê | Onde |
|---|---|
| Vazios por coluna e divergências | `diagnostico/consultas.py:367-408` (`secao_vazios`), `regras.py:355-387` (`resumo_vazios`, `divergencias_coluna`) |
| Lista `colunas_vazias_conhecidas` | `config/fontes.yaml:39` (só lida em `consultas.py:380`) |
| % com hora (a trocar) | `temas.py:205-224`; `df_ano` é reusado em `temas.py:247` (anos da conferência de fuso) |
| Regra N1-A | `fontes.meia_noite_pacifico` (`fontes.py:460`), `fontes.para_sao_paulo_iso` (`fontes.py:551`) |
| UTC → SP | `fontes.para_sao_paulo_de_utc` (`fontes.py:562`) |
| Ligação notícia ↔ raw_articles | `r.id = CAST(SUBSTRING(n.id, 2) AS UNSIGNED)` (`temas.py:255`) |
| Helpers de mapa/SQL | `temas.py:97-168` (`_existe`, `_nome`, `_tab`, `_col`, `_col_real`, `_pulada`, `_registros`, `_data`, `_ano`) |
| Seções por `fontes.ler_tabela` (monkeypatch nos testes) | `temas.py:1004-1048`, `:1058-1098`; testes `tests/test_diagnostico_temas.py:406-416`, `:493-495` |
| Universo histórico | `universo.montar_universo` (`universo.py:57`), `fontes.ler_composicao` (`fontes.py:681`), `exclusoes.carregar_exclusoes` |
| Raiz/classe/mudanças | `tickers.raiz`, `tickers.aplicar_mudancas`; `fontes.mudancas_como_dict` |
| Orquestração das seções | `diagnostico/__main__.py:62-76` |

### 3.2 Fase 3: `data_mudanca` e texto vazio no título (3a, 3c)

**Decisões:**
- `fontes.yaml`, `mudancas_ticker`: troca `colunas_vazias_conhecidas: [data_mudanca]` por
  `colunas_nota_preenchimento: [data_mudanca]`. Para essas colunas a situação (cheia, parcial, vazia) nunca é
  divergência; vira a nota "`<tabela>.<coluna>` preenchida em N de M linhas" (+ " (K vazias)" se K > 0).
- `fontes.yaml`, `noticias`: nova chave `textos_vazios_nota: [titulo]`. Para essas colunas, texto vazio vira
  nota com até 10 ids (consulta `SELECT DISTINCT <id> AS id ... WHERE <col> = '' ORDER BY id LIMIT 10`; `<id>`
  = 1ª coluna da `chave` da tabela, nome real). Nas demais colunas, texto vazio continua divergência.

**Casos com VALORES ESPERADOS** (as strings esperadas estão entre `«` e `»`, para não confundir com as crases
que fazem parte delas):

| caso | chamada | esperado |
|---|---|---|
| 3A | `divergencias_coluna("v1-mudancas_ticker", "data_mudanca", "cheia", 0, 0, False, False, so_nota_preenchimento=True)` | `[]` |
| 3B | idem com `"vazia"` e com `"parcial"` | `[]` e `[]` |
| 3C | `divergencias_coluna("v1-noticias", "titulo", "cheia", 1, 0, False, False, so_nota_texto_vazio=True)` | `[]` |
| 3D | `divergencias_coluna("v1-noticias", "fonte", "cheia", 2, 0, False, False)` | lista com «`v1-noticias.fonte`: 2 textos vazios ('') em vez de NULL» |
| 3E | `nota_preenchimento("v1-mudancas_ticker", "data_mudanca", 10, 0)` | «`v1-mudancas_ticker.data_mudanca` preenchida em 10 de 10 linhas» |
| 3F | `nota_preenchimento("v1-mudancas_ticker", "data_mudanca", 10, 3)` | «`v1-mudancas_ticker.data_mudanca` preenchida em 7 de 10 linhas (3 vazias)» |
| 3G | `nota_texto_vazio("v1-noticias", "titulo", 1, ["n326413"])` | «`v1-noticias.titulo`: 1 textos vazios ('') (a leitura trata como vazio); ids (até 10): n326413» |
| 3H | `montar_sql_ids_texto_vazio("v1-noticias", "id", "titulo")` | «SELECT DISTINCT `id` AS id FROM `v1-noticias` WHERE `titulo` = '' ORDER BY id LIMIT 10» |
| 3I | os 5 casos atuais de `test_divergencias_coluna` (`tests/test_diagnostico_regras.py:310-322`) | sem mudança |

**3J `secao_vazios` ponta a ponta** (`tests/test_diagnostico_consultas.py`, `ler` falso, `MAPA` real já com o
yaml novo): `existentes = {"v1-noticias", "v1-mudancas_ticker"}`; `df_colunas` com colunas
`tabela, coluna, tipo, nulo, pos`: noticias `id` varchar, `titulo` varchar, `fonte` varchar (pos 1-3);
mudancas `ticker_antigo` varchar, `ticker_novo` varchar, `data_mudanca` date (pos 1-3). `ler(sql)`:
- contém "`v1-noticias`" e "COUNT(*) AS total" → `{"total": [5], "nulos__id": [0], "vazios__id": [0], "nulos__titulo": [0], "vazios__titulo": [1], "nulos__fonte": [0], "vazios__fonte": [2]}`;
- contém "`v1-mudancas_ticker`" e "COUNT(*) AS total" → `{"total": [10], "nulos__ticker_antigo": [0], "vazios__ticker_antigo": [0], "nulos__ticker_novo": [0], "vazios__ticker_novo": [0], "nulos__data_mudanca": [0]}`;
- contém "SELECT DISTINCT" → `{"id": ["n326413"]}`.

Esperado:
- divergências: exatamente uma, tema `coluna_vazia`, tabela `v1-noticias`, detalhe «`v1-noticias.fonte`: 2 textos vazios ('') em vez de NULL»;
- notas, nesta ordem: «`v1-noticias.titulo`: 1 textos vazios ('') (a leitura trata como vazio); ids (até 10): n326413», «`v1-mudancas_ticker.data_mudanca` preenchida em 10 de 10 linhas», «demais colunas 100% preenchidas»;
- tabela com 3 linhas: `["v1-noticias", "titulo", 5, 0, 0.0, "cheia", 1, 0]`, `["v1-noticias", "fonte", 5, 0, 0.0, "cheia", 2, 0]`, `["v1-mudancas_ticker", "data_mudanca", 10, 0, 0.0, "cheia", 0, 0]`.

Variante com `nulos__data_mudanca = [10]`: nenhuma divergência de `data_mudanca`; nota
«`v1-mudancas_ticker.data_mudanca` preenchida em 0 de 10 linhas (10 vazias)».

### 3.3 Fase 4: hora das notícias por ano (3b)

**Decisões:**
- Três consultas (só em `temas.py`, via `ler`), contando **artigos distintos** (`COUNT(DISTINCT id)`):
  (1) totais por (ano, origem) com `sem_hora` = `data_hora_publicacao` NULL ou texto vazio;
  (2) candidatos a meia-noite do Pacífico: linhas com minuto e segundo zerados
  (`SUBSTRING(dhp, 15, 5) = '00:00'`), agrupadas por (ano, origem, instante). É só um filtro grosso para não
  trazer a tabela inteira; o teste exato é em Python: `fontes.para_sao_paulo_iso` + `fontes.meia_noite_pacifico`;
  (3) só se houver Google News sem hora e `raw_articles` existir: (ano, `published_precision`) dessas notícias
  (LEFT JOIN; sem linha em raw_articles = sem marca).
- `hora_real = total − sem_hora − so_data_n1a`; % = `round(x / total * 100, 1)` (None se total 0).
- Tabelas (substituem as duas atuais): "Hora da publicação, por ano (artigos distintos)" com colunas
  `["ano", "total", "hora_real", "pct_hora_real", "so_data_n1a", "pct_so_data_n1a", "sem_hora", "pct_sem_hora"]`
  e "Hora da publicação, por ano e origem (artigos distintos)" com `"origem"` logo depois de `"ano"`.
- `precisao == "date"` → nota; o resto (outro valor ou sem linha) → divergência `noticia_sem_hora` por ano.
  Sem `raw_articles`: nota «Marca 'só data' (raw_articles): pulada: tabela ausente (`raw_articles`)» e todo
  Google News sem hora vira divergência.
- `pct_com_hora_por_ano` (`regras.py:182`) fica (tem teste próprio), só deixa de ser usada.

**Caso 4A** (`_horas_por_ano(ler, MAPA, existentes, secao)`, `existentes = {"v1-noticias", "raw_articles"}`).
`ler(sql)` falso:
- contém "AS sem_hora" → totais
  `{"ano": [2024, 2024, 2025], "origem": ["cvm_ipe", "google_news", "google_news"], "total": [10, 100, 200], "sem_hora": [10, 91, 4]}`;
- contém "'00:00'" → candidatos
  `{"ano": [2025, 2025, 2025, 2025], "origem": ["google_news"] * 4, "instante": ["2025-06-10T04:00:00-03:00", "2025-01-10T05:00:00-03:00", "2025-01-10T04:00:00-03:00", "2025-06-10T10:00:00-03:00"], "n": [150, 30, 6, 2]}`
  (os dois primeiros são 00:00 em Los Angeles; 04:00 em janeiro = 23:00 PST, hora real);
- contém "published_precision" → `{"ano": [2024, 2024, 2024, 2025], "precisao": ["date", "datetime", None, "date"], "n": [85, 5, 1, 4]}`.

Esperado:
- tabela por ano: `[[2024, 110, 9, 8.2, 0, 0.0, 101, 91.8], [2025, 200, 16, 8.0, 180, 90.0, 4, 2.0]]`;
- tabela por ano e origem: `[[2024, "cvm_ipe", 10, 0, 0.0, 0, 0.0, 10, 100.0], [2024, "google_news", 100, 9, 9.0, 0, 0.0, 91, 91.0], [2025, "google_news", 200, 16, 8.0, 180, 90.0, 4, 2.0]]`;
- nota: «89 notícias do Google News sem hora, marcadas 'só data' pela coleta (raw_articles.published_precision = 'date'): 2024: 85, 2025: 4»;
- divergências: uma só, tema `noticia_sem_hora`, tabela `v1-noticias`, detalhe «2024: 6 de 100 sem hora e sem a marca 'só data' em raw_articles»;
- devolve o DataFrame dos totais (coluna `ano` com 2024 e 2025).

**Caso 4B** (sem `raw_articles` em `existentes`, mesmos totais e candidatos; a consulta 3 não pode rodar):
divergências «2024: 91 de 100 sem hora e sem a marca 'só data' em raw_articles» e
«2025: 4 de 200 sem hora e sem a marca 'só data' em raw_articles»; nota
«Marca 'só data' (raw_articles): pulada: tabela ausente (`raw_articles`)»; nenhuma nota "marcadas 'só data'".

**Caso 4C** (`meia_noite_por_ano_origem(df)` puro, candidatos de 4A) → `{(2025, "google_news"): 180}`.

### 3.4 Fase 5: seção nova "Histórico novo" (3d)

Módulo novo `processamento/diagnostico/historico.py` (não toca `temas.py`, para rodar em paralelo com a
Fase 4), com funções **puras** (testadas direto) e uma seção que as cola, registrada em `__main__.coletar`.

**(i) Composição sem preço.** Composição como vem na tabela (SQL próprio, sem a união); preço procurado com
a união: `aplicar_mudancas(t, mudancas) in tickers_com_preco`, onde `tickers_com_preco` = tickers de
`fontes.ler_tabela("precos")` (já unidos; qualquer linha) e
`mudancas = fontes.mudancas_como_dict(fontes.ler_tabela("mudancas_ticker", unir_mudancas=False))`.
Grupo `empresa_do_cadastro` se o ticker é `ticker_antigo` em `v1-mudancas_ticker` **ou** `raiz(t)` é raiz
de algum ticker do cadastro; senão `fora_do_cadastro`. `inicio` = menor `data_inicio`; `fim` = `"vigente"`
se alguma linha tem `data_fim` vazia, senão a maior `data_fim` (texto AAAA-MM-DD); `no_indice_desde_2024` =
`"sim"` se alguma linha tem `data_fim` vazia ou ≥ 2024-01-01, senão `"não"`. Ordem: grupo
(`empresa_do_cadastro` antes) e ticker.

Caso 5A `composicao_sem_preco(comp, tickers_com_preco, mudancas, antigos, tickers_cadastro)`:
`comp` (colunas `ticker, data_inicio, data_fim`, datas Timestamp ou NaT):
PETR4 2021-01-01/NaT; NTCO3 2021-01-01/2025-06-30; ALPA4 2021-01-01/2023-04-30; ALPA4 2023-09-01/2024-04-30;
BRML3 2021-01-01/2022-11-30; CPLE5 2021-01-01/2021-12-31; AXIA6 2024-01-01/NaT; ELET6 2021-01-01/2023-12-31;
GOLL4 2021-01-01/2024-01-02; BRDT3 2021-01-01/2021-08-31.
`tickers_com_preco = {"IBOV", "PETR4", "NATU3", "AXIA3"}`;
`mudancas = {"NTCO3": "NATU3", "ELET6": "AXIA3", "BRDT3": "VBBR3"}`; `antigos = {"NTCO3", "ELET6", "BRDT3"}`;
`tickers_cadastro = {"PETR4", "NATU3", "CPLE3", "AXIA3"}`. Esperado:
```
[["AXIA6", "empresa_do_cadastro", "2024-01-01", "vigente", "sim"],
 ["BRDT3", "empresa_do_cadastro", "2021-01-01", "2021-08-31", "não"],
 ["CPLE5", "empresa_do_cadastro", "2021-01-01", "2021-12-31", "não"],
 ["ALPA4", "fora_do_cadastro", "2021-01-01", "2024-04-30", "sim"],
 ["BRML3", "fora_do_cadastro", "2021-01-01", "2022-11-30", "não"],
 ["GOLL4", "fora_do_cadastro", "2021-01-01", "2024-01-02", "sim"]]
```
(NTCO3 e ELET6 têm preço pela união; PETR4 tem preço.)
Caso 5B `nota_composicao_sem_preco(linhas_5A, 10)` →
«Composição do Ibovespa: 6 de 10 tickers sem nenhum preço em v1-precos (3 código antigo de empresa do cadastro, 3 fora do cadastro); 3 estiveram no índice em 2024 ou depois. O preço é procurado com a união das mudanças de ticker (o código antigo vale pelo atual).»
(10 = tickers distintos da composição.) Lista vazia → «Composição do Ibovespa: todos os 10 tickers têm preço em v1-precos (com a união das mudanças de ticker).»

**(ii) `corrigir_horas`.** SQL (via `ler`): execução mais recente com essa etapa
(`ORDER BY iniciada_em DESC, id DESC LIMIT 1`), com status da execução e da etapa; horários UTC → SP.
Caso 5C `nota_corrigir_horas(df)` com
`{"id": ["2026-10-23-coletar-135621"], "status_execucao": ["agendada"], "status_etapa": ["pendente"], "iniciada_em": ["2026-10-23 16:56:21"], "finalizada_em": [None]}` →
«corrigir_horas: execução mais recente 2026-10-23-coletar-135621 (status agendada), etapa pendente; iniciada em 2026-10-23 13:56, finalizada em — (horário de São Paulo)».
DataFrame vazio → «corrigir_horas: nenhuma execução com essa etapa».
(O horário 16:56:21 UTC é da fábrica; o real o usuário vê no relatório.)

**(iii) Cobertura do experimento.** `u = montar_universo(cal, cadastro, precos, exclusoes, composicao)` com
`fontes.ler_tabela("precos")`, `fontes.ler_tabela("cadastro")`, `fontes.ler_composicao(ler=ler)`; por ano: nº
de pregões (`cal`), linhas com `motivo == "ok"`, mín/mediana/máx de ações ok por pregão (pregão sem ação ok
conta 0) e os valores distintos de `universo` no ano, ordenados e unidos por "/".
Caso 5D `cobertura_por_ano(u, cal)` (conferido): `cal = [2020-12-29, 2020-12-30, 2021-01-04, 2021-01-05, 2021-01-06]`;
cadastro AAAA3 ON, BBBB4 PN, CCCC32 BDR; composição AAAA3 2021-01-01/NaT, DDDD3 2021-01-01/2021-01-05;
preços (colunas `data, ticker, fechamento, fechamento_ajustado`, todos 10.0): IBOV, AAAA3 e CCCC32 nos 5;
BBBB4 nos 3 primeiros; DDDD3 em 2021-01-04 e 2021-01-06; `Exclusoes()`. Ações ok por pregão: 2, 2, 2, 1, 1.
Esperado (colunas `["ano", "pregoes", "linhas_ok", "min_por_pregao", "mediana_por_pregao", "max_por_pregao", "universo"]`):
`[[2020, 2, 4, 2, 2.0, 2, "composicao_atual"], [2021, 3, 4, 1, 1.0, 2, "composicao_historica"]]`.
Caso 5E `nota_cobertura(linhas_5D, cal)` →
«Cobertura do experimento (universo com a composição, motivo ok): 8 linhas em 5 pregões, de 2020-12-29 a 2021-01-06.»

**Caso 5F** `secao_historico(ler_que_falha, MAPA, set(), exclusoes=Exclusoes())` (nenhuma tabela): 3 notas que
contêm "pulada: tabela ausente" (uma por parte), nenhuma divergência, nenhuma consulta (`ler` levanta
`AssertionError` se chamado).

---

## 4. Item 3e: troca de ação por BDR não une (Fase 6)

### 4.1 Onde a união acontece hoje e o efeito da mudança

Todo mapa de união sai de `fontes.mudancas_como_dict` (`fontes.py:597`) e é seguido por
`tickers.aplicar_mudancas`. Pontos:

| Onde | Linha | Efeito depois do corte |
|---|---|---|
| `fontes._tratar` (preços, proventos, notícias com `unir_mudancas`) | `fontes.py:369-371` | JBSS3 fica com as linhas dele (até 06/06/2025); JBSS32 começa em 09/06/2025; o retorno suspeito de JBSS32 em 09/06/2025 some |
| `fontes.ler_composicao` | `fontes.py:702` | composição JBSS3 fica JBSS3: candidato do universo histórico, tipo ON pela classe (`universo.py:91`), enquanto vigente e com preço |
| `saida/insumos.py` (proventos `ligar_proventos`, notícias do painel `ligar_empresa`, `pacote_noticias`) | `insumos.py:55` | provento JBSS3: `ticker_atual` JBSS3, empresa JBS pela raiz (`ligacao = "raiz"`), classe ON; não entra no yield/lista de JBSS32 (já não entrava: classe diferente). Payout da JBS continua `indisponivel` (só BDR no painel). Notícia JBSS3 vale para a empresa JBS (painel de JBSS32 e dataset) |
| `experimento/dataset.py` (`empresa_de`, `ligar_empresa`) | `dataset.py:103,115,234-236` | JBSS3 → empresa JBS pela raiz; setor vazio (seção 0, item 3) |
| `diagnostico/temas.secao_tickers` (mapa próprio por SQL) | `temas.py:605-611` | **não muda** (seção 0, item 4) |

### 4.2 Decisões técnicas

- **D6-1 Regra pura** em `tickers.py`: `troca_acao_para_bdr(antigo, novo, tipo_de)` = `classe(antigo) in {3, 4, 5, 6, 11}`
  e `novo` é BDR, onde "é BDR" = `tipo_de[novo] == "BDR"` se `novo` está em `tipo_de` (cadastro), senão
  `tipo_por_classe(classe(novo)) == "BDR"` (32 a 35).
- **D6-2** `mudancas_como_dict(mudancas, tipo_de=None)` tira esses pares (com `tipo_de=None`, vale só a
  classe). **Um ponto só**: `fontes.ler_mudancas(ler)` lê `mudancas_ticker` e, se não estiver vazia, o
  `cadastro` (para o `tipo_de`), e devolve o mapa filtrado. Os 4 chamadores passam a usá-la. Ler o cadastro
  só quando há mudanças mantém os `ler` falsos dos testes de composição (`tests/test_fontes_leitura.py:250-262`,
  que devolvem mudanças vazias) funcionando. Sem recursão: `cadastro` e `mudancas_ticker` não estão em
  `TABELAS_COM_TICKER`.
- **D6-3** BDR → ação, ação → ação e unit → unit seguem unidas (CCRO3 → MOTV3 etc.).

### 4.3 Casos com VALORES ESPERADOS

**6A `troca_acao_para_bdr`:**

| antigo | novo | tipo_de | esperado |
|---|---|---|---|
| JBSS3 | JBSS32 | `{"JBSS32": "BDR"}` | True |
| JBSS3 | JBSS32 | `{}` | True |
| CCRO3 | MOTV3 | `{"MOTV3": "ON"}` | False |
| ELET6 | AXIA3 | `{}` | False |
| XPTO3 | XPTO34 | `{}` | True |
| XPTO3 | XPTO34 | `{"XPTO34": "ON"}` | False (cadastro manda) |
| AAAA11 | AAAA34 | `{}` | True |
| XPTO32 | XPTO3 | `{}` | False (BDR → ação une) |
| XPTO3 | XPTO3F | `{}` | False (classe desconhecida) |

**6B `mudancas_como_dict`:** DataFrame `ticker_antigo = ["JBSS3", "CCRO3", "ELET3"]`,
`ticker_novo = ["JBSS32", "MOTV3", "AXIA3"]`, `data_mudanca = ["2025-06-09", "2025-05-02", "2025-11-10"]`:
com `tipo_de={"JBSS32": "BDR", "MOTV3": "ON", "AXIA3": "ON"}` e com `tipo_de=None` →
`{"CCRO3": "MOTV3", "ELET3": "AXIA3"}`.

**6C banco de teste** (`banco_teste(alterar=...)`, `tests/conftest.py`): (conferido)
```python
def _precos_jbs(df):
    df = df.copy()
    antigo = (df["ticker"] == "JBSS32") & df["data"].isin(["2025-10-16", "2025-10-17"])
    df.loc[antigo, "ticker"] = "JBSS3"
    for c in ("abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"):
        df.loc[antigo, c] = "50.00"
    return df

def _mudancas_jbs(df):
    extra = pd.DataFrame({"ticker_antigo": ["JBSS3"], "ticker_novo": ["JBSS32"], "data_mudanca": ["2025-10-20"]})
    return pd.concat([df, extra], ignore_index=True)

ler = banco_teste(alterar={"v1-precos": _precos_jbs, "v1-mudancas_ticker": _mudancas_jbs})
```
- `fontes.ler_mudancas(ler) == {"ELET3": "AXIA3", "ELET6": "AXIA6"}`.
- `p = fontes.ler_tabela("precos", ler=ler)`: `len(p) == 30`; linhas JBSS3: datas 2025-10-16, 2025-10-17,
  fechamento [50.0, 50.0]; JBSS32: 2025-10-20, 2025-10-21, fechamento [10.0, 10.0].
- `retornos_suspeitos(grade_de_precos(p, calendario.pregoes(p), "fechamento_ajustado", ["JBSS3", "JBSS32"]), -0.75, 1.0)`:
  tudo False. (Hoje, com a união, JBSS32 em 2025-10-20 = 10/50 − 1 = −0,8 → True: é o caso de 09/06/2025.)
- `montar_universo(calendario.pregoes(p), fontes.ler_tabela("cadastro", ler=ler), p, Exclusoes(), comp)` com `comp`
  (colunas `ticker, data_inicio, data_fim`) = JBSS3 2025-10-16/2025-10-17, JBSS32 2025-10-20/NaT,
  PETR4 2025-10-16/NaT: JBSS3 em 16 e 17/10 `tipo_acao` ON, `motivo` ok; em 20 e 21/10 `fora_da_composicao`;
  JBSS32 nos 4 dias `tipo_nao_aceito`.
- `tickers.ligar_a_cnpj("JBSS3", cnpj_de, fontes.ler_mudancas(ler)) == ("22222222000122", "raiz")`
  (`cnpj_de = mapas_cadastro(cadastro)[1]`, de `processamento.fatos.precos`).
- `ligar_proventos(prov, cadastro, mudancas)` (de `processamento.fatos.proventos`) com um provento
  JBSS3 DIVIDENDO data_com 2025-10-10 valor 0.5 (colunas como `fabrica_fundamentos.proventos_de`):
  `ticker_atual` "JBSS3", `cnpj` "22222222000122", `ligacao` "raiz", `tipo_classe` "ON";
  `_do_ticker(ligados, "JBSS32")` vazio.
- `processamento.experimento.noticias.ligar_empresa(pd.DataFrame({"ticker": ["JBSS3"]}), cnpj_de, mudancas)["empresa"].tolist() == ["22222222000122"]`.

**6D composição usa `ler_mudancas`:** em `tests/test_fontes_leitura.py`, com
`monkeypatch.setattr(fontes, "ler_mudancas", lambda ler=None: {"CCRO3": "MOTV3"})` e `_ler_composicao_falso`
(`:250-262`) com linhas JBSS3 e CCRO3 (datas quaisquer) → `out["ticker"].tolist() == ["JBSS3", "MOTV3"]`.

---

## 5. Item 4 (inline, sessão principal)

`tests/test_fatos_banco.py:55-58`: renomear para `test_idiv_m1_ok_em_21_10_2026` e trocar `== HIST` por
`== OK` (`OK` já importado na linha 16; tirar `HIST` do import se ficar sem uso). Só o usuário roda (`-m banco`).

---

## 6. Item 7: `saida.publicar_top_provisorio` (Fase 7)

### 6.1 Decisões

- **D7-1 Parâmetro** opcional no bloco `saida` (ausente = `false`, como `treino.modelo_oficial` em
  `experimento/parametros.py:326-327`), booleano estrito; o yaml real traz `publicar_top_provisorio: false`.
  `ParametrosSaida` ganha `publicar_top_provisorio: bool = False` (no fim).
- **D7-2 Regra:** `publicar_top = params_treino.modelo_oficial or params_saida.publicar_top_provisorio`.
  Os produtores `experimento_historico` e `experimento_top` **rodam igual** (fecham pendentes, geram e gravam
  o registro do top, retreino); só o lote não é gravado: é **validado** (`contrato.validar_lote`) e não entra
  em `pacotes_enviados`. Erro de validação continua virando aviso + `parcial`. Produtor que devolve `None`
  (sem modelo) continua deixando `parcial`.
- **D7-3 Onde vai a nota: `avisos`** (não `coleta_status.nota`). `coleta_status` descreve o que se leu do
  painel da coleta (8.3 item 10); `avisos` é o canal da rodada que a interface já mostra, sem mudar o contrato.
  Texto exato (constante `NOTA_TOP_NAO_PUBLICADO` em `gerar.py`): «Top 5 gerado e registrado só como teste de
  funcionamento (modelo não oficial): experimento_top e experimento_historico não enviados à interface
  (saida.publicar_top_provisorio = false).» Acrescentado uma vez, logo depois do laço dos pacotes (antes da
  checagem diária).
- **D7-4 Estado e ordem:** os dois pacotes já devolvem `novo_estado = None` (`gerar.py:215,226,247`):
  `saida/estado/` não muda. A ordem da 8.5 continua (passos 8 e 9 pulados). Vale também com `completo=True`.

### 6.2 Casos com VALORES ESPERADOS

Banco de teste, `D = 2025-10-22`, `modelos_dir` (fixtures de `tests/test_saida_gerar.py`), `PARAMS`
(`modelo_oficial=False`). `SAIDA_NAO = dataclasses.replace(carregar_parametros_saida(), publicar_top_provisorio=False)`,
`SAIDA_SIM` idem com `True`. `SETE = ORDEM_PACOTES[:-2]` (acoes, series_diarias, mercado_dia, resumo_acao,
fundamentos_trimestrais, proventos, noticias_dia).

| caso | modelo_oficial | publicar | arquivos na pasta de D | `pacotes_enviados` | status | NOTA em `avisos` | `registros/2025-10-22.top.json` |
|---|---|---|---|---|---|---|---|
| 7A | False | False | os 7 de `SETE` + `execucao.json` (8) | `SETE` | ok | sim (1 vez) | existe |
| 7B | False | True | os 10 | `ORDEM_PACOTES` (9) | ok | não | existe |
| 7C | True | False | os 10 | `ORDEM_PACOTES` | ok | não | existe |
| 7D | True | True | os 10 | `ORDEM_PACOTES` | ok | não | existe |
| 7E `completo=True` | False | False | 8 | `SETE` | ok | sim; e `AVISO_COMPLETO` | não existe (carga completa não grava) |
| 7F `completo=True` | False | True | os 10 | `ORDEM_PACOTES` | ok | não | não existe |
| 7G CLI `--completo` (yaml real; `tests/test_saida_completo.py:270-277`) | yaml (False) | yaml (False) | 8 | - | - | - | - |

7C/7D: `params=dataclasses.replace(PARAMS, modelo_oficial=True)`. 7A com `usar_estado=True`: nenhum arquivo
da pasta de estado tem "experimento" no nome. **Parâmetros (`tests/test_saida_parametros.py`):** yaml real →
`publicar_top_provisorio is False`; bloco sem a chave → `False`; valor `"sim"` → `ErroParametrosSaida` com
"saida.publicar_top_provisorio"; chave desconhecida continua "chave desconhecida".

**Testes existentes que mudam** (eles esperam os 10 pacotes com o yaml): `tests/test_saida_gerar.py` `_gerar`
(`:77-83`) passa `kw.setdefault("params_saida", SAIDA_SIM)`; `tests/test_saida_completo.py` `_gerar_em`
(`:76-83`) idem; caso 6 CLI (`:270-277`) passa a esperar os 8 arquivos (renomear para
`test_caso_6_cli_cria_os_oito_arquivos_na_pasta_dada`); `tests/test_rotina_executar.py` `_params_saida`
(`:109-111`) ganha `publicar_top_provisorio=True`.

---

## 7. Item 6: textos da `ESPECIFICACAO.md` (Fase 8; o usuário aprova)

Cada bloco "depois" abaixo é o texto exato a gravar (dentro do bloco de código só para não confundir as crases).

**7.1 Seção 3.1, linha `v1-mudancas_ticker`** (`ESPECIFICACAO.md:105`)
```
ANTES:  | `v1-mudancas_ticker` | `ticker_antigo` | todas | `data_mudanca` hoje vazia |
DEPOIS: | `v1-mudancas_ticker` | `ticker_antigo` | todas | `data_mudanca` preenchida nas 10 linhas desde 24/10/2026 (só informativa: a união dos históricos não depende dela). Troca de ação por BDR não une (seção 6, "Mudança de ticker") |
```

**7.2 Seção 3.4**
```
TROCAR a linha "| Histórico curto (~1 ano hoje; meta de 5 anos) | ..." (:127) POR:
| Histórico (24/10/2026): preços desde 30/12/2019; balanços e ações emitidas desde 2022; notícias desde 01/01/2024 (91% das de 2024 sem hora, marcadas "só data" pela coleta) | Implementar tudo. **Não treinar o modelo "para valer"** até o usuário declarar o histórico completo (`treino.modelo_oficial: true`, R7); até lá, só teste de funcionamento (sem conclusões) |

TROCAR a linha "| `data_mudanca` vazia | ..." (:129) POR:
| Troca de ação por BDR (JBSS3 → JBSS32 em 09/06/2025) | Não une os históricos (seção 6): JBSS3 fica com as suas linhas (até 06/06/2025) e entra no universo histórico enquanto está na composição (classe ON pelo sufixo, empresa pela raiz); a BDR começa em 09/06/2025 |

ACRESCENTAR depois da linha "| Empresas sem balanço nas fontes: ... |" (:132):
| Empresa que parou de entregar balanço | Balanço de referência com `data_fim_periodo` + 15 meses antes de t (`fundamentos.balanco_idade_max_meses`): P/L, P/VP, ROE, margens, EBITDA, endividamento e payout 12m saem `indisponivel` (seção 6, "Balanço velho") |
```

**7.3 Seção 3.5** (`:136`)
```
ANTES:  (criada pela coleta em 23/10/2026; **hoje vazia**)
DEPOIS: (criada pela coleta em 23/10/2026; preenchida em 24/10/2026: 137 linhas, 136 tickers, vigências de 01/01/2021 até hoje; fontes `paccafelipe_csv` (115 linhas, não oficial, seção 10) e `rebalanceamento` (22); 2020 não é coberto: nesses pregões vale a composição atual)
```

**7.4 Seção 6**
```
TROCAR a linha "| Mudança de ticker | Unir os históricos pela `v1-mudancas_ticker` antes de qualquer cálculo |" (:205) POR:
| Mudança de ticker | Unir os históricos pela `v1-mudancas_ticker` antes de qualquer cálculo. **Exceção (24/10/2026): troca de ação (classe 3, 4, 5, 6 ou 11) por BDR** (`tipo_acao` BDR no cadastro; fora dele, classe 32 a 35) não une: o código antigo fica com as suas linhas e a BDR começa na troca (ex.: JBSS3 → JBSS32 em 09/06/2025, que gerava um retorno suspeito). A empresa é a mesma (raiz/CNPJ): notícias e proventos do código antigo valem para ela |

ACRESCENTAR depois da linha "| Point-in-time | ... |" (:202):
| Balanço velho | Em t, se o balanço de referência (D11) tem `data_fim_periodo` + `fundamentos.balanco_idade_max_meses` (15) meses de calendário **antes** de t (estrito: ex.: fim 31/12/2023 vale até 31/03/2025 e fica velho em 01/04/2025; fim 30/09/2024 vale até 30/12/2025), P/L, P/VP, ROE, margens bruta e líquida, EBITDA (valor e margem), endividamento (DL, DL/PL, DL/EBITDA, caixa líquido) e payout 12m saem `indisponivel`, também nos pontos diários de P/L e P/VP do `series_diarias`; a empresa sai das medianas do setor desses indicadores. Não mudam: yield, `payout_por_ano`, `proventos_por_ano`, `fundamentos_trimestrais` e `balanco_referencia` (continua mostrando o balanço usado). Bancos e seguradoras seguem `nao_se_aplica` onde já eram (decidido em 24/10/2026) |
```

**7.5 Seção 8.5**, novo parágrafo depois de "Cada pacote é validado antes de gravar; reprovado, não é gravado e a rodada fica `parcial`." (`:423`)
```
**Top 5 provisório (24/10/2026):** enquanto `treino.modelo_oficial` e `saida.publicar_top_provisorio` forem `false`, o top 5 continua gerado e registrado em `registros/experimento/` (e os resultados continuam sendo fechados), mas `experimento_top` e `experimento_historico` **não são gravados** em `saida/<D>/` (passos 8 e 9 pulados; a ordem dos outros não muda), nem na carga completa (8.7). Eles são validados mesmo assim. `pacotes_enviados` lista os outros 7, a rodada não vira `parcial` por isso, e `avisos` traz: "Top 5 gerado e registrado só como teste de funcionamento (modelo não oficial): experimento_top e experimento_historico não enviados à interface (saida.publicar_top_provisorio = false)." Com `modelo_oficial: true` ou `publicar_top_provisorio: true`, vão os 10.
```

**7.6 Seção 8.7** (`:435`)
```
ANTES:  - **O que sai:** os 10 pacotes inteiros:
DEPOIS: - **O que sai:** os 10 pacotes inteiros (8 enquanto o top 5 não é publicado, 8.5):
```

**7.7 Seção 9**
```
TROCAR a linha "- **Horários da B3 antes de 03/2024:** ainda não cadastrados; ..." (:503) POR:
- **Horários da B3 desde 04/11/2019 (cadastrados em 24/10/2026):** períodos de 17h/18h e quartas de cinzas (abertura às 13h) de 2020 a 2024 no `parametros.yaml` (fontes: B3 OC 020/2022 e OC 125/2022; os demais por notícias da época; o início em 04/11/2019 a conferir). O calendário só exige o horário do pregão que cai na data de uma notícia (ou de uma entrega de balanço, E11) a classificar: pregão sem horário e sem notícia não gera erro.

ACRESCENTAR depois do bloco "**Acréscimo de 24/10/2026 (retornos suspeitos e setor sem a própria empresa; ...)**" (antes de "## 10."):
**Acréscimo de 24/10/2026 (histórico novo; plano em `docs/plano_historico_novo.md`)**
- **H1 Calendário:** horários desde 04/11/2019, quartas de cinzas 2020-2024 e 57 feriados (31/12/2019 a 30/05/2024) conferidos com a B3 e com os dias úteis sem IBOV; horário exigido só nos pregões com notícia a classificar.
- **H2 Balanço velho:** `fundamentos.balanco_idade_max_meses: 15` (seção 6).
- **H3 Diagnóstico:** `data_mudanca` e texto vazio no título viram nota; hora das notícias em três grupos por ano (hora real, "só data" N1-A, sem hora); `noticia_sem_hora` só sem a marca "date" de `raw_articles.published_precision`; seção nova com a composição sem preço, o status do `corrigir_horas` e a cobertura do experimento por ano.
- **H4 Troca de ação por BDR** não une os históricos (seção 6).
- **H5 IDIV:** com o histórico novo, o m1 do IDIV em 21/10/2026 é `ok`.
- **H6 Especificação** atualizada (3.1, 3.4, 3.5, 6, 8.5, 8.7, 10).
- **H7 Top 5 provisório:** `saida.publicar_top_provisorio` (padrão `false`; seção 8.5).
```

**7.8 Seção 10**
```
TROCAR "| Histórico de 5 anos (e testar a cobertura de notícias em 2021–2022) | Coleta |" (:585) POR:
| Histórico de notícias antes de 2024 (hoje desde 01/01/2024) e horário real das de 2024 (91% sem hora, marcadas "só data") | Coleta |

REMOVER as linhas "| Preencher a tabela `v1-composicao_ibov` ... |" (:586) e "| `data_mudanca` em `v1-mudancas_ticker` | Coleta |" (:589).

TROCAR a linha "| Etapa manual `corrigir_horas` ... |" (:587) POR:
| Etapa manual `corrigir_horas`: a execução `2026-10-23-coletar-135621` (tipo `coletar`) está `agendada`, com a etapa `pendente`, desde 23/10/2026: não rodou. Provavelmente a correção do horário das notícias pedida abaixo. **Quando concluir, reavaliar a regra N1-A** (seção 7.2); o diagnóstico mostra o status | Coleta |

ACRESCENTAR antes de "| Autenticação, endereço e forma de envio da API | Equipe da API |":
| Composição do Ibovespa de fonte não oficial: 115 das 137 linhas de `v1-composicao_ibov` vêm de `paccafelipe_csv` (as outras 22, de `rebalanceamento`). Conferir contra as carteiras oficiais da B3; 2020 não é coberto | Coleta |
| 46 tickers da composição sem nenhum preço em `v1-precos` (ex.: ALPA4, BRML3, CIEL3, GOLL4, VIIA3; lista no diagnóstico): ficam fora do universo nas datas em que estavam no índice. O viés de sobrevivência continua (seção 3.4); limitação registrada no TCC | Coleta |
| Histórico antigo faltando depois da troca de ticker: NTCO3, AZUL4 e PETZ3 não têm preço em `v1-precos`; NATU3, AZUL3 e AUAU3 só têm desde 26/06/2025, 13/01/2026 e 05/01/2026 | Coleta |
| GMAT3, RAPT4 e SAUD3 estão no cadastro e nunca na composição: ficam fora do universo nas datas cobertas pela composição | Coleta (conferir) |

ACRESCENTAR depois do bloco "**Resolvidas em 22/10/2026** ...":
**Resolvidas em 24/10/2026:**
- `data_mudanca` preenchida em todas as linhas de `v1-mudancas_ticker` (seção 3.1).
- `v1-composicao_ibov` preenchida de 01/01/2021 até hoje (seção 3.5; a fonte não oficial e os tickers sem preço continuam pendentes acima).
```

---

## 8. Pegadinhas para copiar em TODO despacho

- Projeto em `C:/Users/danie/Desktop/TCC/Arquivos/processamento-tcc`, Python 3.12, `./.venv/Scripts/python.exe`.
  Responder em português. **Não fazer commits.**
- **Banco da coleta é só leitura e o usuário do `.env` TEM permissão de escrita:** não conectar no banco, não
  ler o `.env`, não rodar `python -m processamento.diagnostico`, `python -m processamento.saida`,
  `python -m processamento.rotina` nem `pytest -m banco`. **SQL só em `processamento/fontes.py` ou em
  `processamento/diagnostico/`, e só executado por `fontes.executar_leitura`** (o `ler` injetado). Nunca
  INSERT, UPDATE, DELETE nem DDL.
- **Testes sem rede e sem banco real:** só `banco_teste` (SQLite em memória, `tests/conftest.py`), `ler` falso
  ou `monkeypatch` de `fontes.ler_tabela`/`fontes.ler_composicao`.
- **Não ler, não executar e não importar nada de `extracao-dados-tcc-main/`** (nem `tcc_scraper`).
- **YAML:** datas, horas, caminhos e "ON"/"PN" **entre aspas** (`"2020-02-26"`, `"13:00"`); números e
  booleanos sem aspas (`15`, `false`).
- **Ausência = NaN/None + `status`, nunca 0.**
- **Vazamento temporal é bug:** em t, só dados até o corte de t (balanço só com `data_entrega <= t`).
- pandas 3 (Copy-on-Write): nada de atribuição encadeada (`df[c][i] = x`); use `.loc`, `assign`, `where`.
- Funções de `fatos/`, `universo.py`, `tickers.py` e as puras do diagnóstico não fazem I/O.
- Não inventar gabarito: os valores esperados estão neste plano. Se um teste não bater, **reportar o valor
  obtido** em vez de mudar o esperado.
- Pronto = `./.venv/Scripts/python.exe -m pytest -q` sem falhas (mais o comando da fase).

---

## 9. Ordem e paralelismo

- **Fase 1 primeiro e sozinha** (urgente; não depende de nada e nada depende dela).
- Depois, **em paralelo:** Fases 2, 3, 4, 5, 6 e 8 (arquivos disjuntos; ver tabela).
- **Fase 7 depois da Fase 2** (as duas editam `parametros.yaml`; a Fase 2 põe uma chave obrigatória que quebra
  os testes até o código dela estar pronto).
- Item 4: inline pela sessão principal, a qualquer momento.
- Verificação final (executor): `pytest -q` com tudo junto.

| Fase | O quê | Arquivos | Depende de | Conflita com |
|---|---|---|---|---|
| 1 | calendário | `processamento/config/parametros.yaml` (horários, especiais, feriados), `processamento/calendario.py`, `tests/test_calendario.py`, `tests/test_calendario_feriados.py` | - | 2 e 7 (yaml): por isso vem antes |
| 2 | balanço velho | `processamento/config/parametros.yaml` (bloco `fundamentos`), `processamento/fatos/fundamentos.py`, `processamento/fatos/multiplos.py`, `tests/test_fund_parametros.py`, `tests/test_fund_balanco_velho.py` (novo) | 1 | 7 (yaml) |
| 3 | diag. vazios | `processamento/config/fontes.yaml`, `processamento/diagnostico/regras.py`, `processamento/diagnostico/consultas.py`, `tests/test_diagnostico_regras.py`, `tests/test_diagnostico_consultas.py` | - | - |
| 4 | diag. horas | `processamento/diagnostico/temas.py`, `tests/test_diagnostico_horas.py` (novo) | - | - |
| 5 | diag. seção nova | `processamento/diagnostico/historico.py` (novo), `processamento/diagnostico/__main__.py`, `tests/test_diagnostico_historico.py` (novo) | - | - (só importa helpers de `temas.py`, não edita) |
| 6 | ação → BDR | `processamento/tickers.py`, `processamento/fontes.py`, `processamento/saida/insumos.py`, `processamento/experimento/dataset.py`, `tests/test_mudanca_bdr.py` (novo), `tests/test_fontes_leitura.py` | - | - |
| 7 | top provisório | `processamento/config/parametros.yaml` (bloco `saida`), `processamento/saida/parametros.py`, `processamento/saida/gerar.py`, `tests/test_saida_parametros.py`, `tests/test_saida_gerar.py`, `tests/test_saida_completo.py`, `tests/test_rotina_executar.py` | 2 | 2 (yaml) |
| 8 | especificação | `ESPECIFICACAO.md` | - | - |

Durante o paralelo, um `pytest -q` pode pegar o meio da edição de outra fase: se a falha for num arquivo que
não é da sua fase, rodar só os testes da fase e avisar.

---

## 10. Fases para o implementador

### Fase 1: calendário (item 1) — URGENTE

**1.1 `processamento/config/parametros.yaml`**
- Linha 12 (`horarios_b3:`): logo abaixo dela, **antes** de `  - {a_partir_de: "2024-03-11", ...}`, inserir:
```yaml
  # 2019-11-04 a 2024-03-10 (histórico novo, 24/10/2026): B3 OC 020/2022 (14/03/2022) e OC 125/2022 (07/11/2022);
  # os demais por notícias da época; o início em 2019-11-04 ainda a conferir.
  - {a_partir_de: "2019-11-04", abertura: "10:00", fechamento: "18:00"}
  - {a_partir_de: "2020-03-09", abertura: "10:00", fechamento: "17:00"}
  - {a_partir_de: "2020-11-03", abertura: "10:00", fechamento: "18:00"}
  - {a_partir_de: "2021-03-15", abertura: "10:00", fechamento: "17:00"}
  - {a_partir_de: "2021-11-08", abertura: "10:00", fechamento: "18:00"}
  - {a_partir_de: "2022-03-14", abertura: "10:00", fechamento: "17:00"}
  - {a_partir_de: "2022-11-07", abertura: "10:00", fechamento: "18:00"}
  - {a_partir_de: "2023-03-13", abertura: "10:00", fechamento: "17:00"}
  - {a_partir_de: "2023-11-06", abertura: "10:00", fechamento: "18:00"}
```
- Linha 25 (`dias_especiais:`): logo abaixo, antes de `"2025-03-05"`, inserir:
```yaml
  "2020-02-26": {abertura: "13:00", motivo: "quarta-feira de cinzas"}
  "2021-02-17": {abertura: "13:00", motivo: "quarta-feira de cinzas"}
  "2022-03-02": {abertura: "13:00", motivo: "quarta-feira de cinzas"}
  "2023-02-22": {abertura: "13:00", motivo: "quarta-feira de cinzas"}
  "2024-02-14": {abertura: "13:00", motivo: "quarta-feira de cinzas"}
```
- Linha 29 (comentário dos feriados): trocar por
  `# Feriados da B3: dias úteis sem pregão. 2019-12-31 a 2026-10-12 conferidos com os dias úteis sem IBOV do banco e com a B3 (24/10/2026). O resto: conferir no calendário oficial da B3. DATAS ENTRE ASPAS. 09/07 e 25/01 só fecharam em 2021 (pregão nos outros anos).`
- Linha 30 (`feriados_b3:`): logo abaixo, antes de `"2024-11-15"`, inserir as 57 datas:
```yaml
  "2019-12-31": "último dia útil do ano (sem pregão)"
  "2020-01-01": "Confraternização Universal"
  "2020-02-24": "Carnaval"
  "2020-02-25": "Carnaval"
  "2020-04-10": "Sexta-feira Santa"
  "2020-04-21": "Tiradentes"
  "2020-05-01": "Dia do Trabalho"
  "2020-06-11": "Corpus Christi"
  "2020-09-07": "Independência"
  "2020-10-12": "Nossa Senhora Aparecida"
  "2020-11-02": "Finados"
  "2020-11-20": "Consciência Negra"
  "2020-12-24": "véspera de Natal (sem pregão)"
  "2020-12-25": "Natal"
  "2020-12-31": "último dia útil do ano (sem pregão)"
  "2021-01-01": "Confraternização Universal"
  "2021-01-25": "Aniversário de São Paulo"
  "2021-02-15": "Carnaval"
  "2021-02-16": "Carnaval"
  "2021-04-02": "Sexta-feira Santa"
  "2021-04-21": "Tiradentes"
  "2021-06-03": "Corpus Christi"
  "2021-07-09": "Revolução Constitucionalista"
  "2021-09-07": "Independência"
  "2021-10-12": "Nossa Senhora Aparecida"
  "2021-11-02": "Finados"
  "2021-11-15": "Proclamação da República"
  "2021-12-24": "véspera de Natal (sem pregão)"
  "2021-12-31": "último dia útil do ano (sem pregão)"
  "2022-02-28": "Carnaval"
  "2022-03-01": "Carnaval"
  "2022-04-15": "Sexta-feira Santa"
  "2022-04-21": "Tiradentes"
  "2022-06-16": "Corpus Christi"
  "2022-09-07": "Independência"
  "2022-10-12": "Nossa Senhora Aparecida"
  "2022-11-02": "Finados"
  "2022-11-15": "Proclamação da República"
  "2022-12-30": "último dia útil do ano (sem pregão)"
  "2023-02-20": "Carnaval"
  "2023-02-21": "Carnaval"
  "2023-04-07": "Sexta-feira Santa"
  "2023-04-21": "Tiradentes"
  "2023-05-01": "Dia do Trabalho"
  "2023-06-08": "Corpus Christi"
  "2023-09-07": "Independência"
  "2023-10-12": "Nossa Senhora Aparecida"
  "2023-11-02": "Finados"
  "2023-11-15": "Proclamação da República"
  "2023-12-25": "Natal"
  "2023-12-29": "último dia útil do ano (sem pregão)"
  "2024-01-01": "Confraternização Universal"
  "2024-02-12": "Carnaval"
  "2024-02-13": "Carnaval"
  "2024-03-29": "Sexta-feira Santa"
  "2024-05-01": "Dia do Trabalho"
  "2024-05-30": "Corpus Christi"
```
Atenção: os testes de `tests/test_calendario_feriados.py` trocam trechos que precisam existir **uma vez só**
no yaml (`"2026-11-02": "Finados (a conferir)"` e `feriados_b3_valido_ate: "2027-12-31"`): os motivos novos
("Finados", sem "(a conferir)") não colidem. Não mexer em mais nada do yaml.

**1.2 `processamento/calendario.py`**
- `corte_manha` (`:234-238`) ganha `caminho`:
```python
def corte_manha(d: date, caminho: str | None = None) -> pd.Timestamp:
    """Fim da janela da noite que termina na manhã de d (corte_noite, fuso de São Paulo)."""
    d = _data(d)
    corte = time.fromisoformat(carregar_parametros(caminho)["corte_noite"])
    return _instante(d, corte)
```
- Substituir `_classificar_instante` e `classificar_noticias` inteiros (`:277-324`) por:
```python
def _classificar_instante(ts, cal: list[date], horario, corte, corte_proximo) -> tuple[str, date | None]:
    """Janela e pregão de referência de um instante (seção 7.2).

    Só o pregão da própria data de `ts` (em São Paulo) precisa de horário: os pregões de datas anteriores
    já fecharam antes de `ts`, e os de datas posteriores abrem depois do corte das 8h deles.
    `horario(d)` -> (abertura, fechamento) e `corte(d)` -> instante do corte da manhã de d.
    """
    if pd.isna(ts):
        return "sem_horario", None
    dia = ts.tz_convert(SP).date()
    k = bisect.bisect_left(cal, dia)  # 1º pregão com data >= dia
    if k < len(cal) and cal[k] == dia:
        ab, fe = horario(dia)
        if ts <= fe:
            if ab <= ts:
                return "pregao", dia
            if ts <= corte(dia):
                return ("fora_do_calendario", None) if k == 0 else ("noite", cal[k - 1])
            return "pre_abertura", dia
        k += 1  # depois do fechamento de `dia`: vale o próximo pregão
    if k == len(cal):
        if corte_proximo is not None and ts <= corte_proximo:
            return "noite", cal[-1]
        return "fora_do_calendario", None
    # ts é de uma data anterior a cal[k], logo antes do corte das 8h de cal[k]
    return ("fora_do_calendario", None) if k == 0 else ("noite", cal[k - 1])


def classificar_noticias(
    noticias: pd.DataFrame, cal: list[date], proximo_ao_vivo: date | None = None, caminho: str | None = None
) -> pd.DataFrame:
    """Cópia de `noticias` com as colunas `janela` e `pregao_ref` (ver `_classificar_instante`).

    `noticias` traz `data_hora_publicacao` tz-aware ou NaT. `cal` é a lista de pregões ordenada.
    `proximo_ao_vivo` é o próximo pregão ainda sem preço (só para a noite do último pregão de `cal`).
    Preguiçoso (24/10/2026): só pede o horário da B3 do pregão que cai na data (São Paulo) de alguma notícia.
    Pregão sem horário cadastrado e sem notícia na sua data não gera erro; notícia na data de um pregão sem
    horário levanta `ErroCalendario` (mensagem de `horario_b3`). Mesmo resultado do algoritmo antigo
    (todos os horários antes) sempre que o antigo não levanta erro.
    """
    cal = [_data(p) for p in cal]
    horarios: dict[date, tuple[pd.Timestamp, pd.Timestamp]] = {}
    cortes: dict[date, pd.Timestamp] = {}

    def _horario(d: date) -> tuple[pd.Timestamp, pd.Timestamp]:
        if d not in horarios:
            ab, fe = horario_b3(d, caminho)
            horarios[d] = (_instante(d, ab), _instante(d, fe))
        return horarios[d]

    def _corte(d: date) -> pd.Timestamp:
        if d not in cortes:
            cortes[d] = corte_manha(d, caminho)
        return cortes[d]

    corte_proximo = _corte(_data(proximo_ao_vivo)) if proximo_ao_vivo is not None and cal else None
    janelas = []
    refs = []
    for ts in noticias["data_hora_publicacao"]:
        janela, ref = _classificar_instante(ts, cal, _horario, _corte, corte_proximo)
        janelas.append(janela)
        refs.append(ref)
    saida = noticias.copy()
    saida["janela"] = janelas
    saida["pregao_ref"] = pd.to_datetime(pd.Series(refs, index=saida.index, dtype=object))
    return saida
```
`abertura` e `fechamento` (`:220-231`) continuam (usados por `janela_pregao`/`janela_noite`). Nenhum chamador muda.

**1.3 Testes**
- `tests/test_calendario.py`:
  - `test_horario_b3_antes_do_primeiro_periodo_erro` (`:118-120`): `date(2024, 3, 8)` → `date(2019, 11, 1)`, com
    `match="anterior ao primeiro período"`.
  - acrescentar ao `parametrize` de `test_horario_b3_por_periodo_e_dia_especial` (`:99-115`) os 12 casos da tabela 1A.
  - testes novos 1B (tabela; `CAL` montado com `e_pregao_previsto` de `processamento.calendario`), 1C (dois
    testes: sem erro e com erro; usam `_escrever` e `_CABECALHO_YAML` que já existem no arquivo) e 1D
    (igualdade). Para 1D, copiar no teste a referência do algoritmo antigo:
```python
import bisect
from processamento.calendario import abertura, corte_manha, e_pregao_previsto

def _classificar_ingenuo(noticias, cal, proximo_ao_vivo=None):
    """Algoritmo antigo (até 24/10/2026): calcula o horário de TODOS os pregões. Só para comparar."""
    fechamentos = [fechamento(p) for p in cal]
    aberturas = [abertura(p) for p in cal]
    cortes = [corte_manha(p) for p in cal]
    corte_proximo = corte_manha(proximo_ao_vivo) if proximo_ao_vivo is not None and cal else None
    janelas, refs = [], []
    for ts in noticias["data_hora_publicacao"]:
        if pd.isna(ts):
            j, r = "sem_horario", None
        else:
            k = bisect.bisect_left(fechamentos, ts)
            if k == len(cal):
                j, r = ("noite", cal[-1]) if corte_proximo is not None and ts <= corte_proximo else ("fora_do_calendario", None)
            elif aberturas[k] <= ts <= fechamentos[k]:
                j, r = "pregao", cal[k]
            elif ts <= cortes[k]:
                j, r = ("fora_do_calendario", None) if k == 0 else ("noite", cal[k - 1])
            else:
                j, r = "pre_abertura", cal[k]
        janelas.append(j)
        refs.append(r)
    saida = noticias.copy()
    saida["janela"] = janelas
    saida["pregao_ref"] = pd.to_datetime(pd.Series(refs, index=saida.index, dtype=object))
    return saida
```
- `tests/test_calendario_feriados.py`: casos 1E (parametrize de `test_e_pregao_previsto`,
  `test_pregao_anterior_previsto` e um teste `len(feriados_b3()) == 99`); no teste de banco (`:212`),
  `date(2024, 8, 1)` → `date(2019, 12, 30)`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_calendario.py tests/test_calendario_feriados.py tests/test_exp_janelas.py tests/test_fontes_so_data.py tests/test_vazamento_leitura.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`. **Pronto (usuário, lê o banco):**
`PROC_TESTES_COM_BANCO=1 pytest -q -m banco` com `test_dataset_do_banco_real_so_leitura` e
`test_banco_feriados_conferem_com_pregoes_reais` passando.

### Fase 2: balanço velho (item 2)

**2.1 `processamento/config/parametros.yaml`**, bloco `fundamentos`, logo depois da linha `  pvp_minimo_plausivel: 0.05 ...`:
```yaml
  balanco_idade_max_meses: 15   # balanço de referência com data_fim_periodo + N meses antes de t = velho: P/L, P/VP, ROE, margens, EBITDA, endividamento e payout 12m indisponíveis (seção 6)
```
**2.2 `processamento/fatos/fundamentos.py`**
- `import dataclasses` no topo (junto de `import math`).
- `_CHAVES_FUNDAMENTOS` (`:50-52`): acrescentar `"balanco_idade_max_meses"`.
- `ParametrosFundamentos` (`:59-67`): acrescentar no fim `balanco_idade_max_meses: int = 15`.
- `carregar_parametros_fundamentos` (`:105-113`): no `ParametrosFundamentos(...)`, acrescentar
  `balanco_idade_max_meses=_inteiro_positivo(bloco["balanco_idade_max_meses"], "fundamentos.balanco_idade_max_meses"),`.
- Depois de `quantidade_suspeita` (`:202-212`), duas funções novas:
```python
def balanco_velho(data_fim_periodo, t, meses: int) -> bool:
    """True se o balanço de referência é velho em t: fim do mês de (data_fim_periodo + `meses` meses) < t.

    Estrito: no último dia desse mês o balanço ainda vale (ex.: 2024-09-30 + 15 meses -> 2025-12-31, velho
    a partir de 2026-01-01). Sem data (None/NaT) não é velho.
    """
    if data_fim_periodo is None or pd.isna(data_fim_periodo):
        return False
    limite = pd.Timestamp(data_fim_periodo).normalize() + pd.DateOffset(months=meses) + pd.offsets.MonthEnd(0)
    return bool(limite < pd.Timestamp(t).normalize())


def foto_dentro_do_prazo(foto: FotoBalanco, t, meses: int) -> FotoBalanco:
    """A própria foto, ou uma cópia com `status_base = indisponivel` se o balanço de referência é velho em t.

    Usada só no painel do dia e nos múltiplos diários (seção 6, "Balanço velho"); payout por ano, tabela
    trimestral e balanço de referência continuam com a foto original.
    """
    if foto.status_base == OK and balanco_velho(foto.data_fim_periodo, t, meses):
        return dataclasses.replace(foto, status_base=INDISPONIVEL)
    return foto
```
- `calcular_fundamentos_no_dia`, linha 478: `foto = foto_balanco(dados.balancos, cnpj, ts, exclusoes)` →
  `foto = foto_dentro_do_prazo(foto_balanco(dados.balancos, cnpj, ts, exclusoes), ts, params.balanco_idade_max_meses)`.
- **Não** mexer em `_payout_das_dfps`, `_linhas_da_empresa`, `balanco_referencia_no_dia`, `_cnpjs_com_quantidade_suspeita`.

**2.3 `processamento/fatos/multiplos.py`**
- import: acrescentar `foto_dentro_do_prazo` ao `from processamento.fatos.fundamentos import (...)` (`:18-24`).
- linha 122: logo depois de `foto, qtd = cache[trecho]`, acrescentar
  `foto = foto_dentro_do_prazo(foto, ts, params.balanco_idade_max_meses)  # por dia: a idade cruza o limite dentro do trecho`.

**2.4 Testes:** `tests/test_fund_parametros.py` (2E); `tests/test_fund_balanco_velho.py` (novo) com 2A, 2B, 2C,
2D (imports: `from fabrica_fundamentos import CNPJ, EXCL, mundo, balanco_de, _a`; funções de
`processamento.fatos.fundamentos` e `processamento.fatos.multiplos`).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_fund_balanco_velho.py tests/test_fund_parametros.py tests/test_fatos_multiplos.py tests/test_fund_no_dia.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 3: diagnóstico, vazios (3a, 3c)

**3.1 `processamento/config/fontes.yaml`**
- linha 39: `    colunas_vazias_conhecidas: [data_mudanca]` →
  `    colunas_nota_preenchimento: [data_mudanca]   # preenchida desde 24/10/2026: só nota com a contagem (seção 3.1)`
- depois da linha 10 (`    colunas_ignoradas: [momento_pregao]   ...`), nova linha:
  `    textos_vazios_nota: [titulo]   # texto vazio no título vira nota com até 10 ids (a leitura já trata como vazio); nas outras colunas é divergência`

**3.2 `processamento/diagnostico/regras.py`**
- `divergencias_coluna` (`:371-387`): assinatura nova
  `def divergencias_coluna(tabela, coluna, situacao, texto_vazio, zeros, vazia_conhecida, zero_proibido, so_nota_preenchimento=False, so_nota_texto_vazio=False) -> list:`.
  No corpo: antes de `if vazia_conhecida:` inserir `if so_nota_preenchimento: pass  # só nota (consultas.secao_vazios)`
  e trocar `if vazia_conhecida:` por `elif vazia_conhecida:` (o `elif situacao == "vazia":` continua);
  trocar `if inteiro(texto_vazio) > 0:` por `if inteiro(texto_vazio) > 0 and not so_nota_texto_vazio:`.
- logo depois dela:
```python
def nota_preenchimento(tabela, coluna, total, nulos) -> str:
    """Nota de coluna acompanhada só por contagem (ex.: data_mudanca): preenchida em N de M linhas."""
    total, nulos = inteiro(total), inteiro(nulos)
    nota = f"`{tabela}.{coluna}` preenchida em {total - nulos} de {total} linhas"
    return nota + (f" ({nulos} vazias)" if nulos else "")


def nota_texto_vazio(tabela, coluna, n, ids) -> str:
    """Nota de textos vazios numa coluna em que eles são só informação (ex.: título da notícia)."""
    return (f"`{tabela}.{coluna}`: {inteiro(n)} textos vazios ('') (a leitura trata como vazio); "
            f"ids (até 10): {', '.join(str(i) for i in ids)}")
```
**3.3 `processamento/diagnostico/consultas.py`**
- depois de `montar_sql_vazios` (`:69-83`):
```python
def montar_sql_ids_texto_vazio(tabela: str, coluna_id: str, coluna: str) -> str:
    """Até 10 ids (distintos, em ordem) das linhas com texto vazio na coluna (nomes reais)."""
    return (f"SELECT DISTINCT {fontes.citar(coluna_id)} AS id FROM {fontes.citar(tabela)} "
            f"WHERE {fontes.citar(coluna)} = '' ORDER BY id LIMIT 10")
```
- `secao_vazios` (`:367-408`): logo depois de `conhecidas = ...` (linha 380):
  `so_nota_preench = set(cfg.get("colunas_nota_preenchimento", []))` e
  `so_nota_texto = set(cfg.get("textos_vazios_nota", []))`; passar
  `so_nota_preenchimento=contrato_col in so_nota_preench, so_nota_texto_vazio=contrato_col in so_nota_texto`
  na chamada de `divergencias_coluna`; logo depois do laço de divergências (antes do `if nulos or ...` da linha 396):
```python
            if contrato_col in so_nota_preench and resumo["situacao"] != "tabela_vazia":
                secao["notas"].append(r.nota_preenchimento(nome, coluna, total, nulos))
            if contrato_col in so_nota_texto and textos_vazios > 0:
                coluna_id = cfg["colunas"][cfg["chave"][0]]
                df_ids = ler(montar_sql_ids_texto_vazio(nome, coluna_id, coluna))
                ids = [r.texto(v) for v in df_ids["id"]]
                secao["notas"].append(r.nota_texto_vazio(nome, coluna, textos_vazios, ids))
```
  e a condição da linha 396 ganha `or contrato_col in so_nota_preench`.

**3.4 Testes:** 3A-3I em `tests/test_diagnostico_regras.py` e `tests/test_diagnostico_consultas.py`
(3H string exata); 3J em `tests/test_diagnostico_consultas.py`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_diagnostico_regras.py tests/test_diagnostico_consultas.py tests/test_fontes.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 4: diagnóstico, hora das notícias (3b)

**4.1 `processamento/diagnostico/temas.py`**, funções novas logo antes de `secao_noticias` (`:175`):
```python
def _pct(parte: int, total: int):
    """Percentual com 1 casa (None se total 0)."""
    return None if not total else round(parte / total * 100, 1)


def meia_noite_por_ano_origem(candidatos: pd.DataFrame) -> dict:
    """{(ano, origem): artigos} com instante = 00:00:00 em Los Angeles (regra N1-A, `fontes.meia_noite_pacifico`).

    `candidatos`: ano, origem, instante (texto ISO com fuso), n (artigos distintos).
    """
    if candidatos.empty:
        return {}
    instantes = fontes.para_sao_paulo_iso(candidatos["instante"].map(texto), "v1-noticias.data_hora_publicacao")
    meia = fontes.meia_noite_pacifico(instantes)
    saida: dict = {}
    for (a, o, n), e_meia in zip(_registros(candidatos, ("ano", "origem", "n")), meia):
        if e_meia:
            chave = (_ano(a), texto(o))
            saida[chave] = saida.get(chave, 0) + inteiro(n)
    return saida


def linhas_horas(totais: pd.DataFrame, meia: dict) -> list[list]:
    """[ano, origem, total, hora_real, %, so_data_n1a, %, sem_hora, %] por (ano, origem), na ordem dos totais."""
    linhas = []
    for a, o, t, s in _registros(totais, ("ano", "origem", "total", "sem_hora")):
        ano_v, origem_v, total, sem = _ano(a), texto(o), inteiro(t), inteiro(s)
        n1a = meia.get((ano_v, origem_v), 0)
        real = total - sem - n1a
        linhas.append([ano_v, origem_v, total, real, _pct(real, total), n1a, _pct(n1a, total), sem, _pct(sem, total)])
    return linhas


def somar_horas_por_ano(linhas_ao: list[list]) -> list[list]:
    """Soma as linhas de `linhas_horas` por ano: [ano, total, hora_real, %, so_data_n1a, %, sem_hora, %]."""
    soma: dict = {}
    for ano_v, _o, total, real, _p1, n1a, _p2, sem, _p3 in linhas_ao:
        t0, r0, n0, s0 = soma.get(ano_v, (0, 0, 0, 0))
        soma[ano_v] = (t0 + total, r0 + real, n0 + n1a, s0 + sem)
    return [[a, t, r, _pct(r, t), n, _pct(n, t), s, _pct(s, t)] for a, (t, r, n, s) in sorted(soma.items())]
```
E a função que roda as consultas (também antes de `secao_noticias`):
```python
_COLS_HORAS = ["total", "hora_real", "pct_hora_real", "so_data_n1a", "pct_so_data_n1a", "sem_hora", "pct_sem_hora"]


def _horas_por_ano(ler, mapa: dict, existentes: set, secao: dict) -> pd.DataFrame:
    """Hora da publicação por ano (artigos distintos): hora real, "só data" N1-A e sem hora.

    Divergência `noticia_sem_hora` só para Google News sem hora e sem a marca 'date' em raw_articles;
    os marcados viram nota. Devolve o DataFrame dos totais (ano, origem, total, sem_hora).
    """
    nome = _nome(mapa, "noticias")
    T = _tab(mapa, "noticias")
    c = lambda x: _col(mapa, "noticias", x)
    dhp, dp, org, idc = c("data_hora_publicacao"), c("data_publicacao"), c("origem"), c("id")
    df_tot = ler(
        f"SELECT YEAR({dp}) AS ano, {org} AS origem, COUNT(DISTINCT {idc}) AS total, "
        f"COUNT(DISTINCT CASE WHEN {dhp} IS NULL OR {dhp} = '' THEN {idc} END) AS sem_hora "
        f"FROM {T} GROUP BY ano, origem ORDER BY ano, origem"
    )
    df_cand = ler(
        f"SELECT YEAR({dp}) AS ano, {org} AS origem, {dhp} AS instante, COUNT(DISTINCT {idc}) AS n "
        f"FROM {T} WHERE SUBSTRING({dhp}, 15, 5) = '00:00' GROUP BY ano, origem, instante"
    )
    linhas_ao = linhas_horas(df_tot, meia_noite_por_ano_origem(df_cand))
    adicionar_tabela(secao, "Hora da publicação, por ano (artigos distintos)", ["ano", *_COLS_HORAS],
                     somar_horas_por_ano(linhas_ao))
    adicionar_tabela(secao, "Hora da publicação, por ano e origem (artigos distintos)",
                     ["ano", "origem", *_COLS_HORAS], linhas_ao)

    google = {linha[0]: (linha[2], linha[7]) for linha in linhas_ao if linha[1] == "google_news" and linha[7] > 0}
    if not google:
        return df_tot
    so_data: dict = {}
    sem_marca: dict = {}
    if _existe(mapa, existentes, "raw_articles"):
        RAW = _tab(mapa, "raw_articles")
        rr = lambda x: _col(mapa, "raw_articles", x)
        df_p = ler(
            f"SELECT YEAR(n.{dp}) AS ano, r.{rr('published_precision')} AS precisao, COUNT(DISTINCT n.{idc}) AS n "
            f"FROM {T} n LEFT JOIN {RAW} r ON r.{rr('id')} = CAST(SUBSTRING(n.{idc}, 2) AS UNSIGNED) "
            f"WHERE n.{org} = 'google_news' AND (n.{dhp} IS NULL OR n.{dhp} = '') GROUP BY ano, precisao"
        )
        for a, p, n in _registros(df_p, ("ano", "precisao", "n")):
            alvo = so_data if texto(p) == "date" else sem_marca
            alvo[_ano(a)] = alvo.get(_ano(a), 0) + inteiro(n)
    else:
        secao["notas"].append(f"Marca 'só data' (raw_articles): {_pulada(mapa, 'raw_articles')}")
        sem_marca = {a: sem for a, (_t, sem) in google.items()}
    if so_data:
        partes = ", ".join(f"{a}: {n}" for a, n in sorted(so_data.items()))
        secao["notas"].append(
            f"{sum(so_data.values())} notícias do Google News sem hora, marcadas 'só data' pela coleta "
            f"(raw_articles.published_precision = 'date'): {partes}")
    for a in sorted(sem_marca):
        if sem_marca[a] > 0:
            total = google.get(a, (0, 0))[0]
            secao["divergencias"].append(div(
                "noticia_sem_hora", nome, f"{a}: {sem_marca[a]} de {total} sem hora e sem a marca 'só data' em raw_articles"))
    return df_tot
```
- `secao_noticias`: trocar o bloco `# b) percentual com hora, por ano e por origem` inteiro (`:205-224`) por
  `    # b) hora da publicação por ano e por origem (hora real, só data N1-A, sem hora)` +
  `    df_ano = _horas_por_ano(ler, mapa, existentes, secao)` (o `df_ano["ano"]` continua usado na linha 247).
  O import de `pct_com_hora_por_ano` (`:47`) sai se ficar sem uso (a função fica em `regras.py`).

**4.2 Testes:** `tests/test_diagnostico_horas.py` (novo) com 4A, 4B, 4C; `ler(sql)` falso roteado por
substring ("AS sem_hora", "'00:00'", "published_precision"; qualquer outro SQL → `AssertionError`);
`MAPA = fontes.carregar_mapa()`; `secao = nova_secao("x")` (de `processamento.diagnostico.regras`);
importar `_horas_por_ano`, `meia_noite_por_ano_origem` de `processamento.diagnostico.temas`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_diagnostico_horas.py tests/test_diagnostico_temas.py tests/test_diagnostico_regras.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 5: diagnóstico, seção nova (3d)

**5.1 `processamento/diagnostico/historico.py` (novo).** Código de referência (ajustes de estilo livres; os
textos e a ordem das colunas são o gabarito):
```python
"""Seção "Histórico novo" do diagnóstico (24/10/2026): composição sem preço, corrigir_horas e cobertura.

SQL só pelo `ler` (executado por `fontes.executar_leitura`); tabelas do contrato por `fontes.ler_tabela` e
`fontes.ler_composicao` (sempre pelo módulo `fontes`, para o monkeypatch dos testes). As funções puras
(`composicao_sem_preco`, `nota_*`, `cobertura_por_ano`) não fazem I/O.
"""

from __future__ import annotations

import pandas as pd

from processamento import calendario, fontes
from processamento.diagnostico.regras import adicionar_tabela, nova_secao, texto
from processamento.diagnostico.temas import _col, _existe, _pulada, _registros, _tab
from processamento.exclusoes import Exclusoes, carregar_exclusoes
from processamento.tickers import aplicar_mudancas, raiz
from processamento.universo import montar_universo

INICIO_2024 = pd.Timestamp("2024-01-01")
COLUNAS_COMPOSICAO = ["ticker", "grupo", "inicio", "fim", "no_indice_desde_2024"]
COLUNAS_COBERTURA = ["ano", "pregoes", "linhas_ok", "min_por_pregao", "mediana_por_pregao", "max_por_pregao", "universo"]


def composicao_sem_preco(comp: pd.DataFrame, tickers_com_preco: set, mudancas: dict, antigos: set,
                         tickers_cadastro: set) -> list[list]:
    """Tickers da composição (como vêm na tabela) sem nenhum preço, procurado com a união das mudanças."""
    raizes = {raiz(t) for t in tickers_cadastro}
    linhas = []
    for t, g in comp.groupby("ticker", sort=True):
        if aplicar_mudancas(t, mudancas) in tickers_com_preco:
            continue
        grupo = "empresa_do_cadastro" if (t in antigos or raiz(t) in raizes) else "fora_do_cadastro"
        vigente = g["data_fim"].isna().any()
        fim = "vigente" if vigente else pd.Timestamp(g["data_fim"].max()).date().isoformat()
        desde_2024 = vigente or bool((g["data_fim"] >= INICIO_2024).any())
        inicio = pd.Timestamp(g["data_inicio"].min()).date().isoformat()
        linhas.append([t, grupo, inicio, fim, "sim" if desde_2024 else "não"])
    return sorted(linhas, key=lambda l: (l[1] != "empresa_do_cadastro", l[0]))


def nota_composicao_sem_preco(linhas: list[list], m: int) -> str:
    """Resumo da composição sem preço; `m` = nº de tickers distintos da composição."""
    if not linhas:
        return f"Composição do Ibovespa: todos os {m} tickers têm preço em v1-precos (com a união das mudanças de ticker)."
    a = sum(1 for l in linhas if l[1] == "empresa_do_cadastro")
    k = sum(1 for l in linhas if l[4] == "sim")
    return (f"Composição do Ibovespa: {len(linhas)} de {m} tickers sem nenhum preço em v1-precos "
            f"({a} código antigo de empresa do cadastro, {len(linhas) - a} fora do cadastro); {k} estiveram no "
            "índice em 2024 ou depois. O preço é procurado com a união das mudanças de ticker (o código antigo "
            "vale pelo atual).")


def _hora_sp(valor) -> str:
    """Instante UTC sem fuso (painel da coleta) em São Paulo, 'AAAA-MM-DD HH:MM'; vazio = '—'."""
    if valor is None or pd.isna(valor):
        return "—"
    return fontes.para_sao_paulo_de_utc(pd.Series([valor])).iloc[0].strftime("%Y-%m-%d %H:%M")


def nota_corrigir_horas(df: pd.DataFrame) -> str:
    """Status da execução mais recente com a etapa corrigir_horas (df com 0 ou 1 linha)."""
    if df.empty:
        return "corrigir_horas: nenhuma execução com essa etapa"
    linha = df.iloc[0]
    return (f"corrigir_horas: execução mais recente {texto(linha['id'])} (status {texto(linha['status_execucao'])}), "
            f"etapa {texto(linha['status_etapa'])}; iniciada em {_hora_sp(linha['iniciada_em'])}, "
            f"finalizada em {_hora_sp(linha['finalizada_em'])} (horário de São Paulo)")


def cobertura_por_ano(universo: pd.DataFrame, cal: list) -> list[list]:
    """Por ano: pregões, linhas com motivo ok, mín/mediana/máx de ações ok por pregão e os universos do ano."""
    datas = pd.DatetimeIndex([pd.Timestamp(d) for d in cal])
    ok = universo[universo["motivo"] == "ok"]
    por_pregao = ok.groupby("data").size().reindex(datas, fill_value=0)
    linhas = []
    for ano in sorted(set(datas.year)):
        do_ano = por_pregao[por_pregao.index.year == ano]
        tipos = sorted(set(universo.loc[pd.to_datetime(universo["data"]).dt.year == ano, "universo"]))
        linhas.append([int(ano), int(len(do_ano)), int(do_ano.sum()), int(do_ano.min()), float(do_ano.median()),
                       int(do_ano.max()), "/".join(tipos)])
    return linhas


def nota_cobertura(linhas: list[list], cal: list) -> str:
    """Resumo da cobertura do experimento."""
    total = sum(l[2] for l in linhas)
    return (f"Cobertura do experimento (universo com a composição, motivo ok): {total} linhas em {len(cal)} "
            f"pregões, de {pd.Timestamp(cal[0]).date().isoformat()} a {pd.Timestamp(cal[-1]).date().isoformat()}.")
```
(As funções puras acima foram rodadas sobre os casos 5A-5E e dão exatamente os esperados: conferido.)

E a seção que cola tudo (mesmo arquivo):
```python
def secao_historico(ler, mapa: dict, existentes: set, exclusoes: Exclusoes | None = None) -> dict:
    """Composição sem preço, status do corrigir_horas e cobertura do experimento por ano (só notas e tabelas)."""
    secao = nova_secao("Histórico novo: composição, corrigir_horas e cobertura do experimento")
    faltam = lambda chaves: [c for c in chaves if not _existe(mapa, existentes, c)]
    precos = None

    # (i) composição sem preço
    falta = faltam(("composicao_ibov", "precos", "cadastro", "mudancas_ticker"))
    if falta:
        secao["notas"].append(f"Composição sem preço: {_pulada(mapa, falta[0])}")
    else:
        cc = lambda x: _col(mapa, "composicao_ibov", x)
        bruto = ler(f"SELECT {cc('ticker')} AS ticker, {cc('data_inicio')} AS data_inicio, "
                    f"{cc('data_fim')} AS data_fim FROM {_tab(mapa, 'composicao_ibov')}")
        comp = pd.DataFrame({
            "ticker": fontes.normalizar_ticker(bruto["ticker"].map(texto)),
            "data_inicio": pd.to_datetime(bruto["data_inicio"], errors="coerce"),
            "data_fim": pd.to_datetime(bruto["data_fim"], errors="coerce"),
        }).dropna(subset=["ticker"])
        mud = fontes.ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False)
        precos = fontes.ler_tabela("precos", ler=ler)
        cadastro = fontes.ler_tabela("cadastro", ler=ler)
        linhas = composicao_sem_preco(comp, set(precos["ticker"].dropna()), fontes.mudancas_como_dict(mud),
                                      set(mud["ticker_antigo"].dropna()), set(cadastro["ticker"].dropna()))
        if linhas:
            adicionar_tabela(secao, "Composição do Ibovespa: tickers sem nenhum preço em v1-precos",
                             COLUNAS_COMPOSICAO, linhas)
        secao["notas"].append(nota_composicao_sem_preco(linhas, comp["ticker"].nunique()))

    # (ii) corrigir_horas
    falta = faltam(("painel_etapas", "painel_execucoes"))
    if falta:
        secao["notas"].append(f"corrigir_horas: {_pulada(mapa, falta[0])}")
    else:
        g = lambda x: _col(mapa, "painel_etapas", x)
        e = lambda x: _col(mapa, "painel_execucoes", x)
        df = ler(
            f"SELECT x.{e('id')} AS id, x.{e('status')} AS status_execucao, x.{e('iniciada_em')} AS iniciada_em, "
            f"x.{e('finalizada_em')} AS finalizada_em, t.{g('status')} AS status_etapa "
            f"FROM {_tab(mapa, 'painel_etapas')} t JOIN {_tab(mapa, 'painel_execucoes')} x "
            f"ON x.{e('id')} = t.{g('execucao_id')} WHERE t.{g('etapa_id')} = 'corrigir_horas' "
            f"ORDER BY x.{e('iniciada_em')} DESC, x.{e('id')} DESC LIMIT 1"
        )
        secao["notas"].append(nota_corrigir_horas(df))

    # (iii) cobertura do experimento
    falta = faltam(("precos", "cadastro"))
    if falta:
        secao["notas"].append(f"Cobertura do experimento: {_pulada(mapa, falta[0])}")
        return secao
    precos = fontes.ler_tabela("precos", ler=ler) if precos is None else precos
    cal = calendario.pregoes(precos)
    if not cal:
        secao["notas"].append("Cobertura do experimento: sem pregão com preço do IBOV")
        return secao
    universo = montar_universo(cal, fontes.ler_tabela("cadastro", ler=ler), precos,
                               exclusoes if exclusoes is not None else carregar_exclusoes(),
                               fontes.ler_composicao(ler=ler))
    linhas = cobertura_por_ano(universo, cal)
    adicionar_tabela(secao, "Cobertura do experimento por ano (universo com a composição, motivo ok)",
                     COLUNAS_COBERTURA, linhas)
    secao["notas"].append(nota_cobertura(linhas, cal))
    return secao
```
(`_registros` pode sair do import se não for usado.)

**5.2 `processamento/diagnostico/__main__.py`:** linha 17 → `from processamento.diagnostico import consultas, historico, temas`;
na lista `secoes` (`:62-76`), logo depois da linha do painel (`_seguro("Gatilho da coleta e composição", ...)`):
`        _seguro("Histórico novo", historico.secao_historico, ler, mapa, existentes),`.

**5.3 Testes:** `tests/test_diagnostico_historico.py` (novo): 5A-5E direto nas funções puras (5D monta `u` com
`montar_universo`, dados da seção 3.4); 5F com `ler` que levanta `AssertionError`; e um teste da parte (ii)
com `existentes = {"v1-painel_etapas", "v1-painel_execucoes"}` e `ler` falso que só aceita SQL contendo
"corrigir_horas" (devolve o DataFrame de 5C) → a seção tem a nota de 5C e as notas puladas das partes (i) e (iii).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_diagnostico_historico.py tests/test_diagnostico_main.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 6: troca de ação por BDR (3e)

**6.1 `processamento/tickers.py`**, logo depois de `aplicar_mudancas` (`:47-60`):
```python
CLASSES_DE_ACAO = {3, 4, 5, 6, 11}


def troca_acao_para_bdr(antigo: str, novo: str, tipo_de: dict[str, str]) -> bool:
    """True se a mudança troca uma ação (classe 3, 4, 5, 6 ou 11) por uma BDR: os históricos não se unem.

    BDR = `tipo_acao` "BDR" no cadastro (`tipo_de`); fora do cadastro, classe 32 a 35 (ex.: JBSS3 -> JBSS32).
    """
    if classe(antigo) not in CLASSES_DE_ACAO:
        return False
    if novo in tipo_de:
        return tipo_de[novo] == "BDR"
    return tipo_por_classe(classe(novo)) == "BDR"
```
**6.2 `processamento/fontes.py`**
- import: acrescentar `troca_acao_para_bdr` ao import de `processamento.tickers` (onde já vem `aplicar_mudancas`).
- substituir `mudancas_como_dict` (`:597-605`) e acrescentar `ler_mudancas` logo depois:
```python
def mudancas_como_dict(mudancas: pd.DataFrame, tipo_de: dict[str, str] | None = None) -> dict[str, str]:
    """Monta {ticker antigo: ticker novo} de `v1-mudancas_ticker`, sem linhas sem destino.

    Troca de ação por BDR fica de fora (não une os históricos; seção 6): `tipo_de` é ticker -> tipo_acao do
    cadastro; sem ele, vale só a classe do código.
    """
    antigos = normalizar_ticker(mudancas["ticker_antigo"])
    novos = normalizar_ticker(mudancas["ticker_novo"])
    tipos = tipo_de or {}
    return {
        a: n
        for a, n in zip(antigos, novos, strict=True)
        if isinstance(a, str) and isinstance(n, str) and a != n and not troca_acao_para_bdr(a, n, tipos)
    }


def ler_mudancas(ler: Callable[..., pd.DataFrame] | None = None) -> dict[str, str]:
    """Mapa de união dos históricos (antigo -> novo) lido do banco, sem as trocas de ação por BDR.

    Lê o cadastro só quando há mudanças (o tipo BDR vem dele).
    """
    mudancas = ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False)
    if mudancas.empty:
        return {}
    cadastro = ler_tabela("cadastro", ler=ler)
    tipo_de = {t: tp for t, tp in zip(cadastro["ticker"], cadastro["tipo_acao"])
               if isinstance(t, str) and isinstance(tp, str)}
    return mudancas_como_dict(mudancas, tipo_de)
```
- `_tratar`, linha 370: `mudancas = mudancas_como_dict(ler_tabela("mudancas_ticker", ler=ler, unir_mudancas=False))` → `mudancas = ler_mudancas(ler)`.
- `ler_composicao`, linha 702: a mesma troca → `mudancas = ler_mudancas(ler)`.

**6.3** `processamento/saida/insumos.py:55` → `mudancas = fontes.ler_mudancas(ler)`.
`processamento/experimento/dataset.py:234-236` → `mudancas=fontes.ler_mudancas(ler),`.
Não mexer em `diagnostico/temas.py` (mapa próprio, seção 0 item 4).

**6.4 Testes:** `tests/test_mudanca_bdr.py` (novo) com 6A, 6B, 6C; 6D em `tests/test_fontes_leitura.py`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_mudanca_bdr.py tests/test_fontes_leitura.py tests/test_tickers.py tests/test_universo.py tests/test_exp_dataset.py tests/test_saida_pacotes_fatos.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 6b: setor herdado pela empresa (decisão do usuário, 24/10/2026; DEPOIS da Fase 6)

**Decisão:** ticker do universo do modelo que não está no `v1-cadastro`, mas é ligado a uma empresa do cadastro
por `tickers.ligar_a_cnpj` (mudanças + raiz de 4 letras com CNPJ único), herda o CNPJ e o **setor dessa empresa**.
Ex.: JBSS3 (antigo, até 2025-06-06) → empresa e setor do JBSS32. Ticker sem empresa ou com raiz ambígua: continua
sem setor (como hoje). Tickers do cadastro não mudam (inclusive os com setor vazio, ex.: CRFB3).

**6b.1 `processamento/tickers.py`** (pura, sem I/O), depois de `ligar_a_cnpj`:
```python
def mapas_por_empresa(
    tickers, setor_de: dict, cnpj_de: dict, mudancas: dict
) -> tuple[dict, dict, dict[str, tuple[str, str | None]]]:
    """Estende `setor_de`/`cnpj_de` (do cadastro) aos tickers fora do cadastro ligados a uma empresa dele.

    Herda o CNPJ (ligar_a_cnpj) e o setor da empresa (setor único entre as ações do cadastro com esse CNPJ;
    mais de um setor distinto = sem setor). Devolve (setor_de, cnpj_de, herdados), herdados = {ticker: (cnpj, setor)}.
    Não altera os dicionários de entrada.
    """
```
Regra: para cada `t` em `tickers` com `t not in cnpj_de`: `cnpj, _ = ligar_a_cnpj(t, cnpj_de, mudancas)`; se `cnpj`:
`setores = {setor_de[x] for x, c in cnpj_de.items() if c == cnpj and setor_de.get(x)}`; `setor = única ou None`;
grava `cnpj_de2[t] = cnpj`, `setor_de2[t] = setor` (se não None) e `herdados[t] = (cnpj, setor)`.

**6b.2 `processamento/experimento/dataset.py`** (`montar_dataset`, ~:99-110): logo depois de calcular `tickers`,
`setor_de, cnpj_de, herdados = mapas_por_empresa(tickers, setor_de, cnpj_de, dados.mudancas)`; os mapas estendidos
alimentam `empresa`, `setor` e `variaveis_de_preco` (ret_vs_setor). Em `info`: `"setor_herdado": {t: setor}` ordenado
(vai para o JSON do dataset; serve para relatar ao usuário quais tickers ganharam setor). Notícias já ligam pelo
CNPJ (`ligar_empresa`) e não mudam.

**6b.3 `processamento/saida/pacotes_experimento.py:201`:** `cnpj_de.get(ticker) or ticker` → ligar pelo
`tickers.ligar_a_cnpj(ticker, cnpj_de, <mudanças disponíveis nos insumos>)[0] or ticker` (mesma ligação do dataset
e do `pacote_noticias.py:34`). Se as mudanças não estiverem acessíveis nessa função, reportar em vez de mudar.

**6b.4 Casos com VALORES ESPERADOS (`tests/test_setor_herdado.py`, novo):**
- A. cadastro `setor_de = {"JBSS32": "Consumo não Cíclico", "PETR4": "Petróleo", "AAAA3": "S1", "AAAB3": None}`,
  `cnpj_de = {"JBSS32": "C1", "PETR4": "C2", "AAAA3": "C3", "AAAB3": "C9"}`, `mudancas = {}`,
  `tickers = ["JBSS3", "PETR3", "XPTO3", "PETR4", "AAAA4"]` →
  `herdados == {"JBSS3": ("C1", "Consumo não Cíclico"), "PETR3": ("C2", "Petróleo"), "AAAA4": ("C3", "S1")}`;
  `"XPTO3" not in setor_de2 and "XPTO3" not in cnpj_de2`; `setor_de2["PETR4"] == "Petróleo"`; entradas intactas.
- B. raiz ambígua: cadastro `AAAA3` (C3, S1) e `AAAA11` (C4, S2) → `AAAA4` não herda (`herdados == {}`).
- C. via mudanças: `mudancas = {"CCRO3": "MOTV3"}`, cadastro `MOTV3` (C5, "Bens Industriais") →
  `herdados["CCRO3"] == ("C5", "Bens Industriais")`.
- D. CNPJ com dois setores no cadastro (`X1AA3` C6 "S1", `X1AA4` C6 "S2"), ticker `X1AA5` → `("C6", None)`, sem setor.
- E. `ret_vs_setor` no dataset (fábrica de um pregão t com retorno do dia): setor "S" com JBSS3 (herdado, C1),
  AAAA3 (C5) e BBBB3 (C6); retornos 0.01, 0.02, 0.04 → `ret_vs_setor` bruto JBSS3 = 0.01 − mean(0.02, 0.04) = −0.02;
  AAAA3 = 0.02 − mean(0.01, 0.04) = −0.005; BBBB3 = 0.04 − mean(0.01, 0.02) = 0.025 (antes da regra: JBSS3 NaN,
  AAAA3 = 0.02 − 0.04 = −0.02, BBBB3 = 0.04 − 0.02 = 0.02). Comparar a grade bruta (antes do rank).
  Coluna `setor` da linha JBSS3 = "S"; `empresa` = "C1"; `info["setor_herdado"] == {"JBSS3": "S"}`.

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_setor_herdado.py tests/test_exp_dataset.py tests/test_exp_variaveis.py tests/test_tickers.py tests/test_saida_pacotes_experimento.py`
(os que existirem) e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 7: top 5 provisório (item 7; depois da Fase 2)

**7.1 `processamento/config/parametros.yaml`**, bloco `saida`, logo depois de `  tom_neutro: 0.05 ...`:
```yaml
  publicar_top_provisorio: false            # true = grava experimento_top e experimento_historico mesmo com treino.modelo_oficial false (seção 8.5)
```
**7.2 `processamento/saida/parametros.py`**
- depois de `_CHAVES` (`:15`): `_OPCIONAIS = {"publicar_top_provisorio"}  # ausente = false (yamls de teste montados à mão)`.
- `ParametrosSaida` (`:23-31`): no fim, `publicar_top_provisorio: bool = False`.
- `desconhecidas = presentes - _CHAVES` (`:69`) → `desconhecidas = presentes - _CHAVES - _OPCIONAIS`.
- antes do `return ParametrosSaida(` (`:78`):
```python
    publicar = bloco.get("publicar_top_provisorio", False)
    if not isinstance(publicar, bool):
        raise ErroParametrosSaida(f"saida.publicar_top_provisorio deve ser true ou false (recebeu {publicar!r})")
```
  e `publicar_top_provisorio=publicar,` no `ParametrosSaida(...)`.

**7.3 `processamento/saida/gerar.py`**
- constantes, logo depois de `AVISO_COMPLETO` (`:43-44`):
```python
NAO_PUBLICADOS = ("experimento_historico", "experimento_top")   # só com modelo oficial ou publicar_top_provisorio
NOTA_TOP_NAO_PUBLICADO = ("Top 5 gerado e registrado só como teste de funcionamento (modelo não oficial): "
                          "experimento_top e experimento_historico não enviados à interface "
                          "(saida.publicar_top_provisorio = false).")
```
- em `gerar`, logo depois de `avisos: list[str] = [AVISO_COMPLETO] if completo else []` (`:112`):
  `publicar_top = bool(params_treino.modelo_oficial or params_saida.publicar_top_provisorio)`.
- no laço (`:265-268`), trocar
```python
            registros, removidos, novo_estado = produzido
            arquivo = contrato.gravar_lote(
                pasta, contrato.lote(nome, registros, gerado_em, dados_ate, removidos), compacto=nome in COMPACTOS
            )
```
  por
```python
            registros, removidos, novo_estado = produzido
            lote = contrato.lote(nome, registros, gerado_em, dados_ate, removidos)
            if nome in NAO_PUBLICADOS and not publicar_top:
                contrato.validar_lote(lote)   # confere o pacote, mas não grava nem lista em pacotes_enviados
                continue
            arquivo = contrato.gravar_lote(pasta, lote, compacto=nome in COMPACTOS)
```
- logo depois do laço, antes de `# 4b) checagem diária`: `if not publicar_top: avisos.append(NOTA_TOP_NAO_PUBLICADO)`.
- docstring de `gerar`: uma linha "Sem modelo oficial e sem `saida.publicar_top_provisorio`, `experimento_top` e
  `experimento_historico` são gerados (e o top registrado) mas não gravados na pasta (seção 8.5)."

**7.4 Testes:** seção 6.2 deste plano (7A-7D em `tests/test_saida_gerar.py`; 7E, 7F e o caso 6 CLI em
`tests/test_saida_completo.py`; parâmetros em `tests/test_saida_parametros.py`; ajustes de helper nos três
arquivos, inclusive `tests/test_rotina_executar.py`).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_saida_gerar.py tests/test_saida_completo.py tests/test_rotina_executar.py tests/test_saida_parametros.py tests/test_saida_experimento.py`
e depois `./.venv/Scripts/python.exe -m pytest -q`.

### Fase 8: especificação (item 6; só `ESPECIFICACAO.md`)

Aplicar os textos da seção 7 deste plano (âncoras pelas linhas citadas; conferir o texto "antes" antes de
trocar; os números de linha são de hoje e podem ter andado). Não mexer em mais nada. **Verificação:**
`grep -n "hoje vazia" ESPECIFICACAO.md` sem resultado; `grep -n "publicar_top_provisorio\|balanco_idade_max_meses\|JBSS3" ESPECIFICACAO.md`
mostra as linhas novas.

---

### Fase 9: corte da série na troca de ação por BDR (decisão do usuário, 24/10/2026; AGUARDA APROVAÇÃO)

**Fato (banco, 24/10/2026):** não há linha de JBSS3 em `v1-precos`; a coleta grava o histórico inteiro como JBSS32
desde 2019-12-30 (fechamento 39,03 em 2025-06-06 e 78,20 em 2025-06-09). A Fase 6 (não unir) não basta.

**Regra:** para cada troca ação → BDR (`troca_acao_para_bdr`) com `data_mudanca` preenchida, as linhas do ticker
novo com data **anterior** à `data_mudanca` passam a valer como o ticker antigo (JBSS32 antes de 2025-06-09 = JBSS3).
A linha do próprio dia da mudança fica com o novo. Coluna de data por tabela: `precos.data`, `proventos.data_com`,
`noticias.data_publicacao`. Troca sem `data_mudanca`: sem corte (como hoje). Aplicado na leitura (`fontes._tratar`,
antes de `unir_historicos`), então vale para painel, dataset, saída e diagnóstico.

**Código:** `tickers.cortes_acao_para_bdr(mudancas_df, tipo_de) -> list[tuple[str, str, date]]` e
`tickers.aplicar_cortes(df, cortes, coluna_data) -> DataFrame` (puras); `fontes.ler_cortes_bdr(ler)` (lê mudanças e,
se houver, o cadastro, como `ler_mudancas`); `_tratar` aplica os cortes nas 3 tabelas com ticker.

**Casos com VALORES ESPERADOS (`tests/test_corte_bdr.py`):**
- 9A `aplicar_cortes`: precos JBSS32 em 2025-06-05 (38.290001 / 35.880646), 2025-06-06 (39.029999 / 36.574078),
  2025-06-09 (78.199997 / 73.279350); corte ("JBSS3", "JBSS32", 2025-06-09) → tickers [JBSS3, JBSS3, JBSS32], preços iguais.
- 9B retorno suspeito: antes do corte, `retornos_suspeitos` acusa JBSS32 em 2025-06-09 (73.279350 / 36.574078 − 1 =
  1.00359 > 1.0); depois, nenhum; o retorno de JBSS3 em 2025-06-06 = 36.574078 / 35.880646 − 1 ≈ 0.019326 e o de JBSS32
  em 2025-06-09 fica vazio (primeiro preço).
- 9C universo histórico: composição JBSS3 de 2021-01-01 a 2025-06-08, cadastro JBSS32 BDR → em 2025-06-06 JBSS3 `ok`
  (tipo ON pela classe) e JBSS32 `tipo_nao_aceito`; em 2025-06-09 JBSS3 `fora_da_composicao`.
- 9D setor herdado: `info["setor_herdado"] == {"JBSS3": <setor do JBSS32>}`; linha JBSS3 de 2025-06-06 com
  `empresa` = CNPJ do JBSS32.
- 9E notícias: notícia JBSS32 de 2025-06-01 vira JBSS3 (mesma empresa pela raiz); a de 2025-06-10 continua JBSS32.
- 9F troca sem `data_mudanca` → nenhum corte; troca ação → ação (CCRO3 → MOTV3) → só a união de sempre.
- 9G leitura: `fontes.ler_tabela("precos", ler=falso)` com o `ler` falso das fixtures de 9A devolve as linhas cortadas.

**Esperado no banco real (conferência depois de implementar):** dataset + 1.103 linhas de JBSS3 (2021: 247,
2022: 250, 2023: 248, 2024: 251, 2025: 107; 358 delas no desenvolvimento) se a vigência na composição for contínua;
`setor_herdado` = {"JBSS3": setor do JBSS32}; diagnóstico: JBSS3 sai da lista "sem nenhum preço" (49 → 48) e JBSS32
2025-06-09 sai dos retornos suspeitos; painel: série JBSS32 passa a começar em 2025-06-09 (reenvio inteiro uma vez,
`substituir_serie`), `rentabilidade.a1` do JBSS32 em 2026-10-23 continua `ok` (mais de 252 pregões desde 2025-06-09).

**Verificação:** `./.venv/Scripts/python.exe -m pytest -q tests/test_corte_bdr.py tests/test_mudanca_bdr.py tests/test_setor_herdado.py tests/test_fontes_leitura.py tests/test_universo.py tests/test_exp_dataset.py`
e depois `pytest -q` completo.

## 11. Riscos

| Risco | Mitigação |
|---|---|
| Rodada da segunda mais lenta (preços de ~7 anos no dataset, séries, universo) e passar das 9h45/10h | teste do usuário com `--completo` antes (seção Resumo); o `execucao.json` mostra o tempo |
| Outro defeito do histórico novo aparecer no dataset real (não visível sem banco) | teste de banco do usuário; erro num pacote vira aviso + `parcial`, os outros pacotes saem |
| Fase 6 lê o cadastro a cada leitura de tabela com ticker (3 consultas pequenas a mais) | custo desprezível (~100 linhas) |
| Fixture de outro teste com balanço de referência > 15 meses antes de t (Fase 2) | nenhuma encontrada (fábricas de 2024-2026); se aparecer, reportar o teste, não mudar o esperado |
| Fases paralelas pegando o meio da edição da outra no `pytest -q` | rodar os testes da própria fase e avisar |
