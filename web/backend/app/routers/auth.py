"""Acesso ao site (W01–W03): login, logout, esqueci minha senha e os links de uso único.

O login devolve o cookie httpOnly com o JWT. Respostas que poderiam revelar se um e-mail está
cadastrado (esqueci minha senha) são sempre iguais. Definir a senha por um link (convite ou
redefinição) já deixa a pessoa logada.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..models import User, utcnow
from ..schemas.auth import ForgotIn, LinkInfo, LoginIn, Me, SetPasswordIn
from ..security import clear_session_cookie, set_session_cookie
from ..services import accounts, audit, mailer, passwords, permissions, tokens
from ..services.ratelimit import login_limiter

router = APIRouter()
logger = logging.getLogger(__name__)

INVALID_LINK = "este link é inválido ou expirou"
# Status exigido do dono do link: o convite só serve a quem ainda não criou a senha.
LINK_USER_STATUS = {"invite": "invited", "reset": "active"}
# Intervalo mínimo entre dois links de "esqueci minha senha" para a mesma conta.
FORGOT_COOLDOWN_SECONDS = 60


def me_payload(db: DbSession, user: User) -> Me:
    return Me(
        id=user.id, name=user.name, email=user.email, role=user.role,
        role_label=permissions.ROLE_LABELS.get(user.role, user.role),
        permissions=sorted(permissions.role_permissions(db, user.role)),
    )


def start_session(db: DbSession, request: Request, response: Response, user: User) -> None:
    """Registra o login (sem commit) e põe o cookie na resposta."""
    user.last_login_at = utcnow()
    audit.record(db, request, user, "login", "system", "Acesso ao sistema")
    set_session_cookie(response, user)


@router.post("/auth/login", response_model=Me)
def login(body: LoginIn, request: Request, response: Response, db: DbSession = Depends(get_db)):
    key = f"{audit.client_ip(request)}|{body.email}"
    if login_limiter.blocked(key):
        raise HTTPException(status_code=429, detail="muitas tentativas seguidas. Espere alguns minutos e tente de novo")

    user = accounts.find_by_email(db, body.email)
    if not passwords.verify_password(user.password_hash if user else None, body.password):
        login_limiter.fail(key)
        logger.info("login recusado para %s", body.email)
        raise HTTPException(status_code=401, detail="e-mail ou senha incorretos")
    login_limiter.reset(key)
    if user.status != "active":
        raise HTTPException(status_code=403, detail="este acesso está desativado. Fale com o administrador do sistema")

    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(body.password)
    start_session(db, request, response, user)
    db.commit()
    return me_payload(db, user)


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@router.post("/auth/forgot", status_code=204)
def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks, db: DbSession = Depends(get_db)):
    """Sempre 204: a resposta não diz se o e-mail existe. O envio roda depois da resposta."""
    user = accounts.find_by_email(db, body.email)
    if user is None or user.status != "active":
        return
    last = tokens.last_link_at(db, user, "reset")
    if last is not None and (utcnow() - last).total_seconds() < FORGOT_COOLDOWN_SECONDS:
        return

    raw, _ = tokens.issue_link(db, user, "reset")
    audit.record(db, request, user, "password_reset", "user", user.name, user.id, [
        audit.change("reset_link", "Link de redefinição", None, "Pedido em Esqueci minha senha"),
    ])
    db.commit()
    background.add_task(_send_forgot_email, user.name, user.email, tokens.link_url("reset", raw))


def _send_forgot_email(name: str, email: str, link: str) -> None:
    if not mailer.send_reset(name, email, link):
        # Sem SMTP ninguém veria o link; no desenvolvimento ele fica no log.
        logger.warning("e-mail não enviado; link de redefinição de %s: %s", email, link)


def _valid_link(db: DbSession, raw: str, kind: str):
    link = tokens.find_link(db, raw, kind)
    if link is None or link.user.status != LINK_USER_STATUS[kind]:
        raise HTTPException(status_code=404, detail=INVALID_LINK)
    return link


@router.get("/auth/link", response_model=LinkInfo)
def link_info(token: str = Query(max_length=200), kind: str = Query(pattern="^(invite|reset)$"),
              db: DbSession = Depends(get_db)):
    link = _valid_link(db, token, kind)
    return LinkInfo(kind=link.kind, name=link.user.name, email=link.user.email)


def _check_password(password: str) -> None:
    problem = passwords.password_problem(password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)


@router.post("/auth/accept-invite", response_model=Me)
def accept_invite(body: SetPasswordIn, request: Request, response: Response, db: DbSession = Depends(get_db)):
    link = _valid_link(db, body.token, "invite")
    _check_password(body.password)
    user = link.user
    before = accounts.snapshot(user)
    user.password_hash = passwords.hash_password(body.password)
    user.status = "active"
    user.session_version += 1
    tokens.revoke_links(db, user)
    audit.record(db, request, user, "update", "user", user.name, user.id, [
        *audit.diff(before, accounts.snapshot(user), accounts.USER_FIELD_LABELS),
        audit.change("password", "Senha", None, "Criada pelo convite"),
    ])
    start_session(db, request, response, user)
    db.commit()
    logger.info("convite aceito por %s", user.email)
    return me_payload(db, user)


@router.post("/auth/reset-password", response_model=Me)
def reset_password(body: SetPasswordIn, request: Request, response: Response, db: DbSession = Depends(get_db)):
    link = _valid_link(db, body.token, "reset")
    _check_password(body.password)
    user = link.user
    user.password_hash = passwords.hash_password(body.password)
    # Derruba as outras sessões abertas com a senha antiga.
    user.session_version += 1
    tokens.revoke_links(db, user, "reset")
    audit.record(db, request, user, "update", "user", user.name, user.id, [
        audit.change("password", "Senha", None, "Redefinida pelo link"),
    ])
    start_session(db, request, response, user)
    db.commit()
    logger.info("senha redefinida por %s", user.email)
    return me_payload(db, user)
