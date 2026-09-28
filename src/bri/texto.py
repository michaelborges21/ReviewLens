"""Normalização de texto usada pelo roteador e pela validação de saída do LLM."""

import unicodedata


def sem_acento(texto: str) -> str:
    """Minúsculas e sem diacrítico — para comparar o que o usuário ou o modelo escreveu."""
    normalizado = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")
