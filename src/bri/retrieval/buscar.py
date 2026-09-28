"""Busca híbrida sobre review_chunks: BM25 + denso, fundidos por RRF (spec 03).

Sem reranker cross-encoder (nenhum modelo de rerank disponível localmente) e sem MMR formal —
diversidade por contador simples, suficiente porque 92% das reviews indexadas são chunk único.
"""

from collections import Counter
from typing import Any

import duckdb

from bri.llm import ollama

K_FINAL = 8
K_CANDIDATOS = 50
RRF_K = 60
MAX_CHUNKS_POR_REVIEW = 2
MAX_CHUNKS_POR_TITULO = 3
SIMILARIDADE_MINIMA = 0.3


def _linhas(
    con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> list[dict[str, Any]]:
    """Mesmo padrão de consultas.py — replicado, não importado: `_linhas` é privado por lá."""
    cursor = con.execute(sql, params if params is not None else [])
    assert cursor.description is not None
    colunas = [descricao[0] for descricao in cursor.description]
    return [dict(zip(colunas, linha, strict=True)) for linha in cursor.fetchall()]


def _filtro_metadado(autor: str | None, genero: str | None) -> tuple[str, str, list[str]]:
    """Junta review_chunks -> enrichment_sample -> book_authors/books só quando há filtro."""
    joins: list[str] = []
    condicoes: list[str] = []
    params: list[str] = []
    if autor or genero:
        joins.append("JOIN enrichment_sample es ON es.review_id = rc.review_id")
    if autor:
        joins.append("JOIN book_authors ba ON ba.title = es.title")
        condicoes.append("ba.author = ?")
        params.append(autor)
    if genero:
        joins.append("JOIN books b ON b.title = es.title")
        condicoes.append("list_contains(b.categories, ?)")
        params.append(genero)
    join_sql = " ".join(dict.fromkeys(joins))
    where_sql = ("AND " + " AND ".join(condicoes)) if condicoes else ""
    return join_sql, where_sql, params


def _fundir_rrf(densos: list[dict[str, Any]], bm25: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """RRF: soma 1/(RRF_K + posição), somando as duas listas por chunk_id. Sem normalizar score."""
    rank_denso = {r["chunk_id"]: i for i, r in enumerate(densos)}
    rank_bm25 = {r["chunk_id"]: i for i, r in enumerate(bm25)}
    similaridade_densa = {r["chunk_id"]: r["score"] for r in densos}
    todos = {r["chunk_id"]: r for r in [*bm25, *densos]}  # densos por último: preserva suas colunas

    def rrf(chunk_id: str) -> float:
        pontuacao = 0.0
        if chunk_id in rank_denso:
            pontuacao += 1 / (RRF_K + rank_denso[chunk_id] + 1)
        if chunk_id in rank_bm25:
            pontuacao += 1 / (RRF_K + rank_bm25[chunk_id] + 1)
        return pontuacao

    fundidos = sorted(todos.values(), key=lambda r: rrf(r["chunk_id"]), reverse=True)
    for r in fundidos:
        r["similaridade_densa"] = similaridade_densa.get(r["chunk_id"], 0.0)
    return fundidos


def _aplicar_diversidade(fundidos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """No máximo 2 chunks por review e 3 por título — sem recalcular similaridade (isso é MMR)."""
    por_review: Counter[str] = Counter()
    por_titulo: Counter[str] = Counter()
    resultado = []
    for r in fundidos:
        if por_review[r["review_id"]] >= MAX_CHUNKS_POR_REVIEW:
            continue
        if por_titulo[r["title"]] >= MAX_CHUNKS_POR_TITULO:
            continue
        resultado.append(r)
        por_review[r["review_id"]] += 1
        por_titulo[r["title"]] += 1
    return resultado


def buscar(
    con: duckdb.DuckDBPyConnection,
    pergunta: str,
    autor: str | None = None,
    genero: str | None = None,
) -> list[dict[str, Any]]:
    """Denso + BM25 fundidos por RRF, filtro de metadado opcional, diversidade por review/título.

    [] quando não há evidência suficiente — o chamador decide narrar "não encontrei base".
    """
    vetor = ollama.embedding(pergunta)
    join_sql, where_sql, params = _filtro_metadado(autor, genero)

    densos = _linhas(
        con,
        f"""
        SELECT rc.chunk_id, rc.review_id, rc.title, rc.chunk_text,
               list_cosine_similarity(rc.embedding, ?::FLOAT[768]) AS score
        FROM review_chunks rc {join_sql}
        WHERE 1=1 {where_sql}
        ORDER BY score DESC LIMIT {K_CANDIDATOS}
        """,
        [vetor, *params],
    )

    bm25 = _linhas(
        con,
        f"""
        SELECT chunk_id, review_id, title, chunk_text, score FROM (
            SELECT rc.chunk_id, rc.review_id, rc.title, rc.chunk_text,
                   fts_main_review_chunks.match_bm25(rc.chunk_id, ?) AS score
            FROM review_chunks rc {join_sql}
            WHERE 1=1 {where_sql}
        ) sub
        WHERE score IS NOT NULL
        ORDER BY score DESC LIMIT {K_CANDIDATOS}
        """,
        [pergunta, *params],
    )

    fundidos = _fundir_rrf(densos, bm25)
    # limiar filtra por relevância, não só checa o topo do ranking: achado contra o banco real —
    # BM25 pode ranquear em 1º um chunk com similaridade densa 0.0 (colisão de termo, sem relação
    # semântica), escondendo um match denso genuíno que ficou em 2º lugar na fusão.
    relevantes = [r for r in fundidos if r["similaridade_densa"] >= SIMILARIDADE_MINIMA]
    if not relevantes:
        return []

    diversos = _aplicar_diversidade(relevantes)[:K_FINAL]
    return [
        {"review_id": r["review_id"], "trecho": r["chunk_text"], "score": r["similaridade_densa"]}
        for r in diversos
    ]
