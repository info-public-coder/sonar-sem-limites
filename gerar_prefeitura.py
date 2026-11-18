#!/usr/bin/env python3
"""
Radar Bauru - gera site/prefeitura.js (pagina Prefeitura).

Junta tres fontes oficiais:
  dados/prefeitura/equipe.json      quem e quem (site da Prefeitura; coleta_prefeitura.py)
  dados/*.json                      o que a Prefeita enviou a Camara (SAPL; coleta.py)
  dados/tce/despesas-AAAA-bauru.csv quanto foi pago por programa do orcamento (TCE-SP)

O TCE-SP NAO informa a secretaria de cada despesa. Ligamos uma secretaria a
um programa do orcamento so quando o nome do programa e claramente o tema da
secretaria (lista PROGRAMAS abaixo). Isso e conta nossa e o site diz isso.

Uso:
    python gerar_prefeitura.py
    python gerar_prefeitura.py --conferir
"""

import collections
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gerar_site  # noqa: E402
import regras  # noqa: E402
from gerar_dinheiro import INTERNO, ano_corrente, nome_orgao, pessoa_fisica, valor  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(RAIZ, "site")
NOME_AUTOR_PREFEITA = re.compile(r"^prefeit[oa] municipal$")

# Secretaria (como escrita na pagina oficial, sem acento, minusculas) -> trechos do
# nome do programa no TCE. So entra o que e inequivoco pelo nome.
PROGRAMAS = {
    "secretaria de educacao": ["gestao do sistema de ensino", "programas complementares a educacao",
                               "unidades escolares"],
    "secretaria de assistencia social": ["assistencia social - suas"],
    "secretaria de meio ambiente e bem-estar animal": ["gestao do meio ambiente"],
    "secretaria de cultura": ["gestao acesso cultural"],
    "secretaria de esportes e lazer": ["gestao do esporte e lazer"],
    "secretaria de agricultura e abastecimento": ["agricultura sustentavel"],
    "secretaria de desenvolvimento economico, turismo e inovacao": ["fomento ao desenvolvimento"],
    "secretaria de infraestrutura": ["obras de infraestrutura"],
}
# Orgaos da administracao indireta com contabilidade propria no TCE.
ORGAO_TCE = {"departamento de agua e esgoto": "DAE", "emdurb": "EMDURB"}
GENERICO = "gestao participativa e eficiente"


def tce_por_programa():
    """Ultimo ano fechado do TCE: pago por programa (Prefeitura) e por orgao."""
    arquivos = sorted(glob.glob(os.path.join(RAIZ, "dados", "tce", "despesas-*-bauru.csv")))
    if not arquivos:
        return None
    caminho = arquivos[-1]
    ano = int(re.search(r"(\d{4})", os.path.basename(caminho)).group(1))
    prog = collections.Counter()
    fornec = collections.defaultdict(collections.Counter)
    orgao = collections.Counter()
    with open(caminho, encoding="cp1252", errors="replace") as arq:
        for x in csv.DictReader(arq, delimiter=";"):
            if "pago" not in regras.sem_acento(x["tp_despesa"]):
                continue
            v = valor(x["vl_despesa"])
            org = nome_orgao(x["ds_orgao"])
            orgao[org] += v
            if org != "Prefeitura":
                continue
            p = x["ds_programa"].strip()
            prog[p] += v
            nome = x["ds_despesa"].strip()
            if not INTERNO.search(regras.sem_acento(nome)):
                fornec[p][(nome, pessoa_fisica(x["tp_identificador_despesa"]))] += v
    return {"ano": ano, "programas": prog, "fornecedores": fornec, "orgaos": orgao}


def gasto_da_secretaria(cargo, tce):
    trechos = PROGRAMAS.get(regras.sem_acento(cargo))
    if not trechos or not tce:
        return None
    progs = [(p, v) for p, v in tce["programas"].most_common()
             if any(t in regras.sem_acento(p) for t in trechos)]
    if not progs:
        return None
    juntos = collections.Counter()
    for p, _ in progs:
        juntos.update(tce["fornecedores"][p])
    return {
        "ano": tce["ano"],
        "total": round(sum(v for _, v in progs), 2),
        "programas": [[p.capitalize(), round(v, 2)] for p, v in progs],
        "fornecedores": [{"nome": k[0], "pf": k[1], "pago": round(v, 2)} for k, v in juntos.most_common(5)],
    }


def propostas_da_prefeita():
    autores = gerar_site.carregar("autor")
    cod_autor = {a["cod_autor"] for a in autores
                 if NOME_AUTOR_PREFEITA.match(regras.sem_acento(a.get("nom_autor") or ""))}
    cods = {a["cod_materia"] for a in gerar_site.carregar("autoria")
            if a["cod_autor"] in cod_autor and not a.get("ind_excluido")}
    tipos = {t["tip_materia"]: t for t in gerar_site.carregar("tipo_materia_legislativa")}
    votadas = {v["cod_materia"] for v in gerar_site.carregar("registro_votacao") if not v.get("ind_excluido")}
    materias = []
    for m in gerar_site.carregar("materia_legislativa"):
        if m["cod_materia"] not in cods or m.get("ind_excluido"):
            continue
        t = tipos.get(m["tip_id_basica"], {})
        des = t.get("des_tipo_materia") or "?"
        ementa = (m.get("txt_ementa") or "").strip()
        grupo = "veto" if "veto" in regras.sem_acento(des) else regras.classificar(des, ementa)
        materias.append({
            "cod": m["cod_materia"],
            "id": f"{t.get('sgl_tipo_materia') or '?'} {m.get('num_ident_basica')}/{m.get('ano_ident_basica')}",
            "data": gerar_site.d(m.get("dat_apresentacao")),
            "tipo": des, "grupo": grupo, "ementa": ementa,
            "votada": m["cod_materia"] in votadas,
        })
    materias.sort(key=lambda m: m["data"], reverse=True)
    return materias


def montar():
    caminho = os.path.join(RAIZ, "dados", "prefeitura", "equipe.json")
    if not os.path.exists(caminho):
        raise SystemExit("Falta dados/prefeitura/equipe.json. Rode coleta_prefeitura.py.")
    with open(caminho, encoding="utf-8") as arq:
        equipe = json.load(arq)
    tce = tce_por_programa()
    radar, _ = gerar_site.montar()
    pessoas = []
    for p in equipe["pessoas"]:
        chave = regras.sem_acento(p["cargo"])
        item = {k: p[k] for k in ("id", "cargo", "nome", "fones", "endereco", "curriculo", "pagina", "foto")}
        item["tipo"] = ("prefeita" if chave.startswith("prefeit") else
                        "vice" if chave.startswith("vice") else
                        "secretaria" if chave.startswith("secretaria") or chave == "gabinete" else "indireta")
        item["gasto"] = gasto_da_secretaria(p["cargo"], tce)
        org = ORGAO_TCE.get(chave)
        if org and tce:
            item["orgao_pago"] = {"ano": tce["ano"], "orgao": org, "total": round(tce["orgaos"].get(org, 0), 2)}
        pessoas.append(item)

    corrente = None
    caminho_api = os.path.join(RAIZ, "dados", "gastos", "tce_despesas_ano_corrente.json")
    if os.path.exists(caminho_api):
        with open(caminho_api, encoding="utf-8") as arq:
            ano_c, dados_c = ano_corrente(json.load(arq))
        corrente = {"ano": ano_c, "ate_mes": dados_c["ate_mes"],
                    "prefeitura": dados_c["orgaos"].get("Prefeitura", 0)}

    prefeita = propostas_da_prefeita()
    generico = sum(v for p, v in (tce["programas"].items() if tce else []) if GENERICO in regras.sem_acento(p))
    return {
        "gerado_em": radar["gerado_em"],
        "equipe_fonte": equipe["fonte"],
        "equipe_coletada": equipe["coletado_em"],
        "sapl": gerar_site.SAPL,
        "pessoas": pessoas,
        "propostas": prefeita,
        "grupos": {**regras.GRUPOS, "veto": "Vetos a leis aprovadas pela Câmara"},
        "cobrancas_vereadores": radar["por_grupo"].get("cobranca", 0),
        "camara_coleta": radar["coleta"],
        "tce_corrente": corrente,
        "tce": {"ano": tce["ano"],
                "prefeitura": round(tce["orgaos"].get("Prefeitura", 0), 2),
                "generico": round(generico, 2)} if tce else None,
    }


def conferir(s):
    print(f"Pessoas: {len(s['pessoas'])}")
    for p in s["pessoas"]:
        g = p.get("gasto")
        print(f"  {p['tipo']:10} {p['cargo'][:55]:55} {p['nome'][:30]:30} "
              f"{'R$ %.1f mi' % (g['total'] / 1e6) if g else ''}")
    c = collections.Counter(m["grupo"] for m in s["propostas"])
    print(f"Propostas da Prefeita: {len(s['propostas'])} {dict(c)}; votadas: "
          f"{sum(m['votada'] for m in s['propostas'])}")
    print(f"Cobrancas dos vereadores: {s['cobrancas_vereadores']}; TCE: {s['tce']}")


def main():
    s = montar()
    if "--conferir" in sys.argv:
        conferir(s)
        return 0
    destino = os.path.join(SITE, "prefeitura.js")
    with open(destino + ".parcial", "w", encoding="utf-8") as arq:
        arq.write("window.PREFEITURA = ")
        json.dump(s, arq, ensure_ascii=False, separators=(",", ":"))
        arq.write(";\n")
    os.replace(destino + ".parcial", destino)
    print(f"Gerado {destino} ({os.path.getsize(destino) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
