"""Ponto de entrada do diagnóstico do banco da coleta: `python -m processamento.diagnostico`.

Só lê o banco (SELECT/SHOW, conexão READ ONLY) e gera o relatório em Markdown
(padrão: `docs/diagnostico_banco.md`). Nada é gravado no banco.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from processamento import fontes
from processamento.diagnostico import consultas, historico, lacunas, temas
from processamento.diagnostico.regras import div, nova_secao
from processamento.diagnostico.relatorio import gerar_markdown

CAMINHO_PADRAO = fontes.RAIZ / "docs" / "diagnostico_banco.md"
FUSO = "America/Sao_Paulo"


def _secao_falha(titulo: str, erro: Exception) -> dict:
    """Seção que substitui uma seção cujo cálculo falhou, com a divergência `falha_consulta`."""
    secao = nova_secao(titulo)
    secao["notas"].append("Esta seção não pôde ser concluída; as demais continuaram.")
    secao["divergencias"].append(
        div("falha_consulta", "-", f"{titulo}: {type(erro).__name__}: {erro}")
    )
    return secao


def _seguro(titulo: str, func, *args) -> dict:
    """Roda uma seção; se ela falhar, devolve uma seção de falha no lugar."""
    try:
        return func(*args)
    except Exception as e:
        return _secao_falha(titulo, e)


def coletar(ler, mapa) -> list[dict]:
    """Roda todas as seções do diagnóstico na ordem do relatório e devolve a lista de seções.

    Se a existência das tabelas falhar, o diagnóstico para e devolve só essa seção de falha.
    """
    try:
        secao_existencia, existentes = consultas.secao_existencia(ler, mapa)
    except Exception as e:
        secao = nova_secao("Falha ao ler o esquema")
        secao["notas"].append("Não foi possível ler a lista de tabelas; o diagnóstico parou aqui.")
        secao["divergencias"].append(div("falha_consulta", "-", f"{type(e).__name__}: {e}"))
        return [secao]

    try:
        secao_colunas, df_colunas = consultas.secao_colunas_chaves(ler, mapa, existentes)
    except Exception as e:
        secao_colunas = _secao_falha("Colunas e chaves", e)
        df_colunas = pd.DataFrame()

    secoes = [
        secao_existencia,
        secao_colunas,
        _seguro("Linhas, período e nº de tickers", consultas.secao_resumo, ler, mapa, existentes),
        _seguro("Duplicatas", consultas.secao_duplicatas, ler, mapa, existentes),
        _seguro("Notícias", temas.secao_noticias, ler, mapa, existentes),
        _seguro("Valores distintos", consultas.secao_distintos, ler, mapa, existentes),
        _seguro("Preços e pregões", temas.secao_precos, ler, mapa, existentes),
        _seguro("Balanços", temas.secao_balancos, ler, mapa, existentes),
        _seguro("Tickers e CNPJs", temas.secao_tickers, ler, mapa, existentes),
        _seguro("Quantidade de ações suspeita", temas.secao_quantidade_acoes, ler, mapa, existentes),
        _seguro("Retornos diários suspeitos", temas.secao_retornos_suspeitos, ler, mapa, existentes),
        _seguro("Lacunas nas séries de preços e índices", lacunas.secao_lacunas, ler, mapa, existentes),
        _seguro("Colunas vazias", consultas.secao_vazios, ler, mapa, existentes, df_colunas),
        _seguro("Gatilho da coleta e composição", temas.secao_painel, ler, mapa, existentes),
        _seguro("Histórico novo", historico.secao_historico, ler, mapa, existentes),
    ]
    return secoes


def main(argv=None, ler=None) -> int:
    """Gera o relatório do diagnóstico. Devolve 0 em sucesso, 2 se a configuração estiver
    incompleta e 3 se a sessão não estiver em somente leitura (nada é gravado nesses casos).
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.diagnostico",
        description="Diagnóstico do banco da coleta, só leitura. Gera um relatório em Markdown.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=CAMINHO_PADRAO,
        help="arquivo .md de saída (padrão: docs/diagnostico_banco.md)",
    )
    args = parser.parse_args(argv)

    if ler is None:
        try:
            engine = fontes.criar_engine()
        except fontes.ErroConfiguracao as e:
            print(f"Configuração do banco incompleta: {e}")
            return 2

        def ler(sql, params=None):
            return fontes.executar_leitura(sql, params, engine=engine)

        try:
            fontes.verificar_sessao_somente_leitura(ler)
        except fontes.ErroSomenteLeitura as e:
            print(f"{e}. Nada foi gravado.")
            return 3
        except Exception as e:
            # Não mostra a mensagem original: ela pode conter host ou usuário.
            print(f"Falha ao conectar ao banco ({type(e).__name__}). Nada foi gravado.")
            return 3

    gerado_em = datetime.now(ZoneInfo(FUSO)).strftime("%Y-%m-%d %H:%M") + " (America/Sao_Paulo)"
    try:
        df_versao = ler("SELECT VERSION() AS versao, DATABASE() AS banco")
        versao = str(df_versao["versao"].iloc[0])
        banco = str(df_versao["banco"].iloc[0])
    except Exception:
        versao, banco = "desconhecida", "desconhecido"

    cabecalho = {"gerado_em": gerado_em, "banco": banco, "versao_mysql": versao}
    secoes = coletar(ler, fontes.carregar_mapa())
    markdown = gerar_markdown(cabecalho, secoes)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(markdown, encoding="utf-8")

    divergencias = sum(len(secao["divergencias"]) for secao in secoes)
    print(f"Relatório: {args.saida} | divergências: {divergencias}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
