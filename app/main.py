"""Ponto de entrada da interface web. Sobe com `make app`."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import api, rotas
from app.base import DIRETORIO

app = FastAPI(title="ReviewLens", docs_url="/docs")
app.mount("/static", StaticFiles(directory=str(DIRETORIO / "static")), name="static")
app.include_router(rotas.router)
app.include_router(api.router)
