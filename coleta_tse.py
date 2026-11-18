#!/usr/bin/env python3
"""
Sonar Sem Limites - fotos oficiais e votos de 2024 dos vereadores, pelo TSE.

Fonte: Portal de Dados Abertos do TSE (cdn.tse.jus.br), que abre de qualquer
rede. Os arquivos sao grandes (o de fotos de SP tem 2,2 GB), mas o servidor
aceita pedidos por trecho (HTTP Range): lemos so o indice do zip e os poucos
arquivos de Bauru. Nada alem disso e baixado.

  consulta_cand_2024.zip   -> lista de candidatos (so SP; so Bauru, vereador)
  votacao_candidato_munzona_2024.zip -> votos (so SP; so Bauru, vereador)
  foto_cand2024_SP_div.zip -> fotos (so os candidatos de Bauru que viraram vereadores)

Saida:
  dados/tse/candidatos_bauru_2024.json  (nome de urna, nome, partido, numero, votos, situacao)
  site/fotos/<cod_parlamentar>.jpg      (foto do registro de candidatura no TSE)

CPF, titulo de eleitor, data de nascimento e e-mail do arquivo do TSE sao
descartados na leitura.

Fotos e votos de 2024 nao mudam: depois da primeira coleta, so roda de novo
se faltar alguma foto ou com --refazer.

Uso:
    python coleta_tse.py
    python coleta_tse.py --refazer
"""

import csv
import io
import json
import os
import struct
import sys
import time
import urllib.request
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regras import sem_acento  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(RAIZ, "dados", "tse")
FOTOS = os.path.join(RAIZ, "site", "fotos")
CDN = "https://cdn.tse.jus.br/estatistica/sead"
CAND = CDN + "/odsele/consulta_cand/consulta_cand_2024.zip"
VOTOS = CDN + "/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2024.zip"
FOTOS_ZIP = CDN + "/eleicoes/eleicoes2024/fotos/foto_cand2024_SP_div.zip"
UA = "SonarSemLimites/0.2 (projeto cidadao de transparencia)"
MUNICIPIO = "BAURU"
GUARDAR = ["SQ_CANDIDATO", "NM_URNA_CANDIDATO", "NM_CANDIDATO", "NR_CANDIDATO", "SG_PARTIDO",
           "DS_SIT_TOT_TURNO", "DS_CARGO"]


# ---------- zip remoto, lido por trechos

def trecho(url, inicio, fim):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": f"bytes={inicio}-{fim}"})
    for n in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 206:
                    raise RuntimeError(f"servidor nao aceitou trecho (HTTP {resp.status})")
                return resp.read()
        except Exception:  # noqa: BLE001
            if n == 3:
                raise
            time.sleep(5 * (n + 1))


def tamanho(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return int(resp.headers["Content-Length"])


def indice(url):
    """Le o diretorio central do zip remoto (com suporte a ZIP64)."""
    total = tamanho(url)
    fim = trecho(url, max(0, total - 70000), total - 1)
    p = fim.rfind(b"PK\x05\x06")
    if p < 0:
        raise RuntimeError("fim do zip nao encontrado")
    _, _, _, _, n, tam_dir, ini_dir = struct.unpack("<IHHHHII", fim[p:p + 20])
    p64 = fim.rfind(b"PK\x06\x07")
    if p64 >= 0 and (ini_dir == 0xFFFFFFFF or n == 0xFFFF):
        off_eocd64 = struct.unpack("<Q", fim[p64 + 8:p64 + 16])[0]
        e = trecho(url, off_eocd64, off_eocd64 + 55)
        n, tam_dir, ini_dir = struct.unpack("<QQQ", e[32:56])
    d = trecho(url, ini_dir, ini_dir + tam_dir - 1)
    arquivos, i = {}, 0
    while i < len(d) and d[i:i + 4] == b"PK\x01\x02":
        metodo = struct.unpack("<H", d[i + 10:i + 12])[0]
        comp, real = struct.unpack("<II", d[i + 20:i + 28])
        ln, le, lc = struct.unpack("<HHH", d[i + 28:i + 34])
        off = struct.unpack("<I", d[i + 42:i + 46])[0]
        nome = d[i + 46:i + 46 + ln].decode("cp437")
        extra = d[i + 46 + ln:i + 46 + ln + le]
        j = 0
        while j + 4 <= len(extra):           # campo ZIP64 com tamanhos/offset reais
            tag, sz = struct.unpack("<HH", extra[j:j + 4])
            if tag == 1:
                vals, k = extra[j + 4:j + 4 + sz], 0
                if real == 0xFFFFFFFF:
                    real = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                if comp == 0xFFFFFFFF:
                    comp = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                if off == 0xFFFFFFFF:
                    off = struct.unpack("<Q", vals[k:k + 8])[0]
            j += 4 + sz
        arquivos[nome] = (off, comp, metodo)
        i += 46 + ln + le + lc
    return arquivos


def extrair(url, info):
    off, comp, metodo = info
    cab = trecho(url, off, off + 29)
    ln, le = struct.unpack("<HH", cab[26:30])
    ini = off + 30 + ln + le
    dados = trecho(url, ini, ini + comp - 1) if comp else b""
    return zlib.decompress(dados, -15) if metodo == 8 else dados


def csv_sp(url, prefixo):
    arqs = indice(url)
    nome = next(n for n in arqs if n.upper().startswith(prefixo.upper()) and n.upper().endswith("_SP.CSV"))
    print(f"  {nome} ...", end=" ", flush=True)
    texto = extrair(url, arqs[nome]).decode("latin-1")
    print("ok")
    return csv.DictReader(io.StringIO(texto), delimiter=";")


# ---------- regras

def chave_nome(txt):
    return " ".join(sem_acento(txt).replace(".", " ").split())


def carregar(nome):
    with open(os.path.join(RAIZ, "dados", nome + ".json"), encoding="utf-8") as arq:
        return json.load(arq)


def main():
    refazer = "--refazer" in sys.argv
    legs = carregar("legislatura")
    atual = max(l["num_legislatura"] for l in legs)
    cods = sorted({m["cod_parlamentar"] for m in carregar("mandato") if m["num_legislatura"] == atual})
    parl = {p["cod_parlamentar"]: p for p in carregar("parlamentar")}
    saida = os.path.join(PASTA, "candidatos_bauru_2024.json")
    faltam = [c for c in cods if not os.path.exists(os.path.join(FOTOS, f"{c}.jpg"))]
    if os.path.exists(saida) and not faltam and not refazer:
        print("TSE: fotos e votos de 2024 ja coletados (use --refazer para baixar de novo).")
        return 0

    try:
        print("TSE: candidatos a vereador em Bauru (2024)")
        cands = {}
        for x in csv_sp(CAND, "consulta_cand_2024"):
            if x["NM_UE"].strip().upper() == MUNICIPIO and "VEREADOR" in x["DS_CARGO"].upper():
                cands[x["SQ_CANDIDATO"]] = {k: x[k].strip() for k in GUARDAR}
        print(f"  {len(cands)} candidatos")
        votos = {}
        for x in csv_sp(VOTOS, "votacao_candidato_munzona_2024"):
            if x["NM_MUNICIPIO"].strip().upper() == MUNICIPIO and x["SQ_CANDIDATO"] in cands:
                votos[x["SQ_CANDIDATO"]] = votos.get(x["SQ_CANDIDATO"], 0) + int(x["QT_VOTOS_NOMINAIS"] or 0)
    except Exception as erro:  # noqa: BLE001
        print(f"TSE nao respondeu ({erro}). Mantido o que ja existe.", file=sys.stderr)
        return 1
    if len(cands) < 100:
        print(f"Lista de candidatos estranha ({len(cands)}). Mantido o que ja existe.", file=sys.stderr)
        return 1

    # Liga cada vereador do SAPL ao candidato do TSE pelo nome civil (ou de urna).
    por_nome = {}
    for sq, c in cands.items():
        c["votos"] = votos.get(sq, 0)
        por_nome.setdefault(chave_nome(c["NM_CANDIDATO"]), []).append(sq)
        por_nome.setdefault(chave_nome(c["NM_URNA_CANDIDATO"]), []).append(sq)
    ligados, sem_par = {}, []
    for cod in cods:
        p = parl.get(cod, {})
        achou = None
        for campo in ("nom_completo", "nom_parlamentar"):
            lista = por_nome.get(chave_nome(p.get(campo) or ""), [])
            if len(lista) == 1:
                achou = lista[0]
                break
        if not achou:
            # reserva: todas as palavras do nome do SAPL dentro do nome civil do TSE, e so um candidato assim
            palavras = set(chave_nome(p.get("nom_completo") or p.get("nom_parlamentar") or "").split())
            lista = [sq for sq, c in cands.items() if palavras and palavras <= set(chave_nome(c["NM_CANDIDATO"]).split())]
            if len(lista) == 1:
                achou = lista[0]
        if achou:
            ligados[cod] = achou
        else:
            sem_par.append(f"{cod} {p.get('nom_parlamentar')}")

    os.makedirs(FOTOS, exist_ok=True)
    fotos = 0
    try:
        arqs = indice(FOTOS_ZIP)
        por_sq = {}
        for nome in arqs:
            base = os.path.basename(nome).upper()
            for sq in ligados.values():
                if base.startswith(f"FSP{sq}"):
                    por_sq[sq] = nome
        for cod, sq in ligados.items():
            destino = os.path.join(FOTOS, f"{cod}.jpg")
            if os.path.exists(destino) and not refazer:
                fotos += 1
                continue
            if sq not in por_sq:
                continue
            img = extrair(FOTOS_ZIP, arqs[por_sq[sq]])
            if img[:3] != b"\xff\xd8\xff":
                continue
            with open(destino + ".parcial", "wb") as arq:
                arq.write(img)
            os.replace(destino + ".parcial", destino)
            fotos += 1
    except Exception as erro:  # noqa: BLE001
        print(f"  fotos: TSE nao respondeu ({erro}); seguem as que ja existem", file=sys.stderr)

    os.makedirs(PASTA, exist_ok=True)
    with open(saida + ".parcial", "w", encoding="utf-8") as arq:
        json.dump({"fonte": "https://dadosabertos.tse.jus.br/dataset/candidatos-2024",
                   "vereadores": {str(cod): cands[sq] for cod, sq in ligados.items()}},
                  arq, ensure_ascii=False, indent=1)
    os.replace(saida + ".parcial", saida)
    print(f"TSE: {len(ligados)} de {len(cods)} vereadores ligados ao registro do TSE; {fotos} fotos.")
    if sem_par:
        print("  sem par no TSE (nome diferente): " + "; ".join(sem_par))
    return 0


if __name__ == "__main__":
    sys.exit(main())
