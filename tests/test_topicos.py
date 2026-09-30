"""Testa o k-means dos tópicos: determinismo, separação e carga — sem tocar no modelo real."""

import json
from pathlib import Path

import duckdb
import numpy as np
import pytest

from bri.nlp import topicos
from bri.schemas.topicos import RotuloTopico

# Três aglomerados óbvios em 3 dimensões — a fixture inteira cabe na cabeça de quem lê o teste.
GRUPOS = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE review_chunks (chunk_id VARCHAR, chunk_text VARCHAR, embedding FLOAT[3])"
    )
    for grupo, (x, y, z) in enumerate(GRUPOS):
        for repeticao in range(4):
            ruido = 0.01 * repeticao
            con.execute(
                "INSERT INTO review_chunks VALUES (?, ?, ?)",
                [f"c{grupo}{repeticao}", f"texto do grupo {grupo}", [x + ruido, y, z]],
            )
    return con


def test_carregar_embeddings_deriva_a_dimensao_do_dado(con: duckdb.DuckDBPyConnection) -> None:
    """Nada de 768 fixo: a fixture usa 3 dimensões e o carregador tem que aceitar."""
    chunk_ids, matriz = topicos.carregar_embeddings(con)

    assert len(chunk_ids) == 12
    assert matriz.shape == (12, 3)
    assert np.allclose(np.linalg.norm(matriz, axis=1), 1.0)  # normalizados


def test_agrupar_e_deterministico_com_seed_fixa(con: duckdb.DuckDBPyConnection) -> None:
    _, matriz = topicos.carregar_embeddings(con)

    rotulos_a, centroides_a, _ = topicos.agrupar(matriz, 3)
    rotulos_b, centroides_b, _ = topicos.agrupar(matriz, 3)

    assert np.array_equal(rotulos_a, rotulos_b)
    assert np.allclose(centroides_a, centroides_b)


def test_agrupar_separa_grupos_obvios(con: duckdb.DuckDBPyConnection) -> None:
    _, matriz = topicos.carregar_embeddings(con)

    rotulos, _, _ = topicos.agrupar(matriz, 3)

    # cada bloco de 4 vetores consecutivos veio do mesmo aglomerado
    for inicio in (0, 4, 8):
        assert len(set(rotulos[inicio : inicio + 4].tolist())) == 1
    assert len(set(rotulos.tolist())) == 3


def test_grupos_desbalanceados_nao_colapsam_num_cluster_so() -> None:
    """Regressão: o centroide era somado sem normalizar dentro do laço, então a magnitude (=
    tamanho do cluster) decidia no lugar do ângulo e o maior grupo engolia tudo. Só aparece com
    grupos de tamanhos diferentes — com grupos iguais as magnitudes empatam e o bug se esconde."""
    grande = np.tile(np.array([1.0, 0.0, 0.0], dtype=np.float32), (10, 1))
    pequeno = np.tile(np.array([0.0, 1.0, 0.0], dtype=np.float32), (2, 1))
    matriz = np.vstack([grande, pequeno]).astype(np.float32)

    rotulos, _, _ = topicos.agrupar(matriz, 2)

    assert len(set(rotulos.tolist())) == 2, "todos os pontos caíram no mesmo cluster"
    assert len(set(rotulos[:10].tolist())) == 1
    assert len(set(rotulos[10:].tolist())) == 1


def test_cluster_vazio_e_reassentado_sem_quebrar(con: duckdb.DuckDBPyConnection) -> None:
    """k maior que o número de grupos distintos: o reassentamento tem que ser determinístico."""
    _, matriz = topicos.carregar_embeddings(con)

    rotulos_a, _, _ = topicos.agrupar(matriz, 6)
    rotulos_b, _, _ = topicos.agrupar(matriz, 6)

    assert np.array_equal(rotulos_a, rotulos_b)


def test_exemplares_devolve_os_mais_proximos_do_centroide(con: duckdb.DuckDBPyConnection) -> None:
    _, matriz = topicos.carregar_embeddings(con)
    rotulos, centroides, _ = topicos.agrupar(matriz, 3)

    indices = topicos.exemplares(matriz, rotulos, centroides, topico=0, n=2)

    assert len(indices) == 2
    assert all(rotulos[i] == 0 for i in indices)


def test_silhueta_amostrada_e_estavel_com_seed(con: duckdb.DuckDBPyConnection) -> None:
    _, matriz = topicos.carregar_embeddings(con)
    rotulos, _, _ = topicos.agrupar(matriz, 3)

    assert topicos.silhueta_amostrada(matriz, rotulos) == topicos.silhueta_amostrada(
        matriz, rotulos
    )


def test_rotular_usa_o_fake_e_devolve_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    resposta = json.dumps({"rotulo": "ritmo arrastado", "descricao": "Leitores citam lentidão."})
    monkeypatch.setattr(topicos.ollama, "gerar_json", lambda *a, **k: resposta)

    rotulo = topicos.rotular(["trecho um", "trecho dois"])

    assert rotulo == RotuloTopico(rotulo="ritmo arrastado", descricao="Leitores citam lentidão.")


def test_rotulo_malformado_nao_derruba_a_rodada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma resposta fora do schema deixa o tópico sem nome; não interrompe os outros 19."""
    monkeypatch.setattr(topicos.ollama, "gerar_json", lambda *a, **k: '{"nao_e": "o schema"}')

    assert topicos.rotular(["trecho"]) is None


def test_already_done_permite_retomar(tmp_path: Path) -> None:
    caminho = tmp_path / "topicos.jsonl"
    caminho.write_text('{"topic_id": 0}\n{"topic_id": 3}\n', encoding="utf-8")

    assert topicos.already_done(caminho) == {0, 3}
    assert topicos.already_done(tmp_path / "nao_existe.jsonl") == set()


def test_carregar_no_banco_cria_as_duas_tabelas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rotulos = tmp_path / "topicos.jsonl"
    rotulos.write_text(
        json.dumps(
            {
                "topic_id": 0,
                "rotulo": "ritmo",
                "descricao": "d",
                "n_chunks": 2,
                "coesao_media": 0.9,
                "k": 20,
                "seed": 42,
                "prompt_version": "0.1.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    atribuicoes = tmp_path / "chunk_topics.jsonl"
    atribuicoes.write_text(
        json.dumps({"chunk_id": "c1", "topic_id": 0, "similaridade": 0.9}) + "\n", encoding="utf-8"
    )
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(topicos, "SAIDA_ROTULOS", rotulos)
    monkeypatch.setattr(topicos, "SAIDA_ATRIBUICOES", atribuicoes)
    monkeypatch.setattr(topicos, "BANCO", banco)

    topicos.carregar_no_banco()

    with duckdb.connect(str(banco), read_only=True) as con:
        assert con.execute("SELECT rotulo, k, seed FROM topics").fetchone() == ("ritmo", 20, 42)
        assert con.execute("SELECT chunk_id FROM chunk_topics").fetchone() == ("c1",)
