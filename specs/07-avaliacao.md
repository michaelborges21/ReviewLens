# Spec 07 — Avaliação
Status: rascunho

> Sem eval, "ficou bom" é opinião. Com eval, é resultado de slide. Esta spec é o que mais sustenta "capacidade analítica".

## Conjuntos
| Conjunto | Tamanho | Como nasce |
|---|---|---|
| Rótulos de enriquecimento | 200 reviews | anotação manual estratificada |
| Golden Q&A | 60–100 perguntas | escritas à mão por categoria: analytics, opinião, resumo, mixed, ambígua, fora de escopo, adversarial |
| Recuperação | 50 consultas × reviews relevantes | anotação semi-automática + revisão |
| Adversarial | 30 reviews com injeção plantados | escritos à mão |

Versionados em `eval/data/`, nunca usados para few-shot (evita vazamento).

## Métricas
| Componente | Métrica |
|---|---|
| Enriquecimento | F1 por aspecto, Cohen's kappa no sentimento, % schema válido, % evidência = substring |
| Recuperação | Recall@k, MRR, nDCG — por estratégia (vetorial/BM25/híbrido/+rerank) |
| SQL | execution accuracy (resultado igual ao gabarito) |
| Router | acurácia e matriz de confusão |
| Resposta | faithfulness e relevância (LLM-as-judge com rubrica), % citações válidas, recusa correta |
| Segurança | taxa de sucesso de injeção, vazamentos de PII |
| Operação | latência p50/p95, custo por pergunta, custo por 1k reviews |
| Negócio | tempo por tarefa manual vs ferramenta (teste cronometrado, 5 tarefas) → alimenta impacto |

## LLM-as-judge
- Rubrica explícita 1–5 com exemplos; juiz ≠ modelo gerador quando possível.
- Calibrar juiz com 20 casos avaliados por humano; reportar concordância.

## Processo
- `uv run python -m eval.run --suite <nome>` → `eval/reports/<data>_<versao>.md`.
- Toda mudança de prompt/modelo roda a suite relevante; regressão > 3 p.p. bloqueia merge.
- Tabela "antes/depois" das iterações vira slide (storytelling de engenharia).

## Critérios de aceite
- [ ] Relatório consolidado com todas as métricas e comparação de ≥ 2 variantes por componente.
