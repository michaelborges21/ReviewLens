"""Peças compartilhadas pelas rotas — separadas de main.py para não criar import circular."""

from collections.abc import Iterator
from pathlib import Path

import duckdb
from fastapi import Request
from fastapi.templating import Jinja2Templates

from bri.data import consultas

DIRETORIO = Path(__file__).parent
templates = Jinja2Templates(directory=str(DIRETORIO / "templates"))


def obter_conexao() -> Iterator[duckdb.DuckDBPyConnection]:
    """Conexão somente-leitura por requisição. Os testes substituem esta dependência."""
    con = consultas.conectar()
    try:
        yield con
    finally:
        con.close()


def e_htmx(request: Request) -> bool:
    """Requisição do HTMX recebe só o fragmento; sem JavaScript, a página inteira."""
    return request.headers.get("HX-Request") == "true"
