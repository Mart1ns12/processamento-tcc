"""Modelo 3 x modelo 1, só desenvolvimento. Só lê o CSV; não grava no registro nem em modelos/."""
import json, sys
from datetime import date
from pathlib import Path
import numpy as np
from processamento.experimento import avaliacao, busca, protocolo, treino, validacao
from processamento.experimento import busca_execucao as be
from processamento.experimento.parametros import carregar_parametros_treino
params = carregar_parametros_treino()
lim = be.LIMITES_BUSCA
treino_csv = treino.localizar_datasets(Path("saida/experimento"), date(2026,10,30))["todas"]
df, info = treino.ler_desenvolvimento(treino_csv, params)
print("sha", info["sha256"][:12], "dados ate", df["data"].max())
prep, cal = treino.preparar_dev(df)
dobras = validacao.dobras_walk_forward(cal, params.treino_minimo_meses, params.embargo_pregoes)
cong = json.load(open("docs/protocolo_congelado_rodada_001.json", encoding="utf-8"))
c1, c3 = cong["colunas_1"], cong["colunas_3"]
cand = {c["nome"]: c for c in busca.candidatos(params)}
fam = {"logistica (vencedor)": ("logistica", cand["logistica"]["hiper"]), "xgb ponto de partida (sensibilidade)": ("xgb", dict(params.xgboost))}
saida = {}
acaso = None
for nome, (f, h) in fam.items():
    p1 = treino.prever_walk_forward(prep, dobras, c1, f, params, h)
    p3 = treino.prever_walk_forward(prep, dobras, c3, f, params, h)
    if acaso is None: acaso = treino.calcular_acaso(p3, params)
    m = protocolo.medir_comparacao(p1, p3, params.semente, lim)
    bl = {}
    for lab, p, cols in (("modelo_1", p1, c1), ("modelo_3", p3, c3)):
        a = treino.avaliar(p, params, acaso, colunas=cols)
        auc = avaliacao.auc_por_pregao(p).to_numpy()
        ic95 = avaliacao.ic_bootstrap_blocos(auc-0.5, params.bootstrap_bloco_pregoes, params.bootstrap_reamostragens, params.semente)
        ic995 = avaliacao.ic_bootstrap_blocos(auc-0.5, lim.bloco_bootstrap, lim.reamostragens, params.semente, percentis=lim.percentis_ic)
        bl[lab] = {"auc": a["auc_medio_pregao"], "auc_excesso_ic95": list(ic95), "auc_excesso_ic995": list(ic995), "top5": {k:v for k,v in a["topk"]["5"].items() if not str(k).startswith("distribuicao")}, "top3": a["topk"]["3"].get("taxa_acerto"), "por_ano": a["por_ano"]}
    comp = treino._comparacoes({"modelo_1":p1,"modelo_3":p3,"logistica":p1,"volatilidade":p1,"modelo_3_principais":None,"modelo_3_hora_real_noite":None}, params)[:2]
    saida[nome] = {"comparacao": m, "ic95": comp, "modelos": bl}
fx = {k: v for k, v in acaso["5"].items() if not k.startswith("distribuicao")}
saida["acaso_top5"] = fx
Path(sys.argv[1]).write_text(json.dumps(treino._para_json(saida), ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(treino._para_json(saida), ensure_ascii=False, indent=None)[:14000])
