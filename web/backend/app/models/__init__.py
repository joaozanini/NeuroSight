"""Modelos SQLAlchemy, um módulo por domínio.

Importar daqui registra todos os modelos em `Base.metadata`, que é com o que o Alembic compara o
banco ao gerar migrações.
"""
from .audit import AuditLog
from .base import Base, JSONType, UtcDateTime, new_id, utcnow
from .session import Session
from .user import AuthToken, RolePermission, User

__all__ = [
    "AuditLog", "AuthToken", "Base", "JSONType", "RolePermission", "Session", "User", "UtcDateTime",
    "new_id", "utcnow",
]
