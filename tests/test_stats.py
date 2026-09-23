"""Testa as agregações rodando o SQL de verdade contra um DuckDB em memória."""

import duckdb
import pytest

from bri.data.stats import criar_author_stats, criar_genre_stats, criar_users_agg


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """Base mínima: dois autores com volumes muito diferentes e um livro em duas categorias."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Popular', 'h1', 5.0, 'texto longo de review', TIMESTAMP '2010-01-01'),
            (2, 'Popular', 'h1', 5.0, 'outro texto qualquer',  TIMESTAMP '2011-01-01'),
            (3, 'Popular', 'h2', 1.0, 'curto',                 TIMESTAMP '2012-01-01'),
            (4, 'Obscuro', 'h3', 5.0, 'unica review do livro', TIMESTAMP '2013-01-01'),
            (5, 'Popular', NULL, 3.0, 'review sem autoria',    TIMESTAMP '2013-06-01')
        ) t(review_id, title, user_hash, rating, review_text, reviewed_at)
    """)
    con.execute("""
        CREATE TABLE books AS SELECT * FROM (VALUES
            ('Popular', ['Ficção', 'Aventura']),
            ('Obscuro', ['Ficção'])
        ) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE book_authors AS SELECT * FROM (VALUES
            ('Popular', 'Autora Prolífica'),
            ('Obscuro', 'Autor Estreante')
        ) t(title, author)
    """)
    return con


def test_users_agg_ignora_anonimos(con: duckdb.DuckDBPyConnection) -> None:
    criar_users_agg(con)

    linhas = con.execute("SELECT user_hash, n_reviews FROM users_agg ORDER BY 1").fetchall()
    assert linhas == [("h1", 2), ("h2", 1), ("h3", 1)]


def test_bayesiana_puxa_autor_de_pouco_volume_para_a_media(con: duckdb.DuckDBPyConnection) -> None:
    """O estreante tem 5.0 de média, mas com prior alto fica perto da média global."""
    criar_author_stats(con, prior=50)

    estreante = con.execute(
        "SELECT nota_media, nota_bayesiana FROM author_stats WHERE author = 'Autor Estreante'"
    ).fetchone()
    media_global = con.execute("SELECT avg(rating) FROM reviews").fetchone()[0]

    assert estreante[0] == 5.0
    assert abs(estreante[1] - media_global) < abs(estreante[0] - media_global)


def test_prior_padrao_encolhe_de_fato(con: duckdb.DuckDBPyConnection) -> None:
    """Sem passar prior: se o padrão virasse 0, o ranking enviesado passaria despercebido."""
    criar_author_stats(con)

    estreante = con.execute(
        "SELECT nota_media, nota_bayesiana FROM author_stats WHERE author = 'Autor Estreante'"
    ).fetchone()
    media_global = con.execute("SELECT avg(rating) FROM reviews").fetchone()[0]

    assert estreante[0] == 5.0
    assert abs(estreante[1] - media_global) < abs(estreante[0] - media_global)


def test_bayesiana_quase_nao_move_quem_tem_volume(con: duckdb.DuckDBPyConnection) -> None:
    """Com prior 0 a nota bayesiana tem que coincidir com a média simples."""
    criar_author_stats(con, prior=0)

    linhas = con.execute("SELECT nota_media, nota_bayesiana FROM author_stats").fetchall()
    for media, bayesiana in linhas:
        assert media == pytest.approx(bayesiana)


def test_genre_stats_conta_livro_em_cada_categoria(con: duckdb.DuckDBPyConnection) -> None:
    criar_genre_stats(con)

    linhas = dict(con.execute("SELECT categoria, n_livros FROM genre_stats").fetchall())
    assert linhas == {"Ficção": 2, "Aventura": 1}
