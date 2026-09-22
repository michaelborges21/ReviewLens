"""Garante que a estrutura de pacotes de src/bri importa sem erro."""

import bri
import bri.agent
import bri.data
import bri.guardrails
import bri.llm
import bri.nlp
import bri.retrieval
import bri.schemas

PACOTES = (
    bri,
    bri.data,
    bri.nlp,
    bri.retrieval,
    bri.agent,
    bri.llm,
    bri.guardrails,
    bri.schemas,
)


def test_pacotes_importam() -> None:
    for pacote in PACOTES:
        assert pacote.__doc__
