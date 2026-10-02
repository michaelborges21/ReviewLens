"""Cliente mínimo para o Ollama local (ADR-004: gemma4:12b, sem chave de API)."""

import json
import os
import urllib.request
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11435")
# Modelo por variável de ambiente, igual à URL. A ADR-004 escolheu gemma4:12b medindo, então ele
# segue sendo o padrão — mas rodar em máquina sem GPU, ou repetir a medição com outro modelo, não
# deveria exigir editar código.
MODELO_PADRAO = os.environ.get("OLLAMA_MODELO", "gemma4:12b")
EMBEDDING_MODELO_PADRAO = os.environ.get("OLLAMA_MODELO_EMBEDDING", "embeddinggemma")


def _pedir(rota: str, corpo: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST em JSON para uma rota do Ollama. OSError sobe para o chamador decidir."""
    requisicao = urllib.request.Request(
        f"{OLLAMA_URL}/{rota}",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        dados: dict[str, Any] = json.loads(resposta.read())
    return dados


def gerar_json(
    sistema: str,
    prompt: str,
    schema: dict[str, Any],
    modelo: str = MODELO_PADRAO,
    timeout: int = 300,
) -> str:
    """Chama /api/generate com saída restrita ao schema e thinking desligado.

    Achado dos pilotos: sem as duas coisas, o mesmo modelo caiu de 100% para 33% de acerto
    no enum e ficou 7,8x mais lento.
    """
    dados = _pedir(
        "api/generate",
        {
            "model": modelo,
            "system": sistema,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": 0.1},
        },
        timeout,
    )
    return str(dados["response"])


def embedding(texto: str, modelo: str = EMBEDDING_MODELO_PADRAO, timeout: int = 30) -> list[float]:
    """Chama /api/embeddings.

    Timeout bem menor que gerar_json: medido em 5ms por chamada com o modelo já carregado; 30s
    cobre folgadamente a troca de modelo na GPU (medida em 1,36s), sem herdar os 300s do batch.
    """
    dados = _pedir("api/embeddings", {"model": modelo, "prompt": texto}, timeout)
    return [float(v) for v in dados["embedding"]]
