# Relatorio de discordancia - aspectos e sentimentos

- golden: `/mnt/user-data/outputs/golden_aspectos_anotado.csv`
- predicoes: `pred_demo.csv`
- linhas comparadas: **200**
- linhas com conjunto identico: **86/200** (43.0%)

## 1. Deteccao de aspecto (sentimento ignorado)

micro P **0.918** / R **0.870** / F1 **0.894** | macro F1 **0.800** | TP 416 FP 37 FN 62

| aspecto | suporte | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|
| enredo | 181 | 163 | 2 | 18 | 0.988 | 0.901 | 0.942 |
| personagens | 51 | 42 | 6 | 9 | 0.875 | 0.824 | 0.848 |
| ritmo | 97 | 83 | 4 | 14 | 0.954 | 0.856 | 0.902 |
| final | 21 | 19 | 7 | 2 | 0.731 | 0.905 | 0.809 |
| escrita | 88 | 83 | 4 | 5 | 0.954 | 0.943 | 0.949 |
| edição_física | 17 | 7 | 4 | 10 | 0.636 | 0.412 | 0.500 |
| preço | 8 | 7 | 5 | 1 | 0.583 | 0.875 | 0.700 |
| outro | 15 | 12 | 5 | 3 | 0.706 | 0.800 | 0.750 |

## 2. Par estrito (aspecto + sentimento)

micro P **0.830** / R **0.787** / F1 **0.808** | macro F1 **0.741** | TP 376 FP 77 FN 102

| aspecto | suporte | P | R | F1 | acertos perdidos p/ sentimento |
|---|---|---|---|---|---|
| enredo | 181 | 0.836 | 0.762 | 0.798 | 25 |
| personagens | 51 | 0.771 | 0.725 | 0.747 | 5 |
| ritmo | 97 | 0.908 | 0.814 | 0.859 | 4 |
| final | 21 | 0.731 | 0.905 | 0.809 | 0 |
| escrita | 88 | 0.908 | 0.898 | 0.903 | 4 |
| edição_física | 17 | 0.545 | 0.353 | 0.429 | 1 |
| preço | 8 | 0.583 | 0.875 | 0.700 | 0 |
| outro | 15 | 0.647 | 0.733 | 0.688 | 1 |

## 3. Sentimento condicional (so aspectos co-detectados)

n = 416 | accuracy **0.904** | kappa de Cohen **0.825**

| golden \ predito | positivo | negativo | neutro | misto | total |
|---|---|---|---|---|---|
| **positivo** (golden) | 231 | 9 | 0 | 0 | 240 |
| **negativo** (golden) | 7 | 134 | 1 | 0 | 142 |
| **neutro** (golden) | 0 | 0 | 0 | 0 | 0 |
| **misto** (golden) | 0 | 0 | 23 | 11 | 34 |

Trocas de sentimento mais frequentes: `misto`->`neutro` (23x), `positivo`->`negativo` (9x), `negativo`->`positivo` (7x), `negativo`->`neutro` (1x)

## 4. Cardinalidade

media de aspectos por linha - golden **2.39**, predito **2.27** (modelo sub-anota)

| n aspectos | linhas golden | linhas preditas |
|---|---|---|
| 0 | 0 | 4 |
| 1 | 37 | 35 |
| 2 | 77 | 90 |
| 3 | 57 | 46 |
| 4 | 29 | 25 |

## 5. Taxonomia dos erros

| tipo | linhas | % das discordancias |
|---|---|---|
| aspecto_nao_detectado | 40 | 35.1% |
| sentimento_divergente | 32 | 28.1% |
| aspecto_alucinado | 21 | 18.4% |
| aspecto_nao_detectado+aspecto_alucinado | 14 | 12.3% |
| aspecto_nao_detectado+sentimento_divergente | 5 | 4.4% |
| aspecto_alucinado+sentimento_divergente | 2 | 1.8% |

Confusoes de aspecto mais comuns (golden perdeu -> modelo pos no lugar):
| golden | predito | n |
|---|---|---|
| ritmo | final | 2 |
| edição_física | enredo | 2 |
| escrita | final | 1 |
| enredo | final | 1 |
| ritmo | preço | 1 |
| escrita | preço | 1 |
| edição_física | escrita | 1 |
| personagens | outro | 1 |

8 linha(s) com anomalia estrutural (ver `anomalias.csv`).

---
Dump linha a linha: `discordancias.csv` (114 linhas).