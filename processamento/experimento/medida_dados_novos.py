"""Medida de dados novos (D5 esclarecida): quanto do desenvolvimento muda quando o dataset é regenerado.

Compara um dataset regenerado ("novo") com o dataset congelado da rodada oficial ("congelado"), só no período de
desenvolvimento (`treino.ler_desenvolvimento`: sem o teste final e sem o embargo antes dele). Linhas são chaveadas por
(data, ticker). Colunas comparadas: `colunas_3` do congelado mais `alvo`, com os valores que o modelo recebe (ranks por
pregão de `preparacao.preparar`).

Célula mudada: nos valores preparados (ranks, o que o modelo recebe) vazia de um lado e preenchida do outro, ou
|novo − congelado| > 1e-6 (estritamente maior); E, no valor BRUTO do CSV (antes do rank; a coluna de origem, ver
`preparacao.COLUNA_BRUTA`), o mesmo critério. A diferença é arredondada a 12 casas antes da comparação, para o ruído de
ponto flutuante não decidir a fronteira de 1e-6. Regra de 09/11/2026 ("rank E bruto"): o critério do bruto existe porque
ruído do float32 em valores quase empatados perto de zero (ex.: `salto_abertura` quando a abertura é igual ao fechamento
anterior) muda o rank sem mudar o dado (medida de 09/11/2026, protocolo seção 8, nota da D5).
Linha mudada: alguma célula mudada, ou a chave existe em só um dos dois lados.

Denominador: linhas com `alvo` preenchido no congelado. Linhas que só existem no novo, ou cujo `alvo` vazio no congelado
fica preenchido no novo, entram no numerador (linhas mudadas) mas não no denominador.

Decisão: fração total > 1% → "nova_rodada"; senão "rodada_oficial_continua". Além disso, `parar_e_perguntar` quando a
fração do grupo preco_e_alvo passa de 1% (regra D7), mesmo que o total não passe. Exatamente 1% não passa.

Exploratório. Não constitui recomendação de investimento. Só lê os CSV pelo `treino` (nada do banco, nada do teste final)
e não altera a configuração congelada.

Uso: python -m processamento.experimento.medida_dados_novos --congelado-csv <csv> --novo-csv <csv>
     --congelado docs/protocolo_congelado_rodada_NNN.json [--pasta-docs docs] [--data AAAA-MM-DD]
Saídas: docs/medida_dados_novos_<data>.md e .json. Nunca sobrescreve: se já existirem, erro e nada é gravado.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from processamento import fontes
from processamento.experimento import preparacao, treino
from processamento.experimento.parametros import carregar_parametros_treino

PASTA_DOCS_PADRAO = fontes.RAIZ / "docs"
NOME_BASE = "medida_dados_novos"
CHAVES = ["data", "ticker"]
TOLERANCIA = 1e-6
REGRA = "2026-11-09: rank E bruto"                        # versão do critério de célula mudada (antes: só o rank)
LIMITE = 0.01                                             # acima disso a decisão muda; exatamente 1% não passa
GRUPO_NOTICIAS = [*preparacao.NOTICIAS_DIA, preparacao.EXTREMO_RANK]
GRUPOS_NOMES = ("preco_bloco_a", "noticias", "alvo", "preco_e_alvo")
NOMES_GRUPOS = {
    "preco_bloco_a": "Preço (bloco A)",
    "noticias": "Notícias",
    "alvo": "Alvo",
    "preco_e_alvo": "Preço e alvo (regra D7)",
}


class ErroMedida(Exception):
    """Dados que não batem com a medida: chave repetida, coluna faltando, congelado de outro dataset, saída já existente."""


def colunas_comparadas(congelado: dict) -> list[str]:
    """`colunas_3` do congelado mais `alvo`. Com `extremo_em_rank` no congelado, o extremo entra como rank (mesmo mapeamento de `treino`)."""
    colunas = list(congelado["colunas_3"])
    if congelado.get("extremo_em_rank"):
        colunas = [preparacao.EXTREMO_RANK if c == "noticias_dia_extremo" else c for c in colunas]
    return list(dict.fromkeys([*colunas, "alvo"]))


def ler_preparado(csv: Path, params) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Desenvolvimento do CSV (`treino.ler_desenvolvimento`, com o JSON ao lado): (preparado, bruto, info).

    `preparado` é `preparacao.preparar` (a preparação do treino); `bruto` é o mesmo período antes do rank, com as colunas do dataset.
    Usa `preparacao.preparar` e não `treino.preparar_dev`: esse tira as linhas sem alvo, e a regra conta essas linhas
    (uma que muda entra no numerador). Os ranks são feitos antes de qualquer filtro, então os valores são os que o modelo recebe.
    """
    df, info = treino.ler_desenvolvimento(csv, params)
    return preparacao.preparar(df), df, info


def _grupos(colunas: list[str]) -> dict[str, list[str]]:
    """Grupos da regra: preco_bloco_a (preço, sem notícia nem alvo), noticias, alvo e preco_e_alvo (preço ∪ alvo)."""
    noticias = [c for c in colunas if c in GRUPO_NOTICIAS]
    alvo = [c for c in colunas if c == "alvo"]
    preco = [c for c in colunas if c not in GRUPO_NOTICIAS and c != "alvo"]
    return {"preco_bloco_a": preco, "noticias": noticias, "alvo": alvo, "preco_e_alvo": preco + alvo}


def _mudou_celula(a: pd.Series, b: pd.Series) -> np.ndarray:
    """Célula mudada: vazia de um lado e preenchida do outro, ou diferença > TOLERANCIA (arredondada a 12 casas)."""
    va = a.to_numpy(dtype=float)
    vb = b.to_numpy(dtype=float)
    nan_a, nan_b = np.isnan(va), np.isnan(vb)
    diferenca = np.round(np.abs(va - vb), 12)            # NaN onde falta um dos lados; comparação com NaN dá False
    return (nan_a != nan_b) | (~nan_a & ~nan_b & (diferenca > TOLERANCIA))


def _brutas(colunas: list[str]) -> list[str]:
    """Coluna do dataset de cada coluna preparada (`preparacao.COLUNA_BRUTA`; as demais são iguais)."""
    return list(dict.fromkeys(preparacao.COLUNA_BRUTA.get(c, c) for c in colunas))


def _lado(preparado: pd.DataFrame, bruto: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Chave, valores preparados (`cols`) e brutos (`bruto__<coluna do dataset>`) de um lado. As duas fontes têm de ter as mesmas linhas."""
    b = bruto[CHAVES + _brutas(cols)].rename(columns={c: f"bruto__{c}" for c in _brutas(cols)})
    j = preparado[CHAVES + cols].merge(b, on=CHAVES, how="outer", indicator=True)
    if (j["_merge"] != "both").any():
        raise ErroMedida("preparado e bruto têm linhas diferentes")
    return j.drop(columns="_merge")


def medir(df_congelado: pd.DataFrame, df_novo: pd.DataFrame, colunas: list[str],
          bruto_congelado: pd.DataFrame, bruto_novo: pd.DataFrame) -> dict:
    """Mede a mudança entre o congelado e o novo. Função pura: sem leitura nem gravação.

    `df_*`: linhas preparadas (uma por data × ticker) com as colunas de `colunas`, que tem de incluir `alvo`.
    `bruto_*`: as mesmas linhas antes do rank, com as colunas de origem de `colunas` (`preparacao.COLUNA_BRUTA`).
    Célula mudada: o critério vale no preparado E no bruto (ver o docstring do módulo).
    Denominador: linhas com `alvo` preenchido no congelado (ver o docstring do módulo). ErroMedida se faltar coluna,
    se a chave (data, ticker) se repetir ou se o congelado não tiver nenhuma linha com alvo.
    """
    if "alvo" not in colunas:
        raise ErroMedida("a medida precisa da coluna alvo")
    cols = list(dict.fromkeys(colunas))
    brutas = _brutas(cols)
    for nome, df, bruto in (("congelado", df_congelado, bruto_congelado), ("novo", df_novo, bruto_novo)):
        faltando = [c for c in [*CHAVES, *cols] if c not in df.columns]
        if faltando:
            raise ErroMedida(f"{nome}: faltam colunas {faltando}")
        if df.duplicated(CHAVES).any():
            raise ErroMedida(f"{nome}: chave (data, ticker) repetida")
        faltando_bruto = [c for c in [*CHAVES, *brutas] if c not in bruto.columns]
        if faltando_bruto:
            raise ErroMedida(f"{nome} (bruto): faltam colunas {faltando_bruto}")
        if bruto.duplicated(CHAVES).any():
            raise ErroMedida(f"{nome} (bruto): chave (data, ticker) repetida")

    m = _lado(df_congelado, bruto_congelado, cols).merge(_lado(df_novo, bruto_novo, cols), on=CHAVES, how="outer",
                                                         suffixes=("_c", "_n"), indicator=True)
    so_c = (m["_merge"] == "left_only").to_numpy()
    so_n = (m["_merge"] == "right_only").to_numpy()
    solo = so_c | so_n
    ambos = ~solo
    alvo_c = m["alvo_c"].notna().to_numpy()                # só linhas do congelado têm alvo_c preenchido
    denominador = int(alvo_c.sum())
    if denominador == 0:
        raise ErroMedida("o congelado não tem nenhuma linha com alvo no desenvolvimento")

    mudou = {}
    for c in cols:
        bruta = f"bruto__{preparacao.COLUNA_BRUTA.get(c, c)}"
        mudou[c] = _mudou_celula(m[f"{c}_c"], m[f"{c}_n"]) & _mudou_celula(m[f"{bruta}_c"], m[f"{bruta}_n"]) & ambos

    def linhas(colunas_do_grupo: list[str]) -> np.ndarray:
        """Linhas com alguma célula mudada no grupo. Linha que existe só de um lado conta em todos os grupos."""
        marcadas = solo.copy()
        for c in colunas_do_grupo:
            marcadas |= mudou[c]
        return marcadas

    definicao = _grupos(cols)
    grupos = {}
    for nome in GRUPOS_NOMES:
        n = int(linhas(definicao[nome]).sum())
        grupos[nome] = {"colunas": definicao[nome], "linhas_mudadas": n, "fracao": n / denominador}

    mudou_linha = linhas(cols)
    total = int(mudou_linha.sum())
    fracao_total = total / denominador

    anos = m["data"].dt.year.to_numpy()
    por_ano = []
    for ano in sorted(set(anos.tolist())):
        no_ano = anos == ano
        den = int((alvo_c & no_ano).sum())
        mud = int((mudou_linha & no_ano).sum())
        por_ano.append({"ano": int(ano), "denominador": den, "linhas_mudadas": mud,
                        "fracao": mud / den if den else None})

    contagem = m.loc[mudou_linha, "ticker"].value_counts()
    top = sorted(((str(t), int(n)) for t, n in contagem.items()), key=lambda par: (-par[1], par[0]))[:10]

    return {
        "decisao": "nova_rodada" if fracao_total > LIMITE else "rodada_oficial_continua",
        "parar_e_perguntar": grupos["preco_e_alvo"]["fracao"] > LIMITE,
        "limite": LIMITE,
        "tolerancia": TOLERANCIA,
        "regra": REGRA,
        "fracao_total": fracao_total,
        "linhas_mudadas": total,
        "denominador": denominador,
        "grupos": grupos,
        "por_ano": por_ano,
        "top_tickers": [{"ticker": t, "linhas_mudadas": n} for t, n in top],
        "contagens": {
            "linhas_congelado": len(df_congelado),
            "linhas_novo": len(df_novo),
            "linhas_comparadas": int(ambos.sum()),
            "so_congelado": int(so_c.sum()),
            "so_novo": int(so_n.sum()),
            "denominador": denominador,
        },
    }


# ---------------------------------------------------------------------------
# Gravação e relatório
# ---------------------------------------------------------------------------

def _caminhos_saida(pasta_docs: Path, data: date) -> tuple[Path, Path]:
    md = Path(pasta_docs) / f"{NOME_BASE}_{data.isoformat()}.md"
    js = Path(pasta_docs) / f"{NOME_BASE}_{data.isoformat()}.json"
    for caminho in (md, js):
        if caminho.exists():
            raise ErroMedida(f"{caminho.name} já existe: medidas nunca são sobrescritas")
    return md, js


def _gravar_novo(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "x", encoding="utf-8", newline="\n") as arq:
        arq.write(texto)


def gravar_saidas(pasta_docs, texto_md: str, resultado: dict, data: date) -> tuple[Path, Path]:
    """Grava o .md e o .json, os dois novos. Se algum já existir, ErroMedida e nada é gravado."""
    caminho_md, caminho_json = _caminhos_saida(Path(pasta_docs), data)
    _gravar_novo(caminho_md, texto_md)
    _gravar_novo(caminho_json, json.dumps(treino._para_json(resultado), ensure_ascii=False, indent=2))
    return caminho_md, caminho_json


def executar(csv_congelado: Path, csv_novo: Path, congelado: Path, pasta_docs, *, data: date, params=None) -> tuple[Path, Path]:
    """Mede o desenvolvimento dos dois CSV e grava o relatório e o JSON, ambos novos.

    Antes de medir, confere que o CSV congelado é o dataset do protocolo (sha256 igual ao `sha256_dataset` do congelado).
    """
    params = carregar_parametros_treino() if params is None else params
    _caminhos_saida(Path(pasta_docs), data)                # falha cedo se a saída já existir
    protocolo = json.loads(Path(congelado).read_text(encoding="utf-8"))
    df_c, bruto_c, info_c = ler_preparado(csv_congelado, params)
    df_n, bruto_n, info_n = ler_preparado(csv_novo, params)
    if protocolo.get("sha256_dataset") != info_c["sha256"]:
        raise ErroMedida("o CSV congelado não é o dataset do protocolo congelado (sha256 diferente)")

    resultado = {
        "exploratorio": True,
        "data": data.isoformat(),
        "congelado": {"arquivo": Path(csv_congelado).name, "sha256": info_c["sha256"],
                      "protocolo": Path(congelado).name, "rodada": protocolo.get("rodada")},
        "novo": {"arquivo": Path(csv_novo).name, "sha256": info_n["sha256"]},
        "versao_preparacao": info_n["versao_preparacao"],
        **medir(df_c, df_n, colunas_comparadas(protocolo), bruto_c, bruto_n),
    }
    return gravar_saidas(pasta_docs, _relatorio(resultado), resultado, data)


def _num(valor, casas: int = 6) -> str:
    if valor is None:
        return "n/d"
    return f"{valor:.{casas}f}".replace(".", ",")


def _tabela(cabecalho: list[str], linhas: list[list]) -> list[str]:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join("n/d" if c is None else str(c) for c in linha) + " |" for linha in linhas]
    return saida


def _relatorio(r: dict) -> str:
    """Markdown da medida: decisão, frações por grupo, contagens, por ano, top 10 tickers, datasets e regras."""
    g = r["grupos"]
    decisao = {"nova_rodada": "nova rodada", "rodada_oficial_continua": "rodada oficial continua"}[r["decisao"]]
    linhas = [
        "# Medida de dados novos (D5 esclarecida)",
        "",
        "> Exploratório. Medida só do desenvolvimento, sem abrir o teste final. Não constitui recomendação de investimento.",
        "",
        f"Data da medida: {r['data']}. Congelado: `{r['congelado']['protocolo']}` (rodada {r['congelado']['rodada']}).",
        "",
        "## Decisão",
        "",
        f"- Decisão: **{decisao}** (`{r['decisao']}`).",
        f"- Fração total: {r['linhas_mudadas']} ÷ {r['denominador']} = {_num(r['fracao_total'])} "
        f"(limite {_num(r['limite'], 2)}; exatamente o limite não passa).",
        f"- Parar e perguntar (D7): {'sim' if r['parar_e_perguntar'] else 'não'} "
        f"(fração de preço e alvo {_num(g['preco_e_alvo']['fracao'])}).",
        "",
        "## Frações por grupo",
        "",
    ]
    linhas += _tabela(
        ["Grupo", "Colunas", "Linhas mudadas", "Fração"],
        [[NOMES_GRUPOS[n], ", ".join(g[n]["colunas"]) or "—", g[n]["linhas_mudadas"], _num(g[n]["fracao"])]
         for n in GRUPOS_NOMES],
    )
    contagens = r["contagens"]
    linhas += ["", "## Contagens", ""]
    linhas += _tabela(
        ["Item", "Valor"],
        [["Linhas do congelado (desenvolvimento)", contagens["linhas_congelado"]],
         ["Linhas do novo (desenvolvimento)", contagens["linhas_novo"]],
         ["Linhas comparadas (nos dois)", contagens["linhas_comparadas"]],
         ["Só no congelado", contagens["so_congelado"]],
         ["Só no novo", contagens["so_novo"]],
         ["Denominador (alvo preenchido no congelado)", contagens["denominador"]]],
    )
    linhas += ["", "## Por ano (ano da data)", ""]
    linhas += _tabela(
        ["Ano", "Denominador", "Linhas mudadas", "Fração"],
        [[a["ano"], a["denominador"], a["linhas_mudadas"], _num(a["fracao"])] for a in r["por_ano"]],
    )
    linhas += ["", "## Tickers com mais linhas mudadas (até 10)", ""]
    if r["top_tickers"]:
        linhas += _tabela(["Ticker", "Linhas mudadas"], [[t["ticker"], t["linhas_mudadas"]] for t in r["top_tickers"]])
    else:
        linhas.append("Nenhuma linha mudada.")
    linhas += ["", "## Datasets", ""]
    linhas += _tabela(
        ["Papel", "Arquivo", "sha256"],
        [["Congelado (rodada oficial)", r["congelado"]["arquivo"], r["congelado"]["sha256"]],
         ["Novo", r["novo"]["arquivo"], r["novo"]["sha256"]]],
    )
    linhas += [
        "",
        "## Regras aplicadas",
        "",
        f"- Célula mudada: no preparado (ranks, o que o modelo recebe), vazia de um lado e preenchida do outro, ou "
        f"|novo − congelado| > {TOLERANCIA:g} (estritamente maior); E no bruto (valor do CSV antes do rank, coluna de origem), "
        "o mesmo critério.",
        f"- Regra da medida: {REGRA}.",
        "- Motivo do critério no bruto: ruído do float32 em valores quase empatados perto de zero (ex.: `salto_abertura` "
        "quando a abertura é igual ao fechamento anterior) muda o rank sem mudar o dado (medida de 09/11/2026, protocolo "
        "seção 8, nota da D5).",
        "- Linha mudada: alguma célula mudada, ou a chave (data, ticker) existe em só um dos dois.",
        "- Denominador: linhas com alvo preenchido no congelado. Linhas só no novo entram no numerador, não no denominador.",
        "- Colunas: `colunas_3` do congelado mais `alvo`, com os valores que o modelo recebe (`preparacao.preparar`).",
        f"- Decisão: fração total > {_num(LIMITE, 2)} → nova rodada; preço e alvo > {_num(LIMITE, 2)} → parar e perguntar.",
        "",
    ]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None, params=None) -> int:
    """Ponto de entrada (`python -m processamento.experimento.medida_dados_novos`).

    Devolve 0 em sucesso; 2 se o dataset estiver fora do padrão, uma conferência falhar ou a saída já existir.
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.experimento.medida_dados_novos",
        description="Mede quanto do desenvolvimento muda entre o dataset congelado e um dataset regenerado. "
                    "Só lê os CSV do desenvolvimento (nada do banco).",
    )
    parser.add_argument("--congelado-csv", type=Path, required=True, help="CSV congelado da rodada oficial")
    parser.add_argument("--novo-csv", type=Path, required=True, help="CSV regenerado a comparar")
    parser.add_argument("--congelado", type=Path, required=True,
                        help="protocolo congelado da rodada (JSON, ex.: docs/protocolo_congelado_rodada_003.json)")
    parser.add_argument("--pasta-docs", type=Path, default=PASTA_DOCS_PADRAO,
                        help="pasta de saída do .md e do .json (padrão: docs)")
    parser.add_argument("--data", type=treino._data_argumento, default=None,
                        help="data da medida (AAAA-MM-DD; padrão: hoje, em São Paulo)")
    args = parser.parse_args(argv)
    data = args.data or datetime.now(fontes.SP).date()
    try:
        caminho_md, _ = executar(args.congelado_csv, args.novo_csv, args.congelado, args.pasta_docs,
                                 data=data, params=params)
    except (treino.ErroDataset, ErroMedida) as erro:
        print(f"{erro}")
        return 2
    print(f"Medida gravada: {caminho_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
