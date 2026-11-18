#!/usr/bin/env python3
"""
Radar Bauru - baixa o arquivo ANUAL de despesas ou receitas do TCE-SP
(todos os municipios do estado) e guarda so as linhas de Bauru.

O arquivo de despesas tem ~2 GB por ano. Ele e lido em fluxo: o zip e
descompactado enquanto chega e so as linhas de Bauru vao para o disco.
Roda uma vez por ano, quando o TCE publica o ano fechado.

Uso:
    python coleta_tce_anual.py despesas 2025
    python coleta_tce_anual.py receitas 2025
"""

import os
import struct
import sys
import time
import urllib.request
import zlib

URL = "https://transparencia.tce.sp.gov.br/sites/default/files/conjunto-dados/{tipo}-{ano}.zip"
IBGE_BAURU = b"3506003"
NOME_BAURU = b"Bauru"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "tce")
UA = "RadarBauru/0.2 (projeto cidadao de transparencia)"


def main():
    tipo, ano = sys.argv[1], sys.argv[2]
    assert tipo in ("despesas", "receitas")
    os.makedirs(PASTA, exist_ok=True)
    destino = os.path.join(PASTA, f"{tipo}-{ano}-bauru.csv")
    parcial = destino + ".parcial"

    req = urllib.request.Request(URL.format(tipo=tipo, ano=ano), headers={"User-Agent": UA})
    inicio = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp, open(parcial, "wb") as saida:
        total = int(resp.headers.get("Content-Length", 0))
        cab = resp.read(30)
        if cab[:4] != b"PK\x03\x04":
            raise SystemExit("resposta nao e um zip")
        metodo, = struct.unpack("<H", cab[8:10])
        n_nome, n_extra = struct.unpack("<HH", cab[26:30])
        nome = resp.read(n_nome).decode(errors="replace")
        resp.read(n_extra)
        if metodo != 8:
            raise SystemExit(f"compressao {metodo} nao suportada")
        inflar = zlib.decompressobj(-15)
        resto = b""
        primeira = True
        lidos = 30 + n_nome + n_extra
        mantidas = 0
        ultimo_aviso = 0
        while True:
            bloco = resp.read(1 << 20)
            if not bloco:
                break
            lidos += len(bloco)
            dados = resto + inflar.decompress(bloco)
            linhas = dados.split(b"\n")
            resto = linhas.pop()
            for linha in linhas:
                if primeira:
                    saida.write(linha + b"\n")    # cabecalho
                    primeira = False
                    continue
                campos = linha.split(b";", 4)
                if len(campos) > 3 and (campos[3] == IBGE_BAURU or campos[2] == NOME_BAURU):
                    saida.write(linha + b"\n")
                    mantidas += 1
            if inflar.eof:
                break
            if total and lidos - ultimo_aviso > total / 20:
                ultimo_aviso = lidos
                print(f"  {100 * lidos / total:4.0f}%  {lidos / 1e6:7.0f} MB  "
                      f"{mantidas} linhas de Bauru", flush=True)
        if resto:
            campos = resto.split(b";", 4)
            if len(campos) > 3 and (campos[3] == IBGE_BAURU or campos[2] == NOME_BAURU):
                saida.write(resto + b"\n")
                mantidas += 1

    if mantidas == 0:
        os.remove(parcial)
        raise SystemExit("nenhuma linha de Bauru: nada foi salvo")
    os.replace(parcial, destino)
    print(f"{nome}: {mantidas} linhas de Bauru em {destino} "
          f"({os.path.getsize(destino) / 1e6:.1f} MB, {time.time() - inicio:.0f}s)")


if __name__ == "__main__":
    main()
