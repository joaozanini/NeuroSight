"""Contratos JSON das sessões do fluxo antigo (cena 3D), só para leitura (`/legacy/sessions`)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LegacySessionSummary(BaseModel):
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


class LegacySessionDetail(LegacySessionSummary):
    meta: dict[str, Any] | None
    frames: list[dict[str, Any]] | None
    samples: list[dict[str, Any]] | None
    uv_origin: str | None
    capture_fov_deg: float | None
    video_url: str | None
    error_detail: str | None


class LegacySessionPage(BaseModel):
    items: list[LegacySessionSummary]
    total: int
    limit: int
    offset: int
