# Veredito das hipóteses — fim da F0

Todos os números vêm de `reports/numeros_eda.json`, gerado por `make eda` sobre as 2.239.998
reviews da camada `processed`. Figuras em `reports/figuras/`.

| Hipótese | Veredito |
|---|---|
| H1 — aspectos revelam causas por trás da nota | ⏳ pendente de F1 |
| H2 — reviews longas são as mais informativas | ✅ confirmada, com inversão importante |
| H3 — gêneros diferem nos aspectos citados | ⏳ pendente de F1 |
| H4 — polarização por livro/autor | ⚠️ existe, mas é minoria |
| H5 — divergência entre nota e sentimento | ⏳ pendente de F1 |
| H6 — minoria de usuários concentra as avaliações | ✅ confirmada |
| H7 — existe tendência temporal | ✅ confirmada (curva em U), ❌ na causa atribuída |

---

## H2 — Reviews longas são as mais informativas ✅ (com inversão)
**Figura:** `03_comprimento_vs_nota.png`

Comprimento mediano da review, por nota:

| nota | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| caracteres | 515 | 616 | **645** | 597 | **459** |

O comprimento **não cresce com a nota — faz um arco**. Quem dá 3 escreve mais (645) do que quem
dá 5 (459), e a nota 5 é a mais curta de todas, abaixo até da nota 1.

**Consequência para a spec 04:** a leitura intuitiva da hipótese ("resenhista entusiasmado é bom
candidato a entrevista") está errada. Quem argumenta é o público do meio — notas 2 a 4. O ranking
de candidatos não deve privilegiar 5 estrelas, e como a base não tem helpfulness, o comprimento é
o proxy de profundidade disponível.

## H4 — Polarização por livro/autor ⚠️ existe, mas é minoria
**Figura:** `02_notas.png`

A distribuição **global** não é bimodal, é fortemente assimétrica: 1.340.287 das 2.239.998 notas
são 5 (59,8%).

Definição operacional de livro polarizado (em `src/bri/data/eda.py`): pelo menos 20 reviews, com
≥20% de notas 1 **e** ≥20% de notas 5 ao mesmo tempo.

- livros com ≥20 reviews: **19.357**
- destes, polarizados: **1.316 (6,8%)**

A polarização é real e mensurável, mas é fenômeno de minoria — não serve como lente principal.
Se ela sinaliza **risco** ou **nicho engajado**, como a hipótese afirma, é pergunta que esta fase
não responde: exige saber *sobre o quê* as pessoas divergem, o que só a extração de aspectos (F1)
entrega. Essa metade fica pendente.

## H6 — Minoria de usuários concentra as avaliações ✅
**Figura:** `01_volume.png`

- usuários identificados: **1.008.972** (para 1.686.932 reviews atribuídas)
- o **1% mais ativo concentra 20,2%** das reviews atribuídas
- apenas **19 usuários** passam de 500 reviews

Cauda longa clássica, confirmada. **Viés a controlar:** qualquer média por usuário é dominada por
quem avaliou uma vez só, e qualquer ranking de "top usuários" é dominado por um punhado de
hiperativos. As duas leituras precisam de corte explícito.

## H7 — Tendência temporal ✅ na tendência, ❌ na causa
**Figura:** `06_evolucao_temporal.png`

A tendência existe, mas **não é uma alta recente — é uma curva em U** ao longo de 17 anos:

| 1996 | 1998 | 2000 | 2002 | **2004** | 2006 | 2008 | 2010 | 2012 | 2013 |
|---|---|---|---|---|---|---|---|---|---|
| 4,64 | 4,34 | 4,21 | 4,13 | **4,06** | 4,16 | 4,18 | 4,18 | 4,26 | 4,39 |

Queda contínua de 1996 até o fundo em **2004 (4,06)**, seguida de recuperação gradual. Duas
ressalvas que o gráfico deixa ver e que mudam a leitura:

- **1996 e 1997 têm volume ínfimo** (6.233 e 39.232 reviews). A média alta do começo da série
  repousa em pouca gente e não deve ser lida como "o público era mais generoso".
- **2013 é ano parcial.** A base termina em 04/03/2013, com 85.914 reviews contra 177.434 em
  2012. O salto para 4,39 cobre dois meses, não um ano — é artefato de recorte, não tendência.
  Sem ele, a recuperação recente é bem mais modesta.

Sobre a causa que a hipótese atribui — "novas edições/adaptações mudam percepção" — **o dado não
sustenta**. Um movimento lento e simultâneo em toda a base, ao longo de uma década, é mais
compatível com mudança na composição de quem avalia do que com o efeito de lançamentos
específicos. A tendência está confirmada; a explicação proposta, não.

---

## Pendentes de F1 ⏳

Não é possível dar veredito nesta fase: dependem de aspectos e sentimento, que só existem depois
do enriquecimento. Deixo escrita a pergunta que a F1 precisa fechar:

- **H1** — a nota média esconde problemas específicos? *Pergunta para a F1:* nos livros com nota
  média alta, os aspectos extraídos revelam reclamações recorrentes (tradução, edição física,
  ritmo) que a nota não mostra?
- **H3** — gêneros diferem nos aspectos citados? *Pergunta para a F1:* a distribuição de aspectos
  por `genre_stats` difere de forma significativa entre os gêneros de maior volume?
- **H5** — nota e sentimento divergem? *Pergunta para a F1:* em que fração das reviews o
  sentimento do texto contradiz a nota dada, e isso se concentra em algum gênero ou faixa?

---

## Achado fora das hipóteses: a nota bayesiana não é detalhe

O checklist pedia nota bayesiana "para evitar ranking enviesado por poucos votos". O efeito é
maior do que o rótulo sugere — os dois rankings não têm **nenhum** autor em comum:

| por média simples | | por nota bayesiana | |
|---|---|---|---|
| Isabel Ashdown | 5,00 (n=**1**) | E.B. Sledge | 4,86 (n=676) |
| Dianne Young | 5,00 (n=6) | Toni Weschler | 4,79 (n=1060) |
| Katharine MacDonogh | 5,00 (n=**1**) | Immaculee Ilibagiza | 4,79 (n=668) |

Ordenar `author_stats` por `nota_media` produz um ranking de autores com uma única avaliação.
Qualquer número de "melhores autores" que vá para slide precisa usar `nota_bayesiana` — está
registrado em `reports/data_dictionary.md`.

## Qualidade da base (checklist da spec 01)
**Figura:** `04_qualidade.png`

| problema | reviews |
|---|---|
| texto nulo | 8 |
| texto com menos de 20 caracteres | 728 |
| sem autoria (`user_hash` nulo) | 553.066 (24,7%) |
| data inválida (anterior a 1996) | 276 |
| usuários com mais de 500 reviews | 19 |

Nada aqui compromete a base. O único número grande é a ausência de autoria, que já está
documentada como limite do ranking de entrevistas (spec 04). Idioma ficou fora desta fase por
decisão registrada em `specs/DECISIONS.md`.
