"""Pacientes (W06–W08): lista com busca, cadastro e edição com o TCLE em PDF, detalhe e inativação.

Ver exige "Ver pacientes"; cadastrar e editar, "Cadastrar e editar pacientes"; inativar e reativar,
"Inativar pacientes". Cadastro e edição chegam em multipart (campos em JSON no `data` e o PDF em
`consent_file`), para o termo entrar no mesmo registro da auditoria. Na auditoria o paciente é
identificado pelo código.

O PDF só sai pela rota `/patients/{id}/consent`, que exige login e a permissão de ver pacientes.
"""
import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import get_db
from ..models import Patient, Session, SessionStimulus, User
from ..schemas.patient import (
    ConsentFile, NextCode, PatientCounts, PatientDetail, PatientInput, PatientPage, PatientRow, PatientSession,
    StatusChange,
)
from ..security import require_permission
from ..services import audit, patients
from ..services import sessions as session_rules
from ..services.storage import storage

router = APIRouter()
logger = logging.getLogger(__name__)

ViewPatients = require_permission("patients.view")
EditPatients = require_permission("patients.edit")
DeactivatePatients = require_permission("patients.deactivate")

CODE_TAKEN = "já existe um paciente com este código"
PDF_MAGIC = b"%PDF-"


def patient_input(data: str = Form(...)) -> PatientInput:
    """Os campos do formulário, em JSON no campo `data` do multipart, validados como um corpo JSON."""
    try:
        return PatientInput.model_validate_json(data)
    except ValidationError as e:
        errors = e.errors(include_url=False, include_context=False)
        raise RequestValidationError([{**err, "loc": ("body", "data", *err["loc"])} for err in errors])


def _get(db: DbSession, patient_id: str) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="paciente não encontrado")
    return patient


def _sessions(db: DbSession, patient: Patient, user: User | None) -> list[PatientSession]:
    """"Histórico de sessões" (W08): as que a pessoa pode ver, das mais recentes para as mais antigas."""
    counts = (
        select(SessionStimulus.session_id, func.count().label("n")).group_by(SessionStimulus.session_id).subquery()
    )
    rows = db.execute(
        select(Session, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.session_id == Session.id)
        .where(Session.patient_id == patient.id, session_rules.visible_to(db, user))
        .order_by(session_rules.session_date.desc(), Session.created_at.desc())
    ).all()
    return [
        PatientSession(id=s.id, title=s.title, date=s.started_at or s.created_at, owner_name=s.owner.name,
                       stimuli_count=n, status=s.status)
        for s, n in rows
    ]


def _detail(db: DbSession, patient: Patient, user: User | None) -> PatientDetail:
    consent = None
    if patient.consent_file_key:
        consent = ConsentFile(name=patient.consent_file_name or "termo.pdf", size=patient.consent_file_size or 0)
    history = _sessions(db, patient, user)
    return PatientDetail(
        id=patient.id, code=patient.code, name=patient.name, birth_date=patient.birth_date, sex=patient.sex,
        vision_correction=patient.vision_correction, consent_signed=patient.consent_signed,
        consent_date=patient.consent_date, consent_file=consent, notes=patient.notes, status=patient.status,
        created_at=patient.created_at, created_by_name=patient.created_by.name if patient.created_by else None,
        sessions_count=len(history), sessions=history,
    )


def _uploaded(file: UploadFile | None) -> UploadFile | None:
    # Um campo de arquivo vazio (sem nome) conta como "nenhum arquivo".
    return file if file is not None and file.filename else None


def _store_consent(patient_id: str, upload: UploadFile) -> tuple[str, str, int]:
    """Grava o PDF do TCLE e devolve (chave, nome original, tamanho). Recusa o que não é PDF."""
    limit = settings.max_consent_mb * 1024 * 1024
    if upload.size is not None and upload.size > limit:
        raise HTTPException(status_code=413, detail=f"o PDF do termo passa de {settings.max_consent_mb} MB")
    head = upload.file.read(1024)
    if PDF_MAGIC not in head:
        raise HTTPException(status_code=415, detail="o termo precisa ser um arquivo PDF")
    upload.file.seek(0)

    key, size = patients.save_consent_file(patient_id, upload.file)
    if size > limit:
        storage.delete_file(key)
        raise HTTPException(status_code=413, detail=f"o PDF do termo passa de {settings.max_consent_mb} MB")
    name = os.path.basename(upload.filename or "").strip()[:255] or "termo.pdf"
    return key, name, size


def _apply(patient: Patient, body: PatientInput) -> None:
    for field in ("code", "name", "birth_date", "sex", "vision_correction", "consent_signed", "consent_date", "notes"):
        setattr(patient, field, getattr(body, field))


def _commit(db: DbSession, new_key: str | None) -> None:
    """Commit; se falhar, o PDF recém-gravado sai do disco. Código repetido (corrida) vira 409."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete_file(new_key)
        raise HTTPException(status_code=409, detail=CODE_TAKEN)
    except Exception:
        db.rollback()
        storage.delete_file(new_key)
        raise


@router.get("/patients/next-code", response_model=NextCode)
def next_code(_: User = Depends(EditPatients), db: DbSession = Depends(get_db)):
    """Código sugerido no cadastro (W07): o próximo P-NNN livre."""
    return NextCode(code=patients.suggest_code(db))


@router.get("/patients", response_model=PatientPage)
def list_patients(
    q: str = Query("", max_length=120),
    include_inactive: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=100),
    user: User = Depends(ViewPatients),
    db: DbSession = Depends(get_db),
):
    """W06 (e etapa 1 da W13). Contagem e última sessão consideram só as sessões que a pessoa vê."""
    filters = []
    if not include_inactive:
        filters.append(Patient.status == "active")
    if q.strip():
        term = q.strip()
        filters.append(or_(Patient.name.icontains(term, autoescape=True), Patient.code.icontains(term, autoescape=True)))

    total = db.scalar(select(func.count()).select_from(Patient).where(*filters)) or 0
    history = (
        select(Session.patient_id, func.count().label("n"), func.max(session_rules.session_date).label("last"))
        .where(session_rules.visible_to(db, user)).group_by(Session.patient_id).subquery()
    )
    # Inativos por último; antes, o movimento mais recente: a última sessão ou, sem sessão depois
    # dele, o cadastro (quem acabou de ser cadastrado aparece no topo, como na W13).
    activity = case((history.c.last > Patient.created_at, history.c.last), else_=Patient.created_at)
    order = (case((Patient.status == "inactive", 1), else_=0), activity.desc(), Patient.code.desc())
    rows = db.execute(
        select(Patient, history.c.n, history.c.last).outerjoin(history, history.c.patient_id == Patient.id)
        .where(*filters).order_by(*order).limit(page_size).offset((page - 1) * page_size)
    ).all()
    counts = dict(db.execute(select(Patient.status, func.count()).group_by(Patient.status)).all())
    return PatientPage(
        items=[
            PatientRow(id=p.id, code=p.code, name=p.name, birth_date=p.birth_date, status=p.status,
                       sessions_count=n or 0, last_session_at=last)
            for p, n, last in rows
        ],
        total=total, page=page, page_size=page_size,
        counts=PatientCounts(active=counts.get("active", 0), inactive=counts.get("inactive", 0)),
    )


@router.post("/patients", response_model=PatientDetail, status_code=201)
def create_patient(
    request: Request,
    body: PatientInput = Depends(patient_input),
    consent_file: UploadFile | None = File(None),
    me: User = Depends(EditPatients),
    db: DbSession = Depends(get_db),
):
    consent_file = _uploaded(consent_file)
    if consent_file and not body.consent_signed:
        raise HTTPException(status_code=422, detail="marque o termo como assinado para anexar o PDF")
    if patients.find_by_code(db, body.code):
        raise HTTPException(status_code=409, detail=CODE_TAKEN)

    patient = Patient(status="active", created_by_id=me.id)
    _apply(patient, body)
    db.add(patient)
    db.flush()
    new_key = None
    if consent_file:
        new_key, patient.consent_file_name, patient.consent_file_size = _store_consent(patient.id, consent_file)
        patient.consent_file_key = new_key
    audit.record(db, request, me, "create", "patient", patient.code, patient.id,
                 audit.diff({}, patients.snapshot(patient), patients.FIELD_LABELS))
    _commit(db, new_key)
    db.refresh(patient)
    logger.info("paciente %s cadastrado por %s", patient.code, me.email)
    return _detail(db, patient, me)


@router.get("/patients/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: str, user: User = Depends(ViewPatients), db: DbSession = Depends(get_db)):
    return _detail(db, _get(db, patient_id), user)


@router.put("/patients/{patient_id}", response_model=PatientDetail)
def update_patient(
    patient_id: str,
    request: Request,
    body: PatientInput = Depends(patient_input),
    consent_file: UploadFile | None = File(None),
    me: User = Depends(EditPatients),
    db: DbSession = Depends(get_db),
):
    patient = _get(db, patient_id)
    consent_file = _uploaded(consent_file)
    if consent_file and not body.consent_signed:
        raise HTTPException(status_code=422, detail="marque o termo como assinado para anexar o PDF")
    if body.code != patient.code:
        other = patients.find_by_code(db, body.code)
        if other is not None and other.id != patient.id:
            raise HTTPException(status_code=409, detail=CODE_TAKEN)

    before = patients.snapshot(patient)
    old_key = patient.consent_file_key
    new_key = None
    if consent_file:
        new_key, name, size = _store_consent(patient.id, consent_file)
        patient.consent_file_key, patient.consent_file_name, patient.consent_file_size = new_key, name, size
    _apply(patient, body)
    if not body.consent_signed:  # sem assinatura, sem termo
        patient.consent_file_key = patient.consent_file_name = patient.consent_file_size = None

    after = patients.snapshot(patient)
    changes = audit.diff(before, after, patients.FIELD_LABELS)
    if new_key and not any(c["field"] == "consent_file" for c in changes):  # mesmo nome e tamanho
        changes.append(audit.change("consent_file", patients.FIELD_LABELS["consent_file"],
                                    before["consent_file"], after["consent_file"]))
    if changes:
        audit.record(db, request, me, "update", "patient", patient.code, patient.id, changes)
        _commit(db, new_key)
        if old_key and old_key != patient.consent_file_key:
            storage.delete_file(old_key)
        logger.info("paciente %s alterado por %s: %s", patient.code, me.email, [c["field"] for c in changes])
    return _detail(db, patient, me)


@router.put("/patients/{patient_id}/status", response_model=PatientDetail)
def change_status(patient_id: str, body: StatusChange, request: Request, me: User = Depends(DeactivatePatients),
                  db: DbSession = Depends(get_db)):
    """Inativar (sai das listas e não recebe novas sessões) ou reativar."""
    patient = _get(db, patient_id)
    if patient.status != body.status:
        before = patients.snapshot(patient)
        patient.status = body.status
        audit.record(db, request, me, "update", "patient", patient.code, patient.id,
                     audit.diff(before, patients.snapshot(patient), {"status": patients.FIELD_LABELS["status"]}))
        db.commit()
        logger.info("paciente %s %s por %s", patient.code, "inativado" if body.status == "inactive" else "reativado",
                    me.email)
    return _detail(db, patient, me)


@router.get("/patients/{patient_id}/consent")
def get_consent(patient_id: str, _: User = Depends(ViewPatients), db: DbSession = Depends(get_db)):
    patient = _get(db, patient_id)
    path = storage.path_of(patient.consent_file_key) if patient.consent_file_key else None
    if path is None or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="este paciente não tem o termo em PDF")
    return FileResponse(
        path, media_type="application/pdf", filename=patient.consent_file_name or "termo.pdf",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
