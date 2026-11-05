"""Ingestão em 3 passos: create (gaze.json) -> frames (lotes multipart) -> complete (monta MP4).

Idempotente por X-Session-Id: re-rodar o device retoma a mesma linha/pasta, e frames são
sobrescritos por nome. Assim um upload interrompido pode ser continuado sem duplicar nada.
"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import SessionLocal, get_db
from ..models import Session
from ..services.storage import storage
from ..services.video import assemble_mp4
from ..utils import compute_rollups, parse_captured_at

router = APIRouter()


def _f(v):
    return float(v) if v is not None else None


def _i(v):
    return int(v) if v else None


@router.post("/sessions")
async def create_session(
    request: Request,
    x_session_id: str = Header(..., alias="X-Session-Id"),
    db: DbSession = Depends(get_db),
):
    """Cria/atualiza a sessão a partir do gaze.json cru no corpo. Devolve o id do servidor."""
    raw = await request.body()
    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="corpo não é JSON válido")

    meta = data.get("meta", {}) or {}
    frames = data.get("frames", []) or []
    samples = data.get("samples", []) or []
    sample_count, valid_count, duration = compute_rollups(frames, samples)

    sess = db.scalar(select(Session).where(Session.device_session_id == x_session_id))
    if sess is None:
        sess = Session(device_session_id=x_session_id, status="uploading")
        db.add(sess)
        db.flush()  # gera o id

    sess.status = "uploading"
    sess.meta = meta
    sess.frames = frames
    sess.samples = samples
    sess.capture_fov_deg = _f(meta.get("captureFovDeg"))
    sess.frame_width = _i(meta.get("frameWidth"))
    sess.frame_height = _i(meta.get("frameHeight"))
    sess.video_fps = _f(meta.get("videoFps"))
    sess.uv_origin = meta.get("uvOrigin", "top-left")
    sess.declared_frame_count = len(frames)
    sess.sample_count = sample_count
    sess.valid_sample_count = valid_count
    sess.duration_seconds = duration
    sess.captured_at = parse_captured_at(x_session_id)
    sess.media_dir = storage.session_dir(sess.id)
    storage.ensure_frames_dir(sess.id)
    sess.frame_count = storage.count_frames(sess.id)  # >0 se for retomada
    db.commit()
    db.refresh(sess)

    return {
        "id": sess.id,
        "status": sess.status,
        "expected_frames": sess.declared_frame_count,
        "received_frames": sess.frame_count,
    }


@router.post("/sessions/{sid}/frames")
async def upload_frames(
    sid: str,
    frames: list[UploadFile] = File(...),
    db: DbSession = Depends(get_db),
):
    """Recebe um lote de JPEGs (campo multipart 'frames'). Grava em streaming, valida o magic."""
    sess = db.get(Session, sid)
    if sess is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")

    storage.ensure_frames_dir(sid)
    saved, rejected = [], []
    for uf in frames:
        name = os.path.basename(uf.filename or "")
        if not name.lower().endswith(".jpg"):
            rejected.append(uf.filename or "?")
            continue
        head = await uf.read(3)
        if head[:3] != b"\xff\xd8\xff":  # não é JPEG
            rejected.append(name)
            continue
        dest = storage.frame_path(sid, name)
        with open(dest, "wb") as out:
            out.write(head)
            while True:
                chunk = await uf.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        saved.append(name)

    sess.frame_count = storage.count_frames(sid)
    db.commit()
    return {"received_frames": sess.frame_count, "saved": saved, "rejected": rejected}


@router.post("/sessions/{sid}/complete")
def complete_session(sid: str, background: BackgroundTasks, db: DbSession = Depends(get_db)):
    """Finaliza o upload e agenda a montagem do MP4 em BACKGROUND.

    Responde rápido de propósito: numa sessão longa a montagem leva minutos, e segurar a
    resposta estouraria o timeout do headset/proxy. O status vai a "processing" e vira
    "complete" (ou "failed") quando a montagem termina. Idempotente: repetir o complete de
    uma sessão pronta só devolve o estado; de uma travada em processing, re-agenda.
    """
    sess = db.get(Session, sid)
    if sess is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")

    frame_count = storage.count_frames(sid)
    sess.frame_count = frame_count
    if frame_count == 0:
        sess.status = "failed"
        sess.error_detail = "nenhum frame recebido"
        db.commit()
        raise HTTPException(status_code=409, detail="nenhum frame recebido — nada para montar")

    if sess.status == "complete" and sess.video_path:
        return {"id": sess.id, "status": sess.status, "frame_count": frame_count, "video_ready": True}

    sess.status = "processing"
    sess.error_detail = None
    db.commit()
    background.add_task(_assemble_and_finalize, sid)
    return {"id": sess.id, "status": "processing", "frame_count": frame_count, "video_ready": False}


def _assemble_and_finalize(sid: str) -> None:
    """Roda fora do ciclo request/response; abre a própria sessão de banco."""
    db = SessionLocal()
    try:
        sess = db.get(Session, sid)
        if sess is None:
            return
        w = sess.frame_width or 1024
        h = sess.frame_height or 1024
        out_path = storage.video_path(sid)
        codec, written = assemble_mp4(
            storage.frames_dir(sid), sess.frames or [], w, h, sess.video_fps or 15.0, out_path)

        if codec is None or written == 0:
            sess.status = "failed"
            sess.error_detail = "falha ao montar o MP4 (codec indisponível ou frames ilegíveis)"
        else:
            sess.video_path = out_path
            sess.video_codec = codec
            sess.status = "complete"
            sess.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:  # nunca deixa a task matar o worker silenciosamente sem registrar
        db.rollback()
        sess = db.get(Session, sid)
        if sess is not None:
            sess.status = "failed"
            sess.error_detail = f"erro na montagem do MP4: {e}"
            db.commit()
    finally:
        db.close()
