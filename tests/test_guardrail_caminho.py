"""Testa o guardrail de caminho: escrita só dentro da raiz permitida (specs 04 e 05)."""

from pathlib import Path

from bri.guardrails.caminho import dentro_da_raiz


def test_caminho_dentro_da_raiz_e_aceito(tmp_path: Path) -> None:
    raiz = tmp_path / "reports" / "exports"

    assert dentro_da_raiz(raiz / "arquivo.csv", raiz)


def test_caminho_que_escapa_da_raiz_e_recusado(tmp_path: Path) -> None:
    raiz = tmp_path / "reports" / "exports"
    fora = raiz / ".." / ".." / "fora" / "arquivo.csv"

    assert not dentro_da_raiz(fora, raiz)


def test_a_propria_raiz_e_aceita(tmp_path: Path) -> None:
    raiz = tmp_path / "reports" / "exports"

    assert dentro_da_raiz(raiz, raiz)
