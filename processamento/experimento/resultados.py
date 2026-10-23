"""Dias de resultado do experimento: pregão em que cada empresa teve balanço (plano da etapa 5).

Cada `data_entrega` vira o instante D 23:59:59 (fuso de São Paulo) e passa pela janela de notícias
(`calendario.classificar_noticias`). Se a entrega cai na noite de t, a empresa tem resultado no
dia t. Funções puras: nada de banco ou rede.
"""

from __future__ import annotations

import pandas as pd

from processamento import calendario


def dias_de_resultado(
    balancos: pd.DataFrame, cal: list, proximo_ao_vivo=None
) -> tuple[pd.DataFrame, dict]:
    """Pares (data, empresa) únicos: pregão t cuja noite contém a entrega de balanço.

    `empresa` é o CNPJ do balanço. Contagens: `sem_data` (data_entrega nula, ignorada) e `fora`
    (entrega fora do calendário, por linha de balanço).
    """
    sem_data = balancos["data_entrega"].isna()
    validos = balancos.loc[~sem_data].reset_index(drop=True)
    datas = pd.to_datetime(validos["data_entrega"]).dt.normalize()
    instantes = (datas + pd.Timedelta(hours=23, minutes=59, seconds=59)).dt.tz_localize(calendario.SP)
    entregas = pd.DataFrame({"empresa": validos["cnpj"], "data_hora_publicacao": instantes})

    classificadas = calendario.classificar_noticias(entregas, list(cal), proximo_ao_vivo)
    janelas = classificadas["janela"]
    contagens = {
        "sem_data": int(sem_data.sum()),
        "fora": int((janelas == "fora_do_calendario").sum()),
    }

    noite = classificadas.loc[janelas == "noite"]
    resultado = (
        pd.DataFrame({"data": pd.to_datetime(noite["pregao_ref"]), "empresa": noite["empresa"]})
        .drop_duplicates()
        .sort_values(["data", "empresa"])
        .reset_index(drop=True)
    )
    return resultado, contagens
