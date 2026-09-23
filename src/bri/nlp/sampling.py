"""Amostra estratificada para o enriquecimento: mais sinal de aspecto por real gasto."""

from pathlib import Path

import duckdb

from bri.data.process import BANCO
from bri.llm import custo

RELATORIO = Path("reports/sampling.md")
PROMPT_EXTRACAO = Path("src/bri/prompts/extract_review.md")
SEED = 42
TOP_GENEROS = 8

# Reviews da faixa média são as mais argumentadas (mediana de 645 caracteres contra 459 da nota
# 5 — achado de H2), então rendem mais aspecto por chamada. A amostra sobre-representa o meio e
# o baixo de propósito; quem extrapolar para a base precisa corrigir a calibragem.
PESOS = {"baixa(1-2)": 2, "media(3)": 3, "alta(4-5)": 1}

Celula = tuple[str, str, str]


def formatar_numero(valor: float, casas: int = 0) -> str:
    """Padrão brasileiro: milhar com ponto, decimal com vírgula."""
    inteiro, _, decimal = f"{valor:,.{casas}f}".partition(".")
    inteiro = inteiro.replace(",", ".")
    return f"{inteiro},{decimal}" if decimal else inteiro


def formatar_reais(valor: float) -> str:
    return f"R$ {formatar_numero(valor, 2)}"


def preparar_estratos(con: duckdb.DuckDBPyConnection, top_generos: int = TOP_GENEROS) -> None:
    """Classifica cada review em faixa de nota, período e gênero principal."""
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE reviews_estratificadas AS
        WITH livro_categoria AS (
            SELECT b.title, unnest(b.categories) AS categoria
            FROM books b WHERE b.categories IS NOT NULL
        ),
        principais AS (
            SELECT lc.categoria
            FROM livro_categoria lc JOIN reviews r ON r.title = lc.title
            GROUP BY lc.categoria ORDER BY count(*) DESC LIMIT ?
        ),
        genero_do_livro AS (
            -- min() em vez de um LIMIT 1 arbitrário: livro em vários gêneros do topo precisa
            -- cair sempre no mesmo estrato, senão a amostra deixa de ser reproduzível.
            SELECT title, min(categoria) AS genero
            FROM livro_categoria
            WHERE categoria IN (SELECT categoria FROM principais)
            GROUP BY title
        )
        SELECT r.review_id,
               CASE WHEN r.rating <= 2 THEN 'baixa(1-2)'
                    WHEN r.rating = 3 THEN 'media(3)'
                    ELSE 'alta(4-5)' END AS faixa,
               CASE WHEN r.reviewed_at < '2004-01-01' THEN 'ate2003'
                    WHEN r.reviewed_at < '2010-01-01' THEN '2004-2009'
                    ELSE '2010+' END AS periodo,
               coalesce(
                   g.genero,
                   CASE WHEN b.categories IS NULL THEN 'sem_genero' ELSE 'outros' END
               ) AS genero
        FROM reviews r
        LEFT JOIN books b ON b.title = r.title
        LEFT JOIN genero_do_livro g ON g.title = r.title
        """,
        [top_generos],
    )


def montar_grade(con: duckdb.DuckDBPyConnection) -> dict[Celula, int]:
    """Quantas reviews existem em cada célula da grade."""
    linhas = con.execute("""
        SELECT faixa, periodo, genero, count(*)
        FROM reviews_estratificadas GROUP BY 1, 2, 3
    """).fetchall()
    return {(faixa, periodo, genero): n for faixa, periodo, genero, n in linhas}


def alocar_amostra(grade: dict[Celula, int], total_alvo: int) -> dict[Celula, int]:
    """Aloca proporcional ao peso da faixa, nunca acima do que a célula tem disponível."""
    alocado: dict[Celula, int] = {}
    pendentes = {celula: n for celula, n in grade.items() if n > 0}
    restante = total_alvo

    while pendentes and restante > 0:
        massa = sum(n * PESOS[celula[0]] for celula, n in pendentes.items())
        if massa <= 0:
            break
        cotas = {c: restante * n * PESOS[c[0]] / massa for c, n in pendentes.items()}
        saturadas = [c for c, cota in cotas.items() if cota >= pendentes[c]]
        if saturadas:
            for celula in saturadas:
                alocado[celula] = pendentes[celula]
                restante -= pendentes.pop(celula)
            continue
        for celula, cota in cotas.items():
            alocado[celula] = int(cota)
        break

    return {celula: n for celula, n in alocado.items() if n > 0}


def sortear(
    con: duckdb.DuckDBPyConnection, alocacao: dict[Celula, int], seed: int = SEED
) -> list[int]:
    """Sorteio determinístico: ordenar por hash(review_id, seed) reproduz a mesma amostra."""
    escolhidos: list[int] = []
    for (faixa, periodo, genero), n in sorted(alocacao.items()):
        linhas = con.execute(
            """
            SELECT review_id FROM reviews_estratificadas
            WHERE faixa = ? AND periodo = ? AND genero = ?
            ORDER BY hash(review_id + ?) LIMIT ?
            """,
            [faixa, periodo, genero, seed, n],
        ).fetchall()
        escolhidos.extend(review_id for (review_id,) in linhas)
    return escolhidos


def escrever_relatorio(
    con: duckdb.DuckDBPyConnection, grade: dict[Celula, int], alocacao: dict[Celula, int]
) -> None:
    """reports/sampling.md: o que a spec 01 exige e o que sustenta a ADR-004."""
    media = con.execute("SELECT avg(length(review_text)) FROM reviews").fetchone()
    assert media is not None
    caracteres_medios = int(media[0])
    prefixo = custo.overhead_do_prompt(PROMPT_EXTRACAO, caracteres_medios)
    tokens_review = custo.tokens_de(caracteres_medios)
    entrada = prefixo + tokens_review
    few_shot = 3 * (tokens_review + custo.TOKENS_SAIDA_POR_REVIEW)
    cotacao, procedencia = custo.cotacao_usd_brl()

    por_faixa_base: dict[str, int] = {}
    for (faixa, _, _), n in grade.items():
        por_faixa_base[faixa] = por_faixa_base.get(faixa, 0) + n
    por_faixa_amostra: dict[str, int] = {}
    for (faixa, _, _), n in alocacao.items():
        por_faixa_amostra[faixa] = por_faixa_amostra.get(faixa, 0) + n

    total_base = sum(por_faixa_base.values())
    total_amostra = sum(por_faixa_amostra.values())

    def em_reais(valor_usd: float) -> str:
        return formatar_reais(custo.para_reais(valor_usd, cotacao))

    linhas = [
        "# Amostragem para o enriquecimento (spec 01 · spec 02)",
        "",
        f"Gerado por `make sample`. Seed fixa: **{SEED}** — a mesma seed reproduz a amostra.",
        "",
        "## Composição: amostra vs base",
        "",
        "| faixa de nota | base | % base | amostra | % amostra | peso |",
        "|---|---|---|---|---|---|",
    ]
    for faixa in ("baixa(1-2)", "media(3)", "alta(4-5)"):
        b, a = por_faixa_base.get(faixa, 0), por_faixa_amostra.get(faixa, 0)
        linhas.append(
            f"| {faixa} | {formatar_numero(b)} | {formatar_numero(100 * b / total_base, 1)}% "
            f"| {formatar_numero(a)} | {formatar_numero(100 * a / total_amostra, 1)}% "
            f"| {PESOS[faixa]}× |"
        )
    linhas += [
        "",
        "A distribuição da amostra **não espelha a base, de propósito**. Reviews da faixa média",
        "são as mais argumentadas (mediana de 645 caracteres contra 459 da nota 5 — achado de",
        "H2), logo rendem mais aspecto por chamada paga. Quem extrapolar estatística da amostra",
        "para a base inteira precisa corrigir essa calibragem.",
        "",
        f"Células na grade (faixa × período × gênero): **{formatar_numero(len(grade))}**, das",
        f"quais **{formatar_numero(len(alocacao))}** receberam cota. Gêneros fora do top",
        f"{TOP_GENEROS} caem em `outros`; reviews de livro sem categoria caem em `sem_genero`,",
        "em vez de sumirem da amostra. As células menores ficam com cotas de poucas dezenas de",
        "reviews: a grade serve para espalhar cobertura, não para sustentar inferência por",
        "célula.",
        "",
        "## Custo estimado",
        "",
        f"> **Câmbio usado: US$ 1,00 = {formatar_reais(cotacao)}** ({procedencia}).",
        "> A Anthropic cobra em dólar; os valores abaixo já estão convertidos. Defina a variável",
        "> de ambiente `USD_BRL` para recalcular com o câmbio do dia.",
        "",
        f"Base da conta: {formatar_numero(caracteres_medios)} caracteres médios por review, mais",
        f"o gabarito do prompt e 3 exemplos few-shot → **{formatar_numero(entrada)} tokens de",
        f"entrada** e {formatar_numero(custo.TOKENS_SAIDA_POR_REVIEW)} de saída por chamada.",
        "",
        "> Estimativa por heurística (~4 caracteres por token), margem de 15% a 20%. A contagem",
        "> exata exige o tokenizador do provider, que a ADR-004 ainda não escolheu.",
        "",
        f"Custo da amostra atual ({formatar_numero(total_amostra)} reviews):",
        "",
        "| modelo | custo |",
        "|---|---|",
    ]
    for modelo in custo.MODELOS:
        valor = custo.estimar_custo(total_amostra, entrada, modelo)
        linhas.append(f"| {modelo.nome} | {em_reais(valor)} |")

    linhas += [
        "",
        "### A conta é dominada pelos exemplos, não pelas reviews",
        "",
        f"Dos {formatar_numero(entrada)} tokens de entrada por chamada,",
        f"**{formatar_numero(few_shot)} são os 3 exemplos few-shot**",
        f"({formatar_numero(100 * few_shot / entrada)}%), {formatar_numero(prefixo - few_shot)}",
        f"são o gabarito do prompt e apenas **{formatar_numero(tokens_review)}",
        f"({formatar_numero(100 * tokens_review / entrada)}%) são a review a ser analisada**.",
        "Gabarito e exemplos são idênticos em toda chamada, ou seja, prefixo estável de",
        f"{formatar_numero(prefixo)} tokens — candidato direto a cache de prompt:",
        "",
        "| modelo | sem cache | com cache | economia |",
        "|---|---|---|---|",
    ]
    for modelo in custo.MODELOS:
        sem = custo.estimar_custo(total_amostra, entrada, modelo)
        com = custo.estimar_custo_com_cache(total_amostra, prefixo, tokens_review, modelo)
        economia = formatar_numero(100 * (1 - com / sem))
        linhas.append(f"| {modelo.nome} | {em_reais(sem)} | {em_reais(com)} | {economia}% |")

    linhas += [
        "",
        "**Isso reenquadra a ADR-004:** com cache, o Sonnet 5 custa praticamente o mesmo que o",
        "Haiku 4.5 sem cache. A alavanca compra um degrau de modelo pelo mesmo dinheiro, e vale",
        "decidir o cache antes de decidir o provider.",
        "",
        "Quantas reviews cabem em cada teto de gasto (sem cache):",
        "",
        "| modelo | " + " | ".join(formatar_reais(t) for t in custo.TETOS_BRL) + " |",
        "|---" * (len(custo.TETOS_BRL) + 1) + "|",
    ]
    for modelo in custo.MODELOS:
        cabem = " | ".join(
            formatar_numero(custo.tamanho_por_teto(teto / cotacao, entrada, modelo))
            for teto in custo.TETOS_BRL
        )
        linhas.append(f"| {modelo.nome} | {cabem} |")

    linhas += [
        "",
        "Enriquecer a base inteira está fora de cogitação: são",
        "1.773.128.911 caracteres, da ordem de 440 milhões de tokens só de entrada. A cobertura",
        "total é problema da destilação (spec 07), treinada justamente sobre esta amostra.",
        "",
        "`make enrich` continua bloqueado até a ADR-004 ser decidida e este custo, aprovado.",
        "",
    ]
    RELATORIO.write_text("\n".join(linhas), encoding="utf-8")


def main(total_alvo: int = 20_000) -> None:
    with duckdb.connect(str(BANCO)) as con:
        preparar_estratos(con)
        grade = montar_grade(con)
        alocacao = alocar_amostra(grade, total_alvo)
        escolhidos = sortear(con, alocacao)

        con.execute(
            "CREATE OR REPLACE TEMP TABLE escolhidos AS SELECT unnest(?) AS review_id",
            [escolhidos],
        )
        con.execute("""
            CREATE OR REPLACE TABLE enrichment_sample AS
            SELECT r.* FROM reviews r JOIN escolhidos e ON e.review_id = r.review_id
        """)
        escrever_relatorio(con, grade, alocacao)


if __name__ == "__main__":
    main()
