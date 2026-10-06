"""Execução ao vivo pelo site (W14, W15): achar o óculos, preparar, iniciar, controlar, interromper,
marcar e acompanhar pelo WebSocket da sessão.

Quem vê a sessão pode acompanhar (`GET`/`WS /live`, marcações); preparar, iniciar, controlar,
interromper e marcar exigem "Criar e executar sessões" e ser o responsável, como na W12 e na W16.
O óculos recebe só intenções; quem decide o que aparece na tela é ele (docs/protocolo-oculos.md).
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db import SessionLocal, get_db
from ..models import Device, Session, SessionMarker, User, utcnow
from ..schemas.live import (
    ControlRequest, ControlSent, LiveSnapshot, Marker, MarkerCreate, NearbyDevice, PrepareRequest,
)
from ..security import CurrentUser, require_permission, websocket_user
from ..services import audit, execution
from ..services import sessions as rules
from ..services.live_hub import CLOSE, Connection, hub
from .sessions import NOT_FOUND, Access, _get

router = APIRouter()
logger = logging.getLogger(__name__)

RunSessions = require_permission("sessions.run")

NOT_RESPONSIBLE = "só o responsável pela sessão pode executá-la"
DEVICE_OFFLINE = "o óculos está desconectado. Confira se o app está aberto e na rede"


def _runnable(db: DbSession, session_id: str, me: User) -> Session:
    access = Access(db, me)
    session = _get(db, session_id, access)
    if session.owner_id != me.id:
        raise HTTPException(status_code=403, detail=NOT_RESPONSIBLE)
    return session


def _require_status(session: Session, status: str) -> None:
    if session.status == status:
        return
    if status == "configured":
        raise HTTPException(status_code=409, detail="esta sessão já foi iniciada")
    raise HTTPException(status_code=409, detail="esta sessão não está em andamento")


def _snapshot(session: Session, request: Request) -> dict:
    execution.live_session(session)
    return hub.snapshot(session.id, audit.client_ip(request))


@router.get("/devices/nearby", response_model=list[NearbyDevice])
def nearby_devices(request: Request, me: User = Depends(RunSessions)):
    """Óculos conectados na mesma rede do navegador (mesmo IP público) e livres."""
    return [NearbyDevice(id=d.id, name=d.name, pairing_code=d.pairing_code)
            for d in hub.nearby(audit.client_ip(request))]


@router.get("/sessions/{session_id}/live", response_model=LiveSnapshot)
def live_snapshot(session_id: str, request: Request, user: CurrentUser, db: DbSession = Depends(get_db)):
    return _snapshot(_get(db, session_id, Access(db, user)), request)


@router.post("/sessions/{session_id}/prepare", response_model=LiveSnapshot)
def prepare(session_id: str, body: PrepareRequest, request: Request, me: User = Depends(RunSessions),
            db: DbSession = Depends(get_db)):
    """W14: vincula o óculos à sessão e manda o `load` para ele baixar os estímulos."""
    session = _runnable(db, session_id, me)
    _require_status(session, "configured")
    problem = execution.device_problem(session)
    if problem:
        raise HTTPException(status_code=409, detail=problem)

    ip = audit.client_ip(request)
    if body.pairing_code:
        device = hub.by_code(body.pairing_code)
        if device is None:
            raise HTTPException(status_code=404, detail=f"nenhum óculos conectado com o código {body.pairing_code}")
        paired_by = "code"
    else:
        device = hub.online_device(body.device_id or "")
        if device is None or device.ip != ip:
            raise HTTPException(status_code=404, detail="este óculos não está mais na rede")
        paired_by = "network"
    busy = hub.busy_with(device.id)
    if busy and busy != session.id:
        raise HTTPException(status_code=409, detail="este óculos está executando outra sessão")

    execution.live_session(session)
    for device_id, other_id in hub.bind(session.id, device, paired_by):
        hub.send_device(device_id, {"type": "unload", "sessionId": other_id})
    hub.send_device(device.id, execution.load_message(session))
    logger.info("sessão %s vinculada ao óculos %s (%s) por %s", session.id, device.name, paired_by, me.email)
    return hub.snapshot(session.id, ip)


@router.post("/sessions/{session_id}/release", response_model=LiveSnapshot)
def release(session_id: str, request: Request, me: User = Depends(RunSessions), db: DbSession = Depends(get_db)):
    """"Cancelar" da W14: o óculos volta para a tela inicial."""
    session = _runnable(db, session_id, me)
    _require_status(session, "configured")
    execution.live_session(session)
    device_id = hub.release(session.id)
    if device_id:
        hub.send_device(device_id, {"type": "unload", "sessionId": session.id})
    return _snapshot(session, request)


@router.post("/sessions/{session_id}/start", response_model=LiveSnapshot)
def start(session_id: str, request: Request, me: User = Depends(RunSessions), db: DbSession = Depends(get_db)):
    """"Iniciar sessão" (W14): Configurada → Em andamento, e o óculos começa a coletar."""
    session = _runnable(db, session_id, me)
    _require_status(session, "configured")
    live = execution.live_session(session)
    device = hub.online_device(live.device_id) if live.device_id else None
    if device is None:
        raise HTTPException(status_code=409, detail=DEVICE_OFFLINE if live.device_id else "escolha o óculos antes de iniciar")
    if live.loaded < live.total:
        raise HTTPException(status_code=409, detail="o óculos ainda está carregando os estímulos")
    if device.tracking.get("eye") != "active":
        raise HTTPException(status_code=409, detail="o eye tracking do óculos não está ativo")

    row = db.get(Device, device.id)
    if row is None:  # o hello grava a linha; sem ela o óculos não chegou a se registrar
        raise HTTPException(status_code=409, detail=DEVICE_OFFLINE)
    started_at = execution.start(db, request, me, session, row)
    db.commit()
    hub.set_status(session.id, "running", started_at)
    hub.update_device(device.id, state="running")
    hub.send_device(device.id, {"type": "start", "sessionId": session.id,
                                "startedAt": started_at.isoformat().replace("+00:00", "Z")})
    logger.info("sessão %s iniciada por %s no óculos %s", session.id, me.email, device.name)
    return hub.snapshot(session.id, audit.client_ip(request))


@router.post("/sessions/{session_id}/control", response_model=ControlSent, status_code=202)
def control(session_id: str, body: ControlRequest, me: User = Depends(RunSessions), db: DbSession = Depends(get_db)):
    """Anterior, Tela neutra, Pausar/Retomar vídeo, Próximo estímulo e o clique na sequência (W15)."""
    session = _runnable(db, session_id, me)
    _require_status(session, "running")
    if body.action == "goto" and body.position > len(session.items):
        raise HTTPException(status_code=422, detail="esse estímulo não está na sequência")
    live = execution.live_session(session)
    if not live.device_id or hub.online_device(live.device_id) is None:
        raise HTTPException(status_code=409, detail=DEVICE_OFFLINE)
    command_id = hub.next_command_id(session.id)
    message = {"type": "command", "sessionId": session.id, "commandId": command_id, "action": body.action}
    if body.action == "goto":
        message["position"] = body.position
    hub.send_device(live.device_id, message)
    return ControlSent(command_id=command_id)


@router.post("/sessions/{session_id}/interrupt", response_model=LiveSnapshot)
def interrupt(session_id: str, request: Request, me: User = Depends(RunSessions), db: DbSession = Depends(get_db)):
    """"Interromper sessão" (W15): a coleta para e o óculos envia o que já coletou."""
    session = _runnable(db, session_id, me)
    _require_status(session, "running")
    live = execution.live_session(session)
    execution.end(db, request, me, session, "interrupted")
    db.commit()
    execution.announce_end(session)
    # Se o óculos estiver fora do ar, o interrupt vai quando ele reconectar (o hello dele diz running).
    if live.device_id:
        hub.send_device(live.device_id, {"type": "interrupt", "sessionId": session.id})
    return hub.snapshot(session.id, audit.client_ip(request))


# ---- Marcações ------------------------------------------------------------------------------

def _marker(m: SessionMarker, names: dict[str, str]) -> Marker:
    return Marker(id=m.id, t=m.t, text=m.text, created_at=m.created_at,
                  created_by_name=names.get(m.created_by_id) if m.created_by_id else None)


@router.get("/sessions/{session_id}/markers", response_model=list[Marker])
def list_markers(session_id: str, user: CurrentUser, db: DbSession = Depends(get_db)):
    session = _get(db, session_id, Access(db, user))
    markers = db.scalars(select(SessionMarker).where(SessionMarker.session_id == session.id)
                         .order_by(SessionMarker.t, SessionMarker.id)).all()
    ids = {m.created_by_id for m in markers if m.created_by_id}
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    return [_marker(m, names) for m in markers]


@router.post("/sessions/{session_id}/markers", response_model=Marker, status_code=201)
def create_marker(session_id: str, body: MarkerCreate, me: User = Depends(RunSessions),
                  db: DbSession = Depends(get_db)):
    """"Marcar" (W15): o tempo é o da sessão, contado no servidor desde o início."""
    session = _runnable(db, session_id, me)
    _require_status(session, "running")
    t = max(0.0, (utcnow() - session.started_at).total_seconds()) if session.started_at else 0.0
    marker = SessionMarker(session_id=session.id, t=round(t, 3), text=body.text, created_by_id=me.id)
    db.add(marker)
    db.commit()
    return _marker(marker, {me.id: me.name})


# ---- WebSocket do site ----------------------------------------------------------------------

def _watchable(session_id: str, websocket: WebSocket) -> tuple[str | None, int | None]:
    """Confere o login e se a pessoa vê a sessão; devolve o erro (motivo, código) ou prepara o hub."""
    with SessionLocal() as db:
        user = websocket_user(websocket, db)
        if user is None:
            return "não autenticado", 4401
        session = db.get(Session, session_id)
        if session is None or not rules.can_view(session, user, Access(db, user).all_sessions):
            return NOT_FOUND, 4404
        execution.live_session(session)
        return None, None


@router.websocket("/sessions/{session_id}/live")
async def watch_session(websocket: WebSocket, session_id: str):
    """O retrato da sessão (o mesmo do GET /live), mandado de novo a cada mudança."""
    await websocket.accept()
    reason, code = await run_in_threadpool(_watchable, session_id, websocket)
    if code:
        await websocket.close(code=code, reason=reason)
        return
    conn = Connection(asyncio.get_running_loop(), audit.client_ip(websocket))
    hub.watch(session_id, conn)
    sender = asyncio.create_task(_pump(websocket, conn))
    try:
        # O navegador não manda nada; o loop só percebe quando ele fecha.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unwatch(session_id, conn)
        sender.cancel()


async def _pump(websocket: WebSocket, conn: Connection) -> None:
    """Manda as mensagens enfileiradas para esta conexão, na ordem."""
    try:
        while True:
            message = await conn.queue.get()
            if CLOSE in message:
                await websocket.close(code=message[CLOSE], reason=message.get("reason", ""))
                return
            await websocket.send_json(message)
    except (WebSocketDisconnect, RuntimeError):
        pass
