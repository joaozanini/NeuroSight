"""Modelo de dados. Uma tabela `sessions` com meta/frames/samples como JSON (JSONB no PG).

O viewer precisa de TODAS as samples de uma sessão de uma vez (overlay client-side),
então guardar como JSON evita join e devolve tudo numa leitura. Colunas achatadas
(fov, w, h, fps, contagens, status...) servem para listar/ordenar barato.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column

# JSON portável: vira JSONB no PostgreSQL, JSON comum no SQLite.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"

    id = mapped_column(String(32), primary_key=True, default=_uuid)
    # Nome da pasta no device (X-Session-Id) — chave de idempotência (re-run retoma a mesma linha).
    device_session_id = mapped_column(String(255), unique=True, index=True, nullable=False)
    status = mapped_column(String(20), default="uploading", index=True, nullable=False)  # uploading|complete|failed

    # meta achatado
    capture_fov_deg = mapped_column(Float, nullable=True)
    frame_width = mapped_column(Integer, nullable=True)
    frame_height = mapped_column(Integer, nullable=True)
    video_fps = mapped_column(Float, nullable=True)
    uv_origin = mapped_column(String(32), default="top-left")

    # rollups
    duration_seconds = mapped_column(Float, default=0.0)
    frame_count = mapped_column(Integer, default=0)            # frames de fato no disco
    declared_frame_count = mapped_column(Integer, default=0)   # len(meta.frames[])
    sample_count = mapped_column(Integer, default=0)
    valid_sample_count = mapped_column(Integer, default=0)

    # tempos
    captured_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)

    # mídia (caminhos/keys, nunca blob)
    media_dir = mapped_column(String(512), nullable=True)
    video_path = mapped_column(String(512), nullable=True)
    video_codec = mapped_column(String(16), nullable=True)

    # payload (uma leitura alimenta o viewer inteiro)
    meta = mapped_column(JSONType, default=dict)
    frames = mapped_column(JSONType, default=list)    # [{idx,t,file}]
    samples = mapped_column(JSONType, default=list)   # [{t,valid,world,uv,confidence}]

    error_detail = mapped_column(Text, nullable=True)
