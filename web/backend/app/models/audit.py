"""Registro de auditoria: quem fez o quê, em qual item, de onde e o que mudou.

Só recebe inserções. No banco, uma trigger recusa UPDATE e DELETE (migração 0002). Nome e perfil
de quem agiu são copiados para o registro, para ele continuar fiel mesmo se o usuário mudar depois.
"""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BigIntPK, JSONType, UtcDateTime, utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    created_at = mapped_column(UtcDateTime, default=utcnow, index=True, nullable=False)

    # Quem: vazio nas ações sem usuário conhecido.
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # O quê: códigos em inglês; os rótulos ficam em services/audit.py.
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_label: Mapped[str] = mapped_column(String(255), nullable=False)

    # De onde.
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # O que mudou: [{"field", "label", "before", "after"}], com os valores já em texto legível.
    changes = mapped_column(JSONType, default=list, nullable=False)
