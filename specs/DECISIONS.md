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
Decisão: router classifica a intenção. Números vêm de `sql_query` sobre DuckDB (read-only, views);
opiniões vêm de RAG híbrido com citações; perguntas mistas combinam as duas via loop ReAct curto.
Consequências:
+ números corretos e auditáveis (SQL exibido na UI)
+ custo menor (SQL não gasta token de contexto)
− exige guard de SQL (spec 05) e golden set de SQL (spec 06)
− router vira ponto único de falha → medido no eval

### ADR-007 — Enriquecimento offline em vez de LLM em tempo de consulta
Status: proposta
Contexto: perguntas como "o que mais criticam em thrillers?" exigiriam ler milhares de reviews
por consulta.
Decisão: extrair uma vez, em batch, aspectos/sentimento/temas/especificidade por review (spec 02)
e gravar em tabela. Consultas viram SQL; LLM em tempo real só redige e explica.
Consequências:
+ respostas rápidas, baratas e reprodutíveis; permite estatística de verdade sobre texto
+ cria o dataset que viabiliza a destilação (spec 07)
− custo inicial de batch → mitigado por amostragem estratificada e modelo destilado
− schema de aspectos fixo → categoria `outro` + temas livres clusterizados

### ADR-008 — Modelo usado pelos gates de LLM no CI
Data: 2026-09-22 · Status: **proposta — decisão pendente**
Contexto: `specs/09-workflow-ci.md` diz que o job `llm-gates` roda "com LLM local ou modelo
barato". O `.github/workflows/ci.yml` injeta `ANTHROPIC_API_KEY`, ou seja, modelo comercial.
Runner do GitHub não roda Ollama de forma prática (sem GPU, minutos de cold start por job), então
"LLM local no CI" não é executável como escrito.
Opções:
  (a) spec cede — modelo comercial barato no CI; local fica só para iteração de prompt em dev;
  (b) CI cede — `eval-smoke`/red-team saem do CI e viram gate manual antes do merge;
  (c) híbrido — red-team (30 casos, crítico) no CI comercial; `eval-smoke` completo só local.
Pendente também: o CI roda `llm-gates` em toda PR, enquanto a spec 09 restringe a PRs que tocam
`src/bri/{prompts,agent,guardrails}` — falta filtro `paths:`, senão PR de documentação paga eval.
Decidir antes da primeira PR que toque prompt.

### ADR-009 — Formato dos arquivos de prompt
Data: 2026-09-22 · Status: **proposta — decisão pendente**
Contexto: `specs/05-prompts-guardrails.md` exige `src/bri/prompts/<nome>.yaml` com `id`, `version`,
`model`, `system`, `template`, `output_schema` e `changelog`. No disco há três `.md` sem metadados.
Consequência prática: o gate "prompt alterado sem bump de versão" — cobrado na spec 09 e no prompt
do `ai-review` — não é verificável, nem por script nem pelo revisor IA, sem esses campos.
Opções: (a) converter os três para `.yaml` conforme a spec; (b) manter `.md` com front matter YAML
(legível para prompts longos, ainda parseável); (c) alterar a spec e abrir mão do gate automático.
Recomendação: (b) — preserva a legibilidade do corpo do prompt e viabiliza o gate.

## Log de sessão
<!-- AAAA-MM-DD — o que foi feito, decisão tomada, próximo passo -->
- 2026-09-21 — Reorganização do repositório: specs consolidadas em português em `specs/`,
  conjunto em inglês arquivado em `specs/_archive/en-draft/`, ADRs 001/002 do bookinsights
  incorporados como ADR-006/007 para evitar colisão de numeração.
- 2026-09-22 — Revertida a decisão anterior: o conjunto **em inglês** passa a ser o normativo
  (é o que `AGENTS.md` referencia) e o conjunto em português foi para `specs/_archive/pt/`.
  Motivo: os dois conjuntos coexistiam em `specs/` com numeração divergente (PT 05 = agente,
  EN 05 = prompts/guardrails), o que faria um agente ler a spec errada ao seguir a instrução
  "leia apenas a spec relevante". Restaurados ADR-006/007, que tinham sido apagados junto com o
  log embora as decisões continuem valendo nas specs novas. `ci.yml` movido para
  `.github/workflows/` (na raiz o GitHub nunca o executaria).
  Próximo passo: decidir ADR-008 e ADR-009; criar o andaime que o CI pressupõe
  (`Makefile`, `tests/`, `evals/`, deps de dev no `pyproject.toml`), hoje inexistente — a
  primeira PR nasce vermelha sem ele.
- 2026-09-22 — Reforçada a seção 8 (Estilo) do `AGENTS.md` a pedido do Michael: código simples
  e enxuto, sem abstração para caso hipotético; nomes humanos do domínio do livro/review, nunca
  genéricos ou inventados; comentário curto só onde o código não fala por si, nunca parágrafo.
  Vale para todo código escrito no projeto daqui pra frente, não é uma spec de módulo — por isso
  entrou no `AGENTS.md` (documento transversal) e não em `specs/0N`.
- 2026-09-22 — Início da ingestão (spec 01). Confirmado o schema real dos CSVs (`data/raw/`):
  `Books_rating.csv` não tem coluna de helpfulness, ao contrário do que a spec 01 assumia — spec
  01 e a hipótese H2 (`specs/00-overview.md`) corrigidas para usar comprimento de texto como
  proxy de profundidade, sem depender de helpfulness. Também não há id de review na fonte;
  gerado sequencialmente na ingestão. Dados brutos, que estavam em `csv/` na raiz, movidos para
  `data/raw/` (caminho que a spec 01 e os notebooks já esperavam); `csv/` removido do
  `.gitignore` por não ter mais uso. Primeiro incremento de código é só `raw → interim`
  (`src/bri/data/ingest.py`); carga em DuckDB (`processed`) fica para o próximo incremento.
  De quebra, achado um bug no `.gitignore`: os padrões `data/` e `docs/` (sem `/` na frente) não
  eram ancorados, então ignoravam qualquer diretório com esse nome em qualquer nível — inclusive
  `src/bri/data/`, o pacote Python recém-criado, que por isso nunca apareceria no `git status`.
  Corrigido para `/data/` e `/docs/` (só a raiz).
