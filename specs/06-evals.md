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
- Operacional: latência p50/p95 e throughput. Com execução local (ADR-004) o custo em dinheiro é
  zero — a restrição que importa passou a ser **tempo** (~4,3s por review, ~23,6h na amostra).
  Custo por pergunta volta a ser métrica relevante se a spec 07 comparar contra modelo comercial.

## Metas iniciais (revisar após baseline)
Roteador ≥ 90% · SQL ≥ 90% · Recall@8 ≥ 0,8 · Faithfulness ≥ 0,9 · Red-team crítico = 100%.

## Execução
`make eval-smoke` (≈15 casos, rápido, **local antes do merge** — saiu do CI pela ADR-008, porque o
runner não tem GPU para o `gemma4:12b`) · `make eval` (completo, manual).
Resultados versionados em `reports/evals/<data>_<git-sha>.json`.
