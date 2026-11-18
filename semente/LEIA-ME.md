# Semente

Cópia das versões já processadas de duas fontes que recusam os servidores do
GitHub Actions:

- `prefeitura/`: equipe de governo (site da Prefeitura de Bauru);
- `diretoria/`: equipe, folha (só quem está no site da URE e medianas por cargo),
  servidores da sede (contagens), pagamentos e contratos da URE Bauru
  (portal de dados abertos da Secretaria da Educação).

O robô (`.github/workflows/atualizar.yml`) copia daqui para `dados/` **só o que
estiver faltando**. Se a fonte responder, vale a coleta nova; se não, o site sai
com esta versão.

Nada aqui além do que o próprio site já mostra: sem folha completa do Estado,
sem data de nascimento, sem CPF.

Atualização: rodar `atualizar.py` no computador local renova esta pasta
automaticamente ao final; depois, enviar para o GitHub.
