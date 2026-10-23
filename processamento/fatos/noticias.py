"""Notícias da janela do painel (etapa 7, Fase 3; plano seções 4.7 e 12).

Janela do painel = a mesma do modelo: de 08:00:01 de t até 08:00 de D (seção 7.2, `calendario.classificar_noticias`).
Notícia da empresa vale para todas as suas ações; mesmo `id` conta uma vez por empresa; repetidas por título (E10) saem.

Funções puras: DataFrames entram, DataFrames saem. Nenhuma acessa banco ou rede.
Entrada: DataFrame de `fontes.ler_noticias` (com `precisao_hora`, `momento_ref`, `fonte`, `link`).
"""

from __future__ import annotations

import pandas as pd

from processamento import calendario
from processamento.experimento.noticias import deduplicar, ligar_empresa
from processamento.experimento.parametros import ParametrosExperimento

COLUNAS_JANELA = [
    "id", "empresa", "titulo", "fonte", "link", "publicado_em", "data_publicacao", "precisao_hora",
    "janela", "momento", "prob_positivo", "prob_neutro", "prob_negativo", "score", "rotulo", "protagonista",
    "status",
]
CHAVES_RESUMO = ("quantidade", "positivas", "neutras", "negativas", "tom_medio")
_JANELAS_DO_CALENDARIO = ("noite", "pregao", "pre_abertura")
_SEM_HORA_NO_PAINEL = ("sem_hora", "meia_noite_pacifico")
_ROTULOS = ("positivo", "neutro", "negativo")


def rotulo(pp, pneu, pneg) -> str | None:
    """Rótulo = a maior das 3 probabilidades. Qualquer empate vira "neutro" (inclui positivo = negativo).

    None se alguma probabilidade for ausente (NaN/None).
    """
    valores = {"positivo": pp, "neutro": pneu, "negativo": pneg}
    if any(pd.isna(v) for v in valores.values()):
        return None
    maior = max(valores.values())
    topo = [nome for nome, v in valores.items() if v == maior]
    return topo[0] if len(topo) == 1 else "neutro"


def noticias_da_janela(
    noticias: pd.DataFrame,
    cal: list,
    t,
    proximo,
    cnpj_de: dict,
    mudancas: dict,
    params: ParametrosExperimento,
) -> pd.DataFrame:
    """Notícias de t na janela do painel (08:00:01 de t até 08:00 de D), uma linha por (empresa, id).

    `cal`: pregões ordenados; `t`: data de referência; `proximo`: próximo pregão (D), ainda sem preço.
    Saída: `COLUNAS_JANELA`. `janela` = "sem_horario" (sem hora real), "pregao" (pregão de t ou pré-abertura)
    ou "noite". `rotulo` e `status` ("indisponivel" se faltar probabilidade).
    """
    if noticias.empty:
        return pd.DataFrame(columns=COLUNAS_JANELA)
    e = ligar_empresa(noticias, cnpj_de, mudancas)
    protagonista = e.groupby(["empresa", "id"])["papel"].transform(lambda s: s.eq("protagonista").any())
    e = e.assign(protagonista=protagonista.fillna(False).astype(bool))
    u, _ = deduplicar(e, params)
    publicado_em = u["data_hora_publicacao"]
    momento = publicado_em.fillna(u["momento_ref"])
    base = u.assign(publicado_em=publicado_em, momento=momento)
    c = calendario.classificar_noticias(base.assign(data_hora_publicacao=momento), cal, proximo_ao_vivo=proximo)
    no_pregao_de_t = pd.to_datetime(c["pregao_ref"]).eq(pd.Timestamp(t))
    c = c[c["janela"].isin(_JANELAS_DO_CALENDARIO) & no_pregao_de_t]

    sem_horario = c["publicado_em"].isna() | c["precisao_hora"].isin(_SEM_HORA_NO_PAINEL)
    janela_painel = pd.Series("noite", index=c.index, dtype=object)
    janela_painel = janela_painel.where(~c["janela"].isin(["pregao", "pre_abertura"]), "pregao")
    janela_painel = janela_painel.where(~sem_horario, "sem_horario")

    rotulos = [rotulo(a, b, d) for a, b, d in zip(c["prob_positivo"], c["prob_neutro"], c["prob_negativo"])]
    saida = c.assign(
        janela=janela_painel,
        score=c["prob_positivo"] - c["prob_negativo"],
        rotulo=pd.Series(rotulos, index=c.index, dtype=object),
        status=pd.Series(["ok" if r is not None else "indisponivel" for r in rotulos], index=c.index, dtype=object),
    )
    return saida[COLUNAS_JANELA].reset_index(drop=True)


def destaque(df_empresa: pd.DataFrame) -> pd.DataFrame:
    """Ordena as notícias de uma empresa e põe `destaque` = 1..n.

    Ordem: protagonista primeiro, depois |score| decrescente, depois `momento` decrescente (mais recente),
    depois `id` crescente. Score ausente vai para o fim do seu critério.
    """
    com_abs = df_empresa.assign(_abs_score=df_empresa["score"].abs())
    ordenado = com_abs.sort_values(
        ["protagonista", "_abs_score", "momento", "id"],
        ascending=[False, False, False, True],
        na_position="last",
    )
    ordenado = ordenado.drop(columns="_abs_score").reset_index(drop=True)
    return ordenado.assign(destaque=list(range(1, len(ordenado) + 1)))


def resumo_noticias(df_empresa: pd.DataFrame, coberta: bool) -> dict[str, tuple[float, str]]:
    """Resumo da empresa: chaves `CHAVES_RESUMO`, cada uma (valor, status).

    `coberta` = t não é anterior ao início da cobertura (menor `data_publicacao` lida).
    Sem cobertura: tudo (NaN, "indisponivel"). Sem notícia: contagens 0 "ok" e tom_medio (NaN, "nao_se_aplica").
    Contagem com rótulo ausente, ou tom_medio com score ausente: "indisponivel".
    """
    if not coberta:
        return {chave: (float("nan"), "indisponivel") for chave in CHAVES_RESUMO}
    n = len(df_empresa)
    if n == 0:
        resumo = {chave: (0.0, "ok") for chave in CHAVES_RESUMO[:4]}
        resumo["tom_medio"] = (float("nan"), "nao_se_aplica")
        return resumo
    rotulos = df_empresa["rotulo"]
    rotulo_ausente = bool(rotulos.isna().any())

    def contagem(nome: str) -> tuple[float, str]:
        if rotulo_ausente:
            return (float("nan"), "indisponivel")
        return (float((rotulos == nome).sum()), "ok")

    scores = df_empresa["score"]
    if scores.isna().any():
        tom = (float("nan"), "indisponivel")
    else:
        tom = (float(scores.mean()), "ok")
    return {
        "quantidade": (float(n), "ok"),
        "positivas": contagem("positivo"),
        "neutras": contagem("neutro"),
        "negativas": contagem("negativo"),
        "tom_medio": tom,
    }


def ids_da_empresa(janela: pd.DataFrame, empresa: str) -> list[str]:
    """Ids da empresa na ordem do destaque (usado no noticias_dia e no experimento_top)."""
    da_empresa = janela[janela["empresa"] == empresa]
    return destaque(da_empresa)["id"].tolist()
