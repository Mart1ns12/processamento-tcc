"""Valores esperados do banco da coleta, conforme a especificação (seções 3 e 7).

Constantes puras: nenhuma leitura de banco ou de arquivo acontece aqui.
"""

MACROS_PRECOS = {"IBOV", "USDBRL", "BRENT", "IVVB11"}      # seção 3.1
SERIES_FORA_CALENDARIO = {"IBOV", "USDBRL", "BRENT"}        # fora da análise de buracos/padrão de ticker
INDICES = {"CDI", "IPCA", "IDIV", "SMLL", "IFIX"}
UNITS = {"KLBN11", "BPAC11", "ENGI11", "IGTI11", "SANB11", "TAEE11"}
SEM_CNPJ_CONHECIDOS = {"CRFB3"}
ETAPAS_COLETA = ["precos", "macro", "noticias", "ipe", "enriquecimento", "juiza", "cadastro", "entrega", "analise"]
# Etapas de execuções manuais (ex.: tipo 'coletar'); nunca devem aparecer num daily
# corrigir_horas: execução manual tipo 'coletar' (vista pendente em 23/10/2026); provável correção do horário das notícias pedida à coleta: ao concluir, reavaliar a regra N1-A
ETAPAS_EXECUCAO_MANUAL = ["cvm_itr_dfp", "build_entrega", "corrigir_horas"]
STATUS_ETAPA ={"pendente", "em_andamento", "concluida", "falhou", "pulada"}
MODELOS_FINBERT = {"pt": "lucas-leme/FinBERT-PT-BR", "en": "ProsusAI/finbert"}
IDIOMAS = {"pt", "en"}
OFFSET_SP = "-03:00"
TOLERANCIA_PROB = 1e-3
HORAS_DAILY_UTC = (11, 21)   # 8h SP (agenda nova) e 18:30 SP (agenda antiga)
AMOSTRA_FUSO_POR_ANO = 300
