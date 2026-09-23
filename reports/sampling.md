# Amostragem para o enriquecimento (spec 01 · spec 02)

Gerado por `make sample`. Seed fixa: **42** — a mesma seed reproduz a amostra.

## Composição: amostra vs base

| faixa de nota | base | % base | amostra | % amostra | peso |
|---|---|---|---|---|---|
| baixa(1-2) | 278.393 | 12,4% | 3.826 | 19,2% | 2× |
| media(3) | 190.084 | 8,5% | 3.917 | 19,6% | 3× |
| alta(4-5) | 1.771.521 | 79,1% | 12.206 | 61,2% | 1× |

A distribuição da amostra **não espelha a base, de propósito**. Reviews da faixa média
são as mais argumentadas (mediana de 645 caracteres contra 459 da nota 5 — achado de
H2), logo rendem mais aspecto por chamada paga. Quem extrapolar estatística da amostra
para a base inteira precisa corrigir essa calibragem.

Células na grade (faixa × período × gênero): **90**, das
quais **90** receberam cota. Gêneros fora do top
8 caem em `outros`; reviews de livro sem categoria caem em `sem_genero`,
em vez de sumirem da amostra. As células menores ficam com cotas de poucas dezenas de
reviews: a grade serve para espalhar cobertura, não para sustentar inferência por
célula.

## Custo estimado

> **Câmbio usado: US$ 1,00 = R$ 5,50** (padrão do código, referência de 2026-09-22).
> A Anthropic cobra em dólar; os valores abaixo já estão convertidos. Defina a variável
> de ambiente `USD_BRL` para recalcular com o câmbio do dia.

Base da conta: 791 caracteres médios por review, mais
o gabarito do prompt e 3 exemplos few-shot → **1.784 tokens de
entrada** e 250 de saída por chamada.

> Estimativa por heurística (~4 caracteres por token), margem de 15% a 20%. A contagem
> exata exige o tokenizador do provider, que a ADR-004 ainda não escolheu.

Custo da amostra atual (19.949 reviews):

| modelo | custo |
|---|---|
| haiku-4.5 | R$ 332,89 |
| sonnet-5 | R$ 665,78 |
| opus-5 | R$ 1.664,44 |

### A conta é dominada pelos exemplos, não pelas reviews

Dos 1.784 tokens de entrada por chamada,
**1.341 são os 3 exemplos few-shot**
(75%), 246
são o gabarito do prompt e apenas **197
(11%) são a review a ser analisada**.
Gabarito e exemplos são idênticos em toda chamada, ou seja, prefixo estável de
1.587 tokens — candidato direto a cache de prompt:

| modelo | sem cache | com cache | economia |
|---|---|---|---|
| haiku-4.5 | R$ 332,89 | R$ 176,18 | 47% |
| sonnet-5 | R$ 665,78 | R$ 352,35 | 47% |
| opus-5 | R$ 1.664,44 | R$ 880,88 | 47% |

**Isso reenquadra a ADR-004:** com cache, o Sonnet 5 custa praticamente o mesmo que o
Haiku 4.5 sem cache. A alavanca compra um degrau de modelo pelo mesmo dinheiro, e vale
decidir o cache antes de decidir o provider.

Quantas reviews cabem em cada teto de gasto (sem cache):

| modelo | R$ 100,00 | R$ 250,00 | R$ 500,00 | R$ 1.000,00 |
|---|---|---|---|---|
| haiku-4.5 | 5.992 | 14.981 | 29.963 | 59.926 |
| sonnet-5 | 2.996 | 7.490 | 14.981 | 29.963 |
| opus-5 | 1.198 | 2.996 | 5.992 | 11.985 |

Enriquecer a base inteira está fora de cogitação: são
1.773.128.911 caracteres, da ordem de 440 milhões de tokens só de entrada. A cobertura
total é problema da destilação (spec 07), treinada justamente sobre esta amostra.

`make enrich` continua bloqueado até a ADR-004 ser decidida e este custo, aprovado.
