"""Pacientes e estímulos: patients, stimuli e stimulus_tags.

As etiquetas ficam numa tabela própria, com a posição em que foram digitadas. A exclusão em
cascata vale no PostgreSQL; no SQLite do desenvolvimento quem apaga as etiquetas é o ORM.

Revision ID: 0003_patients_stimuli
Revises: 0002_accounts
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_patients_stimuli"
down_revision: Union[str, Sequence[str], None] = "0002_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("sex", sa.String(length=20), nullable=False),
        sa.Column("vision_correction", sa.String(length=20), nullable=False),
        sa.Column("consent_signed", sa.Boolean(), nullable=False),
        sa.Column("consent_date", sa.Date(), nullable=True),
        sa.Column("consent_file_key", sa.String(length=255), nullable=True),
        sa.Column("consent_file_name", sa.String(length=255), nullable=True),
        sa.Column("consent_file_size", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_patients_created_by_id_users")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name=op.f("uq_patients_code")),
    )
    op.create_index(op.f("ix_patients_status"), "patients", ["status"], unique=False)

    op.create_table(
        "stimuli",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("has_audio", sa.Boolean(), nullable=True),
        sa.Column("device_status", sa.String(length=20), nullable=False),
        sa.Column("device_format", sa.String(length=10), nullable=True),
        sa.Column("device_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("device_sha256", sa.String(length=64), nullable=True),
        sa.Column("device_width", sa.Integer(), nullable=True),
        sa.Column("device_height", sa.Integer(), nullable=True),
        sa.Column("device_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_stimuli_created_by_id_users")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stimuli_status"), "stimuli", ["status"], unique=False)

    op.create_table(
        "stimulus_tags",
        sa.Column("stimulus_id", sa.String(length=32), nullable=False),
        sa.Column("tag", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["stimulus_id"], ["stimuli.id"], name=op.f("fk_stimulus_tags_stimulus_id_stimuli"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("stimulus_id", "tag"),
    )
    op.create_index(op.f("ix_stimulus_tags_tag"), "stimulus_tags", ["tag"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stimulus_tags_tag"), table_name="stimulus_tags")
    op.drop_table("stimulus_tags")
    op.drop_index(op.f("ix_stimuli_status"), table_name="stimuli")
    op.drop_table("stimuli")
    op.drop_index(op.f("ix_patients_status"), table_name="patients")
    op.drop_table("patients")
