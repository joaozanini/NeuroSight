"""Simulador do óculos: faz o papel do app do Meta Quest Pro até a Fase 7, seguindo o protocolo de
docs/protocolo-oculos.md.

Conecta no WebSocket do servidor, mostra o nome e o código de pareamento (Q01), baixa os estímulos
quando o site prepara a sessão (Q02, com cache por sha256), obedece aos comandos da W15 com as
mesmas regras do óculos (troca automática das imagens, vídeo que avança ao terminar, tela neutra,
pausa) e gera olhar e expressões sintéticos. A reprodução e a geração ficam em
web/backend/app/synthetic.py (o seed usa o mesmo gerador nas sessões de exemplo). As fixações têm
posição e duração conhecidas e podem ser gravadas num arquivo (--truth) para conferir a análise. O B
é o Enter (ou --auto-end); depois dele o simulador envia o JSON v2 e a gravação (Q04) e volta a
aguardar, e o servidor processa os dados. Um envio que falhar fica guardado e é retomado na próxima
execução.

Uso (com o venv do backend, que já tem websockets, requests, numpy e OpenCV):

    cd web/backend
    .venv/bin/python ../scripts/device_simulator.py --server http://localhost:8000
    .venv/bin/python ../scripts/device_simulator.py --auto-end 60 --once --truth verdade.json
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

# O gerador de olhar, expressões e gravação fica no pacote da API (app/synthetic.py), que o seed
# também usa para as sessões de exemplo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.synthetic import Recording  # noqa: E402

APP_VERSION = "0.5.0-sim"
FRAME_BATCH = 20


def say(text: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


def fmt_bytes(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            text = f"{size:.0f}" if unit == "B" or size >= 10 else f"{size:.1f}"
            return f"{text.replace('.', ',')} {unit}"
        size /= 1024
    return ""


# ---- Cache dos estímulos -----------------------------------------------------------------------------

class StimulusCache:
    def __init__(self, folder: Path):
        self.folder = folder / "stimuli"
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, stim: dict) -> Path:
        return self.folder / f"{stim['sha256']}.{stim['format']}"

    def has(self, stim: dict) -> bool:
        return self.path(stim).is_file()

    def download(self, http: requests.Session, base: str, stim: dict) -> None:
        target = self.path(stim)
        partial = target.with_suffix(".partial")
        for attempt in range(3):
            digest = hashlib.sha256()
            with http.get(base + stim["url"], stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(partial, "wb") as out:
                    for chunk in r.iter_content(1 << 16):
                        digest.update(chunk)
                        out.write(chunk)
            if digest.hexdigest() == stim["sha256"]:
                os.replace(partial, target)
                return
            say(f"  sha256 não confere em {stim['name']} (tentativa {attempt + 1})")
        partial.unlink(missing_ok=True)
        raise RuntimeError("sha256 não confere")


# ---- O óculos --------------------------------------------------------------------------------------

class Device:
    def __init__(self, args):
        self.args = args
        self.base = args.server.rstrip("/")
        self.api = self.base + "/api/v1"
        self.ws_url = self.api.replace("http", "ws", 1) + "/device/ws"
        self.home = Path(args.data_dir).expanduser()
        self.home.mkdir(parents=True, exist_ok=True)
        self.cache = StimulusCache(self.home)
        self.headers = {"X-Device-Id": args.device_id}
        if args.key:
            self.headers["X-Device-Key"] = args.key
        self.http = requests.Session()
        self.http.headers.update(self.headers)

        self.lock = threading.RLock()
        self.ws = None
        self.send_lock = threading.Lock()
        self.state = "idle"
        self.session: dict | None = None
        self.loaded = 0
        self.load_token = 0
        self.recording: Recording | None = None
        self.pending_out: list[dict] = []  # mensagens que não saíram com a rede fora
        self.stop = threading.Event()
        self.sessions_done = 0

    @property
    def info(self) -> dict:
        return {"id": self.args.device_id, "name": self.args.name, "model": "Quest Pro"}

    def tracking(self) -> dict:
        return {"eye": self.args.eye, "face": "off" if self.args.no_face else self.args.face}

    # -- rede

    def send(self, message: dict) -> None:
        with self.send_lock:
            if self.ws is None:
                if message["type"] in ("ended", "state"):
                    self.pending_out = [m for m in self.pending_out if m["type"] != "state"] + [message]
                return
            try:
                self.ws.send(json.dumps(message))
            except ConnectionClosed:
                if message["type"] in ("ended", "state"):
                    self.pending_out.append(message)

    def hello(self) -> dict:
        message = {"type": "hello", "protocol": 1, "deviceId": self.args.device_id, "name": self.args.name,
                   "model": "Quest Pro", "appVersion": APP_VERSION, "tracking": self.tracking(), "state": self.state}
        if self.session and self.state != "idle":
            message["sessionId"] = self.session["id"]
            message["load"] = {"loaded": self.loaded, "total": len(self.session["stimuli"])}
            if self.recording:
                state = self.recording.state()
                message["playback"] = {k: state[k] for k in ("position", "neutral", "paused", "shown", "lastCommandId")}
        return message

    def run(self) -> None:
        threading.Thread(target=self._heartbeat, daemon=True).start()
        threading.Thread(target=self._resume_uploads, daemon=True).start()
        delay = 1
        while not self.stop.is_set():
            try:
                headers = {k: v for k, v in self.headers.items()}
                with connect(self.ws_url, additional_headers=headers, open_timeout=10) as ws:
                    ws.send(json.dumps(self.hello()))
                    with self.send_lock:
                        self.ws = ws
                    delay = 1
                    for raw in ws:
                        self._on_message(json.loads(raw))
            except InvalidStatus as e:
                say(f"O servidor recusou a conexão ({e.response.status_code}).")
            except ConnectionClosed as e:
                code = e.rcvd.code if e.rcvd else None
                if code == 4401:
                    say("Chave do dispositivo inválida (use --key ou QUESTPRO_DEVICE_KEY).")
                    self.stop.set()
                    break
                say(f"Conexão encerrada ({code or 'sem código'}).")
            except OSError as e:
                say(f"Sem conexão com {self.base} ({e.strerror or e}).")
            finally:
                with self.send_lock:
                    self.ws = None
            if self.stop.wait(delay):
                break
            if delay > 1:
                say(f"Reconectando em {delay} s...")
            delay = min(delay * 2, 30)

    def _heartbeat(self) -> None:
        last_ping = 0.0
        while not self.stop.wait(0.05):
            rec = self.recording
            if rec is not None and self.state == "running":
                rec.advance()
            if time.monotonic() - last_ping >= 15:
                last_ping = time.monotonic()
                self.send({"type": "ping"})

    # -- mensagens do servidor

    def _on_message(self, message: dict) -> None:
        kind = message.get("type")
        if kind == "welcome":
            self._q01(message["pairingCode"])
            with self.send_lock:
                pending, self.pending_out = self.pending_out, []
            for m in pending:
                self.send(m)
        elif kind == "load":
            self._load(message["session"])
        elif kind == "unload":
            with self.lock:
                if self.session and self.session["id"] == message.get("sessionId") and self.state in ("loading", "ready"):
                    self.load_token += 1
                    self.session, self.state = None, "idle"
                    say("Preparação cancelada no site. Aguardando sessão.")
        elif kind == "start":
            self._start(message)
        elif kind == "command":
            rec = self.recording
            if rec and message.get("sessionId") == rec.session["id"] and self.state == "running":
                rec.command(message)
        elif kind == "interrupt":
            if self.recording and message.get("sessionId") == self.recording.session["id"]:
                say("O pesquisador interrompeu a sessão.")
                self.end("interrupted")
        elif kind == "error":
            say(f"Erro do servidor: {message.get('message')}")

    def _q01(self, code: str) -> None:
        tracking = self.tracking()
        labels = {"active": "Ativo", "no_permission": "Sem permissão", "unavailable": "Indisponível", "off": "Desligado"}
        if self.state == "idle":
            say("● Aguardando sessão: pronto para receber a sessão")
            say("  No sistema web, abra a preparação da sessão e escolha este óculos.")
        say(f"  Nome do óculos: {self.args.name}   Código de pareamento: {code}")
        say(f"  Servidor: {self.base}   Eye tracking: {labels[tracking['eye']]}   "
            f"Rastreamento facial: {labels[tracking['face']]}")

    def _load(self, session: dict) -> None:
        with self.lock:
            if self.state in ("running", "uploading"):
                return
            self.load_token += 1
            token = self.load_token
            self.session, self.state = session, "loading"
        total = len(session["stimuli"])
        say(f"● Recebendo sessão: {session['title']}, paciente {session['patientCode']}")
        threading.Thread(target=self._download, args=(session, token, total), daemon=True).start()

    def _download(self, session: dict, token: int, total: int) -> None:
        stimuli = session["stimuli"]
        # Conta pelo cache: dois estímulos com o mesmo arquivo (mesmo sha256) chegam juntos.
        loaded = sum(1 for s in stimuli if self.cache.has(s))
        self.loaded = loaded
        self.send({"type": "load_progress", "sessionId": session["id"], "loaded": loaded, "total": total})
        for stim in stimuli:
            if token != self.load_token:
                return
            if self.cache.has(stim):
                continue
            try:
                if self.args.load_delay:
                    time.sleep(self.args.load_delay)
                self.cache.download(self.http, self.base, stim)
            except Exception as e:  # noqa: BLE001 - qualquer falha vira load_failed
                say(f"  Não foi possível carregar {stim['name']}: {e}")
                self.send({"type": "load_failed", "sessionId": session["id"], "stimulusId": stim["stimulusId"],
                           "message": str(e)[:200]})
                return
            loaded = sum(1 for s in stimuli if self.cache.has(s))
            self.loaded = loaded
            self.send({"type": "load_progress", "sessionId": session["id"], "loaded": loaded, "total": total})
            say(f"  Estímulos no óculos: {loaded} de {total}")
        if token == self.load_token:
            with self.lock:
                self.state = "ready"
            say("Carregamento completo: só a sala neutra até o início da sessão.")

    def _start(self, message: dict) -> None:
        with self.lock:
            if not self.session or self.session["id"] != message.get("sessionId") or self.state != "ready":
                return
            folder = self.home / "pending" / self.session["id"]
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True)
            self.recording = Recording(self.session, self.cache.path, folder, seed=self.args.seed,
                                       frame_fps=self.args.frame_fps, face=not self.args.no_face,
                                       on_change=self._send_state, log=say)
            self.state = "running"
        say("● Sessão iniciada: coletando olhar e expressões (tela neutra até o primeiro estímulo).")
        say("  Aperte Enter para simular o botão B." if not self.args.auto_end else
            f"  O B será apertado sozinho em {self.args.auto_end:g} s.")
        self._send_state(self.recording)
        if self.args.auto_end:
            threading.Timer(self.args.auto_end, self.end, args=("button_b",)).start()

    def _send_state(self, rec: Recording) -> None:
        self.send(rec.state())

    def end(self, reason: str) -> None:
        with self.lock:
            rec = self.recording
            if rec is None or self.state != "running":
                return
            self.state = "uploading"
        rec.end(reason)
        self.send({"type": "ended", "sessionId": rec.session["id"], "reason": reason, "t": round(rec.ended_t, 3)})
        say("● Sessão encerrada " + ("pelo botão B." if reason == "button_b" else "pelo pesquisador."))
        doc = rec.document(self.info, APP_VERSION)
        (rec.folder / "tracking.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        if self.args.truth:
            Path(self.args.truth).write_text(json.dumps(rec.truth(), indent=2, ensure_ascii=False), encoding="utf-8")
            say(f"  Fixações geradas gravadas em {self.args.truth}")
        threading.Thread(target=self._upload_and_finish, args=(rec.session, rec.folder), daemon=True).start()

    # -- envio (Q04)

    def _upload_and_finish(self, session: dict, folder: Path) -> None:
        say(f"● Enviando os dados: {session['title']}, {session['patientCode']}")
        while not self.stop.is_set():
            if self.upload(session["id"], folder):
                break
            say("  Envio falhou; tentando de novo em 10 s (os dados ficam guardados no aparelho).")
            if self.stop.wait(10):
                return
        with self.lock:
            self.recording, self.session, self.state = None, None, "idle"
        self.send({"type": "status", "state": "idle", "tracking": self.tracking()})
        self.sessions_done += 1
        say("Envio concluído. Aguardando a próxima sessão.")
        if self.args.once:
            self.stop.set()
            with self.send_lock:
                if self.ws is not None:
                    self.ws.close()

    def upload(self, session_id: str, folder: Path) -> bool:
        url = f"{self.api}/device/sessions/{session_id}"
        try:
            body = (folder / "tracking.json").read_bytes()
            r = self.http.put(f"{url}/tracking", data=body, headers={"Content-Type": "application/json"}, timeout=120)
            if r.status_code in (403, 404, 409, 422):
                say(f"  O servidor recusou o JSON ({r.status_code}: {r.json().get('detail')}). Descartando.")
                shutil.rmtree(folder, ignore_errors=True)
                return True
            r.raise_for_status()
            say(f"  Dados de rastreamento (JSON), {fmt_bytes(len(body))}: enviado")
            frames_dir = folder / "frames"
            names = sorted(p.name for p in frames_dir.glob("*.jpg")) if frames_dir.is_dir() else []
            for _ in range(3):
                received = set(self.http.get(f"{url}/frames", timeout=30).json()["received"])
                todo = [n for n in names if n not in received]
                total_size = sum((frames_dir / n).stat().st_size for n in names) or 1
                sent_size = sum((frames_dir / n).stat().st_size for n in names if n in received)
                for i in range(0, len(todo), FRAME_BATCH):
                    batch = todo[i:i + FRAME_BATCH]
                    files = [("frames", (n, (frames_dir / n).read_bytes(), "image/jpeg")) for n in batch]
                    self.http.post(f"{url}/frames", files=files, timeout=120).raise_for_status()
                    sent_size += sum((frames_dir / n).stat().st_size for n in batch)
                    say(f"  Gravação da sessão, {fmt_bytes(total_size)}: {round(100 * sent_size / total_size)}%")
                done = self.http.post(f"{url}/complete", timeout=60)
                done.raise_for_status()
                if not done.json()["missingFrames"]:
                    shutil.rmtree(folder, ignore_errors=True)
                    return True
            return False
        except (requests.RequestException, OSError, ValueError) as e:
            say(f"  Erro no envio: {e}")
            return False

    def _resume_uploads(self) -> None:
        """Envios que ficaram pendentes de uma execução anterior."""
        pending = self.home / "pending"
        if not pending.is_dir():
            return
        for folder in sorted(pending.iterdir()):
            if (folder / "tracking.json").is_file() and (self.recording is None or folder != self.recording.folder):
                say(f"Retomando o envio pendente da sessão {folder.name}.")
                while not self.stop.is_set() and not self.upload(folder.name, folder):
                    self.stop.wait(10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador do óculos NeuroSight (docs/protocolo-oculos.md).")
    parser.add_argument("--server", default=os.environ.get("NEUROSIGHT_SERVER", "http://localhost:8000"),
                        help="endereço da API (padrão: http://localhost:8000)")
    parser.add_argument("--key", default=os.environ.get("QUESTPRO_DEVICE_KEY", ""), help="chave do dispositivo")
    parser.add_argument("--device-id", default="simulador-01", help="id estável do óculos")
    parser.add_argument("--name", default="Quest Pro 01", help="nome que aparece no site")
    parser.add_argument("--eye", default="active", choices=["active", "no_permission", "unavailable", "off"])
    parser.add_argument("--face", default="active", choices=["active", "no_permission", "unavailable", "off"])
    parser.add_argument("--no-face", action="store_true", help="sem rastreamento facial (face = null)")
    parser.add_argument("--auto-end", type=float, default=0, metavar="S", help="aperta o B S segundos depois do início")
    parser.add_argument("--once", action="store_true", help="sai depois de enviar uma sessão")
    parser.add_argument("--frame-fps", type=float, default=10, help="quadros por segundo gravados (no máximo o pedido)")
    parser.add_argument("--load-delay", type=float, default=0, metavar="S", help="espera antes de cada download")
    parser.add_argument("--seed", default="neurosight", help="semente do olhar sintético")
    parser.add_argument("--truth", metavar="ARQUIVO", help="grava as fixações geradas (para conferir a análise)")
    parser.add_argument("--data-dir", default="~/.neurosight-simulador", help="cache dos estímulos e envios pendentes")
    args = parser.parse_args()

    device = Device(args)
    threading.Thread(target=device.run, daemon=True).start()
    try:
        while not device.stop.is_set():
            if args.auto_end or not sys.stdin.isatty():
                device.stop.wait(0.5)
                continue
            line = sys.stdin.readline()
            if not line:
                device.stop.wait(0.5)
                continue
            if device.state == "running":
                device.end("button_b")
            else:
                say("O B só vale durante a sessão.")
    except KeyboardInterrupt:
        say("Encerrando o simulador.")
        device.stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
