"""Calendário de pregões, horários da B3 e janelas de notícias (seção 7.2 da especificação).

Pregões = datas com preço do `IBOV` em `v1-precos`. Horários da B3 e corte da noite vêm de
`config/parametros.yaml`. Nenhuma função daqui acessa banco ou rede.
"""

from __future__ import annotations

import bisect
import functools
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

SP = ZoneInfo("America/Sao_Paulo")
CAMINHO_PARAMETROS = Path(__file__).resolve().parent / "config" / "parametros.yaml"
_CHAVES_DE_TOPO = {"fuso", "corte_noite", "horarios_b3_valido_ate", "horarios_b3", "dias_especiais", "feriados_b3", "feriados_b3_valido_ate", "fase1", "fundamentos", "experimento", "treino", "saida", "rotina"}
_CHAVES_PERIODO = {"a_partir_de", "abertura", "fechamento"}
_CHAVES_ESPECIAL = {"abertura", "fechamento", "motivo"}
_RE_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ErroCalendario(Exception):
    """Calendário ou parâmetros inválidos (a mensagem diz o que corrigir)."""


def _validar_data(valor: object, onde: str) -> str:
    """Confere a data (texto AAAA-MM-DD entre aspas); levanta `ErroCalendario` se não bater."""
    if not isinstance(valor, str):
        raise ErroCalendario(
            f"{onde}: a data {valor} deve estar entre aspas no YAML (ex.: \"2026-03-09\")"
        )
    if not _RE_DATA.match(valor):
        raise ErroCalendario(f"{onde}: data inválida {valor!r} (use AAAA-MM-DD)")
    try:
        date.fromisoformat(valor)
    except ValueError as erro:
        raise ErroCalendario(f"{onde}: data inválida {valor!r} ({erro})") from erro
    return valor


def _validar_hora(valor: object, onde: str) -> str:
    """Confere a hora (texto HH:MM entre aspas); levanta `ErroCalendario` se não bater."""
    if not isinstance(valor, str):
        raise ErroCalendario(
            f"{onde}: o horário {valor} deve estar entre aspas no YAML "
            "(ex.: \"10:00\"; sem aspas o YAML lê 10:00 como número)"
        )
    if not _RE_HORA.match(valor):
        raise ErroCalendario(f"{onde}: horário inválido {valor!r} (formato HH:MM)")
    return valor


def _validar_horas(abertura_txt: str | None, fechamento_txt: str | None, corte: str, onde: str) -> None:
    """Abertura depois do corte da noite e antes do fechamento (quando os dois existem)."""
    if abertura_txt is not None:
        if time.fromisoformat(abertura_txt) <= time.fromisoformat(corte):
            raise ErroCalendario(f"{onde}: a abertura {abertura_txt} deve ser depois do corte da noite ({corte})")
    if abertura_txt is not None and fechamento_txt is not None:
        if time.fromisoformat(abertura_txt) >= time.fromisoformat(fechamento_txt):
            raise ErroCalendario(
                f"{onde}: a abertura {abertura_txt} deve ser antes do fechamento {fechamento_txt}"
            )


def _validar_periodos(periodos: object, corte: str) -> None:
    """Valida a lista `horarios_b3`: formato, horas e `a_partir_de` crescente."""
    if not isinstance(periodos, list) or not periodos:
        raise ErroCalendario("horarios_b3 deve ser uma lista não vazia")
    anterior = None
    for i, periodo in enumerate(periodos, start=1):
        onde = f"horarios_b3[{i}]"
        if not isinstance(periodo, dict) or set(periodo) != _CHAVES_PERIODO:
            raise ErroCalendario(f"{onde} deve ter exatamente as chaves a_partir_de, abertura e fechamento")
        inicio = _validar_data(periodo["a_partir_de"], f"{onde}.a_partir_de")
        ab = _validar_hora(periodo["abertura"], f"{onde}.abertura")
        fe = _validar_hora(periodo["fechamento"], f"{onde}.fechamento")
        _validar_horas(ab, fe, corte, onde)
        if anterior is not None and inicio <= anterior:
            raise ErroCalendario(f"{onde}: a_partir_de {inicio} deve ser maior que {anterior} (ordem crescente)")
        anterior = inicio


def _validar_dias_especiais(especiais: object, corte: str) -> None:
    """Valida `dias_especiais`: cada dia traz abertura e/ou fechamento, e horas válidas."""
    if not isinstance(especiais, dict):
        raise ErroCalendario("dias_especiais deve ser um mapeamento (data: {abertura, fechamento, motivo})")
    for data, info in especiais.items():
        onde = f"dias_especiais[{data}]"
        _validar_data(data, "dias_especiais")
        if not isinstance(info, dict) or not info:
            raise ErroCalendario(f"{onde} deve ser um mapeamento com abertura e/ou fechamento")
        extras = set(info) - _CHAVES_ESPECIAL
        if extras:
            raise ErroCalendario(f"{onde}: chave desconhecida {sorted(extras)}")
        if "abertura" not in info and "fechamento" not in info:
            raise ErroCalendario(f"{onde} deve ter abertura e/ou fechamento")
        ab = _validar_hora(info["abertura"], f"{onde}.abertura") if "abertura" in info else None
        fe = _validar_hora(info["fechamento"], f"{onde}.fechamento") if "fechamento" in info else None
        _validar_horas(ab, fe, corte, onde)
        if "motivo" in info and not isinstance(info["motivo"], str):
            raise ErroCalendario(f"{onde}.motivo deve ser um texto")


def _validar_feriados(feriados: object, valido_ate: object, especiais: object) -> None:
    """Valida `feriados_b3`: data entre aspas, motivo, dia útil, sem repetir dias_especiais e até a validade."""
    if not isinstance(feriados, dict):
        raise ErroCalendario("feriados_b3 deve ser um mapeamento (\"AAAA-MM-DD\": motivo)")
    if valido_ate is None:
        raise ErroCalendario("falta a chave 'feriados_b3_valido_ate' (obrigatória quando há feriados_b3)")
    valido_ate_txt = _validar_data(valido_ate, "feriados_b3_valido_ate")
    limite = date.fromisoformat(valido_ate_txt)
    for data, motivo in feriados.items():
        onde = f"feriados_b3[{data}]"
        _validar_data(data, "feriados_b3")
        if not isinstance(motivo, str) or not motivo.strip():
            raise ErroCalendario(f"{onde}: o motivo deve ser um texto não vazio")
        d = date.fromisoformat(data)
        if d.weekday() >= 5:
            raise ErroCalendario(f"{onde}: cai no fim de semana; não precisa entrar")
        if especiais and data in especiais:
            raise ErroCalendario(f"{onde}: também está em dias_especiais; use só uma das duas listas")
        if d > limite:
            raise ErroCalendario(f"{onde}: depois de feriados_b3_valido_ate ({valido_ate_txt})")


@functools.lru_cache
def carregar_parametros(caminho: str | None = None) -> dict:
    """Lê o `parametros.yaml` (ou o caminho dado) e devolve o dicionário validado."""
    arquivo = Path(caminho) if caminho else CAMINHO_PARAMETROS
    with arquivo.open(encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    if not isinstance(dados, dict):
        raise ErroCalendario("o arquivo de parâmetros deve ser um mapeamento")
    for chave in dados:
        if chave not in _CHAVES_DE_TOPO:
            raise ErroCalendario(f"chave desconhecida no arquivo de parâmetros: {chave!r}")
    for obrigatoria in ("fuso", "corte_noite", "horarios_b3_valido_ate", "horarios_b3"):
        if obrigatoria not in dados:
            raise ErroCalendario(f"falta a chave {obrigatoria!r} no arquivo de parâmetros")
    if dados["fuso"] != "America/Sao_Paulo":
        raise ErroCalendario("fuso deve ser \"America/Sao_Paulo\"")
    corte = _validar_hora(dados["corte_noite"], "corte_noite")
    _validar_data(dados["horarios_b3_valido_ate"], "horarios_b3_valido_ate")
    _validar_periodos(dados["horarios_b3"], corte)
    if dados.get("dias_especiais") is not None:
        _validar_dias_especiais(dados["dias_especiais"], corte)
    if "feriados_b3" in dados:
        _validar_feriados(dados["feriados_b3"], dados.get("feriados_b3_valido_ate"), dados.get("dias_especiais"))
    return dados


def _data(valor) -> date:
    """Aceita date, datetime ou Timestamp e devolve só a data."""
    return valor.date() if isinstance(valor, datetime) else valor


def _periodo_de(d: date, periodos: list[dict]) -> dict | None:
    """Período com maior a_partir_de <= d (None se d for anterior ao primeiro)."""
    atual = None
    for periodo in periodos:
        if date.fromisoformat(periodo["a_partir_de"]) <= d:
            atual = periodo
    return atual


def _instante(d: date, hora: time) -> pd.Timestamp:
    """Junta data e hora no fuso de São Paulo."""
    return pd.Timestamp(datetime.combine(d, hora)).tz_localize(SP)


def _exigir_pregao(t: date, cal: list[date]) -> None:
    """Levanta `ErroCalendario` se t não for um pregão de `cal` (lista ordenada)."""
    i = bisect.bisect_left(cal, t)
    if i == len(cal) or cal[i] != t:
        raise ErroCalendario(f"{t} não é pregão (não está no calendário)")


def pregoes(precos: pd.DataFrame) -> list[date]:
    """Datas ordenadas e únicas com preço do IBOV (linhas com fechamento preenchido)."""
    ibov = precos.loc[(precos["ticker"] == "IBOV") & precos["fechamento"].notna(), "data"]
    if ibov.empty:
        return []
    return sorted(set(pd.to_datetime(ibov).dt.date))


def horario_b3(d: date, caminho: str | None = None) -> tuple[time, time]:
    """Abertura e fechamento do pregão de d (período vigente, com o ajuste de dia especial)."""
    d = _data(d)
    params = carregar_parametros(caminho)
    valido_ate = params["horarios_b3_valido_ate"]
    if d > date.fromisoformat(valido_ate):
        raise ErroCalendario(
            f"horário da B3 não cadastrado para {d}: os horários valem até {valido_ate}; "
            "atualizar config/parametros.yaml"
        )
    periodo = _periodo_de(d, params["horarios_b3"])
    if periodo is None:
        raise ErroCalendario(
            f"horário da B3 não cadastrado para {d}: anterior ao primeiro período de parametros.yaml"
        )
    abertura_txt = periodo["abertura"]
    fechamento_txt = periodo["fechamento"]
    especial = (params.get("dias_especiais") or {}).get(d.isoformat())
    if especial:
        abertura_txt = especial.get("abertura", abertura_txt)
        fechamento_txt = especial.get("fechamento", fechamento_txt)
    ab = time.fromisoformat(abertura_txt)
    fe = time.fromisoformat(fechamento_txt)
    if ab >= fe:
        raise ErroCalendario(f"{d}: abertura {ab} deve ser antes do fechamento {fe} (dia especial)")
    return ab, fe


def abertura(d: date) -> pd.Timestamp:
    """Instante de abertura do pregão de d (fuso de São Paulo)."""
    d = _data(d)
    ab, _ = horario_b3(d)
    return _instante(d, ab)


def fechamento(d: date) -> pd.Timestamp:
    """Instante de fechamento do pregão de d (fuso de São Paulo)."""
    d = _data(d)
    _, fe = horario_b3(d)
    return _instante(d, fe)


def corte_manha(d: date, caminho: str | None = None) -> pd.Timestamp:
    """Fim da janela da noite que termina na manhã de d (corte_noite, fuso de São Paulo)."""
    d = _data(d)
    corte = time.fromisoformat(carregar_parametros(caminho)["corte_noite"])
    return _instante(d, corte)


def proximo_pregao(t: date, cal: list[date]) -> date | None:
    """Próximo pregão de `cal` depois de t (None se não houver)."""
    t = _data(t)
    i = bisect.bisect_right(cal, t)
    return cal[i] if i < len(cal) else None


def janela_noite(t: date, cal: list[date], t1: date | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Janela da noite do pregão t: (fechamento de t, corte da manhã de t1). Início exclusivo, fim inclusivo.

    t1 é o pregão seguinte (padrão: `proximo_pregao`). Se t1 for dado, tem que ser o próximo
    pregão já existente em `cal`, ou então `cal` não tem próximo e t1 é usado como está.
    """
    t = _data(t)
    _exigir_pregao(t, cal)
    proximo = proximo_pregao(t, cal)
    if t1 is None:
        if proximo is None:
            raise ErroCalendario(f"sem próximo pregão depois de {t} em cal: informe t1")
        t1 = proximo
    else:
        t1 = _data(t1)
        if t1 <= t:
            raise ErroCalendario(f"t1 ({t1}) deve ser depois de t ({t})")
        if proximo is not None and t1 != proximo:
            raise ErroCalendario(f"t1 ({t1}) difere do próximo pregão em cal ({proximo})")
    return fechamento(t), corte_manha(t1)


def janela_pregao(t: date, cal: list[date]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Janela do pregão t: (abertura, fechamento), ambas inclusivas."""
    t = _data(t)
    _exigir_pregao(t, cal)
    return abertura(t), fechamento(t)


def _classificar_instante(ts, cal: list[date], horario, corte, corte_proximo) -> tuple[str, date | None]:
    """Janela e pregão de referência de um instante (seção 7.2).

    Só o pregão da própria data de `ts` (em São Paulo) precisa de horário: os pregões de datas anteriores
    já fecharam antes de `ts`, e os de datas posteriores abrem depois do corte das 8h deles.
    `horario(d)` -> (abertura, fechamento) e `corte(d)` -> instante do corte da manhã de d.
    """
    if pd.isna(ts):
        return "sem_horario", None
    dia = ts.tz_convert(SP).date()
    k = bisect.bisect_left(cal, dia)  # 1º pregão com data >= dia
    if k < len(cal) and cal[k] == dia:
        ab, fe = horario(dia)
        if ts <= fe:
            if ab <= ts:
                return "pregao", dia
            if ts <= corte(dia):
                return ("fora_do_calendario", None) if k == 0 else ("noite", cal[k - 1])
            return "pre_abertura", dia
        k += 1  # depois do fechamento de `dia`: vale o próximo pregão
    if k == len(cal):
        if corte_proximo is not None and ts <= corte_proximo:
            return "noite", cal[-1]
        return "fora_do_calendario", None
    # ts é de uma data anterior a cal[k], logo antes do corte das 8h de cal[k]
    return ("fora_do_calendario", None) if k == 0 else ("noite", cal[k - 1])


def classificar_noticias(
    noticias: pd.DataFrame, cal: list[date], proximo_ao_vivo: date | None = None, caminho: str | None = None
) -> pd.DataFrame:
    """Cópia de `noticias` com as colunas `janela` e `pregao_ref` (ver `_classificar_instante`).

    `noticias` traz `data_hora_publicacao` tz-aware ou NaT. `cal` é a lista de pregões ordenada.
    `proximo_ao_vivo` é o próximo pregão ainda sem preço (só para a noite do último pregão de `cal`).
    Preguiçoso (24/10/2026): só pede o horário da B3 do pregão que cai na data (São Paulo) de alguma notícia.
    Pregão sem horário cadastrado e sem notícia na sua data não gera erro; notícia na data de um pregão sem
    horário levanta `ErroCalendario` (mensagem de `horario_b3`). Mesmo resultado do algoritmo antigo
    (todos os horários antes) sempre que o antigo não levanta erro.
    """
    cal = [_data(p) for p in cal]
    horarios: dict[date, tuple[pd.Timestamp, pd.Timestamp]] = {}
    cortes: dict[date, pd.Timestamp] = {}

    def _horario(d: date) -> tuple[pd.Timestamp, pd.Timestamp]:
        if d not in horarios:
            ab, fe = horario_b3(d, caminho)
            horarios[d] = (_instante(d, ab), _instante(d, fe))
        return horarios[d]

    def _corte(d: date) -> pd.Timestamp:
        if d not in cortes:
            cortes[d] = corte_manha(d, caminho)
        return cortes[d]

    corte_proximo = _corte(_data(proximo_ao_vivo)) if proximo_ao_vivo is not None and cal else None
    janelas = []
    refs = []
    for ts in noticias["data_hora_publicacao"]:
        janela, ref = _classificar_instante(ts, cal, _horario, _corte, corte_proximo)
        janelas.append(janela)
        refs.append(ref)
    saida = noticias.copy()
    saida["janela"] = janelas
    saida["pregao_ref"] = pd.to_datetime(pd.Series(refs, index=saida.index, dtype=object))
    return saida


# Feriados da B3 (dias úteis sem pregão, lista `feriados_b3` do parametros.yaml; seção 4 do plano da etapa 8).
_MOTIVO_FIM_DE_SEMANA = {5: "sábado", 6: "domingo"}
_DIAS_PARA_ACHAR_PREGAO = 15


def feriados_b3(caminho: str | None = None) -> dict[date, str]:
    """Feriados da B3 do parametros.yaml (dias úteis sem pregão) com o motivo de cada um."""
    params = carregar_parametros(caminho)
    if "feriados_b3" not in params:
        raise ErroCalendario("falta a chave 'feriados_b3' em config/parametros.yaml")
    return {date.fromisoformat(data): motivo for data, motivo in params["feriados_b3"].items()}


def _feriados_vigentes(d: date, caminho: str | None) -> dict[date, str]:
    """Lista de feriados; levanta `ErroCalendario` se d passar de `feriados_b3_valido_ate`."""
    lista = feriados_b3(caminho)
    valido_ate = date.fromisoformat(carregar_parametros(caminho)["feriados_b3_valido_ate"])
    if d > valido_ate:
        raise ErroCalendario(f"lista de feriados da B3 vale até {valido_ate}; atualizar config/parametros.yaml")
    return lista


def motivo_sem_pregao(d: date, caminho: str | None = None) -> str | None:
    """Motivo de d não ser pregão ("sábado", "domingo" ou o texto da lista); None se d é pregão."""
    d = _data(d)
    lista = _feriados_vigentes(d, caminho)
    if d.weekday() >= 5:
        return _MOTIVO_FIM_DE_SEMANA[d.weekday()]
    return lista.get(d)


def e_pregao_previsto(d: date, caminho: str | None = None) -> bool:
    """True se d deve ser pregão: dia útil e fora da lista de feriados da B3."""
    return motivo_sem_pregao(d, caminho) is None


def pregao_anterior_previsto(d: date, caminho: str | None = None) -> date:
    """Último pregão previsto antes de d (volta dia a dia, no máximo 15 dias)."""
    d = _data(d)
    atual = d
    for _ in range(_DIAS_PARA_ACHAR_PREGAO):
        atual -= timedelta(days=1)
        if e_pregao_previsto(atual, caminho):
            return atual
    raise ErroCalendario(f"nenhum pregão previsto nos {_DIAS_PARA_ACHAR_PREGAO} dias antes de {d}")


def primeiro_pregao_do_mes(d: date, caminho: str | None = None) -> bool:
    """True se d é pregão previsto e nenhum dia anterior do mesmo mês é pregão previsto."""
    d = _data(d)
    if not e_pregao_previsto(d, caminho):
        return False
    dia = d.replace(day=1)
    while dia < d:
        if e_pregao_previsto(dia, caminho):
            return False
        dia += timedelta(days=1)
    return True


def avisos_validade(d: date, dias: int = 30, caminho: str | None = None) -> list[str]:
    """Avisos das listas da B3 (feriados e horários) que vencem em até `dias` dias a partir de d."""
    d = _data(d)
    params = carregar_parametros(caminho)
    avisos = []
    if "feriados_b3_valido_ate" in params:
        feriados_ate = date.fromisoformat(params["feriados_b3_valido_ate"])
        if (feriados_ate - d).days <= dias:
            avisos.append(
                f"Feriados da B3 cadastrados só até {feriados_ate}: atualizar feriados_b3 no parametros.yaml."
            )
    horarios_ate = date.fromisoformat(params["horarios_b3_valido_ate"])
    if (horarios_ate - d).days <= dias:
        avisos.append(
            f"Horários da B3 cadastrados só até {horarios_ate}: atualizar horarios_b3 no parametros.yaml."
        )
    return avisos


def conferir_feriados(cal: list[date], desde: date, ate: date, caminho: str | None = None) -> dict:
    """Compara os pregões reais (`cal`) com a lista de feriados, de desde a ate (inclusive).

    `sem_pregao_fora_da_lista`: dias úteis sem pregão e fora da lista (pode faltar um feriado na lista).
    `listados_com_pregao`: feriados da lista que tiveram pregão (a lista pode estar errada).
    Datas como texto AAAA-MM-DD, em ordem.
    """
    desde = _data(desde)
    ate = _data(ate)
    lista = feriados_b3(caminho)
    pregoes_reais = {_data(p) for p in cal}
    sem_pregao = []
    listados = []
    d = desde
    while d <= ate:
        if d.weekday() < 5:
            if d in lista:
                if d in pregoes_reais:
                    listados.append(d)
            elif d not in pregoes_reais:
                sem_pregao.append(d)
        d += timedelta(days=1)
    return {
        "sem_pregao_fora_da_lista": [x.isoformat() for x in sem_pregao],
        "listados_com_pregao": [x.isoformat() for x in listados],
    }
