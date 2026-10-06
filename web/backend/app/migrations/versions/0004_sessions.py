"""Sessões configuradas no site: sessions, session_stimuli, session_shares e session_markers.

A tabela `sessions` da baseline (fluxo antigo, cena 3D) vira `legacy_sessions`, com os dados
preservados, só para leitura. Os nomes dos índices e, no PostgreSQL, o da chave primária
(`sessions_pkey`) também mudam, porque no banco esses nomes são únicos e a tabela nova usa os
mesmos.

Revision ID: 0004_sessions
Revises: 0003_patients_stimuli
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_sessions"
down_revision: Union[str, Sequence[str], None] = "0003_patients_stimuli"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
LEGACY_INDEXES = (("device_session_id", True), ("status", False))


def _rename_legacy(old: str, new: str) -> None:
    """Renomeia a tabela do fluxo antigo com os índices e, no PostgreSQL, a chave primária."""
    op.rename_table(old, new)
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"ALTER TABLE {new} RENAME CONSTRAINT {old}_pkey TO {new}_pkey")
        for column, _ in LEGACY_INDEXES:
            op.execute(f"ALTER INDEX ix_{old}_{column} RENAME TO ix_{new}_{column}")
    else:
        # O SQLite não renomeia índices: recria com o nome novo.
        for column, unique in LEGACY_INDEXES:
            op.drop_index(f"ix_{old}_{column}", table_name=new)
            op.create_index(f"ix_{new}_{column}", new, [column], unique=unique)


def upgrade() -> None:
    _rename_legacy("sessions", "legacy_sessions")

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("end_reason", sa.String(length=30), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("record", sa.Boolean(), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("patient_id", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("duplicated_from_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["duplicated_from_id"], ["sessions.id"], name=op.f("fk_sessions_duplicated_from_id_sessions"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_sessions_owner_id_users")),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], name=op.f("fk_sessions_patient_id_patients")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sessions_created_at"), "sessions", ["created_at"], unique=False)
    op.create_index(op.f("ix_sessions_owner_id"), "sessions", ["owner_id"], unique=False)
    op.create_index(op.f("ix_sessions_patient_id"), "sessions", ["patient_id"], unique=False)
    op.create_index(op.f("ix_sessions_status"), "sessions", ["status"], unique=False)

    op.create_table(
        "session_stimuli",
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.String(length=32), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f("fk_session_stimuli_session_id_sessions"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["stimulus_id"], ["stimuli.id"], name=op.f("fk_session_stimuli_stimulus_id_stimuli")),
        sa.PrimaryKeyConstraint("session_id", "position"),
        sa.UniqueConstraint("session_id", "stimulus_id", name=op.f("uq_session_stimuli_session_id")),
    )
    op.create_index(op.f("ix_session_stimuli_stimulus_id"), "session_stimuli", ["stimulus_id"], unique=False)

    op.create_table(
        "session_shares",
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f("fk_session_shares_session_id_sessions"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_session_shares_user_id_users")),
        sa.PrimaryKeyConstraint("session_id", "user_id"),
    )
    op.create_index(op.f("ix_session_shares_user_id"), "session_shares", ["user_id"], unique=False)

    op.create_table(
        "session_markers",
        sa.Column("id", BigIntPK, autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("t", sa.Float(), nullable=False),
        sa.Column("text", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_session_markers_created_by_id_users")),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f("fk_session_markers_session_id_sessions"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_markers_session_id"), "session_markers", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_session_markers_session_id"), table_name="session_markers")
    op.drop_table("session_markers")
    op.drop_index(op.f("ix_session_shares_user_id"), table_name="session_shares")
    op.drop_table("session_shares")
    op.drop_index(op.f("ix_session_stimuli_stimulus_id"), table_name="session_stimuli")
    op.drop_table("session_stimuli")
    op.drop_index(op.f("ix_sessions_status"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_patient_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_owner_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_created_at"), table_name="sessions")
    op.drop_table("sessions")
    _rename_legacy("legacy_sessions", "sessions")
