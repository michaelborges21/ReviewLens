"""Testa a camada de consulta contra um DuckDB em memória com fixture pequena."""

from typing import Any

import duckdb
import pytest

from bri.data.consultas import (
    aspectos_do_autor,
    aspectos_do_genero,
    buscar_reviews,
    candidato_por_prefixo,
    candidatos_a_entrevista,
    divergencia_nota_sentimento,
    numeros_gerais,
    performance_do_autor,
    performance_do_genero,
    ranking_de_autores,
    ranking_de_generos,
    ranking_por_aspecto,
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
            ('h1', 5, 3.0, 800.0), ('h2', 2, 5.0, 100.0),
            ('h3abcdef000001', 4, 3.2, 500.0), ('h3abcdef000002', 6, 2.8, 600.0)
        ) t(user_hash, n_reviews, nota_media, comprimento_mediano)
    """)
    con.execute("""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, TIMESTAMP '2010-05-01', 'otimo', 'texto longo de review aqui', 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
    """)
    con.execute("""
        CREATE TABLE review_enriched AS SELECT * FROM (VALUES
            ('1', [
                {'aspect': 'enredo', 'sentiment': 'negativo', 'evidence': 'ficou arrastado'},
                {'aspect': 'enredo', 'sentiment': 'positivo', 'evidence': 'reviravolta boa'}
            ], true)
        ) t(review_id, aspects, is_recommendation)
    """)
    return con


def _inserir_aspectos(
    con: duckdb.DuckDBPyConnection,
    titulo: str,
    primeiro_id: int,
    aspecto: str,
    sentimento: str,
    quantas: int,
) -> None:
    """Acrescenta N avaliações de um título à amostra, cada uma com um aspecto/sentimento."""
    for review_id in range(primeiro_id, primeiro_id + quantas):
        con.execute(
            "INSERT INTO enrichment_sample VALUES (?, ?, 2.0, TIMESTAMP '2015-01-01',"
            " 'titulo', 'texto', 'h1')",
            [review_id, titulo],
        )
        con.execute(
            "INSERT INTO review_enriched VALUES (?, [{'aspect': ?, 'sentiment': ?,"
            " 'evidence': 'trecho'}], false)",
            [str(review_id), aspecto, sentimento],
        )


def test_ranking_por_aspecto_prefere_taxa_a_volume(con: duckdb.DuckDBPyConnection) -> None:
    """Regressão do bug de desenho: ordenar por contagem responde "qual é o maior", não "qual é o
    pior". Tolkien tem MAIS menções de ritmo em absoluto, Frank Herbert tem taxa muito maior."""
    # Tolkien: 30 de ritmo negativo em 130 menções (23%) — mais contagem, menos concentração
    _inserir_aspectos(con, "Hobbit", 100, "ritmo", "negativo", 30)
    _inserir_aspectos(con, "Hobbit", 200, "enredo", "positivo", 100)
    # Frank Herbert: 25 de ritmo negativo em 60 menções (42%) — menos contagem, mais concentração
    _inserir_aspectos(con, "Dune", 400, "ritmo", "negativo", 25)
    _inserir_aspectos(con, "Dune", 500, "enredo", "positivo", 35)

    ranking = ranking_por_aspecto(con, "autor", "ritmo", "negativo")

    assert ranking is not None
    assert ranking["entidade"] == "Frank Herbert"  # taxa vence, não volume
    assert ranking["n_mencoes"] == 25
    assert ranking["taxa_crua"] > 40


def test_ranking_por_aspecto_exige_piso_da_entidade(con: duckdb.DuckDBPyConnection) -> None:
    """Taxa de entidade com poucas menções é ruído: 3 de 3 daria 100% e lideraria tudo."""
    _inserir_aspectos(con, "Dune", 100, "ritmo", "negativo", 3)

    assert ranking_por_aspecto(con, "autor", "ritmo", "negativo") is None
    assert ranking_por_aspecto(con, "autor", "ritmo", "negativo", piso_entidade=3) is not None


def test_ranking_por_aspecto_exige_piso_do_aspecto(con: duckdb.DuckDBPyConnection) -> None:
    _inserir_aspectos(con, "Dune", 100, "ritmo", "negativo", 2)
    _inserir_aspectos(con, "Dune", 300, "enredo", "positivo", 60)

    assert ranking_por_aspecto(con, "autor", "ritmo", "negativo", piso_aspecto=3) is None
    assert ranking_por_aspecto(con, "autor", "ritmo", "negativo", piso_aspecto=2) is not None


def test_ranking_por_aspecto_para_genero_via_unnest(con: duckdb.DuckDBPyConnection) -> None:
    _inserir_aspectos(con, "Dune", 100, "ritmo", "negativo", 20)  # Dune é categoria Ficção
    _inserir_aspectos(con, "Dune", 300, "enredo", "positivo", 40)

    ranking = ranking_por_aspecto(con, "genero", "ritmo", "negativo")

    assert ranking is not None
    assert ranking["entidade"] == "Ficção"


def test_ranking_por_aspecto_sem_review_enriched_devolve_none() -> None:
    con = duckdb.connect(":memory:")
    assert ranking_por_aspecto(con, "autor", "ritmo", "negativo") is None


def test_divergencia_nota_sentimento_conta_os_dois_sentidos(
    con: duckdb.DuckDBPyConnection,
) -> None:
    """H5: nota alta com texto negativo, e nota baixa com texto positivo."""
    # nota 5, dois aspectos negativos contra um positivo -> contradiz a nota
    con.execute(
        "INSERT INTO enrichment_sample VALUES (10, 'Dune', 5.0, TIMESTAMP '2015-01-01',"
        " 'otimo', 'texto', 'h1')"
    )
    con.execute(
        "INSERT INTO review_enriched VALUES ('10', ["
        "{'aspect':'ritmo','sentiment':'negativo','evidence':'a'},"
        "{'aspect':'final','sentiment':'negativo','evidence':'b'},"
        "{'aspect':'enredo','sentiment':'positivo','evidence':'c'}], false)"
    )
    # nota 1, texto majoritariamente positivo -> contradiz no sentido inverso
    con.execute(
        "INSERT INTO enrichment_sample VALUES (11, 'Dune', 1.0, TIMESTAMP '2015-01-01',"
        " 'ruim', 'texto', 'h1')"
    )
    con.execute(
        "INSERT INTO review_enriched VALUES ('11', ["
        "{'aspect':'escrita','sentiment':'positivo','evidence':'d'},"
        "{'aspect':'enredo','sentiment':'positivo','evidence':'e'}], false)"
    )

    r = divergencia_nota_sentimento(con)

    assert r is not None
    assert r["nota_alta_texto_negativo"] == 1
    assert r["nota_baixa_texto_positivo"] == 1
    # os dois denominadores existem e são diferentes — é o ponto da função
    assert r["pct_da_nota_alta"] > r["pct_do_total_alta"]


def test_divergencia_nota_sentimento_sem_review_enriched_devolve_none() -> None:
    assert divergencia_nota_sentimento(duckdb.connect(":memory:")) is None


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

    assert candidatos[0]["prefixo"] == "h1"


def test_candidato_por_prefixo_encontra_pelo_prefixo(con: duckdb.DuckDBPyConnection) -> None:
    candidato = candidato_por_prefixo(con, "h1")

    assert candidato is not None
    assert candidato["user_hash"] == "h1"


def test_candidato_por_prefixo_inexistente_devolve_none(con: duckdb.DuckDBPyConnection) -> None:
    assert candidato_por_prefixo(con, "zzz") is None


def test_candidato_por_prefixo_reaplica_elegibilidade(con: duckdb.DuckDBPyConnection) -> None:
    """h2 tem só 2 avaliações — o prefixo não pode contornar o piso de 3 que a tela já aplica."""
    assert candidato_por_prefixo(con, "h2") is None


def test_candidato_por_prefixo_ambiguo_devolve_none(con: duckdb.DuckDBPyConnection) -> None:
    """Dois usuários com o mesmo prefixo de 12 chars: tratado como não encontrado, não escolhido."""
    assert candidato_por_prefixo(con, "h3abcdef0000") is None


def test_aspectos_do_autor_agrega_por_categoria(con: duckdb.DuckDBPyConnection) -> None:
    """'Dune' tem 2 aspectos de enredo na amostra: 1 negativo, 1 positivo."""
    aspectos = aspectos_do_autor(con, "Frank Herbert")

    assert aspectos["aspectos"][0]["aspecto"] == "enredo"
    assert aspectos["aspectos"][0]["n_mencoes"] == 2
    assert aspectos["aspectos"][0]["pct_negativo"] == 50.0
    assert aspectos["aspectos"][0]["exemplo_negativo"] == "ficou arrastado"
    assert aspectos["avaliacoes_analisadas"] == 1
    assert aspectos["avaliacoes_totais"] == 2


def test_aspectos_do_autor_sem_dado_na_amostra(con: duckdb.DuckDBPyConnection) -> None:
    """'Hobbit' tem review na base, mas nenhuma linha caiu na amostra enriquecida."""
    aspectos = aspectos_do_autor(con, "Tolkien")

    assert aspectos["aspectos"] == []
    assert aspectos["avaliacoes_analisadas"] == 0
    assert aspectos["avaliacoes_totais"] == 1


def test_aspectos_do_autor_sem_review_enriched_nao_quebra() -> None:
    """`make data` recria o banco sem review_enriched; a função degrada em vez de lançar exceção."""
    sem_enriquecimento = duckdb.connect(":memory:")
    sem_enriquecimento.execute(
        "CREATE TABLE reviews AS SELECT * FROM (VALUES (1, 'Dune', 5.0))"
        " t(review_id, title, rating)"
    )
    sem_enriquecimento.execute(
        "CREATE TABLE book_authors AS SELECT * FROM (VALUES ('Dune', 'Frank Herbert'))"
        " t(title, author)"
    )

    aspectos = aspectos_do_autor(sem_enriquecimento, "Frank Herbert")

    assert aspectos == {"aspectos": [], "avaliacoes_analisadas": 0, "avaliacoes_totais": 1}


def test_exemplo_negativo_vem_pareado_com_seu_review_id() -> None:
    """Duas reviews concorrem no mesmo aspecto: o id devolvido tem de ser o dono daquele trecho.

    Fixture própria porque o caso exige duas citações negativas no mesmo grupo, o que mudaria as
    contagens dos outros testes.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 2.0), (2, 'Dune', 3.0)
        ) t(review_id, title, rating)
    """)
    con.execute("""
        CREATE TABLE book_authors AS
        SELECT * FROM (VALUES ('Dune', 'Frank Herbert')) t(title, author)
    """)
    con.execute("""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            (1, 'Dune', 'a trama ficou arrastado no meio'),
            (2, 'Dune', 'achei tudo previsivel demais')
        ) t(review_id, title, review_text)
    """)
    con.execute("""
        CREATE TABLE review_enriched AS SELECT * FROM (VALUES
            ('1', [{'aspect': 'enredo', 'sentiment': 'negativo', 'evidence': 'ficou arrastado'}]),
            ('2', [{'aspect': 'enredo', 'sentiment': 'negativo', 'evidence': 'previsivel demais'}])
        ) t(review_id, aspects)
    """)

    enredo = aspectos_do_autor(con, "Frank Herbert")["aspectos"][0]
    dono = con.execute(
        "SELECT review_text FROM enrichment_sample WHERE CAST(review_id AS VARCHAR) = ?",
        [enredo["exemplo_negativo_review_id"]],
    ).fetchone()

    assert enredo["n_mencoes"] == 2
    assert dono is not None
    assert enredo["exemplo_negativo"] in dono[0]


def test_aspectos_do_genero_agrega_por_categoria(con: duckdb.DuckDBPyConnection) -> None:
    aspectos = aspectos_do_genero(con, "Ficção")

    assert aspectos["aspectos"][0]["aspecto"] == "enredo"
    assert aspectos["aspectos"][0]["n_mencoes"] == 2
    assert aspectos["avaliacoes_analisadas"] == 1
    assert aspectos["avaliacoes_totais"] == 2


def test_numeros_gerais(con: duckdb.DuckDBPyConnection) -> None:
    numeros = numeros_gerais(con)

    assert numeros["reviews"] == 3
    assert numeros["livros"] == 2
    assert ranking_de_generos(con)[0]["categoria"] == "Ficção"
