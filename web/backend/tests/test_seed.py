"""`python -m app.seed`: primeiro admin com convite, matriz padrão e os usuários de exemplo."""
from sqlalchemy import select

from app import seed
from app.db import SessionLocal
from app.models import RolePermission, User

from .accounts import API, token_from


def users():
    with SessionLocal() as db:
        return {u.email: (u.role, u.status) for u in db.scalars(select(User))}


def printed_link(out: str) -> str:
    return next(line.strip() for line in out.splitlines() if "token=" in line)


def test_first_admin_gets_an_invite_link(client, capsys):
    assert seed.main(["--admin-email", "Chefe@Lab.br", "--admin-name", "Chefe do Lab"]) == 0
    out = capsys.readouterr().out
    assert users() == {"chefe@lab.br": ("admin", "invited")}
    link = printed_link(out)
    assert link.startswith("http://site.teste/aceitar-convite?token=")

    # Rodar de novo gera um link novo e o anterior deixa de valer.
    seed.main(["--admin-email", "chefe@lab.br"])
    new_link = printed_link(capsys.readouterr().out)
    assert new_link != link
    assert client.get(f"{API}/auth/link", params={"token": token_from(link), "kind": "invite"}).status_code == 404
    r = client.post(f"{API}/auth/accept-invite", json={"token": token_from(new_link), "password": "Senha#forte1"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_without_admin_the_seed_asks_for_one(client, capsys):
    assert seed.main([]) == 1
    assert "--admin-email" in capsys.readouterr().err
    with SessionLocal() as db:
        assert db.scalar(select(RolePermission.role).limit(1)) is not None


def test_demo_users_are_created_once(client, capsys):
    assert seed.main(["--demo"]) == 0
    created = users()
    assert len(created) == 8
    assert created["carlos.lima@exemplo.com"] == ("admin", "active")
    assert created["igor.mendes@exemplo.com"] == ("researcher", "invited")
    assert created["fernanda.lopes@exemplo.com"] == ("researcher", "inactive")
    assert "aceitar-convite?token=" in capsys.readouterr().out

    r = client.post(f"{API}/auth/login", json={"email": "ana.souza@exemplo.com", "password": seed.DEMO_PASSWORD})
    assert r.status_code == 200
    seed.main(["--demo"])
    assert len(users()) == 8
