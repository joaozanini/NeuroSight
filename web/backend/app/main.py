"""App FastAPI: CORS, tabelas no startup, rotas da API e (em produção) o site estático.

Em produção a MESMA origem serve o site (build do React em `static_dir`) e a API em /api,
então não há CORS entre front e back. No dev, o Vite serve o front na 5173 com proxy /api.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import ingest, sessions
from .security import require_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.media_root, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="QuestPro Eye-Tracking API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

# Escrita (ingestão) exige X-Api-Key quando QUESTPRO_API_KEY está definida.
app.include_router(
    ingest.router, prefix=settings.api_prefix, tags=["ingest"],
    dependencies=[Depends(require_api_key)],
)
app.include_router(sessions.router, prefix=settings.api_prefix, tags=["sessions"])


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---- Site estático (build do React) -------------------------------------------------------
# Servido só se a pasta existir (produção). Rotas registradas ANTES (api/healthz/docs) têm
# prioridade; o catch-all devolve index.html para as rotas do SPA (ex.: /sessions/<id>).
_static = os.path.abspath(settings.static_dir) if settings.static_dir else ""
if _static and os.path.isdir(_static):
    _assets = os.path.join(_static, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = os.path.join(_static, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_static, "index.html"))
