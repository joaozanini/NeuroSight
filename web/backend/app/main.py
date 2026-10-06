"""App FastAPI: logging, migrações no startup, rotas da API e (em produção) o site estático.

Em produção a MESMA origem serve o site (build do React em `static_dir`) e a API em /api,
então não há CORS entre front e back. No dev, o Vite serve o front na 5173 com proxy /api.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import migrate
from .logging_config import setup_logging
from .routers import (
    audit, auth, device, legacy_sessions, live, me, patients, permissions, session_data, sessions, stimuli, users,
)
from .schemas.common import Health
from .services import ingestion
from .services.stimuli import resume_pending

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.media_root, exist_ok=True)
    migrate()
    resume_pending()
    ingestion.resume_pending()
    logger.info(
        "API pronta: mídia em %s, site estático %s",
        os.path.abspath(settings.media_root), _static if _serves_site else "desligado (modo dev)",
    )
    if _serves_site and not settings.device_key:
        logger.warning("QUESTPRO_DEVICE_KEY vazia: qualquer um pode se conectar como óculos")
    if _serves_site and "localhost" in settings.public_base_url:
        logger.warning(
            "os links de convite e de redefinição apontam para %s; defina QUESTPRO_PUBLIC_BASE_URL "
            "com o endereço do servidor", settings.public_base_url,
        )
    yield


app = FastAPI(title="NeuroSight API", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
    # O login do site é por cookie.
    allow_credentials=True,
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(sessions.router, prefix=settings.api_prefix, tags=["sessions"])
app.include_router(session_data.router, prefix=settings.api_prefix, tags=["session data"])
app.include_router(live.router, prefix=settings.api_prefix, tags=["live"])
app.include_router(device.router, prefix=settings.api_prefix, tags=["device"])
app.include_router(legacy_sessions.router, prefix=settings.api_prefix, tags=["legacy"])
app.include_router(auth.router, prefix=settings.api_prefix, tags=["auth"])
app.include_router(me.router, prefix=settings.api_prefix, tags=["me"])
app.include_router(users.router, prefix=settings.api_prefix, tags=["users"])
app.include_router(permissions.router, prefix=settings.api_prefix, tags=["permissions"])
app.include_router(audit.router, prefix=settings.api_prefix, tags=["audit"])
app.include_router(patients.router, prefix=settings.api_prefix, tags=["patients"])
app.include_router(stimuli.router, prefix=settings.api_prefix, tags=["stimuli"])


@app.get("/healthz", response_model=Health)
def healthz():
    return Health(ok=True)


# ---- Site estático (build do React) -------------------------------------------------------

def resolve_static_file(root: str, requested: str) -> str | None:
    """Caminho real de um arquivo DENTRO de `root`, ou None se não existir ou escapar da pasta.

    O caminho vem da URL: `//etc/passwd` chega como "/etc/passwd", e `os.path.join` com um caminho
    absoluto descarta `root`; `..` (inclusive codificado como %2e%2e) sobe de pasta; um symlink
    pode apontar para fora. Por isso o caminho é resolvido e só vale se continuar sob `root`.
    """
    root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root, requested.lstrip("/\\")))
    try:
        inside = os.path.commonpath([root, candidate]) == root
    except ValueError:  # drives diferentes no Windows
        inside = False
    if not inside or not os.path.isfile(candidate):
        return None
    return candidate


# Servido só se a pasta existir (produção). Rotas registradas ANTES (api/healthz/docs) têm
# prioridade; o catch-all devolve index.html para as rotas do SPA (ex.: /sessoes/<id>).
_static = os.path.realpath(settings.static_dir) if settings.static_dir else ""
_serves_site = bool(_static) and os.path.isdir(_static)
if _serves_site:
    _assets = os.path.join(_static, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    _api_root = settings.api_prefix.strip("/").split("/")[0]

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Rota de API inexistente responde 404 em JSON, não com o index.html do site.
        if full_path == _api_root or full_path.startswith(_api_root + "/"):
            raise HTTPException(status_code=404, detail="rota não encontrada")
        found = resolve_static_file(_static, full_path) if full_path else None
        return FileResponse(found or os.path.join(_static, "index.html"))
