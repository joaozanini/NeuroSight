"""Lado do óculos (docs/protocolo-oculos.md): o WebSocket permanente e as rotas HTTP para baixar os
estímulos e enviar os dados da sessão depois do B.

A chave é a QUESTPRO_DEVICE_KEY (cabeçalho X-Device-Key), e o óculos se identifica pelo X-Device-Id.
Os estímulos só descem para o óculos vinculado à sessão; os dados só sobem do óculos que a executou.
O JSON e os frames ficam em <media>/sessions/<id>/; validar o conteúdo e montar o MP4 é da Fase 5.
"""
import asyncio
import json
import logging
import os
import re
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..config import settings
from ..db import SessionLocal, get_db
from ..models import Device, Session, utcnow
from ..security import DeviceId, device_key_ok, valid_device_id
from ..services import audit, execution
from ..services.live_hub import CLOSE, Connection, DeviceLive, hub
from ..services.storage import storage

router = APIRouter()
logger = logging.getLogger(__name__)

HELLO_TIMEOUT = 10
SILENCE_TIMEOUT = 45
DEVICE_STATES = ("idle", "loading", "ready", "running", "uploading")
TRACKING_STATES = ("active", "no_permission", "unavailable", "off")
FRAME_NAME = re.compile(r"^\d{1,8}\.jpg$")
JPEG_MAGIC = b"\xff\xd8\xff"
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "mp4": "video/mp4"}


# ---- WebSocket --------------------------------------------------------------------------------

def _tracking(raw) -> dict[str, str]:
    raw = raw if isinstance(raw, dict) else {}
    return {key: raw[key] if raw.get(key) in TRACKING_STATES else "unavailable" for key in ("eye", "face")}


def _parse_hello(message) -> dict | None:
    if not isinstance(message, dict) or message.get("type") != "hello":
        return None
    device_id, name = message.get("deviceId"), message.get("name")
    if not valid_device_id(device_id) or not isinstance(name, str) or not name.strip():
        return None
    state = message.get("state") if message.get("state") in DEVICE_STATES else "idle"
    session_id = message.get("sessionId") if isinstance(message.get("sessionId"), str) else None
    return {
        "deviceId": device_id,
        "name": " ".join(name.split())[:80],
        "model": str(message.get("model") or "")[:80] or None,
        "appVersion": str(message.get("appVersion") or "")[:40] or None,
        "tracking": _tracking(message.get("tracking")),
        "state": state if session_id or state == "idle" else "idle",
        "sessionId": session_id if state != "idle" else None,
        "load": message.get("load") if isinstance(message.get("load"), dict) else None,
        "playback": message.get("playback") if isinstance(message.get("playback"), dict) else None,
    }


def _register(hello: dict, ip: str | None) -> None:
    with SessionLocal() as db:
        device = db.get(Device, hello["deviceId"]) or Device(id=hello["deviceId"])
        device.name, device.model, device.app_version = hello["name"], hello["model"], hello["appVersion"]
        device.last_ip, device.last_seen_at = ip, utcnow()
        db.add(device)
        db.commit()


def _seen(device_id: str) -> None:
    with SessionLocal() as db:
        device = db.get(Device, device_id)
        if device is not None:
            device.last_seen_at = utcnow()
            db.commit()


def _resume(device: DeviceLive, hello: dict, websocket: WebSocket) -> list[dict]:
    """Confere o estado que o óculos trouxe no hello com o banco e devolve o que mandar para ele.

    Refaz o vínculo depois de uma queda (ou de a API reiniciar), manda o `unload` de uma preparação
    que foi cancelada ou passou para outro óculos, o `interrupt` de uma sessão que acabou enquanto
    ele estava fora e encerra a sessão em andamento que o óculos perdeu (o app fechou no meio).
    """
    session_id, state = hello["sessionId"], hello["state"]
    with SessionLocal() as db:
        if session_id is None:
            # O óculos voltou sem sessão: a que estava em andamento nele se perdeu (o app fechou).
            session = db.scalar(select(Session).where(Session.device_id == device.id, Session.status == "running"))
        else:
            session = db.get(Session, session_id)
        if session is None:
            return [{"type": "unload", "sessionId": session_id}] if session_id else []

        known = hub.get_session(session.id)
        live = execution.live_session(session)
        if session.status == "running" and state != "running":
            if session.device_id == device.id and execution.end(
                    db, websocket, session.owner, session, "disconnected", execution.device_agent(session.device)):
                db.commit()
                execution.announce_end(session)
            return []
        if session.status == "configured":
            # Sem a sessão no hub, a API reiniciou: o vínculo volta. Se ela está no hub com outro
            # óculos (ou nenhum), a preparação foi cancelada ou passou para outro.
            if state not in ("loading", "ready") or (known is not None and known.device_id != device.id):
                return [{"type": "unload", "sessionId": session.id}]
            loaded = (hello["load"] or {}).get("loaded")
            hub.restore(session.id, device, "network", loaded if isinstance(loaded, int) else 0, None)
            return []
        if session.status == "running":
            if session.device_id != device.id:
                return [{"type": "interrupt", "sessionId": session.id}]
            hub.restore(session.id, device, "network", live.total, hello["playback"])
            return []
        # A sessão já acabou (interrompida pelo site enquanto o óculos estava fora, por exemplo).
        if state == "running":
            return [{"type": "interrupt", "sessionId": session.id}]
        return []


def _ended(device_id: str, session_id: str, reason: str, websocket: WebSocket) -> None:
    """O B (ou o fim depois de um interrupt): Em andamento → Aguardando dados."""
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        if session is None or session.device_id != device_id:
            return
        reason = reason if reason in execution.END_REASON_LABELS else "button_b"
        if execution.end(db, websocket, session.owner, session, reason, execution.device_agent(session.device)):
            db.commit()
            execution.announce_end(session)


async def _handle(device_id: str, message: dict, websocket: WebSocket, conn: Connection) -> None:
    kind = message.get("type")
    session_id = message.get("sessionId")
    if kind == "ping":
        conn.send({"type": "pong"})
    elif kind == "status":
        fields = {}
        if "tracking" in message:
            fields["tracking"] = _tracking(message.get("tracking"))
        if message.get("state") == "idle":
            fields.update(state="idle", session_id=None)
        hub.update_device(device_id, **fields)
    elif kind == "load_progress" and isinstance(session_id, str):
        loaded = message.get("loaded")
        if isinstance(loaded, int):
            hub.load_progress(session_id, device_id, loaded)
    elif kind == "load_failed" and isinstance(session_id, str):
        hub.load_failed(session_id, device_id, str(message.get("stimulusId") or ""),
                        str(message.get("message") or "falha ao carregar")[:200])
    elif kind == "state" and isinstance(session_id, str):
        hub.playback(session_id, device_id, message)
        if message.get("state") in DEVICE_STATES:
            hub.update_device(device_id, state=message["state"])
    elif kind == "ended" and isinstance(session_id, str):
        hub.update_device(device_id, state="uploading")
        await run_in_threadpool(_ended, device_id, session_id, str(message.get("reason") or ""), websocket)


@router.websocket("/device/ws")
async def device_socket(websocket: WebSocket):
    await websocket.accept()
    if not device_key_ok(websocket.headers.get("x-device-key")):
        await websocket.close(code=4401, reason="chave do dispositivo inválida")
        return
    try:
        hello = _parse_hello(await asyncio.wait_for(websocket.receive_json(), HELLO_TIMEOUT))
    except (asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        hello = None
    if hello is None:
        await websocket.close(code=4400, reason="hello inválido")
        return

    ip = audit.client_ip(websocket)
    conn = Connection(asyncio.get_running_loop(), ip)
    await run_in_threadpool(_register, hello, ip)
    device, replaced = hub.connect_device(conn, hello)
    if replaced is not None:
        replaced.close(4409, "substituído por outra conexão do mesmo óculos")
    sender = asyncio.create_task(_pump(websocket, conn))
    conn.send({"type": "welcome", "pairingCode": device.pairing_code,
               "serverTime": utcnow().isoformat().replace("+00:00", "Z")})
    for message in await run_in_threadpool(_resume, device, hello, websocket):
        conn.send(message)
    logger.info("óculos %s (%s) conectado de %s, código %s", device.name, device.id, ip, device.pairing_code)

    try:
        while not sender.done():
            try:
                message = await asyncio.wait_for(websocket.receive_json(), SILENCE_TIMEOUT)
            except asyncio.TimeoutError:
                await websocket.close(code=4408, reason="sem batimento")
                break
            except ValueError:  # texto que não é JSON
                conn.send({"type": "error", "code": "bad_message", "message": "mensagem não é JSON"})
                continue
            if isinstance(message, dict):
                try:
                    await _handle(device.id, message, websocket, conn)
                except Exception:  # uma mensagem ruim não derruba a conexão
                    logger.exception("óculos %s: erro ao tratar %s", device.id, message.get("type"))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sender.cancel()
        hub.disconnect_device(device.id, conn)
        await run_in_threadpool(_seen, device.id)
        logger.info("óculos %s (%s) desconectado", device.name, device.id)


async def _pump(websocket: WebSocket, conn: Connection) -> None:
    try:
        while True:
            message = await conn.queue.get()
            if CLOSE in message:
                await websocket.close(code=message[CLOSE], reason=message.get("reason", ""))
                return
            await websocket.send_json(message)
    except (WebSocketDisconnect, RuntimeError):
        pass


# ---- HTTP -------------------------------------------------------------------------------------

def _session(db: DbSession, session_id: str) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="sessão não encontrada")
    return session


def _executed_by(db: DbSession, session_id: str, device_id: str) -> Session:
    """Só o óculos que executou a sessão envia os dados dela, e só depois de ela começar."""
    session = _session(db, session_id)
    if session.device_id != device_id:
        raise HTTPException(status_code=403, detail="esta sessão não foi executada neste óculos")
    if session.status not in ("running", "awaiting_data"):
        raise HTTPException(status_code=409, detail="esta sessão não está esperando dados")
    return session


@router.get("/device/sessions/{session_id}/stimuli/{stimulus_id}")
def download_stimulus(session_id: str, stimulus_id: str, device_id: DeviceId, db: DbSession = Depends(get_db)):
    """A versão para o óculos de um estímulo da sessão (aceita Range)."""
    session = _session(db, session_id)
    live = hub.get_session(session.id)
    if device_id not in (session.device_id, live.device_id if live else None):
        raise HTTPException(status_code=403, detail="esta sessão não está vinculada a este óculos")
    item = next((i for i in session.items if i.stimulus_id == stimulus_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="estímulo não está na sessão")
    stimulus = item.stimulus
    path = storage.stimulus_device(stimulus.id, stimulus.device_format or stimulus.format)
    if stimulus.device_status != "ready" or not os.path.isfile(path):
        raise HTTPException(status_code=409, detail="a versão para o óculos ainda não está pronta")
    return FileResponse(path, media_type=MEDIA_TYPES.get(stimulus.device_format, "application/octet-stream"),
                        headers={"ETag": f'"{stimulus.device_sha256}"'})


def _check_upload(session_id: str, device_id: str) -> None:
    with SessionLocal() as db:
        _executed_by(db, session_id, device_id)


def _validate_tracking(path: str, session_id: str) -> dict:
    try:
        with open(path, "rb") as f:
            data = json.load(f)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="o corpo não é um JSON válido")
    if not isinstance(data, dict) or data.get("version") != 2 or not isinstance(data.get("meta"), dict):
        raise HTTPException(status_code=422, detail="o JSON não segue o contrato v2 (version e meta)")
    if data["meta"].get("sessionId") != session_id:
        raise HTTPException(status_code=422, detail="o meta.sessionId não é o desta sessão")
    return data


def _tracking_received(session_id: str, device_id: str, end_reason, request: Request) -> str:
    """Grava o fim, se o `ended` não chegou pelo WebSocket, e devolve o status da sessão."""
    with SessionLocal() as db:
        session = _executed_by(db, session_id, device_id)
        if session.status == "running":
            reason = end_reason if end_reason in ("button_b", "interrupted") else "disconnected"
            if execution.end(db, request, session.owner, session, reason, execution.device_agent(session.device)):
                db.commit()
                execution.announce_end(session)
        return session.status


@router.put("/device/sessions/{session_id}/tracking")
async def upload_tracking(session_id: str, request: Request, device_id: DeviceId):
    """O JSON v2 da sessão. Reenviar substitui o anterior."""
    await run_in_threadpool(_check_upload, session_id, device_id)
    limit = settings.max_tracking_mb * 1024 * 1024
    folder = storage.session_dir(session_id)
    os.makedirs(folder, exist_ok=True)
    final = storage.session_tracking(session_id)
    partial = final + ".partial"
    size = 0
    try:
        with open(partial, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"o JSON passa de {settings.max_tracking_mb} MB")
                out.write(chunk)
        data = await run_in_threadpool(_validate_tracking, partial, session_id)
        os.replace(partial, final)
    finally:
        if os.path.exists(partial):
            os.remove(partial)
    status = await run_in_threadpool(_tracking_received, session_id, device_id, data["meta"].get("endReason"), request)
    logger.info("sessão %s: JSON recebido (%d bytes)", session_id, size)
    return {"status": status, "sizeBytes": size}


def _received_frames(session_id: str) -> list[str]:
    folder = storage.session_frames_dir(session_id)
    if not os.path.isdir(folder):
        return []
    return sorted(name for name in os.listdir(folder) if FRAME_NAME.match(name))


@router.get("/device/sessions/{session_id}/frames")
def list_frames(session_id: str, device_id: DeviceId, db: DbSession = Depends(get_db)):
    _executed_by(db, session_id, device_id)
    return {"received": _received_frames(session_id)}


@router.post("/device/sessions/{session_id}/frames")
def upload_frames(session_id: str, device_id: DeviceId, frames: list[UploadFile] = File(...),
                  db: DbSession = Depends(get_db)):
    """Um lote de quadros JPEG da gravação. Reenviar um nome sobrescreve (retomada)."""
    _executed_by(db, session_id, device_id)
    folder = storage.session_frames_dir(session_id)
    os.makedirs(folder, exist_ok=True)
    saved, rejected = [], []
    for upload in frames:
        name = os.path.basename(upload.filename or "")
        head = upload.file.read(len(JPEG_MAGIC))
        if not FRAME_NAME.match(name) or head != JPEG_MAGIC:
            rejected.append(upload.filename or "?")
            continue
        with open(os.path.join(folder, name), "wb") as out:
            out.write(head)
            shutil.copyfileobj(upload.file, out, 1 << 20)
        saved.append(name)
    if rejected:
        logger.warning("sessão %s: %d quadro(s) recusado(s): %s", session_id, len(rejected), rejected[:5])
    return {"saved": saved, "rejected": rejected, "receivedCount": len(_received_frames(session_id))}


@router.post("/device/sessions/{session_id}/complete")
def complete_upload(session_id: str, device_id: DeviceId, db: DbSession = Depends(get_db)):
    """Fim do envio. Devolve os quadros listados no JSON que ainda não chegaram."""
    session = _executed_by(db, session_id, device_id)
    path = storage.session_tracking(session_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=409, detail="envie o JSON da sessão antes de concluir")
    with open(path, "rb") as f:
        frames = json.load(f).get("frames") or []
    received = set(_received_frames(session_id))
    expected = [str(fr.get("file")) for fr in frames if isinstance(fr, dict) and fr.get("file")]
    missing = [name for name in expected if os.path.basename(name) not in received]
    if missing:
        return {"status": session.status, "missingFrames": missing}
    if session.data_received_at is None:
        session.data_received_at = utcnow()
        db.commit()
        logger.info("sessão %s: envio completo (%d quadros)", session_id, len(received))
    hub.update_device(device_id, state="idle", session_id=None)
    return {"status": session.status, "missingFrames": []}
