"""Ponta a ponta com o simulador do óculos de verdade (web/scripts/device_simulator.py), como pede o
"pronto quando" da Fase 5: a API sobe num uvicorn de teste, o simulador conecta como óculos, o site
prepara, inicia e avança, o B automático encerra, e a sessão vira Concluída com as métricas da W17
batendo com o que o simulador gerou (--truth). Leva uns 15 s.
"""
import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn

from app.config import settings
from app.services import ingestion

from .accounts import PASSWORD, make_user
from .test_live import ready_stimulus
from .test_sessions import ANA, make_patient

SIMULATOR = Path(__file__).resolve().parents[2] / "scripts" / "device_simulator.py"


@pytest.fixture
def server(client, monkeypatch):
    """A API num uvicorn de verdade (o simulador fala WebSocket e HTTP pela rede). O `client`
    garante o banco migrado; o lifespan não roda de novo."""
    from app.main import app

    monkeypatch.setattr(settings, "capture_width", 320)
    monkeypatch.setattr(settings, "capture_height", 320)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not srv.started:
        assert time.monotonic() < deadline, "o uvicorn de teste não subiu"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(10)


def wait_for(check, timeout, message):
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        assert time.monotonic() < deadline, message
        time.sleep(0.1)


def test_simulator_session_ends_completed_with_matching_metrics(server, tmp_path):
    api = f"{server}/api/v1"
    make_user("Ana Souza", ANA, role="researcher")
    site = requests.Session()
    assert site.post(f"{api}/auth/login", json={"email": ANA, "password": PASSWORD}).status_code == 200
    stimuli = [ready_stimulus("Rosto neutro 01"), ready_stimulus("Rosto alegre 02")]
    r = site.post(f"{api}/sessions", json={
        "patient_id": make_patient(), "title": "Rostos neutros e expressivos", "objective": "Teste ponta a ponta.",
        "record": True, "stimuli": [{"stimulus_id": sid, "duration_seconds": 3} for sid in stimuli],
    })
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    truth_file, log_file = tmp_path / "verdade.json", tmp_path / "simulador.log"
    with open(log_file, "w") as log:
        simulator = subprocess.Popen(
            [sys.executable, str(SIMULATOR), "--server", server, "--device-id", "simulador-teste", "--auto-end", "9",
             "--once", "--frame-fps", "5", "--truth", str(truth_file), "--data-dir", str(tmp_path / "oculos")],
            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        )
        try:
            device = wait_for(lambda: site.get(f"{api}/devices/nearby").json(), 15, "o simulador não apareceu na rede")
            assert device[0]["name"] == "Quest Pro 01"
            assert site.post(f"{api}/sessions/{sid}/prepare", json={"device_id": "simulador-teste"}).status_code == 200
            wait_for(lambda: site.get(f"{api}/sessions/{sid}/live").json()["load"]["loaded"] == 2, 15,
                     "o simulador não carregou os estímulos")
            assert site.post(f"{api}/sessions/{sid}/start").status_code == 200
            time.sleep(1)
            assert site.post(f"{api}/sessions/{sid}/control", json={"action": "next"}).status_code == 202
            simulator.wait(60)  # o B sai aos 9 s; depois o envio e o --once
        finally:
            if simulator.poll() is None:
                simulator.kill()
    ingestion.drain()
    assert simulator.returncode == 0, log_file.read_text()

    session = site.get(f"{api}/sessions/{sid}").json()
    assert (session["status"], session["end_reason"], session["data_status"]) == ("completed", "button_b", "ready")
    assert [e["position"] for e in session["exposures"]] == [1, 2]
    analysis = site.get(f"{api}/sessions/{sid}/analysis").json()
    truth = json.loads(truth_file.read_text())
    assert len(analysis["exposures"]) == len(truth["exposures"]) == 2
    for exposure, expected in zip(analysis["exposures"], truth["exposures"]):
        assert exposure["on_t"] == pytest.approx(expected["on"], abs=1e-3)
        assert exposure["off_t"] == pytest.approx(expected["off"], abs=1e-3)
        assert (exposure["samples"], exposure["valid_samples"]) == (expected["samples"], expected["validSamples"])
        long = [f for f in expected["fixations"] if f["duration"] >= 0.1]
        assert len(long) - 1 <= exposure["fixation_count"] <= len(long)
        assert exposure["first_fixation_ms"] == pytest.approx(1000 * (long[0]["start"] - expected["on"]), abs=30)
    assert analysis["recording_status"] == "ready" and analysis["recording"]["fps"] == 5
