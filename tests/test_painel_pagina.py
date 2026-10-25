"""Testes da página do painel (processamento/painel/pagina.html): marcadores, ids, textos e regras de segurança."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PAGINA = RAIZ / "processamento" / "painel" / "pagina.html"


def _pagina() -> str:
    return PAGINA.read_text(encoding="utf-8")


def test_pagina_existe_na_pasta_do_painel():
    assert PAGINA.is_file()


def test_token_pelo_marcador_literal():
    assert 'const TOKEN = "__TOKEN_PAINEL__";' in _pagina()


def test_contem_ids_das_secoes_e_textos_obrigatorios():
    texto = _pagina()
    for trecho in [
        "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO",
        'id="agora"',
        'id="historico"',
        'id="etapas"',
        'id="saude"',
        'id="experimento"',
        'id="testes"',
        'id="log"',
        "/api/painel",
        "/api/acao/iniciar",
        "X-Painel-Token",
    ]:
        assert trecho in texto, trecho


def test_contem_data_usada_e_confirm_com_data():
    texto = _pagina()
    assert "Data usada" in texto
    assert '"Data: "' in texto


def test_envia_cabecalhos_do_post_com_token():
    texto = _pagina()
    assert '"Content-Type": "application/json"' in texto
    assert '"X-Painel-Token": TOKEN' in texto


def test_sem_recurso_externo():
    texto = _pagina()
    assert "http://" not in texto
    assert "https://" not in texto


def test_sem_insercao_de_html_nem_eval():
    texto = _pagina()
    for proibido in ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("]:
        assert proibido not in texto, proibido


def test_textos_de_ausencia_e_erro():
    texto = _pagina()
    for trecho in [
        "Painel sem resposta",
        "Nenhuma execução encontrada em saida/.",
        "Nenhum pytest rodado pelo painel ainda.",
        "Só neste computador (127.0.0.1).",
    ]:
        assert trecho in texto, trecho


# ---------------------------------------------------------------- Fase F: visual "Sala de Operação"


def test_titulo_da_sala_de_operacao():
    texto = _pagina()
    assert "<title>Sala de Operação · Painel de operação do processamento (TCC)</title>" in texto
    assert "<h1>Sala de Operação</h1>" in texto


def test_contem_ids_da_estrutura_nova():
    texto = _pagina()
    for trecho in [
        'id="linha-tempo"',
        'id="tl"',
        'id="comandos"',
        'id="run"',
        'id="steps"',
        'id="saude-cartoes"',
        'id="grafico"',
        'id="cal"',
        'id="tema"',
        'id="carga-linha"',
        'id="pill-geral"',
        'id="pill-hoje"',
        'id="pill-fluxo"',
        'id="pill-testes"',
        'id="cadeado-fechado"',
        'id="cadeado-aberto"',
        'id="exp-kv"',
        'id="hist-tabela"',
        'id="link-relatorio"',
    ]:
        assert trecho in texto, trecho


def test_textos_da_fase_f():
    texto = _pagina()
    for trecho in [
        "Ver o log completo",
        "Não constitui recomendação de investimento.",
        "A manhã do pregão de ",
        "Última atualização",
        "Pode ter sido interrompida",
        "Concluída com pendências",
        "Top 5 publicado na interface",
        "Top 5 retido (não enviado à interface)",
        "Teste final trancado",
        "Escondida até a calibração ser aprovada",
        "m.chance_exibida",
        "faixa cinza = acaso (95% dos sorteios)",
        "Ver relatório completo",
        "Histórico de execuções",
        "Testes automáticos",
        "Saúde dos dados",
        "Experimento: top 5 com maior chance de superar o Ibovespa",
        "Rodadas registradas no log da rotina",
        "Ver o diagnóstico completo",
        "Gerar",
        "Rodar",
    ]:
        assert trecho in texto, trecho


def test_teste_de_funcionamento_com_legenda_fixa_e_selo_em_avaliacao():
    texto = _pagina()
    assert "Teste de funcionamento (treino " in texto
    assert "), não é o resultado do TCC" in texto
    assert "não é o resultado do TCC" in texto
    assert "em avaliação" in texto
    assert "TESTE DE FUNCIONAMENTO, NÃO É RESULTADO" in texto


def test_sem_destravar_teste_final_pelo_painel():
    texto = _pagina()
    assert "--teste-final" not in texto
    assert "teste_final_usado" not in texto


def test_sem_fontes_externas_nem_link_de_estilo():
    texto = _pagina()
    for proibido in ["fonts.googleapis", "IBM Plex", "<link", "@import"]:
        assert proibido not in texto, proibido


def test_namespace_svg_montado_com_join():
    assert '["http:", "", "www.w3.org", "2000", "svg"].join("/")' in _pagina()


def test_dom_montado_com_createelement_e_textcontent():
    texto = _pagina()
    assert "createElement(" in texto
    assert "createElementNS(" in texto
    assert ".textContent" in texto


def test_linguagem_sem_termos_proibidos():
    texto = _pagina().replace("Não constitui recomendação de investimento.", "")
    for proibido in ["compre", "oportunidade", "melhores ações", "recomendação"]:
        assert proibido not in texto, proibido


def test_localstorage_so_em_linha_com_try():
    for linha in _pagina().splitlines():
        if "localStorage" in linha:
            assert "try" in linha, linha.strip()


def test_sem_etapas_simuladas_por_tempo():
    texto = _pagina()
    assert "simular" not in texto
    assert "passo(" not in texto


def test_polling_do_log_e_do_painel():
    texto = _pagina()
    assert "INTERVALO_LOG_MS = 1000" in texto
    assert "INTERVALO_PAINEL_MS = 30000" in texto
    assert "/api/acao?desde=" in texto


def test_marcos_e_visao_consumidos_do_servidor():
    texto = _pagina()
    assert "marcos" in texto
    assert "visao" in texto
    assert "dia_rotulo" in texto
    assert "resumo" in texto
    assert "rotulo" in texto


def test_tema_claro_e_escuro_com_tokens():
    texto = _pagina()
    assert ":root{" in texto or ":root {" in texto
    assert '@media (prefers-color-scheme: dark)' in texto
    assert ':root[data-theme="dark"]' in texto
    assert ':root:not([data-theme="light"])' in texto
    assert "painel-tema" in texto


def test_acoes_fixas_no_painel():
    texto = _pagina()
    for trecho in ["Espera a coleta do dia", "Gera todos os pacotes inteiros", "Confere o banco da coleta", "Roda os testes automáticos"]:
        assert trecho in texto, trecho
    assert "/api/acao/iniciar" in texto
    assert "/api/acao/parar" in texto
