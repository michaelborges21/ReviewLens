# 03 — Bases de conhecimento e RAG
Status: implementado (v0.2) para KB-Reviews, a única base desta rodada — `make index`
(`src/bri/retrieval/{chunking,indexar,buscar}.py`), ligado ao roteador via `Intencao.TEMA_LIVRE`.
KB-Books, KB-Summaries e KB-Glossário seguem fora de escopo. Decisões de implementação registradas
abaixo, sob "Notas de implementação".

## Quando usar RAG (e quando NÃO)
- **RAG serve para**: "o que os leitores dizem sobre X", exemplos, citações, nuances.
- **RAG NÃO serve para agregação** ("nota média do autor X", "quantas reviews em 2010"). Isso é SQL (ver 04). Top-k de trechos não conta nada com precisão.

## Bases
| Base | Conteúdo | Uso |
|---|---|---|
| KB-Reviews | reviews (unidade = review; longas quebradas com overlap) + metadados | busca semântica com filtros |
| KB-Books | descrições e metadados dos livros | contexto do catálogo |
| KB-Summaries | resumos hierárquicos de 02 | respostas rápidas de visão geral |
| KB-Glossário | definições de negócio (nota bayesiana, helpfulness, polarização) | consistência de termos |

## Retrieval
- **Híbrido**: BM25 + denso, fundidos por Reciprocal Rank Fusion.
- **Filtros de metadados antes** da busca (autor, gênero, período, faixa de nota).
- **Rerank** com cross-encoder no top-50 → top-k final (k≈8, ajustar por eval).
- Diversidade: evitar k trechos do mesmo usuário/livro (MMR ou limite por grupo).

## Grounding e citações
- Contexto enviado ao LLM em blocos `<review id="..."> ... </review>`.
- Toda afirmação da resposta referencia `review_id`s presentes no contexto.
- Verificação pós-geração: ids citados ⊆ ids recuperados; senão, retry ou marcar baixa confiança.
- Sem evidência suficiente → responder "não encontrei base suficiente", nunca inventar.

## Avaliação (ver 06)
Recall@k e MRR no conjunto de queries rotuladas; ablação: denso vs BM25 vs híbrido vs híbrido+rerank.

## Notas de implementação (2026-09-28)

Corpus indexado é `enrichment_sample` (19.949 avaliações), a mesma fronteira que `review_enriched`
já respeita — não a base inteira de 2.239.998. Medido na sessão de planejamento: embeddings via
`embeddinggemma` no Ollama custam 5ms por chamada isolada, com o modelo já carregado. **Medido na
execução real, contra o banco inteiro**: `make index` gerou **22.006 chunks** (19.949 reviews mais
os pedaços dos 7,8% que passam de 2.000 caracteres) em **8min55s a 11min40s** — mais lento que a
estimativa de 5ms/chamada isolada sugeria (overhead real de HTTP e serialização em série, não só o
tempo de inferência), mas ainda assim minutos, não as 17h43min do `extract.py`. Busca por
similaridade em ~28.000 vetores sintéticos sem índice HNSW respondeu em ~88ms na medição de
planejamento, confirmando a aposta da ADR-005 de que varredura direta basta nesta escala.

Decisões de escopo, todas por medição ou por ausência de recurso disponível, não por atalho:
- **Sem checkpoint no indexador** — minutos de execução, não o cenário de 17h43min que justificou
  retomada no `extract.py`. `make index` recria a tabela inteira a cada execução.
- **Sem MMR formal** — diversidade por contador simples (no máx. 2 chunks por review, 3 por título).
  92% das reviews indexadas são chunk único; MMR pediria um segundo cálculo sem ganho demonstrado.
- **Sem reranker cross-encoder** — nenhum modelo de rerank disponível localmente. O ranking final é
  a fusão RRF de BM25 + denso.
- **k = 8**, com margem acima do `MAX_CITACOES = 5` do narrador para o que o limiar de relevância ou
  a diversidade descartarem.
- **Limiar de "sem evidência suficiente" = 0,3** de similaridade de cosseno bruta, aplicado como
  **filtro de associação sobre todos os candidatos fundidos**, não como checagem do topo do ranking
  RRF — ver bug corrigido abaixo. Piso conservador inicial, a calibrar depois via `eval-smoke`.
- Filtro de autor/gênero é opcional e pré-busca (JOIN), não pós-hoc; quando a pergunta combina tema
  livre com entidade nomeada, o roteador resolve a entidade do jeito que já faz para AUTOR/GENERO.
  Só se aplica quando a entidade aparece como nome próprio na pergunta — perguntas usando a palavra
  literal "autor"/"gênero" continuam roteadas para o SQL determinístico já existente (que tem sua
  própria quebra por categoria, "final" incluso), não para a busca semântica.

### Bug encontrado e corrigido contra o banco real (2026-09-28)

A checagem de "sem evidência suficiente" verificava só `fundidos[0]` — o item no **topo do ranking
fundido por RRF**, não o melhor item por similaridade densa. Reproduzido com a pergunta real "o que
os leitores criticam sobre finais decepcionantes": a busca densa achou um match genuíno de 0,591 de
similaridade, mas o BM25 ranqueou em 1º um chunk cuja **similaridade densa era 0,0** (coincidência
de termo — a pergunta em português contra reviews em inglês), que venceu a fusão RRF e apareceu como
`fundidos[0]`. A checagem via aquele item ruim no topo e descartava a busca inteira, escondendo o
match denso genuíno que estava mais abaixo na lista fundida.

Corrigido em `buscar.py`: o limiar agora filtra **todos** os candidatos fundidos por
`similaridade_densa >= SIMILARIDADE_MINIMA` antes de aplicar diversidade e cortar em k, em vez de
checar só o primeiro colocado. Teste de regressão em `tests/test_buscar.py` reproduz o cenário
(BM25 rankeia em 1º um chunk denso-irrelevante; a busca ainda encontra o match denso genuíno em 2º
lugar na fusão).
