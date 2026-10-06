"""Regras dos estímulos usadas pelas rotas e pelo `app.seed`: rótulos, diff para a auditoria, a
entrada de um arquivo na biblioteca (como rascunho) e a versão para o óculos em segundo plano.

A versão para o óculos é gerada depois de "Salvar na biblioteca", um estímulo por vez, fora do
ciclo do request. Se a API reiniciar no meio, o que ficou pendente é retomado ao subir.
"""
import hashlib
import logging
import os
import re
import shutil
import threading
import unicodedata
from datetime import timedelta
from typing import BinaryIO

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import SessionLocal, engine
from ..models import SessionStimulus, Stimulus, StimulusTag, User, new_id, utcnow
from . import audit, media
from .storage import storage

logger = logging.getLogger(__name__)

KIND_LABELS = {"image": "Imagem", "video": "Vídeo"}
STATUS_LABELS = {"draft": "Rascunho", "active": "Na biblioteca", "archived": "Arquivado"}
FIELD_LABELS = {"name": "Nome", "description": "Descrição", "tags": "Etiquetas", "status": "Situação"}

ACCEPTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp4"}
VIDEO_EXTENSIONS = {".mov", ".qt", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv", ".3gp", ".mpg", ".mpeg", ".ts"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".avif", ".svg"}

MAX_TAG_LENGTH = 40


def format_problem(filename: str, head: bytes) -> str:
    """Por que o arquivo foi recusado, com o formato certo para o tipo que ele parece ter (W10)."""
    ext = os.path.splitext(filename.lower())[1]
    if head[4:8] == b"ftyp" or ext in VIDEO_EXTENSIONS or ext == ".mp4":
        return "formato não aceito. Envie o vídeo em MP4"
    if ext in IMAGE_EXTENSIONS:
        return "formato não aceito. Envie a imagem em JPG ou PNG"
    return "formato não aceito. Envie imagens em JPG ou PNG e vídeos em MP4"


def suggested_name(filename: str) -> str:
    """"cachoeira-na-mata.jpg" -> "Cachoeira na mata" (o Nome que a W10 já traz preenchido)."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    text = " ".join(re.sub(r"[-_.]+", " ", stem).split())[:120]
    return text[:1].upper() + text[1:] if text else "Estímulo"


def normalize_tag(text: str) -> str:
    return " ".join(text.split()).lower()


def sort_key(text: str) -> str:
    """Ordem alfabética sem tropeçar nos acentos ("água" antes de "bola")."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()


def clean_tags(tags: list[str]) -> list[str]:
    """Sem repetidas nem vazias, na ordem em que foram digitadas."""
    result: list[str] = []
    for raw in tags:
        tag = normalize_tag(raw)
        if tag and tag not in result:
            result.append(tag)
    return result


def snapshot(stimulus: Stimulus) -> dict[str, str | None]:
    return {
        "name": stimulus.name,
        "description": stimulus.description,
        "tags": ", ".join(stimulus.tags) or None,
        "status": STATUS_LABELS.get(stimulus.status, stimulus.status),
    }


def batch_label(stimuli: list[Stimulus]) -> str:
    """"6 imagens enviadas à biblioteca", "1 imagem e 2 vídeos enviados à biblioteca" (W22)."""
    images = sum(1 for s in stimuli if s.kind == "image")
    videos = len(stimuli) - images
    parts = []
    if images:
        parts.append(f"{images} {'imagem' if images == 1 else 'imagens'}")
    if videos:
        parts.append(f"{videos} {'vídeo' if videos == 1 else 'vídeos'}")
    if videos:
        verb = "enviado" if len(stimuli) == 1 else "enviados"
    else:
        verb = "enviada" if images == 1 else "enviadas"
    return f"{' e '.join(parts)} {verb} à biblioteca"


def summary(stimulus: Stimulus) -> str:
    """Uma linha do "O que mudou" da criação em lote: tipo, arquivo e etiquetas."""
    parts = [KIND_LABELS[stimulus.kind], stimulus.original_filename]
    if stimulus.tags:
        parts.append(f"etiquetas: {', '.join(stimulus.tags)}")
    return ", ".join(parts)


def audit_saved(db: DbSession, request, actor: User | None, saved: list[Stimulus]) -> None:
    """Um registro só para o que entrou junto na biblioteca, com uma linha por estímulo (W22, W23)."""
    changes = [audit.change(f"stimulus:{s.id}", s.name, None, summary(s)) for s in saved]
    if len(saved) == 1:
        audit.record(db, request, actor, "create", "stimulus", saved[0].name, saved[0].id, changes)
    else:
        audit.record(db, request, actor, "create", "stimulus", batch_label(saved), None, changes)


def usage_count(db: DbSession, stimulus: Stimulus) -> int:
    """Sessões que usam o estímulo, de qualquer pesquisador (decide se ele pode ser excluído)."""
    return db.scalar(
        select(func.count()).select_from(SessionStimulus).where(SessionStimulus.stimulus_id == stimulus.id)
    ) or 0


# ---- Envio ------------------------------------------------------------------------------------

def _copy_hashing(src: BinaryIO, dst_path: str) -> tuple[int, str, bytes]:
    """Copia em blocos calculando tamanho e sha256; devolve também os primeiros bytes."""
    digest = hashlib.sha256()
    size = 0
    head = b""
    with open(dst_path, "wb") as out:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            if not head:
                head = chunk[:32]
            digest.update(chunk)
            size += len(chunk)
            out.write(chunk)
    return size, digest.hexdigest(), head


def create_draft(db: DbSession, user: User | None, fileobj: BinaryIO, filename: str) -> Stimulus:
    """Guarda o arquivo como rascunho: confere o formato pelo conteúdo, lê resolução e duração e gera
    a miniatura. Recusa com `media.MediaError` (e não deixa nada no disco). Sem commit."""
    filename = os.path.basename(filename or "").strip() or "arquivo"
    ext = os.path.splitext(filename.lower())[1]
    stimulus_id = new_id()
    folder = storage.stimulus_dir(stimulus_id)
    os.makedirs(folder, exist_ok=True)
    try:
        tmp = os.path.join(folder, "upload.tmp")
        size, sha256, head = _copy_hashing(fileobj, tmp)
        fmt = media.detect_format(head)
        if ext not in ACCEPTED_EXTENSIONS or fmt is None:
            raise media.MediaError(format_problem(filename, head), 415)
        original = storage.stimulus_original(stimulus_id, fmt)
        os.replace(tmp, original)

        duration = has_audio = None
        if fmt == "mp4":
            info = media.probe_video(original)
            width, height, duration, has_audio = info.width, info.height, info.duration, info.has_audio
            frame = media.video_frame(original, media.thumbnail_time(duration))
        else:
            frame = media.load_image(original, fmt)
            height, width = frame.shape[:2]
        media.write_thumbnail(frame, storage.stimulus_thumbnail(stimulus_id))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise

    stimulus = Stimulus(
        id=stimulus_id, status="draft", kind=media.kind_of(fmt), name=suggested_name(filename),
        original_filename=filename[:255], format=fmt, size_bytes=size, sha256=sha256,
        width=width, height=height, duration_seconds=duration, has_audio=has_audio,
        device_status="pending", created_by_id=user.id if user else None,
    )
    db.add(stimulus)
    return stimulus


def purge_stale_drafts(db: DbSession) -> int:
    """Rascunhos esquecidos (a pessoa fechou a página sem salvar nem cancelar). Com commit.

    Em lote e só o que ainda é rascunho: dois workers (ou dois envios) podem limpar ao mesmo tempo,
    e as pastas que saem do disco são só as das linhas que este apagou.
    """
    limit = utcnow() - timedelta(hours=settings.draft_hours)
    stale = select(Stimulus.id).where(Stimulus.status == "draft", Stimulus.created_at < limit)
    db.execute(delete(StimulusTag).where(StimulusTag.stimulus_id.in_(stale)))
    removed = list(db.scalars(
        delete(Stimulus).where(Stimulus.id.in_(stale)).returning(Stimulus.id),
        execution_options={"synchronize_session": False},
    ))
    db.commit()
    for stimulus_id in removed:
        storage.delete_stimulus(stimulus_id)
    if removed:
        logger.info("%d rascunho(s) de estímulo esquecido(s) apagado(s)", len(removed))
    return len(removed)


# ---- Versão para o óculos ---------------------------------------------------------------------

def process_device_versions(stimulus_ids: list[str]) -> None:
    """Gera a versão para o óculos de cada estímulo, um por vez (roda fora do request)."""
    for stimulus_id in stimulus_ids:
        try:
            _process(stimulus_id)
        except Exception:  # nunca derruba o worker; o estado fica "failed" ou "processing"
            logger.exception("estímulo %s: erro inesperado na versão para o óculos", stimulus_id)


def _process(stimulus_id: str) -> None:
    with SessionLocal() as db:
        stimulus = db.get(Stimulus, stimulus_id)
        if stimulus is None or stimulus.status == "draft" or stimulus.device_status == "ready":
            return
        stimulus.device_status = "processing"
        stimulus.device_error = None
        db.commit()
        kind, fmt = stimulus.kind, stimulus.format

    src = storage.stimulus_original(stimulus_id, fmt)
    out_dir = storage.stimulus_dir(stimulus_id)
    try:
        if kind == "image":
            version = media.image_device_version(src, fmt, out_dir)
        else:
            version = media.video_device_version(src, out_dir)
        error = None
    except (media.MediaError, OSError) as e:
        version, error = None, str(e)

    with SessionLocal() as db:
        stimulus = db.get(Stimulus, stimulus_id)
        if stimulus is None:  # excluído enquanto processava
            storage.delete_stimulus(stimulus_id)
            return
        if version is None:
            stimulus.device_status = "failed"
            stimulus.device_error = error
            logger.error("estímulo %s: versão para o óculos falhou: %s", stimulus_id, error)
        else:
            stimulus.device_status = "ready"
            stimulus.device_format = version.format
            stimulus.device_size_bytes = version.size_bytes
            stimulus.device_sha256 = version.sha256
            stimulus.device_width = version.width
            stimulus.device_height = version.height
            logger.info("estímulo %s: versão para o óculos pronta (%d × %d, %d bytes)",
                        stimulus_id, version.width, version.height, version.size_bytes)
        db.commit()


# Chave do advisory lock da retomada: com mais de um worker, só um retoma as versões pendentes.
_RESUME_LOCK_KEY = 4_827_002


def _resume(stimulus_ids: list[str]) -> None:
    with engine.connect() as conn:
        postgres = conn.dialect.name == "postgresql"
        if postgres and not conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": _RESUME_LOCK_KEY}).scalar():
            return  # outro worker já está retomando
        try:
            logger.info("retomando a versão para o óculos de %d estímulo(s)", len(stimulus_ids))
            process_device_versions(stimulus_ids)
        finally:
            if postgres:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _RESUME_LOCK_KEY})


def resume_pending() -> threading.Thread | None:
    """Ao subir a API: limpa os rascunhos esquecidos e retoma as versões que ficaram pela metade.

    Nunca impede a API de subir: um erro aqui só fica no log.
    """
    try:
        with SessionLocal() as db:
            purge_stale_drafts(db)
            pending = list(db.scalars(
                select(Stimulus.id).where(
                    Stimulus.status != "draft", Stimulus.device_status.in_(("pending", "processing")),
                ).order_by(Stimulus.created_at)
            ))
    except Exception:
        logger.exception("não foi possível conferir os estímulos pendentes ao subir")
        return None
    if not pending:
        return None
    thread = threading.Thread(target=_resume, args=(pending,), name="stimuli-device", daemon=True)
    thread.start()
    return thread
