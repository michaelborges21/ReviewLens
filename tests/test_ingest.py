"""Testa a ingestão com uma fixture pequena — nunca os CSVs reais de 2,9GB."""

from pathlib import Path

from bri.data.ingest import load_books, load_reviews

BOOKS_CSV = """Title,description,authors,image,previewLink,publisher,publishedDate,infoLink,categories,ratingsCount
Dune,Um clássico de ficção científica,['Frank Herbert'],http://img,http://preview,Ace Books,1965,http://info,['Science Fiction'],
O Hobbit,,['J.R.R. Tolkien'],,,,1937,,['Fantasy'],120.0
Boas Práticas,,"['Ana Lima', 'Bruno Sá']",,,Editora X,2020,,"['Tech', 'Reference']",7.0
Livro Torto,,['Autor Sem Fechar,,,,2001,,42,
"""

REVIEWS_CSV = """Id,Title,Price,User_id,profileName,score,time,summary,text
0441013597,Dune,12.99,A1B2C3,"Leitor Ávido",5.0,940636800,Obra-prima,Um dos melhores livros que já li.
0345339681,O Hobbit,,A9Z8Y7,,4.0,1095724800,Muito bom,Aventura clássica e divertida.
0786280670,Livro Torto,,,,2.0,-1,Sem data,Esta review tem time=-1 no dado bruto.
"""


def test_load_books_tipa_listas_e_descarta_colunas_de_url(tmp_path: Path) -> None:
    caminho = tmp_path / "books_data.csv"
    caminho.write_text(BOOKS_CSV, encoding="utf-8")

    livros = load_books(caminho)

    assert livros.columns == [
        "title",
        "description",
        "authors",
        "publisher",
        "published_date",
        "categories",
        "ratings_count",
    ]
    assert livros["authors"][0].to_list() == ["Frank Herbert"]
    assert livros["authors"][2].to_list() == ["Ana Lima", "Bruno Sá"]
    assert livros["categories"][2].to_list() == ["Tech", "Reference"]


def test_load_books_ratings_count_vira_inteiro(tmp_path: Path) -> None:
    """A fixture usa "120.0" porque é assim que o CSV real vem — cast direto a Int64 zerava tudo."""
    caminho = tmp_path / "books_data.csv"
    caminho.write_text(BOOKS_CSV, encoding="utf-8")

    livros = load_books(caminho)

    assert livros["ratings_count"].to_list() == [None, 120, 7, None]


def test_load_books_lista_malformada_vira_lista_vazia(tmp_path: Path) -> None:
    """Parse tolerante: string quebrada ou que não é lista não derruba a ingestão."""
    caminho = tmp_path / "books_data.csv"
    caminho.write_text(BOOKS_CSV, encoding="utf-8")

    livros = load_books(caminho)

    assert livros["authors"][3].to_list() == []
    assert livros["categories"][3].to_list() == []
    assert livros["categories"][1].to_list() == ["Fantasy"]


def test_load_reviews_gera_review_id_e_tipa_timestamp(tmp_path: Path) -> None:
    caminho = tmp_path / "Books_rating.csv"
    caminho.write_text(REVIEWS_CSV, encoding="utf-8")

    reviews = load_reviews(caminho)

    assert reviews["review_id"].to_list() == [0, 1, 2]
    assert reviews["reviewed_at"][0].year == 1999
    assert reviews["rating"].to_list() == [5.0, 4.0, 2.0]
    assert reviews["price"].to_list() == [12.99, None, None]


def test_load_reviews_preserva_timestamp_negativo(tmp_path: Path) -> None:
    """time=-1 existe no dado bruto (21 linhas); a ingestão é fiel, quem trata é a EDA."""
    caminho = tmp_path / "Books_rating.csv"
    caminho.write_text(REVIEWS_CSV, encoding="utf-8")

    reviews = load_reviews(caminho)

    assert reviews["reviewed_at"][2].year == 1969
