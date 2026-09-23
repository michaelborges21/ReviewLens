# Dicionário de dados — `data/processed/reviewlens.duckdb`

Gerado por `make data` (`src/bri/data/process.py`). Também serve de contexto para o gerador de
SQL do agente (spec 04). Números medidos na carga de 2026-09-22.

## `reviews` (2.239.998 linhas)
Uma linha por review **canônica** — duplicatas de edição já removidas (ver `review_editions`).

| Coluna | Tipo | Nota |
|---|---|---|
| `review_id` | UINTEGER | Gerado na ingestão (a fonte não tem id). Estável: segue a ordem do CSV, que é imutável. |
| `book_id` | VARCHAR | ISBN/ASIN da edição em que a review foi coletada. |
| `title` | VARCHAR | Título do livro. Chave de junção com `books`. |
| `price` | DOUBLE | Nulo em 84% — não usar como métrica principal. |
| `user_hash` | VARCHAR(64) | SHA-256 salgado do `user_id`. Nulo em 24,7% — 553.066 reviews sem autoria na fonte. |
| `rating` | DOUBLE | 1.0 a 5.0, sem nulos. |
| `reviewed_at` | TIMESTAMP | 21 reviews têm `time = -1` na fonte e caem em 1969 — filtrar na análise. |
| `review_title` | VARCHAR | Campo `summary` da fonte. |
| `review_text` | VARCHAR | Entidades HTML desfeitas (um passe). Mediana 516 caracteres. |

`profile_name` e `user_id` **não existem aqui** de propósito: PII só pode viver em `data/raw/`.

## `books` (212.404 linhas)
Uma linha por título; `title` é único.

| Coluna | Tipo | Nota |
|---|---|---|
| `title` | VARCHAR | Chave. 1 linha com título nulo. |
| `description` | VARCHAR | Nulo em 32%. Entidades HTML desfeitas. |
| `authors` | VARCHAR[] | Lista. Nulo em 15%. Versão normalizada em `book_authors`. |
| `publisher` | VARCHAR | Nulo em 36%. |
| `published_date` | VARCHAR | Formato irregular na fonte ("1996", "2005-01-01"): continua texto. |
| `categories` | VARCHAR[] | Lista. 10.883 categorias distintas; "Fiction" domina com 23.419 livros. |
| `ratings_count` | BIGINT | Nulo em 77%. |

## `book_authors` (230.103 linhas)
Pares livro-autor, para agregação por autor sem mexer em lista. 153.082 autores distintos.

| Coluna | Tipo |
|---|---|
| `title` | VARCHAR |
| `author` | VARCHAR |

## `review_editions` (2.969.932 linhas)
Liga a review canônica a **todas** as edições (`book_id`) em que ela apareceu na fonte. Existe
porque ~25% da base era a mesma review replicada entre edições: remover sem registrar perderia
qual edição recebeu a avaliação.

| Coluna | Tipo |
|---|---|
| `review_id` | UINTEGER (review canônica) |
| `book_id` | VARCHAR |

## Cuidados ao consultar
- **Contar reviews por livro**: usar `review_editions` se a pergunta é sobre a edição; usar
  `reviews` se é sobre conteúdo distinto. Contar `reviews` por `book_id` subestima edições.
- **Junção `reviews` × `books`**: por `title`. Casa 100%, mas 7.611 títulos têm mais de um
  `book_id` — a junção agrega edições.
- **Usuários**: `user_hash` nulo não é um usuário; são 24,7% de reviews sem autoria na fonte.
- **Texto**: 37 reviews ainda contêm algo parecido com entidade HTML. São duplamente codificadas
  na origem (`&amp;quot;`), e o unescape é de passe único de propósito: repetir passes destruiria
  um `&quot;` que o resenhista tenha escrito literalmente.
