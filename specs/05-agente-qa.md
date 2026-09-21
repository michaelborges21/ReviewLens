# Spec 05 — Agente de Q&A
Status: rascunho · Ver ADR-001 e spec 06

## Arquitetura
```
pergunta ─► guardrail de entrada ─► ROUTER (intenção + entidades + filtros)
                                      │
      ┌───────────────┬───────────────┼────────────────┬─────────────────┐
  analytics        opinião         resumo          candidatos        fora de escopo
  (SQL tool)     (RAG tool)    (summary tool)   (ranking + HITL)    (recusa educada)
      └───────────────┴──── loop ReAct (máx. 4 passos) ───┘
                                      │
                    guardrail de saída (schema, citações, PII) ─► resposta
```

## Router
Saída estruturada:
```python
class Route(BaseModel):
    intent: Literal["analytics","opinion","summary","interview_candidates","mixed","out_of_scope"]
    entities: list[Entity]   # autor/livro/gênero resolvidos contra o catálogo (fuzzy match)
    filters: Filters         # período, nota, idioma
    needs_clarification: str | None
```
Entidade ambígua ("Stephen" → vários autores) → pergunta de esclarecimento, não chute.

## Tools (escopo por intenção — *tool permission scoping*)
| Tool | Faz | Liberada para intenções |
|---|---|---|
| `run_sql(query)` | SELECT read-only em views permitidas | analytics, mixed |
| `search_reviews(query, filters, k)` | RAG híbrido | opinion, mixed |
| `get_summary(entity)` | sumário pré-computado (ou gera) | summary, mixed |
| `rank_interview_candidates(topic, filters)` | shortlist mascarada | interview_candidates |
| `resolve_entity(name)` | fuzzy match no catálogo | todas |

O loop só recebe o subconjunto de tools da intenção roteada. Motivo: menos tools = menos erro de escolha + menor superfície de abuso.

## Raciocínio (ReAct / CoT)
- ReAct no loop: pensar → chamar tool → observar → repetir, **máx. 4 passos**, depois responde com o que tem.
- Perguntas `mixed` ("autor X caiu de nota? por quê?") = caso de ReAct: SQL mostra a queda, RAG explica.
- CoT fica **interno**. Ao usuário: `rationale` curto + evidências. Com modelos de raciocínio nativo, não forçar "pense passo a passo".

## Estado conversacional
Estado explícito, não histórico cru:
```python
class ConversationState(BaseModel):
    active_entities: list[Entity]
    active_filters: Filters
    last_intent: str | None
    turn_summaries: list[str] = Field(max_length=6)  # janela resumida
```
- Resolve anáfora: "e os livros *dele* depois de 2010?" → herda `active_entities`, sobrescreve filtro.
- Histórico enviado ao LLM = últimas 2 trocas literais + `turn_summaries`. Controla custo e evita deriva.
- Botão "nova análise" zera estado.

## Resposta
```python
class QAAnswer(BaseModel):
    answer: str
    numbers: list[Metric]        # cada uma com a SQL que a gerou (auditável)
    citations: list[str]         # review_ids
    rationale: str = Field(max_length=300)
    confidence: Literal["alta","media","baixa"]
    follow_ups: list[str] = Field(max_length=3)   # "ser propositivo"
```
UI mostra SQL e reviews citados em expansores → transparência para o analista.

## System prompt
Ver `prompts/qa_system.md` (constraints explícitas, escopo, formato, recusa).

## Critérios de aceite
- [ ] Router ≥ 90% de acurácia de intenção no golden set.
- [ ] Execution accuracy do SQL ≥ 85% nas perguntas analíticas.
- [ ] 0 número na resposta sem `Metric` associada.
