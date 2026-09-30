"""Testa o resumo por entidade com fake no lugar do modelo, como test_extract e test_narrador."""

import json
from pathlib import Path

import duckdb
import pytest

from bri.nlp import sumarizar
from bri.schemas.resumo import EntitySummary


@pytest.fixture(autouse=True)
def isolar_descartes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O log de descarte é do projeto; um fake mal escrito já vazou linha para lá uma vez."""
    monkeypatch.setattr(sumarizar, "LOG_DESCARTES", tmp_path / "descartes.jsonl")


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE reviews AS SELECT * FROM (VALUES
            (1, 'Dune', 2.0, TIMESTAMP '2015-01-01', 't', 'texto', 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
    """)
    con.execute(
        "CREATE TABLE books AS SELECT * FROM (VALUES ('Dune', ['Ficção'])) t(title, categories)"
    )
    con.execute(
        "CREATE TABLE book_authors AS SELECT * FROM (VALUES ('Dune','Frank Herbert'))"
        " t(title, author)"
    )
    con.execute("""
        CREATE TABLE enrichment_sample AS SELECT * FROM (VALUES
            (1, 'Dune', 2.0, TIMESTAMP '2015-01-01', 't', 'texto', 'h1')
        ) t(review_id, title, rating, reviewed_at, review_title, review_text, user_hash)
    """)
    con.execute("""
        CREATE TABLE review_enriched AS SELECT * FROM (VALUES
            ('1', [{'aspect':'ritmo','sentiment':'negativo',
                    'evidence':'ficou arrastado demais'}], false)
        ) t(review_id, aspects, is_recommendation)
    """)
    return con


def _resposta(
    review_id: str = "1", quote: str = "ficou arrastado", headline: str = "Ritmo pesa."
) -> str:
    return json.dumps(
        {
            "headline": headline,
            "strengths": [],
            "weaknesses": ["Leitores citam lentidão."],
            "notable_quotes": [{"review_id": review_id, "quote": quote}],
        }
    )


def test_resumo_valido_recebe_contagem_e_versao_do_python(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O modelo não emite n_reviews_considered — é o ponto de separar ResumoRedigido."""
    monkeypatch.setattr(sumarizar.ollama, "gerar_json", lambda *a, **k: _resposta())

    resumo = sumarizar.resumir(con, "autor", "Frank Herbert")

    assert isinstance(resumo, EntitySummary)
    assert resumo.n_reviews_considered == 1
    assert resumo.prompt_version == sumarizar._PROMPT.versao
    assert resumo.entity_type == "autor"


def test_citacao_inventada_e_descartada(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sumarizar.ollama, "gerar_json", lambda *a, **k: _resposta(review_id="999"))

    assert sumarizar.resumir(con, "autor", "Frank Herbert") is None
    motivos = [
        json.loads(linha)["motivo"]
        for linha in sumarizar.LOG_DESCARTES.read_text(encoding="utf-8").splitlines()
    ]
    assert "citacao_inventada" in motivos


def test_quote_nao_literal_descarta_so_a_citacao_e_derruba_o_resumo_sem_sobra(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paráfrase é a falha que a extração já viu: a citação cai, e sem nenhuma o resumo cai."""
    monkeypatch.setattr(
        sumarizar.ollama, "gerar_json", lambda *a, **k: _resposta(quote="o livro é devagar")
    )

    assert sumarizar.resumir(con, "autor", "Frank Herbert") is None
    motivos = [
        json.loads(linha)["motivo"]
        for linha in sumarizar.LOG_DESCARTES.read_text(encoding="utf-8").splitlines()
    ]
    assert "quote_nao_literal" in motivos
    assert "sem_citacao_valida" in motivos


def test_numero_na_prosa_nao_passa(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A regra 3 do prompt pede prosa sem número; o guardrail é quem garante."""
    monkeypatch.setattr(
        sumarizar.ollama,
        "gerar_json",
        lambda *a, **k: _resposta(headline="Nota média de 4,7 estrelas."),
    )

    assert sumarizar.resumir(con, "autor", "Frank Herbert") is None


def test_schema_invalido_descarta(
    con: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sumarizar.ollama, "gerar_json", lambda *a, **k: '{"nao_e": "o schema"}')

    assert sumarizar.resumir(con, "autor", "Frank Herbert") is None


def test_citacoes_enviadas_nao_zeram_um_dos_sentimentos() -> None:
    """Regressão: a consulta devolvia 16 negativas e 16 positivas, mas ordenadas por sentimento —
    e 'negativo' vem antes de 'positivo' no alfabeto. Cortar as 12 primeiras mandava 12 negativas
    e zero positivas, e 54% dos resumos saíam sem nenhum ponto forte."""
    citacoes = [
        {"review_id": str(i), "aspecto": "ritmo", "sentimento": "negativo", "trecho": f"n{i}"}
        for i in range(20)
    ] + [
        {
            "review_id": str(100 + i),
            "aspecto": "enredo",
            "sentimento": "positivo",
            "trecho": f"p{i}",
        }
        for i in range(20)
    ]

    _, ids, _ = sumarizar._blocos(citacoes)
    enviadas = [c for c in sumarizar._intercalar_por_sentimento(citacoes)[: sumarizar.MAX_CITACOES]]

    assert len(ids) == sumarizar.MAX_CITACOES
    assert sum(1 for c in enviadas if c["sentimento"] == "positivo") > 0
    assert sum(1 for c in enviadas if c["sentimento"] == "negativo") > 0


def test_already_done_distingue_autor_de_genero_de_mesmo_nome(tmp_path: Path) -> None:
    """ "Fiction" é gênero e pode ser nome de autor — a chave é o par, não o id."""
    caminho = tmp_path / "resumos.jsonl"
    caminho.write_text(
        json.dumps({"entity_type": "autor", "entity_id": "Fiction"}) + "\n", encoding="utf-8"
    )

    feitas = sumarizar.already_done(caminho)

    assert "autor|Fiction" in feitas
    assert "genero|Fiction" not in feitas


def test_entidades_elegiveis_respeita_o_piso(con: duckdb.DuckDBPyConnection) -> None:
    assert sumarizar.entidades_elegiveis(con, piso=1) == [
        ("autor", "Frank Herbert"),
        ("genero", "Ficção"),
    ]
    assert sumarizar.entidades_elegiveis(con, piso=5) == []


def test_carregar_no_banco_cria_entity_summaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saida = tmp_path / "resumos.jsonl"
    saida.write_text(
        EntitySummary(
            headline="h",
            strengths=[],
            weaknesses=["w"],
            notable_quotes=[{"review_id": "1", "quote": "q"}],  # type: ignore[list-item]
            entity_type="autor",
            entity_id="Frank Herbert",
            n_reviews_considered=3,
            prompt_version="0.2.0",
        ).model_dump_json()
        + "\n",
        encoding="utf-8",
    )
    banco = tmp_path / "t.duckdb"
    monkeypatch.setattr(sumarizar, "SAIDA", saida)
    monkeypatch.setattr(sumarizar, "BANCO", banco)

    sumarizar.carregar_no_banco()

    with duckdb.connect(str(banco), read_only=True) as con:
        linha = con.execute(
            "SELECT entity_type, entity_id, n_reviews_considered FROM entity_summaries"
        ).fetchone()
    assert linha == ("autor", "Frank Herbert", 3)
