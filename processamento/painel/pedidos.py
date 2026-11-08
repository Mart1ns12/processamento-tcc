"""Pedidos à coleta: cada pedido do YAML vira entregue, pendente, sem dados, sem checagem ou erro.

As checagens leem o docs/diagnostico_banco.md (só leitura). Um pedido só vira "entregue" quando a
checagem devolve True. Nada de banco, rede ou processo externo. Checagens são registradas por nome
com o decorador @checagem; o YAML escolhe a checagem pelo nome no dicionário, sem busca dinâmica de atributos.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import yaml

from processamento.painel.aba_coleta import MOTIVO_SEM_SECAO, MOTIVO_SEM_TABELA, contagem_finbert, contagem_juiza, ler_md
from processamento.painel.relatorios import ler_diagnostico
from processamento.painel.saude import _data_br, _milhar, _notas, _plural, _secao, tabela_md

ESTADOS = ("entregue", "pendente", "sem_dados", "sem_checagem", "erro")
PRIORIDADES = ("critico", "normal")
FONTE = "processamento/config/pedidos_coleta.yaml e docs/diagnostico_banco.md"
MOTIVO_SEM_YAML = "processamento/config/pedidos_coleta.yaml não encontrado"
MOTIVO_YAML_ILEGIVEL = "pedidos_coleta.yaml ilegível"
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
RE_INCOERENTES = re.compile(r"^(\d+) linhas incoerentes com os eventos")
RE_FORA_CALENDARIO = re.compile(r"linha fora do calendário[^:]*:\s*(.*)$")
PREFIXO_MUDANCAS = "mudanças registradas em v1-mudancas_ticker:"

CHECAGENS: dict[str, Callable[..., tuple[bool | None, str]]] = {}


def checagem(nome: str) -> Callable[[Callable], Callable]:
    """Registra a função em CHECAGENS com o nome dado (é o nome que o YAML usa)."""
    def registrar(funcao: Callable) -> Callable:
        CHECAGENS[nome] = funcao
        return funcao
    return registrar


# ---------------------------------------------------------------- auxiliares

def _inteiro(texto: str) -> int | None:
    try:
        return int(texto)
    except (TypeError, ValueError):
        return None


def _decimal(texto: str) -> float | None:
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def _corpo(linhas: list[str], prefixo: str) -> list[str] | None:
    achada = _secao(linhas, prefixo)
    return None if achada is None else achada[2]


def _contagem(itens: list[dict]) -> dict[str, int]:
    return {estado: sum(1 for i in itens if i["estado"] == estado) for estado in ESTADOS}


def _indisponivel(motivo: str) -> dict:
    return {"disponivel": False, "motivo": motivo, "gerado_em": None, "itens": [],
            "contagem": _contagem([]), "fonte": FONTE}


# ---------------------------------------------------------------- checagens
# Assinatura: f(diag, linhas, **parametros) -> (True | False | None, evidencia).
# True = entregue; False = pendente; None = sem dados (a evidência explica o porquê).

@checagem("meses_sem_poucas_noticias")
def _meses_sem_poucas_noticias(diag: dict, linhas: list[str], de: str, ate: str):
    corpo = _corpo(linhas, "Notícias por mês")
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    tabela = tabela_md(corpo, "Meses com poucas notícias")
    if tabela is None:
        if any(n.startswith("nenhum mês abaixo") for n in _notas(diag, "Notícias por mês")):
            return True, "Nenhum mês com poucas notícias."
        return None, MOTIVO_SEM_TABELA
    presentes = [linha.get("mes", "") for linha in tabela if de <= linha.get("mes", "") <= ate]
    if presentes:
        return False, "Meses ainda com poucas notícias: " + ", ".join(_data_br(m) for m in presentes)
    return True, f"Nenhum mês de {_data_br(de)} a {_data_br(ate)} com poucas notícias."


@checagem("finbert_e_juiza_completos")
def _finbert_e_juiza_completos(diag: dict, linhas: list[str], max_aguardando: int = 0, so_finbert: bool = False):
    finbert = contagem_finbert(linhas)
    if so_finbert:
        # A juíza fica só no pedido juiza_historico.
        if finbert is None:
            return None, "FinBERT sem contagem no diagnóstico."
        if finbert["sem_prob"] <= max_aguardando:
            return True, "FinBERT em todas as notícias."
        return False, f"{_milhar(finbert['sem_prob'])} sem FinBERT"
    juiza = contagem_juiza(linhas)
    if finbert is None or juiza is None:
        return None, "FinBERT ou juíza sem contagem no diagnóstico."
    sem_prob, nulos = finbert["sem_prob"], juiza["nulos"]
    if sem_prob <= max_aguardando and nulos <= max_aguardando:
        return True, "FinBERT e juíza em todas as notícias."
    return False, f"{_milhar(sem_prob)} sem FinBERT · {_milhar(nulos)} sem juíza"


@checagem("acoes_coerentes_com_eventos")
def _acoes_coerentes_com_eventos(diag: dict, linhas: list[str]):
    titulo = "Ações emitidas: base atual e eventos"
    if _corpo(linhas, titulo) is None:
        return None, MOTIVO_SEM_SECAO
    for nota in _notas(diag, titulo):
        m = RE_INCOERENTES.match(nota)
        if m:
            n = int(m.group(1))
            if n == 0:
                return True, "Nenhuma linha incoerente com os eventos."
            return False, f"{_milhar(n)} linhas incoerentes com os eventos"
    return None, "Nota de linhas incoerentes não encontrada na seção."


@checagem("sem_linha_fora_do_calendario")
def _sem_linha_fora_do_calendario(diag: dict, linhas: list[str], tickers: list[str]):
    titulo = "Preços (v1-precos)"
    corpo = _corpo(linhas, titulo)
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    achados: dict[str, str] = {}
    nota_vista = False
    for nota in _notas(diag, titulo):
        m = RE_FORA_CALENDARIO.search(nota)
        if not m:
            continue
        nota_vista = True
        for par in m.group(1).split(","):
            partes = par.split()
            if len(partes) == 2 and partes[0] in tickers:
                achados.setdefault(partes[0], f"{partes[0]} {_data_br(partes[1])}")
    buracos = tabela_md(corpo, "Buracos por ticker (só os com problema)")
    if not nota_vista and buracos is None:
        # Sem a nota e sem a tabela, o diagnóstico não diz nada sobre o calendário: nunca vira "entregue".
        return None, "Nem a nota de linhas fora do calendário nem a tabela de buracos estão na seção."
    for linha in buracos or []:
        ticker = linha.get("ticker", "")
        n = _inteiro(linha.get("n_fora_do_pregao", ""))
        if ticker in tickers and n and ticker not in achados:
            achados[ticker] = f"{ticker} ({n} fora do pregão)"
    if achados:
        return False, "Ainda no diagnóstico: " + ", ".join(achados.values())
    return True, "Nenhuma linha fora do calendário para " + ", ".join(tickers) + "."


@checagem("colunas_existem")
def _colunas_existem(diag: dict, linhas: list[str], tabela: str, colunas: list[str], tabelas: list[str] | None = None):
    tabelas = tabelas or []
    corpo = _corpo(linhas, "Colunas e chaves")
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    da_tabela = tabela_md(corpo, tabela)
    if da_tabela is None:
        return None, MOTIVO_SEM_TABELA
    presentes = {linha.get("coluna") for linha in da_tabela}
    faltam = [c for c in colunas if c not in presentes]
    if tabelas:
        corpo_existencia = _corpo(linhas, "Existência das tabelas")
        if corpo_existencia is None:
            return None, MOTIVO_SEM_SECAO
        existencia = tabela_md(corpo_existencia, "Existência")
        if existencia is None:
            return None, MOTIVO_SEM_TABELA
        existe = {linha.get("tabela"): linha.get("existe") for linha in existencia}
        faltam += [t for t in tabelas if existe.get(t) != "sim"]
    if faltam:
        return False, "Faltam: " + ", ".join(faltam)
    return True, "Tudo presente: " + ", ".join([*colunas, *tabelas])


@checagem("origem_nos_anos")
def _origem_nos_anos(diag: dict, linhas: list[str], origem: str, anos: list[int]):
    corpo = _corpo(linhas, "Notícias (")
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    tabela = tabela_md(corpo, "Hora da publicação, por ano e origem (artigos distintos)")
    if tabela is None:
        return None, MOTIVO_SEM_TABELA
    totais: dict[str, int | None] = {}
    for linha in tabela:
        if linha.get("origem") == origem:
            totais[linha.get("ano", "")] = _inteiro(linha.get("total", ""))
    faltam = [str(a) for a in anos if not totais.get(str(a))]
    if faltam:
        return False, f"Sem notícias de {origem} em: " + ", ".join(faltam)
    return True, f"{origem}: " + " · ".join(f"{a}: {_milhar(totais[str(a)])}" for a in anos)


@checagem("emissores_por_periodo")
def _emissores_por_periodo(diag: dict, linhas: list[str], tickers: list[str]):
    corpo = _corpo(linhas, "Emissores por período")
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    tabela = tabela_md(corpo, "Tickers com mais de um emissor")
    if tabela is None:
        return False, "Nenhum ticker com mais de um emissor no diagnóstico."
    contagem: dict[str, int] = {}
    for linha in tabela:
        ticker = linha.get("ticker", "")
        contagem[ticker] = contagem.get(ticker, 0) + 1
    faltam = [t for t in tickers if t not in contagem]
    if faltam:
        return False, "Sem histórico de emissores: " + ", ".join(faltam)
    return True, " · ".join(f"{t}: {_plural(contagem[t], 'emissor', 'emissores')}" for t in tickers)


@checagem("valor_distinto")
def _valor_distinto(diag: dict, linhas: list[str], tabela: str, coluna: str, valor: str):
    corpo = _corpo(linhas, "Valores distintos")
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    por_coluna = tabela_md(corpo, "Valores por coluna")
    if por_coluna is None:
        return None, MOTIVO_SEM_TABELA
    for linha in por_coluna:
        if linha.get("tabela") == tabela and linha.get("coluna") == coluna and linha.get("valor") == valor:
            n = _inteiro(linha.get("n", ""))
            if n is not None and n > 0:
                return True, f"{valor}: {_milhar(n)} linhas em {tabela}.{coluna}"
            break
    return False, f"Nenhuma linha com {coluna} = {valor} em {tabela}"


@checagem("coluna_preenchida")
def _coluna_preenchida(diag: dict, linhas: list[str], tabela: str, coluna: str, max_pct_nulo: float,
                       estrito: bool = False):
    corpo = _corpo(linhas, "Vazios e zeros")
    if corpo is None:
        return None, MOTIVO_SEM_SECAO
    for linha in tabela_md(corpo, "Colunas com nulos, textos vazios ou zeros") or []:
        if linha.get("tabela") == tabela and linha.get("coluna") == coluna:
            pct = _decimal(linha.get("pct_nulo", ""))
            if pct is None:
                return None, "Percentual de nulos ilegível no diagnóstico."
            nulos = _inteiro(linha.get("nulos", ""))
            total = _inteiro(linha.get("total", ""))
            # Com total e nulos, compara pela contagem: o pct_nulo do .md é arredondado a uma casa.
            pct_comparado = nulos * 100 / total if nulos is not None and total else pct
            texto = f"{100 - pct:.1f}".replace(".", ",") + "% preenchida"
            if nulos is not None:
                texto += f" ({_milhar(nulos)} vazias)"
            if estrito:
                return pct_comparado < max_pct_nulo, texto
            return pct_comparado <= max_pct_nulo, texto
    if any(n.startswith("demais colunas 100% preenchidas") for n in _notas(diag, "Vazios e zeros")):
        return True, "100% preenchida"
    return None, "Coluna sem linha na tabela de nulos do diagnóstico."


@checagem("indices_desde")
def _indices_desde(diag: dict, linhas: list[str], indices: list[str], inicio_ate: str):
    corpo_resumo = _corpo(linhas, "Resumo das tabelas")
    if corpo_resumo is None:
        return None, MOTIVO_SEM_SECAO
    da_tabela = tabela_md(corpo_resumo, "Índices")
    if da_tabela is None:
        return None, MOTIVO_SEM_TABELA
    corpo_lacunas = _corpo(linhas, "Lacunas nas séries")
    if corpo_lacunas is None:
        return None, MOTIVO_SEM_SECAO
    lacunas = tabela_md(corpo_lacunas, "Lacunas em v1-indices") or []

    por_indice = {linha.get("indice"): linha for linha in da_tabela}
    falhas: list[str] = []
    inicios: list[str] = []
    for indice in indices:
        linha = por_indice.get(indice)
        if linha is None:
            falhas.append(f"{indice} ausente do diagnóstico")
            continue
        inicio = linha.get("inicio", "")
        if not RE_DATA.fullmatch(inicio):
            falhas.append(f"{indice} sem data de início")
        else:
            inicios.append(inicio)
            if inicio > inicio_ate:
                falhas.append(f"{indice} começa em {_data_br(inicio)}")
        for lacuna in lacunas:
            if lacuna.get("serie") == indice:
                falhas.append(f"{indice} com lacuna de {_data_br(lacuna.get('inicio', ''))} "
                              f"a {_data_br(lacuna.get('fim', ''))}")
    if falhas:
        return False, "; ".join(falhas)
    desde = max(inicios, default=inicio_ate)
    return True, f"{', '.join(indices)} desde {_data_br(desde)}, sem lacunas."


@checagem("divergencia_e_mudanca")
def _divergencia_e_mudanca(diag: dict, linhas: list[str], tema: str, termo: str, antigo: str, novo: str):
    if "divergencias" not in diag:
        return None, "Seção de divergências não encontrada no diagnóstico."
    pendente = any(d["tema"] == tema and termo in d["detalhe"] for d in diag["divergencias"])
    nota = next((n for n in _notas(diag, "Tickers e CNPJs") if n.startswith(PREFIXO_MUDANCAS)), None)
    par = f"{antigo} → {novo}"
    if nota is None:
        if pendente:
            return False, f"Divergência {tema} da {termo} ainda no diagnóstico"
        return None, "O diagnóstico ainda não lista as mudanças de ticker (rode o diagnóstico de novo)."
    presente = par in [p.strip() for p in nota[len(PREFIXO_MUDANCAS):].split(",")]
    if presente and not pendente:
        return True, f"{par} em v1-mudancas_ticker e sem divergência {tema}"
    faltas = []
    if pendente:
        faltas.append(f"Divergência {tema} da {termo} ainda no diagnóstico")
    if not presente:
        faltas.append(f"{par} não está em v1-mudancas_ticker")
    return False, " · ".join(faltas)


# ---------------------------------------------------------------- avaliação

def _avaliar_item(bruto: dict, ids_vistos: set[str], diag: dict | None, linhas: list[str] | None,
                  motivo_diag: str) -> tuple[str, str]:
    """(estado, evidência) de um pedido já validado como dict com id e texto str."""
    prioridade = bruto.get("prioridade")
    if prioridade not in PRIORIDADES:
        return "erro", "prioridade inválida"
    if bruto["id"] in ids_vistos:
        return "erro", "id repetido"
    nome = bruto.get("checagem")
    if nome is None:
        return "sem_checagem", "sem checagem automática"
    if not isinstance(nome, str) or nome not in CHECAGENS:
        return "sem_checagem", f"checagem desconhecida: {nome}"
    parametros = bruto.get("parametros")
    if parametros is None:
        parametros = {}
    if not isinstance(parametros, dict):
        return "erro", "parâmetros inválidos"
    if diag is None or linhas is None:
        return "sem_dados", motivo_diag
    try:
        resultado, evidencia = CHECAGENS[nome](diag, linhas, **parametros)
    except Exception as exc:  # erro de parâmetro ou de leitura conta como erro da checagem, não do painel
        return "erro", f"erro na checagem ({type(exc).__name__})"
    if resultado is True:
        return "entregue", evidencia
    if resultado is False:
        return "pendente", evidencia
    if resultado is None:
        return "sem_dados", evidencia
    return "erro", "resultado inválido da checagem"


def avaliar_pedidos(caminho_yaml: Path, docs_md: Path) -> dict:
    """Pedidos do YAML com o estado de cada um conferido no diagnóstico (só leitura)."""
    if not caminho_yaml.is_file():
        return _indisponivel(MOTIVO_SEM_YAML)
    try:
        dados = yaml.safe_load(caminho_yaml.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return _indisponivel(MOTIVO_YAML_ILEGIVEL)
    pedidos = dados.get("pedidos") if isinstance(dados, dict) else None
    if not isinstance(pedidos, list):
        return _indisponivel(MOTIVO_YAML_ILEGIVEL)

    lido = ler_md(docs_md)
    diag, linhas = lido if lido is not None else (None, None)
    motivo_diag = "" if lido is not None else (
        ler_diagnostico(docs_md).get("motivo") or "docs/diagnostico_banco.md não pode ser lido")

    itens: list[dict] = []
    ids_vistos: set[str] = set()
    for bruto in pedidos:
        if not isinstance(bruto, dict):
            continue
        id_, texto = bruto.get("id"), bruto.get("texto")
        if not isinstance(id_, str) or not id_ or not isinstance(texto, str):
            continue
        estado, evidencia = _avaliar_item(bruto, ids_vistos, diag, linhas, motivo_diag)
        ids_vistos.add(id_)
        detalhe = bruto.get("detalhe")
        prioridade = bruto.get("prioridade")
        nome = bruto.get("checagem")
        itens.append({"id": id_, "texto": texto, "detalhe": detalhe if isinstance(detalhe, str) else None,
                      "prioridade": prioridade if isinstance(prioridade, str) else None,
                      "checagem": nome if isinstance(nome, str) else None,
                      "estado": estado, "evidencia": evidencia})

    return {"disponivel": True, "motivo": None, "gerado_em": diag.get("gerado_em") if diag else None,
            "itens": itens, "contagem": _contagem(itens), "fonte": FONTE}
