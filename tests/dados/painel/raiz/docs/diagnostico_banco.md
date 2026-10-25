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
