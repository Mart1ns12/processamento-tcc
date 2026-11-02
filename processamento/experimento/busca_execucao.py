"""Execução da busca pelo melhor modelo (docs/protocolo_variaveis.md, seção 6) e CLI.

Roda só no desenvolvimento, sobre as colunas congeladas de uma rodada válida do protocolo (sem o bloco E).
Só lê o CSV do dataset (nunca o banco), não abre o teste final e não grava em modelos/. Usa o mesmo
registro do protocolo (`docs/protocolo_tentativas.jsonl`), com tipo "busca".

Comando: python -m processamento.experimento.busca_execucao --data AAAA-MM-DD --congelado docs/protocolo_congelado_rodada_NNN.json --motivo "..."
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

from processamento import fontes
from processamento.experimento import avaliacao, busca, protocolo, protocolo_execucao, treino, validacao
from processamento.experimento import protocolo_registro as reg
from processamento.experimento.busca import COMBINACAO, LIMITES_BUSCA, REFERENCIA
from processamento.experimento.parametros import carregar_parametros_treino
from processamento.experimento.protocolo_execucao import (
    ARQUIVO_REGISTRO, DOC_PROTOCOLO, PASTA_EXPERIMENTO, PrevisoesEmCache,
    ErroProtocolo, ErroTravaProtocolo, conferir_periodo, conferir_travas,
)

PASTA_DOCS_PADRAO = fontes.RAIZ / "docs"
ARQUIVOS_CODIGO = protocolo_execucao.ARQUIVOS_CODIGO + ("busca.py", "busca_execucao.py")
_MODELOS_AVALIADOS_SEM_EXTRAS = ("modelo_1", "modelo_3", "logistica", "volatilidade")


def _congelado_valido(eventos: list[dict], congelado: dict, sha256: str) -> int:
    """A configuração tem de vir de uma rodada válida do protocolo, com o mesmo dataset. Devolve o nº da rodada."""
    if congelado.get("sha256_dataset") != sha256:
        raise ErroProtocolo("o congelado é de outro dataset (sha256 diferente): rode o protocolo neste dataset")
    rodada = congelado.get("rodada")
    fins = [e for e in eventos if e.get("tipo") == "protocolo" and e.get("evento") == "fim" and e.get("rodada") == rodada]
    if not fins:
        raise ErroProtocolo(f"a rodada {rodada} do protocolo não tem fim no registro")
    if fins[-1]["status"] != "valida":
        raise ErroProtocolo(f"a rodada {rodada} do protocolo é inválida: a busca só roda sobre rodada válida")
    if fins[-1]["assinatura"]["sha256_dataset"] != sha256:
        raise ErroProtocolo(f"a rodada {rodada} do protocolo foi feita com outro dataset")
    return int(rodada)


def _ic_diferenca(pred_a: pd.DataFrame, pred_b: pd.DataFrame, lim, semente: int) -> tuple:
    """IC do ganho pareado de AUC por pregão (a − b), com os limites da busca."""
    dif = avaliacao.diferenca_pareada(avaliacao.auc_por_pregao(pred_a), avaliacao.auc_por_pregao(pred_b))
    return avaliacao.ic_bootstrap_blocos(
        dif.to_numpy(), lim.bloco_bootstrap, lim.reamostragens, semente, percentis=lim.percentis_ic
    )


def rodar_busca(prep, dobras, params, colunas_3: list[str], lim=LIMITES_BUSCA, prever=None,
                medir=protocolo.medir_comparacao) -> dict:
    """Candidatos e combinação contra a referência, no modelo 3 congelado, e a escolha. Não grava nada.

    Previsões repetidas (mesmas colunas, família e hiperparâmetros) saem do cache. Quem chama confere
    as travas e o período antes.
    """
    previsor = PrevisoesEmCache(treino.prever_walk_forward if prever is None else prever, params)
    hiper_referencia = dict(params.xgboost)
    ref = previsor(prep, dobras, colunas_3, "xgb", params, hiper_referencia)
    candidatos = busca.candidatos(params)
    preds = {c["nome"]: previsor(prep, dobras, colunas_3, c["familia"], params, c["hiper"]) for c in candidatos}
    # combinação fixada antes: referência (#0), LightGBM 3/50 (#8) e logística (#1); só relato
    lgbm_referencia = previsor(prep, dobras, colunas_3, "lgbm", params, hiper_referencia)
    combinada = busca.combinar_por_rank([ref, lgbm_referencia, preds["logistica"]])
    preds[COMBINACAO] = combinada

    medidas, avaliacoes = {}, {}
    for nome, pred in preds.items():
        medidas[nome] = medir(ref, pred, params.semente, lim)
        avaliacoes[nome] = protocolo.avaliar_criterios(medidas[nome], False, lim)

    def dif_para_melhor(nome_melhor: str, nome: str) -> tuple:
        return _ic_diferenca(preds[nome_melhor], preds[nome], lim, params.semente)

    escolha = busca.escolher(avaliacoes, medidas, dif_para_melhor)
    return {"candidatos": candidatos, "preds": {**preds, REFERENCIA: ref}, "medidas": medidas,
            "avaliacoes": avaliacoes, "escolha": escolha, "previsor": previsor}


def _familia_do_vencedor(vencedor: str, candidatos: list[dict], params) -> tuple[str, dict | None]:
    if vencedor == REFERENCIA:
        return "xgb", dict(params.xgboost)
    cand = next(c for c in candidatos if c["nome"] == vencedor)
    return cand["familia"], cand["hiper"]


def avaliar_vencedor(prep, dobras, params, busca_res: dict, colunas_1: list[str], colunas_3: list[str]) -> dict:
    """Modelo 1 (mesma família e hiperparâmetros do vencedor), volatilidade e as métricas de desenvolvimento.

    Se a logística vencer, a referência "logistica" passa a ser o XGBoost do ponto de partida (relatado).
    """
    previsor = busca_res["previsor"]
    vencedor = busca_res["escolha"]["vencedor"]
    familia, hiper = _familia_do_vencedor(vencedor, busca_res["candidatos"], params)
    pred = busca_res["preds"]
    pred3 = pred[REFERENCIA] if vencedor == REFERENCIA else pred[vencedor]
    pred1 = previsor(prep, dobras, colunas_1, familia, params, hiper)
    pred_logistica = pred[REFERENCIA] if vencedor == "logistica" else pred["logistica"]
    pred_vol = previsor(prep, dobras, colunas_3, "volatilidade", params, None)
    previsoes = {
        "modelo_1": pred1, "modelo_3": pred3, "logistica": pred_logistica, "volatilidade": pred_vol,
        "modelo_3_principais": None, "modelo_3_hora_real_noite": None,
    }
    cfg = {"colunas_1": colunas_1, "colunas_3": colunas_3}
    acaso = treino.calcular_acaso(pred3, params)
    modelos_bloco = {
        nome: treino.avaliar(previsoes[nome], params, acaso, colunas=treino._colunas_de(nome, cfg))
        for nome in _MODELOS_AVALIADOS_SEM_EXTRAS
    }
    return {
        "familia": familia,
        "hiperparametros": hiper,
        "modelos": modelos_bloco,
        "comparacoes": treino._comparacoes(previsoes, params),
        "calibracao": treino._calibracao(pred3, params),
        "veredito": treino._veredito(modelos_bloco),
        "logistica_e_referencia": vencedor == "logistica",
    }


def _sha_resultado(busca_res: dict, final: dict) -> str:
    """sha256 do JSON de candidatos, medidas, critérios, escolha e métricas (sem horário)."""
    base = {
        "medidas": busca_res["medidas"],
        "criterios": busca_res["avaliacoes"],
        "escolha": busca_res["escolha"],
        "familia": final["familia"],
        "hiperparametros": final["hiperparametros"],
        "modelos": final["modelos"],
        "comparacoes": final["comparacoes"],
    }
    return protocolo_execucao._sha(json.dumps(treino._para_json(base), sort_keys=True, ensure_ascii=False))


def _num(valor, casas: int = 5) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "n/d"
    return f"{valor:.{casas}f}"


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join("n/d" if c is None else str(c) for c in linha) + " |" for linha in linhas]
    return saida


def _linha_candidato(nome: str, familia: str, medidas: dict, aval: dict, lim) -> list:
    ganhos = medidas["ganho_por_ano"]
    positivos = sum(1 for a in lim.anos if ganhos.get(a) is not None and ganhos[a] > 0)
    pior = min((v for v in ganhos.values() if v is not None), default=None)
    ic = medidas["ic"]
    return [nome, familia, _num(medidas["ganho"]), f"[{_num(ic[0])}; {_num(ic[1])}]",
            f"{positivos} de {len(lim.anos)}", _num(pior), _num(medidas["top"]["queda_pontos"]),
            "sim" if aval["aprovado"] else "não"]


def _relatorio(busca_res: dict, final: dict, ident: dict, n: int, data: date, motivo: str, params, lim,
               historico: list[dict], regras_mudaram: bool = False) -> str:
    """Markdown da rodada: aviso, identificação, todos os candidatos, a combinação, a escolha e as métricas."""
    escolha = busca_res["escolha"]
    linhas = [f"# Busca pelo melhor modelo, rodada {n:03d}", ""]
    if regras_mudaram:
        linhas += ["**Rodada inválida: a seção 6 do protocolo ou os limites mudaram depois da 1ª busca completa. "
                   "Nenhuma configuração final foi gravada.**", ""]
    if not params.modelo_oficial:
        linhas += ["Exploratório: `treino.modelo_oficial` é false.", ""]
    linhas += ["Não constitui recomendação de investimento.", ""]

    linhas += ["## Identificação", ""]
    linhas += [f"- Data: {data.isoformat()}; motivo: {motivo or '(sem motivo)'}",
               f"- Rodada do protocolo de origem: {ident['rodada_protocolo']}",
               f"- Dataset: {ident['arquivo_dataset']}, sha256 {ident['sha256_dataset']}",
               f"- versao_preparacao: {ident['versao_preparacao']}; semente: {ident['semente']}",
               f"- sha_parametros: {ident['sha_parametros']}; sha_regras: {ident['sha_regras']}",
               f"- sha_codigo: {ident['sha_codigo']}",
               f"- Versões: {ident['versoes']}",
               f"- Referência (ponto de partida): XGBoost {ident['hiperparametros']}", ""]

    linhas += ["## Candidatos contra a referência (modelo 3, critérios 1 a 4 da busca)", ""]
    cabecalho = ["Candidato", "Família", "Ganho", "IC 99,5%", "Anos positivos", "Pior ano",
                 "Queda do top 5 (pontos)", "Aprovado"]
    linhas_tab = []
    for cand in busca_res["candidatos"]:
        nome = cand["nome"]
        linhas_tab.append(_linha_candidato(nome, cand["familia"], busca_res["medidas"][nome],
                                           busca_res["avaliacoes"][nome], lim))
    linhas_tab.append(_linha_candidato(COMBINACAO, "combinação por rank (só relato)",
                                       busca_res["medidas"][COMBINACAO], busca_res["avaliacoes"][COMBINACAO], lim))
    linhas += _tabela(cabecalho, linhas_tab) + [""]
    linhas += ["A combinação não pode vencer. Referência: XGBoost do ponto de partida (max_depth 3, "
               "min_child_weight 50).", ""]

    linhas += ["## Escolha", ""]
    linhas += [f"- Vencedor: {escolha['vencedor']}",
               f"- Melhor (maior ganho entre os aprovados): {escolha['melhor'] or 'nenhum'}",
               f"- Aprovados: {', '.join(escolha['aprovados']) or 'nenhum'}",
               f"- Combinação aprovada (não vence): {'sim' if escolha['combinacao_aprovada'] else 'não'}",
               f"- Motivo: {escolha['motivo']}"]
    if final["logistica_e_referencia"]:
        linhas += ["- A logística venceu: a referência logística passa a ser o XGBoost do ponto de partida."]
    linhas += [""]

    linhas += ["## Métricas no desenvolvimento do vencedor", ""]
    linhas += [f"- Família: {final['familia']}; hiperparâmetros: {final['hiperparametros']}",
               f"- Veredito: {final['veredito']['texto']}",
               f"- Calibração: ECE {_num(final['calibracao']['ece'])}, aprovada: "
               f"{'sim' if final['calibracao']['aprovada'] else 'não'}", ""]
    linhas_metricas = []
    for nome, bloco in final["modelos"].items():
        top5 = bloco["topk"]["5"]
        linhas_metricas.append([nome, _num(top5["taxa_acerto"]), top5["vs_acaso"]])
    linhas += _tabela(["Modelo", "Taxa de acerto do top 5", "Frente ao acaso"], linhas_metricas) + [""]
    linhas_comp = [[c["a"], c["b"], c["metrica"], _num(c["media_dif"]), f"[{_num(c['ic'][0])}; {_num(c['ic'][1])}]",
                    c["n_dias"]] for c in final["comparacoes"]]
    linhas += _tabela(["A", "B", "Métrica", "Diferença média", "IC", "Dias"], linhas_comp) + [""]

    linhas += ["## Todas as tentativas da busca", ""]
    linhas_hist = []
    for evento in historico:
        if evento.get("tipo") == "busca" and evento.get("evento") == "fim":
            linhas_hist.append([evento["rodada"], evento["status"], evento.get("vencedor"),
                                evento.get("sha_resultado"), evento.get("repete_rodada"),
                                "sim" if evento.get("reproduziu") is False else ""])
        elif evento.get("tipo") == "busca" and evento.get("evento") == "inicio":
            if evento["rodada"] == n:
                linhas_hist.append([n, "esta rodada", None, None, None, ""])
            elif not any(e.get("tipo") == "busca" and e.get("evento") == "fim" and e.get("rodada") == evento["rodada"]
                         for e in historico):
                linhas_hist.append([evento["rodada"], "interrompida", None, None, None, ""])
    linhas += _tabela(["Rodada", "Situação", "Vencedor", "sha do resultado", "Repete rodada", "Não reproduziu"],
                      linhas_hist) + [""]
    return "\n".join(linhas)


def _identificacao(df: pd.DataFrame, cal: list, dobras: list, info: dict, assinatura: dict, params) -> dict:
    datas = pd.to_datetime(df["data"]).dt.date
    return {
        "rodada_protocolo": assinatura["rodada_protocolo"],
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


def _sha_regras_busca(doc: Path, lim) -> str:
    """Hash das regras da própria busca: a seção 6 do protocolo (fim de linha normalizado), mais os limites."""
    texto = doc.read_text(encoding="utf-8").replace("\r\n", "\n")
    inicio = texto.find("## 6.")
    if inicio == -1:
        raise ErroProtocolo(f"{doc.name}: seção 6 não encontrada")
    fim = texto.find("## 7.", inicio)
    trecho = texto[inicio:] if fim == -1 else texto[inicio:fim]
    return reg._sha_texto(trecho + "\n" + repr(lim))


def _assinatura(info: dict, csv: Path, params, lim, doc: Path, rodada_protocolo: int) -> dict:
    return {
        "sha256_dataset": info["sha256"],
        "arquivo_dataset": csv.name,
        "versao_preparacao": info.get("versao_preparacao"),
        "sha_parametros": reg.sha_parametros(params),
        "sha_regras": _sha_regras_busca(doc, lim),
        "sha_codigo": reg.sha_codigo([PASTA_EXPERIMENTO / a for a in ARQUIVOS_CODIGO]),
        "semente": params.semente,
        "rodada_protocolo": rodada_protocolo,
    }


def _gravar_novo(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "x", encoding="utf-8", newline="\n") as arq:
        arq.write(texto)


def _configuracao_final(congelado: dict, final: dict, n: int, rodada_protocolo: int, sha256: str,
                        vencedor: str) -> dict:
    return {
        "familia": final["familia"],
        "hiperparametros": final["hiperparametros"],
        "colunas_1": congelado["colunas_1"],
        "colunas_3": congelado["colunas_3"],
        "colunas_3e": congelado.get("colunas_3e"),
        "blocos_preco": congelado["blocos_preco"],
        "noticias_contexto": congelado["noticias_contexto"],
        "extremo_em_rank": False,
        "sha256_dataset": sha256,
        "vencedor": vencedor,
        "rodadas_de_origem": {"protocolo": rodada_protocolo, "busca": n},
    }


def executar(pasta_datasets, pasta_docs, *, data: date, motivo: str, congelado: Path | None,
             params=None, lim=LIMITES_BUSCA, doc_protocolo=None, registro_teste_final=None) -> tuple[Path, str]:
    """Roda a busca sobre a configuração congelada e grava o relatório, o JSON e a configuração final.

    Devolve (caminho do relatório, vencedor). Nada é gravado se uma trava ou conferência falhar.
    """
    params = carregar_parametros_treino() if params is None else params
    pasta_docs = Path(pasta_docs)
    doc = pasta_docs / DOC_PROTOCOLO if doc_protocolo is None else Path(doc_protocolo)
    registro_teste_final = treino.REGISTRO_TESTE_FINAL if registro_teste_final is None else Path(registro_teste_final)
    caminho_registro = pasta_docs / ARQUIVO_REGISTRO

    conferir_travas(params, registro_teste_final)
    if congelado is None or not Path(congelado).is_file():
        raise ErroProtocolo("a busca exige --congelado: o JSON de uma rodada válida do protocolo")
    protocolo_execucao._conferir_documento(doc)
    congelado_dados = json.loads(Path(congelado).read_text(encoding="utf-8"))
    eventos = reg.ler(caminho_registro)

    csv = treino.localizar_datasets(Path(pasta_datasets), data)["todas"]
    df, info = treino.ler_desenvolvimento(csv, params)
    rodada_protocolo = _congelado_valido(eventos, congelado_dados, info["sha256"])
    prep, cal = treino.preparar_dev(df)
    dobras = validacao.dobras_walk_forward(cal, params.treino_minimo_meses, params.embargo_pregoes)
    conferir_periodo(df, dobras, params, lim)

    n = reg.proxima_rodada(eventos, "busca")
    if n >= 2 and not motivo.strip():
        raise ErroProtocolo("da 2ª rodada em diante o motivo é obrigatório (--motivo)")
    nomes_saida = {
        "relatorio": pasta_docs / f"busca_rodada_{n:03d}.md",
        "json": pasta_docs / f"busca_rodada_{n:03d}.json",
        "configuracao": pasta_docs / f"configuracao_final_rodada_{n:03d}.json",
    }
    for caminho in nomes_saida.values():
        if caminho.exists():
            raise ErroProtocolo(f"{caminho.name} já existe: arquivos de rodada nunca são sobrescritos")

    assinatura = _assinatura(info, csv, params, lim, doc, rodada_protocolo)
    primeira = reg.primeira_rodada_completa(eventos, "busca")
    regras_mudaram = primeira is not None and primeira["assinatura"]["sha_regras"] != assinatura["sha_regras"]
    iguais = reg.rodadas_iguais(eventos, "busca", assinatura)
    anterior = iguais[-1] if iguais else None
    reg.acrescentar(caminho_registro, {"tipo": "busca", "evento": "inicio", "rodada": n, "motivo": motivo,
                                       "em": treino._agora(), "assinatura": assinatura})
    historico = reg.ler(caminho_registro)
    try:
        colunas_1, colunas_3 = congelado_dados["colunas_1"], congelado_dados["colunas_3"]
        busca_res = rodar_busca(prep, dobras, params, colunas_3, lim)
        final = avaliar_vencedor(prep, dobras, params, busca_res, colunas_1, colunas_3)
        vencedor = busca_res["escolha"]["vencedor"]
        sha_resultado = _sha_resultado(busca_res, final)
        ident = _identificacao(df, cal, dobras, info, assinatura, params)
        configuracao = _configuracao_final(congelado_dados, final, n, rodada_protocolo, info["sha256"], vencedor)
        texto = _relatorio(busca_res, final, ident, n, data, motivo, params, lim, historico, regras_mudaram)
        resumo = {"rodada": n, "status": "invalida" if regras_mudaram else "concluida", "data_rodada": data.isoformat(), "motivo": motivo, "identificacao": ident,
                  "sha_resultado": sha_resultado, "repete_rodada": anterior["rodada"] if anterior else None,
                  "reproduziu": (sha_resultado == anterior["sha_resultado"]) if anterior else None,
                  "vencedor": vencedor, "escolha": busca_res["escolha"], "medidas": busca_res["medidas"],
                  "criterios": busca_res["avaliacoes"], "final": final, "configuracao": configuracao}
        _gravar_novo(nomes_saida["relatorio"], texto)
        _gravar_novo(nomes_saida["json"], json.dumps(treino._para_json(resumo), ensure_ascii=False, indent=2,
                                                     sort_keys=True))
        if not regras_mudaram:
            _gravar_novo(nomes_saida["configuracao"], json.dumps(treino._para_json(configuracao), ensure_ascii=False,
                                                                 indent=2, sort_keys=True))
    except Exception as erro:
        reg.acrescentar(caminho_registro, {"tipo": "busca", "evento": "falhou", "rodada": n,
                                           "em": treino._agora(), "erro": f"{type(erro).__name__}: {erro}"})
        raise
    reg.acrescentar(caminho_registro, {
        "tipo": "busca", "evento": "fim", "rodada": n, "em": treino._agora(), "assinatura": assinatura,
        "vencedor": vencedor, "aprovados": busca_res["escolha"]["aprovados"],
        "combinacao_aprovada": busca_res["escolha"]["combinacao_aprovada"],
        "relatorio": nomes_saida["relatorio"].name, "sha_resultado": sha_resultado,
        "repete_rodada": resumo["repete_rodada"], "reproduziu": resumo["reproduziu"],
        "status": resumo["status"], "adotados": [],
        "motivos": ["seção 6 do protocolo ou limites diferentes da 1ª busca completa"] if regras_mudaram else [],
    })
    if regras_mudaram:
        raise ErroProtocolo(f"Rodada inválida, sem configuração final (relatório gravado: {nomes_saida['relatorio']})")
    return nomes_saida["relatorio"], vencedor


def main(argv=None, params=None, lim=LIMITES_BUSCA, registro_teste_final=None) -> int:
    """Ponto de entrada (`python -m processamento.experimento.busca_execucao`).

    Devolve 0 em sucesso; 2 se faltar dataset, o sha256 não bater, o congelado for de rodada inválida ou
    faltar, o registro estiver adulterado ou faltar motivo; 4 se a trava do teste final estiver fechada.
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.experimento.busca_execucao",
        description="Busca pelo melhor modelo sobre a configuração congelada. Só lê o CSV (nada do banco).",
    )
    parser.add_argument("--data", type=treino._data_argumento, required=True, help="data do dataset (AAAA-MM-DD)")
    parser.add_argument("--congelado", type=Path, default=None,
                        help="docs/protocolo_congelado_rodada_NNN.json de uma rodada válida do protocolo")
    parser.add_argument("--motivo", default="", help="motivo da rodada (obrigatório a partir da 2ª)")
    parser.add_argument("--pasta-datasets", type=Path, default=treino.PASTA_DATASETS_PADRAO,
                        help="pasta dos CSV (padrão: saida/experimento)")
    parser.add_argument("--pasta-docs", type=Path, default=PASTA_DOCS_PADRAO,
                        help="pasta do protocolo, do registro e dos relatórios (padrão: docs)")
    args = parser.parse_args(argv)
    try:
        caminho, _ = executar(
            args.pasta_datasets, args.pasta_docs,
            data=args.data, motivo=args.motivo, congelado=args.congelado, params=params, lim=lim,
            registro_teste_final=registro_teste_final,
        )
    except ErroTravaProtocolo as e:
        print(f"{e}. Nada foi gravado.")
        return 4
    except (treino.ErroDataset, treino.ErroPreRequisito, ErroProtocolo, reg.ErroRegistro) as e:
        print(f"{e}")
        return 2
    print(f"Relatório gravado: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
