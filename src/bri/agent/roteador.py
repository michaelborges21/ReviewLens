"""Classificação determinística de intenção — o roteador da spec 04, ainda sem LLM."""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any

import duckdb

from bri.data import consultas


class Intencao(Enum):
    AUTOR = "autor"
    GENERO = "genero"
    VISAO_GERAL = "visao_geral"
    FORA_DE_ESCOPO = "fora_de_escopo"


TERMOS = {
    Intencao.AUTOR: ("autor", "autora", "escritor", "escritora", "escreveu"),
    Intencao.GENERO: ("genero", "categoria", "genre"),
    Intencao.VISAO_GERAL: ("quantas", "quantos", "total", "visao geral", "resumo da base"),
}


# Palavras que aparecem na pergunta mas nunca são nome de autor ou gênero. Sem essa lista, uma
# pergunta como "desempenho do autor Herbert" faria o roteador procurar um autor chamado
# "desempenho", que é a palavra mais longa da frase.
PALAVRAS_IGNORADAS = frozenset(
    "autor autora escritor escritora escreveu genero categoria genre como esta estao qual "
    "quais sobre para desempenho performance mais menos livro livros review reviews nota "
    "notas melhor pior esse essa dos das com que vai anos ultimos".split()
)


@dataclass(frozen=True)
class Resposta:
    """Toda resposta carrega o SQL que a produziu — a spec 04 exige isso no painel lateral."""

    intencao: Intencao
    texto: str
    sql: str | None
    dados: list[dict[str, Any]]


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


def classificar(pergunta: str) -> Intencao:
    """Só padrão de texto: sem LLM, sem custo e sempre com o mesmo resultado."""
    limpa = _sem_acento(pergunta)
    for intencao, termos in TERMOS.items():
        if any(re.search(rf"\b{termo}\b", limpa) for termo in termos):
            return intencao
    return Intencao.FORA_DE_ESCOPO


def resolver_entidade(
    con: duckdb.DuckDBPyConnection, intencao: Intencao, pergunta: str
) -> str | None:
    """Casa o texto da pergunta com nomes reais do catálogo; sem casar, devolve None."""
    if intencao is Intencao.AUTOR:
        for fragmento in _candidatos(pergunta):
            achado = con.execute(
                """
                SELECT author FROM author_stats
                WHERE n_reviews > 0 AND lower(author) LIKE '%' || lower(?) || '%'
                ORDER BY n_reviews DESC LIMIT 1
                """,
                [fragmento],
            ).fetchone()
            if achado:
                return str(achado[0])
        return None

    if intencao is Intencao.GENERO:
        for fragmento in _candidatos(pergunta):
            achado = con.execute(
                """
                SELECT categoria FROM genre_stats
                WHERE lower(categoria) LIKE '%' || lower(?) || '%'
                ORDER BY n_reviews DESC LIMIT 1
                """,
                [fragmento],
            ).fetchone()
            if achado:
                return str(achado[0])
        return None

    return None


def _fragmentos(pergunta: str) -> list[str]:
    return [p for p in re.split(r"[^\wÀ-ÿ]+", pergunta) if len(p) > 2]


def _candidatos(pergunta: str) -> list[str]:
    """Fragmentos que podem ser nome de entidade, do mais longo ao mais curto.

    Todos são testados contra o catálogo: apostar só no mais longo erra sempre que a pergunta
    tem uma palavra genérica comprida.
    """
    uteis = [f for f in _fragmentos(pergunta) if _sem_acento(f) not in PALAVRAS_IGNORADAS]
    return sorted(uteis, key=len, reverse=True)


def responder(con: duckdb.DuckDBPyConnection, pergunta: str) -> Resposta:
    """Responde o que dá para responder com SQL hoje; recusa o resto em vez de inventar."""
    intencao = classificar(pergunta)

    if intencao is Intencao.VISAO_GERAL:
        numeros = consultas.numeros_gerais(con)
        return Resposta(
            intencao,
            "Números gerais da base.",
            "SELECT count(*) FROM reviews / books / author_stats / genre_stats / users_agg",
            [numeros],
        )

    entidade = resolver_entidade(con, intencao, pergunta)

    if intencao is Intencao.AUTOR and entidade:
        dados = consultas.performance_do_autor(con, entidade)
        serie: list[dict[str, Any]] = dados["serie"]
        return Resposta(
            intencao,
            f"Performance de {entidade}.",
            "SELECT year(reviewed_at), count(*), avg(rating) FROM book_authors"
            " JOIN reviews USING (title) WHERE author = ? GROUP BY 1",
            serie,
        )

    if intencao is Intencao.GENERO and entidade:
        dados = consultas.performance_do_genero(con, entidade)
        return Resposta(
            intencao,
            f"Distribuição de notas em {entidade}.",
            "SELECT rating, count(*) FROM reviews JOIN books USING (title)"
            " WHERE list_contains(categories, ?) GROUP BY 1",
            dados["distribuicao"],
        )

    return Resposta(
        Intencao.FORA_DE_ESCOPO,
        "Não consigo responder isso ainda. Hoje respondo sobre desempenho de um autor, "
        "distribuição de notas de um gênero e números gerais da base. Perguntas sobre o que "
        "os leitores dizem (aspectos, sentimento, resumos) dependem do enriquecimento da F1.",
        None,
        [],
    )
