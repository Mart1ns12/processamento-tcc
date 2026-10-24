"""Testes dos feriados da B3 em processamento/calendario.py (seção 4 do plano da etapa 8).

Usa o `parametros.yaml` real para os valores esperados e arquivos YAML em tmp_path (cópias
do real com uma troca) para os casos de erro. Nenhum teste usa banco ou rede. O teste
`@pytest.mark.banco` só lê e só roda com `PROC_TESTES_COM_BANCO=1 pytest -q -m banco`.
"""

from datetime import date
from pathlib import Path

import pytest

from processamento import calendario
from processamento.calendario import (
    ErroCalendario,
    avisos_validade,
    carregar_parametros,
    conferir_feriados,
    e_pregao_previsto,
    feriados_b3,
    motivo_sem_pregao,
    pregao_anterior_previsto,
    primeiro_pregao_do_mes,
)

REAL = Path(calendario.CAMINHO_PARAMETROS)


def _yaml_trocado(tmp_path: Path, trocas: list[tuple[str, str]]) -> str:
    """Cópia do parametros.yaml real com as trocas (cada trecho antigo tem que existir uma vez)."""
    texto = REAL.read_text(encoding="utf-8")
    for antigo, novo in trocas:
        assert texto.count(antigo) == 1, f"trecho não achado uma vez: {antigo!r}"
        texto = texto.replace(antigo, novo)
    destino = tmp_path / "parametros.yaml"
    destino.write_text(texto, encoding="utf-8")
    return str(destino)


# --- valores esperados (yaml real) ---


@pytest.mark.parametrize(
    "dia, esperado",
    [
        (date(2026, 10, 26), True),
        (date(2026, 10, 24), False),  # sábado
        (date(2026, 10, 25), False),  # domingo
        (date(2026, 11, 2), False),  # Finados
        (date(2026, 11, 3), True),
        (date(2026, 11, 20), False),
        (date(2026, 12, 24), False),
        (date(2026, 12, 31), False),
        (date(2026, 7, 9), True),  # 09/07 tem pregão
        (date(2027, 2, 8), False),
        (date(2027, 2, 9), False),
        (date(2027, 2, 10), True),  # quarta de cinzas: abre às 13h, mas tem pregão
        (date(2019, 12, 31), False),  # último dia útil do ano sem pregão
        (date(2020, 2, 25), False),  # Carnaval
        (date(2020, 2, 26), True),  # quarta de cinzas (histórico novo)
        (date(2021, 1, 25), False),
        (date(2021, 7, 9), False),
        (date(2022, 1, 25), True),
        (date(2023, 12, 29), False),
        (date(2024, 5, 30), False),  # Corpus Christi
    ],
)
def test_e_pregao_previsto(dia, esperado):
    assert e_pregao_previsto(dia) is esperado


def test_e_pregao_previsto_depois_da_validade_levanta_erro():
    with pytest.raises(ErroCalendario, match="vale até 2027-12-31"):
        e_pregao_previsto(date(2028, 1, 3))


@pytest.mark.parametrize(
    "dia, esperado",
    [
        (date(2026, 10, 26), date(2026, 10, 23)),
        (date(2026, 11, 3), date(2026, 10, 30)),  # 02/11 é Finados
        (date(2026, 11, 23), date(2026, 11, 19)),  # 20/11 é sexta de feriado
        (date(2026, 12, 28), date(2026, 12, 23)),  # 24 e 25 fechados
        (date(2027, 1, 4), date(2026, 12, 30)),  # 31/12 e 01/01 fechados
        (date(2027, 2, 10), date(2027, 2, 5)),  # carnaval 08 e 09
        (date(2025, 10, 22), date(2025, 10, 21)),
        (date(2020, 2, 26), date(2020, 2, 21)),  # Carnaval 24 e 25
    ],
)
def test_pregao_anterior_previsto(dia, esperado):
    assert pregao_anterior_previsto(dia) == esperado


@pytest.mark.parametrize(
    "dia, esperado",
    [
        (date(2026, 11, 3), True),
        (date(2026, 11, 4), False),
        (date(2026, 12, 1), True),
        (date(2027, 1, 4), True),
        (date(2026, 11, 2), False),  # não é pregão
        (date(2026, 10, 26), False),
    ],
)
def test_primeiro_pregao_do_mes(dia, esperado):
    assert primeiro_pregao_do_mes(dia) is esperado


def test_avisos_validade_vence_em_30_dias():
    assert avisos_validade(date(2027, 12, 1)) == [
        "Feriados da B3 cadastrados só até 2027-12-31: atualizar feriados_b3 no parametros.yaml.",
        "Horários da B3 cadastrados só até 2027-12-31: atualizar horarios_b3 no parametros.yaml.",
    ]


def test_avisos_validade_31_dias_antes_nao_avisa():
    assert avisos_validade(date(2027, 11, 30)) == []


def test_avisos_validade_longe_do_vencimento_nao_avisa():
    assert avisos_validade(date(2026, 10, 26)) == []


def test_conferir_feriados_acha_dia_sem_pregao_fora_da_lista():
    cal = [date(2026, 10, d) for d in (19, 20, 22, 23)]  # sem 21 (quarta)
    assert conferir_feriados(cal, date(2026, 10, 19), date(2026, 10, 23)) == {
        "sem_pregao_fora_da_lista": ["2026-10-21"],
        "listados_com_pregao": [],
    }


def test_conferir_feriados_acha_feriado_listado_com_pregao():
    cal = [date(2026, 10, d) for d in range(5, 17) if date(2026, 10, d).weekday() < 5]  # inclui 12/10
    assert conferir_feriados(cal, date(2026, 10, 5), date(2026, 10, 16)) == {
        "sem_pregao_fora_da_lista": [],
        "listados_com_pregao": ["2026-10-12"],
    }


def test_motivo_sem_pregao():
    assert motivo_sem_pregao(date(2026, 11, 2)) == feriados_b3()[date(2026, 11, 2)] == "Finados (a conferir)"
    assert motivo_sem_pregao(date(2026, 10, 24)) == "sábado"
    assert motivo_sem_pregao(date(2026, 10, 25)) == "domingo"
    assert motivo_sem_pregao(date(2026, 10, 26)) is None


def test_feriados_b3_tem_datas_e_motivos():
    lista = feriados_b3()
    assert all(isinstance(k, date) and isinstance(v, str) and v for k, v in lista.items())
    assert date(2026, 10, 12) in lista


def test_feriados_b3_yaml_real_tem_99_datas():
    assert len(feriados_b3()) == 99


def test_yaml_real_passa_na_validacao():
    assert "feriados_b3" in carregar_parametros()


# --- validação com yaml temporário ---


def test_data_sem_aspas_levanta_erro(tmp_path):
    caminho = _yaml_trocado(tmp_path, [('"2026-11-02": "Finados (a conferir)"', "2026-11-02: \"Finados (a conferir)\"")])
    with pytest.raises(ErroCalendario, match="entre aspas"):
        carregar_parametros(caminho)


def test_feriado_em_fim_de_semana_levanta_erro(tmp_path):
    caminho = _yaml_trocado(tmp_path, [('"2026-11-02": "Finados (a conferir)"', '"2026-11-15": "Finados (a conferir)"')])
    with pytest.raises(ErroCalendario, match="cai no fim de semana"):
        carregar_parametros(caminho)


def test_feriado_tambem_em_dias_especiais_levanta_erro(tmp_path):
    caminho = _yaml_trocado(
        tmp_path,
        [('"2026-11-02": "Finados (a conferir)"', '"2026-02-18": "Quarta de cinzas"')],
    )
    with pytest.raises(ErroCalendario, match="também está em dias_especiais"):
        carregar_parametros(caminho)


def test_feriado_depois_da_validade_levanta_erro(tmp_path):
    caminho = _yaml_trocado(tmp_path, [('feriados_b3_valido_ate: "2027-12-31"', 'feriados_b3_valido_ate: "2026-12-31"')])
    with pytest.raises(ErroCalendario, match="depois de feriados_b3_valido_ate"):
        carregar_parametros(caminho)


def test_sem_validade_com_feriados_levanta_erro(tmp_path):
    caminho = _yaml_trocado(tmp_path, [('feriados_b3_valido_ate: "2027-12-31"', "")])
    with pytest.raises(ErroCalendario, match="feriados_b3_valido_ate"):
        carregar_parametros(caminho)


def test_motivo_vazio_levanta_erro(tmp_path):
    caminho = _yaml_trocado(tmp_path, [('"2026-11-02": "Finados (a conferir)"', '"2026-11-02": "  "')])
    with pytest.raises(ErroCalendario, match="motivo"):
        carregar_parametros(caminho)


def test_sem_lista_de_feriados_as_funcoes_levantam_erro(tmp_path):
    texto = (
        'fuso: "America/Sao_Paulo"\n'
        'corte_noite: "08:00"\n'
        'horarios_b3_valido_ate: "2027-12-31"\n'
        "horarios_b3:\n"
        '  - {a_partir_de: "2024-03-11", abertura: "10:00", fechamento: "17:00"}\n'
    )
    arquivo = tmp_path / "parametros.yaml"
    arquivo.write_text(texto, encoding="utf-8")
    with pytest.raises(ErroCalendario, match="feriados_b3"):
        feriados_b3(str(arquivo))


# --- banco real (opcional, só lê) ---


@pytest.mark.banco
def test_banco_feriados_conferem_com_pregoes_reais():
    from processamento import fontes

    pregoes = calendario.pregoes(fontes.ler_tabela("precos"))
    resultado = conferir_feriados(pregoes, date(2019, 12, 30), pregoes[-1])
    assert resultado == {"sem_pregao_fora_da_lista": [], "listados_com_pregao": []}
