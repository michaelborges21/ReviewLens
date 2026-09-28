"""Pede ao LLM local que redija em prosa o que o roteador já apurou por SQL (spec 04)."""

import json
from typing import Any

from pydantic import ValidationError

from bri.agent.roteador import Intencao, Resposta
from bri.guardrails.citacoes import citacoes_invalidas
from bri.guardrails.numeros import numeros_invalidos
from bri.llm import ollama, prompts
from bri.schemas.qa import RespostaNarrada

# o padrão de 300s de gerar_json serve ao batch noturno, não a uma requisição de navegador
TIMEOUT_CHAT = 60
MAX_TENTATIVAS = 2
MAX_CITACOES = 5
MAX_LINHAS_NUMEROS = 10

_PROMPT = prompts.carregar("qa_system")
_SCHEMA = RespostaNarrada.model_json_schema()


def _citacoes_do_contexto(aspectos: dict[str, Any]) -> tuple[str, set[str]]:
    """Monta os blocos <review> e o conjunto de ids que o guardrail vai aceitar."""
    blocos: list[str] = []
    ids: set[str] = set()
    for aspecto in aspectos.get("aspectos", [])[:MAX_CITACOES]:
        review_id = aspecto.get("exemplo_negativo_review_id")
        trecho = aspecto.get("exemplo_negativo")
        if not review_id or not trecho:
            continue
        blocos.append(f'<review id="{review_id}">{trecho}</review>')
        ids.add(str(review_id))
    return "\n".join(blocos), ids


def _numeros_em_linhas(dados: list[dict[str, Any]]) -> str:
    """Uma linha curta por registro — json.dumps de float traria 15 dígitos sem utilidade."""

    def formatar(valor: Any) -> str:
        return f"{valor:.2f}" if isinstance(valor, float) else str(valor)

    return "\n".join(
        " ".join(f"{chave}={formatar(valor)}" for chave, valor in linha.items())
        for linha in dados[:MAX_LINHAS_NUMEROS]
    )


def _tamanho_da_amostra(aspectos: dict[str, Any]) -> str:
    analisadas = aspectos.get("avaliacoes_analisadas", 0)
    totais = aspectos.get("avaliacoes_totais", 0)
    if not totais:
        return "nenhuma avaliação desta entidade foi analisada por IA"
    return f"{analisadas} de {totais} avaliações analisadas por IA"


def _correcao(ids_enviados: set[str], numeros_sem_lastro: list[float]) -> str:
    """Sem isto o retry repetiria a mesma resposta: temperatura 0,1 e prompt idêntico."""
    permitidos = ", ".join(sorted(ids_enviados)) or "nenhum"
    avisos = [f"Cite apenas estes review_id: {permitidos}. Não invente outros."]
    if numeros_sem_lastro:
        citados = ", ".join(f"{v:g}" for v in numeros_sem_lastro)
        avisos.append(
            f"Os números {citados} não estão nos dados enviados. Use somente números dos blocos"
            " <numeros> e <amostra>, sem recalcular."
        )
    return f"<correcao>{' '.join(avisos)}</correcao>"


def _pedir_ao_modelo(prompt: str) -> RespostaNarrada | None:
    """Uma chamada. None em qualquer falha — o chat não pode cair por causa do modelo."""
    try:
        bruto = ollama.gerar_json(_PROMPT.sistema, prompt, _SCHEMA, timeout=TIMEOUT_CHAT)
        return RespostaNarrada.model_validate_json(bruto)
    except OSError as erro:  # URLError e timeout de socket descendem daqui
        print(f"narrador: modelo inacessível ({erro})", flush=True)
    except (ValidationError, json.JSONDecodeError, KeyError) as erro:
        print(f"narrador: resposta malformada ({type(erro).__name__})", flush=True)
    return None


def narrar(pergunta: str, resposta: Resposta) -> RespostaNarrada | None:
    """Redige em prosa o que o SQL apurou. None significa: use o texto determinístico."""
    if resposta.intencao is Intencao.FORA_DE_ESCOPO:
        return None

    citacoes, ids_enviados = _citacoes_do_contexto(resposta.aspectos)
    numeros = _numeros_em_linhas(resposta.dados)
    amostra = _tamanho_da_amostra(resposta.aspectos)
    prompt = _PROMPT.montar(pergunta=pergunta, numeros=numeros, amostra=amostra, citacoes=citacoes)
    # comparar contra o prompt inteiro alargaria o permitido: o bloco <estilo> fala em "3 a 5
    # frases", e aí um 5 inventado passaria como se fosse dado. Só os dados valem de lastro.
    dados_enviados = f"{numeros}\n{amostra}\n{' '.join(sorted(ids_enviados))}"

    correcao = ""
    for _ in range(MAX_TENTATIVAS):
        narrada = _pedir_ao_modelo(f"{prompt}\n{correcao}" if correcao else prompt)
        if narrada is None:
            return None

        ids_inventados = citacoes_invalidas(narrada.citacoes, ids_enviados)
        fora = numeros_invalidos(narrada.resposta, dados_enviados)
        if fora.inventados:
            # impossível no domínio (nota 7,3, contagem acima da base): corrigir não melhora
            print(f"narrador: número impossível {fora.inventados}", flush=True)
            return None
        if not ids_inventados and not fora.suspeitos:
            return narrada

        print(f"narrador: citação {ids_inventados}, número sem lastro {fora.suspeitos}", flush=True)
        correcao = _correcao(ids_enviados, fora.suspeitos)
    return None
