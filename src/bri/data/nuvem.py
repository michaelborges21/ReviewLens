"""Nuvem de palavras por gênero, a partir do texto real das avaliações — não da descrição do
catálogo (diferente dos notebooks exploratórios, que geravam nuvem sobre a sinopse do livro).

Amostra de até LIMITE_REVIEWS por gênero: 0,03s medido contra o banco real para um gênero
grande — rápido o bastante para gerar sob demanda, sem pré-computar nem cachear. Stopwords fixas
em inglês, sem nltk: nltk exigiria `nltk.download()`, uma chamada de rede em tempo de execução,
contra o espírito local-only do projeto (reviews estão em inglês — mesma fronteira de idioma já
decidida no resto do projeto).
"""

import base64
import io
import re
from typing import Any

import duckdb
from wordcloud import WordCloud

LIMITE_REVIEWS = 3000
MAX_PALAVRAS = 80

# Lista compacta, não o corpus inteiro do nltk: cobre os termos que dominam qualquer nuvem de
# texto em inglês e mais os genéricos de review de livro, que uma nuvem "sobre o gênero" não quer.
STOPWORDS_EN = frozenset(
    """
    the a an and or but if then so of to in on at by for with from as is are was were be been
    being have has had do does did will would shall should can could may might must this that
    these those it its it's i you he she we they me him her us them my your his her our their
    not no nor too very just only also about into over under again further once here there when
    where why how all any both each few more most other some such own same s t don now d ll m o
    re ve y ain aren couldn didn doesn hadn hasn haven isn ma mightn mustn needn shan shouldn
    wasn weren won wouldn book books read reading reader readers author authors story stories
    one two really im ive dont didnt thats its it out up down what who which because like get
    got even though going also still much well lot bit thing things something lot
    """.split()
)


def _limpar(texto: str) -> list[str]:
    # Sem apóstrofo na captura, de propósito: "don't" vira "don" + "t", e as duas metades já
    # estão na lista de stopwords — capturar com apóstrofo faz "don't"/"i've" passarem inteiros,
    # porque a lista nunca teria essa forma exata (achado ao inspecionar a imagem real gerada).
    palavras = re.findall(r"[a-zA-Z]+", texto.lower())
    return [p for p in palavras if len(p) > 2 and p not in STOPWORDS_EN]


def frequencia_de_palavras(
    con: duckdb.DuckDBPyConnection, categoria: str, limite: int = LIMITE_REVIEWS
) -> dict[str, int]:
    """Conta palavras do texto das avaliações de um gênero, sem as mais comuns do inglês.

    Amostra, não a base inteira do gênero — mesmo espírito de amostragem já usado no projeto
    (RAG, extração de aspectos), não escopo novo de "processar tudo".
    """
    linhas = con.execute(
        """
        SELECT r.review_text FROM reviews r
        JOIN books b ON b.title = r.title
        WHERE list_contains(b.categories, ?) AND r.review_text IS NOT NULL
        LIMIT ?
        """,
        [categoria, limite],
    ).fetchall()

    contagem: dict[str, int] = {}
    for (texto,) in linhas:
        for palavra in _limpar(texto):
            contagem[palavra] = contagem.get(palavra, 0) + 1
    if not contagem:
        return {}
    mais_frequentes = sorted(contagem.items(), key=lambda item: item[1], reverse=True)
    return dict(mais_frequentes[:MAX_PALAVRAS])


def gerar_nuvem(frequencias: dict[str, Any]) -> str | None:
    """PNG em base64 a partir das frequências — None se não houver palavra nenhuma."""
    if not frequencias:
        return None
    imagem = WordCloud(
        width=900, height=420, background_color="#FAF7F0", colormap="viridis"
    ).generate_from_frequencies(frequencias)
    buffer = io.BytesIO()
    imagem.to_image().save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
