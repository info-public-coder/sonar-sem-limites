#!/usr/bin/env python3
"""
Sonar Sem Limites - transforma dados/*.json em site/dados.js (lido por site/index.html).

Uso:
    python gerar_site.py              gera site/dados.js
    python gerar_site.py --conferir   mostra como as regras classificaram os dados
                                      (para revisar ANTES de confiar no site)
"""

import base64
import collections
import datetime
import json
import os
import sys

# O Python "embed" do projeto nao poe a pasta do script no sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regras  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(RAIZ, "dados")
SITE = os.path.join(RAIZ, "site")
SAPL = "https://sapl.bauru.sp.leg.br"

# Codigos de frequencia do SAPL. CONFERIR com a ficha oficial na primeira
# coleta real; codigos fora daqui aparecem como "outro" e no --conferir.
FREQUENCIA = {"P": "presente", "F": "falta", "A": "justificada", "J": "justificada"}


def carregar(nome):
    with open(os.path.join(DADOS, nome + ".json"), encoding="utf-8") as arq:
        return json.load(arq)


def carregar_opcional(nome):
    caminho = os.path.join(DADOS, nome + ".json")
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as arq:
        return json.load(arq)


# Valores vistos em 2026-11: Sim, Nao, Ausente, Em branco, "-------"
# (o traco aparece quando o parlamentar nao vota, ex.: presidente).
VOTO = {"sim": "sim", "nao": "nao", "abstencao": "abstencao", "ausente": "ausente",
        "em branco": "branco", "-------": "nao_votou"}


def d(txt):
    return str(txt or "")[:10]


def link_materia(cod):
    return f"{SAPL}/consultas/materia/materia_mostrar_proc?cod_materia=" + \
        base64.b64encode(str(cod).encode()).decode()


def link_parlamentar(cod):
    return f"{SAPL}/consultas/parlamentar/parlamentar_mostrar_proc?cod_parlamentar={cod}"


def link_sessao(cod, data):
    dia = "/".join(reversed(data.split("-")))
    return f"{SAPL}/consultas/sessao_plenaria/agenda_sessao_plen_mostrar_proc?cod_sessao_plen={cod}&dat_sessao={dia}"


def montar():
    man = carregar("coleta")
    leg = man["legislatura"]
    num = leg["num_legislatura"]
    hoje = datetime.date.today().isoformat()

    parl = {p["cod_parlamentar"]: p for p in carregar("parlamentar")}
    partidos = {p["cod_partido"]: p.get("sgl_partido") or "?" for p in carregar("partido")}
    tipos = {t["tip_materia"]: t for t in carregar("tipo_materia_legislativa")}

    mandatos = collections.defaultdict(list)
    for m in carregar("mandato"):
        if m.get("num_legislatura") == num:
            mandatos[m["cod_parlamentar"]].append(m)

    filiacoes = collections.defaultdict(list)
    for f in carregar("filiacao"):
        filiacoes[f["cod_parlamentar"]].append(f)

    sessoes = {s["cod_sessao_plen"]: s for s in carregar("sessao_plenaria")
               if d(s.get("dat_inicio_sessao")) <= hoje}
    tipos_sessao = {t["tip_sessao"]: t.get("nom_sessao") for t in carregar("tipo_sessao_plenaria")}

    # Em Bauru a chamada e registrada na Ordem do Dia (ordem_dia_presenca).
    # Sessoes sem Ordem do Dia (ex.: "Indicacoes e Requerimentos") nao tem
    # chamada, entao o denominador e "sessoes em que houve chamada".
    presencas = [p for p in carregar("ordem_dia_presenca") if p.get("cod_sessao_plen") in sessoes]
    com_chamada = {p["cod_sessao_plen"] for p in presencas}

    freq = collections.defaultdict(collections.Counter)
    registradas = collections.defaultdict(set)
    codigos_desconhecidos = collections.Counter()
    for p in presencas:
        cod = str(p.get("tip_frequencia") or "").strip().upper()
        tipo = FREQUENCIA.get(cod)
        if tipo == "falta" and str(p.get("txt_justif_ausencia") or "").strip():
            tipo = "justificada"
        if tipo is None:
            tipo = "outro"
            codigos_desconhecidos[cod] += 1
        freq[p["cod_parlamentar"]][tipo] += 1
        registradas[p["cod_parlamentar"]].add(p["cod_sessao_plen"])

    autor_parl = {a["cod_autor"]: a.get("cod_parlamentar") for a in carregar("autor")}
    # Em Bauru o campo ind_primeiro_autor quase nunca e preenchido (6 de 9163
    # em 2026-11). Regra: proposta assinada por UM vereador conta para ele no
    # grupo dela; assinada por varios conta como coautoria para cada um.
    autores_de = collections.defaultdict(list)       # cod_materia -> [cod_parl]
    for a in carregar("autoria"):
        cp = autor_parl.get(a.get("cod_autor"))
        if cp and cp not in autores_de[a["cod_materia"]]:
            autores_de[a["cod_materia"]].append(cp)

    def nome(cod):
        p = parl.get(cod, {})
        return p.get("nom_parlamentar") or p.get("nom_completo") or f"#{cod}"

    materias = []
    contagem = collections.defaultdict(collections.Counter)    # cod_parl -> grupo -> n (principal)
    coautoria = collections.Counter()
    por_grupo = collections.Counter()
    for m in carregar("materia_legislativa"):
        t = tipos.get(m.get("tip_id_basica"), {})
        grupo = regras.classificar(t.get("des_tipo_materia"), m.get("txt_ementa"))
        por_grupo[grupo] += 1
        autores = autores_de.get(m["cod_materia"], [])
        for cp in autores:
            if len(autores) == 1:
                contagem[cp][grupo] += 1
            else:
                coautoria[cp] += 1
        ruas, bairros = regras.extrair_locais(m.get("txt_ementa"))
        materias.append({
            "cod": m["cod_materia"],
            "id": f"{t.get('sgl_tipo_materia') or '?'} {m.get('num_ident_basica')}/{m.get('ano_ident_basica')}",
            "tipo": t.get("des_tipo_materia") or "?",
            "data": d(m.get("dat_apresentacao")),
            "ementa": (m.get("txt_ementa") or "").strip(),
            "grupo": grupo,
            "autores": autores,
            "ruas": ruas,
            "bairros": bairros,
        })

    # Votos nominais (so existem nas votacoes nominais; as simbolicas
    # registram apenas o placar).
    votacoes = {v["cod_votacao"]: v for v in carregar("registro_votacao")}
    extras = {m["cod_materia"]: m for m in carregar_opcional("materia_votada")}
    votos = collections.defaultdict(collections.Counter)
    votos_nao = collections.defaultdict(list)
    votacoes_nominais = set()
    for v in carregar_opcional("registro_votacao_parlamentar"):
        vot = votacoes.get(v.get("cod_votacao"))
        if not vot:
            continue
        votacoes_nominais.add(v["cod_votacao"])
        voto = VOTO.get(regras.sem_acento(v.get("vot_parlamentar")).strip(), "outro")
        votos[v["cod_parlamentar"]][voto] += 1
        if voto == "nao":
            votos_nao[v["cod_parlamentar"]].append(vot.get("cod_materia"))
    codigos_voto = collections.Counter(str(v.get("vot_parlamentar"))
                                       for v in carregar_opcional("registro_votacao_parlamentar"))
    materias_cod = {m["cod"] for m in materias}
    materias_votadas = {}
    for cod_m in {c for lista in votos_nao.values() for c in lista}:
        if cod_m in materias_cod:
            continue
        m = extras.get(cod_m)
        if m:
            t = tipos.get(m.get("tip_id_basica"), {})
            materias_votadas[cod_m] = {
                "id": f"{t.get('sgl_tipo_materia') or '?'} {m.get('num_ident_basica')}/{m.get('ano_ident_basica')}",
                "ementa": (m.get("txt_ementa") or "").strip()}

    tse = {}
    caminho_tse = os.path.join(DADOS, "tse", "candidatos_bauru_2024.json")
    if os.path.exists(caminho_tse):
        with open(caminho_tse, encoding="utf-8") as arq:
            tse = json.load(arq)["vereadores"]

    vereadores = []
    for cod, mands in mandatos.items():
        # Suplentes tem um registro de mandato por periodo de exercicio.
        periodos = sorted((d(m.get("dat_inicio_mandato")), d(m.get("dat_fim_mandato")) or "9999-12-31")
                          for m in mands)
        inicio, fim = periodos[0][0], max(p[1] for p in periodos)
        filis = sorted(filiacoes.get(cod, []), key=lambda f: d(f.get("dat_filiacao")))
        no_periodo = [c for c in com_chamada
                      if any(a <= d(sessoes[c].get("dat_inicio_sessao")) <= b for a, b in periodos)]
        titular = any(str(m.get("ind_titular")) in ("1", "True") for m in mands)
        f = freq[cod]
        vt = votos.get(cod, collections.Counter())
        vereadores.append({
            "cod": cod,
            "nome": nome(cod),
            "partido": partidos.get(filis[-1]["cod_partido"], "?") if filis else "?",
            "inicio": inicio,
            "fim": fim,
            "periodos": periodos,
            "titular": titular,
            "em_exercicio": any(a <= hoje <= b for a, b in periodos),
            "sessoes": len(no_periodo),
            "presente": f["presente"],
            "falta": f["falta"],
            "justificada": f["justificada"],
            "outro": f["outro"],
            "sem_registro": len(set(no_periodo) - registradas[cod]),
            "votos": dict(vt),
            "votos_nao": votos_nao.get(cod, []),
            "propostas": dict(contagem[cod]),
            "coautorias": coautoria[cod],
            "fonte": link_parlamentar(cod),
            "foto": os.path.exists(os.path.join(RAIZ, "site", "fotos", f"{cod}.jpg")),
            "votos_2024": tse.get(str(cod), {}).get("votos"),
            "urna": tse.get(str(cod), {}).get("NM_URNA_CANDIDATO"),
        })
    vereadores.sort(key=lambda v: regras.sem_acento(v["nome"]))

    # "O problema que nao some": mesma rua em 3+ pedidos diferentes.
    por_rua = collections.defaultdict(list)
    for m in materias:
        if m["grupo"] == "bairro":
            for rua in m["ruas"]:
                por_rua[rua].append(m)
    repetidos = []
    for rua, lista in por_rua.items():
        if len(lista) >= 3:
            lista.sort(key=lambda m: m["data"])
            repetidos.append({"rua": rua, "pedidos": [m["cod"] for m in lista]})
    repetidos.sort(key=lambda r: -len(r["pedidos"]))

    ultima = max((d(s.get("dat_inicio_sessao")) for s in sessoes.values()), default="")
    config = {}
    caminho_config = os.path.join(RAIZ, "config.json")
    if os.path.exists(caminho_config):
        with open(caminho_config, encoding="utf-8") as arq:
            config = json.load(arq)

    saida = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="minutes"),
        "coleta": man["fim"],
        "legislatura": {"num": num, "inicio": d(leg.get("dat_inicio")), "fim": d(leg.get("dat_fim"))},
        "sapl": SAPL,
        "api": man["fonte"],
        "consultas": man["consultas"],
        "voto_nominal": bool(votacoes_nominais),
        "votacoes": {"total": len(votacoes), "nominais": len(votacoes_nominais)},
        "materias_votadas": {str(k): v for k, v in materias_votadas.items()},
        "sessoes": {"total": len(sessoes), "com_chamada": len(com_chamada), "ultima": ultima,
                    "por_tipo": dict(collections.Counter(
                        tipos_sessao.get(s.get("tip_sessao"), "?") for s in sessoes.values()))},
        "grupos": regras.GRUPOS,
        "explicacao": regras.EXPLICACAO,
        "por_grupo": dict(por_grupo),
        "vereadores": vereadores,
        "nomes": {str(cod): nome(cod) for cod in {cp for m in materias for cp in m["autores"]}},
        "materias": materias,
        "repetidos": repetidos,
        "salario": config.get("salario"),
    }
    diag = {"codigos_desconhecidos": codigos_desconhecidos, "codigos_voto": codigos_voto,
            "por_tipo": collections.Counter(
        (m["tipo"], m["grupo"]) for m in materias)}
    return saida, diag


def conferir(saida, diag):
    print(f"Coleta {saida['coleta']} | {len(saida['materias'])} materias | "
          f"{saida['sessoes']['total']} sessoes | voto nominal: {saida['voto_nominal']}\n")
    print("Tipo de materia -> grupo:")
    for (tipo, grupo), n in sorted(diag["por_tipo"].items(), key=lambda x: -x[1]):
        print(f"  {n:6}  {tipo[:50]:50} -> {grupo}")
    for grupo in regras.GRUPOS:
        exemplos = [m for m in saida["materias"] if m["grupo"] == grupo][:4]
        print(f"\nExemplos de '{grupo}':")
        for m in exemplos:
            print(f"  {m['id']}: {m['ementa'][:140]}")
    pedidos = [m for m in saida["materias"] if m["grupo"] == "bairro"]
    com_local = sum(1 for m in pedidos if m["ruas"] or m["bairros"])
    print(f"\nPedidos de bairro com rua ou bairro reconhecido: {com_local}/{len(pedidos)}")
    for m in [m for m in pedidos if not (m["ruas"] or m["bairros"])][:5]:
        print(f"  SEM LOCAL: {m['ementa'][:140]}")
    print(f"\nRuas com 3+ pedidos: {len(saida['repetidos'])}; top 5: "
          f"{[(r['rua'], len(r['pedidos'])) for r in saida['repetidos'][:5]]}")
    print(f"Codigos de frequencia nao mapeados: {dict(diag['codigos_desconhecidos']) or 'nenhum'}")
    print(f"Sessoes: {saida['sessoes']}")
    print(f"Votacoes: {saida['votacoes']} | valores de voto: {dict(diag['codigos_voto'])}")


def main():
    try:
        saida, diag = montar()
    except FileNotFoundError as erro:
        print(f"Faltam dados ({erro.filename}). Rode antes: python coleta.py")
        return 1
    if "--conferir" in sys.argv:
        conferir(saida, diag)
        return 0
    os.makedirs(SITE, exist_ok=True)
    caminho = os.path.join(SITE, "dados.js")
    with open(caminho + ".parcial", "w", encoding="utf-8") as arq:
        arq.write("window.SONAR = ")
        json.dump(saida, arq, ensure_ascii=False, separators=(",", ":"))
        arq.write(";\n")
    os.replace(caminho + ".parcial", caminho)
    print(f"Gerado {caminho} ({os.path.getsize(caminho) // 1024} KB): "
          f"{len(saida['vereadores'])} vereadores, {len(saida['materias'])} materias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
