"""Memória de conversa em processo (spec 04, recorte de ConversationState).

ADR-003 autoriza estado em memória, processo único. Sem TTL: reiniciar o processo já limpa tudo,
suficiente para demo local — expiração automática fica para se isto virar serviço de longa duração.
"""

import uuid
from dataclasses import dataclass, field

from bri.agent.roteador import Intencao

MAX_TURNOS = 20  # teto por sessão — histórico de chat não precisa de mais para caber na tela


@dataclass
class Turno:
    pergunta: str
    resposta_texto: str


@dataclass
class EstadoConversa:
    ultima_entidade: tuple[Intencao, str] | None = None
    turnos: list[Turno] = field(default_factory=list)


# dict módulo-level, chave = sessao_id (cookie). Toda função abaixo opera direto sobre este
# atributo do módulo — nenhuma o recebe como default de parâmetro. É a armadilha que já pegou
# exportar.RAIZ_EXPORTS nesta sessão: default é capturado na definição da função, não relido a
# cada chamada, e um teste que faça monkeypatch do atributo do módulo não alcançaria uma função
# cujo parâmetro já capturou o valor antigo.
SESSOES: dict[str, EstadoConversa] = {}


def novo_id_sessao() -> str:
    return uuid.uuid4().hex


def obter(sessao_id: str) -> EstadoConversa:
    """Cria a sessão se ainda não existir; nunca lança KeyError."""
    return SESSOES.setdefault(sessao_id, EstadoConversa())


def registrar_turno(sessao_id: str, pergunta: str, resposta_texto: str) -> None:
    estado = obter(sessao_id)
    estado.turnos.append(Turno(pergunta, resposta_texto))
    estado.turnos[:] = estado.turnos[-MAX_TURNOS:]


def atualizar_entidade(sessao_id: str, intencao: Intencao, entidade: str) -> None:
    obter(sessao_id).ultima_entidade = (intencao, entidade)


def limpar_entidade(sessao_id: str) -> None:
    obter(sessao_id).ultima_entidade = None
