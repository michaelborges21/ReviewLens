"""Schema do resumo por entidade (spec 02, etapa 5) — o que o LLM redige e o que a tabela guarda."""

from typing import Literal

from pydantic import BaseModel, field_validator

TipoEntidade = Literal["livro", "autor", "genero"]


class CitacaoNotavel(BaseModel):
    """review_id + trecho, com os nomes que a spec 02 declara (`quote`, não `trecho`)."""

    review_id: str
    quote: str


class ResumoRedigido(BaseModel):
    """A parte que o modelo escreve: só prosa. Nenhum número, nenhum contador.

    É este schema — não `EntitySummary` — que vai ao `format` do Ollama. Com a contagem fora da
    saída estruturada, o modelo fica **incapaz de inventá-la**: um número em campo estruturado
    não passaria pelo guardrail de números, que só varre prosa. Mesma doutrina da ADR-004:
    restringir a decodificação em vez de corrigir depois.
    """

    headline: str
    strengths: list[str]
    weaknesses: list[str]
    notable_quotes: list[CitacaoNotavel]

    @field_validator("notable_quotes", mode="after")
    @classmethod
    def _uma_por_review(cls, citacoes: list[CitacaoNotavel]) -> list[CitacaoNotavel]:
        """Mesmo motivo de RespostaNarrada: a tela mostra um cartão por citação, e o modelo
        repete a mesma review uma vez por afirmação se ninguém impedir."""
        vistas: dict[str, CitacaoNotavel] = {}
        for citacao in citacoes:
            vistas.setdefault(citacao.review_id, citacao)
        return list(vistas.values())


class EntitySummary(ResumoRedigido):
    """A linha de `entity_summaries`. Os quatro campos abaixo vêm do Python, nunca do modelo."""

    entity_type: TipoEntidade
    entity_id: str
    n_reviews_considered: int
    prompt_version: str
