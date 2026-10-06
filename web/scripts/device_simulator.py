"""Simulador do óculos: faz o papel do app do Meta Quest Pro até a Fase 7, seguindo o protocolo de
docs/protocolo-oculos.md.

Conecta no WebSocket do servidor, mostra o nome e o código de pareamento (Q01), baixa os estímulos
quando o site prepara a sessão (Q02, com cache por sha256), obedece aos comandos da W15 com as
mesmas regras do óculos (troca automática das imagens, vídeo que avança ao terminar, tela neutra,
pausa) e gera olhar e expressões sintéticos. As fixações têm posição e duração conhecidas e podem
ser gravadas num arquivo (--truth) para conferir a análise. O B é o Enter (ou --auto-end); depois
dele o simulador envia o JSON v2 e a gravação (Q04) e volta a aguardar. Um envio que falhar fica
guardado e é retomado na próxima execução.

Uso (com o venv do backend, que já tem websockets, requests, numpy e OpenCV):

    cd web/backend
    .venv/bin/python ../scripts/device_simulator.py --server http://localhost:8000
    .venv/bin/python ../scripts/device_simulator.py --auto-end 60 --once --truth verdade.json
"""
import argparse
import hashlib
import json
import math
import os
import random
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import requests
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

APP_VERSION = "0.4.0-sim"
GAZE_HZ = 72
FACE_HZ = 30
# Painel plano onde os estímulos aparecem (metros) e a distância dos olhos até ele.
PANEL = {"widthM": 2.4, "heightM": 1.35, "distanceM": 2.0}
# A câmera da gravação enquadra o painel com uma margem: ele ocupa 80% da largura do quadro.
PANEL_SHARE = 0.8
ROOM_BGR = (196, 192, 188)
FRAME_BATCH = 20

# XR_FB_face_tracking2, na ordem de XrFaceExpression2FB (docs/protocolo-oculos.md, seção 4.1).
FACE_EXPRESSIONS = """
BROW_LOWERER_L BROW_LOWERER_R CHEEK_PUFF_L CHEEK_PUFF_R CHEEK_RAISER_L CHEEK_RAISER_R
CHEEK_SUCK_L CHEEK_SUCK_R CHIN_RAISER_B CHIN_RAISER_T DIMPLER_L DIMPLER_R EYES_CLOSED_L
EYES_CLOSED_R EYES_LOOK_DOWN_L EYES_LOOK_DOWN_R EYES_LOOK_LEFT_L EYES_LOOK_LEFT_R
EYES_LOOK_RIGHT_L EYES_LOOK_RIGHT_R EYES_LOOK_UP_L EYES_LOOK_UP_R INNER_BROW_RAISER_L
INNER_BROW_RAISER_R JAW_DROP JAW_SIDEWAYS_LEFT JAW_SIDEWAYS_RIGHT JAW_THRUST LID_TIGHTENER_L
LID_TIGHTENER_R LIP_CORNER_DEPRESSOR_L LIP_CORNER_DEPRESSOR_R LIP_CORNER_PULLER_L
LIP_CORNER_PULLER_R LIP_FUNNELER_LB LIP_FUNNELER_LT LIP_FUNNELER_RB LIP_FUNNELER_RT
LIP_PRESSOR_L LIP_PRESSOR_R LIP_PUCKER_L LIP_PUCKER_R LIP_STRETCHER_L LIP_STRETCHER_R
LIP_SUCK_LB LIP_SUCK_LT LIP_SUCK_RB LIP_SUCK_RT LIP_TIGHTENER_L LIP_TIGHTENER_R LIPS_TOWARD
LOWER_LIP_DEPRESSOR_L LOWER_LIP_DEPRESSOR_R MOUTH_LEFT MOUTH_RIGHT NOSE_WRINKLER_L
NOSE_WRINKLER_R OUTER_BROW_RAISER_L OUTER_BROW_RAISER_R UPPER_LID_RAISER_L UPPER_LID_RAISER_R
UPPER_LIP_RAISER_L UPPER_LIP_RAISER_R TONGUE_TIP_INTERDENTAL TONGUE_TIP_ALVEOLAR
TONGUE_FRONT_DORSAL_PALATE TONGUE_MID_DORSAL_PALATE TONGUE_BACK_DORSAL_VELAR TONGUE_OUT
TONGUE_RETREAT
""".split()
assert len(FACE_EXPRESSIONS) == 70
# Expressões que reagem a cada estímulo (as da legenda padrão da W17).
REACTIVE = ["INNER_BROW_RAISER_L", "INNER_BROW_RAISER_R", "LIP_CORNER_PULLER_L", "LIP_CORNER_PULLER_R"]


def say(text: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {text}", flush=True)


def utc_iso(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fmt_bytes(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            text = f"{size:.0f}" if unit == "B" or size >= 10 else f"{size:.1f}"
            return f"{text.replace('.', ',')} {unit}"
        size /= 1024
    return ""


# ---- Geometria ------------------------------------------------------------------------------------

def contain(width: int, height: int) -> tuple[float, float, float, float]:
    """Retângulo do estímulo dentro do painel (UV do painel): inteiro, centralizado, com faixas."""
    panel_aspect = PANEL["widthM"] / PANEL["heightM"]
    aspect = width / height if height else panel_aspect
    if aspect >= panel_aspect:
        w, h = 1.0, panel_aspect / aspect
    else:
        w, h = aspect / panel_aspect, 1.0
    return (1 - w) / 2, (1 - h) / 2, w, h


def panel_in_frame(capture: dict) -> tuple[float, float, float, float]:
    """Retângulo do painel no quadro da gravação (UV do quadro)."""
    frame_w_m = PANEL["widthM"] / PANEL_SHARE
    frame_h_m = frame_w_m * capture["height"] / capture["width"]
    w, h = PANEL_SHARE, PANEL["heightM"] / frame_h_m
    return (1 - w) / 2, (1 - h) / 2, w, h


def capture_fov(capture: dict) -> float:
    half = PANEL["widthM"] / PANEL_SHARE / 2
    return round(math.degrees(2 * math.atan(half / PANEL["distanceM"])), 2)


# ---- Olhar sintético -------------------------------------------------------------------------------

class Scanpath:
    """Fixações de posição e duração conhecidas sobre um estímulo, a partir de quando ele aparece.

    Fixação de 200 a 600 ms num ponto sorteado, sacada de 30 ms até a próxima (sempre a mais de 6°)
    e, de vez em quando, um piscar de 150 ms no lugar da sacada (amostras inválidas).
    """

    def __init__(self, rng: random.Random, on_t: float):
        self.rng = rng
        self.on_t = on_t
        self.fixations: list[dict] = []
        self.gaps: list[tuple[float, float, bool]] = []  # (início, fim, piscando)
        self._end = on_t + rng.uniform(0.12, 0.25)  # latência até a 1ª fixação
        self.gaps.append((on_t, self._end, False))
        self._last = (0.5, 0.5)

    def _extend(self, t: float) -> None:
        while self._end <= t:
            while True:
                u, v = self.rng.uniform(0.12, 0.88), self.rng.uniform(0.12, 0.88)
                if math.dist((u, v), self._last) > 0.12:
                    break
            start = self._end
            end = start + self.rng.uniform(0.2, 0.6)
            self.fixations.append({"start": start, "end": end, "u": u, "v": v})
            blink = self.rng.random() < 0.12
            gap = 0.15 if blink else 0.03
            self.gaps.append((end, end + gap, blink))
            self._last, self._end = (u, v), end + gap

    def sample(self, t: float) -> tuple[bool, float, float]:
        """(válido, u, v) no instante t."""
        self._extend(t)
        for fix in reversed(self.fixations):
            if fix["start"] <= t < fix["end"]:
                return True, fix["u"] + self.rng.gauss(0, 0.002), fix["v"] + self.rng.gauss(0, 0.002)
            if fix["end"] <= t:
                break
        for start, end, blink in reversed(self.gaps):
            if start <= t < end:
                if blink:
                    return False, 0.0, 0.0
                before = self._fixation_ending(start) or {"u": 0.5, "v": 0.5}
                after = self._fixation_starting(end) or before
                k = (t - start) / (end - start)
                return True, before["u"] + (after["u"] - before["u"]) * k, before["v"] + (after["v"] - before["v"]) * k
        return True, 0.5, 0.5

    def _fixation_ending(self, t: float):
        return next((f for f in self.fixations if abs(f["end"] - t) < 1e-9), None)

    def _fixation_starting(self, t: float):
        self._extend(t + 0.001)
        return next((f for f in self.fixations if abs(f["start"] - t) < 1e-9), None)

    def truth(self, off_t: float) -> list[dict]:
        """As fixações que aconteceram até o estímulo sair, cortadas no instante da saída."""
        result = []
        for fix in self.fixations:
            if fix["start"] >= off_t:
                break
            end = min(fix["end"], off_t)
            result.append({"start": round(fix["start"], 4), "end": round(end, 4),
                           "duration": round(end - fix["start"], 4), "u": round(fix["u"], 4), "v": round(fix["v"], 4)})
        return result


# ---- A sessão em execução --------------------------------------------------------------------------

class Recording:
    """Uma sessão do óculos: a reprodução (o óculos é dono dela) e a coleta, até o B."""

    def __init__(self, session: dict, cache: "StimulusCache", args, folder: Path, send_state):
        self.session = session
        self.stimuli = session["stimuli"]
        self.cache = cache
        self.args = args
        self.folder = folder
        self.send_state = send_state
        self.rng = random.Random(f"{args.seed}:{session['id']}")
        self.capture = session["capture"]
        self.record = bool(session.get("record"))
        self.frame_fps = min(self.capture["fps"], args.frame_fps)
        self.panel_rect = panel_in_frame(self.capture)
        self.started_at = datetime.now(timezone.utc)
        self.t0 = time.monotonic()
        self.lock = threading.RLock()

        self.position: int | None = None
        self.neutral = True
        self.paused = False
        self.shown: list[int] = []
        self.last_command_id = 0
        self.on_t = 0.0
        self.video_pos = 0.0  # segundos de vídeo já tocados antes da última retomada
        self.play_t = 0.0
        self.scanpath: Scanpath | None = None
        self.exposures: list[dict] = []

        self.events: list[dict] = [{"t": 0.0, "type": "session_start"}, {"t": 0.0, "type": "neutral_on"}]
        self.gaze: list[dict] = []
        self.face_t: list[float] = []
        self.face_w: list[list[float]] = []
        self.face_c: list[list[float]] = []
        self.frames: list[dict] = []
        self.gaze_k = self.face_k = self.frame_k = 0
        self.end_reason: str | None = None
        self.ended_t: float | None = None
        self._images: dict[int, np.ndarray] = {}
        self._videos: dict[int, cv2.VideoCapture] = {}
        if self.record:
            (folder / "frames").mkdir(parents=True, exist_ok=True)

    def now(self) -> float:
        return time.monotonic() - self.t0

    # -- tela

    def _current(self) -> dict | None:
        return None if self.neutral or self.position is None else self.stimuli[self.position - 1]

    def _deadline(self) -> float | None:
        stim = self._current()
        if stim is None:
            return None
        if stim["kind"] == "image":
            return self.on_t + stim["screenSeconds"] if stim.get("screenSeconds") else None
        if self.paused or not stim.get("mediaSeconds"):
            return None
        return self.play_t + (stim["mediaSeconds"] - self.video_pos)

    def _off(self, t: float) -> None:
        stim = self._current()
        if stim is not None:
            self.events.append({"t": round(t, 4), "type": "stimulus_off", "position": self.position,
                                "stimulusId": stim["stimulusId"]})
            self.exposures[-1]["off"] = round(t, 4)
            self.exposures[-1]["fixations"] = self.scanpath.truth(t)
            self.scanpath = None
        elif self.neutral:
            self.events.append({"t": round(t, 4), "type": "neutral_off"})

    def _show(self, position: int, t: float, cause: str) -> None:
        self._off(t)
        stim = self.stimuli[position - 1]
        self.position, self.neutral, self.paused = position, False, False
        self.on_t = self.play_t = t
        self.video_pos = 0.0
        if position not in self.shown:
            self.shown.append(position)
        self.events.append({"t": round(t, 4), "type": "stimulus_on", "position": position,
                            "stimulusId": stim["stimulusId"], "cause": cause})
        self.scanpath = Scanpath(self.rng, t)
        self.exposures.append({"position": position, "stimulusId": stim["stimulusId"], "name": stim["name"],
                               "on": round(t, 4), "off": None, "fixations": []})
        say(f"Em exibição: {position}. {stim['name']}")

    def _neutral_on(self, t: float, why: str = "") -> None:
        if self.neutral:
            return
        self._off(t)
        self.neutral, self.paused = True, False
        self.events.append({"t": round(t, 4), "type": "neutral_on"})
        say(f"Tela neutra{why}")

    def _auto_next(self, t: float) -> None:
        if self.position is not None and self.position < len(self.stimuli):
            self._show(self.position + 1, t, "auto")
        else:
            self._neutral_on(t, " (fim da sequência; aguardando o B)")

    def advance(self) -> None:
        """Leva a coleta até agora, aplicando as trocas automáticas no instante exato."""
        with self.lock:
            if self.ended_t is not None:
                return
            t = self.now()
            changed = False
            while (deadline := self._deadline()) is not None and deadline <= t:
                self._collect(deadline)
                self._auto_next(deadline)
                changed = True
            self._collect(t)
            if changed:
                self.send_state(self)

    def command(self, message: dict) -> None:
        with self.lock:
            if self.ended_t is not None:
                return
            t = self.now()
            while (deadline := self._deadline()) is not None and deadline <= t:
                self._collect(deadline)
                self._auto_next(deadline)
            self._collect(t)
            action, total = message.get("action"), len(self.stimuli)
            self.last_command_id = message.get("commandId", self.last_command_id)
            if action == "next":
                if self.position is None:
                    self._show(1, t, "command")
                elif self.position < total:
                    self._show(self.position + 1, t, "command")
                else:
                    self._neutral_on(t, " (fim da sequência; aguardando o B)")
            elif action == "previous" and self.position and self.position > 1:
                self._show(self.position - 1, t, "command")
            elif action == "goto" and isinstance(message.get("position"), int) and 1 <= message["position"] <= total:
                self._show(message["position"], t, "command")
            elif action == "neutral":
                self._neutral_on(t)
            elif action == "pause":
                stim = self._current()
                if stim and stim["kind"] == "video" and not self.paused:
                    self.video_pos += t - self.play_t
                    self.paused = True
                    self.events.append({"t": round(t, 4), "type": "video_pause", "position": self.position})
                    say("Vídeo pausado")
            elif action == "resume" and self.paused:
                self.paused, self.play_t = False, t
                self.events.append({"t": round(t, 4), "type": "video_resume", "position": self.position})
                say("Vídeo retomado")
            self.send_state(self)

    def end(self, reason: str) -> None:
        with self.lock:
            if self.ended_t is not None:
                return
            self.advance()
            t = self.now()
            self._collect(t)
            if self._current() is not None:
                self._off(t)
            self.events.append({"t": round(t, 4), "type": "session_end", "reason": reason})
            self.end_reason, self.ended_t = reason, t
            for video in self._videos.values():
                video.release()

    # -- coleta

    def _collect(self, t: float) -> None:
        while (self.gaze_k / GAZE_HZ) <= t:
            self._gaze_sample(self.gaze_k / GAZE_HZ)
            self.gaze_k += 1
        if not self.args.no_face:
            while (self.face_k / FACE_HZ) <= t:
                self._face_sample(self.face_k / FACE_HZ)
                self.face_k += 1
        if self.record:
            while (self.frame_k / self.frame_fps) <= t:
                self._frame(self.frame_k / self.frame_fps)
                self.frame_k += 1

    def _frame_uv(self, pu: float, pv: float) -> list[float] | None:
        if not self.record:
            return None
        x, y, w, h = self.panel_rect
        return [round(x + pu * w, 4), round(y + pv * h, 4)]

    def _gaze_sample(self, t: float) -> None:
        stim = self._current()
        if stim is None or self.scanpath is None:
            # Tela neutra: o olhar passeia devagar perto do centro do painel.
            pu = 0.5 + 0.15 * math.sin(t * 0.7) + self.rng.gauss(0, 0.003)
            pv = 0.5 + 0.1 * math.cos(t * 0.5) + self.rng.gauss(0, 0.003)
            self.gaze.append({"t": round(t, 4), "valid": True, "conf": 1.0, "onStim": False, "stimUv": None,
                              "frameUv": self._frame_uv(pu, pv)})
            return
        valid, u, v = self.scanpath.sample(t)
        if not valid:
            self.gaze.append({"t": round(t, 4), "valid": False, "conf": 0.0, "onStim": False, "stimUv": None,
                              "frameUv": None})
            return
        sx, sy, sw, sh = contain(stim["width"], stim["height"])
        self.gaze.append({"t": round(t, 4), "valid": True, "conf": 1.0, "onStim": True,
                          "stimUv": [round(u, 4), round(v, 4)], "frameUv": self._frame_uv(sx + u * sw, sy + v * sh)})

    def _face_sample(self, t: float) -> None:
        weights = [max(0.0, min(1.0, 0.03 + 0.02 * math.sin(t * (1 + i % 7) * 0.3 + i))) for i in range(70)]
        stim = self._current()
        if stim is not None:
            # Cada estímulo provoca uma reação que sobe e desce nos primeiros segundos.
            since = t - self.on_t
            bump = math.exp(-((since - 1.5) ** 2) / 0.8)
            for name in REACTIVE[(self.position % 2) * 2:(self.position % 2) * 2 + 2]:
                weights[FACE_EXPRESSIONS.index(name)] = round(min(1.0, weights[FACE_EXPRESSIONS.index(name)] + 0.7 * bump), 4)
        if self.gaze and not self.gaze[-1]["valid"]:  # piscando
            for name in ("EYES_CLOSED_L", "EYES_CLOSED_R"):
                weights[FACE_EXPRESSIONS.index(name)] = 0.95
        self.face_t.append(round(t, 4))
        self.face_w.append([round(w, 4) for w in weights])
        self.face_c.append([0.97, 0.95])

    def _frame(self, t: float) -> None:
        width, height = self.capture["width"], self.capture["height"]
        img = np.full((height, width, 3), ROOM_BGR, dtype=np.uint8)
        stim = self._current()
        if stim is not None:
            x, y, w, h = self.panel_rect
            px, py, pw, ph = int(x * width), int(y * height), int(w * width), int(h * height)
            img[py:py + ph, px:px + pw] = 0
            content = self._stimulus_frame(stim, t)
            if content is not None:
                sx, sy, sw, sh = contain(stim["width"], stim["height"])
                rw, rh = max(1, int(sw * pw)), max(1, int(sh * ph))
                ox, oy = px + int(sx * pw), py + int(sy * ph)
                img[oy:oy + rh, ox:ox + rw] = cv2.resize(content, (rw, rh), interpolation=cv2.INTER_AREA)
        name = f"{len(self.frames) + 1:06d}.jpg"
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(self.capture.get("jpegQuality", 80))])
        if ok:
            (self.folder / "frames" / name).write_bytes(buf.tobytes())
            self.frames.append({"idx": len(self.frames) + 1, "t": round(t, 4), "file": name})

    def _stimulus_frame(self, stim: dict, t: float) -> np.ndarray | None:
        position = stim["position"]
        path = str(self.cache.path(stim))
        if stim["kind"] == "image":
            if position not in self._images:
                self._images[position] = cv2.imread(path)
            return self._images[position]
        video = self._videos.get(position)
        if video is None:
            video = self._videos[position] = cv2.VideoCapture(path)
        playhead = self.video_pos + (0 if self.paused else t - self.play_t)
        video.set(cv2.CAP_PROP_POS_MSEC, max(0.0, playhead) * 1000)
        ok, frame = video.read()
        return frame if ok else None

    # -- JSON v2

    def document(self, device: dict) -> dict:
        return {
            "version": 2,
            "meta": {
                "sessionId": self.session["id"],
                "device": device,
                "appVersion": APP_VERSION,
                "startedAt": utc_iso(self.started_at),
                "endedAt": utc_iso(),
                "endReason": self.end_reason,
                "panel": PANEL,
                "capture": ({"width": self.capture["width"], "height": self.capture["height"], "fps": self.frame_fps,
                             "fovDeg": capture_fov(self.capture)} if self.record else None),
                "gazeHz": GAZE_HZ,
                "faceExpressions": None if self.args.no_face else FACE_EXPRESSIONS,
            },
            "stimuli": [
                {"position": s["position"], "stimulusId": s["stimulusId"], "kind": s["kind"], "sha256": s["sha256"],
                 "width": s["width"], "height": s["height"], "screenSeconds": s.get("screenSeconds"),
                 "mediaSeconds": s.get("mediaSeconds")}
                for s in self.stimuli
            ],
            "events": self.events,
            "gaze": self.gaze,
            "face": None if self.args.no_face else {"t": self.face_t, "weights": self.face_w, "confidence": self.face_c},
            "frames": self.frames,
        }

    def truth(self) -> dict:
        """O que o simulador gerou de propósito, para conferir a análise (Fase 5)."""
        return {"sessionId": self.session["id"], "gazeHz": GAZE_HZ, "panel": PANEL, "exposures": self.exposures,
                "validSamples": sum(1 for g in self.gaze if g["valid"]), "samples": len(self.gaze)}

    def state(self) -> dict:
        return {"type": "state", "sessionId": self.session["id"], "state": "running", "t": round(self.now(), 3),
                "position": self.position, "neutral": self.neutral, "paused": self.paused,
                "shown": sorted(self.shown), "lastCommandId": self.last_command_id}


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
            self.recording = Recording(self.session, self.cache, self.args, folder, self._send_state)
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
        doc = rec.document(self.info)
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
