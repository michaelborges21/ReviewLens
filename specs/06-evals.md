# 06 — Avaliação
Status: em implementação (v0.1) — `make eval-smoke` e `make red-team` existem e rodam
(`evals/smoke_narracao.py`, `evals/red_team.py`); faltam o golden set de 100 reviews dirigidas, que depende de
rotulagem humana, o LLM-as-judge de fidelidade e o `make eval` completo ·
**Sem eval, não há como saber se uma mudança melhorou algo.**

## Conjuntos
| Conjunto | Tamanho inicial | Gabarito |
|---|---|---|
| Golden Q&A | 60–100 perguntas (analíticas, semânticas, mistas, fora de escopo) | analíticas: resultado SQL; semânticas: pontos-chave esperados |
| Retrieval | 50 queries | ids relevantes rotulados |
| Aspectos | 100 reviews dirigidas à incerteza, rotuladas à mão | aspectos + sentimento |
| Red-team | 26 casos implementados | injeção em review, papel, vazamento, invenção, fora de escopo |

> **Por que 100 dirigidas e não 200 aleatórias** — decidido em 2026-09-28, depois de medir. O "200"
> era número redondo, não derivado de meta de precisão, e duas medições baratas cobriram parte do que
> ele mediria.
>
> **Sentimento:** a negatividade dos aspectos cai de 94,3% na nota 1 para 4,0% na nota 5, gradiente
> monotônico sobre os **45.847 aspectos** — população inteira, margem menor que qualquer amostra de
> 200 daria. Para esta metade, rotular à mão seria estritamente pior.
>
> **Categoria:** concordância com um segundo modelo local (`qwen3:14b`) em 60 reviews deu 86,7% com
> ao menos uma categoria em comum, **13,3% sem nenhuma** (onde pelo menos um dos dois erra) e
> localizou `ritmo` como a mais frágil, com 54,5% de confirmação. Não substitui rótulo humano —
> concordância diz *onde* há dúvida, nunca quem está certo — mas estreita o alvo.
>
> **Tamanho:** para a pergunta que decide algo (acerto de categoria acima ou abaixo de 85%), 100
> casos dão folga: ±10% pediria ~35, ±5% pediria ~138. E os 100 são **dirigidos à incerteza** —
> casos de discordância entre modelos e aspectos `ritmo` —, o que rende mais informação por minuto
> de rotulagem que sorteio aleatório.

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
`make eval-smoke` (5 casos × cada versão candidata do prompt, ~2min, **local antes do merge** — saiu
do CI pela ADR-008, porque o runner não tem GPU para o `gemma4:12b`) · `make red-team` (26 ataques,
~3min) · `make eval` (completo, ainda stub).
Resultados versionados em `reports/evals/<data>_<git-sha>.json` e `redteam_<data>_<git-sha>.json`.

O smoke mede sobre o **JSON bruto**, antes dos normalizadores de `RespostaNarrada` — medir depois
deles esconderia o que se quer comparar entre versões de prompt. Seus critérios são de dois tipos, e
só o primeiro trava o gate: `schema_valido`, `citacao_fundamentada`, `sem_id_no_texto` e
`resistiu_a_injecao` indicam defeito visível ao usuário; `sem_citacao_repetida`,
`confianca_canonica` e `frases_entre_3_e_5` são informativos, porque os normalizadores já os
corrigem antes da tela.

Limitação a ter em conta ao ler os números: 5 casos fazem cada ponto valer 20 pontos de passo, e o
mesmo critério oscilou entre execuções. Servem para comparar direção, não para precisão.
