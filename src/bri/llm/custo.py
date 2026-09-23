"""Estimativa de custo das chamadas de LLM — o número que a spec 02 exige antes do make enrich."""

from dataclasses import dataclass
from pathlib import Path

# Uma chamada de extração gasta ~4 caracteres por token. A conta exata exigiria o tokenizador do
# provider, que a ADR-004 ainda não escolheu; a margem é de 15-20%.
CARACTERES_POR_TOKEN = 4

# Saída do schema ReviewEnrichment: aspectos com evidência literal mais os campos escalares.
TOKENS_SAIDA_POR_REVIEW = 250


@dataclass(frozen=True)
class Modelo:
    """Preço em dólares por milhão de tokens. Tabela da API Anthropic, consultada em 2026-09-22."""

    nome: str
    usd_por_mtok_entrada: float
    usd_por_mtok_saida: float


MODELOS = (
    Modelo("haiku-4.5", 1.0, 5.0),
    Modelo("sonnet-5", 2.0, 10.0),
    Modelo("opus-5", 5.0, 25.0),
)

TETOS_USD = (25.0, 50.0, 100.0, 250.0)


def tokens_de(caracteres: int) -> int:
    return caracteres // CARACTERES_POR_TOKEN


def overhead_do_prompt(caminho_prompt: Path, caracteres_medios_review: int) -> int:
    """Gabarito do prompt mais os 3 exemplos que o template pede em {{ few_shot_examples }}."""
    gabarito = tokens_de(len(caminho_prompt.read_text(encoding="utf-8")))
    exemplos = 3 * (tokens_de(caracteres_medios_review) + TOKENS_SAIDA_POR_REVIEW)
    return gabarito + exemplos


def estimar_custo(n_reviews: int, tokens_entrada_por_review: int, modelo: Modelo) -> float:
    entrada = n_reviews * tokens_entrada_por_review / 1_000_000 * modelo.usd_por_mtok_entrada
    saida = n_reviews * TOKENS_SAIDA_POR_REVIEW / 1_000_000 * modelo.usd_por_mtok_saida
    return entrada + saida


def tamanho_por_teto(teto_usd: float, tokens_entrada_por_review: int, modelo: Modelo) -> int:
    """Quantas reviews cabem no teto — a direção que a ADR-004 precisa para comparar providers."""
    por_review = estimar_custo(1, tokens_entrada_por_review, modelo)
    if por_review <= 0:
        return 0
    return int(teto_usd / por_review)
