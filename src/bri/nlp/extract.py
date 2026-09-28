"""Extração de aspectos (spec 02, etapa 3) — batch fracionável, retomável entre sessões."""

import argparse
import json
import time
from pathlib import Path

import duckdb
from pydantic import ValidationError

from bri.data.process import BANCO
from bri.llm import ollama, prompts
from bri.schemas.aspectos import AspectoCitado, ReviewEnrichment

SAIDA = Path("data/interim/aspectos.jsonl")
LOG_DESCARTES = Path("reports/aspectos_descartados.jsonl")

# spec 09, doutrina de loops: extração de aspectos tem máx. 1 retry.
MAX_TENTATIVAS = 2

SCHEMA = ReviewEnrichment.model_json_schema()


_PROMPT = prompts.carregar("extract_review")


def registrar_descarte(review_id: str, motivo: str, detalhe: object) -> None:
    """`evidence` não é substring do original, ou o schema falhou mesmo após o retry."""
    LOG_DESCARTES.parent.mkdir(parents=True, exist_ok=True)
    with LOG_DESCARTES.open("a", encoding="utf-8") as arquivo:
        registro = {"review_id": review_id, "motivo": motivo, "detalhe": detalhe}
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _evidencia_valida(aspecto: AspectoCitado, texto_original: str) -> bool:
    return aspecto.evidence in texto_original


def extrair(review: dict[str, str | float]) -> ReviewEnrichment | None:
    """Chama o modelo até MAX_TENTATIVAS vezes; descarta só os aspectos com evidência inventada."""
    review_id = str(review["review_id"])
    texto = str(review["texto"])
    ultimo: ReviewEnrichment | None = None

    for _ in range(MAX_TENTATIVAS):
        prompt = _PROMPT.montar(
            review_id=review_id, score=str(float(review["rating"])), review_text=texto
        )
        bruto = ollama.gerar_json(_PROMPT.sistema, prompt, SCHEMA)
        try:
            ultimo = ReviewEnrichment.model_validate_json(bruto)
        except ValidationError:
            continue
        if all(_evidencia_valida(a, texto) for a in ultimo.aspects):
            return ultimo

    if ultimo is None:
        registrar_descarte(review_id, "schema_invalido_apos_retry", None)
        return None

    validos = [a for a in ultimo.aspects if _evidencia_valida(a, texto)]
    inventados = [a for a in ultimo.aspects if not _evidencia_valida(a, texto)]
    if inventados:
        # a evidência rejeitada vai no log: sem ela não se diagnostica a falha sem reprocessar
        registrar_descarte(
            review_id,
            "evidencia_nao_literal",
            [{"aspect": a.aspect, "evidence": a.evidence} for a in inventados],
        )
    return ultimo.model_copy(update={"aspects": validos})


def already_done(caminho: Path) -> set[str]:
    """Os review_id já gravados — reabrir depois de uma sessão de 2h não reprocessa nada."""
    if not caminho.exists():
        return set()
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return {json.loads(linha)["review_id"] for linha in linhas if linha.strip()}


def buscar_pendentes(
    con: duckdb.DuckDBPyConnection, feitas: set[str]
) -> list[dict[str, str | float]]:
    linhas = con.execute("SELECT review_id, rating, review_text FROM enrichment_sample").fetchall()
    return [
        {"review_id": str(rid), "rating": rating, "texto": texto}
        for rid, rating, texto in linhas
        if str(rid) not in feitas
    ]


def main(limite: int | None = None) -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    feitas = already_done(SAIDA)
    with duckdb.connect(str(BANCO), read_only=True) as con:
        pendentes = buscar_pendentes(con, feitas)
    if limite is not None:
        pendentes = pendentes[:limite]

    print(f"{len(feitas)} já processadas · {len(pendentes)} nesta rodada", flush=True)
    inicio = time.monotonic()
    with SAIDA.open("a", encoding="utf-8") as arquivo:
        for i, review in enumerate(pendentes, 1):
            resultado = extrair(review)
            if resultado is not None:
                arquivo.write(resultado.model_dump_json() + "\n")
                arquivo.flush()
            if i % 20 == 0 or i == len(pendentes):
                decorrido = time.monotonic() - inicio
                print(f"  [{i}/{len(pendentes)}] {decorrido / 60:.1f}min", flush=True)
    print("rodada concluída.", flush=True)


def carregar_no_banco() -> None:
    """Roda uma vez, quando a amostra inteira estiver processada — nunca a cada sessão de 2h."""
    with duckdb.connect(str(BANCO)) as con:
        con.execute(
            "CREATE OR REPLACE TABLE review_enriched AS SELECT * FROM read_json_auto(?)",
            [str(SAIDA)],
        )
    print("review_enriched criada no DuckDB.", flush=True)


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--carregar", action="store_true")
    args = parser.parse_args()
    if args.carregar:
        carregar_no_banco()
    else:
        main(args.limite)


if __name__ == "__main__":
    _cli()
