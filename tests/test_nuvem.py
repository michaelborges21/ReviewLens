"""Testa a nuvem de palavras: contagem sem stopword e geração de imagem — sem comparar pixel."""

import duckdb
import pytest

from bri.data.nuvem import frequencia_de_palavras, gerar_nuvem


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE books AS SELECT * FROM (VALUES
            ('Dune', ['Ficção']), ('Hobbit', ['Fantasia'])
        ) t(title, categories)
    """)
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 5.0, '', 'h1'),
            (2, 'Dune', 4.0, '', 'h2')
        ) t(review_id, title, rating, review_text, user_hash)
    """)
    return con


def test_frequencia_remove_stopword_e_conta_o_resto(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        "UPDATE reviews SET review_text = ? WHERE review_id = 1",
        ["the desert planet is amazing and the sandworms are amazing too"],
    )
    con.execute(
        "UPDATE reviews SET review_text = ? WHERE review_id = 2",
        ["this desert planet has amazing worldbuilding"],
    )

    frequencias = frequencia_de_palavras(con, "Ficção")

    assert frequencias["amazing"] == 3
    assert frequencias["desert"] == 2
    assert "the" not in frequencias
    assert "and" not in frequencias
    assert "is" not in frequencias


def test_frequencia_para_genero_sem_avaliacao_devolve_vazio(
    con: duckdb.DuckDBPyConnection,
) -> None:
    assert frequencia_de_palavras(con, "Inexistente") == {}


def test_gerar_nuvem_com_frequencias_devolve_data_uri() -> None:
    imagem = gerar_nuvem({"ritmo": 40, "personagens": 25, "enredo": 60})

    assert imagem is not None
    assert imagem.startswith("data:image/png;base64,")


def test_gerar_nuvem_sem_frequencia_devolve_none() -> None:
    assert gerar_nuvem({}) is None
