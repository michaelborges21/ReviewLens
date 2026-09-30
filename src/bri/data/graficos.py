"""Gráficos embutidos nas respostas do chat — mesmo matplotlib da EDA (spec 01), mesmo backend
Agg, sem dependência nova. PNG em base64: sem rota, sem arquivo estático, cabe na resposta HTMX.

Padrões reaproveitados dos notebooks exploratórios (notebooks/02_eda_books_rating.ipynb,
04_solucao.ipynb): linha de nota ao longo do tempo e histograma de distribuição de notas.
"""

import base64
import io
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

# Mesma paleta da apresentação: terracota para nota, sage para volume — identidade visual
# consistente com o resto do projeto, não cor escolhida ao acaso.
COR_NOTA = "#B4483C"
COR_VOLUME = "#C9CDBE"
COR_DISTRIBUICAO = "#3D6B5C"


def _para_data_uri(fig: Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def grafico_autor(serie: list[dict[str, Any]]) -> str | None:
    """Nota média e volume de avaliações por ano, eixo duplo.

    None com menos de 2 pontos: um ano só não forma linha, e gráfico vazio é pior que não ter
    gráfico nenhum.
    """
    if len(serie) < 2:
        return None
    ordenada = sorted(serie, key=lambda linha: linha["ano"])
    anos = [linha["ano"] for linha in ordenada]
    notas = [linha["nota_media"] for linha in ordenada]
    volumes = [linha["n_reviews"] for linha in ordenada]

    fig, eixo_notas = plt.subplots(figsize=(7, 3.2))
    eixo_volume = eixo_notas.twinx()
    eixo_volume.bar(anos, volumes, color=COR_VOLUME, alpha=0.6, label="avaliações")
    eixo_notas.plot(anos, notas, color=COR_NOTA, marker="o", linewidth=2, label="nota média")
    eixo_notas.set_ylabel("nota média")
    eixo_notas.set_ylim(1, 5)
    eixo_volume.set_ylabel("nº de avaliações")
    # A linha de nota precisa ficar na frente das barras de volume, não atrás.
    eixo_notas.set_zorder(eixo_volume.get_zorder() + 1)
    eixo_notas.patch.set_visible(False)
    fig.tight_layout()
    return _para_data_uri(fig)


def grafico_genero(distribuicao: list[dict[str, Any]]) -> str | None:
    """Distribuição de notas de um gênero — mesmo padrão de plt.hist(score, bins=5)."""
    if not distribuicao:
        return None
    ordenada = sorted(distribuicao, key=lambda linha: linha["rating"])
    notas = [str(int(linha["rating"])) for linha in ordenada]
    contagens = [linha["n"] for linha in ordenada]

    fig, eixo = plt.subplots(figsize=(7, 3.2))
    eixo.bar(notas, contagens, color=COR_DISTRIBUICAO)
    eixo.set_xlabel("nota")
    eixo.set_ylabel("nº de avaliações")
    fig.tight_layout()
    return _para_data_uri(fig)
