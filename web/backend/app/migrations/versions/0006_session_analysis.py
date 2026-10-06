"""Análise dos dados: o resultado em sessions.analysis e as exibições em session_exposures.

Revision ID: 0006_session_analysis
Revises: 0005_devices
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_session_analysis"
down_revision: Union[str, Sequence[str], None] = "0005_devices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("analysis", JSONType, nullable=True))

    op.create_table(
        "session_exposures",
        sa.Column("id", BigIntPK, autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.String(length=32), nullable=False),
        sa.Column("on_t", sa.Float(), nullable=False),
        sa.Column("off_t", sa.Float(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("valid_samples", sa.Integer(), nullable=False),
        sa.Column("fixation_count", sa.Integer(), nullable=False),
        sa.Column("mean_fixation_ms", sa.Float(), nullable=True),
        sa.Column("first_fixation_ms", sa.Float(), nullable=True),
        sa.Column("fixations", JSONType, nullable=False),
        sa.Column("heat", JSONType, nullable=False),
        sa.Column("face_means", JSONType, nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f("fk_session_exposures_session_id_sessions"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["stimulus_id"], ["stimuli.id"], name=op.f("fk_session_exposures_stimulus_id_stimuli")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seq", name=op.f("uq_session_exposures_session_id")),
    )
    op.create_index(op.f("ix_session_exposures_session_id"), "session_exposures", ["session_id"], unique=False)
    op.create_index(op.f("ix_session_exposures_stimulus_id"), "session_exposures", ["stimulus_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_session_exposures_stimulus_id"), table_name="session_exposures")
    op.drop_index(op.f("ix_session_exposures_session_id"), table_name="session_exposures")
    op.drop_table("session_exposures")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("analysis")
