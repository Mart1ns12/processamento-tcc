"""Pacotes do experimento: top 5 do dia, registro, fechamento e histórico (plano da etapa 7, fase 7; seção 8).

Funções sem banco nem rede: as pastas chegam por parâmetro (`ParametrosSaida`). Teste final trancado: com
`treino.teste_final.fim` vazio nenhum dia é fechado e o histórico sai vazio (n_dias = 0, dia = null).
Probabilidades, contribuições e sombras ficam só no registro interno; o pacote traz a chance sem valor
enquanto a calibração não foi conferida (F16).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time
from pathlib import Path

import numpy as np
import pandas as pd

from processamento.experimento import avaliacao, modelos, preparacao, previsao, relatorio
from processamento.experimento.alvo import alvos
from processamento.experimento.parametros import ParametrosTreino
from processamento.fatos import noticias as fatos_noticias
from processamento.saida import contrato, textos
from processamento.saida.parametros import ParametrosSaida

AVISOS = {
    "provisorio": "Modelo provisório: treinado com cerca de 1 ano de dados, só para testar a rotina.",
    "antes_producao": (
        "Antes da entrada em produção: este top 5 é um teste de funcionamento e não entra no histórico do experimento."
    ),
    "teste_final": "Dia do período de teste final: não entra no histórico do experimento.",
    "depois_10h": "Gerado depois das 10h: não entra no histórico do experimento.",
    "modelo_mes": "Modelo de {mes} (o do mês de D ainda não foi treinado).",
    "poucas_acoes": "Só {n} ações no universo do dia (menos de {k}).",
}
TITULO = "5 ações com maior chance de superar o Ibovespa (experimento)"
SELO = "em_avaliacao"
AVISO_FIXO = relatorio.RODAPE
NOTA_UNIVERSO = {
    "composicao_atual": "Histórico calculado com as ações que compõem o Ibovespa atualmente.",
    "composicao_historica": "Histórico calculado com as ações que compunham o Ibovespa em cada data.",
}
NOTA_SEM_DIAS = (
    "O histórico começa na entrada em produção (teste ao vivo). "
    "Antes disso, os top 5 são testes de funcionamento e não entram aqui."
)
_RE_MODELO_ARQUIVO = re.compile(r"^xgb-(\d{4}-\d{2})\.json$")


def _texto_json(objeto: dict) -> str:
    """JSON do projeto: UTF-8 legível, sem NaN nem Infinity."""
    return json.dumps(objeto, ensure_ascii=False, allow_nan=False, indent=2)


def _numero_ou_none(x) -> float | None:
    """Número como float; ausente (None ou NaN) vira None."""
    if x is None or pd.isna(x):
        return None
    return float(x)


def _folha_retorno(x: float | None) -> dict:
    """Folha de retorno: `ok` com o número, ou `indisponivel` sem preço."""
    if x is None:
        return contrato.folha(None, "indisponivel")
    return contrato.folha(x, "ok")


def _mes(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _chance_saida(chance: dict) -> dict:
    """Chance do `previsao` no contrato 1.0: `media` vira `referencia_acaso`, só quando a chance aparece."""
    return {
        "valor": chance["valor"],
        "referencia_acaso": chance["media"] if chance["exibir"] else None,
        "exibir": chance["exibir"],
        "status": chance["status"],
    }


# ---------------------------------------------------------------- modelo e validade

def escolher_modelo(pasta_modelos: Path, d: date) -> tuple[Path | None, Path | None, list[str]]:
    """Modelo 3 e modelo 1 do dia D.

    Usa `xgb-AAAA-MM` do mês de D; se não existir, o mais recente anterior a esse mês (com aviso).
    O modelo 1 é `xgb-m1-<mês do modelo 3>` se existir. Sem modelo nenhum: (None, None, []).
    """
    pasta = Path(pasta_modelos)
    mes_d = _mes(d)
    avisos: list[str] = []
    if (pasta / f"{modelos.nome_modelo(mes_d)}.json").is_file():
        escolhido = mes_d
    else:
        anteriores = []
        if pasta.is_dir():
            for arquivo in pasta.iterdir():
                casou = _RE_MODELO_ARQUIVO.match(arquivo.name)
                if casou and casou.group(1) < mes_d:
                    anteriores.append(casou.group(1))
        if not anteriores:
            return None, None, []
        escolhido = max(anteriores)
        avisos.append(AVISOS["modelo_mes"].format(mes=escolhido))
    modelo_3 = pasta / f"{modelos.nome_modelo(escolhido)}.json"
    modelo_1 = pasta / f"{modelos.nome_modelo(escolhido, '1')}.json"
    return modelo_3, (modelo_1 if modelo_1.is_file() else None), avisos


def valido_para_historico(
    meta: dict, gerado_em: datetime, d: date, fim: date | None, limite: time
) -> tuple[bool, list[str]]:
    """S10: o top de D entra no histórico só sem razão nenhuma.

    Razões (chaves de `AVISOS`): "provisorio"; "depois_10h" (gerado depois de `limite` em D, inclusive
    o próprio limite, no fuso de São Paulo); "antes_producao" (`fim` vazio); "teste_final" (D <= `fim`).
    """
    razoes: list[str] = []
    if meta["provisorio"]:
        razoes.append("provisorio")
    gerado = gerado_em if gerado_em.tzinfo is not None else gerado_em.replace(tzinfo=contrato.SP)
    if gerado > datetime.combine(d, limite, tzinfo=contrato.SP):
        razoes.append("depois_10h")
    if fim is None:
        razoes.append("antes_producao")
    elif d <= fim:
        razoes.append("teste_final")
    return (not razoes), razoes


# ---------------------------------------------------------------- top 5 do dia

def gerar_top(
    dataset_df: pd.DataFrame,
    t: date,
    d: date,
    modelo,
    meta: dict,
    modelo_m1,
    meta_m1: dict | None,
    janela: pd.DataFrame,
    cnpj_de: dict,
    params_treino: ParametrosTreino,
    params_saida: ParametrosSaida,
    gerado_em: datetime,
    dados_ate: str,
    nome_modelo: str,
    avisos_modelo: list[str],
) -> tuple[dict, dict]:
    """(pacote, interno) do `experimento_top` de D, com base no pregão t (último antes de D).

    Copia o padrão de `treino._exemplo_top`: ranks sobre o dataset inteiro, depois o recorte das linhas de t.
    Sem linhas de t no dataset levanta ValueError (a rodada fica parcial, decidido pelo chamador).
    """
    completo = preparacao.preparar(dataset_df)
    mascara = (pd.to_datetime(dataset_df["data"]) == pd.Timestamp(t)).to_numpy()
    preparado_dia = completo.loc[mascara]
    bruto_dia = dataset_df.loc[mascara]
    if bruto_dia.empty:
        raise ValueError(f"sem linhas de {t.isoformat()} no dataset: não há top 5 para {d.isoformat()}")

    k = params_treino.topk[0]
    n = len(bruto_dia)
    valido, razoes = valido_para_historico(
        meta, gerado_em, d, params_treino.teste_final_fim, params_saida.limite_valido_historico
    )
    avisos = [AVISOS[razao] for razao in razoes] + list(avisos_modelo)
    if n < k:
        avisos.append(AVISOS["poucas_acoes"].format(n=n, k=k))

    ranking = []
    for item in previsao.top_do_dia(preparado_dia, bruto_dia, modelo, meta, params_treino):
        ticker = item["ticker"]
        linha_prep = preparado_dia.loc[preparado_dia["ticker"] == ticker].iloc[0]
        linha_bruta = bruto_dia.loc[bruto_dia["ticker"] == ticker].iloc[0]
        qtd = _numero_ou_none(linha_bruta["noticias_dia_qtd"])
        motivos = []
        for motivo in item["motivos"]:
            fator = motivo["fator"]
            rank = _numero_ou_none(linha_prep[fator]) if fator in linha_prep.index else None
            motivos.append({
                "fator": fator,
                "valor": motivo["valor"],
                "efeito": motivo["efeito"],
                "texto": textos.texto_motivo(fator, motivo["valor"], rank, qtd, params_saida.tom_neutro),
            })
        ranking.append({
            "posicao": item["posicao"],
            "ticker": ticker,
            "chance": _chance_saida(item["chance"]),
            "motivos": motivos,
            "noticias_usadas": fatos_noticias.ids_da_empresa(janela, cnpj_de.get(ticker) or ticker),
        })

    pacote = {
        **contrato.meta(contrato.data_hora_txt(gerado_em), dados_ate),
        "data_referencia": d.isoformat(),
        "pregao_previsto": d.isoformat(),
        "pregao_base": t.isoformat(),
        "valido_para_historico": valido,
        "modelo_versao": nome_modelo,
        "modelo_provisorio": bool(meta["provisorio"]),
        "universo": str(bruto_dia["universo"].iloc[0]),
        "n_candidatas": n,
        "selo": SELO,
        "titulo": TITULO,
        "aviso_fixo": AVISO_FIXO,
        "avisos": avisos,
        "ranking": ranking,
    }

    mes_modelo = nome_modelo.removeprefix("xgb-")
    probabilidades = modelos.prob_xgb(modelo, preparado_dia[meta["colunas"]])
    tem_m1 = modelo_m1 is not None
    interno = {
        "modelo_arquivo": f"{nome_modelo}.json",
        "modelo_m1_arquivo": f"{modelos.nome_modelo(mes_modelo, '1')}.json" if tem_m1 else None,
        "sombra_modelo_1": (
            previsao.top_sombra_modelo(preparado_dia, modelo_m1, meta_m1["colunas"], k) if tem_m1 else None
        ),
        "sombra_volatilidade": previsao.top_sombra_volatilidade(preparado_dia, k),
        "candidatos": bruto_dia["ticker"].tolist(),
        "probabilidades": {
            ticker: float(p) for ticker, p in zip(preparado_dia["ticker"].tolist(), probabilidades)
        },
    }
    return pacote, interno


# ---------------------------------------------------------------- registro do top (S11)

def _caminho_top(pasta: Path, d: date) -> Path:
    return Path(pasta) / f"{d.isoformat()}.top.json"


def ler_registro_top(pasta: Path, d: date) -> dict | None:
    """Conteúdo de `<D>.top.json` (`{"pacote", "interno"}`), ou None se não existe."""
    caminho = _caminho_top(pasta, d)
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def registro_existente(pasta: Path, d: date, fim: date | None) -> dict | None:
    """S11: com `fim` preenchido devolve o pacote já gravado de D; com `fim` vazio devolve sempre None."""
    if fim is None:
        return None
    registro = ler_registro_top(pasta, d)
    return None if registro is None else registro["pacote"]


def gravar_registro_top(pasta: Path, pacote: dict, interno: dict, fim: date | None) -> tuple[dict, bool]:
    """Grava `<D>.top.json`. Devolve (pacote gravado, gravou?).

    Com `fim` preenchido é de uso único: se o arquivo já existe, nada muda e devolve o pacote que está
    nele, com False. Com `fim` vazio (testes de funcionamento) sobrescreve, de forma atômica.
    """
    d = date.fromisoformat(pacote["data_referencia"])
    texto = _texto_json({"pacote": pacote, "interno": interno})
    if fim is None:
        contrato._gravar_atomico(_caminho_top(pasta, d), texto)
        return pacote, True
    caminho = _caminho_top(pasta, d)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        with caminho.open("x", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(texto)
    except FileExistsError:
        return ler_registro_top(pasta, d)["pacote"], False
    return pacote, True


# ---------------------------------------------------------------- fechamento de um dia

def pode_fechar(registro_top: dict | None, fim: date | None) -> bool:
    """Um dia só fecha com `fim` preenchido, registro válido e pregão previsto depois de `fim`."""
    if registro_top is None or fim is None:
        return False
    pacote = registro_top["pacote"]
    if not pacote["valido_para_historico"]:
        return False
    return date.fromisoformat(pacote["pregao_previsto"]) > fim


def fechar_dia(registro_top: dict, precos: pd.DataFrame, cal: list[date], agora: datetime) -> dict | None:
    """Resultado do top 5 de D' (seção 8). Devolve None se o dia não entra.

    Não confere `fim` (isso é de `pode_fechar`, que o chamador usa antes). Só fecha se o registro é válido,
    D' está no calendário e o pregão base é o imediatamente anterior a D' (senão D' não foi pregão).
    Retorno = `alvos(precos, [base, D'])` na linha do pregão base (IBOV incluído).
    """
    pacote = registro_top["pacote"]
    candidatos = list(registro_top["interno"]["candidatos"])
    if not pacote["valido_para_historico"]:
        return None
    dia = date.fromisoformat(pacote["pregao_previsto"])
    base = date.fromisoformat(pacote["pregao_base"])
    cal = list(cal)
    if dia not in cal:
        return None
    pos = cal.index(dia)
    if pos == 0 or cal[pos - 1] != base:
        return None

    grades = alvos(precos, [base, dia], candidatos)
    linha = pd.Timestamp(base)
    ret_ibov = _numero_ou_none(grades["ret_ibov_t1"].loc[linha].iloc[0])
    ranking = [item["ticker"] for item in pacote["ranking"]]

    resultado = []
    for ticker in ranking:
        ret = _numero_ou_none(grades["ret_t1"].loc[linha, ticker])
        superou = None if ret is None or ret_ibov is None else ret > ret_ibov
        resultado.append({
            "ticker": ticker,
            "retorno": _folha_retorno(ret),
            "retorno_ibov": _folha_retorno(ret_ibov),
            "superou": superou,
        })

    alvos_candidatos = {t: _numero_ou_none(grades["alvo"].loc[linha, t]) for t in candidatos}

    def acertos_de(tickers: list[str] | None) -> int | None:
        if tickers is None:
            return None
        return sum(1 for t in tickers if alvos_candidatos.get(t) == 1.0)

    interno = registro_top["interno"]
    return {
        "data_referencia": dia.isoformat(),
        "pregao_base": base.isoformat(),
        "valido_para_historico": True,
        "fechado_em": contrato.data_hora_txt(agora),
        "ranking": ranking,
        "resultado": resultado,
        "acertos_dia": sum(1 for item in resultado if item["superou"] is True),
        "acertos_top3": sum(1 for item in resultado[:3] if item["superou"] is True),
        "resultado_incompleto": any(item["superou"] is None for item in resultado),
        "alvos_candidatos": alvos_candidatos,
        "acertos_sombra_modelo_1": acertos_de(interno["sombra_modelo_1"]),
        "acertos_sombra_volatilidade": acertos_de(interno["sombra_volatilidade"]),
    }


def gravar_resultado(pasta: Path, resultado: dict) -> bool:
    """Grava `<D'>.resultado.json` de uso único (nunca sobrescreve). True se gravou."""
    caminho = Path(pasta) / f"{resultado['data_referencia']}.resultado.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        with caminho.open("x", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(_texto_json(resultado))
    except FileExistsError:
        return False
    return True


def ler_resultados(pasta: Path) -> list[dict]:
    """Todos os `*.resultado.json` da pasta, em ordem de data (vazio se a pasta não existe)."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return [json.loads(c.read_text(encoding="utf-8")) for c in sorted(pasta.glob("*.resultado.json"))]


# ---------------------------------------------------------------- histórico (4.9)

def montar_historico(
    resultados: list[dict],
    d: date,
    fim: date | None,
    universo: str,
    params_treino: ParametrosTreino,
    gerado_em: datetime,
    dados_ate: str,
) -> dict:
    """`experimento_historico` de D (4.9). Entram só dias válidos com pregão previsto depois de `fim`.

    Com `fim` vazio nenhum dia entra. `dia` é o dia fechado mais recente; `data_referencia` é esse dia
    ou D se nenhum. Faixa do acaso sobre as candidatas (com alvo) de todos os dias que entram.
    """
    k = params_treino.topk[0]
    elegiveis = sorted(
        (
            r for r in resultados
            if fim is not None and r["valido_para_historico"] and date.fromisoformat(r["data_referencia"]) > fim
        ),
        key=lambda r: r["data_referencia"],
    )
    n = len(elegiveis)

    dia = None
    taxa_acerto = contrato.folha(None, "indisponivel")
    acaso_media = contrato.folha(None, "indisponivel")
    acaso_faixa = None
    if n:
        total = sum(r["acertos_dia"] for r in elegiveis)
        taxa = total / (k * n)
        ultimo = elegiveis[-1]
        dia = {
            "data_referencia": ultimo["data_referencia"],
            "pregao_base": ultimo["pregao_base"],
            "ranking": ultimo["ranking"],
            "resultado": ultimo["resultado"],
            "acertos_dia": ultimo["acertos_dia"],
            "acertos_top3": ultimo["acertos_top3"],
            "resultado_incompleto": ultimo["resultado_incompleto"],
            "taxa_acumulada": contrato.folha(taxa, "ok"),
        }
        taxa_acerto = contrato.folha(taxa, "ok")
        linhas = [
            (r["data_referencia"], ticker, _numero_ou_nan(alvo))
            for r in elegiveis
            for ticker, alvo in r["alvos_candidatos"].items()
        ]
        faixa = avaliacao.faixa_do_acaso(
            pd.DataFrame(linhas, columns=["data", "ticker", "alvo"]),
            k,
            params_treino.acaso_sorteios,
            params_treino.semente,
            com_retorno=False,
        )
        if faixa["media"] is not None:
            acaso_media = contrato.folha(faixa["media"], "ok")
            acaso_faixa = [faixa["p2_5"], faixa["p97_5"]]

    frases = []
    if universo in NOTA_UNIVERSO:
        frases.append(NOTA_UNIVERSO[universo])
    if n == 0:
        frases.append(NOTA_SEM_DIAS)

    resumo = {
        "periodo_inicio": elegiveis[0]["data_referencia"] if n else None,
        "periodo_fim": elegiveis[-1]["data_referencia"] if n else None,
        "n_dias": n,
        "taxa_acerto": taxa_acerto,
        "acaso_media": acaso_media,
        "acaso_faixa": acaso_faixa,
        "universo": universo,
        "nota": " ".join(frases),
    }
    return {
        **contrato.meta(contrato.data_hora_txt(gerado_em), dados_ate),
        "data_referencia": elegiveis[-1]["data_referencia"] if n else d.isoformat(),
        "dia": dia,
        "resumo": resumo,
    }


def _numero_ou_nan(x) -> float:
    """Alvo para a faixa do acaso: None vira NaN (a faixa ignora as linhas sem alvo)."""
    return np.nan if x is None else float(x)
