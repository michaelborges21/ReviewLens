# 08 — Apresentação e estimativa de impacto
Status: rascunho v0.1

## Narrativa (Situação → Complicação → Resolução)
Começar pela dor do analista, não pela tecnologia. Cada slide técnico responde "e daí para o negócio?".

## Estrutura (mapeada para o enunciado)
| # | Slide | Item |
|---|---|---|
| 1 | O problema e o que muda para a editora | a |
| 2 | Roadmap (feito / próximo / futuro) | b |
| 3 | Processo: dados → enriquecimento → conhecimento → Q&A | c |
| 4 | Hipóteses e veredito de cada uma | d |
| 5–7 | EDA: 3 insights acionáveis (não 20 gráficos) | e |
| 8 | Sumarização: exemplo real de autor/gênero | f |
| 9 | Bases de conhecimento e por que híbrido | g |
| 10 | Demo do Q&A (prints/vídeo) + métricas de qualidade | h |
| 11 | Impacto estimado + premissas | i |
| 12 | Fine-tuning/destilação (se feito) | j |
| 13 | Próximos passos e pedido de decisão ao negócio | — |

## Estimativa de impacto
Fórmula explícita, premissas visíveis, 3 cenários:
```
horas_economizadas/mês = nº_analistas × horas_mês_em_exploração × %_redução
valor = horas_economizadas × custo_hora  − custo_operação_LLM/mês
```
| Cenário | %_redução | Premissa |
|---|---|---|
| Pessimista | 30% | adoção parcial |
| Base | 60% | uso diário |
| Otimista | 80% | substitui leitura manual na triagem |

Impactos qualitativos: decisões de reedição/marketing baseadas em aspectos, recrutamento mais rápido de entrevistados, detecção precoce de problemas (ex.: tradução, qualidade de impressão).
Premissas numéricas são **hipóteses a validar com o negócio** — dizer isso no slide.

## Regra
Todo gráfico/número vem de script em `reports/`. Nada colado à mão.
