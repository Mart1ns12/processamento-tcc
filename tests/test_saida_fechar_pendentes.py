"""Testes de `fechar_pendentes`, `listar_registros_top` e `gravar_descartado` (plano da etapa 8, fase 5, seção 6).

Gabarito da seção 6 do plano (docs/plano_etapa8.md): os 9 casos e os números do registro de 2026-11-03 e
2026-11-04 (base 10-30 e 11-03). Registros de JSON mínimo escritos à mão; preços de fábrica; histórico com
`params_teste(acaso_sorteios=10000)`. Nenhum teste usa banco, rede ou as pastas reais (só tmp_path).
"""

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from fabrica_precos import precos_de
from fabrica_treino import params_teste
from processamento.saida import pacotes_experimento as pe

SP = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 4, 9, 0, tzinfo=SP)
CAL = [date(2026, 10, 30), date(2026, 11, 3), date(2026, 11, 4)]
FIM = date(2026, 11, 2)
CANDIDATOS = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3", "FFFF3"]

RANKING_1103 = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3"]
SOMBRA_M1_1103 = ["FFFF3", "AAAA3", "BBBB3", "CCCC3", "DDDD3"]
SOMBRA_VOL = ["BBBB3", "DDDD3", "EEEE3", "FFFF3", "AAAA3"]
RANKING_1104 = ["BBBB3", "DDDD3", "FFFF3", "EEEE3", "CCCC3"]
SOMBRA_M1_1104 = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3"]


def _escrever_top(pasta: Path, dia: str, base: str, ranking: list[str], sombra_m1: list[str],
                  sombra_vol: list[str], valido: bool = True) -> None:
    """Registro `<D>.top.json` mínimo (só os campos que `fechar_pendentes` lê)."""
    registro = {
        "pacote": {
            "pregao_previsto": dia,
            "pregao_base": base,
            "data_referencia": dia,
            "valido_para_historico": valido,
            "ranking": [{"ticker": t} for t in ranking],
        },
        "interno": {"candidatos": CANDIDATOS, "sombra_modelo_1": sombra_m1, "sombra_volatilidade": sombra_vol},
    }
    (pasta / f"{dia}.top.json").write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")


def _top_1103(pasta: Path, valido: bool = True) -> None:
    _escrever_top(pasta, "2026-11-03", "2026-10-30", RANKING_1103, SOMBRA_M1_1103, SOMBRA_VOL, valido)


def _top_1104(pasta: Path) -> None:
    _escrever_top(pasta, "2026-11-04", "2026-11-03", RANKING_1104, SOMBRA_M1_1104, SOMBRA_VOL)


def _precos_gabarito(eeee3_sem_preco_1103: bool = False) -> pd.DataFrame:
    """Preços do gabarito (aj = fech). Com `eeee3_sem_preco_1103`, EEEE3 fica sem preço em 11-03."""
    datas = CAL
    eeee3 = [40, None, 41.2] if eeee3_sem_preco_1103 else [40, 41, 41.2]
    return pd.concat([
        precos_de("IBOV", datas, [100, 101.5, 102.515]),
        precos_de("AAAA3", datas, [20, 20.5, 20.5]),
        precos_de("BBBB3", datas, [50, 50.5, 51.5]),
        precos_de("CCCC3", datas, [10, 10.2, 10.0]),
        precos_de("DDDD3", datas, [8, 7.9, 8.1]),
        precos_de("EEEE3", datas, eeee3),
        precos_de("FFFF3", datas, [10, 10.3, 10.4]),
    ], ignore_index=True)


def _ler(pasta: Path, nome: str) -> dict:
    return json.loads((pasta / nome).read_text(encoding="utf-8"))


def _arquivos(pasta: Path) -> list[str]:
    return sorted(c.name for c in pasta.iterdir())


def test_rotina_pulou_um_dia_fecha_o_registro_que_ficou_pendente(tmp_path):
    # Caso 1: só o registro de 11-03; a rotina de 11-04 fecha o 11-03 mesmo sem o registro de 11-04.
    _top_1103(tmp_path)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 4), FIM, AGORA)
    assert avisos == []
    resultado = _ler(tmp_path, "2026-11-03.resultado.json")
    assert resultado["data_referencia"] == "2026-11-03"
    assert resultado["pregao_base"] == "2026-10-30"
    assert resultado["ranking"] == RANKING_1103
    assert resultado["acertos_dia"] == 3
    assert resultado["acertos_top3"] == 2
    assert resultado["resultado_incompleto"] is False
    assert resultado["alvos_candidatos"] == {
        "AAAA3": 1.0, "BBBB3": 0.0, "CCCC3": 1.0, "DDDD3": 0.0, "EEEE3": 1.0, "FFFF3": 1.0,
    }
    assert resultado["acertos_sombra_modelo_1"] == 3
    assert resultado["acertos_sombra_volatilidade"] == 3
    assert resultado["resultado"][0]["retorno_ibov"]["valor"] == pytest.approx(0.015, abs=1e-9)
    assert resultado["resultado"][0]["retorno"]["valor"] == pytest.approx(0.025, abs=1e-9)
    assert resultado["resultado"][1]["superou"] is False
    assert _arquivos(tmp_path) == ["2026-11-03.resultado.json", "2026-11-03.top.json"]


def test_chamar_de_novo_nao_muda_nada(tmp_path):
    # Caso 2: o resultado já existe; a segunda chamada não toca nos bytes e não avisa.
    _top_1103(tmp_path)
    pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 4), FIM, AGORA)
    antes = (tmp_path / "2026-11-03.resultado.json").read_bytes()
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 4), FIM, AGORA)
    assert avisos == []
    assert (tmp_path / "2026-11-03.resultado.json").read_bytes() == antes


def test_dois_registros_fecham_e_historico_bate_com_o_gabarito(tmp_path):
    # Caso 3: 11-03 e 11-04 fecham; o histórico de D = 11-05 dá os números do gabarito.
    _top_1103(tmp_path)
    _top_1104(tmp_path)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 4), FIM, AGORA)
    assert avisos == []

    resultado_1104 = _ler(tmp_path, "2026-11-04.resultado.json")
    assert resultado_1104["pregao_base"] == "2026-11-03"
    assert resultado_1104["acertos_dia"] == 2
    assert resultado_1104["acertos_top3"] == 2
    assert resultado_1104["acertos_sombra_modelo_1"] == 2
    assert resultado_1104["acertos_sombra_volatilidade"] == 2

    resultados = pe.ler_resultados(tmp_path)
    historico = pe.montar_historico(
        resultados, date(2026, 11, 5), FIM, "composicao_atual",
        params_teste(acaso_sorteios=10000), AGORA, "2026-11-05T08:00:00-03:00",
    )
    resumo = historico["resumo"]
    assert resumo["n_dias"] == 2
    assert resumo["periodo_inicio"] == "2026-11-03"
    assert resumo["periodo_fim"] == "2026-11-04"
    assert resumo["taxa_acerto"] == {"valor": 0.5, "status": "ok"}
    assert resumo["acaso_media"]["valor"] == pytest.approx(0.4997400000000001, abs=1e-9)
    assert resumo["acaso_media"]["status"] == "ok"
    assert resumo["acaso_faixa"][0] == pytest.approx(0.4, abs=1e-9)
    assert resumo["acaso_faixa"][1] == pytest.approx(0.6000000000000001, abs=1e-9)
    assert historico["dia"]["data_referencia"] == "2026-11-04"
    assert historico["dia"]["taxa_acumulada"] == {"valor": 0.5, "status": "ok"}


def test_registro_invalido_nao_fecha_nem_descarta(tmp_path):
    # Caso 4: valido_para_historico false -> nenhum arquivo e nenhum aviso.
    _top_1103(tmp_path, valido=False)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 4), FIM, AGORA)
    assert avisos == []
    assert _arquivos(tmp_path) == ["2026-11-03.top.json"]


def test_fim_vazio_nao_fecha_nada(tmp_path):
    # Caso 5: teste final trancado (fim None) -> nenhum arquivo, mesmo com registro válido.
    _top_1103(tmp_path)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 4), None, AGORA)
    assert avisos == []
    assert _arquivos(tmp_path) == ["2026-11-03.top.json"]


def test_pregao_previsto_que_nao_houve_vira_descartado(tmp_path):
    # Caso 6: D' = 11-25 fora do calendário, com pregão 11-26 depois -> descartado nao_houve_pregao.
    cal = [date(2026, 11, 24), date(2026, 11, 26)]
    _escrever_top(tmp_path, "2026-11-25", "2026-11-24", RANKING_1103, SOMBRA_M1_1103, SOMBRA_VOL)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), cal, date(2026, 11, 26), FIM, AGORA)
    assert avisos == ["pregão previsto 2026-11-25 não houve; dia descartado"]
    descartado = _ler(tmp_path, "2026-11-25.descartado.json")
    assert descartado["data_referencia"] == "2026-11-25"
    assert descartado["motivo"] == "nao_houve_pregao"
    assert descartado["descartado_em"] == "2026-11-04T09:00:00-03:00"
    assert not (tmp_path / "2026-11-25.resultado.json").exists()


def test_pregao_previsto_que_nao_houve_sem_pregao_depois_espera(tmp_path):
    # Caso 6b (regra 5): D' fora do calendário e nenhum pregão depois -> nada é feito.
    cal = [date(2026, 11, 24)]
    _escrever_top(tmp_path, "2026-11-25", "2026-11-24", RANKING_1103, SOMBRA_M1_1103, SOMBRA_VOL)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), cal, date(2026, 11, 25), FIM, AGORA)
    assert avisos == []
    assert _arquivos(tmp_path) == ["2026-11-25.top.json"]


def test_registro_com_previsto_depois_de_t_ainda_nao_fecha(tmp_path):
    # Caso 6c: D' = 11-25 com t = 11-24 (D' > t) -> nada.
    cal = [date(2026, 11, 24)]
    _escrever_top(tmp_path, "2026-11-25", "2026-11-24", RANKING_1103, SOMBRA_M1_1103, SOMBRA_VOL)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), cal, date(2026, 11, 24), FIM, AGORA)
    assert avisos == []
    assert _arquivos(tmp_path) == ["2026-11-25.top.json"]


def test_pregao_base_diferente_vira_descartado(tmp_path):
    # Caso 7: D' = 11-26 com base 11-24, mas o pregão anterior a 11-26 no calendário é 11-25.
    cal = [date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 26)]
    _escrever_top(tmp_path, "2026-11-26", "2026-11-24", RANKING_1103, SOMBRA_M1_1103, SOMBRA_VOL)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), cal, date(2026, 11, 26), FIM, AGORA)
    assert avisos == [
        "top 5 de 2026-11-26 foi gerado com pregão base 2026-11-24, "
        "mas o pregão anterior a 2026-11-26 foi 2026-11-25; dia descartado",
    ]
    descartado = _ler(tmp_path, "2026-11-26.descartado.json")
    assert descartado["motivo"] == "pregao_base_diferente"
    assert not (tmp_path / "2026-11-26.resultado.json").exists()


def test_ação_sem_preco_deixa_resultado_incompleto(tmp_path):
    # Caso 8: EEEE3 sem preço em 11-03 -> resultado_incompleto true e acertos_dia 2.
    _top_1103(tmp_path)
    pe.fechar_pendentes(tmp_path, _precos_gabarito(eeee3_sem_preco_1103=True), CAL, date(2026, 11, 4), FIM, AGORA)
    resultado = _ler(tmp_path, "2026-11-03.resultado.json")
    assert resultado["resultado_incompleto"] is True
    assert resultado["acertos_dia"] == 2
    assert resultado["resultado"][4]["ticker"] == "EEEE3"
    assert resultado["resultado"][4]["superou"] is None
    assert resultado["resultado"][4]["retorno"] == {"valor": None, "status": "indisponivel"}


def test_registro_do_pregao_de_hoje_e_ignorado(tmp_path):
    # Caso 9: D' = t + 1 (o top de hoje) -> ignorado, sem arquivo e sem aviso.
    _escrever_top(tmp_path, "2026-11-04", "2026-11-03", RANKING_1104, SOMBRA_M1_1104, SOMBRA_VOL)
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), CAL, date(2026, 11, 3), FIM, AGORA)
    assert avisos == []
    assert _arquivos(tmp_path) == ["2026-11-04.top.json"]


def test_descartado_nunca_e_sobrescrito(tmp_path):
    # Uso único: um descartado já existente não muda e não gera aviso novo.
    cal = [date(2026, 11, 24), date(2026, 11, 26)]
    _escrever_top(tmp_path, "2026-11-25", "2026-11-24", RANKING_1103, SOMBRA_M1_1103, SOMBRA_VOL)
    (tmp_path / "2026-11-25.descartado.json").write_text('{"motivo": "antigo"}', encoding="utf-8")
    avisos = pe.fechar_pendentes(tmp_path, _precos_gabarito(), cal, date(2026, 11, 26), FIM, AGORA)
    assert avisos == []
    assert (tmp_path / "2026-11-25.descartado.json").read_text(encoding="utf-8") == '{"motivo": "antigo"}'


def test_listar_registros_top_so_nomes_certos_ordenados(tmp_path):
    _escrever_top(tmp_path, "2026-11-04", "2026-11-03", RANKING_1104, SOMBRA_M1_1104, SOMBRA_VOL)
    _top_1103(tmp_path)
    (tmp_path / "2026-11-03.resultado.json").write_text("{}", encoding="utf-8")
    (tmp_path / "lixo.top.json").write_text("{}", encoding="utf-8")
    (tmp_path / "2026-13-45.top.json").write_text("{}", encoding="utf-8")
    assert pe.listar_registros_top(tmp_path) == [date(2026, 11, 3), date(2026, 11, 4)]
    assert pe.listar_registros_top(tmp_path / "nao_existe") == []


def test_gravar_descartado_e_de_uso_unico(tmp_path):
    assert pe.gravar_descartado(tmp_path, date(2026, 11, 25), "nao_houve_pregao", AGORA) is True
    antes = (tmp_path / "2026-11-25.descartado.json").read_bytes()
    assert pe.gravar_descartado(tmp_path, date(2026, 11, 25), "pregao_base_diferente", AGORA) is False
    assert (tmp_path / "2026-11-25.descartado.json").read_bytes() == antes
