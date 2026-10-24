"""Regras puras do diagnóstico do banco da coleta.

Cada função recebe valores já lidos do banco e devolve um veredito ou uma estrutura
pronta para o relatório. Nada aqui faz SQL nem acessa o banco. Ausência é None
(NaN também conta como None), nunca 0.
"""

import re
from datetime import datetime, timedelta, timezone

from processamento.diagnostico.esperado import HORAS_DAILY_UTC, TOLERANCIA_PROB

# ---------------------------------------------------------------------------
# Padrões de texto
# ---------------------------------------------------------------------------

_DATA = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_HORA = r"[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]{1,6})?)?"
_RE_COM_FUSO = re.compile(_DATA + "T" + _HORA + r"[+-][0-9]{2}:[0-9]{2}")
_RE_UTC_Z = re.compile(_DATA + "T" + _HORA + "Z")
_RE_SEM_FUSO = re.compile(_DATA + "[T ]" + _HORA)
_RE_SO_DATA = re.compile(_DATA)
_RE_TICKER = re.compile(r"^[A-Z0-9]{4}[0-9]{1,2}$")
_RE_CNPJ = re.compile(r"[0-9]{14}")
_RE_ID_NOTICIA = re.compile(r"n[0-9]{6,}")


# ---------------------------------------------------------------------------
# Helpers de estrutura e de conversão
# ---------------------------------------------------------------------------

def _nulo(v) -> bool:
    """Verdadeiro para None e para NaN/NaT (valor que não é igual a si mesmo)."""
    if v is None:
        return True
    try:
        return bool(v != v)
    except (TypeError, ValueError):
        return False


def _linhas(dados, colunas):
    """Aceita um DataFrame (lê as colunas pedidas) ou um iterável de tuplas."""
    if hasattr(dados, "itertuples"):
        return dados[list(colunas)].itertuples(index=False, name=None)
    return dados


def nova_secao(titulo) -> dict:
    """Cria a estrutura de uma seção do relatório de diagnóstico."""
    return {"titulo": titulo, "notas": [], "tabelas": [], "divergencias": []}


def adicionar_tabela(secao, subtitulo, colunas, linhas) -> None:
    """Anexa uma tabela (subtítulo, colunas e linhas) à seção."""
    secao["tabelas"].append({"subtitulo": subtitulo, "colunas": colunas, "linhas": linhas})


def div(tema, tabela, detalhe) -> dict:
    """Registra uma divergência entre o esperado e o banco."""
    return {"tema": tema, "tabela": tabela, "detalhe": detalhe}


def inteiro(v) -> int:
    """Converte para int. None e NaN viram 0 (contagens vindas do MySQL/pandas)."""
    if _nulo(v):
        return 0
    return int(v)


def texto(v):
    """Devolve str. Bytes são decodificados em utf-8; None (ou NaN) fica None."""
    if _nulo(v):
        return None
    if isinstance(v, bytes):
        return v.decode("utf-8")
    return v if isinstance(v, str) else str(v)


# ---------------------------------------------------------------------------
# 1 a 4: formato ISO e fuso horário
# ---------------------------------------------------------------------------

def _parseia_iso(v: str, classe: str) -> bool:
    """Confere se o texto que casou com a regex também é uma data/hora válida."""
    s = v[:-1] + "+00:00" if classe == "iso_utc_z" else v
    try:
        datetime.fromisoformat(s)
    except ValueError:
        return False
    return True


def classificar_formato_iso(v) -> str:
    """Classifica o formato de um texto de data/hora.

    Devolve iso_com_fuso, iso_utc_z, iso_sem_fuso, so_data, invalido, nulo ou texto_vazio.
    """
    if _nulo(v):
        return "nulo"
    if not isinstance(v, str):
        return "invalido"
    if not v.strip():
        return "texto_vazio"
    for classe, regex in (
        ("iso_com_fuso", _RE_COM_FUSO),
        ("iso_utc_z", _RE_UTC_Z),
        ("iso_sem_fuso", _RE_SEM_FUSO),
        ("so_data", _RE_SO_DATA),
    ):
        if regex.fullmatch(v):
            return classe if _parseia_iso(v, classe) else "invalido"
    return "invalido"


def offset_iso(v):
    """Devolve o offset (ex.: '-03:00') de um texto com fuso; None nos demais casos."""
    if classificar_formato_iso(v) == "iso_com_fuso":
        return v[-6:]
    return None


def classificar_grupo_iso(exemplo_min, exemplo_max) -> str:
    """Devolve a classe comum aos dois exemplos, ou 'misto' se forem diferentes."""
    classe_min = classificar_formato_iso(exemplo_min)
    classe_max = classificar_formato_iso(exemplo_max)
    return classe_min if classe_min == classe_max else "misto"


def confere_fuso(iso_sp, utc_naive) -> bool:
    """Confere se o texto com fuso representa o mesmo instante que o datetime UTC sem tz.

    Tolerância de menos de 1 segundo. Qualquer valor nulo ou inválido devolve False.
    """
    classe = classificar_formato_iso(iso_sp)
    if classe not in ("iso_com_fuso", "iso_utc_z") or _nulo(utc_naive):
        return False
    if hasattr(utc_naive, "to_pydatetime"):
        utc_naive = utc_naive.to_pydatetime()
    if not isinstance(utc_naive, datetime):
        return False
    if utc_naive.tzinfo is not None:
        utc_naive = utc_naive.astimezone(timezone.utc).replace(tzinfo=None)
    s = iso_sp[:-1] + "+00:00" if classe == "iso_utc_z" else iso_sp
    instante_utc = datetime.fromisoformat(s).astimezone(timezone.utc).replace(tzinfo=None)
    return abs(instante_utc - utc_naive) < timedelta(seconds=1)


# ---------------------------------------------------------------------------
# 5 e resumo: probabilidades do FinBERT
# ---------------------------------------------------------------------------

def veredito_probabilidades(n_nulos, soma, fora, tol=TOLERANCIA_PROB) -> str:
    """Classifica uma linha de probabilidades: sem_prob, parcial, fora_intervalo, soma_errada ou ok."""
    n = inteiro(n_nulos)
    if n == 3:
        return "sem_prob"
    if n in (1, 2):
        return "parcial"
    if not _nulo(fora) and bool(fora):
        return "fora_intervalo"
    if _nulo(soma) or abs(soma - 1) > tol:
        return "soma_errada"
    return "ok"


def resumir_probabilidades(dados) -> dict:
    """Soma as linhas (n_nulos, soma, fora, n) por veredito, ponderando por n.

    Aceita um DataFrame ou um iterável de tuplas. Devolve sempre as 5 chaves.
    """
    contagem = {"ok": 0, "sem_prob": 0, "parcial": 0, "fora_intervalo": 0, "soma_errada": 0}
    for n_nulos, soma, fora, n in _linhas(dados, ("n_nulos", "soma", "fora", "n")):
        contagem[veredito_probabilidades(n_nulos, soma, fora)] += inteiro(n)
    return contagem


# ---------------------------------------------------------------------------
# 6: percentual de datas com hora
# ---------------------------------------------------------------------------

def pct_com_hora_por_ano(dados) -> dict:
    """Percentual de registros com hora por ano. Soma linhas repetidas do mesmo ano."""
    totais = {}
    com_hora = {}
    for ano, total, com in _linhas(dados, ("ano", "total", "com_hora")):
        a = inteiro(ano)
        totais[a] = totais.get(a, 0) + inteiro(total)
        com_hora[a] = com_hora.get(a, 0) + inteiro(com)
    return {
        a: (round(com_hora[a] / totais[a] * 100, 1) if totais[a] else None)
        for a in sorted(totais)
    }


# ---------------------------------------------------------------------------
# 7 e 8: colunas e chaves
# ---------------------------------------------------------------------------

def comparar_colunas(esperadas, reais, ignoradas=()) -> dict:
    """Compara colunas esperadas com as reais. Colunas ignoradas não entram em nenhuma lista."""
    esp = set(esperadas)
    real = set(reais)
    ign = set(ignoradas)
    return {
        "faltando": sorted((esp - real) - ign),
        "extras": sorted((real - esp) - ign),
    }


def comparar_chave(esperada, real) -> str:
    """Compara a chave esperada com a real: igual, ordem_diferente, sem_chave ou diferente."""
    e = list(esperada)
    r = list(real)
    if e == r:
        return "igual"
    if not r:
        return "sem_chave"
    if sorted(e) == sorted(r):
        return "ordem_diferente"
    return "diferente"


# ---------------------------------------------------------------------------
# 9: período da série de notícias (em dias corridos)
# ---------------------------------------------------------------------------

def classificar_dias_periodo(dias: int) -> str:
    """Classifica a quantidade de dias (DATEDIFF + 1) como 3m, 6m, 9m, 12m ou outro."""
    if 88 <= dias <= 93:
        return "3m"
    if 180 <= dias <= 184:
        return "6m"
    if 271 <= dias <= 276:
        return "9m"
    if 364 <= dias <= 367:
        return "12m"
    return "outro"


# ---------------------------------------------------------------------------
# 10: escala de preços (reais ou milhares)
# ---------------------------------------------------------------------------

def veredito_escala(ordens: dict) -> str:
    """Decide a escala a partir da mediana ponderada das ordens de grandeza.

    Mediana ≥ 8 é reais; ≤ 6 é provavel_milhares; 7 é inconclusivo; sem contagem é sem_dados.
    """
    total = sum(inteiro(c) for c in ordens.values())
    if total == 0:
        return "sem_dados"
    acumulado = 0
    mediana = None
    for ordem in sorted(ordens):
        acumulado += inteiro(ordens[ordem])
        if acumulado >= total / 2:
            mediana = ordem
            break
    if mediana >= 8:
        return "reais"
    if mediana <= 6:
        return "provavel_milhares"
    return "inconclusivo"


# ---------------------------------------------------------------------------
# 11 a 13: calendário de pregões e buracos
# ---------------------------------------------------------------------------

def dias_uteis_sem_pregao(datas_ibov) -> list:
    """Dias de segunda a sexta entre a menor e a maior data que não estão na lista do IBOV."""
    datas = {d for d in datas_ibov if d is not None}
    if not datas:
        return []
    faltando = []
    dia = min(datas)
    fim = max(datas)
    while dia <= fim:
        if dia.weekday() < 5 and dia not in datas:
            faltando.append(dia)
        dia += timedelta(days=1)
    return faltando


def buracos_por_ticker(datas_ibov, datas_por_ticker: dict) -> dict:
    """Para cada ticker, lista os pregões que faltam e as datas fora do calendário IBOV.

    Só considera pregões entre a primeira e a última data do próprio ticker.
    """
    calendario = {d for d in datas_ibov if d is not None}
    resultado = {}
    for ticker, datas in datas_por_ticker.items():
        tdatas = {d for d in datas if d is not None}
        if not tdatas:
            resultado[ticker] = {"faltando": [], "fora_do_pregao": []}
            continue
        ini = min(tdatas)
        fim = max(tdatas)
        pregoes = sorted(d for d in calendario if ini <= d <= fim)
        resultado[ticker] = {
            "faltando": [d for d in pregoes if d not in tdatas],
            "fora_do_pregao": sorted(d for d in tdatas if d not in calendario),
        }
    return resultado


def contar_por_ano(datas) -> dict:
    """Conta as datas por ano, em ordem crescente de ano."""
    contagem = {}
    for d in datas:
        if d is None:
            continue
        contagem[d.year] = contagem.get(d.year, 0) + 1
    return dict(sorted(contagem.items()))


# ---------------------------------------------------------------------------
# 14 a 17: padrões e listas de valores
# ---------------------------------------------------------------------------

def tickers_fora_do_padrao(tickers) -> list:
    """Tickers que não seguem o padrão de 4 letras maiúsculas e 1 ou 2 dígitos. Ignora None."""
    fora = {str(t) for t in tickers if not _nulo(t) and not _RE_TICKER.fullmatch(str(t))}
    return sorted(fora)


def cnpjs_fora_do_padrao(cnpjs) -> list:
    """CNPJs que não são exatamente 14 dígitos sem pontuação. Ignora None."""
    fora = {str(c) for c in cnpjs if not _nulo(c) and not _RE_CNPJ.fullmatch(str(c))}
    return sorted(fora)


def comparar_com_referencia(referencia, outro, ignorar=()) -> dict:
    """Compara dois conjuntos. 'ignorar' filtra apenas o que existe só no outro."""
    ref = set(referencia)
    out = set(outro)
    ign = set(ignorar)
    return {
        "so_na_referencia": sorted(ref - out),
        "so_no_outro": sorted((out - ref) - ign),
    }


def valores_fora_da_lista(valores, permitidos) -> list:
    """Valores distintos que não estão na lista permitida. Ignora None."""
    perm = set(permitidos)
    return sorted({v for v in valores if not _nulo(v) and v not in perm})


# ---------------------------------------------------------------------------
# 18 e 19: vazios e divergências por coluna
# ---------------------------------------------------------------------------

def resumo_vazios(total, nulos) -> dict:
    """Percentual de nulos e situação da coluna: vazia, cheia, parcial ou tabela_vazia."""
    total = inteiro(total)
    nulos = inteiro(nulos)
    if total == 0:
        return {"pct_nulo": None, "situacao": "tabela_vazia"}
    pct = round(nulos / total * 100, 1)
    if nulos == total:
        situacao = "vazia"
    elif nulos == 0:
        situacao = "cheia"
    else:
        situacao = "parcial"
    return {"pct_nulo": pct, "situacao": situacao}


def divergencias_coluna(tabela, coluna, situacao, texto_vazio, zeros,
                        vazia_conhecida, zero_proibido, so_nota_preenchimento=False,
                        so_nota_texto_vazio=False) -> list:
    """Lista as divergências de uma coluna em relação à especificação (strings do relatório)."""
    ref = f"`{tabela}.{coluna}`"
    saida = []
    if situacao == "tabela_vazia":  # sem linhas: nada a julgar por coluna
        return saida
    if so_nota_preenchimento:  # só nota (consultas.secao_vazios)
        pass
    elif vazia_conhecida:
        if situacao != "vazia":
            saida.append(f"{ref}: esperada vazia (seção 3.1), mas tem dados ({situacao})")
    elif situacao == "vazia":
        saida.append(f"{ref}: 100% vazia")
    if inteiro(texto_vazio) > 0 and not so_nota_texto_vazio:
        saida.append(f"{ref}: {inteiro(texto_vazio)} textos vazios ('') em vez de NULL")
    if zero_proibido and inteiro(zeros) > 0:
        saida.append(f"{ref}: {inteiro(zeros)} zeros (ausência deve ser NULL)")
    return saida


def nota_preenchimento(tabela, coluna, total, nulos) -> str:
    """Nota de coluna acompanhada só por contagem (ex.: data_mudanca): preenchida em N de M linhas."""
    total, nulos = inteiro(total), inteiro(nulos)
    nota = f"`{tabela}.{coluna}` preenchida em {total - nulos} de {total} linhas"
    return nota + (f" ({nulos} vazias)" if nulos else "")


def nota_texto_vazio(tabela, coluna, n, ids) -> str:
    """Nota de textos vazios numa coluna em que eles são só informação (ex.: título da notícia)."""
    return (f"`{tabela}.{coluna}`: {inteiro(n)} textos vazios ('') (a leitura trata como vazio); "
            f"ids (até 10): {', '.join(str(i) for i in ids)}")


# ---------------------------------------------------------------------------
# 20 e 21: identificadores e agenda da coleta
# ---------------------------------------------------------------------------

def classificar_id_noticia(v) -> bool:
    """Verdadeiro se o id segue o padrão n seguido de 6 ou mais dígitos."""
    return isinstance(v, str) and _RE_ID_NOTICIA.fullmatch(v) is not None


def horas_fora_da_agenda(contagem: dict, horas=HORAS_DAILY_UTC) -> dict:
    """Devolve só as horas (UTC) que não estão na agenda, ordenadas por hora."""
    return {h: contagem[h] for h in sorted(contagem) if h not in horas}


# ---------------------------------------------------------------------------
# Proventos das classes extintas
# ---------------------------------------------------------------------------

def resumo_proventos_por_ticker(linhas, tickers, inicio, fim) -> list:
    """Para cada ticker: [ticker, n, primeira data_com, última data_com, n no período].

    `linhas` = (ticker, data_com como date ou None). O período é [inicio, fim]; sem período,
    a contagem no período é None. Ordena pelos que mais têm proventos no período e depois
    pelo ticker.
    """
    saida = []
    for tk in sorted(set(tickers)):
        datas = [d for t, d in linhas if t == tk and d is not None]
        if inicio is None or fim is None:
            no_periodo = None
        else:
            no_periodo = sum(1 for d in datas if inicio <= d <= fim)
        saida.append([tk, len(datas), min(datas, default=None), max(datas, default=None), no_periodo])
    return sorted(saida, key=lambda r: (-(r[4] or 0), r[0]))
