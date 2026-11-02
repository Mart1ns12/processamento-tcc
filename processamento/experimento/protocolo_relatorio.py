"""Relatório em markdown de uma rodada do protocolo (docs/protocolo_rodada_NNN.md).

Função pura: recebe o resultado já montado por `protocolo_execucao` e o histórico do registro; não grava nada.

Contrato de `resultado`:
  rodada, data_rodada, motivo, modelo_oficial, status ("valida" | "invalida"), motivos, adotados,
  bloco_e_aprovado, n_testes, identificacao (dict), passo_0 {tentativas, colunas_modelo_1, colunas_modelo_3},
  testes {nome: {base, medidas, avaliacao}} para cada nome de ORDEM_TESTES,
  conjunto {situacao ("executado" | "nao_se_aplica" | "nao_executado"), motivo, blocos, medidas, avaliacao},
  colunas_congeladas (dict ou None), cobertura {ano: {coluna: fração}}, sha_resultado, repete_rodada, reproduziu.

`historico`: eventos do registro até a abertura desta rodada, inclusive o "inicio" dela, sem o seu "fim".
"""

from __future__ import annotations

import math

from processamento.experimento.protocolo import ANOS_PROTOCOLO, ORDEM_TESTES

ROTULOS = {
    "controle": "Controle sorteado (controle)",
    "bloco_a": "A. Preço (bloco_a)",
    "bloco_b": "B. Contexto (bloco_b)",
    "bloco_c": "C. Balanço (bloco_c)",
    "bloco_d": "D. Valor (bloco_d)",
    "bloco_e": "E. Notícias (bloco_e)",
    "conjunto": "Conjunto A a D (conjunto)",
}


def _num(valor, casas: int = 5) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "n/d"
    return f"{valor:.{casas}f}"


def _pct(valor) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "n/d"
    return f"{valor:.1%}"


def _sim_nao(valor) -> str:
    if valor is None:
        return "não se aplica"
    return "sim" if valor else "não"


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return saida + [""]


def _cabecalho(resultado: dict) -> list[str]:
    invalida = resultado["status"] != "valida"
    linhas = [
        f"# Protocolo de teste de variáveis novas: rodada {resultado['rodada']:03d}",
        "",
    ]
    if not resultado.get("modelo_oficial", False):
        linhas += ["**Exploratório:** `treino.modelo_oficial` é false. Nenhum número vale como conclusão do TCC.", ""]
    linhas += ["Não constitui recomendação de investimento.", ""]
    if invalida:
        linhas += ["**RODADA INVÁLIDA:** " + "; ".join(resultado["motivos"]) + ".", ""]
    return linhas


def _identificacao(resultado: dict) -> list[str]:
    ident = resultado["identificacao"]
    situacao = "válida" if resultado["status"] == "valida" else "inválida (" + "; ".join(resultado["motivos"]) + ")"
    versoes = ", ".join(f"{k} {v}" for k, v in (ident.get("versoes") or {}).items()) or "n/d"
    hiper = ", ".join(f"{k}={v}" for k, v in (ident.get("hiperparametros") or {}).items()) or "n/d"
    itens = [
        ("Rodada", resultado["rodada"]),
        ("Data", resultado["data_rodada"]),
        ("Motivo", resultado["motivo"] or "1ª rodada"),
        ("Situação", situacao),
        ("sha256 do dataset", ident.get("sha256_dataset")),
        ("Arquivo do dataset", ident.get("arquivo_dataset")),
        ("versao_preparacao", ident.get("versao_preparacao")),
        ("Período", f"{ident.get('periodo_ini')} a {ident.get('periodo_fim')}"),
        ("Pregões", ident.get("n_pregoes")),
        ("Linhas", ident.get("n_linhas")),
        ("Dobras", ident.get("n_dobras")),
        ("Semente", ident.get("semente")),
        ("sha_parametros", ident.get("sha_parametros")),
        ("sha_regras", ident.get("sha_regras")),
        ("sha_codigo", ident.get("sha_codigo")),
        ("Versões", versoes),
        ("Hiperparâmetros", hiper),
    ]
    return ["## 2. Identificação", ""] + [f"- {rotulo}: {'n/d' if valor is None else valor}" for rotulo, valor in itens] + [""]


def _passo_0(resultado: dict) -> list[str]:
    passo = resultado["passo_0"]
    linhas = [[t["etapa"], t["descricao"], _num(t["auc_medio"]), _sim_nao(t["aceito"])] for t in passo["tentativas"]]
    return (
        ["## 3. Passo 0: seleção dos blocos de base", ""]
        + _tabela(["Etapa", "Descrição", "AUC médio", "Aceito"], linhas)
        + [f"- Base do modelo 1: {', '.join(passo['colunas_modelo_1'])}",
           f"- Base do modelo 3: {', '.join(passo['colunas_modelo_3'])}", ""]
    )


def _linha_criterios(nome: str, teste: dict) -> list:
    medidas, aval = teste["medidas"], teste["avaliacao"]
    ic = medidas["ic"]
    ganhos = [medidas["ganho_por_ano"].get(a) for a in ANOS_PROTOCOLO]
    anos_positivos = sum(1 for g in ganhos if g is not None and g > 0)
    piores = [g for g in ganhos if g is not None]
    return [
        ROTULOS[nome], teste["base"], _num(medidas["ganho"]), f"[{_num(ic[0])}; {_num(ic[1])}]",
        f"{anos_positivos} de {len(ANOS_PROTOCOLO)}", _num(min(piores) if piores else None),
        _num(medidas["top"]["queda_pontos"]), _num(medidas["regime"]["ganho"]),
        _num(medidas["regime"]["por_ano"].get(2023)),
        _sim_nao(aval["c1"]), _sim_nao(aval["c2"]), _sim_nao(aval["c3"]), _sim_nao(aval["c4"]),
        _sim_nao(aval["c5"]), _sim_nao(aval["aprovado"]),
    ]


def _criterios(resultado: dict) -> list[str]:
    linhas = [_linha_criterios(nome, resultado["testes"][nome]) for nome in ORDEM_TESTES]
    cabecalho = ["Teste", "Base", "Ganho", "IC 99%", "Anos positivos", "Pior ano", "Queda top 5 (pp)",
                 "Ganho em 2024 (critério 5)", "Ganho em 2023 (só relato)",
                 "C1", "C2", "C3", "C4", "C5", "Aprovado"]
    conjunto = resultado["conjunto"]
    if conjunto["medidas"] is not None:
        linhas.append(_linha_criterios("conjunto", {"base": "modelo 1", **conjunto}))
    return ["## 4. Critérios", ""] + _tabela(cabecalho, linhas)


def _ganho_por_ano(resultado: dict) -> list[str]:
    cabecalho = ["Teste"] + [str(a) for a in ANOS_PROTOCOLO]
    linhas = []
    pares = [(nome, resultado["testes"][nome]["medidas"]) for nome in ORDEM_TESTES]
    if resultado["conjunto"]["medidas"] is not None:
        pares.append(("conjunto", resultado["conjunto"]["medidas"]))
    for nome, m in pares:
        linhas.append([ROTULOS[nome]] + [
            f"{_num(m['ganho_por_ano'].get(a))} ({m['n_dias_por_ano'].get(a, 0)})" for a in ANOS_PROTOCOLO
        ])
    return ["## 5. Ganho por ano (número de pregões entre parênteses)", ""] + _tabela(cabecalho, linhas)


def _cobertura(resultado: dict) -> list[str]:
    cobertura = resultado["cobertura"]
    colunas = sorted({c for ano in cobertura.values() for c in ano})
    linhas = [[c] + [_pct(cobertura.get(a, {}).get(c)) for a in ANOS_PROTOCOLO] for c in colunas]
    return ["## 6. Cobertura das colunas novas (fração preenchida por ano)", ""] + _tabela(
        ["Coluna"] + [str(a) for a in ANOS_PROTOCOLO], linhas)


def _conjunto(resultado: dict) -> list[str]:
    conjunto = resultado["conjunto"]
    passou = bool((conjunto.get("avaliacao") or {}).get("aprovado"))
    situacao = {
        "executado": "executado: " + ("passou" if passou else "não passou"),
        "nao_se_aplica": "não se aplica",
        "nao_executado": "não executado",
    }[conjunto["situacao"]]
    return ["## 7. Teste conjunto (blocos A a D aprovados)", "",
            f"- Situação: {situacao}", f"- Motivo: {conjunto['motivo']}",
            f"- Blocos no conjunto: {', '.join(conjunto['blocos']) or 'nenhum'}", ""]


def _decisao(resultado: dict) -> list[str]:
    invalida = resultado["status"] != "valida"
    if resultado["adotados"]:
        adotados = ", ".join(ROTULOS[b] for b in resultado["adotados"])
        linha_adotados = f"- Blocos adotados: {adotados}"
    else:
        linha_adotados = "- Nenhum bloco adotado" + (": rodada inválida" if invalida else "")
    if resultado["bloco_e_aprovado"]:
        linha_e = "- Bloco E: aprovado como versão separada, fora da comparação do TCC"
    else:
        linha_e = "- Bloco E: não aprovado"
    congeladas = resultado["colunas_congeladas"]
    if congeladas is None:
        linha_colunas = "- Colunas congeladas: nenhuma (rodada inválida)" if invalida else "- Colunas congeladas: nenhuma"
    else:
        linha_colunas = (f"- Colunas congeladas (modelo 1): {', '.join(congeladas['colunas_1'])}\n"
                         f"- Colunas congeladas (modelo 3): {', '.join(congeladas['colunas_3'])}")
    return ["## 8. Decisão", "", linha_adotados, linha_e, linha_colunas, ""]


def _linhas_tentativas(resultado: dict, historico: list[dict]) -> list[list]:
    fins = {e["rodada"]: e for e in historico if e.get("tipo") == "protocolo" and e.get("evento") == "fim"}
    falhas = {e["rodada"] for e in historico if e.get("tipo") == "protocolo" and e.get("evento") == "falhou"}
    linhas = []
    for e in historico:
        if e.get("tipo") != "protocolo" or e.get("evento") != "inicio":
            continue
        n = e["rodada"]
        if n == resultado["rodada"]:
            fim = {"status": resultado["status"], "motivos": resultado["motivos"],
                   "sha": resultado["identificacao"].get("sha256_dataset"),
                   "repete": resultado.get("repete_rodada"), "reproduziu": resultado.get("reproduziu")}
        elif n in fins:
            f = fins[n]
            fim = {"status": f["status"], "motivos": f["motivos"], "sha": f["assinatura"]["sha256_dataset"],
                   "repete": f.get("repete_rodada"), "reproduziu": f.get("reproduziu")}
        else:
            fim = {"status": "falhou" if n in falhas else "interrompida", "motivos": [], "sha": None,
                   "repete": None, "reproduziu": None}
        reproduziu = {True: "sim", False: "**NÃO REPRODUZIU**", None: "n/d"}[fim["reproduziu"]]
        sha = fim["sha"][:12] if fim["sha"] else "n/d"
        linhas.append([n, e.get("motivo") or "1ª rodada", fim["status"], "; ".join(fim["motivos"]) or "-",
                       sha, fim["repete"] if fim["repete"] is not None else "-", reproduziu])
    return linhas


def _historico(resultado: dict, historico: list[dict]) -> list[str]:
    testes_anteriores = sum(e.get("n_testes", 0) for e in historico
                            if e.get("tipo") == "protocolo" and e.get("evento") == "fim")
    cabecalho = ["Rodada", "Motivo", "Situação", "Motivos", "sha256 dataset", "Repete", "Reproduziu"]
    return (
        ["## 9. Todas as tentativas do protocolo", ""]
        + _tabela(cabecalho, _linhas_tentativas(resultado, historico))
        + [f"- Testes nesta rodada: {resultado['n_testes']}. Testes acumulados: "
           f"{testes_anteriores + resultado['n_testes']}.",
           f"- sha256 do resultado: {resultado['sha_resultado']}", ""]
    )


def gerar_relatorio(resultado: dict, historico: list[dict]) -> str:
    """Markdown da rodada, nas nove seções do protocolo (seção 5 das regras de relato)."""
    partes = [
        _cabecalho(resultado),
        _identificacao(resultado),
        _passo_0(resultado),
        _criterios(resultado),
        _ganho_por_ano(resultado),
        _cobertura(resultado),
        _conjunto(resultado),
        _decisao(resultado),
        _historico(resultado, historico),
    ]
    return "\n".join("\n".join(parte) for parte in partes)
