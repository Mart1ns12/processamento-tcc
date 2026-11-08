"""Cartões de saúde do painel: lê o docs/diagnostico_banco.md (só leitura) e devolve 6 cartões com farol.

Não acessa o banco. Seção, nota ou tabela ausentes viram cartão "idle" com "sem dados";
nenhuma função levanta exceção por arquivo ausente ou quebrado.
"""

from __future__ import annotations

import re
from pathlib import Path

from processamento.painel.relatorios import RE_SECAO, RE_SEPARADOR, _celulas, ler_diagnostico

RE_QTD_ACOES = re.compile(r"em (\d+) empresas em (\d{4}-\d{2}-\d{2})")
RE_QTD_ACOES_ZERO = re.compile(r"^nenhuma empresa com quantidade de ações suspeita em (\d{4}-\d{2}-\d{2})")
RE_RETORNOS = re.compile(r"^(\d+) retornos diários suspeitos em (\d+) tickers")
RE_RETORNOS_ZERO = re.compile(r"^nenhum retorno diário suspeito")
RE_LACUNAS_PRECOS = re.compile(r"^(\d+) lacunas de mais de \d+ pregões em \d+ tickers de v1-precos")
RE_LACUNAS_PRECOS_ZERO = re.compile(r"^nenhuma lacuna de mais de \d+ pregões em v1-precos")
RE_LACUNAS_INDICES = re.compile(r"^(\d+) lacunas em v1-indices")
RE_LACUNAS_INDICES_ZERO = re.compile(r"^nenhuma lacuna em v1-indices")
RE_COBERTURA = re.compile(
    r"^Cobertura do experimento \([^)]*\): (\d+) linhas em (\d+) pregões, de (\d{4}-\d{2}-\d{2}) a (\d{4}-\d{2}-\d{2})"
)

COLUNAS_HORA = ("total", "hora_real", "so_data_n1a", "sem_hora")

# Divergências estruturais (tabela ou coluna faltando, chave diferente, valor não permitido): derrubam o contrato
# (farol bad). Os demais temas são de dado (farol warn) e não derrubam a situação de hoje.
TEMAS_ESTRUTURAIS = frozenset({
    "tabela_ausente", "coluna_faltando", "coluna_extra", "chave", "indice_ausente", "duplicata_chave",
    "valor_desconhecido", "falha_consulta", "etapa_desconhecida", "status_desconhecido",
})


# ---------------------------------------------------------------- auxiliares

def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + "%"


def _data_br(texto: str) -> str:
    """AAAA-MM-DD vira DD/MM/AAAA; AAAA-MM vira MM/AAAA; outro texto fica como está."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.fullmatch(r"(\d{4})-(\d{2})", texto)
    if m:
        return f"{m.group(2)}/{m.group(1)}"
    return texto


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def tabela_md(linhas: list[str], subtitulo: str) -> list[dict[str, str]] | None:
    """Tabela markdown que vem logo após o `### subtitulo`; None se o subtítulo não existe."""
    alvo = "### " + subtitulo
    i = next((k for k, linha in enumerate(linhas) if linha == alvo), None)
    if i is None:
        return None
    k = i + 1
    while k < len(linhas) and not linhas[k].strip():
        k += 1
    cabecalho = None
    tabela: list[dict[str, str]] = []
    while k < len(linhas) and linhas[k].startswith("|"):
        linha = linhas[k]
        k += 1
        if RE_SEPARADOR.match(linha):
            continue
        celulas = _celulas(linha)
        if cabecalho is None:
            cabecalho = celulas
            continue
        tabela.append(dict(zip(cabecalho, celulas)))
    return tabela


def _secao(linhas: list[str], prefixo: str) -> tuple[str, str, list[str]] | None:
    """(número, título, linhas) da seção cujo título começa com `prefixo`; as linhas vão até o próximo `## `."""
    for i, linha in enumerate(linhas):
        m = RE_SECAO.match(linha)
        if m and m.group(2).strip().startswith(prefixo):
            fim = next((j for j in range(i + 1, len(linhas)) if linhas[j].startswith("## ")), len(linhas))
            return m.group(1), m.group(2).strip(), linhas[i + 1:fim]
    return None


def _notas(diag: dict, prefixo: str) -> list[str]:
    return next((s["notas"] for s in diag["secoes"] if s["titulo"].startswith(prefixo)), [])


def _cartao(id_: str, titulo: str, farol: str, numero: str, texto: str, fonte: str | None) -> dict:
    return {"id": id_, "titulo": titulo, "farol": farol, "numero": numero, "texto": texto, "fonte": fonte}


def _sem_secao(id_: str, titulo: str) -> dict:
    return _cartao(id_, titulo, "idle", "sem dados", "Seção não encontrada no diagnóstico.", None)


def _sem_nota(id_: str, titulo: str, fonte: str) -> dict:
    return _cartao(id_, titulo, "idle", "sem dados", "Formato da nota não reconhecido.", fonte)


# ---------------------------------------------------------------- cartões

def _cartao_contrato(diag: dict, linhas: list[str]) -> dict:
    id_, titulo, fonte = "contrato", "Contrato com a coleta", "Divergências × especificação"
    divergencias = diag.get("divergencias", [])
    n = len(divergencias)
    if n == 0:
        return _cartao(id_, titulo, "ok", "0 divergências",
                       "Tabelas, colunas e formatos batem com a especificação.", fonte)
    estruturais: list[str] = []
    de_dado: list[str] = []
    for d in divergencias:
        tema = d.get("tema") or "sem tema"
        lista = estruturais if tema in TEMAS_ESTRUTURAIS else de_dado
        if tema not in lista:
            lista.append(tema)
    if estruturais:
        partes = ["Estruturais: " + ", ".join(estruturais)]
        if de_dado:
            partes.append("de dado: " + ", ".join(de_dado))
        return _cartao(id_, titulo, "bad", _plural(n, "divergência", "divergências"),
                       " · ".join(partes) + ".", fonte)
    return _cartao(id_, titulo, "warn", _plural(n, "divergência", "divergências"),
                   "Problemas de dado (não estruturais): " + ", ".join(de_dado)
                   + ". Não derrubam a situação de hoje.", fonte)


def _cartao_quantidade(diag: dict, linhas: list[str]) -> dict:
    id_, titulo = "quantidade_acoes", "Quantidade de ações"
    achada = _secao(linhas, "Quantidade de ações suspeita")
    if achada is None:
        return _sem_secao(id_, titulo)
    numero, stitulo, corpo = achada
    fonte = f"Seção {numero}: {stitulo}"
    for nota in _notas(diag, "Quantidade de ações suspeita"):
        m = RE_QTD_ACOES.search(nota)
        if m:
            n = int(m.group(1))
            data = _data_br(m.group(2))
            tab = tabela_md(corpo, "Empresas com quantidade de ações suspeita") or []
            exemplos = [r["tickers"] for r in tab[:3] if r.get("tickers")]
            trecho = f" (ex.: {', '.join(exemplos)})" if exemplos else ""
            texto = (f"Provavelmente em milhares{trecho}. P/L, P/VP e payout delas saem indisponível "
                     f"em {data}; yield, ROE, margens, EBITDA e endividamento não mudam.")
            return _cartao(id_, titulo, "warn", _plural(n, "empresa", "empresas"), texto, fonte)
        m = RE_QTD_ACOES_ZERO.match(nota)
        if m:
            data = _data_br(m.group(1))
            return _cartao(id_, titulo, "ok", "0 empresas",
                           f"Nenhuma empresa com quantidade de ações fora do plausível em {data}.", fonte)
    return _sem_nota(id_, titulo, fonte)


def _cartao_retornos(diag: dict, linhas: list[str]) -> dict:
    id_, titulo = "retornos", "Preços suspeitos"
    achada = _secao(linhas, "Retornos diários suspeitos")
    if achada is None:
        return _sem_secao(id_, titulo)
    numero, stitulo, corpo = achada
    fonte = f"Seção {numero}: {stitulo}"
    for nota in _notas(diag, "Retornos diários suspeitos"):
        m = RE_RETORNOS.match(nota)
        if m:
            n = int(m.group(1))
            t = int(m.group(2))
            tab = tabela_md(corpo, "Retornos diários suspeitos") or []
            contagem: dict[str, int] = {}
            for r in tab:
                if r.get("ticker"):
                    contagem[r["ticker"]] = contagem.get(r["ticker"], 0) + 1
            if contagem:
                lista = ", ".join(f"{tk} ({k})" if k > 1 else tk for tk, k in contagem.items())
            else:
                lista = _plural(t, "ticker", "tickers")
            texto = f"{lista}: ficam fora das séries e das medianas do setor; o preço não é corrigido."
            return _cartao(id_, titulo, "warn", _plural(n, "retorno", "retornos"), texto, fonte)
        if RE_RETORNOS_ZERO.match(nota):
            return _cartao(id_, titulo, "ok", "0 retornos", "Nenhum retorno diário suspeito.", fonte)
    return _sem_nota(id_, titulo, fonte)


def _texto_indices(ni: int, corpo: list[str]) -> str:
    if ni == 0:
        return "Índices: nenhuma lacuna."
    tab = tabela_md(corpo, "Lacunas em v1-indices") or []
    grupos: dict[tuple[str, str, str, str], list[str]] = {}
    for r in tab:
        chave = (r.get("inicio", ""), r.get("fim", ""), r.get("tamanho", ""), r.get("unidade", ""))
        grupos.setdefault(chave, []).append(r.get("serie", ""))
    if not grupos:
        return f"Índices: {_plural(ni, 'lacuna', 'lacunas')}."
    partes = [f"{', '.join(s for s in series if s)}: {tam} {uni} ({_data_br(ini)} a {_data_br(fim)})"
              for (ini, fim, tam, uni), series in grupos.items()]
    return "Índices: " + "; ".join(partes) + "."


def _cartao_lacunas(diag: dict, linhas: list[str]) -> dict:
    id_, titulo = "lacunas", "Lacunas nas séries"
    achada = _secao(linhas, "Lacunas nas séries")
    if achada is None:
        return _sem_secao(id_, titulo)
    numero, stitulo, corpo = achada
    fonte = f"Seção {numero}: {stitulo}"
    np_: int | None = None
    ni: int | None = None
    for nota in _notas(diag, "Lacunas nas séries"):
        m = RE_LACUNAS_PRECOS.match(nota)
        if m:
            np_ = int(m.group(1))
        elif RE_LACUNAS_PRECOS_ZERO.match(nota):
            np_ = 0
        m = RE_LACUNAS_INDICES.match(nota)
        if m:
            ni = int(m.group(1))
        elif RE_LACUNAS_INDICES_ZERO.match(nota):
            ni = 0
    if np_ is None and ni is None:
        return _sem_nota(id_, titulo, fonte)
    partes = []
    if np_ is not None:
        partes.append("Preços: nenhuma lacuna." if np_ == 0 else f"Preços: {_plural(np_, 'lacuna', 'lacunas')}.")
    if ni is not None:
        partes.append(_texto_indices(ni, corpo))
    n = (np_ or 0) + (ni or 0)
    farol = "ok" if n == 0 else "warn"
    return _cartao(id_, titulo, farol, _plural(n, "lacuna", "lacunas"), " ".join(partes), fonte)


def _faixa(valores: list[int]) -> str:
    """Um valor inteiro em % ("100%") ou a faixa mínimo–máximo ("80–100%")."""
    mn, mx = min(valores), max(valores)
    return f"{mn}%" if mn == mx else f"{mn}–{mx}%"


def _frase_origens(corpo: list[str]) -> str | None:
    """Uma frase por origem (Google News, WordPress, cvm_ipe) da tabela por ano e origem; None se a tabela falta."""
    tab = tabela_md(corpo, "Hora da publicação, por ano e origem (artigos distintos)")
    if not tab:
        return None
    por_origem: dict[str, dict[str, tuple[int, int]]] = {}
    for r in tab:
        try:
            total, hora = int(r["total"]), int(r["hora_real"])
        except (KeyError, ValueError):
            continue
        if total > 0 and r.get("origem") and r.get("ano"):
            por_origem.setdefault(r["origem"], {})[r["ano"]] = (total, hora)
    partes: list[str] = []
    google = por_origem.get("google_news")
    if google:
        anos = sorted(google)
        ultimo, anteriores = anos[-1], anos[:-1]
        y = round(google[ultimo][1] / google[ultimo][0] * 100)
        if anteriores:
            x = round(sum(google[a][1] / google[a][0] * 100 for a in anteriores) / len(anteriores))
            partes.append(f"Google News: ~{x}% com hora real em {anteriores[0]}–{anteriores[-1]} e {y}% em {ultimo}")
        else:
            partes.append(f"Google News: {y}% com hora real em {ultimo}")
    wordpress = por_origem.get("wordpress")
    if wordpress:
        partes.append("WordPress: " + _faixa([round(h / t * 100) for t, h in wordpress.values()]))
    cvm = por_origem.get("cvm_ipe")
    if cvm:
        if all(h == 0 for _t, h in cvm.values()):
            partes.append("cvm_ipe só tem data")
        else:
            partes.append("cvm_ipe: " + _faixa([round(h / t * 100) for t, h in cvm.values()]) + " com hora real")
    return "; ".join(partes) + "." if partes else None


def _cartao_horario(diag: dict, linhas: list[str]) -> dict:
    id_, titulo = "horario_noticias", "Horário das notícias"
    achada = _secao(linhas, "Notícias")
    if achada is None:
        return _sem_secao(id_, titulo)
    numero, stitulo, corpo = achada
    fonte = f"Seção {numero}: {stitulo}"
    tab = tabela_md(corpo, "Hora da publicação, por ano (artigos distintos)")
    if not tab or not all(c in tab[0] for c in COLUNAS_HORA):
        return _cartao(id_, titulo, "idle", "sem dados", "Tabela de horas não reconhecida.", fonte)
    t = sum(int(r["total"]) for r in tab)
    if t == 0:
        return _cartao(id_, titulo, "idle", "sem dados", "Nenhum artigo na tabela de horas.", fonte)
    hr = sum(int(r["hora_real"]) for r in tab)
    sd = sum(int(r["so_data_n1a"]) for r in tab)
    sh = sum(int(r["sem_hora"]) for r in tab)
    sem = (t - hr) / t
    farol = "ok" if sem <= 0.10 else "warn"
    texto = (f"Com hora real: {_pct(hr / t)} · só data (regra N1-A): {_pct(sd / t)} · "
             f"sem hora: {_pct(sh / t)}. Notícias sem hora entram na janela do dia de forma conservadora.")
    frase = _frase_origens(corpo)
    if frase:
        texto += " " + frase
    return _cartao(id_, titulo, farol, f"{_pct(sem)} sem hora real", texto, f"{fonte} · {_milhar(t)} artigos")


def _cartao_cobertura(diag: dict, linhas: list[str]) -> dict:
    id_, titulo = "cobertura", "Histórico disponível"
    achada = _secao(linhas, "Histórico novo")
    if achada is None:
        return _sem_secao(id_, titulo)
    numero, stitulo, _corpo = achada
    fonte = f"Seção {numero}: {stitulo}"
    for nota in _notas(diag, "Histórico novo"):
        m = RE_COBERTURA.match(nota)
        if m:
            n_linhas, n_pregoes = int(m.group(1)), int(m.group(2))
            farol = "ok" if n_linhas > 0 else "warn"
            texto = f"{_milhar(n_pregoes)} pregões, de {_data_br(m.group(3))} a {_data_br(m.group(4))}, no dataset do experimento."
            return _cartao(id_, titulo, farol, f"{_milhar(n_linhas)} linhas", texto, fonte)
    return _sem_nota(id_, titulo, fonte)


_CARTOES = [
    ("contrato", "Contrato com a coleta", _cartao_contrato),
    ("quantidade_acoes", "Quantidade de ações", _cartao_quantidade),
    ("retornos", "Preços suspeitos", _cartao_retornos),
    ("lacunas", "Lacunas nas séries", _cartao_lacunas),
    ("horario_noticias", "Horário das notícias", _cartao_horario),
    ("cobertura", "Histórico disponível", _cartao_cobertura),
]


def cartoes_saude(caminho: Path) -> dict:
    """Seis cartões de saúde do docs/diagnostico_banco.md. Arquivo ausente ou ilegível: disponivel False."""
    diag = ler_diagnostico(caminho)
    if not diag.get("disponivel"):
        return {"disponivel": False, "motivo": diag.get("motivo"), "gerado_em": None, "cartoes": []}
    try:
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        linhas = []
    cartoes = []
    for id_, titulo, construtor in _CARTOES:
        try:
            cartoes.append(construtor(diag, linhas))
        except Exception:
            cartoes.append(_cartao(id_, titulo, "idle", "sem dados", "Não foi possível ler este cartão.", None))
    return {"disponivel": True, "motivo": None, "gerado_em": diag["gerado_em"], "cartoes": cartoes}


# ---------------------------------------------------------------- linhas afetadas

def _afetadas(titulo: str, itens: list[dict]) -> dict | None:
    if not itens:
        return None
    return {"titulo": titulo, "itens": itens, "total": len(itens)}


def _tabela_por_prefixo(linhas: list[str], prefixo: str) -> list[dict[str, str]]:
    """Tabela do primeiro `### ` cujo título começa com `prefixo`; lista vazia se não existe."""
    alvo = next((linha for linha in linhas if linha.startswith("### " + prefixo)), None)
    if alvo is None:
        return []
    return tabela_md(linhas, alvo[len("### "):]) or []


def _afetadas_contrato(caminho: Path) -> dict | None:
    diag = ler_diagnostico(caminho)
    if not diag.get("disponivel"):
        return None
    itens = [{"rotulo": d["tabela"], "detalhe": d["tema"]}
             for d in diag["divergencias"] if d["tabela"] not in ("", "-")]
    return _afetadas("Tabelas afetadas", itens)


def _afetadas_quantidade(linhas: list[str]) -> dict | None:
    achada = _secao(linhas, "Quantidade de ações suspeita")
    if achada is None:
        return None
    tab = tabela_md(achada[2], "Empresas com quantidade de ações suspeita") or []
    itens = [{"rotulo": t, "detalhe": None}
             for r in tab for t in (r.get("tickers") or "").split(", ") if t]
    return _afetadas("Empresas afetadas", itens)


def _afetadas_retornos(linhas: list[str]) -> dict | None:
    achada = _secao(linhas, "Retornos diários suspeitos")
    if achada is None:
        return None
    tab = tabela_md(achada[2], "Retornos diários suspeitos") or []
    itens = [{"rotulo": r["ticker"], "detalhe": _data_br(r.get("data", ""))} for r in tab if r.get("ticker")]
    return _afetadas("Ações afetadas", itens)


def _afetadas_lacunas(linhas: list[str]) -> dict | None:
    achada = _secao(linhas, "Lacunas nas séries")
    if achada is None:
        return None
    corpo = achada[2]
    tabelas = _tabela_por_prefixo(corpo, "Lacunas em v1-precos") + (tabela_md(corpo, "Lacunas em v1-indices") or [])
    itens = [{"rotulo": r.get("serie") or r.get("ticker", ""),
              "detalhe": f"{_data_br(r.get('inicio', ''))} a {_data_br(r.get('fim', ''))}"}
             for r in tabelas]
    return _afetadas("Séries afetadas", itens)


def afetadas_saude(caminho: Path) -> dict[str, dict]:
    """Linhas afetadas de cada cartão (tabelas, empresas, ações e séries) do diagnóstico. Arquivo ausente: {}.

    Só inclui o cartão quando há itens; `total` é o número de itens.
    """
    try:
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    construtores = {
        "contrato": lambda: _afetadas_contrato(caminho),
        "quantidade_acoes": lambda: _afetadas_quantidade(linhas),
        "retornos": lambda: _afetadas_retornos(linhas),
        "lacunas": lambda: _afetadas_lacunas(linhas),
    }
    resultado: dict[str, dict] = {}
    for id_, construtor in construtores.items():
        try:
            bloco = construtor()
        except Exception:
            bloco = None
        if bloco:
            resultado[id_] = bloco
    return resultado
