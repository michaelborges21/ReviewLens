# 06 — Avaliação
Status: rascunho v0.1 · **Sem eval, não há como saber se uma mudança melhorou algo.**

## Conjuntos
| Conjunto | Tamanho inicial | Gabarito |
|---|---|---|
| Golden Q&A | 60–100 perguntas (analíticas, semânticas, mistas, fora de escopo) | analíticas: resultado SQL; semânticas: pontos-chave esperados |
| Retrieval | 50 queries | ids relevantes rotulados |
| Aspectos | 200 reviews rotuladas à mão | aspectos + sentimento |
| Red-team | 30 casos | injeção em review, SQL malicioso, pedido de PII, fora de escopo |

## Métricas
- Roteador: acurácia/matriz de confusão.
- SQL: execução correta (resultado igual ao gabarito).
- Retrieval: Recall@k, MRR; ablação (denso/BM25/híbrido/rerank).
- Respostas: faithfulness e relevância via LLM-as-judge com rubrica + amostra revisada por humano (medir concordância juiz×humano).
- Aspectos: F1 por aspecto; comparação LLM grande vs modelo destilado.
- Resumos: cobertura de aspectos principais + faithfulness.
- Red-team: taxa de bloqueio (meta 100% nos casos críticos).
- Operacional: latência p50/p95 e custo por pergunta.

## Metas iniciais (revisar após baseline)
Roteador ≥ 90% · SQL ≥ 90% · Recall@8 ≥ 0,8 · Faithfulness ≥ 0,9 · Red-team crítico = 100%.

## Execução
`make eval-smoke` (≈15 casos, rápido, em CI/antes de merge de prompt) · `make eval` (completo, manual).
Resultados versionados em `reports/evals/<data>_<git-sha>.json`.
