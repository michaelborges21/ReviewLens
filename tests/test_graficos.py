"""Testa os gráficos do chat — forma e robustez, sem comparar pixel (como test_eda.py)."""

from bri.data.graficos import grafico_autor, grafico_genero


def test_grafico_autor_com_serie_devolve_imagem() -> None:
    serie = [
        {"ano": 2010, "n_reviews": 3, "nota_media": 4.5},
        {"ano": 2011, "n_reviews": 5, "nota_media": 3.8},
        {"ano": 2012, "n_reviews": 2, "nota_media": 4.0},
    ]

    imagem = grafico_autor(serie)

    assert imagem is not None
    assert imagem.startswith("data:image/png;base64,")


def test_grafico_autor_com_um_ponto_so_devolve_none() -> None:
    """Um ano só não forma linha — gráfico vazio é pior que não ter gráfico."""
    assert grafico_autor([{"ano": 2010, "n_reviews": 3, "nota_media": 4.5}]) is None


def test_grafico_autor_com_lista_vazia_devolve_none() -> None:
    assert grafico_autor([]) is None


def test_grafico_genero_com_distribuicao_devolve_imagem() -> None:
    distribuicao = [{"rating": r, "n": n} for r, n in [(1, 5), (2, 8), (3, 20), (4, 40), (5, 60)]]

    imagem = grafico_genero(distribuicao)

    assert imagem is not None
    assert imagem.startswith("data:image/png;base64,")


def test_grafico_genero_com_lista_vazia_devolve_none() -> None:
    assert grafico_genero([]) is None
