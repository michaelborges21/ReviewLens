"""Schema do rótulo de tópico (spec 02, etapa 4) — o que o LLM devolve ao ver um agrupamento."""

from pydantic import BaseModel, field_validator


class RotuloTopico(BaseModel):
    """Só prosa curta: o id, o tamanho e a coesão do tópico são calculados em Python."""

    rotulo: str
    descricao: str

    @field_validator("rotulo", "descricao", mode="after")
    @classmethod
    def _sem_espaco_sobrando(cls, valor: str) -> str:
        return " ".join(valor.split())
