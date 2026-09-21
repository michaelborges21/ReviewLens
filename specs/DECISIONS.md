# Registro de Decisões (ADR) e log de sessões
Specs são vivas. Esta é a memória do *porquê*.

## Template
```
### ADR-NNN — Título
Data: AAAA-MM-DD · Status: proposta | aceita | substituída por ADR-XXX
Contexto: ...
Decisão: ...
Alternativas descartadas: ...
Consequências: ...
```

### ADR-001 — AGENTS.md como fonte única de instruções
Data: 2026-09-21 · Status: aceita
Contexto: o projeto pode usar diferentes agentes de código.
Decisão: instruções em `AGENTS.md`; `CLAUDE.md` só importa e adiciona o específico do Claude Code.
Consequências: trocar de ferramenta não exige reescrever instruções.

### ADR-002 — DuckDB como camada analítica
Data: 2026-09-21 · Status: aceita
Contexto: perguntas de performance são agregações; RAG é impreciso para isso.
Decisão: DuckDB read-only consultado via tool de SQL validada.
Alternativas: pandas em memória (sem SQL auditável), Postgres (overhead desnecessário).

### ADR-003 — Framework do agente
Status: proposta — loop explícito vs LangGraph. Decidir no início da F2.

### ADR-004 — Provider de LLM
Status: proposta — local (Ollama) para iteração vs API comercial para rodada final. Decidir por eval + custo.

### ADR-005 — Vector store
Status: proposta — LanceDB vs Qdrant.

### ADR-006 — Arquitetura híbrida: SQL para números, RAG para opiniões
Status: proposta
Contexto: as perguntas centrais do cliente ("performance do autor X", "do gênero Y") são
**agregações**. RAG recupera top-k trechos e não consegue calcular média, contagem ou tendência
sobre milhares de reviews — o LLM inventaria ou extrapolaria de 10 exemplos.
Decisão: router classifica a intenção. Números vêm de `run_sql` sobre DuckDB (read-only, views);
opiniões vêm de RAG híbrido com citações; perguntas mistas combinam as duas via loop ReAct curto.
Consequências:
+ números corretos e auditáveis (SQL exibido na UI)
+ custo menor (SQL não gasta token de contexto)
− exige guard de SQL (spec 06) e golden set de SQL (spec 07)
− router vira ponto único de falha → medido no eval

### ADR-007 — Enriquecimento offline em vez de LLM em tempo de consulta
Status: proposta
Contexto: perguntas como "o que mais criticam em thrillers?" exigiriam ler milhares de reviews
por consulta.
Decisão: extrair uma vez, em batch, aspectos/sentimento/temas/especificidade por review (spec 02)
e gravar em tabela. Consultas viram SQL; LLM em tempo real só redige e explica.
Consequências:
+ respostas rápidas, baratas e reprodutíveis; permite estatística de verdade sobre texto
+ cria o dataset que viabiliza a destilação (spec 08)
− custo inicial de batch → mitigado por amostragem estratificada e modelo destilado
− schema de aspectos fixo → categoria `outro` + temas livres clusterizados

## Log de sessão
<!-- AAAA-MM-DD — o que foi feito, decisão tomada, próximo passo -->
- 2026-09-21 — Reorganização do repositório: specs consolidadas em português (bookinsights.zip)
  em `specs/`, conjunto em inglês (bri-specs.zip) arquivado em `specs/_archive/en-draft/`, ADRs
  001/002 do bookinsights incorporados aqui como ADR-006/007 para evitar colisão de numeração.
  Próximo passo: revisar se ADR-003/004/005 (framework do agente, provider de LLM, vector store)
  devem ser decididos antes de iniciar a Fase 2.
