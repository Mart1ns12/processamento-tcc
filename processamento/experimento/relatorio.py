"""Relatório do experimento em Markdown (Fase 6b).

Função pura: recebe o dicionário do `metricas.json` (contrato da Fase 6a) e devolve o texto.
Não lê arquivo nem banco. Campo ausente ou None vira "n/d"; modelo ou dataset extra ausente vira "não encontrado".
"""

from __future__ import annotations

import math
from datetime import date

NAO_INFORMADO = "n/d"
NAO_ENCONTRADO = "não encontrado"
ROTULO_PAPEL_VAZIO = "notícias sem julgamento da juíza, fora da versão"
RODAPE = "Não constitui recomendação de investimento."

ORDEM_MODELOS = (
    "modelo_1",
    "modelo_3",
    "logistica",
    "volatilidade",
    "modelo_3_principais",
    "modelo_3_hora_real_noite",
)
ORDEM_DATASETS = ("todas", "principais", "hora_real_noite")
ROTULO_ACASO = {
    "acima": "acima do acaso",
    "dentro": "ainda não mostrou vantagem sobre o acaso",
    "abaixo": "abaixo do acaso",
}
ROTULO_METRICA = {
    "acerto_top5_dia": "acerto no top 5 por dia",
    "auc_dia": "AUC por dia",
}


def _vazio(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def pct(x, casas: int = 1) -> str:
    """0.4834 -> '48,3%'; com casas=2, 0.0008 -> '0,08%' e -0.0028 -> '-0,28%'. None ou NaN -> 'n/d'."""
    if _vazio(x):
        return NAO_INFORMADO
    texto = f"{100 * x:.{casas}f}"
    if float(texto) == 0:
        texto = texto.lstrip("-")
    return texto.replace(".", ",") + "%"


def _num(x, casas: int = 3) -> str:
    if _vazio(x):
        return NAO_INFORMADO
    if isinstance(x, int):
        return str(x)
    return f"{x:.{casas}f}".replace(".", ",")


def _sim_nao(x) -> str:
    if x is None:
        return NAO_INFORMADO
    return "sim" if x else "não"


def _texto(valor) -> str:
    if isinstance(valor, bool):
        return _sim_nao(valor)
    if _vazio(valor):
        return NAO_INFORMADO
    if isinstance(valor, (int, float)):
        return _num(valor, 4)
    if isinstance(valor, dict):
        return "; ".join(f"{k}: {_texto(v)}" for k, v in valor.items()) or NAO_INFORMADO
    if isinstance(valor, (list, tuple)):
        return "; ".join(_texto(v) for v in valor) or NAO_INFORMADO
    return str(valor)


def _frac(parte, total):
    if _vazio(parte) or _vazio(total) or not total:
        return None
    return parte / total


def _faixa(par, casas: int = 1) -> str:
    if not par or len(par) < 2:
        return NAO_INFORMADO
    return f"{pct(par[0], casas)} a {pct(par[1], casas)}"


def _metrica(valor, metrica) -> str:
    if metrica == "acerto_top5_dia":
        return pct(valor)
    return _num(valor)


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    if not linhas:
        return ["Sem dados."]
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return saida


def _tabela_de_dicts(lista) -> list[str]:
    if not lista or not isinstance(lista[0], dict):
        return ["Sem dados."]
    colunas = list(lista[0].keys())
    return _tabela(colunas, [[_texto(item.get(c)) for c in colunas] for item in lista])


def _linha_historico(periodo: dict) -> str:
    """Linha do aviso com o período de desenvolvimento lido dos dados (em vez de um texto fixo)."""
    inicio, fim = periodo.get("inicio"), periodo.get("fim")
    if not inicio or not fim:
        return "> Período de desenvolvimento não informado (ESPECIFICACAO 3.4)."
    anos = (date.fromisoformat(str(fim)[:10]) - date.fromisoformat(str(inicio)[:10])).days / 365.25
    anos_txt = f"{anos:.1f}".replace(".", ",")
    return (
        f"> Gerado com o período de desenvolvimento de {inicio} a {fim} (cerca de {anos_txt} anos, "
        f"{_texto(periodo.get('n_pregoes'))} pregões); o modelo só vale como oficial com "
        "`treino.modelo_oficial: true` (ESPECIFICACAO 3.4)."
    )


def _aviso(periodo: dict) -> list[str]:
    inicio = _texto(periodo.get("teste_final_inicio"))
    fim = periodo.get("teste_final_fim")
    if periodo.get("teste_final_usado"):
        situacao = "USADO nesta execução (uso único)."
    else:
        situacao = "NÃO usado nem lido para escolher nada (trava fechada)."
    if fim:
        linha_fim = (
            "> O teste final vai até a véspera da entrada em produção "
            f"(`treino.teste_final.fim` = {fim}); depois dele vem o teste ao vivo."
        )
    else:
        linha_fim = (
            "> O teste final vai até a véspera da entrada em produção "
            "(`treino.teste_final.fim`, hoje vazio = trava ativa); depois dele vem o teste ao vivo."
        )
    return [
        "> **AVISO: TESTE DE FUNCIONAMENTO, NÃO É RESULTADO.**",
        _linha_historico(periodo),
        "> Nenhum número abaixo vale como conclusão do TCC: serve só para conferir que o pipeline roda de ponta a ponta.",
        f"> Período de teste final (a partir de {inicio}): {situacao}",
        linha_fim,
    ]


def _titulo(modo) -> list[str]:
    if modo == "teste_final":
        return ["# AVALIAÇÃO NO TESTE FINAL (uso único)"]
    return ["# AVALIAÇÃO DE DESENVOLVIMENTO"]


def _secao_dados(metricas: dict) -> list[str]:
    periodo = metricas.get("periodo") or {}
    datasets = metricas.get("datasets") or {}
    fim = periodo.get("teste_final_fim")
    modo = "teste final (uso único)" if metricas.get("modo") == "teste_final" else "desenvolvimento"
    linhas = [
        "## 2. Dados, períodos e trava",
        "",
        f"- Modo: {modo}.",
        f"- Gerado em: {_texto(metricas.get('gerado_em'))}.",
        f"- Período de desenvolvimento: de {_texto(periodo.get('inicio'))} a {_texto(periodo.get('fim'))}, "
        f"{_texto(periodo.get('n_pregoes'))} pregões, {_texto(periodo.get('n_linhas'))} linhas, "
        f"{_texto(periodo.get('n_tickers'))} papéis (universo: {_texto(periodo.get('universo'))}).",
        f"- Embargo entre treino e teste: {_texto(periodo.get('embargo_pregoes'))} pregão(ões).",
        f"- Teste final: de {_texto(periodo.get('teste_final_inicio'))} até "
        f"{_texto(fim) if fim else 'vazio (trava ativa)'}.",
        f"- Teste final usado nesta execução: {_sim_nao(periodo.get('teste_final_usado'))}.",
        "- Datasets:",
    ]
    for nome in ORDEM_DATASETS:
        ds = datasets.get(nome)
        if not ds:
            linhas.append(f"  - {nome}: {NAO_ENCONTRADO}.")
            continue
        linhas.append(
            f"  - {nome}: arquivo {_texto(ds.get('arquivo'))}, {_texto(ds.get('linhas'))} linhas, "
            f"cobertura desde {_texto(ds.get('cobertura_inicio'))}, sha256 {_texto(ds.get('sha256'))}."
        )
    return linhas


def _secao_noticias(metricas: dict) -> list[str]:
    datasets = metricas.get("datasets") or {}
    linhas = ["## 3. Contagens de notícias", ""]

    principais = datasets.get("principais")
    if not principais:
        linhas.append(f"- Versão principal: {NAO_ENCONTRADO}.")
    else:
        info = principais.get("info_noticias") or {}
        lidas = info.get("lidas")
        papel = info.get("papel_vazio_fora")
        linhas += [
            "- Versão principal:",
            f"  - notícias lidas: {_texto(lidas)};",
            f"  - {ROTULO_PAPEL_VAZIO}: {_texto(papel)} ({pct(_frac(papel, lidas))} das lidas).",
        ]

    hora = datasets.get("hora_real_noite")
    if not hora:
        linhas.append(f"- Versão hora real na noite: {NAO_ENCONTRADO}.")
    else:
        info = hora.get("info_noticias") or {}
        lidas = info.get("lidas")
        sem_hora = info.get("fora_versao")
        fora_noite = info.get("descartadas_fora_da_janela")
        na_noite = info.get("preparadas")
        linhas += [
            "- Versão hora real na noite:",
            f"  - notícias lidas: {_texto(lidas)};",
            f"  - sem hora real (fora da versão): {_texto(sem_hora)} ({pct(_frac(sem_hora, lidas))} das lidas);",
            f"  - com hora real, fora da noite: {_texto(fora_noite)} ({pct(_frac(fora_noite, lidas))} das lidas);",
            f"  - com hora real, na noite: {_texto(na_noite)} ({pct(_frac(na_noite, lidas))} das lidas).",
        ]
    return linhas


def _secao_dobras(metricas: dict) -> list[str]:
    dobras = metricas.get("dobras") or []
    linhas = ["## 4. Dobras", ""]
    if not dobras:
        return linhas + ["Nenhuma dobra (histórico curto)."]
    cabecalho = [
        "Dobra",
        "Mês do teste",
        "Treino",
        "Pregões de treino",
        "Pregões de teste",
        "Linhas de treino",
        "Linhas de teste",
    ]
    tabela = [
        [
            _texto(d.get("numero")),
            _texto(d.get("mes_teste")),
            f"de {_texto(d.get('treino_inicio'))} a {_texto(d.get('treino_fim'))}",
            _texto(d.get("n_pregoes_treino")),
            _texto(d.get("n_pregoes_teste")),
            _texto(d.get("n_linhas_treino")),
            _texto(d.get("n_linhas_teste")),
        ]
        for d in dobras
    ]
    return linhas + _tabela(cabecalho, tabela)


def _secao_selecao(metricas: dict) -> list[str]:
    sel = metricas.get("selecao") or {}
    linhas = [
        "## 5. Seleção",
        "",
        "> Nota: métricas de desenvolvimento são otimistas: blocos e grade foram escolhidos nas mesmas dobras; "
        "o número honesto será o do teste final.",
        "",
        f"- Blocos de preço: {_texto(sel.get('blocos_preco')) if sel.get('blocos_preco') else 'nenhum (só as essenciais)'}.",
        f"- Blocos de notícias de contexto: {_texto(sel.get('noticias_contexto'))}.",
        f"- Hiperparâmetros escolhidos: {_texto(sel.get('hiperparametros'))}.",
        "",
    ]
    tentativas = sel.get("tentativas") or []
    if not tentativas:
        return linhas + ["Sem tentativas registradas."]
    tabela = [
        [
            _texto(t.get("etapa")),
            _texto(t.get("descricao")),
            _num(t.get("auc_medio")),
            _sim_nao(t.get("aceito")),
        ]
        for t in tentativas
    ]
    return linhas + _tabela(["Etapa", "Descrição", "AUC médio", "Aceita"], tabela)


def _secao_topk(metricas: dict) -> list[str]:
    modelos = metricas.get("modelos") or {}
    acaso = metricas.get("acaso") or {}
    linhas = [
        "## 6. Acerto no top 5 e no top 3",
        "",
        "A faixa do acaso é o que daria um sorteio aleatório.",
        "",
    ]
    cabecalho = [
        "Top",
        "Dias",
        "Taxa de acerto (intervalo)",
        "Acaso: média (faixa 2,5% a 97,5%)",
        "Excesso médio (intervalo)",
        "Situação vs acaso",
    ]
    for nome in ORDEM_MODELOS:
        m = modelos.get(nome)
        linhas += [f"### {nome}", ""]
        if not m:
            linhas += [f"{NAO_ENCONTRADO}.", ""]
            continue
        topk = m.get("topk") or {}
        tabela = []
        for k in ("5", "3"):
            t = topk.get(k) or {}
            a = acaso.get(k) or {}
            tabela.append([
                f"Top {k}",
                _texto(t.get("n_dias")),
                f"{pct(t.get('taxa_acerto'))} (intervalo {_faixa(t.get('ic_taxa'))})",
                f"{pct(a.get('media'))} (faixa {pct(a.get('p2_5'))} a {pct(a.get('p97_5'))})",
                f"{pct(t.get('excesso_medio'), 2)} (intervalo {_faixa(t.get('ic_excesso'), 2)})",
                ROTULO_ACASO.get(t.get("vs_acaso"), NAO_INFORMADO),
            ])
        linhas += _tabela(cabecalho, tabela) + [""]
    return linhas


def _secao_veredito(metricas: dict) -> list[str]:
    v = metricas.get("veredito_modelo_3")
    linhas = ["## 7. Veredito", ""]
    if not v:
        return linhas + ["Veredito não encontrado."]
    return linhas + [
        f"- Acaso: {ROTULO_ACASO.get(v.get('acaso'), NAO_INFORMADO)}.",
        f"- Supera a volatilidade: {_sim_nao(v.get('supera_volatilidade'))}.",
        f"- Supera a logística: {_sim_nao(v.get('supera_logistica'))}.",
        "",
        _texto(v.get("texto")),
    ]


def _secao_comparacoes(metricas: dict) -> list[str]:
    comparacoes = metricas.get("comparacoes") or []
    linhas = ["## 8. Diferenças pareadas", ""]
    if not comparacoes:
        return linhas + ["Nenhuma comparação calculada."]
    tabela = []
    for c in comparacoes:
        metrica = c.get("metrica")
        ic = c.get("ic") or []
        intervalo = (
            f"{_metrica(ic[0], metrica)} a {_metrica(ic[1], metrica)}" if len(ic) == 2 else NAO_INFORMADO
        )
        tabela.append([
            f"{_texto(c.get('a'))} vs {_texto(c.get('b'))}",
            ROTULO_METRICA.get(metrica, _texto(metrica)),
            _metrica(c.get("media_dif"), metrica),
            intervalo,
            _texto(c.get("n_dias")),
        ])
    return linhas + _tabela(["Comparação", "Métrica", "Diferença média", "Intervalo", "Dias"], tabela)


def _secao_modelo_3b(metricas: dict) -> list[str]:
    m = metricas.get("modelo_3b") or {}
    return [
        "## 9. Modelo 3b",
        "",
        "Nas previsões, o modelo 3b usa só as linhas do recorte `linhas_modelo_3b`.",
        "",
        f"- Linhas: {_texto(m.get('n_linhas'))}; dias: {_texto(m.get('n_dias'))}.",
        f"- AUC do modelo 3: {_num(m.get('auc_modelo_3'))}; AUC do modelo 1: {_num(m.get('auc_modelo_1'))}.",
        f"- AUC nas linhas fora do recorte: modelo 3, {_num(m.get('auc_modelo_3_fora'))}; "
        f"modelo 1, {_num(m.get('auc_modelo_1_fora'))}.",
    ]


def _secao_abertura(metricas: dict) -> list[str]:
    modelos = metricas.get("modelos") or {}
    com_abertura = []
    for nome in ORDEM_MODELOS:
        m = modelos.get(nome) or {}
        if m.get("abertura"):
            com_abertura.append((nome, m["abertura"]))
    linhas = ["## 10. Alvo de abertura", ""]
    if not com_abertura:
        return linhas + ["Sem dados de abertura."]
    referencia = dict(com_abertura).get("modelo_3", com_abertura[0][1])
    linhas += [
        f"Avaliado só em {_texto(referencia.get('n_dias_validos'))} de {_texto(referencia.get('n_dias_total'))} dias: "
        "nos outros a abertura do IBOV é igual ao fechamento anterior, defeito da fonte.",
        "",
    ]
    tabela = []
    for nome, ab in com_abertura:
        topk = ab.get("topk") or {}
        t5 = topk.get("5") or {}
        t3 = topk.get("3") or {}
        tabela.append([
            nome,
            _num(ab.get("auc_geral")),
            pct(t5.get("taxa_acerto")),
            ROTULO_ACASO.get(t5.get("vs_acaso"), NAO_INFORMADO),
            pct(t3.get("taxa_acerto")),
            ROTULO_ACASO.get(t3.get("vs_acaso"), NAO_INFORMADO),
        ])
    return linhas + _tabela(
        ["Modelo", "AUC", "Top 5: taxa", "Top 5: situação", "Top 3: taxa", "Top 3: situação"],
        tabela,
    )


def _secao_robustez(metricas: dict) -> list[str]:
    modelos = metricas.get("modelos") or {}
    linhas = ["## 11. Robustez por ano e sensibilidade", ""]
    for nome in ORDEM_MODELOS:
        m = modelos.get(nome)
        linhas += [f"### {nome}", ""]
        if not m:
            linhas += [f"{NAO_ENCONTRADO}.", ""]
            continue
        por_ano = m.get("por_ano") or []
        if por_ano:
            tabela = [
                [
                    _texto(a.get("ano")),
                    _texto(a.get("n_dias")),
                    pct(a.get("taxa_acerto_5")),
                    pct(a.get("excesso_5"), 2),
                    pct(a.get("taxa_acerto_3")),
                ]
                for a in por_ano
            ]
            linhas += _tabela(["Ano", "Dias", "Taxa top 5", "Excesso top 5", "Taxa top 3"], tabela) + [""]
        else:
            linhas += ["Sem dados por ano.", ""]
        sens = m.get("sensibilidade") or {}
        if sens.get("anteriores"):
            linhas += [
                f"Sensibilidade (corte {_texto(sens.get('corte'))}, último ano {_texto(sens.get('ultimo_ano'))}): "
                f"anteriores {_texto(sens.get('anteriores'))}.",
                "",
            ]
        else:
            linhas += ["Sensibilidade: sem dados: histórico curto.", ""]
    return linhas


def _secao_calibracao(metricas: dict) -> list[str]:
    cal = metricas.get("calibracao") or {}
    linhas = [
        "## 12. Calibração",
        "",
        f"- ECE: {_num(cal.get('ece'), 4)}; Brier: {_num(cal.get('brier'), 4)}; amostra: {_texto(cal.get('n'))}.",
        f"- Calibração aprovada: {_sim_nao(cal.get('aprovada'))}.",
        "- Chance exibida na interface." if cal.get("chance_exibida") else "- Chance não exibida.",
        "",
    ]
    return linhas + _tabela_de_dicts(cal.get("tabela"))


def _secao_exemplo(metricas: dict) -> list[str]:
    ex = metricas.get("exemplo_top")
    linhas = ["## 13. Exemplo de top 5", ""]
    if not ex:
        return linhas + ["Sem exemplo."]
    linhas += [f"Data: {_texto(ex.get('data'))}.", ""]
    top = ex.get("top") or []
    if top:
        for i, item in enumerate(top, 1):
            if not isinstance(item, dict):
                linhas.append(f"{i}. {_texto(item)}")
                continue
            chance = item.get("chance") or {}
            mostra = "não exibida (calibração não conferida)" if not chance.get("exibir") else pct(chance.get("valor"))
            linhas.append(f"{item.get('posicao')}. **{item.get('ticker')}**, chance: {mostra}. Motivos:")
            for m in item.get("motivos") or []:
                if not isinstance(m, dict):
                    linhas.append(f"   - {_texto(m)}")
                    continue
                linhas.append(
                    f"   - {m.get('fator')}: {m.get('efeito')} (contribuição {_texto(m.get('contribuicao'))}; "
                    f"valor {_texto(m.get('valor'))})"
                )
    else:
        linhas.append("Nenhum item no top do dia.")
    linhas += [
        "",
        f"- Sombra do modelo 1: {_texto(ex.get('sombra_modelo_1'))}.",
        f"- Sombra da volatilidade: {_texto(ex.get('sombra_volatilidade'))}.",
    ]
    return linhas


def _secao_modelo_salvo(metricas: dict) -> list[str]:
    ms = metricas.get("modelo_salvo")
    linhas = ["## 14. Modelo salvo", ""]
    if not ms:
        return linhas + [f"{NAO_ENCONTRADO}."]
    return linhas + [
        f"- Modelo 3 (arquivo): {_texto(ms.get('arquivo'))}.",
        f"- Modelo 1 (arquivo): {_texto(ms.get('arquivo_m1'))}.",
        "- Metadados: gravados ao lado de cada arquivo (`.meta.json`).",
    ]


def gerar_relatorio(metricas: dict) -> str:
    """Monta o Markdown do experimento a partir do dicionário do `metricas.json`."""
    periodo = metricas.get("periodo") or {}
    secoes = []
    if metricas.get("aviso_funcionamento"):
        secoes.append(_aviso(periodo))
    secoes.append(_titulo(metricas.get("modo")))
    secoes += [
        _secao_dados(metricas),
        _secao_noticias(metricas),
        _secao_dobras(metricas),
        _secao_selecao(metricas),
        _secao_topk(metricas),
        _secao_veredito(metricas),
        _secao_comparacoes(metricas),
        _secao_modelo_3b(metricas),
        _secao_abertura(metricas),
        _secao_robustez(metricas),
        _secao_calibracao(metricas),
        _secao_exemplo(metricas),
        _secao_modelo_salvo(metricas),
        ["---", RODAPE],
    ]
    saida = []
    for secao in secoes:
        saida += secao + [""]
    return "\n".join(saida).rstrip() + "\n"
