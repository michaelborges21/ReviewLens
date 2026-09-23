"""Testa a aritmética de custo — uma taxa errada desinforma orçamento sem levantar exceção."""

from pathlib import Path

import pytest

from bri.llm.custo import (
    TOKENS_SAIDA_POR_REVIEW,
    Modelo,
    estimar_custo,
    overhead_do_prompt,
    tamanho_por_teto,
    tokens_de,
)

MODELO_TESTE = Modelo("teste", usd_por_mtok_entrada=1.0, usd_por_mtok_saida=5.0)


def test_custo_bate_com_conta_feita_a_mao() -> None:
    """1.000 reviews × 1.000 tokens entrada = 1M tokens = US$ 1,00; saída 250k = US$ 1,25."""
    assert estimar_custo(1_000, 1_000, MODELO_TESTE) == pytest.approx(1.00 + 1.25)


def test_modelo_mais_caro_custa_mais() -> None:
    barato = estimar_custo(1_000, 1_000, MODELO_TESTE)
    caro = estimar_custo(1_000, 1_000, Modelo("caro", 5.0, 25.0))

    assert caro == pytest.approx(barato * 5)


def test_teto_e_custo_sao_consistentes() -> None:
    """Ida e volta: o que cabe no teto não pode custar mais que o teto."""
    cabem = tamanho_por_teto(50.0, 1_000, MODELO_TESTE)

    assert estimar_custo(cabem, 1_000, MODELO_TESTE) <= 50.0
    assert estimar_custo(cabem + 1, 1_000, MODELO_TESTE) > 50.0


def test_overhead_conta_gabarito_e_exemplos(tmp_path: Path) -> None:
    prompt = tmp_path / "extract_review.md"
    prompt.write_text("x" * 400, encoding="utf-8")

    overhead = overhead_do_prompt(prompt, caracteres_medios_review=800)

    assert overhead == tokens_de(400) + 3 * (tokens_de(800) + TOKENS_SAIDA_POR_REVIEW)
