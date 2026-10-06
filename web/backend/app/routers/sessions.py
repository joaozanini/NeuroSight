"""Sessões (W12, W13, W16 e W18): lista com filtros, criação pelo assistente, detalhe, edição das
informações e visibilidade.

Ver exige só o login, e cada um vê o que a regra de visibilidade deixa (services/sessions.py);
uma sessão que a pessoa não pode ver responde 404, como se não existisse. Criar exige "Criar e
executar sessões"; editar as informações, a mesma permissão e ser o responsável (ou ver as sessões
de todos); mudar a visibilidade, "Alterar a visibilidade das sessões". Criar, editar e mudar a
visibilidade ficam na auditoria, com a sessão identificada pelo título e pelo código do paciente.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import get_db
from ..models import Patient, Session, SessionShare, SessionStimulus, Stimulus, User
from ..schemas.session import (
    ExposureRow, Person, RecordingFile, SequenceItem, SessionCreate, SessionDetail, SessionFiles, SessionPage,
    SessionPatient, SessionRef, SessionRow, SessionStatus, SessionUpdate, ShareCandidate, VisibilityChange,
)
from ..security import CurrentUser, require_permission
from ..services import audit, permissions
from ..services import sessions as rules

router = APIRouter()
logger = logging.getLogger(__name__)

RunSessions = require_permission("sessions.run")
ChangeVisibility = require_permission("sessions.visibility")

NOT_FOUND = "sessão não encontrada"


class Access:
    """As permissões da pessoa logada que mudam o que ela vê e pode fazer numa sessão."""

    def __init__(self, db: DbSession, user: User):
        granted = permissions.role_permissions(db, user.role)
        self.user = user
        self.all_sessions = "sessions.view_all" in granted
        self.patients = "patients.view" in granted
        self.run = "sessions.run" in granted
        self.visibility = "sessions.visibility" in granted
        self.export = "sessions.export" in granted

    def can_edit(self, session: Session) -> bool:
        return self.run and (session.owner_id == self.user.id or self.all_sessions)


def _get(db: DbSession, session_id: str, access: Access) -> Session:
    session = db.get(Session, session_id)
    if session is None or not rules.can_view(session, access.user, access.all_sessions):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return session


def _thumbnail(stimulus_id: str) -> str:
    return f"{settings.api_prefix}/stimuli/{stimulus_id}/thumbnail"


def _candidate(user: User) -> ShareCandidate:
    return ShareCandidate(id=user.id, name=user.name, role=user.role, role_label=permissions.ROLE_LABELS[user.role])


def _files(analysis: dict) -> SessionFiles:
    recording = analysis.get("recording") or {}
    status = recording.get("status") if recording.get("status") in ("ready", "failed") else "none"
    return SessionFiles(tracking_bytes=analysis.get("tracking_bytes") or 0,
                        recording=RecordingFile(status=status, size_bytes=recording.get("bytes")))


def _detail(session: Session, access: Access) -> SessionDetail:
    patient = session.patient
    duration = None
    if session.started_at and session.ended_at:
        duration = (session.ended_at - session.started_at).total_seconds()
    source = session.duplicated_from
    shared = sorted((share.user for share in session.shares), key=lambda u: u.name.casefold())
    data_status, data_error = rules.data_status(session)
    ready = data_status == "ready"
    return SessionDetail(
        id=session.id, type=session.type, status=session.status, end_reason=session.end_reason, title=session.title,
        objective=session.objective, notes=session.notes, record=session.record, visibility=session.visibility,
        shared_with=[_candidate(u) for u in shared],
        patient=SessionPatient(
            id=patient.id, code=patient.code,
            name=patient.name if access.patients else None,
            birth_date=patient.birth_date if access.patients else None,
            sex=patient.sex if access.patients else None,
        ),
        owner=Person(id=session.owner.id, name=session.owner.name),
        created_at=session.created_at, started_at=session.started_at, ended_at=session.ended_at,
        date=session.started_at or session.created_at, duration_seconds=duration,
        items=[
            SequenceItem(
                position=item.position, stimulus_id=item.stimulus_id, name=item.stimulus.name,
                kind=item.stimulus.kind, archived=item.stimulus.status == "archived",
                duration_seconds=item.duration_seconds, media_duration_seconds=item.stimulus.duration_seconds,
                thumbnail_url=_thumbnail(item.stimulus_id),
            )
            for item in session.items
        ],
        duplicated_from=(
            SessionRef(id=source.id, title=source.title)
            if source and rules.can_view(source, access.user, access.all_sessions) else None
        ),
        data_status=data_status,
        data_error=data_error,
        exposures=[
            ExposureRow(
                seq=e.seq, position=e.position, stimulus_id=e.stimulus_id, name=e.stimulus.name, kind=e.stimulus.kind,
                archived=e.stimulus.status == "archived", thumbnail_url=_thumbnail(e.stimulus_id), on_t=e.on_t,
                screen_seconds=round(e.off_t - e.on_t, 3),
            )
            for e in session.exposures
        ] if ready else [],
        files=_files(session.analysis) if ready else None,
        can_edit=access.can_edit(session),
        can_run=access.run and session.owner_id == access.user.id,
        can_change_visibility=access.visibility,
        can_export=access.export,
    )


@router.get("/sessions", response_model=SessionPage)
def list_sessions(
    user: CurrentUser,
    q: str = Query("", max_length=120),
    status: SessionStatus | None = Query(None),
    owner_id: str | None = Query(None, max_length=32),
    since: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=100),
    db: DbSession = Depends(get_db),
):
    """W12: as próprias e as liberadas para a pessoa, das mais recentes para as mais antigas."""
    access = Access(db, user)
    filters = [rules.visible_clause(user, access.all_sessions)]
    if q.strip():
        term = q.strip()
        found = [Session.title.icontains(term, autoescape=True), Patient.code.icontains(term, autoescape=True)]
        if access.patients:
            found.append(Patient.name.icontains(term, autoescape=True))
        filters.append(or_(*found))
    if status:
        filters.append(Session.status == status)
    if owner_id:
        filters.append(Session.owner_id == owner_id)
    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        filters.append(rules.session_date >= since.astimezone(timezone.utc))

    base = select(Session).join(Patient, Session.patient_id == Patient.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(rules.session_date.desc(), Session.created_at.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    return SessionPage(
        items=[
            SessionRow(
                id=s.id, title=s.title, patient_id=s.patient_id, patient_code=s.patient.code, owner_id=s.owner_id,
                owner_name=s.owner.name, date=s.started_at or s.created_at, status=s.status, visibility=s.visibility,
            )
            for s in rows
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/sessions/owners", response_model=list[Person])
def list_owners(user: CurrentUser, db: DbSession = Depends(get_db)):
    """"Todos os responsáveis" (W12): quem é responsável por alguma sessão que a pessoa vê."""
    owners = db.scalars(
        select(User).where(User.id.in_(select(Session.owner_id).where(rules.visible_to(db, user))))
        .order_by(func.lower(User.name))
    ).all()
    return [Person(id=u.id, name=u.name) for u in owners]


@router.post("/sessions", response_model=SessionDetail, status_code=201)
def create_session(body: SessionCreate, request: Request, me: User = Depends(RunSessions),
                   db: DbSession = Depends(get_db)):
    """"Salvar" do assistente (W13): a sessão nasce Configurada, privada, com o criador de responsável."""
    access = Access(db, me)
    patient = db.get(Patient, body.patient_id)
    if patient is None:
        raise HTTPException(status_code=422, detail="paciente não encontrado")
    if patient.status != "active":
        raise HTTPException(status_code=409, detail="este paciente está inativo e não recebe novas sessões")

    ids = [item.stimulus_id for item in body.stimuli]
    found = {s.id: s for s in db.scalars(select(Stimulus).where(Stimulus.id.in_(ids)))}
    for stimulus_id in ids:
        stimulus = found.get(stimulus_id)
        if stimulus is None or stimulus.status == "draft":
            raise HTTPException(status_code=422, detail="um dos estímulos não está mais na biblioteca")
        if stimulus.status == "archived":
            raise HTTPException(status_code=409, detail=f"o estímulo “{stimulus.name}” foi arquivado e não entra em novas sessões")

    source = None
    if body.duplicated_from_id:
        source = _get(db, body.duplicated_from_id, access)

    session = Session(
        title=body.title, objective=body.objective, notes=body.notes, record=body.record, status="configured",
        visibility="private", patient=patient, owner=me, duplicated_from=source,
    )
    session.items = [
        SessionStimulus(
            position=position, stimulus=found[item.stimulus_id],
            duration_seconds=round(item.duration_seconds, 3)
            if item.duration_seconds is not None and found[item.stimulus_id].kind == "image" else None,
        )
        for position, item in enumerate(body.stimuli, start=1)
    ]
    db.add(session)
    db.flush()
    audit.record(db, request, me, "create", "session", rules.audit_label(session), session.id,
                 audit.diff({}, rules.snapshot(session), rules.FIELD_LABELS))
    db.commit()
    db.refresh(session)
    logger.info("sessão %s criada por %s para %s (%d estímulos)", session.id, me.email, patient.code, len(session.items))
    return _detail(session, access)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    access = Access(db, user)
    return _detail(_get(db, session_id, access), access)


@router.patch("/sessions/{session_id}", response_model=SessionDetail)
def update_session(session_id: str, body: SessionUpdate, request: Request, me: User = Depends(RunSessions),
                   db: DbSession = Depends(get_db)):
    """"Editar informações" (W16). Os dados coletados não mudam; a gravação, só antes de começar."""
    access = Access(db, me)
    session = _get(db, session_id, access)
    if not access.can_edit(session):
        raise HTTPException(status_code=403, detail="só o responsável pode editar as informações desta sessão")
    if body.record is not None and body.record != session.record and session.status != "configured":
        raise HTTPException(status_code=409, detail="a gravação só pode ser mudada antes de a sessão começar")

    before = rules.snapshot(session)
    label_before = rules.audit_label(session)
    for field in ("title", "objective", "record"):
        value = getattr(body, field)
        if value is not None:
            setattr(session, field, value)
    if "notes" in body.model_fields_set:
        session.notes = body.notes
    changes = audit.diff(before, rules.snapshot(session), rules.FIELD_LABELS)
    if changes:
        audit.record(db, request, me, "update", "session", rules.audit_label(session), session.id, changes)
        db.commit()
        logger.info("sessão %s (%s) alterada por %s: %s", session.id, label_before, me.email,
                    [c["field"] for c in changes])
    return _detail(session, access)


@router.get("/sessions/{session_id}/share-candidates", response_model=list[ShareCandidate])
def share_candidates(session_id: str, me: User = Depends(ChangeVisibility), db: DbSession = Depends(get_db)):
    """Pesquisadores que podem ser escolhidos na W18: os usuários ativos, menos o responsável e quem
    já vê todas as sessões ("Ver sessões de outros pesquisadores", como o Admin na matriz padrão)."""
    session = _get(db, session_id, Access(db, me))
    see_all = [role for role, granted in permissions.all_grants(db).items() if "sessions.view_all" in granted]
    users = db.scalars(
        select(User).where(User.status == "active", User.id != session.owner_id, User.role.not_in(see_all))
        .order_by(func.lower(User.name))
    ).all()
    return [_candidate(u) for u in users]


@router.put("/sessions/{session_id}/visibility", response_model=SessionDetail)
def change_visibility(session_id: str, body: VisibilityChange, request: Request,
                      me: User = Depends(ChangeVisibility), db: DbSession = Depends(get_db)):
    access = Access(db, me)
    session = _get(db, session_id, access)
    user_ids = list(dict.fromkeys(body.user_ids)) if body.visibility == "shared" else []
    if body.visibility == "shared":
        if not user_ids:
            raise HTTPException(status_code=422, detail="escolha pelo menos um pesquisador")
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        if len(users) != len(user_ids) or any(u.status != "active" or u.id == session.owner_id for u in users):
            raise HTTPException(status_code=422, detail="um dos pesquisadores escolhidos não pode receber acesso")

    before = rules.visibility_snapshot(session)
    session.visibility = body.visibility
    current = {share.user_id: share for share in session.shares}
    session.shares = [current.get(uid) or SessionShare(user_id=uid) for uid in user_ids]
    db.flush()
    db.expire(session, ["shares"])
    changes = audit.diff(before, rules.visibility_snapshot(session), rules.VISIBILITY_FIELD_LABELS)
    if changes:
        audit.record(db, request, me, "visibility_change", "session", rules.audit_label(session), session.id, changes)
        db.commit()
        logger.info("visibilidade da sessão %s mudada por %s: %s", session.id, me.email, session.visibility)
    else:
        db.rollback()
    return _detail(session, access)
