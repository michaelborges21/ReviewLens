# Spec 01 — Dados e EDA
Status: rascunho

## Fontes (hipótese — confirmar ao baixar)
- `Books_rating.csv`: `Id, Title, Price, User_id, profileName, review/helpfulness, review/score, review/time, review/summary, review/text`
- `books_data.csv`: `Title, description, authors, image, previewLink, publisher, publishedDate, infoLink, categories, ratingsCount`

Se o schema real divergir, **atualize esta spec antes de seguir**.

## Pipeline de ingestão (`src/bookinsights/data/`)
1. Leitura com DuckDB direto do CSV → Parquet em `data/interim/`.
2. Validação: schema Pandera/Pydantic, contagem de nulos, tipos. Relatório em `reports/data_quality.md`.
3. Limpeza:
   - `review/helpfulness` "a/b" → `helpful_yes`, `helpful_total`, `helpful_ratio` (com suavização bayesiana: `(a+1)/(b+2)`).
   - `review/time` epoch → datetime.
   - `authors` e `categories` (strings de lista) → arrays normalizados.
   - HTML entities, espaços, textos vazios.
   - Detecção de idioma (`fasttext lid` ou `lingua`) → coluna `lang`.
4. **Dedupe (H4):** mesmo `(User_id, hash(texto normalizado))` em `Id`s diferentes → manter 1, registrar mapeamento edição→obra (`work_id`).
5. Join reviews ↔ livros por `Title` normalizado; medir taxa de match e registrar órfãos.
6. Saída: `data/processed/reviews.parquet`, `books.parquet`, `users.parquet` (agregados por usuário, `User_id` hasheado).

## EDA (notebook `01_eda.ipynb` narrativo, lógica em `analytics/`)
Cada seção responde uma hipótese da spec 00 e termina com **"E daí?" para o negócio** (1 frase).
- Volume: reviews por ano, por gênero, por autor (cauda longa).
- Distribuição de notas (H1); nota média vs % negativos por livro.
- Tamanho de texto, helpfulness (H3), Pareto de usuários (H7).
- Preço × nota por gênero (H8).
- Top autores/gêneros por volume e por "nota ajustada" (média bayesiana, para não premiar livro com 3 reviews 5★).
- Idiomas, duplicatas, qualidade do join.

## Regras
- EDA na base completa via DuckDB (é barato). LLM só em amostra (spec 02).
- Todo gráfico salvo em `presentation/figures/` com nome estável — o deck consome daqui.
- Métrica de ranking sempre com intervalo de confiança ou shrinkage; nunca média crua com n pequeno.

## Critérios de aceite
- [ ] Ingestão idempotente, testada, < 10 min em laptop.
- [ ] Relatório de qualidade de dados gerado.
- [ ] Notebook roda de ponta a ponta (`nbconvert --execute`) sem lógica própria.
