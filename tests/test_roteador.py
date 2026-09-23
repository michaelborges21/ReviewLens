"""Testa o roteador determinístico: classificar, resolver entidade e recusar o resto."""

import duckdb
import pytest

from bri.agent.roteador import Intencao, classificar, resolver_entidade, responder


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE author_stats AS SELECT * FROM (VALUES
            ('Frank Herbert', 1, 2, 4.0, 3.9)
        ) t(author, n_livros, n_reviews, nota_media, nota_bayesiana)
    """)
    con.execute("""
        CREATE TABLE genre_stats AS SELECT * FROM (VALUES
            ('Ficção', 1, 2, 4.0, 500.0)
        ) t(categoria, n_livros, n_reviews, nota_media, comprimento_mediano)
    """)
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'ok', 'texto', 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
    """)
    con.execute("""
        CREATE TABLE books AS
        SELECT * FROM (VALUES ('Dune', ['Ficção'])) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE book_authors AS
        SELECT * FROM (VALUES ('Dune', 'Frank Herbert')) t(title, author)
    """)
    con.execute("""
        CREATE TABLE users_agg AS
        SELECT * FROM (VALUES ('h1', 1, 5.0, 10.0))
            t(user_hash, n_reviews, nota_media, comprimento_mediano)
    """)
    return con


def test_classifica_por_termo_sem_depender_de_acento() -> None:
    assert classificar("como está o autor Frank Herbert?") is Intencao.AUTOR
    assert classificar("qual o gênero mais criticado") is Intencao.GENERO
    assert classificar("quantas reviews temos") is Intencao.VISAO_GERAL


def test_pergunta_fora_de_escopo_nao_vira_consulta() -> None:
    assert classificar("me recomenda um livro bom para viajar") is Intencao.FORA_DE_ESCOPO


def test_resolve_autor_pelo_catalogo(con: duckdb.DuckDBPyConnection) -> None:
    assert resolver_entidade(con, Intencao.AUTOR, "como vai o autor Herbert") == "Frank Herbert"


def test_entidade_inexistente_devolve_none(con: duckdb.DuckDBPyConnection) -> None:
    assert resolver_entidade(con, Intencao.AUTOR, "o autor Fulano Inexistente") is None


def test_responde_autor_com_sql_visivel(con: duckdb.DuckDBPyConnection) -> None:
    """A spec 04 exige o SQL no painel: resposta sem SQL não é auditável."""
    resposta = responder(con, "desempenho do autor Herbert")

    assert resposta.intencao is Intencao.AUTOR
    assert resposta.sql is not None
    assert "Frank Herbert" in resposta.texto


def test_recusa_explica_o_que_sabe_fazer(con: duckdb.DuckDBPyConnection) -> None:
    """Recusar sem dizer o que dá para perguntar deixa o usuário sem saída."""
    resposta = responder(con, "qual sua opinião sobre esse livro")

    assert resposta.intencao is Intencao.FORA_DE_ESCOPO
    assert resposta.sql is None
    assert "F1" in resposta.texto
