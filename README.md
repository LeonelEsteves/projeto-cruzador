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
- `docs/MEMORIA_CRUZADOR_AKDXCT2.md`
- `docs/estrategia_cruzamento.md`
- `saida/relatorio_conciliacao.html`
- `saida/resumo_analise.json`

## Entradas

Arquivos esperados em `dados/brutos/`:
- `DADOS-AKD010.xlsx`
- `DADOS-CT2010.xlsx`
- `GLOSSARIO-CONTAS.xlsx`

Arquivos de referencia em `dados/referencia/`:
- `DDL-AKD.txt`
- `DDL-CT2.txt`
- `DICIONARIO.xlsx`

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
2. `AKD_XNUMAP = CT2_XDOCUM`
3. `AKD_XDOC` no formato `CT2<recno>` apontando para `CT2.R_E_C_N_O_`
4. `AKD_CHAVE` x `CT2_KEY` por tokens de `9` digitos
5. `competencia + valor`
6. `documentos extraidos de historico e campos auxiliares`

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

## Reforcos De Score

O score do match pode ser reforcado por:
- documento igual
- numero AP igual
- ligacao `AKD_XDOC -> RECNO CT2`
- token de `9` digitos entre `AKD_CHAVE` e `CT2_KEY`
- mesma competencia
- mesma conta
- mesmo centro de custo
- mesma classe de valor
- mesmo item contabil
- tokens em comum no historico
- similaridade textual do historico

## Saidas

Arquivos gerados em `saida/`:
- `matches_linha_a_linha.csv`
- `comparativo_conciliacao.csv`
- `resumo_analise.json`
- `overlap_xdoc.csv`
- `overlap_xnumap.csv`
- `akd_sem_match.csv`
- `ct2_sem_match.csv`
- `relatorio_conciliacao.html`

## Relatorio HTML

O arquivo `saida/relatorio_conciliacao.html` possui:
- aba `Dashboard`
- aba `Matches`
- aba `AKD sem match`
- aba `CT2 sem match`
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

Para abrir o relatorio:

```powershell
start .\saida\relatorio_conciliacao.html
```

## Estado Atual

Totais da rodada atual, conforme `saida/resumo_analise.json`:
- `AKD`: `20.346`
- `CT2`: `27.900`
- `candidatos_gerados`: `234.874`
- `matches_selecionados`: `9.889`
- `muito_forte`: `9.332`
- `forte`: `84`
- `provavel`: `473`

Na versao atual, o projeto ja contempla:
- cruzamento documental
- cruzamento por valor e competencia
- extracao avancada de documentos
- ligacao entre `AKD_XDOC` e `RECNO` da `CT2`
- cruzamento por tokens de `9` digitos entre `AKD_CHAVE` e `CT2_KEY`
- painel visual com dashboard e trilhas de pendencia
- identificacao visual da versao do cruzador no HTML

## Observacoes Importantes

- `RECNO` e `LOTE` nao sao usados como chave direta de conciliacao entre `AKD` e `CT2`
- o `RECNO` da `CT2` pode ser usado como evidencia indireta quando codificado em `AKD_XDOC`
- um registro aparecer em trilha de `sem match` nao significa necessariamente ausencia total de indicio, e sim que ele nao foi escolhido no pareamento final `1x1`
- a base atual esta sendo trabalhada com recorte filtrado, entao os totais nao devem ser comparados com rodadas antigas sem considerar os filtros de origem

## Proximos Passos Sugeridos

- integrar `GLOSSARIO-CONTAS.xlsx` como filtro e descricao no relatorio
- mostrar no HTML quais evidencias sustentaram cada match
- criar trilha especifica para conflitos `Nx1`
- evoluir reconciliacao por grupo `1xN` e `NxN`
