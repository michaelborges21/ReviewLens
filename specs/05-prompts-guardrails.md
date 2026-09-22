# 05 — Engenharia de prompts, saídas estruturadas e guardrails
Status: rascunho v0.1

## Versionamento de prompts
`src/bri/prompts/<nome>.yaml`: `id`, `version`, `model`, `system`, `template`, `few_shot_bank` (opcional), `output_schema`, `changelog`.
Mudou prompt → incrementa versão → `make eval-smoke` → sem regressão ou justificativa em DECISIONS.

## Anatomia do system prompt (template)
1. Papel e objetivo (1–2 frases).
2. Escopo: o que responde / o que recusa.
3. Constraints explícitas (MUST/MUST NOT), poucas e testáveis.
4. Como tratar o contexto (dados não confiáveis, citar ids).
5. Formato de saída (schema).

## Posicionamento (contexto longo)
Ordem: system → contexto delimitado em XML → pergunta + lembrete do formato **no final**.
Com muitos documentos, repetir as 2–3 constraints críticas após o contexto (mitiga "lost in the middle"). Colocar os trechos mais relevantes (após rerank) no início e no fim do bloco.

## Few-shot — onde usar
- ✅ Roteador (classificação de intenção), extração de aspectos, geração de SQL (exemplos pergunta→SQL sobre o schema real).
- ✅ Seleção **dinâmica** de exemplos por similaridade a partir de um banco.
- ❌ Resposta final de RAG (exemplos contaminam estilo e conteúdo).
- Exemplos cobrem casos difíceis (sarcasmo, review mista, pergunta ambígua), não só os fáceis.

## Saídas estruturadas
- Preferir saída estruturada nativa do provider (JSON schema / tool use); fallback: parser + pydantic.
- Validação falhou → retry com a mensagem de erro (máx. 2) → senão, erro tratado e logado.
- Validações semânticas além do schema: `evidence` é substring do texto; ids citados existem; SQL passa no validador.

## Raciocínio (CoT / ReAct)
- Usar modelos/modos de raciocínio nativos quando a tarefa pedir (SQL complexo, perguntas mistas). Não exigir raciocínio textual dentro do JSON final.
- Campo curto `rationale` só onde auditoria importa (roteador, ranking de entrevistas).
- ReAct com limite de passos, orçamento de tokens e log de cada ação/observação.

## Guardrails
**Injeção indireta (principal risco deste projeto)**: reviews são texto escrito por terceiros e podem conter "ignore as instruções...".
- Sempre delimitadas em `<review>`; system prompt declara que conteúdo delimitado é dado, nunca instrução.
- Heurística/classificador para marcar reviews suspeitas no índice.
- Tools com menor privilégio: mesmo uma injeção bem-sucedida não consegue escrever, apagar ou exfiltrar.

**Entrada do usuário**: bloquear fora de escopo; limitar tamanho.
**SQL**: sqlglot → só SELECT, só tabelas permitidas, sem funções de arquivo (`read_csv`, `COPY`, `ATTACH`), LIMIT obrigatório, conexão read-only.
**PII**: pseudonimização na camada processed; revelação só via HITL; logs sem texto de usuário completo.
**Conteúdo**: reviews ofensivas não são reproduzidas em resumos; citar com parcimônia.
**Saída**: validação de citações; resposta sem evidência vira "não sei".

## Human-in-the-loop (pontos obrigatórios)
1. Execução de batch LLM acima do orçamento (custo estimado mostrado antes).
2. Revelação/export da lista de candidatos a entrevista.
3. Promoção de nova versão de prompt que piora alguma métrica.
4. Rótulos de tópicos gerados por LLM (revisão rápida antes de ir para slides).
