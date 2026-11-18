#!/usr/bin/env python3
"""
Radar Bauru - atualiza tudo, na ordem certa, e confere as paginas no fim.

  1. coleta.py          Camara (SAPL). Se o servidor nao responder (ele bloqueia
                        algumas redes), mantem os dados da ultima coleta boa.
  2. coleta_gastos.py   TCE-SP (ano corrente) e PNCP. Cada fonte so substitui a
                        anterior se vier completa.
  3. gerar_site.py      site/dados.js     (pagina Camara)
  4. gerar_dinheiro.py  site/dinheiro.js  (pagina Dinheiro)
  5. verificar_site.py  abre as paginas num navegador sem janela e confere

O arquivo anual do TCE (coleta_tce_anual.py) NAO roda aqui: ~2 GB, uma vez por
ano, quando o TCE publica o ano fechado.

Uso:
    python atualizar.py               tudo
    python atualizar.py --sem-coleta  so gera e confere (usa os dados que ja existem)
"""

import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))


def rodar(script, obrigatorio):
    print(f"\n=== {script} ===", flush=True)
    try:
        # Limite de 1 hora: um servidor que trava a conexao nao pode segurar o resto.
        codigo = subprocess.call([sys.executable, "-u", os.path.join(RAIZ, script)], cwd=RAIZ, timeout=3600)
    except subprocess.TimeoutExpired:
        print(f"--- {script} passou de 1 hora e foi interrompido", flush=True)
        codigo = 124
    if codigo != 0:
        aviso = "ERRO" if obrigatorio else "aviso"
        print(f"--- {aviso}: {script} terminou com codigo {codigo}", flush=True)
    return codigo


def main():
    resultado = {}
    if "--sem-coleta" not in sys.argv:
        resultado["coleta.py"] = rodar("coleta.py", False)
        resultado["coleta_tse.py"] = rodar("coleta_tse.py", False)
        resultado["coleta_prefeitura.py"] = rodar("coleta_prefeitura.py", False)
        resultado["coleta_diretoria.py"] = rodar("coleta_diretoria.py", False)
        resultado["coleta_gastos.py"] = rodar("coleta_gastos.py", False)
    for script in ("gerar_site.py", "gerar_dinheiro.py", "gerar_prefeitura.py", "gerar_diretoria.py", "verificar_site.py"):
        resultado[script] = rodar(script, True)
        if resultado[script] != 0:
            break
    print("\n=== resumo ===")
    for script, codigo in resultado.items():
        print(f"  {'ok   ' if codigo == 0 else 'FALHA'}  {script}")
    if resultado.get("coleta.py"):
        print("  (Camara sem coleta nova: o site mostra a ultima coleta boa. Se for bloqueio de rede,"
              " conecte o PC no roteador do celular e rode de novo.)")
    obrigatorios = ("gerar_site.py", "gerar_dinheiro.py", "gerar_prefeitura.py", "gerar_diretoria.py", "verificar_site.py")
    return 1 if any(resultado.get(s) for s in obrigatorios) else 0


if __name__ == "__main__":
    sys.exit(main())
