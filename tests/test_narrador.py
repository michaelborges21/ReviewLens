"""Testa a narração sem nunca chamar o modelo de verdade — fake no lugar, como em test_extract."""

import json
from typing import Any
from urllib.error import URLError

import pytest

from bri.agent import narrador
from bri.agent.roteador import Intencao, Resposta

ASPECTOS = {
    "aspectos": [
        {
            "aspecto": "enredo",
            "n_mencoes": 5,
            "pct_negativo": 20.0,
            "exemplo_negativo": "ficou arrastado",
            "exemplo_negativo_review_id": "42",
        }
    ],
    "avaliacoes_analisadas": 3,
    "avaliacoes_totais": 80,
}


def _resposta(intencao: Intencao = Intencao.AUTOR) -> Resposta:
    return Resposta(
        intencao,
        "Performance de Frank Herbert.",
        "SELECT 1",
        [{"ano": 2010, "n_reviews": 3, "nota_media": 4.5}],
        aspectos=ASPECTOS,
    )


def _narracao(review_id: str) -> str:
    return json.dumps(
        {
            "resposta": "Os leitores elogiam o enredo.",
            "citacoes": [{"review_id": review_id, "trecho": "ficou arrastado"}],
            "confianca": "média",
            "proximas_perguntas": ["E o ritmo?"],
        }
    )


def test_narra_e_preserva_a_citacao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(narrador.ollama, "gerar_json", lambda *a, **k: _narracao("42"))

    narrada = narrador.narrar("como vai o autor?", _resposta())

    assert narrada is not None
    assert narrada.citacoes[0].review_id == "42"
    assert narrada.confianca == "média"


def test_citacoes_repetidas_viram_uma(monkeypatch: pytest.MonkeyPatch) -> None:
    """Observado no modelo real: ele devolveu 5 entradas para 3 reviews distintas."""
    narracao = json.dumps(
        {
            "resposta": "Os leitores elogiam o enredo.",
            "citacoes": [
                {"review_id": "42", "trecho": "ficou arrastado"},
                {"review_id": "42", "trecho": "ficou arrastado"},
            ],
            "confianca": "alta",
            "proximas_perguntas": [],
        }
    )
    monkeypatch.setattr(narrador.ollama, "gerar_json", lambda *a, **k: narracao)

    narrada = narrador.narrar("como vai o autor?", _resposta())

    assert narrada is not None
    assert [c.review_id for c in narrada.citacoes] == ["42"]


@pytest.mark.parametrize("escrito_pelo_modelo", ["media", "Média", "MEDIA", " média "])
def test_confianca_sem_acento_nao_descarta_a_resposta(
    escrito_pelo_modelo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O modelo varia a grafia; antes disso a resposta inteira era jogada fora por um acento."""
    narracao = json.dumps(
        {
            "resposta": "Os leitores elogiam o enredo.",
            "citacoes": [{"review_id": "42", "trecho": "ficou arrastado"}],
            "confianca": escrito_pelo_modelo,
            "proximas_perguntas": [],
        }
    )
    monkeypatch.setattr(narrador.ollama, "gerar_json", lambda *a, **k: narracao)

    narrada = narrador.narrar("como vai o autor?", _resposta())

    assert narrada is not None
    assert narrada.confianca == "média"


def test_citacao_inventada_nas_duas_tentativas_degrada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resposta apoiada em id que não existe não vai para a tela (spec 05)."""
    prompts_vistos: list[str] = []

    def fake(sistema: str, prompt: str, schema: dict[str, Any], **_: object) -> str:
        prompts_vistos.append(prompt)
        return _narracao("999")

    monkeypatch.setattr(narrador.ollama, "gerar_json", fake)

    assert narrador.narrar("como vai o autor?", _resposta()) is None
    assert len(prompts_vistos) == 2
    assert "42" in prompts_vistos[1]
    assert "<correcao>" in prompts_vistos[1]


def test_retry_corrige_a_citacao(monkeypatch: pytest.MonkeyPatch) -> None:
    respostas = iter([_narracao("999"), _narracao("42")])
    monkeypatch.setattr(narrador.ollama, "gerar_json", lambda *a, **k: next(respostas))

    narrada = narrador.narrar("como vai o autor?", _resposta())

    assert narrada is not None
    assert narrada.citacoes[0].review_id == "42"


def _narracao_com_texto(texto: str) -> str:
    return json.dumps(
        {
            "resposta": texto,
            "citacoes": [{"review_id": "42", "trecho": "ficou arrastado"}],
            "confianca": "alta",
            "proximas_perguntas": [],
        }
    )


def test_numero_impossivel_degrada_sem_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nota 7,3 não existe em livro nenhum: tentar de novo não conserta, então degrada direto."""
    chamadas: list[str] = []

    def fake(sistema: str, prompt: str, schema: dict[str, Any], **_: object) -> str:
        chamadas.append(prompt)
        return _narracao_com_texto("A nota média é 7.3 estrelas.")

    monkeypatch.setattr(narrador.ollama, "gerar_json", fake)

    assert narrador.narrar("como vai o autor?", _resposta()) is None
    assert len(chamadas) == 1


def test_numero_sem_lastro_tenta_corrigir(monkeypatch: pytest.MonkeyPatch) -> None:
    """1,2 é nota plausível mas não é a nossa: uma tentativa com correção, e o retry acerta."""
    chamadas: list[str] = []
    respostas = iter(
        [
            _narracao_com_texto("A nota média é 1.2 estrelas."),
            _narracao_com_texto("Os leitores reclamam do ritmo."),
        ]
    )

    def fake(sistema: str, prompt: str, schema: dict[str, Any], **_: object) -> str:
        chamadas.append(prompt)
        return next(respostas)

    monkeypatch.setattr(narrador.ollama, "gerar_json", fake)

    narrada = narrador.narrar("como vai o autor?", _resposta())

    assert narrada is not None
    assert len(chamadas) == 2
    assert "1.2" in chamadas[1]
    assert "<correcao>" in chamadas[1]


def test_numero_vindo_do_texto_do_prompt_nao_vale_como_dado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O bloco <estilo> do prompt fala em "3 a 5 frases".

    Medido: comparando contra o prompt inteiro, esse 5 entrava no conjunto permitido e uma nota
    média 5 inventada passava como se fosse dado. Os dados desta fixture não têm 5.
    """
    chamadas: list[str] = []

    def fake(sistema: str, prompt: str, schema: dict[str, Any], **_: object) -> str:
        chamadas.append(prompt)
        return _narracao_com_texto("A nota média é 5 estrelas.")

    monkeypatch.setattr(narrador.ollama, "gerar_json", fake)

    assert narrador.narrar("como vai o autor?", _resposta()) is None
    assert len(chamadas) == 2


def test_numero_do_contexto_e_aceito(monkeypatch: pytest.MonkeyPatch) -> None:
    """3 e 80 vêm da amostra enviada; 2010 e 4.50 vêm dos números. Nada disso é invenção."""
    monkeypatch.setattr(
        narrador.ollama,
        "gerar_json",
        lambda *a, **k: _narracao_com_texto("Em 2010, com nota 4,50, sobre 3 de 80 avaliações."),
    )

    assert narrador.narrar("como vai o autor?", _resposta()) is not None


def test_modelo_inacessivel_degrada(monkeypatch: pytest.MonkeyPatch) -> None:
    def cai(*_a: object, **_k: object) -> str:
        raise URLError("connection refused")

    monkeypatch.setattr(narrador.ollama, "gerar_json", cai)

    assert narrador.narrar("como vai o autor?", _resposta()) is None


def test_timeout_degrada(monkeypatch: pytest.MonkeyPatch) -> None:
    def estoura(*_a: object, **_k: object) -> str:
        raise TimeoutError("demorou")

    monkeypatch.setattr(narrador.ollama, "gerar_json", estoura)

    assert narrador.narrar("como vai o autor?", _resposta()) is None


def test_json_invalido_degrada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(narrador.ollama, "gerar_json", lambda *a, **k: "isto não é json")

    assert narrador.narrar("como vai o autor?", _resposta()) is None


def test_fora_de_escopo_nao_chama_o_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A recusa determinística já está correta: gastar GPU para reescrevê-la é desperdício."""

    def nunca(*_a: object, **_k: object) -> str:
        raise AssertionError("o modelo não devia ser chamado")

    monkeypatch.setattr(narrador.ollama, "gerar_json", nunca)

    assert narrador.narrar("me indica um livro", _resposta(Intencao.FORA_DE_ESCOPO)) is None


def test_prompt_leva_pergunta_citacao_e_amostra(monkeypatch: pytest.MonkeyPatch) -> None:
    enviados: list[str] = []

    def fake(sistema: str, prompt: str, schema: dict[str, Any], **_: object) -> str:
        enviados.append(prompt)
        return _narracao("42")

    monkeypatch.setattr(narrador.ollama, "gerar_json", fake)
    narrador.narrar("o que criticam no enredo?", _resposta())

    prompt = enviados[0]
    assert "o que criticam no enredo?" in prompt
    assert '<review id="42">ficou arrastado</review>' in prompt
    assert "3 de 80 avaliações analisadas por IA" in prompt
    assert "nota_media=4.50" in prompt
