"""Confere que um caminho de escrita não escapa da raiz permitida (specs 04 e 05).

Menor privilégio de verdade: mesmo que um parâmetro seja adulterado (`../../etc`), a escrita só
acontece dentro de `reports/exports/`. `resolve()` normaliza `..` e symlinks antes da comparação.
"""

from pathlib import Path


def dentro_da_raiz(caminho: Path, raiz: Path) -> bool:
    """True só se `caminho` resolvido está dentro de `raiz` resolvida (ou é ela mesma)."""
    return caminho.resolve().is_relative_to(raiz.resolve())
