"""Estimativa de custo das chamadas de LLM — o número que a spec 02 exige antes do make enrich."""

import os
from dataclasses import dataclass
from pathlib import Path

# Referência datada, NÃO uma consulta de mercado: defina USD_BRL no ambiente para que o
# relatório use o câmbio do dia. Os modelos são cobrados em dólar pela Anthropic; o real
# aparece só na apresentação, porque quem decide o orçamento aqui é brasileiro.
USD_BRL_PADRAO = 5.50
DATA_REFERENCIA_CAMBIO = "2026-09-22"

# Uma chamada de extração gasta ~4 caracteres por token. A conta exata exigiria o tokenizador do
# provider, que a ADR-004 ainda não escolheu; a margem é de 15-20%.
CARACTERES_POR_TOKEN = 4

# Saída do schema ReviewEnrichment: aspectos com evidência literal mais os campos escalares.
TOKENS_SAIDA_POR_REVIEW = 250

# Leitura de prefixo já em cache custa cerca de um décimo do preço de entrada. Importa aqui
# porque o gabarito e os exemplos few-shot são idênticos em toda chamada da extração.
FATOR_LEITURA_CACHE = 0.1


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

TETOS_BRL = (100.0, 250.0, 500.0, 1_000.0)


def cotacao_usd_brl() -> tuple[float, str]:
    """Devolve a cotação e a procedência — o relatório precisa dizer ao leitor qual câmbio usou."""
    bruta = os.environ.get("USD_BRL")
    if bruta is None:
        return USD_BRL_PADRAO, f"padrão do código, referência de {DATA_REFERENCIA_CAMBIO}"
    return float(bruta.replace(",", ".")), "variável de ambiente USD_BRL"


def para_reais(valor_usd: float, cotacao: float) -> float:
    return valor_usd * cotacao


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


def estimar_custo_com_cache(
    n_reviews: int, tokens_prefixo: int, tokens_variaveis: int, modelo: Modelo
) -> float:
    """Mesma conta, com o prefixo estável (gabarito + few-shot) relido do cache."""
    tokens_entrada = tokens_prefixo * FATOR_LEITURA_CACHE + tokens_variaveis
    entrada = n_reviews * tokens_entrada / 1_000_000 * modelo.usd_por_mtok_entrada
    saida = n_reviews * TOKENS_SAIDA_POR_REVIEW / 1_000_000 * modelo.usd_por_mtok_saida
    return entrada + saida


def tamanho_por_teto(teto_usd: float, tokens_entrada_por_review: int, modelo: Modelo) -> int:
    """Quantas reviews cabem no teto — a direção que a ADR-004 precisa para comparar providers."""
    por_review = estimar_custo(1, tokens_entrada_por_review, modelo)
    if por_review <= 0:
        return 0
    return int(teto_usd / por_review)
