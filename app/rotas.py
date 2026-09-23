"""Páginas HTML e fragmentos HTMX."""

from typing import Annotated, Any

import duckdb
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse

from app.base import e_htmx, obter_conexao, templates
from bri.agent import roteador
from bri.data import consultas

router = APIRouter()

Conexao = Annotated[duckdb.DuckDBPyConnection, Depends(obter_conexao)]


def _pagina(request: Request, nome: str, contexto: dict[str, Any]) -> HTMLResponse:
    return templates.TemplateResponse(request, nome, contexto)


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request, con: Conexao) -> HTMLResponse:
    return _pagina(request, "inicio.html", {"numeros": consultas.numeros_gerais(con)})


@router.get("/autores", response_class=HTMLResponse)
def autores(request: Request, con: Conexao, ordenar_por: str = Query("bayesiana")) -> HTMLResponse:
    if ordenar_por not in ("bayesiana", "media", "volume"):
        ordenar_por = "bayesiana"
    return _pagina(
        request,
        "autores.html",
        {
            "autores": consultas.ranking_de_autores(con, ordenar_por),
            "ordenar_por": ordenar_por,
        },
    )


@router.get("/autores/{autor}", response_class=HTMLResponse)
def autor(request: Request, con: Conexao, autor: str) -> HTMLResponse:
    return _pagina(request, "autor.html", {"dados": consultas.performance_do_autor(con, autor)})


@router.get("/generos", response_class=HTMLResponse)
def generos(request: Request, con: Conexao) -> HTMLResponse:
    return _pagina(request, "generos.html", {"generos": consultas.ranking_de_generos(con)})


@router.get("/generos/{categoria}", response_class=HTMLResponse)
def genero(request: Request, con: Conexao, categoria: str) -> HTMLResponse:
    return _pagina(
        request, "genero.html", {"dados": consultas.performance_do_genero(con, categoria)}
    )


@router.get("/reviews", response_class=HTMLResponse)
def reviews(
    request: Request,
    con: Conexao,
    nota: float | None = None,
    ano_de: int | None = None,
    ano_ate: int | None = None,
    genero_nome: str | None = None,
) -> HTMLResponse:
    achadas = consultas.buscar_reviews(
        con, nota=nota, ano_de=ano_de, ano_ate=ano_ate, genero=genero_nome
    )
    contexto: dict[str, Any] = {
        "reviews": achadas,
        "filtros": {
            "nota": nota,
            "ano_de": ano_de,
            "ano_ate": ano_ate,
            "genero_nome": genero_nome,
        },
    }
    if e_htmx(request):
        return _pagina(request, "_tabela_reviews.html", contexto)
    return _pagina(request, "reviews.html", contexto)


@router.get("/entrevistas", response_class=HTMLResponse)
def entrevistas(request: Request, con: Conexao) -> HTMLResponse:
    return _pagina(
        request, "entrevistas.html", {"candidatos": consultas.candidatos_a_entrevista(con)}
    )


@router.post("/entrevistas/aprovar", response_class=HTMLResponse)
def aprovar(request: Request, prefixo: Annotated[str, Form()]) -> HTMLResponse:
    """Gate humano da spec 04. Recebe só o prefixo — o pseudônimo inteiro não vai ao navegador.

    Aprovar não revela nada a mais nem persiste: o export é F3, e lá a referência estável deve
    ser um token do lado do servidor, não o identificador no HTML.
    """
    return _pagina(request, "_aprovacao.html", {"prefixo": prefixo})


@router.get("/chat", response_class=HTMLResponse)
def chat(request: Request) -> HTMLResponse:
    return _pagina(request, "chat.html", {"resposta": None, "pergunta": ""})


@router.post("/chat", response_class=HTMLResponse)
def perguntar(request: Request, con: Conexao, pergunta: Annotated[str, Form()]) -> HTMLResponse:
    resposta = roteador.responder(con, pergunta)
    contexto: dict[str, Any] = {"resposta": resposta, "pergunta": pergunta}
    if e_htmx(request):
        return _pagina(request, "_resposta_chat.html", contexto)
    return _pagina(request, "chat.html", contexto)
