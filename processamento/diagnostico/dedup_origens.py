"""Medição da deduplicação entre origens (só leitura; não grava no banco).

`python -m processamento.diagnostico.dedup_origens` grava `docs/medicao_dedup_origens.md` e
`docs/medicao_dedup_origens_amostra.csv`. Tudo sai de `fontes` (leitura padrão, `ler_noticias` com
`com_url_resolvida=True`). As contas das seções 1 e 2 são funções sobre DataFrames; `carregar_entradas(ler)`
aceita um leitor falso (testes).

Seções: 1 cópias removidas por regra; 2 pares por URL entre origens; 3 amostra de 20 pares removidos;
4 invariância (versão antiga × nova, anos de 2023 a 2025); 5 tempos.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import statistics
import time
from pathlib import Path

import pandas as pd

from processamento import calendario, fontes
from processamento.diagnostico.relatorio import tabela_md
from processamento.experimento import noticias as expn
from processamento.experimento.parametros import ParametrosExperimento, carregar_parametros_experimento
from processamento.fatos.precos import mapas_cadastro
from processamento.tickers import mapas_por_empresa
from processamento.texto_noticias import chave_url

ORIGEM_CVM = "cvm_ipe"
REGRAS_TITULO = ("titulo_mesmo_dia", "titulo_janela")
REGRAS = (*REGRAS_TITULO, "url")
SEMENTE_AMOSTRA = 20261101
COTAS_AMOSTRA = {"titulo_mesmo_dia": 8, "titulo_janela": 6, "url": 6}
TAMANHO_AMOSTRA = sum(COTAS_AMOSTRA.values())
ANOS_INVARIANCIA = (2023, 2024, 2025)
REPETICOES = 3
EXEMPLOS_INVARIANCIA = 10
COLUNAS_AMOSTRA = [
    "empresa", "ticker_removido", "ticker_mantido", "regra", "tambem_url", "origem_removido", "origem_mantido",
    "titulo_removido", "titulo_mantido", "data_removido", "data_mantido", "dias",
]
CAMINHO_MD = fontes.RAIZ / "docs" / "medicao_dedup_origens.md"
CAMINHO_CSV = fontes.RAIZ / "docs" / "medicao_dedup_origens_amostra.csv"


# ---------------------------------------------------------------- leitura (única parte que toca a fonte)

def carregar_entradas(ler=None) -> dict:
    """Lê calendário, cadastro, mudanças e as notícias com e sem a origem wordpress (com a URL resolvida).

    Liga a empresa como o dataset faz (`mapas_cadastro` + `mapas_por_empresa`). Só lê.
    """
    precos = fontes.ler_tabela("precos", ler=ler)
    cal = calendario.pregoes(precos)
    cadastro = fontes.ler_tabela("cadastro", ler=ler)
    mudancas = fontes.ler_mudancas(ler)
    novo = fontes.ler_noticias(ler=ler, com_url_resolvida=True)
    antigo = fontes.ler_noticias(ler=ler, com_url_resolvida=True, origens_ignoradas=["wordpress"])
    setor_de, cnpj_de = mapas_cadastro(cadastro)
    tickers = sorted(set(novo["ticker"]))
    _, cnpj_de, _ = mapas_por_empresa(tickers, setor_de, cnpj_de, mudancas)
    return {"cal": cal, "cnpj_de": cnpj_de, "mudancas": mudancas, "novo": novo, "antigo": antigo}


# ---------------------------------------------------------------- contas (funções de DataFrame)

def _url_da_linha(resolved, link) -> str | None:
    """`resolved_url` se for texto não vazio; senão `link`; None se nenhum."""
    for valor in (resolved, link):
        if isinstance(valor, str) and valor.strip():
            return valor
    return None


def pares_por_url(com: pd.DataFrame) -> pd.DataFrame:
    """Todos os pares de linhas de origens diferentes com a mesma empresa e a mesma `chave_url` (antes de remover).

    `com`: notícias com a coluna `empresa` (saída de `ligar_empresa`). cvm_ipe fica de fora, como na remoção.
    `dias` é |data_publicacao| entre as duas (None se faltar data).
    """
    colunas = ["empresa", "uk", "origem_a", "origem_b", "dias"]
    cand = com[com["origem"] != ORIGEM_CVM]
    resolvidas = cand["resolved_url"] if "resolved_url" in cand.columns else pd.Series(None, index=cand.index)
    ligados = cand["link"] if "link" in cand.columns else pd.Series(None, index=cand.index)
    base = pd.DataFrame({
        "empresa": cand["empresa"].to_numpy(),
        "uk": [chave_url(_url_da_linha(r, l)) for r, l in zip(resolvidas, ligados)],
        "origem": cand["origem"].to_numpy(),
        "data": pd.to_datetime(cand["data_publicacao"]).to_numpy(),
    }).dropna(subset=["uk"])
    linhas: list[dict] = []
    for (empresa, uk), grupo in base.groupby(["empresa", "uk"]):
        if grupo["origem"].nunique() < 2:
            continue
        for a, b in itertools.combinations(grupo.itertuples(index=False), 2):
            if a.origem == b.origem:
                continue
            dias = abs((a.data - b.data).days) if pd.notna(a.data) and pd.notna(b.data) else None
            linhas.append({"empresa": empresa, "uk": uk, "origem_a": a.origem, "origem_b": b.origem, "dias": dias})
    return pd.DataFrame(linhas, columns=colunas)


def secao_remocoes(pares: pd.DataFrame, pares_sem_minimo: pd.DataFrame, pares_min5: pd.DataFrame) -> dict:
    """Seção 1: cópias removidas por regra, por ano, quantas de título também casam por URL, pares por origem.

    `pares`: com o mínimo de palavras configurado; `pares_sem_minimo`: mínimo 0 (só contagem).
    `segurados`: cópias de título que só o mínimo de palavras impediu (mínimo 0 menos o configurado).
    """
    total = {regra: int((pares["regra"] == regra).sum()) for regra in REGRAS}
    if pares.empty:
        por_ano = pd.DataFrame(columns=["ano", *REGRAS, "total"])
        por_origem = pd.DataFrame(columns=["origem_removida", "origem_mantida", "pares"])
    else:
        anos = pd.to_datetime(pares["data_removido"]).dt.year.rename("ano")
        por_ano = pares.groupby([anos, "regra"]).size().unstack(fill_value=0).reindex(columns=list(REGRAS), fill_value=0)
        por_ano["total"] = por_ano.sum(axis=1)
        por_ano = por_ano.reset_index()
        por_origem = (
            pares.groupby(["origem_removido", "origem_mantido"]).size().reset_index(name="pares")
            .rename(columns={"origem_removido": "origem_removida", "origem_mantido": "origem_mantida"})
        )
    titulo_com_url = int((pares["regra"].isin(REGRAS_TITULO) & pares["tambem_url"].astype(bool)).sum())
    titulos_sem_minimo = int(pares_sem_minimo["regra"].isin(REGRAS_TITULO).sum())
    titulos_min5 = int(pares_min5["regra"].isin(REGRAS_TITULO).sum())
    return {
        "total": total,
        "por_ano": por_ano,
        "titulo_com_url": titulo_com_url,
        "por_origem": por_origem,
        "segurados": titulos_sem_minimo - titulos_min5,
        "url_fora_de_um_dia": int(((pares["regra"] == "url") & (_dias(pares) > 1)).sum()),
    }


def _dias(pares: pd.DataFrame) -> pd.Series:
    """Coluna `dias` como número (None vira NaN)."""
    return pd.to_numeric(pares["dias"], errors="coerce")


def secao_url(pares_url: pd.DataFrame) -> dict:
    """Seção 2: pares por URL entre origens (todos): total, dentro e fora de ±1 dia, distribuição de |dias| fora."""
    dias = _dias(pares_url).dropna()
    fora = dias[dias > 1]
    return {
        "total": len(pares_url),
        "dentro": int((dias <= 1).sum()),
        "fora": int(len(fora)),
        "sem_data": int(_dias(pares_url).isna().sum()),
        "faixas": {
            "2 a 7 dias": int(((fora >= 2) & (fora <= 7)).sum()),
            "8 a 30 dias": int(((fora >= 8) & (fora <= 30)).sum()),
            "mais de 30 dias": int((fora > 30).sum()),
        },
    }


def amostra(pares: pd.DataFrame, semente: int = SEMENTE_AMOSTRA) -> pd.DataFrame:
    """Seção 3: até 8 `titulo_mesmo_dia`, 6 `titulo_janela` e 6 `url` (sorteio com semente fixa).

    Se uma regra tiver menos pares, a falta é completada com pares sorteados das outras regras.
    """
    escolhidos = [
        pares[pares["regra"] == regra].sample(n=min(cota, int((pares["regra"] == regra).sum())), random_state=semente)
        for regra, cota in COTAS_AMOSTRA.items()
    ]
    marcados = pd.concat(escolhidos) if escolhidos else pares.iloc[0:0]
    falta = TAMANHO_AMOSTRA - len(marcados)
    resto = pares.drop(index=marcados.index)
    if falta > 0 and len(resto):
        marcados = pd.concat([marcados, resto.sample(n=min(falta, len(resto)), random_state=semente)])
    return marcados[COLUNAS_AMOSTRA].reset_index(drop=True)


def comparar_invariancia(
    entrada_antiga: pd.DataFrame,
    entrada_nova: pd.DataFrame,
    cal: list,
    cnpj_de: dict,
    mudancas: dict,
    params_antigos: ParametrosExperimento,
    params_novos: ParametrosExperimento,
    anos: tuple = ANOS_INVARIANCIA,
) -> dict:
    """Seção 4: versão 'todas' antiga × nova; compara só as linhas com data de publicação nos `anos`.

    Antiga: origem wordpress ignorada e sem deduplicação entre origens. Nova: a configuração do plano.
    Diferença = (id, ticker) presente num lado só ou com janela, pregão de referência, momento ou score diferentes.
    """
    antiga, _ = expn.preparar_noticias(entrada_antiga, cal, cnpj_de, mudancas, "todas", params_antigos)
    nova, _ = expn.preparar_noticias(entrada_nova, cal, cnpj_de, mudancas, "todas", params_novos)
    colunas = ["janela", "pregao_ref", "momento", "score"]
    chaves_antigas = _chaves_nos_anos(entrada_antiga, anos)
    chaves_novas = _chaves_nos_anos(entrada_nova, anos)
    a = antiga.merge(chaves_antigas, on=["id", "ticker"])[["id", "ticker", *colunas]]
    b = nova.merge(chaves_novas, on=["id", "ticker"])[["id", "ticker", *colunas]]
    juntas = a.merge(b, on=["id", "ticker"], how="outer", suffixes=("_antiga", "_nova"), indicator=True)
    diferente = juntas["_merge"] != "both"
    for c in colunas:
        x, y = juntas[f"{c}_antiga"], juntas[f"{c}_nova"]
        diferente |= ~((x == y) | (x.isna() & y.isna()))
    exemplos = juntas.loc[diferente, ["id", "ticker", *[f"{c}_antiga" for c in colunas], *[f"{c}_nova" for c in colunas]]]
    return {
        "linhas_antigas": len(a),
        "linhas_novas": len(b),
        "diferencas": int(diferente.sum()),
        "exemplos": exemplos.head(EXEMPLOS_INVARIANCIA).reset_index(drop=True),
    }


def _chaves_nos_anos(noticias: pd.DataFrame, anos: tuple) -> pd.DataFrame:
    """(id, ticker) das linhas cuja data de publicação cai nos `anos`."""
    ano = pd.to_datetime(noticias["data_publicacao"]).dt.year
    return noticias.loc[ano.isin(anos), ["id", "ticker"]].drop_duplicates()


def _mediana(valores: list[float]) -> float:
    return statistics.median(valores)


def medir_tempos(entradas: dict, params: ParametrosExperimento, ler=None) -> dict:
    """Seção 5: `ler_noticias` com e sem URL resolvida (alternados), `ler_urls_resolvidas` e deduplicação ligada × desligada.

    Cada medida é a mediana de `REPETICOES` execuções (em segundos).
    """
    sem, com, urls = [], [], []
    for _ in range(REPETICOES):
        t0 = time.perf_counter()
        fontes.ler_noticias(ler=ler)
        sem.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        fontes.ler_noticias(ler=ler, com_url_resolvida=True)
        com.append(time.perf_counter() - t0)
    linhas_urls = 0
    for _ in range(REPETICOES):
        t0 = time.perf_counter()
        linhas_urls = len(fontes.ler_urls_resolvidas(ler=ler))
        urls.append(time.perf_counter() - t0)
    base = entradas["novo"]
    com_empresa = expn.ligar_empresa(base, entradas["cnpj_de"], entradas["mudancas"])
    ligada, desligada = [], []
    params_desligada = dataclasses.replace(params, deduplicar_entre_origens=False)
    for _ in range(REPETICOES):
        t0 = time.perf_counter()
        expn.deduplicar(com_empresa, params)
        ligada.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        expn.deduplicar(com_empresa, params_desligada)
        desligada.append(time.perf_counter() - t0)
    return {
        "ler_sem_url": _mediana(sem),
        "ler_com_url": _mediana(com),
        "ler_urls": _mediana(urls),
        "linhas_urls": linhas_urls,
        "linhas_noticias": len(base),
        "dedup_ligada": _mediana(ligada),
        "dedup_desligada": _mediana(desligada),
    }


def calcular(entradas: dict, params: ParametrosExperimento, ler=None) -> dict:
    """Todas as seções (1 a 5) sobre as entradas lidas por `carregar_entradas`."""
    com = expn.ligar_empresa(expn.filtrar_versao(entradas["novo"], "todas", params)[0],
                             entradas["cnpj_de"], entradas["mudancas"])
    _, _, pares = expn.deduplicar_com_pares(com, params)
    _, _, pares_sem_minimo = expn.deduplicar_com_pares(
        com, dataclasses.replace(params, titulo_palavras_min_entre_origens=0))
    remocoes = secao_remocoes(pares, pares_sem_minimo, pares)
    url = secao_url(pares_por_url(com))
    url["remocoes_url_fora_de_um_dia"] = remocoes["url_fora_de_um_dia"]
    invariancia = comparar_invariancia(
        entradas["antigo"], entradas["novo"], entradas["cal"], entradas["cnpj_de"], entradas["mudancas"],
        dataclasses.replace(params, deduplicar_entre_origens=False), params,
    )
    tempos = medir_tempos(entradas, params, ler=ler)
    return {"remocoes": remocoes, "url": url, "amostra": amostra(pares), "invariancia": invariancia,
            "tempos": tempos, "parametros": params}


# ---------------------------------------------------------------- relatório

def _fmt_seg(v: float) -> str:
    return f"{v:.3f} s"


def relatorio(resultado: dict) -> str:
    """Markdown com as cinco seções."""
    rem, url, inv, tem = resultado["remocoes"], resultado["url"], resultado["invariancia"], resultado["tempos"]
    p = resultado["parametros"]
    partes = [
        "# Medição da deduplicação entre origens",
        f"Parâmetros: janela de {p.janela_dias_entre_origens} dia(s), mínimo de "
        f"{p.titulo_palavras_min_entre_origens} palavras no título, deduplicar_titulo={p.deduplicar_titulo}. "
        "Medição só de leitura; nada foi gravado no banco. Gerado por "
        "`python -m processamento.diagnostico.dedup_origens`.",
        "## 1. Cópias removidas por regra",
        tabela_md(["regra", "cópias removidas"], [[r, rem["total"][r]] for r in REGRAS])
        + f"\n\nCópias de título que também casam por URL: {rem['titulo_com_url']}. "
        f"Cópias de título que o mínimo de {p.titulo_palavras_min_entre_origens} palavras segurou "
        f"(rodando com mínimo 0): {rem['segurados']}.",
        "### Por ano",
        tabela_md(["ano", *REGRAS, "total"], rem["por_ano"].values.tolist()) if not rem["por_ano"].empty else "_Nenhuma cópia removida._",
        "### Pares por origem removida × mantida",
        tabela_md(["origem removida", "origem mantida", "pares"], rem["por_origem"].values.tolist())
        if not rem["por_origem"].empty else "_Nenhum par._",
        "## 2. Pares por URL entre origens (todos, antes de remover)",
        tabela_md(["medida", "pares"], [
            ["total", url["total"]],
            ["dentro de ±1 dia", url["dentro"]],
            ["fora de ±1 dia", url["fora"]],
            ["sem data (não entram nas faixas)", url["sem_data"]],
            *[[f"fora: {k}", v] for k, v in url["faixas"].items()],
            ["remoções da regra url fora de ±1 dia", url["remocoes_url_fora_de_um_dia"]],
        ]),
        "## 3. Amostra de pares removidos",
        f"{len(resultado['amostra'])} pares, sorteio com semente {SEMENTE_AMOSTRA}, estratificado "
        f"({', '.join(f'até {v} {k}' for k, v in COTAS_AMOSTRA.items())}). Detalhes em "
        "`docs/medicao_dedup_origens_amostra.csv`.",
        tabela_md(["ticker removido", "ticker mantido", "regra", "origem removida", "origem mantida",
                   "data removida", "data mantida"],
                  [[r.ticker_removido, r.ticker_mantido, r.regra, r.origem_removido, r.origem_mantido,
                    str(pd.Timestamp(r.data_removido).date()), str(pd.Timestamp(r.data_mantido).date())]
                   for r in resultado["amostra"].itertuples(index=False)])
        if not resultado["amostra"].empty else "_Nenhum par removido._",
        "## 4. Invariância (versão 'todas', antiga × nova)",
        f"Antiga: wordpress ignorada e sem deduplicação entre origens. Nova: configuração do plano. "
        f"Linhas comparadas (anos {', '.join(map(str, ANOS_INVARIANCIA))}): {inv['linhas_antigas']} antigas × "
        f"{inv['linhas_novas']} novas. **Diferenças: {inv['diferencas']}.**",
    ]
    if inv["diferencas"]:
        partes.append(tabela_md(list(inv["exemplos"].columns), inv["exemplos"].astype(str).values.tolist()))
    partes += [
        "## 5. Tempos (mediana de 3 execuções)",
        tabela_md(["medida", "tempo", "linhas"], [
            ["ler_noticias sem URL resolvida", _fmt_seg(tem["ler_sem_url"]), tem["linhas_noticias"]],
            ["ler_noticias com URL resolvida", _fmt_seg(tem["ler_com_url"]), tem["linhas_noticias"]],
            ["ler_urls_resolvidas", _fmt_seg(tem["ler_urls"]), tem["linhas_urls"]],
            ["deduplicar com regra entre origens ligada", _fmt_seg(tem["dedup_ligada"]), tem["linhas_noticias"]],
            ["deduplicar com regra entre origens desligada", _fmt_seg(tem["dedup_desligada"]), tem["linhas_noticias"]],
        ]),
    ]
    return "\n\n".join(partes) + "\n"


def amostra_csv(resultado: dict) -> pd.DataFrame:
    return resultado["amostra"]


# ---------------------------------------------------------------- ponto de entrada

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Medição da deduplicação entre origens (só leitura).")
    parser.add_argument("--saida", type=Path, default=CAMINHO_MD, help="arquivo Markdown de saída")
    parser.add_argument("--amostra", type=Path, default=CAMINHO_CSV, help="CSV da amostra")
    args = parser.parse_args(argv)
    params = carregar_parametros_experimento()
    entradas = carregar_entradas()
    resultado = calcular(entradas, params)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(relatorio(resultado), encoding="utf-8")
    amostra_csv(resultado).to_csv(args.amostra, index=False, encoding="utf-8")
    print(f"relatório: {args.saida}")
    print(f"amostra: {args.amostra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
