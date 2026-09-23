"""Gera as figuras e os números do checklist de EDA da spec 01 dentro de reports/."""

import json
from pathlib import Path
from typing import Any

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from bri.data.process import BANCO  # noqa: E402

FIGURAS_DIR = Path("reports/figuras")
NUMEROS = Path("reports/numeros_eda.json")
TOP_N = 15

# Um livro é "polarizado" quando os extremos dominam os dois lados ao mesmo tempo.
MIN_REVIEWS_POLARIZACAO = 20
LIMIAR_EXTREMO = 0.20


def _uma_linha(
    con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> tuple[Any, ...]:
    """Agregação sem GROUP BY sempre devolve uma linha — o stub do DuckDB é que não sabe disso."""
    linha = con.execute(sql, params if params is not None else []).fetchone()
    assert linha is not None
    return linha


def _salvar(fig: Figure, destino: Path, nome: str) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino / nome, dpi=120, bbox_inches="tight")
    plt.close(fig)


def figura_volume(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """Volume por ano e por gênero, e a cauda longa de usuários (H6)."""
    por_ano = con.execute("""
        SELECT year(reviewed_at) AS ano, count(*) AS n FROM reviews
        WHERE reviewed_at > '1996-01-01' GROUP BY 1 ORDER BY 1
    """).fetchall()
    por_genero = con.execute(
        "SELECT categoria, n_reviews FROM genre_stats ORDER BY n_reviews DESC LIMIT ?", [TOP_N]
    ).fetchall()
    concentracao = _uma_linha(
        con,
        """
        WITH ordenado AS (
            SELECT n_reviews, row_number() OVER (ORDER BY n_reviews DESC) AS pos,
                   count(*) OVER () AS total
            FROM users_agg
        )
        SELECT sum(n_reviews) FILTER (WHERE pos <= total * 0.01) * 1.0 / sum(n_reviews)
        FROM ordenado
        """,
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.5))
    ax1.bar([a for a, _ in por_ano], [n for _, n in por_ano], color="#4C72B0")
    ax1.set_title("Reviews por ano")
    ax1.set_xlabel("ano")
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax2.barh(
        [c for c, _ in reversed(por_genero)], [n for _, n in reversed(por_genero)], color="#55A868"
    )
    ax2.set_title(f"Top {TOP_N} gêneros por volume de reviews")
    _salvar(fig, destino, "01_volume.png")

    return {"reviews_por_ano": dict(por_ano), "share_1pct_usuarios": concentracao[0]}


def figura_distribuicao_notas(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """Distribuição global e quantos livros são de fato polarizados (H4)."""
    global_ = con.execute("SELECT rating, count(*) FROM reviews GROUP BY 1 ORDER BY 1").fetchall()
    polarizacao = _uma_linha(
        con,
        """
        WITH por_livro AS (
            SELECT title, count(*) AS n,
                   count(*) FILTER (WHERE rating = 1) * 1.0 / count(*) AS p1,
                   count(*) FILTER (WHERE rating = 5) * 1.0 / count(*) AS p5
            FROM reviews GROUP BY title HAVING count(*) >= ?
        )
        SELECT count(*), count(*) FILTER (WHERE p1 >= ? AND p5 >= ?) FROM por_livro
        """,
        [MIN_REVIEWS_POLARIZACAO, LIMIAR_EXTREMO, LIMIAR_EXTREMO],
    )

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar([str(r) for r, _ in global_], [n for _, n in global_], color="#C44E52")
    ax.set_title("Distribuição global de notas")
    ax.set_xlabel("nota")
    _salvar(fig, destino, "02_notas.png")

    livros_avaliados, polarizados = polarizacao
    return {
        "distribuicao_notas": {str(r): n for r, n in global_},
        "livros_com_min_reviews": livros_avaliados,
        "livros_polarizados": polarizados,
    }


def figura_comprimento_vs_nota(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """O arco de H2: nota 3 escreve mais que nota 5."""
    dados = con.execute("""
        SELECT rating, median(length(review_text)) FROM reviews GROUP BY 1 ORDER BY 1
    """).fetchall()

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot([str(r) for r, _ in dados], [c for _, c in dados], marker="o", color="#8172B2")
    ax.set_title("Comprimento mediano da review por nota")
    ax.set_xlabel("nota")
    ax.set_ylabel("caracteres")
    _salvar(fig, destino, "03_comprimento_vs_nota.png")

    return {"comprimento_mediano_por_nota": {str(r): c for r, c in dados}}


def figura_qualidade(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """Nulos, textos curtos e usuários hiperativos (suspeita de spam)."""
    medidas = _uma_linha(
        con,
        """
        SELECT count(*) FILTER (WHERE review_text IS NULL),
               count(*) FILTER (WHERE length(review_text) < 20),
               count(*) FILTER (WHERE user_hash IS NULL),
               count(*) FILTER (WHERE reviewed_at < '1996-01-01')
        FROM reviews
        """,
    )
    hiperativos = _uma_linha(con, "SELECT count(*) FROM users_agg WHERE n_reviews > 500")

    rotulos = ["texto nulo", "texto < 20", "sem autoria", "data inválida"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(rotulos, list(medidas), color="#937860")
    ax.set_title("Problemas de qualidade (contagem de reviews)")
    ax.set_yscale("log")
    _salvar(fig, destino, "04_qualidade.png")

    return {
        "texto_nulo": medidas[0],
        "texto_muito_curto": medidas[1],
        "sem_autoria": medidas[2],
        "data_invalida": medidas[3],
        "usuarios_acima_500_reviews": hiperativos[0],
    }


def figura_top_autores(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """Volume ao lado da nota bayesiana, para mostrar o efeito do prior."""
    por_volume = con.execute(
        "SELECT author, n_reviews FROM author_stats ORDER BY n_reviews DESC LIMIT ?", [TOP_N]
    ).fetchall()
    por_nota = con.execute(
        """SELECT author, nota_bayesiana FROM author_stats
           WHERE n_reviews > 0 ORDER BY nota_bayesiana DESC LIMIT ?""",
        [TOP_N],
    ).fetchall()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.barh([a for a, _ in reversed(por_volume)], [n for _, n in reversed(por_volume)])
    ax1.set_title(f"Top {TOP_N} autores por volume")
    # Dot plot com eixo ampliado: em barra começando em zero, notas entre 4,7 e 4,9 viram
    # 15 barras visualmente idênticas e o leitor conclui que há empate.
    autores = [a for a, _ in reversed(por_nota)]
    notas = [n for _, n in reversed(por_nota)]
    if notas:
        ax2.hlines(autores, min(notas) - 0.02, notas, color="#DD8452", linewidth=2)
        ax2.plot(notas, autores, "o", color="#DD8452")
        ax2.set_xlim(min(notas) - 0.03, max(notas) + 0.03)
        for autor, nota in zip(autores, notas, strict=True):
            ax2.annotate(
                f"{nota:.3f}", (nota, autor), xytext=(5, -3), textcoords="offset points", fontsize=8
            )
    ax2.set_title(f"Top {TOP_N} por nota bayesiana")
    ax2.set_xlabel("nota bayesiana")
    _salvar(fig, destino, "05_top_autores.png")

    return {
        "top_autor_volume": por_volume[0][0] if por_volume else None,
        "top_autor_bayesiano": por_nota[0][0] if por_nota else None,
    }


def figura_evolucao_temporal(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """Nota média ao longo do tempo (H7)."""
    dados = con.execute("""
        SELECT year(reviewed_at) AS ano, avg(rating) AS nota, count(*) AS n
        FROM reviews WHERE reviewed_at > '1996-01-01' GROUP BY 1 HAVING count(*) > 100 ORDER BY 1
    """).fetchall()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot([a for a, _, _ in dados], [nota for _, nota, _ in dados], marker="o", color="#4C72B0")
    ax.set_title("Nota média por ano")
    ax.set_xlabel("ano")
    ax.set_ylabel("nota média")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _salvar(fig, destino, "06_evolucao_temporal.png")

    return {"nota_media_por_ano": {str(a): nota for a, nota, _ in dados}}


def gerar_figuras(con: duckdb.DuckDBPyConnection, destino: Path) -> dict[str, Any]:
    """Roda o checklist inteiro e devolve os números que sustentam os vereditos."""
    numeros: dict[str, Any] = {}
    for gerar in (
        figura_volume,
        figura_distribuicao_notas,
        figura_comprimento_vs_nota,
        figura_qualidade,
        figura_top_autores,
        figura_evolucao_temporal,
    ):
        numeros.update(gerar(con, destino))
    return numeros


def main() -> None:
    with duckdb.connect(str(BANCO), read_only=True) as con:
        numeros = gerar_figuras(con, FIGURAS_DIR)
    NUMEROS.write_text(json.dumps(numeros, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
