"""Contrato JSON da análise da sessão (W17), montado a partir de `sessions.analysis` e de
`session_exposures` (services/analysis.py)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .session import SessionStatus
from .stimulus import StimulusKind


class AnalysisExposure(BaseModel):
    """Uma exibição de estímulo, com as métricas da W17."""

    seq: int
    position: int
    stimulus_id: str
    name: str
    kind: StimulusKind
    thumbnail_url: str
    file_url: str
    # Dimensões do estímulo original (o mapa de calor e a trajetória ficam por cima dele).
    width: int | None
    height: int | None
    on_t: float
    off_t: float
    samples: int
    valid_samples: int
    fixation_count: int
    mean_fixation_ms: float | None
    first_fixation_ms: float | None
    # [[início, duração, u, v], ...], em segundos da sessão e UV do estímulo (origem em cima à esquerda).
    fixations: list[list[float]]
    # [[u, v, amostras], ...]: células com olhar sobre o estímulo.
    heat: list[list[float]]


class AnalysisMarker(BaseModel):
    t: float
    text: str


class AnalysisRecording(BaseModel):
    url: str
    fps: float
    width: int
    height: int
    # Instante (segundos da sessão) de cada frame do vídeo e o olhar nele ([u, v] no quadro ou null).
    frame_t: list[float]
    frame_gaze: list[list[float] | None]


class FaceSeries(BaseModel):
    key: str
    label: str
    # Uma média a cada 1/hz s desde o início da sessão; null onde não houve leitura.
    values: list[float | None]


class AnalysisFace(BaseModel):
    hz: float
    series: list[FaceSeries]


class SessionAnalysis(BaseModel):
    id: str
    title: str
    patient_code: str
    started_at: datetime | None
    status: SessionStatus
    # Duração da coleta no relógio do óculos, em segundos.
    duration: float
    exposures: list[AnalysisExposure]
    markers: list[AnalysisMarker]
    recording_status: Literal["ready", "failed", "none"]
    recording: AnalysisRecording | None
    face: AnalysisFace | None
    can_export: bool
