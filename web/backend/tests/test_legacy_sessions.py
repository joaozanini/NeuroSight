"""Sessões do fluxo antigo (cena 3D): só leitura em /legacy/sessions, com os dados de antes.

A ingestão saiu na Fase 3; as linhas aqui são criadas direto no banco, como as que ficaram no
servidor.
"""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db import SessionLocal
from app.models import LegacySession

from .accounts import researcher

API = settings.api_prefix
LEGACY = f"{API}/legacy/sessions"


def legacy_session(device_id="2026-06-17_22-10-54", minutes=0, video_path=None) -> str:
    with SessionLocal() as db:
        row = LegacySession(
            device_session_id=device_id, status="complete", frame_width=64, frame_height=64, video_fps=10.0,
            sample_count=2, valid_sample_count=1, frame_count=1, video_path=video_path,
            created_at=datetime(2026, 6, 17, tzinfo=timezone.utc) + timedelta(minutes=minutes),
            meta={"captureFovDeg": 82}, frames=[{"idx": 1, "t": 0.0, "file": "frames/000001.jpg"}],
            samples=[{"t": 0.0, "valid": True, "uv": [0.5, 0.5]}, {"t": 0.03, "valid": False}],
        )
        db.add(row)
        db.commit()
        return row.id


def test_list_and_detail(client):
    first = legacy_session("2026-06-17_10-00-00")
    second = legacy_session("2026-06-17_11-00-00", minutes=60)

    page = client.get(LEGACY, params={"limit": 1}).json()
    assert page["total"] == 2
    assert [s["id"] for s in page["items"]] == [second]  # mais recente primeiro
    assert "samples" not in page["items"][0]

    detail = client.get(f"{LEGACY}/{first}").json()
    assert detail["device_session_id"] == "2026-06-17_10-00-00"
    assert len(detail["samples"]) == 2
    assert detail["video_url"] is None


def test_video_is_served_with_range(client, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00" * 300)
    sid = legacy_session(video_path=str(video))
    detail = client.get(f"{LEGACY}/{sid}").json()
    assert detail["video_url"] == f"{LEGACY}/{sid}/video"
    r = client.get(detail["video_url"], headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert len(r.content) == 100


def test_missing_session_or_video_is_404(client):
    sid = legacy_session()
    assert client.get(f"{LEGACY}/naoexiste").status_code == 404
    assert client.get(f"{LEGACY}/{sid}/video").status_code == 404


def test_old_ingest_and_delete_are_gone(client):
    """A ingestão antiga saiu; POST /sessions agora é o assistente, que exige login."""
    sid = legacy_session()
    r = client.post(f"{API}/sessions", json={"meta": {}}, headers={"X-Session-Id": "2026-06-17_22-10-54"})
    assert r.status_code == 401
    assert client.delete(f"{LEGACY}/{sid}").status_code == 405
    assert client.get(f"{API}/sessions/{sid}").status_code == 401


def test_reads_need_login_or_the_key_when_configured(client, monkeypatch):
    sid = legacy_session()
    monkeypatch.setattr(settings, "api_key", "chave-secreta")

    for path in ("", f"/{sid}", f"/{sid}/video"):
        assert client.get(f"{LEGACY}{path}").status_code == 401
        assert client.get(f"{LEGACY}{path}", headers={"X-Api-Key": "errada"}).status_code == 401
    assert client.get(f"{LEGACY}/{sid}", headers={"X-Api-Key": "chave-secreta"}).status_code == 200

    researcher(client)
    assert client.get(LEGACY).json()["total"] == 1
    assert client.get(f"{LEGACY}/{sid}").status_code == 200


def test_reads_stay_open_without_a_configured_key(client):
    sid = legacy_session()
    assert client.get(f"{LEGACY}/{sid}").status_code == 200
