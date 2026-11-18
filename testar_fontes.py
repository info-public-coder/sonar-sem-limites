#!/usr/bin/env python3
"""
Sonar Sem Limites - testa se cada fonte responde a partir da maquina onde roda.

Faz UMA requisicao leve por fonte e mostra o resultado. Serve para saber, por
exemplo, se o servidor da Camara aceita conexoes do GitHub Actions.

Uso:
    python testar_fontes.py
Sai com codigo 0 sempre (e um diagnostico, nao uma trava).
"""

import subprocess
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (SonarSemLimites/0.2; projeto cidadao de transparencia)"

FONTES = [
    ("Camara (SAPL, API)", "https://sapl.bauru.sp.leg.br/api/legislatura.limit(1)/:json", "python"),
    ("TCE-SP (API mensal)", "https://transparencia.tce.sp.gov.br/api/json/despesas/bauru/2026/1", "python"),
    ("PNCP (contratos)", "https://pncp.gov.br/api/consulta/v1/contratos?dataInicial=20260101&dataFinal=20260131"
                         "&cnpjOrgao=46137410000180&pagina=1&tamanhoPagina=10", "python"),
    ("Prefeitura (equipe de governo)", "https://www2.bauru.sp.gov.br/equipe_governo.aspx", "python"),
    ("URE Bauru (site)", "https://www.educacao.sp.gov.br/urebauru/departamentos/coordenador", "python"),
    ("Folha do Estado (pagina)", "https://www.transparencia.sp.gov.br/PortalTransparencia-Report/Remuneracao.aspx", "python"),
    ("Dados abertos SEDUC (curl)", "https://dados.educacao.sp.gov.br/dataset/ordem-cronol%C3%B3gica-dos-pagamentos", "curl"),
    ("TSE (dados abertos)", "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip", "head"),
]


def testar(url, modo):
    inicio = time.time()
    try:
        if modo == "curl":
            r = subprocess.run(["curl", "-sS", "-o", "/dev/null" if sys.platform != "win32" else "NUL",
                                "-w", "%{http_code}", "--max-time", "60", "-A", UA, url],
                               capture_output=True, text=True)
            codigo = r.stdout.strip() or r.stderr.strip()
        else:
            metodo = "HEAD" if modo == "head" else "GET"
            req = urllib.request.Request(url, method=metodo, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                if metodo == "GET":
                    resp.read(2048)
                codigo = str(resp.status)
    except Exception as erro:  # noqa: BLE001
        codigo = f"ERRO: {erro}"
    return codigo, time.time() - inicio


def main():
    print(f"{'Fonte':34} {'Resultado':40} Tempo")
    for nome, url, modo in FONTES:
        codigo, segundos = testar(url, modo)
        ok = codigo.startswith("2")
        print(f"{nome:34} {('ok ' if ok else 'FALHA ') + codigo:40} {segundos:5.1f}s", flush=True)
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
