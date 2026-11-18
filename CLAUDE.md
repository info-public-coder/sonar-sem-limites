# Sonar Sem Limites — documento de passagem

Este arquivo existe para que o Claude (no VS Code / Claude Code) continue este projeto
exatamente de onde a conversa anterior parou, sem precisar refazer a investigação.

**Leia este arquivo inteiro antes de começar.**

> **Estado atual (13/11/2026):** a coleta rodou e o site funciona localmente com dados
> reais. Este arquivo registra a investigação original; várias suposições dele foram
> corrigidas pelos dados (presença em `ordem_dia_presenca`, voto nominal existe,
> autoria sem autor principal etc.). O estado e as decisões estão em `PLANO.md` e
> `PLANO-EXPANSAO.md`; como rodar está no `README.md`.

---

## 1. O que é o projeto

Construir um site que mostre, **só com dados oficiais**, o que cada vereador de
**Bauru-SP** faz: presença nas sessões, propostas apresentadas e como votou.

É uma réplica do **Radar PTlândia** (https://radarptlandia.org), feito por Gabriel
Damasceno para Hortolândia-SP. O autor publicou um manual de 3 páginas explicando o
passo a passo — ele está em `manual/Como-criar-o-Radar-da-sua-cidade.pdf`
(o usuário precisa copiar o PDF para essa pasta; ele foi anexado na conversa original).

### Estrutura do site de referência (levantada do radarptlandia.org)

Seções, nos títulos originais:

1. **"O que pediram pelo seu bairro?"** — campo de busca por bairro ou rua; sem texto,
   mostra a cidade inteira.
2. **"O problema que não some"** — pedidos repetidos para a mesma rua, com contagem e
   datas, indicando problema persistente.
3. **"O trabalho da Câmara"**, com o subtítulo **"Homenagem ou trabalho?"**.
4. **"Os N vereadores"** — lista com busca por nome, filtro por partido e ordenação:
   Nome (A–Z), Quem mais faltou, Mais propostas de lei, Mais homenagens,
   Mais pedidos para os bairros, Quem mais votou "não".
5. **"Transparência" / "De onde vêm os números"** — fontes e critérios.

No topo: indicador **"Ao vivo"**, subtítulo "Raio-X de [cidade]", e um **cartão de
salário** com contador correndo em tempo real no navegador
("Salário pago aos N vereadores desde a posse").

No rodapé: aviso de projeto independente, sem vínculo com Câmara, Prefeitura ou partidos.

**Bauru tem 21 vereadores** (Hortolândia tem 19).

---

## 2. Passo 1 do manual: JÁ FOI FEITO. Resultado abaixo.

O manual diz para não aceitar "acho que dá" e baixar dados de verdade antes de seguir.
Isso foi feito. **Funciona em Bauru.**

### A Câmara de Bauru usa SAPL

- Portal: `https://www.bauru.sp.leg.br`
- SAPL: `https://sapl.bauru.sp.leg.br`

A busca pública (Atividade Legislativa → Matérias Legislativas) é um **iframe** apontando
para `https://sapl.bauru.sp.leg.br/generico/materia_pesquisar_form` e **tem reCAPTCHA**
("Não sou um robô"). Não tente automatizar esse formulário — não é preciso, e resolver
captcha não é uma opção.

### A API aberta (este é o caminho)

O SAPL de Bauru é da linha 2.x e expõe **HTSQL** em `/api/`, **sem captcha e sem login**.
Isso dá leitura direta das tabelas do banco, com saída em JSON, CSV, XML ou TSV.

Formato da URL, confirmado funcionando:

```
https://sapl.bauru.sp.leg.br/api/<consulta>/:json
https://sapl.bauru.sp.leg.br/api/<consulta>/:csv
```

Exemplo real que retornou HTTP 200 com dados:

```
https://sapl.bauru.sp.leg.br/api/parlamentar.limit(3)/:json
```

Formato da resposta JSON — atenção, vem com **lista dentro de lista**:

```json
{ "parlamentar": [ [ { "cod_parlamentar": 1, "nom_completo": "...", ... } ] ] }
```

Sintaxe HTSQL útil:
- `tabela.limit(N)` — limita
- `tabela?coluna=valor` — filtra (ex.: `materia_legislativa?ano_ident_basica=2025`)
- `tabela{col1,col2}` — escolhe colunas
- `tabela.top(N,coluna)` — ordena e limita
- `count(tabela)` — contagem

### Tabelas e colunas confirmadas (todas retornaram 200)

| Tabela | Colunas observadas |
|---|---|
| `parlamentar` | cod_parlamentar, nom_completo, nom_parlamentar, sex_parlamentar, dat_nascimento, num_tit_eleitor, cod_casa, num_tel_parlamentar, num_fax_parlamentar, … |
| `mandato` | cod_mandato, num_legislatura, dat_inicio_mandato, dat_fim_mandato, num_votos_recebidos, cod_parlamentar |
| `legislatura` | num_legislatura, dat_inicio, dat_fim, dat_eleicao, ind_excluido |
| `filiacao` | dat_filiacao, cod_parlamentar, cod_partido, ind_excluido |
| `partido` | cod_partido, sgl_partido, nom_partido, dat_criacao, dat_extincao, ind_excluido |
| `sessao_plenaria` | cod_sessao_plen, tip_sessao, cod_sessao_leg, num_legislatura, dat_inicio_sessao, dia_sessao, hr_inicio_sessao, num_sessao_plen, dat_fim_sessao, ind_excluido |
| `sessao_plenaria_presenca` | cod_presenca_sessao, cod_sessao_plen, cod_parlamentar, tip_frequencia, txt_justif_ausencia, ind_excluido |
| `ordem_dia_presenca` | cod_presenca_ordem_dia, cod_sessao_plen, cod_parlamentar, tip_frequencia, txt_justif_ausencia, ind_excluido |
| `materia_legislativa` | cod_materia, tip_id_basica, num_ident_basica, ano_ident_basica, dat_apresentacao, tip_apresentacao, cod_regime_tramitacao, num_origem_externa, nom_apelido, ind_tramitacao, ind_polemica, des_objeto, ind_complementar, **txt_ementa**, txt_indexacao, txt_observacao, tip_quorum, cod_assunto, ind_excluido |
| `tipo_materia_legislativa` | tip_materia, sgl_tipo_materia, des_tipo_materia, tip_natureza, ind_num_automatica, quorum_minimo_votacao, ind_publico, ind_excluido |
| `autoria` | cod_autor, cod_materia, ind_primeiro_autor, ind_excluido |
| `autor` | cod_autor, cod_parlamentar, tip_autor, ind_excluido |
| `ordem_dia` | cod_ordem, cod_sessao_plen, cod_materia, dat_ordem, txt_observacao, num_ordem, tip_turno, tip_votacao, tip_quorum, ind_excluido |
| `expediente_materia` | cod_ordem, cod_sessao_plen, cod_materia, dat_ordem, txt_observacao, ind_excluido, num_ordem, tip_votacao, tip_quorum |
| `registro_votacao` | cod_votacao, tip_resultado_votacao, cod_materia, cod_ordem, **num_votos_sim, num_votos_nao, num_abstencao**, txt_observacao, ind_excluido |

Tabelas que **não** existem com esse nome (retornaram 400):
`presenca_sessao_plenaria`, `votacao`, `votacao_parlamentar`, `voto_parlamentar`.

**Sempre filtrar `ind_excluido=0`.** O SAPL marca registros excluídos em vez de apagar.

---

## 3. A lacuna conhecida — resolver primeiro

`registro_votacao` guarda apenas o **placar** da votação (quantos sim, não, abstenção),
não o voto nominal de cada vereador.

**Tarefa aberta:** descobrir se existe tabela de voto individual. Nomes ainda não
testados: `registro_votacao_parlamentar`, `voto`, `votacao_nominal`,
`registro_votacao_parlamentar_detalhe`. Use o link **"Esquema"** no canto superior
esquerdo de `https://sapl.bauru.sp.leg.br/api/` para listar todas as tabelas do banco de
uma vez, em vez de adivinhar nome por nome.

**Se não existir:** o Sonar Sem Limites sai **sem** o ranking "Quem mais votou não", e o site
precisa dizer isso na seção de transparência. O manual é explícito:
*"Dado ausente não é falta"* — se o sistema não registrou, o site não pode acusar.

---

## 4. Cuidados que não são opcionais

- **A API devolve dado pessoal sensível.** `parlamentar` traz `num_tit_eleitor` (título de
  eleitor) e `dat_nascimento`. **Nada disso entra no site, nem nos arquivos commitados no
  GitHub.** O script de coleta deve descartar essas colunas na hora de salvar.
  Só nome, partido, mandato e contato de gabinete são públicos.
- **O servidor é frágil.** Ele parou de responder depois de ~25 requisições rápidas
  durante a investigação. O coletor precisa de pausa entre as chamadas (1–2 segundos),
  User-Agent se identificando, e tentar de novo com calma em caso de erro.
  O manual já avisa disso em "O que pode dar errado".
- **Robô que falha não publica.** Se a coleta vier incompleta ou estranha, o site fica com
  a última versão boa. Nunca publicar dados pela metade.
- **Mesma régua para todos.** Todos os 21 vereadores, de todos os partidos, pelo mesmo
  critério.
- **Link para a fonte oficial em cada número.**
- **Diga o que é estimativa.** O salário, por exemplo, é conta nossa, não dado baixado.

---

## 5. Onde paramos e o que vem agora

A coleta não chegou a ser feita por completo: o ambiente de nuvem da conversa anterior
**não tem acesso de rede ao domínio `bauru.sp.leg.br`** (bloqueio do proxy), e o acesso
pelo navegador travou quando o servidor do SAPL começou a recusar conexões.

**No VS Code, na máquina do usuário, esse bloqueio não existe.** A coleta deve funcionar
direto. Comece por aí.

### Plano

1. **Coletar** — rodar `python coleta.py` (está nesta pasta, ainda **não testado contra o
   servidor real**; ajuste o que quebrar). Salva CSV/JSON em `dados/`.
2. **Resolver a lacuna do voto nominal** (seção 3).
3. **Classificar as propostas** em grupos que qualquer pessoa entenda: pedidos de melhoria
   nos bairros, perguntas e cobranças, homenagens (parabéns, pesar, título de cidadão,
   nome de rua, data comemorativa), projetos de lei, outros. Use `sgl_tipo_materia` +
   palavras do `txt_ementa`. Mesma regra para todos, e explique a regra no site.
4. **Calcular presença** por vereador a partir de `sessao_plenaria_presenca`.
5. **Extrair bairros e ruas** do `txt_ementa` para a busca por local, e cruzar pedidos
   repetidos no mesmo lugar ("O problema que não some"). Avisar no site que pedido
   repetido não prova que a Prefeitura ignorou.
6. **Construir o site** — página única, fundo branco, linguagem simples, pensada para o
   morador no celular. Sem nota, sem opinião: só o dado.
7. **Conferir antes de publicar** (Passo 5 do manual) — abrir a ficha oficial de dois ou
   três vereadores e comparar com o site. Listar o que não bateu e o que é estimativa.
8. **Publicar no GitHub Pages** com GitHub Actions rodando de madrugada (Passo 6).
9. Domínio próprio é opcional e fica para depois.

---

## 6. Como continuar a conversa no VS Code

Abra esta pasta no VS Code com o Claude Code e diga algo como:

> Leia o CLAUDE.md desta pasta. Vamos continuar o Sonar Sem Limites a partir da seção 5.
> Comece rodando a coleta e me mostre os números de dois vereadores antes de montar
> qualquer página.
