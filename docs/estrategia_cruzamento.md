# Estrategia de Cruzamento AKD x CT2

## Resumo executivo
A melhor estrategia nao e tentar um `merge` simples linha a linha. A base real mostra que os dados se relacionam em mais de um nivel:
- nivel documental
- nivel de grupo de linhas
- nivel residual por assinatura do lancamento

Por isso, a conciliacao deve ser feita em camadas e com escore de confianca.

## Colunas exportadas com maior poder de cruzamento

### AKD
- `AKD_XDOC`: DOC Chave
- `AKD_XNUMAP`: Num AP
- `AKD_DATA`: data do lancamento
- `AKD_VALOR1`: valor do lancamento
- `AKD_HIST`: historico do lancamento
- `AKD_XHISTO`: historico de origem
- `AKD_CLVLR`: classe de valor
- `AKD_ENT05`: entidade 05

### CT2
- `CT2_XDOC`: DOC Chave
- `CT2_XDOCUM`: Doc APEX
- `CT2_VALOR`: valor do lancamento
- `CT2_HIST`: historico do lancamento
- `CT2_DEBITO` e `CT2_CREDIT`: contas contabeis
- `CT2_CCD` e `CT2_CCC`: centros de custo

## Limitacoes do extrato atual
- O Excel atual de `AKD` nao trouxe colunas equivalentes a `debito` e `credito`.
- Na `AKD`, a melhor referencia de conta que veio no extrato atual e `AKD_ENT05`.
- Por isso, no comparativo gerado:
  - `akd_data` vem da `AKD`
  - `ct2_data` vem agora da propria `CT2`
  - `ct2_debito` e `ct2_credito` vem da `CT2`
  - `akd_conta_referencia` usa `AKD_ENT05`

## Leitura funcional do cenario

### Chave 1
`AKD_XDOC` e `CT2_XDOC` sao a melhor ancora documental para eventos ja identificados por DOC Chave.

### Chave 2
`AKD_XNUMAP` e `CT2_XDOCUM` sao a melhor ancora para eventos de AP/Doc APEX.

### Restricao importante
Mesmo quando a chave bate, os lados podem ter:
- quantidades diferentes de linhas
- totais diferentes
- desdobramentos contabeis adicionais

Isso impede conciliacao confiavel apenas com `merge` simples.

## Estrategia recomendada

### Etapa 1
Fazer match direto por `AKD_XDOC = CT2_XDOC`.

Classificacao sugerida:
- `forte_1x1`: uma linha em AKD e uma linha em CT2 com mesmo documento e mesmo valor
- `forte_grupo`: documento comum e soma dos grupos igual
- `ambiguo_documento`: documento comum, mas com varias linhas ou totais divergentes

### Etapa 2
Para linhas nao conciliadas na etapa 1, testar `AKD_XNUMAP = CT2_XDOCUM`.

Classificacao sugerida:
- `forte_ap_1x1`
- `forte_ap_grupo`
- `ambiguo_ap`

### Etapa 3
Para o residual, montar assinatura de lancamento:
- competencia derivada da data/historico
- valor
- texto normalizado

Exemplo de assinatura residual:
- `competencia`
- `valor`
- tokens relevantes do historico

Essa etapa deve servir para sugerir candidatos, nao para bater martelo automatico.

### Etapa 4
Aplicar `score` de similaridade forte por linha.

Sinais atuais usados no score:
- `valor` igual
- `AKD_XDOC = CT2_XDOC`
- `AKD_XNUMAP = CT2_XDOCUM`
- mesma data da AKD e CT2
- `AKD_ENT05` igual a conta de debito/credito em `CT2`
- similaridade textual entre `AKD_XHISTO/AKD_HIST` e `CT2_HIST`
- intersecao de tokens relevantes do historico

### Etapa 5
Selecionar o melhor candidato por linha com casamento `1x1`.

Objetivo:
- aumentar cobertura
- evitar duplicidade de conciliacao
- manter trilha de auditoria do por que do match

## Resultado atual da estrategia
- `64.589` candidatos gerados
- `12.700` matches selecionados
- `12.078` matches em nivel `forte` ou `muito_forte`

## Conclusao pratica
A melhor estrategia hoje e:
1. priorizar documento
2. depois priorizar AP
3. por fim usar assinatura de valor + competencia + texto
4. transformar isso em escore auditavel e selecionar o melhor candidato

Esse modelo respeita a natureza do Protheus, reduz falso positivo e permite auditar cada reconciliacao.
