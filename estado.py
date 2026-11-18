"""
Radar Bauru - registro de quando cada fonte deu certo pela ultima vez.

Cada coletor chama registrar() SO quando uma fonte vem completa e e gravada.
O arquivo <pasta>/estado.json guarda, por fonte, a data da ultima coleta boa
e quantos registros vieram. O conferir_dados.py usa isso para apontar dado
velho (fonte que vem falhando) e quedas bruscas de quantidade.
"""

import datetime
import json
import os


def registrar(pasta, fonte, registros):
    caminho = os.path.join(pasta, "estado.json")
    estado = {}
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as arq:
                estado = json.load(arq)
        except (OSError, ValueError):
            estado = {}
    estado[fonte] = {"ultima_boa": datetime.datetime.now().isoformat(timespec="seconds"),
                     "registros": registros}
    os.makedirs(pasta, exist_ok=True)
    with open(caminho + ".parcial", "w", encoding="utf-8") as arq:
        json.dump(estado, arq, ensure_ascii=False, indent=1)
    os.replace(caminho + ".parcial", caminho)


def ler(pasta):
    caminho = os.path.join(pasta, "estado.json")
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, encoding="utf-8") as arq:
            return json.load(arq)
    except (OSError, ValueError):
        return {}
