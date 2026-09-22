# 09 — Workflow de desenvolvimento, loops e CI
Status: rascunho v0.1

## 1. Doutrina de loops (regra central)
> Um loop de correção automática só existe quando há um **verificador determinístico**.
> Sem verificador, o loop apenas queima tokens com confiança crescente e qualidade constante.

Todo loop declara: **verificador**, **limite de iterações**, **o que fazer ao estourar o limite** (parar e pedir ajuda humana — nunca "seguir assim mesmo").

| Loop | Verificador | Máx. | Ao estourar |
|---|---|---|---|
| Geração de código | `pytest` + `mypy` | 3 | Para, resume o que falhou, pede orientação |
| Saída estruturada de LLM | schema pydantic (erro devolvido ao modelo) | 2 | Erro tratado + log; resposta marcada `confiança: baixa` |
| SQL gerado | validador AST + execução | 2 | Responde "não consegui formular a consulta" |
| Extração de aspectos | `evidence` é substring do texto original | 1 | Descarta o aspecto, registra em `reports/` |
| Prompt vs eval | `make eval-smoke` | 2 | Mantém versão anterior do prompt |

**MUST NOT do loop**: editar, enfraquecer, pular (`skip`/`xfail`) ou apagar um teste para fazê-lo passar. Se o teste está errado, isso é uma decisão humana — pare e proponha.

## 2. Ciclo de trabalho por tarefa
```
spec → plano → teste (falhando) → implementação → loop até verde → make check → PR
```
- Nenhum PR sem spec correspondente. Código que diverge da spec **para o trabalho**: ou a spec muda (com ADR), ou o código muda.
- Um PR = um assunto. PR gigante não é revisável por humano nem por IA.

## 3. CI — quem bloqueia e quem opina
LLM é não determinístico; **não pode ser gate de bloqueio**. Aprovar hoje e reprovar amanhã o mesmo código destrói a confiança no CI.

| Papel | Quem | Bloqueia merge? |
|---|---|---|
| Gate obrigatório | ruff · mypy · pytest · `eval-smoke` · **red-team de injeção** | **Sim** |
| Review qualitativo | Claude Action comentando no PR | Não — comenta |

O red-team como check obrigatório é o diferencial: o merge é reprovado se o agente voltar a ser vulnerável a instrução escondida dentro de uma review.

### Jobs
| Job | Quando | Conteúdo |
|---|---|---|
| `quality` | todo PR | ruff, mypy, pytest (sem chamada real a LLM) |
| `llm-gates` | PR que toca `src/bri/{prompts,agent,guardrails}` | `eval-smoke` + red-team, com LLM local ou modelo barato |
| `ai-review` | PR aberto/atualizado | Claude Action; comenta, não bloqueia |

**Custo**: disparar em `pull_request`, nunca em `push`. Segredos via GitHub Secrets; PR de fork não recebe segredo.

## 4. Escopo do review por IA
Pedir ao revisor o que linter não pega:
- aderência à spec citada no PR;
- prompt alterado sem incremento de versão ou sem eval;
- tool nova sem limite de permissão (spec 04/05);
- texto de review tratado como instrução (injeção);
- PII vazando para log, resposta ou export;
- número que vai para slide sem script reprodutível em `reports/`.
Não pedir: estilo, formatação, nomes — isso é trabalho do ruff.

## 5. Branches e commits
`main` protegida · branches `feat/`, `fix/`, `spec/` · commits convencionais · squash no merge.
