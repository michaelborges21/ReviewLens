"""Consultas somente-leitura sobre a camada processed — o que as telas e a API leem."""

from pathlib import Path
from typing import Any

import duckdb

from bri.data.process import BANCO

LIMITE_PADRAO = 25


def conectar(caminho: Path = BANCO) -> duckdb.DuckDBPyConnection:
    """A interface nunca escreve no banco — abrir read-only torna isso impossível, não opcional."""
    return duckdb.connect(str(caminho), read_only=True)


def _linhas(
    con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> list[dict[str, Any]]:
    cursor = con.execute(sql, params if params is not None else [])
    assert cursor.description is not None
    colunas = [descricao[0] for descricao in cursor.description]
    return [dict(zip(colunas, linha, strict=True)) for linha in cursor.fetchall()]


def ranking_de_autores(
    con: duckdb.DuckDBPyConnection, ordenar_por: str = "bayesiana", limite: int = LIMITE_PADRAO
) -> list[dict[str, Any]]:
    """Ordenar por nota_media reproduz o viés que a bayesiana corrige — as telas mostram os dois."""
    colunas = {"bayesiana": "nota_bayesiana", "media": "nota_media", "volume": "n_reviews"}
    if ordenar_por not in colunas:
        raise ValueError(f"ordenação desconhecida: {ordenar_por}")
    return _linhas(
        con,
        f"""
        SELECT author, n_livros, n_reviews, nota_media, nota_bayesiana
        FROM author_stats WHERE n_reviews > 0
        ORDER BY {colunas[ordenar_por]} DESC LIMIT ?
        """,
        [limite],
    )


def performance_do_autor(con: duckdb.DuckDBPyConnection, autor: str) -> dict[str, Any]:
    """author_stats não tem recorte temporal: a série anual vem de reviews via book_authors."""
    resumo = _linhas(con, "SELECT * FROM author_stats WHERE author = ?", [autor])
    serie = _linhas(
        con,
        """
        SELECT year(r.reviewed_at) AS ano, count(*) AS n_reviews, avg(r.rating) AS nota_media
        FROM book_authors ba
        JOIN reviews r ON r.title = ba.title
        WHERE ba.author = ? AND r.reviewed_at > '1996-01-01'
        GROUP BY 1 ORDER BY 1
        """,
        [autor],
    )
    livros = _linhas(
        con,
        """
        SELECT ba.title, count(r.review_id) AS n_reviews, avg(r.rating) AS nota_media
        FROM book_authors ba
        LEFT JOIN reviews r ON r.title = ba.title
        WHERE ba.author = ?
        GROUP BY 1 ORDER BY n_reviews DESC LIMIT 20
        """,
        [autor],
    )
    return {
        "autor": autor,
        "resumo": resumo[0] if resumo else None,
        "serie": serie,
        "livros": livros,
    }


def ranking_de_generos(
    con: duckdb.DuckDBPyConnection, limite: int = LIMITE_PADRAO
) -> list[dict[str, Any]]:
    return _linhas(
        con,
        """
        SELECT categoria, n_livros, n_reviews, nota_media, comprimento_mediano
        FROM genre_stats ORDER BY n_reviews DESC LIMIT ?
        """,
        [limite],
    )


def performance_do_genero(con: duckdb.DuckDBPyConnection, categoria: str) -> dict[str, Any]:
    """genre_stats não guarda distribuição de notas; ela é calculada aqui a partir de reviews."""
    resumo = _linhas(con, "SELECT * FROM genre_stats WHERE categoria = ?", [categoria])
    distribuicao = _linhas(
        con,
        """
        SELECT r.rating, count(*) AS n
        FROM reviews r
        JOIN books b ON b.title = r.title
        WHERE list_contains(b.categories, ?)
        GROUP BY 1 ORDER BY 1
        """,
        [categoria],
    )
    return {
        "categoria": categoria,
        "resumo": resumo[0] if resumo else None,
        "distribuicao": distribuicao,
    }


def buscar_reviews(
    con: duckdb.DuckDBPyConnection,
    nota: float | None = None,
    ano_de: int | None = None,
    ano_ate: int | None = None,
    genero: str | None = None,
    limite: int = 50,
) -> list[dict[str, Any]]:
    """Filtros sempre parametrizados: nada que venha do usuário entra na string de SQL."""
    condicoes = ["r.review_text IS NOT NULL"]
    params: list[Any] = []
    if nota is not None:
        condicoes.append("r.rating = ?")
        params.append(nota)
    if ano_de is not None:
        condicoes.append("year(r.reviewed_at) >= ?")
        params.append(ano_de)
    if ano_ate is not None:
        condicoes.append("year(r.reviewed_at) <= ?")
        params.append(ano_ate)
    if genero is not None:
        condicoes.append(
            "EXISTS (SELECT 1 FROM books b WHERE b.title = r.title"
            " AND list_contains(b.categories, ?))"
        )
        params.append(genero)
    params.append(limite)
    return _linhas(
        con,
        f"""
        SELECT r.review_id, r.title, r.rating, r.reviewed_at, r.review_title, r.review_text
        FROM reviews r WHERE {" AND ".join(condicoes)}
        ORDER BY r.review_id LIMIT ?
        """,
        params,
    )


def candidatos_a_entrevista(
    con: duckdb.DuckDBPyConnection, limite: int = LIMITE_PADRAO
) -> list[dict[str, Any]]:
    """Ranking explicável: as parcelas aparecem na tela, não só a nota final.

    Sem aspectos (F1), profundidade é aproximada pelo comprimento — e H2 mostrou que quem dá 5
    escreve menos, então nota extrema não é sinal de bom entrevistado.
    """
    return _linhas(
        con,
        """
        SELECT user_hash,
               n_reviews,
               nota_media,
               comprimento_mediano,
               abs(nota_media - 3.0) AS distancia_do_meio,
               (ln(n_reviews + 1) * comprimento_mediano) / (1 + abs(nota_media - 3.0)) AS score
        FROM users_agg
        WHERE n_reviews >= 3 AND comprimento_mediano IS NOT NULL
        ORDER BY score DESC LIMIT ?
        """,
        [limite],
    )


def _tabela_existe(con: duckdb.DuckDBPyConnection, nome: str) -> bool:
    """review_enriched só existe após `make enrich-carregar`; `make data` recria o banco sem ela."""
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ?", [nome]
        ).fetchone()
    )


def aspectos_do_autor(con: duckdb.DuckDBPyConnection, autor: str) -> dict[str, Any]:
    """Agrega review_enriched por autor via enrichment_sample -> book_authors.

    É amostra de 19.949 avaliações, não a base inteira. Sem `review_enriched` carregada, devolve
    zero aspectos em vez de quebrar a página — mesmo comportamento de antes do enriquecimento.
    """
    totais = _linhas(
        con,
        "SELECT count(*) AS n FROM reviews r JOIN book_authors ba ON ba.title = r.title"
        " WHERE ba.author = ?",
        [autor],
    )[0]["n"]
    if not _tabela_existe(con, "review_enriched"):
        return {"aspectos": [], "avaliacoes_analisadas": 0, "avaliacoes_totais": totais}

    aspectos = _linhas(
        con,
        """
        WITH base AS (
            SELECT re.aspects
            FROM review_enriched re
            JOIN enrichment_sample es ON es.review_id = re.review_id
            JOIN book_authors ba ON ba.title = es.title
            WHERE ba.author = ?
        ),
        expandido AS (SELECT unnest(aspects) AS a FROM base)
        SELECT (a).aspect AS aspecto,
               count(*) AS n_mencoes,
               100.0 * sum(CASE WHEN (a).sentiment = 'negativo' THEN 1 ELSE 0 END) / count(*)
                   AS pct_negativo,
               any_value((a).evidence) FILTER (WHERE (a).sentiment = 'negativo') AS exemplo_negativo
        FROM expandido GROUP BY 1 ORDER BY n_mencoes DESC
        """,
        [autor],
    )
    analisadas = _linhas(
        con,
        "SELECT count(DISTINCT es.review_id) AS n FROM enrichment_sample es"
        " JOIN book_authors ba ON ba.title = es.title WHERE ba.author = ?",
        [autor],
    )[0]["n"]
    return {"aspectos": aspectos, "avaliacoes_analisadas": analisadas, "avaliacoes_totais": totais}


def aspectos_do_genero(con: duckdb.DuckDBPyConnection, categoria: str) -> dict[str, Any]:
    """Mesma agregação de aspectos_do_autor, via books.categories em vez de book_authors."""
    totais = _linhas(
        con,
        "SELECT count(*) AS n FROM reviews r JOIN books b ON b.title = r.title"
        " WHERE list_contains(b.categories, ?)",
        [categoria],
    )[0]["n"]
    if not _tabela_existe(con, "review_enriched"):
        return {"aspectos": [], "avaliacoes_analisadas": 0, "avaliacoes_totais": totais}

    aspectos = _linhas(
        con,
        """
        WITH base AS (
            SELECT re.aspects
            FROM review_enriched re
            JOIN enrichment_sample es ON es.review_id = re.review_id
            JOIN books b ON b.title = es.title
            WHERE list_contains(b.categories, ?)
        ),
        expandido AS (SELECT unnest(aspects) AS a FROM base)
        SELECT (a).aspect AS aspecto,
               count(*) AS n_mencoes,
               100.0 * sum(CASE WHEN (a).sentiment = 'negativo' THEN 1 ELSE 0 END) / count(*)
                   AS pct_negativo,
               any_value((a).evidence) FILTER (WHERE (a).sentiment = 'negativo') AS exemplo_negativo
        FROM expandido GROUP BY 1 ORDER BY n_mencoes DESC
        """,
        [categoria],
    )
    analisadas = _linhas(
        con,
        "SELECT count(DISTINCT es.review_id) AS n FROM enrichment_sample es"
        " JOIN books b ON b.title = es.title WHERE list_contains(b.categories, ?)",
        [categoria],
    )[0]["n"]
    return {"aspectos": aspectos, "avaliacoes_analisadas": analisadas, "avaliacoes_totais": totais}


def numeros_gerais(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    linhas = _linhas(
        con,
        """
        SELECT (SELECT count(*) FROM reviews)     AS reviews,
               (SELECT count(*) FROM books)       AS livros,
               (SELECT count(*) FROM author_stats) AS autores,
               (SELECT count(*) FROM genre_stats) AS generos,
               (SELECT count(*) FROM users_agg)   AS usuarios
        """,
    )
    return linhas[0]
