# Cruzador AKD x CT2

**Desenvolvedor:** Leonel Diniz  
**Última atualização da documentação:** 30/04/2026  
**Ambiente-alvo:** Protheus, Oracle e Python

## Visão Geral

O Cruzador AKD x CT2 é uma solução de apoio à conciliação contábil e orçamentária entre registros das bases `AKD` e `CT2` do Protheus.

O projeto identifica correspondências entre lançamentos mesmo quando não existe uma chave única explícita. Para isso, combina regras documentais, valor, competência, histórico, contas, centro de custo, classe de valor, item contábil e sinais técnicos extraídos dos campos das bases.

O resultado principal é um relatório HTML navegável, complementado por arquivos CSV e JSON de apoio para análise e auditoria.

## Público-Alvo

Esta documentação atende três perfis:

- **Gestores:** visão objetiva do propósito, resultados e cuidados operacionais.
- **Usuários de negócio:** entendimento das entradas, saídas e leitura do relatório.
- **Equipe técnica:** execução, manutenção, segurança e atualização dos dados.

## Objetivo do Projeto

O objetivo é reduzir o esforço manual de análise entre AKD e CT2, oferecendo uma trilha estruturada de evidências para:

- localizar matches fortes entre lançamentos;
- destacar registros ainda sem correspondência final;
- apoiar a investigação de divergências;
- evidenciar grupos potenciais `1xN` e `Nx1`;
- consolidar informações em um relatório de consulta prática.

## Principais Entregas

- Relatório HTML em `saida/relatorio_conciliacao.html`.
- Resumo executivo e técnico em `saida/resumo_analise.json`.
- Bases auxiliares em CSV para auditoria dos matches e pendências.
- Atualização automática dos CSVs brutos a partir do Oracle, sempre em modo somente leitura.
- Proteções para evitar versionamento de credenciais, backups, artefatos ADVPL e arquivos gerados.

## Estrutura do Projeto

```text
projeto-cruzador/
  config/
    oracle.example.json
  dados/
    brutos/
      DADOS-AKD010.csv
      DADOS-CT2010.csv
      GLOSSARIO-CONTAS.csv
    referencia/
      DICIONARIO.csv
  scripts/
    atualizar_csvs_brutos_oracle.py
    gerar_relatorio_conciliacao_akd_ct2.py
    validar_sql_somente_leitura.py
  sql/
    AKD010.sql
    CT2010.sql
    GLOSSARIO-CONTAS.sql
  .githooks/
    pre-commit
    verificar_credenciais_pre_commit.py
  README.md
  requirements.txt
```

Arquivos e pastas como `saida/`, `docs/`, `.vscode/`, backups, logs, credenciais reais e artefatos ADVPL não devem ser enviados ao Git.

## Entradas

O relatório usa os seguintes arquivos:

- `dados/brutos/DADOS-AKD010.csv`
- `dados/brutos/DADOS-CT2010.csv`
- `dados/brutos/GLOSSARIO-CONTAS.csv`
- `dados/referencia/DICIONARIO.csv`

Os CSVs brutos podem ser atualizados por consulta Oracle usando as queries localizadas em:

- `sql/AKD010.sql`
- `sql/CT2010.sql`
- `sql/GLOSSARIO-CONTAS.sql`

## Saídas

Os arquivos gerados ficam em `saida/`.

Principais saídas:

- `relatorio_conciliacao.html`: relatório principal para navegação e análise.
- `resumo_analise.json`: resumo da execução e indicadores principais.
- `matches_linha_a_linha.csv`: matches selecionados.
- `comparativo_conciliacao.csv`: comparativo detalhado AKD x CT2.
- `akd_sem_match.csv`: registros AKD sem match final.
- `ct2_sem_match.csv`: registros CT2 sem match final.
- `grupos_match_potenciais.csv`: indícios de grupos `1xN` e `Nx1`.
- `overlap_xdoc.csv`, `overlap_xdoc_at01cr.csv`, `overlap_xnumap.csv`: sobreposições documentais.

A pasta `saida/` é gerada localmente e não deve ser versionada.

## Regras de Filtro

Antes do cruzamento, os dados são filtrados para manter apenas os registros relevantes.

### AKD

- `AKD_TPSALD IN ('LQ', 'PG', 'AR', 'RB')`

### CT2

- `CT2_MOEDLC = '01'`
- `CT2_DC IN ('1', '2')`

Algumas abas do relatório usam recortes próprios, como a análise `CTBxORC DET`, que compara contas de referência e contas contábeis com filtros específicos de status, saldo, moeda e natureza da conta.

## Lógica de Cruzamento

O reconciliador utiliza uma combinação de âncoras e reforços de score.

Principais âncoras:

- `AKD_XDOC = CT2_XDOC`
- `AKD_XDOC = CT2_AT01CR`
- `AKD_XNUMAP = CT2_XDOCUM`
- `AKD_XDOC` no formato `CT2<recno>` apontando para `CT2.R_E_C_N_O_`
- tokens estruturados entre `AKD_CHAVE` e `CT2_KEY`
- histórico igual com data e valor para processos específicos
- token `RI:` com data e valor para o processo `900027`
- competência e valor
- documentos extraídos do histórico e de campos auxiliares

Reforços considerados:

- mesma competência;
- mesma data;
- mesmo valor;
- mesma conta;
- mesmo centro de custo;
- mesma classe de valor;
- mesmo item contábil;
- similaridade textual do histórico;
- documentos qualificados extraídos do histórico;
- combinações entre documento, competência, conta, centro de custo e classe.

O pareamento final é feito de forma controlada para evitar escolhas duplicadas indevidas. Quando existem evidências fortes, mas disputa entre múltiplos registros, o caso pode aparecer em `grupos_match_potenciais.csv`.

## Relatório HTML

O relatório principal é `saida/relatorio_conciliacao.html`.

Ele inclui:

- dashboard executivo;
- visão de matches;
- visão AKD;
- visão CT2;
- registros AKD sem match;
- registros CT2 sem match;
- análise `CTBxORC DET`;
- glossário de contas;
- filtros, busca livre, ordenação e redimensionamento de colunas;
- indicadores visuais de divergência;
- identificação da versão gerada.

## Como Executar

Execute os comandos a partir da raiz do projeto.

### 1. Instalar Dependências

```powershell
python -m pip install -r requirements.txt
```

### 2. Gerar Relatório com CSVs Locais

```powershell
python scripts/gerar_relatorio_conciliacao_akd_ct2.py
```

### 3. Abrir o Relatório

```powershell
start .\saida\relatorio_conciliacao.html
```

## Atualização dos Dados Brutos pelo Oracle

O projeto possui um conector Oracle para atualizar os CSVs brutos.

### Configuração

Copie o exemplo e preencha localmente:

```powershell
copy .\config\oracle.example.json .\config\oracle.json
notepad .\config\oracle.json
```

O arquivo `config/oracle.json` contém credenciais reais e nunca deve ser enviado ao Git.

### Atualizar Todas as Bases

```powershell
python scripts/atualizar_csvs_brutos_oracle.py
```

Esse comando consulta Oracle e substitui:

- `dados/brutos/DADOS-AKD010.csv`
- `dados/brutos/DADOS-CT2010.csv`
- `dados/brutos/GLOSSARIO-CONTAS.csv`

Antes da substituição, os arquivos atuais são copiados para `dados/brutos/backups/`.

### Atualizar Apenas Algumas Bases

```powershell
python scripts/atualizar_csvs_brutos_oracle.py --somente akd
python scripts/atualizar_csvs_brutos_oracle.py --somente ct2 glossario
```

## Segurança Banco de Dados

Toda interação com Oracle deve ser exclusivamente de consulta.

O projeto bloqueia qualquer SQL que não seja `SELECT` antes de enviar o comando ao banco. Também são bloqueados comandos múltiplos e palavras-chave que possam alterar dados, estruturas, permissões ou transações.

Comandos bloqueados incluem:

- `UPDATE`
- `DELETE`
- `INSERT`
- `MERGE`
- `DROP`
- `ALTER`
- `CREATE`
- `TRUNCATE`
- `GRANT`
- `REVOKE`
- `COMMIT`
- `ROLLBACK`
- `BEGIN`
- `DECLARE`
- `CALL`
- `EXEC`
- `FOR UPDATE`

A validação fica em `scripts/validar_sql_somente_leitura.py` e é usada tanto pelo gerador do relatório quanto pelo atualizador de CSVs brutos.

## Segurança Git e Informações Sensíveis

Nunca versionar:

- senhas;
- usuários reais de banco;
- DSNs reais;
- tokens;
- chaves privadas;
- certificados privados;
- wallets Oracle;
- arquivos `.env`;
- `tnsnames.ora`;
- `sqlnet.ora`;
- backups;
- logs;
- artefatos ADVPL;
- relatórios e arquivos gerados em `saida/`.

O repositório possui:

- regras no `.gitignore`;
- hook local de pre-commit em `.githooks/`;
- scanner de padrões sensíveis em `.githooks/verificar_credenciais_pre_commit.py`.

Para habilitar os hooks em um clone novo:

```powershell
git config core.hooksPath .githooks
```

Antes de commitar, revise:

```powershell
git status
git diff --cached
```

## Governança de Versionamento

Devem ser versionados:

- código Python essencial para geração do relatório e atualização dos dados;
- SQLs de consulta;
- modelo de configuração sem credenciais;
- requisitos Python;
- README e registros de revisão da documentação;
- dados brutos necessários ao relatório, quando aprovados para versionamento.

Não devem ser versionados:

- credenciais;
- backups;
- logs;
- saídas geradas;
- arquivos ADVPL;
- configurações locais de IDE;
- documentação auxiliar sem dependência direta da entrega;
- arquivos com informação sensível ou operacional restrita.

## Estado Atual da Última Execução

Última execução registrada localmente:

- AKD filtrado: `2.125` linhas
- CT2 filtrado: `650` linhas
- candidatos gerados: `1.177`
- matches selecionados: `290`
- matches muito fortes: `283`
- matches fortes: `7`
- grupos potenciais: `536`

Esses números dependem do recorte de dados vigente e não devem ser comparados com execuções anteriores sem verificar filtros, período e origem dos arquivos.

## Observações Importantes

- `RECNO` e `LOTE` não são usados como chave direta de conciliação entre AKD e CT2.
- `RECNO` da CT2 pode ser usado como evidência indireta quando codificado em `AKD_XDOC`.
- Um registro em trilha de sem match não significa ausência total de evidência; significa apenas que ele não foi escolhido no pareamento final `1x1`.
- O glossário aceita estrutura antiga com `CT1_CONTA` e estrutura nova com `ZL_ITEMORC`.
- O relatório é uma ferramenta de apoio à análise; a validação contábil final continua sendo responsabilidade da área usuária.

## Manutenção

Ao revisar ou atualizar a documentação:

1. Atualize a data no cabeçalho deste README.
2. Registre a alteração em `REVISOES_DOCUMENTACAO.md`.
3. Verifique se os comandos documentados ainda funcionam.
4. Confirme que não há credenciais ou dados sensíveis no conteúdo.

## Próximos Passos Sugeridos

- Exibir no HTML as evidências completas que sustentaram cada match.
- Criar trilha específica para conflitos `Nx1`.
- Evoluir a conciliação por grupo `1xN` e `NxN`.
- Avaliar mascaramento ou redução dos CSVs brutos caso exista risco de exposição de dados sensíveis.
