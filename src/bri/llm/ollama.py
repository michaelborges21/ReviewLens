"""Cliente mínimo para o Ollama local (ADR-004: gemma4:12b, sem chave de API)."""

import json
import os
import urllib.request
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11435")
MODELO_PADRAO = "gemma4:12b"
EMBEDDING_MODELO_PADRAO = "embeddinggemma"


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
    corpo = json.dumps(
        {
            "model": modelo,
            "system": sistema,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=corpo, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        dados = json.loads(resposta.read())
    return str(dados["response"])


def embedding(texto: str, modelo: str = EMBEDDING_MODELO_PADRAO, timeout: int = 30) -> list[float]:
    """Chama /api/embeddings. OSError sobe para o chamador decidir, igual gerar_json.

    Timeout bem menor que gerar_json: medido em 5ms por chamada com o modelo já carregado; 30s
    cobre folgadamente a troca de modelo na GPU (medida em 1,36s), sem herdar os 300s do batch.
    """
    corpo = json.dumps({"model": modelo, "prompt": texto}).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings", data=corpo, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        dados = json.loads(resposta.read())
    return [float(v) for v in dados["embedding"]]
