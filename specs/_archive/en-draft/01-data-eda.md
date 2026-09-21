# 01 — Dados e Análise Exploratória
Status: rascunho v0.1

## Fontes
Duas tabelas (provável dataset "Amazon Books Reviews" do Kaggle — **confirmar ao baixar**):
- `ratings`: id do livro, título, preço, user_id, nome de perfil, helpfulness ("x/y"), nota, timestamp, título da review, texto.
- `books`: título, descrição, autores, editora, data de publicação, categorias, contagem de avaliações.
> Se o schema real diferir, atualize esta seção antes de escrever código.

## Pipeline
`raw (csv, imutável)` → `interim (parquet tipado)` → `processed (DuckDB)`

Limpeza:
- Tipos corretos; timestamp unix → datetime; helpfulness → `helpful_yes`, `helpful_total`, `helpful_ratio`.
- HTML unescape, normalização de espaços; manter texto original em coluna separada.
- Duplicatas exatas e quase-duplicatas (mesmo usuário + mesmo texto em edições diferentes).
- Join por título é frágil (títulos repetidos/edições): documentar taxa de match e estratégia.
- Listas em string (autores, categorias) → arrays normalizados; tabela `book_authors`.
- `user_id` pseudonimizado (hash com salt em `.env`) na camada processed. `profileName` só na raw.

## Amostragem
Base grande → etapas com LLM usam **amostra estratificada** (gênero × faixa de nota × período), seed fixa, tamanho justificado por custo. Documentar em `reports/sampling.md`.

## Checklist de EDA (cada item gera figura/tabela em `reports/`)
- Volume por ano, gênero, autor; cauda longa de livros e usuários (H6).
- Distribuição de notas global e por gênero; bimodalidade (H4).
- Comprimento de texto vs nota vs helpfulness (H2).
- Qualidade: nulos, idioma, textos vazios/curtos, spam.
- Top autores por volume e por nota bayesiana (evitar ranking enviesado por poucos votos).
- Evolução temporal da nota por autor/gênero (H7).

## Saída
Tabelas DuckDB: `reviews`, `books`, `book_authors`, `users_agg`, `author_stats`, `genre_stats`.
Dicionário de dados em `reports/data_dictionary.md` (também usado como contexto para o gerador de SQL).
