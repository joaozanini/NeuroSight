"""Execução da sessão (W14, W15): o que o óculos recebe para carregar e as transições Configurada →
Em andamento → Aguardando dados, com o início e o fim na auditoria.

Usado pelas rotas do site (iniciar, interromper) e pelas do óculos (o B, a queda, o JSON que chega
sem o `ended`). O protocolo está em docs/protocolo-oculos.md.
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session as DbSession
from starlette.requests import HTTPConnection

from ..config import settings
from ..models import Device, Session, User, utcnow
from . import audit
from . import sessions as rules
from .live_hub import hub

logger = logging.getLogger(__name__)

END_REASON_LABELS = {
    "button_b": "Botão B no óculos",
    "interrupted": "Interrompida pelo pesquisador",
    "disconnected": "Queda do óculos",
}
START_LABELS = {"status": "Status", "device": "Óculos"}
END_LABELS = {"status": "Status", "end_reason": "Motivo do fim", "duration": "Duração"}


def stimulus_url(session_id: str, stimulus_id: str) -> str:
    return f"{settings.api_prefix}/device/sessions/{session_id}/stimuli/{stimulus_id}"


def device_problem(session: Session) -> str | None:
    """Por que a sessão ainda não pode ir para o óculos: a versão de algum estímulo não está pronta."""
    for item in session.items:
        stimulus = item.stimulus
        if stimulus.device_status == "failed":
            return (f"não foi possível preparar “{stimulus.name}” para o óculos. Envie o arquivo de novo "
                    "pela biblioteca e monte a sessão outra vez")
        if stimulus.device_status != "ready":
            return f"“{stimulus.name}” ainda está sendo preparado para o óculos. Tente de novo em instantes"
    return None


def load_message(session: Session) -> dict:
    """O `load` do protocolo: a sequência com o arquivo de cada estímulo para o óculos baixar."""
    return {
        "type": "load",
        "session": {
            "id": session.id,
            "title": session.title,
            "patientCode": session.patient.code,
            "record": session.record,
            "capture": {
                "width": settings.capture_width, "height": settings.capture_height,
                "fps": settings.capture_fps, "jpegQuality": settings.capture_jpeg_quality,
            },
            "stimuli": [
                {
                    "position": item.position,
                    "stimulusId": item.stimulus_id,
                    "name": item.stimulus.name,
                    "kind": item.stimulus.kind,
                    "format": item.stimulus.device_format,
                    "url": stimulus_url(session.id, item.stimulus_id),
                    "sha256": item.stimulus.device_sha256,
                    "sizeBytes": item.stimulus.device_size_bytes,
                    "width": item.stimulus.device_width,
                    "height": item.stimulus.device_height,
                    "screenSeconds": item.duration_seconds if item.stimulus.kind == "image" else None,
                    "mediaSeconds": item.stimulus.duration_seconds if item.stimulus.kind == "video" else None,
                    "hasAudio": item.stimulus.has_audio if item.stimulus.kind == "video" else None,
                }
                for item in session.items
            ],
        },
    }


def live_session(session: Session):
    """A sessão no hub, criada ou atualizada a partir do banco."""
    device = session.device
    return hub.session(session.id, session.status, len(session.items), session.started_at,
                       session.device_id, device.name if device else None)


def format_duration(seconds: float) -> str:
    """312 -> "5 min 12 s" (Duração no "O que mudou" da auditoria)."""
    total = max(0, round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"


def device_agent(device: Device | None) -> str | None:
    """"NeuroSight/1.0.0 (Quest Pro 01; Quest Pro)": o "De onde" da auditoria no fim pelo B."""
    if device is None:
        return None
    return f"NeuroSight/{device.app_version or '?'} ({device.name}; {device.model or 'Quest'})"


def start(db: DbSession, request: HTTPConnection, actor: User, session: Session, device: Device) -> datetime:
    """Configurada → Em andamento. O commit é de quem chamou."""
    started_at = utcnow()
    session.status = "running"
    session.started_at = started_at
    session.device_id = device.id
    record_start(db, request, actor, session, device.name)
    return started_at


def record_start(db: DbSession, request: HTTPConnection | None, actor: User | None, session: Session,
                 device_name: str | None, at: datetime | None = None) -> None:
    """O início na auditoria (também usado pelo `app.seed`, com `at`)."""
    audit.record(db, request, actor, "session_start", "session", rules.audit_label(session), session.id, [
        audit.change("status", START_LABELS["status"], rules.STATUS_LABELS["configured"], rules.STATUS_LABELS["running"]),
        audit.change("device", START_LABELS["device"], None, device_name),
    ], at=at)


def end(db: DbSession, request: HTTPConnection | None, actor: User | None, session: Session, reason: str,
        agent: str | None = None) -> bool:
    """Em andamento → Aguardando dados, com o motivo. Devolve False se a sessão já tinha acabado.

    O commit é de quem chamou; o hub é avisado logo depois do commit, por `announce_end`.
    """
    if session.status != "running":
        return False
    session.status = "awaiting_data"
    session.end_reason = reason
    session.ended_at = utcnow()
    record_end(db, request, actor, session, agent=agent)
    logger.info("sessão %s encerrada (%s)", session.id, reason)
    return True


def record_end(db: DbSession, request: HTTPConnection | None, actor: User | None, session: Session,
               agent: str | None = None, at: datetime | None = None) -> None:
    """O fim na auditoria, com o motivo e a duração (também usado pelo `app.seed`, com `at`)."""
    duration = (session.ended_at - session.started_at).total_seconds() if session.started_at else None
    audit.record(db, request, actor, "session_end", "session", rules.audit_label(session), session.id, [
        audit.change("status", END_LABELS["status"], rules.STATUS_LABELS["running"], rules.STATUS_LABELS["awaiting_data"]),
        audit.change("end_reason", END_LABELS["end_reason"], None, END_REASON_LABELS[session.end_reason]),
        audit.change("duration", END_LABELS["duration"], None, format_duration(duration) if duration is not None else None),
    ], agent=agent, at=at)


def announce_end(session: Session) -> None:
    hub.set_status(session.id, session.status)
