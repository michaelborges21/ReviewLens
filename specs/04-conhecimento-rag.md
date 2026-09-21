# Spec 04 — Base de conhecimento e RAG
Status: rascunho

## O que é "base de conhecimento" aqui (item g)
Três camadas, cada uma com um tipo de pergunta:
| Camada | Conteúdo | Serve para |
|---|---|---|
| Estruturada | tabelas DuckDB: livros, autores, gêneros, reviews enriquecidos, aspectos, usuários agregados | números, rankings, filtros |
| Semântica | índice de reviews (texto + summary) e descrições de livros | "o que leitores dizem sobre X" |
| Sumários | `EntitySummary` pré-computados | respostas rápidas e baratas sobre entidades populares |

Opcional (roadmap): enriquecer autores/obras com Wikidata/Open Library (ano, prêmios, série) → cruza "ganhou prêmio" × percepção.

## Indexação
- Chunk = 1 review (reviews longos: split em ~300 tokens com overlap, mantendo `review_id`).
- Metadados por chunk: `review_id, work_id, title, authors, categories, score, year, lang, helpful_ratio, specificity, sentiment`.
- Embeddings multilíngues locais (modelo em `config.py`).
- BM25 via DuckDB FTS (nomes próprios, títulos e termos raros o embedding erra).

## Recuperação
1. **Filtro por metadado primeiro** (autor, gênero, período, nota) — vem do estado conversacional/router.
2. Busca híbrida: vetorial top-50 + BM25 top-50 → **Reciprocal Rank Fusion**.
3. Rerank com cross-encoder → top-8/12.
4. Diversificação (MMR) para não trazer 10 reviews dizendo a mesma coisa.

## Grounding
- Contexto entregue como `<review id="…" score="…" year="…">texto</review>`.
- Regra: responder só com base no contexto; sem evidência → dizer que não há evidência suficiente.
- Pós-checagem: todo `review_id` citado existe no contexto recuperado.

## Por que não "só RAG"
RAG top-k **não agrega**: "qual a nota média do autor X?" respondida por 10 reviews recuperados é errada por construção. Ver ADR-001.

## Critérios de aceite
- [ ] Recall@10 e MRR medidos no golden set de recuperação (spec 07), comparando: vetorial, BM25, híbrido, híbrido+rerank. **Mostrar a tabela na apresentação.**
- [ ] Latência p95 de recuperação < 1,5 s na amostra de demo.
