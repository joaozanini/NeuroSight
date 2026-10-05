"""Leitura: lista paginada (sem samples), detalhe (com tudo), vídeo (Range) e delete."""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import get_db
from ..models import Session
from ..schemas.session import SessionDeleted, SessionDetail, SessionPage, SessionSummary
from ..security import require_api_key
from ..services.storage import storage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/sessions", response_model=SessionPage)
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Session))
    rows = db.scalars(
        select(Session).order_by(Session.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return SessionPage(
        items=[SessionSummary.model_validate(s) for s in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{sid}", response_model=SessionDetail)
def get_session(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(Session, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")
    summary = SessionSummary.model_validate(s)
    return SessionDetail(
        **summary.model_dump(),
        meta=s.meta,
        frames=s.frames,
        samples=s.samples,
        uv_origin=s.uv_origin,
        capture_fov_deg=s.capture_fov_deg,
        video_url=f"{settings.api_prefix}/sessions/{s.id}/video" if s.video_path else None,
        error_detail=s.error_detail,
    )


@router.get("/sessions/{sid}/video")
def get_video(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(Session, sid)
    if s is None or not s.video_path or not os.path.isfile(s.video_path):
        raise HTTPException(status_code=404, detail="vídeo não disponível")
    # FileResponse do Starlette já trata o header Range (206) para o <video> conseguir buscar.
    # inline (não attachment) para o navegador tocar em vez de baixar.
    return FileResponse(s.video_path, media_type="video/mp4", content_disposition_type="inline")


@router.delete("/sessions/{sid}", response_model=SessionDeleted, dependencies=[Depends(require_api_key)])
def delete_session(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(Session, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")
    storage.delete_session(sid)
    db.delete(s)
    db.commit()
    logger.info("sessão %s (%s) apagada com a mídia", sid, s.device_session_id)
    return SessionDeleted(deleted=sid)
