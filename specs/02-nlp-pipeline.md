# 02 — Pipeline NLP (batch, offline)
Status: rascunho v0.1

## Princípio
Tudo que pode ser **pré-computado** é pré-computado. O agente consulta resultados, não reprocessa 1M+ reviews em tempo de pergunta. Isso corta custo e latência e torna as respostas auditáveis.

## Etapas
1. **Idioma** — filtrar/rotular; escopo inicial: inglês (ou o idioma dominante).
2. **Sentimento** — modelo encoder (ex.: RoBERTa de sentimento) em toda a base. Comparar com a nota → H5.
3. **Aspectos (ABSA)** — LLM com saída estruturada na amostra; opcionalmente destilado para modelo pequeno (ver 07) para cobrir a base toda.
4. **Tópicos** — BERTopic sobre embeddings; rótulos de tópicos gerados por LLM e revisados por humano.
5. **Sumarização hierárquica (map-reduce)** — review → livro → autor → gênero. Cada nível cita os ids do nível abaixo.

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
- Alternativa local (Ollama) para iteração barata de prompts; modelo comercial para rodada final, se a qualidade justificar (decidir via eval).

## Saídas
`review_enriched` (sentimento, aspectos, tópico), `entity_summaries`, `topics`.
