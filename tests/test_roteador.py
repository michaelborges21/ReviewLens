"""Testa o roteador determinístico: classificar, resolver entidade e recusar o resto."""

import duckdb
import pytest

from bri.agent import roteador
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
    con.execute("""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'ok', 'texto', 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
    """)
    con.execute("""
        CREATE TABLE review_enriched AS SELECT * FROM (VALUES
            ('1', [{'aspect': 'enredo', 'sentiment': 'positivo', 'evidence': 'otima'}], true)
        ) t(review_id, aspects, is_recommendation)
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


def test_responde_autor_inclui_resumo_de_aspectos(con: duckdb.DuckDBPyConnection) -> None:
    """A pergunta de autor já embute o aspecto mais citado, sem precisar de intenção nova."""
    resposta = responder(con, "desempenho do autor Herbert")

    assert "enredo" in resposta.texto


def test_recusa_explica_o_que_sabe_fazer(con: duckdb.DuckDBPyConnection) -> None:
    """Recusar sem dizer o que dá para perguntar deixa o usuário sem saída."""
    resposta = responder(con, "qual sua opinião sobre esse livro")

    assert resposta.intencao is Intencao.FORA_DE_ESCOPO
    assert resposta.sql is None
    assert "aspectos" in resposta.texto.lower()


def test_classifica_tema_livre() -> None:
    assert classificar("o que os leitores acham do final") is Intencao.TEMA_LIVRE


def test_exclusao_vence_gatilho_ambiguo() -> None:
    """ "voce acha" pede a opinião do MODELO — não pode virar tema livre só por citar leitores."""
    pergunta = "o que voce acha que os leitores pensam sobre isso"

    assert classificar(pergunta) is Intencao.FORA_DE_ESCOPO


def test_responde_tema_livre_com_trechos(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    trechos_fake = [{"review_id": "1", "trecho": "final decepcionante", "score": 0.9}]
    monkeypatch.setattr(roteador.buscar, "buscar", lambda *a, **k: trechos_fake)

    resposta = responder(con, "o que os leitores acham do final")

    assert resposta.intencao is Intencao.TEMA_LIVRE
    assert resposta.trechos == trechos_fake
    assert resposta.aspectos == {}


def test_tema_livre_sem_evidencia_vira_fora_de_escopo(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(roteador.buscar, "buscar", lambda *a, **k: [])

    resposta = responder(con, "o que os leitores acham do final")

    assert resposta.intencao is Intencao.FORA_DE_ESCOPO
    assert resposta.sql is None
