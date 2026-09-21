# Spec 08 — Fine-tuning de modelo open source (opcional, item j)
Status: rascunho

## Tese de negócio
Enriquecer 3M reviews com LLM grande é caro/lento. **Destilar** a tarefa de extração (spec 02) para um modelo pequeno torna a base completa viável e o pipeline recorrente barato.

## Tarefa
Entrada: review. Saída: `ReviewEnrichment` (JSON). Mesma interface do pipeline → troca de modelo = troca de config.

## Dados
- Professor: melhor LLM disponível rotula 5–10k reviews estratificados (fora do eval set).
- Filtro de qualidade: só exemplos que passam schema + evidência-substring; amostra de 200 revisada à mão.
- Split 90/10 (validação), eval final no conjunto humano da spec 07.

## Modelo e treino
- Base: modelo instruct pequeno open source (1–4B parâmetros; escolher o melhor disponível na data e registrar em ADR).
- QLoRA 4-bit (`peft` + `trl` SFT), rank 16, 2–3 épocas; roda em GPU única (Colab/Kaggle) — registrar hardware.
- Inferência com saída restrita a JSON Schema (constrained decoding) para garantir validade.

## Comparação obrigatória (slide)
| Modelo | F1 aspectos | kappa sentimento | % JSON válido | custo/1k reviews | latência/review |
|---|---|---|---|---|---|
| Base zero-shot | | | | | |
| Base few-shot | | | | | |
| **Fine-tuned** | | | | | |
| Professor (LLM grande) | | | | | |

Conclusão esperada (a validar): fine-tuned próximo do professor a uma fração do custo → justifica cobrir a base inteira.

## Critérios de aceite
- [ ] Tabela preenchida; pesos do adapter publicados (HF Hub) ou instrução de reprodução.
- [ ] Se o fine-tuned não superar o few-shot, **apresentar mesmo assim** com a análise do porquê.
