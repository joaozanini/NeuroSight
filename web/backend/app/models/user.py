"""Contas do site: usuários, links de uso único (convite e redefinição) e a matriz de permissões.

Usuários não são excluídos, só desativados: a auditoria e as sessões continuam apontando para eles.
O e-mail é guardado em minúsculas, e é por ele que a pessoa entra.
"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UtcDateTime, new_id, utcnow

ROLES = ("admin", "researcher")
USER_STATUSES = ("invited", "active", "inactive")
TOKEN_KINDS = ("invite", "reset")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin | researcher
    # invited: ainda não criou a senha pelo convite; active; inactive: não entra no sistema.
    status: Mapped[str] = mapped_column(String(20), default="invited", index=True, nullable=False)
    # Hash argon2; vazio até a pessoa aceitar o convite.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Vai no cookie de sessão; mudar a senha incrementa e derruba as outras sessões abertas.
    session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    last_login_at = mapped_column(UtcDateTime, nullable=True)
    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    updated_at = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_by: Mapped["User | None"] = relationship(remote_side=[id], lazy="joined", join_depth=1)


class AuthToken(Base):
    """Link de convite ou de redefinição de senha. Só o hash (sha256) do token fica no banco."""

    __tablename__ = "auth_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # invite | reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at = mapped_column(UtcDateTime, default=utcnow, nullable=False)
    expires_at = mapped_column(UtcDateTime, nullable=False)
    # Preenchido quando o link é usado ou substituído por um novo; daí em diante não vale mais.
    used_at = mapped_column(UtcDateTime, nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class RolePermission(Base):
    """Uma linha por permissão concedida a um perfil (matriz da W21). Sem linha = sem permissão."""

    __tablename__ = "role_permissions"

    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    permission: Mapped[str] = mapped_column(String(50), primary_key=True)
