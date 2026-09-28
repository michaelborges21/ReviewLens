"""Testa o guardrail de citação: id inventado precisa ser detectado antes de chegar à tela."""

from bri.guardrails.citacoes import citacoes_invalidas
from bri.schemas.qa import Citacao


def test_citacao_do_contexto_e_aceita() -> None:
    citacoes = [Citacao(review_id="1", trecho="ficou arrastado")]

    assert citacoes_invalidas(citacoes, {"1", "2"}) == []


def test_id_inventado_e_devolvido() -> None:
    citacoes = [Citacao(review_id="1", trecho="ok"), Citacao(review_id="999", trecho="inventado")]

    assert citacoes_invalidas(citacoes, {"1"}) == ["999"]


def test_resposta_sem_citacao_e_valida() -> None:
    """Pergunta de números gerais não cita ninguém — não é falha de fundamentação."""
    assert citacoes_invalidas([], {"1"}) == []


def test_id_inventado_repetido_aparece_uma_vez() -> None:
    citacoes = [Citacao(review_id="7", trecho="a"), Citacao(review_id="7", trecho="b")]

    assert citacoes_invalidas(citacoes, set()) == ["7"]
