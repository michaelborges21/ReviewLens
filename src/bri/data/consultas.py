"""Consultas somente-leitura sobre a camada processed — o que as telas e a API leem."""

from pathlib import Path
from typing import Any, Literal

import duckdb

from bri.data.process import BANCO
from bri.schemas.aspectos import Aspecto, Sentimento

LIMITE_PADRAO = 25
# 1-2 menções isoladas não deviam decidir "quem mais reclama de X" — 3 é o piso mais baixo que
# ainda descarta um único leitor obcecado com o mesmo aspecto.
PISO_MENCOES_ASPECTO = 3
# Prior do encolhimento, igual ao `m` da nota bayesiana de `author_stats`: mesma lógica, mesmo
# número. O piso de menções da entidade é o próprio prior, então o dado da entidade sempre pesa
# ao menos metade — abaixo disso a taxa é ruído (um gênero com 3 menções chegava a 100%).
PRIOR_ENCOLHIMENTO = 50
PISO_MENCOES_ENTIDADE = PRIOR_ENCOLHIMENTO


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


def todos_os_generos(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Nomes de gênero, ordem alfabética — alimenta a sugestão de digitação em /reviews.

    São 10.883 categorias distintas: grande demais para um <select>, mas cabem numa <datalist>
    (sugestão nativa do navegador, sem JavaScript novo) porque o usuário filtra digitando.
    """
    linhas = _linhas(con, "SELECT categoria FROM genre_stats ORDER BY categoria")
    return [str(linha["categoria"]) for linha in linhas]


def generos_elegiveis_para_nuvem(con: duckdb.DuckDBPyConnection, piso: int = 200) -> list[str]:
    """Gêneros com avaliação suficiente para uma nuvem de palavras ter sentido.

    Abaixo do piso, poucas avaliações não produzem frequência de palavra que signifique nada —
    e cabem numa lista de tamanho razoável para <select> comum (264 nomes, contra 10.883 no
    catálogo inteiro), sem precisar do truque de <datalist> que /reviews usa.
    """
    linhas = _linhas(
        con,
        "SELECT categoria FROM genre_stats WHERE n_reviews >= ? ORDER BY categoria",
        [piso],
    )
    return [str(linha["categoria"]) for linha in linhas]


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

    Devolve `prefixo`, não o `user_hash` inteiro: a spec 04 exige confirmação humana para revelar
    o identificador, e truncar aqui — não no template — impede que um consumidor novo (a API JSON
    já vazou assim uma vez) exponha o hash completo sem passar pelo gate.
    """
    return _linhas(
        con,
        """
        SELECT substr(user_hash, 1, 12) AS prefixo,
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


_ORIGEM_ENTIDADE = {
    "autor": """
        SELECT ba.author AS entidade, re.review_id, re.aspects
        FROM review_enriched re
        JOIN enrichment_sample es ON es.review_id = re.review_id
        JOIN book_authors ba ON ba.title = es.title
    """,
    # Um livro em várias categorias conta em todas — mesmo unnest de stats.criar_genre_stats.
    "genero": """
        SELECT lc.categoria AS entidade, re.review_id, re.aspects
        FROM review_enriched re
        JOIN enrichment_sample es ON es.review_id = re.review_id
        JOIN (SELECT title, unnest(categories) AS categoria FROM books WHERE categories IS NOT NULL)
             lc ON lc.title = es.title
    """,
}


def ranking_por_aspecto(
    con: duckdb.DuckDBPyConnection,
    tipo: Literal["autor", "genero"],
    aspecto: Aspecto,
    sentimento: Sentimento,
    piso_aspecto: int = PISO_MENCOES_ASPECTO,
    piso_entidade: int = PISO_MENCOES_ENTIDADE,
) -> dict[str, Any] | None:
    """Ranqueia autor OU gênero por **taxa encolhida** de menções a um aspecto+sentimento.

    Não por contagem absoluta: contagem responde "qual é o maior", não "qual é o pior". Medido
    contra o banco — ordenando por contagem, "tradução negativa" devolvia Fiction (30 menções,
    0,2% das suas menções) em vez de Bibles (6,1%, trinta vezes mais concentrado). Mas taxa crua
    também não serve: um gênero com 3 menções chegava a 100%. O encolhimento bayesiano é o mesmo
    remédio que `author_stats.nota_bayesiana` já usa para o mesmo problema.

    None quando review_enriched não existe ainda, ou quando nenhuma entidade atinge os dois pisos —
    o roteador decide como recusar, esta função só informa "não há resposta confiável".
    """
    if not _tabela_existe(con, "review_enriched"):
        return None

    sql = f"""
        WITH base AS ({_ORIGEM_ENTIDADE[tipo]}),
        expandido AS (SELECT entidade, unnest(aspects) AS a FROM base),
        mencoes_da_entidade AS (
            SELECT entidade, count(*) AS mencoes_totais FROM expandido GROUP BY entidade
        ),
        taxa_global AS (
            SELECT 1.0 * sum(CASE WHEN (a).aspect = ? AND (a).sentiment = ? THEN 1 ELSE 0 END)
                       / count(*) AS taxa
            FROM expandido
        ),
        alvo AS (
            SELECT entidade, count(*) AS n_mencoes FROM expandido
            WHERE (a).aspect = ? AND (a).sentiment = ? GROUP BY entidade
        )
        SELECT alvo.entidade,
               alvo.n_mencoes,
               ent.mencoes_totais,
               100.0 * alvo.n_mencoes / ent.mencoes_totais AS taxa_crua,
               100.0 * (
                   (ent.mencoes_totais / (ent.mencoes_totais + {PRIOR_ENCOLHIMENTO}.0))
                       * (1.0 * alvo.n_mencoes / ent.mencoes_totais)
                 + ({PRIOR_ENCOLHIMENTO}.0 / (ent.mencoes_totais + {PRIOR_ENCOLHIMENTO}.0))
                       * taxa_global.taxa
               ) AS taxa_encolhida
        FROM alvo
        JOIN mencoes_da_entidade ent ON ent.entidade = alvo.entidade
        CROSS JOIN taxa_global
        WHERE alvo.n_mencoes >= ? AND ent.mencoes_totais >= ?
        ORDER BY taxa_encolhida DESC LIMIT 1
    """
    linhas = _linhas(
        con, sql, [aspecto, sentimento, aspecto, sentimento, piso_aspecto, piso_entidade]
    )
    if not linhas:
        return None
    return {**linhas[0], "sql": sql}


def entidades_com_aspectos(
    con: duckdb.DuckDBPyConnection, tipo: Literal["autor", "genero"], piso: int
) -> list[tuple[str, int]]:
    """Autores ou gêneros com ao menos `piso` avaliações analisadas, em ordem estável.

    Ordem alfabética, não por volume: a retomada do sumarizador depende de a lista não mudar
    entre sessões, e volume muda se a amostra crescer.
    """
    if not _tabela_existe(con, "review_enriched"):
        return []
    linhas = _linhas(
        con,
        f"""
        WITH base AS ({_ORIGEM_ENTIDADE[tipo]})
        SELECT entidade, count(DISTINCT review_id) AS n_avaliacoes
        FROM base GROUP BY entidade HAVING n_avaliacoes >= ? ORDER BY entidade
        """,
        [piso],
    )
    return [(str(linha["entidade"]), int(linha["n_avaliacoes"])) for linha in linhas]


def citacoes_da_entidade(
    con: duckdb.DuckDBPyConnection,
    tipo: Literal["autor", "genero"],
    entidade: str,
    por_aspecto_e_sentimento: int = 2,
) -> list[dict[str, Any]]:
    """Trechos literais com review_id real, equilibrados entre elogio e crítica.

    Ordem determinística (evidência mais longa primeiro, empate pelo review_id): o `any_value` que
    a agregação usa serve a uma célula de tabela, não a um contexto de prompt que precisa ser
    reproduzível entre execuções.
    """
    if not _tabela_existe(con, "review_enriched"):
        return []
    return _linhas(
        con,
        f"""
        WITH base AS ({_ORIGEM_ENTIDADE[tipo]}),
        expandido AS (SELECT review_id, entidade, unnest(aspects) AS a FROM base),
        ranqueado AS (
            SELECT review_id,
                   (a).aspect AS aspecto,
                   (a).sentiment AS sentimento,
                   (a).evidence AS trecho,
                   row_number() OVER (
                       PARTITION BY (a).aspect, (a).sentiment
                       ORDER BY length((a).evidence) DESC, review_id
                   ) AS posicao
            FROM expandido
            WHERE entidade = ? AND (a).sentiment IN ('negativo', 'positivo')
        )
        SELECT review_id, aspecto, sentimento, trecho
        FROM ranqueado WHERE posicao <= ?
        ORDER BY sentimento, aspecto, review_id
        """,
        [entidade, por_aspecto_e_sentimento],
    )


def resumo_da_entidade(
    con: duckdb.DuckDBPyConnection, tipo: Literal["autor", "genero"], entidade: str
) -> dict[str, Any] | None:
    """None quando entity_summaries não existe ou a entidade não atingiu o piso de avaliações.

    Chave é o par tipo+id: "Fiction" é gênero e também pode ser nome de autor.
    """
    if not _tabela_existe(con, "entity_summaries"):
        return None
    linhas = _linhas(
        con,
        "SELECT * FROM entity_summaries WHERE entity_type = ? AND entity_id = ?",
        [tipo, entidade],
    )
    return linhas[0] if linhas else None


def candidato_por_prefixo(con: duckdb.DuckDBPyConnection, prefixo: str) -> dict[str, Any] | None:
    """Busca o candidato completo a partir do prefixo mostrado na tela.

    Reaplica os critérios de candidatos_a_entrevista — um prefixo não pode contornar
    elegibilidade. Mais de um match (colisão de prefixo, praticamente impossível em ~1M usuários)
    é tratado como "não encontrado", não como escolher a primeira linha arbitrariamente.
    """
    linhas = _linhas(
        con,
        """
        SELECT user_hash,
               n_reviews,
               nota_media,
               comprimento_mediano,
               abs(nota_media - 3.0) AS distancia_do_meio
        FROM users_agg
        WHERE n_reviews >= 3 AND comprimento_mediano IS NOT NULL
          AND user_hash LIKE ? || '%'
        """,
        [prefixo],
    )
    return linhas[0] if len(linhas) == 1 else None


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
            SELECT re.review_id, re.aspects
            FROM review_enriched re
            JOIN enrichment_sample es ON es.review_id = re.review_id
            JOIN book_authors ba ON ba.title = es.title
            WHERE ba.author = ?
        ),
        expandido AS (SELECT review_id, unnest(aspects) AS a FROM base),
        -- trecho e id numa agregação só: duas separadas não garantem vir da mesma linha
        agrupado AS (
            SELECT (a).aspect AS aspecto,
                   count(*) AS n_mencoes,
                   100.0 * sum(CASE WHEN (a).sentiment = 'negativo' THEN 1 ELSE 0 END) / count(*)
                       AS pct_negativo,
                   any_value({'trecho': (a).evidence, 'review_id': review_id})
                       FILTER (WHERE (a).sentiment = 'negativo') AS negativo
            FROM expandido GROUP BY 1
        )
        SELECT aspecto, n_mencoes, pct_negativo,
               negativo.trecho AS exemplo_negativo,
               negativo.review_id AS exemplo_negativo_review_id
        FROM agrupado ORDER BY n_mencoes DESC
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
            SELECT re.review_id, re.aspects
            FROM review_enriched re
            JOIN enrichment_sample es ON es.review_id = re.review_id
            JOIN books b ON b.title = es.title
            WHERE list_contains(b.categories, ?)
        ),
        expandido AS (SELECT review_id, unnest(aspects) AS a FROM base),
        agrupado AS (
            SELECT (a).aspect AS aspecto,
                   count(*) AS n_mencoes,
                   100.0 * sum(CASE WHEN (a).sentiment = 'negativo' THEN 1 ELSE 0 END) / count(*)
                       AS pct_negativo,
                   any_value({'trecho': (a).evidence, 'review_id': review_id})
                       FILTER (WHERE (a).sentiment = 'negativo') AS negativo
            FROM expandido GROUP BY 1
        )
        SELECT aspecto, n_mencoes, pct_negativo,
               negativo.trecho AS exemplo_negativo,
               negativo.review_id AS exemplo_negativo_review_id
        FROM agrupado ORDER BY n_mencoes DESC
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


def divergencia_nota_sentimento(con: duckdb.DuckDBPyConnection) -> dict[str, Any] | None:
    """Veredito de H5: em que fração das avaliações o texto contradiz a nota dada.

    Substitui a etapa 2 da spec 02 (encoder de sentimento sobre as 2.239.998, ADR-015): o
    sentimento por aspecto da amostra responde a mesma pergunta sem inferência sobre a base toda.

    Devolve os **dois denominadores** de propósito. "2,5% das avaliações de nota alta contradizem"
    e "1,5% de todas as avaliações são nota alta contradita" são os dois verdadeiros e medem
    coisas diferentes — citar a porcentagem sem dizer sobre o quê é o jeito de confundir na
    apresentação. O condicional é o que responde a hipótese; o geral dá a dimensão no corpus.
    """
    if not _tabela_existe(con, "review_enriched"):
        return None
    linha = _linhas(
        con,
        """
        WITH por_review AS (
            SELECT re.review_id,
                   any_value(es.rating) AS nota,
                   sum(CASE WHEN (a).sentiment = 'negativo' THEN 1 ELSE 0 END) AS negativos,
                   sum(CASE WHEN (a).sentiment = 'positivo' THEN 1 ELSE 0 END) AS positivos
            FROM review_enriched re, UNNEST(re.aspects) AS t(a)
            JOIN enrichment_sample es ON es.review_id = re.review_id
            GROUP BY re.review_id
        )
        SELECT count(*) AS avaliacoes_com_aspecto,
               sum(CASE WHEN nota >= 4 THEN 1 ELSE 0 END) AS nota_alta,
               sum(CASE WHEN nota >= 4 AND negativos > positivos THEN 1 ELSE 0 END)
                   AS nota_alta_texto_negativo,
               sum(CASE WHEN nota <= 2 THEN 1 ELSE 0 END) AS nota_baixa,
               sum(CASE WHEN nota <= 2 AND positivos > negativos THEN 1 ELSE 0 END)
                   AS nota_baixa_texto_positivo
        FROM por_review
        """,
    )[0]
    total = linha["avaliacoes_com_aspecto"]
    return {
        **linha,
        "pct_da_nota_alta": 100.0 * linha["nota_alta_texto_negativo"] / linha["nota_alta"],
        "pct_da_nota_baixa": 100.0 * linha["nota_baixa_texto_positivo"] / linha["nota_baixa"],
        "pct_do_total_alta": 100.0 * linha["nota_alta_texto_negativo"] / total,
        "pct_do_total_baixa": 100.0 * linha["nota_baixa_texto_positivo"] / total,
    }


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
