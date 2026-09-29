# 04 — Agente de Q&A, ferramentas e estado
Status: em implementação (v0.1) — roteador determinístico pronto e testado; `find_interview_candidates`
e `export_report` implementados (2026-09-29); `sql_query`/`search_reviews` como tools formais do
loop ReAct, `ConversationState` e o loop de 5 passos seguem pendentes · Framework: **loop
explícito** (ADR-003, aceita)

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
| `export_report` | gera CSV | escreve só em `reports/exports/` | **sim** |

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
Implementado em `src/bri/schemas/qa.py` como `RespostaNarrada` (ADR-012):

```python
class RespostaNarrada(BaseModel):
    resposta: str                  # 3 a 5 frases, linguagem de negócio
    citacoes: list[Citacao]        # review_id + trecho, conferidos pelo guardrail
    confianca: Literal["alta", "média", "baixa"]
    proximas_perguntas: list[str]
```

Sem `sql_used`: o SQL é nosso e já viaja em `roteador.Resposta.sql`, que a tela mostra no painel —
pedir ao modelo que o repita gastaria token e convidaria à corrupção do texto.

## UI (FastAPI + Jinja2 + HTMX — ADR-010)
Chat + painel com SQL executado e citações clicáveis + aba de entrevistas com botão de aprovação.
Páginas server-side; HTMX é melhoria progressiva, os formulários funcionam sem JavaScript. As
mesmas consultas são expostas em JSON sob `/api`.

Enquanto a F1/F2 não existem, o chat responde por **roteador determinístico só-SQL** (sem LLM):
desempenho de autor, distribuição por gênero e números gerais. Fora disso, recusa dizendo o que
falta — nunca responde com texto inventado. Telas marcam explicitamente o que depende do
enriquecimento.
