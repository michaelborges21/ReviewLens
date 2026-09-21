# 04 — Agente de Q&A, ferramentas e estado
Status: rascunho v0.1 · Framework: ADR-003 (pendente — preferir loop explícito simples; LangGraph se o estado crescer)

## Arquitetura
```
pergunta → [guardrail de entrada] → Roteador (classificação estruturada)
   ├─ analítica      → sql_query
   ├─ semântica      → search_reviews (+ get_summary)
   ├─ visão geral    → get_summary
   ├─ entrevistas    → find_interview_candidates → HITL
   ├─ mista          → loop ReAct (máx. 5 passos)
   └─ fora de escopo → recusa educada
→ [guardrail de saída + validação de citações] → resposta estruturada
```
Roteamento determinístico primeiro; ReAct só quando a pergunta combina fontes. Menos passos = menos custo e menos erro.

## Ferramentas (escopo de permissão)
| Tool | Faz | Limites | Confirmação humana |
|---|---|---|---|
| `sql_query` | SELECT no DuckDB | conexão read-only; só tabelas da allowlist; AST validada (sqlglot); LIMIT forçado; timeout | não |
| `search_reviews` | busca híbrida | k ≤ 50; filtros tipados | não |
| `get_summary` | lê `entity_summaries` | só leitura | não |
| `find_interview_candidates` | ranking de usuários | retorna IDs pseudonimizados + justificativa | **sim** para revelar/exportar |
| `export_report` | gera CSV/MD | escreve só em `reports/exports/` | **sim** |

Nenhuma tool tem shell, rede arbitrária ou escrita fora do diretório permitido.

## Ranking de candidatos a entrevista
Score explicável: helpfulness (bayesiano), profundidade (comprimento, nº de aspectos), diversidade de opinião (incluir críticos, não só fãs), atividade no gênero-alvo, recência. Pesos configuráveis e mostrados na UI.

## Estado conversacional
Estado tipado (pydantic), não só histórico bruto:
```python
class ConversationState(BaseModel):
    active_filters: Filters        # autor, gênero, período herdados entre turnos
    last_entities: list[EntityRef] # resolve "e o segundo livro dele?"
    history_summary: str           # resumo compacto de turnos antigos
    recent_turns: list[Turn]       # últimos N turnos literais
    pending_confirmation: Action | None
```
Filtros herdados sempre visíveis na UI e removíveis pelo usuário.

## Saída
```python
class Answer(BaseModel):
    answer: str
    citations: list[Citation]      # review_id + trecho
    sql_used: str | None           # transparência para o analista
    confidence: Literal["alta", "média", "baixa"]
    follow_ups: list[str]          # sugestões de próximas perguntas
```

## UI (Streamlit)
Chat + painel lateral (filtros ativos, SQL executado, citações clicáveis) + aba de entrevistas com botão de aprovação.
