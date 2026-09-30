"""Mesmos dados das telas, em JSON — o proveito concreto de ter escolhido FastAPI (ADR-010)."""

from typing import Annotated, Any

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from app.base import obter_conexao
from bri.data import consultas

router = APIRouter(prefix="/api")

Conexao = Annotated[duckdb.DuckDBPyConnection, Depends(obter_conexao)]


@router.get("/numeros")
def numeros(con: Conexao) -> dict[str, Any]:
    return consultas.numeros_gerais(con)


@router.get("/autores")
def autores(con: Conexao, ordenar_por: str = Query("bayesiana")) -> list[dict[str, Any]]:
    """Ordenação fora da allowlist é erro do cliente, não do servidor: 400, não 500.

    A tela HTML cai em silêncio para o padrão; aqui o cliente é um programa e precisa saber que
    mandou um valor inválido, em vez de receber uma lista ordenada por outro critério.
    """
    try:
        return consultas.ranking_de_autores(con, ordenar_por)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@router.get("/autores/{autor}")
def autor(con: Conexao, autor: str) -> dict[str, Any]:
    return consultas.performance_do_autor(con, autor)


@router.get("/generos")
def generos(con: Conexao) -> list[dict[str, Any]]:
    return consultas.ranking_de_generos(con)


@router.get("/reviews")
def reviews(
    con: Conexao,
    nota: float | None = None,
    ano_de: int | None = None,
    ano_ate: int | None = None,
    limite: int = 50,
) -> list[dict[str, Any]]:
    return consultas.buscar_reviews(con, nota=nota, ano_de=ano_de, ano_ate=ano_ate, limite=limite)


@router.get("/entrevistas")
def entrevistas(con: Conexao) -> list[dict[str, Any]]:
    return consultas.candidatos_a_entrevista(con)
