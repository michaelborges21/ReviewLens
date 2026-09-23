"""Testa limpeza, deduplicação e pseudonimização com fixtures pequenas."""

import polars as pl
import pytest

from bri.data.process import (
    deduplicar_reviews,
    limpar_texto,
    montar_book_authors,
    pseudonimizar_usuario,
)


def reviews_fixture() -> pl.DataFrame:
    """Mesma review do usuário U1 em três edições, mais duas anônimas de texto igual."""
    return pl.DataFrame(
        {
            "review_id": [0, 1, 2, 3, 4, 5],
            "book_id": ["B1", "B2", "B3", "B9", "B8", "B1"],
            "user_id": ["U1", "U1", "U1", None, None, "U2"],
            "profile_name": ["Ana", "Ana", "Ana", None, None, "Bruno"],
            "review_title": ["t", "t", "t", "anon", "anon", "outro"],
            "review_text": ["mesmo texto", "mesmo texto", "mesmo texto", "eco", "eco", "distinto"],
        },
        schema={
            "review_id": pl.UInt32,
            "book_id": pl.Utf8,
            "user_id": pl.Utf8,
            "profile_name": pl.Utf8,
            "review_title": pl.Utf8,
            "review_text": pl.Utf8,
        },
    )


def test_dedup_colapsa_edicoes_do_mesmo_usuario() -> None:
    canonicas, edicoes = deduplicar_reviews(reviews_fixture())

    u1 = canonicas.filter(pl.col("user_id") == "U1")
    assert u1.height == 1
    assert u1["review_id"][0] == 0
    edicoes_da_canonica = edicoes.filter(pl.col("review_id") == 0)["book_id"].to_list()
    assert sorted(edicoes_da_canonica) == ["B1", "B2", "B3"]


def test_dedup_nao_colapsa_anonimos_distintos() -> None:
    """user_id nulo não é 'um usuário só' — anônimos com mesmo texto em livros distintos ficam."""
    canonicas, _ = deduplicar_reviews(reviews_fixture())

    anonimas = canonicas.filter(pl.col("user_id").is_null())
    assert anonimas.height == 2
    assert sorted(anonimas["book_id"].to_list()) == ["B8", "B9"]


def test_dedup_preserva_review_unica() -> None:
    canonicas, _ = deduplicar_reviews(reviews_fixture())

    assert canonicas.filter(pl.col("user_id") == "U2").height == 1
    assert canonicas.height == 4


def test_unescape_antes_da_dedup_junta_textos_equivalentes() -> None:
    """A ordem em main() importa: limpar antes de deduplicar colapsa 170 pares na base real."""
    reviews = pl.DataFrame(
        {
            "review_id": [0, 1],
            "book_id": ["B1", "B2"],
            "user_id": ["U1", "U1"],
            "profile_name": ["Ana", "Ana"],
            "review_title": ["t", "t"],
            "review_text": ["Diz &quot;oi&quot;", 'Diz "oi"'],
        },
        schema={
            "review_id": pl.UInt32,
            "book_id": pl.Utf8,
            "user_id": pl.Utf8,
            "profile_name": pl.Utf8,
            "review_title": pl.Utf8,
            "review_text": pl.Utf8,
        },
    )

    assert deduplicar_reviews(reviews)[0].height == 2
    assert deduplicar_reviews(limpar_texto(reviews, ["review_text"]))[0].height == 1


def test_limpar_texto_desfaz_entidades_html() -> None:
    df = pl.DataFrame({"review_text": ["Diz &quot;oi&quot; &amp; sai", "Caf&#233;", None]})

    limpo = limpar_texto(df, ["review_text"])

    assert limpo["review_text"].to_list() == ['Diz "oi" & sai', "Café", None]


def test_pseudonimizar_descarta_pii_e_hasheia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_ID_HASH_SALT", "sal-de-teste")

    resultado = pseudonimizar_usuario(reviews_fixture())

    assert "user_id" not in resultado.columns
    assert "profile_name" not in resultado.columns
    hashes = resultado["user_hash"].to_list()
    assert hashes[0] == hashes[1]
    assert hashes[0] != hashes[5]
    assert len(hashes[0]) == 64
    assert hashes[3] is None


def test_pseudonimizar_muda_com_o_salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_ID_HASH_SALT", "sal-a")
    com_sal_a = pseudonimizar_usuario(reviews_fixture())["user_hash"][0]
    monkeypatch.setenv("USER_ID_HASH_SALT", "sal-b")
    com_sal_b = pseudonimizar_usuario(reviews_fixture())["user_hash"][0]

    assert com_sal_a != com_sal_b


def test_pseudonimizar_falha_alto_sem_salt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem salt a pseudonimização para — nunca cai num fallback silencioso (spec 05)."""
    monkeypatch.delenv("USER_ID_HASH_SALT", raising=False)

    with pytest.raises(RuntimeError, match="USER_ID_HASH_SALT"):
        pseudonimizar_usuario(reviews_fixture())


def test_book_authors_explode_multiplos_autores() -> None:
    livros = pl.DataFrame(
        {
            "title": ["Dune", "Boas Práticas", "Sem Autor"],
            "authors": [["Frank Herbert"], ["Ana Lima", "Bruno Sá"], []],
        }
    )

    pares = montar_book_authors(livros)

    assert pares.height == 3
    assert sorted(pares.filter(pl.col("title") == "Boas Práticas")["author"].to_list()) == [
        "Ana Lima",
        "Bruno Sá",
    ]
    assert pares.filter(pl.col("title") == "Sem Autor").height == 0
