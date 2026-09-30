"""Gera o golden set de 200 avaliações a rotular à mão (spec 06): 100 do aspecto `ritmo` — a
categoria mais frágil na medição de concordância entre modelos — mais 100 de amostra geral, para
as outras 8 categorias não ficarem sem representação. Sorteio determinístico com seed fixa, mesma
técnica de `bri.nlp.sampling` (`ORDER BY hash(review_id || seed)`).

Sem coluna de resposta da IA: rotular olhando a resposta da IA enviesaria o gabarito.
"""

import csv
from pathlib import Path

import duckdb

SEED = 42
N_RITMO = 100
N_GERAL = 100
DESTINO = Path("reports/evals/golden_aspectos.csv")
CAMPOS = [
    "review_id",
    "texto",
    "nota",
    "aspecto_1",
    "sentimento_1",
    "aspecto_2",
    "sentimento_2",
    "aspecto_3",
    "sentimento_3",
    "aspecto_4",
    "sentimento_4",
]


def _selecionar(
    con: duckdb.DuckDBPyConnection, so_ritmo: bool, excluir: list[str], n: int
) -> list[tuple[str, str, float]]:
    condicao = (
        "EXISTS (SELECT 1 FROM UNNEST(re.aspects) AS t(a) WHERE (a).aspect = 'ritmo')"
        if so_ritmo
        else "true"
    )
    return con.execute(
        f"""
        SELECT re.review_id, es.review_text, es.rating
        FROM review_enriched re
        JOIN enrichment_sample es ON es.review_id = re.review_id
        WHERE ({condicao}) AND re.review_id NOT IN (SELECT unnest(?))
        ORDER BY hash(re.review_id || CAST(? AS VARCHAR))
        LIMIT ?
        """,
        [excluir, SEED, n],
    ).fetchall()


def gerar(con: duckdb.DuckDBPyConnection) -> Path:
    ritmo = _selecionar(con, so_ritmo=True, excluir=[], n=N_RITMO)
    geral = _selecionar(con, so_ritmo=False, excluir=[r[0] for r in ritmo], n=N_GERAL)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with DESTINO.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        for review_id, texto, nota in [*ritmo, *geral]:
            linha = dict.fromkeys(CAMPOS, "")
            linha.update(review_id=review_id, texto=texto, nota=nota)
            escritor.writerow(linha)
    return DESTINO


if __name__ == "__main__":
    from bri.data.process import BANCO

    with duckdb.connect(str(BANCO), read_only=True) as con:
        caminho = gerar(con)
    print(f"{N_RITMO + N_GERAL} avaliações gravadas em {caminho}")
