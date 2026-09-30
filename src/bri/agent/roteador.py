"""Classificação determinística de intenção — o roteador da spec 04, ainda sem LLM."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

import duckdb

from bri.data import consultas
from bri.retrieval import buscar
from bri.schemas.aspectos import Aspecto, Sentimento
from bri.texto import sem_acento


class Intencao(Enum):
    AUTOR = "autor"
    GENERO = "genero"
    VISAO_GERAL = "visao_geral"
    TEMA_LIVRE = "tema_livre"
    MISTA = "mista"
    FORA_DE_ESCOPO = "fora_de_escopo"


TERMOS = {
    Intencao.AUTOR: ("autor", "autora", "escritor", "escritora", "escreveu"),
    Intencao.GENERO: ("genero", "categoria", "genre"),
    Intencao.VISAO_GERAL: ("quantas", "quantos", "total", "visao geral", "resumo da base"),
}

# MISTA é o caso "qual autor/gênero lidera um aspecto, e o que os leitores dizem sobre isso" —
# ranking por SQL seguido de busca semântica filtrada pelo resultado (spec 04: loop ReAct, aqui
# implementado como sequência fixa de 2 passos, não um planejador genérico — ver DECISIONS.md).
INTERROGATIVOS_RANKING = ("qual", "quais", "quem")
SUPERLATIVOS = ("mais", "menos", "maior", "menor", "melhor", "pior")

# "outro" fica de fora de propósito: é a categoria residual da extração, nunca uma palavra que o
# usuário digita para perguntar.
ASPECTOS_TERMOS: dict[Aspecto, tuple[str, ...]] = {
    "enredo": ("enredo", "historia", "trama"),
    "personagens": ("personagem", "personagens"),
    "ritmo": ("ritmo",),
    "final": ("final",),
    "escrita": ("escrita", "prosa", "estilo"),
    "tradução": ("traducao",),
    "edição_física": ("edicao fisica", "encadernacao", "impressao", "acabamento"),
    "preço": ("preco",),
}
GATILHOS_SENTIMENTO_NEGATIVO = ("reclama", "reclamacao", "reclamam", "critica", "criticam", "pior")
GATILHOS_SENTIMENTO_POSITIVO = ("elogia", "elogio", "elogiam", "melhor", "gostam", "adoram")

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
    # (tipo, valor) da entidade que este turno resolveu — a rota usa isto para lembrar na sessão.
    # Guarda o TIPO real (AUTOR/GENERO), não `intencao`: uma Resposta TEMA_LIVRE que herdou autor
    # não pode salvar (TEMA_LIVRE, valor), senão o próximo turno TEMA_LIVRE comparando tipo falha
    # e a herança quebra na segunda pergunta seguida sem nome.
    entidade_herdavel: tuple[Intencao, str] | None = None


def _e_tema_livre(limpa: str) -> bool:
    if any(termo in limpa for termo in EXCLUSOES_TEMA_LIVRE):
        return False
    return any(re.search(rf"\b{termo}\b", limpa) for termo in GATILHOS_TEMA_LIVRE)


@dataclass(frozen=True)
class _DetalhesMista:
    tipo: Intencao  # AUTOR ou GENERO
    aspecto: Aspecto
    sentimento: Sentimento


def _aspecto_da_pergunta(limpa: str) -> Aspecto | None:
    for aspecto, termos in ASPECTOS_TERMOS.items():
        if any(re.search(rf"\b{re.escape(t)}\b", limpa) for t in termos):
            return aspecto
    return None


def _sentimento_alvo(limpa: str) -> Sentimento:
    """Default negativo: "quem tem o pior/mais reclamado X" é o uso mais comum deste recurso."""
    if any(re.search(rf"\b{t}\b", limpa) for t in GATILHOS_SENTIMENTO_NEGATIVO):
        return "negativo"
    if any(re.search(rf"\b{t}\b", limpa) for t in GATILHOS_SENTIMENTO_POSITIVO):
        return "positivo"
    return "negativo"


def _detectar_mista(limpa: str) -> _DetalhesMista | None:
    """3 condições precisam bater juntas: ranking/superlativo + categoria (autor/gênero) +
    aspecto conhecido. Exigir as três evita MISTA engolir tráfego que já tem rota própria — só
    "mais" ou só "autor" aparece em qualquer pergunta comum."""
    tem_ranking = any(re.search(rf"\b{t}\b", limpa) for t in INTERROGATIVOS_RANKING) and any(
        re.search(rf"\b{t}\b", limpa) for t in SUPERLATIVOS
    )
    if not tem_ranking:
        return None
    aspecto = _aspecto_da_pergunta(limpa)
    if aspecto is None:
        return None
    if any(re.search(rf"\b{t}\b", limpa) for t in TERMOS[Intencao.AUTOR]):
        tipo = Intencao.AUTOR
    elif any(re.search(rf"\b{t}\b", limpa) for t in TERMOS[Intencao.GENERO]):
        tipo = Intencao.GENERO
    else:
        return None
    return _DetalhesMista(tipo, aspecto, _sentimento_alvo(limpa))


def classificar(pergunta: str) -> Intencao:
    """Só padrão de texto: sem LLM, sem custo e sempre com o mesmo resultado.

    MISTA é testada antes de TERMOS: "qual autor tem mais reclamação de ritmo" bateria em
    TERMOS[AUTOR] pelo termo "autor" e nunca chegaria a MISTA se a ordem fosse a outra.
    """
    limpa = sem_acento(pergunta)
    if _detectar_mista(limpa) is not None:
        return Intencao.MISTA
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


def _entidade_ou_herdada(
    entidade: str | None, tipo: Intencao, entidade_herdada: tuple[Intencao, str] | None
) -> str | None:
    """Usa a entidade da pergunta atual; sem ela, herda só se o tipo bater com o herdado."""
    if entidade is not None:
        return entidade
    if entidade_herdada is not None and entidade_herdada[0] is tipo:
        return entidade_herdada[1]
    return None


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


def responder(
    con: duckdb.DuckDBPyConnection,
    pergunta: str,
    entidade_herdada: tuple[Intencao, str] | None = None,
) -> Resposta:
    """Responde o que dá para responder com SQL hoje; recusa o resto em vez de inventar.

    `entidade_herdada` vem da sessão de conversa (bri.agent.conversa): quando a pergunta atual
    não nomeia autor/gênero nenhum, herda o da pergunta anterior, se o tipo bater.
    """
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
    entidade = _entidade_ou_herdada(entidade, intencao, entidade_herdada)

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
            entidade_herdavel=(Intencao.AUTOR, entidade),
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
            entidade_herdavel=(Intencao.GENERO, entidade),
        )

    if intencao is Intencao.TEMA_LIVRE:
        autor_filtro = _entidade_ou_herdada(
            resolver_entidade(con, Intencao.AUTOR, pergunta), Intencao.AUTOR, entidade_herdada
        )
        genero_filtro = _entidade_ou_herdada(
            resolver_entidade(con, Intencao.GENERO, pergunta), Intencao.GENERO, entidade_herdada
        )
        trechos = buscar.buscar(con, pergunta, autor=autor_filtro, genero=genero_filtro)
        if not trechos:
            return Resposta(
                Intencao.FORA_DE_ESCOPO,
                "Não encontrei base suficiente nas avaliações para responder isso.",
                None,
                [],
            )
        herdavel = (
            (Intencao.AUTOR, autor_filtro)
            if autor_filtro
            else (Intencao.GENERO, genero_filtro)
            if genero_filtro
            else None
        )
        return Resposta(
            intencao,
            "O que os leitores dizem sobre o tema perguntado.",
            None,
            [],
            trechos=trechos,
            entidade_herdavel=herdavel,
        )

    if intencao is Intencao.MISTA:
        detalhes = _detectar_mista(sem_acento(pergunta))
        assert detalhes is not None  # classificar() já garantiu a mesma condição
        tipo_str: Literal["autor", "genero"] = (
            "autor" if detalhes.tipo is Intencao.AUTOR else "genero"
        )
        ranking = consultas.ranking_por_aspecto(
            con, tipo_str, detalhes.aspecto, detalhes.sentimento
        )
        if ranking is None:
            rotulo = "autor" if detalhes.tipo is Intencao.AUTOR else "gênero"
            return Resposta(
                Intencao.FORA_DE_ESCOPO,
                f"Não há avaliações suficientes analisadas por IA sobre '{detalhes.aspecto}' "
                f"({detalhes.sentimento}) para apontar qual {rotulo} lidera com confiança — "
                f"é preciso pelo menos {consultas.PISO_MENCOES_ASPECTO} menções do aspecto e "
                f"{consultas.PISO_MENCOES_ENTIDADE} menções no total para a taxa significar algo.",
                None,
                [],
            )
        entidade = ranking["entidade"]
        autor_filtro = entidade if detalhes.tipo is Intencao.AUTOR else None
        genero_filtro = entidade if detalhes.tipo is Intencao.GENERO else None
        trechos = buscar.buscar(con, pergunta, autor=autor_filtro, genero=genero_filtro)
        # A taxa é o critério do ranking, então é ela que a frase precisa dizer — citar só a
        # contagem faria a resposta parecer ordenada por volume, que é justamente o que não é.
        texto = (
            f"{entidade} lidera em {detalhes.aspecto} {detalhes.sentimento} na amostra analisada "
            f"por IA: {ranking['n_mencoes']} de {ranking['mencoes_totais']} menções "
            f"({ranking['taxa_crua']:.1f}% do que os leitores citam sobre {entidade})."
        )
        texto += (
            " Veja abaixo o que os leitores dizem."
            if trechos
            else " Não encontrei trechos de leitores citando isso na busca semântica."
        )
        return Resposta(
            intencao,
            texto,
            ranking["sql"],
            [
                {
                    "entidade": entidade,
                    "n_mencoes": ranking["n_mencoes"],
                    "mencoes_totais": ranking["mencoes_totais"],
                    "taxa_crua": round(ranking["taxa_crua"], 1),
                }
            ],
            trechos=trechos,
            entidade_herdavel=(detalhes.tipo, entidade),
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
