#!/usr/bin/env python3
"""
Radar Bauru - gera site/diretoria.js (pagina Diretoria de Ensino / URE Bauru)
a partir de dados/diretoria/*.json (coleta_diretoria.py).

Regua oficial usada para apontar desvio:
  Lei 14.133/2021, art. 75, I e II: limite da dispensa por valor, atualizado
  todo ano por decreto federal (art. 182). Contratos por dispensa de valor com
  o MESMO fornecedor no MESMO ano que, somados, passam do limite sao listados
  para conferencia. A lei soma "objetos de mesma natureza" na mesma unidade
  (art. 75, par. 1o); o mesmo fornecedor e um sinal, nao prova.

Uso:
    python gerar_diretoria.py
    python gerar_diretoria.py --conferir
"""

import collections
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(RAIZ, "dados", "diretoria")
SITE = os.path.join(RAIZ, "site")

# Valores conferidos no texto oficial (planalto.gov.br) em 14/11/2026.
LIMITES_DISPENSA = {
    2024: {"I": 119812.02, "II": 59906.02, "decreto": "Decreto nº 11.871/2023",
           "link": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/decreto/d11871.htm"},
    2025: {"I": 125451.15, "II": 62725.59, "decreto": "Decreto nº 12.343/2024",
           "link": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/decreto/d12343.htm"},
    2026: {"I": 130984.20, "II": 65492.11, "decreto": "Decreto nº 12.807/2025",
           "link": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12807.htm"},
}
LEI_14133 = "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm"


def ler(nome):
    caminho = os.path.join(PASTA, nome + ".json")
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as arq:
        return json.load(arq)


def chave(txt):
    import unicodedata
    t = unicodedata.normalize("NFD", str(txt or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", "", t).strip()


def inciso(amparo):
    m = re.search(r"Art\.\s*75,\s*(II|I)\b", amparo or "")
    return m.group(1) if m else None


def link_pncp(controle):
    # "46384111000140-1-000427/2025" -> pncp.gov.br/app/editais/46384111000140/2025/427
    m = re.match(r"(\d{14})-(\d)-(\d+)/(\d{4})", controle or "")
    if not m:
        return None
    tipo = "contratos" if m.group(2) == "2" else "editais"
    return f"https://pncp.gov.br/app/{tipo}/{m.group(1)}/{m.group(4)}/{int(m.group(3))}"


def montar():
    equipe = ler("equipe")
    if not equipe:
        raise SystemExit("Falta dados/diretoria/equipe.json. Rode coleta_diretoria.py.")
    folha = ler("folha") or {}
    sede = ler("servidores")
    pag = ler("pagamentos")
    aus = ler("ausencias")
    pn = ler("pncp")
    coleta = ler("coleta") or {}

    # ---- diarias por pessoa da equipe (nome publicado no site da URE)
    diarias_equipe = collections.defaultdict(lambda: collections.defaultdict(float))
    gastos = {}
    if pag:
        for ano, bloco in sorted(pag["anos"].items()):
            linhas = bloco["pagamentos"]
            total = sum(x["valor"] for x in linhas)
            natureza = collections.Counter()
            credores = collections.Counter()
            dia_mes = collections.Counter()
            dia_cargo = collections.Counter()
            pessoas, pessoas_cargo = set(), collections.defaultdict(set)
            for x in linhas:
                natureza[x["natureza"].capitalize()] += x["valor"]
                if x.get("pessoa"):
                    if "diaria" in chave(x["natureza"]).lower():
                        dia_mes[x["data"][:7]] += x["valor"]
                        cargo = x.get("cargo") or "Cargo não identificado (nome repetido ou fora da folha)"
                        dia_cargo[cargo] += x["valor"]
                        pessoas.add(x["pessoa_id"])
                        pessoas_cargo[cargo].add(x["pessoa_id"])
                        if x.get("credor"):
                            diarias_equipe[x["credor"]][ano] += x["valor"]
                else:
                    credores[x["credor"]] += x["valor"]
            gastos[ano] = {
                "ate_mes": bloco["ate_mes"], "total": round(total, 2), "pagamentos": len(linhas),
                "natureza": [[k, round(v, 2)] for k, v in natureza.most_common()],
                "credores": [[k, round(v, 2)] for k, v in credores.most_common(25)],
                "diarias": {"total": round(sum(dia_mes.values()), 2), "pessoas": len(pessoas),
                            "por_mes": sorted([k, round(v, 2)] for k, v in dia_mes.items()),
                            "por_cargo": [[k, round(v, 2), len(pessoas_cargo[k])] for k, v in dia_cargo.most_common()]},
            }

    # ---- equipe com folha e diarias
    pessoas = []
    for p in equipe["pessoas"]:
        linhas = (folha.get("equipe") or {}).get(p["nome"], [])
        pessoas.append({**p, "folha": linhas,
                        "diarias": {a: round(v, 2) for a, v in diarias_equipe.get(p["nome"], {}).items()}})

    # ---- servidores da sede e estimativa da folha
    quadro = None
    if sede:
        med = folha.get("medianas") or {}
        cargos, total, cobertos, fora = [], 0.0, 0, 0
        for nome, n, k in sede["por_cargo"]:
            m = med.get(k)
            if m:
                cargos.append({"cargo": nome, "n": n, "mediana": m["mediana"], "estimativa": round(m["mediana"] * n, 2)})
                total += m["mediana"] * n
                cobertos += n
            else:
                fora += n
                cargos.append({"cargo": nome, "n": n, "mediana": None, "estimativa": None})
        quadro = {"mes": sede["mes"], "sede": sede["sede"], "escolas": sede["escolas"], "fonte": sede["fonte"],
                  "cargos": cargos, "folha_estimada": round(total, 2), "cobertos": cobertos, "fora": fora}

    # ---- PNCP: contratos, diretas e regua do limite da dispensa
    contratos, diretas, alertas = [], [], []
    if pn:
        por_compra = {**(pn.get("compras_origem") or {}), **{d["numeroControlePNCP"]: d for d in pn["diretas"]}}
        for c in pn["contratos"]:
            compra = por_compra.get(c.get("numeroControlePncpCompra"))
            contratos.append({"fornecedor": c["nomeRazaoSocialFornecedor"], "pf": c["tipoPessoa"] == "PF",
                              "valor": c["valorGlobal"] or 0, "objeto": c["objetoContrato"],
                              "data": c["dataAssinatura"], "link": link_pncp(c["numeroControlePNCP"]),
                              "via": compra["modalidade"] if compra and compra.get("modalidade") else "Forma de contratação não informada no PNCP",
                              "amparo": compra["amparo"] if compra else None})
        for d in pn["diretas"]:
            diretas.append({**d, "link": link_pncp(d["numeroControlePNCP"]), "inciso": inciso(d["amparo"])})
        grupos = collections.defaultdict(list)
        for c in pn["contratos"]:
            compra = por_compra.get(c.get("numeroControlePncpCompra"))
            inc = inciso(compra["amparo"]) if compra else None
            if not inc or not c.get("dataAssinatura"):
                continue
            ano = int(c["dataAssinatura"][:4])
            forn = c.get("niFornecedor") or chave(c["nomeRazaoSocialFornecedor"])
            grupos[(ano, forn, inc)].append(c)
        for (ano, _, inc), lista in grupos.items():
            lim = LIMITES_DISPENSA.get(ano)
            soma = sum(c["valorGlobal"] or 0 for c in lista)
            if lim and len(lista) > 1 and soma > lim[inc]:
                alertas.append({"ano": ano, "inciso": inc, "limite": lim[inc], "decreto": lim["decreto"],
                                "link_decreto": lim["link"], "soma": round(soma, 2),
                                "fornecedor": lista[0]["nomeRazaoSocialFornecedor"],
                                "contratos": [{"valor": c["valorGlobal"], "objeto": c["objetoContrato"],
                                               "data": c["dataAssinatura"], "link": link_pncp(c["numeroControlePNCP"])}
                                              for c in sorted(lista, key=lambda c: c["dataAssinatura"])]})
        contratos.sort(key=lambda c: c["data"] or "", reverse=True)
        diretas.sort(key=lambda d: d["data"] or "", reverse=True)
        alertas.sort(key=lambda a: -a["soma"])

    return {
        "coleta": coleta.get("fim"),
        "falhas": coleta.get("falhas", []),
        "site_ure": equipe["fonte"],
        "equipe_coletada": equipe["coletado_em"],
        "folha_publicada": folha.get("publicada_em"),
        "folha_fonte": folha.get("fonte"),
        "pessoas": pessoas,
        "quadro": quadro,
        "gastos": gastos,
        "pagamentos_fonte": pag["fonte"] if pag else None,
        "ausencias": aus,
        "contratos": contratos,
        "diretas": diretas,
        "alertas": alertas,
        "limites": {str(a): v for a, v in LIMITES_DISPENSA.items()},
        "lei_14133": LEI_14133,
    }


def conferir(s):
    print(f"Equipe: {len(s['pessoas'])}; folha publicada {s['folha_publicada']}")
    for p in s["pessoas"]:
        f = p["folha"]
        print(f"  {p['funcao'][:30]:30} {p['nome'][:38]:38} "
              f"{' + '.join(x['cargo'] + ' R$%.2f' % x['remuneracao'] for x in f) or 'SEM FOLHA'}  diarias {p['diarias']}")
    q = s["quadro"]
    if q:
        print(f"Sede {q['mes']}: {q['sede']} servidores; folha estimada R$ {q['folha_estimada']:,.2f} "
              f"({q['cobertos']} cobertos, {q['fora']} fora)")
        for c in q["cargos"]:
            print(f"   {c['n']:3} {c['cargo'][:45]:45} {c['mediana']}")
    for ano, g in s["gastos"].items():
        print(f"Gastos {ano} ate mes {g['ate_mes']}: R$ {g['total']:,.2f}; diarias R$ {g['diarias']['total']:,.2f} "
              f"a {g['diarias']['pessoas']} pessoas")
    print(f"PNCP: {len(s['contratos'])} contratos, {len(s['diretas'])} diretas, {len(s['alertas'])} alertas")
    for a in s["alertas"]:
        print(f"   {a['ano']} inc {a['inciso']} {a['fornecedor']} soma {a['soma']} > {a['limite']}")
    if s["ausencias"]:
        print("Ausencias:", json.dumps(s["ausencias"]["bauru"], ensure_ascii=False), s["ausencias"]["outras_sedes"])


def main():
    s = montar()
    if "--conferir" in sys.argv:
        conferir(s)
        return 0
    destino = os.path.join(SITE, "diretoria.js")
    with open(destino + ".parcial", "w", encoding="utf-8") as arq:
        arq.write("window.DIRETORIA = ")
        json.dump(s, arq, ensure_ascii=False, separators=(",", ":"))
        arq.write(";\n")
    os.replace(destino + ".parcial", destino)
    print(f"Gerado {destino} ({os.path.getsize(destino) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
