# PLANO: ETAPA 6, TREINO E AVALIAÇÃO (teste de funcionamento)

> **Aprovado pelo usuário em 23/10/2026**: decisões 1 a 19 com as recomendações, e um ajuste na decisão 1 (o teste final tem **fim**: a véspera da entrada da rotina diária em produção, fixada na etapa 8; `treino.teste_final.fim` vazio = trava ativa; depois do fim vem o "teste ao vivo"). Decisões registradas na ESPECIFICACAO (7.5, 7.7 e seção 9, "Decisões da etapa 6"). Este arquivo já está com o ajuste. **Implementado em 23/10/2026.** Ajuste posterior aprovado: o teste final avalia só as linhas com dia do alvo (t+1) ≤ `fim` (`validacao.linhas_com_alvo_ate`); a linha do `fim` é a 1ª previsão ao vivo. Com isso, `periodo_teste_final(df, 2025-12-15, 2026-01-05)` passa a dar 12-23 a 01-02 (8 linhas), e não até 01-05 como no Caso 2 abaixo.

Quando o plano foi feito (23/10/2026), `pytest -q` dava **753 passed, 22 skipped**. Ambiente: Python 3.12.10 (.venv), pandas 3.1.0, xgboost 3.4.1, scikit-learn 1.9.1, numpy 2.5.4. Conferi no venv todos os gabaritos abaixo (AUCs, ECE, Brier, sha256, faixa do acaso, dobras). Também conferi que `pred_contribs` soma igual à margem (erro máximo de 3,6e-6), que o XGBoost com semente fixa é reprodutível e que o modelo salvo e relido prevê igual.

## Resumo

A etapa entrega `python -m processamento.experimento.treino`. Ele lê **só os CSV** do dataset (`saida/experimento/dataset-<versao>-<data>.csv`, conferindo o sha256 do JSON ao lado). **Não acessa o banco.** O fluxo:
- tira na hora as linhas do teste final e o pregão de embargo antes dele;
- roda o walk-forward mensal com embargo de 1 pregão no período de desenvolvimento;
- escolhe blocos e grade só nas dobras de desenvolvimento;
- avalia o modelo 1, o modelo 3, o 3b, a logística, a regra da volatilidade e os extras "principais" e "hora real na noite", contra a faixa do acaso (top 5 e top 3);
- confere a calibração, salva o modelo provisório em `modelos/` e grava o relatório com o aviso "TESTE DE FUNCIONAMENTO" no topo.

O teste final vai de `treino.teste_final.inicio` (23/06/2026) até `treino.teste_final.fim` (a véspera da entrada em produção, fixada na etapa 8; hoje vazio). Ele só roda com **quatro condições juntas**: `fim` preenchido, `treino.teste_final.liberado: true` no yaml, a opção `--teste-final` na linha de comando e o registro de uso único ainda inexistente. As linhas depois do `fim` são o "teste ao vivo" e não entram em nenhum dos dois modos.

**Pronto quando (seção 9, etapa 6):** "Pipeline completo rodando com o 1 ano atual (teste de funcionamento, não conclusão)". Traduzindo:
- (a) `pytest -q` sem falhas;
- (b) depois de o usuário regerar os 3 datasets, `python -m processamento.experimento.treino` sai com código 0 e grava o relatório, o `metricas.json`, as previsões e `modelos/xgb-2026-06.json` com o `.meta.json`;
- (c) nenhuma linha com data ≥ 2026-06-23 aparece nas saídas;
- (d) `... treino --teste-final` sai com código 4 ("trava fechada").

---

## Pegadinhas para copiar em TODO despacho ao implementador

1. **Banco:** nada de SQL e nada de banco nos módulos novos. O treino lê só CSV e não importa `fontes.criar_engine`. A pasta `extracao-dados-tcc-main/` é só consulta: nunca executar nem importar nada dela.
2. **Ausência = NaN, nunca 0.** Nada de `fillna(0)` nas variáveis. O XGBoost trata NaN sozinho. A logística imputa só dentro do próprio Pipeline.
3. **YAML:** datas e horas entre aspas (`"2026-06-23"`; sem aspas o PyYAML devolve `datetime.date`, e o validador deve recusar). Booleanos `true`/`false` sem aspas. `"ON"`/`"OFF"` sempre entre aspas.
4. **Bloco novo `treino`:** a chave de topo precisa entrar em `calendario._CHAVES_DE_TOPO` (calendario.py:21), senão `carregar_parametros` dá erro. `carregar_parametros` tem `lru_cache`: nos testes, passar o caminho de um yaml temporário.
5. **pandas 3.1:** Copy-on-Write (atribuição encadeada não funciona; usar `.loc` ou `assign`) e texto como dtype padrão. Ler o CSV com `dtype={"ticker": str, "empresa": str, "setor": str, "universo": str}`, porque o CNPJ tem zero à esquerda.
6. **Semente fixa em tudo:**
   - XGBoost: `random_state=semente`, `n_jobs=1`, `tree_method="hist"`;
   - sorteios e bootstrap: `np.random.default_rng(semente)`;
   - logística: `random_state=semente`.
7. **Linguagem:** nunca "compre", "recomendação", "oportunidade" ou "melhores ações". Usar "estimativa", "experimento", "maior chance segundo o modelo". O aviso fixo "Não constitui recomendação de investimento." é a única ocorrência permitida de "recomendação".
8. **Testes:** nada de rede ou banco, dados pequenos inventados. Gabarito só o deste plano. Rodar com `.venv/Scripts/python -m pytest -q`. Não fazer commit.
9. **Ranks:** `preparacao.preparar` faz o rank por pregão (só entre ações do mesmo dia). Por isso, filtrar **datas inteiras** antes de `preparar` não muda os ranks. Linhas sem alvo saem **depois** de `preparar`, com `linhas_de_treino`.

---

## Fases (cada uma é um despacho)

| Fase | Arquivos | Depende de | Paralela com |
|---|---|---|---|
| 0a | alvo.py, preparacao.py, tests/test_exp_alvo.py | — | 0b, 1, 2, 3, 4 |
| 0b | noticias.py, dataset.py, tests/test_exp_noticias.py, tests/test_exp_dataset.py | — | 0a, 1, 2, 3, 4 |
| 1 | calendario.py, parametros.yaml, experimento/parametros.py, tests/test_treino_parametros.py | — | 0a, 0b, 2, 3, 4 |
| 2 | experimento/validacao.py (novo), tests/test_treino_validacao.py | — | 0a, 0b, 1, 3, 4 |
| 3 | experimento/avaliacao.py (novo), tests/test_treino_avaliacao.py | — | 0a, 0b, 1, 2, 4 |
| 4 | experimento/modelos.py (novo), tests/test_treino_modelos.py | — | 0a, 0b, 1, 2, 3 |
| 5 | experimento/previsao.py (novo), tests/test_treino_previsao.py | 3, 4 | 6b |
| 6a | experimento/treino.py (núcleo), tests/fabrica_treino.py, tests/test_treino_nucleo.py | 0a, 1, 2, 3, 4 | 6b |
| 6b | experimento/relatorio.py (novo), tests/test_treino_relatorio.py | só o esquema do `metricas` (abaixo) | 5, 6a |
| 6c | experimento/treino.py (executar, main, trava, gravação), tests/test_treino_pipeline.py, tests/test_treino_trava.py | todas | — |

**Ação do usuário depois da 0a e da 0b (lê o banco, então o subagente não roda):**
```
python -m processamento.experimento.dataset --versao todas
python -m processamento.experimento.dataset --versao principais
python -m processamento.experimento.dataset --versao hora_real_noite
```
O CSV atual (`dataset-todas-2026-10-21.csv`) não tem a coluna nova e precisa ser regerado.

---

### Fase 0a: coluna `alvo_abertura_valido` (pegadinha 16; seção 10)

**`processamento/experimento/alvo.py`**, em `alvos()`, depois da linha 62 (`ret_ibov_ab_t1 = ...`):
```python
    ibov_ab_t1 = ibov_ab.shift(-1)
    igual = pd.Series(np.isclose(ibov_ab_t1, ibov_fech, rtol=0.0, atol=1e-9), index=ibov_fech.index)
    valido = (~igual).astype(float).where(ibov_ab_t1.notna() & ibov_fech.notna())
```
No dict de retorno, acrescentar `"alvo_abertura_valido": _repetir_ibov(valido, aj),`. Na docstring: "1.0 se a abertura do IBOV em t+1 ≠ o fechamento do IBOV em t (abertura informada); 0.0 se igual (defeito do Yahoo); NaN se faltar algum lado ou no último pregão".

**`processamento/experimento/preparacao.py:18`**
- Antes: `COLUNAS_ALVO = ["alvo", "alvo_abertura", "ret_t1", "ret_ibov_t1"]`
- Depois: `COLUNAS_ALVO = ["alvo", "alvo_abertura", "alvo_abertura_valido", "ret_t1", "ret_ibov_t1"]`

A coluna olha t+1, por isso fica no grupo do alvo. O teste de vazamento (`test_vazamento_experimento.py`) descarta `COLUNAS_ALVO` e continua valendo sem mudança.

**Teste novo em `tests/test_exp_alvo.py`**, usando o `_precos()` que já existe (IBOV com abertura [64000, 64320, 68000] e fechamento [64000, 68000, 68000]):
```python
def test_abertura_do_ibov_valida_so_quando_difere_do_fechamento_anterior():
    v = alvos(_precos(), CAL, TICKERS)["alvo_abertura_valido"]
    for t in TICKERS:                  # vale igual para todas as ações, inclusive DDDD3 (com NaN)
        assert v.loc[D0, t] == 1.0     # abertura(D1)=64320 ≠ fechamento(D0)=64000
        assert v.loc[D1, t] == 0.0     # abertura(D2)=68000 = fechamento(D1)=68000
        assert pd.isna(v.loc[D2, t])   # último pregão: sem t+1
```
**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_exp_alvo.py tests/test_exp_dataset.py tests/test_exp_dataset_saida.py tests/test_exp_preparacao.py tests/test_vazamento_experimento.py`

---

### Fase 0b: versão de notícias `hora_real_noite` (teste extra da 7.5)

**`processamento/experimento/noticias.py`**
- Linha 16: `VERSOES = ("todas", "principais", "hora_real_noite")`.
- Em `filtrar_versao`, trocar o `if/else` das linhas 35-38 e o cálculo das linhas 41-43 por:
```python
    if versao == "todas":
        dentro = pd.Series(True, index=noticias.index)
    elif versao == "principais":
        dentro = _na_versao_principal(noticias, params)
    else:  # hora_real_noite: só horário real (nem "só data", nem sem hora)
        if "precisao_hora" not in noticias.columns:
            raise ValueError("versão hora_real_noite exige a coluna precisao_hora (fontes.aplicar_regra_so_data)")
        dentro = noticias["precisao_hora"].eq("hora")
    fora = noticias[~dentro]
    contagens["fora_versao"] = len(fora)
    if versao == "principais":
        contagens["papel_vazio_fora"] = int(
            (fora["papel"].isna() & ~fora["origem"].isin(params.origens_principais)).sum()
        )
```
- Em `preparar_noticias`, na primeira linha: `if versao == "hora_real_noite": params = dataclasses.replace(params, inicio_janela="fechamento")`, com `import dataclasses` no topo.

**`processamento/experimento/dataset.py`**
- Apagar `VERSOES = ("todas", "principais")` (linha 141) e importar `VERSOES` de `noticias` (`from processamento.experimento.noticias import VERSOES, preparar_noticias`).
- Texto de ajuda do `--versao`: "notícias: todas, principais ou hora_real_noite".
- No `info` de `montar_dataset`, acrescentar `"inicio_janela_efetivo": "fechamento" if versao_noticias == "hora_real_noite" else params.inicio_janela`.

**Testes em `tests/test_exp_noticias.py`** (usar `from processamento import fontes`; os títulos **precisam ser diferentes**, senão a deduplicação por título junta as notícias):
```python
def _quatro():
    return fontes.aplicar_regra_so_data(fazer([
        nota(1, "AAAA3", hora="2026-06-18 19:00", titulo="A"),   # hora real, noite de 18/06
        nota(2, "AAAA3", hora="2026-06-18 11:00", titulo="B"),   # hora real, pregão
        nota(3, "AAAA3", origem="cvm_ipe", titulo="C"),          # sem hora
        nota(4, "AAAA3", hora="2026-06-18 04:00", titulo="D"),   # 00:00 em LA = só data
    ]))
def test_filtro_hora_real_noite_mantem_so_hora_real():
    filtradas, info = filtrar_versao(_quatro(), "hora_real_noite", PARAMS)
    assert set(filtradas["id"]) == {1, 2}
    assert info == {"lidas": 4, "fora_versao": 2, "papel_vazio_fora": 0}
def test_hora_real_noite_so_fica_a_noite():
    saida, info = preparar_noticias(_quatro(), CAL, CNPJ_DE, {}, "hora_real_noite", PARAMS)
    assert saida["id"].tolist() == [1]
    assert saida["pregao_ref"].iloc[0] == pd.Timestamp("2026-06-18")
    assert info["fora_versao"] == 2 and info["descartadas_fora_da_janela"] == 1 and info["preparadas"] == 1
def test_hora_real_noite_sem_precisao_hora_levanta():
    with pytest.raises(ValueError, match="precisao_hora"):
        filtrar_versao(fazer([nota(1, "AAAA3", hora="2026-06-18 19:00")]), "hora_real_noite", PARAMS)
```

**Teste em `tests/test_exp_dataset.py`**, no fixture `caso`, igual ao de `principais`. Na `integracao()`, c3 é cvm_ipe sem hora em cal[3] e a20 é AAAA4 às 19:00 de cal[20], que cai na noite (fechamento às 17:00).
```python
def test_versao_hora_real_noite(caso):
    df, info = montar_dataset(caso["dados"], caso["cal"], versao_noticias="hora_real_noite")
    c = caso["cal"]
    assert info["inicio_janela_efetivo"] == "fechamento" and info["preparadas"] == 1 and info["fora_versao"] == 1
    assert _dia(df, c[3], "BBBB3").iloc[0]["noticias_dia_qtd"] == 0      # em "todas" é 1
    for t in ["AAAA3", "AAAA4"]:
        assert _dia(df, c[20], t).iloc[0]["noticias_dia_qtd"] == 1
        assert _dia(df, c[20], t).iloc[0]["noticias_dia_tom"] == pytest.approx(0.6, abs=1e-9)
    fora = [col for col in COLUNAS_DATASET if col not in COLUNAS_NOTICIAS]
    pd.testing.assert_frame_equal(caso["df"][fora], df[fora])
```
**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_exp_noticias.py tests/test_exp_dataset.py tests/test_exp_dataset_saida.py`

---

### Fase 1: parâmetros do treino

**`processamento/calendario.py:21`:** acrescentar `"treino"` ao conjunto `_CHAVES_DE_TOPO`.

**`processamento/config/parametros.yaml`:** acrescentar no fim:
```yaml
# Fase 2: treino e avaliação (seções 7.4–7.7; plano da etapa 6). Com ~1 ano de histórico: SÓ TESTE DE FUNCIONAMENTO.
treino:
  semente: 20261023
  inicio_experimento: "cobertura"   # "cobertura" = cobertura_inicio do JSON do dataset (1ª data com notícias) ou "AAAA-MM-DD"
  treino_minimo_meses: 3            # meses de treino antes da 1ª dobra de teste
  embargo_pregoes: 1
  teste_final:
    inicio: "2026-06-23"            # 1º dia do teste final (o período reservado na v1 e nunca usado)
    fim: null                       # véspera da entrada em produção (etapa 8), "AAAA-MM-DD"; vazio = trava ativa. Depois: teste ao vivo
    liberado: false                 # true SÓ por decisão do usuário; mesmo assim exige --teste-final; uso único
  topk: [5, 3]                      # o primeiro é o corte principal
  xgboost: {n_estimators: 300, max_depth: 3, learning_rate: 0.03, subsample: 0.8, colsample_bytree: 0.8, min_child_weight: 50, reg_lambda: 5}
  grade: {max_depth: [2, 3], min_child_weight: [50, 200]}   # escolhida só nas dobras de desenvolvimento
  ganho_minimo_bloco: 0.005         # AUC médio por pregão; o bloco entra se o ganho passar disso
  logistica_c: 1.0
  acaso_sorteios: 10000
  bootstrap_reamostragens: 2000
  bootstrap_bloco_pregoes: 5
  motivos_qtd: 3
  motivos_limiar: 0.01              # |contribuição| (escala log-odds) até isto = "neutro"
  calibracao: {bins: 10, ece_maximo: 0.02, linhas_minimas: 5000, liberar_chance: false}
```

**`processamento/experimento/parametros.py`:** acrescentar, reaproveitando `_inteiro_positivo`, `_booleano` e `ErroParametrosExperimento`:
- `@dataclass(frozen=True) class ParametrosTreino` com os campos:
  - `semente: int`, `inicio_experimento: str`, `treino_minimo_meses: int`, `embargo_pregoes: int`;
  - `teste_final_inicio: date`, `teste_final_fim: date | None`, `teste_final_liberado: bool`, `topk: tuple[int, ...]`;
  - `xgboost: dict`, `grade: dict[str, tuple]`, `ganho_minimo_bloco: float`, `logistica_c: float`;
  - `acaso_sorteios: int`, `bootstrap_reamostragens: int`, `bootstrap_bloco_pregoes: int`;
  - `motivos_qtd: int`, `motivos_limiar: float`;
  - `calibracao_bins: int`, `calibracao_ece_maximo: float`, `calibracao_linhas_minimas: int`, `liberar_chance: bool`.
- `carregar_parametros_treino(caminho: str | None = None) -> ParametrosTreino`. Valida:
  - o conjunto exato de chaves (desconhecida ou faltante dá erro, com mensagem `treino.<chave> ...`);
  - `semente`: inteiro ≥ 0;
  - `inicio_experimento`: `"cobertura"` ou texto AAAA-MM-DD;
  - `teste_final.inicio`: **texto** AAAA-MM-DD (um `date` vindo do YAML sem aspas dá erro "use aspas");
  - `teste_final.fim`: `null` (→ `None`, trava ativa) ou **texto** AAAA-MM-DD ≥ `inicio` (sem aspas dá erro "use aspas"; antes do início dá erro);
  - `liberado` e `liberar_chance`: bool;
  - `embargo_pregoes` ≥ 1;
  - `topk`: lista não vazia de inteiros positivos distintos;
  - `xgboost`: exatamente as 7 chaves, com `n_estimators` e `max_depth` inteiros > 0 e os demais números > 0;
  - `grade`: chaves contidas nas do `xgboost`, cada uma com uma lista não vazia de valores válidos;
  - floats ≥ 0, sem aceitar bool.

**Testes (`tests/test_treino_parametros.py`, no estilo de `test_exp_parametros.py`, com `_CABECALHO_YAML` + bloco):**
- o yaml real carrega com `teste_final_inicio == date(2026, 6, 23)`, `teste_final_fim is None`, `teste_final_liberado is False`, `topk == (5, 3)`, `xgboost["min_child_weight"] == 50` e `liberar_chance is False`;
- `liberado: "false"` (texto) dá erro;
- `inicio: 2026-06-23` sem aspas dá erro com "aspas";
- `fim: "2026-11-30"` carrega como `date(2026, 11, 30)`; `fim: "2026-06-22"` (antes do início) dá erro; `fim: 2026-11-30` sem aspas dá erro com "aspas";
- `grade: {gamma: [1]}` dá erro;
- `topk: []` dá erro;
- `embargo_pregoes: 0` dá erro;
- uma chave a mais dá erro;
- `calendario.carregar_parametros(caminho)` aceita o bloco `treino`.

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_parametros.py tests/test_exp_parametros.py tests/test_calendario.py`

---

### Fase 2: `processamento/experimento/validacao.py` (períodos e dobras; funções puras)

```python
@dataclass(frozen=True)
class Dobra:
    numero: int; mes_teste: str            # "AAAA-MM"
    datas_treino: tuple[date, ...]; datas_teste: tuple[date, ...]

def aplicar_inicio(df, inicio: date | None) -> pd.DataFrame          # linhas com data >= inicio (None = todas)
def periodo_desenvolvimento(df, inicio_teste_final: date, embargo: int = 1) -> pd.DataFrame
    # mantém data < inicio_teste_final e tira as `embargo` ÚLTIMAS datas distintas que sobraram; nunca devolve linha >= inicio
def periodo_teste_final(df, inicio_teste_final: date, fim_teste_final: date) -> pd.DataFrame
    # inicio <= data <= fim (só no modo liberado); linhas depois do fim = teste ao vivo, nunca entram
def dobras_walk_forward(cal: list[date], treino_minimo_meses: int, embargo: int = 1) -> list[Dobra]
    # meses = (ano, mês) distintos de cal, em ordem; para j em range(treino_minimo_meses, len(meses)):
    # teste = datas do mês j; anteriores = datas < teste[0]; treino = anteriores[:-embargo]; treino vazio -> pula
def dobras_teste_final(cal: list[date], inicio: date, fim: date, embargo: int = 1) -> list[Dobra]
    # meses das datas em [inicio, fim]; teste = datas do mês dentro de [inicio, fim]; treino = datas < teste[0], menos as `embargo` últimas
    # nenhuma data > fim aparece em treino nem em teste
def linhas_da_dobra(prep, dobra) -> tuple[pd.DataFrame, pd.DataFrame]
    # (treino, teste): linhas cujas datas estão na dobra E com alvo não nulo
```

**Regra do embargo** (seção 7.5 e glossário): o alvo de t olha t+1. O pregão imediatamente anterior ao 1º dia de teste tem o alvo **dentro** do teste, então sai do treino. Isso equivale à rotina real: no retreino da manhã do 1º dia útil do mês, o alvo desse pregão ainda não existe.

**Caso 1: calendário de 14 pregões** (fins de semana; 20/11 feriado; 24, 25 e 31/12 e 01/01 sem pregão):
`2025-10-29, 10-30, 10-31, 11-03, 11-19, 11-21, 11-28, 12-01, 12-23, 12-26, 12-30, 2026-01-02, 01-05, 01-30`

Com `treino_minimo_meses=1` saem 3 dobras:

| # | mes_teste | datas_treino | datas_teste |
|---|---|---|---|
| 1 | 2025-11 | 10-29, 10-30 | 11-03, 11-19, 11-21, 11-28 |
| 2 | 2025-12 | 10-29, 10-30, 10-31, 11-03, 11-19, 11-21 | 12-01, 12-23, 12-26, 12-30 |
| 3 | 2026-01 | 10-29, 10-30, 10-31, 11-03, 11-19, 11-21, 11-28, 12-01, 12-23, 12-26 | 2026-01-02, 01-05, 01-30 |

Com `treino_minimo_meses=2`, saem só as dobras 2025-12 e 2026-01 (iguais às de cima, numeradas 1 e 2).

**Caso 2: nenhuma linha de teste no treino, e o embargo**

Base: tickers A e B em todas as 14 datas, com `alvo` 1.0, exceto (B, 2025-11-19), que tem alvo NaN.
- Em cada dobra: datas de treino ∩ datas de teste = ∅; `max(treino) < teste[0]`; o pregão anterior a `teste[0]` (10-31, 11-28 e 12-30) **não** está no treino; para toda data de treino d, o pregão seguinte a d no calendário é < `teste[0]`.
- `linhas_da_dobra`, contando linhas (treino, teste): dobra 1 = (4, 7); dobra 2 = (11, 8); dobra 3 = (19, 6).
- `periodo_desenvolvimento(df, date(2026,1,1))`: as datas que sobram vão de 10-29 a 12-26 (10 datas); 12-30 (o embargo) e as de 2026 saem.
- `periodo_desenvolvimento(df, date(2026,1,5))`: sobram 11 datas, até 12-30. Sai 01-02, o embargo que atravessa a virada do ano.
- `dobras_walk_forward` sobre o resultado de `inicio=2026-01-01` com mínimo 1: dobra 2025-11 igual à de cima; dobra 2025-12 com treino [10-29 … 11-21] e teste [12-01, 12-23, 12-26].
- `dobras_teste_final(cal14, date(2025,12,15), date(2026,1,30))`:
  - dobra A, mês 2025-12: teste [12-23, 12-26, 12-30], treino [10-29 … 11-28] (7 datas; 12-01 sai pelo embargo);
  - dobra B, mês 2026-01: teste [01-02, 01-05, 01-30], treino [10-29 … 12-26] (10 datas).
- `dobras_teste_final(cal14, date(2025,12,15), date(2026,1,5))` (fim no meio do mês): dobra A igual; dobra B com teste [01-02, 01-05] (01-30 é teste ao vivo e fica fora) e o mesmo treino de 10 datas.
- `dobras_teste_final(cal14, date(2025,12,15), date(2025,12,26))`: uma dobra só, teste [12-23, 12-26], treino [10-29 … 11-28] (7 datas).
- `periodo_teste_final(df, date(2025,12,15), date(2026,1,5))`: datas 12-23, 12-26, 12-30, 01-02, 01-05 (10 linhas, A e B).

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_validacao.py`

---

### Fase 3: `processamento/experimento/avaliacao.py` (métricas; funções puras)

```python
def ordenar_no_dia(df, coluna_score="score") -> pd.DataFrame
    # ordena por data asc, score desc, ticker asc; acrescenta `posicao` 1..n por data; score NaN -> ValueError
def resumo_diario(df, k, *, coluna_alvo="alvo", coluna_score="score", com_retorno=True) -> pd.DataFrame
    # candidatos = linhas com coluna_alvo não nulo; só dias com >= k candidatos
    # colunas: data, n_candidatos, acertos_top, acerto_top (=acertos/k), acertos_ultimos, acerto_ultimos
    #   (+ com_retorno: ret_top, ret_ultimos, ret_ibov, excesso_top = ret_top − ret_ibov, excesso_ultimos)
    # top = k primeiros de ordenar_no_dia; ultimos = k últimos da MESMA ordem
def metricas_periodo(diario, com_retorno=True) -> dict
    # n_dias, taxa_acerto = média de acerto_top, taxa_ultimos, dif_top_ultimos (+ excesso_medio, excesso_ultimos, dif_excesso)
def auc_geral(df, coluna_alvo="alvo", coluna_score="score") -> float | None      # sklearn roc_auc_score; uma classe só -> None
def auc_por_pregao(df, ...) -> pd.Series                                          # índice data; dias com uma classe só ficam fora
def faixa_do_acaso(df, k, n_sorteios, semente, *, coluna_alvo="alvo", com_retorno=True) -> dict
def ic_bootstrap_blocos(valores, tamanho_bloco, n_reamostragens, semente) -> tuple[float | None, float | None]
def diferenca_pareada(a: pd.Series, b: pd.Series) -> pd.Series                   # séries indexadas por data; junção interna; a − b
def por_ano(diario, com_retorno=True) -> pd.DataFrame                             # ano, n_dias, taxa_acerto (+ excesso_medio)
def sensibilidade_ultimo_ano(diario) -> dict
    # corte = última data − 1 ano (pd.DateOffset(years=1)); "ultimo_ano" = data > corte; "anteriores" = o resto (None se vazio)
def linhas_abertura_valida(df) -> pd.DataFrame       # alvo_abertura_valido == 1 E alvo_abertura não nulo
def calibracao(prob, alvo, bins, ece_maximo, linhas_minimas) -> dict
    # faixa = min(floor(p*bins), bins−1); ECE = Σ (n_b/N)·|média_p_b − média_y_b|; brier = média (p−y)²
    # aprovada = N >= linhas_minimas e ECE <= ece_maximo; tabela = [{bin, n, media_prevista, media_real}]
def comparar_com_acaso(taxa, faixa: dict) -> str     # "acima" (> p97_5) | "abaixo" (< p2_5) | "dentro"
```

**Algoritmo exato da faixa do acaso.** Ele fixa o gabarito, então tem que ser seguido à risca:
- `rng = np.random.default_rng(semente)`;
- dias em ordem crescente e só os que têm ≥ k candidatos;
- dentro do dia, candidatos ordenados por ticker;
- por dia: `u = rng.random((S, n))`, `esc = np.argsort(u, axis=1, kind="stable")[:, :k]`, `acerto += alvo[esc].sum(1)/k` e (com_retorno) `excesso += ret[esc].mean(1) − ret_ibov_do_dia`;
- no fim, dividir os dois por `n_dias`.

Devolve `media`, `p2_5`, `p97_5` (`np.percentile(…, [2.5, 97.5])`), `n_sorteios`, `n_dias`, os campos `excesso_*` e as arrays `distribuicao_acerto` e `distribuicao_excesso` (estas não vão para o JSON).

**Bootstrap circular:**
- `rng = default_rng(semente)`, `n = len`, `L = min(L, n)`, `m = ceil(n/L)`;
- em cada reamostragem: `ini = rng.integers(0, n, size=m)`, `idx = ((ini[:, None] + np.arange(L)) % n).ravel()[:n]`, estatística = `valores[idx].mean()`;
- IC = `np.percentile(stats, [2.5, 97.5])`; série vazia dá `(None, None)`.

**Caso 3: top 5 e top 3 com desempate (score desc, ticker asc).** Entregar as linhas **embaralhadas** na entrada.

Dia D1 = 2026-03-02, `ret_ibov_t1` = 0.005:

| ticker | score | alvo | ret_t1 |
|---|---|---|---|
| AAAA3 | 0.70 | 1 | 0.020 |
| BBBB3 | 0.60 | 0 | −0.010 |
| CCCC3 | 0.60 | 1 | 0.015 |
| DDDD3 | 0.55 | 1 | 0.008 |
| EEEE3 | 0.50 | 0 | −0.004 |
| FFFF3 | 0.50 | 1 | 0.012 |
| GGGG3 | 0.40 | 0 | −0.020 |

Dia D2 = 2026-03-03, `ret_ibov_t1` = −0.002:

| ticker | score | alvo | ret_t1 |
|---|---|---|---|
| AAAA3 | 0.30 | 1 | 0.010 |
| BBBB3 | 0.90 | 0 | −0.005 |
| CCCC3 | 0.80 | 1 | 0.001 |
| DDDD3 | 0.20 | 0 | −0.010 |
| EEEE3 | 0.85 | **NaN** | NaN |
| FFFF3 | 0.10 | 1 | 0.004 |
| GGGG3 | 0.50 | 0 | −0.003 |

Seleções esperadas:
- D1: top 5 = [AAAA3, BBBB3, CCCC3, DDDD3, EEEE3]. FFFF3 fica de fora pelo desempate com EEEE3 (0.50). Top 3 = [AAAA3, BBBB3, CCCC3]. Últimos 3 = [EEEE3, FFFF3, GGGG3]. Últimos 5 = [CCCC3, DDDD3, EEEE3, FFFF3, GGGG3]. `n_candidatos` = 7.
- D2: EEEE3 sai por ter alvo NaN, então `n_candidatos` = 6. Top 5 = [BBBB3, CCCC3, GGGG3, AAAA3, DDDD3]. Top 3 = [BBBB3, CCCC3, GGGG3]. Últimos 3 = [AAAA3, DDDD3, FFFF3]. Últimos 5 = [CCCC3, GGGG3, AAAA3, DDDD3, FFFF3].

**Caso 4: números exatos** (tolerância 1e-12):

| | D1 acerto | D1 excesso | D2 acerto | D2 excesso | período: taxa | período: excesso médio |
|---|---|---|---|---|---|---|
| top 5 | 0.6 (acertos_top=3) | 0.0008 | 0.4 (2) | 0.0006 | **0.5** | **0.0007** |
| top 3 | 2/3 (2) | 0.01/3 | 1/3 (1) | −0.001/3 | **0.5** | **0.0015** |
| últimos 5 | 0.6 | −0.0028 | 0.6 | 0.0024 | 0.6 | −0.0002 |
| últimos 3 | 1/3 | −0.009 | 2/3 | 0.004/3 + 0.002 = 0.01/3 | 0.5 | −0.017/6 |

AUC das 13 linhas candidatas:
- AUC geral = **15/28** (0,5357142857);
- AUC de D1 = **0.75** e de D2 = **1/3**;
- AUC médio por pregão = **13/24** (0,5416666667).

**Caso 5: faixa do acaso**
- (a) **Universo = k, sem aleatoriedade:** k=3; dia 1 com alvos [1, 0, 1] e dia 2 com [0, 0, 1], 3 candidatos por dia. Resultado: `media = p2_5 = p97_5 = 0.5`, com S=10000 e qualquer semente.
- (b) **Todos acertam:** 3 dias × 6 ações com alvo 1, k=5. Resultado: `[1.0, 1.0]`, média 1.0.
- (c) **Gabarito com semente:** 10 tickers por dia (`AAAA3, BBBB3, …, JJJJ3`, em ordem), alvo [1,1,1,1,0,0,0,0,0,0] na ordem dos tickers, 3 dias iguais, k=5, S=10000, semente=123, todos com ret_t1 = 0.01 e ret_ibov = 0.0. Esperado:
  - `media == approx(0.39912, abs=1e-12)`, `p2_5 == 0.2`, `p97_5 == 0.6`;
  - `excesso_media`, `excesso_p2_5` e `excesso_p97_5` iguais a approx 0.01;
  - duas chamadas com a mesma semente dão `distribuicao_acerto` idênticas (`np.array_equal`).
- (d) **Excesso degenerado:** em (a) com todos os ret = 0.02 e ibov = 0.005, a faixa de excesso é [0.015, 0.015].

**Caso 7: `alvo_abertura` só nos dias válidos**, com k=2 e 4 tickers (A, B, C, D):

| dia | alvo_abertura_valido | scores A/B/C/D | alvo_abertura A/B/C/D |
|---|---|---|---|
| D1 | 1 | .9/.8/.1/.2 | 1/0/1/0 |
| D2 | **0** | .9/.8/.1/.2 | 1/1/0/0 |
| D3 | 1 | .1/.2/.9/.8 | 0/**NaN**/1/1 |

Passando `resumo_diario(linhas_abertura_valida(df), 2, coluna_alvo="alvo_abertura", com_retorno=False)`:
- D1: top 2 = A, B, acerto 0.5;
- D3: candidatos A, C, D; top 2 = C, D, acerto 1.0;
- taxa = **0.75**, `n_dias` = **2** (se D2 entrasse, daria 0.8333);
- AUC geral = **0.75**; AUC de D1 = 0.5 e de D3 = 1.0.

**Bootstrap:**
- `[0.4]*10` com L=5, B=200, semente 1 dá (0.4, 0.4);
- `[0.2, 0.4, 0.6, 0.8]` com L=4 (rotação inteira) dá (0.5, 0.5) com approx 1e-12;
- mesma semente dá o mesmo IC;
- `[]` dá (None, None).

**Robustez por ano:** acerto_top = 0.6 em 2025-12-29, 0.4 em 2025-12-30, 0.8 em 2026-01-02 e 0.4 em 2026-01-05. Esperado: 2025 com taxa 0.5 (n=2) e 2026 com 0.6 (n=2).

**Sensibilidade:** dias 2025-06-30 (0.2), 2025-07-01 (0.4) e 2026-06-30 (0.6). Esperado: corte "2025-06-30"; último ano com taxa 0.5 (n=2); anteriores com 0.2 (n=1).

**Calibração (bins=10):**
- p = [0.05, 0.12, 0.18, 0.52, 0.54, 0.56, 0.58, 0.95] e y = [0, 0, 1, 1, 0, 1, 1, 1]:
  - faixas [0, 1, 1, 5, 5, 5, 5, 9];
  - ECE = **0.2** (approx 1e-12) e Brier = **0.197975**;
  - com `ece_maximo=0.02` e `linhas_minimas=5`, `aprovada` = False.
- p = [0.25]*4 + [0.75]*4 e y = [1,0,0,0, 1,1,1,0]:
  - ECE = **0.0** e Brier = **0.1875**;
  - aprovada = True com `linhas_minimas=5` e False com `linhas_minimas=10`.

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_avaliacao.py`

---

### Fase 4: `processamento/experimento/modelos.py` (ajuste, contribuições, arquivo)

```python
def treinar_xgb(X: pd.DataFrame, y: pd.Series, hiper: dict, semente: int) -> xgb.XGBClassifier
    # XGBClassifier(**hiper, objective="binary:logistic", eval_metric="logloss", tree_method="hist",
    #               random_state=semente, n_jobs=1, missing=np.nan).fit(X.astype(float), y.astype(int))
def prob_xgb(modelo, X) -> np.ndarray                      # predict_proba(X.astype(float))[:, 1]
def margem_xgb(modelo, X) -> np.ndarray                    # get_booster().predict(DMatrix(X, missing=np.nan), output_margin=True)
def contribuicoes(modelo, X) -> pd.DataFrame               # pred_contribs=True; colunas list(X.columns) + ["vies"]; índice = X.index
def treinar_logistica(X, y, c: float, semente: int) -> Pipeline
    # make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
    #               StandardScaler(), LogisticRegression(C=c, max_iter=1000, random_state=semente))
    # keep_empty_features=True é obrigatório: sem ele, coluna toda vazia na dobra gera UserWarning (conferido)
def prob_logistica(pipe, X) -> np.ndarray
def score_volatilidade(preparado: pd.DataFrame) -> np.ndarray   # 1 − volatilidade_20d (rank; mais calma = maior); NaN -> 0.5
def sha256_arquivo(caminho) -> str                        # em blocos de 1 MiB
def nome_modelo(mes: str, modelo: str = "3") -> str       # "3" -> "xgb-AAAA-MM"; "1" -> "xgb-m1-AAAA-MM"
CHAVES_METADADOS = ("modelo", "versao_noticias", "colunas", "blocos", "hiperparametros", "semente", "periodo_treino",
    "n_linhas_treino", "dataset", "universo", "metricas_validacao", "calibracao", "provisorio", "aviso", "versoes", "gerado_em", "teste_final")
def salvar_modelo(modelo, metadados: dict, pasta: Path, nome: str) -> tuple[Path, Path]
    # falta chave -> ValueError; grava <nome>.json (modelo.save_model) e <nome>.meta.json
    # (UTF-8, indent 2, ensure_ascii=False, default=dataset._json_padrao)
def carregar_modelo(caminho_json: Path) -> tuple[xgb.XGBClassifier, dict]
```

**Caso 6, gabarito da regra da volatilidade** (dataset bruto passado por `preparacao.preparar`; copiar o ajudante `_dataset` de `tests/test_exp_preparacao.py`):

| ticker | volatilidade_20d (bruta) | rank | score | alvo | ret_t1 (ibov 0.0) |
|---|---|---|---|---|---|
| AAAA3 | 0.010 | 0 | 1.0 | 1 | 0.01 |
| BBBB3 | 0.030 | 0.75 | 0.25 | 0 | −0.02 |
| CCCC3 | 0.020 | 0.375 | 0.625 | 0 | −0.01 |
| DDDD3 | NaN | NaN | **0.5** | 1 | 0.03 |
| EEEE3 | 0.020 | 0.375 | 0.625 | 1 | 0.02 |
| FFFF3 | 0.050 | 1.0 | 0.0 | 0 | −0.03 |

- Ordem: AAAA3, CCCC3, EEEE3, DDDD3, BBBB3, FFFF3.
- Top 3 = [AAAA3, CCCC3, EEEE3], com acerto 2/3 e excesso 0.02/3.
- Top 5 = + [DDDD3, BBBB3], com acerto 0.6 e excesso 0.006 (via `avaliacao.resumo_diario`).

**Caso 8, parte 1: pred_contribs.** Dados sintéticos com `rng = default_rng(0)`, X de 2000×4 (`ret_1d`, `ret_5d`, `noticias_dia_tom` com NaN a cada 7 linhas, `beta` todo NaN), `y = (ret_1d + N(0, 0.3) > 0.5)`, hiperparâmetros com `n_estimators=50`. Conferir:
- o shape é (2000, 5) e a última coluna se chama `"vies"`;
- `np.allclose(contrib.sum(1), margem_xgb(...), atol=1e-4)`;
- `np.allclose(1/(1+exp(−margem)), prob_xgb(...), atol=1e-6)`.

**Caso 10: arquivo do modelo**
- Treinar duas vezes com a mesma semente dá `prob_xgb` idêntico (`np.array_equal`).
- `salvar_modelo(..., tmp_path, "xgb-2026-06")` cria `xgb-2026-06.json` e `xgb-2026-06.meta.json`.
- Relendo com `carregar_modelo`: previsões idênticas (`np.array_equal`), metadados iguais aos gravados depois de um vaivém em JSON (tuplas viram listas) e `colunas` na mesma ordem.
- Metadados sem a chave `"semente"` dão ValueError.
- `sha256_arquivo` de um arquivo com os bytes `b"abc"` = `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`.
- `sha256_arquivo` de `b"data,ticker,alvo\n2026-06-18,AAAA3,1\n"` = `3299a78cbf26ca7db4d569949fb37a48c530bda9e115520700648ecbbdb23220`.
- `nome_modelo("2026-06")` = "xgb-2026-06" e `nome_modelo("2026-06", "1")` = "xgb-m1-2026-06".

**Logística:** com o mesmo X (que tem coluna toda NaN), treina sem aviso nem erro (rodar com `warnings` virando erro), e as probabilidades ficam em (0, 1).

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_modelos.py`

---

### Fase 5: `processamento/experimento/previsao.py` (top do dia, motivos, chance, sombras)

```python
def efeito(contrib: float, limiar: float) -> str          # > limiar "ajudou"; < −limiar "atrapalhou"; senão "neutro" (borda = neutro)
def motivos(contrib: pd.Series, valores: pd.Series, qtd: int, limiar: float) -> list[dict]
    # ignora "vies"; ordena por |contrib| desc e depois o nome do fator asc; pega qtd
    # item = {"fator", "contribuicao", "valor" (do dataset BRUTO, antes do rank; None se NaN), "efeito"}
def chance(prob: float, liberar_chance: bool, calibracao_aprovada: bool) -> dict
    # exibir = liberar_chance and calibracao_aprovada
    # exibir:   {"valor": float(prob), "media": 0.5, "exibir": True,  "status": "ok"}
    # senão:    {"valor": None,        "media": 0.5, "exibir": False, "status": "calibracao_nao_conferida"}
def ordenar_top(df_dia, scores: np.ndarray, k: int) -> list[str]   # reusa avaliacao.ordenar_no_dia (score desc, ticker asc)
def top_do_dia(preparado_dia, bruto_dia, modelo, metadados, params) -> list[dict]
    # X = preparado_dia[metadados["colunas"]]; prob = modelos.prob_xgb; contrib = modelos.contribuicoes
    # k = params.topk[0]; item = {"posicao", "ticker", "chance": chance(...), "motivos": motivos(...)}
    # aprovada = metadados["calibracao"]["aprovada"]; os textos ("Notícias ... (3 notícias)") ficam para a etapa 7
def top_sombra_volatilidade(preparado_dia, k) -> list[str]     # modelos.score_volatilidade + ordenar_top
def top_sombra_modelo(preparado_dia, modelo, colunas, k) -> list[str]
```

**Caso 8, parte 2: top motivos.** Linha de contribuições: `ret_1d` 0.30, `ret_5d` −0.45, `volatilidade_20d` 0.005, `noticias_dia_tom` 0.30, `beta` −0.02, `vies` −0.1. Valores brutos: `ret_5d` −0.031, `noticias_dia_tom` 0.42, `ret_1d` 0.012, `beta` NaN, `volatilidade_20d` 0.018. Usar `limiar=0.01`.
- Com `qtd=3`: [ret_5d (−0.45, valor −0.031, "atrapalhou"), noticias_dia_tom (0.30, 0.42, "ajudou"), ret_1d (0.30, 0.012, "ajudou")]. O empate de módulo em 0.30 se resolve pelo nome: "noticias_dia_tom" < "ret_1d".
- Com `qtd=5`: acrescenta beta (−0.02, valor None, "atrapalhou") e volatilidade_20d (0.005, 0.018, "neutro").
- `efeito(0.01, 0.01)` dá "neutro" e `efeito(-0.0100001, 0.01)` dá "atrapalhou".

**Caso 9: a chance fica escondida**
- `chance(0.61, False, True)` e `chance(0.61, True, False)` dão `valor None`, `exibir False` e `status "calibracao_nao_conferida"`.
- `chance(0.61, True, True)` dá valor 0.61, `exibir True` e `status "ok"`.
- `top_do_dia` com os parâmetros reais (`liberar_chance: false`) e um modelo treinado nos dados sintéticos: todo `item["chance"]["valor"] is None`, e o `json.dumps(itens)` não contém a chave "prob".

**Desempate e sombras**
- `ordenar_top` com o D1 do caso 3, k=5, dá [AAAA3, BBBB3, CCCC3, DDDD3, EEEE3].
- `top_sombra_volatilidade` com o dia do caso 6, k=5, dá [AAAA3, CCCC3, EEEE3, DDDD3, BBBB3].
- `top_sombra_modelo` devolve k tickers distintos, na ordem de `prob_xgb` (desempate por ticker).

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_previsao.py`

---

### Fase 6a: núcleo de `processamento/experimento/treino.py`

```python
MODELOS_AVALIADOS = ("modelo_1", "modelo_3", "logistica", "volatilidade", "modelo_3_principais", "modelo_3_hora_real_noite")
class ErroDataset(Exception): ...
def localizar_datasets(pasta: Path, data: date | None) -> dict[str, Path | None]
    # "todas" é obrigatória (a de maior data, ou a de `data`); "principais" e "hora_real_noite" com a MESMA data, ou None
def ler_desenvolvimento(csv: Path, params) -> tuple[pd.DataFrame, dict]
    # confere o sha256 do CSV contra o .json ao lado (diferente -> ErroDataset); lê com dtype de texto;
    # LOGO EM SEGUIDA aplica validacao.periodo_desenvolvimento(teste_final_inicio, embargo) e aplica_inicio
    # ("cobertura" -> info["cobertura_inicio"]); as linhas do teste final nunca saem desta função
    # falta "alvo_abertura_valido" -> ErroDataset("regenere o dataset: python -m processamento.experimento.dataset --versao <v>")
def preparar_dev(df) -> tuple[pd.DataFrame, list[date]]   # (linhas_de_treino(preparar(df)), calendário = datas distintas de df)
def prever_walk_forward(prep, dobras, colunas, tipo, params, hiper=None) -> pd.DataFrame
    # tipo: "xgb" | "logistica" | "volatilidade"; para cada dobra: validacao.linhas_da_dobra -> ajusta no treino -> score no teste
    # saída: data, ticker, dobra, score, alvo, alvo_abertura, alvo_abertura_valido, ret_t1, ret_ibov_t1, dia_resultado
def auc_medio_wf(pred) -> float                          # avaliacao.auc_por_pregao(pred).mean()
def selecionar_configuracao(prep, dobras, params) -> tuple[dict, pd.DataFrame]
    # 1) modelo 1: blocos = (); para b em ("preco_contexto", "macro"): aceita se auc(com) − auc(sem) > ganho_minimo_bloco
    # 2) modelo 3 = colunas_do_modelo("3", blocos_preco); testa "noticias_contexto" com a mesma regra
    # 3) grade: produto cartesiano (ordem das chaves do yaml, valores na ordem dada) sobre params.xgboost, no modelo 3 final;
    #    escolhe o maior AUC médio; empate -> o primeiro; vale para TODOS os XGBoost
    # devolve {"blocos_preco", "noticias_contexto", "hiperparametros", "colunas_1", "colunas_3"} e a tabela de tentativas
def avaliar(pred, params, acaso: dict) -> dict          # monta o bloco "modelos.<nome>" do esquema abaixo
def calcular_acaso(pred_ref, params) -> dict            # faixa para cada k, no alvo e no alvo_abertura (dias válidos)
```
A faixa do acaso é **uma só** para todos os modelos, porque as linhas candidatas são as mesmas.

**`tests/fabrica_treino.py`:**
- `dataset_sintetico(inicio="2025-08-01", n_pregoes=130, n_tickers=12, semente=0)`. Colunas = `dataset.COLUNAS_DATASET`. Calendário de `fabrica_precos.pregoes_uteis`. Tickers `AAAA3`, `BBBB3`, ….
  - Variáveis brutas N(0, 1). `noticias_dia_qtd` ~ Poisson(1), com tom e extremo NaN quando qtd = 0.
  - `ret_ibov_t1` ~ N(0, 0.01) por dia; `ret_t1 = ibov + 0.004·ret_1d + N(0, 0.01)`; `alvo = float(ret_t1 > ret_ibov_t1)`.
  - `alvo_abertura` aleatório; `alvo_abertura_valido` = 0.0 a cada 3º dia e 1.0 nos outros; `dia_resultado` True com probabilidade 0.05.
  - No último dia, as 5 colunas de alvo ficam NaN. `universo` = "composicao_atual".
- `gravar_versoes(pasta, df, versoes=("todas", "principais", "hora_real_noite"))`. Usa `dataset.salvar_dataset` (reuso), com `info` = {versao_noticias, linhas, pregoes, cobertura_inicio = inicio, lidas, fora_versao, papel_vazio_fora, preparadas, descartadas_fora_da_janela}. Nas versões extras, perturbar só as colunas de notícias.
- `params_teste(**trocas)`: `dataclasses.replace(carregar_parametros_treino(), treino_minimo_meses=2, teste_final_inicio=date(2026,1,2), xgboost={…, "n_estimators": 20}, grade={"max_depth": (2,)}, acaso_sorteios=200, bootstrap_reamostragens=50, calibracao_linhas_minimas=100, **trocas)`.

**Teste do caso 6 (mesmas linhas):** nos dados sintéticos, `prever_walk_forward` com "xgb", "logistica" e "volatilidade` nas mesmas dobras produz o **mesmo conjunto** de pares (data, ticker). Esse conjunto é igual à união dos testes das dobras com alvo não nulo e não tem par repetido.

**Outros testes:**
- `selecionar_configuracao` roda duas vezes e dá resultado idêntico.
- `ler_desenvolvimento` devolve datas `max < 2026-01-01` (2026-01-01 é o embargo, porque os dias úteis sintéticos não têm feriado).
- sha256 alterado dá ErroDataset; CSV sem `alvo_abertura_valido` dá ErroDataset com "regenere".

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_nucleo.py`

### Esquema do `metricas.json` (contrato entre 6a, 6b e 6c)

```text
modo ("desenvolvimento"|"teste_final"), aviso_funcionamento (bool), gerado_em,
datasets: {todas|principais|hora_real_noite: {arquivo, sha256, linhas, cobertura_inicio, info_noticias:{...}} | null},
periodo: {inicio, fim, n_pregoes, n_linhas, n_tickers, universo, teste_final_inicio, teste_final_usado, embargo_pregoes},
dobras: [{numero, mes_teste, treino_inicio, treino_fim, n_pregoes_treino, n_pregoes_teste, n_linhas_treino, n_linhas_teste}],
selecao: {blocos_preco, noticias_contexto, hiperparametros, tentativas:[{etapa, descricao, auc_medio, aceito}]},
acaso: {"5":{media,p2_5,p97_5,excesso_media,excesso_p2_5,excesso_p97_5,n_sorteios,n_dias}, "3":{...},
        "abertura":{"5":{media,p2_5,p97_5,n_dias}, "3":{...}}},
modelos: {<nome>: {colunas, auc_geral, auc_medio_pregao, n_dias_auc,
   topk:{"5":{n_dias,taxa_acerto,ic_taxa:[a,b],excesso_medio,ic_excesso:[a,b],taxa_ultimos,excesso_ultimos,dif_top_ultimos,
              vs_acaso,fracao_acaso_maior_ou_igual}, "3":{...}},
   abertura:{n_dias_validos,n_dias_total,auc_geral,topk:{"5":{n_dias,taxa_acerto,vs_acaso},"3":{...}}},
   por_ano:[{ano,n_dias,taxa_acerto_5,excesso_5,taxa_acerto_3}], sensibilidade:{corte,ultimo_ano,anteriores}}},
comparacoes: [{a, b, metrica ("acerto_top5_dia"|"auc_dia"), media_dif, ic:[a,b], n_dias}],
   # pares: modelo_3 com (modelo_1, logistica, volatilidade); (modelo_3_principais, modelo_3_hora_real_noite) com modelo_3
veredito_modelo_3: {acaso: "acima|dentro|abaixo", supera_volatilidade: bool, supera_logistica: bool, texto},
modelo_3b: {n_linhas, n_dias, auc_modelo_3, auc_modelo_1, auc_modelo_3_fora, auc_modelo_1_fora},   # usa linhas_modelo_3b nas previsões
calibracao: {ece, brier, n, aprovada, chance_exibida, tabela},
exemplo_top: {data, top:[itens de previsao.top_do_dia], sombra_modelo_1, sombra_volatilidade},
modelo_salvo: {arquivo, metadados, arquivo_m1, metadados_m1} | null
```
Um modelo extra ausente vira `null`. O texto do veredito, quando o acaso dá "dentro", é "ainda não mostrou vantagem sobre o acaso". O "ganha" só vale se acaso = "acima" **e** o modelo superar a volatilidade **e** a logística na taxa do top 5.

---

### Fase 6b: `processamento/experimento/relatorio.py` (texto; função pura)

```python
def pct(x, casas: int = 1) -> str       # 0.4834 -> "48,3%"; casas=2: 0.0008 -> "0,08%"; -0.0028 -> "-0,28%"; None -> "n/d"
def gerar_relatorio(metricas: dict) -> str     # Markdown
```
Ordem das seções:
1. aviso;
2. dados, períodos e trava;
3. contagens de notícias (principais: `papel_vazio_fora` = "notícias sem julgamento da juíza, fora da versão"; hora real: lidas, sem hora real, hora real fora da noite, na noite);
4. dobras;
5. seleção (com a nota "métricas de desenvolvimento são otimistas: blocos e grade foram escolhidos nas mesmas dobras; o número honesto será o do teste final");
6. tabela do top 5 e do top 3 por modelo, com a faixa do acaso;
7. veredito;
8. diferenças pareadas;
9. modelo 3b;
10. alvo de abertura ("avaliado só em N de M dias: nos outros a abertura do IBOV é igual ao fechamento anterior, defeito da fonte");
11. robustez por ano e sensibilidade ("sem dados: histórico curto" se não houver anteriores);
12. calibração ("chance não exibida");
13. exemplo de top 5 com motivos e sombras;
14. modelo salvo;
15. rodapé "Não constitui recomendação de investimento."

**Aviso no topo**, sempre que `aviso_funcionamento` for true:
```
> **AVISO: TESTE DE FUNCIONAMENTO, NÃO É RESULTADO.**
> Gerado com cerca de 1 ano de histórico (o histórico completo ainda não chegou; ESPECIFICACAO 3.4).
> Nenhum número abaixo vale como conclusão do TCC: serve só para conferir que o pipeline roda de ponta a ponta.
> Período de teste final (a partir de {teste_final_inicio}): NÃO usado nem lido para escolher nada (trava fechada).
> Não constitui recomendação de investimento.
```
No modo `teste_final`, o título é "AVALIAÇÃO NO TESTE FINAL (uso único)", e o aviso de funcionamento continua se o período de desenvolvimento tiver menos de 3 anos.

**Testes**, com um dicionário mínimo montado à mão segundo o esquema:
- a primeira linha não vazia contém "TESTE DE FUNCIONAMENTO";
- o texto contém "2026-06-23" e "Não constitui recomendação de investimento.";
- sem `compre`, `oportunidade` nem `melhores ações` (sem distinguir maiúsculas);
- "recomendação" aparece uma vez só;
- com `vs_acaso="dentro"`, aparece "ainda não mostrou vantagem sobre o acaso";
- `pct(0.4834) == "48,3%"`, `pct(None) == "n/d"` e `pct(0.0008, 2) == "0,08%"`.

**Verificação:** `.venv/Scripts/python -m pytest -q tests/test_treino_relatorio.py`

---

### Fase 6c: `executar`, `main`, trava e gravação (em `treino.py`)

```python
class ErroTravaTesteFinal(Exception): ...
REGISTRO_TESTE_FINAL = fontes.RAIZ / "docs" / "teste_final_usado.json"
def conferir_trava(pedido: bool, liberado: bool, fim: date | None, registro: Path) -> None
    # pedido False -> nada (modo desenvolvimento);
    # fim None -> erro "teste final travado: treino.teste_final.fim vazio (fixado na etapa 8, véspera da produção)";
    # liberado False -> erro "teste final travado: treino.teste_final.liberado = false";
    # registro existe -> erro "o teste final já foi usado (ver <registro>); uso único"
def executar(pasta_datasets, pasta_saida, pasta_modelos, *, data=None, teste_final=False, params=None,
             registro=REGISTRO_TESTE_FINAL) -> Path    # devolve o caminho do relatório
def main(argv=None, params=None) -> int
```

**Modo desenvolvimento** (o padrão):
1. Lê os datasets com `ler_desenvolvimento` e monta as dobras com `dobras_walk_forward(cal, treino_minimo_meses, embargo)`.
2. Seleciona a configuração e prevê todos os `MODELOS_AVALIADOS`. Os extras usam a mesma configuração do modelo 3 no próprio dataset e conferem que o conjunto de pares (data, ticker) é igual ao de "todas".
3. Calcula o acaso, as métricas, as comparações, o 3b e a calibração (previsões do modelo 3).
4. O exemplo do top é o último dia da última dobra, com o modelo daquela dobra.
5. Treina o modelo 3 e o modelo 1 em **todas** as linhas de desenvolvimento e salva `xgb-<mes>` e `xgb-m1-<mes>`, com `mes = teste_final_inicio.strftime("%Y-%m")`. Metadados: `provisorio: true`, aviso "modelo provisório: treinado com ~1 ano; só teste de funcionamento", `teste_final: {inicio, usado: false}` e as versões das bibliotecas.
6. Grava em `pasta_saida/dev-<data do dataset>/` (sobrescreve): `relatorio.md`, `metricas.json` (sem arrays), `previsoes.csv` (data, ticker, modelo, dobra, score, alvos, ret, dia_resultado), `diario.csv` (data, modelo, k, colunas de `resumo_diario`) e `selecao.csv`.

**Modo teste final** (só se `conferir_trava(True, params.teste_final_liberado, params.teste_final_fim, registro)` passar):
1. Lê os metadados `xgb-<mes>.meta.json` e `xgb-m1-<mes>.meta.json` (se faltarem, erro "rode antes o treino de desenvolvimento"). A configuração (colunas e hiperparâmetros) fica **congelada** dali.
2. Lê o CSV, descarta logo na leitura as linhas com data > `fim` (teste ao vivo) e monta as dobras com `dobras_teste_final(cal, inicio, fim, embargo)`.
3. Avalia com as mesmas funções e grava em `pasta_saida/teste-final-<data>/`.
4. Cria o `registro`: {usado_em, teste_final_inicio, teste_final_fim, n_dias, sha256_dataset, configuracao, relatorio, resumo (taxa top 5 do modelo 3, faixa do acaso)}.

**CLI:** `--data AAAA-MM-DD`, `--pasta-datasets` (padrão `saida/experimento`), `--pasta-saida` (padrão `saida/experimento/treino`), `--pasta-modelos` (padrão `modelos`) e `--teste-final`. Códigos de saída:
- 0: ok;
- 2: dataset ausente, sha256 diferente ou "regenere" (as mensagens dizem o comando);
- 4: trava, sem gravar nada.

**Testes de pipeline (`test_treino_pipeline.py`, com fabrica_treino e `tmp_path`)**
1. **Arquivos:** `executar` cria relatorio.md, metricas.json, previsoes.csv, diario.csv e selecao.csv, além de `xgb-2026-01.json`, `.meta.json`, `xgb-m1-2026-01.json` e `.meta.json`. O relatório começa com "TESTE DE FUNCIONAMENTO".
2. **Nada do teste final:** em previsoes.csv, a maior data é 2025-12-31 (nada ≥ 2026-01-01).
3. **Mesmas linhas (caso 6, ponta a ponta):** os conjuntos (data, ticker) são iguais entre modelo_1, modelo_3, logistica e volatilidade.
4. **Reprodutível:** duas execuções dão `previsoes.csv` byte a byte iguais e `metricas.json` igual, ignorando `gerado_em`.
5. **Veneno (a trava de verdade):** nas linhas com data ≥ 2026-01-01 (embargo + teste final), multiplicar por −1 as variáveis brutas e de notícias, trocar `alvo` por `1 − alvo` e pôr `ret_t1 = 99`. As previsões e o `metricas.json` saem iguais aos do original, ignorando `gerado_em` e `datasets.*.sha256`/`arquivo`.
6. **Sem banco:** com `monkeypatch` fazendo `fontes.criar_engine` e `fontes.executar_leitura` levantarem erro, `main([...pastas tmp...], params=params_teste())` devolve 0.
7. **Extras ausentes:** sem os CSV de principais e hora_real_noite, roda igual; `metricas["datasets"]["principais"] is None` e o relatório diz "não encontrado".
8. **CSV inválido:** sem a coluna nova, `main` devolve 2 e mostra "regenere"; sha256 alterado também devolve 2.

**Testes da trava (`test_treino_trava.py`)**
- `conferir_trava(pedido, liberado, fim, registro)`: (False, False, None) passa; (True, True, None) dá erro com "fim vazio"; (True, False, 2026-01-20) dá erro com "liberado"; (True, True, 2026-01-20) sem registro passa; (True, True, 2026-01-20) com registro dá erro "já foi usado".
- `main(["--teste-final", ...])` com `liberado=False` devolve 4; com `liberado=True` e `fim=None` também devolve 4; nos dois casos, a pasta de saída e o registro **não** são criados.
- Com `liberado=True` e `fim=2026-01-20`, sem rodar antes o modo desenvolvimento, dá erro "rode antes o treino de desenvolvimento".
- Com `liberado=True` e `fim=2026-01-20` depois de um modo desenvolvimento:
  - aparece `teste-final-<data>/relatorio.md` com "TESTE FINAL";
  - o registro existe e tem as chaves listadas acima, com `teste_final_fim = "2026-01-20"`;
  - as previsões são todas de data entre 2026-01-02 e 2026-01-20;
  - **veneno do teste ao vivo:** envenenar (como no teste 5 do pipeline) as linhas com data > 2026-01-20 não muda nada nas previsões nem no `metricas.json`;
  - em cada dobra, o treino é < `teste[0]` e não contém o pregão imediatamente anterior;
  - uma 2ª chamada dá `ErroTravaTesteFinal`.
- Com `liberado=True` **sem** `--teste-final`: roda o modo desenvolvimento normal e não cria registro.

**Verificação:** `.venv/Scripts/python -m pytest -q` (o projeto inteiro).

---

## Verificação final e critério de pronto
1. `.venv/Scripts/python -m pytest -q` sem falhas, com os 753 testes antigos e os novos.
2. O usuário regenera os 3 datasets (comandos da Fase 0).
3. Pode ser rodado pelo `executor`, porque não acessa o banco: `python -m processamento.experimento.treino` sai com código 0 e cria `saida/experimento/treino/dev-2026-10-21/relatorio.md` (aviso no topo) e `modelos/xgb-2026-06.json` + `.meta.json`.
4. Conferência: `python -c "import pandas as pd; d=pd.read_csv('saida/experimento/treino/dev-2026-10-21/previsoes.csv', parse_dates=['data']); print(d.data.max())"` mostra ≤ 2026-06-19.
5. `python -m processamento.experimento.treino --teste-final` sai com código 4 (`fim` vazio e `liberado: false`).

Com os dados reais e os parâmetros propostos, o período de desenvolvimento vai de 2025-08-01 a 2026-06-19 (22/06 é o embargo, o mesmo da v1). São 8 dobras de teste, de 2025-11 a 2026-06.

---

## Decisões (APROVADAS em 23/10/2026: todas as recomendações, com o ajuste na 1)
1. **Período do teste final (ajustado pelo usuário).** De `"2026-06-23"` (o período que a v1 reservou e **nunca usou**, HISTORICO 12.4) até a **véspera da entrada da rotina diária em produção** (data fixada na etapa 8), em `treino.teste_final.fim`; hoje vazio = trava ativa. Depois do fim, os dados formam o **teste ao vivo**, um segundo teste independente (registrado na 7.5).
2. **Trava.** Exigir as quatro coisas: `fim` preenchido, yaml `liberado: true`, a opção `--teste-final` e o registro de uso único em `docs/teste_final_usado.json` (versionado, para auditoria).
3. **Como avaliar no teste final.** Recomendo walk-forward mensal continuando dentro do período, com a configuração congelada no metadado do desenvolvimento, igual ao retreino da 7.7. Alternativa: um único modelo treinado em todo o desenvolvimento.
4. **Linhas do experimento.** Recomendo, para todos os modelos, só as linhas a partir da cobertura de notícias (2025-08-01), para comparar o modelo 1 com o 3 nas mesmas linhas. Alternativa: o modelo 1 com todo o histórico desde 2024-07.
5. **Treino mínimo.** Recomendo 3 meses (8 dobras). Alternativa: 1 ou 2 meses (mais dobras, cada uma mais fraca).
6. **Seleção dos blocos.**
   - Recomendação: os blocos de preço são escolhidos no modelo 1 e herdados pelo 3 (o 3 continua sendo o 1 + notícias). O `noticias_contexto` é testado só no 3.
   - Critério: AUC médio por pregão, com ganho mínimo de 0,005, no espírito do "melhorar de verdade" do HISTORICO.
   - Alternativa: ganho > 0 (leitura literal) ou o acerto do top 5 como critério (mais ruidoso).
7. **Grade.** Recomendo max_depth {2, 3} × min_child_weight {50, 200}, escolhida no modelo 3 e aplicada a todos os XGBoost. Alternativas: uma grade por modelo, ou só o ponto de partida enquanto for teste de funcionamento.
8. **Desempate.** Recomendo score decrescente e depois ticker crescente; "últimos k" são os k finais dessa mesma ordem.
9. **Faixa do acaso.** Recomendo os percentis 2,5 e 97,5 da taxa **do período** de cada um dos 10 mil escolhedores (glossário: "onde caem 95% dos escolhedores"). Alternativa: a faixa da taxa diária (bem mais larga, sem sentido para comparar médias).
10. **Volatilidade vazia na regra simples.** Recomendo score neutro 0,5. Alternativa: deixar a ação de fora do dia (mas aí as linhas deixam de ser as mesmas dos outros modelos).
11. **Logística.** Recomendo imputar a mediana com um indicador de vazio, padronizar, usar C=1 e as mesmas colunas do modelo 3.
12. **Modelo 3b.** Recomendo avaliar as previsões do modelo 3 (treinado em todas as linhas) só nos dias de resultado: AUC do 3 contra o do 1, dentro e fora desses dias. Alternativa: treinar só nas ~500 linhas de resultado com `linhas_modelo_3b` (com `min_child_weight=50` o modelo quase não aprende).
13. **`alvo_abertura`.** Recomendo uma coluna nova `alvo_abertura_valido` no dataset e avaliar as mesmas previsões (treinadas no alvo principal) só nos dias válidos. Alternativa: um modelo separado para o alvo de abertura.
14. **Teste "hora real na noite".** Recomendo uma versão nova do dataset, `hora_real_noite`. Aviso: a `mudanca_tom` fica quase toda vazia (exige 5 notícias em 30 pregões); tratar como exploratório.
15. **Bootstrap.** Recomendo o circular em blocos de 5 pregões, com 2000 reamostragens. IC para a taxa e o excesso do top 5 de cada modelo e para as diferenças diárias pareadas.
16. **Calibração e chance.**
    - Critério: ECE com 10 faixas iguais; aprovada se ECE ≤ 0,02 e houver ≥ 5000 linhas.
    - Exibir a chance só se estiver aprovada **e** `liberar_chance: true` (decisão manual).
    - Na exportação, recomendo `valor: null` com `status: "calibracao_nao_conferida"`. Alternativa: mandar o valor com `exibir: false`, como no exemplo da 8.3.
17. **Modelos salvos.**
    - Recomendo `xgb-AAAA-MM` (modelo 3) e `xgb-m1-AAAA-MM` (modelo 1, para o top 5 sombra), com AAAA-MM = mês de uso; no modo desenvolvimento, 2026-06.
    - Treinados só com o desenvolvimento, marcados como provisórios. O retreino com todo o histórico fica para depois da liberação (etapa 8).
18. **Semente.** Recomendo uma semente única, `20261023`. Alternativa: 5 sementes com média, como na v1 (cinco vezes mais tempo).
19. **Pasta das saídas.** Recomendo `saida/experimento/treino/dev-<data do dataset>/` (fora do git).

## Pontos em que o código ou o dataset não batem com a especificação (listados, não resolvidos)
1. O dataset atual não permite avaliar o `alvo_abertura` só nos dias válidos (seção 10): falta a informação da abertura do IBOV. A Fase 0a resolve, mas exige regerar o CSV.
2. Não existe a versão de dataset do teste extra "notícia depois do fechamento" (7.5). Hoje `inicio_janela="fechamento"` ainda deixa as notícias "só data" na noite (23:59:59). A Fase 0b cria a versão `hora_real_noite`.
3. A seção 7.7 diz `modelos/xgb-AAAA-MM.json`, mas o exemplo da 8.3 usa `"modelo_versao": "xgb-2026-11-01"`, com dia. **Usuário (23/10/2026): seguir a 7.7; o exemplo da 8.3 fica para a etapa 7.**
4. A seção 2.1 ainda citava "modelos 1/2/3/3b" no `treino.py`; o modelo 2 saiu (7.4, N2-A). **Corrigido na especificação em 23/10/2026.**
5. O exemplo de motivo da 8.3 (`"tom_noticias_noite"`, "Notícias da noite …") é anterior à N2-A: o fator agora é `noticias_dia_tom`, na janela do dia e da noite. **Fica para a etapa 7** (idem o `chance.valor` do exemplo, que pela decisão 16 sai `null` até a calibração ser conferida).
6. A seção 7.6 não define desempate nem a definição exata da "faixa de 95%": viraram as decisões 8 e 9.
7. Na versão `hora_real_noite`, a base da `mudanca_tom` (E7: "todas as notícias da empresa") passa a ter só as notícias de hora real da noite (decisão 14).
8. Informação: os meses de jan a jun/2026 já foram olhados na avaliação da v1 (HISTORICO 4.3). Só o período a partir de 23/06/2026 está intocado, e isso sustenta a decisão 1.

## Arquivos
- A alterar: `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\experimento\alvo.py`, `...\experimento\preparacao.py`, `...\experimento\noticias.py`, `...\experimento\dataset.py`, `...\experimento\parametros.py`, `...\processamento\calendario.py`, `...\processamento\config\parametros.yaml`, `...\tests\test_exp_alvo.py`, `...\tests\test_exp_noticias.py`, `...\tests\test_exp_dataset.py`.
- A criar em `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\processamento\experimento\`: `validacao.py`, `avaliacao.py`, `modelos.py`, `previsao.py`, `relatorio.py`, `treino.py`.
- A criar em `c:\Users\danie\Desktop\TCC\Arquivos\processamento-tcc\tests\`: `fabrica_treino.py`, `test_treino_parametros.py`, `test_treino_validacao.py`, `test_treino_avaliacao.py`, `test_treino_modelos.py`, `test_treino_previsao.py`, `test_treino_nucleo.py`, `test_treino_relatorio.py`, `test_treino_pipeline.py`, `test_treino_trava.py`.
- Saídas geradas (fora do git): `...\saida\experimento\treino\dev-<data>\`, `...\modelos\xgb-2026-06.json` com o `.meta.json`. Versionado: `...\docs\teste_final_usado.json`, criado só quando o teste final for usado.