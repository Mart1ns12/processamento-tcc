"""Testes de processamento/calendario.py: pregões, horários da B3 e janelas de notícias.

Usa o `parametros.yaml` real (horários) e arquivos YAML em tmp_path para os casos de erro.
Nenhum teste usa banco ou rede.
"""

import bisect
from datetime import date, time

import pandas as pd
import pytest

from processamento.calendario import (
    SP,
    ErroCalendario,
    abertura,
    carregar_parametros,
    classificar_noticias,
    corte_manha,
    e_pregao_previsto,
    fechamento,
    horario_b3,
    janela_noite,
    janela_pregao,
    pregoes,
)

CAL = [
    date(2024, 12, 27),
    date(2024, 12, 30),
    date(2025, 1, 2),
    date(2025, 2, 27),
    date(2025, 2, 28),
    date(2025, 3, 5),
    date(2025, 3, 6),
    date(2025, 10, 16),
    date(2025, 10, 17),
    date(2025, 10, 20),
    date(2025, 10, 21),
    date(2025, 10, 31),
    date(2025, 11, 3),
    date(2025, 11, 19),
    date(2025, 11, 21),
    date(2025, 12, 23),
    date(2025, 12, 26),
]


def _sp(texto: str) -> pd.Timestamp:
    """Instante de São Paulo a partir de 'AAAA-MM-DD HH:MM[:SS]'."""
    return pd.Timestamp(texto).tz_localize(SP)


def _escrever(tmp_path, texto: str) -> str:
    caminho = tmp_path / "parametros.yaml"
    caminho.write_text(texto, encoding="utf-8")
    return str(caminho)


_CABECALHO_YAML = """fuso: "America/Sao_Paulo"
corte_noite: "08:00"
horarios_b3_valido_ate: "2027-03-12"
"""


# --- pregoes ---------------------------------------------------------------------------------


def test_pregoes_so_conta_ibov_com_fechamento():
    precos = pd.DataFrame(
        {
            "ticker": ["IBOV", "BRENT", "BRENT", "BRENT", "USDBRL", "PETR4", "IBOV", "IBOV"],
            "data": [
                "2025-11-19",
                "2025-11-19",
                "2025-11-20",
                "2025-11-21",
                "2025-11-22",
                "2025-11-20",
                "2025-11-21",
                "2025-11-24",
            ],
            "fechamento": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, None],
        }
    )
    assert pregoes(precos) == [date(2025, 11, 19), date(2025, 11, 21)]


def test_pregoes_aceita_date_e_timestamp():
    precos = pd.DataFrame(
        {
            "ticker": ["IBOV", "IBOV"],
            "data": [date(2025, 11, 21), pd.Timestamp("2025-11-19")],
            "fechamento": [1.0, 1.0],
        }
    )
    assert pregoes(precos) == [date(2025, 11, 19), date(2025, 11, 21)]


# --- horario_b3 ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dia, abertura, fechamento_esperado",
    [
        (date(2019, 11, 4), time(10, 0), time(18, 0)),
        (date(2020, 2, 26), time(13, 0), time(18, 0)),  # quarta-feira de cinzas
        (date(2020, 3, 6), time(10, 0), time(18, 0)),
        (date(2020, 3, 9), time(10, 0), time(17, 0)),
        (date(2021, 3, 12), time(10, 0), time(18, 0)),
        (date(2021, 3, 15), time(10, 0), time(17, 0)),
        (date(2021, 11, 5), time(10, 0), time(17, 0)),
        (date(2021, 11, 8), time(10, 0), time(18, 0)),
        (date(2022, 3, 2), time(13, 0), time(18, 0)),  # quarta-feira de cinzas
        (date(2022, 3, 11), time(10, 0), time(18, 0)),
        (date(2022, 3, 14), time(10, 0), time(17, 0)),
        (date(2022, 11, 4), time(10, 0), time(17, 0)),
        (date(2022, 11, 7), time(10, 0), time(18, 0)),
        (date(2023, 3, 10), time(10, 0), time(18, 0)),
        (date(2023, 3, 13), time(10, 0), time(17, 0)),
        (date(2023, 11, 3), time(10, 0), time(17, 0)),
        (date(2023, 11, 6), time(10, 0), time(18, 0)),
        (date(2024, 2, 14), time(13, 0), time(18, 0)),  # quarta-feira de cinzas
        (date(2024, 3, 8), time(10, 0), time(18, 0)),
        (date(2024, 3, 11), time(10, 0), time(17, 0)),
        (date(2024, 7, 29), time(10, 0), time(17, 0)),
        (date(2024, 11, 1), time(10, 0), time(17, 0)),
        (date(2024, 11, 4), time(10, 0), time(18, 0)),
        (date(2025, 3, 5), time(13, 0), time(18, 0)),  # quarta-feira de cinzas
        (date(2025, 3, 7), time(10, 0), time(18, 0)),
        (date(2025, 3, 10), time(10, 0), time(17, 0)),
        (date(2025, 10, 31), time(10, 0), time(17, 0)),
        (date(2025, 11, 3), time(10, 0), time(18, 0)),
        (date(2026, 2, 18), time(13, 0), time(18, 0)),  # quarta-feira de cinzas 2026
        (date(2026, 10, 22), time(10, 0), time(17, 0)),
    ],
)
def test_horario_b3_por_periodo_e_dia_especial(dia, abertura, fechamento_esperado):
    assert horario_b3(dia) == (abertura, fechamento_esperado)


def test_horario_b3_antes_do_primeiro_periodo_erro():
    with pytest.raises(ErroCalendario, match="anterior ao primeiro período"):
        horario_b3(date(2019, 11, 1))


def test_horario_b3_depois_do_valido_ate_erro():
    with pytest.raises(ErroCalendario):
        horario_b3(date(2028, 1, 3))


def test_horario_sem_aspas_erro_com_mensagem_de_aspas(tmp_path):
    caminho = _escrever(
        tmp_path,
        _CABECALHO_YAML
        + "horarios_b3:\n"
        + '  - {a_partir_de: "2024-03-11", abertura: 10:00, fechamento: "17:00"}\n',
    )
    with pytest.raises(ErroCalendario, match="aspas"):
        carregar_parametros(caminho)


def test_yaml_sem_dias_especiais_carrega_sem_erro(tmp_path):
    caminho = _escrever(
        tmp_path,
        _CABECALHO_YAML
        + "horarios_b3:\n"
        + '  - {a_partir_de: "2024-03-11", abertura: "10:00", fechamento: "17:00"}\n',
    )
    params = carregar_parametros(caminho)
    assert params["horarios_b3"][0]["fechamento"] == "17:00"
    assert horario_b3(date(2025, 3, 5), caminho) == (time(10, 0), time(17, 0))


# --- janelas de pregão e noite ---------------------------------------------------------------


def test_janela_pregao_usa_abertura_e_fechamento():
    assert janela_pregao(date(2025, 3, 5), CAL) == (_sp("2025-03-05 13:00"), _sp("2025-03-05 18:00"))
    assert janela_pregao(date(2025, 10, 17), CAL) == (_sp("2025-10-17 10:00"), _sp("2025-10-17 17:00"))


@pytest.mark.parametrize(
    "t, inicio, fim",
    [
        (date(2025, 10, 16), "2025-10-16 17:00", "2025-10-17 08:00"),
        (date(2025, 10, 17), "2025-10-17 17:00", "2025-10-20 08:00"),
        (date(2025, 10, 31), "2025-10-31 17:00", "2025-11-03 08:00"),
        (date(2024, 12, 30), "2024-12-30 18:00", "2025-01-02 08:00"),
        (date(2025, 11, 19), "2025-11-19 18:00", "2025-11-21 08:00"),
        (date(2025, 2, 28), "2025-02-28 18:00", "2025-03-05 08:00"),
        (date(2025, 12, 23), "2025-12-23 18:00", "2025-12-26 08:00"),
    ],
)
def test_janela_noite_vai_do_fechamento_ate_8h_do_proximo_pregao(t, inicio, fim):
    assert janela_noite(t, CAL) == (_sp(inicio), _sp(fim))


def test_janela_noite_ultimo_pregao_sem_t1_erro():
    with pytest.raises(ErroCalendario):
        janela_noite(date(2025, 12, 26), CAL)


def test_janela_noite_ultimo_pregao_com_t1_informado():
    assert janela_noite(date(2025, 12, 26), CAL, t1=date(2025, 12, 29)) == (
        _sp("2025-12-26 18:00"),
        _sp("2025-12-29 08:00"),
    )


def test_janela_noite_data_que_nao_e_pregao_erro():
    with pytest.raises(ErroCalendario):
        janela_noite(date(2025, 11, 20), CAL)


def test_janela_noite_t1_nao_pode_ser_anterior_a_t():
    with pytest.raises(ErroCalendario):
        janela_noite(date(2025, 10, 16), CAL, t1=date(2025, 10, 16))


def test_janela_noite_t1_diferente_do_proximo_pregao_erro():
    with pytest.raises(ErroCalendario):
        janela_noite(date(2025, 10, 16), CAL, t1=date(2025, 10, 20))


# --- classificar_noticias --------------------------------------------------------------------


def _noticias(instantes: list) -> pd.DataFrame:
    """DataFrame com `data_hora_publicacao` (instante textual de São Paulo, None = NaT)."""
    valores = [_sp(texto) if texto is not None else pd.NaT for texto in instantes]
    return pd.DataFrame({"id": range(len(valores)), "data_hora_publicacao": valores})


CASOS_CLASSIFICACAO = [
    ("2025-10-16 16:59:59", "pregao", "2025-10-16"),
    ("2025-10-16 17:00:00", "pregao", "2025-10-16"),
    ("2025-10-16 17:00:01", "noite", "2025-10-16"),
    ("2025-10-17 08:00:00", "noite", "2025-10-16"),
    ("2025-10-17 08:00:01", "pre_abertura", "2025-10-17"),
    ("2025-10-17 10:00:00", "pregao", "2025-10-17"),
    ("2025-10-18 12:00:00", "noite", "2025-10-17"),
    ("2025-10-20 07:59:59", "noite", "2025-10-17"),
    ("2025-01-01 12:00:00", "noite", "2024-12-30"),
    ("2025-11-20 09:30:00", "noite", "2025-11-19"),
    ("2025-03-05 11:00:00", "pre_abertura", "2025-03-05"),
    ("2025-03-05 13:00:00", "pregao", "2025-03-05"),
    ("2025-10-31 17:30:00", "noite", "2025-10-31"),
    ("2025-11-03 17:30:00", "pregao", "2025-11-03"),
    (None, "sem_horario", None),
    ("2024-12-26 20:00:00", "fora_do_calendario", None),
    ("2025-12-26 19:00:00", "fora_do_calendario", None),
]


def test_classificar_noticias_janelas_e_pregao_de_referencia():
    noticias = _noticias([texto for texto, _, _ in CASOS_CLASSIFICACAO])
    saida = classificar_noticias(noticias, CAL)
    for i, (texto, janela, ref) in enumerate(CASOS_CLASSIFICACAO):
        assert saida.loc[i, "janela"] == janela, texto
        if ref is None:
            assert pd.isna(saida.loc[i, "pregao_ref"]), texto
        else:
            assert saida.loc[i, "pregao_ref"] == pd.Timestamp(ref), texto


def test_classificar_noticias_devolve_copia_sem_mexer_na_entrada():
    noticias = _noticias(["2025-10-16 17:00:01"])
    saida = classificar_noticias(noticias, CAL)
    assert "janela" not in noticias.columns
    assert saida is not noticias
    assert "pregao_ref" in saida.columns


def test_classificar_noticias_ultimo_pregao_com_proximo_ao_vivo():
    noticias = _noticias(["2025-12-26 19:00:00", "2025-12-29 08:00:01"])
    saida = classificar_noticias(noticias, CAL, proximo_ao_vivo=date(2025, 12, 29))
    assert saida.loc[0, "janela"] == "noite"
    assert saida.loc[0, "pregao_ref"] == pd.Timestamp("2025-12-26")
    assert saida.loc[1, "janela"] == "fora_do_calendario"
    assert pd.isna(saida.loc[1, "pregao_ref"])


def test_fechamento_do_pregao_de_teste_bate_com_o_horario_b3():
    assert fechamento(date(2025, 10, 16)) == _sp("2025-10-16 17:00")


# --- classificar_noticias com o yaml real (Fase 1) -------------------------------------------


def _pregoes_previstos(*intervalos: tuple[str, str]) -> list[date]:
    """Dias úteis (AAAA-MM-DD, inclusive) de cada intervalo que são pregão previsto no yaml real."""
    return [d.date() for a, b in intervalos for d in pd.bdate_range(a, b) if e_pregao_previsto(d.date())]


CAL_1B = _pregoes_previstos(
    ("2020-02-17", "2020-03-13"),
    ("2021-11-01", "2021-11-19"),
    ("2023-10-30", "2023-11-10"),
    ("2024-03-04", "2024-03-15"),
)

CASOS_1B = [
    ("2020-02-21 18:00:00", "pregao", "2020-02-21"),
    ("2020-02-21 18:00:01", "noite", "2020-02-21"),
    ("2020-02-25 12:00:00", "noite", "2020-02-21"),  # Carnaval
    ("2020-02-26 08:00:00", "noite", "2020-02-21"),
    ("2020-02-26 08:00:01", "pre_abertura", "2020-02-26"),
    ("2020-02-26 10:30:00", "pre_abertura", "2020-02-26"),
    ("2020-02-26 12:59:59", "pre_abertura", "2020-02-26"),
    ("2020-02-26 13:00:00", "pregao", "2020-02-26"),
    ("2020-02-26 18:00:00", "pregao", "2020-02-26"),
    ("2020-02-26 18:00:01", "noite", "2020-02-26"),
    ("2020-03-06 17:30:00", "pregao", "2020-03-06"),
    ("2020-03-09 17:30:00", "noite", "2020-03-09"),
    ("2021-11-05 17:00:00", "pregao", "2021-11-05"),
    ("2021-11-05 17:00:01", "noite", "2021-11-05"),
    ("2021-11-05 17:30:00", "noite", "2021-11-05"),
    ("2021-11-06 12:00:00", "noite", "2021-11-05"),
    ("2021-11-08 08:00:00", "noite", "2021-11-05"),
    ("2021-11-08 08:00:01", "pre_abertura", "2021-11-08"),
    ("2021-11-08 17:30:00", "pregao", "2021-11-08"),
    ("2021-11-08 18:00:00", "pregao", "2021-11-08"),
    ("2021-11-08 18:00:01", "noite", "2021-11-08"),
    ("2021-11-15 12:00:00", "noite", "2021-11-12"),  # feriado
    ("2023-11-03 17:30:00", "noite", "2023-11-03"),
    ("2023-11-06 17:30:00", "pregao", "2023-11-06"),
    ("2024-03-08 17:30:00", "pregao", "2024-03-08"),
    ("2024-03-11 17:30:00", "noite", "2024-03-11"),
    (None, "sem_horario", None),
]


def test_cal_1b_tem_50_pregoes():
    assert len(CAL_1B) == 50


@pytest.mark.parametrize("texto, janela, ref", CASOS_1B)
def test_classificar_noticias_com_yaml_real(texto, janela, ref):
    saida = classificar_noticias(_noticias([texto]), CAL_1B)
    assert saida.loc[0, "janela"] == janela, texto
    if ref is None:
        assert pd.isna(saida.loc[0, "pregao_ref"]), texto
    else:
        assert saida.loc[0, "pregao_ref"] == pd.Timestamp(ref), texto


# Preguiçoso: yaml temporário com um único período (2024-03-11); o calendário inclui pregões sem horário.

_PERIODO_UNICO_1C = 'horarios_b3:\n  - {a_partir_de: "2024-03-11", abertura: "10:00", fechamento: "17:00"}\n'

CASOS_1C = [
    ("2024-03-12 09:00:00", "pre_abertura", "2024-03-12"),
    ("2024-03-12 17:30:00", "noite", "2024-03-12"),
    ("2024-03-13 12:00:00", "pregao", "2024-03-13"),
    ("2024-03-15 17:00:00", "pregao", "2024-03-15"),
    ("2024-03-11 07:00:00", "noite", "2024-03-08"),  # sem erro: não precisa do horário de 08/03
    ("2024-03-09 12:00:00", "noite", "2024-03-08"),  # sábado, sem erro
    (None, "sem_horario", None),
]


def _cal_1c() -> list[date]:
    return [d.date() for d in pd.bdate_range("2023-12-27", "2024-03-15")]


def test_classificar_noticias_preguicoso_sem_erro(tmp_path):
    caminho = _escrever(tmp_path, _CABECALHO_YAML + _PERIODO_UNICO_1C)
    saida = classificar_noticias(_noticias([t for t, _, _ in CASOS_1C]), _cal_1c(), caminho=caminho)
    for i, (texto, janela, ref) in enumerate(CASOS_1C):
        assert saida.loc[i, "janela"] == janela, texto
        if ref is None:
            assert pd.isna(saida.loc[i, "pregao_ref"]), texto
        else:
            assert saida.loc[i, "pregao_ref"] == pd.Timestamp(ref), texto


def test_classificar_noticias_preguicoso_erro_no_dia_sem_horario(tmp_path):
    caminho = _escrever(tmp_path, _CABECALHO_YAML + _PERIODO_UNICO_1C)
    with pytest.raises(ErroCalendario, match="horário da B3 não cadastrado para 2024-03-08"):
        classificar_noticias(_noticias(["2024-03-08 12:00:00"]), _cal_1c(), caminho=caminho)


# Igualdade com o algoritmo antigo (todos os horários calculados de antemão). Só para comparar.


def _classificar_ingenuo(noticias, cal, proximo_ao_vivo=None):
    """Algoritmo antigo (até 24/10/2026): calcula o horário de TODOS os pregões. Só para comparar."""
    fechamentos = [fechamento(p) for p in cal]
    aberturas = [abertura(p) for p in cal]
    cortes = [corte_manha(p) for p in cal]
    corte_proximo = corte_manha(proximo_ao_vivo) if proximo_ao_vivo is not None and cal else None
    janelas, refs = [], []
    for ts in noticias["data_hora_publicacao"]:
        if pd.isna(ts):
            j, r = "sem_horario", None
        else:
            k = bisect.bisect_left(fechamentos, ts)
            if k == len(cal):
                j, r = ("noite", cal[-1]) if corte_proximo is not None and ts <= corte_proximo else ("fora_do_calendario", None)
            elif aberturas[k] <= ts <= fechamentos[k]:
                j, r = "pregao", cal[k]
            elif ts <= cortes[k]:
                j, r = ("fora_do_calendario", None) if k == 0 else ("noite", cal[k - 1])
            else:
                j, r = "pre_abertura", cal[k]
        janelas.append(j)
        refs.append(r)
    saida = noticias.copy()
    saida["janela"] = janelas
    saida["pregao_ref"] = pd.to_datetime(pd.Series(refs, index=saida.index, dtype=object))
    return saida


CAL_1D = _pregoes_previstos(("2025-02-24", "2025-03-14"), ("2025-10-13", "2025-11-07"))


def _instantes_1d() -> list[str]:
    """Para cada dia: um instante a cada 15 minutos (00:00 a 23:45) e os instantes de borda."""
    extras = [
        "08:00:00", "08:00:01", "09:59:59", "10:00:00", "13:00:00",
        "17:00:00", "17:00:01", "18:00:00", "18:00:01", "23:59:59",
    ]
    dias = list(pd.date_range("2025-02-20", "2025-03-18")) + list(pd.date_range("2025-10-09", "2025-11-12"))
    textos: list[str] = []
    for dia in dias:
        dia_txt = dia.strftime("%Y-%m-%d")
        textos += [f"{dia_txt} {m // 60:02d}:{m % 60:02d}:00" for m in range(0, 1440, 15)]
        textos += [f"{dia_txt} {hora}" for hora in extras]
    return textos


@pytest.mark.parametrize("proximo", [None, date(2025, 11, 10)])
def test_classificar_noticias_igual_ao_algoritmo_antigo(proximo):
    noticias = _noticias(_instantes_1d() + [None])
    assert len(noticias) == 6573
    novo = classificar_noticias(noticias, CAL_1D, proximo_ao_vivo=proximo)
    antigo = _classificar_ingenuo(noticias, CAL_1D, proximo)
    pd.testing.assert_frame_equal(novo, antigo)


def test_classificar_noticias_igual_ao_antigo_com_instantes_em_utc():
    noticias = _noticias(_instantes_1d() + [None])
    em_utc = noticias.assign(data_hora_publicacao=noticias["data_hora_publicacao"].dt.tz_convert("UTC"))
    novo = classificar_noticias(em_utc, CAL_1D)
    antigo = _classificar_ingenuo(noticias, CAL_1D)
    assert list(novo["janela"]) == list(antigo["janela"])
