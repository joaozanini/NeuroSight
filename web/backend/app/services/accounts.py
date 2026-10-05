"""Regras das contas usadas pelas rotas e pelo `app.seed`: rótulos, diff para a auditoria e o
envio dos links de convite e de redefinição.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..models import AuthToken, User
from . import mailer, tokens
from .permissions import ROLE_LABELS

STATUS_LABELS = {"invited": "Convite pendente", "active": "Ativo", "inactive": "Inativo"}
USER_FIELD_LABELS = {"name": "Nome", "email": "E-mail", "role": "Perfil", "status": "Status"}


def snapshot(user: User) -> dict[str, str]:
    """Valores legíveis dos campos editáveis, para o diff da auditoria."""
    return {
        "name": user.name,
        "email": user.email,
        "role": ROLE_LABELS.get(user.role, user.role),
        "status": STATUS_LABELS.get(user.status, user.status),
    }


def find_by_email(db: DbSession, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def other_active_admins(db: DbSession, user: User) -> int:
    return db.scalar(
        select(func.count()).select_from(User)
        .where(User.role == "admin", User.status == "active", User.id != user.id)
    ) or 0


@dataclass
class SentLink:
    email_sent: bool
    link: str
    expires_at: datetime


def send_link(user: User, raw_token: str, token: AuthToken, invited_by: str | None = None) -> SentLink:
    """Manda o e-mail do link já salvo no banco (chame depois do commit)."""
    link = tokens.link_url(token.kind, raw_token)
    if token.kind == "invite":
        sent = mailer.send_invite(user.name, user.email, link, invited_by)
    else:
        sent = mailer.send_reset(user.name, user.email, link)
    return SentLink(email_sent=sent, link=link, expires_at=token.expires_at)
