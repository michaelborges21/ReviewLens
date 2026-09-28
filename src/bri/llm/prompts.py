"""Carrega os prompts versionados de src/bri/prompts — um só lugar para front matter e variáveis."""

from dataclasses import dataclass
from pathlib import Path

DIRETORIO = Path(__file__).parents[1] / "prompts"


@dataclass(frozen=True)
class Prompt:
    versao: str
    sistema: str
    template_usuario: str

    def montar(self, **valores: str) -> str:
        """Troca cada {{ chave }} do template pelo valor correspondente."""
        texto = self.template_usuario
        for chave, valor in valores.items():
            texto = texto.replace(f"{{{{ {chave} }}}}", valor)
        return texto


def carregar(nome: str, diretorio: Path = DIRETORIO) -> Prompt:
    """Lê <nome>.md: front matter YAML, depois corpo dividido em [system] e [user].

    Caminho resolvido por __file__, não pelo diretório de trabalho — `make enrich` rodava só da
    raiz do projeto antes disso. `diretorio` serve ao eval, que compara versões candidatas.
    """
    conteudo = (diretorio / f"{nome}.md").read_text(encoding="utf-8")
    _, frente, corpo = conteudo.split("---", 2)
    sistema, marcador, usuario = corpo.partition("[user]")
    if not marcador:
        raise ValueError(f"prompt {nome} não tem a seção [user]")
    return Prompt(
        versao=_versao_declarada(frente),
        sistema=sistema.replace("[system]", "").strip(),
        template_usuario=usuario.strip(),
    )


def _versao_declarada(frente: str) -> str:
    """Varredura de linha em vez de parser YAML: é um campo só, não vale a dependência."""
    for linha in frente.splitlines():
        if linha.startswith("version:"):
            return linha.removeprefix("version:").strip()
    raise ValueError("front matter sem campo version")
