"""Execução de uma rodada do protocolo de variáveis novas (docs/protocolo_variaveis.md, seções 4 e 5) e CLI.

Só lê o CSV do dataset de desenvolvimento (nunca o banco), não abre o teste final e não grava em modelos/.
Ordem da rodada: travas, leitura, conferências, abertura no registro (antes de treinar), testes, decisão,
arquivos novos e registro do fim. Falha no meio fica registrada como "falhou".

Comando: python -m processamento.experimento.protocolo_execucao --data AAAA-MM-DD --motivo "1ª rodada"
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

from processamento import fontes
from processamento.experimento import avaliacao, preparacao, protocolo, treino, validacao
from processamento.experimento import protocolo_registro as reg
from processamento.experimento.parametros import carregar_parametros_treino
from processamento.experimento.protocolo import LIMITES
from processamento.experimento.protocolo_relatorio import gerar_relatorio

PASTA_DOCS_PADRAO = fontes.RAIZ / "docs"
PASTA_SAIDA_PADRAO = treino.PASTA_DATASETS_PADRAO / "protocolo"
DOC_PROTOCOLO = "protocolo_variaveis.md"
ARQUIVO_REGISTRO = "protocolo_tentativas.jsonl"
PASTA_EXPERIMENTO = Path(__file__).resolve().parent
ARQUIVOS_CODIGO = (
    "treino.py", "validacao.py", "avaliacao.py", "modelos.py", "preparacao.py", "protocolo.py",
    "protocolo_execucao.py",
)


class ErroTravaProtocolo(Exception):
    """Trava do protocolo fechada: nada é lido nem gravado."""


class ErroProtocolo(Exception):
    """Pré-requisito ou conferência do protocolo que falhou (documento, período, colunas, arquivo já existente)."""


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _com_blocos(base: list[str], nomes: list[str]) -> list[str]:
    """Colunas da base mais as colunas dos blocos do protocolo, na ordem dada."""
    return list(base) + [coluna for nome in nomes for coluna in preparacao.BLOCOS_PROTOCOLO[nome]]


class PrevisoesEmCache:
    """Mesma assinatura de prever_walk_forward. Chave: (colunas, tipo, JSON do hiperparâmetro); None vira
    `params.xgboost`. `treinos` conta as chamadas que de fato foram ao previsor."""

    def __init__(self, previsor, params):
        self._previsor = previsor
        self._params = params
        self._cache: dict = {}
        self.treinos = 0

    def __call__(self, prep, dobras, colunas, tipo, params, hiper=None):
        hiper = dict(self._params.xgboost) if hiper is None else dict(hiper)
        chave = (tuple(colunas), tipo, json.dumps(hiper, sort_keys=True))
        if chave not in self._cache:
            self.treinos += 1
            self._cache[chave] = self._previsor(prep, dobras, list(colunas), tipo, params, hiper)
        return self._cache[chave]


def conferir_travas(params, registro_teste_final: Path) -> None:
    """Antes de qualquer leitura: teste final depois do limite do protocolo, ou já usado, recusam a rodada."""
    if params.teste_final_inicio > protocolo.DATA_LIMITE:
        raise ErroTravaProtocolo(
            f"início do teste final ({params.teste_final_inicio:%d/%m/%Y}) depois de {protocolo.DATA_LIMITE:%d/%m/%Y}"
        )
    if Path(registro_teste_final).exists():
        raise ErroTravaProtocolo(f"o teste final já foi usado (ver {registro_teste_final}); uso único")


def _conferir_documento(doc: Path) -> None:
    if not doc.is_file():
        raise ErroProtocolo(f"documento do protocolo ausente: {doc}")
    texto = doc.read_text(encoding="utf-8")
    if not all(f"## {n}." in texto for n in (3, 4, 5)):
        raise ErroProtocolo(f"{doc.name} não tem as seções 3 a 5 do protocolo")


def conferir_periodo(df: pd.DataFrame, dobras: list, params, lim: LimitesProtocolo) -> None:
    """Período de desenvolvimento: nada do teste final, anos das dobras iguais aos do protocolo."""
    if not dobras:
        raise ErroProtocolo("sem dobras de desenvolvimento")
    if pd.to_datetime(df["data"]).max().date() >= params.teste_final_inicio:
        raise ErroProtocolo("há dados a partir do início do teste final")
    if any(max(d.datas_teste) >= params.teste_final_inicio for d in dobras):
        raise ErroProtocolo("há dobra de teste a partir do início do teste final")
    anos = {d.year for dobra in dobras for d in dobra.datas_teste}
    if anos != set(lim.anos):
        raise ErroProtocolo(f"anos de teste das dobras {sorted(anos)} diferentes dos do protocolo {list(lim.anos)}")


def conferir_colunas(prep: pd.DataFrame) -> dict:
    """Coluna do protocolo sem nenhum valor no período: ErroProtocolo. Devolve a fração preenchida por ano."""
    anos = pd.to_datetime(prep["data"]).dt.year
    cobertura: dict[int, dict[str, float]] = {}
    for coluna in sum(preparacao.BLOCOS_PROTOCOLO.values(), []):
        if coluna not in prep.columns or prep[coluna].isna().all():
            raise ErroProtocolo(f"coluna do protocolo sem nenhum valor no período: {coluna}")
        for ano, fracao in prep[coluna].notna().groupby(anos).mean().items():
            cobertura.setdefault(int(ano), {})[coluna] = float(fracao)
    return cobertura


def _testar_conjunto(prep, dobras, previsor, hiper, params, lim, testes, aprovados, c1, p1, medir):
    """Conjunto dos blocos A a D aprovados (só com 2 ou mais). Devolve (registro do conjunto, aprovado ou None)."""
    if testes["controle"]["avaliacao"]["aprovado"]:
        return {"situacao": "nao_executado", "motivo": "controle aprovado: rodada inválida, o conjunto não roda",
                "blocos": [], "medidas": None, "avaliacao": None, "colunas": None}, None
    if len(aprovados) < 2:
        return {"situacao": "nao_se_aplica",
                "motivo": f"{len(aprovados)} bloco(s) aprovado(s); o conjunto só roda com 2 ou mais",
                "blocos": [], "medidas": None, "avaliacao": None, "colunas": None}, None
    colunas = _com_blocos(c1, aprovados)
    cand = previsor(prep, dobras, colunas, "xgb", params, hiper)
    medidas = medir(p1, cand, params.semente, lim)
    aval = protocolo.avaliar_criterios(medidas, False, lim)
    return {"situacao": "executado", "motivo": "2 ou mais blocos aprovados: conjunto contra o modelo 1",
            "blocos": list(aprovados), "medidas": medidas, "avaliacao": aval, "colunas": colunas}, aval["aprovado"]


def rodar_protocolo(prep, dobras, params, lim=LIMITES, prever=None, medir=protocolo.medir_comparacao) -> dict:
    """Passo 0, controle e blocos A a E, conjunto e os blocos adotados. Não grava nada.

    `previsoes` (no retorno) tem o par (base, candidato) de cada teste, para a tabela diária.
    """
    previsor = PrevisoesEmCache(treino.prever_walk_forward if prever is None else prever, params)
    sel = treino.selecionar_blocos(prep, dobras, params, prever=previsor)
    extras = ("noticias_contexto",) if sel["noticias_contexto"] else ()
    c1 = preparacao.colunas_do_modelo("1", tuple(sel["blocos"]))
    c3 = preparacao.colunas_do_modelo("3", tuple(sel["blocos"]) + extras)
    hiper = dict(params.xgboost)
    p1 = previsor(prep, dobras, c1, "xgb", params, hiper)
    p3 = previsor(prep, dobras, c3, "xgb", params, hiper)

    testes: dict[str, dict] = {}
    previsoes: dict[str, tuple] = {}
    for nome in protocolo.ORDEM_TESTES:
        e_bloco_e = nome == "bloco_e"
        colunas_base, pred_base = (c3, p3) if e_bloco_e else (c1, p1)
        cand = previsor(prep, dobras, _com_blocos(colunas_base, [nome]), "xgb", params, hiper)
        medidas = medir(pred_base, cand, params.semente, lim)
        aval = protocolo.avaliar_criterios(medidas, e_bloco_e, lim)
        testes[nome] = {"base": "modelo 3" if e_bloco_e else "modelo 1", "medidas": medidas, "avaliacao": aval}
        previsoes[nome] = (pred_base, cand)

    aprovados = [b for b in protocolo.BLOCOS_ADOTAVEIS if testes[b]["avaliacao"]["aprovado"]]
    ganhos = {b: testes[b]["medidas"]["ganho"] for b in protocolo.BLOCOS_ADOTAVEIS}
    conjunto, conjunto_aprovado = _testar_conjunto(
        prep, dobras, previsor, hiper, params, lim, testes, aprovados, c1, p1, medir
    )
    return {
        "passo_0": {"tentativas": sel["tentativas"], "colunas_modelo_1": c1, "colunas_modelo_3": c3,
                    "blocos": list(sel["blocos"]), "noticias_contexto": bool(sel["noticias_contexto"])},
        "testes": testes,
        "aprovados": aprovados,
        "conjunto": conjunto,
        "adotados": protocolo.decidir_conjunto(aprovados, ganhos, conjunto_aprovado),
        "previsoes": previsoes,
    }


def _ganho_diario(previsoes: dict, lim: LimitesProtocolo) -> str:
    """CSV da rodada: teste, data, ganho de AUC do pregão e diferença de acerto do top k (fração)."""
    partes = []
    for nome in protocolo.ORDEM_TESTES:
        base, cand = previsoes[nome]
        ganho = avaliacao.diferenca_pareada(avaliacao.auc_por_pregao(cand), avaliacao.auc_por_pregao(base))
        top_base = avaliacao.resumo_diario(base, lim.k_top).set_index("data")["acerto_top"]
        top_cand = avaliacao.resumo_diario(cand, lim.k_top).set_index("data")["acerto_top"]
        tabela = pd.concat(
            [ganho.rename("ganho_auc"), (top_cand - top_base).rename("dif_top")], axis=1
        ).sort_index()
        tabela.index = pd.to_datetime(tabela.index).strftime("%Y-%m-%d")
        tabela.insert(0, "teste", nome)
        partes.append(tabela.rename_axis("data").reset_index())
    return pd.concat(partes, ignore_index=True)[["teste", "data", "ganho_auc", "dif_top"]].to_csv(
        index=False, lineterminator="\n"
    )


def _gravar_novo(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "x", encoding="utf-8", newline="\n") as arq:
        arq.write(texto)


def _sha_resultado(rodada: dict) -> str:
    """sha256 do JSON de passo 0, medidas, critérios e decisão (sem horário): mesmas entradas, mesmo hash."""
    medidas = {nome: t["medidas"] for nome, t in rodada["testes"].items()}
    criterios = {nome: t["avaliacao"] for nome, t in rodada["testes"].items()}
    if rodada["conjunto"]["medidas"] is not None:
        medidas["conjunto"] = rodada["conjunto"]["medidas"]
        criterios["conjunto"] = rodada["conjunto"]["avaliacao"]
    decisao = {"status": rodada["status"], "motivos": rodada["motivos"], "adotados": rodada["adotados"],
               "bloco_e_aprovado": rodada["bloco_e_aprovado"]}
    base = {"passo_0": rodada["passo_0"], "medidas": medidas, "criterios": criterios, "decisao": decisao}
    return _sha(json.dumps(treino._para_json(base), sort_keys=True, ensure_ascii=False))


def _congelar(rodada: dict, params, n: int) -> dict:
    """Configuração congelada: só em rodada válida."""
    adotados = rodada["adotados"]
    colunas_1 = _com_blocos(rodada["passo_0"]["colunas_modelo_1"], adotados)
    colunas_3 = _com_blocos(rodada["passo_0"]["colunas_modelo_3"], adotados)
    return {
        "colunas_1": colunas_1,
        "colunas_3": colunas_3,
        "colunas_3e": _com_blocos(colunas_3, ["bloco_e"]) if rodada["bloco_e_aprovado"] else None,
        "hiperparametros": dict(params.xgboost),
        "extremo_em_rank": False,
        "blocos_preco": rodada["passo_0"]["blocos"],
        "noticias_contexto": rodada["passo_0"]["noticias_contexto"],
        "sha256_dataset": rodada["identificacao"]["sha256_dataset"],
        "rodada": n,
    }


def _montar_rodada(resultado: dict, decisao: dict, ident: dict, cobertura: dict, n: int, data: date,
                   motivo: str, params, anterior: dict | None) -> dict:
    rodada = dict(resultado)
    rodada.update(
        rodada=n, data_rodada=data.isoformat(), motivo=motivo, modelo_oficial=bool(params.modelo_oficial),
        status=decisao["status"], motivos=decisao["motivos"], adotados=decisao["adotados"],
        bloco_e_aprovado=decisao["bloco_e_aprovado"], identificacao=ident, cobertura=cobertura,
        n_testes=len(protocolo.ORDEM_TESTES) + (1 if resultado["conjunto"]["situacao"] == "executado" else 0),
        colunas_congeladas=None,
    )
    rodada["sha_resultado"] = _sha_resultado(rodada)
    rodada["repete_rodada"] = anterior["rodada"] if anterior else None
    rodada["reproduziu"] = (rodada["sha_resultado"] == anterior["sha_resultado"]) if anterior else None
    if decisao["status"] == "valida":
        rodada["colunas_congeladas"] = _congelar(rodada, params, n)
    return rodada


def _identificacao(df: pd.DataFrame, cal: list, dobras: list, info: dict, assinatura: dict, params) -> dict:
    datas = pd.to_datetime(df["data"]).dt.date
    return {
        "sha256_dataset": info["sha256"],
        "arquivo_dataset": assinatura["arquivo_dataset"],
        "versao_preparacao": info.get("versao_preparacao"),
        "periodo_ini": datas.min().isoformat(),
        "periodo_fim": datas.max().isoformat(),
        "n_pregoes": len(cal),
        "n_linhas": int(len(df)),
        "n_dobras": len(dobras),
        "semente": params.semente,
        "sha_parametros": assinatura["sha_parametros"],
        "sha_regras": assinatura["sha_regras"],
        "sha_codigo": assinatura["sha_codigo"],
        "versoes": treino._versoes(),
        "hiperparametros": dict(params.xgboost),
    }


def _assinatura(info: dict, csv: Path, params, lim, doc: Path) -> dict:
    return {
        "sha256_dataset": info["sha256"],
        "arquivo_dataset": csv.name,
        "versao_preparacao": info.get("versao_preparacao"),
        "sha_parametros": reg.sha_parametros(params),
        "sha_regras": reg.sha_regras(doc, lim),
        "sha_codigo": reg.sha_codigo([PASTA_EXPERIMENTO / a for a in ARQUIVOS_CODIGO]),
        "semente": params.semente,
    }


def executar(pasta_datasets, pasta_docs, pasta_saida, *, data: date, motivo: str, params=None, lim=LIMITES,
             doc_protocolo=None, registro_teste_final=None) -> tuple[Path, str]:
    """Roda uma rodada e grava relatório, JSON, configuração congelada (se válida) e a tabela diária.

    Devolve (caminho do relatório, "valida" ou "invalida"). Nada é gravado se uma trava ou conferência falhar.
    """
    params = carregar_parametros_treino() if params is None else params
    pasta_docs, pasta_saida = Path(pasta_docs), Path(pasta_saida)
    doc = pasta_docs / DOC_PROTOCOLO if doc_protocolo is None else Path(doc_protocolo)
    registro_teste_final = treino.REGISTRO_TESTE_FINAL if registro_teste_final is None else Path(registro_teste_final)
    caminho_registro = pasta_docs / ARQUIVO_REGISTRO

    conferir_travas(params, registro_teste_final)
    _conferir_documento(doc)
    if set(protocolo.ORDEM_TESTES) != set(preparacao.BLOCOS_PROTOCOLO):
        raise ErroProtocolo("ORDEM_TESTES não bate com BLOCOS_PROTOCOLO")
    eventos = reg.ler(caminho_registro)

    csv = treino.localizar_datasets(Path(pasta_datasets), data)["todas"]
    df, info = treino.ler_desenvolvimento(csv, params)
    prep, cal = treino.preparar_dev(df)
    dobras = validacao.dobras_walk_forward(cal, params.treino_minimo_meses, params.embargo_pregoes)
    conferir_periodo(df, dobras, params, lim)
    cobertura = conferir_colunas(prep)

    n = reg.proxima_rodada(eventos, "protocolo")
    if n >= 2 and not motivo.strip():
        raise ErroProtocolo("da 2ª rodada em diante o motivo é obrigatório (--motivo)")
    nomes_saida = {
        "relatorio": pasta_docs / f"protocolo_rodada_{n:03d}.md",
        "json": pasta_docs / f"protocolo_rodada_{n:03d}.json",
        "congelado": pasta_docs / f"protocolo_congelado_rodada_{n:03d}.json",
        "diario": pasta_saida / f"rodada-{n:03d}" / "ganho_diario.csv",
    }
    for caminho in nomes_saida.values():
        if caminho.exists():
            raise ErroProtocolo(f"{caminho.name} já existe: arquivos de rodada nunca são sobrescritos")

    assinatura = _assinatura(info, csv, params, lim, doc)
    primeira = reg.primeira_rodada_completa(eventos, "protocolo")
    regras_mudaram = primeira is not None and primeira["assinatura"]["sha_regras"] != assinatura["sha_regras"]
    iguais = reg.rodadas_iguais(eventos, "protocolo", assinatura)
    anterior = iguais[-1] if iguais else None

    reg.acrescentar(caminho_registro, {"tipo": "protocolo", "evento": "inicio", "rodada": n, "motivo": motivo,
                                       "em": treino._agora(), "assinatura": assinatura})
    historico = reg.ler(caminho_registro)
    try:
        resultado = rodar_protocolo(prep, dobras, params, lim)
        previsoes = resultado.pop("previsoes")
        avaliacoes = {nome: resultado["testes"][nome]["avaliacao"] for nome in protocolo.ORDEM_TESTES}
        decisao = protocolo.decidir_rodada(avaliacoes, resultado["adotados"], regras_mudaram)
        ident = _identificacao(df, cal, dobras, info, assinatura, params)
        rodada = _montar_rodada(resultado, decisao, ident, cobertura, n, data, motivo, params, anterior)
        texto_relatorio = gerar_relatorio(rodada, historico)
        _gravar_novo(nomes_saida["relatorio"], texto_relatorio)
        _gravar_novo(nomes_saida["json"], json.dumps(treino._para_json(rodada), ensure_ascii=False, indent=2,
                                                     sort_keys=True))
        if rodada["colunas_congeladas"] is not None:
            _gravar_novo(nomes_saida["congelado"], json.dumps(treino._para_json(rodada["colunas_congeladas"]),
                                                              ensure_ascii=False, indent=2, sort_keys=True))
        _gravar_novo(nomes_saida["diario"], _ganho_diario(previsoes, lim))
    except Exception as erro:
        reg.acrescentar(caminho_registro, {"tipo": "protocolo", "evento": "falhou", "rodada": n,
                                           "em": treino._agora(), "erro": f"{type(erro).__name__}: {erro}"})
        raise
    reg.acrescentar(caminho_registro, {
        "tipo": "protocolo", "evento": "fim", "rodada": n, "em": treino._agora(), "assinatura": assinatura,
        "status": rodada["status"], "motivos": rodada["motivos"], "adotados": rodada["adotados"],
        "bloco_e_aprovado": rodada["bloco_e_aprovado"], "aprovados": resultado["aprovados"],
        "n_testes": rodada["n_testes"], "relatorio": nomes_saida["relatorio"].name,
        "sha_resultado": rodada["sha_resultado"], "repete_rodada": rodada["repete_rodada"],
        "reproduziu": rodada["reproduziu"],
    })
    return nomes_saida["relatorio"], rodada["status"]


def _data_argumento(texto: str) -> date:
    return treino._data_argumento(texto)


def main(argv=None, params=None, lim=LIMITES, registro_teste_final=None) -> int:
    """Ponto de entrada (`python -m processamento.experimento.protocolo_execucao`).

    Devolve 0 em rodada válida; 3 em rodada inválida (relatório gravado); 2 se faltar dataset, o sha256 não
    bater, a coluna nova faltar ("regenere"), o registro estiver adulterado ou faltar motivo; 4 se a trava
    do protocolo estiver fechada (nada é gravado).
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.experimento.protocolo_execucao",
        description="Uma rodada do protocolo de variáveis novas. Só lê o CSV do dataset (nada do banco).",
    )
    parser.add_argument("--data", type=_data_argumento, required=True, help="data do dataset (AAAA-MM-DD)")
    parser.add_argument("--motivo", default="", help="motivo da rodada (obrigatório a partir da 2ª)")
    parser.add_argument("--pasta-datasets", type=Path, default=treino.PASTA_DATASETS_PADRAO,
                        help="pasta dos CSV (padrão: saida/experimento)")
    parser.add_argument("--pasta-docs", type=Path, default=PASTA_DOCS_PADRAO,
                        help="pasta do protocolo, do registro e dos relatórios (padrão: docs)")
    parser.add_argument("--pasta-saida", type=Path, default=PASTA_SAIDA_PADRAO,
                        help="pasta da tabela diária (padrão: saida/experimento/protocolo)")
    args = parser.parse_args(argv)
    try:
        caminho, status = executar(
            args.pasta_datasets, args.pasta_docs, args.pasta_saida,
            data=args.data, motivo=args.motivo, params=params, lim=lim,
            registro_teste_final=registro_teste_final,
        )
    except ErroTravaProtocolo as e:
        print(f"{e}. Nada foi gravado.")
        return 4
    except (treino.ErroDataset, ErroProtocolo, reg.ErroRegistro) as e:
        print(f"{e}")
        return 2
    if status == "valida":
        print(f"Relatório gravado: {caminho}")
        return 0
    print(f"Rodada inválida (relatório gravado): {caminho}")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
