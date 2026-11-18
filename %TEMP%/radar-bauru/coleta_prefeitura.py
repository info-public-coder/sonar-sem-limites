#!/usr/bin/env python3
"""
Radar Bauru - equipe de governo da Prefeitura (Prefeita, vice e secretarios).

Fonte oficial: pagina "Equipe de Governo" do site da Prefeitura
(https://www2.bauru.sp.gov.br/equipe_governo.aspx). Guarda cargo, nome,
telefone e endereco da secretaria, o resumo de curriculo publicado pela
Prefeitura e a foto oficial (site/fotos/pref-<id>.jpg).

So substitui dados/prefeitura/equipe.json se vier completo (10+ pessoas,
com a Prefeita). Abre da rede de casa.

Uso:
    python coleta_prefeitura.py
"""

import datetime
import html
import json
import os
import re
import sys
import time
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(RAIZ, "dados", "prefeitura")
FOTOS = os.path.join(RAIZ, "site", "fotos")
SITE = "https://www2.bauru.sp.gov.br"
PAGINA = SITE + "/equipe_governo.aspx"
UA = "RadarBauru/0.2 (projeto cidadao de transparencia)"
PAUSA = 1.0


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        corpo, tipo = resp.read(), resp.headers.get("Content-Type", "")
    time.sleep(PAUSA)
    return corpo, tipo


def texto(trecho):
    t = re.sub(r"(?i)<br\s*/?>", "\n", trecho)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"[ \t\xa0]+", " ", t).strip()


def ler_equipe(pagina):
    pessoas = []
    for bloco in re.findall(r'(?s)<div class="row mt-2">(.*?)</div></div>', pagina):
        cargo = re.search(r"(?s)<h3>(.*?)</h3>", bloco)
        nome = re.search(r"(?s)<p><b>(.*?)</b></p>", bloco)
        if not cargo or not nome:
            continue
        foto = re.search(r"src='([^']+/equipe_governo/(\d+)\.\w+)'", bloco)
        link = re.search(r'<a href="(/[^"]+)"><h3>', bloco)
        fones = [texto(f) for f in re.findall(r'<a href="tel:[^"]+">(.*?)</a>', bloco)]
        depois_fone = bloco.split("<p><b>", 1)[1].split("</b></p>", 1)[1]
        paragrafos = [texto(p) for p in re.findall(r"(?s)<p>(.*?)</p>", depois_fone)]
        sem_p = re.sub(r"(?s)<p>.*?</p>", "", depois_fone)
        linhas = [l.strip() for l in texto(sem_p).split("\n") if l.strip()]
        endereco = next((l for l in linhas if not l.startswith("Fone") and "/" != l and not re.match(r"^[\d() /-]+$", l)), "")
        pessoas.append({
            "id": foto.group(2) if foto else None,
            "cargo": texto(cargo.group(1)),
            "nome": texto(nome.group(1)),
            "fones": fones,
            "endereco": endereco,
            "curriculo": "\n".join(p for p in paragrafos if p),
            "pagina": SITE + link.group(1) if link else None,
            "foto_url": SITE + foto.group(1) if foto else None,
        })
    return pessoas


def main():
    try:
        corpo, _ = baixar(PAGINA)
    except Exception as erro:  # noqa: BLE001
        print(f"Site da Prefeitura nao respondeu ({erro}). Mantida a versao anterior.")
        return 2
    pessoas = ler_equipe(corpo.decode("utf-8", errors="replace"))
    if len(pessoas) < 10 or not any(p["cargo"].lower().startswith("prefeit") for p in pessoas):
        print(f"Pagina veio estranha ({len(pessoas)} pessoas). Mantida a versao anterior.", file=sys.stderr)
        return 1

    os.makedirs(FOTOS, exist_ok=True)
    fotos = 0
    for p in pessoas:
        p["foto"] = False
        if not p["foto_url"]:
            continue
        destino = os.path.join(FOTOS, f"pref-{p['id']}.jpg")
        try:
            img, tipo = baixar(p["foto_url"])
        except Exception:  # noqa: BLE001
            p["foto"] = os.path.exists(destino)   # fica a ultima foto boa
            continue
        if tipo.startswith("image/") or img[:3] == b"\xff\xd8\xff":
            with open(destino + ".parcial", "wb") as arq:
                arq.write(img)
            os.replace(destino + ".parcial", destino)
            p["foto"] = True
            fotos += 1

    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, "equipe.json")
    with open(caminho + ".parcial", "w", encoding="utf-8") as arq:
        json.dump({"fonte": PAGINA, "coletado_em": datetime.datetime.now().isoformat(timespec="minutes"),
                   "pessoas": pessoas}, arq, ensure_ascii=False, indent=1)
    os.replace(caminho + ".parcial", caminho)
    print(f"Equipe de governo: {len(pessoas)} pessoas, {fotos} fotos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
