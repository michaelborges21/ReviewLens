"""Testa o guardrail de números: pegar invenção sem reprovar formatação legítima."""

import pytest

from bri.guardrails.numeros import numeros_de, numeros_invalidos

CONTEXTO = "ano=2010 n_reviews=5 nota_media=3.00\n3 de 50 avaliações analisadas por IA"


def test_numero_do_contexto_e_aceito() -> None:
    prosa = "Em 2010 houve 5 avaliações, com nota média de 3.00."

    assert not numeros_invalidos(prosa, CONTEXTO)


@pytest.mark.parametrize(
    "escrito_pelo_modelo",
    [
        "a nota média foi 3,00",  # vírgula decimal
        "a nota média foi 3",  # sem casa decimal
        "foram 5 avaliações em 2010.",  # ponto final colado no número
    ],
)
def test_formatacao_diferente_nao_e_invencao(escrito_pelo_modelo: str) -> None:
    """Medido em 18 respostas reais: comparar como texto reprovava 22% delas só por grafia."""
    assert not numeros_invalidos(escrito_pelo_modelo, CONTEXTO)


def test_separador_de_milhar_casa_com_o_banco() -> None:
    assert not numeros_invalidos("são 2.239.998 avaliações", "total=2239998")


def test_nota_falsa_e_suspeita_nao_invencao() -> None:
    """1,2 é nota plausível, só não é a nossa: cabe uma tentativa de correção antes de descartar."""
    fora = numeros_invalidos("a nota média é de 1.2 estrelas", CONTEXTO)

    assert fora.suspeitos == [1.2]
    assert fora.inventados == []


def test_nota_impossivel_e_invencao() -> None:
    """Decimal fora de 1 a 5 não é nota de livro nenhum — descarta sem tentar de novo."""
    fora = numeros_invalidos("a nota média é 7.3", CONTEXTO)

    assert fora.inventados == [7.3]
    assert fora.suspeitos == []


def test_contagem_acima_da_base_e_invencao() -> None:
    fora = numeros_invalidos("analisamos 9000000 avaliações", CONTEXTO)

    assert fora.inventados == [9000000.0]


def test_percentual_derivado_fica_como_suspeito() -> None:
    """O modelo calculando "mais de 60%" não é fraude, é cálculo: merece retry, não descarte."""
    fora = numeros_invalidos("mais de 60% das notas são altas", CONTEXTO)

    assert fora.suspeitos == [60.0]
    assert fora.inventados == []


def test_numeros_de_normaliza_os_dois_lados() -> None:
    assert numeros_de("2.239.998 e 4,5") == {2239998.0, 4.5}
