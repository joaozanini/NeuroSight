"""Migrações: a baseline reproduz o esquema dos modelos, e um banco antigo é carimbado sem perder dados.

Os testes rodam no SQLite. Com NEUROSIGHT_TEST_PG_URL apontando para um PostgreSQL descartável
(ex.: postgresql+psycopg://postgres:senha@localhost:55499/postgres), os mesmos testes rodam nele.
"""
import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, create_engine, inspect, insert, select, text

from app.db import BASELINE_REVISION, migrate
from app.models import Base, Session

PG_URL = os.environ.get("NEUROSIGHT_TEST_PG_URL")


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request, tmp_path):
    if request.param == "sqlite":
        eng = create_engine(f"sqlite:///{tmp_path / 'migracao.db'}")
    else:
        if not PG_URL:
            pytest.skip("NEUROSIGHT_TEST_PG_URL não definida")
        eng = create_engine(PG_URL)
        with eng.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS sessions, alembic_version CASCADE"))
    yield eng
    eng.dispose()


def schema_diff(engine):
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), Base.metadata)


def current_revision(engine):
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def create_legacy_schema(engine):
    """O que as versões anteriores faziam ao subir: create_all, sem convenção de nomes nem Alembic."""
    legacy = MetaData()
    Session.__table__.to_metadata(legacy)
    legacy.create_all(engine)


def test_fresh_database_reaches_head_matching_models(engine):
    migrate(engine)
    assert current_revision(engine) == BASELINE_REVISION
    assert schema_diff(engine) == []


def test_migrate_is_idempotent(engine):
    migrate(engine)
    migrate(engine)
    assert current_revision(engine) == BASELINE_REVISION


def test_legacy_database_is_stamped_and_keeps_its_rows(engine):
    create_legacy_schema(engine)
    with engine.begin() as conn:
        conn.execute(insert(Session.__table__).values(
            id="a" * 32, device_session_id="2026-06-17_22-10-54", status="complete",
            created_at=Session.created_at.default.arg(None),
        ))

    migrate(engine)

    assert current_revision(engine) == BASELINE_REVISION
    assert schema_diff(engine) == []
    with engine.connect() as conn:
        rows = conn.execute(select(Session.__table__.c.device_session_id)).scalars().all()
    assert rows == ["2026-06-17_22-10-54"]


def test_baseline_names_indexes_and_primary_key_like_create_all(engine):
    migrate(engine)
    insp = inspect(engine)
    indexes = {ix["name"]: ix["unique"] for ix in insp.get_indexes("sessions")}
    assert indexes == {"ix_sessions_device_session_id": True, "ix_sessions_status": False}
    if engine.dialect.name == "postgresql":
        # Nome que o PostgreSQL deu à PK no banco criado pelo create_all antigo.
        assert insp.get_pk_constraint("sessions")["name"] == "sessions_pkey"
