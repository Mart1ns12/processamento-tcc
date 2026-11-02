"""Testes do protocolo: relatório (protocolo_relatorio.py) com resultado montado à mão, e execução (protocolo_execucao.py).
Tudo em tmp_path e com dataset sintético. Nada de banco, rede ou modelo real."""

import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fabrica_protocolo import doc_de_teste, lim_teste
from fabrica_treino import dataset_sintetico, gravar_versoes, params_teste
from processamento import fontes
from processamento.experimento import modelos, preparacao, protocolo, treino, validacao
from processamento.experimento import protocolo_execucao as execucao
from processamento.experimento import protocolo_registro as reg
from processamento.experimento.protocolo import ANOS_PROTOCOLO, LIMITES, ORDEM_TESTES
from processamento.experimento.protocolo_relatorio import ROTULOS, gerar_relatorio


def _medidas(ganho=0.001):
    return {
        "n_dias_auc": 100,
        "auc_base": 0.52,
        "auc_candidato": 0.521,
        "ganho": ganho,
        "ic": (-0.002, 0.004),
        "ganho_por_ano": {a: ganho for a in ANOS_PROTOCOLO},
        "n_dias_por_ano": {a: 17 for a in ANOS_PROTOCOLO},
        "top": {"k": 5, "n_dias": 100, "acertos_base": 200, "acertos_candidato": 199,
                "taxa_base": 0.4, "taxa_candidato": 0.398, "queda_pontos": 0.2},
        "regime": {"ganho": ganho, "por_ano": {2023: 0.002, 2024: 0.001}},
    }


def _resultado(status="valida", motivos=(), bloco_e=False, **trocas):
    testes = {}
    for nome in ORDEM_TESTES:
        testes[nome] = {
            "base": "modelo 3" if nome == "bloco_e" else "modelo 1",
            "medidas": _medidas(),
            "avaliacao": {"c1": False, "c2": False, "c3": False, "c4": True,
                          "c5": False if nome == "bloco_e" else None, "aprovado": False},
        }
    resultado = {
        "rodada": 1, "data_rodada": "2026-11-02", "motivo": "", "modelo_oficial": False,
        "status": status, "motivos": list(motivos), "adotados": [], "bloco_e_aprovado": False,
        "n_testes": 6,
        "identificacao": {
            "sha256_dataset": "a" * 64, "arquivo_dataset": "todas.csv", "versao_preparacao": 3,
            "periodo_ini": "2021-04-01", "periodo_fim": "2025-12-31", "n_pregoes": 1200, "n_linhas": 90000,
            "n_dobras": 60, "semente": 20261023, "sha_parametros": "b" * 64, "sha_regras": "c" * 64,
            "sha_codigo": "d" * 64, "versoes": {"xgboost": "3.4.1"}, "hiperparametros": {"max_depth": 3},
        },
        "passo_0": {
            "tentativas": [{"etapa": "modelo_1", "descricao": "bloco preco_contexto", "auc_medio": 0.51, "aceito": False}],
            "colunas_modelo_1": ["ret_1d", "vol_20d"], "colunas_modelo_3": ["ret_1d", "vol_20d", "noticias_dia_qtd"],
        },
        "testes": testes,
        "conjunto": {"situacao": "nao_executado", "motivo": "controle aprovado", "blocos": [],
                     "medidas": None, "avaliacao": None},
        "colunas_congeladas": None,
        "cobertura": {a: {"bloco_a": 1.0, "bloco_e": (0.0 if a == 2023 else 0.9)} for a in ANOS_PROTOCOLO},
        "sha_resultado": "e" * 64,
        "repete_rodada": None,
        "reproduziu": None,
    }
    resultado.update(trocas)
    return resultado


def _historico(*eventos):
    return list(eventos)


def test_relatorio_mostra_controle_e_os_cinco_blocos_mesmo_reprovados():
    texto = gerar_relatorio(_resultado(), _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1}))
    for nome in ORDEM_TESTES:
        assert ROTULOS[nome] in texto


def test_relatorio_rodada_invalida_diz_nenhum_bloco_adotado():
    resultado = _resultado(status="invalida", motivos=["controle aprovado"])
    texto = gerar_relatorio(resultado, _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1}))
    assert "nenhum bloco adotado" in texto.lower()
    assert "RODADA INVÁLIDA" in texto


def test_relatorio_sem_nan_e_ausencia_vira_nd():
    resultado = _resultado()
    resultado["identificacao"]["sha256_dataset"] = None
    resultado["testes"]["bloco_b"]["medidas"]["ic"] = (None, None)
    resultado["testes"]["bloco_b"]["medidas"]["ganho"] = float("nan")
    texto = gerar_relatorio(resultado, _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1}))
    assert not re.search(r"\bnan\b", texto, re.IGNORECASE)
    assert "n/d" in texto


def test_relatorio_criterio_5_nao_se_aplica_quando_none():
    texto = gerar_relatorio(_resultado(), _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1}))
    assert "não se aplica" in texto


def test_relatorio_mostra_2023_como_so_relato_e_coluna_2024():
    texto = gerar_relatorio(_resultado(), _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1}))
    assert "Ganho em 2024 (critério 5)" in texto
    assert "Ganho em 2023 (só relato)" in texto


def test_relatorio_rodada_sem_fim_sai_interrompida():
    historico = _historico(
        {"tipo": "protocolo", "evento": "inicio", "rodada": 1, "motivo": ""},
        {"tipo": "protocolo", "evento": "inicio", "rodada": 2, "motivo": "teste"},
    )
    texto = gerar_relatorio(_resultado(rodada=2, motivo="teste"), historico)
    linha_1 = next(l for l in texto.splitlines() if l.startswith("| 1 |"))
    assert "interrompida" in linha_1


def test_relatorio_reproduziu_falso_fica_em_destaque():
    historico = _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1})
    texto = gerar_relatorio(_resultado(repete_rodada=1, reproduziu=False), historico)
    assert "NÃO REPRODUZIU" in texto


def test_relatorio_cobertura_bloco_e_2023_zero_por_cento():
    texto = gerar_relatorio(_resultado(), _historico({"tipo": "protocolo", "evento": "inicio", "rodada": 1}))
    linha = next(l for l in texto.splitlines() if l.startswith("| bloco_e |"))
    colunas = [c.strip() for c in linha.split("|")[1:-1]]
    assert colunas[1 + ANOS_PROTOCOLO.index(2023)] == "0.0%"


# ---------- Cenários de decisão: previsor e medição falsos, sem treino ----------

def _medidas_fake(ganho=0.001, ic=(0.001, 0.02), regime=None):
    regime = ganho if regime is None else regime
    return {
        "n_dias_auc": 100, "auc_base": 0.5, "auc_candidato": 0.5, "ganho": ganho, "ic": ic,
        "ganho_por_ano": {a: ganho for a in ANOS_PROTOCOLO},
        "n_dias_por_ano": {a: 10 for a in ANOS_PROTOCOLO},
        "top": {"k": 5, "n_dias": 100, "acertos_base": 200, "acertos_candidato": 200,
                "taxa_base": 0.4, "taxa_candidato": 0.4, "queda_pontos": 0.0},
        "regime": {"ganho": regime, "por_ano": {2023: regime, 2024: regime}},
    }


def _tabela(ganhos=None):
    ganhos = ganhos or {}
    tab = {nome: _medidas_fake(ganhos.get(nome, 0.001)) for nome in ORDEM_TESTES}
    tab["conjunto"] = _medidas_fake(ganhos.get("conjunto", 0.001))
    return tab


def _nome_do_candidato(cand, base):
    extra = set(cand) - set(base)
    for nome, cols in preparacao.BLOCOS_PROTOCOLO.items():
        if extra == set(cols):
            return nome
    return "conjunto"


def _falsos(monkeypatch, tabela, auc=None):
    """Previsor que devolve as colunas (e as registra), medição que responde pela tabela. Nada é treinado."""
    colunas_vistas, hipers, bases = [], [], []

    def prever(prep, dobras, colunas, tipo, params, hiper=None):
        colunas_vistas.append(list(colunas))
        hipers.append(hiper)
        return tuple(colunas)

    def medir(pred_base, cand, semente, lim):
        bases.append((_nome_do_candidato(cand, pred_base), pred_base))
        return tabela[_nome_do_candidato(cand, pred_base)]

    monkeypatch.setattr(treino, "auc_medio_wf", auc or (lambda colunas: 0.5))
    return prever, medir, colunas_vistas, hipers, bases


def _rodar_falso(monkeypatch, tabela, auc=None):
    prever, medir, vistas, hipers, bases = _falsos(monkeypatch, tabela, auc)
    res = execucao.rodar_protocolo(None, [], params_teste(), lim_teste(), prever=prever, medir=medir)
    return res, vistas, hipers, bases


def test_ninguem_aprovado_fica_sem_bloco(monkeypatch):
    res, _, _, _ = _rodar_falso(monkeypatch, _tabela())
    c1 = preparacao.colunas_do_modelo("1", ())
    assert res["aprovados"] == [] and res["adotados"] == []
    assert res["conjunto"]["situacao"] == "nao_se_aplica"
    assert execucao._com_blocos(c1, res["adotados"]) == c1


def test_um_aprovado_adota_sem_conjunto(monkeypatch):
    res, _, _, _ = _rodar_falso(monkeypatch, _tabela({"bloco_b": 0.01}))
    assert res["aprovados"] == ["bloco_b"] and res["adotados"] == ["bloco_b"]
    assert res["conjunto"]["situacao"] == "nao_se_aplica" and res["conjunto"]["medidas"] is None


def test_conjunto_passa_com_colunas_na_ordem(monkeypatch):
    tab = _tabela({"bloco_a": 0.01, "bloco_c": 0.01, "conjunto": 0.012})
    res, _, _, _ = _rodar_falso(monkeypatch, tab)
    c1 = preparacao.colunas_do_modelo("1", ())
    esperado = c1 + preparacao.BLOCOS_PROTOCOLO["bloco_a"] + preparacao.BLOCOS_PROTOCOLO["bloco_c"]
    assert res["adotados"] == ["bloco_a", "bloco_c"]
    assert res["conjunto"]["situacao"] == "executado"
    assert res["conjunto"]["colunas"] == esperado


def test_conjunto_falha_com_ic_tocando_zero(monkeypatch):
    tab = _tabela({"bloco_a": 0.007, "bloco_c": 0.009})
    tab["conjunto"] = _medidas_fake(0.012, ic=(-0.001, 0.02))
    res, _, _, _ = _rodar_falso(monkeypatch, tab)
    assert res["adotados"] == ["bloco_c"]
    assert res["conjunto"]["situacao"] == "executado"
    assert res["conjunto"]["avaliacao"]["aprovado"] is False


def test_controle_aprovado_nao_roda_conjunto(monkeypatch):
    res, _, _, _ = _rodar_falso(monkeypatch, _tabela({"controle": 0.01, "bloco_a": 0.01}))
    assert res["testes"]["controle"]["avaliacao"]["aprovado"] is True
    assert res["conjunto"]["situacao"] == "nao_executado"
    dec = protocolo.decidir_rodada({n: res["testes"][n]["avaliacao"] for n in ORDEM_TESTES}, res["adotados"], False)
    assert dec["status"] == "invalida" and dec["adotados"] == [] and dec["bloco_e_aprovado"] is False


def test_bloco_e_aprovado_usa_modelo_3_como_base(monkeypatch):
    res, _, _, bases = _rodar_falso(monkeypatch, _tabela({"bloco_e": 0.01}))
    c3 = preparacao.colunas_do_modelo("3", ())
    assert res["testes"]["bloco_e"]["avaliacao"]["aprovado"] is True
    assert res["adotados"] == []
    base_e = [b for nome, b in bases if nome == "bloco_e"][0]
    assert tuple(base_e) == tuple(c3)
    dec = protocolo.decidir_rodada({n: res["testes"][n]["avaliacao"] for n in ORDEM_TESTES}, [], False)
    assert dec["bloco_e_aprovado"] is True
    congelado = execucao._congelar(
        {"adotados": [], "bloco_e_aprovado": True, "passo_0": res["passo_0"],
         "identificacao": {"sha256_dataset": "x"}}, params_teste(), 1)
    assert congelado["colunas_3"] == c3
    assert congelado["colunas_3e"] == c3 + preparacao.BLOCOS_PROTOCOLO["bloco_e"]


def test_bloco_e_falha_so_no_criterio_5(monkeypatch):
    tab = _tabela({"bloco_e": 0.006})
    tab["bloco_e"] = _medidas_fake(0.006, ic=(0.001, 0.01), regime=-0.0001)
    res, _, _, _ = _rodar_falso(monkeypatch, tab)
    aval = res["testes"]["bloco_e"]["avaliacao"]
    assert aval["c5"] is False and aval["aprovado"] is False


def test_bloco_a_com_regime_negativo_passa(monkeypatch):
    tab = _tabela({"bloco_a": 0.01})
    tab["bloco_a"] = _medidas_fake(0.01, regime=-0.01)
    res, _, _, _ = _rodar_falso(monkeypatch, tab)
    aval = res["testes"]["bloco_a"]["avaliacao"]
    assert aval["c5"] is None and aval["aprovado"] is True


def test_passo_0_aceita_macro_e_testes_usam_essa_base(monkeypatch):
    res, vistas, _, _ = _rodar_falso(
        monkeypatch, _tabela(), auc=lambda colunas: 0.6 if "exposicao_dolar" in colunas else 0.5
    )
    assert res["passo_0"]["blocos"] == ["macro"]
    c1 = preparacao.colunas_do_modelo("1", ("macro",))
    assert "exposicao_dolar" in res["passo_0"]["colunas_modelo_1"]
    assert list(c1) + preparacao.BLOCOS_PROTOCOLO["bloco_a"] in vistas


def test_hiperparametros_fixos_em_todas_as_chamadas(monkeypatch):
    params = params_teste()
    prever, medir, _, hipers, _ = _falsos(monkeypatch, _tabela())
    execucao.rodar_protocolo(None, [], params, lim_teste(), prever=prever, medir=medir)
    assert hipers and all(h == params.xgboost for h in hipers)


def test_cache_nao_treina_duas_vezes_a_mesma_base():
    chamadas = []

    def previsor(prep, dobras, colunas, tipo, params, hiper=None):
        chamadas.append((tuple(colunas), hiper))
        return "pred"

    cache = execucao.PrevisoesEmCache(previsor, params_teste())
    cache(None, [], ["a", "b"], "xgb", params_teste(), None)
    cache(None, [], ["a", "b"], "xgb", params_teste(), dict(params_teste().xgboost))
    assert len(chamadas) == 1 and cache.treinos == 1


def test_conferir_colunas_recusa_coluna_vazia():
    df = pd.DataFrame({"data": pd.to_datetime(["2025-01-02"] * 2)})
    for colunas in preparacao.BLOCOS_PROTOCOLO.values():
        for coluna in colunas:
            df[coluna] = 1.0
    df["dy_12m"] = float("nan")
    with pytest.raises(execucao.ErroProtocolo, match="dy_12m"):
        execucao.conferir_colunas(df)


# ---------- Ponta a ponta: treina de verdade, com dataset sintético em tmp_path ----------

@pytest.fixture
def amb(tmp_path):
    datasets = tmp_path / "datasets"
    csv = gravar_versoes(datasets, dataset_sintetico(), versoes=("todas",))["todas"]
    docs = tmp_path / "docs"
    doc_de_teste(docs)
    return {"datasets": datasets, "docs": docs, "saida": tmp_path / "saida", "csv": csv,
            "data": treino._data_do_arquivo(csv), "teste_final": tmp_path / "teste_final_usado.json",
            "params": params_teste(), "lim": lim_teste(), "tmp": tmp_path}


def _rodar(amb, motivo="1ª rodada", docs=None, saida=None, params=None):
    return execucao.executar(
        amb["datasets"], docs or amb["docs"], saida or amb["saida"], data=amb["data"], motivo=motivo,
        params=params or amb["params"], lim=amb["lim"], registro_teste_final=amb["teste_final"],
    )


def _main(amb, motivo=None, docs=None, params=None, lim=None, datasets=None):
    argv = ["--data", amb["data"].isoformat(), "--pasta-datasets", str(datasets or amb["datasets"]),
            "--pasta-docs", str(docs or amb["docs"]), "--pasta-saida", str(amb["saida"])]
    if motivo is not None:
        argv += ["--motivo", motivo]
    return execucao.main(argv, params=params or amb["params"], lim=lim or amb["lim"],
                         registro_teste_final=amb["teste_final"])


def _arquivos(pasta):
    return sorted(p.name for p in pasta.iterdir())


def _registro(amb):
    return reg.ler(amb["docs"] / "protocolo_tentativas.jsonl")


def _envenenar(df, mascara):
    """Cópia com as linhas marcadas estragadas (como em test_treino_pipeline): variáveis brutas, notícias e
    colunas do protocolo com sinal trocado, alvo invertido e ret_t1 = 99."""
    saida = df.copy()
    cols = list(dict.fromkeys([*preparacao.COLUNAS_RANK, *preparacao.COLUNAS_PROTOCOLO]))
    saida.loc[mascara, cols] = saida.loc[mascara, cols] * -1
    saida.loc[mascara, "alvo"] = 1 - saida.loc[mascara, "alvo"]
    saida.loc[mascara, "ret_t1"] = 99.0
    return saida


def test_rodada_real_pequena(amb):
    relatorio, status = _rodar(amb)
    assert relatorio == amb["docs"] / "protocolo_rodada_001.md"
    assert status in ("valida", "invalida")
    assert (amb["docs"] / "protocolo_rodada_001.json").exists()
    assert [e["evento"] for e in _registro(amb)] == ["inicio", "fim"]
    assert "bloco_e" in relatorio.read_text(encoding="utf-8")
    assert (amb["saida"] / "rodada-001" / "ganho_diario.csv").exists()


def test_determinismo(amb):
    d2, s2 = amb["tmp"] / "docs2", amb["tmp"] / "saida2"
    doc_de_teste(d2)
    _rodar(amb)
    _rodar(amb, docs=d2, saida=s2)
    j1 = json.loads((amb["docs"] / "protocolo_rodada_001.json").read_text(encoding="utf-8"))
    j2 = json.loads((d2 / "protocolo_rodada_001.json").read_text(encoding="utf-8"))
    assert j1["sha_resultado"] == j2["sha_resultado"]
    assert (amb["saida"] / "rodada-001" / "ganho_diario.csv").read_bytes() == \
        (s2 / "rodada-001" / "ganho_diario.csv").read_bytes()


def test_repeticao_no_mesmo_registro(amb):
    _rodar(amb)
    _rodar(amb, motivo="repetição para conferir")
    j2 = json.loads((amb["docs"] / "protocolo_rodada_002.json").read_text(encoding="utf-8"))
    assert j2["repete_rodada"] == 1 and j2["reproduziu"] is True
    texto = (amb["docs"] / "protocolo_rodada_002.md").read_text(encoding="utf-8")
    assert "| 1 |" in texto and "| 2 |" in texto


def test_segunda_rodada_sem_motivo_recusada(amb):
    _rodar(amb)
    assert _main(amb, motivo="") == 2
    assert not (amb["docs"] / "protocolo_rodada_002.md").exists()


def test_veneno(amb):
    df = dataset_sintetico()
    envenenado = _envenenar(df, df["data"] >= pd.Timestamp("2026-01-01"))
    datasets2 = amb["tmp"] / "envenenado"
    csv2 = gravar_versoes(datasets2, envenenado, versoes=("todas",))["todas"]
    d2, s2 = amb["tmp"] / "docs_v", amb["tmp"] / "saida_v"
    doc_de_teste(d2)
    _rodar(amb)
    execucao.executar(datasets2, d2, s2, data=treino._data_do_arquivo(csv2), motivo="1ª rodada",
                      params=amb["params"], lim=amb["lim"], registro_teste_final=amb["teste_final"])
    j1 = json.loads((amb["docs"] / "protocolo_rodada_001.json").read_text(encoding="utf-8"))
    j2 = json.loads((d2 / "protocolo_rodada_001.json").read_text(encoding="utf-8"))
    assert j1["sha_resultado"] == j2["sha_resultado"]
    assert (amb["saida"] / "rodada-001" / "ganho_diario.csv").read_bytes() == \
        (s2 / "rodada-001" / "ganho_diario.csv").read_bytes()


def test_recusa_outra_versao_preparacao(amb, capsys):
    caminho = amb["csv"].with_suffix(".json")
    info = json.loads(caminho.read_text(encoding="utf-8"))
    info["versao_preparacao"] = info["versao_preparacao"] + 1
    caminho.write_text(json.dumps(info), encoding="utf-8")
    assert _main(amb, motivo="1ª rodada") == 2
    assert "regenere" in capsys.readouterr().out
    assert _arquivos(amb["docs"]) == ["protocolo_variaveis.md"]


def test_recusa_sha_alterado(amb):
    amb["csv"].write_bytes(amb["csv"].read_bytes() + b"\n")
    assert _main(amb, motivo="1ª rodada") == 2
    assert _arquivos(amb["docs"]) == ["protocolo_variaveis.md"]


def test_trava_data_limite(amb):
    params = params_teste(teste_final_inicio=date(2026, 6, 24))
    assert _main(amb, motivo="1ª rodada", params=params) == 4
    assert _arquivos(amb["docs"]) == ["protocolo_variaveis.md"]
    execucao.conferir_travas(params_teste(teste_final_inicio=date(2026, 6, 23)), amb["teste_final"])


def test_trava_teste_final_usado(amb):
    amb["teste_final"].write_text("{}", encoding="utf-8")
    assert _main(amb, motivo="1ª rodada") == 4
    assert _arquivos(amb["docs"]) == ["protocolo_variaveis.md"]


def test_nao_toca_em_modelos_nem_teste_final(amb, monkeypatch):
    def proibido(*args, **kwargs):
        raise AssertionError("o protocolo não pode chamar isto")

    for alvo, nome in ((modelos, "salvar_modelo"), (treino, "ler_teste_final"),
                       (validacao, "dobras_teste_final"), (treino, "executar"),
                       (fontes, "criar_engine"), (fontes, "executar_leitura")):
        monkeypatch.setattr(alvo, nome, proibido)
    _rodar(amb)
    texto = Path(execucao.__file__).read_text(encoding="utf-8")
    for termo in ("salvar_modelo", "save_model", "ler_teste_final", "dobras_teste_final"):
        assert termo not in texto


def test_nunca_sobrescreve(amb):
    (amb["docs"] / "protocolo_rodada_001.md").write_text("original", encoding="utf-8")
    with pytest.raises(execucao.ErroProtocolo):
        _rodar(amb)
    assert (amb["docs"] / "protocolo_rodada_001.md").read_text(encoding="utf-8") == "original"
    assert not (amb["docs"] / "protocolo_tentativas.jsonl").exists()


def test_regras_alteradas_invalidam(amb):
    _rodar(amb)
    doc = amb["docs"] / "protocolo_variaveis.md"
    doc.write_bytes(doc.read_bytes().replace("+0,005".encode("utf-8"), "+0,006".encode("utf-8")))
    assert _main(amb, motivo="regras mudadas de propósito") == 3
    assert not (amb["docs"] / "protocolo_congelado_rodada_002.json").exists()
    assert json.loads((amb["docs"] / "protocolo_rodada_002.json").read_text(encoding="utf-8"))["status"] == "invalida"


def test_registro_adulterado(amb):
    _rodar(amb)
    caminho = amb["docs"] / "protocolo_tentativas.jsonl"
    caminho.write_text(caminho.read_text(encoding="utf-8").replace('"rodada": 1', '"rodada": 7', 1), encoding="utf-8")
    assert _main(amb, motivo="tentativa") == 2
    assert not (amb["docs"] / "protocolo_rodada_002.md").exists()


def test_ano_faltando(amb):
    lim = replace(amb["lim"], anos=(2024, 2025))
    assert _main(amb, motivo="1ª rodada", lim=lim) == 2


def test_coluna_nova_vazia(amb):
    df = dataset_sintetico()
    df["dy_12m"] = float("nan")
    datasets2 = amb["tmp"] / "vazia"
    gravar_versoes(datasets2, df, versoes=("todas",))
    assert _main(amb, motivo="1ª rodada", datasets=datasets2) == 2


def test_interrupcao_fica_registrada(amb, monkeypatch):
    original = treino.prever_walk_forward
    contador = {"n": 0}

    def quebra(*args, **kwargs):
        contador["n"] += 1
        if contador["n"] == 3:
            raise RuntimeError("falha de teste no meio da rodada")
        return original(*args, **kwargs)

    monkeypatch.setattr(treino, "prever_walk_forward", quebra)
    with pytest.raises(RuntimeError):
        _rodar(amb)
    assert [e["evento"] for e in _registro(amb)] == ["inicio", "falhou"]
    monkeypatch.setattr(treino, "prever_walk_forward", original)
    assert _main(amb, motivo="retomada") in (0, 3)
    assert (amb["docs"] / "protocolo_rodada_002.md").exists()
    assert [e["evento"] for e in _registro(amb)][:2] == ["inicio", "falhou"]


def test_controle_aprovado_ponta_a_ponta_invalida(amb, monkeypatch):
    original = execucao.rodar_protocolo
    chamadas = {"n": 0}

    def medir_controle_aprovado(pred_base, pred_cand, semente, lim):
        chamadas["n"] += 1
        if chamadas["n"] == 1:   # o controle é o primeiro teste da ordem
            return _medidas_fake(0.01)
        return protocolo.medir_comparacao(pred_base, pred_cand, semente, lim)

    monkeypatch.setattr(
        execucao, "rodar_protocolo",
        lambda prep, dobras, params, lim: original(prep, dobras, params, lim, medir=medir_controle_aprovado),
    )
    assert _main(amb, motivo="1ª rodada") == 3
    texto = (amb["docs"] / "protocolo_rodada_001.md").read_text(encoding="utf-8")
    assert "controle aprovado" in texto and "nenhum bloco adotado" in texto.lower()
    assert not (amb["docs"] / "protocolo_congelado_rodada_001.json").exists()
    fim = [e for e in _registro(amb) if e["evento"] == "fim"][0]
    assert fim["status"] == "invalida" and fim["adotados"] == []
