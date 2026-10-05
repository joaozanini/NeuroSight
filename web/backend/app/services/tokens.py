"""Tokens: o JWT da sessão do site (no cookie httpOnly) e os links de uso único.

Sessão: o JWT leva o id do usuário e a `session_version`; a cada request o usuário é recarregado
do banco, então desativar bloqueia na hora e trocar a senha derruba as outras sessões.

Links de convite e de redefinição: o token aleatório vai só no e-mail (ou na tela do admin); o
banco guarda o sha256 dele. Cada link vale uma vez, até a validade, e um link novo do mesmo tipo
invalida o anterior. A senha atual continua valendo até o link de redefinição ser usado.
"""
import functools
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..models import AuthToken, User, utcnow

logger = logging.getLogger(__name__)

SESSION_COOKIE = "neurosight_session"
_JWT_ALGORITHM = "HS256"

LINK_PATHS = {"invite": "/aceitar-convite", "reset": "/redefinir-senha"}


@functools.cache
def secret_key() -> str:
    """A chave configurada, ou uma gerada uma vez e guardada junto da mídia.

    Com vários workers, o primeiro a criar o arquivo vence (O_EXCL) e os outros leem a mesma chave.
    """
    if settings.secret_key:
        if len(settings.secret_key) < 32:
            logger.warning("QUESTPRO_SECRET_KEY tem menos de 32 caracteres; use uma chave mais longa")
        return settings.secret_key
    path = Path(settings.media_root) / ".secret_key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text(encoding="ascii").strip()
    key = secrets.token_urlsafe(48)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(key)
    logger.warning("QUESTPRO_SECRET_KEY não definida: chave da sessão gerada em %s", path)
    return key


# ---- Sessão do site -------------------------------------------------------------------------

def encode_session(user: User, now: datetime | None = None) -> str:
    now = now or utcnow()
    payload = {
        "sub": user.id,
        "sv": user.session_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_hours)).timestamp()),
    }
    return jwt.encode(payload, secret_key(), algorithm=_JWT_ALGORITHM)


def decode_session(token: str) -> dict | None:
    """Payload de um cookie válido (assinatura e validade), ou None."""
    try:
        return jwt.decode(token, secret_key(), algorithms=[_JWT_ALGORITHM], options={"require": ["sub", "exp", "iat"]})
    except jwt.PyJWTError:
        return None


def should_renew(payload: dict, now: datetime | None = None) -> bool:
    """Renova o cookie quando já passou da metade da validade (sessão deslizante)."""
    now = now or utcnow()
    return now.timestamp() > (payload["iat"] + payload["exp"]) / 2


# ---- Links de uso único ---------------------------------------------------------------------

def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def link_url(kind: str, raw: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}{LINK_PATHS[kind]}?token={quote(raw)}"


def link_hours(kind: str) -> int:
    return settings.invite_hours if kind == "invite" else settings.reset_hours


def issue_link(db: DbSession, user: User, kind: str, created_by: User | None = None) -> tuple[str, AuthToken]:
    """Cria o link (sem commit). Devolve o token cru, que não fica guardado em lugar nenhum."""
    revoke_links(db, user, kind)
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    link = AuthToken(
        user_id=user.id, kind=kind, token_hash=_hash(raw), created_at=now,
        expires_at=now + timedelta(hours=link_hours(kind)),
        created_by_id=created_by.id if created_by else None,
    )
    db.add(link)
    return raw, link


def revoke_links(db: DbSession, user: User, kind: str | None = None) -> None:
    """Invalida os links ainda não usados do usuário (de um tipo ou de todos)."""
    stmt = update(AuthToken).where(AuthToken.user_id == user.id, AuthToken.used_at.is_(None))
    if kind:
        stmt = stmt.where(AuthToken.kind == kind)
    db.execute(stmt.values(used_at=utcnow()))


def find_link(db: DbSession, raw: str, kind: str) -> AuthToken | None:
    """O link válido (do tipo pedido, não usado e no prazo) para este token, ou None."""
    if not raw:
        return None
    link = db.scalar(select(AuthToken).where(AuthToken.token_hash == _hash(raw), AuthToken.kind == kind))
    if link is None or link.used_at is not None or link.expires_at <= datetime.now(timezone.utc):
        return None
    return link


def last_link_at(db: DbSession, user: User, kind: str) -> datetime | None:
    return db.scalar(
        select(AuthToken.created_at).where(AuthToken.user_id == user.id, AuthToken.kind == kind)
        .order_by(AuthToken.created_at.desc()).limit(1)
    )
