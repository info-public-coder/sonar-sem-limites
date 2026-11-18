# Radar Sem Limites · Bauru-SP

Site independente que mostra, só com dados oficiais, o que fazem os 21 vereadores
de Bauru-SP e para onde vai o dinheiro público da cidade.

Inspirado no [Radar PTlândia](https://radarptlandia.org), de Gabriel Damasceno, e
construído seguindo o manual que o autor publicou.

**Estado:** funciona localmente com dados reais. Ainda não foi publicado.

## Páginas

| Página | O que mostra | Fontes |
|---|---|---|
| `site/index.html` (Câmara) | Presença, propostas por tipo, votos nominais, pedidos por bairro e rua, salário | SAPL da Câmara, TCE-SP |
| `site/prefeitura.html` (Prefeitura) | Crachás da Prefeita, do vice e dos secretários: propostas enviadas à Câmara, quanto foi pago em cada área | Site da Prefeitura, SAPL, TCE-SP |
| `site/diretoria.html` (Diretoria de Ensino) | Administração da URE Bauru: quem comanda e quanto recebe, servidores da sede, diárias, gastos, contratos, limite da dispensa, ausências | Site da URE, folha do Estado, dados abertos da SEDUC, PNCP |
| `site/dinheiro.html` (Dinheiro) | Quanto foi pago, por área, por modalidade, quem recebeu, shows e eventos, contratos | TCE-SP, PNCP |

As páginas abrem direto do disco, sem servidor.

## Como atualizar

O Python do projeto fica em `..\..\.python_embed\python.exe`; não há `python` no
PATH. Na pasta `radar-bauru`:

```
..\..\.python_embed\python.exe atualizar.py
```

O comando coleta, gera as páginas e confere tudo num navegador sem janela. Para só
gerar e conferir com os dados que já existem, acrescente `--sem-coleta`.

Uma vez por ano, quando o TCE-SP publicar o ano fechado (arquivo de cerca de 2 GB,
lido em fluxo; só as linhas de Bauru ficam no disco):

```
..\..\.python_embed\python.exe coleta_tce_anual.py despesas 2026
```

**Rede:** o servidor da Câmara bloqueia a rede de casa. Para coletar a Câmara,
conecte o computador no roteador do celular. TCE-SP e PNCP abrem de qualquer rede.

## Atualização automática (GitHub Actions)

Dois robôs em `.github/workflows/`:

| Arquivo | Quando roda | O que faz |
|---|---|---|
| `testar-fontes.yml` | à mão (Actions → Testar fontes → Run workflow) | uma requisição por fonte, para saber o que responde a partir do GitHub |
| `atualizar.yml` | todo dia às 03:00 (Brasília) e à mão | coleta, gera as páginas, confere e publica no GitHub Pages |

- A pasta `dados/` não vai para o repositório (peso e dado pessoal). Ela fica no
  **cache do Actions**, que não é público: cada execução parte da última coleta boa.
- Só publica se as páginas forem geradas e passarem na conferência. Se algo
  falhar, o site no ar continua o mesmo e a execução aparece em vermelho na aba Actions.
- Na primeira execução o cache está vazio: o robô baixa tudo, inclusive o arquivo
  anual do TCE-SP (cerca de 2 GB lido em fluxo). Pode levar mais de uma hora.
- Para ligar: Settings → Pages → Source: **GitHub Actions**.
- `conferir_dados.py` roda no fim. Fonte que passou do prazo (Câmara 4 dias, TCE e PNCP 7, Prefeitura e
  servidores/pagamentos da URE 45, que dependem do computador local) deixa a execução **vermelha** e o
  GitHub manda e-mail; o site é publicado assim mesmo, com a data de cada fonte em "Situação dos dados".
- `publicar.yml` ("Publicar agora") publica a pasta `site/` como está no repositório, em ~1 minuto.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `coleta.py` | Baixa os dados da Câmara (API aberta do SAPL) para `dados/` |
| `coleta_gastos.py` | TCE-SP (ano corrente) e PNCP para `dados/gastos/` |
| `coleta_tse.py` | Fotos e votos de 2024 dos vereadores (dados abertos do TSE, lidos por trecho) |
| `coleta_prefeitura.py` | Equipe de governo e fotos (site da Prefeitura) para `dados/prefeitura/` |
| `coleta_diretoria.py` | URE Bauru: equipe, folha, servidores da sede, pagamentos, ausências, PNCP para `dados/diretoria/` |
| `coleta_tce_anual.py` | Arquivo anual do TCE-SP, só Bauru, para `dados/tce/` |
| `regras.py` | Como cada proposta é classificada e como ruas e bairros são lidos (o mesmo texto aparece no site) |
| `gerar_site.py` / `gerar_dinheiro.py` / `gerar_prefeitura.py` / `gerar_diretoria.py` | Geram `site/dados.js`, `site/dinheiro.js`, `site/prefeitura.js` e `site/diretoria.js` |
| `resumo.py` | Números de um vereador no terminal, para conferir com a ficha oficial |
| `verificar_site.py` | Confere as páginas: erros, seções desenhadas, largura de celular |
| `atualizar.py` | Roda tudo na ordem |
| `testar_fontes.py` | Testa se cada fonte responde (usado pelo robô de teste) |
| `conferir_dados.py` | Aponta fonte velha, buraco ou queda de quantidade; gera a seção "Situação dos dados" e o resumo do Actions |
| `estado.py` | Registra quando cada fonte deu certo pela última vez (usado pelos coletores) |
| `config.json` | Subsídio dos vereadores e suas fontes |
| `PLANO.md` / `PLANO-EXPANSAO.md` | Plano de implementação e decisões |
| `CLAUDE.md` | Documento de passagem da investigação original |

Os dados brutos (`dados/`) não vão para o repositório.

## Cuidados

Este projeto cita pessoas pelo nome. Um número errado derruba o projeto inteiro.

- Só dado oficial. Nada de print, boato ou reportagem como fonte de número.
- Mesma régua para todos os vereadores, de todos os partidos.
- Link para a fonte em cada número. O que é conta nossa é dito como conta nossa.
- Dado pessoal não entra: CPF, título de eleitor e data de nascimento são
  descartados na coleta.
- Dado ausente não é falta: se o sistema não registrou, o site não acusa.
- Coleta que falha não substitui a última versão boa.

Projeto independente, sem vínculo com a Câmara Municipal, a Prefeitura ou partidos.
