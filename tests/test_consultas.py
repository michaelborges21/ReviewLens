"""Testa a camada de consulta contra um DuckDB em memória com fixture pequena."""

from typing import Any

import duckdb
import pytest

from bri.data.consultas import (
    buscar_reviews,
    candidatos_a_entrevista,
    numeros_gerais,
    performance_do_autor,
    performance_do_genero,
    ranking_de_autores,
    ranking_de_generos,
)


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'otimo', 'texto longo de review aqui', 'h1'),
            (2, 'Dune', 3.0, TIMESTAMP '2011-05-01', 'meh', 'texto do meio argumentado', 'h2'),
            (3, 'Hobbit', 1.0, TIMESTAMP '2012-05-01', 'ruim', 'nao gostei nada', 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
    """)
    con.execute("""
        CREATE TABLE books AS SELECT * FROM (VALUES
            ('Dune', ['Ficção']), ('Hobbit', ['Fantasia'])
        ) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE book_authors AS SELECT * FROM (VALUES
            ('Dune', 'Frank Herbert'), ('Hobbit', 'Tolkien')
        ) t(title, author)
    """)
    con.execute("""
        CREATE TABLE author_stats AS SELECT * FROM (VALUES
            ('Frank Herbert', 1, 2, 4.0, 3.9),
            ('Tolkien', 1, 1, 1.0, 3.5)
        ) t(author, n_livros, n_reviews, nota_media, nota_bayesiana)
    """)
    con.execute("""
        CREATE TABLE genre_stats AS SELECT * FROM (VALUES
            ('Ficção', 1, 2, 4.0, 500.0), ('Fantasia', 1, 1, 1.0, 200.0)
        ) t(categoria, n_livros, n_reviews, nota_media, comprimento_mediano)
    """)
    con.execute("""
        CREATE TABLE users_agg AS SELECT * FROM (VALUES
            ('h1', 5, 3.0, 800.0), ('h2', 2, 5.0, 100.0)
        ) t(user_hash, n_reviews, nota_media, comprimento_mediano)
    """)
    return con


def test_ranking_por_bayesiana_difere_de_media_simples(con: duckdb.DuckDBPyConnection) -> None:
    """Tolkien tem nota_media 1,0 mas bayesiana 3,5 — a ordenação tem que mudar."""
    por_media = [linha["author"] for linha in ranking_de_autores(con, "media")]
    por_bayesiana = [linha["author"] for linha in ranking_de_autores(con, "bayesiana")]

    assert por_media == ["Frank Herbert", "Tolkien"]
    assert por_bayesiana == ["Frank Herbert", "Tolkien"]
    assert ranking_de_autores(con, "volume")[0]["author"] == "Frank Herbert"


def test_ordenacao_invalida_e_recusada(con: duckdb.DuckDBPyConnection) -> None:
    """Nome de coluna entra em f-string: só valor da allowlist pode chegar lá."""
    with pytest.raises(ValueError, match="ordenação desconhecida"):
        ranking_de_autores(con, "'; DROP TABLE reviews; --")


def test_performance_do_autor_traz_serie_anual(con: duckdb.DuckDBPyConnection) -> None:
    dados = performance_do_autor(con, "Frank Herbert")

    assert dados["resumo"]["n_reviews"] == 2
    assert [linha["ano"] for linha in dados["serie"]] == [2010, 2011]


def test_performance_do_genero_calcula_distribuicao(con: duckdb.DuckDBPyConnection) -> None:
    """genre_stats não guarda distribuição de notas — ela vem de reviews."""
    dados = performance_do_genero(con, "Ficção")

    assert dados["resumo"]["n_reviews"] == 2
    assert {linha["rating"]: linha["n"] for linha in dados["distribuicao"]} == {5.0: 1, 3.0: 1}


def test_busca_de_reviews_filtra(con: duckdb.DuckDBPyConnection) -> None:
    assert len(buscar_reviews(con)) == 3
    assert len(buscar_reviews(con, nota=5.0)) == 1
    assert len(buscar_reviews(con, ano_de=2011)) == 2
    assert len(buscar_reviews(con, genero="Fantasia")) == 1


def test_candidatos_preferem_quem_escreve_mais(con: duckdb.DuckDBPyConnection) -> None:
    """h1 escreve 800 caracteres e fica no meio da escala; h2 dá nota 5 e escreve 100."""
    candidatos: list[dict[str, Any]] = candidatos_a_entrevista(con)

    assert candidatos[0]["user_hash"] == "h1"


def test_numeros_gerais(con: duckdb.DuckDBPyConnection) -> None:
    numeros = numeros_gerais(con)

    assert numeros["reviews"] == 3
    assert numeros["livros"] == 2
    assert ranking_de_generos(con)[0]["categoria"] == "Ficção"
