"""Execução ao vivo: a tabela devices e, nas sessões, o óculos que executou e o fim do envio.

Revision ID: 0005_devices
Revises: 0004_sessions
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_devices"
down_revision: Union[str, Sequence[str], None] = "0004_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("last_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("device_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("data_received_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index(batch.f("ix_sessions_device_id"), ["device_id"], unique=False)
        batch.create_foreign_key(batch.f("fk_sessions_device_id_devices"), "devices", ["device_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_constraint(batch.f("fk_sessions_device_id_devices"), type_="foreignkey")
        batch.drop_index(batch.f("ix_sessions_device_id"))
        batch.drop_column("data_received_at")
        batch.drop_column("device_id")
    op.drop_table("devices")
