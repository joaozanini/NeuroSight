"""Ingestão e análise (W16, W17): o óculos envia o JSON v2 e a gravação, o servidor monta o MP4,
analisa e fecha o status; o site mostra os estímulos exibidos, a análise e os downloads auditados.

O óculos é o WebSocket do TestClient (como em test_live.py) e os dados vêm do mesmo gerador do
simulador (app/synthetic.py), num relógio virtual.
"""
import json
import os
from pathlib import Path

import pytest

from app.db import SessionLocal
from app.models import Session
from app.services import ingestion
from app.services.storage import storage
from app.synthetic import Recording, VirtualClock, play

from .accounts import API, audit_entries, login, make_user
from .test_live import dev_headers, device, get_session, new_session, prepared, ready_stimulus, sync
from .test_sessions import BRUNO, create, make_patient, revoke

SMALL_CAPTURE = {"width": 64, "height": 40, "fps": 5, "jpegQuality": 70}


def collect(load: dict, steps, folder: Path, face=True) -> Recording:
    """O que o óculos gravou: o roteiro no relógio virtual, com a sequência do `load`."""
    message = {**load["session"], "capture": SMALL_CAPTURE}
    clock = VirtualClock()
    recording = Recording(message, lambda stim: storage.stimulus_device(stim["stimulusId"], stim["format"]),
                          folder, seed="teste", frame_fps=SMALL_CAPTURE["fps"], face=face, clock=clock)
    play(recording, clock, steps)
    return recording


def upload(client, session_id: str, recording: Recording, folder: Path, complete=True) -> dict:
    url = f"{API}/device/sessions/{session_id}"
    doc = recording.document({"id": "questpro-teste-01", "name": "Quest Pro 01", "model": "Quest Pro"}, "teste")
    r = client.put(f"{url}/tracking", content=json.dumps(doc), headers=dev_headers())
    assert r.status_code == 200, r.text
    names = [f["file"] for f in doc["frames"]]
    for i in range(0, len(names), 20):
        files = [("frames", (n, (folder / "frames" / n).read_bytes(), "image/jpeg")) for n in names[i:i + 20]]
        assert client.post(f"{url}/frames", files=files, headers=dev_headers()).status_code == 200
    if complete:
        r = client.post(f"{url}/complete", headers=dev_headers())
        assert r.json() == {"status": "awaiting_data", "missingFrames": []}
        ingestion.drain()
    return doc


def executed(client, tmp_path, steps=None, n=3, end="button_b", record=True, face=True, complete=True, **overrides):
    """Uma sessão executada no óculos de teste e com os dados enviados. Devolve (id, recording, doc)."""
    session, _ = new_session(client, n=n, record=record, **overrides)
    sid = session["id"]
    with device(client) as (ws, _):
        load = prepared(client, ws, sid)
        assert client.post(f"{API}/sessions/{sid}/start").status_code == 200
        sync(ws)
        if end == "interrupted":
            assert client.post(f"{API}/sessions/{sid}/interrupt").status_code == 200
        else:
            ws.send_json({"type": "ended", "sessionId": sid, "reason": end, "t": 20.0})
        sync(ws)
    steps = steps or [(2.13, "next"), (20.0, end)]
    recording = collect(load, steps, tmp_path, face=face)
    doc = upload(client, sid, recording, tmp_path, complete=complete)
    return sid, recording, doc


# ---- Ingestão ---------------------------------------------------------------------------------------

def test_session_is_processed_and_completed(client, tmp_path):
    sid, recording, doc = executed(client, tmp_path)
    session = client.get(f"{API}/sessions/{sid}").json()
    assert session["status"] == "completed" and session["data_status"] == "ready"
    # Três imagens de 5 s, a partir de 2,13 s, e o B aos 20 s (tela neutra no fim).
    assert [(e["seq"], e["position"], e["name"], e["on_t"], e["screen_seconds"]) for e in session["exposures"]] == [
        (1, 1, "Rosto neutro 01", 2.13, 5.0), (2, 2, "Rosto neutro 02", 7.13, 5.0), (3, 3, "Rosto neutro 03", 12.13, 5.0),
    ]
    assert session["files"] == {
        "tracking_bytes": os.path.getsize(storage.session_tracking(sid)),
        "recording": {"status": "ready", "size_bytes": os.path.getsize(storage.session_recording(sid))},
    }
    assert session["can_export"] is True

    analysis = client.get(f"{API}/sessions/{sid}/analysis").json()
    assert analysis["duration"] == 20.0 and analysis["recording_status"] == "ready"
    truth = recording.truth()
    for exposure, expected in zip(analysis["exposures"], truth["exposures"], strict=True):
        long = [f for f in expected["fixations"] if f["duration"] >= 0.1]
        assert len(long) - 1 <= exposure["fixation_count"] <= len(long)
        assert exposure["samples"] == expected["samples"] and exposure["valid_samples"] == expected["validSamples"]
        assert exposure["first_fixation_ms"] == pytest.approx(1000 * (long[0]["start"] - expected["on"]), abs=30)
        assert len(exposure["fixations"]) == exposure["fixation_count"] and exposure["heat"]
        assert exposure["file_url"] == f"/api/v1/stimuli/{exposure['stimulus_id']}/file"
    video = analysis["recording"]
    assert len(video["frame_t"]) == len(doc["frames"]) == len(video["frame_gaze"]) == 100  # 20 s a 5 fps
    assert (video["fps"], video["width"], video["height"]) == (5, 64, 40)
    assert [s["label"] for s in analysis["face"]["series"]] == [
        "Sobrancelha interna elevada", "Canto da boca puxado", "Olhos fechados",
    ]
    assert len(analysis["face"]["series"][0]["values"]) == 200

    r = client.get(f"{API}/sessions/{sid}/recording", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and r.headers["content-type"] == "video/mp4" and len(r.content) == 100


def test_interrupted_and_dropped_sessions_end_as_interrupted(client, tmp_path):
    sid, _, _ = executed(client, tmp_path / "a", end="interrupted", steps=[(1.0, "next"), (4.0, "interrupted")])
    assert get_session(sid).status == "interrupted"
    assert get_session(sid).end_reason == "interrupted"

    # O app fechou no meio: o óculos volta sem a sessão e o servidor encerra como queda.
    sid = create(client, make_patient("P-016", "Outro Paciente"), [ready_stimulus("Rosto alegre 02")])["id"]
    with device(client) as (ws, _):
        load = prepared(client, ws, sid)
        client.post(f"{API}/sessions/{sid}/start")
        sync(ws)
    with device(client) as (ws, _):
        sync(ws)
    assert get_session(sid).end_reason == "disconnected"
    recording = collect(load, [(1.0, "next"), (3.0, "interrupted")], tmp_path / "b")
    upload(client, sid, recording, tmp_path / "b")
    assert get_session(sid).status == "interrupted"


def test_session_without_recording(client, tmp_path):
    sid, _, doc = executed(client, tmp_path, record=False, face=False)
    assert doc["frames"] == [] and doc["meta"]["capture"] is None and doc["face"] is None
    session = client.get(f"{API}/sessions/{sid}").json()
    assert session["files"]["recording"] == {"status": "none", "size_bytes": None}
    analysis = client.get(f"{API}/sessions/{sid}/analysis").json()
    assert analysis["recording_status"] == "none" and analysis["recording"] is None and analysis["face"] is None
    assert client.get(f"{API}/sessions/{sid}/recording").status_code == 404
    assert client.get(f"{API}/sessions/{sid}/downloads/recording").status_code == 404


def test_data_status_while_waiting_and_processing(client, tmp_path):
    sid, _, _ = executed(client, tmp_path, complete=False)
    detail = client.get(f"{API}/sessions/{sid}").json()
    assert (detail["status"], detail["data_status"], detail["exposures"], detail["files"]) == \
        ("awaiting_data", "waiting", [], None)
    r = client.get(f"{API}/sessions/{sid}/analysis")
    assert r.status_code == 409 and r.json()["detail"] == "os dados desta sessão ainda não foram processados"
    assert client.post(f"{API}/device/sessions/{sid}/complete", headers=dev_headers()).status_code == 200
    ingestion.drain()
    assert client.get(f"{API}/sessions/{sid}").json()["data_status"] == "ready"
    # O óculos repetiu o complete (a resposta se perdeu): responde o status final.
    r = client.post(f"{API}/device/sessions/{sid}/complete", headers=dev_headers())
    assert r.json() == {"status": "completed", "missingFrames": []}
    r = client.put(f"{API}/device/sessions/{sid}/tracking", content=b"{}", headers=dev_headers())
    assert r.status_code == 409


def test_processing_failure_keeps_waiting_and_is_retried(client, tmp_path, monkeypatch):
    sid, recording, _ = executed(client, tmp_path, complete=False)

    def broken(*args, **kwargs):
        raise RuntimeError("defeito na análise")

    monkeypatch.setattr(ingestion.analysis, "analyze", broken)
    client.post(f"{API}/device/sessions/{sid}/complete", headers=dev_headers())
    ingestion.drain()
    detail = client.get(f"{API}/sessions/{sid}").json()
    assert (detail["status"], detail["data_status"]) == ("awaiting_data", "failed")
    assert detail["data_error"] == "erro inesperado no processamento"

    monkeypatch.undo()  # corrigido o defeito, a API sobe de novo e retoma
    ingestion.resume_pending()
    ingestion.drain()
    assert client.get(f"{API}/sessions/{sid}").json()["status"] == "completed"


def test_new_json_after_complete_is_processed_again(client, tmp_path, monkeypatch):
    sid, recording, doc = executed(client, tmp_path, complete=False)
    queued = []
    monkeypatch.setattr(ingestion, "schedule", queued.append)  # segura a fila
    client.post(f"{API}/device/sessions/{sid}/complete", headers=dev_headers())
    assert queued == [sid]
    # Antes de a fila chegar nela, o óculos reenvia o JSON: o envio volta a ficar em aberto.
    doc["events"] = [e for e in doc["events"] if e["type"] != "stimulus_on" or e["position"] == 1]
    r = client.put(f"{API}/device/sessions/{sid}/tracking", content=json.dumps(doc), headers=dev_headers())
    assert r.status_code == 200 and get_session(sid).data_received_at is None
    assert ingestion.process(sid) is False  # sem o complete novo, nada a processar
    client.post(f"{API}/device/sessions/{sid}/complete", headers=dev_headers())
    assert queued == [sid, sid]
    assert ingestion.process(sid) is True
    session = client.get(f"{API}/sessions/{sid}").json()
    assert session["status"] == "completed" and [e["position"] for e in session["exposures"]] == [1]


# ---- Downloads -------------------------------------------------------------------------------------

def test_downloads_are_exported_and_audited(client, tmp_path):
    sid, _, _ = executed(client, tmp_path)
    r = client.get(f"{API}/sessions/{sid}/downloads/tracking", params={"tz": "America/Sao_Paulo"})
    assert r.status_code == 200 and r.content == Path(storage.session_tracking(sid)).read_bytes()
    assert r.headers["content-type"] == "application/json"
    started = get_session(sid).started_at
    assert "attachment" in r.headers["content-disposition"] and "P-015_" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].endswith('_rastreamento.json"')
    assert started is not None

    r = client.get(f"{API}/sessions/{sid}/downloads/recording")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"
    assert r.headers["content-disposition"].endswith('_gravacao.mp4"')

    r = client.get(f"{API}/sessions/{sid}/downloads/csv")
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    text = r.content.decode("utf-8")
    assert text.startswith("﻿Sessão;Paciente;Data;Ordem;Nº;Estímulo;Tipo;Início (s);Fim (s);Tempo de tela (s);")
    lines = text.strip().split("\r\n")
    header = lines[0].split(";")
    assert "Sobrancelha interna elevada (média)" in header and "TONGUE_RETREAT (média)" in header
    assert len(header) == 16 + 3 + 70
    rows = [line.split(";") for line in lines[1:]]
    assert [(row[3], row[4], row[5], row[6], row[7], row[9]) for row in rows] == [
        ("1", "1", "Rosto neutro 01", "Imagem", "2,130", "5,000"),
        ("2", "2", "Rosto neutro 02", "Imagem", "7,130", "5,000"),
        ("3", "3", "Rosto neutro 03", "Imagem", "12,130", "5,000"),
    ]

    # Retomar um download pelo meio não é outra exportação.
    client.get(f"{API}/sessions/{sid}/downloads/recording", headers={"Range": "bytes=100-"})
    entries = audit_entries(action="export")
    assert [(e.entity_type, e.entity_id, e.entity_label, e.user_name) for e in entries] == [
        ("session", sid, "Rostos neutros e expressivos, P-015", "Ana Souza"),
    ] * 3
    assert [e.changes[0]["after"] for e in entries] == [
        "Dados de rastreamento (JSON)", "Gravação da sessão (MP4)", "Métricas por estímulo (CSV)",
    ]
    assert entries[0].changes[0]["label"] == "Arquivo"


def test_downloads_need_the_export_permission_and_access(client, tmp_path):
    sid, _, _ = executed(client, tmp_path)
    revoke("researcher", "sessions.export")
    assert client.get(f"{API}/sessions/{sid}/downloads/csv").status_code == 403
    assert client.get(f"{API}/sessions/{sid}").json()["can_export"] is False
    assert client.get(f"{API}/sessions/{sid}/analysis").json()["can_export"] is False

    make_user("Bruno Castro", BRUNO, role="researcher")
    login(client, BRUNO)
    assert client.get(f"{API}/sessions/{sid}/analysis").status_code == 404
    assert client.get(f"{API}/sessions/{sid}/recording").status_code == 404
    assert audit_entries(action="export") == []


def test_session_stored_rows(client, tmp_path):
    """O que fica no banco: o resumo em sessions.analysis e uma linha por exibição."""
    sid, _, _ = executed(client, tmp_path)
    with SessionLocal() as db:
        session = db.get(Session, sid)
        summary = session.analysis
        assert summary["version"] == 1 and summary["params"]["dispersion_deg"] == 1.0
        assert summary["params"]["min_fixation_ms"] == 100
        assert [e.seq for e in session.exposures] == [1, 2, 3]
        assert all(len(e.face_means) == 70 for e in session.exposures)


def test_face_series_follow_the_legend_order(client, tmp_path):
    """O JSONB do PostgreSQL devolve as chaves em outra ordem; a W17 recebe a da legenda padrão."""
    sid, _, _ = executed(client, tmp_path)
    with SessionLocal() as db:
        session = db.get(Session, sid)
        data = dict(session.analysis)
        series = data["face"]["series"]
        data["face"] = {**data["face"], "series": {key: series[key] for key in sorted(series)}}
        session.analysis = data
        db.commit()
    keys = [s["key"] for s in client.get(f"{API}/sessions/{sid}/analysis").json()["face"]["series"]]
    assert keys == ["INNER_BROW_RAISER", "LIP_CORNER_PULLER", "EYES_CLOSED"]
