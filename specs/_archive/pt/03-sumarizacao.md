# Spec 03 — Sumarização de informação textual
Status: rascunho

## Níveis
| Nível | Entrada | Saída |
|---|---|---|
| Livro | reviews do livro (enriquecidos) | `BookSummary` |
| Autor | `BookSummary` dos livros + métricas SQL | `EntitySummary` |
| Gênero | idem, agregando autores/livros | `EntitySummary` |

## Estratégia: map-reduce guiado por dados
1. **Selecionar** (não jogar tudo no contexto): por aspecto, os reviews mais específicos e úteis de cada polaridade, + amostra aleatória para evitar viés de extremos.
2. **Map:** resumo por lote com citações de `review_id`.
3. **Reduce:** consolida lotes; números injetados **do SQL** no prompt como fatos (`<metrics>`), nunca calculados pelo LLM.
4. **Verificação:** citações existem? cada ponto tem ≥1 evidência? proporção de pontos positivos/negativos coerente com a distribuição real de aspectos?

## Schema
```python
class Point(BaseModel):
    text: str
    polarity: Literal["forte","fraco"]
    prevalence: Literal["recorrente","ocasional"]  # derivado de contagem SQL, não opinião do LLM
    citations: list[str] = Field(min_length=1)

class EntitySummary(BaseModel):
    entity: str; level: Literal["livro","autor","genero"]
    headline: str = Field(max_length=160)          # 1 frase para executivo
    strengths: list[Point]; weaknesses: list[Point]
    trend_note: str | None                          # só se SQL detectar tendência significativa
    recommended_actions: list[str] = Field(max_length=3)  # "ser propositivo"
```

## Anatomia do prompt (reforço posicional)
```
[system]  papel + constraints + formato
[user]    <metrics>…</metrics> <reviews>…</reviews>
          ↓ ao FINAL, repetir: tarefa, regra de citação, regra "números só de <metrics>"
```
Motivo: com contexto longo, instruções no meio perdem peso (*lost in the middle*); repetir o essencial no fim é barato e mensurável no eval.

## Critérios de aceite
- [ ] 100% dos pontos com citação válida.
- [ ] Faithfulness ≥ 0.9 no LLM-as-judge (spec 07) em 30 resumos.
- [ ] Resumos cacheados por (entidade, versão do prompt, versão dos dados).
