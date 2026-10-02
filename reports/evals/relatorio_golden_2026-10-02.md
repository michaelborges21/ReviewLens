# Gabarito de aspectos vs extração da IA

- gabarito: `reports/evals/golden_aspectos_anotado_claude.csv`
- predição: tabela `review_enriched` do DuckDB
- linhas comparadas: **200**
- gerado em 2026-10-02

## 1. Visão geral (todas as linhas)

- conjunto idêntico: **68/200** (34.0%)
- detecção: micro P 0.808 / R 0.818 / **F1 0.813** | macro F1 0.758
- par estrito: micro P 0.727 / R 0.736 / **F1 0.732** | macro F1 0.705

> Estes números somam as duas metades do golden e **não** estimam o corpus: metade foi
> escolhida onde a IA já dizia `ritmo`. Use a seção 2.

## 2. Metade aleatória vs metade dirigida

| metade | n | P | R | F1 | conjunto idêntico |
|---|---|---|---|---|---|
| aleatória (estima o corpus) | 100 | 0.762 | 0.782 | **0.772** | 39/100 |
| dirigida a `ritmo` (enviesada) | 100 | 0.838 | 0.841 | 0.840 | 29/100 |

### Detecção por aspecto — só a metade aleatória

| aspecto | suporte | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|
| enredo | 96 | 75 | 0 | 21 | 1.000 | 0.781 | 0.877 |
| personagens | 16 | 16 | 10 | 0 | 0.615 | 1.000 | 0.762 |
| ritmo | 6 | 0 | 0 | 6 | 0.000 | 0.000 | 0.000 |
| final | 6 | 4 | 2 | 2 | 0.667 | 0.667 | 0.667 |
| escrita | 35 | 31 | 20 | 4 | 0.608 | 0.886 | 0.721 |
| edição_física | 14 | 10 | 1 | 4 | 0.909 | 0.714 | 0.800 |
| preço | 5 | 5 | 1 | 0 | 0.833 | 1.000 | 0.909 |
| outro | 10 | 6 | 12 | 4 | 0.333 | 0.600 | 0.429 |

Um aspecto com recall 0 aqui e recall alto na seção 1 é subdetectado de verdade: o número
bom vem da metade que foi selecionada pela própria resposta da IA.

## 3. Sentimento (só aspectos que os dois detectaram)

n = 391 | accuracy **0.900** | kappa de Cohen **0.809**

| gabarito \ predito | positivo | negativo | neutro | misto | total |
|---|---|---|---|---|---|
| **positivo** | 222 | 0 | 0 | 1 | 223 |
| **negativo** | 3 | 126 | 1 | 2 | 132 |
| **neutro** | 0 | 0 | 0 | 0 | 0 |
| **misto** | 19 | 13 | 0 | 4 | 36 |

- casos em que o gabarito disse `misto`: **36**, acerto **11.1%**
- casos não-`misto`: 355, acerto **98.0%**

> O eixo de sentimento só é fraco onde o gabarito pede `misto`. Fora disso a
> concordância é alta — o defeito é o modelo colapsar ambivalência em positivo ou
> negativo, não errar polaridade.

## 4. Anomalias na extração (independem do gabarito)

- linhas em que a IA repetiu o mesmo aspecto: **21/200** (10.5%)
- linhas em que a IA não extraiu aspecto nenhum: **4**

| review_id | repetido | extração completa |
|---|---|---|
| 2448260 | `escrita`×2 | enredo/positivo ; escrita/misto ; ritmo/negativo |
| 265455 | `escrita`×2 | escrita/positivo ; personagens/positivo ; ritmo/positivo |
| 720468 | `enredo`×2 | enredo/negativo ; escrita/positivo ; ritmo/negativo |
| 2405963 | `escrita`×2 | enredo/positivo ; escrita/positivo ; ritmo/positivo |
| 1064687 | `personagens`×2 | personagens/misto ; ritmo/positivo |

Aspecto repetido com sentimentos opostos é ambivalência escrita como duas linhas —
exatamente o caso que o rótulo `misto` existe para cobrir.

## 5. Diagnóstico do gabarito

Se o gabarito usa um rótulo muito acima da taxa da IA no corpus inteiro, ele pode estar
servindo de curinga — e aí o F1 daquela categoria mede critério divergente, não erro.

| aspecto | linhas no gabarito | % gabarito | % corpus (IA) | diferença |
|---|---|---|---|---|
| enredo | 181 | 90.5% | 66.3% | +24.2 pp |
| personagens | 51 | 25.5% | 32.2% | -6.7 pp |
| ritmo | 97 | 48.5% | 17.7% | +30.8 pp |
| final | 21 | 10.5% | 7.0% | +3.5 pp |
| escrita | 88 | 44.0% | 60.8% | -16.8 pp |
| tradução | 0 | 0.0% | 1.2% | -1.2 pp |
| edição_física | 17 | 8.5% | 6.6% | +1.9 pp |
| preço | 8 | 4.0% | 4.9% | -0.9 pp |
| outro | 15 | 7.5% | 18.3% | -10.8 pp |

## 6. Confusões mais comuns (gabarito perdeu → IA pôs no lugar)

| gabarito | IA | n |
|---|---|---|
| enredo | escrita | 15 |
| enredo | personagens | 9 |
| enredo | outro | 6 |
| outro | escrita | 5 |
| escrita | personagens | 4 |
| ritmo | escrita | 4 |
| enredo | final | 3 |
| enredo | ritmo | 3 |

## 7. Rótulos do gabarito fora do schema

Nenhum: todos os rótulos caem nas 9 categorias e nos 4 sentimentos.

## 8. Material para adjudicação humana

As **132** linhas em que gabarito e IA divergem estão em `reports/evals/discordancias_2026-10-02.csv`, com o
texto da avaliação ao lado das duas propostas. Adjudicar (escolher entre duas opções) é
bem mais rápido que rotular em branco — caminho mais curto para um gabarito confiável.
