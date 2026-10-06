"""Modelos SQLAlchemy, um módulo por domínio.

Importar daqui registra todos os modelos em `Base.metadata`, que é com o que o Alembic compara o
banco ao gerar migrações.
"""
from .audit import AuditLog
from .base import Base, JSONType, UtcDateTime, new_id, utcnow
from .device import Device
from .legacy_session import LegacySession
from .patient import Patient
from .session import Session, SessionMarker, SessionShare, SessionStimulus
from .stimulus import Stimulus, StimulusTag
from .user import AuthToken, RolePermission, User

__all__ = [
    "AuditLog", "AuthToken", "Base", "Device", "JSONType", "LegacySession", "Patient", "RolePermission", "Session",
    "SessionMarker", "SessionShare", "SessionStimulus", "Stimulus", "StimulusTag", "User", "UtcDateTime", "new_id",
    "utcnow",
]
