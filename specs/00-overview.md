# 00 — Visão geral, hipóteses e roadmap
Status: aprovada (v0.1) · Dono: Michael · Revisar a cada fase concluída · F0 concluída; o
entregável de código de F1 a F4 está completo, mas quatro dos cinco critérios de saída ainda não
foram cumpridos — ver "O que falta, e por quê" logo abaixo do roadmap.

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

Cada hipótese termina como: ✅ confirmada / ❌ refutada / ⚠️ inconclusiva — com gráfico em
`reports/`. **H1, H3 e H5 dependem do enriquecimento** (aspectos e sentimento não existem antes
da F1): na EDA elas ficam como ⏳ pendente e só recebem veredito ao fim da F1. Prometer os sete
vereditos na EDA seria prometer o que o dado dessa fase não sustenta.

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

## O que falta, e por quê

Vale a pena ser direto sobre isso, porque a resposta muda conforme a pergunta.

**O sistema funciona ponta a ponta e é demonstrável.** Uma pergunta em português vira resposta
com citação verificável; há 138 resumos por entidade, 20 temas, ranking por taxa encolhida,
busca híbrida e guardrails que barram injeção de instrução em texto de leitor. Nesse sentido, o
MVP está de pé.

**Mas quatro dos cinco critérios de saída deste roadmap ainda não foram cumpridos**, e nenhum
deles depende de escrever mais código:

| Fase | O que falta | Natureza do trabalho |
|---|---|---|
| F1 | métricas da spec 06 acima do mínimo | depende do golden set abaixo |
| F2 | golden set ≥ meta | **rotular 200 avaliações à mão** |
| F3 | lista de entrevista validada por humano | aprovar uma lista de verdade na tela |
| F4 | revisão de storytelling | ler os slides e preencher 3 premissas de negócio |

O caso mais pesado é o golden set. As 200 avaliações já estão selecionadas e prontas numa
planilha (`reports/evals/golden_aspectos.csv`), com as colunas de resposta em branco; o script
que compara o gabarito com a extração já existe e roda. O que falta é a parte que nenhuma
ferramenta faz por nós: alguém ler avaliação por avaliação e dizer qual aspecto e qual sentimento
estão ali. É trabalho braçal, demorado e que exige atenção contínua — e é justamente por isso que
não dá para terceirizar ao próprio modelo, porque usar a IA para avaliar a IA seria circular e
não provaria nada.

**Por decisão consciente, isso fica para uma etapa futura.** No momento não há tempo nem mão de
obra disponível para a rotulagem manual, e forçá-la agora significaria ou fazer às pressas — o
que produziria um gabarito ruim, pior que gabarito nenhum — ou travar todo o resto do projeto
esperando por ela. Preferimos entregar o sistema funcionando, com os limites escritos, e deixar a
medição formal para quando houver disponibilidade real de fazê-la com o cuidado que ela exige.

**Enquanto isso, o que se sabe de verdade sobre qualidade** está medido e é reproduzível: 97,0%
de citação literal verificada sobre os 45.847 aspectos, gradiente de sentimento coerente
(negatividade caindo de 94,3% na nota 1 para 4,0% na nota 5), red-team bloqueando os casos
críticos, e zero citação atribuída à entidade errada nos 138 resumos. Isso mede **consistência**,
não **acerto** — a diferença é real e está registrada, para ninguém confundir uma coisa com a
outra ao ler estes números.

As fases F2 e F3 **não** estão marcadas como concluídas na tabela acima, e isso é deliberado:
marcá-las contradiria o critério que esta própria spec define. Um roadmap que se declara cumprido
sem cumprir o que escreveu deixa de servir para qualquer coisa.

## Métricas de sucesso (produto)
- Tempo de resposta a uma pergunta típica: de horas (manual) → < 1 min.
- Respostas analíticas 100% corretas (verificáveis por SQL).
- Respostas textuais com ≥ 90% de afirmações suportadas por citação (faithfulness).

## Fora de escopo (por enquanto)
Dados em tempo real, autenticação multiusuário, deploy em produção.
