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

| Papel | Quem | Onde roda | Bloqueia merge? |
|---|---|---|---|
| Gate obrigatório (automático) | ruff · mypy · pytest | CI | **Sim** |
| Gate obrigatório (manual) | `eval-smoke` · **red-team de injeção** | **local, antes do merge** | Sim, por disciplina |

O review qualitativo por IA saiu (ADR-011): dependia de chave de API, que o projeto não usa.
O papel que ele cumpria — pegar o que o linter não vê — passou a ser revisão humana.

O red-team continua sendo o diferencial: o merge não deve acontecer se o agente voltar a ser
vulnerável a instrução escondida dentro de uma review.

**Por que ele saiu do CI (ADR-008):** a ADR-004 escolheu `gemma4:12b` local, e o runner do GitHub
não tem GPU — não consegue executar o modelo do projeto. Não há chave de API para a alternativa
comercial. O gate passou a ser local, e com isso **deixou de ser automático**: depende de
disciplina humana, que esta mesma spec aponta como frágil. Mitigação em aberto: hook de
`pre-push` local rodando o red-team.

### Jobs
| Job | Quando | Conteúdo |
|---|---|---|
| `quality` | todo PR | ruff, mypy, pytest (sem chamada real a LLM) |

Dois jobs foram removidos do `ci.yml`: `llm-gates` (ADR-008), que exigia GPU inexistente no
runner, e `ai-review` (ADR-011), que dependia de chave de API. `eval-smoke` e red-team rodam
localmente, antes do merge.

**Custo**: disparar em `pull_request`, nunca em `push`. O CI **não precisa de nenhum segredo** —
não há chave de API no projeto.

## 4. Escopo da revisão de PR (hoje humana)
A lista abaixo nasceu como instrução para o revisor por IA, removido pela ADR-011. Continua
valendo como **checklist de revisão humana** — e volta a ser automatizável se um dia o projeto
tiver um provider configurado. Olhar o que o linter não pega:
- aderência à spec citada no PR;
- prompt alterado sem incremento de versão ou sem eval;
- tool nova sem limite de permissão (spec 04/05);
- texto de review tratado como instrução (injeção);
- PII vazando para log, resposta ou export;
- número que vai para slide sem script reprodutível em `reports/`.
Não pedir: estilo, formatação, nomes — isso é trabalho do ruff.

## 5. Branches e commits
`main` protegida · branches `feat/`, `fix/`, `spec/` · commits convencionais · squash no merge.
