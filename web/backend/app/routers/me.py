"""Usuário logado (W05): os próprios dados, com as permissões do perfil, e a troca de senha.

Nome, e-mail e perfil são definidos pelo administrador; aqui só a senha muda. Trocar a senha
derruba as outras sessões abertas e renova o cookie desta.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DbSession

from ..db import get_db
from ..schemas.auth import Me, PasswordChangeIn
from ..security import CurrentUser, set_session_cookie
from ..services import audit, passwords
from ..services.ratelimit import login_limiter
from .auth import me_payload

router = APIRouter()


@router.get("/me", response_model=Me)
def get_me(user: CurrentUser, db: DbSession = Depends(get_db)):
    return me_payload(db, user)


@router.put("/me/password", status_code=204)
def change_password(body: PasswordChangeIn, user: CurrentUser, request: Request, response: Response,
                    db: DbSession = Depends(get_db)):
    key = f"me|{user.id}"
    if login_limiter.blocked(key):
        raise HTTPException(status_code=429, detail="muitas tentativas seguidas. Espere alguns minutos e tente de novo")
    # 400 e não 401: o 401 levaria a pessoa para a tela de login.
    if not passwords.verify_password(user.password_hash, body.current_password):
        login_limiter.fail(key)
        raise HTTPException(status_code=400, detail="a senha atual está incorreta")
    login_limiter.reset(key)
    problem = passwords.password_problem(body.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    user.password_hash = passwords.hash_password(body.new_password)
    user.session_version += 1
    audit.record(db, request, user, "update", "user", user.name, user.id, [
        audit.change("password", "Senha", None, "Alterada pelo próprio usuário"),
    ])
    db.commit()
    set_session_cookie(response, user)
