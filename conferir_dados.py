#!/usr/bin/env python3
"""
Sonar Sem Limites - confere se ha dado faltando ou velho, fonte por fonte.

Para cada fonte: data da ultima coleta boa (estado.json dos coletores), prazo
maximo, buracos (meses do TCE, os 21 vereadores) e quedas bruscas de
quantidade em relacao a conferencia anterior.

Saidas:
  dados/conferencia.json   resultado (o robo do GitHub le "falhas" daqui)
  site/situacao.js         secao "Situacao dos dados" nas paginas
  $GITHUB_STEP_SUMMARY     tabela no resumo da execucao (so no GitHub Actions)

Situacoes: ok, aviso (vale olhar) e falha (passou do prazo ou faltou dado
essencial). Uso:
    python conferir_dados.py
Sai com codigo 1 se houver falha.
"""

import datetime
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(RAIZ, "dados")
SITE = os.path.join(RAIZ, "site")
sys.path.insert(0, RAIZ)
import estado  # noqa: E402

VEREADORES = 21
# (aviso, falha) em dias desde a ultima coleta boa
PRAZO_DIARIO = (3, 7)        # fontes coletadas todo dia pelo robo
PRAZO_CAMARA = (2, 4)
PRAZO_LOCAL = (30, 45)       # Prefeitura e URE: dependem do computador local (semente)
QUEDA = 0.8                  # menos de 80% da contagem anterior vira aviso
HOJE = datetime.datetime.now()


def ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8") as arq:
            return json.load(arq)
    except (OSError, ValueError):
        return None


def ler_js(nome, variavel):
    try:
        with open(os.path.join(SITE, nome), encoding="utf-8") as arq:
            texto = arq.read()
        return json.loads(texto[texto.index("=") + 1:].strip().rstrip(";"))
    except (OSError, ValueError):
        return None


def dias(iso):
    if not iso:
        return None
    try:
        return (HOJE - datetime.datetime.fromisoformat(str(iso)[:19])).days
    except ValueError:
        try:
            return (HOJE - datetime.datetime.fromisoformat(str(iso)[:10])).days
        except ValueError:
            return None


def data_efetiva(info):
    """(data usada para o prazo, texto extra). Se a fonte foi consultada depois
    do ultimo download e nao tinha mudado ("verificada"), vale a verificacao;
    o texto mostra as duas datas, para nao parecer coleta nova."""
    baixada, conferida = info.get("ultima_boa"), info.get("verificada")
    if conferida and (not baixada or conferida > baixada):
        return conferida, f"; baixada em {str(baixada)[8:10]}/{str(baixada)[5:7]}, fonte sem mudança desde então" if baixada else ""
    return baixada, ""


class Relatorio:
    def __init__(self, anterior):
        self.itens = []
        self.contagens = {}
        self.anterior = (anterior or {}).get("contagens", {})

    def add(self, pagina, fonte, situacao, data, detalhe):
        self.itens.append({"pagina": pagina, "fonte": fonte, "situacao": situacao,
                           "data": (str(data)[:10] if data else None), "detalhe": detalhe})

    def prazo(self, pagina, fonte, data, limites, extra=""):
        d = dias(data)
        if d is None:
            self.add(pagina, fonte, "falha", None, "nunca coletada com sucesso" + extra)
        elif d > limites[1]:
            self.add(pagina, fonte, "falha", data, f"última coleta boa há {d} dias (prazo {limites[1]})" + extra)
        elif d > limites[0]:
            self.add(pagina, fonte, "aviso", data, f"última coleta boa há {d} dias" + extra)
        else:
            verbo = "conferida" if "fonte sem mudança" in extra else "coletada"
            self.add(pagina, fonte, "ok", data, (f"{verbo} hoje" if d == 0 else f"{verbo} há {d} dia(s)") + extra)

    def contagem(self, chave, valor):
        """Guarda a contagem e diz se caiu muito em relacao a ultima conferencia."""
        if valor is None:
            return ""
        anterior = self.anterior.get(chave)
        self.contagens[chave] = valor
        if anterior and valor < anterior * QUEDA:
            return f"; ATENÇÃO: {valor} registros, eram {anterior}"
        return ""


def conferir():
    anterior = ler_json(os.path.join(DADOS, "conferencia.json"))
    r = Relatorio(anterior)
    ano, mes = HOJE.year, HOJE.month

    # ---- Camara
    man = ler_json(os.path.join(DADOS, "coleta.json")) or {}
    camara = ler_js("dados.js", "SONAR") or {}
    em_exercicio = sum(1 for v in camara.get("vereadores", []) if v.get("em_exercicio"))
    extra = r.contagem("camara_materias", len(camara.get("materias", [])) or None)
    r.prazo("Câmara", "Câmara (SAPL)", man.get("fim"), PRAZO_CAMARA, extra)
    if camara:
        if em_exercicio != VEREADORES:
            r.add("Câmara", "Vereadores em exercício", "falha", man.get("fim"),
                  f"{em_exercicio} no site; a Câmara tem {VEREADORES}")
        else:
            r.add("Câmara", "Vereadores em exercício", "ok", man.get("fim"), f"{em_exercicio} de {VEREADORES}")
    tse = ler_json(os.path.join(DADOS, "tse", "candidatos_bauru_2024.json"))
    sem_foto = [v["nome"] for v in camara.get("vereadores", []) if v.get("em_exercicio") and not v.get("foto")]
    r.add("Câmara", "Fotos e votos (TSE 2024)", "ok" if tse and not sem_foto else "aviso", None,
          "todos com foto" if tse and not sem_foto else
          ("sem foto: " + ", ".join(sem_foto) if sem_foto else "arquivo do TSE ausente"))

    # ---- Dinheiro: TCE e PNCP
    est = estado.ler(os.path.join(DADOS, "gastos"))
    tce = est.get("tce_despesas_ano_corrente", {})
    corrente = ler_json(os.path.join(DADOS, "gastos", "tce_despesas_ano_corrente.json")) or {}
    meses = sorted(int(m) for m in (corrente.get("meses") or {}))
    buracos = [m for m in range(1, (max(meses) if meses else 0) + 1) if m not in meses]
    extra = r.contagem("tce_corrente", tce.get("registros"))
    if buracos:
        extra += f"; FALTAM os meses {buracos}"
    elif meses:
        extra += f"; janeiro a {meses[-1]:02d}/{corrente.get('ano')}"
    data, nota = data_efetiva(tce)
    r.prazo("Dinheiro", f"TCE-SP {ano} (pagamentos do mês)", data, PRAZO_DIARIO, extra + nota)
    if buracos:
        r.itens[-1]["situacao"] = "falha"
    elif meses and meses[-1] < mes - 3:
        r.add("Dinheiro", f"TCE-SP {ano}: meses publicados", "aviso", None,
              f"o TCE só publicou até {meses[-1]:02d}/{ano}")
    anual = os.path.join(DADOS, "tce", f"despesas-{ano - 1}-bauru.csv")
    r.add("Dinheiro", f"TCE-SP {ano - 1} (ano fechado)", "ok" if os.path.exists(anual) else "aviso", None,
          "arquivo anual presente" if os.path.exists(anual) else
          f"arquivo anual de {ano - 1} ainda não baixado (o TCE publica depois que o ano fecha)")
    for nome, info in sorted(est.items()):
        if not nome.startswith("pncp_"):
            continue
        a = int(nome.rsplit("_", 1)[1])
        limites = PRAZO_DIARIO if a == ano else (15, 30)
        rotulo = "PNCP " + nome.split("_")[1].replace("contratos", "contratos").capitalize() + f" {a}"
        data, nota = data_efetiva(info)
        r.prazo("Dinheiro", rotulo, data, limites, nota +
                r.contagem(nome, info.get("registros")) + f"; {info.get('registros')} registros")
    if f"pncp_contratos_{ano}" not in est:
        r.add("Dinheiro", f"PNCP Contratos {ano}", "falha", None, "nunca coletado com sucesso")

    # ---- Prefeitura
    eq = ler_json(os.path.join(DADOS, "prefeitura", "equipe.json")) or {}
    r.prazo("Prefeitura", "Equipe de governo (site da Prefeitura)", eq.get("coletado_em"), PRAZO_LOCAL,
            r.contagem("prefeitura_equipe", len(eq.get("pessoas", [])) or None) +
            "; só atualiza pelo computador local (o site recusa o GitHub)")

    # ---- Diretoria de Ensino
    estd = estado.ler(os.path.join(DADOS, "diretoria"))
    nomes = {"equipe": "Equipe (site da URE)", "servidores": "Servidores da sede (cadastro)",
             "folha": "Salários (folha do Estado)", "pagamentos": "Pagamentos e diárias",
             "pncp": "Contratos (PNCP)"}
    for chave, rotulo in nomes.items():
        info = estd.get(chave, {})
        # Servidores e pagamentos vem do portal da Secretaria, que recusa o GitHub:
        # so atualizam pelo computador local. O resto o robo coleta todo dia.
        local = chave in ("servidores", "pagamentos")
        data, nota = data_efetiva(info)
        r.prazo("Diretoria de Ensino", rotulo, data, PRAZO_LOCAL if local else PRAZO_DIARIO, nota +
                r.contagem("diretoria_" + chave, info.get("registros")) +
                ("; só atualiza pelo computador local (o portal recusa o GitHub)" if local else ""))
    folha = ler_json(os.path.join(DADOS, "diretoria", "folha.json")) or {}
    d = dias(folha.get("publicada_em"))
    if d is not None and d > 150:
        r.add("Diretoria de Ensino", "Folha do Estado: publicação", "aviso", folha.get("publicada_em"),
              f"o Estado não publica folha nova há {d} dias (atraso da fonte, não da coleta)")
    pag = ler_json(os.path.join(DADOS, "diretoria", "pagamentos.json")) or {}
    ate = ((pag.get("anos") or {}).get(str(ano)) or {}).get("ate_mes")
    if ate and ate < mes - 3:
        r.add("Diretoria de Ensino", f"Pagamentos {ano}: meses publicados", "aviso", None,
              f"a Secretaria só publicou até {ate:02d}/{ano}")

    return r


# ---------- saidas

RENDER = r"""
(function () {
  var S = window.SITUACAO; if (!S) return;
  var arq = (location.pathname.split("/").pop() || "index.html").replace(/\?.*$/, "");
  var PAG = {"index.html": ["Câmara"], "": ["Câmara"], "prefeitura.html": ["Prefeitura", "Câmara"],
             "dinheiro.html": ["Dinheiro"], "diretoria.html": ["Diretoria de Ensino"]};
  var quer = PAG[arq] || ["Câmara"];
  var itens = S.itens.filter(function (i) { return quer.indexOf(i.pagina) >= 0; });
  if (!itens.length) return;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function br(d) { if (!d) return "—"; var p = d.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
  var ROT = {ok: "em dia", aviso: "atenção", falha: "desatualizado"};
  var sec = document.createElement("section");
  sec.id = "situacao";
  sec.innerHTML = '<h2>Situação dos dados</h2><p class="sub">Quando cada fonte desta página foi coletada pela última vez com sucesso. Conferido em ' + br(S.gerado_em.slice(0, 10)) + '.</p>' +
    '<ul class="lista">' + itens.map(function (i) {
      return '<li class="item situacao-' + i.situacao + '"><div class="meta"><span class="selo">' + ROT[i.situacao] + "</span><span>" + esc(i.fonte) + "</span><span>última coleta: " + br(i.data) + "</span></div><p class=\"pequeno\">" + esc(i.detalhe) + "</p></li>";
    }).join("") + "</ul>";
  var main = document.querySelector("main");
  if (main) main.appendChild(sec);
})();
"""


def gravar_saidas(r):
    falhas = [i for i in r.itens if i["situacao"] == "falha"]
    avisos = [i for i in r.itens if i["situacao"] == "aviso"]
    saida = {"gerado_em": HOJE.isoformat(timespec="minutes"), "itens": r.itens,
             "falhas": len(falhas), "avisos": len(avisos), "contagens": r.contagens}
    os.makedirs(DADOS, exist_ok=True)
    with open(os.path.join(DADOS, "conferencia.json"), "w", encoding="utf-8") as arq:
        json.dump(saida, arq, ensure_ascii=False, indent=1)
    publico = {k: saida[k] for k in ("gerado_em", "itens", "falhas", "avisos")}
    with open(os.path.join(SITE, "situacao.js") + ".parcial", "w", encoding="utf-8") as arq:
        arq.write("window.SITUACAO = " + json.dumps(publico, ensure_ascii=False, separators=(",", ":")) + ";\n")
        arq.write(RENDER)
    os.replace(os.path.join(SITE, "situacao.js") + ".parcial", os.path.join(SITE, "situacao.js"))

    icone = {"ok": "🟢", "aviso": "🟡", "falha": "🔴"}
    linhas = ["## Situação dos dados", "",
              f"{len(falhas)} falha(s), {len(avisos)} aviso(s). Conferido em {HOJE:%d/%m/%Y %H:%M}.", "",
              "| | Página | Fonte | Última coleta boa | Detalhe |", "|---|---|---|---|---|"]
    for i in r.itens:
        linhas.append(f"| {icone[i['situacao']]} | {i['pagina']} | {i['fonte']} | {i['data'] or '—'} | {i['detalhe']} |")
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as arq:
            arq.write("\n".join(linhas) + "\n")
    return falhas, avisos


def main():
    r = conferir()
    falhas, avisos = gravar_saidas(r)
    marca = {"ok": "ok   ", "aviso": "AVISO", "falha": "FALHA"}
    for i in r.itens:
        print(f"  {marca[i['situacao']]}  {i['pagina']:20} {i['fonte'][:42]:42} {i['data'] or '—':10}  {i['detalhe']}")
    print(f"\n{len(falhas)} falha(s), {len(avisos)} aviso(s).")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
