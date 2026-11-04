"""Testes da página do painel (processamento/painel/pagina.html): marcadores, ids, textos e regras de segurança."""

from __future__ import annotations

import re
from pathlib import Path

from processamento.painel.acoes import ACOES
from processamento.painel.ajuda import AJUDA
from processamento.painel.saude import _CARTOES

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
        "Diagnóstico completo",
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
    for trecho in ["Espera a coleta do dia", "Gera todos os pacotes inteiros", "Confere o banco da coleta", "Roda os testes automáticos", "Roda a rotina, a carga completa e o publicador da API"]:
        assert trecho in texto, trecho
    assert "/api/acao/iniciar" in texto
    assert "/api/acao/parar" in texto


def test_seis_abas_com_ancoras_na_ordem():
    texto = _pagina()
    abas = ["hoje", "coleta", "diagnostico", "execucoes", "api", "experimento"]
    posicoes = []
    for aba in abas:
        assert f'href="#{aba}" data-aba-link="{aba}"' in texto, aba
        assert f'data-aba="{aba}"' in texto, aba
        posicoes.append(texto.index(f'data-aba-link="{aba}"'))
    assert posicoes == sorted(posicoes)
    assert "aria-current" in texto
    assert "hashchange" in texto


def test_blocos_na_ordem_das_abas():
    texto = _pagina()
    ordem = ['id="aba-hoje"', 'id="hoje-situacao"', 'id="hoje-fluxo"', 'id="agora"', 'id="novidades"', 'id="saude"', 'id="mercado"', 'id="dia-atipico"', 'id="aba-coleta"', 'id="coleta-etapas"', 'id="aba-diagnostico"', 'id="saude-completa"', 'id="aba-execucoes"', 'id="historico"', 'id="linha-tempo"', 'id="comandos"', 'id="run"', 'id="testes"', 'id="aba-api"', 'id="api-cartao"', 'id="aba-experimento"', 'id="experimento"']
    posicoes = [texto.index(trecho) for trecho in ordem]
    assert posicoes == sorted(posicoes)


def test_tela_inteira_e_breakpoints():
    texto = _pagina()
    assert "max-width:1180px" not in texto
    assert 'class="two"' not in texto
    for trecho in [
        "max-width:1240px",
        "min-height:44px",
        "@media (max-width:599px)",
        "container-type:inline-size",
        "@container (max-width:1100px)",
    ]:
        assert trecho in texto, trecho


def test_logo_e_favicon_sem_link_literal():
    texto = _pagina()
    for trecho in [
        "Painel do Processamento",
        'id="logo-ic"',
        'createElement("link")',
        '"data:image/svg+xml,"',
        "XMLSerializer",
        'link.rel = "icon"',
    ]:
        assert trecho in texto, trecho
    assert "<link" not in texto


# ---------------------------------------------------------------- Fase 5b: ajuda ("?"), resumo, "O que fazer", tempos


def test_ids_de_ajuda_batem_com_o_dicionario():
    texto = _pagina()
    estaticos = set(re.findall(r'data-ajuda="([a-z0-9_]+)"', texto))
    literais = set(re.findall(r'botaoAjuda\("([a-z0-9_]+)"\)', texto))
    dinamicos = {"saude_" + c[0] for c in _CARTOES} | {"saude_coerencia_mercado"} | {"acao_" + a for a in ACOES}
    assert estaticos | literais | dinamicos == set(AJUDA)
    assert len(estaticos) == 17
    assert 'botaoAjuda("saude_" + id)' in texto
    assert 'botaoAjuda("acao_" + id)' in texto


def test_botoes_de_ajuda_estaticos_acessiveis():
    texto = _pagina()
    tags = re.findall(r'<button class="ajuda-btn"[^>]*>', texto)
    assert len(tags) == 17
    for tag in tags:
        for trecho in ['type="button"', 'aria-label="Ajuda"', 'aria-expanded="false"', 'aria-controls="ajuda-caixa"', " hidden"]:
            assert trecho in tag, (trecho, tag)


def test_caixa_de_ajuda_teclado_e_resumo():
    texto = _pagina()
    for trecho in [
        'id="ajuda-caixa"',
        'role="tooltip"',
        '"aria-describedby"',
        '"Escape"',
        "pointerover",
        "pointerout",
        "isConnected",
        '"O que fazer: "',
        "data-fazer",
        'id="resumo-frase"',
        'id="resumo-lista"',
        "irPara(",
        "scrollIntoView",
        "preventScroll",
        ".resumo",
        ".tempos",
        ".ajuda",
        '"Tempo: "',
        '"leva "',
    ]:
        assert trecho in texto, trecho


def test_frase_do_dia_e_glossario_pelo_servidor():
    texto = _pagina()
    assert '<p class="dia" id="frase-dia" hidden></p>' in texto
    assert "(d.visao || {}).dia" in texto
    assert '<details id="glossario" hidden>' in texto
    assert "Palavras do painel" in texto
    assert 'id="glossario-lista"' in texto
    assert "(d.visao || {}).glossario" in texto


def test_impressao_esconde_ajuda_e_abre_blocos():
    texto = _pagina()
    assert "@media print" in texto
    for trecho in [".ajuda-btn", "#comandos .actions", "#run", "#erro-rede"]:
        assert trecho in texto, trecho
    assert 'addEventListener("beforeprint"' in texto
    assert 'addEventListener("afterprint"' in texto


def test_calendario_apaga_dias_futuros_e_cartao_alinhado_no_topo():
    texto = (Path(__file__).resolve().parents[1] / "processamento" / "painel" / "pagina.html").read_text(encoding="utf-8")
    assert ".cal .d.fut{" in texto
    assert 'classes.push("fut")' in texto
    assert "celulaDia(dia, hojeIso)" in texto
    assert "align-content:start}" in texto


# ---------------------------------------------------------------- Fase F9: fluxo de 5 estágios, dia atípico, novidades, afetadas


def test_fluxo_cinco_estagios_api_banco_e_tempo():
    texto = _pagina()
    for trecho in [
        '"fluxo-banco"',
        '"fluxo-api"',
        'botaoAjuda("api")',
        'botaoAjuda("banco_api")',
        'botaoAjuda("tempo_api")',
        'botaoAjuda("etapas_coleta")',
        "coleta_etapas",
        "3 · Banco da API",
        "4 · API",
        "5 · Interface",
        "fluxo.replaceChildren(coleta, seta(), processamento, seta(), banco, seta(), apiNo, seta(), interfaceNo)",
        "repeat(auto-fit,minmax(170px,1fr))",
        "@container (max-width:1100px)",
        ".flow .arrow{display:none}",
    ]:
        assert trecho in texto, trecho
    assert "http://" not in texto and "https://" not in texto


def test_dia_atipico_novidades_e_afetadas():
    texto = _pagina()
    for trecho in [
        'id="dia-atipico"',
        'botaoAjuda("dia_atipico")',
        'data-ajuda="o_que_mudou"',
        'id="novidades"',
        "afetadas",
        "e mais ",
        "ver todas",
        'data-fazer="dia-atipico"',
        'dia_atipico',
    ]:
        assert trecho in texto, trecho


def test_botao_dia_primeiro_em_acoes_e_origem_da_data():
    texto = _pagina()
    assert '["dia", "botoes-hoje"]' in texto
    assert 'if (id !== "rotina" && id !== "dia") return "";' in texto
    assert '["dia", "Roda a rotina, a carga completa e o publicador da API' in texto


def test_sem_wordpress_link_de_validacao_nem_commit():
    texto = _pagina().lower()
    for proibido in ["wordpress", "link-validacao", "commit"]:
        assert proibido not in texto, proibido


def test_paleta_clara_escura_e_fontes_do_sistema():
    texto = _pagina()
    for trecho in ["--bg:#F5F6F8", "--bg:#0F1115", "--log:#0B0D11", "system-ui", "ui-monospace"]:
        assert trecho in texto, trecho


def test_nenhum_id_igual_a_nome_de_aba():
    texto = _pagina()
    for nome in ["hoje", "coleta", "diagnostico", "execucoes", "api"]:
        assert f'id="{nome}"' not in texto, nome


def test_abas_escondidas_com_hidden_e_print_mostra_tudo():
    # [data-aba]{display:grid} não pode anular o atributo hidden das abas que não estão abertas.
    texto = _pagina()
    assert "[data-aba][hidden]{display:none}" in texto
    assert "[data-aba][hidden]{display:block!important}" in texto


# ---------------------------------------------------------------- Fase F2: tela Hoje (situação, fluxo, progresso, grade)


def test_hoje_situacao_fluxo_progresso_e_grade_presentes():
    texto = _pagina()
    for trecho in [
        'id="hoje-situacao"',
        'id="hero-icone"',
        'id="hero-botao"',
        'id="hero-proxima"',
        'id="fluxo-nos"',
        'id="fluxo-rodape"',
        'id="progresso-dia"',
        'id="progresso-barras"',
        'id="progresso-restante"',
        'id="fluxo-detalhe"',
        'id="mercado"',
        'id="mercado-linha"',
        'id="mercado-coerencia"',
        "Situação de hoje",
        "Fluxo do dia",
        "O que mudou desde ontem",
        "Mercado no último pregão",
        "Rodar o dia completo",
        "Próxima execução automática",
        'href="#diagnostico"',
        "fluxo_nos",
        ".progresso",
        "polyline",
    ]:
        assert trecho in texto, trecho


def test_hoje_sem_numero_do_prototipo_escrito_a_mao():
    assert "167.922" not in _pagina()
