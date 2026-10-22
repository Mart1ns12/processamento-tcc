"""Testes de processamento/exclusoes.py: leitura e validação do exclusoes.yaml.

Os arquivos de teste ficam em tmp_path. Nenhum teste usa banco ou rede.
"""

import pytest

from processamento.exclusoes import CAMINHO_EXCLUSOES, ErroExclusoes, Exclusoes, carregar_exclusoes


def _escrever(tmp_path, texto: str) -> str:
    caminho = tmp_path / "exclusoes.yaml"
    caminho.write_text(texto, encoding="utf-8")
    return str(caminho)


def test_arquivo_real_tem_as_exclusoes_decididas():
    exc = carregar_exclusoes(str(CAMINHO_EXCLUSOES))
    assert set(exc.tickers_excluidos) == {"CRFB3", "SRNA3", "STBP3"}
    assert set(exc.cnpjs_sem_balanco) == {"03847461000192", "06057223000171"}


def test_cnpj_sem_aspas_recusado(tmp_path):
    caminho = _escrever(tmp_path, "cnpjs_sem_balanco:\n  3847461000192: x\n")
    with pytest.raises(ErroExclusoes, match="aspas"):
        carregar_exclusoes(caminho)


def test_ticker_em_minusculas_recusado(tmp_path):
    caminho = _escrever(tmp_path, 'tickers_excluidos:\n  "petr4": motivo\n')
    with pytest.raises(ErroExclusoes, match="petr4"):
        carregar_exclusoes(caminho)


def test_chave_de_topo_desconhecida_recusada(tmp_path):
    caminho = _escrever(tmp_path, "outra:\n  X: y\n")
    with pytest.raises(ErroExclusoes, match="outra"):
        carregar_exclusoes(caminho)


def test_arquivo_vazio_devolve_exclusoes_vazias(tmp_path):
    exc = carregar_exclusoes(_escrever(tmp_path, ""))
    assert exc == Exclusoes()
    assert exc.tickers_excluidos == {}
    assert exc.cnpjs_sem_balanco == {}


def test_motivo_vazio_recusado(tmp_path):
    caminho = _escrever(tmp_path, 'tickers_excluidos:\n  CRFB3: ""\n')
    with pytest.raises(ErroExclusoes):
        carregar_exclusoes(caminho)
