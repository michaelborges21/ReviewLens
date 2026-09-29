"""Testa o estado de conversa em memória: sessões isoladas, teto de turnos, entidade herdada."""

import pytest

from bri.agent import conversa
from bri.agent.roteador import Intencao


@pytest.fixture(autouse=True)
def limpar_sessoes() -> None:
    conversa.SESSOES.clear()


def test_obter_cria_sessao_vazia() -> None:
    estado = conversa.obter("s1")

    assert estado.ultima_entidade is None
    assert estado.turnos == []


def test_registrar_turno_acumula() -> None:
    conversa.registrar_turno("s1", "pergunta 1", "resposta 1")
    conversa.registrar_turno("s1", "pergunta 2", "resposta 2")

    turnos = conversa.obter("s1").turnos
    assert [t.pergunta for t in turnos] == ["pergunta 1", "pergunta 2"]


def test_registrar_turno_respeita_teto() -> None:
    for i in range(conversa.MAX_TURNOS + 5):
        conversa.registrar_turno("s1", f"pergunta {i}", f"resposta {i}")

    turnos = conversa.obter("s1").turnos
    assert len(turnos) == conversa.MAX_TURNOS
    # sobraram os ÚLTIMOS, não os primeiros
    assert turnos[-1].pergunta == f"pergunta {conversa.MAX_TURNOS + 4}"
    assert turnos[0].pergunta == "pergunta 5"


def test_atualizar_e_limpar_entidade() -> None:
    conversa.atualizar_entidade("s1", Intencao.AUTOR, "Frank Herbert")
    assert conversa.obter("s1").ultima_entidade == (Intencao.AUTOR, "Frank Herbert")

    conversa.limpar_entidade("s1")
    assert conversa.obter("s1").ultima_entidade is None


def test_sessoes_diferentes_nao_se_misturam() -> None:
    conversa.atualizar_entidade("s1", Intencao.AUTOR, "Frank Herbert")
    conversa.registrar_turno("s1", "pergunta de s1", "resposta")

    estado_s2 = conversa.obter("s2")

    assert estado_s2.ultima_entidade is None
    assert estado_s2.turnos == []
