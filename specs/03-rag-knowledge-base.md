# 03 — Bases de conhecimento e RAG
Status: rascunho v0.1

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
