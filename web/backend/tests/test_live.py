"""Execução ao vivo (W14, W15) e o protocolo do óculos (docs/protocolo-oculos.md): pareamento pelo
IP e pelo código, preparação, início, comandos, marcações, interrupção, o B, a reconexão e o envio
dos dados. O óculos é um WebSocket do TestClient.
"""
import hashlib
import json
import os
from contextlib import contextmanager

import pytest
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.db import SessionLocal
from app.models import Device, Session, Stimulus
from app.services.storage import storage

from .accounts import API, audit_entries, login, make_user, researcher
from .media_files import jpeg
from .test_sessions import ANA, BRUNO, create, make_patient, make_stimulus

DEVICE_ID = "questpro-teste-01"


def ready_stimulus(name="Rosto neutro 01", kind="image", content=None) -> str:
    """Estímulo com a versão para o óculos pronta no disco."""
    sid = make_stimulus(name, kind)
    data = content or jpeg()
    fmt = "mp4" if kind == "video" else "jpg"
    path = storage.stimulus_device(sid, fmt)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    with SessionLocal() as db:
        s = db.get(Stimulus, sid)
        s.device_status, s.device_format, s.device_size_bytes = "ready", fmt, len(data)
        s.device_sha256, s.device_width, s.device_height = hashlib.sha256(data).hexdigest(), 64, 40
        db.commit()
    return sid


def hello(**overrides):
    message = {
        "type": "hello", "protocol": 1, "deviceId": DEVICE_ID, "name": "Quest Pro 01", "model": "Quest Pro",
        "appVersion": "1.0.0", "tracking": {"eye": "active", "face": "active"}, "state": "idle",
    }
    message.update(overrides)
    return message


@contextmanager
def device(client, headers=None, **hello_fields):
    """Um óculos conectado; devolve (ws, welcome)."""
    with client.websocket_connect(f"{API}/device/ws", headers=headers or {}) as ws:
        ws.send_json(hello(**hello_fields))
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome", welcome
        yield ws, welcome


def sync(ws) -> list[dict]:
    """Manda um ping e junta o que chegar até o pong: o servidor trata as mensagens em ordem, então
    tudo o que o óculos mandou antes já foi processado."""
    ws.send_json({"type": "ping"})
    received = []
    while True:
        message = ws.receive_json()
        if message["type"] == "pong":
            return received
        received.append(message)


def dev_headers(device_id=DEVICE_ID):
    return {"X-Device-Id": device_id}


def prepared(client, ws, session_id, loaded=True) -> dict:
    """Prepara a sessão neste óculos (pelo IP) e devolve o `load` recebido."""
    r = client.post(f"{API}/sessions/{session_id}/prepare", json={"device_id": DEVICE_ID})
    assert r.status_code == 200, r.text
    load = next(m for m in sync(ws) if m["type"] == "load")
    if loaded:
        total = len(load["session"]["stimuli"])
        ws.send_json({"type": "load_progress", "sessionId": session_id, "loaded": total, "total": total})
        sync(ws)
    return load


def started(client, ws, session_id):
    prepared(client, ws, session_id)
    r = client.post(f"{API}/sessions/{session_id}/start")
    assert r.status_code == 200, r.text
    start = next(m for m in sync(ws) if m["type"] == "start")
    assert start["sessionId"] == session_id
    return r.json()


def new_session(client, n=2, **overrides):
    researcher(client)
    stimuli = [ready_stimulus(f"Rosto neutro 0{i + 1}") for i in range(n)]
    return create(client, make_patient(), stimuli, **overrides), stimuli


def get_session(session_id) -> Session:
    with SessionLocal() as db:
        return db.get(Session, session_id)


def tracking(session_id, frames=(), end_reason="button_b"):
    return {
        "version": 2,
        "meta": {"sessionId": session_id, "endReason": end_reason, "panel": {"widthM": 2.4, "heightM": 1.35,
                                                                           "distanceM": 2.0}},
        "stimuli": [], "events": [], "gaze": [], "face": None,
        "frames": [{"idx": i + 1, "t": i / 30, "file": name} for i, name in enumerate(frames)],
    }


# ---- Conexão e pareamento -----------------------------------------------------------------------

def test_device_registers_and_gets_a_pairing_code(client):
    with device(client) as (ws, welcome):
        assert len(welcome["pairingCode"]) == 4 and welcome["pairingCode"].isdigit()
        assert sync(ws) == []
    with SessionLocal() as db:
        row = db.get(Device, DEVICE_ID)
        assert (row.name, row.model, row.app_version) == ("Quest Pro 01", "Quest Pro", "1.0.0")


def test_device_key_is_required_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "device_key", "segredo-do-oculos")
    with client.websocket_connect(f"{API}/device/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4401
    with device(client, headers={"X-Device-Key": "segredo-do-oculos"}) as (ws, _):
        assert sync(ws) == []
    r = client.get(f"{API}/device/sessions/x/frames", headers=dev_headers())
    assert r.status_code == 401


def test_invalid_hello_closes_the_socket(client):
    with client.websocket_connect(f"{API}/device/ws") as ws:
        ws.send_json({"type": "hello", "deviceId": "com espaço", "name": "X"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4400


def test_a_new_connection_of_the_same_device_replaces_the_old_and_keeps_the_code(client):
    with device(client) as (old, first):
        with device(client) as (new, second):
            assert second["pairingCode"] == first["pairingCode"]
            with pytest.raises(WebSocketDisconnect) as closed:
                old.receive_json()
            assert closed.value.code == 4409
            assert sync(new) == []


def test_nearby_lists_devices_on_the_same_ip(client):
    researcher(client)
    with device(client):
        r = client.get(f"{API}/devices/nearby")
        assert r.status_code == 200
        assert [d["name"] for d in r.json()] == ["Quest Pro 01"]
    assert client.get(f"{API}/devices/nearby").json() == []


# ---- Preparação (W14) -----------------------------------------------------------------------------

def test_prepare_by_network_sends_the_sequence_and_tracks_the_load(client):
    session, stimuli = new_session(client)
    with device(client) as (ws, _):
        load = prepared(client, ws, session["id"], loaded=False)["session"]
        assert load["title"] == "Rostos neutros e expressivos" and load["patientCode"] == "P-015"
        assert load["record"] is True and load["capture"]["fps"] == settings.capture_fps
        first = load["stimuli"][0]
        assert (first["position"], first["stimulusId"], first["kind"], first["screenSeconds"]) == (1, stimuli[0], "image", 5)

        # O óculos baixa o arquivo e confere o sha256.
        r = client.get(first["url"], headers=dev_headers())
        assert r.status_code == 200 and hashlib.sha256(r.content).hexdigest() == first["sha256"]
        assert client.get(first["url"], headers=dev_headers("outro-oculos")).status_code == 403

        before = client.get(f"{API}/sessions/{session['id']}/live").json()["version"]
        ws.send_json({"type": "load_progress", "sessionId": session["id"], "loaded": 1, "total": 2})
        sync(ws)
        live = client.get(f"{API}/sessions/{session['id']}/live").json()
        assert live["load"] == {"loaded": 1, "total": 2, "error": None}
        assert live["version"] > before  # o site fica com o retrato de versão maior
        assert live["device"]["name"] == "Quest Pro 01" and live["device"]["online"] is True
        assert live["device"]["same_network"] is True and live["device"]["paired_by"] == "network"
        assert live["device"]["tracking"] == {"eye": "active", "face": "active"}

        ws.send_json({"type": "load_failed", "sessionId": session["id"], "stimulusId": stimuli[1], "message": "sem espaço"})
        sync(ws)
        live = client.get(f"{API}/sessions/{session['id']}/live").json()
        assert live["load"]["error"] == {"stimulus_id": stimuli[1], "message": "sem espaço"}


def test_prepare_by_pairing_code(client):
    session, _ = new_session(client)
    with device(client) as (ws, welcome):
        r = client.post(f"{API}/sessions/{session['id']}/prepare", json={"pairing_code": "0000"})
        assert r.status_code in (404, 422)
        r = client.post(f"{API}/sessions/{session['id']}/prepare", json={"pairing_code": welcome["pairingCode"]})
        assert r.status_code == 200, r.text
        assert r.json()["device"]["paired_by"] == "code"
        assert any(m["type"] == "load" for m in sync(ws))
    r = client.post(f"{API}/sessions/{session['id']}/prepare", json={"pairing_code": "12a4"})
    assert r.status_code == 422


def test_prepare_waits_for_the_device_version(client):
    researcher(client)
    pending = make_stimulus("Rosto alegre 02")  # versão para o óculos ainda pendente
    session = create(client, make_patient(), [pending])
    with device(client):
        r = client.post(f"{API}/sessions/{session['id']}/prepare", json={"device_id": DEVICE_ID})
        assert r.status_code == 409 and "sendo preparado" in r.json()["detail"]


def test_release_and_rebinding_send_unload(client):
    session, stimuli = new_session(client)
    other = create(client, make_patient("P-016"), stimuli)
    with device(client) as (ws, _):
        prepared(client, ws, session["id"])
        # Preparar outra sessão no mesmo óculos tira a primeira dele.
        prepared(client, ws, other["id"], loaded=False)
        assert client.get(f"{API}/sessions/{session['id']}/live").json()["device"] is None
        r = client.post(f"{API}/sessions/{other['id']}/release")
        assert r.status_code == 200 and r.json()["device"] is None
        assert {"type": "unload", "sessionId": other["id"]} in sync(ws)


def test_only_the_owner_runs_the_session(client):
    session, _ = new_session(client)
    make_user("Bruno Castro", BRUNO, "researcher")
    login(client, BRUNO)
    r = client.post(f"{API}/sessions/{session['id']}/prepare", json={"device_id": DEVICE_ID})
    assert r.status_code == 404  # não vê a sessão privada
    admin_id = make_user("Carlos Lima", "carlos.lima@exemplo.com", "admin")
    assert admin_id
    login(client, "carlos.lima@exemplo.com")
    r = client.post(f"{API}/sessions/{session['id']}/start")
    assert r.status_code == 403 and r.json()["detail"] == "só o responsável pela sessão pode executá-la"


# ---- Início, comandos e marcações (W15) -------------------------------------------------------------

def test_start_requires_device_load_and_eye_tracking(client):
    session, _ = new_session(client)
    r = client.post(f"{API}/sessions/{session['id']}/start")
    assert r.status_code == 409 and r.json()["detail"] == "escolha o óculos antes de iniciar"
    with device(client, tracking={"eye": "no_permission", "face": "active"}) as (ws, _):
        prepared(client, ws, session["id"], loaded=False)
        r = client.post(f"{API}/sessions/{session['id']}/start")
        assert r.json()["detail"] == "o óculos ainda está carregando os estímulos"
        ws.send_json({"type": "load_progress", "sessionId": session["id"], "loaded": 2, "total": 2})
        sync(ws)
        r = client.post(f"{API}/sessions/{session['id']}/start")
        assert r.json()["detail"] == "o eye tracking do óculos não está ativo"
        ws.send_json({"type": "status", "tracking": {"eye": "active", "face": "unavailable"}})
        sync(ws)
        assert client.post(f"{API}/sessions/{session['id']}/start").status_code == 200
    assert get_session(session["id"]).status == "running"


def test_start_control_markers_and_the_b_button(client):
    session, stimuli = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        live = started(client, ws, sid)
        assert live["status"] == "running" and live["started_at"]
        row = get_session(sid)
        assert row.status == "running" and row.device_id == DEVICE_ID and row.started_at is not None
        start = audit_entries(action="session_start")[0]
        assert start.user_name == "Ana Souza" and start.entity_label == "Rostos neutros e expressivos, P-015"
        assert [(c["label"], c["before"], c["after"]) for c in start.changes] == [
            ("Status", "Configurada", "Em andamento"), ("Óculos", None, "Quest Pro 01")]
        assert client.post(f"{API}/sessions/{sid}/prepare", json={"device_id": DEVICE_ID}).status_code == 409

        r = client.post(f"{API}/sessions/{sid}/control", json={"action": "next"})
        assert r.status_code == 202
        command = next(m for m in sync(ws) if m["type"] == "command")
        assert command == {"type": "command", "sessionId": sid, "commandId": r.json()["command_id"], "action": "next"}
        client.post(f"{API}/sessions/{sid}/control", json={"action": "goto", "position": 2})
        assert next(m for m in sync(ws) if m["type"] == "command")["position"] == 2
        assert client.post(f"{API}/sessions/{sid}/control", json={"action": "goto", "position": 3}).status_code == 422
        assert client.post(f"{API}/sessions/{sid}/control", json={"action": "goto"}).status_code == 422

        ws.send_json({"type": "state", "sessionId": sid, "state": "running", "t": 6.2, "position": 2,
                      "neutral": False, "paused": False, "shown": [1, 2], "lastCommandId": 2})
        sync(ws)
        playback = client.get(f"{API}/sessions/{sid}/live").json()["playback"]
        assert playback == {"position": 2, "neutral": False, "paused": False, "shown": [1, 2]}

        r = client.post(f"{API}/sessions/{sid}/markers", json={"text": "  Paciente   movimentou a cabeça "})
        assert r.status_code == 201
        assert r.json()["text"] == "Paciente movimentou a cabeça" and r.json()["t"] >= 0
        assert r.json()["created_by_name"] == "Ana Souza"
        assert [m["text"] for m in client.get(f"{API}/sessions/{sid}/markers").json()] == ["Paciente movimentou a cabeça"]
        assert client.post(f"{API}/sessions/{sid}/markers", json={"text": "  "}).status_code == 422

        ws.send_json({"type": "ended", "sessionId": sid, "reason": "button_b", "t": 12.0})
        sync(ws)

    row = get_session(sid)
    assert (row.status, row.end_reason) == ("awaiting_data", "button_b") and row.ended_at is not None
    end = audit_entries(action="session_end")[0]
    assert end.user_name == "Ana Souza" and end.user_agent == "NeuroSight/1.0.0 (Quest Pro 01; Quest Pro)"
    assert [(c["label"], c["after"]) for c in end.changes][:2] == [
        ("Status", "Aguardando dados"), ("Motivo do fim", "Botão B no óculos")]
    assert client.post(f"{API}/sessions/{sid}/control", json={"action": "next"}).status_code == 409
    assert client.post(f"{API}/sessions/{sid}/markers", json={"text": "tarde demais"}).status_code == 409


def test_control_needs_the_device_online(client):
    session, _ = new_session(client)
    with device(client) as (ws, _):
        started(client, ws, session["id"])
    r = client.post(f"{API}/sessions/{session['id']}/control", json={"action": "next"})
    assert r.status_code == 409 and "desconectado" in r.json()["detail"]
    live = client.get(f"{API}/sessions/{session['id']}/live").json()
    assert live["device"]["online"] is False and live["device"]["name"] == "Quest Pro 01"


def test_interrupt_ends_the_session_and_tells_the_device(client):
    session, _ = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        started(client, ws, sid)
        r = client.post(f"{API}/sessions/{sid}/interrupt")
        assert r.status_code == 200 and r.json()["status"] == "awaiting_data"
        assert {"type": "interrupt", "sessionId": sid} in sync(ws)
        # O óculos confirma o fim; a sessão já tinha acabado e nada muda.
        ws.send_json({"type": "ended", "sessionId": sid, "reason": "interrupted", "t": 3.0})
        sync(ws)
    row = get_session(sid)
    assert (row.status, row.end_reason) == ("awaiting_data", "interrupted")
    ends = audit_entries(action="session_end")
    assert len(ends) == 1 and ends[0].changes[1]["after"] == "Interrompida pelo pesquisador"


# ---- Quedas e reconexão ---------------------------------------------------------------------------

def test_reconnection_restores_the_running_session(client):
    session, _ = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        started(client, ws, sid)
    from app.services.live_hub import hub
    hub.reset()  # como se a API tivesse reiniciado
    playback = {"position": 1, "neutral": False, "paused": False, "shown": [1], "lastCommandId": 1}
    with device(client, state="running", sessionId=sid, playback=playback) as (ws, _):
        assert sync(ws) == []
        live = client.get(f"{API}/sessions/{sid}/live").json()
        assert live["device"]["online"] is True and live["playback"]["position"] == 1
        assert client.post(f"{API}/sessions/{sid}/control", json={"action": "next"}).status_code == 202


def test_device_back_without_the_session_ends_it_as_disconnected(client):
    session, _ = new_session(client)
    with device(client) as (ws, _):
        started(client, ws, session["id"])
    with device(client) as (ws, _):  # hello em idle: o app fechou no meio
        sync(ws)
    row = get_session(session["id"])
    assert (row.status, row.end_reason) == ("awaiting_data", "disconnected")


def test_session_interrupted_while_offline_is_interrupted_on_reconnect(client):
    session, _ = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        started(client, ws, sid)
    assert client.post(f"{API}/sessions/{sid}/interrupt").status_code == 200
    with device(client, state="running", sessionId=sid) as (ws, _):
        assert {"type": "interrupt", "sessionId": sid} in sync(ws)


def test_cancelled_preparation_unloads_on_reconnect(client):
    session, _ = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        prepared(client, ws, sid)
    client.post(f"{API}/sessions/{sid}/release")
    with device(client, state="ready", sessionId=sid, load={"loaded": 2, "total": 2}) as (ws, _):
        assert {"type": "unload", "sessionId": sid} in sync(ws)


# ---- Envio dos dados ------------------------------------------------------------------------------

def test_upload_tracking_frames_and_complete(client):
    session, _ = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        started(client, ws, sid)
        ws.send_json({"type": "ended", "sessionId": sid, "reason": "button_b", "t": 9.0})
        sync(ws)

    url = f"{API}/device/sessions/{sid}"
    names = ["000001.jpg", "000002.jpg"]
    assert client.post(f"{url}/complete", headers=dev_headers()).status_code == 409  # falta o JSON
    r = client.put(f"{url}/tracking", content=b"{nao json", headers=dev_headers())
    assert r.status_code == 422
    r = client.put(f"{url}/tracking", content=json.dumps({"version": 2, "meta": {"sessionId": "outra"}}),
                   headers=dev_headers())
    assert r.status_code == 422
    r = client.put(f"{url}/tracking", content=json.dumps(tracking(sid, names)), headers=dev_headers("outro-oculos"))
    assert r.status_code == 403
    r = client.put(f"{url}/tracking", content=json.dumps(tracking(sid, names)), headers=dev_headers())
    assert r.status_code == 200 and r.json()["status"] == "awaiting_data"
    assert os.path.isfile(storage.session_tracking(sid))

    files = [("frames", ("000001.jpg", jpeg(), "image/jpeg")), ("frames", ("x.png", b"\x89PNG", "image/png"))]
    r = client.post(f"{url}/frames", files=files, headers=dev_headers())
    assert r.json() == {"saved": ["000001.jpg"], "rejected": ["x.png"], "receivedCount": 1}
    assert client.get(f"{url}/frames", headers=dev_headers()).json() == {"received": ["000001.jpg"]}
    r = client.post(f"{url}/complete", headers=dev_headers())
    assert r.json() == {"status": "awaiting_data", "missingFrames": ["000002.jpg"]}
    assert get_session(sid).data_received_at is None

    client.post(f"{url}/frames", files=[("frames", ("000002.jpg", jpeg(), "image/jpeg"))], headers=dev_headers())
    r = client.post(f"{url}/complete", headers=dev_headers())
    assert r.json() == {"status": "awaiting_data", "missingFrames": []}
    assert get_session(sid).data_received_at is not None


def test_tracking_without_ended_closes_the_session(client):
    session, _ = new_session(client)
    sid = session["id"]
    with device(client) as (ws, _):
        started(client, ws, sid)
    r = client.put(f"{API}/device/sessions/{sid}/tracking", content=json.dumps(tracking(sid)), headers=dev_headers())
    assert r.status_code == 200 and r.json()["status"] == "awaiting_data"
    assert get_session(sid).end_reason == "button_b"


def test_no_upload_before_the_session_runs(client):
    session, _ = new_session(client)
    r = client.put(f"{API}/device/sessions/{session['id']}/tracking", content=json.dumps(tracking(session["id"])),
                   headers=dev_headers())
    assert r.status_code == 403  # nenhum óculos executou a sessão ainda


# ---- WebSocket do site ----------------------------------------------------------------------------

def test_browser_socket_follows_the_session(client):
    session, _ = new_session(client)
    sid = session["id"]
    with client.websocket_connect(f"{API}/sessions/{sid}/live") as browser:
        first = browser.receive_json()
        assert first["type"] == "live" and first["device"] is None and first["nearby"] == []
        with device(client) as (ws, _):
            assert [d["name"] for d in browser.receive_json()["nearby"]] == ["Quest Pro 01"]
            prepared(client, ws, sid, loaded=False)
            snapshot = browser.receive_json()
            while snapshot["device"] is None:
                snapshot = browser.receive_json()
            assert snapshot["device"]["name"] == "Quest Pro 01" and snapshot["load"]["loaded"] == 0


def test_browser_socket_needs_login_and_visibility(client):
    session, _ = new_session(client)
    client.cookies.clear()
    with client.websocket_connect(f"{API}/sessions/{session['id']}/live") as browser:
        with pytest.raises(WebSocketDisconnect) as closed:
            browser.receive_json()
        assert closed.value.code == 4401
    make_user("Bruno Castro", BRUNO, "researcher")
    login(client, BRUNO)
    with client.websocket_connect(f"{API}/sessions/{session['id']}/live") as browser:
        with pytest.raises(WebSocketDisconnect) as closed:
            browser.receive_json()
        assert closed.value.code == 4404
    login(client, ANA)
