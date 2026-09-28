"""Confere se o modelo citou só review_ids que estavam no contexto enviado (specs 03 e 05)."""

from bri.schemas.qa import Citacao


def citacoes_invalidas(citacoes: list[Citacao], ids_enviados: set[str]) -> list[str]:
    """review_ids citados que não foram enviados ao modelo — ou seja, inventados.

    Lista vazia significa resposta fundamentada. Citação nenhuma também é válida: pergunta de
    números gerais não tem o que citar.
    """
    inventados = (c.review_id for c in citacoes if c.review_id not in ids_enviados)
    return list(dict.fromkeys(inventados))
