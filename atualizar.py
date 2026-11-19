#!/usr/bin/env python3
"""
Sonar Sem Limites - atualiza tudo, na ordem certa, e confere as paginas no fim.

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
# Tempo maximo de cada script. O PNCP e lento e cai com frequencia: a coleta de
# gastos ganha 2 horas; os demais, 1 hora.
LIMITE_SEGUNDOS = {"coleta_gastos.py": 7200}


def rodar(script, obrigatorio):
    print(f"\n=== {script} ===", flush=True)
    try:
        # Limite de 1 hora: um servidor que trava a conexao nao pode segurar o resto.
        limite = LIMITE_SEGUNDOS.get(script, 3600)
        codigo = subprocess.call([sys.executable, "-u", os.path.join(RAIZ, script)], cwd=RAIZ, timeout=limite)
    except subprocess.TimeoutExpired:
        print(f"--- {script} passou do limite de {limite // 60} minutos e foi interrompido", flush=True)
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
    else:
        # Nao bloqueia a publicacao: so mostra (e grava) o que esta velho ou faltando.
        resultado["conferir_dados.py"] = rodar("conferir_dados.py", False)
    print("\n=== resumo ===")
    for script, codigo in resultado.items():
        print(f"  {'ok   ' if codigo == 0 else 'FALHA'}  {script}")
    if resultado.get("coleta.py"):
        print("  (Camara sem coleta nova: o site mostra a ultima coleta boa. Se for bloqueio de rede,"
              " conecte o PC no roteador do celular e rode de novo.)")
    obrigatorios = ("gerar_site.py", "gerar_dinheiro.py", "gerar_prefeitura.py", "gerar_diretoria.py", "verificar_site.py")
    falhou = any(resultado.get(s) for s in obrigatorios)
    if not falhou and not os.environ.get("GITHUB_ACTIONS"):
        renovar_semente()
    return 1 if falhou else 0


# Fontes que recusam os servidores do GitHub: a copia processada vai para
# semente/, que o robo usa quando a coleta de la falha (ver semente/LEIA-ME.md).
SEMENTE = {
    "prefeitura": ["equipe.json"],
    "diretoria": ["equipe.json", "folha.json", "servidores.json", "pagamentos.json", "pncp.json", "estado.json"],
    # PNCP: o GitHub consegue coletar, mas o servidor cai muito; a semente evita pagina vazia.
    "gastos": ["pncp_*.json", "estado.json"],
}


def renovar_semente():
    import glob
    import shutil
    copiados = 0
    for pasta, arquivos in SEMENTE.items():
        os.makedirs(os.path.join(RAIZ, "semente", pasta), exist_ok=True)
        for padrao in arquivos:
            for origem in glob.glob(os.path.join(RAIZ, "dados", pasta, padrao)):
                shutil.copy2(origem, os.path.join(RAIZ, "semente", pasta, os.path.basename(origem)))
                copiados += 1
    print(f"  semente/ renovada ({copiados} arquivos). Envie para o GitHub para o robo usar.")


if __name__ == "__main__":
    sys.exit(main())
