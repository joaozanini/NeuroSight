"""Leitura: lista paginada (sem samples), detalhe (com tudo), vídeo (Range) e delete."""
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import get_db
from ..models import Session
from ..security import require_api_key
from ..services.storage import storage

router = APIRouter()


def to_summary(s: Session) -> dict:
    return {
        "id": s.id,
        "device_session_id": s.device_session_id,
        "status": s.status,
        "captured_at": s.captured_at.isoformat() if s.captured_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "duration_seconds": s.duration_seconds,
        "frame_count": s.frame_count,
        "declared_frame_count": s.declared_frame_count,
        "sample_count": s.sample_count,
        "valid_sample_count": s.valid_sample_count,
        "frame_width": s.frame_width,
        "frame_height": s.frame_height,
        "video_fps": s.video_fps,
        "video_codec": s.video_codec,
        "has_video": bool(s.video_path),
    }


@router.get("/sessions")
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Session))
    rows = db.scalars(
        select(Session).order_by(Session.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return {"items": [to_summary(s) for s in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/sessions/{sid}")
def get_session(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(Session, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")
    d = to_summary(s)
    d.update({
        "meta": s.meta,
        "frames": s.frames,
        "samples": s.samples,
        "uv_origin": s.uv_origin,
        "capture_fov_deg": s.capture_fov_deg,
        "video_url": f"{settings.api_prefix}/sessions/{s.id}/video" if s.video_path else None,
        "error_detail": s.error_detail,
    })
    return d


@router.get("/sessions/{sid}/video")
def get_video(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(Session, sid)
    if s is None or not s.video_path or not os.path.isfile(s.video_path):
        raise HTTPException(status_code=404, detail="vídeo não disponível")
    # FileResponse do Starlette já trata o header Range (206) para o <video> conseguir buscar.
    # inline (não attachment) para o navegador tocar em vez de baixar.
    return FileResponse(s.video_path, media_type="video/mp4", content_disposition_type="inline")


@router.delete("/sessions/{sid}", dependencies=[Depends(require_api_key)])
def delete_session(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(Session, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")
    storage.delete_session(sid)
    db.delete(s)
    db.commit()
    return {"deleted": sid}
