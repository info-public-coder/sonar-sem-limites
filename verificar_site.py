#!/usr/bin/env python3
"""
Sonar Sem Limites - confere as paginas do site num navegador sem janela (Edge ou
Chrome), na largura de um celular (412px). Rodar depois de QUALQUER mudanca
no site ou nos geradores.

Falha (codigo 1) se uma pagina tiver erro de JavaScript, nao desenhar as
secoes esperadas ou tiver rolagem lateral.

Uso:
    python verificar_site.py
"""

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent
SITE = RAIZ / "site"
NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

# pagina -> (seletor, minimo esperado)
PAGINAS = {
    "index.html": [("section", 5), (".cracha", 15), (".cracha .pilha", 10), ("#bairro .item", 1)],
    "dinheiro.html": [("section", 5), ("#fornecedores .item", 1), ("#areas li, #total .tile", 1)],
    "prefeitura.html": [("section", 3), (".cracha", 15), ("#prefeita .pilha", 1)],
    "diretoria.html": [("section", 6), ("#equipe .cracha", 5), ("#gastos .barras li", 3), ("#diarias .barras li", 2)],
}

MOLDURA = """<!doctype html><meta charset="utf-8"><body>
<iframe id="f" src="{url}" style="width:412px;height:900px;border:0"></iframe>
<pre id="o">SEM RESULTADO</pre>
<script>
f.onload = function () {{
  setTimeout(function () {{
    var d = f.contentDocument, r = [];
    {checagens}
    r.push("largura=" + d.documentElement.scrollWidth);
    o.textContent = "RESULTADO " + r.join(" ");
  }}, 1500);
}};
</script>"""


def navegador():
    for caminho in NAVEGADORES:
        if os.path.exists(caminho):
            return caminho
    # Linux (GitHub Actions traz o Google Chrome instalado)
    for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        achado = shutil.which(nome)
        if achado:
            return achado
    raise SystemExit("Edge/Chrome nao encontrado")


def verificar(exe, pagina, esperados, tmp):
    checagens = "".join(
        f'r.push("{i}=" + d.querySelectorAll({sel!r}).length);' for i, (sel, _) in enumerate(esperados))
    moldura = pathlib.Path(tmp) / f"moldura_{pagina}"
    moldura.write_text(MOLDURA.format(url=(SITE / pagina).as_uri(), checagens=checagens), encoding="utf-8")
    extra = [] if sys.platform == "win32" else ["--no-sandbox"]   # exigido no Linux do GitHub
    proc = subprocess.run(
        [exe, "--headless=new", "--disable-gpu", "--allow-file-access-from-files", *extra,
         "--disable-web-security", f"--user-data-dir={os.path.join(tmp, 'perfil')}", "--virtual-time-budget=8000",
         "--enable-logging=stderr", "--v=0", "--dump-dom", moldura.as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    problemas = []
    for linha in proc.stderr.splitlines():
        if "CONSOLE" in linha and ("Uncaught" in linha or "Error" in linha):
            problemas.append("erro de JavaScript: " + linha.split('"', 1)[-1][:200])
    m = re.search(r"RESULTADO ([^<]*)", proc.stdout)
    if not m:
        problemas.append("a pagina nao terminou de carregar")
        return problemas, ""
    valores = dict(p.split("=") for p in m.group(1).split())
    for i, (sel, minimo) in enumerate(esperados):
        n = int(valores.get(str(i), 0))
        if n < minimo:
            problemas.append(f"'{sel}': {n} (esperado >= {minimo})")
    if int(valores.get("largura", 0)) > 412:
        problemas.append(f"rolagem lateral: largura {valores['largura']}px > 412px")
    return problemas, m.group(1)


def main():
    exe = navegador()
    falhou = False
    with tempfile.TemporaryDirectory() as tmp:
        for pagina, esperados in PAGINAS.items():
            problemas, bruto = verificar(exe, pagina, esperados, tmp)
            if problemas:
                falhou = True
                print(f"FALHOU {pagina}:")
                for p in problemas:
                    print(f"  - {p}")
            else:
                print(f"ok     {pagina}  ({bruto})")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
