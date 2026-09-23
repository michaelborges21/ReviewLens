# 01 — Dados e Análise Exploratória
Status: rascunho v0.1

## Fontes
Dataset "Amazon Books Reviews" do Kaggle, duas tabelas — **schema confirmado em `data/raw/`**:
- `books_data.csv` (~212k linhas): `Title, description, authors, image, previewLink, publisher,
  publishedDate, infoLink, categories, ratingsCount`.
- `Books_rating.csv` (~3M linhas): `Id (isbn do livro), Title, Price, User_id, profileName,
  score, time, summary, text`. **Sem coluna de helpfulness** — a fonte real não tem o campo
  "x/y" que uma versão anterior desta spec assumia. Também não existe id de review; é gerado
  sequencialmente na ingestão.

## Pipeline
`raw (csv, imutável)` → `interim (parquet tipado)` → `processed (DuckDB)`

Limpeza:
- Tipos corretos; timestamp unix → datetime.
- HTML unescape (`&quot;` em 313k reviews). **Sem normalização de espaços e sem coluna de texto
  original**: medi zero espaços duplos e zero tags em 3M de reviews, e o texto pré-unescape já
  está preservado em `data/interim/` — duplicar a maior coluna da base não se paga.
- **Duplicatas: ~25% da base.** 3.000.000 → 2.239.998. (Deduplicar o texto cru daria 2.240.168;
  como o unescape roda **antes**, 170 pares que só diferiam na codificação HTML colidem e se
  juntam — é o mesmo conteúdo, devem mesmo colapsar.) Chaves diferentes por grupo, de
  propósito: `(user_id, review_text)` para identificados (remove 751.142) e
  `(book_id, review_text)` para anônimos (remove 8.690). Tratar os `user_id` nulos como um
  usuário só colapsaria 175.412 reviews anônimas distintas. A linha canônica é o menor
  `review_id` do grupo, e `review_editions` guarda todas as edições que a review cobria.
- Join por título é frágil (títulos repetidos/edições): documentar taxa de match e estratégia.
- Listas em string (autores, categorias) → arrays normalizados; tabela `book_authors`.
- `user_id` pseudonimizado (hash com salt em `.env`) na camada processed. `profileName` só na raw.

## Qualidade medida na ingestão (medido em 2026-09-22, 3M reviews / 212.404 livros)
Números reproduzíveis rodando `make data` e consultando `data/interim/*.parquet`.

- **Join por título: 100% de match.** `books.title` é único (212.404 linhas, 212.404 títulos) e
  todos os 212.403 títulos distintos das reviews casam. O risco não é match, é **granularidade**:
  7.611 títulos têm mais de um `book_id` (edições diferentes — "Pride and Prejudice" tem 11).
  Join por título agrega edições; para análise por edição, usar `book_id`.
- **`user_id` nulo em 18,7%** (561.787 reviews) — limita o ranking de candidatos a entrevista
  (spec 04), que só pode considerar os 81,3% atribuíveis.
- **`price` nulo em 84%** — análise de preço é inviável como métrica principal.
- **21 reviews com `time = -1`** (viram 1969-12-31) e 288 anteriores a 1996, no dado bruto. A
  ingestão preserva fielmente; filtrar é decisão da EDA/camada processed, não da ingestão.
- **`review_text`**: mediana 516 caracteres, média 823, máx. 32.576; 834 com menos de 20
  caracteres e 8 nulos. Base suficiente para usar comprimento como proxy de profundidade (H2).
- `description` nulo em 32%, `publisher` em 36%, `ratings_count` em 77% dos livros.

## Amostragem
Base grande → etapas com LLM usam **amostra estratificada** (gênero × faixa de nota × período), seed fixa, tamanho justificado por custo. Documentar em `reports/sampling.md`.

## Checklist de EDA (cada item gera figura/tabela em `reports/`)
- Volume por ano, gênero, autor; cauda longa de livros e usuários (H6).
- Distribuição de notas global e por gênero; bimodalidade (H4).
- Comprimento de texto vs nota (H2).
- Qualidade: nulos, idioma, textos vazios/curtos, spam.
- Top autores por volume e por nota bayesiana (evitar ranking enviesado por poucos votos).
- Evolução temporal da nota por autor/gênero (H7).

## Saída
Tabelas DuckDB: `reviews`, `books`, `book_authors`, `users_agg`, `author_stats`, `genre_stats`.
Dicionário de dados em `reports/data_dictionary.md` (também usado como contexto para o gerador de SQL).
