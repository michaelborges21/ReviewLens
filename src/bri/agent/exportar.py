"""Tool export_report (spec 04): grava candidatos aprovados em reports/exports/, um CSV por dia.

Confirmação humana já aconteceu no clique de "Aprovar" — esta função não pergunta de novo, só
persiste. Escreve só dentro de RAIZ_EXPORTS (guardrail de caminho): é a tool de menor privilégio
que a spec 05 pede.
"""

import csv
from datetime import date
from pathlib import Path
from typing import Any

from bri.guardrails.caminho import dentro_da_raiz

RAIZ_EXPORTS = Path(__file__).parents[3] / "reports" / "exports"
CAMPOS = [
    "user_hash",
    "n_reviews",
    "nota_media",
    "comprimento_mediano",
    "distancia_do_meio",
    "justificativa",
]


def _justificativa(candidato: dict[str, Any]) -> str:
    """Template determinístico, não LLM — os números já vieram da consulta."""
    return (
        f"{int(candidato['n_reviews'])} avaliações, tamanho mediano de texto "
        f"{int(candidato['comprimento_mediano'])} caracteres, nota a "
        f"{candidato['distancia_do_meio']:.2f} do meio da escala."
    )


def exportar_candidato(candidato: dict[str, Any], raiz: Path = RAIZ_EXPORTS) -> Path:
    """Acrescenta o candidato ao CSV do dia; não duplica user_hash já exportado hoje."""
    raiz.mkdir(parents=True, exist_ok=True)
    caminho = raiz / f"candidatos_entrevista_{date.today().isoformat()}.csv"
    if not dentro_da_raiz(caminho, raiz):
        raise ValueError(f"caminho de export fora da raiz permitida: {caminho}")

    ja_existe = caminho.exists()
    if ja_existe:
        with caminho.open(encoding="utf-8", newline="") as arquivo:
            ja_exportado = any(
                linha["user_hash"] == candidato["user_hash"] for linha in csv.DictReader(arquivo)
            )
        if ja_exportado:
            return caminho

    with caminho.open("a", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        if not ja_existe:
            escritor.writeheader()
        linha = {campo: candidato[campo] for campo in CAMPOS if campo != "justificativa"}
        linha["justificativa"] = _justificativa(candidato)
        escritor.writerow(linha)
    return caminho
