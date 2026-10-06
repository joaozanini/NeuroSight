"""Análise dos dados de uma sessão (o JSON v2 de docs/protocolo-oculos.md): o que a W16, a W17 e o
CSV por estímulo mostram. Só cálculo, sem banco nem disco (services/ingestion.py guarda o resultado).

- **Exibições**: cada estímulo vai do `stimulus_on` ao `stimulus_off` (ou à tela neutra, ou ao fim
  da sessão), na ordem em que apareceu. A tela neutra fica de fora, e um estímulo que volta à tela
  (Anterior, clique na sequência) gera outra exibição, com as próprias métricas.
- **Fixações por I-DT** (Salvucci e Goldberg, 2000): janela de pelo menos 100 ms cuja dispersão, a
  amplitude horizontal mais a vertical, fica em até 1°. Os graus de ângulo visual saem da geometria
  do painel (`meta.panel`) e do estímulo dentro dele (inteiro, centralizado). Só entram as amostras
  válidas sobre o estímulo; uma falha no meio corta a janela. Depois, fixações vizinhas separadas
  por menos de 75 ms e a menos de 0,5° viram uma só: sem isso, uma amostra ruidosa no meio de uma
  fixação longa a partia em duas.
- **Métricas** de cada exibição: fixações, duração média, tempo até a 1ª fixação (desde o
  `stimulus_on`) e a porcentagem de amostras válidas (o OpenXR deu um olhar válido).
- **Mapa de calor**: histograma das amostras válidas sobre o estímulo, numa grade de UV; o site
  espalha cada célula com uma gaussiana (src/heatmap).
- **Expressões**: a média das 70 em cada exibição (para o CSV) e as séries da legenda padrão da W17
  (média dos lados L e R), reamostradas em janelas de 100 ms, ou seja, cerca de 10 Hz.
- **Gravação**: o olhar no quadro da gravação (`frameUv`) mais próximo de cada frame do MP4, para o
  círculo sobre o vídeo.
"""
import math
from dataclasses import dataclass, field

import numpy as np

# Os parâmetros padrão do plano; a ingestão passa os de `settings` (QUESTPRO_FIXATION_*).
DISPERSION_DEG = 1.0
MIN_FIXATION_S = 0.1
MERGE_GAP_S = 0.075
MERGE_DEG = 0.5
HEAT_BINS = 80
FACE_HZ = 10
# Pausa no olhar maior que isso (em períodos de amostragem) corta a janela do I-DT.
MAX_GAP_PERIODS = 2.5
# O olhar de um frame da gravação: a amostra mais próxima a até 50 ms.
FRAME_GAZE_S = 0.05

# Legenda padrão da W17: a expressão (lados L e R) e o nome na interface.
DEFAULT_EXPRESSIONS = (
    ("INNER_BROW_RAISER", "Sobrancelha interna elevada"),
    ("LIP_CORNER_PULLER", "Canto da boca puxado"),
    ("EYES_CLOSED", "Olhos fechados"),
)


@dataclass
class Fixation:
    start: float
    duration: float
    u: float
    v: float
    # Centro em graus (horizontal, vertical) e quantas amostras entraram, para juntar vizinhas.
    az: float = 0.0
    el: float = 0.0
    count: int = 0

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class Exposure:
    seq: int
    position: int
    stimulus_id: str
    on: float
    off: float
    samples: int = 0
    valid_samples: int = 0
    fixations: list[Fixation] = field(default_factory=list)
    heat: list[list[float]] = field(default_factory=list)
    face_means: list[float] | None = None

    @property
    def fixation_count(self) -> int:
        return len(self.fixations)

    @property
    def mean_fixation_ms(self) -> float | None:
        if not self.fixations:
            return None
        return round(1000 * sum(f.duration for f in self.fixations) / len(self.fixations), 1)

    @property
    def first_fixation_ms(self) -> float | None:
        return round(1000 * (self.fixations[0].start - self.on), 1) if self.fixations else None

    @property
    def valid_fraction(self) -> float | None:
        return round(self.valid_samples / self.samples, 4) if self.samples else None


@dataclass
class Result:
    duration: float
    gaze_hz: float | None
    samples: int
    valid_samples: int
    exposures: list[Exposure]
    # Séries da legenda padrão a FACE_HZ: {"INNER_BROW_RAISER": [0.03, None, ...], ...}; None sem facial.
    face_series: dict[str, list[float | None]] | None
    face_expressions: list[str] | None
    # Olhar no quadro de cada frame do MP4 ([u, v] ou None), na ordem dos frames.
    frame_gaze: list[list[float] | None] = field(default_factory=list)


@dataclass
class Params:
    dispersion_deg: float = DISPERSION_DEG
    min_fixation_s: float = MIN_FIXATION_S
    merge_gap_s: float = MERGE_GAP_S
    merge_deg: float = MERGE_DEG

    def as_dict(self) -> dict:
        return {"dispersion_deg": self.dispersion_deg, "min_fixation_ms": round(self.min_fixation_s * 1000),
                "merge_gap_ms": round(self.merge_gap_s * 1000), "merge_deg": self.merge_deg,
                "heat_bins": HEAT_BINS, "face_hz": FACE_HZ}


class Gaze:
    """O olhar em colunas numpy, ordenado pelo tempo."""

    def __init__(self, samples: list[dict]):
        rows = sorted(samples, key=lambda s: s["t"])
        n = len(rows)
        self.t = np.fromiter((s["t"] for s in rows), float, n)
        self.valid = np.fromiter((s["valid"] for s in rows), bool, n)
        on_stim = np.fromiter((bool(s.get("onStim")) for s in rows), bool, n)
        self.stim_u, self.stim_v = _uv_columns(rows, "stimUv")
        self.frame_u, self.frame_v = _uv_columns(rows, "frameUv")
        inside = (self.stim_u >= 0) & (self.stim_u <= 1) & (self.stim_v >= 0) & (self.stim_v <= 1)
        # Amostras que valem para as fixações e o mapa de calor: válidas e sobre o estímulo.
        self.on_stim = self.valid & on_stim & inside
        self.period = _period(self.t)


def _uv_columns(rows: list[dict], key: str) -> tuple[np.ndarray, np.ndarray]:
    u = np.full(len(rows), np.nan)
    v = np.full(len(rows), np.nan)
    for i, s in enumerate(rows):
        uv = s.get(key)
        if uv is not None:
            u[i], v[i] = uv
    return u, v


def _period(t: np.ndarray) -> float:
    """Intervalo típico entre amostras (a mediana resiste às falhas)."""
    if len(t) < 2:
        return 1 / 72
    steps = np.diff(t)
    steps = steps[steps > 0]
    return float(np.median(steps)) if len(steps) else 1 / 72


# ---- Exibições ------------------------------------------------------------------------------------

def session_duration(doc: dict) -> float:
    """Até o `session_end`; sem ele (sessão que caiu), até a última coisa registrada."""
    ends = [e["t"] for e in doc["events"] if e["type"] == "session_end"]
    if ends:
        return float(max(ends))
    last = [e["t"] for e in doc["events"]] + [g["t"] for g in doc["gaze"][-1:]]
    face = doc.get("face")
    if face and face.get("t"):
        last.append(face["t"][-1])
    return float(max(last, default=0.0))


def exposures(doc: dict, duration: float) -> list[Exposure]:
    """As exibições de estímulo, na ordem em que apareceram."""
    stimuli = {s["position"]: s for s in doc["stimuli"]}
    events = sorted(enumerate(doc["events"]), key=lambda pair: (pair[1]["t"], pair[0]))
    result: list[Exposure] = []
    current: dict | None = None

    def close(t: float) -> None:
        nonlocal current
        if current is not None and t > current["on"]:
            result.append(Exposure(seq=len(result) + 1, position=current["position"],
                                   stimulus_id=current["stimulus_id"], on=current["on"], off=t))
        current = None

    for _, event in events:
        kind, t = event["type"], float(event["t"])
        if kind == "stimulus_on":
            close(t)
            position = event["position"]
            stimulus_id = event.get("stimulusId") or stimuli.get(position, {}).get("stimulusId")
            if stimulus_id:
                current = {"position": position, "stimulus_id": stimulus_id, "on": t}
        elif kind in ("stimulus_off", "neutral_on", "session_end"):
            close(t)
    close(duration)
    return result


# ---- Fixações ---------------------------------------------------------------------------------------

def stimulus_size_m(stim: dict | None, panel: dict) -> tuple[float, float]:
    """Largura e altura do estímulo no painel, em metros (inteiro, centralizado, com faixas)."""
    panel_w, panel_h = float(panel["widthM"]), float(panel["heightM"])
    width, height = (stim or {}).get("width"), (stim or {}).get("height")
    if not width or not height:
        return panel_w, panel_h
    aspect, panel_aspect = width / height, panel_w / panel_h
    if aspect >= panel_aspect:
        return panel_w, panel_w / aspect
    return panel_h * aspect, panel_h


def to_degrees(u: np.ndarray, v: np.ndarray, size_m: tuple[float, float], distance_m: float):
    """UV no estímulo → (horizontal, vertical) em graus de ângulo visual, a partir do centro."""
    x = (u - 0.5) * size_m[0]
    y = (v - 0.5) * size_m[1]
    az = np.degrees(np.arctan2(x, distance_m))
    el = np.degrees(np.arctan2(y, np.hypot(x, distance_m)))
    return az, el


def idt(t: np.ndarray, x: np.ndarray, y: np.ndarray, period: float, params: Params) -> list[tuple[int, int]]:
    """I-DT numa sequência sem falhas: devolve (primeira, última) amostra de cada fixação.

    A duração de uma janela é do primeiro ao último instante mais um período (cada amostra vale
    pelo intervalo dela), então 8 amostras a 72 Hz já somam os 100 ms.
    """
    found: list[tuple[int, int]] = []
    n = len(t)
    i = 0
    while i < n:
        j = int(np.searchsorted(t, t[i] + params.min_fixation_s - period - 1e-9, side="left"))
        if j >= n:
            break
        x_min, x_max = float(x[i:j + 1].min()), float(x[i:j + 1].max())
        y_min, y_max = float(y[i:j + 1].min()), float(y[i:j + 1].max())
        if (x_max - x_min) + (y_max - y_min) > params.dispersion_deg:
            i += 1
            continue
        while j + 1 < n:
            nx_min, nx_max = min(x_min, x[j + 1]), max(x_max, x[j + 1])
            ny_min, ny_max = min(y_min, y[j + 1]), max(y_max, y[j + 1])
            if (nx_max - nx_min) + (ny_max - ny_min) > params.dispersion_deg:
                break
            x_min, x_max, y_min, y_max = nx_min, nx_max, ny_min, ny_max
            j += 1
        found.append((i, j))
        i = j + 1
    return found


def _runs(t: np.ndarray, usable: np.ndarray, period: float) -> list[np.ndarray]:
    """Índices das sequências de amostras usáveis sem falha nem pausa longa entre elas."""
    runs, current = [], []
    last_t = None
    for i in range(len(t)):
        if not usable[i]:
            if current:
                runs.append(np.array(current))
            current, last_t = [], None
            continue
        if last_t is not None and t[i] - last_t > MAX_GAP_PERIODS * period:
            runs.append(np.array(current))
            current = []
        current.append(i)
        last_t = t[i]
    if current:
        runs.append(np.array(current))
    return runs


def _merge(fixations: list[Fixation], params: Params) -> list[Fixation]:
    merged: list[Fixation] = []
    for fix in fixations:
        prev = merged[-1] if merged else None
        if (prev is not None and fix.start - prev.end < params.merge_gap_s
                and math.hypot(fix.az - prev.az, fix.el - prev.el) < params.merge_deg):
            total = prev.count + fix.count
            merged[-1] = Fixation(
                start=prev.start, duration=fix.end - prev.start,
                u=(prev.u * prev.count + fix.u * fix.count) / total,
                v=(prev.v * prev.count + fix.v * fix.count) / total,
                az=(prev.az * prev.count + fix.az * fix.count) / total,
                el=(prev.el * prev.count + fix.el * fix.count) / total, count=total,
            )
        else:
            merged.append(fix)
    return merged


def fixations(gaze: Gaze, idx: np.ndarray, size_m: tuple[float, float], distance_m: float,
              params: Params) -> list[Fixation]:
    """As fixações nas amostras `idx` (as de uma exibição)."""
    t = gaze.t[idx]
    usable = gaze.on_stim[idx]
    u, v = gaze.stim_u[idx], gaze.stim_v[idx]
    found: list[Fixation] = []
    for run in _runs(t, usable, gaze.period):
        rt, ru, rv = t[run], u[run], v[run]
        az, el = to_degrees(ru, rv, size_m, distance_m)
        for first, last in idt(rt, az, el, gaze.period, params):
            span = slice(first, last + 1)
            found.append(Fixation(
                start=float(rt[first]), duration=float(rt[last] - rt[first] + gaze.period),
                u=float(ru[span].mean()), v=float(rv[span].mean()),
                az=float(az[span].mean()), el=float(el[span].mean()), count=last - first + 1,
            ))
    return _merge(found, params)


def heat(gaze: Gaze, idx: np.ndarray) -> list[list[float]]:
    """Histograma das amostras sobre o estímulo: [[u, v, amostras], ...] no centro de cada célula."""
    use = idx[gaze.on_stim[idx]]
    if not len(use):
        return []
    cols = np.minimum((gaze.stim_u[use] * HEAT_BINS).astype(int), HEAT_BINS - 1)
    rows = np.minimum((gaze.stim_v[use] * HEAT_BINS).astype(int), HEAT_BINS - 1)
    counts = np.bincount(rows * HEAT_BINS + cols, minlength=HEAT_BINS * HEAT_BINS)
    cells = np.nonzero(counts)[0]
    return [[round((int(c) % HEAT_BINS + 0.5) / HEAT_BINS, 4), round((int(c) // HEAT_BINS + 0.5) / HEAT_BINS, 4),
             int(counts[c])] for c in cells]


# ---- Expressões -------------------------------------------------------------------------------------

def _face_matrix(doc: dict) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    face, names = doc.get("face"), doc["meta"].get("faceExpressions")
    if not face or not names or not face.get("t"):
        return None
    t = np.asarray(face["t"], dtype=float)
    weights = np.asarray(face["weights"], dtype=float).reshape(len(t), len(names))
    order = np.argsort(t, kind="stable")
    return t[order], weights[order], list(names)


def face_series(t: np.ndarray, weights: np.ndarray, names: list[str], duration: float) -> dict[str, list]:
    """As expressões da legenda padrão em janelas de 1/FACE_HZ s; janela sem leitura = None."""
    bins = max(1, math.ceil(duration * FACE_HZ))
    slot = np.clip((t * FACE_HZ).astype(int), 0, bins - 1)
    keep = (t >= 0) & (t <= duration)
    counts = np.bincount(slot[keep], minlength=bins)
    series = {}
    for key, _label in DEFAULT_EXPRESSIONS:
        columns = [i for i, name in enumerate(names) if name in (f"{key}_L", f"{key}_R", key)]
        if not columns:
            continue
        values = weights[:, columns].mean(axis=1)
        sums = np.bincount(slot[keep], weights=values[keep], minlength=bins)
        series[key] = [round(float(s / c), 3) if c else None for s, c in zip(sums, counts)]
    return series


# ---- Tudo junto -----------------------------------------------------------------------------------

def analyze(doc: dict, params: Params | None = None, frames: list[dict] | None = None) -> Result:
    """O JSON v2 (já validado por services/tracking.py) → métricas e séries. `frames` são os frames
    que entraram no MP4, na ordem, para o olhar de cada um."""
    params = params or Params()
    duration = session_duration(doc)
    gaze = Gaze(doc["gaze"])
    panel = doc["meta"]["panel"]
    stimuli = {s["position"]: s for s in doc["stimuli"]}
    face = _face_matrix(doc)

    found = exposures(doc, duration)
    for exposure in found:
        lo, hi = np.searchsorted(gaze.t, [exposure.on, exposure.off], side="left")
        idx = np.arange(lo, hi)
        exposure.samples = int(len(idx))
        exposure.valid_samples = int(gaze.valid[idx].sum())
        size_m = stimulus_size_m(stimuli.get(exposure.position), panel)
        exposure.fixations = fixations(gaze, idx, size_m, float(panel["distanceM"]), params)
        exposure.heat = heat(gaze, idx)
        if face is not None:
            t, weights, _ = face
            lo, hi = np.searchsorted(t, [exposure.on, exposure.off], side="left")
            if hi > lo:
                exposure.face_means = [round(float(x), 4) for x in weights[lo:hi].mean(axis=0)]

    hz = doc["meta"].get("gazeHz")
    return Result(
        duration=round(duration, 3),
        gaze_hz=float(hz) if hz else (round(1 / gaze.period, 1) if len(gaze.t) > 1 else None),
        samples=int(len(gaze.t)),
        valid_samples=int(gaze.valid.sum()),
        exposures=found,
        face_series=face_series(face[0], face[1], face[2], duration) if face is not None else None,
        face_expressions=face[2] if face is not None else None,
        frame_gaze=frame_gaze(gaze, frames) if frames else [],
    )


def frame_gaze(gaze: Gaze, frames: list[dict]) -> list[list[float] | None]:
    """O olhar no quadro da gravação de cada frame (na ordem de `frames`), ou None se não houver
    amostra válida a até FRAME_GAZE_S do frame."""
    if not len(gaze.t):
        return [None] * len(frames)
    result: list[list[float] | None] = []
    for frame in frames:
        t = float(frame["t"])
        k = int(np.searchsorted(gaze.t, t))
        best = min((i for i in (k - 1, k) if 0 <= i < len(gaze.t)), key=lambda i: abs(gaze.t[i] - t))
        u, v = gaze.frame_u[best], gaze.frame_v[best]
        if abs(gaze.t[best] - t) > FRAME_GAZE_S or not gaze.valid[best] or np.isnan(u) or np.isnan(v):
            result.append(None)
        else:
            result.append([round(float(u), 4), round(float(v), 4)])
    return result
