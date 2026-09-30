"""Tópicos por k-means sobre os embeddings já existentes (spec 02, etapa 4 · ADR-016).

Sem BERTopic: os 22.006 vetores de `review_chunks` foram pagos na rodada de RAG, e a silhueta
medida (~0,02 em todo k de 8 a 60) não sustenta HDBSCAN — devolveria a maioria como ruído, ao
custo de três dependências novas. A saída é **tema exploratório**, não "o tópico da review".
"""

import argparse
import json
from pathlib import Path
from typing import Any, cast

import duckdb
import numpy as np
from numpy.typing import NDArray
from pydantic import ValidationError

from bri.data.process import BANCO
from bri.llm import ollama, prompts
from bri.schemas.topicos import RotuloTopico

SAIDA_ROTULOS = Path("data/interim/topicos.jsonl")
SAIDA_ATRIBUICOES = Path("data/interim/chunk_topics.jsonl")
RELATORIO = Path("reports/topicos.md")

SEED = 42  # mesma semente de toda amostragem do projeto
K_CANDIDATOS = (8, 12, 16, 20, 24, 30, 40, 60)
K_PADRAO = 20  # escolhido por medição, não por gosto — ver reports/topicos.md e ADR-016
MAX_ITERACOES = 100  # 40 não convergiu por estabilidade de rótulo em nenhum k medido
N_EXEMPLARES = 8
SUBAMOSTRA_SILHUETA = 3000
MAX_CHARS_EXEMPLAR = 400

_PROMPT = prompts.carregar("rotular_topico")
SCHEMA = RotuloTopico.model_json_schema()

Matriz = NDArray[np.float32]


def carregar_embeddings(con: duckdb.DuckDBPyConnection) -> tuple[list[str], Matriz]:
    """Traz os vetores para numpy por Arrow — 22.006×768 em ~0,2s, contra minutos linha a linha.

    A dimensão vem do dado (`reshape(n, -1)`), não de um 768 fixo: é o que deixa o teste usar
    vetores de 3 dimensões em vez de fabricar 768 floats por linha.
    """
    tabela = (
        con.execute("SELECT chunk_id, embedding FROM review_chunks ORDER BY chunk_id")
        .arrow()
        .read_all()
    )
    chunk_ids = [str(c) for c in tabela.column("chunk_id").to_pylist()]
    plano = tabela.column("embedding").combine_chunks().flatten().to_numpy(zero_copy_only=False)
    matriz = cast(Matriz, plano.astype(np.float32).reshape(tabela.num_rows, -1))
    return chunk_ids, _normalizar(matriz)


def _normalizar(matriz: Matriz) -> Matriz:
    """Cosseno vira produto interno. Os vetores do embeddinggemma já chegam unitários; normalizar
    de novo é barato e evita depender disso silenciosamente."""
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return cast(Matriz, matriz / normas)


def _centroides_iniciais(matriz: Matriz, k: int, gerador: np.random.Generator) -> Matriz:
    """k-means++ : o primeiro ponto é sorteado, os demais saem proporcionais à distância ao mais
    próximo já escolhido. Toda aleatoriedade vem do gerador semeado, nada de global."""
    escolhidos = [int(gerador.integers(matriz.shape[0]))]
    for _ in range(1, k):
        similaridade = matriz @ matriz[escolhidos].T
        distancia = 1.0 - similaridade.max(axis=1)
        distancia = np.clip(distancia, 0.0, None) ** 2
        total = float(distancia.sum())
        if total <= 0:
            escolhidos.append(int(gerador.integers(matriz.shape[0])))
            continue
        escolhidos.append(int(gerador.choice(matriz.shape[0], p=distancia / total)))
    return matriz[escolhidos].copy()


def agrupar(matriz: Matriz, k: int, seed: int = SEED) -> tuple[NDArray[np.int32], Matriz, int]:
    """k-means esférico determinístico. Devolve rótulos, centroides e iterações efetivas.

    Quatro detalhes sustentam o "seed 42": o gerador é local, o k-means++ deriva só dele, o empate
    de argmax cai no menor índice (comportamento estável do numpy) e cluster vazio é reassentado
    no ponto de menor similaridade ao próprio centroide — escolha determinística, não sorteio.
    """
    gerador = np.random.default_rng(seed)
    centroides = _centroides_iniciais(matriz, k, gerador)
    rotulos = np.zeros(matriz.shape[0], dtype=np.int32)

    iteracoes = 0
    for iteracoes in range(1, MAX_ITERACOES + 1):
        novos = cast(NDArray[np.int32], np.argmax(matriz @ centroides.T, axis=1).astype(np.int32))
        if iteracoes > 1 and np.array_equal(novos, rotulos):
            break
        rotulos = novos
        for grupo in range(k):
            membros = matriz[rotulos == grupo]
            if membros.shape[0] == 0:
                pior = int(np.argmin((matriz * centroides[rotulos]).sum(axis=1)))
                centroides[grupo] = matriz[pior]
                continue
            centroides[grupo] = membros.sum(axis=0)
        # Normalizar DENTRO do laço, não só no fim: a atribuição é produto interno, então
        # centroide não unitário faz a magnitude (= tamanho do cluster) decidir no lugar do
        # ângulo, e o maior cluster engole todos os pontos. Medido: sem isto, todo k colapsa
        # em um único grupo de 22.006.
        centroides = _normalizar(centroides)
    return rotulos, centroides, iteracoes


def coesao_media(matriz: Matriz, rotulos: NDArray[np.int32], centroides: Matriz) -> float:
    """Similaridade média de cada ponto ao seu centroide. Sobe sempre com k — não escolhe k."""
    return float((matriz * centroides[rotulos]).sum(axis=1).mean())


def silhueta_amostrada(
    matriz: Matriz, rotulos: NDArray[np.int32], seed: int = SEED, n: int = SUBAMOSTRA_SILHUETA
) -> float:
    """Silhueta de cosseno numa subamostra fixa: o cálculo completo é O(n²) em 22 mil pontos."""
    gerador = np.random.default_rng(seed)
    total = matriz.shape[0]
    indices = np.arange(total) if total <= n else gerador.choice(total, size=n, replace=False)
    amostra, rotulos_amostra = matriz[indices], rotulos[indices]
    distancias = 1.0 - amostra @ amostra.T
    np.fill_diagonal(distancias, np.nan)

    valores: list[float] = []
    for grupo in np.unique(rotulos_amostra):
        dentro = rotulos_amostra == grupo
        if int(dentro.sum()) < 2:
            continue
        a = np.nanmean(distancias[np.ix_(dentro, dentro)], axis=1)
        fora = [
            np.nanmean(distancias[np.ix_(dentro, rotulos_amostra == outro)], axis=1)
            for outro in np.unique(rotulos_amostra)
            if outro != grupo
        ]
        if not fora:
            continue
        b = np.min(np.vstack(fora), axis=0)
        valores.extend(((b - a) / np.maximum(a, b)).tolist())
    return float(np.mean(valores)) if valores else 0.0


def medir_k(matriz: Matriz, candidatos: tuple[int, ...] = K_CANDIDATOS) -> list[dict[str, Any]]:
    """Varredura de k — ~1s por k. É o que justifica K_PADRAO por medição, não por chute."""
    medidas = []
    for k in candidatos:
        rotulos, centroides, iteracoes = agrupar(matriz, k)
        tamanhos = np.bincount(rotulos, minlength=k)
        medidas.append(
            {
                "k": k,
                "coesao": round(coesao_media(matriz, rotulos, centroides), 4),
                "silhueta": round(silhueta_amostrada(matriz, rotulos), 4),
                "menor_cluster": int(tamanhos.min()),
                "maior_cluster": int(tamanhos.max()),
                "iteracoes": iteracoes,
            }
        )
    return medidas


def escrever_relatorio(medidas: list[dict[str, Any]], destino: Path = RELATORIO) -> None:
    linhas = [
        "# Escolha de k para os tópicos (spec 02, etapa 4 · ADR-016)",
        "",
        f"k-means esférico sobre os embeddings de `review_chunks`, seed {SEED}, silhueta de "
        f"cosseno em subamostra fixa de {SUBAMOSTRA_SILHUETA}.",
        "",
        "| k | coesão | silhueta | menor cluster | maior cluster | iterações |",
        "|---|---|---|---|---|---|",
    ]
    linhas += [
        f"| {m['k']} | {m['coesao']:.4f} | {m['silhueta']:+.4f} | {m['menor_cluster']} | "
        f"{m['maior_cluster']} | {m['iteracoes']} |"
        for m in medidas
    ]
    linhas += [
        "",
        "**Como ler.** A coesão sobe monotonicamente com k — é assim que ela se comporta sempre, "
        "então sozinha não escolhe nada. O que decide é a silhueta, e ela fica na casa de 0,02 em "
        "todo o intervalo: as avaliações **não formam agrupamentos disjuntos** neste espaço. Isso "
        "é propriedade do dado, não defeito do método, e é a razão de a saída se chamar *tema "
        "exploratório* em vez de *o tópico da review*.",
        "",
        f"`K_PADRAO = {K_PADRAO}`: silhueta em platô, menor cluster acima de algumas centenas "
        "(abaixo disso o rótulo sai de amostra rala) e um número de temas que um humano revisa "
        "numa sentada — a spec 02 exige revisão humana dos rótulos.",
        "",
    ]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas), encoding="utf-8")


def exemplares(
    matriz: Matriz,
    rotulos: NDArray[np.int32],
    centroides: Matriz,
    topico: int,
    n: int = N_EXEMPLARES,
) -> list[int]:
    """Índices dos n chunks mais próximos do centroide — o que melhor representa o tema."""
    indices = np.flatnonzero(rotulos == topico)
    if indices.size == 0:
        return []
    similaridade = matriz[indices] @ centroides[topico]
    return [int(i) for i in indices[np.argsort(-similaridade)[:n]]]


def rotular(trechos: list[str]) -> RotuloTopico | None:
    """None quando o modelo devolve algo fora do schema — a rodada segue, o tópico fica sem nome."""
    bloco = "\n".join(f"<chunk>{t[:MAX_CHARS_EXEMPLAR]}</chunk>" for t in trechos)
    try:
        bruto = ollama.gerar_json(_PROMPT.sistema, _PROMPT.montar(trechos=bloco), SCHEMA)
        return RotuloTopico.model_validate_json(bruto)
    except (OSError, ValidationError):
        return None


def already_done(caminho: Path) -> set[int]:
    if not caminho.exists():
        return set()
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return {json.loads(linha)["topic_id"] for linha in linhas if linha.strip()}


def main(k: int = K_PADRAO, medir: bool = False) -> None:
    with duckdb.connect(str(BANCO), read_only=True) as con:
        chunk_ids, matriz = carregar_embeddings(con)
        textos = [
            str(t)
            for (t,) in con.execute(
                "SELECT chunk_text FROM review_chunks ORDER BY chunk_id"
            ).fetchall()
        ]
    print(f"{matriz.shape[0]} chunks, {matriz.shape[1]} dimensões", flush=True)

    if medir:
        escrever_relatorio(medir_k(matriz))
        print(f"medição escrita em {RELATORIO}", flush=True)
        return

    rotulos, centroides, iteracoes = agrupar(matriz, k)
    print(f"k={k}, {iteracoes} iterações", flush=True)

    SAIDA_ATRIBUICOES.parent.mkdir(parents=True, exist_ok=True)
    similaridades = (matriz * centroides[rotulos]).sum(axis=1)
    with SAIDA_ATRIBUICOES.open("w", encoding="utf-8") as arquivo:
        for chunk_id, topico, similaridade in zip(chunk_ids, rotulos, similaridades, strict=True):
            arquivo.write(
                json.dumps(
                    {
                        "chunk_id": chunk_id,
                        "topic_id": int(topico),
                        "similaridade": round(float(similaridade), 4),
                    }
                )
                + "\n"
            )

    feitos = already_done(SAIDA_ROTULOS)
    with SAIDA_ROTULOS.open("a", encoding="utf-8") as arquivo:
        for topico in range(k):
            if topico in feitos:
                continue
            indices = exemplares(matriz, rotulos, centroides, topico)
            rotulo = rotular([textos[i] for i in indices])
            membros = int((rotulos == topico).sum())
            arquivo.write(
                json.dumps(
                    {
                        "topic_id": topico,
                        "rotulo": rotulo.rotulo if rotulo else "sem rótulo",
                        "descricao": rotulo.descricao if rotulo else "",
                        "n_chunks": membros,
                        "coesao_media": round(float(similaridades[rotulos == topico].mean()), 4),
                        "k": k,
                        "seed": SEED,
                        "prompt_version": _PROMPT.versao,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            arquivo.flush()
            print(f"  [{topico + 1}/{k}] {rotulo.rotulo if rotulo else 'sem rótulo'}", flush=True)
    print("rodada concluída.", flush=True)


def carregar_no_banco() -> None:
    """Relê os dois JSONL — rótulo corrigido à mão entra no banco sem recomputar agrupamento."""
    with duckdb.connect(str(BANCO)) as con:
        con.execute(
            "CREATE OR REPLACE TABLE topics AS SELECT * FROM read_json_auto(?)",
            [str(SAIDA_ROTULOS)],
        )
        con.execute(
            "CREATE OR REPLACE TABLE chunk_topics AS SELECT * FROM read_json_auto(?)",
            [str(SAIDA_ATRIBUICOES)],
        )
    print("topics e chunk_topics criadas no DuckDB.", flush=True)


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=K_PADRAO)
    parser.add_argument("--medir", action="store_true")
    parser.add_argument("--carregar", action="store_true")
    args = parser.parse_args()
    if args.carregar:
        carregar_no_banco()
        return
    main(k=args.k, medir=args.medir)


if __name__ == "__main__":
    _cli()
