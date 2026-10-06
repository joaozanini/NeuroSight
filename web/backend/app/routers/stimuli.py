"""Estímulos (W09–W11): a biblioteca de imagens e vídeos que o óculos mostra nas sessões.

Ver a biblioteca exige só o login. Enviar e editar exigem "Enviar e editar estímulos"; arquivar,
desarquivar e excluir, "Arquivar estímulos". Cada arquivo sobe num request próprio (o progresso é
por arquivo) e fica como rascunho de quem enviou até "Salvar na biblioteca", que cria todos de uma
vez, num registro só da auditoria, e agenda a versão para o óculos em segundo plano.

Só o que nunca foi usado em sessões pode ser excluído; o resto é arquivado.
"""
import logging
import os
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import get_db
from ..models import Session, SessionStimulus, Stimulus, StimulusTag, User
from ..schemas.stimulus import (
    LibraryCounts, StimulusCard, StimulusDetail, StimulusDraft, StimulusPage, StimulusSave, StimulusSession,
    StimulusStatusChange, StimulusUpdate,
)
from ..security import CurrentUser, require_permission
from ..services import audit, media, stimuli
from ..services import sessions as session_rules
from ..services.storage import storage

router = APIRouter()
logger = logging.getLogger(__name__)

EditStimuli = require_permission("stimuli.edit")
ArchiveStimuli = require_permission("stimuli.archive")

NOT_FOUND = "estímulo não encontrado"
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "mp4": "video/mp4"}
# Os arquivos de um id nunca mudam (trocar o arquivo é enviar outro estímulo).
IMMUTABLE = {"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}


def _url(stimulus_id: str, what: str) -> str:
    return f"{settings.api_prefix}/stimuli/{stimulus_id}/{what}"


def _card(s: Stimulus) -> StimulusCard:
    return StimulusCard(id=s.id, name=s.name, kind=s.kind, status=s.status, tags=s.tags,
                        duration_seconds=s.duration_seconds, thumbnail_url=_url(s.id, "thumbnail"))


def _draft(s: Stimulus) -> StimulusDraft:
    return StimulusDraft(
        id=s.id, original_filename=s.original_filename, suggested_name=s.name, kind=s.kind, format=s.format,
        size_bytes=s.size_bytes, width=s.width, height=s.height, duration_seconds=s.duration_seconds,
        thumbnail_url=_url(s.id, "thumbnail"),
    )


def _sessions(db: DbSession, s: Stimulus, user: User) -> list[StimulusSession]:
    """"Usado em N sessões" (W11): as que a pessoa pode ver, das mais recentes para as mais antigas."""
    rows = db.scalars(
        select(Session).join(SessionStimulus, SessionStimulus.session_id == Session.id)
        .where(SessionStimulus.stimulus_id == s.id, session_rules.visible_to(db, user))
        .order_by(session_rules.session_date.desc(), Session.created_at.desc())
    ).all()
    return [StimulusSession(id=r.id, title=r.title, patient_code=r.patient.code, date=r.started_at or r.created_at)
            for r in rows]


def _detail(db: DbSession, s: Stimulus, user: User) -> StimulusDetail:
    used = stimuli.usage_count(db, s)
    return StimulusDetail(
        id=s.id, name=s.name, description=s.description, kind=s.kind, format=s.format, status=s.status,
        original_filename=s.original_filename, size_bytes=s.size_bytes, width=s.width, height=s.height,
        duration_seconds=s.duration_seconds, has_audio=s.has_audio, tags=s.tags, created_at=s.created_at,
        created_by_name=s.created_by.name if s.created_by else None, thumbnail_url=_url(s.id, "thumbnail"),
        file_url=_url(s.id, "file"), device_status=s.device_status, device_error=s.device_error,
        sessions_count=used, sessions=_sessions(db, s, user) if used else [], can_delete=used == 0,
    )


def _visible(db: DbSession, stimulus_id: str, user: User) -> Stimulus:
    """O estímulo, se a pessoa pode vê-lo: rascunho só para quem enviou."""
    s = db.get(Stimulus, stimulus_id)
    if s is None or (s.status == "draft" and s.created_by_id != user.id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return s


def _in_library(db: DbSession, stimulus_id: str) -> Stimulus:
    s = db.get(Stimulus, stimulus_id)
    if s is None or s.status == "draft":
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return s


def _tag_filter(condition):
    return Stimulus.id.in_(select(StimulusTag.stimulus_id).where(condition))


@router.get("/stimuli", response_model=StimulusPage)
def list_stimuli(
    user: CurrentUser,
    q: str = Query("", max_length=120),
    kind: Literal["image", "video"] | None = Query(None),
    tag: str | None = Query(None, max_length=40),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=100),
    db: DbSession = Depends(get_db),
):
    filters = [Stimulus.status.in_(("active", "archived") if include_archived else ("active",))]
    if kind:
        filters.append(Stimulus.kind == kind)
    if tag and tag.strip():
        filters.append(_tag_filter(StimulusTag.tag == stimuli.normalize_tag(tag)))
    if q.strip():
        term = q.strip()
        filters.append(or_(
            Stimulus.name.icontains(term, autoescape=True),
            _tag_filter(StimulusTag.tag.icontains(stimuli.normalize_tag(term), autoescape=True)),
        ))

    total = db.scalar(select(func.count()).select_from(Stimulus).where(*filters)) or 0
    order = (case((Stimulus.status == "archived", 1), else_=0), Stimulus.created_at.desc(), Stimulus.name)
    rows = db.scalars(select(Stimulus).where(*filters).order_by(*order).limit(page_size).offset((page - 1) * page_size))
    kinds = dict(db.execute(
        select(Stimulus.kind, func.count()).where(Stimulus.status == "active").group_by(Stimulus.kind)
    ).all())
    images, videos = kinds.get("image", 0), kinds.get("video", 0)
    return StimulusPage(
        items=[_card(s) for s in rows], total=total, page=page, page_size=page_size,
        counts=LibraryCounts(total=images + videos, images=images, videos=videos),
    )


@router.get("/stimuli/tags", response_model=list[str])
def list_tags(user: CurrentUser, include_archived: bool = Query(False), db: DbSession = Depends(get_db)):
    """Etiquetas em uso, para o filtro "Todas as etiquetas"."""
    statuses = ("active", "archived") if include_archived else ("active",)
    tags = db.scalars(
        select(StimulusTag.tag).join(Stimulus).where(Stimulus.status.in_(statuses)).distinct()
    ).all()
    return sorted(tags, key=lambda t: (stimuli.sort_key(t), t))


@router.post("/stimuli/uploads", response_model=StimulusDraft, status_code=201)
def upload_stimulus(file: UploadFile = File(...), me: User = Depends(EditStimuli), db: DbSession = Depends(get_db)):
    """Um arquivo da W10. Fica como rascunho de quem enviou até "Salvar na biblioteca"."""
    stimuli.purge_stale_drafts(db)
    limit = settings.max_stimulus_mb * 1024 * 1024
    if file.size is not None and file.size > limit:
        raise HTTPException(status_code=413, detail=f"o arquivo passa do limite de {settings.max_stimulus_mb} MB")
    try:
        draft = stimuli.create_draft(db, me, file.file, file.filename or "")
    except media.MediaError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    db.commit()
    logger.info("rascunho de estímulo %s (%s, %s) enviado por %s", draft.id, draft.original_filename,
                draft.format, me.email)
    return _draft(draft)


@router.delete("/stimuli/uploads/{stimulus_id}", status_code=204)
def discard_upload(stimulus_id: str, me: User = Depends(EditStimuli), db: DbSession = Depends(get_db)):
    """Cancelar ou Remover na W10: o rascunho sai do disco. Só quem enviou."""
    s = db.get(Stimulus, stimulus_id)
    if s is None or s.status != "draft" or s.created_by_id != me.id:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    db.delete(s)
    db.commit()
    storage.delete_stimulus(stimulus_id)


@router.post("/stimuli", response_model=list[StimulusCard], status_code=201)
def save_to_library(body: StimulusSave, request: Request, background: BackgroundTasks,
                    me: User = Depends(EditStimuli), db: DbSession = Depends(get_db)):
    """"Salvar na biblioteca": os rascunhos viram estímulos, com nome, descrição e etiquetas."""
    ids = [item.id for item in body.items]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="o mesmo arquivo veio mais de uma vez")
    drafts = {s.id: s for s in db.scalars(select(Stimulus).where(Stimulus.id.in_(ids)))}
    for item in body.items:
        s = drafts.get(item.id)
        if s is None or s.status != "draft" or s.created_by_id != me.id:
            raise HTTPException(status_code=409, detail="um dos arquivos não está mais disponível. Envie-o de novo")

    saved = []
    for item in body.items:
        s = drafts[item.id]
        s.name, s.description, s.status = item.name, item.description, "active"
        s.set_tags(item.tags)
        saved.append(s)
    db.flush()
    stimuli.audit_saved(db, request, me, saved)
    db.commit()
    background.add_task(stimuli.process_device_versions, ids)
    logger.info("%d estímulo(s) salvo(s) na biblioteca por %s", len(saved), me.email)
    return [_card(s) for s in saved]


@router.get("/stimuli/{stimulus_id}", response_model=StimulusDetail)
def get_stimulus(stimulus_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    return _detail(db, _visible(db, stimulus_id, user), user)


@router.patch("/stimuli/{stimulus_id}", response_model=StimulusDetail)
def update_stimulus(stimulus_id: str, body: StimulusUpdate, request: Request, me: User = Depends(EditStimuli),
                    db: DbSession = Depends(get_db)):
    s = _in_library(db, stimulus_id)
    before = stimuli.snapshot(s)
    if body.name is not None:
        s.name = body.name
    if "description" in body.model_fields_set:
        s.description = body.description
    if body.tags is not None:
        s.set_tags(body.tags)
    changes = audit.diff(before, stimuli.snapshot(s), stimuli.FIELD_LABELS)
    if changes:
        audit.record(db, request, me, "update", "stimulus", s.name, s.id, changes)
        db.commit()
        logger.info("estímulo %s alterado por %s: %s", s.id, me.email, [c["field"] for c in changes])
    return _detail(db, s, me)


@router.put("/stimuli/{stimulus_id}/status", response_model=StimulusDetail)
def change_status(stimulus_id: str, body: StimulusStatusChange, request: Request, me: User = Depends(ArchiveStimuli),
                  db: DbSession = Depends(get_db)):
    """Arquivar (sai da biblioteca e não entra em novas sessões) ou desarquivar."""
    s = _in_library(db, stimulus_id)
    if s.status != body.status:
        before = stimuli.snapshot(s)
        s.status = body.status
        audit.record(db, request, me, "update", "stimulus", s.name, s.id,
                     audit.diff(before, stimuli.snapshot(s), {"status": stimuli.FIELD_LABELS["status"]}))
        db.commit()
        logger.info("estímulo %s %s por %s", s.id, "arquivado" if body.status == "archived" else "desarquivado",
                    me.email)
    return _detail(db, s, me)


@router.delete("/stimuli/{stimulus_id}", status_code=204)
def delete_stimulus(stimulus_id: str, request: Request, me: User = Depends(ArchiveStimuli),
                    db: DbSession = Depends(get_db)):
    s = _in_library(db, stimulus_id)
    if stimuli.usage_count(db, s) > 0:
        raise HTTPException(status_code=409, detail="este estímulo já foi usado em sessões e não pode ser excluído. Arquive-o")
    changes = audit.diff(stimuli.snapshot(s), {}, stimuli.FIELD_LABELS)
    changes.append(audit.change("file", "Arquivo", s.original_filename, None))
    audit.record(db, request, me, "delete", "stimulus", s.name, s.id, changes)
    db.delete(s)
    db.commit()
    storage.delete_stimulus(stimulus_id)
    logger.info("estímulo %s (%s) excluído por %s", stimulus_id, s.original_filename, me.email)


@router.get("/stimuli/{stimulus_id}/thumbnail")
def get_thumbnail(stimulus_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    s = _visible(db, stimulus_id, user)
    path = storage.stimulus_thumbnail(s.id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="miniatura não disponível")
    return FileResponse(path, media_type="image/jpeg", headers=IMMUTABLE)


@router.get("/stimuli/{stimulus_id}/file")
def get_file(stimulus_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    """O arquivo original, para a prévia da W11 (o <video> busca por Range)."""
    s = _visible(db, stimulus_id, user)
    path = storage.stimulus_original(s.id, s.format)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="arquivo não disponível")
    return FileResponse(path, media_type=MEDIA_TYPES[s.format], filename=s.original_filename,
                        content_disposition_type="inline", headers=IMMUTABLE)
