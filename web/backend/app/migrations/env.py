"""Ambiente do Alembic: a mesma configuração (QUESTPRO_DB_URL) e os mesmos modelos da API.

Funciona de dois jeitos: pela linha de comando (`alembic ...` em web/backend, com o alembic.ini)
e chamado por `app.db.migrate()`, que entrega a conexão pronta em `config.attributes`.
"""
from logging.config import fileConfig

from alembic import context

from app.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (`alembic upgrade head --sql`)."""
    context.configure(
        url=settings.db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with(connection) -> None:
    # render_as_batch: no SQLite, ALTER TABLE vira "recria a tabela", que é o que ele suporta.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_with(connection)
        return

    from app.db import engine

    with engine.connect() as connection:
        _run_with(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
