"""Testa o download de modelos sem rede: urlopen trocado por fake, como em test_extract."""

import io
import json
from typing import Any

import pytest

from bri.llm import baixar_modelos


def _resposta_de_tags(nomes: list[str]) -> io.BytesIO:
    corpo = json.dumps({"models": [{"name": nome} for nome in nomes]}).encode("utf-8")
    return io.BytesIO(corpo)


class _ContextoFalso(io.BytesIO):
    """urlopen devolve um context manager; BytesIO não é um, então embrulha."""

    def __enter__(self) -> "_ContextoFalso":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_modelos_instalados_aceita_sufixo_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Ollama guarda `embeddinggemma` como `embeddinggemma:latest` — as duas formas contam."""
    monkeypatch.setattr(
        baixar_modelos.urllib.request,
        "urlopen",
        lambda *a, **k: _ContextoFalso(_resposta_de_tags(["embeddinggemma:latest"]).getvalue()),
    )

    instalados = baixar_modelos.modelos_instalados()

    assert "embeddinggemma" in instalados
    assert "embeddinggemma:latest" in instalados


def test_nao_baixa_o_que_ja_esta_instalado(monkeypatch: pytest.MonkeyPatch) -> None:
    """São ~8,8GB somados e o compose chama isto em todo `up`: baixar de novo seria inaceitável."""
    monkeypatch.setattr(
        baixar_modelos,
        "modelos_instalados",
        lambda: {baixar_modelos.MODELO_PADRAO, baixar_modelos.EMBEDDING_MODELO_PADRAO},
    )
    baixados: list[str] = []
    monkeypatch.setattr(baixar_modelos, "baixar", baixados.append)

    assert baixar_modelos.main() == 0
    assert baixados == []


def test_baixa_somente_o_que_falta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        baixar_modelos, "modelos_instalados", lambda: {baixar_modelos.MODELO_PADRAO}
    )
    baixados: list[str] = []
    monkeypatch.setattr(baixar_modelos, "baixar", baixados.append)

    assert baixar_modelos.main() == 0
    assert baixados == [baixar_modelos.EMBEDDING_MODELO_PADRAO]


def test_ollama_fora_do_ar_falha_com_codigo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem isso o compose seguiria para o app com o modelo ausente, e o chat degradaria calado."""
    monkeypatch.setattr(baixar_modelos, "esperar_ollama", lambda: False)

    assert baixar_modelos.main() == 1


def test_erro_no_stream_do_pull_vira_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Ollama devolve 200 com {"error": ...} no corpo — tratar como sucesso esconderia a falha."""
    linhas = json.dumps({"error": "model not found"}).encode("utf-8") + b"\n"
    monkeypatch.setattr(
        baixar_modelos.urllib.request, "urlopen", lambda *a, **k: _ContextoFalso(linhas)
    )

    with pytest.raises(OSError, match="model not found"):
        baixar_modelos.baixar("inexistente:1b")


def test_progresso_mostra_percentual_quando_ha_total() -> None:
    linha: dict[str, Any] = {
        "status": "downloading",
        "total": 8_000_000_000,
        "completed": 2_000_000_000,
    }

    assert baixar_modelos._progresso(linha) == "  downloading — 25% de 8.0GB"


def test_progresso_mostra_mb_em_camada_pequena() -> None:
    """45MB como `0.0GB` parece download quebrado para quem está olhando o log."""
    linha: dict[str, Any] = {"status": "pulling", "total": 45_000_000, "completed": 9_000_000}

    assert baixar_modelos._progresso(linha) == "  pulling — 20% de 45MB"


def test_progresso_sem_total_mostra_so_o_status() -> None:
    assert baixar_modelos._progresso({"status": "pulling manifest"}) == "  pulling manifest"
