"""Sessões do fluxo antigo (cena 3D), só para leitura: lista, detalhe (com tudo) e vídeo (Range).

O fluxo antigo foi substituído pelas sessões configuradas no site; a ingestão dele saiu e ninguém
grava mais nesta tabela. Com QUESTPRO_API_KEY definida, ler exige o login do site ou a X-Api-Key.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import get_db
from ..models import LegacySession
from ..schemas.legacy_session import LegacySessionDetail, LegacySessionPage, LegacySessionSummary
from ..security import require_reader

router = APIRouter(prefix="/legacy", dependencies=[Depends(require_reader)])


@router.get("/sessions", response_model=LegacySessionPage)
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(LegacySession))
    rows = db.scalars(
        select(LegacySession).order_by(LegacySession.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return LegacySessionPage(
        items=[LegacySessionSummary.model_validate(s) for s in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{sid}", response_model=LegacySessionDetail)
def get_session(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(LegacySession, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")
    summary = LegacySessionSummary.model_validate(s)
    return LegacySessionDetail(
        **summary.model_dump(),
        meta=s.meta,
        frames=s.frames,
        samples=s.samples,
        uv_origin=s.uv_origin,
        capture_fov_deg=s.capture_fov_deg,
        video_url=f"{settings.api_prefix}/legacy/sessions/{s.id}/video" if s.video_path else None,
        error_detail=s.error_detail,
    )


@router.get("/sessions/{sid}/video")
def get_video(sid: str, db: DbSession = Depends(get_db)):
    s = db.get(LegacySession, sid)
    if s is None or not s.video_path or not os.path.isfile(s.video_path):
        raise HTTPException(status_code=404, detail="vídeo não disponível")
    # FileResponse do Starlette já trata o header Range (206) para o <video> conseguir buscar.
    # inline (não attachment) para o navegador tocar em vez de baixar.
    return FileResponse(s.video_path, media_type="video/mp4", content_disposition_type="inline")
