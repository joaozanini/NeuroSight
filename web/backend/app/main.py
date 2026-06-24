"""App FastAPI: CORS, criação das tabelas no startup e registro das rotas."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import ingest, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.media_root, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="QuestPro Eye-Tracking API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(ingest.router, prefix=settings.api_prefix, tags=["ingest"])
app.include_router(sessions.router, prefix=settings.api_prefix, tags=["sessions"])


@app.get("/healthz")
def healthz():
    return {"ok": True}
