import re
from pathlib import Path

from processamento.painel import ajuda
from processamento.painel.ajuda import (
    AJUDA, CAMPOS, GLOSSARIO, O_QUE_FAZER, campos_do_texto, montar_ajuda,
)

IDS = {"resumo", "fluxo", "coleta", "processamento", "interface", "pacotes", "contrato", "rodada",
       "carga_vs_rotina", "linha_tempo", "prazo", "folga", "saude", "saude_contrato",
       "saude_quantidade_acoes", "saude_retornos", "saude_lacunas", "saude_horario_noticias",
       "saude_cobertura", "experimento", "teste_funcionamento", "cadeado", "modelo", "top5_retido",
       "chance", "modelo_sombra", "grafico", "faixa_acaso", "historico", "testes", "acao_rotina",
       "acao_carga", "acao_diagnostico", "acao_testes"}
CHAVES_FAZER = {"saude_contrato", "saude_quantidade_acoes", "saude_retornos", "saude_lacunas",
                "saude_horario_noticias", "saude_cobertura", "saude_sem_dados", "saude_sem_diagnostico",
                "coleta_warn", "coleta_bad", "rotina_falhou", "rotina_parcial", "rotina_interrompida",
                "sem_rotina", "atraso_prazo", "calendario_erro", "testes_falhas", "testes_interrompidos",
                "trava_abandonada"}
TERMOS_GLOSSARIO = ["Pregão", "Ibovespa", "Indicador", "Indisponível", "Histórico insuficiente",
                    "Pacote", "Rodada", "Diagnóstico", "Walk-forward", "Faixa do acaso", "Calibração",
                    "P/L", "P/VP", "Payout", "Dividend yield"]
PROIBIDAS = ["compre", "oportunidade", "melhores ações", "recomendação", "http", "select"]


def _todos():
    return [t for par in AJUDA.values() for t in par] + list(O_QUE_FAZER.values())


def _sem_placeholders_e_excecoes(texto):
    # "top 5" (nome do produto), "B3" (nome da bolsa) e "95%" (definição da faixa) não são dados.
    sem = re.sub(r"\{[a-z_]+\}", "", texto)
    return re.sub(r"(?i)top 5", "", sem).replace("B3", "").replace("95%", "")


def test_ids_e_chaves_completos():
    assert set(AJUDA) == IDS
    for titulo, texto in AJUDA.values():
        assert isinstance(titulo, str) and titulo
        assert isinstance(texto, str) and texto
    assert set(O_QUE_FAZER) == CHAVES_FAZER


def test_campos_dos_textos_estao_em_CAMPOS():
    usados = set()
    for _, texto in AJUDA.values():
        assert campos_do_texto(texto) <= CAMPOS, texto
        usados |= campos_do_texto(texto)
    assert usados == CAMPOS
    for texto in O_QUE_FAZER.values():
        assert campos_do_texto(texto) == set(), texto


def test_nenhum_numero_escrito_a_mao():
    for t in _todos():
        s = _sem_placeholders_e_excecoes(t)
        assert not re.search(r"\d", s), t


def test_sem_palavras_proibidas():
    for t in _todos():
        baixo = t.lower()
        for palavra in PROIBIDAS:
            assert palavra not in baixo, (palavra, t)


def test_experimento_deixa_claro_que_e_teste():
    assert "teste de funcionamento" in AJUDA["experimento"][1]
    assert "não é o resultado do TCC" in AJUDA["experimento"][1]
    # Título do cartão (posição 0): o texto de "Teste de funcionamento" não repete a expressão.
    assert "teste de funcionamento" in AJUDA["teste_funcionamento"][0].lower()
    assert "nenhum botão que destranque" in AJUDA["cadeado"][1]


def test_montar_ajuda_preenche_campos():
    a = montar_ajuda({"prazo": "09:45", "prazo_tardio": "12:00", "limite_historico": "10:00",
                      "abertura": None, "lixo": "x"})
    assert set(a) == IDS
    assert a["prazo"] == {
        "titulo": "Prazo da rotina",
        "texto": ('É o horário-limite para a coleta entregar os dados: 09:45, lido do arquivo de configuração '
                  '(parametros.yaml). Sem entrega até lá, a rodada é registrada como "falhou" e só o arquivo '
                  'da rodada é gravado, para o site avisar que os dados são do pregão anterior. A rotina '
                  'continua tentando até 12:00, mas um top 5 feito depois de 10:00 não conta para o histórico '
                  'do experimento.'),
    }
    assert "o prazo da rotina (09:45) e a abertura da bolsa (sem dados)" in a["linha_tempo"]["texto"]


def test_montar_ajuda_sem_chaves_no_resultado():
    assert all("{" not in v["texto"] and "}" not in v["texto"] for v in montar_ajuda({}).values())
    assert all("{" not in v["texto"] and "}" not in v["texto"] for v in montar_ajuda(None).values())


def test_codigo_do_modulo_sem_termos_proibidos_no_painel():
    fonte = Path(ajuda.__file__).read_text(encoding="utf-8")
    for termo in ["SELECT", ".env", "executar_leitura"]:
        assert termo not in fonte, termo


def test_glossario_tem_15_itens_na_ordem():
    assert len(GLOSSARIO) == 15
    assert [termo for termo, _ in GLOSSARIO] == TERMOS_GLOSSARIO


def test_glossario_sem_digitos():
    for termo, texto in GLOSSARIO:
        for t in (termo, texto):
            assert not re.search(r"\d", _sem_placeholders_e_excecoes(t)), t


def test_glossario_sem_palavras_proibidas():
    for termo, texto in GLOSSARIO:
        for t in (termo, texto):
            baixo = t.lower()
            for palavra in PROIBIDAS:
                assert palavra not in baixo, (palavra, t)
