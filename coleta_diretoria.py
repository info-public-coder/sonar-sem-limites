#!/usr/bin/env python3
"""
Sonar Sem Limites - Unidade Regional de Ensino (URE) Bauru, a antiga Diretoria de Ensino.

Foco: a ADMINISTRACAO da URE (quem tem cargo, quanto recebe, o que a unidade
gasta e contrata). Nao coleta dados de alunos nem de escolas.

Fontes (todas oficiais e abertas; cada uma so substitui a anterior se vier boa):
  1. Site da URE Bauru (educacao.sp.gov.br/urebauru): nomes e funcoes publicados.
  2. Folha do Estado (transparencia.sp.gov.br, RemuneracaoAtivos.csv): nome,
     cargo e remuneracao. Nao tem lotacao: so guardamos (a) as linhas de quem
     esta no site da URE e (b) a mediana da remuneracao de cada cargo na
     Secretaria da Educacao. Nenhum outro nome e salvo.
  3. Cadastro de servidores ativos (dados.educacao.sp.gov.br, mensal,
     anonimizado): quantos servidores trabalham na SEDE da URE, por cargo.
     So contagens sao salvas (o arquivo traz data de nascimento: descartada).
  4. Pagamentos da Secretaria (dados.educacao.sp.gov.br, "ordem cronologica"):
     pagamentos cuja unidade e a URE Bauru (UG 080297). Diarias e locomocao
     sao pagas a pessoas: o nome so e guardado se a pessoa esta no site da
     URE; dos demais guardamos so o cargo (pela folha, se o nome for unico).
  5. Ausencias (dados.educacao.sp.gov.br, mensal, anonimizado): dias de
     ausencia por tipo, na sede da URE Bauru e nas sedes das outras URE.
  6. PNCP: contratos e contratacoes diretas da unidade 080297.

Uso:
    python coleta_diretoria.py

Portal de dados abertos da Secretaria: recusa o cliente HTTP do Python (403) e
aceita o curl; o coletor usa o curl para ele. Se um dia o curl tambem falhar,
baixe os arquivos pelo navegador e ponha em
dados/diretoria/manual/ com o nome original ("Base Servidores Ativos 1026.csv",
"Base Ausencias 0926.csv", "Pagamentos 2026_5.zip"...). O que estiver la e usado
no lugar do download.
"""

import collections
import csv
import datetime
import html
import io
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regras import sem_acento  # noqa: E402
import estado  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(RAIZ, "dados", "diretoria")
UA_NAVEGADOR = "Mozilla/5.0 (SonarSemLimites/0.2; projeto cidadao de transparencia)"
UG = "080297"
NOME_URE = "URE BAURU"
CNPJ_SEDUC = "46384111000140"
ANO_INICIAL = 2025

SITE_URE = "https://www.educacao.sp.gov.br/urebauru"
PAGINAS_URE = ["departamentos/coordenador", "departamentos/asure", "departamentos/ese",
               "departamentos/eec", "departamentos/seintec", "departamentos/segre",
               "departamentos/seafin", "departamentos/seafin/secomse", "departamentos/seafin/sefin",
               "departamentos/seom", "departamentos/seom/sefisc", "departamentos/sepes_menu",
               "departamentos/sepes_menu/seape", "departamentos/sepes_menu/sefrep",
               "departamentos/sepes_menu/sepes"]
FOLHA_PAGINA = "https://www.transparencia.sp.gov.br/PortalTransparencia-Report/Remuneracao.aspx"
FOLHA_CSV = "https://www.transparencia.sp.gov.br/PortalTransparencia-Report/txt/RemuneracaoAtivos.csv"
DADOS_SEDUC = "https://dados.educacao.sp.gov.br"
CONJ_SERVIDORES = DADOS_SEDUC + "/dataset/servidores-ativos-por-unidade"
CONJ_AUSENCIAS = DADOS_SEDUC + "/dataset/aus%C3%AAncias-por-servidor"
CONJ_PAGAMENTOS = DADOS_SEDUC + "/dataset/ordem-cronol%C3%B3gica-dos-pagamentos"
PNCP = "https://pncp.gov.br/api/consulta/v1"
MANUAL = os.path.join(PASTA, "manual")


def manuais(padrao):
    """Arquivos baixados a mao em dados/diretoria/manual/ que casam com o padrao."""
    if not os.path.isdir(MANUAL):
        return []
    return [os.path.join(MANUAL, n) for n in os.listdir(MANUAL)
            if re.search(padrao, sem_acento(n), re.I)]

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
# Mesmo cargo escrito de outro jeito no cadastro e na folha.
CARGO_ALIAS = {"PROFESSORDEENSINOFUNDAMENTALEMEDIO": "PROFENSINOFUNDAMENTALMEDIO"}
NATUREZAS_PESSOA = re.compile(r"diaria|locomoc")


def baixar_curl(url, timeout, tentativas):
    """O portal de dados abertos da Secretaria recusa o cliente HTTP do Python
    (HTTP 403) e aceita o curl, ferramenta padrao do Windows 10/11. Mesma
    identificacao do projeto, pausa entre arquivos e novas tentativas calmas."""
    ultimo = None
    for n in range(tentativas):
        r = subprocess.run(["curl", "-sSL", "--fail", "--max-time", str(timeout), "-A", UA_NAVEGADOR, url],
                           capture_output=True)
        if r.returncode == 0:
            time.sleep(3)
            return r.stdout
        ultimo = r.stderr.decode("utf-8", errors="replace").strip()
        if "404" in ultimo:
            break
        time.sleep(15 * (n + 1))
    raise RuntimeError(f"falhou: {url}: {ultimo}")


def baixar(url, timeout=300, tentativas=4):
    if url.startswith(DADOS_SEDUC):
        return baixar_curl(url, timeout, tentativas)
    req = urllib.request.Request(url, headers={"User-Agent": UA_NAVEGADOR})
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
            time.sleep(2)
            return corpo
        except urllib.error.HTTPError as erro:
            if 400 <= erro.code < 500 and erro.code != 429:
                raise
            ultimo = erro
        except Exception as erro:  # noqa: BLE001
            ultimo = erro
        time.sleep(10 * (n + 1))
    raise RuntimeError(f"falhou: {url}: {ultimo}")


def texto_html(corpo):
    s = corpo.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", s)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", s))
    return [l.strip() for l in t.split("\n") if l.strip()]


def chave(txt):
    return re.sub(r"[^A-Z0-9 ]", "", sem_acento(txt).upper()).strip()


PARTICULAS = {"DE", "DA", "DO", "DOS", "DAS", "E"}


def tokens(txt):
    return [t for t in chave(txt).split() if t not in PARTICULAS]


def mesmo_nome(site, folha_nome):
    """A folha abrevia nomes do meio ("NILCEIA MARIA A MARTELINE"), tira o "de" e
    corta em 30 letras. Aceita so se: primeiro e ultimo nome iguais (o ultimo pode
    estar cortado se o nome da folha tem 30 letras) e cada nome do meio da folha
    bate, na ordem, com um nome do site por extenso ou pela inicial."""
    s, f = tokens(site), tokens(folha_nome)
    if len(s) < 2 or len(f) < 2 or s[0] != f[0]:
        return False
    cortado = len(chave(folha_nome)) >= 30
    ultimo_ok = f[-1] == s[-1] or (cortado and s[-1].startswith(f[-1]) and len(f[-1]) >= 2)
    if not ultimo_ok:
        return False
    i = 1
    for t in f[1:-1]:
        while i < len(s) - 1 and not (t == s[i] or (len(t) == 1 and s[i].startswith(t))):
            i += 1
        if i >= len(s) - 1:
            return False
        i += 1
    return True


def chave_cargo(txt):
    k = re.sub(r"[^A-Z0-9]", "", sem_acento(txt).upper())
    return CARGO_ALIAS.get(k, k)


def valor(txt):
    txt = str(txt).strip()
    return float(txt.replace(".", "").replace(",", ".")) if txt else 0.0


def gravar(nome, dados):
    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, nome + ".json")
    with open(caminho + ".parcial", "w", encoding="utf-8") as arq:
        json.dump(dados, arq, ensure_ascii=False, indent=1)
    os.replace(caminho + ".parcial", caminho)


def quantidade(nome, dados):
    """Numero que resume cada fonte, para o conferir_dados.py notar quedas bruscas."""
    if nome == "equipe":
        return len(dados["pessoas"])
    if nome == "servidores":
        return dados["sede"]
    if nome == "folha":
        return len(dados["equipe"])
    if nome == "pagamentos":
        return sum(len(a["pagamentos"]) for a in dados["anos"].values())
    if nome == "pncp":
        return len(dados["contratos"])
    return None


def ler(nome):
    caminho = os.path.join(PASTA, nome + ".json")
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as arq:
        return json.load(arq)


def links_do_conjunto(pagina_conjunto, padrao):
    """Arquivos de um conjunto do portal de dados abertos (pagina -> recursos -> arquivo)."""
    corpo = baixar(pagina_conjunto).decode("utf-8", errors="replace")
    diretos = re.findall(r'href="(https://dados\.educacao\.sp\.gov\.br/sites/default/files/[^"]+)"', corpo)
    achados = [u for u in diretos if re.search(padrao, urllib.parse.unquote(u))]
    if achados:
        return achados
    recursos = []
    for href, titulo in re.findall(r'href="(/dataset/[^"]+/resource/[0-9a-f-]+)"[^>]*>\s*([^<]+?)\s*<', corpo):
        if re.search(padrao, titulo) and href not in recursos:
            recursos.append((href, titulo))
    return recursos


def arquivo_do_recurso(href):
    corpo = baixar(DADOS_SEDUC + href).decode("utf-8", errors="replace")
    urls = re.findall(r'https://dados\.educacao\.sp\.gov\.br/sites/default/files/[^"]+\.(?:csv|zip|xlsx)', corpo)
    return urls[0] if urls else None


# ---------- 1. equipe publicada no site da URE

NOME_PESSOA = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõçü]+(?: (?:de|da|do|dos|das|e|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-záéíóúâêôãõçü'.-]+)){1,7}$")
NAO_NOME = re.compile(r"(?i)secretaria|servi[cç]o|se[cç][aã]o|equipe|assessoria|resolu|unidade|ensino|"
                      r"atribui|telefone|e-mail|nome|plant|supervis|comiss|fala sp|transpar|termo|"
                      r"pol[ií]tica|governo|estado|coordenador|chefe|apoio|executivos|especialistas|"
                      r"constru|arquivos|curr[ií]culo|tecnologia|informa|frequ|pagamento|finan|visualizador|conte[uú]do|menu|a[cç][oõ]es|saiba")
ROTULOS = [
    (re.compile(r"(?i)dirigente regional"), "Dirigente Regional de Ensino (Coordenador Geral)"),
    (re.compile(r"(?i)^apoio"), "Apoio ao Gabinete"),
    (re.compile(r"(?i)executivos? p[uú]blicos?"), "Assessoria Técnica (Executivo Público)"),
    (re.compile(r"(?i)comiss[aã]o de atribui"), "Comissão de Atribuição de Aulas"),
    (re.compile(r"(?i)^chefe de servi[cç]o"), "Chefe de Serviço"),
    (re.compile(r"(?i)^chefe de se[cç][aã]o"), "Chefe de Seção"),
    (re.compile(r"(?i)^equipe"), "Equipe"),
]


def equipe_ure():
    pessoas, vistos = [], set()
    for pagina in PAGINAS_URE:
        url = f"{SITE_URE}/{pagina}"
        try:
            linhas = texto_html(baixar(url, timeout=60))
        except Exception as erro:  # noqa: BLE001
            print(f"    {pagina}: {erro}")
            continue
        marcas = [i for i, l in enumerate(linhas) if l.startswith("O máximo permitido é de 100")]
        if marcas:
            ini = marcas[0]
            setor = linhas[ini - 1]
        else:   # pagina sem o marcador (ex.: Supervisao): comeca no primeiro bloco de conteudo
            visos = [i for i, l in enumerate(linhas) if l == "Visualizador do Conteúdo da Web"]
            if not visos:
                continue
            ini = visos[0]
            setor = next((l for l in linhas if l.startswith("ESE") or l.startswith("EEC")), pagina)
        funcao = None
        for l in linhas[ini + 1:]:
            if l.startswith("Fala SP"):
                break
            if "Atribuições" in l or l.startswith("Z7_") or l == "Visualizador do Conteúdo da Web":
                funcao = None          # texto legal ou outro bloco: para de colher nomes
                continue
            for padrao, nome_funcao in ROTULOS:
                if padrao.search(l):
                    funcao = nome_funcao
                    break
            candidato = l.split(":", 1)[1].strip() if ":" in l else l
            candidato = re.split(r"\s+-\s+\(", candidato)[0].strip()
            if funcao and NOME_PESSOA.match(candidato) and not NAO_NOME.search(candidato):
                k = chave(candidato)
                if k in vistos:
                    continue
                vistos.add(k)
                pessoas.append({"nome": candidato, "funcao": funcao, "setor": setor, "fonte": url})
    if not any("Dirigente" in p["funcao"] for p in pessoas):
        raise ValueError("Dirigente nao encontrado no site da URE")
    return {"coletado_em": datetime.date.today().isoformat(), "fonte": SITE_URE, "pessoas": pessoas}


# ---------- 2. folha do Estado

def mes_da_folha():
    """O portal nao diz o mes do arquivo atual (so lista os meses antigos, em
    .rar). Usamos a data de publicacao que o proprio servidor informa."""
    req = urllib.request.Request(FOLHA_CSV, method="HEAD", headers={"User-Agent": UA_NAVEGADOR})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.headers.get("Last-Modified")
    return datetime.datetime.strptime(data, "%a, %d %b %Y %H:%M:%S GMT").date().isoformat() if data else None


def folha(equipe, cargos_sede):
    mes = mes_da_folha()
    corpo = baixar(FOLHA_CSV, timeout=900).decode("latin-1")
    leitor = csv.reader(io.StringIO(corpo), delimiter=";")
    cab = next(leitor)
    if len(cab) < 10 or "NOME" not in cab[0].upper():
        raise ValueError(f"cabecalho estranho: {cab}")
    # O nome na folha vem cortado em 30 caracteres.
    por_primeiro = collections.defaultdict(list)
    for p in equipe["pessoas"]:
        por_primeiro[tokens(p["nome"])[0]].append(p["nome"])
    candidatos = collections.defaultdict(lambda: collections.defaultdict(list))
    por_cargo = collections.defaultdict(list)
    linhas_equipe = collections.defaultdict(list)
    cargo_por_nome = collections.defaultdict(set)
    n = 0
    for c in leitor:
        if len(c) < 11 or "EDUCACAO" not in c[2].upper() or "FUNDACAO" in c[2].upper():
            continue
        n += 1
        k = chave(c[0])[:30]
        cargo_por_nome[k].add(c[1].strip())
        rem = valor(c[3])
        if rem > 0:
            por_cargo[chave_cargo(c[1])].append(rem)
        primeiro = k.split()[0] if k else ""
        for nome_site in por_primeiro.get(primeiro, []):
            if not mesmo_nome(nome_site, c[0]):
                continue
            candidatos[nome_site][c[0].strip()].append({
                "cargo": c[1].strip(), "remuneracao": valor(c[3]), "ferias_13": valor(c[4]),
                "eventuais": valor(c[5]), "licenca_premio": valor(c[6]), "indenizacoes": valor(c[7]),
                "redutor": valor(c[8]), "liquido": valor(c[9])})
    # So entra quem tem UM unico nome compativel na folha da Educacao (homonimo = sem salario).
    duvidosos = {}
    for nome_site, por_nome in candidatos.items():
        exatos = {k: v for k, v in por_nome.items() if tokens(k) == tokens(nome_site)}
        if len(exatos) == 1:            # nome inteiro igual vence as abreviacoes
            por_nome = exatos
        if len(por_nome) == 1:
            nome_folha, linhas = next(iter(por_nome.items()))
            linhas_equipe[nome_site] = [{**x, "nome_folha": nome_folha} for x in linhas]
        else:
            duvidosos[nome_site] = sorted(por_nome)
    if n < 100000:
        raise ValueError(f"folha com poucas linhas da Educacao ({n})")
    medianas = {k: {"mediana": round(statistics.median(v), 2), "n": len(v)}
                for k, v in por_cargo.items() if k in cargos_sede and len(v) >= 3}
    return {"publicada_em": mes, "fonte": FOLHA_PAGINA, "linhas_seduc": n, "homonimos": duvidosos,
            "equipe": linhas_equipe, "medianas": medianas,
            "nomes_procurados": sorted(p["nome"] for p in equipe["pessoas"]),
            "cargos_sede": sorted(cargos_sede)}, cargo_por_nome


class SemMudanca(Exception):
    """A fonte foi consultada e nao mudou: vale a versao anterior (dados)."""
    def __init__(self, dados):
        super().__init__("sem mudanca na fonte")
        self.dados = dados


def folha_sem_mudanca(equipe, cargos_sede):
    """Versao anterior da folha, se o Estado nao publicou arquivo novo e a lista
    de nomes da URE e os cargos da sede continuam os mesmos. Senao, None."""
    anterior = ler("folha")
    if not anterior:
        return None
    try:
        publicada = mes_da_folha()
    except Exception:  # noqa: BLE001
        return None
    if (anterior.get("publicada_em") == publicada
            and anterior.get("nomes_procurados") == sorted(p["nome"] for p in equipe["pessoas"])
            and set(cargos_sede) <= set(anterior.get("cargos_sede", []))):
        return anterior
    return None


def versao_arquivo(url):
    """Data e tamanho de um arquivo, sem baixar (cabecalho HTTP); para arquivo
    local, tamanho e data de modificacao."""
    if os.path.exists(url):
        return f"{os.path.getsize(url)}|{int(os.path.getmtime(url))}"
    r = subprocess.run(["curl", "-sSIL", "--max-time", "60", "-A", UA_NAVEGADOR, url], capture_output=True)
    texto = r.stdout.decode("latin-1", errors="replace")
    data = re.findall(r"(?im)^last-modified:\s*(.+?)\s*$", texto)
    tam = re.findall(r"(?im)^content-length:\s*(\d+)", texto)
    if r.returncode != 0 or not (data or tam):
        raise RuntimeError(f"nao deu para consultar a versao de {url}")
    return f"{tam[-1] if tam else '?'}|{data[-1] if data else '?'}"


# ---------- 3. servidores da sede (cadastro anonimizado)

def mes_do_arquivo(nome):
    m = re.search(r"(\d{2})(\d{2})\D*$", urllib.parse.unquote(nome).rsplit(".", 1)[0])
    return f"20{m.group(2)}-{m.group(1)}" if m else None


def ultimo_arquivo(conjunto, prefixo):
    locais = manuais(sem_acento(prefixo) + r" \d{4}")
    if locais:
        return sorted(locais, key=lambda u: mes_do_arquivo(u) or "")[-1]
    achados = links_do_conjunto(conjunto, prefixo + r" \d{4}")
    if achados and isinstance(achados[0], str):
        urls = achados
    else:
        urls = [arquivo_do_recurso(href) for href, _ in achados[:1]]
    urls = [u for u in urls if u]
    urls.sort(key=lambda u: mes_do_arquivo(u) or "", reverse=True)
    if not urls:
        raise ValueError(f"nenhum arquivo '{prefixo}' em {conjunto}")
    return urls[0]


def ler_csv_seduc(url):
    if os.path.exists(url):
        with open(url, "rb") as arq:
            corpo = arq.read()
    else:
        corpo = baixar(url, timeout=900)
    texto = corpo.decode("utf-8") if corpo[:3] == b"\xef\xbb\xbf" else corpo.decode("latin-1")
    leitor = csv.DictReader(io.StringIO(texto.lstrip("﻿").lstrip("ï»¿")), delimiter=";")
    return leitor


def servidores_sede():
    url = ultimo_arquivo(CONJ_SERVIDORES, "Base Servidores Ativos")
    anterior = ler("servidores")
    if anterior and anterior.get("arquivo") == os.path.basename(url) and "sedes" in anterior:
        raise SemMudanca(anterior)        # mesmo arquivo mensal ja processado
    por_cargo, quadro = collections.Counter(), collections.Counter()
    total_ure = sede = 0
    # De TODAS as URE: quantos trabalham na sede e com que codigo de unidade.
    # Serve de denominador para comparar as ausencias entre sedes.
    sedes_n, sedes_ua = collections.Counter(), collections.defaultdict(set)
    for x in ler_csv_seduc(url):
        de = (x.get("NOMEDE_E") or "").strip()
        na_sede = (x.get("LOCAL_UA") or "").strip() == "DE"
        if na_sede and de:
            sedes_n[de] += 1
            sedes_ua[de].add((x.get("UA_E") or "").strip())
        if de != NOME_URE:
            continue
        total_ure += 1
        if (x.get("LOCAL_UA") or "").strip() == "UE":
            continue
        sede += 1
        por_cargo[(x.get("NOMECAR_E") or "").strip()] += 1
        quadro[(x.get("QUADRO_E") or "").strip()] += 1
    if sede < 30 or total_ure < 1000:
        raise ValueError(f"contagem estranha: sede {sede}, URE {total_ure}")
    return {"mes": mes_do_arquivo(url), "fonte": CONJ_SERVIDORES, "arquivo": os.path.basename(url),
            "sede": sede, "escolas": total_ure - sede,
            "por_cargo": [[k, v, chave_cargo(k)] for k, v in por_cargo.most_common()],
            "quadro": dict(quadro),
            "sedes": {de: {"n": n, "ua": sorted(sedes_ua[de])} for de, n in sedes_n.items()}}


# ---------- 4. ausencias (anonimizado)

TIPOS_AUSENCIA = [("TT_DIAS_FALTA_MEDICA", "Falta médica"), ("TT_DIAS_FALTA_JUST", "Falta justificada"),
                  ("TT_DIAS_FALTA_INJUST", "Falta injustificada"), ("TT_DIAS_FALTA_ABONADA", "Falta abonada"),
                  ("TT_DIAS_LIC_PREMIO", "Licença-prêmio"), ("TT_DIAS_LIC_GESTANTE", "Licença-gestante"),
                  ("TT_DIAS_LIC_PATERNIDADE", "Licença-paternidade"),
                  ("TT_DIAS_LIC_ACID_TRAB", "Licença por acidente de trabalho"),
                  ("TT_DIAS_LIC_INTER_PARTIC", "Licença para interesses particulares")]


def ausencias(sede_info):
    """O arquivo de ausencias so lista quem teve ausencia no mes. Por isso a taxa
    usa como base TODOS os servidores da sede (cadastro): dias de ausencia /
    (servidores da sede x dias do mes). A sede de cada URE e achada pelo codigo
    da unidade (o mesmo do cadastro), nao pelo nome."""
    url = ultimo_arquivo(CONJ_AUSENCIAS, "Base Aus[eê]ncias")
    ua_para_ure = {ua: de for de, s in sede_info["sedes"].items() for ua in s["ua"] if ua}
    sedes = collections.defaultdict(lambda: {"com_ausencia": 0, "dias": 0, "tipos": collections.Counter()})
    dias_mes = 0
    for x in ler_csv_seduc(url):
        de = ua_para_ure.get((x.get("UA_EXERC") or "").strip())
        if not de:
            continue
        dias_mes = max(dias_mes, int(valor(x.get("TOTAL_DIAS_MES") or 0)))
        s = sedes[de]
        s["com_ausencia"] += 1
        s["dias"] += int(valor(x.get("TOT_DIAS_AUSENCIAS") or 0))
        for col, nome in TIPOS_AUSENCIA:
            s["tipos"][nome] += int(valor(x.get(col) or 0))
    if not dias_mes or len(sedes) < 50:
        raise ValueError(f"ausencias: so {len(sedes)} sedes identificadas")

    def taxa(de):
        n = sede_info["sedes"][de]["n"]
        return sedes[de]["dias"] / (n * dias_mes) if n else 0

    comparaveis = [de for de, s in sede_info["sedes"].items() if s["n"] >= 20]   # sedes muito pequenas distorcem
    taxas = sorted(taxa(de) for de in comparaveis)
    b = sedes[NOME_URE]
    n_bauru = sede_info["sedes"][NOME_URE]["n"]
    return {"mes": mes_do_arquivo(url), "fonte": CONJ_AUSENCIAS, "arquivo": os.path.basename(url),
            "bauru": {"servidores": n_bauru, "com_ausencia": b["com_ausencia"], "dias": b["dias"],
                      "dias_possiveis": n_bauru * dias_mes, "tipos": dict(b["tipos"])},
            "outras_sedes": {"quantidade": len(comparaveis), "mediana_taxa": round(statistics.median(taxas), 4),
                             "posicao": sum(1 for t in taxas if t < taxa(NOME_URE)) + 1}}


# ---------- 5. pagamentos da URE (UG 080297)

def indice_folha(cargo_por_nome):
    """Indice dos nomes da folha da Educacao por (primeiro, ultimo nome), para
    achar rapido os candidatos de cada nome. Nomes cortados em 30 letras (o
    ultimo nome pode estar pela metade) ficam tambem num indice so pelo primeiro."""
    por_par, cortados = collections.defaultdict(list), collections.defaultdict(list)
    for k in cargo_por_nome:
        t = tokens(k)
        if len(t) < 2:
            continue
        por_par[(t[0], t[-1])].append(k)
        if len(k) >= 30:
            cortados[t[0]].append(k)
    return por_par, cortados


def cargo_do_credor(credor, cargo_por_nome, indice):
    """Cargo de quem recebeu diaria, pela folha. Mesma regra dos cracha:
    primeiro e ultimo nome iguais, nomes do meio por extenso ou inicial. Se
    houver mais de uma pessoa compativel, so vale se todas tiverem o mesmo
    cargo; senao fica sem cargo."""
    k = chave(credor)[:30]
    if k in cargo_por_nome and len(cargo_por_nome[k]) == 1:
        return next(iter(cargo_por_nome[k]))
    t = tokens(credor)
    if len(t) < 2:
        return None
    por_par, cortados = indice
    candidatos = list(dict.fromkeys(c for c in por_par.get((t[0], t[-1]), []) + cortados.get(t[0], [])
                                    if mesmo_nome(credor, c)))
    if not candidatos:
        return None
    exatos = [c for c in candidatos if tokens(c) == t]
    if exatos:
        candidatos = exatos
    else:
        # O candidato que confere mais nomes do meio vence ("MARIA ISABEL CRISTINA C MORAES"
        # ganha de "MARIA CRISTINA DE MORAES" para "MARIA ISABEL CRISTINA CASTILHO DE MORAES").
        melhor = max(len(tokens(c)) for c in candidatos)
        candidatos = [c for c in candidatos if len(tokens(c)) == melhor]
    cargos = set()
    for c in candidatos:
        cargos |= cargo_por_nome[c]
    # "OUTROS VINCULOS" e um segundo vinculo da mesma pessoa, nao outro cargo
    cargos = {c for c in cargos if "OUTROS VINCULOS" not in c.upper()} or cargos
    if len(cargos) == 1:
        return next(iter(cargos))
    # Mais de um cargo possivel: guarda todos ("A|B"); o gerador decide se caem no mesmo grupo.
    return "|".join(sorted(cargos))


def pagamentos(equipe, obter_mapa):
    """obter_mapa() devolve o mapa nome->cargos da folha; so e chamado se os
    arquivos de pagamento mudaram (evita baixar a folha a toa)."""
    urls = manuais(r"Pagamentos \d{4}.*\.zip")
    if not urls:
        achados = links_do_conjunto(CONJ_PAGAMENTOS, r"Pagamentos \d{4}.*\.zip")
        urls = achados if achados and isinstance(achados[0], str) else []
    urls = [u for u in urls if int(re.search(r"Pagamentos (\d{4})", urllib.parse.unquote(u)).group(1)) >= ANO_INICIAL]
    versoes = {os.path.basename(urllib.parse.unquote(u)): versao_arquivo(u) for u in urls}
    nomes = sorted(p["nome"] for p in equipe["pessoas"])
    anterior = ler("pagamentos")
    if anterior and anterior.get("versoes") == versoes and anterior.get("nomes_equipe") == nomes:
        raise SemMudanca(anterior)        # nenhum arquivo do portal mudou
    cargo_por_nome = obter_mapa()
    nomes_equipe = {chave(p["nome"])[:30]: p["nome"] for p in equipe["pessoas"]}
    indice, cache_cargo = indice_folha(cargo_por_nome), {}
    por_ano = {}
    for url in urls:
        ano = int(re.search(r"Pagamentos (\d{4})", urllib.parse.unquote(url)).group(1))
        if ano < ANO_INICIAL:
            continue
        z = zipfile.ZipFile(url if os.path.exists(url) else io.BytesIO(baixar(url, timeout=900)))
        # Cada arquivo e acumulado ("ate setembro"); o zip pode trazer mais de um mes
        # por UG pagadora: fica so o mais recente de cada uma.
        melhor = {}
        for nome in z.namelist():
            m = re.search(r"UG (\d{6})(?:.*?at[eé] (\w+))?", sem_acento(nome), re.I)
            if not m or not nome.lower().endswith(".csv"):
                continue
            if m.group(2):
                mes = MESES.index(m.group(2).lower()) + 1 if m.group(2).lower() in MESES else 0
            else:
                mes = 12          # arquivo do ano fechado (ex.: "UG 080001 - ... - 2025.csv")
            if mes > melhor.get(m.group(1), (0, ""))[0]:
                melhor[m.group(1)] = (mes, nome)
        linhas, ate = [], 0
        for mes, nome in melhor.values():
            ate = max(ate, mes)
            bruto = z.read(nome)
            if bruto[:3] == b"\xef\xbb\xbf":
                bruto = bruto[3:]
            try:
                texto = bruto.decode("utf-8")
            except UnicodeDecodeError:          # alguns arquivos vem em Windows-1252
                texto = bruto.decode("cp1252", errors="replace")
            leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
            # 2025 usa espacos nos nomes das colunas e "FINALIDADE"; 2026 usa "_" e
            # "FINALIDADE_PROCESSO". Normaliza para um nome so.
            leitor.fieldnames = [re.sub(r"\s+", "_", c.strip().upper()).replace("FINALIDADE_PROCESSO", "FINALIDADE")
                                 for c in leitor.fieldnames]
            for x in leitor:
                if (x.get("CODIGO_UG_DOCUMENTO") or "").strip().zfill(6) != UG:
                    continue
                natureza = x["CODIGO_NOME_NATUREZA_DE_DESPESA"].strip()
                credor = x["NOME_CREDOR_FAVORECIDO"].strip()
                data = x["DATA_PAGAMENTO"].strip()[:10]
                if re.match(r"\d{2}/\d{2}/\d{4}", data):        # 2025 vem dd/mm/aaaa
                    data = f"{data[6:10]}-{data[3:5]}-{data[0:2]}"
                item = {"data": data, "natureza": natureza,
                        "valor": valor(x["VALOR_DOCUMENTO"]), "finalidade": (x.get("FINALIDADE") or "").strip()[:200]}
                if NATUREZAS_PESSOA.search(sem_acento(natureza)):
                    k = chave(credor)[:30]
                    item["pessoa"] = True
                    item["pessoa_id"] = abs(hash(("sonar", k))) % 10**9   # so para contar pessoas distintas
                    if k in nomes_equipe:
                        item["credor"] = nomes_equipe[k]
                    if credor not in cache_cargo:
                        cache_cargo[credor] = cargo_do_credor(credor, cargo_por_nome, indice)
                    item["cargo"] = cache_cargo[credor]
                else:
                    item["credor"] = credor
                linhas.append(item)
        if not linhas:
            raise ValueError(f"nenhum pagamento da UG {UG} em {ano}")
        por_ano[str(ano)] = {"ate_mes": ate, "arquivo": os.path.basename(url) if os.path.exists(url) else url,
                             "pagamentos": linhas}
    if not por_ano:
        raise ValueError("nenhum arquivo de pagamentos encontrado")
    return {"fonte": CONJ_PAGAMENTOS, "ug": UG, "anos": por_ano, "versoes": versoes, "nomes_equipe": nomes}


# ---------- 6. PNCP

def pncp_get(caminho, params):
    saida, pagina = [], 1
    while True:
        q = urllib.parse.urlencode({**params, "pagina": pagina, "tamanhoPagina": 50})
        req = urllib.request.Request(f"{PNCP}/{caminho}?{q}",
                                     headers={"User-Agent": "SonarSemLimites/0.2", "Accept": "application/json"})
        for n in range(5):
            try:
                with urllib.request.urlopen(req, timeout=150) as resp:
                    corpo = resp.read()
                break
            except urllib.error.HTTPError as erro:
                if 400 <= erro.code < 500:
                    raise
                time.sleep(10 * (n + 1))
            except Exception:  # noqa: BLE001
                time.sleep(10 * (n + 1))
        else:
            raise RuntimeError(f"PNCP nao respondeu: {caminho}")
        time.sleep(1)
        if not corpo.strip():
            return saida
        d = json.loads(corpo)
        saida += [x for x in d.get("data") or [] if (x.get("unidadeOrgao") or {}).get("codigoUnidade") == UG]
        if not d.get("paginasRestantes"):
            return saida
        pagina += 1


DIAS_ANO_FECHADO = 7   # ano encerrado: consulta o PNCP no maximo uma vez por semana


def pncp():
    hoje = datetime.date.today()
    contratos, diretas = [], []
    anterior = ler("pncp") or {}
    consultas = dict(anterior.get("anos_consultados") or {})
    limite = (datetime.datetime.now() - datetime.timedelta(days=DIAS_ANO_FECHADO)).isoformat()
    for ano in range(ANO_INICIAL, hoje.year + 1):
        if (ano < hoje.year and consultas.get(str(ano), "") > limite and "--tudo" not in sys.argv
                and any(c.get("ano_consulta") == ano for c in anterior.get("contratos", []))):
            # ano encerrado consultado ha menos de uma semana: reaproveita
            contratos += [c for c in anterior["contratos"] if c.get("ano_consulta") == ano]
            diretas += [d for d in anterior.get("diretas", []) if d.get("ano_consulta") == ano]
            print(f"    PNCP {ano}: ano encerrado, consultado ha menos de {DIAS_ANO_FECHADO} dias; reaproveitado")
            continue
        ini, fim = f"{ano}0101", min(datetime.date(ano, 12, 31), hoje).strftime("%Y%m%d")
        base = {"dataInicial": ini, "dataFinal": fim, "codigoUnidadeAdministrativa": UG}
        for x in pncp_get("contratos", {**base, "cnpjOrgao": CNPJ_SEDUC}):
            item = {k: x.get(k) for k in ("numeroControlePNCP", "numeroControlePncpCompra", "niFornecedor",
                                          "nomeRazaoSocialFornecedor", "tipoPessoa", "valorGlobal",
                                          "objetoContrato", "dataAssinatura", "dataVigenciaFim")}
            item["ano_consulta"] = ano
            contratos.append(item)
        for cod, nome in ((8, "Dispensa"), (9, "Inexigibilidade")):
            for x in pncp_get("contratacoes/publicacao", {**base, "codigoModalidadeContratacao": cod,
                                                         "cnpj": CNPJ_SEDUC}):
                diretas.append({"modalidade": nome, "numeroControlePNCP": x.get("numeroControlePNCP"),
                                "amparo": (x.get("amparoLegal") or {}).get("nome"),
                                "valor": x.get("valorTotalHomologado") or x.get("valorTotalEstimado"),
                                "objeto": x.get("objetoCompra"), "data": (x.get("dataPublicacaoPncp") or "")[:10],
                                "situacao": x.get("situacaoCompraNome"), "ano_consulta": ano})
        consultas[str(ano)] = datetime.datetime.now().isoformat(timespec="seconds")
    # Compra de origem de cada contrato (modalidade e amparo legal), inclusive de
    # anos anteriores a 2025: sem isso nao da para dizer como o contrato foi feito.
    ja = {d["numeroControlePNCP"] for d in diretas}
    # Modalidade e amparo de uma compra nao mudam depois de publicados: reaproveita
    # as ja consultadas e so pergunta ao PNCP pelas novas.
    compras = {k: v for k, v in ((ler("pncp") or {}).get("compras_origem") or {}).items() if v.get("modalidade")}
    ja |= set(compras)
    for ctrl in sorted({c["numeroControlePncpCompra"] for c in contratos if c.get("numeroControlePncpCompra")} - ja):
        m = re.match(r"(\d{14})-\d-(\d+)/(\d{4})", ctrl)
        if not m:
            continue
        url = f"{PNCP}/orgaos/{m.group(1)}/compras/{m.group(3)}/{int(m.group(2))}"
        req = urllib.request.Request(url, headers={"User-Agent": "SonarSemLimites/0.2", "Accept": "application/json"})
        x = None
        for n in range(4):                  # o PNCP responde 429/504 quando esta cheio: espera e tenta de novo
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    x = json.loads(resp.read())
                time.sleep(2)
                break
            except Exception:  # noqa: BLE001
                time.sleep(15 * (n + 1))
        if not x:
            continue
        compras[ctrl] = {"modalidade": x.get("modalidadeNome"), "numeroControlePNCP": ctrl,
                         "amparo": (x.get("amparoLegal") or {}).get("nome"),
                         "valor": x.get("valorTotalHomologado") or x.get("valorTotalEstimado"),
                         "objeto": x.get("objetoCompra"), "data": (x.get("dataPublicacaoPncp") or "")[:10],
                         "situacao": x.get("situacaoCompraNome")}
    for x in contratos:
        if x["tipoPessoa"] == "PF":
            x["niFornecedor"] = None       # CPF nunca e salvo
    return {"fonte": "https://pncp.gov.br/app/", "ug": UG, "contratos": contratos, "diretas": diretas,
            "compras_origem": compras, "anos_consultados": consultas}


# ---------- principal

def main():
    falhas = []

    def etapa(nome, funcao):
        print(f"  {nome} ...", flush=True)
        try:
            dados = funcao()
        except SemMudanca as sem:
            # Consultada e igual: mantem a versao anterior e registra so a verificacao.
            print("    sem mudanca na fonte; mantida a versao anterior")
            estado.verificar(PASTA, nome)
            return sem.dados
        except Exception as erro:  # noqa: BLE001
            print(f"    FALHOU: {erro} (mantida a versao anterior)", file=sys.stderr)
            falhas.append(nome)
            return ler(nome)
        gravar(nome, dados)
        estado.registrar(PASTA, nome, quantidade(nome, dados))
        return dados

    print("URE Bauru - coletando")
    equipe = etapa("equipe", equipe_ure)
    sede = etapa("servidores", servidores_sede)
    mapa = {}                       # nome->cargos da folha (so existe se a folha foi baixada)

    def baixar_folha():
        dados, m = folha(equipe, {c[2] for c in sede["por_cargo"]})
        mapa["valor"] = m
        return dados

    def obter_mapa():
        if "valor" not in mapa:     # folha nao mudou, mas os pagamentos sim: baixa a folha agora
            print("  folha (para ligar diarias a cargos) ...", flush=True)
            dados = baixar_folha()
            gravar("folha", dados)
            estado.registrar(PASTA, "folha", quantidade("folha", dados))
        return mapa["valor"]

    if equipe and sede:
        def etapa_folha():
            anterior = folha_sem_mudanca(equipe, {c[2] for c in sede["por_cargo"]})
            if anterior:
                raise SemMudanca(anterior)
            return baixar_folha()
        etapa("folha", etapa_folha)
    # Ausencias: NAO coletadas. O boletim de frequencia quase nao registra a equipe
    # das sedes (09/2026: 1 servidor com ausencia entre 123 na sede de Bauru;
    # so 38 das 93 sedes aparecem). Mostrar isso sugeriria uma equipe que nunca
    # falta. A funcao ausencias() fica para quando o dado melhorar.
    if equipe and sede:
        etapa("pagamentos", lambda: pagamentos(equipe, obter_mapa))
    else:
        print("  pagamentos: pulado (precisa da equipe e dos servidores)")
        falhas.append("pagamentos")
    etapa("pncp", pncp)
    gravar("coleta", {"fim": datetime.datetime.now().isoformat(timespec="seconds"), "falhas": falhas})
    print("Terminou" + (f" com falhas em: {', '.join(falhas)}" if falhas else " sem falhas."))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
