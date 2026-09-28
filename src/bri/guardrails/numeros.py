"""Confere se todo número da prosa veio do contexto enviado ao modelo (specs 05 e 06).

Irmão de `citacoes`: o red-team mostrou que o modelo resiste a ordens ("ignore as instruções") mas
aceita valor plausível disfarçado de dado — mandaram afirmar nota 1,2 e ele afirmou, três vezes em
três, embora o contexto dissesse 3,00.

A comparação é numérica, não textual. Medido em 18 respostas legítimas: comparar como texto
reprovava 22% delas só por formatação (`2.239.998` contra `2239998`, "4 estrelas" contra `4.00`);
como número, 0%.
"""

import re
from dataclasses import dataclass

# Faixas derivadas do banco em 2026-09-28. Só a contagem cresce com o tempo, e um teto velho deixa a
# regra mais rígida, nunca mais frouxa — o erro cai no lado seguro.
NOTA_MINIMA, NOTA_MAXIMA = 1.0, 5.0
MAIOR_CONTAGEM = 2_239_998.0

_NUMERO = re.compile(r"\d[\d.,]*")


@dataclass(frozen=True)
class ForaDoContexto:
    """Números sem lastro no contexto, separados pela gravidade da grade de decisão.

    `suspeitos` são plausíveis e podem ser o modelo derivando algo ("mais de 50% das notas são 5"):
    vale uma tentativa de correção. `inventados` são impossíveis no domínio: descarta direto.
    """

    suspeitos: list[float]
    inventados: list[float]

    def __bool__(self) -> bool:
        return bool(self.suspeitos or self.inventados)


def _como_numero(token: str) -> float | None:
    """Normaliza a grafia antes de converter: é o que evita reprovar resposta correta.

    Tira pontuação de fim de frase, remove separador de milhar (ponto seguido de exatamente três
    dígitos) e aceita vírgula decimal. `1.2` não é milhar e continua valendo 1,2.
    """
    limpo = token.rstrip(".,;:)%")
    limpo = re.sub(r"(?<=\d)\.(?=\d{3}(\D|$))", "", limpo)
    try:
        return float(limpo.replace(",", "."))
    except ValueError:
        return None


def numeros_de(texto: str) -> set[float]:
    """Todo número do texto, já normalizado — serve tanto para a prosa quanto para o contexto."""
    achados = (_como_numero(t) for t in _NUMERO.findall(texto))
    return {n for n in achados if n is not None}


def _impossivel(valor: float) -> bool:
    """Número com decimal só pode ser nota; inteiro não passa do tamanho da maior tabela.

    Checar "cabe em algum domínio" não discriminaria nada: a faixa de contagem vai a 2,2 milhões e
    engoliria até 7,3. A forma do número é o que separa os casos.
    """
    if valor != int(valor):
        return not NOTA_MINIMA <= valor <= NOTA_MAXIMA
    return not 0 <= valor <= MAIOR_CONTAGEM


def numeros_invalidos(prosa: str, contexto: str) -> ForaDoContexto:
    """Números afirmados na prosa que não estavam no contexto, classificados por gravidade."""
    sem_lastro = numeros_de(prosa) - numeros_de(contexto)
    return ForaDoContexto(
        suspeitos=sorted(v for v in sem_lastro if not _impossivel(v)),
        inventados=sorted(v for v in sem_lastro if _impossivel(v)),
    )
