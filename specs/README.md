# Specs — índice e status

O status de cada spec fica **na linha 2 do próprio arquivo**, na escada
`rascunho` → `aprovada` → `em implementação` → `concluída`. Não se repete aqui pelo mesmo motivo
das ADRs: cópia divergia do original a cada avanço. Fonte única, não cópia.

| # | Spec | Cobre itens do case |
|---|---|---|
| 00 | [Visão geral, hipóteses e roadmap](00-overview.md) | a, b, d, i |
| 01 | [Dados e EDA](01-data-eda.md) | e |
| 02 | [Pipeline NLP (batch, offline)](02-nlp-pipeline.md) | e, f |
| 03 | [Bases de conhecimento e RAG](03-rag-knowledge-base.md) | g |
| 04 | [Agente de Q&A, ferramentas e estado](04-qa-agent.md) | h |
| 05 | [Prompts, saídas estruturadas e guardrails](05-prompts-guardrails.md) | h |
| 06 | [Avaliação](06-evals.md) | c, h, i |
| 07 | [Fine-tuning (destilação)](07-fine-tuning.md) | j |
| 08 | [Apresentação e estimativa de impacto](08-presentation-impact.md) | a–j |
| 09 | [Workflow, loops e CI](09-workflow-ci.md) | — |

O conjunto anterior, em português e com numeração diferente, está em
[`_archive/pt/`](_archive/pt/). **Não é normativo** — serve só como histórico.

## ADRs
Todo o registro de decisões vive em [`DECISIONS.md`](DECISIONS.md) — **inclusive o status de cada
uma**. A tabela abaixo é só índice de assuntos: o status também vivia aqui, divergia do original a
cada decisão tomada, e foi removido por isso. Fonte única, não cópia.

| ADR | Assunto |
|---|---|
| 001 | AGENTS.md como fonte única de instruções |
| 002 | DuckDB como camada analítica |
| 003 | Framework do agente (loop explícito vs LangGraph) |
| 004 | Provider de LLM (local vs API comercial) |
| 005 | Vector store (store dedicado vs DuckDB acumulando o papel) |
| 006 | Arquitetura híbrida: SQL para números, RAG para opiniões |
| 007 | Enriquecimento offline em vez de LLM em tempo de consulta |
| 008 | Modelo usado pelos gates de LLM no CI |
| 009 | Formato dos arquivos de prompt (`.yaml` vs `.md`) |
| 010 | FastAPI + Jinja2 + HTMX no lugar de Streamlit |
| 011 | Nenhuma chave de API no projeto |
| 012 | Narração da resposta do chat por LLM local |
| 013 | Guardrail determinístico de números na resposta narrada |
| 014 | RAG semântico sobre a amostra, sem infraestrutura nova |
| 015 | Sentimento sobre a base completa não será construído |
| 016 | Tópicos por k-means sobre os embeddings existentes, não BERTopic |
| 017 | Nota não entra na prosa do chat |
| 018 | `app/` sob `mypy --strict` junto com `src/` |
| 019 | Hook de pre-push para `eval-smoke`, condicional a `prompts/` |
| 020 | Enxugamento: dedup de consultas, taxonomia derivada e ranking determinístico |
| 021 | Modelo e timeout por ambiente, cliente do Ollama sem repetição |
| 022 | Dockerização, com modelo e dados fora da imagem |

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
