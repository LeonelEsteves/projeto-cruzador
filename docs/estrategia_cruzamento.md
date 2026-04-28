# Estrategia de Cruzamento AKD x CT2

## Resumo executivo
A melhor estrategia nao e tentar um `merge` simples linha a linha. A base real mostra que os dados se relacionam em mais de um nivel:
- nivel documental
- nivel de grupo de linhas
- nivel residual por assinatura do lancamento
- nivel indireto por documentos embutidos em historicos e campos tecnicos

Por isso, a conciliacao deve ser feita em camadas e com escore de confianca auditavel.

## Recorte atual da base
O reconciliador trabalha hoje com filtros de origem ativos antes do cruzamento:

### CT2
- `CT2_MOEDLC = '01'`
- `CT2_DC IN ('1','2')`

### AKD
- `AKD_TPSALD IN ('LQ', 'PG', 'AR', 'RB')`

Totais atuais apos filtro:
- `AKD`: `20.346`
- `CT2`: `27.900`

## Colunas exportadas com maior poder de cruzamento

### AKD
- `AKD_XDOC`: DOC chave
- `AKD_XNUMAP`: numero AP
- `AKD_CHAVE`: chave tecnica com possiveis documentos embutidos
- `AKD_IDREF`: referencia auxiliar
- `AKD_DATA`: data do lancamento
- `AKD_VALOR1`: valor do lancamento
- `AKD_HIST`: historico do lancamento
- `AKD_XHISTO`: historico de origem
- `AKD_CLVLR`: classe de valor
- `AKD_ENT05`: referencia de conta
- `AKD_ITCTB`: item contabil

### CT2
- `CT2_XDOC`: DOC chave
- `CT2_XDOCUM`: Doc APEX
- `CT2_KEY`: chave tecnica com possiveis documentos embutidos
- `CT2_XNUMCT`: numero tecnico auxiliar
- `CT2_DOC`: documento auxiliar
- `CT2_DATA`: data do lancamento
- `CT2_VALOR`: valor do lancamento
- `CT2_HIST`: historico do lancamento
- `CT2_DEBITO` e `CT2_CREDIT`: contas contabeis
- `CT2_CCD` e `CT2_CCC`: centros de custo
- `CT2_CLVLDB` e `CT2_CLVLCR`: classes de valor
- `CT2_ITEMD` e `CT2_ITEMC`: itens contabeis

## Leitura funcional do cenario

### Chave 1
`AKD_XDOC` e `CT2_XDOC` sao a melhor ancora documental para eventos ja identificados por DOC chave.

### Chave 2
`AKD_XNUMAP` e `CT2_XDOCUM` sao a melhor ancora para eventos de AP/Doc APEX.

### Chave 3
Quando `AKD_XDOC` esta no formato `CT2<numero>`, o sufixo numerico e tratado como ponte para `CT2.R_E_C_N_O_`.

### Chave 4
`AKD_CHAVE` e `CT2_KEY` podem carregar documentos de `9` digitos, usados como evidencia adicional de conciliacao.

### Restricao importante
Mesmo quando a chave bate, os lados podem ter:
- quantidades diferentes de linhas
- totais diferentes
- desdobramentos contabeis adicionais
- conflito entre varios candidatos para um mesmo registro final

Isso impede conciliacao confiavel apenas com `merge` simples.

## Estrategia recomendada

### Etapa 1
Fazer match direto por `AKD_XDOC = CT2_XDOC`.

Classificacao conceitual:
- `forte_1x1`: uma linha em AKD e uma linha em CT2 com mesmo documento e mesmo valor
- `forte_grupo`: documento comum e soma dos grupos igual
- `ambiguo_documento`: documento comum, mas com varias linhas ou totais divergentes

### Etapa 2
Para linhas nao conciliadas na etapa 1, testar `AKD_XNUMAP = CT2_XDOCUM`.

### Etapa 3
Aplicar a regra `AKD_XDOC -> RECNO CT2` quando o campo vier no formato `CT2<numero>`.

Essa e uma ancora forte porque:
- usa o proprio `RECNO` da CT2 como evidencia indireta
- nao usa `RECNO` como chave primaria de uniao entre bases
- apenas reconhece quando a AKD codificou explicitamente essa referencia

### Etapa 4
Extrair documentos embutidos em historicos e campos auxiliares.

Padroes atualmente considerados:
- `DOC`
- `DOC N`
- `REF DOC`
- `NF`
- `AP`
- `NR`
- prefixos `SE`, `SF`, `AK`, `SEU`, `FFC`, `RFB`
- variacoes com e sem zeros a esquerda

### Etapa 5
Para o residual, montar assinatura de lancamento:
- competencia derivada da data
- valor
- texto normalizado

Essa etapa serve para sugerir candidatos, nao para bater martelo automatico isoladamente.

### Etapa 6
Aplicar `score` de similaridade forte por linha.

Sinais atuais usados no score:
- `valor` igual
- `AKD_XDOC = CT2_XDOC`
- `AKD_XNUMAP = CT2_XDOCUM`
- `AKD_XDOC -> RECNO CT2`
- token de `9` digitos entre `AKD_CHAVE` e `CT2_KEY`
- mesma competencia
- `AKD_ENT05` igual a conta de debito/credito em `CT2`
- centro de custo equivalente
- classe de valor equivalente
- item contabil equivalente
- similaridade textual entre `AKD_XHISTO/AKD_HIST` e `CT2_HIST`
- intersecao de tokens relevantes do historico

### Etapa 7
Selecionar o melhor candidato por linha com casamento `1x1`.

Objetivo:
- aumentar cobertura com rastreabilidade
- evitar duplicidade de conciliacao final
- manter trilha de auditoria do por que do match

## Resultado atual da estrategia
- `234.874` candidatos gerados
- `9.889` matches selecionados
- distribuicao:
  - `muito_forte`: `9.332`
  - `forte`: `84`
  - `provavel`: `473`

## Leitura pratica do estado atual
- A maior parte da massa selecionada esta em `muito_forte`, o que indica boa qualidade de evidencia.
- O total de matches precisa sempre ser lido junto com os filtros de origem ativos.
- Parte dos registros fora do match final pode ter sido encontrada por alguma regra, mas nao selecionada no pareamento `1x1` por conflito com candidato melhor.
- O relatorio HTML hoje apoia a auditoria com dashboard, abas de pendencia e identificacao da versao do cruzador no topo.

## Conclusao pratica
A melhor estrategia hoje e:
1. priorizar documento
2. depois priorizar AP
3. reconhecer ligacao `AKD_XDOC -> RECNO CT2`
4. aproveitar documentos extraidos do historico e campos tecnicos
5. usar assinatura residual por competencia + valor + texto
6. transformar isso em escore auditavel e selecionar o melhor candidato

Esse modelo respeita a natureza do Protheus, reduz falso positivo e permite auditar cada reconciliacao.
