# Specs — índice e status

Status: `rascunho` → `aprovada` → `em implementação` → `concluída`

| # | Spec | Status | Cobre itens do case |
|---|---|---|---|
| 00 | [Visão, negócio e hipóteses](00-visao-negocio.md) | rascunho | a, d, i |
| 01 | [Dados e EDA](01-dados-eda.md) | rascunho | e |
| 02 | [Enriquecimento estruturado](02-enriquecimento.md) | rascunho | e, f |
| 03 | [Sumarização](03-sumarizacao.md) | rascunho | f |
| 04 | [Base de conhecimento e RAG](04-conhecimento-rag.md) | rascunho | g |
| 05 | [Agente de Q&A](05-agente-qa.md) | rascunho | h |
| 06 | [Segurança, guardrails e HITL](06-seguranca-guardrails.md) | rascunho | h |
| 07 | [Avaliação](07-avaliacao.md) | rascunho | c, h, i |
| 08 | [Fine-tuning (destilação)](08-fine-tuning.md) | rascunho | j |
| 09 | [Apresentação e roadmap](09-apresentacao-roadmap.md) | rascunho | a–j, b |

## ADRs
Todo o registro de decisões vive em [`DECISIONS.md`](DECISIONS.md).
- [ADR-006 — Arquitetura híbrida: SQL para números, RAG para opiniões](DECISIONS.md#adr-006--arquitetura-híbrida-sql-para-números-rag-para-opiniões)
- [ADR-007 — Enriquecimento offline em vez de LLM em tempo de consulta](DECISIONS.md#adr-007--enriquecimento-offline-em-vez-de-llm-em-tempo-de-consulta)

## Mapa: técnicas de prompt/LLM → onde aparecem
| Técnica | Onde | Intensidade |
|---|---|---|
| System prompt com constraints e escopo | 05, src/bri/prompts/qa_system.md | alta |
| Few-shot (dinâmico) | 02, src/bri/prompts/extract_review.md | alta |
| Anatomia do chat e reforço posicional | 03, 05 | média |
| Saídas estruturadas + parsing | 02, 03, 05 | alta |
| Estado conversacional | 05 | média |
| Grounding com RAG | 04, 05 | alta |
| ReAct / CoT | 05 (router + loop) | média |
| Tool calling seguro | 05, 06 | alta |
| Least privilege | 06 (infra: DuckDB read-only) | média |
| Tool permission scoping | 05, 06 (tools por intenção) | média |
| Prompt defensivo e guardrails | 06 | alta (reviews = input não confiável) |
| Human-in-the-loop | 06 (candidatos a entrevista, jobs caros) | pontual |
| **Avaliação (adicionada)** | 07 | alta |
| **Destilação p/ fine-tuning (adicionada)** | 08 | opcional |
