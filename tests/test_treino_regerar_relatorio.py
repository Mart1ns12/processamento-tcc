"""Regeração do relatorio.md a partir do metricas.json gravado (sem retreinar). Usa só pasta temporária."""

import json

from processamento.experimento import regerar_relatorio


def _modelo(taxa, auc):
    return {"auc_medio_pregao": auc, "topk": {"5": {"taxa_acerto": taxa, "vs_acaso": "acima"}, "3": {}}}


def _metricas_antigas():
    return {
        "modo": "desenvolvimento",
        "aviso_funcionamento": False,
        "modelos": {
            "modelo_3": _modelo(0.5167, 0.5165),
            "volatilidade": _modelo(0.4834, 0.5087),
            "logistica": _modelo(0.5112, 0.5213),
        },
        "veredito_modelo_3": {
            "acaso": "acima",
            "supera_volatilidade": True,
            "supera_logistica": True,
            "referencia_terceira": "a logística",
            "texto": "texto antigo do veredito",
        },
        "calibracao": {"aprovada": True, "chance_exibida": False},
    }


def test_regerar_atualiza_o_veredito_so_no_relatorio(tmp_path):
    (tmp_path / "metricas.json").write_text(json.dumps(_metricas_antigas()), encoding="utf-8")
    caminho = regerar_relatorio.regerar(tmp_path)
    assert caminho == tmp_path / "relatorio.md"
    texto = caminho.read_text(encoding="utf-8")
    assert "texto antigo do veredito" not in texto
    assert (
        "- Supera a logística: no top 5 sim (0,5167 × 0,5112); no AUC por pregão não (0,5165 × 0,5213)."
    ) in texto
    assert "mas não superou a logística (0,5165 × 0,5213) neste período." in texto
    # o metricas.json não é reescrito
    assert json.loads((tmp_path / "metricas.json").read_text(encoding="utf-8"))["veredito_modelo_3"]["texto"] == (
        "texto antigo do veredito"
    )
