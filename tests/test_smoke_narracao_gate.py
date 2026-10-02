"""Testa o gate de 'Ollama fora do ar' do eval-smoke, sem chamar o modelo (ADR-019).

Só a lógica pura: _rodar_caso em si exige Ollama de pé, e isso evals/smoke_narracao.py já
resolve sozinho — o que falta cobrir é a decisão que evita o falso-verde.
"""

from evals.smoke_narracao import _todas_falharam_por_conexao


def test_todos_os_casos_falharam_por_conexao() -> None:
    medido = {
        "v0.2.0 (base)": [{"falha_conexao": True}, {"falha_conexao": True}],
        "em produção": [{"falha_conexao": True}],
    }

    assert _todas_falharam_por_conexao(medido)


def test_execucao_normal_nao_e_falha_de_conexao() -> None:
    medido = {"em produção": [{"checagens": {"schema_valido": True}}]}

    assert not _todas_falharam_por_conexao(medido)


def test_falha_parcial_nao_mascara_regressao_real() -> None:
    """Um caso isolado de timeout não deve esconder uma regressão real no resto do lote."""
    medido = {"em produção": [{"falha_conexao": True}, {"checagens": {"schema_valido": True}}]}

    assert not _todas_falharam_por_conexao(medido)


def test_sem_caso_nenhum_nao_e_falha_de_conexao() -> None:
    assert not _todas_falharam_por_conexao({})
