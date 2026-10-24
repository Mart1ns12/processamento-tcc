"""Retreino mensal da rotina diária (seção 7 do plano da etapa 8; fase 6).

Em produção (`treino.teste_final.fim` preenchido) e enquanto não existir `xgb-AAAA-MM.json` do mês de D,
treina o modelo 3 e o modelo 1 só com os pregões antes do dia 1 do mês, menos o de embargo. Colunas, blocos
e hiperparâmetros vêm do desenvolvimento congelado (`treino._configuracao_congelada`), nunca re-escolhidos.

Só lê DataFrames: nada de banco, rede, `datetime.now()` ou relógio do sistema.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pandas as pd

from processamento.experimento import modelos, preparacao, treino
from processamento.experimento.parametros import ParametrosTreino
from processamento.saida import contrato


def _primeiro_dia(mes: str) -> date:
    return date.fromisoformat(f"{mes}-01")


def datas_de_treino(cal: list, mes: str, embargo: int) -> list[date]:
    """Pregões de `cal` antes do dia 1 de `mes` ("AAAA-MM"), menos os `embargo` últimos."""
    corte = _primeiro_dia(mes)
    datas = sorted({pd.Timestamp(d).date() for d in cal})
    antes = [d for d in datas if d < corte]
    return antes[: max(len(antes) - embargo, 0)]


def precisa_retreinar(pasta_modelos: Path, d: date, fim: date | None) -> bool:
    """Só com `fim` preenchido (produção). Retreina enquanto falta algum dos quatro arquivos do mês de D.

    Os quatro são o `xgb-AAAA-MM.json` (sinal de "pronto") com o `.meta.json`, e o `xgb-m1-AAAA-MM.json` com o
    `.meta.json`. Se a gravação caiu no meio, um deles falta e o retreino refaz o par inteiro.
    """
    if fim is None:
        return False
    pasta = Path(pasta_modelos)
    mes = f"{d.year:04d}-{d.month:02d}"
    faltam = []
    for modelo in ("3", "1"):
        nome = modelos.nome_modelo(mes, modelo)
        faltam.extend([pasta / f"{nome}.json", pasta / f"{nome}.meta.json"])
    return not all(arquivo.is_file() for arquivo in faltam)


def _sha256_linhas(prep: pd.DataFrame, colunas: list[str]) -> str:
    """SHA-256 do CSV das linhas de treino (data, ticker, colunas, alvo), com texto e fim de linha fixos."""
    tabela = prep[["data", "ticker", *colunas, "alvo"]].assign(
        data=pd.to_datetime(prep["data"]).dt.strftime("%Y-%m-%d")
    )
    return hashlib.sha256(tabela.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def _metadados_retreino(modelo: str, colunas: list[str], dev: dict, calibracao: dict | None, *,
                        congelada: dict, prep: pd.DataFrame, universo: list[str], sha: str, mes: str,
                        params: ParametrosTreino, gerado_em: str) -> dict:
    """`.meta.json` do retreino: todas as `CHAVES_METADADOS` mais `retreino`. Métricas são as do desenvolvimento."""
    provisorio = not params.modelo_oficial
    return treino._para_json({
        "modelo": modelo,
        "versao_noticias": "todas",
        "colunas": list(colunas),
        "blocos": {"blocos_preco": congelada["blocos_preco"], "noticias_contexto": congelada["noticias_contexto"]},
        "hiperparametros": dict(congelada["hiperparametros"]),
        "semente": params.semente,
        "periodo_treino": {"inicio": treino._iso(prep["data"].min()), "fim": treino._iso(prep["data"].max())},
        "n_linhas_treino": len(prep),
        "dataset": {"arquivo": None, "sha256": sha},
        "universo": universo,
        "metricas_validacao": {**dev["metricas_validacao"], "origem": "desenvolvimento"},
        "calibracao": calibracao,
        "provisorio": provisorio,
        "aviso": treino.AVISO_PROVISORIO if provisorio else None,
        "versoes": treino._versoes(),
        "gerado_em": gerado_em,
        "teste_final": {
            "inicio": treino._iso(params.teste_final_inicio),
            "fim": treino._iso(params.teste_final_fim),
            "usado": treino.REGISTRO_TESTE_FINAL.exists(),
        },
        "retreino": {
            "mes": mes,
            "configuracao_de": modelos.nome_modelo(params.teste_final_inicio.strftime("%Y-%m"), "3"),
            "corte_antes_de": _primeiro_dia(mes).isoformat(),
        },
    })


def retreinar_mes(df: pd.DataFrame, info: dict, cal: list, d: date, *, pasta_modelos: Path,
                  params: ParametrosTreino, agora) -> list[str]:
    """Treina e grava o modelo 1 e depois o modelo 3 do mês de `d` (o `.json` do 3 é o sinal de "pronto").

    Devolve a lista de avisos (vazia em sucesso). Não faz nada se `precisa_retreinar` for falso. Qualquer
    exceção sobe para o chamador, que a transforma em aviso. `cal` são as datas de pregão disponíveis.
    """
    pasta = Path(pasta_modelos)
    if not precisa_retreinar(pasta, d, params.teste_final_fim):
        return []
    mes = f"{d.year:04d}-{d.month:02d}"
    mes_dev = params.teste_final_inicio.strftime("%Y-%m")
    congelada = treino._configuracao_congelada(pasta, params)
    dev3 = treino._ler_meta(pasta, modelos.nome_modelo(mes_dev, "3"))
    dev1 = treino._ler_meta(pasta, modelos.nome_modelo(mes_dev, "1"))

    inicio = treino._inicio_experimento(params.inicio_experimento, info)
    datas = [x for x in datas_de_treino(cal, mes, params.embargo_pregoes) if inicio is None or x >= inicio]
    if not datas:
        raise treino.ErroPreRequisito(f"retreino de {mes}: nenhuma linha de treino antes de {mes}-01")
    no_treino = pd.to_datetime(df["data"]).dt.normalize().isin(pd.to_datetime(datas))
    prep = preparacao.linhas_de_treino(preparacao.preparar(df.loc[no_treino]))
    if prep.empty:
        raise treino.ErroPreRequisito(f"retreino de {mes}: nenhuma linha de treino antes de {mes}-01")

    hiper, semente = congelada["hiperparametros"], params.semente
    ajuste1 = modelos.treinar_xgb(prep[congelada["colunas_1"]], prep["alvo"], hiper, semente)
    ajuste3 = modelos.treinar_xgb(prep[congelada["colunas_3"]], prep["alvo"], hiper, semente)

    comum = {
        "congelada": congelada,
        "prep": prep,
        "universo": sorted({str(u) for u in prep["universo"].dropna()}),
        "sha": _sha256_linhas(prep, list(dict.fromkeys([*congelada["colunas_3"], *congelada["colunas_1"]]))),
        "mes": mes,
        "params": params,
        "gerado_em": contrato.data_hora_txt(agora),
    }
    meta1 = _metadados_retreino("1", congelada["colunas_1"], dev1, None, **comum)
    meta3 = _metadados_retreino("3", congelada["colunas_3"], dev3, dev3["calibracao"], **comum)
    modelos.salvar_modelo(ajuste1, meta1, pasta, modelos.nome_modelo(mes, "1"))
    modelos.salvar_modelo(ajuste3, meta3, pasta, modelos.nome_modelo(mes, "3"))
    return []
