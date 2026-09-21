# 07 — Fine-tuning (opcional)
Status: backlog

## Alvo recomendado: destilação de extração de aspectos
Não fazer fine-tuning para "ensinar os dados" ao modelo — conhecimento muda e isso é papel do RAG.
Fazer fine-tuning onde há **tarefa repetitiva em volume**: extrair aspectos de toda a base.

1. LLM grande rotula a amostra (spec 02) → revisão humana de um subconjunto.
2. LoRA/QLoRA em modelo open source pequeno (1–4B, família Qwen/Llama/Gemma) — ou classificador encoder (DeBERTa) se a saída for simplificada para multi-label.
3. Comparar em 06: F1 vs LLM grande, custo por 1M reviews, latência.
4. Decisão via ADR: vale usar em produção se perda de F1 ≤ X p.p. e custo cai ≥ 10×.

## Artefatos
Notebook/script reprodutível, model card, resultados em `reports/fine_tuning.md`.
