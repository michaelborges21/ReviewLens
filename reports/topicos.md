# Escolha de k para os tópicos (spec 02, etapa 4 · ADR-016)

k-means esférico sobre os embeddings de `review_chunks`, seed 42, silhueta de cosseno em subamostra fixa de 3000.

| k | coesão | silhueta | menor cluster | maior cluster | iterações |
|---|---|---|---|---|---|
| 8 | 0.5810 | +0.0270 | 1783 | 3765 | 62 |
| 12 | 0.5906 | +0.0247 | 1220 | 2460 | 100 |
| 16 | 0.5974 | +0.0242 | 393 | 2048 | 60 |
| 20 | 0.6021 | +0.0247 | 382 | 1949 | 53 |
| 24 | 0.6065 | +0.0212 | 371 | 1808 | 60 |
| 30 | 0.6113 | +0.0224 | 328 | 1583 | 84 |
| 40 | 0.6174 | +0.0171 | 83 | 1149 | 60 |
| 60 | 0.6262 | +0.0199 | 72 | 713 | 61 |

**Como ler.** A coesão sobe monotonicamente com k — é assim que ela se comporta sempre, então sozinha não escolhe nada. O que decide é a silhueta, e ela fica na casa de 0,02 em todo o intervalo: as avaliações **não formam agrupamentos disjuntos** neste espaço. Isso é propriedade do dado, não defeito do método, e é a razão de a saída se chamar *tema exploratório* em vez de *o tópico da review*.

`K_PADRAO = 20`: silhueta em platô, menor cluster acima de algumas centenas (abaixo disso o rótulo sai de amostra rala) e um número de temas que um humano revisa numa sentada — a spec 02 exige revisão humana dos rótulos.
