"""Tabelas de agregação por usuário, autor e gênero — base do ranking e dos slides."""

import duckdb

from bri.data.process import BANCO

# Peso do prior bayesiano: um autor com 2 reviews 5 estrelas não pode liderar o ranking.
# Com 50, um autor só se descola da média global depois de umas dezenas de avaliações.
PRIOR_BAYESIANO = 50


def criar_users_agg(con: duckdb.DuckDBPyConnection) -> None:
    """Uma linha por usuário identificado; anônimos (user_hash nulo) ficam de fora."""
    con.execute("""
        CREATE OR REPLACE TABLE users_agg AS
        SELECT user_hash,
               count(*)                    AS n_reviews,
               avg(rating)                 AS nota_media,
               median(length(review_text)) AS comprimento_mediano,
               min(reviewed_at)            AS primeira_review,
               max(reviewed_at)            AS ultima_review
        FROM reviews
        WHERE user_hash IS NOT NULL
        GROUP BY user_hash
    """)


def criar_author_stats(con: duckdb.DuckDBPyConnection, prior: int = PRIOR_BAYESIANO) -> None:
    """Nota bayesiana puxa autores com poucas reviews para a média global."""
    con.execute(
        """
        CREATE OR REPLACE TABLE author_stats AS
        WITH media_global AS (SELECT avg(rating) AS c FROM reviews),
        por_autor AS (
            SELECT ba.author,
                   count(DISTINCT ba.title) AS n_livros,
                   count(r.review_id)       AS n_reviews,
                   avg(r.rating)            AS nota_media
            FROM book_authors ba
            LEFT JOIN reviews r ON r.title = ba.title
            GROUP BY ba.author
        )
        SELECT author, n_livros, n_reviews, nota_media,
               (n_reviews::DOUBLE / (n_reviews + ?)) * coalesce(nota_media, 0)
             + (?::DOUBLE / (n_reviews + ?)) * (SELECT c FROM media_global) AS nota_bayesiana
        FROM por_autor
        """,
        [prior, prior, prior],
    )


def criar_genre_stats(con: duckdb.DuckDBPyConnection) -> None:
    """Um livro em duas categorias conta nas duas — por isso a soma passa do total de livros."""
    con.execute("""
        CREATE OR REPLACE TABLE genre_stats AS
        WITH livro_categoria AS (
            SELECT title, unnest(categories) AS categoria
            FROM books
            WHERE categories IS NOT NULL
        )
        SELECT lc.categoria,
               count(DISTINCT lc.title)      AS n_livros,
               count(r.review_id)            AS n_reviews,
               avg(r.rating)                 AS nota_media,
               median(length(r.review_text)) AS comprimento_mediano
        FROM livro_categoria lc
        LEFT JOIN reviews r ON r.title = lc.title
        GROUP BY lc.categoria
    """)


def main() -> None:
    with duckdb.connect(str(BANCO)) as con:
        criar_users_agg(con)
        criar_author_stats(con)
        criar_genre_stats(con)


if __name__ == "__main__":
    main()
