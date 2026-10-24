"""Montagem do dataset do experimento (seção 7.3 da especificação; plano da etapa 5, fase 8).

Junta as variáveis de preço, as de notícias, o alvo e os dias de resultado em uma linha por
pregão × ação do universo do modelo. `montar_dataset` é pura: recebe DataFrames (ver
`DadosExperimento`) e devolve DataFrames, sem banco ou rede. Ausência é NaN, nunca 0. Os ranks
ficam para `preparacao.preparar`, que roda só sobre as linhas daqui.

`executar` e `main` (fase 9) são a parte com I/O: leem a coleta só por `fontes.py`, montam o
dataset e gravam o CSV e o JSON em `saida/experimento/` (fora do git).
Uso: `python -m processamento.experimento.dataset [--versao todas|principais|hora_real_noite] [--ate AAAA-MM-DD] [--proximo AAAA-MM-DD] [--pasta PASTA]`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from processamento import calendario, fontes
from processamento.exclusoes import carregar_exclusoes
from processamento.experimento.alvo import alvos
from processamento.experimento.noticias import VERSOES, preparar_noticias
from processamento.experimento.parametros import ParametrosExperimento, carregar_parametros_experimento
from processamento.experimento.preparacao import COLUNAS_ALVO, COLUNAS_RANK, IDENTIFICACAO
from processamento.experimento.resultados import dias_de_resultado
from processamento.experimento.tom import COLUNAS_NOTICIAS, variaveis_de_noticias
from processamento.experimento.variaveis import variaveis_de_preco
from processamento.fatos.precos import ParametrosPrecos, carregar_parametros_precos, indice_pregoes, mapas_cadastro
from processamento.tickers import ligar_a_cnpj, mapas_por_empresa
from processamento.universo import montar_universo

COLUNAS_DATASET = IDENTIFICACAO + COLUNAS_NOTICIAS + COLUNAS_RANK + COLUNAS_ALVO


@dataclass(frozen=True)
class DadosExperimento:
    """Tabelas de entrada do dataset, já lidas. `universo` vem de `montar_universo` (uma linha por
    pregão × ticker; só `no_universo` entra). `mudancas`: ticker antigo -> atual."""

    precos: pd.DataFrame
    cadastro: pd.DataFrame
    noticias: pd.DataFrame
    balancos: pd.DataFrame
    universo: pd.DataFrame
    mudancas: dict[str, str]


def _mascara(modelo: pd.DataFrame, cal: list, tickers: list[str]) -> pd.DataFrame:
    """True onde a ação está no universo do modelo naquele pregão (pregão × ticker)."""
    dentro = modelo.assign(dentro=True).pivot(index="data", columns="ticker", values="dentro")
    return dentro.reindex(index=indice_pregoes(cal), columns=tickers).fillna(False).astype(bool)


def _grades_em_longo(grades: dict[str, pd.DataFrame]) -> list[pd.DataFrame]:
    """Cada grade (pregão × ticker) vira um DataFrame longo: data, ticker e o valor com o nome da variável."""
    return [
        g.rename_axis(index="data", columns="ticker")
        .reset_index()
        .melt(id_vars="data", var_name="ticker", value_name=nome)
        for nome, g in grades.items()
    ]


def _juntar(base: pd.DataFrame, longos: list[pd.DataFrame]) -> pd.DataFrame:
    """Encadeia as tabelas longas à `base` pela esquerda, em (data, ticker)."""
    df = base
    for longo in longos:
        df = df.merge(longo, on=["data", "ticker"], how="left")
    return df


def montar_dataset(
    dados: DadosExperimento,
    cal: list,
    *,
    versao_noticias: str = "todas",
    proximo_ao_vivo=None,
    params: ParametrosExperimento | None = None,
    params_precos: ParametrosPrecos | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Dataset do experimento: uma linha por pregão × ação do universo do modelo, em `COLUNAS_DATASET`.

    Só entram as linhas com `no_universo` (sem BDR, exclusões ou ação sem preço no dia). O tom
    de setor e de mercado usa só essas linhas. `cobertura_inicio` é a menor `data_publicacao` das
    notícias lidas, antes do filtro de versão. Sem `proximo_ao_vivo`, a noite do último pregão de
    `cal` ainda está aberta. `info`: contagens das notícias e dos dias de resultado, mais linhas,
    pregões, versão, cobertura ("AAAA-MM-DD" ou None) e `setor_herdado` (ticker fora do cadastro
    que ganhou o setor da empresa dele, `tickers.mapas_por_empresa`).
    """
    params = carregar_parametros_experimento() if params is None else params
    params_precos = carregar_parametros_precos() if params_precos is None else params_precos
    cal = list(cal)
    setor_de, cnpj_de = mapas_cadastro(dados.cadastro)

    modelo = dados.universo.loc[dados.universo["no_universo"], ["data", "ticker", "universo"]].reset_index(drop=True)
    tickers = sorted(modelo["ticker"].unique())
    # Ticker fora do cadastro ligado a uma empresa dele (ex.: JBSS3 antigo) herda CNPJ e setor (plano Fase 6b)
    setor_de, cnpj_de, herdados = mapas_por_empresa(tickers, setor_de, cnpj_de, dados.mudancas)
    empresa_de = {t: ligar_a_cnpj(t, cnpj_de, dados.mudancas)[0] or t for t in tickers}
    modelo["empresa"] = modelo["ticker"].map(empresa_de)
    modelo["setor"] = modelo["ticker"].map(setor_de)
    mascara = _mascara(modelo, cal, tickers)

    grades = variaveis_de_preco(
        dados.precos, cal, tickers, mascara, setor_de, cnpj_de, params, params_precos
    )
    grades.update(alvos(dados.precos, cal, tickers))
    df = _juntar(modelo, _grades_em_longo(grades))

    nots, info_nots = preparar_noticias(
        dados.noticias, cal, cnpj_de, dados.mudancas, versao_noticias, params, proximo_ao_vivo
    )
    datas_pub = pd.to_datetime(dados.noticias["data_publicacao"])
    cobertura = datas_pub.min().normalize() if datas_pub.notna().any() else None
    noite_aberta = cal[-1] if cal and proximo_ao_vivo is None else None
    df = variaveis_de_noticias(
        nots, df, cal, params, noite_aberta=noite_aberta, cobertura_inicio=cobertura
    )

    resultado, info_res = dias_de_resultado(dados.balancos, cal, proximo_ao_vivo)
    marcados = pd.MultiIndex.from_frame(resultado[["data", "empresa"]])
    df["dia_resultado"] = pd.MultiIndex.from_frame(df[["data", "empresa"]]).isin(marcados)

    df = df.sort_values(["data", "ticker"]).reset_index(drop=True)[COLUNAS_DATASET]
    info = {
        **info_nots,
        **info_res,
        "linhas": len(df),
        "pregoes": len(cal),
        "versao_noticias": versao_noticias,
        "inicio_janela_efetivo": "fechamento" if versao_noticias == "hora_real_noite" else params.inicio_janela,
        "cobertura_inicio": None if cobertura is None else cobertura.date().isoformat(),
        "setor_herdado": {t: herdados[t][1] for t in sorted(herdados) if herdados[t][1] is not None},
    }
    return df, info


PASTA_PADRAO = fontes.RAIZ / "saida" / "experimento"


def _leitor_padrao() -> Callable[..., pd.DataFrame]:
    """Leitor pela conexão somente leitura da coleta; confere READ ONLY antes de devolver."""
    engine = fontes.criar_engine()

    def leitor(sql, params=None):
        return fontes.executar_leitura(sql, params, engine=engine)

    fontes.verificar_sessao_somente_leitura(leitor)
    return leitor


def _json_padrao(valor):
    """Converte tipos do numpy que o json padrão não grava; o resto vira texto."""
    if isinstance(valor, np.bool_):
        return bool(valor)
    if isinstance(valor, np.integer):
        return int(valor)
    if isinstance(valor, np.floating):
        return float(valor)
    return str(valor)


def _data_argumento(texto: str) -> date:
    """Data em AAAA-MM-DD para o argparse."""
    try:
        return date.fromisoformat(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"data inválida (use AAAA-MM-DD): {texto}") from e


def salvar_dataset(df: pd.DataFrame, info: dict, pasta: Path) -> Path:
    """Grava `dataset-<versao>-<última data>.csv` (UTF-8, sem índice, datas AAAA-MM-DD) e o `.json` ao lado.

    O JSON traz `info` (com os parâmetros em `info["parametros"]`, se houver), o sha256 do CSV e
    `gerado_em` (horário de São Paulo). Devolve o caminho do CSV.
    """
    if df.empty:
        raise ValueError("dataset vazio: nada a gravar")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    ultima = pd.Timestamp(df["data"].max()).strftime("%Y-%m-%d")
    base = f"dataset-{info['versao_noticias']}-{ultima}"
    csv = pasta / f"{base}.csv"
    df.to_csv(csv, index=False, date_format="%Y-%m-%d", encoding="utf-8", lineterminator="\n")
    registro = {
        **info,
        "arquivo": csv.name,
        "sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "gerado_em": datetime.now(fontes.SP).isoformat(timespec="seconds"),
    }
    texto = json.dumps(registro, ensure_ascii=False, indent=2, default=_json_padrao)
    (pasta / f"{base}.json").write_text(texto, encoding="utf-8")
    return csv


def executar(
    versao: str,
    ate: date | None,
    proximo: date | None,
    pasta: Path,
    ler: Callable[..., pd.DataFrame] | None = None,
    existe_composicao: bool | None = None,
) -> Path:
    """Lê a coleta, monta o dataset e grava em `pasta`. Devolve o caminho do CSV.

    `ate` é o último pregão: filtra preços (e portanto `cal`) e balanços. `proximo` é o próximo
    pregão: as notícias são cortadas em `corte_manha(proximo)` e a noite do último pregão fecha.
    Sem `proximo`, a noite do último pregão fica aberta e as notícias não são cortadas.
    `ler` injetado (testes) pula a conexão e a checagem READ ONLY.
    """
    if versao not in VERSOES:
        raise ValueError(f"versão desconhecida: {versao!r}")
    if ler is None:
        ler = _leitor_padrao()
    precos = fontes.ler_tabela("precos", ate=ate, ler=ler)
    cal = calendario.pregoes(precos)
    if proximo is not None and cal and proximo <= cal[-1]:
        raise ValueError("--proximo precisa ser depois do último pregão do dataset")
    params = carregar_parametros_experimento()
    params_precos = carregar_parametros_precos()
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    composicao = fontes.ler_composicao(ler=ler, existe=existe_composicao)
    dados = DadosExperimento(
        precos=precos,
        cadastro=cadastro,
        noticias=fontes.ler_noticias(
            ate=calendario.corte_manha(proximo) if proximo is not None else None, ler=ler
        ),
        balancos=fontes.ler_tabela("balancos", ate=ate, ler=ler),
        universo=montar_universo(cal, cadastro, precos, carregar_exclusoes(), composicao),
        mudancas=fontes.ler_mudancas(ler),
    )
    df, info = montar_dataset(
        dados,
        cal,
        versao_noticias=versao,
        proximo_ao_vivo=proximo,
        params=params,
        params_precos=params_precos,
    )
    info = {
        **info,
        "parametros": {"experimento": asdict(params), "precos": asdict(params_precos)},
    }
    return salvar_dataset(df, info, pasta)


def main(argv=None, ler=None) -> int:
    """Ponto de entrada (`python -m processamento.experimento.dataset`). Devolve 0 em sucesso,
    2 se a configuração do banco estiver incompleta e 3 se a sessão não estiver em somente
    leitura ou a conexão falhar (nada é gravado nesses casos).
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.experimento.dataset",
        description="Monta e grava o dataset do experimento. Só lê o banco da coleta.",
    )
    parser.add_argument(
        "--versao", choices=VERSOES, default="todas", help="notícias: todas, principais ou hora_real_noite"
    )
    parser.add_argument("--ate", type=_data_argumento, default=None, help="último pregão do dataset (AAAA-MM-DD)")
    parser.add_argument(
        "--proximo", type=_data_argumento, default=None,
        help="próximo pregão: fecha a noite do último pregão (AAAA-MM-DD)",
    )
    parser.add_argument("--pasta", type=Path, default=PASTA_PADRAO, help="pasta de saída (padrão: saida/experimento)")
    args = parser.parse_args(argv)

    if ler is None:
        try:
            ler = _leitor_padrao()
        except fontes.ErroConfiguracao as e:
            print(f"Configuração do banco incompleta: {e}")
            return 2
        except fontes.ErroSomenteLeitura as e:
            print(f"{e}. Nada foi gravado.")
            return 3
        except Exception as e:
            # Não mostra a mensagem original: ela pode conter host ou usuário.
            print(f"Falha ao conectar ao banco ({type(e).__name__}). Nada foi gravado.")
            return 3

    caminho = executar(args.versao, args.ate, args.proximo, args.pasta, ler=ler)
    print(f"Dataset gravado: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
