"""`python -m app.seed`: primeiro admin com convite, matriz padrão e os dados de exemplo."""
import dataclasses

import pytest
from sqlalchemy import func, select

from app import seed, seed_media
from app.db import SessionLocal
from app.models import AuditLog, Patient, RolePermission, Stimulus, User

from .accounts import API, login, token_from


@pytest.fixture(autouse=True)
def short_demo_videos(monkeypatch):
    """Os vídeos de exemplo têm 45 s e 80 s; nos testes, 1 s basta."""
    monkeypatch.setattr(seed_media, "VIDEOS", [dataclasses.replace(v, seconds=1) for v in seed_media.VIDEOS])


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


def test_demo_creates_patients_and_stimuli_once(client, capsys):
    assert seed.main(["--demo"]) == 0
    with SessionLocal() as db:
        codes = sorted(db.scalars(select(Patient.code)))
        assert codes == [f"P-{i:03d}" for i in range(1, 16)]
        mariana = db.scalar(select(Patient).where(Patient.code == "P-014"))
        assert (mariana.name, mariana.consent_file_name) == ("Mariana Alves", "termo-P-014.pdf")
        stimuli = list(db.scalars(select(Stimulus)))
        assert {s.status for s in stimuli} == {"active"}
        assert {s.device_status for s in stimuli} == {"ready"}
        assert sum(s.kind == "video" for s in stimuli) == 2
        batch = db.scalar(select(AuditLog).where(AuditLog.entity_type == "stimulus"))
        assert batch.entity_label == "15 imagens e 2 vídeos enviados à biblioteca"
        assert batch.user_name == "Ana Souza"
    out = capsys.readouterr().out
    assert "Pacientes de exemplo: 15 criados." in out

    seed.main(["--demo"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Patient)) == 15
        assert db.scalar(select(func.count()).select_from(Stimulus)) == len(seed_media.IMAGES) + 2
    assert "Estímulos de exemplo: já existem." in capsys.readouterr().out

    login(client, "ana.souza@exemplo.com", seed.DEMO_PASSWORD)
    page = client.get(f"{API}/stimuli").json()
    assert page["counts"] == {"total": 17, "images": 15, "videos": 2}
    assert client.get(f"{API}/patients/next-code").json() == {"code": "P-016"}
    pid = client.get(f"{API}/patients", params={"q": "P-014"}).json()["items"][0]["id"]
    assert client.get(f"{API}/patients/{pid}/consent").content.startswith(b"%PDF-")
