"""Olhar, expressões faciais e gravação sintéticos de uma sessão, no formato do JSON v2
(docs/protocolo-oculos.md, seção 4).

Usado pelo simulador do óculos (web/scripts/device_simulator.py), em tempo real, e pelo
`python -m app.seed --demo`, que gera os dados das sessões de exemplo num relógio virtual. Fica no
pacote da API porque a imagem Docker não leva a pasta web/scripts.

A reprodução segue as regras do óculos (troca automática das imagens, vídeo que avança ao terminar,
tela neutra, pausa). As fixações têm posição e duração conhecidas (`truth()`), para conferir a
análise: de 200 a 600 ms num ponto sorteado, sacadas de 30 ms até a próxima (sempre a mais de
0,12 UV) e, de vez em quando, uma piscada de 150 ms (amostras inválidas) no lugar da sacada.
"""
import math
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

GAZE_HZ = 72
FACE_HZ = 30
# Painel plano onde os estímulos aparecem (metros) e a distância dos olhos até ele.
PANEL = {"widthM": 2.4, "heightM": 1.35, "distanceM": 2.0}
# A câmera da gravação enquadra o painel com uma margem: ele ocupa 80% da largura do quadro.
PANEL_SHARE = 0.8
ROOM_BGR = (196, 192, 188)

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


def utc_iso(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---- Geometria ------------------------------------------------------------------------------------

def contain(width: int, height: int) -> tuple[float, float, float, float]:
    """Retângulo do estímulo dentro do painel (UV do painel): inteiro, centralizado, com faixas."""
    panel_aspect = PANEL["widthM"] / PANEL["heightM"]
    aspect = width / height if width and height else panel_aspect
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


def capture_fov() -> float:
    half = PANEL["widthM"] / PANEL_SHARE / 2
    return round(math.degrees(2 * math.atan(half / PANEL["distanceM"])), 2)


# ---- Olhar sintético -------------------------------------------------------------------------------

class Scanpath:
    """Fixações de posição e duração conhecidas sobre um estímulo, a partir de quando ele aparece."""

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
    """Uma sessão do óculos: a reprodução (o óculos é dono dela) e a coleta, até o B.

    `session` é o `session` do `load` (docs/protocolo-oculos.md, seção 2.2) e `stimulus_path` diz
    onde está o arquivo de cada estímulo. `clock` devolve os segundos desde o início: o simulador
    usa o relógio de verdade e o seed, um relógio virtual que ele mesmo avança.
    """

    def __init__(self, session: dict, stimulus_path: Callable[[dict], str], folder: Path | None, *,
                 seed: str = "neurosight", frame_fps: float = 10, face: bool = True,
                 clock: Callable[[], float] | None = None, started_at: datetime | None = None,
                 on_change: Callable[["Recording"], None] | None = None,
                 log: Callable[[str], None] | None = None):
        self.session = session
        self.stimuli = session["stimuli"]
        self.stimulus_path = stimulus_path
        self.folder = folder
        self.rng = random.Random(f"{seed}:{session['id']}")
        self.capture = session["capture"]
        self.record = bool(session.get("record")) and folder is not None
        self.frame_fps = min(self.capture["fps"], frame_fps)
        self.face = face
        self.panel_rect = panel_in_frame(self.capture)
        self.started_at = started_at or datetime.now(timezone.utc)
        t0 = time.monotonic()
        self.now = clock or (lambda: time.monotonic() - t0)
        self.on_change = on_change or (lambda rec: None)
        self.log = log or (lambda text: None)
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
        self._images: dict[int, np.ndarray | None] = {}
        self._videos: dict[int, dict] = {}
        if self.record:
            (folder / "frames").mkdir(parents=True, exist_ok=True)

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
                               "on": round(t, 4), "off": None, "samples": 0, "validSamples": 0, "fixations": []})
        self.log(f"Em exibição: {position}. {stim['name']}")

    def _neutral_on(self, t: float, why: str = "") -> None:
        if self.neutral:
            return
        self._off(t)
        self.neutral, self.paused = True, False
        self.events.append({"t": round(t, 4), "type": "neutral_on"})
        self.log(f"Tela neutra{why}")

    def _auto_next(self, t: float) -> None:
        if self.position is not None and self.position < len(self.stimuli):
            self._show(self.position + 1, t, "auto")
        else:
            self._neutral_on(t, " (fim da sequência; aguardando o B)")

    def _catch_up(self, t: float) -> bool:
        """Aplica as trocas automáticas até `t`, no instante exato de cada uma, e coleta até `t`."""
        changed = False
        while (deadline := self._deadline()) is not None and deadline <= t:
            self._collect(deadline)
            self._auto_next(deadline)
            changed = True
        self._collect(t)
        return changed

    def advance(self) -> None:
        """Leva a coleta até agora."""
        with self.lock:
            if self.ended_t is not None:
                return
            if self._catch_up(self.now()):
                self.on_change(self)

    def command(self, message: dict) -> None:
        with self.lock:
            if self.ended_t is not None:
                return
            t = self.now()
            self._catch_up(t)
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
                    self.log("Vídeo pausado")
            elif action == "resume" and self.paused:
                self.paused, self.play_t = False, t
                self.events.append({"t": round(t, 4), "type": "video_resume", "position": self.position})
                self.log("Vídeo retomado")
            self.on_change(self)

    def end(self, reason: str) -> None:
        with self.lock:
            if self.ended_t is not None:
                return
            t = self.now()
            self._catch_up(t)
            if self._current() is not None:
                self._off(t)
            self.events.append({"t": round(t, 4), "type": "session_end", "reason": reason})
            self.end_reason, self.ended_t = reason, t
            for video in self._videos.values():
                video["capture"].release()
            self._videos.clear()

    # -- coleta

    def _collect(self, t: float) -> None:
        """Gera as amostras com tempo menor que `t` (a de `t` em diante já é da tela seguinte)."""
        while (self.gaze_k / GAZE_HZ) < t:
            self._gaze_sample(self.gaze_k / GAZE_HZ)
            self.gaze_k += 1
        if self.face:
            while (self.face_k / FACE_HZ) < t:
                self._face_sample(self.face_k / FACE_HZ)
                self.face_k += 1
        if self.record:
            while (self.frame_k / self.frame_fps) < t:
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
        exposure = self.exposures[-1]
        exposure["samples"] += 1
        if not valid:
            self.gaze.append({"t": round(t, 4), "valid": False, "conf": 0.0, "onStim": False, "stimUv": None,
                              "frameUv": None})
            return
        exposure["validSamples"] += 1
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
                index = FACE_EXPRESSIONS.index(name)
                weights[index] = min(1.0, weights[index] + 0.7 * bump)
        # Piscando: a amostra do olhar do instante (a k-ésima é a de k/GAZE_HZ, já gerada) é inválida.
        if self.gaze and not self.gaze[min(len(self.gaze) - 1, int(t * GAZE_HZ))]["valid"]:
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
            sx, sy, sw, sh = contain(stim["width"], stim["height"])
            rw, rh = max(1, int(sw * pw)), max(1, int(sh * ph))
            content = self._stimulus_frame(stim, t, (rw, rh))
            if content is not None:
                ox, oy = px + int(sx * pw), py + int(sy * ph)
                img[oy:oy + rh, ox:ox + rw] = content
        name = f"{len(self.frames) + 1:06d}.jpg"
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(self.capture.get("jpegQuality", 80))])
        if ok:
            (self.folder / "frames" / name).write_bytes(buf.tobytes())
            self.frames.append({"idx": len(self.frames) + 1, "t": round(t, 4), "file": name})

    def _stimulus_frame(self, stim: dict, t: float, size: tuple[int, int]) -> np.ndarray | None:
        """O estímulo no instante `t`, já no tamanho em que aparece no quadro."""
        position = stim["position"]
        if stim["kind"] == "image":
            # A imagem não muda: reduz uma vez só (reduzir 2048 px a cada quadro custa caro).
            if position not in self._images:
                original = cv2.imread(str(self.stimulus_path(stim)))
                self._images[position] = (cv2.resize(original, size, interpolation=cv2.INTER_AREA)
                                          if original is not None else None)
            return self._images[position]
        playhead = self.video_pos + (0 if self.paused else t - self.play_t)
        frame = self._video_frame(position, str(self.stimulus_path(stim)), max(0.0, playhead))
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA) if frame is not None else None

    def _video_frame(self, position: int, path: str, playhead: float) -> np.ndarray | None:
        """O quadro do vídeo em `playhead`, lendo em sequência (pular no H.264 a cada quadro é lento)."""
        video = self._videos.get(position)
        if video is None:
            capture = cv2.VideoCapture(path)
            video = self._videos[position] = {"capture": capture, "fps": capture.get(cv2.CAP_PROP_FPS) or 30.0,
                                              "next": 0, "frame": None}
        target = int(playhead * video["fps"])
        if target < video["next"] - 1 or target > video["next"] + 2 * video["fps"]:
            video["capture"].set(cv2.CAP_PROP_POS_FRAMES, target)
            video["next"], video["frame"] = target, None
        while video["next"] <= target:
            ok, frame = video["capture"].read()
            if not ok:
                break
            video["frame"] = frame
            video["next"] += 1
        return video["frame"]

    # -- JSON v2

    def document(self, device: dict, app_version: str) -> dict:
        ended = self.started_at + timedelta(seconds=self.ended_t or self.now())
        return {
            "version": 2,
            "meta": {
                "sessionId": self.session["id"],
                "device": device,
                "appVersion": app_version,
                "startedAt": utc_iso(self.started_at),
                "endedAt": utc_iso(ended),
                "endReason": self.end_reason,
                "panel": PANEL,
                "capture": ({"width": self.capture["width"], "height": self.capture["height"], "fps": self.frame_fps,
                             "fovDeg": capture_fov()} if self.record else None),
                "gazeHz": GAZE_HZ,
                "faceExpressions": FACE_EXPRESSIONS if self.face else None,
            },
            "stimuli": [
                {"position": s["position"], "stimulusId": s["stimulusId"], "kind": s["kind"], "sha256": s["sha256"],
                 "width": s["width"], "height": s["height"], "screenSeconds": s.get("screenSeconds"),
                 "mediaSeconds": s.get("mediaSeconds")}
                for s in self.stimuli
            ],
            "events": self.events,
            "gaze": self.gaze,
            "face": {"t": self.face_t, "weights": self.face_w, "confidence": self.face_c} if self.face else None,
            "frames": self.frames,
        }

    def truth(self) -> dict:
        """O que foi gerado de propósito, para conferir a análise: cada exibição com as fixações e as
        amostras (todas e as válidas)."""
        return {"sessionId": self.session["id"], "gazeHz": GAZE_HZ, "panel": PANEL, "exposures": self.exposures,
                "validSamples": sum(1 for g in self.gaze if g["valid"]), "samples": len(self.gaze)}

    def state(self) -> dict:
        return {"type": "state", "sessionId": self.session["id"], "state": "running", "t": round(self.now(), 3),
                "position": self.position, "neutral": self.neutral, "paused": self.paused,
                "shown": sorted(self.shown), "lastCommandId": self.last_command_id}


class VirtualClock:
    """Relógio que só anda quando mandam: o seed gera uma sessão de minutos em segundos."""

    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def play(recording: Recording, clock: VirtualClock, steps: list[tuple[float, str | dict]]) -> None:
    """Executa um roteiro no relógio virtual: em cada instante, um comando da W15 ou o fim.

    Ex.: [(4.2, "next"), (40.0, "next"), (61.3, "button_b")]. "button_b" e "interrupted" encerram.
    """
    for t, step in steps:
        clock.t = t
        recording.advance()
        if step in ("button_b", "interrupted"):
            recording.end(step)
            return
        recording.command(step if isinstance(step, dict) else {"action": step})
