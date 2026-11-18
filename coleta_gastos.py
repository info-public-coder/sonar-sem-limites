#!/usr/bin/env python3
"""
Sonar Sem Limites - coleta de gastos e contratos (fontes que nao sao a Camara).

  1. TCE-SP, API mensal por municipio: despesas de Bauru do ano corrente
     (o ano anterior, completo e detalhado, vem de coleta_tce_anual.py).
  2. PNCP: contratos e contratacoes diretas (dispensa e inexigibilidade) do
     Municipio de Bauru (CNPJ 46.137.410/0001-80), desde 2025.

Mesmas travas da coleta da Camara: pausa entre chamadas, nao repete erro 4xx,
confere contagens, e so troca dados/gastos/ se tudo der certo.

Uso:
    python coleta_gastos.py             tudo
    python coleta_gastos.py --ano 2026  so o PNCP desse ano (e o TCE do ano corrente)
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
import estado  # noqa: E402
PASTA = os.path.join(RAIZ, "dados", "gastos")
TCE = "https://transparencia.tce.sp.gov.br/api/json/{tipo}/bauru/{ano}/{mes}"
PNCP = "https://pncp.gov.br/api/consulta/v1"
CNPJ_PREFEITURA = "46137410000180"
ANO_INICIAL = 2025
PAUSA = 1.0
UA = "SonarSemLimites/0.2 (projeto cidadao de transparencia)"
POR_PAGINA = 50
MODALIDADES_DIRETAS = {8: "Dispensa", 9: "Inexigibilidade"}


def baixar(url, tentativas=5, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    ultimo = None
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
                status = resp.status
            time.sleep(PAUSA)
            if status == 204 or not corpo.strip():
                return None
            return json.loads(corpo.decode("utf-8"))
        except urllib.error.HTTPError as erro:
            if 400 <= erro.code < 500:
                time.sleep(PAUSA)
                raise
            ultimo = erro
        except Exception as erro:  # noqa: BLE001
            ultimo = erro
        espera = 10 * n
        print(f"\n    tentativa {n}/{tentativas} falhou ({ultimo}); esperando {espera}s", file=sys.stderr)
        time.sleep(espera)
    raise RuntimeError(f"falhou: {url}: {ultimo}")


def tce_ano_corrente(tipo, ano):
    """Baixa mes a mes ate o primeiro mes vazio. Devolve {mes: registros}."""
    meses = {}
    for mes in range(1, 13):
        print(f"  TCE {tipo} {ano}/{mes:02d} ...", end=" ", flush=True)
        try:
            dados = baixar(TCE.format(tipo=tipo, ano=ano, mes=mes))
        except urllib.error.HTTPError as erro:
            print(f"HTTP {erro.code}, parando")
            break
        if not dados:
            print("vazio, parando")
            break
        meses[mes] = dados
        print(f"{len(dados)} registros")
    return meses


def pncp_paginado(caminho, params):
    saida, pagina, total = [], 1, None
    while True:
        q = "&".join(f"{k}={v}" for k, v in {**params, "pagina": pagina,
                                              "tamanhoPagina": POR_PAGINA}.items())
        dados = baixar(f"{PNCP}/{caminho}?{q}")
        if not dados or dados.get("empty"):
            break
        total = dados.get("totalRegistros")
        saida.extend(dados.get("data") or [])
        if pagina % 10 == 0:
            print(f"pag {pagina}/{dados.get('totalPaginas')}", end=" ", flush=True)
        if not dados.get("paginasRestantes"):
            break
        pagina += 1
    if total is not None and len(saida) != total:
        raise ValueError(f"PNCP {caminho}: esperava {total}, vieram {len(saida)}")
    return saida


def gravar(nome, dados):
    """Grava UM arquivo de forma atomica: so substitui o anterior se completo."""
    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, nome + ".json")
    with open(caminho + ".parcial", "w", encoding="utf-8") as arq:
        json.dump(dados, arq, ensure_ascii=False)
    os.replace(caminho + ".parcial", caminho)


def main():
    """Cada fonte e gravada assim que termina. Se uma falhar, as outras ficam
    atualizadas e a que falhou continua com a ultima versao boa."""
    hoje = datetime.date.today()
    falhas, registros = [], {}

    def etapa(nome, funcao, valida):
        try:
            dados = funcao()
            if not valida(dados):
                raise ValueError("dados vazios ou estranhos")
        except Exception as erro:  # noqa: BLE001
            print(f"\n  FALHOU {nome}: {erro} (mantida a versao anterior)", file=sys.stderr)
            falhas.append(nome)
            return
        gravar(nome, dados)
        registros[nome] = (sum(len(m) for m in dados["meses"].values())
                           if isinstance(dados, dict) else len(dados))
        estado.registrar(PASTA, nome, registros[nome])
        print(f"  gravado {nome}: {registros[nome]} registros")

    etapa("tce_despesas_ano_corrente",
          lambda: {"ano": hoje.year, "meses": tce_ano_corrente("despesas", hoje.year)},
          lambda d: bool(d["meses"]))

    anos = range(ANO_INICIAL, hoje.year + 1)
    if "--ano" in sys.argv:
        anos = [int(sys.argv[sys.argv.index("--ano") + 1])]
    for ano in anos:
        ini, fim = f"{ano}0101", min(datetime.date(ano, 12, 31), hoje).strftime("%Y%m%d")
        print(f"  PNCP contratos {ano} ...", end=" ", flush=True)
        etapa(f"pncp_contratos_{ano}",
              lambda: pncp_paginado("contratos", {"dataInicial": ini, "dataFinal": fim,
                                                  "cnpjOrgao": CNPJ_PREFEITURA}),
              lambda d: len(d) > 0)
        for cod, nome in MODALIDADES_DIRETAS.items():
            print(f"  PNCP {nome} {ano} ...", end=" ", flush=True)
            etapa(f"pncp_{nome.lower()}_{ano}",
                  lambda: pncp_paginado("contratacoes/publicacao",
                                        {"dataInicial": ini, "dataFinal": fim,
                                         "codigoModalidadeContratacao": cod,
                                         "cnpj": CNPJ_PREFEITURA}),
                  lambda d: isinstance(d, list))

    manifesto = os.path.join(PASTA, "coleta.json")
    anterior = {}
    if os.path.exists(manifesto):
        with open(manifesto, encoding="utf-8") as arq:
            anterior = json.load(arq)
    registros = {**anterior.get("registros", {}), **registros}
    with open(manifesto, "w", encoding="utf-8") as arq:
        json.dump({"fim": datetime.datetime.now().isoformat(timespec="seconds"),
                   "registros": registros, "falhas": falhas}, arq, ensure_ascii=False, indent=1)
    if falhas:
        print("\nTerminou com falhas em: " + ", ".join(falhas), file=sys.stderr)
        return 1
    print(f"\nColeta de gastos completa. Salvo em {PASTA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
