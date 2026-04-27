# Memoria do Projeto Cruzador AKD x CT2

## Objetivo
Construir uma rotina em Python para analisar e reconciliar movimentos da base orcamentaria `AKD` com movimentos da base contabil `CT2`, usando os arquivos Excel disponiveis no projeto.

## Fontes atuais
- `dados/brutos/DADOS-AKD010.xlsx`
- `dados/brutos/DADOS-CT2010.xlsx`
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
- Os arquivos Excel nao contem todas as colunas das tabelas Oracle/Protheus, apenas um subconjunto operacional.
- Nao existe uma chave unica 1:1 pronta entre as duas bases exportadas.
- Existem duas chaves indiretas importantes:
  - `AKD_XDOC` <-> `CT2_XDOC`
  - `AKD_XNUMAP` <-> `CT2_XDOCUM`
- Essas chaves nao garantem granularidade de linha unica. Em muitos casos, um documento representa um grupo de linhas em cada base.

## Evidencias medidas na base atual
- `AKD`: 68.046 linhas.
- `CT2`: 49.413 linhas.
- Sobreposicao de documentos:
  - `AKD_XDOC` x `CT2_XDOC`: 2.573 chaves em comum.
  - `AKD_XNUMAP` x `CT2_XDOCUM`: 1.671 chaves em comum.
- O join direto por documento gera muita ambiguidade por repeticao de linhas dos dois lados.
- Existem casos fortes de reconciliacao por grupo:
  - mesmos documentos
  - mesmas somas por documento
  - mesmas quantidades de linhas em alguns grupos
- Tambem existem muitos casos em que os totais divergem, indicando:
  - granularidade diferente
  - partidas contabeis adicionais
  - descontos, rateios ou lancamentos complementares

## Direcao tecnica atual
Usar estrategia em camadas:
1. Reconciliacao forte por chaves documentais.
2. Reconciliacao por grupos de documento com comparacao de totais.
3. Reconciliacao residual por assinatura de lancamento, usando data, valor e texto.
4. Classificacao de confianca do match.

## Evolucao da abordagem para maximizar acertos
- Foi criado um reconciliador linha a linha com `score` e casamento `1x1` guloso pelo melhor candidato.
- A geracao de candidatos usa blocos controlados para evitar explosao combinatoria:
  - `AKD_XDOC` x `CT2_XDOC`
  - `AKD_XNUMAP` x `CT2_XDOCUM`
  - `competencia + valor`
- O score atual combina:
  - igualdade de valor
  - igualdade de documento
  - igualdade de AP/Doc APEX
- mesma data ou mesma competencia, conforme disponibilidade da CT2
  - coincidencia de `AKD_ENT05` com conta contabil de `CT2`
  - similaridade textual do historico
  - intersecao de tokens relevantes do historico

## Resultado medido da versao atual
- Candidatos gerados: `64.589`
- Matches linha a linha selecionados: `12.700`
- Distribuicao:
  - `muito_forte`: `2.600`
  - `forte`: `9.478`
  - `provavel`: `622`

## Leitura funcional do resultado
- Essa abordagem privilegia alto acerto com rastreabilidade.
- O motor atual e forte para documentos, APs e historicos parecidos com mesmo valor.
- Para ampliar ainda mais a cobertura, os proximos refinamentos devem focar no residual sem derrubar a precisao.

## Padrao de trabalho combinado
- Preferencia por Python.
- Toda analise relevante deve ficar documentada.
- O projeto deve manter memoria viva para continuidade sem perda de contexto.

## Proximos passos naturais
- Gerar relatorio automatizado das chaves candidatas.
- Classificar matches em `forte`, `provavel`, `ambiguo` e `sem match`.
- Evoluir para exportacao de CSVs de conciliacao.
