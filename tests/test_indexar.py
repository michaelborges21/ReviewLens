"""Testa a indexação: chunking sobre a amostra e gravação de review_chunks (embedding mockado)."""

import duckdb
import pytest

from bri.retrieval import indexar


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(f"""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            (1, 'Dune', 'review curta sobre o livro'),
            (2, 'Dune', '{"x" * 3000}')
        ) t(review_id, title, review_text)
    """)
    return con


def test_montar_chunks_produz_um_registro_por_chunk(con: duckdb.DuckDBPyConnection) -> None:
    registros = indexar.montar_chunks(con)

    curtos = [r for r in registros if r["review_id"] == "1"]
    longos = [r for r in registros if r["review_id"] == "2"]
    assert len(curtos) == 1
    assert len(longos) > 1
    assert curtos[0]["chunk_id"] == "1-0"
    assert longos[0]["title"] == "Dune"


def test_indexar_cria_tabela_com_embeddings(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(indexar.ollama, "embedding", lambda texto, **_: [0.1] * 768)

    indexar.indexar(con)

    consulta = f"SELECT chunk_id, review_id, title, embedding FROM {indexar.TABELA}"
    linhas = con.execute(consulta).fetchall()
    assert len(linhas) == len(indexar.montar_chunks(con))
    assert len(linhas[0][3]) == 768


def test_indexar_cria_indice_fts_utilizavel(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(indexar.ollama, "embedding", lambda texto, **_: [0.1] * 768)

    indexar.indexar(con)

    resultado = con.execute(
        f"""
        SELECT chunk_id, score FROM (
            SELECT chunk_id, fts_main_{indexar.TABELA}.match_bm25(chunk_id, ?) AS score
            FROM {indexar.TABELA}
        ) WHERE score IS NOT NULL
    """,
        ["curta"],
    ).fetchall()

    assert any(chunk_id == "1-0" for chunk_id, _ in resultado)


def test_indexar_e_idempotente(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem checkpoint: rodar de novo recria do zero, sem duplicar nem falhar."""
    monkeypatch.setattr(indexar.ollama, "embedding", lambda texto, **_: [0.1] * 768)

    indexar.indexar(con)
    indexar.indexar(con)

    total = con.execute(f"SELECT count(*) FROM {indexar.TABELA}").fetchone()
    assert total is not None
    assert total[0] == len(indexar.montar_chunks(con))
