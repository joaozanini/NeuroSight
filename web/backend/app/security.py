"""Proteção das rotas: login do site (cookie com JWT), permissões, a chave de leitura do fluxo antigo
e a chave do óculos.

Site: `get_current_user` lê o cookie, valida o JWT e recarrega o usuário do banco a cada request,
então um usuário desativado (ou que trocou a senha em outro lugar) perde o acesso na hora.
`require_permission(...)` consulta a matriz da W21 também a cada request.

Fluxo antigo (só leitura, `/legacy/sessions`): com QUESTPRO_API_KEY definida, exige a mesma chave
no X-Api-Key ou o login do site. Sem a chave configurada fica aberto (modo dev).

Óculos (WebSocket e rotas /device): com QUESTPRO_DEVICE_KEY definida, exige a mesma chave no
X-Device-Key. Sem ela fica aberto (modo dev).
"""
import re
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response
from starlette.requests import HTTPConnection
from sqlalchemy.orm import Session as DbSession

from .config import settings
from .db import get_db
from .models import User
from .models.device import DEVICE_ID_PATTERN
from .services import permissions, tokens

NOT_AUTHENTICATED = "não autenticado"


# ---- Sessão do site -------------------------------------------------------------------------

def set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        tokens.SESSION_COOKIE,
        tokens.encode_session(user),
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(tokens.SESSION_COOKIE, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")


def _logged_user(request: HTTPConnection, response: Response, db: DbSession) -> User | None:
    """O usuário do cookie, se ele for válido e o usuário estiver ativo (renova o cookie velho)."""
    raw = request.cookies.get(tokens.SESSION_COOKIE)
    payload = tokens.decode_session(raw) if raw else None
    if payload is None:
        return None
    user = db.get(User, payload["sub"])
    if user is None or user.status != "active" or payload.get("sv") != user.session_version:
        return None
    if tokens.should_renew(payload):
        set_session_cookie(response, user)
    return user


def get_current_user(request: Request, response: Response, db: DbSession = Depends(get_db)) -> User:
    user = _logged_user(request, response, db)
    if user is None:
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def websocket_user(connection: HTTPConnection, db: DbSession) -> User | None:
    """O usuário do cookie num WebSocket (o navegador manda o cookie no upgrade)."""
    return _logged_user(connection, Response(), db)


def require_reader(
    request: Request,
    response: Response,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    db: DbSession = Depends(get_db),
) -> None:
    """Leitura do fluxo antigo: quem está logado no site ou um script com a X-Api-Key.

    Sem QUESTPRO_API_KEY (dev) fica aberta.
    """
    if not settings.api_key:
        return
    if x_api_key and secrets.compare_digest(x_api_key, settings.api_key):
        return
    if _logged_user(request, response, db) is None:
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED)


def require_permission(*required: str):
    """Dependência que exige todas as permissões indicadas e devolve o usuário logado."""
    unknown = set(required) - permissions.PERMISSION_IDS
    if unknown:
        raise ValueError(f"permissões desconhecidas: {sorted(unknown)}")

    def dependency(user: CurrentUser, db: DbSession = Depends(get_db)) -> User:
        granted = permissions.role_permissions(db, user.role)
        if not set(required) <= granted:
            raise HTTPException(status_code=403, detail="você não tem permissão para fazer isso")
        return user

    return dependency


# ---- Óculos ---------------------------------------------------------------------------------

def device_key_ok(key: str | None) -> bool:
    if not settings.device_key:
        return True
    return bool(key) and secrets.compare_digest(key, settings.device_key)


def valid_device_id(device_id: str | None) -> bool:
    return bool(device_id) and re.fullmatch(DEVICE_ID_PATTERN, device_id) is not None


def require_device(
    x_device_key: str | None = Header(default=None, alias="X-Device-Key"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> str:
    """Rotas HTTP do óculos: confere a chave e devolve o id do óculos."""
    if not device_key_ok(x_device_key):
        raise HTTPException(status_code=401, detail="chave do dispositivo inválida")
    if not valid_device_id(x_device_id):
        raise HTTPException(status_code=401, detail="informe o X-Device-Id do óculos")
    return x_device_id


DeviceId = Annotated[str, Depends(require_device)]
