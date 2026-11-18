#!/usr/bin/env python3
"""
Sonar Sem Limites - numeros por vereador no terminal, para conferir com a ficha
oficial. Usa exatamente o mesmo calculo do site (gerar_site.montar).

Uso:
    python resumo.py                    tabela com todos em exercicio
    python resumo.py NOME [NOME ...]    ficha detalhada (busca parcial no nome)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gerar_site  # noqa: E402
import regras  # noqa: E402


def br(d):
    return "/".join(reversed(d.split("-"))) if d else "-"


def ficha(s, v):
    p = v["propostas"]
    print(f"\n{v['nome']} ({v['partido']})")
    print(f"  Fonte oficial: {v['fonte']}")
    print(f"  Mandato: {br(v['inicio'])} a {br(v['fim'])}")
    print(f"  Sessoes com chamada no periodo: {v['sessoes']}")
    print(f"    presente {v['presente']} | falta {v['falta']} | justificada {v['justificada']}"
          f" | sem registro {v['sem_registro']}" + (f" | outro {v['outro']}" if v["outro"] else ""))
    print("  Propostas assinadas so por ele:")
    for g, nome in regras.GRUPOS.items():
        print(f"    {nome:28} {p.get(g, 0)}")
    print(f"  Coautorias: {v['coautorias']}")
    t = v["votos"]
    print(f"  Votos nas {s['votacoes']['nominais']} votacoes nominais: {t or 'nenhum registrado'}")


def main():
    try:
        s, _ = gerar_site.montar()
    except FileNotFoundError as erro:
        print(f"Faltam dados ({erro.filename}). Rode antes: python coleta.py")
        return 1
    print(f"Coleta {s['coleta']} | {s['legislatura']['num']}a legislatura | "
          f"{s['sessoes']['com_chamada']} sessoes com chamada")
    nomes = sys.argv[1:]
    if nomes:
        for busca in nomes:
            achados = [v for v in s["vereadores"] if regras.sem_acento(busca) in regras.sem_acento(v["nome"])]
            if not achados:
                print(f"\nNinguem com '{busca}' no nome.")
            for v in achados:
                ficha(s, v)
        return 0
    print(f"\n{'Nome':30} {'Part.':10} {'Sess':>4} {'Pres':>4} {'Falt':>4} {'Just':>4} {'S/reg':>5} "
          f"{'Bairro':>6} {'Cobr':>4} {'Hom':>4} {'Lei':>4} {'Nao':>4}  Mandato")
    for v in s["vereadores"]:
        p = v["propostas"]
        print(f"{v['nome'][:30]:30} {v['partido'][:10]:10} {v['sessoes']:>4} {v['presente']:>4} "
              f"{v['falta']:>4} {v['justificada']:>4} {v['sem_registro']:>5} {p.get('bairro', 0):>6} "
              f"{p.get('cobranca', 0):>4} {p.get('homenagem', 0):>4} {p.get('lei', 0):>4} "
              f"{v['votos'].get('nao', 0):>4}  {br(v['inicio'])}-{br(v['fim'])}"
              + ("" if v["em_exercicio"] else "  (saiu)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
