# Cruzador AKDXCT2

Projeto para conciliacao e cruzamento de lancamentos entre as bases `AKD` e `CT2`, com foco em ambiente `Protheus`, usando `Python` e saida analitica em `CSV`, `JSON` e `HTML`.

## Finalidade

Identificar o maior numero possivel de correspondencias entre registros da `AKD` e da `CT2`, mesmo quando nao existe uma chave unica explicita de cruzamento.

O reconciliador trabalha com:
- regras documentais
- comparacao por valor e competencia
- similaridade de historico
- contas, centro de custo, classe de valor e item contabil
- documentos extraidos do historico
- regras especificas de ligacao entre campos tecnicos das bases

## Estrutura

- `dados/brutos/`
- `dados/referencia/`
- `docs/`
- `scripts/`
- `saida/`

Arquivos principais:
- `scripts/analisar_cruzamento_akd_ct2.py`
- `scripts/analisar_match_profundo_akd_ct2.py`
- `scripts/gerar_consulta_akc_ct5_excel.py`
- `docs/MEMORIA_CRUZADOR_AKDXCT2.md`
- `docs/estrategia_cruzamento.md`
- `docs/consulta_akc_ct5_lado_a_lado.sql`
- `saida/relatorio_conciliacao.html`
- `saida/resumo_analise.json`

## Entradas

Arquivos esperados em `dados/brutos/`:
- `DADOS-AKD010.csv`
- `DADOS-CT2010.csv`
- `GLOSSARIO-CONTAS.csv` ou `GLOSSARIO-CONTAS.xlsx`

Arquivos de referencia em `dados/referencia/`:
- `DDL-AKD.txt`
- `DDL-CT2.txt`
- `DICIONARIO.csv`

## Filtros De Origem

Antes do cruzamento, o script filtra os dados com estas regras:

### CT2
- `CT2_MOEDLC = '01'`
- `CT2_DC IN ('1', '2')`

### AKD
- `AKD_TPSALD IN ('LQ', 'PG', 'AR', 'RB')`

## Regras De Cruzamento

As principais ancoras do reconciliador sao:

1. `AKD_XDOC = CT2_XDOC`
2. `AKD_XDOC = CT2_AT01CR`
3. `AKD_XNUMAP = CT2_XDOCUM`
4. `AKD_XDOC` no formato `CT2<recno>` apontando para `CT2.R_E_C_N_O_`
5. `AKD_CHAVE` x `CT2_KEY` por tokens estruturados e alfanumericos extraidos das chaves compostas
6. para `AKD_PROCES IN (900013, 900025, 900026)`, `AKD_HIST = CT2_HIST` com `data exata + valor igual` como ancora textual forte
7. para `AKD_PROCES = 900027`, token de `10` digitos apos `RI:` em `AKD_HIST` e `CT2_HIST` com `data exata + valor igual`
8. `documentos extraidos do historico` com filtro de qualidade e controle de frequencia
9. `competencia + valor`
10. `documentos extraidos de historico e campos auxiliares`

## Extracao Avancada De Documento

O script extrai e normaliza documentos presentes em campos como:

### AKD
- `AKD_XDOC`
- `AKD_XNUMAP`
- `AKD_CHAVE`
- `AKD_IDREF`
- `AKD_XHISTO`
- `AKD_HIST`

### CT2
- `CT2_XDOC`
- `CT2_AT01CR`
- `CT2_XDOCUM`
- `CT2_XNUMCT`
- `CT2_DOC`
- `CT2_KEY`
- `CT2_HIST`

Padroes considerados:
- `DOC`
- `DOC N`
- `REF DOC`
- `NF`
- `AP`
- `NR`
- prefixos como `SE`, `SF`, `AK`, `SEU`, `FFC`, `RFB`
- variantes com e sem zeros a esquerda

Filtros adicionais para documentos vindos de historico:
- descarte de tokens genericos, datas soltas e identificadores muito curtos
- priorizacao de documentos com perfil de identificador real, como tracking, referencia fiscal e numero documental mais longo
- bloqueio de documentos excessivamente frequentes para reduzir falso positivo em massa

## Reforcos De Score

O score do match pode ser reforcado por:
- documento igual
- documento AKD igual ao `CT2_AT01CR`
- numero AP igual
- historico exato com `data exata + valor igual` quando `AKD_PROCES IN (900013, 900025, 900026)`
- token `RI:` com `data exata + valor igual` quando `AKD_PROCES = 900027`
- ligacao `AKD_XDOC -> RECNO CT2`
- token estruturado entre `AKD_CHAVE` e `CT2_KEY`
- documento qualificado extraido do historico
- mesma competencia
- mesma data exata
- mesma conta
- mesmo centro de custo
- mesma classe de valor
- mesmo item contabil
- combinacao `competencia + conta + CC`
- combinacao `competencia + classe de valor`
- combinacao `competencia + conta + classe de valor`
- combinacao `competencia + CC + classe de valor`
- evidencias documentais extraidas do historico combinadas com `competencia`, `conta`, `CC` e `classe`
- evidencias documentais extraidas do historico combinadas com `data exata`, `conta` e `valor`
- evidencias por chave estruturada combinadas com `competencia`, `conta` e `classe`
- tokens em comum no historico
- similaridade textual do historico
- reforco textual para casos sem ancora documental explicita, quando `texto`, `competencia`, `conta` ou `classe` convergem

## Saidas

Arquivos gerados em `saida/`:
- `matches_linha_a_linha.csv`
- `comparativo_conciliacao.csv`
- `resumo_analise.json`
- `overlap_xdoc.csv`
- `overlap_xdoc_at01cr.csv`
- `overlap_xnumap.csv`
- `akd_sem_match.csv`
- `ct2_sem_match.csv`
- `grupos_match_potenciais.csv`
- `relatorio_conciliacao.html`

Arquivos gerados pela analise profunda de match em `saida/analise_match_profunda/`:
- `candidatos_match_detalhados.csv`
- `assinaturas_evidencia.csv`
- `top_candidatos_akd_sem_match.csv`
- `top_candidatos_ct2_sem_match.csv`
- `hipoteses_novas_regras.csv`
- `campos_prioritarios_akd.csv`
- `campos_prioritarios_ct2.csv`
- `sobreposicao_campos_cruzados.csv`
- `correlacao_campos_match.csv`
- `origens_candidatos.csv`
- `resumo_match_profundo.json`

## Relatorio HTML

O arquivo `saida/relatorio_conciliacao.html` possui:
- aba `Dashboard`
- aba `Matches`
- aba `AKD pura`
- aba `CT2 pura`
- aba `AKD sem match`
- aba `CT2 sem match`
- icones visuais pertinentes em todas as abas para facilitar a navegacao
- aba `ORCxCTB` como ultima aba do relatorio, com icone visual de relatorio, consolidado AKD x CT2 por conta de referencia, descricao da conta consultada no glossario, coluna `Origem` e contas presentes apenas de um lado
- filtro `Status contas` na aba `ORCxCTB` para separar contas `ok` de contas `divergente`
- opcao para recolher ou expandir a secao de filtros no topo do relatorio
- filtros, busca livre e ordenacao
- redimensionamento de colunas
- expansao das colunas de historico
- indicadores de divergencia de data, valor e conta
- identificacao de versao no topo com data de atualizacao e link para o commit do Git

## Como Executar

No PowerShell, a partir da raiz do projeto:

```powershell
python scripts/analisar_cruzamento_akd_ct2.py
```

Para rodar a analise profunda segregada, focada em descobrir novos matches:

```powershell
python scripts/analisar_match_profundo_akd_ct2.py
```

Para limitar a trilha de investigacao aos `N` melhores candidatos por registro sem match:

```powershell
python scripts/analisar_match_profundo_akd_ct2.py --top 10
```

Para ampliar a profundidade da busca usando mais colunas e mais blocos de candidatos:

```powershell
python scripts/analisar_match_profundo_akd_ct2.py --modo amplo
```

Para varrer de forma ainda mais pesada, incluindo grupos por valor puro:

```powershell
python scripts/analisar_match_profundo_akd_ct2.py --modo exaustivo --limite-grupo-valor 0 --top 20
```

Para abrir o relatorio:

```powershell
start .\saida\relatorio_conciliacao.html
```

## Estado Atual

Totais da rodada atual, conforme `saida/resumo_analise.json`:
- `AKD`: `20.346`
- `CT2`: `27.966`
- `candidatos_gerados`: `264.308`
- `matches_selecionados`: `9.874`
- `muito_forte`: `9.392`
- `forte`: `462`
- `provavel`: `20`

Na versao atual, o projeto ja contempla:
- cruzamento documental
- cruzamento por valor e competencia
- extracao avancada de documentos
- extracao qualificada de documento a partir do historico com filtro de frequencia
- ancora textual exata por historico com `data + valor` para os processos `900013`, `900025` e `900026`
- ancora por token `RI:` com `data + valor` para o processo `900027`
- ligacao entre `AKD_XDOC` e `RECNO` da `CT2`
- cruzamento direto entre `AKD_XDOC` e `CT2_AT01CR`
- cruzamento por tokens estruturados entre `AKD_CHAVE` e `CT2_KEY`
- reforco de score para `AKD_XNUMAP -> CT2_XDOCUM` e `AKD_XNUMAP -> CT2_AT04DB`
- blocos residuais mais amplos por `ano + valor`, `trimestre + valor`, `conta + valor`, `CC + valor` e `classe + valor`
- reforcos compostos por `documento extra + competencia/conta/CC/classe`
- reforcos compostos por `documento do historico + data exata/competencia + conta + valor`
- reforcos compostos por `chave estruturada + competencia/conta/classe`
- reforco textual para matches sem ancora direta, quando o contexto operacional converge
- trilha segregada para grupos potenciais `1xN` e `Nx1` quando o `1x1` bloqueia candidatos muito fortes
- painel visual com dashboard e trilhas de pendencia
- identificacao visual da versao do cruzador no HTML
- exibicao, no topo do HTML, da data de atualizacao dos arquivos ativos de `AKD`, `CT2` e `Glossario`
- analise profunda segregada para investigar candidatos e desenhar novas regras de match
- na aba `Glossario de contas`, todas as colunas ficam visiveis por padrao e a largura e redistribuida para ocupar toda a grid

## Observacoes Importantes

- `RECNO` e `LOTE` nao sao usados como chave direta de conciliacao entre `AKD` e `CT2`
- o `RECNO` da `CT2` pode ser usado como evidencia indireta quando codificado em `AKD_XDOC`
- um registro aparecer em trilha de `sem match` nao significa necessariamente ausencia total de indicio, e sim que ele nao foi escolhido no pareamento final `1x1`
- a base atual esta sendo trabalhada com recorte filtrado, entao os totais nao devem ser comparados com rodadas antigas sem considerar os filtros de origem
- excecao: a aba `ORCxCTB` usa um recorte proprio para analise por conta, com `AKD_STATUS = 1`, `AKD_TPSALD IN ('LQ', 'PG', 'AR', 'RB')`, `AKD_ENT05` iniciado por `1`, `3` ou `4`, `CT2_MOEDLC = '01'`, `CT2_TPSALD = '1'` e `CT2_DEBITO` ou `CT2_CREDIT` iniciados por `1`, `3` ou `4`
- o glossario de contas aceita tanto a estrutura antiga com `CT1_CONTA` quanto a nova com `ZL_ITEMORC`; ambas sao exibidas na aba de glossario como `Conta`

## Proximos Passos Sugeridos

- integrar `GLOSSARIO-CONTAS.xlsx` como filtro e descricao no relatorio
- mostrar no HTML quais evidencias sustentaram cada match
- criar trilha especifica para conflitos `Nx1`
- evoluir reconciliacao por grupo `1xN` e `NxN`

## Analise Profunda De Match

O script `scripts/analisar_match_profundo_akd_ct2.py` serve para investigar candidatos de cruzamento sem alterar a logica principal do reconciliador.

Ele foi pensado para apoiar a descoberta de novas regras, mostrando:
- todos os candidatos de match gerados pelo motor atual, com score, evidencias e status de selecao
- candidatos adicionais descobertos por blocos mais amplos como `ano + valor`, `trimestre + valor`, `conta + valor`, `CC + valor`, `classe + valor`, `item + valor`, `filial + valor` e, no modo exaustivo, `valor puro`
- assinaturas recorrentes de evidencia para entender o que mais gera match e o que mais fica bloqueado
- correlacao entre outras colunas relevantes das duas bases para apoiar novas hipoteses de regra
- perfil automatico das colunas mais preenchidas e mais discriminantes de cada base
- sobreposicao entre campos cruzaveis normalizados, incluindo documento, token estruturado, conta, centro de custo, classe, item, mes, ano e trimestre
- os melhores candidatos para cada `AKD` e `CT2` que ficaram sem match final
- hipoteses de novas regras com base em combinacoes recorrentes de sinais como `AT04DB`, `competencia`, `conta`, `CC`, `texto`, `tokens`, `chave estruturada` e `documento extra`
- hipoteses de novas regras com base em combinacoes recorrentes de sinais como `AT01CR`, `AT04DB`, `competencia`, `conta`, `CC`, `texto`, `tokens`, `chave estruturada` e `documento extra`

## Grupos Potenciais 1xN E Nx1

O reconciliador principal continua fechando a conciliacao oficial em `1x1`, mas agora tambem exporta a trilha `saida/grupos_match_potenciais.csv`.

Essa trilha destaca casos em que:
- existe evidencia muito forte de match
- ha ancora documental ou estrutural
- o contexto contabil tambem converge
- mas o pareamento final bloqueia o caso por disputa entre dois ou mais registros

Os tipos atuais sao:
- `akd_1xN`: um registro AKD com multiplos CT2 muito fortes
- `ct2_Nx1`: um registro CT2 com multiplos AKD muito fortes

Essa saida foi criada para apoiar a futura implementacao de reconciliacao por grupo sem perder a seguranca do fluxo `1x1`.

Leitura sugerida dos resultados:
- comece por `resumo_match_profundo.json`
- depois revise `hipoteses_novas_regras.csv`
- em seguida leia `correlacao_campos_match.csv` e `origens_candidatos.csv`
- depois use `campos_prioritarios_akd.csv`, `campos_prioritarios_ct2.csv` e `sobreposicao_campos_cruzados.csv` para localizar novas colunas promissoras
- em seguida priorize `top_candidatos_akd_sem_match.csv` e `top_candidatos_ct2_sem_match.csv`
- use `assinaturas_evidencia.csv` para decidir quais combinacoes merecem virar regra nova no cruzador principal
