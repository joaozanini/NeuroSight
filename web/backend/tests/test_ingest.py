"""Ingestão do fluxo antigo (create -> frames -> complete) e leitura, depois da troca para `def`.

O contrato é o que o app do óculos e o scripts/replay_session.py usam: os campos das respostas e
os códigos de erro não podem mudar.
"""
import json

import cv2
import numpy as np
import pytest

from app.config import settings

API = settings.api_prefix
DEVICE_ID = "2026-06-17_22-10-54"


def gaze_json(n_frames=4, fps=10.0, size=64):
    frames = [{"idx": i, "t": round(i / fps, 6), "file": f"frames/{i:06d}.jpg"} for i in range(1, n_frames + 1)]
    samples = [
        {"t": k / 30, "valid": k % 5 != 0, "world": [0, 0, 0], "uv": [0.5, 0.5], "confidence": 0.9}
        for k in range(int(n_frames / fps * 30))
    ]
    meta = {"captureFovDeg": 82, "frameWidth": size, "frameHeight": size, "videoFps": fps, "uvOrigin": "top-left"}
    return {"meta": meta, "frames": frames, "samples": samples}


def jpeg(size=64, shade=120):
    ok, buf = cv2.imencode(".jpg", np.full((size, size, 3), shade, dtype=np.uint8))
    assert ok
    return buf.tobytes()


def create(client, payload=None, device_id=DEVICE_ID, **headers):
    return client.post(
        f"{API}/sessions",
        content=json.dumps(payload or gaze_json()),
        headers={"X-Session-Id": device_id, "Content-Type": "application/json", **headers},
    )


def send_frames(client, sid, names, **headers):
    files = [("frames", (name, jpeg(shade=40 * i), "image/jpeg")) for i, name in enumerate(names, 1)]
    return client.post(f"{API}/sessions/{sid}/frames", files=files, headers=headers)


def test_full_ingest_flow_builds_the_video(client):
    r = create(client)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "status", "expected_frames", "received_frames"}
    assert body["status"] == "uploading"
    assert body["expected_frames"] == 4
    assert body["received_frames"] == 0
    sid = body["id"]

    r = send_frames(client, sid, ["000001.jpg", "000002.jpg", "000003.jpg", "000004.jpg"])
    assert r.status_code == 200
    assert r.json() == {
        "received_frames": 4,
        "saved": ["000001.jpg", "000002.jpg", "000003.jpg", "000004.jpg"],
        "rejected": [],
    }

    r = client.post(f"{API}/sessions/{sid}/complete")
    assert r.status_code == 200
    assert r.json() == {"id": sid, "status": "processing", "frame_count": 4, "video_ready": False}

    # O TestClient só devolve depois das background tasks: o MP4 já foi montado.
    detail = client.get(f"{API}/sessions/{sid}").json()
    assert detail["status"] == "complete"
    assert detail["has_video"] is True
    assert detail["video_codec"] in ("h264", "mp4v")
    assert detail["video_url"] == f"{API}/sessions/{sid}/video"
    assert detail["device_session_id"] == DEVICE_ID
    assert detail["captured_at"].startswith("2026-06-17T22:10:54")
    assert detail["sample_count"] == 12
    assert detail["valid_sample_count"] == 9
    assert len(detail["frames"]) == 4 and len(detail["samples"]) == 12

    video = client.get(detail["video_url"], headers={"Range": "bytes=0-99"})
    assert video.status_code == 206
    assert video.headers["content-type"] == "video/mp4"
    assert len(video.content) == 100

    # Repetir o complete de uma sessão pronta só devolve o estado.
    again = client.post(f"{API}/sessions/{sid}/complete").json()
    assert again == {"id": sid, "status": "complete", "frame_count": 4, "video_ready": True}


def test_create_is_idempotent_and_reports_frames_for_resuming(client):
    sid = create(client).json()["id"]
    send_frames(client, sid, ["000001.jpg", "000002.jpg"])

    r = create(client)
    assert r.json()["id"] == sid
    assert r.json()["received_frames"] == 2


@pytest.mark.parametrize("raw", [b"{nao e json", b"[1, 2, 3]", "\udcff".encode("utf-8", "surrogatepass")])
def test_create_rejects_invalid_body(client, raw):
    r = client.post(f"{API}/sessions", content=raw, headers={"X-Session-Id": DEVICE_ID})
    assert r.status_code == 400
    assert r.json() == {"detail": "corpo não é JSON válido"}


def test_create_requires_session_header(client):
    r = client.post(f"{API}/sessions", content=json.dumps(gaze_json()))
    assert r.status_code == 422


def test_frames_rejects_non_jpeg_and_wrong_extension(client):
    sid = create(client).json()["id"]
    files = [
        ("frames", ("000001.jpg", jpeg(), "image/jpeg")),
        ("frames", ("000002.jpg", b"\x89PNG\r\n\x1a\n...", "image/jpeg")),
        ("frames", ("000003.png", jpeg(), "image/png")),
        ("frames", ("../../fora.jpg", jpeg(), "image/jpeg")),
    ]
    r = client.post(f"{API}/sessions/{sid}/frames", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] == ["000001.jpg", "fora.jpg"]  # o caminho do nome é descartado
    assert body["rejected"] == ["000002.jpg", "000003.png"]
    assert body["received_frames"] == 2


def test_frames_for_unknown_session_is_404(client):
    r = send_frames(client, "naoexiste", ["000001.jpg"])
    assert r.status_code == 404


def test_complete_without_frames_fails_the_session(client):
    sid = create(client).json()["id"]
    r = client.post(f"{API}/sessions/{sid}/complete")
    assert r.status_code == 409
    detail = client.get(f"{API}/sessions/{sid}").json()
    assert detail["status"] == "failed"
    assert detail["error_detail"] == "nenhum frame recebido"


def test_list_and_delete(client):
    first = create(client, device_id="2026-06-17_10-00-00").json()["id"]
    second = create(client, device_id="2026-06-17_11-00-00").json()["id"]

    page = client.get(f"{API}/sessions", params={"limit": 1}).json()
    assert page["total"] == 2
    assert page["limit"] == 1 and page["offset"] == 0
    assert [s["id"] for s in page["items"]] == [second]  # mais recente primeiro
    assert "samples" not in page["items"][0]

    r = client.delete(f"{API}/sessions/{first}")
    assert r.json() == {"deleted": first}
    assert client.get(f"{API}/sessions/{first}").status_code == 404
    assert client.get(f"{API}/sessions").json()["total"] == 1


def test_video_missing_is_404(client):
    sid = create(client).json()["id"]
    assert client.get(f"{API}/sessions/{sid}/video").status_code == 404


def test_api_key_protects_writes_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "chave-secreta")

    r = create(client)
    assert r.status_code == 401
    r = create(client, **{"X-Api-Key": "errada"})
    assert r.status_code == 401
    r = create(client, **{"X-Api-Key": "chave-secreta"})
    assert r.status_code == 200
    sid = r.json()["id"]

    assert client.delete(f"{API}/sessions/{sid}").status_code == 401
    # Leituras continuam abertas no fluxo antigo.
    assert client.get(f"{API}/sessions/{sid}").status_code == 200
