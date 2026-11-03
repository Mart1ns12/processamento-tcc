"""Leitura dos relatórios do painel: logs da rotina, diagnóstico, experimento e último pytest.

Só lê arquivos gerados pelo projeto (nenhum SQL, nenhum banco). Nenhuma função levanta exceção
por arquivo ausente ou quebrado: devolve `disponivel False` com `motivo`, ou `None`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from processamento.painel.leitores import duracao_segundos

RE_INICIO = re.compile(r"^Rotina de (\d{4}-\d{2}-\d{2}) \(início (\d{2}:\d{2}:\d{2})(, --sem-esperar)?\)$")
RE_CONSULTA = re.compile(r"^(\d{2}:\d{2}:\d{2}) consulta (\d+): (.*)$")
RE_SAIDA = re.compile(r"^Saída de \S+ em .+: status (\w+)$")
RE_SEM_PREGAO = re.compile(r"não é pregão previsto \((.+)\): nada a gerar\.$")
RE_LOG_ROTINA = re.compile(r"^rotina-(\d{4}-\d{2}-\d{2})\.log$")
RE_SECAO = re.compile(r"^## (\d+)\. (.+)$")
RE_SEPARADOR = re.compile(r"^\|[\s:|-]*-[\s:|-]*$")
RE_DEV = re.compile(r"^dev-(\d{4}-\d{2}-\d{2})$")
RE_TOP = re.compile(r"^(\d{4}-\d{2}-\d{2})\.top\.json$")
RE_PYTEST_INICIO = re.compile(r"^# painel: acao=\S+ inicio=(\S+) comando=")
RE_PYTEST_FIM = re.compile(r"^# painel: fim=(\S+) codigo=(-?\d+)")
RE_PYTEST_RESUMO = re.compile(
    r"^=*\s*(no tests ran|\d+ (passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?))"
)
RE_PAR = re.compile(r"(\d+) (\w+)")
RE_TEMPO = re.compile(r" in ([\d.]+s)")

TITULO_DIVERGENCIAS = "## Divergências × especificação"
ORDEM_MODELOS = [
    ("modelo_3", "Modelo 3 (com notícias)"),
    ("modelo_1", "Modelo 1 (sem notícias)"),
    ("logistica", "Regressão logística"),
    ("volatilidade", "Regra da volatilidade"),
]
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


def _ultima_pasta_dev(raiz: Path) -> Path | None:
    """Pasta `dev-AAAA-MM-DD` de saida/experimento/treino com a maior data no nome."""
    candidatos = []
    for p in _listar(raiz / "saida" / "experimento" / "treino"):
        m = RE_DEV.match(p.name)
        if m and p.is_dir():
            candidatos.append((m.group(1), p))
    if not candidatos:
        return None
    return max(candidatos, key=lambda t: t[0])[1]


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


def _re_meta(familia: str, sombra: bool = False) -> re.Pattern:
    """Meta do modelo da família: `<familia>-AAAA-MM.meta.json`, ou a sombra `<familia>-m1-AAAA-MM.meta.json`."""
    prefixo = re.escape(f"{familia}-m1-" if sombra else f"{familia}-")
    return re.compile(rf"^{prefixo}(\d{{4}}-\d{{2}})\.meta\.json$")


def _resumo_meta(caminho: Path, mes: str) -> dict | None:
    """Resumo de um `<familia>-AAAA-MM.meta.json` (ou da sombra); None se ilegível."""
    meta = _ler_json(caminho)
    if meta is None:
        return None
    validacao = _d(meta.get("metricas_validacao"))
    calibracao = _d(meta.get("calibracao"))
    return {
        "arquivo": caminho.name,
        "mes": mes,
        "modelo": meta.get("modelo"),
        "provisorio": meta.get("provisorio"),
        "periodo_treino": meta.get("periodo_treino"),
        "n_linhas_treino": meta.get("n_linhas_treino"),
        "gerado_em": meta.get("gerado_em"),
        "auc_medio_pregao": validacao.get("auc_medio_pregao"),
        "acerto_top5": validacao.get("taxa_acerto_top5"),
        "calibracao_aprovada": calibracao.get("aprovada"),
        "chance_exibida": calibracao.get("chance_exibida"),
        "aviso": meta.get("aviso"),
    }


def _ler_desenvolvimento(raiz: Path) -> dict:
    """Resumo do treino de desenvolvimento mais recente (`dev-AAAA-MM-DD/metricas.json`)."""
    pasta = _ultima_pasta_dev(raiz)
    if pasta is None:
        return {"disponivel": False, "motivo": "nenhum treino de desenvolvimento em saida/experimento/treino/"}
    metricas = _ler_json(pasta / "metricas.json")
    if metricas is None:
        return {"disponivel": False, "motivo": f"metricas.json ausente ou ilegível em {pasta.name}"}

    modelos_json = _d(metricas.get("modelos"))
    modelos = []
    for nome, rotulo in ORDEM_MODELOS:
        bloco = _d(modelos_json.get(nome))
        if not bloco:
            continue
        top5 = _d(_d(bloco.get("topk")).get("5"))
        modelos.append({
            "nome": nome,
            "rotulo": rotulo,
            "auc_medio_pregao": bloco.get("auc_medio_pregao"),
            "acerto_top5": top5.get("taxa_acerto"),
            "ic_top5": top5.get("ic_taxa"),
        })

    acaso = _d(_d(metricas.get("acaso")).get("5"))
    acaso_top5 = {"media": acaso.get("media"), "faixa": [acaso.get("p2_5"), acaso.get("p97_5")]} if acaso else None
    calibracao = _d(metricas.get("calibracao"))
    return {
        "disponivel": True,
        "pasta": pasta.name,
        "modo": metricas.get("modo"),
        "aviso_funcionamento": metricas.get("aviso_funcionamento"),
        "gerado_em": metricas.get("gerado_em"),
        "periodo": _d(metricas.get("periodo")),
        "acaso_top5": acaso_top5,
        "modelos": modelos,
        "veredito": _d(metricas.get("veredito_modelo_3")).get("texto"),
        "calibracao": {
            "ece": calibracao.get("ece"),
            "aprovada": calibracao.get("aprovada"),
            "chance_exibida": calibracao.get("chance_exibida"),
        },
        "tem_relatorio": (pasta / "relatorio.md").is_file(),
    }


def caminho_ultimo_relatorio(raiz: Path) -> Path | None:
    """`relatorio.md` do treino de desenvolvimento mais recente; None se não há pasta de treino."""
    pasta = _ultima_pasta_dev(raiz)
    return None if pasta is None else pasta / "relatorio.md"


def ler_experimento(raiz: Path, params: dict) -> dict:
    """Situação do modelo, modelo sombra, treino de desenvolvimento, registros e teste final."""
    modelo_oficial = bool(params.get("modelo_oficial"))
    publicar_provisorio = bool(params.get("publicar_top_provisorio"))
    pasta_modelos = raiz / "modelos"
    familia = params.get("familia_producao") or "xgb"  # a família em produção (treino.familia_producao)

    em_uso = _mais_novo(pasta_modelos, _re_meta(familia))
    sombra = _mais_novo(pasta_modelos, _re_meta(familia, sombra=True))
    modelo_em_uso = _resumo_meta(em_uso[1], em_uso[0]) if em_uso else None
    modelo_sombra = _resumo_meta(sombra[1], sombra[0]) if sombra else None
    situacao = "oficial" if modelo_oficial and modelo_em_uso and modelo_em_uso["provisorio"] is False else "provisório"

    desenvolvimento = _ler_desenvolvimento(raiz)

    pasta_registros = raiz / "registros" / "experimento"
    tops = [p for p in _listar(pasta_registros) if RE_TOP.match(p.name)]
    resultados = [p for p in _listar(pasta_registros) if p.name.endswith(".resultado.json")]
    datas_top = [RE_TOP.match(p.name).group(1) for p in tops]

    return {
        "situacao_modelo": situacao,
        "top_publicado": modelo_oficial or publicar_provisorio,
        "mostrar_aviso": (not modelo_oficial) or desenvolvimento.get("aviso_funcionamento") is not False,
        "modelo_em_uso": modelo_em_uso,
        "modelo_sombra": modelo_sombra,
        "n_meta": sum(1 for p in _listar(pasta_modelos) if p.name.endswith(".meta.json")),
        "desenvolvimento": desenvolvimento,
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


def duracao_ultima_acao(pasta_logs_painel: Path, acao_id: str, max_arquivos: int = 20) -> int | None:
    """Segundos da execução mais recente da ação, pelos logs do painel (cabeçalho inicio= e rodapé fim=).

    Ignora execução sem rodapé (em andamento ou interrompida), parada pelo painel (parado=sim)
    ou com código de saída de erro. None se nenhuma servir.
    """
    arquivos = [p for p in _listar(pasta_logs_painel)
                if p.name.startswith(acao_id + "-") and p.name.endswith(".log") and p.is_file()]
    for arquivo in sorted(arquivos, key=lambda p: p.name, reverse=True)[:max_arquivos]:
        inicio = fim = codigo = None
        parado = False
        for linha in _ler_texto(arquivo).splitlines():
            m = RE_PYTEST_INICIO.match(linha)
            if m and inicio is None:
                inicio = m.group(1)
                continue
            m = RE_PYTEST_FIM.match(linha)
            if m:
                fim, codigo, parado = m.group(1), int(m.group(2)), "parado=sim" in linha
        if inicio is None or fim is None or parado or codigo not in CODIGOS_COMPLETOS.get(acao_id, {0}):
            continue
        segundos = duracao_segundos(inicio, fim)
        if segundos is not None:
            return segundos
    return None


def duracoes_painel(pasta_logs_painel: Path, ids: list[str]) -> dict[str, int | None]:
    """{id da ação: segundos da última execução completa pelo painel, ou None}."""
    return {acao_id: duracao_ultima_acao(pasta_logs_painel, acao_id) for acao_id in ids}
