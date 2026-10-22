-- tcc_scraper.features_dataset_v1 definição

CREATE TABLE `features_dataset_v1` (
  `data` date NOT NULL,
  `ticker` varchar(12) NOT NULL,
  `quant_noticias` int NOT NULL,
  `positivo` double DEFAULT NULL,
  `neutro` double DEFAULT NULL,
  `negativo` double DEFAULT NULL,
  `score_finbert` double DEFAULT NULL,
  `retorno_1d` double DEFAULT NULL,
  `retorno_5d` double DEFAULT NULL,
  `retorno_20d` double DEFAULT NULL,
  `volatilidade_20d` double DEFAULT NULL,
  `volume_relativo` double DEFAULT NULL,
  `retorno_ibovespa` double DEFAULT NULL,
  `target` smallint DEFAULT NULL,
  PRIMARY KEY (`data`,`ticker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_articles definição

CREATE TABLE `raw_articles` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `url_hash` varchar(64) NOT NULL,
  `url` text NOT NULL,
  `google_id` text,
  `resolved_url` text,
  `title` text NOT NULL,
  `source_name` text,
  `source_domain` varchar(255) DEFAULT NULL,
  `published_at` datetime(6) NOT NULL,
  `lang` varchar(5) NOT NULL,
  `collected_at` datetime(6) NOT NULL,
  `origem` varchar(16) NOT NULL DEFAULT 'google_news',
  `published_precision` varchar(8) NOT NULL DEFAULT 'datetime',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_raw_articles_url_hash` (`url_hash`),
  KEY `ix_articles_published_at` (`published_at`),
  KEY `ix_articles_source_domain` (`source_domain`),
  KEY `ix_articles_origem` (`origem`)
) ENGINE=InnoDB AUTO_INCREMENT=299800 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_collection_runs definição

CREATE TABLE `raw_collection_runs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `collector` varchar(32) NOT NULL,
  `unit_key` varchar(128) NOT NULL,
  `status` varchar(16) NOT NULL,
  `items_found` int NOT NULL,
  `hit_cap` tinyint(1) NOT NULL,
  `error` text,
  `finished_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_collection_runs_collector_unit` (`collector`,`unit_key`)
) ENGINE=InnoDB AUTO_INCREMENT=20977 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_llm_prompts definição

CREATE TABLE `raw_llm_prompts` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `nome` varchar(64) NOT NULL,
  `versao` int NOT NULL,
  `texto_template` longtext NOT NULL,
  `schema_json` json NOT NULL,
  `sha256` varchar(64) NOT NULL,
  `criado_em` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_llm_prompts_nome_versao` (`nome`,`versao`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_macro definição

CREATE TABLE `raw_macro` (
  `series` varchar(24) NOT NULL,
  `date` date NOT NULL,
  `value` double NOT NULL,
  PRIMARY KEY (`series`,`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_prices definição

CREATE TABLE `raw_prices` (
  `ticker` varchar(12) NOT NULL,
  `date` date NOT NULL,
  `open` double DEFAULT NULL,
  `high` double DEFAULT NULL,
  `low` double DEFAULT NULL,
  `close` double DEFAULT NULL,
  `adj_close` double DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  `source` varchar(16) NOT NULL,
  PRIMARY KEY (`ticker`,`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-acoes_emitidas` definição

CREATE TABLE `v1-acoes_emitidas` (
  `cnpj` varchar(14) NOT NULL,
  `data_referencia` date NOT NULL,
  `qtd_on` bigint DEFAULT NULL,
  `qtd_pn` bigint DEFAULT NULL,
  PRIMARY KEY (`cnpj`,`data_referencia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-balancos` definição

CREATE TABLE `v1-balancos` (
  `cnpj` varchar(14) NOT NULL,
  `tipo_documento` varchar(3) NOT NULL,
  `data_inicio_periodo` date NOT NULL,
  `data_fim_periodo` date NOT NULL,
  `data_entrega` date DEFAULT NULL,
  `receita_liquida` double DEFAULT NULL,
  `lucro_bruto` double DEFAULT NULL,
  `lucro_liquido` double DEFAULT NULL,
  `patrimonio_liquido` double DEFAULT NULL,
  `ebit` double DEFAULT NULL,
  `depreciacao_amortizacao` double DEFAULT NULL,
  `emprestimos_curto_prazo` double DEFAULT NULL,
  `emprestimos_longo_prazo` double DEFAULT NULL,
  `caixa` double DEFAULT NULL,
  `aplicacoes_financeiras` double DEFAULT NULL,
  PRIMARY KEY (`cnpj`,`tipo_documento`,`data_inicio_periodo`,`data_fim_periodo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-cadastro` definição

CREATE TABLE `v1-cadastro` (
  `ticker` varchar(12) NOT NULL,
  `cnpj` varchar(14) DEFAULT NULL,
  `empresa` varchar(128) NOT NULL,
  `setor` varchar(128) DEFAULT NULL,
  `subsetor` varchar(128) DEFAULT NULL,
  `tipo_acao` varchar(8) NOT NULL,
  `unit_qtd_on` smallint DEFAULT NULL,
  `unit_qtd_pn` smallint DEFAULT NULL,
  PRIMARY KEY (`ticker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-indices` definição

CREATE TABLE `v1-indices` (
  `data` date NOT NULL,
  `indice` varchar(8) NOT NULL,
  `valor` double NOT NULL,
  PRIMARY KEY (`data`,`indice`),
  KEY `ix_indices_indice` (`indice`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-mudancas_ticker` definição

CREATE TABLE `v1-mudancas_ticker` (
  `ticker_antigo` varchar(12) NOT NULL,
  `ticker_novo` varchar(12) NOT NULL,
  `data_mudanca` date DEFAULT NULL,
  PRIMARY KEY (`ticker_antigo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-noticias` definição

CREATE TABLE `v1-noticias` (
  `id` varchar(16) NOT NULL,
  `ticker` varchar(12) NOT NULL,
  `data_hora_publicacao` varchar(32) DEFAULT NULL,
  `data_hora_coleta` varchar(32) NOT NULL,
  `titulo` text NOT NULL,
  `fonte` varchar(255) DEFAULT NULL,
  `link` text,
  `prob_positivo` double DEFAULT NULL,
  `prob_neutro` double DEFAULT NULL,
  `prob_negativo` double DEFAULT NULL,
  `data_publicacao` date NOT NULL,
  `momento_pregao` varchar(16) NOT NULL,
  `origem` varchar(16) NOT NULL,
  `papel` varchar(24) DEFAULT NULL,
  `tipo_conteudo` varchar(24) DEFAULT NULL,
  `evento` varchar(24) DEFAULT NULL,
  `qualidade` double DEFAULT NULL,
  PRIMARY KEY (`id`,`ticker`),
  KEY `ix_noticias_ticker_data_publicacao` (`ticker`,`data_publicacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_comandos` definição

CREATE TABLE `v1-painel_comandos` (
  `id` varchar(36) NOT NULL,
  `tipo` varchar(16) NOT NULL,
  `parametros` json NOT NULL,
  `criado_em` datetime(6) NOT NULL,
  `ack_em` datetime(6) DEFAULT NULL,
  `ok` tinyint(1) DEFAULT NULL,
  `erro` text,
  PRIMARY KEY (`id`),
  KEY `ix_painel_comandos_ack_em` (`ack_em`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_comandos_aplicados` definição

CREATE TABLE `v1-painel_comandos_aplicados` (
  `id` varchar(36) NOT NULL,
  `aplicado_em` datetime(6) NOT NULL,
  `ok` tinyint(1) NOT NULL,
  `erro` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_execucoes` definição

CREATE TABLE `v1-painel_execucoes` (
  `id` varchar(48) NOT NULL,
  `tipo` varchar(12) NOT NULL,
  `etapa_alvo` varchar(24) DEFAULT NULL,
  `origem` varchar(8) NOT NULL,
  `status` varchar(16) NOT NULL,
  `aguardando` varchar(16) DEFAULT NULL,
  `iniciada_em` datetime(6) NOT NULL,
  `finalizada_em` datetime(6) DEFAULT NULL,
  `prazo_em` datetime(6) NOT NULL,
  `erro` text,
  `atualizada_em` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_painel_execucoes_iniciada_em` (`iniciada_em`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_heartbeat` definição

CREATE TABLE `v1-painel_heartbeat` (
  `host` varchar(64) NOT NULL,
  `versao` varchar(32) NOT NULL,
  `ocupado_com` varchar(16) DEFAULT NULL,
  `visto_em` datetime(6) NOT NULL,
  PRIMARY KEY (`host`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_historico` definição

CREATE TABLE `v1-painel_historico` (
  `id` varchar(32) NOT NULL,
  `status` varchar(16) NOT NULL,
  `modo` varchar(24) NOT NULL,
  `anos` json NOT NULL,
  `ano_atual` int DEFAULT NULL,
  `coletor_atual` varchar(32) DEFAULT NULL,
  `unidade_atual` varchar(128) DEFAULT NULL,
  `iniciada_em` datetime(6) NOT NULL,
  `finalizada_em` datetime(6) DEFAULT NULL,
  `itens_por_min` double NOT NULL DEFAULT '0',
  `erro` text,
  `atualizada_em` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_historico_progresso` definição

CREATE TABLE `v1-painel_historico_progresso` (
  `ano` int NOT NULL,
  `coletor` varchar(32) NOT NULL,
  `unidades_total` int NOT NULL DEFAULT '0',
  `unidades_feitas` int NOT NULL DEFAULT '0',
  `unidades_erro` int NOT NULL DEFAULT '0',
  `itens` int NOT NULL DEFAULT '0',
  `status_segmento` varchar(16) NOT NULL,
  `atualizado_em` datetime(6) NOT NULL,
  PRIMARY KEY (`ano`,`coletor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_logs` definição

CREATE TABLE `v1-painel_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `ts` datetime(6) NOT NULL,
  `nivel` varchar(8) NOT NULL,
  `origem` varchar(16) NOT NULL,
  `etapa` varchar(24) DEFAULT NULL,
  `mensagem` text NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_painel_logs_ts` (`ts`)
) ENGINE=InnoDB AUTO_INCREMENT=343 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-precos` definição

CREATE TABLE `v1-precos` (
  `data` date NOT NULL,
  `ticker` varchar(12) NOT NULL,
  `abertura` double DEFAULT NULL,
  `maxima` double DEFAULT NULL,
  `minima` double DEFAULT NULL,
  `fechamento` double DEFAULT NULL,
  `fechamento_ajustado` double DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  PRIMARY KEY (`data`,`ticker`),
  KEY `ix_precos_ticker` (`ticker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-proventos` definição

CREATE TABLE `v1-proventos` (
  `ticker` varchar(12) NOT NULL,
  `tipo` varchar(10) NOT NULL,
  `data_com` date NOT NULL,
  `valor_por_acao` double NOT NULL,
  `data_pagamento` date DEFAULT NULL,
  PRIMARY KEY (`ticker`,`tipo`,`data_com`),
  KEY `ix_proventos_ticker` (`ticker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_b3_cadastro` definição

CREATE TABLE `v1-raw_b3_cadastro` (
  `cd_cvm` int NOT NULL AUTO_INCREMENT,
  `cnpj` varchar(14) DEFAULT NULL,
  `trading_name` varchar(128) DEFAULT NULL,
  `issuing_company` varchar(8) DEFAULT NULL,
  `industry_classification` text,
  `other_codes` json DEFAULT NULL,
  `payload` json NOT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`cd_cvm`)
) ENGINE=InnoDB AUTO_INCREMENT=80234 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_b3_proventos` definição

CREATE TABLE `v1-raw_b3_proventos` (
  `registro_hash` varchar(64) NOT NULL,
  `issuing_company` varchar(8) NOT NULL,
  `trading_name` varchar(128) DEFAULT NULL,
  `type_stock` varchar(16) DEFAULT NULL,
  `corporate_action` varchar(64) DEFAULT NULL,
  `value_cash` double DEFAULT NULL,
  `last_date_prior_ex` date DEFAULT NULL,
  `date_approval` date DEFAULT NULL,
  `ratio` varchar(32) DEFAULT NULL,
  `quoted_per_shares` varchar(32) DEFAULT NULL,
  `payload` json NOT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`registro_hash`),
  KEY `ix_raw_b3_proventos_issuing_company` (`issuing_company`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_b3_suplemento` definição

CREATE TABLE `v1-raw_b3_suplemento` (
  `registro_hash` varchar(64) NOT NULL,
  `issuing_company` varchar(8) NOT NULL,
  `tipo` varchar(8) NOT NULL,
  `payload` json NOT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`registro_hash`),
  KEY `ix_raw_b3_suplemento_issuing_company` (`issuing_company`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_cvm_acoes` definição

CREATE TABLE `v1-raw_cvm_acoes` (
  `cnpj` varchar(14) NOT NULL,
  `tipo_documento` varchar(3) NOT NULL,
  `dt_refer` date NOT NULL,
  `versao` int NOT NULL,
  `cd_cvm` int NOT NULL,
  `qt_on` bigint DEFAULT NULL,
  `qt_pn` bigint DEFAULT NULL,
  `qt_total` bigint DEFAULT NULL,
  `dt_receb` date DEFAULT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`cnpj`,`tipo_documento`,`dt_refer`,`versao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_cvm_balancos` definição

CREATE TABLE `v1-raw_cvm_balancos` (
  `cnpj` varchar(14) NOT NULL,
  `tipo_documento` varchar(3) NOT NULL,
  `dt_refer` date NOT NULL,
  `versao` int NOT NULL,
  `demonstracao` varchar(3) NOT NULL,
  `cd_conta` varchar(16) NOT NULL,
  `dt_ini_exerc` date NOT NULL,
  `dt_fim_exerc` date NOT NULL,
  `cd_cvm` int NOT NULL,
  `ds_conta` varchar(255) DEFAULT NULL,
  `ordem_exerc` varchar(16) NOT NULL,
  `escala_moeda` varchar(8) NOT NULL,
  `vl_conta` double NOT NULL,
  `dt_receb` date DEFAULT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`cnpj`,`tipo_documento`,`dt_refer`,`versao`,`demonstracao`,`cd_conta`,`dt_ini_exerc`,`dt_fim_exerc`),
  KEY `ix_raw_cvm_balancos_cd_cvm` (`cd_cvm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_cvm_cadastro` definição

CREATE TABLE `v1-raw_cvm_cadastro` (
  `cnpj` varchar(14) NOT NULL,
  `cd_cvm` int NOT NULL,
  `denom_social` text NOT NULL,
  `sit` varchar(32) DEFAULT NULL,
  `setor_ativ` text,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`cnpj`),
  KEY `ix_raw_cvm_cadastro_cd_cvm` (`cd_cvm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_ipe_docs` definição

CREATE TABLE `v1-raw_ipe_docs` (
  `protocolo_entrega` varchar(32) NOT NULL,
  `cnpj` varchar(14) NOT NULL,
  `nome_companhia` text,
  `cd_cvm` int NOT NULL,
  `data_referencia` date DEFAULT NULL,
  `categoria` varchar(128) NOT NULL,
  `tipo` varchar(255) DEFAULT NULL,
  `especie` varchar(255) DEFAULT NULL,
  `assunto` text,
  `data_entrega` date NOT NULL,
  `tipo_apresentacao` varchar(64) DEFAULT NULL,
  `versao` int DEFAULT NULL,
  `link_download` text NOT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`protocolo_entrega`),
  KEY `ix_raw_ipe_docs_cd_cvm` (`cd_cvm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_article_bodies definição

CREATE TABLE `raw_article_bodies` (
  `article_id` bigint NOT NULL,
  `body_text` text NOT NULL,
  `extraction_method` varchar(32) NOT NULL,
  `fetched_at` datetime(6) NOT NULL,
  PRIMARY KEY (`article_id`),
  CONSTRAINT `fk_raw_article_bodies_article_id` FOREIGN KEY (`article_id`) REFERENCES `raw_articles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.raw_llm_runs definição

CREATE TABLE `raw_llm_runs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `prompt_id` bigint NOT NULL,
  `data_referencia` date NOT NULL,
  `pregao_referencia` date DEFAULT NULL,
  `modelo` varchar(64) NOT NULL,
  `prompt_renderizado` longtext NOT NULL,
  `resposta_bruta` longtext,
  `resposta_json` json DEFAULT NULL,
  `resumo_geral` text,
  `buscas_json` json DEFAULT NULL,
  `citacoes_json` json DEFAULT NULL,
  `tokens_entrada` int DEFAULT NULL,
  `tokens_saida` int DEFAULT NULL,
  `tokens_pensamento` int DEFAULT NULL,
  `latencia_ms` int DEFAULT NULL,
  `status` varchar(16) NOT NULL,
  `erro` text,
  `iniciado_em` datetime(6) NOT NULL,
  `finalizado_em` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_raw_llm_runs_prompt_id` (`prompt_id`),
  KEY `ix_llm_runs_data_referencia` (`data_referencia`),
  CONSTRAINT `fk_raw_llm_runs_prompt_id` FOREIGN KEY (`prompt_id`) REFERENCES `raw_llm_prompts` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.staging_article_sentiment definição

CREATE TABLE `staging_article_sentiment` (
  `article_id` bigint NOT NULL,
  `model` varchar(64) NOT NULL,
  `prob_pos` double NOT NULL,
  `prob_neu` double NOT NULL,
  `prob_neg` double NOT NULL,
  `text_source` varchar(8) NOT NULL,
  `scored_at` datetime(6) NOT NULL,
  PRIMARY KEY (`article_id`,`model`),
  CONSTRAINT `fk_staging_article_sentiment_article_id` FOREIGN KEY (`article_id`) REFERENCES `raw_articles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ck_article_sentiment_probs_nonneg` CHECK (((`prob_pos` >= 0) and (`prob_neu` >= 0) and (`prob_neg` >= 0)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.staging_article_tickers definição

CREATE TABLE `staging_article_tickers` (
  `article_id` bigint NOT NULL,
  `ticker` varchar(12) NOT NULL,
  PRIMARY KEY (`article_id`,`ticker`),
  KEY `ix_article_tickers_ticker` (`ticker`),
  CONSTRAINT `fk_staging_article_tickers_article_id` FOREIGN KEY (`article_id`) REFERENCES `raw_articles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.staging_llm_acoes_sinais definição

CREATE TABLE `staging_llm_acoes_sinais` (
  `data_referencia` date NOT NULL,
  `ticker` varchar(12) NOT NULL,
  `run_id` bigint NOT NULL,
  `pregao_referencia` date DEFAULT NULL,
  `direcao_esperada` varchar(8) NOT NULL,
  `confianca` double NOT NULL,
  `motivo` text NOT NULL,
  `setor` varchar(32) NOT NULL,
  `noticias_relacionadas` json NOT NULL,
  PRIMARY KEY (`data_referencia`,`ticker`),
  KEY `fk_staging_llm_acoes_sinais_run_id` (`run_id`),
  KEY `ix_llm_acoes_sinais_ticker` (`ticker`),
  CONSTRAINT `fk_staging_llm_acoes_sinais_run_id` FOREIGN KEY (`run_id`) REFERENCES `raw_llm_runs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.staging_llm_mercados definição

CREATE TABLE `staging_llm_mercados` (
  `data_referencia` date NOT NULL,
  `nome` varchar(64) NOT NULL,
  `run_id` bigint NOT NULL,
  `pregao_referencia` date DEFAULT NULL,
  `tipo` varchar(16) NOT NULL,
  `variacao_pct` double DEFAULT NULL,
  `motivo` text NOT NULL,
  PRIMARY KEY (`data_referencia`,`nome`),
  KEY `fk_staging_llm_mercados_run_id` (`run_id`),
  CONSTRAINT `fk_staging_llm_mercados_run_id` FOREIGN KEY (`run_id`) REFERENCES `raw_llm_runs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.staging_llm_noticias_empresas definição

CREATE TABLE `staging_llm_noticias_empresas` (
  `data_referencia` date NOT NULL,
  `ticker` varchar(12) NOT NULL,
  `item_hash` varchar(64) NOT NULL,
  `run_id` bigint NOT NULL,
  `pregao_referencia` date DEFAULT NULL,
  `titulo` text NOT NULL,
  `resumo` text NOT NULL,
  `fonte` varchar(255) DEFAULT NULL,
  `url` text,
  `publicado_em` date DEFAULT NULL,
  `setor` varchar(32) NOT NULL,
  `sentimento` varchar(16) NOT NULL,
  `relevancia` double NOT NULL,
  PRIMARY KEY (`data_referencia`,`ticker`,`item_hash`),
  KEY `fk_staging_llm_noticias_empresas_run_id` (`run_id`),
  KEY `ix_llm_noticias_empresas_ticker` (`ticker`),
  CONSTRAINT `fk_staging_llm_noticias_empresas_run_id` FOREIGN KEY (`run_id`) REFERENCES `raw_llm_runs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.staging_llm_noticias_macro definição

CREATE TABLE `staging_llm_noticias_macro` (
  `data_referencia` date NOT NULL,
  `item_hash` varchar(64) NOT NULL,
  `run_id` bigint NOT NULL,
  `pregao_referencia` date DEFAULT NULL,
  `escopo` varchar(8) NOT NULL,
  `titulo` text NOT NULL,
  `resumo` text NOT NULL,
  `fonte` varchar(255) DEFAULT NULL,
  `url` text,
  `publicado_em` date DEFAULT NULL,
  `commodities_afetadas` json NOT NULL,
  `direcao_commodity` varchar(16) NOT NULL,
  `setores_afetados` json NOT NULL,
  PRIMARY KEY (`data_referencia`,`item_hash`),
  KEY `fk_staging_llm_noticias_macro_run_id` (`run_id`),
  CONSTRAINT `fk_staging_llm_noticias_macro_run_id` FOREIGN KEY (`run_id`) REFERENCES `raw_llm_runs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-painel_etapas` definição

CREATE TABLE `v1-painel_etapas` (
  `execucao_id` varchar(48) NOT NULL,
  `etapa_id` varchar(24) NOT NULL,
  `ordem` smallint NOT NULL,
  `status` varchar(16) NOT NULL,
  `unidades_total` int DEFAULT NULL,
  `unidades_feitas` int NOT NULL DEFAULT '0',
  `unidades_erro` int NOT NULL DEFAULT '0',
  `unidades_saturadas` int NOT NULL DEFAULT '0',
  `itens` int NOT NULL DEFAULT '0',
  `iniciada_em` datetime(6) DEFAULT NULL,
  `finalizada_em` datetime(6) DEFAULT NULL,
  `ultimo_erro_unidade` varchar(128) DEFAULT NULL,
  `ultimo_erro_mensagem` text,
  `atualizada_em` datetime(6) NOT NULL,
  PRIMARY KEY (`execucao_id`,`etapa_id`),
  CONSTRAINT `fk_painel_etapas_execucao_id` FOREIGN KEY (`execucao_id`) REFERENCES `v1-painel_execucoes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-raw_llm_juiza_runs` definição

CREATE TABLE `v1-raw_llm_juiza_runs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `prompt_id` bigint NOT NULL,
  `modelo` varchar(64) NOT NULL,
  `n_itens` int NOT NULL,
  `tokens_entrada` int DEFAULT NULL,
  `tokens_saida` int DEFAULT NULL,
  `latencia_ms` int DEFAULT NULL,
  `status` varchar(16) NOT NULL,
  `erro` text,
  `resposta_bruta` longtext,
  `iniciado_em` datetime(6) NOT NULL,
  `finalizado_em` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_raw_llm_juiza_runs_prompt_id` (`prompt_id`),
  CONSTRAINT `fk_raw_llm_juiza_runs_prompt_id` FOREIGN KEY (`prompt_id`) REFERENCES `raw_llm_prompts` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=117 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- tcc_scraper.`v1-staging_noticias_julgamento` definição

CREATE TABLE `v1-staging_noticias_julgamento` (
  `article_id` bigint NOT NULL,
  `ticker` varchar(12) NOT NULL,
  `prompt_versao` int NOT NULL,
  `run_id` bigint DEFAULT NULL,
  `modelo` varchar(64) NOT NULL,
  `papel` varchar(24) NOT NULL,
  `tipo_conteudo` varchar(24) NOT NULL,
  `evento` varchar(24) NOT NULL,
  `tickers_adicionais` json NOT NULL,
  `qualidade` double NOT NULL,
  `confianca` double NOT NULL,
  `julgado_em` datetime(6) NOT NULL,
  PRIMARY KEY (`article_id`,`ticker`,`prompt_versao`),
  KEY `fk_staging_noticias_julgamento_run_id` (`run_id`),
  KEY `ix_staging_noticias_julgamento_ticker` (`ticker`),
  CONSTRAINT `fk_staging_noticias_julgamento_article_id` FOREIGN KEY (`article_id`) REFERENCES `raw_articles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_staging_noticias_julgamento_run_id` FOREIGN KEY (`run_id`) REFERENCES `v1-raw_llm_juiza_runs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;