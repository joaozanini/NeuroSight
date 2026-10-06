"""Dados coletados de uma sessão (W16, W17): a análise, a gravação para assistir e os downloads.

Ver a análise e a gravação exige só poder ver a sessão (a regra da W12; sem acesso, 404). Baixar o
JSON, o MP4 e o CSV por estímulo exige "Exportar os dados das sessões" e fica na auditoria como
"Exportação", com o arquivo no "O que mudou". As exportações identificam o paciente só pelo código.
"""
import csv
import io
import logging
import os
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import undefer

from ..config import settings
from ..db import get_db
from ..models import Session, SessionExposure, SessionMarker, User
from ..schemas.analysis import (
    AnalysisExposure, AnalysisFace, AnalysisMarker, AnalysisRecording, FaceSeries, SessionAnalysis,
)
from ..security import CurrentUser, require_permission
from ..services import analysis as metrics
from ..services import audit
from ..services import sessions as rules
from ..services.storage import storage
from ..utils import csv_cell, csv_number
from .sessions import Access, _get

router = APIRouter()
logger = logging.getLogger(__name__)

ExportData = require_permission("sessions.export")

NOT_READY = "os dados desta sessão ainda não foram processados"
KIND_LABELS = {"image": "Imagem", "video": "Vídeo"}
# O que foi baixado, como aparece no "O que mudou" da W23.
FILE_LABELS = {
    "tracking": "Dados de rastreamento (JSON)",
    "recording": "Gravação da sessão (MP4)",
    "csv": "Métricas por estímulo (CSV)",
}
FILE_SUFFIXES = {"tracking": "rastreamento.json", "recording": "gravacao.mp4", "csv": "estimulos.csv"}
CSV_HEADER = [
    "Sessão", "Paciente", "Data", "Ordem", "Nº", "Estímulo", "Tipo", "Início (s)", "Fim (s)", "Tempo de tela (s)",
    "Amostras", "Amostras válidas", "Amostras válidas (%)", "Fixações", "Duração média da fixação (ms)",
    "Tempo até a 1ª fixação (ms)",
]


def _ready(db: DbSession, session_id: str, user: User) -> tuple[Session, Access]:
    access = Access(db, user)
    session = _get(db, session_id, access)
    if rules.data_status(session)[0] != "ready":
        raise HTTPException(status_code=409, detail=NOT_READY)
    return session, access


def _exposures(db: DbSession, session_id: str, *heavy) -> list[SessionExposure]:
    return list(db.scalars(
        select(SessionExposure).where(SessionExposure.session_id == session_id).order_by(SessionExposure.seq)
        .options(*(undefer(column) for column in heavy))
    ))


def _stimulus_url(stimulus_id: str, what: str) -> str:
    return f"{settings.api_prefix}/stimuli/{stimulus_id}/{what}"


@router.get("/sessions/{session_id}/analysis", response_model=SessionAnalysis)
def get_analysis(session_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    """W17: as exibições com as métricas, as marcações, a gravação e as expressões."""
    session, access = _ready(db, session_id, user)
    data = session.analysis
    exposures = _exposures(db, session.id, SessionExposure.fixations, SessionExposure.heat)
    markers = db.scalars(select(SessionMarker).where(SessionMarker.session_id == session.id)
                         .order_by(SessionMarker.t, SessionMarker.id)).all()
    recording = data.get("recording") or {}
    face = data.get("face")
    labels = dict(metrics.DEFAULT_EXPRESSIONS)
    # Na ordem da legenda da W17: o JSONB do PostgreSQL não guarda a ordem das chaves.
    order = list(labels)
    series = sorted((face or {}).get("series", {}).items(),
                    key=lambda item: order.index(item[0]) if item[0] in order else len(order))
    return SessionAnalysis(
        id=session.id, title=session.title, patient_code=session.patient.code, started_at=session.started_at,
        status=session.status, duration=data["duration"],
        exposures=[
            AnalysisExposure(
                seq=e.seq, position=e.position, stimulus_id=e.stimulus_id, name=e.stimulus.name, kind=e.stimulus.kind,
                thumbnail_url=_stimulus_url(e.stimulus_id, "thumbnail"), file_url=_stimulus_url(e.stimulus_id, "file"),
                width=e.stimulus.width, height=e.stimulus.height, on_t=e.on_t, off_t=e.off_t, samples=e.samples,
                valid_samples=e.valid_samples, fixation_count=e.fixation_count, mean_fixation_ms=e.mean_fixation_ms,
                first_fixation_ms=e.first_fixation_ms, fixations=e.fixations, heat=e.heat,
            )
            for e in exposures
        ],
        markers=[AnalysisMarker(t=m.t, text=m.text) for m in markers],
        recording_status=recording.get("status") if recording.get("status") in ("ready", "failed") else "none",
        recording=AnalysisRecording(
            url=f"{settings.api_prefix}/sessions/{session.id}/recording", fps=recording["fps"],
            width=recording["width"], height=recording["height"], frame_t=recording["frame_t"],
            frame_gaze=recording["frame_gaze"],
        ) if recording.get("status") == "ready" else None,
        face=AnalysisFace(hz=face["hz"], series=[
            FaceSeries(key=key, label=labels.get(key, key), values=values) for key, values in series
        ]) if face else None,
        can_export=access.export,
    )


@router.get("/sessions/{session_id}/recording")
def get_recording(session_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    """A gravação para assistir na W17 (o <video> busca por Range). Baixar é pela rota de downloads."""
    session, _ = _ready(db, session_id, user)
    path = storage.session_recording(session.id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="a gravação desta sessão não está disponível")
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "private, max-age=3600"})


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _first_request(request: Request) -> bool:
    """Um download retomado (Range a partir do meio) não é outra exportação."""
    ranges = request.headers.get("range")
    return not ranges or ranges.replace(" ", "").startswith("bytes=0-")


@router.get("/sessions/{session_id}/downloads/{kind}")
def download(session_id: str, kind: Literal["tracking", "recording", "csv"], request: Request,
             tz: str = Query("America/Sao_Paulo", max_length=64), me: User = Depends(ExportData),
             db: DbSession = Depends(get_db)):
    """"Baixar" da W16 e da W17: o JSON como o óculos enviou, o MP4 e o CSV por estímulo."""
    session, _ = _ready(db, session_id, me)
    zone = _zone(tz)
    started = (session.started_at or session.created_at).astimezone(zone)
    filename = f"{session.patient.code}_{started:%Y-%m-%d_%H%M}_{FILE_SUFFIXES[kind]}"
    path = None
    if kind == "tracking":
        path = storage.session_tracking(session.id)
    elif kind == "recording":
        path = storage.session_recording(session.id)
    if path is not None and not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="este arquivo não está disponível")

    if _first_request(request):
        audit.record(db, request, me, "export", "session", rules.audit_label(session), session.id,
                     [audit.change("file", "Arquivo", None, FILE_LABELS[kind])])
        db.commit()
        logger.info("sessão %s: %s baixado por %s", session.id, FILE_LABELS[kind], me.email)

    if kind == "csv":
        content = _csv(session, _exposures(db, session.id, SessionExposure.face_means), started)
        return Response(content=content.encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    media_type = "application/json" if kind == "tracking" else "video/mp4"
    return FileResponse(path, media_type=media_type, filename=filename)


def _csv(session: Session, exposures: list[SessionExposure], started: datetime) -> str:
    """Uma linha por exibição de estímulo, com as métricas da W17 e a média de cada expressão."""
    names: list[str] = (session.analysis or {}).get("face_expressions") or []
    defaults = [(label, [i for i, name in enumerate(names) if name in (f"{key}_L", f"{key}_R", key)])
                for key, label in metrics.DEFAULT_EXPRESSIONS]
    defaults = [(label, columns) for label, columns in defaults if columns]

    buffer = io.StringIO()
    # Ponto e vírgula, vírgula decimal e BOM: é o que o Excel em português abre direto.
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(CSV_HEADER + [f"{label} (média)" for label, _ in defaults] + [f"{n} (média)" for n in names])
    for e in exposures:
        means = e.face_means or []
        valid = 100 * e.valid_samples / e.samples if e.samples else None
        row = [
            csv_cell(session.title), csv_cell(session.patient.code), f"{started:%d/%m/%Y %H:%M}", e.seq, e.position,
            csv_cell(e.stimulus.name), KIND_LABELS[e.stimulus.kind], csv_number(e.on_t), csv_number(e.off_t),
            csv_number(e.off_t - e.on_t), e.samples, e.valid_samples, csv_number(valid, 1), e.fixation_count,
            csv_number(e.mean_fixation_ms, 1), csv_number(e.first_fixation_ms, 1),
        ]
        row += [csv_number(sum(means[i] for i in columns) / len(columns), 4) if means else ""
                for _, columns in defaults]
        row += [csv_number(value, 4) for value in means] if means else [""] * len(names)
        writer.writerow(row)
    return "﻿" + buffer.getvalue()
