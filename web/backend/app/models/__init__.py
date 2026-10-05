"""Modelos SQLAlchemy, um módulo por domínio.

Importar daqui registra todos os modelos em `Base.metadata`, que é com o que o Alembic compara o
banco ao gerar migrações.
"""
from .base import Base, JSONType, new_id, utcnow
from .session import Session

__all__ = ["Base", "JSONType", "Session", "new_id", "utcnow"]
