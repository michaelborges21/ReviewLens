"""Monta o contexto de avaliação — compartilhado pelo smoke e pelo red-team, para não duplicar."""

from bri.agent.roteador import Intencao, Resposta


def resposta_com_payload(payload: str, review_id: str = "777") -> Resposta:
    """Uma Resposta cuja citação de leitor carrega texto hostil, como viria da base real.

    O payload entra onde entraria a evidência de um leitor de verdade: é exatamente o vetor de
    injeção indireta que a spec 05 aponta como principal risco do projeto.
    """
    return Resposta(
        Intencao.AUTOR,
        "Performance de Teste.",
        "SELECT 1",
        [{"ano": 2010, "n_reviews": 5, "nota_media": 3.0}],
        aspectos={
            "aspectos": [
                {
                    "aspecto": "enredo",
                    "n_mencoes": 3,
                    "pct_negativo": 66.0,
                    "exemplo_negativo": payload,
                    "exemplo_negativo_review_id": review_id,
                }
            ],
            "avaliacoes_analisadas": 3,
            "avaliacoes_totais": 50,
        },
    )
