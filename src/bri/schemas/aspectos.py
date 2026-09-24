"""Schema de saída da extração de aspectos (spec 02) — fonte única das 9 categorias válidas."""

from typing import Literal

from pydantic import BaseModel

Aspecto = Literal[
    "enredo",
    "personagens",
    "ritmo",
    "final",
    "escrita",
    "tradução",
    "edição_física",
    "preço",
    "outro",
]
Sentimento = Literal["positivo", "negativo", "neutro", "misto"]


class AspectoCitado(BaseModel):
    aspect: Aspecto
    sentiment: Sentimento
    evidence: str


class ReviewEnrichment(BaseModel):
    review_id: str
    aspects: list[AspectoCitado]
    is_recommendation: bool | None
