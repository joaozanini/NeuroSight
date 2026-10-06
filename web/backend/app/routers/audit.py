"""Auditoria (W22, W23): lista com filtros, detalhe e exportação em CSV. Só leitura.

Exige a permissão "Consultar a auditoria". O CSV sai em streaming, em lotes, para não montar o
arquivo inteiro na memória; a própria exportação fica registrada.
"""
import csv
import io
from datetime import datetime, timezone
from typing import Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from ..db import SessionLocal, get_db
from ..models import AuditLog, User
from ..schemas.audit import AuditDetail, AuditFilters, AuditItem, AuditPage, Option
from ..security import require_permission
from ..services import audit
from ..services.permissions import ROLE_LABELS
from ..utils import csv_cell

router = APIRouter()

ViewAudit = require_permission("admin.audit")

CSV_BATCH = 500
CSV_HEADER = ["Data e hora", "Usuário", "Perfil", "Ação", "Tipo de item", "Item afetado", "IP", "Navegador",
              "O que mudou"]


class AuditQuery:
    """Filtros da W22, comuns à lista e ao CSV. O período chega como instantes (o navegador sabe o
    fuso de quem está olhando; "Hoje" depende dele)."""

    def __init__(
        self,
        since: datetime | None = Query(None),
        until: datetime | None = Query(None),
        user_id: str | None = Query(None, max_length=32),
        action: str | None = Query(None, max_length=40),
        entity_type: str | None = Query(None, max_length=40),
    ):
        self.since, self.until = _aware(since), _aware(until)
        self.user_id, self.action, self.entity_type = user_id, action, entity_type

    def apply(self, stmt: Select) -> Select:
        if self.since:
            stmt = stmt.where(AuditLog.created_at >= self.since)
        if self.until:
            stmt = stmt.where(AuditLog.created_at < self.until)
        if self.user_id:
            stmt = stmt.where(AuditLog.user_id == self.user_id)
        if self.action:
            stmt = stmt.where(AuditLog.action == self.action)
        if self.entity_type:
            stmt = stmt.where(AuditLog.entity_type == self.entity_type)
        return stmt


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _options(labels: dict[str, str]) -> list[Option]:
    return [Option(value=k, label=v) for k, v in labels.items()]


@router.get("/audit/filters", response_model=AuditFilters)
def audit_filters(_: User = Depends(ViewAudit), db: DbSession = Depends(get_db)):
    users = db.execute(select(User.id, User.name).order_by(func.lower(User.name))).all()
    return AuditFilters(
        actions=_options(audit.ACTION_LABELS),
        entity_types=_options(audit.ENTITY_LABELS),
        roles=_options(ROLE_LABELS),
        users=[Option(value=uid, label=name) for uid, name in users],
    )


@router.get("/audit", response_model=AuditPage)
def list_audit(
    filters: AuditQuery = Depends(),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    _: User = Depends(ViewAudit),
    db: DbSession = Depends(get_db),
):
    total = db.scalar(filters.apply(select(func.count()).select_from(AuditLog))) or 0
    rows = db.scalars(
        filters.apply(select(AuditLog))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    return AuditPage(items=[AuditItem.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/audit/export.csv")
def export_audit(
    request: Request,
    filters: AuditQuery = Depends(),
    tz: str = Query("America/Sao_Paulo", max_length=64),
    me: User = Depends(ViewAudit),
    db: DbSession = Depends(get_db),
):
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    audit.record(db, request, me, "export", "system", "Registros da auditoria (CSV)")
    db.commit()

    filename = f"auditoria-{datetime.now(zone):%Y-%m-%d}.csv"
    return StreamingResponse(
        _csv_rows(filters, zone),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_rows(filters: AuditQuery, zone: ZoneInfo) -> Iterator[str]:
    """Linhas do CSV em lotes. Abre a própria sessão do banco: o gerador roda depois da rota."""
    buffer = io.StringIO()
    # Ponto e vírgula e BOM: é o que o Excel em português abre direto, com os acentos certos.
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

    def flush() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return text

    writer.writerow(CSV_HEADER)
    yield "﻿" + flush()
    stmt = filters.apply(select(AuditLog)).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    with SessionLocal() as db:
        for i, entry in enumerate(db.scalars(stmt.execution_options(yield_per=CSV_BATCH)), 1):
            writer.writerow([csv_cell(v) for v in _csv_values(entry, zone)])
            if i % CSV_BATCH == 0:
                yield flush()
    yield flush()


def _csv_values(entry: AuditLog, zone: ZoneInfo) -> list[str]:
    changes = " | ".join(
        f"{c.get('label')}: {c.get('before') or '—'} → {c.get('after') or '—'}" for c in entry.changes or []
    )
    return [
        entry.created_at.astimezone(zone).strftime("%d/%m/%Y %H:%M:%S"),
        entry.user_name or "",
        ROLE_LABELS.get(entry.user_role or "", entry.user_role or ""),
        audit.ACTION_LABELS.get(entry.action, entry.action),
        audit.ENTITY_LABELS.get(entry.entity_type, entry.entity_type),
        entry.entity_label,
        entry.ip or "",
        entry.user_agent or "",
        changes,
    ]


@router.get("/audit/{entry_id}", response_model=AuditDetail)
def get_audit_entry(entry_id: int, _: User = Depends(ViewAudit), db: DbSession = Depends(get_db)):
    entry = db.get(AuditLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="registro não encontrado")
    return AuditDetail.model_validate(entry)
