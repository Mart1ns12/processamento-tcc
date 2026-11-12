"""Rodar o dia completo: rotina -> carga completa -> publicador do projeto da API, em sequência.

Roda como filho do painel (python -m processamento.painel.dia --data AAAA-MM-DD). Não acessa banco nem
rede por conta própria: só chama os três comandos fixos e lê saida/D/execucao.json.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import deque
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from os import environ
from pathlib import Path

from processamento.calendario import SP
from processamento.painel import leitores, relatorios

RE_PUB_SO_EXECUCAO = re.compile(r"^\d{2}/\d{2}/\d{4}: só a execução foi gravada")
RE_PUB_COMPLETA = re.compile(r"^\d{2}/\d{2}/\d{4} publicado \(modo")
RE_PUB_RECUSADA = re.compile(r"^Publicação de .* recusada|^Não publicado:")

# Variáveis do banco da coleta (e do Python/ambiente do processamento) que o publicador não deve herdar.
_NAO_HERDADAS = {
    "IP_BANCO", "PORTA_BANCO", "NOME_BANCO", "USER_BANCO", "SENHA_BANCO",
    "USER_ESCRITA", "SENHA_ESCRITA", "USER_LEITURA", "SENHA_LEITURA",
    "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV",
}

# Chave do resultado (marcador "# dia: resultado=<chave> <frase>") -> frase.
_FRASES = {
    "completa": "publicado no banco da API (completo)",
    "so_execucao": "só a execução gravada (a rotina falhou)",
    "sem_saida": "nada publicado: a rotina não gerou saída nova (sem pregão, configuração, banco ou trava)",
    "carga_falhou": "nada publicado: a carga completa falhou",
    "publicador_bloqueado": "nada publicado: a rotina falhou, mas há uma carga completa antiga deste dia",
    "recusada": "publicador recusou a publicação (motivo no log)",
    "erro_publicador": "publicador: configuração ou banco da API",
}


def verificar_publicador(raiz: Path, params_painel: dict) -> dict:
    """{"dir_api": str|None, "python": str|None, "motivo": str|None}. Só is_dir/is_file; nunca lê arquivo da API."""
    vazio = {"dir_api": None, "python": None}
    dir_api = params_painel.get("dir_api")
    if not dir_api:
        return {**vazio, "motivo": "Projeto da API não configurado: falta dir_api em processamento/config/painel.yaml."}
    pasta = Path(raiz) / dir_api
    if not pasta.is_dir():
        return {**vazio, "motivo": f"Pasta do projeto da API não encontrada ({pasta})."}
    python = None
    for candidato in (pasta / ".venv" / "Scripts" / "python.exe", pasta / ".venv" / "bin" / "python"):
        if candidato.is_file():
            python = candidato
            break
    if python is None:
        return {**vazio, "motivo": "Python do projeto da API não encontrado em .venv (crie o ambiente virtual lá)."}
    if not (pasta / "publicador" / "__main__.py").is_file():
        return {**vazio, "motivo": "Publicador não encontrado na pasta do projeto da API."}
    return {"dir_api": str(pasta), "python": str(python), "motivo": None}


def ambiente_publicador(base: Mapping[str, str], raiz: Path) -> dict[str, str]:
    """Copia base sem as variáveis do banco da coleta nem PROC_*; define PROC_DIR_PROCESSAMENTO e saída em utf-8."""
    env = {}
    for chave, valor in base.items():
        maiuscula = chave.upper()
        if maiuscula in _NAO_HERDADAS or maiuscula.startswith("PROC_"):
            continue
        env[chave] = valor
    env["PROC_DIR_PROCESSAMENTO"] = str(raiz)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def status_rotina(raiz: Path, pasta_saida: str, d: date, desde: datetime) -> str | None:
    """registros[0].status do saida/D/execucao.json se registros[0].gerado_em >= desde - 1 s; senão None."""
    dados, _erro = leitores.ler_json(Path(raiz) / pasta_saida / d.isoformat() / "execucao.json")
    if not isinstance(dados, dict):
        return None
    registros = dados.get("registros")
    if not isinstance(registros, list) or not registros or not isinstance(registros[0], dict):
        return None
    primeiro = registros[0]
    gerado = leitores._instante(primeiro.get("gerado_em"))
    if gerado is None or gerado < desde - timedelta(seconds=1):
        return None
    status = primeiro.get("status")
    return status if isinstance(status, str) else None


def resultado_publicador(linhas: list[str]) -> str | None:
    """"so_execucao" | "completa" | "recusada" | None, pela última linha que o publicador escreveu."""
    for linha in reversed(linhas):
        if RE_PUB_SO_EXECUCAO.match(linha):
            return "so_execucao"
        if RE_PUB_COMPLETA.match(linha):
            return "completa"
        if RE_PUB_RECUSADA.match(linha):
            return "recusada"
    return None


def _marca(imprimir: Callable[[str], object], texto: str) -> None:
    imprimir(f"# dia: {texto}")


def _hora(m: datetime) -> str:
    return m.isoformat(timespec="seconds")


def _resultado(imprimir: Callable[[str], object], chave: str, codigo: int) -> int:
    _marca(imprimir, f"resultado={chave} {_FRASES[chave]}")
    return codigo


def executar_dia(d: date, raiz: Path, params_painel: dict, *, rodar, imprimir=print, relogio=None,
                 ambiente=None, esperar: bool = False) -> int:
    """Roda rotina, carga e publicador em sequência e devolve o código de saída (ver SIGNIFICADOS["dia"]).

    `esperar` False (painel): rotina com --sem-esperar. True (agendador): a rotina espera a coleta nos
    prazos dela (parametros.yaml: prazo e prazo_tardio).
    """
    agora = relogio or (lambda: datetime.now(SP))
    base = dict(environ) if ambiente is None else dict(ambiente)
    raiz = Path(raiz)
    dia = d.isoformat()

    api = verificar_publicador(raiz, params_painel)
    if api["motivo"]:
        _marca(imprimir, f"resultado=configuracao {api['motivo']}")
        return 2

    # 1. Rotina (só leitura do banco da coleta)
    inicio = agora()
    _marca(imprimir, f"etapa=rotina inicio={_hora(inicio)}")
    argv_rotina = [sys.executable, "-m", "processamento.rotina", "--data", dia]
    if not esperar:
        argv_rotina.append("--sem-esperar")
    codigo, linhas = rodar(argv_rotina, raiz, base)
    status = status_rotina(raiz, "saida", d, inicio)
    if any(relatorios.RE_SEM_PREGAO.search(linha) for linha in linhas):
        detalhe = "dia sem pregão"
    elif status is not None:
        detalhe = f"status {status}"
    else:
        detalhe = f"código {codigo}, sem saída nova"
    _marca(imprimir, f"etapa=rotina fim codigo={codigo} em={_hora(agora())} detalhe={detalhe}")

    if status is None or status == "em_andamento":
        _marca(imprimir, "etapa=carga pulada motivo=a rotina não gerou saída nova")
        _marca(imprimir, "etapa=publicador pulada motivo=a rotina não gerou saída nova")
        return _resultado(imprimir, "sem_saida", 3)

    if status in ("ok", "parcial"):
        # 2. Carga completa (só leitura do banco; grava em saida_completa/)
        _marca(imprimir, f"etapa=carga inicio={_hora(agora())}")
        codigo_carga, linhas_carga = rodar(
            [sys.executable, "-m", "processamento.saida", "--data", dia, "--completo"], raiz, base)
        detalhe_carga = f"código {codigo_carga}"
        for linha in linhas_carga:
            m = relatorios.RE_SAIDA.match(linha)
            if m:
                detalhe_carga = f"status {m.group(1)}"
        _marca(imprimir, f"etapa=carga fim codigo={codigo_carga} em={_hora(agora())} detalhe={detalhe_carga}")
        if codigo_carga != 0:
            _marca(imprimir, "etapa=publicador pulada motivo=a carga completa falhou")
            return _resultado(imprimir, "carga_falhou", 4)
    else:
        # 3. Rotina falhou: sem carga nova. Se já existe carga completa deste dia, o publicador não roda.
        _marca(imprimir, "etapa=carga pulada motivo=a rotina falhou")
        if (raiz / "saida_completa" / dia).is_dir():
            _marca(imprimir, f"etapa=publicador pulada motivo=saida_completa/{dia}/ já existe de uma carga "
                             "anterior: o publicador publicaria essa carga junto")
            return _resultado(imprimir, "publicador_bloqueado", 6)

    # 4. Publicador do projeto da API (argv fixo; nunca --forcar nem --criar-tabelas)
    _marca(imprimir, f"etapa=publicador inicio={_hora(agora())}")
    codigo_pub, linhas_pub = rodar(
        [api["python"], "-m", "publicador", "--data", dia], Path(api["dir_api"]),
        ambiente_publicador(base, raiz))
    resultado = resultado_publicador(linhas_pub)
    detalhe_pub = {"so_execucao": "só a execução", "completa": "publicado (completo)",
                   "recusada": "recusado"}.get(resultado or "", f"código {codigo_pub}")
    _marca(imprimir, f"etapa=publicador fim codigo={codigo_pub} em={_hora(agora())} detalhe={detalhe_pub}")

    if codigo_pub == 0:
        return _resultado(imprimir, "completa" if resultado == "completa" else "so_execucao", 0)
    if codigo_pub == 1:
        return _resultado(imprimir, "recusada", 1)
    return _resultado(imprimir, "erro_publicador", 5)


def _rodar_real(argv: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, list[str]]:
    """Roda o comando (argv fixo, sem shell), repete cada linha na tela e guarda as últimas 500."""
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    guardadas: deque[str] = deque(maxlen=500)
    for linha in proc.stdout:
        linha = linha.rstrip("\r\n")
        print(linha, flush=True)
        guardadas.append(linha)
    codigo = proc.wait()
    return codigo, list(guardadas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rodar o dia completo (rotina, carga e publicador).")
    parser.add_argument("--data", required=True, type=date.fromisoformat, help="data do pregão, AAAA-MM-DD")
    parser.add_argument("--esperar", action="store_true",
                        help="a rotina espera a coleta nos prazos dela (agendador); sem isso, --sem-esperar")
    args = parser.parse_args(argv)
    raiz = leitores.RAIZ_PADRAO
    params = leitores.ler_parametros_painel(raiz)
    return executar_dia(args.data, raiz, params, rodar=_rodar_real, esperar=args.esperar)


if __name__ == "__main__":
    sys.exit(main())
