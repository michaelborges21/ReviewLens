"""Testa a aritmética de custo — uma taxa errada desinforma orçamento sem levantar exceção."""

from pathlib import Path

import pytest

from bri.llm.custo import (
    DATA_REFERENCIA_CAMBIO,
    TOKENS_SAIDA_POR_REVIEW,
    USD_BRL_PADRAO,
    Modelo,
    cotacao_usd_brl,
    estimar_custo,
    estimar_custo_com_cache,
    overhead_do_prompt,
    para_reais,
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


def test_cache_cobra_um_decimo_do_prefixo() -> None:
    """Prefixo de 1.000 tokens vira 100 na entrada; a parte variável segue no preço cheio."""
    com_cache = estimar_custo_com_cache(1_000, 1_000, 200, MODELO_TESTE)

    assert com_cache == pytest.approx(estimar_custo(1_000, 300, MODELO_TESTE))


def test_cache_nunca_sai_mais_caro_que_sem_cache() -> None:
    sem = estimar_custo(1_000, 1_200, MODELO_TESTE)
    com = estimar_custo_com_cache(1_000, 1_000, 200, MODELO_TESTE)

    assert com < sem


def test_cotacao_vem_do_ambiente_quando_definida(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USD_BRL", "6,25")

    taxa, procedencia = cotacao_usd_brl()

    assert taxa == pytest.approx(6.25)
    assert "USD_BRL" in procedencia


def test_cotacao_cai_no_padrao_datado_sem_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USD_BRL", raising=False)

    taxa, procedencia = cotacao_usd_brl()

    assert taxa == USD_BRL_PADRAO
    assert DATA_REFERENCIA_CAMBIO in procedencia


def test_cotacao_invalida_quebra_alto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Câmbio com lixo não pode cair em silêncio no padrão e desinformar orçamento."""
    monkeypatch.setenv("USD_BRL", "seis reais")

    with pytest.raises(ValueError):
        cotacao_usd_brl()


def test_conversao_para_reais() -> None:
    assert para_reais(60.53, 5.5) == pytest.approx(332.915)


def test_overhead_conta_gabarito_e_exemplos(tmp_path: Path) -> None:
    prompt = tmp_path / "extract_review.md"
    prompt.write_text("x" * 400, encoding="utf-8")

    overhead = overhead_do_prompt(prompt, caracteres_medios_review=800)

    assert overhead == tokens_de(400) + 3 * (tokens_de(800) + TOKENS_SAIDA_POR_REVIEW)
