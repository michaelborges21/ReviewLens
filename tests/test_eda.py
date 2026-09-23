"""Confere que o checklist da spec 01 gera todas as figuras e os números correspondentes."""

from pathlib import Path

import duckdb
import pytest

from bri.data.eda import gerar_figuras
from bri.data.stats import criar_author_stats, criar_genre_stats, criar_users_agg


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Popular', 'h1', 5.0, 'review longa e detalhada', TIMESTAMP '2010-01-01'),
            (2, 'Popular', 'h2', 1.0, 'odiei', TIMESTAMP '2011-01-01'),
            (3, 'Popular', 'h3', 3.0, 'texto do meio, argumentado', TIMESTAMP '2012-01-01'),
            (4, 'Obscuro', NULL, 5.0, 'sem autoria', TIMESTAMP '2013-01-01')
        ) t(review_id, title, user_hash, rating, review_text, reviewed_at)
    """)
    con.execute("""
        CREATE TABLE books AS SELECT * FROM (VALUES
            ('Popular', ['Ficção']), ('Obscuro', ['Ficção'])
        ) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE book_authors AS SELECT * FROM (VALUES
            ('Popular', 'Autora'), ('Obscuro', 'Autor')
        ) t(title, author)
    """)
    criar_users_agg(con)
    criar_author_stats(con)
    criar_genre_stats(con)
    return con


def test_gera_uma_figura_por_item_do_checklist(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    gerar_figuras(con, tmp_path)

    gerados = sorted(p.name for p in tmp_path.glob("*.png"))
    assert gerados == [
        "01_volume.png",
        "02_notas.png",
        "03_comprimento_vs_nota.png",
        "04_qualidade.png",
        "05_top_autores.png",
        "06_evolucao_temporal.png",
    ]


def test_numeros_acompanham_as_figuras(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    """Todo número que vai para o veredito precisa sair do mesmo script que gera a figura."""
    numeros = gerar_figuras(con, tmp_path)

    assert numeros["distribuicao_notas"] == {"1.0": 1, "3.0": 1, "5.0": 2}
    assert numeros["sem_autoria"] == 1

    comprimento = numeros["comprimento_mediano_por_nota"]
    assert comprimento["3.0"] > comprimento["1.0"]
