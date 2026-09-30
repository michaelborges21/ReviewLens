# 02 — Pipeline NLP (batch, offline)
Status: em implementação (v0.1) — etapa 3 (aspectos) concluída em 19.947 reviews; etapas 2
(sentimento), 4 (tópicos) e 5 (sumarização) pendentes

## Princípio
Tudo que pode ser **pré-computado** é pré-computado. O agente consulta resultados, não reprocessa 1M+ reviews em tempo de pergunta. Isso corta custo e latência e torna as respostas auditáveis.

## Etapas
1. **Idioma** — filtrar/rotular; escopo inicial: inglês (ou o idioma dominante). Fora desta fase
   por decisão registrada.
2. ~~**Sentimento** — modelo encoder em toda a base~~ → **não será construído (ADR-015).** O
   sentimento **por aspecto** que a etapa 3 produz responde H5 sem inferência sobre 2,24M textos:
   2,5% das avaliações de nota alta têm texto majoritariamente negativo, 3,5% das de nota baixa
   têm texto positivo (`consultas.divergencia_nota_sentimento`). Não existe, e não passará a
   existir, sentimento de review inteira — neste projeto "sentimento" é sempre por aspecto.
3. **Aspectos (ABSA)** — LLM com saída estruturada na amostra. **Concluída**: 19.947 avaliações,
   45.847 aspectos, 97,0% de citação literal verificada.
4. **Tópicos** — **k-means sobre os embeddings já existentes, não BERTopic (ADR-016)**; rótulos
   gerados por LLM e revisados por humano. k=20 escolhido por medição. A silhueta medida é ~0,02
   em todo k de 8 a 60: a saída é **tema exploratório**, não "o tópico da review".
5. **Sumarização por entidade** — autor e gênero, com piso de 20 avaliações analisadas. **Não é a
   cascata map-reduce literal** (review → livro → autor → gênero) que esta spec desenhava: a
   agregação de aspectos em SQL já é o passo "map" e é pré-computada, e não há problema de janela
   de contexto a resolver (9 aspectos + 12 citações cabem muitas vezes), então o "reduce" é uma
   chamada por entidade. Cada resumo cita `review_id` reais, validados contra os ids enviados.
   Livros ficam fora do primeiro passe.

## Schema de aspectos (exemplo)
```json
{
  "review_id": "str",
  "aspects": [
    {"aspect": "enum[enredo, personagens, ritmo, final, escrita, tradução, edição_física, preço, outro]",
     "sentiment": "enum[positivo, negativo, neutro, misto]",
     "evidence": "trecho literal curto da review"}
  ],
  "is_recommendation": "bool | null"
}
```
`evidence` precisa ser substring do texto original → validação programática (anti-alucinação).

## Schema de resumo de entidade
```json
{"entity_type": "livro|autor|genero", "entity_id": "str",
 "headline": "str (1 frase)", "strengths": ["str"], "weaknesses": ["str"],
 "notable_quotes": [{"review_id": "str", "quote": "str"}],
 "n_reviews_considered": "int", "prompt_version": "str"}
```

## Custo e execução
- Antes de `make enrich`: script imprime nº de chamadas, tokens estimados, custo estimado e tempo. Execução só após aprovação (HITL).
- Batch API quando disponível; cache por hash; retomável (checkpoint por lote).
- **Execução local em `gemma4:12b` via Ollama (ADR-004)** — custo zero, sem chave de API. A
  estimativa de custo em dinheiro deixa de ser bloqueio; o que importa agora é **tempo**: ~4,3s
  por review, ~23,6h para as 19.949 da amostra. Daí o checkpoint retomável ser obrigatório, não
  opcional.
- Três ajustes medidos como obrigatórios: as 9 categorias listadas no prompt, JSON Schema no
  `format` do Ollama (restringe a decodificação — torna enum inválido impossível) e
  `think: false`. Sem eles: 33% de enum correto e 50,4s por review, contra 100% e 4,3s com eles.

## Saídas
- `review_enriched` — `review_id`, `aspects` (lista de aspecto+sentimento+evidência literal),
  `is_recommendation`. **Sem coluna de sentimento de review inteira** (ADR-015) e **sem coluna de
  tópico**: o tópico vive em `chunk_topics`, na granularidade de chunk, que é a granularidade em
  que o embedding existe.
- `entity_summaries` — um resumo por par (tipo, entidade), com citações verificadas.
- `topics` + `chunk_topics` — os 20 temas e a ligação chunk↔tema. Separadas de `review_chunks`
  porque `make index` recria aquela tabela com `CREATE OR REPLACE`.
