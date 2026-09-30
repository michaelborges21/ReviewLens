"""Páginas HTML e fragmentos HTMX."""

from typing import Annotated, Any

import duckdb
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse

from app.base import e_htmx, obter_conexao, templates
from bri.agent import conversa, exportar, narrador, roteador
from bri.agent.roteador import Intencao
from bri.data import consultas, graficos, nuvem

router = APIRouter()

Conexao = Annotated[duckdb.DuckDBPyConnection, Depends(obter_conexao)]

NOME_COOKIE = "sessao_id"


def _sessao_id(request: Request) -> str:
    return request.cookies.get(NOME_COOKIE) or conversa.novo_id_sessao()


def _com_cookie(resposta: HTMLResponse, sessao_id: str, request: Request) -> HTMLResponse:
    """Só reescreve o cookie quando o id mudou — evita resetar validade a cada resposta."""
    if request.cookies.get(NOME_COOKIE) != sessao_id:
        resposta.set_cookie(NOME_COOKIE, sessao_id, httponly=True, samesite="lax")
    return resposta


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
    return _pagina(
        request,
        "autor.html",
        {
            "dados": consultas.performance_do_autor(con, autor),
            "aspectos": consultas.aspectos_do_autor(con, autor),
            "resumo": consultas.resumo_da_entidade(con, "autor", autor),
        },
    )


@router.get("/generos", response_class=HTMLResponse)
def generos(request: Request, con: Conexao) -> HTMLResponse:
    return _pagina(request, "generos.html", {"generos": consultas.ranking_de_generos(con)})


@router.get("/generos/{categoria}", response_class=HTMLResponse)
def genero(request: Request, con: Conexao, categoria: str) -> HTMLResponse:
    return _pagina(
        request,
        "genero.html",
        {
            "dados": consultas.performance_do_genero(con, categoria),
            "aspectos": consultas.aspectos_do_genero(con, categoria),
            "resumo": consultas.resumo_da_entidade(con, "genero", categoria),
        },
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
    # A <datalist> mora em reviews.html, fora do bloco que o HTMX troca — não precisa
    # recarregar os 10.883 gêneros a cada filtro, só na primeira carga da página.
    contexto["generos"] = consultas.todos_os_generos(con)
    return _pagina(request, "reviews.html", contexto)


@router.get("/nuvem", response_class=HTMLResponse)
def nuvem_de_palavras(request: Request, con: Conexao, categoria: str | None = None) -> HTMLResponse:
    imagem = None
    mensagem = None
    if categoria:
        frequencias = nuvem.frequencia_de_palavras(con, categoria)
        imagem = nuvem.gerar_nuvem(frequencias)
        if imagem is None:
            mensagem = f"Sem avaliações suficientes para gerar uma nuvem de '{categoria}'."

    contexto: dict[str, Any] = {"categoria": categoria, "imagem": imagem, "mensagem": mensagem}
    if e_htmx(request):
        return _pagina(request, "_nuvem_imagem.html", contexto)
    contexto["generos"] = consultas.generos_elegiveis_para_nuvem(con)
    return _pagina(request, "nuvem.html", contexto)


@router.get("/entrevistas", response_class=HTMLResponse)
def entrevistas(request: Request, con: Conexao) -> HTMLResponse:
    return _pagina(
        request, "entrevistas.html", {"candidatos": consultas.candidatos_a_entrevista(con)}
    )


@router.post("/entrevistas/aprovar", response_class=HTMLResponse)
def aprovar(request: Request, con: Conexao, prefixo: Annotated[str, Form()]) -> HTMLResponse:
    """Gate humano da spec 04 para as duas linhas 'sim': revelar o candidato e exportá-lo.

    O prefixo do formulário é só chave de busca — a linha completa vem de nova consulta ao banco,
    reaplicando os critérios de elegibilidade, nunca dos dados que o navegador mandou.
    """
    candidato = consultas.candidato_por_prefixo(con, prefixo)
    if candidato is None:
        return _pagina(request, "_aprovacao.html", {"prefixo": prefixo, "candidato": None})
    # raiz explícito, não o default do parâmetro: o default é capturado na definição da função,
    # então testar sobrescrevendo exportar.RAIZ_EXPORTS via monkeypatch não o alcançaria.
    exportar.exportar_candidato(candidato, raiz=exportar.RAIZ_EXPORTS)
    return _pagina(request, "_aprovacao.html", {"prefixo": prefixo, "candidato": candidato})


@router.get("/chat", response_class=HTMLResponse)
def chat(request: Request) -> HTMLResponse:
    sessao_id = _sessao_id(request)
    estado = conversa.obter(sessao_id)
    contexto = {
        "resposta": None,
        "narrada": None,
        "pergunta": "",
        "turnos": estado.turnos,
        "entidade_herdada": estado.ultima_entidade,
    }
    return _com_cookie(_pagina(request, "chat.html", contexto), sessao_id, request)


def _grafico_da_resposta(resposta: roteador.Resposta) -> str | None:
    """Só AUTOR e GENERO têm dado com forma de série — mista e visão geral são uma linha só,
    agregada, e forçar gráfico ali seria inventar visualização sem conteúdo real."""
    if resposta.intencao is Intencao.AUTOR:
        return graficos.grafico_autor(resposta.dados)
    if resposta.intencao is Intencao.GENERO:
        return graficos.grafico_genero(resposta.dados)
    return None


@router.post("/chat", response_class=HTMLResponse)
def perguntar(request: Request, con: Conexao, pergunta: Annotated[str, Form()]) -> HTMLResponse:
    sessao_id = _sessao_id(request)  # cobre POST direto sem GET prévio (bookmark, teste)
    estado = conversa.obter(sessao_id)

    resposta = roteador.responder(con, pergunta, entidade_herdada=estado.ultima_entidade)
    narrada = narrador.narrar(pergunta, resposta)

    texto_final = narrada.resposta if narrada else resposta.texto
    conversa.registrar_turno(sessao_id, pergunta, texto_final)
    if resposta.entidade_herdavel:
        conversa.atualizar_entidade(sessao_id, *resposta.entidade_herdavel)

    contexto: dict[str, Any] = {
        "resposta": resposta,
        "narrada": narrada,
        "pergunta": pergunta,
        "turnos": conversa.obter(sessao_id).turnos,
        "entidade_herdada": conversa.obter(sessao_id).ultima_entidade,
        "grafico": _grafico_da_resposta(resposta),
    }
    pagina = "_resposta_chat.html" if e_htmx(request) else "chat.html"
    return _com_cookie(_pagina(request, pagina, contexto), sessao_id, request)


@router.post("/chat/limpar-filtro", response_class=HTMLResponse)
def limpar_filtro(request: Request) -> HTMLResponse:
    sessao_id = _sessao_id(request)
    conversa.limpar_entidade(sessao_id)
    estado = conversa.obter(sessao_id)
    contexto = {
        "resposta": None,
        "narrada": None,
        "pergunta": "",
        "turnos": estado.turnos,
        "entidade_herdada": None,
    }
    pagina = "_resposta_chat.html" if e_htmx(request) else "chat.html"
    return _com_cookie(_pagina(request, pagina, contexto), sessao_id, request)
