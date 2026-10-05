"""Administração de usuários (W19, W20). Tudo exige a permissão "Gerenciar usuários".

Usuários não são excluídos, só desativados. O sistema nunca fica sem um admin ativo, e ninguém
muda o próprio perfil nem se desativa. Convites e redefinições vão por e-mail; se o e-mail não
sair, a resposta traz o link para o admin copiar.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..models import User
from ..schemas.user import LinkResult, UserCreate, UserCreated, UserDetail, UserOut, UserPage, UserUpdate
from ..security import require_permission
from ..services import accounts, audit, tokens

router = APIRouter()
logger = logging.getLogger(__name__)

ManageUsers = require_permission("admin.users")

EMAIL_TAKEN = "já existe um usuário com este e-mail"


def _detail(user: User) -> UserDetail:
    return UserDetail(
        **UserOut.model_validate(user).model_dump(),
        created_by_name=user.created_by.name if user.created_by else None,
        sessions_as_owner=0,
    )


def _get(db: DbSession, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    return user


def _link_result(sent: accounts.SentLink) -> LinkResult:
    return LinkResult(email_sent=sent.email_sent, link=None if sent.email_sent else sent.link, expires_at=sent.expires_at)


@router.get("/users", response_model=UserPage)
def list_users(
    me: User = Depends(ManageUsers),
    q: str = Query("", max_length=120),
    role: str | None = Query(None, pattern="^(admin|researcher)$"),
    status: str | None = Query(None, pattern="^(invited|active|inactive)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=100),
    db: DbSession = Depends(get_db),
):
    filters = []
    if q.strip():
        term = q.strip()
        filters.append(or_(User.name.icontains(term, autoescape=True), User.email.icontains(term, autoescape=True)))
    if role:
        filters.append(User.role == role)
    if status:
        filters.append(User.status == status)

    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    # Você primeiro, os inativos por último, o resto por nome.
    order = (
        case((User.id == me.id, 0), else_=1),
        case((User.status == "inactive", 1), else_=0),
        func.lower(User.name),
    )
    rows = db.scalars(select(User).where(*filters).order_by(*order).limit(page_size).offset((page - 1) * page_size)).all()
    return UserPage(items=[UserOut.model_validate(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("/users", response_model=UserCreated, status_code=201)
def create_user(body: UserCreate, request: Request, me: User = Depends(ManageUsers), db: DbSession = Depends(get_db)):
    if accounts.find_by_email(db, body.email):
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)
    user = User(name=body.name, email=body.email, role=body.role, status="invited", created_by_id=me.id)
    db.add(user)
    db.flush()
    raw, link = tokens.issue_link(db, user, "invite", created_by=me)
    audit.record(db, request, me, "create", "user", user.name, user.id,
                 audit.diff({}, accounts.snapshot(user), accounts.USER_FIELD_LABELS))
    db.commit()
    logger.info("usuário %s (%s) criado por %s", user.email, user.role, me.email)

    sent = accounts.send_link(user, raw, link, invited_by=me.name)
    return UserCreated(user=_detail(user), invite=_link_result(sent))


@router.get("/users/{user_id}", response_model=UserDetail)
def get_user(user_id: str, _: User = Depends(ManageUsers), db: DbSession = Depends(get_db)):
    return _detail(_get(db, user_id))


@router.patch("/users/{user_id}", response_model=UserDetail)
def update_user(user_id: str, body: UserUpdate, request: Request, me: User = Depends(ManageUsers),
                db: DbSession = Depends(get_db)):
    user = _get(db, user_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)

    new_role = changes.get("role", user.role)
    deactivating = changes.get("status") == "inactive" and user.status != "inactive"
    if user.id == me.id and (new_role != user.role or deactivating):
        raise HTTPException(status_code=409, detail="você não pode mudar o próprio perfil nem desativar a própria conta")
    losing_admin = user.role == "admin" and user.status == "active" and (new_role != "admin" or deactivating)
    if losing_admin and accounts.other_active_admins(db, user) == 0:
        raise HTTPException(status_code=409, detail="o sistema precisa de pelo menos um admin ativo")
    if "email" in changes and changes["email"] != user.email:
        other = accounts.find_by_email(db, changes["email"])
        if other is not None and other.id != user.id:
            raise HTTPException(status_code=409, detail=EMAIL_TAKEN)

    before = accounts.snapshot(user)
    for field in ("name", "email", "role"):
        if field in changes:
            setattr(user, field, changes[field])
    if deactivating:
        user.status = "inactive"
        # As sessões abertas não voltam a valer se a pessoa for reativada depois.
        user.session_version += 1
        tokens.revoke_links(db, user)
    elif changes.get("status") == "active" and user.status == "inactive":
        # Quem nunca criou a senha volta para o convite pendente (e precisa de um convite novo).
        user.status = "active" if user.password_hash else "invited"

    diff = audit.diff(before, accounts.snapshot(user), accounts.USER_FIELD_LABELS)
    if diff:
        audit.record(db, request, me, "update", "user", user.name, user.id, diff)
        db.commit()
        logger.info("usuário %s alterado por %s: %s", user.email, me.email, [c["field"] for c in diff])
    return _detail(user)


@router.post("/users/{user_id}/resend-invite", response_model=LinkResult)
def resend_invite(user_id: str, request: Request, me: User = Depends(ManageUsers), db: DbSession = Depends(get_db)):
    user = _get(db, user_id)
    if user.status != "invited":
        raise HTTPException(status_code=409, detail="o convite só pode ser reenviado para quem ainda não criou a senha")
    raw, link = tokens.issue_link(db, user, "invite", created_by=me)
    audit.record(db, request, me, "invite", "user", user.name, user.id, [
        audit.change("invite", "Convite", None, f"Reenviado para {user.email}"),
    ])
    db.commit()
    return _link_result(accounts.send_link(user, raw, link, invited_by=me.name))


@router.post("/users/{user_id}/send-reset", response_model=LinkResult)
def send_reset(user_id: str, request: Request, me: User = Depends(ManageUsers), db: DbSession = Depends(get_db)):
    user = _get(db, user_id)
    if user.status != "active":
        raise HTTPException(status_code=409, detail="só usuários ativos podem receber a redefinição de senha")
    raw, link = tokens.issue_link(db, user, "reset", created_by=me)
    audit.record(db, request, me, "password_reset", "user", user.name, user.id, [
        audit.change("reset_link", "Link de redefinição", None, f"Enviado para {user.email}"),
    ])
    db.commit()
    return _link_result(accounts.send_link(user, raw, link))
