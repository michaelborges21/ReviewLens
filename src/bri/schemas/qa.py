"""Schema da resposta que o LLM redige no chat (spec 04) — validado antes de chegar à tela."""

from typing import Literal

from pydantic import BaseModel, field_validator

from bri.texto import sem_acento

CANONICOS = {"alta": "alta", "media": "média", "baixa": "baixa"}


class Citacao(BaseModel):
    """Trecho de leitor com o review_id de onde saiu — o id é o que o guardrail confere."""

    review_id: str
    trecho: str


class RespostaNarrada(BaseModel):
    resposta: str
    citacoes: list[Citacao]
    confianca: Literal["alta", "média", "baixa"]
    proximas_perguntas: list[str]

    @field_validator("citacoes", mode="after")
    @classmethod
    def _uma_citacao_por_review(cls, citacoes: list[Citacao]) -> list[Citacao]:
        """O modelo repete o mesmo review; a tela mostraria o cartão duas vezes."""
        unicas: dict[str, Citacao] = {}
        for citacao in citacoes:
            unicas.setdefault(citacao.review_id, citacao)
        return list(unicas.values())

    @field_validator("confianca", mode="before")
    @classmethod
    def _normalizar_confianca(cls, valor: object) -> object:
        """O modelo varia a grafia; sem isto um acento descartava a resposta inteira."""
        if not isinstance(valor, str):
            return valor
        return CANONICOS.get(sem_acento(valor.strip()), valor)
