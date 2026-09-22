# Specs — índice e status

Status: `rascunho` → `aprovada` → `em implementação` → `concluída`

| # | Spec | Status | Cobre itens do case |
|---|---|---|---|
| 00 | [Visão geral, hipóteses e roadmap](00-overview.md) | rascunho v0.1 | a, b, d, i |
| 01 | [Dados e EDA](01-data-eda.md) | rascunho v0.1 | e |
| 02 | [Pipeline NLP (batch, offline)](02-nlp-pipeline.md) | rascunho v0.1 | e, f |
| 03 | [Bases de conhecimento e RAG](03-rag-knowledge-base.md) | rascunho v0.1 | g |
| 04 | [Agente de Q&A, ferramentas e estado](04-qa-agent.md) | rascunho v0.1 | h |
| 05 | [Prompts, saídas estruturadas e guardrails](05-prompts-guardrails.md) | rascunho v0.1 | h |
| 06 | [Avaliação](06-evals.md) | rascunho v0.1 | c, h, i |
| 07 | [Fine-tuning (destilação)](07-fine-tuning.md) | backlog | j |
| 08 | [Apresentação e estimativa de impacto](08-presentation-impact.md) | rascunho v0.1 | a–j |
| 09 | [Workflow, loops e CI](09-workflow-ci.md) | rascunho v0.1 | — |

O conjunto anterior, em português e com numeração diferente, está em
[`_archive/pt/`](_archive/pt/). **Não é normativo** — serve só como histórico.

## ADRs
Todo o registro de decisões vive em [`DECISIONS.md`](DECISIONS.md).

| ADR | Assunto | Status |
|---|---|---|
| 001 | AGENTS.md como fonte única de instruções | aceita |
| 002 | DuckDB como camada analítica | aceita |
| 003 | Framework do agente (loop explícito vs LangGraph) | proposta |
| 004 | Provider de LLM (local vs API comercial) | proposta |
| 005 | Vector store (LanceDB vs Qdrant) | proposta |
| 006 | Arquitetura híbrida: SQL para números, RAG para opiniões | proposta |
| 007 | Enriquecimento offline em vez de LLM em tempo de consulta | proposta |
| 008 | Modelo usado pelos gates de LLM no CI | proposta |
| 009 | Formato dos arquivos de prompt (`.yaml` vs `.md`) | proposta |

## Mapa: técnicas de prompt/LLM → onde aparecem
| Técnica | Onde | Intensidade |
|---|---|---|
| System prompt com constraints e escopo | 05, `src/bri/prompts/qa_system` | alta |
| Few-shot (dinâmico) | 02, 05, `src/bri/prompts/extract_review` | alta |
| Anatomia do chat e reforço posicional | 02, 05 | média |
| Saídas estruturadas + parsing | 02, 04, 05 | alta |
| Estado conversacional | 04 | média |
| Grounding com RAG | 03, 04 | alta |
| ReAct / CoT | 04 (roteador + loop), 05 | média |
| Tool calling seguro | 04, 05 | alta |
| Least privilege | 04, 05 (DuckDB read-only, escopo de tools) | média |
| Prompt defensivo e guardrails | 05 | alta (reviews = input não confiável) |
| Human-in-the-loop | 05 (candidatos a entrevista, jobs caros) | pontual |
| Avaliação e regressão de prompt | 06 | alta |
| Destilação p/ fine-tuning | 07 | opcional |
| Loops com verificador determinístico | 09 | alta |
