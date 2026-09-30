"""Resumo por entidade (spec 02, etapa 5) — batch fracionável, retomável entre sessões.

Não é a cascata map-reduce que a spec desenhava: a agregação de aspectos em SQL já é o passo
"map" e é pré-computada, e 9 aspectos mais uma dúzia de citações cabem folgados na janela — então
o "reduce" é uma chamada por entidade. Escopo do primeiro passe: autor e gênero, livros fora.
"""

import argparse
import json
import time
from itertools import zip_longest
from pathlib import Path
from typing import Any, Literal

import duckdb
from pydantic import ValidationError

from bri.data import consultas
from bri.data.process import BANCO
from bri.guardrails.citacoes import citacoes_invalidas
from bri.guardrails.numeros import numeros_invalidos
from bri.llm import ollama, prompts
from bri.schemas.qa import Citacao
from bri.schemas.resumo import CitacaoNotavel, EntitySummary, ResumoRedigido

SAIDA = Path("data/interim/resumos.jsonl")
LOG_DESCARTES = Path("reports/resumos_descartados.jsonl")

# spec 09, doutrina de loops: verificador determinístico, limite de iterações, e o que fazer ao
# estourar. Mesmo número da extração de aspectos e da narração.
MAX_TENTATIVAS = 2
PISO_REVIEWS = 20  # 75 autores e 63 gêneros atingem — medido
MAX_CITACOES = 12

SCHEMA = ResumoRedigido.model_json_schema()
_PROMPT = prompts.carregar("summarize")

Tipo = Literal["autor", "genero"]


def chave(tipo: str, entidade: str) -> str:
    """A chave é o par: "Fiction" é gênero e pode ser nome de autor."""
    return f"{tipo}|{entidade}"


def registrar_descarte(tipo: str, entidade: str, motivo: str, detalhe: object) -> None:
    LOG_DESCARTES.parent.mkdir(parents=True, exist_ok=True)
    with LOG_DESCARTES.open("a", encoding="utf-8") as arquivo:
        arquivo.write(
            json.dumps(
                {"entidade": chave(tipo, entidade), "motivo": motivo, "detalhe": detalhe},
                ensure_ascii=False,
            )
            + "\n"
        )


def already_done(caminho: Path) -> set[str]:
    """As entidades já gravadas — reabrir depois de uma sessão não reprocessa nada."""
    if not caminho.exists():
        return set()
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return {
        chave(json.loads(linha)["entity_type"], json.loads(linha)["entity_id"])
        for linha in linhas
        if linha.strip()
    }


def entidades_elegiveis(
    con: duckdb.DuckDBPyConnection, piso: int = PISO_REVIEWS
) -> list[tuple[Tipo, str]]:
    """Autores e gêneros com avaliações analisadas suficientes, em ordem estável."""
    tipos: tuple[Tipo, ...] = ("autor", "genero")
    return [
        (tipo, entidade)
        for tipo in tipos
        for entidade, _ in consultas.entidades_com_aspectos(con, tipo, piso)
    ]


def _intercalar_por_sentimento(citacoes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alterna negativa e positiva, para que o corte em MAX_CITACOES não zere um dos lados."""
    negativas = [c for c in citacoes if c["sentimento"] == "negativo"]
    positivas = [c for c in citacoes if c["sentimento"] == "positivo"]
    intercaladas: list[dict[str, Any]] = []
    for negativa, positiva in zip_longest(negativas, positivas):
        intercaladas += [c for c in (negativa, positiva) if c is not None]
    return intercaladas


def _blocos(citacoes: list[dict[str, Any]]) -> tuple[str, set[str], dict[str, str]]:
    """Monta os <review> do prompt, os ids enviados e o trecho original de cada id.

    Cada bloco leva `aspecto` e `sentimento`: sem eles o modelo escolhe a citação por proximidade
    de texto e acaba sustentando uma afirmação sobre narrativa com um trecho sobre a capa —
    observado no piloto com Ayn Rand.

    A escolha **intercala** negativa e positiva em vez de cortar a cabeça da lista: a consulta
    devolve os dois lados equilibrados, mas ordenados por sentimento, e "negativo" vem antes de
    "positivo" no alfabeto. Cortar as 12 primeiras mandava 12 negativas e zero positivas — e os
    resumos saíam sem nenhum ponto forte, sem que o dado justificasse isso.
    """
    escolhidas = _intercalar_por_sentimento(citacoes)[:MAX_CITACOES]
    blocos = "\n".join(
        f'<review id="{c["review_id"]}" aspecto="{c["aspecto"]}" '
        f'sentimento="{c["sentimento"]}">{c["trecho"]}</review>'
        for c in escolhidas
    )
    originais = {str(c["review_id"]): str(c["trecho"]) for c in escolhidas}
    return blocos, set(originais), originais


def _linhas_de_aspectos(aspectos: dict[str, Any]) -> str:
    return "\n".join(
        f"{a['aspecto']} n_mencoes={a['n_mencoes']} pct_negativo={a['pct_negativo']:.0f}"
        for a in aspectos["aspectos"]
    )


def _quotes_literais(
    resumo: ResumoRedigido, originais: dict[str, str]
) -> tuple[list[CitacaoNotavel], list[str]]:
    """Mantém só as citações copiadas de verdade — parafrasear é a falha que `extract` já viu."""
    mantidas, descartadas = [], []
    for citacao in resumo.notable_quotes:
        original = originais.get(citacao.review_id, "")
        if " ".join(citacao.quote.split()) in " ".join(original.split()):
            mantidas.append(citacao)
        else:
            descartadas.append(citacao.quote)
    return mantidas, descartadas


def resumir(con: duckdb.DuckDBPyConnection, tipo: Tipo, entidade: str) -> EntitySummary | None:
    """Chama o modelo até MAX_TENTATIVAS; devolve None quando nada passa pelos verificadores."""
    aspectos = (
        consultas.aspectos_do_autor(con, entidade)
        if tipo == "autor"
        else consultas.aspectos_do_genero(con, entidade)
    )
    citacoes = consultas.citacoes_da_entidade(con, tipo, entidade)
    if not aspectos["aspectos"] or not citacoes:
        registrar_descarte(tipo, entidade, "sem_aspecto_ou_citacao", len(citacoes))
        return None

    blocos, ids_enviados, originais = _blocos(citacoes)
    contexto_numerico = _linhas_de_aspectos(aspectos)
    correcao = ""

    for _ in range(MAX_TENTATIVAS):
        prompt = _PROMPT.montar(
            tipo=tipo, entidade=entidade, aspectos=contexto_numerico, citacoes=blocos + correcao
        )
        try:
            bruto = ollama.gerar_json(_PROMPT.sistema, prompt, SCHEMA)
            redigido = ResumoRedigido.model_validate_json(bruto)
        except (OSError, ValidationError) as erro:
            registrar_descarte(tipo, entidade, "schema_invalido", str(erro)[:200])
            continue

        inventados = citacoes_invalidas(
            [Citacao(review_id=c.review_id, trecho=c.quote) for c in redigido.notable_quotes],
            ids_enviados,
        )
        if inventados:
            correcao = (
                f"\n<correcao>Cite apenas estes ids: {', '.join(sorted(ids_enviados))}.</correcao>"
            )
            registrar_descarte(tipo, entidade, "citacao_inventada", inventados)
            continue

        prosa = " ".join([redigido.headline, *redigido.strengths, *redigido.weaknesses])
        fora = numeros_invalidos(prosa, contexto_numerico)
        if fora.inventados:
            registrar_descarte(tipo, entidade, "numero_impossivel", fora.inventados)
            return None
        if fora.suspeitos:
            correcao = "\n<correcao>Não escreva número nenhum na prosa.</correcao>"
            registrar_descarte(tipo, entidade, "numero_sem_lastro", fora.suspeitos)
            continue

        mantidas, parafraseadas = _quotes_literais(redigido, originais)
        if parafraseadas:
            registrar_descarte(tipo, entidade, "quote_nao_literal", parafraseadas)
        if not mantidas:
            registrar_descarte(tipo, entidade, "sem_citacao_valida", len(redigido.notable_quotes))
            return None

        return EntitySummary(
            headline=redigido.headline,
            strengths=redigido.strengths,
            weaknesses=redigido.weaknesses,
            notable_quotes=mantidas,
            entity_type=tipo,
            entity_id=entidade,
            n_reviews_considered=aspectos["avaliacoes_analisadas"],
            prompt_version=_PROMPT.versao,
        )
    return None


def main(limite: int | None = None) -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    feitas = already_done(SAIDA)
    with duckdb.connect(str(BANCO), read_only=True) as con:
        pendentes = [
            (tipo, entidade)
            for tipo, entidade in entidades_elegiveis(con)
            if chave(tipo, entidade) not in feitas
        ]
        if limite is not None:
            pendentes = pendentes[:limite]
        print(f"{len(feitas)} já resumidas · {len(pendentes)} nesta rodada", flush=True)

        inicio = time.monotonic()
        with SAIDA.open("a", encoding="utf-8") as arquivo:
            for i, (tipo, entidade) in enumerate(pendentes, 1):
                resumo = resumir(con, tipo, entidade)
                if resumo is not None:
                    arquivo.write(resumo.model_dump_json() + "\n")
                    arquivo.flush()
                if i % 10 == 0 or i == len(pendentes):
                    print(
                        f"  [{i}/{len(pendentes)}] {(time.monotonic() - inicio) / 60:.1f}min",
                        flush=True,
                    )
    print("rodada concluída.", flush=True)


def carregar_no_banco() -> None:
    """Colunas explícitas: 138 linhas não dão margem para o inferidor de tipos do read_json_auto
    acertar `notable_quotes` se a primeira leva vier com lista vazia."""
    with duckdb.connect(str(BANCO)) as con:
        con.execute(
            """
            CREATE OR REPLACE TABLE entity_summaries AS SELECT * FROM read_json(?, columns = {
                headline: 'VARCHAR', strengths: 'VARCHAR[]', weaknesses: 'VARCHAR[]',
                notable_quotes: 'STRUCT(review_id VARCHAR, quote VARCHAR)[]',
                entity_type: 'VARCHAR', entity_id: 'VARCHAR',
                n_reviews_considered: 'INTEGER', prompt_version: 'VARCHAR'
            })
            """,
            [str(SAIDA)],
        )
    print("entity_summaries criada no DuckDB.", flush=True)


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--carregar", action="store_true")
    args = parser.parse_args()
    if args.carregar:
        carregar_no_banco()
        return
    main(limite=args.limite)


if __name__ == "__main__":
    _cli()
