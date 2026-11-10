# Auditoria D9: retornos depois de 23/06/2026 (universo do modelo)

Registrado em 10/11/2026, antes do teste final (D9; `docs/protocolo_variaveis.md`, seção 8). Só retornos e eventos, sem abrir resultado de modelo. Leitura do banco só pelas funções do projeto (sessão READ ONLY); do dataset `9f520c5fa7e9…` só (data, ticker). Exploratório; não constitui recomendação de investimento.

## 0. Conclusão

- **Nenhum evento novo nas ações do universo** entre 23/06 e 10/11/2026: nenhum retorno fora dos limites de suspeito [−75%, +100%], nenhum desdobramento, bonificação ou grupamento em `v1-eventos_acoes`, nenhum preço parado.
- Os retornos grandes (seção 1) são movimentos de mercado com o IBOV junto (02/09 +3,1%, 05/10 +7,7%, 26/10 −13,9%), sem reversão no pregão seguinte, e com o retorno ajustado igual ao sem ajuste (não há provento nem evento no dia). HAPV3 em 13/08 (−33%, IBOV −0,2%) é movimento da própria ação, com o preço sem ajuste igual e sem provento nem evento; a queda de 26/10 (−55%) já está citada na especificação (seção 6, "Quantidade de ações suspeita").
- **Observação, não evento (seção 5):** em 5 de 72 pares (ticker, `data_com`) o ajuste do `fechamento_ajustado` no pregão ex não corresponde ao provento de `v1-proventos` (fração 0,77 a 3,0; padrão = 1): BBAS3 01/09, BPAC11 10/08, CMIG4 23/06 e 22/09, ENGI11 11/08. O efeito no retorno do dia é de 0,2 a 1,0 ponto percentual, dentro do ruído diário; é o mesmo tipo de divergência da RAIZ4 no desenvolvimento (`docs/conferencia_rodada_005.md`, seção 6). Fica registrado como limitação, sem nova versão.


- Universo: 73 tickers com linha no dataset `9f520c5fa7e9…` a partir de 23/06/2026 (2026-06-23 a 2026-11-09; 6944 linhas). Retornos até 2026-11-10 (o alvo de 09/11).
- Colunas de preço lidas: ['abertura', 'maxima', 'minima', 'fechamento', 'fechamento_ajustado', 'volume']

## 1. Retornos fora dos limites [−75%, +100%] ou com |retorno| > 15%, só dias no universo (t ou t+1 do modelo)

| ticker | data | ret_aj | ret_fech | ret_ibov | tipo |
|---|---|---|---|---|---|
| HAPV3 | 2026-08-13 | -0.3309 | -0.3309 | -0.00233 | |ret| > 15% |
| MGLU3 | 2026-09-02 | 0.16883 | 0.16883 | 0.0305 | |ret| > 15% |
| VAMO3 | 2026-09-02 | 0.16107 | 0.16107 | 0.0305 | |ret| > 15% |
| ASAI3 | 2026-10-05 | 0.16413 | 0.16413 | 0.07702 | |ret| > 15% |
| B3SA3 | 2026-10-05 | 0.22632 | 0.22632 | 0.07702 | |ret| > 15% |
| BBDC3 | 2026-10-05 | 0.15033 | 0.15033 | 0.07702 | |ret| > 15% |
| BPAC11 | 2026-10-05 | 0.22523 | 0.22523 | 0.07702 | |ret| > 15% |
| CSAN3 | 2026-10-05 | 0.23786 | 0.23786 | 0.07702 | |ret| > 15% |
| CYRE3 | 2026-10-05 | 0.18399 | 0.18399 | 0.07702 | |ret| > 15% |
| LREN3 | 2026-10-05 | 0.15391 | 0.15391 | 0.07702 | |ret| > 15% |
| MGLU3 | 2026-10-05 | 0.24179 | 0.24179 | 0.07702 | |ret| > 15% |
| RENT3 | 2026-10-05 | 0.20685 | 0.20685 | 0.07702 | |ret| > 15% |
| VAMO3 | 2026-10-05 | 0.21308 | 0.21308 | 0.07702 | |ret| > 15% |
| MGLU3 | 2026-10-09 | 0.1922 | 0.1922 | 0.01381 | |ret| > 15% |
| MRVE3 | 2026-10-09 | 0.21617 | 0.21617 | 0.01381 | |ret| > 15% |
| ALOS3 | 2026-10-26 | -0.2547 | -0.2547 | -0.13885 | |ret| > 15% |
| ASAI3 | 2026-10-26 | -0.42971 | -0.42971 | -0.13885 | |ret| > 15% |
| AURE3 | 2026-10-26 | -0.29396 | -0.29396 | -0.13885 | |ret| > 15% |
| AZZA3 | 2026-10-26 | -0.35227 | -0.35227 | -0.13885 | |ret| > 15% |
| B3SA3 | 2026-10-26 | -0.36279 | -0.36279 | -0.13885 | |ret| > 15% |
| BBAS3 | 2026-10-26 | -0.29328 | -0.29328 | -0.13885 | |ret| > 15% |
| BBDC3 | 2026-10-26 | -0.20653 | -0.20653 | -0.13885 | |ret| > 15% |
| BBDC4 | 2026-10-26 | -0.21699 | -0.21699 | -0.13885 | |ret| > 15% |
| BEEF3 | 2026-10-26 | -0.22248 | -0.22248 | -0.13885 | |ret| > 15% |
| BPAC11 | 2026-10-26 | -0.24831 | -0.24831 | -0.13885 | |ret| > 15% |
| COGN3 | 2026-10-26 | -0.38387 | -0.38387 | -0.13885 | |ret| > 15% |
| CSAN3 | 2026-10-26 | -0.46731 | -0.46731 | -0.13885 | |ret| > 15% |
| CSNA3 | 2026-10-26 | -0.17463 | -0.17463 | -0.13885 | |ret| > 15% |
| CYRE3 | 2026-10-26 | -0.44813 | -0.44813 | -0.13885 | |ret| > 15% |
| DIRR3 | 2026-10-26 | -0.24048 | -0.24048 | -0.13885 | |ret| > 15% |
| ENEV3 | 2026-10-26 | -0.1528 | -0.1528 | -0.13885 | |ret| > 15% |
| ENGI11 | 2026-10-26 | -0.28855 | -0.28855 | -0.13885 | |ret| > 15% |
| EQTL3 | 2026-10-26 | -0.28723 | -0.28723 | -0.13885 | |ret| > 15% |
| FLRY3 | 2026-10-26 | -0.20703 | -0.20703 | -0.13885 | |ret| > 15% |
| HAPV3 | 2026-10-26 | -0.54926 | -0.54926 | -0.13885 | |ret| > 15% |
| HYPE3 | 2026-10-26 | -0.2455 | -0.2455 | -0.13885 | |ret| > 15% |
| IGTI11 | 2026-10-26 | -0.22888 | -0.22888 | -0.13885 | |ret| > 15% |
| LREN3 | 2026-10-26 | -0.33608 | -0.33608 | -0.13885 | |ret| > 15% |
| MGLU3 | 2026-10-26 | -0.58235 | -0.58235 | -0.13885 | |ret| > 15% |
| MOTV3 | 2026-10-26 | -0.26931 | -0.26931 | -0.13885 | |ret| > 15% |
| MRVE3 | 2026-10-26 | -0.42527 | -0.42527 | -0.13885 | |ret| > 15% |
| MULT3 | 2026-10-26 | -0.2526 | -0.2526 | -0.13885 | |ret| > 15% |
| NATU3 | 2026-10-26 | -0.2519 | -0.2519 | -0.13885 | |ret| > 15% |
| RADL3 | 2026-10-26 | -0.22535 | -0.22535 | -0.13885 | |ret| > 15% |
| RAIL3 | 2026-10-26 | -0.16756 | -0.16756 | -0.13885 | |ret| > 15% |
| RDOR3 | 2026-10-26 | -0.19918 | -0.19918 | -0.13885 | |ret| > 15% |
| RENT3 | 2026-10-26 | -0.39584 | -0.39584 | -0.13885 | |ret| > 15% |
| SBSP3 | 2026-10-26 | -0.20982 | -0.20982 | -0.13885 | |ret| > 15% |
| VAMO3 | 2026-10-26 | -0.56786 | -0.56786 | -0.13885 | |ret| > 15% |
| VIVA3 | 2026-10-26 | -0.27747 | -0.27747 | -0.13885 | |ret| > 15% |
| YDUQ3 | 2026-10-26 | -0.35541 | -0.35541 | -0.13885 | |ret| > 15% |

Contexto: 7081 retornos diários no período; |ret| > 10%: 115; > 15%: 56; > 30%: 14; máximo 0.2418, mínimo -0.5823.

## 2. `v1-eventos_acoes` com `data_com` de 2026-06-23 a 2026-11-10

Colunas: ['ticker', 'data_com', 'tipo', 'fator', 'isin', 'isin_emitido', 'cnpj', 'data_aprovacao']

Nenhum evento no período.

## 3. Proventos de ações do universo com `data_com` no período: o ajuste do pregão ex

77 proventos. Fração do provento que entrou no ajuste (1 = ajuste padrão): mediana 1.003, mín 0.811, máx 4.445.

Lista: provento ≥ 3% do preço ou ajuste fora de 0,75–1,25 do provento (17 casos):

| ticker | tipo | data_com | valor | prov/fech | pregao_ex | ret_fech | ret_aj | ret_aproximado_com_provento | fracao_do_provento_no_ajuste |
|---|---|---|---|---|---|---|---|---|---|
| CMIG4 | JCP | 2026-06-23 | 0.11020257159 | 0.01 | 2026-06-24 | -0.02457 | -0.00461 | -0.01454 | 1.991 |
| RADL3 | JCP | 2026-07-03 | 0.088359621 | 0.0052 | 2026-07-06 | 0.02168 | 0.02864 | 0.02685 | 1.346 |
| RADL3 | DIVIDENDO | 2026-07-03 | 0.02722277 | 0.0016 | 2026-07-06 | 0.02168 | 0.02864 | 0.02327 | 4.367 |
| BBSE3 | DIVIDENDO | 2026-08-06 | 1.98328466981 | 0.0484 | 2026-08-07 | -0.06299 | -0.01531 | -0.01457 | 0.985 |
| BPAC11 | JCP | 2026-08-10 | 0.258896221 | 0.0048 | 2026-08-11 | -0.06925 | -0.05564 | -0.06445 | 2.833 |
| VALE3 | DIVIDENDO | 2026-08-11 | 0.462016093 | 0.0062 | 2026-08-12 | -0.0164 | 0.0112 | -0.01019 | 4.445 |
| VALE3 | JCP | 2026-08-11 | 1.568705805 | 0.0211 | 2026-08-12 | -0.0164 | 0.0112 | 0.00469 | 1.309 |
| ENGI11 | DIVIDENDO | 2026-08-11 | 0.30000000000000004 | 0.0066 | 2026-08-12 | -0.0252 | -0.0144 | -0.01862 | 1.643 |
| TAEE11 | DIVIDENDO | 2026-08-14 | 0.24076375464 | 0.0063 | 2026-08-17 | -0.01819 | -0.0024 | -0.01184 | 2.487 |
| TAEE11 | JCP | 2026-08-14 | 0.35947457988 | 0.0095 | 2026-08-17 | -0.01819 | -0.0024 | -0.00871 | 1.666 |
| RECV3 | JCP | 2026-08-17 | 0.340736 | 0.0318 | 2026-08-18 | -0.05219 | -0.0211 | -0.02043 | 0.979 |
| PETR3 | JCP | 2026-08-21 | 0.87657566 | 0.0178 | 2026-08-24 | -0.04864 | -0.02192 | -0.03088 | 1.504 |
| PETR4 | JCP | 2026-08-21 | 0.87657566 | 0.0198 | 2026-08-24 | -0.04944 | -0.0196 | -0.02965 | 1.508 |
| PETR3 | DIVIDENDO | 2026-08-21 | 0.47156696 | 0.0096 | 2026-08-24 | -0.04864 | -0.02192 | -0.03908 | 2.796 |
| PETR4 | DIVIDENDO | 2026-08-21 | 0.47156696 | 0.0106 | 2026-08-24 | -0.04944 | -0.0196 | -0.03879 | 2.803 |
| MOTV3 | JCP | 2026-09-04 | 0.72331534623 | 0.0431 | 2026-09-08 | -0.0298 | 0.01391 | 0.01331 | 1.014 |
| CMIG4 | JCP | 2026-09-22 | 0.03495670057 | 0.0031 | 2026-09-23 | -0.02905 | -0.02304 | -0.02597 | 1.954 |

## 4. Preço parado (≥ 5 fechamentos iguais seguidos) no período

Nenhum.

## 5. Proventos somados por (ticker, data_com): fração exata do provento no ajuste (1 = padrão)

72 pares. Fração exata: mediana 1.0, mín 0.769, máx 3.0; fora de 0,95–1,05: 5.

| ticker | data_com | provento_total | prov/fech | pregao_ex | ret_fech | ret_aj | ret_ajuste_padrao | fracao_exata |
|---|---|---|---|---|---|---|---|---|
| BBAS3 | 2026-09-01 | 0.136963 | 0.0065 | 2026-09-02 | 0.04951 | 0.05474 | 0.05633 | 0.769 |
| BPAC11 | 2026-08-10 | 0.258896 | 0.0048 | 2026-08-11 | -0.06925 | -0.05564 | -0.06476 | 3.0 |
| CMIG4 | 2026-06-23 | 0.110203 | 0.01 | 2026-06-24 | -0.02457 | -0.00461 | -0.01469 | 2.0 |
| CMIG4 | 2026-09-22 | 0.034957 | 0.0031 | 2026-09-23 | -0.02905 | -0.02304 | -0.02605 | 2.0 |
| ENGI11 | 2026-08-11 | 0.3 | 0.0066 | 2026-08-12 | -0.0252 | -0.0144 | -0.01875 | 1.667 |
