"""`python -m app.seed`: primeiro admin com convite, matriz padrão e os dados de exemplo."""
import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app import seed, seed_media, seed_tracking
from app.db import SessionLocal
from app.models import AuditLog, Patient, RolePermission, Session, SessionMarker, Stimulus, User

from .accounts import API, login, token_from


@pytest.fixture(autouse=True)
def short_demo_videos(monkeypatch):
    """Os vídeos de exemplo têm 45 s e 80 s; nos testes, 1 s basta. A gravação dos dados de exemplo
    fica mínima."""
    monkeypatch.setattr(seed_media, "VIDEOS", [dataclasses.replace(v, seconds=1) for v in seed_media.VIDEOS])
    monkeypatch.setattr(seed_tracking, "DEMO_CAPTURE", {"width": 64, "height": 40, "fps": 2, "jpegQuality": 60})


@pytest.fixture
def no_demo_data(monkeypatch):
    """Para os testes que não olham as sessões: os dados coletados de exemplo são o que mais demora."""
    monkeypatch.setattr(seed_tracking, "generate", lambda db, session, sequence: False)


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


def test_demo_users_are_created_once(client, capsys, no_demo_data):
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


def test_demo_creates_patients_and_stimuli_once(client, capsys, no_demo_data):
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


def test_demo_creates_the_sessions_of_the_prototypes_once(client, capsys, no_demo_data):
    assert seed.main(["--demo"]) == 0
    assert "Sessões de exemplo: 26 criadas." in capsys.readouterr().out
    seed.main(["--demo"])
    assert "Sessões de exemplo: já existem." in capsys.readouterr().out

    # W12 e W06 como a Ana vê: 23 sessões nos últimos 30 dias, P-014 com 3.
    login(client, "ana.souza@exemplo.com", seed.DEMO_PASSWORD)
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    page = client.get(f"{API}/sessions", params={"since": since}).json()
    assert page["total"] == 23
    assert [(r["title"], r["patient_code"], r["status"], r["visibility"]) for r in page["items"][:4]] == [
        ("Rostos neutros e expressivos", "P-014", "running", "private"),
        ("Paisagens naturais", "P-009", "awaiting_data", "private"),
        ("Rostos neutros e expressivos", "P-015", "configured", "private"),
        ("Publicidade em vídeo", "P-011", "interrupted", "shared"),
    ]
    patients = client.get(f"{API}/patients").json()["items"]
    assert [(p["code"], p["sessions_count"]) for p in patients] == [
        ("P-014", 3), ("P-009", 2), ("P-015", 1), ("P-011", 1), ("P-007", 2), ("P-012", 1), ("P-010", 2), ("P-008", 1),
    ]
    login(client, "carlos.lima@exemplo.com", seed.DEMO_PASSWORD)
    assert client.get(f"{API}/sessions").json()["total"] == 26


def test_demo_sessions_get_collected_data(client, capsys):
    """As Concluídas e as Interrompidas passam pela ingestão com dados sintéticos e continuam com o
    status da W12; as Aguardando dados ficam sem dados, como se o óculos ainda enviasse."""
    assert seed.main(["--demo"]) == 0
    assert "Dados coletados de exemplo: 21 sessões" in capsys.readouterr().out
    with SessionLocal() as db:
        sessions = list(db.scalars(select(Session)))
        executed = [s for s in sessions if s.status in ("completed", "interrupted")]
        assert len(executed) == 21
        for s in executed:
            assert s.end_reason == ("button_b" if s.status == "completed" else "interrupted")
            assert s.analysis["recording"]["status"] == "ready" and s.data_received_at is not None
            assert s.ended_at > s.started_at and s.exposures
        assert all(s.analysis is None for s in sessions if s.status not in ("completed", "interrupted"))
        markers = db.scalar(select(func.count()).select_from(SessionMarker))
        assert markers > 0

    login(client, "ana.souza@exemplo.com", seed.DEMO_PASSWORD)
    rows = client.get(f"{API}/sessions", params={"q": "P-010", "status": "completed"}).json()["items"]
    detail = client.get(f"{API}/sessions/{rows[0]['id']}").json()
    assert detail["data_status"] == "ready"
    assert [e["position"] for e in detail["exposures"]] == list(range(1, 13))  # rostos, todos com 5 s
    assert all(e["screen_seconds"] == 5.0 for e in detail["exposures"])
    analysis = client.get(f"{API}/sessions/{rows[0]['id']}/analysis").json()
    assert all(e["fixation_count"] > 0 for e in analysis["exposures"])
    assert [m["text"] for m in analysis["markers"]] == [
        "Paciente movimentou a cabeça", "Equipe de enfermagem entrou no quarto",
    ]


def test_demo_data_fills_sessions_seeded_before(client, capsys, monkeypatch):
    """Um banco semeado antes de existir a análise ganha os dados ao rodar o --demo de novo, uma vez."""
    generate = seed_tracking.generate
    monkeypatch.setattr(seed_tracking, "generate", lambda db, session, sequence: False)
    seed.main(["--demo"])
    monkeypatch.setattr(seed_tracking, "generate", generate)
    capsys.readouterr()

    seed.main(["--demo"])
    out = capsys.readouterr().out
    assert "Sessões de exemplo: já existem." in out
    assert "Dados coletados de exemplo: 21 sessões" in out
    seed.main(["--demo"])
    assert "Dados coletados de exemplo" not in capsys.readouterr().out
