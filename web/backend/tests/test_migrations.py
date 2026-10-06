"""Migrações: o head reproduz o esquema dos modelos, um banco antigo é carimbado sem perder dados,
a matriz de permissões sai semeada e a auditoria não aceita UPDATE nem DELETE.

Os testes rodam no SQLite. Com NEUROSIGHT_TEST_PG_URL apontando para um PostgreSQL descartável
(ex.: postgresql+psycopg://postgres:senha@localhost:55499/postgres), os mesmos testes rodam nele.
"""
import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, create_engine, inspect, insert, select, text
from sqlalchemy.exc import DBAPIError

from app.db import BASELINE_REVISION, alembic_config, migrate
from app.models import AuditLog, Base, LegacySession, RolePermission
from app.services.permissions import DEFAULT_GRANTS

PG_URL = os.environ.get("NEUROSIGHT_TEST_PG_URL")
HEAD = ScriptDirectory.from_config(alembic_config()).get_current_head()


@pytest.fixture(params=["sqlite", "postgresql"])
def engine(request, tmp_path):
    if request.param == "sqlite":
        eng = create_engine(f"sqlite:///{tmp_path / 'migracao.db'}")
    else:
        if not PG_URL:
            pytest.skip("NEUROSIGHT_TEST_PG_URL não definida")
        eng = create_engine(PG_URL)
        with eng.begin() as conn:
            conn.execute(text(
                "DROP TABLE IF EXISTS session_markers, session_shares, session_stimuli, sessions, devices, legacy_sessions, "
                "stimulus_tags, stimuli, patients, audit_log, role_permissions, auth_tokens, users, alembic_version CASCADE"
            ))
            conn.execute(text("DROP FUNCTION IF EXISTS audit_log_read_only() CASCADE"))
    yield eng
    eng.dispose()


def schema_diff(engine):
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), Base.metadata)


def current_revision(engine):
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def legacy_table():
    """A tabela do fluxo antigo com o nome e os índices de antes (`sessions`), sem convenção de nomes."""
    legacy = MetaData()
    table = LegacySession.__table__.to_metadata(legacy, name="sessions")
    for index in table.indexes:
        index.name = index.name.replace("legacy_sessions", "sessions")
    return table


def create_legacy_schema(engine):
    """O que as versões anteriores faziam ao subir: create_all, sem convenção de nomes nem Alembic."""
    legacy_table().metadata.create_all(engine)


def test_fresh_database_reaches_head_matching_models(engine):
    migrate(engine)
    assert current_revision(engine) == HEAD
    assert schema_diff(engine) == []


def test_migrate_is_idempotent(engine):
    migrate(engine)
    migrate(engine)
    assert current_revision(engine) == HEAD


def test_legacy_database_is_stamped_and_keeps_its_rows(engine):
    create_legacy_schema(engine)
    with engine.begin() as conn:
        conn.execute(insert(legacy_table()).values(
            id="a" * 32, device_session_id="2026-06-17_22-10-54", status="complete",
            created_at=LegacySession.created_at.default.arg(None),
        ))

    migrate(engine)

    assert current_revision(engine) == HEAD
    assert schema_diff(engine) == []
    # As sessões antigas continuam lá, na tabela renomeada.
    with engine.connect() as conn:
        rows = conn.execute(select(LegacySession.__table__.c.device_session_id)).scalars().all()
    assert rows == ["2026-06-17_22-10-54"]


def test_baseline_names_indexes_and_primary_key_like_create_all(engine):
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), BASELINE_REVISION)
    insp = inspect(engine)
    indexes = {ix["name"]: ix["unique"] for ix in insp.get_indexes("sessions")}
    assert indexes == {"ix_sessions_device_session_id": True, "ix_sessions_status": False}
    if engine.dialect.name == "postgresql":
        # Nome que o PostgreSQL deu à PK no banco criado pelo create_all antigo.
        assert insp.get_pk_constraint("sessions")["name"] == "sessions_pkey"


def test_legacy_sessions_keep_their_rows_under_the_new_names(engine):
    """A 0004 renomeia a tabela antiga com os índices e a PK, e a tabela nova usa os nomes de antes."""
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "0003_patients_stimuli")
        conn.execute(insert(legacy_table()).values(
            id="b" * 32, device_session_id="2026-06-18_09-00-00", status="complete",
            created_at=LegacySession.created_at.default.arg(None),
        ))
    migrate(engine)
    insp = inspect(engine)
    indexes = {ix["name"]: ix["unique"] for ix in insp.get_indexes("legacy_sessions")}
    assert indexes == {"ix_legacy_sessions_device_session_id": True, "ix_legacy_sessions_status": False}
    assert "ix_sessions_status" in {ix["name"] for ix in insp.get_indexes("sessions")}
    if engine.dialect.name == "postgresql":
        assert insp.get_pk_constraint("legacy_sessions")["name"] == "legacy_sessions_pkey"
        assert insp.get_pk_constraint("sessions")["name"] == "sessions_pkey"
    with engine.connect() as conn:
        rows = conn.execute(select(LegacySession.__table__.c.id)).scalars().all()
    assert rows == ["b" * 32]

    # E volta: o downgrade devolve a tabela antiga com os nomes de antes.
    with engine.begin() as conn:
        command.downgrade(alembic_config(conn), "0003_patients_stimuli")
    insp = inspect(engine)
    assert "legacy_sessions" not in insp.get_table_names()
    indexes = {ix["name"]: ix["unique"] for ix in insp.get_indexes("sessions")}
    assert indexes == {"ix_sessions_device_session_id": True, "ix_sessions_status": False}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id FROM sessions")).scalars().all() == ["b" * 32]


def test_permission_matrix_is_seeded_with_the_default(engine):
    """A lista literal da migração 0002 tem de bater com a de services/permissions.py."""
    migrate(engine)
    with engine.connect() as conn:
        rows = conn.execute(select(RolePermission.role, RolePermission.permission)).all()
    seeded = {}
    for role, permission in rows:
        seeded.setdefault(role, set()).add(permission)
    assert seeded == {role: set(perms) for role, perms in DEFAULT_GRANTS.items()}


def test_audit_log_only_accepts_inserts(engine):
    migrate(engine)
    with engine.begin() as conn:
        conn.execute(insert(AuditLog.__table__).values(
            created_at=AuditLog.created_at.default.arg(None), action="login", entity_type="system",
            entity_label="Acesso ao sistema", changes=[],
        ))
    for statement in ("UPDATE audit_log SET action = 'outra'", "DELETE FROM audit_log"):
        with pytest.raises(DBAPIError, match="audit_log só aceita inserções"):
            with engine.begin() as conn:
                conn.execute(text(statement))
    if engine.dialect.name == "postgresql":
        with pytest.raises(DBAPIError, match="audit_log só aceita inserções"):
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE audit_log"))
    with engine.connect() as conn:
        assert conn.execute(select(AuditLog.__table__.c.action)).scalars().all() == ["login"]


def test_accounts_migration_downgrades_to_the_baseline(engine):
    migrate(engine)
    with engine.begin() as conn:
        command.downgrade(alembic_config(conn), BASELINE_REVISION)
    assert current_revision(engine) == BASELINE_REVISION
    assert set(inspect(engine).get_table_names()) == {"sessions", "alembic_version"}


def test_devices_migration_goes_back_and_forth(engine):
    migrate(engine)
    with engine.begin() as conn:
        command.downgrade(alembic_config(conn), "0004_sessions")
    assert "devices" not in inspect(engine).get_table_names()
    assert "device_id" not in {c["name"] for c in inspect(engine).get_columns("sessions")}
    migrate(engine)
    assert current_revision(engine) == HEAD and schema_diff(engine) == []
