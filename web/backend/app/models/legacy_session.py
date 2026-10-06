"""Sessões de captura do fluxo antigo (cena 3D), guardadas só para consulta.

O fluxo antigo foi substituído pelas sessões configuradas no site (`models/session.py`). A tabela
`sessions` da baseline virou `legacy_sessions` na migração 0004: os dados e a mídia continuam no
servidor, só para leitura e sem tela (rotas `/legacy/sessions`). Ninguém mais grava aqui.

O payload (meta/frames/samples) fica em JSON, numa linha só; as colunas achatadas servem para
listar e ordenar sem abrir o JSON.
"""
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import mapped_column

from .base import Base, JSONType, new_id, utcnow


class LegacySession(Base):
    __tablename__ = "legacy_sessions"

    id = mapped_column(String(32), primary_key=True, default=new_id)
    # Nome da pasta no device (X-Session-Id) — chave de idempotência (re-run retoma a mesma linha).
    device_session_id = mapped_column(String(255), unique=True, index=True, nullable=False)
    status = mapped_column(String(20), default="uploading", index=True, nullable=False)  # uploading|processing|complete|failed

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
    created_at = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
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

    @property
    def has_video(self) -> bool:
        return bool(self.video_path)
