"""Treino e avaliação do experimento (plano da etapa 6, fases 6a e 6c).

Lê só os CSV do dataset (conferidos pelo sha256 do JSON ao lado) e não acessa o banco. O teste final
sai logo na leitura (`ler_desenvolvimento`, e `ler_teste_final` no teste final): nenhuma data depois
do fim do período sai daqui. A trava do teste final (`conferir_trava`) fica antes de qualquer leitura.

Ausência é NaN/None, nunca 0. Semente fixa vem de `params.semente` (modelos e bootstrap).
Uso: `python -m processamento.experimento.treino [--data AAAA-MM-DD] [--teste-final]`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
from datetime import date, datetime
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb

from processamento import fontes
from processamento.experimento import avaliacao, modelos, preparacao, previsao, relatorio, validacao
from processamento.experimento.parametros import ParametrosTreino, carregar_parametros_treino

MODELOS_AVALIADOS = ("modelo_1", "modelo_3", "logistica", "volatilidade", "modelo_3_principais", "modelo_3_hora_real_noite")
TIPOS_DATASET = ("todas", "principais", "hora_real_noite")
_RE_NOME_CSV = re.compile(r"^dataset-(todas|principais|hora_real_noite)-(\d{4}-\d{2}-\d{2})\.csv$")
_TIPOS_MODELO = ("xgb", "lgbm", "logistica", "volatilidade")
_COLUNAS_TEXTO = {"ticker": str, "empresa": str, "setor": str, "universo": str}
COLUNAS_PREVISAO = [
    "data", "ticker", "dobra", "score", "alvo", "alvo_abertura", "alvo_abertura_valido",
    "ret_t1", "ret_ibov_t1", "dia_resultado",
]


class ErroDataset(Exception):
    """Dataset ausente, alterado depois de gravado ou sem as colunas da versão atual."""


def _regenere(versao: str) -> str:
    return f"regenere o dataset: python -m processamento.experimento.dataset --versao {versao}"


def localizar_datasets(pasta: Path, data: date | None) -> dict[str, Path | None]:
    """CSV de cada versão. "todas" é obrigatória (a de maior data, ou a de `data`); "principais" e
    "hora_real_noite" saem com a MESMA data, ou None se não existirem."""
    pasta = Path(pasta)
    achados: dict[str, dict[date, Path]] = {versao: {} for versao in TIPOS_DATASET}
    if pasta.is_dir():
        for arquivo in pasta.iterdir():
            casamento = _RE_NOME_CSV.match(arquivo.name)
            if casamento:
                achados[casamento.group(1)][date.fromisoformat(casamento.group(2))] = arquivo
    todas = achados["todas"]
    if data is None:
        if not todas:
            raise ErroDataset(f"não achei dataset-todas-*.csv em {pasta}; {_regenere('todas')}")
        data = max(todas)
    if data not in todas:
        raise ErroDataset(f"não achei dataset-todas-{data:%Y-%m-%d}.csv em {pasta}; {_regenere('todas')}")
    return {
        "todas": todas[data],
        "principais": achados["principais"].get(data),
        "hora_real_noite": achados["hora_real_noite"].get(data),
    }


def _inicio_experimento(valor: str, info: dict) -> date | None:
    """`treino.inicio_experimento`: "cobertura" = cobertura_inicio do JSON; senão a data dada."""
    if valor == "cobertura":
        cobertura = info.get("cobertura_inicio")
        return None if cobertura in (None, "") else pd.Timestamp(cobertura).date()
    return date.fromisoformat(valor)


def _carregar_csv(csv: Path) -> tuple[pd.DataFrame, dict]:
    """CSV inteiro (datas lidas) com o JSON ao lado. Confere o sha256 e a coluna `alvo_abertura_valido`.

    Sem a coluna, ou com outra `versao_preparacao`, o dataset é antigo: ErroDataset com o comando de regeração.
    """
    csv = Path(csv)
    caminho_json = csv.with_suffix(".json")
    if not caminho_json.is_file():
        raise ErroDataset(f"falta o JSON ao lado do CSV ({caminho_json.name}); {_regenere('todas')}")
    info = json.loads(caminho_json.read_text(encoding="utf-8"))
    if modelos.sha256_arquivo(csv) != info.get("sha256"):
        raise ErroDataset(f"o sha256 de {csv.name} não bate com o JSON ao lado: o CSV mudou depois de gravado")

    df = pd.read_csv(csv, dtype=_COLUNAS_TEXTO, encoding="utf-8")
    df["data"] = pd.to_datetime(df["data"], format="%Y-%m-%d")
    versao = info.get("versao_noticias", "<v>")
    if "alvo_abertura_valido" not in df.columns:
        raise ErroDataset(f"o dataset {csv.name} não tem a coluna alvo_abertura_valido; {_regenere(versao)}")
    if info.get("versao_preparacao") != preparacao.VERSAO_PREPARACAO:
        raise ErroDataset(
            f"o dataset {csv.name} é da versão de preparação {info.get('versao_preparacao')}, e a atual é "
            f"{preparacao.VERSAO_PREPARACAO}; {_regenere(versao)}"
        )
    return df, info


def ler_desenvolvimento(csv: Path, params: ParametrosTreino) -> tuple[pd.DataFrame, dict]:
    """Período de desenvolvimento do CSV, com o JSON ao lado (`info`).

    Confere o sha256 dos bytes do CSV contra o JSON. Logo após a leitura tira o teste final e o
    pregão de embargo antes dele; depois aplica o início do experimento. Sem `alvo_abertura_valido`
    o dataset é antigo: ErroDataset com o comando de regeração.
    """
    df, info = _carregar_csv(csv)
    df = validacao.periodo_desenvolvimento(df, params.teste_final_inicio, params.embargo_pregoes)
    df = validacao.aplicar_inicio(df, _inicio_experimento(params.inicio_experimento, info))
    return df, info


def preparar_dev(df: pd.DataFrame) -> tuple[pd.DataFrame, list[date]]:
    """Linhas de treino (com alvo, ranks por pregão) e o calendário de desenvolvimento (datas distintas de `df`)."""
    cal = sorted({pd.Timestamp(d).date() for d in df["data"]})
    return preparacao.linhas_de_treino(preparacao.preparar(df)), cal


def prever_walk_forward(prep, dobras, colunas, tipo: str, params: ParametrosTreino, hiper: dict | None = None) -> pd.DataFrame:
    """Score de cada linha de teste com alvo, dobra a dobra. `tipo`: "xgb", "lgbm", "logistica" ou "volatilidade".

    `hiper` é o dicionário do XGBoost (padrão: `params.xgboost`). A regra da volatilidade não treina,
    mas usa as mesmas linhas das outras, para que todos os modelos avaliem o mesmo conjunto.
    """
    if tipo not in _TIPOS_MODELO:
        raise ValueError(f"tipo de modelo desconhecido: {tipo!r} (use {', '.join(_TIPOS_MODELO)})")
    hiper = dict(params.xgboost) if hiper is None else hiper
    partes = []
    for dobra in dobras:
        treino, teste = validacao.linhas_da_dobra(prep, dobra)
        if teste.empty:
            continue
        if tipo == "xgb":
            ajuste = modelos.treinar_xgb(treino[colunas], treino["alvo"], hiper, params.semente)
            score = modelos.prob_xgb(ajuste, teste[colunas])
        elif tipo == "lgbm":
            ajuste = modelos.treinar_lgbm(treino[colunas], treino["alvo"], hiper, params.semente)
            score = modelos.prob_lgbm(ajuste, teste[colunas])
        elif tipo == "logistica":
            ajuste = modelos.treinar_logistica(treino[colunas], treino["alvo"], params.logistica_c, params.semente)
            score = modelos.prob_logistica(ajuste, teste[colunas])
        else:
            score = modelos.score_volatilidade(teste)
        partes.append(pd.DataFrame({
            "data": teste["data"].to_numpy(),
            "ticker": teste["ticker"].to_numpy(),
            "dobra": dobra.numero,
            "score": np.asarray(score, dtype=float),
            "alvo": teste["alvo"].to_numpy(),
            "alvo_abertura": teste["alvo_abertura"].to_numpy(),
            "alvo_abertura_valido": teste["alvo_abertura_valido"].to_numpy(),
            "ret_t1": teste["ret_t1"].to_numpy(),
            "ret_ibov_t1": teste["ret_ibov_t1"].to_numpy(),
            "dia_resultado": teste["dia_resultado"].to_numpy(),
        }))
    if not partes:
        return pd.DataFrame(columns=COLUNAS_PREVISAO)
    return pd.concat(partes, ignore_index=True)


def auc_medio_wf(pred: pd.DataFrame) -> float | None:
    """Média do AUC por pregão das previsões (None se não houver pregão com as duas classes)."""
    aucs = avaliacao.auc_por_pregao(pred)
    return float(aucs.mean()) if len(aucs) else None


def _ganho_aceito(candidato: float | None, atual: float | None, minimo: float) -> bool:
    """Aceita se o AUC com o bloco passar do AUC sem ele em mais que `minimo`. Sem AUC, não aceita."""
    if candidato is None or atual is None:
        return False
    return (candidato - atual) > minimo


def selecionar_blocos(prep, dobras, params: ParametrosTreino, prever=None) -> dict:
    """Seleção dos blocos (F6): preco_contexto e macro no modelo 1, noticias_contexto no modelo 3.

    Usa os hiperparâmetros do yaml. Não testa o extremo em rank nem a grade. `prever` troca
    `prever_walk_forward` (mesma assinatura), para o protocolo reaproveitar as previsões.
    """
    prever = prever_walk_forward if prever is None else prever   # resolvido aqui: os testes trocam o nome do módulo

    def auc_de(colunas: list[str]) -> float | None:
        return auc_medio_wf(prever(prep, dobras, colunas, "xgb", params, None))

    tentativas: list[dict] = []
    blocos: list[str] = []
    atual = auc_de(preparacao.colunas_do_modelo("1", ()))
    for bloco in ("preco_contexto", "macro"):
        candidato = auc_de(preparacao.colunas_do_modelo("1", tuple(blocos + [bloco])))
        aceito = _ganho_aceito(candidato, atual, params.ganho_minimo_bloco)
        tentativas.append({"etapa": "modelo_1", "descricao": f"bloco {bloco}", "auc_medio": candidato, "aceito": aceito})
        if aceito:
            blocos.append(bloco)
            atual = candidato

    atual = auc_de(preparacao.colunas_do_modelo("3", tuple(blocos)))
    candidato = auc_de(preparacao.colunas_do_modelo("3", tuple(blocos) + ("noticias_contexto",)))
    noticias_contexto = _ganho_aceito(candidato, atual, params.ganho_minimo_bloco)
    tentativas.append({
        "etapa": "modelo_3", "descricao": "bloco noticias_contexto", "auc_medio": candidato, "aceito": noticias_contexto,
    })
    return {
        "blocos": list(blocos),
        "noticias_contexto": bool(noticias_contexto),
        "tentativas": tentativas,
        "auc_3": candidato if noticias_contexto else atual,
    }


def selecionar_configuracao(prep, dobras, params: ParametrosTreino) -> tuple[dict, pd.DataFrame]:
    """Blocos, bloco de notícias, extremo em rank e hiperparâmetros, só com as dobras de desenvolvimento.

    1) blocos de preço no modelo 1, em ordem; 2) "noticias_contexto" no modelo 3; 3) `noticias_dia_extremo` em rank
    no modelo 3, pela mesma regra de ganho; 4) grade no modelo 3 final (o maior AUC médio; empate fica com o
    primeiro). Devolve (configuração, tabela de tentativas).
    """
    sel = selecionar_blocos(prep, dobras, params)
    tentativas: list[dict] = sel["tentativas"]

    def auc_de(colunas: list[str], hiper: dict | None = None) -> float | None:
        return auc_medio_wf(prever_walk_forward(prep, dobras, colunas, "xgb", params, hiper))

    blocos = sel["blocos"]
    noticias_contexto = sel["noticias_contexto"]
    atual = sel["auc_3"]

    blocos_3 = tuple(blocos) + (("noticias_contexto",) if noticias_contexto else ())
    colunas_1 = preparacao.colunas_do_modelo("1", tuple(blocos))
    colunas_3 = preparacao.colunas_do_modelo("3", blocos_3)

    com_rank = [preparacao.EXTREMO_RANK if c == "noticias_dia_extremo" else c for c in colunas_3]
    candidato = auc_de(com_rank)
    extremo_em_rank = _ganho_aceito(candidato, atual, params.ganho_minimo_bloco)
    tentativas.append({
        "etapa": "modelo_3", "descricao": "noticias_dia_extremo em rank", "auc_medio": candidato,
        "aceito": extremo_em_rank,
    })
    if extremo_em_rank:
        colunas_3 = com_rank

    chaves = list(params.grade)
    melhor: tuple[float, dict, int] | None = None
    for valores in itertools.product(*(params.grade[c] for c in chaves)):
        mudancas = dict(zip(chaves, valores))
        hiper = {**params.xgboost, **mudancas}
        auc = auc_de(colunas_3, hiper)
        descricao = ", ".join(f"{c}={v}" for c, v in mudancas.items()) or "padrão do yaml"
        tentativas.append({"etapa": "grade", "descricao": descricao, "auc_medio": auc, "aceito": False})
        if auc is not None and (melhor is None or auc > melhor[0]):
            melhor = (auc, hiper, len(tentativas) - 1)
    if melhor is None:
        raise ValueError("nenhuma configuração da grade tem AUC médio calculável nas dobras de desenvolvimento")
    tentativas[melhor[2]]["aceito"] = True

    configuracao = {
        "blocos_preco": list(blocos),
        "noticias_contexto": bool(noticias_contexto),
        "extremo_em_rank": bool(extremo_em_rank),
        "hiperparametros": dict(melhor[1]),
        "colunas_1": colunas_1,
        "colunas_3": colunas_3,
    }
    return configuracao, pd.DataFrame(tentativas, columns=["etapa", "descricao", "auc_medio", "aceito"])


def _vs_acaso(taxa: float | None, faixa: dict) -> str | None:
    if taxa is None or faixa.get("p97_5") is None:
        return None
    return avaliacao.comparar_com_acaso(taxa, faixa)


def _fracao_acima(taxa: float | None, faixa: dict) -> float | None:
    """Fração dos sorteios do acaso com taxa maior ou igual à do modelo."""
    dist = faixa.get("distribuicao_acerto")
    if taxa is None or dist is None or len(dist) == 0:
        return None
    return float(np.mean(np.asarray(dist) >= taxa))


def _bloco_topk(diario: pd.DataFrame, params: ParametrosTreino, faixa: dict) -> dict:
    m = avaliacao.metricas_periodo(diario)
    taxa = m["taxa_acerto"]
    ic_taxa = avaliacao.ic_bootstrap_blocos(
        diario["acerto_top"], params.bootstrap_bloco_pregoes, params.bootstrap_reamostragens, params.semente
    )
    ic_excesso = avaliacao.ic_bootstrap_blocos(
        diario["excesso_top"], params.bootstrap_bloco_pregoes, params.bootstrap_reamostragens, params.semente
    )
    return {
        "n_dias": m["n_dias"],
        "taxa_acerto": taxa,
        "ic_taxa": list(ic_taxa),
        "excesso_medio": m["excesso_medio"],
        "ic_excesso": list(ic_excesso),
        "taxa_ultimos": m["taxa_ultimos"],
        "excesso_ultimos": m["excesso_ultimos"],
        "dif_top_ultimos": m["dif_top_ultimos"],
        "vs_acaso": _vs_acaso(taxa, faixa),
        "fracao_acaso_maior_ou_igual": _fracao_acima(taxa, faixa),
    }


def _bloco_abertura(pred: pd.DataFrame, params: ParametrosTreino, faixas: dict) -> dict:
    """Alvo da abertura do IBOV, só nos pregões válidos (pegadinha 16)."""
    valida = avaliacao.linhas_abertura_valida(pred)
    topk = {}
    for k in params.topk:
        diario = avaliacao.resumo_diario(valida, k, coluna_alvo="alvo_abertura", com_retorno=False)
        m = avaliacao.metricas_periodo(diario, com_retorno=False)
        topk[str(k)] = {
            "n_dias": m["n_dias"],
            "taxa_acerto": m["taxa_acerto"],
            "vs_acaso": _vs_acaso(m["taxa_acerto"], faixas[str(k)]),
        }
    return {
        "n_dias_validos": int(valida["data"].nunique()),
        "n_dias_total": int(pred["data"].nunique()),
        "auc_geral": avaliacao.auc_geral(valida, coluna_alvo="alvo_abertura"),
        "topk": topk,
    }


def _valor_do_ano(tabela: pd.DataFrame, ano: int, coluna: str) -> float | None:
    if ano not in tabela.index:
        return None
    valor = tabela.loc[ano, coluna]
    return None if pd.isna(valor) else float(valor)


def _por_ano(diarios: dict[int, pd.DataFrame], params: ParametrosTreino) -> list[dict]:
    """Uma linha por ano do top principal (o primeiro de `topk`), com a taxa de cada top e o excesso do principal."""
    principal = params.topk[0]
    tabelas = {k: avaliacao.por_ano(diarios[k]).set_index("ano") for k in params.topk}
    base = tabelas[principal]
    linhas = []
    for ano in base.index:
        linha = {"ano": int(ano), "n_dias": int(base.loc[ano, "n_dias"])}
        for k in params.topk:
            linha[f"taxa_acerto_{k}"] = _valor_do_ano(tabelas[k], ano, "taxa_acerto")
            if k == principal:
                linha[f"excesso_{k}"] = _valor_do_ano(tabelas[k], ano, "excesso_medio")
        linhas.append(linha)
    return linhas


def avaliar(pred: pd.DataFrame, params: ParametrosTreino, acaso: dict, *, colunas: list[str] | None = None) -> dict:
    """Bloco `modelos.<nome>` do esquema de `metricas.json`.

    `acaso` é o retorno de `calcular_acaso` (com as distribuições, que não vão para o JSON). `colunas`
    é só registrado no bloco (opcional).
    """
    principal = params.topk[0]
    diarios: dict[int, pd.DataFrame] = {}
    topk: dict[str, dict] = {}
    for k in params.topk:
        diarios[k] = avaliacao.resumo_diario(pred, k)
        topk[str(k)] = _bloco_topk(diarios[k], params, acaso[str(k)])
    return {
        "colunas": list(colunas) if colunas is not None else None,
        "auc_geral": avaliacao.auc_geral(pred),
        "auc_medio_pregao": auc_medio_wf(pred),
        "n_dias_auc": int(len(avaliacao.auc_por_pregao(pred))),
        "topk": topk,
        "abertura": _bloco_abertura(pred, params, acaso["abertura"]),
        "por_ano": _por_ano(diarios, params),
        "sensibilidade": avaliacao.sensibilidade_ultimo_ano(diarios[principal]),
    }


def calcular_acaso(pred_ref: pd.DataFrame, params: ParametrosTreino) -> dict:
    """Faixa do acaso de cada top (`str(k)`) e da abertura (`"abertura"`, nos dias válidos).

    É uma só para todos os modelos, porque as linhas candidatas são as mesmas. Os arrays
    `distribuicao_*` vêm junto: quem grava o JSON deve tirá-los.
    """
    saida: dict = {}
    for k in params.topk:
        saida[str(k)] = avaliacao.faixa_do_acaso(pred_ref, k, params.acaso_sorteios, params.semente)
    valida = avaliacao.linhas_abertura_valida(pred_ref)
    saida["abertura"] = {
        str(k): avaliacao.faixa_do_acaso(
            valida, k, params.acaso_sorteios, params.semente, coluna_alvo="alvo_abertura", com_retorno=False
        )
        for k in params.topk
    }
    return saida


# ---------------------------------------------------------------------------
# Fase 6c: trava do teste final, execução, gravação e `main` (plano da etapa 6)
# ---------------------------------------------------------------------------

REGISTRO_TESTE_FINAL = fontes.RAIZ / "docs" / "teste_final_usado.json"
PASTA_DATASETS_PADRAO = fontes.RAIZ / "saida" / "experimento"
PASTA_SAIDA_PADRAO = PASTA_DATASETS_PADRAO / "treino"
PASTA_MODELOS_PADRAO = fontes.RAIZ / "modelos"
AVISO_PROVISORIO = "modelo provisório (treino.modelo_oficial: false): só teste de funcionamento"
MODELO_CALIBRADO = "modelo_3"
_EXTRAS = (("modelo_3_principais", "principais"), ("modelo_3_hora_real_noite", "hora_real_noite"))
_COLUNAS_TENTATIVA = ["etapa", "descricao", "auc_medio", "aceito"]
_COLUNAS_PREVISAO_CSV = [
    "data", "ticker", "modelo", "dobra", "score", "alvo", "alvo_abertura", "alvo_abertura_valido",
    "ret_t1", "ret_ibov_t1", "dia_resultado",
]
_COLUNAS_DIARIO_CSV = [
    "data", "modelo", "k", "n_candidatos", "acertos_top", "acerto_top", "acertos_ultimos", "acerto_ultimos",
    "ret_top", "ret_ultimos", "ret_ibov", "excesso_top", "excesso_ultimos",
]
_CHAVES_FORA_DO_INFO = ("parametros", "gerado_em", "arquivo", "sha256", "linhas", "cobertura_inicio")


class ErroTravaTesteFinal(Exception):
    """Pedido de teste final sem as condições da trava (fim, liberado ou registro de uso único)."""


class ErroPreRequisito(Exception):
    """Falta um passo anterior, como o treino de desenvolvimento antes do teste final."""


def conferir_trava(pedido: bool, liberado: bool, fim: date | None, registro: Path) -> None:
    """Teste final só roda com `fim` preenchido, `liberado: true` e sem registro de uso (uso único)."""
    if not pedido:
        return
    if fim is None:
        raise ErroTravaTesteFinal(
            "teste final travado: treino.teste_final.fim vazio (fixado na etapa 8, véspera da produção)"
        )
    if not liberado:
        raise ErroTravaTesteFinal("teste final travado: treino.teste_final.liberado = false")
    if Path(registro).exists():
        raise ErroTravaTesteFinal(f"o teste final já foi usado (ver {registro}); uso único")


def _iso(valor) -> str | None:
    """Data em AAAA-MM-DD (None e NaT viram None)."""
    if valor is None or valor is pd.NaT:
        return None
    return pd.Timestamp(valor).strftime("%Y-%m-%d")


def _agora() -> str:
    return datetime.now(fontes.SP).isoformat(timespec="seconds")


def _para_json(valor):
    """Tipos do numpy e do pandas viram tipos JSON; NaN e infinito viram None; datas viram AAAA-MM-DD."""
    if valor is None or valor is pd.NaT:
        return None
    if isinstance(valor, dict):
        return {str(k): _para_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_para_json(v) for v in valor]
    if isinstance(valor, np.ndarray):
        return [_para_json(v) for v in valor.tolist()]
    if isinstance(valor, pd.DataFrame):
        return [_para_json(linha) for linha in valor.to_dict("records")]
    if isinstance(valor, (bool, np.bool_)):
        return bool(valor)
    if isinstance(valor, (int, np.integer)):
        return int(valor)
    if isinstance(valor, (float, np.floating)):
        real = float(valor)
        return None if math.isnan(real) or math.isinf(real) else real
    if isinstance(valor, date):
        return valor.strftime("%Y-%m-%d")
    return valor


def _sem_distribuicoes(acaso: dict) -> dict:
    """Faixas do acaso sem os arrays `distribuicao_*` (não vão para o JSON)."""
    return {
        k: _sem_distribuicoes(v) if isinstance(v, dict) else v
        for k, v in acaso.items()
        if not str(k).startswith("distribuicao_")
    }


def _versoes() -> dict:
    return {"xgboost": xgb.__version__, "sklearn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__}


def _data_do_arquivo(csv: Path) -> date:
    return date.fromisoformat(_RE_NOME_CSV.match(Path(csv).name).group(2))


def _data_argumento(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"data inválida (use AAAA-MM-DD): {texto}") from e


def _dev(df: pd.DataFrame, params: ParametrosTreino) -> pd.DataFrame:
    """Linhas do período de desenvolvimento (antes de `teste_final.inicio`)."""
    return df.loc[df["data"] < pd.Timestamp(params.teste_final_inicio)]


def ler_teste_final(csv: Path, params: ParametrosTreino, fim: date) -> tuple[pd.DataFrame, dict]:
    """Linhas do CSV cujo dia do alvo (t+1) é <= `fim`. A linha do próprio `fim` e as seguintes são o
    teste ao vivo: saem logo na leitura (seção 7.5).

    Não tira o pregão de embargo: a 1ª dobra do teste final já o deixa fora do treino (`dobras_teste_final`).
    """
    df, info = _carregar_csv(csv)
    df = validacao.linhas_com_alvo_ate(df, fim)
    df = validacao.aplicar_inicio(df, _inicio_experimento(params.inicio_experimento, info))
    return df, info


def _dobras(cal: list[date], params: ParametrosTreino, modo: str, fim: date | None) -> list[validacao.Dobra]:
    if modo == "teste_final":
        return validacao.dobras_teste_final(cal, params.teste_final_inicio, fim, params.embargo_pregoes)
    return validacao.dobras_walk_forward(cal, params.treino_minimo_meses, params.embargo_pregoes)


def _pares(pred: pd.DataFrame) -> set:
    """Pares (data, ticker) das previsões, com a data em texto."""
    return {(pd.Timestamp(d).strftime("%Y-%m-%d"), t) for d, t in zip(pred["data"], pred["ticker"])}


def _conferir_mesmas_linhas(referencia: pd.DataFrame, outro: pd.DataFrame, nome: str, tipo: str) -> None:
    """Um dataset extra tem de ter as mesmas linhas de teste (data × ticker) do dataset todas."""
    if _pares(referencia) != _pares(outro):
        raise ErroDataset(
            f"{nome}: o dataset {tipo} tem pregão × ticker diferente do dataset todas; {_regenere(tipo)}"
        )


def _no_recorte(pred: pd.DataFrame, recorte: pd.DataFrame) -> np.ndarray:
    """Linhas da previsão cujo par (data, ticker) está no recorte."""
    chaves = {(pd.Timestamp(d).strftime("%Y-%m-%d"), t) for d, t in zip(recorte["data"], recorte["ticker"])}
    return np.array(
        [(pd.Timestamp(d).strftime("%Y-%m-%d"), t) in chaves for d, t in zip(pred["data"], pred["ticker"])],
        dtype=bool,
    )


def _colunas_de(nome: str, cfg: dict) -> list[str]:
    if nome == "modelo_1":
        return cfg["colunas_1"]
    if nome == "volatilidade":
        return ["volatilidade_20d"]
    return cfg["colunas_3"]


def _serie(pred: pd.DataFrame, metrica: str, k: int) -> pd.Series:
    """Valor de cada dia para a comparação pareada: acerto do top k ou AUC do pregão."""
    if metrica == "acerto_top5_dia":
        return avaliacao.resumo_diario(pred, k).set_index("data")["acerto_top"]
    return avaliacao.auc_por_pregao(pred)


def _comparacoes(pred: dict, params: ParametrosTreino) -> list[dict]:
    """Diferenças pareadas por dia, com IC por bootstrap de blocos (modelo 3 contra os de referência)."""
    k = params.topk[0]
    pares = [("modelo_3", "modelo_1"), ("modelo_3", "logistica"), ("modelo_3", "volatilidade")]
    pares += [(nome, "modelo_3") for nome, _ in _EXTRAS if pred[nome] is not None]
    saida = []
    for a, b in pares:
        for metrica in ("acerto_top5_dia", "auc_dia"):
            dif = avaliacao.diferenca_pareada(_serie(pred[a], metrica, k), _serie(pred[b], metrica, k))
            ic = avaliacao.ic_bootstrap_blocos(
                dif.to_numpy(), params.bootstrap_bloco_pregoes, params.bootstrap_reamostragens, params.semente
            )
            saida.append({
                "a": a,
                "b": b,
                "metrica": metrica,
                "media_dif": float(dif.mean()) if len(dif) else None,
                "ic": list(ic),
                "n_dias": int(len(dif)),
            })
    return saida


def _modelo_3b(pred: dict, prep: pd.DataFrame) -> dict:
    """AUC do modelo 3 e do modelo 1 só nos dias de resultado (`preparacao.linhas_modelo_3b`) e fora deles."""
    recorte = preparacao.linhas_modelo_3b(prep)
    recorte = recorte.loc[recorte["alvo"].notna()]
    p3, p1 = pred["modelo_3"], pred["modelo_1"]
    m3 = _no_recorte(p3, recorte)
    m1 = _no_recorte(p1, recorte)
    return {
        "n_linhas": int(m3.sum()),
        "n_dias": int(p3.loc[m3, "data"].nunique()),
        "auc_modelo_3": avaliacao.auc_geral(p3.loc[m3]),
        "auc_modelo_1": avaliacao.auc_geral(p1.loc[m1]),
        "auc_modelo_3_fora": avaliacao.auc_geral(p3.loc[~m3]),
        "auc_modelo_1_fora": avaliacao.auc_geral(p1.loc[~m1]),
    }


def _supera(taxa: float | None, outra: float | None) -> bool:
    return taxa is not None and outra is not None and taxa > outra


def _veredito(modelos_bloco: dict) -> dict:
    """"Acima do acaso" só conta se o modelo 3 também superar a volatilidade e a logística no top 5."""
    top5 = modelos_bloco[MODELO_CALIBRADO]["topk"]["5"]
    situacao = top5["vs_acaso"]
    taxa = top5["taxa_acerto"]
    sup_vol = _supera(taxa, modelos_bloco["volatilidade"]["topk"]["5"]["taxa_acerto"])
    sup_log = _supera(taxa, modelos_bloco["logistica"]["topk"]["5"]["taxa_acerto"])
    if situacao == "acima" and sup_vol and sup_log:
        texto = "No top 5, o modelo 3 ficou acima do acaso e superou a regra da volatilidade e a logística neste período."
    elif situacao == "acima":
        faltam = [nome for nome, ok in (("a regra da volatilidade", sup_vol), ("a logística", sup_log)) if not ok]
        texto = "No top 5, o modelo 3 ficou acima do acaso, mas não superou " + " nem ".join(faltam) + "."
    elif situacao == "dentro":
        texto = "No top 5, o modelo 3 ainda não mostrou vantagem sobre o acaso."
    elif situacao == "abaixo":
        texto = "No top 5, o modelo 3 ficou abaixo do acaso."
    else:
        texto = "Sem dados suficientes para comparar o modelo 3 com o acaso."
    return {"acaso": situacao, "supera_volatilidade": sup_vol, "supera_logistica": sup_log, "texto": texto}


def _calibracao(p3: pd.DataFrame, params: ParametrosTreino) -> dict:
    calib = avaliacao.calibracao(
        p3["score"], p3["alvo"], params.calibracao_bins, params.calibracao_ece_maximo, params.calibracao_linhas_minimas
    )
    return {
        "ece": calib["ece"],
        "brier": calib["brier"],
        "n": calib["n"],
        "aprovada": calib["aprovada"],
        "chance_exibida": bool(calib["aprovada"] and params.liberar_chance),
        "tabela": calib["tabela"],
    }


def _exemplo_top(prep, df, dobras, cfg: dict, params: ParametrosTreino, aprovada: bool) -> dict | None:
    """Top do último dia de teste da última dobra, com o modelo treinado nessa dobra, e as sombras."""
    if not dobras:
        return None
    treino, teste = validacao.linhas_da_dobra(prep, dobras[-1])
    if teste.empty:
        return None
    dia = teste["data"].max()
    c1, c3, hiper = cfg["colunas_1"], cfg["colunas_3"], cfg["hiperparametros"]
    ajuste3 = modelos.treinar_xgb(treino[c3], treino["alvo"], hiper, params.semente)
    ajuste1 = modelos.treinar_xgb(treino[c1], treino["alvo"], hiper, params.semente)
    completo = preparacao.preparar(df)
    mascara = (df["data"] == dia).to_numpy()
    preparado_dia = completo.loc[mascara]
    bruto_dia = df.loc[mascara]
    k = params.topk[0]
    meta = {"colunas": c3, "calibracao": {"aprovada": aprovada}}
    return {
        "data": _iso(dia),
        "top": previsao.top_do_dia(preparado_dia, bruto_dia, ajuste3, meta, params),
        "sombra_modelo_1": previsao.top_sombra_modelo(preparado_dia, ajuste1, c1, k),
        "sombra_volatilidade": previsao.top_sombra_volatilidade(preparado_dia, k),
    }


def _avaliar(lidos: dict, params: ParametrosTreino, modo: str, fim: date | None, congelada: dict | None) -> dict:
    """Walk-forward, métricas, comparações, 3b, calibração e exemplo. Não grava nada."""
    df, _ = lidos["todas"]
    prep, cal = preparar_dev(df)
    dobras = _dobras(cal, params, modo, fim)
    if not dobras:
        raise ErroPreRequisito("não há dobras para avaliar (histórico curto para treino_minimo_meses)")
    if congelada is not None:      # teste final, ou desenvolvimento com --configuracao
        cfg, tentativas = congelada, pd.DataFrame(columns=_COLUNAS_TENTATIVA)
    elif modo == "desenvolvimento":
        cfg, tentativas = selecionar_configuracao(prep, dobras, params)
    else:
        raise ErroPreRequisito("teste final sem configuração congelada")
    hiper = cfg["hiperparametros"]
    c1, c3 = cfg["colunas_1"], cfg["colunas_3"]
    pred: dict[str, pd.DataFrame | None] = {
        "modelo_1": prever_walk_forward(prep, dobras, c1, "xgb", params, hiper),
        "modelo_3": prever_walk_forward(prep, dobras, c3, "xgb", params, hiper),
        "logistica": prever_walk_forward(prep, dobras, c3, "logistica", params),
        "volatilidade": prever_walk_forward(prep, dobras, c3, "volatilidade", params),
    }
    for nome, tipo in _EXTRAS:
        par = lidos[tipo]
        if par is None:
            pred[nome] = None
            continue
        prep_x, cal_x = preparar_dev(par[0])
        pred[nome] = prever_walk_forward(prep_x, _dobras(cal_x, params, modo, fim), c3, "xgb", params, hiper)
        _conferir_mesmas_linhas(pred["modelo_3"], pred[nome], nome, tipo)

    acaso = calcular_acaso(pred["modelo_3"], params)
    bloco = {
        nome: None if pred[nome] is None else avaliar(pred[nome], params, acaso, colunas=_colunas_de(nome, cfg))
        for nome in MODELOS_AVALIADOS
    }
    calib = _calibracao(pred["modelo_3"], params)
    return {
        "prep": prep,
        "dobras": dobras,
        "cfg": cfg,
        "tentativas": tentativas,
        "pred": pred,
        "acaso": acaso,
        "modelos": bloco,
        "comparacoes": _comparacoes(pred, params),
        "modelo_3b": _modelo_3b(pred, prep),
        "calibracao": calib,
        "veredito": _veredito(bloco),
        "exemplo": _exemplo_top(prep, df, dobras, cfg, params, calib["aprovada"]),
    }


def _bloco_dataset(par) -> dict | None:
    if par is None:
        return None
    _, info = par
    return {
        "arquivo": info.get("arquivo"),
        "sha256": info.get("sha256"),
        "linhas": info.get("linhas"),
        "cobertura_inicio": info.get("cobertura_inicio"),
        "info_noticias": {k: v for k, v in info.items() if k not in _CHAVES_FORA_DO_INFO},
    }


def _dobras_json(prep: pd.DataFrame, dobras) -> list[dict]:
    saida = []
    for d in dobras:
        treino, teste = validacao.linhas_da_dobra(prep, d)
        saida.append({
            "numero": d.numero,
            "mes_teste": d.mes_teste,
            "treino_inicio": _iso(d.datas_treino[0]),
            "treino_fim": _iso(d.datas_treino[-1]),
            "n_pregoes_treino": len(d.datas_treino),
            "n_pregoes_teste": len(d.datas_teste),
            "n_linhas_treino": len(treino),
            "n_linhas_teste": len(teste),
        })
    return saida


def _montar_metricas(res: dict, lidos: dict, params: ParametrosTreino, modo: str, modelo_salvo, gerado_em: str) -> dict:
    """Esquema do `metricas.json` (contrato com a fase 6b). Ainda sem a conversão para JSON."""
    df, _ = lidos["todas"]
    dev = _dev(df, params)
    inicio_dev, fim_dev = dev["data"].min(), dev["data"].max()
    universo = sorted({str(u) for u in dev["universo"].dropna()})
    aviso = True if modo == "desenvolvimento" else (fim_dev - inicio_dev).days < 3 * 365
    return {
        "modo": modo,
        "aviso_funcionamento": aviso,
        "gerado_em": gerado_em,
        "datasets": {nome: _bloco_dataset(lidos[nome]) for nome in TIPOS_DATASET},
        "periodo": {
            "inicio": _iso(inicio_dev),
            "fim": _iso(fim_dev),
            "n_pregoes": int(dev["data"].nunique()),
            "n_linhas": int((res["prep"]["data"] < pd.Timestamp(params.teste_final_inicio)).sum()),
            "n_tickers": int(dev["ticker"].nunique()),
            "universo": ", ".join(universo),
            "teste_final_inicio": _iso(params.teste_final_inicio),
            "teste_final_fim": _iso(params.teste_final_fim),
            "teste_final_usado": modo == "teste_final",
            "embargo_pregoes": params.embargo_pregoes,
        },
        "dobras": _dobras_json(res["prep"], res["dobras"]),
        "selecao": {
            "blocos_preco": res["cfg"]["blocos_preco"],
            "noticias_contexto": res["cfg"]["noticias_contexto"],
            "hiperparametros": res["cfg"]["hiperparametros"],
            "tentativas": res["tentativas"],
        },
        "acaso": _sem_distribuicoes(res["acaso"]),
        "modelos": res["modelos"],
        "comparacoes": res["comparacoes"],
        "veredito_modelo_3": res["veredito"],
        "modelo_3b": res["modelo_3b"],
        "calibracao": res["calibracao"],
        "exemplo_top": res["exemplo"],
        "modelo_salvo": modelo_salvo,
    }


def _metadados(modelo: str, colunas: list[str], res: dict, info: dict, params: ParametrosTreino,
               universo: list[str], gerado_em: str, bloco: dict, calibracao: dict | None) -> dict:
    """`.meta.json` de um modelo provisório, já em tipos JSON (traz todas as chaves de `CHAVES_METADADOS`)."""
    cfg, prep = res["cfg"], res["prep"]
    return _para_json({
        "modelo": modelo,
        "versao_preparacao": preparacao.VERSAO_PREPARACAO,
        "versao_noticias": info.get("versao_noticias", "todas"),
        "colunas": list(colunas),
        "blocos": {"blocos_preco": list(cfg["blocos_preco"]), "noticias_contexto": cfg["noticias_contexto"]},
        "hiperparametros": dict(cfg["hiperparametros"]),
        "semente": params.semente,
        "periodo_treino": {"inicio": _iso(prep["data"].min()), "fim": _iso(prep["data"].max())},
        "n_linhas_treino": len(prep),
        "dataset": {"arquivo": info.get("arquivo"), "sha256": info.get("sha256")},
        "universo": universo,
        "metricas_validacao": {
            "auc_geral": bloco["auc_geral"],
            "auc_medio_pregao": bloco["auc_medio_pregao"],
            "taxa_acerto_top5": bloco["topk"]["5"]["taxa_acerto"],
        },
        "calibracao": calibracao,
        "provisorio": not params.modelo_oficial,
        "aviso": AVISO_PROVISORIO if not params.modelo_oficial else None,
        "versoes": _versoes(),
        "gerado_em": gerado_em,
        "teste_final": {"inicio": _iso(params.teste_final_inicio), "fim": _iso(params.teste_final_fim), "usado": False},
    })


def _sem_gerado(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if k != "gerado_em"}


def _treinar_e_salvar(res: dict, params: ParametrosTreino, pasta_modelos: Path, info: dict, universo: list[str]) -> dict:
    """Modelo 3 e modelo 1 treinados em todas as linhas de desenvolvimento, marcados como provisórios."""
    prep, cfg = res["prep"], res["cfg"]
    hiper = cfg["hiperparametros"]
    mes = params.teste_final_inicio.strftime("%Y-%m")
    ajuste3 = modelos.treinar_xgb(prep[cfg["colunas_3"]], prep["alvo"], hiper, params.semente)
    ajuste1 = modelos.treinar_xgb(prep[cfg["colunas_1"]], prep["alvo"], hiper, params.semente)
    gerado = _agora()
    meta3 = _metadados("3", cfg["colunas_3"], res, info, params, universo, gerado,
                       res["modelos"][MODELO_CALIBRADO], res["calibracao"])
    meta1 = _metadados("1", cfg["colunas_1"], res, info, params, universo, gerado,
                       res["modelos"]["modelo_1"], None)
    nome3, nome1 = modelos.nome_modelo(mes, "3"), modelos.nome_modelo(mes, "1")
    modelos.salvar_modelo(ajuste3, meta3, pasta_modelos, nome3)
    modelos.salvar_modelo(ajuste1, meta1, pasta_modelos, nome1)
    return {
        "arquivo": f"{nome3}.json",
        "metadados": _sem_gerado(meta3),
        "arquivo_m1": f"{nome1}.json",
        "metadados_m1": _sem_gerado(meta1),
    }


def _ler_meta(pasta: Path, nome: str) -> dict:
    caminho = pasta / f"{nome}.meta.json"
    if not caminho.is_file():
        raise ErroPreRequisito(f"falta {caminho.name} em {pasta}: rode antes o treino de desenvolvimento")
    return json.loads(caminho.read_text(encoding="utf-8"))


def _configuracao_congelada(pasta_modelos: Path, params: ParametrosTreino) -> dict:
    """Colunas e hiperparâmetros dos `.meta.json` do desenvolvimento (o teste final não re-seleciona nada)."""
    mes = params.teste_final_inicio.strftime("%Y-%m")
    meta3 = _ler_meta(pasta_modelos, modelos.nome_modelo(mes, "3"))
    meta1 = _ler_meta(pasta_modelos, modelos.nome_modelo(mes, "1"))
    if not (modelos.preparacao_compativel(meta3) and modelos.preparacao_compativel(meta1)):
        raise ErroPreRequisito(
            f"os modelos de {mes} são de outra versão de preparação: rode antes o treino de desenvolvimento"
        )
    return {
        "blocos_preco": meta3["blocos"]["blocos_preco"],
        "noticias_contexto": meta3["blocos"]["noticias_contexto"],
        "hiperparametros": meta3["hiperparametros"],
        "colunas_1": meta1["colunas"],
        "colunas_3": meta3["colunas"],
    }


def _ler_configuracao(caminho: Path, sha256: str | None) -> dict:
    """Configuração congelada pelo protocolo ou pela busca (`docs/protocolo_congelado_rodada_NNN.json`),
    para o treino de desenvolvimento (`--configuracao`).

    Recusa outro dataset (sha256 diferente) e outra família que não XGBoost. Arquivo sem `familia` é do
    protocolo, que só congela XGBoost. Devolve as mesmas chaves de `_configuracao_congelada`.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroPreRequisito(f"configuração não encontrada: {caminho}")
    congelado = json.loads(caminho.read_text(encoding="utf-8"))
    if congelado.get("sha256_dataset") != sha256:
        raise ErroPreRequisito(f"a configuração {caminho.name} é de outro dataset (sha256 diferente)")
    familia = congelado.get("familia", "xgb")
    if familia != "xgb":
        raise ErroPreRequisito(f"família {familia!r} ainda não tem treino de desenvolvimento (só xgb)")
    chaves = ("blocos_preco", "noticias_contexto", "hiperparametros", "colunas_1", "colunas_3")
    faltam = [c for c in chaves if c not in congelado]
    if faltam:
        raise ErroPreRequisito(f"{caminho.name} não tem {', '.join(faltam)}")
    return {c: congelado[c] for c in chaves}


def _previsoes(pred: dict) -> pd.DataFrame:
    partes = [pred[nome].assign(modelo=nome) for nome in MODELOS_AVALIADOS if pred.get(nome) is not None]
    return pd.concat(partes, ignore_index=True)[_COLUNAS_PREVISAO_CSV]


def _diario(pred: dict, params: ParametrosTreino) -> pd.DataFrame:
    partes = []
    for nome in MODELOS_AVALIADOS:
        if pred.get(nome) is None:
            continue
        for k in params.topk:
            partes.append(avaliacao.resumo_diario(pred[nome], k).assign(modelo=nome, k=k))
    return pd.concat(partes, ignore_index=True)[_COLUNAS_DIARIO_CSV]


def _gravar_saidas(pasta: Path, metricas: dict, res: dict, params: ParametrosTreino) -> Path:
    """relatorio.md, metricas.json, previsoes.csv, diario.csv e selecao.csv. Devolve o caminho do relatório."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / "relatorio.md"
    caminho.write_text(relatorio.gerar_relatorio(metricas), encoding="utf-8")
    (pasta / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _previsoes(res["pred"]).to_csv(
        pasta / "previsoes.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8", lineterminator="\n"
    )
    _diario(res["pred"], params).to_csv(
        pasta / "diario.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8", lineterminator="\n"
    )
    res["tentativas"].to_csv(pasta / "selecao.csv", index=False, encoding="utf-8", lineterminator="\n")
    return caminho


def _gravar_registro(registro: Path, metricas: dict, pasta: Path, cfg: dict, sha256: str | None,
                     params: ParametrosTreino) -> None:
    """Registro de uso único do teste final (`docs/teste_final_usado.json`, versionado para auditoria)."""
    top5 = metricas["modelos"][MODELO_CALIBRADO]["topk"]["5"]
    faixa = metricas["acaso"]["5"]
    registro_json = {
        "usado_em": _agora(),
        "teste_final_inicio": _iso(params.teste_final_inicio),
        "teste_final_fim": _iso(params.teste_final_fim),
        "n_dias": top5["n_dias"],
        "sha256_dataset": sha256,
        "configuracao": _para_json(cfg),
        "relatorio": f"{Path(pasta).name}/relatorio.md",
        "resumo": {
            "taxa_top5_modelo_3": top5["taxa_acerto"],
            "vs_acaso": top5["vs_acaso"],
            "acaso_top5": {"media": faixa["media"], "p2_5": faixa["p2_5"], "p97_5": faixa["p97_5"]},
        },
    }
    Path(registro).parent.mkdir(parents=True, exist_ok=True)
    Path(registro).write_text(json.dumps(registro_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def executar(
    pasta_datasets: Path,
    pasta_saida: Path,
    pasta_modelos: Path,
    *,
    data: date | None = None,
    teste_final: bool = False,
    params: ParametrosTreino | None = None,
    registro: Path | None = None,
    configuracao: Path | None = None,
) -> Path:
    """Treino e avaliação; grava as saídas e devolve o caminho do relatório.

    Desenvolvimento (padrão): walk-forward no período de desenvolvimento, modelos provisórios em
    `pasta_modelos` e saídas em `pasta_saida/dev-<data>/`. Com `configuracao` (JSON congelado pelo protocolo
    ou pela busca), a configuração é a dele, sem seleção. Teste final (`teste_final=True`): só com a
    trava aberta; configuração congelada dos `.meta.json`; saídas em `pasta_saida/teste-final-<data>/`
    e o registro de uso único em `registro`. A trava é conferida antes de qualquer leitura ou gravação.
    """
    params = carregar_parametros_treino() if params is None else params
    registro = REGISTRO_TESTE_FINAL if registro is None else Path(registro)
    conferir_trava(teste_final, params.teste_final_liberado, params.teste_final_fim, registro)
    if teste_final and configuracao is not None:
        raise ErroPreRequisito("--configuracao não vale no teste final: a configuração vem dos .meta.json")
    arquivos = localizar_datasets(Path(pasta_datasets), data)
    data_dataset = _data_do_arquivo(arquivos["todas"])
    if teste_final:
        modo, fim = "teste_final", params.teste_final_fim
        congelada = _configuracao_congelada(Path(pasta_modelos), params)
        leitor = partial(ler_teste_final, params=params, fim=fim)
    else:
        modo, fim, congelada = "desenvolvimento", None, None
        leitor = partial(ler_desenvolvimento, params=params)

    lidos = {nome: None if arquivos[nome] is None else leitor(arquivos[nome]) for nome in TIPOS_DATASET}
    if modo == "desenvolvimento" and configuracao is not None:
        congelada = _ler_configuracao(configuracao, lidos["todas"][1].get("sha256"))
    res = _avaliar(lidos, params, modo, fim, congelada)
    df_todas, info_todas = lidos["todas"]
    universo = sorted({str(u) for u in _dev(df_todas, params)["universo"].dropna()})
    gerado = _agora()
    if modo == "desenvolvimento":
        pasta = Path(pasta_saida) / f"dev-{data_dataset:%Y-%m-%d}"
        modelo_salvo = _treinar_e_salvar(res, params, Path(pasta_modelos), info_todas, universo)
    else:
        pasta = Path(pasta_saida) / f"teste-final-{data_dataset:%Y-%m-%d}"
        modelo_salvo = None
    metricas = _para_json(_montar_metricas(res, lidos, params, modo, modelo_salvo, gerado))
    caminho = _gravar_saidas(pasta, metricas, res, params)
    if modo == "teste_final":
        _gravar_registro(registro, metricas, pasta, res["cfg"], info_todas.get("sha256"), params)
    return caminho


def main(argv=None, params: ParametrosTreino | None = None, registro: Path | None = None) -> int:
    """Ponto de entrada (`python -m processamento.experimento.treino`).

    Devolve 0 em sucesso; 2 se faltar dataset, o sha256 não bater, a coluna nova faltar ("regenere") ou
    faltar um passo anterior; 4 se a trava do teste final estiver fechada (nada é gravado).
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.experimento.treino",
        description="Treino e avaliação do experimento. Só lê os CSV do dataset (nada do banco).",
    )
    parser.add_argument("--data", type=_data_argumento, default=None,
                        help="data do dataset (AAAA-MM-DD); padrão: a mais recente")
    parser.add_argument("--pasta-datasets", type=Path, default=PASTA_DATASETS_PADRAO,
                        help="pasta dos CSV (padrão: saida/experimento)")
    parser.add_argument("--pasta-saida", type=Path, default=PASTA_SAIDA_PADRAO,
                        help="pasta das saídas (padrão: saida/experimento/treino)")
    parser.add_argument("--pasta-modelos", type=Path, default=PASTA_MODELOS_PADRAO,
                        help="pasta dos modelos (padrão: modelos)")
    parser.add_argument("--teste-final", action="store_true",
                        help="roda o teste final (uso único; exige a trava aberta)")
    parser.add_argument("--configuracao", type=Path, default=None,
                        help="JSON de configuração congelada (protocolo ou busca) para o desenvolvimento; "
                             "recusado no teste final")
    args = parser.parse_args(argv)
    try:
        caminho = executar(
            args.pasta_datasets,
            args.pasta_saida,
            args.pasta_modelos,
            data=args.data,
            teste_final=args.teste_final,
            params=params,
            registro=registro,
            configuracao=args.configuracao,
        )
    except ErroTravaTesteFinal as e:
        print(f"{e}. Nada foi gravado.")
        return 4
    except (ErroDataset, ErroPreRequisito) as e:
        print(f"{e}")
        return 2
    print(f"Relatório gravado: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
