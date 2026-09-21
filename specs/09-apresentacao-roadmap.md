# Spec 09 — Apresentação e roadmap
Status: rascunho

## Princípios
- Público: time de negócio. Linguagem de decisão, não de arquitetura. Técnica vai para apêndice.
- Estrutura **SCR** (Situação → Complicação → Resolução) e **títulos-conclusão** ("Notas escondem insatisfação: 1 em 5 reviews 4★ critica o final"), não títulos-tema ("Análise de notas").
- Todo número rastreável a script/notebook; figuras de `presentation/figures/`.
- Formato: `.pptx` gerado por `presentation/build_deck.py` (python-pptx) **ou** Google Slides; ~15 slides + apêndice.

## Roteiro (mapeado aos itens a–j)
| # | Slide | Item |
|---|---|---|
| 1 | Título + promessa em 1 frase | a |
| 2 | O problema: horas de leitura manual, cobertura baixa, viés | a |
| 3 | O que entregamos (demo em 1 imagem) | a |
| 4 | Como funciona em 1 diagrama (sem jargão) | c |
| 5 | Hipóteses que testamos | d |
| 6–8 | Achados da EDA (1 insight por slide, com "e daí?") | e |
| 9 | Resumo automático de um autor real (antes: 2h lendo / depois: 30s) | f |
| 10 | Base de conhecimento: números do SQL + vozes dos leitores | g |
| 11 | Q&A ao vivo / prints de 3 perguntas | h |
| 12 | Encontrando leitores para entrevista (com aprovação humana) | h |
| 13 | Quão confiável é? (métricas de eval em linguagem simples) | c |
| 14 | Impacto estimado: cenários + sensibilidade | i |
| 15 | Fine-tuning: mesma qualidade, fração do custo | j |
| 16 | Roadmap + próximos passos e decisões pedidas ao negócio | b |
| A | Apêndice: arquitetura, métricas completas, limitações, riscos | — |

## Roadmap (item b)
| Fase | Horizonte | Entrega | Valor |
|---|---|---|---|
| 0 — MVP (este case) | semanas 1–2 | EDA, enriquecimento em amostra, resumos, Q&A, shortlist com HITL, eval | provar valor |
| 1 — Piloto | mês 1–2 | base completa via modelo destilado, uso por 2–3 analistas, coleta de feedback, teste cronometrado real | medir impacto real |
| 2 — Produto | mês 3–4 | ingestão incremental de novos reviews, alertas de queda de percepção por autor, painel de leitores | decisão proativa |
| 3 — Expansão | mês 5+ | outras fontes (Goodreads, redes), enriquecimento via Wikidata, comparação com concorrentes, multilíngue | vantagem competitiva |

Cada fase com: métrica de sucesso, risco principal e decisão necessária do negócio.

## Limitações a declarar (honestidade gera confiança)
Viés de quem escreve review; dados históricos (verificar período); join por título imperfeito; LLM pode errar nuances — por isso citações e eval.

## Critérios de aceite
- [ ] Um leitor de negócio entende o deck sem narrador.
- [ ] Cada slide de achado tem ação recomendada.
