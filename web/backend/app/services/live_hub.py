"""Hub da execução ao vivo: quais óculos estão conectados, com que código de pareamento, qual sessão
cada um carregou e o que está na tela dele, e quem acompanha cada sessão pelo site.

Fica só em memória, por isso a API roda com um worker (decisão 1 do plano). Se a API reiniciar, o
óculos reconecta e o `hello` dele traz o estado de volta (docs/protocolo-oculos.md).

As rotas REST rodam no threadpool e os WebSockets no event loop: tudo aqui é protegido por um lock,
e o envio só enfileira a mensagem na conexão, que a manda pelo próprio loop. Ninguém espera a rede.
"""
import asyncio
import itertools
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

Message = dict[str, Any]
CLOSE = "__close__"


class Connection:
    """Um WebSocket aberto (do óculos ou do navegador), com a fila de saída no loop dele."""

    _ids = itertools.count(1)

    def __init__(self, loop: asyncio.AbstractEventLoop, ip: str | None):
        self.id = next(self._ids)
        self.loop = loop
        self.ip = ip
        self.queue: asyncio.Queue = asyncio.Queue()

    def send(self, message: Message) -> None:
        """Enfileira a mensagem; vale de qualquer thread."""
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, message)
        except RuntimeError:  # loop já encerrado: a conexão caiu
            pass

    def close(self, code: int, reason: str = "") -> None:
        self.send({CLOSE: code, "reason": reason})


@dataclass
class DeviceLive:
    id: str
    name: str
    model: str | None
    app_version: str | None
    ip: str | None
    tracking: dict[str, str]
    state: str = "idle"
    session_id: str | None = None
    pairing_code: str | None = None
    connection: Connection | None = None
    connected_at: float = field(default_factory=time.monotonic)

    @property
    def online(self) -> bool:
        return self.connection is not None


@dataclass
class SessionLive:
    id: str
    status: str
    total: int
    started_at: datetime | None = None
    device_id: str | None = None
    device_name: str | None = None
    paired_by: str | None = None  # network | code
    loaded: int = 0
    load_error: dict[str, str] | None = None
    position: int | None = None
    neutral: bool = True
    paused: bool = False
    shown: list[int] = field(default_factory=list)
    command_seq: int = 0
    # Cresce a cada mudança (em microssegundos, para continuar crescendo se a API reiniciar): o site
    # fica com o retrato mais novo quando a resposta de uma rota chega depois do WebSocket.
    version: int = 0
    viewers: dict[int, Connection] = field(default_factory=dict)

    def touch(self) -> None:
        self.version = max(self.version + 1, time.time_ns() // 1000)

    def reset_load(self) -> None:
        self.loaded, self.load_error = 0, None

    def reset_playback(self) -> None:
        self.position, self.neutral, self.paused, self.shown = None, True, False, []


class LiveHub:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.devices: dict[str, DeviceLive] = {}
        self.sessions: dict[str, SessionLive] = {}
        # Último código de cada óculos, para devolver o mesmo numa reconexão.
        self._last_codes: dict[str, str] = {}

    def reset(self) -> None:
        """Esquece tudo (testes)."""
        with self._lock:
            self.devices.clear()
            self.sessions.clear()
            self._last_codes.clear()

    # ---- Óculos -------------------------------------------------------------------------------

    def _new_code(self, device_id: str) -> str:
        in_use = {d.pairing_code for d in self.devices.values() if d.online and d.id != device_id}
        previous = self._last_codes.get(device_id)
        if previous and previous not in in_use:
            return previous
        while True:
            code = f"{random.randint(1000, 9999)}"
            if code not in in_use:
                return code

    def connect_device(self, conn: Connection, hello: Message) -> tuple[DeviceLive, Connection | None]:
        """Registra o óculos como online e dá o código de pareamento. Devolve a conexão anterior do
        mesmo óculos, se houver, para ser fechada."""
        with self._lock:
            device_id = hello["deviceId"]
            old = self.devices.get(device_id)
            replaced = old.connection if old and old.connection is not conn else None
            device = DeviceLive(
                id=device_id, name=hello["name"], model=hello.get("model"), app_version=hello.get("appVersion"),
                ip=conn.ip, tracking=dict(hello.get("tracking") or {}), state=hello.get("state") or "idle",
                session_id=hello.get("sessionId"), connection=conn,
            )
            device.pairing_code = self._new_code(device_id)
            self._last_codes[device_id] = device.pairing_code
            self.devices[device_id] = device
            self._notify_device_sessions(device_id)
            return device, replaced

    def disconnect_device(self, device_id: str, conn: Connection) -> None:
        with self._lock:
            device = self.devices.get(device_id)
            if device is None or device.connection is not conn:
                return  # já foi substituída por outra conexão
            device.connection = None
            self._notify_device_sessions(device_id)
            # Óculos offline e sem sessão não aparece em lugar nenhum.
            if not any(s.device_id == device_id for s in self.sessions.values()):
                del self.devices[device_id]

    def device(self, device_id: str) -> DeviceLive | None:
        with self._lock:
            return self.devices.get(device_id)

    def online_device(self, device_id: str) -> DeviceLive | None:
        device = self.device(device_id)
        return device if device and device.online else None

    def by_code(self, code: str) -> DeviceLive | None:
        with self._lock:
            return next((d for d in self.devices.values() if d.online and d.pairing_code == code), None)

    def nearby(self, ip: str | None) -> list[DeviceLive]:
        """Óculos online com o mesmo IP público e livres (sem sessão em andamento), do mais recente."""
        with self._lock:
            found = [d for d in self.devices.values() if d.online and d.ip == ip and not self._busy(d.id)]
            return sorted(found, key=lambda d: d.connected_at, reverse=True)

    def _busy(self, device_id: str) -> bool:
        return any(s.device_id == device_id and s.status == "running" for s in self.sessions.values())

    def busy_with(self, device_id: str) -> str | None:
        """A sessão em andamento neste óculos, se houver."""
        with self._lock:
            return next((s.id for s in self.sessions.values()
                         if s.device_id == device_id and s.status == "running"), None)

    def update_device(self, device_id: str, **fields: Any) -> None:
        with self._lock:
            device = self.devices.get(device_id)
            if device is None:
                return
            for key, value in fields.items():
                setattr(device, key, value)
            self._notify_device_sessions(device_id)

    def send_device(self, device_id: str, message: Message) -> bool:
        """Manda ao óculos se ele estiver online."""
        with self._lock:
            device = self.devices.get(device_id)
            if device is None or device.connection is None:
                return False
            device.connection.send(message)
            return True

    # ---- Sessões ------------------------------------------------------------------------------

    def session(self, session_id: str, status: str, total: int, started_at: datetime | None = None,
                device_id: str | None = None, device_name: str | None = None) -> SessionLive:
        """A sessão no hub, criada a partir do banco quando ainda não está aqui. O status vem sempre
        do banco, que é quem manda nele (a ingestão dos dados o muda e só depois avisa o hub)."""
        with self._lock:
            live = self.sessions.get(session_id)
            if live is None:
                live = SessionLive(id=session_id, status=status, total=total, started_at=started_at,
                                   device_id=device_id, device_name=device_name)
                live.touch()
                self.sessions[session_id] = live
            elif (live.status, live.total) != (status, total):
                live.status, live.total = status, total
                live.started_at = started_at or live.started_at
                live.touch()
            return live

    def get_session(self, session_id: str) -> SessionLive | None:
        with self._lock:
            return self.sessions.get(session_id)

    def bind(self, session_id: str, device: DeviceLive, paired_by: str) -> list[tuple[str, str]]:
        """Vincula o óculos à sessão (W14). Devolve os vínculos desfeitos, (óculos, sessão), para
        mandar o `unload`."""
        with self._lock:
            live = self.sessions[session_id]
            dropped: list[tuple[str, str]] = []
            if live.device_id and live.device_id != device.id:
                dropped.append((live.device_id, session_id))
                self._forget_device(live.device_id)
            for other in self.sessions.values():
                if other.id != session_id and other.device_id == device.id:
                    dropped.append((device.id, other.id))
                    other.device_id, other.device_name, other.paired_by = None, None, None
                    other.reset_load()
                    self._broadcast(other)
            live.device_id, live.device_name, live.paired_by = device.id, device.name, paired_by
            live.reset_load()
            live.reset_playback()
            device.session_id, device.state = session_id, "loading"
            self._broadcast(live)
            return dropped

    def release(self, session_id: str) -> str | None:
        """Desfaz o vínculo (Cancelar na W14) e devolve o óculos que estava vinculado."""
        with self._lock:
            live = self.sessions.get(session_id)
            if live is None or live.device_id is None:
                return None
            device_id = live.device_id
            live.device_id, live.device_name, live.paired_by = None, None, None
            live.reset_load()
            self._forget_device(device_id)
            self._broadcast(live)
            return device_id

    def _forget_device(self, device_id: str) -> None:
        device = self.devices.get(device_id)
        if device is None:
            return
        if device.online:
            device.session_id, device.state = None, "idle"
        else:
            del self.devices[device_id]

    def restore(self, session_id: str, device: DeviceLive, paired_by: str, loaded: int | None,
                playback: Message | None) -> None:
        """Refaz o vínculo a partir do `hello` de um óculos que reconectou."""
        with self._lock:
            live = self.sessions[session_id]
            live.device_id, live.device_name = device.id, device.name
            live.paired_by = live.paired_by or paired_by
            if loaded is not None:
                live.loaded = max(0, min(loaded, live.total))
            if playback:
                self._apply_playback(live, playback)
            self._broadcast(live)

    def set_status(self, session_id: str, status: str, started_at: datetime | None = None) -> None:
        with self._lock:
            live = self.sessions.get(session_id)
            if live is None:
                return
            live.status = status
            if started_at is not None:
                live.started_at = started_at
            if status == "running":
                live.reset_playback()
            if status not in ("configured", "running") and live.device_id:
                # Acabou: o óculos fica livre para outra sessão assim que terminar de enviar.
                device = self.devices.get(live.device_id)
                if device is not None and device.session_id == session_id and device.state in ("running", "ready"):
                    device.state = "uploading"
            self._broadcast(live)

    def next_command_id(self, session_id: str) -> int:
        with self._lock:
            live = self.sessions[session_id]
            live.command_seq += 1
            return live.command_seq

    def load_progress(self, session_id: str, device_id: str, loaded: int, total: int | None = None) -> None:
        with self._lock:
            live = self.sessions.get(session_id)
            if live is None or live.device_id != device_id:
                return
            live.loaded = max(0, min(loaded, live.total))
            live.load_error = None
            device = self.devices.get(device_id)
            if device is not None:
                device.state = "ready" if live.loaded >= live.total else "loading"
            self._broadcast(live)

    def load_failed(self, session_id: str, device_id: str, stimulus_id: str, message: str) -> None:
        with self._lock:
            live = self.sessions.get(session_id)
            if live is None or live.device_id != device_id:
                return
            live.load_error = {"stimulus_id": stimulus_id, "message": message}
            self._broadcast(live)

    def playback(self, session_id: str, device_id: str, state: Message) -> None:
        with self._lock:
            live = self.sessions.get(session_id)
            if live is None or live.device_id != device_id:
                return
            self._apply_playback(live, state)
            self._broadcast(live)

    @staticmethod
    def _apply_playback(live: SessionLive, state: Message) -> None:
        position = state.get("position")
        live.position = position if isinstance(position, int) and 1 <= position <= live.total else None
        live.neutral = bool(state.get("neutral", live.position is None))
        live.paused = bool(state.get("paused", False))
        shown = state.get("shown") or []
        live.shown = sorted({p for p in shown if isinstance(p, int) and 1 <= p <= live.total})

    # ---- Quem acompanha pelo site -------------------------------------------------------------

    def watch(self, session_id: str, conn: Connection) -> None:
        with self._lock:
            live = self.sessions[session_id]
            live.viewers[conn.id] = conn
            conn.send(self._snapshot(live, conn.ip))

    def unwatch(self, session_id: str, conn: Connection) -> None:
        with self._lock:
            live = self.sessions.get(session_id)
            if live is not None:
                live.viewers.pop(conn.id, None)

    def snapshot(self, session_id: str, viewer_ip: str | None) -> Message:
        with self._lock:
            return self._snapshot(self.sessions[session_id], viewer_ip)

    def _notify_device_sessions(self, device_id: str) -> None:
        """Avisa quem acompanha as sessões que mostram este óculos (vinculado ou por perto)."""
        for live in self.sessions.values():
            if live.device_id == device_id or live.device_id is None:
                self._broadcast(live)

    def _broadcast(self, live: SessionLive) -> None:
        """A sessão mudou: nova versão e o retrato para quem acompanha."""
        live.touch()
        for conn in list(live.viewers.values()):
            conn.send(self._snapshot(live, conn.ip))

    def _snapshot(self, live: SessionLive, viewer_ip: str | None) -> Message:
        device = self.devices.get(live.device_id) if live.device_id else None
        device_info = None
        if live.device_id:
            device_info = {
                "id": live.device_id,
                "name": device.name if device else live.device_name,
                "online": bool(device and device.online),
                "pairing_code": device.pairing_code if device and device.online else None,
                "same_network": bool(device and device.ip and device.ip == viewer_ip),
                "paired_by": live.paired_by,
                "state": device.state if device and device.online else "offline",
                "tracking": dict(device.tracking) if device and device.online else {},
            }
        nearby = []
        if live.device_id is None and live.status == "configured":
            nearby = [
                {"id": d.id, "name": d.name, "pairing_code": d.pairing_code}
                for d in sorted(self.devices.values(), key=lambda d: d.connected_at, reverse=True)
                if d.online and d.ip == viewer_ip and not self._busy(d.id)
            ]
        return {
            "type": "live",
            "version": live.version,
            "session_id": live.id,
            "status": live.status,
            "started_at": live.started_at.isoformat() if live.started_at else None,
            "device": device_info,
            "nearby": nearby,
            "load": {"loaded": live.loaded, "total": live.total, "error": live.load_error},
            "playback": {"position": live.position, "neutral": live.neutral, "paused": live.paused,
                         "shown": list(live.shown)},
        }


hub = LiveHub()
