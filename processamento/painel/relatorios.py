"""Leitura dos relatórios do painel: logs da rotina, diagnóstico, experimento (só a operação) e último pytest.

Só lê arquivos gerados pelo projeto (nenhum SQL, nenhum banco). Nenhuma função levanta exceção
por arquivo ausente ou quebrado: devolve `disponivel False` com `motivo`, ou `None`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from processamento.painel.leitores import _instante, duracao_segundos

RE_INICIO = re.compile(r"^Rotina de (\d{4}-\d{2}-\d{2}) \(início (\d{2}:\d{2}:\d{2})(, --sem-esperar)?\)$")
RE_CONSULTA = re.compile(r"^(\d{2}:\d{2}:\d{2}) consulta (\d+): (.*)$")
RE_SAIDA = re.compile(r"^Saída de \S+ em .+: status (\w+)$")
RE_SEM_PREGAO = re.compile(r"não é pregão previsto \((.+)\): nada a gerar\.$")
RE_LOG_ROTINA = re.compile(r"^rotina-(\d{4}-\d{2}-\d{2})\.log$")
RE_SECAO = re.compile(r"^## (\d+)\. (.+)$")
RE_SEPARADOR = re.compile(r"^\|[\s:|-]*-[\s:|-]*$")
RE_TOP = re.compile(r"^(\d{4}-\d{2}-\d{2})\.top\.json$")
RE_PYTEST_INICIO = re.compile(r"^# painel: acao=\S+ inicio=(\S+) comando=")
RE_PYTEST_FIM = re.compile(r"^# painel: fim=(\S+) codigo=(-?\d+)")
RE_PYTEST_RESUMO = re.compile(
    r"^=*\s*(no tests ran|\d+ (passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?))"
)
RE_PAR = re.compile(r"(\d+) (\w+)")
RE_TEMPO = re.compile(r" in ([\d.]+s)")

# Marcadores que o `processamento/painel/dia.py` imprime (uma linha por etapa; `em=` só nos fins novos).
RE_DIA_INICIO = re.compile(r"^# dia: etapa=(\w+) inicio=(\S+)$")
RE_DIA_FIM = re.compile(r"^# dia: etapa=(\w+) fim codigo=(-?\d+)(?: em=(\S+))? detalhe=(.*)$")
RE_DIA_PULADA = re.compile(r"^# dia: etapa=(\w+) pulada motivo=(.*)$")
IDS_ETAPAS_DIA = ("rotina", "carga", "publicador")

TITULO_DIVERGENCIAS = "## Divergências × especificação"
NORMALIZA_CONTAGEM = {"error": "errors", "warning": "warnings"}


def _ler_json(caminho: Path) -> dict | None:
    """Lê um JSON-objeto; None se ausente, ilegível ou de outro tipo."""
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dado if isinstance(dado, dict) else None


def _d(valor) -> dict:
    """Devolve o valor se for dict, senão um dict vazio (evita KeyError em JSON estranho)."""
    return valor if isinstance(valor, dict) else {}


def _listar(pasta: Path) -> list[Path]:
    """Conteúdo ordenado da pasta; lista vazia se ela não existe ou não é pasta."""
    try:
        return sorted(pasta.iterdir())
    except OSError:
        return []


def _ler_texto(caminho: Path) -> str:
    """Texto do arquivo (erros de codificação trocados por �); vazio se não pode ser lido."""
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mais_novo(pasta: Path, regex: re.Pattern) -> tuple[str, Path] | None:
    """Arquivo da pasta que casa `regex` com o maior grupo 1 (AAAA-MM ou AAAA-MM-DD) e o grupo 1."""
    candidatos = []
    for p in _listar(pasta):
        m = regex.match(p.name)
        if m and p.is_file():
            candidatos.append((m.group(1), p))
    if not candidatos:
        return None
    grupo, caminho = max(candidatos, key=lambda t: t[0])
    return grupo, caminho


# ---------------------------------------------------------------- logs da rotina

def resultado_terminal(linha: str) -> tuple[str, str] | None:
    """Resultado de uma linha que termina a rodada: (tipo, detalhe), ou None se a linha não termina nada."""
    m = RE_SEM_PREGAO.search(linha)
    if m:
        return "sem_pregao", m.group(1)
    if linha.startswith("outra rotina em andamento"):
        return "trava", linha
    if linha.startswith(("Saída não gerada:", "Coleta não terminou até")):
        return "falhou", linha
    if linha.startswith(("Configuração do banco incompleta", "Configuração inválida")):
        return "configuracao", linha
    if (
        linha.startswith("Falha ao conectar ao banco")
        or "Rodada interrompida" in linha
        or linha.endswith("A coleta não foi alterada.")
    ):
        return "sem_banco", linha
    return None


def _classificar_linha(rodada: dict, linha: str) -> None:
    """Põe uma linha dentro da rodada: consulta, resultado, aviso ou 'outras'."""
    m = RE_CONSULTA.match(linha)
    if m:
        rodada["consultas"].append({"hora": m.group(1), "numero": int(m.group(2)), "texto": m.group(3)})
        return
    m = RE_SAIDA.match(linha)
    if m:
        rodada["resultado"] = m.group(1)
        return
    fim = resultado_terminal(linha)
    if fim is not None:
        rodada["resultado"], rodada["detalhe"] = fim
        return
    if linha.startswith("- "):
        rodada["avisos"].append(linha[2:])
    elif linha.startswith("Aviso: "):
        rodada["avisos"].append(linha[7:])
    else:
        rodada["outras"].append(linha)


def analisar_log_rotina(texto: str) -> list[dict]:
    """Separa o log de um dia em rodadas (uma por cabeçalho 'Rotina de ...') e classifica as linhas."""
    rodadas: list[dict] = []
    atual = None
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        m = RE_INICIO.match(linha)
        if m:
            atual = {
                "data": m.group(1),
                "inicio": m.group(2),
                "sem_esperar": m.group(3) is not None,
                "consultas": [],
                "resultado": "incompleta",
                "detalhe": None,
                "avisos": [],
                "outras": [],
            }
            rodadas.append(atual)
            continue
        if atual is not None:
            _classificar_linha(atual, linha)
    return rodadas


def ler_logs_rotina(pasta_logs: Path, max_arquivos: int = 10) -> dict:
    """Rodadas dos logs `rotina-AAAA-MM-DD.log` da pasta, da data mais nova para a mais antiga."""
    candidatos = []
    for p in _listar(pasta_logs):
        m = RE_LOG_ROTINA.match(p.name)
        if m and p.is_file():
            candidatos.append((m.group(1), p))
    if not candidatos:
        return {"disponivel": False, "motivo": "nenhum log da rotina em logs/", "arquivos": []}
    candidatos.sort(key=lambda t: t[0], reverse=True)
    arquivos = [
        {"arquivo": p.name, "data": data, "rodadas": analisar_log_rotina(_ler_texto(p))}
        for data, p in candidatos[:max_arquivos]
    ]
    return {"disponivel": True, "motivo": None, "arquivos": arquivos}


# ---------------------------------------------------------------- diagnóstico do banco

def _celulas(linha: str) -> list[str]:
    """Células de uma linha de tabela markdown; `\\|` vira `|` dentro da célula."""
    partes = re.split(r"(?<!\\)\|", linha.strip().strip("|"))
    return [p.strip().replace("\\|", "|") for p in partes]


def ler_diagnostico(caminho: Path) -> dict:
    """Divergências e seções do `docs/diagnostico_banco.md`. Sem as linhas Banco: e MySQL:."""
    if not caminho.is_file():
        return {"disponivel": False, "motivo": "docs/diagnostico_banco.md não encontrado (rode o diagnóstico)"}
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return {"disponivel": False, "motivo": "docs/diagnostico_banco.md não pode ser lido"}

    linhas = texto.splitlines()
    inicio = next((i for i, linha in enumerate(linhas) if linha.strip() == TITULO_DIVERGENCIAS), None)
    if inicio is None:
        return {"disponivel": False, "motivo": "formato não reconhecido"}

    gerado_em = None
    for linha in linhas:
        if linha.startswith("- Gerado em: "):
            gerado_em = linha[len("- Gerado em: "):].strip()
            break

    fim_div = next((i for i in range(inicio + 1, len(linhas)) if RE_SECAO.match(linhas[i])), len(linhas))
    divergencias = []
    cabecalho_lido = False
    for linha in linhas[inicio + 1:fim_div]:
        if not linha.startswith("|") or RE_SEPARADOR.match(linha):
            continue
        if not cabecalho_lido:
            cabecalho_lido = True
            continue
        celulas = _celulas(linha)
        celulas += [""] * (4 - len(celulas))
        divergencias.append({"numero": celulas[0], "tema": celulas[1], "tabela": celulas[2], "detalhe": celulas[3]})

    secoes = []
    em_notas = False
    for linha in linhas[inicio + 1:]:
        m = RE_SECAO.match(linha)
        if m:
            secoes.append({"numero": int(m.group(1)), "titulo": m.group(2).strip(), "notas": []})
            em_notas = True
            continue
        if linha.startswith("## ") or linha.startswith("### "):
            em_notas = False
            continue
        if em_notas and linha.startswith("- "):
            nota = linha[2:].strip()
            if not nota.startswith(("Banco:", "MySQL:")):
                secoes[-1]["notas"].append(nota)

    return {
        "disponivel": True,
        "motivo": None,
        "gerado_em": gerado_em,
        "sem_divergencias": not divergencias,
        "divergencias": divergencias,
        "secoes": secoes,
    }


# ---------------------------------------------------------------- experimento

def trava_teste_final(params: dict, raiz: Path) -> dict:
    """Estado do teste final (uso único) a partir de `params['teste_final']` e do registro de uso."""
    teste = _d(params.get("teste_final"))
    inicio = teste.get("inicio")
    fim = teste.get("fim")
    liberado = bool(teste.get("liberado"))
    if (raiz / "docs" / "teste_final_usado.json").exists():
        estado, texto = "usado", "O teste final já foi usado (uso único)."
    elif fim is None:
        estado, texto = "ativa", "Trava ativa: treino.teste_final.fim vazio; o teste final não roda."
    elif not liberado:
        estado = "definido_nao_liberado"
        texto = "Fim definido, mas o teste final ainda não foi liberado (treino.teste_final.liberado = false)."
    else:
        estado, texto = "liberado", "Liberado: falta rodar o treino com --teste-final (uso único)."
    return {"estado": estado, "texto": texto, "inicio": inicio, "fim": fim, "liberado": liberado}


def _re_meta(familia: str) -> re.Pattern:
    """Meta do modelo da família: `<familia>-AAAA-MM.meta.json`."""
    prefixo = re.escape(f"{familia}-")
    return re.compile(rf"^{prefixo}(\d{{4}}-\d{{2}})\.meta\.json$")


def _resumo_meta(caminho: Path, mes: str, familia: str) -> dict | None:
    """Resumo de um `<familia>-AAAA-MM.meta.json` (sem métricas de desempenho); None se ilegível."""
    meta = _ler_json(caminho)
    if meta is None:
        return None
    dataset = meta.get("dataset")
    versao_preparacao = meta.get("versao_preparacao")
    versao_noticias = meta.get("versao_noticias")
    return {
        "arquivo": caminho.name,
        "mes": mes,
        "familia": meta["familia"] if isinstance(meta.get("familia"), str) else familia,
        "modelo": meta.get("modelo"),
        "versao_preparacao": (
            versao_preparacao
            if isinstance(versao_preparacao, int) and not isinstance(versao_preparacao, bool) else None
        ),
        "versao_noticias": versao_noticias if isinstance(versao_noticias, str) else None,
        "provisorio": meta.get("provisorio"),
        "periodo_treino": meta.get("periodo_treino"),
        "n_linhas_treino": meta.get("n_linhas_treino"),
        "gerado_em": meta.get("gerado_em"),
        "dataset": (
            {"arquivo": dataset.get("arquivo"), "sha256": dataset.get("sha256")} if isinstance(dataset, dict) else None
        ),
        "aviso": meta.get("aviso"),
    }


def ler_experimento(raiz: Path, params: dict) -> dict:
    """Situação do modelo em produção, registros e teste final (sem métricas de desempenho)."""
    modelo_oficial = bool(params.get("modelo_oficial"))
    publicar_provisorio = bool(params.get("publicar_top_provisorio"))
    pasta_modelos = raiz / "modelos"
    familia = params.get("familia_producao") or "xgb"  # a família em produção (treino.familia_producao)

    em_uso = _mais_novo(pasta_modelos, _re_meta(familia))
    modelo_em_uso = _resumo_meta(em_uso[1], em_uso[0], familia) if em_uso else None
    situacao = "oficial" if modelo_oficial and modelo_em_uso and modelo_em_uso["provisorio"] is False else "provisório"

    pasta_registros = raiz / "registros" / "experimento"
    tops = [p for p in _listar(pasta_registros) if RE_TOP.match(p.name)]
    resultados = [p for p in _listar(pasta_registros) if p.name.endswith(".resultado.json")]
    datas_top = [RE_TOP.match(p.name).group(1) for p in tops]

    return {
        "situacao_modelo": situacao,
        "top_publicado": modelo_oficial or publicar_provisorio,
        "modelo_em_uso": modelo_em_uso,
        "n_meta": sum(1 for p in _listar(pasta_modelos) if p.name.endswith(".meta.json")),
        "registros": {
            "tops": len(tops),
            "resultados": len(resultados),
            "ultimo_top": max(datas_top) if datas_top else None,
        },
        "trava_teste_final": trava_teste_final(params, raiz),
    }


# ---------------------------------------------------------------- último pytest

def ler_ultimo_pytest(pasta_logs_painel: Path) -> dict:
    """Resumo do último `testes-*.log` gravado pelo painel (cabeçalho, rodapé, contagens e falhas)."""
    arquivos = [p for p in _listar(pasta_logs_painel) if p.name.startswith("testes-") and p.name.endswith(".log")]
    if not arquivos:
        return {"disponivel": False, "motivo": "nenhum pytest rodado pelo painel ainda"}
    arquivo = sorted(arquivos, key=lambda p: p.name)[-1]

    inicio = fim = codigo = None
    resumo = None
    falhas: list[str] = []
    for linha in _ler_texto(arquivo).splitlines():
        m = RE_PYTEST_INICIO.match(linha)
        if m:
            inicio = m.group(1)
            continue
        m = RE_PYTEST_FIM.match(linha)
        if m:
            fim, codigo = m.group(1), int(m.group(2))
            continue
        if RE_PYTEST_RESUMO.match(linha):
            resumo = linha
            continue
        if (linha.startswith("FAILED ") or linha.startswith("ERROR ")) and len(falhas) < 20:
            falhas.append(linha)

    contagens: dict[str, int] = {}
    tempo = None
    if resumo is not None:
        for numero, nome in RE_PAR.findall(resumo):
            contagens[NORMALIZA_CONTAGEM.get(nome, nome)] = int(numero)
        m = RE_TEMPO.search(resumo)
        tempo = m.group(1) if m else None

    return {
        "disponivel": True,
        "arquivo": arquivo.name,
        "inicio": inicio,
        "fim": fim,
        "codigo": codigo,
        "aprovado": None if codigo is None else codigo == 0,
        "interrompido": codigo is None,
        "contagens": contagens,
        "tempo": tempo,
        "falhas": falhas,
    }


# ---------------------------------------------------------------- duração das ações

CODIGOS_COMPLETOS = {"testes": {0, 1}}   # pytest com falhas também rodou até o fim


def _arquivos_da_acao(pasta_logs_painel: Path, acao_id: str, max_arquivos: int) -> list[Path]:
    """Logs `<acao_id>-*.log` da pasta, do mais novo para o mais antigo, no máximo `max_arquivos`."""
    arquivos = [p for p in _listar(pasta_logs_painel)
                if p.name.startswith(acao_id + "-") and p.name.endswith(".log") and p.is_file()]
    return sorted(arquivos, key=lambda p: p.name, reverse=True)[:max_arquivos]


def _cabecalho_rodape(linhas: list[str]) -> tuple[str | None, str | None, int | None, bool]:
    """(inicio, fim, codigo, parado) do log do painel: primeiro cabeçalho inicio= e último rodapé fim=."""
    inicio = fim = codigo = None
    parado = False
    for linha in linhas:
        m = RE_PYTEST_INICIO.match(linha)
        if m and inicio is None:
            inicio = m.group(1)
            continue
        m = RE_PYTEST_FIM.match(linha)
        if m:
            fim, codigo, parado = m.group(1), int(m.group(2)), "parado=sim" in linha
    return inicio, fim, codigo, parado


def duracao_ultima_acao(pasta_logs_painel: Path, acao_id: str, max_arquivos: int = 20) -> int | None:
    """Segundos da execução mais recente da ação, pelos logs do painel (cabeçalho inicio= e rodapé fim=).

    Ignora execução sem rodapé (em andamento ou interrompida), parada pelo painel (parado=sim)
    ou com código de saída de erro. None se nenhuma servir.
    """
    for arquivo in _arquivos_da_acao(pasta_logs_painel, acao_id, max_arquivos):
        inicio, fim, codigo, parado = _cabecalho_rodape(_ler_texto(arquivo).splitlines())
        if inicio is None or fim is None or parado or codigo not in CODIGOS_COMPLETOS.get(acao_id, {0}):
            continue
        segundos = duracao_segundos(inicio, fim)
        if segundos is not None:
            return segundos
    return None


def _hora_valida(texto: str | None) -> str | None:
    """A hora ISO como veio do log, se for uma data e hora com fuso (ou sem fuso); None para `10:00:00`."""
    return texto if _instante(texto) is not None else None


def tempos_etapas_dia(linhas: list[str]) -> dict[str, dict]:
    """{etapa: {"inicio", "fim", "codigo"}} das etapas do dia (rotina, carga, publicador).

    `inicio` e `fim` ficam como ISO do log, ou None (logs antigos só têm a hora, e a etapa pulada não tem código).
    """
    tempos = {i: {"inicio": None, "fim": None, "codigo": None} for i in IDS_ETAPAS_DIA}
    for linha in linhas:
        m = RE_DIA_INICIO.match(linha)
        if m and m.group(1) in tempos:
            tempos[m.group(1)]["inicio"] = _hora_valida(m.group(2))
            continue
        m = RE_DIA_FIM.match(linha)
        if m and m.group(1) in tempos:
            tempos[m.group(1)]["codigo"] = int(m.group(2))
            tempos[m.group(1)]["fim"] = _hora_valida(m.group(3))
    return tempos


def medias_etapas_dia(pasta_logs_painel: Path, n: int | None, max_arquivos: int = 20) -> dict:
    """Média (segundos) de cada etapa do dia nas últimas `n` execuções completas do painel.

    Só conta log com rodapé e sem parado=sim, e em cada etapa só as durações de código 0 com início e fim
    em ISO. {"medias": {etapa: int|None}, "amostras": {etapa: int}}; sem n válido ou sem logs, tudo None/0.
    """
    medias = {i: None for i in IDS_ETAPAS_DIA}
    amostras = {i: 0 for i in IDS_ETAPAS_DIA}
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        return {"medias": medias, "amostras": amostras}
    duracoes: dict[str, list[int]] = {i: [] for i in IDS_ETAPAS_DIA}
    for arquivo in _arquivos_da_acao(pasta_logs_painel, "dia", max_arquivos):
        linhas = _ler_texto(arquivo).splitlines()
        _inicio, fim, _codigo, parado = _cabecalho_rodape(linhas)
        if fim is None or parado:
            continue
        tempos = tempos_etapas_dia(linhas)
        for i in IDS_ETAPAS_DIA:
            t = tempos[i]
            if t["codigo"] != 0 or len(duracoes[i]) >= n:
                continue
            segundos = duracao_segundos(t["inicio"], t["fim"])
            if segundos is not None:
                duracoes[i].append(segundos)
    for i in IDS_ETAPAS_DIA:
        if duracoes[i]:
            medias[i] = round(sum(duracoes[i]) / len(duracoes[i]))
            amostras[i] = len(duracoes[i])
    return {"medias": medias, "amostras": amostras}


def duracoes_painel(pasta_logs_painel: Path, ids: list[str]) -> dict[str, int | None]:
    """{id da ação: segundos da última execução completa pelo painel, ou None}."""
    return {acao_id: duracao_ultima_acao(pasta_logs_painel, acao_id) for acao_id in ids}
