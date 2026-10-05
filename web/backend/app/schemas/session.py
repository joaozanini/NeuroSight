"""Contratos JSON das sessões de captura do fluxo antigo: ingestão e leitura.

Os nomes e formatos são os que o app do óculos e o `scripts/replay_session.py` já usam; mudar um
campo aqui quebra o upload do aparelho.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SessionSummary(BaseModel):
    """Linha da lista: tudo menos o payload (samples/frames podem ter dezenas de milhares de itens)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    device_session_id: str
    status: str
    captured_at: datetime | None
    created_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    frame_count: int | None
    declared_frame_count: int | None
    sample_count: int | None
    valid_sample_count: int | None
    frame_width: int | None
    frame_height: int | None
    video_fps: float | None
    video_codec: str | None
    has_video: bool


class SessionDetail(SessionSummary):
    meta: dict[str, Any] | None
    frames: list[dict[str, Any]] | None
    samples: list[dict[str, Any]] | None
    uv_origin: str | None
    capture_fov_deg: float | None
    video_url: str | None
    error_detail: str | None


class SessionPage(BaseModel):
    items: list[SessionSummary]
    total: int
    limit: int
    offset: int


class SessionDeleted(BaseModel):
    deleted: str


class IngestCreated(BaseModel):
    """Resposta do create: o óculos lê `id` e `received_frames` para retomar o envio."""

    id: str
    status: str
    expected_frames: int
    received_frames: int


class FramesReceived(BaseModel):
    received_frames: int
    saved: list[str]
    rejected: list[str]


class IngestCompleted(BaseModel):
    id: str
    status: str
    frame_count: int
    video_ready: bool
