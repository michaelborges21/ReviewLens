"""Testa a grade, a alocação ponderada e o determinismo do sorteio."""

import duckdb
import pytest

from bri.nlp.sampling import (
    Celula,
    alocar_amostra,
    formatar_numero,
    formatar_reais,
    montar_grade,
    preparar_estratos,
    sortear,
)


def test_formata_numero_no_padrao_brasileiro() -> None:
    """Milhar com ponto e decimal com vírgula — 1,784 em português seria um decimal."""
    assert formatar_numero(1784) == "1.784"
    assert formatar_numero(1_773_128_911) == "1.773.128.911"
    assert formatar_numero(19.2, 1) == "19,2"
    assert formatar_numero(0) == "0"


def test_formata_reais() -> None:
    assert formatar_reais(332.9) == "R$ 332,90"
    assert formatar_reais(1234.5) == "R$ 1.234,50"
    assert formatar_reais(1_000_000) == "R$ 1.000.000,00"


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """Um livro com gênero e outro sem — o sem categoria não pode sumir da grade."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE reviews AS
        SELECT i AS review_id,
               CASE WHEN i % 2 = 0 THEN 'ComGenero' ELSE 'SemGenero' END AS title,
               CASE WHEN i % 5 = 0 THEN 3.0 WHEN i % 7 = 0 THEN 1.0 ELSE 5.0 END AS rating,
               TIMESTAMP '2012-01-01' AS reviewed_at,
               'texto da review ' || i AS review_text
        FROM range(1, 201) t(i)
    """)
    con.execute("""
        CREATE TABLE books AS SELECT * FROM (VALUES
            ('ComGenero', ['Ficção']),
            ('SemGenero', NULL)
        ) t(title, categories)
    """)
    preparar_estratos(con)
    return con


def test_grade_inclui_reviews_sem_genero(con: duckdb.DuckDBPyConnection) -> None:
    grade = montar_grade(con)

    generos = {celula[2] for celula in grade}
    assert "sem_genero" in generos
    assert sum(grade.values()) == 200


def test_alocacao_nunca_excede_o_disponivel() -> None:
    grade: dict[Celula, int] = {
        ("media(3)", "2010+", "Ficção"): 5,
        ("alta(4-5)", "2010+", "Ficção"): 1_000,
    }

    alocacao = alocar_amostra(grade, total_alvo=500)

    for celula, n in alocacao.items():
        assert n <= grade[celula]
    assert sum(alocacao.values()) <= 500


def test_peso_favorece_a_faixa_media() -> None:
    """Mesmo volume disponível, a faixa média (peso 3) recebe mais que a alta (peso 1)."""
    grade: dict[Celula, int] = {
        ("media(3)", "2010+", "Ficção"): 1_000,
        ("alta(4-5)", "2010+", "Ficção"): 1_000,
    }

    alocacao = alocar_amostra(grade, total_alvo=400)

    assert alocacao[("media(3)", "2010+", "Ficção")] > alocacao[("alta(4-5)", "2010+", "Ficção")]


def test_grade_vazia_nao_quebra() -> None:
    assert alocar_amostra({}, total_alvo=100) == {}
    assert alocar_amostra({("media(3)", "2010+", "X"): 0}, total_alvo=100) == {}


def test_mesma_seed_reproduz_a_amostra(con: duckdb.DuckDBPyConnection) -> None:
    alocacao = alocar_amostra(montar_grade(con), total_alvo=40)

    assert sortear(con, alocacao, seed=42) == sortear(con, alocacao, seed=42)


def test_seed_diferente_muda_a_amostra(con: duckdb.DuckDBPyConnection) -> None:
    alocacao = alocar_amostra(montar_grade(con), total_alvo=40)

    assert sortear(con, alocacao, seed=42) != sortear(con, alocacao, seed=99)
