#!/usr/bin/env python3
"""
Radar Bauru - gera site/dinheiro.js a partir de:
  dados/tce/despesas-AAAA-bauru.csv   (ano fechado, detalhado; coleta_tce_anual.py)
  dados/gastos/*.json                 (ano corrente pelo TCE + PNCP; coleta_gastos.py)

Uso:
    python gerar_dinheiro.py              gera site/dinheiro.js
    python gerar_dinheiro.py --conferir   mostra totais e exemplos das regras
"""

import collections
import csv
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regras import sem_acento  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))
TCE_DIR = os.path.join(RAIZ, "dados", "tce")
GASTOS = os.path.join(RAIZ, "dados", "gastos")
SITE = os.path.join(RAIZ, "site")
ANO_INICIAL = 2025
TOP = 60

FONTES = {
    "tce_anual": "https://transparencia.tce.sp.gov.br/conjunto-de-dados",
    "tce_api": "https://transparencia.tce.sp.gov.br/",
    "pncp": "https://pncp.gov.br/app/",
}

# Pagamentos a orgaos da propria administracao (folha, previdencia, repasses)
# nao sao "fornecedores": ficam separados no ranking.
INTERNO = re.compile(r"prefeitura municipal de bauru|fund\w* prev\w* serv|funprev|"
                     r"gua e esgoto|emdurb|empresa mun\w* desenv|mara municipal de bauru")

# Eventos: termos exatos. "evento" sozinho casa com "desenvolvimento".
EVENTOS = [
    ("shows", "Shows e apresentações artísticas",
     re.compile(r"apresentacao artistica|\bshows?\b|\bcache\b")),
    ("carnaval", "Carnaval", re.compile(r"\bcarnaval")),
    ("estrutura", "Estrutura de eventos (palco, som, tendas, banheiros)",
     re.compile(r"\bpalcos?\b|sonorizacao|\btendas?\b|banheiros? quimicos?|\bgradis?\b|"
                r"iluminacao cenica|camarim")),
]
NAO_EVENTO = re.compile(r"emenda impositiva")


def valor(txt):
    return float(str(txt).replace(".", "").replace(",", "."))


def nome_orgao(txt):
    t = sem_acento(txt)
    if "prefeitura" in t:
        return "Prefeitura"
    if "esgoto" in t:
        return "DAE"
    if "emdurb" in t or "desenv. urbano" in t:
        return "EMDURB"
    if "funprev" in t or "prev." in t:
        return "FUNPREV"
    if "mara municipal" in t:
        return "Câmara Municipal"
    return txt.strip().title()


def pessoa_fisica(identificador):
    return "fisica" in sem_acento(identificador) or sem_acento(identificador).startswith("cpf")


def classificar_evento(texto):
    t = sem_acento(texto)
    if NAO_EVENTO.search(t):
        return None
    for chave, _, padrao in EVENTOS:
        if padrao.search(t):
            return chave
    return None


def sem_modalidade(modalidade):
    t = sem_acento(modalidade)
    return "outros" in t or "aplica" in t or not t.strip()


def categoria_sem_licitacao(elemento):
    """O que e, de fato, um pagamento que o TCE marca como "Outros/nao aplicavel".
    Usa o codigo oficial da natureza da despesa (ex.: 31901101): 1o digito =
    categoria, 2o = grupo (1 pessoal, 2 juros, 3 custeio, 4 investimento,
    6 amortizacao), 3o-4o = modalidade de aplicacao (50 = entidade sem fins
    lucrativos, 91 = entre orgaos do proprio municipio)."""
    cod = re.match(r"\s*(\d{8})", elemento or "")
    cod = cod.group(1) if cod else ""
    t = sem_acento(elemento)
    if re.search(r"previdenci|rpps|deficit atuarial", t):
        return "Previdência dos servidores (contribuições e cobertura do déficit)"
    if cod[:2] in ("32", "46") or "divida" in t:
        return "Dívida (juros e amortização)"
    if cod[:2] == "31":
        return "Salários e encargos dos servidores"
    if cod[2:4] == "50":
        return "Repasses a entidades (termos de colaboração e fomento)"
    if re.search(r"energia|agua e esgoto|telefon|comunicacao de dados", t):
        return "Contas de energia, água e telefone"
    if "terceirizacao" in t:
        return "Terceirização de mão de obra"
    if cod[2:4] == "91":
        return "Serviços pagos a órgãos do próprio município"
    if re.search(r"sentenc|precator|indeniza|restitui", t):
        return "Sentenças judiciais, precatórios e indenizações"
    if re.search(r"pis/pasep|obrigacoes tributarias|tribut", t):
        return "Tributos e contribuições (PIS/Pasep)"
    if re.search(r"subven|auxilio financeiro|beneficios assist|bolsa", t):
        return "Subvenções, bolsas e auxílios"
    return "Outras despesas sem modalidade informada"


NAO_INFORMADA = {"Contas de energia, água e telefone", "Terceirização de mão de obra",
                 "Outras despesas sem modalidade informada"}


def ranking(contador, n=TOP):
    return [{"nome": k[0], "pf": k[1], "pago": round(v, 2)}
            for k, v in contador.most_common(n)]


def ano_fechado(caminho):
    ano = int(re.search(r"(\d{4})", os.path.basename(caminho)).group(1))
    pago_orgao = collections.Counter()
    area = collections.defaultdict(collections.Counter)
    modalidade = collections.defaultdict(collections.Counter)
    fornec = collections.defaultdict(collections.Counter)
    interno = collections.Counter()
    eventos = []
    # O arquivo anual do TCE-SP vem em Windows-1252, nao UTF-8.
    with open(caminho, encoding="cp1252", errors="replace") as arq:
        for x in csv.DictReader(arq, delimiter=";"):
            if "pago" not in sem_acento(x["tp_despesa"]):
                continue
            org = nome_orgao(x["ds_orgao"])
            v = valor(x["vl_despesa"])
            pago_orgao[org] += v
            area[org][x["ds_funcao_governo"].strip().title()] += v
            mod = x["ds_modalidade_lic"].strip()
            if sem_modalidade(mod):
                # "Outros/nao aplicavel" escondia mais da metade do dinheiro: abre pelo tipo de despesa.
                cat = categoria_sem_licitacao(x["ds_elemento"])
                # So e "sem licitacao por natureza" o que a lei nao manda licitar (folha,
                # previdencia, divida, tributos, sentencas, repasses). Terceirizacao e
                # contas de consumo podem vir de contratos licitados: o TCE so nao
                # informou a modalidade.
                prefixo = ("Modalidade não informada ao TCE: " if cat in NAO_INFORMADA
                           else "Sem licitação por natureza: ")
                modalidade[org][prefixo + cat] += v
            else:
                modalidade[org][mod.capitalize()] += v
            pf = pessoa_fisica(x["tp_identificador_despesa"])
            nome = x["ds_despesa"].strip()
            if INTERNO.search(sem_acento(nome)):
                interno[org] += v
            else:
                fornec[org][(nome, pf)] += v
            grupo = classificar_evento(x["historico_despesa"])
            if grupo:
                eventos.append({
                    "orgao": org, "data": x["dt_emissao_despesa"], "fornecedor": nome, "pf": pf,
                    "historico": re.sub(r"\s+", " ", x["historico_despesa"]).strip()[:220],
                    "valor": round(v, 2), "modalidade": x["ds_modalidade_lic"].strip().capitalize(),
                    "grupo": grupo})
    eventos.sort(key=lambda e: -e["valor"])
    return ano, {
        "fonte": "tce_anual", "completo": True, "ate_mes": 12,
        "orgaos": {k: round(v, 2) for k, v in pago_orgao.most_common()},
        "areas": {o: [[k, round(v, 2)] for k, v in c.most_common()] for o, c in area.items()},
        "modalidades": {o: [[k, round(v, 2)] for k, v in c.most_common()] for o, c in modalidade.items()},
        "fornecedores": {o: ranking(c) for o, c in fornec.items()},
        "interno": {k: round(v, 2) for k, v in interno.items()},
        "eventos": eventos,
    }


def ano_corrente(dados):
    pago_orgao = collections.Counter()
    fornec = collections.defaultdict(collections.Counter)
    interno = collections.Counter()
    meses = sorted(int(m) for m in dados["meses"])
    for mes, registros in dados["meses"].items():
        for x in registros:
            if "pago" not in sem_acento(x.get("evento")):
                continue
            org = nome_orgao(x["orgao"])
            v = valor(x["vl_despesa"])
            pago_orgao[org] += v
            nome = (x.get("nm_fornecedor") or "").strip()
            if INTERNO.search(sem_acento(nome)):
                interno[org] += v
            else:
                fornec[org][(nome, pessoa_fisica(x.get("id_fornecedor", "")))] += v
    return dados["ano"], {
        "fonte": "tce_api", "completo": False, "ate_mes": max(meses) if meses else 0,
        "orgaos": {k: round(v, 2) for k, v in pago_orgao.most_common()},
        "fornecedores": {o: ranking(c) for o, c in fornec.items()},
        "interno": {k: round(v, 2) for k, v in interno.items()},
    }


def link_pncp(controle, tipo):
    # "46137410000180-2-000123/2025" -> /app/contratos/46137410000180/2025/123
    m = re.match(r"(\d{14})-\d+-0*(\d+)/(\d{4})", controle or "")
    if not m:
        return FONTES["pncp"]
    return f"https://pncp.gov.br/app/{tipo}/{m.group(1)}/{m.group(3)}/{m.group(2)}"


def carregar(nome):
    caminho = os.path.join(GASTOS, nome + ".json")
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as arq:
        return json.load(arq)


def montar():
    anos = {}
    for caminho in sorted(glob.glob(os.path.join(TCE_DIR, "despesas-*-bauru.csv"))):
        ano, dados = ano_fechado(caminho)
        if ano >= ANO_INICIAL:
            anos[str(ano)] = dados
    corrente = carregar("tce_despesas_ano_corrente")
    if corrente and str(corrente["ano"]) not in anos:
        ano, dados = ano_corrente(corrente)
        anos[str(ano)] = dados
    if not anos:
        raise FileNotFoundError("dados/tce ou dados/gastos")

    contratos, diretas, shows_diretas = [], [], []
    hoje = datetime.date.today().year
    for ano in range(ANO_INICIAL, hoje + 1):
        for c in carregar(f"pncp_contratos_{ano}"):
            pf = str(c.get("tipoPessoa", "")).upper() == "PF"
            contratos.append({
                "data": (c.get("dataAssinatura") or "")[:10],
                "objeto": re.sub(r"\s+", " ", c.get("objetoContrato") or "").strip()[:300],
                "valor": c.get("valorGlobal") or c.get("valorInicial") or 0,
                "fornecedor": (c.get("nomeRazaoSocialFornecedor") or "").strip(),
                "pf": pf,
                "tipo": (c.get("tipoContrato") or {}).get("nome", ""),
                "link": link_pncp(c.get("numeroControlePNCP"), "contratos"),
            })
        for modalidade in ("dispensa", "inexigibilidade"):
            for c in carregar(f"pncp_{modalidade}_{ano}"):
                item = {
                    "data": (c.get("dataPublicacaoPncp") or "")[:10],
                    "objeto": re.sub(r"\s+", " ", c.get("objetoCompra") or "").strip()[:300],
                    "valor": c.get("valorTotalHomologado") or c.get("valorTotalEstimado") or 0,
                    "modalidade": modalidade.capitalize(),
                    "amparo": (c.get("amparoLegal") or {}).get("nome", ""),
                    "link": link_pncp(c.get("numeroControlePNCP"), "editais"),
                }
                diretas.append(item)
                if classificar_evento(item["objeto"]):
                    shows_diretas.append(item)
    contratos.sort(key=lambda c: c["data"], reverse=True)
    diretas.sort(key=lambda c: c["data"], reverse=True)

    return {
        "gerado_em": datetime.datetime.now().isoformat(timespec="minutes"),
        "fontes": FONTES,
        "anos": anos,
        "grupos_evento": {k: n for k, n, _ in EVENTOS},
        "contratos": contratos,
        "diretas": diretas,
        "eventos_pncp": shows_diretas,
    }


def conferir(s):
    for ano, a in s["anos"].items():
        print(f"\n== {ano} ({'completo' if a['completo'] else 'até mês ' + str(a['ate_mes'])})")
        print("  Pago por órgão (R$ mi):", {k: round(v / 1e6, 1) for k, v in a["orgaos"].items()})
        print("  Interno (folha/repasses):", {k: round(v / 1e6, 1) for k, v in a["interno"].items()})
        print("  Top 8 fornecedores da Prefeitura:")
        for f in a["fornecedores"].get("Prefeitura", [])[:8]:
            print(f"    {f['nome'][:55]:55} {'PF' if f['pf'] else 'PJ'} {f['pago'] / 1e6:7.2f} mi")
        if a.get("eventos"):
            por = collections.Counter()
            for e in a["eventos"]:
                por[e["grupo"]] += e["valor"]
            print("  Eventos (R$ mi):", {k: round(v / 1e6, 2) for k, v in por.items()},
                  f"{len(a['eventos'])} pagamentos")
            for e in a["eventos"][:6]:
                print(f"    {e['grupo']:9} {e['fornecedor'][:28]:28} {e['valor']:>11,.2f}  {e['historico'][:70]}")
    print(f"\nPNCP: {len(s['contratos'])} contratos, {len(s['diretas'])} compras diretas, "
          f"{len(s['eventos_pncp'])} diretas com cara de evento")
    for e in s["eventos_pncp"][:5]:
        print(f"    {e['data']} {e['modalidade']:15} {e['valor']:>12,.2f}  {e['objeto'][:80]}")


def main():
    try:
        s = montar()
    except FileNotFoundError as erro:
        print(f"Faltam dados ({erro}). Rode coleta_tce_anual.py e coleta_gastos.py.")
        return 1
    if "--conferir" in sys.argv:
        conferir(s)
        return 0
    os.makedirs(SITE, exist_ok=True)
    caminho = os.path.join(SITE, "dinheiro.js")
    with open(caminho + ".parcial", "w", encoding="utf-8") as arq:
        arq.write("window.DINHEIRO = ")
        json.dump(s, arq, ensure_ascii=False, separators=(",", ":"))
        arq.write(";\n")
    os.replace(caminho + ".parcial", caminho)
    print(f"Gerado {caminho} ({os.path.getsize(caminho) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
