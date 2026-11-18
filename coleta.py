#!/usr/bin/env python3
"""
Sonar Sem Limites - coleta dos dados oficiais do SAPL da Camara Municipal de Bauru.

Le a API HTSQL aberta em https://sapl.bauru.sp.leg.br/api/ e salva os dados
em dados/*.json, mais dados/coleta.json com o registro da rodada.

Regras que este script segue de proposito (ver CLAUDE.md secao 4):
  - pausa entre as requisicoes: o servidor da Camara e fragil;
  - identifica quem esta acessando no User-Agent;
  - baixa so a legislatura atual nas tabelas grandes, em paginas;
  - descarta colunas com dado pessoal sensivel antes de salvar;
  - se qualquer passo falhar ou os numeros vierem estranhos, NAO sobrescreve
    o que ja estava salvo ("robo que falha nao publica").

Uso:
    python coleta.py              coleta completa
    python coleta.py --testar     so verifica se o servidor responde (1 chamada)
"""

import datetime
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://sapl.bauru.sp.leg.br/api/"
FONTE_HUMANA = "https://sapl.bauru.sp.leg.br"
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")

PAUSA = 2.0          # segundos entre chamadas. Nao diminua sem motivo.
TENTATIVAS = 3
TIMEOUT = 60
PAGINA = 2000        # registros por chamada nas tabelas grandes

UA = (
    "SonarSemLimites/0.2 (projeto cidadao de transparencia; "
    "coleta lenta, uma vez por dia, sem paralelismo)"
)

# Colunas que NUNCA sao salvas, por serem dado pessoal. CLAUDE.md secao 4.
COLUNAS_PROIBIDAS = {
    "num_tit_eleitor", "dat_nascimento", "num_cpf", "num_rg",
    "end_residencial", "num_cep_resid", "num_tel_resid", "num_tel_residencial",
    "num_cel_parlamentar", "end_email", "end_web", "txt_observacao_parlamentar",
}

# Chave usada para ordenar a paginacao de cada tabela (paginar sem ordem
# fixa pode repetir ou pular registros).
CHAVE = {
    "legislatura": "num_legislatura",
    "parlamentar": "cod_parlamentar",
    "mandato": "cod_mandato",
    "partido": "cod_partido",
    "filiacao": "cod_parlamentar,cod_partido,dat_filiacao",
    "autor": "cod_autor",
    "tipo_materia_legislativa": "tip_materia",
    "tipo_sessao_plenaria": "tip_sessao",
    "sessao_plenaria": "cod_sessao_plen",
    "sessao_plenaria_presenca": "cod_presenca_sessao",
    "ordem_dia_presenca": "cod_presenca_ordem_dia",
    "ordem_dia": "cod_ordem",
    "expediente_materia": "cod_ordem",
    "materia_legislativa": "cod_materia",
    "autoria": "cod_materia,cod_autor",
    "registro_votacao": "cod_votacao",
    "registro_votacao_parlamentar": "cod_votacao,cod_parlamentar",
}

# Nomes candidatos para o voto individual (CLAUDE.md secao 3).
CANDIDATAS_VOTO_NOMINAL = [
    "registro_votacao_parlamentar",
    "votacao_nominal",
    "voto",
]


class ErroDoCliente(Exception):
    """HTTP 4xx: a consulta esta errada ou a tabela nao existe. Nao repetir."""


registro_chamadas = []


def _url(consulta):
    return BASE + urllib.parse.quote(consulta, safe="(){}?=&<>!'.,*+-/:~") + "/:json"


def _baixar(consulta, tentativas=TENTATIVAS):
    url = _url(consulta)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    ultimo = None
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
            registro_chamadas.append({"consulta": consulta, "ok": True})
            time.sleep(PAUSA)
            return dados
        except urllib.error.HTTPError as erro:
            if 400 <= erro.code < 500:
                registro_chamadas.append({"consulta": consulta, "ok": False, "http": erro.code})
                time.sleep(PAUSA)
                raise ErroDoCliente(f"HTTP {erro.code} em {consulta}") from erro
            ultimo = erro
        except Exception as erro:  # noqa: BLE001 - rede, timeout, JSON quebrado
            ultimo = erro
        espera = PAUSA * n * 5
        print(f"\n    tentativa {n}/{tentativas} falhou ({ultimo}); esperando {espera:.0f}s",
              file=sys.stderr)
        time.sleep(espera)
    registro_chamadas.append({"consulta": consulta, "ok": False, "erro": str(ultimo)})
    raise RuntimeError(f"falhou depois de {tentativas} tentativas: {ultimo}")


def _registros(bruto):
    """A API devolve {"tabela": [[ {...}, ... ]]}; extrai a lista de dicts."""
    if not isinstance(bruto, dict) or not bruto:
        raise ValueError("resposta em formato inesperado")
    dentro = next(iter(bruto.values()))
    while isinstance(dentro, list) and len(dentro) == 1 and isinstance(dentro[0], list):
        dentro = dentro[0]
    if not isinstance(dentro, list):
        raise ValueError("resposta nao contem lista de registros")
    return [r for r in dentro if isinstance(r, dict)]


def _primeiro_numero(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    if isinstance(valor, dict):
        valor = list(valor.values())
    if isinstance(valor, list):
        for item in valor:
            n = _primeiro_numero(item)
            if n is not None:
                return n
    return None


def contar(expressao):
    n = _primeiro_numero(_baixar(f"count({expressao})"))
    if n is None:
        raise ValueError(f"contagem sem numero para {expressao}")
    return n


def baixar_tabela(tabela, filtro=""):
    """Baixa tabela (com filtro HTSQL opcional) em paginas ordenadas."""
    expr = tabela + (f"?{filtro}" if filtro else "")
    total = contar(expr)
    chave = CHAVE.get(tabela)
    saida = []
    for inicio in range(0, total, PAGINA):
        ordenado = f"({expr}).sort({chave})" if chave else f"({expr})"
        saida.extend(_registros(_baixar(f"{ordenado}.limit({PAGINA},{inicio})")))
    if len(saida) != total:
        raise ValueError(f"{tabela}: contagem dizia {total}, vieram {len(saida)}")
    return saida, expr


def limpar(registros):
    """Remove dado pessoal e registros marcados como excluidos."""
    saida = []
    for reg in registros:
        if str(reg.get("ind_excluido", 0)) not in ("0", "False", "None", ""):
            continue
        saida.append({k: v for k, v in reg.items() if k not in COLUNAS_PROIBIDAS})
    return saida


def legislatura_atual(legislaturas, hoje):
    hoje_txt = hoje.isoformat()
    for leg in legislaturas:
        if str(leg.get("dat_inicio", ""))[:10] <= hoje_txt <= str(leg.get("dat_fim", ""))[:10]:
            return leg
    raise ValueError("nenhuma legislatura cobre a data de hoje")


def minimo(registros, coluna):
    valores = [r[coluna] for r in registros if isinstance(r.get(coluna), int)]
    if not valores:
        raise ValueError(f"sem valores de {coluna} para filtrar")
    return min(valores)


def validar(res, leg):
    """Confere se os numeros fazem sentido antes de salvar."""
    problemas = []
    num = leg["num_legislatura"]
    mandatos = [m for m in res["mandato"] if m.get("num_legislatura") == num]
    vereadores = {m["cod_parlamentar"] for m in mandatos}
    if not 15 <= len(vereadores) <= 40:
        problemas.append(f"{len(vereadores)} parlamentares com mandato na legislatura {num} "
                         "(esperado ~21 mais suplentes)")
    if not res["sessao_plenaria"]:
        problemas.append("nenhuma sessao plenaria na legislatura atual")
    # Em Bauru a chamada fica em ordem_dia_presenca; sessao_plenaria_presenca
    # so tem registros antigos (85 no total em 2026-11).
    presencas = res["ordem_dia_presenca"]
    if len(presencas) < len(res["sessao_plenaria"]) * 5:
        problemas.append(f"so {len(presencas)} registros de presenca para "
                         f"{len(res['sessao_plenaria'])} sessoes")
    if not res["materia_legislativa"]:
        problemas.append("nenhuma materia na legislatura atual")
    sessoes = {s["cod_sessao_plen"] for s in res["sessao_plenaria"]}
    orfas = sum(1 for p in presencas if p.get("cod_sessao_plen") not in sessoes)
    if orfas > len(presencas) * 0.5:
        problemas.append(f"{orfas} presencas de sessoes fora da lista (filtro errado?)")
    return problemas


def salvar_tudo(res, manifesto):
    """Grava numa pasta temporaria e so troca quando tudo foi escrito."""
    nova = PASTA + ".nova"
    shutil.rmtree(nova, ignore_errors=True)
    os.makedirs(nova)
    for tabela, registros in res.items():
        with open(os.path.join(nova, tabela + ".json"), "w", encoding="utf-8") as arq:
            json.dump(registros, arq, ensure_ascii=False, indent=1)
    with open(os.path.join(nova, "coleta.json"), "w", encoding="utf-8") as arq:
        json.dump(manifesto, arq, ensure_ascii=False, indent=1)
    os.makedirs(PASTA, exist_ok=True)
    for nome in os.listdir(nova):
        os.replace(os.path.join(nova, nome), os.path.join(PASTA, nome))
    os.rmdir(nova)


def testar():
    try:
        _registros(_baixar("legislatura.limit(1)", tentativas=1))
    except Exception as erro:  # noqa: BLE001
        print(f"Servidor NAO respondeu: {erro}")
        return 2
    print("Servidor respondeu.")
    return 0


def main():
    if "--testar" in sys.argv:
        return testar()

    print("Sonar Sem Limites - coletando do SAPL da Camara de Bauru")
    print(f"Pausa de {PAUSA}s entre as chamadas.\n")
    inicio = datetime.datetime.now()

    if testar() != 0:
        print("Nada foi alterado em dados/.", file=sys.stderr)
        return 2

    res, consultas = {}, {}

    def etapa(tabela, filtro=""):
        print(f"  {tabela} {('[' + filtro + ']') if filtro else ''} ...", end=" ", flush=True)
        brutos, expr = baixar_tabela(tabela, filtro)
        res[tabela] = limpar(brutos)
        consultas[tabela] = expr
        print(f"{len(res[tabela])} registros")

    try:
        # Tabelas pequenas: inteiras.
        for t in ["legislatura", "parlamentar", "mandato", "partido", "filiacao",
                  "autor", "tipo_materia_legislativa", "tipo_sessao_plenaria"]:
            etapa(t)

        leg = legislatura_atual(res["legislatura"], datetime.date.today())
        num = leg["num_legislatura"]
        ano_ini = int(str(leg["dat_inicio"])[:4])
        print(f"\n  Legislatura atual: {num}a ({leg['dat_inicio']} a {leg['dat_fim']})\n")

        # Tabelas grandes: so a legislatura atual.
        etapa("sessao_plenaria", f"num_legislatura={num}")
        s0 = minimo(res["sessao_plenaria"], "cod_sessao_plen")
        for t in ["sessao_plenaria_presenca", "ordem_dia_presenca", "ordem_dia",
                  "expediente_materia"]:
            etapa(t, f"cod_sessao_plen>={s0}")

        etapa("materia_legislativa", f"ano_ident_basica>={ano_ini}")
        m0 = minimo(res["materia_legislativa"], "cod_materia")
        etapa("autoria", f"cod_materia>={m0}")

        ordens = res["ordem_dia"] + res["expediente_materia"]
        o0 = minimo(ordens, "cod_ordem")
        etapa("registro_votacao", f"cod_ordem>={o0}")

        # Lacuna do voto nominal (CLAUDE.md secao 3).
        voto_nominal = {"tabela": None, "testadas": {}}
        v0 = minimo(res["registro_votacao"], "cod_votacao") if res["registro_votacao"] else 0
        for nome in CANDIDATAS_VOTO_NOMINAL:
            try:
                contar(nome + ".limit(1)")
            except ErroDoCliente:
                voto_nominal["testadas"][nome] = "nao existe"
                continue
            voto_nominal["testadas"][nome] = "existe"
            voto_nominal["tabela"] = nome
            filtro = f"cod_votacao>={v0}" if nome == "registro_votacao_parlamentar" else ""
            etapa(nome, filtro)
            break
        print(f"\n  Voto nominal: {voto_nominal}")

        # Materias de anos anteriores votadas nominalmente nesta legislatura.
        res["materia_votada"] = []
        if voto_nominal["tabela"] == "registro_votacao_parlamentar":
            nominais = {v["cod_votacao"] for v in res["registro_votacao_parlamentar"]}
            ja_tem = {m["cod_materia"] for m in res["materia_legislativa"]}
            faltam = sorted({v["cod_materia"] for v in res["registro_votacao"]
                             if v["cod_votacao"] in nominais and v.get("cod_materia")
                             and v["cod_materia"] not in ja_tem})
            print(f"  materia_votada [{len(faltam)} materias antigas] ...", end=" ", flush=True)
            for i in range(0, len(faltam), 100):
                lista = ",".join(str(c) for c in faltam[i:i + 100])
                res["materia_votada"] += limpar(_registros(_baixar(
                    f"materia_legislativa?cod_materia={{{lista}}}")))
            consultas["materia_votada"] = "materia_legislativa?cod_materia={...}"
            print(f"{len(res['materia_votada'])} registros")

    except Exception as erro:  # noqa: BLE001
        print(f"\nFALHOU: {erro}\nNada foi alterado em dados/. "
              "O site continua com a ultima versao boa.", file=sys.stderr)
        return 1

    problemas = validar(res, leg)
    if problemas:
        print("\nDados estranhos, NADA foi salvo:\n  - " + "\n  - ".join(problemas),
              file=sys.stderr)
        return 1

    manifesto = {
        "fonte": BASE,
        "fonte_humana": FONTE_HUMANA,
        "inicio": inicio.isoformat(timespec="seconds"),
        "fim": datetime.datetime.now().isoformat(timespec="seconds"),
        "legislatura": leg,
        "consultas": consultas,
        "registros": {t: len(r) for t, r in res.items()},
        "voto_nominal": voto_nominal,
        "chamadas": len(registro_chamadas),
    }
    salvar_tudo(res, manifesto)
    print(f"\nColeta completa: {len(res)} tabelas, {len(registro_chamadas)} chamadas. "
          f"Salvo em {PASTA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
