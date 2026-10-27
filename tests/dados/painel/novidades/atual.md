# Diagnóstico do banco da coleta (só leitura)

- Gerado em: 2026-10-27 10:44 (America/Sao_Paulo)
- Banco: banco_teste

## Divergências × especificação

Nenhuma divergência encontrada.

## 3. Resumo das tabelas

### Período e entidades

| tabela | linhas | inicio | fim | entidades | coluna_entidade |
|---|---|---|---|---|---|
| v1-precos | 143686 | 2019-12-30 | 2026-10-27 | 89 | ticker |
| v1-balancos | 2694 | 2021-03-31 | 2026-09-30 | 85 | cnpj |
| v1-indices | 5128 | 2021-01-01 | 2026-10-26 | 5 | indice |

## 10. Quantidade de ações suspeita

- quantidade de ações suspeita (P/VP < 0,05; v1-acoes_emitidas provavelmente em milhares) em 1 empresas em 2026-10-26: valor de mercado, P/L, P/VP e payout = indisponivel (seção 6)

### Empresas com quantidade de ações suspeita

| tickers | cnpj | data_referencia | acoes | pvp |
|---|---|---|---|---|
| HAPV3 | 05197443000138 | 2026-06-30 | 502630884 | 0.0416 |

## 11. Retornos diários suspeitos

- 2 retornos diários suspeitos em 2 tickers (fechamento_ajustado contra o último pregão com preço, abaixo de -75% ou acima de 100%): saem das séries e das medianas do setor; o preço não é corrigido (seção 6)

### Retornos diários suspeitos

| ticker | data | aj_anterior | aj | retorno_aj | retorno_fech |
|---|---|---|---|---|---|
| PCAR3 | 2021-03-01 | 10.2961 | 21.857 | 1.1228 | 1.1228 |
| UGPA3 | 2021-06-28 | 7.0026 | 15.3592 | 1.1933 | 1.1933 |

## 12. Lacunas nas séries de preços e índices

- nenhuma lacuna de mais de 5 pregões em v1-precos (fechamento_ajustado, só dentro do período com preço de cada ticker)
- 3 lacunas em v1-indices (IDIV, SMLL e IFIX: mais de 5 pregões, inclusive no fim)

### Lacunas em v1-indices

| serie | inicio | fim | tamanho | unidade |
|---|---|---|---|---|
| IDIV | 2025-01-02 | 2025-12-30 | 250 | pregões |
| IFIX | 2025-01-02 | 2025-12-30 | 250 | pregões |
| SMLL | 2025-01-02 | 2025-12-30 | 250 | pregões |

## 15. Histórico novo: composição, corrigir_horas e cobertura do experimento

- Cobertura do experimento (universo com a composição, motivo ok): 117505 linhas em 1699 pregões, de 2019-12-30 a 2026-10-26.
