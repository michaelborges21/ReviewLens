"""Baixa no Ollama os modelos que o projeto usa — o passo que falta entre subir o container e usar.

Os nomes vêm de `ollama.py`, não de uma lista própria: o modelo é configurável por ambiente
(ADR-021), e uma segunda lista aqui baixaria o modelo errado quando alguém trocasse a variável.

Idempotente de propósito: são ~8,8GB somados, e o compose chama isto em todo `up`.
"""

import json
import sys
import time
import urllib.error
import urllib.request

from bri.llm.ollama import EMBEDDING_MODELO_PADRAO, MODELO_PADRAO, OLLAMA_URL

TIMEOUT_DOWNLOAD = 3600  # 8,8GB em rede doméstica passa folgado de 10 min
TENTATIVAS_ATE_RESPONDER = 30
ESPERA_ENTRE_TENTATIVAS = 2


def modelos_instalados() -> set[str]:
    """Nomes já presentes no Ollama, com e sem o sufixo `:latest`.

    O Ollama guarda `embeddinggemma` como `embeddinggemma:latest`, então comparar o nome cru
    acusaria falta de um modelo que está ali.
    """
    requisicao = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
    with urllib.request.urlopen(requisicao, timeout=30) as resposta:
        dados = json.loads(resposta.read())
    nomes: set[str] = set()
    for modelo in dados.get("models", []):
        nome = str(modelo["name"])
        nomes.add(nome)
        nomes.add(nome.removesuffix(":latest"))
    return nomes


def esperar_ollama() -> bool:
    """Espera o Ollama responder. O healthcheck do compose já cobre isso; aqui é para quem roda
    o script na mão, antes de o serviço ter subido."""
    for tentativa in range(TENTATIVAS_ATE_RESPONDER):
        try:
            modelos_instalados()
            return True
        except (OSError, urllib.error.URLError):
            if tentativa == 0:
                print(f"esperando o Ollama responder em {OLLAMA_URL}...", flush=True)
            time.sleep(ESPERA_ENTRE_TENTATIVAS)
    return False


def _tamanho(bytes_: int) -> str:
    """GB só quando é GB — uma camada de 45MB mostrada como `0.0GB` parece download quebrado."""
    return f"{bytes_ / 1e9:.1f}GB" if bytes_ >= 1e9 else f"{round(bytes_ / 1e6)}MB"


def _progresso(linha: dict[str, object]) -> str:
    """Uma linha curta de status. Sem barra animada: a saída vai para log de container."""
    status = str(linha.get("status", ""))
    total, completo = linha.get("total"), linha.get("completed")
    if isinstance(total, int) and isinstance(completo, int) and total > 0:
        return f"  {status} — {100 * completo // total}% de {_tamanho(total)}"
    return f"  {status}"


def baixar(modelo: str) -> None:
    """Puxa um modelo, imprimindo o andamento. Levanta OSError se o Ollama recusar."""
    corpo = json.dumps({"model": modelo, "stream": True}).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{OLLAMA_URL}/api/pull", data=corpo, headers={"Content-Type": "application/json"}
    )
    ultimo = ""
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT_DOWNLOAD) as resposta:
        for bruta in resposta:
            if not bruta.strip():
                continue
            linha = json.loads(bruta)
            if erro := linha.get("error"):
                raise OSError(f"Ollama recusou {modelo}: {erro}")
            # só imprime quando a mensagem muda: o stream manda centenas de linhas por segundo
            if (texto := _progresso(linha)) != ultimo:
                print(texto, flush=True)
                ultimo = texto


def main() -> int:
    desejados = [MODELO_PADRAO, EMBEDDING_MODELO_PADRAO]
    if not esperar_ollama():
        print(f"Ollama não respondeu em {OLLAMA_URL}. Ele está rodando?", file=sys.stderr)
        return 1

    instalados = modelos_instalados()
    for modelo in desejados:
        if modelo in instalados:
            print(f"[ok] {modelo} já está baixado", flush=True)
            continue
        print(f"[baixando] {modelo}", flush=True)
        try:
            baixar(modelo)
        except OSError as erro:
            print(f"falhou ao baixar {modelo}: {erro}", file=sys.stderr)
            return 1
        print(f"[ok] {modelo}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
