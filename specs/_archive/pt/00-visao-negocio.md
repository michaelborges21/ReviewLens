# Spec 00 — Visão, negócio e hipóteses
Status: rascunho

## Problema
Analistas da editora exploram reviews manualmente. Consequências: lentidão, cobertura baixa (leem dezenas de reviews de um universo de milhões), viés de seleção (leem os mais recentes ou os mais extremos) e nenhuma rastreabilidade.

## Personas e jobs-to-be-done
| Persona | Pergunta típica | O que precisa receber |
|---|---|---|
| Analista de catálogo | "Como está o autor X nos últimos 5 anos?" | métricas + tendência + resumo de pontos fortes/fracos com citações |
| Editor de aquisição | "Que gênero está subindo e o que leitores reclamam?" | comparativo entre gêneros + temas emergentes |
| Pesquisa/marketing | "Quem eu entrevisto sobre ficção científica?" | shortlist ranqueada de leitores com justificativa, aprovada por humano |

## Objetivo do produto
Reduzir o tempo de uma exploração típica de **horas para minutos**, com **números corretos e opiniões rastreáveis** (toda afirmação qualitativa cita reviews).

## Hipóteses (validar na EDA — spec 01)
| ID | Hipótese | Como testar | Por que importa |
|---|---|---|---|
| H1 | Notas têm distribuição em J (inflação de 5 estrelas): a média de estrelas discrimina mal livros | histograma, média vs % de notas ≤2 | justifica usar texto, não só nota |
| H2 | Há divergência nota × texto (ex.: 4★ com texto crítico) | sentimento do texto vs score | texto traz sinal que a nota esconde |
| H3 | Reviews "úteis" (helpfulness) são mais longos e mais específicos | correlação helpfulness × tamanho/especificidade | base do ranking de candidatos a entrevista |
| H4 | Reviews estão duplicados entre edições do mesmo livro | dedupe por (user, texto) entre Ids | evita inflar métricas |
| H5 | Gêneros diferem nos aspectos criticados (ex.: ritmo em thriller, rigor em não-ficção) | aspectos extraídos × categoria | insight acionável por gênero |
| H6 | Percepção muda no tempo (drift) para autores com série longa | série temporal de sentimento por autor | alerta para editora |
| H7 | Uma minoria de leitores produz a maioria dos reviews úteis | curva de Pareto por usuário | viabiliza painel de leitores |
| H8 | Preço tem relação fraca com nota | correlação + controle por gênero | evita decisão errada de pricing |

Hipóteses que falharem **também entram na apresentação** (mostra rigor).

## Estimativa de impacto (item i)
Modelo paramétrico, com cenários; **todas as premissas explícitas e marcadas para validação com o cliente**:

```
horas_economizadas_mes = n_analistas × horas_exploracao_mes × taxa_reducao
valor_mes = horas_economizadas_mes × custo_hora
custo_mes = custo_infra + custo_llm (tokens medidos no eval)
ROI = (valor_mes − custo_mes) / custo_mes
```
- Cenários pessimista / base / otimista para `taxa_reducao` (ex.: 40% / 65% / 85%) e `horas_exploracao_mes`.
- `taxa_reducao` estimada por **teste cronometrado**: 5 tarefas reais feitas manualmente vs com a ferramenta (spec 07).
- Impactos de segunda ordem (quantificar só se houver base, senão listar qualitativamente): decisões de aquisição mais rápidas, detecção precoce de queda de percepção, custo de recrutamento de entrevistas.
- Gráfico de sensibilidade (tornado) mostrando qual premissa mais mexe no ROI.

## Fora de escopo (MVP)
Coleta de novos dados, recomendação de livros, contato automatizado com leitores, dashboards em produção.

## Critérios de aceite
- [ ] Cada hipótese tem resultado (confirmada / refutada / inconclusiva) com gráfico.
- [ ] Impacto com fórmula, premissas, 3 cenários e sensibilidade.
