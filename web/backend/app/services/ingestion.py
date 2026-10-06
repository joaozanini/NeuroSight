"""Ingestão dos dados de uma sessão depois do envio do óculos: monta o MP4 da gravação, analisa o
JSON v2 (services/analysis.py), guarda o resultado e fecha o ciclo do status, de Aguardando dados
para Concluída (fim pelo botão B) ou Interrompida (pelo pesquisador ou por queda).

Roda fora do request, numa fila com uma thread só, porque pesa na CPU: o `complete` do óculos põe a
sessão na fila e, ao subir, a API retoma as que ficaram pela metade (inclusive as que falharam, para
tentar de novo depois de uma correção). Se o processamento falhar, a sessão continua Aguardando
dados, com o erro em `analysis`, e a W16 mostra o problema. Com mais de um worker (o Docker atual),
duas retomadas podem calcular a mesma sessão; o `FOR UPDATE` no fim deixa só uma gravar.
"""
import json
import logging
import os
import queue
import threading

from sqlalchemy import delete, select

from ..config import settings
from ..db import SessionLocal
from ..models import Session, SessionExposure, utcnow
from . import analysis, tracking, video
from .live_hub import hub
from .storage import storage

logger = logging.getLogger(__name__)

# O status depois do processamento, pelo motivo do fim.
FINAL_STATUS = {"button_b": "completed", "interrupted": "interrupted", "disconnected": "interrupted"}

_queue: "queue.Queue[str]" = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


def final_status(end_reason: str | None) -> str:
    return FINAL_STATUS.get(end_reason or "", "interrupted")


def params() -> analysis.Params:
    return analysis.Params(dispersion_deg=settings.fixation_dispersion_deg,
                           min_fixation_s=settings.fixation_min_ms / 1000)


# ---- Fila ---------------------------------------------------------------------------------------

def schedule(session_id: str) -> None:
    """Põe a sessão na fila de processamento (vale de qualquer thread)."""
    global _worker
    _queue.put(session_id)
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="sessions-ingestion", daemon=True)
            _worker.start()


def drain() -> None:
    """Espera a fila esvaziar (testes e seed)."""
    _queue.join()


def _run() -> None:
    while True:
        session_id = _queue.get()
        try:
            process(session_id)
        except Exception:  # nunca derruba a fila
            logger.exception("sessão %s: erro inesperado no processamento dos dados", session_id)
        finally:
            _queue.task_done()


def resume_pending() -> None:
    """Ao subir a API: põe na fila as sessões com os dados recebidos e ainda não processados."""
    try:
        with SessionLocal() as db:
            pending = list(db.scalars(
                select(Session.id).where(Session.status == "awaiting_data", Session.data_received_at.is_not(None))
                .order_by(Session.data_received_at)
            ))
    except Exception:
        logger.exception("não foi possível conferir as sessões com dados pendentes ao subir")
        return
    if pending:
        logger.info("retomando o processamento dos dados de %d sessão(ões)", len(pending))
    for session_id in pending:
        schedule(session_id)


# ---- Processamento --------------------------------------------------------------------------------

def process(session_id: str) -> bool:
    """Processa os dados recebidos de uma sessão. Devolve True se ela passou para o status final."""
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        if session is None or session.status != "awaiting_data" or session.data_received_at is None:
            return False
        received_at = session.data_received_at

    path = storage.session_tracking(session_id)
    try:
        with open(path, "rb") as f:
            doc = json.load(f)
        tracking.validate(doc, session_id)
        recording, frames = _recording(session_id, doc)
        result = analysis.analyze(doc, params(), frames)
    except Exception as e:  # o arquivo some, o JSON quebra ou um erro no cálculo: fica para a próxima
        logger.exception("sessão %s: não foi possível processar os dados", session_id)
        _failed(session_id, received_at, _problem(e))
        return False

    summary = {
        "version": 1,
        "processed_at": utcnow().isoformat(),
        "params": params().as_dict(),
        "duration": result.duration,
        "gaze_hz": result.gaze_hz,
        "samples": result.samples,
        "valid_samples": result.valid_samples,
        "tracking_bytes": os.path.getsize(path),
        "recording": {**recording, "frame_t": [round(float(f["t"]), 4) for f in frames],
                      "frame_gaze": result.frame_gaze} if recording["status"] == "ready" else recording,
        "face": {"hz": analysis.FACE_HZ, "series": result.face_series} if result.face_series is not None else None,
        "face_expressions": result.face_expressions,
    }
    with SessionLocal() as db:
        # Trava só a linha da sessão: no PostgreSQL, o FOR UPDATE não vale com os joins automáticos do
        # paciente e do responsável (lado opcional de um outer join).
        db.execute(select(Session.id).where(Session.id == session_id).with_for_update())
        session = db.get(Session, session_id)
        if session is None or session.status != "awaiting_data" or session.data_received_at != received_at:
            return False  # outra execução já fechou a sessão, ou chegaram dados novos (vão para a fila)
        # Apaga antes de inserir: trocando a lista, o SQLAlchemy inseriria as novas antes de apagar as
        # antigas e esbarraria no UNIQUE (session_id, seq).
        db.execute(delete(SessionExposure).where(SessionExposure.session_id == session_id))
        db.add_all([
            SessionExposure(
                session_id=session_id, seq=e.seq, position=e.position, stimulus_id=e.stimulus_id,
                on_t=round(e.on, 4), off_t=round(e.off, 4), samples=e.samples, valid_samples=e.valid_samples, fixation_count=e.fixation_count,
                mean_fixation_ms=e.mean_fixation_ms, first_fixation_ms=e.first_fixation_ms,
                fixations=[[round(f.start, 4), round(f.duration, 4), round(f.u, 4), round(f.v, 4)]
                           for f in e.fixations],
                heat=e.heat, face_means=e.face_means,
            )
            for e in result.exposures
        ])
        session.analysis = summary
        session.status = final_status(session.end_reason)
        db.commit()
        status = session.status
    hub.set_status(session_id, status)
    logger.info("sessão %s processada: %d exibições, gravação %s, status %s", session_id, len(result.exposures),
                recording["status"], status)
    return True


def _recording(session_id: str, doc: dict) -> tuple[dict, list[dict]]:
    """Monta o MP4 dos frames; devolve o resumo da gravação e os frames que entraram no vídeo."""
    capture, frames = doc["meta"].get("capture"), doc["frames"]
    if not capture or not frames:
        return {"status": "none"}, []
    final = storage.session_recording(session_id)
    # Nome próprio por thread: duas execuções da mesma sessão não escrevem no mesmo arquivo.
    partial = f"{final}.{os.getpid()}-{threading.get_ident()}.mp4"
    try:
        codec, written = video.assemble_mp4(storage.session_frames_dir(session_id), frames, capture["width"],
                                            capture["height"], capture["fps"], partial)
        if codec is None:
            return {"status": "failed", "error": "nenhum quadro da gravação pôde ser lido"}, []
        os.replace(partial, final)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    return {
        "status": "ready", "codec": codec, "fps": float(capture["fps"]),
        "width": int(capture["width"]) // 2 * 2, "height": int(capture["height"]) // 2 * 2,
        "bytes": os.path.getsize(final),
    }, written


def _problem(error: Exception) -> str:
    if isinstance(error, tracking.TrackingError):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "o JSON da sessão não está no servidor"
    if isinstance(error, ValueError):
        return "o JSON da sessão não pôde ser lido"
    return "erro inesperado no processamento"


def _failed(session_id: str, received_at, problem: str) -> None:
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        if session is not None and session.status == "awaiting_data" and session.data_received_at == received_at:
            session.analysis = {"error": problem, "failed_at": utcnow().isoformat()}
            db.commit()
