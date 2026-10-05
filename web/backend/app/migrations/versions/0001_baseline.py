"""Baseline: o esquema que as versões anteriores criavam com create_all (só a tabela sessions).

Um banco criado antes do Alembic já tem exatamente este esquema. Ele é carimbado com esta revisão,
sem recriar nada: automaticamente pelo `app.db.migrate()` quando a API sobe, ou à mão com
`alembic stamp 0001_baseline`.

A chave primária fica sem nome explícito, como no create_all antigo (no PostgreSQL ela se chama
`sessions_pkey`), para o esquema ser idêntico ao do banco que já está no servidor. Conferido com
`pg_dump --schema-only` dos dois bancos.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificadores da revisão, usados pelo Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("device_session_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("capture_fov_deg", sa.Float(), nullable=True),
        sa.Column("frame_width", sa.Integer(), nullable=True),
        sa.Column("frame_height", sa.Integer(), nullable=True),
        sa.Column("video_fps", sa.Float(), nullable=True),
        sa.Column("uv_origin", sa.String(length=32), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=True),
        sa.Column("declared_frame_count", sa.Integer(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("valid_sample_count", sa.Integer(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_dir", sa.String(length=512), nullable=True),
        sa.Column("video_path", sa.String(length=512), nullable=True),
        sa.Column("video_codec", sa.String(length=16), nullable=True),
        sa.Column("meta", JSONType, nullable=True),
        sa.Column("frames", JSONType, nullable=True),
        sa.Column("samples", JSONType, nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_device_session_id", "sessions", ["device_session_id"], unique=True)
    op.create_index("ix_sessions_status", "sessions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_device_session_id", table_name="sessions")
    op.drop_table("sessions")
