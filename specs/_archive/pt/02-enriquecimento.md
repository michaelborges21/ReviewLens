# Spec 02 — Enriquecimento estruturado por review
Status: rascunho · Ver ADR-002

## Objetivo
Transformar texto livre em **colunas consultáveis** uma vez (batch), para que perguntas de negócio virem SQL barato e correto.

## Schema de saída (Pydantic, `llm/schemas.py`)
```python
class Aspect(BaseModel):
    name: Literal["enredo","personagens","escrita","ritmo","final","originalidade",
                  "precisao_factual","edicao_fisica","preco","traducao","outro"]
    sentiment: Literal["positivo","negativo","misto"]
    evidence: str = Field(max_length=200)   # trecho literal do review

class ReviewEnrichment(BaseModel):
    review_id: str
    overall_sentiment: Literal["positivo","negativo","misto","neutro"]
    score_text_mismatch: bool               # H2
    aspects: list[Aspect] = Field(max_length=6)
    themes: list[str] = Field(max_length=4) # livres, normalizados depois por clustering
    specificity: int = Field(ge=1, le=5)    # quão concreto/argumentado é (H3, entrevistas)
    is_spoiler: bool
    language: str
```
`evidence` deve ser substring do review → validação automática (anti-alucinação barata).

## Técnicas
- **Saída estruturada:** JSON Schema passado ao modelo (Ollama `format=<schema>` / tool schema na API) + validação Pydantic. Retry único com erro de validação.
- **Few-shot dinâmico:** banco de ~30 exemplos rotulados à mão cobrindo casos difíceis (sarcasmo, misto, spoiler, review em outro idioma, review sobre a entrega e não o livro). Para cada review, selecionar os **3 mais similares por embedding**. Motivo: few-shot fixo enviesa para os exemplos e desperdiça tokens.
- **Delimitação:** review dentro de `<review id>`; instrução repetida após o dado (reforço posicional).
- **Batch:** 10–20 reviews por chamada quando o modelo suportar, com `review_id` para reassociação.

## Amostragem
- Amostra estratificada por gênero × faixa de nota × década (ex.: 20–50k reviews; tamanho definido pelo custo medido em 500 reviews).
- Todo livro/autor usado na demo recebe cobertura completa.
- Registrar custo e tempo por 1k reviews → alimenta spec 00 (impacto) e spec 08 (justificativa do fine-tuning).

## Pós-processamento
- `themes` livres → embeddings → clustering (HDBSCAN) → rótulo de cluster gerado por LLM e revisado.
- Tabela `review_aspects` explodida (1 linha por aspecto) para SQL.

## Critérios de aceite
- [ ] ≥ 98% das saídas válidas no schema após retry.
- [ ] Concordância com 200 rótulos humanos medida (spec 07): F1 por aspecto, kappa no sentimento.
- [ ] Custo/1k reviews reportado.
