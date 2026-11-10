# Plano da rodada 5 (aprovado em 09/11/2026)

Feito para continuar num chat novo. A rodada 5 do protocolo e da busca passa a ser a **oficial** (D5; `docs/protocolo_variaveis.md`, seção 8, nota da D5 e bloco de 09/11/2026). Segue o mesmo caminho da rodada 3.

**Exploratório:** `treino.modelo_oficial` é false. Não constitui recomendação de investimento.

## 1. Situação de partida

| Item | Valor |
|---|---|
| Rodada oficial até agora | 3 (reproduzida na 4): só o bloco A; vence a referência, XGBoost do ponto de partida (`docs/configuracao_final_rodada_003.json`) |
| Dataset congelado da rodada 3 | `dataset-todas-2026-11-06.csv`, sha256 `c954b437c55e41f20a84e91a647964cc33a1c3cf4bb60df474f3f560c81851aa`; cópia em `C:\Users\danie\Desktop\TCC\Arquivos\copias_congeladas\dataset_v7_rodada_003\` e no Google Drive |
| Por que a rodada 5 | Medida de 09/11/2026 (`docs/medida_dados_novos_2026-11-09.md`): 51,4% de linhas mudadas (44,9% com a regra refinada); notícias 37,0%; preço e bloco A 17,4%. A D7 foi aceita (pregão de 20/11/2020 nas janelas de 252 pregões e ruído do float32 no `salto_abertura`) |
| Produção | `treino.familia_producao: "xgb"`; modelos `modelos/xgb-2026-06*` da rodada 3, provisórios |
| `versao_preparacao` | 7 (sem mudança: só os dados mudaram) |
| Lista manual de quantidade suspeita | Vazia (a coleta corrigiu a RAIZ4) |
| Hashes das regras (não podem mudar) | `sha_regras` do protocolo `e275d3d6e8f1…`; da busca `dd967e28c1eb…` |
| Teste final | **Trancado**: `fim` vazio, `liberado: false`; exige a medida de dados novos do dia (`treino.conferir_medida_dados_novos`) |

## 2. Regras para todos os passos

- Não fazer commits (o usuário faz).
- Não ler, editar nem executar nada em `extracao-dados-tcc-main/`.
- Banco só leitura, e só pelos comandos do projeto.
- Não mudar as seções 3 a 6 de `docs/protocolo_variaveis.md`, que entram nos hashes. A seção 8 é registro.
- Até o fim da reprodução (passo 6a), não mexer em `processamento/experimento/treino.py`, `modelos.py`, no bloco `treino` do `parametros.yaml` nem nos demais arquivos de `ARQUIVOS_CODIGO`. Eles entram em `sha_codigo` e `sha_parametros`.
- Python: `.venv/Scripts/python.exe`. Prefixar os comandos longos com `PYTHONIOENCODING=utf-8`, para evitar erro de acentuação no Windows.
- Comandos longos (protocolo, busca, reprodução, sensibilidade, treino) rodam em segundo plano. Gravar a saída em arquivo e esperar terminar, sem acompanhar o progresso.
- Gravar as tabelas em arquivo e trazer só o resumo ao usuário.
- Testes: só os afetados, com `-q`, durante o trabalho. O `pytest -q` completo fica só no passo 10.

## 3. Passos, paradas e critérios

| # | Passo | Tempo | Para quando |
|---|---|---|---|
| 1 | Gerar as 3 versões do dataset | ~6 min | Se o dataset não for gerado, ou se a `versao_preparacao` não for 7 |
| 2 | Conferência e medida formal | ~15 min | **PARADA 1, sempre** |
| 3 | Protocolo (rodada 5) | ~45 min | Os blocos aprovados não forem **só o A**, ou o controle for aprovado (rodada inválida) |
| 4 | Busca (rodada 5) | ~25 min | O vencedor não for a **referência** (XGBoost do ponto de partida) |
| 5 | Registro na seção 8, antes da sensibilidade | ~5 min | |
| 6a | Reprodução (rodada 6) | ~70 min | `reproduziu` não for true no protocolo ou na busca |
| 6b | Sensibilidade (rodada 5), em paralelo com a 6a | ~20 min | **PARADA 2, sempre** (depois da 6a e da 6b) |
| 7 | Arquivar os modelos e treinar | ~10 min | Alguma métrica difere da busca 005 em 1e-12 ou mais. **PARADA 3, sempre** |
| 8 | Produção | — | O vencedor mudou (então o plano é outro) |
| 9 | Cópia congelada (D6) | ~2 min | |
| 10 | Documentos e verificação final | ~20 min | **PARADA 4, sempre** (antes de qualquer rotina real) |

São cerca de 3h30 de máquina, quase tudo em segundo plano.

### Passo 1: dataset (em 10/11, depois do daily das 8h)

**Não usar a data 2026-11-06.** O arquivo novo sobrescreveria o `c954…` em `saida/experimento/`, e o registro das rodadas 3 e 4 aponta para esse nome. Gerar sem `--ate`, para que o último pregão seja 09/11:

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.dataset --versao todas
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.dataset --versao principais
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.dataset --versao hora_real_noite
```

Conferir que os três saíram com a mesma data, `dataset-*-2026-11-09.csv`. Se a data for outra (por exemplo, sem o pregão de 09/11), usar a data que saiu em todos os passos seguintes, no lugar de `2026-11-09`.

### Passo 2: conferência → PARADA 1

1. Gerar `docs/conferencia_rodada_005.md` no formato de `docs/conferencia_rodada_003.md`, com:
   - identificação e sha256 das 3 versões;
   - linhas por ano;
   - notícias por ano e por origem;
   - % de pares (pregão × ação) com notícia;
   - por origem, % de linhas com notícia;
   - contagens do JSON do dataset contra o `c954…`;
   - linhas que entram ou saem;
   - colunas que mudam e a causa.
   Só o desenvolvimento (2021-01-01 a 22/06/2026); as linhas desde 23/06/2026 só são contadas.
2. Fazer a medida formal com a regra refinada (`rank E bruto`):
   ```
   PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.medida_dados_novos --congelado-csv C:/Users/danie/Desktop/TCC/Arquivos/copias_congeladas/dataset_v7_rodada_003/dataset-todas-2026-11-06.csv --novo-csv saida/experimento/dataset-todas-2026-11-09.csv --congelado docs/protocolo_congelado_rodada_003.json --data 2026-11-10
   ```
3. Conferir a D7 sobre o dataset definitivo. A mudança de preço deve ser a mesma da medida de 09/11: `beta` e `mom_12_1` em 2021, e o ruído no `salto_abertura`. **Se aparecer uma causa nova de mudança de preço ou de alvo, parar e explicar.**
4. **PARADA 1:** trazer o resumo ao usuário (linhas por ano, cobertura de notícias, % com notícia, fração da medida por grupo e por ano, diferenças contra a rodada 3).

### Passo 3: protocolo

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.protocolo_execucao --data 2026-11-09 --motivo "Rodada 5 oficial (D5, medida de 09/11/2026): dataset v7 de 2026-11-09; conferencia em docs/conferencia_rodada_005.md"
```

Antes de rodar, conferir que o `sha_regras` continua `e275d3d6e8f1…` (`protocolo_registro.sha_regras`). Se não for, parar.

**Critério de parada:** se os blocos adotados não forem só o A, ou se a rodada sair inválida, parar e mostrar a comparação com as rodadas 1 e 3. Se forem só o A, seguir para o passo 4.

### Passo 4: busca

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.busca_execucao --data 2026-11-09 --congelado docs/protocolo_congelado_rodada_005.json --motivo "Rodada 5 oficial: busca com o conjunto congelado da rodada 5 do protocolo; conferencia em docs/conferencia_rodada_005.md"
```

**Critério de parada:** se o vencedor não for `referencia`, parar e mostrar a comparação com as rodadas 1 e 3; nesse caso o plano de produção é outro. Se for, gravar `docs/comparacao_rodadas_003_005.md`, com critérios por bloco, candidatos da busca, AUC dos modelos 3 e 1 e ganho das notícias, e seguir.

### Passo 5: registro na seção 8, antes da sensibilidade

Inserir na seção 8, antes do checklist, a subseção "Rodada 5", com:
- o resultado do protocolo e da busca;
- o desenho da sensibilidade: casos a–d iguais aos das rodadas 1 e 3; família XGBoost com os hiperparâmetros da configuração 005; colunas de `docs/protocolo_congelado_rodada_005.json`; datasets de 2026-11-09 com os sha das 3 versões; fora do `protocolo_tentativas.jsonl`; IC sem ajuste.

Não mexer no título nem na tabela do checklist (o painel lê os dois). Conferir os hashes das regras e rodar `pytest -q tests/test_painel_aba_experimento.py`.

### Passo 6a: reprodução (em segundo plano)

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.protocolo_execucao --data 2026-11-09 --motivo "Reproducao da rodada 5 (mesmas entradas)"
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.busca_execucao --data 2026-11-09 --congelado docs/protocolo_congelado_rodada_005.json --motivo "Reproducao da rodada 5 (mesmas entradas)"
```

**Critério de parada:** no `docs/protocolo_tentativas.jsonl`, o protocolo e a busca da rodada 6 precisam ter `repete_rodada: 5` e `reproduziu: true`, com o mesmo `sha_resultado`. Se não tiverem, parar.

### Passo 6b: sensibilidade (em paralelo com a 6a) → PARADA 2

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.sensibilidade --data 2026-11-09 --rodada 5
```

Conferência: o AUC médio do modelo 1 no caso (b), todas as linhas, tem de ser igual ao `final.modelos.modelo_1.auc_medio_pregao` de `docs/busca_rodada_005.json`. Gravar `docs/comparacao_sensibilidade_003_005.md`.

**PARADA 2:** trazer ao usuário a reprodução, a sensibilidade e a comparação com a rodada 3.

### Passo 7: arquivar e treinar → PARADA 3

1. Criar `modelos/antigos/rodada_003/` e **copiar** para lá os quatro `modelos/xgb-2026-06*` e `xgb-m1-2026-06*` atuais. Copiar, não mover: o treino sobrescreve os arquivos, e assim nunca há momento sem modelo. Usar uma pasta própria para não colidir com os de 24/10, que já estão em `modelos/antigos/`.
2. Treinar:
   ```
   PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m processamento.experimento.treino --data 2026-11-09 --configuracao docs/configuracao_final_rodada_005.json
   ```
3. Conferir, com diferença abaixo de 1e-12, o `saida/experimento/treino/dev-2026-11-09/metricas.json` contra o `final` de `docs/busca_rodada_005.json`:
   - `auc_medio_pregao` do modelo 3, do modelo 1, da logística e da volatilidade;
   - `auc_geral` do modelo 3;
   - top 5 do modelo 3 e do modelo 1;
   - `calibracao.ece`.
   O script de referência é o da rodada 3, `conferir_treino_r3.py`; adaptar caminhos e nomes.
4. Conferir os metadados dos dois modelos:
   - `familia` `xgb`, `versao_preparacao` 7, `provisorio: true`;
   - `dataset.sha256` igual ao do novo `todas`;
   - `configuracao.arquivo` igual a `configuracao_final_rodada_005.json`, com o sha do arquivo;
   - `rodadas_de_origem` `{busca: 5, protocolo: 5}`.
5. **PARADA 3:** trazer as métricas, os metadados, o veredito (o texto mostra top 5 e AUC por pregão contra cada referência) e o exemplo de top 5.

### Passo 8: produção

Sem mudança de código se o vencedor continuar sendo o XGBoost:
- o yaml já está em `xgb`;
- a trava do teste final lê o sha do dataset nos metadados dos modelos novos;
- o painel passa a mostrar "busca rodada 005 (reproduzida na 006)".

Não rodar rotina real.

### Passo 9: cópia congelada (D6)

1. Criar `C:\Users\danie\Desktop\TCC\Arquivos\copias_congeladas\dataset_v7_rodada_005\` com as 3 versões de 2026-11-09, os `.json` e um `SHA256SUMS.txt` (o sha das cópias tem de bater com o dos originais).
2. Trazer ao usuário o caminho e o sha256 do `todas`.
3. A D6 volta a `pendente` no checklist até o usuário confirmar a cópia no Google Drive.

### Passo 10: documentos e verificação → PARADA 4

1. `docs/protocolo_variaveis.md`, seção 8:
   - parágrafo "Implementação (data)" da rodada 5;
   - a nota da D5 passa a dizer "congelado oficial hoje = sha novo";
   - D6 com o sha novo e os dois locais, assim que o usuário confirmar.
2. `ESPECIFICACAO.md`:
   - §7.4 aponta a configuração para `docs/configuracao_final_rodada_005.json`;
   - bloco novo "Acréscimo de 10/11/2026 (resultado da rodada 5)": dataset, protocolo, busca, comparação do TCC, modelos.
3. `CLAUDE.md`, pegadinha 19: rodada 5 oficial (reproduzida na 6), sha do dataset novo, configuração 005.
4. Testes que leem os arquivos reais e mudam com o registro: a lista de rodadas e o checklist em `tests/test_painel_aba_experimento.py`. Atualizar só as expectativas, nunca o código.
5. Verificação: conferir os hashes das regras; depois `pytest -q` completo pelo executor (~6 a 13 min).
6. **PARADA 4:** resumo final ao usuário. Rotina real só por decisão dele.

## 4. Riscos

- Os números da rodada 3 deixam de ser os oficiais. Os modelos de produção mudam no passo 7; os da rodada 3 ficam em `modelos/antigos/rodada_003/`.
- Se o vencedor mudar no passo 4, os passos 7 e 8 viram um plano novo, como aconteceu com a rodada 3.
- Se a coleta entregar dados novos entre os passos 1 e 7, o desenvolvimento já medido não é afetado. Antes do teste final, a trava exige a medida do dia contra o congelado dos modelos.
- Se o `sha_regras` ou o `sha_parametros` mudarem antes da reprodução, ela deixa de ser reconhecida como repetição. Nesse caso, parar.
