"""Classificação determinística de intenção — o roteador da spec 04, ainda sem LLM."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import duckdb

from bri.data import consultas
from bri.retrieval import buscar
from bri.texto import sem_acento


class Intencao(Enum):
    AUTOR = "autor"
    GENERO = "genero"
    VISAO_GERAL = "visao_geral"
    TEMA_LIVRE = "tema_livre"
    FORA_DE_ESCOPO = "fora_de_escopo"


TERMOS = {
    Intencao.AUTOR: ("autor", "autora", "escritor", "escritora", "escreveu"),
    Intencao.GENERO: ("genero", "categoria", "genre"),
    Intencao.VISAO_GERAL: ("quantas", "quantos", "total", "visao geral", "resumo da base"),
}

# tema livre é sobre o que os LEITORES pensam, não a opinião do modelo (spec 05 proíbe a segunda).
# checado só depois de TERMOS não bater — preserva 100% o comportamento de AUTOR/GENERO/VISAO_GERAL.
GATILHOS_TEMA_LIVRE = (
    "leitores",
    "leitor",
    "acham",
    "acha",
    "criticam",
    "critica",
    "reclamam",
    "reclama",
    "elogiam",
    "elogia",
)
# essas vencem qualquer gatilho acima: pedem a opinião do modelo ou uma recomendação pessoal,
# ambas fora de escopo pela spec 05 — "qual sua opinião" não pode virar tema livre por causa de
# nenhuma outra palavra que apareça na frase.
EXCLUSOES_TEMA_LIVRE = (
    "sua opiniao",
    "voce acha",
    "na sua visao",
    "me recomenda",
    "me indica",
    "devo ler",
)


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
    # o dict de consultas.aspectos_do_*: o narrador precisa das citações e do tamanho da amostra
    aspectos: dict[str, Any] = field(default_factory=dict)
    # trechos de bri.retrieval.buscar — forma própria, não reaproveita `aspectos`: um é "melhor
    # exemplo por categoria", outro é "top-k por relevância"
    trechos: list[dict[str, Any]] = field(default_factory=list)


def _e_tema_livre(limpa: str) -> bool:
    if any(termo in limpa for termo in EXCLUSOES_TEMA_LIVRE):
        return False
    return any(re.search(rf"\b{termo}\b", limpa) for termo in GATILHOS_TEMA_LIVRE)


def classificar(pergunta: str) -> Intencao:
    """Só padrão de texto: sem LLM, sem custo e sempre com o mesmo resultado."""
    limpa = sem_acento(pergunta)
    for intencao, termos in TERMOS.items():
        if any(re.search(rf"\b{termo}\b", limpa) for termo in termos):
            return intencao
    if _e_tema_livre(limpa):
        return Intencao.TEMA_LIVRE
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
    uteis = [f for f in _fragmentos(pergunta) if sem_acento(f) not in PALAVRAS_IGNORADAS]
    return sorted(uteis, key=len, reverse=True)


def _resumo_de_aspectos(aspectos: dict[str, Any]) -> str:
    """Cita o aspecto mais mencionado, ou vazio se a amostra não cobre a entidade."""
    if not aspectos["aspectos"]:
        return ""
    top = aspectos["aspectos"][0]
    return (
        f" Nas {aspectos['avaliacoes_analisadas']} avaliações analisadas por IA, "
        f"o aspecto mais citado é {top['aspecto']} ({top['n_mencoes']} menções, "
        f"{top['pct_negativo']:.0f}% negativas)."
    )


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
        aspectos = consultas.aspectos_do_autor(con, entidade)
        return Resposta(
            intencao,
            f"Performance de {entidade}.{_resumo_de_aspectos(aspectos)}",
            "SELECT year(reviewed_at), count(*), avg(rating) FROM book_authors"
            " JOIN reviews USING (title) WHERE author = ? GROUP BY 1\n"
            "-- aspectos: WITH base AS (SELECT re.aspects FROM review_enriched re"
            " JOIN enrichment_sample es USING (review_id) JOIN book_authors USING (title)"
            " WHERE author = ?) ...",
            serie,
            aspectos=aspectos,
        )

    if intencao is Intencao.GENERO and entidade:
        dados = consultas.performance_do_genero(con, entidade)
        aspectos = consultas.aspectos_do_genero(con, entidade)
        return Resposta(
            intencao,
            f"Distribuição de notas em {entidade}.{_resumo_de_aspectos(aspectos)}",
            "SELECT rating, count(*) FROM reviews JOIN books USING (title)"
            " WHERE list_contains(categories, ?) GROUP BY 1\n"
            "-- aspectos: WITH base AS (SELECT re.aspects FROM review_enriched re"
            " JOIN enrichment_sample es USING (review_id) JOIN books b USING (title)"
            " WHERE list_contains(categories, ?)) ...",
            dados["distribuicao"],
            aspectos=aspectos,
        )

    if intencao is Intencao.TEMA_LIVRE:
        autor_filtro = resolver_entidade(con, Intencao.AUTOR, pergunta)
        genero_filtro = resolver_entidade(con, Intencao.GENERO, pergunta)
        trechos = buscar.buscar(con, pergunta, autor=autor_filtro, genero=genero_filtro)
        if not trechos:
            return Resposta(
                Intencao.FORA_DE_ESCOPO,
                "Não encontrei base suficiente nas avaliações para responder isso.",
                None,
                [],
            )
        return Resposta(
            intencao, "O que os leitores dizem sobre o tema perguntado.", None, [], trechos=trechos
        )

    return Resposta(
        Intencao.FORA_DE_ESCOPO,
        "Não consigo responder isso ainda. Hoje respondo sobre desempenho de um autor, "
        "distribuição de notas de um gênero, o que os leitores citam sobre eles "
        "(aspectos extraídos por IA de uma amostra), busca por tema livre nas avaliações "
        "e números gerais da base.",
        None,
        [],
    )
