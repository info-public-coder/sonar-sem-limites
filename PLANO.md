# Sonar Sem Limites — plano de implementação

Acompanha a seção 5 do `CLAUDE.md`. Atualizar o status a cada etapa concluída.
Regra: **nenhuma página é montada antes de a coleta rodar e os números de dois
vereadores serem conferidos com o usuário.**

| # | Etapa | Status | Entrega |
|---|---|---|---|
| 1 | Coleta (`coleta.py`) | **Feita** com dados reais em 13/11/2026 (48 chamadas, 18 tabelas) | `dados/*.json` + `dados/coleta.json` |
| 1b | Números no terminal (`resumo.py`) | Pronto; usa o mesmo cálculo do site | checkpoint |
| 2 | Voto nominal | **Existe** (`registro_votacao_parlamentar`), mas só 22 de 1.392 votações são nominais | "votou não" com ressalva |
| 3 | Classificar propostas (`regras.py`) | Feita, revisada com dados reais | regra explicada no site |
| 4 | Presença | Feita, por `ordem_dia_presenca` (P/F/A) | por vereador |
| 5 | Ruas/bairros + repetidos | Feito: 94% dos pedidos com local reconhecido | "O problema que não some" |
| — | **Checkpoint:** 2 vereadores (Bussola, Estela) | Mostrado; falta o usuário conferir na ficha oficial | — |
| 6 | Site (`site/index.html` + `gerar_site.py`) | Funciona com dados reais; conferido por `verificar_site.py` | abrir `site/index.html` |
| 6b | Página Dinheiro (expansão, módulo C) | 2025 (TCE anual + PNCP: 5.562 contratos, 134 diretas) e 2026 até setembro (API TCE + PNCP: 4.940 contratos, 80 diretas) prontos; coleta completa em 14/11, sem falhas | `site/dinheiro.html` |
| 6c | Crachás dos vereadores (foto, anel de presença, barra colorida) | Feito em 14/11. Fotos e votos de 2024 pelo TSE (`coleta_tse.py`, dados abertos lidos por trecho): 32 de 32 | `site/index.html` |
| 6d | Página Prefeitura (módulo B) | Feita em 14/11: crachás da Prefeita, do vice, de 16 secretarias e de 4 órgãos (equipe e fotos do site oficial). Gasto por secretaria pelo nome do programa do TCE (conta nossa). Saúde não aparece na página oficial. Regra do usuário: campo sem dado sai do site. Salário do Executivo retirado (TCE paga sem nome; lei no SAPL, rede do celular) | `site/prefeitura.html` |
| 6e | Página Diretoria de Ensino (módulo D, URE Bauru) | Feita em 15/11 e completada em 18/11: 13 de 15 nomes com salário; 123 servidores da sede; pagamentos e diárias de 2025 (ano todo) e 2026 (até set); 38 contratos (27 dispensa, 11 pregão); limite da dispensa 2024-2026 sem caso. Portal da SEDUC: baixado com curl (recusa o cliente do Python). Ausências **retiradas**: o boletim quase não cobre as sedes (1 de 123 em Bauru) | `site/diretoria.html` |
| — | Comando único `atualizar.py` | Pronto: coleta, gera e confere | — |
| 7 | Conferência com fichas oficiais | Pendente | lista do que não bateu |
| 8 | GitHub Pages + Actions | Workflows prontos em `.github/workflows/` (teste das fontes e robô diário com cache de `dados/`). Falta o usuário publicar o repositório e rodar o teste | workflow |
| 9 | Domínio próprio | Opcional | — |

## Decisões abertas (usuário)

- ~~Audiências públicas~~: feito, grupo próprio (171; sessões solenes → homenagem).
- ~~Utilidade pública~~: feito, grupo próprio (10).
- ~~Subsídio~~: R$ 14.762,80, pela norma nº 586/2022 (SAPL cod_norma=13340) e pelo
  organograma oficial da Câmara (dez/2025), em `config.json`. **Pendente:** ler o
  texto integral da norma (o PDF não baixou: servidor fora) e confirmar se houve
  revisão em 2026.
- Expansão (Prefeita, secretarias, arrecadação, gastos): ver `PLANO-EXPANSAO.md`,
  aguardando aprovação.

## Fatos de Bauru descobertos na coleta

- O servidor bloqueia a rede de casa do usuário; funciona pelo roteador do celular.
- Presença fica em `ordem_dia_presenca`; `sessao_plenaria_presenca` só tem 85 registros antigos.
- Sessões tipo 6 ("Indicações e Requerimentos") não têm chamada: 108 de 121 têm.
- `ind_primeiro_autor` quase nunca preenchido (6 de 9.163): proposta de um só
  vereador conta para ele; com vários, conta como coautoria.
- Suplentes têm um registro de `mandato` por período de exercício.
- Requerimentos são, na maioria, pedidos de melhoria à EMDURB e ao DAE.
- Valores de voto: Sim, Nao, Ausente, Em branco, "-------" (sem voto, ex.: presidente).
- Link da matéria usa o código em base64; o do parlamentar usa o código direto.

## Ajustes previstos no `coleta.py` (fazer quando o servidor voltar)

- Antes de baixar tudo, rodar `count(tabela)` para ver o tamanho. Tabelas grandes
  (`materia_legislativa`, `sessao_plenaria_presenca`, `autoria`) devem ser baixadas em
  partes (por ano ou com `.limit()`/offset), não numa requisição só.
- Filtrar `ind_excluido=0` já na consulta, não só depois.
- Python: usar `..\..\.python_embed\python.exe` (não há `python` no PATH).
- Baixar só a 34ª legislatura (2025–2028) nas tabelas de matéria, sessão e presença, em
  vez do histórico inteiro.
- Primeira consulta da etapa 2: `registro_votacao_parlamentar` (nome usado no esquema do
  SAPL 2.x para o voto individual). Confirmar pelo link "Esquema" da API.
- Contagem de propostas: decidir entre autor principal (`ind_primeiro_autor`) e coautor.
  Moções com 20 coautores existem e inflariam todos por igual.
- Presença: o SAPL mostra às vezes 22 presentes (suplente em exercício). Contar por
  vereador e por período de exercício, não supor 21 fixos.
- Salário (cartão do topo): a fonte não é o SAPL, é o portal de transparência da Câmara.

## Fontes de dados (revisado em 2026-11-13)

1. **API HTSQL `/api/`** — principal. Dados estruturados, em lote, sem captcha.
2. **Páginas públicas do SAPL** (`/consultas/sessao_plenaria/...`,
   `/consultas/materia/materia_mostrar_proc?...`) — alternativa se a API for desligada, e
   o link de fonte em cada número do site. Não usar o formulário com reCAPTCHA.
3. **Pedido pela LAI (e-SIC da Câmara)** — se faltar algo, como o voto nominal.
4. **Portal de transparência** — subsídio dos vereadores.

"Tempo real" não é o objetivo: o radar de referência atualiza uma vez por dia, de
madrugada. O "Ao vivo" de lá é só o contador de salário, que é calculado no navegador.

## Log

**2026-11-13** — Primeira tentativa de coleta na máquina do usuário.
- DNS ok: `sapl.bauru.sp.leg.br` → 186.224.22.34 e 201.63.151.154 (o portal
  `www.bauru.sp.leg.br` usa os mesmos IPs).
- 186.224.22.34 responde ping, mas as portas 443 e 80 dão timeout. 201.63.151.154 não
  responde nem a ping.
- Outros sites funcionam normalmente (Google, Câmara dos Deputados, SAPL de Campinas),
  então a internet local está ok e o problema é específico do servidor de Bauru.
- Nada foi baixado. Ainda não dá para saber se o servidor está fora do ar ou se está
  bloqueando este IP. Próximo teste: abrir `https://sapl.bauru.sp.leg.br/api/` no celular
  com dados móveis (outro IP).
- Busca na web: o SAPL de Bauru continua na linha 2.x e tem páginas de sessão indexadas
  até 31/08/2026, então o sistema não foi trocado. O servidor esteve no ar recentemente;
  a falha de hoje é pontual ou de rede. A tentativa foi numa sexta à noite; testar de
  novo em horário de expediente.
- `coleta.py` reescrito: testa o servidor com 1 chamada antes de tudo; baixa tabelas
  pequenas inteiras e as grandes só da legislatura atual, paginadas com ordem fixa e
  conferindo a contagem; não repete chamada que deu 4xx; procura o voto nominal; valida
  os números (15–40 parlamentares, sessões, presenças, matérias) e só troca `dados/` se
  tudo passar. Grava `dados/coleta.json` com as consultas usadas (link de fonte).
- `resumo.py` criado: tabela geral e ficha por nome. Mostra a frequência com o código
  bruto do SAPL e separa "sessão sem registro" de falta.
- **Ainda não confirmado no servidor real:** a sintaxe `(tabela?filtro).sort(x).limit(n,o)`
  e o formato da resposta de `count()`. É a primeira coisa a conferir quando conectar.

## Revisão geral (13/11/2026)

- **Bug corrigido:** a página da Câmara não carregava. Um erro de aspas entrou na
  edição do cartão de salário e a página não foi testada depois.
  **Prevenção:** `verificar_site.py`, que roda no fim do `atualizar.py`.
- **Bug corrigido:** a página Dinheiro só tinha 2025. O coletor gravava tudo só no
  fim, e o PNCP lento segurava o TCE de 2026.
  **Agora:** cada fonte grava sozinha quando termina, e só se vier completa.
- **Validado:** API mensal do TCE e arquivo anual batem centavo por centavo
  (dez/2025, todos os órgãos).
- **Corrigido:** o "acento corrompido" do TCE era erro de leitura nosso
  (Windows-1252 lido como UTF-8).
- **Datas futuras:** 93 matérias com data após hoje são pedidos ainda não lidos
  (data da próxima sessão). O site marca "sessão agendada" e explica.
- README e CLAUDE.md atualizados.
