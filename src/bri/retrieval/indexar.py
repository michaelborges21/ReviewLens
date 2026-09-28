"""Constrói review_chunks: embedding + índice FTS sobre enrichment_sample (spec 03, make index).

Sem checkpoint: a rodada inteira leva minutos, não as 17h43min da extração de aspectos — não há o
mesmo motivo para retomada parcial. `CREATE OR REPLACE TABLE` recria do zero a cada execução.
"""

import duckdb

from bri.data.process import BANCO
from bri.llm import ollama
from bri.retrieval.chunking import dividir_em_chunks

TABELA = "review_chunks"


def montar_chunks(con: duckdb.DuckDBPyConnection) -> list[dict[str, str]]:
    """enrichment_sample -> um registro por chunk, com chunk_id sequencial por review."""
    linhas = con.execute(
        "SELECT review_id, title, review_text FROM enrichment_sample WHERE review_text IS NOT NULL"
    ).fetchall()
    registros = []
    for review_id, title, texto in linhas:
        for i, trecho in enumerate(dividir_em_chunks(texto)):
            registros.append(
                {
                    "chunk_id": f"{review_id}-{i}",
                    "review_id": str(review_id),
                    "title": title,
                    "chunk_text": trecho,
                }
            )
    return registros


def indexar(con: duckdb.DuckDBPyConnection) -> None:
    registros = montar_chunks(con)
    total = len(registros)
    print(f"{total} chunks a embedar", flush=True)

    linhas = []
    for i, registro in enumerate(registros, 1):
        vetor = ollama.embedding(registro["chunk_text"])
        linhas.append(tuple(registro.values()) + (vetor,))
        if i % 500 == 0 or i == total:
            print(f"  [{i}/{total}]", flush=True)

    con.execute(f"""
        CREATE OR REPLACE TABLE {TABELA} (
            chunk_id VARCHAR, review_id VARCHAR, title VARCHAR, chunk_text VARCHAR,
            embedding FLOAT[768]
        )
    """)
    con.executemany(f"INSERT INTO {TABELA} VALUES (?, ?, ?, ?, ?)", linhas)

    con.execute("INSTALL fts; LOAD fts;")
    con.execute(f"PRAGMA create_fts_index('{TABELA}', 'chunk_id', 'chunk_text', overwrite=1)")
    print(f"{TABELA} criada: {total} chunks, índice FTS pronto.", flush=True)


if __name__ == "__main__":
    with duckdb.connect(str(BANCO)) as con:
        indexar(con)
