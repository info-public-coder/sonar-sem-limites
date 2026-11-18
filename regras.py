"""
Radar Bauru - regras de classificacao. A MESMA regra vale para todos os
vereadores, e o texto de EXPLICACAO aparece no site, na secao Transparencia.

Classificacao usa o tipo da materia no SAPL (des_tipo_materia) e palavras da
ementa (txt_ementa). Revisar com os dados reais: rodar
`python gerar_site.py --conferir` mostra quantas materias caem em cada grupo
e exemplos de cada, inclusive do grupo "outros".
"""

import re
import unicodedata

GRUPOS = {
    "bairro": "Pedidos para os bairros",
    "cobranca": "Perguntas e cobranças",
    "homenagem": "Homenagens",
    "lei": "Projetos de lei",
    "audiencia": "Audiências públicas",
    "utilidade": "Utilidade pública",
    "outros": "Outros",
}

EXPLICACAO = [
    ("Pedidos para os bairros",
     "Indicações à Prefeita e requerimentos à EMDURB, ao DAE e a outros órgãos "
     "pedindo melhorias ou serviços, como asfalto, iluminação, limpeza, poda, "
     "lombada e sinalização."),
    ("Perguntas e cobranças",
     "Requerimentos que pedem informações, esclarecimentos ou cópia de "
     "documentos (em geral \"com base na Lei Orgânica\")."),
    ("Homenagens",
     "Moções e votos de aplauso, congratulação ou pesar; medalhas, títulos e "
     "honrarias; projetos que só dão nome a rua, praça ou prédio ou criam data "
     "comemorativa; sessões solenes."),
    ("Projetos de lei",
     "Projetos de lei, de resolução e de decreto legislativo que não são "
     "homenagem nem utilidade pública; emendas à Lei Orgânica."),
    ("Audiências públicas",
     "Audiências e reuniões públicas que o vereador pediu para debater um "
     "tema com a população."),
    ("Utilidade pública",
     "Projetos que declaram uma entidade (associação, ONG, clube) de "
     "utilidade pública. Ficam separados porque não são só homenagem: o "
     "título tem efeito legal e permite à entidade receber recursos públicos."),
    ("Outros",
     "Moções de apelo ou repúdio, outros eventos públicos, licenças, vetos e "
     "processos diversos."),
]


def sem_acento(txt):
    return "".join(c for c in unicodedata.normalize("NFD", str(txt or ""))
                   if unicodedata.category(c) != "Mn").lower()


HOMENAGEM_MOCAO = re.compile(r"aplauso|congratula|parabeniza|pesar|louvor|homenage")
HOMENAGEM_PROJETO = re.compile(r"titulo de cidada|cidadao bauruense|cidada bauruense|medalha|comenda|"
                               r"honra ao merito|honraria|\bdenomina|institui o dia|"
                               r"institui a semana|institui o mes|data comemorativa|calendario oficial")
COBRANCA = re.compile(r"com base na lom|informac|esclarecimento|copia integral|copia do|copias")


def classificar(des_tipo, ementa):
    tipo = sem_acento(des_tipo)
    em = sem_acento(ementa)
    if "indica" in tipo:
        return "bairro"
    if "requerimento" in tipo:
        if re.search(r"voto de (profundo )?(aplauso|pesar|congratula|louvor)", em):
            return "homenagem"
        if COBRANCA.search(em):
            return "cobranca"
        return "bairro"
    if "evento" in tipo:
        if re.match(r"\s*(audiencia|reuniao) publica", em):
            return "audiencia"
        if re.match(r"\s*(sessao )?solene", em):
            return "homenagem"
        return "outros"
    if "mocao" in tipo:
        return "homenagem" if HOMENAGEM_MOCAO.search(em) else "outros"
    if "projeto" in tipo and "utilidade publica" in em:
        return "utilidade"
    if "projeto" in tipo or "emenda a lei organica" in tipo:
        return "homenagem" if HOMENAGEM_PROJETO.search(em) else "lei"
    return "outros"


# ---------------------------------------------------------------- locais

LOGRADOURO = re.compile(
    r"\b(rua|r\.|avenida|av\.|alameda|al\.|travessa|tv\.|praca|pca\.|estrada|rodovia|viela)\s+"
    r"([a-z0-9][a-z0-9 .'-]{2,60}?)"
    r"(?=\s*(?:,|;|\(|\)|$|\bn[o.º°]?\s*\d|\bno\b|\bna\b|\bnas\b|\bnos\b|\bdo\b\s+(?:bairro|jardim|parque|vila)|"
    r"\bentre\b|\besquina\b|\bjunto\b|\bproximo\b|\bdefronte\b|\bem frente\b|\bate\b|\bjardim\b|\bvila\b|"
    r"\bparque\b|\bbairro\b|\bnucleo\b|\bquadra\b|\b-\b))"
)
BAIRRO = re.compile(
    r"\b(jardim|jd\.|vila|vl\.|parque|pq\.|nucleo habitacional|nucleo|conjunto habitacional|"
    r"residencial|distrito|chacara|chacaras|bairro)\s+"
    r"([a-z0-9][a-z0-9 .'-]{2,50}?)"
    r"(?=\s*(?:,|;|\.|\(|\)|$|\be\b|\bem\b|\bpara\b|\bque\b|\bonde\b|\bjunto\b|\bproximo\b|\b-\b))"
)
TIPO_LOGRADOURO = {"r.": "rua", "av.": "avenida", "al.": "alameda", "tv.": "travessa",
                   "pca.": "praca"}
TIPO_BAIRRO = {"jd.": "jardim", "vl.": "vila", "pq.": "parque"}


NAO_E_NOME = re.compile(r"^(localizad|situad|existente|publica|central|sem denominacao|"
                        r"que |de lazer|e |da regiao|do bairro)")


def _limpo(txt):
    txt = re.sub(r"\s+", " ", txt).strip(" .-'")
    return "" if NAO_E_NOME.match(txt) else txt.title()


def extrair_locais(ementa):
    """Devolve (ruas, bairros) citados na ementa, normalizados."""
    em = sem_acento(ementa)
    ruas, bairros = set(), set()
    for tipo, nome in LOGRADOURO.findall(em):
        nome = _limpo(nome)
        if len(nome) >= 3:
            ruas.add(f"{TIPO_LOGRADOURO.get(tipo, tipo).title()} {nome}")
    for tipo, nome in BAIRRO.findall(em):
        nome = _limpo(nome)
        if len(nome) >= 3:
            prefixo = TIPO_BAIRRO.get(tipo, tipo)
            bairros.add(nome if prefixo == "bairro" else f"{prefixo.title()} {nome}")
    return sorted(ruas), sorted(bairros)
