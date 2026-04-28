# Memoria do Projeto Cruzador AKD x CT2

## Objetivo
Construir e evoluir uma rotina em Python para analisar e reconciliar movimentos da base orcamentaria `AKD` com movimentos da base contabil `CT2`, usando os arquivos Excel disponiveis no projeto e mantendo rastreabilidade funcional para auditoria.

## Fontes atuais
- `dados/brutos/DADOS-AKD010.xlsx`
- `dados/brutos/DADOS-CT2010.xlsx`
- `dados/brutos/GLOSSARIO-CONTAS.xlsx`
- `dados/referencia/DICIONARIO.xlsx`
- `dados/referencia/DDL-AKD.txt`
- `dados/referencia/DDL-CT2.txt`

## Estrutura atual da pasta
- `dados/brutos/`: arquivos Excel de entrada
- `dados/referencia/`: DDLs e dicionario de campos
- `docs/`: memoria do projeto e estrategia funcional
- `scripts/`: automacao Python
- `saida/`: CSVs, JSON e HTML gerados pela analise

## Contexto aprendido
- A base `AKD` representa movimentos orcamentarios.
- A base `CT2` representa lancamentos contabeis.
- Os arquivos Excel nao contem todas as colunas das tabelas Oracle/Protheus, apenas um subconjunto operacional exportado.
- Nao existe uma chave unica `1x1` pronta entre as duas bases.
- `RECNO` e `LOTE` nao devem ser usados como chave direta de uniao entre `AKD` e `CT2`.
- Existem evidencias indiretas importantes de conciliacao:
  - `AKD_XDOC` <-> `CT2_XDOC`
  - `AKD_XNUMAP` <-> `CT2_XDOCUM`
  - `AKD_XDOC` no formato `CT2<recno>` <-> `CT2.R_E_C_N_O_`
  - documentos de `9` digitos em `AKD_CHAVE` <-> `CT2_KEY`
  - documentos embutidos nos historicos e campos auxiliares

## Filtros de origem atualmente ativos
### CT2
- `CT2_MOEDLC = '01'`
- `CT2_DC IN ('1','2')`

### AKD
- `AKD_TPSALD IN ('LQ', 'PG', 'AR', 'RB')`

Esses filtros mudam o tamanho da base efetivamente analisada e precisam sempre ser considerados ao comparar resultados entre rodadas.

## Direcao tecnica atual
Usar estrategia em camadas:
1. Reconciliacao forte por chaves documentais.
2. Reconciliacao por assinatura residual com `competencia + valor`.
3. Reforco por documentos extraidos de historico e campos auxiliares.
4. Reforco por conta, centro de custo, classe de valor e item contabil.
5. Classificacao de confianca do match.
6. Selecao final `1x1` pelo melhor score.

## Evolucao da abordagem para maximizar acertos
- Foi criado um reconciliador linha a linha com `score` auditavel e casamento `1x1` guloso pelo melhor candidato.
- A geracao de candidatos usa blocos controlados para evitar explosao combinatoria.
- A estrategia atual considera:
  - `AKD_XDOC` x `CT2_XDOC`
  - `AKD_XNUMAP` x `CT2_XDOCUM`
  - `AKD_XDOC -> RECNO CT2` quando o valor vem no formato `CT2<numero>`
  - `AKD_CHAVE` x `CT2_KEY` por tokens de `9` digitos
  - `competencia + valor`
  - documentos encontrados em historicos e campos auxiliares
- O score atual combina sinais como:
  - igualdade documental
  - igualdade de AP/Doc APEX
  - evidencia `AKD_XDOC -> RECNO CT2`
  - coincidencia de token de `9` digitos entre chave e key
  - mesma competencia
  - conta equivalente
  - centro de custo equivalente
  - classe de valor equivalente
  - item contabil equivalente
  - similaridade textual e intersecao de tokens do historico

## Resultado medido da versao atual
Totais correntes com os filtros de origem ativos:
- `AKD`: `20.346`
- `CT2`: `27.900`
- `candidatos_gerados`: `234.874`
- `matches_linha_a_linha_selecionados`: `9.889`
- distribuicao:
  - `muito_forte`: `9.332`
  - `forte`: `84`
  - `provavel`: `473`

## Leitura funcional do resultado
- A cobertura atual privilegia rastreabilidade e reducao de falso positivo.
- A maior parte dos matches esta concentrada na faixa `muito_forte`, o que indica melhora de qualidade com as novas ancoras documentais.
- Parte dos registros em `sem match` pode ter indicio real de relacao, mas nao ter sido escolhida na selecao final `1x1` por conflito de candidatos ou falta de evidencias suficientes.
- A regra `AKD_XDOC -> RECNO CT2` elevou fortemente a confianca de muitos matches, mesmo quando nao aumentou tanto o total final em algumas rodadas.

## Entregas atuais do projeto
- reconciliador Python em `scripts/analisar_cruzamento_akd_ct2.py`
- CSV detalhado de matches em `saida/matches_linha_a_linha.csv`
- comparativo para conferencia em `saida/comparativo_conciliacao.csv`
- pendencias em `saida/akd_sem_match.csv` e `saida/ct2_sem_match.csv`
- resumo executivo em `saida/resumo_analise.json`
- relatorio visual em `saida/relatorio_conciliacao.html`

## Estado atual do relatorio HTML
- abas: `Dashboard`, `Matches`, `AKD sem match`, `CT2 sem match`
- filtros de ano, trimestre, confianca e divergencias
- busca livre em qualquer coluna
- ordenacao e redimensionamento de colunas
- expansao das colunas de historico
- dashboard com graficos e insights
- identificacao da versao do cruzador no topo, com data de atualizacao e link para o commit do Git

## Padrao de trabalho combinado
- Preferencia por Python.
- Toda analise relevante deve ficar documentada.
- O projeto deve manter memoria viva para continuidade sem perda de contexto.
- Mudancas relevantes devem atualizar `README.md`, `docs/MEMORIA_CRUZADOR_AKDXCT2.md` e `docs/estrategia_cruzamento.md`.

## Proximos passos naturais
- integrar `GLOSSARIO-CONTAS.xlsx` como filtro e descricao funcional no relatorio
- expor no HTML as evidencias que sustentaram cada match
- criar trilha especifica para conflitos `Nx1`
- evoluir para conciliacao por grupo `1xN` e `NxN`
