"""Auxiliares dos testes de contas: criar usuários direto no banco, entrar e ler a auditoria."""
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AuditLog, User
from app.services import passwords

API = settings.api_prefix
PASSWORD = "Senha#forte1"


def make_user(name="Carlos Lima", email="carlos.lima@exemplo.com", role="admin", status="active",
              password=PASSWORD) -> str:
    with SessionLocal() as db:
        user = User(name=name, email=email, role=role, status=status,
                    password_hash=passwords.hash_password(password) if password else None)
        db.add(user)
        db.commit()
        return user.id


def login(client, email="carlos.lima@exemplo.com", password=PASSWORD):
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def admin(client) -> str:
    """Cria o admin Carlos Lima e entra com ele."""
    uid = make_user()
    login(client)
    return uid


def researcher(client, email="ana.souza@exemplo.com") -> str:
    uid = make_user("Ana Souza", email, "researcher")
    login(client, email)
    return uid


def token_from(link: str) -> str:
    return parse_qs(urlparse(link).query)["token"][0]


def audit_entries(**filters) -> list[AuditLog]:
    with SessionLocal() as db:
        stmt = select(AuditLog).order_by(AuditLog.id)
        for field, value in filters.items():
            stmt = stmt.where(getattr(AuditLog, field) == value)
        return list(db.scalars(stmt))


def get_user(uid: str) -> User:
    with SessionLocal() as db:
        return db.get(User, uid)
