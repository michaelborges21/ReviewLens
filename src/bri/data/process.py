"""Limpa o interim, deduplica e carrega as tabelas do DuckDB que o agente consulta por SQL."""

import hashlib
import html
import os
from pathlib import Path

import duckdb
import polars as pl

from bri.data.ingest import INTERIM_DIR

PROCESSED_DIR = Path("data/processed")
BANCO = PROCESSED_DIR / "reviewlens.duckdb"


def limpar_texto(df: pl.DataFrame, colunas: list[str]) -> pl.DataFrame:
    """Desfaz entidades HTML; nulos passam intactos."""
    return df.with_columns(
        [pl.col(coluna).map_elements(html.unescape, return_dtype=pl.Utf8) for coluna in colunas]
    )


def deduplicar_reviews(reviews: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Remove a mesma review replicada em edições diferentes, guardando quais edições eram.

    Identificado e anônimo usam chaves diferentes de propósito: tratar os user_id nulos como um
    usuário só colapsaria 175.412 reviews anônimas distintas que apenas compartilham o texto.
    """
    identificadas = reviews.filter(pl.col("user_id").is_not_null()).with_columns(
        pl.col("review_id").min().over(["user_id", "review_text"]).alias("review_canonica")
    )
    anonimas = reviews.filter(pl.col("user_id").is_null()).with_columns(
        pl.col("review_id").min().over(["book_id", "review_text"]).alias("review_canonica")
    )
    todas = pl.concat([identificadas, anonimas])

    edicoes = todas.select(pl.col("review_canonica").alias("review_id"), "book_id").unique()
    canonicas = todas.filter(pl.col("review_id") == pl.col("review_canonica")).drop(
        "review_canonica"
    )
    return canonicas, edicoes


def pseudonimizar_usuario(reviews: pl.DataFrame) -> pl.DataFrame:
    """Troca user_id por hash salgado e descarta profile_name — PII só existe na camada raw."""
    salt = os.environ.get("USER_ID_HASH_SALT")
    if not salt:
        raise RuntimeError(
            "USER_ID_HASH_SALT não definido — copie .env.example para .env e preencha. "
            "Pseudonimização não tem fallback silencioso (spec 05)."
        )
    return reviews.with_columns(
        pl.col("user_id")
        .map_elements(
            lambda user_id: hashlib.sha256(f"{salt}{user_id}".encode()).hexdigest(),
            return_dtype=pl.Utf8,
        )
        .alias("user_hash")
    ).drop("user_id", "profile_name")


def montar_book_authors(books: pl.DataFrame) -> pl.DataFrame:
    """Normaliza a lista de autores em pares (livro, autor), consultáveis por SQL."""
    return (
        books.explode("authors", empty_as_null=True)
        .select("title", pl.col("authors").alias("author"))
        .drop_nulls("author")
        .unique()
    )


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    livros = limpar_texto(pl.read_parquet(INTERIM_DIR / "books.parquet"), ["description"])
    reviews = limpar_texto(
        pl.read_parquet(INTERIM_DIR / "reviews.parquet"), ["review_text", "review_title"]
    )
    reviews, edicoes = deduplicar_reviews(reviews)

    tabelas = {
        "reviews": pseudonimizar_usuario(reviews),
        "books": livros,
        "book_authors": montar_book_authors(livros),
        "review_editions": edicoes,
    }
    BANCO.unlink(missing_ok=True)
    with duckdb.connect(str(BANCO)) as con:
        for nome, df in tabelas.items():
            con.register("entrada", df)
            con.execute(f"CREATE TABLE {nome} AS SELECT * FROM entrada")


if __name__ == "__main__":
    main()
