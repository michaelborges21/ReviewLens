"""Lê os CSVs brutos da Amazon Books Reviews e grava parquet tipado em data/interim/."""

import ast
from pathlib import Path

import polars as pl

RAW_DIR = Path("data/raw")
INTERIM_DIR = Path("data/interim")


def _parse_lista_python(valor: str | None) -> list[str]:
    """Converte "['Fulano', 'Beltrano']" (repr de lista Python) em list[str]."""
    if not valor:
        return []
    try:
        itens = ast.literal_eval(valor)
    except (ValueError, SyntaxError):
        return []
    if not isinstance(itens, list):
        return []
    return [str(item) for item in itens]


def load_books(path: Path = RAW_DIR / "books_data.csv") -> pl.DataFrame:
    """Lê books_data.csv e tipa authors/categories como lista, descarta colunas só de URL."""
    bruto = pl.read_csv(path, infer_schema_length=0)
    return bruto.select(
        pl.col("Title").alias("title"),
        pl.col("description"),
        pl.col("authors").map_elements(_parse_lista_python, return_dtype=pl.List(pl.Utf8)),
        pl.col("publisher"),
        pl.col("publishedDate").alias("published_date"),
        pl.col("categories").map_elements(_parse_lista_python, return_dtype=pl.List(pl.Utf8)),
        pl.col("ratingsCount")
        .cast(pl.Float64, strict=False)
        .cast(pl.Int64, strict=False)
        .alias("ratings_count"),
    )


def load_reviews(path: Path = RAW_DIR / "Books_rating.csv") -> pl.DataFrame:
    """Lê Books_rating.csv, tipa timestamp e gera review_id (a fonte não tem um)."""
    bruto = pl.read_csv(path, infer_schema_length=0)
    return bruto.select(
        pl.col("Id").alias("book_id"),
        pl.col("Title").alias("title"),
        pl.col("Price").cast(pl.Float64, strict=False).alias("price"),
        pl.col("User_id").alias("user_id"),
        pl.col("profileName").alias("profile_name"),
        pl.col("score").cast(pl.Float64, strict=False).alias("rating"),
        (pl.col("time").cast(pl.Int64, strict=False) * 1000)
        .cast(pl.Datetime("ms"))
        .alias("reviewed_at"),
        pl.col("summary").alias("review_title"),
        pl.col("text").alias("review_text"),
    ).with_row_index("review_id")


def main() -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    load_books().write_parquet(INTERIM_DIR / "books.parquet")
    load_reviews().write_parquet(INTERIM_DIR / "reviews.parquet")


if __name__ == "__main__":
    main()
