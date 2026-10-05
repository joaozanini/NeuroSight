"""Contratos JSON da auditoria (W22, W23)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditChange(BaseModel):
    field: str
    label: str
    before: str | None
    after: str | None


class AuditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_id: str | None
    user_name: str | None
    user_role: str | None
    action: str
    entity_type: str
    entity_id: str | None
    entity_label: str
    ip: str | None


class AuditDetail(AuditItem):
    user_agent: str | None
    changes: list[AuditChange]


class AuditPage(BaseModel):
    items: list[AuditItem]
    total: int
    page: int
    page_size: int


class Option(BaseModel):
    value: str
    label: str


class AuditFilters(BaseModel):
    """Opções dos filtros da W22 e os rótulos das ações, tipos de item e perfis."""

    actions: list[Option]
    entity_types: list[Option]
    roles: list[Option]
    users: list[Option]
