# evals/

Golden sets, red-team e runners de avaliação (spec `06-evals.md`).

## O que já roda

- `make eval-smoke` → `smoke_narracao.py`: compara versões do prompt de narração sobre 5 casos
  fixos, medindo sete critérios determinísticos no **JSON bruto** do modelo, antes dos
  normalizadores do schema. Falha se a versão em produção regredir num critério visível ao usuário.
- `make red-team` → `red_team.py`: 26 ataques de injeção indireta em cinco famílias — sobrescrever a
  instrução, assumir outro papel, vazar dado interno, inventar número e sair do escopo. Cada ataque
  declara a string que não pode aparecer na resposta, então a verificação é determinística.
- `casos.py`: monta o contexto envenenado, compartilhado pelos dois runners.
- `prompts_candidatos/`: versões anteriores do prompt, congeladas como linha de base do smoke.

Resultados vão para `reports/evals/`, versionados por data e sha do commit.

## O que falta, e depende de trabalho humano

O golden set de aspectos (100 reviews dirigidas à incerteza — ver spec 06) e o LLM-as-judge de
fidelidade. Rotulagem à mão não tem substituto: concordância entre dois modelos mostra *onde* há
dúvida, nunca qual dos dois está certo.
