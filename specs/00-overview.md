# 00 — Visão geral, hipóteses e roadmap
Status: rascunho v0.1 · Dono: Michael · Revisar a cada fase concluída

## Problema
Analistas de uma editora exploram avaliações de livros manualmente. É lento, não escala e depende de leitura humana.

## Personas e jobs-to-be-done
| Persona | Pergunta típica | Módulo |
|---|---|---|
| Analista editorial | "Como está a performance do autor X nos últimos 5 anos?" | SQL tool + resumo |
| Gestor de gênero | "O que os leitores mais criticam em fantasia?" | aspectos + sumarização |
| Pesquisa/UX | "Quem são bons candidatos para entrevista sobre o livro Y?" | busca de usuários + HITL |
| Qualquer um | Pergunta livre | Agente Q&A |

## Hipóteses iniciais (a validar na EDA — ver 01)
- **H1** A nota média esconde problemas específicos; aspectos extraídos do texto revelam causas (ritmo, final, tradução, edição física).
- **H2** Reviews longas são as mais informativas (proxy de profundidade — a base não tem
  helpfulness) → melhores candidatos a entrevista.
- **H3** Gêneros diferem nos aspectos mais citados (ex.: técnicos → clareza; ficção → personagens).
- **H4** Polarização de notas (bimodal) por livro/autor é sinal de risco ou de nicho engajado.
- **H5** Há divergência entre nota e sentimento do texto em uma fração relevante das reviews.
- **H6** Uma minoria de usuários prolíficos concentra boa parte das avaliações (viés a controlar).
- **H7** Existe tendência temporal (novas edições/adaptações mudam percepção).

Cada hipótese termina a EDA como: ✅ confirmada / ❌ refutada / ⚠️ inconclusiva — com gráfico em `reports/`.

## Roadmap
| Fase | Entrega | Critério de saída |
|---|---|---|
| F0 Fundação | repo, specs, ingestão, EDA | hipóteses avaliadas, dataset limpo em DuckDB |
| F1 Enriquecimento | sentimento, aspectos (amostra), tópicos, resumos hierárquicos | métricas de 06 acima do mínimo |
| F2 Q&A MVP | roteador + SQL tool + RAG com citações + UI | golden set ≥ meta |
| F3 Entrevistas | ranking de usuários + HITL + export | lista validada por humano |
| F4 Apresentação | slides a–j + estimativa de impacto | revisão de storytelling |
| F5 (opcional) | fine-tuning/destilação | ganho de custo com perda de qualidade aceitável |
| Futuro | alertas de reputação, novos dados (redes sociais), dashboard contínuo, multilíngue | — |

## Métricas de sucesso (produto)
- Tempo de resposta a uma pergunta típica: de horas (manual) → < 1 min.
- Respostas analíticas 100% corretas (verificáveis por SQL).
- Respostas textuais com ≥ 90% de afirmações suportadas por citação (faithfulness).

## Fora de escopo (por enquanto)
Dados em tempo real, autenticação multiusuário, deploy em produção.
