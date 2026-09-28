"""Testa a busca híbrida: ranking, filtro de metadado, diversidade e limiar de evidência."""

import duckdb
import pytest

from bri.retrieval import buscar


def _vetor(posicao: int) -> list[float]:
    """Vetor one-hot: cosseno exato de 1.0 com ele mesmo e 0.0 com qualquer outra posição."""
    v = [0.0] * 768
    v[posicao] = 1.0
    return v


Linha = tuple[str, str, str, str, list[float]]


def _con_com_chunks(linhas: list[Linha]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE review_chunks (
            chunk_id VARCHAR, review_id VARCHAR, title VARCHAR, chunk_text VARCHAR,
            embedding FLOAT[768]
        )
    """)
    con.executemany("INSERT INTO review_chunks VALUES (?, ?, ?, ?, ?)", linhas)
    con.execute("LOAD fts;")
    con.execute("PRAGMA create_fts_index('review_chunks', 'chunk_id', 'chunk_text', overwrite=1)")
    return con


def test_chunk_mais_proximo_aparece_primeiro(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_com_chunks(
        [
            ("a-0", "a", "Livro A", "final decepcionante e apressado", _vetor(0)),
            ("b-0", "b", "Livro B", "personagens muito bem construidos", _vetor(1)),
        ]
    )
    monkeypatch.setattr(buscar.ollama, "embedding", lambda texto: _vetor(0))

    resultado = buscar.buscar(con, "o que acharam do final")

    assert resultado[0]["review_id"] == "a"
    assert resultado[0]["score"] == pytest.approx(1.0)


def test_filtro_por_autor_exclui_fora_do_filtro(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_com_chunks(
        [
            ("dune-0", "1", "Dune", "final decepcionante", _vetor(0)),
            ("hobbit-0", "2", "Hobbit", "final decepcionante tambem", _vetor(0)),
        ]
    )
    con.execute("""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES (1, 'Dune'), (2, 'Hobbit'))
            t(review_id, title)
    """)
    con.execute("""
        CREATE TABLE book_authors AS SELECT * FROM (VALUES
            ('Dune', 'Frank Herbert'), ('Hobbit', 'Tolkien')
        ) t(title, author)
    """)
    monkeypatch.setattr(buscar.ollama, "embedding", lambda texto: _vetor(0))

    resultado = buscar.buscar(con, "o que acharam do final", autor="Frank Herbert")

    assert [r["review_id"] for r in resultado] == ["1"]


def test_diversidade_limita_chunks_por_review(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_com_chunks(
        [
            ("c-0", "c", "Livro C", "trecho um sobre o final", _vetor(0)),
            ("c-1", "c", "Livro C", "trecho dois sobre o final", _vetor(0)),
            ("c-2", "c", "Livro C", "trecho tres sobre o final", _vetor(0)),
        ]
    )
    monkeypatch.setattr(buscar.ollama, "embedding", lambda texto: _vetor(0))

    resultado = buscar.buscar(con, "o que acharam do final")

    assert len(resultado) == buscar.MAX_CHUNKS_POR_REVIEW


def test_match_de_bm25_sem_relacao_semantica_nao_esconde_match_denso_bom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Achado contra o banco real: BM25 pode ranquear em 1º um chunk com similaridade densa 0.0.

    'b-0' compartilha palavras com a pergunta (BM25 alto) mas o vetor é ortogonal (denso 0.0);
    'a-0' tem o vetor idêntico ao da pergunta (denso 1.0) mas nenhuma palavra em comum. Sem o
    filtro por similaridade mínima, a fusão RRF pode colocar 'b-0' em 1º e a checagem de "sem
    evidência" olhando só o topo do ranking devolveria [] mesmo havendo o match denso genuíno.
    """
    con = _con_com_chunks(
        [
            ("a-0", "a", "Livro A", "xyzxyz abc123 semtermoemcomum", _vetor(0)),
            ("b-0", "b", "Livro B", "pergunta sobre final decepcionante aqui", _vetor(5)),
        ]
    )
    monkeypatch.setattr(buscar.ollama, "embedding", lambda texto: _vetor(0))

    resultado = buscar.buscar(con, "pergunta sobre final decepcionante aqui")

    assert [r["review_id"] for r in resultado] == ["a"]


def test_sem_similaridade_suficiente_retorna_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    con = _con_com_chunks([("a-0", "a", "Livro A", "assunto completamente diferente", _vetor(5))])
    monkeypatch.setattr(buscar.ollama, "embedding", lambda texto: _vetor(0))

    assert buscar.buscar(con, "pergunta sem relacao nenhuma") == []
