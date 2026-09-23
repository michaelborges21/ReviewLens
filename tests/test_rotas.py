"""Testa as rotas com TestClient — e, principalmente, que texto de review não vira marcação."""

from collections.abc import Iterator

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.base import obter_conexao
from app.main import app

SCRIPT = "<script>alert('xss')</script>"


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'otimo', ?, 'h1'),
            (2, 'Dune', 3.0, TIMESTAMP '2011-05-01', 'meh', 'texto comum', 'h2')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
        """,
        [SCRIPT],
    )
    con.execute("""
        CREATE TABLE books AS
        SELECT * FROM (VALUES ('Dune', ['Ficção'])) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE book_authors AS
        SELECT * FROM (VALUES ('Dune', 'Frank Herbert')) t(title, author)
    """)
    con.execute("""
        CREATE TABLE author_stats AS
        SELECT * FROM (VALUES ('Frank Herbert', 1, 2, 4.0, 3.9))
            t(author, n_livros, n_reviews, nota_media, nota_bayesiana)
    """)
    con.execute("""
        CREATE TABLE genre_stats AS
        SELECT * FROM (VALUES ('Ficção', 1, 2, 4.0, 500.0))
            t(categoria, n_livros, n_reviews, nota_media, comprimento_mediano)
    """)
    con.execute("""
        CREATE TABLE users_agg AS
        SELECT * FROM (VALUES ('h1abcdef012345', 5, 3.0, 800.0))
            t(user_hash, n_reviews, nota_media, comprimento_mediano)
    """)

    app.dependency_overrides[obter_conexao] = lambda: con
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "caminho",
    ["/", "/autores", "/generos", "/reviews", "/entrevistas", "/chat", "/autores/Frank%20Herbert"],
)
def test_paginas_respondem(cliente: TestClient, caminho: str) -> None:
    assert cliente.get(caminho).status_code == 200


def test_texto_de_review_e_escapado(cliente: TestClient) -> None:
    """Review é dado de terceiro (spec 05). Se o autoescape cair, isto tem que ficar vermelho."""
    corpo = cliente.get("/reviews").text

    assert SCRIPT not in corpo
    assert "&lt;script&gt;" in corpo


def test_chat_responde_e_mostra_sql(cliente: TestClient) -> None:
    resposta = cliente.post("/chat", data={"pergunta": "desempenho do autor Herbert"})

    assert resposta.status_code == 200
    assert "Frank Herbert" in resposta.text


def test_chat_recusa_fora_de_escopo(cliente: TestClient) -> None:
    resposta = cliente.post("/chat", data={"pergunta": "me indica um livro para viajar"})

    assert "Não consigo responder isso ainda" in resposta.text


def test_api_devolve_json(cliente: TestClient) -> None:
    dados = cliente.get("/api/autores").json()

    assert dados[0]["author"] == "Frank Herbert"
    assert cliente.get("/api/numeros").json()["reviews"] == 2


def test_entrevistas_mostra_pseudonimo_truncado(cliente: TestClient) -> None:
    """PII: a tela nunca mostra identificador inteiro (spec 05)."""
    corpo = cliente.get("/entrevistas").text

    assert "h1abcdef0123" in corpo
    assert "h1abcdef012345" not in corpo
