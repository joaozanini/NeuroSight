"""Dados coletados das sessões de exemplo (`python -m app.seed --demo`).

Cada sessão de exemplo Concluída ou Interrompida roda um roteiro no relógio virtual do gerador do
simulador (app/synthetic.py): a tela neutra do começo, os estímulos na ordem (as imagens com tempo e
os vídeos trocam sozinhos; as de troca manual ficam de 6 a 10 s na tela), a tela neutra do fim e o
B, ou a interrupção pelo pesquisador lá pela metade da sequência. O JSON v2 e a gravação passam pela
mesma ingestão das sessões de verdade (services/ingestion.py), que monta o MP4, analisa e fecha o
status. Algumas sessões ganham marcações, como na W16.

A gravação sai em 640 × 400 a 10 fps, para o seed não demorar (a das sessões de verdade segue as
variáveis QUESTPRO_CAPTURE_*).
"""
import json
import random
import shutil
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from .models import Session, SessionMarker
from .services import execution, ingestion
from .services.storage import storage
from .synthetic import Recording, VirtualClock, play

DEMO_CAPTURE = {"width": 640, "height": 400, "fps": 10, "jpegQuality": 75}
DEMO_DEVICE = {"id": "quest-pro-exemplo", "name": "Quest Pro 01", "model": "Quest Pro"}
DEMO_APP_VERSION = "1.0.0"
# Marcações por sequência (W16, W17), em segundos desde o início da sessão.
DEMO_MARKERS = {
    "rostos": [(28.0, "Paciente movimentou a cabeça"), (65.0, "Equipe de enfermagem entrou no quarto")],
    "paisagens": [(21.0, "Paciente pediu para ajustar o óculos")],
}


def script(stimuli: list[dict], rng: random.Random, interrupt: bool) -> list[tuple[float, str]]:
    """Os comandos da W15 no tempo: só os "Próximo" das trocas manuais e o fim (B ou interrupção)."""
    t = rng.uniform(3, 6)
    steps: list[tuple[float, str]] = [(t, "next")]
    stop_at = max(1, round(len(stimuli) * 0.6)) if interrupt else None
    for stim in stimuli:
        if stim["kind"] == "video":
            length, manual = stim.get("mediaSeconds") or 5.0, False
        elif stim.get("screenSeconds"):
            length, manual = stim["screenSeconds"], False
        else:
            length, manual = rng.uniform(6, 10), True
        if stim["position"] == stop_at:
            return steps + [(t + length * rng.uniform(0.4, 0.7), "interrupted")]
        t += length
        if manual:
            steps.append((t, "next"))
    return steps + [(t + rng.uniform(2, 4), "button_b")]


def generate(db: DbSession, session: Session, sequence: str) -> bool:
    """Gera e processa os dados de uma sessão de exemplo já executada. Devolve False se não deu."""
    final = session.status
    if final not in ("completed", "interrupted") or session.started_at is None:
        return False
    problem = execution.device_problem(session)
    if problem:
        print(f"  {session.title}, {session.patient.code}: sem dados de exemplo ({problem}).")
        return False

    message = execution.load_message(session)["session"]
    message["capture"] = DEMO_CAPTURE
    folder = Path(storage.session_dir(session.id))
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    clock = VirtualClock()
    recording = Recording(
        message, lambda stim: storage.stimulus_device(stim["stimulusId"], stim["format"]), folder,
        seed="exemplo", frame_fps=DEMO_CAPTURE["fps"], clock=clock, started_at=session.started_at,
    )
    play(recording, clock, script(message["stimuli"], random.Random(session.id), final == "interrupted"))
    doc = recording.document(DEMO_DEVICE, DEMO_APP_VERSION)
    (folder / "tracking.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")

    duration = recording.ended_t
    session.status, session.end_reason = "awaiting_data", recording.end_reason
    session.ended_at = session.started_at + timedelta(seconds=duration)
    session.data_received_at = session.ended_at + timedelta(seconds=40)
    for t, text in DEMO_MARKERS.get(sequence, []):
        if t < duration - 1:
            db.add(SessionMarker(session_id=session.id, t=t, text=text, created_by_id=session.owner_id,
                                 created_at=session.started_at + timedelta(seconds=t)))
    db.commit()
    return ingestion.process(session.id)
