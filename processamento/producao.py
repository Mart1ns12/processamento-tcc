"""Entrada em produção (plano da etapa 8, seção 10; fase 9).

    python -m processamento.producao --inicio AAAA-MM-DD [--confirmar]

Sem `--confirmar`: só confere e imprime os problemas e os passos. Não grava nada.
Com `--confirmar` e sem problemas: move os `*.top.json` dos testes de funcionamento para
`registros/experimento/funcionamento-<hoje>/` (não apaga) e grava `docs/producao.json` de uso único.
Com problemas, não move nada e sai com código 1. Nunca edita o `parametros.yaml`, nunca lê o banco
e nunca roda o treino. Hoje e agora chegam por parâmetro; só o `main` (ponto de entrada) usa o relógio.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path

from processamento import calendario, fontes
from processamento.experimento import modelos, treino
from processamento.experimento.parametros import ParametrosTreino, carregar_parametros_treino
from processamento.saida import contrato, pacotes_experimento
from processamento.saida.parametros import carregar_parametros_saida

ARQUIVO_PRODUCAO_PADRAO = fontes.RAIZ / "docs" / "producao.json"

MSG_MODELO_PROVISORIO = (
    "modelo ainda provisório (treino.modelo_oficial: false): com o histórico curto o modelo não é treinado "
    "para valer (pegadinha 13) e nenhum dia entraria no histórico"
)
MSG_REGISTRO_USADO = "teste final já usado (docs/teste_final_usado.json)"
MSG_RESULTADO_FECHADO = "já existe resultado fechado em registros/experimento: conferir antes de entrar em produção"


class ErroProducao(Exception):
    """Entrada em produção recusada (por exemplo, `docs/producao.json` já existe)."""


def _passos(d0: date, fim: date | None) -> list[str]:
    """Os passos da seção 10 do plano, com D0 e `fim` preenchidos (`<fim>` se D0 não é pregão)."""
    d0_txt = d0.isoformat()
    fim_txt = fim.isoformat() if fim is not None else "<fim>"
    return [
        "1. Antes (já feito): histórico completo no banco; regerar os datasets e rodar o treino de "
        "desenvolvimento com treino.modelo_oficial: true.",
        f"2. Conferências (esta etapa): python -m processamento.producao --inicio {d0_txt}",
        f"3. python -m processamento.producao --inicio {d0_txt} --confirmar: move os *.top.json de teste de "
        "funcionamento para registros/experimento/funcionamento-<hoje>/ e grava docs/producao.json. "
        "Não edita o parametros.yaml.",
        f"4. Edite processamento/config/parametros.yaml: treino.teste_final.fim: \"{fim_txt}\" e "
        "liberado: true (data entre aspas).",
        f"5. Em {d0_txt} ou depois: python -m processamento.experimento.dataset --versao "
        f"<todas|principais|hora_real_noite> --ate {fim_txt} --proximo {d0_txt} (as três versões) e depois "
        "python -m processamento.experimento.treino --data <data do arquivo> --teste-final (uma única vez).",
    ]


def _dev_nao_provisorio(pasta_modelos: Path, params_treino: ParametrosTreino) -> str | None:
    """Problema se o `.meta.json` do treino de desenvolvimento não está com `provisorio: false`."""
    nome = modelos.nome_modelo(params_treino.teste_final_inicio.strftime("%Y-%m"), "3")
    caminho = Path(pasta_modelos) / f"{nome}.meta.json"
    if not caminho.is_file():
        return (f"falta {caminho.name}: rode o treino de desenvolvimento com treino.modelo_oficial: true "
                "antes de entrar em produção")
    meta = json.loads(caminho.read_text(encoding="utf-8"))
    if meta.get("provisorio") is not False:
        return (f"{caminho.name} não está com provisorio: false: rode o treino de desenvolvimento com "
                "treino.modelo_oficial: true")
    return None


def conferir_entrada(d0: date, hoje: date, params_treino: ParametrosTreino, pasta_modelos: Path,
                     pasta_registros: Path, registro_teste_final: Path) -> tuple[date | None, list[str], list[str]]:
    """Confere a entrada em produção sem gravar nada. Devolve (fim, problemas, passos).

    `fim` = pregão anterior a D0 quando D0 é pregão previsto; senão None.
    """
    problemas: list[str] = []
    fim: date | None = None
    if calendario.e_pregao_previsto(d0):
        fim = calendario.pregao_anterior_previsto(d0)
    else:
        problemas.append(f"{d0.isoformat()} não é pregão previsto")
    if d0 <= hoje:
        problemas.append(f"D0 precisa ser depois de hoje ({hoje.isoformat()})")
    if not params_treino.modelo_oficial:
        problemas.append(MSG_MODELO_PROVISORIO)
    aviso_dev = _dev_nao_provisorio(Path(pasta_modelos), params_treino)
    if aviso_dev is not None:
        problemas.append(aviso_dev)
    if params_treino.teste_final_fim is not None and params_treino.teste_final_fim != fim:
        problemas.append(f"treino.teste_final.fim já está preenchido com {params_treino.teste_final_fim.isoformat()}")
    if Path(registro_teste_final).exists():
        problemas.append(MSG_REGISTRO_USADO)
    pasta = Path(pasta_registros)
    if pasta.is_dir() and any(pasta.glob("*.resultado.json")):
        problemas.append(MSG_RESULTADO_FECHADO)
    return fim, problemas, _passos(d0, fim)


def confirmar_entrada(d0: date, fim: date | None, hoje: date, pasta_registros: Path, arquivo_producao: Path,
                      agora: datetime) -> list[str]:
    """Move os `*.top.json` para `funcionamento-<hoje>/` e grava `arquivo_producao` (uso único).

    Devolve os nomes dos arquivos movidos. Nada é movido se `arquivo_producao` já existe ou se
    algum destino já existe.
    """
    if fim is None:
        raise ErroProducao("sem fim (D0 não é pregão previsto): nada a confirmar")
    arquivo_producao = Path(arquivo_producao)
    if arquivo_producao.exists():
        raise ErroProducao(f"{arquivo_producao.name} já existe: a entrada em produção é de uso única")
    pasta = Path(pasta_registros)
    origens = [pasta / f"{d.isoformat()}.top.json" for d in pacotes_experimento.listar_registros_top(pasta)]
    destino = pasta / f"funcionamento-{hoje.isoformat()}"
    conflito = [origem.name for origem in origens if (destino / origem.name).exists()]
    if conflito:
        raise ErroProducao(f"já existe em {destino.name}: {', '.join(conflito)}")
    if origens:
        destino.mkdir(parents=True, exist_ok=True)
        for origem in origens:
            os.replace(origem, destino / origem.name)
    arquivados = [origem.name for origem in origens]
    texto = json.dumps(
        {
            "inicio": d0.isoformat(),
            "fim": fim.isoformat(),
            "confirmado_em": contrato.data_hora_txt(agora),
            "registros_arquivados": arquivados,
        },
        indent=2, ensure_ascii=False, allow_nan=False,
    )
    arquivo_producao.parent.mkdir(parents=True, exist_ok=True)
    with arquivo_producao.open("x", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return arquivados


def _data_argumento(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as erro:
        raise argparse.ArgumentTypeError(f"data inválida (use AAAA-MM-DD): {texto!r}") from erro


def _imprimir_passos(passos: list[str]) -> None:
    print("Passos (seção 10 do plano):")
    for passo in passos:
        print(f"  {passo}")


def main(argv=None, *, hoje=None, agora=None, params_treino=None, pasta_modelos=None,
         pasta_registros=None, registro_teste_final=None, arquivo_producao=None) -> int:
    """Ponto de entrada. 0 = sem problemas; 1 = problemas (nada movido nem gravado)."""
    parser = argparse.ArgumentParser(prog="python -m processamento.producao",
                                     description="Confere a entrada em produção (seção 10 do plano da etapa 8).")
    parser.add_argument("--inicio", required=True, type=_data_argumento,
                        help="D0: primeiro pregão em produção (AAAA-MM-DD)")
    parser.add_argument("--confirmar", action="store_true",
                        help="move os *.top.json de teste de funcionamento e grava docs/producao.json (uso único)")
    args = parser.parse_args(argv)

    agora = datetime.now(contrato.SP) if agora is None else agora
    hoje = agora.astimezone(contrato.SP).date() if hoje is None else hoje
    params_treino = carregar_parametros_treino() if params_treino is None else params_treino
    pasta_modelos = treino.PASTA_MODELOS_PADRAO if pasta_modelos is None else Path(pasta_modelos)
    pasta_registros = (carregar_parametros_saida().pasta_registros if pasta_registros is None
                       else Path(pasta_registros))
    registro_teste_final = treino.REGISTRO_TESTE_FINAL if registro_teste_final is None else Path(registro_teste_final)
    arquivo_producao = ARQUIVO_PRODUCAO_PADRAO if arquivo_producao is None else Path(arquivo_producao)

    d0 = args.inicio
    fim, problemas, passos = conferir_entrada(d0, hoje, params_treino, pasta_modelos, pasta_registros,
                                              registro_teste_final)
    if arquivo_producao.exists():
        problemas.append(f"{arquivo_producao.name} já existe: a entrada em produção já foi confirmada")

    if problemas:
        print(f"Entrada em produção em {d0.isoformat()} NÃO liberada. Problemas:")
        for problema in problemas:
            print(f"  - {problema}")
        print("Nada foi movido nem gravado.")
        _imprimir_passos(passos)
        return 1

    if not args.confirmar:
        print(f"Conferências OK para D0 = {d0.isoformat()} (fim = {fim.isoformat()}). Nada foi gravado.")
        _imprimir_passos(passos)
        return 0

    try:
        arquivados = confirmar_entrada(d0, fim, hoje, pasta_registros, arquivo_producao, agora)
    except ErroProducao as erro:
        print(f"Não confirmado: {erro}")
        print("Nada foi gravado.")
        return 1
    print(f"Entrada em produção confirmada: D0 = {d0.isoformat()}, fim = {fim.isoformat()}.")
    print(f"Arquivados em funcionamento-{hoje.isoformat()}: {len(arquivados)}")
    print(f"Gravado: {arquivo_producao}")
    _imprimir_passos(passos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
