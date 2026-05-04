# Insights de Chaves Candidatas AKD x CT2

## Escopo

- AKD analisado: `2125` linhas.
- CT2 analisado: `650` linhas.
- Candidatos simples encontrados: `59`.
- Candidatos compostos encontrados: `417`.
- Candidatos documentais/tokenizados encontrados: `5`.

## Melhores Chaves Simples

| Rank | AKD | CT2 | Tipo | Cobertura AKD | Cobertura CT2 | 1x1 | Score | Leitura |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `AKD_XNUMAP` | `CT2_AT04DB` | coluna_simples | 32.97% | 99.26% | 0.00% | 23.29 | forte para bloqueio seletivo |
| 2 | `AKD_XNUMAP` | `CT2_XDOCUM` | coluna_simples | 32.97% | 99.26% | 0.00% | 23.29 | forte para bloqueio seletivo |
| 3 | `AKD_DATA` | `CT2_DATA` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.45 | boa ancora de bloqueio |
| 4 | `AKD_DATA` | `CT2_DTCV3` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.45 | boa ancora de bloqueio |
| 5 | `AKD_DATA` | `DER_DATA` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.45 | boa ancora de bloqueio |
| 6 | `DER_DATA` | `CT2_DATA` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.45 | boa ancora de bloqueio |
| 7 | `DER_DATA` | `CT2_DTCV3` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.45 | boa ancora de bloqueio |
| 8 | `DER_DATA` | `DER_DATA` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.45 | boa ancora de bloqueio |
| 9 | `DER_MES` | `DER_MES` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.04 | boa ancora de bloqueio |
| 10 | `AKD_FILORI` | `CT2_FILIAL` | coluna_simples | 100.00% | 100.00% | 0.00% | 20.01 | boa ancora de bloqueio |

## Melhores Chaves Compostas

| Rank | AKD | CT2 | Tipo | Cobertura AKD | Cobertura CT2 | 1x1 | Score | Leitura |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `AKD_XNUMAP+AKD_ENT05` | `CT2_AT04DB+CT2_DEBITO` | chave_composta | 21.73% | 92.86% | 46.09% | 55.56 | forte para bloqueio seletivo |
| 2 | `AKD_XNUMAP+AKD_ENT05` | `CT2_XDOCUM+CT2_DEBITO` | chave_composta | 21.73% | 92.86% | 46.09% | 55.56 | forte para bloqueio seletivo |
| 3 | `AKD_XNUMAP+AKD_CLVLR` | `CT2_AT04DB+CT2_CLVLDB` | chave_composta | 18.38% | 88.00% | 63.49% | 47.55 | forte para bloqueio seletivo |
| 4 | `AKD_XNUMAP+AKD_CLVLR` | `CT2_XDOCUM+CT2_CLVLDB` | chave_composta | 18.38% | 88.00% | 63.49% | 47.55 | forte para bloqueio seletivo |
| 5 | `AKD_XNUMAP+DER_VALOR` | `CT2_AT04DB+DER_VALOR` | chave_composta | 22.84% | 84.56% | 15.83% | 41.94 | forte para bloqueio seletivo |
| 6 | `AKD_XNUMAP+DER_VALOR` | `CT2_XDOCUM+DER_VALOR` | chave_composta | 22.84% | 84.56% | 15.83% | 41.94 | forte para bloqueio seletivo |
| 7 | `AKD_CLVLR+DER_VALOR` | `CT2_CLVLDB+DER_VALOR` | chave_composta | 7.75% | 74.29% | 70.41% | 36.78 | forte para bloqueio seletivo |
| 8 | `AKD_XNUMAP+AKD_ITEM` | `CT2_AT04DB+CT2_MOEDLC` | chave_composta | 26.70% | 99.26% | 0.00% | 32.34 | forte para bloqueio seletivo |
| 9 | `AKD_XNUMAP+AKD_ITEM` | `CT2_AT04DB+CT2_EMPORI` | chave_composta | 26.70% | 99.26% | 0.00% | 32.34 | forte para bloqueio seletivo |
| 10 | `AKD_XNUMAP+AKD_ITEM` | `CT2_XDOCUM+CT2_MOEDLC` | chave_composta | 26.70% | 99.26% | 0.00% | 32.34 | forte para bloqueio seletivo |

## Melhores Sinais Documentais

| Rank | AKD | CT2 | Tipo | Cobertura AKD | Cobertura CT2 | 1x1 | Score | Leitura |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `AKD_XNUMAP` | `CT2_XDOCUM` | token_documental | 32.97% | 99.26% | 0.00% | 23.29 | forte para bloqueio seletivo |
| 2 | `AKD_XDOC` | `CT2_XDOC` | token_documental | 7.25% | 20.77% | 0.00% | 9.67 | indicio util, mas com muita ambiguidade |
| 3 | `AKD_XDOC` | `CT2_AT01CR` | token_documental | 7.25% | 20.77% | 0.00% | 9.67 | indicio util, mas com muita ambiguidade |
| 4 | `DER_HIST_DOCS` | `DER_HIST_DOCS` | token_documental | 18.85% | 61.35% | 0.00% | -0.91 | boa ancora de bloqueio |
| 5 | `DER_CHAVE_TOKENS` | `DER_CHAVE_TOKENS` | token_documental | 8.75% | 31.26% | 0.00% | -12.42 | indicio util, mas com muita ambiguidade |

## Recomendacoes

- Priorizar a chave composta `AKD_XNUMAP+AKD_ENT05` x `CT2_AT04DB+CT2_DEBITO` como candidata de bloqueio/relacionamento.
- Usar `AKD_XNUMAP` x `CT2_AT04DB` como melhor sinal simples inicial.
- Usar `AKD_XNUMAP` x `CT2_XDOCUM` como trilha documental complementar.
- Campos com boa cobertura, mas baixa taxa 1x1, devem entrar como bloqueio ou reforco de score, nao como chave unica.

## Leitura dos Indicadores

- `Cobertura AKD` e `Cobertura CT2` mostram quanto dos valores preenchidos de cada lado encontra correspondencia no outro lado.
- `1x1` mede quantos valores sobrepostos aparecem uma unica vez em cada base, indicando menor ambiguidade.
- `Score` combina cobertura, sobreposicao distinta, taxa 1x1, especificidade/cardinalidade e penalizacao por valores muito repetidos.
- Uma chave candidata boa para relacionamento final costuma ter cobertura relevante e alta taxa `1x1`.
- Uma chave com cobertura alta e `1x1` baixo ainda pode ser excelente para reduzir o universo de busca antes de aplicar valor, data e similaridade textual.
