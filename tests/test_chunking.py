"""Testa a divisão de review longa em chunks — lógica pura, sem DuckDB nem Ollama."""

from bri.retrieval.chunking import LIMITE_CHUNK, OVERLAP, dividir_em_chunks


def test_texto_curto_vira_um_chunk_identico() -> None:
    texto = "review curta, sem necessidade de dividir."

    assert dividir_em_chunks(texto) == [texto]


def test_texto_vazio_nao_gera_chunk() -> None:
    assert dividir_em_chunks("") == []


def test_texto_longo_e_dividido_com_overlap() -> None:
    texto = "x" * 5000

    chunks = dividir_em_chunks(texto)

    assert len(chunks) > 1
    assert all(len(c) <= LIMITE_CHUNK for c in chunks)
    # o fim de um chunk e o início do próximo se sobrepõem em OVERLAP caracteres
    for anterior, seguinte in zip(chunks, chunks[1:], strict=False):
        assert anterior[-OVERLAP:] == seguinte[:OVERLAP]


def test_chunks_cobrem_o_texto_inteiro_sem_buraco() -> None:
    texto = "".join(f"{i:04d}" for i in range(1500))  # 6000 chars distintos, fácil de rastrear

    chunks = dividir_em_chunks(texto)

    reconstruido = chunks[0]
    for chunk in chunks[1:]:
        reconstruido += chunk[OVERLAP:]
    assert reconstruido == texto


def test_texto_exatamente_no_limite_nao_divide() -> None:
    texto = "x" * LIMITE_CHUNK

    assert dividir_em_chunks(texto) == [texto]
