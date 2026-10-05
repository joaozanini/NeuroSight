"""Acesso (W01–W03, W05): login, sessão no cookie, esqueci minha senha, links e troca de senha."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuthToken, User, utcnow
from app.services import tokens

from .accounts import API, PASSWORD, admin, audit_entries, get_user, login, make_user, token_from

NEW_PASSWORD = "Nova#senha9"


@pytest.fixture
def other_client(client):
    """Um segundo navegador, com o próprio cookie (o banco já está migrado pelo `client`)."""
    from app.main import app

    return TestClient(app)


def issue(uid: str, kind: str, hours_ago: float = 0) -> str:
    with SessionLocal() as db:
        user = db.get(User, uid)
        raw, link = tokens.issue_link(db, user, kind)
        if hours_ago:
            link.created_at -= timedelta(hours=hours_ago)
            link.expires_at -= timedelta(hours=hours_ago)
        db.commit()
        return raw


# ---- Login e sessão -------------------------------------------------------------------------

def test_login_sets_an_httponly_cookie_and_returns_the_profile(client):
    uid = make_user()
    r = client.post(f"{API}/auth/login", json={"email": "  Carlos.Lima@Exemplo.com ", "password": PASSWORD},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/129.0"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Carlos Lima"
    assert body["role_label"] == "Admin"
    assert "admin.users" in body["permissions"] and len(body["permissions"]) == 12
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{tokens.SESSION_COOKIE}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie

    assert client.get(f"{API}/me").json()["id"] == uid
    assert get_user(uid).last_login_at is not None
    [entry] = audit_entries(action="login")
    assert (entry.user_id, entry.user_name, entry.user_role) == (uid, "Carlos Lima", "admin")
    assert (entry.entity_type, entry.entity_label) == ("system", "Acesso ao sistema")
    assert entry.ip == "testclient"
    assert "Chrome" in entry.user_agent


@pytest.mark.parametrize("email, password", [
    ("carlos.lima@exemplo.com", "Senha#errada1"),
    ("ninguem@exemplo.com", PASSWORD),
])
def test_wrong_credentials_get_the_same_answer(client, email, password):
    make_user()
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 401
    assert r.json()["detail"] == "e-mail ou senha incorretos"
    assert "set-cookie" not in r.headers
    assert audit_entries() == []


def test_invited_user_cannot_log_in_before_creating_the_password(client):
    make_user(status="invited", password=None)
    r = client.post(f"{API}/auth/login", json={"email": "carlos.lima@exemplo.com", "password": ""})
    assert r.status_code == 401


def test_inactive_user_is_told_the_access_is_disabled(client):
    make_user(status="inactive")
    r = client.post(f"{API}/auth/login", json={"email": "carlos.lima@exemplo.com", "password": PASSWORD})
    assert r.status_code == 403
    assert "desativado" in r.json()["detail"]


def test_too_many_failures_block_the_login_for_a_while(client):
    make_user()
    for _ in range(10):
        client.post(f"{API}/auth/login", json={"email": "carlos.lima@exemplo.com", "password": "errada"})
    r = client.post(f"{API}/auth/login", json={"email": "carlos.lima@exemplo.com", "password": PASSWORD})
    assert r.status_code == 429


def test_routes_need_the_cookie_and_logout_clears_it(client):
    admin(client)
    assert client.get(f"{API}/me").status_code == 200
    r = client.post(f"{API}/auth/logout")
    assert r.status_code == 204
    assert client.get(f"{API}/me").status_code == 401


@pytest.mark.parametrize("cookie", ["lixo", "a.b.c"])
def test_forged_cookie_is_refused(client, cookie):
    make_user()
    client.cookies.set(tokens.SESSION_COOKIE, cookie)
    assert client.get(f"{API}/me").status_code == 401


def test_expired_session_is_refused_and_old_sessions_are_renewed(client):
    uid = make_user()
    user = get_user(uid)
    client.cookies.set(tokens.SESSION_COOKIE, tokens.encode_session(user, now=utcnow() - timedelta(hours=13)))
    assert client.get(f"{API}/me").status_code == 401

    old = tokens.encode_session(user, now=utcnow() - timedelta(hours=7))
    client.cookies.set(tokens.SESSION_COOKIE, old)
    r = client.get(f"{API}/me")
    assert r.status_code == 200
    renewed = r.cookies.get(tokens.SESSION_COOKIE)
    assert renewed and renewed != old

    fresh = tokens.encode_session(user)
    client.cookies.set(tokens.SESSION_COOKIE, fresh)
    assert tokens.SESSION_COOKIE not in client.get(f"{API}/me").cookies


# ---- Esqueci minha senha e redefinição ------------------------------------------------------

def test_forgot_answers_the_same_and_only_creates_a_link_for_active_accounts(client, caplog):
    uid = make_user()
    make_user("Fernanda Lopes", "fernanda.lopes@exemplo.com", "researcher", "inactive")
    for email in ("carlos.lima@exemplo.com", "ninguem@exemplo.com", "fernanda.lopes@exemplo.com"):
        r = client.post(f"{API}/auth/forgot", json={"email": email})
        assert r.status_code == 204
    with SessionLocal() as db:
        links = db.scalars(select(AuthToken)).all()
    assert [(link.user_id, link.kind) for link in links] == [(uid, "reset")]
    # Sem SMTP o link fica no log do servidor.
    assert "http://site.teste/redefinir-senha?token=" in caplog.text
    [entry] = audit_entries(action="password_reset")
    assert entry.changes[0]["after"] == "Pedido em Esqueci minha senha"

    # Pedir de novo logo em seguida não gera outro link.
    client.post(f"{API}/auth/forgot", json={"email": "carlos.lima@exemplo.com"})
    with SessionLocal() as db:
        assert len(db.scalars(select(AuthToken)).all()) == 1


def test_reset_link_flow(client, other_client):
    uid = make_user()
    login(other_client)
    raw = issue(uid, "reset")

    # A senha atual continua valendo até o link ser usado.
    login(client)
    client.cookies.clear()

    r = client.get(f"{API}/auth/link", params={"token": raw, "kind": "reset"})
    assert r.json() == {"kind": "reset", "name": "Carlos Lima", "email": "carlos.lima@exemplo.com"}
    assert client.get(f"{API}/auth/link", params={"token": raw, "kind": "invite"}).status_code == 404

    r = client.post(f"{API}/auth/reset-password", json={"token": raw, "password": "fraca"})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("A senha precisa ter:")

    r = client.post(f"{API}/auth/reset-password", json={"token": raw, "password": NEW_PASSWORD})
    assert r.status_code == 200
    assert client.get(f"{API}/me").status_code == 200  # já entra logado
    # A sessão aberta com a senha antiga cai.
    assert other_client.get(f"{API}/me").status_code == 401

    assert client.post(f"{API}/auth/reset-password", json={"token": raw, "password": NEW_PASSWORD}).status_code == 404
    client.cookies.clear()
    assert client.post(f"{API}/auth/login", json={"email": "carlos.lima@exemplo.com", "password": PASSWORD}).status_code == 401
    login(client, password=NEW_PASSWORD)
    [entry] = audit_entries(action="update")
    assert entry.changes == [{"field": "password", "label": "Senha", "before": None, "after": "Redefinida pelo link"}]


def test_expired_or_replaced_links_are_refused(client):
    uid = make_user()
    old = issue(uid, "reset", hours_ago=3)
    assert client.get(f"{API}/auth/link", params={"token": old, "kind": "reset"}).status_code == 404
    first = issue(uid, "reset")
    second = issue(uid, "reset")
    assert client.get(f"{API}/auth/link", params={"token": first, "kind": "reset"}).status_code == 404
    assert client.get(f"{API}/auth/link", params={"token": second, "kind": "reset"}).status_code == 200


def test_accepting_the_invite_activates_and_logs_in(client):
    admin(client)
    r = client.post(f"{API}/users", json={"name": "Igor Mendes", "email": "igor.mendes@exemplo.com", "role": "researcher"})
    invite = r.json()["invite"]
    assert invite["email_sent"] is False
    raw = token_from(invite["link"])
    assert invite["link"].startswith("http://site.teste/aceitar-convite?token=")
    client.cookies.clear()

    r = client.get(f"{API}/auth/link", params={"token": raw, "kind": "invite"})
    assert r.json()["name"] == "Igor Mendes"
    r = client.post(f"{API}/auth/accept-invite", json={"token": raw, "password": NEW_PASSWORD})
    assert r.status_code == 200
    me = client.get(f"{API}/me").json()
    assert me["email"] == "igor.mendes@exemplo.com"
    assert get_user(me["id"]).status == "active"
    assert client.post(f"{API}/auth/accept-invite", json={"token": raw, "password": NEW_PASSWORD}).status_code == 404

    entry = audit_entries(action="update", user_id=me["id"])[0]
    assert entry.changes == [
        {"field": "status", "label": "Status", "before": "Convite pendente", "after": "Ativo"},
        {"field": "password", "label": "Senha", "before": None, "after": "Criada pelo convite"},
    ]
    assert len(audit_entries(action="login", user_id=me["id"])) == 1


# ---- Meu perfil ------------------------------------------------------------------------------

def test_change_password(client, other_client):
    admin(client)
    login(other_client)
    r = client.put(f"{API}/me/password", json={"current_password": "errada", "new_password": NEW_PASSWORD})
    assert r.status_code == 400
    assert r.json()["detail"] == "a senha atual está incorreta"
    r = client.put(f"{API}/me/password", json={"current_password": PASSWORD, "new_password": "fraca"})
    assert r.status_code == 422

    r = client.put(f"{API}/me/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert r.status_code == 204
    assert client.get(f"{API}/me").status_code == 200  # esta sessão continua, com cookie novo
    assert other_client.get(f"{API}/me").status_code == 401
    client.cookies.clear()
    login(client, password=NEW_PASSWORD)
    [entry] = audit_entries(action="update")
    assert entry.changes[0]["after"] == "Alterada pelo próprio usuário"
