# Radar Bauru: plano de expansão

Situação: **aprovado em 13/11/2026**, com as decisões abaixo. A implementação
ainda não começou.

## Decisões do usuário (13/11/2026)

1. Site em 3 páginas (Câmara, Prefeitura, Dinheiro): aprovado.
2. Ordem da seção 6: aprovada.
3. Fornecedor pessoa física: mostrar o nome, nunca o CPF (o peso é desprezível).
4. Download de 2,1 GB autorizado e feito (resultado abaixo).
5. Período: **dados a partir de 2025**. Para 2025, arquivo anual do TCE; para 2026,
   API mensal do TCE.

## Resultado do teste do arquivo anual do TCE (despesas 2025)

- 120.051 linhas de Bauru (61,5 MB), extraídas em 3,5 min por
  `coleta_tce_anual.py`. Ficam em `dados/tce/`, fora do git.
- **Não existe campo "secretaria".** Existe a área de governo oficial (função),
  com 18 valores (Educação R$ 464 mi, Saúde R$ 425 mi, Urbanismo R$ 200 mi pagos),
  além de programa (20) e ação (104).
  **Decisão técnica:** o site mostra o gasto por **área de governo** e diz que isso
  não é o mesmo que secretaria. Gasto exato por secretaria só pelo portal da
  Prefeitura ou por pedido de acesso à informação.
- Modalidade disponível. Valores pagos pela Prefeitura em 2025:
  - dispensa: R$ 131,5 mi;
  - inexigibilidade: R$ 27,1 mi;
  - pregão eletrônico: R$ 298,1 mi.
- Eventos: a subfunção "Difusão Cultural" soma R$ 25,8 mi, mas mistura folha e
  convênios. O histórico identifica shows ("APRESENTACAO ARTISTICA", "CARNAVAL").
  **Regra a definir:** subfunção mais palavras do histórico, explicada no site.
- **Subsídio conferido:** "31901175 - Subsídios - Agentes Políticos" da Câmara
  somou R$ 3,72 mi pagos em 2025, cerca de R$ 310 mil por mês, o mesmo que
  21 × R$ 14.762,80.
- O arquivo anual do TCE vem em Windows-1252 (não UTF-8). A API mensal manda UTF-8
  com escapes. Os acentos estão íntegros nas duas fontes.

## Publicação no GitHub: viabilidade

- **Tamanho:** sem problema. Estimativa de 10–15 MB de site no total. Dados brutos
  fora do repositório.
- **Risco:** o servidor da Câmara bloqueia alguns endereços (a rede de casa e a nuvem
  da conversa anterior). O GitHub Actions pode estar bloqueado também. TCE e PNCP
  abrem normalmente.
- **Regra do usuário:** nada no GitHub (nem repositório de teste) antes de o site
  funcionar completo localmente. Esse risco só é tratado quando chegar a hora de
  publicar.
- **Sem pedidos por e-SIC ou LAI.** Dado que não existe em fonte aberta fica de fora,
  e o site diz isso.
- Antes de publicar, `radar-bauru` vira um repositório próprio (hoje está dentro do
  git de `Py_Projetos`).
- PNCP: 5.562 contratos da Prefeitura só em 2025. Reduzidos aos campos úteis, cerca
  de 1–2 MB.

Amplia o Radar da Câmara para três áreas novas:

- **A.** Arrecadação polêmica: multas e radares, impostos e taxas.
- **B.** Prefeita e secretarias.
- **C.** Gastos públicos da Prefeitura: licitações, contratos e eventos.

As regras do projeto continuam valendo em todas elas: só dado oficial, mesma régua
para todos, link para a fonte em cada número, estimativa dita como estimativa,
dado ausente não é falta, robô que falha não publica.

---

## 1. Fontes testadas

Todas as fontes abaixo foram acessadas em 13/11/2026, e os dados conferidos
são de Bauru.

| Fonte | O que traz | Período | Acesso | Testado |
|---|---|---|---|---|
| **TCE-SP, API por município** (`transparencia.tce.sp.gov.br/api/json/...`) | Despesas: órgão, empenho, fornecedor, data, valor, fase (empenhado, liquidado, pago). Receitas: órgão, tipo de receita, destinação, valor | Mês a mês, **inclui 2026** (até setembro) | JSON, sem login | Sim. Set/2026: 11.417 despesas e 618 receitas |
| **TCE-SP, arquivos anuais** (`.../conjunto-dados/despesas-AAAA.zip`) | Tudo o que a API traz, mais função, subfunção, programa, ação, **modalidade de licitação**, tipo de gasto e **histórico** (descrição) de cada empenho | 2008–2025 (só o ano fechado); atualização semanal | CSV em zip. Despesas: **2,1 GB por ano** (estado todo). Receitas: 35 MB | Receitas 2025: sim. Despesas: só o cabeçalho |
| **PNCP**, Portal Nacional de Contratações Públicas (`pncp.gov.br/api/consulta`) | Licitações, dispensas, inexigibilidades, contratos e atas, com objeto, valor e fornecedor | Desde a Lei 14.133 | JSON, sem login. Município de Bauru = CNPJ 46.137.410/0001-80 | Sim |
| **Diário Oficial de Bauru** (`www2.bauru.sp.gov.br/arquivos/sist_diariooficial/...`) | Autorizações de inexigibilidade (ex.: shows do aniversário da cidade), decretos, nomeações | Edições em PDF | PDF; precisa extrair o texto | Abre daqui; extração ainda não testada |
| **EMDURB**, página "Localização Radares" | Lista de radares | Atual | HTML | Achada na busca; não aberta ainda |
| **SAPL da Câmara** (já em uso) | Leis (13.399 normas), projetos da Prefeita, vetos e o andamento dos pedidos de informação | 34ª legislatura | Já em uso | Sim |

**Exemplo de que os números saem:** receita de Bauru em 2025, pelo TCE.

| Item | Valor |
|---|---|
| Prefeitura | R$ 1.688 mi |
| FUNPREV | R$ 383 mi |
| DAE | R$ 257 mi |
| EMDURB | R$ 100 mi |
| IPTU | R$ 223 mi |
| Taxas | R$ 18,9 mi |
| Contribuição de iluminação pública | R$ 16,4 mi |
| Multas de trânsito (código "450 - Trânsito - Fiscalização") | R$ 5,57 mi |

São somas preliminares, feitas para testar a fonte. A regra de cada número será
conferida antes de ir ao site.

---

## 2. Módulo A: Arrecadação polêmica

**O que mostrar**

- Quanto a cidade arrecadou por ano com cada imposto e taxa: IPTU, ISS, ITBI,
  taxas, contribuição de iluminação pública. De 2018 até o ano atual, com o ano
  corrente marcado como parcial.
- **Multas de trânsito:** valor arrecadado por ano e por mês.
- **Para onde foi o dinheiro das multas:** o Código de Trânsito (art. 320) obriga a
  gastar a receita de multas em sinalização, engenharia de tráfego, fiscalização e
  educação de trânsito. O TCE marca receita e despesa com o mesmo código de
  destinação ("450 - Trânsito - Fiscalização"). Dá para mostrar lado a lado o que
  entrou e o que saiu por esse código, com dado oficial e sem opinião.
- **Radares:** lista com a localização (EMDURB) e, se possível, mapa.

**Dúvidas que ainda preciso fechar**

1. Quem registra a receita das multas de radar: a Prefeitura ou a EMDURB? Em 2025
   achei R$ 5,57 mi na Prefeitura. A EMDURB tem receita própria (R$ 100 mi) e
   pode ter outra parte.
   **Teste:** filtrar as receitas da EMDURB por tipo "multa" nos dados do TCE.
2. Número de multas por radar: a imprensa cita 71.918 multas em 2025, mas jornal
   não é fonte.
   **Teste:** procurar relatório oficial da EMDURB. Se não existir, fica de fora.
3. ISS: a minha primeira soma usou busca por palavra e pode ter pegado itens
   errados.
   **Regra final:** usar o código contábil da receita, não o nome.

---

## 3. Módulo B: Prefeita e secretarias

É possível, mas com limites. O que existe em dado oficial:

| Medida | Fonte | Situação |
|---|---|---|
| Subsídio da Prefeita, do vice e dos secretários | Lei municipal no SAPL (a imprensa cita a mesma lei de 2022 dos vereadores) | Achar a norma |
| Projetos que a Prefeita enviou à Câmara, aprovados ou não | SAPL (autoria do Executivo: há 211 projetos de lei sem vereador autor nesta legislatura) | Dado já baixado |
| Vetos da Prefeita | SAPL (tipo "Veto") | Dado já baixado |
| **Tempo de resposta da Prefeitura aos pedidos de informação dos vereadores** | SAPL, andamento das matérias (aparece "ENCAMINHADO PEDIDO DE INFORMAÇÃO") | Exige baixar a tabela de andamento; não testado |
| Pedidos recebidos por órgão (Prefeita, EMDURB, DAE…) | Texto dos pedidos, que já citam o destinatário | Dado já baixado |
| Gasto por secretaria | TCE ou portal da Prefeitura | **Dúvida aberta (abaixo)** |
| Inexigibilidades autorizadas pela Prefeita | Diário Oficial | Extrair do PDF |

**Dúvida aberta:** os dados do TCE não têm um campo "secretaria". Talvez dê para
deduzir pelo programa ou pela ação do orçamento.
**Teste:** baixar uma vez o arquivo de despesas de 2025 (2,1 GB, filtrando só Bauru)
e verificar.
**Alternativa:** o portal de transparência da própria Prefeitura.

**Limite honesto:** não há registro oficial de presença ou de "produtividade" de
secretário. O módulo mostra gastos, respostas e atos, não uma nota.

---

## 4. Módulo C: Gastos públicos

**O que mostrar**

- **Licitações e contratos** (PNCP): o que foi comprado, de quem e por quanto, e em
  que modalidade (pregão, dispensa, inexigibilidade). Filtro por fornecedor e
  por assunto.
- **Compras sem licitação** (dispensa e inexigibilidade) separadas, porque são o
  ponto mais cobrado pela população.
- **Eventos públicos:** shows e festas.
  - Pelo TCE: subfunção "Difusão Cultural" mais o histórico do empenho.
  - Pelo Diário Oficial: autorizações de inexigibilidade. Exemplo real: show do
    aniversário de Bauru 2026, R$ 210 mil, autorizado em 01/06/2026.
- **Maiores fornecedores** da Prefeitura, por ano.
- **Para onde vai o dinheiro:** saúde, educação, transporte etc., com valores
  pagos (não só empenhados).

**Cuidados**

- Mostrar **valor pago**, deixando claro que empenho não é pagamento.
- Fornecedor pessoa física: **não mostrar CPF**. Decidir se mostra o nome (abaixo).
- Grandes contratos com aditivos: mostrar o valor do contrato e dos aditivos
  separados, como na fonte.

---

## 5. Como fica a construção

- **Coletores novos**, cada um com as mesmas travas da coleta atual (testa antes,
  pausa entre chamadas, valida, só troca os dados se tudo der certo):
  - `coleta_tce.py`: API mensal e arquivo anual filtrado para Bauru;
  - `coleta_pncp.py`;
  - `coleta_diario.py`: PDF do Diário Oficial, mais trabalhoso; fica por último.
- **O site deixa de ser uma página só.** Os dados da Câmara já ocupam 3,3 MB; com
  gastos e receitas, uma página única fica pesada no celular. Proposta:
  - `index.html`: Câmara (o que já existe);
  - `prefeitura.html`: Prefeita e secretarias;
  - `dinheiro.html`: arrecadação e gastos;
  - menu comum no topo; cada página carrega só os próprios dados.
- **Atualização:** a Câmara e a API do TCE diariamente; o arquivo anual do TCE uma
  vez por ano, quando o ano fecha.
- **Rede:** o servidor da Câmara bloqueia a rede da sua casa. As fontes TCE, PNCP e
  Prefeitura abriram normalmente da sua rede.

---

## 6. Ordem proposta

1. **Terminar a Câmara antes de tudo:** etapa 7 do `PLANO.md`, conferir 2–3
   vereadores com a ficha oficial.
2. **Módulo C, gastos** (PNCP e API do TCE): as fontes mais fáceis e já testadas.
3. **Módulo A, arrecadação:** receitas do TCE, multas versus gasto com trânsito,
   radares.
4. **Módulo B, Prefeita e secretarias:** depende do teste de "gasto por
   secretaria" e da tabela de andamento do SAPL.
5. Diário Oficial (eventos e inexigibilidades), por ser PDF.
6. Só então o GitHub.

---

## 7. Decisões que preciso de você

1. Aprovar a divisão do site em 3 páginas (Câmara, Prefeitura, Dinheiro).
2. Aprovar a ordem da seção 6.
3. **Fornecedor pessoa física:** mostrar o nome (sem CPF) ou só "pessoa física"?
   Artistas contratados como pessoa física aparecem aqui.
4. Autorizar o download único de 2,1 GB do TCE para testar "gasto por secretaria".
   Fazer isso **fora** do roteador do celular, porque o TCE abre da rede de casa.
5. Período: só desta gestão (desde 2025) ou também anos anteriores, para comparar?
   O TCE tem dados desde 2008.

---

## Módulo D — Unidade Regional de Ensino (URE) Bauru (proposta de 14/11/2026)

Pedido do usuário: **página própria "Diretoria de Ensino"** (`site/diretoria.html`,
quarto item do menu: Câmara | Prefeitura | Dinheiro | Diretoria de Ensino), focada na **administração** (quem tem
cargo, quanto recebe, o que a unidade gasta e contrata), **não** em dados de
alunos e professores. Aprovado: D.E. inteira com filtro por cidade; ausências
entram; começar pelo que tem régua oficial.

Fato: desde 2025 a Diretoria de Ensino se chama **URE Bauru** (Unidade Regional
de Ensino), órgão da Secretaria Estadual da Educação.

### Fontes testadas

| Fonte | O que tem | Teste |
|---|---|---|
| Site da URE (educacao.sp.gov.br/urebauru) | Dirigente (Gabriel Prochnou Vieira) e chefes de cada serviço, por nome | Abre; páginas por setor |
| Folha do Estado (transparencia.sp.gov.br, `RemuneracaoAtivos.csv`, 64 MB) | Nome, cargo, órgão, remuneração, eventuais, líquido. **Sem lotação** | Abre; Last-Modified mai/2026: falta descobrir o mês e se a consulta por mês dá o atual |
| Pagamentos da SEDUC (dados.educacao.sp.gov.br, "ordem cronológica") | Cada pagamento com a unidade (UG 080297 = URE Bauru), natureza (inclui **diárias com o nome do servidor**), credor, data, valor, finalidade. 2024 a set/2026 | Abre. 2026: 2.460 pagamentos, R$ 61,9 mi, R$ 662 mil em diárias a 620 pessoas |
| PNCP (CNPJ SEDUC 46.384.111/0001-40) | Contratos e dispensas por unidade (código e nome) | Abre; lento |
| Cadastro de servidores ativos (dados.educacao.sp.gov.br, mensal, anonimizado) | Lotação, cargo, quadro e início de exercício de cada servidor; **sem nome e sem salário** | Abre. Out/2026: **123 servidores na sede da URE Bauru** (3.537 nas escolas) |
| Webservice da Fazenda (despesa por UGE e credor) | Completo | Exige usuário e senha: fora |

### O que a aba mostraria

1. **Quem comanda**: crachás do Dirigente e dos chefes de serviço (nome do site
   da URE), com cargo e remuneração da folha do Estado (cruzamento por nome; se
   houver homônimo, fica sem valor).
2. **Salário dos servidores da URE**:
   - quem tem nome publicado no site da URE (Dirigente, chefes, apoio, comissões):
     salário exato da folha do Estado, cruzado por nome e cargo;
   - os 123 da sede: quantos são por cargo (cadastro oficial) e o salário típico
     de cada cargo (mediana da folha estadual daquele cargo na Secretaria da
     Educação). A soma da folha da sede é **estimativa**, dita como estimativa:
     os dados abertos não ligam o nome à lotação;
   - mês: a folha publicada mais recente é **março/2026** (o Estado publica com
     cerca de 8 meses de atraso); o site mostra o mês.
3. **Diárias**: total por mês; por pessoa só para quem tem cargo de chefia ou
   está no site da URE; demais servidores agregados por cargo.
4. **Para onde vai o dinheiro da URE**: por tipo de despesa, maiores credores,
   por cidade (prefeituras recebem transporte escolar).
5. **Contratos e dispensas** (PNCP).
6. **Ausências** dos servidores da URE (conjunto anonimizado), se der para
   separar a URE das escolas.

### Réguas oficiais (inconformidade só com régua)

- **Fracionamento de dispensa** (Lei 14.133, art. 75 §1º): soma de dispensas no
  ano para o mesmo objeto/fornecedor acima do limite legal. Mostrado como
  "acima do limite da lei", com link, nunca como "irregular".
- **Diárias**: só vira régua se lermos o decreto estadual de diárias; até lá,
  só números.
- **Ordem cronológica de pagamento** (art. 141): o arquivo não traz a data de
  vencimento nem do ateste, então **não dá** para verificar. Fica fora.

### Pendências antes de construir

- Confirmar UG 080297 = URE Bauru pelo nome da unidade no PNCP.
- ~~Mês da folha~~: março/2026 é o último publicado (consulta por mês existe no portal).
- Ver se o conjunto de ausências separa a URE das escolas.
