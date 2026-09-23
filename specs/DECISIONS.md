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
`model`, `system`, `template`, `output_schema` e `changelog`.
**Correção de 2026-09-22:** a versão anterior desta entrada afirmava que os três prompts eram
`.md` "sem metadados". Estava errado — ao abri-los para a F1, os três têm front matter YAML com
`version`, `used_by` e `schema`. Ou seja, a opção (b) abaixo **já está implementada** e o gate
"prompt alterado sem bump de versão" é verificável hoje.
Opções: (a) converter os três para `.yaml` conforme a spec; (b) manter `.md` com front matter YAML
(legível para prompts longos, ainda parseável); (c) alterar a spec e abrir mão do gate automático.
Decisão: **(b)**, que é o estado real do repositório. Resta alinhar a spec 05, que ainda pede
`.yaml`, e completar os campos que faltam no front matter (`model`, `changelog`).

### ADR-010 — FastAPI + Jinja2 + HTMX no lugar de Streamlit
Data: 2026-09-23 · Status: aceita
Contexto: o Michael quis ver a interface cedo para ir opinando, com o backend acompanhando.
O `AGENTS.md` §4 e a spec 04 definiam Streamlit.
Recomendei manter Streamlit: o ciclo de iteração visual é mais curto e não exige frontend
separado. Ele optou por FastAPI, com frontend servido pelo próprio backend.
Decisão: FastAPI servindo Jinja2, com HTMX como melhoria progressiva. Sem Node e sem build —
os formulários funcionam sem JavaScript, e o HTMX só troca fragmentos quando está disponível.
Alternativas descartadas: SPA em React/Vue (toolchain e build tornam cada ajuste visual lento,
que é o oposto do objetivo); FastAPI só como API (não permite ver a interface).
Consequências:
+ contrato explícito por rota — quando a tela muda, sabe-se qual rota muda
+ as mesmas consultas saem em JSON sob `/api`, reaproveitáveis
− sem widgets prontos: mais código de tela escrito à mão
− `app/` não é coberto pelo `mypy --strict`, que o `AGENTS.md` §4 restringe a `src/`; por isso a
  lógica mora em `src/bri/` e `app/` fica fino

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
- 2026-09-22 — Camada `processed` (spec 01): `src/bri/data/process.py` carrega `reviews`,
  `books`, `book_authors` e `review_editions` no DuckDB. Medido antes de desenhar: ~25% da base
  é duplicação (3M → ~2,24M), quase toda ela a mesma review replicada entre edições do mesmo
  livro. Decidido remover mantendo `review_editions` (review canônica → todos os `book_id`), em
  vez de remover sem rastro ou de marcar com flag — flag faria todo consumidor lembrar de
  filtrar, e quem esquecesse inflaria o número em silêncio. Dedup usa chaves distintas para
  identificados e anônimos porque tratar `user_id` nulo como um usuário só colapsaria 175.412
  reviews anônimas legítimas. Duas divergências da spec 01 propostas e aceitas: não normalizar
  espaços (zero espaços duplos e zero tags medidos em 3M de reviews) e não duplicar o texto
  original em coluna separada (o pré-unescape já vive em `data/interim/`). `users_agg`,
  `author_stats` e `genre_stats` ficam para o incremento de EDA, onde serão usadas de fato.
  `empty_as_null=True` fixado explicitamente no `explode` de `montar_book_authors`: hoje uma
  lista de autores vazia explode para nulo e é descartada, mas o Polars 2.0 inverte esse default
  e os 31.413 livros sem autor passariam a gerar par em `book_authors`. Cheguei a fixar isso no
  `read_csv` da ingestão por engano — o parâmetro não existe lá, e o `mypy --strict` pegou.
- 2026-09-22 — EDA e fechamento da F0 (spec 01). Duas decisões: (a) **veredito parcial** — H1, H3
  e H5 dependem de aspectos e sentimento, que só existem na F1, então a EDA as marca como
  pendentes em vez de fingir conclusão; a spec 00 foi alterada para admitir isso. (b) **idioma
  sai do checklist de qualidade** — detectar em 2,24M de textos custaria dependência e tempo, e
  quem precisa é a F1 sobre a amostra estratificada. Achado que contraria a leitura intuitiva de
  H2 e afeta a spec 04: o comprimento da review **não cresce com a nota**, faz um arco — mediana
  de 645 caracteres na nota 3 contra 459 na nota 5. Quem dá 5 estrelas escreve pouco; quem
  argumenta é o público do meio. Logo, "melhor candidato a entrevista" não é o resenhista
  entusiasmado. Agregações vivem em SQL dentro do DuckDB (`src/bri/data/stats.py`) e são testadas
  contra banco em memória, em vez de reimplementadas em Python só para ficarem testáveis.
- 2026-09-22 — Amostragem e custo (specs 01 e 02), para destravar a F1 sem gastar nada. A base
  tem 1.773.128.911 caracteres, da ordem de 440 milhões de tokens só de entrada: enriquecer tudo
  é inviável em qualquer modelo, e é por isso que a spec 02 usa amostra e deixa a cobertura
  total para a destilação (spec 07). Decisões: (a) a estimativa é ancorada em **teto de gasto**,
  derivando quantas reviews cabem por modelo — é o formato que a ADR-004 precisa para comparar
  providers; (b) a alocação **sobre-amostra as faixas média e baixa** (pesos 3, 2 e 1), porque
  reviews ponderadas e críticas citam mais aspecto concreto por chamada paga; a distorção fica
  documentada em `reports/sampling.md` para quem extrapolar; (c) contagem de tokens por
  heurística de ~4 caracteres/token, com margem de 15-20% — sem a ADR-004 não há provider, e sem
  provider não há tokenizador correto; o `messages.count_tokens` exigiria justamente a credencial
  e a decisão que este incremento existe para destravar. `make enrich` segue bloqueado até o
  número ser aprovado.
- 2026-09-23 — Interface web (ADR-010). `src/bri/data/consultas.py` (consultas somente-leitura),
  `src/bri/agent/roteador.py` (classificação determinística de intenção, sem LLM) e `app/`
  (FastAPI + Jinja2 + HTMX). O roteador **não usa `sqlglot`**: ele compõe consultas
  parametrizadas a partir de filtros estruturados e nunca executa texto do usuário — a validação
  AST da spec 04 é para o SQL escrito por LLM, que só aparece na F2. Dois defeitos meus achados
  por teste durante a implementação: a resolução de entidade escolhia a palavra mais longa da
  pergunta como nome, e em "desempenho do autor Herbert" procurava um autor chamado
  "desempenho"; passou a testar todos os fragmentos contra o catálogo, ignorando palavras
  genéricas. O segundo foi vazamento de PII: a tela de entrevistas truncava o pseudônimo na
  exibição, mas mandava o hash **inteiro** no campo oculto do formulário de aprovação — bastava
  ver o código-fonte da página. O formulário passou a enviar só o prefixo, e o campo foi
  renomeado de `user_hash` para `prefixo`, que é o que ele de fato carrega. Quando a F3 trouxer
  export, a referência estável deve ser um token do lado do servidor, nunca o identificador no
  HTML. Restrição operacional: o app abre o DuckDB em read-only e o DuckDB não aceita leitor
  e escritor no mesmo arquivo — `make data` com a aplicação no ar falha.
