"""Orquestração da saída: `python -m processamento.saida --data AAAA-MM-DD` (plano da etapa 7, Fase 8; seção 11).

`gerar(D)` lê a coleta pelos cortes de D (`saida/insumos.py`), calcula as grades de t e monta cada pacote na
ordem da seção 2.5: montar -> validar e gravar (`contrato.gravar_lote`) -> atualizar o estado (só os "quando muda").
Erro num pacote vira aviso e a rodada segue (`parcial`). Nenhuma regra de conteúdo mora aqui: cada pacote está
no seu módulo. Este módulo não faz SQL; a leitura é a de `insumos.py` (ou o leitor de teste injetado).
"""

from __future__ import annotations

import argparse
import functools
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from processamento import calendario, fontes
from processamento.experimento import dataset as exp_dataset
from processamento.experimento import modelos, treino
from processamento.experimento.dataset import DadosExperimento, montar_dataset
from processamento.experimento.parametros import carregar_parametros_experimento, carregar_parametros_treino
from processamento.fatos.fundamentos import carregar_parametros_fundamentos
from processamento.fatos.multiplos import multiplos_diarios
from processamento.fatos.precos import carregar_parametros_precos, mapas_cadastro
from processamento.saida import contrato, pacote_noticias, pacote_series, pacotes_experimento, pacotes_fatos
from processamento.saida.insumos import ErroSaida, ler_insumos
from processamento.saida.parametros import carregar_parametros_saida
from processamento.universo import aviso_composicao, montar_universo

ORDEM = ("acoes", "series_diarias", "mercado_dia", "resumo_acao", "fundamentos_trimestrais", "proventos",
         "noticias_dia", "experimento_historico", "experimento_top")   # seção 2.5
COMPACTOS = ("series_diarias", "proventos")                              # seção 2.3 (S20)
COLETA_NAO_CONSULTADA = {"consultado": False, "nota": "gatilho da coleta não consultado (etapa 8)"}
AVISO_SEM_MODELO = "sem arquivo de modelo em {pasta}: experimento_top não gerado"
AVISO_NAO_HOUVE = "pregão previsto {dia} não houve; dia descartado"


def _data_argumento(texto: str) -> date:
    """Data em AAAA-MM-DD para o argparse."""
    try:
        return date.fromisoformat(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"data inválida (use AAAA-MM-DD): {texto}") from e


def _rodada_anterior(pasta: Path) -> int:
    """Rodada do `execucao.json` que já está na pasta (0 se não há)."""
    arquivo = pasta / "execucao.json"
    if not arquivo.is_file():
        return 0
    return int(json.loads(arquivo.read_text(encoding="utf-8"))["registros"][0]["rodada"])


def _execucao(d: date, rodada: int, inicio: str, fim: str | None, status: str, gerado_em: str, dados_ate: str,
              coleta_status: dict, enviados: list[dict], avisos: list[str]) -> dict:
    """Registro do pacote `execucao` (4.10)."""
    return {
        **contrato.meta(gerado_em, dados_ate), "data_referencia": d.isoformat(), "rodada": rodada,
        "inicio": inicio, "fim": fim, "status": status, "coleta_status": coleta_status,
        "pacotes_enviados": enviados, "avisos": avisos,
    }


def _gravar_execucao(pasta: Path, registro: dict) -> None:
    """Grava `execucao.json` (atômico, pelo contrato)."""
    contrato.gravar_lote(pasta, contrato.lote("execucao", [registro], registro["gerado_em"], registro["dados_ate"]))


def gerar(d: date, *, ler=None, pasta_saida: Path | None = None, pasta_modelos: Path | None = None,
          pasta_registros: Path | None = None, pasta_estado: Path | None = None, usar_estado: bool = False,
          agora: datetime | None = None, coleta_status: dict | None = None, avisos_coleta: list[str] = (),
          existe_composicao: bool | None = None, params_treino=None, params_saida=None) -> Path:
    """Gera os pacotes da saída de D e devolve a pasta (`pasta_saida`, que é a pasta de D).

    `ler`: leitor injetado (testes e etapa 8); sem ele usa a conexão somente leitura da coleta.
    `usar_estado`: lê e grava o estado do "quando muda" (sem ele, manda tudo). Ponto de vista: t vem de `ler_insumos`.
    Levanta `ErroSaida` (depois de gravar `execucao.json` com status `falhou`) se não há pregão antes de D.
    """
    params_saida = carregar_parametros_saida() if params_saida is None else params_saida
    params_treino = carregar_parametros_treino() if params_treino is None else params_treino
    pasta = Path(pasta_saida) if pasta_saida is not None else params_saida.pasta / d.isoformat()
    pasta_modelos = Path(pasta_modelos) if pasta_modelos is not None else treino.PASTA_MODELOS_PADRAO
    pasta_registros = Path(pasta_registros) if pasta_registros is not None else params_saida.pasta_registros
    estado_dir = None
    if usar_estado:
        estado_dir = Path(pasta_estado) if pasta_estado is not None else params_saida.pasta_estado
    if ler is None:
        ler = exp_dataset._leitor_padrao()
    agora = datetime.now(contrato.SP) if agora is None else agora
    gerado_em = contrato.data_hora_txt(agora)
    dados_ate = contrato.data_hora_txt(calendario.corte_manha(d))
    coleta = COLETA_NAO_CONSULTADA if coleta_status is None else coleta_status
    rodada = _rodada_anterior(pasta) + 1
    avisos: list[str] = []

    # 1) execução em andamento (a rodada é a do execucao.json que já existe, + 1)
    _gravar_execucao(pasta, _execucao(d, rodada, gerado_em, None, "em_andamento", gerado_em, dados_ate,
                                      coleta, [], []))

    # 2) insumos cortados por D
    try:
        ins = ler_insumos(d, ler, existe_composicao=existe_composicao)
    except Exception as erro:
        # Fora o ErroSaida, não mostra a mensagem original (pode conter host ou usuário do banco).
        motivo = str(erro) if isinstance(erro, ErroSaida) else f"falha ao ler a coleta ({type(erro).__name__})"
        _gravar_execucao(pasta, _execucao(d, rodada, gerado_em, contrato.data_hora_txt(datetime.now(contrato.SP)),
                                          "falhou", gerado_em, dados_ate, coleta, [], [motivo]))
        if isinstance(erro, ErroSaida):
            raise
        raise ErroSaida(motivo) from erro

    aviso = aviso_composicao(ins.cal, ins.composicao)
    if aviso is not None:
        avisos.append(aviso)

    params_precos = carregar_parametros_precos()
    params_fund = carregar_parametros_fundamentos()
    params_exp = carregar_parametros_experimento()

    # Cálculos compartilhados entre pacotes: calculados no primeiro uso; se falham, o pacote que usa vira aviso.
    @functools.cache
    def grades():
        return pacotes_fatos.calcular_grades(ins, params_precos, params_fund)

    @functools.cache
    def universo():
        return montar_universo(ins.cal, ins.cadastro, ins.precos, ins.exclusoes, ins.composicao)

    @functools.cache
    def multiplos():
        return multiplos_diarios(pacotes_fatos.dados_fundamentos(ins), ins.cal, ins.exclusoes, params_fund,
                                 desde=pacote_series.inicio_janela(ins.cal, ins.t))

    @functools.cache
    def janela():
        return pacote_noticias.janela_do_dia(ins, params_exp)

    @functools.cache
    def dataset():
        dados = DadosExperimento(
            precos=ins.precos, cadastro=ins.cadastro, noticias=ins.noticias, balancos=ins.balancos,
            universo=universo(), mudancas=ins.mudancas,
        )
        df, _info = montar_dataset(dados, ins.cal, versao_noticias="todas", proximo_ao_vivo=d,
                                   params=params_exp, params_precos=params_precos)
        return df

    def estado_de(nome: str):
        return contrato.ler_estado(estado_dir, nome)

    def quando_muda(nome: str, atuais: list[dict]):
        enviar, removidos = contrato.comparar_registros(atuais, estado_de(nome), contrato.CHAVES[nome])
        return enviar, removidos, atuais

    # Cada produtor devolve (registros, removidos, novo_estado) ou None (pacote pulado, com aviso já dado).
    def acoes():
        u = universo()
        do_dia = u[pd.to_datetime(u["data"]).dt.date == ins.t]
        return quando_muda("acoes", pacotes_fatos.montar_acoes(ins, do_dia, gerado_em, dados_ate))

    def series():
        return pacote_series.montar_series_diarias(ins, multiplos(), estado_de("series_diarias"), gerado_em, dados_ate)

    def mercado():
        return pacotes_fatos.montar_mercado_dia(ins, grades(), gerado_em, dados_ate), [], None

    def resumo():
        return pacotes_fatos.montar_resumo_acao(ins, grades(), params_fund, gerado_em, dados_ate), [], None

    def fundamentos():
        return quando_muda("fundamentos_trimestrais",
                           pacotes_fatos.montar_fundamentos_trimestrais(ins, params_fund, gerado_em, dados_ate))

    def proventos():
        return quando_muda("proventos", pacotes_fatos.montar_proventos(ins, params_fund, gerado_em, dados_ate))

    def noticias():
        return pacote_noticias.montar_noticias_dia(ins, janela(), gerado_em, dados_ate), [], None

    def historico():
        fim = params_treino.teste_final_fim
        if fim is not None:
            registro_t = pacotes_experimento.ler_registro_top(pasta_registros, ins.t)
            if pacotes_experimento.pode_fechar(registro_t, fim):
                resultado = pacotes_experimento.fechar_dia(registro_t, ins.precos, ins.cal, agora)
                if resultado is None:
                    avisos.append(AVISO_NAO_HOUVE.format(dia=ins.t.isoformat()))
                else:
                    pacotes_experimento.gravar_resultado(pasta_registros, resultado)
        resultados = pacotes_experimento.ler_resultados(pasta_registros)
        u = universo()
        universo_t = str(u.loc[pd.to_datetime(u["data"]).dt.date == ins.t, "universo"].iloc[0])
        pacote = pacotes_experimento.montar_historico(
            resultados, d, fim, universo_t, params_treino, agora, dados_ate
        )
        return [pacote], [], None

    def top():
        fim = params_treino.teste_final_fim
        existente = pacotes_experimento.registro_existente(pasta_registros, d, fim)
        if existente is not None:
            avisos.extend(existente["avisos"])
            return [existente], [], None
        caminho, caminho_m1, avisos_modelo = pacotes_experimento.escolher_modelo(pasta_modelos, d)
        if caminho is None:
            avisos.append(AVISO_SEM_MODELO.format(pasta=pasta_modelos))
            return None
        modelo, meta = modelos.carregar_modelo(caminho)
        modelo_m1, meta_m1 = modelos.carregar_modelo(caminho_m1) if caminho_m1 is not None else (None, None)
        cnpj_de = mapas_cadastro(ins.cadastro)[1]
        pacote, interno = pacotes_experimento.gerar_top(
            dataset(), ins.t, d, modelo, meta, modelo_m1, meta_m1, janela(), cnpj_de, params_treino, params_saida,
            agora, dados_ate, caminho.stem, avisos_modelo,
        )
        pacote, _gravou = pacotes_experimento.gravar_registro_top(pasta_registros, pacote, interno, fim)
        avisos.extend(pacote["avisos"])
        return [pacote], [], None

    produtores = {
        "acoes": acoes, "series_diarias": series, "mercado_dia": mercado, "resumo_acao": resumo,
        "fundamentos_trimestrais": fundamentos, "proventos": proventos, "noticias_dia": noticias,
        "experimento_historico": historico, "experimento_top": top,
    }

    # 4) cada pacote: montar -> validar e gravar -> estado. Erro num pacote vira aviso e a rodada segue.
    enviados: list[dict] = []
    incompleta = False
    for nome in ORDEM:
        try:
            produzido = produtores[nome]()
            if produzido is None:
                incompleta = True
                continue
            registros, removidos, novo_estado = produzido
            arquivo = contrato.gravar_lote(
                pasta, contrato.lote(nome, registros, gerado_em, dados_ate, removidos), compacto=nome in COMPACTOS
            )
            if novo_estado is not None:
                contrato.gravar_estado(estado_dir, nome, novo_estado)
            enviados.append({"pacote": nome, "arquivo": arquivo.name,
                             "registros": len(registros), "removidos": len(removidos)})
        except Exception as erro:
            avisos.append(f"falha ao gerar {nome}: {type(erro).__name__}: {erro}")
            incompleta = True

    # 5) execução final: ok = os 9 pacotes; parcial = algum falhou ou foi pulado; falhou = nenhum gravado
    if not enviados:
        status = "falhou"
    elif incompleta:
        status = "parcial"
    else:
        status = "ok"
    fim = contrato.data_hora_txt(datetime.now(contrato.SP))
    _gravar_execucao(pasta, _execucao(d, rodada, gerado_em, fim, status, gerado_em, dados_ate, coleta,
                                      enviados, avisos + list(avisos_coleta)))
    return pasta


def main(argv=None, ler=None, existe_composicao: bool | None = None) -> int:
    """Ponto de entrada (`python -m processamento.saida`). Devolve 0 se `ok` ou `parcial`, 2 se a configuração
    do banco estiver incompleta, 3 se a sessão não estiver em somente leitura ou a conexão falhar (nada é
    gravado) e 4 se `falhou` (nenhum pacote gravado ou não há pregão antes de D).
    """
    parser = argparse.ArgumentParser(
        prog="python -m processamento.saida",
        description="Gera os pacotes JSON da saída do dia D. Só lê o banco da coleta.",
    )
    parser.add_argument("--data", type=_data_argumento, required=True, help="D: pregão previsto (AAAA-MM-DD)")
    parser.add_argument("--pasta", type=Path, default=None,
                        help="pasta raiz da saída (padrão: parametros.yaml); os pacotes vão para PASTA/AAAA-MM-DD")
    parser.add_argument("--pasta-modelos", type=Path, default=None, help="pasta dos modelos (padrão: modelos)")
    parser.add_argument("--pasta-registros", type=Path, default=None,
                        help="pasta dos registros do experimento (padrão: parametros.yaml)")
    parser.add_argument("--sem-estado", action="store_true",
                        help="não lê nem grava o estado do envio (manda tudo)")
    args = parser.parse_args(argv)
    d = args.data

    if ler is None:
        try:
            ler = exp_dataset._leitor_padrao()
        except fontes.ErroConfiguracao as e:
            print(f"Configuração do banco incompleta: {e}")
            return 2
        except fontes.ErroSomenteLeitura as e:
            print(f"{e}. Nada foi gravado.")
            return 3
        except Exception as e:
            # Não mostra a mensagem original: ela pode conter host ou usuário.
            print(f"Falha ao conectar ao banco ({type(e).__name__}). Nada foi gravado.")
            return 3

    pasta_d = None if args.pasta is None else args.pasta / d.isoformat()
    try:
        pasta = gerar(
            d, ler=ler, pasta_saida=pasta_d, pasta_modelos=args.pasta_modelos,
            pasta_registros=args.pasta_registros, usar_estado=not args.sem_estado,
            existe_composicao=existe_composicao,
        )
    except ErroSaida as e:
        print(f"Saída não gerada: {e}")
        return 4

    execucao = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))["registros"][0]
    print(f"Saída de {d.isoformat()} em {pasta}: status {execucao['status']}")
    for aviso in execucao["avisos"]:
        print(f"- {aviso}")
    return 4 if execucao["status"] == "falhou" else 0
