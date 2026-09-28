"""Testa o carregador de prompts — inclusive a falha silenciosa que ele passou a recusar."""

from pathlib import Path

import pytest

from bri.llm import prompts


def test_carrega_extract_review_com_sistema_e_template() -> None:
    prompt = prompts.carregar("extract_review")

    assert prompt.versao == "0.2.0"
    assert "CATEGORIAS VÁLIDAS" in prompt.sistema
    assert "{{ review_text }}" in prompt.template_usuario


def test_montar_troca_todas_as_variaveis() -> None:
    prompt = prompts.carregar("extract_review")

    montado = prompt.montar(review_id="42", score="5.0", review_text="adorei o ritmo")

    assert "42" in montado
    assert "adorei o ritmo" in montado
    assert "{{" not in montado


def test_prompt_sem_secao_user_e_recusado(tmp_path: Path) -> None:
    """Sem esta checagem o template vinha vazio e o prompt chegava incompleto ao modelo."""
    (tmp_path / "solto.md").write_text(
        "---\nversion: 0.1.0\n---\nsó corpo, sem marcador\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="não tem a seção"):
        prompts.carregar("solto", tmp_path)


def test_front_matter_sem_versao_e_recusado(tmp_path: Path) -> None:
    (tmp_path / "sem_versao.md").write_text(
        "---\nused_by: nada\n---\n[system]\nx\n[user]\ny\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="sem campo version"):
        prompts.carregar("sem_versao", tmp_path)
